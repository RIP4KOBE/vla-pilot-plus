"""Account one GPU3 render-process diagnostic under the shared research lock."""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
import re
import xml.etree.ElementTree as ET

ROOT = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
ARTIFACT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
sys.path.insert(0, str(ROOT / 'scripts'))
import qd_ed_final_runner as r
import qd_ed_available_gpu_queue as q
import qd_ed_policy_native_probe as native

SCRIPT = ARTIFACT / 'runtime/debug-tools/libero-task0-render-process.py'
EXPECTED_SCRIPT = '9eff1e42185316c5070b1d581e6238169657d1bdff9f4e20ebb76ac583e1a390'
RUNTIME = ARTIFACT / 'runtime/gpu3-render-diagnostic/runtime-manifest.json'
SEEDS = ROOT / 'data/frozen-seed-plan.json'
PROTOCOL = ROOT / 'experiments/iteration_001_execution_intent/gpu3-render-process-diagnostic.md'
FOLDER = ARTIFACT / 'runtime/gpu3-render-process-diagnostic'
FOLDER.mkdir(parents=True, exist_ok=True)
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

def kernel_rows(extra, timeout=10):
    done = subprocess.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'json', *extra],
                          capture_output=True, text=True, timeout=timeout, check=True)
    return [json.loads(line) for line in done.stdout.splitlines() if line.startswith('{')]

# These helpers are specific to this one model-parent / renderer diagnostic.
def normalized_boot(value):
    return str(value).lower().replace('-', '')


def proc_table(boot, proc_root=Path('/proc')):
    result = {}
    for path in proc_root.iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            result[int(path.name)] = {'pid': int(path.name), 'ppid': int(fields[1]),
                'pgid': int(fields[2]), 'session_id': int(fields[3]),
                'proc_start_ticks': fields[19], 'boot_id': normalized_boot(boot), 'state': fields[0]}
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            continue
    return result


def same_birth(left, right):
    return bool(left and right and all(str(left[key]) == str(right[key])
        for key in ('pid', 'proc_start_ticks')) and normalized_boot(left['boot_id']) == normalized_boot(right['boot_id']))


def identity(record, role=None):
    result = {key: record[key] for key in ('pid', 'ppid', 'pgid', 'session_id', 'proc_start_ticks', 'boot_id')}
    result['boot_id'] = normalized_boot(result['boot_id'])
    result['role'] = role or record['role']
    return result


def collect_owned(owned, snapshot, renderer_record=None, *, resource_id=None, contract_sha256=None):
    parent, = [record for record in owned.values() if record['role'] == 'model_parent']
    if renderer_record is not None:
        r.require(renderer_record['schema'] == 'qd-ed-render-process-ownership-v1'
            and renderer_record['resource_id'] == resource_id and renderer_record['contract_sha256'] == contract_sha256,
            'renderer ownership contract mismatch')
        r.require(identity(renderer_record['model_parent']) == identity(parent), 'renderer reports a different model parent')
        renderer = identity(renderer_record['renderer'])
        r.require(renderer['role'] == 'renderer' and renderer['pid'] != parent['pid']
            and renderer['ppid'] == parent['pid'] and renderer['pgid'] == renderer['session_id'] == parent['pid']
            and renderer['boot_id'] == parent['boot_id'] and str(renderer['proc_start_ticks']).isdigit()
            and int(renderer['proc_start_ticks']) >= int(parent['proc_start_ticks']), 'invalid renderer birth identity')
        previous = owned.get(renderer['pid'])
        r.require(previous is None or (same_birth(previous, renderer)
            and previous['role'] in ('renderer', 'auxiliary_cpu')), 'renderer PID identity changed')
        r.require(not any(item['role'] == 'renderer' and item['pid'] != renderer['pid'] for item in owned.values()),
            'multiple renderer identities')
        # This durable record was independently verified by the owned parent before releasing start.
        # Retain it even if the renderer already exited before this supervisor poll.
        if previous and 'reused_at_ticks' in previous:
            renderer['reused_at_ticks'] = previous['reused_at_ticks']
        owned[renderer['pid']] = renderer
    changed = True
    while changed:
        changed = False
        for pid, live in snapshot.items():
            if pid in owned or live['pgid'] != parent['pid'] or live['session_id'] != parent['pid']:
                continue
            ancestor = owned.get(live['ppid'])
            if ancestor and same_birth(ancestor, snapshot.get(ancestor['pid'])):
                owned[pid] = identity(live, 'auxiliary_cpu')
                changed = True
    for pid, record in owned.items():
        live = snapshot.get(pid)
        if live and not same_birth(record, live):
            # Keep the historical identity, and bound later kernel attribution before the reused birth.
            record.setdefault('reused_at_ticks', str(live['proc_start_ticks']))
    return owned


def validate_owned_liveness(owned, snapshot):
    parent, = [record for record in owned.values() if record['role'] == 'model_parent']
    for pid, record in owned.items():
        live = snapshot.get(pid)
        if live is None or live['state'] in ('Z', 'X', 'x'):
            continue
        r.require(same_birth(record, live) and live['pgid'] == record['pgid']
            and live['session_id'] == record['session_id'], 'owned process birth or group identity changed')
        if record['role'] == 'renderer' and same_birth(parent, snapshot.get(parent['pid'])):
            r.require(live['ppid'] == parent['pid'], 'renderer parent identity changed')


def validate_gpu_xml(xml, expected_uuid, owned, snapshot, before_snapshot=None):
    tree = ET.fromstring(xml)
    devices = tree.findall('gpu')
    r.require(len(devices) == 1 and devices[0].findtext('uuid') == expected_uuid, 'GPU3 XML identity differs')
    processes = devices[0].find('processes')
    r.require(processes is not None and (processes.text or '').strip() in ('',), 'GPU process metadata unavailable')
    pids = []
    for item in processes.findall('process_info'):
        text = (item.findtext('pid') or '').strip()
        r.require(text.isdigit(), 'GPU process metadata has unknown PID')
        pid = int(text)
        record, live = owned.get(pid), snapshot.get(pid)
        if live is None and before_snapshot is not None:
            # nvidia-smi can return a process that exited during the query. A changed/reused
            # live PID never takes this fallback; only a previously verified birth can.
            live = before_snapshot.get(pid)
        r.require(record is not None and record['role'] in ('model_parent', 'renderer')
            and same_birth(record, live) and live['pgid'] == record['pgid']
            and live['session_id'] == record['session_id'], 'external or unverified GPU3 process appeared')
        pids.append(pid)
    return sorted(set(pids))


def gpu_processes(expected_uuid, owned, boot, *, timeout=10, run=subprocess.run, refresh=None):
    before = proc_table(boot)
    result = run(['nvidia-smi', '-q', '-x', '-i', '3'], capture_output=True, text=True, timeout=timeout)
    r.require(result.returncode == 0, 'GPU3 graphics/compute exclusivity query failed')
    # The atomic parent-verified registration is durable before any renderer GPU operation,
    # but may have appeared after the outer monitor's previous refresh.
    snapshot = refresh() if refresh is not None else proc_table(boot)
    return validate_gpu_xml(result.stdout, expected_uuid, owned, snapshot, before_snapshot=before)


def pci_device(value):
    domain, bus, device = str(value).lower().split(':')
    return f'{int(domain, 16):04x}:{int(bus, 16):02x}:{int(device.split(".")[0], 16):02x}'


def owned_xids(rows, owned, boot, pci, *, clock_ticks=None):
    ticks = clock_ticks or os.sysconf('SC_CLK_TCK')
    result = []
    for row in rows:
        r.require(normalized_boot(row.get('_BOOT_ID')) == normalized_boot(boot), 'kernel boot identity changed')
        message = row.get('MESSAGE', '')
        match = re.search(r'NVRM: Xid \(PCI:([^)]*)\):\s*(\d+),.*?\bpid=(\d+),', message)
        if not match or pci_device(match.group(1)) != pci_device(pci):
            continue
        code, pid = int(match.group(2)), int(match.group(3))
        record = owned.get(pid)
        if record is None or record['role'] not in ('model_parent', 'renderer'):
            continue
        observed = int(row['__MONOTONIC_TIMESTAMP']) / 1_000_000
        if observed < int(record['proc_start_ticks']) / ticks:
            continue
        if 'reused_at_ticks' in record and observed >= int(record['reused_at_ticks']) / ticks:
            continue
        result.append({'message': message, 'xid': code, 'pid': pid, 'role': record['role'],
            'proc_start_ticks': record['proc_start_ticks'], 'boot_id': normalized_boot(boot),
            'time_unix_us': int(row['__REALTIME_TIMESTAMP']), 'monotonic_time_us': int(row['__MONOTONIC_TIMESTAMP']),
            'journal_cursor': row['__CURSOR']})
    return result


def cleanup_owned(process, owned, *, snapshot_fn, timeout=18, clock=time.monotonic,
                  sleep=time.sleep, killpg=os.killpg, kill=os.kill):
    """Bounded group cleanup even after leader exit; never signal a reused or unproven PID."""
    started = clock()
    parent, = [record for record in owned.values() if record['role'] == 'model_parent']
    pgid = parent['pgid']
    sent, foreign_seen = [], {}

    def inspect():
        snapshot = snapshot_fn()
        collect_owned(owned, snapshot)
        live = {pid: item for pid, item in snapshot.items()
            if item['state'] not in ('Z', 'X', 'x') and pid in owned and same_birth(owned[pid], item)}
        group = {pid: item for pid, item in snapshot.items() if item['pgid'] == pgid
            and item['state'] not in ('Z', 'X', 'x')}
        foreign = {pid: item for pid, item in group.items() if pid not in live}
        foreign_seen.update({pid: identity(item, 'unverified') for pid, item in foreign.items()})
        return live, group, foreign

    def signal_owned(signum):
        live, group, foreign = inspect()
        grouped = {pid: item for pid, item in live.items() if item['pgid'] == pgid and item['session_id'] == parent['session_id']}
        if grouped and not foreign and set(group) == set(grouped):
            try:
                killpg(pgid, signum)
                sent.append({'target': 'verified_process_group', 'pgid': pgid, 'signal': int(signum), 'pids': sorted(grouped)})
            except ProcessLookupError:
                pass
        else:
            grouped = {}
        # If a foreign/reused identity is in the group, signal only each independently revalidated owned birth.
        for pid in sorted(set(live) - set(grouped)):
            fresh = snapshot_fn().get(pid)
            if not same_birth(owned[pid], fresh) or fresh['state'] in ('Z', 'X', 'x'):
                continue
            try:
                kill(pid, signum)
                sent.append({'target': 'verified_pid', 'pid': pid, 'signal': int(signum)})
            except ProcessLookupError:
                pass

    signal_owned(signal.SIGTERM)
    escalated = False
    while True:
        process.poll()  # Reap the direct child; renderer is joined by its model parent on normal completion.
        live, group, foreign = inspect()
        if not live:
            return {'success': not foreign, 'remaining_owned_pids': [], 'unverified_group_members': list(foreign_seen.values()),
                'signals': sent, 'elapsed_seconds': clock() - started}
        elapsed = clock() - started
        if not escalated and elapsed >= min(10, timeout / 2):
            signal_owned(signal.SIGKILL)
            escalated = True
        if elapsed >= timeout:
            return {'success': False, 'remaining_owned_pids': sorted(live),
                'unverified_group_members': list(foreign_seen.values()), 'signals': sent, 'elapsed_seconds': elapsed}
        sleep(min(0.1, max(0, timeout - elapsed)))


with r.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
    q.no_unfinished(ROOT)
    with r.locked(ROOT / 'data/qd-ed-state.lock'):
        r.sync_state_from_journal(ROOT, r.read_events(ROOT / 'data/attempt-ledger.jsonl'))
    state = r.read_state(ROOT / 'research-state.yaml')
    r.require(q.candidate_indices(state) == [3], 'GPU3-only authorization required')
    runtime = r.read_json(RUNTIME)
    r.require(r.runtime_gpu(runtime, state) == 3 and runtime['cuda_egl_verified'], 'GPU3 binding missing')
    r.require(r.digest(SCRIPT) == EXPECTED_SCRIPT, 'render-process script changed')
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
    source_paths |= {str(PROTOCOL.relative_to(ROOT)), 'scripts/qd_ed_policy_native_probe.py', 'third_party/rdt/scripts/maniskill_model.py', 'third_party/rdt/models/multimodal_encoder/t5_encoder.py', 'third_party/rdt/models/multimodal_encoder/siglip_encoder.py', 'third_party/rdt/models/rdt_runner.py'}
    source_files = [{'path': p, 'sha256': r.digest(ROOT / p)} for p in sorted(source_paths)]
    resource_id = state['run_name'] + '__gpu3_render_process__' + uuid.uuid4().hex[:12]
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
    contract = {'schema': 'qd-ed-task0-render-process-contract-v1', 'resource_id': resource_id, 'output_dir': str(output),
        'source_commit': source, 'source_script_sha256': EXPECTED_SCRIPT, 'supervisor_sha256': r.digest(__file__),
        'protocol_sha256': r.digest(PROTOCOL), 'runtime_manifest_path': str(RUNTIME), 'runtime_manifest_sha256': r.digest(RUNTIME),
        'seed_plan_path': str(SEEDS), 'seed_plan_sha256': r.digest(SEEDS),
        'profiles_path': str(profiles_path), 'profiles_sha256': r.digest(profiles_path),
        'runtime_inventory_path': str(inventory_path), 'runtime_inventory_sha256': r.digest(inventory_path),
        'policy_configuration_path': str(policy_path), 'policy_configuration_sha256': r.digest(policy_path),
        'physical_gpu': 3, 'timeout_seconds': 600, 'render_limit': 32, 'explicit_render_calls': 9,
        'dependency_sources': dependency_records, 'source_files': source_files,
        'actions': 0, 'integration_transitions': 0, 'cleanup_timeout_seconds': 40,
        'renderer_ownership_schema': 'qd-ed-render-process-ownership-v1'}
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
    base = {'resource_id': resource_id, 'kind': 'libero_static_render_process_b1_render', 'physical_gpu': 3,
        'output_dir': str(output), 'source_script_sha256': EXPECTED_SCRIPT,
        'runtime_manifest_sha256': r.digest(RUNTIME), 'contract_sha256': r.digest(FOLDER / 'frozen-contract.json')}
    process, dispatched, started = None, False, None
    terminal, result, faults = 'aborted', {}, []
    owned, monitor_errors = {}, []

    def refresh_owned():
        snapshot = proc_table(boot)
        ownership = output / 'renderer-process.json'
        if ownership.exists():
            record = r.read_json(ownership)
            fingerprint = r.digest(ownership)
            previous = refresh_owned.renderer_record_sha
            r.require(previous is None or previous == fingerprint, 'renderer ownership record changed')
            collect_owned(owned, snapshot, record, resource_id=resource_id, contract_sha256=base['contract_sha256'])
            refresh_owned.renderer_record_sha = fingerprint
        else:
            collect_owned(owned, snapshot)
        r.durable_json(output / 'owned-processes.json', {'schema': 'qd-ed-render-process-supervisor-ownership-v1',
            'resource_id': resource_id, 'processes': list(owned.values()), 'time_unix': time.time()})
        validate_owned_liveness(owned, snapshot)
        return snapshot
    refresh_owned.renderer_record_sha = None

    def read_faults(query_timeout=10):
        global cursor
        rows = kernel_rows(['--after-cursor', cursor], timeout=query_timeout)
        faults.extend(owned_xids(rows, owned, boot, runtime['gpu_mapping']['pci_bus_id']))
        if rows:
            cursor = rows[-1]['__CURSOR']
        r.durable_json(output / 'kernel-observations.json', {'owned_processes': list(owned.values()),
            'physical_gpu': 3, 'records': faults})

    r.append_healthcheck_event(ROOT, {**base, 'event': 'reserved', 'time_unix': time.time(), 'admission': admission})
    try:
        r.require(r.digest(SCRIPT) == EXPECTED_SCRIPT, 'render-process script changed before launch')
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
            snapshot = proc_table(boot)
            r.require(process.pid in snapshot, 'model-parent identity disappeared before registration')
            parent = identity(snapshot[process.pid], 'model_parent')
            r.require(parent['ppid'] == os.getpid() and parent['pid'] == parent['pgid'] == parent['session_id'],
                'model parent is not an owned session/group leader')
            owned[parent['pid']] = parent
            r.durable_json(output / 'process.json', {**parent, 'parent_pid': os.getpid(),
                'resource_id': resource_id, 'time_unix': time.time()})
            r.durable_json(FOLDER / 'status.json', {'phase': 'running', 'resource_id': resource_id,
                'pid': process.pid, 'output_dir': str(output)})
            print(json.dumps({'phase': 'running', 'resource_id': resource_id, 'pid': process.pid}), flush=True)
            while True:
                remaining = timeout - (time.monotonic() - started)
                r.require(remaining > 0, 'render-process timeout')
                refresh_owned()
                read_faults(min(10, remaining))
                r.require(not any(f['xid'] in (31, 109) for f in faults), 'owned GPU3 native graphics Xid')
                code = process.poll()
                if code is not None:
                    break
                remaining = timeout - (time.monotonic() - started)
                r.require(remaining > 0, 'render-process timeout')
                gpu_processes(runtime['gpu_mapping']['uuid'], owned, boot, timeout=min(10, remaining), refresh=refresh_owned)
                time.sleep(min(1, max(0, timeout - (time.monotonic() - started))))
        r.require(code == 0, f'render-process child exit code {code}')
        events = r.read_events(output / 'render_process_events.jsonl')
        completed = [e for e in events if e.get('event') == 'completed']
        r.require(len(completed) == 1 and completed[0]['mj_step_or_mj_step2_calls'] == 0,
                  'zero-integration completion evidence missing')
        proof = completed[0]
        r.require(proof['renderer_joined'] is True and proof['renderer_exitcode'] == 0
            and proof['renderer_forced_termination'] is False and proof['refused_integration_calls'] == 0
            and proof['renderer_cleanup_success'] is True, 'renderer join/cleanup evidence missing')
        renderer, = [record for record in owned.values() if record['role'] == 'renderer']
        r.require(identity(proof['model_parent']) == identity(parent) and identity(proof['renderer']) == identity(renderer),
            'completed process identities differ from registered births')
        r.require(all(e['pid'] == renderer['pid'] for e in events if e.get('event') in {'render_enter','render_exit'}),
            'render executed outside renderer process')
        for label in ('construct','set_init_state','before_model_load','after_model_load','after_prediction_sync','close'):
            entries = [e for e in events if e.get('event') == 'phase_enter' and e.get('phase') == label]
            r.require(len(entries) == 1 and entries[0]['pid'] == renderer['pid'], 'scene phase process ownership differs: ' + label)
        for label in ('load_model','predict_b1'):
            entries = [e for e in events if e.get('event') == 'phase_enter' and e.get('phase') == label]
            r.require(len(entries) == 1 and entries[0]['pid'] == parent['pid'], 'model phase process ownership differs: ' + label)
        maps = [e for e in events if e.get('event') == 'gpu_library_maps']
        r.require(len(maps) == 6 and {(e['pid'], e['boundary']) for e in maps}
            == {(pid, name) for pid in (parent['pid'], renderer['pid'])
                for name in ('before_model_load','after_model_load','after_prediction_sync')}, 'both-process loaded library evidence missing')
        r.require(proof['predict_unguided_invocations'] == 1 and proof['raw_prediction_shape'] == [1,64,128]
            and proof['raw_prediction_finite'] and proof['compute']['model_forward_calls'] == 5
            and proof['compute']['model_batch_rows'] == 5 and proof['compute']['denoising_invocations'] == 1,
            'exact native B1 evidence missing')
        r.require(proof['action_vectors_executed'] == proof['stage_calls'] == proof['dino_model_loads'] == 0,
            'unexpected activity outside diagnostic scope')
        frames = [e for e in events if e.get('event') == 'render_exit']
        r.require(frames and all(e['rgb_finite'] and e['rgb_nonuniform'] and e['rgb_dtype'] == 'uint8' and (not e['depth'] or e['depth_finite']) for e in frames), 'invalid render-process frame evidence')
        r.require(all(r.digest(Path(v['path'])) == v['sha256'] for v in contract['dependency_sources']), 'dependency source changed')
        grouped = {}
        for frame in frames:
            if frame['phase'] in {'before_model_load','after_model_load','after_prediction_sync'}:
                key = str((frame['camera'],frame['width'],frame['height'],frame['depth']))
                grouped.setdefault(key, {})[frame['phase']] = frame['rgb_sha256']
        comparisons = {k: {'phase_hashes': v, 'identical_at_all_three_boundaries': len(v) == 3 and len(set(v.values())) == 1} for k,v in grouped.items()}
        r.durable_json(output / 'cross-boundary-image-hashes.json', comparisons)
        expected_hashes = {('agentview',128): '28a6ee31b7f3160728615023e4a09cb9ec79d5c533bc3de3aa94cf624aad6115',
            ('robot0_eye_in_hand',128): '5b7c11d173b84e2d877f0ec7f105d0e9f1e1a31d985c8934571c2ef0a76456a9',
            ('agentview',640): '6d9b118dc42be6c23d511316b9a64f53c467a3eef63528fe4b7e1aabb9234b09'}
        static_comparisons = [{'phase':v['phase'],'camera':v['camera'],'width':v['width'],
            'rgb_sha256':v['rgb_sha256'],'matches_prior_static_scene':v['rgb_sha256']==expected_hashes[(v['camera'],v['width'])]}
            for v in frames if v['phase'] in {'before_model_load','after_model_load','after_prediction_sync'}]
        r.durable_json(output / 'image-comparison-to-static-pass.json',static_comparisons)
        r.require(len(comparisons)==3 and all(v['identical_at_all_three_boundaries'] for v in comparisons.values()), 'cross-boundary image identity differs')
        r.require(len(static_comparisons)==9 and all(v['matches_prior_static_scene'] for v in static_comparisons), 'static reference image identity differs')
        result, terminal = {'image_hash_comparisons': comparisons, 'diagnostic_evidence': completed[0], 'frame_count': len(frames), 'task_score': None}, 'completed'
    except BaseException as exc:
        result = {'reason': str(exc) if isinstance(exc, r.GateError) else type(exc).__name__, 'task_score': None}
    finally:
        cleanup_deadline = time.monotonic() + 40
        cleanup = {'success': process is None, 'remaining_owned_pids': []}
        if process is not None:
            if owned:
                try:
                    refresh_owned()
                except BaseException as ownership_error:
                    monitor_errors.append({'stage': 'pre_cleanup_ownership', 'exception_type': type(ownership_error).__name__})
            try:
                if owned:
                    cleanup = cleanup_owned(process, owned, snapshot_fn=lambda: proc_table(boot),
                        timeout=min(18, max(0.1, cleanup_deadline - time.monotonic())))
                else:
                    # Birth registration failed: never invent permission to signal a PID/group.
                    cleanup = {'success': process.poll() is not None, 'remaining_owned_pids': [],
                        'reason': 'model-parent birth was not verified'}
            except BaseException as cleanup_error:
                monitor_errors.append({'stage': 'owned_cleanup', 'exception_type': type(cleanup_error).__name__})
                cleanup = {'success': False, 'remaining_owned_pids': []}
        if owned:
            try:
                refresh_owned()
            except BaseException as ownership_error:
                monitor_errors.append({'stage': 'post_cleanup_ownership', 'exception_type': type(ownership_error).__name__})
            try:
                remaining = cleanup_deadline - time.monotonic()
                r.require(remaining > 0, 'cleanup deadline before final kernel observation')
                read_faults(min(10, remaining))
            except BaseException as kernel_error:
                monitor_errors.append({'stage': 'post_cleanup_kernel', 'exception_type': type(kernel_error).__name__})
            try:
                remaining = cleanup_deadline - time.monotonic()
                r.require(remaining > 0, 'cleanup deadline before final GPU observation')
                gpu_pids = gpu_processes(runtime['gpu_mapping']['uuid'], owned, boot, timeout=min(10, remaining), refresh=refresh_owned)
                r.require(not gpu_pids, 'owned GPU3 processes remain after cleanup')
                cleanup['final_gpu_process_pids'] = gpu_pids
            except BaseException as gpu_error:
                monitor_errors.append({'stage': 'post_cleanup_gpu', 'exception_type': type(gpu_error).__name__})
        if not cleanup['success'] or monitor_errors or any(f['xid'] in (31, 109) for f in faults):
            terminal = 'aborted'
            result.setdefault('reason', 'owned process cleanup, final monitoring, or GPU3 Xid check failed')
        seconds = time.monotonic() - started if dispatched else 0.0
        result.update(base, event=terminal, gpu_process_wall_seconds=seconds, time_unix=time.time(),
            measurement='one exclusive admitted GPU3 logical resource with model parent and spawn renderer; lifetime includes cleanup; zero episodes/actions/integration',
            faults=faults, owned_processes=list(owned.values()), cleanup=cleanup, final_monitor_errors=monitor_errors)
        r.durable_json(output / 'healthcheck-result.json', result)
        r.append_healthcheck_event(ROOT, result)
        r.durable_json(FOLDER / 'status.json', {'phase': terminal, 'resource_id': resource_id, 'result_path': str(output / 'healthcheck-result.json')})
        print(json.dumps(result), flush=True)
