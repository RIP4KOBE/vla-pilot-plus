"""CPU fakes only; never import Torch, LIBERO, MuJoCo or a renderer."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('scene_child', Path(__file__).with_name('libero-task0-render-only.py'))
child = importlib.util.module_from_spec(spec)
spec.loader.exec_module(child)


def fake_modules():
    calls = []
    def native(name):
        def function(*args, **kwargs):
            calls.append((name, args, kwargs))
        return function
    mujoco = SimpleNamespace(**{name: native(name) for name in ['mj_step', 'mj_step1', 'mj_step2', 'mj_forward']})
    rgb = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    class Sim:
        def __init__(self):
            self.data = SimpleNamespace(time=0.0)
        def step(self, *args, **kwargs):
            calls.append(('sim.step', args, kwargs))
        def render(self, *args, **kwargs):
            calls.append(('render', args, kwargs))
            return (rgb, np.ones((2, 2), dtype=np.float32)) if kwargs.get('depth', False) else rgb
    return mujoco, Sim, rgb, calls


def test_integration_rejected_before_original_call_and_bindings_restored():
    mujoco, Sim, _, calls = fake_modules()
    originals = (mujoco.mj_step, mujoco.mj_step2, Sim.step, Sim.render)
    events = []
    guard = child.Guard(events.append)
    guard.install(mujoco, Sim)
    try:
        for operation in (lambda: mujoco.mj_step(None, None), lambda: mujoco.mj_step2(None, None), lambda: Sim().step()):
            with pytest.raises(child.ScopeViolation, match='outside diagnostic scope'):
                operation()
        assert calls == [] and guard.blocked_integrations == 3
    finally:
        guard.restore()
    assert (mujoco.mj_step, mujoco.mj_step2, Sim.step, Sim.render) == originals


def test_initialization_native_calls_are_preserved_and_time_recorded():
    mujoco, Sim, _, calls = fake_modules()
    events = []
    guard = child.Guard(events.append)
    guard.install(mujoco, Sim)
    try:
        data = SimpleNamespace(time=1.25)
        mujoco.mj_step1(None, data)
        mujoco.mj_forward(None, data)
        assert guard.step1 == guard.forwards == 1
        assert [call[0] for call in calls] == ['mj_step1', 'mj_forward']
        assert all(event['sim_time_before'] == 1.25 for event in events)
        assert all(event['sim_time_after'] == 1.25 for event in events if event['event'].endswith('_exit'))
    finally:
        guard.restore()


def test_render_limit_includes_constructor_phase_and_preserves_return_identity():
    mujoco, Sim, rgb, calls = fake_modules()
    events = []
    guard = child.Guard(events.append, limit=2)
    guard.install(mujoco, Sim)
    try:
        sim = Sim()
        assert sim.render(camera_name='agentview', width=640, height=640, depth=False) is rgb
        guard.phase = 'render_loop'
        assert sim.render(camera_name='agentview', width=640, height=640, depth=False) is rgb
        with pytest.raises(child.ScopeViolation, match='budget exhausted'):
            sim.render(camera_name='agentview', width=640, height=640, depth=False)
        assert guard.renders == 2 and len(calls) == 2
        assert [event['phase'] for event in events if event['event'] == 'render_enter'] == ['construct', 'render_loop']
        for event in events:
            if event['event'] == 'render_exit':
                assert event['rgb_dtype'] == 'uint8' and event['rgb_finite'] and event['rgb_nonuniform']
                assert event['rgb_min'] == 0 and event['rgb_max'] == 11 and event['depth_finite'] is None
    finally:
        guard.restore()


def test_real_flow_shape_construct_set_init_eight_renders_no_reset_or_action():
    mujoco, Sim, _, calls = fake_modules()
    events, closed = [], []
    guard = child.Guard(events.append)
    guard.install(mujoco, Sim)
    init_row = object()
    try:
        def camera_observations(sim):
            for camera in ('agentview', 'robot0_eye_in_hand'):
                sim.render(camera_name=camera, width=128, height=128, depth=True)
        class Env:
            def __init__(self):
                self.sim = Sim()
                self.env = SimpleNamespace(model=SimpleNamespace(get_xml=lambda: 'mock model identity'))
                mujoco.mj_step1(None, self.sim.data)
                mujoco.mj_forward(None, self.sim.data)
                camera_observations(self.sim)
            def set_init_state(self, row):
                assert row is init_row
                mujoco.mj_forward(None, self.sim.data)
                camera_observations(self.sim)
            def reset(self):
                pytest.fail('reset is outside this minimal construction path')
            def step(self, action):
                pytest.fail('actions are outside diagnostic scope')
            def close(self):
                closed.append(True)
        child.run_scene(Env, init_row, guard, events.append)
        assert guard.renders == 12 and guard.step1 == 1 and guard.forwards == 2
        assert guard.blocked_integrations == 0 and closed == [True]
        assert sum(event['event'] == 'render_enter' and event['phase'] == 'render_loop' for event in events) == 8
        assert all(event['depth_finite'] is True for event in events if event['event'] == 'render_exit' and event['depth'])
    finally:
        guard.restore()


def test_unexpected_native_time_advance_fails_with_public_time_evidence():
    events = []
    guard = child.Guard(events.append)
    def changed(_model, data):
        data.time += 0.002
    observed = guard.native_observer(changed, 'mj_step1')
    with pytest.raises(child.ScopeViolation, match='advanced simulation time'):
        observed(None, SimpleNamespace(time=0.0))
    assert events[-1]['sim_time_before'] == 0.0 and events[-1]['sim_time_after'] == 0.002
