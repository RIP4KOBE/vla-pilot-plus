import json,hashlib,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
C=P.parent; N25=C.parent; R=N25.parent.parent; W=R/'study_worktree'
D=N25/'infrastructure-continuation-preparation-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def read(p):return json.loads(Path(p).read_text())
def write(p,d):
 with Path(p).open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
data=read(P/'metadata-input-draft-v1.json');seal=read(C/'metadata-seal-v1.json')
assert data['root_authorized'] is False and len(data['files'])==206
old={str(Path(x['path']).resolve()):x for x in seal['metadata_files']}
allfiles={str(Path(x['path']).resolve()):x for x in data['files']}
assert len(old)==131 and len(allfiles)==206 and all(allfiles[k]==v for k,v in old.items())
denied={'events.jsonl','stage_events.jsonl','stage_responses.jsonl','attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl'}
total=0
for q in data['files']:
 p=Path(q['path']);assert p.name not in denied and not p.is_symlink()
 assert p.stat().st_size<=16*1024*1024 and sha(p)==q['sha256'];total+=p.stat().st_size
assert total<=128*1024*1024
result=read(C/'result-v1.json');review=read(C/'root-terminal-review-v1.json')
assert review['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION' and review['cohort_disposition']==result['decision']=='REJECT_NUMERIC_FUTILITY'
assert review['accepted_cells']==28 and review['cleanup']['no_owned_processes']
assert len(data['references'])==15
assert data['references']['root_review']==ref(C/'root-terminal-review-v1.json')
names=subprocess.check_output(['git','diff','--name-only'],cwd=W,text=True).splitlines()
snapshot={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip(),
 'tracked_dirty_files':[{'path':n,'sha256':sha(W/n)} for n in names]}
assert snapshot['commit']=='6f796358aa84d53e9c8a04859f7d19352c9db7fe'
write(P/'pre-integration-bookkeeping-v1.json',snapshot)
data['root_authorized']=True
write(P/'metadata-input-authorized-v1.json',data)
record={'schema':'n25-root-logical-metadata-and-common-integration-review-v1','accepted':True,
 'authorized_input':ref(P/'metadata-input-authorized-v1.json'),
 'input_draft':ref(P/'metadata-input-draft-v1.json'),
 'roles':ref(P/'root-metadata-roles-v1.json'),'collector':ref(D/'downstream-root-activation-v1/root-collect-logical-dev-v1.py'),
 'independent_terminal':ref(C/'root-terminal-review-v1.json'),'metadata_files':206,'distinct_metadata_bytes':total,
 'old_sealed_metadata_files':131,'new_accepted_cells':10,'new_typed_metadata_per_cell':6,
 'raw_stage_reads':0,'tensor_reads':0,'protected_payload_reads':0,
 'accepted_common_cpu_review':ref(D/'downstream-common-cpu-v1/root-cpu-review-v2.json'),
 'next_commit':'ff285373cc69a898cb1f5e6ed9cbbfe370a2972a',
 'source_integration_authorized':True,'scope':'Five additive accepted common files only; invoke bounded logical evidence after integration under dead-controller and runner locks.',
 'n26_admission_authorized':False,'validation_authorized':False,'gpu_authorized':False}
write(P/'root-metadata-integration-review-v1.json',record)
print(json.dumps({'review':ref(P/'root-metadata-integration-review-v1.json'),'input':record['authorized_input'],'metadata_bytes':total}))

