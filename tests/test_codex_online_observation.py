"""Provider-isolation and real wrapper boundary tests; no network/GPU."""
import base64
import io
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))

OBS={'target_visibility':'clear','target_location':'outside_goal','grasp':'not_held',
     'support':'supported','evidence':'The target stands on the table outside the basket.'}


def fake_cli(monkeypatch, tmp_path, replies):
    import core.codex_stage as transport
    import core.gemini_grounder as legacy
    import vlm_query.vlm_agent as guidance
    cli=tmp_path/'codex';cli.touch();calls=[]
    def forbidden(**kwargs):
        raise AssertionError('No OpenAI-compatible client may be constructed')
    monkeypatch.setattr(legacy,'OpenAI',forbidden);monkeypatch.setattr(guidance,'OpenAI',forbidden)
    class Process:
        pid=12345
        returncode=0
        def __init__(self,command,**kwargs):
            self.command,self.kwargs=command,kwargs;calls.append(self)
            answer=replies.pop(0)
            events=[{'type':'thread.started','thread_id':'test'}, {'type':'turn.started'},
                {'type':'item.completed','item':{'type':'agent_message','text':answer}},
                {'type':'turn.completed','usage':{'input_tokens':100,'cached_input_tokens':0,'output_tokens':30}}]
            kwargs['stdout'].write(('\n'.join(json.dumps(e) for e in events)).encode());kwargs['stdout'].flush()
        def communicate(self,input=None,timeout=None):
            self.prompt=input
    monkeypatch.setattr(transport.subprocess,'Popen',Process)
    return dict(backend='codex_cli',model='gpt-6-astra',reasoning_effort='low',cli_path=str(cli),
        disabled_skill_paths=[],event_policy='completed_transport_cycles_v6',
        capture_dir=str(tmp_path/'captures')),calls


def test_online_identity_then_five_field_stage_never_uses_poe(monkeypatch,tmp_path):
    from core.gemini_grounder import create_gemini_stage_recognizer
    config,calls=fake_cli(monkeypatch,tmp_path,['A small yellow carton.',json.dumps(OBS)])
    monkeypatch.setenv('OPENAI_API_KEY','fake-poe');monkeypatch.setenv('OPENAI_BASE_URL','https://api.poe.com/v1')
    config.update(output_format='stage_observation_v1',identity_memory_enabled=True)
    observer=create_gemini_stage_recognizer(config)
    observer.set_trace_context({'episode_id':0,'task_id':0},'initial')
    image=np.zeros((8,8,3),dtype=np.uint8)
    assert observer.observe_scene(current_rgb=image,instruction='pick up carton',stage_descriptions='',
        init_img_with_keypoints=image,keypoint_id_to_object={0:'carton'})==OBS
    assert len(calls)==2
    assert observer.last_result['codex_completed_turns']==2
    assert observer.last_result['codex_logical_call_attempts']==2
    assert observer.last_result['api_request_attempts'] is None
    assert observer.last_result['validation_attempts'][0]['capture_query_index']==1
    assert all('OPENAI_API_KEY' not in c.kwargs['env'] and 'OPENAI_BASE_URL' not in c.kwargs['env'] for c in calls)
    assert all('forced_login_method="chatgpt"' in c.command for c in calls)
    assert 'three lines' not in observer.public_policy['config_overrides']['developer_instructions']
    captures=list((tmp_path/'captures').glob('request_*/response.json'))
    assert len(captures)==2 and all(json.loads(p.read_text())['ok'] for p in captures)


def test_first_valid_negative_answer_wins_after_one_syntax_retry(monkeypatch,tmp_path):
    from core.gemini_grounder import create_gemini_stage_recognizer
    config,calls=fake_cli(monkeypatch,tmp_path,['not JSON',json.dumps(OBS)])
    config.update(output_format='stage_observation_v1',observation_validation_max_attempts=2)
    observer=create_gemini_stage_recognizer(config)
    assert observer.observe_scene(current_rgb=np.zeros((8,8,3),dtype=np.uint8),
        instruction='pick up carton',stage_descriptions='')==OBS
    assert len(calls)==2 and calls[0].prompt==calls[1].prompt
    assert [x['valid'] for x in observer.last_result['validation_attempts']]==[False,True]
    assert observer.last_result['codex_completed_turns']==2


def test_fresh_reward_uses_codex_with_saved_provenance(monkeypatch,tmp_path):
    from vlm_query.vlm_agent import VLMAgent
    reply='num_stages = 2\ndef stage1_guidance_1(keypoints, action_sequence):\n    return 0\n'
    config,calls=fake_cli(monkeypatch,tmp_path,[reply])
    config['query_template_dir']=str(ROOT/'vlm_query/c0_contract_v1')
    agent=VLMAgent(config,base_dir=str(tmp_path),env_type='libero');agent.task_dir=str(tmp_path/'reward')
    buffer=io.BytesIO();Image.new('RGB',(8,8)).save(buffer,format='PNG')
    content=[{'type':'text','text':'Return Python source'}, {'type':'image_url','image_url':{
        'url':'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()}}]
    assert agent._query_guidance_with_retry([{'role':'user','content':content}])==reply.strip()
    assert agent.client is None and len(calls)==1
    assert agent.api_request_counter.snapshot()['completed_turns']==1
    assert (tmp_path/'reward/codex_requests/request_0000/response.json').is_file()


def test_codex_runtime_strips_keys_and_rejects_mixed_or_cached_config(monkeypatch):
    from codex_only_runtime import worker_environment, validate_config
    monkeypatch.setenv('POE_API_KEY','fake');monkeypatch.setenv('OPENAI_API_KEY','fake')
    env=worker_environment()
    assert env['VLA_CODEX_ONLY']=='1' and env['CUDA_VISIBLE_DEVICES']=='2'
    assert 'POE_API_KEY' not in env and 'OPENAI_API_KEY' not in env
    config={'perception':{k:{'backend':'codex_cli','api_key':None,'base_url':None}
                          for k in ('gemini','vlm_agent')},'main':{}}
    validate_config(config)
    config['perception']['vlm_agent']['backend']='openai_compatible'
    with pytest.raises(ValueError,match='managed-login'):validate_config(config)
    config['perception']['vlm_agent']['backend']='codex_cli'
    config['main']['cached_functions_dir']='old'
    with pytest.raises(ValueError,match='fresh'):validate_config(config)


def test_user_provider_directive_blocks_legacy_poe_launch():
    from types import SimpleNamespace
    from stage_closed_loop_run import prepare
    with pytest.raises(RuntimeError,match='User forbids Poe'):
        prepare(SimpleNamespace(provider='poe'))


def test_actual_main_initialization_allows_codex_fresh_reward(monkeypatch,tmp_path):
    import main
    from omegaconf import OmegaConf
    config,_=fake_cli(monkeypatch,tmp_path,[])
    config['query_template_dir']=str(ROOT/'vlm_query/c0_contract_v1')
    monkeypatch.setenv('VLA_CODEX_ONLY','1')
    monkeypatch.setattr(main,'observe_api_requests',lambda *args: pytest.fail('Do not replace Codex counters with HTTP counters'))
    monkeypatch.setattr(main,'KeypointDetector',lambda **kwargs:object())
    monkeypatch.setattr(main,'KeypointTracker',lambda *args:object())
    monkeypatch.setattr(main,'TrajectoryVideoRecorder',lambda **kwargs:object())
    runner=main.Main.__new__(main.Main)
    runner.config=OmegaConf.create({'use_guidance':True,'use_vlm_stage_recognition':True,
                                  'stage_controller':'proprio_v4','cached_functions_dir':None})
    runner.output_dir=str(tmp_path);runner.backend='libero';runner.adapter=object()
    cfg=OmegaConf.create({'main':runner.config,'perception':{'keypoint_detector':{},
        'sam3':{'enabled':False},'gemini_grounding':{'enabled':False},'vlm_agent':config,'gemini':config}})
    runner._init_components(cfg)
    assert runner.vlm_agent.client is None
    assert runner.vlm_agent.api_request_counter.snapshot()['backend']=='codex_cli'
    assert runner.gemini_stage_recognizer.output_format=='stage_observation_v1'
