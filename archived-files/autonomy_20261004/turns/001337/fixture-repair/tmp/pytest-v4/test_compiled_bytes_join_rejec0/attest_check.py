import sys, hashlib
from pathlib import Path
from scripts import qd_ed_n36_source as source
import fixture
root=Path(__file__).parent
state=source.active()
# Explicitly synthetic inventories; this does not attest the installed runtime.
def inventories():
    files=[{'path':str(p.relative_to(root)),'sha256':source.sha(p)} for p in root.rglob('*.py')]
    runtime={'modules':{},'generated_modules':{},'interpreter':source.interpreter_identity()}
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if path and Path(path).is_file() and not Path(path).resolve().is_relative_to(root):
            runtime['modules'][name]={'path':str(Path(path).resolve()),'sha256':source.sha(path)}
    # Torch exposes virtual module objects whose __file__ is not the compiled
    # implementation path. Include the real loader's complete execution log.
    for name,path in list(state.compiled)+[(n,p) for n,(p,h) in state.startup_sources.items()]:
        if not Path(path).resolve().is_relative_to(root):
            runtime['modules'][name]={'path':str(Path(path).resolve()),'sha256':source.sha(path)}
    return {'files':files},runtime
frozen,runtime=inventories()
for name in ('os.path','posixpath'):
    runtime['modules'][name]={'path':str(Path(sys.modules[name].__file__).resolve()),'sha256':source.sha(sys.modules[name].__file__)}

# Fixture-only references: actual bytes under this temporary source tree.
from scripts import qd_ed_n23_worker as binding_worker
for alias,canonical in source.IMPORTLIB_FROZEN_PAIRS:
    path=Path(sys.modules[canonical].__file__).resolve()
    record={'path':str(path),'sha256':source.sha(path)}
    runtime['modules'][alias]=record
    runtime['modules'][canonical]=dict(record)
import json
(root/'synthetic-runtime.json').write_text(json.dumps(runtime,sort_keys=True))
binding={
    'context':{'path':str(Path(__file__).resolve()),'sha256':source.sha(__file__)},
    'runtime_closure':{'path':str(root/'synthetic-runtime.json'),
                       'sha256':source.sha(root/'synthetic-runtime.json')},
    'process':binding_worker.process_identity(), 'phase':'runtime_before'}
runtime_receipt={'schema':'n34-runtime-receipt-v2','binding':binding,
                 'modules':dict(runtime['modules']),'generated_modules':{}}

receipt=source.attest(root,frozen,runtime,binding=binding)
assert any(r['module']=='fixture' for r in receipt['compiled'])
(root/'fixture.py').write_text('value = "other!"\n')
new,_=inventories()
try: source.attest(root,new,runtime,binding=binding)
except ValueError as e: assert 'compiled source not frozen' in str(e)
else: raise AssertionError('live compiled bytes not checked')
import importlib.machinery
importlib.machinery.SourceFileLoader.get_code=lambda *a:None
try: source.active()
except ValueError as e: assert 'loader replaced' in str(e)
else: raise AssertionError('loader replacement accepted')
print('compiled source joins verified')
