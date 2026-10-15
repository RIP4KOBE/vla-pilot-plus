#!/usr/bin/env python3
"""Read-only normalization reconstruction, not a counterfactual rollout."""
import argparse
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]/'artifacts/stage_closed_loop_20260929/runs'


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def norm(reward, reference):
    return max(0., min(1.2, 1. - reward/reference)) if reference is not None and reference < -1e-6 else 0.


def diagnose(name):
    folder = ROOT/name
    config = yaml.safe_load((folder/'resolved-config.yaml').read_text())
    preserve = bool(config['main'].get('stage_preserve_reward_reference_on_guidance_toggle', False))
    events = rows(folder/'output/eds_eval/stage_events.jsonl')
    metrics = {(r['episode'], r['global_step']): r for r in rows(folder/'output/eds_eval/eds_metrics.jsonl')}
    result = []
    for episode in sorted({r['episode_id'] for r in events}):
        actual_reference = semantic_reference = last_reward = None
        checked = []; differences = []; rebases = []
        for r in (r for r in events if r['episode_id'] == episode):
            step = r['global_step']
            observed = r.get('normalized_reward_diagnostic')
            if r['guidance_before'] and last_reward is not None and observed is not None:
                predicted = norm(last_reward, actual_reference)
                checked.append(abs(predicted-observed) < 1e-10)
                alternate = norm(last_reward, semantic_reference)
                if (r['stage_before'] == r['stage_after'] == 1 and alternate >= .8 > observed
                        and r.get('target_distance_m') is not None and r['target_distance_m'] <= .10):
                    differences.append(dict(step=step, observed_normalized_reward=observed,
                        same_reward_with_stage_entry_reference=alternate, raw_reward=last_reward,
                        actual_reference=actual_reference, stage_entry_reference=semantic_reference,
                        distance_m=r['target_distance_m'], actual_guidance_after=r['guidance_after'],
                        contact_phase=r.get('contact_phase')))
            stage_changed = r['stage_before'] != r['stage_after']
            gate_changed = r['guidance_before'] != r['guidance_after']
            if stage_changed:
                semantic_reference = None
            if stage_changed or (gate_changed and not preserve):
                actual_reference = None
            metric = metrics.get((episode, step))
            if r['guidance_after'] and metric is not None:
                last_reward = metric['selected_reward']
                if semantic_reference is None:
                    semantic_reference = last_reward
                if actual_reference is None:
                    actual_reference = last_reward
                    rebases.append(dict(step=step, stage=r['stage_after'], actual_reference=actual_reference,
                        stage_entry_reference=semantic_reference, differs_from_stage_entry=actual_reference != semantic_reference))
        result.append(dict(episode=episode, task=next(r['task_id'] for r in events if r['episode_id']==episode),
            normalization_samples=len(checked), actual_normalization_exact=bool(checked) and all(checked),
            reference_initializations=rebases, threshold_differences_on_observed_rewards=differences))
    record = dict(run=name, preserve_stage_reference_across_guidance_toggles=preserve, tasks=result,
        note='Actual normalized rewards reconstructed from selected ED reward and current reset behavior. Alternate values reuse observed rewards but retain a reference across guidance-only toggles, like the historical reset rule. They do not predict new trajectories, action ranks, future observations, or success.')
    (folder/'reward-reference-diagnostic.json').write_text(json.dumps(record, indent=2)+'\n')
    for r in result:
        print(dict(task=r['task'], exact=r['actual_normalization_exact'], samples=r['normalization_samples'],
            rebases=sum(x['differs_from_stage_entry'] for x in r['reference_initializations']),
            threshold_differences=[x['step'] for x in r['threshold_differences_on_observed_rewards']]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name')
    diagnose(parser.parse_args().name)
