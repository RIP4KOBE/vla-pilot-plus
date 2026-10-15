#!/usr/bin/env python3
"""Prospective stdlib-only N4 report. Explicit SHA-bound JSON inputs; no bundles.

Reports evidence, not phase authorization. Invalid attempts retain their costs.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path

COHORT = 'N4_TERMINAL_POPULATION_DEV_20260924'
ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT/'experiments/iteration_004_terminal_population/protocol.md'
PROFILES = ('C0', 'Q0', 'N4')
TASKS = (0,3,6,9)
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
    from qd_ed_n4_plan import LIMITS, ALLOCATION, BUDGET_ALLOCATION, FROZEN_DOCS, original_bucket, PREREQUISITE_REVIEW_SHA256, SHARED_RESOURCE_SHA256
    require(plan['n4_cohort']['cohort_id'] == COHORT and plan['n4_cohort']['limits'] == LIMITS
        and set(plan['candidate_profiles']) == {'N4'}
        and plan['n4_cohort']['protocol']['sha256'] == sha(PROTOCOL), 'wrong cohort/protocol/limits')
    require(plan['n4_cohort'].get('budget_allocation')==BUDGET_ALLOCATION
        and plan['n4_cohort'].get('budget_allocation_amendment')=={'path':ALLOCATION,'sha256':sha(ROOT/ALLOCATION)}
        and any(x=={'path':ALLOCATION,'sha256':sha(ROOT/ALLOCATION)} for x in plan['code_files']),
        'N4 prospective budget allocation/amendment differs')
    paths={x['path']:x['sha256'] for x in plan['code_files']}
    require(all(paths.get(p)==digest and sha(ROOT/p)==digest for p,digest in FROZEN_DOCS.items()), 'N4 document identity differs')
    require(plan['n4_cohort']['prerequisite_review']['sha256']==PREREQUISITE_REVIEW_SHA256
        and plan['n4_cohort']['shared_resource_contract']['sha256']==SHARED_RESOURCE_SHA256, 'N4 authority/prerequisite identity differs')
    rows = [r for r in plan['episodes'] if not r.get('retry_of')]
    require([cellkey(r) for r in rows] == [(task, p) for task in TASKS for p in PROFILES], 'original 12-cell order differs')
    require(len({r['episode_key'] for r in plan['episodes']}) == len(plan['episodes']), 'duplicate planned episode key')
    for task in TASKS:
        group = [r for r in rows if r['task_id'] == task]
        require(len({tuple(r[k] for k in ('env_seed', 'policy_seed', 'init_index', 'init_row_sha256')) for r in group}) == 1,
                'matched task seed/init differs')
    for row in rows:
        require(row['split'] == 'dev' and row['iteration'] == COHORT, 'non-Dev cell')
        require(row['budget_bucket']==original_bucket(row['task_id'],row['profile']), 'N4 original arm budget bucket differs')
    recoveries = [r for r in plan['episodes'] if r.get('retry_of')]
    require(len(recoveries) <= 4 and len({cellkey(r) for r in recoveries}) == len(recoveries), 'recovery allowance differs')
    by_cell = {cellkey(r): r for r in rows}
    for row in recoveries:
        require(row['budget_bucket']==BUDGET_ALLOCATION['retry_bucket'],'N4 retry budget bucket differs')
        require(cellkey(row) in by_cell, 'recovery scientific cell missing')
        actual={k:v for k,v in row.items() if k not in {'episode_key','retry_of','n4_recovery_contract','budget_bucket'}}
        original={k:v for k,v in by_cell[cellkey(row)].items() if k not in {'episode_key','budget_bucket'}}
        require(actual==original and row['episode_key']!=by_cell[cellkey(row)]['episode_key'], 'recovery scientific identity differs')
    return rows


def validate_record_identity(terminal, plan, plan_sha):
    require(terminal['plan_sha256'] == plan_sha, 'unbound journal record')
    row = next((r for r in plan['episodes'] if r['episode_key'] == terminal['episode_key']), None)
    require(row is not None and terminal['identity'] == {k: row[k] for k in IDENTITY}, 'unplanned terminal identity')
    require(terminal['physical_gpu'] == 3 and terminal['source_commit'] == plan['source_commit']
        and terminal['profile_manifest_sha256'] == plan['profiles_sha256']
        and terminal['runtime_manifest_sha256'] == plan['runtime_manifest_sha256']
        and terminal['runtime_inventory_sha256'] == plan['runtime_inventory_sha256']
        and terminal['init_row_sha256'] == row['init_row_sha256']
        and terminal['budget_bucket'] == row['budget_bucket']
        and terminal.get('retry_of') == row.get('retry_of'), 'terminal frozen condition differs')
    binding = terminal.get('n4_frozen_identity', {})
    require(terminal.get('n4_cohort_id') == COHORT and binding.get('cohort_id') == COHORT
        and all(binding.get(k) == plan[k] for k in BINDING)
        and binding.get('protocol_sha256') == plan['n4_cohort']['protocol']['sha256']
        and binding.get('accounting_clarification_sha256') == plan['n4_cohort']['accounting_clarification']['sha256']
        and binding.get('source_files_sha256') == hashlib.sha256(json.dumps(plan['code_files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        and binding.get('resource_contract_sha256') == hashlib.sha256(json.dumps({k:plan['n4_cohort'][k] for k in
            ('limits','health_resources','runtime_prerequisites','budget_allocation','budget_allocation_amendment','prerequisite_protocol','prerequisite_review','shared_resource_contract','shared_resource_pointer')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        and binding.get('candidate_sha256') == plan['candidate_profiles']['N4']['sha256'], 'N4 binding differs')
    return row


def validate_terminal(terminal,plan,plan_sha):
    row=validate_record_identity(terminal,plan,plan_sha)
    require(terminal['event'] in {'valid','aborted'},'nonterminal record')
    require(type(terminal.get('success')) is bool and type(terminal.get('outcome_valid')) is bool
        and type(terminal.get('n4_episode_dispatched')) is bool, 'raw outcome/dispatch status missing')
    if not terminal['n4_episode_dispatched']:
        require(terminal['event']=='aborted' and terminal['outcome_valid'] is False and terminal['gpu_process_wall_seconds']==0,
            'predispatch terminal cannot claim scientific completion or GPU cost')
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
        'observer_bytes_written': compute.get('decision_evidence', {}).get('bytes_written'), 'n4': None}
    require(all(m.get('qd_quality_mode','provider')=='provider' for m in metrics), 'N4/control raw-provider quality mode differs')
    if profile != 'N4':
        require(all(m.get('qd_final_selection_mode','archive_global_best')=='archive_global_best'
            and 'qd_terminal_population' not in m and 'qd_archive_reference' not in m for m in metrics),
            'control consumer mode differs')
        return result
    require(steps==sorted(steps),'N4 guided decision order differs')
    for metric in metrics:
        require(metric.get('qd_final_selection_mode')=='terminal_population_v1'
            and isinstance(metric.get('qd_terminal_population'),dict)
            and isinstance(metric.get('qd_archive_reference'),dict), 'N4 consumer metrics missing')
    from qd_ed_n4_plan import native_audit_alignment
    alignment=native_audit_alignment(audit,metrics,require=require)
    result['n4']={'native_terminal_population_alignment':alignment,
        'actual_prefix_different_decisions':alignment['actual_prefix_different_decisions'],
        'records':[{k:m.get(k) for k in ('global_step','selected_reward','qd_final_selection_mode',
                    'qd_terminal_population','qd_archive_reference')} for m in metrics],
        'evidence':'Accepted native bundle audit, exact guided decision/count alignment; prefix difference is not task benefit.',
        'target_distance_after':'Unknown for selected; archive-reference distance is a separate diagnostic, never zero-imputed'}
    return result


def summarize(plan, attempts, inflight=()):
    rows = plan_contract(plan)
    grouped = defaultdict(list)
    require(len({a['terminal']['attempt_id'] for a in attempts}) == len(attempts), 'duplicate input attempt')
    dispatched=[a for a in attempts if a['terminal']['n4_episode_dispatched']]
    predispatch=[a for a in attempts if not a['terminal']['n4_episode_dispatched']]
    require(len(dispatched)+sum(a['dispatched'] for a in inflight)<=16,'excess dispatched episodes')
    for attempt in dispatched:
        grouped[cellkey(attempt['terminal']['identity'])].append(attempt)
    bindings = {json.dumps(a['terminal']['n4_frozen_identity'], sort_keys=True) for a in attempts}
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
                    and previous['n4_frozen_identity'] == later['n4_frozen_identity'], 'invalid replacement or recovery linkage')
            from qd_ed_n4_plan import recoverable
            require(recoverable(previous,previous['n4_frozen_identity']),
                    'recovery lacks exact prospective infrastructure eligibility')
        active=[a for a in inflight if cellkey(a['identity'])==cellkey(row)]
        require(len(active)<=1 and len(group)+sum(a['dispatched'] for a in active)<=2,'excess concurrent/recovery dispatches for cell')
        valid = [a for a in group if a['status'] == 'complete_valid']
        require(not (valid and active),'inflight attempt cannot supersede valid cell')
        if active and group:
            from qd_ed_n4_plan import recoverable
            require(len(group)==1 and active[0]['retry_of']==group[0]['terminal']['attempt_id']
                and recoverable(group[0]['terminal'],active[0]['n4_frozen_identity']), 'inflight recovery predecessor ineligible')
        elif active:
            require(not active[0]['retry_of'],'inflight retry lacks dispatched original')
        require(len(valid) <= 1 and (not valid or valid[0] is group[-1]), 'valid scientific cell cannot be superseded')
        status = ('inflight_dispatched' if active[0]['dispatched'] else 'reserved_no_dispatch') if active else valid[0]['status'] if valid else group[-1]['status'] if group else 'missing'
        cells.append({'identity': {k:row[k] for k in IDENTITY}, 'status': status,
            'valid_attempt_id': valid[0]['terminal']['attempt_id'] if valid else None,
            'success': valid[0]['terminal']['success'] if valid else None,
            'attempts': group, 'inflight':active,'metrics': valid[0].get('metrics') if valid else None})
    require(sum(len(c['attempts']) > 1 for c in cells) <= 4, 'cohort recovery allowance exceeded')
    profiles = {}
    for profile in PROFILES:
        current = [c for c in cells if c['identity']['profile'] == profile]
        valid = [c for c in current if c['status'] == 'complete_valid']
        raw_attempts = [a['terminal'] for c in current for a in c['attempts']]
        profiles[profile] = {'expected': 4, 'complete_valid': len(valid), 'successes_observed': sum(c['success'] for c in valid),
            'failures_observed': sum(not c['success'] for c in valid), 'statuses': dict(Counter(c['status'] for c in current)),
            'success_rate': sum(c['success'] for c in valid)/4 if len(valid) == 4 else None,
            'terminal_attempts': len(raw_attempts), 'all_attempt_gpu_seconds': observed([t.get('gpu_process_wall_seconds') for t in raw_attempts]+
                [None for a in inflight if a['identity']['profile']==profile]),
            'all_attempt_cost_fields': {k:observed([t.get(k) for t in raw_attempts]+[None for a in inflight if a['identity']['profile']==profile]) for k in COSTS},
            'valid_cell_cost_fields': {k:observed([next(a['terminal'] for a in c['attempts'] if a['status']=='complete_valid').get(k) for c in valid]) for k in COSTS},
            'stage_failed_queries_all_attempts': observed([t.get('stage_failed_queries') for t in raw_attempts])}
        observations = [c['metrics'] for c in valid]
        profiles[profile]['valid_cell_observation_summary'] = {
            'finite_executed_actions': all(m['finite_executed_actions'] for m in observations) if observations else None,
            'observer_wall_s': observed([m['observer_wall_s'] for m in observations]),
            'observer_bytes_written': observed([m['observer_bytes_written'] for m in observations]),
            'qd_active_chunks': sum(m['qd_active_chunks'] for m in observations) if observations else None}
        if profile == 'N4':
            summaries=[m['n4'] for m in observations]
            profiles[profile]['n4_consumer_summary']={
                'valid_episodes_observed':len(valid),
                'guided_decisions_checked':sum(m['native_terminal_population_alignment']['checked_decisions'] for m in summaries),
                'actual_prefix_different_decisions':sum(m['actual_prefix_different_decisions'] for m in summaries),
                'difference_scope':'Selected vs simultaneously stored archive reference over actual sent prefix; no counterfactual success claim'}
    complete = all(c['status'] == 'complete_valid' for c in cells)
    comparisons = {}
    for control in ('C0', 'Q0'):
        comparisons['N4_vs_'+control] = {'complete_matched_4_tasks': complete, 'gained_tasks': None, 'lost_tasks': None, 'success_delta': None}
        if complete:
            lookup = {cellkey(c['identity']): c['success'] for c in cells}
            comparisons['N4_vs_'+control].update(
                gained_tasks=[t for t in TASKS if lookup[t,'N4'] and not lookup[t,control]],
                lost_tasks=[t for t in TASKS if not lookup[t,'N4'] and lookup[t,control]],
                success_delta=profiles['N4']['successes_observed']-profiles[control]['successes_observed'])
    numeric = (profiles['N4']['successes_observed'] >= 2 and all(profiles['N4']['successes_observed'] >= profiles[p]['successes_observed'] for p in ('C0','Q0'))) if complete else None
    return {'schema': 'qd-ed-n4-matrix-report-v1', 'cohort_id': COHORT, 'cells': cells, 'profiles': profiles,
        'predispatch_records':predispatch,'terminal_records':len(attempts),
        'inflight_records':list(inflight),'episode_dispatches':len(dispatched)+sum(a['dispatched'] for a in inflight),
        'predispatch_gpu_seconds':observed([a['terminal']['gpu_process_wall_seconds'] for a in predispatch]),
        'matrix': 'complete_valid_12' if complete else 'incomplete', 'cell_status_counts': dict(Counter(c['status'] for c in cells)),
        'paired_comparisons': comparisons, 'protocol_numeric_dev_criterion': numeric,
        'protocol_execution_activity_criterion':(profiles['N4']['n4_consumer_summary']['actual_prefix_different_decisions']>0) if complete else None,
        'first_three': {'cells': [{'profile':c['identity']['profile'],'status':c['status'],'attempt_id':c['valid_attempt_id']} for c in cells[:3]],
            'all_complete_valid': all(c['status']=='complete_valid' for c in cells[:3]), 'checkpoint_release': 'NOT_DETERMINED_BY_THIS_REPORT'},
        'stage_http_requests': None, 'stage_http_retries': None,
        'cost_scope': 'Explicit supplied episode terminals, including invalid/recovered attempts. No global ledger total or health-resource cost is inferred.',
        'pairing_scope': 'Only this frozen 12-cell matrix; missing/invalid are never failures or a smaller denominator.',
        'phase_authorized': False, 'scientific_promotion': 'Requires full native correctness, archive-parent use and actual-prefix difference gate plus numeric criterion; this report never authorizes a phase.'}


def load_attempt(spec, plans):
    terminal = read_ref(spec['terminal'])
    require(terminal['plan_sha256'] in plans, 'terminal uses unlisted plan')
    plan = plans[terminal['plan_sha256']]
    validate_terminal(terminal, plan, terminal['plan_sha256'])
    output = Path(terminal['output_dir']).resolve()
    require(Path(spec['terminal']['path']).resolve() == output/'attempt-result.json', 'terminal location differs')
    # Preserve exact original public result without copying command/configuration objects.
    preserved = {k:terminal[k] for k in ('attempt_id','episode_key','identity','event','success','outcome_valid','task_failure',
        'failure_class','reason','retryable_infrastructure','retry_of','time_unix','gpu_process_wall_seconds','output_dir','budget_bucket',
        'n4_frozen_identity','n4_recovery_eligibility','n4_episode_dispatched','failure_detail','gpu_monitor_timeout','required_cost_telemetry_complete','compute_outcome',
        'stage_backend','stage_model','stage_condition','stage_failed_queries','stage_successful_queries','stage_query_events',
        'provider_token_usage_complete',*COSTS) if k in terminal}
    result = {'terminal':preserved, 'references':spec, 'status':'terminal_invalid'}
    if not terminal['n4_episode_dispatched']:
        require(set(spec)=={'terminal'},'predispatch record must supply terminal only')
        result['status']='predispatch_rejected'
        return result
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


def validate_journal_excerpt(excerpt,specs,plans,base):
    """Root-authorized exact N4 extraction, including every rejected reservation.

    The immutable source-journal SHA and extraction assertion are root provenance;
    this reader never opens external cohorts' scientific journal payloads.
    """
    source=excerpt.get('source_journal',{})
    require(excerpt.get('schema')=='qd-ed-n4-journal-excerpt-v1' and excerpt.get('cohort_id')==COHORT
        and excerpt.get('extraction')=='all_events_all_n4_attempts_through_snapshot'
        and Path(source.get('path','')).resolve()==(Path(base['worktree'])/'data/attempt-ledger.jsonl').resolve()
        and isinstance(source.get('sha256'),str) and len(source['sha256'])==64,
        'N4 complete journal extraction provenance missing')
    groups=defaultdict(list)
    for event in excerpt['events']:
        require(event.get('n4_cohort_id')==COHORT and event.get('identity',{}).get('iteration')==COHORT,
            'journal excerpt contains another cohort')
        groups[event['attempt_id']].append(event)
    terminal_ids=[];inflight=[]
    for identifier,events in groups.items():
        require([e['event'] for e in events] in (['reserved','dispatched','valid'],['reserved','dispatched','aborted'],['reserved','aborted'],['reserved'],['reserved','dispatched']),
            'N4 journal events incomplete/duplicate/out of order')
        final=events[-1]
        require(all(e.get(k)==final.get(k) for e in events for k in
            ('attempt_id','identity','episode_key','plan_sha256','n4_frozen_identity','retry_of','output_dir','budget_bucket')),
            'N4 journal identity changed within attempt')
        if final['event'] in {'reserved','dispatched'}:
            require(final['plan_sha256'] in plans,'inflight attempt uses undeclared frozen plan')
            validate_record_identity(final,plans[final['plan_sha256']],final['plan_sha256'])
            inflight.append({**{k:final.get(k) for k in ('attempt_id','identity','episode_key','plan_sha256','retry_of',
                'budget_bucket','n4_frozen_identity','output_dir')},'last_event':final['event'],
                'dispatched':any(e['event']=='dispatched' for e in events),'gpu_process_wall_seconds':None})
            continue
        require(type(final.get('n4_episode_dispatched')) is bool
            and final['n4_episode_dispatched']==any(e['event']=='dispatched' for e in events),
            'terminal dispatch bool disagrees with actual journal presence')
        require(final['plan_sha256'] in plans,'journal terminal uses undeclared frozen plan')
        validate_terminal(final,plans[final['plan_sha256']],final['plan_sha256'])
        terminal_ids.append(identifier)
    require(excerpt.get('inflight_attempt_ids')==[a['attempt_id'] for a in inflight],'N4 inflight inventory differs')
    require(excerpt.get('terminal_attempt_ids')==terminal_ids,'N4 journal complete terminal ID inventory differs')
    terminals=[read_ref(spec['terminal']) for spec in specs]
    require(len(terminals)==len(terminal_ids) and {t['attempt_id'] for t in terminals}==set(terminal_ids),
            'report omitted/repeated an N4 invalid, predispatched or valid terminal')
    require(all(t==groups[t['attempt_id']][-1] for t in terminals),'report terminal differs from actual journal terminal')
    return inflight


def resource_costs(plan,references,attempts,inflight=()):
    declared=plan['n4_cohort']['health_resources']
    require([{'resource_id':x['resource_id'],'scope':x['scope']} for x in references]==declared,
            'all frozen health references required in declaration order')
    rows=[]
    for reference in references:
        terminal=read_ref(reference['terminal'])
        require(terminal.get('resource_id')==reference['resource_id'] and terminal.get('event') in {'completed','aborted'}
            and finite(terminal.get('gpu_process_wall_seconds')) and terminal['gpu_process_wall_seconds']>=0,
            'health cost evidence incomplete')
        rows.append({**reference,'gpu_process_wall_seconds':terminal['gpu_process_wall_seconds']})
    episode_seconds=sum(a['terminal']['gpu_process_wall_seconds'] for a in attempts)
    new_seconds=sum(x['gpu_process_wall_seconds'] for x in rows if x['scope']=='new_n4')
    return {'episode_dispatches_observed':sum(a['terminal']['n4_episode_dispatched'] for a in attempts)+sum(a['dispatched'] for a in inflight),'episode_seconds':episode_seconds,
        'new_health_seconds':new_seconds,'new_cohort_seconds':None if inflight else episode_seconds+new_seconds,
        'new_cohort_seconds_observed_subtotal':episode_seconds+new_seconds,'inflight_costs_settled':not bool(inflight),
        'within_local_8_5_hours':None if inflight else episode_seconds+new_seconds<=8.5*3600,
        'reused_prior_health_seconds_not_recharged':sum(x['gpu_process_wall_seconds'] for x in rows if x['scope']=='reused_prior'),
        'health_evidence':rows,'global_budget_status':'not inferred; authoritative runner journal admission remains required'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--execute-reviewed', action='store_true'); args = p.parse_args()
    require(args.execute_reviewed and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'explicit review and empty CUDA mask required')
    manifest = parse(args.manifest.read_text()); script = Path(__file__).resolve()
    require(manifest['schema'] == 'qd-ed-n4-report-input-v1' and manifest['script_sha256'] == sha(script)
            and manifest['protocol_sha256'] == sha(PROTOCOL), 'report freeze differs')
    auth = read_ref(manifest['authorization'])
    # Authorization binds input plan and immutable report definition. Snapshot manifests may add only named terminals.
    require(auth['script'] == {'path':str(script),'sha256':sha(script)} and auth['protocol_sha256'] == manifest['protocol_sha256']
            and auth['base_plan_sha256'] == manifest['base_plan']['sha256']
            and auth.get('schema') == 'qd-ed-n4-report-authorization-v1' and auth.get('status') == 'authorized', 'report execution authorization differs')
    base = read_ref(manifest['base_plan']); originals = plan_contract(base)
    code={entry['path']:entry['sha256'] for entry in base['code_files']}
    require(code.get('scripts/qd_ed_n4_report.py')==sha(script)
        and code.get('scripts/qd_ed_n4_plan.py')==sha(script.with_name('qd_ed_n4_plan.py')),
        'report/contract source not frozen into this matrix')
    plans = {manifest['base_plan']['sha256']:base}
    for reference in manifest.get('plan_revisions', []):
        plan = read_ref(reference)
        require(plan_contract(plan) == originals and all(plan[k] == base[k] for k in BINDING)
                and plan['candidate_profiles'] == base['candidate_profiles']
                and plan['code_files'] == base['code_files']
                and plan['n4_cohort']['limits'] == base['n4_cohort']['limits']
                and plan['n4_cohort']['runtime_prerequisites'] == base['n4_cohort']['runtime_prerequisites']
                and plan['n4_cohort']['health_resources'] == base['n4_cohort']['health_resources']
                and all(plan['n4_cohort'][k] == base['n4_cohort'][k] for k in ('protocol','accounting_clarification','budget_allocation','budget_allocation_amendment','prerequisite_protocol','prerequisite_review','shared_resource_contract','shared_resource_pointer')),
                'revision changes scientific/source condition')
        plans[reference['sha256']] = plan
    require(auth.get('journal_excerpt_sha256')==manifest['journal_excerpt']['sha256'],'journal extraction authorization differs')
    journal_excerpt=read_ref(manifest['journal_excerpt'])
    inflight=validate_journal_excerpt(journal_excerpt,manifest['attempts'],plans,base)
    require(not inflight or manifest.get('input_scope_complete') is False,'inflight snapshot cannot claim complete cost/outcome scope')
    attempts = [load_attempt(spec, plans) for spec in manifest['attempts']]
    report = summarize(base, attempts,inflight)
    report['resources']=resource_costs(base,manifest.get('health_resources',[]),attempts,inflight)
    report.update(input_manifest=manifest, input_manifest_sha256=sha(args.manifest), input_scope_complete=manifest.get('input_scope_complete') is True,
        input_scope_note='Completeness of the named terminal inventory is a root assertion, not inferred by scanning live attempts.')
    references=[manifest['authorization'],manifest['base_plan'],manifest['journal_excerpt'],
                *manifest.get('plan_revisions',[]),*[x['terminal'] for x in manifest.get('health_resources',[])]]
    references += [ref for spec in manifest['attempts'] for ref in spec.values()]
    for reference in references:
        require(sha(reference['path'])==reference['sha256'],'input changed while reporting')
    require(sha(args.manifest)==report['input_manifest_sha256'],'input manifest changed while reporting')
    destination = args.output.resolve()
    require(not destination.exists() and destination.suffix == '.json'
        and destination.is_relative_to(Path(base['artifact_root']).resolve()/'continuation_20260923')
        and all(not destination.is_relative_to(Path(a['terminal']['output_dir']).resolve()) for a in attempts),
        'new separate artifact JSON output required')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({'matrix':report['matrix'],'cells':report['cell_status_counts'],'output':str(args.output)}))


if __name__ == '__main__':
    main()
