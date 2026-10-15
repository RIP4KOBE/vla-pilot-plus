import importlib.abc,json,os,subprocess,sys,time
from pathlib import Path
root=Path.cwd().resolve();out=root.parent/'submodule-freeze-repair-v1'
sys.path.insert(0,str(root))
blocked=('main','transformers','diffusers','mujoco','robosuite','libero','mani_skill','scripts.maniskill_model','core.rdt_policy_steer')
class NoModelSimulator(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if any(fullname==prefix or fullname.startswith(prefix+'.') for prefix in blocked):
   raise AssertionError('Forbidden CPU-check import: '+fullname)
sys.meta_path.insert(0,NoModelSimulator())
from scripts import qd_ed_n23_worker as w, qd_ed_n32_bridge as b
start=time.monotonic()
paths=b.source_paths(root)
source=w.source_record(root,paths)
assert set(paths)=={x['path'] for x in source['files']}
assert w.verify_source(root,source)==source['sha256']
assert source['commit']==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
loaded=b.attest_loaded(root,source)
assert not any(any(name==p or name.startswith(p+'.') for p in blocked) for name in sys.modules)
assert os.environ['CUDA_VISIBLE_DEVICES']==''
(out/'source-record-v1.json').write_text(json.dumps(source,indent=2)+'\n')
result={'commit':source['commit'],'source_file_count':len(paths),'source_sha256':source['sha256'],'verify_source_return':source['sha256'],'loaded_attestation':loaded,'blocked_import_prefixes':blocked,'forbidden_imports':[],'gpu_or_model_or_simulator_executed':False,'seconds':time.monotonic()-start,'rdt_gitlink':subprocess.check_output(['git','ls-tree',source['commit'],'third_party/rdt'],text=True).strip(),'status':'PASS','release_generated':False,'scientific_success':None}
(out/'roundtrip-result-v1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
