#!/usr/bin/env python3
"""Freeze N18 matched Dev plan after source integration; never dispatch."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess

import qd_ed_final_runner as runner
import qd_ed_n18_dev_contract as contract

ROOT = Path(__file__).resolve().parents[1]


def committed_record(relative, head):
    actual = (ROOT / relative).read_bytes()
    committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=ROOT)
    runner.require(actual == committed, 'uncommitted N18 frozen source: ' + relative)
    return {'path': relative, 'sha256': hashlib.sha256(actual).hexdigest()}


def main():
    state = runner.read_state(ROOT / 'research-state.yaml')
    snapshot = runner.budget_snapshot(
        runner.read_events(ROOT / 'data/attempt-ledger.jsonl'),
        runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'))
    runner.require(runner.authorized_gpu(state) == 3
                   and state['resource_isolation']['status'] == 'ACTIVE'
                   and state['resource_isolation']['validation_status'] == 'PASS'
                   and state['budget']['max_episode_attempts'] == 393
                   and state['budget']['max_gpu_hours'] == 100.0
                   and snapshot['running'] == 0
                   and state['budget']['reserved']['baseline'] - snapshot['by_bucket']['baseline'] >= 4
                   and state['budget']['reserved']['development'] - snapshot['by_bucket']['development'] >= 8,
                   'N18 GPU3 matched Dev capacity unavailable')
    parent = runner.read_json(contract.SOURCE_PLAN)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    out = contract.RUN_DIR / 'plan.frozen.v1.json'
    runner.require(not out.exists(), 'N18 plan already frozen')
    plan = copy.deepcopy(parent)
    code = {record['path'] for record in plan['code_files']}
    code |= runner.REQUIRED_CODE
    code |= {'core/qd_lift_quality.py', 'core/rdt_policy_steer.py',
             'configs/qd_ed_final/candidate_n7.json',
             'configs/qd_ed_final/candidate_n18.json',
             'scripts/audit_decision_evidence.py', 'scripts/qd_ed_final_runner.py',
             'scripts/qd_ed_n18_dev_contract.py', 'scripts/qd_ed_n18_dev_prepare.py',
             'scripts/qd_ed_n18_dev_supervise.py', 'tests/test_qd_lift_quality.py'}
    plan['code_files'] = [committed_record(relative, head) for relative in sorted(code)]
    for stale in ('n11_cohort', 'n17_passive_physics', 'n7_cohort',
                  'n7_passive_diagnostic', 'n7_e2_passive_diagnostic',
                  'root_integration_review', 'supersedes_unlaunched_plan'):
        plan.pop(stale, None)
    plan.update(source_commit=head, worktree=str(ROOT),
                runtime_manifest_path=str(contract.E2_RUNTIME),
                runtime_manifest_sha256=runner.digest(contract.E2_RUNTIME),
                candidate_profiles={'N18': {
                    'path': str(ROOT / 'configs/qd_ed_final/candidate_n18.json'),
                    'sha256': runner.digest(ROOT / 'configs/qd_ed_final/candidate_n18.json')}},
                episodes=contract.expected_rows(),
                stage_condition=runner.E2_STAGE_CONDITION,
                phase_authorization={'dev': True, 'validation': False, 'formal': False})
    plan['scientific_config_files'] = sorted(set(plan['scientific_config_files']) |
        {'configs/qd_ed_final/candidate_n7.json',
         'configs/qd_ed_final/candidate_n18.json'})
    plan['derived_from'] = {'path': str(contract.SOURCE_PLAN),
                            'sha256': runner.digest(contract.SOURCE_PLAN)}
    plan['n18_cohort'] = {
        'schema': 'n18-close-then-lift-dev-v1',
        'cohort_id': contract.COHORT,
        'limits': contract.LIMITS,
        'protocol': {'path': str(contract.PROTOCOL),
                     'sha256': runner.digest(contract.PROTOCOL)},
        'source_plan': {'path': str(contract.SOURCE_PLAN),
                        'sha256': runner.digest(contract.SOURCE_PLAN)},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    runner.durable_json(out, plan)
    runner.validate_plan(out, root=ROOT)
    print(json.dumps({'schema': 'n18-dev-plan-frozen-v1', 'plan_path': str(out),
                      'plan_sha256': runner.digest(out), 'source_commit': head,
                      'episode_keys': [row['episode_key'] for row in plan['episodes']],
                      'gpu_dispatched': False}, sort_keys=True))


if __name__ == '__main__':
    main()
