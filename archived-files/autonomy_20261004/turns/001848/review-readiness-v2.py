import os,sys,json,pathlib,hashlib,datetime,traceback
P=pathlib.Path
O=P('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001848')
B=O.parent
prior=json.loads((B/'001847/operational-summary-v1.json').read_text())
for name,r in prior['ledger_prefixes'].items():
 data=P(r['path']).read_bytes();assert hashlib.sha256(data[:r['bytes']]).hexdigest()==r['sha256'];assert len(data)==r['bytes']
g=json.loads((B/'001841/composition-v6/graph.complete-disabled-v1.json').read_text());root=P(g['production_required_worktree'])
os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(g['specification']);sys.path.insert(0,str(root));os.chdir(root)
from scripts import qd_ed_n36_readiness_prepare as m
e=m.e
proof=json.loads((B/'001847/terminal-reconciliation-v1.json').read_text())['proof'];proof={k:proof[k] for k in ('path','sha256')}
proof['path']=str(P(proof['path']).resolve())
record=dict(schema='n36-measured-readiness-root-review-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=prior['current_source'],proof=proof,episode_authorized=False)
try:
 spec=e.specification();source=e.read(g['source_record']);runtime=m.derive(spec,source,g['source_record'],proof)
 data=json.dumps(runtime,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 ref=dict(path=spec['runtime_binding']['runtime_path'],sha256=hashlib.sha256(data).hexdigest())
 (O/'prospective-runtime.json').write_bytes(data)
 record.update(status='PASS_FROZEN_DERIVE_ROOT_ACCEPTANCE_PENDING',runtime=ref,policy=m.policy(spec))
except Exception as ex:
 record.update(status='BLOCKED_FROZEN_READINESS_VALIDATOR',error=type(ex).__name__+': '+str(ex),traceback=traceback.format_exc())
(O/'readiness-review-v2.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
