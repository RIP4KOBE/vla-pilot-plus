"""Adversarial CPU state and direct archive identity tests; no efficacy claim."""
from types import SimpleNamespace
import copy
import pytest
import torch
from core.qd_closure_intent import ClosureIntentMemory, MODE, validate_config
from core.qd_ed import QDArchive
from core.rdt_libero_action_converter import decode_rdt_libero_action_chunk


def identity(step=0):
    return dict(episode=0,stage=1,step=step,provider={'source':'exact'},target_index=0,
                tracker_instance=7,tracker_generation=2,target_status='tracked')


def packet(jaw=.04):
    return {'gripper_qpos':None if jaw is None else torch.tensor([jaw/2,-jaw/2],dtype=torch.float64)}


def selection(memory, *, origin='observed_close_dwell', alias=None, native=None):
    native=torch.zeros(1,64,128) if native is None else native
    native[:,:8,10]=1
    entries=[dict(occurrence=0,iteration=0,plan=native[0].clone())]
    origins=[origin]
    if alias is not None:
        entries.append(dict(occurrence=1,iteration=0,plan=native[0].clone()));origins.append(alias)
    decision=SimpleNamespace(identity=identity(),packet=packet(),entries=entries,origins=origins)
    entry=SimpleNamespace(occurrence_id=0,source_iter=0,action=native[0].clone())
    memory.enter(identity(),packet(),guided=True)
    memory.select(decision,entry,native)
    memory.finish()
    decoded=decode_rdt_libero_action_chunk(native,8)
    memory.bind_decode(native.float(),decoded)
    memory.commit(decoded,8,0)
    return decoded,decision,entry


def executed(**kwargs):
    memory=ClosureIntentMemory();decoded,_,_=selection(memory,**kwargs)
    for j in range(8):memory.acknowledge(action=decoded[0,j],step=j,index=j+1,terminated=False,truncated=False)
    assert memory.previous['native'] is None and memory.previous['decoded'] is None
    return memory


@pytest.mark.parametrize('fault',['none','stage','target','provider','episode','tracker_instance','tracker_generation','target_status',
    'gap','jaw_missing','jaw_nan','jaw_inf','jaw_equal','jaw_increasing','unguided','incomplete','open','memory','ordinary','mixed_alias'])
def test_trigger_exclusions_and_single_consumption(fault):
    memory=executed(origin='closure_intent_memory' if fault=='memory' else 'ordinary' if fault=='ordinary' else 'observed_close_dwell',
                    alias='ordinary' if fault=='mixed_alias' else None)
    current=identity(8);obs=packet(.03)
    if fault in ('stage','episode','tracker_instance','tracker_generation'):current[fault]+=1
    if fault=='target':current['target_index']=1
    if fault=='provider':current['provider']={'source':'other'}
    if fault=='target_status':current['target_status']='lost'
    if fault=='gap':current['step']=16
    if fault=='jaw_missing':obs=packet(None)
    if fault=='jaw_nan':obs=packet(float('nan'))
    if fault=='jaw_inf':obs=packet(float('inf'))
    if fault=='jaw_equal':obs=packet(.04)
    if fault=='jaw_increasing':obs=packet(.05)
    if fault=='mixed_alias':memory.previous['ambiguous']=True  # Explicit unresolved-origin witness cannot arm.
    if fault=='incomplete':memory.previous['acknowledged']=7
    if fault=='open':memory.previous['positive']=False
    assert memory.enter(current,obs,guided=fault!='unguided') == (fault=='none')
    assert memory.previous is None
    # Latch survives ten read-only parent opportunities and expires if unselected.
    assert [memory.latch for _ in range(10)]==[fault=='none']*10
    memory.finish()
    assert not memory.latch
    assert not memory.enter(identity(16),packet(.02),guided=True)


@pytest.mark.parametrize('reason',['episode_reset','stage_change','unguided_or_mode_off','terminal','exception','step_exception','incomplete_execution'])
def test_all_resets_discard_prior_and_latch(reason):
    memory=executed();memory.reset(reason)
    assert memory.previous is None and not memory.latch and not memory.boundary_open
    assert not memory.enter(identity(8),packet(.03),guided=True)
    memory.reset(reason)
    assert not memory.boundary_open


@pytest.mark.parametrize('fault',['native','decoder','duplicate_commit','step','index','action','duplicate_ack'])
def test_mandatory_contradictions_raise_and_clear(fault):
    memory=ClosureIntentMemory();decoded,_,_=selection(memory)
    with pytest.raises(ValueError):
        if fault=='native':memory.bind_decode(torch.ones(1,64,128),decoded)
        elif fault=='decoder':memory.bind_decode(memory.previous['native'].float(),decoded+1)
        elif fault=='duplicate_commit':memory.commit(decoded,8,0)
        elif fault=='duplicate_ack':
            memory.acknowledge(action=decoded[0,0],step=0,index=1,terminated=False,truncated=False)
            memory.acknowledge(action=decoded[0,0],step=0,index=1,terminated=False,truncated=False)
        else:memory.acknowledge(action=decoded[0,0]+(fault=='action'),step=1 if fault=='step' else 0,
                index=2 if fault=='index' else 1,terminated=False,truncated=False)
    assert memory.previous is None and not memory.latch


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_occurrence_survives_archive_copy_dedup_without_changing_winner(dtype):
    actions=torch.zeros(16,64,128,dtype=dtype)
    actions[:,:,10]=.5  # Different native bytes, same decoded +1 as memory.
    rewards=torch.arange(16,dtype=dtype);rewards[0]=15
    archives=[QDArchive(grid_shape=(4,4)) for _ in range(2)]
    for tagged,archive in enumerate(archives):
        archive.update(actions=actions,rewards=rewards,costs=-rewards,descriptors=torch.zeros(16,2),
            cell_ids=torch.zeros(16,dtype=torch.long),source_iter=-1,
            **({'occurrence_ids':tuple(range(16))} if tagged else {}))
    a,b=(arc.select_global_best()[1] for arc in archives)
    assert a.occurrence_id is None and b.occurrence_id==0  # stable first equal-content tie
    assert torch.equal(a.action,b.action) and a.reward==b.reward and b.action.data_ptr()!=actions.data_ptr()
    # Equal-content newcomer cannot overwrite the incumbent's direct identity.
    archives[1].update(actions=actions,rewards=rewards,costs=-rewards,descriptors=torch.zeros(16,2),
        cell_ids=torch.zeros(16,dtype=torch.long),source_iter=0,occurrence_ids=tuple(range(16,32)))
    assert archives[1].select_global_best()[1].occurrence_id==0
    assert archives[1].snapshot()[0]['occurrence_id']==0
    clone=b.action.clone();clone[:8,10]=1
    assert not torch.equal(clone,b.action)
    assert torch.equal(decode_rdt_libero_action_chunk(clone[None],8),decode_rdt_libero_action_chunk(b.action[None],8))
    untouched=torch.ones_like(clone,dtype=torch.bool);untouched[:8,10]=False
    assert torch.equal(clone[untouched],b.action[untouched])


def test_hash_equal_without_transport_never_claims_direct_origin():
    memory=ClosureIntentMemory();_,decision,entry=selection(memory)
    memory.reset('exception');memory.enter(identity(),packet(),guided=True)
    entry.occurrence_id=None
    with pytest.raises(ValueError,match='occurrence missing'):memory.select(decision,entry,entry.action[None])


def test_nested_boundary_and_closed_boundary_fail():
    memory=ClosureIntentMemory();memory.enter(identity(),packet(),guided=True)
    with pytest.raises(RuntimeError):memory.enter(identity(),packet(),guided=True)
    assert not memory.boundary_open and memory.previous is None
    with pytest.raises(RuntimeError):memory.finish()


def test_boundary_latch_is_immutable():
    from dataclasses import FrozenInstanceError
    from core.qd_closure_intent import BoundaryLatch
    latch=BoundaryLatch(True)
    with pytest.raises(FrozenInstanceError):latch.eligible=False


@pytest.mark.parametrize('origin,alias,eligible',[
    ('observed_close_dwell','ordinary',True),
    ('ordinary','observed_close_dwell',False),
    ('closure_intent_memory','observed_close_dwell',False)])
def test_transport_resolves_equal_bytes_without_origin_laundering(origin,alias,eligible):
    memory=executed(origin=origin,alias=alias)
    assert memory.previous['origin']==origin and memory.previous['ambiguous'] is False
    assert memory.enter(identity(8),packet(.03),guided=True)==eligible
