# Frozen t00 C0 observation: first complete episode

原任务独立结果：execution outcome=completed；root 报告 success=false。证据中720个实际step均未报告success，最后step719为truncated=true、success=false。任务完成记录不等于任务成功。

完整性：已有审计accepted=true、evidence_complete=true、errors=[]；冻结分析器复审通过。共90次decision、720个连续真实pre-reset outcomes；每个实际prefix均长8。29次guided，61次unguided。CUDA未初始化。输出为本目录selected-decision-analysis.json，解释汇总为interpretation-summary.json。没有改冻结代码、定义、阈值、map、账本或原episode。

## 严格目标身份结果

**0/29条guided与冻结map-v2精确匹配，因此A/B均为Unknown。** 冻结strata中显示的0 witnesses对应0 eligible；不能解释为零发生率或反证。全部29条有相同original/source/path三元组，source_text与path均29/29匹配，只有original_code SHA与静态候选不符：

- Recorded original_code_sha256：a6efff2bb46ca4038d30b63cbcdf340a126b10efeffa0830288ba0879b8484fa。
- Frozen map期望：64bfc5d573100a463facb1849937b4fbd895070028584e2f0d8d3d3aa21dcfe6。
- Recorded source_text_sha256：d374557f569b8c69f898a1596dfefd32a21774929511bb969d5d27e0050d4830。
- Recorded source_path：/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/guidance/task_0/stage1_guidance.txt。
- original_identity_origin=loader_attached_original；source_text_origin=loader_attached_text。

同一source下wrapper SHA有两个值：38a837e02ebb206c1740d92b01333eef42562bb504773c9decd6d9ca1ef00dbd（8条）与a2fe62d2c5bf3be97da9ac173de6c4446c29f9faea0742e2dbe810fbceffdf74（21条）。保留原分组，不把它们解释为不同奖励语义。没有记录normalized structural code SHA或co_code/co_flags/co_consts明细；这些字段为Unknown，不能从SHA反推。差异原因交由独立CPU provenance审查，本报告不做源身份修复或替代归因。

## 可独立计算的连续诊断

下表限29条guided、选中投影与真实已执行8步。原生EEF为float64，记录投影为bfloat16。数值描述追踪偏差，不证明奖励误选、物理接触原因或未执行候选会更好。

| 量 | 中位数 | 范围 |
|---|---:|---:|
| EEF投影RMSE | 0.0364834 m | 0.0066073–0.1823367 m |
| 第8步端点投影误差 | 0.0634094 m | 0.0108905–0.2464260 m |
| 投影运动响应gain | 0.482507 | 0.057196–1.092144 |
| t0来源cast误差 | 0.0004477 m | 0.0000809–0.0010560 m |
| 记录端点精度screen | 0.0011960 m | 0.0005980–0.0021973 m |

29条端点误差均超过其既定存储精度screen；这仍不是物理噪声置信界或因果诊断。缺精确目标身份使d/P/optimism以及step7→8目标距离变化均保持Unknown，不能据上述误差把B判为支持。

## Guidance / stage 与夹爪观察

| Stage | Guidance | Decisions | 真实steps | 投影诊断 |
|---|---|---:|---:|---|
| 1 | on | 29 | 232 | 29条可算EEF误差；目标均Unknown |
| 1 | off | 21 | 168 | 无canonical guided projection / provider，Unknown |
| 2 | off | 40 | 320 | 无canonical guided projection / provider，Unknown |

冻结原始wrapper分层的RMSE中位数为0.0512462 m（8条）和0.0364834 m（21条），完整四个原始strata保留在JSON中；上表仅按实际stage/guidance描述，不赋予wrapper差异语义。

29条guided的真实后处理命令prefix为13条全负、7条全正、9条混合；其中第7→8步命令sign改变2条。第7→8步gripper qpos变化L2中位数0.000275573，范围0.000030968–0.00693848（原记录qpos单位）。命令正负和关节运动均不证明抓取；物体实时位姿、接触、抓取成功以及未执行候选的反馈Unknown。

这是observer=true的单条C0；不与之前observer=false C0、外部GPU2 Q0/C0或尚未完成的其他row作配对性能结论。保留该冻结结果；任何后续身份工程解释必须另存并标记post-data，不覆盖本目录。
