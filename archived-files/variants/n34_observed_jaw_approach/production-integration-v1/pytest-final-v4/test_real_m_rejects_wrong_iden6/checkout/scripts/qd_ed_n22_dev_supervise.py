#!/usr/bin/env python3
"""Serial matched ten-task N22 Dev; native-invalid stop, numeric futility, no retries."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import signal

import qd_ed_final_runner as runner
import qd_ed_n22_dev_contract as contract
import qd_ed_available_gpu_queue as queue
import audit_decision_evidence as audit

ROOT = Path(__file__).resolve().parents[1]
NATIVE_FIELDS = ('score_batches_verified', 'candidate_scores_verified',
                 'positive_bonus_candidates', 'rank_changed_batches')
COST_FIELDS = ('model_forward_calls', 'model_batch_rows', 'reward_calls',
               'reward_evaluations', 'reward_scoring_batches',
               'provider_logical_call_attempts', 'stage_codex_logical_call_attempts',
               'gpu_process_wall_seconds')


def release_check(path, plan_path, plan):
    release = runner.read_json(path)
    runner.require(release == {
        'schema': 'n22-dev-execution-release-v1',
        'plan_path': str(Path(plan_path).resolve()),
        'plan_sha256': runner.digest(plan_path),
        'source_commit': plan['source_commit'],
        'cohort_id': contract.COHORT,
        'episode_keys': [row['episode_key'] for row in plan['episodes']],
        'physical_gpu': 7,
        'validation_authorized': False,
        'formal_authorized': False,
    }, 'N22 release differs from frozen Dev plan')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    args = parser.parse_args()
    plan, _, _ = runner.validate_plan(args.plan, root=ROOT)
    release_check(args.release, args.plan, plan)
    status = runner.owned(args.status, plan['artifact_root'])
    runner.require(not status.exists(), 'N22 status already exists; cohort cannot resume')
    status.parent.mkdir(parents=True, exist_ok=True)
    completed, attempted = [], []
    successes = {arm: 0 for arm in contract.ARMS}
    candidate_successes = []
    native = {arm: {**{key: 0 for key in NATIVE_FIELDS},
                    'guided_decisions': 0, 'parent_rounds_verified': 0}
              for arm in ('N21', 'N22')}
    costs = {arm: {key: 0 for key in COST_FIELDS} for arm in contract.ARMS}
    missing_costs = []

    def write(state, **extra):
        runner.durable_json(status, {
            'status': state, 'completed_keys': completed, 'attempted_keys': attempted,
            'successes': successes, 'native': native, 'cost_totals': costs,
            'cost_missing_fields': missing_costs,
            'candidate_success_tasks': candidate_successes,
            'physical_gpu': 7, 'n21_role': 'ablation_control_only_no_promotion',
            'dev_gate_promoted': False, **extra})

    write('started')
    try:
        for row in plan['episodes']:
            devices = queue.inventory()
            runner.require(7 in devices and devices[7]['uuid'] == contract.GPU7_UUID,
                           'N22 GPU7 UUID missing or differs')
            queue.reservation_admission(devices[7])
            runner.gpu_admission(physical_gpu=7, expected_uuid=contract.GPU7_UUID)
            with runner.n22_support().supervised_scope(plan, ROOT, row['episode_key']):
                summaries = runner.run_plan(args.plan, split='dev', iteration=contract.COHORT,
                                            episode_keys=[row['episode_key']], root=ROOT)
            runner.require(len(summaries) == 1, 'N22 one-cell result missing')
            result = summaries[0]
            attempted.append(row['episode_key'])
            for key in COST_FIELDS:
                value = result.get(key)
                if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                    costs[row['profile']][key] += value
                else:
                    missing_costs.append({'episode_key': row['episode_key'], 'field': key})
            output = Path(result['output_dir'])
            links = contract.RUN_DIR / 'attempts'
            links.mkdir(parents=True, exist_ok=True)
            link = links / result['attempt_id']
            runner.require(not link.exists() and not link.is_symlink(), 'N22 attempt index collision')
            link.symlink_to(output, target_is_directory=True)
            runner.require(result['event'] == 'valid' and result['outcome_valid'] is True,
                           'N22 Dev invalid; no automatic retry')
            runner.require(not missing_costs, 'N22 actual cost telemetry missing')
            report = audit.audit_episode(output / 'eds_eval/decision_evidence/episode_000',
                                         output / 'eds_eval/episode_compute.jsonl')
            runner.durable_json(output / 'eds_eval/decision-evidence-audit.json', report)
            runner.require(report.get('accepted') is True and report.get('evidence_complete') is True,
                           'N22 native evidence failed')
            if row['profile'] in native:
                arm = row['profile']
                metric = runner.read_events(output / 'eds_eval/eds_metrics.jsonl')
                gate = report.get('n22_hold_lift_quality_audit' if arm == 'N22'
                                  else 'n18_lift_quality_audit', {})
                selection = report.get('n5_grasp_timing_audit', {})
                count = len(metric)
                if count:
                    runner.require(gate.get('score_batches_verified') == 11 * count
                                   and gate.get('candidate_scores_verified') == 176 * count
                                   and selection.get('checked_decisions') == count
                                   and selection.get('parent_rounds_verified') == 10 * count,
                                   'N22 quality/selection/parent or fixed compute not natively audited')
                    expected_mode = 'close_hold_then_lift_v1' if arm == 'N22' else 'close_then_lift_v1'
                    runner.require(all(m.get('qd_archive_active_for_chunk') is True
                                       and m.get('qd_quality_mode') == expected_mode
                                       and m.get('score_call_count') == 11
                                       and m.get('search_evaluation_count') == 176
                                       and all(m.get(k) == 10 for k in
                                               ('resample_count', 'renoise_count', 'rollout_count'))
                                       for m in metric), 'N22 substantive QD/ED activity differs')
                    for key in NATIVE_FIELDS:
                        runner.require(type(gate.get(key)) is int and gate[key] >= 0,
                                       'N22 native mechanism counter missing')
                        native[arm][key] += gate[key]
                    native[arm]['parent_rounds_verified'] += selection['parent_rounds_verified']
                    native[arm]['guided_decisions'] += count
                else:
                    runner.require(not gate and not selection, 'N22 unguided metric/audit mismatch')
                if arm == 'N22' and result['success'] is True:
                    candidate_successes.append(row['task_id'])
            successes[row['profile']] += int(result['success'] is True)
            completed.append(row['episode_key'])
            write('cell_audited', last_attempt=result['attempt_id'])
            if row['profile'] == 'N22':
                remaining = len(contract.TASKS) - len(completed) // len(contract.ARMS)
                if successes['N22'] + remaining < 5:
                    write('rejected_numeric_futility', remaining_tasks=remaining,
                          maximum_possible_candidate_successes=successes['N22'] + remaining)
                    return
        promoted = (len(completed) == 40 and successes['N22'] >= 5
                    and successes['N22'] >= max(successes[arm] for arm in ('C0', 'Q0', 'N21'))
                    and native['N22']['guided_decisions'] > 0
                    and native['N22']['parent_rounds_verified'] > 0)
        write('completed_all_forty_audited', dev_gate_promoted=promoted,
              candidate_lift_bonus_observed=native['N22']['positive_bonus_candidates'] > 0,
              candidate_ranking_change_observed=native['N22']['rank_changed_batches'] > 0,
              mechanism_caveat='Bonus/ranking counts are descriptive, not additional promotion vetoes or causal task evidence.')
    except BaseException as exc:
        write('interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed',
              reason=type(exc).__name__,
              detail=str(exc) if isinstance(exc, runner.GateError) else type(exc).__name__)
        raise


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
