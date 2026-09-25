"""N5 four-cell source identity, private cap and one-cell supervisor gates."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n5_plan as n5


def test_n5_rows_reuse_exact_matched_exposed_dev_cells():
    parent = runner.read_json(n5.PARENT_PLAN)
    rows = n5.rows_from_parent(parent)
    prior = {row['task_id']: row for row in parent['episodes'] if row['profile'] == 'N4'}
    assert [row['task_id'] for row in rows] == [0, 3, 6, 9]
    for row in rows:
        original = prior[row['task_id']]
        assert {key: row[key] for key in n5.FIELDS} == {key: original[key] for key in n5.FIELDS}
        assert row['budget_bucket'] == 'development' and row['profile'] == 'N5'


def test_n5_scope_rejects_unsupervised_or_different_cell():
    plan = {'source_commit': 'frozen'}
    root = Path('/tmp/n5-test-root')
    row = {'episode_key': 'a'}
    with pytest.raises(runner.GateError):
        n5.require_scope(plan, root, runner.__dict__, row)
    with n5.supervised_scope(plan, root, 'a'):
        n5.require_scope(plan, root, runner.__dict__, row)
        with pytest.raises(runner.GateError):
            n5.require_scope(plan, root, runner.__dict__, {'episode_key': 'b'})


def test_n5_local_gpu_cap_preserves_protected_reserves():
    state = {'budget': {'reserved': runner.BUCKETS, 'running': 0, 'gpu_hours_consumed': 12.,
                        'gpu_hour_reservations': {'validation': 14., 'formal': 10.},
                        'max_gpu_hours': 48.}}
    row = {'profile': 'N5', 'iteration': n5.COHORT, 'budget_bucket': 'development'}
    n5.protected_budget(state, [], [], row, 1800, runner.__dict__, plan={})
    exhausted = [{'identity': {'iteration': n5.COHORT}, 'event': 'valid',
                  'gpu_process_wall_seconds': 14000.}]
    with pytest.raises(runner.GateError, match='local dispatch/GPU-hour cap'):
        n5.protected_budget(state, exhausted, [], row, 1800, runner.__dict__, plan={})
    state['budget']['gpu_hours_consumed'] = 24.
    with pytest.raises(runner.GateError, match='protected GPU-hour reserves'):
        n5.protected_budget(state, [], [], row, 1800, runner.__dict__, plan={})
