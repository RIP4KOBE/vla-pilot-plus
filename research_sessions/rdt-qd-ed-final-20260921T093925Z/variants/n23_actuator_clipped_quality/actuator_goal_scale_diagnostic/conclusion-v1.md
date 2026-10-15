# N23 实际控制器缩放边界与两种固定增量公式

**实际记录的控制器平移输出边界确实是 ±0.05，而 N23 内部仍使用 0.01；但是 0.05 的 affine scaled_delta 不能直接当作实际末端位移。** 两个预先限定公式与同一执行记录比较时，A=0.01 的残差更小。这既不证明0.01是最优参数，也不支持仅凭控制器边界就将N23改为0.05并宣称修复。

共2876个已知起点的单步：A/B平均欧氏残差分别 **4.340 / 28.424 mm**；356个已知起点的八步总量：分别 **29.863 / 215.318 mm**。这些都是描述性残差，没有新的quality、候选排序、控制器动作、参数拟合或成功率推断。

## 输入和实际参数核验

独立scope SHA256 `b2802ce980098453df6a75bc9e426ac1443bae9c8749cb5067ecaee128f94134`；冻结read manifest SHA256 `82848e3bf21292449f05d3648887084ecb249eab3c94503184069de89cc954d3`。新实际输入只有四个明确已完成attempt的 `eds_metrics.jsonl`，只读取其中 qd_actuator_metadata 与global_step/episode身份字段。动作和EEF完全来自已闭合proprioception结果 SHA256 `d658ea7ab4a053a69b019dfa39d20035948e8c5d3af75ce1896f0d325e96f02a`，没有新tensor bundle、额外任务或运行中输入。

139条实际metadata（按task为15/54/68/2）均记录：

- class=`robosuite.controllers.osc.OperationalSpaceController`，name=`OSC_POSE`，fixed impedance、delta=true、orientation=true、control_dim=6。
- 六维input min/max为−1/+1；output前三维为−0.05/+0.05，后三维为−0.5/+0.5；记录bounds dtype均float64。
- 每个attempt内pid/adapter/wrapper/environment/controller/episode/inner-reset的完整context恒定；set_goal/scale_action的qualname、实际source path和完整文件SHA与本次静态文件逐一一致。

| benchmark task | guided快照数 | 无边界快照的unguided块 | 实际local task_index | 实际episode_index | inner_reset_generation |
|---:|---:|---:|---:|---:|---:|
| 0 | 15 | 75 | 0 | 0 | 0 |
| 1 | 54 | 36 | 0 | 0 | 0 |
| 2 | 68 | 22 | 0 | 0 | 0 |
| 3 | 2 | 88 | 0 | 0 | 0 |

全部实际context原值（含process/controller实例）在JSON保留。`task_index`是filtered environment列表中的局部索引，不能等同benchmark task ID；四个隔离attempt局部索引均0。全局task绑定使用事前明确的四attempt manifest、相同已闭合native/proprioception引用，未拿局部0冒充全局task证明。root已另行审查原40格task-major计划；本执行器没有新增读取该计划。

**覆盖边界：**139个guided边界有当时的static metadata快照；其余221个unguided边界无逐步快照。B用于unguided样本时，只是明确沿用该attempt一致bounds的假设性重建，并非每个unguided动作的live controller参数都被本次核验。guided边界的static快照也不是每个物理substep的最终目标记录。

## 静态源码所能证明的语义

`core/qd_actuator_clipped_quality.py` 的内部几何为 `origin+cumsum(clip(translations,-1,1)*.01)`；原 `libero_adapter.py` projector也使用 `ACTION_SCALE_POS=0.01`。decoder只抽取指定7维并二值化夹爪，平移量由记录的executed_action给出。环境wrapper从 installed OSC_POSE config加载控制器，但本结论**没有仅凭默认文件认定实际bounds**，而是由上述139条实际实例metadata确认。

已绑定的 `Controller.scale_action` 对input做componentwise clip，再按bounds midpoint/range作affine变换。fixed/delta模式的 `OperationalSpaceController.set_goal` 调用它；之后将scaled_delta[:3]与更新后的 `self.ee_pos` 交给 `set_goal_position(...position_limit=self.position_limits,set_pos=...)`。

因此B严格定义为 **实际记录bounds确定的 affine scaled_delta（位置限幅之前）**。live position_limits、cached action_scale/input/output transforms、最终goal_pos及控制器内部substep未记录，全部保留 Unknown。默认config的null不能代替live position_limits证据，源码有缓存计算也不等于本次记录了缓存内容。B是从bounds重建的变换表达式，不宣称位级重现缓存计算或观测到了最后goal。

每步set_goal使用当时控制器EEF参考，而不是保证将上一目标完整实现。把8个目标增量相加也不等于控制器实际执行了一个由起点出发的八步积分轨迹。记录的pre/poststep EEF是观察量，本次没有新增记录控制器内部每次update的精确origin。

## 两个唯一比较公式

对每个记录的executed xyz action，预先限定：

`A = 0.01 × clip(action_xyz, −1, 1)`

`B = (clip(action_xyz, input_min, input_max) − midpoint_input) × |output_range|/|input_range| + midpoint_output`

本次实际bounds使B数学上化为 `0.05×clip(action_xyz,−1,1)`。没有第三个scale，没有最小二乘或阈值拟合。所有计算使用CPU Python FP64保存值描述公式，**不是native GPU BF16 projection/quality/排名复现**。

残差符号统一为“公式增量 − 观察EEF位移”。单步观察为同reset连续两次poststep之差；八步观察为块开始前的记录到第八步后记录的差，预测量为该块8个固定公式增量之和。4个episode首步起点缺失，单步2876/2880 known；4个首块起点缺失，八步356/360 known。Unknown样本保持分母，不填0。

所有表的残差单位为 **mm**。median为普通中位数；p90使用排序后位置 `(n−1)×0.9` 的线性插值。signed mean xyz与欧氏残差是不同统计，前者可以方向抵消。

## 单步：按task和总体

| task | known / total（Unknown） | A signed mean xyz | A mean / median / p90 | B signed mean xyz | B mean / median / p90 |
|---|---|---|---|---|---|
| all | 2876 / 2880（4） | [0.1403, 0.6842, -2.3526] | 4.3398 / 2.1774 / 12.0664 | [1.7510, 4.5704, -11.9120] | 28.4237 / 22.6610 / 64.4872 |
| 0 | 719 / 720（1） | [-0.2707, -0.0296, -0.5213] | 2.5024 / 1.8541 / 5.9756 | [-0.8900, 1.3041, -2.6037] | 22.6942 / 20.0803 / 55.7007 |
| 1 | 719 / 720（1） | [-1.0313, 1.1037, -2.3937] | 4.9022 / 3.1785 / 11.7351 | [-5.2276, 5.9527, -12.6216] | 35.7109 / 34.8250 / 64.4039 |
| 2 | 719 / 720（1） | [1.9585, 1.8160, -6.3436] | 9.2010 / 9.8109 / 15.4328 | [12.2638, 9.9893, -32.5031] | 48.8346 / 52.7864 / 75.0556 |
| 3 | 719 / 720（1） | [-0.0952, -0.1532, -0.1520] | 0.7535 / 0.3850 / 2.0286 | [0.8580, 1.0357, 0.0802] | 6.4550 / 3.0071 / 18.0374 |

## 八步总量：按task和总体

| task | known / total（Unknown） | A signed mean xyz | A mean / median / p90 | B signed mean xyz | B mean / median / p90 |
|---|---|---|---|---|---|
| all | 356 / 360（4） | [1.1597, 5.6475, -19.2689] | 29.8630 / 15.2023 / 83.5787 | [13.0052, 35.2038, -93.8610] | 215.3182 / 164.6801 / 469.5392 |
| 0 | 89 / 90（1） | [-2.2148, -0.0520, -4.3770] | 14.7302 / 13.1415 / 29.1813 | [-6.0404, 7.5767, -18.0571] | 167.7122 / 152.2876 / 407.2495 |
| 1 | 89 / 90（1） | [-8.2889, 9.1308, -19.7076] | 32.8599 / 21.4130 / 75.5818 | [-45.3360, 45.2424, -100.0693] | 267.4751 / 299.0028 / 440.7299 |
| 2 | 89 / 90（1） | [15.9036, 14.6131, -51.5863] | 67.1049 / 77.9349 / 109.9270 | [96.0101, 81.5840, -260.7584] | 379.4028 / 411.3840 / 549.2468 |
| 3 | 89 / 90（1） | [-0.7611, -1.1019, -1.4046] | 4.7569 / 2.6441 / 10.9043 | [7.3872, 6.4122, 3.4406] | 46.6828 / 24.0429 / 112.3773 |

## 全部样本的guided与夹爪分组

guided分组使用已记录当次decision标记。单步gripper组按该实际动作符号；八步按0、1..7、8个正向命令分成全非正向、mixed、全正向。这些与运动量或成功无关，不拟合阈值。两个维度是分别分组，不能把行数相加当独立样本；完整per-task和guided×gripper交叉表在CSV/JSON保存。

| 观察单位 | 分组 | known / total（Unknown） | A signed mean xyz | A mean / median / p90 | B signed mean xyz | B mean / median / p90 |
|---|---|---|---|---|---|---|
| one_step | guidance:guided | 1108 / 1112（4） | [0.6514, 1.9374, -5.4939] | 9.0978 / 9.2648 / 14.6673 | [2.5083, 9.7117, -33.4219] | 54.6406 / 55.3634 / 73.1434 |
| one_step | guidance:unguided | 1768 / 1768（0） | [-0.1800, -0.1011, -0.3841] | 1.3579 / 0.8944 / 2.8575 | [1.2765, 1.3484, 1.5681] | 11.9936 / 7.9494 / 30.2018 |
| one_step | commanded_gripper:nonpositive | 1972 / 1976（4） | [0.3110, 0.7313, -1.7858] | 3.5347 / 1.1598 / 11.3789 | [3.5593, 2.2327, -10.6217] | 23.4684 / 11.9340 / 61.9273 |
| one_step | commanded_gripper:positive | 904 / 904（0） | [-0.2320, 0.5814, -3.5891] | 6.0959 / 3.7665 / 13.0817 | [-2.1935, 9.6701, -14.7268] | 39.2332 / 33.8265 / 68.6673 |
| eight_steps | guidance:guided | 135 / 139（4） | [5.4149, 16.2172, -45.7829] | 64.3684 / 68.3121 / 102.4945 | [17.5781, 75.1746, -268.0519] | 420.5803 / 416.0710 / 531.4615 |
| eight_steps | guidance:unguided | 221 / 221（0） | [-1.4396, -0.8091, -3.0725] | 8.7850 / 5.3737 / 19.2974 | [10.2118, 10.7873, 12.5451] | 89.9319 / 54.4054 / 230.0035 |
| eight_steps | commanded_gripper:all_nonpositive | 207 / 211（4） | [2.6173, 4.2984, -11.8961] | 20.6955 / 4.9308 / 79.6823 | [29.7452, 10.0189, -70.0533] | 157.7879 / 53.1190 / 447.4633 |
| eight_steps | commanded_gripper:all_positive | 75 / 75（0） | [-0.5613, 2.0114, -23.5196] | 35.7647 / 19.4979 / 86.2739 | [-15.4489, 98.3974, -71.4257] | 286.2684 / 248.7538 / 480.5214 |
| eight_steps | commanded_gripper:mixed | 74 / 74（0） | [-1.1734, 13.1066, -35.5847] | 49.5255 / 49.8604 / 94.6935 | [-4.9827, 41.6060, -183.1967] | 304.3387 / 355.8214 / 499.8688 |

没有选择更有利的任务或只展示guided：每任务、总体、guided/unguided、命令组、交叉组都已保存，包括空交叉组与Unknown分母。注意unguided B的额外静态参数沿用假设；不得将其描述为当步live目标观测。

## 解释边界

实际bounds证明“内部0.01”与“由实际bounds重建的0.05目标增量”不是同一量，但目标语义匹配并不保证短时真实运动匹配。阻抗控制、姿态耦合、状态更新、可能的接触及跟踪动态都可能使目标增量之和偏离实际轨迹；本次没有读取接触、奖励、成功或物体真值来区分原因。

A残差更小也不能把0.01解释成已找到最佳动力学参数或成功率最优proxy。只比较两个事前指定公式，其他scale未测试；误差衡量不是研究目标的替代品。本记录不支持直接修改N23为0.05、重排候选，或从任一残差推断任务收益。任何后继候选尚未实现或放行。

## 两次工程提取失败与最终关闭

范围原允许最多2次工程重跑，本次已用完：

1. v1在额外的compound identity谓词失败。它错误地要求`episode_index==0`且`local task_index==benchmark ordinal`。v1日志没打印context，实际触发的子条件单靠该日志为 **Unknown**；最初关于episode索引的解释是源码层面推测，不能记为观察到非零episode。
2. v2只移除无依据的episode==0限制并打印context，再因局部/全局task等同假设失败；实际打印`episode_index=0, task_index=0`。允许源码清楚区分filtered列表的`task_idx`与`current_env.task_id`。
3. v3只纠正局部/全局索引绑定，同时加强闭合derived actions的attempt_id与冻结manifest一致性核验。local task_index、episode_index等仍为非负整数，完整context在同attempt恒定，method/source/bounds原门全部保留。实际四attempt局部task和episode都为0。最终通过，没有发现实际bounds或实例身份漂移。

v1/v2源码、异常、两次修订JSON和逐行diff全部保留。没有改变公式、bounds、阈值、样本或数据范围。新metrics读取计数：冻结hash各任务1次；v1读取tasks0/1，v2读取tasks0/1，v3读取全部4个；合计12次文件读取（8次提取+4次hash冻结），只限同四个允许路径。新tensor bundle读取0。最终提取耗时0.246548秒，低于120秒；Python单线程（上限2），CUDA不可见、未导入Torch/环境/provider/runtime，process/network/import/path guard无触发。

报告工作只读取本目录导出结果，不再读实际metrics或native记录。root提供已审查计划哈希作为绑定说明，不是本执行器新增实际输入。此screen已闭合、无剩余工程重跑，不改变source/controller/state/ledger/budget或在线实验。

## 输出与复现

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python extract_cpu_v3.py
```

仅供审查代码，已闭合目录拒绝覆盖结果，不应再次执行。所有输入哈希在read manifest；源码链每条actual method也保留原引用。输出清单：

| 文件 | SHA256 |
|---|---|
| `eight-step-summaries-v1.csv` | `9c50bbf3cba262e0e59b26320fbce7590b99d73d06b072eb9cd76564ebd66089` |
| `engineering-correction-v1.json` | `3925a4e0c92d5d7449bfbaa563be8eb72edd8bd65440f7903dab81c63f57a929` |
| `engineering-correction-v2.json` | `2f083ff72d29bfd0c4144ccfd2ac6782251a6304926463def99717edae5f342a` |
| `extract-v1.log` | `aa66d6b2d78166c026249a0f590f3e0b0be340273c40aa10100a4208eda40503` |
| `extract-v2.log` | `2fe63676e7848252a1d0a6aa610c6bc25869567f8dbfda1242c14708a9bd9ec5` |
| `extract-v3.log` | `f13713573c317ba2ea6d7f45837d881f48f604f5459992541b11dedf209e6d71` |
| `extract_cpu_v1-to-extract_cpu_v2.diff` | `fdf26ce786d03b6bda863bb136d524b0558fae867447c0a26fda0c443757023e` |
| `extract_cpu_v1.py` | `9c0c1d1a99bd7a55cb661f4abb0bcb4f554eedf922d963e7855d736c49bd4ce2` |
| `extract_cpu_v2-to-extract_cpu_v3.diff` | `3f26562f3f2b98e4c0e0749c269ac4733a188c9c665762865cac66b4791c2be9` |
| `extract_cpu_v2.py` | `0242f2036f556a8c8f5a334eee6c3d5ddb77c2c8ce7042955dc3a4fa70f05582` |
| `extract_cpu_v3.py` | `cc52612b8615ea6f8fecf0496b858d430fc1be4052a07d6cf10145785a125781` |
| `extraction-attempt-account-v1.json` | `693255ca3a66a1541df3423cf73b193c7f098cace76866c6f016b43aa88fe5af` |
| `freeze-v1.log` | `f98ab479e4cd594bb034086981e4766a1219b6564bae4549b514a3db07b8ebab` |
| `freeze_scope_v1.py` | `2f153b9f7a3424068193b1ecd539e71e5436ea0f29f818440e289e6244f8cb64` |
| `one-step-summaries-v1.csv` | `c30bb448f1f0b1718904052ad625b90698349ffba16165cb1637796cb30f29e3` |
| `read-scope-v1.json` | `82848e3bf21292449f05d3648887084ecb249eab3c94503184069de89cc954d3` |
| `report_cpu_v1.py` | `6664588e43f59ef917345f64dc4c05a242f01d1c612f327899a0ede6822b9039` |
| `result-v1.json` | `a676e47f929546dd8355b308d03b9cdc24c06ad7d1426a111d652351d379f373` |
