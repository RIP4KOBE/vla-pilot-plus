import json,hashlib,pathlib,datetime,fcntl,os,yaml,subprocess
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001718'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def save(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
prior=json.loads((A/'turns/001717/operational-summary-v1.json').read_text()); prefixes={}
for k,v in prior['ledger_prefixes'].items():
 p=pathlib.Path(v['path']);b=p.read_bytes();assert hashlib.sha256(b[:v['bytes']]).hexdigest()==v['sha256'];prefixes[k]={**ref(p),'prior_prefix_preserved':True}
for pid in [3116764,3116766,3122548,3128402]:assert not pathlib.Path(f'/proc/{pid}').exists()
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(); handles={}
for label,pid,ticks in [('driver',268073,97715947),('coordinator',3129601,154239184)]:
 vals=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();assert int(vals[19])==ticks;handles[label]=dict(pid=pid,start_ticks=ticks,boot_id=boot,state=vals[0])
rows=[json.loads(l) for l in (W/'data/gpu-healthcheck-ledger.jsonl').read_text().splitlines()]; row=rows[-1];assert row['event']=='aborted' and row['resource_id']=='n36_readiness_preparation_001651'
local=[json.loads(l) for l in (W/'data/readiness-preparation-ledger.jsonl').read_text().splitlines()];assert local[-1]==row
policy=json.loads((A/'turns/001694/preparation-accounting-repair/preparation-policy.prospective-disabled-v2.json').read_text()); out=pathlib.Path(policy['proof_path']).with_suffix('.measurement')
assert not pathlib.Path(policy['proof_path']).exists()
next_step='Diagnose and repair readiness required_after import handling in an isolated executor: child failed importing _remote_module_non_scriptable at qd_ed_n36_readiness_prepare.py:696. Preserve strict runtime/native closure audits and all charges; no replay of consumed preparation resource. Reconcile derived budget from terminal preparation journal, then require reviewed prospective recovery identity/release before any fresh measurement; production adoption and scientific gates remain closed.'
record=dict(schema='n36-preparation-terminal-reconciliation-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='ABORTED_CHARGED_IMPORT_FAILURE',source=prior['current_source'],exit=ref(A/'turns/001716/measurement-exit-v1.json'),child_log=ref(out/'child.log'),provider_transport=ref(out/'provider-transport.json'),ledger_prefixes=prefixes,terminal=row,mirrored_terminal_exact=True,retained_charge_gpu_hours=row['gpu_process_wall_seconds']/3600,all_measurement_handles_absent=True,proof_exists=False,diagnosis='ModuleNotFoundError: _remote_module_non_scriptable during required_after imports; provider transport returncode 0 does not constitute readiness success.',next_bounded_step=next_step,target_met=False)
save(T/'terminal-reconciliation-v1.json',record)
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,is_yaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text()); entry=d['n36_preparation_measurement_execution'];entry['status']='TERMINAL_ABORTED_CHARGED_IMPORT_FAILURE';entry['live_handles']=[];entry['terminal_reconciliation']=ref(T/'terminal-reconciliation-v1.json');d['next_action']=next_step
  tmp=p.with_name(p.name+'.tmp-001718');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
summary=dict(schema='autonomy-operational-summary-v1',turn=1718,at=record['at'],current_source=prior['current_source'],owning_source=prior['owning_source'],scientific_source=prior['scientific_source'],live_handles=handles,ledger_prefixes=prefixes,completed_work=['Verified bound authority, driver identity, deadline and both STOP paths.','Reconciled terminal failed readiness measurement; provider and GPU child handles absent; mirrored charge retained.','Recorded concrete import failure and updated owning state/checkpoint without source changes or duplicate dispatch.'],terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),next_bounded_step=next_step,unresolved_evidence=['Readiness native/runtime proof absent; derived budget reconciliation pending.','Reviewed engineering recovery, production adoption, validation/formal/ablation evidence pending.'],deadline_utc='2026-10-11T11:13:13Z',stop_present=any(p.exists() for p in [A/'STOP',pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP')]),target_met=False)
save(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(json.dumps(ref(T/'operational-summary-v1.json')))
