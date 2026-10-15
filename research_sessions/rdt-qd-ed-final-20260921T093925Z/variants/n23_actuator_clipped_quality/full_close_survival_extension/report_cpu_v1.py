from pathlib import Path
import collections,csv,hashlib,json
H=Path(__file__).resolve().parent;d=json.loads((H/'result-v1.json').read_text());new=d['decisions'];allrows=d['task0_reused_decisions']+new
assert len(new)==124 and len(allrows)==139 and len(d['batches'])==1364 and len(d['parent_rounds'])==1240
assert sum(d['new_native_coverage']['canonical_histogram_0_to_8'])==21824
assert sum(r['selected_parent_pool']['full_positive'] for r in d['parent_rounds'])==4525
assert 4462+63+0==4525
assert len(list(csv.DictReader((H/'all-decisions-v1.csv').open())))==139
summary={r['task']:r for r in d['summaries']};cats=['never_full_positive','ever_full_positive_then_terminal_none','terminal_full_positive_not_selected','selected_full_positive']
for s in summary.values():assert sum(s['categories'].values())==s['decisions']
labels={'never_full_positive':'全程无full8','ever_full_positive_then_terminal_none':'曾有full8，终轮无','terminal_full_positive_not_selected':'终轮有full8但未选','selected_full_positive':'选中full8'}
lossfinal=[]
for r in new:
 if r['category']=='ever_full_positive_then_terminal_none':
  k=max(i for i,x in enumerate(r['canonical_full_positive_counts']) if x)
  parent=r['actual_parent_full_positive_counts'][k]
  lossfinal.append({'task':r['task'],'step':r['global_step'],'last_full_canonical_iter':k-1,'next_parent_iter':k,'next_parent_full_count':parent,'next_offspring_full_count':r['canonical_full_positive_counts'][k+1],
    'observed_last_loss':'actual_allocation_none' if parent==0 else 'actual_full_parent_then_offspring_none','archive_final_full_count':r['final_archive_full_positive']})
assert collections.Counter(r['observed_last_loss'] for r in lossfinal)=={'actual_allocation_none':25,'actual_full_parent_then_offspring_none':2}
with (H/'final-full-losses-v1.csv').open('w',newline='') as fp:
 w=csv.DictWriter(fp,fieldnames=list(lossfinal[0]));w.writeheader();w.writerows(lossfinal)
with (H/'parent-rounds-v1.csv').open('w',newline='') as fp:
 cols=['task','global_step','iter_idx','source_full_positive','selected_parent_full_positive','descendant_full_positive','full_parent_to_full_descendant','full_parent_to_transient_descendant','full_parent_to_zero_descendant','nonfull_parent_to_full_descendant'];w=csv.DictWriter(fp,fieldnames=cols);w.writeheader()
 for r in d['parent_rounds']:w.writerow({**{k:r[k] for k in cols if k in r},'source_full_positive':r['source_pool']['full_positive'],'selected_parent_full_positive':r['selected_parent_pool']['full_positive'],'descendant_full_positive':r['descendant_pool']['full_positive']})
full_rows=[]
for b in d['batches']:
 for r in b['full_positive_rows']:full_rows.append({'task':b['task'],'step':b['global_step'],'iter_idx':b['iter_idx'],'row':r['row'],'occurrence_id':r['occurrence_id'],'fingerprint':r['fingerprint'],'native_cost':r['native_cost'],'native_quality':r['native_quality'],'native_cost_dtype':b['native_costs']['dtype'],'native_gripper_sha256':r['native_gripper']['sha256']})
assert len(full_rows)==5060
with (H/'full-positive-candidates-v1.csv').open('w',newline='') as fp:
 w=csv.DictWriter(fp,fieldnames=list(full_rows[0]));w.writeheader();w.writerows(full_rows)
t='''# N23 tasks1..3：完整八步正向候选的供给、父代分配与终轮保留

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
'''
for task in [0,1,2,3,'new1to3','all0to3']:
 s=summary[task];vals=[s['categories'].get(c,0) for c in cats];t+=f"| {task} | {s['decisions']} | {' | '.join(map(str,vals))} | {s['never_any_positive']} | {s['ever_any_but_never_full_positive']} |\n"
t+='''
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
'''
for r in new:
 if r['terminal_full_positive']==0 and r['final_archive_full_positive']>0:t+=f"| {r['task']} | {r['global_step']} | {','.join(map(str,r['canonical_full_positive_counts']))} | {','.join(map(str,r['actual_parent_full_positive_counts']))} | {r['final_archive_full_positive']} | {r['selected_positive_count']} |\n"
t+='''
这4个最终snapshot按原native审计alias与原cost/夹爪数据绑定。它们说明terminal canonical与archive成员可不同；不证明改选archive动作会成功。task0旧数据中没有这一full8差异案例，此处不能把旧task0观察泛化成所有任务。

## 固定规则代表例：每类按(task,step)最早一例

代表例使用事前确定的chronological-first规则，不按成本、结果或异常程度挑选；所有决策仍完整保留在附表。

| 分类 | task / step | canonical full8数（11批） | parent full8数（10轮） | terminal / archive full8 | 所选row / 正向数 / 原cost |
|---|---|---|---|---|---|
'''
for cat,rep in d['representatives_first_chronological_per_category'].items():
 r=next(x for x in new if x['task']==rep['task'] and x['global_step']==rep['global_step'])
 t+=f"| {labels[cat]} | {r['task']} / {r['global_step']} | {','.join(map(str,r['canonical_full_positive_counts']))} | {','.join(map(str,r['actual_parent_full_positive_counts']))} | {r['terminal_full_positive']} / {r['final_archive_full_positive']} | {r['selected_index']} / {r['selected_positive_count']} / {r['selected_native_cost']:.12g} |\n"
t+='''
其中step392初始没有full8，搜索中出现后又消失，不能写成“初始有好动作被损坏”。step64终轮仍有4个full8候选而实际选中6步正向命令，也不能只凭动作符号判断哪一个更好。完整原成本和身份可核查，但本次不重新排序，也不贴成功/效用标签。

## 全决策附表

I=初始full8，T=terminal full8，A=final archive full8，S=所选8步中正向数。source为task0闭合JSON复用或tasks1..3新native。更完整的11批/10父代轮轨迹及any/transient计数在全139行 `all-decisions-v1.csv`；下表没有只保留出现full8的决策。

| task | step | I | T | A | S | 分类 | 证据来源 |
|---:|---:|---:|---:|---:|---:|---|---|
'''
for r in sorted(allrows,key=lambda r:(r['task'],r['global_step'])):t+=f"| {r['task']} | {r['global_step']} | {r['initial_full_positive']} | {r['terminal_full_positive']} | {r['final_archive_full_positive']} | {r['selected_positive_count']} | {labels[r['category']]} | {'旧JSON' if r['task']==0 else '新native'} |\n"
t+='''
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
'''
for p in sorted(H.iterdir()):
 if p.is_file():t+=f"| `{p.name}` | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |\n"
f=H/'conclusion-v1.md';assert not f.exists();f.write_text(t)
m={'schema':'n23-full-close-survival-output-manifest-v1','files':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(H.iterdir()) if p.is_file()]};o=H/'output-manifest-v1.json';o.write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps({'conclusion_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256(o.read_bytes()).hexdigest(),'files':len(m['files'])},indent=2))
