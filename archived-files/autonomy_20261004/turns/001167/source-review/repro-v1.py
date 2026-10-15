"""Two narrow source-review concerns; synthetic CPU tensors/files only."""
import ast, hashlib, importlib.util, importlib._bootstrap_external, json, os, sys
from pathlib import Path
from types import SimpleNamespace
import torch
ROOT=Path.cwd()
OUT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001167/source-review')
assert os.environ['CUDA_VISIBLE_DEVICES']==''
torch.set_num_threads(2)
sys.path.insert(0,str(ROOT))
results={}
# Execute the unchanged attest_loaded function body with only its inventory
# dependencies isolated, so no actual worker/release/runtime is invoked.
source=ROOT/'scripts/qd_ed_n34_source.py'
tree=ast.parse(source.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='attest_loaded')
fixture=OUT/'code-binding-fixture';fixture.mkdir(exist_ok=True)
path=fixture/'fixture.py';frozen='def value():\n    return "frozen"\n';stale='def value():\n    return "stale!"\n'
assert len(frozen)==len(stale)
path.write_text(frozen)
stat=path.stat();cache=Path(importlib.util.cache_from_source(str(path)));cache.parent.mkdir(exist_ok=True)
cache.write_bytes(importlib._bootstrap_external._code_to_timestamp_pyc(compile(stale,str(path),'exec'),int(stat.st_mtime),stat.st_size))
name='core.source_review_fixture';spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
namespace={'Path':Path,'sys':SimpleNamespace(modules={name:module}),'w':SimpleNamespace(require=require,sha=sha),'RDT_PREFIXES':('models','configs','data','rdt')}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
receipt=namespace['attest_loaded'](fixture,{'files':[{'path':'fixture.py','sha256':sha(path)}]})
results['loaded_code']={'frozen_source_return':'frozen','actual_return':module.value(),'source_hash':sha(path),'accepted_inventory':receipt,'stale_code_accepted':module.value()!='frozen'}
# No policy/provider/model execution: literal synthetic archive projection only.
from scripts.qd_ed_n36_arithmetic import verify_assignment
plans=torch.zeros((16,64,128),dtype=torch.bfloat16)
points=torch.zeros((1,3),dtype=torch.bfloat16)
origins=[torch.tensor([1.,0.,0.],dtype=torch.float64) for _ in range(16)]
xyz=torch.zeros((16,9,3),dtype=torch.bfloat16);xyz[:,:,0]=1
update={'geometry':{'source_origins':origins,'projected_xyz':xyz},'descriptors':torch.tensor([[1.,0.]]*16),
        'bounds_lo':torch.tensor([0.,-1.]),'bounds_hi':torch.tensor([2.,1.]),'cell_ids':torch.full((16,),10,dtype=torch.int64)}
verify_assignment(plans,points,update,False,device='cpu')
original=origins[0].clone();origins[0][0]+=0.001
verify_assignment(plans,points,update,False,device='cpu')
results['archive_origin']={'original_raw':original.tolist(),'corrupt_raw':origins[0].tolist(),
 'same_native_cast':torch.equal(original.bfloat16(),origins[0].bfloat16()),'corrupted_raw_origin_accepted':True,
 'scope':'verify_assignment helper; full worker not invoked; native auditor has no other geometry-origin binding'}
results['cuda_initialized']=torch.cuda.is_initialized()
assert not results['cuda_initialized']
(OUT/'repro-results-v1.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
