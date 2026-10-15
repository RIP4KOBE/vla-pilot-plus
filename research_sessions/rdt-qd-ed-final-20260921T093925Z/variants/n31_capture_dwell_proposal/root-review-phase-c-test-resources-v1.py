from pathlib import Path
import json,hashlib,subprocess,datetime,collections
P=Path(__file__).resolve().parent;I=P/'implementation'
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
cpu=wall=0.;receipts=[]
for n in range(1,9):
 e=json.loads((P/f'cpu-phase-c-run{n}-external.json').read_text());z=json.loads((P/f'cpu-phase-c-run{n}-resource.json').read_text())
 assert not Path('/proc/'+str(e['pid'])).exists()
 assert z['affinity']==[0,1] and z['threads']==2 and z['cuda_initialized'] is False and z['explicit_cuda_tensor_work']==0
 assert z['historical_payload_reads']==0 and z['cuda_visible_devices']==''
 assert e['exit']==(0 if n==8 else 1)
 assert z['guard_clean']==(n not in (5,6,7))
 if n in (5,6,7):
  assert z['denied']==[{'event':'os.scandir','path':str(I/'vlm_query')}]*2
 else:assert not z['denied']
 cpu+=e['child_cpu_seconds'];wall+=e['wall_seconds']
 receipts.append({'external':ref(P/f'cpu-phase-c-run{n}-external.json'),'resource':ref(P/f'cpu-phase-c-run{n}-resource.json'),'source':ref(P/f'cpu-phase-c-run{n}-source.json'),'exit':e['exit'],'guard_clean':z['guard_clean'],'pid_absent':True})
assert cpu<1200 and wall<1800
calls=[t for t in z['tests'] if t['when']=='call']
assert len(calls)==121 and all(t['outcome']=='passed' for t in calls) and len({t['nodeid'] for t in calls})==121
source=json.loads((P/'cpu-phase-c-run8-source.json').read_text())
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=I).decode().strip()
assert commit=='7428ce8a51f76c5f641537be9a7614631d82b0d9'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=I)
git_count=0
for item in source:
 path=Path(item['path']);assert ref(path)['sha256']==item['sha256']
 if path.is_relative_to(I):
  b=subprocess.check_output(['git','show',commit+':'+str(path.relative_to(I))],cwd=I)
  assert hashlib.sha256(b).hexdigest()==item['sha256'];git_count+=1
assert ref(I/'core/qd_capture_dwell_proposal.py')['sha256']=='e0b274e418aa9adc3cf7955ca162d830e66ffe9db79c65428573757e95fee843'
assert ref(I/'tests/test_qd_capture_dwell_proposal.py')['sha256']=='2ef8448fdbc5b0b247803ad94505aacbf3a5f9f19a3b44b6c183707a99c9eefe'
out={'schema':'n31-root-phase-c-test-resource-review-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'ACCEPT_FINAL_SYNTHETIC_TEST_AND_RESOURCE_EVIDENCE_ONLY','source_commit':commit,'receipts':receipts,'cumulative_child_cpu_seconds':cpu,'cumulative_wall_seconds':wall,'final_distinct_passing_cases':121,'final_run_sources_rehashed':len(source),'final_run_git_blobs_rehashed':git_count,'root_reran_tests':False,'root_arithmetic_replay':False,'gpu_execution_authorized':False,'budget_adopted':False,'target_achieved':False,'limitations':['Synthetic model/environment stubs are not real robot task evidence.','Runs5–7 have retained source-scan guard failures; only run8 provides final clean coverage.','Source packaging, independent bridge review and root adoption remain separate.','Source snapshot initially inspected with wrong dict assumption; corrected as255-entry list. No scientific execution resulted.'],'final_case_ids':[t['nodeid'] for t in calls]}
path=P/'root-phase-c-test-resource-review-v1.json'
with path.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'review':ref(path),'cpu':cpu,'wall':wall,'final_tests':len(calls),'git_blobs':git_count}))

