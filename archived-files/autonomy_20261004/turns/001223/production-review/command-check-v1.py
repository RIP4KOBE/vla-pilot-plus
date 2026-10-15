"""Evaluate exact command-construction and receipt comparison AST; no worker runs."""
import ast
import hashlib
import json
from pathlib import Path
import types

OUT=Path(__file__).resolve().parent
AUTH=json.loads((OUT/'authority-v1.json').read_text())
report=json.loads(Path(AUTH['candidate_report']['path']).read_text())
plan=json.loads(Path(report['candidate']['path']).read_text())
root=Path(plan['worktree'])
row=plan['episodes'][0]
manifest=json.loads(Path(plan['expected_manifests'][row['episode_key']]['path']).read_text())
context_ref={'path':str(Path(manifest['output_dir'])/'n36-worker-context.json'),'sha256':'0'*64}
def extract(relative, name, ns):
    p=root/relative
    tree=ast.parse(p.read_text())
    tree.body=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name]
    exec(compile(tree,str(p),'exec'),ns)
    return ns[name]
source_command=extract('scripts/qd_ed_n36_source.py','command',{'Path':Path})
worker_command=extract('scripts/qd_ed_n36_runner.py','worker_command',{'source_execution':types.SimpleNamespace(command=source_command)})
actual=worker_command(manifest['argv'][0],root,context_ref['path'],context_ref['sha256'])
tree=ast.parse((root/'scripts/qd_ed_n36_worker.py').read_text())
check=next(x for x in ast.walk(tree) if isinstance(x,ast.Call) and len(x.args)==2
           and isinstance(x.args[1],ast.Constant) and x.args[1].value=='worker command receipt differs')
context={'plan':{'path':report['candidate']['path'],'sha256':report['candidate']['sha256']},
         'release':{'path':'/not-created/release.json','sha256':'0'*64}}
command={'argv':actual,'main_argv':manifest['argv'],'context':context_ref}
ns={'manifest':manifest,'context_ref':context_ref,'command':command,'context':context}
accepted=eval(compile(ast.Expression(check.args[0]),'<exact-terminal-command-guard>','eval'),ns)
expected=eval(compile(ast.Expression(check.args[0].comparators[0]),'<exact-terminal-expected-command>','eval'),ns)
assert accepted is False
evidence=[]
for rel in ['scripts/qd_ed_n36_source.py','scripts/qd_ed_n36_runner.py','scripts/qd_ed_n36_worker.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_available_gpu_queue.py']:
    p=root/rel
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest==next(x['sha256'] for x in plan['source']['files'] if x['path']==rel)
    evidence.append({'path':str(p),'sha256':digest})
result={'schema':'n36-production-command-receipt-check-v1','status':'REPRODUCED_BLOCKER',
    'method':'Exact pure construction function and exact terminal comparison AST, in memory only. Synthetic context digest never written as authority.',
    'actual_runner_argv':actual,'terminal_expected_argv':expected['argv'],
    'terminal_accepts_runner_command':accepted,'terminal_guard_line':check.lineno,
    'worker_executed':False,'evidence':evidence}
with (OUT/'command-check-result-v1.json').open('x') as f:
    json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'status':result['status'],'terminal_accepts_runner_command':accepted,'line':check.lineno}))
