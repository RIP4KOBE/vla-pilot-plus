"""CPU-only E2 diagnostic dispatch boundary tests."""
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qd_ed_final_runner as runner


def test_e2_support_is_distinct_and_requires_scoped_one_cell_dispatch(tmp_path):
    support = runner.n7_dispatch_support({'n7_e2_passive_diagnostic': {}})
    assert support is runner.n7_e2_passive_support()
    assert support is not runner.n7_passive_support()
    plan = {'source_commit': 'frozen-test-commit'}
    row = {'episode_key': 'n7_e2_passive_t03_20260928'}
    with pytest.raises(runner.GateError, match='one-cell supervisor'):
        support.require_scope(plan, tmp_path, vars(runner), row)
    with support.supervised_scope(plan, tmp_path, row['episode_key']):
        support.require_scope(plan, tmp_path, vars(runner), row)
        with pytest.raises(runner.GateError, match='one-cell supervisor'):
            support.require_scope(plan, tmp_path, vars(runner),
                                  {'episode_key': 'n7_e2_passive_t00_20260928'})


def test_e2_release_binds_exact_plan_and_disables_protected_phases(tmp_path):
    support = runner.n7_e2_passive_support()
    plan_path = tmp_path / 'plan.json'
    plan_path.write_text('{"frozen":true}\n')
    plan = {'source_commit': 'frozen-test-commit',
            'episodes': [{'episode_key': 'n7_e2_passive_t00_20260928'}]}
    release = {
        'schema': 'n7-e2-passive-diagnostic-execution-release-v1',
        'plan_path': str(plan_path.resolve()),
        'plan_sha256': runner.digest(plan_path),
        'source_commit': plan['source_commit'],
        'cohort_id': support.COHORT,
        'episode_keys': [plan['episodes'][0]['episode_key']],
        'physical_gpu': 3,
        'validation_authorized': False,
        'formal_authorized': False,
    }
    release_path = tmp_path / 'release.json'
    release_path.write_text(json.dumps(release))
    support.release_check(release_path, plan_path, plan)
    release['validation_authorized'] = True
    release_path.write_text(json.dumps(release))
    with pytest.raises(runner.GateError):
        support.release_check(release_path, plan_path, plan)
