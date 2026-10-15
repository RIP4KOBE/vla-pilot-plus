#!/usr/bin/env python3
"""CPU-only outcome accounting; incomplete evidence can never pass a phase gate.

Scientific samples use explicit task/seed identities. Infrastructure recovery
may replace an unresolved attempt, but task failures remain in the denominator.
This report does not authorize a phase or infer QD causality from success rates.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import qd_ed_final_runner as runner

COST_FIELDS = ('model_forward_calls', 'model_batch_rows', 'denoising_invocations',
               'model_denoising_steps', 'denoising_step_batch_rows', 'reward_calls',
               'reward_evaluations', 'reward_scoring_batches', 'guided_chunks',
               'unguided_chunks', 'provider_request_attempts', 'provider_sdk_retry_attempts',
               'vision_encoder_forward_calls', 'vision_encoder_batch_rows',
               'text_encoder_forward_calls', 'text_encoder_batch_rows',
               'dino_forward_calls', 'dino_batch_rows',
               'candidate_evaluations', 'score_batches',
               'provider_logical_call_attempts', 'provider_completed_turns', 'provider_failed_calls',
               'provider_usage_complete_calls', 'provider_input_tokens', 'provider_cached_input_tokens',
               'provider_output_tokens', 'provider_reasoning_output_tokens', 'provider_call_latency_s')


def observed_total(values):
    """Unknown observations stay unknown, including a known subtotal plus null."""
    return sum(values) if all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                              for value in values) else None

def key(identity):
    return json.dumps(identity, sort_keys=True, separators=(',', ':'))


def summarize(plan, events, split, iteration):
    rows = runner.selected_rows(plan, split, iteration)
    expected = {}
    for row in rows:
        ident = runner.episode_identity(row)
        expected.setdefault(key(ident), ident)
    attempts = {k: [] for k in expected}
    for group in runner.event_groups(events).values():
        identity = group[0]['identity']
        runner.require(all(e['identity'] == identity for e in group), 'attempt identity changed')
        sample = key(identity)
        if sample not in expected:
            runner.require(identity.get('split') != split or str(identity.get('iteration')) != str(iteration),
                           'unplanned scientific sample in selected phase')
            continue
        previous = attempts[sample]
        # Enforce the same retry contract without depending on chronological
        # interleaving of unrelated samples in the append-only journal.
        if any(e['event'] == 'dispatched' for e in group):
            dispatched_previous = [g for g in previous if any(e['event'] == 'dispatched' for e in g)]
            if dispatched_previous:
                prior = dispatched_previous[-1][-1]
                runner.require(prior['event'] == 'aborted' and prior.get('retryable_infrastructure') is True,
                               'task outcome cannot be replaced by a later attempt')
                runner.require(group[0].get('retry_of') == prior['attempt_id'], 'unlinked recovery attempt')
            else:
                runner.require(not group[0].get('retry_of'), 'recovery has no dispatched predecessor')
        previous.append(group)
    samples = []
    for sample, identity in expected.items():
        groups = attempts[sample]
        dispatched = [g for g in groups if any(e['event'] == 'dispatched' for e in g)]
        final = dispatched[-1][-1] if dispatched else None
        result = {**identity, 'attempt_ids': [g[0]['attempt_id'] for g in groups],
                  'dispatched_attempts': len(dispatched), 'success': None, 'outcome_valid': False,
                  'required_cost_telemetry_complete': False, 'metric_chunks': 0,
                  'stage_backend': final.get('stage_backend') if final else None,
                  'stage_model': final.get('stage_model') if final else None,
                  'stage_condition': final.get('stage_condition') if final else None,
                  'provider_http_observation': final.get('provider_http_observation') if final else None,
                  'provider_token_usage_complete': final.get('provider_token_usage_complete') if final else None,
                  'gpu_process_wall_seconds': sum(g[-1].get('gpu_process_wall_seconds', 0)
                                                  for g in groups if g[-1]['event'] in runner.TERMINAL),
                  'terminal_costs': {field: final.get(field) if final else None for field in COST_FIELDS}}
        if final is None:
            result['status'] = 'pending'
        elif final['event'] == 'dispatched':
            result['status'] = 'running'
        elif final['event'] == 'valid':
            runner.require(type(final.get('success')) is bool, 'completed task lacks a boolean outcome')
            result.update(status='completed', success=final['success'],
                          outcome_valid=final.get('outcome_valid') is True,
                          required_cost_telemetry_complete=final.get('required_cost_telemetry_complete') is True,
                          metric_chunks=final.get('metric_chunks', 0),
                          failure_class=final.get('failure_class'), reason=final.get('reason'))
            runner.require(result['outcome_valid'] or result['success'] is False,
                           'invalid outcome cannot count as success')
        else:
            result['status'] = 'unresolved_infrastructure' if final.get('retryable_infrastructure') else 'unresolved_invalid'
            result['reason'] = final.get('reason')
        samples.append(result)
    profiles = {}
    for profile in sorted({s['profile'] for s in samples}):
        cells = [s for s in samples if s['profile'] == profile]
        completed = [s for s in cells if s['status'] == 'completed']
        profiles[profile] = {
            'expected': len(cells), 'completed': len(completed),
            'success_count': sum(s['success'] is True for s in completed),
            'failure_count': sum(s['success'] is False for s in completed),
            'unresolved_count': len(cells) - len(completed),
            'complete': len(completed) == len(cells),
            'outcome_valid': all(s['outcome_valid'] for s in cells),
            'cost_telemetry_complete': all(s['required_cost_telemetry_complete'] for s in cells),
            'guided_chunks': sum(s['metric_chunks'] for s in cells),
            'dispatched_attempts': sum(s['dispatched_attempts'] for s in cells),
            'gpu_hours_including_recovery': sum(s['gpu_process_wall_seconds'] for s in cells) / 3600,
            'stage_backends': sorted({s['stage_backend'] for s in cells if s['stage_backend'] is not None}),
            'stage_models': sorted({s['stage_model'] for s in cells if s['stage_model'] is not None}),
            'stage_conditions': sorted({s['stage_condition'] for s in cells if s['stage_condition'] is not None}),
            'provider_http_observations': sorted({s['provider_http_observation'] for s in cells
                                                if s['provider_http_observation'] is not None}),
            'provider_token_usage_complete': all(s['provider_token_usage_complete'] is True for s in cells)
                                            if any(s['stage_backend'] == 'codex_cli' for s in cells) else None,
            'terminal_cost_totals': {field: observed_total([s['terminal_costs'][field] for s in cells])
                                    for field in COST_FIELDS},
            # Missing observations are never dropped into a smaller denominator.
            'success_rate': sum(s['success'] is True for s in cells) / len(cells) if len(completed) == len(cells) else None,
        }
    comparisons = {}
    def cellkey(sample):
        return tuple(sample[k] for k in ('task_id', 'env_seed', 'policy_seed', 'init_index'))
    for candidate in sorted(set(profiles) - {'Q0', 'C0'}):
        for control in ('C0', 'Q0'):
            if control not in profiles:
                continue
            left = {cellkey(s): s for s in samples if s['profile'] == candidate}
            right = {cellkey(s): s for s in samples if s['profile'] == control}
            comparable = left.keys() == right.keys() and all(s['status'] == 'completed' for s in [*left.values(), *right.values()])
            comparisons[candidate + '_vs_' + control] = {
                'matched_and_complete': comparable,
                'success_delta': profiles[candidate]['success_count'] - profiles[control]['success_count'] if comparable else None,
                'gained': [list(k) for k in left if left[k]['success'] and not right[k]['success']] if comparable else [],
                'lost': [list(k) for k in left if not left[k]['success'] and right[k]['success']] if comparable else [],
            }
    return {'schema': 'qd-ed-final-outcomes-v1', 'run_name': plan['run_name'],
            'split': split, 'iteration': str(iteration), 'profiles': profiles,
            'comparisons': comparisons, 'samples': samples,
            'phase_authorized_by_report': False,
            'note': 'Task failures remain failures. Terminal cost totals exclude superseded recovery attempts; GPU time includes them. Codex logical calls, observed tokens and CLI latency are distinct from unobservable internal HTTP requests/retries; null totals mean unknown. Missing/invalid evidence and scientific QD activity require explicit phase review.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, default=runner.ROOT / 'data/attempt-ledger.jsonl')
    parser.add_argument('--split', choices=('dev', 'validation', 'formal'), required=True)
    parser.add_argument('--iteration', required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(runner.read_json(args.plan), runner.read_events(args.ledger), args.split, args.iteration),
                     indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
