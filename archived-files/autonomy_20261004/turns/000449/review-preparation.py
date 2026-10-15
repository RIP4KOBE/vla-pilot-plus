import json,hashlib,pathlib,datetime,sys,subprocess
ROOT=pathlib.Path.cwd(); BASE=ROOT.parent; OUT=BASE/'autonomy_20261004/turns/000449'; P=BASE/'variants/n32_archive_eligible_capture/prospective-continuation-v3'
sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r
checks=[]
def ck(name,ok):
 checks.append({'check':name,'passed':bool(ok)})
 if not ok: raise RuntimeError(name)
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
def load(p):return json.loads(pathlib.Path(p).read_text())
def verify(v):
 a=ref(v['path']);ck('hash '+v['path'],a['sha256']==v['sha256'] and a['bytes']==v.get('bytes',a['bytes']));return load(v['path']) if str(v['path']).endswith('.json') else None
index=load(P/'artifact-index-v1.json')
for x in index['artifacts']:verify(x)
m=load(P/'carry-forward-map-v1.json'); plan=verify(m['parent_plan']); rows={x['episode_key']:x for x in plan['episodes']}
ev=[json.loads(x) for x in (ROOT/'data/attempt-ledger.jsonl').read_text().splitlines()]; health=[json.loads(x) for x in (ROOT/'data/gpu-healthcheck-ledger.jsonl').read_text().splitlines()]
snap=r.budget_snapshot(ev,health); groups=r.event_groups(ev)
ck('all reservations terminal',all(x[-1]['event'] in r.TERMINAL for x in groups.values()))
for c in m['accepted_cells']+[m['old_invalid_cell']]:
 d={k:verify(c[k]) for k in ['native_receipt','generic_audit','terminal_receipt','command_receipt','context','process_receipt','expected_manifest','stage_events']}
 t=d['terminal_receipt']; n=d['native_receipt']; cx=d['context']; a=d['expected_manifest']; ident=c['old_attempt_id']
 ck(ident+' ledger terminal',groups[ident][-1]==t)
 ck(ident+' exact identity',n['attempt_id']==t['attempt_id']==cx['attempt_id']==ident and n['row']==a['row']==rows[ident]==c['original_row'])
 ck(ident+' bindings',n['source']==a['source']==plan['source'] and n['plan']==cx['plan']==m['parent_plan'] and a['runtime']==plan['runtime'] and t['plan_sha256']==m['parent_plan']['sha256'])
 ck(ident+' command',d['command_receipt']['main_argv']==a['argv'] and cx['main_argv']==a['argv'][1:])
 ck(ident+' audit',n['accepted'] is True and d['generic_audit']['accepted'] is True and n['audit_report']['sha256']==c['generic_audit']['sha256'] and n['process_unchanged'] is True)
 ck(ident+' process',n['process']=={k:d['process_receipt'][k] for k in ['pid','proc_start_ticks','boot_id']})
 valid=c['denominator_eligible'];ck(ident+' validity',t['event']=='valid' and t['outcome_valid'] is True and t['required_cost_telemetry_complete'] is True if valid else t['outcome_valid'] is False and t['success'] is None)
ck('14 accepted',len(m['accepted_cells'])==14)
ck('16 distinct proposed',len(m['proposed_cells'])==len({x['new_attempt_id'] for x in m['proposed_cells']})==16)
semantic=[]
for c in m['accepted_cells']:semantic.append((c['original_row']['task_id'],c['original_row']['profile']))
for i,c in enumerate(m['proposed_cells']):
 old=c['old_row'];new=c['proposed_row'];ck('row parent '+str(i),old==plan['episodes'][i+14]);ck('semantic exact '+str(i),{k:v for k,v in old.items() if k not in ['episode_key','iteration','budget_bucket']}=={k:v for k,v in new.items() if k not in ['episode_key','iteration','budget_bucket']})
 ck('explicit recovery '+str(i),c['recovery_of']==(m['old_invalid_cell']['old_attempt_id'] if i==0 else None) and c['retry_of'] is None)
 ck('never dispatched '+str(i),c['new_attempt_id'] not in groups)
 semantic.append((new['task_id'],new['profile']))
ck('exact 30 semantic cells',len(set(semantic))==30 and set(semantic)=={(t,p) for t in range(10) for p in ['C0','Q0','N32']})
commands=load(P/'command-candidates-v1.json')['commands'];allow={'hydra.run.dir','main.eds_eval.output_dir','main.eds_eval.job_id','main.eds_mechanism_pretest.output_dir','main.eds_mechanism_pretest.run_id','main.eds_config.n32_runtime_binding'}
for c in commands:
 a=verify(c['parent_expected_manifest']); ck('command original '+c['new_attempt_id'],a['argv']==c['old_argv']);ck('command identity substitutions '+c['new_attempt_id'],c['proposed_argv']==[x.replace(a['output_dir'],c['proposed_output_dir']).replace(c['old_attempt_id'],c['new_attempt_id']) for x in a['argv']] and all(x['old'].split('=',1)[0] in allow for x in c['exact_changes']))
a=load(P/'accounting-amendment-candidate-v1.json');ck('account totals',snap['dispatched']==a['retained_attempts'] and abs(snap['gpu_hours_consumed']-a['retained_gpu_hours'])<1e-9 and snap['by_bucket']==a['retained_by_bucket']);ck('account future',a['maximum_cumulative_attempts']==snap['dispatched']+16 and abs(a['maximum_cumulative_gpu_hours']-snap['gpu_hours_consumed']-8.5)<1e-9)
ck('STOP absent',not (BASE/'autonomy_20261004/STOP').exists());ck('deadline',datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-10T17:42:00+00:00'))
result={'schema':'n32r3-root-preparation-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_FOR_BOUNDED_CPU_IMPLEMENTATION_ONLY','checks':checks,'artifact_index':ref(P/'artifact-index-v1.json'),'ledger_prefix':ref(ROOT/'data/attempt-ledger.jsonl'),'health_prefix':ref(ROOT/'data/gpu-healthcheck-ledger.jsonl'),'budget_snapshot':snap,'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'accepted_historical_cells':14,'proposed_cells':16,'gpu_authorized':False,'pooling_authorized':False,'budget_adopted':False,'remaining_blockers':['Operational continuation implementation and focused adversarial tests','Independent source delta and receipt continuity review','New runtime/source/manifests and exact composed configuration audits','Prospective accounting adoption and fresh admission','Detached root release'],'historical_transport_cause':'Unknown'}
(OUT/'preparation-root-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'checks':len(checks),'snapshot':snap}))
