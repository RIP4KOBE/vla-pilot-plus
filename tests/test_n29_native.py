import copy,json,math

from pathlib import Path

from types import SimpleNamespace

import pytest,torch

from test_rdt_steer import _patch_core_imports,stub_steer,stub_adapter,_rollout_cond,_n2_fixture_provider

from test_n25_clipped_rbf import native_adapter,input_tensor,config

from test_n26_clean_output_rbf import layout

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('case',['mixed','zero_spread','zero_operand','active_box','duplicate_rows','strict_interior'])
@pytest.mark.parametrize('arrangement',['contiguous','model_slice'])
def test_parent_proof_exact_cases(dtype,case,arrangement):
    from scripts.qd_ed_n29_preflight import check_case
    from scripts.qd_ed_audit_backend import create_backend
    from scripts.qd_ed_n29_reference import CASES
    # Parameter identities must match original fixed native corpus, not silently substitute.
    assert case in CASES
    result=check_case(case,dtype,arrangement,create_backend('cpu'),ROOT)
    assert result['accepted'] and result['boundary_observer_binding_verified'] and result['rng_scope']=='cpu_only'

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_full_native_parent_sequence_boundary_corruption(stub_steer,stub_adapter,monkeypatch,tmp_path,dtype):
    from core.decision_evidence import DecisionEvidence
    from test_qd_actuator_clipped_quality import static_adapter_fixture
    from scripts import qd_ed_n29_native as n
    from scripts.qd_ed_audit_backend import create_backend
    for key,value in vars(static_adapter_fixture()).items():monkeypatch.setattr(stub_adapter,key,value,raising=False)
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    stub_steer._noise_scheduler.config={'prediction_type':'sample'}
    monkeypatch.setattr(stub_steer._rdt_model.dit,'forward',lambda *a:layout(input_tensor(dtype,16),'model_slice'))
    points=torch.tensor([[.1124,-.071,.3154],[.13,-.21,.39]],dtype=dtype)
    provider=_n2_fixture_provider(index=0);rec=DecisionEvidence(tmp_path/'native',episode=0)
    rec.begin_decision(global_step=24,stage=1,use_guidance=True,keypoints=points,providers=[provider]);stub_steer._decision_evidence=rec
    monkeypatch.setattr(stub_adapter,'_decision_evidence',rec,raising=False)
    stub_steer._eds_guided_denoise_loop(x_t=input_tensor(dtype,16),cond=_rollout_cond(stub_steer),keypoints=points,
        guidance_fns=[provider],eds_config=config(stub_steer,'N29'),verbose=False,global_step=24,current_stage=1)
    metrics=stub_steer.get_last_eds_metrics();metrics['global_step']=24;events=rec._pending
    compute=stub_steer.get_episode_compute_counters();compute['guided_chunks']=1
    backend=create_backend('cpu');gate=n.audit_events('N29',[metrics],events,compute,backend)
    assert gate['all_call_summaries_verified']==14 and gate['witness_calls_verified']==11 and gate['parent_boundaries_verified']==10
    assert gate['witness_numeric_bytes']<=220*1024
    for fault in ('all_markers','boundary','allocation','prefix','operand','boundary_order','metrics_phase','radius','beta','scaled_operand','operand_norms'):
        bad=copy.deepcopy(events);m=copy.deepcopy(metrics)
        if fault=='all_markers':bad=[e for e in bad if not e['event'].startswith('n29')]
        elif fault=='boundary':bad=[e for e in bad if e['event']!='n29_parent_renoise_input']
        elif fault=='allocation':next(e for e in bad if e['event']=='n29_rbf_witness' and e['values']['metadata']['call']['phase']=='parent')['values']['metadata']['call']['parent_allocation_sequence']+=1
        elif fault in ('prefix','boundary_order'):
            e=next(e for e in bad if e['event']=='n29_parent_renoise_input')
            if fault=='prefix':e['values']['prefix'][0,0,0]+=.125
            else:e['values']['metadata']['parent_witness_sequence']+=1
        elif fault=='operand':next(e for e in bad if e['event']=='n29_rbf_witness' and e['values']['metadata']['call']['phase']=='parent')['values']['tensors']['update_operand'][0,0,0]+=.125
        elif fault in ('radius','beta','scaled_operand','operand_norms'):
            t=next(e for e in bad if e['event']=='n29_rbf_witness')['values']['tensors'][fault]
            t.reshape(-1)[0]+=.125
        else:m['rollout_direction_rbf_evidence_by_iter'][0][0]['phase']='rollout'
        with pytest.raises(ValueError):n.audit_events('N29',[m],bad,compute,backend)
    with pytest.raises(ValueError):n.audit_events('N28',[metrics],events,compute,backend)

def test_zero_guided_gate_cannot_downgrade():
    from scripts import qd_ed_n29_native as n
    report={'accepted':True,'evidence_complete':True,'observed_counts':{}}
    with pytest.raises(ValueError):n.counts('N29',[],report,0)
    report[n.GATE]=n.audit_events('N29',[],[],{'guided_chunks':0,'rbf_gradient_calls':0,'rbf_gradient_batch_rows':0},None)
    assert n.counts('N29',[],report,0)[0]['guided_decisions']==0
    with pytest.raises(ValueError):n.counts('N28',[],report,0)

@pytest.mark.parametrize('arm',['C0','Q0','N28','N29'])
def test_zero_guided_missing_metrics_actual_output_shape(tmp_path,arm):
    from scripts import qd_ed_n29_native as n
    directory=tmp_path/'eds_eval';directory.mkdir()
    compute={'policy_counters_available':True,'guided_chunks':0,'rbf_gradient_calls':0,'rbf_gradient_batch_rows':0}
    (directory/'episode_compute.jsonl').write_text(json.dumps(compute)+'\n')
    report={'accepted':True,'evidence_complete':True,'observed_counts':{}}
    if arm in {'N28','N29'}:
        report[n.GATE if arm=='N29' else n.control.GATE]=n.audit_events(arm,[],[],compute,None)
    assert n.from_output(arm,tmp_path,report,0)[0]['guided_decisions']==0
    bad=copy.deepcopy(report);bad['observed_counts']={'canonical_candidate_batch':11}
    with pytest.raises(ValueError):n.from_output(arm,tmp_path,bad,0)
    if arm=='N29':
        report.pop(n.GATE)
        with pytest.raises(ValueError):n.from_output(arm,tmp_path,report,0)
