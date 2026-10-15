import json
from types import SimpleNamespace
import numpy as np
import torch
from test_stage_carry_runtime import runner_state


def test_runtime_annotates_current_frame_preserves_raw_and_records_same_target(tmp_path):
    from core.stage.controller import update_stage
    runner,state,safety = runner_state()
    runner.backend='libero'
    runner.config.update(use_guidance=True,stage_controller='online',stage_target_marker_enabled=True,
                         eds_eval={'output_dir':str(tmp_path)})
    runner.adapter._env_config={'vlm_camera':'agentview'}
    runner.adapter.get_camera_params=lambda _:SimpleNamespace(width=100,height=100,
        intrinsic=np.array([[100.,0,50],[0,100,50],[0,0,1]]),extrinsic=np.eye(4))
    raw=np.zeros((100,100,3),dtype=np.uint8)
    runner.adapter.get_vlm_image=lambda:raw
    runner.policy=SimpleNamespace(_action_chunk_horizon=8,get_normalized_reward=lambda:0.,reset_stage=lambda:None)
    runner.guidance_fns={1:[lambda kp,a:-(a-kp[0]).square().mean()],2:[lambda kp,a:torch.tensor(0.)]}
    observation=dict(target_visibility='occluded',target_location='unknown',grasp='unknown',support='unknown',evidence='Hidden.')
    calls=[]
    def observe(**kwargs):calls.append(kwargs);return observation
    runner.gemini_stage_recognizer=SimpleNamespace(observe_scene=observe,last_result={'ok':True,'observation':observation})
    runner.stage_descriptions='';runner.init_img_with_keypoints=None;events=[];runner._append_stage_event=events.append
    state.update(use_guidance=False,global_step=0)
    update_stage(runner,state,1.)
    assert len(calls)==1 and not np.any(raw)
    assert np.any(calls[0]['current_rgb'])
    marker=events[0]['current_target_marker']
    assert calls[0]['current_target_marker']==marker and marker['target_world_position']==[0.,0.,.16]
    assert marker['target_world_position']==events[0]['robot_evidence']['geometry']['target_position']
    assert not {'stage','reward','grasp','success','guidance'} & set(marker)
    assert len(list(tmp_path.glob('stage_unmarked_frames/episode_000/*.png')))==1


def test_online_request_includes_marker_instruction_but_no_control_metadata(monkeypatch):
    import core.gemini_grounder as grounder
    from core.gemini_grounder import create_gemini_stage_recognizer
    requests=[]
    observation=dict(target_visibility='clear',target_location='above_goal',grasp='held',support='unsupported',evidence='Visible target in fingers.')
    def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(observation)),finish_reason='stop')])
    monkeypatch.setattr(grounder,'_make_client',lambda _:SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    observer=create_gemini_stage_recognizer(dict(output_format='stage_observation_v1'))
    metadata=dict(schema='stage_current_target_marker_v1',raw_png_path='LOCAL_ARTIFACT_PATH',target_world_position=[1.,2.,3.])
    actual=observer.observe_scene(current_rgb=np.zeros((10,10,3),dtype=np.uint8),instruction='pick up the butter and place it in the basket',
        stage_descriptions='CONTROL_DIRECTIVES',keypoint_id_to_object={0:'butter_1_main'},current_target_marker=metadata)
    assert actual==observation and observer.last_result['current_target_marker']==metadata
    payload=json.dumps(requests)
    assert 'magenta circle marked TARGET' in payload
    assert 'CONTROL_DIRECTIVES' not in payload and 'LOCAL_ARTIFACT_PATH' not in payload
    assert sum(p['type']=='image_url' for p in requests[0]['messages'][0]['content'])==1
