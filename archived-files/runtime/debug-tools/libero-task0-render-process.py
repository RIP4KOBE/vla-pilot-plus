#!/usr/bin/env python3
"""Spawn-renderer variant of the frozen scene/model/B1 diagnostic; parent supervises both PIDs."""
import argparse
from contextlib import contextmanager
import faulthandler
import hashlib
import importlib
import importlib.util
import json
import os
import multiprocessing
import threading
from pathlib import Path
import signal
import subprocess
import sys
import time

STATIC_SHA256 = '237f1c4125488379f2230c3cd854808c3bc330979d09c120ad10dfb7497fd115'
SCHEMA = 'qd-ed-task0-render-process-contract-v1'
PROTOCOL = 'experiments/iteration_001_execution_intent/gpu3-render-process-diagnostic.md'
DEPENDENCY_MODULES = {'libero.libero.envs.env_wrapper', 'libero.libero.envs.bddl_base_domain',
    'robosuite.environments.base', 'robosuite.environments.robot_env', 'robosuite.utils.binding_utils',
    'robosuite.renderers.context.egl_context'}
CAMERAS = [('agentview', 128, True), ('robot0_eye_in_hand', 128, True), ('agentview', 640, False)]


def load_static():
    path = Path(__file__).with_name('libero-task0-render-only.py')
    if hashlib.sha256(path.read_bytes()).hexdigest() != STATIC_SHA256:
        raise RuntimeError('validated static helper changed')
    spec = importlib.util.spec_from_file_location('validated_static_scene', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


static = load_static()
require, digest = static.require, static.digest


def buffer_scalars(sim):
    """Read existing struct fields only; no GL/EGL/context-changing calls."""
    result = {}
    for key, chain in {'context_offWidth': ('_render_context_offscreen', 'con', 'offWidth'),
        'context_offHeight': ('_render_context_offscreen', 'con', 'offHeight'),
        'model_offwidth': ('model', 'vis', 'global_', 'offwidth'),
        'model_offheight': ('model', 'vis', 'global_', 'offheight')}.items():
        try:
            value = sim
            for attribute in chain:
                value = getattr(value, attribute)
            result[key] = int(value)
        except (AttributeError, TypeError, ValueError):
            result[key] = None
    return result


class RenderModelGuard(static.Guard):
    def render_observer(self, original):
        guarded = super().render_observer(original)
        def observed(sim, *args, **kwargs):
            index = self.renders + 1
            self.emit({'event': 'render_buffer_enter', 'phase': self.phase,
                       'render_index': index, **buffer_scalars(sim)})
            result = guarded(sim, *args, **kwargs)
            self.emit({'event': 'render_buffer_exit', 'phase': self.phase,
                       'render_index': index, **buffer_scalars(sim)})
            return result
        return observed


@contextmanager
def phase(emit, name):
    emit({'event': 'phase_enter', 'phase': name})
    started = time.monotonic()
    try:
        yield
    except BaseException as exc:
        emit({'event': 'phase_exception', 'phase': name, 'exception_type': type(exc).__name__,
              'elapsed_seconds': time.monotonic() - started})
        raise
    else:
        emit({'event': 'phase_exit', 'phase': name, 'elapsed_seconds': time.monotonic() - started})


def validate_frame(record):
    if record.get('event') == 'render_exit':
        require(record['rgb_shape'] == [record['height'], record['width'], 3] and
            record['rgb_dtype'] == 'uint8' and record['rgb_finite'] is True and
            record['rgb_nonuniform'] is True and
            (not record['depth'] or record['depth_finite'] is True),
            'rendered frame is nonfinite, uniform, or has unexpected shape/dtype')


def process_identity(pid=None, role=None):
    pid = os.getpid() if pid is None else pid
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return {'role': role, 'pid': int(pid), 'ppid': int(fields[1]), 'pgid': int(fields[2]),
        'session_id': int(fields[3]), 'proc_start_ticks': fields[19],
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def send_message(connection, value):
    connection.send_bytes(json.dumps(value, sort_keys=True, allow_nan=False).encode())


def receive_message(connection, deadline):
    remaining = deadline - time.monotonic()
    require(remaining > 0 and connection.poll(remaining), 'renderer IPC deadline reached')
    value = json.loads(connection.recv_bytes(65536).decode())
    require(isinstance(value, dict), 'unexpected renderer IPC payload')
    return value


def emit_to_file(events, record):
    with Path(events).open('a') as stream:
        stream.write(json.dumps({'monotonic_seconds': time.monotonic(), 'pid': os.getpid(),
            'thread_id': threading.get_ident(), 'native_thread_id': threading.get_native_id(), **record},
            sort_keys=True, allow_nan=False) + '\n')
    validate_frame(record)


def filtered_gpu_library_maps():
    paths = set()
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(None, 5)
        if len(fields) == 6:
            path = fields[5].removesuffix(' (deleted)')
            name = Path(path).name
            if path.startswith('/') and name.startswith(('libcuda', 'libcudart', 'libEGL', 'libGLX', 'libnvidia')) and '.so' in name:
                paths.add(path)
    return sorted(paths)


def renderer_handshake(connection, payload):
    identity = process_identity(role='renderer')
    parent = payload['model_parent']
    require(identity['ppid'] == parent['pid'] and identity['pgid'] == parent['pgid'] and
            identity['session_id'] == parent['session_id'] and
            process_identity(parent['pid'], 'model_parent') == parent, 'renderer ancestry changed')
    send_message(connection, {'event': 'ready', 'renderer': identity,
        'resource_id': payload['resource_id'], 'contract_sha256': payload['contract_sha256']})
    require(receive_message(connection, payload['deadline']) == {'command': 'start'}, 'renderer start ACK missing')
    return identity


def renderer_loop(connection, payload, factory, init_row, guard, emit):
    env, initial_time = None, None
    failure, cleanup_failure = None, None
    try:
        guard.phase = 'construct'
        with phase(emit, 'construct'):
            env = factory()
        guard.phase = 'set_init_state'
        with phase(emit, 'set_init_state'):
            env.set_init_state(init_row)
        initial_time = float(env.sim.data.time)
        emit({'event': 'scene_identity', 'sim_time': initial_time,
            'generated_model_xml_sha256': hashlib.sha256(env.env.model.get_xml().encode()).hexdigest()})
        send_message(connection, {'ok': True, 'terminal': False, 'event': 'scene_started'})
        expected = iter(('before_model_load', 'after_model_load', 'after_prediction_sync'))
        while True:
            command = receive_message(connection, payload['deadline']).get('command')
            if command == 'close':
                break
            require(command == next(expected, None), 'unexpected renderer boundary order')
            guard.phase = command
            require(guard.limit - guard.renders >= 3, 'insufficient total render budget for required boundary')
            with phase(emit, command):
                require(float(env.sim.data.time) == initial_time, 'scene time changed before boundary')
                for camera, size, depth in CAMERAS:
                    env.sim.render(camera_name=camera, width=size, height=size, depth=depth)
                require(float(env.sim.data.time) == initial_time, 'scene time changed after boundary')
            emit({'event': 'gpu_library_maps', 'role': 'renderer', 'boundary': command,
                  'libraries': filtered_gpu_library_maps()})
            send_message(connection, {'ok': True, 'terminal': False, 'event': 'boundary_completed',
                                     'boundary': command, 'camera_render_calls': guard.renders})
    except BaseException as exc:
        failure = {'exception_type': type(exc).__name__, 'phase': guard.phase}
        emit({'event': 'renderer_exception', **failure})
    # Do not send exceptions/tracebacks: they can retain scene/context handles.
    try:
        if env is not None:
            guard.phase = 'close'
            with phase(emit, 'close'):
                env.close()
    except BaseException as exc:
        cleanup_failure = {'exception_type': type(exc).__name__, 'phase': 'close'}
        emit({'event': 'renderer_cleanup_exception', **cleanup_failure})
    env = None
    evidence = {'renderer_cleanup_success': cleanup_failure is None, 'camera_render_calls': guard.renders,
        'mj_step1_calls': guard.step1, 'mj_forward_calls': guard.forwards, 'mj_step_or_mj_step2_calls': 0,
        'refused_integration_calls': guard.blocked_integrations, 'sim_time_after_init': initial_time}
    emit({'event': 'renderer_stopped', **evidence})
    send_message(connection, {'ok': failure is None and cleanup_failure is None, 'terminal': True,
        'failure': failure or cleanup_failure, 'evidence': evidence})
    return failure is None and cleanup_failure is None


def renderer_main(connection, payload):
    """Spawn entry: only stdlib identity work before the parent records ownership."""
    guard = None
    emit = lambda record: emit_to_file(payload['events'], record)
    try:
        renderer_handshake(connection, payload)
        args = argparse.Namespace(contract=Path(payload['contract_path']), contract_sha256=payload['contract_sha256'])
        contract, runtime, root, config, row, task, dependencies, native = validate_contract(args)
        require(contract['resource_id'] == payload['resource_id'] and str(Path(contract['output_dir']).resolve()) ==
                str(Path(payload['events']).parent.resolve()), 'renderer contract output mismatch')
        faulthandler.enable(all_threads=True)
        sys.addaudithook(audit_network)
        import numpy as np
        import torch
        sys.path.insert(0, str(root / 'third_party/libero_pro'))
        import mujoco
        from robosuite.utils.binding_utils import MjSim
        guard = RenderModelGuard(emit, 32)
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
        okay = renderer_loop(connection, payload, factory, init_row, guard, emit)
        if not okay:
            raise SystemExit(1)
    except BaseException as exc:
        if not isinstance(exc, SystemExit):
            emit({'event': 'renderer_bootstrap_exception', 'exception_type': type(exc).__name__})
            try:
                send_message(connection, {'ok': False, 'terminal': True,
                    'failure': {'exception_type': type(exc).__name__, 'phase': 'renderer_bootstrap'}, 'evidence': {}})
            except (BrokenPipeError, EOFError, OSError):
                pass
        raise SystemExit(1)
    finally:
        # Private guards remain installed through native destructors / process exit.
        # The model parent never installed them, so no shared restoration is needed.
        connection.close()


class RenderProcessFailure(RuntimeError):
    pass


def workflow(payload, emit, load_policy, predict_once, target=renderer_main, cleanup_seconds=(20, 10, 5)):
    require(threading.current_thread() is threading.main_thread(), 'model caller must be main thread')
    parent = process_identity(role='model_parent')
    payload = {**payload, 'model_parent': parent}
    context = multiprocessing.get_context('spawn')
    connection, child_connection = context.Pipe(duplex=True)
    process = context.Process(target=target, args=(child_connection, payload), name='libero-render-owner', daemon=False)
    renderer, terminal, original_failed = None, None, False
    process.start()
    child_connection.close()
    def accept(reply):
        nonlocal terminal
        if reply.get('terminal'):
            terminal = reply
        if not reply.get('ok'):
            failure = reply.get('failure') or {'exception_type': 'Unknown', 'phase': 'IPC'}
            raise RenderProcessFailure('renderer failed: ' + failure['exception_type'] + ' at ' + failure['phase'])
        return reply
    def dispatch(command):
        require(terminal is None, 'renderer already stopped')
        send_message(connection, {'command': command})
        return accept(receive_message(connection, payload['deadline']))
    try:
        ready = receive_message(connection, payload['deadline'])
        require(ready.get('event') == 'ready' and ready.get('resource_id') == payload['resource_id'] and
                ready.get('contract_sha256') == payload['contract_sha256'], 'renderer handshake mismatch')
        renderer = ready['renderer']
        require(renderer['pid'] == process.pid and renderer == process_identity(process.pid, 'renderer') and
            renderer['ppid'] == parent['pid'] and renderer['pgid'] == parent['pgid'] and
            renderer['session_id'] == parent['session_id'] and renderer['boot_id'] == parent['boot_id'],
            'renderer identity/ancestry mismatch')
        ownership = {'schema': 'qd-ed-render-process-ownership-v1', 'resource_id': payload['resource_id'],
            'contract_sha256': payload['contract_sha256'], 'model_parent': parent, 'renderer': renderer}
        path = Path(payload['events']).with_name('renderer-process.json')
        require(not path.exists(), 'renderer ownership record already exists')
        temporary = path.with_name(f'.renderer-process.{os.getpid()}.tmp')
        with temporary.open('x') as stream:
            json.dump(ownership, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        require(not path.exists(), 'renderer ownership record appeared concurrently')
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        emit({'event': 'renderer_process_started', **ownership})
        dispatch('start')
        dispatch('before_model_load')
        emit({'event': 'gpu_library_maps', 'role': 'model_parent', 'boundary': 'before_model_load',
              'libraries': filtered_gpu_library_maps()})
        with phase(emit, 'load_model'):
            policy = load_policy()
        emit({'event': 'gpu_library_maps', 'role': 'model_parent', 'boundary': 'after_model_load',
              'libraries': filtered_gpu_library_maps()})
        dispatch('after_model_load')
        with phase(emit, 'predict_b1'):
            evidence = predict_once(policy)
        emit({'event': 'gpu_library_maps', 'role': 'model_parent', 'boundary': 'after_prediction_sync',
              'libraries': filtered_gpu_library_maps()})
        dispatch('after_prediction_sync')
    except BaseException:
        original_failed = True
        raise
    finally:
        signal.alarm(0)
        emit({'event': 'renderer_cleanup_started', 'maximum_cleanup_seconds': sum(cleanup_seconds)})
        # Bounded, only this verified child. External resource supervisor owns the
        # overall deadline and the complete two-process GPU lifetime accounting.
        if terminal is None and process.is_alive():
            try:
                send_message(connection, {'command': 'close'})
            except (BrokenPipeError, EOFError, OSError):
                pass
        cleanup_deadline = time.monotonic() + cleanup_seconds[0]
        while terminal is None and process.is_alive() and time.monotonic() < cleanup_deadline:
            try:
                if connection.poll(min(0.1, max(0.0, cleanup_deadline - time.monotonic()))):
                    reply = json.loads(connection.recv_bytes(65536).decode())
                    if reply.get('terminal'):
                        terminal = reply
            except (EOFError, OSError):
                break
        process.join(max(0.0, cleanup_deadline - time.monotonic()))
        forced = False
        for wait_seconds, action in ((cleanup_seconds[1], process.terminate), (cleanup_seconds[2], process.kill)):
            if process.is_alive():
                actual = process_identity(process.pid, 'renderer')
                require(actual['ppid'] == parent['pid'] and actual['pgid'] == parent['pgid'] and
                    (renderer is None or actual == renderer), 'refusing cleanup of changed child identity')
                action()
                forced = True
                process.join(wait_seconds)
        connection.close()
        emit({'event': 'renderer_process_joined', 'renderer_pid': process.pid, 'joined': not process.is_alive(),
              'exitcode': process.exitcode, 'forced_termination': forced})
        require(not process.is_alive(), 'owned renderer survived bounded cleanup')
        if not original_failed:
            require(terminal is not None and terminal['ok'] and not forced and process.exitcode == 0,
                    'renderer cleanup or exit failed')
    return {**evidence, **terminal['evidence'], 'model_parent': parent, 'renderer': renderer,
            'renderer_joined': True, 'renderer_exitcode': process.exitcode, 'renderer_forced_termination': False}

def validate_compute(counters):
    for name in ('model_forward_calls', 'vision_encoder_forward_calls', 'text_encoder_forward_calls'):
        require(type(counters.get(name)) is int and counters[name] > 0, 'missing production model/encoder compute')
    require(counters.get('model_batch_rows') == counters['model_forward_calls'] and
            counters.get('denoising_invocations') == 1, 'compute is not exactly one B1 prediction')


def audit_network(event, _args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.bind'}:
        raise RuntimeError('network is outside scene/model diagnostic scope')


def validate_contract(args):
    require(digest(args.contract) == args.contract_sha256, 'contract fingerprint mismatch')
    contract = json.loads(args.contract.read_text())
    require(contract['schema'] == SCHEMA and contract['source_script_sha256'] == digest(__file__), 'contract/script mismatch')
    for label in ('runtime_manifest', 'seed_plan', 'profiles', 'runtime_inventory', 'policy_configuration'):
        require(digest(contract[label + '_path']) == contract[label + '_sha256'], label + ' fingerprint mismatch')
    runtime = json.loads(Path(contract['runtime_manifest_path']).read_text())
    root = Path(runtime['worktree']).resolve()
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == contract['source_commit'],
            'source HEAD changed')
    require(runtime['gpu_mapping']['physical_gpu'] == 3 and runtime['gpu_mapping']['egl_device_index'] == 0,
            'expected physical GPU3/EGL0')
    expected_env = {'CUDA_VISIBLE_DEVICES': '3', 'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'MUJOCO_EGL_DEVICE_ID': '0',
        'MUJOCO_GL': 'egl', 'PYOPENGL_PLATFORM': 'egl', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
        'LIBERO_CONFIG_PATH': runtime['environment']['LIBERO_CONFIG_PATH']}
    require(all(os.environ.get(name) == value for name, value in expected_env.items()), 'frozen GPU/offline/LIBERO environment mismatch')
    source_records = contract['source_files']
    require(len({row['path'] for row in source_records}) == len(source_records), 'duplicate source record')
    for row in source_records:
        source = (root / row['path']).resolve()
        require(source.is_relative_to(root) and digest(source) == row['sha256'], 'source file fingerprint mismatch')
    dependencies = contract['dependency_sources']
    require({row['module'] for row in dependencies} == DEPENDENCY_MODULES and len(dependencies) == len(DEPENDENCY_MODULES),
            'dependency source set differs from static scene contract')
    for row in dependencies:
        require(Path(row['path']).is_absolute() and digest(row['path']) == row['sha256'], 'dependency fingerprint mismatch')
    sys.path.insert(0, str(root / 'scripts'))
    sys.path.insert(0, str(root))
    import qd_ed_policy_native_probe as native
    required_sources = native.runner.REQUIRED_CODE | {native.SCRIPT_RELATIVE, PROTOCOL}
    require(required_sources <= {row['path'] for row in source_records}, 'required source/protocol fingerprints missing')
    profiles = json.loads(Path(contract['profiles_path']).read_text())
    config = json.loads(Path(contract['policy_configuration_path']).read_text())
    require(config == native.policy_configuration(root, profiles), 'policy configuration differs from frozen native B1')
    seeds = json.loads(Path(contract['seed_plan_path']).read_text())
    row, = [item for item in seeds['blocks']['dev'] if item['task_id'] == 0]
    require(row['env_seed'] == row['policy_seed'] == 1969522881 and row['init_index'] == 0, 'scene seed/init mismatch')
    task = runtime['tasks']['0']
    require(digest(task['bddl_path']) == row['bddl_sha256'] and digest(task['init_path']) == row['init_file_sha256'],
            'frozen task0 BDDL/init changed')
    return contract, runtime, root, config, row, task, dependencies, native


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--contract-sha256', required=True)
    args = parser.parse_args(argv)
    contract, runtime, root, config, row, task, dependencies, native = validate_contract(args)
    output = Path(contract['output_dir']).resolve()
    require(output.is_relative_to(Path(runtime['artifact_root']).resolve()), 'output outside owned artifact root')
    output.mkdir(parents=True, exist_ok=True)
    events = output / 'render_process_events.jsonl'
    with events.open('x'):
        pass
    def emit(record):
        emit_to_file(events, record)
    def deadline(_signum, _frame):
        raise TimeoutError('scene/model diagnostic reached 600-second deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(600)
    faulthandler.enable(all_threads=True)
    sys.addaudithook(audit_network)
    started = time.monotonic()
    prediction_calls = 0
    try:
        emit({'event': 'started', 'resource_id': contract['resource_id'], 'source_commit': contract['source_commit'],
            'contract_sha256': args.contract_sha256, 'script_sha256': digest(__file__),
            'static_helper_sha256': STATIC_SHA256, 'physical_gpu': 3, 'egl_device_index': 0,
            'timeout_seconds': 600, 'total_render_cap': 32, 'action_vectors_executed': 0, 'stage_calls': 0})
        import random
        import numpy as np
        import torch
        def load_policy():
            from core.rdt_policy_steer import RDTSteer
            require(torch.cuda.device_count() == 1, 'expected one visible CUDA device')
            properties = torch.cuda.get_device_properties(0)
            normalize = lambda value: str(value).lower().removeprefix('gpu-')
            require(normalize(properties.uuid) == normalize(runtime['gpu_mapping']['uuid']), 'CUDA UUID differs from GPU3 runtime')
            emit({'event': 'cuda_identity', 'torch_logical_device': 0, 'torch_uuid': str(properties.uuid)})
            random.seed(native.SYNTHETIC_SEED)
            np.random.seed(native.SYNTHETIC_SEED)
            torch.manual_seed(native.SYNTHETIC_SEED)
            torch.cuda.manual_seed_all(native.SYNTHETIC_SEED)
            policy = RDTSteer.from_pretrained(config['pretrained_path'], num_inference_steps=config['num_inference_steps'],
                vision_encoder=config['vision_encoder'], text_encoder=config['text_encoder'],
                weight_variant=config['weight_variant'], control_frequency=int(config['control_frequency']))
            policy.to('cuda:0')
            policy.eval()
            policy.post_init(adapter=None, postprocessor=lambda value: value, sample_batch_size=1, policy_config=config)
            policy.reset()
            emit({'event': 'model_loaded', 'synthetic_seed': native.SYNTHETIC_SEED,
                'compute': policy.get_episode_compute_counters()})
            return policy
        def predict_once(policy):
            nonlocal prediction_calls
            require(prediction_calls == 0, 'second B1 prediction is forbidden')
            prediction_calls += 1
            from core.rdt_libero_obs_processor import RDTLiberoObsProcessor
            require(isinstance(policy._obs_processor, RDTLiberoObsProcessor), 'production observation processor missing')
            with phase(emit, 'process_synthetic_observation'):
                converted = policy._obs_processor.process(native.synthetic_observation(np))
            with phase(emit, 'encode_synthetic_task'):
                text_embed = policy._get_lang_embed(converted.task)
            with phase(emit, 'native_predict_unguided_b1'):
                raw = policy._predict_unguided(converted.state_128, converted.state_mask_128, converted.images, text_embed, B=1)
            with phase(emit, 'prediction_cuda_sync_and_inspect'):
                torch.cuda.synchronize(0)
                array = raw.detach().cpu().numpy()
                require(list(array.shape) == [1, 64, 128] and bool(np.isfinite(array).all()), 'invalid raw B1 prediction')
                counters = policy.get_episode_compute_counters()
                validate_compute(counters)
                evidence = {'raw_prediction_shape': list(array.shape), 'raw_prediction_dtype': str(array.dtype),
                    'raw_prediction_finite': True, 'raw_prediction_sha256': hashlib.sha256(array.tobytes()).hexdigest(),
                    'compute': counters, 'synthetic_seed': native.SYNTHETIC_SEED, 'num_inference_steps': policy._num_inference_steps}
                emit({'event': 'prediction_evidence', **evidence})
                return evidence
        payload = {'contract_path': str(args.contract.resolve()), 'contract_sha256': args.contract_sha256,
            'resource_id': contract['resource_id'], 'events': str(events), 'deadline': started + 600}
        evidence = workflow(payload, emit, load_policy, predict_once)
        require(prediction_calls == 1 and evidence['refused_integration_calls'] == 0, 'scope counts differ')
        evidence.update(schema=SCHEMA, resource_id=contract['resource_id'], diagnostic_only=True, task_success=None,
            mj_step_or_mj_step2_calls=0, action_vectors_executed=0, stage_calls=0, dino_model_loads=0,
            predict_unguided_invocations=prediction_calls, elapsed_seconds=time.monotonic() - started)
        with (output / 'render-process-evidence.json').open('x') as stream:
            json.dump(evidence, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
        emit({'event': 'completed', **evidence})
        return 0
    except BaseException as exc:
        emit({'event': 'failed', 'exception_type': type(exc).__name__, 'elapsed_seconds': time.monotonic() - started,
            'prediction_calls_started': prediction_calls})
        raise
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    raise SystemExit(main())
