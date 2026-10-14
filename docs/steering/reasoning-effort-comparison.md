# Codex 推理强度对照：low → ultra

2026-10-14，main 已改为请求 `gpt-6-astra / ultra`，并完成 VLS、EDS、EDS+QD 各十任务的完整在线评测。**最终统一协议新组：EDS 3/10、VLS 1/10、EDS+QD 0/10。30回合全部有效，零回合级基础设施错误，30份视频通过完整解码。**

| 方法 | 既有 low | 本次 ultra | 新增成功 | 丢失成功 |
|---|---:|---:|---|---|
| EDS | 3/10 | 3/10 | 无 | 无 |
| VLS | 1/10 | 1/10 | 无 | 无 |
| EDS+QD | 1/10 | 0/10 | 无 | [5] |

本轮不支持“提高推理强度即可稳定提高成功率”的结论。EDS保持3/10，VLS保持1/10，EDS+QD丢失task5。首次ultra的完整有效VLS为2/10，成功task3、6；它与本次新组分开保留，不能选用其中较高分代表统一协议的新组。

## 条件与实际改动

在线服务仅使用当前ChatGPT登录的Codex CLI0.156.1，模型名保持`gpt-6-astra`。两类客户端`perception.gemini`与`perception.vlm_agent`均使用`reasoning_effort: ultra`；每任务重新生成身份描述、reward函数和相关阶段内容，随后按实际观测在线判断Stage，生成后的reward在本地评分。没有缓存回复回放，没有Poe或模型降级。请求元数据不独立证明服务端内部模型身份。

任务0–9，seed依次为44、235、43、546、6、621、197、87、151、548。RDT及编码器/DINO、LIBERO资产、初始化与RNG恢复、H8执行、720步上限、算法参数、提示词、Stage/reward合同与180秒物理调用超时保持原样。设备沿用EDS GPU0/EGL2、VLS GPU1/EGL3、EDS+QD GPU4/EGL6，均为H200 NVL。保留单次视觉推理禁工具、禁委派合同。

**传输条件另有明确调整：**首轮EDS task7、EDS+QD task9以及随后EDS整组重测的task2遭遇HTTP429，原先最多重试1次、等待2秒未能恢复。于07:22 UTC停止两组未完成重测，保留其全部数据，然后将两类客户端统一设为最多重试8次、每次等待30秒。完整回复不会因效果不好而重采样；仅未获得完整回复的可恢复传输错误可重试，鉴权/权限/额度耗尽信号仍直接失败。算法和回复接受规则没有改变。

因此最终配置相对low有六处明确差异：两处推理强度、两处重试次数、两处等待时间。旧low的1118个捕获请求均一次物理CLI调用完成，未触发外层重试；不可见的底层HTTP尝试仍不作推断。新组有54个限流请求成功恢复，其中53个用了2次物理CLI调用、1个用了3次；最终均取得有效回复。**零回合错误不等于没有发生限流。**

重试修订在新组结果产生前登记，之后完整重跑三组各10回合。不拼接任务、不替换合法失败、不设达到3/10或更高的筛选门槛。不同方法保留各自默认搜索预算；这也不是等计算预算对比。

## 逐任务结果

| Task | Seed | EDS low→ultra | VLS low→ultra | EDS+QD low→ultra |
|---|---:|---|---|---|
| 0 | 44 | 失败→失败 | 失败→失败 | 失败→失败 |
| 1 | 235 | 失败→失败 | 失败→失败 | 失败→失败 |
| 2 | 43 | 失败→失败 | 失败→失败 | 失败→失败 |
| 3 | 546 | 成功→成功 | 成功→成功 | 失败→失败 |
| 4 | 6 | 失败→失败 | 失败→失败 | 失败→失败 |
| 5 | 621 | 失败→失败 | 失败→失败 | 成功→失败 |
| 6 | 197 | 失败→失败 | 失败→失败 | 失败→失败 |
| 7 | 87 | 失败→失败 | 失败→失败 | 失败→失败 |
| 8 | 151 | 成功→成功 | 失败→失败 | 失败→失败 |
| 9 | 548 | 成功→成功 | 失败→失败 | 失败→失败 |

每个回合的动作数、视频/合同hash及受测身份保存在随Git交付的[结果JSON](validation/reasoning-effort-results.json)。旧low报告见[三模式整合验收](results.md)，原始成绩未改写。

## Stage与动作差异的证据

EDS与low的7个任务具有完全一致的动作序列，包括三个成功任务3、8、9；另三个任务轨迹不同但成败相同。VLS有4个任务完整动作一致，EDS+QD有6个；同分不代表所有轨迹逐位相同。

**EDS+QD task5（seed621）：**low成功，用223个动作；新ultra失败，用720个动作。前88个动作完全一致。第64和80步的全部输入图像一致，low判断已握持并进入Stage2，新ultra判断不确定并留在Stage1；第88步新组重新开启引导，low仍关闭，动作开始分歧。两份reward均通过64个合同探针，最大绝对误差为0，因此没有观察到该回合的reward合同数值错误。

首轮ultra的同一task5在413个动作后成功；它与新组的前256个动作一致。第256步相同图像上，首轮判断不确定、保持引导，新组判断已握持、关闭引导，随后轨迹分开。首轮QD整个cohort因另一个task9的限流无效，该task5仅用于正常完成回合的机制诊断，不构成首轮完整成功率。

**VLS task6（seed197）：**新组与low的720个执行动作完全一致，均失败。首轮ultra成功，用335个动作；它与新组前296个动作一致。第280步相同图像上，首轮判断不确定，新组判断已握持；第296步首轮开启引导、新组关闭，动作开始分歧。两份reward同样在64个探针上最大误差为0。

这些关键请求的全部图像一致，但完整提示词并不一致：差异是首次在线生成的目标身份描述那一行。日志支持“在线描述/判断变化进入Stage与引导控制链并改变动作”的机制解释；没有做固定身份文字、固定回复的反事实干预，不能证明仅身份描述或仅推理强度导致成败，也不能把某个不同的视觉判断直接标为正确。合同探针一致不等于证明所有输入上的函数数学等价。

## 耗时与在线用量

| 方法 | low worker耗时 | ultra worker耗时 | 每请求平均耗时 low→ultra | reasoning tokens low→ultra |
|---|---|---|---:|---:|
| EDS | 03:17:55 | 05:04:37 | 32.29→51.96s | 13,572→142,467 |
| VLS | 03:41:01 | 05:47:33 | 32.04→51.81s | 19,839→186,988 |
| EDS+QD | 04:01:43 | 06:19:00 | 32.30→50.05s | 18,465→204,060 |

新组三组并行的worker窗口约6小时19分。耗时包含仿真、推理、渲染、服务等待及传输恢复，不是active GPU hours；也不能把全部增加归因于ultra推理计算。reasoning是output token的明细，不重复相加或推算金额。

| 方法 | 捕获的完整请求 | 物理CLI调用尝试 | 恢复的请求 | 最终失败回复 |
|---|---:|---:|---:|---:|
| EDS | 328 | 347 | 19 | 0 |
| VLS | 387 | 408 | 20 | 0 |
| EDS+QD | 422 | 437 | 15 | 0 |

现有日志字段`logical_call_attempts`实际上随每次物理CLI调用递增；本表用捕获目录计数区分完整请求与物理尝试，不把重试误计为新的科学回合。

## 所有尝试的去向

本次共启动66个科学回合：首轮30、被停止的两组重测共6、新统一协议30。最终主表只来自最后30个完整有效回合。

| 组别 | 已启动 | 正常完成 | 基础设施中断/错误 | 地位 |
|---|---:|---:|---|---|
| 首轮EDS | 10 | 9 | task7 HTTP429 | 整组无效，保留 |
| 首轮VLS | 10 | 10 | 无 | 独立有效2/10，保留 |
| 首轮EDS+QD | 10 | 9 | task9 HTTP429 | 整组无效，保留 |
| EDS重测（旧传输配置） | 5 | 3 | task2 HTTP429，task4主动停止 | 不计入主表 |
| EDS+QD重测（旧传输配置） | 1 | 0 | task0主动停止 | 不计入主表 |
| 新统一协议三模式 | 30 | 30 | 无回合级错误 | 本页主表 |

首轮VLS和首轮QD在工具层收尾时曾返回143，而其worker已正常结束；原始receipt保留，原因未确定。首轮VLS另经独立只读审计正常返回0并通过，完整有效2/10不依赖该工具层状态。新组三个launcher和worker均返回0。

## 复核、来源与运行入口

受测源码：`c99565de6e34278c14518748d7c608433a4c529a`（main）。初次仅改变推理强度的提交为`6c83eb6a55fa6f92723e58a960d59ee4f606084e`，low受测源码为`33954ead452927fc3168efb610487a688f89169e`。后续报告提交只增加文档/证据摘要，运行时116个文件在封存时与受测快照一致。没有新增worktree或推送远端。

检查包括：初次改档后1442项CPU通过、3项skip；传输修订后250项客户端/配置检查与26项传输审计检查通过；真实Codex图像预检通过；新组三份原审计及独立只读重审均通过（EDS42、VLS43、EDS+QD42项）；30个视频完整CPU解码通过。原有5个未提交用户文件hash未变。

以下ignored证据仅在维护者本机，不随普通clone提供：

- [完整汇总](../../.worktrees/exp/steering-ultra-20261014/checks/ultra-recovery-final.json) · [封存与hash](../../.worktrees/exp/steering-ultra-20261014/checks/ultra-recovery-final-seal.json) · [全部66次尝试](../../.worktrees/exp/steering-ultra-20261014/checks/all-attempts-ledger.json)。
- [逐任务比较](../../.worktrees/exp/steering-ultra-20261014/checks/low-ultra-recovery-comparison.json) · [完整30任务动作/Stage比较](../../.worktrees/exp/steering-ultra-20261014/checks/paired-control-traces-final.json) · [关键请求及身份文字差异](../../.worktrees/exp/steering-ultra-20261014/checks/completed-task-prompt-differences.json)。
- [30份视频索引](../../.worktrees/exp/steering-ultra-20261014/checks/video-health-recovery/index.md) · [在线请求计数和恢复记录](../../.worktrees/exp/steering-ultra-20261014/checks/ultra-final-transport-statistics.json) · [新协议预登记](../../.worktrees/exp/steering-ultra-20261014/checks/transport-recovery-registration.json)。

实验入口为`.worktrees/exp/steering-ultra-20261014/`，其中`runs/`链接到同服务器数据盘`/mnt/data/shared2/hynx/steering-ultra-20261014/runs/`。所有来源组和旧low结果均保留。

安装和准备资产后，使用公共入口：

```bash
python scripts/check_steering.py --local-config configs/local.yaml \
  --output-dir outputs/ultra-preflight-001 --gpu --api

for method in vls eds eds_qd; do
  python scripts/evaluate_steering.py --method "$method" \
    --local-config configs/local.yaml --output-dir "outputs/${method}-ultra-full10-001"
done
```

循环在配置指定的一张空闲GPU上依次执行，目录须不存在；本机实际用三个对应GPU/EGL的local配置并行执行了同一入口。代码、配置、模型和任务资产在运行期间固定。用户按此步骤重新在线生成内容时，成绩可能变化。

## 对后续研究的含义

保留已验证EDS的3/10作为机制开发对照；本次未看到将在线推理强度调到ultra即可提高完整十任务成绩的证据。后续若要隔离agent能力影响，应分别控制身份描述与Stage判断，使用预登记的多次在线重复或配对诊断，再比较算法改动。当前main按要求保持ultra，本轮没有修改QD搜索、档案、reward合同或Stage策略来追求更高分。

每任务只有一个固定seed；初始描述、在线生成和服务日期均可变化，传输协议也经过修订。因此这些结果是当前端到端设置的观测，不能推出普遍能力高低、统计优越性或确定的因果关系。
