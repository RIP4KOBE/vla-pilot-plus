"""Reproducible node15.6 CPU-only AST-isolated checks; synthetic fixtures only."""
import ast
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

OUT = Path(__file__).resolve().parent
AUTHORITY = json.loads((OUT / 'authority-v1.json').read_text())
ROOT = Path(AUTHORITY['worktree'])
BASE = '1c10f9dd2afed8f8301e61f42dde46b8fa9565ed'
SOURCE = ROOT / 'scripts/qd_ed_n36_engineering_r1.py'
TESTS = ROOT / 'tests/test_n36_engineering_r1.py'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def guard():
    assert all(not Path(p).exists() for p in AUTHORITY['stop_authority']['paths']), 'STOP present'
    assert dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(AUTHORITY['deadline'].replace('Z', '+00:00')), 'deadline'

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()

guard()
started = dt.datetime.now(dt.timezone.utc).isoformat()
before = git('show', BASE + ':scripts/qd_ed_n36_engineering_r1.py')
old_tree, new_tree = ast.parse(before), ast.parse(SOURCE.read_text())
funcs = lambda tree: {n.name: ast.dump(n, include_attributes=False) for n in tree.body if isinstance(n, ast.FunctionDef)}
old, new = funcs(old_tree), funcs(new_tree)
added = {'_recovery_json','_recovery_rows','_recovery_read','_recovery_contract','_recovery_capture','_recovery_partition'}
assert set(new) - set(old) == added and not set(old) - set(new)
changed = sorted(name for name in old if old[name] != new[name])
assert changed == ['preparation_health_suffix', 'specification'], changed
old_nodes={n.name:n for n in old_tree.body if isinstance(n,ast.FunctionDef)}
new_nodes={n.name:n for n in new_tree.body if isinstance(n,ast.FunctionDef)}
def strict_tail(node):
    start=next(i for i,n in enumerate(node.body) if isinstance(n,ast.If) and ast.unparse(n.test)=='not prep')
    return [ast.dump(n,include_attributes=False) for n in node.body[start:]]
assert strict_tail(old_nodes['preparation_health_suffix']) == strict_tail(new_nodes['preparation_health_suffix'])
def constants(tree):
    return {n.targets[0].id:ast.dump(n.value,include_attributes=False) for n in tree.body
            if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
old_consts,new_consts=constants(old_tree),constants(new_tree)
assert set(old_consts)==set(new_consts)
assert [k for k in old_consts if old_consts[k]!=new_consts[k]]==['SPECIFICATION']
assert all(ast.dump(n,include_attributes=False) in [ast.dump(v,include_attributes=False) for v in new_tree.body]
           for n in old_tree.body if isinstance(n,(ast.Import,ast.ImportFrom)))
# Syntax compilation never executes/imports the production module.
compile(new_tree,str(SOURCE),'exec')
compile(ast.parse(TESTS.read_text()),str(TESTS),'exec')
changed_files=git('diff','--name-only',BASE,'--').splitlines()
assert set(changed_files)=={'scripts/qd_ed_n36_engineering_r1.py','tests/test_n36_engineering_r1.py'}
for key in ('specification','contract','root_semantic_review'):
    ref=AUTHORITY[key]
    assert sha(Path(ref['path']).read_bytes())==ref['sha256'],key
spec=json.loads(Path(AUTHORITY['specification']['path']).read_bytes())
assert set(changed_files)<=set(spec['runtime_binding']['source_change_allowlist'])
pin=next(ast.literal_eval(n.value) for n in new_tree.body if isinstance(n,ast.Assign)
         and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='SPECIFICATION')
assert pin==AUTHORITY['specification']
assert spec['recovery_prefix_contract']==AUTHORITY['contract']
selected=[n for n in ast.parse(TESTS.read_text()).body if isinstance(n,ast.FunctionDef)
          and (n.name=='recovery_cpu' or n.name.startswith('test_recovery_cpu_'))]
header = """import copy, hashlib, json, sys
from pathlib import Path
import pytest
class BlockProductionImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'scripts','torch','tensorflow','jax','numpy','cv2','PIL','mujoco','transformers','openai','anthropic','poe','libero'}:
            raise AssertionError('Forbidden production/native/model/provider import: '+fullname)
sys.meta_path.insert(0, BlockProductionImports())
"""
text=header+'RECOVERY_CPU_SOURCE = '+repr(str(SOURCE))+'\n'+ast.unparse(ast.Module(body=selected,type_ignores=[]))+'\n'
with tempfile.TemporaryDirectory(prefix='node156-synthetic-cpu-') as temporary:
    test_path=Path(temporary)/'test_recovery_cpu.py'
    test_path.write_text(text)
    command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',str(test_path)]
    environment=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
    begin=time.monotonic()
    result=subprocess.run(command,cwd=ROOT,env=environment,text=True,capture_output=True,timeout=120)
    elapsed=time.monotonic()-begin
    (OUT/'focused-cpu-output-v1.txt').write_text(result.stdout+result.stderr)
    receipt=dict(schema='n36-recovery-prefix-focused-cpu-receipt-v1',started_at=started,
        finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),command=command,cwd=str(ROOT),
        environment_overrides={k:environment[k] for k in ('PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONDONTWRITEBYTECODE')},
        exit_code=result.returncode,elapsed_seconds=elapsed,stdout=result.stdout,stderr=result.stderr,
        generated_test_sha256=sha(text.encode()),ast_isolated=True,synthetic_fixtures_only=True,
        blocked_import_roots=['scripts','torch','tensorflow','jax','numpy','cv2','PIL','mujoco','transformers','openai','anthropic','poe','libero'],
        source_before_commit=BASE,source_head=git('rev-parse','HEAD'),
        source_sha256=sha(SOURCE.read_bytes()),test_sha256=sha(TESTS.read_bytes()),
        changed_files=changed_files,changed_existing_functions=changed,added_functions=sorted(added),
        unchanged_strict_current_lifecycle_tail=True,unchanged_all_other_existing_functions=True,
        unchanged_constants_except_specification=True,verified_authority_pins=True,
        spec_allowlist_pass=True,production_artifacts_executed=False)
    (OUT/'focused-cpu-receipt-v1.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(result.stdout,end='');print(result.stderr,end='')
    if result.returncode: raise SystemExit(result.returncode)
guard()
