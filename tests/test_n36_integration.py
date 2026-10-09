"""Real policy/recorder chains with synthetic model/observations, independent audit."""
import copy,io,json
from collections import Counter
from pathlib import Path
import pytest,torch,numpy as np
from test_n31_capture_dwell_integration import make,packet,runtime_cfg,_patch_core_imports,stub_adapter,mock_batch


def episode(tmp_path,monkeypatch,adapter,batch,arm='N36',dtype=torch.float32,providers_mode='normal',disk=False,nohit=False, fault=None,target=.01,positive_template=False,terminal_kind='truncated',terminal_prefix=8):
    from core.decision_evidence import DecisionEvidence
    from scripts import audit_decision_evidence as generic
    p,provider,conf,_,_,_=make('on' if arm=='N36' else 'off',adapter,monkeypatch,dtype)
    if arm=='N36':
        conf.update(closure_intent_mode='off', n35_runtime_binding=None, nonprogress_tangent_mode='nonprogress_tangent_v1',
            n36_runtime_binding={'task_id':0,'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','run_id':'CPU-synthetic-only'}, capture_dwell_proposal_mode='off', observed_jaw_approach_mode='observed_jaw_approach_v1',
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
        if arm=='N36':rec.record('n36_observation_context',packet=ctx)
        torch.manual_seed(310+index)
        actions=p.select_action(batch,generate_new_chunk=True,use_guidance=guided,keypoints=None if not guided else ctx['keypoints'].numpy(),guidance_fns=providers,
            guidance_type='eds',eds_config=runtime_cfg(conf),global_step=step,current_stage=1,
            **({'capture_dwell_context':ctx} if arm=='N36' else {}))
        if guided:metrics.append(copy.deepcopy(p.get_last_eds_metrics()))
        p._nonprogress_tangent.commit(actions,8,step)
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
            p._nonprogress_tangent.acknowledge(action=actions[0,j],step=step+j,index=j+1,terminated=terminated,truncated=truncated)
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
    from core.qd_nonprogress_tangent import SOURCE_FILES
    import hashlib
    root=Path(__file__).resolve().parents[1]
    op=next(e['values'] for e in events if e['event']=='n36_capture_dwell_opportunity')
    return {'binding':{'task_id':0,'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','run_id':'CPU-synthetic-only'},
        'config_sha256':op['config_sha256'],'source_hashes':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in SOURCE_FILES}}

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_real_policy_three_boundaries(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype):
    from scripts import qd_ed_n36_native as audit
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype=dtype,target=.08,providers_mode='chain')
    generic=a();assert generic['accepted'],generic['errors']
    result=audit.audit_events('N36',m,e,c,expected_runtime=expected(e))
    assert result['parent_rounds_verified']==30
    assert result['lifecycle']['eligible_boundaries']>=1
    assert result['lifecycle']['expiries']==3
    assert result['executed_actions_verified']==24
    ops=[x['values'] for x in e if x['event']=='n36_capture_dwell_opportunity']
    assert all(x['memory_eligible'] and x['reason'] in ('nonprogress_tangent','no_native_change') for x in ops[10:20])
    assert any(x['reason']=='nonprogress_tangent' for x in ops[10:20])
    assert c['model_forward_calls']==63 and c['rbf_gradient_calls']==57
    assert not any(x['event'].startswith('n35_') for x in e)
    assert not torch.cuda.is_initialized()


def test_auditor_corruption_prevents_next_admission(tmp_path,monkeypatch,stub_adapter,mock_batch):
    from scripts import qd_ed_n36_native as audit, qd_ed_n36_contract as c, qd_ed_n36_supervise as controller
    from test_n36_controller import events_for
    m,original,compute,_=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,target=.08,providers_mode='chain')
    trust=expected(original)
    assert audit.audit_events('N36',m,original,compute,expected_runtime=trust)['lifecycle']['eligible_boundaries']
    plan={'episodes':c.expected_rows(),'worktree':str(c.ROOT)}
    for fault in ('missing_boundary','missing_ack','missing_commit','missing_expiry','missing_runtime','missing_provider',
                  'origin','occurrence','archive_alias','decode','ack_order','ack_action','latch','rearm','source',
                  'other15','suffix','path','projection','provider','cell','visits','parent','geometry','physical'):
        events=copy.deepcopy(original)
        def event(kind,index=0):return [e for e in events if e['event']==kind][index]
        if fault.startswith('missing_'):
            kind={'boundary':'n36_boundary_entry','ack':'n36_step_acknowledged','commit':'n36_execution_commit',
                'expiry':'n36_boundary_expiry','runtime':'n36_native_runtime','provider':'provider_return'}[fault[8:]]
            events.remove(event(kind))
        elif fault=='origin':event('n36_selected_occurrence')['values']['origin']='ordinary'
        elif fault=='occurrence':event('n36_selected_occurrence')['values']['occurrence']=None
        elif fault=='archive_alias':event('n36_archive_update',10)['values']['archive'][0]['occurrence_id']=999
        elif fault=='decode':event('n36_decode_binding')['values']['decoded'][0,0,6]=1
        elif fault=='ack_order':event('n36_step_acknowledged')['values']['index']=2
        elif fault=='ack_action':event('n36_step_acknowledged')['values']['action'][0]+=1
        elif fault=='latch':event('n36_boundary_expiry',1)['values']['eligible']=False
        elif fault=='rearm':event('n36_boundary_entry',2)['values']['eligible']=not event('n36_boundary_entry',2)['values']['eligible']
        elif fault=='source':event('n36_capture_dwell_opportunity')['values']['source_hashes']['main.py']='0'*64
        elif fault=='other15':event('n36_capture_dwell_opportunity')['values']['actual_scored_population'][0,0,39]+=1
        elif fault=='suffix':event('n36_capture_dwell_opportunity',10)['values']['candidate'][8,10]+=1
        elif fault=='path':event('n36_capture_dwell_opportunity',10)['values']['path']['axis']=0
        elif fault=='projection':event('scoring_inputs')['values']['projected_xyz'][0,1,0]+=.1
        elif fault=='provider':event('provider_return')['values']['result']+=.1
        elif fault=='cell':event('n36_archive_update')['values']['cell_ids'][0]=(event('n36_archive_update')['values']['cell_ids'][0]+1)%16
        elif fault=='visits':event('n36_archive_update')['values']['cumulative_visits'][0]+=1
        elif fault=='parent':event('archive_parent_allocation')['values']['weights']['0']=99.
        elif fault=='geometry':event('n36_archive_update')['values']['geometry']['projected_xyz'][0,1,0]+=.1
        elif fault=='physical':event('n36_boundary_entry',1)['values']['dot']=1.
        # Producer verdicts cannot satisfy the recomputing auditor.
        for e in events:e['producer_PASS']=True
        def verify(row,final):
            if row['profile']=='N36':audit.audit_events('N36',m,events,compute,expected_runtime=trust)
        result=controller.reconcile(plan,events_for([False]*4),verify)
        assert result['status']=='INVALID_STOP' and result['next_row'] is None,fault
        assert len(result['outcomes'])==3,fault


@pytest.mark.parametrize('terminal_kind,terminal_prefix',[('terminated',8),('truncated',3)])
def test_actual_terminal_reset_audited(tmp_path,monkeypatch,stub_adapter,mock_batch,terminal_kind,terminal_prefix):
    from scripts import qd_ed_n36_native as audit
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,target=.08,terminal_kind=terminal_kind,terminal_prefix=terminal_prefix)
    assert a()['accepted']
    result=audit.audit_events('N36',m,e,c,expected_runtime=expected(e))
    assert result['lifecycle']['acknowledgements']==terminal_prefix
    bad=copy.deepcopy(e);bad.remove(next(x for x in bad if x['event']=='n36_memory_reset'))
    with pytest.raises(ValueError):audit.audit_events('N36',m,bad,c,expected_runtime=expected(e))


@pytest.mark.parametrize('scenario',['empty','gap','missing','nonfinite'])
def test_ineligible_whole_episode_is_still_audited(tmp_path,monkeypatch,stub_adapter,mock_batch,scenario):
    from scripts import qd_ed_n36_native as audit
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,target=.08,
        providers_mode=scenario if scenario in ('empty','gap') else 'normal',fault=scenario if scenario in ('missing','nonfinite') else None)
    assert a()['accepted']
    result=audit.audit_events('N36',m,e,c,expected_runtime=expected(e))
    assert result['lifecycle']['eligible_boundaries']==0


@pytest.mark.parametrize('arm',['C0','Q0','N34'])
def test_control_absence_and_native_score_recomputation(tmp_path,monkeypatch,stub_adapter,mock_batch,arm):
    import test_n34_observed_jaw as control
    from scripts.qd_ed_n36_arithmetic import verify_scores
    m,e,c,a=control.episode(tmp_path,monkeypatch,stub_adapter,mock_batch,arm=arm)
    assert a()['accepted']
    assert not any(x['event'].startswith(('n35_','n36_')) for x in e)
    result=verify_scores(e,device='cpu')
    assert result['batches']==c['reward_scoring_batches'] and result['gpu_attested'] is False

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
        n34_runtime_binding=binding,closure_intent_mode='off',n35_runtime_binding=None,nonprogress_tangent_mode='nonprogress_tangent_v1',n36_runtime_binding=binding)
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
        assert p._nonprogress_tangent.previous is None and not p._nonprogress_tangent.latch
        return
    out=run(case)
    assert out['steps']==16 and out['cache_reads']==1 and out['policy_reads']==17
    assert out['tracker_reads']==out['snapshots']==2
    assert p._nonprogress_tangent.previous is None and not p._nonprogress_tangent.latch
    assert out['compute']['model_forward_calls']==42 and out['compute']['rbf_gradient_calls']==38
    if observer:
        assert len([e for e in out['events'] if e['event']=='n36_step_acknowledged'])==16
        assert not any(e['event'].startswith('n34_') for e in out['events'])




def test_cpu_worker_audit_is_not_native_cuda_attestation(tmp_path,monkeypatch,stub_adapter,mock_batch):
    from scripts import qd_ed_n36_worker as worker
    from scripts.qd_ed_audit_backend import create_backend
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,target=.08,disk=True)
    report=a();assert report['accepted']
    report=worker.audit_native('N36',tmp_path,report,create_backend('cpu'),expected(e),arithmetic_device='cpu')
    assert report[worker.n36.GATE]['arithmetic']['device']=='cpu'
    with pytest.raises(ValueError,match='actual device arithmetic'):
        worker.native_counts('N36',tmp_path,report,expected(e))
    assert not torch.cuda.is_initialized()
