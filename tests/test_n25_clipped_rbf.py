"""N25 uses synthetic tensors/models/adapters only; no runtime/environment import."""
import ast
import copy
import inspect
import json
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np
import pytest
import torch

from test_rdt_steer import (_patch_core_imports, stub_steer, stub_adapter,
                            _rollout_cond, _n2_fixture_provider)

ROOT = Path(__file__).resolve().parents[1]


def native_adapter(adapter, monkeypatch):
    """Compile only frozen pure projection method; never import an env runtime."""
    tree = ast.parse((ROOT/'core/env_adapters/libero_adapter.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=='LiberoAdapter')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=='delta_actions_to_ee_trajectory')
    import __future__
    scope={'np':np,'torch':torch}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'pure_adapter_projection','exec',
                 flags=__future__.annotations.compiler_flag),scope)
    origins=[]
    def origin():
        origins.append(1)
        return SimpleNamespace(position=np.array([.12317,-.17312,.23141]))
    monkeypatch.setattr(adapter,'get_ee_pose_world',origin,raising=False)
    monkeypatch.setattr(adapter,'delta_actions_to_ee_trajectory',
                        MethodType(scope['delta_actions_to_ee_trajectory'],adapter))
    return origins


def config(steer, mode='N25'):
    raw=json.loads((ROOT/f'configs/qd_ed_final/candidate_{mode.lower()}.json').read_text())
    return steer._resolve_eds_config_with_reference_defaults(raw['profile'])


def input_tensor(dtype, B=4):
    x=torch.zeros(B,64,128,dtype=dtype)
    x[:,:8,39]=torch.linspace(-.7,.7,B,dtype=dtype)[:,None]
    x[:,:8,40]=torch.linspace(.6,-.4,B,dtype=dtype)[:,None]
    x[:,:8,41]=torch.arange(8,dtype=dtype)[None,:]/32
    x[:,:,10]=.25
    return x


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_custom_derivative_and_native_forward(dtype):
    from core.qd_actuator_clipped_rbf import strict_interior_clip
    values=torch.tensor([-2.,-1.,-.5,0.,.5,1.,2.],dtype=dtype,requires_grad=True)
    out=strict_interior_clip(values)
    assert torch.equal(out,values.detach().clamp(-1,1))
    out.sum().backward()
    assert torch.equal(values.grad,torch.tensor([0,0,1,1,1,0,0],dtype=dtype))


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_interior_original_bitwise_parity_origin_count_rng(stub_steer,stub_adapter,monkeypatch,dtype):
    from core.qd_actuator_clipped_rbf import MODE
    origins=native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=4,
                         policy_config={'action_chunk_horizon':8})
    x=input_tensor(dtype);saved=x.clone();rng=torch.random.get_rng_state().clone()
    old=stub_steer._compute_diversity_gradient(x)
    new,evidence=stub_steer._compute_eds_diversity_gradient(x,descriptor_mode=MODE,descriptor_cfg={})
    assert torch.equal(old,new)
    assert len(origins)==8 and torch.equal(x,saved)
    assert torch.equal(rng,torch.random.get_rng_state())
    assert evidence['clipped_components']==evidence['boundary_components']==0
    assert evidence['interior_components']==4*8*3
    assert evidence['summary_only_not_exact_replay'] is True
    assert torch.count_nonzero(new[:,8:])==0
    inactive=[k for k in range(128) if k not in (39,40,41)]
    assert torch.count_nonzero(new[:,:,inactive])==0
    counters=stub_steer.get_episode_compute_counters()
    assert counters['rbf_gradient_calls']==2 and counters['rbf_gradient_batch_rows']==8
    assert counters['model_forward_calls']==counters['reward_calls']==0


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('scenario',['coincident','all_saturated','mixed'])
def test_saturation_zero_valid_nontranslation_and_global_norm(stub_steer,stub_adapter,monkeypatch,dtype,scenario):
    from core.qd_actuator_clipped_rbf import MODE
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=4,
                         policy_config={'action_chunk_horizon':8})
    x=input_tensor(dtype)
    if scenario=='coincident':x[:,:8,39:42]=.25
    elif scenario=='all_saturated':x[:,:8,39:42]=torch.tensor([2.,-2.,1.,-1.],dtype=dtype)[:,None,None]
    else:x[0,:8,39:42]=2.;x[1,:8,39]=1.;x[2,:8,40]=-1.
    gradient,e=stub_steer._compute_eds_diversity_gradient(x,descriptor_mode=MODE,descriptor_cfg={})
    values=x[:,:8,39:42];g=gradient[:,:8,39:42]
    assert torch.count_nonzero(g[(values<=-1)|(values>=1)])==0
    assert torch.isfinite(gradient).all()
    if scenario!='mixed':assert torch.count_nonzero(gradient)==0 and e['zero_gradient']
    else:
        assert not e['zero_gradient']
        assert e['gradient_after_normalization']['norm']==pytest.approx(1.,abs=.02)
    assert e['interior_components']+e['boundary_components']+e['clipped_components']==4*8*3


@pytest.mark.parametrize('fault',['nan','inf','shape','dtype','horizon','batch','adapter','projection_nonfinite','projection_shape'])
def test_fail_closed_without_baseline_fallback(stub_steer,stub_adapter,monkeypatch,fault):
    from core.qd_actuator_clipped_rbf import MODE
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=4,
                         policy_config={'action_chunk_horizon':8})
    x=input_tensor(torch.float32)
    if fault=='nan':x[0,0,0]=float('nan')
    if fault=='inf':x[0,0,39]=float('inf')
    if fault=='shape':x=x[:,:8]
    if fault=='dtype':x=x.double()
    if fault=='horizon':stub_steer._action_chunk_horizon=7
    if fault=='batch':x=x[:1]
    if fault=='adapter':stub_steer._adapter=None
    if fault=='projection_nonfinite':monkeypatch.setattr(stub_steer,'_rdt_sample_to_trajectory_3d',lambda _:torch.full((1,9,3),float('nan')))
    if fault=='projection_shape':monkeypatch.setattr(stub_steer,'_rdt_sample_to_trajectory_3d',lambda _:torch.zeros(1,8,3))
    monkeypatch.setattr(stub_steer,'_compute_diversity_gradient',lambda _:pytest.fail('raw fallback'))
    with pytest.raises(ValueError):stub_steer._compute_eds_diversity_gradient(x,descriptor_mode=MODE,descriptor_cfg={})


def test_profile_only_two_modes_parent_rescue_default_off_and_config_closed(stub_steer):
    a=json.loads((ROOT/'configs/qd_ed_final/candidate_n23.json').read_text())['profile']
    b=json.loads((ROOT/'configs/qd_ed_final/candidate_n25.json').read_text())['profile']
    changed={k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}
    assert changed=={'initial_diversity_descriptor_mode','rollout_diversity_descriptor_mode'}
    cfg=config(stub_steer);assert cfg.qd_gripper_rescue_mode=='none'
    assert cfg.population_size==16 and cfg.cem_iters==10
    for change in [{'initial_diversity_descriptor_mode':'absolute_eef'},
                   {'rollout_diversity_descriptor_mode':'absolute_eef'},
                   {'qd_gripper_rescue_mode':'full_close_parent_rescue_v1'},
                   {'qd_quality_mode':'provider'},{'population_size':8},{'initial_diversity_scale':21.}]:
        with pytest.raises(ValueError):stub_steer._resolve_eds_config_with_reference_defaults(b|change)
    assert config(stub_steer,'N23').initial_diversity_descriptor_mode=='absolute_eef'


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_initial_and_rollout_actual_schedule_model_rng_and_summary(stub_steer,stub_adapter,monkeypatch,dtype):
    from core.qd_actuator_clipped_rbf import MODE
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,
                         policy_config={'action_chunk_horizon':8})
    cond=_rollout_cond(stub_steer);x=input_tensor(dtype,16)
    # Score adapter synthetic only: this test observes proposal schedules, not quality.
    monkeypatch.setattr(stub_steer,'_eds_score_population_as_cost',
                        lambda values,**kw:(torch.zeros(16,dtype=dtype),{}))
    runs=[]
    for mode in ['N23','N25']:
        stub_steer.reset_episode_compute_counters();stub_steer._noise_scheduler.last_step_args=[]
        torch.manual_seed(251)
        cfg=config(stub_steer,mode)
        initial,ii=stub_steer._eds_initial_denoise_rbf_diverse(x_t=x.clone(),cond=cond,cfg=cfg)
        initial_steps=[t for _,t in stub_steer._noise_scheduler.last_step_args]
        stub_steer._noise_scheduler.last_step_args=[]
        final,costs,ri=stub_steer._eds_rollout_rbf_diverse_reference(cond=cond,action_mask=cond['action_mask'],
            noisy_action=x.clone(),keypoints=torch.zeros(1,3,dtype=dtype),guidance_fns=[],n_trunc_steps=3,
            cfg=cfg,iter_idx=2,reward_mode='normal',shuffle_seed=0)
        runs.append((stub_steer.get_episode_compute_counters(),torch.random.get_rng_state().clone(),initial_steps,
                     [t for _,t in stub_steer._noise_scheduler.last_step_args]))
        if mode=='N25':
            for phase,items in [('initial',ii['direction_rbf_evidence_by_step']),('rollout',ri['direction_rbf_evidence_by_step'])]:
                assert items
                for row in items:
                    assert row['phase']==phase and row['descriptor_mode']==MODE
                    assert row['iteration']==(-1 if phase=='initial' else 2)
                    assert row['masked_gradient']['finite'] and row['update_operand']['finite']
                    assert row['summary_only_not_exact_replay']
            assert ri['rollout_diversity_fallback_used'] is False
            assert ii['initial_diversity_fallback_used'] is False
            # Every synthetic scheduler delta touches only the original translation indices.
            for output,t in stub_steer._noise_scheduler.last_step_args:
                assert torch.count_nonzero(output[:,8:])==0
                assert torch.count_nonzero(output[:,:,[k for k in range(128) if k not in (39,40,41)]])==0
    assert runs[0][0]==runs[1][0]
    assert torch.equal(runs[0][1],runs[1][1])
    assert runs[0][2:]==runs[1][2:]


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_full_synthetic_guided_loop_176_11_and_json_telemetry(stub_steer,stub_adapter,monkeypatch,dtype):
    from test_qd_actuator_clipped_quality import static_adapter_fixture
    for name,value in vars(static_adapter_fixture()).items():monkeypatch.setattr(stub_adapter,name,value,raising=False)
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,
                         policy_config={'action_chunk_horizon':8})
    provider=_n2_fixture_provider(index=0)
    points=torch.tensor([[.1124,-.071,.3154],[.13,-.21,.39]],dtype=dtype)
    x=input_tensor(dtype,16);runs=[]
    for mode in ['N23','N25']:
        stub_steer.reset();torch.manual_seed(2525)
        selected=stub_steer._eds_guided_denoise_loop(x_t=x.clone(),cond=_rollout_cond(stub_steer),
            keypoints=points,guidance_fns=[provider],eds_config=config(stub_steer,mode),
            verbose=False,global_step=24,current_stage=1)
        metrics=stub_steer.get_last_eds_metrics();compute=stub_steer.get_episode_compute_counters()
        assert metrics['search_evaluation_count']==176 and metrics['score_call_count']==11
        assert metrics['resample_count']==metrics['renoise_count']==metrics['rollout_count']==10
        assert not any(key.startswith('qd_gripper_rescue_') for key in metrics)
        assert torch.isfinite(selected).all()
        if mode=='N25':
            groups=[metrics['initial_direction_rbf_evidence_by_step'],*metrics['rollout_direction_rbf_evidence_by_iter']]
            rows=[row for group in groups for row in group]
            assert len(rows)==compute['rbf_gradient_calls'] and rows
            assert {row['phase'] for row in rows}=={'initial','rollout'}
            for row in rows:assert row['global_step']==24 and row['stage']==1
            json.dumps(metrics,allow_nan=False)
        runs.append((compute,torch.random.get_rng_state().clone()))
    assert runs[0][0]==runs[1][0]
    assert torch.equal(runs[0][1],runs[1][1])
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_native_witness_roundtrip_caps_first_decision_and_instrumentation_parity(stub_steer,stub_adapter,monkeypatch,tmp_path,dtype):
    from core.decision_evidence import DecisionEvidence
    from core.qd_actuator_clipped_rbf import BoundedWitness
    from test_qd_actuator_clipped_quality import static_adapter_fixture
    for name,value in vars(static_adapter_fixture()).items():monkeypatch.setattr(stub_adapter,name,value,raising=False)
    origins=native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,
                         policy_config={'action_chunk_horizon':8})
    provider=_n2_fixture_provider(index=0)
    points=torch.tensor([[.1124,-.071,.3154],[.13,-.21,.39]],dtype=dtype)
    x=input_tensor(dtype,16);runs=[]
    for instrumented in [False,True]:
        stub_steer.reset();torch.manual_seed(2525);origins.clear()
        rec=DecisionEvidence(tmp_path/'captured',episode=0) if instrumented else None
        stub_steer._decision_evidence=rec
        monkeypatch.setattr(stub_adapter,'_decision_evidence',rec,raising=False)
        if rec:rec.begin_decision(global_step=24,stage=1,use_guidance=True,keypoints=points,providers=[provider])
        selected=stub_steer._eds_guided_denoise_loop(x_t=x.clone(),cond=_rollout_cond(stub_steer),
            keypoints=points,guidance_fns=[provider],eds_config=config(stub_steer),verbose=False,
            global_step=24,current_stage=1)
        metrics=stub_steer.get_last_eds_metrics();json.dumps(metrics,allow_nan=False)
        runs.append((selected.clone(),torch.random.get_rng_state().clone(),
                     stub_steer.get_episode_compute_counters(),len(origins)))
        if rec:
            rec.flush();assert not rec.failed
            events=[e for p in sorted(rec.root.glob('bundle_*.pt'))
                    for e in torch.load(p,map_location='cpu',weights_only=True)['events']]
            witnesses=[e for e in events if e['event']=='n25_rbf_witness']
            cover=[e for e in events if e['event']=='n25_rbf_witness_coverage']
            assert len(witnesses)==11 and len(cover)==1
            assert cover[0]['values']['missing_slots']==[]
            assert cover[0]['values']['numeric_bytes']<=220*1024
            for event in witnesses:
                assert event['decision_id']==rec.decision_id and event['global_step']==24
                tensors=event['values']['tensors'];meta=event['values']['metadata']
                assert meta['numeric_bytes']<=20*1024
                assert len(json.dumps(meta).encode())<=16*1024
                assert tensors['input_xyz'].shape==(16,8,3)
                assert tensors['input_xyz'].dtype==dtype
                assert torch.equal(tensors['model_output_after'],tensors['model_output_before']+tensors['update_operand'])
                assert meta['call']['update_operand_is_measured_output_delta'] is False
            manager=stub_steer._n25_rbf_witness
            manager.begin(rec)
            assert manager.prepare('initial',-1) is None
            manager.finish()  # No backfill or extra coverage for a second guided decision.
            assert manager.numeric_bytes==cover[0]['values']['numeric_bytes']
            stub_steer.reset()
            assert not stub_steer._n25_rbf_witness.first_consumed
    assert torch.equal(runs[0][0],runs[1][0])
    assert torch.equal(runs[0][1],runs[1][1])
    assert runs[0][2:]==runs[1][2:]


def test_witness_fixed_selection_missing_slots_no_backfill_and_caps():
    from core.qd_actuator_clipped_rbf import BoundedWitness
    events=[];rec=SimpleNamespace(record=lambda event,**values:events.append((event,values)))
    m=BoundedWitness();m.begin(None)
    assert m.prepare('initial',-1) is None
    m.finish();m.begin(rec)
    assert m.prepare('rollout',0) is None  # Missing recorder does not shift sampling later.
    m=BoundedWitness();m.begin(rec)
    sample=m.prepare('initial',-1);assert sample=={}
    assert m.prepare('initial',-1) is None
    m.finish();assert len(events)==1 and len(events[0][1]['missing_slots'])==11
    fields={'input_xyz','source_origins','cast_origins','projected_xyz','gradient_before','gradient_after',
            'update_operand','model_output_before','model_output_after'}
    capture={k:torch.zeros((16,3) if 'origins' in k else (16,8,3)) for k in fields}
    for fault in ['fields','shape','numeric_call','numeric_episode','metadata','duplicate','nonfinite']:
        m=BoundedWitness();m.begin(rec);m.prepare('initial',-1)
        value=copy.deepcopy(capture);e={'phase':'initial','iteration':-1}
        if fault=='fields':value['full_latent']=torch.zeros(16,64,128)
        if fault=='shape':value['input_xyz']=torch.zeros(16,64,3)
        if fault=='numeric_call':m.NUMERIC_CALL_CAP=1
        if fault=='numeric_episode':m.numeric_bytes=m.NUMERIC_EPISODE_CAP
        if fault=='metadata':e['bad']='x'*16384
        if fault=='duplicate':m.recorded=[('initial',-1)]
        if fault=='nonfinite':value['input_xyz'][0,0,0]=float('nan')
        with pytest.raises(ValueError):m.emit(value,e)


@pytest.mark.parametrize('phase',['initial','rollout'])
def test_nonfinite_model_output_does_not_replay_baseline(stub_steer,stub_adapter,monkeypatch,phase):
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,
                         policy_config={'action_chunk_horizon':8})
    cfg=config(stub_steer);cond=_rollout_cond(stub_steer);x=input_tensor(torch.float32,16)
    monkeypatch.setattr(stub_steer,'_counted_dit',lambda values,*a:torch.full_like(values,float('inf')))
    monkeypatch.setattr(stub_steer,'_eds_initial_fallback_to_iid',lambda **kw:pytest.fail('IID fallback'))
    monkeypatch.setattr(stub_steer,'_eds_rollout_fallback_to_baseline',lambda **kw:pytest.fail('baseline fallback'))
    with pytest.raises(ValueError,match='nonfinite'):
        if phase=='initial':stub_steer._eds_initial_denoise_rbf_diverse(x_t=x,cond=cond,cfg=cfg)
        else:stub_steer._eds_rollout_rbf_diverse_reference(cond=cond,action_mask=cond['action_mask'],
            noisy_action=x,keypoints=torch.zeros(1,3),guidance_fns=[],n_trunc_steps=3,cfg=cfg,
            iter_idx=0,reward_mode='normal',shuffle_seed=0)


def test_missing_autograd_gradient_rejected(stub_steer,stub_adapter,monkeypatch):
    from core.qd_actuator_clipped_rbf import MODE
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,
                         policy_config={'action_chunk_horizon':8})
    monkeypatch.setattr(torch.autograd,'grad',lambda *a,**kw:(None,))
    with pytest.raises(ValueError,match='missing gradient'):
        stub_steer._compute_eds_diversity_gradient(input_tensor(torch.float32,16),descriptor_mode=MODE,descriptor_cfg={})
