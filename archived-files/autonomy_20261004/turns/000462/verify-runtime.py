import sys,json,time,hashlib,datetime,subprocess
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w, qd_ed_n32r3_bridge as b
out=root.parent/'autonomy_20261004/turns/000462'
def ref(p):
 p=Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
p=root.parent/'variants/n32_archive_eligible_capture/root-continuation-release-v3/accounted-composition-input-v1.json'; plan=w.read_ref(ref(p));runtime=w.read_ref(plan['runtime']); start=time.monotonic()
result={'schema':'n32r3-runtime-readiness-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':plan['source']['commit'],'composition':ref(p),'runtime':plan['runtime'],'script':ref(__file__),'gpu_dispatched':False,'production_approved':False}
try:
 assert not Path(plan['stop_path']).exists()
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==plan['source']['commit']
 w.verify_source(root,plan['source']);b.attest_loaded(root,plan['source'])
 result['source_files_verified']=len(plan['source']['files'])
 r.verify_files(runtime['files'],allowed_roots=(str(root),runtime['worktree'],runtime['artifact_root']))
 result['runtime_entries_verified']=len(runtime['files'])
 r.validate_runtime_inputs(plan,runtime,b.profiles(root),root,{'artifacts':runtime['artifact_root']})
 result['status']='PASS'
except Exception as e: result.update(status='FAIL',error=repr(e))
result['elapsed_seconds']=time.monotonic()-start
w.atomic_json(out/'runtime-verification.json',result);print(json.dumps(result))
