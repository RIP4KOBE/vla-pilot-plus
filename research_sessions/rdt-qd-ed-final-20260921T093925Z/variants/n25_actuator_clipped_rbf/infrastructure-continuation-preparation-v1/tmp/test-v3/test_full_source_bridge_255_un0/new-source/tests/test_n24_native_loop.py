"""Full production CPU loops with synthetic model/controller/collector only."""
import ast
import copy
import json
from collections import defaultdict
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np
import pytest
import torch

from test_rdt_steer import (_patch_core_imports, stub_steer, stub_adapter,
                            _rollout_cond, _n2_fixture_provider)


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('scenario',['rescue','empty','present'])
def test_full_n24_cpu_loop_and_source_audit(stub_steer,stub_adapter,monkeypatch,tmp_path,dtype,scenario):
    from core.decision_evidence import DecisionEvidence
    from core.rdt_libero_action_converter import decode_rdt_libero_action_chunk
    from core.qd_ed import fingerprint_action
    from scripts.audit_decision_evidence import audit_episode, fingerprints, require, AuditFailure
    from scripts.audit_gripper_parent_rescue import audit_rescue
    from scripts.qd_ed_audit_backend import create_backend
    from test_qd_actuator_clipped_quality import static_adapter_fixture
    root=Path(__file__).resolve().parents[1]
    for name,value in vars(static_adapter_fixture()).items():
        monkeypatch.setattr(stub_adapter,name,value,raising=False)
    monkeypatch.setattr(stub_adapter,'get_ee_pose_world',lambda:SimpleNamespace(position=np.array([.12317,-.17312,.23141])),raising=False)
    tree=ast.parse((root/'core/env_adapters/libero_adapter.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LiberoAdapter')
    node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='delta_actions_to_ee_trajectory')
    scope={'np':np,'torch':torch}
    import __future__
    exec(compile(ast.Module(body=[node],type_ignores=[]),'libero_adapter.py','exec',flags=__future__.annotations.compiler_flag),scope)
    monkeypatch.setattr(stub_adapter,'delta_actions_to_ee_trajectory',MethodType(scope['delta_actions_to_ee_trajectory'],stub_adapter))
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    provider=_n2_fixture_provider(index=0)
    provider_path=tmp_path/'stage1_guidance.py';provider_path.write_text(provider._guidance_source_text)
    provider._guidance_source_path=str(provider_path)
    points=torch.tensor([[.1124,-.071,.3154],[.13,-.21,.39]],dtype=dtype)
    initial=torch.zeros(16,64,128,dtype=dtype);initial[:,:,39:42]=1.2
    initial[:,:,10]=-100 if scenario=='empty' else 100 if scenario=='present' else -1
    if scenario=='rescue':
        # Same geometry/native score/cell, losing fingerprint: guaranteed initial
        # archive lacks the sole full-close proposal. This is a synthetic input,
        # never a change to the real allocator or refinement algorithm.
        negative=fingerprint_action(initial[1])
        for value in range(1,1000):
            initial[0,:8,10]=value/10
            if fingerprint_action(initial[0])>negative:break
        assert fingerprint_action(initial[0])>negative
    monkeypatch.setattr(stub_steer,'_eds_initial_population',lambda **kw:initial.clone())
    allruns=[]
    for mode,instrumented in [('N23',True),('N24',True),('N24',False)]:
        stub_steer.reset()
        rec=DecisionEvidence(tmp_path/f'{mode}-{instrumented}',episode=0) if instrumented else None
        stub_steer._decision_evidence=rec
        monkeypatch.setattr(stub_adapter,'_decision_evidence',rec,raising=False)
        if rec:rec.begin_decision(global_step=0,stage=1,use_guidance=True,keypoints=points,providers=[provider])
        cfg=json.loads((root/f'configs/qd_ed_final/candidate_{mode.lower()}.json').read_text())['profile']
        cfg=stub_steer._resolve_eds_config_with_reference_defaults(cfg)
        torch.manual_seed(25191)
        selected=stub_steer._eds_guided_denoise_loop(x_t=torch.zeros_like(initial),cond=_rollout_cond(stub_steer),
            keypoints=points,guidance_fns=[provider],eds_config=cfg,verbose=False,global_step=0,current_stage=1)
        metrics=stub_steer.get_last_eds_metrics();rng=torch.random.get_rng_state().clone()
        assert metrics['search_evaluation_count']==176 and metrics['score_call_count']==11
        result={'selected':selected.clone(),'rng':rng,'metrics':metrics,'compute':stub_steer.get_episode_compute_counters()}
        if rec:
            actions=decode_rdt_libero_action_chunk(selected.float(),8)
            rec.record('policy_action_decode',selected_latent=selected.float(),action_chunk=actions)
            rec.commit_decision(action_chunk=actions,execution_horizon=8)
            for i in range(8):
                rec.dispatch(global_step=i,execution_index=i+1)
                rec.record('executed_action',action_numpy=actions[0,i].numpy())
                rec.pre_reset_outcome({'robot0_eef_pos':np.zeros(3)},reward=0.,terminated=i==7,success=False)
                rec.step_returned(terminated=i==7,truncated=False,success=False)
            rec.finish()
            compute=tmp_path/f'{mode}-{instrumented}'/'episode_compute.jsonl'
            compute.write_text(json.dumps({'episode_id':0,'outcome':'completed','decision_evidence':rec.status()})+'\n')
            report=audit_episode(rec.root,compute,arithmetic_backend=create_backend('cpu'))
            (compute.parent/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
            assert report['accepted'],report['errors']
            events=[e for p in sorted(rec.root.glob('bundle_*.pt')) for e in torch.load(p,map_location='cpu',weights_only=True)['events']]
            result['parents']=[e['values']['source_fingerprints'] for e in events if e['event']=='parent_allocation']
            if mode=='N24':
                gate=report['n24_gripper_parent_rescue_audit']
                assert gate['canonical_candidates_verified']==176 and gate['parent_rounds_verified']==10
                assert gate['substitutions']==metrics['qd_gripper_rescue_substitutions']
                assert (gate['substitutions']>0) if scenario=='rescue' else gate['substitutions']==0
                kinds=defaultdict(list)
                for e in events:kinds[e['event']].append(e)
                context=kinds['decision_context'][0]
                # Corrupt actual source evidence after a successful real-loop audit.
                for fault in ('fingerprint','slot','predicate','cost','context','raw','descriptor','cell','missing','duplicate','future','final_archive','all_markers'):
                    changed=copy.deepcopy(kinds)
                    ov=changed['gripper_rescue_parents'][0]['values']
                    if fault=='fingerprint':ov['actual_actions'][0,0,39]+=1
                    elif fault=='slot':ov['replacement_slot']=15 if ov['replacement_slot']!=15 else 14
                    elif fault=='predicate':ov['original_full_close_mask'][0]=~ov['original_full_close_mask'][0]
                    elif fault=='cost':ov['actual_costs'][0]+=1
                    elif fault=='context':ov['context']['stage']=99
                    elif fault=='raw':ov['actual_raw'][0]+=1
                    elif fault=='descriptor':ov['actual_descriptors'][0,0]+=1
                    elif fault=='cell':ov['actual_cells'][0]=(int(ov['actual_cells'][0])+1)%16
                    elif fault=='missing':changed['gripper_rescue_cache'].pop()
                    elif fault=='duplicate':changed['gripper_rescue_parents'].append(changed['gripper_rescue_parents'][0])
                    elif fault=='future':changed['gripper_rescue_cache'][0]['sequence']=changed['parent_allocation'][0]['sequence']+1
                    elif fault=='final_archive':changed['final_selection'][0]['values']['archive_reference']['population'][0,0,10]+=1
                    elif fault=='all_markers':
                        for kind in ('gripper_rescue_begin','gripper_rescue_cache','gripper_rescue_parents'):changed[kind]=[]
                        for row in changed['parent_allocation']+changed['final_selection']:row['values'].pop('gripper_rescue_mode',None)
                    with pytest.raises(AuditFailure):audit_rescue(changed,context,require,fingerprints)
        allruns.append(result)
    assert torch.equal(allruns[1]['selected'],allruns[2]['selected'])
    assert torch.equal(allruns[1]['rng'],allruns[2]['rng'])
    assert allruns[0]['compute']==allruns[1]['compute']==allruns[2]['compute']
    assert torch.equal(allruns[0]['rng'],allruns[1]['rng'])
    if scenario!='rescue':
        assert torch.equal(allruns[0]['selected'],allruns[1]['selected'])
        assert allruns[0]['parents']==allruns[1]['parents']
    assert not any(k.startswith('qd_gripper_rescue_') for k in allruns[0]['metrics'])
    assert not torch.cuda.is_initialized()
    (tmp_path/'summary.json').write_text(json.dumps({'dtype':str(dtype),'scenario':scenario,
        'score':'Unknown/not-run','compute':allruns[1]['compute'],
        'substitutions':allruns[1]['metrics']['qd_gripper_rescue_substitutions'],
        'canonical_evaluations':176,'score_batches':11,'instrumentation_parity':True,
        'inactive_parent_action_parity':scenario!='rescue','rng_parity':True},indent=2)+'\n')


@pytest.mark.parametrize('change',[{'qd_gripper_rescue_mode':'other'},{'qd_quality_mode':'provider'},
    {'qd_parent_survivor_count':4},{'qd_bounds_update_policy':'causal_envelope_v1'},
    {'qd_sparse_exponent':2.},{'chunk_population_mode':'warm_start_mix'}])
def test_config_closed(stub_steer,change):
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'configs/qd_ed_final/candidate_n24.json').read_text())['profile']
    config.update(change)
    with pytest.raises(ValueError):stub_steer._resolve_eds_config_with_reference_defaults(config)
