#!/usr/bin/env python3
"""Prospective stdlib-only N2 report. Explicit SHA-bound JSON inputs; no bundles.

Reports evidence, not phase authorization. Invalid attempts retain their costs.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path

COHORT = 'N2_EXECUTED_QUALITY_DEV_20260923'
BASE_PLAN_SHA = 'ec037ec84555bd46d3b776f29979545d21b21c1f3671c3bd32b07e933d5cdc45'
PROFILES = ('C0', 'Q0', 'N2')
IDENTITY = ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')
BINDING = ('source_commit', 'profiles_sha256', 'runtime_manifest_sha256', 'runtime_inventory_sha256', 'seed_plan_sha256')
COSTS = ('model_forward_calls', 'model_batch_rows', 'denoising_invocations', 'model_denoising_steps',
    'denoising_step_batch_rows', 'reward_calls', 'reward_evaluations', 'reward_scoring_batches',
    'guided_chunks', 'unguided_chunks', 'vision_encoder_forward_calls', 'vision_encoder_batch_rows',
    'text_encoder_forward_calls', 'text_encoder_batch_rows', 'dino_forward_calls', 'dino_batch_rows',
    'candidate_evaluations', 'score_batches', 'rbf_gradient_calls', 'rbf_gradient_batch_rows', 'renoise_invocations',
    'provider_logical_call_attempts', 'provider_completed_turns', 'provider_failed_calls', 'provider_usage_complete_calls',
    'provider_input_tokens', 'provider_cached_input_tokens', 'provider_output_tokens', 'provider_reasoning_output_tokens',
    'provider_call_latency_s', 'provider_request_attempts', 'provider_sdk_retry_attempts')
HTTP = {'provider_request_attempts', 'provider_sdk_retry_attempts'}
VIOLATIONS = ('nonfinite_count', 'gripper_qpos_violation_count', 'qd_accounting_violation_count',
    'qd_elite_monotonicity_violation_count', 'qd_final_selection_mismatch_count', 'qd_secondary_invariant_violation_count')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pairs(items):
    result = {}
    for k, v in items:
        require(k not in result, 'duplicate JSON key: ' + k)
        result[k] = v
    return result


def parse(text):
    return json.loads(text, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def read_ref(reference, *, lines=False):
    path = Path(reference['path']).resolve()
    require(path.suffix in ({'.jsonl'} if lines else {'.json'}), 'only explicit JSON/JSONL input allowed')
    require(sha(path) == reference['sha256'], 'SHA differs: ' + str(path))
    text = path.read_text()
    return [parse(line) for line in text.splitlines() if line.strip()] if lines else parse(text)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def observed(values):
    known = [v for v in values if finite(v) and v >= 0]
    return {'complete_total': sum(known) if values and len(known) == len(values) else None,
        'observed_subtotal': sum(known) if known else None, 'observed_values': len(known), 'missing_values': len(values)-len(known)}


def describe(values):
    require(all(finite(v) for v in values), 'nonfinite descriptive scalar')
    return {'count': len(values), 'min': min(values) if values else None, 'max': max(values) if values else None,
        'negative': sum(v < 0 for v in values), 'zero': sum(v == 0 for v in values), 'positive': sum(v > 0 for v in values)}


def cellkey(row):
    return row['task_id'], row['profile']


def plan_contract(plan):
    require(plan['n2_cohort']['cohort_id'] == COHORT, 'wrong cohort')
    rows = [r for r in plan['episodes'] if not r.get('retry_of')]
    require([cellkey(r) for r in rows] == [(task, p) for task in range(10) for p in PROFILES], 'original 30-cell order differs')
    require(len({r['episode_key'] for r in plan['episodes']}) == len(plan['episodes']), 'duplicate planned episode key')
    for task in range(10):
        group = [r for r in rows if r['task_id'] == task]
        require(len({tuple(r[k] for k in ('env_seed', 'policy_seed', 'init_index', 'init_row_sha256')) for r in group}) == 1,
                'matched task seed/init differs')
    for row in rows:
        require(row['split'] == 'dev' and row['iteration'] == COHORT, 'non-Dev cell')
    recoveries = [r for r in plan['episodes'] if r.get('retry_of')]
    require(len(recoveries) <= 4 and len({cellkey(r) for r in recoveries}) == len(recoveries), 'recovery allowance differs')
    by_cell = {cellkey(r): r for r in rows}
    for row in recoveries:
        require(cellkey(row) in by_cell and all(row[k] == by_cell[cellkey(row)][k] for k in IDENTITY), 'recovery scientific identity differs')
    return rows


def validate_terminal(terminal, plan, plan_sha):
    require(terminal['plan_sha256'] == plan_sha and terminal['event'] in {'valid', 'aborted'}, 'nonterminal/unbound record')
    row = next((r for r in plan['episodes'] if r['episode_key'] == terminal['episode_key']), None)
    require(row is not None and terminal['identity'] == {k: row[k] for k in IDENTITY}, 'unplanned terminal identity')
    require(terminal['physical_gpu'] == 3 and terminal['source_commit'] == plan['source_commit']
        and terminal['profile_manifest_sha256'] == plan['profiles_sha256']
        and terminal['runtime_manifest_sha256'] == plan['runtime_manifest_sha256']
        and terminal['runtime_inventory_sha256'] == plan['runtime_inventory_sha256']
        and terminal['init_row_sha256'] == row['init_row_sha256']
        and terminal.get('retry_of') == row.get('retry_of'), 'terminal frozen condition differs')
    binding = terminal.get('n2_frozen_identity', {})
    require(terminal.get('n2_cohort_id') == COHORT and binding.get('cohort_id') == COHORT
        and all(binding.get(k) == plan[k] for k in BINDING)
        and binding.get('protocol_sha256') == plan['n2_cohort']['protocol']['sha256']
        and binding.get('accounting_clarification_sha256') == plan['n2_cohort']['accounting_clarification']['sha256']
        and binding.get('candidate_sha256') == plan['candidate_profiles']['N2']['sha256'], 'N2 binding differs')
    require(type(terminal.get('success')) is bool and type(terminal.get('outcome_valid')) is bool, 'raw outcome missing')
    require(finite(terminal.get('gpu_process_wall_seconds')) and terminal['gpu_process_wall_seconds'] >= 0, 'terminal GPU cost missing')
    return row


def summarize_metrics(metrics, terminal, audit, compute):
    profile = terminal['identity']['profile']
    require(len(metrics) == terminal['metric_chunks'] == compute['guided_chunks'], 'guided metric counts differ')
    steps = [m['global_step'] for m in metrics]
    require(len(set(steps)) == len(steps), 'duplicate metric step')
    for metric in metrics:
        require(metric['episode'] == 0 and metric['task_id'] == terminal['identity']['task_id']
            and type(metric['global_step']) is int and 0 <= metric['global_step'] <= 720, 'metric identity differs')
        require(metric['score_call_count'] == 11 and metric['search_evaluation_count'] == 176, 'frozen 11/176 accounting differs')
        require(all(type(metric.get(k)) is int and metric[k] == 0 for k in VIOLATIONS), 'metric safety/accounting violation')
        require(finite(metric.get('action_mask_violation_max')) and 0 <= metric['action_mask_violation_max'] <= 1e-6,
                'existing action-mask gate fails')
    require(sum(m['score_call_count'] for m in metrics) == terminal['score_batches']
            and sum(m['search_evaluation_count'] for m in metrics) == terminal['candidate_evaluations'], 'terminal canonical counts differ')
    result = {'guided_chunks': len(metrics), 'canonical_score_batches': terminal['score_batches'],
        'canonical_candidate_evaluations': terminal['candidate_evaluations'],
        'finite_executed_actions': True, 'finite_action_evidence': 'accepted frozen auditor plus zero metric nonfinite_count; no action tensors reread',
        'observed_scoring_roles': audit.get('observed_scoring_roles'),
        'qd_active_chunks': sum(m.get('qd_archive_active_for_chunk') is True for m in metrics),
        'select_action_latency_s': observed([m.get('select_action_latency_s') for m in metrics]),
        'eds_loop_latency_s': observed([m.get('eds_loop_latency_s') for m in metrics]),
        'observer_wall_s': compute.get('decision_evidence', {}).get('observer_wall_s'),
        'observer_bytes_written': compute.get('decision_evidence', {}).get('bytes_written'), 'n2': None}
    if profile != 'N2':
        require(all(m.get('qd_quality_mode', 'provider') == 'provider' for m in metrics), 'control quality mode differs')
        return result
    records = []
    for metric in metrics:
        require(metric.get('qd_quality_mode') == 'executed_prefix_v1'
                and type(metric.get('qd_quality_applicable')) is bool and isinstance(metric.get('qd_quality_reason'), str), 'N2 applicability metadata missing')
        batches = metric.get('qd_quality_batches')
        require(isinstance(batches, list), 'N2 quality batches missing')
        applicable = metric['qd_quality_applicable']
        changed = 0
        if applicable:
            require(type(metric.get('qd_quality_target_index')) is int and metric['qd_quality_target_index'] >= 0
                    and metric.get('qd_quality_identity'), 'N2 recognized identity missing')
            require([b['iter_idx'] for b in batches] == list(range(-1, 10)), 'N2 canonical quality iterations differ')
            for batch in batches:
                raw, quality, fps = batch['raw_provider_quality'], batch['quality'], batch['fingerprints']
                require(len(raw) == len(quality) == len(fps) == 16 and all(finite(v) for v in raw + quality), 'N2 quality population differs')
                changed += sum(x != y for x, y in zip(raw, quality))
            raw, best, gap = (metric.get(k) for k in ('qd_selected_raw_reward', 'qd_final_best_raw_reward', 'qd_selected_raw_gap'))
            require(all(finite(v) for v in (raw, best, gap, metric.get('selected_reward'), metric.get('qd_best_observed_raw_reward')))
                    and gap == raw-best and gap <= 0, 'N2 selected raw-quality gap inconsistent')
        else:
            require(batches == [], 'inapplicable N2 unexpectedly has Q8 batches')
        require(type(metric.get('qd_quality_changed_candidates')) is int and metric['qd_quality_changed_candidates'] == changed,
                'N2 changed-quality count differs')
        records.append({k: metric.get(k) for k in ('global_step', 'qd_quality_applicable', 'qd_quality_reason', 'qd_quality_target_index',
            'qd_quality_identity', 'qd_quality_changed_candidates', 'qd_selected_raw_reward', 'qd_final_best_raw_reward',
            'qd_selected_raw_gap', 'qd_best_observed_raw_reward', 'selected_reward')})
    result['n2'] = {'records': records, 'applicable_chunks': sum(r['qd_quality_applicable'] for r in records),
        'inapplicable_chunks': sum(not r['qd_quality_applicable'] for r in records),
        'reason_counts': dict(Counter(r['qd_quality_reason'] for r in records)),
        'quality_changed_candidates': sum(r['qd_quality_changed_candidates'] for r in records),
        'raw_selected_minus_final_best': describe([r['qd_selected_raw_gap'] for r in records if r['qd_quality_applicable']]),
        'normalized_stage_input_directly_observed': False,
        'raw_stage_separation_evidence': 'source/CPU tests plus recorded selected raw scalar; actual normalized Stage input is not logged',
        'selection_change_count': None, 'selection_change_count_limit': 'different internal/raw scalar alone does not establish changed search/selected action'}
    return result


def summarize(plan, attempts):
    rows = plan_contract(plan)
    grouped = defaultdict(list)
    require(len(attempts) <= 34 and len({a['terminal']['attempt_id'] for a in attempts}) == len(attempts), 'duplicate/excess input attempt')
    for attempt in attempts:
        grouped[cellkey(attempt['terminal']['identity'])].append(attempt)
    bindings = {json.dumps(a['terminal']['n2_frozen_identity'], sort_keys=True) for a in attempts}
    require(len(bindings) <= 1, 'cohort runtime/Stage frozen bindings differ')
    require(set(grouped) <= {cellkey(row) for row in rows}, 'outside-matrix attempt')
    cells = []
    for row in rows:
        group = sorted(grouped[cellkey(row)], key=lambda a: a['terminal']['time_unix'])
        require(len(group) <= 2, 'more than one recovery for a scientific cell')
        if group:
            require(not group[0]['terminal'].get('retry_of'), 'missing original attempt')
        if len(group) == 2:
            previous, later = (a['terminal'] for a in group)
            require(previous['outcome_valid'] is False and later['retry_of'] == previous['attempt_id']
                    and previous['n2_frozen_identity'] == later['n2_frozen_identity'], 'invalid replacement or recovery linkage')
            certificate = previous.get('n2_recovery_eligibility', {})
            infrastructure = previous['event'] == 'aborted' and previous.get('retryable_infrastructure') is True
            transport = (certificate.get('schema') == 'qd-ed-n2-recovery-eligibility-v1'
                and certificate.get('frozen_identity') == previous['n2_frozen_identity']
                and certificate.get('reason') == 'exact_codex_stage_transport_failure'
                and previous.get('reason') == certificate.get('gate') == 'Codex Stage call failure invalidates the frozen transport condition'
                and previous.get('compute_outcome') == 'completed' and previous.get('required_cost_telemetry_complete') is True
                and previous.get('stage_backend') == 'codex_cli' and previous.get('provider_failed_calls', 0) > 0
                and previous.get('stage_failed_queries', 0) > 0)
            require(infrastructure or transport, 'recovery lacks original infrastructure eligibility')
        valid = [a for a in group if a['status'] == 'complete_valid']
        require(len(valid) <= 1 and (not valid or valid[0] is group[-1]), 'valid scientific cell cannot be superseded')
        status = valid[0]['status'] if valid else group[-1]['status'] if group else 'missing'
        cells.append({'identity': {k:row[k] for k in IDENTITY}, 'status': status,
            'valid_attempt_id': valid[0]['terminal']['attempt_id'] if valid else None,
            'success': valid[0]['terminal']['success'] if valid else None,
            'attempts': group, 'metrics': valid[0].get('metrics') if valid else None})
    require(sum(len(c['attempts']) > 1 for c in cells) <= 4, 'cohort recovery allowance exceeded')
    profiles = {}
    for profile in PROFILES:
        current = [c for c in cells if c['identity']['profile'] == profile]
        valid = [c for c in current if c['status'] == 'complete_valid']
        raw_attempts = [a['terminal'] for c in current for a in c['attempts']]
        profiles[profile] = {'expected': 10, 'complete_valid': len(valid), 'successes_observed': sum(c['success'] for c in valid),
            'failures_observed': sum(not c['success'] for c in valid), 'statuses': dict(Counter(c['status'] for c in current)),
            'success_rate': sum(c['success'] for c in valid)/10 if len(valid) == 10 else None,
            'terminal_attempts': len(raw_attempts), 'all_attempt_gpu_seconds': observed([t.get('gpu_process_wall_seconds') for t in raw_attempts]),
            'all_attempt_cost_fields': {k:observed([t.get(k) for t in raw_attempts]) for k in COSTS},
            'valid_cell_cost_fields': {k:observed([next(a['terminal'] for a in c['attempts'] if a['status']=='complete_valid').get(k) for c in valid]) for k in COSTS},
            'stage_failed_queries_all_attempts': observed([t.get('stage_failed_queries') for t in raw_attempts])}
        observations = [c['metrics'] for c in valid]
        profiles[profile]['valid_cell_observation_summary'] = {
            'finite_executed_actions': all(m['finite_executed_actions'] for m in observations) if observations else None,
            'observer_wall_s': observed([m['observer_wall_s'] for m in observations]),
            'observer_bytes_written': observed([m['observer_bytes_written'] for m in observations]),
            'qd_active_chunks': sum(m['qd_active_chunks'] for m in observations) if observations else None}
        if profile == 'N2':
            records = [r for m in observations for r in m['n2']['records']]
            profiles[profile]['n2_quality_summary'] = {
                'valid_episodes_observed': len(valid), 'guided_chunks_observed': len(records),
                'applicable_chunks': sum(r['qd_quality_applicable'] for r in records) if observations else None,
                'inapplicable_chunks': sum(not r['qd_quality_applicable'] for r in records) if observations else None,
                'quality_changed_candidates': sum(r['qd_quality_changed_candidates'] for r in records) if observations else None,
                'reason_counts': dict(Counter(r['qd_quality_reason'] for r in records)),
                'raw_selected_minus_final_best': describe([r['qd_selected_raw_gap'] for r in records if r['qd_quality_applicable']]),
                'actual_normalized_stage_input_observed': False, 'substantive_selection_activation': 'Requires existing checkpoint review; not inferred from scalar changes.'}
    complete = all(c['status'] == 'complete_valid' for c in cells)
    comparisons = {}
    for control in ('C0', 'Q0'):
        comparisons['N2_vs_'+control] = {'complete_matched_10_tasks': complete, 'gained_tasks': None, 'lost_tasks': None, 'success_delta': None}
        if complete:
            lookup = {cellkey(c['identity']): c['success'] for c in cells}
            comparisons['N2_vs_'+control].update(
                gained_tasks=[t for t in range(10) if lookup[t,'N2'] and not lookup[t,control]],
                lost_tasks=[t for t in range(10) if not lookup[t,'N2'] and lookup[t,control]],
                success_delta=profiles['N2']['successes_observed']-profiles[control]['successes_observed'])
    numeric = (profiles['N2']['successes_observed'] >= 5 and all(profiles['N2']['successes_observed'] >= profiles[p]['successes_observed'] for p in ('C0','Q0'))) if complete else None
    return {'schema': 'qd-ed-n2-matrix-report-v1', 'cohort_id': COHORT, 'cells': cells, 'profiles': profiles,
        'matrix': 'complete_valid_30' if complete else 'incomplete', 'cell_status_counts': dict(Counter(c['status'] for c in cells)),
        'paired_comparisons': comparisons, 'protocol_numeric_dev_criterion': numeric,
        'first_three': {'cells': [{'profile':c['identity']['profile'],'status':c['status'],'attempt_id':c['valid_attempt_id']} for c in cells[:3]],
            'all_complete_valid': all(c['status']=='complete_valid' for c in cells[:3]), 'checkpoint_release': 'NOT_DETERMINED_BY_THIS_REPORT'},
        'stage_http_requests': None, 'stage_http_retries': None,
        'cost_scope': 'Explicit supplied episode terminals, including invalid/recovered attempts. No global ledger total or health-resource cost is inferred.',
        'pairing_scope': 'Only this frozen 30-cell matrix; missing/invalid are never failures or a smaller denominator.',
        'phase_authorized': False, 'scientific_promotion': 'Requires existing protocol correctness/activation review in addition to numeric criterion.'}


def load_attempt(spec, plans):
    terminal = read_ref(spec['terminal'])
    require(terminal['plan_sha256'] in plans, 'terminal uses unlisted plan')
    plan = plans[terminal['plan_sha256']]
    validate_terminal(terminal, plan, terminal['plan_sha256'])
    output = Path(terminal['output_dir']).resolve()
    require(Path(spec['terminal']['path']).resolve() == output/'attempt-result.json', 'terminal location differs')
    # Preserve exact original public result without copying command/configuration objects.
    preserved = {k:terminal[k] for k in ('attempt_id','episode_key','identity','event','success','outcome_valid','task_failure',
        'failure_class','reason','retryable_infrastructure','retry_of','time_unix','gpu_process_wall_seconds','output_dir',
        'n2_frozen_identity','n2_recovery_eligibility','required_cost_telemetry_complete','compute_outcome',
        'stage_backend','stage_model','stage_condition','stage_failed_queries','stage_successful_queries','stage_query_events',
        'provider_token_usage_complete',*COSTS) if k in terminal}
    result = {'terminal':preserved, 'references':spec, 'status':'terminal_invalid'}
    if not (terminal['event'] == 'valid' and terminal['outcome_valid'] is True):
        require(set(spec) == {'terminal'}, 'invalid attempt must supply terminal only; no audit/metric reads')
        return result
    result['status'] = 'pending_or_rejected_audit'
    if 'audit' not in spec:
        require(set(spec) == {'terminal'}, 'no data reads before audit reference')
        return result
    require(Path(spec['audit']['path']).resolve() == output/'eds_eval/decision-evidence-audit.json', 'audit location differs')
    audit = read_ref(spec['audit'])
    result['audit_acceptance'] = {k:audit.get(k) for k in ('accepted','evidence_complete','original_execution_outcome','errors')}
    if not (audit.get('accepted') is True and audit.get('evidence_complete') is True):
        require(set(spec) == {'terminal','audit'}, 'rejected audit must not supply metric data')
        return result
    require(set(spec) == {'terminal','audit','compute','metrics'}, 'valid attempt needs explicit compute/metrics refs')
    compute_path = output/'eds_eval/episode_compute.jsonl'
    require(Path(spec['compute']['path']).resolve() == compute_path and Path(spec['metrics']['path']).resolve() == output/'eds_eval/eds_metrics.jsonl'
        and audit['episode_dir'] == str(output/'eds_eval/decision_evidence/episode_000')
        and audit['episode_compute_file'] == str(compute_path) and audit['original_execution_outcome'] == 'completed', 'accepted evidence linkage differs')
    compute_rows = read_ref(spec['compute'], lines=True)
    require(len(compute_rows) == 1, 'one compute row required')
    compute = compute_rows[0]
    require(compute['episode_id'] == 0 and compute['task_id'] == terminal['identity']['task_id']
        and compute['episode_seed'] == terminal['identity']['env_seed'] and compute['outcome'] == 'completed'
        and terminal['compute_outcome'] == 'completed' and terminal['required_cost_telemetry_complete'] is True
        and terminal['stage_backend'] == 'codex_cli' and terminal['stage_condition'] == 'codex_login_astra_low_v1'
        and terminal['provider_token_usage_complete'] is True and terminal['provider_failed_calls'] == 0
        and terminal['stage_failed_queries'] == 0 and audit.get('errors') == [], 'valid condition/compute/Stage gate differs')
    for field in COSTS:
        if field in HTTP:
            require(field in terminal and terminal[field] is None and compute.get(field) is None, 'HTTP counts must remain Unknown')
        elif field not in {'candidate_evaluations','score_batches'}:
            require(field in terminal and field in compute and terminal[field] == compute[field]
                and (field == 'provider_reasoning_output_tokens' and terminal[field] is None
                     or finite(terminal[field]) and terminal[field] >= 0
                     and (field == 'provider_call_latency_s' or type(terminal[field]) is int)),
                'compute/terminal counter differs: '+field)
    result.update(status='complete_valid', metrics=summarize_metrics(read_ref(spec['metrics'], lines=True), terminal, audit, compute))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--execute-reviewed', action='store_true'); args = p.parse_args()
    require(args.execute_reviewed and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'explicit review and empty CUDA mask required')
    manifest = parse(args.manifest.read_text()); script = Path(__file__).resolve()
    require(manifest['schema'] == 'qd-ed-n2-report-input-v1' and manifest['script_sha256'] == sha(script)
            and manifest['protocol_sha256'] == sha(script.with_name('protocol.md')), 'report freeze differs')
    auth = read_ref(manifest['authorization'])
    # Authorization binds input plan and immutable report definition. Snapshot manifests may add only named terminals.
    require(auth['script'] == {'path':str(script),'sha256':sha(script)} and auth['protocol_sha256'] == manifest['protocol_sha256']
            and auth['base_plan_sha256'] == BASE_PLAN_SHA, 'report execution authorization differs')
    require(manifest['base_plan']['sha256'] == BASE_PLAN_SHA, 'different study/old observation plan')
    base = read_ref(manifest['base_plan']); originals = plan_contract(base)
    plans = {BASE_PLAN_SHA:base}
    for reference in manifest.get('plan_revisions', []):
        plan = read_ref(reference)
        require(plan_contract(plan) == originals and all(plan[k] == base[k] for k in BINDING)
                and plan['candidate_profiles'] == base['candidate_profiles']
                and all(plan['n2_cohort'][k] == base['n2_cohort'][k] for k in ('protocol','accounting_clarification')),
                'revision changes scientific/source condition')
        plans[reference['sha256']] = plan
    attempts = [load_attempt(spec, plans) for spec in manifest['attempts']]
    report = summarize(base, attempts)
    report.update(input_manifest=manifest, input_manifest_sha256=sha(args.manifest), input_scope_complete=manifest.get('input_scope_complete') is True,
        input_scope_note='Completeness of the named terminal inventory is a root assertion, not inferred by scanning live attempts.')
    for spec in manifest['attempts']:
        for reference in spec.values():
            require(sha(reference['path']) == reference['sha256'], 'input changed while reporting')
    destination = args.output.resolve()
    require(not destination.exists() and destination.suffix == '.json'
        and destination.is_relative_to(Path(base['artifact_root']).resolve()/'continuation_20260923')
        and all(not destination.is_relative_to(Path(a['terminal']['output_dir']).resolve()) for a in attempts),
        'new separate artifact JSON output required')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({'matrix':report['matrix'],'cells':report['cell_status_counts'],'output':str(args.output)}))


if __name__ == '__main__':
    main()
