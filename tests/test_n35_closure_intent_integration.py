"""Real policy/recorder chains with synthetic model/observations, independent audit."""
import copy,io,json
from collections import Counter
from pathlib import Path
import pytest,torch,numpy as np
from test_n31_capture_dwell_integration import make,packet,runtime_cfg,_patch_core_imports,stub_adapter,mock_batch


def episode(tmp_path,monkeypatch,adapter,batch,arm='N35',dtype=torch.float32,providers_mode='normal',disk=False,nohit=False, fault=None,target=.01,positive_template=False,terminal_kind='truncated',terminal_prefix=8):
    from core.decision_evidence import DecisionEvidence
    from scripts import audit_decision_evidence as generic
    p,provider,conf,_,_,_=make('on' if arm=='N35' else 'off',adapter,monkeypatch,dtype)
    if arm=='N35':
        conf.update(closure_intent_mode='executed_closure_intent_v1',
            n35_runtime_binding={'task_id':0,'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','run_id':'CPU-synthetic-only'}, capture_dwell_proposal_mode='off', observed_jaw_approach_mode='observed_jaw_approach_v1',
            n34_runtime_binding={'task_id':0,'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','run_id':'CPU-synthetic-only'})
    if arm=='off':conf.update(observed_jaw_approach_mode='off', n34_runtime_binding=None)
    if arm=='C0':conf={**conf,'qd_archive_mode':'none','qd_parent_sampling':'uniform_cells'}
    encode=p._rdt_model.encode_inputs
    def masked(*args):
        c=encode(*args);m=torch.zeros((1,1,128),dtype=dtype);m[:,:,[10,39,40,41,42,43,44]]=1;c['action_mask']=m;return c
    monkeypatch.setattr(p._rdt_model,'encode_inputs',masked)
    if positive_template:
        initial=p._eds_initial_population
        def positive(*args,**kwargs):
            result=initial(*args,**kwargs);result[0,:8,10]=.5
            p._last_eds_initial_sampler_trace_stages=[(name,result.detach() if name=='initial_final' else values) for name,values in p._last_eds_initial_sampler_trace_stages]
            return result
        monkeypatch.setattr(p,'_eds_initial_population',positive)
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
    modes=['normal']*3 if providers_mode=='chain' else ['normal','unguided','normal'] if providers_mode=='gap' else [providers_mode]
    for index,mode in enumerate(modes):
        step=index*8;guided=mode!='unguided';providers=[] if mode in ('empty','unguided') else [provider];ctx=packet(target);ctx['task_id']=0;ctx['gripper_qpos']=torch.tensor([.02-index*.001,-.02+index*.001],dtype=torch.float64)
        if nohit:ctx['gripper_qpos']=torch.tensor([.04,.03],dtype=torch.float64)
        if fault == 'entry':ctx['observed_eef'][0]=.01
        if fault == 'nonfinite':ctx['hand_quaternion_xyzw'][0]=float('nan')
        if fault == 'empty':ctx['gripper_qpos']=torch.tensor([-.02,.02],dtype=torch.float64)
        if fault == 'missing':ctx['gripper_qpos']=None
        if not guided:ctx.update(keypoints=None,tracker=None)
        rec.begin_decision(global_step=step,stage=1,use_guidance=guided,keypoints=ctx['keypoints'],providers=providers,keypoint_tracking_snapshot=ctx['tracker'])
        if arm=='N35':rec.record('n35_observation_context',packet=ctx)
        torch.manual_seed(310+index)
        actions=p.select_action(batch,generate_new_chunk=True,use_guidance=guided,keypoints=None if not guided else ctx['keypoints'].numpy(),guidance_fns=providers,
            guidance_type='eds',eds_config=runtime_cfg(conf),global_step=step,current_stage=1,
            **({'capture_dwell_context':ctx} if arm=='N35' else {}))
        if guided:metrics.append(copy.deepcopy(p.get_last_eds_metrics()))
        p._closure_intent.commit(actions,8,step)
        rec.commit_decision(action_chunk=actions,execution_horizon=8)
        final=index==len(modes)-1
        for j in range(terminal_prefix if final else 8):
            ended=final and j==terminal_prefix-1
            terminated=ended and terminal_kind=='terminated'
            truncated=ended and terminal_kind=='truncated'
            rec.dispatch(global_step=step+j,execution_index=j+1);rec.record('executed_action',action_numpy=actions[0,j].float())
            rec.pre_reset_outcome({'robot0_eef_pos':ctx['observed_eef'],'robot0_eef_quat':ctx['hand_quaternion_xyzw'],
                'robot0_gripper_qpos':torch.tensor([.02-(index+1)*.001,-.02+(index+1)*.001],dtype=torch.float64) if j==7 else ctx['gripper_qpos']},reward=0.,terminated=terminated,success=terminated)
            rec.step_returned(terminated=terminated,truncated=truncated,success=terminated)
            p._closure_intent.acknowledge(action=actions[0,j],step=step+j,index=j+1,terminated=terminated,truncated=truncated)
    status=rec.finish();assert not rec.failed
    if disk:events=generic.load_events(root,status)
    else:
        stream=io.BytesIO();torch.save(rec.all_events,stream);stream.seek(0);events=torch.load(stream,map_location='cpu',weights_only=True)
    compute={**p.get_episode_compute_counters(),'episode_id':0,'task_id':0,'policy_counters_available':True,'outcome':'completed','decision_evidence':status}
    cp=(tmp_path/'eds_eval' if disk else tmp_path)/'episode_compute.jsonl';cp.write_text(json.dumps(compute)+'\n')
    if disk:(tmp_path/'eds_eval/eds_metrics.jsonl').write_text(''.join(json.dumps(m)+'\n' for m in metrics))
    def audit(ev=events,flag=True):
        if disk:return generic.audit_episode(root,cp,n31_empty_provider_search=flag)
        with monkeypatch.context() as m:
            m.setattr(generic,'load_events',lambda *_:ev)
            return generic.audit_episode(root,cp,n31_empty_provider_search=flag)
    return metrics,events,compute,audit



def expected(events):
    from core.qd_closure_intent import SOURCE_FILES
    import hashlib
    root=Path(__file__).resolve().parents[1]
    op=next(e['values'] for e in events if e['event']=='n35_capture_dwell_opportunity')
    return {'binding':{'task_id':0,'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','run_id':'CPU-synthetic-only'},
        'config_sha256':op['config_sha256'],'source_hashes':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in SOURCE_FILES}}

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_real_policy_three_boundaries(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype):
    from scripts import qd_ed_n35_native as audit
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype=dtype,target=0.,providers_mode='chain')
    generic=a();assert generic['accepted'],generic['errors']
    result=audit.audit_events('N35',m,e,c,expected_runtime=expected(e))
    assert result['parent_rounds_verified']==30
    assert result['lifecycle']['eligible_boundaries']==1
    assert result['lifecycle']['consumptions']==1
    assert result['lifecycle']['expiries']==3
    assert result['executed_actions_verified']==24
    entries=[x['values'] for x in e if x['event']=='n35_boundary_entry']
    assert entries[1]['eligible'] and not entries[2]['eligible']
    ops=[x['values'] for x in e if x['event']=='n35_capture_dwell_opportunity']
    assert all(x['reason']=='closure_intent_memory' for x in ops[10:20])
    assert all(type(x['decoded_delta_count']) is int for x in ops[10:20])
    assert c['model_forward_calls']==63 and c['rbf_gradient_calls']==57
    print('N35_CPU_LIFECYCLE',result['lifecycle'])


def test_zero_decoded_delta_is_retained_and_audited(tmp_path,monkeypatch,stub_adapter,mock_batch):
    from scripts import qd_ed_n35_native as audit
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,target=0.,providers_mode='chain',positive_template=True)
    generic=a();assert generic['accepted'],generic['errors']
    result=audit.audit_events('N35',m,e,c,expected_runtime=expected(e))
    assert result['lifecycle']['eligible_boundaries']==1
    assert result['zero_decoded_delta_memory_opportunities']==10
    assert any(x['native_delta_count']>0 and x['decoded_delta_count']==0 for x in
        (e['values'] for e in e if e['event']=='n35_capture_dwell_opportunity'))


def test_adversarial_audit_origin_lifecycle_and_decoder(tmp_path,monkeypatch,stub_adapter,mock_batch):
    from scripts import qd_ed_n35_native as audit
    m,original,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,target=0.,providers_mode='chain')
    trust=expected(original)
    for fault in ('missing_entry','missing_ack','missing_commit','missing_expiry','wrong_origin','wrong_occurrence',
                  'archive_alias','native_bytes','decoded_bytes','ack_index','ack_action','ack_sequence',
                  'expire_latch','rearm','source','other15','suffix','fake_reset'):
        events=copy.deepcopy(original)
        def event(kind,index=0):return [e for e in events if e['event']==kind][index]
        if fault.startswith('missing_'):
            kind={'entry':'boundary_entry','ack':'step_acknowledged','commit':'execution_commit','expiry':'boundary_expiry'}[fault[8:]]
            events.remove(event('n35_'+kind))
        elif fault=='wrong_origin':event('n35_selected_occurrence')['values']['origin']='ordinary'
        elif fault=='wrong_occurrence':event('n35_selected_occurrence')['values']['occurrence']=0
        elif fault=='archive_alias':event('n35_archive_update',10)['values']['archive'][0]['occurrence_id']=0
        elif fault=='native_bytes':event('n35_selected_occurrence')['values']['native'][0,0,10]=-1
        elif fault=='decoded_bytes':event('n35_decode_binding')['values']['decoded'][0,0,6]=-1
        elif fault=='ack_index':event('n35_step_acknowledged')['values']['index']=2
        elif fault=='ack_action':event('n35_step_acknowledged')['values']['action'][0]+=1
        elif fault=='ack_sequence':event('n35_step_acknowledged')['sequence']=0
        elif fault=='expire_latch':event('n35_boundary_expiry',1)['values']['eligible']=False
        elif fault=='rearm':event('n35_boundary_entry',2)['values']['eligible']=True
        elif fault=='source':event('n35_capture_dwell_opportunity')['values']['source_hashes']['main.py']='0'*64
        elif fault=='other15':event('n35_capture_dwell_opportunity')['values']['actual_scored_population'][0,0,39]+=1
        elif fault=='suffix':event('n35_capture_dwell_opportunity',10)['values']['candidate'][8,10]+=1
        elif fault=='fake_reset':event('n35_execution_complete')['event']='n35_memory_reset';event('n35_memory_reset')['values']={'reason':'terminal'}
        with pytest.raises((ValueError,KeyError,IndexError),match=None):
            audit.audit_events('N35',m,events,c,expected_runtime=trust)


@pytest.mark.parametrize('observer',[True,False])
@pytest.mark.parametrize('step_fault',[False,True])
def test_main_step_ack_and_raw_observation_hook(tmp_path,monkeypatch,stub_adapter,observer,step_fault):
    from test_n30_initial_observation_repair import make_case,run
    from test_n31_capture_dwell_integration import config,project_adapter
    case=make_case(stub_adapter,monkeypatch,tmp_path,mode='Q0',steps=16)
    app,p,rec,state=case
    app.config['eds_config']=config()
    binding={'task_id':0,'source_commit':'1'*40,'run_id':'main-unit'}
    app.config['eds_config'].update(capture_dwell_proposal_mode='off',observed_jaw_approach_mode='observed_jaw_approach_v1',
        n34_runtime_binding=binding,closure_intent_mode='executed_closure_intent_v1',n35_runtime_binding=binding)
    def enrich(obs):
        obs['observation.robot_state']['eef']['quat']=torch.tensor([[0.,0.,0.,1.]],dtype=torch.float64)
        obs['observation.robot_state']['gripper']={'qpos':torch.tensor([[.02-state['step']*.0001,-.02+state['step']*.0001]],dtype=torch.float64)}
        return obs
    enrich(stub_adapter._last_obs)
    original=stub_adapter.step
    def step(action):
        if step_fault and state['step']==3:
            raise RuntimeError('synthetic actual step failure')
        o,r,t,tr,i=original(action);enrich(o);return o,r,t,tr,i
    stub_adapter.step=step;project_adapter(stub_adapter,monkeypatch)
    if not observer:
        app._enable_decision_evidence=lambda ep:None;p._decision_evidence=None;stub_adapter._decision_evidence=None
        rec.all_events=[];rec.finished=False
    if step_fault:
        with pytest.raises(RuntimeError,match='synthetic actual step failure'):run(case)
        assert p._closure_intent.previous is None and not p._closure_intent.latch
        return
    out=run(case)
    assert out['steps']==16 and out['cache_reads']==1 and out['policy_reads']==17
    assert out['tracker_reads']==out['snapshots']==2
    assert p._closure_intent.previous is None and not p._closure_intent.latch
    assert out['compute']['model_forward_calls']==42 and out['compute']['rbf_gradient_calls']==38
    if observer:
        assert len([e for e in out['events'] if e['event']=='n35_step_acknowledged'])==16
        assert not any(e['event'].startswith('n34_') for e in out['events'])


@pytest.mark.parametrize('scenario',['missing','nonfinite','empty','gap'])
def test_missing_trigger_evidence_is_ineligible_not_invalid(tmp_path,monkeypatch,stub_adapter,mock_batch,scenario):
    from scripts import qd_ed_n35_native as audit
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,target=0.,
        providers_mode=scenario if scenario in ('empty','gap') else 'normal',
        fault=scenario if scenario in ('missing','nonfinite') else None)
    generic=a();assert generic['accepted'],generic['errors']
    result=audit.audit_events('N35',m,e,c,expected_runtime=expected(e))
    assert result['lifecycle']['eligible_boundaries']==0
    if scenario=='gap':assert 'unguided_or_mode_off' in result['lifecycle']['resets']


def test_select_exception_resets_pending_intent(monkeypatch,stub_adapter,mock_batch):
    p,provider,conf,rec,_,_=make('off',stub_adapter,monkeypatch,torch.float32)
    from core.qd_closure_intent import ClosureIntentMemory
    p._closure_intent=ClosureIntentMemory();p._closure_intent.previous={'unusable':'sentinel'}
    def broken(*args,**kwargs):raise RuntimeError('synthetic model exception')
    monkeypatch.setattr(p._obs_processor,'observe',broken)
    with pytest.raises(RuntimeError,match='synthetic model exception'):p.select_action(mock_batch)
    assert p._closure_intent.previous is None and not p._closure_intent.latch
