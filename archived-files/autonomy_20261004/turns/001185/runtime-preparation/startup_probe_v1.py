"""Diagnostic source-only imports. No model, provider, simulator, or device calls."""
import os, sys, json, time, traceback, importlib
from pathlib import Path
OUT=Path(os.environ['N36_PREPARATION_OUTPUT'])
started=time.monotonic(); completed=[]; failure=None
try:
    for name in ('core','scripts.qd_ed_n36_worker','core.rdt_policy_steer','lerobot.processor.pipeline','lerobot.processor.env_processor','scripts.maniskill_model'):
        t=time.monotonic(); importlib.import_module(name); completed.append({'module':name,'seconds':time.monotonic()-t}); print('IMPORTED',name,flush=True)
    import torch
    assert not torch.cuda.is_initialized()
except BaseException as exc:
    failure={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    traceback.print_exc()
finally:
    state=sys.modules['_n36_source_bootstrap']
    result={'schema':'n36-actual-source-only-import-diagnostic-v1','completed':completed,'failure':failure,'elapsed_after_probe_entry':time.monotonic()-started,'isolated':bool(sys.flags.isolated),'no_site':bool(sys.flags.no_site),'dont_write_bytecode':bool(sys.flags.dont_write_bytecode),'pycache_prefix':sys.pycache_prefix,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'compiled':[{'module':n,'path':p,'sha256':h} for (n,p),h in sorted(state.compiled.items())],'startup_sources':state.startup_sources,'sys_path':sys.path,'core_initializer_suppressed':False,'source_loader_restored':False,'torch_cuda_initialized':getattr(sys.modules.get('torch'), 'cuda',None).is_initialized() if getattr(sys.modules.get('torch'), 'cuda',None) else None}
    (OUT/'startup-diagnostic-v1.json').write_text(json.dumps(result,indent=2)+'\n')
if failure: raise SystemExit(1)
