import os,sys,json,pathlib,datetime,hashlib,yaml,fcntl
P=pathlib.Path;O=P('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001866');g=json.loads((O.parent/'001864/canonical-v2/graph.complete-disabled-v1.json').read_text());os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(g['specification']);sys.path.insert(0,g['production_required_worktree']);os.chdir(g['production_required_worktree'])
from scripts import qd_ed_n36_readiness_prepare as m
from scripts import qd_ed_n36_runner as runner
e=m.e;v=json.loads((O/'release-validation-v1.json').read_text());r=e.read(v['release']);a=e.read(r['accounting_authority']);spec=e.specification();plan=e.read(g['plan']);root=e.owner_root(plan)
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return dict(path=str(p),sha256=e.w.sha(p))
adoption=dict(schema='n36-preparation-accounting-adoption-v1',approved=True,accounting_authority=r['accounting_authority'],owner_root=str(root),resource_id=r['resource_id'],production_adoption=False)
with e.r.locked(root/'data/qd-ed-state.lock'):
 state,events,resources,reservations=runner.snapshot(root,a);snap=e.r.budget_snapshot(events,resources)
 e.exact({k:state['budget'].get(k) for k in snap},snap,'exact current accounting')
 prospective=dict(state);prospective[m.ADOPTION_SLOT]=adoption;m.validate_preparation_state(root,plan,a,r,prospective)
 protected=sum(max(0.,hours-snap['gpu_hours_by_bucket'][key]) for key,hours in a['caps']['protected_gpu_hours'].items());margin=e.accounting.retained_margin(root,a['margin_reference']);cap=min(state['budget']['max_gpu_hours'],float(e.accounting.ABSOLUTE_HOURS),float(e.accounting.WEEKLY_HOURS));need=r['gpu_seconds']/3600
 assert snap['gpu_healthcheck_inflight']==0 and snap['running']==0
 assert snap['gpu_hours_consumed']+protected+margin+need<=cap
 record=put(O/'prospective-arithmetic-v1.json',dict(schema='n36-preparation-prospective-arithmetic-v1',authority=r['accounting_authority'],retained_snapshot=snap,charged_gpu_hours=snap['gpu_hours_consumed'],protected_gpu_hours=protected,retained_margin_gpu_hours=margin,new_reservation_gpu_hours=need,total_committed_upper_bound=snap['gpu_hours_consumed']+protected+margin+need,effective_cap=cap,remaining_after_commitment=cap-snap['gpu_hours_consumed']-protected-margin-need,attempts_added=0,automatic_recoveries=0,production_adoption=False))

print(json.dumps(dict(status='PASS_PROSPECTIVE_ACCOUNTING_NOT_ADOPTED',arithmetic=record)))
