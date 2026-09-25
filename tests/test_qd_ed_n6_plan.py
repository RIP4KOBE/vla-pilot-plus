"""N6 exact matched-cell and private-resource gates."""
from pathlib import Path

import pytest

from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n6_plan as n6


def test_n6_rows_reuse_exposed_n5_dev_identity_without_reusing_attempts():
    parent = runner.read_json(n6.PARENT_PLAN)
    rows = n6.rows_from_parent(parent)
    assert [row['task_id'] for row in rows] == [0, 3, 6, 9]
    for row, original in zip(rows, parent['episodes']):
        assert {key: row[key] for key in n6.FIELDS} == {key: original[key] for key in n6.FIELDS}
        assert row['episode_key'] != original['episode_key']
        assert row['budget_bucket'] == 'development' and row['profile'] == 'N6'


def test_n6_scope_is_one_cell_only():
    plan = {'source_commit': 'frozen'}
    root = Path('/tmp/n6-test-root')
    with pytest.raises(runner.GateError):
        n6.require_scope(plan, root, runner.__dict__, {'episode_key': 'a'})
    with n6.supervised_scope(plan, root, 'a'):
        n6.require_scope(plan, root, runner.__dict__, {'episode_key': 'a'})
        with pytest.raises(runner.GateError):
            n6.require_scope(plan, root, runner.__dict__, {'episode_key': 'b'})


def test_n6_local_cap_preserves_protected_reserves():
    state = {'budget': {'reserved': runner.BUCKETS, 'running': 0, 'gpu_hours_consumed': 13.,
                        'gpu_hour_reservations': {'validation': 14., 'formal': 10.},
                        'max_gpu_hours': 48.}}
    row = {'profile': 'N6', 'iteration': n6.COHORT, 'budget_bucket': 'development'}
    n6.protected_budget(state, [], [], row, 1800, runner.__dict__, plan={})
    exhausted = [{'identity': {'iteration': n6.COHORT}, 'event': 'valid',
                  'gpu_process_wall_seconds': 14000.}]
    with pytest.raises(runner.GateError, match='local dispatch/GPU-hour cap'):
        n6.protected_budget(state, exhausted, [], row, 1800, runner.__dict__, plan={})
    state['budget']['gpu_hours_consumed'] = 24.
    with pytest.raises(runner.GateError, match='protected GPU-hour reserves'):
        n6.protected_budget(state, [], [], row, 1800, runner.__dict__, plan={})
