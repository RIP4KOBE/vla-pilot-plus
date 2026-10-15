#!/usr/bin/env python3
"""Freeze N9 and matched C0/Q0/N7 exposed-Dev cells on physical GPU3."""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
PARENT = ARTIFACT / 'continuation_20260925/n7-dev-v1/plan.frozen.v1.json'
PARENT_SHA = '9cef973dd2a2f7cd07f82eb1965b96e2bcb3557f372e25dc4cd04dc622b277be'
PROTOCOL = 'experiments/iteration_009_contact_sweep/protocol.md'
N7_PROFILE = 'configs/qd_ed_final/candidate_n7.json'
N9_PROFILE = 'configs/qd_ed_final/candidate_n9.json'
COHORT = 'N9_CONTACT_SWEEP_DEV_20260928'
TASKS = (0, 3, 6, 9)
ARMS = ('C0', 'Q0', 'N7', 'N9')
LIMITS = {'original_cells': 16, 'dispatches': 16, 'recoveries': 0,
          'gpu_hours': 10.0, 'episode_timeout_seconds': 1800,
          'cleanup_seconds': 40, 'physical_gpu': 3}
ADDITIONS = {PROTOCOL, N7_PROFILE, N9_PROFILE, 'core/qd_contact_sweep.py',
             'core/rdt_policy_steer.py', 'scripts/audit_decision_evidence.py',
             'scripts/qd_ed_final_runner.py', 'scripts/qd_ed_n9_plan.py',
             'scripts/qd_ed_n9_supervise.py', 'scripts/qd_ed_n9_report.py',
             'tests/test_qd_contact_sweep.py'}
_SCOPE = None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows_from_parent(parent):
    source = {row['task_id']: row for row in parent['episodes'] if row['profile'] == 'N7'}
    if set(source) != set(TASKS):
        raise ValueError('N9 requires the exact four frozen N7 Dev identities')
    rows = []
    for task in TASKS:
        for arm in ARMS:
            row = copy.deepcopy(source[task])
            row.update(iteration=COHORT, profile=arm,
                       episode_key=f'n9_dev_t{task:02d}_{arm.lower()}_20260928',
                       budget_bucket='development')
            rows.append(row)
    return rows


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    root = Path(root)
    cohort = plan.get('n9_cohort')
    runner['require'](isinstance(cohort, dict) and cohort.get('schema') == 'qd-ed-n9-contact-sweep-dev-v1'
                      and cohort.get('cohort_id') == COHORT and cohort.get('limits') == LIMITS,
                      'N9 frozen cohort/limits differ')
    runner['require'](cohort['protocol'] == {'path': PROTOCOL, 'sha256': sha(root / PROTOCOL)}
                      and cohort['parent_plan'] == {'path': str(PARENT), 'sha256': PARENT_SHA}
                      and sha(PARENT) == PARENT_SHA, 'N9 prospective protocol or parent differs')
    parent = runner['read_json'](PARENT)
    runner['require'](plan['episodes'] == rows_from_parent(parent)
                      and plan['phase_authorization'] == {'dev': True, 'validation': False, 'formal': False}
                      and set(plan['candidate_profiles']) == {'N7', 'N9'}
                      and set(manifest['profiles']) == {'C0', 'Q0', 'N7', 'N9'},
                      'N9 matched matrix, profiles, or phase gate differs')
    for arm, path in (('N7', N7_PROFILE), ('N9', N9_PROFILE)):
        runner['require'](plan['candidate_profiles'][arm] ==
                          {'path': str(root / path), 'sha256': sha(root / path)},
                          'N9 candidate identity differs: ' + arm)
    runner['require'](manifest['profiles']['N7']['resolved_eds_config']['qd_final_selection_mode']
                      == 'terminal_grasp_proximity_v1'
                      and manifest['profiles']['N9']['resolved_eds_config']['qd_final_selection_mode']
                      == 'terminal_contact_sweep_v1'
                      and manifest['profiles']['N9']['resolved_eds_config']['qd_descriptor']
                      == 'target_xy_quadrant_signed_height_v1',
                      'N9 algorithm identities differ')
    runner['require'](all(plan[key] == parent[key] for key in
                          ('runtime_manifest_path', 'runtime_manifest_sha256',
                           'runtime_inventory_path', 'runtime_inventory_sha256',
                           'seed_plan_path', 'seed_plan_sha256', 'profiles_path', 'profiles_sha256'))
                      and runner['runtime_gpu'](runtime) == 3
                      and runtime['stage_engineering_condition'] == cohort['stage_condition'],
                      'N9 inherited model/input/Stage/GPU differs')
    runner['require'](ADDITIONS <= {r['path'] for r in plan['code_files']}
                      and set(plan['scientific_config_files']) <= {r['path'] for r in plan['code_files']},
                      'N9 source fingerprints incomplete')
    state = runner['read_state'](root / 'research-state.yaml')
    runner['require'](state['resource_isolation']['status'] == 'ACTIVE'
                      and state['resource_isolation']['validation_status'] == 'PASS'
                      and state['resource_isolation']['private_budget'] is True
                      and state['budget']['max_episode_attempts'] == 240
                      and state['budget']['max_gpu_hours'] == 48.0
                      and state['budget']['reserved'] == runner['BUCKETS']
                      and runner['authorized_gpu'](state) == 3,
                      'N9 private GPU3 authority differs')


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('N9 nested supervisor')
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
                      and (row is None or _SCOPE[2] == row['episode_key']),
                      'N9 requires one-cell audited supervisor')


def protected_budget(state, events, resources, row, timeout, runner, *, plan):
    runner['require'](row in plan['episodes'] and row['iteration'] == COHORT
                      and row['budget_bucket'] == 'development'
                      and timeout == LIMITS['episode_timeout_seconds']
                      and state['budget']['running'] == 0,
                      'N9 cell/bucket/timeout differs')
    cohort = [e for e in events if e.get('identity', {}).get('iteration') == COHORT]
    dispatched = [e for e in cohort if e.get('event') == 'dispatched']
    spent = sum(e.get('gpu_process_wall_seconds', 0.) for e in cohort
                if e.get('event') in runner['TERMINAL'])
    runner['require'](len(dispatched) < LIMITS['dispatches']
                      and spent + timeout + LIMITS['cleanup_seconds'] <= LIMITS['gpu_hours'] * 3600,
                      'N9 local dispatch/GPU-hour cap exceeded')
    runner['require'](state['budget']['gpu_hours_consumed']
                      + (timeout + LIMITS['cleanup_seconds']) / 3600
                      + state['budget']['gpu_hour_reservations']['formal']
                      <= state['budget']['max_gpu_hours'],
                      'N9 cannot borrow protected formal reserve')


def admission(plan, runtime, row, events, resources, root, runner):
    return {'n9_cohort_id': COHORT, 'n9_protocol_sha256': plan['n9_cohort']['protocol']['sha256']}


def build_plan(parent, root, head, runner):
    root = Path(root)
    runner.require(sha(PARENT) == PARENT_SHA and parent['source_commit'] != head,
                   'N9 immutable parent or prospective source differs')
    paths = {r['path'] for r in parent['code_files']} | ADDITIONS | runner.REQUIRED_CODE
    code_files = []
    for relative in sorted(paths):
        actual = (root / relative).read_bytes()
        committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=root)
        runner.require(actual == committed, 'N9 uncommitted source: ' + relative)
        code_files.append({'path': relative, 'sha256': hashlib.sha256(actual).hexdigest()})
    plan = copy.deepcopy(parent)
    plan.pop('n7_cohort', None)
    plan.update(frozen=True, worktree=str(root), source_commit=head,
                episodes=rows_from_parent(parent), code_files=code_files,
                candidate_profiles={arm: {'path': str(root / path), 'sha256': sha(root / path)}
                                    for arm, path in (('N7', N7_PROFILE), ('N9', N9_PROFILE))},
                phase_authorization={'dev': True, 'validation': False, 'formal': False},
                scientific_config_files=sorted(set(parent['scientific_config_files']) | {PROTOCOL, N9_PROFILE}),
                egl_mapping_verified=True)
    runtime = runner.read_json(plan['runtime_manifest_path'])
    plan['n9_cohort'] = {'schema': 'qd-ed-n9-contact-sweep-dev-v1',
                         'cohort_id': COHORT, 'limits': copy.deepcopy(LIMITS),
                         'protocol': {'path': PROTOCOL, 'sha256': sha(root / PROTOCOL)},
                         'parent_plan': {'path': str(PARENT), 'sha256': PARENT_SHA},
                         'stage_condition': copy.deepcopy(runtime['stage_engineering_condition'])}
    return plan


def main():
    import qd_ed_final_runner as runner
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-plan', type=Path, required=True)
    parser.add_argument('--source-head', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runner.require(args.parent_plan.resolve() == PARENT and not args.output.exists(),
                   'N9 parent/output identity differs')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    runner.require(head == args.source_head, 'N9 source HEAD differs')
    with runner.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
        plan = build_plan(runner.read_json(PARENT), ROOT, head, runner)
        output = runner.owned(args.output, plan['artifact_root'])
        output.parent.mkdir(parents=True, exist_ok=True)
        runner.durable_json(output, plan)
        runner.validate_plan(output, root=ROOT)
    print(json.dumps({'status': 'frozen_reviewable_no_execution_release',
                      'plan': str(output), 'sha256': sha(output), 'episodes': len(plan['episodes'])}))


if __name__ == '__main__':
    main()
