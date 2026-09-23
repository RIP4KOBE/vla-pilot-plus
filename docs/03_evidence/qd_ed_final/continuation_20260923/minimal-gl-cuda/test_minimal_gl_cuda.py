"""CPU only: fakes and raw-array evidence; no torch/MuJoCo/OpenGL import."""
import ast
import json
import os
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import minimal_gl_cuda_worker as w
import supervise_minimal_gl_cuda as s


class FakeBackend:
    def __init__(self, mismatch=None, nonfinite=None, initialized=False):
        self.initialized = initialized
        self.calls, self.count = [], 0
        self.mismatch, self.nonfinite = mismatch, nonfinite

    def cuda_initialized(self):
        return self.initialized

    def assert_static(self):
        self.calls.append('static')

    def cuda_init(self):
        self.calls.append('cuda_init'); self.initialized = True

    def cuda_allocation(self):
        self.calls.append('cuda_allocation')

    def cuda_matmul(self):
        self.calls.append('cuda_matmul')

    def render(self):
        self.calls.append('render')
        rgb = np.full((96, 96, 3), 17, dtype=np.uint8)
        depth = np.full((96, 96), 0.5, dtype=np.float32)
        rgb[:, 48:] = (100, 50, 25)
        depth[48:, :] = 0.75
        if self.count == self.mismatch:
            rgb[0, 0, 0] += 1
        if self.count == self.nonfinite:
            depth[0, 0] = np.nan
        self.count += 1
        return rgb, depth


def test_fixed_two_frame_boundaries_and_no_warmup(tmp_path):
    backend = FakeBackend()
    frames = w.run_boundaries(backend, tmp_path)
    assert [x for x in backend.calls if x != 'static'] == [
        'render', 'render', 'cuda_init', 'render', 'render',
        'cuda_allocation', 'render', 'render', 'cuda_matmul', 'render', 'render']
    assert len(frames) == 8 and len(list(tmp_path.glob('*.npy'))) == 16
    assert all(x['rgb']['exact_reference_match'] for x in frames)
    assert all(x['depth']['finite'] for x in frames)


@pytest.mark.parametrize('index', [1, 2, 4, 6, 7])
def test_first_rgb_mismatch_preserved_and_never_retried(tmp_path, index):
    backend = FakeBackend(mismatch=index)
    with pytest.raises(RuntimeError, match='RGB mismatch'):
        w.run_boundaries(backend, tmp_path)
    assert backend.count == index + 1
    assert len(list(tmp_path.glob('*.npy'))) == 2 * (index + 1)
    events = [json.loads(line) for line in (tmp_path / 'events.jsonl').read_text().splitlines()]
    failed = [e for e in events if e['event'] == 'frame'][-1]
    assert failed['rgb']['different_elements'] == 1
    assert failed['rgb']['max_abs_difference'] == 1


def test_depth_nonfinite_preserved_and_stops(tmp_path):
    backend = FakeBackend(nonfinite=3)
    with pytest.raises(RuntimeError, match='nonfinite'):
        w.run_boundaries(backend, tmp_path)
    assert backend.count == 4
    assert np.isnan(np.load(next(tmp_path.glob('frame_03*depth.npy')))).any()


def test_depth_difference_recorded_without_new_equality_requirement(tmp_path):
    rgb = np.zeros((96, 96, 3), np.uint8)
    baseline = np.zeros((96, 96), np.float32)
    record = w.save_frame(tmp_path, 2, 'cuda_init', 0, rgb, baseline + 1, (rgb, baseline))
    assert record['depth']['finite'] and not record['depth']['exact_reference_match']
    assert record['depth']['max_abs_difference'] == 1


def test_preinitialized_cuda_fails_before_any_render(tmp_path):
    backend = FakeBackend(initialized=True)
    with pytest.raises(RuntimeError, match='before baseline'):
        w.run_boundaries(backend, tmp_path)
    assert backend.count == 0


def test_unexpected_cuda_init_during_baseline_stops(tmp_path):
    backend = FakeBackend()
    original = backend.render
    def render():
        result = original(); backend.initialized = True; return result
    backend.render = render
    with pytest.raises(RuntimeError, match='during baseline'):
        w.run_boundaries(backend, tmp_path)
    assert backend.count == 1


def test_absolute_frame_cap(tmp_path):
    rgb = np.zeros((96, 96, 3), np.uint8); depth = np.zeros((96, 96), np.float32)
    with pytest.raises(RuntimeError, match='render cap'):
        w.save_frame(tmp_path, 10, 'baseline', 0, rgb, depth, (rgb, depth))
    assert not list(tmp_path.iterdir())


def test_source_scope_has_one_forward_and_no_step_or_renderer():
    tree = ast.parse(Path(w.__file__).read_text())
    attributes = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert attributes.count('mj_forward') == 1
    assert attributes.count('EGLGLContext') == 1
    assert attributes.count('make_current') == 1
    assert not {'mj_step', 'mj_step1', 'mj_step2', 'Renderer'} & set(attributes)
    assert all(name not in sys.modules for name in ('torch', 'mujoco', 'OpenGL', 'libero'))


@pytest.mark.parametrize('change', [{'physical_gpu': 7}, {'egl_device_index': 3}, {'uuid': 'GPU-spoof'},
                                  {'metadata_cuda_ordinal_namespace': 'masked_cuda'}, {'display_or_context_calls': True}])
def test_mapping_rejects_spoof_and_ordinal_confusion(change):
    mapping = {'physical_gpu': 3, 'egl_device_index': 0, 'uuid': w.EXPECTED_UUID,
               'pci_bus_id': '00000000:61:00.0', 'metadata_mapping_verified': True,
               'metadata_cuda_ordinal_namespace': 'unmasked_pci_bus_id', 'display_or_context_calls': False}
    s.validate_mapping(mapping)
    with pytest.raises(RuntimeError):
        s.validate_mapping({**mapping, **change})


def test_owned_xids_require_pci_pid_code_and_boot():
    def row(message, boot='abc'):
        return {'MESSAGE': message, '_BOOT_ID': boot, '__CURSOR': 'c'}
    good = 'NVRM: Xid (PCI:0000:61:00): 31, pid=123, name=python'
    assert len(s.owned_xids([row(good)], 123, 'abc')) == 1
    assert s.owned_xids([row(good)], 12, 'abc') == []
    assert s.owned_xids([row(good.replace('61:00', '41:00'))], 123, 'abc') == []
    assert s.owned_xids([row(good.replace(': 31,', ': 13,'))], 123, 'abc') == []
    with pytest.raises(RuntimeError, match='boot'):
        s.owned_xids([row(good, 'other')], 123, 'abc')


def test_exclusivity_covers_graphics_and_compute():
    def xml(pid=None, identity=w.EXPECTED_UUID):
        proc = '' if pid is None else f'<process_info><pid>{pid}</pid><type>G</type></process_info>'
        return f'<nvidia_smi_log><gpu><uuid>{identity}</uuid><processes>{proc}</processes></gpu></nvidia_smi_log>'
    s.check_graphics_exclusive(xml(), -1)
    s.check_graphics_exclusive(xml(123), 123)
    with pytest.raises(RuntimeError, match='external'):
        s.check_graphics_exclusive(xml(456), 123)
    with pytest.raises(RuntimeError, match='UUID'):
        s.check_graphics_exclusive(xml(identity='wrong'), 123)


def test_kill_only_owned_group(monkeypatch):
    calls = []
    process = SimpleNamespace(pid=123, poll=lambda: None, wait=lambda **kw: calls.append(('wait', kw)))
    monkeypatch.setattr(s.os, 'getpgid', lambda pid: 123)
    monkeypatch.setattr(s.os, 'killpg', lambda pid, sig: calls.append((pid, sig)))
    s.kill_owned(process)
    assert calls[0] == (123, signal.SIGKILL)
    monkeypatch.setattr(s.os, 'getpgid', lambda pid: 456)
    with pytest.raises(RuntimeError, match='process group'):
        s.kill_owned(process)
    assert len(calls) == 2


def test_watchdog_does_not_extend_lifetime_for_blocking_metadata(monkeypatch):
    calls = []; expired = SimpleNamespace(set=lambda: calls.append('expired'))
    stopped = SimpleNamespace(wait=lambda seconds: calls.append(seconds) or False)
    monkeypatch.setattr(s.time, 'monotonic', lambda: 119)
    monkeypatch.setattr(s, 'kill_owned', lambda child: calls.append(child))
    child = SimpleNamespace(poll=lambda: None)
    s.watchdog(child, 120, stopped, expired)
    assert calls == [1, 'expired', child]


def test_watchdog_does_not_time_out_already_exited_child(monkeypatch):
    calls = []
    expired = SimpleNamespace(set=lambda: calls.append('expired'))
    stopped = SimpleNamespace(wait=lambda seconds: False)
    monkeypatch.setattr(s.time, 'monotonic', lambda: 121)
    monkeypatch.setattr(s, 'kill_owned', lambda child: calls.append('killed'))
    s.watchdog(SimpleNamespace(poll=lambda: 0), 120, stopped, expired)
    assert calls == []


@pytest.mark.parametrize('exitcode,write_failure', [(0, False), (-6, False), (0, True)])
def test_accounting_has_one_resource_and_cleanup_elapsed(tmp_path, monkeypatch, exitcode, write_failure):
    events, cleanup = [], []
    fake = SimpleNamespace(pid=os.getpid(), returncode=exitcode, poll=lambda: exitcode)
    contract = {'resource_id': 'cpu-fake', 'output_dir': str(tmp_path), 'worker': w.__file__,
                'boot_id': 'abc', 'source_commit': 'test'}
    path = tmp_path / 'contract.json'; path.write_text('{}')
    monkeypatch.setattr(s, 'verify_frozen', lambda c: None)
    monkeypatch.setattr(s, 'gpu_processes', lambda pid: None)
    monkeypatch.setattr(s, 'kernel_rows', lambda extra: [{'_BOOT_ID': 'abc', '__CURSOR': 'c', 'MESSAGE': ''}])
    monkeypatch.setattr(s.subprocess, 'Popen', lambda *args, **kwargs: fake)
    monkeypatch.setattr(s.threading, 'Thread', lambda **kwargs: SimpleNamespace(start=lambda: None, join=lambda **kw: None))
    monkeypatch.setattr(s, 'validate_result', lambda output: {'status': 'passed'})
    monkeypatch.setattr(s, 'kill_owned', lambda process: cleanup.append(process))
    if write_failure:
        original = w.write_json
        def write_json(path, value):
            if path.name == 'supervisor-result.json':
                raise OSError('simulated full evidence disk')
            return original(path, value)
        monkeypatch.setattr(w, 'write_json', write_json)
    ticks = iter([100, 107]); monkeypatch.setattr(s.time, 'monotonic', lambda: next(ticks))
    runner = SimpleNamespace(append_healthcheck_event=lambda root, event: events.append(event))
    result = s.run_admitted(contract, path, runner, {})
    assert [e['event'] for e in events] == ['reserved', 'dispatched', 'completed' if exitcode == 0 and not write_failure else 'aborted']
    assert result['gpu_process_wall_seconds'] == 7
    assert result['scientific_episode_count'] == 0
    assert cleanup == [fake] and result['child_returncode'] == exitcode
    assert result['evidence_files_sha256']['worker.log'] == w.sha256(tmp_path / 'worker.log')
    assert result['evidence_files_sha256']['process.json'] == w.sha256(tmp_path / 'process.json')
    if write_failure:
        assert 'evidence_write_error' in result


def test_result_validation_independently_reads_all_raw_arrays(tmp_path):
    frames = w.run_boundaries(FakeBackend(), tmp_path)
    value = {'status': 'passed', 'frame_count': 8, 'render_calls': 8, 'forward_calls': 1,
             'step_calls': 0, 'context_creations': 1, 'make_current_calls': 1,
             'cuda_uuid': w.EXPECTED_UUID, 'frames': frames}
    (tmp_path / 'result.json').write_text(json.dumps(value))
    assert s.validate_result(tmp_path)['status'] == 'passed'
    with Path(frames[7]['rgb']['path']).open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(RuntimeError, match='hash'):
        s.validate_result(tmp_path)


def test_network_and_application_scope_audit():
    for event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
        with pytest.raises(RuntimeError):
            w.block_out_of_scope(event, ())
    with pytest.raises(RuntimeError):
        w.block_out_of_scope('import', ('libero.libero.envs',))
    w.block_out_of_scope('import', ('mujoco',))


@pytest.mark.parametrize('kind', ['black', 'constant_red', 'constant_depth', 'endpoint_only_depth'])
def test_blank_baseline_rejected_with_raw_evidence(tmp_path, kind):
    rgb, depth = FakeBackend().render()
    if kind == 'black':
        rgb[:] = 0
    elif kind == 'constant_red':
        rgb[:] = (255, 0, 0)
    elif kind == 'constant_depth':
        depth[:] = 0.5
    else:
        depth[:48] = 0; depth[48:] = 1
    with pytest.raises(RuntimeError, match='blank baseline|visible geometry'):
        w.save_frame(tmp_path, 0, 'baseline', 0, rgb, depth, (rgb, depth))
    assert len(list(tmp_path.glob('*.npy'))) == 2
    records = [json.loads(line) for line in (tmp_path / 'events.jsonl').read_text().splitlines()]
    assert records[-1]['event'] == 'frame'


@pytest.mark.parametrize('bad_value', [-0.0001, 1.0001])
def test_depth_range_frozen_and_rejected_at_every_boundary(tmp_path, bad_value):
    rgb, depth = FakeBackend().render()
    depth[0, 0] = bad_value
    with pytest.raises(RuntimeError, match=r'outside \[0,1\]'):
        w.save_frame(tmp_path, 6, 'cuda_matmul', 0, rgb, depth, (rgb, depth))
    assert len(list(tmp_path.glob('*.npy'))) == 2


def test_xml_contains_visible_distinct_plane_box_and_no_simulation_objects():
    scene = ET.parse(Path(w.__file__).with_name('scene.xml')).getroot()
    assert scene.find('asset') is None and scene.find('actuator') is None
    world = scene.find('worldbody')
    geoms = world.findall('geom')
    assert {g.attrib['type'] for g in geoms} == {'plane', 'box'}
    assert len({g.attrib['rgba'] for g in geoms}) == 2
    assert not scene.findall('.//joint') and not scene.findall('.//freejoint')
    assert len(world.findall('camera')) == len(world.findall('light')) == 1
    camera = world.find('camera')
    position = np.fromstring(camera.attrib['pos'], sep=' ')
    axes = np.fromstring(camera.attrib['xyaxes'], sep=' ').reshape(2, 3)
    x = axes[0] / np.linalg.norm(axes[0])
    y = axes[1] - np.dot(axes[1], x) * x; y /= np.linalg.norm(y)
    z = np.cross(x, y)
    half_fov = np.tan(np.deg2rad(float(camera.attrib['fovy']) / 2))
    # Analytic pinhole check, not a renderer: box center and a plane point are in view.
    box = next(g for g in geoms if g.attrib['type'] == 'box')
    for target in (np.fromstring(box.attrib['pos'], sep=' '), np.array([0.6, 0.0, 0.0])):
        delta = target - position; distance = -np.dot(delta, z)
        assert distance > 0
        assert abs(np.dot(delta, x)) < distance * half_fov
        assert abs(np.dot(delta, y)) < distance * half_fov


def test_parent_rejects_self_consistent_blank_arrays(tmp_path):
    frames = w.run_boundaries(FakeBackend(), tmp_path)
    # Forge hashes to agree with blank arrays: semantic validation must still fail.
    record = frames[0]
    path = Path(record['rgb']['path']); blank = np.zeros((96, 96, 3), np.uint8)
    with path.open('wb') as stream:
        np.save(stream, blank, allow_pickle=False)
    record['rgb']['npy_sha256'] = w.sha256(path)
    record['rgb']['array_sha256'] = w.compare_arrays(blank, blank)['array_sha256']
    value = {'status': 'passed', 'frame_count': 8, 'render_calls': 8, 'forward_calls': 1,
             'step_calls': 0, 'context_creations': 1, 'make_current_calls': 1,
             'cuda_uuid': w.EXPECTED_UUID, 'frames': frames}
    (tmp_path / 'result.json').write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match='blank baseline'):
        s.validate_result(tmp_path)


def test_plan_contract_rejected_under_different_parent_before_loading_libraries(tmp_path, monkeypatch):
    contract = {'schema': 'minimal-gl-cuda-v1', 'stages': list(w.STAGES), 'timeout_seconds': 120,
                'physical_gpu': 3, 'egl_device_index': 0, 'uuid': w.EXPECTED_UUID,
                'readback_validity': w.READBACK_VALIDITY, 'boot_id': s.boot_id(),
                'supervisor_pid': os.getpid(), 'fingerprints': {}}
    for key, value in w.EXPECTED_ENV.items():
        monkeypatch.setenv(key, value)
    path = tmp_path / 'contract.json'; path.write_text(json.dumps(contract))
    monkeypatch.setattr(w.ctypes, 'CDLL', lambda *a, **kw: pytest.fail('library loaded before parent validation'))
    with pytest.raises(RuntimeError, match='supervisor is not parent'):
        w.verify_contract(path, w.sha256(path))


def test_predispatch_failure_is_zero_cost_and_never_launches(tmp_path, monkeypatch):
    events = []
    contract = {'resource_id': 'cpu-fake', 'output_dir': str(tmp_path), 'worker': w.__file__,
                'boot_id': 'abc', 'source_commit': 'test'}
    path = tmp_path / 'contract.json'; path.write_text('{}')
    def changed(c):
        raise RuntimeError('frozen source changed')
    monkeypatch.setattr(s, 'verify_frozen', changed)
    monkeypatch.setattr(s, 'kernel_rows', lambda extra: [{'_BOOT_ID': 'abc', '__CURSOR': 'c', 'MESSAGE': ''}])
    monkeypatch.setattr(s.subprocess, 'Popen', lambda *a, **kw: pytest.fail('unexpected launch'))
    runner = SimpleNamespace(append_healthcheck_event=lambda root, event: events.append(event))
    result = s.run_admitted(contract, path, runner, {})
    assert [e['event'] for e in events] == ['reserved', 'aborted']
    assert result['gpu_process_wall_seconds'] == 0 and result['child_returncode'] is None


def test_unresolved_cleanup_keeps_resource_inflight(tmp_path, monkeypatch):
    events = []
    fake = SimpleNamespace(pid=os.getpid(), returncode=None, poll=lambda: None)
    contract = {'resource_id': 'cpu-fake', 'output_dir': str(tmp_path), 'worker': w.__file__,
                'boot_id': 'abc', 'source_commit': 'test'}
    path = tmp_path / 'contract.json'; path.write_text('{}')
    monkeypatch.setattr(s, 'verify_frozen', lambda c: None)
    def external(pid):
        if pid != -1:
            raise RuntimeError('external graphics process')
    monkeypatch.setattr(s, 'gpu_processes', external)
    monkeypatch.setattr(s, 'kernel_rows', lambda extra: [{'_BOOT_ID': 'abc', '__CURSOR': 'c', 'MESSAGE': ''}])
    monkeypatch.setattr(s.subprocess, 'Popen', lambda *a, **kw: fake)
    monkeypatch.setattr(s.threading, 'Thread', lambda **kw: SimpleNamespace(start=lambda: None, join=lambda **kw: None))
    def unresolved(process):
        raise RuntimeError('termination unconfirmed')
    monkeypatch.setattr(s, 'kill_owned', unresolved)
    ticks = iter([100, 107]); monkeypatch.setattr(s.time, 'monotonic', lambda: next(ticks))
    runner = SimpleNamespace(append_healthcheck_event=lambda root, event: events.append(event))
    with pytest.raises(RuntimeError, match='remains inflight'):
        s.run_admitted(contract, path, runner, {})
    assert [e['event'] for e in events] == ['reserved', 'dispatched']
    assert json.loads((tmp_path / 'cleanup-unresolved.json').read_text())['elapsed_seconds_lower_bound'] == 7
