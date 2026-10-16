"""CPU checks for PI05 loading, effective resampling and protocol isolation."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import pytest
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def policy_class():
    from core.pi05_steer import PI05PolicySteer
    return PI05PolicySteer


def test_strict_loader_restores_only_declared_actual_ties(tmp_path,monkeypatch,policy_class):
    from safetensors.torch import save_file
    from lerobot.configs.policies import PreTrainedConfig
    monkeypatch.setattr(PreTrainedConfig,'from_pretrained',lambda *a,**k:SimpleNamespace(compile_model=True))
    class Tiny(policy_class):
        def __init__(self,config):
            torch.nn.Module.__init__(self)
            self.a=torch.nn.Parameter(torch.zeros(2));self.b=self.a
    file=tmp_path/'model.safetensors'
    save_file({'a':torch.ones(2)},file,metadata={'b':'a'})
    model=Tiny.from_pretrained(tmp_path)
    assert torch.equal(model.a,torch.ones(2)) and model.a is model.b
    assert model._checkpoint_load['restored_tied_aliases']=={'b':'a'}
    save_file({'a':torch.ones(2)},file)
    with pytest.raises(RuntimeError,match='Missing key'):Tiny.from_pretrained(tmp_path)
    class Untied(Tiny):
        def __init__(self,config):
            super().__init__(config);self.b=torch.nn.Parameter(torch.zeros(2))
    save_file({'a':torch.ones(2)},file,metadata={'b':'a'})
    with pytest.raises(RuntimeError,match='Missing key'):Untied.from_pretrained(tmp_path)
    file.write_bytes(b'broken')
    with pytest.raises(Exception):Tiny.from_pretrained(tmp_path)


def test_fkd_scores_real_euler_steps_and_sorts_terminal(policy_class):
    obj=SimpleNamespace(_action_chunk_horizon=10,_sample_to_trajectory_3d=lambda x:x)
    fkd=policy_class._init_fkd(obj,{'lmbda':1.0},20,10,.8,torch.zeros(1,3),
                              lambda kp,traj:traj.mean(),torch.device('cpu'))
    x=torch.arange(20,dtype=torch.float32).view(20,1,1).expand(20,10,3)/100
    for step in range(2,10):x,_=fkd.resample(sampling_idx=step,latents=x,x0_preds=x)
    scored=[e for e in fkd.get_diagnostics()['events'] if e['scored']]
    assert [e['timestep'] for e in scored]==[2,7,9]
    assert sorted(scored[-1]['terminal_sort_indices'])==list(range(20))
    assert x[0].mean()==x.mean((1,2)).max()


def test_fkd_does_not_replace_failed_reward_with_zero(policy_class):
    obj=SimpleNamespace(_action_chunk_horizon=10,_sample_to_trajectory_3d=lambda x:x)
    def broken(*_):raise ValueError('bad reward')
    fkd=policy_class._init_fkd(obj,{},2,10,.8,torch.zeros(1,3),broken,torch.device('cpu'))
    with pytest.raises(ValueError,match='bad reward'):
        fkd.resample(sampling_idx=2,latents=torch.ones(2,10,3),x0_preds=torch.ones(2,10,3))


def test_gradient_failure_is_not_unguided_fallback(policy_class):
    obj=SimpleNamespace(_adapter=True,_episode_compute={'reward_gradient_calls':0},
        _chunk_metrics={'reward_gradient_attempts':0},_action_chunk_horizon=10,
        _sample_to_trajectory_3d=lambda x:x)
    def broken(*_):raise ValueError('bad reward')
    with pytest.raises(RuntimeError,match='refusing silent'):
        policy_class._compute_keypoint_gradient(obj,torch.ones(2,10,3),torch.zeros(1,3),broken)


def test_padded_latents_are_unpadded_before_action_normalization(policy_class):
    received=[]
    def postprocess(x):
        received.append(tuple(x.shape))
        return x*torch.ones(7)+torch.zeros(7)
    adapter=SimpleNamespace(delta_actions_to_ee_trajectory=lambda x:x[:,:3].cumsum(0))
    obj=SimpleNamespace(_adapter=adapter,_postprocessor=postprocess,
                        _original_action_dim=7,_action_chunk_horizon=10)
    x=torch.ones(2,50,32,requires_grad=True)
    result=policy_class._sample_to_trajectory_3d(obj,x)
    result.sum().backward()
    assert received==[(2,50,7)] and result.shape==(2,10,3)
    assert x.grad[...,:3].abs().sum()>0 and x.grad[...,7:].abs().sum()==0


def test_pi05_protocol_does_not_inherit_rdt_rng_or_swap(tmp_path):
    from scripts.pi05_runtime import load_config
    from scripts.steering_runtime import load_config as rdt_config
    local={k:'/assets/'+k for k in ('pi05_checkpoint','pi05_tokenizer','rdt_checkpoint','text_encoder','vision_encoder')}
    before=rdt_config(local,method='vls',output_dir=tmp_path/'rdt')
    pi=load_config(local,tmp_path/'pi05',[0,3])
    after=rdt_config(local,method='vls',output_dir=tmp_path/'rdt')
    assert before==after
    assert pi['backend']['libero']['suite_name']=='libero_object'
    assert pi['main']['episode_rng_fixture_manifest'] is None
    assert pi['main']['episode_policy_rng_mode']=='per_seed_v1'
    assert pi['main']['episode_seed_schedule']==[44,546]
    assert pi['main']['guidance_type']=='vls'
    assert pi['perception']==before['perception']
    assert before['backend']['libero']['suite_name']=='libero_object_swap'
    with pytest.raises(ValueError):load_config(local,tmp_path,[3,0])


def test_audit_rejects_nominal_fkd_without_actual_scoring():
    from scripts.audit_pi05 import metric_valid
    row=dict(schema='pi05_vls_chunk_v1',finite=True,checkpoint_load={'strict':True},
        executed_candidate_index=0,execution_horizon=10,compute_delta={'model_forward_calls':10},
        guidance=True,reward_gradient_applied=8,rbf_gradient_applied=2,reward_gradient_unavailable=0,
        sample_batch_size=20,fkd={'events':[]})
    assert not metric_valid(row)
    row['fkd']['events']=[dict(scored=True,timestep=t,terminal_sort_indices=list(range(20))) for t in [2,7,9]]
    assert metric_valid(row)
    row['checkpoint_load']['strict']=False
    assert not metric_valid(row)


def test_dino_patch_does_not_change_python_ast():
    import ast
    # The historical compatibility patch must only change comments/indentation.
    patch=Path('scripts/dependency_patches/dinov2-source.patch').read_text()
    old=''.join(line[1:] for line in patch.splitlines(True) if line.startswith((' ','-')) and not line.startswith('---'))
    new=''.join(line[1:] for line in patch.splitlines(True) if line.startswith((' ','+')) and not line.startswith('+++'))
    # Ignore the unchanged, incomplete trailing class context of this hunk.
    old=old.split('\nclass SwiGLUFFNFused')[0]
    new=new.split('\nclass SwiGLUFFNFused')[0]
    assert ast.dump(ast.parse(old))==ast.dump(ast.parse(new))


def test_download_never_overwrites_existing_different_model(tmp_path,monkeypatch):
    import scripts.prepare_public_models as assets
    import huggingface_hub
    p=tmp_path/'rdt_checkpoint/config.json';p.parent.mkdir();p.write_text('wrong')
    monkeypatch.setattr(huggingface_hub,'snapshot_download',lambda *a,**k:pytest.fail('network must not run'))
    with pytest.raises(ValueError,match='identity mismatch'):
        assets.download(SimpleNamespace(model='rdt',directory=tmp_path))
    assert p.read_text()=='wrong'
