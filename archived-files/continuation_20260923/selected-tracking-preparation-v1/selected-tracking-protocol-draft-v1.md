# Selected projection → executed EEF：有界读取草案 v1

状态：仅源码/协议草案。尚未实现、未读取 residual 或任何新增 episode；需要 root 另行决定此精确范围。它独立于已冻结 full-Dev chronology，不修改已有分析/算法。目的只有两项：描述实际所选投影与真实 EEF 的向量/幅度/步位关系；检验前一段已观测偏差对紧邻下一段是否有描述性预测信息。不推断目标、抓取、接触、失败原因或任何未执行候选的效果。

## 输入与先行门

仅使用 full-Dev 报告绑定的 **30 个 accepted representative**（10 tasks × C0/Q0/N2，接受正确链接的 recovery，排除其所有 invalid predecessors）。精确 attempt/path 清单必须从 root 已核验报告与 full chronology manifest 冻结进新授权，不按目录搜索、不用相似 suffix猜测。报告 SHA由 root提供为 `d376f98a0d0d23d7b73b0a20ab768594c63ed6a6abce9473e0e67d2247bc88ab`；本草案没有读取该报告。所有 guided decision都纳入；不按 success、任务标签、Q8是否激活或误差大小挑选。unguided仍计总数但记 no_recorded_selected_projection，不新增投影。

授权后、首次 tensor decode 前，绑定新脚本/协议、source525506ca、对应 source inventory、完整矩阵报告/manifest、每个 representative 的 accepted terminal/audit/compute、collector status/index及每个bundle SHA。若刚完成的 full chronology 保存了同一冻结 auditor 产生的 fresh accepted/evidence_complete 审计及精确输入hash，可以验证这些hash和 frozen index 后复用，不重新审计所有30。若 fresh audit未绑定同一bundle集合，先停止报告缺口；仅经 root 明确采用原冻结auditor才可补审计，不能默默放宽、调用旧0d59锁源CLI或扫描其他episode。

仅 CPU `CUDA_VISIBLE_DEVICES=''`、`map_location='cpu', weights_only=True`；确认 torch CUDA始终未初始化。不实例化 policy/adapter/environment，不调用 decoder/provider/projector/model/simulator，不访问视频或keypoint/target值。原生tensor只作hash/shape/dtype核对，导出新的小型表；不重存大bundle、不覆写原文件。读前/读后hash一致，输出独立路径，异常complete=false且原terminal不变。

## 必需关联与来源（不靠行号猜）

| 内容 | 现有字段/源码 | 约束 |
|---|---|---|
| 真实选择 | `decision_context`、`final_selection`、`policy_action_decode.selected_canonical_fingerprint/selected_latent/action_chunk` | episode/decision/reset关联精确；canonical fingerprint只用作索引，再核native shape/dtype/bytes与允许的明确cast路径。不能靠float值相近匹配。 |
| 既有投影 | canonical角色的 `scoring_inputs.samples/projected_xyz/projection_origin_sequences` | 只导出与实际selected相符的行，不评分/排序其他行。多个同content发生位置都保留引用；只有投影和origin的shape/dtype/bytes全部一致才可折叠为同一个值，不能声称唯一archive插入祖先。不同值/identity缺失记Unknown，不任选一行。 |
| 起点 | 指向 `projection_origin.source_eef_position` 和 `cast_eef_start` | sequence在同decision的score之前，x0与cast起点native一致。未cast来源O是当次controller EEF位置，不是想象的episode初始raw observation。 |
| 实际动作 | `decision_committed`、逐条 `action_dispatch.execution_index`、`executed_action.action_numpy` | dispatch index=1..m且global_step连续；只使用实际执行的prefix，m≤committed H=8。decode、commit和sent的关联另核，不用Stage gripper日志替代真实sent。 |
| 实际响应 | 同dispatch窗口的 `pre_reset_outcome.observation.robot0_eef_pos` 和 `step_returned` | 使用真正env.step后、auto-reset前的观测；返回reset后的新初始观测不能接入旧prefix。terminated/truncated都结束连续段。 |

当前源码证据：`core/rdt_policy_steer.py:1745`评分保存full projection；`:7078`每candidate取前8步 `[39,40,41,42,43,44,10]`，交adapter既有投影。`core/env_adapters/libero_adapter.py:1627`构造t0..t8、以 `get_ee_pose_world` 起点和native dtype累计；`:1664`固定 `ACTION_SCALE_POS=0.01`。这个常数与注释“controller实际缩放另行处理”只证明近似结构，不证明配置bug或实际尺度不匹配。**禁止按本次误差反推出/修改该常数。**

## 坐标、精度与动作变换

1. 对每个可解析decision记 `X=(x0,…,x8)`、未cast源起点 `O∈R³`、`cast_eef_start`；记录所有native dtype/shape/hash/finite。预计投影shape(9,3)、真实EEF各(3,)、sent各(7,)，必须实测核验；不假定BF16或FP64。原始cast误差 `O−x0` 独立报告。
2. 起点来源是 `get_ee_pose_world → get_ee_pose → controller.ee_pos`；实际p来自 `robot0_eef_pos`。源码意图是同world坐标，但观测时间/控制器更新差异仍可能存在。若同episode/reset、前一dispatch连续，可另报 `O−p_previous_post_action` 作为origin bridge，不要求其为0，也不拿它替换O。首个decision没有先前raw post-action起点时该bridge为Unknown，不能把x0当成高精度实测点。
3. `core/rdt_libero_action_converter.py:31–65`只取动作索引、cast FP32并二值化gripper，没有位置clip。main在commit前走env postprocessor；adapter当前配置的该pipeline为空，又在step中走一次，再二值化gripper并cast FP32后记录sent。核对selected canonical→decoded/committed→sent的位置和旋转量是否符合这条路径；二值gripper单独记录，不影响纯XYZ公式。不得把记录中的真实差异通过重算decoder抹掉。
4. 区分投影使用的native位置分量和实际sent FP32位置分量；报告差值/边界外sent数量（源码声明bounds[-1,1]），不擅自clip数组。下游controller的实际 clipping/scaling/动力学未完整记录；相关值与作用Unknown。即使sent在界内，也不能宣称控制器没有饱和或真实执行等于命令。实际残差可能混合这些因素；此诊断不给原因标签。
5. 所有身份比较先保留native dtype/shape/bytes。仅在关联完成后把存储值转CPU float64作描述性减法、平方和；这不恢复丢失精度。记录native相邻可表示值间隔与origin cast误差；不把小于存储分辨率的差解释成物理改善。`torch.equal`数值相等单独不足以证明dtype/bytes相同。

## 预定量与时间对齐

decision起点的global step记s；execution_index=i对应实际action `s+i−1`，其pre-reset响应记 `p_i`。`x_i`对应同prefix i动作后的投影，**不能用p_1对应x0或把末帧当末动作响应**。终端短chunk仅计算i=1..m，m实际来自dispatch；不补到8、不按720整齐划段。gap、重复index、跨reset、missing值记具体Unknown或identity failure，不使用插值。

对全部可关联selected prefix预定义：

- 原样绝对误差 `e_abs(i)=p_i−x_i`：xyz、L2及逐步平方L2。
- 去除起点cast差的描述性位移误差 `e_disp(i)=(p_i−O)−(x_i−x0)`；不是重跑projector。两套均保留，不在结果后选更好看的一套。
- `origin_cast=O−x0`，可用时另列origin bridge；每prefix报告末点误差与 `mean_i ||e||²`（分母m），并按i=1..8分别报告实际观测数、向量均值和L2分布。每episode先摘要，task/arm逐格并列；不把chunks当独立episode扩大小样本。
- 相邻步向量差仅对i≥2用 `p_i−p_(i−1)` 与 `x_i−x_(i−1)`；首步用O的版本明确标作source-origin约定，不能伪称有独立pre-action raw观测。禁止将EEF移动自动叫目标进展。

不读provider回调结果、keypoint值、target map、最终pool其他候选quality或候选反事实。provider身份metadata只用于下一节同语义连续性，不用于宣称目标物体绑定。完整性审计已读过的大bundle可能含这些字段；实现只访问/导出该最小allowlist，不扩展科学分析。

## 预先声明的 retrospective predictive check（另请root明确接受）

资格只基于已知时序/身份，不基于成功或误差：同episode/arm、无reset/terminal/gap/OFF、紧邻guided decisions、相同source+profile、相同stage、provider有序原code/text/path身份精确相同且均完整；前段m=8；后一段m为实际执行长度。前段已完成才提供feedback。缺字段只记Unknown、不猜hash或默认provider/target index。相同provider身份不证明同一物体/目标附着，本项是无target的运动误差时间关系。

固定使用前段 `r_previous=e_disp_previous(8)`，不拟合系数或筛误差窗口。在下一段的每个实际步i定义基线 `b_i=O_current+(x_i−x0)`；零预测残差时error=`p_i−b_i`。固定一步transport预测为 `b'_i=b_i+(i/8)r_previous`，报告其误差及与零baseline的逐prefix MSE差。前段endpoint提供信息只用于下一段；不以当前误差构造当前校正。不裁剪r、不搜lag/rollingwindow/gain，不因partial改变分母8。输出所有qualified pair和被排除原因；总体只作逐episode/arm描述，相关chunk不提供独立显著性样本。

这只是用已执行两段检查“前段偏差是否含下一段预测信息”，不是部署新算法，也不是新候选会选什么的反事实。物理轨迹未受校正影响；不能把误差下降当任务收益、可用quality、controller修复证据或晋级门。即使有关联，新的内部质量还需另冻结实现、相同预算和同轮Dev；没有关联则不据此拟合更复杂校准器。

## 交付及停止

最小输出：`inputs-and-source-hashes.json`；逐decision选中内容/投影/源起点/真实prefix关联与Unknown表；逐prefix步位误差；仅合格相邻pair的固定baseline对比；30格完整计数/episode摘要及简短限制。不会添加成功/成本裁定或改原report，所有invalid/recovery计费仍由原报告负责。

实现前冻结工具SHA与纯合成fixture（t0错位、原点cast、同fp异dtype/投影歧义、sent变化、reset、m<8、已知/未知pair）；实际读取前root批准上述范围与transport项，并核验精确30路径和fresh-audit输入绑定。缺失核心provenance或源hash不符立即停止；仅局部可选身份不足保留Unknown，不能“补推”身份。此草案既不授权当前作者读取真实residual，也不授权GPU实验或候选实现。
