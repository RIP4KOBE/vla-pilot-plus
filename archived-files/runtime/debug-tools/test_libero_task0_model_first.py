"""CPU-only model-order/context/RNG mocks; no Torch, model or simulator imports."""
import ast
import importlib.util
from pathlib import Path
import random
from types import SimpleNamespace
import numpy as np
import pytest

DIRECTORY = Path(__file__).parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

child = load('model_first_child', 'libero-task0-model-first.py')
fixtures = load('model_first_cpu_fixtures', 'test_libero_task0_render_model.py')


def rng_modules():
    py = random.Random(12)
    np_module = SimpleNamespace(random=np.random.RandomState(12))
    torch_state = {'value': 12}
    torch_module = SimpleNamespace(get_rng_state=lambda: torch_state['value'],
        set_rng_state=lambda value: torch_state.update(value=value))
    return py, np_module, torch_module, torch_state


def assert_numpy_state_equal(left, right):
    assert left[0] == right[0] and left[2:] == right[2:]
    np.testing.assert_array_equal(left[1], right[1])


def test_complete_model_before_context_and_scene_cpu_rng_restore_before_one_prediction():
    guard, emit, events, operations, destructions_factory, init_row, _ = fixtures.setup()
    py, npm, tm, ts = rng_modules()
    initialized, policy, snapshots = [False], object(), {}
    class Context:
        def __init__(self, marker, *, device_id):
            assert marker is policy and device_id == -1
            operations.append('original_context')
    original = Context.__init__
    observer = child.ModelFirstContextObserver(lambda: initialized[0], emit)
    observer.install(Context)
    def load_policy():
        assert guard.renders == 0 and not observer.context_creation_records
        py.seed(193735)
        npm.random.seed(193735)
        ts['value'] = 99
        snapshots.update(python=py.getstate(), numpy=npm.random.get_state(), torch=ts['value'])
        initialized[0] = True
        operations.append('load')
        return policy
    def factory():
        assert observer.model_loaded and initialized[0]
        assert npm.random.randint(0, 1000000) == np.random.RandomState(1969522881).randint(0, 1000000)
        py.random()
        ts['value'] += 10
        Context(policy, device_id=-1)
        return destructions_factory()
    def predict(value):
        assert value is policy and guard.renders == 7
        assert py.getstate() == snapshots['python'] and ts['value'] == snapshots['torch']
        assert_numpy_state_equal(npm.random.get_state(), snapshots['numpy'])
        operations.append('predict')
        return {'prediction': 'CPU mock'}
    try:
        proof = child.workflow(factory, init_row, guard, emit, load_policy, predict, observer,
            lambda: child.isolated_scene_cpu_rng(py, npm, tm, emit))
        assert guard.renders == 10 and proof['explicit_render_calls'] == 6
        assert proof['cpu_rng_restored_after_scene_init'] and proof['model_loaded_before_scene']
        assert proof['context_creation_records'] == [dict(index=1, model_loaded_before=True, cuda_initialized_before=True, completed=True)]
        assert guard.blocked_integrations == 0 and guard.step1 == 1 and guard.forwards == 2
        assert [e['phase'] for e in events if e['event'] == 'phase_enter'] == ['load_model', 'construct',
            'set_init_state', 'after_model_load_scene_init', 'predict_b1', 'after_prediction_sync', 'close']
        assert operations.index('load') < operations.index('original_context') < operations.index('predict')
        assert operations.count('load') == operations.count('predict') == 1
    finally:
        observer.restore()
        guard.restore()
    assert Context.__init__ is original


def test_rng_and_owned_constructor_restored_after_original_exception_and_early_context_rejected():
    py, npm, tm, ts = rng_modules()
    states = py.getstate(), npm.random.get_state(), ts['value']
    events, calls = [], []
    error = ValueError('original constructor CPU failure')
    class Context:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise error
    original = Context.__init__
    observer = child.ModelFirstContextObserver(lambda: True, events.append)
    observer.install(Context)
    try:
        with pytest.raises(child.static.ScopeViolation if hasattr(child, 'static') else RuntimeError):
            Context('must not reach original')
        assert not calls
        observer.model_loaded = True
        with pytest.raises(ValueError) as caught:
            with child.isolated_scene_cpu_rng(py, npm, tm, events.append):
                py.random()
                npm.random.random()
                ts['value'] = 100
                Context('exact argument', device_id=-1)
        assert caught.value is error and calls == [(('exact argument',), {'device_id': -1})]
        assert py.getstate() == states[0] and ts['value'] == states[2]
        assert_numpy_state_equal(npm.random.get_state(), states[1])
        assert events[-1]['event'] == 'scene_cpu_rng_restored'
    finally:
        observer.restore()
    assert Context.__init__ is original


def test_original_model_factory_ast_no_extra_cuda_operations_and_integration_guard():
    before = ast.parse((DIRECTORY / 'libero-task0-render-model.py').read_text())
    after = ast.parse((DIRECTORY / 'libero-task0-model-first.py').read_text())
    for name in ('load_policy', 'predict_once', 'factory', 'validate_compute'):
        a = next(node for node in ast.walk(before) if isinstance(node, ast.FunctionDef) and node.name == name)
        b = next(node for node in ast.walk(after) if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(a) == ast.dump(b)
    cuda_calls = lambda tree: [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and ast.unparse(n.func).startswith('torch.cuda.')]
    assert cuda_calls(before) == cuda_calls(after)
    guard, emit, events, operations, factory, init_row, mujoco = fixtures.setup()
    py, npm, tm, _ = rng_modules()
    observer = child.ModelFirstContextObserver(lambda: True, emit)
    def forbidden_factory():
        mujoco.mj_step(None, None)
        pytest.fail('must reject integration first')
    try:
        with pytest.raises(RuntimeError, match='outside diagnostic scope'):
            child.workflow(forbidden_factory, init_row, guard, emit, object,
                lambda _: pytest.fail('no prediction'), observer,
                lambda: child.isolated_scene_cpu_rng(py, npm, tm, emit))
        assert guard.blocked_integrations == 1 and guard.renders == 0 and 'mj_step' not in operations
        assert any(e['event'] == 'scene_cpu_rng_restored' for e in events)
    finally:
        guard.restore()
