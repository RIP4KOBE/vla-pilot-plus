import json, os, subprocess, time
from pathlib import Path
out = Path(__file__).parent
root = Path.cwd()
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
    PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
cmd = ['/home/hynx/miniconda3/envs/vla-pilot/bin/python', '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
       'tests/test_n36_preparation_binding.py',
       'tests/test_n36_readiness_prepare.py::test_preparation_source_scope_requires_exact_prospective_admission',
       '--basetemp=' + str(out / 'pytest-regressions-1')]
start = time.time()
with (out / 'test-regressions-1.log').open('w') as log:
    result = subprocess.run(cmd, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
(out / 'run-regressions-1.json').write_text(json.dumps(dict(command=cmd, cwd=str(root),
    exit_code=result.returncode, elapsed_seconds=time.time()-start), indent=2) + '\n')
print((out / 'test-regressions-1.log').read_text())
raise SystemExit(result.returncode)
