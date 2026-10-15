"""One-time authorized migration: finish the active episode, then hold old lease."""
import datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import time

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
X = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
D = Path(__file__).resolve().parent
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r

pid = 3262566
proc = Path('/proc', str(pid))
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
expected_ticks = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19] if proc.exists() else None
authority = D / 'authorization.json'
assert r.digest(authority) == '4026c141ff9bd06f31734c0a43122327b359c35bd847670f641961df9ce81f47'
assert r.read_json(authority)['max_owned_workers_combined'] == 2
assert not (D / 'drain-result.json').exists()
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
while True:
    with r.locked(W / 'data/qd-ed-state.lock'):
        events = r.read_events(W / 'data/attempt-ledger.jsonl')
        resources = r.read_events(W / 'data/gpu-healthcheck-ledger.jsonl')
        groups = r.event_groups(events)
        inflight = [g[-1]['attempt_id'] for g in groups.values() if g[-1]['event'] not in r.TERMINAL]
        health = {}
        for event in resources:
            health[event['resource_id']] = event
        live_health = [key for key, value in health.items() if value['event'] not in ('completed', 'aborted')]
        if not inflight and not live_health:
            own = [g for g in groups.values() if Path(g[0]['output_dir']).is_relative_to(Path('/mnt/data/shared2/hynx/VLA-Pilot++') / X.name)]
            latest = max((g[-1] for g in own), key=lambda e: e['time_unix']) if own else None
            artifact_ready = latest is None or ((Path(latest['output_dir']) / 'attempt-result.json').exists() and
                r.read_json(Path(latest['output_dir']) / 'attempt-result.json') == latest)
            if artifact_ready:
                signalled = False
                if proc.exists():
                    assert (proc / 'cwd').resolve() == X
                    assert (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19] == expected_ticks
                    assert any(Path(token.decode()).name == 'qd_ed_n1v_supervise.py' for token in (proc / 'cmdline').read_bytes().split(b'\0') if token)
                    # The state lock prevents a subsequent reservation while this signal is sent.
                    os.kill(pid, signal.SIGTERM)
                    signalled = True
                r.durable_json(D / 'drain-result.json', {
                    'schema': 'two-study-safe-drain-v1', 'utc': now(), 'boot_id': boot,
                    'supervisor_pid': pid, 'proc_start_ticks': expected_ticks,
                    'signal': 'SIGTERM' if signalled else None,
                    'inflight_attempts': [], 'inflight_healthchecks': [],
                    'latest_counterpart_terminal_id': latest['attempt_id'] if latest else None,
                    'latest_terminal_artifact_matches_journal': artifact_ready,
                    'active_episode_interrupted': False,
                    'authorization_sha256': r.digest(authority)})
                break
    r.durable_json(D / 'drain-status.json', {'status': 'waiting_for_current_episode_terminal', 'utc': now(), 'inflight_attempt_ids': inflight, 'inflight_health_ids': live_health, 'target_supervisor_pid': pid})
    time.sleep(1)

deadline = time.monotonic() + 45
with (W / 'data/qd-ed-runner.lock').open('a+') as lease:
    while True:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() > deadline:
                raise RuntimeError('Shared supervisor did not release old lease; no force kill or migration')
            time.sleep(0.2)
    with r.locked(W / 'data/qd-ed-state.lock'):
        assert not any(g[-1]['event'] not in r.TERMINAL for g in r.event_groups(r.read_events(W / 'data/attempt-ledger.jsonl')).values())
        held = {'schema': 'two-study-migration-lease-v1', 'status': 'OLD_SHARED_RUNNER_LEASE_HELD_FOR_MIGRATION',
                'utc': now(), 'pid': os.getpid(), 'boot_id': boot,
                'lock_path': str(W / 'data/qd-ed-runner.lock'), 'lock_inode': os.fstat(lease.fileno()).st_ino,
                'drain_result_sha256': r.digest(D / 'drain-result.json')}
        r.durable_json(D / 'migration-lease.json', held)
    print(json.dumps(held), flush=True)
    while not (D / 'release-migration-lease.json').exists():
        time.sleep(1)
    release = r.read_json(D / 'release-migration-lease.json')
    assert release.get('authorization_sha256') == r.digest(authority)
    assert release.get('migration_validated') is True
    fcntl.flock(lease, fcntl.LOCK_UN)
    r.durable_json(D / 'migration-lease-released.json', {**held, 'status': 'RELEASED_AFTER_VALIDATED_MIGRATION', 'released_utc': now()})
    print('Migration lease released after verified split.', flush=True)
