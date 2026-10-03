"""Strict representation decoder and complete Main-loop native evidence regression."""
import copy,types
from pathlib import Path
import numpy as np
import pytest,torch
from core.decision_evidence import _snapshot
from scripts import qd_ed_n30_native as native
from test_n30_initial_observation_repair import make_case,run
from test_n30_executed_progress import _patch_core_imports,stub_adapter,eq
ROOT=Path(__file__).resolve().parents[1]


def original():
    path=ROOT/'docs/experiments/n30/terminal-feedback-repair/original-native-v1.py'
    m=types.ModuleType('original_n30_native');exec(compile(path.read_text(),str(path),'exec'),m.__dict__);return m

@pytest.mark.parametrize('value',[False,True])
def test_native_numpy_snapshot_exact_boolean_meaning(value):
    frozen=_snapshot(np.bool_(value))
    assert type(frozen) is torch.Tensor and frozen.dtype==torch.bool and frozen.shape==() and frozen.device.type=='cpu'
    assert frozen is not value and native.terminal_bool(frozen) is value and native.terminal_bool(value) is value

@pytest.mark.parametrize('kind',['int0','int1','float0','nan','string','none','numpy_raw','int_tensor','float_tensor','vector','matrix','empty','meta'])
def test_decoder_rejects_wrong_type_shape_value_or_device(kind):
    v={'int0':0,'int1':1,'float0':0.,'nan':float('nan'),'string':'false','none':None,'numpy_raw':np.bool_(False),
       'int_tensor':torch.tensor(0),'float_tensor':torch.tensor(0.),'vector':torch.tensor([False]),'matrix':torch.tensor([[True,False]]),
       'empty':torch.empty(0,dtype=torch.bool),'meta':torch.empty((),dtype=torch.bool,device='meta')}[kind]
    with pytest.raises(ValueError,match='terminal boolean'):native.terminal_bool(v)


def numpy_returns(case):
    adapter=case[0].adapter;step=adapter.step
    def wrapped(action):
        obs,reward,terminated,truncated,info=step(action)
        return obs,reward,np.bool_(terminated),np.bool_(truncated),info
    adapter.step=wrapped;return case

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('truncate',[False,True])
def test_complete_main_two_prefixes_numpy_flags_and_unchanged_compute(stub_adapter,monkeypatch,tmp_path,dtype,truncate):
    outputs=[]
    for numpy in (False,True):
        folder=tmp_path/str(numpy);folder.mkdir();case=make_case(stub_adapter,monkeypatch,folder,dtype=dtype,truncate=truncate)
        out=run(numpy_returns(case) if numpy else case);outputs.append(out)
        compute={**out['compute'],'policy_counters_available':True};native.compute_check(compute,3)
        if numpy:
            with pytest.raises(ValueError,match='terminal feedback binding'):original().audit_events('N30',out['metrics'],out['events'],compute)
        else:assert original().audit_events('N30',out['metrics'],out['events'],compute)==native.audit_events('N30',out['metrics'],out['events'],compute)
        gate=native.audit_events('N30',out['metrics'],out['events'],compute)
        assert gate['completed_prefixes_verified']==2 and gate['active_insertions_verified']==2 and gate['actual_acknowledgments_verified']==17
        assert case[1]._executed_progress.pending is None and case[1]._executed_progress.completed is None and case[1]._executed_progress.reason=='terminal_or_truncated'
        packets=[e['values']['packet'] for e in out['events'] if e['event']=='n30_observation_context']
        assert all(p['start_eef'].dtype==torch.float64 for p in packets) and out['cache_reads']==1 and out['steps']==17 and out['reset_queries']==0
    a,b=outputs
    assert a['compute']==b['compute'] and torch.equal(a['rng'],b['rng']) and all(eq(x,y) for x,y in zip(a['actions'],b['actions']))
    # Mutations are only synthetic in-memory evidence. Each channel remains bound.
    for event,field in [('n30_actual_ack','terminated'),('n30_actual_ack','truncated'),('pre_reset_outcome','terminated'),('step_returned','terminated'),('step_returned','truncated')]:
        events=copy.deepcopy(b['events']);target=next(e for e in events if e['event']==event);target['values'][field]=True
        with pytest.raises(ValueError,match='terminal feedback binding'):native.audit_events('N30',b['metrics'],events,{**b['compute'],'policy_counters_available':True})
    # Reject a malformed representation in the real audit, not just helper tests.
    for field in ('terminated','truncated'):
        events=copy.deepcopy(b['events']);next(e for e in events if e['event']=='n30_actual_ack')['values'][field]=torch.tensor([False])
        with pytest.raises(ValueError,match='terminal boolean'):native.audit_events('N30',b['metrics'],events,{**b['compute'],'policy_counters_available':True})

@pytest.mark.parametrize('mode',['C0','Q0'])
def test_control_full_main_python_numpy_parity(stub_adapter,monkeypatch,tmp_path,mode):
    outputs=[]
    for numpy in (False,True):
        folder=tmp_path/str(numpy);folder.mkdir();case=make_case(stub_adapter,monkeypatch,folder,mode=mode,steps=16)
        out=run(numpy_returns(case) if numpy else case);outputs.append(out)
        compute={**out['compute'],'policy_counters_available':True}
        assert original().audit_events(mode,out['metrics'],out['events'],compute)==native.audit_events(mode,out['metrics'],out['events'],compute)
        assert not any(e['event'].startswith('n30_') for e in out['events'])
    a,b=outputs;assert a['compute']==b['compute'] and torch.equal(a['rng'],b['rng']) and all(eq(x,y) for x,y in zip(a['actions'],b['actions']))
    assert a['cache_reads']==b['cache_reads']==0
