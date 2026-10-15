#!/usr/bin/env python3
"""Diagnostic application-context lifetime boundary around exactly one original B1."""
import argparse
from contextlib import contextmanager
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
import weakref

STATIC_SHA256 = '237f1c4125488379f2230c3cd854808c3bc330979d09c120ad10dfb7497fd115'
SCHEMA = 'qd-ed-task0-context-lifetime-contract-v1'
PROTOCOL = 'experiments/iteration_001_execution_intent/gpu3-context-lifetime-diagnostic.md'
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


class ModelFirstContextObserver:
    """Observe existing production constructor; no native context queries or binding."""
    def __init__(self, cuda_is_initialized, emit):
        self.cuda_is_initialized, self.emit = cuda_is_initialized, emit
        self.model_loaded = False
        self.context_creation_records = []
        self.context_refs = []
        self._binding = None

    def install(self, context_class):
        require(self._binding is None, 'context observer already installed')
        original = context_class.__init__
        def observed(instance, *args, **kwargs):
            record = {'index': len(self.context_creation_records) + 1,
                'model_loaded_before': self.model_loaded,
                'cuda_initialized_before': bool(self.cuda_is_initialized()), 'completed': False,
                'constructor': {'offscreen': kwargs.get('offscreen', args[1] if len(args) > 1 else True),
                    'device_id': kwargs.get('device_id', args[2] if len(args) > 2 else -1),
                    'max_width': kwargs.get('max_width', args[3] if len(args) > 3 else 640),
                    'max_height': kwargs.get('max_height', args[4] if len(args) > 4 else 480)}}
            self.context_creation_records.append(record)
            self.emit({'event': 'context_creation_enter', **record})
            require(record['model_loaded_before'] and record['cuda_initialized_before'],
                    'render context creation preceded complete model loading / CUDA initialization')
            try:
                result = original(instance, *args, **kwargs)
            except BaseException as exc:
                self.emit({'event': 'context_creation_exception', **record, 'exception_type': type(exc).__name__})
                raise
            record['completed'] = True
            self.context_refs.append((weakref.ref(instance), record))
            self.emit({'event': 'context_creation_exit', **record})
            return result
        self._binding = context_class, original, observed
        context_class.__init__ = observed

    def restore(self):
        if self._binding is not None:
            cls, original, observed = self._binding
            if cls.__init__ is observed:
                cls.__init__ = original
            self._binding = None


@contextmanager
def isolated_scene_cpu_rng(random_module, numpy_module, torch_module, emit):
    """Isolate only Python / NumPy / Torch CPU RNG; no CUDA state APIs."""
    python_state = random_module.getstate()
    numpy_state = numpy_module.random.get_state()
    torch_cpu_state = torch_module.get_rng_state()
    emit({'event': 'scene_cpu_rng_saved', 'generators': ['python', 'numpy', 'torch_cpu']})
    try:
        numpy_module.random.seed(1969522881)
        emit({'event': 'scene_numpy_seed', 'env_seed': 1969522881})
        yield
    finally:
        random_module.setstate(python_state)
        numpy_module.random.set_state(numpy_state)
        torch_module.set_rng_state(torch_cpu_state)
        emit({'event': 'scene_cpu_rng_restored', 'generators': ['python', 'numpy', 'torch_cpu']})


def simulation_snapshot(sim):
    import numpy as np
    result = {name: np.array(getattr(sim.data, name), copy=True) for name in ('qpos', 'qvel', 'act', 'ctrl')}
    result['time'] = np.asarray(float(sim.data.time))
    require(all(bool(np.isfinite(value).all()) for value in result.values()), 'nonfinite physical state')
    return result


def state_sha256(state):
    hasher = hashlib.sha256()
    for name in sorted(state):
        value = state[name]
        hasher.update(name.encode())
        hasher.update(str(value.dtype).encode())
        hasher.update(str(value.shape).encode())
        hasher.update(value.tobytes())
    return hasher.hexdigest()


def same_physical_state(expected, sim):
    import numpy as np
    actual = simulation_snapshot(sim)
    require(all(np.array_equal(expected[key], actual[key]) for key in expected),
            'qpos/qvel/act/ctrl/time changed during context lifecycle')
    return state_sha256(actual)


class ContextLifetime:
    """Naturally destroy one owned application context, then rebuild it once."""
    def __init__(self, context_class, egl_api, context_observer, emit):
        self.context_class, self.egl_api = context_class, egl_api
        self.observer, self.emit = context_observer, emit
        self.destroy_records = []
        self.unraisable_records = []
        self.watching = False
        self.target_address = None
        self.release_calls = self.rebuild_calls = 0
        self.saved = None
        self._original_destroy = None

    @staticmethod
    def address(handle):
        return int(handle.address) if handle is not None else None

    def install(self):
        require(self._original_destroy is None, 'destroy observer already installed')
        original = self.egl_api.eglDestroyContext
        def observed(*args, **kwargs):
            handle = args[1] if len(args) > 1 else kwargs.get('ctx')
            matched = self.watching and self.address(handle) == self.target_address
            try:
                result = original(*args, **kwargs)
            except BaseException as exc:
                if matched:
                    record = {'returned_success': False, 'exception_type': type(exc).__name__}
                    self.destroy_records.append(record)
                    self.emit({'event': 'owned_egl_destroy_exception', **record})
                raise
            if matched:
                record = {'returned_success': bool(result), 'exception_type': None}
                self.destroy_records.append(record)
                self.emit({'event': 'owned_egl_destroy_return', **record})
            return result
        self._original_destroy, self._destroy_wrapper = original, observed
        self.egl_api.eglDestroyContext = observed

    def restore(self):
        if self._original_destroy is not None:
            if self.egl_api.eglDestroyContext is self._destroy_wrapper:
                self.egl_api.eglDestroyContext = self._original_destroy
            self._original_destroy = None

    def release(self, sim):
        require(self.release_calls == 0 and self.rebuild_calls == 0, 'context release cannot repeat')
        self.release_calls += 1
        old = sim._render_context_offscreen
        require(type(old) is self.context_class and old.sim is sim and old.offscreen is True,
                'unexpected or shared render context')
        live = [(reference, record) for reference, record in self.observer.context_refs if reference() is not None]
        require(len(live) == 1 and live[0][0]() is old, 'expected one live managed application context')
        constructor = dict(live[0][1]['constructor'])
        require(constructor['offscreen'] is True and constructor['device_id'] == old.device_id,
                'original constructor identity differs')
        self.saved = {'cam': old.cam, 'vopt': old.vopt, 'pert': old.pert,
            'constructor': constructor, 'physical_state': simulation_snapshot(sim), 'buffers': buffer_scalars(sim)}
        self.state_before = state_sha256(self.saved['physical_state'])
        old_ref, gl_ref = weakref.ref(old), weakref.ref(old.gl_ctx)
        self.target_address = self.address(old.gl_ctx._context)
        require(self.target_address is not None, 'original EGL handle missing')
        self.emit({'event': 'context_release_enter', 'physical_state_sha256': self.state_before,
                   'constructor': constructor, 'global_egl_display_released': False})
        original_unraisable = sys.unraisablehook
        def observe_unraisable(event):
            record = {'exception_type': event.exc_type.__name__ if event.exc_type else 'Unknown'}
            self.unraisable_records.append(record)
            self.emit({'event': 'context_release_unraisable', **record})
            original_unraisable(event)
        self.watching = True
        sys.unraisablehook = observe_unraisable
        try:
            sim._render_context_offscreen = None
            del old  # The original __del__ owns con.free and gl_ctx.free exactly once.
        finally:
            self.watching = False
            if sys.unraisablehook is observe_unraisable:
                sys.unraisablehook = original_unraisable
        require(not self.unraisable_records, 'unraisable exception during context release; prediction forbidden')
        require(sim._render_context_offscreen is None and old_ref() is None and gl_ref() is None,
                'application context or GL context still referenced; prediction forbidden')
        require(len(self.destroy_records) == 1 and self.destroy_records[0]['returned_success'] is True and
                self.destroy_records[0]['exception_type'] is None, 'owned EGL destruction not confirmed')
        self.state_after_release = same_physical_state(self.saved['physical_state'], sim)
        self.emit({'event': 'context_release_exit', 'render_context_weakref_dead': True, 'gl_context_weakref_dead': True,
            'sim_context_none': True, 'owned_egl_destroy_success_count': 1, 'physical_state_sha256': self.state_after_release,
            'global_egl_display_released': False})

    def rebuild(self, sim, guard):
        require(self.release_calls == 1 and self.rebuild_calls == 0 and sim._render_context_offscreen is None,
                'unexpected context rebuild state')
        self.rebuild_calls += 1
        same_physical_state(self.saved['physical_state'], sim)
        before_forwards = guard.forwards
        params = self.saved['constructor']
        self.emit({'event': 'context_rebuild_enter', 'constructor': params})
        new = self.context_class(sim, device_id=params['device_id'], max_width=params['max_width'], max_height=params['max_height'])
        require(sim._render_context_offscreen is new, 'new context did not attach to original sim')
        new.cam, new.vopt, new.pert = self.saved['cam'], self.saved['vopt'], self.saved['pert']
        self.forward_delta = guard.forwards - before_forwards
        require(self.forward_delta == 1, 'context rebuild must add exactly one original mj_forward')
        self.state_after_rebuild = same_physical_state(self.saved['physical_state'], sim)
        require(buffer_scalars(sim) == self.saved['buffers'], 'context/model buffer dimensions changed on rebuild')
        self.emit({'event': 'context_rebuild_exit', 'mj_forward_delta': self.forward_delta,
            'physical_state_sha256': self.state_after_rebuild, 'display_option_objects_preserved': True})

    def evidence(self):
        return {'context_release_calls': self.release_calls, 'context_rebuild_calls': self.rebuild_calls,
            'owned_egl_destroy_records': self.destroy_records, 'release_unraisable_exceptions': self.unraisable_records,
            'global_egl_display_released': False,
            'context_rebuild_mj_forward_calls': self.forward_delta, 'display_option_objects_preserved': True,
            'physical_state_sha256_before_release': self.state_before,
            'physical_state_sha256_after_release': self.state_after_release,
            'physical_state_sha256_after_rebuild': self.state_after_rebuild}


def workflow(factory, init_row, guard, emit, load_policy, predict_once, context_observer, scene_rng, lifetime):
    """Full original loader first; unchanged scene, then exactly one original B1."""
    env = None
    try:
        guard.phase = 'load_model'
        with phase(emit, 'load_model'):
            policy = load_policy()
        context_observer.model_loaded = True
        emit({'event': 'complete_model_loaded_before_scene', 'context_creation_count': len(context_observer.context_creation_records)})
        require(not context_observer.context_creation_records, 'context created before complete model loading')
        with scene_rng():
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
                require(float(env.sim.data.time) == initial_time, 'scene time changed before boundary')
                for camera, size, depth in CAMERAS:
                    env.sim.render(camera_name=camera, width=size, height=size, depth=depth)
                require(float(env.sim.data.time) == initial_time, 'scene time changed after boundary')
        boundary('after_model_load_scene_init')
        guard.phase = 'context_release_before_b1'
        with phase(emit, 'context_release_before_b1'):
            lifetime.release(env.sim)
        guard.phase = 'predict_b1'
        with phase(emit, 'predict_b1'):
            evidence = predict_once(policy)
        guard.phase = 'context_rebuild_after_b1'
        with phase(emit, 'context_rebuild_after_b1'):
            lifetime.rebuild(env.sim, guard)
        boundary('after_prediction_sync')
        return {**evidence, **lifetime.evidence(), 'model_loaded_before_scene': True, 'explicit_render_calls': 6,
            'context_creation_records': context_observer.context_creation_records,
            'cpu_rng_restored_after_scene_init': True, 'scene_env_seed': 1969522881,
            'sim_time_after_init': initial_time, 'sim_time_final': float(env.sim.data.time)}
    finally:
        if env is not None:
            guard.phase = 'close'
            with phase(emit, 'close'):
                env.close()

def validate_compute(counters):
    for name in ('model_forward_calls', 'vision_encoder_forward_calls', 'text_encoder_forward_calls'):
        require(type(counters.get(name)) is int and counters[name] > 0, 'missing production model/encoder compute')
    require(counters.get('model_batch_rows') == counters['model_forward_calls'] and
            counters.get('denoising_invocations') == 1, 'compute is not exactly one B1 prediction')


def audit_network(event, _args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.bind'}:
        raise RuntimeError('network is outside scene/model diagnostic scope')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--contract-sha256', required=True)
    args = parser.parse_args(argv)
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
    output = Path(contract['output_dir']).resolve()
    require(output.is_relative_to(Path(runtime['artifact_root']).resolve()), 'output outside owned artifact root')
    output.mkdir(parents=True, exist_ok=True)
    events = output / 'context_lifetime_events.jsonl'
    with events.open('x'):
        pass
    def emit(record):
        with events.open('a') as stream:
            stream.write(json.dumps({'monotonic_seconds': time.monotonic(), **record}, sort_keys=True, allow_nan=False) + '\n')
        validate_frame(record)
    def deadline(_signum, _frame):
        raise TimeoutError('scene/model diagnostic reached 600-second deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(600)
    faulthandler.enable(all_threads=True)
    sys.addaudithook(audit_network)
    started = time.monotonic()
    guard = RenderModelGuard(emit, 32)
    prediction_calls = 0
    context_observer = None
    lifetime = None
    try:
        emit({'event': 'started', 'resource_id': contract['resource_id'], 'source_commit': contract['source_commit'],
            'contract_sha256': args.contract_sha256, 'script_sha256': digest(__file__),
            'static_helper_sha256': STATIC_SHA256, 'physical_gpu': 3, 'egl_device_index': 0,
            'timeout_seconds': 600, 'total_render_cap': 32, 'action_vectors_executed': 0, 'stage_calls': 0})
        import random
        import numpy as np
        import torch
        sys.path.insert(0, str(root / 'third_party/libero_pro'))
        import mujoco
        from robosuite.utils.binding_utils import MjSim, MjRenderContext, MjRenderContextOffscreen
        guard.install(mujoco, MjSim)
        context_observer = ModelFirstContextObserver(torch.cuda.is_initialized, emit)
        context_observer.install(MjRenderContext)
        egl_module = sys.modules['robosuite.renderers.context.egl_context']
        lifetime = ContextLifetime(MjRenderContextOffscreen, egl_module.EGL, context_observer, emit)
        lifetime.install()
        from libero.libero.envs import OffScreenRenderEnv
        for item in dependencies:
            path = Path(importlib.import_module(item['module']).__file__).resolve()
            require(path == Path(item['path']).resolve() and digest(path) == item['sha256'], 'loaded dependency source differs')
        emit({'event': 'dependency_sources', 'files': {item['module']: item['sha256'] for item in dependencies}})
        init_states = torch.load(task['init_path'], map_location='cpu', weights_only=False)
        init_row = np.ascontiguousarray(np.asarray(init_states[0], dtype=np.float64))
        require(init_row.shape == (110,) and hashlib.sha256(init_row.tobytes()).hexdigest() == row['init_row_sha256'],
                'loaded init row differs')
        def factory():
            return OffScreenRenderEnv(bddl_file_name=task['bddl_path'], camera_heights=128, camera_widths=128,
                camera_depths=True, camera_names=['agentview', 'robot0_eye_in_hand'], renderer='mujoco')
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
        scene_rng = lambda: isolated_scene_cpu_rng(random, np, torch, emit)
        evidence = workflow(factory, init_row, guard, emit, load_policy, predict_once, context_observer, scene_rng, lifetime)
        require(context_observer.context_creation_records and
            all(record['model_loaded_before'] and record['cuda_initialized_before'] and record['completed']
                for record in context_observer.context_creation_records), 'model-first context observation incomplete')
        require(prediction_calls == 1 and guard.blocked_integrations == 0, 'scope counts differ')
        evidence.update(schema=SCHEMA, resource_id=contract['resource_id'], diagnostic_only=True, task_success=None,
            camera_render_calls=guard.renders, mj_step1_calls=guard.step1, mj_forward_calls=guard.forwards,
            mj_step_or_mj_step2_calls=0, action_vectors_executed=0, stage_calls=0, dino_model_loads=0,
            predict_unguided_invocations=prediction_calls, elapsed_seconds=time.monotonic() - started)
        with (output / 'context-lifetime-evidence.json').open('x') as stream:
            json.dump(evidence, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
        emit({'event': 'completed', **evidence})
        return 0
    except BaseException as exc:
        emit({'event': 'failed', 'exception_type': type(exc).__name__, 'elapsed_seconds': time.monotonic() - started,
            'camera_render_calls': guard.renders, 'mj_step1_calls': guard.step1, 'mj_forward_calls': guard.forwards,
            'refused_integration_calls': guard.blocked_integrations, 'prediction_calls_started': prediction_calls})
        raise
    finally:
        if lifetime is not None:
            lifetime.restore()
        if context_observer is not None:
            context_observer.restore()
        guard.restore()
        signal.alarm(0)


if __name__ == '__main__':
    raise SystemExit(main())
