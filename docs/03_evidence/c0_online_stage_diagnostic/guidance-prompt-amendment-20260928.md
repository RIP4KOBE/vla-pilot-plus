# 单变量 Stage guidance 提示词补充试验

日期：2026-09-28。用户已明确要求继续完成获批 Codex Stage 排查，不再以原预算为停点。此补充仍限于 C0 Stage；不改 RDT、ED、QD、任务、种子、缓存或历史结果。

原四组同图筛选 A（JSON/low）、B（三行文本/low）、C（JSON/medium）、D（JSON/high）检验格式与推理强度。A 与 B 的 72 次有效成对决策只差 2 次、且都在同一张 guidance 边界画面。已完成的 C 和进行中的 D 也暂未显示系统性 stage 改善。另一方面，原 Codex 在线结果比历史 Poe 成功轨迹更频繁输出 stage 1/guidance off；task 9 的固定画面显示目标仍未抓取，Poe 维持 guidance on 而 Codex 关闭。原模板明确把“夹爪已接近目标”列为关引导条件，并把 reward 上升暗示为可关引导，但该 reward 是本地轨迹代理而非抓取完成真值。因此单独检验提示词的 guidance 持续规则有直接证据基础。

变体 E 使用同一 `gpt-6-astra`、`low`、JSON 输出；仅在新模板 `vlm_query/stage_template_codex_guidance_persistence_v1.txt` 中澄清：stage 1 目标未确认抓取时，即使夹爪接近或本地 reward 高也继续 guidance。已用静态检查确认它与原模板恰好只有声明的四处文字替换。v6 传输接受规则仅处理已完成回复，不改变模型输入或合法 Stage 决策；所有传输失败仍单独计数。

先在相同的 24 个原始 PNG/任务提示词上每个重复 3 次，比较 stage 1/off 数、历史成功任务决策、与原轨迹一致性及同图稳定性；若有明确改善且无明显错误的视觉晋级，再把该单一条件扩展至其余 103 个请求。E 是新的 Codex 提示协议，不得称为对历史 Poe/Gemini 语义的严格复现。最终成功率仍由随后冻结的 GPU2 十任务闭环测量决定。
