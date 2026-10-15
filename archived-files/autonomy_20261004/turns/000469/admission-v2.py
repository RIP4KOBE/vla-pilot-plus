import pathlib,sys,json,datetime,hashlib
root=pathlib.Path.cwd();sys.path[:0]=[str(root),str(root/"scripts")]
from scripts import qd_ed_n32r3_contract as c, qd_ed_n32r3_runner as n, qd_ed_n32r3_release as rel, qd_ed_final_runner as r
out=root.parent/'autonomy_20261004/turns/000469';prev=out.parent/'000468'
v=json.loads((prev/'release-validation-v2.json').read_text()); assert v['status']=='PASS'
p=c.read_ref(v['plan']); release=c.read_ref(v['release']); runtime=c.read_ref(p['runtime']);authority=c.read_ref(p['authority'])
probe=json.loads((out/'image-transport-probe-sanitized/result.json').read_text());assert probe['exit']==0 and probe['completed_turns']==1 and not probe['errors']
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True),r.locked(root/'data/qd-ed-state.lock'):
 state,events,resources,reservations=n.snapshot(root,authority)
 handles=n.continuation_handles(p,events);assert not handles,handles
 snap=rel.admission(p,authority,state,events,resources,reservations,p['episodes'][0],now=datetime.datetime.now(datetime.timezone.utc),gpu_idle=True)
 n.check_probe(runtime,resources,root)
 device=n.device_check();env=r.child_environment(runtime);r.verify_provider(runtime,env,root=root);r.runtime_gpu(runtime,state)
 record={'status':'PASS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan':v['plan'],'release':v['release'],'device':device,'budget_snapshot':snap,'handles':handles,'stage_probe':c.ref(out/'image-transport-probe-sanitized/result.json'),'ledger_prefix':n.journal_prefix(root/'data/attempt-ledger.jsonl'),'driver':json.loads((out.parent.parent/'driver-status.json').read_text()),'prior_turn_exit':json.loads((prev/'receipt.json').read_text())['exit']}
 (out/'admission.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record))
