# 首次 EDS→nonEDS handoff：实际反馈诊断

**完整覆盖两格、四决策、32实际步；没有新增算法提名。** 两格step16均为Stage1/use_guidance=true/provider1；step24仍Stage1，但use_guidance=false/provider0。两格记录tracker实例与generation1、旧target index0均连续，reset_sequence=0；start24与step23实际反馈原dtype/字节完全一致。未发生记录中的Stage切换或环境reset。最终context仍不能区分Stage查询“不需引导”与Main后置禁用，不能称Stage错误。

所有距离都对**各自固定step16目标快照**计算，单位mm；不是实时物体距离或任务效用。两段的实际EEF/quat/gripper均为native FP64，命令为FP32；记录命令→commit→actual→outcome/return均通过绑定。

| task | 已执行段 | 引导 / 夹爪命令 | 旧snapshot距离：起点→终点 | 净EEF位移范数 | 对旧snapshot净接近 |
|---|---|---|---:|---:|---:|
| 0 | 16–23 | 是；8步全+1（关） | 10.962→41.347 | 33.396 | −30.385 |
| 0 | 24–31 | 否；8步全−1（开） | 41.347→60.332 | 27.584 | −18.985 |
| 1 | 16–23 | 是；8步全−1（开） | 55.601→21.390 | 60.339 | +34.211 |
| 1 | 24–31 | 否；24–28为−1，29–31为+1 | 21.390→17.646 | 4.300 | +3.743 |

**task0：** 与旧目标的距离在仍有EDS的16–23段已逐步增加，EEF净向上28.418mm；随后非EDS段净向上20.449mm。23→24时命令由关变开，实际EEF当步对旧snapshot距离增加6.194mm。关爪段qpos从step16的[0.03517,−0.03887]到step23的[0.01174,−0.01086]；开爪命令开始后step24仍为[0.00790,−0.00740]，到step31回到[0.02921,−0.02923]，显示命令与状态的时间差。不能把上述向上/远离自动称为退化：抓到物体后抬升与未抓到后离开，目前均未证实。step24同tracker/index的keypoint快照有所更新，计算始终不更换固定step16参考。

**task1：** 16–23接近34.211mm，切换后24–31仍接近3.743mm；23→24当步再接近0.840mm，夹爪命令未在该边界改变。直到step29才给+1，step31 qpos为[0.04011,−0.03387]；不能用三步命令或这些坐标判定抓握。其旧index快照在两个决策中相同。两格32步均无terminated/truncated。

23→24 translation命令向量差的L2分别0.523889与0.400214，属于**动作命令坐标**，不是EEF物理跳变。两格N30历史flag在step24均committed=false、ack0，但decision_committed和全部实际反馈存在并一致，不能当成没有执行。

这些记录反驳“两格在此次handoff都立即中断接近”的强描述：task1仍继续接近；task0的旧snapshot远离在切换前已经开始。它们不证明保持EDS、维持关爪、保护warm或改变Stage会改善任务。真抓握/接触、目标语义是否选错、期望抓取姿态、禁用的原始原因以及未执行动作的结果仍Unknown。只覆盖预先选定的首次handoff，不代表完整episode；不重读旧尾部、不产生新的反事实或GPU候选。

执行与资源：reader 4f11e72f…497ed0 未改。先前launcher硬限错误保留；新明确手动授权下exit0，readerPID3858764/start_ticks93705935。68容器24,429,984 bytes每份一次open/hash/load；ZIP22,213,773 bytes，CPU独立storage20,884,656 bytes，4decision/32step及最终partial一致。reader CPU2.074040754s；完整child CPU2.347659s，外部启动至退出wall2.233845076s。两次启动合计child CPU2.390150s（第一轮零payload）。CPU affinity0,1/线程2；AS16GiB，峰值RSS469,520KiB。旧失败不覆盖，无自动重试。

`guard_clean=false`如实保留：foreign lerobot/src 两次list/open探测被拒，路径及事件完整见resource-v1.json，未允许访问。CUDA未初始化、显式CUDA tensor工作0；不声称没有driver/runtime探测。没有模型、scorer、API、仿真或研究源码/state/budget写入。行政摘要仅读取本次JSON产物，没有payload或数值重放。
