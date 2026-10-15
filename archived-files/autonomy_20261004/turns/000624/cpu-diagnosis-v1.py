import os,sys,json,pathlib,hashlib
root=pathlib.Path.cwd();sys.path.insert(0,str(root));os.environ['CUDA_VISIBLE_DEVICES']=''
out=root.parent/'autonomy_20261004/turns/000624'
plan=json.loads((root.parent/'variants/n34_observed_jaw_approach/root-recovery-release-v2/plan.frozen-v1.json').read_text())
closure=json.loads(pathlib.Path(plan['runtime_closure']['path']).read_text())
manifest=json.loads(pathlib.Path(next(iter(plan['expected_manifests'].values()))['path']).read_text())
from scripts.qd_ed_n34_bridge import compose_launch
before=set(sys.modules)
config,resolved=compose_launch(manifest['argv'],plan['worktree'])
missing={}
for name,module in list(sys.modules.items()):
 if name.startswith('hydra') and getattr(module,'__file__',None):
  p=pathlib.Path(module.__file__).resolve();record={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
  if closure['modules'].get(name)!=record:missing[name]=record
record={'schema':'n34r1-cpu-runtime-diagnosis-v1','source':plan['source']['commit'],'probe':'CPU configuration composition only; no Main, model, environment, provider or GPU execution','new_hydra_modules':sorted(n for n in set(sys.modules)-before if n.startswith('hydra')),'missing_or_differing_frozen_hydra_modules':missing,'observed_failure_reproduced':'hydra._internal.core_plugins' in missing,'cause':'Runtime import probe captures inventory before prepare composes manifests; configuration composition lazily loads Hydra plugins later. Frozen closure is therefore incomplete at worker runtime-before attestation.','prospective_repair':'Run actual manifest configuration composition before prospective module inventory freeze, then verify strict runtime attestation again after prepare. Preserve old closure and invalid attempt; require a new recovery identity and detached release. No audit weakening.','source_repair_required_for_this_observed_failure':False,'unresolved':'Further lazy runtime paths must still pass complete public and native audits. CPU composition is not task success.'}
(out/'cpu-diagnosis-v1.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
