import copy

import pytest

from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n11_dev_contract as n11


def test_n11_candidate_changes_only_parent_survivor_mechanism():
    source = runner.read_json(n11.SOURCE_PLAN)
    baseline = runner.read_json(source['profiles_path'])['profiles']['Q0']
    candidate = runner.read_json(runner.ROOT/'configs/qd_ed_final/candidate_n11.json')
    active = runner.expand_candidate('N11',candidate,baseline)
    inherited = runner.expand_candidate('N7',runner.read_json(
        runner.ROOT/'configs/qd_ed_final/candidate_n7.json'),baseline)
    assert active['resolved_eds_config'] == {
        **inherited['resolved_eds_config'],'qd_parent_survivor_count':4}
    assert active['static_override_values']['main.eds_config.qd_parent_survivor_count'] == 4
    changed = copy.deepcopy(candidate)
    changed['profile']['qd_descriptor'] = 'target_relative_endpoint_xy'
    with pytest.raises(runner.GateError):
        runner.expand_candidate('N11',changed,baseline)


def test_n11_matched_rows_and_one_cell_supervisor_scope(tmp_path):
    rows = n11.expected_rows()
    assert len(rows) == 16
    assert [row['profile'] for row in rows[:4]] == list(n11.ARMS)
    assert all(row['budget_bucket'] == ('baseline' if row['profile']=='C0' else 'development')
               for row in rows)
    for task in n11.TASKS:
        group = [row for row in rows if row['task_id']==task]
        assert len({(row['env_seed'],row['policy_seed'],row['init_row_sha256']) for row in group}) == 1
    plan = {'source_commit':'test-head'}
    with pytest.raises(runner.GateError):
        n11.require_scope(plan,tmp_path,vars(runner),rows[0])
    with n11.supervised_scope(plan,tmp_path,rows[0]['episode_key']):
        n11.require_scope(plan,tmp_path,vars(runner),rows[0])
        with pytest.raises(runner.GateError):
            n11.require_scope(plan,tmp_path,vars(runner),rows[1])
