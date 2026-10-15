from pathlib import Path
import csv,difflib,hashlib,json
H=Path(__file__).resolve().parent;d=json.loads((H/'result-v1.json').read_text());scope=json.loads((H/'read-scope-v1.json').read_text())
assert d['comparison_count']==2 and d['coverage']=={'steps_total':2880,'steps_known':2876,'steps_unknown':4,'blocks_total':360,'blocks_known':356,'blocks_unknown':4}
assert len(d['steps'])==2880 and len(d['blocks'])==360
assert all(x['same_controller_context']['task_index']==x['same_controller_context']['episode_index']==0 for x in d['metadata'])
for key in ['step_summaries','block_summaries']:
 rows=d[key];allrow=next(r for r in rows if r['task']=='all' and r['dimension']=='all')
 for f in ['A','B']:
  assert sum(r[f]['known'] for r in rows if type(r['task']) is int and r['dimension']=='all')==allrow[f]['known']
  assert sum(r[f]['unknown'] for r in rows if type(r['task']) is int and r['dimension']=='all')==4
fmt=lambda v:'Unknown' if v is None else '['+', '.join(f'{1000*x:.4f}' for x in v)+']'
res=lambda s:' / '.join(f'{1000*s[k]:.4f}' if s[k] is not None else 'Unknown' for k in ['euclidean_residual_mean_m','euclidean_residual_median_m','euclidean_residual_p90_m'])
for a,b in [('extract_cpu_v1.py','extract_cpu_v2.py'),('extract_cpu_v2.py','extract_cpu_v3.py')]:
 target=H/(a.replace('.py','')+'-to-'+b.replace('.py','')+'.diff');target.write_text(''.join(difflib.unified_diff((H/a).read_text().splitlines(True),(H/b).read_text().splitlines(True),fromfile=a,tofile=b)))
account={'schema':'n23-scale-extraction-attempt-account-v1','initial_extraction':{'script':'extract_cpu_v1.py','status':'failed_extra_compound_identity_predicate','trigger_subcondition':'Unknown from v1 log; it did not print actual context','metric_files_read_tasks':[0,1]},'engineering_rerun_1':{'script':'extract_cpu_v2.py','status':'failed_local_global_task_index_assumption','actual_failed_context_episode_index':0,'actual_failed_context_local_task_index':0,'metric_files_read_tasks':[0,1]},'engineering_rerun_2':{'script':'extract_cpu_v3.py','status':'passed','metric_files_read_tasks':[0,1,2,3],'elapsed_seconds':d['elapsed_seconds']},'engineering_reruns_used':2,'engineering_reruns_remaining':0,'metadata_hash_freeze_reads_by_task':[1,1,1,1],'extraction_metric_file_reads_by_task':[3,3,1,1],'total_metric_file_read_count_including_hash_freeze':12,'new_tensor_bundle_reads':0,'formula_changes':0,'sample_changes':0,'bound_changes':0,'root_task_binding_review_reference':'root reported original frozen plan SHA acd2b2c639f7756cdc353b6a7eea8c93a4d735a8ce6ee25838d9502c938d07f0 already reviewed; executor did not newly read that plan'}
(H/'extraction-attempt-account-v1.json').write_text(json.dumps(account,indent=2)+'\n')
t='''# N23 实际控制器缩放边界与两种固定增量公式

**实际记录的控制器平移输出边界确实是 ±0.05，而 N23 内部仍使用 0.01；但是 0.05 的 affine scaled_delta 不能直接当作实际末端位移。** 两个预先限定公式与同一执行记录比较时，A=0.01 的残差更小。这既不证明0.01是最优参数，也不支持仅凭控制器边界就将N23改为0.05并宣称修复。

共2876个已知起点的单步：A/B平均欧氏残差分别 **4.340 / 28.424 mm**；356个已知起点的八步总量：分别 **29.863 / 215.318 mm**。这些都是描述性残差，没有新的quality、候选排序、控制器动作、参数拟合或成功率推断。

## 输入和实际参数核验

独立scope SHA256 `b2802ce980098453df6a75bc9e426ac1443bae9c8749cb5067ecaee128f94134`；冻结read manifest SHA256 `82848e3bf21292449f05d3648887084ecb249eab3c94503184069de89cc954d3`。新实际输入只有四个明确已完成attempt的 `eds_metrics.jsonl`，只读取其中 qd_actuator_metadata 与global_step/episode身份字段。动作和EEF完全来自已闭合proprioception结果 SHA256 `d658ea7ab4a053a69b019dfa39d20035948e8c5d3af75ce1896f0d325e96f02a`，没有新tensor bundle、额外任务或运行中输入。

139条实际metadata（按task为15/54/68/2）均记录：

- class=`robosuite.controllers.osc.OperationalSpaceController`，name=`OSC_POSE`，fixed impedance、delta=true、orientation=true、control_dim=6。
- 六维input min/max为−1/+1；output前三维为−0.05/+0.05，后三维为−0.5/+0.5；记录bounds dtype均float64。
- 每个attempt内pid/adapter/wrapper/environment/controller/episode/inner-reset的完整context恒定；set_goal/scale_action的qualname、实际source path和完整文件SHA与本次静态文件逐一一致。

| benchmark task | guided快照数 | 无边界快照的unguided块 | 实际local task_index | 实际episode_index | inner_reset_generation |
|---:|---:|---:|---:|---:|---:|
'''
for m in d['metadata']:
 c=m['same_controller_context'];t+=f"| {m['task']} | {m['recorded_snapshot_count']} | {m['unguided_boundaries_without_snapshot']} | {c['task_index']} | {c['episode_index']} | {c['inner_reset_generation']} |\n"
t+='''
全部实际context原值（含process/controller实例）在JSON保留。`task_index`是filtered environment列表中的局部索引，不能等同benchmark task ID；四个隔离attempt局部索引均0。全局task绑定使用事前明确的四attempt manifest、相同已闭合native/proprioception引用，未拿局部0冒充全局task证明。root已另行审查原40格task-major计划；本执行器没有新增读取该计划。

**覆盖边界：**139个guided边界有当时的static metadata快照；其余221个unguided边界无逐步快照。B用于unguided样本时，只是明确沿用该attempt一致bounds的假设性重建，并非每个unguided动作的live controller参数都被本次核验。guided边界的static快照也不是每个物理substep的最终目标记录。

## 静态源码所能证明的语义

`core/qd_actuator_clipped_quality.py` 的内部几何为 `origin+cumsum(clip(translations,-1,1)*.01)`；原 `libero_adapter.py` projector也使用 `ACTION_SCALE_POS=0.01`。decoder只抽取指定7维并二值化夹爪，平移量由记录的executed_action给出。环境wrapper从 installed OSC_POSE config加载控制器，但本结论**没有仅凭默认文件认定实际bounds**，而是由上述139条实际实例metadata确认。

已绑定的 `Controller.scale_action` 对input做componentwise clip，再按bounds midpoint/range作affine变换。fixed/delta模式的 `OperationalSpaceController.set_goal` 调用它；之后将scaled_delta[:3]与更新后的 `self.ee_pos` 交给 `set_goal_position(...position_limit=self.position_limits,set_pos=...)`。

因此B严格定义为 **实际记录bounds确定的 affine scaled_delta（位置限幅之前）**。live position_limits、cached action_scale/input/output transforms、最终goal_pos及控制器内部substep未记录，全部保留 Unknown。默认config的null不能代替live position_limits证据，源码有缓存计算也不等于本次记录了缓存内容。B是从bounds重建的变换表达式，不宣称位级重现缓存计算或观测到了最后goal。

每步set_goal使用当时控制器EEF参考，而不是保证将上一目标完整实现。把8个目标增量相加也不等于控制器实际执行了一个由起点出发的八步积分轨迹。记录的pre/poststep EEF是观察量，本次没有新增记录控制器内部每次update的精确origin。

## 两个唯一比较公式

对每个记录的executed xyz action，预先限定：

`A = 0.01 × clip(action_xyz, −1, 1)`

`B = (clip(action_xyz, input_min, input_max) − midpoint_input) × |output_range|/|input_range| + midpoint_output`

本次实际bounds使B数学上化为 `0.05×clip(action_xyz,−1,1)`。没有第三个scale，没有最小二乘或阈值拟合。所有计算使用CPU Python FP64保存值描述公式，**不是native GPU BF16 projection/quality/排名复现**。

残差符号统一为“公式增量 − 观察EEF位移”。单步观察为同reset连续两次poststep之差；八步观察为块开始前的记录到第八步后记录的差，预测量为该块8个固定公式增量之和。4个episode首步起点缺失，单步2876/2880 known；4个首块起点缺失，八步356/360 known。Unknown样本保持分母，不填0。

所有表的残差单位为 **mm**。median为普通中位数；p90使用排序后位置 `(n−1)×0.9` 的线性插值。signed mean xyz与欧氏残差是不同统计，前者可以方向抵消。

## 单步：按task和总体

| task | known / total（Unknown） | A signed mean xyz | A mean / median / p90 | B signed mean xyz | B mean / median / p90 |
|---|---|---|---|---|---|
'''
for r in [r for r in d['step_summaries'] if r['dimension']=='all']:
 a,b=r['A'],r['B'];t+=f"| {r['task']} | {a['known']} / {a['total']}（{a['unknown']}） | {fmt(a['signed_mean_xyz_residual_m'])} | {res(a)} | {fmt(b['signed_mean_xyz_residual_m'])} | {res(b)} |\n"
t+='''
## 八步总量：按task和总体

| task | known / total（Unknown） | A signed mean xyz | A mean / median / p90 | B signed mean xyz | B mean / median / p90 |
|---|---|---|---|---|---|
'''
for r in [r for r in d['block_summaries'] if r['dimension']=='all']:
 a,b=r['A'],r['B'];t+=f"| {r['task']} | {a['known']} / {a['total']}（{a['unknown']}） | {fmt(a['signed_mean_xyz_residual_m'])} | {res(a)} | {fmt(b['signed_mean_xyz_residual_m'])} | {res(b)} |\n"
t+='''
## 全部样本的guided与夹爪分组

guided分组使用已记录当次decision标记。单步gripper组按该实际动作符号；八步按0、1..7、8个正向命令分成全非正向、mixed、全正向。这些与运动量或成功无关，不拟合阈值。两个维度是分别分组，不能把行数相加当独立样本；完整per-task和guided×gripper交叉表在CSV/JSON保存。

| 观察单位 | 分组 | known / total（Unknown） | A signed mean xyz | A mean / median / p90 | B signed mean xyz | B mean / median / p90 |
|---|---|---|---|---|---|---|
'''
for unit,key in [('one_step','step_summaries'),('eight_steps','block_summaries')]:
 for r in d[key]:
  if r['task']=='all' and r['dimension'] in ['guidance','commanded_gripper']:
   a,b=r['A'],r['B'];t+=f"| {unit} | {r['dimension']}:{r['group']} | {a['known']} / {a['total']}（{a['unknown']}） | {fmt(a['signed_mean_xyz_residual_m'])} | {res(a)} | {fmt(b['signed_mean_xyz_residual_m'])} | {res(b)} |\n"
t+='''
没有选择更有利的任务或只展示guided：每任务、总体、guided/unguided、命令组、交叉组都已保存，包括空交叉组与Unknown分母。注意unguided B的额外静态参数沿用假设；不得将其描述为当步live目标观测。

## 解释边界

实际bounds证明“内部0.01”与“由实际bounds重建的0.05目标增量”不是同一量，但目标语义匹配并不保证短时真实运动匹配。阻抗控制、姿态耦合、状态更新、可能的接触及跟踪动态都可能使目标增量之和偏离实际轨迹；本次没有读取接触、奖励、成功或物体真值来区分原因。

A残差更小也不能把0.01解释成已找到最佳动力学参数或成功率最优proxy。只比较两个事前指定公式，其他scale未测试；误差衡量不是研究目标的替代品。本记录不支持直接修改N23为0.05、重排候选，或从任一残差推断任务收益。任何后继候选尚未实现或放行。

## 两次工程提取失败与最终关闭

范围原允许最多2次工程重跑，本次已用完：

1. v1在额外的compound identity谓词失败。它错误地要求`episode_index==0`且`local task_index==benchmark ordinal`。v1日志没打印context，实际触发的子条件单靠该日志为 **Unknown**；最初关于episode索引的解释是源码层面推测，不能记为观察到非零episode。
2. v2只移除无依据的episode==0限制并打印context，再因局部/全局task等同假设失败；实际打印`episode_index=0, task_index=0`。允许源码清楚区分filtered列表的`task_idx`与`current_env.task_id`。
3. v3只纠正局部/全局索引绑定，同时加强闭合derived actions的attempt_id与冻结manifest一致性核验。local task_index、episode_index等仍为非负整数，完整context在同attempt恒定，method/source/bounds原门全部保留。实际四attempt局部task和episode都为0。最终通过，没有发现实际bounds或实例身份漂移。

v1/v2源码、异常、两次修订JSON和逐行diff全部保留。没有改变公式、bounds、阈值、样本或数据范围。新metrics读取计数：冻结hash各任务1次；v1读取tasks0/1，v2读取tasks0/1，v3读取全部4个；合计12次文件读取（8次提取+4次hash冻结），只限同四个允许路径。新tensor bundle读取0。最终提取耗时0.246548秒，低于120秒；Python单线程（上限2），CUDA不可见、未导入Torch/环境/provider/runtime，process/network/import/path guard无触发。

报告工作只读取本目录导出结果，不再读实际metrics或native记录。root提供已审查计划哈希作为绑定说明，不是本执行器新增实际输入。此screen已闭合、无剩余工程重跑，不改变source/controller/state/ledger/budget或在线实验。

## 输出与复现

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python extract_cpu_v3.py
```

仅供审查代码，已闭合目录拒绝覆盖结果，不应再次执行。所有输入哈希在read manifest；源码链每条actual method也保留原引用。输出清单：

| 文件 | SHA256 |
|---|---|
'''
for p in sorted(H.iterdir()):
 if p.is_file():t+=f"| `{p.name}` | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |\n"
f=H/'conclusion-v1.md';assert not f.exists();f.write_text(t)
m={'schema':'n23-actuator-goal-scale-output-manifest-v1','files':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(H.iterdir()) if p.is_file()]};o=H/'output-manifest-v1.json';o.write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps({'conclusion_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256(o.read_bytes()).hexdigest(),'files':len(m['files'])},indent=2))
