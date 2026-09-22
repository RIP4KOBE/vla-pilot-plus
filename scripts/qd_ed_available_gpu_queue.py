#!/usr/bin/env python3
"""Wait on CPU for an authorized idle GPU, then run explicit frozen episodes.

This queue grants no phase authorization and never retries a dispatched episode.
Hardware rebinding creates new manifests/plans; scientific inputs stay frozen.
"""
from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

import yaml

import qd_ed_final_runner as runner
import qd_ed_gpu_probe as probe
from qd_ed_runtime_setup import normalized_pci_bus_id


ROOT = Path(__file__).resolve().parents[1]
UNFINISHED_JOURNAL = 'unfinished attempt or healthcheck requires reconciliation'
HARDWARE_RUNTIME_KEYS = {'gpu_mapping', 'cuda_egl_verified', 'cuda_egl_probe',
                         'metadata_mapping_verified', 'egl_device_metadata_path', 'files'}
MAPPING_KEYS = ('physical_gpu', 'uuid', 'pci_bus_id', 'driver_version', 'egl_device_index')


def candidate_indices(state):
    policy = state.get('authorized_gpu_selection', {})
    candidates = policy.get('candidate_indices')
    runner.require(isinstance(candidates, list) and bool(candidates)
                   and all(type(i) is int and i >= 0 for i in candidates)
                   and len(set(candidates)) == len(candidates)
                   and policy.get('single_exclusive_worker') is True
                   and policy.get('rescan_if_unavailable') is True,
                   'explicit available-GPU selection authorization missing')
    runner.require(runner.authorized_gpu(state) in candidates,
                   'selected GPU is outside authorized candidates')
    return candidates


def visible_mask_indices(mask, order, devices):
    """Resolve only explicit UUIDs or provable PCI-ordered CUDA ordinals."""
    if not mask or mask.strip() == '-1':
        return set()
    pci_order = None
    if order == 'PCI_BUS_ID':
        try:
            pci_order = sorted(devices, key=lambda index: normalized_pci_bus_id(devices[index]['pci_bus_id']))
        except (KeyError, RuntimeError):
            return set()
    selected = set()
    for token in mask.split(','):
        token = token.strip()
        if token == '-1':
            break
        if token.startswith('GPU-'):
            matches = [index for index, device in devices.items()
                       if device['uuid'].lower().startswith(token.lower())]
            if len(matches) != 1:
                break
            selected.add(matches[0])
        elif token.isdigit() and pci_order is not None and int(token) < len(pci_order):
            selected.add(pci_order[int(token)])
        else:
            break
    return selected


def process_gpu_reservations(devices, *, proc_root=Path('/proc'), own_pid=None):
    """Read only CUDA mask/order values; never retain process environments."""
    own_pid = os.getpid() if own_pid is None else own_pid
    processes = {}
    for path in Path(proc_root).iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            if fields[0] in {'Z', 'X', 'x'}:
                continue
            processes[int(path.name)] = (int(fields[1]), fields[19], path)
        except (OSError, ValueError, IndexError):
            continue
    excluded = {own_pid}
    while True:
        children = {pid for pid, (parent, _, _) in processes.items() if parent in excluded}
        enlarged = excluded | children
        if enlarged == excluded:
            break
        excluded = enlarged
    reservations = {index: [] for index in devices}
    for pid, (_, started, path) in processes.items():
        if pid in excluded:
            continue
        try:
            # Linux exposes the environment as a NUL stream. Only these two
            # allowlisted fields are decoded; no other value is logged/stored.
            selected = {}
            with (path / 'environ').open('rb') as stream:
                for field in stream.read().split(b'\0'):
                    key, separator, value = field.partition(b'=')
                    if separator and key in {b'CUDA_VISIBLE_DEVICES', b'CUDA_DEVICE_ORDER'}:
                        selected[key] = value.decode('ascii', errors='strict')
            fresh = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            if fresh[0] in {'Z', 'X', 'x'} or fresh[19] != started:
                continue
            indices = visible_mask_indices(selected.get(b'CUDA_VISIBLE_DEVICES', ''),
                                           selected.get(b'CUDA_DEVICE_ORDER', ''), devices)
            for index in indices:
                reservations[index].append(pid)
        except (OSError, UnicodeError, ValueError, IndexError):
            continue
    return {index: sorted(pids) for index, pids in reservations.items()}


def inventory(run=subprocess.run, *, reservations=process_gpu_reservations):
    """Only NVIDIA metadata queries: no CUDA imports, allocations, or contexts."""
    raw = run(['nvidia-smi', '--query-gpu=index,uuid,memory.used,pci.bus_id',
               '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15)
    apps = run(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
                '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15)
    runner.require(raw.returncode == 0 and apps.returncode == 0,
                   'available-GPU inventory query failed')
    devices = {}
    try:
        for fields in csv.reader(io.StringIO(raw.stdout)):
            index, identity, memory, pci = [value.strip() for value in fields]
            index, memory = int(index), int(memory)
            runner.require(index >= 0 and memory >= 0 and identity.startswith('GPU-')
                           and index not in devices, 'invalid GPU inventory identity')
            devices[index] = {'physical_gpu': index, 'uuid': identity,
                              'pci_bus_id': normalized_pci_bus_id(pci),
                              'memory_used_mib': memory, 'compute_pids': []}
        runner.require(bool(devices) and len({d['uuid'] for d in devices.values()}) == len(devices),
                       'empty or ambiguous GPU inventory')
        by_uuid = {device['uuid']: device for device in devices.values()}
        for fields in csv.reader(io.StringIO(apps.stdout)):
            if not fields or (len(fields) == 1 and 'no running' in fields[0].lower()):
                continue
            identity, pid = [value.strip() for value in fields]
            runner.require(identity in by_uuid and pid.isdigit(), 'unknown GPU compute process identity')
            by_uuid[identity]['compute_pids'].append(int(pid))
    except (ValueError, TypeError) as exc:
        raise runner.GateError('invalid available-GPU inventory response') from exc
    masks = reservations(devices)
    for index, device in devices.items():
        device['reserving_pids'] = masks.get(index, [])
    return devices


def currently_idle(device):
    return (not device['compute_pids'] and not device.get('reserving_pids')
            and device['memory_used_mib'] < 1024)


def update_idle_windows(devices, windows, now, idle_seconds):
    for index in set(windows) - set(devices):
        windows.pop(index)
    for index, device in devices.items():
        identity = (device['uuid'], device.get('pci_bus_id'))
        previous = windows.get(index)
        if not currently_idle(device):
            windows.pop(index, None)
            elapsed = 0.0
        else:
            if previous is None or previous[0] != identity:
                windows[index] = (identity, now)
            elapsed = max(0.0, now - windows[index][1])
        device['idle_observed_seconds'] = elapsed
        device['idle_stable'] = currently_idle(device) and elapsed >= idle_seconds


def choose_device(devices, candidates, preferred):
    runner.require(set(candidates) <= set(devices), 'authorized GPU is missing from this server')
    order = [preferred] + [index for index in candidates if index != preferred]
    return next((devices[index] for index in order
                 if currently_idle(devices[index]) and devices[index].get('idle_stable', True)), None)


def reservation_admission(device):
    fresh = inventory().get(device['physical_gpu'])
    runner.require(fresh is not None and fresh['uuid'] == device['uuid'],
                   'GPU reservation inventory identity changed')
    runner.require(not fresh.get('reserving_pids'),
                   f"GPU{device['physical_gpu']} has external GPU reservations")


def current_metadata(physical_gpu, *, root=ROOT):
    # Use a fresh unmasked process so no earlier library initialization can
    # cache another CUDA ordinal namespace. This helper creates no context.
    env = dict(os.environ)
    env.pop('CUDA_VISIBLE_DEVICES', None)
    env['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    script = ('import json,sys; sys.path.insert(0,sys.argv[1]); '
              'from qd_ed_runtime_setup import query_gpu_egl_metadata; '
              'print(json.dumps(query_gpu_egl_metadata(int(sys.argv[2]))))')
    completed = subprocess.run([str(runner.PYTHON), '-c', script, str(Path(root) / 'scripts'),
                                str(physical_gpu)], env=env, cwd=root, capture_output=True,
                               text=True, timeout=30)
    runner.require(completed.returncode == 0, 'GPU/EGL metadata enumeration failed')
    return json.loads(completed.stdout, object_pairs_hook=runner.unique_pairs)


def same_mapping(left, right):
    try:
        return (all(left.get(key) == right.get(key) for key in MAPPING_KEYS if key != 'pci_bus_id')
                and normalized_pci_bus_id(left['pci_bus_id']) == normalized_pci_bus_id(right['pci_bus_id']))
    except (KeyError, RuntimeError):
        return False


def reusable_probe(runtime, mapping, health_events, *, root=ROOT):
    """Accept only actual, accounted evidence with matching current probe code."""
    if not same_mapping(runtime.get('gpu_mapping', {}), mapping):
        return None
    reference = runtime.get('cuda_egl_probe', {})
    if runtime.get('cuda_egl_verified') is not True or not reference:
        return None
    matching = [event for event in health_events if event.get('resource_id') == reference.get('resource_id')]
    if not matching or matching[-1].get('event') != 'completed':
        return None
    if matching[-1].get('source_script_sha256') != runner.digest(Path(root) / 'scripts/qd_ed_gpu_probe.py'):
        return None
    try:
        evidence_path = runner.owned(reference['evidence_path'], runtime['artifact_root'])
        if runner.digest(evidence_path) != reference['evidence_sha256']:
            return None
        evidence = runner.read_json(evidence_path)
        if evidence.get('resource_id') != reference['resource_id']:
            return None
        probe.validate_probe_evidence(evidence, mapping)
        if runner.digest(evidence_path.parent / 'probe-frame.png') != evidence['frame_png_sha256']:
            return None
    except (OSError, KeyError, runner.GateError):
        return None
    return copy.deepcopy(reference)


def find_probe(runtime, mapping, health_events, *, root=ROOT):
    proof = reusable_probe(runtime, mapping, health_events, root=root)
    if proof:
        return proof
    artifact = Path(runtime['artifact_root'])
    paths = sorted((artifact / 'runtime').glob('*manifest*.json'))
    paths += sorted((artifact / 'runtime/resource_queue').glob('*/runtime-manifest.json'))
    for path in paths:
        saved = runner.read_json(path)
        if (saved.get('schema') != runtime.get('schema')
                or saved.get('worktree') != runtime.get('worktree')
                or saved.get('artifact_root') != runtime.get('artifact_root')):
            continue
        proof = reusable_probe(saved, mapping, health_events, root=root)
        if proof:
            return proof
    return None


def no_unfinished(root):
    events = runner.read_events(root / 'data/attempt-ledger.jsonl')
    resources = runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
    snapshot = runner.budget_snapshot(events, resources)
    runner.require(all(group[-1]['event'] in runner.TERMINAL
                       for group in runner.event_groups(events).values())
                   and snapshot['gpu_healthcheck_inflight'] == 0,
                   UNFINISHED_JOURNAL)
    return events, resources


def pending_gate(root, row):
    # Multiple authorized worktrees share journals, but each keeps its own
    # cached state. Refresh only declared, physically linked shared accounting
    # and only after the owner has closed every outstanding transaction.
    with runner.locked(root / 'data/qd-ed-state.lock'):
        state = runner.read_state(root / 'research-state.yaml')
        candidates = candidate_indices(state)
        events, resources = no_unfinished(root)
        migration = state.get('execution_migration', {})
        if migration.get('same_study_budget') is True:
            shared = Path(migration.get('shared_journal_root', ''))
            runner.require(shared.is_absolute(), 'shared journal root is not absolute')
            for name in ('attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl',
                         'gpu-hour-reservation-ledger.jsonl', 'qd-ed-state.lock', 'qd-ed-runner.lock'):
                path = root / 'data' / name
                runner.require(path.is_symlink() and path.resolve() == (shared / name).resolve(),
                               'declared shared journal/lock binding changed')
            runner.sync_state_from_journal(root, events)
            state = runner.read_state(root / 'research-state.yaml')
        runner.check_retry(events, row)
        runner.check_budget(state, events, row, resources,
                            runner.read_events(root / 'data/gpu-hour-reservation-ledger.jsonl'))
        return state, candidates


def append_selection(path, event):
    with Path(path).open('a') as stream:
        stream.write(json.dumps({'time_unix': time.time(), **event}, sort_keys=True, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def update_selected_gpu(root, physical_gpu):
    # Caller holds runner lock; short state lock is never held during a probe.
    with runner.locked(root / 'data/qd-ed-state.lock'):
        no_unfinished(root)
        path = root / 'research-state.yaml'
        state = runner.read_state(path)
        runner.require(physical_gpu in candidate_indices(state), 'GPU selection authorization changed')
        state['gpu_pool'] = [physical_gpu]
        state['authorized_gpu_selection']['selected_physical_gpu'] = physical_gpu
        temporary = path.with_suffix('.yaml.queue-tmp')
        with temporary.open('w') as stream:
            yaml.safe_dump(state, stream, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)


def clone_runtime(runtime, mapping, metadata_path, proof):
    result = copy.deepcopy(runtime)
    old_metadata = runtime.get('egl_device_metadata_path')
    result['files'] = [record for record in result['files'] if record['path'] != old_metadata]
    result['files'].append({'path': str(metadata_path), 'resolved_path': str(metadata_path.resolve()),
                            'size_bytes': metadata_path.stat().st_size, 'sha256': runner.digest(metadata_path)})
    result['egl_device_metadata_path'] = str(metadata_path)
    result['gpu_mapping'] = copy.deepcopy(mapping)
    result['gpu_mapping']['cuda_egl_verified'] = bool(proof)
    result['metadata_mapping_verified'] = True
    result['cuda_egl_verified'] = bool(proof)
    result.pop('cuda_egl_probe', None)
    if proof:
        result['cuda_egl_probe'] = proof
    runner.require({k: v for k, v in result.items() if k not in HARDWARE_RUNTIME_KEYS}
                   == {k: v for k, v in runtime.items() if k not in HARDWARE_RUNTIME_KEYS},
                   'nonhardware runtime identity changed')
    return result


def bind_plan(plan_path, plan, runtime, device, row, events_path, *, root=ROOT):
    """Freeze a hardware-only child plan, keeping the original immutable."""
    physical_gpu = device['physical_gpu']
    with runner.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
        pending_gate(root, row)
        # Reverify source and inputs before changing singleton state binding.
        runner.validate_plan(plan_path, root=root, allow_unverified_gpu=True)
        mapping = current_metadata(physical_gpu, root=root)
        runner.require(mapping['uuid'] == device['uuid'], 'selected GPU inventory identity changed')
        reservation_admission(device)
        runner.gpu_admission(physical_gpu=physical_gpu, expected_uuid=mapping['uuid'])
        resources = runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
        proof = find_probe(runtime, mapping, resources, root=root)
        if (same_mapping(runtime['gpu_mapping'], mapping) and proof
                and runtime.get('cuda_egl_probe') == proof and runtime.get('cuda_egl_verified') is True):
            return Path(plan_path), plan, runtime
        folder = runner.owned(Path(plan['artifact_root']) / 'runtime/resource_queue' / uuid.uuid4().hex,
                              plan['artifact_root'])
        folder.mkdir(parents=True, exist_ok=False)
        metadata_path = folder / 'egl-device-metadata.json'
        runner.durable_json(metadata_path, mapping)
        runtime_path = folder / 'runtime-manifest.json'
        runner.durable_json(runtime_path, clone_runtime(runtime, mapping, metadata_path, proof))
        update_selected_gpu(root, physical_gpu)
        append_selection(events_path, {'event': 'hardware_selected', 'physical_gpu': physical_gpu,
                         'uuid': mapping['uuid'], 'runtime_manifest_path': str(runtime_path),
                         'reused_probe_resource_id': proof['resource_id'] if proof else None})
    # Existing audited APIs acquire their own runner lock; do not nest flock.
    if not proof:
        before_probes = probe_dispatch_ids(root)
        try:
            probe.run_probe(runtime_path, root=root)
        except BaseException:
            # A predispatch admission race must leave the previous frozen
            # plan usable on the next poll. Once a probe dispatches, stop and
            # retain its selected binding for explicit reconciliation.
            if probe_dispatch_ids(root) == before_probes:
                with runner.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
                    update_selected_gpu(root, runner.runtime_gpu(runtime))
            raise
    new_plan = copy.deepcopy(plan)
    new_plan['runtime_manifest_path'] = str(runtime_path)
    new_plan['runtime_manifest_sha256'] = runner.digest(runtime_path)
    new_plan['egl_mapping_verified'] = True
    new_plan['frozen_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    preview_path = folder / 'hardware-environment-preview.json'
    runner.durable_json(preview_path, {
        'schema': 'qd-ed-hardware-environment-preview-v1',
        'environment_public': {'CUDA_VISIBLE_DEVICES': str(physical_gpu),
            'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'MUJOCO_EGL_DEVICE_ID': str(mapping['egl_device_index']),
            'MUJOCO_GL': 'egl', 'PYOPENGL_PLATFORM': 'egl'},
        'parent_nonhardware_preflight_index': plan.get('preflight_index'),
        'note': 'Parent resolved previews describe unchanged scientific/provider inputs; this hardware environment supersedes their device binding.',
    })
    new_plan['hardware_selection'] = {'parent_plan_path': str(Path(plan_path).resolve()),
                                      'parent_plan_sha256': runner.digest(plan_path),
                                      'physical_gpu': physical_gpu, 'uuid': mapping['uuid'],
                                      'hardware_environment_preview': str(preview_path),
                                      'hardware_environment_preview_sha256': runner.digest(preview_path),
                                      'selected_at_unix': time.time()}
    destination = folder / 'plan.json'
    runner.durable_json(destination, new_plan)
    verified, _, new_runtime = runner.validate_plan(destination, root=root)
    append_selection(events_path, {'event': 'hardware_plan_frozen', 'physical_gpu': physical_gpu,
                     'plan_path': str(destination), 'plan_sha256': runner.digest(destination)})
    return destination, verified, new_runtime


def is_admission_race(error):
    return isinstance(error, runner.GateError) and bool(re.fullmatch(
        r'GPU\d+ (?:has external compute processes|has external GPU reservations|memory is \d+ MiB; requires <1024 MiB)', str(error)))


def dispatch_ids(root):
    return {event['attempt_id'] for event in runner.read_events(root / 'data/attempt-ledger.jsonl')
            if event.get('event') == 'dispatched'}


def probe_dispatch_ids(root):
    return {event['resource_id'] for event in runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
            if event.get('event') == 'dispatched'}


def undispatched_admission_race(error, new_events, new_resources=()):
    if is_admission_race(error):
        return True
    # run_plan wraps a failed final predispatch check. Its journal preserves
    # the exact cause, so classify only this narrow resource-admission case.
    terminals = [event for event in new_events if event.get('event') == 'aborted']
    if terminals:
        return all(event.get('failure_class') == 'predispatch_gate'
                   and is_admission_race(runner.GateError(event.get('reason', ''))) for event in terminals)
    # run_probe has a second admission check after a CPU-only reservation.
    # Its public wrapper retains the exact cause in the healthcheck journal.
    resources = [event for event in new_resources if event.get('event') == 'aborted']
    return (str(error) == 'GPU probe failed; runtime readiness remains unchanged'
            and bool(resources) and all(event.get('gpu_process_wall_seconds') == 0
            and is_admission_race(runner.GateError(event.get('reason', ''))) for event in resources))


def run_queue(plan_path, episode_keys, *, poll_seconds=30, idle_seconds=120, status_path=None, root=ROOT,
              sleep=time.sleep, monotonic=time.monotonic, max_polls=None):
    root = Path(root).resolve()
    runner.require(type(poll_seconds) is int and 1 <= poll_seconds <= 60, 'poll interval must be 1..60 seconds')
    runner.require(type(idle_seconds) is int and 0 <= idle_seconds <= 3600,
                   'idle stability window must be 0..3600 seconds')
    runner.require(bool(episode_keys) and len(set(episode_keys)) == len(episode_keys),
                   'explicit unique episode keys required')
    # Establish the owned status path before deeper validation, allowing a
    # durable failure record even when a source/auth/budget check rejects.
    state = runner.read_state(root / 'research-state.yaml')
    artifact = Path(state['artifacts']).resolve()
    status_path = runner.owned(status_path or artifact / 'runtime/available-gpu-queue-status.json', artifact)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    events_path = status_path.with_name(status_path.stem + '-events.jsonl')
    status = {'schema': 'qd-ed-available-gpu-queue-v1', 'pid': os.getpid(),
              'base_plan_path': str(Path(plan_path).resolve()), 'episode_keys': list(episode_keys),
              'idle_stability_seconds': idle_seconds,
              'completed_keys': [], 'results': [], 'status': 'starting'}

    def save(phase, **values):
        status.update(status=phase, updated_unix=time.time(), **values)
        runner.durable_json(status_path, status)

    with runner.locked(root / 'data/qd-ed-available-gpu-queue.lock', nonblocking=True):
        save('starting')
        try:
            # All frozen source/model/input checks remain active while an
            # explicitly unverified new device waits for its admitted probe.
            plan, _, runtime = runner.validate_plan(plan_path, root=root, allow_unverified_gpu=True)
            code_paths = {record['path'] for record in plan['code_files']}
            runner.require({'scripts/qd_ed_available_gpu_queue.py', 'scripts/qd_ed_gpu_probe.py',
                            'scripts/qd_ed_runtime_setup.py'} <= code_paths,
                           'queue/probe/metadata source fingerprints missing')
            rows = {row['episode_key']: row for row in plan['episodes']}
            runner.require(set(episode_keys) <= set(rows), 'requested episode key absent from frozen plan')
            for key in episode_keys:
                runner.require(plan.get('phase_authorization', {}).get(rows[key]['split']) is True,
                               'requested split lacks frozen phase authorization')
                try:
                    pending_gate(root, rows[key])
                except runner.GateError as exc:
                    if str(exc) != UNFINISHED_JOURNAL:
                        raise
            runner.verify_provider(runtime, runner.child_environment(runtime), root=root)
            active_path, polls, idle_windows = Path(plan_path).resolve(), 0, {}
            for key in episode_keys:
                row = rows[key]
                while True:
                    try:
                        state, candidates = pending_gate(root, row)
                    except runner.GateError as exc:
                        if str(exc) != UNFINISHED_JOURNAL:
                            raise
                        idle_windows.clear()
                        polls += 1
                        save('waiting_journal', current_episode_key=key,
                             active_plan_path=str(active_path), selected_physical_gpu=None,
                             gpu_inventory=[], last_resource_reason=str(exc))
                        if max_polls is not None and polls >= max_polls:
                            return status
                        sleep(poll_seconds)
                        continue
                    devices = inventory()
                    update_idle_windows(devices, idle_windows, monotonic(), idle_seconds)
                    device = choose_device(devices, candidates, runner.runtime_gpu(runtime))
                    polls += 1
                    save('waiting' if device is None else 'selected', current_episode_key=key,
                         gpu_inventory=list(devices.values()), active_plan_path=str(active_path),
                         selected_physical_gpu=device['physical_gpu'] if device else None)
                    if device is None:
                        if max_polls is not None and polls >= max_polls:
                            return status
                        sleep(poll_seconds)
                        continue
                    before = dispatch_ids(root)
                    before_probes = probe_dispatch_ids(root)
                    event_count = len(runner.read_events(root / 'data/attempt-ledger.jsonl'))
                    resource_count = len(runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl'))
                    try:
                        active_path, plan, runtime = bind_plan(active_path, plan, runtime, device,
                                                              row, events_path, root=root)
                        # bind_plan returns only after any new probe completed
                        # and the rebound plan validated. A later episode
                        # admission race can safely wait using that new plan.
                        before_probes = probe_dispatch_ids(root)
                        reservation_admission(device)
                        save('running', selected_physical_gpu=device['physical_gpu'],
                             active_plan_path=str(active_path), active_plan_sha256=runner.digest(active_path))
                        result = runner.run_plan(active_path, split=row['split'], iteration=row['iteration'],
                                                 episode_keys=[key], root=root)
                    except runner.GateError as exc:
                        fresh_events = runner.read_events(root / 'data/attempt-ledger.jsonl')[event_count:]
                        fresh_resources = runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')[resource_count:]
                        if (dispatch_ids(root) == before and probe_dispatch_ids(root) == before_probes
                                and undispatched_admission_race(exc, fresh_events, fresh_resources)):
                            append_selection(events_path, {'event': 'admission_race', 'episode_key': key,
                                             'physical_gpu': device['physical_gpu']})
                            idle_windows.pop(device['physical_gpu'], None)
                            save('waiting', last_resource_reason='GPU became busy before dispatch')
                            if max_polls is not None and polls >= max_polls:
                                return status
                            sleep(poll_seconds)
                            continue
                        raise
                    status['completed_keys'].append(key)
                    status['results'].extend(result)
                    save('episode_completed')
                    idle_windows.clear()
                    break
            save('completed')
            return status
        except BaseException as exc:
            # GateError messages are authored public reasons. Other exceptions
            # are reduced to type names so provider/subprocess output is never
            # copied into status files or terminal output.
            reason = str(exc) if isinstance(exc, runner.GateError) else type(exc).__name__
            save('interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed', reason=reason)
            append_selection(events_path, {'event': status['status'], 'reason': reason,
                                          'completed_keys': status['completed_keys']})
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--episode-key', action='append', required=True)
    parser.add_argument('--poll-seconds', type=int, default=30)
    parser.add_argument('--idle-seconds', type=int, default=120,
                        help='Continuous observed idle time required before selecting a GPU (default: 120)')
    parser.add_argument('--status-path', type=Path)
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        result = run_queue(args.plan, args.episode_key, poll_seconds=args.poll_seconds,
                           idle_seconds=args.idle_seconds, status_path=args.status_path)
        print(json.dumps({'status': result['status'], 'completed_keys': result['completed_keys']}))
        return 0
    except BaseException as exc:
        print(json.dumps({'status': 'failed', 'reason': str(exc) if isinstance(exc, runner.GateError)
                          else type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
