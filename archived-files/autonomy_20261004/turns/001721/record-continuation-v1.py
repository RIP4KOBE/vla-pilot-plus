from pathlib import Path
import json,hashlib,datetime,fcntl,os,subprocess
import yaml
W=Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001721';O=T/'independent-import-review';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def atomic(p,d,is_yaml=False):
 q=p.with_name(p.name+'.tmp-001721');q.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(q,p)
prev=json.loads((A/'turns/001720/operational-summary-v1.json').read_text());prefixes={}
for k,v in prev['ledger_prefixes'].items():
 p=Path(v['path']);assert hashlib.sha256(p.read_bytes()[:v['bytes']]).hexdigest()==v['sha256'];prefixes[k]={**ref(p),'prior_prefix_preserved':True}
r=json.loads((A/'turns/001719/readiness-import-repair/report-v1.json').read_text());rw=Path(r['source']['worktree'])
for f in r['source']['files']:assert ref(rw/f['path'])['sha256']==f['after_sha256']
assert hashlib.sha256(r['source']['diff'].encode()).hexdigest()==r['source']['diff_sha256']
process=json.loads((O/'process-v1.json').read_text());driver=json.loads((A/'driver-status.json').read_text());handles={}
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for name,v in {'driver':driver['driver'],'coordinator':driver['process'],**{k:process[k] for k in ['wrapper','executor']}}.items():
 s=Path(f'/proc/{v["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert int(s[19])==v['start_ticks'] and v['boot_id']==boot;handles[name]={**v,'state':s[0],'identity_verified':True}
assert not (A/'STOP').exists();assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
entry=dict(status='CPU_INDEPENDENT_IMPORT_REVIEW_RUNNING',source=r['code_ref'],worktree=str(rw),authority=ref(O/'authority-v1.json'),output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=handles['wrapper'],executor=handles['executor'],gpu_authorized=False,source_edits_authorized=False)
next_step='Monitor turn001721 independent import review by exact boot/start identity. On terminal exit reconcile exact source review and findings. If scoped PASS, prospectively bind a NEW preparation recovery identity and refresh affected source/graph/native/runtime/controller records before any measurement. Never replay n36_readiness_preparation_001651. Production readiness and scientific promotion remain closed.'
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 state=yaml.safe_load((W/'research-state.yaml').read_text());checkpoint=json.loads((C/'checkpoint.json').read_text())
 for d in [state,checkpoint]:
  repair=d['n36_readiness_import_repair'];repair['status']='TERMINAL_CPU_REPAIR_HASH_VERIFIED_INDEPENDENT_REVIEW_RUNNING';repair['source_after']=r['code_ref'];repair['terminal_reconciliation']=ref(T/'terminal-reconciliation-v1.json');repair['report']=ref(A/'turns/001719/readiness-import-repair/report-v1.json')
  d['n36_readiness_import_repair_review']=entry;d['in_flight_executor']=entry;d['in_flight_executors']=[entry];d['next_action']=next_step
 atomic(W/'research-state.yaml',state,True);atomic(C/'checkpoint.json',checkpoint)
summary=dict(schema='autonomy-operational-summary-v1',turn=1721,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],repair_source_observed=dict(worktree=str(rw),commit=r['code_ref'],tracked_clean=True,reported_file_hashes_verified=True),live_handles=handles,controller_status='Prior preparation TERMINAL_ABORTED_CHARGED_IMPORT_FAILURE. CPU repair terminal; independent CPU review running. No GPU dispatch.',ledger_prefixes=prefixes,completed_work=['Verified hash-bound handoff, authority, live driver identities and ACTIVE/PASS isolation; owning ledger prefixes unchanged.','Reconciled terminal CPU repair at 1c10f9dd2afed8f8301e61f42dde46b8fa9565ed; two-file scope and reported file/diff hashes verified; 63 focused CPU checks reported.','Launched official current-login gpt-6-astra independent review; recorded exact live handles and owning checkpoint continuation.'],next_bounded_step=next_step,unresolved_evidence=['Independent repair review pending.','Native/runtime readiness proof and fresh recovery release absent.','Validation/formal/required ablation completion remains unproven; terminal telemetry incomplete.'],deadline_utc='2026-10-11T11:13:13Z',stop_present=False,target_met=False)
(T/'operational-summary-v1.json').write_text(json.dumps(summary,indent=2)+'\n');(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(json.dumps(ref(T/'operational-summary-v1.json')))
