"""Synthetic CPU boundaries, exact native bytes, no simulator or tensor replay."""
import copy
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import pytest
import torch
from test_rdt_steer import _patch_core_imports


def identity(step=0):
    return dict(episode=0,stage=1,provider={'source':'full','code':'semantic'},target_index=0,
        tracker_instance=7,tracker_generation=2,target_status='tracked',task_id=0,
        source_commit='1'*40,run_id='synthetic',step=step,decision_id=f'e0:d{step//8}:s{step}')


def packet(position=(0.,0.,0.)):
    return {'observed_eef':torch.tensor(position,dtype=torch.float64)}


def selected(origin='observed_open_approach',dtype=torch.float32):
    from core.qd_nonprogress_tangent import NonprogressMemory
    from core.rdt_libero_action_converter import decode_rdt_libero_action_chunk
    memory=NonprogressMemory();who=identity();memory.enter(who,packet(),guided=True)
    plan=torch.zeros(64,128,dtype=dtype);plan[:8,39]=.5;plan[:8,10]=-1.
    # Exact-content aliases must not determine origin: winner occurrence 1.
    entries=[dict(occurrence=j,iteration=0,plan=plan.clone()) for j in range(2)]
    decision=SimpleNamespace(identity=who,entries=entries,origins=['observed_open_approach',origin],packet=packet())
    entry=SimpleNamespace(occurrence_id=1,source_iter=0,action=plan)
    memory.select(decision,entry,plan[None]);memory.finish()
    actions=decode_rdt_libero_action_chunk(plan[None],8)
    memory.bind_decode(plan[None].float(),actions);memory.commit(actions,8,0)
    return memory,actions


def complete(memory,actions,terminal=None):
    for j in range(8 if terminal is None else terminal):
        memory.acknowledge(action=actions[0,j],step=j,index=j+1,terminated=False,truncated=j+1==terminal)


@pytest.mark.parametrize('field',list(identity()))
@pytest.mark.parametrize('kind',['missing','changed'])
def test_each_identity_boundary_consumes(field,kind):
    m,a=selected();complete(m,a);next_id=identity(8)
    if kind=='missing':del next_id[field]
    elif field=='decision_id':next_id[field]=identity()['decision_id']
    elif isinstance(next_id[field],int):next_id[field]+=1
    elif field=='provider':next_id[field]['code']='changed'
    elif field=='target_status':next_id[field]='static_background'
    else:next_id[field]='2'*40 if field=='source_commit' else 'changed'
    assert not m.enter(next_id,packet(),guided=True)
    assert m.previous is None
    m.finish();assert not m.enter(identity(16),packet(),guided=True)


@pytest.mark.parametrize('origin,eligible',[('observed_open_approach',True),('ordinary',False),('nonprogress_tangent',False),('observed_close_dwell',False),('unknown',False)])
def test_exact_winner_alias_origin(origin,eligible):
    m,a=selected(origin);complete(m,a)
    assert m.previous['aliases']==[0,1]
    assert m.previous['native'] is m.previous['decoded'] is None
    assert m.enter(identity(8),packet(),guided=True) is eligible
    m.finish();assert not m.latch and not m.enter(identity(16),packet(),guided=True)


@pytest.mark.parametrize('at',range(1,9))
@pytest.mark.parametrize('termination',[False,True])
def test_terminal_at_each_ack_including_eighth(at,termination):
    m,a=selected()
    for j in range(at):m.acknowledge(action=a[0,j],step=j,index=j+1,terminated=termination and j+1==at,truncated=not termination and j+1==at)
    assert m.previous is None and not m.enter(identity(8),packet(),guided=True)


@pytest.mark.parametrize('fault',['wrong_index','wrong_step','duplicate','wrong_action','signed_zero','commit','decode','horizon','occurrence','iteration','native','nested'])
def test_mandatory_transport_errors(fault):
    from core.qd_nonprogress_tangent import NonprogressMemory
    m,a=selected()
    with pytest.raises((ValueError,RuntimeError)):
        if fault in ('commit','horizon'):m.commit(a,7 if fault=='horizon' else 8,0)
        elif fault=='decode':m.bind_decode(torch.zeros(1,64,128),a)
        elif fault=='nested':m.enter(identity(8),packet(),guided=True);m.enter(identity(8),packet(),guided=True)
        elif fault in ('occurrence','iteration','native'):
            m.reset('test');m.enter(identity(),packet(),guided=True)
            plan=torch.zeros(64,128);d=SimpleNamespace(identity=identity(),packet=packet(),entries=[dict(occurrence=0,iteration=0,plan=plan)],origins=['ordinary'])
            entry=SimpleNamespace(occurrence_id=None if fault=='occurrence' else 0,source_iter=1 if fault=='iteration' else 0,action=plan)
            m.select(d,entry,plan[None]+(1 if fault=='native' else 0))
        else:
            index=2 if fault=='wrong_index' else 1;step=1 if fault=='wrong_step' else 0
            action=a[0,0].clone()
            if fault=='wrong_action':action[0]+=1
            if fault=='signed_zero':action[1]=-0.
            if fault=='duplicate':m.acknowledge(action=action,step=0,index=1,terminated=False,truncated=False)
            m.acknowledge(action=action,step=step,index=index,terminated=False,truncated=False)


@pytest.mark.parametrize('count',[0,1,7])
def test_missing_full8_and_ambiguity(count):
    m,a=selected()
    for j in range(count):m.acknowledge(action=a[0,j],step=j,index=j+1,terminated=False,truncated=False)
    assert not m.enter(identity(8),packet(),guided=True)
    m,a=selected();complete(m,a);m.previous['ambiguous']=True
    assert not m.enter(identity(8),packet(),guided=True)


@pytest.mark.parametrize('end,active',[(0.,True),(-1.,True),(1.,False),(2**-52,False),(-2**-52,True)])
def test_fixed_binary64_dot_boundary(end,active):
    from core.qd_nonprogress_tangent import nonprogress
    m,a=selected();complete(m,a)
    assert m.enter(identity(8),packet((end,0.,0.)),guided=True) is active
    # Exact cancellation, including signed zero, with fixed xyz order.
    assert nonprogress([1.,1.,0.],[0.,0.,0.],[1.,-1.,-0.])[0]
    assert nonprogress([1e16,1.,-1e16],[0.,0.,0.],[1.,1.,1.])[2]==0.


@pytest.mark.parametrize('p',[[0.,-0.,0.],[float('nan'),1.,0.],[float('inf'),0.,0.],None])
def test_zero_nonfinite_prediction(p):
    from core.qd_nonprogress_tangent import nonprogress
    assert nonprogress(p,[0.,0.,0.],[0.,0.,0.])[0] is False


@pytest.mark.parametrize('missing',['prior','current','nonfinite'])
def test_physical_unknown(missing):
    m,a=selected();complete(m,a)
    ctx=packet()
    if missing=='prior':m.previous['eef']=None
    elif missing=='current':ctx['observed_eef']=None
    else:ctx['observed_eef'][0]=float('nan')
    assert not m.enter(identity(8),ctx,guided=True)


@pytest.mark.parametrize('reason',['episode_reset','stage_change','guidance_change','exception','abort','source_change','runtime_change'])
def test_resets_and_unguided(reason):
    m,a=selected();complete(m,a);m.reset(reason)
    assert not m.enter(identity(8),packet(),guided=True)
    m,a=selected();complete(m,a);assert not m.enter(identity(8),packet(),guided=False)


def geometry(target):
    return dict(target=torch.tensor(target,dtype=torch.float64),observed_eef=torch.zeros(3,dtype=torch.float64),
        hand_quaternion_xyzw=torch.tensor([0.,0.,0.,1.],dtype=torch.float64),gripper_qpos=torch.tensor([.02,-.02],dtype=torch.float64),target_recognized=True)


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('target,axis',[((.08,0.,0.),1),((0.,.08,0.),0),((.02,.02,.0164),0),((.1,.2,-.0036),2),((2.,1.,0.),2)])
def test_axes_ties_clipping_native_remainder(dtype,target,axis):
    from core.qd_nonprogress_tangent import propose
    from core.qd_capture_dwell_proposal import _same_native_bytes as same
    from scripts.qd_ed_n36_reference import reconstruct
    template=torch.linspace(-.7,.7,64*128).reshape(64,128).to(dtype);template[9,0]=-0.;template[0,0]=-0.
    before=template.clone();g=geometry(target);r,path=propose(template,**g)
    candidate,arrival,reason,reference=reconstruct(template,g['target'],g['observed_eef'],g['hand_quaternion_xyzw'],g['gripper_qpos'],eligible=True)
    assert same(template,before) and same(r.candidate,candidate) and path['axis']==axis
    mask=torch.ones_like(template,dtype=torch.bool);mask[:8,[39,40,41,42,43,44,10]]=False
    assert same(r.candidate[mask],template[mask])
    assert (r.candidate[:8,39:42].abs()<=1).all()
    assert (r.candidate[:8,42:45]==0).all() and (r.candidate[:8,10]==-1).all()
    assert same(path['native_commands'],reference['native_commands'])
    noop,_=propose(r.candidate,**g);assert noop.candidate is None and noop.reason=='no_native_change'


@pytest.mark.parametrize('fault',['inside','zero_quat','missing','nonfinite','empty_gap','unsupported_dtype'])
def test_geometry_fail_closed_and_close_priority(fault):
    from core.qd_nonprogress_tangent import propose
    from core.qd_observed_jaw_approach import propose as direct
    from core.qd_capture_dwell_proposal import _same_native_bytes as same
    p=torch.zeros(64,128);g=geometry((0.,0.,0.) if fault=='inside' else (.08,0.,0.))
    if fault=='zero_quat':g['hand_quaternion_xyzw'].zero_()
    if fault=='missing':g['gripper_qpos']=None
    if fault=='nonfinite':g['observed_eef'][0]=float('nan')
    if fault=='empty_gap':g['gripper_qpos']=-g['gripper_qpos']
    if fault=='unsupported_dtype':
        with pytest.raises(ValueError):propose(p.double(),**g)
        return
    r,path=propose(p,**g);n34=direct(p,**g)
    assert r.reason==n34.reason
    if fault=='inside':assert same(r.candidate,n34.candidate)
    else:assert r.candidate is None
    assert path is None


def test_latch_is_frozen():
    from core.qd_nonprogress_tangent import BoundaryLatch
    latch=BoundaryLatch(True)
    with pytest.raises(FrozenInstanceError):latch.eligible=False


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_ten_updates_clone_each_changed_current_template(dtype):
    from core.qd_nonprogress_tangent import NonprogressDecision, propose
    from core.qd_ed import QDArchive
    from core.rdt_policy_steer import _EDSConfig
    from core.qd_capture_dwell_proposal import _same_native_bytes as same
    from test_n31_capture_dwell_integration import packet as observation
    m,a=selected(dtype=dtype);complete(m,a)
    binding={k:identity()[k] for k in ('task_id','source_commit','run_id')}
    cfg=_EDSConfig(observed_jaw_approach_mode='observed_jaw_approach_v1',n34_runtime_binding=binding,
        nonprogress_tangent_mode='nonprogress_tangent_v1',n36_runtime_binding=binding)
    ctx=observation(.08);ctx['task_id']=0;ctx['tracker']['generation']=2
    semantic=SimpleNamespace(identity=identity()['provider'],target_index=0,validate=lambda _:None)
    mask=torch.zeros(1,1,128,dtype=dtype);mask[:,:,[10,39,40,41,42,43,44]]=1
    decision=NonprogressDecision(semantic,ctx,ctx['keypoints'].to(dtype),episode=0,stage=1,step=8,
        action_mask=mask,config=cfg,memory=m)
    assert decision.memory_eligible
    archive=QDArchive(grid_shape=(4,4))
    def population(round):
        plans=torch.zeros(16,64,128,dtype=dtype);plans[:,:,10]=-1.
        plans[:,8:,39]=(round+1)/32.;plans[:,9,40]=-0.;plans[:,10,40]=torch.arange(16,dtype=dtype)/64.
        return plans
    def score(plans,round):
        decision.scope=('canonical_initial' if round==-1 else 'canonical_offspring',round,'initial_population' if round==-1 else 'rollout')
        rewards=torch.zeros(16,dtype=dtype);rewards[14]=round+2
        xyz=torch.zeros(16,9,3,dtype=dtype)
        decision.record_score(plans,{'projected_xyz':xyz,'source_origins':[torch.zeros(3,dtype=torch.float64) for _ in range(16)]},rewards,-rewards,None)
        archive.update(actions=plans,rewards=rewards,costs=-rewards,descriptors=torch.zeros(16,2),
            cell_ids=torch.zeros(16,dtype=torch.long),source_iter=round,occurrence_ids=tuple(range((round+1)*16,(round+2)*16)))
    score(population(0),-1)
    templates=[]
    for it in range(10):
        best=archive.select_global_best()[1];templates.append(best.action.clone())
        decision.prepare(archive,it,[],ctx['keypoints'].to(dtype),None)
        expected,_=propose(best.action,**geometry((.08,0.,0.)))
        assert decision.memory_eligible and decision.pending['memory_eligible']
        assert same(decision.pending['candidate'],expected.candidate)
        ordinary=population(it+1);before=ordinary.clone();after=decision.apply(ordinary,None)
        assert same(before,ordinary) and same(after[:15],before[:15])
        assert same(after[15,8:],best.action[8:])
        score(after,it)
    assert len({float(x[8,39]) for x in templates})==10
    decision.close();assert not m.latch
    with pytest.raises(RuntimeError,match='expired'):decision.prepare(archive,10,[],ctx['keypoints'].to(dtype),None)


@pytest.mark.parametrize('fault',['n35_mode','n35_binding','missing_binding','unequal_binding','wrong_mode','no_n34','off_binding','horizon'])
def test_exclusive_config(fault):
    from core.rdt_policy_steer import _EDSConfig
    from core.qd_nonprogress_tangent import validate_config
    binding={'task_id':0,'source_commit':'1'*40,'run_id':'synthetic'}
    config=_EDSConfig(nonprogress_tangent_mode='nonprogress_tangent_v1',n36_runtime_binding=binding,
        observed_jaw_approach_mode='observed_jaw_approach_v1',n34_runtime_binding=binding)
    from dataclasses import replace
    changes={'n35_mode':{'closure_intent_mode':'executed_closure_intent_v1'},
        'n35_binding':{'n35_runtime_binding':binding},'missing_binding':{'n36_runtime_binding':None},
        'unequal_binding':{'n36_runtime_binding':{**binding,'run_id':'other'}},
        'wrong_mode':{'nonprogress_tangent_mode':'unknown'},'no_n34':{'observed_jaw_approach_mode':'off'},
        'off_binding':{'nonprogress_tangent_mode':'off'},'horizon':{}}
    config=replace(config,**changes[fault])
    with pytest.raises(ValueError):validate_config(config,7 if fault=='horizon' else 8)
