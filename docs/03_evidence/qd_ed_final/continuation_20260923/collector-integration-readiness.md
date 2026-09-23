# Node 5.2 collector integration readiness

审查日期：2026-09-23 UTC。源码基线：E 分支 `2c4a591add2f697e60fb6292a8fd8f1222134a4e`。本次仅 CPU 源码审查及读取已完成 CPU 测试产物；未改 W、runner、profiles、账本，未运行 GPU，未重跑全套测试。

结论：collector 的真实 CPU 路径已贯通，但**尚不能直接把下一轮标为与无 observer 的历史运行等价**。需要先冻结共同观测条件、审计脚本和单独证据有效性门槛。当前未发现需要立即修改 collector 算法路径的缺陷。明确剩余工程风险是逐次 GPU→CPU 拷贝可能同步、细碎 fsync、整 episode 审计 RAM，以及 runner 尚未绑定新观测条件/调用审计。

## 1. 大小估计与 I/O 边界

以下估计只针对新增 `decision_evidence`，不包含原视频、机制 trace、qualitative、模型或其他日志。

形状条件：`B=16`、`I=10`、latent `[B,64,128]`、执行 horizon `H=8`、archive 最多 16 个质量单元。来源：`configs/qd_ed_final/baseline_profiles.json` 的 C0/Q0 `static_override_values`；`configs/policy.yaml:38`；`configs/backend/libero.yaml:25`（最多 720 动作）。固定 8 动作完整前缀时最多 `ceil(720/8)=90` 次决策；提前终止或关闭 guidance 会减少重型 guided bundles。此处没有把每个实际 episode 都假定为 720 步。

`core/decision_evidence.py:24` 对每份 tensor 执行独立 CPU clone；重复内容不会因为相同 fingerprint 自动去重。重型数据来自：

| 每次 guided 决策的数据 | 发生次数 | BF16 主体大小 |
| --- | ---: | ---: |
| `scoring_inputs.samples` | 正式 11 次 | 2.75 MiB |
| `canonical_candidate_batch.candidates` | 11 次 | 2.75 MiB |
| `parent_allocation.source_population` | 10 次 | 2.50 MiB |
| `final_selection.population` | 最多 16 行 | 0.25 MiB |
| final selected + decoded selected latent | 各 1 行 | 0.03125 MiB |
| 合计，不含 metadata/小张量/辅助评分 | — | **8.28125 MiB** |

每多一次整批辅助评分，再增加约 0.25 MiB 的 BF16 latent；完整投影 `[16,9,3]`、原 reward 切片 `[16,7,3]`、quality、provider 原始标量和 origin 较小，但大量小 tensor/字典的序列化开销不能忽略。FP32 主体是 BF16 的两倍。来源：`core/rdt_policy_steer.py:1752`、`:4880`、`:5194`、`:5402`、`:6527`。

**现有 CPU 实测**，没有新增运行：`/tmp/pytest-of-hynx/pytest-17/test_decision_evidence_audit_a0` 为 C0/pretest 开；`...a1` 为 Q0/pretest 关。二者均是 16 粒子、10 轮、stub 5 denoising steps、单次决策。模型张量是 FP32，不冒称生产 BF16 测量。

| 量 | C0/pretest 开，终止 1 动作 | Q0/pretest 关，截断 2 动作 |
| --- | ---: | ---: |
| scoring batches（正式+辅助） | 11+5 | 11+0 |
| projection_origin 事件 | 2320 | 2079 |
| 最大 bundle 字节 | 21,632,749 | 18,810,501 |
| 全部 bundle 字节 | 21,640,003 | 18,821,739 |
| episode 目录全部文件字节 | 21,949,022 | 19,093,866 |
| episode 目录 MiB | 20.9322 | 18.2093 |
| collector 计时子集秒 | 0.496536 | 0.309877 |

上述数字已由本轮工具实际读取 status、bundle 文件大小及 CPU tensor 字节确认。随后尝试补记 manifest SHA 时，临时 `pytest-17/...a0/.../events.jsonl` 已不存在（并发 pytest 的临时目录保留/清理可能影响它）；没有补造原 SHA，也未为恢复临时文件重跑测试。故表格是已确认的临时 CPU 产物 readback，不能冒充可长期复查的冻结实验 artifact。

这些不同 CPU 条件的时长**不是两臂速度比较**。只将上述实测中可明确识别的主 latent 存储改按 BF16 算，其余字节原样保留，得到约 **11.401 / 9.944 MiB 每决策**。这是形状推算，不是 GPU 实测，也不是严格字节上界。小张量 dtype、provider 数、keypoint 数、完整模型 denoising steps、archive 占用与 metadata 都会影响总量。BF16 原值被保留；fingerprint 的 FP32 转换仅规范化内容哈希，不增加数值精度。

用这些单决策样本线性外推 90 次 guided 决策，FP32 约 **1.84 / 1.60 GiB 每 episode**；BF16 主体推算约 **1.00 / 0.87 GiB**。实际冻结 C0/Q0 profiles 均有 `eds_mechanism_pretest.enabled=true`、`first_chunk_only=false`、`max_chunks=2`：`core/rdt_policy_steer.py:4201` 没有 `max_chunks` 判断，`main.py:1935` 的上限只管旧 trace 保存。因而不能把 Q0 无 pretest 的 CPU 数量直接当下一轮 Q0 实际量，也不能为了省 I/O 悄悄关闭辅助评分。以现有形状为基础，**1–2 GiB/episode 是规划数量级，不是硬上限**；若保守按 25 MiB/decision 预留，90 次约 2.20 GiB，4 episode 约 8.79 GiB；可在冻结前给新增 collector 留至少约 12 GiB 空间余量，原视频/trace 另算。25 MiB 和 12 GiB 是建议的规划余量，不是已测保证或新增截断规则。

完整健康 episode 的 bundle 数约 `决策数 + 3×动作数 + terminal自动reset额外1`：720 步、90 决策最多约 2251 个 bundle。`commit_decision`、`dispatch`、outer `executed_action`、`step_returned` 分别 flush；terminal snapshot 另在 reset 前 flush（`core/decision_evidence.py:201`、`:213`、`:222`，`core/env_adapters/libero_adapter.py:1709`）。每 bundle 有数据、JSONL、目录三次 fsync，加 status 临时文件替换（`:244`）。因此限制可能是小文件持久化延迟和 inode，而非大文件带宽。未测生产目标盘延迟。

collector 峰值不是整个 episode 累积：每次决策 pending 列表在 commit 后清空。但是序列化时 CPU tensor 副本和用于 SHA 的完整文件 bytes 同时存在（`:252`、`:256`、`:273`），故峰值至少可接近两份有效载荷，另有 Python/torch 对象、serializer 和原算法内存。**没有测得严格 RAM 上界。**

离线 auditor 则在 `scripts/audit_decision_evidence.py:37` 的 `load_events()` 累积整 episode 张量，随后按决策建立引用索引（`:86`、`:94`）。对于约 1–2 GiB 文件，实际 RAM 会更大；建议串行审核 episode，CPU RAM 预算至少预留数 GiB，并在首个完整观测 episode 测峰值。若空间/RAM 不足，应在下一次冻结前明确调整持久化实现或资源预算；不能偷偷少存候选、跳 event、降精度或把缺失字段填零。

## 2. 冻结清单及当前 runner 缺口

` scripts/qd_ed_final_runner.py:32–43` 的 REQUIRED_CODE 递归收集 `core/`、`utils/`、`vlm_query/` 的 `.py/.txt`；不是只看静态集合。

| 文件 | 默认 REQUIRED_CODE 覆盖 | 下一轮要求 |
| --- | --- | --- |
| `core/decision_evidence.py` | 是，递归 | 必须出现在新 plan.code_files，不能复用旧 plan 清单 |
| `core/rdt_policy_steer.py`、`core/env_adapters/libero_adapter.py` | 是 | 冻结集成后字节 |
| `main.py`、`configs/config.yaml` | 是，显式 | 冻结默认值与启用路径 |
| `scripts/audit_decision_evidence.py` | **否** | 显式加入 code_files，或后续有授权地加入 REQUIRED_CODE |
| 本轮测试文件 | 否，非运行依赖 | 保存提交号/测试命令；若审查协议要求 CPU 复现，则另行冻结这些文件 |
| 未来调用 audit 的 wrapper/runner 变更、共同观测协议/配置 | 尚未实现 | 一并冻结，不能仅冻结 collector |

`validate_plan():185–202` 核对 HEAD 和清单哈希；仅 HEAD 对未入清单脚本的未提交漂移没有同等字节保护。auditor 已提交的 SHA256：`4bc0ab26bde72308ebdf87b89519d74d30098775698a3c39e8e22bba5fed5999`；collector：`6af1088737787f17601bf720510c7115adc4f2f35d6e628c60944ad6fecb4ae0`。

现 runner **没有** decision_evidence 配置绑定或 audit 调用。`build_command():305–342` 从 profile static overrides 组装命令，`runtime.main_overrides` 又必须恰为 cache identity guard。不能仅在 runtime 任意追加 observer flag 后宣称已受冻结。下一步最小集成需要一个明确命名、两臂共用的观测 condition binding，并把 `main.decision_evidence.enabled=true` 纳入命令及 resolved-config 核验（现核验入口 `:786`）。不需要修改原 reward/Stage/action profile。

审计结果应另存 `{original_execution_outcome, evidence_complete, accepted, errors}`。保持 Main 原成功/失败结果及成本，**证据缺失不能被改写成原执行 error，也不能被当作观测条件有效样本**。这项单独门槛尚未接入 runner；本报告没有替它作已集成声明。

## 3. 下一轮四 episode 的共同观测条件

这是前瞻安排要求，不是新的 dispatch 或候选授权。两臂和两组任务/seed 配对必须由同一新冻结 plan 明确，顺序在读结果前固定。

- 两臂使用同一集成 HEAD、collector/auditor 字节、相同 observer enabled=true、完整事件 schema、原生 dtype、无降采样、相同 flush/fsync 策略与输出盘；同一 GPU3 运行条件和已有独占准入。使用新 attempt 身份，不改写当前无 observer C0。
- 保持已冻结的模型、provider/Codex wrapper、cache、policy/env seeds、task/init row、horizon/720步上限、pretest 等条件；观测开关独立于 pretest，不能以“打开日志”为由额外打开或关闭旧 trace 计算。
- 新条件明确标识为 `decision_evidence_v1`（建议名字，尚未写入 runner），与 observer-off 历史结果分列。四条都保留原任务结果、原实际成本、完整性状态；只对通过独立 gate 的记录作精确过程分析。缺数据保持 Unknown，不自动重试同身份、不补 future 反馈参与选择。
- 报告原 whole-episode、select_action、policy/Stage/perception counters，并单独报告 `observer_wall_s`、bundle bytes/数量。这个 observer 时长只涵盖 snapshot/fingerprint/bundle flush，明确排除了 status/scalar bookkeeping（`core/decision_evidence.py:85`）。`select_action_latency_s` 已包含内部 observer 时间（`main.py:1776`）。不可相加重复收费，也不可直接相减后声称恢复“无 observer 真实时延”。GPU→CPU 拷贝可能等待已有 CUDA 工作，CPU 子集计时不是纯日志独占时间。
- 首个实际观测 episode 应保存 bytes、磁盘余量、审计进程 RAM 峰值、完整性与已有模型/denoise/reward/Stage 计数。共同开关消除一项不对称，但不证明 GPU 数值等价；当前没有 observer on/off 的真实 GPU 配对结果，也没有由四条小样本支持的性能提升结论。

## 4. 默认关闭及不干预算法的现有证据

`configs/config.yaml:42` 默认 false；`main.py:1558` 仅显式开启才构造 collector。RDT/adapter hooks 对缺失的 `_decision_evidence` 只做 `getattr(..., None)` 检查，不生成附加 provider、model、projector、render、step、reset 或 Stage 调用。评分 scope setter 的 disabled 分支同样不采样。

源代码中 `_counted_reward():1428` 返回原 provider result；projection 从原表达式命名现有 full_trajs，adapter 从原一次 get_ee_pose_world 读中保存局部值（`:1653`），没有第二次状态读取。`_snapshot()` 使用 detach/cpu/clone 或 ndarray.copy，fingerprint 仅作用副本，没有 RNG API或写回动作/模型张量。collector 的状态只用于记录 ID/有效性；生产选择分支不读取未来 outcome。时间、内存、GPU 同步副作用仍客观存在。

已有检查，不在本审查中重跑：

| 检查 | 位置/结果 | 能证明的范围 |
| --- | --- | --- |
| observer off/on 实际 stub select_action，pretest各开关 | `tests/test_rdt_steer.py:8263` | 完整 action、CPU RNG state、model/projector/provider 调用序列和计数相同 |
| 原始 provider dtype/真实 quality | `tests/test_rdt_steer.py:8352` | 实际 score API返回截取，不用 XY 代理替代；BF16/native dtype 保留 |
| 实际 adapter/projector AST方法 | `tests/test_decision_evidence.py:63,124` | 同一动作后处理/step/reset次序、9点投影、不增加 pose 查询；终止前冻结值 |
| 实际 Main observer故障 | `tests/test_main_rdt_startup.py:1357` | 成功/未成功 × bundle写失败/初始写失败/缺hook，原 outcome=completed 与 success_count保持，证据失败单列 |
| 真实 Main→C0/Q0→adapter→compute→audit | `tests/test_rdt_steer.py:9698`；2 passed/14.69s | C0 pretest开终止成功；Q0 pretest关两步截断；全部事件由原方法生成，无测试手工补 event |
| 默认关闭相关回归 | 548 passed/26.48s；后续 helper修复定向16+5 passed | CPU 回归；不含 GPU 数值等价或真实机器人/物理任务验证 |
| 独立 audit 与 collector | 22 passed/1.82s | SHA、weights_only、事件顺序、角色/指纹/执行/终止关联；正确重算 SHA 后的语义损坏仍拒绝 |

贯通测试使用 AST 载入未编辑的 Main/adapter 方法以避开 import-time `.env`/native 初始化；底层 native env、模型、Stage/视频依赖为 CPU stubs。它覆盖记录接口连通性，不能覆盖真实 EGL/CUDA 生命周期或生产 I/O 时序。当前 LIBERO env_postprocessor 是空 steps（`core/env_adapters/libero_adapter.py:1007`）；auditor 对 decoded 与 committed chunk 的相等检查适用于这个现有条件，未来若有非恒等 postprocessor 必须另行审查，不能直接复用这一 gate 断言。
