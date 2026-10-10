"""CPU-only owner admission fixtures; no real state, journals or release I/O."""
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import qd_ed_n36_contract as c
from scripts import qd_ed_n36_release as release
from scripts import qd_ed_n36r3_admission as admission


HISTORICAL_ALIAS = '/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z'


def test_exact_historical_alias_allowlist():
    assert release.N36R3_OWNER_ALIAS == HISTORICAL_ALIAS


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    owner = tmp_path / 'owner'
    source = tmp_path / 'source'
    foreign = tmp_path / 'foreign'
    for path in (owner, source, foreign):
        path.mkdir()
    alias = tmp_path / 'historical-alias'
    alias.symlink_to(owner, target_is_directory=True)
    monkeypatch.setattr(admission, 'OWNER', owner)
    monkeypatch.setattr(admission, 'SOURCE', source)
    monkeypatch.setattr(release, 'N36R3_OWNER_ALIAS', str(alias))
    plan = {'cohort': c.DRAFT_N36R3_COHORT, 'worktree': str(source),
            'authority': {'path': 'synthetic-authority', 'sha256': 'synthetic'},
            'resource_routing': {'source_cwd': str(source), 'owner_root': str(owner),
                                 'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID}}
    caps = copy.deepcopy(c.CAPS)
    authority = {'caps': caps, 'amendment': {'synthetic': True}}
    state = {'worktree': str(alias), 'canonical_worktree': str(owner),
             'n36_budget_authority': copy.deepcopy(plan['authority']),
             'gpu_pool': [7], 'max_concurrent_gpu_workers': 1,
             'budget': {'max_episode_attempts': caps['attempts'],
                        'max_gpu_hours': caps['gpu_hours'],
                        'reserved': copy.deepcopy(caps['buckets']),
                        'gpu_hour_reservations': copy.deepcopy(caps['protected_gpu_hours']),
                        'amendment': copy.deepcopy(authority['amendment'])},
             'resource_isolation': {'status': 'ACTIVE', 'validation_status': 'PASS',
                                    'private_budget': True}}
    return SimpleNamespace(**locals())


def check(f):
    before = copy.deepcopy((f.plan, f.authority, f.state))
    try:
        return release.validate_state(f.plan, f.authority, f.state)
    finally:
        assert (f.plan, f.authority, f.state) == before
        assert not list(f.tmp_path.rglob('research-state.yaml'))
        assert not list(f.tmp_path.rglob('*.jsonl'))


@pytest.mark.parametrize('spelling', ['canonical', 'historical'])
def test_accepts_owner_without_mutating_state_or_plan(fixture, spelling):
    f = fixture
    if spelling == 'canonical':
        f.state['worktree'] = str(f.owner)
    assert check(f) is None


@pytest.mark.parametrize('spelling', ['canonical', 'historical'])
@pytest.mark.parametrize('metadata', ['missing', 'foreign', 'alias', 'normalized', 'null'])
def test_rejects_canonical_metadata_mismatch(fixture, spelling, metadata):
    f = fixture
    if spelling == 'canonical':
        f.state['worktree'] = str(f.owner)
    if metadata == 'missing':
        del f.state['canonical_worktree']
    else:
        f.state['canonical_worktree'] = {'foreign': str(f.foreign), 'alias': str(f.alias),
                                        'normalized': str(f.owner) + '/.', 'null': None}[metadata]
    with pytest.raises(ValueError, match='canonical worktree differs'):
        check(f)


@pytest.mark.parametrize('spelling', ['arbitrary-alias', 'foreign', 'normalized-owner',
                                      'normalized-alias', 'missing', 'null'])
def test_rejects_unlisted_lexical_paths(fixture, spelling):
    f = fixture
    other = f.tmp_path / 'other-alias'
    other.symlink_to(f.owner, target_is_directory=True)
    if spelling == 'missing':
        del f.state['worktree']
    else:
        f.state['worktree'] = {'arbitrary-alias': str(other), 'foreign': str(f.foreign),
                              'normalized-owner': str(f.owner) + '/.',
                              'normalized-alias': str(f.alias) + '/', 'null': None}[spelling]
    with pytest.raises(ValueError, match='owning state worktree differs'):
        check(f)


@pytest.mark.parametrize('fault', ['missing', 'dangling', 'retargeted', 'loop', 'regular-file'])
def test_alias_identity_is_rechecked_on_every_call(fixture, fault):
    f = fixture
    check(f)
    f.alias.unlink()
    if fault == 'dangling':
        f.alias.symlink_to(f.tmp_path / 'absent')
    elif fault == 'retargeted':
        f.alias.symlink_to(f.foreign, target_is_directory=True)
    elif fault == 'loop':
        f.alias.symlink_to(f.alias)
    elif fault == 'regular-file':
        f.alias.write_text('not an owner directory')
    with pytest.raises(ValueError, match='alias identity differs'):
        check(f)


@pytest.mark.parametrize('failure', ['different-inode', 'stat-error', 'resolution-error'])
def test_identity_and_resolution_errors_fail_closed(fixture, monkeypatch, failure):
    f = fixture
    if failure == 'different-inode':
        monkeypatch.setattr(Path, 'samefile', lambda *args: False)
    elif failure == 'stat-error':
        def stat_error(*args):
            raise OSError('synthetic filesystem error')
        monkeypatch.setattr(Path, 'samefile', stat_error)
    else:
        original = Path.resolve
        def resolution_error(path, *args, **kwargs):
            if path == f.alias:
                raise OSError('synthetic resolution error')
            return original(path, *args, **kwargs)
        monkeypatch.setattr(Path, 'resolve', resolution_error)
    with pytest.raises(ValueError, match='alias identity differs'):
        check(f)


@pytest.mark.parametrize('field', ['worktree', 'owner_root', 'source_cwd'])
def test_plan_routing_stays_lexical(fixture, field):
    f = fixture
    if field == 'worktree':
        f.plan[field] = str(f.source) + '/.'
    else:
        f.plan['resource_routing'][field] = str(f.alias if field == 'owner_root' else f.source) + '/.'
    with pytest.raises(ValueError, match='lexical owner/source routing differs'):
        check(f)


@pytest.mark.parametrize('fault', ['caps', 'authority', 'gpu', 'workers', 'attempts',
                                  'hours', 'reserved', 'protected', 'amendment',
                                  'isolation', 'validation', 'private', 'hold'])
def test_alias_does_not_bypass_remaining_state_gates(fixture, fault):
    f = fixture
    budget = f.state['budget']
    if fault == 'caps':
        f.authority['caps']['attempts'] += 1
    elif fault == 'authority':
        f.state['n36_budget_authority'] = {}
    elif fault == 'gpu':
        f.state['gpu_pool'] = [0]
    elif fault == 'workers':
        f.state['max_concurrent_gpu_workers'] = 2
    elif fault in ('attempts', 'hours'):
        budget[{'attempts': 'max_episode_attempts', 'hours': 'max_gpu_hours'}[fault]] += 1
    elif fault in ('reserved', 'protected', 'amendment'):
        budget[{'reserved': 'reserved', 'protected': 'gpu_hour_reservations',
                'amendment': 'amendment'}[fault]] = {}
    elif fault == 'hold':
        f.state['external_resource_hold'] = {'do_not_auto_resume': True}
    else:
        f.state['resource_isolation'][{'isolation': 'status', 'validation': 'validation_status',
                                       'private': 'private_budget'}[fault]] = False
    with pytest.raises((ValueError, release.r.GateError)):
        check(f)


def test_other_cohorts_keep_existing_state_contract(fixture):
    f = fixture
    f.plan['cohort'] = c.COHORT
    del f.state['canonical_worktree']
    f.state['worktree'] = str(f.foreign)
    assert check(f) is None
