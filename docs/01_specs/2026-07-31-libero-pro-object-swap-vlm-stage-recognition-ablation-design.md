# LIBERO-PRO Object Swap 720-Step VLM Stage Recognition 补充消融实验设计

## 1. 摘要

本实验用于补充既有 RDT + EDS + RBF 在 LIBERO-PRO `libero_object_swap` 上的 OOD 评估，验证启用 `main.use_vlm_stage_recognition=true` 后，能否在抓取完成时及时关闭或切换 steering，减少 EDS guidance 对运输与放置阶段的干扰，并提高同一套 10 个 swap tasks 的成功率。

实验采用配对 A/B 设计：对两组已有非零成功率的 RBF+EDS 参数配置分别重跑 Stage Recognition OFF/ON，全部正式组将 `max_episode_steps` 从既有实验的 240 统一提高到 720。在本轮内部，除 `main.use_vlm_stage_recognition` 外，benchmark、任务、seed、policy、EDS/RBF 参数、cached guidance、720-step budget、视频与指标记录均保持一致。主实验共 4 个 jobs、40 episodes。

相对既有 OOD 结果，本轮存在两个实验变化：`max_episode_steps: 240 -> 720` 和 Stage Recognition OFF/ON；但 720 是本轮全部组的固定设置，不参与组内 sweep。因此，Stage Recognition 的因果比较必须使用本轮 720-step ON/OFF 配对结果；与历史 240-step 结果的比较只能用于观察延长 episode budget 的可能影响。

本轮只设计和执行补充评估，不修改 EDS、RBF diversity、reward 或 stage-recognition 的算法语义。若机制预检发现缓存阶段描述不适配或触发逻辑无法覆盖真实抓取，不在本实验中顺带修复，而是记录证据并单独申请后续算法改动。

## 2. 背景与实验依据

### 2.1 既有 OOD 实验

本实验继承以下结果与运行约束：

- RBF+EDS 三轮机制实验、parameter sweep、renoise ablation 和 rollout RBF 分析：
  `docs/03_evidence/eds_init_pg_diverse_sampling/`
- LIBERO-PRO object-swap 主实验报告：
  `docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md`
- Level-4 历史对照：
  `/home/hynx/VLA-Pilot++/.worktrees/feat/rdt_ed_steering_integration/docs/03_evidence/eds_steering/level_4_vls_pi05_libero_pro_ood.md`

既有 object-swap sweep 中，256 个有效 rollout-RBF jobs 仅有以下三组获得 `1/10`：

| 配置 | `renoise_t_max -> min` | rollout scale | rollout start ratio | rollout iters | SR |
|---|---:|---:|---:|---|---:|
| P1 | `2 -> 1` | 5 | 0.2 | all | `1/10` |
| 等价重复 | `2 -> 1` | 5 | 0.4 | all | `1/10` |
| P2 | `3 -> 1` | 20 | 0.6 | all | `1/10` |

在 `renoise_t_max=2` 下，start ratio 0.2 与 0.4 映射到相同的离散去噪作用范围，因此本轮只保留 0.2。另有一组 `4 -> 1, scale=5, start=0.6, iters=all` 得到 `1/10`，但只保存了 9 个视频，被既有 validity gate 判定为 invalid，不纳入本轮主配置。

### 2.2 当前阶段控制问题

当前 `main.py::_update_stage()` 会根据 gripper/reward 条件生成阶段识别触发信号，但只有在 Gemini stage recognizer 已初始化时才会真正更新 `current_stage` 和 `use_guidance`。既有 OOD 实验设置：

```yaml
main:
  use_vlm_stage_recognition: false
perception:
  gemini_grounding:
    enabled: false
```

因此视频和日志中的控制状态长期保持 Stage 1 / Guide ON。即使机器人已经完成抓取，针对抓取目标的 EDS reward 仍可能作用于运输或放置阶段，干扰后续动作。

### 2.3 Gemini Grounding 与 Stage Recognition 的边界

Gemini grounding 和 Gemini stage recognition 是独立机制：

- Grounding 用于在后端无法提供 segmentation 时定位语义目标。
- Stage recognition 用于根据当前 RGB、任务描述、阶段描述、初始关键点信息和触发原因判断当前阶段及 guidance 开关。

LIBERO adapter 已提供 segmentation，本 benchmark 不需要 Gemini grounding。为避免同时改变目标定位来源，本轮所有 A/B 组均固定：

```yaml
perception.gemini_grounding.enabled=false
```

因此，本实验只测量 stage recognition 的增量效果，不测量 Gemini grounding。

## 3. 研究问题与假设

### 3.1 主要研究问题

在相同 RDT + RBF-assisted initial sampling + RBF-assisted truncated rollout + EDS 配置下，启用 VLM stage recognition 是否能够：

1. 在真实抓取后将控制从 Stage 1 / Guide ON 切换到适合后续任务的状态；
2. 减少抓取后 guidance 对运输、释放和放置动作的干扰；
3. 将同一套 10 个 `libero_object_swap` tasks 的成功数由当前 `1/10` 提升到初版目标 `>=5/10`。

### 3.2 次要研究问题

- 现有 stage trigger 是否能稳定覆盖真实抓取事件；
- cached stage descriptions 是否足以支持 object-swap 中不同物体的阶段判断；
- Stage Recognition 的 API 延迟是否显著增加总推理延迟；
- 识别错误是否会造成过早关闭 guidance、错误切换阶段或成功率下降。

### 3.3 核心假设

- H1：Stage Recognition ON 比严格配对的 OFF 组具有更高的成功率。
- H2：Stage Recognition ON 能提高“抓取后 guidance 正确关闭/切换”的比例。
- H3：如果成功率没有提高，失败应可通过 stage-event trace 区分为未触发、API/解析失败、阶段误判，或与阶段控制无关的抓取/运输/放置失败。

## 4. 设计目标与非目标

### 4.1 设计目标

- 作为既有 OOD 实验的补充，最大限度复用原 benchmark、runner、Hydra 参数和 artifacts。
- 对 Stage Recognition OFF/ON 做任务级配对比较。
- 保留现有 EDS diversity、reward、target distance、latency 和 qualitative metrics。
- 增加足够的 stage-event 可观测性，避免把“启用了配置”误当作“机制实际生效”。
- 所有结果可断点续跑、可验证、可追踪到独立 output directory。

### 4.2 非目标

- 不启用或评估 Gemini grounding。
- 不修改 EDS、initial RBF、rollout RBF 或 reward 函数。
- 不修改 stage-recognition prompt、触发阈值或阶段定义。
- 不修复现有 gripper trigger 的 chunk 边界语义。
- 不扩大到 `libero_object_task/env/temp` 或多 seed。
- 不以 10 个 tasks 的结果宣称统计显著性或普遍收益。

## 5. 实验控制原则

相对既有 240-step OOD 实验，本轮涉及两个变化维度：

```yaml
max_episode_steps: 240 -> 720
main.use_vlm_stage_recognition: false | true
```

但在本轮 4 个正式 jobs 内，`max_episode_steps=720` 对所有组固定，唯一组内自变量为：

```yaml
main.use_vlm_stage_recognition: false | true
```

以下设置在 A/B 之间必须严格一致：

- policy checkpoint 和加载方式；
- LIBERO-PRO suite、task 顺序、init state 和 episode seed；
- RDT、EDS、initial RBF 和 rollout RBF 参数；
- cached guidance 路径及其内容；
- Gemini grounding 关闭；
- 视频、metrics、qualitative trace 和最大 episode steps；
- 硬件类型和推理精度。

不得直接将本轮 720-step Stage Recognition ON 与历史 240-step OFF 的差异全部归因于 Stage Recognition。正式 Stage Recognition 结论以本轮同配置、同任务、同 seed、同 720-step budget 的 ON/OFF 配对重跑为准。

本轮可进行两层描述性比较：

1. 历史 240-step OFF 与本轮 720-step OFF：观察延长 episode budget 后的结果变化；
2. 本轮 720-step OFF 与本轮 720-step ON：评估 Stage Recognition 的增量效果。

由于本轮不运行 240-step ON，因此不是完整的 2x2 因子实验，不能独立估计 episode horizon 与 Stage Recognition 的交互效应。

## 6. 固定实验设置

### 6.1 Benchmark 与运行规模

| 项目 | 设置 |
|---|---|
| Benchmark | LIBERO-PRO OOD Evaluation |
| Suite | `libero_object_swap` |
| Strict perturbation | `backend.libero.strict_perturbations=true` |
| Tasks / episodes per job | 10 |
| Max episode steps | 720，所有机制预检和正式 A/B 组保持一致 |
| Root seed | `seed=0`，显式写入 overrides |
| Policy | 与既有 object-swap OOD 实验相同的 RDT checkpoint |
| Guidance | EDS |
| Reward mode | `normal` |
| GPU | 仅使用空闲的 GPU 2；其他 GPU 不由本实验调度 |

每个 episode 实际生成的 `episode_seed` 必须写入 trace 或 job metadata，以验证 A/B 对应 task 使用相同的环境随机性。禁止在报告中推测或手工补写 episode seed。

### 6.2 固定 EDS 与 initial RBF 参数

```yaml
population_size: 16
cem_iters: 10
use_cem: false
num_elites: 16
temperature: 0.1

initial_sampling_mode: rbf_diverse_denoise
initial_diversity_scale: 20.0
initial_diversity_start_ratio: 0.8

truncated_rollout_mode: rbf_diverse
renoise_t_min: 1
rollout_diversity_skip_final_steps: 0
```

### 6.3 Stage Recognition 固定设置

Stage Recognition ON 组沿用当前实现默认语义：

```yaml
main:
  use_vlm_stage_recognition: true
perception:
  gemini_grounding:
    enabled: false
```

其余 stage-recognition 参数保持现有默认值，不在本轮 sweep：

| 参数 | 固定值 |
|---|---|
| Model | `gemini-2.5-flash` |
| Temperature | `0` |
| Query limit | 沿用现有默认值 50 |
| Schmitt upper threshold | 沿用现有默认值 0.8 |
| Schmitt lower threshold | 沿用现有默认值 0.6 |
| API base URL | 沿用现有 OpenAI-compatible/Poe 配置 |

Stage Recognition OFF 组必须同时确保 recognizer 未初始化，但不能因此关闭其他已有 EDS/RBF metrics。

Stage Recognition ON 使用本任务提供的 Poe API credential，但明文只允许在启动进程前通过环境变量 `OPENAI_API_KEY` 注入。不得将 token 写入设计文档、shell 脚本、命令行参数、Hydra config/overrides、日志、run manifest、报告或 Git；所有状态记录只能写 `OPENAI_API_KEY_PRESENT=true/false`。Stage Recognition ON 不允许使用 `dummy` key。

启动前应通过一个不回显 token 的最小 API health check 验证 credential、base URL 和模型可用。禁止使用 `set -x`，禁止打印完整环境变量；实验结束后从交互 shell 中清除该环境变量。

### 6.4 Cached Guidance

所有组固定复用既有 cached guidance：

`/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent`

本轮不修改缓存内容。已知其中部分 stage description 仍以 alphabet soup 为对象，而不同 swap task 的 keypoint 目标映射通常由 segmentation/keypoint 数据提供。机制预检需要专门检查这种文本不一致是否造成明显误判。

如果需要修改 stage description、prompt 或缓存，必须先停止当前实验并取得 approval，因为这会引入第二个算法变量，破坏本轮参数级 A/B。

## 7. 主实验矩阵

### 7.1 参数配置 P1：保守 rollout diversity

```yaml
renoise_t_max: 2
renoise_t_min: 1
rollout_diversity_scale: 5.0
rollout_diversity_start_ratio: 0.2
rollout_diversity_iters: all
```

### 7.2 参数配置 P2：强 rollout diversity

```yaml
renoise_t_max: 3
renoise_t_min: 1
rollout_diversity_scale: 20.0
rollout_diversity_start_ratio: 0.6
rollout_diversity_iters: all
```

### 7.3 四组配对实验

| Job label | 参数配置 | Stage Recognition | Grounding | Episodes |
|---|---|---:|---:|---:|
| `p1_stage_off` | P1 | false | false | 10 |
| `p1_stage_on` | P1 | true | false | 10 |
| `p2_stage_off` | P2 | false | false | 10 |
| `p2_stage_on` | P2 | true | false | 10 |

总规模：

- 4 jobs；
- 每 job 10 episodes；
- 共 40 episodes。

P1/P2 是两个独立参数族。P1 的 ON/OFF 只在 P1 内比较，P2 的 ON/OFF 只在 P2 内比较，不将 P1-OFF 与 P2-ON 作为 Stage Recognition 的因果对照。

## 8. 正式运行前的机制预检

在启动 40 episodes 前，先以 P1 + Stage Recognition ON 对两个代表性 task 做最小机制预检：

| Task | 选择理由 |
|---|---|
| Task 0 | alphabet soup，与 cached stage description 语义一致 |
| Task 6 | butter，既有 OOD 实验中出现成功，但与缓存文本存在语义不一致 |

预检不是主结果，不计入 40 episodes。预检必须确认：

1. Gemini stage recognizer 初始化成功；
2. strict `libero_object_swap` perturbation 确实加载；
3. 至少发生一次有效 trigger/query；
4. API response 可解析，且没有认证、配额、超时或返回格式错误；
5. stage/guidance 的 before/after 状态被 trace；
6. 视频或事件记录能够判断切换是否与实际抓取时序一致；
7. API key 未被写入任何 artifact。

以下任一情况发生时，不得直接批量运行：

- 两个 task 均没有 trigger/query；
- recognizer 初始化或查询失败；
- 返回内容无法解析；
- cached stage description 明显导致对象或阶段误判；
- strict perturbation 未生效；
- stage-event trace 缺失，无法证明机制是否运行。

此时应将预检标记为 blocked，保存日志和失败原因，并在修改 prompt、缓存、阈值或触发逻辑前申请 approval。

## 9. Runner 与输出设计

### 9.1 Runner 约束

优先扩展并复用：

`scripts/rdt_eds_eval_runner.py`

现有 runner 将 `--offline-vlm` 同时绑定到：

```yaml
main.use_vlm_stage_recognition
perception.gemini_grounding.enabled
```

本实验要求二者解耦。runner 应允许显式控制：

- Stage Recognition OFF/ON；
- Gemini grounding 始终 OFF；
- 是否使用真实 stage-recognition API；
- 独立 output root；
- `--resume`、validity check 和失败重试。

该解耦只属于实验配置/runner 能力，不应改变 `main.py` 中的算法行为。

### 9.2 输出目录

统一输出根目录：

`/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling/outputs/ood_eval/stage_recognition_ablation`

建议目录：

```text
stage_recognition_ablation/
  mechanism_pretest/
  p1_stage_off/
  p1_stage_on/
  p2_stage_off/
  p2_stage_on/
  runner_logs/
  run_manifest.json
```

每个正式 job 必须保存：

- `results.txt`；
- `.hydra/config.yaml`；
- `.hydra/overrides.yaml`；
- 10 个 per-episode videos；
- EDS metrics / JSONL；
- qualitative artifacts；
- stage-event trace；
- job log；
- task ID、episode ID 和 episode seed 映射；
- wall-clock、API query latency 和总 action latency；
- failure reason 或 invalid reason。

### 9.3 Resume 与并行

- 仅调度 GPU 2，并在启动前通过 `nvidia-smi` 确认其空闲且显存满足要求；
- 如果 GPU 2 被其他任务占用，则等待或安全续跑，不自动迁移到 GPU 0、1、3-7；
- 通过 `CUDA_VISIBLE_DEVICES=2` 启动单 GPU runner；4 个正式 jobs 原则上串行执行，每个 job 使用独立输出目录；
- 已通过 validity check 的 job 在 `--resume` 时不重复运行；
- 单个 job 失败不终止其他 jobs；
- API 限流时允许有界重试，并记录重试次数和最终状态；
- 不允许同时启动多个重复 runner。

720 steps 将单 episode 最坏运行时上限提高到既有 240-step 实验的 3 倍。runner 和交接记录必须保存每个 episode/job 的 wall-clock、当前进度及预计剩余时间，避免把长时间运行误判为卡死。

## 10. Metrics 与事件记录

### 10.1 保留现有指标

必须继续记录上一轮 OOD 实验中的全部指标，包括但不限于：

- success count / success rate；
- initial EEF diversity before/after RBF/final；
- diversity retention ratio；
- endpoint spread before/after/final；
- rollout diversity；
- reward、selected reward；
- final target distance；
- score entropy、parent rank；
- initial sampler latency；
- select_action latency；
- fallback、nonfinite 和 action-mask 异常。

新增 stage metrics 是在现有 metrics 之上补充，不得替代已有记录。

### 10.2 Stage-event trace

每次 stage trigger/query 至少记录：

| 字段 | 含义 |
|---|---|
| `episode_id`, `task_id`, `chunk_id`, `global_step` | 事件定位 |
| `episode_seed` | 配对随机性检查 |
| `trigger_reason` | gripper、reward 或其他触发来源 |
| `gripper_value_used` | 实际用于触发判断的 gripper 值 |
| `previous/current/first/last_gripper_value` | 能获取时用于诊断 chunk 边界 |
| `stage_before`, `stage_after` | 阶段变化 |
| `guidance_before`, `guidance_after` | guidance 开关变化 |
| `raw_response`, `parsed_stage`, `parsed_guidance` | API 输出及解析结果 |
| `query_latency_s` | 单次查询延迟 |
| `query_index`, `query_count` | 查询预算使用 |
| `init/query/parse_failure` | 明确错误类型 |

报告需要聚合：

- 每 episode trigger/query 数；
- API 成功率与解析成功率；
- 首次 stage transition 的 step；
- 实际抓取后 guidance-off 比例；
- premature guidance-off 比例；
- Stage 2 但 guidance 仍开启的比例；
- 查询延迟对总 action latency 的影响。

注意：当前实现发生 stage query 异常时可能记录错误后回退到 Stage 1 / Guide ON。实验 validity 不能把这种行为视为正常 OFF 结果，必须将其标记为 API/机制失败。

## 11. Qualitative Evidence

所有 40 个正式 episodes 都必须保存视频和与上一轮一致的 qualitative artifacts。Stage ON 组还需生成或叠加：

- stage timeline；
- guidance ON/OFF timeline；
- trigger/query 标记；
- grasp/close 时刻；
- stage response 摘要；
- EDS selected trajectory 与目标轨迹；
- 抓取前、抓取后、运输和放置阶段的代表帧。

每个 episode 至少标注一个主要失败类型：

- 未接近目标；
- 接近但未抓取；
- 空抓或错误抓取；
- 成功抓取但 guidance 一直开启；
- 成功抓取且 guidance 正确关闭/切换；
- 运输失败；
- 释放/放置失败；
- 过早进入 Stage 2；
- API/解析失败；
- 其他，并给出证据路径。

定性分析必须将“多样性增强”与“阶段控制改善”分开，不能仅凭轨迹更分散推断 Stage Recognition 有效。

## 12. Validity Gate

一个正式 job 只有同时满足以下条件才可记为 complete：

1. `results.txt` 存在且 success 可解析；
2. 恰有 10 个可读取的 episode videos；
3. Hydra config 和 overrides 存在；
4. `backend.libero.strict_perturbations=true`；
5. suite 明确为 `libero_object_swap`；
6. Gemini grounding 在全部组均为 false；
7. Stage Recognition 的 ON/OFF 与 job label 一致；
8. `max_episode_steps=720` 明确写入 config/overrides；
9. cached guidance 路径与设计一致；
10. metrics 和 qualitative artifacts 完整；
11. Stage ON job 中 recognizer 初始化成功，且存在可审计的 query trace；
12. 没有退回普通 LIBERO 的迹象；
13. episode seed 可用于 A/B 配对核验。

以下情况必须记为 invalid，而不能静默纳入 SR：

- Stage ON 使用 dummy/缺失 API key；
- recognizer 初始化失败；
- API 查询或解析持续失败，实际始终回退到 Stage 1；
- strict perturbation、suite 或 grounding 设置错误；
- `max_episode_steps` 不是 720；
- 视频少于 10；
- success 无法解析；
- artifacts 明显不完整；
- A/B 的 task 或 episode seed 无法配对。

非 stage-related 的少量 EDS fallback、nonfinite 或 action mask violation 也必须记录并分析；若影响 episode 有效性，应在报告中明确排除规则，不得事后按结果选择性排除。

## 13. 分析方法

### 13.1 主要结果

分别对 P1、P2 报告：

| Profile | Stage OFF successes | Stage ON successes | Paired delta | OFF SR | ON SR |
|---|---:|---:|---:|---:|---:|

同时给出 task-level 配对表：

| Task | P1 OFF | P1 ON | P2 OFF | P2 ON | Stage event summary | Failure type |
|---|---:|---:|---:|---:|---|---|

### 13.2 次要结果

- 抓取尝试数与成功抓取数；
- 抓取后 guidance 正确关闭/切换的 episode 数；
- 过早切换和错误切换数；
- 无 trigger、无 query、API failure、parse failure 数；
- query latency 和端到端 latency；
- Stage ON/OFF 下 EDS diversity、selected reward、target distance 的差异；
- 不同 profile 对 Stage Recognition 的敏感性。

### 13.3 历史结果使用

历史 `rdt_unguided`、`eds_iid_baseline` 和 257-job sweep 结果可在报告中作为上下文完整列出，但必须标注 `historical/reference, max_episode_steps=240`。Stage Recognition 的正式增量结论只来自本轮 720-step 配对 A/B。

报告应单独提供 horizon 补充表，比较相同 P1/P2 参数的历史 240-step OFF 与本轮 720-step OFF。该比较用于判断旧失败是否仅因 240-step timeout，但受历史运行差异影响，只能作为描述性证据。因为缺少 240-step ON，不得报告 horizon x stage-recognition interaction effect。

样本量只有 10 个固定 tasks，报告以描述性结论和 task-level evidence 为主，不进行过度的显著性宣称。

## 14. 成功判据与决策规则

### 14.1 初版目标

最强 Stage Recognition ON 配置在同一套 10 个 swap tasks 上达到：

```text
successes >= 5/10
```

### 14.2 结果分级

- **强正向**：至少一组 Stage ON 达到 `>=5/10`，且机制 trace 无系统性错误。
- **有希望**：至少一组 Stage ON 相比配对 OFF 增加 `>=2` 个成功任务，且无明显 premature transition 或 API 失效。
- **中性**：ON/OFF SR 相同；进一步检查抓取成功数、trigger 覆盖和抓取后 guidance 状态。
- **负向**：Stage ON SR 更低，或过早切换、阶段误判明显增加。
- **不可评估**：Stage ON 未发生有效 query/transition，或 API/缓存问题使 recognizer 实际没有运行。

如果 Stage Recognition 能改善抓取后的 guidance 状态，但 SR 仍低于目标，下一步优先定位抓取质量、grasp-aware reward、stage-conditioned reward 和 EDS selection，而不是继续盲目扩大 stage 参数 sweep。

## 15. 已知风险

### 15.1 Gripper trigger 的 chunk 边界

当前新 chunk 开始时 `action_executed` 可能重置为 0，触发逻辑读取上一 action chunk 的首个动作而非末尾动作，从而漏掉 close transition。本轮不修改该逻辑，但必须记录 first/last gripper 值并在报告中统计漏触发证据。

### 15.2 Cached stage description 语义不一致

缓存文本可能仍描述 alphabet soup，而实际 task 是 butter 等其他物体。虽然 keypoint 映射可能正确，但 VLM 阶段判断可能被文本误导。Task 0/6 机制预检专门用于暴露该风险。

### 15.3 Stage 2 reward 语义

现有 cached Stage 2 reward 可能为零。如果 recognizer 返回 Stage 2 + Guide OFF，系统退回 unguided RDT；如果返回 Stage 2 + Guide ON，则 EDS 可能在零 reward 下运行。两种情况均需明确记录，不能笼统视为“进入放置阶段”。

### 15.4 API 可靠性与成本

真实 Stage Recognition 依赖外部 API，存在认证、配额、限流、延迟和返回格式风险。错误回退到 Stage 1 会掩盖失效，因此必须以 trace 和 validity gate 单独识别。

### 15.5 小样本波动

10 个固定 tasks 适合验证能否达到 `>=5/10` 的工程目标，但不足以证明跨 seed 或跨 suite 的稳定提升。达到目标后再决定是否扩展到更多 seeds 或 `task/env/temp`。

## 16. 最终交付物

### 16.1 输出与报告

实验输出根目录：

`outputs/ood_eval/stage_recognition_ablation`

最终报告：

`docs/03_evidence/eds_init_pg_diverse_sampling/2026-07-31-libero-pro-object-swap-vlm-stage-recognition-ablation-report.md`

报告必须包含：

1. 完整 Hydra 参数和 policy/checkpoint 信息；
2. 机制预检结果；
3. 4 个正式 jobs 的 validity 状态；
4. task-level 配对 SR 表；
5. 历史 240-step OFF 与本轮 720-step OFF 的描述性对比；
6. Stage OFF/ON 机制指标；
7. API 和总延迟；
8. 所有失败类型及证据路径；
9. representative videos/qualitative artifacts；
10. 是否达到 `>=5/10`；
11. 下一步算法建议及其证据依据。

### 16.2 完成前检查

- 机制预检已通过，或有明确 blocked 原因；
- 4 个正式 jobs 均为 complete，或有明确 failed/invalid 原因；
- complete job 均有 `results.txt`、Hydra config 和 10 个视频；
- A/B task 与 episode seed 已配对；
- 所有机制预检和正式 jobs 均明确使用 `max_episode_steps=720`；
- strict perturbation 和 suite 已验证；
- grounding 在所有组均关闭；
- Stage ON jobs 有真实 query trace；
- API key 未出现在 artifacts；
- 最终报告已生成；
- runner 只使用 GPU 2，其他 GPU 未被本实验占用；
- 没有遗留 runner 或 `main.py` 实验进程。

## 17. MVP 实施边界

本轮 MVP 只需要：

1. 在 runner 中解耦 Stage Recognition 与 Gemini grounding 配置；
2. 增加本设计的 P1/P2 配对 job matrix；
3. 补充 stage-event trace 和 validity check；
4. 执行机制预检、4 个正式 jobs 和报告生成。

本设计阶段不实现代码、不启动实验，也不修改任何算法参数或 cached guidance 内容。实验执行前如需修改 stage prompt、缓存描述、gripper trigger、reward 或 EDS 核心逻辑，必须单独说明原因并取得 approval。
