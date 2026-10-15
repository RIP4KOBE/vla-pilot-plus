# N30 first-active lineage：禁用的后续 CPU 诊断协议

**executable=false；本文件不授权任何 payload 读取。** 必须由 root 独立审阅本次 Phase A、冻结实际执行代码和资源边界，再发新的精确 release。当前 578/100 研究预算与保护阶段不变，无算法/模型/API/GPU/仿真或新实验。

## 固定样本与完整容器边界

全部两个已接受 N30 格（task0 `4300bcf89485`、task1 `1e52b07e1725`），均按完整 metrics 中最早 active 选取 step8、`e0:d2:s8`；不得按后代、成功、距离或评分改变选样。`input-bindings.disabled.v1.json` 精确列34文件、24,273,690 stat字节，每文件至多一次读入、一次 `torch.load(BytesIO(bytes), weights_only=True, map_location="cpu")`。读取同次计算 SHA，必须等于由已验证 index/receipt 复制的 SHA；现阶段这些不是新测 payload 哈希。

每格包含 bundle_000026.pt（整个决策，约12.09 MB），以及八个 executed_action 和八个 outcome/ack 小容器。**weights_only 仍会反序列化整个容器，不是只读下列 tensor 字节。** 两个大容器分别另含2496 projection_origin、16 scoring_inputs、256 provider_return、16 scoring_aggregate、16 effective_quality 共存事件。允许未来完整容器解码必须写进 release；这些事件及下列白名单事件中的 cost/quality/reward/success/描述几何等非目标字段不分析、不导出。索引事件名中没有 Stage 正文、图像或视频事件；这只是记录器/source 与 index 类别检查，不是已检查序列化字节。

拟议资源（尚未释放）：2 CPU affinity/线程，单进程累计 CPU 120秒、wall 120秒含启动退出；Torch导入前 RLIMIT_AS=16GiB。原始读取硬限24,273,690 bytes、34 containers，不自动增额；ZIP全部成员未压缩总额及去重 CPU tensor storages 分别<=128MiB。任一文件、身份、shape、SHA或限额错误即保留错误与已读清单停止，无自动重试或扩大数据。CUDA隐藏、不得创建CUDA张量/初始化设备；Torch依赖若需额外路径，由新release明确，不能把本phase的stdlib guard当成已验证Torch启动环境。

## 允许分析/导出的字段

事件外壳限 sequence/event/episode/decision_id/global_step/reset_sequence，必须匹配冻结 index。

- decision_context / n30_observation_context：stage/use_guidance、tracker/provider的身份哈希与编号、已有原始EEF与目标快照/目标索引；不读取或导出provider源码/回答。身份缺失或冲突保持Unknown。
- n30_initial_proposal：progress_state的active/reason/previous_start_step、current_context的身份/start/target、previous_native_plan与其identity、fresh_native_population、fresh_tail、inserted_row、action_mask。只作native内容/来源与56+8组合核对，不重新计算进展门或奖励。expected source shapes是16×64×128 fresh、1×64×128 previous、64×128 inserted、8×128 tail、1×1×128 mask，实际dtype/shape未来逐项记录。
- canonical_candidate_batch / canonical_candidate_identity：iter_idx、candidates、occurrence_ids、canonical_fingerprints/fingerprints。限11批、176行；不分析effective_quality/rewards/descriptors。
- archive_parent_allocation / parent_allocation：iter_idx、已记录fingerprints/lanes/cell IDs/索引、source_population、source_pool_id、parent_source_occurrence_ids、elite_count、offspring_sources、original_archive_occurrences/identity_scope。限10轮、每轮16实际父代槽。**原archive插入发生的occurrence未保存，不重建排名/quality或伪造插入日志。**
- final_selection / n30_selected_native_plan：population、selected_latent/native_plan、selected_index/fingerprint/cell、selected native identity 与目标/起始快照。native (1,64,128) 内容先核对，policy_action_decode的FP32表示与native dtype必须区别。
- policy_action_decode / n30_decode_binding / n30_commit_binding / decision_committed：selected_latent、action_chunk/actions、execution_horizon、step、committed，只核对既有converter表示和commit前8动作。不能另选动作。
- 八次 executed_action / pre_reset_outcome / n30_actual_ack / step_returned：实际command、已有EEF位置/姿态及gripper qpos/qvel、执行索引与关联native identity；terminated/truncated仅控制reset/关联边界，不当效果特征；不分析reward/success。只描述steps8..15的已执行响应。

## 四类链路结论与间接耦合

1. **direct identity**：完整native row的dtype、shape、bytes一致；fingerprint仅是定位线索。不同occurrence即使内容相同也不自动等同祖先。
2. **unique genealogical ancestry**：实际parent_pool槽/parent_indices到同轮offspring行的source调度绑定可核对；从先前canonical到archive pool的原始occurrence没有记录。只有先前合法候选集合中内容/指纹匹配唯一且时序/cell/槽一致，才报告“唯一内容支持的谱系推断”，明确依赖完整候选集合及原worker来源审计；不能声称已观察未记录的archive插入因果事件。
3. **ambiguous**：多个同内容/同指纹来源或后代竞争，保留集合/数量而不择一归因；**missing/unknown**：字段/唯一关联不足，不解释为丢弃。进入canonical不等于曾占archive槽，进入actual parent与final archive才分别证明那些已记录快照的成员关系。
4. **indirect population coupling remains unexcluded**：QD bounds/occupancy/sparse allocation 与 ED RBF 可经整批耦合影响其它候选。无直接/单亲后代链只能报告 direct ancestry 未确认，不能说插入对最终动作零影响、机制无效或反事实不插入会一样。禁止反事实模型/评分/RNG回放。

该诊断仅两个 first-active 检查点，不能代表18次插入或完整episode“从未存活”。记录首轮/各轮身份匹配与最终选择，不设结果后阈值、不筛有利任务、不以质量重排。

## 实际反馈与仍依赖的证据

steps8..15用 step8 时已记录 current_context / selected.target_snapshot 作为**固定行动前快照**，与当前chunk start及八次真实命令/反馈相连。原source已显示这些字段；数值尚未读。它不是连续目标GT，距离变化不是接触/抓取/成功。

触发本次插入的 steps0..7 严格进展门、此前snapshot0和native winner来源继续依赖已绑定同进程原生审计；当前34文件可核对已复制的 previous_native_plan 内容，但不独立重新计算旧进展门。若审查目标改为独立重算该旧门，需另冻上一decision及其8步反馈范围，不偷偷扩大本集合。无需为本次lineage问题增加旧tensor读取。

第一阶段只证实元数据可定位与哈希/身份一致性；不证明payload数值正确。原native算术、context真实性及原始完整审计均明确继承root-bound receipt/audit attestation。本诊断不重跑原native audit或provider，不产生接受科学结果/修改历史状态的权限。
