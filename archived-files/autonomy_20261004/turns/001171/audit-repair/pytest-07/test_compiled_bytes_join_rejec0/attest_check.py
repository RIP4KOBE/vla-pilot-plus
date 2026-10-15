import sys, hashlib
from pathlib import Path
from scripts import qd_ed_n36_source as source
import fixture
root=Path(__file__).parent
state=source.active()
# Explicitly synthetic inventories; this does not attest the installed runtime.
def inventories():
    files=[{'path':str(p.relative_to(root)),'sha256':source.sha(p)} for p in root.rglob('*.py')]
    runtime={'modules':{},'generated_modules':{}}
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if path and Path(path).is_file() and not Path(path).resolve().is_relative_to(root):
            runtime['modules'][name]={'path':str(Path(path).resolve()),'sha256':source.sha(path)}
    return {'files':files},runtime
frozen,runtime=inventories()
receipt=source.attest(root,frozen,runtime)
assert any(r['module']=='fixture' for r in receipt['compiled'])
(root/'fixture.py').write_text('value = "other!"\n')
new,_=inventories()
try: source.attest(root,new,runtime)
except ValueError as e: assert 'compiled source not frozen' in str(e)
else: raise AssertionError('live compiled bytes not checked')
import importlib.machinery
importlib.machinery.SourceFileLoader.get_code=lambda *a:None
try: source.active()
except ValueError as e: assert 'loader replaced' in str(e)
else: raise AssertionError('loader replacement accepted')
print('compiled source joins verified')
