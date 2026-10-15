from pathlib import Path
import sys,json,copy,datetime,os,yaml
W=Path("/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z")/'study_worktree'
sys.path.insert(0,str(W))
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_arithmetic_repair as n
from scripts import qd_ed_n23_v2_preflight_admit as admit
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True),r.locked(W/'data/qd-ed-state.lock'):
 state_path=W/'research-state.yaml';state=r.read_state(state_path)
 assert 'n23_arithmetic_repair_authority' not in state
 source=w.source_record(W,c.source_paths(vars(r)))
 assert len(sys.argv)==2 and source['commit']==sys.argv[1]
 review=n.final_review(source,c.ref(c.GPU7_RUNTIME))
 events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
 n.named_failures(events,vars(r));n.first.no_dev(events)
 c.full_capacity(state,events,resources,vars(r),preflight=True)
 files=[W/'data'/f for f in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl')]
 hashes={str(p):w.sha(p) for p in files};before=copy.deepcopy(state['budget'])
 assert not n.AUTHORITY.exists()
 n.AUTHORITY.parent.mkdir(parents=True,exist_ok=True)
 (n.AUTHORITY.parent/'research-state.yaml.before').write_bytes(state_path.read_bytes())
 record={'schema':'n23-arithmetic-repair-authority-v3','exception':c.ref(n.EXCEPTION),
 'failed_review':c.ref(n.FAILURE_REVIEW),'prior_failure':c.ref(n.prior.FAILURE_REVIEW),
 'final_source_review':review,'source':source,'runtime':c.ref(c.GPU7_RUNTIME),
 'authority_interpretation':'Continuing user-authorized autonomous research includes this necessary bounded engineering repair. This is a prospective coordinator exception to an assistant-authored opportunity limit, not a new user approval, budget increase, scientific relaxation, or hidden retry. Preserve all three failed attempts and their costs; one additional recovery opportunity only.',
 'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'user_message':c.AUTONOMOUS_REPLY,
 'cumulative_caps':n.CAPS,'limits':n.LIMITS,'validation_authorized':False,'formal_authorized':False}
 w.atomic_json(n.AUTHORITY,record)
 state['n23_arithmetic_repair_authority']=c.ref(n.AUTHORITY)
 state['current_iteration'].update(status='ARITHMETIC_REPAIR_READY',source_commit=source['commit'],
 arithmetic_repair_authority=c.ref(n.AUTHORITY),dev_dispatched=False,backend_opportunities_consumed=3)
 plan=n.build_plan(W,vars(r))
 n.admission(plan,state,events,resources,r.read_events(files[2]),root=W,r=vars(r))
 assert state['budget']==before and {str(p):w.sha(p) for p in files}==hashes
 temp=state_path.with_name('.research-state.arithmetic-repair.tmp')
 with temp.open('w') as f:yaml.safe_dump(state,f,sort_keys=False);f.flush();os.fsync(f.fileno())
 os.replace(temp,state_path)
 applied={'schema':'n23-arithmetic-repair-adoption-applied-v3','authority':c.ref(n.AUTHORITY),
 'state_before':c.ref(n.AUTHORITY.parent/'research-state.yaml.before'),'state_after':c.ref(state_path),
 'journal_hashes_unchanged':hashes,'budget_unchanged':True,'snapshot':r.budget_snapshot(events,resources),
 'gpu_dispatched':False,'validation_authorized':False,'formal_authorized':False}
 w.atomic_json(n.AUTHORITY.parent/'applied.json',applied)
 print(json.dumps({'authority':c.ref(n.AUTHORITY),'applied':c.ref(n.AUTHORITY.parent/'applied.json'),'capacity':'PASS'}))

