"""Root release of only the new bounded N28 arithmetic resource."""
from pathlib import Path
import datetime,json,os,sys,yaml
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree';sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n28_contract as c,qd_ed_n28_backend as b,qd_ed_n28_bridge as bridge
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
source=w.source_record(ROOT,c.source_paths(vars(r)));runtime=c.runtime_ref()
assert source==json.loads((V/'source-manifest-execution-v1.json').read_text())
bridge.verify(c.ref(c.BRIDGE),source,runtime,ROOT)
assert w.read_ref(c.ref(V/'root-source-runtime-check-v1.json'))['accepted'] is True
with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(ROOT/'data/qd-ed-state.lock'):
  state=r.read_state(ROOT/'research-state.yaml');c.require_budget_state(state,vars(r))
  resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl');events=r.read_events(ROOT/'data/attempt-ledger.jsonl')
  assert not any(e.get('kind')==b.KIND for e in resources)
  assert not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
  snap=r.budget_snapshot(events,resources);assert snap['running']==snap['gpu_healthcheck_inflight']==0
  source_review={'schema':'n28-arithmetic-source-review-v1','accepted':True,'source':source,'runtime':runtime,
    'source_bridge':c.ref(c.BRIDGE),'phase_b_protocol':c.ref(c.PROTOCOL),'arithmetic_protocol':c.ref(c.ARITHMETIC_PROTOCOL),
    'predecessor':c.predecessor(),'budget_reuse':c.budget_reuse(),'limits':b.LIMITS,'gpu_release':False}
  w.atomic_json(b.REVIEW,source_review);b.source_review(source,runtime,ROOT)
  authority={'schema':'n28-arithmetic-resource-authority-v1','source':source,'runtime':runtime,
    'source_review':c.ref(b.REVIEW),'budget_reuse':c.budget_reuse(),'limits':b.LIMITS,
    'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'automatic_retry':False,
    'dev_authorized':False,'validation_authorized':False,'formal_authorized':False}
  w.atomic_json(b.AUTHORITY,authority);state['n28_arithmetic_authority']=c.ref(b.AUTHORITY)
  b.authority(source,runtime,ROOT,state)
  state['current_iteration'].update(status='N28_NATIVE_PREFLIGHT_RELEASED',arithmetic_execution_authorized=True,execution_authorized=False)
  state['next_action']='Run only the once-released24-case N28 arithmetic resource on GPU7; require settled accepted proof before Dev adoption.'
  path=ROOT/'research-state.yaml';tmp=path.with_suffix('.yaml.n28-arith-tmp')
  with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
  release={'schema':'n28-tensor-resource-release-v1','source':source,'runtime':runtime,'authority':c.ref(b.AUTHORITY),'limits':b.LIMITS,'one_shot':True}
  w.atomic_json(b.RELEASE,release)
  cp_path=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';cp=json.loads(cp_path.read_text())
  cp.update(status='N28_NATIVE_PREFLIGHT_RELEASED',automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=c.PREFLIGHT,
    n28_arithmetic_authority=c.ref(b.AUTHORITY),n28_arithmetic_release=c.ref(b.RELEASE),next_action=state['next_action'])
  r.durable_json(cp_path,cp)
  w.atomic_json(V/'arithmetic-preflight-adoption-v1/root-release-record-v1.json',{'schema':'n28-root-one-resource-release-record-v1',
    'recorded_at':now,'release':c.ref(b.RELEASE),'source_review':c.ref(b.REVIEW),'cpu_review':c.ref(V/'root-phase-b-cpu-review-v1.json'),
    'runtime_review':c.ref(V/'root-source-runtime-check-v1.json'),'before_budget_snapshot':snap,'native_cuda_proof_yet':False,
    'episode_dispatch_authorized':False,'maximum_process_seconds':120,'maximum_native_cases':24})
print(json.dumps({'released':'N28 one native resource only','maximum_seconds':120,'gpu':7,'episodes':0,'model_api_sim_calls':0}))

