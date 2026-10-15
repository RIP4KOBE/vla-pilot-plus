# N30 first-active decoder：准备完成，尚未执行

固定两个接受N30格、各step8首次active，沿已接受Phase A的34完整容器/24,273,690 bytes。`decode_cpu_v1.py`不导入生产代码，不运行native auditor、评分、RBF、模型或仿真；当前只做过一次stdlib AST语法检查，未启动Torch、未读payload、未跑测试。

程序必须先验证新root release的executable=true、reader/input/protocol/Phase A review/source manifest全部精确hash，以及6292fc8六份静态依赖源码的实际字节，才允许Torch导入及精确payload路径读取。`execution-release.disabled.v1.json`和`command.disabled.v1.json`不是release。root审阅后另建固定路径root-execution-release-v1.json；不运行此disabled模板。

分析输出是每格10轮parent/offspring计数与content-supported谱系、final selected/committed绑定、steps8..15相对固定step8目标快照的实际EEF/命令/gripper描述。完整native内容比较保留dtype/shape/bytes；canonical fingerprint严格little-endian FP32无round。初始56+fresh8及mask/其余15行、native→FP32 decoder零夹爪映射、真实action/ack/terminal关系分别检查。

重复同内容occurrence报告ambiguous，缺少原archive insertion occurrence始终说明。单个匹配的推断也不是记录过的插入因果事件；单亲调度不等于ED全批因果依赖。即使无可确认warm祖先，也不能排除bounds/occupancy/sparse allocation/RBF间接作用。无quality/奖励重排、不分析共存projection/provider-return/score内容、不导出raw动作或场景数值数组，不用gripper状态推断抓取。

父代需满足冻结identity_indices、elite_count0、16个offspring source与lane顺序；事件episode/decision/reset、guided stage、Main packet/tracker/keypoints/current target、commit.step8皆独立比较。旧steps0..7触发门和完整原native source有效性明确继承bound worker audit，当前不会重算旧历史。

## 执行边界（待root另行释放）

命令用timeout SIGKILL 120s覆盖解释器启动/退出，taskset 0,1，线程2、CUDA隐藏，Python -I -B。reader在Torch导入前设16GiB RLIMIT_AS、120s RLIMIT_CPU，内部119s报警留退出时间。不得自动重试；若被外层SIGKILL，progress/partial保留而final resource可能缺失，root据外层退出记录判断。

每payload仅一次filesystem open/read，SHA从同一bytes计算，然后一次BytesIO weights_only CPU load。全部ZIP成员累计未压缩<=128MiB，全部CPU tensor去重storage累计<=128MiB；这包含共存事件，绝不称只解码白名单tensor。各文件读取/加载成功与失败分别记账；每轮与每步已有结果写partial，不补零或继续扩读。

审计guard在Torch导入前安装：payload精确路径且只准当前单次读取；标准Python安装根与系统运行库仅读；/proc/self/maps、/proc/cpuinfo等列明runtime metadata只读；已确认字符设备/dev/null仅sink；tmp在本目录；写入仅固定输出名/owned tmp。禁网络、子进程与生产模块导入，普通依赖探测拒绝会如实记录。Python audit hook不等同内核文件系统沙箱，动态链接器原生访问不保证逐项可见；不声称完全无driver/runtime probe。显式不做CUDA张量工作，记录torch.cuda.is_initialized。实际依赖启动兼容性尚未运行验证，不先验写guard-clean。

root审核可直接按禁用JSON中的参数制作新release；source manifest与reader hash不能在执行前漂移。当前原有源码、实验、预算、状态和Phase A产物未改。下一步仅这一次现有证据诊断，不提名新算法。
