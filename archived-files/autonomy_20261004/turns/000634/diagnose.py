import sys,pathlib,json,hashlib,importlib,ast
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/000634').resolve()
plan=json.loads((root.parent/'variants/n34_observed_jaw_approach/root-recovery2-release-v2/plan.frozen-v1.json').read_text());closure=json.loads(pathlib.Path(plan['runtime_closure']['path']).read_text())
before=set(sys.modules)
# Import package code only. Never call load_dotenv or inspect any environment/credential file.
importlib.import_module('dotenv')
missing={}
for name,module in list(sys.modules.items()):
 if name.startswith('dotenv') and getattr(module,'__file__',None):
  p=pathlib.Path(module.__file__).resolve();record={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
  if closure['modules'].get(name)!=record:missing[name]=record
assert 'dotenv.parser' in missing
record={'schema':'n34r2-cpu-runtime-diagnosis-v1','source':plan['source']['commit'],'observed_failure_reproduced':True,'missing_dotenv_modules':missing,'probe_scope':'CPU import of dotenv code only; no load_dotenv call, credential/env-file read, Main execution, model, environment, provider or GPU execution.','cause':'Main imports dotenv inside a top-level try block. Existing probe selects only direct top-level Import/ImportFrom nodes and therefore omits this nested import. Worker later loads it and strict post-run runtime attestation rejects it.','prospective_repair':'Include explicit dotenv code import in future CPU inventory probe without invoking loader. Review other nested imports in Main for analogous omissions. Keep exact module path/hash attestations and all native gates; no retroactive acceptance. Fresh recovery identity/release before further dispatch.','unresolved':'Only the first runtime omission is observed; a future native run may expose more lazy imports. CPU import coverage is not scientific evidence.','gpu_dispatched':False,'target_met':False}
(out/'cpu-diagnosis-v1.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
