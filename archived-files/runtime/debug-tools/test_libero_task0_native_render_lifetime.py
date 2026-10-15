"""CPU fake helper integration and lossless frame/reference checks; no GPU imports."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

DIRECTORY = Path(__file__).parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

child = load('native_lifetime_diagnostic', DIRECTORY / 'libero-task0-native-render-lifetime.py')
fixtures = load('native_lifetime_scene_fixtures', DIRECTORY / 'test_libero_task0_render_model.py')


class FakeLifetime:
    def __init__(self, sim):
        self.sim = sim
        self.original = sim.render
        self.closed = self.finalized = False
        self.events = []
        self.calls = 0
        self.failed = False
        sim.render = self.render
        sim.fake_owner = self
    def render(self, *args, **kwargs):
        context = self.sim._render_context_offscreen
        if self.calls:
            self.events.append({'event': 'native_create_exit'})
            context.con = SimpleNamespace(offWidth=self.sim.model.vis.global_.offwidth,
                offHeight=self.sim.model.vis.global_.offheight)
        else:
            self.events.append({'event': 'reuse_existing_native'})
        result = self.original(*args, **kwargs)
        self.calls += 1
        del context.con
        self.events.append({'event': 'native_release_exit', 'verified': True})
        return result
    def close(self):
        self.closed = True
    def snapshot(self):
        return dict(failed=self.failed, closed=self.closed, finalized=self.finalized,
            last_cleanup_success=self.calls > 0, native_attributes_present=self.calls == 0,
            unreturned_factory_allocation_unknown=False, events=self.events.copy())


def setup(tmp_path):
    guard, emit, events, operations, old_factory, init_row, _ = fixtures.setup()
    def factory():
        env = old_factory()
        for name in ('scn', 'cam', 'vopt', 'pert'):
            setattr(env.sim._render_context_offscreen, name, object())
        original_close = env.close
        def close():
            original_close()
            if hasattr(env.sim, 'fake_owner'):
                env.sim.fake_owner.finalized = True
        env.close = close
        return env
    canonical = {}
    for camera, size, depth in child.CAMERAS:
        rgb = np.arange(size * size * 3, dtype=np.uint8).reshape(size, size, 3)
        canonical[child.camera_key(camera, size, size, depth)] = hashlib.sha256(rgb.tobytes()).hexdigest()
    recorder = lambda boundary, camera, size, depth, result, index: child.save_explicit_frame(
        tmp_path, canonical, emit, boundary, camera, size, depth, result, index)
    return guard, emit, events, operations, factory, init_row, canonical, recorder


def test_scene_first_original_calls_nine_canonical_frames_and_fifteen_lossless_npy_files(tmp_path):
    guard, emit, events, operations, factory, init_row, canonical, recorder = setup(tmp_path)
    policy, owners = object(), []
    def install(sim):
        assert guard.renders == 4
        owner = FakeLifetime(sim)
        owners.append(owner)
        return owner
    def load_policy():
        assert guard.renders == 7 and not owners[0].snapshot()['native_attributes_present']
        operations.append('load')
        return policy
    def predict(value):
        assert value is policy and guard.renders == 10 and not owners[0].snapshot()['native_attributes_present']
        operations.append('predict')
        return {'prediction': 'CPU mock'}
    try:
        evidence = child.workflow(factory, init_row, guard, emit, load_policy, predict, install, recorder)
        assert guard.renders == 13 and evidence['explicit_render_calls'] == 9
        assert evidence['native_lifetime_effective_after_render_calls'] == 4
        assert operations.count('load') == operations.count('predict') == 1 and operations[-1] == 'close'
        assert evidence['canonical_rgb_matches_all'] and evidence['python_context_identity_preserved']
        assert len(evidence['raw_frame_artifacts']) == 9 and len(list(tmp_path.rglob('*.npy'))) == 15
        for frame in evidence['raw_frame_artifacts']:
            assert frame['canonical_rgb_matches'] and frame['rgb']['array_sha256'] == canonical[frame['camera_key']]
            for record in (frame['rgb'], frame['depth']):
                if record is not None:
                    value = np.load(record['path'], allow_pickle=False)
                    assert list(value.shape) == record['shape'] and str(value.dtype) == record['dtype']
                    assert hashlib.sha256(value.tobytes()).hexdigest() == record['array_sha256']
                    assert child.digest(record['path']) == record['npy_sha256'] and np.isfinite(value).all()
        assert owners[0].closed and owners[0].finalized
    finally:
        guard.restore()


def test_rgb_mismatch_is_saved_then_stops_before_model_and_reference_hash_is_frozen(tmp_path):
    guard, emit, events, operations, factory, init_row, canonical, _ = setup(tmp_path)
    bad = {**canonical, child.camera_key('agentview', 128, 128, True): '0' * 64}
    def record(*args):
        return child.save_explicit_frame(tmp_path, bad, emit, *args)
    try:
        with pytest.raises(RuntimeError, match='canonical RGB hash mismatch'):
            child.workflow(factory, init_row, guard, emit, lambda: pytest.fail('no model load'),
                lambda _: pytest.fail('no prediction'), FakeLifetime, record)
        assert guard.renders == 5 and len(list(tmp_path.rglob('*.npy'))) == 2
        assert any(e.get('event') == 'raw_frame_artifact' and not e['canonical_rgb_matches'] for e in events)
        assert operations[-1] == 'close'
    finally:
        guard.restore()
    rows = [dict(event='completed', action_vectors_executed=0, mj_step_or_mj_step2_calls=0)]
    for camera, size, depth in child.CAMERAS:
        rows.append(dict(event='render_exit', phase='render_loop', camera=camera, width=size, height=size, depth=depth,
            rgb_sha256=canonical[child.camera_key(camera, size, size, depth)], rgb_shape=[size, size, 3],
            rgb_dtype='uint8', rgb_finite=True, rgb_nonuniform=True, depth_finite=True if depth else None))
    path = tmp_path / 'reference.jsonl'
    path.write_text('\n'.join(json.dumps(row) for row in rows))
    contract = dict(canonical_reference_path=str(path), canonical_reference_sha256=child.digest(path), canonical_rgb_sha256=canonical)
    assert child.validate_canonical_reference(contract) == canonical
    path.write_text(path.read_text() + '\n{}')
    with pytest.raises(RuntimeError, match='fingerprint'):
        child.validate_canonical_reference(contract)


def test_original_model_factory_cuda_ast_and_depth_finite_gate(tmp_path):
    before = ast.parse((DIRECTORY / 'libero-task0-render-model.py').read_text())
    after = ast.parse((DIRECTORY / 'libero-task0-native-render-lifetime.py').read_text())
    for name in ('load_policy', 'predict_once', 'factory', 'validate_compute'):
        a = next(n for n in ast.walk(before) if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in ast.walk(after) if isinstance(n, ast.FunctionDef) and n.name == name)
        assert ast.dump(a) == ast.dump(b)
    cuda_calls = lambda tree: [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and ast.unparse(n.func).startswith('torch.cuda.')]
    assert cuda_calls(before) == cuda_calls(after)
    rgb = np.arange(128 * 128 * 3, dtype=np.uint8).reshape(128, 128, 3)
    canonical = {child.camera_key('agentview', 128, 128, True): hashlib.sha256(rgb.tobytes()).hexdigest()}
    depth = np.full((128, 128), np.nan, dtype=np.float32)
    with pytest.raises(RuntimeError, match='invalid saved raw frame'):
        child.save_explicit_frame(tmp_path, canonical, lambda _: None, 'before_model_load', 'agentview', 128, True, (rgb, depth), 5)
