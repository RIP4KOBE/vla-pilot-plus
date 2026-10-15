#!/usr/bin/env python3
"""Freeze the complete N4-E1 Dev decision and keep the broader study active."""
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import yaml

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
B = Path(__file__).resolve().parent
A = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
R = A / 'continuation_20260923/n4-e1-full12-report-v1'
D = B / 'full12-root-review-v1'
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


manifest = r.read_json(R / 'manifest.json')
report = r.read_json(R / 'report.json')
plan = r.read_json(B / 'plan.frozen.json')
revision = r.read_json(B / 'first3-release-v1/plan.checkpoint.frozen.json')
assert not D.exists()
assert report['schema'] == 'qd-ed-n4e1-matrix-report-v1' and report['cohort_id'] == n.COHORT
assert report['matrix'] == 'complete_valid_12' and report['cell_status_counts'] == {'complete_valid': 12}
assert report['input_scope_complete'] is True and report['input_manifest_sha256'] == r.digest(R / 'manifest.json')
assert report['episode_dispatches'] == report['resources']['episode_dispatches_observed'] == 12
assert report['resources']['inflight_costs_settled'] is True
assert report['resources']['within_local_8_5_hours'] is True
assert report['protocol_numeric_dev_criterion'] is False
assert report['protocol_execution_activity_criterion'] is True
assert report['profiles']['N4']['complete_valid'] == report['profiles']['C0']['complete_valid'] == report['profiles']['Q0']['complete_valid'] == 4
assert {p: report['profiles'][p]['successes_observed'] for p in ('C0', 'Q0', 'N4')} == {'C0': 0, 'Q0': 0, 'N4': 1}
assert report['profiles']['N4']['n4_consumer_summary']['guided_decisions_checked'] == 85
assert report['profiles']['N4']['n4_consumer_summary']['actual_prefix_different_decisions'] == 72
assert all(cell['status'] == 'complete_valid' for cell in report['cells'])
assert manifest['base_plan'] == ref(B / 'plan.frozen.json')
assert manifest['plan_revisions'] == [ref(B / 'first3-release-v1/plan.checkpoint.frozen.json')]
assert plan['source_commit'] == revision['source_commit']
assert [spec['terminal']['sha256'] for spec in manifest['attempts']] and len(manifest['attempts']) == 12
assert r.read_json(B / 'remaining9-v1/launch-result.json')['exit_code'] == 0
assert r.read_json(B / 'remaining9-v1/status.json')['status'] == 'completed'

stage_refs = []
latencies = []
for spec in manifest['attempts']:
    terminal = r.read_json(spec['terminal']['path'])
    path = Path(terminal['output_dir']) / 'eds_eval/stage_events.jsonl'
    rows = r.read_events(path)
    assert all(row.get('query_ok') is True for row in rows)
    assert len(rows) == terminal['stage_successful_queries'] == terminal['provider_logical_call_attempts']
    assert terminal['provider_failed_calls'] == terminal['stage_failed_queries'] == 0
    assert terminal['required_cost_telemetry_complete'] is True and terminal['provider_token_usage_complete'] is True
    assert all(isinstance(row.get('codex_call_latency_s'), (int, float)) for row in rows)
    latencies.extend(row['codex_call_latency_s'] for row in rows)
    stage_refs.append({'episode_key': terminal['episode_key'], 'events': ref(path), 'calls': len(rows),
                       'max_call_latency_s': max((row['codex_call_latency_s'] for row in rows), default=None)})
assert len(latencies) == 196 and max(latencies) < 90

with r.locked(W / 'data/qd-ed-runner.lock', nonblocking=True):
    with r.locked(W / 'data/qd-ed-state.lock'):
        state_path = W / 'research-state.yaml'
        state = r.read_state(state_path)
        events = r.read_events(W / 'data/attempt-ledger.jsonl')
        resources = r.read_events(W / 'data/gpu-healthcheck-ledger.jsonl')
        budget = r.budget_snapshot(events, resources)
        assert budget['running'] == 0 and budget['dispatched'] == 92
        assert budget['by_bucket']['baseline'] == 20 and budget['by_bucket']['development'] == 66
        assert budget['by_bucket']['validation'] == budget['by_bucket']['formal'] == 0
        assert state['budget']['dispatched'] == budget['dispatched']
        assert abs(state['budget']['gpu_hours_consumed'] - budget['gpu_hours_consumed']) < 1e-9
        assert state['candidate']['active_execution_release'] == ref(B / 'first3-release-v1/remaining9-execution-release.json')
        assert state['resource_isolation']['owned_supervisor']['pid'] == r.read_json(B / 'remaining9-v1/launch.json')['supervisor_pid']
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        review = {
            'schema': 'n4e1-complete-dev-root-review-v1', 'utc': now,
            'decision': 'REJECT_NUMERIC_DEV', 'candidate_mechanism': 'ACTIVE_BUT_NOT_SUFFICIENT',
            'project_target_met': False, 'study_continues': True, 'cohort_id': n.COHORT,
            'source_commit': plan['source_commit'], 'base_plan': ref(B / 'plan.frozen.json'),
            'checkpoint_plan': ref(B / 'first3-release-v1/plan.checkpoint.frozen.json'),
            'report': ref(R / 'report.json'), 'manifest': ref(R / 'manifest.json'),
            'first3_checkpoint': ref(B / 'first3-release-v1/correctness-checkpoint.json'),
            'first3_root_review': ref(B / 'first3-release-v1/root-review.json'),
            'remaining9_resource_preflight': ref(B / 'first3-release-v1/remaining9-resource-preflight.json'),
            'remaining9_launch_result': ref(B / 'remaining9-v1/launch-result.json'),
            'cell_status_counts': report['cell_status_counts'],
            'task_outcomes': [{'task_id': cell['identity']['task_id'], 'profile': cell['identity']['profile'],
                               'success': cell['success'], 'attempt_id': cell['valid_attempt_id']}
                              for cell in report['cells']],
            'success_counts': {profile: report['profiles'][profile]['successes_observed'] for profile in ('C0', 'Q0', 'N4')},
            'paired_comparisons': report['paired_comparisons'],
            'numeric_dev_criterion': False, 'execution_activity_criterion': True,
            'native_N4_guided_decisions': 85, 'native_actual_prefix_differences': 72,
            'episode_dispatches': 12, 'cohort_GPU_seconds': report['resources']['new_cohort_seconds'],
            'global_private_budget_snapshot': budget,
            'transport_observation': {'successful_complete_stage_calls': len(latencies),
                'failed_or_missing_calls': 0, 'max_call_latency_s': max(latencies),
                'calls_over_old_90_second_deadline': sum(value > 90 for value in latencies),
                'calls_over_new_180_second_deadline': sum(value > 180 for value in latencies),
                'stage_event_evidence': stage_refs,
                'causal_limit': 'All new calls finished below 90 seconds. This matched rerun validates costs but does not establish that the 180-second deadline caused the improvement in transport validity.'},
            'measurement_limits': [
                'Stored archive-reference decoding is not a counterfactual rollout or task-benefit causal estimate.',
                'Actual normalized Stage API arguments and true physical grasp/contact remain unmeasured.',
                'Dev seeds/tasks were previously exposed; this is an engineering re-evaluation, not independent holdout.',
                'The historical original90 N4 cohort remains invalid/incomplete and is not pooled here.'
            ],
            'protected_phase_authorized': False,
            'next_action': 'Bounded CPU outer-loop review of N4 failures, proposal/selection/closed-loop evidence and exact remaining budget; no new GPU dispatch without a separately frozen substantive hypothesis and valid contemporaneous control design.'
        }
        D.mkdir(parents=True, exist_ok=False)
        write(D / 'root-review.json', review)
        candidate = state['candidate']
        candidate['status'] = 'N4E1_DEV_REJECT_NUMERIC'
        candidate['scientific_decision'] = 'REJECT_NUMERIC_DEV_1_OF_4'
        candidate['online_score'] = {'split': 'dev', 'condition': 'N4_E1_t180', 'successes': 1, 'episodes': 4,
                                     'C0_successes': 0, 'Q0_successes': 0, 'target_minimum': 2}
        candidate['latest_report'] = ref(R / 'report.json')
        candidate['full_dev_root_review'] = ref(D / 'root-review.json')
        candidate['completed_execution_release'] = ref(B / 'first3-release-v1/remaining9-execution-release.json')
        candidate['active_execution_release'] = None
        candidate['online_dispatch_authorized'] = False
        candidate['engineering_dependency']['status'] = 'DEV_COMPLETE_VALID_TRANSPORT'
        candidate['engineering_dependency']['online_authorized'] = False
        state['closed_candidates']['N4'] = {'decision': 'REJECT_NUMERIC_DEV',
                                             'report': ref(R / 'report.json'),
                                             'review': ref(D / 'root-review.json'),
                                             'source_commit': plan['source_commit'], 'condition': 'N4_E1_t180'}
        state['study']['status'] = 'ACTIVE_OUTER_REVIEW_AFTER_N4E1_DEV'
        state['project_target']['status'] = 'IN_PROGRESS_TARGET_NOT_YET_MET'
        state['project_target']['achieved'] = False
        state['current_owned_workers'] = []
        state['resource_isolation']['owned_supervisor']['terminal_status'] = 'EXIT_0_COMPLETED'
        state['resource_isolation']['owned_supervisor']['launch_result'] = ref(B / 'remaining9-v1/launch-result.json')
        state['next_action'] = review['next_action']
        state['updated_at'] = now
        handle, temporary = tempfile.mkstemp(prefix='.research-state.n4e1-', suffix='.yaml', dir=W)
        try:
            with os.fdopen(handle, 'w') as stream:
                yaml.safe_dump(state, stream, sort_keys=False, allow_unicode=True)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, state_path)
            descriptor = os.open(W, os.O_RDONLY)
            try: os.fsync(descriptor)
            finally: os.close(descriptor)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
        ledger_path = W / 'docs/03_evidence/qd_ed_final/iteration-ledger.md'
        with ledger_path.open('a') as stream:
            stream.write(f'\n\n### {now} — N4-E1 complete Dev REJECT; project study active\n\n')
            stream.write(f'N4-E1 transport180 matched matrix:12/12 accepted valid,12 dispatches, '
                         f'GPU seconds{review["cohort_GPU_seconds"]:.6f}. N4 1/4 task3; C0 0/4; Q0 0/4. '
                         'N4 gained task3 over both controls with no losses, but predeclared ≥2/4 criterion fails. '
                         'Native consumer active:85 guided decisions,72 decoded actual-prefix differences; activity is not task benefit. '
                         f'All196 Stage calls completed with max{max(latencies):.3f}s (<old90), so 180s causal role unproven. '
                         f'Private cumulative{budget["dispatched"]}/240 attempts,{budget["gpu_hours_consumed"]:.9f}/48 GPUh; '
                         'baseline20/20,development66/100,recovery6/20,validation/formal untouched. '
                         f'Root review {D / "root-review.json"} SHA{r.digest(D / "root-review.json")}; '
                         f'report SHA{r.digest(R / "report.json")}. No protected release; bounded outer-loop continues.\n')
            stream.flush(); os.fsync(stream.fileno())
print(json.dumps({'decision': review['decision'], 'root_review': ref(D / 'root-review.json'),
                  'success_counts': review['success_counts'], 'budget': budget}))
