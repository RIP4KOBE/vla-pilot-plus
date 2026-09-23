# Node 5.2：决策到实际观测的精确证据审计

审计源码：`1a0e1b52c3cab9acac1ee6092d58d5925b41163f`。本报告是 CPU / 只读审计及待实施方案；未修改 benchmark、reward、Stage、checkpoint、action、harness、state 或 ledger，未运行 GPU。

## 结论与证据状态

最小缺口是一个独立的旁路 collector：保留已有计算产生的完整投影及实际质量值，串接实际 parent / final 身份，再接真实环境执行后的观测。不能用 XY 最近距离代替 provider quality，也不能把未执行候选的未来结果用于部署选择。当前没有支持新增算法候选的充分证据，node 5.2 的下一步是补可验证的观测能力。

重启前已经完成 `torch.load(..., map_location="cpu", weights_only=True)` 的实际 CPU 核查，最终 `torch.cuda.is_initialized()` 为 false：

| 已核查集合 | traces | shadow 批数 | 候选出现次数 | tensor 中找到相同 canonical fingerprint | 同 fingerprint 的已存 reward 值匹配 |
|---|---:|---:|---:|---:|---:|
| 原 fixed-pool 历史输入 | 20 | 220 | 3520 | 3520 | 3520 |
| 本轮失败 attempt 中的 trace | 6 | 66 | 1056 | 1056 | 1056 |
| 合计 | 26 | 266 | 4576 | 4576 | 4576 |

两组所有已存轨迹都是 `torch.bfloat16 [16,7,3]`；没有完整 `[B,9,3]`，没有明确保存的起始 EEF 字段或实际执行后观测字段。动作张量、已有质量张量及指纹可恢复到它们**已保存的原 dtype 精度**；没有恢复出缺失的原始 t0 或 t8Z。

上述扫描原输出位于 `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/evidence-audit/existing-artifact-inventory.json`。扫描输入的历史 manifest 是同一 study 的 `iteration_001_execution_intent/fixed-pool-replay.json`；当前 attempt 输入按 W 的 `data/attempt-ledger.jsonl` 中 `output_dir` 查找，包含另一工作树的授权输出目录。服务器重启一度使 A 挂载不可用，故先将结果保存至本地 W。挂载恢复后已重新读取原 inventory JSON，两组汇总与保存的结果完全一致，SHA256 为 `4e0965194279ceb7fb0755aebe22831f737dad6d3bd93272c31f7eb59af04cc6`。**恢复后未再次加载26个原 tensor，也未重跑266批遍历**；完整逐文件路径/原扫描 SHA 仍保存在该 inventory 内。

历史 manifest 的既有报告已说明 BF16 反算起点不能在 CPU arithmetic 下精确重现全部存储位置。不能用 t7Z 加第八动作得到的近似值冒充原 t8Z；更不能将 BF16 转成 FP64 称为新增精度。本轮失败 trace 不因可读而变成有效科学样本。

## 现有源码到底保存了什么

以下路径相对 W，行号对应上述 HEAD。

1. **全投影存在于运行中，序列化前被切短。** `core/env_adapters/libero_adapter.py:1620` 的 `delta_actions_to_ee_trajectory` 先取得真实 EEF position，按输入 action dtype 建立起点，使用 `0.01` 尺度和 `torch.cumsum`，返回含起点的 `T+1` XYZ。`core/rdt_policy_steer.py:6895` 逐候选调用它并转成 sample dtype。`:1722` 的 EDS reward slice 是 `[:,1:H,:3]`，H=8 时恰为 t1…t7；`:4174`、`:4559` 保存的机制轨迹正是该 reward slice。当前 provider 本来就用这个窗口，本审计不改成 t1…t8。
2. **t8 descriptor 不是 provider quality。** `core/rdt_policy_steer.py:4641` 用完整投影生成 descriptor；`core/qd_ed.py:62` 取最后一点 XY 并减 target XY。`:75` 的 execution-intent descriptor 要求 `[B,9,3]`。`core/rdt_policy_steer.py:4844` shadow stream 已存 descriptor、resolved reward 和动作 fingerprint，`:5772` 记录每轮实际候选。`17/220 XY argmin` 只涉及另一个几何量，不是 quality 排序错误；本次没有重新计算该比例。
3. **实际 provider 返回与决策 quality 要分层记录。** `core/rdt_policy_steer.py:1428` 的 `_counted_reward` 直接调用 provider；`:1733` 的 `_score_particles` 按候选逐个求和，再转到 samples 的 device / dtype。`:1909` 再按既有 reward mode 转换并令 `costs=-rewards`；`:4141` resolved reward 优先取 info，否则为负 cost。旧 trace/stream 能恢复已存的最终 quality，不能恢复未保存的每个 provider 原始返回或其转换前精度。
4. **质量选择已有确切规则。** `core/qd_ed.py:375` 按更高 reward、相等时更小 fingerprint 替换；`:533` 全局选择 key 为 `(-reward, fingerprint, cell)`。`core/rdt_policy_steer.py:6424` 选择 archive 最优，`:6457` 核对最终 latent fingerprint 与 reward。非 archive 路径在 `:6440` 使用 cost argmin。日志须记录实际分支，不能把几何 argmin 或自行改写的 tie-break 当真值。
5. **父代身份只部分直存。** `core/rdt_policy_steer.py:5140` 的实际 allocation 已有 parent actions / rewards / costs / cell IDs / fingerprints / lanes；`:5330` 起还有真实 source population 和 parent indices。`:5455` selection trace 保存 indices、ranks、来源与概率，但 index 的含义依赖当轮 source pool；`:5220` 只直接记录 secondary parent fingerprints。不能仅凭重复 fingerprint 认定同一个候选出现次或精确 parent occurrence。新增日志应直接截已选父代及当时 source pool 身份。
6. **现有 trace 开关不是零额外调用的观测开关。** `core/rdt_policy_steer.py:5048` 与 `:6008` 为部分中间态额外调用 `_eds_score_population_as_cost`；`:4166` 又有 first-chunk 限制。`main.py:1892` 起有 pretest / max-chunks 限制；`core/eds_mechanism_trace.py:95` 才按 save_tensors 写 binary payload。不得通过扩大该机制 trace 开关来实现“零额外 provider 调用”日志；既有冻结配置也不在此方案中改动。
7. **当前保存发生于执行之前。** `main.py:1827`…`:1944` 写 chunk metrics / trace；`:1905` execution_info 只有计划 horizon 等信息。`:2023` 才执行 action；之后没有持久化每步实际 EEF / 目标坐标 / action / reward。`:2031` 的 previous action 只是内存状态，视频叠加图也不能恢复原数值精度。
8. **终止时不能在 main 读取 live controller 当 post-step 状态。** 内层 `core/env_adapters/libero_adapter.py:807` 先取得 raw_obs，`:813` 调用原 success predicate，`:825` 格式化 raw_obs，`:832` 在 terminated 时自动 `self.reset()`，之后才 return。外层 `:1682` 在已有 postprocessor 后把夹爪二值化并转 float32 NumPy，再进入 inner step；`:1699` 缓存返回 observation。因此 main 的 step 返回后再读取 live sim/controller，终止路径可能读到下一初始状态。需要在 inner step 的 auto-reset **之前**冻结原 raw_obs / 当前目标证据，不改变原 reset 时机。
9. **可用的只读状态与禁用旁路。** `libero_adapter.py:1140` 的 EEF getter 复制 controller position；`:1345` 的对象姿态来自 `sim.data.body_xpos/body_xquat` 的 copy。`core/keypoint_tracker.py:146` 用这些当前姿态更新目标，也会在缺 pose 时回退初始值，必须记录 fallback，而非冒充新测量。`libero_adapter.py:1131` 的 `_get_raw_obs` 实际执行零 action step，**绝不可用于日志**。`:146` 的 `_convert_nested_dict` 用 `torch.from_numpy`，未主动升/降精度，但共享内存视图需在 pre-reset 边界 clone，不能留到后续异步写入。

## 最小实现范围：一个 collector，四组窄 hook

后续仅在隔离 executor worktree 实施；当前 W 只新增此证据目录。

- 新增 `core/decision_evidence.py`：无模型、环境或 provider 依赖的 append-only collector，事件 ID、只读快照、tensor bundle 与 JSONL writer。独立观测配置默认关闭；研究启用时 Q0/P2/N1 使用同一条件，不复用 mechanism_pretest 开关。输出只含函数/源码 SHA 引用，不含 prompt、凭据或 raw Stage response。
- `core/rdt_policy_steer.py` 的窄 hook：给实际 scoring call 绑定 decision/batch/candidate occurrence；`_counted_reward` 保存**原函数这一次返回**再原样 return，不重算、不改变求和顺序；`_score_particles` 将现有一次 full-projection 表达式保留局部变量再原 slice，收集完整投影；在现有 shadow-stream、parent allocation、final selection 已有局部变量处截取数值。不得额外调用 model、provider、descriptor、decode 或 projector。辅助 trace 的既有评分若发生，标注 `role=auxiliary_pretest`，不得冒充参与选择的 canonical candidate quality。
- `core/env_adapters/libero_adapter.py` 的窄 hook：在原 projector 已取得 EEF position 时保留原数组副本及实际 cast 后起点；在外层 step 已生成实际 `action_numpy` 时截取该数组；在内层 step 已取得 raw_obs / 原 success 结果后、原 auto-reset 前冻结观测和必要目标姿态。不要调用 `_get_raw_obs`、render、forward、check_success、step、reset 的额外副本。目标姿态只复制既有已注册 object/link 的当前状态；不引入隐藏 evaluator 条件。若原目标跟踪语义无法无歧义复现，标 Unknown / fallback，不重新调用 provider。
- `main.py`：在 chunk 开始绑定 episode / chunk / stage / observation ID；把真实已选 latent、实际返回 action chunk、最终发送 action 串接，后者还需区分 postprocessor 与 binary gripper。先写完整 decision，再在每个 step 的 pre-reset snapshot 返回后 append execution outcome。next-chunk 当前 keypoints 的**原有**读取与这组结果关联。Stage 切换是 context 边界，不是 episode reset；terminal snapshot 归属旧 episode，reset 事件单独归新状态。

任何 `.cpu()` / clone / 文件写入都有成本，CUDA tensor 拷贝也可能引入同步；不能声称 wall time、异步调度或 GPU 行为严格零影响。尽量复用已有 CPU 快照和同步点，单独记 observer 时间/字节，不新增显式 CUDA synchronize。CPU 等价验证之后仍需在相同冻结观测条件下通过实际 runtime gate，才可用于合法在线评测。

## 最小数据结构与精度契约

建议 `decision_events.jsonl` 存小型索引；`decision_<id>.pt` 存 CPU tensors / 基本类型，读取仅 `weights_only=True`。binary tensor 的 dtype / shape / 字节摘要为精度依据，JSON 展示数字不是提升精度的方法。模型 BF16 就标 BF16；原 NumPy EEF / raw observation 按实际 dtype 保存，不假定一定为 FP64。canonical action fingerprint 沿用 `core/qd_ed.py:43` 的 float32 little-endian 全 latent 字节；另存 native dtype payload hash，两个 hash 不混用。

1. `context`: `attempt_id, episode_id, reset_id, decision_id, chunk_start_step, current_stage, use_guidance, observation_id, provider_bundle_sha256, provider_function_order, reward_mode, model_dtype, horizon, projection_semantics/source_sha`。冻结 keypoints 数组和目标索引；不读取未来记录。
2. `candidate_batch`: `batch_id, role, iter_idx, source_pool_id, occurrence_ids[B], canonical_fingerprints[B], native_latents[B,64,128], decoded_actions[B,8,7]（仅已有解码结果）, source_eef_position, cast_eef_start[B,3], projected_xyz[B,9,3], provider_input_xyz[B,7,3], provider_call_ids[B,K], provider_returns（保留各自实际dtype）, aggregate_before_reward_mode[B], effective_quality[B], cost[B], descriptor, bounds/cell_snapshot_id`。若某路径没有已计算的解码或 descriptor，标未观测，不额外计算来填齐。
3. `parent_allocation`: `iter_idx, source_pool_id, selected_source_occurrence_ids[16], selected_fingerprints[16], source_indices[16], cell_ids[16], lane[16], original_selection_probability/weight`。重复抽到同父代保留重复 slot；不按 fingerprint 去重。
4. `decision_committed`: `selected_occurrence_id, selected_fingerprint, selected_quality, selected_cost, selected_cell, selection_rule, action_chunk_payload_id, execution_horizon, last_available_observation_id`。QD 场景断言等于真实 archive global-best；其它场景使用原实际分支。提前终止不补虚拟 action。
5. `action_dispatch` / `step_outcome`: `decision_id, execution_index(1…8), env_step_before/after, selected_fingerprint, actual_action_numpy[7], pre_reset_observation_id, raw_eef_position/quaternion, gripper_state, task_target_pose_or_registered_keypoint_state, env_reward, terminated, truncated, original_info_success, original_success_predicate_called=true, terminal_reset_follows, observation_origin="actual_env_step"`。pending dispatch 没有 outcome 就保持未完成，不能捏造 failure/zero reward。
6. `next_decision_link` / `boundary`: 标记 `stage_change / episode_terminal / automatic_reset / external_abort`；关联下一次合法原有 observation / keypoint 读取。可离线计算 t1…t8 实际位移、对固定起点 target 的距离变化、对当前 target 的距离变化及投影误差，两种 target 基准分别命名。它们是执行后诊断，不是本决策的质量输入。

起始 EEF + projected t1…t8 是**当前观测的运动学代理**；step_outcome t1…t8 是**唯一真实执行路径**。未选候选没有真实结果。terminal、异常或 stage reset 发生时实际前缀可能少于 8，使用 `observed_prefix_length` 和显式边界；不填满到 8，不跨 reset 拼轨迹。

## 有意义的 CPU 回归验收

下列是后续实现必须运行的测试设计，本报告没有把“计划测试”写成已通过。

1. 用实际 RDT stub/CPU 路径比较 observer off/on：provider/model/projector/Stage/render/step/reset 调用计数及顺序、RNG state、输出 action、selection fingerprints、父代 slots 必须一致；制造 provider 有状态计数器，使任何重算都会失败。保持既有 trace 配置不变。
2. BF16 原样 round-trip：构造第八个 delta 与第七个显著不同的输入，实际 full projection `[B,9,3]` 与原 provider slice `[B,7,3]` 都逐 bit 匹配；不从 t7 反算 t8，不把 BF16→FP64 当精度恢复；snapshot 后修改 source tensor 不得改变已冻结证据。
3. 真实 provider 返回：多 provider、不同返回 dtype、正负值及 reward-mode 测试；原调用仅一次、原返回/求和/转换保持，单独保存 raw return 与 effective quality。构造 XY 最近候选 reward 较差，最终仍服从 provider rule；再覆盖 exact reward tie 的原 fingerprint/cell 规则。
4. 真实 lineage：同 fingerprint 的不同出现次、多次抽到同父代、archive rebin 和 population reorder；验证每个 parent slot 能映射当时 source pool，并最终 selected fingerprint 与实际执行 latent 相同，不能用后来的 pool index 解释旧 index。
5. 真实动作边界：外层既有 postprocessor 改值、raw gripper 为负/零/正时，记录的 action_numpy 逐 bit 等于传给 inner step 的参数；保持零→-1 语义、horizon、action 顺序与环境调用数。
6. terminal auto-reset：CPU fake inner env 令 terminal EEF=A，reset EEF=B；运行实际 inner `step`，证据必须是 A，原 reset 次数仍 1，下一 episode 才能引用 B。提前终止只存真实前缀，不能出现 t8 或成功状态插值。
7. 时间因果：同一 observation/state/RNG 下任意修改之后才追加的 outcomes，已提交 decision hash、所选 action 与排序不变；部署选择函数不持有 outcome-store 读取接口。stage change 清理关联上下文，episode reset 清理所有 parent/decision 活跃状态。
8. 写入失败/原异常：partial bundle / JSONL 截断明确标 telemetry incomplete；不重复 provider、动作或环境步骤，不覆盖原异常、不补缺字段为0。恢复读取只接受完整 bundle 的 hash 与 commit 引用，不把半记录当真实观测。

## 原 artifact 可补回与仍未知的界限

可恢复：已保存候选 latent、原 dtype quality/cost、t1…t7 reward-input 轨迹、已存 t8XY descriptor、gripper 动作数据、exact canonical fingerprints、已有 selection indices / 部分 parent 信息。可以按显式规则复核已有 provider quality 的排序和最终指纹，不需要再运行 provider。

不能声称已恢复：原始真实 EEF、原 t8Z/full projection、每函数未保存 raw return、完整不可歧义的 parent occurrence、实际发送动作与 selected latent 的全链、执行后真实进展、对未选候选的未来结果。旧视频/rounded metadata/近似重建不填补这些空缺。

下一步是按上述边界在独立 executor worktree 加旁路 collector 并运行 CPU 回归，再由 root 在 GPU3 唯一授权资源上决定运行准入；本报告不启动调度，也不结束整体 autoresearch。inventory 已完成挂载恢复后回读，未来执行所需输入 hash 仍按新冻结协议验证。
