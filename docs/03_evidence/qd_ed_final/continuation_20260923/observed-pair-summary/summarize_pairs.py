#!/usr/bin/env python3
"""Stdlib-only descriptive summary of four explicitly named completed episodes.

Never opens a tensor bundle, ledger, process, model, provider, or simulator.
Missing manifest rows stay pending; no directory scan or implicit latest input.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

EXPECTED_PLAN_SHA = 'ac123471db9fa9468661238982b3bdb5cb1a68010ec8261e0e5b12239c57e7e8'
ANALYZER = 'docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/analyze_episode.py'
AUDITOR = 'scripts/audit_decision_evidence.py'
TARGET_MAP = 'docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/provider-target-review/static-output/provider-target-map-v2.json'
ORDER = [(0, 'C0', 1969522881), (0, 'Q0', 1969522881), (5, 'C0', 970869399), (5, 'Q0', 970869399)]
KEYS = [f'observed_pairs_t{task:02d}_{arm.lower()}_20260923' for task, arm, _ in ORDER]
IDENTITY_FIELDS = ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')
COST_FIELDS = ('gpu_process_wall_seconds', 'model_forward_calls', 'model_batch_rows',
    'reward_evaluations', 'reward_scoring_batches', 'guided_chunks', 'unguided_chunks',
    'vision_encoder_forward_calls', 'text_encoder_forward_calls', 'dino_forward_calls',
    'provider_logical_call_attempts', 'provider_completed_turns', 'provider_failed_calls',
    'provider_usage_complete_calls', 'provider_input_tokens', 'provider_cached_input_tokens',
    'provider_output_tokens', 'provider_call_latency_s', 'provider_request_attempts',
    'provider_sdk_retry_attempts')
LIMIT = ('Four planned episodes across two paired tasks do not establish improved success rate or causal effect. '
         'Decisions/chunks are correlated within an episode, not independent samples. '
         'No p-values, automatic promotion, unexecuted outcome labels, or pooling with observer=false/external GPU2.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_reference(reference, root=None):
    require(set(reference) == {'path', 'sha256'}, 'reference requires only path and sha256')
    path = Path(reference['path']).resolve()
    if root is not None:
        require(path.is_relative_to(Path(root).resolve()), 'reference escapes frozen artifact root')
    require(path.suffix == '.json', 'only explicit JSON documents may be consumed')
    data = path.read_bytes()
    require(digest(data) == reference['sha256'], 'input SHA mismatch: ' + str(path))
    def bad_constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(data, parse_constant=bad_constant), path


def check_plan(plan, plan_sha):
    require(plan_sha == EXPECTED_PLAN_SHA, 'not the preregistered observed-pair plan')
    require(plan.get('schema') == 'qd-ed-final-plan-v1' and plan.get('frozen') is True, 'frozen runner plan required')
    require(plan['phase_authorization'] == {'dev': True, 'validation': False, 'formal': False}, 'dev-only plan required')
    require(plan.get('observational_overrides') == {'main.decision_evidence.enabled': True}, 'observer condition differs')
    rows = plan['episodes']
    require(len(rows) == 4 and [row['episode_key'] for row in rows] == KEYS, 'fixed four rows/order differ')
    for row, (task, arm, seed) in zip(rows, ORDER):
        expected = {'task_id': task, 'profile': arm, 'env_seed': seed, 'policy_seed': seed,
            'split': 'dev', 'seed_block': 'dev', 'init_index': 0, 'budget_bucket': 'development',
            'iteration': 'OBSERVED_PAIRS_DEV_20260923', 'timeout_seconds': 1800}
        require(all(row.get(key) == value for key, value in expected.items()) and not row.get('retry_of'),
                'planned row identity differs')
    sources = {item['path']: item['sha256'] for item in plan['code_files']}
    require(ANALYZER in sources and AUDITOR in sources and TARGET_MAP in sources,
            'frozen analyzer/auditor/target-map source missing')
    return sources


def presence(eligible, ids):
    return {'eligible_decisions': len(eligible), 'witness_decision_ids': ids,
            'episode_presence': 'present' if ids else 'not_observed_among_eligible' if eligible else 'Unknown'}


def decision_summary(decisions):
    ids = [row['decision_id'] for row in decisions]
    require(len(ids) == len(set(ids)) and bool(ids), 'missing or duplicate decision identifiers')
    require(all(type(row['hypothesis_eligible']) is bool for row in decisions), 'eligibility must be explicit')
    eligible = [row for row in decisions if row['hypothesis_eligible']]
    full = []
    for row in eligible:
        diag = row['diagnostics']
        require(isinstance(diag, dict) and type(diag['projection_optimism_witness']) is bool,
                'eligible decision lacks original B witness')
        if diag['step7_to8'] is not None:
            require(type(diag['step7_to8']['both_regress_robust']) is bool, 'eligible full prefix lacks original A witness')
            full.append(row)
    a_ids = [row['decision_id'] for row in full if row['diagnostics']['step7_to8']['both_regress_robust']]
    b_ids = [row['decision_id'] for row in eligible if row['diagnostics']['projection_optimism_witness']]
    return {'decision_count_descriptive_only': len(decisions), 'hypothesis_eligible_decisions': len(eligible),
        'hypothesis_ineligible_decisions': len(decisions)-len(eligible),
        'unknown_reasons': dict(Counter(reason for row in decisions for reason in row['unknown_reasons'])),
        'ineligible_reasons': dict(Counter(reason for row in decisions for reason in row['hypothesis_ineligible_reasons'])),
        'A_unscored_tail': presence(full, a_ids), 'B_projection_response': presence(eligible, b_ids),
        'A_B_overlap_decision_ids': [value for value in a_ids if value in set(b_ids)],
        'overlap_limit': 'Overlapping witnesses are not independent mechanisms or samples; no automatic ranking.'}


def stratum_key(row):
    return json.dumps({key: row[key] for key in ('stage', 'guidance', 'provider_identities')}, sort_keys=True, allow_nan=False)


def summarize_strata(analysis):
    grouped = defaultdict(list)
    for row in analysis['decisions']:
        grouped[stratum_key(row)].append(row)
    saved = {stratum_key(row): row for row in analysis['strata']}
    require(len(saved) == len(analysis['strata']) and set(saved) == set(grouped), 'analyzer strata differ from decisions')
    result = []
    for key, rows in grouped.items():
        summary = decision_summary(rows)
        original = saved[key]
        require(original['decisions'] == len(rows) and
                original['hypothesis_eligible_decisions'] == summary['hypothesis_eligible_decisions'] and
                original['projection_optimism_witness_ids'] == summary['B_projection_response']['witness_decision_ids'] and
                original['step7_to8_joint_regression_witness_ids'] == summary['A_unscored_tail']['witness_decision_ids'],
                'analyzer witness strata inconsistent')
        result.append({**json.loads(key), **summary,
            'frozen_analyzer_descriptive_medians': {name: original.get(name) for name in
                ('actual_progress_median_m', 'projection_rmse_median_m')},
            'median_scope': 'Within-episode descriptive decisions, not independent observations.'})
    return result


def complete_row(reference, row, plan, plan_sha, sources):
    require(set(reference) == {'status', 'terminal', 'audit', 'analysis'} and reference['status'] == 'complete',
            'complete row requires terminal/audit/analysis references')
    root = Path(plan['artifact_root']).resolve()
    terminal, terminal_path = load_reference(reference['terminal'], root)
    audit, audit_path = load_reference(reference['audit'], root)
    analysis, analysis_path = load_reference(reference['analysis'], root)
    require(terminal_path.name == 'attempt-result.json', 'explicit terminal result required')
    output = terminal_path.parent
    require(Path(terminal['output_dir']).resolve() == output and output.parent == root/'attempts', 'attempt output binding differs')
    require(terminal['attempt_id'] == output.name and terminal['episode_key'] == row['episode_key'] and
        terminal['identity'] == {key: row[key] for key in IDENTITY_FIELDS}, 'terminal scientific identity differs')
    require(terminal['physical_gpu'] == 3 and terminal['budget_bucket'] == 'development', 'GPU/condition cannot be pooled')
    require(terminal['plan_sha256'] == plan_sha and terminal['source_commit'] == plan['source_commit'] and
        terminal['profile_manifest_sha256'] == plan['profiles_sha256'] and
        terminal['runtime_inventory_sha256'] == plan['runtime_inventory_sha256'] and
        terminal['runtime_manifest_sha256'] == plan['runtime_manifest_sha256'], 'terminal frozen condition differs')
    require(terminal['event'] == 'valid' and terminal.get('outcome_valid') is True and
        type(terminal.get('success')) is bool, 'complete valid original terminal required; no relabeling')
    require(audit_path == output/'eds_eval/decision-evidence-audit.json', 'audit path binding differs')
    require(audit.get('schema') == 'qd-ed-decision-evidence-audit-v1' and audit.get('accepted') is True and
        audit.get('evidence_complete') is True and audit.get('errors') == [], 'accepted complete audit required')
    require(analysis.get('schema') == 'qd-ed-selected-decision-analysis-v2' and
        analysis.get('input_kind') == 'audited_runtime_episode', 'frozen runtime analysis schema required')
    require(analysis['source_sha256'] == {'analysis': sources[ANALYZER], 'existing_auditor': sources[AUDITOR]},
            'analysis/auditor source differs from plan')
    episode = output/'eds_eval/decision_evidence/episode_000'
    compute = output/'eds_eval/episode_compute.jsonl'
    require(analysis['episode_dir'] == audit['episode_dir'] == str(episode) and
        audit['episode_compute_file'] == str(compute), 'analysis/audit episode paths differ')
    require(analysis['task_id'] == row['task_id'] and analysis['episode_seed'] == row['env_seed'] and
        analysis['episode_id'] == 0 and analysis['original_execution_outcome'] == audit['original_execution_outcome'] == 'completed',
        'analysis identity/outcome differs')
    require(analysis['cuda_initialized_before'] is False and analysis['cuda_initialized_after'] is False,
            'analysis was not CPU-only')
    require(analysis['audit'] == {key: value for key, value in audit.items() if key != 'wrapper_observation'},
            'analysis internal audit differs from explicit accepted audit')
    require(isinstance(analysis['input_sha256'], dict) and all(str(path) in analysis['input_sha256']
        for path in (episode/'status.json', episode/'events.jsonl', compute)), 'analysis input provenance incomplete')
    require(analysis['input_sha256'].get(str(Path(plan['worktree']).resolve()/TARGET_MAP)) == sources[TARGET_MAP],
            'original frozen map-v2 condition differs; supplemental maps cannot be pooled')
    costs = {key: terminal.get(key) for key in COST_FIELDS}
    require(type(costs['gpu_process_wall_seconds']) in (int, float) and
        math.isfinite(costs['gpu_process_wall_seconds']) and costs['gpu_process_wall_seconds'] >= 0, 'terminal GPU cost invalid')
    for value in costs.values():
        require(value is None or (type(value) in (int, float) and math.isfinite(value) and value >= 0), 'invalid cost counter')
    return {'episode_key': row['episode_key'], 'status': 'complete', 'identity': terminal['identity'],
        'attempt_id': terminal['attempt_id'], 'physical_gpu': 3,
        'original_outcome': {name: terminal.get(name) for name in ('event', 'outcome_valid', 'success', 'task_failure', 'failure_class')},
        'original_execution_outcome': analysis['original_execution_outcome'],
        'audit': {'accepted': True, 'evidence_complete': True, 'accepted_is_not_task_success': True,
                  'wrapper_observation': audit.get('wrapper_observation')},
        'source_sha256': analysis['source_sha256'], 'target_map_sha256': sources[TARGET_MAP], 'input_references': reference,
        'analysis_input_sha256': analysis['input_sha256'],
        'provenance_limit': 'Summary verifies named JSON SHA bindings; it deliberately does not reread underlying tensor/status/index/compute files. The frozen analyzer audited them.',
        'costs': costs, 'mechanism': decision_summary(analysis['decisions']), 'strata': summarize_strata(analysis)}


def pair_description(left, right, all_complete):
    result = {'task_id': left['identity']['task_id'], 'C0_P2_key': left['episode_key'], 'Q0_key': right['episode_key'],
              'status': 'complete_descriptive_pair' if all_complete else 'pending_all_four',
              'inference': 'Not evaluated; no significance test, benefit claim, or automatic promotion.'}
    if not all_complete:
        return result
    result['original_success'] = {'C0_P2': left['original_outcome']['success'], 'Q0': right['original_outcome']['success']}
    result['episode_witness_presence'] = {hypothesis: {'C0_P2': left['mechanism'][hypothesis]['episode_presence'],
        'Q0': right['mechanism'][hypothesis]['episode_presence']} for hypothesis in ('A_unscored_tail', 'B_projection_response')}
    lstrata, rstrata = ({stratum_key(row): row for row in item['strata']} for item in (left, right))
    result['stage_provider_alignment'] = [{'identity': json.loads(key), 'C0_P2': lstrata.get(key), 'Q0': rstrata.get(key),
        'match': 'same_stage_guidance_provider_identity' if key in lstrata and key in rstrata else 'unmatched_retained'}
        for key in sorted(set(lstrata)|set(rstrata))]
    result['stage_limit'] = 'Same task/seed does not guarantee the same adaptive Stage/provider trajectory; unmatched strata remain visible.'
    return result


def summarize(manifest):
    require(manifest.get('schema') == 'qd-ed-observed-pair-summary-input-v1', 'input manifest schema differs')
    require(set(manifest['episodes']) == set(KEYS), 'manifest must retain all four predetermined keys')
    plan, _ = load_reference(manifest['plan'])
    sources = check_plan(plan, manifest['plan']['sha256'])
    rows = []
    for row in plan['episodes']:
        reference = manifest['episodes'][row['episode_key']]
        if reference is None or reference.get('status') == 'pending':
            require(reference is None or set(reference) <= {'status', 'reason'}, 'pending row must not contain partial inputs')
            rows.append({'episode_key': row['episode_key'], 'status': 'pending',
                'identity': {key: row[key] for key in IDENTITY_FIELDS},
                'reason': reference.get('reason', 'complete accepted analysis not supplied') if reference else 'complete accepted analysis not supplied',
                'original_outcome': None, 'audit': None, 'mechanism': None, 'costs': None})
        else:
            rows.append(complete_row(reference, row, plan, manifest['plan']['sha256'], sources))
    complete = [row for row in rows if row['status'] == 'complete']
    all_complete = len(complete) == 4
    return {'schema': 'qd-ed-observed-pair-summary-v1', 'plan_reference': manifest['plan'],
        'source_sha256': {'analysis': sources[ANALYZER], 'existing_auditor': sources[AUDITOR]},
        'target_map_condition': {'path': str(Path(plan['worktree']).resolve()/TARGET_MAP), 'sha256': sources[TARGET_MAP],
                                 'scope': 'Original frozen map-v2 only; no supplemental identity repair condition.'},
        'summary_script_sha256': digest(Path(__file__).read_bytes()),
        'status': 'complete_descriptive_matrix' if all_complete else 'pending_matrix',
        'completed_episodes': len(complete), 'pending_episodes': 4-len(complete), 'planned_episodes': 4,
        'unit_of_evidence': 'One complete episode; within-episode decisions are descriptive, correlated observations.',
        'rows': rows, 'pairs': [pair_description(rows[0], rows[1], all_complete), pair_description(rows[2], rows[3], all_complete)],
        'completed_episode_gpu_wall_seconds': sum(row['costs']['gpu_process_wall_seconds'] for row in complete),
        'cost_scope': 'Only the explicitly supplied completed episodes; excludes pending/aborted/other study resources and CPU audit time.',
        'promotion_status': 'NOT_EVALUATED', 'limitations': LIMIT}


def render_markdown(report):
    lines = ['# Four observed Dev episodes — descriptive summary', '',
        f"Status: {report['status']}; completed {report['completed_episodes']}/4, pending {report['pending_episodes']}/4.", '',
        '| Task | Arm | Status | Original task success | Audit | Eligible decisions (descriptive) | A episode presence | B episode presence | GPU wall seconds |',
        '|---|---|---|---|---|---|---|---|---|']
    for row in report['rows']:
        identity = row['identity']
        if row['status'] == 'pending':
            values = ['pending', 'Unknown', 'pending', 'Unknown', 'Unknown', 'Unknown', 'Unknown']
        else:
            values = ['complete', str(row['original_outcome']['success']).lower(), 'accepted (not success)',
                str(row['mechanism']['hypothesis_eligible_decisions']), row['mechanism']['A_unscored_tail']['episode_presence'],
                row['mechanism']['B_projection_response']['episode_presence'], str(row['costs']['gpu_process_wall_seconds'])]
        lines.append('| '+' | '.join([str(identity['task_id']), 'C0/P2' if identity['profile']=='C0' else 'Q0', *values])+' |')
    lines += ['', 'A = the frozen analyzer’s eligible full-prefix joint step7→8 regression witness. B = its eligible projection-response witness. No eligible prefix means Unknown, not a negative finding.', '']
    for pair in report['pairs']:
        lines.append(f"Task {pair['task_id']} pair: {pair['status']}.")
        if pair['status'] == 'complete_descriptive_pair':
            lines.append('Original outcomes and A/B presence: '+json.dumps({'success':pair['original_success'], 'witness_presence':pair['episode_witness_presence']}, sort_keys=True)+'.')
            unmatched = sum(row['match'] == 'unmatched_retained' for row in pair['stage_provider_alignment'])
            lines.append(f"Stage/provider strata: {len(pair['stage_provider_alignment'])}; unmatched strata retained: {unmatched}. Full identities, counts, witness IDs and original descriptive medians are in summary.json.")
        lines.append('')
    lines += [f"Completed-row GPU wall time only: {report['completed_episode_gpu_wall_seconds']} seconds. This is not the study's total budget/cost.", '', LIMIT,
        '', 'Input JSON SHA bindings and frozen analyzer/auditor hashes are preserved in summary.json. The summary does not reopen tensor bundles or turn audit acceptance into task success. Missing inputs remain pending. No algorithm or promotion decision is made.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    manifest = json.loads(raw)
    report = summarize(manifest)
    plan, _ = load_reference(manifest['plan'])
    output = args.output_dir.resolve()
    require(output.is_relative_to(Path(plan['artifact_root']).resolve()/'continuation_20260923'), 'outputs must stay in a new artifact continuation directory')
    require(not output.exists(), 'refusing to overwrite an existing report directory')
    output.mkdir(parents=True, exist_ok=False)
    report['input_manifest_sha256'] = digest(raw)
    (output/'input-manifest.json').write_bytes(raw)
    (output/'summary.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
    (output/'report.md').write_text(render_markdown(report))
    print(json.dumps({'status':report['status'], 'completed_episodes':report['completed_episodes'],
        'pending_episodes':report['pending_episodes'], 'output_dir':str(output), 'promotion_status':'NOT_EVALUATED'}))


if __name__ == '__main__':
    main()
