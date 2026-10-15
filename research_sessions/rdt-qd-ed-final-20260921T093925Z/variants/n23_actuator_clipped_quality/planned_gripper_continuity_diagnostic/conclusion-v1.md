# N23 已完成 task0..3：跨动作块的计划夹爪连续性

**观察到旧计划尾部与下一次重规划之间存在命令变化，但这本身不是算法缺陷。** 在 114 对严格同 guided、Stage、reset 和已记录目标追踪身份的相邻决策中，15 对旧计划的 offsets8..15 全部预测正向夹爪命令；下一次实际执行的 prefix0..7 中，5 对仍全正向、8 对混合、2 对全非正向。旧尾部从未执行，其物理正确性、保留它的效果及成功率收益均为 **Unknown**。

同 Stage/目标身份并不意味着观察未更新。下面保留全部分母、改变和不改变的例子；不将重规划变化直接解释为错误，也不据此选择或实现 memory 候选。

## 范围与证据

这是独立的新 OBSERVE，不修改此前两个关闭的 task0 screen。只使用事前冻结的 N23 task0..3 已完成 chronological prefix，未经成功结果挑选。源保持 `51104470983cdbafd08feb87f2f39b7553779405`。scope SHA256 `d99fa82a046dfbbea0f4849f86ab53ee603a132ab4df29626f7a3e22db88b97f`，四 attempt manifest SHA256 `cca36ad827d720aa7973e808d86db7fb00da961f44ba4203f57123626adc39f4`。

首先仅从这四个显式 attempt 的 terminal、native receipt/audit、decision index 冻结精确读取清单 `read-scope-v1.json`，SHA256 `65e0381d8ad3e1e9321be09b63e5cbf5a11ece46f1950adf76a2aceed640d452`。然后一次读取 360 个 hash-linked selected-event bundles，每个一次。只分析 decision_context、policy_action_decode、decision_committed、final_selection，以及这些已选 bundle 中的 terminal population 夹爪计数；未扫描 canonical 历史、provider 返回或成本寻找例子。bundle 中物理共存的其他张量被反序列化后忽略，没有作为本分析输入。

每个任务 90 决策/720 个已执行动作，四任务共 360 决策、2880 动作；共 356 对立即相邻边界，前一个完整执行 8 步，step 相差 8，无跨 reset 比较。所有 selected latent 指纹与保存的解码/commit 匹配；139 个 guided 决策另与 accepted native audit 的 selected native hash、selected index、target index、实际 action prefix 长度绑定。全部动作数量/reset 还由被原 native receipt 哈希绑定的 index 及已接受 audit 总量核对；未读取额外 execution/outcome bundles。

原 decoder 的 latent 第10维 `<0→-1`、其余 `→+1` 规则保持不变；360 个 selected latent 的前16步未发现恰好零值。prefix和tail只是精确动作符号，不计算新的轨迹、距离、quality、价值或模拟。没有调用 CUDA、模型、API、provider、simulator，未读 task4/其他尝试/保护集/进行中结果/凭据。

## 所有相邻对的分层

严格身份要求：双方 guided、相同 Stage、reset、tracker instance 和 registry generation、相同 recorded target_index、target valid且状态为 tracked/static_background、provider源哈希一致。不能从 task ID、同坐标或相近运动推断这些身份。

分类有明确优先顺序：先 Stage 改变，再同 Stage 的 guidance 改变，再同 Stage 均 unguided；只有其余两边 guided 的记录核查 target identity。实际不存在 reset/incomplete/tail缺失，也不存在两边 guided 同 Stage 但 tracker身份缺失/改变的额外对。全样本 guidance 实际改变 45 对，其中 22 对同时属于 34 对 Stage 改变；表中 23 是不重叠的同 Stage guidance 改变。

| 分层 | 相邻对 | 8bit 完全一致 | 旧尾部全正向 | 其中下一全非正向 | 其中下一混合 | 总不同bit |
|---|---:|---:|---:|---:|---:|---:|
| 严格同 guided / Stage / reset / target | 114 | 41 | 15 | 2 | 8 | 348 |
| 同 Stage、均 unguided | 185 | 152 | 25 | 2 | 3 | 152 |
| 同 Stage、guidance 改变 | 23 | 12 | 6 | 3 | 0 | 73 |
| Stage 改变（可同时改变 guidance） | 34 | 22 | 6 | 2 | 0 | 70 |

这些行没有因结果好坏删除任何记录。356 对中 227 对的8bit完全一致。两边 unguided 的 185 对也有 5 对全正向旧尾部变为非全正向；因此这类现象不特属于 QD/ED。

| task | guided 决策 | 严格相邻对 | 严格8bit一致 | 严格旧尾部全正向 | 下一全非正向 | 下一混合 |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 15 | 7 | 5 | 0 | 0 | 0 |
| 1 | 54 | 46 | 7 | 8 | 0 | 6 |
| 2 | 68 | 60 | 28 | 7 | 2 | 2 |
| 3 | 2 | 1 | 1 | 0 | 0 | 0 |

## 严格层全部15个全正向旧尾部

`1`=正向命令、`0`=非正向命令，旧尾部均为 `11111111`。下面包含保持的 5 对，没有只列改变的 10 对。next terminal 的候选数只来自同一个已读取 selected bundle，分别列出“至少一正向 / 全8步正向”；不是重跑或新候选搜索。

| task | 上一步→下一步 | 下一实际prefix bits | 下一terminal正向候选 / 全正向候选 | 记录目标位移（mm） |
|---:|---|---|---|---:|
| 1 | 56→64 | `11111100` | 16 / 4 | 3.16581643e-07 |
| 1 | 256→264 | `11100000` | 16 / 0 | 0 |
| 1 | 376→384 | `11110000` | 11 / 1 | 0.609456892 |
| 1 | 440→448 | `11111100` | 12 / 0 | 6.94857082 |
| 1 | 464→472 | `11111110` | 16 / 0 | 2.18997676 |
| 1 | 512→520 | `11110000` | 15 / 1 | 45.576946 |
| 1 | 608→616 | `11111111` | 15 / 4 | 2.59067305 |
| 1 | 656→664 | `11111111` | 8 / 5 | 2.538473 |
| 2 | 272→280 | `00000000` | 0 / 0 | 0.773473793 |
| 2 | 304→312 | `00000000` | 0 / 0 | 2.17671994 |
| 2 | 536→544 | `00011111` | 16 / 3 | 53.0734366 |
| 2 | 544→552 | `11111111` | 14 / 2 | 4.40768167 |
| 2 | 592→600 | `11110000` | 16 / 8 | 2.03940393e-07 |
| 2 | 664→672 | `11111111` | 16 / 11 | 0 |
| 2 | 704→712 | `11111111` | 16 / 16 | 0 |

两例全非正向变化为 task2 的 **272→280、304→312**，下一实际 terminal population 都为 16 个全非正向候选。因此在那两个既有终轮池中，仅改 terminal selector 无法选出正向命令。但这不证明旧尾部正确、保留旧尾部有利，亦不排除新观测合理地使全部候选改变。

8 例 mixed 包含不同情形：部分下一池仍有全8步正向候选，部分没有。只依据符号不能决定应选择哪个，也没有重新评价这些备选的动作效果。原固定 pool 内的质量、可达性和实际执行后果未在此研究。

## 位置与身份的限制

目标位移只对双方已有完整且一致记录身份的对计算，用保存的 policy-visible context keypoint 坐标相减得到描述性长度；不查询新 pose，不积分轨迹，不选择握持阈值。严格15例既有目标位移近零，也有约 45.58/53.07 mm 的更新。近零并不能证明没有新视觉/机器人观测或需要坚持旧计划；同移也不能证明确定抓取。

EEF 位置没有保存在本范围的 decision_context，故全部 EEF 位移明确为 **Unknown**，不扩读 projection/action-outcome bundles 来补齐。221 个 unguided 决策没有可由 terminal selection 证明的目标 index，目标身份标为 Unknown；这不被填补为“与上一目标相同”，也没有混入严格层。registry身份只证明追踪记录的身份一致，不能保证物体状态估计准确或接触成立。

RDT 更远的动作尾部可能随着执行及新观测失准；重规划正是允许更新计划的机制。本观察只证实了命令计划在边界的变化，不证实连续性保留是优化方向或能提高任务成功率，也不诊断环境执行故障。结果来自四个相关且已暴露 Dev 轨迹，没有独立对照、因果干预、反事实物理结果或泛化证据。

## 核验与关闭

两阶段都使用精确路径守卫，blocked reads=0。主提取 47.76秒，2 CPU threads，CUDA initialized=false。保存完整每边界记录、356对 bit patterns/counts/identity flags、全部索引/输入/源码哈希，以及 `pairs-v1.csv`。本报告只读自己的导出 JSON/CSV，并额外核对360/356分母、2880动作、15全正向旧尾部及分层汇总一致性；未再次读取真实 bundles。

未修改源、controller、state、ledger、预算、已有 screen，未创建或实现候选、未放行 GPU。该 OBSERVE 关闭。任何后继算法提案都应在当前在线 cohort 终局及预算可行性审查后再决定。

复现命令（已存在的 immutable 结果会使脚本拒绝覆盖；仅供审阅，不应在关闭目录再次执行）：

```bash
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python extract_cpu_v1.py
```

| 输出文件 | SHA256 |
|---|---|
| `freeze_read_scope_v1.py` | `9617b70d705fd859cacf078e30f850a9ec70e89b0ed8fd5ac5deca1294278904` |
| `freeze-v1.log` | `0793801b189d420e41781e06b9b899ead68a9100157e0b42903622ddb5266b8a` |
| `read-scope-v1.json` | `65e0381d8ad3e1e9321be09b63e5cbf5a11ece46f1950adf76a2aceed640d452` |
| `extract_cpu_v1.py` | `9e085cec3ae3aca2d11e9f031a42c8b68f169680a545f14b903b047a33b3b0d9` |
| `extract-v1.log` | `4d26ae908e75d6d0b94f0ef470223da3c5aaa36f38056412e2e8b4b658e600bd` |
| `result-v1.json` | `2e12365b15cff7e656a4468a4ad22cb238e34d0c5155ad0294a5fd13c332cacd` |
| `pairs-v1.csv` | `2b69067d2fa4e650c26548051f9c7bb1ae663fcadd58c4944f9b5d1d6f1e9093` |
