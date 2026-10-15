from pathlib import Path
import json,hashlib,datetime,fcntl,os,sys
import yaml
W=Path.cwd();sys.path.insert(0,str(W))
from scripts import qd_ed_final_runner as r
A=W.parent/'autonomy_20261004';T=A/'turns/001719';O=T/'readiness-import-repair';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
def atomic(p,d,is_yaml=False):
 q=p.with_name(p.name+'.tmp-001719');q.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(q,p)
prev=json.loads((A/'turns/001718/operational-summary-v1.json').read_text());prefixes={}
for k,v in prev['ledger_prefixes'].items():
 p=Path(v['path']);assert hashlib.sha256(p.read_bytes()[:v['bytes']]).hexdigest()==v['sha256'];prefixes[k]={**ref(p),'prior_prefix_preserved':True}
process=json.loads((O/'process-v1.json').read_text());handles={}
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for name,v in {'driver':dict(pid=268073,start_ticks=97715947),'coordinator':dict(pid=3134084,start_ticks=154256224),**{k:process[k] for k in ['wrapper','executor']}}.items():
 s=Path(f'/proc/{v["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert int(s[19])==v['start_ticks'];handles[name]=dict(pid=v['pid'],start_ticks=int(s[19]),boot_id=boot,state=s[0])
assert not (A/'STOP').exists();assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
entry=dict(status='CPU_IMPORT_REPAIR_RUNNING',source='d3225489f6edfd2e49f472dc1ea9307f14f8be70',worktree='/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree',authority=ref(O/'authority-v1.json'),output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=handles['wrapper'],executor=handles['executor'],gpu_authorized=False,source_edits_authorized=True)
next_step='Monitor the existing turn001719 CPU import-repair executor by exact boot/start identity; do not duplicate or dispatch GPU. On terminal exit reconcile actual commit/report/tests, independently review the bounded repair, then prospectively bind a NEW preparation recovery resource and affected source/graph records. Never replay n36_readiness_preparation_001651. Production readiness and scientific promotion remain closed.'
with (C/'state.lock').open('a') as cl, (W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 state=yaml.safe_load((W/'research-state.yaml').read_text());checkpoint=json.loads((C/'checkpoint.json').read_text())
 snap=r.budget_snapshot(r.read_events(W/'data/attempt-ledger.jsonl'),r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'))
 prior=checkpoint['budget_snapshot'];delta=snap['gpu_hours_consumed']-prior['gpu_hours_consumed'];assert abs(delta-162.70163536071777/3600)<1e-10
 record=dict(schema='n36-readiness-accounting-reconciliation-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),ledger_prefixes=prefixes,prior_checkpoint_snapshot=prior,recomputed_snapshot=snap,arithmetic=dict(additional_seconds=162.70163536071777,additional_gpu_hours=delta,retained_gpu_hours=prior['gpu_hours_consumed'],total_gpu_hours=snap['gpu_hours_consumed'],remaining_absolute_gpu_hours=224-snap['gpu_hours_consumed'],protected_validation_remaining=32-snap['gpu_hours_by_bucket']['validation'],protected_formal_remaining=12,remaining_after_protected=224-snap['gpu_hours_consumed']-(32-snap['gpu_hours_by_bucket']['validation'])-12),budget_caps_unchanged=True,terminal_telemetry_complete=False,terminal_reconciliation=ref(A/'turns/001718/terminal-reconciliation-v1.json'))
 put(T/'accounting-reconciliation-v1.json',record)
 for k,v in snap.items():state['budget'][k]=v
 for k in ['by_bucket','reserved_attempts','gpu_hours_by_bucket','gpu_healthcheck_hours','gpu_healthcheck_inflight']:state.setdefault('runner',{})[k]=snap[k]
 for d in [state,checkpoint]:
  d['budget_snapshot']=snap;d['n36_readiness_import_repair']=entry;d['in_flight_executor']=entry;d['in_flight_executors']=[entry];d['next_action']=next_step;d['n36_readiness_accounting_reconciliation']=ref(T/'accounting-reconciliation-v1.json')
 atomic(W/'research-state.yaml',state,True);atomic(C/'checkpoint.json',checkpoint)
summary=dict(schema='autonomy-operational-summary-v1',turn=1719,at=record['at'],current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,ledger_prefixes=prefixes,completed_work=['Verified handoff/authority hashes, live driver/coordinator and dead historical measurement identities; ledger prefixes preserved.','Reconciled retained preparation charge: 75.64264702604362 + 0.045194898711310494 = 75.68784192475492 GPU hours; caps and protected reserves unchanged.','Launched bounded CPU import repair through official current-login Codex gpt-6-astra in the isolated executor checkout; recorded durable identity and scope.'],accounting_reconciliation=ref(T/'accounting-reconciliation-v1.json'),next_bounded_step=next_step,unresolved_evidence=['CPU repair and independent review pending.','Readiness native/runtime proof absent; terminal telemetry remains incomplete.','Fresh prospective recovery release, production adoption, validation/formal/ablation evidence pending.'],deadline_utc='2026-10-11T11:13:13Z',stop_present=False,target_met=False)
put(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(json.dumps(ref(T/'operational-summary-v1.json')))
