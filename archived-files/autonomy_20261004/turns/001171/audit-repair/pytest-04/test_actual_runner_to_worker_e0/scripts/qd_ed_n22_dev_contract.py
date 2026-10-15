#!/usr/bin/env python3
"""Prospective GPU7 N22 matched Dev contract; protected phases stay closed."""
from __future__ import annotations

import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import threading

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT.parent if ROOT.name == 'study_worktree' else ROOT.parents[2]
RUN_DIR = SESSION / 'variants/n22_hold_conditioned_lift'
SOURCE_PLAN = SESSION / 'variants/n21_stage_raw_reward_binding/plan.frozen.v1.gpu7.json'
GPU7_RUNTIME = Path(json.loads(SOURCE_PLAN.read_text())['runtime_manifest_path'])
PROTOCOL = RUN_DIR / 'protocol-dev-v1.md'
GPU7_ADDENDUM = PROTOCOL
CPU_PROTOCOL = RUN_DIR / 'protocol-cpu-v1.md'
PROTOCOL_SHA = '650489b28f8b048b1963cfd7268dc937274a12f33132beabe93d4bc9bde0c295'
PREDECESSOR_REVIEW = RUN_DIR / 'predecessor-review-v1.json'
BUDGET_AMENDMENT = SESSION / 'budget-autonomous-amendment-20260930-n22.md'
AUTONOMOUS_REPLY = '继续完成满足目标且无需我介入的autoresearch'
GPU7_UUID = 'GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF = 'rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
COHORT = 'N22_HOLD_LIFT_DEV_20260930'
TASKS = tuple(range(10))
ARMS = ('C0', 'Q0', 'N21', 'N22')
LIMITS = {'dispatches': 40, 'gpu_hours': 21.0,
          'episode_timeout_seconds': 1800, 'cleanup_seconds': 40,
          'physical_gpu': 7}
_SCOPE = None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_rows():
    parent = json.loads(SOURCE_PLAN.read_text())
    seed_path = Path(parent['seed_plan_path'])
    if sha(seed_path) != parent['seed_plan_sha256']:
        raise ValueError('N22 original frozen seed plan identity differs')
    seeds = json.loads(seed_path.read_text())
    original = {row['task_id']: row for row in seeds['blocks']['dev']}
    if tuple(seeds['backend_task_order']) != TASKS or set(original) != set(TASKS) or len(seeds['blocks']['dev']) != 10:
        raise ValueError('N22 frozen ten-task Dev identities changed')
    fields = ('task_id', 'env_seed', 'policy_seed', 'init_index',
              'init_row_sha256', 'init_file_sha256', 'bddl_sha256')
    rows = []
    for task in TASKS:
        for arm in ARMS:
            row = {key: original[task][key] for key in fields}
            row.update(split='dev', seed_block='dev', iteration=COHORT, profile=arm,
                       timeout_seconds=LIMITS['episode_timeout_seconds'],
                       episode_key=f'n22_dev_t{task:02d}_{arm.lower()}_20260930',
                       budget_bucket='baseline' if arm == 'C0' else 'development')
            rows.append(row)
    return rows


def predecessor_review(runner):
    """Read only the root-owned terminal review; validation uses aggregate data only."""
    r = runner
    review = r['read_json'](PREDECESSOR_REVIEW)
    r['require'](set(review) == {'schema', 'source_plan', 'source_status', 'phase',
                               'disposition', 'allow_n22', 'cause_resolved', 'rationale'}
                 and review['schema'] == 'n22-n21-prerequisite-v1'
                 and review['source_plan'] == {'path': str(SOURCE_PLAN), 'sha256': sha(SOURCE_PLAN)}
                 and review['phase'] in {'dev', 'validation'}
                 and review['disposition'] in {'rejected', 'invalid_resolved'}
                 and review['allow_n22'] is True
                 and isinstance(review['rationale'], str) and bool(review['rationale'].strip())
                 and type(review['cause_resolved']) is bool,
                 'N22 predecessor terminal review identity/authority differs')
    source = review['source_status']
    r['require'](isinstance(source, dict) and set(source) == {'path', 'sha256'}
                 and Path(source['path']).is_absolute()
                 and (Path(source['path']).resolve().is_relative_to(SESSION.resolve())
                      or Path(source['path']).resolve().is_relative_to(
                          Path(json.loads(SOURCE_PLAN.read_text())['artifact_root']).resolve()))
                 and sha(source['path']) == source['sha256'],
                 'N22 predecessor terminal status hash/path differs')
    status = r['read_json'](source['path'])
    if review['phase'] == 'validation':
        r['require'](set(status) == {'schema', 'cohort_id', 'aggregate_only', 'terminal',
                                   'gate_passed', 'outcome_valid'}
                     and status['schema'] == 'n21-validation-aggregate-disposition-v1'
                     and isinstance(status['cohort_id'], str) and bool(status['cohort_id'])
                     and status['aggregate_only'] is True and status['terminal'] is True
                     and status['gate_passed'] is False and type(status['outcome_valid']) is bool,
                     'N22 requires a rejected aggregate validation disposition only')
        valid = status['outcome_valid'] is True
    else:
        valid = (status.get('status') in {'rejected_task0_necessary_gate', 'completed_all_twelve_audited'}
                 and status.get('dev_gate_promoted') is False)
        r['require'](valid or status.get('status') in {'failed', 'interrupted'},
                     'N22 N21 Dev predecessor is not terminal and rejected')
    r['require']((review['disposition'] == 'rejected' and valid)
                 or (review['disposition'] == 'invalid_resolved' and not valid
                     and review['cause_resolved'] is True),
                 'N22 invalid predecessor requires resolved-cause review, not numeric failure')
    return {'path': str(PREDECESSOR_REVIEW), 'sha256': sha(PREDECESSOR_REVIEW)}


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    r = runner
    meta = plan.get('n22_cohort')
    r['require'](isinstance(meta, dict)
                 and meta.get('schema') == 'n22-hold-lift-dev-v1'
                 and meta.get('cohort_id') == COHORT and meta.get('limits') == LIMITS
                 and meta.get('early_stop') == 'numeric_futility_after_complete_task_quadruple'
                 and sha(PROTOCOL) == PROTOCOL_SHA
                 and meta.get('protocol') == {'path': str(PROTOCOL), 'sha256': PROTOCOL_SHA}
                 and meta.get('predecessor_review') == predecessor_review(r)
                 and meta.get('n21_role') == 'ablation_control_only_no_promotion'
                 and sha(BUDGET_AMENDMENT) == r['GPU7_N22_AMENDMENT']['proposal_sha256']
                 and meta.get('budget_amendment') == {'path': str(BUDGET_AMENDMENT),
                                                     'sha256': sha(BUDGET_AMENDMENT)}
                 and meta.get('source_plan') == {'path': str(SOURCE_PLAN), 'sha256': sha(SOURCE_PLAN)},
                 'N22 prospective cohort/protocol differs')
    r['require'](plan.get('stage_condition') == r['E2_STAGE_CONDITION']
                 and plan.get('phase_authorization') == {'dev': True, 'validation': False, 'formal': False}
                 and set(plan.get('candidate_profiles', {})) == {'N21', 'N22'}
                 and set(manifest['profiles']) == set(ARMS)
                 and plan['episodes'] == expected_rows()
                 and all(plan.get(name) is None for name in
                         ('n11_cohort', 'n17_passive_physics', 'n7_cohort', 'n9_cohort', 'n18_cohort', 'n20_cohort', 'n21_cohort')),
                 'N22 matched matrix, profiles or phase gate differs')
    relative = 'configs/qd_ed_final/candidate_n22.json'
    for arm in ('N21', 'N22'):
        path = Path(root) / f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        r['require'](plan['candidate_profiles'][arm] == {'path': str(path), 'sha256': sha(path)},
                     'N22 candidate/ablation profile identity differs')
    n21 = manifest['profiles']['N21']['resolved_eds_config']
    n22 = manifest['profiles']['N22']['resolved_eds_config']
    n7 = json.loads((Path(root) / 'configs/qd_ed_final/candidate_n7.json').read_text())['profile']
    r['require'](n21 == {**manifest['profiles']['Q0']['resolved_eds_config'],
                         'qd_descriptor': n7['qd_descriptor'],
                         'qd_final_selection_mode': n7['qd_final_selection_mode'],
                         'qd_quality_mode': 'close_then_lift_v1'}
                 and n22 == {**n21, 'qd_quality_mode': 'close_hold_then_lift_v1'}
                 and n22['qd_descriptor'] == 'target_xy_quadrant_signed_height_v1'
                 and n22['qd_final_selection_mode'] == 'terminal_grasp_proximity_v1',
                 'N22 inherited algorithm/ablation profile differs')
    binding = plan.get('n22_gpu7_binding')
    r['require'](binding == {
            'schema': 'n22-gpu7-binding-v1',
            'addendum': {'path': str(GPU7_ADDENDUM), 'sha256': sha(GPU7_ADDENDUM)},
            'runtime': {'path': str(GPU7_RUNTIME), 'sha256': sha(GPU7_RUNTIME)},
            'physical_gpu': 7, 'uuid': GPU7_UUID,
            'egl_device_index': 4, 'reused_probe_resource_id': GPU7_PROOF},
            'N22 GPU7 binding differs')
    r['require'](plan['runtime_manifest_path'] == str(GPU7_RUNTIME)
                 and plan['runtime_manifest_sha256'] == sha(GPU7_RUNTIME)
                 and runtime == json.loads(GPU7_RUNTIME.read_text())
                 and r['runtime_gpu'](runtime) == 7
                 and runtime['gpu_mapping']['uuid'] == GPU7_UUID
                 and runtime['gpu_mapping']['egl_device_index'] == 4
                 and runtime.get('cuda_egl_verified') is True
                 and runtime.get('cuda_egl_probe', {}).get('resource_id') == GPU7_PROOF
                 and runtime.get('stage_recovered_error_condition') == r['E2_STAGE_CONDITION']
                 and runtime.get('stage_engineering_condition') ==
                 r['n4e1_support']().engineering_condition()
                 and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
                 'N22 E2 Stage/GPU binding differs')
    required = {'core/qd_lift_quality.py', 'core/rdt_policy_steer.py',
                'core/qd_terminal_population.py',
                'scripts/audit_decision_evidence.py', 'scripts/qd_ed_final_runner.py',
                'scripts/qd_ed_available_gpu_queue.py',
                'scripts/qd_ed_n22_dev_contract.py', 'scripts/qd_ed_n22_dev_prepare.py',
                'scripts/qd_ed_n22_dev_supervise.py', relative,
                'tests/test_qd_lift_quality.py', 'tests/test_qd_terminal_population.py',
                'tests/test_rdt_steer.py', 'tests/test_qd_ed_n22_dev.py',
                'tests/test_qd_hold_lift_quality.py',
                'configs/qd_ed_final/candidate_n21.json',
                'experiments/iteration_022_hold_lift/protocol-cpu.md',
                'experiments/iteration_022_hold_lift/protocol.md'}
    r['require'](required <= {item['path'] for item in plan['code_files']}
                 and sha(Path(root) / 'experiments/iteration_022_hold_lift/protocol.md') == sha(PROTOCOL)
                 and sha(Path(root) / 'experiments/iteration_022_hold_lift/protocol-cpu.md') == sha(CPU_PROTOCOL)
                 and relative in plan['scientific_config_files'],
                 'N22 source fingerprints incomplete')
    require_state(r['read_state'](Path(root) / 'research-state.yaml'), r)


def require_state(state, r):
    r['require'](state['resource_isolation']['status'] == 'ACTIVE'
                 and state['resource_isolation']['validation_status'] == 'PASS'
                 and state['resource_isolation']['private_budget'] is True
                 and state['budget'].get('amendment') == r['GPU7_N22_AMENDMENT']
                 and state['budget']['max_episode_attempts'] == 438
                 and state['budget']['max_gpu_hours'] == 100.0
                 and state['budget']['reserved'] == r['N22_BUCKETS']
                 and state['budget']['gpu_hour_reservations'] == {'validation': 32., 'formal': 12.}
                 and r['authorized_gpu'](state) == 7
                 and state.get('n22_gpu7_binding') == {
                     'scope': COHORT + '_only',
                     'user_reply': AUTONOMOUS_REPLY,
                     'selected_gpu': 7,
                     'addendum_path': str(GPU7_ADDENDUM),
                     'addendum_sha256': sha(GPU7_ADDENDUM)},
                 'N22 owning GPU budget/device authority differs')


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('nested N22 supervisor scope')
    _SCOPE = (str(Path(root).resolve()), plan['source_commit'], episode_key,
              os.getpid(), threading.get_ident())
    try:
        yield
    finally:
        _SCOPE = None


def require_scope(plan, root, runner, row=None):
    runner['require'](_SCOPE is not None and _SCOPE[0] == str(Path(root).resolve())
                      and _SCOPE[1] == plan['source_commit']
                      and _SCOPE[3:] == (os.getpid(), threading.get_ident())
                      and (row is None or row['episode_key'] == _SCOPE[2]),
                      'N22 dispatch requires its one-cell supervisor')


def protected_budget(state, events, resources, row, timeout, runner, *, plan):
    runner['require'](row in plan['episodes'] and row['iteration'] == COHORT
                      and row['profile'] in ARMS
                      and row['budget_bucket'] ==
                      ('baseline' if row['profile'] == 'C0' else 'development')
                      and timeout == LIMITS['episode_timeout_seconds']
                      and state['budget']['running'] == 0,
                      'N22 cell, bucket or timeout differs')
    local = [e for e in events if e.get('identity', {}).get('iteration') == COHORT]
    dispatches = [e for e in local if e.get('event') == 'dispatched']
    spent = sum(e.get('gpu_process_wall_seconds', 0.0) for e in local
                if e.get('event') in runner['TERMINAL'])
    runner['require'](len(dispatches) < LIMITS['dispatches']
                      and spent + timeout + LIMITS['cleanup_seconds'] <=
                      LIMITS['gpu_hours'] * 3600,
                      'N22 local dispatch/GPU-hour cap exceeded')
    snap = runner['budget_snapshot'](events, resources)
    protected = sum(max(0.0, hours - snap['gpu_hours_by_bucket'].get(name, 0.0))
                    for name, hours in state['budget']['gpu_hour_reservations'].items()
                    if name not in {'baseline', 'development'})
    runner['require'](snap['gpu_hours_consumed'] +
                      (timeout + LIMITS['cleanup_seconds']) / 3600 + protected
                      <= state['budget']['max_gpu_hours'] + 1e-9,
                      'N22 would borrow protected GPU hours')


def admission(plan, runtime, row, events, resources, root, runner):
    r = runner
    r['require'](row in plan['episodes'], 'N22 row is outside the frozen matrix')
    index = plan['episodes'].index(row)
    local = [event for event in events if event.get('identity', {}).get('iteration') == COHORT]
    r['require'](not any(event.get('episode_key') == row['episode_key'] for event in local),
                 'N22 reserved or dispatched cell cannot be retried')
    expected = plan['episodes'][:index]
    keys = {original['episode_key'] for original in expected}
    r['require'](all(event.get('episode_key') in keys for event in local),
                 'N22 dispatch must follow the exact task-major prefix')
    successes = 0
    for original in expected:
        terminal = [event for event in local if event.get('episode_key') == original['episode_key']
                    and event.get('event') in r['TERMINAL']]
        r['require'](len(terminal) == 1 and terminal[0]['event'] == 'valid'
                     and terminal[0].get('outcome_valid') is True,
                     'N22 preceding cells must all be valid; cohort cannot resume after invalid')
        report = r['read_json'](Path(terminal[0]['output_dir']) / 'eds_eval/decision-evidence-audit.json')
        r['require'](report.get('accepted') is True and report.get('evidence_complete') is True,
                     'N22 preceding cells must all be independently audited')
        if original['profile'] == 'N22':
            successes += int(terminal[0].get('success') is True)
    complete_tasks = index // len(ARMS)
    r['require'](successes + len(TASKS) - complete_tasks >= 5,
                 'N22 numeric futility closes later-task admission')
    return {'n22_cohort_id': COHORT,
            'n22_protocol_sha256': plan['n22_cohort']['protocol']['sha256'],
            'n22_arm_role': 'ablation_control_only' if row['profile'] == 'N21'
                            else 'candidate' if row['profile'] == 'N22' else 'control'}
