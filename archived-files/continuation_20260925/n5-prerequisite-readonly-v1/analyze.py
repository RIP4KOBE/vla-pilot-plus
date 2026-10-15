"""Read-only retrospective activity check for frozen N5 rule on exposed N4 task 9.

This does not replay a simulator, read an outcome, or tune the rule.
"""
import hashlib
import json
from pathlib import Path

import torch

from core.qd_executed_quality import _template_index
from core.qd_grasp_timing import select_grasp_timing
from core.qd_terminal_population import TerminalPopulation
from core.rdt_libero_action_converter import rdt_action_to_libero_raw


EVIDENCE = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/attempts/rdt-qd-ed-final-20260921T093925Z__n4e1_dev_t09_n4_20260924__7a16cf55edcc/eds_eval/decision_evidence/episode_000')
OUTPUT = Path(__file__).with_name('activity-v1.json')


def main():
    rows = []
    references = [json.loads(line) for line in (EVIDENCE / 'events.jsonl').read_text().splitlines()]
    for reference in references:
        path = EVIDENCE / reference['bundle']
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == reference['sha256']
        rows.extend(torch.load(path, map_location='cpu', weights_only=True)['events'])
    decisions = {}
    for row in rows:
        decisions.setdefault(row['decision_id'], []).append(row)
    result = []
    for decision_id, events in decisions.items():
        kinds = {}
        for event in events:
            kinds.setdefault(event['event'], []).append(event)
        final_rows = kinds.get('final_selection', [])
        if len(final_rows) != 1 or final_rows[0]['values'].get('selection_rule') != 'terminal_population_first_argmin':
            continue
        final = final_rows[0]['values']
        terminal = final['terminal_population']
        source = next(row for row in kinds['scoring_inputs'] if row['sequence'] == terminal['scoring_batch_id'])
        context = kinds['decision_context'][0]['values']
        provider = context['providers'][0]
        source_text = Path(provider['source_path']).read_text()
        assert hashlib.sha256(source_text.encode()).hexdigest() == provider['source_text_sha256']
        _, _, target_index = _template_index(source_text)
        pop = TerminalPopulation.capture(final['population'], terminal['native_costs'],
            terminal['raw_provider_quality'], terminal['cell_ids'], terminal['parent_cell_ids'])
        selected = select_grasp_timing(pop, source['values']['projected_xyz'],
            rdt_action_to_libero_raw(pop.actions[:, :8, :]), source['values']['keypoints'],
            target_index=target_index, recognition_reason='recognized_weighted_distance_template')
        assert selected.native_argmin_index == final['selected_index']
        result.append({'decision_id': decision_id, 'global_step': context['global_step'] if 'global_step' in context else final_rows[0]['global_step'],
            'n4_index': selected.native_argmin_index, 'n5_rule_index': selected.index,
            'eligible_indices': selected.eligible_indices, 'best_reach_m': selected.best_reach_m,
            'n5_selected_positive_steps': torch.nonzero(selected.positive_commands[selected.index], as_tuple=False).reshape(-1).tolist()})
    output = {'schema': 'n5-exposed-task9-retrospective-activity-v1',
              'source_evidence': str(EVIDENCE), 'decisions': result,
              'decisions_count': len(result),
              'eligible_decisions': sum(bool(item['eligible_indices']) for item in result),
              'changed_decisions': sum(item['n4_index'] != item['n5_rule_index'] for item in result),
              'scope': 'existing N4 final rows; no N5 rollout or task-success inference'}
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: output[key] for key in ('decisions_count', 'eligible_decisions', 'changed_decisions')}))


if __name__ == '__main__':
    main()
