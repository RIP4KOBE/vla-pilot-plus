"""Independent synthetic-only checks; never call run/admit or open real evidence."""
import copy
import importlib.util
import os
from pathlib import Path

import pytest

assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
import torch
assert not torch.cuda.is_initialized()

READER=Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-executed-quality-20260923/docs/03_evidence/qd_ed_final/continuation_20260923/selected-tracking-preparation/read_selected_tracking.py')
spec=importlib.util.spec_from_file_location('selected_tracking_independent_subject',READER)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


def fixture(start=0,m=8,endpoint=(0.,0.,0.),ended=False):
    chosen=torch.zeros((1,64,128),dtype=torch.bfloat16);chosen[:,:8,39]=1
    decoded=chosen[:,:8,[39,40,41,42,43,44,10]].float();decoded[:,:,-1]=1
    origin=torch.tensor([.5001,.25,.75],dtype=torch.float64);cast=origin.bfloat16()
    x=torch.stack([cast+torch.tensor([i/16,0,0],dtype=torch.bfloat16) for i in range(9)])
    fp=s.fingerprint(chosen[0]);rows=[];did=f'e0:d{start//8+1}:s{start}'
    def add(kind,values,step=start,reset=0):
        rows.append({'sequence':len(rows)+1,'event':kind,'episode':0,'decision_id':did,
            'global_step':step,'reset_sequence':reset,'values':values})
    add('decision_context',{'stage':1,'use_guidance':True,'providers':[{'ordinal':0,
        'original_code_sha256':'a'*64,'source_text_sha256':'b'*64,'source_path':'frozen-fixture-guidance.py'}]})
    add('projection_origin',{'source_eef_position':origin,'cast_eef_start':cast})
    add('scoring_inputs',{'samples':chosen.clone(),'projected_xyz':x[None],
        'projection_origin_sequences':[2],'scoring_scope':{'role':'canonical_initial'}})
    add('final_selection',{'selected_latent':chosen,'selected_canonical_fingerprint':fp})
    add('policy_action_decode',{'selected_latent':chosen.float(),'selected_canonical_fingerprint':fp,'action_chunk':decoded})
    add('decision_committed',{'action_chunk':decoded.clone(),'execution_horizon':8})
    for i in range(1,m+1):
        step=start+i-1;terminal=ended and i==m
        add('action_dispatch',{'execution_index':i},step)
        add('executed_action',{'action_numpy':decoded[0,i-1].clone()},step)
        p=origin+(x[i].double()-x[0].double())+torch.tensor(endpoint,dtype=torch.float64)*(i/8)
        add('pre_reset_outcome',{'observation':{'robot0_eef_pos':p},'terminated':terminal},step)
        if terminal:add('automatic_reset_boundary',{'reset_will_follow':True},step)
        add('step_returned',{'terminated':terminal,'truncated':False},step,reset=int(terminal))
    return rows


def test_response_uses_x_i_and_keeps_source_cast_error_separate():
    d=s.describe(fixture())
    assert d['tracking_status']=='known_recorded_selected_prefix'
    assert d['summary']['disp_mse']==pytest.approx(0,abs=1e-25)
    assert d['tracking'][0]['e_abs'][0]==pytest.approx(.0001)
    assert d['projected']['origin_cast_delta'][0]==pytest.approx(.0001)
    assert len(d['tracking'])==8 and d['tracking'][0]['i']==1


def test_same_fingerprint_different_native_or_projection_is_not_arbitrarily_joined():
    for changed in ('dtype','projection','origin'):
        rows=fixture();duplicate=copy.deepcopy(rows[2])
        if changed=='dtype':duplicate['values']['samples']=duplicate['values']['samples'].float()
        elif changed=='projection':duplicate['values']['projected_xyz'][0,4,0]+=.125
        else:
            extra_origin=copy.deepcopy(rows[1]);extra_origin['sequence']=100
            extra_origin['values']['source_eef_position'][0]+=.00001
            rows.append(extra_origin);duplicate['values']['projection_origin_sequences']=[100]
        duplicate['sequence']=101;rows.append(duplicate)
        value,reason=s.selected(rows)
        assert value is None and 'ambiguous' in reason


def test_terminal_reset_increment_preserves_response_but_prevents_pair():
    previous=s.describe(fixture(m=3,ended=True))
    assert previous['m']==3 and previous['ended'] and len(previous['tracking'])==3
    assert s.temporal_pair(previous,s.describe(fixture(start=3)))['reason']=='reset_or_terminal_boundary'


def test_fixed_transport_uses_only_previous_endpoint_and_denominator_eight():
    previous=s.describe(fixture(endpoint=(.8,0,0)))
    current=s.describe(fixture(start=8,m=3,endpoint=(0,.4,0)),previous)
    pair=s.temporal_pair(previous,current)
    assert pair['status']=='retrospective_predictive_check'
    assert pair['previous_e_disp_8']==pytest.approx([.8,0,0])
    assert pair['points'][0]['transported_error']==pytest.approx([-.1,.05,0])
    assert pair['points'][-1]['transported_error']==pytest.approx([-.3,.15,0])
    assert pair['current_m']==3
    unknown=copy.deepcopy(previous);unknown['provider_identity_known']=False
    assert s.temporal_pair(unknown,current)['reason']=='provider_identity_unknown'
    off=copy.deepcopy(previous);off['use_guidance']=False
    assert s.temporal_pair(off,current)['reason']=='unguided_boundary'


def test_real_sent_difference_is_retained_without_rewriting_decoded_values():
    rows=fixture();sent=next(x for x in rows if x['event']=='executed_action')
    sent['values']['action_numpy'][0]+=0.25
    d=s.describe(rows)
    assert d['actual_prefix'][0]['sent_decode_delta'][0]==.25
    assert d['summary']['sent_decode_changed_steps']==1
    assert d['summary']['sent_outside_declared_unit_bounds_components']==1
    assert not torch.cuda.is_initialized()
