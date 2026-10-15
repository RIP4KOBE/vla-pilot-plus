"""Account one GPU3 context-lifetime diagnostic under the shared research lock."""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
ARTIFACT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
sys.path.insert(0, str(ROOT / 'scripts'))
import qd_ed_final_runner as r
import qd_ed_available_gpu_queue as q
import qd_ed_policy_native_probe as native

SCRIPT = ARTIFACT / 'runtime/debug-tools/libero-task0-context-lifetime.py'
EXPECTED_SCRIPT = '76c600819d57cc7179b3ba75c3f88ba5901053e68f38523ebbbe021c9785784f'
RUNTIME = ARTIFACT / 'runtime/gpu3-render-diagnostic/runtime-manifest.json'
SEEDS = ROOT / 'data/frozen-seed-plan.json'
PROTOCOL = ROOT / 'experiments/iteration_001_execution_intent/gpu3-context-lifetime-diagnostic.md'
FOLDER = ARTIFACT / 'runtime/gpu3-context-lifetime-diagnostic'
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
    r.require(r.digest(SCRIPT) == EXPECTED_SCRIPT, 'context-lifetime script changed')
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
    source_paths |= {str(PROTOCOL.relative_to(ROOT)), 'scripts/qd_ed_policy_native_probe.py'}
    source_files = [{'path': p, 'sha256': r.digest(ROOT / p)} for p in sorted(source_paths)]
    resource_id = state['run_name'] + '__gpu3_context_lifetime__' + uuid.uuid4().hex[:12]
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
    contract = {'schema': 'qd-ed-task0-context-lifetime-contract-v1', 'resource_id': resource_id, 'output_dir': str(output),
        'source_commit': source, 'source_script_sha256': EXPECTED_SCRIPT, 'supervisor_sha256': r.digest(__file__),
        'protocol_sha256': r.digest(PROTOCOL), 'runtime_manifest_path': str(RUNTIME), 'runtime_manifest_sha256': r.digest(RUNTIME),
        'seed_plan_path': str(SEEDS), 'seed_plan_sha256': r.digest(SEEDS),
        'profiles_path': str(profiles_path), 'profiles_sha256': r.digest(profiles_path),
        'runtime_inventory_path': str(inventory_path), 'runtime_inventory_sha256': r.digest(inventory_path),
        'policy_configuration_path': str(policy_path), 'policy_configuration_sha256': r.digest(policy_path),
        'physical_gpu': 3, 'timeout_seconds': 600, 'render_limit': 32, 'explicit_render_calls': 6,
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
    base = {'resource_id': resource_id, 'kind': 'libero_render_context_not_live_across_b1', 'physical_gpu': 3,
        'output_dir': str(output), 'source_script_sha256': EXPECTED_SCRIPT,
        'runtime_manifest_sha256': r.digest(RUNTIME), 'contract_sha256': r.digest(FOLDER / 'frozen-contract.json')}
    process, dispatched, started = None, False, None
    terminal, result, faults = 'aborted', {}, []
    r.append_healthcheck_event(ROOT, {**base, 'event': 'reserved', 'time_unix': time.time(), 'admission': admission})
    try:
        r.require(r.digest(SCRIPT) == EXPECTED_SCRIPT, 'context-lifetime script changed before launch')
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
                r.require(time.monotonic() - started < timeout, 'context-lifetime timeout')
                xml = subprocess.check_output(['nvidia-smi','-q','-x','-i','3'],text=True,timeout=10)
                devices = ET.fromstring(xml).findall('gpu')
                r.require(len(devices)==1 and devices[0].findtext('uuid')==runtime['gpu_mapping']['uuid'],'GPU3 XML identity differs')
                app_list = devices[0].find('processes')
                r.require(app_list is not None and not (app_list.text or '').strip(),'GPU process metadata unavailable')
                r.require(all((app.findtext('pid') or '').strip()==str(process.pid) for app in app_list.findall('process_info')),'external GPU3 graphics/compute process appeared')
                time.sleep(1)
        r.require(code == 0, f'context-lifetime child exit code {code}')
        events = r.read_events(output / 'context_lifetime_events.jsonl')
        completed = [e for e in events if e.get('event') == 'completed']
        r.require(len(completed) == 1 and completed[0]['mj_step_or_mj_step2_calls'] == 0,
                  'zero-integration completion evidence missing')
        proof = completed[0]
        r.require(proof['predict_unguided_invocations'] == 1 and proof['raw_prediction_shape'] == [1,64,128]
            and proof['raw_prediction_finite'] and proof['compute']['model_forward_calls'] == 5
            and proof['compute']['model_batch_rows'] == 5 and proof['compute']['denoising_invocations'] == 1
            and proof['compute']['vision_encoder_forward_calls'] > 0 and proof['compute']['text_encoder_forward_calls'] > 0,
            'exact native B1 evidence missing')
        r.require(proof['action_vectors_executed'] == proof['stage_calls'] == proof['dino_model_loads'] == 0,
            'unexpected activity outside diagnostic scope')
        r.require(proof['model_loaded_before_scene'] and proof['explicit_render_calls']==6
            and proof['cpu_rng_restored_after_scene_init'] and proof['scene_env_seed']==1969522881,
            'context-lifetime order or scene RNG isolation missing')
        context_records=proof['context_creation_records']
        r.require(context_records and all(v['model_loaded_before'] and v['cuda_initialized_before'] and v['completed'] for v in context_records),
            'context-lifetime context observation missing')
        r.require(len(context_records)==2 and context_records[0]['constructor']==context_records[1]['constructor'],
            'expected exactly two matching application contexts')
        r.require(proof['context_release_calls']==proof['context_rebuild_calls']==1
            and proof['context_rebuild_mj_forward_calls']==1 and proof['display_option_objects_preserved']
            and proof['global_egl_display_released'] is False and not proof['release_unraisable_exceptions'],
            'context lifecycle scope or cleanup proof differs')
        r.require(proof['owned_egl_destroy_records']==[{'returned_success':True,'exception_type':None}],
            'original application EGL destruction not confirmed')
        physical_hashes=[proof[k] for k in ('physical_state_sha256_before_release',
            'physical_state_sha256_after_release','physical_state_sha256_after_rebuild')]
        r.require(len(set(physical_hashes))==1 and len(physical_hashes[0])==64,
            'qpos/qvel/act/ctrl/time differ across context lifecycle')
        r.require(proof['sim_time_after_init']==proof['sim_time_final']==0 and proof['mj_step1_calls']==1
            and proof['mj_forward_calls']==6, 'static scene changed')
        frames = [e for e in events if e.get('event') == 'render_exit']
        r.require(frames and all(e['rgb_finite'] and e['rgb_nonuniform'] and e['rgb_dtype'] == 'uint8' and (not e['depth'] or e['depth_finite']) for e in frames), 'invalid context-lifetime frame evidence')
        r.require(all(r.digest(Path(v['path'])) == v['sha256'] for v in contract['dependency_sources']), 'dependency source changed')
        grouped = {}
        for frame in frames:
            if frame['phase'] in {'after_model_load_scene_init','after_prediction_sync'}:
                key = str((frame['camera'],frame['width'],frame['height'],frame['depth']))
                grouped.setdefault(key, {})[frame['phase']] = frame['rgb_sha256']
        comparisons = {k: {'phase_hashes': v, 'identical_at_both_boundaries': len(v) == 2 and len(set(v.values())) == 1} for k,v in grouped.items()}
        r.durable_json(output / 'cross-boundary-image-hashes.json', comparisons)
        expected = {('agentview',128): '28a6ee31b7f3160728615023e4a09cb9ec79d5c533bc3de3aa94cf624aad6115',
            ('robot0_eye_in_hand',128): '5b7c11d173b84e2d877f0ec7f105d0e9f1e1a31d985c8934571c2ef0a76456a9',
            ('agentview',640): '6d9b118dc42be6c23d511316b9a64f53c467a3eef63528fe4b7e1aabb9234b09'}
        comparisons_to_static = [{'phase':e['phase'],'camera':e['camera'],'width':e['width'],'rgb_sha256':e['rgb_sha256'],
            'matches_static':e['rgb_sha256']==expected[(e['camera'],e['width'])]}
            for e in frames if e['phase'] in {'after_model_load_scene_init','after_prediction_sync'}]
        r.durable_json(output / 'image-comparison-to-static-pass.json',comparisons_to_static)
        r.require(len(frames)==10 and len(comparisons)==3 and all(v['identical_at_both_boundaries'] for v in comparisons.values()),'context-lifetime camera sequence differs')
        r.require(len(comparisons_to_static)==6 and all(v['matches_static'] for v in comparisons_to_static),'context-lifetime images differ from static reference')
        result, terminal = {'image_hash_comparisons': comparisons, 'diagnostic_evidence': completed[0], 'frame_count': len(frames), 'prediction_matches_model_first': proof['raw_prediction_sha256']=='e47036194c7e9007cf4d17b3fbc18ac7b2afb4227551624e14eb5f8ebd90f7ca', 'task_score': None}, 'completed'
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
