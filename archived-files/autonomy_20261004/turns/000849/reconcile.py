import sys, json, hashlib, datetime, subprocess, os
from pathlib import Path
import yaml
root=Path.cwd();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as r, qd_ed_n34_contract as c, qd_ed_n34_supervise as sup, qd_ed_n34_runner as runner
out=root.parent/'autonomy_20261004/turns/000849'
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def read(p): return json.loads(Path(p).read_text())
def ref(p): return {'path':str(Path(p).resolve()),'sha256':r.digest(p)}
def bound(x):
 assert r.digest(x['path'])==x['sha256'],x['path']
 return read(x['path'])
def identity(pid):
 p=Path('/proc')/str(pid)/'stat'
 if not p.exists(): return None
 f=p.read_text().split(') ',1)[1].split()
 return {'pid':pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(f[19]),'state':f[0]}
state=r.read_state(root/'research-state.yaml');checkpoint=read(cp);a=state['active_controller'];assert a==checkpoint['active_controller']
plan=bound(a['plan']);bound(a['release']);bound(a['launch']);authority=bound(plan['authority'])
handoff=bound({'path':str(root.parent/'autonomy_20261004/handoff-v2.json'),'sha256':'3d8267a367e40ba6a3b9fd307fc8371a335e21bbc92df6700d7ecc10fd9669de'})
for k in ['authorization','required_continuation_context','completion_contract']:
 x=handoff[k];assert r.digest(x['path'])==x['sha256']
assert identity(a['handles']['controller']['pid']) is None
prior=read(root.parent/'autonomy_20261004/turns/000848/live-monitor-v1.json')
prefixes={}
for name,x in prior['ledger_prefixes'].items():
 data=(root/'data'/name).read_bytes();assert hashlib.sha256(data[:x['bytes']]).hexdigest()==x['sha256']
 prefixes[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'prior_prefix_verified':True}
events=r.read_events(root/'data/attempt-ledger.jsonl');resources=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl')
handles=runner.existing_handles(plan,events);assert not handles,handles
assert all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(events).values())
receipts=[]
def verify(row,final):
 assert read(Path(final['output_dir'])/'attempt-result.json')==final
 receipt=bound(final['n34_worker_receipt']);audit=bound(receipt['audit_report'])
 assert receipt['accepted'] is True and receipt['main_exit_code']==0 and receipt['process_unchanged'] is True
 assert receipt['plan']==a['plan'] and receipt['attempt_id']==row['episode_key']
 receipts.append({'attempt_id':row['episode_key'],'receipt':final['n34_worker_receipt'],'audit_report':receipt['audit_report'],'audit_summary':{k:v for k,v in audit.items() if k in ('passed','status','valid','accepted','ok')}})
rec=sup.reconcile(plan,events,verify,live_handles=handles)
snap=r.budget_snapshot(events,resources)
local=c.cohort_events(plan['episodes'],events)
ids={e['resource_id'] for e in resources if e.get('cohort')==c.COHORT or e.get('kind')=='n34r11_resource_preparation_v1'}
local_snap=r.budget_snapshot(local,[e for e in resources if e['resource_id'] in ids])
remaining=18000-local_snap['gpu_hours_consumed']*3600
assert remaining<1840 and rec['status']=='READY_FOR_ROOT_RELEASE'
result=read(a['result_path']);assert result['error']=="ValueError('cohort_seconds_remaining insufficient')"
now=datetime.datetime.now(datetime.timezone.utc)
record={'schema':'n34r11-terminal-accounting-reconciliation-v1','at':now.isoformat(),'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'scientific_source':plan['scientific_source'],'controller':a,'controller_identity_now':None,'worker_handles':handles,'driver':identity(268073),'prior_turn_completed_normally':read(root.parent/'autonomy_20261004/turns/000848/receipt.json')['status']=='completed_turn','controller_result':ref(a['result_path']),'stop_present':Path(plan['stop_path']).exists(),'authorization_deadline':handoff['until'],'deadline_passed':now>=datetime.datetime.fromisoformat(handoff['until'].replace('Z','+00:00')),'ledger_prefixes':prefixes,'budget_snapshot':snap,'cohort_snapshot':local_snap,'cohort_seconds_cap':18000,'cohort_seconds_remaining':remaining,'full_attempt_required_seconds':1840,'admission_shortfall_seconds':1840-remaining,'reconciliation':rec,'receipt_checks':receipts,'verification_scope':'Contiguous lifecycle, terminal JSON equivalence, receipt and native audit report digests/acceptance; existing completed worker audits retained, no broad runtime/native replay.','disposition':'BUDGET_CAPPED_PARTIAL_COHORT_NO_PROMOTION','matched':{'complete_triples':6,'C0_successes':0,'Q0_successes':0,'N34_successes':1},'partial_task6':'C0 valid failure; Q0/N34 not dispatched; excluded from matched denominator','remaining_tasks':'tasks7-9 unobserved','scientific_gate':'30 valid cells and N34 >=5/10 and >=both controls required; not met. Upper bound 1+4=5 does not establish numeric futility.','next_bounded_step':'Assess a separately frozen prospective continuation/cohort budget under standing authorization, preserving 19 outcomes without replay or post-hoc pooling, and unchanged scientific promotion thresholds. Do not restart R11 or modify its frozen 18000-second ceiling.','goal_complete':False,'validation_authorized':False,'formal_authorized':False}
(out/'terminal-reconciliation-v1.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['disposition','budget_snapshot','cohort_snapshot','cohort_seconds_remaining','admission_shortfall_seconds','matched']},indent=2))
