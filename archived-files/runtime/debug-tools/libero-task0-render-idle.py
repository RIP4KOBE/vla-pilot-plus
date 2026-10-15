#!/usr/bin/env python3
"""GPU3 static-scene temporal control: six explicit renders around 75 seconds idle."""
import argparse
import faulthandler
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

SCHEMA = 'qd-ed-task0-render-idle-contract-v1'
PROTOCOL = 'experiments/iteration_001_execution_intent/gpu3-render-idle-diagnostic.md'
HELPER_SHA256 = '82981d32eaf709ac3c7e4232749b92baeb86994fa98bdd49c81347819d715e70'
helper_path = Path(__file__).with_name('libero-task0-render-model.py')
if hashlib.sha256(helper_path.read_bytes()).hexdigest() != HELPER_SHA256:
    raise RuntimeError('validated frame/guard helper changed')
spec = importlib.util.spec_from_file_location('static_idle_guard_helper', helper_path)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
require, digest, phase = helper.require, helper.digest, helper.phase


def workflow(factory, init_row, guard, emit, cuda_is_initialized, sleep=time.sleep, clock=time.monotonic):
    env = None
    states = {}
    def check_cuda(boundary):
        initialized = bool(cuda_is_initialized())
        states[boundary] = initialized
        emit({'event': 'cuda_initialization_state', 'boundary': boundary, 'is_initialized': initialized})
        require(not initialized, 'Torch CUDA initialized outside idle-control scope')
    try:
        check_cuda('before_construct')
        guard.phase = 'construct'
        with phase(emit, 'construct'):
            env = factory()
        guard.phase = 'set_init_state'
        with phase(emit, 'set_init_state'):
            env.set_init_state(init_row)
        initial_time = float(env.sim.data.time)
        emit({'event': 'scene_identity', 'sim_time': initial_time,
            'generated_model_xml_sha256': hashlib.sha256(env.env.model.get_xml().encode()).hexdigest()})
        def boundary(name):
            guard.phase = name
            require(guard.limit - guard.renders >= 3, 'insufficient total render budget for required boundary')
            with phase(emit, name):
                require(float(env.sim.data.time) == initial_time, 'scene time changed before render boundary')
                for camera, size, depth in helper.CAMERAS:
                    env.sim.render(camera_name=camera, width=size, height=size, depth=depth)
                require(float(env.sim.data.time) == initial_time, 'scene time changed after render boundary')
        boundary('before_idle')
        check_cuda('before_idle')
        guard.phase = 'idle_wait'
        emit({'event': 'idle_enter', 'requested_seconds': 75.0, 'sim_time': initial_time})
        idle_started = clock()
        sleep(75.0)
        idle_finished = clock()
        idle_elapsed = idle_finished - idle_started
        emit({'event': 'idle_exit', 'requested_seconds': 75.0, 'elapsed_seconds': idle_elapsed,
            'idle_started_monotonic': idle_started, 'idle_finished_monotonic': idle_finished})
        require(idle_elapsed >= 75.0, 'fixed idle interval was shorter than 75 seconds')
        check_cuda('after_idle')
        require(float(env.sim.data.time) == initial_time, 'scene time changed during idle interval')
        boundary('after_idle')
        check_cuda('after_final_render')
        return {'idle_requested_seconds': 75.0, 'idle_elapsed_seconds': idle_elapsed,
            'cuda_initialization_states': states, 'explicit_render_calls': 6,
            'sim_time_after_init': initial_time, 'sim_time_final': float(env.sim.data.time)}
    finally:
        if env is not None:
            guard.phase = 'close'
            with phase(emit, 'close'):
                env.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--contract-sha256', required=True)
    args = parser.parse_args(argv)
    require(digest(args.contract) == args.contract_sha256, 'contract fingerprint mismatch')
    contract = json.loads(args.contract.read_text())
    require(contract['schema'] == SCHEMA and contract['source_script_sha256'] == digest(__file__), 'contract/script mismatch')
    for label in ('runtime_manifest', 'seed_plan'):
        require(digest(contract[label + '_path']) == contract[label + '_sha256'], label + ' fingerprint mismatch')
    runtime = json.loads(Path(contract['runtime_manifest_path']).read_text())
    root = Path(runtime['worktree']).resolve()
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == contract['source_commit'],
            'source HEAD changed')
    require(runtime['gpu_mapping']['physical_gpu'] == 3 and runtime['gpu_mapping']['egl_device_index'] == 0,
            'expected physical GPU3/EGL0')
    expected_env = {'CUDA_VISIBLE_DEVICES': '3', 'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'MUJOCO_EGL_DEVICE_ID': '0',
        'MUJOCO_GL': 'egl', 'PYOPENGL_PLATFORM': 'egl', 'LIBERO_CONFIG_PATH': runtime['environment']['LIBERO_CONFIG_PATH']}
    require(all(os.environ.get(name) == value for name, value in expected_env.items()), 'frozen GPU/LIBERO environment mismatch')
    records = contract['source_files']
    require(len({row['path'] for row in records}) == len(records) and PROTOCOL in {row['path'] for row in records},
            'source/protocol fingerprints missing or duplicated')
    for row in records:
        source = (root / row['path']).resolve()
        require(source.is_relative_to(root) and digest(source) == row['sha256'], 'source file fingerprint mismatch')
    dependencies = contract['dependency_sources']
    require({row['module'] for row in dependencies} == helper.DEPENDENCY_MODULES and len(dependencies) == len(helper.DEPENDENCY_MODULES),
            'dependency source set differs from static scene contract')
    for row in dependencies:
        require(Path(row['path']).is_absolute() and digest(row['path']) == row['sha256'], 'dependency fingerprint mismatch')
    seeds = json.loads(Path(contract['seed_plan_path']).read_text())
    row, = [item for item in seeds['blocks']['dev'] if item['task_id'] == 0]
    require(row['env_seed'] == row['policy_seed'] == 1969522881 and row['init_index'] == 0, 'scene seed/init mismatch')
    task = runtime['tasks']['0']
    require(digest(task['bddl_path']) == row['bddl_sha256'] and digest(task['init_path']) == row['init_file_sha256'],
            'frozen task0 BDDL/init changed')
    output = Path(contract['output_dir']).resolve()
    require(output.is_relative_to(Path(runtime['artifact_root']).resolve()), 'output outside owned artifact root')
    output.mkdir(parents=True, exist_ok=True)
    events = output / 'render_idle_events.jsonl'
    with events.open('x'):
        pass
    def emit(record):
        with events.open('a') as stream:
            stream.write(json.dumps({'monotonic_seconds': time.monotonic(), 'pid': os.getpid(), **record},
                sort_keys=True, allow_nan=False) + '\n')
        helper.validate_frame(record)
    def deadline(_signum, _frame):
        raise TimeoutError('render-idle diagnostic reached 180-second deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(180)
    faulthandler.enable(all_threads=True)
    sys.addaudithook(helper.audit_network)
    started = time.monotonic()
    guard = helper.RenderModelGuard(emit, 32)
    try:
        emit({'event': 'started', 'resource_id': contract['resource_id'], 'source_commit': contract['source_commit'],
            'contract_sha256': args.contract_sha256, 'script_sha256': digest(__file__),
            'static_helper_sha256': helper.STATIC_SHA256, 'frame_helper_sha256': HELPER_SHA256,
            'physical_gpu': 3, 'egl_device_index': 0, 'timeout_seconds': 180, 'total_render_cap': 32,
            'policy_model_loads': 0, 'predict_unguided_invocations': 0, 'action_vectors_executed': 0,
            'stage_calls': 0, 'dino_model_loads': 0})
        import numpy as np
        import torch
        sys.path.insert(0, str(root))
        sys.path.insert(0, str(root / 'third_party/libero_pro'))
        import mujoco
        from robosuite.utils.binding_utils import MjSim
        guard.install(mujoco, MjSim)
        from libero.libero.envs import OffScreenRenderEnv
        for item in dependencies:
            path = Path(importlib.import_module(item['module']).__file__).resolve()
            require(path == Path(item['path']).resolve() and digest(path) == item['sha256'], 'loaded dependency source differs')
        emit({'event': 'dependency_sources', 'files': {item['module']: item['sha256'] for item in dependencies}})
        init_states = torch.load(task['init_path'], map_location='cpu', weights_only=False)
        init_row = np.ascontiguousarray(np.asarray(init_states[0], dtype=np.float64))
        require(init_row.shape == (110,) and hashlib.sha256(init_row.tobytes()).hexdigest() == row['init_row_sha256'],
                'loaded init row differs')
        np.random.seed(row['env_seed'])
        def factory():
            return OffScreenRenderEnv(bddl_file_name=task['bddl_path'], camera_heights=128, camera_widths=128,
                camera_depths=True, camera_names=['agentview', 'robot0_eye_in_hand'], renderer='mujoco')
        evidence = workflow(factory, init_row, guard, emit, torch.cuda.is_initialized)
        require(guard.blocked_integrations == 0, 'integration attempted')
        evidence.update(schema=SCHEMA, resource_id=contract['resource_id'], diagnostic_only=True, task_success=None,
            camera_render_calls=guard.renders, mj_step1_calls=guard.step1, mj_forward_calls=guard.forwards,
            mj_step_or_mj_step2_calls=0, action_vectors_executed=0, stage_calls=0, dino_model_loads=0,
            policy_model_loads=0, predict_unguided_invocations=0, elapsed_seconds=time.monotonic() - started)
        with (output / 'render-idle-evidence.json').open('x') as stream:
            json.dump(evidence, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
        emit({'event': 'completed', **evidence})
        return 0
    except BaseException as exc:
        emit({'event': 'failed', 'exception_type': type(exc).__name__, 'elapsed_seconds': time.monotonic() - started,
            'camera_render_calls': guard.renders, 'mj_step1_calls': guard.step1, 'mj_forward_calls': guard.forwards,
            'refused_integration_calls': guard.blocked_integrations, 'prediction_calls_started': 0})
        raise
    finally:
        guard.restore()
        signal.alarm(0)


if __name__ == '__main__':
    raise SystemExit(main())
