import pathlib,json,hashlib,sys,io,importlib
import torch
out=(pathlib.Path.cwd().parent/'autonomy_20261004/turns/000644').resolve()
plan=json.loads((out.parent.parent.parent/'variants/n34_observed_jaw_approach/root-recovery3-release-v1/plan.frozen-v1.json').read_text())
closure=json.loads(pathlib.Path(plan['runtime_closure']['path']).read_text())
before=set(sys.modules)
stream=io.BytesIO();torch.save({'probe':torch.tensor([1.,2.])},stream);stream.seek(0)
result=torch.load(stream,map_location='cpu',weights_only=True);assert torch.equal(result['probe'],torch.tensor([1.,2.]))
missing={}
for name,module in list(sys.modules.items()):
 if name.startswith('torch.utils.serialization') and getattr(module,'__file__',None):
  p=pathlib.Path(module.__file__).resolve();record={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
  if closure['modules'].get(name)!=record:missing[name]=record
assert 'torch.utils.serialization.config' in missing and not torch.cuda.is_initialized()
d={'schema':'n34r3-cpu-runtime-diagnosis-v1','source':plan['source']['commit'],'observed_missing_module_reproduced':True,'missing_serialization_modules':missing,'new_module_names':sorted(set(sys.modules)-before),'tiny_cpu_tensor_roundtrip':'PASS','cuda_initialized':False,'cause':'Prospective import inventory omits torch serialization config imported lazily by serialization operations; native post-run audit correctly rejected unbound runtime bytes.','prospective_repair':'Expand future CPU inventory to include serialization lazy imports and bounded representative CPU serialization paths. Keep exact module hashes and strict post-run attestation; inspect further lazy runtime paths before any fresh recovery release.','scope':'Tiny in-memory CPU tensor save/load only. No model, external checkpoint, environment, credentials, provider, GPU or protected evaluation.','retroactive_acceptance':False,'target_met':False}
(out/'cpu-diagnosis-v1.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))
