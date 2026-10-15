"""Render only already derived outputs; never reopen native evidence."""
from pathlib import Path
import hashlib,json,collections,csv
H=Path(__file__).resolve().parent;d=json.loads((H/'result-v1.json').read_text())
check=lambda x: x or (_ for _ in ()).throw(ValueError('derived consistency'))
check(d['coverage']=={'attempts':4,'transitions':2880,'prefixes':360,'command_sign_runs':171,'strict_pairs':15})
check(sum(r['actions'] for r in d['command_runs'])==2880)
check(all(p['actions']==8 for p in d['prefixes']))
check(sum(a['positive_actions']+a['negative_actions'] for a in d['attempts'])==2880)
check(sum(p['previous_executed_prefix']['positive_commands']==8 for p in d['strict_pairs'])==11)
check(sum(p['next_prefix_category']=='retained_all_positive' for p in d['strict_pairs'])==5)
fmt=lambda x:'Unknown' if x is None else '['+', '.join(f'{v:.8f}' for v in x)+']'
scalar=lambda x:'Unknown' if x is None else f'{x:.8g}'
# The detail tables retain complete run/prefix joint endpoints, ranges and changes.
for name,rows in [('command-runs-detail-v1.csv',d['command_runs']),('prefixes-detail-v1.csv',d['prefixes'])]:
 compact=[]
 for r in rows:
  x={k:r[k] for k in ['task','start_step','end_step','actions','start_status','eef_net_displacement_m','eef_observed_path_length_m']}
  x['command_or_prefix']=r.get('command',r.get('actual_command_bits'))
  for field in ['robot0_gripper_qpos','robot0_gripper_qvel','robot0_eef_pos']:
   for k in ['start','end','net_change']:x[field+'_'+k]=json.dumps(r[field][k])
   x[field+'_min']=json.dumps(r[field]['observed_range']['min']);x[field+'_max']=json.dumps(r[field]['observed_range']['max'])
  compact.append(x)
 with (H/name).open('w',newline='') as fp:
  w=csv.DictWriter(fp,fieldnames=list(compact[0]));w.writeheader();w.writerows(compact)
t='''# N23 task0..3：实际夹爪与末端本体感知

本次有界观察已完成：**2880 个已有实际动作、360 个八步块、171 段连续同号命令，全部四项本体感知字段完整且有限。** 这补齐了原计划连续性观察的实际运动描述，但不能把计划变化解释为抓取损害。

特别是旧尾部全正向的 15 对中，上一段**实际**命令只有 11 对全正向，其余 4 对混合。两例下一段全非正向（task2 272→280、304→312），上一段实际命令分别是 `00000011`、`01111111`，不是两次已知稳定握持后的释放。更一般地，本体感知数据也没有提供物体接触/抓取标签；旧未执行尾部的效果仍然 Unknown。

## 范围、覆盖与关联

这是独立授权的执行本体感知 OBSERVE。scope SHA256 `6079124108909718e89d0158bb7a4c13bf03e3f23cffdc0981162fd34740943d`，四已完成 N23 Dev attempts manifest SHA256 `cca36ad827d720aa7973e808d86db7fb00da961f44ba4203f57123626adc39f4`。旧的两次 task0 screen 和 planned-tail screen 均不改写。

先读取允许的 index 元数据，冻结 `read-scope-v1.json`，SHA256 `562c021300c743db343975ea63c20cb7be451839ac22464902e48943d9e31eab`。清单绑定前一闭合结果及其 native terminal/receipt/audit/index 引用、源 `51104470983cdbafd08feb87f2f39b7553779405` 和相关源码字节。随后主 screen 严格读取清单中 9000 个 bundle，每个一次（各任务 2250）。52.251815 秒内完成，低于180秒限额，无工程重跑；2 CPU threads，CUDA_VISIBLE_DEVICES为空、CUDA未初始化，禁止派生进程/网络/CUDA初始化与路径守卫均无触发。

只提取 `pre_reset_outcome.observation` 中已暴露给 policy 的四项：EEF xyz、EEF quaternion、两关节 gripper qpos/qvel。每任务每字段均 720/720 finite，0 missing、0 nonfinite、0 shape mismatch。原bundle可能物理包含 reward/success/terminated 等同存字段，但程序从不访问它们作为数据特征；step_returned仅核对事件顺序/身份，不读取其结果值。未访问 privileged contact、物体模拟姿态、图像、新pose或保护/进行中数据。

每个实际7D executed_action与对应的已保存 policy decode/decision commit逐值一致，夹爪符号与前一闭合诊断的 bits逐位一致。dispatch execution index、decision ID、step、reset及因果事件顺序均核对。前一selected latent的完整绑定沿用已关闭的native审计/诊断，本次不分析其他 canonical histories、重新投影或打分。

状态时点采用 **动作执行后、自动重置前** 的实际观察。段起点是同reset下紧邻前一步的 poststep。每个任务 step0 前观察均没有保存，所以4个初始块/初始run起点与完整净变化为 Unknown；不得填0或拿第一个动作后状态冒充初始状态。其余356个八步块起点已知，15对研究案例的两段起止全部已知。终末动作同样用 pre-reset观察，未把重置后的状态混入。

夹爪关节值保留原观测单位及两关节符号；不假设两关节相等或简单相加就是握持宽度。EEF xyz单位为米。所有 net/range 是描述量，没有拟合接触阈值、系数或选择成功相关子集；quaternion分量仅保留原记录，不把分量差称为旋转角度。

## 四个任务的全部动作

“同号run”是一个 episode/reset 内实际夹爪命令符号不变的最大连续区间，允许跨Stage/guidance边界；这些身份变化列表保存在JSON。没有将每个8步块都误算为一个新run。

| task | 动作数 | +1命令 | -1命令 | 同号runs | qpos两关节范围（min→max） | EEF xyz范围（m，min→max） |
|---:|---:|---:|---:|---:|---|---|
'''
for a in d['attempts']:
 q=a['whole_episode_observations']['robot0_gripper_qpos']['observed_range'];e=a['whole_episode_observations']['robot0_eef_pos']['observed_range']
 t+=f"| {a['task']} | 720 | {a['positive_actions']} | {a['negative_actions']} | {a['runs']} | {fmt(q['min'])} → {fmt(q['max'])} | {fmt(e['min'])} → {fmt(e['max'])} |\n"
t+='''
全部171 runs在 `command-runs-detail-v1.csv` 和 result JSON逐段列出起止step、两个关节起止/净变化/min/max、qvel范围、EEF xyz起止/净变化/range及可观测路径长度；没有删除短run或方向变化。每任务 JSON 另明确区分“未知 episode 初始→末态”与“已记录 step0 后→step719 后”的变化。

## 按实际八步命令分组的描述

分类完全由8个二值命令决定：全正向8/8、混合1..7/8、全非正向0/8；没有使用关节位置、任务结果或拟合阈值分组。各组是相关时间序列的描述，不能当作干预效应。

| 八步类型 | 块数 | 净变化起点已知 | qpos joint0净变化 min / mean / max | qpos joint1净变化 min / mean / max | EEF净位移 min / mean / max（mm） |
|---|---:|---:|---|---|---|
'''
labels={'all_positive':'全正向','mixed':'混合','all_nonpositive':'全非正向'}
for k,s in d['prefix_type_summaries'].items():
 q=s['robot0_gripper_qpos']['net_change_each_coordinate'];e=s['eef_net_displacement_m']
 qf=lambda z:' / '.join(f'{z[x]:.8f}' for x in ['min','mean','max'])
 ef=' / '.join(f'{1000*e[x]:.4f}' for x in ['min','mean','max'])
 t+=f"| {labels[k]} | {s['prefixes']} | {e['count']} | {qf(q[0])} | {qf(q[1])} | {ef} |\n"
t+='''
全非正向的211块中只有207块净变化起点已知，缺失正是4个episode首块。其余组起点均已知。组间统计包含不同动作与状态，不解释为命令类型导致的平均效果。+1命令也不保证每个关节每块都单调变化；例如全正向组 joint0 净变化实际既有负也有正，不能从指令符号推断物理握持状态。

| 八步类型 | qpos pooled范围（min→max） | qvel pooled范围（原单位，min→max） |
|---|---|---|
'''
for k,s in d['prefix_type_summaries'].items():
 q=s['robot0_gripper_qpos'];v=s['robot0_gripper_qvel'];t+=f"| {labels[k]} | {fmt(q['pooled_observed_min'])} → {fmt(q['pooled_observed_max'])} | {fmt(v['pooled_observed_min'])} → {fmt(v['pooled_observed_max'])} |\n"
t+='''
逐块全部360条，包括 qpos/qvel/EEF范围和净变化，见 `prefixes-detail-v1.csv`。观察路径长度只累加实际相邻记录的EEF距离；首块少第一段并显式标记不完整，没有任何预测轨迹积分。

## 全部15对：两段实际夹爪命令与关节状态

每一行旧预测尾部均为 `11111111`；表中列的是两段**实际已执行**命令。`1=+1`，`0=-1`。三组状态分别为上一段开始、中间共享边界（上一段结束=下一段开始）、下一段结束。没有省略5例 retained。

| task | step边界 | 上一实际bits → 下一实际bits | 下一类型 | qpos上一开始 | qpos共享边界 | qpos下一结束 |
|---:|---|---|---|---|---|---|
'''
for p in d['strict_pairs']:
 a=p['previous_executed_prefix'];b=p['next_executed_prefix'];check(a['robot0_gripper_qpos']['end']==b['robot0_gripper_qpos']['start'])
 t+=f"| {p['task']} | {p['previous_step']}→{p['next_step']} | `{a['actual_command_bits']}` → `{b['actual_command_bits']}` | {p['next_prefix_category']} | {fmt(a['robot0_gripper_qpos']['start'])} | {fmt(b['robot0_gripper_qpos']['start'])} | {fmt(b['robot0_gripper_qpos']['end'])} |\n"
t+='''
## 全部15对：EEF实际起止和前一诊断的目标位移

三组EEF坐标的时点与上表相同。所有15对的 Stage、reset、guided及已记录 target/tracker identity都严格相同，允许描述性比较；**不能据此推断接触、确定抓取或保持旧计划的效果**。目标位移从旧诊断原样引用，没有新读取对象pose；它表示policy追踪记录的变化，不是对象ground-truth或EEF与对象刚性绑定证据。

| task | step边界 | EEF上一开始 xyz(m) | EEF共享边界 xyz(m) | EEF下一结束 xyz(m) | 上一/下一EEF净位移(mm) | 旧记录目标位移(mm) |
|---:|---|---|---|---|---|---:|
'''
for p in d['strict_pairs']:
 a=p['previous_executed_prefix'];b=p['next_executed_prefix'];check(a['robot0_eef_pos']['end']==b['robot0_eef_pos']['start'])
 t+=f"| {p['task']} | {p['previous_step']}→{p['next_step']} | {fmt(a['robot0_eef_pos']['start'])} | {fmt(b['robot0_eef_pos']['start'])} | {fmt(b['robot0_eef_pos']['end'])} | {1000*a['eef_net_displacement_m']:.4f} / {1000*b['eef_net_displacement_m']:.4f} | {1000*p['target_displacement_m_from_prior_diagnostic']:.9g} |\n"
t+='''
所有未舍入数值和两段 qpos/qvel/EEF完整范围已保留JSON及 `strict-pairs-v1.csv`。Markdown中的向量小数仅为阅读显示，不反馈成阈值。

## 能得出的结论与未知

记录确认了命令、关节与EEF均有可观测变化，且计划差异不能一概描述为“实际连续握持被打断”。两例下一全非正向尤其需要区分旧预测尾部与上一段真正执行的混合命令。相反，5例保持全正向也只说明命令及本体感知的记录，不证明握持成功。

关节不动、关节间距、+1持续时间、EEF运动或追踪目标同移都不被贴上抓取标签。没有contact/奖励/成功/对象真值结果，没有替代动作实验，无法判断旧尾部保留是否好于当前重规划。旧计划是远期模型输出，可靠性未知；新观测可以合理改变计划。同身份并不等于世界状态不变。

本次不选择/实现算法、memory、保留lane或评分更改，不改变当前GPU7 cohort、源码/controller/state/ledger/预算。所有旧记录原样保留。此有界观察已关闭；后续提案由root在当前cohort终局及预算审查后决定。

## 输出及复现

数据源全路径/哈希、源文件字节哈希、原生receipt/audit/index引用均在冻结manifest；每条动作保留四种事件sequence/bundle/reset关联。实际屏幕未使用工程重跑机会，也未超时。报表阶段只读取本目录导出JSON，没有重开真实输入。

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python extract_cpu_v1.py
```

脚本拒绝覆盖既有结果；以上仅供审阅复现逻辑，关闭后不要在原目录重跑。导出已闭合的结果哈希如下。

| 文件 | SHA256 |
|---|---|
'''
for name in ['freeze_scope_v1.py','freeze-v1.log','read-scope-v1.json','extract_cpu_v1.py','extract-v1.log','result-v1.json','command-runs-v1.csv','command-runs-detail-v1.csv','prefixes-v1.csv','prefixes-detail-v1.csv','strict-pairs-v1.csv','report_cpu_v1.py']:
 t+=f"| `{name}` | `{hashlib.sha256((H/name).read_bytes()).hexdigest()}` |\n"
f=H/'conclusion-v1.md';check(not f.exists());f.write_text(t)
m={'schema':'n23-executed-proprioception-output-manifest-v1','files':[{'path':str(x),'sha256':hashlib.sha256(x.read_bytes()).hexdigest(),'bytes':x.stat().st_size} for x in sorted(H.iterdir()) if x.is_file()]};o=H/'output-manifest-v1.json';o.write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps({'conclusion_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'output_manifest_sha256':hashlib.sha256(o.read_bytes()).hexdigest(),'outputs':len(m['files'])},indent=2))
