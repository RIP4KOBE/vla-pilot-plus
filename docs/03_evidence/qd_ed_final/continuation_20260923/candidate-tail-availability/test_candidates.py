"""Synthetic CPU fixtures only. No runtime episode/bundle is opened."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


c=load('candidate_check',HERE/'check_candidates.py')
a=load('frozen_cpu_numerics',ROOT/'docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/analyze_episode.py')
torch=a.cpu_torch()
fixture=load('synthetic_existing_audit_fixture',ROOT/'tests/test_decision_evidence_audit.py')


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        rec,_=fixture.episode(Path(self.temp.name),auxiliary=True)
        import json
        self.rows=fixture.audit.load_events(rec.root,json.loads((rec.root/'status.json').read_text()))
        context=a.one(self.rows,'decision_context')['values']
        context['providers'][0].update(original_code_sha256='a'*64,source_text_sha256='b'*64,source_path='/synthetic/provider')
        self.target_map={a.provider_identity(context['providers'][0]):{'keypoint_index':0,'distance_progress_interpretation':'approach_proxy'}}
        self.selected={'decision_id':self.rows[0]['decision_id'],'global_step':0,'stage':1,'guidance':True,
            'hypothesis_eligible':True,'command_translation_matches_projection_source':True,
            'frozen_target':[0.,0.,0.], 'diagnostics':{'step7_to8':None,'projection_optimism_witness':False},
            'unknown_reasons':[],'hypothesis_ineligible_reasons':[]}

    def run_fixture(self): return c.analyze_decision(self.rows,self.selected,self.target_map,a)

    def test_negative_quality_tradeoff_all_ties_and_auxiliary_exclusion(self):
        report=self.run_fixture()
        self.assertEqual(report['summary']['canonical_occurrences'],4)  # 2x2, not auxiliary 2.
        self.assertEqual(report['summary']['known_nonflagged_occurrences'],2)
        self.assertEqual(report['summary']['best_known_quality_minus_actual_selected'],-1.)
        self.assertFalse(report['summary']['any_nonflagged_quality_ge_selected'])
        self.assertEqual(len(report['summary']['best_known_exact_ties']),2)
        self.assertTrue(all(row['fingerprint_differs_from_selected'] for row in report['summary']['best_known_exact_ties']))
        self.assertEqual(report['summary']['final_time_alternative_availability'],'Unknown')
        self.assertIsNone(report['original_actual_A'])  # Short actual prefix is still examined prospectively.
        self.assertFalse(torch.cuda.is_initialized())

    def test_quality_preserving_alternative_uses_recorded_quality_without_tolerance(self):
        for row in self.rows:
            if row['event']=='effective_quality': row['values']['quality'][0]=1.
            elif row['event']=='canonical_candidate_batch': row['values']['effective_quality'][0]=1.
        report=self.run_fixture()['summary']
        self.assertTrue(report['any_nonflagged_quality_ge_selected'])
        self.assertTrue(report['any_distinct_fingerprint_nonflagged_quality_ge_selected'])
        self.assertEqual(report['best_known_quality_minus_actual_selected'],0.)

    def test_repeated_fingerprint_different_projection_is_unknown_not_cherry_picked(self):
        scores=[row for row in self.rows if row['event']=='scoring_inputs' and
                row['values']['scoring_scope']['role']=='canonical_offspring']
        scores[0]['values']['projected_xyz'][0,8,0]+=0.5
        report=self.run_fixture()
        self.assertEqual(len(report['ambiguous_fingerprints']),1)
        self.assertIsNone(report['summary']['any_nonflagged'])
        self.assertIsNone(report['summary']['best_known_nonflagged_quality'])
        ambiguous=[row for row in report['candidates'] if row['fingerprint'] in report['ambiguous_fingerprints']]
        self.assertEqual(len(ambiguous),2)
        self.assertTrue(all(row['tail_classification'] is None for row in ambiguous))

    def test_non_normal_target_mismatch_and_command_mismatch_remain_excluded(self):
        for row in self.rows:
            if row['event']=='effective_quality': row['values']['reward_mode']='inverted'
        report=self.run_fixture()
        self.assertTrue(all('reward_mode_not_normal' in row['ineligible_reasons'] for row in report['candidates']))
        self.assertIsNone(report['summary']['any_nonflagged'])
        for row in self.rows:
            if row['event']=='effective_quality': row['values']['reward_mode']='normal'
            elif row['event']=='scoring_inputs': row['values']['keypoints']=torch.ones(1,3)
        report=self.run_fixture()
        self.assertTrue(all('target_unknown_scoring_keypoints_differ_from_context' in row['ineligible_reasons'] for row in report['candidates']))
        self.selected['command_translation_matches_projection_source']=False
        with self.assertRaisesRegex(ValueError,'command mismatch'): self.run_fixture()

    def test_all_guided_eligible_decisions_enter_regardless_of_A_B_witness(self):
        decisions=[]
        for name,eligible,witness in [('non_witness',True,False),('witness',True,True),('excluded',False,True)]:
            row=copy.deepcopy(self.selected)
            row.update(decision_id=name,hypothesis_eligible=eligible)
            row['diagnostics']['step7_to8']={'both_regress_robust':witness}
            decisions.append(row)
        events=[{'decision_id':row['decision_id']} for row in decisions]
        with patch.object(c,'analyze_decision',return_value={'summary':{'any_nonflagged':True}}) as call:
            report=c.analyze_events(events,{'decisions':decisions},self.target_map,a)
        self.assertEqual(call.call_count,2)
        self.assertEqual([call.args[1]['decision_id'] for call in call.call_args_list],['non_witness','witness'])
        self.assertEqual(report['eligible_decisions'],2)
        self.assertEqual(report['excluded_decision_count'],1)


if __name__=='__main__': unittest.main()
