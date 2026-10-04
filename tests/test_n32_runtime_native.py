"""Real policy/recorder chains with synthetic model/observations, independent audit."""
import copy,io,json
from collections import Counter
from pathlib import Path
import pytest,torch,numpy as np
from test_n31_capture_dwell_integration import make,packet,runtime_cfg,_patch_core_imports,stub_adapter,mock_batch


def episode(tmp_path,monkeypatch,adapter,batch,arm='N32',dtype=torch.float32,providers_mode='normal',disk=False,nohit=False):
    from core.decision_evidence import DecisionEvidence
    from scripts import audit_decision_evidence as generic
    p,provider,conf,_,_,_=make('on' if arm=='N32' else 'off',adapter,monkeypatch,dtype)
    if arm=='N32':
        conf.update(capture_dwell_proposal_mode='off', archive_eligible_capture_mode='archive_eligible_capture_v1',
            n32_runtime_binding={'task_id':0,'source_commit':'148d1aae182500df04d0fa8b13fc54bc533e56a7','run_id':'CPU-synthetic-only'})
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
        step=index*8;guided=mode!='unguided';providers=[] if mode in ('empty','unguided') else [provider];ctx=packet(.01);ctx['task_id']=0
        if nohit:ctx['gripper_qpos']=torch.tensor([.04,.03],dtype=torch.float64)
        if not guided:ctx.update(keypoints=None,tracker=None)
        rec.begin_decision(global_step=step,stage=1,use_guidance=guided,keypoints=ctx['keypoints'],providers=providers,keypoint_tracking_snapshot=ctx['tracker'])
        if arm=='N32':rec.record('n32_observation_context',packet=ctx)
        torch.manual_seed(310+index)
        actions=p.select_action(batch,generate_new_chunk=True,use_guidance=guided,keypoints=None if not guided else ctx['keypoints'].numpy(),guidance_fns=providers,
            guidance_type='eds',eds_config=runtime_cfg(conf),global_step=step,current_stage=1,
            **({'capture_dwell_context':ctx} if arm=='N32' else {}))
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
    # Test fixture trust anchor only; external audits must supply a separately
    # reviewed manifest rather than derive their trust anchor from evidence.
    from pathlib import Path
    import hashlib
    op=next(e['values'] for e in events if e['event']=='n32_archive_eligible_opportunity')
    root=Path(__file__).resolve().parents[1]/'core'
    return {'binding':{'task_id':0,'source_commit':'148d1aae182500df04d0fa8b13fc54bc533e56a7','run_id':'CPU-synthetic-only'},
        'config_sha256':op['config_sha256'],
        'source_hashes':{name:hashlib.sha256(((root.parent/'main.py') if name=='main.py' else root/name).read_bytes()).hexdigest() for name in
            ('qd_archive_eligible_runtime.py','qd_archive_eligible_capture.py','qd_capture_dwell.py',
             'qd_capture_dwell_proposal.py','qd_ed.py','rdt_policy_steer.py','main.py')}}


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_n32_real_policy_native_audit(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype):
    from scripts import qd_ed_n32_native as n
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype=dtype)
    report=a();assert report['accepted'],report['errors']
    gate=n.audit_events('N32',m,e,c,expected_runtime=expected(e))
    assert gate['opportunities_verified']==10 and gate['other15_commitments_verified']==10
    report[n.GATE]=gate
    assert n.counts('N32',m,report,1,expected_runtime=expected(e))[0]['parent_rounds_verified']==10
    assert not any(x['event'].startswith('n31_') for x in e)
    print('N32_COSTS',dtype,m[0]['capture_dwell_proposal']['costs'])


@pytest.fixture
def native_run(tmp_path,monkeypatch,stub_adapter,mock_batch):
    return episode(tmp_path,monkeypatch,stub_adapter,mock_batch)


@pytest.mark.parametrize('fault',['missing_parent','parent_bytes','selected','slot15','other15','cost',
    'projection','origin','source_iter','decision','source','config','task','occurrences','missing_projection',
    'rng','compute','executed','retention','packet','missing_binding','provider','mask'])
def test_n32_independent_rejects(native_run,fault):
    from scripts import qd_ed_n32_native as n
    m,e,c,_=native_run
    trusted=expected(e);m,e,c=copy.deepcopy((m,e,c))
    of=lambda kind:[v['values'] for v in e if v['event']==kind]
    op=of('n32_archive_eligible_opportunity')[0];parent=op['parents'][0]
    if fault=='missing_parent':op['parents'].pop()
    elif fault=='parent_bytes':parent['source']['plan'][0,39]+=.1
    elif fault=='selected':op['selected_cell']=99
    elif fault=='slot15':op['actual_scored_population'][15,0,10]=123
    elif fault=='other15':op['original_post_rollout_population'][0,0,39]+=.1
    elif fault=='cost':parent['source']['cost']+=1
    elif fault=='projection':parent['source']['projection'][0,0]+=.1
    elif fault=='origin':parent['source']['source_origin'][0]+=.1
    elif fault=='source_iter':parent['source_iter']=7
    elif fault=='decision':op['identity']['step']+=8
    elif fault=='source':op['source_hashes']['rdt_policy_steer.py']='f'*64
    elif fault=='config':op['config']['cem_iters']=9
    elif fault=='task':op['binding']['task_id']=99
    elif fault=='occurrences':parent['matching_occurrences'].append(999)
    elif fault=='missing_projection':parent['source']['projection']=None
    elif fault=='rng':op['prepare_rng_after']['cpu'][0]^=1
    elif fault=='compute':c['reward_evaluations']+=1
    elif fault=='executed':of('executed_action')[0]['action_numpy'][0]+=.1
    elif fault=='retention':of('n32_archive_update')[0]['archive'][0]['source_iter']=9
    elif fault=='packet':op['observation']['gripper_qpos'][0]+=.1
    elif fault=='missing_binding':trusted=None
    elif fault=='provider':op['identity']['provider']['code_structure_sha256']='f'*64
    elif fault=='mask':of('n32_canonical_cache')[0]['action_mask'][0,0,11]=1
    with pytest.raises((ValueError,KeyError,IndexError)):
        n.audit_events('N32',m,e,c,expected_runtime=trusted)


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('case',['secondary','best','none','duplicate','tie'])
def test_actual_adapter_all_parent_cases(monkeypatch,dtype,case):
    from dataclasses import dataclass,field,replace
    from types import SimpleNamespace
    from test_qd_archive_eligible_capture import fixture,raw
    from core.qd_archive_eligible_runtime import ArchiveEligibleDecision
    from core.qd_capture_dwell import CaptureDwellDecision
    from scripts.qd_ed_n32_reference import enumerate_parents
    occupied,cache,kw=fixture(dtype)
    if case=='best':cache.entries[0]['projection'].zero_()
    if case=='none':cache.entries[1]['projection'].fill_(1)
    if case=='duplicate':cache.entries[2]={**copy.deepcopy(cache.entries[1]),'row':2,'occurrence':2}
    if case=='tie':occupied={9:occupied[1],3:occupied[1]}
    @dataclass
    class Config:
        n32_runtime_binding: dict=field(default_factory=lambda:{'task_id':0,'source_commit':'1'*40,'run_id':'unit'})
    sem=SimpleNamespace(identity={'synthetic':True},target_index=0,validate=lambda _:None)
    ctx=packet();ctx['task_id']=0;ctx['keypoints']=kw['target'][None]
    d=ArchiveEligibleDecision(sem,ctx,ctx['keypoints'],episode=0,stage=0,step=0,action_mask=kw['action_mask'],config=Config())
    d.entries=copy.deepcopy(cache.entries);d.batches=1
    arc=SimpleNamespace(entries=occupied)
    population=torch.stack([r['plan'] for r in cache.entries]);original=population.clone()
    rng=torch.random.get_rng_state().clone()
    d.prepare(arc,0,[],ctx['keypoints'],None)
    record=copy.deepcopy(d.pending)
    actual=d.apply(population,None)
    assert raw(population)==raw(original) and raw(actual[:15])==raw(original[:15])
    assert torch.equal(rng,torch.random.get_rng_state())
    independent={c:{'plan':e.action,'reward':e.reward,'cost':e.cost,'fingerprint':e.fingerprint,
        'source_iter':e.source_iter,'insert_sequence':e.insert_sequence} for c,e in occupied.items()}
    parents,selected,candidate,arrival,reason=enumerate_parents(independent,cache.entries,0,kw['action_mask'],kw['target'],ctx)
    assert len(parents)==len(record['parents']) and selected==record['selected_cell']
    if case=='none':assert actual is population and raw(actual)==raw(original)
    else:assert raw(actual[15])==raw(candidate)
    if case=='secondary':assert selected==1
    if case=='duplicate':assert record['parents'][1]['matching_occurrences']==[1,2]
    if case=='tie':assert selected==3
    if case=='best':
        old=CaptureDwellDecision(sem,ctx,ctx['keypoints'],episode=0,stage=0,step=0,action_mask=kw['action_mask'])
        old.entries=copy.deepcopy(cache.entries)
        for e in old.entries:
            from core.qd_capture_dwell import native_id
            e['native_identity']=native_id(e['plan'])
        old.batches=1
        arc.select_global_best=lambda:(0,occupied[0])
        old.prepare(arc,0,[],ctx['keypoints'],None)
        assert raw(old.apply(population,None))==raw(actual)


@pytest.mark.parametrize('fault',['projection','duplicate','source','identity','packet'])
def test_adapter_rejects_missing_contradictory_provenance(fault):
    from dataclasses import dataclass,field,replace
    from types import SimpleNamespace
    from test_qd_archive_eligible_capture import fixture
    from core.qd_archive_eligible_runtime import ArchiveEligibleDecision
    occupied,cache,kw=fixture()
    @dataclass
    class Config:
        n32_runtime_binding: dict=field(default_factory=lambda:{'task_id':0,'source_commit':'1'*40,'run_id':'unit'})
    sem=SimpleNamespace(identity={'synthetic':True},target_index=0,validate=lambda _:None)
    ctx=packet();ctx['task_id']=0
    if fault=='packet':ctx['tracker']=None
    with pytest.raises((ValueError,RuntimeError)):
        d=ArchiveEligibleDecision(sem,ctx,ctx['keypoints'],episode=0,stage=0,step=0,action_mask=kw['action_mask'],config=Config())
        d.entries=cache.entries;d.batches=1
        if fault=='projection':d.entries[1]['projection']=None
        if fault=='duplicate':
            d.entries[2]={**copy.deepcopy(d.entries[1]),'row':2,'occurrence':2};d.entries[2]['cost']+=1
        if fault=='source':occupied[1]=replace(occupied[1],source_iter=2)
        if fault=='identity':ctx['keypoints']+=1
        d.prepare(SimpleNamespace(entries=occupied),0,[],ctx['keypoints'],None)


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_full_noeligible_off_population_rng_calls_parity(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype):
    from scripts import qd_ed_n32_native as n
    results=[]
    for arm in ('Q0','N32'):
        folder=tmp_path/arm;folder.mkdir()
        m,e,c,a=episode(folder,monkeypatch,stub_adapter,mock_batch,arm=arm,dtype=dtype,nohit=True)
        results.append((m,e,c,torch.random.get_rng_state().clone()))
        if arm=='N32':
            gate=n.audit_events(arm,m,e,c,expected_runtime=expected(e))
            assert gate['changed_proposals_verified']==0
    from scripts.qd_ed_n31_reference import same
    a,b=results
    for kind,key in [('canonical_candidate_batch','candidates'),('final_selection','selected_latent'),('executed_action','action_numpy')]:
        av=[e['values'][key] for e in a[1] if e['event']==kind]
        bv=[e['values'][key] for e in b[1] if e['event']==kind]
        assert len(av)==len(bv) and all(same(x,y) for x,y in zip(av,bv))
    assert torch.equal(a[3],b[3])
    for key in ('model_forward_calls','model_batch_rows','rbf_gradient_calls','reward_scoring_batches','reward_evaluations'):
        assert a[2][key]==b[2][key]
    assert Counter(e['event'] for e in a[1] if e['event'] in ('projection_origin','scoring_inputs','provider_return'))==Counter(e['event'] for e in b[1] if e['event'] in ('projection_origin','scoring_inputs','provider_return'))


def test_n32_config_requires_explicit_binding_and_no_mixed_modes(stub_adapter,monkeypatch):
    p,_,conf,_,_,_=make('on',stub_adapter,monkeypatch,torch.float32)
    conf.update(capture_dwell_proposal_mode='off',archive_eligible_capture_mode='archive_eligible_capture_v1')
    with pytest.raises(ValueError):p._resolve_eds_config_with_reference_defaults(conf)
    conf['n32_runtime_binding']={'task_id':0,'source_commit':'1'*40,'run_id':'unit'}
    assert p._resolve_eds_config_with_reference_defaults(conf).archive_eligible_capture_mode=='archive_eligible_capture_v1'
    with pytest.raises(ValueError):p._resolve_eds_config_with_reference_defaults({**conf,'capture_dwell_proposal_mode':'capture_dwell_proposal_v1'})
    with pytest.raises(ValueError):p._resolve_eds_config_with_reference_defaults({**conf,'qd_parent_survivor_count':1})


@pytest.mark.parametrize("observer",[False,True])
def test_n32_complete_main_raw_packet_no_new_observation(stub_adapter,monkeypatch,tmp_path,observer):
    from test_n30_initial_observation_repair import make_case,run
    case=make_case(stub_adapter,monkeypatch,tmp_path,mode="Q0",steps=16)
    app,p,rec,state=case
    from test_n31_capture_dwell_integration import config,project_adapter
    app.config["eds_config"]=config()
    app.config["eds_config"].update(capture_dwell_proposal_mode='off',archive_eligible_capture_mode='archive_eligible_capture_v1',
        n32_runtime_binding={'task_id':0,'source_commit':'1'*40,'run_id':'main-unit'})
    # Raw cached adapter fields carry native float64; preprocessor erases robot_state.
    def enrich(obs):
        obs["observation.robot_state"]["eef"]["quat"]=torch.tensor([[0.,0.,0.,1.]],dtype=torch.float64)
        obs["observation.robot_state"]["gripper"]={"qpos":torch.tensor([[.02,-.02]],dtype=torch.float64)}
        return obs
    enrich(stub_adapter._last_obs)
    old=stub_adapter.step
    def step(a):
        o,r,t,tr,i=old(a);enrich(o);return o,r,t,tr,i
    stub_adapter.step=step
    project_adapter(stub_adapter,monkeypatch)
    if not observer:
        app._enable_decision_evidence=lambda ep:None;p._decision_evidence=None;stub_adapter._decision_evidence=None
        rec.all_events=[];rec.finished=False
    out=run(case)
    assert out["cache_reads"]==1 and out["policy_reads"]==17 and out["steps"]==16
    assert out["tracker_reads"]==out["snapshots"]==2
    assert all("observation.robot_state" not in x for x in out["processed"])
    if observer:
        events=[e for e in out["events"] if e["event"]=="n32_observation_context"]
        assert len(events)==2
        assert all(e["values"]["packet"]["hand_quaternion_xyzw"].dtype==torch.float64 for e in events)
    assert not hasattr(p,"_executed_progress")
    assert out["compute"]["model_forward_calls"]==42 and out["compute"]["rbf_gradient_calls"]==38
    assert out["compute"]["reward_scoring_batches"]==32 and out["compute"]["reward_evaluations"]==512



def test_recursive_native_cpu_copy_and_no_alias():
    from core.qd_archive_eligible_runtime import cpu
    value=[{'plan':torch.ones(2,dtype=torch.bfloat16),'origin':(torch.zeros(3,dtype=torch.float64),)}]
    copied=cpu(value)
    assert copied[0]['plan'].dtype==torch.bfloat16 and copied[0]['origin'][0].dtype==torch.float64
    assert copied[0]['plan'].data_ptr()!=value[0]['plan'].data_ptr()
    assert copied[0]['origin'][0].data_ptr()!=value[0]['origin'][0].data_ptr()
    copied[0]['plan'].zero_()
    assert bool(value[0]['plan'].all())


def test_actual_hydra_n32_configuration(stub_adapter,monkeypatch):
    from hydra import compose,initialize_config_dir
    from pathlib import Path
    p,_,conf,_,_,_=make('on',stub_adapter,monkeypatch,torch.float32)
    with initialize_config_dir(config_dir=str(Path(__file__).resolve().parents[1]/'configs'),version_base=None):
        composed=compose(config_name='config',overrides=['main.eds_config.archive_eligible_capture_mode=archive_eligible_capture_v1',
            'main.eds_config.n32_runtime_binding={task_id:0,source_commit:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,run_id:CPU}'])
    conf.update(capture_dwell_proposal_mode='off',archive_eligible_capture_mode=composed.main.eds_config.archive_eligible_capture_mode,
        n32_runtime_binding=composed.main.eds_config.n32_runtime_binding)
    assert p._resolve_eds_config_with_reference_defaults(conf).n32_runtime_binding['run_id']=='CPU'


def test_disk_native_audit_gate_and_binding(tmp_path,monkeypatch,stub_adapter,mock_batch):
    from scripts import qd_ed_n32_native as n
    from types import SimpleNamespace
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,disk=True)
    generic=a();assert generic['accepted'],generic['errors']
    trusted=expected(e)
    report=n.audit_output('N32',tmp_path,generic,SimpleNamespace(report=lambda:{'kind':'cpu'}),expected_runtime=trusted)
    assert n.from_output('N32',tmp_path,report,expected_runtime=trusted)[0]['opportunities_verified']==10
    with pytest.raises(ValueError):n.from_output('N32',tmp_path,report)
    damaged=copy.deepcopy(report);del damaged[n.GATE]['runtime_identity']
    with pytest.raises(ValueError):n.from_output('N32',tmp_path,damaged,expected_runtime=trusted)
