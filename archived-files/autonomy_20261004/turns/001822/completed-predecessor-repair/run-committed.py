import json, os, subprocess, time
from pathlib import Path
out = Path(__file__).parent
root = Path.cwd()
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
    PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
cmd = ['/home/hynx/miniconda3/envs/vla-pilot/bin/python', '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
       'tests/test_n36_engineering_r1.py::test_recovery_terminal_cpu_partition_and_budget',
       'tests/test_n36_engineering_r1.py::test_parent_source_and_shared_safety_predicates_unchanged',
       'tests/test_n36_readiness_prepare.py::test_preparation_source_scope_requires_exact_prospective_admission',
       '--basetemp=' + str(out / 'pytest-committed-1')]
start = time.time()
with (out / 'test-committed-1.log').open('w') as log:
    result = subprocess.run(cmd, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
(out / 'run-committed-1.json').write_text(json.dumps(dict(command=cmd, cwd=str(root),
    exit_code=result.returncode, elapsed_seconds=time.time()-start), indent=2) + '\n')
print((out / 'test-committed-1.log').read_text())
raise SystemExit(result.returncode)
