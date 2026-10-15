"""Root integration/runtime/finite-budget review; no experiment dispatch."""
from pathlib import Path
import sys,json,datetime,yaml
C=Path(__file__).resolve().parent
W=C.parents[2]/'study_worktree'
sys.path.insert(0,str(W))
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n25_cont_contract as c,qd_ed_n25_cont_bridge as bridge
from scripts import qd_ed_n25_backend as backend

assert W.resolve()==r.ROOT.resolve() and C.resolve()==c.RUN_DIR.resolve()
for q in json.loads((C/'pre-integration-bookkeeping-v1.json').read_text()):assert w.sha(W/q['path'])==q['sha256']
seal=c.history(cleanup=True)
source=w.source_record(W,c.source_paths(vars(r)))
assert source==w.read_ref(c.ref(C.parent/'infrastructure-continuation-preparation-v1/source-manifest-v1.json'))
runtime=w.read_ref(seal['runtime']); c.old.validate_runtime(runtime,W,vars(r))
env=r.child_environment(runtime);r.verify_provider(runtime,env,root=W)
device=r.gpu_admission(physical_gpu=7,expected_uuid=runtime['gpu_mapping']['uuid'])
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
w.atomic_json(C/'source-bridge-v1.json',bridge.build(source,seal,W))
review={'schema':'n25-continuation-source-runtime-review-v1','accepted':True,'source':source,'runtime':seal['runtime'],
 'protocol':c.ref(c.PROTOCOL),'seal':c.ref(c.SEAL),'root_seal_review':c.ref(c.SEAL_REVIEW),'source_bridge':c.ref(c.BRIDGE),
 'historical_backend_proof':seal['historical_backend_proof'],'no_new_preflight':True,'gpu_authorized':False}
w.atomic_json(c.FINAL_REVIEW,review)
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(W/'data/qd-ed-state.lock'):
  state=r.read_state(W/'research-state.yaml');events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
  assert not c.local_events(events)
  snap=r.budget_snapshot(events,resources)
  assert snap['running']==snap['gpu_healthcheck_inflight']==0
  backend.settled_proof(w.read_ref(seal['historical_backend_proof']),resources,vars(r))
  reserved_h=sum(max(0.,v-snap['gpu_hours_by_bucket'][b]) for b,v in c.CAPS['protected_gpu_hours'].items())
  cap=min(22-seal['old_gpu_seconds']/3600,100-snap['gpu_hours_consumed']-reserved_h)
  authority={'schema':'n25-continuation-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':seal['runtime'],
   'protocol':c.ref(c.PROTOCOL),'seal':c.ref(c.SEAL),'final_review':c.ref(c.FINAL_REVIEW),
   'existing_budget_authority':state['n25_budget_authority'],'caps':c.CAPS,'limits':c.LIMITS,
   'original_local_gpu_hours':22.,'old_gpu_seconds':seal['old_gpu_seconds'],'remaining_local_gpu_hours':cap,
   'recorded_at':now,'authority_interpretation':'Root adopts the bounded, preregistered named infrastructure continuation under the user instruction to continue autonomously. No new user-audited budget or increased limit. Existing494/100 and all bucket/protected reserves unchanged.',
   'validation_authorized':False,'formal_authorized':False}
  w.atomic_json(c.AUTHORITY,authority)
  state['n25_continuation_authority']=c.ref(c.AUTHORITY)
  c.full_capacity(state,events,resources,vars(r))
  state['current_iteration'].update(status='INFRASTRUCTURE_CONTINUATION_REVIEWED_AWAITING_PLAN',execution_authorized=False,next_gpu_execution_authorized=False,continuation_authority=c.ref(c.AUTHORITY),continuation_seal=c.ref(c.SEAL))
  state['updated_at']=now
  state['next_action']='Freeze and inspect exact22-row N25 infrastructure continuation; one GPU7 launch only after root release. Codex managed chatgpt Stage only; no Poe or alternate account/provider fallback.'
  p=W/'research-state.yaml';temp=p.with_suffix('.yaml.continuation.tmp')
  with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True)
  temp.replace(p)
  w.atomic_json(C/'root-integration-review-v1.json',{'schema':'n25-continuation-root-integration-review-v1','accepted':True,'recorded_at':now,'source':source,'source_bridge':c.ref(c.BRIDGE),'final_review':c.ref(c.FINAL_REVIEW),'authority':c.ref(c.AUTHORITY),'budget_snapshot':snap,'remaining_local_gpu_hours':cap,'gpu_admission':device,'provider':'codex_cli/chatgpt/gpt-6-astra/low/E2/180s','credential_files_read_or_modified':False,'saved_poe_credentials_preserved':True,'gpu_launched':False})
print(json.dumps({'source_commit':source['commit'],'source_files':len(source['files']),'review':c.ref(c.FINAL_REVIEW),'authority':c.ref(c.AUTHORITY),'remaining_local_gpu_hours':cap,'snapshot':snap,'gpu_launched':False}))
