"""N7 validation matching, isolation and protected-resource gates."""
import json
from pathlib import Path

import pytest

from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n7_validation_plan as validation


def test_sixty_cells_match_frozen_task_seed_init_and_arm_order():
    parent = runner.read_json(validation.DEV_PLAN)
    seeds = runner.read_json(parent['seed_plan_path'])
    rows = validation.rows_from_parent(parent, seeds)
    assert len(rows) == len({r['episode_key'] for r in rows}) == 60
    assert [r['seed_block'] for r in rows] == [b for b in validation.BLOCKS for _ in range(30)]
    assert [r['task_id'] for r in rows[::3]] == list(range(10)) * 2
    assert [r['profile'] for r in rows] == list(validation.ARMS) * 20
    for row in rows:
        source = next(x for x in seeds['blocks'][row['seed_block']] if x['task_id'] == row['task_id'])
        assert {field: row[field] for field in validation.FIELDS} == {field: source[field] for field in validation.FIELDS}
        assert row['split'] == row['budget_bucket'] == 'validation'
        assert row['iteration'] == validation.COHORT
    exposure = json.loads(validation.EXPOSURE.read_text())
    assert exposure['task_seed_overlaps_with_prior_or_formal'] == 0
    assert exposure['same_init_row_across_two_seeds_per_task'] is True


def test_validation_scope_is_one_cell_only():
    plan = {'source_commit': 'frozen', 'n7_validation': {}}
    root = Path('/tmp/n7-validation-test-root')
    with pytest.raises(runner.GateError):
        validation.require_scope(plan, root, runner.__dict__, {'episode_key': 'a'})
    with validation.supervised_scope(plan, root, 'a'):
        validation.require_scope(plan, root, runner.__dict__, {'episode_key': 'a'})
        with pytest.raises(runner.GateError):
            validation.require_scope(plan, root, runner.__dict__, {'episode_key': 'b'})
    assert runner.n7_dispatch_support(plan) is runner.n7_validation_support()


def test_validation_cap_preserves_formal_reserve():
    state = {'budget': {'reserved': runner.BUCKETS, 'running': 0,
                        'gpu_hours_consumed': 14.,
                        'gpu_hour_reservations': {'validation': 14., 'formal': 10.},
                        'max_gpu_hours': 48.}}
    row = {'profile': 'N7', 'iteration': validation.COHORT,
           'budget_bucket': 'validation', 'split': 'validation'}
    validation.protected_budget(state, [], [], row, 1800, runner.__dict__, plan={})
    exhausted = [{'identity': {'iteration': validation.COHORT}, 'event': 'valid',
                  'gpu_process_wall_seconds': 49000.}]
    with pytest.raises(runner.GateError, match='dispatch/GPU-hour cap'):
        validation.protected_budget(state, exhausted, [], row, 1800, runner.__dict__, plan={})
    state['budget']['gpu_hours_consumed'] = 38.
    with pytest.raises(runner.GateError, match='formal GPU-hour reserve'):
        validation.protected_budget(state, [], [], row, 1800, runner.__dict__, plan={})
