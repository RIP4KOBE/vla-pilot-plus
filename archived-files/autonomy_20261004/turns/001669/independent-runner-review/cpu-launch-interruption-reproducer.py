"""CPU-only constructor interruption reproducer; no project entrypoint imported."""
import ast
import json
from pathlib import Path
import subprocess
import sys

handles = []
class InterruptedPopen(subprocess.Popen):
    def _execute_child(self, *args, **kwargs):
        super()._execute_child(*args, **kwargs)
        handles.append(self)  # Test-only ownership retained for guaranteed cleanup.
        raise KeyboardInterrupt("SYNTHETIC interruption after OS spawn")

process = None
error = None
try:
    process = InterruptedPopen([sys.executable, '-I', '-S', '-B', '-c', 'import time; time.sleep(30)'],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except BaseException as exc:
    error = type(exc).__name__
try:
    child_alive = handles[0].poll() is None
    source = Path(sys.argv[1]).read_text()
    module = ast.parse(source)
    runner = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'execute_preparation')
    owner_lock = next(n for n in runner.body if isinstance(n, ast.With))
    check = next(n for n in owner_lock.body if isinstance(n, ast.If) and n.lineno == 680)
    # Evaluate only the actual guard expression, never the measurement function.
    keeps_unknown = eval(compile(ast.Expression(check.test), '<reviewed-unknown-guard>', 'eval'),
                         {'process': process, 'identity': None})
    assert process is None and child_alive and keeps_unknown is False
    print(json.dumps({'synthetic_cpu_only': True, 'measurement_entrypoint_executed': False,
        'constructor_error': error, 'returned_handle_is_none': process is None,
        'actual_child_alive': child_alive, 'line_680_unknown_guard_fires': keeps_unknown,
        'source_trace': 'No provider files exist before child admission; process-is-not-None quiescence branch also skipped; lines 706-717 select aborted settlement.',
        'limitation': 'Reproduces Popen boundary plus exact guard expression; does not execute runner or owning accounting.'}, sort_keys=True))
finally:
    for child in handles:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)
