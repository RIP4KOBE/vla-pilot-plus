#!/usr/bin/env python3
"""Review completed E1 first-three evidence and freeze the remaining-nine release."""
import argparse
import copy
import datetime
import json
from pathlib import Path
import sys

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
B = Path(__file__).resolve().parent
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r
import qd_ed_n4e1_plan as n


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': r.digest(path)}


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    source_plan_path = B / 'plan.frozen.json'
    source_plan = r.read_json(source_plan_path)
    report_dir = r.owned(args.report_dir, source_plan['artifact_root'])
    output = r.owned(args.output_dir, source_plan['artifact_root'])
    assert output.is_relative_to(B) and not output.exists()
    assert report_dir == Path(source_plan['artifact_root']) / 'continuation_20260923/n4-e1-first3-report-v1'
    manifest = r.read_json(report_dir / 'manifest.json')
    report = r.read_json(report_dir / 'report.json')
    assert report['input_manifest_sha256'] == r.digest(report_dir / 'manifest.json')
    assert report['input_scope_complete'] is True and report['matrix'] == 'incomplete'
    assert report['cell_status_counts'] == {'complete_valid': 3, 'missing': 9}
    assert report['first_three']['all_complete_valid'] is True
    assert len(manifest['attempts']) == 3 and not manifest['plan_revisions']
    assert report['episode_dispatches'] == 3 and report['resources']['inflight_costs_settled'] is True
    assert report['resources']['within_local_8_5_hours'] is True
    assert report['predispatch_records'] == [] and report['inflight_records'] == []
    assert [cell['identity']['profile'] for cell in report['cells'][:3]] == ['C0', 'Q0', 'N4']
    assert all(cell['status'] == 'complete_valid' for cell in report['cells'][:3])
    assert all(cell['status'] == 'missing' for cell in report['cells'][3:])
    assert all(type(cell['success']) is bool for cell in report['cells'][:3])
    attempts = [cell['valid_attempt_id'] for cell in report['cells'][:3]]
    assert all(cell['attempts'][0]['terminal']['required_cost_telemetry_complete'] is True
               and cell['attempts'][0]['terminal']['provider_token_usage_complete'] is True
               and cell['attempts'][0]['terminal']['provider_failed_calls'] == 0
               and cell['attempts'][0]['terminal']['stage_failed_queries'] == 0
               for cell in report['cells'][:3])
    assert all(cell['metrics']['finite_executed_actions'] is True for cell in report['cells'][:3])
    assert report['cells'][0]['metrics']['qd_active_chunks'] == 0
    assert report['cells'][1]['metrics']['qd_active_chunks'] == report['cells'][1]['metrics']['guided_chunks'] > 0
    metric = report['cells'][2]['metrics']
    assert metric['qd_active_chunks'] == metric['guided_chunks'] > 0
    native = metric['n4']['native_terminal_population_alignment']
    audit = native['audit']
    count = metric['guided_chunks']
    assert native['status'] == 'verified' and native['checked_decisions'] == count
    assert audit['checked_decisions'] == count and audit['canonical_batches_verified'] == 11 * count
    assert audit['canonical_candidates_verified'] == 176 * count and audit['parent_rounds_verified'] == 10 * count
    assert audit['actual_actions_verified'] > 0
    assert all(row['selected_index'] == min(range(16), key=lambda i: row['terminal_native_costs']['values'][i])
               and row['stage_raw_reward'] == row['selected_raw_reward']
               and row['archive_cost_reference_sha256'] == row['archive_reference_costs']['sha256']
               and row['archive_cost_spread_scale'] > 0 for row in audit['decisions'])
    assert metric['observed_scoring_roles'] == {'auxiliary_pretest': 5 * count,
                                                 'canonical_initial': count,
                                                 'canonical_offspring': 10 * count}
    assert metric['n4']['actual_prefix_different_decisions'] == native['actual_prefix_different_decisions']
    checks = {name: True for name in n.CHECKS}
    evidence = [ref(report_dir / 'report.json'), ref(report_dir / 'manifest.json'),
                ref(report_dir / 'journal-excerpt.json'), ref(B / 'root-prelaunch-review.json')]
    evidence += [spec[key] for spec in manifest['attempts'] for key in ('terminal', 'audit', 'compute', 'metrics')]
    assert len({item['path'] for item in evidence}) == len(evidence)
    with r.locked(W / 'data/qd-ed-state.lock'):
        state = r.read_state(W / 'research-state.yaml')
        events = r.read_events(W / 'data/attempt-ledger.jsonl')
        resources = r.read_events(W / 'data/gpu-healthcheck-ledger.jsonl')
        budget = r.budget_snapshot(events, resources)
        assert state['budget']['max_episode_attempts'] == 240 and state['budget']['max_gpu_hours'] == 48
        assert state['candidate']['active_execution_release'] == ref(B / 'execution-release.json')
        assert all(group[-1]['event'] in r.TERMINAL for group in r.event_groups(events).values()
                   if group[0].get('identity', {}).get('iteration') == n.COHORT)
    output.mkdir(parents=True, exist_ok=False)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    root_review = {
        'schema': 'n4e1-first3-root-correctness-review-v1', 'status': 'PASS_CORRECTNESS_ONLY',
        'utc': now, 'cohort_id': n.COHORT, 'base_plan': ref(source_plan_path),
        'source_commit': source_plan['source_commit'], 'source_files_sha256': n.source_identity(source_plan),
        'attempt_ids': attempts,
        'task_successes': {cell['identity']['profile']: cell['success'] for cell in report['cells'][:3]},
        'checks': checks,
        'native_N4_summary': {key: audit[key] for key in ('schema', 'checked_decisions',
            'canonical_batches_verified', 'canonical_candidates_verified', 'parent_rounds_verified',
            'actual_actions_verified', 'decoded_reference_first8_different_decisions',
            'decoded_reference_actual_prefix_different_decisions')},
        'budget_snapshot': budget, 'evidence': evidence,
        'root_review_basis': 'Frozen report revalidated all three original terminals, accepted audits, complete actual costs and exact native/metric/action associations.',
        'measurement_limits': [
            'Stored archive-reference decoding is not a counterfactual rollout or causal task-benefit claim.',
            'Actual normalized Stage API arguments remain unmeasured; the source and recorded raw/scale associations are unchanged.'
        ],
        'first3_effect_gate_applied': False, 'full12_numerical_and_activity_decision_pending': True,
        'protected_phase_authorized': False,
    }
    write(output / 'root-review.json', root_review)
    checkpoint = {
        'schema': 'qd-ed-n4e1-checkpoint-v1', 'cohort_id': n.COHORT,
        'source_commit': source_plan['source_commit'],
        'source_files_sha256': n.source_identity(source_plan),
        'protocol_sha256': source_plan['n4e1_cohort']['protocol']['sha256'],
        'attempt_ids': attempts, 'checks': checks,
        'evidence': [ref(output / 'root-review.json'), ref(report_dir / 'report.json'),
                     ref(report_dir / 'manifest.json'), *[spec['audit'] for spec in manifest['attempts']]],
        'utc': now,
    }
    write(output / 'correctness-checkpoint.json', checkpoint)
    checkpoint_reference = ref(output / 'correctness-checkpoint.json')
    n.read_attestation(checkpoint_reference, source_plan, W, r, 'qd-ed-n4e1-checkpoint-v1')
    plan = copy.deepcopy(source_plan)
    plan['n4e1_cohort']['checkpoint_release'] = checkpoint_reference
    runtime = r.read_json(plan['runtime_manifest_path'])
    seed = r.read_json(plan['seed_plan_path'])
    profiles = r.read_json(plan['profiles_path'])
    profiles['profiles']['N4'] = r.expand_candidate('N4', r.read_json(W / n.PROFILE), profiles['profiles']['Q0'])
    n.validate_contract(plan, profiles, runtime, seed, W, r, metadata_only=True)
    plan_path = output / 'plan.checkpoint.frozen.json'
    write(plan_path, plan)
    release = copy.deepcopy(r.read_json(B / 'execution-release.json'))
    release['plan'] = ref(plan_path)
    release['episode_keys'] = [row['episode_key'] for row in plan['episodes'][3:]]
    release['stage'] = 'remaining9'
    release['checkpoint_release'] = checkpoint_reference
    release['root_prelaunch_review'] = ref(output / 'root-review.json')
    release_path = output / 'remaining9-execution-release.json'
    write(release_path, release)
    n.execution_release(ref(release_path), plan_path, plan, runtime, release['episode_keys'], W, r)
    print(json.dumps({'status': 'PASS_CORRECTNESS_ONLY', 'release': ref(release_path),
                      'checkpoint': checkpoint_reference, 'remaining_keys': release['episode_keys']}))


if __name__ == '__main__':
    main()
