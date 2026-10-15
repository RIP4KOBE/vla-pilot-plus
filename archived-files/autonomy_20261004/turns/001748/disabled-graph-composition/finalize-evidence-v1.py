import json,hashlib,datetime as dt
from pathlib import Path
O=Path(__file__).absolute().parent;Q=O/'composition-v3'
def rec(p):
 d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
def save(p,x):
 with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2);f.write('\n')
 return rec(p)
r=json.loads((Q/'report-v1.json').read_text());assert r['status']=='PASS_COMPLETE_DISABLED_GRAPH' and r['blockers']==[]
assert (Q/'report-v1.sha256').read_text().split()[0]==rec(Q/'report-v1.json')['sha256']
assert r['generated_audit_manifest_count']==40 and r['generated_engineering_manifest_count']==1
assert all(c['status']=='PASS' for c in r['checks'])
for m in ['generated-artifact-manifest-v1.json','outputs-manifest-v1.json']:
 for f in json.loads((Q/m).read_text())['files']:assert rec(Path(f['path']))==f,f['path']
attempts=[]
for p,s in [(O,'compose-disabled-v1.py'),(O/'composition-v2','compose-disabled-v2.py'),(Q,'compose-disabled-v3.py')]:
 d=json.loads((p/'report-v1.json').read_text())
 receipt=dict(schema='n36-cpu-composition-command-receipt-v1',at=dt.datetime.now(dt.timezone.utc).isoformat(),builder=rec(p/s),stdout_stderr=rec(p/'builder-stdout-v1.log'),report=rec(p/'report-v1.json'),process_exit_code=0,status=d['status'],blockers=d['blockers'],classification='PASS_UNMODIFIED_PRODUCTION_GRAPH' if p==Q else 'EXECUTOR_IO_GUARD_IMPORT_FAILURE_NOT_PRODUCTION_REJECTION',superseded_without_overwrite=p!=Q)
 receiptref=save(p/'command-receipt-v1.json',receipt);attempts.append(receiptref)
a=json.loads((O/'authority-v1.json').read_text());slots=json.loads(Path(a['downstream_slots']['path']).read_text());graph=json.loads(Path(r['graph']['path']).read_text())
files=[rec(p) for p in sorted(O.rglob('*')) if p.is_file()]
manifest=save(O/'complete-generated-artifact-manifest-v1.json',dict(schema='n36-complete-composition-output-manifest-v1',files=files,includes_preexisting_authority=True,excludes=['complete-generated-artifact-manifest-v1.json (self)','final-composition-index-v1.json','final-composition-index-v1.sha256'],all_existing_artifacts_preserved=True))
index=save(O/'final-composition-index-v1.json',dict(schema='n36-final-disabled-composition-index-v1',status=r['status'],final_report=rec(Q/'report-v1.json'),final_report_sha256=rec(Q/'report-v1.sha256'),graph=r['graph'],generated_artifact_manifest=manifest,production_generated_artifact_manifest=r['generated_artifact_manifest'],command_receipts=attempts,relocation_map=graph['relocation_map'],graph_slot_relocation=dict(original=slots['slots']['graph'],new=r['graph']),source=a['source'],resource_id=a['fresh_resource_id'],retained_charge_gpu_hours=a['retained_charge_gpu_hours'],recovery_of=a['recovery_of'],remaining_composition_blockers=[],remaining_future_gates=r['future_gates'],release_enabled=False,runtime_ready=False,provider_ready=False,gpu_authorized=False,provider_measurement_authorized=False,health_authorized=False,episode_authorized=False,b5_review=None,root_acceptance=None,source_edits=False,owning_state_mutation=False,note='Final report-v1.json is in composition-v3. Root and composition-v2 reports are retained failed import attempts; no artifact was overwritten. All 40 audit manifests and separate engineering manifest passed unmodified production verify_graph.'))
with (O/'final-composition-index-v1.sha256').open('x') as f:f.write(index['sha256']+'  final-composition-index-v1.json\n')
print(json.dumps(dict(status=r['status'],report=rec(Q/'report-v1.json'),index=index,checks=len(r['checks']),elapsed_builder_seconds=r['elapsed_builder_seconds'],artifacts=len(files))))
