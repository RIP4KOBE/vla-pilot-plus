import os,sys,json,pathlib,datetime,hashlib,yaml,fcntl
P=pathlib.Path;O=P('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001870');g=json.loads((O.parent/'001864/canonical-v2/graph.complete-disabled-v1.json').read_text());os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(g['specification']);sys.path.insert(0,g['production_required_worktree']);os.chdir(g['production_required_worktree'])
from scripts import qd_ed_n36_readiness_prepare as m
from scripts import qd_ed_n36_runner as runner
e=m.e;v=json.loads((O.parent/'001866/release-validation-v1.json').read_text());r=e.read(v['release']);a=e.read(r['accounting_authority']);spec=e.specification();plan=e.read(g['plan']);root=e.owner_root(plan)
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return dict(path=str(p),sha256=e.w.sha(p))
with e.r.locked(root/'data/qd-ed-state.lock'):
 state,events,resources,reservations=runner.snapshot(root,a);snap=e.r.budget_snapshot(events,resources)
 old={k:state['budget'].get(k) for k in snap}
 own=m.journal_rows(root);mirrors=[x for x in resources if x.get('kind')=='readiness_preparation'];e.exact(own,mirrors,'exact mirrored journal')
 rid='n36_readiness_preparation_recovery_001858'
 terminal=[x for x in own if x.get('resource_id')==rid and x.get('event')=='completed']
 assert len(terminal)==1
 charge=terminal[0]['gpu_process_wall_seconds']/3600
 expected=json.loads(json.dumps(old))
 expected['gpu_healthcheck_hours']+=charge;expected['gpu_hours_by_bucket']['recovery']+=charge
 def same(x,y):
  if isinstance(x,dict):return x.keys()==y.keys() and all(same(x[k],y[k]) for k in x)
  if isinstance(x,float):return abs(x-y)<1e-10
  return x==y
 assert same(expected,snap),(old,snap,charge)
 assert snap['running']==snap['gpu_healthcheck_inflight']==0
 prefixes={}
 for n in [*e.JOURNALS,'readiness-preparation-ledger.jsonl']:
  p=root/'data'/n;prefixes[n]=dict(path=str(p),bytes=p.stat().st_size,sha256=e.w.sha(p))
 record=put(O/'accounting-reconciliation-v1.json',dict(schema='owning-accounting-reconciliation-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),reason='State total already retained readiness001858 charge; recovery bucket and healthcheck subtotal were stale by its exact mirrored terminal charge.',authority=a['approval_basis'],old_snapshot=old,new_snapshot=snap,retained_terminal=terminal[0],added_total_gpu_hours=0,added_recovery_subtotal_gpu_hours=charge,added_healthcheck_subtotal_gpu_hours=charge,ledger_prefixes=prefixes,ledger_mutations=False,attempts_added=0,new_dispatch=False))
 for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text())
  if isyaml:d['budget'].update(snap)
  d['budget_snapshot']=snap
  d.setdefault('accounting_reconciliation_history',[]).append(record)
  d['n36_latest_accounting_reconciliation']=record
  temp=p.with_name(p.name+'.001870.tmp');temp.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(temp,p)
 print(json.dumps(dict(status='PASS_RECONCILED_EXISTING_CHARGE',record=record,charge=charge,current_gpu_hours=snap['gpu_hours_consumed'])))
