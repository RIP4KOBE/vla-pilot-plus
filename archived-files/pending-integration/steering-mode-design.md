# Phase 4 / 5 三模式配置及审计草案（只读核对，未实施）

范围：根目录 `/home/hynx/lizhuo/VLA-Pilot++`，当前 `codex/rdt-steering-integration`。未改 runtime/config/scripts/tests，未运行测试、GPU、模拟或 API。当前入口仅释放 EDS：`scripts/steering_runtime.py:79–81`。以下都用于当前冻结 EDS cohort 完成后的实施；不能据此宣称 VLS/QD 已验收。

## 1. 共同评测契约与最小模式差分

保留 `configs/evaluation/libero_object_swap.yaml` 的任务 0–9、种子 `[44,235,43,546,6,621,197,87,151,548]`、20 个 prepare/rollout RNG fixtures、同 RDT EMA/T5/SigLIP/DINO/LIBERO 资产、8 步执行、720 环境步上限、实时 Codex `gpt-6-astra/low`、共同 Stage 与 target_distance 奖励生成/验证机制。实际 Stage 查询/轨迹不必相同：算法改变轨迹后，查询触发会自然分化；匹配规则与上限，不伪造查询数一致。保持 `cached_functions_dir: null` 和每任务新生成奖励，禁止历史回复回放。

| 对外 method | `main.guidance_type` | `qd_archive_mode` | 主要预算 |
| --- | --- | --- | --- |
| `vls` | `vls` | `none` | 原 main RDT VLS，有效 B20；每 guided chunk 一次完整 5 步去噪 |
| `eds` | `eds` | `none` | 本轮冻结 16 粒子、10 轮、11 个搜索评分批次、176 候选 |
| `eds_qd` | `eds` | `grid_archive` | 与 EDS 同预算；替换父代来源与最终候选选择 |

不要把 `eds_qd` 直接传给 policy 的 `guidance_type`：`core/rdt_policy_steer.py:1637–1652` 只认 `vls/eds`。manifest/method_label 记录 `eds_qd`。

EDS 与 QD 都保留 `qd_metrics_observer: true`，shadow observer 是日志，不是启用档案的证明。VLS 可显式关闭无意义的 EDS observer/EDS mechanism pretest，但保留共同视频/Stage/compute 日志；这一诊断差异必须在 manifest 显式记录。

## 2. VLS 应保留的原 main **实际有效** setting

`configs/config.yaml:50–64` 表面值：B20、guide40、diversity10、start_ratio null、MCMC4、sigmoid(25,.75)、FKD max/λ10/adaptive/freq5。然而 `core/env_adapters/libero_adapter.py:1775–1783` 在没有 `task_guide_scales` 时给出 `recommended_guide_scale=80`；`main.py:614–626,1525–1530,1780–1783` 覆盖 YAML 的 40。当前原 main 与共同 OOD YAML 都没有 task_guide_scales。

因此保留原 main 的 effective setting 应写清：

```yaml
main:
  use_guidance: true
  guidance_type: vls
  vls_config:
    sample_batch_size: 20
    use_diversity: true
    guide_scale: 80.0  # 显式反映原 LIBERO adapter 的有效值
    diversity_scale: 10.0
    start_ratio: null
    MCMC_steps: 4
    sigmoid_k: 25.0
    sigmoid_x0: 0.75
    use_fkd: true
    fkd: {potential_type: max, lmbda: 10.0, adaptive_resampling: true, resample_frequency: 5}
backend:
  libero:
    task_guide_scales: [80, 80, 80, 80, 80, 80, 80, 80, 80, 80]
```

若任务子集被入口重排/裁剪，task_guide_scales 按 adapter 的 `current_task_idx`（子集局部序号）对齐；本次所有值相同不会歧义。若决定 guide40，必须显式 task_guide_scales=[40]*10，并标记为新参数选择，不能说它保留了原 main 有效值。

`MCMC_steps=4` 在 RDT `_vls_guided_denoise_loop` 仅被读取（1797–1805），不驱动 MCMC 内循环；不能报告 4 次 MCMC 或四倍 forward。`start_ratio:null` 实际取 scheduler 第 floor(T/3) 个 timestep（7132–7137），5 步时为索引1；初段一次 RBF，后4步 keypoint gradient。Denoising DiT `no_grad`，反向传播仅经过动作→EEF几何与奖励（1824–1856；7076–7106）。

FKD 初始化开启不代表每步都重采样。当前 freq5 在5步 scheduler 的 guidance 段仅产生一次非终末评分机会；terminal 调用被显式跳过（1866），最终由 argmax reward 选择（6820–6834），且可视化排序再评分一次（6836–6850）。MAX potential 使用 max(current_reward, history_reward) 再 exp(λ reward)，ESS≥B/2 时合法不重采样（core/fkd_class.py:243–285）；不能仅以配置开关作为已发生重采样的证据，也不能因某chunk resample次数为0判无效。

历史文档 `docs/03_evidence/2026-06-03-rdt-libero-vls-hparam-validation.md:47–55,89–93` 的最好完整 ID setting 是 B20/guide20/diversity1/FKD on/旧Stage off 的7/10，未达到当时 unguided9/10门槛。它不是本次 OOD/共同 Stage 已验收 baseline；不应为了结果替换成那组值。

## 3. EDS+QD 首次固定档案方案

继承当前 EDS 全量 setting，只开启以下固定档案选择；不混入 N 系 adaptive/causal-envelope/secondary/global-anchor/execution-intent 等实验机制：

```yaml
main:
  guidance_type: eds
  eds_config:
    qd_archive_mode: grid_archive
    qd_degenerate_fallback_policy: none
    qd_descriptor: target_relative_endpoint_xy
    qd_grid_shape: [4, 4]
    qd_cell_capacity: 1
    qd_secondary_lane_mode: none
    qd_parent_sampling: sparse_priority
    qd_global_quality_anchor_count: 0
    qd_sparse_exponent: 1.0
    qd_bounds_quantiles: [0.05, 0.95]
    qd_bounds_expand_fraction: 0.10
    qd_min_axis_span_m: 0.08
    qd_bounds_update_policy: fixed_initial
    qd_overflow_policy: clamp_edge
    qd_tie_break: stable_fingerprint
    qd_metrics_observer: true
```

共同 EDS 设置需保持：population16/cem_iters10/use_cem false、renoise3→1、initial `rbf_diverse_denoise` absolute_eef/scale20/start.8、rollout `rbf_diverse` absolute_eef/scale20/start.6/iters all、legacy_temperature、no extra elite/anchor、fresh chunk population、memory fraction0、fixed RBF control、legacy_linear search、fixed horizon8。`core/rdt_policy_steer.py:7613–7644` 对 grid_archive 已强制这些条件。

实际枚举就是 `sparse_priority`，不是 `sparse` 或 `sparsity_priority`。`core/qd_ed.py:779–831` 在已占据格中使用 `w_c=(cumulative_visits[c]+1)^(-1)`，将16槽按归一权重分配整数下界，剩余按最大余数分配，局部带种子的打散仅处理余数平手。访问计数统计每个候选落格，包括被拒绝者（426–427），不是只统计被选为父代次数。

Descriptor 为当前观测运动学投影的第8步末端 EEF XY减第一个目标关键点XY；不是64步末端，也不是实际模拟未来结果。`rdt_policy_steer.py:4641–4653,6890–6911`、`qd_ed.py:51–71`。Bounds由初始16候选每轴5%/95%分位数向两侧各扩10%原始span，若不足.08m则绕中位数补到.08m（110–169）。越界夹到边格，不能把合法overflow作为运行无效。

每个 guided chunk 新建档案（`rdt_policy_steer.py:4839,4880–4900`），初始16候选先入档，然后10轮每轮从档案选16父代、renoise/truncated-denoise、评分、入档。每格最多1个最高reward精英，平手按稳定action指纹（`qd_ed.py:468–502`）。最后执行档案全局最高reward候选（6413–6463）。档案只跨此chunk的10轮存活，不跨chunk/episode，不能宣传为跨任务recursive self-improving。

## 4. 当前已有的 QD 证据与应补的审计

当前 `scripts/audit_steering.py:70–82` 只验证EDS基础参数和 `qd_archive_enabled`；尚未证明实际父代替换/档案更新/最终选择。下面字段已存在 `core/eds_eval_metrics.py:427–515`，多数可直接离线审计，无需新增采样或改变搜索。

每个 guided chunk 应校验：

1. 方法与配置：grid_archive、active_for_chunk true、descriptor/grid/capacity/sparse/bounds均匹配；fallback和degenerate fallback false；secondary/anchor0，固定边界扩张0；EDS控制组 archive_enabled=false、active=false。不能把 shadow_qd_observer_enabled 当启用档案证据。
2. 预算：`population_size_observed=16`、`eds_iters_executed=10`、`score_call_count=11`、`search_evaluation_count=176`、`qd_evaluation_count=176`；per_iter/qd系列数组长度10，shadow stream长度11且每条16候选。注意搜索评分预算与实际全部 reward_calls不同（见下一节）。
3. 初始档案：`qd_initial_accounting.total=16`，insertions+replacements+rejections=16，初始replacements=0、insertions=initial_occupied_cells，格数量1..16；利用 shadow初始descriptor重算bounds/checksum/cell访次与胜者。
4. 每轮更新：insertions+replacements+rejections=16；累计访问sum在第 i=0..9轮为16*(i+2)，最终176；每格访问非递减；occupied数量1..16且固定边界下不减；coverage=occupied/16；已有精英格reward不减；accounting/monotonicity/selection mismatch全0。相同reward完全合法，不要求严格改善。
5. 真实父代：`qd_parent_slots_by_cell_by_iter` 每轮总和16、键为前一轮已占据格；`qd_parent_weights_by_cell_by_iter` 与上一状态 `(visits+1)^-1` 一致；可用同局部seed/episode/global_step/iter重算最大余数分配。`parent_count_by_source.qd_archive_offspring=160`；per_iter相关来源16，`weighted_offspring/anchor/elite=0`。不要要求每格必有slot或covered_cell_ratio=1，稀疏优先可能合法给某格0槽。
6. 最终选择：`selected_chunk_population_source='qd_archive'`；selected_cell存在、selected_reward与全局max一致、两个selected/global_best指纹一致，mismatch0。仅比较两个同源写入的指纹不够强：可从 `shadow_qd_candidate_stream` 重建每格winner与全局best，并核对每轮snapshot/pretest trace的父代与最终action；现有trace只覆盖有限qualitative chunks，不宣称全程保存了action tensors。
7. 生命周期：每chunk初始访次重置、初始accounting16、bounds来源于该chunk初始descriptor，不继承上一chunk；fresh memory保持关闭。archive ID/生命周期标签可加为可解释字段，但现有shadow+初始accounting已能核对多数要求。

科学结果与有效性分类应分开：

- `infrastructure_valid`：worker/JSONL/资产/源码/hash/设备、episode无运行异常、规定任务及seed完结。配置违反或少执行算法为protocol/mechanism failure，不能笼统都记infrastructure error。
- `method_valid`：上列机制与预算正确、真实online Stage/reward契约、无静默退化到EDS。
- 科学结果：10任务env success、coverage/spread/overflow/平手比例/边缘格拥挤/更新率/选择来源年代、latency等。0/10、低coverage、全reward平手、大量clamp、无精英提升均可在运行与方法有效时成立，保留结果并解释机制局限；不得用这些指标把失败cohort剔除。

## 5. VLS 日志缺口与验收分类

已有 Stage、reward contract、RNG、episode_compute、环境success共同审计可复用。`main.py:1850–1858` 只为EDS采集chunk metrics，因此VLS没有相应的逐chunk机制证据；当前 audit 对 VLS也没有特定分支。

phase4 建议新增不改变算法的逐chunk VLS telemetry（审计新增观测本身应有不改变action/RNG的CPU检查）：method/resolved B/effective guide_scale/actual timestep list/start阈值、keypoint gradient attempted/returned/applied/zero/nonfinite/exception数量与norm、RBF attempted/applied、FKD initialized/score opportunities/actual resample/ESS、最终selection_source和best reward指纹、finite action与translation-slot mask违规数、该chunk compute counter差分。MCMC declared字段应标记未执行，不伪造计数。VLS `_compute_keypoint_gradient` 可因非tensor/no-grad/nonfinite/异常返回None（7088–7091,7107–7111,7119–7121），单看use_guidance=true并不足以证明梯度生效。

CPU检查只在冻结结束后做：模式routing/配置裁剪与effective guide80覆盖检查；5步scheduler VLS gradient/FKD/best-selection调用路径；target_distance的batch梯度与数值契约；telemetry对随机数状态/action无干扰；QD sparse父代/固定bounds/生命周期/176预算；审计负样本（标志开但父代未替换、少一轮、selection指纹错应失败，低成功/低coverage/平手应仍valid）。已有基础测试位置 `tests/test_rdt_steer.py:529–632,6305–6403` 和 `tests/test_qd_ed_archive.py`，但前者主QD全loop测试是uniform配置；应补sparse整条路径，不能靠uniform测试声称sparse已验收。本次没有运行任何测试。

## 6. Compute 差异与可比较口径

读取实际EMA `config.json` 的 `noise_scheduler.num_inference_timesteps=5`；`rdt_policy_steer.py:1159–1160`在override=null时采用它。

| 每个正常guided chunk，无fallback | VLS原main | EDS / EDS+QD |
| --- | --- | --- |
| 粒子数 | 20 | 16 |
| DiT forward batches | 5 | 5+sum([3,2,2,2,2,1,1,1,1,1])=21 |
| DiT batch rows | 100 | 336 |
| denoising invocations | 1 | 11 |
| renoise invocations | 0 | 10 |
| RBF gradient batches（按当前开关） | 1 | 4初始+15截断=19 |
| 奖励使用 | 4次梯度批评估+FKD机会+final selection及visualization评分 | 11搜索评分批次，共176候选；trace可能额外评分 |
| 额外QD工作 | 无 | 投影descriptor/hash/档案更新/稀疏父代分配，非额外DiT |

推导依据：VLS1785–1897、EDS initial2758–2799、trunc schedule5089–5093、RBF mask3473–3485。这说明三模式保留原设置不是compute-matched三组实验。EDS与QD同主搜索预算，但QD有实际CPU/geometry开销；VLS与EDS的主模型batch rows是100vs336（3.36倍），此外VLS有reward梯度，不能把该比值当wall-time比。

`score_call_count=11/search_evaluation_count=176` 是算法搜索账，**不是总reward调用账，也不是11个模型调用**。例如pretest trace的initial intermediate scores在5048–5054额外调用reward却不计入search count；VLS可视化也有额外评分。真实episode compute现有字段（1393–1431；main1275–1294）：model_forward_calls/model_batch_rows/model_denoising_steps/denoising_step_batch_rows/reward_calls/reward_evaluations/reward_scoring_batches/rbf_gradient_calls、encoder/DINO、Codex attempts/completions/token可用性。VLS尚缺keypoint-gradient backward计数，须单独记录。

报告同时给每guided chunk均值/分布、每环境步、每episode总预算和wall-time；各模式guided chunk数及成功提前结束会不同，不能只比episode总数。EDS–QD主比较固定16×10与共同Stage；若另做三模式等预算实验，应另立配置/实验，不能在本次迁移验收中把VLS偷偷改到匹配336rows。Stage查询次数与token仅作为在线成本记录，不预先强迫相等。

## 7. 执行顺序建议

本轮EDS冻结cohort按既有规则完整完成并保留结果。随后phase4先实现/CPU核验VLS mode与其最小telemetry，再完整10任务；phase5固定上面的QD profile+离线严格审计，再完整10任务。成功率不是启动重跑的自动开关：低于历史3/10先归因并保留本轮；只有预定义需要的同步源包/集成对照才各再10一次，避免反复抽样挑高分。预算按2–3小时/10任务规划，不以该规划作强杀超时。
