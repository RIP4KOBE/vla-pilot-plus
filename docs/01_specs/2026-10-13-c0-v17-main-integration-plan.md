**VLA-Pilot++：C0 / Codex V17 合入主分支的整合方案（审阅稿 v1，2026-10-13）**

本方案交付一个可从主分支安装、配置、运行和审计的 C0 / Codex V17 baseline，供团队在同一条件下开展后续算法研究。本轮仅完成仓库核查、方案与来源清单，没有创建集成分支、修改运行代码、合并主分支、运行测试或调用 GPU/API。

推荐以 V17 冻结实现为整合来源，以当前 main 为目标基础。迁移保留完整 V17 科学行为，先把依赖、入口和配置做成可移植形式，再验证迁移。历史 P2 的 4/10 单独归档，不将两个版本拼接后沿用历史成绩。

**一、交付目标与 baseline 身份**

| 项目 | 方案约定 |
| --- | --- |
| 团队主线 baseline ID | 建议 `c0_codex_v17`，明确版本，不使用会漂移的 `best` |
| 算法 | RDT + ED + absolute-EEF RBF + V17 Stage controller；QD archive OFF |
| 已有成绩 | 2026-09-30 单次完整在线十任务 3/10，task 3/8/9 |
| 合入后的成绩 | 使用新入口重新测量、单独记录，不直接继承旧数字 |
| 历史最高记录 | `historical/p2_abs_rbf_gemini_20260805_control_4of10`；旧 Gemini、旧 reward cache、另一轮实验 |
| 主分支默认行为 | 保留原有 PI05 / guidance=false 等默认配置；V17 通过显式 profile 选择 |
| provider | Stage、身份描述、reward 生成均走当前账号的 Codex CLI；不启用 Poe 回退 |
| 新算法研究 | 从发布后的 main / baseline tag 分支；本次不引入 N 系列候选或开启 QD |
| 实验管理 | 继续使用现有 .worktrees/exp 归档体系；原结果、原冻结快照保持不变 |

工程完成的定义是：同事在不依赖旧研究 worktree 的干净 checkout 中，通过文档给出的入口与资产清单运行此 profile；源码、配置、模型、任务和初始化身份均可核对，测试和运行审计可独立完成。

科学结论的边界是：V17 是已验收的固定十任务在线诊断 baseline，不是已经达到 ≥5/10 的最终 QD/ED 方法，也不是历史 Gemini 4/10 的严格复现。迁移保持评分7点/执行8步、原 softmax 倍率、线性末端投影等已有行为；任何修正另立实验。

**二、当前事实与整合来源**

| 对象 | 当前状态 |
| --- | --- |
| main | `d51cb85f485502e0429c79529872efef2ec59981` |
| 历史 P2 branch | `exp/eds-init-pg-diverse-sampling`，HEAD `b3db98cf4fd98a6479d92683e33ebe3d032f25d9` |
| V17 branch | `exp/rdt-qd-ed-gpu6-20260922T063626Z`，HEAD `77761b4cda78ac3b6762a6aa60f97b07fde7c1dc` |
| 祖先关系 | main 是 P2 的祖先，P2 是 V17 HEAD 的祖先 |
| V17 相对 main | 217 个提交，2,823 个文件变化，约515万新增行；大部分行来自第三方资产 |
| V17 冻结来源 | 48 个文件；本次逐个校验冻结副本、当前工作副本与 accepted SHA，全数匹配 |
| 48 文件的 Git 状态 | 37 个 untracked、5 个已跟踪但有修改、6 个已跟踪且无修改 |
| 额外测试状态 | 31 个未跟踪测试文件、3 个已修改测试文件 |
| main 工作区 | 有5个未跟踪文档，应在未来操作中原样保留 |

V17 实际 worktree：
[打开 V17](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree)

验收来源：
[accepted-setting.json](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/accepted-setting.json)
 · [resolved-config.yaml](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/resolved-config.yaml)
 · [48 文件来源清单](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/docs/01_specs/2026-10-13-c0-v17-source-inventory.csv)

来源清单只枚举验收时冻结的48文件，**不代表完整运行依赖闭包**。新入口还需要基础配置、公共模块、第三方环境和模型。直接 git merge 会漏未提交修改；只复制48文件也不能得到可独立运行版本。

**三、代码与文件的整合范围**

以下均为拟在集成分支中的处理，不改变原验收快照。

| 分组 | 主要现有文件 | 处理方式与验收重点 |
| --- | --- | --- |
| 策略与环境 | `main.py`、`core/rdt_policy_steer.py`、`core/env_adapters/libero_adapter.py`、`core/rdt_libero_action_converter.py`、`core/rdt_libero_obs_processor.py` | 从 V17 提取其运行需要的行为；保留原生动作、观测时序、8步执行、ED/RBF 搜索，不做算法重写 |
| 数值 reward | `core/c0_reward_contract.py`、`utils/guidance_utils.py` | 保留生成后数值验证、Stage2常数零、reward/reference与引导开关一致性 |
| Codex 接入 | `core/codex_stage.py`、`core/codex_stage_policy.py`、`core/codex_vision.py`、`core/gemini_grounder.py`、`vlm_query/vlm_agent.py` | 保留 Stage、身份、reward 三条调用链及完整回复审计；不只迁移 Stage 客户端 |
| Stage 证据 | `core/stage_evidence.py`、`stage_observation.py`、`stage_observation_json.py`、`stage_response_validation.py`、`stage_identity_memory.py`、`stage_target_marker.py` | 保留视觉事实、unknown语义、目标标记和查询调度 |
| 接触、携带、恢复 | `core/stage_contact_handoff.py`、`stage_grasp_guard.py`、`stage_robot_evidence.py`、`stage_release_guard.py`、`stage_carry_hold.py`、`stage_fused_carry_hold.py`、`stage_failed_contact_recheck.py` | 保留完整状态依赖；动作guard关闭不等于可删除其模块 |
| 初始化 | `core/episode_rng_fixture.py`、`core/episode_rng_hooks.py`、`scripts/stage_rng_fixture_worker.py` | 保留任务准备和rollout开始两个恢复点、顺序、状态签名与CUDA随机流检查 |
| 提示词与配置 | `configs/stage_controller/*`、`vlm_query/c0_contract_v1/*`、`vlm_query/stage_observation_v1.txt`、基础Hydra配置和全局stage模板 | profile显式选择冻结模板；保留旧策略仍用到的全局模板 |
| ED 公共依赖 | `core/eds_eval_metrics.py`、`core/eds_mechanism_trace.py`、`core/qd_ed.py`、`core/fkd_class.py` 等 | 即使QD关闭，导入与observer仍可能需要；先保留依赖，不在此次整合中拆除未启用分支 |
| 感知与公共工具 | keypoint detector/tracker、policy observation sampling、adapter基类、SAM工厂、可视化与logging工具、`patches/light.py` | 按import与实际路径补齐；校验可选后端不因新依赖而无法导入 |
| 运行与审计 | Codex runtime、Stage worker、Codex审计、深度审计、ED记录 | 抽取不依赖旧study的运行与审计入口；原脚本和原快照留在研究归档 |

五个已跟踪但未提交的冻结运行文件是 `main.py`、`core/codex_stage.py`、`core/codex_stage_policy.py`、`core/gemini_grounder.py`、`vlm_query/vlm_agent.py`，必须进入来源映射和代码审查。

不将 N1–N36 的研究队列、未验收候选、私有资源调度、历史恢复规则作为主线运行入口。也不把整个 `research-state.yaml`、研究账本、旧锁文件、凭据或大批历史输出作为新程序的隐式依赖。与实际运行有关的场景资产和初始化数据按依赖处理，不能因为文件大就排除。

**四、必须先解决的隐式启动依赖**

当前调用关系包括：

```text
stage_closed_loop_run
  ├─ c0_trace_replay → c0_codex_repro
  ├─ c0_poe_online_retest → c0_poe_online_preflight → c0_current_trace_replay
  └─ c0_poe_fresh_retest

codex_only_runtime.worker_environment
  └─ c0_trace_replay.process_env

stage_rng_fixture_worker
  └─ 顶层 import c0_poe_resilient_worker
```

其中部分脚本不在48文件冻结范围内。带poe名称的文件仍承担公共工具或顶层导入；V17通过 `VLA_CODEX_ONLY=1` 跳过Poe transport安装。因此不能按文件名直接删除。

拟采用的迁移顺序：

1. 提取路径解析、JSON读写、时间、seed清单、环境构造等纯公共功能。
2. 新入口显式传入仓库根、资产根、输出根、GPU、profile、fixture，不再从旧manifest派生命令。
3. 保留Codex-only环境构造与验证，同时让Stage和reward两个backend都明确为 `codex_cli`。
4. 保留RNG hook安装时点；首轮迁移优先保留现有hook语义，正式接口化另作小提交并做等价检查。
5. 建立新入口后，切断它对旧Poe runner、旧研究状态和锁的依赖；原研究脚本不重写。
6. 在不暴露旧worktree到Python路径/资产搜索路径的干净环境中检查导入和配置展开。

初次整合尽量保持科学函数不变。若确需修改源码接口，来源清单记录原文件SHA、集成文件SHA、变更原因和对应等价检查；不要求经过路径重构的新文件继续拥有旧SHA。

**五、profile、入口与环境配置设计**

建议新增以下路径；这些是拟交付接口，目前尚不存在：

```text
configs/baseline/c0_codex_v17.yaml
configs/local/baseline.example.yaml
scripts/run_baseline.py
scripts/audit_baseline.py
environments/c0_codex_v17/                 # 独立环境与依赖清单
tests/fixtures/c0_codex_v17/               # 精简离线回归样本
assets/manifests/c0_codex_v17.json         # 模型、场景、fixture身份
docs/baselines/c0_codex_v17.md
docs/baselines/historical_p2_4of10.md
```

profile使用明确的Hydra组合与全局包映射；不能把 `baseline` 下的字段错误嵌套成主程序读不到的新层级。新入口必须有CPU可执行的配置展开模式，输出真正生效的resolved config。

调用接口示意（待实现，非现成可执行命令）：

```text
python scripts/run_baseline.py --profile c0_codex_v17 --resolve-only
python scripts/run_baseline.py --profile c0_codex_v17 --preflight --gpu 2
python scripts/run_baseline.py --profile c0_codex_v17 --gpu 2 --output-root <new-run-directory>
python scripts/audit_baseline.py --run <new-run-directory>
```

默认完整队列为task0–9。子任务选择仅作为明确标记的smoke/debug模式，不产生完整十任务成绩。profile参数覆盖进入新manifest，科学字段变化时标记为派生实验，不能继续混称V17基准运行。

科学配置与机器配置分开：

| 科学条件：必须保持 | 机器条件：允许配置但需记录、验证 |
| --- | --- |
| 模型权重、encoder身份、EMA、5步实际去噪 | 权重文件位置；移动路径须保持内容身份 |
| Stage模型及推理强度、提示词、回复策略 | CLI可执行文件位置、正常账号登录 |
|任务顺序、seed、fixture、720步、8动作chunk | 输出根、日志与捕获目录 |
| ED/RBF/Stage全部生效参数 | 物理GPU选择及UUID；首次迁移验证仍GPU2 |
| 当前视觉输入、目标标记、fresh reward/identity | EGL设备映射、LIBERO本地路径、显存配置 |
| RNG恢复时点及continuous模式 | Python解释器位置；包版本另按环境清单核验 |

允许变化的机器字段不是“自动等价”：模型移动要核对hash，GPU/EGL映射要做启动检查，包版本不同应单独标明环境变更。新manifest保存原验收manifest引用和SHA，以及迁移后的有效配置；原manifest不改写。

新入口将默认拒绝缺失fixture、不同权重、零语言embedding、provider混用、输出目录覆盖等会使baseline身份失真的情况。首次GPU验证继续使用GPU2单worker；设备忙则报告/排队，不终止同事进程。

**六、冻结的关键算法与在线条件**

以下是便于审阅的关键字段；实际以完整resolved config语义对比为准，而非只核对本表。

| 项目 | 保留值 |
| --- | --- |
| 任务 | libero_object_swap，0–9，init states，等待5步，严格扰动，720动作 |
| seeds | 44、235、43、546、6、621、197、87、151、548 |
| RDT | Object EMA，64步输出，执行8步，20Hz；checkpoint提供5步推理 |
| ED | population16、10轮、use_cem=false、legacy_temperature=0.1 |
| 父代/最终选择 | softmax(0.1×reward)、无精英携带、只选末轮最佳 |
| 初始RBF | absolute_eef，scale20，ratio0.8 |
| 短去噪RBF | absolute_eef，scale20，ratio0.6，所有轮，无额外clean tail |
| 短去噪序列 | [3,2,2,2,2,1,1,1,1,1] |
| QD | archive none，observer true，不启用archive选择 |
| reward | 每任务fresh c0_xyz_v1；Stage1距离reward、Stage2常0；本地数值计算 |
| Stage | proprio_v4；部分遮挡held、physical/fused carry、失败接触复查启用 |
| 引导一致性 | stage-entry reference；同阶段guidance开关不重置；纯proximity交接关闭 |
| 动作 | grasp_action_guard_enabled=false；无外部7D动作覆盖 |
| Codex | gpt-6-astra / low；Stage与vlm_agent均codex_cli；ChatGPT托管登录 |
| 接入校验 | timeout180秒、transport_retry_count1、completed_transport_cycles_v6 |
| 查询 | 最小16步、常规32步、不确定16步；每任务最多50次 |
| 初始化 | historical_fixture_v1；episode_policy_rng_mode=continuous；20次规定恢复 |
| 在线性 | cached_functions_dir/root为空；不用保存的Stage回复，不调用Poe |

V17配置里部分字段仍名为gemini/poe或旧method_label，不按名字判断实际provider。迁移可以增加解释性profile名称，但不在同一提交重命名整套配置键。

同事使用自己的正常Codex登录，主线不携带账号凭据。CLI版本与调用合同进入运行记录；本次未重新验证10月13日在线服务可用性，后续preflight会验证。模型名相同也不承诺在线回复与9月30日逐字相同。

**七、依赖、模型与场景资产迁移**

| 依赖 | 核验到的身份/问题 | 推荐处理 |
| --- | --- | --- |
| LIBERO-PRO | P2/V17普通tracked tree：`91576c5720b4b4cd1de45896c11d535772f191a0`；2409文件约656MiB | 第一版优先保留准确vendor内容；修正.gitmodules不一致。若采用外部包，必须有固定内容清单和安装校验 |
| main的LIBERO-PRO | .gitmodules有声明，HEAD没有对应gitlink/tree | 将实际依赖补齐，不能以“已有子模块声明”判定完成 |
| RDT源码 | submodule `b896f4dcac8ed1c3fae4a056200db267607f131f` | 保留固定版本，校验实际import来源 |
| LeRobot / CALVIN | 现有固定版本及旧editable路径依赖 | 保留主线兼容；消除指向其他研究WT的editable安装依赖 |
| RDT EMA权重 | 约2.46GB；SHA `b4e3631db326689297cd2f0b02d32ade9dc6ee9ae09c03171add64b80e86aaa1` | 外部资产清单与校验；同时固定config.json |
| T5 snapshot | `3db67ab1af984cf10548a73467f0e5bca2aaaeb2` | 指定准确snapshot及tokenizer/config，不按cache目录mtime选最新 |
| SigLIP snapshot | `9fdffc58afc957d1a03a25b10dba0329ab15c2a3` | 固定processor/config和权重身份 |
| DINOv2 vitb14 | 权重SHA `0b8b82f85de91b424aded121c7e1dcc2b7bc6d0adeea651bf73a13307fad8c73` | 固定torch hub源码和权重，不能只保留.pth |
| RNG | 20个.pt，共294436B，已逐个校验 | 可版本化为小型固定输入包，保留来源与hash |
| 训练数据 | 本次评测不使用 | 不作为baseline安装前提 |

现有LIBERO配置会间接指向另一个历史WT的assets/BDDL/init文件。新入口必须为当前checkout生成自己的LIBERO路径配置；核验10个任务的BDDL、pruned_init与实际使用的init row身份，不复用旧绝对路径。

20个RNG文件的manifest SHA：
`628c429d457def157c9163be94a1202721673f97f1e43aa6446e5a06889c6043`。

内部使用相对路径，可整包搬迁保持manifest字节不变。保留校准audit及来源引用；运行时按task、seed、prepare/rollout阶段和state signature恢复。不能用相同seed替代此包。此fixture来自历史3/10 C0的初始化诊断，不是历史4/10那一轮；其中不包含旧Stage、reward、动作或环境回复。

现有requirements/environment并非V17准确锁文件。核验依据包括Python3.12.12、Torch2.7.1+cu126、TorchVision0.22.1、MuJoCo3.7.0、robosuite1.4.0、NumPy2.2.0、Transformers4.53.3、diffusers0.35.2、Hydra1.3.2、OmegaConf2.3.0。实施时整理为独立环境定义，补足系统EGL、驱动、FFmpeg、完整包依赖及真实module origins；不直接覆盖所有用户的旧环境配置，也不声称以上简表已经足够重建环境。

**八、提交拆分与实施顺序**

建议分支名：`codex/baseline-c0-v17`。使用主仓库已有工作区 `/home/hynx/lizhuo/VLA-Pilot++` 从main创建并切换到集成分支，不新建worktree；V17实验工作区始终留作原实现与冻结证据来源。主仓库目前没有已跟踪文件修改，五个未跟踪文档逐一记录并保留。实施时若工作区已被同事用于其他修改或运行，先完成只读来源准备，协调占用后再切分支，不能覆盖其工作。

集成源码和将来合入的配置/文档在现有主仓库工作区审查；GPU运行结果继续写入原实验目录下新增的 `integration_runs/c0_codex_v17/<run_id>/`，与原accepted run并列分开管理。新run的manifest绑定集成代码所在目录和Git提交，不让输出路径反过来决定import哪个worktree。提交采用明确文件清单，避免把主仓库原有未跟踪文档或实验产物一起加入。

| 步骤/提交 | 具体工作 | 可审阅交付物 | 完成条件 |
| --- | --- | --- | --- |
| P0 来源冻结与范围锁定 | 记录main基点、48文件、额外依赖、环境、资产、旧结果 | integration manifest、完整来源映射 | 所有必需来源可定位；未提交源文件已纳入快照，原件未动 |
| P1 补齐依赖与环境 | LIBERO准确版本、资产manifest、独立环境、路径配置 | 依赖提交和安装文档 | 干净checkout不引用历史WT的代码或场景 |
| P2 引入策略骨干 | RDT/ED/RBF及其公共依赖，保持旧入口兼容 | 核心实现提交 | 主线既有相关测试通过，算法差异有逐项说明 |
| P3 引入V17控制 | Codex三条调用链、Stage/reward/RNG机制和模板 | 控制器提交及相关测试 | 离线关键状态与冻结V17一致 |
| P4 配置与便携入口 | profile、本地路径schema、preflight、新run manifest、审计 | 可独立启动的入口提交 | 配置语义对齐，旧study依赖消除，输出不覆盖 |
| P5 回归样本与文档 | 提取小型fixture，补迁移检查，保留旧结果索引 | 测试和文档提交 | CPU验收通过，缺失fixture不被skip掩盖 |
| P6 GPU迁移验收 | GPU2单worker、完整在线10任务，必要时差异诊断 | 新报告、逐任务结果、审计、视频索引 | 工程有效性与性能各自有明确结论 |
| P7 发布整合 | 汇总diff/验证/限制；在确认最终变更后合入main | 最终可审阅diff、baseline tag、协作说明 | main指向验证过的树；后续同事从该tag起步 |

P2/P3若存在双向导入依赖，可以调整提交边界以保持提交可构建；不能为了漂亮拆分而伪造中间版本可运行。所有移植改动先在集成分支，主分支合入前不承载半成品。

本次范围优先是“行为保持的工程迁移”。大规模模块重写、去掉全部QD遗留、调prompt、修7点切片、改softmax、修milk恢复、优化目标标记等，放到发布后的独立研究变更。

**九、CPU与离线验收清单**

CPU验证不调用模型API，不占GPU。以下是计划中的检查，本轮未执行。

| 检查层 | 具体检查 | 通过标准 |
| --- | --- | --- |
| 来源完整性 | 48文件来源映射、额外依赖闭包、资产/fixture hash | 无缺文件、无身份不明替换 |
| 配置语义 | 展开新profile，与旧resolved config逐项比较 | 仅已登记路径/作业身份等差异；科学字段一致 |
| 干净环境 | import来源、Hydra组合、可选依赖、无旧WT/PYTHONPATH | 安装后仅使用本checkout与明确外部资产 |
| Stage回归 | 已有17文件456项历史检查所覆盖的合同 | 移植后的实际测试全部通过；不把旧456直接当新结果 |
| reward/RNG | 数值合同、无随机污染、20次恢复顺序、状态metadata | 非恒定reward门控正确，错误fixture明确失败 |
| RDT/动作 | 非CEM16×10、RBF两段参数、末轮选择、8动作、原生7D | 用固定输入验证行为，无外部动作覆盖 |
| provider | Stage/identity/reward全部Codex、回复事件验证、错误分类 | 不走Poe、不静默换模型、不吞掉失败 |
| 入口行为 | 新目录、完整10任务顺序、配置冻结、路径可移植 | 不覆盖旧结果、不写其他study账本 |
| 原主线兼容 | PI05/VLS及RDT无引导配置、backend导入、观测处理 | 相关既有测试通过；不宣称未运行的全后端性能已验证 |

历史17个测试文件：

```text
tests/test_stage_failed_contact_recheck.py
tests/test_stage_fused_carry_hold.py
tests/test_stage_partial_visibility.py
tests/test_stage_evidence.py
tests/test_stage_grasp_guard.py
tests/test_stage_robot_evidence.py
tests/test_stage_recovery_priority.py
tests/test_stage_reward_progress_handoff.py
tests/test_stage_reward_reference.py
tests/test_stage_carry_hold.py
tests/test_stage_carry_runtime.py
tests/test_stage_gripper_passthrough.py
tests/test_stage_release_guard.py
tests/test_stage_target_marker_runtime.py
tests/test_codex_online_observation.py
tests/test_codex_stage.py
tests/test_main_rdt_startup.py
```

另外纳入现有reward合同、episode RNG fixture/hooks、observation JSON/response validation、target marker、RDT action converter/obs processor/steer、policy observation sampling、env adapter imports、perturbation parsing等相关测试；只为迁移引入的真实风险补新测试，不为文件改名写镜像测试。

旧测试中有读取V13/V14/V16实验目录和prechange/main.py的依赖。将必要正反例提取为带来源SHA的小型fixture，覆盖orange40→56、cream48→64、butter344→360、BBQ/pudding不误恢复、unknown/held/过期/指宽不足等情况。旧研究分支的legacy测试不自动代表当前main兼容，要对照当前main行为补核验。

离线差异检查将相同观察、机器人状态、reward/reference和已有候选张量输入冻结V17与集成版，比较Stage、ED gate、恢复链、reference reset和动作。离散量须一致；浮点量优先同环境精确比较，若使用容差，需事先给出数值依据并披露，不能为通过测试事后放宽。离线输入回放只证明移植行为，不作为新在线成功率。

**十、GPU与API任务、顺序、时间**

| 顺序 | 执行内容 | 本地GPU | Codex调用 | 结果用途 |
| --- | --- | --- | --- | --- |
| G0 | 单独进程检查当前CLI登录/图像结构化回复 | 不需要 | 少量，计划1–3次探针 | 接入检查；不改变后续worker RNG |
| G1 | GPU2渲染、模型加载、资产/语言编码、RNG hook启动检查 | GPU2单worker | 可保持无在线调用 | 工程smoke；不计为完整任务成功率 |
| G2 | 集成版task0–9完整在线一批 | GPU2单worker | 每任务fresh身份、reward；执行中online Stage | 主要迁移验收，10个主回合 |
| G3 条件触发 | 冻结源实现同期10任务 + 集成版同期10任务 | GPU2串行 | 两组各自fresh在线调用 | 仅在证据需要时隔离源码迁移与provider/环境变化 |

G1必须在独立进程结束后再启动G2；不能因预热或API探针消耗正式worker的随机状态。G2保持规定task顺序、fixture和连续策略RNG，不拆成任意任务拼接统计。

9月30日原V17十任务用时4806.82秒，即1小时20分7秒；325次调用中305次Stage、10次身份、10次reward，累计模型调用耗时3611.95秒。该数据说明时间主要受在线推理影响，不能按纯GPU算力估计。

建议G2排期留2–3小时；G3若触发，额外留4–6小时。这是时间估计，不是到点强杀或放弃队列的条件。保持180秒单调用合同、既有重试与错误记录；会话结束或前端超时不应杀死后台实验。worker需有独立日志、进度文件和明确退出状态，持续输出task/step/Stage/ED状态及最近调用时间。

第一轮预设只有G2的10个主回合，不预设多种算法消融，也不为达3/10反复重跑。G0/G1和所有中止/重试单独留痕。硬件或API故障不作为算法失败混入10个有效结果；合法任务失败不可重试后替换。严格可比的最终队列若必须重开，则另建完整批次，保留旧批次并说明原因。

整体工程排期粗估为1–2个工作日，另加G2约2–3小时；新机器环境修复或条件对照可能延长。此估计基于已发现依赖，不是已完成工作量或承诺截止时间。

**十一、怎样判断“可以合入并作为团队基线”**

分开报告工程有效性和性能，不用一个布尔值掩盖原因。

| 结果 | 判定与后续 |
| --- | --- |
| CPU/离线差异/依赖校验失败 | 移植尚未完成，修复后再进入GPU验收 |
| GPU批次不完整、provider混用、输入身份不符、审计失败 | 不成立为有效迁移结果；保留故障记录并修工程原因 |
| 完整有效且≥3/10，其他合同通过 | 达到建议的团队baseline发布条件；报告本次实际任务成功集合 |
| 完整有效但<3/10，离线迁移一致 | 不直接宣布移植错误，也不宣布性能恢复；先审查新在线判断与首处分叉，必要时G3 |
| 源版同期≥3/10但集成版低，且离线/执行分叉指向迁移 | 优先修移植回归，不修改算法以掩盖差异 |
| 源版与集成版同期都低，且工程合同一致 | 说明当前在线/环境条件下旧成绩未复现；发布为“旧V17实现迁移”需单独说明，暂不打“性能验收”标签 |
| 两组结果不同但无确定归因 | 报告有限样本不确定性，不将10次试验当作统计非劣证明 |

≥3/10是建议的性能发布目标，不是对每次fresh在线调用的保证。success集合不要求必须还是3/8/9；若变化则分析对应轨迹。API调用数、ED块数和总动作数也随轨迹变化，不要求重新恰好325、191、5585；要求记录和行为合同成立。

迁移62项完成审计与59项深审计所表达的合同，重新计算新run结果。不存在的触发事件应清楚区分“未触发”和“实现错误”，不能为了让旧审计通过而制造触发或放宽科学规则。环境success是成绩来源，Stage宣告完成不能替代。

**十二、证据与团队交付**

每次新运行最少保留：

- 基线ID、Git提交/dirty状态、源文件映射、环境与依赖版本、模型/资产hash。
- resolved config、任务/seed/初始化协议、GPU映射、CLI/model/reasoning与实际provider记录。
- 每任务环境结果、动作数、Stage查询/错误数、ED块数、终止原因。
- Stage原始输入/回复、关键点/目标标记、reward/reference、ED gate、原生动作审计所需记录。
- 十任务视频、科学审计、失败分析和与原基线差异；大型内容保留在外部归档，源码仓库提交索引/hash和小型样本。

历史4/10和V17旧3/10各有独立证据索引，不改写原result、旧manifest或旧SHA。原V17完整证据约897MiB、历史4/10单轮约472MiB，不作为常规源码复制内容；运行所需656MiB LIBERO资产采用前述独立依赖决策。

README增加从零运行的最短路径：安装独立环境 → 获取校验资产 → 配置本机路径与正常Codex登录 → resolve/preflight → 完整十任务 → audit → 查看结果。原CLAUDE.md等存在“无测试”等陈旧说明，随文档提交修正，避免同事按旧说明启动错误setting。

协作约定：

1. main只包含可运行基线和已通过审查的改动；每位同事从同一baseline tag创建功能/算法分支。
2. 算法实验用新的profile和run目录，记录父baseline；不改baseline文件后仍沿用相同名字。
3. Stage/provider变化与QD/ED算法变化分开提交、分开比较。
4. 每人配置自己的输出根和资源；本研究验证GPU2，代码不把GPU2写成所有同事的唯一设备。
5. 后续公开发布或论文以真实评测协议命名，不将固定十任务开发结果称为独立泛化结论。

**十三、合入与回退方式**

整合前记录main基点与同事新增提交；实际合入前重新检查main是否前进，有变化则在集成分支解决冲突并重跑受影响检查。保留main当前5个未跟踪文档，不执行清理或覆盖。

合入交付包括：最终提交列表、变更范围、验证报告、环境/资产说明和剩余限制，便于进行最终审阅。确认最终变更后再执行主分支合入和可选远端发布；本方案本身不执行这些动作。

建议发布标签为 `baseline/c0-codex-v17-v1`，仅在明确完成发布条件后创建。保留整合前main提交引用。若合入后发现回归，使用revert撤销集成提交或合并提交；不对同事共享分支使用破坏性reset，不删除原研究证据和新失败记录。

**十四、供审阅时调整的决策**

| 决策 | 建议选项 | 替代方案及影响 |
| --- | --- | --- |
| 团队基线 | V17，Codex-only，历史3/10参考 | 选择旧P2需恢复其独立旧条件，不能默认复用当前在线服务得到4/10 |
| main默认 | 保留现有默认，V17显式profile | 全局默认改V17会影响PI05/CALVIN等使用者，需要扩大兼容验证 |
| LIBERO资产 | 首次保留准确vendor内容 | 外部固定资产包可减小主仓库，但要新增获取、校验与离线安装流程 |
| RNG初始化 | 随基线保留20个约288KiB的状态文件与manifest | 改成普通seed是新实验条件，需重新建立成绩 |
| 性能发布门槛 | 工程合同通过 + 完整有效十任务≥3/10 | 允许先发布工程迁移版时须明确“性能未复验达标”，标签区分 |
| GPU用量 | 首先10个主回合；差异需归因时再做同期20回合 | 一开始就双版本20回合证据更强，但时间/调用量约翻倍 |
| 重构范围 | 最小行为保持迁移，拆独立runtime入口 | 同时大规模清理算法会扩大归因范围，不建议首轮做 |
| 工作区策略 | 使用主仓库现有工作区的集成分支；结果统一放原.worktrees/exp实验目录 | 不新增worktree；原V17工作区保持为来源，实施前核对同事占用 |

审阅时最值得先确定的是：团队基线身份、LIBERO资产分发方式、性能发布门槛，以及是否将同期20任务对照设为必做。其余文件拆分和路径迁移可按此方案推进。

**证据索引**

[原V17十任务报告](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/docs/03_evidence/stage_consistency/2026-09-30-codex-v17-full10-report.md)
 · [历史CPU检查记录](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/artifacts/stage_closed_loop_20260929/runs/codex_failed_contact_v17_historical_initialization_online_full10/installed-cpu-validation.json)
 · [RNG来源manifest](/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/stage_closed_loop_20260929/runs/historical_initialization_calibration_v1/fixture-manifest.json)
 · [当前最优baseline分析](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-gpu6-20260922T063626Z/study_worktree/docs/03_evidence/stage_consistency/2026-10-13-current-best-baseline-and-algorithm.md)

