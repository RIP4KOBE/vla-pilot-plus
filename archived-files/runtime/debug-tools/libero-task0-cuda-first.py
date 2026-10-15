#!/usr/bin/env python3
"""CUDA-first variant of the frozen loader-boundary diagnostic; no actions or predictions."""
import argparse
import builtins
from contextlib import contextmanager
import faulthandler
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

SCHEMA = 'qd-ed-task0-cuda-first-contract-v1'
PROTOCOL = 'experiments/iteration_001_execution_intent/gpu3-cuda-first-diagnostic.md'
HELPER_SHA256 = '82981d32eaf709ac3c7e4232749b92baeb86994fa98bdd49c81347819d715e70'
helper_path = Path(__file__).with_name('libero-task0-render-model.py')
if hashlib.sha256(helper_path.read_bytes()).hexdigest() != HELPER_SHA256:
    raise RuntimeError('validated scene/model helper changed')
spec = importlib.util.spec_from_file_location('validated_scene_model_helper', helper_path)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
require, digest, phase = helper.require, helper.digest, helper.phase
BOUNDARIES = ('production_imports', 'cuda_identity_seed', 'internal_get_text_encoder',
    'internal_constructor_reset', 'from_pretrained', 'policy_to', 'policy_eval',
    'policy_post_init', 'policy_reset')
LOADER_SOURCES = {
    'scripts.maniskill_model': 'third_party/rdt/scripts/maniskill_model.py',
    'models.multimodal_encoder.t5_encoder': 'third_party/rdt/models/multimodal_encoder/t5_encoder.py',
    'models.multimodal_encoder.siglip_encoder': 'third_party/rdt/models/multimodal_encoder/siglip_encoder.py',
    'models.rdt_runner': 'third_party/rdt/models/rdt_runner.py',
}


@contextmanager
def internal_hooks(invoke, verify_module, import_owner=builtins):
    """Install on the original lazy import's return, never import a model early."""
    original_import = import_owner.__import__
    originals = []
    installed = False

    def intercept(*args, **kwargs):
        nonlocal installed
        result = original_import(*args, **kwargs)
        name = args[0] if args else kwargs.get('name')
        if name == 'scripts.maniskill_model':
            require(not installed, 'internal loader hooks installed twice')
            verify_module(result)
            cls = result.RoboticDiffusionTransformerModel
            for method, boundary in [('get_text_encoder', 'internal_get_text_encoder'),
                                     ('reset', 'internal_constructor_reset')]:
                original = getattr(cls, method)
                def wrapped(*call_args, _original=original, _boundary=boundary, **call_kwargs):
                    return invoke(_boundary, _original, *call_args, **call_kwargs)
                originals.append((cls, method, original, wrapped))
                setattr(cls, method, wrapped)
            installed = True
            # The one targeted import is now complete; all remaining imports are original.
            if import_owner.__import__ is intercept:
                import_owner.__import__ = original_import
        return result

    import_owner.__import__ = intercept
    try:
        yield
        require(installed, 'original maniskill_model import was not observed')
    finally:
        if import_owner.__import__ is intercept:
            import_owner.__import__ = original_import
        for cls, name, original, wrapped in reversed(originals):
            if getattr(cls, name) is wrapped:
                setattr(cls, name, original)


def zero_compute(counters):
    require(isinstance(counters, dict) and all(name in counters for name in
        ('model_forward_calls', 'text_encoder_forward_calls', 'vision_encoder_forward_calls', 'denoising_invocations')),
        'production compute counters missing')
    require(all((type(value) is int and value == 0) or (isinstance(value, list) and not value)
                for value in counters.values()), 'unexpected model/encoder/reward compute')


def load_in_phases(boundary, guard, emit, import_policy, cuda_identity_seed, config,
                   verify_module, import_owner=builtins):
    """Preserve the prior loader's calls/arguments and observe only successful returns."""
    counts = {name: 0 for name in BOUNDARIES}
    policy = None
    def invoke(name, original, *args, **kwargs):
        nonlocal policy
        require(counts[name] == 0, 'loader operation invoked more than once: ' + name)
        counts[name] += 1
        previous = guard.phase
        guard.phase = name
        try:
            with phase(emit, name):
                result = original(*args, **kwargs)
            if name == 'from_pretrained':
                policy = result
            counters = getattr(policy, '_episode_compute', None) if policy is not None else None
            if counters is not None:
                snapshot = {key: list(value) if isinstance(value, list) else value for key, value in counters.items()}
                zero_compute(snapshot)
                emit({'event': 'policy_compute', 'phase': name, 'compute': snapshot})
            boundary(name)
            return result
        finally:
            guard.phase = previous
    policy_class = invoke('production_imports', import_policy)
    invoke('cuda_identity_seed', cuda_identity_seed)
    with internal_hooks(invoke, verify_module, import_owner):
        policy = invoke('from_pretrained', policy_class.from_pretrained, config['pretrained_path'],
            num_inference_steps=config['num_inference_steps'], vision_encoder=config['vision_encoder'],
            text_encoder=config['text_encoder'], weight_variant=config['weight_variant'],
            control_frequency=int(config['control_frequency']))
    require(all(counts[name] == 1 for name in ('internal_get_text_encoder', 'internal_constructor_reset')),
            'internal constructor hook counts differ')
    invoke('policy_to', policy.to, 'cuda:0')
    invoke('policy_eval', policy.eval)
    invoke('policy_post_init', policy.post_init, adapter=None, postprocessor=lambda value: value,
           sample_batch_size=1, policy_config=config)
    invoke('policy_reset', policy.reset)
    counters = policy.get_episode_compute_counters()
    zero_compute(counters)
    require(all(value == 1 for value in counts.values()), 'loader call counts differ')
    emit({'event': 'model_loaded', 'call_counts': counts, 'compute': counters})
    return {'call_counts': counts, 'compute': counters}


def workflow(factory, init_row, guard, emit, loader):
    env = None
    successful = []
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
        def render_boundary(name, cameras):
            guard.phase = 'after_' + name
            require(guard.limit - guard.renders >= len(cameras), 'insufficient total render budget for required boundary')
            emit({'event': 'boundary_enter', 'boundary': name, 'sim_time': float(env.sim.data.time)})
            require(float(env.sim.data.time) == initial_time, 'scene time changed before boundary')
            for camera, size, depth in cameras:
                env.sim.render(camera_name=camera, width=size, height=size, depth=depth)
            require(float(env.sim.data.time) == initial_time, 'scene time changed after boundary')
            emit({'event': 'boundary_exit', 'boundary': name, 'sim_time': float(env.sim.data.time)})
        render_boundary('baseline', helper.CAMERAS)
        def boundary(name):
            require(len(successful) < len(BOUNDARIES) and name == BOUNDARIES[len(successful)],
                    'loader boundary order differs')
            render_boundary(name, [('agentview', 128, True)])
            successful.append(name)
        evidence = loader(boundary)
        require(tuple(successful) == BOUNDARIES, 'loader boundaries incomplete')
        return {**evidence, 'successful_boundaries': successful, 'explicit_render_calls': 12,
                'sim_time_after_init': initial_time, 'sim_time_final': float(env.sim.data.time)}
    finally:
        if env is not None:
            guard.phase = 'close'
            with phase(emit, 'close'):
                env.close()


class CudaFirstObserver:
    """Observe the original render-context constructor without native context queries."""
    def __init__(self, cuda, emit):
        self.cuda, self.emit = cuda, emit
        self.early_cuda_init_calls = 0
        self.context_creation_records = []
        self._binding = None

    def early_init(self):
        require(self.early_cuda_init_calls == 0, 'early CUDA initialization invoked twice')
        self.early_cuda_init_calls += 1
        before = bool(self.cuda.is_initialized())
        self.emit({'event': 'early_cuda_init_enter', 'is_initialized': before})
        with phase(self.emit, 'early_cuda_init'):
            self.cuda.init()
        after = bool(self.cuda.is_initialized())
        self.emit({'event': 'early_cuda_init_exit', 'is_initialized_before': before, 'is_initialized_after': after})
        require(after, 'early CUDA initialization did not initialize CUDA')

    def install(self, context_class):
        require(self._binding is None, 'render-context observer installed twice')
        original = context_class.__init__
        def observed(instance, *args, **kwargs):
            initialized = bool(self.cuda.is_initialized())
            record = {'index': len(self.context_creation_records) + 1,
                      'is_initialized_before': initialized, 'completed': False}
            self.context_creation_records.append(record)
            self.emit({'event': 'context_creation_enter', **record})
            require(initialized, 'render context creation preceded CUDA initialization')
            try:
                result = original(instance, *args, **kwargs)
            except BaseException as exc:
                self.emit({'event': 'context_creation_exception', **record, 'exception_type': type(exc).__name__})
                raise
            record['completed'] = True
            self.emit({'event': 'context_creation_exit', **record})
            return result
        self._binding = (context_class, original, observed)
        context_class.__init__ = observed

    def restore(self):
        if self._binding is not None:
            cls, original, observed = self._binding
            if cls.__init__ is observed:
                cls.__init__ = original
            self._binding = None


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
    source_hashes = {row['path']: row['sha256'] for row in source_records}
    for row in source_records:
        source = (root / row['path']).resolve()
        require(source.is_relative_to(root) and digest(source) == row['sha256'], 'source file fingerprint mismatch')
    dependencies = contract['dependency_sources']
    require({row['module'] for row in dependencies} == helper.DEPENDENCY_MODULES and len(dependencies) == len(helper.DEPENDENCY_MODULES),
            'dependency source set differs from static scene contract')
    for row in dependencies:
        require(Path(row['path']).is_absolute() and digest(row['path']) == row['sha256'], 'dependency fingerprint mismatch')
    sys.path.insert(0, str(root / 'scripts'))
    sys.path.insert(0, str(root))
    import qd_ed_policy_native_probe as native
    required_sources = native.runner.REQUIRED_CODE | {native.SCRIPT_RELATIVE, PROTOCOL} | set(LOADER_SOURCES.values())
    require(required_sources <= set(source_hashes), 'required source/protocol fingerprints missing')
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
    events = output / 'cuda_first_events.jsonl'
    with events.open('x'):
        pass
    def emit(record):
        with events.open('a') as stream:
            stream.write(json.dumps({'monotonic_seconds': time.monotonic(), **record}, sort_keys=True, allow_nan=False) + '\n')
        helper.validate_frame(record)
    def deadline(_signum, _frame):
        raise TimeoutError('cuda-first diagnostic reached 600-second deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(600)
    faulthandler.enable(all_threads=True)
    sys.addaudithook(helper.audit_network)
    started = time.monotonic()
    guard = helper.RenderModelGuard(emit, 32)
    cuda_observer = None
    try:
        emit({'event': 'started', 'resource_id': contract['resource_id'], 'source_commit': contract['source_commit'],
            'contract_sha256': args.contract_sha256, 'script_sha256': digest(__file__),
            'scene_model_helper_sha256': HELPER_SHA256, 'static_helper_sha256': helper.STATIC_SHA256,
            'physical_gpu': 3, 'egl_device_index': 0, 'timeout_seconds': 600, 'total_render_cap': 32,
            'action_vectors_executed': 0, 'stage_calls': 0, 'predict_unguided_invocations': 0})
        import random
        import numpy as np
        import torch
        sys.path.insert(0, str(root / 'third_party/libero_pro'))
        import mujoco
        from robosuite.utils.binding_utils import MjSim, MjRenderContext
        guard.install(mujoco, MjSim)
        cuda_observer = CudaFirstObserver(torch.cuda, emit)
        cuda_observer.install(MjRenderContext)
        from libero.libero.envs import OffScreenRenderEnv
        for item in dependencies:
            module = sys.modules.get(item['module'])
            require(module is not None, 'expected scene dependency not loaded')
            path = Path(module.__file__).resolve()
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
        def import_policy():
            from core.rdt_policy_steer import RDTSteer
            return RDTSteer
        def cuda_identity_seed():
            require(torch.cuda.device_count() == 1, 'expected one visible CUDA device')
            properties = torch.cuda.get_device_properties(0)
            normalize = lambda value: str(value).lower().removeprefix('gpu-')
            require(normalize(properties.uuid) == normalize(runtime['gpu_mapping']['uuid']), 'CUDA UUID differs from GPU3 runtime')
            emit({'event': 'cuda_identity', 'torch_logical_device': 0, 'torch_uuid': str(properties.uuid)})
            random.seed(native.SYNTHETIC_SEED)
            np.random.seed(native.SYNTHETIC_SEED)
            torch.manual_seed(native.SYNTHETIC_SEED)
            torch.cuda.manual_seed_all(native.SYNTHETIC_SEED)
        def verify_module(imported):
            require(imported is sys.modules.get('scripts.maniskill_model'), 'unexpected loader import result')
            for module_name, relative in LOADER_SOURCES.items():
                module = sys.modules.get(module_name)
                require(module is not None, 'expected natural loader dependency missing')
                path = Path(module.__file__).resolve()
                require(path == (root / relative).resolve() and digest(path) == source_hashes[relative],
                        'loaded model dependency differs')
            emit({'event': 'loader_sources', 'files': {name: source_hashes[path] for name, path in LOADER_SOURCES.items()}})
        def loader(boundary):
            return load_in_phases(boundary, guard, emit, import_policy, cuda_identity_seed, config, verify_module)
        cuda_observer.early_init()
        evidence = workflow(factory, init_row, guard, emit, loader)
        require(cuda_observer.early_cuda_init_calls == 1 and cuda_observer.context_creation_records and
                all(record['is_initialized_before'] and record['completed']
                    for record in cuda_observer.context_creation_records), 'CUDA/context observation incomplete')
        require(guard.blocked_integrations == 0, 'integration attempted')
        evidence.update(schema=SCHEMA, resource_id=contract['resource_id'], diagnostic_only=True, task_success=None,
            camera_render_calls=guard.renders, mj_step1_calls=guard.step1, mj_forward_calls=guard.forwards,
            mj_step_or_mj_step2_calls=0, action_vectors_executed=0, stage_calls=0, dino_model_loads=0,
            predict_unguided_invocations=0, policy_model_loads=1, synthetic_seed=native.SYNTHETIC_SEED,
            early_cuda_init_calls=cuda_observer.early_cuda_init_calls,
            context_creation_records=cuda_observer.context_creation_records,
            elapsed_seconds=time.monotonic() - started)
        with (output / 'cuda-first-evidence.json').open('x') as stream:
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
        if cuda_observer is not None:
            cuda_observer.restore()
        guard.restore()
        signal.alarm(0)


if __name__ == '__main__':
    raise SystemExit(main())
