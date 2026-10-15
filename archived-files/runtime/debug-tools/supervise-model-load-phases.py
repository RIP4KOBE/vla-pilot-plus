"""Account one GPU3 model-load-phases diagnostic under the shared research lock."""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
ARTIFACT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
sys.path.insert(0, str(ROOT / 'scripts'))
import qd_ed_final_runner as r
import qd_ed_available_gpu_queue as q
import qd_ed_policy_native_probe as native

SCRIPT = ARTIFACT / 'runtime/debug-tools/libero-task0-model-load-phases.py'
EXPECTED_SCRIPT = '741c087a21228b5dc5f49801c3734b93ed690760a3731eb5c8b6b3138a0775a4'
RUNTIME = ARTIFACT / 'runtime/gpu3-render-diagnostic/runtime-manifest.json'
SEEDS = ROOT / 'data/frozen-seed-plan.json'
PROTOCOL = ROOT / 'experiments/iteration_001_execution_intent/gpu3-model-load-phases-diagnostic.md'
FOLDER = ARTIFACT / 'runtime/gpu3-model-load-phases-diagnostic'
FOLDER.mkdir(parents=True, exist_ok=True)
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

def kernel_rows(extra):
    done = subprocess.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'json', *extra],
                          capture_output=True, text=True, timeout=10, check=True)
    return [json.loads(line) for line in done.stdout.splitlines() if line.startswith('{')]

with r.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
    q.no_unfinished(ROOT)
    with r.locked(ROOT / 'data/qd-ed-state.lock'):
        r.sync_state_from_journal(ROOT, r.read_events(ROOT / 'data/attempt-ledger.jsonl'))
    state = r.read_state(ROOT / 'research-state.yaml')
    r.require(q.candidate_indices(state) == [3], 'GPU3-only authorization required')
    runtime = r.read_json(RUNTIME)
    r.require(r.runtime_gpu(runtime, state) == 3 and runtime['cuda_egl_verified'], 'GPU3 binding missing')
    r.require(r.digest(SCRIPT) == EXPECTED_SCRIPT, 'model-load-phases script changed')
    r.verify_files(runtime['files'], allowed_roots=(ROOT, ARTIFACT))
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    r.require(PROTOCOL.read_bytes() == subprocess.check_output(['git', 'show', source + ':' + str(PROTOCOL.relative_to(ROOT))], cwd=ROOT), 'protocol differs from committed source')
    profiles_path = ROOT / 'configs/qd_ed_final/baseline_profiles.json'
    inventory_path = ROOT / 'data/runtime-inventory.json'
    r.require(r.digest(profiles_path) == '75ba829fc29db71ae31669cd803c24fbe8ea96fe347160539a273f9d73551690', 'frozen profiles changed')
    r.require(r.digest(inventory_path) == '44d456203ca168eec9eddfb6834d54347153b2c859eb1b4fc0dea02c15138b83', 'frozen model inventory changed')
    inventory = r.read_json(inventory_path)
    print(json.dumps({'phase': 'verifying_frozen_model_bytes_cpu_only'}), flush=True)
    r.verify_files(inventory['checkpoint'])
    for encoder in inventory['hf_encoders']:
        r.verify_files(encoder['files'])
        if 'snapshot' in encoder:
            snapshot = Path(encoder['snapshot'])
            r.require({p.resolve() for p in snapshot.parent.iterdir() if p.is_dir()} == {snapshot.resolve()}, 'encoder snapshot set changed')
    r.verify_files([inventory['dinov2']['weights']])
    policy_path = FOLDER / 'policy-configuration.json'
    r.durable_json(policy_path, native.policy_configuration(ROOT, r.read_json(profiles_path)))
    source_paths = {v['path'] for v in r.read_json(ROOT / 'data/qd-ed-gpu3-context-drift-plan.json')['code_files']}
    source_paths |= {str(PROTOCOL.relative_to(ROOT)), 'scripts/qd_ed_policy_native_probe.py',
        'third_party/rdt/scripts/maniskill_model.py', 'third_party/rdt/models/multimodal_encoder/t5_encoder.py',
        'third_party/rdt/models/multimodal_encoder/siglip_encoder.py', 'third_party/rdt/models/rdt_runner.py'}
    source_files = [{'path': p, 'sha256': r.digest(ROOT / p)} for p in sorted(source_paths)]
    resource_id = state['run_name'] + '__gpu3_model_load_phases__' + uuid.uuid4().hex[:12]
    output = FOLDER / resource_id
    output.mkdir(exist_ok=False)
    lib = Path('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages')
    dependencies = [ROOT / 'third_party/libero_pro/libero/libero/envs/env_wrapper.py',
        ROOT / 'third_party/libero_pro/libero/libero/envs/bddl_base_domain.py']
    dependencies += [lib / ('robosuite/' + x) for x in ('environments/base.py', 'environments/robot_env.py',
        'utils/binding_utils.py', 'renderers/context/egl_context.py')]
    modules = ['libero.libero.envs.env_wrapper', 'libero.libero.envs.bddl_base_domain',
        'robosuite.environments.base', 'robosuite.environments.robot_env', 'robosuite.utils.binding_utils',
        'robosuite.renderers.context.egl_context']
    dependency_records = [{'module': m, 'path': str(p), 'sha256': r.digest(p)} for m,p in zip(modules, dependencies)]
    contract = {'schema': 'qd-ed-task0-model-load-phases-contract-v1', 'resource_id': resource_id, 'output_dir': str(output),
        'source_commit': source, 'source_script_sha256': EXPECTED_SCRIPT, 'supervisor_sha256': r.digest(__file__),
        'protocol_sha256': r.digest(PROTOCOL), 'runtime_manifest_path': str(RUNTIME), 'runtime_manifest_sha256': r.digest(RUNTIME),
        'seed_plan_path': str(SEEDS), 'seed_plan_sha256': r.digest(SEEDS),
        'profiles_path': str(profiles_path), 'profiles_sha256': r.digest(profiles_path),
        'runtime_inventory_path': str(inventory_path), 'runtime_inventory_sha256': r.digest(inventory_path),
        'policy_configuration_path': str(policy_path), 'policy_configuration_sha256': r.digest(policy_path),
        'physical_gpu': 3, 'timeout_seconds': 600, 'render_limit': 32, 'explicit_render_calls': 12,
        'dependency_sources': dependency_records, 'source_files': source_files,
        'actions': 0, 'integration_transitions': 0}
    r.durable_json(FOLDER / 'frozen-contract.json', contract)
    windows = {}
    while True:
        r.require(q.candidate_indices(r.read_state(ROOT / 'research-state.yaml')) == [3], 'GPU authorization changed')
        devices = q.inventory()
        q.update_idle_windows(devices, windows, time.monotonic(), 120)
        r.durable_json(FOLDER / 'status.json', {'phase': 'waiting_stable_idle', 'device': devices[3], 'time_unix': time.time()})
        print(json.dumps({'phase': 'waiting', 'idle_seconds': devices[3]['idle_observed_seconds']}), flush=True)
        if q.choose_device(devices, [3], 3):
            break
        time.sleep(30)
    q.reservation_admission(devices[3])
    q.no_unfinished(ROOT)
    state = r.read_state(ROOT / 'research-state.yaml')
    timeout = r.check_budget(state, r.read_events(ROOT / 'data/attempt-ledger.jsonl'),
        {'budget_bucket': 'recovery', 'timeout_seconds': 600}, r.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'),
        r.read_events(ROOT / 'data/gpu-hour-reservation-ledger.jsonl'), physical_gpu=3)
    admission = r.gpu_admission(physical_gpu=3, expected_uuid=runtime['gpu_mapping']['uuid'])
    baseline = kernel_rows(['-n', '1'])
    r.require(len(baseline) == 1, 'kernel baseline missing')
    cursor, boot = baseline[0]['__CURSOR'], baseline[0]['_BOOT_ID']
    base = {'resource_id': resource_id, 'kind': 'libero_static_scene_model_load_phases', 'physical_gpu': 3,
        'output_dir': str(output), 'source_script_sha256': EXPECTED_SCRIPT,
        'runtime_manifest_sha256': r.digest(RUNTIME), 'contract_sha256': r.digest(FOLDER / 'frozen-contract.json')}
    process, dispatched, started = None, False, None
    terminal, result, faults = 'aborted', {}, []
    r.append_healthcheck_event(ROOT, {**base, 'event': 'reserved', 'time_unix': time.time(), 'admission': admission})
    try:
        r.require(r.digest(SCRIPT) == EXPECTED_SCRIPT, 'model-load-phases script changed before launch')
        r.verify_files(source_files, root=ROOT)
        r.verify_files(inventory['checkpoint'])
        for encoder in inventory['hf_encoders']:
            r.verify_files(encoder['files'])
        r.require(subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip() == source, 'source HEAD changed before dispatch')
        command = [str(r.PYTHON), str(SCRIPT), '--contract', str(FOLDER / 'frozen-contract.json'),
            '--contract-sha256', r.digest(FOLDER / 'frozen-contract.json')]
        r.durable_json(output / 'command.json', {'argv': command})
        r.append_healthcheck_event(ROOT, {**base, 'event': 'dispatched', 'time_unix': time.time(), 'timeout_seconds': timeout})
        dispatched, started = True, time.monotonic()
        with (output / 'probe.log').open('x') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=r.child_environment(runtime),
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            ticks = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
            r.durable_json(output / 'process.json', {'pid': process.pid, 'proc_start_ticks': ticks,
                'parent_pid': os.getpid(), 'boot_id': boot, 'resource_id': resource_id, 'time_unix': time.time()})
            r.durable_json(FOLDER / 'status.json', {'phase': 'running', 'resource_id': resource_id, 'pid': process.pid, 'output_dir': str(output)})
            print(json.dumps({'phase': 'running', 'resource_id': resource_id, 'pid': process.pid}), flush=True)
            while True:
                rows = kernel_rows(['--after-cursor', cursor])
                for row in rows:
                    r.require(row.get('_BOOT_ID') == boot, 'kernel boot identity changed')
                    cursor = row['__CURSOR']
                    message = row.get('MESSAGE', '')
                    if message.startswith('NVRM: Xid (PCI:0000:61:00):') and f'pid={process.pid},' in message:
                        faults.append({'message': message, 'time_unix_us': int(row['__REALTIME_TIMESTAMP'])})
                r.durable_json(output / 'kernel-observations.json', {'owned_pid': process.pid, 'physical_gpu': 3, 'records': faults})
                r.require(not any(': 31,' in f['message'] or ': 109,' in f['message'] for f in faults), 'owned GPU3 native graphics Xid')
                code = process.poll()
                if code is not None:
                    break
                r.require(time.monotonic() - started < timeout, 'model-load-phases timeout')
                r.check_exclusive_gpu(process, physical_gpu=3)
                time.sleep(1)
        r.require(code == 0, f'model-load-phases child exit code {code}')
        events = r.read_events(output / 'model_load_phase_events.jsonl')
        completed = [e for e in events if e.get('event') == 'completed']
        r.require(len(completed) == 1 and completed[0]['mj_step_or_mj_step2_calls'] == 0,
                  'zero-integration completion evidence missing')
        proof = completed[0]
        r.require(len(proof['successful_boundaries']) == 9 and len(set(proof['successful_boundaries'])) == 9,
            'nine loading boundaries did not complete')
        r.require(len(proof['call_counts']) == 9 and all(v == 1 for v in proof['call_counts'].values()),
            'original loading operations not called exactly once')
        r.require(proof['predict_unguided_invocations'] == 0 and proof['explicit_render_calls'] == 12
            and all(v == 0 or v == [] for v in proof['compute'].values()), 'unexpected inference/render counts')
        r.require(proof['action_vectors_executed'] == proof['stage_calls'] == 0, 'unexpected task activity')
        frames = [e for e in events if e.get('event') == 'render_exit']
        r.require(frames and all(e['rgb_finite'] and e['rgb_nonuniform'] and e['rgb_dtype'] == 'uint8' for e in frames), 'invalid model-load-phases frame evidence')
        r.require(all(r.digest(Path(v['path'])) == v['sha256'] for v in contract['dependency_sources']), 'dependency source changed')
        result, terminal = {'diagnostic_evidence': proof, 'frame_count': len(frames), 'task_score': None}, 'completed'
    except BaseException as exc:
        result = {'reason': str(exc) if isinstance(exc, r.GateError) else type(exc).__name__, 'task_score': None}
    finally:
        r.terminate_owned(process)
        seconds = time.monotonic() - started if dispatched else 0.0
        result.update(base, event=terminal, gpu_process_wall_seconds=seconds, time_unix=time.time(),
            measurement='exclusive admitted GPU3 child lifetime including initialization and cleanup; no episode/actions/integration', faults=faults)
        r.durable_json(output / 'healthcheck-result.json', result)
        r.append_healthcheck_event(ROOT, result)
        r.durable_json(FOLDER / 'status.json', {'phase': terminal, 'resource_id': resource_id, 'result_path': str(output / 'healthcheck-result.json')})
        print(json.dumps(result), flush=True)
