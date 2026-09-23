"""Synthetic numerical/association fixtures, never represented as runtime events."""
import importlib.util
from pathlib import Path
import unittest
import torch

spec=importlib.util.spec_from_file_location('reader',Path(__file__).with_name('read_closed_loop.py'))
r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

def step(i,x,reset=0,command=1,terminal=False):
    return {'global_step':i,'reset_sequence':reset,'eef':{'value':[x,0.,0.]},
        'command':{'value':[0.]*6+[command]},'gripper_qpos':{'value':[x,-x]},
        'terminated':terminal,'truncated':False}

class SyntheticTests(unittest.TestCase):
    def test_cpu_only(self):
        self.assertFalse(torch.cuda.is_initialized())

    def test_contiguous_net_and_path(self):
        out=r.motion_summary([step(1,2.),step(2,1.)],step(0,0.))
        self.assertEqual(out['eef_net_displacement_m'],1.)
        self.assertEqual(out['eef_path_length_m'],3.)
        self.assertEqual(out['contiguous_observed_edges'],2)

    def test_reset_never_bridges(self):
        out=r.motion_summary([step(1,100.,1),step(2,101.,1)],step(0,0.,terminal=True))
        self.assertEqual(out['eef_path_length_m'],1.)
        self.assertEqual(out['origin_step'],1)
        self.assertIn('origin_missing',out['motion_origin'])

    def test_gap_excluded_and_net_unknown(self):
        out=r.motion_summary([step(0,0.),step(2,99.)])
        self.assertEqual(out['eef_path_length_m'],0.)
        self.assertIsNone(out['eef_net_displacement_m'])

    def test_signs_not_grasps(self):
        out=r.motion_summary([step(0,0.,command=-1),step(1,1.,command=-1),step(2,2.,command=1)])
        self.assertEqual(out['command_sign_changes'],1)
        self.assertEqual([x['count'] for x in out['command_sign_runs']],[2,1])
        self.assertNotIn('grasp',out)

    def test_keypoint_only_same_index(self):
        a={'decision_id':'a','reset_sequence':0,'last_executed_step':7,'keypoints':{'shape':[1,3],'value':[[0.,0.,0.]]}}
        b={'decision_id':'b','reset_sequence':0,'global_step':8,'keypoints':{'shape':[1,3],'value':[[3.,4.,0.]]}}
        out=r.keypoint_link(a,b)
        self.assertEqual(out['displacement_m'],[5.])
        self.assertEqual(out['real_object_motion'],'Unknown')
        b['reset_sequence']=1
        self.assertEqual(r.keypoint_link(a,b)['status'],'Unknown')

    def test_wrapper_hash_not_semantic_identity(self):
        a={'ordinal':0,'original_code_sha256':'a','source_text_sha256':'b','source_path':'c','code_sha256':'wrapper1'}
        b={**a,'code_sha256':'wrapper2'}
        self.assertEqual(r.provider_signature([a]),r.provider_signature([b]))
        self.assertNotEqual(r.provider_signature([a]),r.provider_signature([{**b,'source_text_sha256':'different'}]))

    def test_native_dtype_is_part_of_identity(self):
        self.assertNotEqual(r.native_key(torch.tensor([1.],dtype=torch.float32)),r.native_key(torch.tensor([1.],dtype=torch.bfloat16)))

    def test_selected_quality_keeps_raw_separate(self):
        latent=torch.tensor([[1.,2.]],dtype=torch.bfloat16)
        rows=[{'event':'final_selection','values':{'selected_latent':latent,'selected_quality':-2.,'selected_raw_provider_quality':-3.,'selected_canonical_fingerprint':'x','selected_index':0,'selection_rule':'archive_global_best'}},
            {'event':'scoring_inputs','sequence':10,'values':{'samples':latent,'scoring_scope':{'role':'canonical_initial'}}},
            {'event':'effective_quality','values':{'scoring_batch_id':10,'quality':torch.tensor([-2.],dtype=torch.bfloat16),'quality_mode':'executed_prefix_v1','reward_mode':'normal'}},
            {'event':'scoring_aggregate','values':{'scoring_batch_id':10,'aggregate_before_reward_mode':torch.tensor([-3.],dtype=torch.bfloat16)}}]
        out=r.selected_quality(rows,True)
        self.assertEqual(out['selected_raw_provider_quality'],-3.)
        self.assertEqual(out['selected_internal_quality'],-2.)
        self.assertEqual(r.selected_quality(rows,False)['status'],'Unknown')

    def test_all_reactivations_retained(self):
        steps=[step(i,float(i)) for i in range(4)]
        decisions=[{'stage':1,'use_guidance':g,'providers':[],'reset_sequence':0,'global_step':i,'last_executed_step':i,'decision_id':str(i)} for i,g in enumerate([True,False,True,False])]
        out=r.summarize_decisions(decisions,steps,[])
        self.assertEqual(out['all_on_to_off_steps'],[1,3])
        self.assertEqual(out['all_off_to_on_steps'],[2])
        self.assertEqual(out['last_guided_executed_step'],2)
        self.assertTrue(all(t['association'].startswith('Unknown') for t in out['stage_guidance_transitions']))

    def test_dispatch_preserves_pre_reset_not_returned_reset(self):
        meta={'decision_id':'d','global_step':0,'reset_sequence':0}
        rows=[{**meta,'event':'action_dispatch','sequence':1,'values':{'execution_index':1}},
              {**meta,'event':'executed_action','sequence':2,'values':{'action_numpy':torch.zeros(7)}},
              {**meta,'event':'pre_reset_outcome','sequence':3,'values':{'observation':{'robot0_eef_pos':torch.tensor([1.,2.,3.])},'reward':0.,'success':False,'terminated':True,'origin':'actual_env_step_before_automatic_reset'}},
              {**meta,'reset_sequence':1,'event':'step_returned','sequence':4,'values':{'truncated':False}}]
        out=r.actual_steps(rows)[0]
        self.assertEqual(out['eef']['value'],[1.,2.,3.])
        self.assertEqual((out['reset_sequence'],out['returned_reset_sequence']),(0,1))

    def test_no_stage_prose_allowlist(self):
        self.assertTrue(set(r.STAGE_KEYS).isdisjoint({'raw_response','evidence','error','prompt'}))

if __name__=='__main__':
    unittest.main()
