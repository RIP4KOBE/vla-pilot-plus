# N27 条件性 operator-placement 反驳复核

**结论：这个想法与旧 clean-tail 有实质区别，可以保留为一个可证伪的条件性机制假设；证据尚不足以判定其能改善任务，或直接放行下一轮。** 它把“去噪过程中改预测输出”改成“对当前 QD 父代作一次变异，再由既有去噪链处理”。当前 N27 screen 未终结；本报告不是候选登记、实施或 release。此前8份材料下“不足以优先登记后继”的报告保持原样；新增接口/时序证据只支持更具体地提出这个问题，不补齐任务因果证据。

## 与旧负结果的区别，以及不能声称的东西

获准 curated schedule 记录的是 task0 首个 guided chunk：initial 4次、rollout 15次 RBF；10个 rollout 中9个在最后一次 model forward 后、scheduler.step 前仍修改 model_output。它证明**操作位置**，不证明这个位置造成失败。task0 独立 root review 为 valid failure；可行射线实际赋值活跃、新增越界为0，这也不等于最终动作或抓握正确。

历史 clean-tail 报告§1、§6（第11–19、118–124行）中，唯一改动 skip_final=1 后 winner 2/10→0/10；2790个单步 rollout 完全无 RBF，方向覆盖和 endpoint spread 中位数分别降68.9%、93.3%。这是既定旧协议下的有效负结果，不能重包装成新方案；其旧 Stage/query 容错也不等于当前严格 validity 协议（旧报告§10–11），这些数字不是当前 N27 的匹配对照。

拟议操作会在**每个** rollout 前保留一次父代变异，即使 n_trunc=1 也不主动删除该机会；随后不再改 rollout model_output。因而它不是 skip_final=1 的别名。然而输入对象、噪声前后位置、调用次数均改变：按当前3→1整数线性 schedule 和0.6门，rollout RBF由15次变10次，initial4次不变，总19→14。原16次 rollout denoiser forward、10次 renoise、11批/176 canonical评估可以保持，但 RBF/projector工作和总耗时不等价，必须如实计账，不能称纯时序单因素、等价梯度或相同总算力。

## 静态接口是否真实存在

`rdt_policy_steer.py:5154–5175,5333–5374` 在本 guided chunk 初始化 population 并新建 archive；`5615–5666` 从该 archive 取 parent_actions，`5774–5797,5900–5907` 生成 offspring，形状为16×64×128（当前 clipped preset 无 exact survivor/rescue，`8544–8550`）。`6104–6105` 才 renoise，`6164–6193` 才调用并评分 rollout，`6322–6357` 得到下一轮 population。因此 **pre-renoise offspring 的接口存在，是同一 chunk 内已去噪候选的模型动作空间副本**，不是 noisy x_t，也不是上一 chunk 的已执行动作；父代可以来自本 chunk 更早的 archive，而非紧邻上一轮全部 offspring。

这里的“归一化动作”应精确理解为 scheduler/模型使用的统一128维动作坐标：这条路径没有经过 `_postprocess_actions` 的最终 LIBERO decode（`7674–7680`）。不能进一步声称每个值已在[-1,1]、物理单位已标定、处于模型流形，或它是本轮同一次 forward 的原始预测。初始/历史 rollout 本身可能包含 RBF 修改；本次也未递归读取 archive helper、converter 或 scheduler 实现来另作字节/数值证明。

已有几何使用前8步 xyz 的 clipped投影、detached梯度和全局范数归一化（`qd_actuator_clipped_rbf.py:45–95`），符号为减逆距离势能（policy第109、3954–3955行）。纯可行射线 helper 可处理相同 shape/native dtype 的前缀；但 `qd_clean_output_rbf.py:38–50` 与 `qd_feasible_ray_rbf.py:69–80` 的现有证据明确绑定 **same_forward_unmodified_model_output**。父代不能冒用该标签或复用旧 witness 作为新输入证明。当前 config guards 也固定 model-output source、rbf_diverse和步内时序（feasible wrapper第13–34行；policy第8539–8585行）。若未来另行批准，需要显式的新操作语义和 parent→mutation→renoise provenance；不能只把张量换进去并宣称旧 gate 全部适用。初始路径、原数值核心、QD评分/分区/选择、Stage和噪声抽样规则应保持，不在本报告修改。

## 最强反驳

1. **重复父代不会被这个确定性势能自动拆开。** 逆距离项的导数含两轨迹之差（clipped helper第81–94行）：相同投影的那一对贡献为0；全部相同且同origin/掩码时总梯度为0。重复组对其他不同轨迹仍可有非零力，但相同副本会得到相同变异，不能据此增加组内独特性。原 `randn_like` 在变异之后才独立加噪（policy第3223–3229行）；当前步内 RBF 看到了噪声/模型已分化的群体，前移后可能失去这一优势。实际父代重复/退化比例本次材料没有，**Unknown**；不得为了保证活跃暗加抖动、换父代或调整保留策略。
2. **可行性只约束变异当刻，且可能没有可移动坐标。** helper只在严格内部坐标允许非零operand，逐粒子取24分量最小FP32 alpha；边界/已有越界坐标保持原值（`qd_feasible_ray_update.py:40–58`）。饱和父代可能梯度为0；全局归一化又可能把固定范数集中到少数剩余坐标。它既不修复已越界父代，也不保证噪声及后续scheduler输出不越界。新增方案不能继承“N27赋值无新增越界”作为最终执行有效性证明。
3. **变异可能被噪声/模型吸收，也可能被放大。** renoise调用的是既有 `scheduler.add_noise(parent, noise, selected_timestep)`；实际系数/σ及 solver细节不在本次读取范围。若写作常见示意式 A_t(parent+δ)+B_tε，也不能据此宣称实际 A_t、δ传递比例已知，更不能用1/σ补偿偷偷再调scale。全部原 forward 接受变异后的 noisy input，最后仍由 `scheduler.step(...).prev_sample` 产生候选（policy第3699–3712、4005行），不是将动作投影到真实可行流形。相同初始seed不等于不同闭环轨迹上的噪声/观测已严格配对。

## 唯一条件性假设与最小反证

**假设：当前父代上的一次受限几何变异，经过原模型的全部截断去噪后，仍能形成有区别的候选行为，而无需直接修改 rollout 的末次预测输出；这可能比当前操作位置更有利于任务。** 前半是传递机制，后半是尚未证实的任务收益；“模型再次处理过”本身不是质量保证。

最小可证伪预测是：在事前冻结的实际 parent 域，变异不是始终零/舍入不变，并且其候选差异不会在原 renoise/denoise 后全部消失。若所有父代更新均为零，则所谓替代机制实际退化为仅移除 rollout RBF；若存在非零更新但有受控证据显示最终影响全部消失，传递假设被否定。合法零梯度应如实计入，不是工程 invalid，也不能靠事后挑非零案例救假设。普通单路径的 parent→final 差异同时含噪声和去噪效应，不能证明变异贡献；严格归因需要预先限定的同输入/同噪声对照，这不在当前权限，且不得偷偷增加模型调用。没有该证据时保持 Unknown，后续匹配任务结果才决定冻结的任务晋级条件；代理距离增大或更平滑都不能替代成功率。

因此本次支持的是**一个明确的新操作轴可以被检验**，不是“已有证据证明应该立即实现”。最缺的一项事实是该操作在真实父代域到最终候选之间的有效传递；重复性、饱和支持和模型吸收是这个缺口的不同原因。若闭轮后仍不能在有限范围内区分这些原因，不应继续追加参数菜单或包装已否定方向。当前13格续跑、原证据与所有冻结条件不变。

## 来源与边界

仅以下10份获准材料，未跟随任何 payload/Stage/张量/保护集引用；纯标准库文本/哈希与限定rg定位，所有处理进程显式2CPU亲和性、2线程环境、CUDA隐藏，均快速结束，未执行生产模块、Torch、测试、模型、API或仿真。CPU文件处理在60秒范围内；唯一新增产物为本报告。执行规格第109–125、137–163行允许有清晰归因的QD/ED接口研究，同时要求保持固定语义、未知反事实诚实标识；本报告不创建任何实验权限。

`R`为本研究统一根目录，`study_worktree`为W；以下SHA对应本次读取字节。

| 相对R路径 | bytes | SHA256 |
|---|---:|---|
| variants/n27_feasible_ray_update/hydra-continuation-v1/root-first-guided-schedule-observation-v1.json | 7097 | `a359fd1fc3ab79677d5ea748bf957d8ec0e6c11bc7146768465e77f301567097` |
| variants/n27_feasible_ray_update/hydra-continuation-v1/task0-root-review-v1.json | 14867 | `04d1e04701b988a9fdace815772f366aa213e9bb7b1d6f7f22f11fd1ccbd1e18` |
| study_worktree/core/rdt_policy_steer.py | 407196 | `768fd9d1072f1f2abc0e3a1f87f764facd69b99e102399c041b73167b6ef00fe` |
| study_worktree/core/qd_feasible_ray_update.py | 2773 | `146163977866af87d2c643b0446be9ebac12f83cf9337d534b736874c623203e` |
| study_worktree/core/qd_feasible_ray_rbf.py | 4858 | `f2494d1a2c55f4899d848d5f7e8af03cc8518cd53749c8875a117c1ff15a3207` |
| study_worktree/core/qd_clean_output_rbf.py | 3556 | `f107f50e45c233e291e5f5799633b0f3005fe54dc0649506dec41a4c02bb789c` |
| study_worktree/core/qd_actuator_clipped_rbf.py | 10438 | `d0a516046f9d9efc8694916a9ff845c8b67868d8d7d2d01381894bcc05b89408` |
| study_worktree/docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-03-p2-rollout-clean-tail-parameter-sweep-report.md | 17791 | `7eeb573ea941d7dbf5467c950d3201d59de2960dbe2c2ca32c0d01293f7cfd8c` |
| study_worktree/docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md | 21913 | `3a45e53d3b40fa0a40c43ad53a34cfbb8c9fe497dc98a5e178e4c1ef016999ef` |
| variants/n27_feasible_ray_update/conditional-outer-loop-review-v1/review-v1.md | 5997 | `bb7073013df11187534a4d206c751b3f543aea03e3523613101c28dcff81baec` |
