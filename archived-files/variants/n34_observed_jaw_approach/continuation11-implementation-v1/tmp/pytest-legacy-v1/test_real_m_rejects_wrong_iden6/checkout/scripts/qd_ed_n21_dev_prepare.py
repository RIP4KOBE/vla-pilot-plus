#!/usr/bin/env python3
"""Freeze prospective N21 GPU7 Dev plan; never dispatch."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess

import qd_ed_final_runner as runner
import qd_ed_n21_dev_contract as contract
import qd_ed_available_gpu_queue as queue

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = contract.RUN_DIR / 'plan.frozen.v1.gpu7.json'


def committed_record(relative, head):
    actual = (ROOT / relative).read_bytes()
    committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=ROOT)
    runner.require(actual == committed, 'uncommitted N21 frozen source: ' + relative)
    return {'path': relative, 'sha256': hashlib.sha256(actual).hexdigest()}


def build_plan():
    """Build a committed-source draft without dispatch, state mutation or GPU use."""
    parent = runner.read_json(contract.SOURCE_PLAN)
    runner.require(parent.get('n20_cohort', {}).get('cohort_id') ==
                   'N20_TERMINAL_RAW_DEV_20260929'
                   and len(parent['episodes']) == 12,
                   'N21 source Dev identity differs')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    plan = copy.deepcopy(parent)
    code = {record['path'] for record in parent['code_files']}
    code |= runner.REQUIRED_CODE
    code |= {'core/qd_lift_quality.py', 'core/qd_terminal_population.py',
             'core/rdt_policy_steer.py',
             'configs/qd_ed_final/candidate_n7.json',
             'configs/qd_ed_final/candidate_n21.json',
             'scripts/audit_decision_evidence.py', 'scripts/qd_ed_final_runner.py',
             'scripts/qd_ed_available_gpu_queue.py',
             'scripts/qd_ed_n21_dev_contract.py', 'scripts/qd_ed_n21_dev_prepare.py',
             'scripts/qd_ed_n21_dev_supervise.py', 'tests/test_qd_lift_quality.py',
             'tests/test_qd_terminal_population.py', 'tests/test_rdt_steer.py',
             'tests/test_qd_ed_n21_dev.py', 'experiments/iteration_021_stage_raw/protocol.md'}
    plan['code_files'] = [committed_record(relative, head) for relative in sorted(code)]
    for stale in ('n20_cohort', 'n20_gpu7_binding', 'n18_cohort', 'n18_gpu7_rebind', 'n11_cohort',
                  'n17_passive_physics', 'n7_cohort', 'n9_cohort'):
        plan.pop(stale, None)
    plan.update(source_commit=head, worktree=str(ROOT),
                runtime_manifest_path=str(contract.GPU7_RUNTIME),
                runtime_manifest_sha256=runner.digest(contract.GPU7_RUNTIME),
                candidate_profiles={'N21': {
                    'path': str(ROOT / 'configs/qd_ed_final/candidate_n21.json'),
                    'sha256': runner.digest(ROOT / 'configs/qd_ed_final/candidate_n21.json')}},
                episodes=contract.expected_rows(),
                phase_authorization={'dev': True, 'validation': False, 'formal': False},
                derived_from={'path': str(contract.SOURCE_PLAN),
                              'sha256': runner.digest(contract.SOURCE_PLAN)})
    plan['scientific_config_files'] = sorted(set(plan['scientific_config_files']) |
        {'configs/qd_ed_final/candidate_n7.json',
         'configs/qd_ed_final/candidate_n21.json'})
    plan['n21_cohort'] = {
        'schema': 'n21-stage-raw-dev-v1',
        'cohort_id': contract.COHORT,
        'limits': contract.LIMITS,
        'early_stop': 'reject_after_audited_task0_candidate_failure',
        'protocol': {'path': str(contract.PROTOCOL),
                     'sha256': runner.digest(contract.PROTOCOL)},
        'source_plan': {'path': str(contract.SOURCE_PLAN),
                        'sha256': runner.digest(contract.SOURCE_PLAN)},
    }
    plan['n21_gpu7_binding'] = {
        'schema': 'n21-gpu7-binding-v1',
        'addendum': {'path': str(contract.GPU7_ADDENDUM),
                     'sha256': runner.digest(contract.GPU7_ADDENDUM)},
        'runtime': {'path': str(contract.GPU7_RUNTIME),
                    'sha256': runner.digest(contract.GPU7_RUNTIME)},
        'physical_gpu': 7,
        'uuid': contract.GPU7_UUID,
        'egl_device_index': 4,
        'reused_probe_resource_id': contract.GPU7_PROOF,
    }
    return plan


def main():
    runner.require(not OUTPUT.exists(), 'N21 plan already frozen')
    state = runner.read_state(ROOT / 'research-state.yaml')
    events = runner.read_events(ROOT / 'data/attempt-ledger.jsonl')
    snap = runner.budget_snapshot(events,
        runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'))
    runner.require(runner.authorized_gpu(state) == 7 and snap['running'] == 0
                   and state['budget'].get('amendment') == runner.GPU7_N21_AMENDMENT
                   and state['budget']['max_episode_attempts'] == 398
                   and state['budget']['max_gpu_hours'] == 100.0
                   and state['budget']['reserved'] == runner.N21_BUCKETS
                   and state['budget']['reserved']['baseline'] - snap['by_bucket']['baseline'] >= 4
                   and state['budget']['reserved']['development'] - snap['by_bucket']['development'] >= 8
                   and not any(event.get('event') == 'dispatched'
                               and event.get('identity', {}).get('iteration') == contract.COHORT
                               for event in events),
                   'N21 matched Dev capacity unavailable or cohort already started')
    devices = queue.inventory()
    runner.require(7 in devices and devices[7]['uuid'] == contract.GPU7_UUID,
                   'N21 GPU7 UUID differs')
    queue.reservation_admission(devices[7])
    runner.gpu_admission(physical_gpu=7, expected_uuid=contract.GPU7_UUID)
    mapping = queue.current_metadata(7, root=ROOT)
    runner.require(mapping['egl_device_index'] == 4
                   and mapping['metadata_mapping_verified'] is True,
                   'N21 GPU7 EGL mapping differs')
    runtime = runner.read_json(contract.GPU7_RUNTIME)
    proof = queue.find_probe(runtime, mapping,
        runner.read_events(ROOT / 'data/gpu-healthcheck-ledger.jsonl'), root=ROOT)
    runner.require(isinstance(proof, dict)
                   and proof.get('resource_id') == contract.GPU7_PROOF,
                   'N21 reusable CUDA/EGL proof unavailable')
    plan = build_plan()
    runner.durable_json(OUTPUT, plan)
    runner.validate_plan(OUTPUT, root=ROOT)
    print(json.dumps({'schema': 'n21-dev-plan-frozen-v1', 'plan_path': str(OUTPUT),
                      'plan_sha256': runner.digest(OUTPUT), 'source_commit': plan['source_commit'],
                      'episode_keys': [row['episode_key'] for row in plan['episodes']],
                      'gpu_dispatched': False}, sort_keys=True))


if __name__ == '__main__':
    main()
