#!/usr/bin/env python3
"""GPU3-only prospective E2 passive N7 Dev replay; exact release required."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import threading
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT.parent if ROOT.name == 'study_worktree' else ROOT.parents[2]
ART = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
RUN_DIR = ART / 'continuation_20260928/n7-e2-passive-tracker-diagnostic-v1'
SOURCE_PLAN = ART / 'continuation_20260925/n7-dev-v1/plan.frozen.v1.json'
SOURCE_PLAN_SHA = '9cef973dd2a2f7cd07f82eb1965b96e2bcb3557f372e25dc4cd04dc622b277be'
PROTOCOL = SESSION / 'variants/n10_lineage_survival/e2-prospective-measurement-protocol-v1.md'
COHORT = 'N7_E2_PASSIVE_TRACKING_DEV_20260928'
TASKS = (0, 3, 6, 9)
LIMITS = {'primary_dispatches': 4, 'gpu_hours': 4.2,
          'episode_timeout_seconds': 1800, 'cleanup_seconds': 40, 'physical_gpu': 3}
_SCOPE = None


def api(r):
    return SimpleNamespace(**r) if isinstance(r, dict) else r


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_rows():
    if sha(SOURCE_PLAN) != SOURCE_PLAN_SHA:
        raise ValueError('historical N7 frozen plan changed')
    historical = json.loads(SOURCE_PLAN.read_text())
    original = {r['task_id']: r for r in historical['episodes']}
    if set(original) != set(TASKS):
        raise ValueError('historical N7 four-cell identity changed')
    rows = []
    for task in TASKS:
        row = copy.deepcopy(original[task])
        row.update(iteration=COHORT, episode_key=f'n7_e2_passive_t{task:02d}_20260928',
                   budget_bucket='development')
        rows.append(row)
    return rows


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    r = api(runner)
    meta = plan.get('n7_e2_passive_diagnostic')
    r.require(isinstance(meta, dict) and meta.get('schema') == 'n7-e2-passive-diagnostic-v1'
              and meta.get('cohort_id') == COHORT and meta.get('limits') == LIMITS
              and meta.get('source_plan_sha256') == SOURCE_PLAN_SHA
              and meta.get('run_dir') == str(RUN_DIR)
              and meta.get('protocol_path') == str(PROTOCOL)
              and meta.get('protocol_sha256') == sha(PROTOCOL),
              'passive diagnostic metadata/protocol differs')
    r.require(plan.get('n7_cohort') is None and plan.get('n7_passive_diagnostic') is None
              and plan.get('n7_validation') is None
              and plan.get('n7_validation_continuation') is None
              and plan.get('n9_cohort') is None
              and plan.get('stage_condition') == r.E2_STAGE_CONDITION
              and set(plan.get('candidate_profiles', {})) == {'N7'}
              and plan.get('phase_authorization') == {'dev': True, 'validation': False, 'formal': False}
              and plan.get('episodes') == expected_rows(),
              'passive diagnostic must contain only four original N7 Dev identities')
    r.require(plan['candidate_profiles']['N7']['sha256'] ==
              'd77b8472364cd00dc2548e9e8160672a4f16335a56736cf66d77de6ae74ccb2d'
              and manifest['profiles']['N7']['resolved_eds_config']['qd_descriptor']
              == 'target_xy_quadrant_signed_height_v1'
              and manifest['profiles']['N7']['resolved_eds_config']['qd_final_selection_mode']
              == 'terminal_grasp_proximity_v1',
              'N7 scientific profile changed')
    r.require(r.runtime_gpu(runtime) == 3 and
              runtime.get('stage_engineering_condition') ==
              r.n4e1_support().engineering_condition() and
              runtime.get('stage_recovered_error_condition') == r.E2_STAGE_CONDITION and
              runtime.get('stage_condition') == r.E2_STAGE_CONDITION and
              runtime['frozen_stage_provider'].get('allow_recovered_error_events') is True,
              'GPU3/E2 Stage transport identity changed')
    state = r.read_state(Path(root) / 'research-state.yaml')
    r.require(state['resource_isolation']['status'] == 'ACTIVE'
              and state['resource_isolation']['validation_status'] == 'PASS'
              and state['resource_isolation']['private_budget'] is True
              and state['budget']['max_episode_attempts'] == 393
              and state['budget']['max_gpu_hours'] == 100.0
              and state['budget']['reserved'] == r.AMENDED_BUCKETS
              and state['budget'].get('amendment') == r.GPU3_AMENDMENT
              and r.authorized_gpu(state) == 3,
              'owning GPU3 private budget/authority changed')
    required = {'main.py', 'core/keypoint_tracker.py', 'core/decision_evidence.py',
                'core/codex_stage.py', 'configs/perception.yaml',
                'scripts/qd_ed_final_runner.py', 'scripts/qd_ed_n7_e2_passive_diagnostic.py',
                'tests/test_keypoint_tracking_evidence.py'}
    r.require(required <= {item['path'] for item in plan['code_files']},
              'passive source fingerprints absent')


@contextmanager
def supervised_scope(plan, root, episode_key):
    global _SCOPE
    if _SCOPE is not None:
        raise RuntimeError('nested passive supervisor scope')
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
              'passive diagnostic requires its audited one-cell supervisor')


def protected_budget(state, events, resources, row, timeout, runner, *, plan):
    r = api(runner)
    r.require(row['profile'] == 'N7' and row['iteration'] == COHORT
              and row['budget_bucket'] == 'development'
              and timeout == LIMITS['episode_timeout_seconds']
              and state['budget']['running'] == 0,
              'passive diagnostic row/budget scope changed')
    local = [e for e in events if e.get('identity', {}).get('iteration') == COHORT]
    dispatched = [e for e in local if e.get('event') == 'dispatched']
    spent = sum(e.get('gpu_process_wall_seconds', 0.0)
                for e in local if e.get('event') in r.TERMINAL)
    r.require(len(dispatched) < LIMITS['primary_dispatches']
              and spent + timeout + LIMITS['cleanup_seconds'] <= LIMITS['gpu_hours'] * 3600,
              'passive diagnostic local dispatch/GPU-hour cap exhausted')
    reserved = state['budget']['gpu_hour_reservations']
    snapshot = r.budget_snapshot(events, resources)
    protected = sum(max(0.0, hours - snapshot['gpu_hours_by_bucket'].get(name, 0.0))
                    for name, hours in reserved.items() if name != 'development')
    # The generic runner's journal-based check_budget is the authoritative
    # admission.  This local check must never relax its protected reserves.
    r.require(state['budget']['gpu_hours_consumed'] +
              (timeout + LIMITS['cleanup_seconds']) / 3600 + protected
              <= state['budget']['max_gpu_hours'] + 1e-9,
              'passive diagnostic would borrow protected GPU hours')


def admission(plan, runtime, row, events, resources, root, runner):
    return {'n7_e2_passive_diagnostic_cohort': COHORT,
            'n7_e2_passive_protocol_sha256': plan['n7_e2_passive_diagnostic']['protocol_sha256']}


def audit_tracking(output):
    import torch
    folder = Path(output) / 'eds_eval/decision_evidence/episode_000'
    contexts = []
    for line in (folder / 'events.jsonl').open():
        summary = json.loads(line)
        if not any(e['event'] == 'decision_context' for e in summary['events']):
            continue
        bundle = folder / summary['bundle']
        if sha(bundle) != summary['sha256']:
            raise ValueError('passive decision-context bundle hash mismatch')
        events = torch.load(bundle, map_location='cpu', weights_only=True)['events']
        selected = [e for e in events if e['event'] == 'decision_context']
        if len(selected) != 1:
            raise ValueError('passive decision-context count mismatch')
        event = selected[0]
        values = event['values']
        snap = values.get('keypoint_tracking_snapshot')
        if values.get('keypoints') is not None:
            if not isinstance(snap, dict) or 'capture_error_type' in snap:
                raise ValueError('passive snapshot missing or capture failed')
            if '0' not in snap.get('targets', {}):
                raise ValueError('passive target 0 status missing')
        contexts.append({'global_step': event['global_step'],
                         'guided': bool(values['use_guidance']),
                         'instance_id': None if snap is None else snap.get('instance_id'),
                         'generation': None if snap is None else snap.get('generation'),
                         'target0': None if snap is None else snap.get('targets', {}).get('0')})
    if not contexts:
        raise ValueError('passive decision contexts absent')
    guided = [x for x in contexts if x['guided']]
    if not guided:
        raise ValueError('passive guided decisions absent')
    return {'schema': 'n7-e2-passive-tracking-audit-v1',
            'decision_contexts': len(contexts), 'guided_decisions': len(guided),
            'target0_tracked_guided': sum(x['target0'] == {'valid': True, 'status': 'tracked'} for x in guided),
            'guided_tracker_identities': sorted({(x['instance_id'], x['generation']) for x in guided}),
            'contexts': contexts}


def release_check(path, plan_path, plan):
    import qd_ed_final_runner as runner
    release = runner.read_json(path)
    runner.require(release == {
        'schema': 'n7-e2-passive-diagnostic-execution-release-v1',
        'plan_path': str(Path(plan_path).resolve()),
        'plan_sha256': runner.digest(plan_path),
        'source_commit': plan['source_commit'],
        'cohort_id': COHORT,
        'episode_keys': [r['episode_key'] for r in plan['episodes']],
        'physical_gpu': 3,
        'validation_authorized': False,
        'formal_authorized': False,
    }, 'passive diagnostic release differs')


def main():
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    import audit_decision_evidence as audit
    import qd_ed_final_runner as runner
    import qd_ed_available_gpu_queue as queue
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    args = parser.parse_args()
    plan, _, _ = runner.validate_plan(args.plan, root=ROOT)
    release_check(args.release, args.plan, plan)
    status = runner.owned(args.status, plan['artifact_root'])
    runner.require(not status.exists(), 'passive supervisor status already exists')
    completed = []
    runner.durable_json(status, {'status': 'started', 'completed_keys': completed, 'physical_gpu': 3})
    try:
        for row in plan['episodes']:
            devices = queue.inventory()
            runner.require(3 in devices, 'GPU3 missing')
            queue.reservation_admission(devices[3])
            runner.gpu_admission(physical_gpu=3, expected_uuid=devices[3]['uuid'])
            # The command file is __main__, while the runner loads this same
            # file as its contract module.  Scope must live in that instance.
            with runner.n7_e2_passive_support().supervised_scope(plan, ROOT,
                                                               row['episode_key']):
                summaries = runner.run_plan(args.plan, split='dev', iteration=COHORT,
                                            episode_keys=[row['episode_key']], root=ROOT)
            runner.require(len(summaries) == 1, 'passive diagnostic cell result missing')
            result = summaries[0]
            output = Path(result['output_dir'])
            links = RUN_DIR / 'attempts'
            links.mkdir(parents=True, exist_ok=True)
            link = links / result['attempt_id']
            runner.require(not link.exists(), 'passive diagnostic attempt index collision')
            link.symlink_to(output, target_is_directory=True)
            runner.require(result['event'] == 'valid' and result['outcome_valid'] is True,
                           'passive diagnostic cell failed; no automatic retry')
            native = audit.audit_episode(output / 'eds_eval/decision_evidence/episode_000',
                                         output / 'eds_eval/episode_compute.jsonl')
            runner.durable_json(output / 'eds_eval/decision-evidence-audit.json', native)
            runner.require(native.get('accepted') is True and native.get('evidence_complete') is True,
                           'passive diagnostic native audit rejected episode')
            tracking = audit_tracking(output)
            runner.durable_json(output / 'eds_eval/passive-tracking-audit.json', tracking)
            runner.durable_json(status, {'status': 'cell_audited',
                'completed_keys': completed + [row['episode_key']],
                'last_attempt': result['attempt_id'], 'physical_gpu': 3})
            completed.append(row['episode_key'])
        runner.durable_json(status, {'status': 'completed_all_four_audited',
            'completed_keys': completed, 'physical_gpu': 3})
    except BaseException as exc:
        runner.durable_json(status, {'status': 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed',
            'completed_keys': completed, 'reason': type(exc).__name__, 'physical_gpu': 3})
        raise


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
