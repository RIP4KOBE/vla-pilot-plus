#!/usr/bin/env python3
"""CPU wait queue for exactly one accounted native B1 diagnostic, no episodes."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import sys
import threading
import time

import qd_ed_available_gpu_queue as queue
import qd_ed_final_runner as runner
import qd_ed_policy_native_probe as native


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_RELATIVE = 'scripts/qd_ed_native_probe_queue.py'
RESOURCE_PREFLIGHT_KEY = 'n1_dev_t00_c0'
IDLE_SECONDS = 120
HEARTBEAT_SECONDS = 30
REQUIRED_QUEUE_CODE = {SCRIPT_RELATIVE, native.SCRIPT_RELATIVE,
    'scripts/qd_ed_available_gpu_queue.py', 'scripts/qd_ed_gpu_probe.py',
    'scripts/qd_ed_runtime_setup.py'}


def current_head(root):
    return runner.subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()


def diagnostic_plan(plan_path, root):
    plan, runtime, config = native.validate_inputs(plan_path, root)
    gates = plan.get('phase_authorization', {})
    runner.require(set(gates) == {'dev', 'validation', 'formal'}
                   and all(value is False for value in gates.values()),
                   'native queue requires all scientific phase gates false')
    diagnostic = plan.get('diagnostic_only', {})
    runner.require(diagnostic.get('kind') == 'policy_native_diagnostic'
                   and diagnostic.get('scope') == native.SCOPE
                   and diagnostic.get('synthetic_seed') == native.SYNTHETIC_SEED
                   and diagnostic.get('synthetic_task') == native.SYNTHETIC_TASK
                   and diagnostic.get('timeout_seconds') == 600,
                   'frozen native diagnostic scope changed or missing')
    config_path = runner.owned(diagnostic['policy_configuration_path'], plan['artifact_root'])
    runner.require(runner.digest(config_path) == diagnostic['policy_configuration_sha256']
                   and runner.read_json(config_path) == config, 'frozen native policy configuration changed')
    records = {record['path']: record for record in plan['code_files']}
    runner.require(REQUIRED_QUEUE_CODE <= set(records), 'native queue source fingerprints missing')
    for relative in REQUIRED_QUEUE_CODE:
        runner.require(records[relative]['sha256'] == runner.digest(Path(root) / relative),
                       'native queue source fingerprint changed')
    matching = [row for row in plan['episodes'] if row['episode_key'] == RESOURCE_PREFLIGHT_KEY]
    runner.require(len(matching) == 1, 'immutable C0 resource preflight row missing or ambiguous')
    row = matching[0]
    runner.require(row['split'] == 'dev' and row['iteration'] == 'N1' and row['profile'] == 'C0'
                   and row['task_id'] == 0 and row['budget_bucket'] == 'development'
                   and not row.get('retry_of'), 'C0 resource preflight row identity changed')
    return plan, runtime, row


def waiting_gate(plan_path, plan_hash, plan, row, root):
    runner.require(runner.digest(plan_path) == plan_hash, 'native queue frozen plan changed while waiting')
    runner.require(current_head(root) == plan['source_commit'], 'native queue source HEAD changed')
    runner.verify_files(plan['code_files'], root=root)
    diagnostic = plan['diagnostic_only']
    runner.require(runner.digest(diagnostic['policy_configuration_path'])
                   == diagnostic['policy_configuration_sha256'],
                   'frozen native policy configuration changed while waiting')
    state, candidates = queue.pending_gate(root, row)
    events, resources = queue.no_unfinished(root)
    runner.check_budget(state, events, {'budget_bucket': 'recovery', 'timeout_seconds': 600},
                        resources, runner.read_events(root / 'data/gpu-hour-reservation-ledger.jsonl'))
    return candidates


def run_queue(plan_path, *, root=ROOT, poll_seconds=30, status_path=None,
              sleep=time.sleep, monotonic=time.monotonic, max_polls=None):
    root, plan_path = Path(root).resolve(), Path(plan_path).resolve()
    runner.require(type(poll_seconds) is int and 1 <= poll_seconds <= 60,
                   'native queue poll interval must be 1..60 seconds')
    artifact = Path(runner.read_state(root / 'research-state.yaml')['artifacts']).resolve()
    status_path = runner.owned(status_path or artifact / 'runtime/native-probe-queue-status.json', artifact)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    events_path = status_path.with_name(status_path.stem + '-events.jsonl')
    status = {'schema': 'qd-ed-native-probe-queue-v1', 'pid': os.getpid(),
              'base_plan_path': str(plan_path), 'status': 'starting',
              'scope': native.SCOPE, 'scientific_episodes_authorized': False,
              'scientific_episodes_dispatched': 0,
              'resource_preflight_row_only': RESOURCE_PREFLIGHT_KEY,
              'idle_stability_seconds': IDLE_SECONDS, 'timeout_seconds': 600}
    status_lock, stopped, heartbeat_errors = threading.Lock(), threading.Event(), []

    def save(phase, **values):
        with status_lock:
            runner.require(not heartbeat_errors, 'native queue status heartbeat failed')
            status.update(status=phase, updated_unix=time.time(), **values)
            runner.durable_json(status_path, status)

    def heartbeat():
        while not stopped.wait(HEARTBEAT_SECONDS):
            with status_lock:
                try:
                    status['updated_unix'] = time.time()
                    runner.durable_json(status_path, status)
                except Exception as exc:
                    heartbeat_errors.append(type(exc).__name__)
                    return

    with runner.locked(root / 'data/qd-ed-native-probe-queue.lock', nonblocking=True):
        save('starting')
        thread = threading.Thread(target=heartbeat, name='native-probe-queue-heartbeat', daemon=True)
        thread.start()
        try:
            plan, runtime, row = diagnostic_plan(plan_path, root)
            active_path, plan_hash = plan_path, runner.digest(plan_path)
            original_episodes = queue.dispatch_ids(root)
            idle_windows, polls = {}, 0
            while True:
                try:
                    candidates = waiting_gate(active_path, plan_hash, plan, row, root)
                except runner.GateError as exc:
                    if str(exc) != 'unfinished attempt or healthcheck requires reconciliation':
                        raise
                    # Observe the journal only. Its owner must finish/reconcile;
                    # no GPU query, binding, reconciliation or dispatch here.
                    idle_windows.clear()
                    polls += 1
                    save('waiting_journal', active_plan_path=str(active_path),
                         selected_physical_gpu=None, last_resource_reason=str(exc))
                    if max_polls is not None and polls >= max_polls:
                        return status
                    sleep(poll_seconds)
                    continue
                runner.require(queue.dispatch_ids(root) == original_episodes,
                               'scientific episode journal changed during native queue')
                devices = queue.inventory()
                queue.update_idle_windows(devices, idle_windows, monotonic(), IDLE_SECONDS)
                preferred = runner.runtime_gpu(runtime)
                device = queue.choose_device(devices, candidates,
                    preferred if preferred in candidates else candidates[0])
                polls += 1
                save('waiting' if device is None else 'selected', gpu_inventory=list(devices.values()),
                     selected_physical_gpu=device['physical_gpu'] if device else None,
                     active_plan_path=str(active_path))
                if device is None:
                    if max_polls is not None and polls >= max_polls:
                        return status
                    sleep(poll_seconds)
                    continue
                before_resources = queue.probe_dispatch_ids(root)
                before_resource_count = len(runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl'))
                before_episode_count = len(runner.read_events(root / 'data/attempt-ledger.jsonl'))
                try:
                    active_path, _, _ = queue.bind_plan(active_path, plan, runtime, device, row,
                                                        events_path, root=root)
                    plan, runtime, rebound_row = diagnostic_plan(active_path, root)
                    runner.require(rebound_row == row, 'native hardware binding changed preflight identity')
                    plan_hash = runner.digest(active_path)
                    waiting_gate(active_path, plan_hash, plan, row, root)
                    queue.reservation_admission(device)
                    save('running_diagnostic', active_plan_path=str(active_path), active_plan_sha256=plan_hash)
                    terminal = native.run_probe(active_path, root=root, timeout_seconds=600)
                    save('diagnostic_returned', result=terminal)
                    runner.require(queue.dispatch_ids(root) == original_episodes,
                                   'scientific episode dispatched during native diagnostic')
                    runner.require(terminal.get('event') == 'completed',
                                   terminal.get('reason', 'native diagnostic did not complete'))
                    runner.require(terminal.get('kind') == 'policy_native_diagnostic'
                                   and terminal.get('scope') == native.SCOPE
                                   and terminal.get('plan_sha256') == plan_hash
                                   and terminal.get('source_commit') == plan['source_commit']
                                   and terminal.get('physical_gpu') == runner.runtime_gpu(runtime),
                                   'completed native diagnostic resource contract mismatch')
                except runner.GateError as exc:
                    fresh_episodes = runner.read_events(root / 'data/attempt-ledger.jsonl')[before_episode_count:]
                    fresh_resources = runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')[before_resource_count:]
                    if (queue.dispatch_ids(root) == original_episodes
                            and queue.probe_dispatch_ids(root) == before_resources
                            and queue.undispatched_admission_race(exc, fresh_episodes, fresh_resources)):
                        idle_windows.pop(device['physical_gpu'], None)
                        queue.append_selection(events_path, {'event': 'predispatch_resource_race',
                                                             'physical_gpu': device['physical_gpu']})
                        save('waiting', last_resource_reason='GPU became busy before any resource dispatch')
                        if max_polls is not None and polls >= max_polls:
                            return status
                        sleep(poll_seconds)
                        continue
                    raise
                save('completed')
                queue.append_selection(events_path, {'event': 'native_diagnostic_completed',
                    'resource_id': terminal['resource_id'], 'scientific_episodes_dispatched': 0})
                return status
        except BaseException as exc:
            reason = str(exc) if isinstance(exc, runner.GateError) else type(exc).__name__
            phase = 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed'
            save(phase, reason=reason)
            queue.append_selection(events_path, {'event': phase, 'reason': reason})
            raise
        finally:
            stopped.set()
            thread.join(timeout=1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--poll-seconds', type=int, default=30)
    parser.add_argument('--status-path', type=Path)
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        result = run_queue(args.plan, poll_seconds=args.poll_seconds, status_path=args.status_path)
        print(runner.json.dumps({'status': result['status'], 'scientific_episodes_dispatched': 0}))
        return 0
    except BaseException as exc:
        print(runner.json.dumps({'status': 'failed', 'reason': str(exc) if isinstance(exc, runner.GateError)
                                 else type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
