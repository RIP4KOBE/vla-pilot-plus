# 三模式在线验收结果

2026-10-13，在 **RDT + LIBERO ObjectSwap OOD** 上，EDS为 **3/10**、VLS为 **1/10**、EDS+QD为 **1/10**。三组各十任务均完整有效、worker正常退出、零基础设施错误；三组有效且EDS≥3/10的整合门槛通过。

原始在线受测runtime为 `33954ead452927fc3168efb610487a688f89169e`。同一任务采用同一预先固定seed、初始化、资产和Stage规则，每任务每方法仅一个episode。此前迁移验收的10个episode单独记录；本次整合共40个科学episode（迁移10 + 公共比较30），没有额外科学重试或用新成功替换旧失败。

| Task ID | Seed | EDS | VLS | EDS+QD |
| --- | ---: | --- | --- | --- |
| 0 | 44 | 失败 · 720动作 | 失败 · 720动作 | 失败 · 720动作 |
| 1 | 235 | 失败 · 720动作 | 失败 · 720动作 | 失败 · 720动作 |
| 2 | 43 | 失败 · 720动作 | 失败 · 720动作 | 失败 · 720动作 |
| 3 | 546 | 成功 · 120动作 | 成功 · 134动作 | 失败 · 720动作 |
| 4 | 6 | 失败 · 720动作 | 失败 · 720动作 | 失败 · 720动作 |
| 5 | 621 | 失败 · 720动作 | 失败 · 720动作 | 成功 · 223动作 |
| 6 | 197 | 失败 · 720动作 | 失败 · 720动作 | 失败 · 720动作 |
| 7 | 87 | 失败 · 720动作 | 失败 · 720动作 | 失败 · 720动作 |
| 8 | 151 | 成功 · 211动作 | 失败 · 720动作 | 失败 · 720动作 |
| 9 | 548 | 成功 · 214动作 | 失败 · 720动作 | 失败 · 720动作 |

表中所有成功与失败都通过完整合同审计。逐任务合同检查数、配置/环境/原audit hash、动作数及视频hash随Git保存在[final-results.json](validation/final-results.json)。低成功率不等于无效cohort；这个单seed比较不足以推出统计优越性、非劣效或泛化能力。

## 实际计算与服务

| 方法 | Worker耗时 | Guided / unguided块 | Stage observation / 错误 | DiT forwards | DiT batch rows |
| --- | --- | ---: | ---: | ---: | ---: |
| EDS | 03:17:55 | 205 / 494 | 309 / 0 | 6,775 | 71,350 |
| VLS | 03:41:01 | 368 / 459 | 369 / 0 | 4,135 | 39,095 |
| EDS+QD | 04:01:43 | 284 / 554 | 380 / 0 | 8,734 | 98,194 |

三组并行窗口为04:01:50。Worker耗时包括服务等待、模型计算、仿真、渲染及进程开销，不能记作active GPU hours。设备均为H200 NVL；本机映射EDS为GPU0/EGL2，VLS为GPU1/EGL3，EDS+QD为GPU4/EGL6。

EDS与EDS+QD每guided块执行11批搜索评分、176候选评价，模型为21次B16 forward（336 batch rows）；VLS为5次B20 forward（100 batch rows）。unguided均为5次B1 forward。各组轨迹、引导块数和成功停止时点不同，**这不是等总计算预算比较**。

| 方法 | 搜索评分批次 / 候选评价 | 全部记录reward评价 | RBF梯度调用 | Guided select_action平均 |
| --- | ---: | ---: | ---: | ---: |
| EDS | 2,255 / 36,080 | 52,480 | 3,895 | 2.552s |
| VLS | 不适用 | 51,520 | 368 | 0.675s |
| EDS+QD | 3,124 / 49,984 | 72,704 | 5,396 | 2.619s |

全episode reward计数还包括搜索评分之外的工作，不能与176候选预算混用。select_action延迟是程序区间wall time，不是GPU kernel time。VLS的1,472次reward梯度、368次RBF均实际应用；FKD共1,104次调用、368次评分机会，均因ESS条件跳过，实际重采样0次。这是配置允许的自适应行为。

EDS没有活动archive，32,800行父代来源为weighted offspring；EDS+QD的284个guided块全部启用archive，45,440行父代来自archive，284次最终选择来自archive，最终覆盖率均值0.99626、范围0.9375–1。离线审计验证记录一致性；没有据此额外宣称独立证明全部执行tensor。archive每动作块重建，不跨任务学习。

| 方法 | Provider完成 / 失败 | 调用wall latency合计 | Input tokens（其中cached） | Output tokens | 其中reasoning |
| --- | ---: | --- | ---: | ---: | ---: |
| EDS | 329 / 0 | 02:57:04 | 3,183,949（1,975,424） | 37,225 | 13,572 |
| VLS | 389 / 0 | 03:27:43 | 3,761,626（2,345,856） | 47,366 | 19,839 |
| EDS+QD | 400 / 0 | 03:35:21 | 3,869,031（2,421,888） | 46,953 | 18,465 |

每组除Stage observation外，另有10次身份请求和10次新reward生成请求。候选评分在本地运行，不计作API调用。这里是已记录的CLI logical turn；不可见的底层HTTP尝试/重试保持未知。cached是input的子集，reasoning是output的明细，不重复相加，也不据此推算金额。实际使用Codex CLI 0.156.1，请求gpt-6-astra/low；请求字段不独立证明服务端内部模型身份。

## 封存、视频与复查

三份原始v2审计、独立只读重审及最终整合汇总在修改基础设施前完成。17:18:34 UTC封存时，113个受测源码文件仍匹配。随后的生命周期/归档修复属于另一发布与checker身份，不能把上述在线成绩改名归于新commit。

| 原始证据 | SHA-256 |
| --- | --- |
| [三组汇总](../../.worktrees/exp/steering-integration/checks/three-mode-final.json) | `a67ee5e13f7563b86ea8fadd9e55dd5d5b80f53601cdd1e65f1af72a2c2402eb` |
| [封存记录](../../.worktrees/exp/steering-integration/checks/three-mode-final-seal.json) | `14502922a48c5c7ec8de5a59e698a2104d7a241cba2b4e1a9e95a4b51a4e4161` |
| [30份视频索引](../../.worktrees/exp/steering-integration/checks/video-health/index.json) | `93388502f0dda33a1bfd22de7ae56e70e8c4278591029d101b6511cfc807a70a` |

30份终局视频均通过CPU完整解码，帧数与执行动作数一致，10fps，H264；逐视频的原件路径/hash和实际checker身份已登记。该检查确认交付文件可解码与结构完整，不证明所有像素、标注或任务语义正确。视频原件、在线图像/回复、reward程序、源码快照、机制日志及失败证据都保留，未提交大文件到Git。

上表的原始链接指向维护者本机ignored归档，普通clone不包含，也没有已配置的公开下载包。可移植的小型摘要在本页和[JSON](validation/final-results.json)；需要完整复查时由维护者提供字节副本，并按[归档指南](evaluation.md#prepared-infrastructure)在独立报告中重审。原始receipt不可为方便移动路径而改写。

## 与迁移验收的关系

迁移轮也是有效3/10（task 3、8、9），但属于独立受测身份，见[迁移记录](integration-status.md#迁移版-eds完整有效-310)与[README来源](../../README.md#provenance)。公共EDS与迁移轮共5,585个动作，其中5,313个相同，8个任务完整序列相同；task0最后24个、task4最后248个不同。

原始日志显示，差异前相同图像上的新在线回复改变了Stage或guidance时机：task0在step680的抓取判断后改变后续recheck；task4在step464分别进入接触grace与carry阶段，step472开始不同动作。已保存[动作比较](../../.worktrees/exp/steering-integration/checks/eds-common-completed-action-comparison.json)、[task0归因](../../.worktrees/exp/steering-integration/checks/eds-common-task0-online-divergence.json)与[task4归因](../../.worktrees/exp/steering-integration/checks/eds-common-task4-online-divergence.json)。这些日志归因不等于隔离provider波动、身份文字与控制影响的反事实实验；同分不表示轨迹逐位复现。
