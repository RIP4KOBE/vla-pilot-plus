"""Exercise both clients' actual environment lookup, using a fake credential."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))


def test_fresh_reward_and_stage_use_the_same_private_runtime_credential(monkeypatch,tmp_path):
    import c0_poe_fresh_retest as fresh
    import stage_closed_loop_run as run
    import core.gemini_grounder as stage
    import vlm_query.vlm_agent as guidance
    keyfile=tmp_path/'fake.key';keyfile.write_text('not-a-real-credential');keyfile.chmod(0o600)
    monkeypatch.setattr(fresh.runner,'CREDENTIAL',keyfile)
    env=run.worker_env()
    assert env['CUDA_VISIBLE_DEVICES']=='2'
    assert env['GOOGLE_API_KEY']==env['OPENAI_API_KEY']=='not-a-real-credential'
    for key in ('GOOGLE_API_KEY','OPENAI_API_KEY','OPENAI_BASE_URL'):
        monkeypatch.setenv(key,env[key])
    clients=[]
    def client(**kwargs):
        clients.append(kwargs)
        return SimpleNamespace()
    monkeypatch.setattr(stage,'OpenAI',client)
    monkeypatch.setattr(guidance,'OpenAI',client)
    stage._make_client({'base_url':'https://api.poe.com/v1','api_key':None})
    guidance.VLMAgent({'api_key':None,'base_url':'https://api.poe.com/v1',
        'query_template_dir':str(ROOT/'vlm_query')},base_dir=str(tmp_path),env_type='libero')
    assert len(clients)==2
    assert all(x['api_key']=='not-a-real-credential' for x in clients)
    assert all(x['base_url']=='https://api.poe.com/v1' for x in clients)
