"""Actual source-only import and strict attestation; never runs Main or constructs runtime objects."""
import os,sys,json,time,traceback,importlib,hashlib
from pathlib import Path
OUT=Path(os.environ['N36_PREPARATION_OUTPUT']);ROOT=Path.cwd();TURN=OUT.parent.parent
phases=[];phase='imports'
def write(name,data):
 p=OUT/name;p.write_text(json.dumps(data,indent=2)+'\n');return ref(p)
def ref(p):
 p=Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
t0=time.monotonic()
try:
 for name in ['core','scripts.qd_ed_n36_worker','core.rdt_policy_steer','lerobot.processor.pipeline','lerobot.processor.env_processor','scripts.maniskill_model','core.env_adapters.libero_adapter','robosuite.controllers.osc','gymnasium','cv2','imageio','matplotlib.pyplot','h5py','hydra','omegaconf','tqdm','sentencepiece','dotenv','utils.guidance_utils','core.decision_evidence','lerobot.policies.factory','core.render_phase_diagnostics','core.passive_physics_trace','utils.vis_utils','scripts.qd_ed_n36_prepare']:
  importlib.import_module(name)
 from transformers import T5EncoderModel,AutoTokenizer,AutoConfig,SiglipImageProcessor,SiglipVisionModel,T5Tokenizer,T5TokenizerFast
 from safetensors.torch import load_model
 from torchvision import transforms
 from scipy.spatial.transform import Rotation
 import torch
 assert not torch.cuda.is_initialized()

 phases.append({'phase':phase,'seconds':time.monotonic()-t0});phase='frozen_source_and_runtime_attestation';t=time.monotonic()
 from scripts import qd_ed_n36_bridge as b,qd_ed_n34_source as s,qd_ed_n36_source as se,qd_ed_n36_build as nb
 source=json.loads((OUT/'source-owning-v1.json').read_text());closure=json.loads((OUT/'runtime-closure-v2.json').read_text())
 s.verify_source(ROOT,source)
 receipt=se.attest(ROOT,source,closure);loaded=b.attest_loaded(ROOT,source)
 se.verify_receipt(receipt,ROOT,source,closure,loaded=loaded)
 write('source-execution-frozen-v2.json',receipt)
 diagnostic_closure=json.loads(json.dumps(closure));diagnostic_closure['modules']['__main__']=ref(__file__);diagnostic_closure['modules']['__mp_main__']=ref(__file__)
 binding={'purpose':'CPU prospective frozen inventory verification only','source':source['commit'],'probe':ref(__file__)}
 runtime_receipt=s.attest_runtime_receipt(diagnostic_closure,closure['runtime'],binding=binding,after=True)
 s.verify_runtime_receipt(diagnostic_closure,runtime_receipt,binding=binding,after=True)
 write('runtime-execution-frozen-v2.json',runtime_receipt)
 phases.append({'phase':phase,'seconds':time.monotonic()-t});phase='static_native_build_and_cpu_mapping';t=time.monotonic()
 native={'schema':'n36-native-build-v1','torch_version':str(torch.__version__),'cuda_version':torch.version.cuda,'torch_build':torch.__config__.show(),'libraries':json.loads((OUT/'native-libraries-static-v1.json').read_text())['libraries']}
 native_ref=ref(OUT/'native-build-v2.json')
 mapped=nb.mapped_libraries(Path('/proc/self/maps').read_text());old_native=json.loads((OUT/'native-build-v1.json').read_text());old_paths={r['path'] for r in old_native['libraries']}
 write('native-mapping-diagnostic-v2.json',{'actual_mapped_paths':mapped,'not_bound_by_failed_v1_inventory':[x for x in mapped if x not in old_paths],'cuda_initialized':torch.cuda.is_initialized(),'native_manifest':native_ref})
 cpu_mapped=nb.attest(native_ref,after=False)
 write('native-cpu-mapped-v2.json',cpu_mapped)
 assert not torch.cuda.is_initialized()
 phases.append({'phase':phase,'seconds':time.monotonic()-t});phase='disabled_all40_prepare';t=time.monotonic()
 from scripts.qd_ed_n36_prepare import prepare
 plan=prepare(OUT/'draft',closure['runtime'],runtime_closure_ref=ref(OUT/'runtime-closure-v2.json'),controller_semantics_ref=ref(OUT/'controller-semantics-v1.json'),native_build_ref=native_ref,root=ROOT)
 assert plan['worktree']==str(ROOT) and plan['release_enabled'] is False and len(plan['expected_manifests'])==40
 phases.append({'phase':phase,'seconds':time.monotonic()-t});phase='post_composition_source_and_runpy';t=time.monotonic()
 import runpy
 before_main=sys.modules['__main__']; before_argv=list(sys.argv)
 ns=runpy.run_module('scripts.qd_ed_n36_contract',run_name='n36_contract_runpy_diagnostic',alter_sys=True)
 assert sys.modules['__main__'] is before_main and sys.argv==before_argv
 assert ns['__name__']=='n36_contract_runpy_diagnostic' and ns['__package__']=='scripts' and ns['__spec__'].name=='scripts.qd_ed_n36_contract'
 write('runpy-diagnostic-v1.json',{'status':'PASS','module':'scripts.qd_ed_n36_contract','run_name':ns['__name__'],'package':ns['__package__'],'spec_name':ns['__spec__'].name,'argv_restored':True,'main_module_restored':True,'actual_Main_not_executed':'Main calls dotenv; credential reads forbidden. Reuse reviewed source run_main semantics tests.'})
 receipt=se.attest(ROOT,source,closure);se.verify_receipt(receipt,ROOT,source,closure,loaded=b.attest_loaded(ROOT,source))
 write('source-execution-post-compose-v1.json',receipt)
 assert not torch.cuda.is_initialized()
 phases.append({'phase':phase,'seconds':time.monotonic()-t})
 write('prepare-artifacts-result-v2.json',{'status':'PASS_DISABLED_DRAFT_CPU_ONLY','phases':phases,'elapsed_seconds':time.monotonic()-t0,'draft':ref(OUT/'draft/plan.draft.json'),'native_after_cuda': 'UNRESOLVED_NOT_EXECUTED','cuda_initialized':False,'release_enabled':False})
except BaseException as exc:
 traceback.print_exc()
 write('prepare-artifacts-result-v2.json',{'status':'FAILED','phase':phase,'phases':phases,'elapsed_seconds':time.monotonic()-t0,'failure':{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}})
 raise
