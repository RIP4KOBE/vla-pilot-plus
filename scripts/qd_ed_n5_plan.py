#!/usr/bin/env python3
"""N5's closed four-cell Dev identity, private budget and supervised launch gate."""
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
COHORT = 'N5_GRASP_TIMING_DEV_20260925'
TASKS = (0, 3, 6, 9)
FIELDS = ('env_seed', 'policy_seed', 'init_index', 'init_row_sha256', 'init_file_sha256', 'bddl_sha256')
PROTOCOL = 'experiments/iteration_005_grasp_timing/protocol.md'
CONTINUATION = 'experiments/iteration_005_grasp_timing/continuation-engineering-v1.md'
PROFILE = 'configs/qd_ed_final/candidate_n5.json'
PARENT_PROFILE = 'configs/qd_ed_final/candidate_n4.json'
PARENT_PLAN = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260924/n4-e1-dev-v1/plan.frozen.json')
PARENT_PLAN_SHA256 = 'c13e38a59f46b0a2ebe6175bb0a045991447dbc12c97ede800405c3339ea59e3'
PRIOR_REPORT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n4-e1-full12-report-v1/report.json')
PRIOR_REPORT_SHA256 = '19c53c7568c504ac67f3b170cc42b70b2ec10ce23496a1f2bf130cb0702ca558'
LIMITS = {'original_cells': 4, 'dispatches': 8, 'recoveries': 4, 'gpu_hours': 4.2,
          'episode_timeout_seconds': 1800, 'cleanup_seconds': 40, 'physical_gpu': 3}
CODE_ADDITIONS = {PROTOCOL, CONTINUATION, PROFILE, 'core/qd_grasp_timing.py',
                  'scripts/qd_ed_n5_plan.py', 'scripts/qd_ed_n5_supervise.py',
                  'scripts/qd_ed_n5_report.py',
                  'tests/test_qd_grasp_timing.py', 'tests/test_qd_ed_n5_plan.py'}
_SCOPE = None
AUDIT_PLUMBING = {'scripts/qd_ed_n5_plan.py', 'scripts/qd_ed_n5_supervise.py',
                  'scripts/qd_ed_n5_report.py', 'tests/test_qd_ed_n5_plan.py'}


def api(value):
    return SimpleNamespace(**value) if isinstance(value, dict) else value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provider_metric(metric):
    # The metrics writer omits this key for its default provider mode.
    return metric.get('qd_quality_mode', 'provider') == 'provider'


def rows_from_parent(parent):
    prior = {row['task_id']: row for row in parent['episodes']
             if row['profile'] == 'N4' and not row.get('retry_of')}
    if set(prior) != set(TASKS):
        raise ValueError('N5 parent lacks the four accepted Dev identities')
    rows = []
    for task in TASKS:
        row = copy.deepcopy(prior[task])
        row.update(iteration=COHORT, profile='N5',
                   episode_key=f'n5_dev_t{task:02d}_20260925', budget_bucket='development')
        rows.append(row)
    return rows


def binding(plan, runtime):
    cohort = plan['n5_cohort']
    return {'cohort_id': COHORT, 'protocol_sha256': cohort['protocol']['sha256'],
            'source_commit': plan['source_commit'],
            'profiles_sha256': plan['profiles_sha256'],
            'candidate_sha256': plan['candidate_profiles']['N5']['sha256'],
            'runtime_manifest_sha256': plan['runtime_manifest_sha256'],
            'runtime_inventory_sha256': plan['runtime_inventory_sha256'],
            'seed_plan_sha256': plan['seed_plan_sha256'],
            'stage_public_config_sha256': runtime['frozen_stage_provider']['public_config_sha256']}


def verify_prior_cell(plan, root, runner):
    """Bind task 0 to its original valid attempt and byte-identical science code."""
    r = api(runner)
    reference = plan['n5_cohort'].get('prior_accepted_cell')
    r.require(isinstance(reference, dict) and set(reference) == {'path', 'sha256'},
              'N5 continuation proof missing')
    proof_path = r.owned(reference['path'], plan['artifact_root'])
    r.require(r.digest(proof_path) == reference['sha256'], 'N5 continuation proof changed')
    proof = r.read_json(proof_path)
    r.require(proof.get('schema') == 'qd-ed-n5-prior-cell-proof-v1'
              and proof.get('episode_key') == rows_from_parent(r.read_json(PARENT_PLAN))[0]['episode_key']
              and proof.get('task_id') == 0, 'N5 prior cell identity differs')
    old_plan_path = r.owned(proof['plan']['path'], plan['artifact_root'])
    old_plan = r.read_json(old_plan_path)
    r.require(r.digest(old_plan_path) == proof['plan']['sha256']
              and old_plan['source_commit'] == proof['source_commit']
              and old_plan['episodes'] == plan['episodes']
              and old_plan['n5_cohort']['cohort_id'] == COHORT,
              'N5 prior plan identity differs')
    old_files = {item['path']: item['sha256'] for item in old_plan['code_files']}
    new_files = {item['path']: item['sha256'] for item in plan['code_files']}
    r.require(all(new_files.get(path) == sha256 for path, sha256 in old_files.items()
                  if path not in AUDIT_PLUMBING)
              and set(new_files) - set(old_files) <= {CONTINUATION},
              'N5 scientific source changed during audit continuation')
    result_path = r.owned(proof['result']['path'], plan['artifact_root'])
    result = r.read_json(result_path)
    audit_path = r.owned(proof['native_audit']['path'], plan['artifact_root'])
    native = r.read_json(audit_path)
    checkpoint_path = r.owned(proof['checkpoint']['path'], plan['artifact_root'])
    checkpoint = r.read_json(checkpoint_path)
    r.require(r.digest(result_path) == proof['result']['sha256']
              and r.digest(audit_path) == proof['native_audit']['sha256']
              and r.digest(checkpoint_path) == proof['checkpoint']['sha256']
              and result['event'] == 'valid' and result['outcome_valid'] is True
              and result['attempt_id'] == proof['attempt_id']
              and result['episode_key'] == proof['episode_key']
              and result['identity']['task_id'] == 0
              and result['source_commit'] == proof['source_commit']
              and result['plan_sha256'] == proof['plan']['sha256']
              and result['success'] is False
              and native['accepted'] is True and native['evidence_complete'] is True
              and native['n5_grasp_timing_audit']['checked_decisions'] == result['guided_chunks']
              and checkpoint['accepted'] is True
              and checkpoint['attempt_id'] == proof['attempt_id']
              and checkpoint['episode_key'] == proof['episode_key']
              and checkpoint['source_commit'] == proof['source_commit']
              and checkpoint['plan_sha256'] == proof['plan']['sha256']
              and checkpoint['success'] is False,
              'N5 prior valid result or evidence changed')
    events = r.read_events(Path(root) / 'data/attempt-ledger.jsonl')
    valid = [event for event in events if event.get('episode_key') == proof['episode_key']
             and event.get('event') == 'valid']
    r.require(len(valid) == 1 and valid[0]['attempt_id'] == proof['attempt_id'],
              'N5 prior cell ledger identity differs')
    return proof


def migrated_runtime(parent, root, runner):
    """Rebind only resolved paths changed by the user's worktree relocation."""
    r = api(runner); root = Path(root).resolve()
    prior = r.read_json(parent['runtime_manifest_path'])
    r.require(r.digest(parent['runtime_manifest_path']) == parent['runtime_manifest_sha256'],
              'N5 prior runtime bytes changed')
    updated = copy.deepcopy(prior)
    old_root = Path(parent['worktree'])
    count = 0
    for record in updated['files']:
        path = Path(record['path'])
        r.require(path.is_file() and path.stat().st_size == record['size_bytes']
                  and r.digest(path) == record['sha256'],
                  'N5 relocation changed frozen runtime file contents: ' + str(path))
        if 'resolved_path' not in record:
            continue
        actual = path.resolve()
        if record.get('resolved_path') == str(actual):
            continue
        r.require(path.is_relative_to(old_root)
                  and actual == (root / path.relative_to(old_root)).resolve(),
                  'N5 unexpected runtime path migration: ' + str(path))
        record['resolved_path'] = str(actual)
        count += 1
    r.require(count > 0, 'N5 expected archived worktree path rebinding missing')
    return updated, count


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    r = api(runner); root = Path(root)
    cohort = plan.get('n5_cohort')
    r.require(isinstance(cohort, dict) and cohort.get('schema') == 'qd-ed-n5-grasp-timing-dev-v1'
              and cohort.get('cohort_id') == COHORT and cohort.get('limits') == LIMITS,
              'N5 exact cohort/limits missing')
    r.require(plan.get('n4e1_cohort') is None and plan.get('n4_cohort') is None
              and set(plan.get('candidate_profiles', {})) == {'N5'},
              'N5 plan must contain only its candidate')
    r.require(cohort.get('protocol') == {'path': PROTOCOL, 'sha256': r.digest(root / PROTOCOL)},
              'N5 protocol identity differs')
    r.require(cohort.get('continuation_protocol') == {'path': CONTINUATION, 'sha256': r.digest(root / CONTINUATION)},
              'N5 continuation protocol identity differs')
    r.require(cohort.get('parent_plan') == {'path': str(PARENT_PLAN), 'sha256': PARENT_PLAN_SHA256}
              and sha(PARENT_PLAN) == PARENT_PLAN_SHA256,
              'N5 frozen matched parent plan differs')
    r.require(cohort.get('prior_report') == {'path': str(PRIOR_REPORT), 'sha256': PRIOR_REPORT_SHA256}
              and sha(PRIOR_REPORT) == PRIOR_REPORT_SHA256,
              'N5 prior complete comparator report differs')
    r.require(plan.get('phase_authorization') == {'dev': True, 'validation': False, 'formal': False}
              and plan.get('episodes') == rows_from_parent(r.read_json(PARENT_PLAN)),
              'N5 four original Dev cells/order/phase differ')
    r.require(Path(plan.get('profiles_path', '')).resolve() == (root / 'configs/qd_ed_final/n4_observed_baseline_profiles.json').resolve()
              and plan['profiles_sha256'] == r.digest(plan['profiles_path'])
              and set(manifest['profiles']) == {'C0', 'Q0', 'N5'},
              'N5 observed controls or profile manifest differ')
    candidate = r.read_json(root / PROFILE)
    r.require(plan['candidate_profiles']['N5'] == {'path': str(root / PROFILE), 'sha256': r.digest(root / PROFILE)}
              and candidate['parent_candidate'] == {'path': PARENT_PROFILE, 'sha256': r.digest(root / PARENT_PROFILE)},
              'N5 candidate or parent profile differs')
    r.require(manifest['profiles']['N5']['resolved_eds_config']['qd_final_selection_mode'] == 'terminal_grasp_proximity_v1'
              and manifest['profiles']['N5']['resolved_eds_config'].get('qd_quality_mode', 'provider') == 'provider',
              'N5 final consumer/provider mode differs')
    r.require(cohort.get('stage_condition') == r.n4e1_support().engineering_condition()
              and runtime.get('stage_engineering_condition') == cohort['stage_condition']
              and r.runtime_gpu(runtime) == 3,
              'N5 inherited 180s Codex/GPU3 condition differs')
    migrated, count = migrated_runtime(r.read_json(PARENT_PLAN), root, runner)
    r.require(runtime == migrated
              and cohort.get('runtime_parent') == {'path': r.read_json(PARENT_PLAN)['runtime_manifest_path'],
                                                   'sha256': r.read_json(PARENT_PLAN)['runtime_manifest_sha256']}
              and cohort.get('relocated_resolved_paths') == count,
              'N5 runtime changed beyond verified archive path rebinding')
    paths = {record['path'] for record in plan['code_files']}
    r.require(CODE_ADDITIONS <= paths and set(plan['scientific_config_files']) <= paths,
              'N5 source/protocol fingerprints missing')
    verify_prior_cell(plan, root, runner)
    state = r.read_state(root / 'research-state.yaml')
    r.require(state['resource_isolation']['status'] == 'ACTIVE'
              and state['resource_isolation']['validation_status'] == 'PASS'
              and state['resource_isolation']['private_budget'] is True
              and state['budget']['max_episode_attempts'] == 240
              and state['budget']['max_gpu_hours'] == 48.0
              and state['budget']['reserved'] == r.BUCKETS
              and r.authorized_gpu(state) == 3,
              'N5 independent GPU3 resource authority differs')


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('N5 nested supervisor scope')
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
              'N5 requires its one-cell audited supervisor')


def protected_budget(state, events, resources, row, timeout, runner, *, plan):
    r = api(runner)
    r.require(row['profile'] == 'N5' and row['iteration'] == COHORT
              and row['budget_bucket'] == 'development'
              and timeout == LIMITS['episode_timeout_seconds'],
              'N5 cell/timeout/bucket differs')
    r.require(state['budget']['reserved'] == r.BUCKETS and state['budget']['running'] == 0,
              'N5 private budget/reserves or running attempt changed')
    n5_events = [event for event in events if event.get('identity', {}).get('iteration') == COHORT]
    dispatched = [event for event in n5_events if event.get('event') == 'dispatched']
    settled = [event for event in n5_events if event.get('event') in r.TERMINAL]
    spent = sum(event.get('gpu_process_wall_seconds', 0.0) for event in settled)
    r.require(len(dispatched) < LIMITS['dispatches']
              and spent + timeout + LIMITS['cleanup_seconds'] <= LIMITS['gpu_hours'] * 3600,
              'N5 local dispatch/GPU-hour cap exceeded')
    r.require(state['budget']['gpu_hours_consumed'] + (timeout + LIMITS['cleanup_seconds']) / 3600
              + state['budget']['gpu_hour_reservations']['validation']
              + state['budget']['gpu_hour_reservations']['formal'] <= state['budget']['max_gpu_hours'],
              'N5 cannot borrow protected GPU-hour reserves')


def admission(plan, runtime, row, events, resources, root, runner):
    return {'n5_cohort_id': COHORT, 'n5_frozen_identity': binding(plan, runtime)}


def build_plan(parent, root, head, runtime_path, migrated_count, prior_proof_path, runner):
    r = api(runner); root = Path(root)
    r.require(sha(PARENT_PLAN) == PARENT_PLAN_SHA256 and parent['source_commit'] != head,
              'N5 parent plan/head identity invalid')
    runtime = r.read_json(runtime_path)
    paths = {record['path'] for record in parent['code_files']} | CODE_ADDITIONS | r.REQUIRED_CODE
    code_files = []
    for relative in sorted(paths):
        actual = (root / relative).read_bytes()
        committed = subprocess.check_output(['git', 'show', head + ':' + relative], cwd=root)
        r.require(actual == committed, 'N5 uncommitted source: ' + relative)
        code_files.append({'path': relative, 'sha256': hashlib.sha256(actual).hexdigest()})
    plan = copy.deepcopy(parent)
    for key in ('n4e1_cohort', 'n4_cohort', 'preflight_index', 'preflight_index_sha256',
                'frozen_at', 'preparation_provenance', 'resource_amendment'):
        plan.pop(key, None)
    plan.update(frozen=True, worktree=str(root), source_commit=head,
        episodes=rows_from_parent(parent), code_files=code_files,
        runtime_manifest_path=str(runtime_path), runtime_manifest_sha256=r.digest(runtime_path),
        candidate_profiles={'N5': {'path': str(root / PROFILE), 'sha256': r.digest(root / PROFILE)}},
        phase_authorization={'dev': True, 'validation': False, 'formal': False},
        scientific_config_files=sorted(set(parent['scientific_config_files']) | {PROTOCOL, CONTINUATION, PROFILE}),
        egl_mapping_verified=True)
    plan['n5_cohort'] = {
        'schema': 'qd-ed-n5-grasp-timing-dev-v1', 'cohort_id': COHORT,
        'limits': copy.deepcopy(LIMITS),
        'protocol': {'path': PROTOCOL, 'sha256': r.digest(root / PROTOCOL)},
        'continuation_protocol': {'path': CONTINUATION, 'sha256': r.digest(root / CONTINUATION)},
        'prior_accepted_cell': {'path': str(prior_proof_path), 'sha256': r.digest(prior_proof_path)},
        'parent_plan': {'path': str(PARENT_PLAN), 'sha256': PARENT_PLAN_SHA256},
        'prior_report': {'path': str(PRIOR_REPORT), 'sha256': PRIOR_REPORT_SHA256},
        'stage_condition': copy.deepcopy(runtime['stage_engineering_condition']),
        'runtime_parent': {'path': parent['runtime_manifest_path'],
                           'sha256': parent['runtime_manifest_sha256']},
        'relocated_resolved_paths': migrated_count}
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-plan', type=Path, required=True)
    parser.add_argument('--source-head', required=True)
    parser.add_argument('--runtime-output', type=Path, required=True)
    parser.add_argument('--prior-cell-proof', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import qd_ed_final_runner as r
    r.require(args.parent_plan.resolve() == PARENT_PLAN and not args.output.exists()
              and not args.runtime_output.exists(),
              'N5 frozen parent or output path differs')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    r.require(head == args.source_head, 'N5 source HEAD differs')
    with r.locked(ROOT / 'data/qd-ed-runner.lock', nonblocking=True):
        parent = r.read_json(PARENT_PLAN)
        runtime, migrated_count = migrated_runtime(parent, ROOT, r.__dict__)
        runtime_output = r.owned(args.runtime_output, parent['artifact_root'])
        runtime_output.parent.mkdir(parents=True, exist_ok=True)
        r.durable_json(runtime_output, runtime)
        prior_proof_path = r.owned(args.prior_cell_proof, parent['artifact_root'])
        plan = build_plan(parent, ROOT, head, runtime_output, migrated_count, prior_proof_path, r.__dict__)
        output = r.owned(args.output, plan['artifact_root'])
        output.parent.mkdir(parents=True, exist_ok=True)
        r.durable_json(output, plan)
        try:
            r.validate_plan(output, root=ROOT)
        except BaseException:
            # Preserve the failed draft for diagnosis; it never receives a launch release.
            raise
    print(json.dumps({'status': 'frozen_reviewable_no_execution_release',
                      'plan': str(output), 'sha256': sha(output), 'episodes': [x['episode_key'] for x in plan['episodes']]}))


if __name__ == '__main__':
    main()
