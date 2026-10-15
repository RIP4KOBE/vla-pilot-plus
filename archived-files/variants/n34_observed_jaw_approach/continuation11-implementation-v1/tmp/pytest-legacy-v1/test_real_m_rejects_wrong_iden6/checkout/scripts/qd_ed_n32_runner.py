"""Root-invoked N32 production adapter. No authority creation or automatic recovery."""
import argparse
import datetime as dt
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import time

from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts import qd_ed_n32_contract as c, qd_ed_n32_bridge as b
from scripts import qd_ed_n32_release as release, qd_ed_n32_supervise as supervisor
from scripts import qd_ed_n32_worker as worker


def process_identity(pid):
    w.require(type(pid) is int and pid > 0, 'invalid child PID')
    return {'pid': pid, 'proc_start_ticks': Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19],
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def cleanup_owned(process, identity):
    """Signal only this parent's unreaped Popen child on lifecycle timeout.

    No PID/group lookup creates a new handle. Popen.send_signal rechecks waitpid
    under its child lock; an exited, unreaped child cannot have its PID reused.
    The adapter is the sole waiter and never restores a Popen from journal data.
    """
    def send(sig):
        if process.poll() is not None:
            return
        w.require(identity == process_identity(process.pid), 'owned child identity changed')
        stat = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()
        w.require(int(stat[1]) == os.getpid(), 'process is not this executor child')
        process.send_signal(sig)
    send(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        send(signal.SIGKILL)
        process.wait(timeout=30)


def wait_worker(process, started, identity):
    """Monitor queries share the episode deadline; loss of telemetry is INVALID.

    A failed query does not signal the worker. Retain the parent timer while it
    settles, and clean up the exact child only if the episode deadline expires.
    """
    deadline = started + 1800
    def monitor(child, remaining):
        def bounded_run(command, **kwargs):
            left = deadline - time.monotonic()
            if left <= 0:
                raise subprocess.TimeoutExpired('owned episode', 1800)
            kwargs['timeout'] = min(kwargs.get('timeout', left), left)
            return subprocess.run(command, **kwargs)
        r.check_exclusive_gpu(child, run=bounded_run, physical_gpu=7)
    try:
        return r.wait_exclusively(process, max(0., deadline-time.monotonic()), physical_gpu=7, monitor=monitor)
    except (KeyboardInterrupt, SystemExit):
        raise  # External cancellation never signals a live episode.
    except BaseException as exc:
        if isinstance(exc, subprocess.TimeoutExpired) and exc.cmd == 'owned episode':
            raise
        if process.poll() is None:
            try:
                process.wait(timeout=max(0., deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                cleanup_owned(process, identity)
        raise  # Even an eventual exit0 cannot repair missing exclusivity telemetry.


def journal_prefix(path):
    raw = Path(path).read_bytes() if Path(path).exists() else b''
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def device_check():
    from scripts import qd_ed_available_gpu_queue as queue
    devices = queue.inventory()
    w.require(7 in devices and devices[7]['uuid'] == c.GPU_UUID, 'assigned GPU UUID')
    queue.reservation_admission(devices[7])
    return r.gpu_admission(physical_gpu=7, expected_uuid=c.GPU_UUID)


def check_probe(runtime, resources, root):
    from scripts import qd_ed_available_gpu_queue as queue
    w.require(queue.reusable_probe(runtime, runtime['gpu_mapping'], resources, root=root) is not None,
              'hash-bound accounted GPU/EGL proof unavailable; no automatic probe')


def snapshot(root, authority):
    for name, anchor in authority['ledger_prefixes'].items():
        w.require(name in {'attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl', 'gpu-hour-reservation-ledger.jsonl'}, 'unexpected ledger anchor')
        release.prefix(root / 'data' / name, anchor)
    w.require({'attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl'} <= set(authority['ledger_prefixes']), 'historical charge anchors missing')
    events = r.read_events(root / 'data/attempt-ledger.jsonl')
    resources = r.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
    reservations = r.read_events(root / 'data/gpu-hour-reservation-ledger.jsonl')
    return r.read_state(root / 'research-state.yaml'), events, resources, reservations


def existing_handles(plan, events):
    """Read only N32 output identities; never signal or infer a new PID owner."""
    groups = r.event_groups(events)
    unsettled = []
    for row in plan['episodes']:
        output = Path(w.read_ref(plan['expected_manifests'][row['episode_key']])['output_dir'])
        if not output.exists() and not output.is_symlink():
            continue
        group = groups.get(row['episode_key'])
        if not group or group[-1]['event'] not in r.TERMINAL:
            unsettled.append({'episode_key': row['episode_key'], 'status': 'ORPHAN_OR_UNSETTLED'})
            continue
        try:
            record = r.read_json(output / 'process.json')
            expected = {k: record[k] for k in ('pid', 'boot_id', 'proc_start_ticks')}
            try:
                actual = process_identity(record['pid'])
            except FileNotFoundError:
                continue
            if actual == expected:
                unsettled.append({'episode_key': row['episode_key'], 'status': 'LIVE'})
        except (OSError, ValueError, KeyError, TypeError, r.GateError):
            unsettled.append({'episode_key': row['episode_key'], 'status': 'UNKNOWN'})
    return unsettled


def execute_one(plan_ref, release_ref):
    """One primary, or a read-only reconciled stop. All writes require release."""
    plan, runtime, authority = release.validate_release(plan_ref, release_ref)
    root = Path(plan['worktree']).resolve()
    with r.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
        with r.locked(root / 'data/qd-ed-state.lock'):
            plan, runtime, authority = release.validate_release(plan_ref, release_ref)
            state, events, resources, reservations = snapshot(root, authority)
            w.require(state['run_name'] == plan['run_name'] and Path(state['artifacts']).resolve() == Path(runtime['artifact_root']).resolve(), 'owning run identity')
            def verify_existing(row, final):
                release.prefix(root / 'data/attempt-ledger.jsonl', final['ledger_prefix'])
                recorded = w.read_ref(c.ref(Path(final['output_dir']) / 'attempt-result.json'))
                w.require(recorded == final, 'terminal artifact/journal differs')
                return worker.verify_terminal(plan_ref, row, final, release_ref)
            reconciled = supervisor.reconcile(plan, events, verify_existing, live_handles=existing_handles(plan, events))
            if reconciled['next_row'] is None:
                return reconciled
            row = reconciled['next_row']
            # Reject every foreign or unknown unsettled handle, including reservations.
            w.require(all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(events).values()), 'unsettled/live ledger')
            # STOP/time/accounting checked before even probing the device.
            release.admission(plan, authority, state, events, resources, reservations, row,
                              now=dt.datetime.now(dt.timezone.utc), gpu_idle=True)
            check_probe(runtime, resources, root)
            admission = device_check()
            env = r.child_environment(runtime)
            r.verify_provider(runtime, env, root=root)
            r.runtime_gpu(runtime, state)
            plan, runtime, authority = release.validate_release(plan_ref, release_ref)
            state, current, resources, reservations = snapshot(root, authority)
            w.require(current == events, 'ledger changed under locks')
            admission = device_check()
            release.admission(plan, authority, state, current, resources, reservations, row,
                              now=dt.datetime.now(dt.timezone.utc), gpu_idle=True)
            manifest = w.read_ref(plan['expected_manifests'][row['episode_key']])
            output = Path(manifest['output_dir'])
            r.owned(output, plan['artifact_root'])
            w.require(not output.exists() and not output.is_symlink(), 'output exists: no replay')
            # A deterministic key is unique across the entire journal, not just N32.
            w.require(not any(e['attempt_id'] == row['episode_key'] or e.get('episode_key') == row['episode_key'] for e in events), 'global attempt replay')
            output.mkdir(parents=True)
            context_path = output / 'n32-worker-context.json'
            w.atomic_json(context_path, worker.context_for(plan_ref, row, release_ref))
            context_ref = c.ref(context_path)
            command = [manifest['argv'][0], '-m', 'scripts.qd_ed_n32_worker', '--context', str(context_path), '--context-sha256', context_ref['sha256']]
            base = {'attempt_id': row['episode_key'], 'episode_key': row['episode_key'], 'identity': supervisor.c_identity(row),
                    'budget_bucket': row['budget_bucket'], 'plan_sha256': plan_ref['sha256'], 'release': release_ref,
                    'source_commit': plan['source']['commit'], 'runtime_manifest_sha256': plan['runtime']['sha256'],
                    'runtime_inventory_sha256': plan['runtime_inventory_sha256'], 'init_row_sha256': row['init_row_sha256'],
                    'output_dir': str(output), 'physical_gpu': 7, 'retry_of': None, 'recovery_of': None,
                    'ledger_prefix': journal_prefix(root / 'data/attempt-ledger.jsonl'), 'context': context_ref,
                    'stage_backend': 'codex_cli', 'stage_model': 'gpt-6-astra', 'stage_condition': r.stage_condition(runtime)}
            r.append_event_locked(root, {**base, 'event': 'reserved', 'time_unix': time.time(), 'admission': admission})
            w.atomic_json(output / 'command.json', {'argv': command, 'main_argv': manifest['argv'], 'context': context_ref})
            # Recheck STOP after durable reservation. Rejection leaves an unsettled
            # primary for root review, never a retryable/zero-charge synthetic outcome.
            w.require(not Path(plan['stop_path']).exists() and not Path(plan['stop_path']).is_symlink(), 'STOP after reservation')
            end = dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00'))
            w.require(dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1840) <= end, 'deadline after reservation')
            r.append_event_locked(root, {**base, 'event': 'dispatched', 'time_unix': time.time(), 'timeout_seconds': 1800})
        started = time.monotonic()
        process = None
        process_finished = None
        identity = None
        outcome = None
        try:
            with (output / 'runner.log').open('w') as log:
                process = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.PIPE, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                identity = process_identity(process.pid)
                record = {**identity, 'attempt_id': row['episode_key'], 'context': context_ref, 'release': release_ref}
                w.atomic_json(output / 'process.json', record)
                process.stdin.write(b'G'); process.stdin.flush(); process.stdin.close()
                code = wait_worker(process, started, identity)
                process_finished = time.monotonic()
                w.require(code == 0, 'worker exit not zero')
            outcome = r.validate_result(output, row, b.profiles(root)['profiles'][row['profile']], runtime)
            outcome['n32_worker_receipt'] = c.ref(output / 'eds_eval/n32-worker-receipt.json')
            terminal = {**base, **outcome, 'event': 'valid', 'time_unix': time.time(),
                        'gpu_process_wall_seconds': (process_finished or time.monotonic()) - started}
            worker.verify_terminal(plan_ref, row, terminal, release_ref)
        except BaseException as exc:
            if isinstance(exc, subprocess.TimeoutExpired) and exc.cmd == 'owned episode' and process is not None:
                w.require(identity is not None, 'missing owned child identity; leave unsettled')
                cleanup_owned(process, identity)
                process_finished = time.monotonic()
            # An unknown/live process stays dispatched and blocks every new launch.
            # Root reconciles its eventual cost; STOP/interrupt never kills it.
            if process is not None and process.poll() is None:
                raise
            _, outcome = r.failed_outcome(exc, output, row, launch_failed=process is None, runtime=runtime)
            outcome.update(outcome_valid=False, success=None, task_failure=False, retryable_infrastructure=False,
                           classification='INVALID', required_cost_telemetry_complete=False)
            terminal = {**base, **outcome, 'event': 'aborted', 'time_unix': time.time(),
                        'gpu_process_wall_seconds': (process_finished or time.monotonic()) - started}
        terminal['gpu_time_measurement'] = 'exclusive GPU7 process wall-time upper bound including audits and cleanup'
        with r.locked(root / 'data/qd-ed-state.lock'):
            r.append_event_locked(root, terminal)
            w.atomic_json(output / 'attempt-result.json', terminal)
        return {'status': 'VALID' if terminal['outcome_valid'] is True else 'INVALID_STOP', 'terminal': terminal}


def launch(plan_ref, release_ref):
    while True:
        result = execute_one(plan_ref, release_ref)
        if result['status'] != 'VALID':
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'plan-sha256', 'release', 'release-sha256'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = launch({'path': str(Path(args.plan).resolve()), 'sha256': args.plan_sha256},
                    {'path': str(Path(args.release).resolve()), 'sha256': args.release_sha256})
    print(result['status'])


if __name__ == '__main__':
    main()
