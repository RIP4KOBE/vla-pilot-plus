# N26 条件验证静态设计

**结论：可做受限的评估接入；本交付只有设计，没有实现或运行授权。** N26 是否晋级尚未知。本设计读取清单内的静态源码，不读取真实 Dev、历史证明、状态、账本或保护集。N25 的原始 INVALID 和接续科学淘汰只保留为 N26 来源链，均不能替代 N26 自身的完整晋级。

设计依据是本目录 `root-static-design-protocol-v1.md`（SHA256 `11d902d99ca3f504c7e1d3da90eeda4ea2e72beb51aa38d8e7f21f276a8d1c66`）。24 个静态输入的绝对路径、完整 commit 和 SHA 见 `static-source-inventory-v1.json`；本轮未执行 import、测试或任何实际证据验证。以下行号分别属于 N26 `6026794cd5d52f3a5054bf2704ebb3c516f9f47e`、N25 验证 `79caa4b6f8a3cc67a379b8da510dc9ab745b4c14`。

## 1. 硬入口和不变的评估

新验证入口仅接受独立 root 终态审查确认的 **N26 全 40 格有效晋级**：C0/Q0/N25/N26 各 10 格，N26 ≥5 且不低于三个对照；实质 QD/ED、原生审计、同轮计算/运行时/提供方契约全部通过。现有 `qd_ed_n26_report.analyze` 第40行起定义完整矩阵和数值门，第83行起的 writer 将 status/journal 不一致强制记为 INVALID。新入口必须复核这两层，不能只读 promoted 布尔值；所有无效、未完成、数值淘汰、完整失败、缺审查都关闭。

晋级后才按身份/曝光元数据选第一个完全未使用的 c1..c4：每个 cohort 为两个不同的 10-task block，顺序 b1/b2 → task0..9 → C0/Q0/N26，共60格、各20。复用旧验证 identity 第51/79行的选择/排序语义；检查实际 env seed、policy seed、init 行/文件与 BDDL 身份，不凭 seed 名称宣称新布局。任何已预约/派发或历史曝光使相应 cohort 不可选；不读结果来选 cohort。freeze、release、每格 admission 重查；开始后仅允许本 cohort 已登记的合法前缀，禁止更换 cohort、重启和替代。

全部60有效、N26≥10/20且≥C0/Q0，并有实质 QD/ED，才验证晋级。**没有验证数值提前淘汰。** 最多62次，最多两次原分类器允许的 sole-Codex-timeout 恢复，每格最多一次、第一有效结果；有效任务失败不重跑，恢复再失败立即关闭。1800秒整 worker +40秒清理、单 GPU7、当前 Codex managed login、原 E2/180秒 Stage、无 Poe 回退不变。formal 保持关闭；验证通过也不是整体目标已完成。

## 2. 最小源码差异提案

基于实际已冻结、最终审查通过的 N26 Dev **6026794 /315文件**建立新隔离分支。若在线工程导致该来源改变，本设计不能自行接受任意新 HEAD，须重新审查来源边界。不合并旧79验证分支；以它为源码参考新增 N26 模块。

| 新模块 `scripts/qd_ed_n26_validation_*.py` | 复用结构及必要变化 |
|---|---|
| bridge | 79的 `verify_delta/source_record`（第70/89行）；将全部315 Dev字节绑定到新评估源，精确反向还原两个共享文件，其余313文件逐字不变。 |
| contract | 79的 `dev_promotion/validate_contract/validate_worker_context/full_capacity/protected_budget/admission`；替换为 N26 四臂 Dev 证据、三臂验证及独立 authority，禁止调用旧 Dev 的 current-HEAD 准入。 |
| evidence | 79的 `historical_backend/historical_receipt`（第14/73行）只作结构参考；新增下述历史315源、36-case证明、元数据审查及持续匹配检查。 |
| identity | 保留首次完全未曝光选择、全部身份去重和 journal-first 曝光登记；只对保留的身份字段操作，保护结果不得成为选择输入。 |
| recovery | 79的 `check_cell_history/create_eligibility/verify_eligibility/selected_terminal/accepted_cell`；调用不变的 N26/原 E2 分类和 profile-bound native 检查；没有接续工程异常的恢复权限。 |
| prepare / supervise | 复用单行 `run_plan`、一次冻结和锁/设备/费用流程；保持原始 Hydra 参数，先创建固定 controller 目录再开锁。 |
| report | 保存完整60格分母、全部尝试/费用和保护明细，只向迭代层输出 aggregate disposition。 |
| terminal | 新增独立既有终态审阅入口：不覆盖 result，不以再次调用同一 writer 冒充独立审查。 |

只提议修改两个既有文件；所有核心、profile、native/reference、common/continuation/Dev controller 均保持原字节：

* `qd_ed_final_runner.py`：新增 `is_n26_validation_plan`；在 `is_n26_plan/is_n25_plan/is_n7_plan/is_n23_plan/is_n23_v2_plan` 排除该明确 marker；扩展 `metered_plan/typed_metered_plan/metered_support`，以及 `validate_plan` 原有两个 E2/runtime 条件；在 `check_budget/check_retry` 增加专属 validation 路由；在 `append_event_locked` 增加身份曝光登记；`run_plan/reconcile_ledger` **仅**增加明确的 validation dispatched label。与79 routing addendum采用同一有限模式，保留602中的6f/N26原路由。
* `qd_ed_n23_worker.validate_context`：仅增加显式验证路由，置于旧 Dev/continuation 路由前，由新 contract 拒绝矛盾 marker、错误阶段/臂/来源。其余函数特别是 `run_worker/verify_receipt` 逐字不变。原第209/226/320行根据 `n26_cohort` 调用 N26 审计，因此新 plan 必须保留精确 worker-audit marker，同时以 `n26_validation` 指向新评估入口。不能删除全部 N26 markers 后退化到旧路径。

不修改 `build_command/episode_identity/validate_outcome`、锁、子进程、清理、计时或原恢复 helper；如果实现发现必须修改，先报告新的具体差异。无生产函数复制、globals 替换或 monkeypatch。新模块、协议/反向桥记录、定向 tests/fixtures/guard 是可新增范围；没有模型、科学或新 GPU proof 模块。

## 3. 证明与源码桥的两个兼容边界

**历史来源不能等同评估 HEAD。** N26 `backend.verify_proof` 第136行调用 `validate_plan`，后者第47行调用 `verify_source`；`bridge.build/verify_reverse` 第21/54行也要求当前315源码形状。验证源码加入路由后直接复用这些入口会正确拒绝。新增 evidence 模块应绑定原 Dev plan/source manifest、602 Git字节、原 source bridge/final review/authority、原 runtime、同源36-case proof 的 plan/report/process/terminal及原 health 结账。可复用字节未变的 `backend.validate_report/settled_proof`（第78/119行）的 JSON/计账检查，不能调用其 current-source admission/run 或新预检。绑定其传递使用的 contract/reference/audit-backend 模块路径和字节，拒绝 shadow import。

新桥先逐字还原 validation→602，再保存602→c09/8fd、6f行政接续及ff共同证据的历史桥引用。证明仍写原 commit、原进程/boot、原账本成本；不得标成新验证来源生成。新验证 worker 在原 metered process 内执行原审计：C0/Q0 的 arithmetic backend 是 CPU，N26 是分配的 CUDA，三臂 worker 都占原 GPU7。原模型输入、sample-only门、FP32/BF16/layout数学、bounded witness、zero-gradient合法性和176/11均不变。

**历史证据审查不是张量重放。** 79的 `historical_receipt` 调用 `w.evidence_record(output)`，不能照搬为新历史入口。建议 root 在原 Dev 源尚未改变且终态已闭合时，形成有限的 JSON-only 输入清单与独立 promotion seal：全部40有效格的 context/receipt/report/process/terminal、所有 primary/recovery成本、指标/compute元数据、Dev-only journal和root审查；检查 receipt 中 evidence.files 的规范元数据 digest，**不跟随 tensor refs**。明确依赖原同进程原生审计及 root 完整性证明，不能称重新数值审计。历史 eligibility 中可能链接 Stage/图像等证据时同样不自动跟随；保留 root 对原冻结分类器及有限恢复谱系的核验引用。实际数量/字节上限由后续实施协议依据固定40+≤2上界冻结，本设计不授权读取。

`qd_ed_n26_logical.current_matching` 第75行的持续匹配语义必须保留：原N25两个 Dev cohorts和原资源的 root-attested projection，对比正常 runner 已读取、由调用者过滤的当前 matching events；不永久钉死整个私有账本的SHA。新增历史适配器复用共同层的纯比较入口，不让旧 `common.build` 或整个 Dev current-HEAD 验证器冒充新评估来源。再独立比较 **N26 Dev** 的完整终态事件及36-case资源组；任何后追加匹配预约、未结账或成本变化均拒绝。release创建、freeze、launch、每格admission均必须实际到达该检查；无时间戳代替当前比较。旧proof及current-matching依赖的元数据提取完整性信任要明示。

## 4. 有限 authority、终态与禁用模板

不把79的494固定上限复制成“现在有额度”。读取并绑定 root 最终实际采用的有限预算文档和状态：100 GPU小时不增、validation/formal/recovery桶及保护储备不转移；启动前必须容纳全部剩余60 primaries+2 recovery名额。冻结本地小时上限 L≤32，且 L 连同剩余formal保护小时可容纳；每格保证已花费+1840秒≤L并满足累计约束。所有失败、原资源/历史/新成本保留。若无法容纳完整名额或下一格时间，关闭为未完成/无效，不能写科学 REJECT 或借formal额度。本设计不采用预算。

controller/result固定归属 `N26/validation-execution`；attempt 数据仍由冻结 artifact_root/attempts 管理，二者不作父子假设。创建该 controller 目录后才能开 supervisor.lock；root import helper 要保留 scripts/ 的合法模块路径。根的独立 terminal reader 在 controller已退出、原锁及进程身份复核后运行，检查唯一attempt IDs、所有已dispatch进程/cleanup（含最后invalid）、reserved但未dispatch的明确无进程状态、所有费用、精确60格前缀与状态一致性。status失败而账本有额外合法结果时保存两份前缀和费用并 INVALID；不自动恢复、不虚构0/20。细节最终保存在保护报告，CLI/root迭代接口只有聚合结论。

后续模板一律 `executable=false`、所有实际ref/seed/cap留未解析，不能被live schema接收；本轮仅定义，不生成release：

| 提议 schema | 必要绑定 |
|---|---|
| `n26-dev-promotion-review-v1` | root独立终态审查ref、Dev plan/status/result/315-source/journal refs、40格counts、原proof/bridge/runtime、允许validation；只能精确完整晋级。 |
| `n26-validation-source-review-v1` | 新完整source、602逆桥、静态协议、原Dev来源/proof、runtime；本身无execution release。 |
| `n26-validation-authority-v1` | promotion/source review、cohort/seed selection、实际finite budget authority/caps、L/60/62/2/1800+40/GPU7、validation=true、formal=false，另需真实state引用。 |
| `n26-protected-validation-v1` plan marker | 精确60 rows、原C0/Q0/N26 profiles/runtime/input指纹、新source、原native marker及上述全部ref；冻结一次。 |
| `n26-validation-execution-release-v1` | plan/source/cohort/ordered keys、seed/freshness、authority、GPU UUID、limits；当前matching/capacity复核。 |
| `n26-validation-root-terminal-review-v1` | 已存在的detail/aggregate/status/journal/source/reader/process refs、独立重建的aggregate disposition与费用核对；不是writer重跑。 |

N26的实际root Dev review字段以未来冻结reader为准；现 `qd_ed_n26_report.py` 只有 result writer，没有该独立reader，不能捏造已存在的 accepted/source_commit 顶层字段。实施时冻结明确root review schema并逐ref对应实际writer的 `n26-dev-cohort-result-v1`、status.content和controller_evidence；任何接口差异须先审查，不能跳过root审查。

## 5. 后续只需定向合成检查

1. 全315-source逆桥、313原文件不变、worker其它函数原字节；旧602路由行为不变；矛盾/missing marker、shadow helper、plan/profile漂移失败。
2. 真正40格晋级与39格、错对照、零实质QD/ED、INVALID/REJECT/futility、状态不一致负控；原schema的ref、symlink同文件关系、全部attempt唯一且成本完整。
3. 历史36-case proof正确来源/结账及负控；不得重标新commit、漏health成本、把12-case旧证明代替36-case；当前匹配hook覆盖全部入口，后来无关cohort不误拒绝。
4. metadata-only首次未曝光cohort、跨block/init重复、release期间新增曝光、全部已用及曝光登记失败关闭；不读取protected outcome作选择。
5. 60/62/2/每格1恢复与first-valid、时间/名额/formal储备、未采用authority、错误GPU/并行worker拒绝；新invalid不得成为通用重试权限。
6. 真实N26 metric/receipt schema，零guided缺metrics仅原三方一致条件允许，删全markers拒绝，zero-gradient合法，C0/Q0 CPU审计与N26 CUDA审计身份区别。
7. 分离controller/attempt根、路径逃逸、目录预创建、terminal已写但status后处理失败、invalid最后进程清理；保护detail保存而聚合输出不泄露逐任务结果。

上述为待批准实施的测试提案；继承数学/模型大套件不无故重跑。本轮没有任何测试结果或验证性能结论。

