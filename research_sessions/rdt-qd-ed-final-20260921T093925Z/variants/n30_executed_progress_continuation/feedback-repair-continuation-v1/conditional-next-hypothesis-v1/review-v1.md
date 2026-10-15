# N30 条件性下一假设静态评审

**当前建议：COLLECT_TARGETED_EVIDENCE；不提名新的 GPU 算法候选（0/3）。** N30 R2 仍在运行。此结论不是淘汰 N30，也不是认定 QD/ED 的改进空间已耗尽。首个修复后 task0 的 C0/Q0/N30 都失败，而 N30 有24次有效 guided、14次插入、240轮父代和192次动作确认；它证明反馈/复制机制实际运行，尚未证明续接内容进入最终执行或产生收益。[S1–S4]

## 证据矩阵

| 已核验事实 | 支持什么 | 不支持什么 / 未知 | 来源 |
|---|---|---|---|
| N30 当前一个完整 matched triple 均失败；候选同进程审计通过，14次插入 | 先前 Boolean 工程问题已在真实 episode 闭合；新的 proposal 路径活跃 | 不知道续接直接内容或其后代是否获选；不是完整 screen 结论 | S1、S2 |
| N30 只在上一实际8步对旧 target snapshot 严格接近且身份连续时，将剩余56步+fresh尾8步放入行15；普通评分/父代/ED仍运行 | 单次实际接近可以提供下一次 proposal 的条件 | 接近不是抓取；旧前缀有效不证明未来尾部适用，也不证明 target 静止 | S3、S4；progress.py:119–150、194–226 |
| slot15起初被标为PROGRESS_MODE；父代分配将来源改成archive lane，最终archive selection全标qd_archive | selected_source是当前容器来源，不是跨迭代祖先标签 | 不能据其计数宣布“续接全被丢弃”或“续接赢了”；相同fingerprint也不自动证明唯一祖先 | policy.py:5262–5280、5741–5756、5793–5801、7156–7177、7321–7371 |
| N22 task0存在相同初始pool→有效质量不同→父代/动作不同；task1全同；task3一个分数变化但动作全同 | 机制活跃、搜索影响、实际动作影响是不同层次 | 动作改变仍未带来成功；不能以ranking/bonus次数替代收益 | S5–S10 |
| N22 task2首次行动分叉前Stage guidance已分叉；N22终局是INVALID，已审计四任务全失败 | 限定了跨臂归因；有四任务负证据 | 不是完整有效的10任务否证，也不能把后续guided数量差全归于算法 | S6、S9 |
| N24实际rescue156次，候选0/6、Q0/N23各0/6、C0为1/6，数值futility | 行为定向parent rescue活跃但此协议无成功收益 | 不支持未经新证据再做close bonus/保留lane或增加保留份额 | S11 |
| N25原cohort是INVALID，候选1/4；N26同轮候选N26为0/6，N25与C0各1/6，Q0为0/6 | N26数值淘汰；N25并非所有实验都零成功 | 原N25 INVALID不能变科学淘汰；1/6不是可靠优胜；不能跨cohort合并SR | S12–S14 |
| N26同轮N25/N26分别893/2033个标量call、96278/532个clipped分量，均无zero gradient | 输入几何/活动统计可很不同 | call分母不同，计数不能当配对处理效应；更少clipping未证明成功 | S13、S14 |
| 已有N3把上一实际执行位移减去投影位移，并对后续候选投影加线性残差ramp后重排 | “使用执行反馈校准几何quality”已是具体既存机制 | 不能把它重新命名为新feedback方案；本范围未重审N3全部实验结果 | S19:34–76、153–190 |

S1=R2/root-first-valid-repair-cell-review-v1.json；S2=root-first-matched-triple-observation-v1.md；S3=N30/hypothesis-and-protocol-v1.md；S4=core/qd_executed_progress.py；S5=N22/idea-declaration-v1.md；S6=N22/terminal-conclusion-v1.md；S7–S10=N22/task0..3-trace-conclusion-v1.md；S11=N24/root-terminal-review-v2.json；S12=N25/root-terminal-review-v1.json；S13=N26/root-terminal-review-v1.json；S14=N26/result-v1.json；S15=core/qd_executed_quality.py；S16=core/rdt_policy_steer.py列出的窄窗口；S17=原执行规格；S18=r2/controller-contract-v1.md；S19=core/qd_executed_feedback.py。精确绝对路径、SHA和读取字节见source-input-manifest-v1.json；S16记录窗口哈希，不冒充完整源文件哈希。

## 唯一优先的可证伪问题：插入之后，作用链是否到达执行？

条件性机制假设 H：**在仍guided且历史有效的决策中，N30已提供的续接在普通archive/parent/ED链路中没有形成可确认的最终执行贡献。** 这仅是需要排除的“作用链阻断”解释，不是已证事实，更不是一个新算法提名。先排除它，才能区分“proposal未传递”和“已传递但没有任务帮助”；N22的两类既存反例正说明不能省略这一步。

最小闭轮后诊断规则（本次不执行）：对本轮全部已接受N30格，不按成功、插入数量或轨迹挑样本。先用既有scalar/metadata列出active/eligible/invalid-evidence、第一次active的决策身份；无active的格原样保留。仅对每格事前规则选出的第一次active chunk（最多4个）检查一次作用链：初始插入行→同轮canonical/archive身份→实际parent→offspring关联→final selected/committed前8步。前一native plan已随n30_initial_proposal记录；不要为补历史无界追溯。记录直接内容一致、唯一可连后代、重复指纹导致歧义、无法连接四类，不把未连接直接当丢失；source明确original_archive_occurrences未记录，必须保留这一未知。[S16:5274–5280、5741–5756、7321–7337]

现有根summary不足以完成该身份判别。若下一scope允许，可先固定上述最多4个decision容器及其完整解码字节上限；tensor容器中共存事件的解码也必须显式授权，只导出指定身份/计数，不重新评分。仅当已记录身份本身不能区分重复来源时，诊断结论为Unknown；不能从指纹巧合补造祖先。完整 episode 的“从未选中”需要更广、另冻的证据，第一次active样本不能承担该结论。

如需判断已选中内容的实际短期响应，另在同一新scope固定这最多4个chunk已存在的8次executed_action/pre_reset_outcome，关联已有target snapshot及guided身份。只报告实际已执行路径到旧snapshot的距离前后差、实际命令和gripper状态；不将其称为连续目标进展、抓取或未选候选的物理结果。缺字段则Unknown。不重放模型、不新增分支仿真、不改当前N30。容器的精确个数/字节必须先stat+冻结manifest，本次未打开索引或tensor，故不臆造payload大小。

**判别结果：** 若存在唯一绑定的续接/后代进入执行，则“这些检查点全部在执行前丢失”的强版本被反驳，不能继续以该解释申请保留lane。若确无直接内容或可追溯后代进入执行，最多支持这些检查点的搜索门瓶颈；仍不证明该续接会比当前winner有用，更不自动支持N24/H4式强保留。若已进入执行却无后续接近，上一前缀进展不足以担保尾部；不能据此把更长memory、gripper锁定或orientation bonus当成必需修复。若身份歧义未消除，停止这一解释，不为凑下一轮补算法。

## 为什么当前不冻结新干预

- 再做反馈位移校准与N3重叠；只改阈值、步长、RBF尺度或close/lift奖励缺少新的作用链证据。
- 对N30插入做parent保护仍属于已暴露的retention家族。即使语义从“全close”换成“上一进展”，也需先证明当前确有丢失、且被保护内容可用；目前两个前提都未满足。保留不等于执行效果。
- 用orientation、真实hold或风险另设quality，目前没有已核验的部署时目标抓取姿态/holding标签或候选后果证据；单一target距离模板忽略这些量是静态事实，不是已发现可用的正确替代目标。[S15:19–31、152–161]

因此本评审不给出新的干预公式、参数或GPU试验行。也就没有可诚实声称会改善task success的候选预测。未来若证据支持一个具体干预，再与同轮C0/Q0及“只移除该干预”的候选对照冻结；guided保留176/11 canonical、Q0/N30实际256/16 total score与19RBF/21×B16 forwards，unguided5×B1，另计整episode Stage/GPU费用。正式QD移除/替换消融仍是独立必要证据，不能拿机制活跃替代。

N30若晋级，优先原独立验证路径；若有效淘汰，才审这份条件性证据建议；若工程INVALID，先按原规则闭合，不借此更换科学假设。578/100预算与protected32/12h、本轮3/4门槛均不变。目标仍TARGET_NOT_MET；本报告不创建新实验、预算或release。
