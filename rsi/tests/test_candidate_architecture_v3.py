from dataclasses import asdict, replace
import json
from types import SimpleNamespace
import numpy as np
import pytest
import torch
from mode_gate.config import ModeGateConfig
from mode_gate.types import ActionChunkBatch, GateContext, TaskSpaceTrajectoryBatch, GeometryEvidence, SemanticCandidateScore, SemanticPlan, ControllerRoute, ProgressEvidence
from mode_gate.gate import TrajectoryCandidateGate
from mode_gate.geometry import select_execution_candidate
from mode_gate.cards import CandidateCardRenderer
from mode_gate.semantic_planner import SemanticPlanner
from mode_gate.verifier import (GroundedCapabilityVerifier, CandidateVerifierInput, build_verifier_input,
    save_verifier_input, load_verifier_input, save_verifier_artifact, FeatureStandardizer, PlattCalibrator,
    DeployedVerifierPredictor)
from mode_gate.verifier_training import VerifierExample, VerifierTrainingConfig, validate_independent_groups, train_verifier, record_verifier_training_usage
from mode_gate.state_machine import EpisodeChunkController
from mode_gate.incidents import IncidentMemory, VerifierDecisionRecord
from mode_gate.experiment_contract import label_contract_payload

THREAD = '01a0893c-15b0-7203-881c-de3c5bcee058'

def evidence(n=40):
    ctx = GateContext('context', np.zeros((24,32,3),dtype=np.uint8),'拿起杯子','stage_1')
    actions = np.random.default_rng(2).normal(0,.1,(n,10,7)).astype(np.float32)
    batch = ActionChunkBatch(actions, [f'c{i}' for i in range(n)],'context',1,'policy','OSC','world')
    class Projector:
        def project(self, batch, ctx):
            positions = np.pad(batch.actions[:,:,:3], ((0,0),(1,0),(0,0)))
            orientations = np.tile([0.,0.,0.,1.],(n,11,1))
            return TaskSpaceTrajectoryBatch(positions, orientations, np.zeros((n,11)),batch.sample_ids)
    return ctx, TrajectoryCandidateGate(ModeGateConfig(sample_count=n), Projector()).analyze(ctx,batch,None)

def input_item(n=40):
    _, ev = evidence(n)
    return build_verifier_input(scene_feature=np.ones(2048), evidence=ev, remaining_budget=50,retry_budget=50,backbone_id='v44-sha')

def test_full_candidates_preserve_ids_actions_time_points():
    _,ev=evidence(64)
    full=ev.planner_candidates()
    assert len(full)==64
    assert full[-1]['candidate_id']=='c63'
    np.testing.assert_array_equal(full[-1]['actions'], ev.action_batch.actions[-1])
    assert np.array(full[-1]['positions']).shape==(11,3)
    assert not hasattr(ev,'modes') and not hasattr(ev,'responsibilities')


@pytest.mark.parametrize('choice',[ControllerRoute.RESTEER,ControllerRoute.EXPAND])
@pytest.mark.parametrize('rollout_complete',[False,True])
def test_formal_local_selection_keeps_all_candidates_and_learned_head(tmp_path,choice,rollout_complete):
    from mode_gate.runtime import CandidateRuntime, RuntimeStatus
    from mode_gate.verifier import VerifierPrediction
    from mode_gate.types import DecisionSnapshot
    ctx,ev=evidence(40)
    ctx=replace(ctx,metadata={'planner_steering_enabled':False,'initialization_posthoc_only':False})
    inputs=[]
    def predict(item):
        inputs.append(item)
        return VerifierPrediction(choice,(3.,-1.) if choice is ControllerRoute.RESTEER else (-1.,3.),.02)
    def unexpected(*args,**kwargs): raise AssertionError('online Planner called')
    runtime=CandidateRuntime(config=ModeGateConfig(controller_mode='learned_verifier',
        require_learned_verifier=True,require_complete_rollout_before_expansion=True),
        gate=SimpleNamespace(analyze=lambda *args:ev),planner=SimpleNamespace(score=unexpected),
        verifier=SimpleNamespace(predict=predict,artifact_root=tmp_path/'head'),backbone_id='frozen-v44',
        combined_renderer=CandidateCardRenderer(None),incidents=IncidentMemory(tmp_path/'incidents'),
        geometry_factory=lambda context:SimpleNamespace(score_round=lambda ev:tuple(
            GeometryEvidence(c.candidate_id,0.,1.,1.,i==0,'test obstacle' if i==0 else None)
            for i,c in enumerate(ev.candidates))))
    runtime.start_episode(stage_id='1')
    runtime.controller.state.verification_due=True
    runtime.controller.state.retry_index=7
    runtime.controller.state.rollout_complete=rollout_complete
    snapshot=DecisionSnapshot('snapshot','policy',tmp_path/'sim.npz',runtime.controller.state.as_dict(),
                              tmp_path/'rng.pt',{},'a'*64,'b'*64)
    result=runtime.process_batch(context=ctx,batch=ev.action_batch,artifact_root=tmp_path/'rounds',
                                  scene_feature=np.ones(2048),snapshot=snapshot,camera_images={})
    assert len(inputs)==1, result.error
    assert inputs[0].remaining_budget==43 and len(inputs[0].candidate_trajectories)==40
    assert result.verifier_decision is choice
    if choice is ControllerRoute.EXPAND and rollout_complete:
        assert result.status is RuntimeStatus.EXPAND and result.selected is None
    else:
        assert result.selected.sample_index==1  # Skip only the vetoed first particle.
        assert result.status is (RuntimeStatus.RESTEER if choice is ControllerRoute.RESTEER else RuntimeStatus.EXECUTE)
    assert runtime.controller.state.retry_index==(8 if choice is ControllerRoute.RESTEER else 7)


def test_gate_accepts_real_fkd_diagnostics_without_losing_any_candidate(tmp_path):
    from rsi.core.fkd_class import FKD, PotentialType
    ctx, ev=evidence()
    fkd=FKD(potential_type=PotentialType.MAX, lmbda=10., num_particles=40,
        adaptive_resampling=True, resample_frequency=5, resampling_t_start=0,
        resampling_t_end=9, timesteps=list(range(10)), reward_fn=lambda x:torch.ones(40),
        device='cpu')
    batch=replace(ev.action_batch,metadata={'sampling_diagnostics':fkd.diagnostics()})
    gate=TrajectoryCandidateGate(ModeGateConfig(),SimpleNamespace(project=lambda batch,ctx:ev.trajectories))
    result=gate.analyze(ctx,batch,tmp_path)
    assert len(result.candidates)==40
    assert tuple(result.sampling_diagnostics.ancestor_ids)==tuple(range(40))
    assert tuple(result.sampling_diagnostics.resample_timesteps)==()
    np.testing.assert_array_equal(result.action_batch.actions,ev.action_batch.actions)

def test_planner_sees_complete_candidates_and_selects_explicitly(tmp_path):
    ctx,ev=evidence()
    ctx=replace(ctx,metadata={"execution_horizon":10})
    geometry=tuple(GeometryEvidence(c.candidate_id,0.,1.,1.,False) for c in ev.candidates)
    planner=SemanticPlanner(client=SimpleNamespace(),thinking_level='ultra')
    prompt=planner._prompt(ctx,ev,geometry,{},[])
    payload=json.loads(prompt.split('\n\n',1)[1])
    assert len(payload['candidates'])==40 and len(payload['candidates'][-1]['actions'])==10
    assert payload['execution_horizon']==10
    assert 'later predicted actions are context, not promised execution' in prompt
    scores=tuple(SemanticCandidateScore(c.candidate_id,1.,'可行',()) for c in ev.candidates)
    assert select_execution_candidate(ev.candidates,geometry,scores,'c39').sample_index==39
    with pytest.raises(ValueError):
        select_execution_candidate(ev.candidates,geometry,scores,None)
    renderer=CandidateCardRenderer(None)
    renderer.render(observation_image=ctx.observation_image,candidate_paths={c.candidate_id:ev.trajectories.positions[c.sample_index] for c in ev.candidates},output_path=tmp_path/'all.png')
    assert (tmp_path/'all.png').is_file()

def test_internal_encoder_permutation_invariant_and_all_candidates_receive_gradient():
    torch.set_num_threads(1)
    item=input_item()
    model=GroundedCapabilityVerifier()
    seen=[]
    def hook(module,args):
        args[0].requires_grad_(True)
        args[0].retain_grad()
        seen.append(args[0])
    handle=model.trajectory_encoder.register_forward_pre_hook(hook)
    logits=model(item)
    logits.sum().backward()
    assert torch.all(seen[0].grad.abs().sum((1,2))>0)
    handle.remove()
    perm=np.random.default_rng(3).permutation(40)
    other=replace(item,candidate_trajectories=item.candidate_trajectories[perm],candidate_ids=tuple(item.candidate_ids[i] for i in perm))
    torch.testing.assert_close(model(item),model(other),atol=2e-6,rtol=2e-6)
    assert model(item).shape==(1,2)
    assert not any('backbone' in n or 'policy' in n for n,_ in model.named_parameters())

def test_no_future_history_and_legacy_feature_rejected(tmp_path):
    with pytest.raises(ValueError,match='later'):
        replace(input_item(),executed_history=np.zeros((1,15)),decision_step=0)
    old=tmp_path/'old.npz'
    np.savez(old,scene_feature=np.ones(2048),mode_ee_features=np.zeros((4,20)))
    with pytest.raises(ValueError,match='legacy'):
        load_verifier_input(old)
    item=input_item(65)
    new=save_verifier_input(tmp_path/'new.npz',item)
    np.testing.assert_array_equal(load_verifier_input(new).candidate_trajectories,item.candidate_trajectories)

def test_argmax_ignores_calibration(tmp_path):
    model=GroundedCapabilityVerifier()
    for p in model.parameters():
        p.data.zero_()
    model.head[-1].bias.data.copy_(torch.tensor([2.,1.]))
    save_verifier_artifact(tmp_path,model=model,standardizer=FeatureStandardizer(),
        calibrator=PlattCalibrator(0.,50.),metadata={'label_config':label_contract_payload(),'backbone_id':'v44-sha'})
    predictor=DeployedVerifierPredictor(tmp_path)
    result=predictor.predict(input_item())
    assert result.route is ControllerRoute.RESTEER and result.p_expansion > .99

def test_budget_50_not_replenished_by_stage_advance():
    cfg=ModeGateConfig(stagnation_window=1)
    controller=EpisodeChunkController(cfg)
    controller.start_episode()
    for i in range(50):
        controller.state.verification_due=True
        controller.begin_sampling();controller.mark_abstracted();controller.mark_scored(has_safe_candidate=True)
        assert controller.route_scored_batch().route is ControllerRoute.RESTEER
        controller.observe_chunk(ProgressEvidence(f'stage_{i+1}',True,1.,'predicate',False))
        assert controller.state.retry_index==i+1
    controller.state.verification_due=True
    controller.begin_sampling();controller.mark_abstracted();controller.mark_scored(has_safe_candidate=True)
    assert controller.route_scored_batch().route is ControllerRoute.EXPAND
    assert cfg.experiment_contract().max_policy_steps_per_branch==500

def test_early_expansion_is_not_supervision_and_revisions_are_separate(tmp_path):
    mem=IncidentMemory(tmp_path)
    decision=VerifierDecisionRecord('r','c','p','s','x'*64,'','EXPANSION','EXPANSION',(0.,1.),.8,
        'head_argmax','learned_verifier',2,48,retry_index=2)
    mem.record_decision(decision)
    fact=mem.record_fact(episode_id='e',context_id='r',kind='retry_outcome',payload={'censored':True,'stop_reason':'early_expansion'})
    annotation={'record_id':'r','episode_id':'e','label_version':'fixed_budget_50-v2','label':'EXPANSION',
        'reason':'提前停止','evidence_refs':[{'event_id':fact['event_id']}], 'use_for_training':True,
        'supersedes':None, 'planner_provenance':{'planner_thread_id':THREAD}}
    with pytest.raises(ValueError,match='alone'):
        mem.annotate(annotation)
    annotation.update(label='AMBIGUOUS/CENSORED',use_for_training=False)
    first=mem.annotate(annotation)
    native=mem.record_fact(episode_id='e',context_id='r',kind='native_outcome',payload={'success':True})
    second=mem.annotate({**annotation,'label':'RE-STEER','use_for_training':True,'reason':'后续真实成功',
        'supersedes':first['annotation_id'],'evidence_refs':[{'event_id':native['event_id']}]})
    assert first['annotation_id']!=second['annotation_id']
    assert len(list(mem.experiences.interpretations.iter_valid()))==2
    assert list(mem.decisions.iter_valid())[0]['route']=='EXPANSION'

def test_train_tiny_dataset_without_touching_backbone_and_independent_leakage(tmp_path):
    torch.set_num_threads(1)
    rows=[]
    for i in range(6):
        item=input_item(5)
        item=replace(item,scene_feature=np.full(2048,(-1)**i,dtype=np.float32),
                     candidate_trajectories=item.candidate_trajectories+10*(i%2)+i*.001,
                     context_id=f'independent-context-{i}')
        path=save_verifier_input(tmp_path/f'f{i}.npz',item)
        from mode_gate.io_utils import sha256_file
        rows.append(VerifierExample(str(i),'p',f'e{i}','train' if i<4 else 'test',str(path),'planner',i%2,
                                    f'a{i}',sha256_file(path),episode_id=f'e{i}',snapshot_hash=f's{i}'))
    with pytest.raises(ValueError,match='leakage'):
        validate_independent_groups([rows[0],replace(rows[4],group_id=rows[0].group_id)])
    result=train_verifier(rows,policy_id='p',output_root=tmp_path/'model',
        config=VerifierTrainingConfig(device='cpu',max_epochs=45,batch_size=4,patience=45),
        reviewer=lambda m:{'accept':m['independent']['accuracy']==1.,'reason':'独立检查',
                           'planner_provenance':{'planner_thread_id':THREAD}})
    assert result.metrics['train']['accuracy']==1.
    assert result.metrics['independent']['contexts']==2
    assert result.gate.passed
    memory = IncidentMemory(tmp_path / 'usage')
    record_verifier_training_usage(memory, result, rows, request_id='planner-request')
    record_verifier_training_usage(memory, result, rows, request_id='planner-request')
    used = list(memory.experiences.training_usage.iter_valid())
    assert len(used) == 1 and len(used[0]['examples']) == 6
    assert used[0]['request_id'] == 'planner-request'

def test_account_planner_remains_designated_task():
    from mode_gate.planner_account import load_planner_account_config
    value=load_planner_account_config()
    assert value['planner_thread_id']==THREAD
    assert value['model']=='gpt-6-astra' and value['reasoning_effort']=='ultra'


@pytest.mark.parametrize('posthoc_only',[False,True])
@pytest.mark.parametrize('planner_enabled',[False,True])
def test_runtime_all_candidates_history_native_fact_and_video(tmp_path,posthoc_only,planner_enabled):
    from mode_gate.runtime import CandidateRuntime, RuntimeStatus
    from mode_gate.types import DecisionSnapshot
    from mode_gate.io_utils import sha256_file
    from mode_gate.demo_matching import compare_demo_candidates
    import h5py
    ctx, ev = evidence(24)
    ctx=replace(ctx,metadata={'initialization_posthoc_only':posthoc_only,
                              'planner_steering_enabled':planner_enabled})
    local = posthoc_only or not planner_enabled
    class Planner:
        def score(self, context, round_evidence, geometry, overlay_path, **kwargs):
            assert not local, 'disabled online role must not request Planner judgments'
            assert len(round_evidence.planner_candidates()) == 24
            return SemanticPlan(tuple(SemanticCandidateScore(c.candidate_id,.9,'可行') for c in ev.candidates),
                '接近并抓取', 'stage_1', .95, 'gpt-6-astra', 'candidate-scorer-v4',
                selected_candidate_id='c23', selection_reason='抓取姿态合适')
    mem = IncidentMemory(tmp_path / 'incidents')
    runtime = CandidateRuntime(config=ModeGateConfig(sample_count=24),
        gate=SimpleNamespace(analyze=lambda *args: ev), planner=Planner(),
        combined_renderer=CandidateCardRenderer(None), incidents=mem, backbone_id='v44-sha',
        geometry_factory=lambda context: SimpleNamespace(score_round=lambda ev:
            tuple(GeometryEvidence(c.candidate_id,0.,1.,1.,False) for c in ev.candidates)))
    runtime.start_episode(stage_id='stage_1')
    runtime.controller.state.verification_due = True
    snapshot = DecisionSnapshot('snapshot','policy',tmp_path/'sim.npz',runtime.controller.state.as_dict(),
                                tmp_path/'rng.pt',{},'a'*64,'b'*64)
    images = {'agentview':np.zeros((24,32,3),np.uint8),'wrist':np.ones((24,32,3),np.uint8)*200}
    mem.record_video_frame(runtime.episode_id,images,context_id='initial',step=0)
    result = runtime.process_batch(context=ctx,batch=ev.action_batch,artifact_root=tmp_path/'rounds',
        scene_feature=np.ones(2048),snapshot=snapshot,camera_images=images)
    assert result.status is RuntimeStatus.RESTEER, result.error
    assert result.selected.sample_index == (0 if local else 23)
    row = list(mem.decisions.iter_valid())[0]
    item = load_verifier_input(row['verifier_feature_path'])
    if local:
        assert row['provenance']['planner_provenance']['planner_called'] is False
        assert row['provenance']['semantic_model']=='local_vls_particle_order'
    assert item.candidate_trajectories.shape[0]==24 and item.remaining_budget==50
    evidence_json = json.loads((tmp_path/'rounds/context/round_001/visuals/evidence.json').read_text())
    original_index = evidence_json['full_video']
    runtime.record_execution_step(np.zeros(7),SimpleNamespace(position=[0,0,0],quaternion=[1,0,0,0]),
        native_success=True,images=images)
    runtime.observe_chunk(ProgressEvidence('stage_1',False,1.,'native',True))
    full = mem.experiences.finish_video(runtime.episode_id, finalize=True)
    assert sha256_file(original_index['path'])==original_index['sha256']
    assert len(json.loads(full.read_text())['segments'])==2
    assert json.loads(full.read_text())['full_video']['path'].endswith('.mp4')
    assert not list(mem.labels.iter_valid())
    outcome = [x for x in mem.experiences.facts.iter_valid() if x['kind']=='retry_outcome'][-1]
    assert outcome['payload']['native_success'] is True
    demo = tmp_path/'success.hdf5'
    with h5py.File(demo,'w') as f:
        f.create_dataset('ee_position',data=ev.trajectories.positions[23])
        f.create_dataset('action',data=ev.action_batch.actions[23])
        f.attrs.update(simulator_success=True,snapshot_id='snapshot')
    comparison = compare_demo_candidates(mem,record_id=result.record_id,demo_path=demo)
    assert len(comparison.comparisons)==24 and comparison.native_success and not comparison.label_attached


def test_planner_explores_native_account_evidence_and_requests_training(tmp_path):
    from mode_gate.experience_planner import ExperiencePlanner
    mem = IncidentMemory(tmp_path / 'incidents')
    for i in range(2):
        feature = save_verifier_input(tmp_path/f'f{i}.npz',replace(input_item(3),context_id=f'c{i}'),
            metadata={'policy_id':'p','snapshot_hash':str(i)*64})
        mem.record_decision(VerifierDecisionRecord(str(i),f'c{i}','p',f's{i}',str(i)*64,'','RE-STEER',None,None,None,
            'fixed_budget_50','fixed_budget_50',0,50,verifier_feature_path=str(feature),provenance={'episode_id':f'e{i}'}))
        fact = mem.record_fact(episode_id=f'e{i}',context_id=str(i),kind='native_outcome',payload={'native_success':bool(i)})
        mem.annotate({'record_id':str(i),'episode_id':f'e{i}','label_version':'fixed_budget_50-v2',
            'label':'RE-STEER' if i else 'EXPANSION','reason':'真实执行证据',
            'evidence_refs':[{'event_id':fact['event_id']}],'use_for_training':True,
            'source':'actual_execution','planner_provenance':{'planner_thread_id':THREAD}})
    ids = [x['annotation_id'] for x in mem.experiences.latest_annotations().values()]
    commands = [('search',{'collection':'annotation_heads'}),
        ('retrain',{'train_annotation_ids':[ids[0]],'independent_annotation_ids':[ids[1]],'reason':'新经历可用于训练检查'}),
        ('finish',{'reason':'开始训练'})]
    class Client:
        def request(self,**kwargs):
            action,args = commands.pop(0)
            return SimpleNamespace(text=json.dumps({'action':action,'arguments':args}),planner_metadata={'planner_thread_id':THREAD})
    result = ExperiencePlanner(mem,client=Client()).run(purpose='verifier_training',current={'policy_id':'p'})
    assert result['training_request']['train_annotation_ids']==[ids[0]]
    assert not commands


def test_historical_import_never_turns_stage_or_old_budget_into_labels(tmp_path):
    from mode_gate.factual_reconstruction import reconstruct_factual_labels
    from mode_gate.io_utils import AtomicJsonl
    rollout = tmp_path/'episode'
    rollout.mkdir()
    (rollout/'runtime_decision.json').write_text(json.dumps({'record_id':'r','round_id':1,'status':'EXECUTE',
        'stage_advanced':True,'remaining_budget':4}))
    plan = tmp_path/'plan.json'
    plan.write_text(json.dumps({'contexts':[{'record_id':'r','retry_budget':4,'remaining_budget':4}]}))
    ledger = AtomicJsonl(tmp_path/'episodes.jsonl')
    ledger.append({'event_id':'done','event':'EPISODE_COMPLETED','success':False,'output_dir':str(rollout)})
    result = reconstruct_factual_labels(incidents=tmp_path/'incidents',episodes=ledger.path,
        replay_plan=plan,output=tmp_path/'report.json',apply=True)
    assert result['labels_attached']==0 and result['fact_count']==1
    fact=result['facts'][0]['payload']
    assert fact['native_success'] is False and fact['original_context']['retry_budget']==4


def test_remedy_selection_inspects_evidence_and_does_not_require_text_similarity(tmp_path):
    from mode_gate.experience_planner import ExperiencePlanner
    from mode_gate.experiences import artifact_ref
    report = tmp_path/'measured.json'
    report.write_text(json.dumps({'old_policy':'p0','current_task_successes':8,'total':10}))
    ref = artifact_ref(report,kind='historical_evidence')
    remedy = {'signature_id':'historical','task_id':'another_task','delta_id':'d',
              'metadata':{'policy_gate_report_path':str(report)}, 'evidence_refs':[ref]}
    cmds = [('search',{'collection':'remedies','query':''}),
            ('read_evidence',{'path':str(report)}),
            ('select_remedy',{'signature_id':'historical','alpha_l_values':[.15,.7],
                'reason':'文字不同，但接触失败和补救能力相通','evidence_refs':[ref]})]
    class Client:
        def request(self,**kwargs):
            action,args = cmds.pop(0)
            return SimpleNamespace(text=json.dumps({'action':action,'arguments':args}),planner_metadata={'planner_thread_id':THREAD})
    out=ExperiencePlanner(IncidentMemory(tmp_path/'incidents'),client=Client()).run(
        purpose='remedy_lookup',current={'task_id':'new_task'},remedies=[remedy])
    assert out['remedy']['delta_id']=='d' and out['alpha_l_values']==[.8]
    assert out['merge_coefficient_selection']['selection_owner']=='user_configuration'
    assert out['history'][-1]['arguments']['alpha_l_values']==[.15,.7]
    assert out['planner_provenance']['planner_thread_id']==THREAD


def test_ticket_media_only_serves_hashed_real_evidence(tmp_path):
    from mode_gate.teleop import create_teleop_app
    from mode_gate.experiences import artifact_ref
    from fastapi.testclient import TestClient
    from PIL import Image
    path=tmp_path/'real.png'
    Image.fromarray(np.zeros((12,12,3),np.uint8)).save(path)
    ref=artifact_ref(path,kind='real_observation')
    session=SimpleNamespace(ui_context={'multimodal_evidence':{'images':[ref]},'visual_guidance':{'operation_steps_zh':['接近目标']}})
    with TestClient(create_teleop_app(session)) as client:
        data=client.get('/ticket/evidence').json()
        assert client.get('/ticket/media/'+ref['sha256']).status_code==200
        assert client.get('/ticket/media/'+'0'*64).status_code==404
