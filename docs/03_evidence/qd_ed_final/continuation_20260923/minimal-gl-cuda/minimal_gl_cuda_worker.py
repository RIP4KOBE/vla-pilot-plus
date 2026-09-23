#!/usr/bin/env python3
"""Bounded, single-context static diagnostic. Importing this module is CPU-only."""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import faulthandler
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time

STAGES = ('baseline', 'cuda_init', 'cuda_allocation', 'cuda_matmul')
EXPECTED_UUID = 'GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315'
EXPECTED_ENV = {'CUDA_VISIBLE_DEVICES': '3', 'CUDA_DEVICE_ORDER': 'PCI_BUS_ID',
                'MUJOCO_EGL_DEVICE_ID': '0', 'MUJOCO_GL': 'egl', 'PYOPENGL_PLATFORM': 'egl'}
READBACK_VALIDITY = {'baseline_min_distinct_rgb_colors': 2,
                    'raw_depth_min': 0.0, 'raw_depth_max': 1.0,
                    'baseline_depth_spatial_variation': True,
                    'baseline_has_interior_depth': True}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def emit(path, event, **fields):
    with Path(path).open('a') as stream:
        stream.write(json.dumps({'event': event, 'monotonic': time.monotonic(),
                                 'time_unix': time.time(), **fields}, sort_keys=True,
                                allow_nan=False) + '\n')
        stream.flush(); os.fsync(stream.fileno())


@contextlib.contextmanager
def phase(log, name):
    emit(log, 'enter', phase=name)
    try:
        yield
    except BaseException as exc:
        emit(log, 'error', phase=name, error=type(exc).__name__, message=str(exc))
        raise
    else:
        emit(log, 'exit', phase=name)


def compare_arrays(array, reference):
    import numpy as np
    same_shape = array.shape == reference.shape and array.dtype == reference.dtype
    finite = bool(np.isfinite(array).all())
    valid = same_shape and finite and bool(np.isfinite(reference).all())
    delta = np.abs(array.astype(np.float64) - reference.astype(np.float64)) if valid else None
    return {'shape': list(array.shape), 'dtype': str(array.dtype), 'finite': finite,
            'array_sha256': hashlib.sha256(array.tobytes(order='C')).hexdigest(),
            'exact_reference_match': bool(same_shape and np.array_equal(array, reference)),
            'different_elements': int(np.count_nonzero(array != reference)) if valid else None,
            'max_abs_difference': float(delta.max(initial=0)) if valid else None}


def readback_validity(rgb, depth):
    """Exact nonblank checks fixed before GPU evidence; no empirical thresholds."""
    import numpy as np
    shaped = rgb.shape == (96, 96, 3) and depth.shape == (96, 96)
    finite = bool(np.isfinite(depth).all())
    valid = shaped and finite
    return {'distinct_rgb_colors': int(np.unique(rgb.reshape(-1, 3), axis=0).shape[0]) if shaped else None,
            'depth_min': float(depth.min()) if valid else None,
            'depth_max': float(depth.max()) if valid else None,
            'depth_in_unit_interval': bool(valid and np.all((depth >= 0) & (depth <= 1))),
            'depth_spatial_variation': bool(valid and depth.min() < depth.max()),
            'has_interior_depth': bool(valid and np.any((depth > 0) & (depth < 1)))}


def require_readback_validity(validity, *, baseline):
    require(validity['depth_in_unit_interval'], 'raw depth outside [0,1]')
    if baseline:
        require(validity['distinct_rgb_colors'] is not None and validity['distinct_rgb_colors'] >= 2,
                'blank baseline: fewer than two distinct RGB pixel colors')
        require(validity['depth_spatial_variation'] and validity['has_interior_depth'],
                'baseline depth lacks nonconstant visible geometry')


def save_frame(output, index, stage, within_stage, rgb, depth, reference):
    import numpy as np
    require(index < 10, 'render cap exceeded')
    # Persist observed arrays before judging them, including failed readbacks.
    records = {}
    for name, array, ref in zip(('rgb', 'depth'), (rgb, depth), reference):
        path = output / f'frame_{index:02d}_{stage}_{within_stage}_{name}.npy'
        with path.open('xb') as stream:
            np.save(stream, array, allow_pickle=False)
            stream.flush(); os.fsync(stream.fileno())
        records[name] = {**compare_arrays(array, ref), 'path': str(path),
                         'npy_sha256': sha256(path)}
    validity = readback_validity(rgb, depth)
    record = {'index': index, 'stage': stage, 'within_stage': within_stage,
              'readback_validity': validity, **records}
    emit(output / 'events.jsonl', 'frame', **record)
    require(rgb.shape == (96, 96, 3) and rgb.dtype == np.uint8, 'RGB shape/dtype mismatch')
    require(depth.shape == (96, 96) and depth.dtype == np.float32, 'depth shape/dtype mismatch')
    require(records['rgb']['finite'] and records['depth']['finite'], 'nonfinite readback')
    require_readback_validity(validity, baseline=index == 0)
    require(records['rgb']['exact_reference_match'], f'RGB mismatch at {stage}:{within_stage}')
    return record


def run_boundaries(backend, output):
    """The same orchestration is exercised by CPU fakes; no hidden warmup frames."""
    frames, reference = [], None
    for stage in STAGES:
        with phase(output / 'events.jsonl', stage):
            if stage == 'baseline':
                require(not backend.cuda_initialized(), 'CUDA initialized before baseline')
            else:
                getattr(backend, stage)()
            for within in range(2):
                if stage == 'baseline':
                    require(not backend.cuda_initialized(), 'CUDA initialized during baseline')
                backend.assert_static()
                rgb, depth = backend.render()
                if reference is None:
                    reference = (rgb.copy(), depth.copy())
                frames.append(save_frame(output, len(frames), stage, within, rgb, depth, reference))
                backend.assert_static()
                if stage == 'baseline':
                    require(not backend.cuda_initialized(), 'CUDA initialized during baseline')
    require(len(frames) == 8, 'incomplete fixed sequence')
    return frames


def normalized_uuid(value):
    # Recent PyTorch exposes UUID as a printable UUID or string, no early query.
    return str(value).lower().removeprefix('gpu-')


class RealBackend:
    def __init__(self, contract, output):
        self.output, self.contract = output, contract
        self.context = self.render_context = self.scene = None
        self.forward_calls = self.step_calls = self.render_calls = self.make_current_calls = 0
        self.context_creations = 0

    def initialize(self):
        with phase(self.output / 'events.jsonl', 'torch_import'):
            import torch
            self.torch = torch
            require(not torch.cuda.is_initialized(), 'torch import initialized CUDA')
        with phase(self.output / 'events.jsonl', 'static_scene_initialize'):
            import numpy as np
            import mujoco
            self.np, self.mj = np, mujoco
            require(not self.cuda_initialized(), 'CUDA initialized before context creation')
            spec = importlib.util.spec_from_file_location('minimal_production_egl_context',
                                                        self.contract['production_egl_source'])
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            # Exact installed implementation, bypassing broad robosuite package initialization.
            self.context = module.EGLGLContext(96, 96, device_id=0)
            self.context_creations += 1
            self.context.make_current(); self.make_current_calls += 1
            self.context_identity = id(self.context)
            self.model = mujoco.MjModel.from_xml_path(self.contract['scene_xml'])
            self.data = mujoco.MjData(self.model)
            mujoco.mj_forward(self.model, self.data); self.forward_calls += 1
            self.static_snapshot = self.snapshot()
            self.scene = mujoco.MjvScene(self.model, maxgeom=32)
            self.camera = mujoco.MjvCamera()
            self.camera.type = mujoco.mjtCamera.mjCAMERA_FIXED
            self.camera.fixedcamid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, 'probe')
            require(self.camera.fixedcamid >= 0, 'fixed camera unavailable')
            self.option = mujoco.MjvOption()
            self.perturb = mujoco.MjvPerturb()
            self.render_context = mujoco.MjrContext(self.model, mujoco.mjtFontScale.mjFONTSCALE_100)
            mujoco.mjr_setBuffer(mujoco.mjtFramebuffer.mjFB_OFFSCREEN, self.render_context)
            self.viewport = mujoco.MjrRect(0, 0, 96, 96)
            require(not self.cuda_initialized(), 'CUDA initialized before first baseline frame')
            emit(self.output / 'events.jsonl', 'scope', context_implementation=self.contract['production_egl_source'],
                 expected_egl_index=0, expected_physical_gpu=3, expected_uuid=EXPECTED_UUID,
                 context_creations=self.context_creations, forward_calls=self.forward_calls, step_calls=0,
                 graphics_identity_basis='fresh unmasked metadata plus production explicit EGL-index selection',
                 actual_display_device_query='not performed; no added GL/EGL identity query confound')

    def snapshot(self):
        names = ('qpos', 'qvel', 'qacc', 'ctrl', 'act', 'mocap_pos', 'mocap_quat', 'xpos', 'xquat')
        return (float(self.data.time), tuple((name, getattr(self.data, name).tobytes()) for name in names),
                self.model.geom_pos.tobytes(), self.model.geom_quat.tobytes(),
                self.model.cam_pos.tobytes(), self.model.cam_quat.tobytes())

    def assert_static(self):
        require(self.snapshot() == self.static_snapshot, 'static model/data changed')
        require(id(self.context) == self.context_identity and self.context_creations == 1
                and self.make_current_calls == 1 and self.forward_calls == 1 and self.step_calls == 0,
                'context or simulation scope changed')

    def cuda_initialized(self):
        return self.torch.cuda.is_initialized()

    def cuda_init(self):
        self.torch.cuda.init()
        require(self.torch.cuda.device_count() == 1 and self.torch.cuda.current_device() == 0,
                'masked CUDA device mismatch')
        observed = self.torch.cuda.get_device_properties(0).uuid
        emit(self.output / 'events.jsonl', 'cuda_identity', logical_device=0, uuid=str(observed),
             expected_uuid=EXPECTED_UUID)
        require(normalized_uuid(observed) == normalized_uuid(EXPECTED_UUID), 'actual CUDA UUID mismatch')

    def cuda_allocation(self):
        self.matrix = self.torch.ones((32, 32), dtype=self.torch.float32, device='cuda:0')
        self.torch.cuda.synchronize()
        observed = self.matrix.cpu().numpy()
        require(self.np.array_equal(observed, self.np.ones((32, 32), dtype=self.np.float32)),
                'allocation contents mismatch')
        emit(self.output / 'events.jsonl', 'cuda_output', operation='allocation',
             **compare_arrays(observed, self.np.ones((32, 32), dtype=self.np.float32)))

    def cuda_matmul(self):
        self.product = self.matrix @ self.matrix
        self.torch.cuda.synchronize()
        observed = self.product.cpu().numpy()
        expected = self.np.full((32, 32), 32, dtype=self.np.float32)
        emit(self.output / 'events.jsonl', 'cuda_output', operation='matmul', **compare_arrays(observed, expected))
        require(self.np.array_equal(observed, expected), 'matmul output mismatch')

    def render(self):
        require(self.render_calls < 10, 'render cap exceeded')
        rgb = self.np.empty((96, 96, 3), dtype=self.np.uint8)
        depth = self.np.empty((96, 96), dtype=self.np.float32)
        with phase(self.output / 'events.jsonl', f'render_{self.render_calls:02d}'):
            self.mj.mjv_updateScene(self.model, self.data, self.option, self.perturb, self.camera,
                                    self.mj.mjtCatBit.mjCAT_ALL, self.scene)
            self.render_calls += 1
            self.mj.mjr_render(self.viewport, self.scene, self.render_context)
            self.mj.mjr_readPixels(rgb, depth, self.viewport, self.render_context)
        return rgb, depth

    def close(self):
        # No rebind/rebuild at cleanup. Any native cleanup fault is captured by parent.
        with phase(self.output / 'events.jsonl', 'cleanup'):
            if self.render_context is not None:
                self.render_context.free()
            # MjvScene owns native memory through its Python destructor (no free method).
            self.scene = None
            if self.context is not None:
                self.context.free()


def block_out_of_scope(event, args):
    if event in {'socket.connect', 'socket.connect_ex', 'socket.bind', 'subprocess.Popen', 'os.system'}:
        raise RuntimeError(f'out-of-scope operation: {event}')
    if event == 'import' and (args[0].startswith(('libero', 'robosuite.environments', 'core.rdt'))):
        raise RuntimeError('out-of-scope application import')


def verify_contract(contract, digest):
    require(sha256(contract) == digest, 'contract hash mismatch')
    value = json.loads(Path(contract).read_text())
    require(value['schema'] == 'minimal-gl-cuda-v1' and value['stages'] == list(STAGES)
            and value['timeout_seconds'] == 120 and value['physical_gpu'] == 3
            and value['egl_device_index'] == 0 and value['uuid'] == EXPECTED_UUID
            and value['readback_validity'] == READBACK_VALIDITY, 'contract scope mismatch')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == value['boot_id'], 'boot changed')
    require(all(os.environ.get(k) == v for k, v in EXPECTED_ENV.items()), 'GPU environment mismatch')
    require(os.getppid() == value['supervisor_pid'], 'supervisor is not parent')
    # Kernel-enforced orphan cleanup even if the supervisor itself is SIGKILLed.
    libc = ctypes.CDLL(None, use_errno=True)
    require(libc.prctl(1, signal.SIGKILL, 0, 0, 0) == 0, 'parent-death guard unavailable')
    require(os.getppid() == value['supervisor_pid'], 'supervisor exited during guard installation')
    for path, expected in value['fingerprints'].items():
        require(sha256(path) == expected, f'frozen file changed: {path}')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--contract-sha256', required=True)
    args = parser.parse_args()
    faulthandler.enable(all_threads=True)
    # Native fatal errors get Python thread stacks. Parent owns timeout and all accounting.
    contract = verify_contract(args.contract, args.contract_sha256)
    sys.addaudithook(block_out_of_scope)
    output = Path(contract['output_dir'])
    backend = RealBackend(contract, output)
    try:
        backend.initialize()
        frames = run_boundaries(backend, output)
    finally:
        backend.close()
    write_json(output / 'result.json', {'schema': 'minimal-gl-cuda-result-v1', 'status': 'passed',
               'frame_count': len(frames), 'frames': frames, 'forward_calls': backend.forward_calls,
               'step_calls': backend.step_calls, 'context_creations': backend.context_creations,
               'make_current_calls': backend.make_current_calls, 'render_calls': backend.render_calls,
               'no_environment_episodes': True, 'cuda_uuid': EXPECTED_UUID})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
