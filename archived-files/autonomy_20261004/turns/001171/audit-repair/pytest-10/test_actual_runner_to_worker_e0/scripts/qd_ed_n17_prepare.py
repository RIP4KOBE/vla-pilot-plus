#!/usr/bin/env python3
"""Freeze two N7 passive physics Dev identities; does not dispatch."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import qd_ed_final_runner as runner


ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT.parent
SOURCE = SESSION / 'artifacts/continuation_20260928/n11-parent-survival-dev-v1/plan.frozen.v1.json'
PROTOCOL = SESSION / 'variants/n17_passive_physics/protocol-v1.md'
OUTPUT = SESSION / 'variants/n17_passive_physics/plan.frozen.v2.json'
COHORT = 'N17_PASSIVE_PHYSICS_DEV_20260929'


def committed_record(relative, head):
    actual = (ROOT / relative).read_bytes()
    committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=ROOT)
    runner.require(actual == committed, 'uncommitted N17 source: ' + relative)
    return {'path': relative, 'sha256': hashlib.sha256(actual).hexdigest()}


def main():
    runner.require(not OUTPUT.exists(), 'N17 plan already frozen')
    state = runner.read_state(ROOT / 'research-state.yaml')
    snapshot = runner.budget_snapshot(
        runner.read_events(ROOT / 'data/attempt-ledger.jsonl'),
        runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'))
    runner.require(runner.authorized_gpu(state) == 3
                   and state['resource_isolation']['status'] == 'ACTIVE'
                   and state['resource_isolation']['validation_status'] == 'PASS'
                   and snapshot['dispatched'] == state['budget']['dispatched']
                   and snapshot['running'] == 0
                   and state['budget']['reserved']['development'] - snapshot['by_bucket']['development'] >= 2,
                   'N17 private GPU3 development capacity unavailable')
    parent = runner.read_json(SOURCE)
    plan = copy.deepcopy(parent)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    paths = {record['path'] for record in parent['code_files']}
    paths |= {'main.py', 'core/passive_physics_trace.py', 'configs/config.yaml',
              'scripts/qd_ed_final_runner.py', 'scripts/qd_ed_n17_prepare.py',
              'scripts/qd_ed_n17_supervise.py', 'tests/test_passive_physics_trace.py'}
    plan['code_files'] = [committed_record(path, head) for path in sorted(paths)]
    rows = [copy.deepcopy(row) for row in parent['episodes']
            if row['profile'] == 'N7' and row['task_id'] in (0, 9)]
    runner.require([row['task_id'] for row in rows] == [0, 9], 'N17 task ordering differs')
    for row in rows:
        row.update(iteration=COHORT, episode_key=f'n17_physics_t{row["task_id"]:02d}_n7_20260929',
                   budget_bucket='development')
    plan.pop('n11_cohort', None)
    plan.update(source_commit=head, worktree=str(ROOT), episodes=rows,
                candidate_profiles={'N7': {'path': str(ROOT / 'configs/qd_ed_final/candidate_n7.json'),
                                            'sha256': runner.digest(ROOT / 'configs/qd_ed_final/candidate_n7.json')}},
                phase_authorization={'dev': True, 'validation': False, 'formal': False},
                stage_condition=runner.E2_STAGE_CONDITION,
                derived_from={'path': str(SOURCE), 'sha256': runner.digest(SOURCE)},
                n17_passive_physics={'schema': 'n17-passive-physics-dev-v1',
                                     'cohort_id': COHORT, 'max_dispatches': 2,
                                     'max_gpu_hours': 2.0,
                                     'protocol_path': str(PROTOCOL),
                                     'protocol_sha256': runner.digest(PROTOCOL),
                                     'source_plan_path': str(SOURCE),
                                     'source_plan_sha256': runner.digest(SOURCE)})
    runner.durable_json(OUTPUT, plan)
    runner.validate_plan(OUTPUT, root=ROOT)
    print(json.dumps({'plan': str(OUTPUT), 'sha256': runner.digest(OUTPUT),
                      'source_commit': head, 'episode_keys': [r['episode_key'] for r in rows],
                      'gpu_dispatched': False}, sort_keys=True))


if __name__ == '__main__':
    main()
