"""Offline applied-tree parity review; only synthetic local paths, no worker/model/provider."""
import ast
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import yaml

ROOT = Path(__file__).resolve().parents[4]
BASE = '33954ead452927fc3168efb610487a688f89169e'
CHECKS = Path(__file__).resolve().parent

def digest(data):
    return hashlib.sha256(data).hexdigest()

def blob(path):
    return subprocess.check_output(['git', 'show', BASE+':'+path], cwd=ROOT)

paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, '--', 'main.py', 'core', 'utils', 'configs', 'vlm_query'], cwd=ROOT, text=True).splitlines()
scientific = []
for name in paths:
    old = blob(name); current = (ROOT/name).read_bytes()
    same = old == current
    ast_same = same or name.endswith('.py') and ast.dump(ast.parse(old), include_attributes=False) == ast.dump(ast.parse(current), include_attributes=False)
    scientific.append(dict(path=name, byte_equal=same, ast_equal=bool(ast_same), frozen_sha256=digest(old), current_sha256=digest(current)))
assert all(row['byte_equal'] or row['path']=='core/codex_stage_policy.py' and row['ast_equal'] for row in scientific)

frozen_source = blob('scripts/run_steering.py').decode()
current_source = (ROOT/'scripts/run_steering.py').read_text()
old_ast, new_ast = ast.parse(frozen_source), ast.parse(current_source)
def nodes(tree, kind): return [n for n in ast.walk(tree) if isinstance(n,kind)]
def dumped(node): return ast.dump(node,include_attributes=False)
def assigned(tree,name):
    return next(n.value for n in nodes(tree,ast.Assign) if any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
def call(tree, owner, method):
    return next(n for n in nodes(tree,ast.Call) if isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id==owner and n.func.attr==method)
old_spawn=call(old_ast,'subprocess','Popen');new_spawn=call(new_ast,'owner','spawn')
launch_checks=dict(
    worker_argv_ast_equal=dumped(assigned(old_ast,'cmd'))==dumped(assigned(new_ast,'cmd')),
    worker_arguments_keywords_equal=[dumped(x) for x in old_spawn.args+old_spawn.keywords]==[dumped(x) for x in new_spawn.args+new_spawn.keywords],
    config_loader_assignment_equal=dumped(assigned(old_ast,'cfg'))==dumped(assigned(new_ast,'cfg')),
    worker_file_byte_equal=blob('scripts/steering_worker.py')==(ROOT/'scripts/steering_worker.py').read_bytes(),
    config_environment_helper_byte_equal=blob('scripts/steering_runtime.py')==(ROOT/'scripts/steering_runtime.py').read_bytes(),
    codex_runtime_helper_byte_equal=blob('scripts/codex_only_runtime.py')==(ROOT/'scripts/codex_only_runtime.py').read_bytes())
assert all(launch_checks.values())

validation=json.loads((CHECKS/'post-cohort-fixes/validation.json').read_text())
patch_checks=[dict(path=f['path'], expected_sha256=f['candidate_sha256'], actual_sha256=digest((ROOT/f['path']).read_bytes())) for f in validation['files']]
assert all(r['expected_sha256']==r['actual_sha256'] for r in patch_checks)
seal=json.loads((CHECKS/'three-mode-final-seal.json').read_text())
seal_checks={p:digest((CHECKS.parent/p).read_bytes())==h for p,h in seal['files_sha256'].items()}
assert all(seal_checks.values())

# Refuse expensive or external work before importing either launcher. Both use
# the verified identical runtime helper and the same actual repository root.
blocked=[]
def guard(event,args):
    if event in ('subprocess.Popen','socket.connect','socket.connect_ex','os.system'):
        blocked.append(event);raise RuntimeError('Forbidden review operation: '+event)
    if event=='import' and args[0].split('.')[0] in ('torch','mujoco','robosuite','openai'):
        blocked.append(args[0]);raise RuntimeError('Forbidden review import: '+args[0])
sys.addaudithook(guard)
sys.dont_write_bytecode=True
modules=[]
for label,source in [('frozen',frozen_source),('applied',current_source)]:
    module=types.ModuleType('review_'+label)
    module.__file__=str(ROOT/'scripts/run_steering.py')
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    modules.append(module)
config_checks=[]
with tempfile.TemporaryDirectory(prefix='applied-parity-',dir=CHECKS) as temporary:
    temp=Path(temporary)
    local={key:str(temp/'assets'/key) for key in ('rdt_checkpoint','text_encoder','vision_encoder','libero_root','libero_config','torch_home')}
    for directory in local.values():Path(directory).mkdir(parents=True)
    local.update(gpu=0,egl_device_id=2)
    local_path=temp/'local.yaml';local_path.write_text(yaml.safe_dump(local))
    for method in ('vls','eds','eds_qd'):
        outputs=[]
        for module in modules:
            capture=io.StringIO()
            args=types.SimpleNamespace(local_config=str(local_path),output_dir=str(temp/'unused-run'),tasks=None,method=method,print_config=True)
            with redirect_stdout(capture): assert module.run(args)==0
            outputs.append(capture.getvalue())
        assert outputs[0]==outputs[1]
        assert not (temp/'unused-run').exists()
        config_checks.append(dict(method=method,print_config_bytes_equal=True,output_directory_created=False))
assert not blocked
report=dict(schema='steering_final_applied_readonly_review_v1',frozen_online_commit=BASE,
    reviewed_tree='Applied working tree, before final release/merge commit',
    scientific_files=scientific,launch_checks=launch_checks,print_config_checks=config_checks,
    applied_patch_files=patch_checks,sealed_artifacts_unchanged=seal_checks,
    forbidden_operations_attempted=blocked,worker_model_gpu_provider_executed=False,
    full_cpu_suite='Owned and reported separately by root; not rerun by this review',
    findings=[],verdict='no_blocking_findings',
    limitations=['Static scientific parity plus actual print-config resolution, not a new online cohort.',
      'New worker session changes process lifetime/terminal isolation only; existing owned-process tests cover cancellation.',
      'Original online evidence remains bound to frozen commit; release/checker commit must be recorded separately.'])
(CHECKS/'final-applied-review.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(scientific_files=len(scientific),scientific_byte_changes=[x['path'] for x in scientific if not x['byte_equal']],
    launch_checks=launch_checks,print_config_checks=config_checks,patch_files=len(patch_checks),sealed_files=len(seal_checks),verdict=report['verdict']),indent=2))
