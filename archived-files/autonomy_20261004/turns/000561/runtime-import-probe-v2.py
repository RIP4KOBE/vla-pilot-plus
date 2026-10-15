import os,sys,json,pathlib,hashlib,importlib,importlib.metadata,ast,traceback
root=pathlib.Path.cwd(); out=(root.parent/'autonomy_20261004/turns/000561').resolve()
rpath=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n32_archive_eligible_capture/root-recovery-release-v2/runtime.owning-v1.json')
r=json.loads(rpath.read_text()); os.environ.update(r['environment']);os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.path[:0]=[str(root)]+r['environment']['PYTHONPATH'].split(':')
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
# Import only top-level import statements from Main; do not execute its dotenv loader or entrypoint.
ns={'__name__':'n34_root_import_probe'}; errors=[]; imported=[]
for node in ast.parse((root/'main.py').read_text()).body:
 if isinstance(node,(ast.Import,ast.ImportFrom)):
  try: exec(compile(ast.Module(body=[node],type_ignores=[]),str(root/'main.py'),'exec'),ns);imported.append(ast.unparse(node))
  except Exception as e: errors.append({'import':ast.unparse(node),'error':str(e),'type':type(e).__name__})
for name in ['scripts.qd_ed_n34_worker','core.rdt_policy_steer','core.env_adapters.libero_adapter','lerobot.processor.pipeline','lerobot.processor.env_processor','robosuite.controllers.osc','scripts.maniskill_model']:
 try: importlib.import_module(name);imported.append(name)
 except Exception as e: errors.append({'import':name,'error':str(e),'type':type(e).__name__})
# Explicit lazy imports used by deployed RDT policy/model and native audit.
for statement in [
 'from transformers import T5EncoderModel, AutoTokenizer, AutoConfig, SiglipImageProcessor, SiglipVisionModel',
 'from safetensors.torch import load_model',
 'from torchvision import transforms',
 'from scipy.spatial.transform import Rotation',
 'from lerobot.utils.constants import OBS_ENV_STATE, OBS_IMAGE, OBS_IMAGES, OBS_STATE, OBS_STR',
 'import scripts.audit_decision_evidence',
 'import scripts.qd_ed_n34_native',
]:
 try: exec(statement, ns); imported.append(statement)
 except Exception as e: errors.append({'import':statement,'error':str(e),'type':type(e).__name__})
from scripts import qd_ed_n34_source as s, qd_ed_n34_bridge as b
import torch
external={};local={}; missing=[]
for n,m in list(sys.modules.items()):
 if n in ('torch.ops','torch.classes','__main__'):continue
 p=getattr(m,'__file__',None)
 if not p:continue
 p=pathlib.Path(p).resolve()
 if not p.is_file():missing.append({'module':n,'path':str(p)});continue
 (local if p.is_relative_to(root) else external)[n]=ref(p)
paths=b.source_paths(root)
uncovered={n:v for n,v in local.items() if str(pathlib.Path(v['path']).relative_to(root)) not in paths}
record={'schema':'n34-root-prospective-runtime-import-probe-v1','runtime':ref(rpath),'probe':ref(__file__),'imports':imported,'errors':errors,'external_modules':external,'checkout_modules':local,'uncovered_checkout_modules':uncovered,'missing_files':missing,'interpreter':{**ref(sys.executable),'version':sys.version},'distribution_versions':{n:importlib.metadata.version(n) for n in ['torch','numpy','robosuite','mujoco','transformers']},'cuda_initialized':torch.cuda.is_initialized(),'gpu_dispatched':False,'scope':'Prospective CPU import coverage only. No model loading, environment construction, rollout, protected evaluation or candidate-receipt discovery. Not a complete runtime release.'}
(out/'runtime-import-probe-v2.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'external_modules':len(external),'checkout_modules':len(local),'errors':errors,'uncovered':uncovered,'missing':missing,'cuda_initialized':record['cuda_initialized']}))

# Candidate authority commits ordinary bytes and the reviewed generated-content rule.
# No candidate/native outcome is read or used to discover trust.
assert not errors and not uncovered and not missing and not torch.cuda.is_initialized()
generated=external.pop(s.GENERATED_NAME)
closure={'schema':'n34-runtime-source-closure-v2','runtime':ref(rpath),
 'modules':external,'required_after':[s.GENERATED_NAME,'robosuite.controllers.osc','transformers.models.t5.modeling_t5','transformers.models.siglip.modeling_siglip'],
 'interpreter':record['interpreter'],'distribution_versions':record['distribution_versions'],
 'versions':{'python':sys.version,'torch':torch.__version__,'libero':'superproject committed checkout; bound separately by source record','robosuite':record['distribution_versions']['robosuite'],'mujoco':record['distribution_versions']['mujoco']},
 'generated_modules':{s.GENERATED_NAME:{'rule':s.GENERATED_RULE,'generator':external[s.GENERATOR_NAME],'template':external[s.TEMPLATE_NAME],'sha256':generated['sha256']}}}
(out/'runtime-closure.CANDIDATE-v2.json').write_text(json.dumps(closure,indent=2)+'\n')
binding={'purpose':'CPU prospective runtime preparation only','source':os.popen('git rev-parse HEAD').read().strip(),'probe':ref(__file__)}
receipt=s.attest_runtime_receipt(closure,ref(rpath),binding=binding,after=True)
s.verify_runtime_receipt(closure,receipt,binding=binding,after=True)
from scripts.qd_ed_n34_controller import verify_semantics
verify_semantics(ref(root.parent/'autonomy_20261004/turns/000539/n34-controller-semantics-v1.json'),ref(rpath),closure)
(out/'runtime-probe-receipt-v2.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'runtime_attestation':'PASS','ordinary':len(receipt['modules']),'generated':list(receipt['generated_modules']),'controller_proof':'PASS','release_enabled':False}))

from scripts.qd_ed_n34_prepare import prepare
plan=prepare(out/'prospective-draft-v1',ref(rpath),runtime_closure_ref=ref(out/'runtime-closure.CANDIDATE-v2.json'),controller_semantics_ref=ref(root.parent/'autonomy_20261004/turns/000539/n34-controller-semantics-v1.json'))
print(json.dumps({'draft_manifests':len(plan['expected_manifests']),'source':plan['source']['commit'],'scientific_source':plan['scientific_source']['commit'],'release_enabled':plan['release_enabled']}))
