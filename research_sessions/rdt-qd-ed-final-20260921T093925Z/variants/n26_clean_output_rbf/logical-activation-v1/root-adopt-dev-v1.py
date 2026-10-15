import json,math,os,sys,yaml
from pathlib import Path
from datetime import datetime,timezone
A=Path(__file__).resolve().parent;N26=A.parent;R=N26.parent.parent;W=R/'study_worktree'
sys.path[:0]=[str(W/'scripts'),str(W)]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n26_contract as c,qd_ed_n26_backend as b,qd_ed_n26_logical as logical
from scripts import qd_ed_n25_cont_evidence as e
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
 source=w.read_ref(c.ref(N26/'source-manifest.logical-v1.json'));runtime=c.runtime_ref()
 proof=b.verify_proof(c.ref(c.BACKEND_PROOF),source,runtime,W)
 events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
 b.settled_proof(proof,resources,vars(r));logical.current_matching(events,resources)
 report=w.read_ref(proof['report']);process=w.read_ref(proof['process']);terminal=w.read_ref(proof['terminal'])
 cleanup=e.process_cleanup([{k:process[k] for k in ('pid','proc_start_ticks','boot_id')}])
 assert len(report['cases'])==36 and all(x['accepted'] for x in report['cases'])
 assert report['backend']['physical_uuid']==c.GPU7_UUID
 assert all(report[k]==0 for k in ('model_calls','api_calls','simulation_steps','episodes'))
 assert report['worker_wall_seconds']<=terminal['gpu_process_wall_seconds']<=100
 review={'schema':'n26-root-actual-arithmetic-proof-review-v1','accepted':True,'proof':c.ref(c.BACKEND_PROOF),
  'source':c.ref(N26/'source-manifest.logical-v1.json'),'runtime':runtime,'cases':36,
  'dtypes':sorted({x['dtype'] for x in report['cases']}),'layouts':sorted({x['layout'] for x in report['cases']}),
  'physical_gpu':7,'uuid':c.GPU7_UUID,'worker_wall_seconds':report['worker_wall_seconds'],
  'charged_gpu_seconds':terminal['gpu_process_wall_seconds'],'episode_attempts':0,'api_calls':0,
  'cleanup':cleanup,'historical_proof_relabelled':False,'dev_release':False,'reviewer':c.ref(__file__)}
 w.atomic_json(A/'root-actual-proof-review-v1.json',review)
 final={'schema':'n26-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
  'protocol':c.ref(c.PROTOCOL),'source_plan':c.ref(c.SOURCE_PLAN),'source_bridge':c.ref(c.BRIDGE),
  'predecessor':c.ref(c.PREDECESSOR),'backend_proof':c.ref(c.BACKEND_PROOF),
  'arithmetic_protocol':c.ref(c.ARITHMETIC_PROTOCOL),'admission_clarification':c.ref(c.CLARIFICATION),
  'composition_protocol':c.ref(c.LOGICAL_PROTOCOL),
  'logical_admission_addendum':c.ref(W/'experiments/qd_ed_n26_logical/admission-addendum-v1.md'),'no_gpu_release':True}
 w.atomic_json(c.FINAL_REVIEW,final)
 caps=c.budget_authority()['caps'];snap=r.budget_snapshot(events,resources)
 protected=sum(max(0,h-snap['gpu_hours_by_bucket'][k]) for k,h in caps['protected_gpu_hours'].items())
 local=math.floor(min(22.,100.-snap['gpu_hours_consumed']-protected)*10000)/10000
 assert local>=1840/3600 and local<=22.
 authority={'schema':'n26-dev-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':runtime,
  'protocol':c.ref(c.PROTOCOL),'final_review':c.ref(c.FINAL_REVIEW),'budget_authority':c.ref(c.BUDGET_AUTHORITY),
  'limits':c.LIMITS,'local_gpu_hours':local,'recorded_at':datetime.now(timezone.utc).isoformat(),
  'authority_interpretation':'Root finite N26 matched Dev adoption under continuing user no-intervention delegation; current Codex only. Validation and formal remain closed.',
  'admission_clarification':c.ref(c.CLARIFICATION),'composition_protocol':c.ref(c.LOGICAL_PROTOCOL),
  'logical_predecessor':c.ref(c.PREDECESSOR),'validation_authorized':False,'formal_authorized':False}
 w.atomic_json(c.AUTHORITY,authority)
 with r.locked(W/'data/qd-ed-state.lock'):
  state=r.read_state(W/'research-state.yaml');state['n26_dev_authority']=c.ref(c.AUTHORITY)
  state['current_iteration'].update(status='DEV_PREPARED_NOT_RELEASED',actual_tensor_proof=c.ref(c.BACKEND_PROOF),
    actual_proof_review=c.ref(A/'root-actual-proof-review-v1.json'),authority=c.ref(c.AUTHORITY),local_gpu_hours=local)
  tmp=W/'research-state.yaml.root-n26-tmp'
  with tmp.open('w') as f:yaml.safe_dump(state,f,sort_keys=False);f.flush();os.fsync(f.fileno())
  os.replace(tmp,W/'research-state.yaml')
 c.final_review(source,runtime,W);c.authority(source,runtime,W,state)
 c.full_capacity(state,events,resources,vars(r))
 print(json.dumps({'proof_review':c.ref(A/'root-actual-proof-review-v1.json'),'final_review':c.ref(c.FINAL_REVIEW),
  'authority':c.ref(c.AUTHORITY),'local_gpu_hours':local,'budget_snapshot':snap,'dev_released':False}))

