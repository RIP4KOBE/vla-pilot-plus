#!/usr/bin/env python3
"""Run/resume the approved N1V30 cohort with at most six explicit recoveries."""
import argparse
from contextlib import contextmanager
import copy
import os
from pathlib import Path
import signal
import time

import qd_ed_available_gpu_queue as q
import qd_ed_final_runner as r
import qd_ed_n1v as protocol


@contextmanager
def held_runner_lease(path):
    """Only this already-held inode is reentrant, only in the acquiring PID."""
    path = Path(path).resolve()
    original = r.locked
    with original(path, nonblocking=True):
        owner = os.getpid(); stat = path.stat(); identity = (stat.st_dev, stat.st_ino)
        @contextmanager
        def nested(requested, *, nonblocking=False):
            if Path(requested).resolve() == path:
                current = path.stat()
                r.require(os.getpid() == owner and (current.st_dev, current.st_ino) == identity,
                          'N1V shared lease PID/inode changed')
                yield
            else:
                with original(requested, nonblocking=nonblocking):
                    yield
        r.locked = nested
        try:
            yield
        finally:
            r.locked = original


def validate_cohort(plan):
    expected = [(task, profile) for task in range(10)
                for profile in (('Q0', 'C0', 'N1') if task % 2 == 0 else ('C0', 'Q0', 'N1'))]
    r.require([(row['task_id'], row['profile']) for row in plan['episodes']] == expected
              and all(row['iteration'] == 'N1V' and not row.get('retry_of') for row in plan['episodes']),
              'N1V30 original task-interleaved primary order changed')
    r.require(plan.get('n1v_recovery') == protocol.CONTRACT, 'N1V recovery contract changed')


def cell_action(events, row, plan):
    """Return one valid representative, an undispatched primary, or one recovery."""
    groups = r.event_groups(events)
    prior = [g for g in groups.values() if g[0]['identity'] == r.episode_identity(row)]
    for group in prior:
        last = group[-1]
        r.require(last['event'] in r.TERMINAL, 'N1V unfinished attempt requires explicit reconciliation')
        r.require(last.get('source_commit') == plan['source_commit']
                  and last.get('n1v_authorization_sha256') == protocol.AUTH_SHA
                  and last.get('runtime_manifest_sha256') == plan['runtime_manifest_sha256']
                  and last.get('init_row_sha256') == row['init_row_sha256'],
                  'N1V existing attempt differs from frozen source/runtime/input authority')
    dispatched = [g for g in prior if any(e['event'] == 'dispatched' for e in g)]
    valid = [g[-1] for g in dispatched if g[-1].get('outcome_valid') is True]
    if valid:
        r.require(len(valid) == 1 and dispatched[-1][-1] == valid[0], 'N1V duplicate or reordered valid cell')
        return 'completed', valid[0]
    if not dispatched:
        return 'primary', row
    last = dispatched[-1][-1]
    retry = {**row, 'episode_key': row['episode_key'] + '_recovery1',
             'budget_bucket': 'recovery', 'retry_of': last['attempt_id']}
    r.check_retry(events, retry)
    return 'recovery', retry


def mechanism_audit(terminal):
    """Identity/activity check, without a task-success or coverage threshold."""
    output = Path(terminal['output_dir'])
    metrics = r.read_events(output / 'eds_eval/eds_metrics.jsonl')
    active = [m for m in metrics if m.get('qd_archive_active_for_chunk')]
    result = {'attempt_id': terminal['attempt_id'], 'task_id': terminal['identity']['task_id'],
              'profile': terminal['identity']['profile'], 'success': terminal['success'],
              'guided_chunks': len(metrics), 'active_qd_chunks': len(active),
              'metrics_sha256': r.digest(output / 'eds_eval/eds_metrics.jsonl') if metrics else None}
    if terminal['identity']['profile'] == 'N1':
        for m in active:
            r.require(m['qd_descriptor'] == 'target_distance_gripper_duty_v1'
                      and m['qd_descriptor_axes'] == [{'name': 'target_distance', 'unit': 'm'},
                          {'name': 'positive_gripper_command_duty', 'unit': 'fraction'}],
                      'N1V N1 descriptor/axis implementation mismatch')
            parents = m['qd_parent_descriptor_values_by_iter']
            r.require(isinstance(parents, list) and all(isinstance(batch, list) for batch in parents),
                      'N1V parent sampling telemetry missing')
        result['sampled_parent_count'] = sum(len(batch) for m in active for batch in m['qd_parent_descriptor_values_by_iter'])
        result['parent_batches_with_multiple_duties'] = sum(len({d[1] for d in batch}) > 1
            for m in active for batch in m['qd_parent_descriptor_values_by_iter'])
    return result


def run(plan_path, status_path, *, root=r.ROOT):
    root = Path(root); plan_path = Path(plan_path).resolve()
    plan = r.read_json(plan_path); validate_cohort(plan)
    status_path = r.owned(status_path, plan['artifact_root']); status_path.parent.mkdir(parents=True, exist_ok=True)
    status = {'schema': 'qd-ed-n1v-supervisor-v1', 'pid': os.getpid(),
              'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              'plan_path': str(plan_path), 'plan_sha256': r.digest(plan_path),
              'source_commit': plan['source_commit'], 'physical_gpu': 2,
              'primary_planned': 30, 'recovery_limit': 6, 'completed_keys': [], 'mechanism_audits': []}
    def save(phase, **values):
        status.update(status=phase, updated_unix=time.time(), **values)
        r.durable_json(status_path, status)
    save('starting')
    try:
        with held_runner_lease(root / 'data/qd-ed-runner.lock'):
            plan, _, runtime = r.validate_plan(plan_path, root=root)
            r.require(r.runtime_gpu(runtime) == 2, 'N1V requires physical GPU2')
            # A same-boot proven device is mandatory; do not add unplanned probes.
            mapping = q.current_metadata(2, root=root)
            proof = q.find_probe(runtime, mapping, r.read_events(root / 'data/gpu-healthcheck-ledger.jsonl'), root=root)
            r.require(q.same_mapping(runtime['gpu_mapping'], mapping) and proof == runtime.get('cuda_egl_probe')
                      and proof is not None, 'N1V approved GPU2 readiness proof changed; review required')
            events = r.read_events(root / 'data/attempt-ledger.jsonl')
            snap = r.budget_snapshot(events, r.read_events(root / 'data/gpu-healthcheck-ledger.jsonl'))
            cohort = [g for g in r.event_groups(events).values() if g[0]['identity']['iteration'] == 'N1V'
                      and any(e['event'] == 'dispatched' for e in g)]
            primary_used = sum(not g[0].get('retry_of') for g in cohort)
            recovery_used = sum(bool(g[0].get('retry_of')) for g in cohort)
            r.require(snap['by_bucket']['development'] + 30 - primary_used <= protocol.CAPS['development']
                      and snap['by_bucket']['recovery'] + 6 - recovery_used <= protocol.CAPS['recovery']
                      and snap['dispatched'] + 36 - len(cohort) + max(0,60-snap['by_bucket']['validation'])
                          + max(0,40-snap['by_bucket']['formal']) <= 250,
                      'N1V full remaining cohort/recovery capacity no longer fits approved budget')
            for row in plan['episodes']:
                while True:
                    events = r.read_events(root / 'data/attempt-ledger.jsonl')
                    action, item = cell_action(events, row, plan)
                    if action == 'completed':
                        status['completed_keys'].append(row['episode_key'])
                        status['mechanism_audits'].append(mechanism_audit(item))
                        save('cell_completed', current_episode_key=row['episode_key'], valid_representatives=len(status['completed_keys']))
                        break
                    active_path = plan_path
                    if action == 'recovery':
                        recovery = copy.deepcopy(plan); recovery['episodes'] = [item]
                        recovery['n1v_recovery_parent'] = {'path': str(plan_path), 'sha256': r.digest(plan_path),
                                                          'retry_of': item['retry_of']}
                        active_path = status_path.parent / (item['episode_key'] + '-plan.json')
                        if active_path.exists():
                            r.require(r.read_json(active_path) == recovery, 'N1V frozen recovery plan changed')
                        else:
                            r.durable_json(active_path, recovery)
                    queue_status = status_path.parent / (item['episode_key'] + '-queue.json')
                    save('running_' + action, current_episode_key=item['episode_key'],
                         active_plan_path=str(active_path), queue_status_path=str(queue_status))
                    before = set(r.event_groups(events))
                    try:
                        q.run_queue(active_path, [item['episode_key']], root=root, poll_seconds=5,
                                    idle_seconds=120, status_path=queue_status)
                    except r.GateError:
                        fresh = [g for key, g in r.event_groups(r.read_events(root / 'data/attempt-ledger.jsonl')).items()
                                 if key not in before and any(e['event'] == 'dispatched' for e in g)]
                        if len(fresh) != 1 or fresh[0][-1].get('failure_detail') != 'n1v_stage_timeout':
                            raise
                        # The next cell_action enforces identity, one per cell,
                        # six total, and refuses a failed recovery or valid failure.
                        save('stage_timeout_recorded', infrastructure_attempt_id=fresh[0][-1]['attempt_id'])
            save('development_completed', current_episode_key=None)
            return status
    except BaseException as exc:
        save('interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'stopped_incomplete',
             reason=str(exc) if isinstance(exc, r.GateError) else type(exc).__name__)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    args = parser.parse_args()
    def interrupted(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    return run(args.plan, args.status)


if __name__ == '__main__':
    main()
