# N27 条件性 outer-loop 复核

结论：若当前固定 screen 最终失败，**本次限定证据不足以优先登记一个新的算法候选**。建议为 `COLLECT_TARGETED_EVIDENCE`，不是继续包装 scale、close bonus 或 parent retention。当前续跑未终结；本报告不改变任何规则、预算或 release，也不把任务0或父代理转述的任务1失败当作全轮结论。

## 已知与未知

- **实现与作用位置**：`qd_clean_output_rbf.py:28–50` 要求实际 scheduler 的 prediction_type=sample，以同一 model_output 为几何输入；`qd_actuator_clipped_rbf.py:59–95` 在 detached leaf 上用 clipped 前8步投影的逆距离势能梯度及全局归一化。`qd_feasible_ray_update.py:40–58` 用每粒子24个平移分量的最小FP32边界比率限制原方向，非零更新只允许严格内部坐标，零更新保留原字节。源码能说明该局部契约，不能单凭阅读证明全部线上算术或最终执行。
- **机制已活跃**：唯一获准读取的 task0 root review 接受该格有效、success=false。14个guided chunk有266次RBF调用；3604/4256个粒子限步，alpha均值0.54549、无alpha=0；实际赋值delta范数均值8.08054，原提议operand范数均值20.00141；记录的新增越界分量为0。11个有限witness由原同进程审计验证；本复核没有重放它们。故该格不支持“开关未生效”或“更新完全被舍入吞掉”的解释，但标量检查不等于对266次调用全部做了独立张量证明。
- **任务因果收益仍Unknown**：这些量是 scheduler 之前的预测动作对象，不是最终候选、被选中动作、真实位移或抓取进展。`qd_feasible_ray_rbf.py:37–60` 明确区分operand和实际赋值delta；它没有给出经过后续去噪/调度后的任务后果。本次允许材料不含该因果链。合法失败证明这一格未完成任务，不能定位是proposal、selection还是closed loop。

闭合N26叙述已给出0/6，而同轮C0/N25各1/6；其132个有限N25/N26 witness中，N26更新前后越界116→7333/25344，非零operand被舍入吸收仅83/25215，未见完整投影alias。这些支持了**正在被N27检验**的可行性假设，不能在N27尚未闭合时再次当作新假设的证据。N27若失败，只能否定其冻结screen晋级条件；不能证明所有可行更新、QD/ED或固定模型均不可能达到目标。

## 为什么不选一个“看起来不同”的后继

每粒子共用最小alpha，静态上确实可能由一个分量限制其他分量；但现有aggregate无法证明这损失了有用的任务行为。改逐坐标截断/切向方向/归一化或时刻权重目前都只是可行性轴的未验证变体，不能从“限步很多而失败”推出优先级。反过来，降低标量、提高精度、继续保留close父代，也没有新增证据绕过既有负结果；本次没有重新阅读它们的历史trial来挑有利例子。

因此**优先算法假设：无**；不为保持队列运行而登记候选。当前材料也不足以断言“reward/selector一定错误”：外部provider、完整候选池质量排序及动作后果不在本次读范围。

## 唯一值得补齐的区分事实（未执行、未授权）

在相同可恢复的已暴露Dev状态，搜索中是否存在**确实推进任务、却被现有选择规则放弃的候选前缀**？这是区分“再改proposal”与“转向selection”的缺失事实，而不是下一算法已成立。它需要预先定义、与部署可观测量一致的进展判据，以及足够的同状态候选结果证据；positive gripper、较低几何cost或更大距离都不能代替。

最小可证伪预测可写成：在事前固定的同状态比较中，被放弃候选达到该进展判据而原选中候选未达到。若二者均未推进，则该例不支持selection损失；若原选中同样推进，也不支持此“放弃更好行为”的解释；单例成立仍不证明某种新selector能泛化。没有真实反事实时必须保持Unknown。执行规格§5明确要求额外仿真分支另行限定与批准；本报告没有创建该范围、没有调用仿真，也没有授权读取更多payload。若闭轮后不能获得这一类能区分机制的证据，宜如实报告目标未达及证据缺口，而非无限生成候选（执行规格§6）。

## 读范围与来源

仅以下8个文件；未跟随JSON/文档的链接或读取其他记录。`W`为当前统一研究目录下study_worktree，所有科学源码保持不变。初始rg只作这些文件的文本定位，但未显式设置其线程上限，实际并行数Unknown；后续标准库读/哈希/写进程显式限定2CPU和60秒CPU上限，一次完整读/哈希进程记录0.00134CPU秒。没有执行Torch、生产模块、测试、GPU、模型、API或仿真。除本文件外未新增产物。

| 路径（相对R） | SHA256 |
|---|---|
| variants/n26_clean_output_rbf/outer-loop-update-feasibility-review-v1.md | `73960862fea1702218f6bc1a1652d261dbcb3ec392b0a03853e85c90a06a36e8` |
| variants/n27_feasible_ray_update/hypothesis-and-scope-v1.md | `a49314e4349c2e4ee273374703fe16e0d734871ff244009b31041e484817f9bd` |
| variants/n27_feasible_ray_update/hydra-continuation-v1/task0-root-review-v1.json | `04d1e04701b988a9fdace815772f366aa213e9bb7b1d6f7f22f11fd1ccbd1e18` |
| study_worktree/core/qd_feasible_ray_update.py | `146163977866af87d2c643b0446be9ebac12f83cf9337d534b736874c623203e` |
| study_worktree/core/qd_feasible_ray_rbf.py | `f2494d1a2c55f4899d848d5f7e8af03cc8518cd53749c8875a117c1ff15a3207` |
| study_worktree/core/qd_clean_output_rbf.py | `f107f50e45c233e291e5f5799633b0f3005fe54dc0649506dec41a4c02bb789c` |
| study_worktree/core/qd_actuator_clipped_rbf.py | `d0a516046f9d9efc8694916a9ff845c8b67868d8d7d2d01381894bcc05b89408` |
| study_worktree/docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md | `3a45e53d3b40fa0a40c43ad53a34cfbb8c9fe497dc98a5e178e4c1ef016999ef` |
