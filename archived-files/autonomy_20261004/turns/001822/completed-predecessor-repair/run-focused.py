import ast, hashlib, json, os, subprocess, time
from pathlib import Path
root = Path.cwd()
out = Path(__file__).parent
source = root / 'tests/test_n36_engineering_r1.py'
tree = ast.parse(source.read_text())
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and
    (n.name.startswith(('test_recovery_cpu_', 'test_recovery_multi_cpu_',
                       'test_recovery_terminal_cpu_', 'test_recovery_prospective_cpu_'))
     or n.name in ('recovery_cpu', 'recovery_multi_cpu', 'recovery_terminal_cpu', 'repin_terminal_partition'))]
header = 'import copy, hashlib, json\nfrom pathlib import Path\nimport pytest\nRECOVERY_CPU_SOURCE = ' + repr(str(root / 'scripts/qd_ed_n36_engineering_r1.py')) + '\n'
target = out / 'test_recovery_isolated.py'
target.write_text(header + ast.unparse(ast.Module(body=nodes, type_ignores=[])) + '\n')
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
    PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
cmd = ['/home/hynx/miniconda3/envs/vla-pilot/bin/python', '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', str(target), '--basetemp=' + str(out / 'pytest-focused-1')]
start = time.time()
with (out / 'test-focused-1.log').open('w') as log:
    result = subprocess.run(cmd, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
record = dict(command=cmd, cwd=str(root), exit_code=result.returncode, elapsed_seconds=time.time()-start,
    isolation='AST-selected existing CPU fixture/test bodies; production recovery, lifecycle and budget bodies; no production imports or owner journal reads',
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), selected_functions=[n.name for n in nodes])
(out / 'run-focused-1.json').write_text(json.dumps(record, indent=2) + '\n')
print((out / 'test-focused-1.log').read_text())
raise SystemExit(result.returncode)
