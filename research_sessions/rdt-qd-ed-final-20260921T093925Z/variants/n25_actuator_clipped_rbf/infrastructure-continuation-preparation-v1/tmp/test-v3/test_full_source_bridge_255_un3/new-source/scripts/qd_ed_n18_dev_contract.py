#!/usr/bin/env python3
"""Prospective GPU3 N18 matched Dev contract; protected phases stay closed."""
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
RUN_DIR = SESSION / 'variants/n18_lift_quality'
SOURCE_PLAN = SESSION / 'artifacts/continuation_20260928/n11-parent-survival-dev-v1/plan.frozen.v1.json'
E2_RUNTIME = SESSION / 'artifacts/continuation_20260928/n7-e2-passive-tracker-diagnostic-v1/runtime-manifest.e2.frozen.v1.json'
PROTOCOL = RUN_DIR / 'protocol-v1.md'
GPU7_ADDENDUM = RUN_DIR / 'gpu7-rebind-addendum-v1.md'
GPU7_UUID = 'GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF = 'rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
COHORT = 'N18_CLOSE_THEN_LIFT_DEV_20260929'
TASKS = (0, 3, 6, 9)
ARMS = ('C0', 'Q0', 'N18')
LIMITS = {'dispatches': 12, 'gpu_hours': 6.0,
          'episode_timeout_seconds': 1800, 'cleanup_seconds': 40,
          'physical_gpu': 3}
_SCOPE = None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_rows():
    parent = json.loads(SOURCE_PLAN.read_text())
    original = {row['task_id']: row for row in parent['episodes'] if row['profile'] == 'N7'}
    if set(original) != set(TASKS):
        raise ValueError('N18 original N7 four-task identities changed')
    rows = []
    for task in TASKS:
        for arm in ARMS:
            row = copy.deepcopy(original[task])
            row.update(iteration=COHORT, profile=arm,
                       episode_key=f'n18_dev_t{task:02d}_{arm.lower()}_20260929',
                       budget_bucket='baseline' if arm == 'C0' else 'development')
            rows.append(row)
    return rows


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    r = runner
    meta = plan.get('n18_cohort')
    r['require'](isinstance(meta, dict)
                 and meta.get('schema') == 'n18-close-then-lift-dev-v1'
                 and meta.get('cohort_id') == COHORT and meta.get('limits') == LIMITS
                 and meta.get('protocol') == {'path': str(PROTOCOL), 'sha256': sha(PROTOCOL)}
                 and meta.get('source_plan') == {'path': str(SOURCE_PLAN), 'sha256': sha(SOURCE_PLAN)},
                 'N18 prospective cohort/protocol differs')
    r['require'](plan.get('stage_condition') == r['E2_STAGE_CONDITION']
                 and plan.get('phase_authorization') == {'dev': True, 'validation': False, 'formal': False}
                 and set(plan.get('candidate_profiles', {})) == {'N18'}
                 and set(manifest['profiles']) == set(ARMS)
                 and plan['episodes'] == expected_rows()
                 and all(plan.get(name) is None for name in
                         ('n11_cohort', 'n17_passive_physics', 'n7_cohort', 'n9_cohort')),
                 'N18 matched matrix, profiles or phase gate differs')
    relative = 'configs/qd_ed_final/candidate_n18.json'
    r['require'](plan['candidate_profiles']['N18'] == {
        'path': str(Path(root) / relative), 'sha256': sha(Path(root) / relative)},
        'N18 candidate profile identity differs')
    n18 = manifest['profiles']['N18']['resolved_eds_config']
    n7 = json.loads((Path(root) / 'configs/qd_ed_final/candidate_n7.json').read_text())['profile']
    r['require'](n18 == {**manifest['profiles']['Q0']['resolved_eds_config'],
                         'qd_descriptor': n7['qd_descriptor'],
                         'qd_final_selection_mode': n7['qd_final_selection_mode'],
                         'qd_quality_mode': 'close_then_lift_v1'}
                 and n18['qd_descriptor'] == 'target_xy_quadrant_signed_height_v1'
                 and n18['qd_final_selection_mode'] == 'terminal_grasp_proximity_v1',
                 'N18 algorithm profile differs from N7 quality-only delta')
    rebind = plan.get('n18_gpu7_rebind')
    if rebind is None:
        r['require'](plan['runtime_manifest_path'] == str(E2_RUNTIME)
                     and plan['runtime_manifest_sha256'] == sha(E2_RUNTIME)
                     and r['runtime_gpu'](runtime) == 3,
                     'N18 original GPU3 runtime differs')
        device = 3
    else:
        parent_path = RUN_DIR / 'plan.frozen.v1.json'
        r['require'](rebind == {
            'schema': 'n18-gpu7-hardware-only-rebind-v1',
            'parent_plan': {'path': str(parent_path), 'sha256': sha(parent_path)},
            'addendum': {'path': str(GPU7_ADDENDUM), 'sha256': sha(GPU7_ADDENDUM)},
            'runtime': {'path': plan['runtime_manifest_path'],
                        'sha256': plan['runtime_manifest_sha256']},
            'physical_gpu': 7, 'uuid': GPU7_UUID,
            'egl_device_index': 4, 'reused_probe_resource_id': GPU7_PROOF},
            'N18 GPU7 user-authorized hardware-only binding differs')
        hardware = {'gpu_mapping', 'cuda_egl_verified', 'cuda_egl_probe',
                    'metadata_mapping_verified', 'egl_device_metadata_path', 'files'}
        old = json.loads(E2_RUNTIME.read_text())
        r['require']({k: v for k, v in runtime.items() if k not in hardware}
                     == {k: v for k, v in old.items() if k not in hardware}
                     and r['runtime_gpu'](runtime) == 7
                     and runtime['gpu_mapping']['uuid'] == GPU7_UUID
                     and runtime['gpu_mapping']['egl_device_index'] == 4
                     and runtime.get('cuda_egl_verified') is True
                     and runtime.get('cuda_egl_probe', {}).get('resource_id') == GPU7_PROOF,
                     'N18 GPU7 manifest changed nonhardware runtime or proof')
        device = 7
    r['require'](r['runtime_gpu'](runtime) == device
                 and runtime.get('stage_recovered_error_condition') == r['E2_STAGE_CONDITION']
                 and runtime.get('stage_engineering_condition') ==
                 r['n4e1_support']().engineering_condition()
                 and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
                 'N18 E2 Stage/GPU binding differs')
    required = {'core/qd_lift_quality.py', 'core/rdt_policy_steer.py',
                'scripts/audit_decision_evidence.py', 'scripts/qd_ed_final_runner.py',
                'scripts/qd_ed_n18_dev_contract.py', 'scripts/qd_ed_n18_dev_prepare.py',
                'scripts/qd_ed_n18_dev_supervise.py', relative,
                'tests/test_qd_lift_quality.py'}
    if rebind is not None:
        required.add('scripts/qd_ed_n18_gpu7_prepare.py')
    r['require'](required <= {item['path'] for item in plan['code_files']}
                 and relative in plan['scientific_config_files'],
                 'N18 source fingerprints incomplete')
    state = r['read_state'](Path(root) / 'research-state.yaml')
    r['require'](state['resource_isolation']['status'] == 'ACTIVE'
                 and state['resource_isolation']['validation_status'] == 'PASS'
                 and state['resource_isolation']['private_budget'] is True
                 and state['budget'].get('amendment') == r['GPU3_AMENDMENT']
                 and state['budget']['max_episode_attempts'] == 393
                 and state['budget']['max_gpu_hours'] == 100.0
                 and state['budget']['reserved'] == r['AMENDED_BUCKETS']
                 and r['authorized_gpu'](state) == device
                 and (device == 3 or state.get('n18_gpu7_rebind') == {
                     'scope': 'N18_CLOSE_THEN_LIFT_DEV_20260929_only',
                     'user_reply': '允许改用其他空闲 GPU',
                     'selected_gpu': 7,
                     'addendum_path': str(GPU7_ADDENDUM),
                     'addendum_sha256': sha(GPU7_ADDENDUM)}),
                 'N18 owning GPU budget/device authority differs')


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('nested N18 supervisor scope')
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
                      'N18 dispatch requires its one-cell supervisor')


def protected_budget(state, events, resources, row, timeout, runner, *, plan):
    runner['require'](row in plan['episodes'] and row['iteration'] == COHORT
                      and row['profile'] in ARMS
                      and row['budget_bucket'] ==
                      ('baseline' if row['profile'] == 'C0' else 'development')
                      and timeout == LIMITS['episode_timeout_seconds']
                      and state['budget']['running'] == 0,
                      'N18 cell, bucket or timeout differs')
    local = [e for e in events if e.get('identity', {}).get('iteration') == COHORT]
    dispatches = [e for e in local if e.get('event') == 'dispatched']
    spent = sum(e.get('gpu_process_wall_seconds', 0.0) for e in local
                if e.get('event') in runner['TERMINAL'])
    runner['require'](len(dispatches) < LIMITS['dispatches']
                      and spent + timeout + LIMITS['cleanup_seconds'] <=
                      LIMITS['gpu_hours'] * 3600,
                      'N18 local dispatch/GPU-hour cap exceeded')
    snap = runner['budget_snapshot'](events, resources)
    protected = sum(max(0.0, hours - snap['gpu_hours_by_bucket'].get(name, 0.0))
                    for name, hours in state['budget']['gpu_hour_reservations'].items()
                    if name not in {'baseline', 'development'})
    runner['require'](snap['gpu_hours_consumed'] +
                      (timeout + LIMITS['cleanup_seconds']) / 3600 + protected
                      <= state['budget']['max_gpu_hours'] + 1e-9,
                      'N18 would borrow protected GPU hours')


def admission(plan, runtime, row, events, resources, root, runner):
    return {'n18_cohort_id': COHORT,
            'n18_protocol_sha256': plan['n18_cohort']['protocol']['sha256']}
