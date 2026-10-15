#!/usr/bin/env python3
"""Freeze N7's four exposed Dev cells with one N6 descriptor delta."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
from contextlib import contextmanager
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
COHORT = 'N7_DIRECTION_HEIGHT_DEV_20260925'
TASKS = (0, 3, 6, 9)
FIELDS = ('env_seed', 'policy_seed', 'init_index', 'init_row_sha256', 'init_file_sha256', 'bddl_sha256')
PROTOCOL = 'experiments/iteration_007_direction_height/protocol.md'
CLARIFICATION = 'experiments/iteration_006_height_aware/prelaunch-measurement-clarification-v1.md'
PROFILE = 'configs/qd_ed_final/candidate_n7.json'
PARENT_PROFILE = 'configs/qd_ed_final/candidate_n6.json'
PARENT_PLAN = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260925/n6-dev-v1/plan.frozen.v2.json')
PARENT_PLAN_SHA256 = '822240abf71493a9cb402729bf174558a4115ad60264fe3c1379cbdec605aa84'
PRIOR_REPORT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260925/n6-dev-v1/full-dev-report-v1.json')
PRIOR_REPORT_SHA256 = '6ba9508e55b7e58ecd9fb376f0105f217dfc67825fe762f70092ea9984344fe0'
PREREQUISITE = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260925/n7-prerequisite-readonly-v1.json')
PREREQUISITE_SHA256 = '65ecd0b855b46f35aaa88d6865f2c0549b42a757555aef6d7a479105b9ea5de3'
LIMITS = {'original_cells': 4, 'dispatches': 8, 'recoveries': 4, 'gpu_hours': 4.2,
          'episode_timeout_seconds': 1800, 'cleanup_seconds': 40, 'physical_gpu': 3}
CODE_ADDITIONS = {PROTOCOL, CLARIFICATION, PROFILE, 'scripts/qd_ed_n7_plan.py',
                  'scripts/qd_ed_n7_supervise.py', 'scripts/qd_ed_n7_report.py',
                  'tests/test_qd_direction_height.py', 'tests/test_qd_ed_n7_plan.py',
                  'tests/test_n4_terminal_population_audit.py',
                  'core/qd_ed.py', 'core/rdt_policy_steer.py',
                  'scripts/qd_ed_final_runner.py', 'scripts/audit_decision_evidence.py'}
_SCOPE = None


def api(value):
    return SimpleNamespace(**value) if isinstance(value, dict) else value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows_from_parent(parent):
    previous = {row['task_id']: row for row in parent['episodes']
                if row['profile'] == 'N6' and not row.get('retry_of')}
    if set(previous) != set(TASKS):
        raise ValueError('N7 parent lacks four N6 original Dev identities')
    rows = []
    for task in TASKS:
        row = copy.deepcopy(previous[task])
        row.update(iteration=COHORT, profile='N7',
                   episode_key=f'n7_dev_t{task:02d}_20260925', budget_bucket='development')
        rows.append(row)
    return rows


def binding(plan, runtime):
    cohort = plan['n7_cohort']
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
    cohort = plan.get('n7_cohort')
    r.require(isinstance(cohort, dict) and cohort.get('schema') == 'qd-ed-n7-direction-height-dev-v1'
              and cohort.get('cohort_id') == COHORT and cohort.get('limits') == LIMITS,
              'N7 exact cohort/limits missing')
    r.require(plan.get('n6_cohort') is None and set(plan.get('candidate_profiles', {})) == {'N7'},
              'N7 plan must contain only its candidate')
    r.require(cohort.get('protocol') == {'path': PROTOCOL, 'sha256': r.digest(root / PROTOCOL)},
              'N7 protocol identity differs')
    r.require(cohort.get('measurement_clarification') == {'path': CLARIFICATION, 'sha256': r.digest(root / CLARIFICATION)},
              'N7 prelaunch measurement clarification differs')
    r.require(cohort.get('parent_plan') == {'path': str(PARENT_PLAN), 'sha256': PARENT_PLAN_SHA256}
              and sha(PARENT_PLAN) == PARENT_PLAN_SHA256,
              'N7 matched parent plan differs')
    prior = r.read_json(PRIOR_REPORT)
    r.require(cohort.get('prior_report') == {'path': str(PRIOR_REPORT), 'sha256': PRIOR_REPORT_SHA256}
              and r.digest(PRIOR_REPORT) == PRIOR_REPORT_SHA256
              and prior['decision'] == 'REJECT_DEV' and prior['accepted_cells'] == 4
              and prior['candidate_successes'] == 1,
              'N7 prior complete negative report differs')
    r.require(cohort.get('prerequisite') == {'path': str(PREREQUISITE), 'sha256': PREREQUISITE_SHA256}
              and r.digest(PREREQUISITE) == PREREQUISITE_SHA256,
              'N7 retrospective mechanism read differs')
    parent = r.read_json(PARENT_PLAN)
    r.require(plan.get('phase_authorization') == {'dev': True, 'validation': False, 'formal': False}
              and plan.get('episodes') == rows_from_parent(parent),
              'N7 four original Dev cells/order/phase differ')
    r.require(all({field: row[field] for field in FIELDS}
                  == {field: parent['episodes'][i][field] for field in FIELDS}
                  for i, row in enumerate(plan['episodes'])),
              'N7 matched seeds/input rows differ')
    r.require(Path(plan.get('profiles_path', '')).resolve()
              == (root / 'configs/qd_ed_final/n4_observed_baseline_profiles.json').resolve()
              and plan['profiles_sha256'] == r.digest(plan['profiles_path'])
              and set(manifest['profiles']) == {'C0', 'Q0', 'N7'},
              'N7 observed controls/profile manifest differ')
    candidate = r.read_json(root / PROFILE)
    r.require(plan['candidate_profiles']['N7'] == {'path': str(root / PROFILE), 'sha256': r.digest(root / PROFILE)}
              and candidate['parent_candidate'] == {'path': PARENT_PROFILE, 'sha256': r.digest(root / PARENT_PROFILE)}
              and manifest['profiles']['N7']['resolved_eds_config']['qd_descriptor'] == 'target_xy_quadrant_signed_height_v1'
              and manifest['profiles']['N7']['resolved_eds_config']['qd_final_selection_mode'] == 'terminal_grasp_proximity_v1',
              'N7 candidate or inherited N6 consumer differs')
    r.require(cohort.get('stage_condition') == r.n4e1_support().engineering_condition()
              and runtime.get('stage_engineering_condition') == cohort['stage_condition']
              and r.runtime_gpu(runtime) == 3,
              'N7 inherited Codex/GPU3 condition differs')
    r.require(plan['runtime_manifest_path'] == parent['runtime_manifest_path']
              and plan['runtime_manifest_sha256'] == parent['runtime_manifest_sha256']
              and runtime == r.read_json(parent['runtime_manifest_path']),
              'N7 runtime/input manifest differs from N6')
    paths = {record['path'] for record in plan['code_files']}
    r.require(CODE_ADDITIONS <= paths and set(plan['scientific_config_files']) <= paths,
              'N7 source/protocol fingerprints missing')
    state = r.read_state(root / 'research-state.yaml')
    r.require(state['resource_isolation']['status'] == 'ACTIVE'
              and state['resource_isolation']['validation_status'] == 'PASS'
              and state['resource_isolation']['private_budget'] is True
              and state['budget']['max_episode_attempts'] == 240
              and state['budget']['max_gpu_hours'] == 48.0
              and state['budget']['reserved'] == r.BUCKETS
              and r.authorized_gpu(state) == 3,
              'N7 independent GPU3 authority differs')


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('N7 nested supervisor scope')
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
              'N7 requires its one-cell audited supervisor')


def protected_budget(state, events, resources, row, timeout, runner, *, plan):
    r = api(runner)
    r.require(row['profile'] == 'N7' and row['iteration'] == COHORT
              and row['budget_bucket'] == 'development'
              and timeout == LIMITS['episode_timeout_seconds'],
              'N7 cell/timeout/bucket differs')
    r.require(state['budget']['reserved'] == r.BUCKETS and state['budget']['running'] == 0,
              'N7 private budget/reserves or running attempt changed')
    n7_events = [event for event in events if event.get('identity', {}).get('iteration') == COHORT]
    dispatched = [event for event in n7_events if event.get('event') == 'dispatched']
    settled = [event for event in n7_events if event.get('event') in r.TERMINAL]
    spent = sum(event.get('gpu_process_wall_seconds', 0.0) for event in settled)
    r.require(len(dispatched) < LIMITS['dispatches']
              and spent + timeout + LIMITS['cleanup_seconds'] <= LIMITS['gpu_hours'] * 3600,
              'N7 local dispatch/GPU-hour cap exceeded')
    r.require(state['budget']['gpu_hours_consumed'] + (timeout + LIMITS['cleanup_seconds']) / 3600
              + state['budget']['gpu_hour_reservations']['validation']
              + state['budget']['gpu_hour_reservations']['formal'] <= state['budget']['max_gpu_hours'],
              'N7 cannot borrow protected GPU-hour reserves')


def admission(plan, runtime, row, events, resources, root, runner):
    return {'n7_cohort_id': COHORT, 'n7_frozen_identity': binding(plan, runtime)}


def build_plan(parent, root, head, runner):
    r = api(runner); root = Path(root)
    r.require(sha(PARENT_PLAN) == PARENT_PLAN_SHA256 and parent['source_commit'] != head,
              'N7 parent plan/head identity invalid')
    paths = {record['path'] for record in parent['code_files']} | CODE_ADDITIONS | r.REQUIRED_CODE
    code_files = []
    for relative in sorted(paths):
        actual = (root / relative).read_bytes()
        committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=root)
        r.require(actual == committed, 'N7 uncommitted source: ' + relative)
        code_files.append({'path': relative, 'sha256': hashlib.sha256(actual).hexdigest()})
    plan = copy.deepcopy(parent)
    plan.pop('n6_cohort', None)
    plan.update(frozen=True, worktree=str(root), source_commit=head,
        episodes=rows_from_parent(parent), code_files=code_files,
        candidate_profiles={'N7': {'path': str(root / PROFILE), 'sha256': r.digest(root / PROFILE)}},
        phase_authorization={'dev': True, 'validation': False, 'formal': False},
        scientific_config_files=sorted(set(parent['scientific_config_files']) | {PROTOCOL, CLARIFICATION, PROFILE}),
        egl_mapping_verified=True)
    runtime = r.read_json(plan['runtime_manifest_path'])
    plan['n7_cohort'] = {'schema': 'qd-ed-n7-direction-height-dev-v1', 'cohort_id': COHORT,
        'limits': copy.deepcopy(LIMITS),
        'protocol': {'path': PROTOCOL, 'sha256': r.digest(root / PROTOCOL)},
        'measurement_clarification': {'path': CLARIFICATION, 'sha256': r.digest(root / CLARIFICATION)},
        'parent_plan': {'path': str(PARENT_PLAN), 'sha256': PARENT_PLAN_SHA256},
        'prior_report': {'path': str(PRIOR_REPORT), 'sha256': PRIOR_REPORT_SHA256},
        'prerequisite': {'path': str(PREREQUISITE), 'sha256': PREREQUISITE_SHA256},
        'stage_condition': copy.deepcopy(runtime['stage_engineering_condition'])}
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-plan', type=Path, required=True)
    parser.add_argument('--source-head', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import qd_ed_final_runner as r
    r.require(args.parent_plan.resolve() == PARENT_PLAN and not args.output.exists(),
              'N7 frozen parent or output path differs')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    r.require(head == args.source_head, 'N7 source HEAD differs')
    with r.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
        parent = r.read_json(PARENT_PLAN)
        plan = build_plan(parent, ROOT, head, r.__dict__)
        output = r.owned(args.output, plan['artifact_root'])
        output.parent.mkdir(parents=True, exist_ok=True)
        r.durable_json(output, plan)
        r.validate_plan(output, root=ROOT)
    print(json.dumps({'status': 'frozen_reviewable_no_execution_release',
                      'plan': str(output), 'sha256': sha(output),
                      'episodes': [x['episode_key'] for x in plan['episodes']]}))


if __name__ == '__main__':
    main()
