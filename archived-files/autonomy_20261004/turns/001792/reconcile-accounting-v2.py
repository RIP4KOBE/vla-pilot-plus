from pathlib import Path
import sys,json,yaml,hashlib,fcntl,os,datetime
W=Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001792';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
sys.path.insert(0,'/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
from scripts import qd_ed_final_runner as r
prior=json.loads((A/'turns/001791/operational-summary-v1.json').read_text())
def verify():
 for x in prior['ledger_prefixes'].values():
  b=Path(x['path']).read_bytes();assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256']
def write(p,d,y=False):
 q=p.with_name(p.name+'.001792.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
with (C/'state.lock').open('a') as lock,(W/'data/qd-ed-state.lock').open('a') as lock2:
 fcntl.flock(lock,fcntl.LOCK_EX);fcntl.flock(lock2,fcntl.LOCK_EX);verify()
 s=yaml.safe_load((W/'research-state.yaml').read_text());snap=r.budget_snapshot([json.loads(l) for l in (W/'data/attempt-ledger.jsonl').read_text().splitlines()],[json.loads(l) for l in (W/'data/gpu-healthcheck-ledger.jsonl').read_text().splitlines()]);assert not s['current_owned_workers'] and snap['running']==snap['gpu_healthcheck_inflight']==0
 delta={k:dict(previous=s['budget'][k],recomputed=v) for k,v in snap.items() if s['budget'][k]!=v}
 expected=234.72371816635132/3600
 print(json.dumps(delta));assert snap['gpu_hours_consumed']==s['budget']['gpu_hours_consumed'];assert abs(snap['gpu_healthcheck_hours']-s['budget']['gpu_healthcheck_hours']-expected)<1e-12
 assert abs(snap['gpu_hours_by_bucket']['recovery']-s['budget']['gpu_hours_by_bucket']['recovery']-expected)<1e-12
 p=T/'full-ledger-accounting-v1.json';d=dict(schema='n36-current-full-ledger-accounting-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),ledger_prefixes=prior['ledger_prefixes'],changes=delta,snapshot=snap,terminal_reconciliation=prior['terminal_reconciliation'],reason='Retain completed preparation charge exactly once in all authoritative accounting summaries.',caps_changed=False,charges_erased=False,unknown_telemetry_preserved=True)
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 rr=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
 s['budget'].update(snap);s['budget_snapshot']=snap;s['n36_current_full_ledger_accounting']=rr;write(W/'research-state.yaml',s,True)
 cp=json.loads((C/'checkpoint.json').read_text());cp['budget_snapshot']=snap;cp['n36_current_full_ledger_accounting']=rr;write(C/'checkpoint.json',cp)
 verify();print(json.dumps(delta))
