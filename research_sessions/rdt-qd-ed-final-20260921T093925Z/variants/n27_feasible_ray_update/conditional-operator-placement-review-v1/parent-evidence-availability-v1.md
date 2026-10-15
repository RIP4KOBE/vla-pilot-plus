# 首个 guided chunk 的父代证据可用性

**结论：存在一个可明确限定的候选容器，足以支持下一步申请一次 CPU 解码；本次尚未验证张量内容，也没有算重复率、support或新变异。** 索引确认 step0 同一决策含10条 parent_allocation。源码表明这些记录应能恢复实际 pre-renoise offspring；实际 iter0..9唯一性、shape和字段完整性仍需解码后验证，不能由事件数量代替。

## 已实际确认的范围

唯一 attempt：`rdt-qd-ed-final-20260921T093925Z__n27_screen_t00_n27_20261001_hydra1__30a35187b503`。获准 task0 root review 接受它为有效失败、source=e21d48ab33dbd3aca017349b6004c2ba7d981493，并记录原worker验证11个有限witness；未跟随其中其他artifact引用。

其 `eds_eval/decision_evidence/episode_000/events.jsonl` 大小5,919,663 bytes，但只解析首行。首行330,983 bytes，SHA256 `523f7808afe9bfbbd56ac5a5ad0e4c77ba0a49248be58d3cccef48c58b3a802f`；sequence1..2863，decision_id=`e0:d1:s0`、global_step=0、reset_sequence=0。包含10条 archive_parent_allocation、10条 parent_allocation、11条 canonical_candidate_batch、11条 n27_rbf_witness及1条coverage。结合限定witness的first-guided规则（clipped helper第140–175行），这是可定位的首个guided决策；不是按结果/活动挑出的某个后续chunk。

| 父代记录序号 | archive_parent_allocation sequence | parent_allocation sequence |
|---:|---:|---:|
| 1 | 400 | 401 |
| 2 | 834 | 835 |
| 3 | 1067 | 1068 |
| 4 | 1300 | 1301 |
| 5 | 1533 | 1534 |
| 6 | 1766 | 1767 |
| 7 | 1983 | 1984 |
| 8 | 2200 | 2201 |
| 9 | 2417 | 2418 |
| 10 | 2634 | 2635 |

这些是**记录顺序，不是已经读取的iter_idx**。索引条目只有 sequence/event/decision_id/global_step/reset_sequence；它不公开source_population、parent_indices或shape。文件引用为同目录 `bundle_000001.pt`，stat大小 **12,060,933 bytes**，索引声明SHA256 **`b9ba0f873f0c2b5bb3c81c22df087400952f95cb9ca1d82b1394bf7c7f56f466`**。本次未读其内容，未独立重算该SHA。

小型 `status.json`（532 bytes，SHA `af91fe9fe551636e55a4d535b0eb10c2f860ef090a7f36314097a67bc005f882`）标记complete=true/failed=false，90 decisions及2250 bundles。此为记录器状态，不新增一次独立native审计。

## 字段能否还原实际父代

`W/core/rdt_policy_steer.py:5900–5926` 先以parent索引构造elite/offspring，再逐轮记录 `parent_allocation(source_population, parent_indices, elite_count, parent_cell_ids, offspring_sources, source_quality, source_costs)`；第6104–6105行随后才renoise。故理论重建为 `source_population.index_select(0, parent_indices[elite_count:])`。应保留原archive allocation身份，不能把父代槽号当unique候选，更不能把迭代序号当原始插入因果历史。原archive记录还保存fingerprints、cells和lanes（第5628–5645行），可作关联核对，而非用fingerprint推导不存在的历史。

传统mechanism trace不是十轮pre-renoise父代的可靠替代：policy第6087–6101行只在 `trace_enabled and i==0` 保存 `resampled`；`eds_mechanism_trace.py:328–358` 的JSON仅给stage/shape，完整actions另在tensor payload（第363–405行）。因此无需为本题搜寻或读取其他trace目录。

| 问题 | 一次限定解码后可做到 | 仍不能证明 |
|---|---|---|
| 重复父代 | 每轮16槽的完整模型动作字节重复率；另外报告前8×3 xyz相同/clip后相同，区别full-action与行为前缀 | 相同指纹的插入因果、其他chunk普遍性 |
| 可移动支持 | 每轮384分量的严格内部/恰好边界/外部计数及每粒子支持数；共10轮3840分量 | 有内部坐标必有非零梯度；可移动必有任务价值 |
| 假设父代变异全零否 | 原dtype的CPU参考RBF/可行射线产生的gradient、operand、alpha、赋值delta是否全零 | CUDA逐位结果、模型吸收、最终候选/真实接触/成功收益 |

`qd_actuator_clipped_rbf.py:81–94` 中重复轨迹对自身的梯度为零；重复组对其他组可以共同移动。`qd_feasible_ray_update.py:40–58` 中零operand保留字节，边界/外部不允许非零operand。故“父代重复率”不能单独判断变异无效，support也不能替代实际参考梯度计算。现有N27 witness输入是同一次model_output，而不是父代（`qd_feasible_ray_rbf.py:69–80`）；不能直接拿既有非零RBF标量作新位置的活跃证据。

## 供 root 审查的最小后续方案（未授权、未执行）

只需上述 **一个** bundle；先冻结精确路径、索引行和root review引用，保持全部10轮分母。一次读取整12,060,933-byte文件并在同一读取字节上核SHA；仅一次CPU weights_only解码。**完整container包括共存scoring/provider_return/projection/selection等事件**，读取授权必须明确覆盖整个容器反序列化，不能仅以导出prefix的15 KiB声称实际读取量。只导出父代重复/support/参考更新的聚合，不导出共存quality、provider返回或其他无关数值。容器中未预料字段或无法关联时停止并记Unknown，不另找bundle。

建议新范围固定：1文件/13 MiB输入硬上限；ZIP声明未压缩总量及解码去重storage各≤64 MiB（这是未来拒绝门，当前未验证符合）；独立进程在Torch导入前8 GiB RLIMIT_AS、2CPU/线程、CUDA隐藏未初始化、≤60秒总时限，无网络/生产导入/model/API/sim。达到任一上限就留下不完整结果，不扩读/重跑。峰值RSS如实记录，不把AS上限写成RSS保证。

只保留10个parent_allocation的实际iter0..9、elite_count=0、source_population形状16×64×128及长度16的parent_indices/cells，并核对前述10条archive身份。每批FP32数值大小≤524,288 bytes，10批≤5,242,880 bytes；BF16为其一半，但这不是容器总storage上限。计算只取每批16×8×3的xyz（所有池FP32前缀≤15,360 bytes）；全action只用于字节身份，不评分/几何拟合/selection重排。

若进一步做假设RBF，必须从同一容器直接关联原记录的origin，核验其shape、dtype及同决策一致性。每轮既有首RBF witness提供的source/cast origins为16×3（11槽上限，第185–207行），但其采样时刻是原rollout模型调用，不是尚未存在的pre-renoise变异；共同origin的使用假设必须明说。若关联不唯一/缺失，则只完成重复与support，参考RBF保持Unknown，不设零origin或调投影。沿固定clip、0.01投影、原负梯度符号/全局归一化/20提议范数、逐粒子FP32 alpha做CPU参考；不把旧same_forward证据标签套到它上面，不声称CPU零/非零就是CUDA证明，不添加噪声打破重复。该检查只能回答离线可检验的局部活跃性，不能回答通过renoise/模型之后是否保留影响。

## 读取审计与来源

本次实际tensor字节读取/解码均为0；未读metrics、Stage、图片/视频、其他attempt或保护集。开始文件清单在自设250项打印界限停止（RuntimeError，未读内容）；随后只列同一目录的非.pt条目。首行先以自设64 KiB门读取65,537-byte前缀并停止；root明确扩到1 MiB后，两次读取/解析同一首行用于schema与计数，未解析后续行。前述边界停止均保留于工具记录，不是实验故障。状态532-byte文件仅读一次。没有运行Torch、生产模块或测试，所有进程显式2CPU亲和性/2线程环境、CPU文件处理远低于60秒。唯一新增产物为本报告。

| 来源 | SHA256 |
|---|---|
| C27/task0-root-review-v1.json | `04d1e04701b988a9fdace815772f366aa213e9bb7b1d6f7f22f11fd1ccbd1e18` |
| W/core/rdt_policy_steer.py | `768fd9d1072f1f2abc0e3a1f87f764facd69b99e102399c041b73167b6ef00fe` |
| W/core/eds_mechanism_trace.py | `312087f5c354f81a820f2acb8419c6380e96805de79f1789c5c7ff23a8fcabf3` |
| W/core/qd_feasible_ray_update.py | `146163977866af87d2c643b0446be9ebac12f83cf9337d534b736874c623203e` |
| W/core/qd_feasible_ray_rbf.py | `f2494d1a2c55f4899d848d5f7e8af03cc8518cd53749c8875a117c1ff15a3207` |
| W/core/qd_actuator_clipped_rbf.py | `d0a516046f9d9efc8694916a9ff845c8b67868d8d7d2d01381894bcc05b89408` |

C27=`R/variants/n27_feasible_ray_update/hydra-continuation-v1`；W=`R/study_worktree`。索引行、status与container声明哈希已在正文列出，container内容哈希尚未独立核验。当前N27续跑和原科学规则保持不变。
