"""Real policy/recorder chains with synthetic model/observations, independent audit."""
import copy,io,json
from collections import Counter
from pathlib import Path
import pytest,torch,numpy as np
from test_n31_capture_dwell_integration import make,packet,runtime_cfg,_patch_core_imports,stub_adapter,mock_batch


def episode(tmp_path,monkeypatch,adapter,batch,arm='N34',dtype=torch.float32,providers_mode='normal',disk=False,nohit=False, fault=None,target=.01):
    from core.decision_evidence import DecisionEvidence
    from scripts import audit_decision_evidence as generic
    p,provider,conf,_,_,_=make('on' if arm=='N34' else 'off',adapter,monkeypatch,dtype)
    if arm=='N34':
        conf.update(capture_dwell_proposal_mode='off', observed_jaw_approach_mode='observed_jaw_approach_v1',
            n34_runtime_binding={'task_id':0,'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','run_id':'CPU-synthetic-only'})
    if arm=='off':conf.update(observed_jaw_approach_mode='off', n34_runtime_binding=None)
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
        step=index*8;guided=mode!='unguided';providers=[] if mode in ('empty','unguided') else [provider];ctx=packet(target);ctx['task_id']=0
        if nohit:ctx['gripper_qpos']=torch.tensor([.04,.03],dtype=torch.float64)
        if fault == 'entry':ctx['observed_eef'][0]=.01
        if fault == 'nonfinite':ctx['hand_quaternion_xyzw'][0]=float('nan')
        if fault == 'empty':ctx['gripper_qpos']=torch.tensor([-.02,.02],dtype=torch.float64)
        if fault == 'missing':ctx['observed_eef']=None
        if not guided:ctx.update(keypoints=None,tracker=None)
        rec.begin_decision(global_step=step,stage=1,use_guidance=guided,keypoints=ctx['keypoints'],providers=providers,keypoint_tracking_snapshot=ctx['tracker'])
        if arm=='N34':rec.record('n34_observation_context',packet=ctx)
        torch.manual_seed(310+index)
        actions=p.select_action(batch,generate_new_chunk=True,use_guidance=guided,keypoints=None if not guided else ctx['keypoints'].numpy(),guidance_fns=providers,
            guidance_type='eds',eds_config=runtime_cfg(conf),global_step=step,current_stage=1,
            **({'capture_dwell_context':ctx} if arm=='N34' else {}))
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
    op=next(e['values'] for e in events if e['event']=='n34_capture_dwell_opportunity')
    root=Path(__file__).resolve().parents[1]/'core'
    return {'binding':{'task_id':0,'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','run_id':'CPU-synthetic-only'},
        'config_sha256':op['config_sha256'],
        'source_hashes':{name:hashlib.sha256((root.parent/name).read_bytes()).hexdigest() for name in
            __import__('core.qd_observed_jaw_approach',fromlist=['SOURCE_FILES']).SOURCE_FILES}}



from core.qd_observed_jaw_approach import propose
from scripts.qd_ed_n34_reference import reconstruct
from scripts.qd_ed_n31_reference import same
from core.rdt_libero_action_converter import encode_libero_prefix, decode_rdt_libero_action_chunk


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('target',[[.04,0.,0.],[2.,-2.,2.],[0.,0.,0.],[.008,0.,-.0116],[.0080001,0.,0.]])
@pytest.mark.parametrize('quat',[[0.,0.,0.,1.],[.2,-.5,.1,.7],[0.,0.,2.,2.]])
def test_independent_geometry_and_native_mapping(dtype,target,quat):
    torch.manual_seed(34)
    plan=torch.randn(64,128,dtype=dtype)
    ctx=packet();ctx['keypoints']=torch.tensor([target],dtype=torch.float64)
    ctx['hand_quaternion_xyzw']=torch.tensor(quat,dtype=torch.float64)
    args=dict(target=ctx['keypoints'][0],observed_eef=ctx['observed_eef'],
        hand_quaternion_xyzw=ctx['hand_quaternion_xyzw'],gripper_qpos=ctx['gripper_qpos'],target_recognized=True)
    out=propose(plan,**args)
    ref,arrival,reason=reconstruct(plan,args['target'],args['observed_eef'],args['hand_quaternion_xyzw'],args['gripper_qpos'])
    assert same(out.candidate,ref) and out.arrival_index==arrival and out.reason==reason
    assert same(out.candidate[8:],plan[8:])
    untouched=[i for i in range(128) if i not in [10,39,40,41,42,43,44]]
    assert same(out.candidate[:8,untouched],plan[:8,untouched])
    decoded=decode_rdt_libero_action_chunk(out.candidate[None],8)[0]
    assert torch.equal(decoded[:,3:6],torch.zeros(8,3))
    assert torch.all(decoded[:,:3].abs()<=1)
    assert same(encode_libero_prefix(plan,decoded.to(dtype)),out.candidate)
    if reason=='observed_close_dwell':assert torch.all(decoded[:,:6]==0) and torch.all(decoded[:,6]==1)
    else:assert torch.all(decoded[:,6]==-1)
    if target==[2.,-2.,2.]:assert torch.equal(decoded[0,:3],torch.tensor([1.,-1.,1.]))


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('fault',[None,'entry','nonfinite','empty'])
def test_real_policy_native_audit(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype,fault):
    from scripts import qd_ed_n34_native as n
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype=dtype,fault=fault)
    report=a();assert report['accepted'],report['errors']
    gate=n.audit_events('N34',m,e,c,expected_runtime=expected(e))
    assert gate['opportunities_verified']==gate['other15_commitments_verified']==10
    assert gate['executed_actions_verified']==8
    assert not any(x['event'].startswith(('n31_','n32_')) for x in e)
    assert gate['changed_proposals_verified']==(0 if fault in ('nonfinite','empty') else 10)
    ops=[x['values'] for x in e if x['event']=='n34_capture_dwell_opportunity']
    if fault is None:assert all(x['reason']=='observed_open_approach' for x in ops)
    if fault=='entry':assert all(x['reason']=='observed_close_dwell' for x in ops)
    print('N34_CPU',str(dtype),fault,json.dumps(gate,sort_keys=True))


@pytest.mark.parametrize('fault',['candidate','other15','suffix','selection','execution','source','binding','observation','missing','cost'])
def test_tamper_rejected(tmp_path,monkeypatch,stub_adapter,mock_batch,fault):
    from scripts import qd_ed_n34_native as n
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch)
    trust=expected(e)
    def vals(kind):return next(x['values'] for x in e if x['event']==kind)
    op=vals('n34_capture_dwell_opportunity')
    if fault=='candidate':op['candidate'][0,10]=1
    if fault=='other15':op['actual_scored_population'][0,0,39]+=.1
    if fault=='suffix':op['candidate'][8,39]+=.1
    if fault=='selection':vals('final_selection')['selected_latent'][0,0,39]+=.1
    if fault=='execution':vals('executed_action')['action_numpy'][0]+=.1
    if fault=='source':op['source_hashes']['main.py']='0'*64
    if fault=='binding':op['binding']['run_id']='wrong'
    if fault=='observation':vals('n34_observation_context')['packet']['observed_eef'][0]=1
    if fault=='missing':e[:]=[x for x in e if x['event']!='n34_capture_dwell_opportunity']
    if fault=='cost':vals('canonical_candidate_batch')['effective_quality'][0]+=1
    with pytest.raises(ValueError):n.audit_events('N34',m,e,c,expected_runtime=trust)


@pytest.mark.parametrize('mode',['empty','unguided'])
def test_false_trigger_and_disabled_parity(tmp_path,monkeypatch,stub_adapter,mock_batch,mode):
    from scripts import qd_ed_n34_native as n
    results=[]
    for arm in ('Q0','off','N34'):
        folder=tmp_path/arm;folder.mkdir()
        m,e,c,a=episode(folder,monkeypatch,stub_adapter,mock_batch,arm=arm,providers_mode=mode)
        decoded=next(x['values']['action_chunk'] for x in e if x['event']=='policy_action_decode')
        results.append((decoded,torch.random.get_rng_state(),{k:v for k,v in c.items() if k!='decision_evidence'}))
        if arm=='N34':
            if mode=='empty':
                gate=n.audit_events('N34',m,e,c,expected_runtime=expected(e));assert gate['changed_proposals_verified']==0
            else:assert not any(x['event']=='n34_capture_dwell_opportunity' for x in e)
    for result in results[1:]:
        assert same(result[0],results[0][0]) and torch.equal(result[1],results[0][1]) and result[2]==results[0][2]


@pytest.mark.parametrize('fault',['nonfinite','empty'])
def test_no_effect_controls_match_q0(tmp_path,monkeypatch,stub_adapter,mock_batch,fault):
    results=[]
    for arm in ('Q0','off','N34'):
        folder=tmp_path/arm;folder.mkdir()
        m,e,c,a=episode(folder,monkeypatch,stub_adapter,mock_batch,arm=arm,fault=fault)
        results.append((next(x['values']['action_chunk'] for x in e if x['event']=='policy_action_decode'),torch.random.get_rng_state(),c))
    for out,rng,c in results[1:]:
        assert same(out,results[0][0]) and torch.equal(rng,results[0][1])
        assert {k:v for k,v in c.items() if k!='decision_evidence'}=={k:v for k,v in results[0][2].items() if k!='decision_evidence'}

@pytest.mark.parametrize("observer",[False,True])
def test_n34_complete_main_raw_packet_no_new_observation(stub_adapter,monkeypatch,tmp_path,observer):
    from test_n30_initial_observation_repair import make_case,run
    case=make_case(stub_adapter,monkeypatch,tmp_path,mode="Q0",steps=16)
    app,p,rec,state=case
    from test_n31_capture_dwell_integration import config,project_adapter
    app.config["eds_config"]=config()
    app.config["eds_config"].update(capture_dwell_proposal_mode='off',observed_jaw_approach_mode='observed_jaw_approach_v1',
        n34_runtime_binding={'task_id':0,'source_commit':'1'*40,'run_id':'main-unit'})
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
        events=[e for e in out["events"] if e["event"]=="n34_observation_context"]
        assert len(events)==2
        assert all(e["values"]["packet"]["hand_quaternion_xyzw"].dtype==torch.float64 for e in events)
    assert not hasattr(p,"_executed_progress")
    assert out["compute"]["model_forward_calls"]==42 and out["compute"]["rbf_gradient_calls"]==38
    assert out["compute"]["reward_scoring_batches"]==32 and out["compute"]["reward_evaluations"]==512



from torch import nn
from PIL import Image
@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_production_input_encoder_native_mask(dtype):
    from core.rdt_policy_steer import _RDTModelAdapter

    class _FakeImageProcessor:
        image_mean = [0.5, 0.5, 0.5]
        size = {"height": 8, "width": 8}

        def preprocess(self, img, return_tensors):
            assert return_tensors == "pt"
            return {"pixel_values": torch.zeros(1, 3, 8, 8)}

    class _FakeVision(nn.Module):
        hidden_size = 1152

        def forward(self, image_tensor):
            return torch.zeros(image_tensor.shape[0], 1, self.hidden_size)

    class _FakePolicy(nn.Module):
        def __init__(self):
            super().__init__()
            self.noise_scheduler_sample = None
            self.captured_state_tokens = None

        def adapt_conditions(self, text_embeds, image_embeds, state_tokens):
            self.captured_state_tokens = state_tokens.detach().clone()
            return (
                torch.zeros(1, 1, 4),
                torch.zeros(1, 1, 4),
                torch.zeros(1, 1, 4),
            )

    class _FakeReal:
        def __init__(self):
            self.device = torch.device("cpu")
            self.dtype = dtype
            self.image_processor = _FakeImageProcessor()
            self.image_size = None
            self.args = {
                "dataset": {"image_aspect_ratio": "pad"},
                "model": {"state_token_dim": 128},
            }
            self.vision_model = _FakeVision()
            self.text_model = nn.Identity()
            self.policy = _FakePolicy()
            self.control_frequency = 20

    real = _FakeReal()
    adapter = _RDTModelAdapter(real)
    state_128 = torch.zeros(1, 128)
    state_mask_128 = torch.zeros(1, 128)
    state_mask_128[0, [0, 1, 2, 3, 4, 5, 6, 10, 11]] = 1.0
    images = [Image.fromarray(np.zeros((8,8,3),dtype=np.uint8)) for _ in range(6)]

    cond = adapter.encode_inputs(state_128, state_mask_128, images, torch.ones(1, 1, 4096))

    captured = real.policy.captured_state_tokens
    assert captured is not None
    assert tuple(captured.shape) == (1, 1, 256)
    appended_mask = captured[0, 0, 128:]
    assert torch.where(appended_mask > 0)[0].tolist() == [10, 39, 40, 41, 42, 43, 44]
    assert cond["action_indices"] == [39, 40, 41, 42, 43, 44, 10]
    assert torch.where(cond["action_mask"][0, 0] > 0)[0].tolist() == [10, 39, 40, 41, 42, 43, 44]



def test_disk_receipt_has_n34_identity(tmp_path,monkeypatch,stub_adapter,mock_batch):
    from scripts import qd_ed_n34_native as n
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,disk=True)
    generic=a();assert generic['accepted'],generic['errors']
    trust=expected(e)
    report=n.audit_output(tmp_path,generic,expected_runtime=trust)
    assert report[n.GATE]['profile']=='N34'
    assert report[n.GATE]['runtime_identity']==trust
    assert report[n.GATE]['schema']=='n34-independent-observed-jaw-v1'
    with pytest.raises(ValueError):n.audit_output(tmp_path,dict(generic,accepted=False),expected_runtime=trust)
    with pytest.raises(ValueError):n.audit_events('N34',m,e,c,expected_runtime={})


def test_explicit_config_hydra_and_exclusive_modes(stub_adapter,monkeypatch):
    from hydra import compose,initialize_config_dir
    p,_,conf,_,_,_=make('off',stub_adapter,monkeypatch,torch.float32)
    with initialize_config_dir(config_dir=str(Path(__file__).resolve().parents[1]/'configs'),version_base=None):
        composed=compose(config_name='config',overrides=['main.eds_config.observed_jaw_approach_mode=observed_jaw_approach_v1',
            'main.eds_config.n34_runtime_binding={task_id:0,source_commit:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,run_id:CPU}'])
    conf.update(observed_jaw_approach_mode=composed.main.eds_config.observed_jaw_approach_mode,
        n34_runtime_binding=dict(composed.main.eds_config.n34_runtime_binding))
    resolved=p._resolve_eds_config_with_reference_defaults(conf)
    assert resolved.observed_jaw_approach_mode=='observed_jaw_approach_v1'
    for change in ({'n34_runtime_binding':None},{'archive_eligible_capture_mode':'archive_eligible_capture_v1'},
        {'capture_dwell_proposal_mode':'capture_dwell_proposal_v1'},{'qd_parent_survivor_count':1},
        {'qd_quality_mode':'actuator_clipped_v1'},{'observed_jaw_approach_mode':'typo'}):
        with pytest.raises(ValueError):p._resolve_eds_config_with_reference_defaults({**conf,**change})


@pytest.mark.parametrize('missing',['observed_eef','hand_quaternion_xyzw','gripper_qpos'])
@pytest.mark.parametrize('kind',['missing','nan','inf'])
def test_required_observation_noop(missing,kind):
    args=dict(target=torch.zeros(3),observed_eef=torch.zeros(3),hand_quaternion_xyzw=torch.tensor([0.,0.,0.,1.]),
              gripper_qpos=torch.tensor([.02,-.02]),target_recognized=True)
    if kind=='missing':args[missing]=None
    else:args[missing][0]=float(kind)
    plan=torch.zeros(64,128);saved=plan.clone()
    out=propose(plan,**args)
    assert out.candidate is None and same(plan,saved)


def test_no_predicted_close_or_cross_decision_memory():
    plan=torch.ones(64,128)
    args=dict(target=torch.tensor([.04,0.,0.],dtype=torch.float64),observed_eef=torch.zeros(3,dtype=torch.float64),
        hand_quaternion_xyzw=torch.tensor([0.,0.,0.,2.],dtype=torch.float64),gripper_qpos=torch.tensor([.02,-.02],dtype=torch.float64),target_recognized=True)
    approach=propose(plan,**args)
    # Nominal endpoint is the exact center, yet all commands remain open.
    decoded=decode_rdt_libero_action_chunk(approach.candidate[None],8)[0]
    assert torch.all(decoded[:,6]==-1)
    args['observed_eef']=torch.tensor([.04,0.,0.],dtype=torch.float64)
    close=propose(plan,**args)
    assert close.reason=='observed_close_dwell' and torch.all(close.candidate[:8,39:45]==0)
    args['observed_eef'].zero_()
    again=propose(plan,**args)
    assert same(again.candidate,approach.candidate)


@pytest.mark.parametrize('arm',['C0','Q0','N31','N32'])
@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_disabled_matches_exact_base_policy(tmp_path,monkeypatch,stub_adapter,mock_batch,arm,dtype):
    """Load only two changed methods from the authorized base's local Git object."""
    import ast,subprocess,textwrap
    from types import MethodType
    import core.rdt_policy_steer as module
    source=subprocess.check_output(['git','show','04d1255016fa13a2d467995b9e37a6a829356a1c:core/rdt_policy_steer.py'],text=True)
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RDTSteer')
    outputs=[]
    for old in (True,False):
        p,provider,conf,rec,counts,_=make('on' if arm=='N31' else 'off',stub_adapter,monkeypatch,dtype)
        if arm=='C0':conf.update(qd_archive_mode='none',qd_parent_sampling='uniform_cells')
        if arm=='N32':conf.update(archive_eligible_capture_mode='archive_eligible_capture_v1',
            n32_runtime_binding={'task_id':0,'source_commit':'04d1255016fa13a2d467995b9e37a6a829356a1c','run_id':'CPU-parity'})
        if old:
            for name in ('_eds_guided_denoise_loop','_resolve_eds_config_with_reference_defaults'):
                node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
                ns=dict(vars(module));exec(compile(textwrap.dedent(ast.get_source_segment(source,node)),'<authorized-base>','exec'),ns)
                monkeypatch.setattr(p,name,MethodType(ns[name],p))
        else:conf['observed_jaw_approach_mode']='off'
        ctx=packet(.01);ctx['task_id']=0
        torch.manual_seed(310)
        value=p.select_action(mock_batch,generate_new_chunk=True,use_guidance=True,keypoints=ctx['keypoints'].numpy(),
            guidance_fns=[provider],guidance_type='eds',eds_config=runtime_cfg(conf),global_step=0,current_stage=1,
            capture_dwell_context=ctx)
        canonical=[event['candidates'] for event in rec.events if event['event']=='canonical_candidate_batch']
        outputs.append((value,torch.random.get_rng_state(),p.get_episode_compute_counters(),canonical,counts['origins']))
    a,b=outputs
    assert same(a[0],b[0]) and torch.equal(a[1],b[1]) and a[2]==b[2] and a[4]==b[4]
    assert len(a[3])==len(b[3])==11 and all(same(x,y) for x,y in zip(a[3],b[3]))


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_unrecognized_nonempty_provider_no_effect(stub_adapter,mock_batch,monkeypatch,dtype):
    outputs=[]
    def unsupported(points,trajectory):return -(trajectory**2).sum()
    for active in (False,True):
        p,_,conf,rec,_,_=make('off',stub_adapter,monkeypatch,dtype)
        if active:conf.update(observed_jaw_approach_mode='observed_jaw_approach_v1',
            n34_runtime_binding={'task_id':0,'source_commit':'0'*40,'run_id':'CPU-unsupported'})
        ctx=packet(.01);ctx['task_id']=0
        torch.manual_seed(310)
        value=p.select_action(mock_batch,generate_new_chunk=True,use_guidance=True,keypoints=ctx['keypoints'].numpy(),
            guidance_fns=[unsupported],guidance_type='eds',eds_config=conf,global_step=0,current_stage=1,capture_dwell_context=ctx)
        outputs.append((value,torch.random.get_rng_state(),p.get_episode_compute_counters()))
        if active:
            assert p.get_last_eds_metrics()['capture_dwell_proposal']['reasons']==['unrecognized_target']*10
    assert same(outputs[0][0],outputs[1][0]) and torch.equal(outputs[0][1],outputs[1][1]) and outputs[0][2]==outputs[1][2]


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_ordinary_selection_and_execution_of_n34(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype):
    from scripts import qd_ed_n34_native as n
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,dtype=dtype,target=.06)
    report=a();assert report['accepted'],report['errors']
    gate=n.audit_events('N34',m,e,c,expected_runtime=expected(e))
    assert gate['selected_proposal_content_decisions']==1
    assert gate['executed_actions_verified']==8
    print('N34_CPU',str(dtype),'selected',json.dumps(gate,sort_keys=True))


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_asymmetric_jaw_center_rotates_to_world(dtype):
    plan=torch.zeros(64,128,dtype=dtype)
    args=dict(target=torch.tensor([.03,.02,.005],dtype=torch.float64),
        observed_eef=torch.tensor([.01,-.02,.003],dtype=torch.float64),
        hand_quaternion_xyzw=torch.tensor([0.,0.,2.,2.],dtype=torch.float64),
        gripper_qpos=torch.tensor([.04,.02],dtype=torch.float64),target_recognized=True)
    out=propose(plan,**args)
    # +90deg world z maps hand center (0,.03,-.0036) to (-.03,0,-.0036).
    decoded=decode_rdt_libero_action_chunk(out.candidate[None],8)[0]
    expected_command=torch.tensor([.625,.5,.07,0.,0.,0.,-1.],dtype=dtype).float()
    torch.testing.assert_close(decoded,expected_command.expand(8,7),rtol=0,atol=1e-7)
    ref,_,reason=reconstruct(plan,args['target'],args['observed_eef'],args['hand_quaternion_xyzw'],args['gripper_qpos'])
    assert same(out.candidate,ref) and reason=='observed_open_approach'


@pytest.mark.parametrize('arm',['C0','Q0'])
def test_control_native_gate_has_no_n34(tmp_path,monkeypatch,stub_adapter,mock_batch,arm):
    from scripts import qd_ed_n34_native as n
    m,e,c,a=episode(tmp_path,monkeypatch,stub_adapter,mock_batch,arm=arm)
    report=a();assert report['accepted'],report['errors']
    gate=n.audit_events(arm,m,e,c)
    assert gate['changed_proposals_verified']==gate['opportunities_verified']==0
    assert gate['profile']==arm
    corrupted=copy.deepcopy(e)
    corrupted.append({**e[-1],'event':'n34_capture_dwell_opportunity'})
    with pytest.raises(ValueError):n.audit_events(arm,m,corrupted,c)
