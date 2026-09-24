# N1W 批准执行协议

用户明确批准：“批准 N1W 修复方案并继续 GPU2 实验（建议）”。
已批准方案 `n1w-transport-fallback-proposal.md` 的内容及SHA保留不变；
其中“待批准”标签成为历史。授权记录：`/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/resource/n1w-approved/authorization.json`，
SHA `445306c7023e0cba6a5affeaf2afab5af91bb393b9b39bf64341ba17b2c11258`。

共享分组上限13/125/60/40/12，总250次/48GPU小时，验证60次/14小时、
正式40次/10小时保护不变。授权时已用115次/16.16969853044709GPU小时，
开发95、恢复7，正好支持新30主回合+5恢复，剩余非保护时间7.8303014696小时。
两个工作树同步同一不可变授权；GPU2优先、共享单worker，GPU3队列保持暂停。

新N1W独立cohort：task0..9每task先按原顺序执行C0/Q0，再N1；不合并旧轮次。
三组仅共用新的Stage接受规则`completed_transport_fallback_v1`，公共SHA
`47b97a211a069a6f104f7928e32aeaa0f72031e7a948ee320ee1ef3416fdd6d2`。
仅允许唯一turn中、最终消息前、至多1个完整匹配CLI固定前缀的回退error item，
之后必须依次得到唯一合法JSON、完整usage、零退出码，无其他错误。保持原始
item类型/摘要/回退分类。180秒、原CLI/模型/强度/图像/提示/一次应用层调用不变。

N1继续只改变目标距离×夹爪正向指令占比描述符；RDT权重、初始状态、Dev种子、
720步/1800秒、176候选/11评分批次保持。前2个N1是实施检查、计入10回合，
不按成败筛选。N1完整10有效且>=5/10、不低于C0/Q0、有实际QD活动，才进入
原独立验证和正式验收，否则关闭为未达标，不追加未注册候选。

仅对明确未完成的`codex_timeout`且身份/成本/不变量/GPU检查均通过的当前
N1W尝试，在首次终态写入时标记可恢复。每cell最多1次、全N1W最多5次，
原初始化/源码/种子不变、明确retry_of、计入recovery和全局成本；未知token
保持UNKNOWN。合法任务失败不重试，其他非恢复错误/同cell再次失败/恢复耗尽/
预算保护触发即停。旧N1V终态不重新分类，旧恢复次数不混入N1W额度。

执行仍为GPU2/EGL1、120秒空闲准入；复用同boot已验证CUDA/EGL证据，无新增
GPU探针或在线合成Stage调用。完整CPU检查与新源码/runtime/plan冻结通过后派发。
