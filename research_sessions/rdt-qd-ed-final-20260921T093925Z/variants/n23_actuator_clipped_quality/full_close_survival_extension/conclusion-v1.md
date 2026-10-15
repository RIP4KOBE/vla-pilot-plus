# N23 tasks1..3：完整八步正向候选的供给、父代分配与终轮保留

本次新扫描覆盖 **124个guided决策、1364个canonical批次、21824个候选行、1240轮实际父代分配**。其中39个决策从未提供完整8步正向候选，27个曾提供但终轮已无，30个终轮仍提供却没有选中，28个选中了完整8步正向候选。**终轮候选集与最终archive不同：4个终轮无full8的决策，最终archive仍保有full8。**

这里full8只指候选前8个动作的夹爪命令均为+1；它不是已经测得的连续闭合、接触、抓取或物理效用。仅被原实验选中的动作前缀实际执行；其他候选的前8步没有在本诊断中执行。

## 冻结范围与核验

独立scope SHA256 `97a1c71e8d25654964931dddb55a621d895e2da43d721b440d4e55d7f9df5bf7`，read manifest SHA256 `535f11b8c7fb73b27298487049144a5281c67acaa13ae51dfc3533d7fc2fb144`。只读取显式已完成N23 tasks1/2/3，共54/68/2个已审计guided bundle；每bundle在主提取中一次。路径/哈希从既有metered receipt/index关联的已关闭manifest冻结，未为选择例子扩大原始搜索。

原生提取44.575095秒，低于240秒；2 CPU threads，CUDA_VISIBLE_DEVICES为空、CUDA未初始化；路径/进程/网络/CUDA初始化守卫无触发；无工程重跑。task0只读取已关闭 `gripper_availability_diagnostic/screen-result-v1.json`，SHA256 `d8ba9b2865479646edfede42e447497dd7b162a4847e3fe5447aa98905c5477c`，没有重新读取task0任何native tensor。

源绑定保持 `51104470983cdbafd08feb87f2f39b7553779405` 与前一gripper诊断的源码/配置字节。新张量仅检查canonical/parent/final/archive的夹爪 `[:, :8, 10]`、原quality/cost向量以及记录fingerprint/occurrence/分配/选择元数据。未访问其他动作维度计算新轨迹，也没有几何、quality、排名重算。序列化bundle物理包含其他张量；加载后不分析其内容。

原decoder对有限第10维 `<0`映射−1，其余+1。21824行的174592个前缀夹爪值均有限且无恰好零值，保持BF16原值/字节哈希；full8计数是精确符号计数，不涉及浮点容差阈值。

完整canonical/parent fingerprints来自实际记录；父代按accepted native audit的全部prior-occurrence aliases，进一步核对记录fingerprint、前8步夹爪字节及原成本。最终archive的完整动作身份关联继承同一accepted native audit，同时重新核对夹爪/成本；**没有为重做完整动作SHA而读取本scope排除的非夹爪分量**。所有重复alias都保留，相同fingerprint不推导唯一插入历史。缺失的中间archive替换事件仍为Unknown。

## 全部决策分解：full8与短暂正向必须分开

| task | guided决策 | 从未full8 | 曾有full8但终轮无 | 终轮有full8但未选 | 选中full8 | 从未任何正向 | 有过正向但从未full8 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 15 | 9 | 4 | 0 | 2 | 3 | 6 |
| 1 | 54 | 11 | 11 | 18 | 14 | 3 | 8 |
| 2 | 68 | 26 | 16 | 12 | 14 | 2 | 24 |
| 3 | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| new1to3 | 124 | 39 | 27 | 30 | 28 | 7 | 32 |
| all0to3 | 139 | 48 | 31 | 30 | 30 | 10 | 38 |

task0行仅复用旧JSON；新读取的分母严格为tasks1..3的124决策。不能把full8口径与旧any-positive口径混用：新39个从未full8的决策里，32个至少有过1..7正向命令，只有7个连任何正向候选都未出现。完整8步供给与短暂正向bit供给是不同观测。

新样本所有候选的0..8正向命令直方图为 **[10174,916,1065,1051,1098,1047,700,713,5060]**，21824行合计：10174行0正向、6590行1..7正向、5060行full8。初始canonical即有full8的决策83个，初始无但随后出现的2个。此处没有按成功相关结果挑选轨迹。

`canonical-batches-v1.csv`保留1364批完整9桶计数；`full-positive-candidates-v1.csv`逐条保留全部5060个full8候选的原顺序、fingerprint、occurrence ID、原native cost/quality/dtype及gripper哈希。成本只原样保留，未重排或评价新的质量函数。

## 实际父代池与对应offspring

1240轮×16槽位=19840个实际父代槽位。记录中elite_count=0且parent_indices为恒等0..15，因此source pool和实际selected-parent pool顺序一致；两个计数仍分别输出，未将未知archive全体当作父代池。

4525个full8父代槽位，在相应记录次序的offspring行中：

- 4462个仍为full8；
- 63个变为1..7正向；
- 0个变为0正向。

另有86个非full8父代对应full8 offspring。这里是原记录source-slot→该轮offspring-row关联，带双方fingerprint与identity；**不是独立干预、不是唯一archive插入血统，也不能把某次变化归因为某一个denoise子操作**。同一archive动作可重复分配到多个slot，这些slot不是独立样本。

池级别所有轮次另观察到：37次“上一canonical池有full8，而下一实际分配池无full8”；9次“实际父代池有full8，而该轮offspring池无full8”。它们可能在同一决策重复出现、随后重新出现，不等于37/9个独立失败。

对27个“曾有full8、最终canonical无full8”的决策，仅定位最后一次full8消失：25个在下一实际分配池已无full8，2个是在实际full8父代之后下一offspring池无full8。完整27行在 `final-full-losses-v1.csv`。第一种只说明**实际选父集合**没提供full8，不能证明当时archive完全无full8，更不能从缺失的中间日志推断某次替换淘汰。

## 终轮无full8而最终archive仍有：全部4例

| task | step | canonical full8数（初始后十轮） | actual parent full8数（十轮） | 最终archive full8 | 所选正向步数 |
|---:|---:|---|---|---:|---:|
| 1 | 624 | 3,0,0,0,0,0,1,0,1,0,0 | 1,1,0,0,0,1,0,1,0,0 | 1 | 5 |
| 2 | 272 | 2,4,4,3,1,2,1,1,0,0,0 | 4,5,3,2,2,1,1,0,0,0 | 1 | 2 |
| 2 | 288 | 1,2,1,1,0,0,0,0,0,0,0 | 2,1,1,0,0,0,0,0,0,0 | 1 | 0 |
| 2 | 496 | 1,1,1,2,3,2,2,1,0,0,0 | 2,1,2,3,2,2,1,0,0,0 | 1 | 0 |

这4个最终snapshot按原native审计alias与原cost/夹爪数据绑定。它们说明terminal canonical与archive成员可不同；不证明改选archive动作会成功。task0旧数据中没有这一full8差异案例，此处不能把旧task0观察泛化成所有任务。

## 固定规则代表例：每类按(task,step)最早一例

代表例使用事前确定的chronological-first规则，不按成本、结果或异常程度挑选；所有决策仍完整保留在附表。

| 分类 | task / step | canonical full8数（11批） | parent full8数（10轮） | terminal / archive full8 | 所选row / 正向数 / 原cost |
|---|---|---|---|---|---|
| 全程无full8 | 1 / 0 | 0,0,0,0,0,0,0,0,0,0,0 | 0,0,0,0,0,0,0,0,0,0 | 0 / 0 | 13 / 0 / 0.04150390625 |
| 选中full8 | 1 / 56 | 15,16,16,16,16,16,16,16,16,16,16 | 16,16,16,16,16,16,16,16,16,16 | 16 / 15 | 9 / 8 / 0.00430297851562 |
| 终轮有full8但未选 | 1 / 64 | 10,12,9,9,8,6,7,6,5,5,4 | 12,9,9,8,6,7,6,5,5,4 | 4 / 4 | 7 / 6 / 0.00137329101562 |
| 曾有full8，终轮无 | 1 / 392 | 0,0,0,1,1,2,2,2,0,0,0 | 0,0,0,2,2,2,2,0,0,0 | 0 / 0 | 6 / 5 / 0.00144195556641 |

其中step392初始没有full8，搜索中出现后又消失，不能写成“初始有好动作被损坏”。step64终轮仍有4个full8候选而实际选中6步正向命令，也不能只凭动作符号判断哪一个更好。完整原成本和身份可核查，但本次不重新排序，也不贴成功/效用标签。

## 全决策附表

I=初始full8，T=terminal full8，A=final archive full8，S=所选8步中正向数。source为task0闭合JSON复用或tasks1..3新native。更完整的11批/10父代轮轨迹及any/transient计数在全139行 `all-decisions-v1.csv`；下表没有只保留出现full8的决策。

| task | step | I | T | A | S | 分类 | 证据来源 |
|---:|---:|---:|---:|---:|---:|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 全程无full8 | 旧JSON |
| 0 | 8 | 0 | 0 | 0 | 0 | 全程无full8 | 旧JSON |
| 0 | 16 | 0 | 0 | 0 | 0 | 全程无full8 | 旧JSON |
| 0 | 160 | 0 | 0 | 0 | 0 | 全程无full8 | 旧JSON |
| 0 | 232 | 0 | 0 | 0 | 0 | 全程无full8 | 旧JSON |
| 0 | 240 | 11 | 16 | 15 | 8 | 选中full8 | 旧JSON |
| 0 | 304 | 5 | 0 | 0 | 0 | 曾有full8，终轮无 | 旧JSON |
| 0 | 312 | 0 | 0 | 0 | 0 | 全程无full8 | 旧JSON |
| 0 | 328 | 1 | 0 | 0 | 0 | 曾有full8，终轮无 | 旧JSON |
| 0 | 344 | 1 | 0 | 0 | 0 | 曾有full8，终轮无 | 旧JSON |
| 0 | 400 | 0 | 0 | 0 | 0 | 全程无full8 | 旧JSON |
| 0 | 408 | 15 | 15 | 15 | 8 | 选中full8 | 旧JSON |
| 0 | 488 | 0 | 0 | 0 | 0 | 全程无full8 | 旧JSON |
| 0 | 496 | 0 | 0 | 0 | 0 | 全程无full8 | 旧JSON |
| 0 | 504 | 1 | 0 | 0 | 0 | 曾有full8，终轮无 | 旧JSON |
| 1 | 0 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 1 | 8 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 1 | 16 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 1 | 24 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 1 | 56 | 15 | 16 | 15 | 8 | 选中full8 | 新native |
| 1 | 64 | 10 | 4 | 4 | 6 | 终轮有full8但未选 | 新native |
| 1 | 136 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 1 | 144 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 1 | 256 | 15 | 16 | 9 | 8 | 选中full8 | 新native |
| 1 | 264 | 0 | 0 | 0 | 3 | 全程无full8 | 新native |
| 1 | 272 | 0 | 0 | 0 | 3 | 全程无full8 | 新native |
| 1 | 280 | 10 | 11 | 11 | 7 | 终轮有full8但未选 | 新native |
| 1 | 296 | 11 | 15 | 15 | 8 | 选中full8 | 新native |
| 1 | 304 | 8 | 14 | 13 | 8 | 选中full8 | 新native |
| 1 | 312 | 4 | 1 | 1 | 2 | 终轮有full8但未选 | 新native |
| 1 | 320 | 0 | 0 | 0 | 6 | 全程无full8 | 新native |
| 1 | 328 | 3 | 1 | 1 | 3 | 终轮有full8但未选 | 新native |
| 1 | 352 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 1 | 376 | 6 | 14 | 13 | 8 | 选中full8 | 新native |
| 1 | 384 | 2 | 1 | 1 | 4 | 终轮有full8但未选 | 新native |
| 1 | 392 | 0 | 0 | 0 | 5 | 曾有full8，终轮无 | 新native |
| 1 | 400 | 2 | 0 | 0 | 7 | 曾有full8，终轮无 | 新native |
| 1 | 408 | 2 | 5 | 4 | 3 | 终轮有full8但未选 | 新native |
| 1 | 416 | 3 | 0 | 0 | 5 | 曾有full8，终轮无 | 新native |
| 1 | 424 | 6 | 1 | 1 | 3 | 终轮有full8但未选 | 新native |
| 1 | 432 | 4 | 0 | 0 | 7 | 曾有full8，终轮无 | 新native |
| 1 | 440 | 7 | 5 | 7 | 8 | 选中full8 | 新native |
| 1 | 448 | 3 | 0 | 0 | 6 | 曾有full8，终轮无 | 新native |
| 1 | 456 | 4 | 6 | 6 | 3 | 终轮有full8但未选 | 新native |
| 1 | 464 | 6 | 2 | 4 | 8 | 选中full8 | 新native |
| 1 | 472 | 3 | 0 | 0 | 7 | 曾有full8，终轮无 | 新native |
| 1 | 480 | 6 | 5 | 7 | 8 | 选中full8 | 新native |
| 1 | 488 | 1 | 0 | 0 | 4 | 曾有full8，终轮无 | 新native |
| 1 | 496 | 5 | 1 | 1 | 8 | 选中full8 | 新native |
| 1 | 504 | 4 | 1 | 2 | 3 | 终轮有full8但未选 | 新native |
| 1 | 512 | 10 | 10 | 8 | 8 | 选中full8 | 新native |
| 1 | 520 | 1 | 1 | 1 | 4 | 终轮有full8但未选 | 新native |
| 1 | 528 | 1 | 0 | 0 | 4 | 曾有full8，终轮无 | 新native |
| 1 | 536 | 4 | 0 | 0 | 0 | 曾有full8，终轮无 | 新native |
| 1 | 560 | 0 | 0 | 0 | 3 | 全程无full8 | 新native |
| 1 | 568 | 8 | 3 | 4 | 7 | 终轮有full8但未选 | 新native |
| 1 | 576 | 2 | 2 | 2 | 1 | 终轮有full8但未选 | 新native |
| 1 | 584 | 5 | 0 | 0 | 5 | 曾有full8，终轮无 | 新native |
| 1 | 592 | 11 | 6 | 7 | 7 | 终轮有full8但未选 | 新native |
| 1 | 600 | 6 | 8 | 6 | 7 | 终轮有full8但未选 | 新native |
| 1 | 608 | 8 | 8 | 10 | 8 | 选中full8 | 新native |
| 1 | 616 | 5 | 4 | 2 | 8 | 选中full8 | 新native |
| 1 | 624 | 3 | 0 | 1 | 5 | 曾有full8，终轮无 | 新native |
| 1 | 632 | 3 | 1 | 1 | 3 | 终轮有full8但未选 | 新native |
| 1 | 640 | 3 | 2 | 2 | 3 | 终轮有full8但未选 | 新native |
| 1 | 648 | 2 | 3 | 4 | 1 | 终轮有full8但未选 | 新native |
| 1 | 656 | 9 | 7 | 8 | 8 | 选中full8 | 新native |
| 1 | 664 | 11 | 5 | 7 | 8 | 选中full8 | 新native |
| 1 | 672 | 10 | 6 | 6 | 1 | 终轮有full8但未选 | 新native |
| 2 | 0 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 8 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 16 | 2 | 0 | 0 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 32 | 15 | 16 | 15 | 8 | 选中full8 | 新native |
| 2 | 40 | 15 | 16 | 16 | 8 | 选中full8 | 新native |
| 2 | 176 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 184 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 192 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 200 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 208 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 216 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 224 | 0 | 0 | 0 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 232 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 240 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 248 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 256 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 264 | 1 | 0 | 0 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 272 | 2 | 0 | 1 | 2 | 曾有full8，终轮无 | 新native |
| 2 | 280 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 288 | 1 | 0 | 1 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 296 | 2 | 1 | 2 | 0 | 终轮有full8但未选 | 新native |
| 2 | 304 | 3 | 4 | 3 | 7 | 终轮有full8但未选 | 新native |
| 2 | 312 | 1 | 0 | 0 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 320 | 5 | 6 | 7 | 8 | 选中full8 | 新native |
| 2 | 336 | 2 | 0 | 0 | 2 | 曾有full8，终轮无 | 新native |
| 2 | 352 | 3 | 1 | 1 | 0 | 终轮有full8但未选 | 新native |
| 2 | 360 | 0 | 0 | 0 | 2 | 全程无full8 | 新native |
| 2 | 376 | 2 | 0 | 0 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 384 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 392 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 400 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 408 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 416 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 424 | 1 | 0 | 0 | 2 | 曾有full8，终轮无 | 新native |
| 2 | 432 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 440 | 0 | 0 | 0 | 2 | 全程无full8 | 新native |
| 2 | 456 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 464 | 1 | 0 | 0 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 472 | 0 | 0 | 0 | 4 | 全程无full8 | 新native |
| 2 | 488 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 2 | 496 | 1 | 0 | 1 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 504 | 0 | 0 | 0 | 1 | 全程无full8 | 新native |
| 2 | 512 | 0 | 0 | 0 | 5 | 全程无full8 | 新native |
| 2 | 520 | 1 | 0 | 0 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 528 | 1 | 0 | 0 | 0 | 曾有full8，终轮无 | 新native |
| 2 | 536 | 12 | 12 | 12 | 8 | 选中full8 | 新native |
| 2 | 544 | 7 | 3 | 4 | 5 | 终轮有full8但未选 | 新native |
| 2 | 552 | 4 | 2 | 3 | 8 | 选中full8 | 新native |
| 2 | 560 | 4 | 0 | 0 | 3 | 曾有full8，终轮无 | 新native |
| 2 | 568 | 8 | 4 | 5 | 5 | 终轮有full8但未选 | 新native |
| 2 | 576 | 5 | 4 | 5 | 3 | 终轮有full8但未选 | 新native |
| 2 | 584 | 1 | 0 | 0 | 2 | 曾有full8，终轮无 | 新native |
| 2 | 592 | 11 | 13 | 12 | 8 | 选中full8 | 新native |
| 2 | 600 | 8 | 8 | 8 | 4 | 终轮有full8但未选 | 新native |
| 2 | 608 | 9 | 13 | 10 | 4 | 终轮有full8但未选 | 新native |
| 2 | 616 | 11 | 14 | 14 | 8 | 选中full8 | 新native |
| 2 | 624 | 3 | 0 | 0 | 4 | 曾有full8，终轮无 | 新native |
| 2 | 632 | 10 | 12 | 12 | 8 | 选中full8 | 新native |
| 2 | 640 | 14 | 7 | 10 | 7 | 终轮有full8但未选 | 新native |
| 2 | 648 | 12 | 15 | 13 | 8 | 选中full8 | 新native |
| 2 | 656 | 10 | 7 | 7 | 6 | 终轮有full8但未选 | 新native |
| 2 | 664 | 13 | 7 | 9 | 7 | 终轮有full8但未选 | 新native |
| 2 | 672 | 11 | 11 | 12 | 8 | 选中full8 | 新native |
| 2 | 680 | 11 | 10 | 11 | 8 | 选中full8 | 新native |
| 2 | 688 | 11 | 5 | 5 | 2 | 终轮有full8但未选 | 新native |
| 2 | 696 | 10 | 10 | 11 | 8 | 选中full8 | 新native |
| 2 | 704 | 13 | 16 | 14 | 8 | 选中full8 | 新native |
| 2 | 712 | 13 | 16 | 16 | 8 | 选中full8 | 新native |
| 3 | 0 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |
| 3 | 8 | 0 | 0 | 0 | 0 | 全程无full8 | 新native |

## 结论边界与关闭

新记录区分了full8供给、实际父代分配、offspring保留和终轮选择四个观察位置，也显示“any-positive”会掩盖完整前缀缺失。它没有检验物理抓取、保存旧动作的效益、memory或保留lane的成功率。正向命令可能不适合当时状态；没有接触、物体真值、counterfactual rollout或干预证据可判定效用。

中间archive替换因果、单一denoise操作的因果影响及未执行候选的任务结果均为Unknown。不会仅凭这些统计选择新算法，也不会把既有N11类别重复包装为新收益证据。当前实验与冻结源/controller/state/ledger/预算均未变。

本有界screen已关闭。提取后只读取本目录派生输出生成报表与一致性核验，没有重开native或扩展到task4/5、controls或protected。两个工程重跑机会都未使用。

复现命令（仅供审阅，已关闭目录禁止覆盖结果）：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python extract_cpu_v1.py
```

| 输出文件 | SHA256 |
|---|---|
| `all-decisions-v1.csv` | `e196b8b6b8dff30ca4116f4e50149ac10627b7728134b5301c872c49e51aa004` |
| `canonical-batches-v1.csv` | `cab617b0a30be90139aef8ce1b3969d7cdece60ae367f07f68bcc5ba8e620cfe` |
| `extract-v1.log` | `167f9319b38ff135d828dbb55ed90cf6053e8bd955b92a5650407f89aec83002` |
| `extract_cpu_v1.py` | `3745d6c91253e52f63254f4058dd7e9e55b5deda205493b15ebbc722597a618b` |
| `final-full-losses-v1.csv` | `0be2a0d546f6132b89f1f55a23f80bb05feadb7a56fbc18cd654d8a9ea057b74` |
| `freeze-v1.log` | `ee5b3a520d13655de6d01812dec8e4a791606e631b4c91409cd40d12c0a2b1e4` |
| `freeze_scope_v1.py` | `c9340da9bf654e528f463783a938955b8ea6058c03510d42f28dcbf19044b55b` |
| `full-positive-candidates-v1.csv` | `bb318de562a1e0cf1c6eea4df729bae18717903f6f7640a70cc034cea198a438` |
| `parent-rounds-v1.csv` | `615fc07848d0cfb024aaeb6483edc52bbd3e136a92c060edc9ae520871c24d7e` |
| `read-scope-v1.json` | `535f11b8c7fb73b27298487049144a5281c67acaa13ae51dfc3533d7fc2fb144` |
| `report_cpu_v1.py` | `dad6bcb2ff541bb21f01f765549c0f69c08745b990892c4117d16782215d6bff` |
| `result-v1.json` | `224caebf75c59c794de9245eaff5fb5a6fcf7d405c680302d7bbe266f9377828` |
