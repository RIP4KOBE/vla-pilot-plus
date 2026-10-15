import ast
import os
from pathlib import Path
import sys

root = Path.cwd()
out = Path('/tmp/node156-inventory-cpu')
source = root / 'tests/test_n36_engineering_r1.py'
tree = ast.parse(source.read_text())
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and (
    n.name.startswith(('recovery_', 'test_recovery_cpu_', 'test_recovery_multi_cpu_',
                       'test_recovery_terminal_cpu_', 'test_recovery_prospective_cpu_',
                       'test_inventory_admission_')) or n.name in (
    'prospective_scope_cpu', 'test_prospective_scope_actual_composition_admission',
    'repin_terminal_partition', 'inventory_admission_cpu'))]
constants = [n for n in tree.body if isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Name) and t.id == 'PROPOSED_SCOPE_SPECIFICATION' for t in n.targets)]
header = '''import copy, hashlib, json\nfrom pathlib import Path\nimport pytest\nfrom scripts import qd_ed_n36_engineering_r1 as e\nPINNED_SPECIFICATION = dict(e.SPECIFICATION)\nRECOVERY_CPU_SOURCE = %r\n''' % str(root/'scripts/qd_ed_n36_engineering_r1.py')
target = out / 'test_focused_inventory.py'
target.write_text(header + ast.unparse(ast.Module(body=constants+functions, type_ignores=[])))
sys.path.insert(0, str(root))
def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = os.fsdecode(args[0]); low = name.lower(); base = Path(low).name
        if ('2026-08-10' in low or ('poe' in base and base != 'qd_ed_poe_launch.py')
                or base in ('auth.json','credentials.json','.env') or '/.ssh/' in low
                or '/dev/nvidia' in low):
            raise PermissionError('prohibited CPU test access: ' + name)
        mode, flags = args[1:3]
        writing = (isinstance(mode,str) and any(x in mode for x in 'wax+')) or (
            isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if writing and name != '/dev/null' and not (str(Path(name).resolve()).startswith('/tmp/') or str(Path(name).resolve()) == '/tmp'):
            raise PermissionError('CPU test write outside temporary directory: ' + name)
    if event in ('socket.connect','socket.bind'):
        raise PermissionError('network prohibited')
    if event == 'subprocess.Popen':
        raise PermissionError('subprocess prohibited during focused CPU tests')
sys.addaudithook(guard)
import pytest
sys.exit(pytest.main([str(target), '-q', '-p', 'no:cacheprovider', '--basetemp', str(out/'pytest-tmp')] + sys.argv[1:]))
