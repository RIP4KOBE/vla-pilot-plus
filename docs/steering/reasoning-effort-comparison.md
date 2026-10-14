# Codex 推理强度对照：low → ultra

2026-10-14，按用户要求在 main 开展 VLS、EDS、EDS+QD 各10个完整在线回合。当前状态：首轮遭遇 Codex HTTP429，正在冻结加强传输恢复的统一重测协议。首轮 VLS 完整有效，为2/10；EDS和EDS+QD各有一个基础设施错误，不能登记完整成功率。此前完整 low 对照为 EDS 3/10、VLS 1/10、EDS+QD 1/10，详见[原始结果](results.md)。原始数据、配置、审计和成绩保持不变。

## 固定条件

模型保持 `gpt-6-astra`，当前 ChatGPT 登录、Codex CLI 0.156.1；将公共配置中 `perception.gemini.reasoning_effort` 和 `perception.vlm_agent.reasoning_effort` 同时从 `low` 改为 `ultra`。因此新 reward 程序生成、身份描述和每次在线 Stage 观察均使用 ultra；生成后的 reward 在本地评分。

任务为 LIBERO ObjectSwap OOD，task 0–9，seed 依次为44、235、43、546、6、621、197、87、151、548。RDT/编码器/DINO资产、LIBERO资产、初始化状态与RNG恢复、三模式搜索参数、H8动作执行、720步上限、提示词、Stage合同及180秒请求超时保持原样。保留单次视觉推理的禁工具/禁委派合同；不额外启用CLI工具或多代理。

### 传输协议修订（重测开始前登记）

首轮 EDS task7、EDS+QD task9 以及随后 EDS 整组重测的 task2 均因 HTTP429 耗尽现有重试而中止回合。原配置最多重试1次、初始等待2秒。两组尚在运行的独立重测于07:22 UTC停止，原始结果完整保留；EDS重测已完成3个正常回合并记录1个错误，EDS+QD重测尚未完成首回合。

两类 Codex 客户端统一改为最多重试8次、每次等待30秒（最多9次物理调用），采用已有传输机制，不修改算法、提示词、Stage/reward判断或回复接受规则。仅未获得完整回复的可恢复传输错误可以重试；鉴权、权限、额度耗尽信号直接失败。完整回复不因任务效果不佳而重采样，耗尽重试仍记基础设施错误。

此后在新冻结提交上完整重跑三模式各10回合，作为统一协议的新组；不从旧组中拼接任务，不按分数选择保留哪组。旧 VLS 2/10 独立报告。与 low 的最终比较将明确列出推理强度和传输参数两类差异，不能声称配置只变化了推理强度。旧 low 的1118个捕获请求均一次物理调用完成，未触发外层重试；这是已观测事实，不保证在另一服务时段也如此。

本机模型能力清单列出 ultra。[Codex 官方配置说明](https://learn.chatgpt.com/docs/config-file/config-reference)也说明推理档位取决于模型和客户端；本次仍以同一实际视觉接口预检为准，不以配置字符串证明服务可用或服务端内部模型身份。

## 运行与有效性

沿用上一轮同型号设备和映射：EDS GPU0/EGL2、VLS GPU1/EGL3、EDS+QD GPU4/EGL6；开始前确认空闲，不停止其他任务。三组分别运行、保存独立目录，运行期间冻结代码和配置。审计绑定 manifest、两类在线客户端及该回合冻结的配置，兼容旧 low 数据，但拒绝 low/ultra 混用。

本轮需要30个主回合。合法任务失败保留，不重试、不挑选成功回合、不拼接不同配置。预检不计入成功率；基础设施错误与合法任务失败分开记录。此轮没有“必须达到3/10”的性能验收门槛，完整有效的低分同样是研究结果。

实验管理入口为仓库根下 `.worktrees/exp/steering-ultra-20261014/`。系统盘剩余空间不足以安全容纳三组新视频，故其 `runs/` 链接到同服务器 `/mnt/data/shared2/hynx/steering-ultra-20261014/runs/`；没有新增worktree。目录中保存预检、逐组日志、配置、源码哈希、实时进度、完整视频及最终比较，均不覆盖上一轮。

在安装/资产准备完成后，公共入口仍为：

```bash
python scripts/check_steering.py --local-config configs/local.yaml \
  --output-dir outputs/ultra-preflight-001 --gpu --api

for method in vls eds eds_qd; do
  python scripts/evaluate_steering.py --method "$method" \
    --local-config configs/local.yaml --output-dir "outputs/${method}-ultra-full10-001"
done
```

以上循环在一张已分配GPU上依次执行；本机本轮使用三个分别指定设备的local配置并行执行。每个输出目录须不存在，命令默认包含全部10个任务。

## 预先确定的比较指标

- 主指标：每方法完整有效的成功数/10，以及对应每个task/seed的low→ultra变化。
- 变化明细：新增成功、丢失成功、共同成功与共同失败，不仅报告总分。
- 机制与服务：引导块、Stage切换/请求/错误、reward合同和机制审计、token与请求wall latency；区分本地推理计算和服务等待。
- 归因边界：每任务一个固定seed；新生成的回复存在波动，服务日期也不同。结果检验这一推理档位设置的实际影响，不能仅凭一次十任务比较证明普遍的能力提升或严格因果关系。

最终成绩须由完整审计确认后更新到本页；当前不登记任何未完成回合的成功率。
