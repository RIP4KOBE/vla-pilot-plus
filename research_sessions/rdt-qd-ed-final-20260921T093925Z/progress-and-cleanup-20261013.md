# Autoresearch 研究进度与清理报告

核对日期：2026-10-13。用户可读时间采用北京时间（UTC+8）；原始记录保留 UTC。本报告只汇总现有证据并执行存储清理，没有启动新的实验，也没有改变研究预算或成功判据。

**目标尚未达成，当前没有本研究的 GPU 实验或自动迭代服务在运行。** 七天自动执行服务于 2026-10-11 19:14:37 按预设截止时间退出。最后状态不是算法成功，而是 N36 工程审计未通过，报错为 `fresh preparation release`（准备发布记录时效校验失败）。不能把包装进程退出码 0 当作审计通过。

目标仍是：LIBERO-PRO `libero_object_swap`，候选先通过新冻结验证集至少 10/20、且不低于同轮 C0/P2 与 Q0；再在历史固定正式验收集达到至少 5/10，并满足同轮对照、QD 实质生效、必要消融、成本与可复现性要求。**本轮正式验收派发次数为 0。**

## 1. 总体进度与计算消耗

| 项目 | 本次核实结果 |
| --- | --- |
| 已派发尝试 | 507；其中 463 个有效结果、18 个已结束无效结果、26 个中止尝试 |
| 总 GPU 消耗 | 76.0444236495 GPU 小时（包含已计账的健康检查与失败执行） |
| 当前记录的预算上限 | 1800 次 / 224 GPU 小时；并未耗尽 |
| 预算分桶已用 | baseline 107 / development 313 / validation 60 / formal 0 / recovery 27 |
| 七天窗口新增 | 104 次尝试：85 个有效结果、19 个中止；约 22.24 GPU 小时，含运行准备及健康检查 |
| 自动协调回合 | 1894 个；这不是 1894 个算法实验 |
| 最新有效科学运行结束 | N35 队列于 2026-10-10 04:54:02 结束 |
| 当前后台 | systemd 服务 inactive/dead，研究工作进程未检出 |

每个 episode、控制组、恢复尝试均可能占一次 attempt，不能把 507 次理解为 507 种算法。账本中的 `event=valid` 历史字段也不等于科学结果有效；本报告按 `outcome_valid`、中止状态和唯一 attempt 身份统计。

七天窗口的主要新增算法证据来自 N31、N32、N34、N35。N36 后续大量时间消耗在依赖、运行路径、来源绑定与发布时效审计上，没有形成有效候选实验。**自动工作持续了七天，但没有实现七天高效的算法迭代；工程修复占比过高，是本轮执行的明确不足。**

## 2. 实验演进与结果

不同表行可能使用不同 task/seed/init 身份；它们不是可以直接排序或相加的统一排行榜。中止、无效和未执行格子不作为有效成功率的分母。

| 阶段 / 变体 | 研究内容 | 关键结果与结论 |
| --- | --- | --- |
| 历史起点 | Q0 sparse QD、Q1 uniform-expand20；C0/P2 为 QD-OFF 对照 | Q0、Q1 各 2/10；同轮 C0 3/10。另轮 C0 的 4/10 不与前者合并。尚无历史 QD 配置通过全部 adoption gates。 |
| 更早扫描 | RBF 参数与增加 population/iterations | 257-job 扫描中仅 3 个有效配置各 1/10；18 个扩大搜索预算配置为 0/10 或 1/10。没有证据支持原样扩算力大扫。 |
| N1 | 距离与夹爪命令描述符 | 未获得有效候选 episode，效果未知。 |
| N2–N3 | 执行前缀质量、反馈残差校准 | N2 1/10，C0 2/10、Q0 1/10；N3 0/10，C0 3/10、Q0 1/10。代理几何改善没有转化为成功率。 |
| N4–N6 | 从终轮候选选择动作、抓取时机、高度描述符 | 完整 N4-E1 1/4，N5 1/4，N6 1/4。实际动作会改变，但没有稳定增益。原 N4 不完整队列不冒充完整结果。 |
| N7 | 水平接近方向 + 有符号高度描述符 | 小开发集 2/4；独立 C1 验证 N7 3/20、Q0 3/20、C0 0/20。验证未过 10/20 门槛；只检验同 init-row 下 seed 稳健性，不声称新布局泛化。 |
| N8–N12 | 分区细化、横向扫掠、父代存活、同状态抓取诊断 | N8 为离线分析；N9 1/4，低于同轮 N7 2/4；N11 1/4，与同轮 N7、C0 持平。N12 两条同状态分支都未成功，不支持仅提前闭合夹爪即可解决失败。 |
| N13–N22 | 阶段/停滞反馈审计、夹爪质量、被动物理诊断、闭合后抬升 | 多项为离线诊断或工程修复，不能全部记成在线候选。N18/N19 候选无效；N20/N21 各 0/1；N22 与其同轮对照在四格中均 0/4。 |
| N23–N26 | 实际执行裁剪后的质量、夹爪模式父代保留、RBF 更新 | N23、N24 各 0/6；N25 在早期开发 1/4，在 N26 匹配轮中为 1/6；该轮 C0 1/6、Q0 0/6、N26 0/6。没有持续优势。 |
| N27–N30 | 可执行更新方向、加噪前父代、群体相对信任、已执行进展反馈 | N27 修复轮 0/4；后续 N28 匹配轮 N27 1/4、N28 0/4；N29 与同轮 C0/Q0/N28 均 0/6；N30 修复后候选 0/2。停止于预设开发判据，剩余未跑格子保持未知。 |
| N31 | 抓取闭合和停留的候选提议 | N31、C0、Q0 同轮均 0/6。未获成功率支持。 |
| N32 | 让抓取候选进入 QD 档案选择链 | R2 候选有效结果 0/4，另 1 次中止；R3 续跑候选 0/2。R2 对照 C0/Q0 各 0/5；R3 对照 C0 1/1、Q0 0/1。分阶段保留，不掩盖中止。 |
| N33 | 中间的 CPU 可行性探索 | 无独立 N33 在线队列，不计为完成的候选评估。 |
| N34 | 利用已观察夹爪状态调整接近行为 | 修复后完整匹配七格：N34 1/7，C0 0/7，Q0 0/7。仅一个成功的探索信号。此前 11 次控制组中止保留计账。 |
| N35 | 闭合意图机制 | 同轮 N35 1/7、N34 1/7、C0 1/7、Q0 0/7，未优于 C0 或 N34。 |
| N36 | 非进展状态下的切向探索 | 四个科学队列均在 C0 控制组中止，另一次工程诊断中止；无有效 N36 候选成绩。最后 CPU 审计仍未通过。 |

完整的逐队列、逐 profile 分母和输出目录见 [JSON 汇总](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/maintenance/20261013/experiment-results-by-iteration.json) 与 [CSV 汇总](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/maintenance/20261013/experiment-results-by-iteration.csv)。早期机制细节见 [9 月 28 日报告](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/progress-summary-20260928.md)；其中旧预算和旧状态由本报告及权威账本更新。

## 3. 目前可以成立的研究结论

1. **尚未证明任何新候选稳定优于既有最优 baseline。** N7 的 2/4 是小开发集最佳信号，不能替代 3/20 的验证失败；最新代码 N36 也不是性能最优版本。
2. 优化不限于 QD 描述符：已尝试 quality 定义、父代/精英保留、最终动作消费者、可执行动作约束、反馈校准，以及夹爪时序。
3. 覆盖率、候选保留次数、几何预测误差、动作改变率可以改善，但这些改善并不保证抓取成功。N2/N3、N4、N24 的证据都提示应直接检查“候选变化 → 实际执行 → 抓取/搬运进展”的链条。
4. N34 的夹爪观测方向值得保留为弱探索信号；N35 没有建立新增收益。接下来应先修复最小运行通路，避免继续扩张重复审计和发布依赖，再做有明确停止判据的匹配小规模实验。
5. 验证、正式验收及必要消融仍未完成。不能给出可信的“已完成百分之多少”，也不能保证再延长运行时间就能达标。

## 4. 文件位置

所有研究文件的统一**导航入口**：

`/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood`

当前会话目录：

`/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z`

| 入口 | 内容 |
| --- | --- |
| [study_worktree](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree) | 研究主代码、research-state.yaml、实验协议、data 下私有账本、结果与 Arbor 会话记录 |
| [variants](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants) | 按 N2–N36 等算法/诊断变体分类的实现、方案、CPU 验证、分析和报告 |
| [artifacts](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/artifacts) | 大型原始产物：attempts、冻结计划、原始动作/决策 tensor、图片、视频、日志、runtime；部分后期实现位于其 variants 内 |
| [autonomy_20261004](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004) | 七天驱动、systemd 配置、授权与预算记录、每次自动协调回合；turns 指向数据盘 |
| [historical_variants](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/historical_variants) | 早期 eds-* 历史 worktree 与结果；本次中间图清理发生在这里 |
| [另一已归档会话](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z) | 原 GPU2/N1V 系列的独立研究记录，与本会话预算分开 |
| [本次维护记录](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/maintenance/20261013) | 本报告、逐队列结果表、删除计划/执行清单、再生成校验和恢复脚本 |

`artifacts` 的实际磁盘位置是：

`/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z`

这是已有的符号链接布局：从统一研究目录可访问全部当前会话产物，但大型文件物理上在数据盘。不能把“统一入口”解释成所有字节都在系统盘。旧绝对路径的兼容链接仍保留，避免破坏既有引用。

## 5. 本次清理

按用户本次授权，删除范围严格限制为：

- 历史 RBF 扫描中，可由保留的 `tensors/mechanism_trace.pt` 重新生成的中间 3D 图：仅第 1–8 轮的 population/best-trajectory 图；第 0、9 轮及所有最终汇总图保留。共 **94,880 张**，原占用 **10,062,684,160 字节**。
- 统一目录及当前会话数据盘内的 Python 字节码与测试缓存：**3,897 个文件**，原占用 **111,153,152 字节**。

合计按文件实际分配块数释放 **10,173,837,312 字节，约 9.48 GiB**。清理后系统盘可用约 **9.70 GiB**，清理前仅约 **0.26 GiB**；不同进程同时写盘可能造成少量变化。

没有删除科学失败/中止结果、任何候选的原始实验数据、模型权重、源代码 worktree、正式/验证证据、账本、凭据或无法确认可废弃的测试夹具。没有迁移原始数据，也没有终止其他研究进程。本次清理释放的是**磁盘空间**；物理内存原本约有 801 GiB 可用，没有清空系统页缓存。

清理前后研究状态与四份私有账本 SHA-256 一致。抽样用保留的原始轨迹重绘两类图，均与原图字节级一致。保存了逐文件路径、原大小、inode、SHA-256、删除原因和原始轨迹位置：

- [执行结果](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/maintenance/20261013/cleanup-result.json)
- [删除清单](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/maintenance/20261013/deleted-files.jsonl.gz)
- [重绘验证](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/maintenance/20261013/regeneration-check.json)
- [恢复中间图脚本](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/maintenance/20261013/restore_intermediate_plots.py)
- [最终复核](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/maintenance/20261013/final-verification.json)：5,930 份对应原始轨迹全部在位；删除后又抽取两张图运行恢复脚本，均与原图字节级一致。恢复脚本导入模块时自动重建的少量字节码缓存不影响清理结果。

如需查看已删中间图，用 vla-pilot 环境执行恢复脚本并传入具体历史 chunk 目录即可；不会执行仿真或调用 API。原始轨迹和绘图源代码均已保留。原历史报告本身保持不变，本维护报告说明了中间图的删除情况。

