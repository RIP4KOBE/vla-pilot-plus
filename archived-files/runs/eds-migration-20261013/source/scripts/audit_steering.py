"""Validate complete online cohorts without counting infrastructure errors as failures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.steering_runtime import atomic_json, digest, rows


def audit(folder, *, exit_code=None):
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_text())
    out = folder / 'output'
    invalid_jsonl = []
    def strict_rows(path):
        records = []
        if not path.exists():
            return records
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError('Expected an object')
                records.append(value)
            except (ValueError, TypeError):
                invalid_jsonl.append(f'{path.name}:{number}')
        return records
    events = strict_rows(out / 'eds_eval/stage_events.jsonl')
    metadata = strict_rows(out / 'eds_eval/episode_metadata.jsonl')
    compute = strict_rows(out / 'eds_eval/episode_compute.jsonl')
    metrics = strict_rows(out / 'eds_eval/eds_metrics.jsonl')
    restores = strict_rows(out / 'eds_eval/episode_rng_events.jsonl')
    queries = [r for r in events if r.get('query_status') in ('ok', 'error')]
    status = json.loads((folder / 'status.json').read_text())
    if exit_code is None:
        exit_code = status.get('exit_code')
    checks = {
        'worker_exit': exit_code == status.get('exit_code') == 0,
        'runtime_source_unchanged': status.get('source_unchanged') is True,
        'config_unchanged': digest(folder / 'resolved-config.yaml') == manifest.get('config_sha256'),
        'complete_jsonl': not invalid_jsonl,
        'tasks_and_seeds': [(m.get('task_id'), m.get('episode_seed')) for m in metadata]
            == list(zip(manifest['tasks'], manifest['seeds'])),
        'completed_episodes': len(compute) == len(manifest['tasks']) and
            all(r.get('outcome') == 'completed' for r in compute),
        'compute_episode_identity': [(c.get('episode_id'), c.get('task_id'), c.get('episode_seed'))
                                     for c in compute] ==
            [(i, t, s) for i, (t, s) in enumerate(zip(manifest['tasks'], manifest['seeds']))],
        'no_episode_errors': not list(out.glob('episode_*/error.txt')),
        'online_queries_valid': bool(queries) and all(r.get('query_ok') for r in queries),
        'online_query_for_every_task': all(any(q.get('task_id') == task and q.get('query_ok')
                                             for q in queries) for task in manifest['tasks']),
        'reward_gate': bool(events) and all(not r['guidance_after'] or
            r.get('reward_capability', {}).get('available') for r in events),
        'reward_reference_reset_only_on_stage_change': bool(events) and all(
            r.get('reward_reference_reset') == (r['stage_before'] != r['stage_after']) for r in events),
        'rng_restore_order': [(r['metadata']['task_id'], r['metadata']['episode_seed'], r['metadata']['phase'])
                              for r in restores] ==
            [(t, s, p) for t, s in zip(manifest['tasks'], manifest['seeds']) for p in ('prepare', 'rollout')],
        'source_snapshot_intact': all(digest(folder / 'source' / p) == h
                                     for p, h in manifest['source_sha256'].items()),
    }
    if manifest['method'] in ('eds', 'eds_qd'):
        checks['guided_search_matches_gate'] = [(r['episode_id'], r['global_step']) for r in events
                                                if r['guidance_after']] == [
            (r['episode'], r['global_step']) for r in metrics]
        checks['eds_search_mechanism'] = bool(metrics) and all(
            r.get('population_size') == 16 and r.get('population_size_observed') == 16
            and r.get('eds_iters_executed') == 10 and r.get('execution_horizon_resolved') == 8
            and r.get('initial_sampling_mode') == 'rbf_diverse_denoise'
            and r.get('initial_diversity_fallback_used') is False
            and r.get('rollout_diversity_fallback_used') is False
            and r.get('rollout_diversity_iters_applied') == 10
            and r.get('qd_archive_enabled') is (manifest['method'] == 'eds_qd')
            for r in metrics)
    fixture = json.loads((ROOT / 'tests/fixtures/steering_rng/fixture-manifest.json').read_text())
    checks['rng_states_match'] = bool(restores) and all(
        r['sha256'] == fixture['fixtures'][f"{r['metadata']['task_id']}:{r['metadata']['phase']}"]['sha256']
        and r['state_signature'] == fixture['fixtures'][f"{r['metadata']['task_id']}:{r['metadata']['phase']}"]['state_signature']
        for r in restores)
    from core.stage_fused_carry_hold import audit_checks as carry_checks
    from core.stage_failed_contact_recheck import audit_checks as contact_checks
    checks.update(carry_checks(events))
    checks.update(contact_checks(events))
    task_rows = []
    for i, task in enumerate(manifest['tasks'], 1):
        episode = out / f'episode_{i}'
        videos = list(episode.glob('*agentview.mp4'))
        valid = len(videos) == 1 and not (episode / 'error.txt').exists() and '_error' not in videos[0].name
        contracts = list(episode.rglob('target_distance_reward.json'))
        contract_valid = len(contracts) == 1 and json.loads(contracts[0].read_text()).get('valid') is True
        task_rows.append(dict(task_id=task, episode=i, seed=manifest['seeds'][i-1],
                              valid=valid and contract_valid,
                              success=valid and '_success' in videos[0].name,
                              reward_contract_valid=contract_valid,
                              videos=[str(v.relative_to(folder)) for v in videos]))
    checks['videos_and_reward_contracts'] = all(r['valid'] for r in task_rows)
    successes = sum(r['success'] for r in task_rows)
    result_text = (out / 'results.txt').read_text() if (out / 'results.txt').exists() else ''
    count = re.search(r'Success count:\s*(\d+)/(\d+)', result_text)
    checks['environment_success_count_matches'] = bool(count) and (int(count[1]), int(count[2])) == (
        successes, len(task_rows))
    result = {'method': manifest['method'], 'valid': all(checks.values()), 'checks': checks,
              'completed': sum(r['valid'] for r in task_rows), 'planned': len(task_rows),
              'successes': successes, 'success_task_ids': [r['task_id'] for r in task_rows if r['success']],
              'tasks': task_rows, 'stage_queries': len(queries),
              'infrastructure_error_episodes': len(list(out.glob('episode_*/error.txt'))),
              'invalid_jsonl': invalid_jsonl}
    atomic_json(folder / 'audit.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir')
    args = parser.parse_args()
    result = audit(args.run_dir)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['valid'] else 1)
