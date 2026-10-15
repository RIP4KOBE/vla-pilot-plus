# N28 闭轮后首 guided 身份连接可用性

**结论：四格的实现谱系可连接；不能从这些身份连接判断变异信息是否被模型保留，或是否带来任务收益。** 本次不解码、不复算，也不提名或释放下一算法。

激活已核对：冻结结果 `adf94981b8ffb9d1cdfbabd1b330b8a88f6e734a0aa15d4024cef352e7f6397b` 与根终态复核 `27820eb627674c516377a90873c1132448bbcc190673be6c64d6872cb14087f7` 一致：16格全部有效，C0/Q0/N27/N28分别0/4、0/4、1/4、0/4，`REJECT_SCREEN`，根记录原控制器已退出。仅继承根退出核验，本 reader 未读取 /proc 或自行再次核验进程。

N28 plan SHA：`36254e660f55c35b1046001e95947e94c175b6aa7c99f1edf55a254f34c0bd00`；source 为 `52b9eb0a8a365ee2ea12daffdb7a98c76bec0a72`。四份 context/receipt 的383项 source记录与 plan/source manifest 完全相同；terminal、profile、task、episode、attempt、plan、receipt/audit refs 及进程身份字段相互一致。未执行原控制器或重放原证明。

| task | 首 guided | parent轮/槽 | witness / renoise入口 | canonical批 | 选中row | 首索引decode / dispatch |
|---|---|---:|---:|---:|---:|---:|
| 0 | `e0:d1:s0`，step0 | 10 / 160 | 11 / 10 | 11 | 0 | 1 / 0 |
| 1 | `e0:d1:s0`，step0 | 10 / 160 | 11 / 10 | 11 | 0 | 1 / 0 |
| 2 | `e0:d1:s0`，step0 | 10 / 160 | 11 / 10 | 11 | 9 | 1 / 0 |
| 3 | `e0:d1:s0`，step0 | 10 / 160 | 11 / 10 | 11 | 0 | 1 / 0 |

覆盖全部四个已接受 N28 格，未按成败或活动挑选。每格仅原 first-guided 段；11个 witness 含1个 initial与10个 parent。每格 canonical 为初始1批加10轮，每批声明16行。所有640个 parent slots 的既有审计匹配列表非空，本段没有多重匹配项；这不恢复未知的原始 archive 插入 occurrence。

| 连接 | 本次可用性及依据 | 保留限制 |
|---|---|---|
| archive allocation → 实际 pre-mutation parent | **explicit / joinable**：审计 `parent_associations`、metrics `parent_allocation_sequence` 与索引对应10轮一致。 | matching occurrence 是既有内容匹配，非重新验证 tensor，更不是唯一原始插入历史。 |
| pre-mutation → post-mutation | **explicit，但内容在本 reader 未验证**：冻结 witness schema 包含两者；原 worker逐位审计接受，11个 check 的身份和状态存在。 | JSON index只有事件身份，不包含这些 tensor的值或独立 shape观测。 |
| post-mutation → actual renoise入口 | **explicit / joinable**：每轮 witness后一条即boundary；父代sequence、iteration与已接受native gate相符。 | 精确prefix相等及same-object证明继承原同进程审计，不是本次读者数值复验。 |
| renoise入口 → canonical offspring | **joinable谱系**：同decision/iteration、固定行序和canonical sequence/scoring-batch；原source拼接offspring再mask/score，无新重排干预。 | 无独立逐行after-noise身份JSON；行序联系依赖冻结代码和既有审计。不能把共同祖先当变异影响仍存在。 |
| canonical → 选中执行前缀 | **explicit选择身份**：终轮q2343、row0/0/9/0、occurrence、fingerprint及原native ID一致，各首索引有1个decode事件。 | 首索引无action_dispatch；原N5报告声明该decision实际prefix8步的绑定已验证。本次未读取后续索引行，实际dispatch内容未独立核验；不能将0解释成未执行。 |

四个 `.pt` 容器仅核对引用路径、存在性和stat大小（合计46,072,852字节）；**内容读取0字节**。索引与receipt里的bundle SHA相同，但未重哈希容器。first-index/first-metrics均只读取第一完整JSONL行；记录的是该行SHA，整个文件SHA只继承receipt，未通过读取其余段重新验证。原native算术、tensor完整性、shape及decoder/dispatch关联均明确继承已绑定原审计和root终态。

声明shape：父代全张量`16×64×128`、prefix/witness主体`16×8×3`、origin`16×3`，审计dtype为BF16；这些来自冻结发出器/审计规则及原worker报告，不是本 reader对tensor的独立观测。源码依据：`qd_parent_before_renoise.py:28–68,87–103,129–151`；`qd_ed_n28_native.py:104–147`；`rdt_policy_steer.py:5912–5939,6117–6127,6346–6352,6454–6464`。精确路径与SHA在来源清单。

**尚不能回答：** 更新的数值差异如何经模型传递、是否导致选中动作改变、是否影响物理任务结果。最小缺失是上述已连接对象的数值观察；即使另行批准只读解码，也只能得到处理后路径差异，不能在缺少同噪声/同输入未处理对照时推断因果吸收或保留。本任务不自动读取这些值或运行对照。

**字段边界偏差：** schema检查时误将已允许 audit JSON 的完整首N5 decision字典输出到工具上下文，包含cost/raw-quality数值向量；因此不能声称全过程严格只见身份/shape。已向root披露并获准继续精确字段检查。这些数值未用于结论、样本选择、重算或阈值；没有读取任何Stage正文/tensor文件。原scope保留，偏差记录及原暂存文件hash保留，交付暂存已缩减到身份字段。此次报告是知情可用性审计，不是盲态研究。

没有读取controls原始产物、旧cohort payload、凭据或保护集；未导入Torch/NumPy/生产代码、运行GPU/API/模型/仿真/测试。未改源码、状态、配置、账本或预算。交付后停止。
