"""Real policy/recorder chains with synthetic model/observations, independent audit."""
import copy,io,json
from collections import Counter
from pathlib import Path
import pytest,torch,numpy as np
from test_n31_capture_dwell_integration import make,packet,runtime_cfg,_patch_core_imports,stub_adapter,mock_batch


def episode(tmp_path,monkeypatch,adapter,batch,arm='N31',dtype=torch.float32,providers_mode='normal',disk=False):
    from core.decision_evidence import DecisionEvidence
    from scripts import audit_decision_evidence as generic
    p,provider,conf,_,_,_=make('on' if arm=='N31' else 'off',adapter,monkeypatch,dtype)
    if arm=='C0':conf={**conf,'qd_archive_mode':'none','qd_parent_sampling':'uniform_cells'}
    encode=p._rdt_model.encode_inputs
    def masked(*args):
        c=encode(*args);m=torch.zeros((1,1,128),dtype=dtype);m[:,:,[10,39,40,41,42,43,44]]=1;c['action_mask']=m;return c
    monkeypatch.setattr(p._rdt_model,'encode_inputs',masked)
    provider._guidance_original_func.__code__=provider._guidance_original_func.__code__.replace(co_filename='<string>')
    source=tmp_path/'approach.txt';source.write_text(provider._guidance_source_text);provider._guidance_source_path=str(source)
    # Real snapshots and sequence bookkeeping; single small in-memory serialization.
    class Recorder(DecisionEvidence):
        def flush(self):
            if not hasattr(self,'all_events'):self.all_events=[]
            self.all_events.extend(self._pending);self._pending=[]
    recdir=tmp_path/'eds_eval/decision_evidence' if disk else tmp_path
    root=recdir/'episode_000';rec=(DecisionEvidence if disk else Recorder)(recdir,episode=0);p._decision_evidence=rec;monkeypatch.setattr(adapter,'_decision_evidence',rec,raising=False)
    metrics=[]
    modes=['normal','empty','unguided'] if providers_mode=='mixed' else [providers_mode]
    for index,mode in enumerate(modes):
        step=index*8;guided=mode!='unguided';providers=[] if mode in ('empty','unguided') else [provider];ctx=packet(.01)
        if not guided:ctx.update(keypoints=None,tracker=None)
        rec.begin_decision(global_step=step,stage=1,use_guidance=guided,keypoints=ctx['keypoints'],providers=providers,keypoint_tracking_snapshot=ctx['tracker'])
        if arm=='N31':rec.record('n31_observation_context',packet=ctx)
        torch.manual_seed(310+index)
        actions=p.select_action(batch,generate_new_chunk=True,use_guidance=guided,keypoints=None if not guided else ctx['keypoints'].numpy(),guidance_fns=providers,
            guidance_type='eds',eds_config=runtime_cfg(conf),global_step=step,current_stage=1,
            **({'capture_dwell_context':ctx} if arm=='N31' else {}))
        if guided:metrics.append(copy.deepcopy(p.get_last_eds_metrics()))
        rec.commit_decision(action_chunk=actions,execution_horizon=8)
        for j in range(8):
            rec.dispatch(global_step=step+j,execution_index=j+1);rec.record('executed_action',action_numpy=actions[0,j].float())
            rec.pre_reset_outcome({'robot0_eef_pos':ctx['observed_eef'],'robot0_eef_quat':ctx['hand_quaternion_xyzw'],
                'robot0_gripper_qpos':ctx['gripper_qpos']},reward=0.,terminated=False,success=False)
            rec.step_returned(terminated=False,truncated=(index==len(modes)-1 and j==7),success=False)
    status=rec.finish();assert not rec.failed
    if disk:events=generic.load_events(root,status)
    else:
        stream=io.BytesIO();torch.save(rec.all_events,stream);stream.seek(0);events=torch.load(stream,map_location='cpu',weights_only=True)
    compute={**p.get_episode_compute_counters(),'episode_id':0,'policy_counters_available':True,'outcome':'completed','decision_evidence':status}
    cp=(tmp_path/'eds_eval' if disk else tmp_path)/'episode_compute.jsonl';cp.write_text(json.dumps(compute)+'\n')
    if disk:(tmp_path/'eds_eval/eds_metrics.jsonl').write_text(''.join(json.dumps(m)+'\n' for m in metrics))
    def audit(ev=events,flag=True):
        if disk:return generic.audit_episode(root,cp,n31_empty_provider_search=flag)
        with monkeypatch.context() as m:
            m.setattr(generic,'load_events',lambda *_:ev)
            return generic.audit_episode(root,cp,n31_empty_provider_search=flag)
    return metrics,events,compute,audit


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_native_real_recorder_full_chain(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype):
    from scripts import qd_ed_n31_native as n
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype=dtype)
    report=a();assert report['accepted'],report['errors']
    gate=n.audit_events('N31',m,e,c);assert gate['changed_proposals_verified']==10 and gate['other15_commitments_verified']==10
    report[n.GATE]=gate;assert n.counts('N31',m,report,1)[0]['parent_rounds_verified']==10


@pytest.fixture
def native_run(tmp_path,monkeypatch,stub_adapter,mock_batch):return episode(tmp_path,monkeypatch,stub_adapter,mock_batch)


@pytest.mark.parametrize('fault',['mask','target','source_iter','insert','cell','slot','other15','projection','origin','quality','scope','snapshot','duplicate','decode','scalar','parent_native','provider_structure'])
def test_native_tamper(native_run,fault):
    from scripts import qd_ed_n31_native as n
    m,e,c,_=native_run;m,e,c=copy.deepcopy((m,e,c));of=lambda kind:[v['values'] for v in e if v['event']==kind]
    op=of('n31_capture_dwell_opportunity')[0];cache=of('n31_canonical_cache')[0]
    if fault=='mask':cache['action_mask'][0,0,11]=1
    elif fault=='target':of('n31_observation_context')[0]['packet']['keypoints'][0,0]+=.01
    elif fault=='source_iter':op['archive']['source_iter']=9
    elif fault=='insert':of('n31_archive_update')[0]['archive'][0]['insert_sequence']+=1
    elif fault=='cell':of('n31_archive_update')[0]['cell_ids'][0]=99
    elif fault=='slot':op['slot']=14
    elif fault=='other15':op['ordinary_other15']['native_identity']='0'*64
    elif fault=='projection':cache['projected_outcomes'][0,0,0]+=.1
    elif fault=='origin':cache['source_origins'][0][0]+=.1
    elif fault=='quality':of('canonical_candidate_batch')[0]['effective_quality'][0]+=.1
    elif fault=='scope':cache['role']='auxiliary_pretest'
    elif fault=='snapshot':op['observation']['gripper_qpos'][0]+=.1
    elif fault=='duplicate':op['matching_occurrences'].append(99)
    elif fault=='decode':of('policy_action_decode')[0]['action_chunk'][0,0,-1]=0
    elif fault=='scalar':m[0]['capture_dwell_proposal']['changed']=0
    elif fault=='parent_native':of('parent_allocation')[0]['source_population'][0,0,39]+=.1
    elif fault=='provider_structure':op['identity']['provider']['code_structure_sha256']='f'*64
    with pytest.raises((ValueError,KeyError,IndexError)):n.audit_events('N31',m,e,c)


@pytest.mark.parametrize('arm',['C0','Q0','N31'])
@pytest.mark.parametrize('mode',['empty','mixed'])
def test_all_arms_real_empty_provider_and_mixed(tmp_path,monkeypatch,stub_adapter,mock_batch,arm,mode):
    from scripts import qd_ed_n31_native as n
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,arm=arm,providers_mode=mode)
    report=a();assert report['accepted'],report['errors'];report[n.GATE]=n.audit_events(arm,m,e,c)
    assert n.counts(arm,m,report,len(m))[0]['guided_decisions']==len(m)
    assert c['reward_scoring_batches']==(0 if mode=='empty' else 16)
    assert not a(flag=False)['accepted']


@pytest.mark.parametrize('fault',['delete_all_effect','delete_one_effect','quality_nonzero','quality_negative_zero','cost_positive_zero','wrong_dtype','wrong_scope','changed_aux_scope','moved_auxiliary','normal_fake_empty'])
def test_empty_score_cannot_be_forged(tmp_path,monkeypatch,stub_adapter,mock_batch,fault):
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,arm='Q0',providers_mode='normal' if fault=='normal_fake_empty' else 'empty')
    e=copy.deepcopy(e);of=lambda kind:[v['values'] for v in e if v['event']==kind]
    if fault=='delete_all_effect':e=[v for v in e if v['event']!='effective_quality']
    elif fault=='delete_one_effect':e.remove(next(v for v in e if v['event']=='effective_quality'))
    elif fault=='quality_nonzero':of('canonical_candidate_batch')[0]['effective_quality'][0]=1
    elif fault=='quality_negative_zero':of('effective_quality')[0]['quality']=-of('effective_quality')[0]['quality']
    elif fault=='cost_positive_zero':of('effective_quality')[0]['costs'].zero_()
    elif fault=='wrong_dtype':of('effective_quality')[0]['costs']=of('effective_quality')[0]['costs'].double()
    elif fault=='wrong_scope':of('effective_quality')[0]['scoring_scope']['iter_idx']=0
    elif fault=='changed_aux_scope':
        next(v for v in of('effective_quality') if v['scoring_scope']['role']=='auxiliary_pretest')['scoring_scope']['site']='rollout_trace'
    elif fault=='moved_auxiliary':
        aux=next(v for v in e if v['event']=='effective_quality' and v['values']['scoring_scope']['role']=='auxiliary_pretest')
        aux['sequence']=next(v['sequence'] for v in e if v['event']=='parent_allocation')+1
    elif fault=='normal_fake_empty':of('decision_context')[0]['providers']=[]
    assert not a(e)['accepted']


@pytest.mark.parametrize('arm',['C0','Q0','N31'])
def test_zero_guided_requires_explicit_native_gate(tmp_path,monkeypatch,stub_adapter,mock_batch,arm):
    from scripts import qd_ed_n31_native as n
    m,e,compute,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,arm=arm,providers_mode='unguided')
    p=tmp_path/'eds_eval';p.mkdir();(p/'episode_compute.jsonl').write_text(json.dumps(compute)+'\n')
    report=a();assert report['accepted'],report['errors']
    with pytest.raises(ValueError):n.from_output(arm,tmp_path,report,0)
    with pytest.raises(ValueError):n.audit_events(arm,[],[],compute)
    report[n.GATE]=n.audit_events(arm,m,e,compute);assert n.from_output(arm,tmp_path,report,0)[0]['guided_decisions']==0
    report['observed_counts']['canonical_candidate_batch']=11
    with pytest.raises(ValueError):n.from_output(arm,tmp_path,report,0)
