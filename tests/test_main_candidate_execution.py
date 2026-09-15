from types import SimpleNamespace
import numpy as np
import pytest
import torch
from omegaconf import OmegaConf


@pytest.mark.parametrize('prediction_horizon',[10,50])
@pytest.mark.parametrize('native_success_without_terminal',[False,True])
def test_main_executes_ten_steps_of_selected_candidate_not_particle_zero(tmp_path,monkeypatch,prediction_horizon,native_success_without_terminal):
    from main import Main
    monkeypatch.setattr('mode_gate.ticket_visuals.policy_camera_images',lambda _: {})
    actions=[]; selected=[]; policy_calls=[]
    cached=torch.arange(40*prediction_horizon*7,dtype=torch.float32).reshape(40,prediction_horizon,7)/10000
    class Policy:
        _action_chunk_horizon=10
        def select_action(self, *args, **kwargs):
            policy_calls.append(kwargs)
            return cached
    class Adapter:
        vlm_camera='camera'
        def get_task_description(self):return 'test task'
        def get_vlm_image(self):return np.zeros((32,32,3),dtype=np.uint8)
        def get_ee_pose_world(self):return None
        def step(self,action):
            actions.append(action.clone())
            return {},0.,len(actions)==20 and not native_success_without_terminal,False,{'success':len(actions)==20}
    runtime=SimpleNamespace(episode_id='episode',start_episode=lambda **kwargs:None,
        record_execution_step=lambda *args,**kwargs:None,
        assess_progress=lambda **kwargs:None,observe_chunk=lambda *args,**kwargs:None,
        _close_factual_labels=lambda **kwargs:None)
    app=Main.__new__(Main)
    app.policy=Policy();app.adapter=Adapter()
    app.config=OmegaConf.create({'use_guidance':False,'debug_draw_trajectory':False})
    app.mode_gate_controller=runtime;app.mode_aware_runtime=runtime
    app.mode_gate_incidents=SimpleNamespace(record_fact=lambda **kwargs:None,record_video_frame=lambda *args,**kwargs:None,
        experiences=SimpleNamespace(finish_video=lambda *args,**kwargs:None))
    app.video_recorder=SimpleNamespace(add_frame=lambda *args,**kwargs:None,save_video=lambda **kwargs:None)
    app._get_policy_observation=lambda: {}
    app.success_count=0
    def choose(**kwargs):
        batch=kwargs['sample_policy'](None)
        index=(35,5)[len(selected)];selected.append(index)
        return batch[index:index+1]
    app._run_mode_gate=choose
    app._run_episode(0,str(tmp_path))
    assert len(policy_calls)==2, 'non-boundary steps must not reread the full policy cache'
    assert selected==[35,5] and len(actions)==20
    torch.testing.assert_close(torch.stack(actions[:10]),cached[35,:10])
    torch.testing.assert_close(torch.stack(actions[10:]),cached[5,:10])


@pytest.mark.parametrize('posthoc_only',[False,True])
@pytest.mark.parametrize('planner_enabled',[False,True])
def test_stage_guidance_planner_requires_explicit_online_role(posthoc_only,planner_enabled):
    from main import Main
    calls=[]
    def stage_call(**kwargs):
        calls.append(kwargs)
        return 2,False
    app=Main.__new__(Main)
    app.config=OmegaConf.create({'initialization_posthoc_only':posthoc_only,'use_vlm_stage_recognition':True,
                                 'planner_steering_enabled':planner_enabled})
    app.policy=SimpleNamespace(get_normalized_reward=lambda:.9,reset_stage=lambda:None)
    app.gemini_stage_recognizer=SimpleNamespace(identify_stage_and_guidance=stage_call)
    app.adapter=SimpleNamespace(get_vlm_image=lambda:np.zeros((8,8,3)),get_task_description=lambda:'task')
    app.stage_descriptions='stage_1\nstage_2';app.init_img_with_keypoints=None
    app.keypoint_id_to_object={};app.guidance_fns={1:[],2:[]}
    state={'prev_norm_reward':0.,'prev_gripper_open':True,'current_stage':1,'use_guidance':True,'vlm_query_count':0}
    result=app._update_stage(state,-1.,.8,.6)
    called = planner_enabled and not posthoc_only
    assert len(calls)==int(called)
    assert result['current_stage']==(2 if called else 1)
    assert result['use_guidance'] is (not called)
