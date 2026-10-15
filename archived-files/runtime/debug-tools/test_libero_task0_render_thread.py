"""CPU-only ownership, ordered calls, failure cleanup, and frozen-operation checks."""
import ast
import gc
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import threading
import numpy as np
import pytest

DIRECTORY = Path(__file__).parent
spec = importlib.util.spec_from_file_location('render_thread_child', DIRECTORY / 'libero-task0-render-thread.py')
child = importlib.util.module_from_spec(spec)
spec.loader.exec_module(child)


def setup(fail_render=False, limit=32):
    events, operations, destructions = [], [], []
    def emit(record):
        events.append({'thread_id': threading.get_ident(), 'native_thread_id': threading.get_native_id(), **record})
        child.validate_frame(record)
    def native(name):
        def original(*args, **kwargs):
            operations.append((name, threading.get_ident()))
        return original
    mujoco = SimpleNamespace(**{name: native(name) for name in ('mj_step', 'mj_step1', 'mj_step2', 'mj_forward')})
    class Context:
        def __init__(self, sim):
            self.sim = sim
            self.con = SimpleNamespace(offWidth=640, offHeight=480)
        def __del__(self):
            destructions.append(('context', threading.get_ident()))
    class Sim:
        def __init__(self):
            self.data = SimpleNamespace(time=0.0)
            self._render_context_offscreen = Context(self)
            self.model = SimpleNamespace(vis=SimpleNamespace(global_=SimpleNamespace(offwidth=640, offheight=480)))
            self.calls = 0
        def step(self):
            operations.append(('sim.step', threading.get_ident()))
        def render(self, *, camera_name, width, height, depth=False):
            self.calls += 1
            operations.append(('render', threading.get_ident()))
            if fail_render and self.calls == 8:
                raise ValueError('CPU render failure')
            image = np.arange(width * height * 3, dtype=np.uint8).reshape(height, width, 3)
            return (image, np.ones((height, width), dtype=np.float32)) if depth else image
        def __del__(self):
            destructions.append(('sim', threading.get_ident()))
    guard = child.RenderModelGuard(emit, limit)
    guard.install(mujoco, Sim)
    init_row = object()
    def observations(sim):
        for camera in ('agentview', 'robot0_eye_in_hand'):
            sim.render(camera_name=camera, width=128, height=128, depth=True)
    class Env:
        def __init__(self):
            operations.append(('construct', threading.get_ident()))
            self.cycle = self
            self.sim = Sim()
            self.env = SimpleNamespace(model=SimpleNamespace(get_xml=lambda: 'CPU scene'))
            mujoco.mj_step1(None, self.sim.data)
            mujoco.mj_forward(None, self.sim.data)
            observations(self.sim)
        def set_init_state(self, row):
            assert row is init_row
            operations.append(('set_init', threading.get_ident()))
            mujoco.mj_forward(None, self.sim.data)
            observations(self.sim)
        def close(self):
            operations.append(('close', threading.get_ident()))
            self.sim = None
        def __del__(self):
            destructions.append(('env', threading.get_ident()))
    return guard, emit, events, operations, destructions, Env, init_row, mujoco


def test_order_same_thread_lifecycle_one_main_model_load_and_prediction():
    main = threading.get_ident()
    original_gc = gc.isenabled()
    guard, emit, events, operations, destructions, factory, init_row, _ = setup()
    policy = object()
    def load():
        assert threading.get_ident() == main and guard.renders == 7 and not gc.isenabled()
        operations.append(('load', main))
        return policy
    def predict(value):
        assert value is policy and threading.get_ident() == main and guard.renders == 10
        operations.append(('predict', main))
        return {'mock_prediction': True}
    try:
        evidence = child.workflow(factory, init_row, guard, emit, load, predict)
        owner = evidence['render_thread_id']
        assert evidence['main_thread_id'] == main and owner != main
        assert guard.renders == 13 and guard.blocked_integrations == 0
        assert evidence['cleanup_success'] and evidence['render_thread_joined']
        assert evidence['scene_references_released'] == dict(environment=True, sim=True, render_context=True)
        assert evidence['worker_cleanup_gc_calls'] == 1
        assert len(evidence['scene_release_records']) == 3
        assert all(row['thread_id'] == owner for row in evidence['scene_release_records'])
        assert sorted(destructions) == sorted((label, owner) for label in ('env', 'sim', 'context'))
        assert all(tid == (main if name in {'load', 'predict'} else owner) for name, tid in operations)
        assert [name for name, _ in operations].count('load') == [name for name, _ in operations].count('predict') == 1
        phases = [(e['phase'], e['thread_id']) for e in events if e['event'] == 'phase_enter']
        assert phases == [('construct', owner), ('set_init_state', owner), ('before_model_load', owner),
            ('load_model', main), ('after_model_load', owner), ('predict_b1', main),
            ('after_prediction_sync', owner), ('close', owner), ('final_scene_release', owner)]
        assert [e['boundary'] for e in events if e['event'] == 'gpu_library_maps'] == [
            'before_model_load', 'after_model_load', 'after_prediction_sync']
        assert gc.isenabled() is original_gc
    finally:
        guard.restore()


@pytest.mark.parametrize('failure', ['model', 'render'])
def test_exception_cleanup_and_native_cycle_destruction_stay_on_worker(failure):
    main = threading.get_ident()
    original_gc = gc.isenabled()
    guard, emit, events, operations, destructions, factory, init_row, _ = setup(fail_render=failure == 'render')
    original_error = RuntimeError('original model error')
    def load():
        assert threading.get_ident() == main
        if failure == 'model':
            raise original_error
        return object()
    try:
        with pytest.raises(RuntimeError) as caught:
            child.workflow(factory, init_row, guard, emit, load, lambda _: pytest.fail('no prediction after failure'))
        if failure == 'model':
            assert caught.value is original_error
        else:
            assert isinstance(caught.value, child.RenderThreadFailure)
            assert caught.value.__cause__ is None and caught.value.__context__ is None
            assert 'ValueError' in str(caught.value)
        stopped, = [e for e in events if e['event'] == 'render_thread_stopped']
        owner = stopped['render_thread_id']
        assert owner != main and stopped['cleanup_success']
        assert all(stopped['scene_references_released'].values())
        assert sorted(destructions) == sorted((label, owner) for label in ('env', 'sim', 'context'))
        assert operations[-1] == ('close', owner)
        assert gc.isenabled() is original_gc
    finally:
        guard.restore()


def test_original_model_ast_and_integration_render_limits_and_filtered_maps(monkeypatch):
    before = ast.parse((DIRECTORY / 'libero-task0-render-model.py').read_text())
    after = ast.parse((DIRECTORY / 'libero-task0-render-thread.py').read_text())
    for name in ('load_policy', 'predict_once', 'factory', 'validate_compute'):
        left = next(node for node in ast.walk(before) if isinstance(node, ast.FunctionDef) and node.name == name)
        right = next(node for node in ast.walk(after) if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(left) == ast.dump(right)
    assert sum(isinstance(node, ast.Call) and ast.unparse(node.func) == 'torch.cuda.synchronize'
               for node in ast.walk(after)) == 1
    assert not any(isinstance(node, ast.Call) and ast.unparse(node.func) == 'torch.cuda.init' for node in ast.walk(after))
    guard, emit, events, operations, destructions, factory, init_row, mujoco = setup(limit=7)
    def load():
        for forbidden in (mujoco.mj_step, mujoco.mj_step2, guard.forbid_integration):
            with pytest.raises(child.static.ScopeViolation, match='outside diagnostic scope'):
                forbidden(None, None)
        return object()
    try:
        with pytest.raises(child.RenderThreadFailure, match='ScopeViolation'):
            child.workflow(factory, init_row, guard, emit, load, lambda _: pytest.fail('no prediction'))
        assert guard.renders == 7 and guard.blocked_integrations == 3
        assert not any(name in {'mj_step', 'mj_step2', 'sim.step'} for name, _ in operations)
        assert len(destructions) == 3
    finally:
        guard.restore()
    monkeypatch.setattr(Path, 'read_text', lambda _: '0-1 r-xp 0 00:00 0 /usr/lib/libcuda.so.1\n'
        '1-2 r-xp 0 00:00 0 /usr/lib/libEGL_nvidia.so.0\n'
        '2-3 rw-p 0 00:00 0 /private/credentials.json\n'
        '3-4 rw-p 0 00:00 0 [heap]\n')
    assert child.filtered_gpu_library_maps() == ['/usr/lib/libEGL_nvidia.so.0', '/usr/lib/libcuda.so.1']
