# N24 task0 rescue survival：一次限定诊断

结论：12次已记录替换均恢复了一个 full8 父代，且12个对应当轮 ED 后代均保留 full8。终轮候选可用性并非每次都变成最终执行：step304、408终轮各有1个full8候选，实际分别选择3/8、0/8正向命令。本诊断不说明这些候选是否能抓住物体，也不估计成功率或相对于N23的因果收益。

本次只读取已完成、原审计有效的 task0/N24 attempt `rdt-qd-ed-final-20260921T093925Z__n24_dev_t00_n24_20260930__169d5a090d1b`。未读取其他attempt、运行中任务或保护集。当前N24队列和冻结规则没有改变。

## 覆盖与计数

- 原生14 bundles，共243,123,318字节；每份仅一次读取，同一bytes先SHA验证再CPU `torch.load(BytesIO, weights_only=True)`。没有第二次native提取。
- 14 guided decisions、154 canonical batches、2,464候选、140父代轮、12替换，与原accepted/evidence_complete native audit全部一致。
- Native `cache_updates=32` 是逐候选刷新次数；实际 `updated=true` 的批次为21。冻结实现和独立审计一致，二者均原样报告。
- CPU2线程、CUDA不可见且未初始化；提取4.843773499秒，低于120秒上限，guard拦截0。没有网络/子进程/运行时/provider/API/模型/仿真调用，没有新增动作、GPU记账或状态改写。
- full8定义是native latent前8步第10维均>=0，并核验选中动作原生decoder/commit第6轴正号一致；本次canonical切片中精确零值0个。正命令不等于物理闭合或抓握。

## 全部14个决策

计数均为该实际16行池中的full8行数；初始为canonical iter=-1，终轮为iter=9。

| step | stage | 初始full8 | 终轮full8 | 实选正命令/8 | 分类 | 原生刷新数 | 变化批数 | 替换数 |
|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 0 | 1 | 0 | 0 | 0 | 始终无full8 | 0 | 0 | 0 |
| 8 | 1 | 0 | 0 | 0 | 始终无full8 | 0 | 0 | 0 |
| 16 | 1 | 0 | 0 | 0 | 始终无full8 | 0 | 0 | 0 |
| 160 | 1 | 0 | 0 | 0 | 始终无full8 | 0 | 0 | 0 |
| 232 | 1 | 0 | 0 | 0 | 始终无full8 | 0 | 0 | 0 |
| 240 | 1 | 11 | 16 | 8 | 选中full8 | 9 | 5 | 0 |
| 304 | 1 | 5 | 1 | 3 | 终轮有但未选 | 2 | 2 | 8 |
| 312 | 1 | 6 | 15 | 8 | 选中full8 | 7 | 5 | 0 |
| 320 | 1 | 14 | 16 | 8 | 选中full8 | 3 | 1 | 0 |
| 328 | 1 | 16 | 16 | 8 | 选中full8 | 6 | 3 | 0 |
| 392 | 1 | 0 | 0 | 0 | 始终无full8 | 0 | 0 | 0 |
| 400 | 1 | 0 | 0 | 0 | 始终无full8 | 0 | 0 | 0 |
| 408 | 1 | 1 | 1 | 0 | 终轮有但未选 | 1 | 1 | 3 |
| 416 | 1 | 1 | 5 | 8 | 选中full8 | 4 | 4 | 1 |

分类完整分母：7/14始终无full8；0/14曾有full8但终轮无；2/14终轮有而未选；5/14选中full8。所有7个始终无full8的决策初始也无full8，后续10轮没有出现，不能自动归因于QD淘汰。

## 全部12次替换

轮号为原记录0..9；每行的原池full8=0、实际池full8=1，其他15行的授权gripper字节和记录fingerprint保持一致，actual parent→child由记录的parent_indices和canonical行号绑定。全部16行仍经过ED，未把缓存作为exact survivor或强制执行。

| step | 轮 | 替换slot | cache birth(iter,row) | 当轮child正命令/8 | 原child完整fingerprint在终轮的行 | 实选同child fingerprint |
|---:|---:|---:|---|---:|---|---|
| 304 | 2 | 8 | (1,11) | 8 | [] | False |
| 304 | 3 | 14 | (1,11) | 8 | [] | False |
| 304 | 4 | 0 | (1,11) | 8 | [] | False |
| 304 | 5 | 12 | (1,11) | 8 | [] | False |
| 304 | 6 | 11 | (1,11) | 8 | [] | False |
| 304 | 7 | 14 | (1,11) | 8 | [] | False |
| 304 | 8 | 13 | (1,11) | 8 | [] | False |
| 304 | 9 | 14 | (1,11) | 8 | [14] | False |
| 408 | 6 | 15 | (-1,7) | 8 | [] | False |
| 408 | 7 | 15 | (-1,7) | 8 | [] | False |
| 408 | 8 | 15 | (-1,7) | 8 | [] | False |
| 416 | 0 | 12 | (-1,6) | 8 | [] | False |

- step304：round2..9共8次反复从同一缓存birth(1,11)补回full8；每次当轮后代都full8。终轮只有最后一次rescue的原后代fingerprint直接出现于row14，但未选中，实选3个正命令。
- step408：round6..8共3次补回同一初始cache birth(-1,7)。round9原allocation已有full8，故没有替换。终轮有1个full8但实选0个正命令。三个早先rescue原child的完整fingerprint都未直接出现在终轮。
- step416：仅round0一次补回初始cache birth(-1,6)，当轮后代full8。之后各轮原allocation已经有full8；终轮5个full8并实际选中一个。初轮原child的完整fingerprint与最终选择不同，因此不能把最终选择归因给该次rescue。

12个rescue原child的完整身份均未在之后的实际父代审计matching_occurrence_ids中再次出现；这只限制“同一个完整张量被再次分配”的结论。变异后的后代关系、archive插入/淘汰原因，以及最终选择是否存在间接rescue祖先，都保持Unknown。没有依据fingerprint相似或仅相同命令符号虚构血缘。

## 源码与证据边界

- 冻结3b7 `core/qd_gripper_parent_rescue.py:80-98` 逐行严格更低cost时update_count+1，并单独返回updated布尔；`core/rdt_policy_steer.py:5171-5175` 累加update_count。`scripts/audit_gripper_parent_rescue.py:99-108` 独立核验并累加同一逐行计数。本诊断仅读取原记录，不重新比较cost或排序。
- 原archive allocation的fingerprint/witness、rescue的original/actual grip、actual parent记录、native audit occurrence映射及当轮canonical row顺序分别保留。缓存候选不被假称为archive成员。
- 本提取只核验授权的gripper字节与已记录完整fingerprint/occurrence身份；完整动作关联与原“first native worst slot/min-cost cache”正确性由已接受的原native audit承担。没有对未授权latent维度重新哈希、查看geometry/provider-return、重算quality、重排候选。
- `torch.load`会反序列化整个允许bundle，但程序只访问scope限定字段与索引元数据；未分析其他tensor内容。最终archive population本次没有读取，因此不能声称archive内full8彻底消失。
- 没有真实接触/object pose/reward/success字段分析，没有物理结果、收益、失败归因或paired-state/counterfactual声明。无法据此选择或实现下一候选。

## 可复核文件

输入清单在首次native读取前冻结；`read-scope-v1.json`、输入清单和extractor是不可改写的前置记录。14个partial-decision文件保留完整授权切片和链接；`result-v1.json`、两份CSV及本结论为汇总。所有输出由 `output-manifest-v1.json` 逐文件绑定。

- Scope SHA256: `d309ef966b8f18f8d66dbdbc2e670b8d70369ed23ec2b0d6552d6323ed64548b`
- Input manifest SHA256: `6d48d9550f01b0e3ac6d17efd09a410a6ec4beb2644f79b68a3067f57f1ba403`
- Extractor SHA256: `191c7658685918d5cc8fb42dfc549acf7a28fc233b46c2d1f913293057ffbafb`
- Result SHA256: `a64c5dca8291ec2846e75fe25170e4b8da158294eebe2ee7b68fe0b543bdee4d`
- Native audit SHA256: `92bd6852eceedef8cbc67befe98b74cd036685a74afc8cea6ec4d154117d2c0e`
- Native receipt SHA256: `f14f7a1c4dfcb60729f0b33b3d00de4e55dc8b1599bb74e01b4e0697c8d86cae`

诊断已完成并关闭，不再读取native、不扩大语料、不改当前算法或协议。
