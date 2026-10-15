"""Record actual controller identity, then run the unchanged released supervisor."""
import json,sys,runpy
from pathlib import Path
A=Path(__file__).resolve().parent;N26=A.parent;W=N26.parent.parent/'study_worktree'
sys.path[:0]=[str(W/'scripts'),str(W)]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n26_contract as c
plan=N26/'plan.frozen.v1.gpu7.json';release=N26/'execution-release-v1.json'
status=N26/'execution/supervisor-status-v1.json'
(N26/'execution').mkdir(parents=True,exist_ok=True)
with r.locked(N26/'execution/root-controller-record.lock',nonblocking=True):
 record={'schema':'n26-root-controller-process-v1','process':w.process_identity(),
   'source_commit':'6026794cd5d52f3a5054bf2704ebb3c516f9f47e',
   'plan':c.ref(plan),'release':c.ref(release),'entrypoint':c.ref(W/'scripts/qd_ed_n26_supervise.py'),
   'wrapper':c.ref(__file__),'physical_gpu':7,'one_launch':True}
 w.atomic_json(N26/'execution/controller-process-v1.json',record)
 print(json.dumps({'controller':record['process'],'plan':record['plan'],'gpu':7}),flush=True)
sys.argv=[str(W/'scripts/qd_ed_n26_supervise.py'),'--plan',str(plan),'--release',str(release),'--status',str(status)]
runpy.run_path(str(W/'scripts/qd_ed_n26_supervise.py'),run_name='__main__')

