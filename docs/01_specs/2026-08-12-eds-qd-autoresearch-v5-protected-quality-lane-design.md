# EDS-QD Autoresearch v5：Protected Quality + Secondary Lane 实验设计

日期：`2026-08-12`

状态：`APPROVED / EXECUTING — protocol-first versioned successor`

授权链：用户明确要求在单个 cycle 结束后继续自主闭环；v4 design已预注册“candidate FAIL后若仍有新task-linked QD证据与合法预算，代理直接创建下一versioned protocol”。父结果commit `9e3d855`，Run040 decision `REJECT_H5_V4_TOP2_RETENTION_FAIL_TRIGGER_OUTER_LOOP`。

唯一目标仍是正式 `libero_object_swap >=5/10`；正式达标立即停止。每层以task success、delta、gained/lost和gap优先，proxy不能覆盖target gate。

## 1. 为什么继续、为什么只改这一点

Run040使下一方向比v4更窄，而不是扩展探索：capacity-one历史重放0 mismatch；`65.10%`候选处于同cell碰撞，reward top-two trajectory direction/shape中位差`0.3617/0.2501`且reward gap仅`0.01270`，secondary lineage可获得`27.81%` sparse slots。Alias和可激活性均成立。

v4唯一失败是naive overall top-two在causal rebin后发生17次quality-retention violation。根因是将quality和secondary放进同一reward排序池，secondary history能够挤掉本应保护的capacity-one lineage。因此不能实现v4 top2，也不能放宽gate；只允许把两个角色结构性分离。

## 2. H5-v5 与唯一候选

假设 `H5-v5`：

> 若每个endpoint-XY cell的quality lane逐步、逐rebin精确复现capacity-one archive，而secondary lane只保留一个不同fingerprint的reward-best替代行为且永远不能修改/驱逐quality lane，则可在完全保留v3 quality/visitation ecology的同时，让被capacity-one丢弃的approach lineage获得固定预算内的后代，提升task success。

唯一候选 `qd_protected_quality_secondary_v1`，algorithm iteration 5：

1. quality lane独立执行当前capacity-one update、tie、causal rebin和visit迁移，必须fixed-input bit/exact identity。
2. 每个有quality的cell至多一个secondary；候选池为映射到该cell的旧secondary、rebin中未成为该cell quality的旧quality、当轮未成为quality的candidate，排除quality fingerprint后按`reward desc, fingerprint asc`取一。
3. rebin后若某cell没有quality，该cell secondary全部丢弃；secondary不能创建额外occupied XY cell或携带visits。
4. dedicated global-quality parent仍来自quality lane。其余15个cell slot counts对同coordinates必须与v3 capacity-one production allocator完全一致。
5. cell内有secondary时，用stateless SHA-256起点在quality/secondary间round-robin；无secondary则全部quality。不得修改global RNG。
6. 两lane parents均走原renoise/rollout；offspring进入下一轮时可通过正常candidate update竞争quality，但old secondary本身不能直接晋升quality。
7. final execution只从quality lane选择现有global reward best；secondary不得直接执行。
8. 仍为16 parents、176 search / 176 QD / 11 score calls；RBF、Stage、guidance、fallback、bounds、anchor count、population、model/reward/VLM调用不变。

禁止lane count/rotation/reward threshold/capacity sweep、overall top2恢复、第三lane、shape heuristic、final secondary selection或其他机制叠加。

## 3. Run041 零-episode protected-lane replay

先另立protocol，复用Run040冻结的24条只读traces（不读取outcome/success），实现前不改core/config。

PASS：capacity-one quality/rebin/visits精确mismatch0；protected lane相对comparator quality fingerprint/reward/occupied cells/visits/allocation cell counts在全部264 streams/240 allocations精确一致；quality/global-best retention violation0；capacity/duplicate/RNG/accounting violation0；至少20%的sparse slots实际选择secondary；coverage retention1.0；Run040 collision/top2证据精确复现；双run byte identity、secret/write clean。

FAIL则拒绝H5-v5并按全局no-progress/预算规则决定是否终止。PASS只授权单独implementation protocol，随后TDD、CPU integrated mechanism、online promotion逐级进行。

## 4. Fresh evaluation isolation

Task排序为`SHA256("eds-qd-autoresearch-v5|<split>|task-select=<task>")`；seed为`SHA256("eds-qd-autoresearch-v5|<split>|task=<task>")`前8 bytes mod 1,000,000，均与v1-v4/formal不重叠。

- Mechanism：tasks `[7,5]`，seeds `[87603,666847]`，paired4 cells；candidate不得低于control或丢control success，secondary须真实激活，全部机制/安全/延迟门PASS。
- Dev-A：排除mechanism后tasks `[8,0,4]`，seeds `[722809,356933,33067]`，paired6 cells；candidate `>=2/3`、至少`+1`、lost空集。
- Validation：tasks0..9，seeds `[148392,894439,929693,934684,186167,100751,365645,543533,256271,426125]`，paired20 cells；candidate `>=5/10`、不低于control、lost空集。
- Formal：仅validation PASS后使用reuse-limited tasks0..9/seeds `[44,235,43,546,6,621,197,87,151,548]`，paired20 cells；candidate `>=5/10`且全部硬门PASS后立即冻结。

## 5. 预算、连续性与边界

起点仍为66 effective episodes、90/143 reservations、`5.447063166666667/48` GPUh、formal0。最大scientific cells仍4+6+20+20=50，最坏140/143，保留3 exact-cell recovery slots；不提高cap。

若v5离线或任一valid split失败，立即结果commit与outer-loop。由于v3没有跨task target gain、v4离线淘汰，v5若也没有任何task-level gain且无新的非重复QD证据，则触发`CONCLUDE_NO_ADOPTION_WITHIN_GLOBAL_BUDGET`；不得再生成第六candidate。反之只在formal成功、预算硬边界、用户暂停或外部不可修复blocker时停止。

Git/write/GPU/credential/受保护未跟踪文件规则完全继承v4：所有修改只在当前worktree/branch；大型产物只在owned root；GPU0-7需fresh admission且不共享/抢占；credential仅child env；统一总账append-only；受保护Stage-guidance design不读、不改、不stage。
