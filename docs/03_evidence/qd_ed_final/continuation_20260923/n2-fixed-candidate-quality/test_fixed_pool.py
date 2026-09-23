"""Disposable native CPU fixtures; never open recorded runtime bundles."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_fixed_pool as n

a = n.module('n2_test_selected', HERE.parent/'decision-analysis-draft/analyze_episode.py')
c = n.module('n2_test_history', HERE.parent/'candidate-tail-availability/check_candidates.py')
m = n.module('n2_test_membership', HERE.parent/'final-population-membership/check_membership.py')
HELPER = Path(os.environ.get('N2_QUALITY_HELPER', '/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-executed-quality-20260923/core/qd_executed_quality.py'))
h = n.module('n2_test_quality', HELPER)
torch = a.cpu_torch()


def fixture(profile='C0', actual_A=True, mode='changed'):
    population = torch.zeros(3, 64, 128, dtype=torch.bfloat16)
    population[1, :8, 39] = .125
    population[2, :8, 39] = .25
    points = torch.zeros(3, 9, 3, dtype=torch.bfloat16)
    points[:2, 1:, 0] = .125
    points[2, 8, 0] = 1
    quality = torch.tensor([-.015625, -.015625, 0], dtype=torch.bfloat16)
    if mode == 'all_tied':
        points[:, 1:, 0] = .125
        quality[:] = -.015625
    keypoints = torch.tensor([[10, 10, 10], [0, 0, 0]], dtype=torch.bfloat16)
    identity = ('a'*64, 'b'*64, '/synthetic/provider.txt')
    entry = {'original_code_sha256': identity[0], 'source_text_sha256': identity[1], 'source_path': identity[2],
             'keypoint_index': 1, 'target_selection': 'fixed_keypoint_index',
             'distance_progress_interpretation': 'approach_proxy', 'target_expression': 'keypoints[1]'}
    context = {'use_guidance': True, 'keypoints': keypoints.clone(), 'providers': [entry.copy()]}
    rows = []
    def event(name, **values):
        row = {'event': name, 'sequence': len(rows)+1, 'decision_id': 'e0:d1:s0', 'values': values}
        rows.append(row)
        return row['sequence']
    event('decision_context', **context)
    for iteration in [-1, 0]:
        origins = [event('projection_origin', source_eef_position=points[i, 0].clone()) for i in range(3)]
        score = event('scoring_inputs', samples=population.clone(), projected_xyz=points.clone(),
            provider_input_xyz=points[:, 1:8].clone(), keypoints=keypoints.clone(), projection_origin_sequences=origins,
            slice_kind='eds', scoring_scope={'role': 'canonical_initial' if iteration == -1 else 'canonical_iteration', 'iter_idx': iteration})
        event('effective_quality', scoring_batch_id=score, quality=quality.clone(), reward_mode='normal')
        event('canonical_candidate_batch', candidates=population.clone(), effective_quality=quality.clone(), iter_idx=iteration,
            occurrence_ids=[f'e0:d1:s0:q{iteration}:r{i}' for i in range(3)],
            canonical_fingerprints=[a.fingerprint(x) for x in population])
    selected_fp = a.fingerprint(population[2])
    event('final_selection', population=population.clone(), selected_latent=population[2:].clone(), selected_index=2,
        # Like Q0's FP32 carrier, this scalar is exactly the original BF16 value.
        selected_quality=quality[2].float(), selected_canonical_fingerprint=selected_fp,
        selection_rule='cost_argmin' if profile == 'C0' else 'archive_global_best')
    event('policy_action_decode', selected_canonical_fingerprint=selected_fp)
    analysis = {'decision_id': 'e0:d1:s0', 'global_step': 0, 'stage': 1, 'guidance': True,
        'hypothesis_eligible': True, 'command_translation_matches_projection_source': True, 'frozen_target': [0., 0., 0.],
        'diagnostics': {'step7_to8': {'both_regress_robust': actual_A}, 'projection_optimism_witness': False}}
    return rows, analysis, {identity: entry}


def run_fixture(rows, analysis, targets, profile='C0', helper=None):
    history = c.analyze_decision(rows, analysis, targets, a)
    membership = m.inspect_decision(rows, history, profile, a, c)
    return n.rerank_decision(rows, history, membership, analysis, targets, profile, a, c, m,
                             helper or h.executed_prefix_quality)


class FixedPoolTests(unittest.TestCase):
    def test_C0_native_quality_all_ties_and_old_tradeoff(self):
        rows, analysis, targets = fixture()
        rng = torch.get_rng_state().clone()
        result = run_fixture(rows, analysis, targets)
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        self.assertEqual(result['all_exact_maximum_slots'], [0, 1])
        self.assertTrue(result['tie_robust_changed'])
        self.assertEqual(result['deterministic_representative_slot'], 0)
        self.assertEqual(result['q8_maximum'], -.015625)
        self.assertEqual(result['q8_dtype'], 'torch.bfloat16')
        self.assertEqual(result['all_exact_maximum_original_quality_tradeoffs'], [-.015625, -.015625])
        self.assertEqual(result['slots'][2]['projected_distance8_m'], 1.)
        self.assertEqual(result['slots'][2]['projected_distance7_m'], 0.)
        self.assertEqual(result['slots'][0]['target_identity']['keypoint_index'], 1)
        self.assertFalse(torch.cuda.is_initialized())

    def test_Q0_all_native_occurrences_retained_once_per_final_slot(self):
        rows, analysis, targets = fixture('Q0')
        calls = []
        def spy(projection, keypoints, **kwargs):
            calls.append((projection.dtype, kwargs['target_index']))
            return h.executed_prefix_quality(projection, keypoints, **kwargs)
        result = run_fixture(rows, analysis, targets, 'Q0', spy)
        self.assertEqual(calls, [(torch.bfloat16, 1)]*3)
        self.assertTrue(all(len(slot['used_occurrence_ids']) == 2 for slot in result['slots']))
        self.assertTrue(all(slot['insertion_occurrence'] == 'Unknown' for slot in result['slots']))
        self.assertEqual(result['deterministic_representative_fingerprint'], min(result['all_exact_maximum_fingerprints']))

    def test_tie_including_actual_selection_is_not_activity(self):
        rows, analysis, targets = fixture(mode='all_tied')
        result = run_fixture(rows, analysis, targets)
        self.assertEqual(result['all_exact_maximum_slots'], [0, 1, 2])
        self.assertTrue(result['deterministic_representative_changed'])
        self.assertFalse(result['tie_robust_changed'])
        self.assertTrue(result['mixed_tie_contains_actual_selected_and_distinct'])
        self.assertFalse(n.summarize([result])['recorded_choice_activity_gate'])

    def test_Q0_same_latent_different_native_geometry_fails_C0_uses_actual_last_batch(self):
        for profile in ['C0', 'Q0']:
            rows, analysis, targets = fixture(profile)
            score = next(r['values'] for r in rows if r['event'] == 'scoring_inputs')
            score['projected_xyz'][0, 8, 0] = .5  # old provider slice and old quality unchanged
            if profile == 'Q0':
                with self.assertRaisesRegex(ValueError, 'ambiguous native input'):
                    run_fixture(rows, analysis, targets, profile)
            else:
                result = run_fixture(rows, analysis, targets, profile)
                self.assertEqual(result['slots'][0]['projected_distance8_m'], .125)
                self.assertEqual(len(result['slots'][0]['used_occurrence_ids']), 1)

    def test_Q0_same_latent_different_old_quality_fails(self):
        rows, analysis, targets = fixture('Q0')
        first_score = next(r['sequence'] for r in rows if r['event'] == 'scoring_inputs')
        next(r['values'] for r in rows if r['event'] == 'effective_quality' and r['values']['scoring_batch_id'] == first_score)['quality'][0] = -.5
        next(r['values'] for r in rows if r['event'] == 'canonical_candidate_batch')['effective_quality'][0] = -.5
        with self.assertRaisesRegex(ValueError, 'ambiguous native input or original quality'):
            run_fixture(rows, analysis, targets, 'Q0')

    def test_wrong_helper_storage_dtype_and_mutation_are_rejected(self):
        def promote(p, k, **kwargs):
            return h.executed_prefix_quality(p, k, **kwargs).float()
        def mutate(p, k, **kwargs):
            result = h.executed_prefix_quality(p, k, **kwargs)
            p[0, 8, 1] = 10
            return result
        for helper, reason in [(promote, 'sample storage dtype'), (mutate, 'mutated recorded')]:
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(ValueError, reason):
                    run_fixture(*fixture(), helper=helper)

    def test_native_byte_join_rejects_signed_zero_mismatch(self):
        rows, analysis, targets = fixture()
        history = c.analyze_decision(rows, analysis, targets, a)
        membership = m.inspect_decision(rows, history, 'C0', a, c)
        score = [r['values'] for r in rows if r['event'] == 'scoring_inputs'][-1]
        score['samples'][0, 0, 0] = -0.
        self.assertTrue(torch.equal(score['samples'], a.one([r for r in rows if r['event'] == 'canonical_candidate_batch' and r['values']['iter_idx'] == 0], 'canonical_candidate_batch')['values']['candidates']))
        with self.assertRaisesRegex(ValueError, 'native bytes'):
            n.rerank_decision(rows, history, membership, analysis, targets, 'C0', a, c, m, h.executed_prefix_quality)

    def test_auxiliary_score_cannot_replace_canonical_source(self):
        rows, analysis, targets = fixture()
        history = c.analyze_decision(rows, analysis, targets, a)
        membership = m.inspect_decision(rows, history, 'C0', a, c)
        [r['values'] for r in rows if r['event'] == 'scoring_inputs'][-1]['scoring_scope']['role'] = 'auxiliary_pretest'
        with self.assertRaisesRegex(ValueError, 'canonical score role'):
            n.rerank_decision(rows, history, membership, analysis, targets, 'C0', a, c, m, h.executed_prefix_quality)

    def test_all_A_nonA_Unknown_decisions_are_kept(self):
        results = [run_fixture(*fixture(actual_A=value)) for value in [True, False, None]]
        summary = n.summarize(results)
        self.assertEqual(summary['all_eligible']['decisions'], 3)
        self.assertEqual(summary['all_eligible']['tie_robust_changed'], 3)
        self.assertTrue(all(row['decisions'] == 1 for row in summary['A_strata_descriptive_only'].values()))

    def test_final_membership_tampering_is_not_repaired(self):
        rows, analysis, targets = fixture()
        history = c.analyze_decision(rows, analysis, targets, a)
        membership = m.inspect_decision(rows, history, 'C0', a, c)
        membership['slots'][0]['matching_occurrence_ids'].pop()
        with self.assertRaisesRegex(ValueError, 'saved final membership differs'):
            n.rerank_decision(rows, history, membership, analysis, targets, 'C0', a, c, m, h.executed_prefix_quality)

    def test_read_gate_rejects_before_opening_missing_manifest(self):
        result = subprocess.run([sys.executable, str(HERE/'analyze_fixed_pool.py'), '--manifest', '/nonexistent',
            '--output-dir', '/nonexistent-output'], capture_output=True, text=True,
            env={**os.environ, 'CUDA_VISIBLE_DEVICES': ''}, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('root review and empty CUDA mask required', result.stderr)
        self.assertNotIn('FileNotFoundError', result.stderr)


if __name__ == '__main__':
    unittest.main()
