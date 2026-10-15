import pathlib,json,hashlib,datetime,sys,collections,os
import yaml
sys.path.insert(0,str(pathlib.Path.cwd()))
from scripts import qd_ed_final_runner as r
root=pathlib.Path.cwd(); out=root.parent/'autonomy_20261004/turns/000509'; cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'; tp=cp.parent/'idea_tree.json'
def ref(p):
 p=pathlib.Path(p);return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def readref(x):
 assert ref(x['path'])['sha256']==x['sha256'];return json.loads(pathlib.Path(x['path']).read_text())
def write(p,d):
 tmp=p.with_name(p.name+'.tmp509');tmp.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n');os.replace(tmp,p)
def identity(x):
 p=pathlib.Path('/proc')/str(x['pid'])/'stat'
 if not p.exists():return {'pid':x['pid'],'alive':False,'expected_start':x.get('proc_start_ticks',x.get('start_ticks'))}
 fields=p.read_text().rsplit(')',1)[1].split();start=fields[19];boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 return {'pid':x['pid'],'alive':True,'state':fields[0],'start_ticks':start,'boot_id':boot,'identity_matches':str(x.get('proc_start_ticks',x.get('start_ticks')))==start and x['boot_id']==boot}
s=yaml.safe_load((root/'research-state.yaml').read_text());a=s['active_controller'];plan=readref(a['plan']);readref(a['release']);readref(a['launch']);protocol=readref(plan['protocol']);result=json.loads(pathlib.Path(a['result_path']).read_text());assert result['exit']==0 and result['result']['status']=='NUMERIC_FUTILITY'
assert not identity(a)['alive']
b=(root/'data/attempt-ledger.jsonl').read_bytes();events=[json.loads(x) for x in b.splitlines()];prev=json.loads((out.parent/'000508/controller-observation-v1.json').read_text());assert hashlib.sha256(b[:prev['ledger']['bytes']]).hexdigest()==prev['ledger']['sha256']
groups=r.event_groups(events);outcomes=result['result']['outcomes'];counts={};cells=[];handles=[identity(a)]
for x in outcomes:
 g=groups[x['attempt_id']];f=g[-1];assert f['event']=='valid' and f['outcome_valid'] is True and f['success'] is x['success']; assert f['identity']['task_id']==x['task_id'] and f['identity']['profile']==x['profile']
 counts.setdefault(x['profile'],{'n':0,'success':0});counts[x['profile']]['n']+=1;counts[x['profile']]['success']+=x['success']
for task in range(6):
 fs=[groups[x['attempt_id']][-1] for x in outcomes if x['task_id']==task];assert len(fs)==3
 for k in ['env_seed','policy_seed','init_index']:assert len({f['identity'][k] for f in fs})==1
 assert len({f['init_row_sha256'] for f in fs})==1
new=[g[-1] for aid,g in groups.items() if aid.startswith('n32r3')];assert len(new)==4
for f in new:
 assert [e['event'] for e in groups[f['attempt_id']]]==['reserved','dispatched','valid']
 receipt=readref(f['n32_worker_receipt']);audit=readref(receipt['audit_report']);assert receipt['accepted'] is True and receipt['main_exit_code']==0 and receipt['process_unchanged'] is True and audit['accepted'] is True and audit['evidence_complete'] is True
 assert receipt['attempt_id']==f['attempt_id'] and receipt['plan']==a['plan']
 output=pathlib.Path(f['output_dir']);terminal=json.loads((output/'attempt-result.json').read_text());assert terminal==f
 process=json.loads((output/'process.json').read_text());h=identity(process);handles.append(h);assert not h['alive'] or not h['identity_matches']
 cells.append({'attempt_id':f['attempt_id'],'success':f['success'],'bucket':f['budget_bucket'],'seconds':f['gpu_process_wall_seconds'],'terminal':ref(output/'attempt-result.json'),'worker_receipt':f['n32_worker_receipt'],'audit':receipt['audit_report'],'native_counts':receipt['native_counts']})
snap=r.budget_snapshot(events,r.read_events(root/'data/gpu-healthcheck-ledger.jsonl'));assert snap['running']==0 and snap['gpu_healthcheck_inflight']==0
assert 0+10-6<protocol['promotion']['n32_min_successes']
driver=json.loads((root.parent/'autonomy_20261004/driver-status.json').read_text());assert driver['turn']==509
for k in ['driver','process']:
 h=identity(driver[k]);assert h['identity_matches'];handles.append(h)
review={'schema':'n32r3-root-terminal-reconciliation-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':s['source_commit'],'scientific_source':s['scientific_source_commit'],'controller':a,'controller_exit':ref(a['result_path']),'controller_status':ref(a['status_path']),'decision':'REJECT_NUMERIC_DEV_FUTILITY','counts':counts,'complete_valid_triples':6,'unobserved_tasks':[6,7,8,9],'upper_bound_successes':4,'required_successes':5,'inherited_valid_cells':14,'new_valid_cells':4,'receipt_review_scope':'Hash-bound accepted same-process receipts and native audit reports; controller performed full frozen reconciliation. No repeated tensor audit or historical provenance rebuild.','new_cells':cells,'new_charged_seconds':sum(f['gpu_process_wall_seconds'] for f in new),'budget_snapshot':snap,'ledger':{'bytes':len(b),'rows':len(events),'sha256':hashlib.sha256(b).hexdigest(),'prior_prefix_preserved':True},'live_handles':handles,'http_counters':'Unknown','historical_failures_and_charges_retained':True,'source_plan_thresholds_unchanged':True,'scientific_promotion':False,'validation_authorized':False,'formal_authorized':False,'goal_met':False,'next_action':'Bounded dev-only mechanism diagnosis: contrast N32 task4 selected proposals without success and task5 unselected proposal against matched controls; use actual execution/target-motion evidence before new falsifiable ideation. No replay or automatic recovery.'}
write(out/'terminal-reconciliation-v1.json',review);rr=ref(out/'terminal-reconciliation-v1.json')
with r.locked(root/'data/qd-ed-state.lock'):
 s=yaml.safe_load((root/'research-state.yaml').read_text());c=json.loads(cp.read_text());assert s['active_controller']==a==c['active_controller'];assert (root/'data/attempt-ledger.jsonl').read_bytes()==b
 for d in [s,c]:
  d['closed_n32r3_controller']={**a,'terminal_review':rr,'exit':0};d['active_controller']=None;d['n32r3_terminal_reconciliation']=rr;d['status']='N32R3_REJECTED_NUMERIC_FUTILITY';d['phase']='DEV_TERMINAL_REVIEWED';d['next_action']=review['next_action'];d['budget_snapshot']=snap;d['updated_at']=review['at']
 s['budget']['gpu_hours_consumed']=snap['gpu_hours_consumed']
 tmp=root/'research-state.yaml.tmp509';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(tmp,root/'research-state.yaml');write(cp,c)
 t=json.loads(tp.read_text());n=t['nodes']['15.2'];n['status']='done';n['phase']='DEV_REJECTED_NUMERIC_FUTILITY';n['n32r3_terminal_review']=rr;n['n32r3_counts']=counts;n['n32r3_insight']='Six matched dev triples: C0 1/6, Q0 0/6, N32 0/6. Remaining four tasks cannot meet five-success gate. Task4 selected capture proposals did not yield success; task5 changed proposal was not selected. Tasks6-9 Unknown. No scientific promotion.';write(tp,t)
print(json.dumps({'review':rr,'counts':counts,'new_gpu_hours':review['new_charged_seconds']/3600,'budget':snap},indent=2))
