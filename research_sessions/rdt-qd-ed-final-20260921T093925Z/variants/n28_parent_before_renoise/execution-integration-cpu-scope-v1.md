# N28 执行接入：CPU 准备范围 v1

基于已接受的 CPU commit 85154b4dcb43046a2fcf2df4e8179b45b58dd2b4，在同一 implementation worktree/分支继续。root审阅：root-phase-a-cpu-review-v1.json。此范围只允许 CPU 工程准备，不允许实际 GPU、模型、API、仿真、生产 ledger/state 改写或 source adoption。

1. 保持 hypothesis-and-cpu-scope-v1.md 的唯一主要机制；不要加新scale、noise、quality、selection、跨chunk状态或provider变化。优先复用现有 metered worker、process lifecycle、receipt、GPU准入与通用证据审计，增加 N28 独立且默认关闭的路由/契约，禁止破坏已冻结 N27 及更早代码路径。
2. 新 cohort 固定为 N28_PARENT_BEFORE_RENOISE_SCREEN_20261001，C0/Q0/N27/N28、task0..3、原冻结 Dev task-seed-init 映射、task-major16格，无结果继承，无自动 retry。成功门 N28>=2/4、>=C0/Q0、严格>N27、QD/ED实质活跃和全部有效性条件；完整筛选不达门为REJECT_SCREEN，任何无效为INVALID并关剩余队列，不依模型代理指标挑删格。
3. 先准备新 native arithmetic 检查的代码、计划预览与CPU synthetic tests，实际执行权留给root。只需覆盖新的parent→赋值/散射封装与原helper接线、RNG/非xyz/尾部和重复/零梯度/边界不变量；原纯helper未变及N27旧数值证明可被明确引用，不宣称新parent来源已由旧same-forward witness证明。固定最多24个合成case（6种×FP32/BF16×2布局），0模型/评分/API/仿真；GPU进程含退出开销最多120秒，单GPU7，必须由独立真实release才允许执行，原预检只引用不复跑。CPU不得伪造native proof。
4. 新 profile expansion 与 worker 必须按新cohort路由至N28审计；第一guided原initial1个witness保持原N27 same-forward含义，parent10个是实际allocation副本，严格核对decision/iteration/parent_allocation_sequence、原始父代字节、geometry/operand/assigned delta/alpha/支持。原同进程CUDA后处理审计要计入worker时间，禁止第二个未计账GPU进程回放。
5. 新 N28 的完整guided chunk为initial4+parent10 RBF，21forward批、176候选/11评分批；对照保留旧19 RBF。区别parent phase与post-forward step（后者为0），正确处理零guided episode与有限witness不回填；合法零梯度只是描述值，不是无效或晋级门。保持总episode模型/reward/provider/gradient/encoder/renoise费用记录。初始N27质量/QD的原native checks仍适用，不关闭通用数值/执行/选择审计。
6. parent→实际renoise输入的绑定要明确区分“源代码相邻同变量调用+CPU调用链检查”与“实际native记录”；不将original_renoise_and_denoise_follow=True标量当作观察证明。如必要，可加最小first-guided bounded boundary witness，记录真正传入原renoise的prefix/身份，不增加model/score/RNG/projector调用，不越过原有限字节预算，并重新核对instrumentation parity。不要为此创建广泛新追踪框架。无同输入/同噪声的额外RDT counterfactual；模型传递因果仍Unknown。
7. 准备四臂实际命令的Hydra组合验证；pin当前codex_cli/chatgpt/current managed login、现有gpt-6-astra/low/180s与prompt。官方CLI源/flags不变，无Poe/alternate account/provider/API-key fallback；现有Poe凭据不可读/改/导出。准入前登录状态由root实际验证。grounding/guidance外部API额外调用仍为0。
8. 准备完整冻结科学源清单和现有runtime/data/model指纹复用，明确旧证明与新wrapper/source的桥接范围。不能将上一阶段19文件CPU清单当完整release清单。最终source commit在所有必要修改/测试后一次冻结；不提交运行时状态或历史产物。
9. 准备 controller/report 的故障关闭、预算/保护储备、精确顺序、scope/source/UUID/父子进程、未知费用等测试。明确计入每个dispatch与无效运行；缺token/HTTP细节记Unknown，不填0。终局独立结果包含逐任务/同轮gain-loss及原生/费用/有效性；不触碰验证/正式集。controller不得把成功筛选当完整Dev/正式目标完成。
10. 有限预算草案为538次/100GPUh，66/232/180/40/20桶，validation32/formal12小时储备不变，局部8.25GPUh、16×1840+120秒最大新工作。当前仍355次/48.11473511024311小时；草案未采用。只实现被具体root authority+source/runtime+native proof+execution release共同约束的门；没有这些真实材料就拒绝。不得因测试fixture有值写入真state或放行。
11. 未来大产物统一从本变体 artifacts 入口访问，并放在既有 R/artifacts/variants/n28_parent_before_renoise 子目录的数据卷；本阶段只使用小型synthetic fixtures。禁止复制模型/历史payload，代码卷约10GiB空闲。root后续创建实际存储入口，当前不动旧路径。
12. 累计N28 CPU测试预算仍180CPU秒，已用37.196932039，当前阶段余142.803067961；affinity2/线程2、CUDA隐藏，保留全部失败和探测记录。只在具体修改/失败需要时重测，不重复已过且未变的算子矩阵。遇到资源或语义缺口报告具体问题；正常只读依赖核实可自行完成，不反复等审批。所有代码和证据限本N28目录/implementation，禁止spawn新agent。提交具体代码、精简设计、实际测试/资源/差异清单供root审查；实际GPU和下一轮source adoption仍关闭。
