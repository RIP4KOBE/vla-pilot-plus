"""Two CUDA-first CPU mocks plus the three inherited loader/guard checks."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

DIRECTORY = Path(__file__).parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

child = load('cuda_first_child', 'libero-task0-cuda-first.py')
inherited = load('inherited_loader_tests', 'test_libero_task0_model_load_phases.py')
inherited.child = child
test_loader_order = inherited.test_exact_loader_order_arguments_and_sixteen_total_camera_calls
test_loader_exception_restore = inherited.test_owned_wrappers_preserve_original_exception_arguments_and_restore
test_integration_and_render_limits = inherited.test_original_integration_guards_and_render_cap_stop_before_originals


def test_early_init_once_then_context_original_arguments_result_exception_and_restore():
    events, calls = [], []
    initialized = False
    def init():
        nonlocal initialized
        calls.append('cuda.init')
        initialized = True
    cuda = SimpleNamespace(init=init, is_initialized=lambda: initialized)
    sentinel, result = object(), object()
    error = RuntimeError('original constructor error')
    class Context:
        def __init__(self, *args, **kwargs):
            calls.append((self, args, kwargs))
            if kwargs.get('fail'):
                raise error
            return result
    original = Context.__init__
    observer = child.CudaFirstObserver(cuda, events.append)
    observer.install(Context)
    try:
        observer.early_init()
        instance = object.__new__(Context)
        assert Context.__init__(instance, sentinel, device_id=-1, max_width=640, max_height=480) is result
        with pytest.raises(RuntimeError) as caught:
            Context.__init__(instance, sentinel, fail=True)
        assert caught.value is error
        with pytest.raises(child.helper.static.ScopeViolation, match='invoked twice'):
            observer.early_init()
        assert calls == ['cuda.init', (instance, (sentinel,), dict(device_id=-1, max_width=640, max_height=480)),
                         (instance, (sentinel,), dict(fail=True))]
        assert observer.early_cuda_init_calls == 1
        assert observer.context_creation_records == [dict(index=1, is_initialized_before=True, completed=True),
                                                    dict(index=2, is_initialized_before=True, completed=False)]
        exit_event = next(row for row in events if row['event'] == 'early_cuda_init_exit')
        assert exit_event['is_initialized_before'] is False and exit_event['is_initialized_after'] is True
    finally:
        observer.restore()
    assert Context.__init__ is original


def test_context_before_cuda_refused_and_frozen_loader_operations_ast_unchanged():
    calls, events = [], []
    cuda = SimpleNamespace(init=lambda: calls.append('init'), is_initialized=lambda: False)
    class Context:
        def __init__(self, *args, **kwargs):
            calls.append('context')
    original = Context.__init__
    observer = child.CudaFirstObserver(cuda, events.append)
    observer.install(Context)
    try:
        with pytest.raises(child.helper.static.ScopeViolation, match='preceded CUDA'):
            Context('must not reach original')
        assert not calls and observer.early_cuda_init_calls == 0
    finally:
        observer.restore()
    assert Context.__init__ is original
    before = ast.parse((DIRECTORY / 'libero-task0-model-load-phases.py').read_text())
    after = ast.parse((DIRECTORY / 'libero-task0-cuda-first.py').read_text())
    for name in ('internal_hooks', 'zero_compute', 'load_in_phases', 'workflow'):
        left = next(node for node in before.body if isinstance(node, ast.FunctionDef) and node.name == name)
        right = next(node for node in after.body if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(left) == ast.dump(right)
    for name in ('factory', 'import_policy', 'cuda_identity_seed', 'verify_module', 'loader'):
        left = next(node for node in ast.walk(before) if isinstance(node, ast.FunctionDef) and node.name == name)
        right = next(node for node in ast.walk(after) if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(left) == ast.dump(right)
    init_calls = [node for node in ast.walk(after) if isinstance(node, ast.Call) and ast.unparse(node.func) == 'self.cuda.init']
    early_call, = [node for node in ast.walk(after) if isinstance(node, ast.Call) and ast.unparse(node.func) == 'cuda_observer.early_init']
    workflow_call, = [node for node in ast.walk(after) if isinstance(node, ast.Call) and ast.unparse(node.func) == 'workflow']
    assert len(init_calls) == 1 and early_call.lineno < workflow_call.lineno
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
                   node.func.attr in {'synchronize', 'make_current', '_predict_unguided'} for node in ast.walk(after))
