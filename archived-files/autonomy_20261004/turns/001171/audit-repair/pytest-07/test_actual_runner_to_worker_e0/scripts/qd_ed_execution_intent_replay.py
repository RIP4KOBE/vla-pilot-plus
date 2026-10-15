#!/usr/bin/env python3
"""CPU fixed-pool N1 replay; no model/environment calls or counterfactual SR.

Historical t8-Z is not serialized. This explicitly approximate radial replay
uses stored t8 XY and saved t7 Z + the eighth action's projected Z delta. Exact
legacy reward/fingerprint replay and exact gripper-duty evidence stay separate.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.qd_ed import (QDArchive, QDBounds, EXECUTION_INTENT_DESCRIPTOR,
    allocate_parent_slots, cell_ids, execution_intent_descriptor,
    fingerprint_action, freeze_execution_intent_bounds)
from core.rdt_libero_action_converter import rdt_action_to_libero_raw


def replay(path: Path, elimination_trace: dict) -> dict:
    raw = torch.load(path, map_location='cpu', weights_only=True)
    q = raw['qd_info']
    meta = raw['metadata']
    stages = {s['iter_idx']: s for s in raw['stages'] if s['stage'] == 'full_process_after_rollout'}
    stages[-1] = next(s for s in raw['stages'] if s['stage'] == 'initial')
    q0 = QDArchive(grid_shape=(4, 4))
    n1 = QDArchive(grid_shape=(4, 4), descriptor_mode=EXECUTION_INTENT_DESCRIPTOR)
    bounds0 = QDBounds(torch.tensor(q['qd_bounds_xy_m'][0]), torch.tensor(q['qd_bounds_xy_m'][1]), q['qd_bounds_source_initial_checksum'])
    target = raw['keypoints'].float().reshape(-1, 3)[0]
    events_by_iteration = collections.defaultdict(list)
    for e in elimination_trace['eliminations']:
        events_by_iteration[e['batch_iteration']].append(e)
    counts = collections.Counter()
    steps = []
    proposals = {}
    pending_retained = []
    for stream in q['shadow_qd_candidate_stream']:
        iteration = stream['iter_idx']
        stage = stages[iteration]
        actions = stage['actions']
        rewards = torch.tensor(stream['rewards'])
        for fp, action in zip(stream['fingerprints'], actions, strict=True):
            if fingerprint_action(action) != fp:
                raise ValueError('Saved action/fingerprint mismatch')
        if iteration >= 0:
            kwargs = dict(population_size=16, sampling='sparse_priority', sparse_exponent=1.,
                          run_seed=0, episode=meta['episode'], global_step=meta['global_step'], iter_idx=iteration)
            parents0 = allocate_parent_slots(q0, **kwargs)
            parents1 = allocate_parent_slots(n1, **kwargs)
            counts['parent_batches'] += 1
            counts['parent_batches_with_changed_fingerprint_multiset'] += int(collections.Counter(parents0.parent_fingerprints) != collections.Counter(parents1.parent_fingerprints))
            counts['parent_slots_with_changed_identity'] += sum(a != b for a,b in zip(parents0.parent_fingerprints, parents1.parent_fingerprints, strict=True))
            counts['previous_discordant_eliminations_retained_and_sampled_next_iteration'] += sum(fp in parents1.parent_fingerprints for fp in pending_retained)
            if sum(parents0.slot_counts.values()) != 16 or sum(parents1.slot_counts.values()) != 16:
                raise ValueError('Parent accounting violation')
        descriptor0 = torch.tensor(stream['descriptors_xy_m'])
        # XY is exact saved QD data. Z is an approximation explicitly kept out
        # of the exact legacy/decoder validity gates.
        endpoint = torch.empty(actions.shape[0], 3)
        endpoint[:, :2] = descriptor0 + target[:2]
        endpoint[:, 2] = stage['trajectories'][:, -1, 2].float() + actions[:, 7, 41].float() * .01
        projected = torch.zeros(actions.shape[0], 9, 3)
        projected[:, 8] = endpoint
        decoded = rdt_action_to_libero_raw(actions[:, :8])
        descriptor1 = execution_intent_descriptor(projected, raw['keypoints'], decoded)
        if iteration == -1:
            bounds1 = freeze_execution_intent_bounds(descriptor1, quantiles=(.05,.95), expand_fraction=.1, min_axis_span_m=.08)
        cells0, _ = cell_ids(descriptor0, bounds0, (4,4))
        cells1, _ = cell_ids(descriptor1, bounds1, (4,4))
        # Pair-count measures aliases introduced/lifted in this same saved pool.
        for i in range(len(actions)):
            for j in range(i):
                counts['new_alias_candidate_pairs'] += int(cells0[i] != cells0[j] and cells1[i] == cells1[j])
                counts['resolved_alias_candidate_pairs'] += int(cells0[i] == cells0[j] and cells1[i] != cells1[j])
        for fp, c0, c1, d1, r in zip(stream['fingerprints'], cells0.tolist(), cells1.tolist(), descriptor1.tolist(), stream['rewards'], strict=True):
            proposals[fp] = {'q0_cell': c0, 'n1_cell': c1, 'positive_duty': d1[1], 'reward': r}
        for archive, descriptor, ids in ((q0, descriptor0, cells0), (n1, descriptor1, cells1)):
            update = archive.update(actions=actions, rewards=rewards, costs=-rewards,
                                    descriptors=descriptor, cell_ids=ids, source_iter=iteration)
            if update.total != 16 or len(archive.entries) > 16:
                raise ValueError('Archive accounting/capacity violation')
        best0 = q0.select_global_best()[1]
        best1 = n1.select_global_best()[1]
        if best0.fingerprint != best1.fingerprint or best0.reward != max(v['reward'] for v in proposals.values()):
            raise ValueError('Global quality invariant violated')
        if iteration >= 0 and {str(k): v.reward for k,v in sorted(q0.entries.items())} != q['qd_per_cell_elite_reward_by_iter'][iteration]:
            raise ValueError('Exact Q0 replay mismatch')
        survivors1 = {entry.fingerprint for entry in n1.entries.values()}
        pending_retained = [e['loser']['fingerprint'] for e in events_by_iteration[iteration] if e['loser']['fingerprint'] in survivors1]
        counts['discordant_elimination_occurrences_surviving_after_same_update'] += len(pending_retained)
        counts['updates'] += 1
        steps.append({'iteration': iteration, 'q0_survivors': [e.fingerprint for e in q0.entries.values()],
                      'n1_survivors': sorted(survivors1), 'rescued_discordant_occurrences': pending_retained,
                      'q0_xy_cells_represented_by_n1_survivors': len({proposals[fp]['q0_cell'] for fp in survivors1}),
                      'q0_duty_bin_count': len({min(int(4*proposals[e.fingerprint]['positive_duty']),3) for e in q0.entries.values()}),
                      'n1_duty_bin_count': len({min(int(4*proposals[fp]['positive_duty']),3) for fp in survivors1}),
                      'global_best_fingerprint': best0.fingerprint})
    if q0.select_global_best()[1].fingerprint != q['qd_selected_action_fingerprint']:
        raise ValueError('Exact legacy final selection mismatch')
    counts['discordant_eliminations_present_in_final_n1_archive'] = sum(e['loser']['fingerprint'] in survivors1 for e in elimination_trace['eliminations'])
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'task_id':meta['task_id'], 'global_step':meta['global_step'], 'counts':dict(counts),
            'radial_reconstruction_exact':False, 'legacy_selection_replay_exact':True,
            'n1_global_reward_best_preserved_for_reconstructed_fixed_pool':True,
            'bounds': [bounds1.lo.tolist(),bounds1.hi.tolist()], 'updates':steps}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=json.loads(args.diagnostic.read_text())
    traces=[replay(Path(t['source']),t) for t in source['traces']]
    total=collections.Counter()
    for t in traces:total.update(t['counts'])
    result={'schema':'qd-ed-execution-intent-fixed-pool-replay-v1','protocol_commit':'56031d2a6136d6d1f0d0cb95c7d42f77a8158da3',
            'summary':{'traces':len(traces),'counts':dict(total),'exact_radial_reconstruction':False,
                       'legacy_replay_exact':True,'global_best_invariant_pass':True},
            'reconstruction':{'t8_xy':'stored exact descriptor plus keypoint0',
                              't8_z':'approximate: saved BF16 t7Z + float32 eighth Z action *0.01',
                              'exact_recovery_attempt':'No BF16 start coordinate reproduced all seven stored positions across all candidate streams for any of20 traces under CPU projector arithmetic; no exact t8Z identity claimed.',
                              'implication':'N1 survival/allocation/new-alias counts are descriptive approximate replay; cannot gate acceptance as exact historical counterfactual or task gain.'},
            'allocation_rng':{'run_seed':0,'episode':'saved episode index','global_step':'saved global step','meaning':'same deterministic sampling rule for both reconstructed archives; saved offspring remain fixed despite changed parents'},
            'no_new_episodes':True,'gpu_calls':0,'model_calls':0,'environment_calls':0,
            'input_sha256':hashlib.sha256(args.diagnostic.read_bytes()).hexdigest(),
            'source_fingerprints':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'core/qd_ed.py',ROOT/'core/rdt_libero_action_converter.py']},
            'traces':traces}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':main()
