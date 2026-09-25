#!/usr/bin/env python3
"""Freeze 60 matched N7/C0/Q0 validation originals without scientific edits."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
COHORT = 'N7_VALIDATION_C1_20260925'
TASKS = tuple(range(10))
BLOCKS = ('validation_c1_b1', 'validation_c1_b2')
ARMS = ('C0', 'Q0', 'N7')
FIELDS = ('env_seed', 'policy_seed', 'init_index', 'init_row_sha256', 'init_file_sha256', 'bddl_sha256')
PROTOCOL = 'experiments/iteration_007_direction_height/validation-protocol.md'
PROFILE = 'configs/qd_ed_final/candidate_n7.json'
DEV_PLAN = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260925/n7-dev-v1/plan.frozen.v1.json')
DEV_PLAN_SHA256 = '9cef973dd2a2f7cd07f82eb1965b96e2bcb3557f372e25dc4cd04dc622b277be'
DEV_REPORT = DEV_PLAN.with_name('full-dev-report-v1.json')
DEV_REPORT_SHA256 = 'c6ae8e5864f0e550d8d4c5651422e1b25a38161b2781bc1b7937b93d9edaa463'
EXPOSURE = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260925/n7-validation-c1-v1/prelaunch-exposure-v1.json')
EXPOSURE_SHA256 = 'e593d77e2bb2f6354b8633d932cdc7b0abbc84b7134b6d241d16b7eef8054cc9'
LIMITS = {'original_cells': 60, 'dispatches': 60, 'gpu_hours': 14.0,
          'episode_timeout_seconds': 1800, 'cleanup_seconds': 40, 'physical_gpu': 3}
CODE_ADDITIONS = {PROTOCOL, PROFILE, 'scripts/qd_ed_n7_validation_plan.py',
                  'scripts/qd_ed_n7_validation_supervise.py',
                  'scripts/qd_ed_n7_validation_report.py',
                  'scripts/qd_ed_final_runner.py',
                  'tests/test_qd_ed_n7_validation_plan.py'}
_SCOPE = None


def api(value):
    return SimpleNamespace(**value) if isinstance(value, dict) else value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows_from_parent(parent, seeds):
    template = copy.deepcopy(parent['episodes'][0])
    rows = []
    for block in BLOCKS:
        seed_rows = {item['task_id']: item for item in seeds['blocks'][block]}
        if set(seed_rows) != set(TASKS):
            raise ValueError('N7 validation seed block does not cover all backend tasks')
        for task in TASKS:
            seed = seed_rows[task]
            for arm in ARMS:
                row = copy.deepcopy(template)
                row.update({field: seed[field] for field in FIELDS})
                row.update(split='validation', seed_block=block, task_id=task,
                           iteration=COHORT, profile=arm, budget_bucket='validation',
                           episode_key=f'n7v_{block[-2:]}_t{task:02d}_{arm.lower()}_20260925',
                           timeout_seconds=1800)
                rows.append(row)
    return rows


def binding(plan, runtime):
    cohort = plan['n7_validation']
    return {'cohort_id': COHORT, 'protocol_sha256': cohort['protocol']['sha256'],
            'source_commit': plan['source_commit'],
            'profiles_sha256': plan['profiles_sha256'],
            'candidate_sha256': plan['candidate_profiles']['N7']['sha256'],
            'runtime_manifest_sha256': plan['runtime_manifest_sha256'],
            'runtime_inventory_sha256': plan['runtime_inventory_sha256'],
            'seed_plan_sha256': plan['seed_plan_sha256'],
            'stage_public_config_sha256': runtime['frozen_stage_provider']['public_config_sha256']}


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    r = api(runner); root = Path(root)
    cohort = plan.get('n7_validation')
    r.require(isinstance(cohort, dict) and cohort.get('schema') == 'qd-ed-n7-validation-c1-v1'
              and cohort.get('cohort_id') == COHORT and cohort.get('limits') == LIMITS,
              'N7 validation cohort/limits differ')
    r.require(plan.get('n7_cohort') is None and set(plan.get('candidate_profiles', {})) == {'N7'}
              and plan.get('phase_authorization') == {'dev': False, 'validation': True, 'formal': False},
              'N7 validation candidate/phase differs')
    r.require(cohort.get('protocol') == {'path': PROTOCOL, 'sha256': r.digest(root / PROTOCOL)},
              'N7 validation prospective protocol changed')
    r.require(cohort.get('dev_plan') == {'path': str(DEV_PLAN), 'sha256': DEV_PLAN_SHA256}
              and sha(DEV_PLAN) == DEV_PLAN_SHA256,
              'N7 original Dev source plan differs')
    dev = r.read_json(DEV_REPORT)
    r.require(cohort.get('dev_report') == {'path': str(DEV_REPORT), 'sha256': DEV_REPORT_SHA256}
              and sha(DEV_REPORT) == DEV_REPORT_SHA256
              and dev['decision'] == 'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'
              and dev['accepted_cells'] == 4 and dev['candidate_successes'] == 2,
              'N7 Dev eligibility differs')
    exposure = r.read_json(EXPOSURE)
    r.require(cohort.get('prelaunch_exposure') == {'path': str(EXPOSURE), 'sha256': EXPOSURE_SHA256}
              and sha(EXPOSURE) == EXPOSURE_SHA256
              and exposure['candidate_cells'] == 20
              and exposure['task_seed_overlaps_with_prior_or_formal'] == 0
              and exposure['same_init_row_across_two_seeds_per_task'] is True,
              'N7 validation exposure preflight differs')
    parent = r.read_json(DEV_PLAN)
    expected = rows_from_parent(parent, seeds)
    r.require(plan['episodes'] == expected and len(expected) == 60
              and {row['profile'] for row in expected} == set(ARMS)
              and [row['task_id'] for row in expected[::3]] == list(TASKS) * 2,
              'N7 validation matched rows/order differ')
    r.require(Path(plan['profiles_path']).resolve()
              == (root / 'configs/qd_ed_final/n4_observed_baseline_profiles.json').resolve()
              and set(manifest['profiles']) == {'C0', 'Q0', 'N7'}
              and manifest['profiles']['N7']['resolved_eds_config']['qd_descriptor'] == 'target_xy_quadrant_signed_height_v1'
              and manifest['profiles']['N7']['resolved_eds_config']['qd_final_selection_mode'] == 'terminal_grasp_proximity_v1',
              'N7 validation profile/controls differ')
    r.require(plan['candidate_profiles']['N7'] == {'path': str(root / PROFILE), 'sha256': r.digest(root / PROFILE)}
              and plan['candidate_profiles']['N7']['sha256'] == parent['candidate_profiles']['N7']['sha256'],
              'N7 candidate scientific profile changed after Dev')
    r.require(plan['runtime_manifest_path'] == parent['runtime_manifest_path']
              and plan['runtime_manifest_sha256'] == parent['runtime_manifest_sha256']
              and runtime == r.read_json(parent['runtime_manifest_path'])
              and r.runtime_gpu(runtime) == 3
              and cohort.get('stage_condition') == runtime['stage_engineering_condition'],
              'N7 validation runtime/model/Stage/GPU differs from Dev')
    paths = {record['path'] for record in plan['code_files']}
    r.require(CODE_ADDITIONS <= paths and set(plan['scientific_config_files']) <= paths,
              'N7 validation source/protocol fingerprints missing')
    state = r.read_state(root / 'research-state.yaml')
    r.require(state['resource_isolation']['status'] == 'ACTIVE'
              and state['resource_isolation']['validation_status'] == 'PASS'
              and state['resource_isolation']['private_budget'] is True
              and state['budget']['max_episode_attempts'] == 240
              and state['budget']['max_gpu_hours'] == 48.0
              and state['budget']['reserved'] == r.BUCKETS
              and r.authorized_gpu(state) == 3,
              'N7 validation private GPU3 authority differs')


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('N7 validation nested supervisor scope')
    _SCOPE = (str(Path(root).resolve()), plan['source_commit'], episode_key,
              os.getpid(), threading.get_ident())
    try:
        yield
    finally:
        _SCOPE = None


def require_scope(plan, root, runner, row=None):
    r = api(runner)
    r.require(_SCOPE is not None and _SCOPE[0] == str(Path(root).resolve())
              and _SCOPE[1] == plan['source_commit']
              and _SCOPE[3:] == (os.getpid(), threading.get_ident())
              and (row is None or row['episode_key'] == _SCOPE[2]),
              'N7 validation requires its one-cell audited supervisor')


def protected_budget(state, events, resources, row, timeout, runner, *, plan):
    r = api(runner)
    r.require(row['profile'] in ARMS and row['iteration'] == COHORT
              and row['budget_bucket'] == 'validation' and row['split'] == 'validation'
              and timeout == LIMITS['episode_timeout_seconds'],
              'N7 validation cell/timeout/bucket differs')
    r.require(state['budget']['reserved'] == r.BUCKETS and state['budget']['running'] == 0,
              'N7 validation private budget/reserves or running attempt changed')
    cohort_events = [event for event in events if event.get('identity', {}).get('iteration') == COHORT]
    dispatched = [event for event in cohort_events if event.get('event') == 'dispatched']
    settled = [event for event in cohort_events if event.get('event') in r.TERMINAL]
    spent = sum(event.get('gpu_process_wall_seconds', 0.0) for event in settled)
    r.require(len(dispatched) < LIMITS['dispatches']
              and spent + timeout + LIMITS['cleanup_seconds'] <= LIMITS['gpu_hours'] * 3600,
              'N7 validation dispatch/GPU-hour cap exceeded')
    r.require(state['budget']['gpu_hours_consumed'] + (timeout + LIMITS['cleanup_seconds']) / 3600
              + state['budget']['gpu_hour_reservations']['formal'] <= state['budget']['max_gpu_hours'],
              'N7 validation cannot borrow formal GPU-hour reserve')


def admission(plan, runtime, row, events, resources, root, runner):
    return {'n7_validation_cohort_id': COHORT,
            'n7_validation_frozen_identity': binding(plan, runtime)}


def build_plan(parent, root, head, runner):
    r = api(runner); root = Path(root)
    r.require(sha(DEV_PLAN) == DEV_PLAN_SHA256 and sha(DEV_REPORT) == DEV_REPORT_SHA256
              and sha(EXPOSURE) == EXPOSURE_SHA256 and parent['source_commit'] != head,
              'N7 validation parent/report/exposure/head identity invalid')
    seeds = r.read_json(parent['seed_plan_path'])
    paths = {record['path'] for record in parent['code_files']} | CODE_ADDITIONS | r.REQUIRED_CODE
    code_files = []
    for relative in sorted(paths):
        actual = (root / relative).read_bytes()
        committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=root)
        r.require(actual == committed, 'N7 validation uncommitted source: ' + relative)
        code_files.append({'path': relative, 'sha256': hashlib.sha256(actual).hexdigest()})
    plan = copy.deepcopy(parent)
    plan.pop('n7_cohort', None)
    plan.update(frozen=True, worktree=str(root), source_commit=head,
                episodes=rows_from_parent(parent, seeds), code_files=code_files,
                phase_authorization={'dev': False, 'validation': True, 'formal': False},
                scientific_config_files=sorted(set(parent['scientific_config_files']) | {PROTOCOL}),
                egl_mapping_verified=True)
    runtime = r.read_json(plan['runtime_manifest_path'])
    plan['n7_validation'] = {'schema': 'qd-ed-n7-validation-c1-v1', 'cohort_id': COHORT,
        'limits': copy.deepcopy(LIMITS),
        'protocol': {'path': PROTOCOL, 'sha256': r.digest(root / PROTOCOL)},
        'dev_plan': {'path': str(DEV_PLAN), 'sha256': DEV_PLAN_SHA256},
        'dev_report': {'path': str(DEV_REPORT), 'sha256': DEV_REPORT_SHA256},
        'prelaunch_exposure': {'path': str(EXPOSURE), 'sha256': EXPOSURE_SHA256},
        'stage_condition': copy.deepcopy(runtime['stage_engineering_condition'])}
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev-plan', type=Path, required=True)
    parser.add_argument('--source-head', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import qd_ed_final_runner as r
    r.require(args.dev_plan.resolve() == DEV_PLAN and not args.output.exists(),
              'N7 validation frozen Dev parent or output path differs')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    r.require(head == args.source_head, 'N7 validation source HEAD differs')
    with r.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
        parent = r.read_json(DEV_PLAN)
        plan = build_plan(parent, ROOT, head, r.__dict__)
        output = r.owned(args.output, plan['artifact_root'])
        output.parent.mkdir(parents=True, exist_ok=True)
        r.durable_json(output, plan)
        r.validate_plan(output, root=ROOT)
    print(json.dumps({'status': 'frozen_reviewable_no_execution_release',
                      'plan': str(output), 'sha256': sha(output),
                      'episodes': len(plan['episodes']), 'per_arm': 20}))


if __name__ == '__main__':
    main()
