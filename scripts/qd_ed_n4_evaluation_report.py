#!/usr/bin/env python3
"""Conditional protected-phase metadata report, never execution authority.

Uses only explicit SHA-bound JSON inputs. Native audits are separately produced
by the unchanged production auditor or the additive QD-OFF phase auditor.
"""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path

import qd_ed_n4_evaluation as e


def recompute_dev(manifest, root, r):
    """Replay the exact frozen Dev reporter's metadata path, without its CLI."""
    d = e.frozen_report(r); script = Path(d.__file__).resolve()
    d.require(manifest['schema'] == 'qd-ed-n4-report-input-v1'
        and manifest['script_sha256'] == d.sha(script) and manifest['protocol_sha256'] == d.sha(d.PROTOCOL), 'Dev report freeze differs')
    auth = d.read_ref(manifest['authorization'])
    d.require(auth['script'] == {'path': str(script), 'sha256': d.sha(script)}
        and auth['protocol_sha256'] == manifest['protocol_sha256']
        and auth['base_plan_sha256'] == manifest['base_plan']['sha256']
        and auth.get('schema') == 'qd-ed-n4-report-authorization-v1' and auth.get('status') == 'authorized', 'Dev report authorization differs')
    base = d.read_ref(manifest['base_plan']); originals = d.plan_contract(base)
    code = {v['path']: v['sha256'] for v in base['code_files']}
    d.require(code.get('scripts/qd_ed_n4_report.py') == d.sha(script)
        and code.get('scripts/qd_ed_n4_plan.py') == d.sha(script.with_name('qd_ed_n4_plan.py')), 'Dev report/source contract differs')
    plans = {manifest['base_plan']['sha256']: base}
    for reference in manifest.get('plan_revisions', []):
        plan = d.read_ref(reference)
        d.require(d.plan_contract(plan) == originals and all(plan[k] == base[k] for k in d.BINDING)
            and plan['candidate_profiles'] == base['candidate_profiles'] and plan['code_files'] == base['code_files']
            and all(plan['n4_cohort'][k] == base['n4_cohort'][k] for k in ('limits', 'runtime_prerequisites', 'health_resources',
                'protocol', 'accounting_clarification', 'budget_allocation', 'budget_allocation_amendment',
                'prerequisite_protocol', 'prerequisite_review', 'shared_resource_contract', 'shared_resource_pointer')),
            'Dev revision scientific/source condition differs')
        d.require(reference['sha256'] not in plans, 'duplicate Dev plan reference')
        plans[reference['sha256']] = plan
    d.require(auth.get('journal_excerpt_sha256') == manifest['journal_excerpt']['sha256'], 'Dev journal authority differs')
    inflight = d.validate_journal_excerpt(d.read_ref(manifest['journal_excerpt']), manifest['attempts'], plans, base)
    d.require(not inflight or manifest.get('input_scope_complete') is False, 'inflight Dev cannot claim complete scope')
    attempts = [d.load_attempt(spec, plans) for spec in manifest['attempts']]
    report = d.summarize(base, attempts, inflight)
    report['resources'] = d.resource_costs(base, manifest.get('health_resources', []), attempts, inflight)
    report.update(input_manifest=manifest, input_scope_complete=manifest.get('input_scope_complete') is True,
        input_scope_note='Completeness of the named terminal inventory is a root assertion, not inferred by scanning live attempts.')
    # input_manifest_sha256 is CLI transport provenance, not recomputable from a
    # decoded dict without the original file serialization; caller binds that ref.
    recheck_refs(d, manifest)
    return report, attempts, base


def recheck_refs(d, manifest):
    refs = [manifest[k] for k in ('authorization', 'base_plan', 'journal_excerpt')]
    refs += manifest.get('plan_revisions', []) + [x['terminal'] for x in manifest.get('health_resources', [])]
    refs += [v for spec in manifest['attempts'] for v in spec.values()]
    for ref in refs: d.require(d.sha(ref['path']) == ref['sha256'], 'report input changed')


def record_identity(t, plan, plan_sha, r):
    row = next((x for x in plan['episodes'] if x['episode_key'] == t.get('episode_key')), None)
    r.require(row is not None and t.get('identity') == r.episode_identity(row), 'phase cell differs')
    r.require(t.get('plan_sha256') == plan_sha and t.get('physical_gpu') == 3
        and all(t.get(k) == plan[k] for k in ('source_commit', 'runtime_manifest_sha256', 'runtime_inventory_sha256'))
        and t.get('profile_manifest_sha256') == plan['profiles_sha256'] and t.get('init_row_sha256') == row['init_row_sha256']
        and t.get('budget_bucket') == row['budget_bucket'] and t.get('retry_of') == row.get('retry_of')
        and t.get('n4_evaluation_cohort_id') == plan['n4_evaluation']['cohort_id']
        and t.get('n4_evaluation_frozen_identity') == e.binding(plan), 'phase frozen identity differs')
    r.owned(t['output_dir'], plan['artifact_root'])
    return row


def terminal_check(t, plan, plan_sha, r, d):
    row = record_identity(t, plan, plan_sha, r)
    r.require(t.get('event') in r.TERMINAL and type(t.get('success')) is bool
        and type(t.get('outcome_valid')) is bool and type(t.get('n4_episode_dispatched')) is bool
        and d.finite(t.get('gpu_process_wall_seconds')) and t['gpu_process_wall_seconds'] >= 0, 'phase terminal/cost missing')
    if not t['n4_episode_dispatched']:
        r.require(t['event'] == 'aborted' and t['outcome_valid'] is False and t['gpu_process_wall_seconds'] == 0,
            'phase predispatch cannot claim outcome or GPU time')
    return row


def journal_excerpt(excerpt, specs, plans, base, r, d):
    cohort = base['n4_evaluation']['cohort_id']; source = excerpt.get('source_journal', {})
    r.require(excerpt.get('schema') == 'qd-ed-n4-evaluation-journal-excerpt-v1'
        and excerpt.get('cohort_id') == cohort and excerpt.get('extraction') == 'all_events_all_phase_attempts_through_snapshot'
        and Path(source.get('path', '')).resolve() == (Path(base['worktree'])/'data/attempt-ledger.jsonl').resolve()
        and isinstance(source.get('sha256'), str) and len(source['sha256']) == 64, 'phase complete journal authority missing')
    groups = defaultdict(list)
    for event in excerpt['events']:
        r.require(event.get('n4_evaluation_cohort_id') == cohort and event.get('identity', {}).get('iteration') == cohort,
            'phase excerpt includes another cohort')
        groups[event['attempt_id']].append(event)
    terminals = []; inflight = []
    for identifier, events in groups.items():
        r.require([x['event'] for x in events] in (['reserved'], ['reserved','dispatched'], ['reserved','aborted'],
            ['reserved','dispatched','valid'], ['reserved','dispatched','aborted']), 'phase journal sequence differs')
        final = events[-1]
        r.require(final['plan_sha256'] in plans and all(event.get(k) == final.get(k) for event in events for k in (
            'attempt_id','identity','episode_key','plan_sha256','n4_evaluation_frozen_identity','retry_of','output_dir','budget_bucket')),
            'phase journal identity drift')
        row = record_identity(final, plans[final['plan_sha256']], final['plan_sha256'], r)
        dispatched = any(x['event'] == 'dispatched' for x in events)
        if final['event'] in {'reserved','dispatched'}:
            inflight.append({**{k: final[k] for k in ('attempt_id','identity','episode_key','plan_sha256','output_dir','budget_bucket')},
                'last_event': final['event'], 'dispatched': dispatched, 'gpu_process_wall_seconds': None,
                'retry_of': final.get('retry_of'), 'cell_identity': {k: row[k] for k in e.FIELDS}})
        else:
            terminal_check(final, plans[final['plan_sha256']], final['plan_sha256'], r, d)
            r.require(final['n4_episode_dispatched'] is dispatched, 'phase journal/terminal dispatch differs')
            terminals.append(identifier)
    r.require(excerpt.get('terminal_attempt_ids') == terminals
        and excerpt.get('inflight_attempt_ids') == [x['attempt_id'] for x in inflight], 'phase journal inventory differs')
    values = [d.read_ref(s['terminal']) for s in specs]
    r.require(len(values) == len(terminals) and {t['attempt_id'] for t in values} == set(terminals)
        and all(t == groups[t['attempt_id']][-1] for t in values), 'phase omitted/repeated/changed terminal')
    return inflight


def summarize(plan, attempts, r, d, *, validated_rows, inflight=(), input_scope_complete=False):
    phase = plan['n4_evaluation']['phase']; limits = e.PHASES[phase]
    originals = [x for x in plan['episodes'] if not x.get('retry_of')]
    grouped = defaultdict(list)
    active_by_cell = defaultdict(list)
    for item in inflight: active_by_cell[e.cell(item['cell_identity'])].append(item)
    r.require(len({a['terminal']['attempt_id'] for a in attempts}) == len(attempts)
        and set(validated_rows) == {a['terminal']['attempt_id'] for a in attempts}, 'phase duplicate/unvalidated attempts')
    for attempt in attempts:
        t = attempt['terminal']; row = validated_rows[t['attempt_id']]
        r.require(row['episode_key'] == t['episode_key'] and r.episode_identity(row) == t['identity']
            and row.get('retry_of') == t.get('retry_of'), 'phase own-plan row association missing')
        grouped[e.cell(row)].append(attempt)
    r.require(set(grouped) | set(active_by_cell) <= {e.cell(x) for x in originals}, 'phase outside original matrix')
    dispatched_count = sum(a['terminal']['n4_episode_dispatched'] for a in attempts) + sum(x['dispatched'] for x in inflight)
    r.require(dispatched_count <= limits['originals'] + limits['recoveries'], 'phase actual dispatch allowance exceeded')
    cells = []; retries = 0
    for row in originals:
        group = sorted(grouped[e.cell(row)], key=lambda a: a['terminal']['time_unix'])
        executed = [a for a in group if a['terminal']['n4_episode_dispatched']]
        r.require(len(executed) <= 2 and (not executed or not executed[0]['terminal'].get('retry_of')), 'phase recovery chain differs')
        if len(executed) == 2:
            retries += 1; first, second = [a['terminal'] for a in executed]
            r.require(second.get('retry_of') == first['attempt_id'] and e.recoverable(first, e.binding(plan)), 'ineligible phase retry')
        valid = [a for a in group if a['status'] == 'complete_valid']
        r.require(len(valid) <= 1 and (not valid or valid[0] is executed[-1]), 'phase superseded valid cell')
        selected = valid[0] if valid else None
        active = active_by_cell[e.cell(row)]
        r.require(len(active) <= 1 and (not active or selected is None and len(executed) < 2), 'phase valid/excess cell inflight')
        if active and executed:
            r.require(active[0].get('retry_of') == executed[0]['terminal']['attempt_id']
                and e.recoverable(executed[0]['terminal'], e.binding(plan)), 'phase inflight recovery differs')
        elif active:
            r.require(not active[0].get('retry_of'), 'phase inflight recovery original missing')
        cells.append({'identity': {k: row[k] for k in (*d.IDENTITY, 'seed_block')},
            'status': 'complete_valid' if selected else ('inflight_dispatched' if active[0]['dispatched'] else 'reserved_no_dispatch') if active else group[-1]['status'] if group else 'pending',
            'valid_attempt_id': selected['terminal']['attempt_id'] if selected else None,
            'success': selected['terminal']['success'] if selected else None, 'attempts': group,
            'metrics': selected.get('metrics') if selected else None, 'inflight': active})
    r.require(retries <= limits['recoveries'], 'phase recovery ceiling exceeded')
    arms = ('C0','Q0','N4') + (('N4_QD_OFF',) if phase == 'formal' else ())
    profiles = {}
    for arm in arms:
        chosen = [x for x in cells if x['identity']['profile'] == arm]
        valid = [x for x in chosen if x['status'] == 'complete_valid']
        raw = [a['terminal'] for x in chosen for a in x['attempts']] + [a for x in chosen for a in x['inflight']]
        r.require(len(chosen) == limits['per_arm'], 'phase arm denominator differs')
        profiles[arm] = {'expected': limits['per_arm'], 'complete_valid': len(valid),
            'successes_observed': sum(x['success'] is True for x in valid),
            'failures_observed': sum(x['success'] is False for x in valid),
            'success_rate': sum(x['success'] is True for x in valid)/limits['per_arm'] if len(valid) == limits['per_arm'] else None,
            'all_attempt_gpu_seconds': d.observed([t['gpu_process_wall_seconds'] for t in raw]),
            'all_attempt_costs': {k: d.observed([t.get(k) for t in raw]) for k in d.COSTS},
            'blocks': {b: {'expected': 10, 'complete_valid': sum(x['status'] == 'complete_valid' for x in chosen if x['identity']['seed_block'] == b),
                'successes_observed': sum(x['success'] is True for x in chosen if x['identity']['seed_block'] == b)}
                for b in dict.fromkeys(x['identity']['seed_block'] for x in chosen)}}
    complete = all(x['status'] == 'complete_valid' for x in cells) and not inflight and input_scope_complete
    paired = {}
    for control in ('C0','Q0') + (('N4_QD_OFF',) if phase == 'formal' else ()):
        left = {e.sample(x['identity']): x for x in cells if x['identity']['profile'] == 'N4'}
        right = {e.sample(x['identity']): x for x in cells if x['identity']['profile'] == control}
        r.require(left.keys() == right.keys(), 'phase arms not matched')
        comparable = all(x['status'] == 'complete_valid' for x in (*left.values(), *right.values()))
        paired['N4_vs_' + control] = {'matched_complete': comparable,
            'gained': [list(k) for k in left if left[k]['success'] and not right[k]['success']] if comparable else None,
            'lost': [list(k) for k in left if not left[k]['success'] and right[k]['success']] if comparable else None,
            'success_delta': profiles['N4']['successes_observed'] - profiles[control]['successes_observed'] if comparable else None}
    numeric = (profiles['N4']['successes_observed'] >= limits['threshold'] and
        all(profiles['N4']['successes_observed'] >= profiles[x]['successes_observed'] for x in ('C0','Q0'))) if complete else None
    n4_metrics = [x['metrics']['n4'] for x in cells if x['identity']['profile'] == 'N4' and x['status'] == 'complete_valid']
    return {'schema': 'qd-ed-n4-evaluation-report-v1', 'phase': phase, 'cohort_id': plan['n4_evaluation']['cohort_id'],
        'candidate_fingerprint': plan['n4_evaluation']['candidate_fingerprint'], 'complete': complete, 'numeric_pass': numeric,
        'input_scope_complete': input_scope_complete, 'cells': cells, 'profiles': profiles, 'paired_comparisons': paired,
        'statuses': dict(Counter(x['status'] for x in cells)), 'inflight_attempts': list(inflight),
        'actual_dispatches': dispatched_count, 'raw_terminal_records': len(attempts),
        'candidate_activity': {'scope': 'descriptive only; no protected-phase prefix-difference threshold',
            'guided_native_decisions': sum(m['native_terminal_population_alignment']['checked_decisions'] for m in n4_metrics),
            'actual_prefix_different_decisions': sum(m['actual_prefix_different_decisions'] for m in n4_metrics)},
        'phase_authorized': False, 'scientific_promotion': 'Requires independent bound correctness review and phase authority.',
        'ablation_scope': 'N4_QD_OFF is total QD removal with C0-equivalent active algorithm and population Stage spread; retained fourth arm, no superiority gate.',
        'unknown_scope': 'Invalid/missing cells are Unknown; episode-level matched denominators; no physical grasp or counterfactual claims.'}


def phase_resource_costs(plan, refs, attempts, inflight, d, r):
    declared = plan['n4_evaluation']['health_resources']
    r.require([{'resource_id': x['resource_id'], 'scope': x['scope']} for x in refs] == declared, 'phase health inventory differs')
    health = []
    for ref in refs:
        t = d.read_ref(ref['terminal'])
        r.require(t.get('resource_id') == ref['resource_id'] and t.get('event') in {'completed','aborted'}
            and d.finite(t.get('gpu_process_wall_seconds')) and t['gpu_process_wall_seconds'] >= 0, 'phase health unsettled')
        # Current contract inherits only accounted prior proofs. New probes need a
        # prospectively revised contract rather than an invented charge category.
        r.require(ref['scope'] == 'reused_prior', 'unapproved new phase health resource')
        health.append({**ref, 'gpu_process_wall_seconds': t['gpu_process_wall_seconds']})
    seconds = sum(a['terminal']['gpu_process_wall_seconds'] for a in attempts)
    return {'episode_seconds_observed_subtotal': seconds, 'episode_seconds': seconds if not inflight else None,
        'inflight_costs_settled': not bool(inflight), 'reused_prior_health_seconds_not_recharged': sum(x['gpu_process_wall_seconds'] for x in health),
        'health_evidence': health, 'budget_authority': 'private 240/48 journal admission; this report does not release reservations'}


def recompute(manifest, root, r):
    root = Path(root); d = e.frozen_report(r)
    r.require(manifest.get('schema') == 'qd-ed-n4-evaluation-report-input-v1'
        and manifest.get('script_sha256') == r.digest(root/e.REPORT) and manifest.get('protocol_sha256') == e.PROTOCOL_SHA,
        'phase report source contract differs')
    auth = d.read_ref(manifest['authorization'])
    r.require(auth.get('schema') == 'qd-ed-n4-evaluation-report-authorization-v1' and auth.get('status') == 'authorized'
        and auth.get('script') == {'path': str((root/e.REPORT).resolve()), 'sha256': manifest['script_sha256']}
        and auth.get('protocol_sha256') == e.PROTOCOL_SHA and auth.get('base_plan_sha256') == manifest['base_plan']['sha256']
        and auth.get('journal_excerpt_sha256') == manifest['journal_excerpt']['sha256'], 'phase report authority differs')
    base = d.read_ref(manifest['base_plan']); plans = {manifest['base_plan']['sha256']: base}
    seeds = r.read_json(base['seed_plan_path']); phase = base['n4_evaluation']['phase']
    r.require(r.digest(base['seed_plan_path']) == base['seed_plan_sha256'], 'phase seed metadata changed')
    for ref in manifest.get('plan_revisions', []):
        plan = d.read_ref(ref)
        r.require(ref['sha256'] not in plans and e.binding(plan) == e.binding(base)
            and e.source_identity(plan,r) == e.source_identity(base,r)
            and e.source_identity(e.read_ref(plan['n4_evaluation']['dev_plan'],plan,r),r)
                == e.source_identity(e.read_ref(base['n4_evaluation']['dev_plan'],base,r),r), 'phase revision source/candidate differs')
        plans[ref['sha256']] = plan
    for plan in plans.values():
        r.require(plan.get('frozen') is True and plan['phase_authorization'].get(phase) is True, 'phase report plan unreleased')
        r.require(r.digest(plan['profiles_path']) == plan['profiles_sha256']
            and r.digest(plan['runtime_manifest_path']) == plan['runtime_manifest_sha256'], 'phase profile/runtime bytes changed')
        for entry in plan['code_files']:
            r.require(r.digest(r.owned(root/entry['path'],root)) == entry['sha256'], 'phase frozen source changed')
        profiles = r.read_json(plan['profiles_path'])
        candidate_ref = plan['candidate_profiles']['N4']; candidate_path = r.owned(root/candidate_ref['path'],root)
        r.require(r.digest(candidate_path) == candidate_ref['sha256'], 'phase candidate bytes changed')
        profiles['profiles']['N4'] = r.expand_candidate('N4',r.read_json(candidate_path),profiles['profiles']['Q0'])
        e.validate_contract(plan,profiles,r.read_json(plan['runtime_manifest_path']),seeds,root,r)
    inflight = journal_excerpt(d.read_ref(manifest['journal_excerpt']),manifest['attempts'],plans,base,r,d)
    r.require(not inflight or manifest.get('input_scope_complete') is False, 'inflight phase cannot claim complete scope')
    original_metrics = d.summarize_metrics
    def metrics(records, terminal, audit, compute):
        result = original_metrics(records,terminal,audit,compute)
        if terminal['identity']['profile'] == 'N4_QD_OFF':
            import audit_n4_qd_off_evidence as off
            result['qd_off_native'] = off.native_audit_alignment(audit,records,require=r.require)
        return result
    validated_rows = {}
    def validate(t, plan, digest):
        row = terminal_check(t,plan,digest,r,d)
        r.require(t['attempt_id'] not in validated_rows, 'phase duplicate validated terminal')
        validated_rows[t['attempt_id']] = row
        return row
    d.validate_terminal = validate; d.summarize_metrics = metrics
    attempts = []
    for spec in manifest['attempts']:
        attempt = d.load_attempt(spec,plans); terminal = d.read_ref(spec['terminal'])
        attempt['terminal'].update({k: terminal[k] for k in ('n4_evaluation_cohort_id','n4_evaluation_frozen_identity','n4_evaluation_recovery_eligibility') if k in terminal})
        attempts.append(attempt)
    by_id = {a['terminal']['attempt_id']: a for a in attempts}
    for a in attempts:
        terminal = a['terminal']
        if terminal.get('retry_of') and terminal['n4_episode_dispatched']:
            r.require(terminal['retry_of'] in by_id, 'phase recovery original missing')
            actual = d.read_ref(a['references']['terminal']); plan = plans[actual['plan_sha256']]
            e.recovery_release(plan,validated_rows[terminal['attempt_id']],d.read_ref(by_id[terminal['retry_of']]['references']['terminal']),r)
    report = summarize(base,attempts,r,d,validated_rows=validated_rows,inflight=inflight,input_scope_complete=manifest.get('input_scope_complete') is True)
    report['resources'] = phase_resource_costs(base,manifest.get('health_resources',[]),attempts,inflight,d,r)
    report['input_manifest'] = manifest
    recheck_refs(d,manifest)
    return report,attempts,base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execute-reviewed',action='store_true'); args = parser.parse_args()
    import qd_ed_final_runner as r
    r.require(args.execute_reviewed and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'explicit reviewed CPU-only report required')
    manifest = r.read_json(args.manifest); before = r.digest(args.manifest)
    report,attempts,plan = recompute(manifest,e.ROOT,r)
    r.require(r.digest(args.manifest) == before, 'phase manifest changed')
    report['input_manifest_sha256'] = before
    output = r.owned(args.output,Path(plan['artifact_root'])/'continuation_20260924')
    r.require(not output.exists() and output.suffix == '.json'
        and all(not output.is_relative_to(Path(a['terminal']['output_dir']).resolve()) for a in attempts), 'separate new report required')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream: json.dump(report,stream,indent=2,sort_keys=True,allow_nan=False); stream.write('\n')
    print(json.dumps({'complete':report['complete'],'numeric_pass':report['numeric_pass'],'output':str(output)}))


if __name__ == '__main__': main()
