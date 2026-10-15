import json,sys,os
from pathlib import Path
A=Path(__file__).resolve().parent;N26=A.parent;R=N26.parent.parent;W=R/'study_worktree'
sys.path[:0]=[str(W/'scripts'),str(W)]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n26_contract as c,qd_ed_n26_backend as b,qd_ed_n26_logical as logical
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
 review=w.read_ref(c.ref(A/'root-integration-adoption-review-v1.json'))
 assert review['accepted'] and review['gpu_release'] is False
 source=w.read_ref(review['source']);runtime=c.runtime_ref()
 state=r.read_state(W/'research-state.yaml');events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
 assert state['online_stage_provider_policy']['poe_allowed'] is False
 snapshot=b.admission(state,events,resources,vars(r),source,runtime,W,
   reservation_events=r.read_events(W/'data/gpu-hour-reservation-ledger.jsonl'))
 w.verify_source(W,source)
 admission=r.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)
 logical.current_matching(events,resources)
 record={'schema':'n26-root-arithmetic-release-review-v1','accepted':True,
   'integration_review':c.ref(A/'root-integration-adoption-review-v1.json'),'source':review['source'],
   'runtime':runtime,'authority':c.ref(b.AUTHORITY),'budget_snapshot':snapshot,'gpu_admission':admission,
   'limits':b.LIMITS,'current_matching_journal_checked':True,
   'scope':'Exactly one tensor-only36-case process; zero model/API/simulation/episode calls; no retry.',
   'reader':c.ref(__file__)}
 w.atomic_json(A/'root-arithmetic-release-review-v1.json',record)
 release={'schema':'n26-tensor-resource-release-v1','source':source,'runtime':runtime,
   'authority':c.ref(b.AUTHORITY),'limits':b.LIMITS,'one_shot':True}
 w.atomic_json(b.RELEASE,release)
 print(json.dumps({'review':c.ref(A/'root-arithmetic-release-review-v1.json'),'release':c.ref(b.RELEASE)}))

