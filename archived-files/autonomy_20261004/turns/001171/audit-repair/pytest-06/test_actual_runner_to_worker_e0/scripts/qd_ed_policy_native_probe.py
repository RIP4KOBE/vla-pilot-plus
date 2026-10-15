#!/usr/bin/env python3
"""Accounted, synthetic B1 RDT inference diagnostic with no simulator instance.

Uses the production model loader, observation processor, text encoder and
_predict_unguided method. Importing their real type dependencies may import
gymnasium; no environment, Stage client, renderer or action executor is created.
This isolates B1 inference, not the prior guided-to-unguided transition.
"""
from __future__ import annotations

import argparse
import contextlib
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import uuid

import qd_ed_final_runner as runner


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_RELATIVE = 'scripts/qd_ed_policy_native_probe.py'
SCHEMA = 'qd-ed-policy-native-probe-v1'
SYNTHETIC_SEED = 193735
SYNTHETIC_TASK = 'Move the synthetic object toward the synthetic target.'
SCOPE = {
    'input_kind': 'deterministic_synthetic_images_and_proprioception',
    'prediction_path': 'RDTSteer._predict_unguided',
    'batch_size': 1, 'predict_unguided_invocations': 1,
    'environment_instances': 0, 'simulation_steps': 0,
    'action_vectors_executed': 0, 'stage_calls': 0,
    'guided_warmup_calls': 0, 'scientific_episode': False,
    'limitation': 'B1-only diagnostic cannot establish guided-transition or EGL causality',
    'gym_type_imports_allowed': True,
}


def policy_configuration(root, profiles):
    """Resolve only the exact frozen policy leaf values, without Hydra/env init."""
    defaults = runner.read_state(Path(root) / 'configs/policy.yaml')['rdt']
    resolved = []
    for profile in profiles['profiles'].values():
        values = profile['static_override_values']
        runner.require(values.get('policy.type') == 'rdt' and values.get('device') in {'cuda', 'cuda:0'},
                       'native probe requires the frozen CUDA RDT policy')
        config = dict(defaults)
        for key, value in values.items():
            if key.startswith('policy.rdt.'):
                name = key.removeprefix('policy.rdt.')
                runner.require(name in config and '.' not in name, 'unrecognized frozen RDT configuration')
                config[name] = value
        resolved.append(config)
    runner.require(resolved and all(config == resolved[0] for config in resolved),
                   'profile RDT model configurations differ')
    config = resolved[0]
    for name in ('pretrained_path', 'text_encoder', 'vision_encoder'):
        runner.require(Path(config[name]).is_absolute() and Path(config[name]).exists(),
                       'native probe requires existing local model/encoder paths')
    runner.require(config['fail_on_zero_language_embedding'] is True,
                   'native probe must use a real nonzero text encoding')
    return config


def validate_inputs(plan_path, root):
    plan, profiles, runtime = runner.validate_plan(plan_path, root=root)
    records = {item['path']: item for item in plan['code_files']}
    runner.require(SCRIPT_RELATIVE in records and
                   records[SCRIPT_RELATIVE]['sha256'] == runner.digest(Path(__file__)),
                   'native diagnostic script is not included in the frozen plan')
    frozen = runtime['frozen_stage_provider']
    runner.require(frozen.get('backend') == 'codex_cli', 'native diagnostic expects the frozen Codex contract')
    # Verify the unused provider's public binding only. Do not invoke Codex,
    # inspect account credentials, or make a provider/network request.
    runner.stage_overrides(runtime)
    runner.require(runner.digest(frozen['cli_path']) == frozen['cli_sha256'],
                   'frozen Codex executable fingerprint changed')
    return plan, runtime, policy_configuration(root, profiles)


def append_phase(output, name, event, **details):
    record = {'phase': name, 'event': event, 'time_unix': time.time(),
              'monotonic_seconds': time.monotonic(), **details}
    with (Path(output) / 'phase-boundaries.jsonl').open('a') as stream:
        stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


@contextlib.contextmanager
def phase(output, name, **details):
    append_phase(output, name, 'enter', **details)
    try:
        yield
    except BaseException as exc:
        append_phase(output, name, 'python_exception', exception_type=type(exc).__name__)
        raise
    else:
        append_phase(output, name, 'exit')


def audit_no_network_or_simulator(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.bind'}:
        raise RuntimeError('Network operations are disabled in the native diagnostic')
    if event == 'import' and str(args[0]).split('.')[0] in {'mujoco', 'mujoco_py', 'robosuite', 'libero'}:
        raise RuntimeError('Simulator imports are disabled in the native diagnostic')


def install_phase_wrappers(policy, output):
    """Trace original bound methods without changing their arguments or results."""
    for name in ('_get_lang_embed', '_counted_encode_inputs', '_counted_dit', '_counted_scheduler_step'):
        original = getattr(policy, name)
        sequence = [0]
        def traced(*args, _original=original, _name=name, _sequence=sequence, **kwargs):
            _sequence[0] += 1
            details = {'call_index': _sequence[0]}
            if args and hasattr(args[0], 'shape'):
                details['first_argument_shape'] = list(args[0].shape)
            with phase(output, _name, **details):
                return _original(*args, **kwargs)
        setattr(policy, name, traced)


def synthetic_observation(np):
    y, x = np.indices((256, 256), dtype=np.int32)
    agent = np.stack(((x + y) % 256, (2 * x + 3 * y) % 256, (5 * x + y) % 256), axis=-1).astype(np.uint8)
    wrist = np.flip(agent, axis=1).copy()
    return {'agentview_image': agent, 'robot0_eye_in_hand_image': wrist,
            'robot0_joint_pos': np.array([0., -0.2, 0.1, -1.5, 0.2, 1.1, 0.3], dtype=np.float32),
            'robot0_gripper_qpos': np.array([0.02, -0.02], dtype=np.float32), 'task': SYNTHETIC_TASK}


def child_probe(contract_path, output, resource_id):
    runner.require(os.environ.get('QD_ED_NATIVE_PARENT_PID') == str(os.getppid()),
                   'native child requires an admitted parent')
    runner.require(os.environ.get('QD_ED_NATIVE_RESOURCE_ID') == resource_id,
                   'native child resource identity mismatch')
    runner.require(runner.digest(contract_path) == os.environ.get('QD_ED_NATIVE_CONTRACT_SHA256'),
                   'native child contract changed')
    contract = runner.read_json(contract_path)
    runner.require(contract['resource_id'] == resource_id and contract['scope'] == SCOPE,
                   'native child scope/resource mismatch')
    runner.require(Path(output).resolve() == Path(contract['output_dir']).resolve(), 'native child output mismatch')
    runner.require(runner.digest(contract['plan_path']) == contract['plan_sha256'] and
                   runner.digest(contract['runtime_manifest_path']) == contract['runtime_manifest_sha256'] and
                   runner.digest(Path(__file__)) == contract['source_script_sha256'],
                   'native child frozen inputs changed')
    runtime = runner.read_json(contract['runtime_manifest_path'])
    physical_gpu = runner.runtime_gpu(runtime)
    mapping = runtime['gpu_mapping']
    runner.require(physical_gpu == contract['physical_gpu'] and
                   os.environ.get('CUDA_VISIBLE_DEVICES') == str(physical_gpu) and
                   os.environ.get('CUDA_DEVICE_ORDER') == 'PCI_BUS_ID', 'native child GPU environment mismatch')
    runner.require(os.environ.get('HF_HUB_OFFLINE') == '1' and os.environ.get('TRANSFORMERS_OFFLINE') == '1',
                   'native diagnostic must be offline')
    runner.gpu_admission(physical_gpu=physical_gpu, expected_uuid=mapping['uuid'])
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    faulthandler.enable(file=sys.stderr, all_threads=True)
    sys.addaudithook(audit_no_network_or_simulator)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    with phase(output, 'import_production_model'):
        import random
        import numpy as np
        import torch
        from core.rdt_policy_steer import RDTSteer
        from core.rdt_libero_obs_processor import RDTLiberoObsProcessor
    with phase(output, 'verify_cuda_identity'):
        runner.require(torch.cuda.device_count() == 1, 'native diagnostic requires one visible CUDA device')
        properties = torch.cuda.get_device_properties(0)
        normalize = lambda value: str(value).lower().removeprefix('gpu-')
        runner.require(normalize(properties.uuid) == normalize(mapping['uuid']), 'native CUDA UUID differs from frozen GPU')
    random.seed(SYNTHETIC_SEED)
    np.random.seed(SYNTHETIC_SEED)
    torch.manual_seed(SYNTHETIC_SEED)
    torch.cuda.manual_seed_all(SYNTHETIC_SEED)
    config = contract['policy_configuration']
    with phase(output, 'load_frozen_rdt_t5_siglip'):
        policy = RDTSteer.from_pretrained(
            config['pretrained_path'], num_inference_steps=config['num_inference_steps'],
            vision_encoder=config['vision_encoder'], text_encoder=config['text_encoder'],
            weight_variant=config['weight_variant'], control_frequency=int(config['control_frequency']))
        policy.to('cuda:0')
        policy.eval()
        # post_init permits None because the unguided method does not access an
        # adapter. It sets the same policy flags and observation processor as main.
        policy.post_init(adapter=None, postprocessor=lambda value: value, sample_batch_size=1,
                         policy_config=config)
        policy.reset()
    install_phase_wrappers(policy, output)
    with phase(output, 'process_synthetic_observation'):
        observation = synthetic_observation(np)
        runner.require(isinstance(policy._obs_processor, RDTLiberoObsProcessor), 'production observation processor missing')
        converted = policy._obs_processor.process(observation)
    with phase(output, 'encode_synthetic_task'):
        text_embed = policy._get_lang_embed(converted.task)
    with phase(output, 'predict_unguided_b1', batch_size=1):
        raw = policy._predict_unguided(converted.state_128, converted.state_mask_128,
                                      converted.images, text_embed, B=1)
    with phase(output, 'synchronize_and_inspect_raw_prediction'):
        torch.cuda.synchronize(0)
        array = raw.detach().cpu().numpy()
        runner.require(list(array.shape) == [1, 64, 128] and bool(np.isfinite(array).all()),
                       'native prediction is nonfinite or has an unexpected shape')
        evidence = {
            'schema': SCHEMA, 'resource_id': resource_id, **SCOPE,
            'physical_gpu': physical_gpu, 'torch_logical_device': 0,
            'torch_uuid': str(properties.uuid), 'torch_device_name': properties.name,
            'cuda_visible_devices': os.environ['CUDA_VISIBLE_DEVICES'],
            'cuda_device_order': os.environ['CUDA_DEVICE_ORDER'],
            'torch_version': str(torch.__version__), 'synthetic_seed': SYNTHETIC_SEED,
            'raw_prediction_shape': list(array.shape), 'raw_prediction_dtype': str(array.dtype),
            'raw_prediction_finite': True, 'raw_prediction_sha256': hashlib.sha256(array.tobytes()).hexdigest(),
            'compute': policy.get_episode_compute_counters(),
            'loaded_gym_type_packages': sorted(name for name in ('gym', 'gymnasium') if name in sys.modules),
            'simulator_modules_present': sorted(name for name in ('mujoco', 'mujoco_py', 'robosuite', 'libero') if name in sys.modules),
            'num_inference_steps': policy._num_inference_steps,
        }
        runner.durable_json(Path(output) / 'probe-evidence.json', evidence)
    append_phase(output, 'diagnostic_complete', 'exit')
    return evidence


def validate_evidence(evidence, contract, runtime):
    runner.require(evidence.get('schema') == SCHEMA and evidence.get('resource_id') == contract['resource_id'],
                   'native evidence identity mismatch')
    runner.require(all(evidence.get(key) == value for key, value in SCOPE.items()), 'native evidence scope mismatch')
    physical_gpu = runner.runtime_gpu(runtime)
    normalize = lambda value: str(value).lower().removeprefix('gpu-')
    runner.require(evidence.get('physical_gpu') == physical_gpu and evidence.get('torch_logical_device') == 0 and
                   evidence.get('cuda_visible_devices') == str(physical_gpu) and
                   evidence.get('cuda_device_order') == 'PCI_BUS_ID' and
                   normalize(evidence.get('torch_uuid')) == normalize(runtime['gpu_mapping']['uuid']),
                   'native evidence GPU identity mismatch')
    runner.require(evidence.get('raw_prediction_shape') == [1, 64, 128] and
                   evidence.get('raw_prediction_finite') is True and evidence.get('simulator_modules_present') == [],
                   'native inference evidence incomplete or simulator imported')
    counters = evidence.get('compute', {})
    for name in ('model_forward_calls', 'vision_encoder_forward_calls', 'text_encoder_forward_calls'):
        runner.require(type(counters.get(name)) is int and counters[name] > 0, 'native model/encoder calls missing')
    runner.require(counters.get('model_batch_rows') == counters['model_forward_calls'] and
                   counters.get('denoising_invocations') == 1, 'native evidence is not one B1 denoising invocation')


def last_phase_boundary(output):
    """A native abort may leave a partial log line; accounting must still finish."""
    path = Path(output) / 'phase-boundaries.jsonl'
    if not path.exists():
        return None
    last = None
    for line in path.read_text(errors='replace').splitlines():
        try:
            last = json.loads(line)
        except (ValueError, TypeError):
            return {'last_complete_boundary': last, 'incomplete_or_invalid_phase_line': True}
    return last


def run_probe(plan_path, *, root=ROOT, timeout_seconds=600):
    root = Path(root).resolve()
    plan_path = Path(plan_path).resolve()
    runner.require(type(timeout_seconds) is int and 0 < timeout_seconds <= 600,
                   'native diagnostic timeout must be 1..600 seconds')
    with runner.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
        plan, runtime, config = validate_inputs(plan_path, root)
        state = runner.read_state(root / 'research-state.yaml')
        physical_gpu = runner.runtime_gpu(runtime, state)
        events = runner.read_events(root / 'data/attempt-ledger.jsonl')
        resources = runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
        timeout = runner.check_budget(state, events,
            {'budget_bucket': 'recovery', 'timeout_seconds': timeout_seconds}, resources,
            runner.read_events(root / 'data/gpu-hour-reservation-ledger.jsonl'), physical_gpu=physical_gpu)
        admission = runner.gpu_admission(physical_gpu=physical_gpu, expected_uuid=runtime['gpu_mapping']['uuid'])
        resource_id = plan['run_name'] + f'__gpu{physical_gpu}_native_b1__' + uuid.uuid4().hex[:12]
        output = runner.owned(Path(plan['artifact_root']) / 'runtime/native_probes' / resource_id, plan['artifact_root'])
        output.mkdir(parents=True, exist_ok=False)
        base = {'resource_id': resource_id, 'kind': 'policy_native_diagnostic', 'physical_gpu': physical_gpu,
                'output_dir': str(output), 'source_commit': plan['source_commit'],
                'plan_sha256': runner.digest(plan_path), 'runtime_manifest_sha256': plan['runtime_manifest_sha256'],
                'runtime_inventory_sha256': plan['runtime_inventory_sha256'],
                'source_script_sha256': runner.digest(Path(__file__)), 'scope': SCOPE}
        contract = {**base, 'plan_path': str(plan_path), 'runtime_manifest_path': plan['runtime_manifest_path'],
                    'policy_configuration': config, 'synthetic_seed': SYNTHETIC_SEED, 'synthetic_task': SYNTHETIC_TASK}
        contract_path = output / 'diagnostic-contract.json'
        runner.durable_json(contract_path, contract)
        process, started, dispatched = None, None, False
        event, details = 'aborted', {}
        runner.append_healthcheck_event(root, {**base, 'event': 'reserved', 'time_unix': time.time(), 'admission': admission})
        try:
            runner.runtime_gpu(runtime, runner.read_state(root / 'research-state.yaml'))
            runner.gpu_admission(physical_gpu=physical_gpu, expected_uuid=runtime['gpu_mapping']['uuid'])
            runner.require(runner.digest(plan_path) == base['plan_sha256'] and
                           runner.digest(plan['runtime_manifest_path']) == base['runtime_manifest_sha256'],
                           'native diagnostic inputs changed before dispatch')
            env = runner.child_environment(runtime)
            env.update(QD_ED_NATIVE_PARENT_PID=str(os.getpid()), QD_ED_NATIVE_RESOURCE_ID=resource_id,
                       QD_ED_NATIVE_CONTRACT_SHA256=runner.digest(contract_path),
                       HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', DISABLE_SAFETENSORS_CONVERSION='1',
                       PYTHONFAULTHANDLER='1', PYTHONDONTWRITEBYTECODE='1')
            command = [str(runner.PYTHON), str(Path(__file__).resolve()), '_child',
                       '--contract', str(contract_path), '--output', str(output), '--resource-id', resource_id]
            runner.durable_json(output / 'command.json', {'argv': command, 'scope': SCOPE,
                'environment_public': {name: env[name] for name in ('CUDA_VISIBLE_DEVICES', 'CUDA_DEVICE_ORDER',
                    'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'PYTHONFAULTHANDLER')}})
            runner.append_healthcheck_event(root, {**base, 'event': 'dispatched', 'time_unix': time.time(), 'timeout_seconds': timeout})
            dispatched, started = True, time.monotonic()
            with (output / 'native-probe.log').open('w') as log:
                process = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    ticks = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
                except OSError:
                    ticks = None
                runner.durable_json(output / 'process.json', {'pid': process.pid, 'resource_id': resource_id,
                    'proc_start_ticks': ticks, 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()})
                code = runner.wait_exclusively(process, timeout, physical_gpu=physical_gpu)
            details['child_exit_code'] = code
            if code < 0:
                details['native_signal'] = signal.Signals(-code).name
            runner.require(code == 0, f'native diagnostic child exited with code {code}')
            evidence = runner.read_json(output / 'probe-evidence.json')
            validate_evidence(evidence, contract, runtime)
            details.update(evidence_path=str(output / 'probe-evidence.json'),
                           evidence_sha256=runner.digest(output / 'probe-evidence.json'))
            event = 'completed'
        except BaseException as exc:
            details['reason'] = str(exc) if isinstance(exc, runner.GateError) else type(exc).__name__
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
        finally:
            runner.terminate_owned(process)
            elapsed = time.monotonic() - started if dispatched else 0.0
            terminal = {**base, **details, 'event': event, 'time_unix': time.time(),
                        'gpu_process_wall_seconds': elapsed,
                        'last_phase_boundary': last_phase_boundary(output),
                        'measurement': f'exclusive GPU{physical_gpu} child wall time including startup, inference and cleanup'}
            runner.append_healthcheck_event(root, terminal)
            runner.durable_json(output / 'healthcheck-result.json', terminal)
        return terminal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', allow_abbrev=False)
    run.add_argument('--plan', type=Path, required=True)
    run.add_argument('--timeout-seconds', type=int, default=600)
    child = commands.add_parser('_child', help=argparse.SUPPRESS, allow_abbrev=False)
    child.add_argument('--contract', type=Path, required=True)
    child.add_argument('--output', type=Path, required=True)
    child.add_argument('--resource-id', required=True)
    args = parser.parse_args(argv)
    def interrupted(signum, frame):
        raise KeyboardInterrupt('native diagnostic interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    if args.command == '_child':
        child_probe(args.contract, args.output, args.resource_id)
        return 0
    result = run_probe(args.plan, timeout_seconds=args.timeout_seconds)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['event'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
