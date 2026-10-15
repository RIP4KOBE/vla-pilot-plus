# 有限 handoff decoder 已冻结，未执行

范围严格为两格首次 e0:d3:s16→e0:d4:s24，68容器24,429,984 bytes，4个context和32个实际steps。reader/command仅准备；没有payload open/hash/decode、Torch/NumPy/production import、测试、GPU/API/model/scorer/sim或状态写入。

复用已接受lineage reader的guard、单次文件读取/hash、BytesIO weights_only CPU load、ZIP/CPU storage计数、资源和错误收尾。12个基础函数源码逐字一致，见static-syntax-v1.json；修改限新的固定refs/输入布局、分析字段与result schema。whole-container decode会含共存候选/score等，未来需独立release；只有固定白名单存留供分析，绝不比较候选、quality或provider返回值。provider仅输出既有digest，不跟随source_path、不打开或序列化provider代码/Stage正文。

命令→commit→indexed dispatch→actual action→pre_reset outcome→returned按精确event/step/reset身份绑定，记录原dtype/shape并逐字比较命令；不从native latent重新decode动作。N30 committed=false/无ack只是history状态，step24是否执行由真实通路绑定证明。反馈bool只接受Python bool或0D CPU torch.bool，拒绝宽泛truthiness。原worker的native算术/选择/源模板验证仍为继承证据，reader不冒充独立重放。

输出固定step16 target、raw start16、start24与step23原dtype字节连续性，4个Stage/final use_guidance/provider digest/tracker上下文、32个实际命令与EEF/quat/gripper状态、两段各8步net motion及23→24边界变化。缺失target/观测保留null；身份冲突拒绝并留partial，不能零target替代。当前keypoint沿用旧index的快照明确标记为旧target引用，不能推定新阶段目标；final use_guidance不是Stage查询need_guidance，禁用原因、真抓握与语义目标正确性仍Unknown。

progress逐容器落盘；partial在每个已分析实际step及每个完整decision后落盘。partial用于保留已完成工作，不授权自动resume/replay。资源/异常留存；已知foreign依赖探测仍拒绝记录，不为“guard clean”放宽路径。导入期间可能有driver探测，报告只断言CPU张量、CUDA未初始化，并不预宣称零driver调用。

未来单次120秒wall（外部timeout包含启动/退出），OS RLIMIT_CPU120秒/AS16GiB、2CPU与2threads；ZIP及累计unique CPU storage各64MiB。内部计时从stdlib导入后开始，不冒充完整进程wall；RSS仅观测不设虚构上限。无root release文件时reader fail closed；command.disabled.v1.json给出精确argv/cwd和root release字段例子（executable=false）。

静态AST parse/compile通过但未执行任何编译结果，不是运行/算术通过。保留一次静态旧manifest文件名查找错误（preparation-error-v1.txt）：旧reader显示后因source-manifest-v1.json不存在停止，实际名decoder-source-manifest-v1.json；没有payload访问、没有试运行。全部代码仅写本decode-v1；旧诊断与W不变。
