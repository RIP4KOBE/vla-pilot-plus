#!/usr/bin/env python3
"""Serial GPU7 N19 three-arm Dev supervisor; stop on first invalid cell."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal

import qd_ed_final_runner as runner
import qd_ed_n19_dev_contract as contract
import qd_ed_available_gpu_queue as queue
import audit_decision_evidence as audit

ROOT = Path(__file__).resolve().parents[1]


def release_check(path, plan_path, plan):
    release = runner.read_json(path)
    device = 7
    runner.require(release == {
        'schema': 'n19-dev-execution-release-v1',
        'plan_path': str(Path(plan_path).resolve()),
        'plan_sha256': runner.digest(plan_path),
        'source_commit': plan['source_commit'],
        'cohort_id': contract.COHORT,
        'episode_keys': [row['episode_key'] for row in plan['episodes']],
        'physical_gpu': device,
        'validation_authorized': False,
        'formal_authorized': False,
    }, 'N19 release differs from frozen Dev plan')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    args = parser.parse_args()
    plan, _, _ = runner.validate_plan(args.plan, root=ROOT)
    device = 7
    release_check(args.release, args.plan, plan)
    status = runner.owned(args.status, plan['artifact_root'])
    runner.require(not status.exists(), 'N19 status already exists')
    completed = []
    successes = {arm: 0 for arm in contract.ARMS}
    candidate_successes = set()
    native = {'score_batches_verified': 0, 'candidate_scores_verified': 0,
              'positive_bonus_candidates': 0}
    runner.durable_json(status, {'status': 'started', 'completed_keys': completed,
                                'successes': successes, 'physical_gpu': device})
    try:
        for row in plan['episodes']:
            devices = queue.inventory()
            runner.require(device in devices, f'GPU{device} missing')
            queue.reservation_admission(devices[device])
            runner.gpu_admission(physical_gpu=device, expected_uuid=devices[device]['uuid'])
            with runner.n19_support().supervised_scope(plan, ROOT, row['episode_key']):
                summaries = runner.run_plan(args.plan, split='dev', iteration=contract.COHORT,
                                            episode_keys=[row['episode_key']], root=ROOT)
            runner.require(len(summaries) == 1, 'N19 one-cell result missing')
            result = summaries[0]
            output = Path(result['output_dir'])
            links = contract.RUN_DIR / 'attempts'
            links.mkdir(parents=True, exist_ok=True)
            link = links / result['attempt_id']
            runner.require(not link.exists() and not link.is_symlink(), 'N19 attempt index collision')
            link.symlink_to(output, target_is_directory=True)
            runner.require(result['event'] == 'valid' and result['outcome_valid'] is True,
                           'N19 Dev invalid; no automatic retry')
            report = audit.audit_episode(output / 'eds_eval/decision_evidence/episode_000',
                                         output / 'eds_eval/episode_compute.jsonl')
            runner.durable_json(output / 'eds_eval/decision-evidence-audit.json', report)
            runner.require(report.get('accepted') is True and report.get('evidence_complete') is True,
                           'N19 native evidence failed')
            if row['profile'] == 'N19':
                metric = runner.read_events(output / 'eds_eval/eds_metrics.jsonl')
                gate = report.get('n18_lift_quality_audit', {})
                runner.require(gate.get('score_batches_verified') == 11 * len(metric)
                               and gate.get('candidate_scores_verified') == 176 * len(metric)
                               and report.get('n5_grasp_timing_audit', {}).get('checked_decisions') == len(metric),
                               'N19 quality/selection or fixed compute not natively audited')
                for key in native:
                    native[key] += gate[key]
                if result['success'] is True:
                    candidate_successes.add(row['task_id'])
            successes[row['profile']] += int(result['success'] is True)
            completed.append(row['episode_key'])
            runner.durable_json(status, {'status': 'cell_audited', 'completed_keys': completed,
                'successes': successes, 'native': native,
                'last_attempt': result['attempt_id'], 'physical_gpu': device})
        promoted = (0 in candidate_successes and successes['N19'] >= 2
                    and successes['N19'] > max(successes['C0'], successes['Q0'])
                    and native['positive_bonus_candidates'] > 0)
        runner.durable_json(status, {'status': 'completed_all_nine_audited',
            'completed_keys': completed, 'successes': successes, 'native': native,
            'candidate_success_tasks': sorted(candidate_successes),
            'dev_gate_promoted': promoted, 'physical_gpu': device})
    except BaseException as exc:
        runner.durable_json(status, {'status': 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed',
            'completed_keys': completed, 'successes': successes, 'native': native,
            'reason': type(exc).__name__, 'physical_gpu': device})
        raise


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
