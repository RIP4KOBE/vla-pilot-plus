import pathlib,json,hashlib,datetime,collections,sys,shutil,subprocess,yaml
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/000876').resolve();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
def read(p): return json.loads(pathlib.Path(p).read_text())
def ref(p):
 p=pathlib.Path(p);return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
prev=read(out.parent/'000875/terminal-reconciliation-v1.json');driver=read(root.parent/'autonomy_20261004/driver-status.json');assert driver['turn']==876
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();handles=[]
for key in ['driver','process']:
 h=driver[key];fields=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and h['start_ticks']==int(fields[19]);handles.append(dict(h,observed_state=fields[0]))
assert not pathlib.Path('/proc/2303352').exists();assert read(out.parent/'000875/receipt.json')['exit']==0
plan=read(out.parent/'000861/plan.frozen-v1.json');assert not pathlib.Path(plan['stop_path']).exists()
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==prev['source']
rows=[]
for n in prev['native_receipts']:
 if not any(t in n['attempt_id'] for t in ['t05_n34','t06_n34']):continue
 rp=pathlib.Path(n['receipt']['path']);assert ref(rp)==n['receipt'];p=rp.parent
 metrics=[json.loads(l) for l in (p/'eds_metrics.jsonl').read_text().splitlines()];audit=read(p/'decision-evidence-audit.json');assert audit['accepted'];a=audit['n34_observed_jaw_audit'];stages=[json.loads(l) for l in (p/'stage_events.jsonl').read_text().splitlines()]
 close=[{'global_step':m['global_step'],'reasons':m['capture_dwell_proposal']['reasons']} for m in metrics if 'observed_close_dwell' in m['capture_dwell_proposal']['reasons']]
 rows.append({'attempt_id':n['attempt_id'],'success':n['success'],'receipt':ref(rp),'audit':ref(p/'decision-evidence-audit.json'),'metrics':ref(p/'eds_metrics.jsonl'),'stage_events':ref(p/'stage_events.jsonl'),'guided_decisions':len(metrics),'audit_counts':{k:v for k,v in a.items() if k not in ['runtime_identity','compute_expected']},'proposal_reasons':dict(collections.Counter(z for m in metrics for z in m['capture_dwell_proposal']['reasons'])),'close_dwell_chunks':close,'stage_summary':[ {k:e.get(k) for k in ['global_step','query_ok','stage_before','stage_after','guidance_before','guidance_after']} for e in stages]})
next_step='Extract bounded native jaw/target observations, selected action linkage and proposal lineage around task6 close-dwell chunk and task5 first24 steps. Audit aggregate content selection is not ancestry: test indirect influence before attributing success or registering a new idea. Review tree constraints before ideation; no GPU replay or protected evaluation.'
d={'schema':'n34-dev-mechanism-comparison-v1','at':now.isoformat(),'source':source,'handles':handles,'prior_terminal_review':ref(out.parent/'000875/terminal-reconciliation-v1.json'),'scope':'Dev tasks5/6 only; existing receipts/audits/scalar metrics; no new execution','tasks':rows,'findings':['Task5 success: zero of3 guided decisions selected proposal content;23 changed proposals, all observed-open approach. Direct proposal-content execution does not explain success; indirect lineage effects remain unresolved.','Task6 failure:30 of44 guided decisions selected proposal content;151 changed proposals,150 observed-open approach and1 observed-close-dwell. Selection survival alone is insufficient.','Stage text is model interpretation, not measured grasp or target-motion evidence. Geometry and closure timing remain unresolved.'],'next_step':next_step,'target_met':False,'validation_authorized':False,'formal_authorized':False}
with runner.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with runner.locked(root/'data/qd-ed-state.lock'):
  for name,v in prev['ledger_prefixes'].items():
   b=(root/'data'/name).read_bytes();assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256']
  d['ledger_prefixes']=prev['ledger_prefixes'];write(out/'mechanism-comparison-v1.json',d);rr=ref(out/'mechanism-comparison-v1.json')
  sp=root/'research-state.yaml';cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
  for p in [sp,cp,tp]:shutil.copyfile(p,out/(p.name+'.before'))
  s=runner.read_state(sp);c=read(cp);t=read(tp)
  for obj in [s,c]:obj.update(n34_dev_mechanism_comparison=rr,next_action=next_step,updated_at=now.isoformat())
  t['nodes']['15.4']['mechanism_comparison']=rr;t['nodes']['15.4']['insight']+=' Task5 success had0/3 direct proposal-content selections; task6 failure had30/44. Indirect ancestry and actual jaw/target motion unresolved.'
  q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
  write(out/'diagnosis-adoption-v1.json',{'review':rr,'state':ref(sp),'checkpoint':ref(cp),'tree':ref(tp),'no_new_dispatch':True})
(out/'operational-summary.md').write_text(f'''Turn876 — {now.isoformat()}\n\nSource {source} unchanged. Driver268073/start97715947 and coordinator2405974/start140239487 verified on boot {boot}; controller2303352 absent, prior turn875 completed normally. STOP absent; authorization deadline2026-10-11T11:13:13Z. No GPU dispatch or source changes.\n\nCompleted Dev-only task5/task6 audit comparison, hash-bound in mechanism-comparison-v1.json. Task5 success had0/3 guided direct proposal-content selections (23 open-approach changes); task6 failure had30/44 selections (150 open-approach changes,1 close-dwell). Direct content survival is not mechanism proof; ancestry unresolved. All owning ledger prefixes unchanged:474 attempts,69.99568238388729 GPUh; protected reserves retained.\n\nNext bounded step: {next_step}\n\nOriginal validation/formal/ablation goal unmet. No completion record.\n''')
print(json.dumps({'record':rr,'close_dwell':[(x['attempt_id'],x['close_dwell_chunks']) for x in rows]}))
