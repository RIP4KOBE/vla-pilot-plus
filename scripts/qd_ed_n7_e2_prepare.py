#!/usr/bin/env python3
"""Freeze an approved E2 N7 passive cohort; never dispatches an episode."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess

import qd_ed_final_runner as runner
import qd_ed_n7_e2_passive_diagnostic as diagnostic

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def committed_record(relative, head):
    path = ROOT / relative
    actual = path.read_bytes()
    committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=ROOT)
    runner.require(actual == committed, 'uncommitted frozen source: ' + relative)
    return {'path': relative, 'sha256': hashlib.sha256(actual).hexdigest()}


def main():
    state = runner.read_state(ROOT / 'research-state.yaml')
    budget = state['budget']
    runner.require(runner.authorized_gpu(state) == 3
                   and state['resource_isolation']['status'] == 'ACTIVE'
                   and state['resource_isolation']['validation_status'] == 'PASS'
                   and state['resource_isolation']['private_budget'] is True
                   and budget.get('amendment') == runner.GPU3_AMENDMENT
                   and budget['max_episode_attempts'] == 393
                   and budget['max_gpu_hours'] == 100.0
                   and budget['reserved'] == runner.AMENDED_BUCKETS
                   and budget['gpu_hour_reservations'] == {'validation':32.,'formal':12.},
                   'approved exact GPU3 E2 budget amendment missing')
    runner.require(sha(diagnostic.SESSION / 'budget-extension-proposal-20260928.md') ==
                   runner.GPU3_AMENDMENT['proposal_sha256'],
                   'approved proposal bytes changed')
    runner.require(sha(diagnostic.PROTOCOL) == diagnostic.PROTOCOL_SHA,
                   'E2 measurement protocol bytes changed')
    runner.require(sha(diagnostic.SOURCE_PLAN) == diagnostic.SOURCE_PLAN_SHA,
                   'original N7 plan hash changed')
    source = runner.read_json(diagnostic.SOURCE_PLAN)
    runner.require(sha(source['runtime_manifest_path']) == source['runtime_manifest_sha256'],
                   'original N7 runtime hash changed')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                   text=True).strip()
    run_dir = diagnostic.RUN_DIR
    runtime_path = run_dir / 'runtime-manifest.e2.frozen.v1.json'
    plan_path = run_dir / 'plan.frozen.v1.json'
    runner.require(not runtime_path.exists() and not plan_path.exists(),
                   'E2 diagnostic manifest/plan already exists')

    runtime = copy.deepcopy(runner.read_json(source['runtime_manifest_path']))
    runtime['frozen_stage_provider']['allow_recovered_error_events'] = True
    runtime['stage_recovered_error_condition'] = runner.E2_STAGE_CONDITION
    runtime['stage_condition'] = runner.E2_STAGE_CONDITION
    runtime['provider_note'] = ('Prospective E2 single-answer recovered-error transport; '
                                'previous invalid E1 task3 remains invalid')
    runner.stage_overrides(runtime)

    plan = copy.deepcopy(source)
    code = {record['path'] for record in plan['code_files']}
    code |= runner.REQUIRED_CODE
    code |= {'main.py', 'core/keypoint_tracker.py', 'core/decision_evidence.py',
             'core/codex_stage.py', 'configs/perception.yaml',
             'scripts/qd_ed_final_runner.py',
             'scripts/qd_ed_n7_e2_passive_diagnostic.py',
             'scripts/qd_ed_n7_e2_prepare.py',
             'tests/test_qd_ed_n7_e2_passive_diagnostic.py',
             'tests/test_keypoint_tracking_evidence.py'}
    plan['code_files'] = [committed_record(relative, head) for relative in sorted(code)]
    plan.pop('n7_cohort', None)
    plan.pop('n7_passive_diagnostic', None)
    plan.pop('root_integration_review', None)
    plan.pop('supersedes_unlaunched_plan', None)
    plan.update(source_commit=head, worktree=str(ROOT),
                episodes=diagnostic.expected_rows(),
                stage_condition=runner.E2_STAGE_CONDITION,
                phase_authorization={'dev':True,'validation':False,'formal':False})
    plan['derived_from'] = {'path':str(diagnostic.SOURCE_PLAN),
                            'sha256':diagnostic.SOURCE_PLAN_SHA}
    plan['e2_source_lineage'] = {
        'original_n7_plan_sha256': diagnostic.SOURCE_PLAN_SHA,
        'stopped_e1_diagnostic_report_sha256':
            'ca5bb714dfca5d4ef8aa7322eb639087472e42612d2923aa7e80a52ef437c744',
        'retroactive_acceptance': False,
    }
    plan['n7_e2_passive_diagnostic'] = {
        'schema': 'n7-e2-passive-diagnostic-v1',
        'cohort_id': diagnostic.COHORT,
        'limits': diagnostic.LIMITS,
        'source_plan_sha256': diagnostic.SOURCE_PLAN_SHA,
        'run_dir': str(run_dir),
        'protocol_path': str(diagnostic.PROTOCOL),
        'protocol_sha256': diagnostic.PROTOCOL_SHA,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    runner.durable_json(runtime_path, runtime)
    plan['runtime_manifest_path'] = str(runtime_path)
    plan['runtime_manifest_sha256'] = sha(runtime_path)
    runner.durable_json(plan_path, plan)
    runner.validate_plan(plan_path, root=ROOT)
    print(json.dumps({'schema':'n7-e2-plan-frozen-v1','plan_path':str(plan_path),
                      'plan_sha256':sha(plan_path),'source_commit':head,
                      'runtime_manifest_sha256':sha(runtime_path),
                      'episode_keys':[row['episode_key'] for row in plan['episodes']],
                      'gpu_dispatched':False},sort_keys=True))


if __name__ == '__main__':
    main()
