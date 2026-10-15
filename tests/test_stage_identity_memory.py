from types import SimpleNamespace
import numpy as np
from core.stage.observation import identify
import json


def test_memory_is_generated_online_once_per_episode_and_never_contains_old_stage_replies():
    requests=[]
    def request(content):
        requests.append(content)
        return 'A short brown bottle with a red and yellow label.'
    observer=SimpleNamespace(context={'episode_id':0,'task_id':3},_last_completion_metadata={},
                             _request_stage_response=request)
    kwargs=dict(instruction='pick up the bbq sauce and place it in the basket',
                initial_image=np.zeros((8,8,3),dtype=np.uint8),mapping={0:'bbq_sauce_1_main'})
    description,new=identify(observer,**kwargs)
    assert new and len(requests)==1 and 'grasp' not in description
    assert identify(observer,**kwargs)==(description,False) and len(requests)==1
    observer.context={'episode_id':1,'task_id':3}
    assert identify(observer,**kwargs)[1] and len(requests)==2


def test_online_transport_sends_only_current_frame_after_identity_step(monkeypatch,tmp_path):
    import core.gemini_grounder as grounder
    from core.gemini_grounder import create_gemini_stage_recognizer
    requests=[]
    observation=dict(target_visibility='clear',target_location='outside_goal',grasp='not_held',
                     support='supported',evidence='The brown bottle is on the table outside the basket.')
    def create(**kwargs):
        requests.append(kwargs)
        text=kwargs['messages'][0]['content'][0]['text']
        content='A small brown bottle with a red label.' if text.startswith('Identify only') else json.dumps(observation)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content),finish_reason='stop')])
    monkeypatch.setattr(grounder,'_make_client',lambda _:SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    observer=create_gemini_stage_recognizer(dict(output_format='stage_observation_v1',
        identity_memory_enabled=True,capture_dir=str(tmp_path/'capture')))
    observer.set_trace_context({'episode_id':0,'task_id':3},'initial')
    kwargs=dict(current_rgb=np.zeros((4,4,3),dtype=np.uint8),init_img_with_keypoints=np.ones((4,4,3),dtype=np.uint8),
                instruction='pick up the bbq sauce and place it in the basket',stage_descriptions='OLD_DIRECTIVES',
                keypoint_id_to_object={0:'bbq_sauce_1_main'})
    assert observer.observe_scene(**kwargs)==observation
    assert observer.last_result['identity_generated_this_query']
    assert observer.observe_scene(**kwargs)==observation
    assert not observer.last_result['identity_generated_this_query']
    assert len(requests)==3  # one identity, two current observations
    assert all(sum(x['type']=='image_url' for x in r['messages'][0]['content'])==1 for r in requests)
    assert 'A small brown bottle' in json.dumps(requests[1])
    assert 'OLD_DIRECTIVES' not in json.dumps(requests)
