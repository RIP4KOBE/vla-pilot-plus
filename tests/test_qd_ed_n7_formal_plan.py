"""Conditional N7 formal matrix, eligibility and one-worker routing."""
import pytest

from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n7_formal_plan as formal


def test_fixed_set_has_exact_task_seed_arm_matrix():
    parent=runner.read_json(formal.VALIDATION_PLAN)
    seeds=runner.read_json(parent['seed_plan_path'])
    rows=formal.rows_from_parent(parent,seeds)
    assert len(rows)==len({x['episode_key'] for x in rows})==40
    assert [x['task_id'] for x in rows[::4]]==list(range(10))
    assert [x['profile'] for x in rows]==list(formal.ARMS)*10
    assert [x['env_seed'] for x in rows[::4]]==[44,235,43,546,6,621,197,87,151,548]
    assert all(x['split']==x['budget_bucket']==x['seed_block']=='formal'
               and x['retry_of'] is None and x['iteration']==formal.COHORT for x in rows)


def test_formal_eligibility_rejects_incomplete_validation():
    with pytest.raises(runner.GateError,match='did not authorize'):
        formal.eligibility({'decision':'INCOMPLETE_OR_INVALID','accepted_cells':6},runner)


def test_formal_dispatch_uses_own_one_cell_support():
    plan={'source_commit':'frozen','n7_formal':{},'candidate_profiles':{'N6':{},'N7':{}}}
    assert runner.is_n6_plan(plan) is False
    support=runner.n7_dispatch_support(plan)
    assert support is runner.n7_formal_support()
    with support.supervised_scope(plan,runner.ROOT,'cell_a'):
        support.require_scope(plan,runner.ROOT,runner.__dict__,{'episode_key':'cell_a'})
        with pytest.raises(runner.GateError,match='one-cell audited supervisor'):
            support.require_scope(plan,runner.ROOT,runner.__dict__,{'episode_key':'cell_b'})
