"""Disposable native CPU tensors only; no runtime bundle or result is opened."""
import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


m = load('membership', HERE/'check_membership.py')
c = load('historical_cpu_helpers', HERE.parent/'candidate-tail-availability/check_candidates.py')
a = load('frozen_cpu_helpers', HERE.parent/'decision-analysis-draft/analyze_episode.py')
torch = a.cpu_torch()


def fixture(profile='C0', duplicate=False):
    population = torch.zeros(3 if duplicate else 2, 64, 128, dtype=torch.bfloat16)
    population[-1, :8, 39] = .125
    quality = torch.zeros(len(population), dtype=torch.bfloat16); quality[-1] = 1
    history = {'decision_id':'e0:d1:s0','global_step':0,'stage':1,'original_actual_A':True,'original_actual_B':False,
               'selected_fingerprint':a.fingerprint(population[-1]),'actual_selected_quality':1.,'candidates':[]}
    events = []
    for sequence, iteration in [(1,-1),(2,0)]:
        ids = [f'e0:d1:s0:q{sequence}:r{i}' for i in range(len(population))]
        events.append({'event':'canonical_candidate_batch','sequence':sequence,'values':{
            'iter_idx':iteration,'candidates':population.clone(),'effective_quality':quality.clone(),
            'occurrence_ids':ids,'canonical_fingerprints':[a.fingerprint(x) for x in population]}})
        for i, fp in enumerate(events[-1]['values']['canonical_fingerprints']):
            history['candidates'].append({'occurrence_id':ids[i],'fingerprint':fp,'canonical_batch_sequence':sequence,
                'candidate_row':i,'iteration':iteration,'effective_quality':float(quality[i]),'quality_dtype':str(quality.dtype),
                'tail_classification':'robust_regression' if i==len(population)-1 else 'not_flagged_robust_regression',
                'unknown_reasons':[],'ineligible_reasons':[]})
    final = {'population':population.clone(),'selected_latent':population[-1:].clone(),'selected_index':len(population)-1,
             'selected_quality':1.,'selected_canonical_fingerprint':history['selected_fingerprint'],
             'selection_rule':'cost_argmin' if profile=='C0' else 'archive_global_best'}
    events += [{'event':'final_selection','sequence':3,'values':final},
               {'event':'policy_action_decode','sequence':4,'values':{'selected_canonical_fingerprint':history['selected_fingerprint']}}]
    return events, history


class Tests(unittest.TestCase):
    def test_C0_uses_last_batch_quality_and_preserves_duplicate_slots_and_ties(self):
        rows, history = fixture(duplicate=True)
        rows[1]['values']['effective_quality'][:2] = .25
        for item in history['candidates']:
            if item['iteration']==0 and item['candidate_row']<2: item['effective_quality']=.25
        result=m.inspect_decision(rows,history,'C0',a,c)
        self.assertEqual(result['pool_kind'],'actual_C0_final_population')
        self.assertEqual(result['summary']['best_known_quality_minus_actual_selected'],-.75)
        self.assertEqual(len(result['summary']['best_known_exact_ties']),2)
        self.assertEqual(result['slots'][0]['effective_quality'],.25)
        self.assertEqual(len(result['slots'][0]['matching_occurrence_ids']),4)
        self.assertFalse(torch.cuda.is_initialized())

    def test_Q0_historical_alternative_not_in_final_pool_is_not_available(self):
        rows, history = fixture('Q0')
        final=rows[2]['values']; final['population']=final['population'][-1:];final['selected_index']=0
        result=m.inspect_decision(rows,history,'Q0',a,c)
        self.assertEqual(result['pool_kind'],'actual_Q0_final_archive_elites')
        self.assertEqual(result['summary']['final_slots'],1)
        self.assertFalse(result['summary']['any_distinct_nonflagged'])
        self.assertIsNone(result['summary']['best_known_nonflagged_quality'])

    def test_Q0_duplicate_quality_or_tail_ambiguity_stays_Unknown(self):
        rows, history = fixture('Q0')
        rows[1]['values']['effective_quality'][0]=.5
        history['candidates'][2]['effective_quality']=.5
        result=m.inspect_decision(rows,history,'Q0',a,c)
        self.assertTrue(result['summary']['any_distinct_nonflagged'])
        self.assertIsNone(result['slots'][0]['effective_quality'])
        self.assertIsNone(result['summary']['any_distinct_nonflagged_quality_ge_selected'])
        self.assertEqual(result['summary']['maximum_scope'],'known_subset_only')
        for item in history['candidates']:
            if item['candidate_row']==0:
                item['tail_classification']=None
                item['unknown_reasons']=['same_fingerprint_projection_origin_or_keypoints_ambiguous']
        result=m.inspect_decision(rows,history,'Q0',a,c)
        self.assertIsNone(result['summary']['any_distinct_nonflagged'])
        self.assertIn('same_fingerprint_projection_origin_or_keypoints_ambiguous',result['slots'][0]['unknown_or_ineligible_reasons'])

    def test_native_dtype_selected_and_C0_final_batch_inconsistency_fail_closed(self):
        for defect in ['dtype','selected','C0last']:
            with self.subTest(defect=defect):
                profile='C0' if defect=='C0last' else 'Q0'
                rows,history=fixture(profile); final=rows[2]['values']
                if defect=='dtype':
                    final['population']=final['population'].float();final['selected_latent']=final['selected_latent'].float()
                    message='no exact native canonical match'
                elif defect=='selected':
                    final['selected_index']=0;message='selected native tensor differs'
                else:
                    final['population']=final['population'].flip(0);final['selected_index']=0
                    message='differs from last canonical'
                with self.assertRaisesRegex(ValueError,message): m.inspect_decision(rows,history,profile,a,c)


if __name__ == '__main__': unittest.main()
