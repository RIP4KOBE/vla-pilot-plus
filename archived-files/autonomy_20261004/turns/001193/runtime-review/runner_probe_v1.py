import sys,json,runpy,hashlib,traceback
from pathlib import Path
O=Path(__file__).resolve().parent
A=json.loads((O/'authority-v1.json').read_text());D=json.loads(Path(A['draft']['path']).read_text());C=json.loads(Path(D['runtime_closure']['path']).read_text())
old=sys.argv
result={'scope':'Actual public runner --help plus source/runtime closure; no release validation or dispatch','release_enabled':False}
try:
 sys.argv=['scripts.qd_ed_n36_runner','--help']
 try:runpy.run_module('scripts.qd_ed_n36_runner',run_name='__main__',alter_sys=True)
 except SystemExit as e:assert e.code==0
 finally:sys.argv=old
 import torch
 assert not torch.cuda.is_initialized()
 from scripts import qd_ed_n36_source as se,qd_ed_n34_source as rs,qd_ed_n36_bridge as b
 # Only the review harness is added to the in-memory diagnostic inventory.
 ref={'path':str(Path(__file__).resolve()),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 C['modules']['runner_probe_v1']=ref;C['modules']['__main__']=ref;C['modules']['__mp_main__']=ref
 receipt=se.attest(D['worktree'],D['source'],C)
 loaded=b.attest_loaded(D['worktree'],D['source'])
 se.verify_receipt(receipt,D['worktree'],D['source'],C,loaded=loaded)
 binding={'purpose':'review public runner help only','probe':ref}
 rr=rs.attest_runtime_receipt(C,D['runtime'],binding=binding)
 rs.verify_runtime_receipt(C,rr,binding=binding)
 (O/'runner-source-execution-v1.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (O/'runner-runtime-execution-v1.json').write_text(json.dumps(rr,indent=2)+'\n')
 result.update(status='PASS',cuda_initialized=False,compiled_records=len(receipt['compiled']),runtime_modules=len(rr['modules']))
except BaseException as e:
 result.update(status='FAIL',error_type=type(e).__name__,error=str(e),traceback=traceback.format_exc());traceback.print_exc()
(O/'runner-probe-result-v1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));sys.exit(0 if result['status']=='PASS' else 1)
