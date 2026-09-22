N1 方法与负结果记录（2026-09-22；只读核对 source `2435f86f601fa97070f6697670b29063078e91ac`）

**研究结论：TARGET_NOT_MET；N1 算法效果：Unknown；最佳有效候选：无。** N1 完成了预注册、实现及 CPU 检查，但没有进入在线候选评估，也没有通过 Dev、Validation 或 Formal 晋级；它不是正式成功版本。修订协议要求先完成同条件 Q0×10 与 C0/P2×10 的 20 个有效对照，再执行 N1×10，整个 N1 Dev 队列最多 30 次尝试，失败和中止均计数。现有有效对照与尝试约束不能支持晋级，不能换名、补分母或放宽门槛。独立有界复查未找到证据足够的新 N2 机制，因此按用户要求收尾；这不构成“N1 已测得劣于 Q0/P2”的结论。[用户收尾规则](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md:163)、[交付规则](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md:259)、[对照前置修订](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/startup-repair-amendment.md)。

**唯一候选机制。** N1 在 Q0 的 4×4、每格一个精英档案中，把 `target_relative_endpoint_xy` 换为 `target_distance_gripper_duty_v1`：第一轴是第 8 个实际执行动作对应的投影末端位置到当前可见 keypoint0 的三维欧氏距离（米）；第二轴是这 8 个已解码夹爪指令中 +1 的比例。部署解码为原始 action128 槽 10 小于零取 −1，否则取 +1，零也取 +1；它是正指令占比，不是抓取状态、闭合概率或成功概率。投影只使用当前观测及运动学近似，不是模拟器反事实轨迹；不读取任务 ID、种子标签、隐藏状态或未来观测。该改变有意合并方位方向并压缩夹爪时序，可能引入新的行为混叠。[预注册](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/protocol.md)、[候选配置](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/configs/qd_ed_final/candidate_n1.json)、[描述符与边界实现](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/qd_ed.py:74)。

以下伪代码概括已实现、但未在线评估的 N1；质量函数、ED 扰动/去噪及最终动作解码沿用 Q0。质量是既有 guidance 函数在既有 EDS 轨迹切片上的奖励之和，越大越好，内部 cost = −reward；描述符距离并不另加为奖励。无 guidance 时既有评分返回零，不构造替代奖励。N1 没有额外质量锚点、次级档案、动态扩边、退化回退或跨 chunk 记忆。[质量及搜索接入](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/rdt_policy_steer.py:1733)、[档案与分配](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/qd_ed.py:347)。

```text
每个新的 guided chunk：
  A = 空档案；visits[16] = 0；P = 原 Q0 RBF 多样性初始去噪得到 16 个候选
  D(a) = (||project(a)[t8] - keypoint0||₂, mean(decode(a)[0:8, gripper] > 0))
  从初始 P 冻结径向边界：.05/.95 分位数，各侧扩 .1×原跨度；
    扩后跨度不足 .08 m 时以中位数为中心取 .08 m；占比边界固定 [0,1]
  cell(a) = 各轴归一化后 floor(4×值)，截断至 [0,3]；边界本 chunk 不再变
  UPDATE(P)：
    检查候选、描述符和质量均 finite；每个候选所在格 visits 加 1（含被拒者）
    每格在本批候选与原精英中保留最高 reward；相等取较小 action SHA256
    指纹 = 连续、小端 float32 原候选动作字节的 SHA256
    空格插入；更优者替换；其余拒绝；插入+替换+拒绝 = 本批候选数
  UPDATE(P)
  对 i = 0..9：
    已占格权重 w[c] = 1/(visits[c]+1)
    16*w/sum(w) 先取 floor，再按小数余数分完剩余父代名额
    余数相等用由 run_seed/episode/global_step/i 派生的局部 RNG 排序
    按名额复制格精英，恰好 16 个父代；不直接携带未扰动精英到 offspring
    t = linspace(3,1,10).astype(int)[i]
    offspring = 原 Q0 加噪(t) → 原 RBF 多样性截断去噪(t) → 原 action mask
    用原质量评分；UPDATE(offspring)；旧精英仍可保存在 A
  final = 全档案最高 reward；同分按指纹、再按 cell 排序
  原解码与缓存执行固定 8 个动作；下一新 chunk 重建档案和边界
episode reset：沿用原 reset，清动作缓存、chunk memory、观测处理状态和计算计数
stage reset：沿用原 reset_stage，清 chunk memory/stage reward，不清 episode 计算计数
```

因此每个完整 guided 搜索为初始 16 加 10×16，即 **176 个候选、11 个搜索评分批次**，档案最多 16 个精英，每轮恰好 16 个父代。此数目不代表总 DiT、编码器或 reward 成本；既有定性记录与预检查可产生额外评分，实际成本须取调用计数。初始/滚动 RBF 多样性配置分别沿用 scale 20、start ratio .8/.6；没有通过调整 ED、奖励或预算叠加第二个算法变化。[主搜索循环](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/rdt_policy_steer.py:4695)、[最终选择](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/rdt_policy_steer.py:6414)、[重置](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/core/rdt_policy_steer.py:1349)。

**已有 CPU 证据及限制。** 本收尾没有重跑测试；引用实施时记录的 417 项 QD/RDT/可视化测试通过，及随后 2 项定向计算计数测试通过（覆盖有重叠，不能相加为 419 个独立测试）。覆盖包括 t8 与 t7 的区分、完整三维距离、含零的 8 指令解码、边界单位及稳定性、16 父代/最多 16 精英、176/11、全局最优指纹、重置隔离及真实调用计数。这是当时 stub/CPU 路径的实现证据，不是当前 HEAD 的完整在线验证。[原测试记录及源码指纹](/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/experiments/iteration_001_execution_intent/analysis.md)。

固定候选池历史回放覆盖 20 条 Q0 trace、220 批、3,520 个候选出现次，保持 proposals/rewards 不变。Q0 精英奖励及最终指纹可精确复现，夹爪指令占比精确；历史缺失 t8Z，N1 径向分桶使用明确标记的近似重建。因此 N1 生存/父代/混叠统计只是描述性近似：82 个夹爪不一致的淘汰出现次中，27 个立即保留、25 个在下一轮获得父代名额；同时档案占格中位数由 16 降为 4，新增同格候选对 7,814 个。73/82 对被占比分桶区分不等于救回 73 个有用动作。固定池全局最高奖励保持 220/220，也不能证明新父代产生的后代质量或任务收益，因为回放没有生成这些后代。[回放证据](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/iteration_001_execution_intent/fixed-pool-replay.json)，SHA256 `4e0d834b6dca576ce687afc422d41dc0ac02c4abd249dc60a4d40ef241cbe19c`。

原始 baseline、修订后 Q0、P2/C0 对照、N1 候选及基础设施健康检查分别报告，不能合并分母或互相补样。原 baseline 的无效失败及未派发格保持原记录；历史 Q0 的 2/10 不能替代本研究的同条件有效对照。GPU 渲染、模型 B1 和零动作诊断不属于 N1 成功率样本；最新 native-resource 诊断甚至在模型加载前因严格图像哈希不一致停止，也不能证明或否定 N1 机制。当前不能声称 N1 提升成功率、抓取能力、空间覆盖、计算效率或鲁棒性，不能报告统计优势，也不能推荐正式采用。继续研究至少需要一个满足既定数值/图像身份与资源门控的完整执行条件，以及有前瞻协议和合法预算的配对对照/候选队列；不能据本负结果记录自动重开或放宽原队列。
