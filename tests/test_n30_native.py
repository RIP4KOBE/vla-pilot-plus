"""Independent cross-decision replay against actual policy and recorder schema."""
import copy,json
from collections import Counter
from pathlib import Path
import pytest,torch
from test_n30_executed_progress import (_patch_core_imports,stub_steer,stub_adapter,mock_batch,
    setup_policy,call,cfg,runtime_cfg,packet,eq)


@pytest.fixture(params=[torch.float32,torch.bfloat16])
def native_run(request,stub_steer,stub_adapter,mock_batch,monkeypatch,tmp_path):
    from core.decision_evidence import DecisionEvidence
    from scripts import qd_ed_n30_native as n
    dtype,scenario=request.param if isinstance(request.param,tuple) else (request.param,'continuous')
    provider=setup_policy(stub_steer,stub_adapter,monkeypatch,dtype)
    encode=stub_steer._rdt_model.encode_inputs
    def real_mask(*args):
        cond=encode(*args);mask=torch.zeros((1,1,128),dtype=dtype);mask[:,:,[10,39,40,41,42,43,44]]=1;cond['action_mask']=mask;return cond
    monkeypatch.setattr(stub_steer._rdt_model,'encode_inputs',real_mask)
    provider._guidance_original_func.__code__=provider._guidance_original_func.__code__.replace(co_filename='<string>')
    source=tmp_path/'approach.txt';source.write_text(provider._guidance_source_text);provider._guidance_source_path=str(source)
    class Recorder(DecisionEvidence):
        def flush(self):
            if not hasattr(self,'all_events'):self.all_events=[]
            self.all_events.extend(self._pending);self._pending=[]
    rec=Recorder(tmp_path/'native',episode=0);stub_steer._decision_evidence=rec
    monkeypatch.setattr(stub_adapter,'_decision_evidence',rec,raising=False)
    metrics=[]
    chunks=[(0,1.,.5,True),(8,.5,.25,True)] if scenario=='continuous' else [(0,1.,.5,True),(8,.5,.4,False),(16,.4,.2,True)]
    for step,start,end,guided in chunks:
        p=packet(start)
        if not guided:p.update(keypoints=None,tracker=None)
        rec.begin_decision(global_step=step,stage=1,use_guidance=guided,keypoints=p['keypoints'],providers=[provider] if guided else [],keypoint_tracking_snapshot=p['tracker'])
        rec.record('n30_observation_context',packet=p)
        actions=call(stub_steer,mock_batch,provider,runtime_cfg(cfg()),step=step,context=p,guided=guided)
        if guided:metrics.append(copy.deepcopy(stub_steer.get_last_eds_metrics()))
        stub_steer.commit_executed_progress(actions,8,step);rec.commit_decision(action_chunk=actions,execution_horizon=8)
        for i in range(8):
            rec.dispatch(global_step=step+i,execution_index=i+1)
            rec.record('executed_action',action_numpy=actions[0,i].float())
            endpoint=torch.tensor([start+(end-start)*(i+1)/8,0.,0.],dtype=torch.float64)
            rec.pre_reset_outcome({'robot0_eef_pos':endpoint},reward=0.,terminated=False,success=False)
            if stub_steer.executed_progress_pending():stub_steer.acknowledge_executed_progress(global_step=step+i,execution_index=i+1,action=actions[0,i],endpoint=endpoint,terminated=False,truncated=False)
            rec.step_returned(terminated=False,truncated=False,success=False)
    rec.flush();assert not rec.failed
    events=rec.all_events;compute=stub_steer.get_episode_compute_counters();compute['policy_counters_available']=True
    n.compute_check(compute,2)
    return metrics,events,compute


def test_native_full_replay(native_run):
    from scripts import qd_ed_n30_native as n
    m,e,c=native_run;gate=n.audit_events('N30',m,e,c)
    assert gate['active_insertions_verified']==1 and gate['completed_prefixes_verified']==2
    assert gate['actual_acknowledgments_verified']==16 and gate['parent_rounds_verified']==20
    report={'accepted':True,'evidence_complete':True,'observed_counts':dict(Counter(x['event'] for x in e)),n.GATE:gate}
    assert n.counts('N30',m,report,2)[0]['guided_decisions']==2


@pytest.mark.parametrize('fault',['markers','endpoint','observed_start','target_snapshot','row','tail','other_row','old_winner','decode_zero','ack_order','guidance_gap','tracker','scalar','control'])
def test_deliberate_native_corruption(native_run,fault):
    from scripts import qd_ed_n30_native as n
    m,e,c=copy.deepcopy(native_run)
    def of(kind):return [x for x in e if x['event']==kind]
    if fault=='markers':e=[x for x in e if not x['event'].startswith('n30_')]
    elif fault=='endpoint':of('n30_actual_ack')[7]['values']['endpoint'][0]+=.1
    elif fault=='observed_start':of('n30_observation_context')[1]['values']['packet']['start_eef'][0]+=.1
    elif fault=='target_snapshot':of('n30_initial_proposal')[1]['values']['current_context']['target'][0]+=.01
    elif fault in {'row','other_row'}:of('canonical_candidate_batch')[11]['values']['candidates'][15 if fault=='row' else 0,0,39]+=.2
    elif fault=='tail':of('n30_initial_proposal')[1]['values']['fresh_tail'][0,39]+=.2
    elif fault=='old_winner':of('n30_initial_proposal')[1]['values']['previous_native_plan'][0,8,39]+=.2
    elif fault=='decode_zero':of('policy_action_decode')[0]['values']['action_chunk'][0,0,-1]=0
    elif fault=='ack_order':of('n30_actual_ack')[0]['values']['execution_index']=0
    elif fault=='guidance_gap':of('decision_context')[1]['values']['use_guidance']=False
    elif fault=='tracker':of('n30_initial_proposal')[1]['values']['current_context']['identity']['tracker_generation']+=1
    elif fault=='scalar':m[1]['executed_progress_continuation']['active']=False
    elif fault=='control':of('n30_initial_proposal')[1]['values']['control']='qd_off_v1'
    with pytest.raises((ValueError,KeyError)):n.audit_events('N30',m,e,c)


@pytest.mark.parametrize('arm',['C0','Q0','N30'])
def test_zero_guided_metrics_missing_and_profile_gate(tmp_path,arm):
    from scripts import qd_ed_n30_native as n
    compute={'policy_counters_available':True,'guided_chunks':0,'unguided_chunks':1,'model_forward_calls':5,'model_batch_rows':5,
        'rbf_gradient_calls':0,'rbf_gradient_batch_rows':0,'reward_scoring_batches':0,'reward_evaluations':0}
    p=tmp_path/'eds_eval';p.mkdir();(p/'episode_compute.jsonl').write_text(json.dumps(compute)+'\n')
    report={'accepted':True,'evidence_complete':True,'observed_counts':{}}
    # all arms require an explicit same-worker N30-family gate, even with zero guided work.
    with pytest.raises(ValueError):n.from_output(arm,tmp_path,report,0)
    report[n.GATE]=n.audit_events(arm,[],[],compute)
    assert n.from_output(arm,tmp_path,report,0)[0]['guided_decisions']==0
    report['observed_counts']['canonical_candidate_batch']=11
    with pytest.raises(ValueError):n.from_output(arm,tmp_path,report,0)


def test_legacy_serializer_control_omission():
    from core.eds_eval_metrics import EDSChunkMetrics
    from scripts import qd_ed_n30_native as n
    # Real serializer omits provider-mode/new inactive fields; consume its actual shape.
    metric=EDSChunkMetrics()
    for k,v in {'score_call_count':11,'search_evaluation_count':176,'resample_count':10,'renoise_count':10,'rollout_count':10,
        'qd_archive_active_for_chunk':True}.items():setattr(metric,k,v)
    m=metric.to_jsonable();assert 'qd_quality_mode' not in m and 'executed_progress_continuation' not in m
    gate={'schema':'n30-independent-copy-feedback-v1','profile':'Q0','guided_decisions':1,'canonical_batches_verified':11,'canonical_candidates_verified':176}
    assert n.counts('Q0',[m],{'accepted':True,'evidence_complete':True,'observed_counts':{'canonical_candidate_batch':11},n.GATE:gate},1)[0]['guided_decisions']==1


def test_cpu_future_qd_off_control_uses_real_no_archive_path(stub_steer,stub_adapter,mock_batch,monkeypatch):
    from test_n30_executed_progress import FakeRecorder
    provider=setup_policy(stub_steer,stub_adapter,monkeypatch)
    rec=FakeRecorder();stub_steer._decision_evidence=rec
    import core.rdt_policy_steer as module
    monkeypatch.setattr(module,'allocate_parent_slots',lambda *a,**k:(_ for _ in ()).throw(AssertionError('QD parent allocation called')))
    conf=runtime_cfg({**cfg(),'executed_progress_continuation_control':'qd_off_v1',
        'qd_archive_mode':'none','qd_parent_sampling':'uniform_cells'})
    first=call(stub_steer,mock_batch,provider,conf,context=packet());stub_steer.commit_executed_progress(first,8,0)
    for i in range(8):stub_steer.acknowledge_executed_progress(global_step=i,execution_index=i+1,action=first[0,i],endpoint=torch.tensor([.5,0.,0.],dtype=torch.float64),terminated=False,truncated=False)
    call(stub_steer,mock_batch,provider,conf,step=8,context=packet(.5))
    m=stub_steer.get_last_eds_metrics();compute=stub_steer.get_episode_compute_counters()
    assert m['executed_progress_continuation']['active'] and m['executed_progress_continuation']['control']=='qd_off_v1'
    assert m['qd_archive_active_for_chunk'] is False
    parents=[e for e in rec.events if e['event']=='parent_allocation']
    assert len(parents)==20 and all(e['parent_cell_ids'] is None for e in parents)
    assert all(not any(source.startswith('qd_archive') for source in e['offspring_sources']) for e in parents)
    assert compute['reward_scoring_batches']==32 and compute['reward_evaluations']==512
    assert compute['model_forward_calls']==42 and compute['model_batch_rows']==672 and compute['rbf_gradient_calls']==38
    for bad in ({**cfg(),'qd_archive_mode':'none'}, {**cfg(),'executed_progress_continuation_control':'qd_off_v1'},
                {**cfg(),'executed_progress_continuation_mode':'off','executed_progress_continuation_control':'qd_off_v1'}):
        with pytest.raises(ValueError):stub_steer._resolve_eds_config_with_reference_defaults(bad)


@pytest.mark.parametrize('fault',['mask','provider_structure'])
def test_mask_and_independent_provider_source_tamper(native_run,fault):
    from scripts import qd_ed_n30_native as n
    m,e,c=copy.deepcopy(native_run)
    proposal=[x for x in e if x['event']=='n30_initial_proposal'][1]['values']
    if fault=='mask':proposal['action_mask'][0,0,11]=1
    else:proposal['current_context']['identity']['provider']['code_structure_sha256']='a'*64
    with pytest.raises(ValueError):n.audit_events('N30',m,e,c)


@pytest.mark.parametrize('native_run',[(torch.float32,'gap')],indirect=True)
def test_real_recorder_unguided_none_context_clears_history(native_run):
    from scripts import qd_ed_n30_native as n
    m,e,c=native_run
    assert c['guided_chunks']==2 and c['unguided_chunks']==1
    gate=n.audit_events('N30',m,e,c)
    assert gate['observation_contexts_verified']==3 and gate['completed_prefixes_verified']==2
    assert gate['active_insertions_verified']==0 and gate['inactive_decisions_verified']==2
