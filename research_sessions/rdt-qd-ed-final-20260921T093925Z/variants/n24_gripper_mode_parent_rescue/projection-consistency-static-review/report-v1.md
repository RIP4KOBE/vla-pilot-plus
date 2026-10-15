# N24 projection consistency 静态复核

结论：N23/N24 的 effective quality 使用内部 clipped translation 投影，而 N5 终轮 eligibility 接收 descriptor 路径取得的原始投影；数据流确实分离。这与N23“只改quality、保留descriptor/selector”的既定设计相符。该差异本身不构成已证实的执行bug，也不能直接解释step304、408为何不合格。

## 精确数据流

1. `rdt_policy_steer.py:2066-2094` 的 `_eds_score_population_as_cost` 先调用原 `_score_particles`，保留raw provider rewards和已评分actions。原投影及其source_origins传入 `ActuatorClippedContract.score`。`qd_actuator_clipped_quality.py:118-125` 仅返回quality和changed mask，不返回或替换projection。
2. `qd_actuator_clipped_quality.py:132-159` 接收8步translation及9点投影。先检查原生dtype/device，并要求captured origin等于原投影第0点、raw `origin+cumsum(delta*0.01)` 与原投影t1..8逐位一致。只有前7步存在超出[-1,1]的translation时，才内部计算clipped增量；质量只用t1..7，权重[1,1,1,1,3,3,3]归一化。前7步无变化时直接保留raw；第8步越界单独出现不会改变该quality。
3. `rdt_policy_steer.py:6276-6279` 在canonical iter9调用 `describe_qd(population, projection_out=...)`。该闭包在:4982-4990转入 `_eds_qd_descriptor`；:4844-4851再次调用 `_rdt_sample_to_trajectory_3d`，把所得原投影复制到 `terminal_projected_xyz`。:7604-7626经原adapter接口取得轨迹，未在此路径加入N23clamp，未消费quality内部xyz。
4. `rdt_policy_steer.py:6335-6346` 固定同一终轮canonical actions/costs/raw关联；:6994-7004将这批actions、上述投影、同一keypoints和识别target传给 `select_grasp_timing`。`qd_grasp_timing.py:61-75` 消费t1..8，在原eligible集合中选择native minimum cost；空集回到native argmin。

## 两种度量的边界

| 项目 | N23/N24 effective quality | N5 eligibility |
|---|---|---|
| 几何来源 | 内部componentwise clamp[-1,1]、0.01 cumulative projection | descriptor调用原adapter得到的投影 |
| 使用点 | t1..t7，不含原点/t8 | t1..t8，不含原点 |
| 判据 | 加权负平方距离；没有gripper eligibility门 | 存在一个正命令t，同时distance<=0.06m且<=全16×8最小distance+0.03m |
| 数值路线 | origin/translation/keypoint/raw同native dtype；native norm和square，乘FP32归一化weights后归约再cast raw dtype | 原生projection/keypoint先detach.float()到FP32，再差分和vector_norm |
| 输出/用途 | quality及changed mask；后续cost/归档/父代分配等消费quality | 原eligible indices与selected index；不替换quality |

因此“全8步正命令”不是原N5的充分条件。相对门槛依赖整个16×8池，改变任何行的几何也可能改变其他行是否合格，不能只局部重算某个full8行或只检查绝对6cm。clip更接近/更远都没有静态保证。

## origin、context与N24继承关系

quality入口在每次评分前后验证provider和controller/reset静态上下文（`qd_actuator_clipped_quality.py:100-115`）；同次quality原点与raw轨迹有精确一致性检查（:145-154）。context中含adapter/wrapper/environment/controller身份、局部task/episode和reset generation。未读取实际环境、provider源码或物理状态。
评分调用通过 `capture_origin=True` 保存source origin；稍后的descriptor调用没有传origin_out，属于一次独立原adapter投影。此次允许的5个源码未显式比较这两次调用的origin，因此不能将“同一逻辑search/context”夸大成已证明两次原点逐位一致。adapter实现不在scope内，不补读它。
N24仍要求ACTUATOR_CLIPPED_MODE，父代rescue仅在同search内替换既有候选，保留原descriptor和上述selector流（`rdt_policy_steer.py:5153-5175,6335-6346,8310-8319`；`qd_gripper_parent_rescue.py`及其独立audit核验缓存与实际父代）。它没有把quality内clipped几何转送N5。raw Stage binding仍在 `rdt_policy_steer.py:7500-7509` 单独使用选中raw reward和原archive spread关联，不将effective quality冒充raw provider输出。

## 对已闭合两例可以说什么

允许引用的closed membership conclusion及root review表明：step304、408各有一个终轮full8候选，但原eligible_indices均为空，实际选择等于原native argmin。它们只确认“没有通过原门”，没有提供本次可分析的几何或逐子条件证据。
静态分离与上述空集同时存在，不等于clipping会使这些候选合格，更不等于合格或选中之后能抓住物体。不能直接称之为bug、门槛错误或这两例的失败原因。改变N5输入投影将构成另一个单独声明的科学干预；当前N24保持冻结。

## 唯一最小可证伪后续问题（未执行）

对同一已暴露task0的全部14个终轮16行池，固定原记录canonical动作、origin、target、binary gripper以及6cm/3cm规则，仅把N5几何由raw投影替换为明确规定的componentwise[-1,1]、0.01累计到t8的假设投影，full8∩eligible的成员是否发生变化？

若未来单独冻结此诊断，应包含全部14池，报告双向变化及原5个已选full8/7个无full8的结果，不只挑两例；重算相对门须覆盖全部16×8点。t8延伸是新的假设，不是已经记录的native clipped selector投影。原点/布局/dtype/GPU算术无法精确绑定时必须Unknown，不用经验容差冒充证明。本静态任务没有授权读取相关payload、执行这项诊断、重排/评估或实现任何候选。

## 输入范围与哈希

口头任务称6源码，冻结scope实际列5源码+2闭合文档；本次严格只读这7份文件。全部哈希复核一致；未追随闭合审查中的其他artifact引用。无新增payload、.pt、metrics、环境/凭据读取，无runtime import、test、GPU/API/model/simulator或算法/状态/预算变更。所有输出仅本目录。

| 文件 | SHA256 |
|---|---|
| qd_actuator_clipped_quality.py | `14f43ab89b7e59c99ada6f66a832f3a3f08d60c4fb1c92c0c8a6bb27a57ef120` |
| qd_grasp_timing.py | `f38c980b22df080991e4cb86d07c1dbc933652e584e8b897dbb16e1312fd6142` |
| rdt_policy_steer.py | `aa91f6a0ce6a532c724fed559a93a08545241924028f621fe73101ee3bed3ea8` |
| qd_gripper_parent_rescue.py | `95e58de7f33a3f365f3d7640206f9f040b821d1bcd3d44aea008dd3236a25e3f` |
| audit_gripper_parent_rescue.py | `546ed6c7579b70fa6e99fb1525f144fb500b57ea9e3694af517434769f09ab68` |
| conclusion-v1.md | `4edc01fe2a2ed488e85a987817706f615d08e68db4110ca238f19916fee655ce` |
| root-review-v1.json | `434e7608346dd81603400dd9bce4ea9429956348804dce9ab9342848048113cd` |

完整绝对路径、行号证据映射及可证伪问题保存于 `static-result-v1.json`；输出哈希见 `output-manifest-v1.json`。静态复核已闭合，后续保持待命。
