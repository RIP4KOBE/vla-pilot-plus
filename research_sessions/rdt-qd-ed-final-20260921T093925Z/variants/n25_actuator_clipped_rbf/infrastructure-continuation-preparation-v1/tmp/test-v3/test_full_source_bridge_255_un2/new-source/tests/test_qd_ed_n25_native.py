import copy,json
from pathlib import Path
import numpy as np
import pytest
import torch
from test_rdt_steer import _patch_core_imports,stub_steer,stub_adapter,_rollout_cond,_n2_fixture_provider
from test_n25_clipped_rbf import native_adapter,config,input_tensor

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_full_native_loop_independent_witness_and_serializer(stub_steer,stub_adapter,monkeypatch,tmp_path,dtype):
    from core.decision_evidence import DecisionEvidence
    from core.rdt_libero_action_converter import decode_rdt_libero_action_chunk
    from scripts.audit_decision_evidence import audit_episode,load_events
    from scripts.qd_ed_audit_backend import create_backend
    from scripts import qd_ed_n25_native as n
    from test_qd_actuator_clipped_quality import static_adapter_fixture
    for k,v in vars(static_adapter_fixture()).items():monkeypatch.setattr(stub_adapter,k,v,raising=False)
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    provider=_n2_fixture_provider(index=0);src=tmp_path/'provider.py';src.write_text(provider._guidance_source_text);provider._guidance_source_path=str(src)
    points=torch.tensor([[.1124,-.071,.3154],[.13,-.21,.39]],dtype=dtype)
    rec=DecisionEvidence(tmp_path/'eds_eval',episode=0);stub_steer._decision_evidence=rec
    monkeypatch.setattr(stub_adapter,'_decision_evidence',rec,raising=False)
    rec.begin_decision(global_step=0,stage=1,use_guidance=True,keypoints=points,providers=[provider]);torch.manual_seed(2525)
    selected=stub_steer._eds_guided_denoise_loop(x_t=input_tensor(dtype,16),cond=_rollout_cond(stub_steer),keypoints=points,
       guidance_fns=[provider],eds_config=config(stub_steer),verbose=False,global_step=0,current_stage=1)
    metrics=stub_steer.get_last_eds_metrics();metrics['global_step']=0
    actions=decode_rdt_libero_action_chunk(selected.float(),8)
    rec.record('policy_action_decode',selected_latent=selected.float(),action_chunk=actions);rec.commit_decision(action_chunk=actions,execution_horizon=8)
    for i in range(8):
        rec.dispatch(global_step=i,execution_index=i+1);rec.record('executed_action',action_numpy=actions[0,i].numpy())
        rec.pre_reset_outcome({'robot0_eef_pos':np.zeros(3)},reward=0.,terminated=i==7,success=False)
        rec.step_returned(terminated=i==7,truncated=False,success=False)
    rec.finish()
    compute={**stub_steer.get_episode_compute_counters(),'episode_id':0,'outcome':'completed','guided_chunks':1,'unguided_chunks':0,'decision_evidence':rec.status()}
    cp=tmp_path/'compute.jsonl';cp.write_text(json.dumps(compute)+'\n')
    report=audit_episode(rec.root,cp,arithmetic_backend=create_backend('cpu'));assert report['accepted'],report['errors']
    events=load_events(rec.root,rec.status());backend=create_backend('cpu')
    gate=n.audit_events('N25',[metrics],events,compute,backend);assert gate['witness_calls_verified']==11
    report[n.GATE]=gate
    counts,_=n.counts('N25',[metrics],report,1);assert counts['guided_decisions']==1
    assert counts['parent_rounds_verified']==10 and counts['witness_calls_verified']==11
    witnesses=[e for e in events if e['event']=='n25_rbf_witness']
    for fault in ('all_markers','missing','extra','other_reset','origin','operand','output','call','cap','mode','cost'):
        es=copy.deepcopy(events);ms=copy.deepcopy([metrics]);cs=copy.deepcopy(compute)
        wi=[e for e in es if e['event']=='n25_rbf_witness']
        if fault=='all_markers':es=[e for e in es if not e['event'].startswith('n25_')]
        elif fault=='missing':es.remove(wi[0])
        elif fault=='extra':es.append(copy.deepcopy(wi[0]))
        elif fault=='other_reset':wi[0]['reset_sequence']+=1
        elif fault=='origin':wi[0]['values']['tensors']['source_origins'][0,0]+=1
        elif fault in ('operand','output'):wi[0]['values']['tensors']['update_operand' if fault=='operand' else 'model_output_after'][0,0,0]+=1
        elif fault=='call':wi[0]['values']['metadata']['call']['denoising_step']+=1
        elif fault=='cap':wi[0]['values']['metadata']['numeric_bytes']=999999
        elif fault=='mode':ms[0].pop('initial_diversity_descriptor_mode')
        elif fault=='cost':cs['rbf_gradient_calls']+=1
        with pytest.raises(ValueError):n.audit_events('N25',ms,es,cs,create_backend('cpu'))
    deleted=copy.deepcopy(report);deleted.pop(n.GATE)
    with pytest.raises(ValueError):n.counts('N25',[metrics],deleted,1)
    with pytest.raises(ValueError):n.audit_events('N23',[metrics],events,compute,create_backend('cpu'))
    assert not torch.cuda.is_initialized()
