# N30 首次 active 续接谱系：一次 CPU 诊断完成

**两格的最终选择均为 `unique_content_supported_nonwarm`，不是直接插入行。** task0 的插入原内容进入前两轮各一个实际父代槽；task1 在十轮实际父代中均未出现。原56+fresh8、初始row15/其余15行、全部canonical身份、父代顺序、final native→FP32 decode→commit→实际8步均通过此次限定内容/身份核对。

以下仅覆盖两个已接受N30格各自最早active：step8 / `e0:d2:s8`，不是全部18次插入或完整episode。native dtype两格均BF16。无重评分、反事实模型、环境执行或新算法。

## 十轮父代/后代

每格每轮16父代。W为唯一内容支持的warm谱系推断数，D为直接等于初始插入native行的父代数，A/M为有歧义/缺失来源数。offspring行按已记录parent_indices和冻结无survivor的identity顺序相连；不是单亲“总因果”证明。

| iteration | task0 W / D / A / M | task1 W / D / A / M | 后代直接等于初始插入行（t0 / t1） |
|---|---|---|---|
| 0 | 1 / 1 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| 1 | 1 / 1 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| 2 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| 3 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| 4 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| 5 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| 6 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| 7 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| 8 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| 9 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |

两格所有已核对父代都有唯一先前canonical内容匹配，本样本未出现重复来源歧义或缺失。task0前两轮各有一个warm-linked offspring；下一轮并未自动保留这条后代链，后8轮无warm-linked父代。task1十轮均为非warm内容支持的谱系。完整匹配occurrence IDs及逐槽分类保留在result JSON，未凭aggregate selected_source推断。

| task | 最终archive行数 | 插入原内容仍在最终archive | selected index / cell | final matching occurrence | 最终来源类别 |
|---|---|---|---|---|---|
| 0 | 16 | 0 | 4 / 4 | e0:d2:s8:q5811:r4 | unique_content_supported_nonwarm |
| 1 | 16 | 0 | 12 / 12 | e0:d2:s8:q4250:r6 | unique_content_supported_nonwarm |

task0原内容作为实际archive allocation返回父代，证明它至少在这些已记录快照中可用；不能把task1未选父代写成“从未进入archive”。两格最终archive都没有原插入内容；原archive插入/替换occurrence未记录，所以未重建未观察的插入事件。

## 实际 steps8..15 反馈

目标是各自step8已有target0快照，stage1/tracked身份一致。下表是实际EEF到这个固定旧快照的距离，**不是投影距离、连续目标GT或抓取指标**。所选8步实际命令/ack与已选择的非warm候选绑定；全部16个gripper命令都是−1。

起点距离：task0 101.972 mm；task1 147.752 mm。

| 实际 step | task0 距离 mm | task1 距离 mm | task0 qpos L2（原单位） | task1 qpos L2（原单位） |
|---|---|---|---|---|
| 8 | 94.044 | 134.437 | 0.054407 | 0.054423 |
| 9 | 83.287 | 122.077 | 0.054735 | 0.054743 |
| 10 | 71.345 | 109.960 | 0.054920 | 0.054923 |
| 11 | 58.154 | 97.780 | 0.055026 | 0.055025 |
| 12 | 43.963 | 86.045 | 0.055100 | 0.055095 |
| 13 | 29.480 | 75.281 | 0.055163 | 0.055158 |
| 14 | 15.997 | 65.368 | 0.055223 | 0.055219 |
| 15 | 12.445 | 55.601 | 0.053687 | 0.055277 |

8步末相对该固定快照的距离减少分别为 89.527 mm、92.151 mm。这是已执行候选的实际局部接近，不能归因于未选续接，也不能说明未选续接会更好/更差。EEF和gripper反馈原dtype为float64；姿态字段存在但未作姿态目标或抓取推断。未遇这8步内terminal/truncated。

## 解释边界

- 此处genealogy是完整native内容与已记录父代索引/调度支持的推断。没有原archive insertion occurrence；无反事实，也没有重新计算或验证未开放的原生评分本体。原native有效性和steps0..7触发门继承已绑定worker审计。
- QD bounds/occupancy/sparse allocation与ED RBF存在全体候选耦合。非warm最终谱系**不能推出**插入对最终动作无影响或机制无效；仅限制“续接通过直接/单亲后代被最终执行”的解释。
- 两个初期检查点不能解释全部失败、其它active chunks、接触、持物或最终任务效果。原闭合三臂0/2及3/4门槛保持不变。没有放行保留lane、强制执行或任何新GPU实验。

## 单次执行与资源

精确release SHA `7075241f41d0b6bcf5bfab6ab12c23c4b5dca3a53599a7944b809e4f9e3bfb7c`；reader SHA `3f6404a29c0108f190a5eb83dffbfb0e42696f1cef1be44d9612c5c4dc99263d`。exit0，34文件各一次read/load，24,273,690 bytes；CPU 2.359426458s、reader wall 2.329512579s（工具报告外层wall2.455994852s）；峰值RSS 475456 KiB，AS16GiB上限；CPU affinity0,1/线程2。ZIP累计未压缩22,116,978 bytes、去重CPU storage20,814,272 bytes，均低于128MiB。

**guard_clean=false，如实保留。** 两次foreign路径探测被拒（一次listdir、一次open）：`/home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-gt-rollout-reintegration/third_party/lerobot/src`。未成功读取该路径；没有为了清理日志而重试。Torch导入成功、CUDA未初始化、显式CUDA张量工作0；不声称driver/runtime探测绝对不存在。execution日志为空，完整probe/resource记录保留。

结果为两格complete；partial和逐容器progress均保留。自此只读取自产JSON/日志用于整理，没有再次打开payload。资源中reader耗时不包含外部报告整理的小型stdlib命令；其已计量部分见closure JSON，启动/少量作者命令未作精确全流程CPU声称。

**本次诊断结束，停止数据工作。**
