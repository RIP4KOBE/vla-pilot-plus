"""Bounded CPU audit of one exposed valid development Q0; no re-evaluation."""
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
import torch
assert not torch.cuda.is_initialized()
torch.set_num_threads(1)

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
SOURCE = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/attempts/rdt-qd-ed-final-20260921T093925Z__n1r_dev_t00_q0__f27eacd7e033')
C0 = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/external-valid-c0-readonly/observation-summary.json')
OUT = Path(__file__).resolve().parent
COMMIT = '9ba5f628a6b13dde4f707876ff8312b49a46c319'
INPUTS = {}


def read(path):
    data = path.read_bytes(); INPUTS[str(path)] = hashlib.sha256(data).hexdigest(); return data


def jsonl(path):
    return [json.loads(line) for line in read(path).splitlines()]


def summary(values):
    return {'count': len(values), 'min': min(values), 'max': max(values),
            'mean': statistics.mean(values), 'median': statistics.median(values)} if values else None


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


# These two pure CPU helpers are byte-identical to the recorded execution source.
for name in ('core/qd_ed.py', 'core/rdt_libero_action_converter.py'):
    assert read(W / name) == subprocess.check_output(['git', 'show', COMMIT + ':' + name], cwd=W)
sys.path.insert(0, str(W))
from core.qd_ed import QDBounds, cell_ids, fingerprint_action
from core.rdt_libero_action_converter import rdt_action_to_libero_raw

metrics = jsonl(SOURCE / 'eds_eval/eds_metrics.jsonl')
stages = jsonl(SOURCE / 'eds_eval/stage_events.jsonl')
compute = jsonl(SOURCE / 'eds_eval/episode_compute.jsonl')[0]
attempt = json.loads(read(SOURCE / 'attempt-result.json'))
c0_summary = json.loads(read(C0))
read(SOURCE / 'eds_eval/episode_metadata.jsonl')
ledger_rows = [json.loads(line) for line in (W / 'data/attempt-ledger.jsonl').read_text().splitlines()
               if 'f27eacd7e033' in line]
terminal = ledger_rows[-1]
assert terminal['event'] == 'valid' and terminal['outcome_valid'] is True and terminal['success'] is False
assert terminal['identity']['split'] == 'dev' and terminal['physical_gpu'] == 2
assert Path(terminal['output_dir']) == SOURCE and terminal['source_commit'] == COMMIT
write('source-ledger-excerpt.json', [{k: row.get(k) for k in ('event', 'attempt_id', 'identity', 'physical_gpu',
      'source_commit', 'output_dir', 'outcome_valid', 'success', 'gpu_process_wall_seconds')} for row in ledger_rows])

# Only two already-saved trace files; auxiliary trace stages are excluded.
trace_by_step = {}
for path in sorted(SOURCE.rglob('mechanism_trace.pt')):
    read(path)
    payload = torch.load(path, map_location='cpu', weights_only=True)
    assert not torch.cuda.is_initialized()
    selected = [s for s in payload['stages'] if s['stage'] in {'initial', 'full_process_after_rollout'}]
    mapping = {-1 if s['stage'] == 'initial' else int(s['iter_idx']): s for s in selected}
    assert len(mapping) == 11
    trace_by_step[int(payload['metadata']['global_step'])] = {'path': str(path), 'stages': mapping}

chunk_rows, discarded_rows, trace_rows, all_quality, parent_rows = [], [], [], [], []
replay_checks = collections.Counter()
all_initial_inserts = all_inserts = all_replacements = all_rejections = all_candidates = 0
best_without_parent = 0
population_below_archive = 0
for m in metrics:
    step = m['global_step']
    assert m['qd_archive_active_for_chunk'] and m['qd_bounds_update_policy'] == 'fixed_initial'
    assert m['qd_cell_capacity'] == 1 and m['qd_secondary_lane_mode'] == 'none'
    assert m['qd_descriptor'] == 'target_relative_endpoint_xy'
    bounds = QDBounds(torch.tensor(m['qd_bounds_xy_m'][0]), torch.tensor(m['qd_bounds_xy_m'][1]), '')
    # Bounds telemetry is [lo_xy, hi_xy], verified against every reported occupancy/update.
    archive = {}
    canonical_rows = m['shadow_qd_candidate_stream']
    assert [row['iter_idx'] for row in canonical_rows] == list(range(-1, 10))
    trace = trace_by_step.get(step)
    observed_actions = 0
    grip_patterns = collections.Counter()
    selected_record = None
    for batch in canonical_rows:
        iteration = int(batch['iter_idx'])
        assigned, overflow = cell_ids(torch.tensor(batch['descriptors_xy_m']), bounds, m['qd_grid_shape'])
        saved = trace['stages'][iteration] if trace else None
        if saved:
            assert all(value.device.type == 'cpu' for value in saved.values() if torch.is_tensor(value))
            assert saved['actions'].dtype == torch.bfloat16 and saved['trajectories'].shape == (16, 7, 3)
            assert [fingerprint_action(row) for row in saved['actions']] == batch['fingerprints']
            assert saved['rewards'].float().tolist() == batch['rewards']
            decoded = rdt_action_to_libero_raw(saved['actions'][:, :8])
            observed_actions += 16
            grip_patterns.update(''.join('+' if x > 0 else '-' for x in row.tolist()) for row in decoded[:, :, 6])
        previous_best = min(archive.values(), key=lambda x: (-x['reward'], x['fingerprint'], x['cell'])) if archive else None
        if iteration >= 0 and previous_best is not None:
            slots = m['qd_parent_slots_by_cell_by_iter'][iteration].get(str(previous_best['cell']), 0)
            best_without_parent += int(slots == 0)
            parent_rows.append({'global_step': step, 'iter_idx': iteration,
                'previous_archive_best_cell': previous_best['cell'],
                'previous_archive_best_fingerprint': previous_best['fingerprint'],
                'previous_archive_best_reward': previous_best['reward'], 'allocated_parent_slots': slots})
        groups = collections.defaultdict(list)
        for row, (cell, quality, fp, xy) in enumerate(zip(assigned.tolist(), batch['rewards'], batch['fingerprints'], batch['descriptors_xy_m'])):
            item = {'step': step, 'iter_idx': iteration, 'row': row, 'cell': cell,
                    'reward': quality, 'fingerprint': fp, 'xy': xy}
            if saved:
                grip = decoded[row, :, 6].to(torch.int64).tolist()
                item.update(gripper_pattern=grip, positive_gripper_duty=sum(v > 0 for v in grip) / 8,
                            stored_t7_z=float(saved['trajectories'][row, -1, 2]),
                            raw_t8_dz=float(saved['actions'][row, 7, 41]))
            groups[cell].append(item)
        counts = collections.Counter()
        for cell, rows in groups.items():
            new_best = min(rows, key=lambda x: (-x['reward'], x['fingerprint']))
            old = archive.get(cell)
            change = old is None or (-new_best['reward'], new_best['fingerprint']) < (-old['reward'], old['fingerprint'])
            retained = new_best if change else old
            if change:
                counts['insertions' if old is None else 'replacements'] += 1
                archive[cell] = retained
                counts['rejections'] += len(rows) - 1
            else:
                counts['rejections'] += len(rows)
            if saved:
                discarded = [(item, 'rejected_current_candidate') for item in rows if item is not retained]
                if change and old is not None:
                    discarded.append((old, 'evicted_prior_elite'))
                for item, reason in discarded:
                    different = item['fingerprint'] != retained['fingerprint']
                    discarded_rows.append({'step': step, 'update_iter': iteration, 'cell': cell, 'reason': reason,
                        'discarded_iter': item['iter_idx'], 'discarded_row': item['row'],
                        'discarded_fp': item['fingerprint'], 'retained_iter': retained['iter_idx'],
                        'retained_row': retained['row'], 'retained_fp': retained['fingerprint'],
                        'distinct_action': different, 'discarded_reward': item['reward'], 'retained_reward': retained['reward'],
                        'quality_tie': item['reward'] == retained['reward'],
                        'gripper_pattern_differs': item['gripper_pattern'] != retained['gripper_pattern'],
                        'discarded_gripper': ''.join('+' if x > 0 else '-' for x in item['gripper_pattern']),
                        'retained_gripper': ''.join('+' if x > 0 else '-' for x in retained['gripper_pattern']),
                        'discarded_positive_duty': item['positive_gripper_duty'],
                        'retained_positive_duty': retained['positive_gripper_duty'],
                        'stored_t7_z_abs_difference_m': abs(item['stored_t7_z'] - retained['stored_t7_z']),
                        'descriptor_t8_xy_distance_m': sum((a-b)**2 for a,b in zip(item['xy'], retained['xy'])) ** .5,
                        'raw_t8_dz_abs_difference': abs(item['raw_t8_dz'] - retained['raw_t8_dz'])})
        assert sum(counts.values()) == 16
        all_candidates += 16
        if iteration == -1:
            assert all(counts[k] == m['qd_initial_accounting'][k] for k in ('insertions', 'replacements', 'rejections'))
            assert len(archive) == m['qd_initial_occupied_cells']
            all_initial_inserts += counts['insertions']
        else:
            for key in ('insertions', 'replacements', 'rejections'):
                assert counts[key] == m['qd_archive_' + key + '_by_iter'][iteration], (step, iteration, key)
            assert len(archive) == m['qd_occupied_cells_by_iter'][iteration]
            assert max(x['reward'] for x in archive.values()) == m['qd_archive_best_reward_by_iter'][iteration]
            actual_per_cell = m['qd_per_cell_elite_reward_by_iter'][iteration]
            assert {str(k): v['reward'] for k,v in archive.items()} == actual_per_cell
            population_below_archive += int(max(batch['rewards']) < max(x['reward'] for x in archive.values()))
            replay_checks['matched_iteration_archives'] += 1
        all_inserts += counts['insertions']; all_replacements += counts['replacements']; all_rejections += counts['rejections']
        all_quality.append({'global_step': step, 'iter_idx': iteration, 'unique_quality_values': len(set(batch['rewards'])),
                            'quality_min': min(batch['rewards']), 'quality_max': max(batch['rewards'])})
    selected_record = min(archive.values(), key=lambda x: (-x['reward'], x['fingerprint'], x['cell']))
    assert selected_record['fingerprint'] == m['qd_selected_action_fingerprint'] == m['qd_global_best_action_fingerprint']
    assert selected_record['reward'] == m['selected_reward'] == m['final_best_reward']
    replay_checks['matched_final_selections'] += 1
    chunk_rows.append({'global_step': step, 'initial_best_reward': m['initial_best_reward'],
        'selected_reward': m['selected_reward'], 'quality_gain': m['selected_reward'] - m['initial_best_reward'],
        'initial_occupied': m['qd_initial_occupied_cells'], 'final_occupied': len(archive),
        'selected_source_iter': selected_record['iter_idx'], 'selected_cell': selected_record['cell'],
        'target_distance_before': m['target_distance_before'], 'target_distance_after': m['target_distance_after'],
        'selected_fingerprint': selected_record['fingerprint']})
    if trace:
        trace_rows.append({'global_step': step, 'trace_path': trace['path'], 'canonical_rows_verified': observed_actions,
                           'decoded_eight_command_gripper_patterns': dict(grip_patterns),
                           'source_actions_dtype': 'bfloat16', 'stored_projection_points': 't1..t7, seven XYZ points',
                           'selected': selected_record, 'actual_t8_z_available': False})

assert not torch.cuda.is_initialized()
safe_stages = [{k:r[k] for k in ('global_step', 'stage_before', 'stage_after', 'guidance_before', 'guidance_after',
                               'query_ok', 'query_status', 'first_gripper_value', 'last_gripper_value')} for r in stages]
distinct = [r for r in discarded_rows if r['distinct_action']]
grip_diff = [r for r in distinct if r['gripper_pattern_differs']]
report = {'scope': 'one externally exposed valid dev Q0 on GPU2; no matched GPU3 or C0 performance comparison',
    'attempt_id': terminal['attempt_id'], 'physical_gpu': 2, 'outcome_valid': True, 'success': False,
    'gpu_process_wall_seconds': terminal['gpu_process_wall_seconds'], 'source_commit': COMMIT,
    'cpu_safety': {'cuda_visible_devices': '', 'torch_load_map_location': 'cpu', 'weights_only': True,
                   'cuda_initialized_before': False, 'cuda_initialized_after': torch.cuda.is_initialized(),
                   'loaded_tensor_files': len(trace_by_step), 'no_provider_or_simulation_evaluation': True},
    'compute': {k:compute[k] for k in ('outcome', 'guided_chunks', 'unguided_chunks', 'reward_calls',
               'reward_scoring_batches', 'model_forward_calls', 'model_batch_rows', 'dino_forward_calls',
               'stage_codex_logical_call_attempts', 'stage_codex_completed_turns', 'stage_codex_failed_calls',
               'stage_codex_call_latency_s')},
    'qd': {'active_chunks': len(metrics), 'canonical_candidate_occurrences': all_candidates,
           'archive_insertions': all_inserts, 'archive_replacements': all_replacements, 'archive_rejections': all_rejections,
           'initial_insertions': all_initial_inserts, 'replay_checks': dict(replay_checks),
           'grid_shape': [4,4], 'cell_capacity': 1, 'descriptor': 'target_relative_endpoint_xy',
           'parent_sampling': 'sparse_priority', 'bounds_policy': 'fixed_initial', 'secondary_lane': 'none',
           'fallback_chunks': sum(bool(m['qd_fallback_used']) for m in metrics),
           'best_archive_elite_missing_parent_slot_iterations': best_without_parent,
           'population_best_below_retained_archive_best_iterations': population_below_archive,
           'initial_occupied': summary([r['initial_occupied'] for r in chunk_rows]),
           'final_occupied': summary([r['final_occupied'] for r in chunk_rows])},
    'quality': {'final_vs_initial_improved_chunks': sum(r['quality_gain'] > 0 for r in chunk_rows),
                'final_vs_initial_equal_chunks': sum(r['quality_gain'] == 0 for r in chunk_rows),
                'final_vs_initial_worse_chunks': sum(r['quality_gain'] < 0 for r in chunk_rows),
                'within_chunk_quality_gain': summary([r['quality_gain'] for r in chunk_rows]),
                'all_equal_canonical_batches': sum(r['unique_quality_values'] == 1 for r in all_quality),
                'canonical_batches': len(all_quality),
                'selected_source_iter_counts': dict(collections.Counter(r['selected_source_iter'] for r in chunk_rows)),
                'interpretation': 'stored provider/search quality only, not task success or between-stage calibrated score'},
    'trace_mechanism': {'traced_global_steps': sorted(trace_by_step),
        'canonical_action_rows_verified': sum(r['canonical_rows_verified'] for r in trace_rows),
        'discard_events': len(discarded_rows), 'distinct_action_discard_events': len(distinct),
        'discard_event_reasons': dict(collections.Counter(r['reason'] for r in discarded_rows)),
        'quality_tie_discard_events': sum(r['quality_tie'] for r in discarded_rows),
        'gripper_pattern_diff_discard_events': len(grip_diff),
        'positive_duty_diff_discard_events': sum(r['discarded_positive_duty'] != r['retained_positive_duty'] for r in distinct),
        'gripper_pattern_diff_quality_ties': sum(r['quality_tie'] for r in grip_diff),
        'discarded_with_higher_stored_quality': sum(r['discarded_reward'] > r['retained_reward'] for r in distinct),
        'different_stored_t7_z_discard_events': sum(r['stored_t7_z_abs_difference_m'] > 0 for r in distinct),
        'stored_t7_z_difference_m': summary([r['stored_t7_z_abs_difference_m'] for r in distinct]),
        'descriptor_t8_xy_distance_m': summary([r['descriptor_t8_xy_distance_m'] for r in distinct]),
        'events_are_not_independent': True,
        'interpretation': 'Observed archive compression of alternatives; no evidence discarded alternatives would succeed'},
    'stage': {'events': len(stages), 'query_ok_count': sum(bool(r['query_ok']) for r in stages),
              'stage_after_counts': dict(collections.Counter(r['stage_after'] for r in stages)),
              'guidance_toggles': sum(r['guidance_before'] != r['guidance_after'] for r in stages),
              'interpretation': 'observed Stage switches; correctness and causality are not inferred'},
    'external_c0_context_only': {'summary_path': str(C0), 'attempt_id': c0_summary['source_attempt'],
                                'success': c0_summary['task_success'], 'matched_comparison': False},
    'missing_evidence': ['actual per-action EEF/gripper outcomes and contemporaneous object/target poses',
        'complete raw candidate actions/projections for 50 of the 52 guided chunks',
        'full t0..t8 native-precision projection and actual t8 XYZ for saved traces',
        'raw per-provider returns with canonical scoring occurrence linkage',
        'final decoded dispatched action to each step outcome linkage, including terminal before automatic reset',
        'outcomes of unexecuted candidates and within-cell discarded alternatives',
        'a matched current-root C0/Q0 comparison and subsequent independent algorithm evidence'],
    'analysis_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'input_sha256': INPUTS}
write('observation-summary.json', report)
write('stage-events-sanitized.json', safe_stages)
write('saved-trace-identity-summary.json', trace_rows)
for name, rows in [('chunks.csv', chunk_rows), ('canonical-quality.csv', all_quality), ('within-cell-discard-events.csv', discarded_rows), ('archive-best-parent-slots.csv', parent_rows)]:
    with (OUT/name).open('w', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
print(json.dumps({k:report[k] for k in ('qd','quality','trace_mechanism','stage')},indent=2))
