#!/usr/bin/env python3
"""Run only four explicitly authorized post-data identity supplements, CPU-only."""
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
ARTIFACT = ROOT.parents[2]
W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
AUTH_SHA = '6b6d42304f238ed2d88a1689a2ba6becf01761df67c57941b89dc1c26e0a47b6'
HEAD = '0d59b853a241cd88d984f5126428720a14abbfd5'
AUDITOR_SHA = '92a07efed65f900e7acda74e96603b38854ff43f8ec80d0adf40c5e6d2b4bc3f'
PYTHON = '/home/hynx/miniconda3/envs/vla-pilot/bin/python'
KEYS = {'t00-c0': 'observed_pairs_t00_c0_20260923',
        't00-q0': 'observed_pairs_t00_q0_20260923',
        't05-c0': 'observed_pairs_t05_c0_20260923',
        't05-q0': 'observed_pairs_t05_q0_20260923'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save_new(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def event(kind, **values):
    value = {'utc': now(), 'event': kind, **values}
    with (ROOT / 'driver-events.jsonl').open('a') as stream:
        stream.write(json.dumps(value, sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(value), flush=True)


def verify():
    auth_path = ROOT / 'authorization.json'
    assert digest(auth_path) == AUTH_SHA
    auth = json.loads(auth_path.read_text())
    assert auth['rows'] == list(KEYS.values())
    assert subprocess.check_output(['git', '-C', str(W), 'rev-parse', 'HEAD'], text=True).strip() == HEAD
    for name in ('permitted_analysis_script', 'map', 'old_map', 'reproduction', 'derivation_script', 'definitions'):
        assert digest(auth[name]['path']) == auth[name]['sha256'], name
    assert digest(W / 'scripts/audit_decision_evidence.py') == AUDITOR_SHA
    return auth


def stats(values):
    values = [x for x in values if x is not None]
    return ({'n': len(values), 'min': min(values), 'median': statistics.median(values),
             'mean': statistics.mean(values), 'max': max(values)} if values else
            {'n': 0, 'min': None, 'median': None, 'mean': None, 'max': None})


def summarize(result, auth):
    decisions = result['decisions']
    guided = [d for d in decisions if d['guidance']]
    eligible = [d for d in decisions if d['hypothesis_eligible']]
    full = [d for d in eligible if d['diagnostics']['step7_to8'] is not None]
    mapped = [d for d in guided if d['target_review'] is not None]
    identities = collections.Counter()
    for d in guided:
        for identity in d['provider_identities']:
            identities[(identity.get('original_code_sha256'), identity.get('source_text_sha256'),
                        identity.get('source_path'))] += 1
    map_identities = {(entry['original_code_sha256'], entry['source_text_sha256'], entry['source_path'])
                      for entry in json.loads(Path(auth['map']['path']).read_text())['entries']}
    continuous_keys = ('actual_frozen_target_progress_m', 'predicted_frozen_target_progress_m',
                       'progress_optimism_m', 'eef_projection_rmse_m', 'endpoint_projection_error_m',
                       'projected_motion_tracking_gain', 'projected_t0_source_cast_error_m',
                       'endpoint_precision_floor_m')
    a = [d['decision_id'] for d in full if d['diagnostics']['step7_to8']['both_regress_robust']]
    b = [d['decision_id'] for d in eligible if d['diagnostics']['projection_optimism_witness']]
    # Descriptive overlap only; no new criterion is used to accept/reject A or B.
    tail_only_b = [d['decision_id'] for d in full if d['diagnostics']['projection_optimism_witness']
                   and not d['diagnostics']['through_step7']['projection_optimism_witness']]
    return {'schema': 'qd-ed-post-data-identity-supplement-summary-v1', 'post_data': True,
            'authorization_sha256': AUTH_SHA, 'task_id': result['task_id'],
            'episode_seed': result['episode_seed'], 'original_execution_outcome': result['original_execution_outcome'],
            'audit_accepted': result['audit']['accepted'], 'evidence_complete': result['audit']['evidence_complete'],
            'decisions': len(decisions), 'guided_decisions': len(guided),
            'guided_target_triple_matches': sum(count for key, count in identities.items() if key in map_identities),
            'guided_target_resolved_decisions': len(mapped), 'eligible_decisions': len(eligible),
            'eligible_full_eight_step_decisions': len(full),
            'provider_identities': [{'original_code_sha256': key[0], 'source_text_sha256': key[1],
                                     'source_path': key[2], 'count': count, 'triple_in_map': key in map_identities}
                                    for key, count in identities.items()],
            'A_witnesses': len(a), 'A_witness_ids': a, 'B_witnesses': len(b), 'B_witness_ids': b,
            'A_B_overlap_ids': sorted(set(a) & set(b)), 'B_full_chunk_but_not_through_step7_ids': tail_only_b,
            'A_progress_reversal_ids': [d['decision_id'] for d in full if d['diagnostics']['step7_to8']['positive_progress_reversed']],
            'continuous_eligible': {key: stats(d['diagnostics'][key] for d in eligible) for key in continuous_keys},
            'step7_to8_continuous_eligible': {key: stats(d['diagnostics']['step7_to8'][key] for d in full)
                                           for key in ('actual_distance_increase_m', 'predicted_distance_increase_m',
                                                       'actual_progress_through_step7_m', 'actual_progress_through_step8_m')},
            'eligible_projection_dtypes': dict(collections.Counter(d['projection_dtype'] for d in eligible)),
            'actual_eef_dtypes': dict(collections.Counter(step['eef_source_dtype'] for d in decisions for step in d['actual_steps'])),
            'all_prefix_lengths': dict(collections.Counter(str(d['executed_prefix_length']) for d in decisions)),
            'ineligible_reasons': dict(collections.Counter(reason for d in decisions for reason in d['hypothesis_ineligible_reasons'])),
            'unknown_reasons': dict(collections.Counter(reason for d in decisions for reason in d['unknown_reasons'])),
            'strata': result['strata'], 'cuda_initialized_after': result['cuda_initialized_after'],
            'promotion_status': 'NOT_PROMOTED; require independent-episode replication, available predecision signal, recorded-candidate selection change and original protocol approval',
            'limits': ['Post-data identity engineering correction; original frozen-map outputs remain separate.',
                       'Within-episode chunks are correlated, not independent replications.',
                       'Target is the decision-time keypoint, not contemporaneous object pose; EEF progress is not grasp/task success.',
                       'BF16 projections remain BF16-origin despite float64 analysis arithmetic.',
                       'Only selected executed actions have observed outcomes; alternate candidate outcomes Unknown.',
                       'No mechanism, parameter, threshold, promotion condition, or runtime policy changed.',
                       'Wrapper hash variation cause remains Unknown.']}


def execute(label, attempt, audit, auth):
    output = ROOT / label / dt.datetime.now(dt.timezone.utc).strftime('run_%Y%m%dT%H%M%S.%fZ')
    output.mkdir(parents=True, exist_ok=False)
    audit_path = attempt / 'eds_eval/decision-evidence-audit.json'
    episode = attempt / 'eds_eval/decision_evidence/episode_000'
    compute = attempt / 'eds_eval/episode_compute.jsonl'
    assert Path(audit['episode_dir']).resolve() == episode.resolve()
    assert Path(audit['episode_compute_file']).resolve() == compute.resolve()
    status = json.loads((episode / 'status.json').read_text())
    assert status['complete'] is True
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1')
    command = [PYTHON, auth['permitted_analysis_script']['path'], '--episode-dir', str(episode),
               '--episode-compute', str(compute), '--target-map', auth['map']['path'],
               '--output', str(output / 'selected-decision-analysis.json')]
    manifest = {'schema': 'qd-ed-post-data-identity-supplement-invocation-v1', 'started_utc': now(),
                'label': label, 'row_key': KEYS[label], 'attempt_dir': str(attempt),
                'authorization_path': str(ROOT / 'authorization.json'), 'authorization_sha256': AUTH_SHA,
                'driver_path': str(Path(__file__).resolve()), 'driver_sha256': digest(__file__),
                'production_head': HEAD, 'auditor_sha256': AUDITOR_SHA,
                'independent_audit_path': str(audit_path), 'independent_audit_sha256': digest(audit_path),
                'independent_audit_accepted': True, 'independent_evidence_complete': True,
                'source_bindings': {key: auth[key] for key in ('permitted_analysis_script', 'map', 'old_map', 'definitions', 'reproduction', 'derivation_script')},
                'cuda_visible_devices': '', 'post_data': True, 'command': command,
                'original_frozen_outputs_modified': False}
    save_new(output / 'invocation.json', manifest)
    event('analysis_started', label=label, output_dir=str(output))
    started = time.monotonic()
    with (output / 'analyzer.stdout.log').open('x') as stdout, (output / 'analyzer.stderr.log').open('x') as stderr:
        process = subprocess.run(command, cwd=W, env=env, stdout=stdout, stderr=stderr, check=False)
    assert process.returncode == 0, f'analyzer failed rc={process.returncode}; see {output}'
    verify()
    assert digest(audit_path) == manifest['independent_audit_sha256']
    result = json.loads((output / 'selected-decision-analysis.json').read_text())
    assert result['audit']['accepted'] is True and result['audit']['evidence_complete'] is True
    assert result['cuda_initialized_before'] is False and result['cuda_initialized_after'] is False
    summary = summarize(result, auth)
    summary['analysis_sha256'] = digest(output / 'selected-decision-analysis.json')
    summary['analysis_wall_seconds'] = time.monotonic() - started
    save_new(output / 'supplemental-summary.json', summary)
    lines = [f'# {label}: post-data identity supplement', '',
             f"Original outcome: {summary['original_execution_outcome']}; independent audit accepted/complete. "
             f"{summary['guided_target_triple_matches']}/{summary['guided_decisions']} guided target triples match, "
             f"{summary['eligible_decisions']} eligible decisions, {summary['eligible_full_eight_step_decisions']} full-eight prefixes.", '',
             f"Frozen-definition A witnesses: {summary['A_witnesses']}; B witnesses: {summary['B_witnesses']}. "
             'These are correlated within-episode observations, not an algorithm promotion.', '',
             'Full continuous values, witness IDs, eligibility and unchanged strata are in supplemental-summary.json; '
             'all selected-decision trajectories are in selected-decision-analysis.json. Invocation.json binds the authorization, script, map, definitions and original audit.', '',
             *['- ' + text for text in summary['limits']]]
    with (output / 'report.md').open('x') as stream:
        stream.write('\n'.join(lines) + '\n')
    event('analysis_complete', label=label, output_dir=str(output),
          target_triple_matches=summary['guided_target_triple_matches'], guided=summary['guided_decisions'],
          eligible=summary['eligible_decisions'], A_witnesses=summary['A_witnesses'], B_witnesses=summary['B_witnesses'],
          cuda_initialized=False)


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    auth = verify()
    save_new(ROOT / 'driver-start.json', {'utc': now(), 'pid': os.getpid(), 'authorization_sha256': AUTH_SHA,
                                         'driver_sha256': digest(__file__), 'fixed_rows': KEYS, 'cuda_visible_devices': ''})
    pending = dict(KEYS)
    previous = {}
    while pending:
        auth = verify()
        for label, key in list(pending.items()):
            attempts = sorted((ARTIFACT / 'attempts').glob(f'{ARTIFACT.name}__{key}__*'))
            assert len(attempts) <= 1, f'nonunique fixed-row attempt: {key}'
            state = 'waiting_for_attempt'
            audit = None
            if attempts:
                audit_path = attempts[0] / 'eds_eval/decision-evidence-audit.json'
                state = 'waiting_for_complete_independent_audit'
                if audit_path.is_file():
                    try:
                        audit = json.loads(audit_path.read_text())
                    except json.JSONDecodeError:
                        audit = None
            if audit is not None:
                if audit.get('accepted') is True and audit.get('evidence_complete') is True:
                    execute(label, attempts[0], audit, auth)
                else:
                    event('audit_refused_no_analysis', label=label, audit_path=str(audit_path),
                          accepted=audit.get('accepted'), complete=audit.get('evidence_complete'), errors=audit.get('errors'))
                del pending[label]
            elif previous.get(label) != state:
                event(state, label=label)
                previous[label] = state
        if pending:
            time.sleep(15)
    event('all_authorized_rows_finished')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        event('driver_failed', error_type=type(error).__name__, detail=str(error))
        raise
