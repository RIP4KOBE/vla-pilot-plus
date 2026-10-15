#!/usr/bin/env python3
"""Prospective task0 scene diagnostic: zero actions and no time integration.

Standard construction retains mj_step1 and forward. The owning supervisor must
enforce exclusive GPU3, account wall time, and enforce an external <=600s deadline.
This child does not reserve resources, select a GPU, retry, or evaluate a policy.
"""
import argparse
import faulthandler
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ScopeViolation(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ScopeViolation(message)


class Guard:
    """Process-local counting/limits; original allowed native calls are unchanged."""
    def __init__(self, emit, limit=32):
        require(type(limit) is int and 1 <= limit <= 32, 'render limit must be between 1 and 32')
        self.emit, self.limit = emit, limit
        self.phase = 'construct'
        self.renders = self.step1 = self.forwards = self.blocked_integrations = 0
        self._originals = []

    def forbid_integration(self, *_args, **_kwargs):
        self.blocked_integrations += 1
        self.emit({'event': 'integration_refused', 'phase': self.phase})
        raise ScopeViolation('mj_step/mj_step2/MjSim.step integration is outside diagnostic scope')

    def native_observer(self, original, name):
        def observed(model, data, *args, **kwargs):
            before = float(data.time)
            if name == 'mj_step1':
                self.step1 += 1
            else:
                self.forwards += 1
            self.emit({'event': name + '_enter', 'phase': self.phase, 'sim_time_before': before})
            result = original(model, data, *args, **kwargs)
            after = float(data.time)
            self.emit({'event': name + '_exit', 'phase': self.phase,
                       'sim_time_before': before, 'sim_time_after': after})
            require(after == before, 'native initialization unexpectedly advanced simulation time')
            return result
        return observed

    def render_observer(self, original):
        def observed(sim, *args, **kwargs):
            require(self.renders < self.limit, 'total camera render budget exhausted')
            width = kwargs.get('width', args[0] if args else None)
            height = kwargs.get('height', args[1] if len(args) > 1 else None)
            camera = kwargs.get('camera_name')
            require((camera, width, height) in {
                ('agentview', 128, 128), ('robot0_eye_in_hand', 128, 128), ('agentview', 640, 640)},
                'unexpected camera or dimensions')
            require(kwargs.get('depth', False) is (width == 128), 'unexpected camera depth mode')
            require(kwargs.get('segmentation', False) is False, 'segmentation is outside diagnostic scope')
            self.renders += 1
            count, before = self.renders, float(sim.data.time)
            common = {'phase': self.phase, 'render_index': count, 'camera': camera,
                      'width': width, 'height': height, 'depth': width == 128}
            self.emit({**common, 'event': 'render_enter', 'sim_time_before': before})
            started = time.perf_counter()
            result = original(sim, *args, **kwargs)
            elapsed, after = time.perf_counter() - started, float(sim.data.time)
            rgb = result[0] if isinstance(result, tuple) else result
            import numpy as np
            rgb_min, rgb_max = float(rgb.min()), float(rgb.max())
            self.emit({**common, 'event': 'render_exit', 'elapsed_s': elapsed,
                'sim_time_before': before, 'sim_time_after': after,
                'rgb_shape': [int(value) for value in rgb.shape],
                'rgb_dtype': str(rgb.dtype), 'rgb_finite': bool(np.isfinite(rgb).all()),
                'rgb_min': rgb_min, 'rgb_max': rgb_max, 'rgb_nonuniform': rgb_min != rgb_max,
                'depth_finite': bool(np.isfinite(result[1]).all()) if isinstance(result, tuple) else None,
                'rgb_sha256': hashlib.sha256(rgb.tobytes()).hexdigest()})
            require(after == before, 'render unexpectedly advanced simulation time')
            return result
        return observed

    def install(self, mujoco, sim_class):
        replacements = [(mujoco, 'mj_step', self.forbid_integration),
            (mujoco, 'mj_step2', self.forbid_integration),
            (mujoco, 'mj_step1', self.native_observer(mujoco.mj_step1, 'mj_step1')),
            (mujoco, 'mj_forward', self.native_observer(mujoco.mj_forward, 'mj_forward')),
            (sim_class, 'step', self.forbid_integration),
            (sim_class, 'render', self.render_observer(sim_class.render))]
        for obj, name, replacement in replacements:
            self._originals.append((obj, name, getattr(obj, name)))
            setattr(obj, name, replacement)

    def restore(self):
        for obj, name, original in reversed(self._originals):
            setattr(obj, name, original)
        self._originals.clear()


def run_scene(factory, init_row, guard, emit):
    """No reset/step or settling actions: retain standard constructor then set row0."""
    env = None
    try:
        guard.phase = 'construct'
        emit({'event': 'construct_enter'})
        env = factory()
        emit({'event': 'construct_exit', 'sim_time': float(env.sim.data.time)})
        guard.phase = 'set_init_state'
        emit({'event': 'set_init_state_enter'})
        env.set_init_state(init_row)
        initial_time = float(env.sim.data.time)
        emit({'event': 'set_init_state_exit', 'sim_time': initial_time})
        # This records the real scene produced by LIBERO, not a synthetic XML.
        emit({'event': 'scene_identity',
              'generated_model_xml_sha256': hashlib.sha256(env.env.model.get_xml().encode()).hexdigest()})
        guard.phase = 'render_loop'
        cameras = [('agentview', 128, True), ('robot0_eye_in_hand', 128, True), ('agentview', 640, False)]
        for index in range(8):
            if guard.renders >= guard.limit:
                break
            camera, size, depth = cameras[index % len(cameras)]
            env.sim.render(camera_name=camera, width=size, height=size, depth=depth)
        require(float(env.sim.data.time) == initial_time, 'scene time changed after init-state binding')
    finally:
        if env is not None:
            guard.phase = 'close'
            emit({'event': 'close_enter'})
            env.close()
            emit({'event': 'close_exit'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--runtime-sha256', required=True)
    parser.add_argument('--seed-plan', type=Path, required=True)
    parser.add_argument('--seed-plan-sha256', required=True)
    parser.add_argument('--source-head', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-renders', type=int, default=32)
    parser.add_argument('--timeout-seconds', type=int, default=600)
    args = parser.parse_args(argv)
    require(1 <= args.timeout_seconds <= 600, 'timeout must be at most 600 seconds')
    require(1 <= args.max_renders <= 32, 'render count must be at most 32')
    require(digest(args.runtime) == args.runtime_sha256, 'runtime fingerprint mismatch')
    require(digest(args.seed_plan) == args.seed_plan_sha256, 'seed plan fingerprint mismatch')
    runtime = json.loads(args.runtime.read_text())
    seeds = json.loads(args.seed_plan.read_text())
    root = Path(runtime['worktree']).resolve()
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == args.source_head,
            'source HEAD mismatch')
    require(runtime['gpu_mapping']['physical_gpu'] == 3 and runtime['gpu_mapping']['egl_device_index'] == 0,
            'runtime must bind physical GPU3 and EGL0')
    expected_env = {'CUDA_VISIBLE_DEVICES': '3', 'CUDA_DEVICE_ORDER': 'PCI_BUS_ID',
        'MUJOCO_EGL_DEVICE_ID': '0', 'MUJOCO_GL': 'egl', 'PYOPENGL_PLATFORM': 'egl',
        'LIBERO_CONFIG_PATH': runtime['environment']['LIBERO_CONFIG_PATH']}
    require(all(os.environ.get(name) == value for name, value in expected_env.items()),
            'supervisor hardware/LIBERO environment differs from frozen binding')
    row, = [row for row in seeds['blocks']['dev'] if row['task_id'] == 0]
    require(row['env_seed'] == row['policy_seed'] == 1969522881 and row['init_index'] == 0, 'task0 seed/init identity mismatch')
    task = runtime['tasks']['0']
    require(digest(task['bddl_path']) == row['bddl_sha256'] and digest(task['init_path']) == row['init_file_sha256'],
            'frozen BDDL/init file changed')
    output = args.output.resolve()
    require(output.is_relative_to(Path(runtime['artifact_root']).resolve()), 'output must remain in owned artifact root')
    output.mkdir(parents=True, exist_ok=True)
    event_path = output / 'scene_render_events.jsonl'
    with event_path.open('x'):
        pass
    def emit(record):
        with event_path.open('a') as stream:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
    def deadline(_signum, _frame):
        raise TimeoutError('scene diagnostic deadline reached')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(args.timeout_seconds)
    faulthandler.enable(all_threads=True)
    started = time.monotonic()
    guard = Guard(emit, args.max_renders)
    try:
        emit({'event': 'started', 'kind': 'task0_scene_render_diagnostic',
            'source_head': args.source_head, 'runtime_sha256': args.runtime_sha256,
            'script_sha256': digest(__file__), 'physical_gpu': 3, 'egl_device_index': 0,
            'max_total_camera_renders': args.max_renders, 'timeout_seconds': args.timeout_seconds,
            'policy_model_loads': 0, 'action_vectors_executed': 0, 'stage_calls': 0,
            'literal_zero_native_dynamics_calls': False})
        # Lazy imports only after frozen input/mask checks. Torch loads only the
        # small CPU init-state file; no model/encoder or adapter/main import.
        import numpy as np
        import torch
        sys.path.insert(0, str(root / 'third_party/libero_pro'))
        import mujoco
        from robosuite.utils.binding_utils import MjSim
        guard.install(mujoco, MjSim)
        from libero.libero.envs import OffScreenRenderEnv
        source_modules = ['libero.libero.envs.env_wrapper', 'libero.libero.envs.bddl_base_domain',
            'robosuite.environments.base', 'robosuite.environments.robot_env', 'robosuite.utils.binding_utils',
            'robosuite.renderers.context.egl_context']
        emit({'event': 'dependency_sources', 'files': {name: digest(importlib.import_module(name).__file__)
                                                     for name in source_modules}})
        init_states = torch.load(task['init_path'], map_location='cpu', weights_only=False)
        init_row = np.ascontiguousarray(np.asarray(init_states[0], dtype=np.float64))
        require(init_row.shape == (110,) and hashlib.sha256(init_row.tobytes()).hexdigest() == row['init_row_sha256'],
                'loaded init row0 differs from frozen identity')
        np.random.seed(row['env_seed'])
        def factory():
            return OffScreenRenderEnv(bddl_file_name=task['bddl_path'], camera_heights=128,
                camera_widths=128, camera_depths=True, camera_names=['agentview', 'robot0_eye_in_hand'],
                renderer='mujoco')
        run_scene(factory, init_row, guard, emit)
        require(guard.blocked_integrations == 0, 'integration was attempted')
        emit({'event': 'completed', 'diagnostic_only': True, 'task_success': None,
            'elapsed_seconds': time.monotonic() - started, 'camera_render_calls': guard.renders,
            'mj_step1_calls': guard.step1, 'mj_forward_calls': guard.forwards,
            'mj_step_or_mj_step2_calls': 0, 'action_vectors_executed': 0, 'stage_calls': 0})
        return 0
    except BaseException as exc:
        emit({'event': 'failed', 'exception_type': type(exc).__name__,
            'elapsed_seconds': time.monotonic() - started, 'camera_render_calls': guard.renders,
            'mj_step1_calls': guard.step1, 'mj_forward_calls': guard.forwards,
            'refused_integration_calls': guard.blocked_integrations})
        raise
    finally:
        guard.restore()
        signal.alarm(0)


if __name__ == '__main__':
    raise SystemExit(main())
