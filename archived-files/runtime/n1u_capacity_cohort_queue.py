"""Resource-only wrapper: hold the existing shared runner lock across the final N1U30 cohort.

Production queue, plan, source, budgets and episode identities are unchanged.
Nested requests for this one already-held lock are reentrant only in this PID.
All state/admission/other locks retain the original implementation.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import json
import os
import signal
import sys
import time


@contextmanager
def held_runner_lease(runner, path):
    path = Path(path).resolve()
    original = runner.locked
    with original(path, nonblocking=True):
        owner = os.getpid()
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)

        @contextmanager
        def nested(requested, *, nonblocking=False):
            if Path(requested).resolve() == path:
                current = path.stat()
                runner.require(os.getpid() == owner, 'cohort lease belongs to another PID')
                runner.require((current.st_dev, current.st_ino) == identity,
                               'shared runner lock inode changed')
                yield
            else:
                with original(requested, nonblocking=nonblocking):
                    yield
        runner.locked = nested
        try:
            yield
        finally:
            runner.locked = original


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    root = Path(manifest['worktree'])
    sys.path.insert(0, str(root / 'scripts'))
    import qd_ed_final_runner as r
    import qd_ed_available_gpu_queue as q
    r.require(r.digest(Path(__file__)) == manifest['wrapper_sha256'], 'resource wrapper changed')
    plan_path = Path(manifest['plan_path'])
    r.require(r.digest(plan_path) == manifest['plan_sha256'], 'frozen N1U plan changed')
    plan = r.read_json(plan_path)
    keys = manifest['episode_keys']
    r.require(keys == [row['episode_key'] for row in plan['episodes']] and len(keys) == 30,
              'N1U original full cohort order changed')
    r.require(all(row['iteration'] == 'N1U' for row in plan['episodes']), 'unexpected cohort identity')
    r.require([row['profile'] for row in plan['episodes'][20:]] == ['N1'] * 10,
              'N1 must follow the full control cohort')
    groups = r.event_groups(r.read_events(root/'data/attempt-ledger.jsonl'))
    r.require(not any(group[0].get('identity', {}).get('iteration') == 'N1U' for group in groups.values()),
              'N1U has already reserved an attempt; no automatic cohort restart')
    status = r.owned(manifest['status_path'], plan['artifact_root'])
    lease_events = r.owned(manifest['lease_events_path'], plan['artifact_root'])
    r.require(not status.exists(), 'new resource status path already exists')
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    argv = ['--plan',str(plan_path),'--poll-seconds','5','--idle-seconds','120',
            '--status-path',str(status)]
    for key in keys:
        argv.extend(['--episode-key',key])
    def event(kind):
        with lease_events.open('a') as stream:
            stream.write(json.dumps({'event':kind,'pid':os.getpid(),'time_unix':time.time(),
                                     'manifest_sha256':r.digest(args.manifest)})+'\n')
            stream.flush();os.fsync(stream.fileno())
    try:
        while True:
            try:
                with held_runner_lease(r, root/'data/qd-ed-runner.lock'):
                    snapshot = r.budget_snapshot(r.read_events(root/'data/attempt-ledger.jsonl'),
                                                r.read_events(root/'data/gpu-healthcheck-ledger.jsonl'))
                    r.require(snapshot['running'] == 0 and snapshot['gpu_healthcheck_inflight'] == 0,
                              'unfinished shared attempt requires review before cohort lease')
                    r.require(snapshot['by_bucket']['development'] + len(keys) <= r.BUCKETS['development'],
                              'insufficient development slots for complete N1U cohort')
                    r.require(snapshot['dispatched'] + len(keys) <= 240,
                              'insufficient total attempt slots for complete N1U cohort')
                    event('shared_cohort_lock_acquired')
                    try:
                        return q.main(argv)
                    finally:
                        event('shared_cohort_lock_releasing')
            except r.LockBusyError as exc:
                r.require(exc.lock_path == (root/'data/qd-ed-runner.lock').resolve(),
                          'unexpected lock contention outside shared cohort lock')
                r.durable_json(status,{'status':'waiting_cohort_lock','pid':os.getpid(),
                    'episode_keys':keys,'current_episode_key':keys[0],
                    'completed_keys':[],'updated_unix':time.time(),
                    'last_resource_reason':'another runner holds shared study lock'})
                time.sleep(5)
    except BaseException as exc:
        r.durable_json(status, {'status': 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
            'pid': os.getpid(), 'episode_keys': keys, 'completed_keys': [],
            'updated_unix': time.time(), 'reason': str(exc) if isinstance(exc, r.GateError) else type(exc).__name__})
        event('resource_wrapper_interrupted' if isinstance(exc,KeyboardInterrupt) else 'resource_wrapper_failed')
        raise


if __name__ == '__main__':
    raise SystemExit(main())
