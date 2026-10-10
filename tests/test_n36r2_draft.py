import copy
import pytest
from scripts import qd_ed_n36_contract as c, qd_ed_n36_release as release


def test_exact_fresh_identity_preserves_science_and_order():
    original = c.expected_rows()
    recovery = c.expected_rows(cohort=c.DRAFT_RECOVERY_COHORT)
    old_keys = {r['episode_key'] for cohort in (c.COHORT, c.RECOVERY_COHORT)
                for r in c.expected_rows(cohort=cohort)}
    assert len(recovery) == 40 and not old_keys & {r['episode_key'] for r in recovery}
    for old, new in zip(original, recovery):
        assert {k: v for k, v in old.items() if k not in ('iteration', 'episode_key')} == {
            k: v for k, v in new.items() if k not in ('iteration', 'episode_key')}
        assert new['episode_key'].endswith('_001250')
        c.require_row(new, cohort=c.DRAFT_RECOVERY_COHORT)
    assert c.expected_rows(cohort=c.RECOVERY_COHORT)[0]['episode_key'] == 'n36r1_dev_t00_c0_001203'


@pytest.mark.parametrize('cohort', ['N36R2_NONPROGRESS_TANGENT_DEV_001251', 'N36R3', '', None])
def test_no_open_ended_cohorts(cohort):
    with pytest.raises(ValueError):
        c.expected_rows(cohort=cohort)


@pytest.mark.parametrize('field,value', [('env_seed', -1), ('replacement', 'old'),
                                       ('episode_key', 'n36r1_dev_t00_c0_001203'),
                                       ('profile', 'Q0'), ('budget_bucket', 'recovery')])
def test_identity_mutations_fail(field, value):
    row = copy.deepcopy(c.expected_rows(cohort=c.DRAFT_RECOVERY_COHORT)[0])
    row[field] = value
    with pytest.raises(ValueError):
        c.require_row(row, cohort=c.DRAFT_RECOVERY_COHORT)


def test_new_identity_cannot_release_or_admit():
    # An identity alone is malformed; it grants no release or admission.
    with pytest.raises(KeyError, match='schema'):
        release.validate_plan({'cohort': c.DRAFT_RECOVERY_COHORT})
    with pytest.raises(KeyError, match='n36r2_release_refs'):
        c.pre_dispatch({}, {}, now=None, stop_path='/nonexistent', cohort=c.DRAFT_RECOVERY_COHORT)


def test_layout_guard_unchanged(tmp_path):
    with pytest.raises(ValueError, match='unsupported N36 worktree layout'):
        c.stop_path(tmp_path / 'implementation')
    root = tmp_path / 'variants/n36r2/implementation_worktree'
    assert c.stop_path(root) == str(tmp_path / 'autonomy_20261004/STOP')
