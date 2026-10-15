# N30 first-active lineage Phase A：元数据定位完成

**两个接受格均覆盖，尚未读取/哈希/解码任何 tensor。** Root闭合为 REJECT_NUMERIC_DEV_FUTILITY、三臂各0/2；本次独立比对其hash-bound source/plan/result、两格accepted refs、terminal/context/receipt/audit身份及receipt/index绑定，不重放原native证据。

| task | attempt后缀 | earliest active | guided / active | 后续候选容器 | stat字节 |
|---|---|---|---|---|---|
| 0 | 4300bcf89485 | step8 / e0:d2:s8 | 24 / 14 | 17 | 12,136,589 |
| 1 | 1e52b07e1725 | step8 / e0:d2:s8 | 6 / 4 | 17 | 12,137,101 |

两份完整index各2250容器，仅stat全部4500个已列payload，共378,217,122 bytes；无symlink/traversal，全部index中的payload SHA与原receipt元数据条目一致，但**没有重新测payload SHA**。固定两个decision分别包含11 canonical批、10 archive/actual-parent轮、一个native selection/decode/commit与8个executed_action/outcome/ack。元数据sequence验证commit早于实际action；8步均符合dispatch→executed_action→pre_reset_outcome→ack→returned，且step8..15连续。后续固定34容器合计 **24,273,690 bytes**，精确路径、stat身份、既有SHA与共存事件见 `input-bindings.disabled.v1.json`。

可核验层次：
- **本阶段独立核验**：两个接受attempt的固定source/plan/输出身份、root-ref哈希、receipt/context/audit引用一致；全部metrics中最早active规则；完整index顺序与所需事件覆盖；索引和receipt哈希相符；容器真实stat大小/无路径逃逸。
- **继承原worker attestation**：previous native winner/进展触发门、输入字段数值与source之间的一致性、原native audit；没有因为metadata检查通过就重新宣布数值验证。
- **仍未知**：插入行是否进入archive、哪些parent/child能唯一绑定、最终选中是否直接或单亲后代、实际8步数值响应。索引只有事件身份，不含tensor shape/值或parent indices；必须等新的有界decode权限。原archive insertion occurrences明确未记录，即使解码也可能只能得唯一内容支持的推断或歧义，不能伪造唯一祖先。

## 后续读取为什么足够有限

每格只需 bundle_000026.pt 的完整decision，加八个action与八个outcome/ack小容器。大容器另共存2496 projection_origin、16 scoring_inputs、256 provider_return、16 scoring_aggregate、16 effective_quality；完整解码必然触及其存储，但不得分析/导出非目标字段。原status共存类型完整性依赖source/index，未做ZIP或storage读取。disabled协议提出单进程CPU120s/wall120s、16GiB AS、34文件一次读取、128MiB ZIP/storage上限；这些执行额度尚未批准。

当前chunk的step8 target snapshot/source身份在同一decision中可定位，可与steps8..15真实反馈描述性关联。它不是实时目标轨迹/抓取标签。触发插入的上一chunk0进展继续继承原worker审计；当前集合不独立重算0..7门。若将来改变问题为重算旧门，需另行冻结额外旧context/反馈，不追加本次读取。

**谱系不等于完整因果影响。** QD bounds/occupancy/sparse allocation与ED RBF可能通过population耦合让未成为最终祖先的行间接改变别的候选。因此无可确认直接后代不能解释为对最终动作零影响或机制无效；本次不准备反事实模型/评分回放。只观察两个first-active检查点，也不能概括整个episode。未提名/实施新算法。

## 来源与失败/资源

`input-read-manifest-v1.json`列32个唯一既有输入、51次读取记录（含scope闭合重哈希），既有元数据与静态源码保守合计19,298,082 bytes。policy仅展示相关源码窗口；其完整文件字节hash用冻结480文件manifest核验，其余实际检查的源码同样绑定6292fc8。`source-binding-v1.json`保存核对与窗口。未读取r2文件中的其它嵌套历史refs/控制臂输出/保护数据。

首轮把静态Markdown错误按JSON解析，留下 `inventory_metadata_v1.py`、失败日志及资源；仅读到已允许静态报告，无index/payload。修正为独立v2后metadata通过；index reader独立完成、无重扫index。两个成功reader均guard0、tensor open/hash/decode=0，无Torch/NumPy/生产导入、测试、网络/API/GPU/仿真。所有命令2 CPU affinity、线程环境上限2。

已测输入/源码/reader CPU合计0.917416297s，加打包进程另记；小型脚本生成和自有输出检视命令未逐一CPU计时，shell/解释器启动开销也未全计入，因此不冒称精确全流程CPU值。实际输入重复读取全部入manifest；自有派生JSON的检视另作保守read allowance。上限300CPU秒/128MiB，不曾执行耗时子进程或新测试。

产物供root独立审阅。**Phase A结束；decode仍disabled，等待单独release。**
