"""Real spawn/IPC tests with CPU fake scenes; no GPU / model / simulator import."""
import ast
import importlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import numpy as np
import pytest

DIRECTORY = Path(__file__).parent
sys.path.insert(0, str(DIRECTORY))
child = importlib.import_module('libero-task0-render-process')


def cpu_renderer_entry(connection, payload):
    emit = lambda row: child.emit_to_file(payload['events'], row)
    child.renderer_handshake(connection, payload)
    if payload.get('hang_after_ack'):
        # CPU sleep tests only the owned termination path, never executes a scene.
        time.sleep(20)
        return
    def native(*args, **kwargs):
        return None
    mujoco = SimpleNamespace(**{name: native for name in ('mj_step', 'mj_step1', 'mj_step2', 'mj_forward')})
    class Sim:
        def __init__(self):
            self.data = SimpleNamespace(time=0.0)
            self._render_context_offscreen = SimpleNamespace(con=SimpleNamespace(offWidth=640, offHeight=480))
            self.model = SimpleNamespace(vis=SimpleNamespace(global_=SimpleNamespace(offwidth=640, offheight=480)))
            self.calls = 0
        def step(self):
            pytest.fail('original integration must not run')
        def render(self, *, camera_name, width, height, depth=False):
            self.calls += 1
            if payload.get('render_failure') and self.calls == 8:
                raise ValueError('original CPU scene error')
            rgb = np.arange(width * height * 3, dtype=np.uint8).reshape(height, width, 3)
            return (rgb, np.ones((height, width), dtype=np.float32)) if depth else rgb
    guard = child.RenderModelGuard(emit, payload.get('render_limit', 32))
    guard.install(mujoco, Sim)
    init_row = object()
    def observe(sim):
        for camera in ('agentview', 'robot0_eye_in_hand'):
            sim.render(camera_name=camera, width=128, height=128, depth=True)
    class Env:
        def __init__(self):
            emit({'event': 'fake_construct', 'owner_pid': os.getpid()})
            self.sim = Sim()
            self.env = SimpleNamespace(model=SimpleNamespace(get_xml=lambda: 'CPU scene'))
            mujoco.mj_step1(None, self.sim.data)
            mujoco.mj_forward(None, self.sim.data)
            if payload.get('integration_failure'):
                mujoco.mj_step(None, self.sim.data)
            observe(self.sim)
        def set_init_state(self, row):
            assert row is init_row
            mujoco.mj_forward(None, self.sim.data)
            observe(self.sim)
        def close(self):
            emit({'event': 'fake_close', 'owner_pid': os.getpid()})
    okay = child.renderer_loop(connection, payload, Env, init_row, guard, emit)
    connection.close()
    if not okay:
        raise SystemExit(1)


def setup(tmp_path, **extra):
    path = tmp_path / 'render_process_events.jsonl'
    path.touch()
    payload = dict(contract_path='unused CPU mock', contract_sha256='CPU mock fingerprint', resource_id='CPU mock',
                   events=str(path), deadline=time.monotonic() + 15, **extra)
    emit = lambda row: child.emit_to_file(path, row)
    return payload, emit, path


def test_real_spawn_order_ownership_scalar_evidence_cleanup_and_model_ast(tmp_path):
    payload, emit, path = setup(tmp_path)
    parent_pid = os.getpid()
    calls, policy = [], object()
    def load():
        assert os.getpid() == parent_pid
        ownership = json.loads(path.with_name('renderer-process.json').read_text())
        assert ownership['renderer']['pid'] != parent_pid
        calls.append('load')
        return policy
    def predict(value):
        assert value is policy and os.getpid() == parent_pid
        calls.append('predict')
        return {'mock_prediction': True}
    proof = child.workflow(payload, emit, load, predict, target=cpu_renderer_entry, cleanup_seconds=(2, 1, 1))
    assert calls == ['load', 'predict'] and proof['camera_render_calls'] == 13
    assert proof['mj_step1_calls'] == 1 and proof['mj_forward_calls'] == 2 and proof['refused_integration_calls'] == 0
    assert proof['renderer_joined'] and proof['renderer_exitcode'] == 0 and not proof['renderer_forced_termination']
    assert proof['renderer_cleanup_success']
    renderer = proof['renderer']
    assert renderer['pid'] != parent_pid and renderer['ppid'] == parent_pid
    assert renderer['pgid'] == os.getpgid(0) and not Path(f"/proc/{renderer['pid']}").exists()
    events = [json.loads(line) for line in path.read_text().splitlines()]
    register = next(i for i, row in enumerate(events) if row['event'] == 'renderer_process_started')
    construct = next(i for i, row in enumerate(events) if row['event'] == 'fake_construct')
    assert register < construct
    assert all(row['pid'] == renderer['pid'] for row in events if row['event'] in {'render_enter', 'render_exit', 'fake_construct', 'fake_close'})
    assert [(row['phase'], row['pid']) for row in events if row['event'] == 'phase_enter'] == [
        ('construct', renderer['pid']), ('set_init_state', renderer['pid']), ('before_model_load', renderer['pid']),
        ('load_model', parent_pid), ('after_model_load', renderer['pid']), ('predict_b1', parent_pid),
        ('after_prediction_sync', renderer['pid']), ('close', renderer['pid'])]
    maps = [row for row in events if row['event'] == 'gpu_library_maps']
    assert len(maps) == 6 and {row['role'] for row in maps} == {'renderer', 'model_parent'}
    before = ast.parse((DIRECTORY / 'libero-task0-render-model.py').read_text())
    after = ast.parse((DIRECTORY / 'libero-task0-render-process.py').read_text())
    for name in ('load_policy', 'predict_once', 'factory', 'validate_compute'):
        a = next(node for node in ast.walk(before) if isinstance(node, ast.FunctionDef) and node.name == name)
        b = next(node for node in ast.walk(after) if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(a) == ast.dump(b)
    assert sum(isinstance(node, ast.Call) and ast.unparse(node.func) == 'torch.cuda.synchronize'
               for node in ast.walk(after)) == 1
    assert not any(isinstance(node, ast.Call) and ast.unparse(node.func) in {'torch.cuda.init', 'gc.disable'} for node in ast.walk(after))


@pytest.mark.parametrize('failure', ['model', 'render', 'integration', 'cap'])
def test_failures_stop_and_owned_renderer_exits_without_passing_traceback(tmp_path, failure):
    extra = {'render_failure': failure == 'render', 'integration_failure': failure == 'integration',
             'render_limit': 7 if failure == 'cap' else 32}
    payload, emit, path = setup(tmp_path, **extra)
    original_error = RuntimeError('CPU parent model error')
    def load():
        if failure == 'model':
            raise original_error
        return object()
    with pytest.raises(RuntimeError) as caught:
        child.workflow(payload, emit, load, lambda _: pytest.fail('no later prediction'),
                       target=cpu_renderer_entry, cleanup_seconds=(2, 1, 1))
    if failure == 'model':
        assert caught.value is original_error
    else:
        assert isinstance(caught.value, child.RenderProcessFailure)
        assert caught.value.__cause__ is None and caught.value.__context__ is None
    ownership = json.loads(path.with_name('renderer-process.json').read_text())
    assert not Path(f"/proc/{ownership['renderer']['pid']}").exists()
    events = [json.loads(line) for line in path.read_text().splitlines()]
    joined, = [row for row in events if row['event'] == 'renderer_process_joined']
    assert joined['joined'] and not joined['forced_termination']
    assert joined['exitcode'] == (0 if failure == 'model' else 1)
    assert not any(row.get('phase') == 'predict_b1' for row in events)


def test_stalled_owned_renderer_is_boundedly_terminated_never_success(tmp_path):
    payload, emit, path = setup(tmp_path, hang_after_ack=True)
    payload['deadline'] = time.monotonic() + 1.5
    started = time.monotonic()
    with pytest.raises(RuntimeError):
        child.workflow(payload, emit, lambda: pytest.fail('no load'), lambda _: pytest.fail('no prediction'),
                       target=cpu_renderer_entry, cleanup_seconds=(0.1, 0.5, 0.5))
    assert time.monotonic() - started < 5
    events = [json.loads(line) for line in path.read_text().splitlines()]
    joined, = [row for row in events if row['event'] == 'renderer_process_joined']
    assert joined['joined'] and joined['forced_termination'] and joined['exitcode'] != 0
    assert not Path(f"/proc/{joined['renderer_pid']}").exists()
