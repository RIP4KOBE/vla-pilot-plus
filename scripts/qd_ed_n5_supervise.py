#!/usr/bin/env python3
"""GPU3-only N5 Dev supervisor: one episode, full native audit, then next cell."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import time

import audit_decision_evidence as audit
import qd_ed_available_gpu_queue as queue
import qd_ed_final_runner as runner


ROOT = Path(__file__).resolve().parents[1]


def release_check(path, plan_path, plan, keys):
    release = runner.read_json(path)
    runner.require(release == {
        'schema': 'qd-ed-n5-dev-continuation-release-v1',
        'plan_path': str(plan_path.resolve()),
        'plan_sha256': runner.digest(plan_path),
        'source_commit': plan['source_commit'],
        'cohort_id': runner.n5_support().COHORT,
        'episode_keys': keys,
        'prior_accepted_cell': plan['n5_cohort']['prior_accepted_cell'],
        'physical_gpu': 3,
        'validation_authorized': False,
        'formal_authorized': False,
    }, 'N5 exact execution release differs')
    return release


def wait_gpu3(status, completed):
    while True:
        state = runner.read_state(ROOT / 'research-state.yaml')
        runner.require(state['resource_isolation']['status'] == 'ACTIVE'
                       and runner.authorized_gpu(state) == 3,
                       'N5 GPU3/resource authority changed')
        devices = queue.inventory()
        runner.require(3 in devices, 'GPU3 disappeared')
        try:
            queue.reservation_admission(devices[3])
            runner.gpu_admission(physical_gpu=3, expected_uuid=devices[3]['uuid'])
            return
        except runner.GateError as exc:
            if not queue.is_admission_race(exc):
                raise
            runner.durable_json(status, {'status': 'waiting_gpu3', 'completed_keys': completed,
                'last_resource_reason': str(exc), 'selected_physical_gpu': 3})
            time.sleep(30)


def audit_result(summary, row, status, completed, *, precomputed_report_path=None,
                 reconciliation=None):
    output = Path(summary['output_dir'])
    evidence = output / 'eds_eval/decision_evidence/episode_000'
    compute = output / 'eds_eval/episode_compute.jsonl'
    if precomputed_report_path is None:
        report = audit.audit_episode(evidence, compute)
        runner.durable_json(output / 'eds_eval/decision-evidence-audit.json', report)
    else:
        runner.require(Path(precomputed_report_path).resolve() ==
                       (output / 'eds_eval/decision-evidence-audit-reconciled-v1.json').resolve()
                       and isinstance(reconciliation, dict),
                       'N5 reconciliation must use its separately recorded native audit')
        report = runner.read_json(precomputed_report_path)
    runner.require(report.get('accepted') is True and report.get('evidence_complete') is True,
                   'N5 native evidence audit rejected completed episode')
    gate = report.get('n5_grasp_timing_audit')
    metrics = runner.read_events(output / 'eds_eval/eds_metrics.jsonl')
    runner.require(isinstance(gate, dict) and gate.get('schema') == 'n5-native-grasp-timing-audit-v1'
                   and len(metrics) == summary.get('guided_chunks') == gate.get('checked_decisions')
                   and gate.get('canonical_batches_verified') == len(metrics) * 11
                   and gate.get('canonical_candidates_verified') == len(metrics) * 176
                   and gate.get('parent_rounds_verified') == len(metrics) * 10,
                   'N5 native audit/metric count differs')
    decisions = gate['decisions']
    runner.require([metric.get('global_step') for metric in metrics]
                   == [decision['global_step'] for decision in decisions],
                   'N5 audit/metric decision order differs')
    changed_prefix = 0
    for metric, decision in zip(metrics, decisions):
        terminal = metric.get('qd_terminal_population')
        grasp = terminal.get('grasp_selection') if isinstance(terminal, dict) else None
        verified = decision.get('n5_grasp_selection')
        runner.require(metric.get('qd_final_selection_mode') == 'terminal_grasp_proximity_v1'
                       and runner.n5_support().provider_metric(metric)
                       and metric.get('score_call_count') == 11
                       and metric.get('search_evaluation_count') == 176
                       and isinstance(grasp, dict) and isinstance(verified, dict)
                       and all(grasp.get(key) == verified.get(key) for key in
                               ('target_index', 'recognition_reason', 'eligible_indices', 'native_argmin_index'))
                       and terminal.get('selected_index') == verified.get('selected_index')
                       and terminal.get('selected_fingerprint') == decision['selected_fingerprint']
                       and terminal.get('selected_cost') == decision['selected_cost']
                       and terminal.get('selected_raw_reward') == decision['selected_raw_reward'],
                       'N5 native metric/decision association differs')
        changed_prefix += bool(decision['n5_native_argmin_actual_prefix_diff_positions'])
    checkpoint = {'schema': 'qd-ed-n5-dev-cell-audit-v1', 'episode_key': row['episode_key'],
        'attempt_id': summary['attempt_id'], 'accepted': True,
        'task_id': row['task_id'], 'success': summary['success'],
        'guided_chunks': len(metrics), 'native_argmin_actual_prefix_different_decisions': changed_prefix,
        'n5_native_audit_schema': gate['schema'],
        'source_commit': summary['source_commit'], 'plan_sha256': summary['plan_sha256']}
    if reconciliation is not None:
        checkpoint['offline_audit_reconciliation'] = reconciliation
    runner.durable_json(output / 'eds_eval/n5-cell-audit.json', checkpoint)
    runner.durable_json(status, {'status': 'cell_audited', 'completed_keys': completed + [row['episode_key']],
                                'latest_checkpoint': str(output / 'eds_eval/n5-cell-audit.json'),
                                'selected_physical_gpu': 3})
    return checkpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    args = parser.parse_args()
    runner.require(Path(runner.read_state(ROOT / 'research-state.yaml')['worktree']).resolve() == ROOT,
                   'N5 supervisor must run from owning study worktree')
    plan, _, runtime = runner.validate_plan(args.plan, root=ROOT)
    proof = runner.n5_support().verify_prior_cell(plan, ROOT, runner.__dict__)
    first_key = plan['episodes'][0]['episode_key']
    runner.require(proof['episode_key'] == first_key, 'N5 continuation does not start after task 0')
    keys = [row['episode_key'] for row in plan['episodes'][1:]]
    release_check(args.release, args.plan, plan, keys)
    status = runner.owned(args.status, plan['artifact_root'])
    runner.require(not status.exists(), 'N5 status already exists; do not duplicate supervisor')
    completed = [first_key]
    runner.durable_json(status, {'status': 'started', 'completed_keys': completed,
                                'selected_physical_gpu': 3})
    try:
        for row in plan['episodes'][1:]:
            wait_gpu3(status, completed)
            runner.durable_json(status, {'status': 'dispatching', 'completed_keys': completed,
                                        'current_key': row['episode_key'], 'selected_physical_gpu': 3})
            with runner.n5_support().supervised_scope(plan, ROOT, row['episode_key']):
                summaries = runner.run_plan(args.plan, split='dev', iteration=plan['n5_cohort']['cohort_id'],
                    episode_keys=[row['episode_key']], root=ROOT)
            runner.require(len(summaries) == 1 and summaries[0]['event'] == 'valid'
                           and summaries[0]['outcome_valid'] is True,
                           'N5 cell failed; preserve terminal and stop')
            audit_result(summaries[0], row, status, completed)
            completed.append(row['episode_key'])
        runner.durable_json(status, {'status': 'completed_all_four_audited', 'completed_keys': completed,
                                    'selected_physical_gpu': 3})
    except BaseException as exc:
        runner.durable_json(status, {'status': 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed',
                                    'completed_keys': completed, 'reason': str(exc) if isinstance(exc, runner.GateError) else type(exc).__name__,
                                    'selected_physical_gpu': 3})
        raise


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
