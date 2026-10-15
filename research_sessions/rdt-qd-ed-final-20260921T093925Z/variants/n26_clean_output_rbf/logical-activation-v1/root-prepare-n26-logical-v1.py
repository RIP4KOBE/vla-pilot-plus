#!/usr/bin/env python3
"""Root prepare actual N26 admission; GPU release is a later explicit root step."""
import json,math,os,subprocess,sys,yaml
from pathlib import Path
from datetime import datetime,timezone
A=Path(__file__).resolve().parent;N26=A.parent;R=N26.parent.parent;W=R/'study_worktree'
C=R/'variants/n25_actuator_clipped_rbf/infrastructure-continuation-v1'
H=N26/'conditional-controller-cpu-v1'
sys.path[:0]=[str(W/'scripts'),str(W)]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n26_contract as c
from scripts import qd_ed_n26_logical as logical,qd_ed_n26_bridge as bridge,qd_ed_n26_backend as backend
def write(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
def ref(p):return c.ref(p)
def get(p):return w.read_ref(ref(p))
def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
  review=get(C/'root-logical-dev-review-v1.json')
  assert review['accepted'] and review['n26_predecessor_and_source_integration_authorized']
  assert ref(H/'root-cpu-review-v1.json')['sha256']=='1c7246994b2ce98c3c909484dfa24eb966c6cd1390d46cd4707d3566563c8f8b'
  source=w.source_record(W,c.source_paths(vars(r)))
  assert source==get(H/'source-manifest-v1.json') and source['commit']=='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
  before=get(C/'logical-dev-preparation-v1/pre-integration-bookkeeping-v1.json')
  for q in before['tracked_dirty_files']:assert w.sha(W/q['path'])==q['sha256']
  runtime_ref=c.runtime_ref();runtime=w.read_ref(runtime_ref)
  c.validate_runtime(runtime,W,vars(r))
  r.verify_provider(runtime,r.child_environment(runtime),root=W)
  evidence=get(C/'logical-dev-evidence-v1.json')
  gate={'schema':'n26-logical-predecessor-review-v1','disposition':'VALID_LOGICAL_DEV_REJECTION',
    'allow_n26':True,'allow_validation':False,'logical_disposition':evidence['logical_disposition'],
    'common_evidence':ref(C/'logical-dev-evidence-v1.json'),
    'continuation_root_review':ref(C/'root-terminal-review-v1.json'),'common_reader':evidence['reader'],
    'runtime':runtime_ref,'historical_backend_proof':evidence['settled_original_resource']['reference'],
    'composition_protocol':ref(c.LOGICAL_PROTOCOL),
    'admission_addendum':ref(W/'experiments/qd_ed_n26_logical/admission-addendum-v1.md')}
  write(c.PREDECESSOR,gate);logical.read_gate(root=W)
  write(N26/'source-manifest.logical-v1.json',source)
  b=bridge.build(source,runtime_ref,W);write(c.BRIDGE,b)
  events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
  logical.current_matching(events,resources)
  state=r.read_state(W/'research-state.yaml');snap=r.budget_snapshot(events,resources)
  assert snap['running']==snap['gpu_healthcheck_inflight']==0 and snap==review['budget_snapshot']
  assert state['budget']['max_episode_attempts']==494 and state['budget']['max_gpu_hours']==100.
  caps=json.loads(json.dumps(c.BASE_CAPS))
  for bucket,need in [('baseline',10),('development',30)]:
   caps['buckets'][bucket]=max(caps['buckets'][bucket],snap['by_bucket'][bucket]+need)
  caps['attempts']=sum(caps['buckets'].values())
  assert caps['attempts']==522 and caps['buckets']['baseline']==62 and caps['buckets']['development']==220
  protected_hours=sum(max(0.,h-snap['gpu_hours_by_bucket'][b]) for b,h in caps['protected_gpu_hours'].items())
  remaining=100.-snap['gpu_hours_consumed']-protected_hours
  assert remaining>(100+1840)/3600
  now=datetime.now(timezone.utc).isoformat()
  document=A/'finite-budget-amendment-v1.md'
  text=f"""# N26 finite resource amendment after logical N25 rejection

Recorded {now}. Root adoption under the user's continuing instruction “继续完成满足目标且无需我介入的autoresearch”, with the prior recorded prospective finite-adjustment policy. This is a coordinator decision under that delegation, not a separately user-audited522-attempt approval.

Current settled use: {snap['dispatched']} attempts and {snap['gpu_hours_consumed']:.12f} GPU hours; buckets {json.dumps(snap['by_bucket'])}. N25 original INVALID and its six unknown token calls remain; its valid logical continuation ended at28 accepted cells with C0=1/7,Q0=0/7,N23=0/7,N25=1/7. Independent terminal and logical evidence reviews are frozen.

N26 needs exactly40 primary matched Dev cells (10C0,10Q0,10N25,10N26), at most2 narrowly typed recovery opportunities. Only the required unprotected episode caps change: baseline55→62 (+7), development199→220 (+21), total494→522 (+28). Validation180/formal40/recovery20 attempt caps,100 cumulative GPU hours,32 validation/12 formal hour reservations remain unchanged. History is not erased or reattributed.

Current remaining unprotected hours: {remaining:.12f}. One new tensor-only proof uses at most60 active+40 cleanup seconds, billed as recovery health GPU wall with0episode/model/API/simulation calls. The Dev local cap will be frozen after this proof at no more than min(22, actual remaining unprotected hours), with1840 seconds available before each dispatch. There is no automatic retry for the proof or unmetered dispatch.

Scientific gates are unchanged: full40 valid cells and N26≥5/10 and≥all three controls; numeric futility only after a whole original task quadruple. No validation/formal launch or protected payload access is admitted here. Provider remains current Codex managed login only, no Poe/fallback. GPU7, one owned experiment worker. Artifacts remain under the unified experiment root.
"""
  document.write_text(text)
  interpretation='Root finite adoption under continuing user no-intervention delegation; not a separate user audit. Preserve100GPUh/protected reserves and all historical costs.'
  budget={'schema':'n26-finite-budget-authority-v1','cohort_id':c.COHORT,'caps':caps,
    'amendment':'n26-logical-finite-budget-20261001-v1','amendment_document':ref(document),
    'predecessor':ref(c.PREDECESSOR),'recorded_at':now,'authority_interpretation':interpretation}
  write(c.BUDGET_AUTHORITY,budget)
  arithmetic_review={'schema':'n26-arithmetic-source-review-v1','accepted':True,'source':source,'runtime':runtime_ref,
    'source_bridge':ref(c.BRIDGE),'phase_b_protocol':ref(c.PROTOCOL),'arithmetic_protocol':ref(c.ARITHMETIC_PROTOCOL),
    'admission_clarification':ref(c.CLARIFICATION),'predecessor':ref(c.PREDECESSOR),
    'budget_authority':ref(c.BUDGET_AUTHORITY),'composition_protocol':ref(c.LOGICAL_PROTOCOL),
    'logical_admission_addendum':ref(W/'experiments/qd_ed_n26_logical/admission-addendum-v1.md'),
    'limits':backend.LIMITS,'gpu_release':False}
  write(backend.REVIEW,arithmetic_review)
  arithmetic_authority={'schema':'n26-arithmetic-resource-authority-v1','source':source,'runtime':runtime_ref,
    'source_review':ref(backend.REVIEW),'budget_authority':ref(c.BUDGET_AUTHORITY),'limits':backend.LIMITS,
    'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'automatic_retry':False,
    'dev_authorized':False,'validation_authorized':False,'formal_authorized':False}
  write(backend.AUTHORITY,arithmetic_authority)
  with r.locked(W/'data/qd-ed-state.lock'):
   current=r.read_state(W/'research-state.yaml')
   assert current==state
   write(A/'pre-adoption-state-v1.json',state)
   current['budget'].update(max_episode_attempts=caps['attempts'],max_gpu_hours=100.,reserved=caps['buckets'],
      gpu_hour_reservations=caps['protected_gpu_hours'],amendment=budget['amendment'])
   current['n26_budget_authority']=ref(c.BUDGET_AUTHORITY)
   current['n26_arithmetic_authority']=ref(backend.AUTHORITY)
   current['n25_continuation_terminal']={'result':ref(C/'result-v1.json'),'root_review':ref(C/'root-terminal-review-v1.json'),
      'logical_evidence':ref(C/'logical-dev-evidence-v1.json'),'logical_review':ref(C/'root-logical-dev-review-v1.json'),
      'disposition':'REJECT_NUMERIC_FUTILITY','counts':evidence['counts']}
   current['current_iteration']={'candidate':'N26','status':'ARITHMETIC_PREPARATION_NO_RELEASE','target_met':False,
      'prepared_source_commit':source['commit'],'physical_gpu':7,'logical_predecessor':ref(c.PREDECESSOR),
      'budget_authority':ref(c.BUDGET_AUTHORITY),'cpu_review':ref(H/'root-cpu-review-v1.json'),
      'validation_authorized':False,'formal_authorized':False}
   tmp=W/'research-state.yaml.root-n26-tmp'
   with tmp.open('w') as f:yaml.safe_dump(current,f,sort_keys=False);f.flush();os.fsync(f.fileno())
   os.replace(tmp,W/'research-state.yaml')
  c.budget_authority();backend.source_review(source,runtime_ref,W)
  backend.authority(source,runtime_ref,W,current)
  final={'schema':'n26-root-logical-integration-and-finite-adoption-v1','accepted':True,
    'source':ref(N26/'source-manifest.logical-v1.json'),'runtime':runtime_ref,'predecessor':ref(c.PREDECESSOR),
    'source_bridge':ref(c.BRIDGE),'budget_authority':ref(c.BUDGET_AUTHORITY),'pre_adoption_snapshot':snap,
    'remaining_unprotected_hours_before_tensor_proof':remaining,'arithmetic_source_review':ref(backend.REVIEW),
    'arithmetic_authority':ref(backend.AUTHORITY),'provider_verified':'codex_cli/current-managed-chatgpt-login',
    'poe_or_account_fallback_allowed':False,'gpu_release':False,'reviewer':ref(__file__)}
  write(A/'root-integration-adoption-review-v1.json',final)
  print(json.dumps({'review':ref(A/'root-integration-adoption-review-v1.json'),'caps':caps,
    'remaining_unprotected_hours':remaining,'predecessor':ref(c.PREDECESSOR),'gpu_release':False}))
if __name__=='__main__':main()

