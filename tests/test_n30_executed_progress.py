"""Synthetic N30 tests; no real models, environment, artifacts or provider/API calls."""
import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace, MethodType
import numpy as np
import pytest
import torch
from test_rdt_steer import (_patch_core_imports, stub_steer, stub_adapter, mock_batch,
                            _n2_fixture_provider, _StubRDTModel)

ROOT = Path(__file__).resolve().parents[1]
MODE = 'executed_progress_continuation_v1'

def q0():
    return json.loads((ROOT/'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())['profiles']['Q0']['restored_profile']

def runtime_cfg(profile):
    static=json.loads((ROOT/'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())['profiles']['Q0']['static_override_values']
    pretest={k.removeprefix('main.eds_mechanism_pretest.'):v for k,v in static.items() if k.startswith('main.eds_mechanism_pretest.')}
    return {**profile,'mechanism_pretest':pretest}

def cfg():
    return json.loads((ROOT/'configs/qd_ed_final/candidate_n30.json').read_text())['profile']

def packet(start=1., target=0.):
    return {'start_eef':torch.tensor([start,0.,0.],dtype=torch.float64),
        'keypoints':torch.tensor([[target,0.,0.],[target,0.,0.]],dtype=torch.float64),
        'episode':0,'tracker':{'instance_id':4,'generation':1,
             'targets':{'0':{'valid':True,'status':'tracked'},'1':{'valid':True,'status':'tracked'}}}}

def semantic(index=0):
    return SimpleNamespace(target_index=index,identity={'code':'frozen-provider'})

def native(dtype):
    p=torch.linspace(-.8,.8,64*128).reshape(1,64,128).to(dtype)
    p[0,0,10]=0.;p[0,1,10]=-0.;p[0,2,10]=-.5
    return p

def eq(a,b):
    return a.dtype==b.dtype and a.shape==b.shape and torch.equal(a.contiguous().reshape(-1).view(torch.uint8),b.contiguous().reshape(-1).view(torch.uint8))

def prepare(h,dtype=torch.float32):
    from core.rdt_libero_action_converter import decode_rdt_libero_action_chunk
    p=native(dtype);h.begin(semantic(),packet(),stage=1,step=0);h.select(p)
    a=decode_rdt_libero_action_chunk(p.float(),8);h.bind_decode(p.float(),a);h.commit(a,8,0)
    return p,a

def finish(h,a,end=.5):
    for i in range(8):
        h.acknowledge(global_step=i,execution_index=i+1,action=a[0,i],
            endpoint=torch.tensor([end,0.,0.],dtype=torch.float64),terminated=False,truncated=False)

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_native_shift_forward_decode_mask_and_rng(dtype):
    from core.qd_executed_progress import ProgressContinuation,identity
    h=ProgressContinuation();p,a=prepare(h,dtype)
    assert a[0,:3,-1].tolist()==[1.,1.,-1.]  # exact converter zero boundary
    finish(h,a);h.begin(semantic(),packet(.5,4.),stage=1,step=8)  # snapshot may move
    assert h.active and h.previous['distance_before_m']==1. and h.previous['distance_after_m']==.5
    fresh=torch.linspace(-.9,.9,16*64*128).reshape(16,64,128).to(dtype)
    before=fresh.clone();rng=torch.random.get_rng_state();out=h.propose(fresh)
    assert torch.equal(rng,torch.random.get_rng_state()) and eq(fresh,before)
    assert eq(out[:15],fresh[:15]) and eq(out[15,:56],p[0,8:]) and eq(out[15,56:],fresh[15,56:])
    mask=torch.zeros(1,1,128,dtype=dtype);mask[:,:, [39,40,41,42,43,44,10]]=1
    assert eq((out*mask)[15,:56],(p*mask)[0,8:])
    assert identity(h.previous['native_plan'])==identity(p)
    # Forward promotion check cannot be replaced by BF16 round-trip tolerance.
    h.select(p);bad=p.float().clone();bad[0,0,39]+=1e-6
    with pytest.raises(RuntimeError,match='decode'):h.bind_decode(bad,a)

@pytest.mark.parametrize('end,active',[(.5,True),(1.,False),(1.2,False),(1.-2**-52,True)])
def test_strict_float64_progress_sign(end,active):
    from core.qd_executed_progress import ProgressContinuation
    h=ProgressContinuation();_,a=prepare(h);finish(h,a,end);h.begin(semantic(),packet(),stage=1,step=8)
    assert h.active is active

@pytest.mark.parametrize('change',['stage','provider','target','tracker','generation','episode','status','reset','guidance','gap'])
def test_immediate_identity_only(change):
    from core.qd_executed_progress import ProgressContinuation
    h=ProgressContinuation();_,a=prepare(h);finish(h,a);s=semantic();p=packet();stage=1;step=8
    if change=='stage':stage=2
    elif change=='provider':s.identity['code']='different'
    elif change=='target':s.target_index=1
    elif change=='tracker':p['tracker']['instance_id']+=1
    elif change=='generation':p['tracker']['generation']+=1
    elif change=='episode':p['episode']+=1
    elif change=='status':p['tracker']['targets']['0']['status']='static_background'
    elif change=='reset':h.clear('episode_reset',reset=True)
    elif change=='guidance':h.clear('guidance_gap_or_mode_off')
    elif change=='gap':step=16
    h.begin(s,p,stage=stage,step=step);assert not h.active and h.previous is None

@pytest.mark.parametrize('fault',['missing','nonfinite','skip','duplicate','wrong_action','no_commit','terminated','truncated','partial','repeat_after8'])
def test_bad_feedback_cannot_license_memory(fault):
    from core.qd_executed_progress import ProgressContinuation
    h=ProgressContinuation();_,a=prepare(h)
    if fault=='no_commit':h.pending['committed']=False
    if fault=='partial':h.commit(a,4,0)
    for i in range(8):
        if fault=='skip' and i==3:continue
        endpoint=None if fault=='missing' and i==3 else torch.tensor([.5,0.,0.])
        if fault=='nonfinite' and i==3:endpoint[0]=float('nan')
        action=a[0,i].clone()
        if fault=='wrong_action' and i==3:action[0]+=1
        args=dict(global_step=i,execution_index=i+1,action=action,endpoint=endpoint,
            terminated=fault=='terminated' and i==3,truncated=fault=='truncated' and i==3)
        h.acknowledge(**args)
        if fault=='duplicate' and i==3:h.acknowledge(**args)
    if fault=='repeat_after8':h.acknowledge(**args)
    h.begin(semantic(),packet(),stage=1,step=8);assert not h.active

@pytest.mark.parametrize('fault',['none','tracker','targets','start','points','valid','episode'])
def test_invalid_observation_explicit(fault):
    from core.qd_executed_progress import ProgressContinuation
    h=ProgressContinuation();p=packet()
    if fault=='none':p=None
    elif fault=='tracker':p['tracker']=None
    elif fault=='targets':p['tracker']['targets']=[]
    elif fault=='start':p['start_eef'][0]=float('inf')
    elif fault=='points':p['keypoints'][0,0]=float('nan')
    elif fault=='valid':p['tracker']['targets']['0']['valid']=False
    elif fault=='episode':p['episode']=True
    h.begin(semantic(),p,stage=1,step=0)
    assert h.status=='invalid_evidence' and h.current is None
    h.begin(None,packet(),stage=1,step=8);assert h.reason=='unrecognized_single_target_provider' and h.status=='inactive'


def main_functions():
    source=(ROOT/'main.py').read_text();tree=ast.parse(source)
    names={'_progress_continuation_context','_acknowledge_progress_continuation'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    env={'torch':torch};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/'main.py'),'exec'),env)
    return env


def obs(x):return {'observation.robot_state':{'eef':{'pos':torch.tensor([[x,0.,0.]],dtype=torch.float64)}}}

class FakeRecorder:
    def __init__(self):self.events=[];self.scoring_batch_id=0
    def record(self,event,**kw):
        def freeze(x):
            if torch.is_tensor(x):return x.detach().clone()
            if isinstance(x,dict):return {k:freeze(v) for k,v in x.items()}
            if isinstance(x,(list,tuple)):return type(x)(freeze(v) for v in x)
            return x
        self.events.append({'event':event,**freeze(kw)});return len(self.events)
    def begin_scoring(self,**kw):self.scoring_batch_id+=1;return self.scoring_batch_id
    def end_scoring(self,**kw):pass
    def begin_score_call(self):pass
    def set_scoring_scope(self,**kw):pass
    def provider_return(self,*a,**kw):pass


def setup_policy(steer,adapter,monkeypatch,dtype=torch.float32,old=False):
    steer.post_init(adapter=adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    # Explicit deterministic synthetic DiT output, never instantiate a checkpoint.
    steer._dit.register_parameter('dummy',torch.nn.Parameter(torch.zeros((),dtype=dtype),requires_grad=False))
    cond=steer._rdt_model.encode_inputs
    def encode(*args):
        c=cond(*args);c['action_mask']=c['action_mask'].to(dtype);return c
    monkeypatch.setattr(steer._rdt_model,'encode_inputs',encode)
    if old:
        import core.rdt_policy_steer as module
        f=json.loads((ROOT/'tests/n30_original_control_functions.json').read_text())
        for name,source in f['functions'].items():
            ns=dict(vars(module));exec(compile(source,'<pinned-d855-control>','exec'),ns)
            monkeypatch.setattr(steer,name,MethodType(ns[name],steer))
    provider=_n2_fixture_provider(index=0)
    return provider


def call(steer,batch,provider,config,step=0,context=None,guided=True):
    return steer.select_action(batch,generate_new_chunk=True,use_guidance=guided,
        keypoints=np.array([[0.,0.,0.]],dtype=np.float64),guidance_fns=[provider],guidance_type='eds',
        eds_config=config,global_step=step,current_stage=1,executed_progress_context=context)

@pytest.mark.parametrize('pretest',[False,True])
@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_actual_main_policy_two_chunks_fixed_cost_and_native_binding(stub_steer,stub_adapter,mock_batch,monkeypatch,dtype,pretest):
    from core.qd_executed_progress import identity
    provider=setup_policy(stub_steer,stub_adapter,monkeypatch,dtype)
    funcs=main_functions();rec=FakeRecorder();stub_steer._decision_evidence=rec
    fresh=[];original=stub_steer._eds_initial_population
    def sampler(*a,**kw):
        p=original(*a,**kw);fresh.append(p.detach().clone());return p
    monkeypatch.setattr(stub_steer,'_eds_initial_population',sampler)
    p=packet();ctx=funcs['_progress_continuation_context'](obs(1.),p['keypoints'],p['tracker'],0)
    torch.manual_seed(30);actions=call(stub_steer,mock_batch,provider,runtime_cfg(cfg()) if pretest else cfg(),context=ctx)
    h=stub_steer._executed_progress;winner=h.pending['native_plan'].clone()
    assert winner.dtype==dtype and h.pending['native_identity']==identity(winner)
    stub_steer.commit_executed_progress(actions,8,0)
    for i in range(8):
        funcs['_acknowledge_progress_continuation'](stub_steer,obs(1.-.5*(i+1)/8),
            global_step=i,execution_index=i+1,action=actions[0,i],terminated=False,truncated=False)
    assert h.completed['ack_count']==8 and h.completed['native_identity']==identity(winner)
    ctx=funcs['_progress_continuation_context'](obs(.5),p['keypoints'],p['tracker'],0)
    call(stub_steer,mock_batch,provider,runtime_cfg(cfg()) if pretest else cfg(),step=8,context=ctx)
    canonical=[e for e in rec.events if e['event']=='canonical_candidate_batch']
    assert len(canonical)==22
    proposals=[e for e in rec.events if e['event']=='n30_initial_proposal']
    assert len(proposals)==2 and proposals[1]['progress_state']['active']
    mask=proposals[1]['action_mask'];pop=canonical[11]['candidates']
    assert eq(pop[:15],(fresh[1]*mask)[:15])
    assert eq(pop[15,:56],(winner*mask)[0,8:])
    assert eq(pop[15,56:],(fresh[1]*mask)[15,56:])
    assert eq(proposals[1]['inserted_row'],pop[15])
    assert eq(proposals[1]['fresh_native_population'],fresh[1])
    assert proposals[1]['initial_final_trace_semantics']=='composed_canonical_reuses_its_score'
    if pretest:
        trace=stub_steer.get_last_eds_mechanism_trace()
        initial=next(x for x in trace.stages if x.stage=='initial')
        final=next(x for x in trace.stages if x.stage=='initial_final')
        assert eq(initial.actions,final.actions) and eq(initial.costs,final.costs)
    compute=stub_steer.get_episode_compute_counters()
    assert compute['model_forward_calls']==42 and compute['model_batch_rows']==42*16
    assert compute['rbf_gradient_calls']==38
    assert compute['reward_scoring_batches']==(32 if pretest else 22)
    assert compute['reward_evaluations']==(512 if pretest else 352)
    metrics=stub_steer.get_last_eds_metrics();assert metrics['executed_progress_continuation']['active']
    assert metrics['score_call_count']==11 and metrics['search_evaluation_count']==176
    # No history applies through unguided; ordinary five-forward path retained.
    before=dict(compute);call(stub_steer,mock_batch,provider,cfg(),step=16,guided=False)
    assert h.pending is None and h.completed is None
    after=stub_steer.get_episode_compute_counters();assert after['model_forward_calls']-before['model_forward_calls']==5
    assert after['reward_evaluations']==before['reward_evaluations']

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_default_off_matches_pinned_d855_and_inactive_n30(stub_adapter,mock_batch,monkeypatch,dtype):
    from core.rdt_policy_steer import RDTSteer
    results=[]
    for mode in ('old','off','inactive'):
        s=RDTSteer(rdt_model=_StubRDTModel(),num_inference_steps=5)
        provider=setup_policy(s,stub_adapter,monkeypatch,dtype,old=mode=='old')
        p=packet();conf=q0() if mode=='old' else ({**q0(),'executed_progress_continuation_mode':'off'} if mode=='off' else cfg())
        # Old method signature intentionally has no new context argument.
        conf=runtime_cfg(conf)
        kwargs=dict(generate_new_chunk=True,use_guidance=True,keypoints=np.array([[0.,0.,0.]]),guidance_fns=[provider],guidance_type='eds',eds_config=conf,global_step=0,current_stage=1)
        if mode!='old':kwargs['executed_progress_context']=p
        torch.manual_seed(3030);out=s.select_action(mock_batch,**kwargs)
        m=s.get_last_eds_metrics()
        if mode in ('old','off'):assert 'executed_progress_continuation' not in m
        else:assert m['executed_progress_continuation']['active'] is False
        m.pop('executed_progress_continuation',None)
        results.append((out.clone(),torch.random.get_rng_state(),s.get_episode_compute_counters(),m))
    for result in results[1:]:
        assert eq(result[0],results[0][0]);assert torch.equal(result[1],results[0][1]);assert result[2]==results[0][2]
    assert 'executed_progress_continuation' not in results[0][3]


@pytest.mark.parametrize('pretest',[False,True])
def test_recorder_does_not_control_continuation(stub_adapter,mock_batch,monkeypatch,pretest):
    from core.rdt_policy_steer import RDTSteer
    traces=[]
    for record in (False,True):
        s=RDTSteer(rdt_model=_StubRDTModel(),num_inference_steps=5);fn=setup_policy(s,stub_adapter,monkeypatch)
        s._decision_evidence=FakeRecorder() if record else None;torch.manual_seed(3)
        conf=runtime_cfg(cfg()) if pretest else cfg()
        first=call(s,mock_batch,fn,conf,context=packet());s.commit_executed_progress(first,8,0)
        for i in range(8):s.acknowledge_executed_progress(global_step=i,execution_index=i+1,action=first[0,i],endpoint=torch.tensor([.5,0.,0.]),terminated=False,truncated=False)
        second=call(s,mock_batch,fn,conf,step=8,context=packet(.5));assert s._executed_progress.active
        traces.append((second.clone(),torch.random.get_rng_state(),s.get_episode_compute_counters()))
    assert eq(traces[0][0],traces[1][0]) and torch.equal(traces[0][1],traces[1][1]) and traces[0][2]==traces[1][2]


def test_main_callback_order_and_identity_capture():
    s=(ROOT/'main.py').read_text();ast.parse(s)
    assert s.index('select_kwargs["executed_progress_context"]') < s.index('action_chunk = self.policy.select_action')
    assert s.index('self.policy.commit_executed_progress(') < s.index('obs, reward, terminated, truncated, info = self.adapter.step(')
    assert s.index('obs, reward, terminated, truncated, info = self.adapter.step(') < s.index('_acknowledge_progress_continuation(self.policy, obs,')
    assert 'evidence_enabled=evidence is not None or continuation_enabled' in s
    assert 'execution_index=action_executed + 1' in s
    p=packet();f=main_functions();ctx=f['_progress_continuation_context'](obs(1.),p['keypoints'],p['tracker'],0)
    assert eq(ctx['start_eef'],p['start_eef']) and ctx['tracker']==p['tracker']
    p['tracker']['targets']['0']['valid']=False;assert ctx['tracker']['targets']['0']['valid']


def test_actual_profile_config_and_real_hydra_composition(stub_steer,stub_adapter):
    from hydra import initialize_config_dir,compose
    from omegaconf import OmegaConf
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    profiles=json.loads((ROOT/'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())['profiles']
    composed={}
    for arm in ('C0','Q0','N30'):
        base=profiles['Q0' if arm=='N30' else arm]
        # Values are frozen static command fields; no runtime, model or credentials are loaded.
        overrides=[]
        for key,val in base['static_override_values'].items():
            overrides.append(key+'='+json.dumps(val,separators=(',',':')))
        if arm=='N30':overrides.append('main.eds_config.executed_progress_continuation_mode='+MODE)
        with initialize_config_dir(version_base=None,config_dir=str(ROOT/'configs')):
            c=compose(config_name='config',overrides=overrides)
        eds=OmegaConf.to_container(c.main.eds_config,resolve=True);composed[arm]=eds
        resolved=stub_steer._resolve_eds_config_with_reference_defaults(eds)
        assert resolved.executed_progress_continuation_mode==(MODE if arm=='N30' else 'off')
    assert {k:v for k,v in composed['N30'].items() if k!='executed_progress_continuation_mode'}=={k:v for k,v in composed['Q0'].items() if k!='executed_progress_continuation_mode'}
    assert {k:v for k,v in cfg().items() if k!='executed_progress_continuation_mode'}==q0()
    for key,val in [('chunk_population_mode','warm_start_mix'),('qd_quality_mode','executed_residual_v1'),('diversity_update_mode','feasible_ray_v1')]:
        with pytest.raises(ValueError):stub_steer._resolve_eds_config_with_reference_defaults({**cfg(),key:val})


@pytest.mark.parametrize('method',['reset','reset_stage'])
def test_actual_policy_reset_clears_feedback(stub_steer,stub_adapter,method):
    from core.qd_executed_progress import ProgressContinuation
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    h=ProgressContinuation();stub_steer._executed_progress=h;_,a=prepare(h);finish(h,a)
    assert h.completed is not None
    getattr(stub_steer,method)()
    assert h.completed is None and h.pending is None and h.previous is None
    h.begin(semantic(),packet(),stage=1,step=8);assert not h.active


def test_progress_uses_unquantized_recorded_snapshot():
    from core.qd_executed_progress import ProgressContinuation
    h=ProgressContinuation();p,a=prepare(h)
    raw_target=1.+2**-30;end=1.+2**-31
    h.pending['target']=torch.tensor([raw_target,0.,0.],dtype=torch.float64)
    finish(h,a,end);h.begin(semantic(),packet(),stage=1,step=8)
    assert h.active and h.previous['distance_before_m']==2**-30 and h.previous['distance_after_m']==2**-31
    # Reconstructing from float32 provider keypoints would reverse this sign.
    assert float(torch.tensor(raw_target,dtype=torch.float32))==1. and abs(end-1.)>0.
