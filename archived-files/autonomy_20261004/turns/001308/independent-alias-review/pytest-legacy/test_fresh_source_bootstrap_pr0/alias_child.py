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
# Partial, observed CPU inventory for testing the actual producer. This is
# explicitly not the complete committed production source freeze.
root=Path(execution.__file__).resolve().parents[1]
state=execution.active()
source_files={str(root/'scripts/qd_ed_n36_bootstrap.py'):state.bootstrap_digest}
for (name,path),digest in state.compiled.items():
    path=str(Path(path).resolve())
    if Path(path).is_relative_to(root): source_files[path]=digest
    elif name not in runtime['modules']: runtime['modules'][name]={'path':path,'sha256':digest}
for name,module in list(sys.modules.items()):
    path=getattr(module,'__file__',None)
    if path and Path(path).is_file() and not Path(path).resolve().is_relative_to(root) and name not in runtime['modules']:
        runtime['modules'][name]={'path':str(Path(path).resolve()),'sha256':execution.sha(path)}
source={'files':[{'path':str(Path(path).relative_to(root)),'sha256':digest} for path,digest in source_files.items()]}
# Freeze this expanded test-only inventory before the parent's handoff.
frozen_path=runtime_path.with_name('observed-runtime.json')
frozen_path.write_text(json.dumps(runtime))
binding['runtime_closure']={'path':str(frozen_path),'sha256':execution.sha(frozen_path)}
print('READY',flush=True)
assert sys.stdin.read(1)=='G'
receipt=execution.attest(root,source,runtime,binding=binding)
print(json.dumps(receipt),flush=True)
