import json,sys,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent; C=P.parent; R=C.parent.parent.parent; W=R/'study_worktree'
sys.path[:0]=[str(W/'scripts'),str(W)]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n25_cont_downstream as common
manifest=w.read_ref(common.e.ref(C.parent/'infrastructure-continuation-preparation-v1/downstream-common-cpu-v1/source-manifest-v2.json'))
w.verify_source(W,manifest)
before=json.loads((P/'pre-integration-bookkeeping-v1.json').read_text())
for q in before['tracked_dirty_files']:assert w.sha(W/q['path'])==q['sha256']
with r.locked(C/'execution/supervisor.lock',nonblocking=True):
 with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
  sys.argv=[str(W/'scripts/qd_ed_n25_cont_downstream.py'),'--input',str(P/'metadata-input-authorized-v1.json'),
    '--output',str(C/'logical-dev-evidence-v1.json')]
  common.main()
  d=json.loads((C/'logical-dev-evidence-v1.json').read_text())
  print(json.dumps({'evidence':common.e.ref(C/'logical-dev-evidence-v1.json'),
    'logical_disposition':d['logical_disposition'],'accepted_cells':d['accepted_cells'],
    'counts':d['counts'],'allow_n26':d['allow_n26'],'allow_validation':d['allow_validation'],
    'metadata_bytes':d['metadata_bytes']}))

