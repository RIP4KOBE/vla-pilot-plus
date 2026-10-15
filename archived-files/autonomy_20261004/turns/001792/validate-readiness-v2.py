import pathlib,json,hashlib,sys,os,datetime,traceback
W=pathlib.Path.cwd(); T=W.parent/'autonomy_20261004/turns/001792'
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(p):return json.loads(p.read_text())
g=read(W.parent/'autonomy_20261004/turns/001788/graph.reviewed-disabled-v1.json')
source=read(pathlib.Path(g['source_record']['path']))
cwd=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
sys.path.insert(0,str(cwd));sys.dont_write_bytecode=True;os.chdir(cwd)
os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(g['specification'])
from scripts import qd_ed_n36_engineering_r1 as e,qd_ed_n36_readiness_prepare as prep
spec=e.specification();policy=prep.policy(spec);proof=ref(pathlib.Path(policy['proof_path']))
result=dict(schema='n36-measured-readiness-validation-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=g['source_record'],specification=g['specification'],proof=proof,gpu_dispatched=False,provider_called=False,production_adopted=False)
try:
 runtime=prep.derive(spec,source,g['source_record'],proof)
 data=json.dumps(runtime,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 preview=T/'runtime.measured-preview-v2.json';preview.write_bytes(data)
 result.update(status='PASS',preview=ref(preview),prospective_runtime=dict(path=spec['runtime_binding']['runtime_path'],sha256=hashlib.sha256(data).hexdigest()),acceptance_path=policy['acceptance_path'])
except Exception as exc:
 result.update(status='FAIL',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
(T/'readiness-validation-v2.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
