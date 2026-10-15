import subprocess, sys
from scripts import qd_ed_n36_runner as runner
from scripts import qd_ed_n36_source as source
from pathlib import Path
root=Path(__file__).parent
source.active()
argv=runner.worker_command(sys.executable,root,root/'absent-context.json','0'*64)
assert argv==source.command(sys.executable,root,'scripts.qd_ed_n36_worker','--context',str(root/'absent-context.json'),'--context-sha256','0'*64)
result=subprocess.run(argv+['--help'],capture_output=True,text=True,timeout=40)
assert result.returncode==0,(result.stdout,result.stderr)
assert '--context-sha256' in result.stdout
import torch
assert not torch.cuda.is_initialized()
# Synthetic inventory for checking the binding mechanism, not a release anchor.
state=source.active()
frozen={'files':[{'path':str(p.relative_to(root)),'sha256':source.sha(p)} for p in root.rglob('*.py')]}
runtime={'modules':{},'generated_modules':{}}
for name,path in list(state.compiled)+[(n,p) for n,(p,h) in state.startup_sources.items()]:
    if not Path(path).resolve().is_relative_to(root):
        runtime['modules'][name]={'path':str(Path(path).resolve()),'sha256':source.sha(path)}
receipt=source.attest(root,frozen,runtime)
loaded={'reference':{'path':'scripts/qd_ed_n31_reference.py','sha256':source.sha(root/'scripts/qd_ed_n31_reference.py')}}
source.verify_receipt(receipt,root,frozen,runtime,loaded=loaded)
receipt['compiled']=[r for r in receipt['compiled'] if r['module']!='scripts.qd_ed_n31_reference']
try: source.verify_receipt(receipt,root,frozen,runtime,loaded=loaded)
except ValueError as e: assert 'missing executable receipt' in str(e)
else: raise AssertionError('missing dependency executable receipt accepted')
print('actual runner-to-worker source entry verified')
