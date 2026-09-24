# N4-E1：一次性 transport180 工程条件建议（未授权运行）

本文件仅为 source-only 设计，不是计划、release、恢复证书或新算法。依据协调者提供的公开失败分类与资源快照；未读取新 episode、保护阶段、peer、native payload 或账户信息。源基线为本隔离 V 的 e4ab106（生产算法沿用 W f6a9ab04），旧 N4 90 秒 cohort 永久 incomplete/invalid，不修改其 gate/terminal/cost，也不恢复其晋级。

## 权限与假设边界

原用户 spec §1 授权预算内自主必要工程修复和新工作副本，§4 要求修复后对照重新标记/验证、不能将工程收益归因于 QD，§7.3 只许事前规定的相同身份基础设施恢复。故可准备**新运输工程条件**，必须显式前瞻声明其与原冻结 Stage 运行条件的差别；不能把180秒称为原90秒的同身份恢复。现有9次成功延迟24.214–89.344s只表明截止截断假设值得检验，不证明180秒必要、足够，或远端超时根因。completed∩failed 清理边界不等于计数错误，不能因同一次调用后来有 completed 就删除失败或补造 usage。

建议 Arbor 新建工程节点/condition `N4_E1_TRANSPORT180`，方法名仍 N4，不当作新的 QD 算法候选。链接旧 cohort 的 INVALID 和诊断证据；旧全部成本、known subtotal/Unknown、已完成及未派发 disposition 保留。此节点只准一次新 matched matrix，不把新 original 标为旧 cell 的 retry。旧6条不得充任新 controls/候选，不跨条件合并 success denominator。相同4任务/seed/init已经暴露，只能叫工程条件下的开发再评估，不是独立验证，也不证明工程修复的因果效果。

## 唯一设计与一次性检查门

- 全新12个 original key，task-major：0、3、6、9，每task C0、Q0、N4。使用原 Dev env/policy seeds和init0/逐文件SHA，原任务、720steps、20Hz、8actions、profile、N4 last16 firstargmin、Q0 archive父代/raw Stage、176/11及其它算法开关全部不变。
- 三臂统一 timeout_seconds=180；model、reasoning effort、Stage prompt/输入图像、cache/perception/provider、CLI executable/version、auth方式、one application attempt、内部CLI重试Unknown口径均保持。episode deadline1800 + cleanup40不改；更长Stage等待可能挤占episode时间、改变fallback/实际行为，必须报告完整wall/Stage成本，不能称额外推理免费或放宽episode timeout。
- E的passive lifecycle timing只在此新条件前共同冻结；不回写旧90秒记录/语义，不加Stage探测请求、重试、模型或GPU warmup。CPU synthetic 检查部分事件、180秒超时/取消、completed∩failed、usage缺失以及one-call/原异常行为；诊断时钟不授予scientific-valid或recovery资格。
- **第一task0的完整三臂就是唯一在线工程检查块，并计入12条。** 不另跑可丢弃的成功pilot。全部必须有效、required成本完整、native/raw/Stage/source/action/compute正确，N4有真实archive-parent使用；差异为0或任务失败不触发成功导向早停。通过后同一source/runtime/release规则运行其余9条。
- 全12仍需全部 accepted valid；N4≥2/4且≥C0/Q0；原所有安全、身份、176/11、实质QD和≥1 actual executed-prefix difference门原样。first3不能替代完整矩阵；新工程条件的数据独立报告，不能与原90秒矩阵择优拼接。
- **有界失败规则：** 任一 missing-token timeout仍Unknown、非恢复资格，立即停止该新矩阵尚未派发项，保留原terminal和known costs，cohort INVALID。episode普通1800超时、数值/action、安全、audit、身份错误均不转infra；没有180→360自动升级、补充Stage请求、改名重跑同cell或继续直到成功。精确定义的完整成本 transport failure/监控故障可沿用事前窄恢复类，≤4且每cell≤1，完全相同新工程身份；未知token不在其中。一次新矩阵若再次失效，返回有限CPU工程根因审查；任何后续运行都需要新的实质工程证据及事前有限设计，不能由本合同自动授权或重复同一timeout ladder。这不等于关闭用户整个研究目标。

## 最小未来接口边界（现在不实现）

当前 `qd_ed_final_runner.stage_overrides` 硬校90秒；`CODEX_STAGE_CONDITION` 同时写method label、terminal和compute。`core.codex_stage` 本来接受(0,600]配置并用该值communicate，无需为180更改其执行算法。不能只改runtime、全局放宽90任意值或覆盖旧tag。新入口需允许**只有SHA绑定的新工程contract**的180值及独立condition tag；旧90路径和所有旧身份继续exact。所有 `stage_overrides` 调用点（validate_plan/build_command/provider验证/episode_compute/result复核）与记录tag必须一致，新条件generic/direct dispatch在没有专用live lease+release时关闭。

新增dedicated工程plan/supervisor/report（或封闭版本化适配器）应复用原N4 native audit和算术函数，而不是用旧COHORT validator替新cohort合法化。新增绑定：原算法/profile/helper/decoder/auditor/protocol SHA、工程protocol、新runtime/provider public-config SHA、condition/cohort、原seed/init/model/dependency映射、私有resource authority、全部原生source inventory、预先固定12行和4base+8dev分配。`episode_identity` 中iteration变成新cohort，raw event显式携带engineering condition及不可混池的frozen binding；保留实际dispatch presence、全部invalid/predispatch和parent recovery lineage。

Source map逐文件列出必要transport/observability与tooling delta；算法/core QD/EDS、Stage输入/normalization/prompt、模型和环境字节不改。E timing涉及的实际文件待其最终实现后精确枚举，不以目录豁免。新runtime从原manifest派生，只有公开timeout/condition/公共policy SHA及必要source evidence变更；GPU3 UUID/PCI/boot/driver、model inventory、cache、native dependencies不变。现有同boot工程proof按等价范围复用、原成本不重计；若确需新health，必须先列合同并计入新local/global小时，不能由queue隐式新增。

旧 reporter固定COHORT/文档SHA/资源分配，不能原样读取新矩阵。新report独立固定12行、自己的journal excerpt/授权/source/各planrevision，保留invalid和inflight成本Unknown。原native consumer auditor可不变；每guided逐步native alignment/11×16/10parent/actualm、Stage raw通道照旧。新矩阵通过只产生其自己的Dev工程条件证书；旧protected准备工具硬绑定旧N4 report，**不能直接复用其晋级证书**。任何保护阶段部署仍需新条件对应的明确source/runtime/report映射，在首次保护披露前审查冻结，保持60/40规模和10/20、5/10门，不新增本次保护授权。

## 资源情景（不是当前准入保证）

协调者快照：private80dispatched、11.403172863324977GPUh，base16/dev58/rec6。按原caps20/100/60/40/20，保护60+40原始attempt与14+10h均不动。新12 originals=4base+8dev →92总、base20/dev66/rec6；最多4合法recovery →96总、rec10。再保留100保护originals为196≤240；没有candidate进入baseline、历史重标或保护借用。四个C0将恰好用尽baseline，之后本方案没有再起第二套同配置完整12矩阵的baseline余量。

此快照 unprotected小时=48−24−11.403172863324977=12.596827136675023。local8.5h更紧；12个1840s窗口=6.133333333333333h，16窗口=8.177777777777777h，local最多余1160s给新关联health（若每条都用足窗口）。这只是容量情景：private其他新增费用、实际局部成本/未知资源cost可使真实可用更少；每dispatch在真实GPU3私有lease内重新核算全部ledger，拒绝不够完整1800+40的行，绝不缩短或保证能完成。GPU wall可准确计入，即使token仍Unknown；两种成本概念不得互相补足。新释放前需freeze+预算/源/设备准入；本文件没有执行效力。
