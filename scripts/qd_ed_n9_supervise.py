#!/usr/bin/env python3
"""Execute 16 N9 Dev originals sequentially, auditing each before the next."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import time

import audit_decision_evidence as audit
import qd_ed_available_gpu_queue as queue
import qd_ed_final_runner as runner
import qd_ed_n9_plan as contract

ROOT = Path(__file__).resolve().parents[1]


def release_check(path, plan_path, plan):
    release = runner.read_json(path)
    runner.require(release == {
        'schema': 'qd-ed-n9-dev-execution-release-v1',
        'plan_path': str(plan_path.resolve()),
        'plan_sha256': runner.digest(plan_path),
        'source_commit': plan['source_commit'],
        'cohort_id': contract.COHORT,
        'episode_keys': [r['episode_key'] for r in plan['episodes']],
        'physical_gpu': 3, 'validation_authorized': False, 'formal_authorized': False,
    }, 'N9 exact execution release differs')


def wait_gpu3(status, completed):
    while True:
        state = runner.read_state(ROOT / 'research-state.yaml')
        runner.require(state['resource_isolation']['status'] == 'ACTIVE'
                       and runner.authorized_gpu(state) == 3,
                       'N9 GPU3/resource authority changed')
        devices = queue.inventory()
        runner.require(3 in devices, 'GPU3 disappeared')
        try:
            queue.reservation_admission(devices[3])
            runner.gpu_admission(physical_gpu=3, expected_uuid=devices[3]['uuid'])
            return
        except runner.GateError as exc:
            if not queue.is_admission_race(exc):
                raise
            runner.durable_json(status, {'status': 'waiting_gpu3',
                'completed_count': len(completed), 'last_resource_reason': str(exc),
                'selected_physical_gpu': 3})
            time.sleep(30)


def audit_result(summary, row, plan_sha):
    output = Path(summary['output_dir'])
    report = audit.audit_episode(output / 'eds_eval/decision_evidence/episode_000',
                                 output / 'eds_eval/episode_compute.jsonl')
    runner.durable_json(output / 'eds_eval/decision-evidence-audit.json', report)
    runner.require(report.get('accepted') is True and report.get('evidence_complete') is True,
                   'N9 native evidence audit rejected completed episode')
    metrics = runner.read_events(output / 'eds_eval/eds_metrics.jsonl')
    runner.require(len(metrics) == summary.get('guided_chunks'),
                   'N9 guided metric count differs')
    n9 = report.get('n9_contact_sweep_audit')
    n7 = report.get('n7_direction_height_audit')
    if row['profile'] in {'N7', 'N9'} and metrics:
        runner.require(isinstance(n7, dict)
                       and n7.get('checked_decisions') == len(metrics)
                       and n7.get('assignments_verified') == len(metrics) * 11
                       and n7.get('candidates_verified') == len(metrics) * 176,
                       'N9/N7 native descriptor lineage incomplete')
    if row['profile'] == 'N9' and metrics:
        runner.require(isinstance(n9, dict) and n9.get('schema') == 'n9-native-contact-sweep-audit-v1'
                       and n9.get('checked_decisions') == len(metrics)
                       and n9.get('canonical_batches_verified') == len(metrics) * 11
                       and n9.get('canonical_candidates_verified') == len(metrics) * 176
                       and n9.get('parent_rounds_verified') == len(metrics) * 10
                       and [m['global_step'] for m in metrics]
                           == [d['global_step'] for d in n9['decisions']],
                       'N9 native selection lineage incomplete')
    for metric in metrics:
        if row['profile'] in {'Q0', 'N7', 'N9'}:
            runner.require(metric.get('score_call_count') == 11
                           and metric.get('search_evaluation_count') == 176,
                           'N9 matched QD/ED search accounting differs')
        if row['profile'] in {'N7', 'N9'}:
            runner.require(metric.get('qd_descriptor') == 'target_xy_quadrant_signed_height_v1'
                           and metric.get('qd_final_selection_mode') ==
                               ('terminal_contact_sweep_v1' if row['profile'] == 'N9' else 'terminal_grasp_proximity_v1')
                           and runner.n5_support().provider_metric(metric),
                           'N9/N7 descriptor/provider/selector differs')
        if row['profile'] == 'C0':
            runner.require(metric.get('qd_archive_enabled') is False,
                           'N9 C0 control unexpectedly uses archive')
    changed = []
    if row['profile'] == 'N9' and isinstance(n9, dict):
        for metric, decision in zip(metrics, n9['decisions']):
            detail = decision['n9_contact_sweep_selection']
            recorded = metric['qd_terminal_population']['contact_sweep_selection']
            runner.require(all(recorded.get(key) == detail.get(key) for key in
                               ('baseline_grasp_index', 'selected_index', 'target_index', 'changed'))
                           and metric['qd_terminal_population']['selected_index'] == detail['selected_index'],
                           'N9 metric/native selection differs')
            if detail['changed']:
                changed.append({'global_step': decision['global_step'],
                                'sweep_reduction_m': detail['baseline_sweep_m'] - detail['selected_sweep_m'],
                                'reach_loss_m': detail['reach_loss_m']})
    checkpoint = {'schema': 'qd-ed-n9-dev-cell-audit-v1',
                  'episode_key': row['episode_key'], 'attempt_id': summary['attempt_id'],
                  'accepted': True, 'profile': row['profile'], 'task_id': row['task_id'],
                  'env_seed': row['env_seed'], 'init_row_sha256': row['init_row_sha256'],
                  'success': summary['success'], 'guided_chunks': len(metrics),
                  'changed_decisions': changed, 'source_commit': summary['source_commit'],
                  'plan_sha256': plan_sha}
    runner.durable_json(output / 'eds_eval/n9-cell-audit.json', checkpoint)
    return checkpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    args = parser.parse_args()
    runner.require(Path(runner.read_state(ROOT / 'research-state.yaml')['worktree']).resolve() == ROOT,
                   'N9 supervisor must run from owning study worktree')
    plan, _, _ = runner.validate_plan(args.plan, root=ROOT)
    release_check(args.release, args.plan, plan)
    status = runner.owned(args.status, plan['artifact_root'])
    runner.require(not status.exists(), 'N9 status already exists; duplicate supervisor prohibited')
    completed = []
    runner.durable_json(status, {'status': 'started', 'completed_keys': completed,
                                'selected_physical_gpu': 3})
    try:
        for row in plan['episodes']:
            wait_gpu3(status, completed)
            runner.durable_json(status, {'status': 'dispatching', 'completed_keys': completed,
                                        'current_key': row['episode_key'], 'selected_physical_gpu': 3})
            with runner.n9_support().supervised_scope(plan, ROOT, row['episode_key']):
                summaries = runner.run_plan(args.plan, split='dev', iteration=contract.COHORT,
                                            episode_keys=[row['episode_key']], root=ROOT)
            runner.require(len(summaries) == 1 and summaries[0]['event'] == 'valid'
                           and summaries[0]['outcome_valid'] is True,
                           'N9 cell invalid; preserve terminal and stop')
            checkpoint = audit_result(summaries[0], row, runner.digest(args.plan))
            completed.append(row['episode_key'])
            runner.durable_json(status, {'status': 'cell_audited', 'completed_keys': completed,
                                        'latest_checkpoint': str(Path(summaries[0]['output_dir']) /
                                                                 'eds_eval/n9-cell-audit.json'),
                                        'latest_success': checkpoint['success'],
                                        'selected_physical_gpu': 3})
        runner.durable_json(status, {'status': 'completed_all_sixteen_audited',
                                    'completed_keys': completed, 'selected_physical_gpu': 3})
    except BaseException as exc:
        runner.durable_json(status, {'status': 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed',
                                    'completed_keys': completed,
                                    'reason': str(exc) if isinstance(exc, runner.GateError) else type(exc).__name__,
                                    'selected_physical_gpu': 3})
        raise


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
