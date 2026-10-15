import json, os, sys
from pathlib import Path
from scripts import qd_ed_n36_source as execution
execution.active()
runtime_path, context_path = map(Path,sys.argv[1:])
runtime=json.loads(runtime_path.read_text())
binding={'context':{'path':str(context_path),'sha256':execution.sha(context_path)},
 'runtime_closure':{'path':str(runtime_path),'sha256':execution.sha(runtime_path)},
 'process':{'pid':os.getpid(),'proc_start_ticks':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
 'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()},'phase':'runtime_before'}
print('READY',flush=True)
assert sys.stdin.read(1)=='G'
claim=execution.live_alias(runtime,binding)
print(json.dumps({'schema':'n36-source-execution-v2','binding':binding,'interpreter':runtime['interpreter'],
 'frozen_modules':['posixpath'],'frozen_aliases':{'os.path':claim}}),flush=True)
