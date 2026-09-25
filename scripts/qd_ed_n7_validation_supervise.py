#!/usr/bin/env python3
"""Run N7/C0/Q0 C1 validation sequentially on GPU3 with per-cell audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import time

import audit_decision_evidence as audit
import qd_ed_available_gpu_queue as queue
import qd_ed_final_runner as runner
import qd_ed_n7_validation_plan as contract


ROOT = Path(__file__).resolve().parents[1]


def release_check(path, plan_path, plan, keys):
    release = runner.read_json(path)
    runner.require(release == {
        'schema': 'qd-ed-n7-validation-c1-execution-release-v1',
        'plan_path': str(plan_path.resolve()),
        'plan_sha256': runner.digest(plan_path),
        'source_commit': plan['source_commit'],
        'cohort_id': contract.COHORT,
        'episode_keys': keys,
        'physical_gpu': 3,
        'formal_authorized': False,
    }, 'N7 validation exact execution release differs')


def wait_gpu3(status, completed):
    while True:
        state = runner.read_state(ROOT / 'research-state.yaml')
        runner.require(state['resource_isolation']['status'] == 'ACTIVE'
                       and runner.authorized_gpu(state) == 3,
                       'N7 validation GPU3/resource authority changed')
        devices = queue.inventory()
        runner.require(3 in devices, 'GPU3 disappeared')
        try:
            queue.reservation_admission(devices[3])
            runner.gpu_admission(physical_gpu=3, expected_uuid=devices[3]['uuid'])
            return
        except runner.GateError as exc:
            if not queue.is_admission_race(exc):
                raise
            runner.durable_json(status, {'status': 'waiting_gpu3', 'completed_count': len(completed),
                'last_resource_reason': str(exc), 'selected_physical_gpu': 3})
            time.sleep(30)


def audit_result(summary, row, status, completed):
    output = Path(summary['output_dir'])
    report = audit.audit_episode(output / 'eds_eval/decision_evidence/episode_000',
                                 output / 'eds_eval/episode_compute.jsonl')
    runner.durable_json(output / 'eds_eval/decision-evidence-audit.json', report)
    runner.require(report.get('accepted') is True and report.get('evidence_complete') is True,
                   'N7 validation native evidence audit rejected completed episode')
    metrics = runner.read_events(output / 'eds_eval/eds_metrics.jsonl')
    runner.require(len(metrics) == summary.get('guided_chunks'),
                   'N7 validation guided metric count differs')
    native = report.get('n7_direction_height_audit')
    if row['profile'] == 'N7':
        runner.require((len(metrics) == 0 and native is None)
                       or (isinstance(native, dict)
                           and native.get('schema') == 'n7-native-direction-height-descriptor-audit-v1'
                           and native.get('checked_decisions') == len(metrics)
                           and native.get('assignments_verified') == len(metrics) * 11
                           and native.get('candidates_verified') == len(metrics) * 176),
                       'N7 validation direction-height audit/metric count differs')
    for metric in metrics:
        if row['profile'] in {'N7', 'Q0'}:
            runner.require(metric.get('score_call_count') == 11
                           and metric.get('search_evaluation_count') == 176,
                           'N7/Q0 validation 176/11 search accounting differs')
        if row['profile'] == 'N7':
            runner.require(metric.get('qd_descriptor') == 'target_xy_quadrant_signed_height_v1'
                           and metric.get('qd_final_selection_mode') == 'terminal_grasp_proximity_v1'
                           and runner.n5_support().provider_metric(metric),
                           'N7 validation descriptor/provider/selector differs')
        if row['profile'] == 'C0':
            runner.require(metric.get('qd_archive_enabled') is False,
                           'C0 validation P2 control unexpectedly uses QD archive')
    checkpoint = {'schema': 'qd-ed-n7-validation-cell-audit-v1',
        'episode_key': row['episode_key'], 'attempt_id': summary['attempt_id'],
        'accepted': True, 'profile': row['profile'], 'task_id': row['task_id'],
        'seed_block': row['seed_block'], 'env_seed': row['env_seed'],
        'init_row_sha256': row['init_row_sha256'], 'success': summary['success'],
        'guided_chunks': len(metrics),
        'n7_native_assignments': native['assignments_verified'] if isinstance(native, dict) else None,
        'source_commit': summary['source_commit'], 'plan_sha256': summary['plan_sha256']}
    path = output / 'eds_eval/n7-validation-cell-audit.json'
    runner.durable_json(path, checkpoint)
    runner.durable_json(status, {'status': 'cell_audited',
        'completed_count': len(completed) + 1, 'latest_checkpoint': str(path),
        'selected_physical_gpu': 3})
    return checkpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    args = parser.parse_args()
    runner.require(Path(runner.read_state(ROOT / 'research-state.yaml')['worktree']).resolve() == ROOT,
                   'N7 validation supervisor must run from owning study worktree')
    plan, _, _ = runner.validate_plan(args.plan, root=ROOT)
    keys = [row['episode_key'] for row in plan['episodes']]
    runner.require(len(keys) == 60, 'N7 validation must have 60 matched originals')
    release_check(args.release, args.plan, plan, keys)
    status = runner.owned(args.status, plan['artifact_root'])
    runner.require(not status.exists(), 'N7 validation status already exists; do not duplicate supervisor')
    completed = []
    runner.durable_json(status, {'status': 'started', 'completed_count': 0,
                                'selected_physical_gpu': 3})
    try:
        for row in plan['episodes']:
            wait_gpu3(status, completed)
            runner.durable_json(status, {'status': 'dispatching',
                'completed_count': len(completed), 'current_key': row['episode_key'],
                'selected_physical_gpu': 3})
            with contract.supervised_scope(plan, ROOT, row['episode_key']):
                summaries = runner.run_plan(args.plan, split='validation',
                    iteration=contract.COHORT, episode_keys=[row['episode_key']], root=ROOT)
            runner.require(len(summaries) == 1 and summaries[0]['event'] == 'valid'
                           and summaries[0]['outcome_valid'] is True,
                           'N7 validation cell failed; preserve terminal and stop')
            audit_result(summaries[0], row, status, completed)
            completed.append(row['episode_key'])
        runner.durable_json(status, {'status': 'completed_all_sixty_audited',
            'completed_count': 60, 'selected_physical_gpu': 3})
    except BaseException as exc:
        runner.durable_json(status, {'status': 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed',
            'completed_count': len(completed),
            'reason': str(exc) if isinstance(exc, runner.GateError) else type(exc).__name__,
            'selected_physical_gpu': 3})
        raise


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
