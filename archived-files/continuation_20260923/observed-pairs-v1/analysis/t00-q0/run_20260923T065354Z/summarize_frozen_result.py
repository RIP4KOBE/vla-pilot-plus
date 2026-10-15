#!/usr/bin/env python3
"""Display a completed frozen analyzer JSON; never read episode bundles or change gates."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def stats(values):
    xs = [x for x in values if x is not None]
    return {'n': len(xs), 'min': min(xs), 'median': statistics.median(xs),
            'max': max(xs)} if xs else {'n': 0, 'min': None, 'median': None, 'max': None}


def triple(identity):
    return tuple(identity.get(k) for k in ('original_code_sha256', 'source_text_sha256', 'source_path'))


def diagnostic_stats(rows):
    values = [r['diagnostics'] for r in rows if r['diagnostics'] is not None]
    return {k: stats([v[k] for v in values]) for k in ('eef_projection_rmse_m',
        'endpoint_projection_error_m', 'projected_motion_tracking_gain',
        'projected_t0_source_cast_error_m', 'endpoint_precision_floor_m')}


def pattern(row):
    return ''.join('+' if x > 0 else '-' if x < 0 else '0' for x in row['actual_gripper_command_prefix'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--frozen-map', type=Path, required=True)
    args = parser.parse_args()
    raw = args.analysis.read_bytes()
    analysis = json.loads(raw)
    assert analysis['schema'] == 'qd-ed-selected-decision-analysis-v2'
    assert analysis['input_kind'] == 'audited_runtime_episode'
    assert analysis['audit']['accepted'] and analysis['audit']['evidence_complete']
    assert analysis['cuda_initialized_after'] is False
    map_sha = hashlib.sha256(args.frozen_map.read_bytes()).hexdigest()
    assert map_sha == analysis['input_sha256'][str(args.frozen_map.resolve())]
    mapping = json.loads(args.frozen_map.read_text())['entries']
    rows = analysis['decisions']
    projected = [r for r in rows if r['diagnostics'] is not None]
    eligible = [r for r in rows if r.get('hypothesis_eligible')]
    full_eligible = [r for r in eligible if r['diagnostics']['step7_to8'] is not None]
    steps = [s for r in rows for s in r['actual_steps']]
    identity_counts = Counter(json.dumps(p, sort_keys=True) for r in rows for p in r['provider_identities'])
    triples = Counter(triple(p) for r in rows for p in r['provider_identities'])
    identity_rows = []
    for identity, count in triples.items():
        original, text, path = identity
        path_entries = [e for e in mapping if e['source_path'] == path]
        exact = any(triple(e) == identity for e in path_entries)
        text_match = any(e['source_text_sha256'] == text for e in path_entries)
        status = ('exact_match' if exact else 'no_target_map_entry_for_source_path' if not path_entries
                  else 'original_code_mismatch' if text_match else 'source_text_mismatch')
        identity_rows.append({'original_code_sha256': original, 'source_text_sha256': text,
            'source_path': path, 'count': count, 'frozen_map_status': status,
            'expected_original_code_sha256': sorted({e['original_code_sha256'] for e in path_entries})})
    source_matches = sum(v['count'] for v in identity_rows
                         if v['frozen_map_status'] in {'exact_match', 'original_code_mismatch'})
    exact_matches = sum(v['count'] for v in identity_rows if v['frozen_map_status'] == 'exact_match')
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['stage'], row['guidance'])].append(row)
    tails = [r['diagnostics']['step7_to8'] for r in projected if r['diagnostics']['step7_to8'] is not None]
    summary = {
        'schema': 'qd-ed-frozen-single-episode-interpretation-v1',
        'source_analysis_path': str(args.analysis.resolve()),
        'source_analysis_sha256': hashlib.sha256(raw).hexdigest(),
        'display_helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'frozen_map_sha256': map_sha, 'task_id': analysis['task_id'], 'episode_seed': analysis['episode_seed'],
        'original_execution': {'outcome': analysis['original_execution_outcome'],
            'any_captured_environment_success': any(s['success'] for s in steps),
            'last_step_success': steps[-1]['success'], 'last_step_truncated': steps[-1]['truncated'],
            'actual_steps': len(steps)},
        'evidence': {'accepted': True, 'complete': True, 'errors': analysis['audit']['errors'],
            'decisions': len(rows), 'guided': sum(r['guidance'] for r in rows),
            'unguided': sum(not r['guidance'] for r in rows), 'projected_decisions': len(projected),
            'actual_prefix_lengths': dict(Counter(r['executed_prefix_length'] for r in rows)),
            'source_eef_dtypes': dict(Counter(s['eef_source_dtype'] for s in steps)),
            'projection_dtypes': dict(Counter(r['projection_dtype'] for r in projected)),
            'cuda_initialized': False},
        'target_identity': {'exact_map_matches': exact_matches,
            'source_text_and_path_matches': source_matches,
            'unique_original_source_path_tuples': identity_rows,
            'all_recorded_provider_identities': [{'count': n, 'identity': json.loads(v)}
                                                for v, n in identity_counts.items()],
            'structural_code_fields_or_structural_code_sha256_recorded': False},
        'frozen_hypotheses': {'eligible_decisions': len(eligible),
            'eligible_full_prefixes': len(full_eligible),
            'A_witnesses': sum(r['diagnostics']['step7_to8']['both_regress_robust'] for r in full_eligible)
                           if full_eligible else None,
            'B_witnesses': sum(r['diagnostics']['projection_optimism_witness'] for r in eligible) if eligible else None,
            'interpretation': 'Unknown when eligible denominator is zero; not a negative result'},
        'continuous_diagnostics': diagnostic_stats(projected),
        'endpoint_error_above_existing_resolution_floor_count': sum(
            r['diagnostics']['endpoint_projection_error_m'] > r['diagnostics']['endpoint_precision_floor_m']
            for r in projected),
        'gripper_projected_decisions': {'command_patterns': dict(Counter(pattern(r) for r in projected)),
            'step7_to8_command_switches': sum(t['gripper_command_switched'] for t in tails),
            'step7_to8_qpos_change_l2': stats([t['gripper_qpos_change_l2'] for t in tails]),
            'physical_grasp': 'Unknown'},
        'stage_guidance_groups': [{'stage': stage, 'guidance': guidance, 'decisions': len(rs),
            'actual_steps': sum(len(r['actual_steps']) for r in rs),
            'resolved_targets': sum(r['frozen_target'] is not None for r in rs),
            'continuous_diagnostics': diagnostic_stats(rs),
            'command_patterns': dict(Counter(pattern(r) for r in rs))}
            for (stage, guidance), rs in grouped.items()],
        'frozen_strata_preserved': analysis['strata'],
        'unknown_reasons': dict(Counter(x for r in rows for x in r['unknown_reasons'])),
        'limits': ['Frozen script/map and all primary gates unchanged',
            'Wrapper SHA differences are recorded, not interpreted as different reward semantics',
            'EEF error alone establishes neither target-relative progress nor reward misselection',
            'Commands/qpos do not establish grasp; unexecuted outcomes remain Unknown',
            'This report is per episode; no four-row paired conclusion is made'],
    }
    out = args.analysis.parent
    with (out / 'interpretation-summary.json').open('x') as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write('\n')
    lines = ['# Frozen single-episode result', '',
        f"Task {analysis['task_id']}, seed {analysis['episode_seed']}. Original execution outcome: **{analysis['original_execution_outcome']}**. "
        f"Captured environment success (any / last): **{summary['original_execution']['any_captured_environment_success']} / {steps[-1]['success']}**. "
        f"Last step truncated={steps[-1]['truncated']}; {len(steps)} actual steps.", '',
        f"Evidence audit accepted=true, complete=true, errors=[]; {len(rows)} decisions, "
        f"{summary['evidence']['guided']} guided and {summary['evidence']['unguided']} unguided. CUDA remained uninitialized.", '',
        f"Frozen target identity exact matches: **{exact_matches}/{len(projected)} projected decisions**; "
        f"source text+path matches: {source_matches}. Eligible target-aware decisions: {len(eligible)}. "
        f"A witnesses={summary['frozen_hypotheses']['A_witnesses']}; B witnesses={summary['frozen_hypotheses']['B_witnesses']}. "
        'Null means Unknown; zero eligible decisions cannot establish zero incidence or a negative result.', '',
        '| Continuous diagnostic | n | median | min | max |', '|---|---:|---:|---:|---:|']
    for key, value in summary['continuous_diagnostics'].items():
        lines.append(f"| {key} | {value['n']} | {value['median']} | {value['min']} | {value['max']} |")
    lines += ['', '| Stage | Guidance | Decisions | Actual steps |', '|---|---|---:|---:|']
    for row in summary['stage_guidance_groups']:
        lines.append(f"| {row['stage']} | {row['guidance']} | {row['decisions']} | {row['actual_steps']} |")
    lines += ['', 'Identity triples and all observed wrapper identities/counts are preserved in interpretation-summary.json, '
        'along with the original frozen strata. No normalized code-structure SHA/co_flags/co_consts are recorded; those details remain Unknown. '
        'A shared source with different wrapper hashes is not treated as a new reward.', '',
        'Gripper command patterns for projected decisions: `' + json.dumps(summary['gripper_projected_decisions']['command_patterns']) + '`. '
        'Positive/negative are actual postprocessed command signs only; physical grasp is Unknown.', '',
        'Target distances, progress and tail-target changes remain Unknown wherever frozen identity did not match. '
        'Continuous EEF tracking errors alone do not prove a reward failure, collision, grasp failure, or benefit of an unexecuted candidate. '
        'This isolated row is not a paired or population performance conclusion. No frozen map, script, threshold, production file or ledger was changed.', '']
    with (out / 'report.md').open('x') as stream:
        stream.write('\n'.join(lines))
    print(json.dumps({'summary': str(out / 'interpretation-summary.json'),
        'exact_matches': exact_matches, 'guided': summary['evidence']['guided'],
        'eligible': len(eligible), 'cuda_initialized': False}))


if __name__ == '__main__':
    main()
