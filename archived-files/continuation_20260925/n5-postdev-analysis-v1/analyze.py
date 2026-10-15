"""Read-only N5 selected-action projection versus actual EEF feedback analysis."""
import collections
import hashlib
import json
from pathlib import Path

import torch

def run():
    from scripts import audit_decision_evidence as audit
    root = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
    rows = []
    sources = []
    for task in (0, 3, 6, 9):
        base, = (root / 'attempts').glob(f'*n5_dev_t{task:02d}*')
        evidence = base / 'eds_eval/decision_evidence/episode_000'
        status = json.loads((evidence / 'status.json').read_text())
        events = audit.load_events(evidence, status)
        sources.append({'task_id': task, 'status_sha256': hashlib.sha256((evidence / 'status.json').read_bytes()).hexdigest(),
                        'events_index_sha256': hashlib.sha256((evidence / 'events.jsonl').read_bytes()).hexdigest()})
        grouped = collections.defaultdict(lambda: collections.defaultdict(list))
        for event in events:
            grouped[event['decision_id']][event['event']].append(event)
        for decision_id, kinds in grouped.items():
            if not kinds['final_selection']:
                continue
            final = kinds['final_selection'][0]
            grasp = final['values']['terminal_population']['grasp_selection']
            target_index = grasp['target_index']
            if target_index is None:
                continue
            selected = grasp['selected_index'] if 'selected_index' in grasp else final['values']['selected_index']
            scoring = {event['values']['scoring_scope']['iter_idx']: event for event in kinds['scoring_inputs']
                       if event['values']['scoring_scope']['role'] != 'auxiliary_pretest'}
            projected = scoring[9]['values']['projected_xyz'][selected, 1:9].float()
            actuals = kinds['pre_reset_outcome']
            commands = kinds['executed_action']
            count = min(len(actuals), len(commands), 8)
            if count == 0:
                continue
            actual = torch.stack([event['values']['observation']['robot0_eef_pos'].float() for event in actuals[:count]])
            target = scoring[9]['values']['keypoints'][target_index].float()
            errors = torch.linalg.vector_norm(projected[:count] - actual, dim=-1)
            actual_distance = torch.linalg.vector_norm(actual - target, dim=-1)
            projected_distance = torch.linalg.vector_norm(projected[:count] - target, dim=-1)
            positive = [i for i, event in enumerate(commands[:count]) if event['values']['action_numpy'][-1].item() > 0]
            rows.append({'task_id': task, 'decision_id': decision_id, 'global_step': final['global_step'],
                         'stage': kinds['decision_context'][0]['values']['stage'],
                         'selected_index': selected, 'native_argmin_index': grasp['native_argmin_index'],
                         'selector_changed': selected != grasp['native_argmin_index'],
                         'actual_steps': count, 'positive_command_steps': positive,
                         'projected_to_actual_eef_error_m': [float(x) for x in errors],
                         'actual_target_distance_m': [float(x) for x in actual_distance],
                         'projected_target_distance_m': [float(x) for x in projected_distance],
                         'min_actual_target_distance_at_positive_m':
                             min((float(actual_distance[i]) for i in positive), default=None)})
    active = [row for row in rows if row['selector_changed']]
    result = {'schema': 'n5-postdev-selected-projection-feedback-v1', 'sources': sources,
              'scope': 'Executed selected actions only; source-bound target keypoint frozen within each chunk. No rejected-candidate outcomes.',
              'guided_decisions': len(rows), 'selector_changed_decisions': len(active),
              'active_decisions': active,
              'all_selected_eef_error_median_m': float(torch.tensor([x for row in rows for x in row['projected_to_actual_eef_error_m']]).median()),
              'all_selected_eef_error_max_m': max(x for row in rows for x in row['projected_to_actual_eef_error_m']),
              'rows': rows}
    path = Path(__file__).with_name('projection-feedback-v1.json')
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'guided_decisions': len(rows), 'selector_changed_decisions': len(active),
                      'median_eef_error_m': result['all_selected_eef_error_median_m'],
                      'max_eef_error_m': result['all_selected_eef_error_max_m']}))


if __name__ == '__main__':
    run()
