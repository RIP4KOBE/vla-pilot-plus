#!/usr/bin/env python3
"""Fail-closed N11 four-arm exposed-Dev cohort contract, GPU3 only."""
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
ART = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
RUN_DIR = ART / 'continuation_20260928/n11-parent-survival-dev-v1'
SOURCE_PLAN = ART / 'continuation_20260925/n7-dev-v1/plan.frozen.v1.json'
SOURCE_PLAN_SHA = '9cef973dd2a2f7cd07f82eb1965b96e2bcb3557f372e25dc4cd04dc622b277be'
E2_RUNTIME = ART / 'continuation_20260928/n7-e2-passive-tracker-diagnostic-v1/runtime-manifest.e2.frozen.v1.json'
E2_RUNTIME_SHA = 'efcf53c1d8ffaf8bf1049a01969407dea634838e2943d07c6cf7810319e8ff5c'
PROTOCOL = SESSION / 'variants/n11_parent_survival/protocol-v1.md'
COHORT = 'N11_EXACT_PARENT_SURVIVAL_DEV_20260928'
TASKS = (0, 3, 6, 9)
ARMS = ('C0', 'Q0', 'N7', 'N11')
LIMITS = {'dispatches': 16, 'gpu_hours': 6.0,
          'episode_timeout_seconds': 1800, 'cleanup_seconds': 40,
          'physical_gpu': 3}
_SCOPE = None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_rows():
    if sha(SOURCE_PLAN) != SOURCE_PLAN_SHA:
        raise ValueError('N11 historical N7 plan changed')
    parent = json.loads(SOURCE_PLAN.read_text())
    original = {row['task_id']: row for row in parent['episodes'] if row['profile'] == 'N7'}
    if set(original) != set(TASKS):
        raise ValueError('N11 original N7 four-task identities changed')
    rows = []
    for task in TASKS:
        for arm in ARMS:
            row = copy.deepcopy(original[task])
            row.update(iteration=COHORT, profile=arm,
                       episode_key=f'n11_dev_t{task:02d}_{arm.lower()}_20260928',
                       budget_bucket='baseline' if arm == 'C0' else 'development')
            rows.append(row)
    return rows


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    r = runner
    meta = plan.get('n11_cohort')
    r['require'](isinstance(meta, dict)
                 and meta.get('schema') == 'n11-exact-parent-survival-dev-v1'
                 and meta.get('cohort_id') == COHORT and meta.get('limits') == LIMITS
                 and meta.get('protocol') == {'path':str(PROTOCOL),'sha256':sha(PROTOCOL)}
                 and meta.get('source_plan') == {'path':str(SOURCE_PLAN),'sha256':SOURCE_PLAN_SHA},
                 'N11 prospective cohort/protocol differs')
    r['require'](plan.get('stage_condition') == r['E2_STAGE_CONDITION']
                 and plan.get('phase_authorization') ==
                 {'dev':True,'validation':False,'formal':False}
                 and set(plan.get('candidate_profiles',{})) == {'N7','N11'}
                 and set(manifest['profiles']) == set(ARMS)
                 and plan['episodes'] == expected_rows()
                 and plan.get('n7_e2_passive_diagnostic') is None
                 and plan.get('n7_cohort') is None and plan.get('n9_cohort') is None,
                 'N11 matrix, profiles, or phase gate differs')
    for arm in ('N7','N11'):
        relative = f'configs/qd_ed_final/candidate_{arm.lower()}.json'
        expected = {'path':str(Path(root)/relative),'sha256':sha(Path(root)/relative)}
        r['require'](plan['candidate_profiles'][arm] == expected,
                     'N11 candidate profile identity differs: ' + arm)
    n7 = manifest['profiles']['N7']['resolved_eds_config']
    n11 = manifest['profiles']['N11']['resolved_eds_config']
    r['require'](n11 == {**n7, 'qd_parent_survivor_count':4}
                 and n7.get('qd_parent_survivor_count',0) == 0
                 and n11['qd_descriptor'] == 'target_xy_quadrant_signed_height_v1'
                 and n11['qd_final_selection_mode'] == 'terminal_grasp_proximity_v1',
                 'N11 algorithm profile differs from exact N7 parent-survival delta')
    r['require'](plan['runtime_manifest_path'] == str(E2_RUNTIME)
                 and plan['runtime_manifest_sha256'] == E2_RUNTIME_SHA
                 and sha(E2_RUNTIME) == E2_RUNTIME_SHA
                 and r['runtime_gpu'](runtime) == 3
                 and runtime.get('stage_recovered_error_condition') == r['E2_STAGE_CONDITION']
                 and runtime.get('stage_engineering_condition') ==
                 r['n4e1_support']().engineering_condition()
                 and runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
                 'N11 exact E2 Stage/GPU binding differs')
    required = {'core/qd_ed.py','core/rdt_policy_steer.py','core/eds_eval_metrics.py',
                'scripts/audit_decision_evidence.py','scripts/qd_ed_final_runner.py',
                'scripts/qd_ed_n11_dev_contract.py','scripts/qd_ed_n11_dev_prepare.py',
                'scripts/qd_ed_n11_dev_supervise.py','configs/qd_ed_final/candidate_n11.json',
                'tests/test_qd_parent_survival.py'}
    r['require'](required <= {item['path'] for item in plan['code_files']}
                 and {'configs/qd_ed_final/candidate_n7.json',
                      'configs/qd_ed_final/candidate_n11.json'} <=
                 set(plan['scientific_config_files']),
                 'N11 source fingerprints incomplete')
    state = r['read_state'](Path(root)/'research-state.yaml')
    r['require'](state['resource_isolation']['status'] == 'ACTIVE'
                 and state['resource_isolation']['validation_status'] == 'PASS'
                 and state['resource_isolation']['private_budget'] is True
                 and state['budget'].get('amendment') == r['GPU3_AMENDMENT']
                 and state['budget']['max_episode_attempts'] == 393
                 and state['budget']['max_gpu_hours'] == 100.0
                 and state['budget']['reserved'] == r['AMENDED_BUCKETS']
                 and r['authorized_gpu'](state) == 3,
                 'N11 owning GPU3 private authority differs')


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('nested N11 supervisor scope')
    _SCOPE = (str(Path(root).resolve()),plan['source_commit'],episode_key,
              os.getpid(),threading.get_ident())
    try:
        yield
    finally:
        _SCOPE = None


def require_scope(plan, root, runner, row=None):
    runner['require'](_SCOPE is not None and _SCOPE[0] == str(Path(root).resolve())
                      and _SCOPE[1] == plan['source_commit']
                      and _SCOPE[3:] == (os.getpid(),threading.get_ident())
                      and (row is None or row['episode_key'] == _SCOPE[2]),
                      'N11 dispatch requires its one-cell supervisor')


def protected_budget(state, events, resources, row, timeout, runner, *, plan):
    runner['require'](row in plan['episodes'] and row['iteration'] == COHORT
                      and row['profile'] in ARMS
                      and row['budget_bucket'] ==
                      ('baseline' if row['profile'] == 'C0' else 'development')
                      and timeout == LIMITS['episode_timeout_seconds']
                      and state['budget']['running'] == 0,
                      'N11 cell, bucket, or timeout differs')
    local = [e for e in events if e.get('identity',{}).get('iteration') == COHORT]
    dispatches = [e for e in local if e.get('event') == 'dispatched']
    spent = sum(e.get('gpu_process_wall_seconds',0.0) for e in local
                if e.get('event') in runner['TERMINAL'])
    runner['require'](len(dispatches) < LIMITS['dispatches']
                      and spent + timeout + LIMITS['cleanup_seconds'] <=
                      LIMITS['gpu_hours']*3600,
                      'N11 local dispatch/GPU-hour cap exceeded')
    snap = runner['budget_snapshot'](events, resources)
    protected = sum(max(0.0, hours-snap['gpu_hours_by_bucket'].get(name,0.0))
                    for name,hours in state['budget']['gpu_hour_reservations'].items()
                    if name not in {'baseline','development'})
    runner['require'](snap['gpu_hours_consumed'] +
                      (timeout + LIMITS['cleanup_seconds'])/3600 + protected
                      <= state['budget']['max_gpu_hours'] + 1e-9,
                      'N11 would borrow protected GPU hours')


def admission(plan, runtime, row, events, resources, root, runner):
    return {'n11_cohort_id':COHORT,
            'n11_protocol_sha256':plan['n11_cohort']['protocol']['sha256']}
