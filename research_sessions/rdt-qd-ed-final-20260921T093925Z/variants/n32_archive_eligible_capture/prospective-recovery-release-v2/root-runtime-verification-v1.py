import sys,json,time,hashlib,datetime,subprocess
from pathlib import Path
root=Path.cwd().resolve();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w, qd_ed_n32_bridge as b, qd_ed_n32_worker as worker
out=root.parent/'prospective-recovery-release-v2'
start=time.monotonic()
def ref(p):
 p=Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
plan=w.read_ref(ref(out/'plan.frozen.CANDIDATE-v1.json'));runtime=w.read_ref(plan['runtime'])
result={'schema':'n32r2-root-full-runtime-verification-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':plan['source']['commit'],'plan':ref(out/'plan.frozen.CANDIDATE-v1.json'),'runtime':plan['runtime'],'script':ref(__file__),'gpu_dispatched':False,'production_approved':False}
try:
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==plan['source']['commit']
 w.verify_source(root,plan['source']);assert b.source_paths(root)=={v['path'] for v in plan['source']['files']}
 result['source_files_verified']=len(plan['source']['files'])
 result['loaded_attestation']=b.attest_loaded(root,plan['source']);result['worker_attestation']=worker.attest_worker_loaded(root,plan['source'])
 r.verify_files(runtime['files'],allowed_roots=(str(root),runtime['worktree'],runtime['artifact_root']))
 result['runtime_entries_verified']=len(runtime['files'])
 r.validate_runtime_inputs(plan,runtime,b.profiles(root),root,{'artifacts':runtime['artifact_root']})
 result['full_frozen_model_task_seed_validation']='PASS';result['status']='PASS'
except Exception as e:
 result['status']='FAIL';result['error']=repr(e)
result['elapsed_seconds']=time.monotonic()-start
w.atomic_json(out/'root-runtime-verification-result-v1.json',result)
print(json.dumps({k:v for k,v in result.items() if 'attestation' not in k},indent=2))
raise SystemExit(0 if result['status']=='PASS' else 1)
