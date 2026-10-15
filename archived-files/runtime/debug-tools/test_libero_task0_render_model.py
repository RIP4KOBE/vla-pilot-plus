"""CPU fake workflow and guards only; no simulator, Torch, model or GPU import."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SCRIPT = Path(__file__).with_name('libero-task0-render-model.py')
spec = importlib.util.spec_from_file_location('scene_model_child', SCRIPT)
child = importlib.util.module_from_spec(spec)
spec.loader.exec_module(child)


def setup(limit=32):
    events, operations = [], []
    def emit(row):
        events.append(row)
        child.validate_frame(row)
    def native(name):
        def original(*args, **kwargs):
            operations.append(name)
        return original
    mujoco = SimpleNamespace(**{name: native(name) for name in ['mj_step', 'mj_step1', 'mj_step2', 'mj_forward']})
    class Sim:
        def __init__(self):
            self.data = SimpleNamespace(time=0.0)
            self._render_context_offscreen = SimpleNamespace(con=SimpleNamespace(offWidth=640, offHeight=480))
            self.model = SimpleNamespace(vis=SimpleNamespace(global_=SimpleNamespace(offwidth=640, offheight=480)))
        def step(self):
            operations.append('sim.step')
        def render(self, *, camera_name, width, height, depth=False):
            operations.append(('render', camera_name, width, depth))
            self._render_context_offscreen.con.offHeight = max(height, self._render_context_offscreen.con.offHeight)
            self.model.vis.global_.offheight = self._render_context_offscreen.con.offHeight
            rgb = np.arange(width * height * 3, dtype=np.uint8).reshape(height, width, 3)
            return (rgb, np.ones((height, width), dtype=np.float32)) if depth else rgb
    guard = child.RenderModelGuard(emit, limit)
    guard.install(mujoco, Sim)
    init_row = object()
    def observations(sim):
        for camera in ['agentview', 'robot0_eye_in_hand']:
            sim.render(camera_name=camera, width=128, height=128, depth=True)
    class Env:
        def __init__(self):
            self.sim = Sim()
            self.env = SimpleNamespace(model=SimpleNamespace(get_xml=lambda: 'CPU mock scene'))
            mujoco.mj_step1(None, self.sim.data)
            mujoco.mj_forward(None, self.sim.data)
            observations(self.sim)
        def set_init_state(self, row):
            assert row is init_row
            mujoco.mj_forward(None, self.sim.data)
            observations(self.sim)
        def close(self):
            operations.append('close')
    return guard, emit, events, operations, Env, init_row, mujoco


def test_three_boundaries_exact_order_one_model_load_one_prediction_and_thirteen_total_renders():
    guard, emit, events, operations, factory, init_row, _ = setup()
    policy, evidence = object(), {'prediction': 'CPU fake'}
    def load():
        assert guard.renders == 7
        operations.append('load')
        return policy
    def predict(argument):
        assert argument is policy and guard.renders == 10
        operations.extend(['predict_once', 'sync_once'])
        return evidence
    try:
        assert child.workflow(factory, init_row, guard, emit, load, predict) is evidence
        names = [event['phase'] for event in events if event['event'] == 'phase_enter']
        assert names == ['construct', 'set_init_state', 'before_model_load', 'load_model',
                         'after_model_load', 'predict_b1', 'after_prediction_sync', 'close']
        assert guard.renders == 13 and guard.blocked_integrations == 0
        assert operations.count('load') == operations.count('predict_once') == operations.count('sync_once') == 1
        for phase in ('before_model_load', 'after_model_load', 'after_prediction_sync'):
            frames = [event for event in events if event['event'] == 'render_exit' and event['phase'] == phase]
            assert [(e['camera'], e['width'], e['depth']) for e in frames] == child.CAMERAS
        buffers = [e for e in events if e['event'].startswith('render_buffer_') and e['render_index'] == 7]
        assert buffers[0]['context_offHeight'] == 480 and buffers[1]['context_offHeight'] == 640
    finally:
        guard.restore()


def test_model_phase_cannot_execute_integration_and_no_later_prediction_or_retry_occurs():
    guard, emit, events, operations, factory, init_row, mujoco = setup()
    def load():
        mujoco.mj_step(None, None)
    try:
        with pytest.raises(child.static.ScopeViolation, match='outside diagnostic scope'):
            child.workflow(factory, init_row, guard, emit, load, lambda _: pytest.fail('prediction must not occur'))
        assert 'mj_step' not in operations and guard.blocked_integrations == 1
        assert operations[-1] == 'close'
        assert not any(e.get('phase') == 'after_model_load' for e in events)
    finally:
        guard.restore()


def test_prediction_failure_is_preserved_and_scene_is_closed_without_post_prediction_render():
    guard, emit, events, operations, factory, init_row, _ = setup()
    error = RuntimeError('CPU fake original failure')
    def fail(_policy):
        raise error
    try:
        with pytest.raises(RuntimeError) as caught:
            child.workflow(factory, init_row, guard, emit, object, fail)
        assert caught.value is error and guard.renders == 10
        assert operations[-1] == 'close'
        assert not any(e.get('phase') == 'after_prediction_sync' for e in events)
    finally:
        guard.restore()


def test_total_render_cap_includes_construction_and_rejects_missing_boundary_budget():
    guard, emit, _, operations, factory, init_row, _ = setup(limit=7)
    try:
        with pytest.raises(child.static.ScopeViolation, match='insufficient total render budget'):
            child.workflow(factory, init_row, guard, emit, object, lambda _: pytest.fail('no prediction'))
        assert guard.renders == 7
        assert sum(isinstance(value, tuple) for value in operations) == 7
    finally:
        guard.restore()


def test_frame_validation_and_exact_b1_compute_guard():
    record = dict(event='render_exit', rgb_shape=[128, 128, 3], height=128, width=128,
        rgb_dtype='uint8', rgb_finite=True, rgb_nonuniform=True, depth=True, depth_finite=True)
    child.validate_frame(record)
    for key in ('rgb_finite', 'rgb_nonuniform', 'depth_finite'):
        with pytest.raises(child.static.ScopeViolation, match='rendered frame'):
            child.validate_frame({**record, key: False})
    counts = dict(model_forward_calls=5, model_batch_rows=5, vision_encoder_forward_calls=1,
                  text_encoder_forward_calls=1, denoising_invocations=1)
    child.validate_compute(counts)
    with pytest.raises(child.static.ScopeViolation, match='exactly one B1'):
        child.validate_compute({**counts, 'denoising_invocations': 2})


def test_production_prediction_path_has_one_b1_call_and_only_postprediction_sync():
    tree = ast.parse(SCRIPT.read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    predict = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == '_predict_unguided']
    sync = [node for node in calls if ast.unparse(node.func) == 'torch.cuda.synchronize']
    assert len(predict) == len(sync) == 1
    assert next(kw.value.value for kw in predict[0].keywords if kw.arg == 'B') == 1
    assert predict[0].lineno < sync[0].lineno
    load = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'load_policy')
    assert not any(isinstance(node, ast.Call) and ast.unparse(node.func) == 'torch.cuda.synchronize' for node in ast.walk(load))
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == 'child_probe' for node in calls)
