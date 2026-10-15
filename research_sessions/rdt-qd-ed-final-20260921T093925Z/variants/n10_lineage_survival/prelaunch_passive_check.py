#!/usr/bin/env python3
"""Read-only plan, private-budget, GPU3 and storage admission snapshot."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'study_worktree'
sys.path.insert(0, str(ROOT / 'scripts'))
import qd_ed_final_runner as runner
import qd_ed_available_gpu_queue as queue
import qd_ed_n7_passive_diagnostic as diagnostic


def free_gb(path):
    stat = os.statvfs(path)
    return round(stat.f_bavail * stat.f_frsize / 10**9, 2)


def main():
    path = diagnostic.RUN_DIR / 'plan.frozen.v2.json'
    plan, _, runtime = runner.validate_plan(path, root=ROOT)
    state = runner.read_state(ROOT / 'research-state.yaml')
    events = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
    resources = runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl')
    reservations = runner.read_events(ROOT / 'data/gpu-hour-reservation-ledger.jsonl')
    snapshot = runner.budget_snapshot(events, resources)
    runner.require(snapshot['dispatched'] == state['budget']['dispatched']
                   and abs(snapshot['gpu_hours_consumed'] -
                           state['budget']['gpu_hours_consumed']) < 1e-8,
                   'private ledger and state differ')
    runner.require(diagnostic.RUN_DIR.resolve().is_relative_to(
                   (ROOT.parent / 'artifacts').resolve()),
                   'attempt index is not on mounted artifact volume')
    runner.require((HERE / 'diagnostic_runs').resolve() ==
                   diagnostic.RUN_DIR.resolve(), 'variant-local artifact link differs')
    runner.require(len(plan['episodes']) == 4 and
                   all(row['split'] == 'dev' and row['budget_bucket'] == 'development'
                       for row in plan['episodes']), 'non-Dev row in diagnostic plan')
    gpu = queue.inventory().get(3)
    runner.require(gpu is not None, 'GPU3 absent')
    queue.reservation_admission(gpu)
    gpu_admission = runner.gpu_admission(
        physical_gpu=3, expected_uuid=runtime['gpu_mapping']['uuid'])
    timeouts = {}
    for row in plan['episodes']:
        runner.check_retry(events, row)
        timeout = runner.check_budget(state, events, row, resources,
                                      reservations, physical_gpu=3)
        diagnostic.protected_budget(state, events, resources, row, timeout,
                                    runner.__dict__, plan=plan)
        timeouts[row['episode_key']] = timeout
    budget = state['budget']
    runner.require(snapshot['by_bucket']['development'] + 4 <=
                   budget['reserved']['development'] and
                   snapshot['dispatched'] + 4 +
                   max(0, 60 - snapshot['by_bucket']['validation']) +
                   max(0, 40 - snapshot['by_bucket']['formal']) <=
                   budget['max_episode_attempts'],
                   'four-cell projected attempt reserve exhausted')
    protected_hours = sum(max(0.0, value -
                              snapshot['gpu_hours_by_bucket'].get(bucket, 0.0))
                          for bucket, value in
                          budget['gpu_hour_reservations'].items())
    runner.require(snapshot['gpu_hours_consumed'] + 4.2 + protected_hours <=
                   budget['max_gpu_hours'],
                   'four-cell projected protected GPU hours exhausted')
    report = {
        'schema': 'n7-passive-prelaunch-v1',
        'status': 'admissible_read_only_no_gpu_dispatch',
        'plan_path': str(path), 'plan_sha256': runner.digest(path),
        'source_commit': plan['source_commit'],
        'gpu3': {'uuid': gpu['uuid'], **gpu_admission},
        'budget': {'dispatched': snapshot['dispatched'],
                   'development_dispatched': snapshot['by_bucket']['development'],
                   'gpu_hours_consumed': snapshot['gpu_hours_consumed'],
                   'protected_remaining_gpu_hours': protected_hours,
                   'projected_primary_dispatches': 4,
                   'projected_max_gpu_hours': 4.2,
                   'admitted_timeout_seconds_by_episode': timeouts},
        'storage': {'system_free_gb': free_gb(ROOT),
                    'artifact_free_gb': free_gb(diagnostic.RUN_DIR),
                    'artifact_root': str(diagnostic.RUN_DIR),
                    'variant_link': str(HERE / 'diagnostic_runs')},
        'validation_authorized': False,
        'formal_authorized': False,
    }
    out = HERE / 'passive-prelaunch-v2.json'
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
