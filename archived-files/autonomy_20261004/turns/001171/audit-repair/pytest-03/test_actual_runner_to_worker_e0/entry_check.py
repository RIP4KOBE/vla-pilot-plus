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
print('actual runner-to-worker source entry verified')
