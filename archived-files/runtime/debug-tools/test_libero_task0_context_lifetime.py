"""CPU-only natural-destructor / EGL-call mocks and frozen algorithm checks."""
import ast
import importlib.util
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import numpy as np
import pytest

DIRECTORY = Path(__file__).parent
spec = importlib.util.spec_from_file_location('context_lifetime_child', DIRECTORY / 'libero-task0-context-lifetime.py')
child = importlib.util.module_from_spec(spec)
spec.loader.exec_module(child)


def setup(mode=None):
    events, calls = [], []
    def emit(record):
        events.append(record)
        child.validate_frame(record)
    def native(model, data, *args, **kwargs):
        calls.append('native_forward')
    mujoco = SimpleNamespace(mj_step=lambda *a: pytest.fail('native integration'),
        mj_step2=lambda *a: pytest.fail('native integration'), mj_step1=lambda *a: None, mj_forward=native)
    serial = [0]
    def destroy(display, handle):
        calls.append(('eglDestroyContext', display, handle.address))
        return not (mode == 'destroy_false' and handle.address == 1)
    api = SimpleNamespace(eglDestroyContext=destroy)
    class GL:
        def __init__(self, index):
            self._context = SimpleNamespace(address=index)
        def free(self):
            if self._context:
                try:
                    api.eglDestroyContext('original_display', self._context)
                except Exception:
                    pass
            self._context = None
        def __del__(self):
            self.free()
    class Con:
        def __init__(self, sim, index):
            self.index = index
            self.offWidth = sim.model.vis.global_.offwidth
            self.offHeight = sim.model.vis.global_.offheight
        def free(self):
            calls.append(('con.free', self.index))
            if mode == 'con_exception' and self.index == 1:
                raise RuntimeError('native con.free CPU exception')
    class BaseContext:
        def __init__(self, sim, offscreen=True, device_id=-1, max_width=640, max_height=480):
            serial[0] += 1
            self.index = serial[0]
            self.sim, self.offscreen, self.device_id = sim, offscreen, device_id
            self.gl_ctx = GL(self.index)
            sim.forward()
            sim._render_context_offscreen = self
            self.con = Con(sim, self.index)
            self.cam, self.vopt, self.pert, self.scn = object(), object(), object(), object()
            calls.append(('constructor', self.index, device_id, max_width, max_height))
            if mode == 'state_drift' and self.index == 2:
                sim.data.qpos[0] += 1
        def __del__(self):
            calls.append(('context.__del__', self.index))
            self.con.free()
            self.gl_ctx.free()
            del self.con, self.gl_ctx, self.scn, self.cam, self.vopt, self.pert
    class Context(BaseContext):
        def __init__(self, sim, device_id, max_width=640, max_height=480):
            super().__init__(sim, offscreen=True, device_id=device_id, max_width=max_width, max_height=max_height)
    class Sim:
        def __init__(self):
            self.data = SimpleNamespace(time=0.0, qpos=np.arange(7, dtype=float), qvel=np.zeros(7), act=np.zeros(0), ctrl=np.zeros(7))
            self.model = SimpleNamespace(vis=SimpleNamespace(global_=SimpleNamespace(offwidth=640, offheight=480)))
            self._render_context_offscreen = None
        def forward(self):
            mujoco.mj_forward(None, self.data)
        def step(self):
            pytest.fail('original integration')
        def render(self, *, camera_name, width, height, depth=False):
            ctx = self._render_context_offscreen
            assert ctx is not None
            ctx.con.offWidth = self.model.vis.global_.offwidth = max(width, self.model.vis.global_.offwidth)
            ctx.con.offHeight = self.model.vis.global_.offheight = max(height, self.model.vis.global_.offheight)
            rgb = np.arange(width * height * 3, dtype=np.uint8).reshape(height, width, 3)
            return (rgb, np.ones((height, width), dtype=np.float32)) if depth else rgb
    guard = child.RenderModelGuard(emit, 32)
    guard.install(mujoco, Sim)
    observer = child.ModelFirstContextObserver(lambda: True, emit)
    observer.install(BaseContext)
    lifetime = child.ContextLifetime(Context, api, observer, emit)
    lifetime.install()
    def obs(sim):
        for camera in ('agentview', 'robot0_eye_in_hand'):
            sim.render(camera_name=camera, width=128, height=128, depth=True)
    init_row = object()
    class Env:
        def __init__(self):
            self.sim = Sim()
            self.env = SimpleNamespace(model=SimpleNamespace(get_xml=lambda: 'CPU scene'))
            mujoco.mj_step1(None, self.sim.data)
            Context(self.sim, device_id=-1)
            for _ in range(3):
                self.sim.forward()
            obs(self.sim)
        def set_init_state(self, value):
            assert value is init_row
            self.sim.forward()
            obs(self.sim)
        def close(self):
            self.sim._render_context_offscreen = None
            calls.append('close')
    return guard, observer, lifetime, emit, events, calls, Env, init_row, mujoco


def scene_rng(emit):
    py = random.Random(12)
    npm = SimpleNamespace(random=np.random.RandomState(12))
    cpu_state = [12]
    tm = SimpleNamespace(get_rng_state=lambda: cpu_state[0], set_rng_state=lambda value: cpu_state.__setitem__(0, value))
    return lambda: child.isolated_scene_cpu_rng(py, npm, tm, emit)


def test_natural_old_context_destruction_before_one_prediction_and_exact_reconstruction():
    guard, observer, lifetime, emit, events, calls, factory, init_row, _ = setup()
    policy = object()
    def load():
        calls.append('load')
        return policy
    def predict(value):
        assert value is policy and guard.renders == 7
        assert observer.context_refs[0][0]() is None
        assert calls.count(('context.__del__', 1)) == calls.count(('con.free', 1)) == 1
        assert calls.count(('eglDestroyContext', 'original_display', 1)) == 1
        calls.append('predict')
        return {'prediction': 'CPU mock'}
    try:
        evidence = child.workflow(factory, init_row, guard, emit, load, predict, observer, scene_rng(emit), lifetime)
        assert guard.renders == 10 and guard.forwards == 6 and guard.blocked_integrations == 0
        assert evidence['context_release_calls'] == evidence['context_rebuild_calls'] == 1
        assert evidence['context_rebuild_mj_forward_calls'] == 1
        assert evidence['owned_egl_destroy_records'] == [dict(returned_success=True, exception_type=None)]
        assert evidence['release_unraisable_exceptions'] == [] and evidence['global_egl_display_released'] is False
        assert evidence['physical_state_sha256_before_release'] == evidence['physical_state_sha256_after_release'] == evidence['physical_state_sha256_after_rebuild']
        assert evidence['display_option_objects_preserved'] and all(ref() is None for ref, _ in observer.context_refs)
        assert [entry for entry in calls if isinstance(entry, tuple) and entry[0] == 'constructor'] == [
            ('constructor', 1, -1, 640, 480), ('constructor', 2, -1, 640, 480)]
        assert calls.index(('context.__del__', 1)) < calls.index('predict') < calls.index(('constructor', 2, -1, 640, 480))
        assert calls.count(('context.__del__', 2)) == calls.count(('eglDestroyContext', 'original_display', 2)) == 1
    finally:
        lifetime.restore()
        observer.restore()
        guard.restore()


@pytest.mark.parametrize('mode', ['destroy_false', 'con_exception', 'state_drift', 'shared_reference'])
def test_release_or_rebuild_failure_stops_and_restores_observers(mode):
    guard, observer, lifetime, emit, events, calls, factory, init_row, _ = setup(mode)
    held = []
    forwarded = []
    actual_hook = sys.unraisablehook
    sys.unraisablehook = lambda event: forwarded.append(event.exc_type.__name__)
    forwarding_hook = sys.unraisablehook
    original_destroy = lifetime._original_destroy
    if mode == 'shared_reference':
        def factory_with_reference():
            env = factory()
            held.append(env.sim._render_context_offscreen)
            return env
        selected_factory = factory_with_reference
    else:
        selected_factory = factory
    def predict(_value):
        if mode != 'state_drift':
            pytest.fail('prediction must not follow incomplete release')
        calls.append('predict')
        return {}
    try:
        with pytest.raises(RuntimeError):
            child.workflow(selected_factory, init_row, guard, emit, object, predict, observer, scene_rng(emit), lifetime)
        assert guard.renders == 7 and sys.unraisablehook is forwarding_hook
        if mode == 'con_exception':
            assert forwarded == ['RuntimeError']
            assert lifetime.unraisable_records == [dict(exception_type='RuntimeError')]
        if mode != 'state_drift':
            assert 'predict' not in calls and lifetime.rebuild_calls == 0
    finally:
        held.clear()
        lifetime.restore()
        observer.restore()
        guard.restore()
        sys.unraisablehook = actual_hook
    assert lifetime.egl_api.eglDestroyContext is original_destroy


def test_frozen_model_rng_factory_ast_no_manual_destructor_or_extra_cuda_calls():
    before = ast.parse((DIRECTORY / 'libero-task0-model-first.py').read_text())
    after = ast.parse((DIRECTORY / 'libero-task0-context-lifetime.py').read_text())
    for name in ('load_policy', 'predict_once', 'factory', 'isolated_scene_cpu_rng', 'validate_compute'):
        a = next(node for node in ast.walk(before) if isinstance(node, ast.FunctionDef) and node.name == name)
        b = next(node for node in ast.walk(after) if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(a) == ast.dump(b)
    cuda_calls = lambda tree: [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and ast.unparse(n.func).startswith('torch.cuda.')]
    assert cuda_calls(before) == cuda_calls(after)
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
                   node.func.attr in {'__del__', 'free', 'eglDestroyContext', 'make_current'} for node in ast.walk(after))
