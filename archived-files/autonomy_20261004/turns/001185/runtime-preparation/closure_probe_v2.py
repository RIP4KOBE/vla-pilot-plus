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
 phases.append({'phase':phase,'seconds':time.monotonic()-t0});phase='source_closure';t=time.monotonic()
 from scripts import qd_ed_n36_bridge as b,qd_ed_n34_source as s,qd_ed_n36_source as se
 source=s.source_record(ROOT,b.source_paths(ROOT));write('source-owning-v1.json',source)
 phases.append({'phase':phase,'seconds':time.monotonic()-t,'files':len(source['files'])});phase='runtime_inventory';t=time.monotonic()
 previous=json.loads((TURN/'000916/runtime-v1/runtime-closure-v1.json').read_text());closure=json.loads(json.dumps(previous))
 # Preserve every previous prospective source hash. Add actual external imports and
 # source-loader transient inputs as candidate coverage; never replace a conflicting hash.
 added={}; conflicts=[];state=se.active()
 for name,mod in list(sys.modules.items()):
  if name in ('torch.ops','torch.classes',s.GENERATED_NAME,'__main__','__mp_main__','_n36_source_bootstrap'):continue
  p=getattr(mod,'__file__',None)
  if not p:continue
  p=Path(p).resolve()
  if p.is_relative_to(ROOT):continue
  row=ref(p)
  if name in closure['modules'] and closure['modules'][name]!=row:conflicts.append({'module':name,'old':closure['modules'][name],'new':row});closure['modules'][name]=row
  elif name not in closure['modules']:added[name]=row;closure['modules'][name]=row
 for (name,p),digest in state.compiled.items():
  p=Path(p).resolve()
  if p.is_relative_to(ROOT) or name==s.GENERATED_NAME:continue
  row=ref(p);assert row['sha256']==digest
  if name not in closure['modules']:closure['modules'][name]=row;added[name]=row
  elif closure['modules'][name]!=row:
   canonical='triton.backends.'+name+'.'+p.stem
   assert name in ('amd','nvidia') and p.parent.name==name and p.stem=='driver'
   closure['modules'][canonical]=row;added[canonical]=row
 # The diagnostic is inventoried by its canonical runpy name, not as a replacement worker.
 write('runtime-inventory-delta-v2.json',{'added':added,'conflicts':conflicts,'prior':ref(TURN/'000916/runtime-v1/runtime-closure-v1.json'),'production_closure_complete':False})
 write('runtime-closure-candidate-v2.json',closure)
 phases.append({'phase':phase,'seconds':time.monotonic()-t,'added':len(added),'conflicts':len(conflicts)})
 assert all(x['module']=='_cyutility' for x in conflicts)
 closure['modules']['scipy._cyutility']=previous['modules']['_cyutility']
 write('runtime-closure-candidate-v2.json',closure)
 phase='strict_source_execution_attestation';t=time.monotonic()
 receipt=se.attest(ROOT,source,closure)
 write('source-execution-diagnostic-v2.json',receipt)
 loaded=b.attest_loaded(ROOT,source)
 se.verify_receipt(receipt,ROOT,source,closure,loaded=loaded)
 phases.append({'phase':phase,'seconds':time.monotonic()-t})
 phase='strict_runtime_attestation';t=time.monotonic()
 # Diagnostic Main aliases are external harness entries, unlike production worker.
 diagnostic_closure=json.loads(json.dumps(closure))
 diagnostic_closure['modules']['__main__']=ref(__file__)
 diagnostic_closure['modules']['__mp_main__']=ref(__file__)
 # Bootstrap aliases belong to owning source, handled by source attestation.
 binding={'purpose':'CPU import-only diagnostic; no release or actual worker-body claim','source':source['commit'],'probe':ref(__file__)}
 rr=s.attest_runtime_receipt(diagnostic_closure,closure['runtime'],binding=binding,after=True)
 s.verify_runtime_receipt(diagnostic_closure,rr,binding=binding,after=True)
 write('runtime-execution-diagnostic-v2.json',rr)
 phases.append({'phase':phase,'seconds':time.monotonic()-t})
 assert not torch.cuda.is_initialized()
 write('closure-probe-result-v2.json',{'status':'PASS_DIAGNOSTIC_ONLY','phases':phases,'cuda_initialized':False,'elapsed_seconds':time.monotonic()-t0})
except BaseException as exc:
 traceback.print_exc()
 write('closure-probe-result-v2.json',{'status':'FAILED','phase':phase,'phases':phases,'elapsed_seconds':time.monotonic()-t0,'failure':{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}})
 raise
