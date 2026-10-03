"""Complete Main method AST regressions; synthetic external services only."""
import ast,copy,hashlib,inspect,json,logging,os,time
from pathlib import Path
from types import MethodType,SimpleNamespace
from typing import Any,Dict
import numpy as np
import pytest,torch
from test_n30_executed_progress import _patch_core_imports,stub_adapter,setup_policy,cfg,runtime_cfg,eq
from test_rdt_steer import _StubRDTModel
ROOT=Path(__file__).resolve().parents[1]


def compile_main(old=False):
    source=(ROOT/'main.py').read_text();tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Main')
    methods=[copy.deepcopy(n) for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'_run_episode','_get_policy_observation'}]
    if old:
        pinned=json.loads((ROOT/'tests/n30_initial_observation_original.json').read_text())
        assert pinned['base_commit']=='4ce2b95757c1c0d662696ba19d6a9a14d2e59b49'
        methods=[ast.parse(pinned['method_source']).body[0] if n.name=='_run_episode' else n for n in methods]
    names={'_progress_continuation_context','_acknowledge_progress_continuation','_config_section_to_dict','_config_has_key',
        '_main_vls_config','_adapter_actual_task_id','_gripper_qpos_violation_count','_chunk_boundary_action_jump'}
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    constants=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in
        {'_LEGACY_MAIN_VLS_FIELDS','_GRIPPER_QPOS_MIN','_GRIPPER_QPOS_MAX','_GRIPPER_QPOS_TOLERANCE'} for t in n.targets)]
    tracker=ast.parse((ROOT/'core/keypoint_tracker.py').read_text())
    funcs += [n for n in tracker.body if isinstance(n,ast.FunctionDef) and n.name=='read_keypoints_with_passive_tracking']
    sample=ast.parse((ROOT/'core/policy_observation_sampling.py').read_text())
    funcs += [n for n in sample.body if isinstance(n,ast.FunctionDef) and n.name=='policy_observation_sample_num']
    ns={'Any':Any,'torch':torch,'np':np,'os':os,'time':time,'inspect':inspect,'Path':Path,'log':logging.getLogger('synthetic-main'),
        'add_text_to_image':lambda image,text:image,'append_jsonl':lambda path,row:None}
    wrapper=ast.ClassDef(name='Main',bases=[],keywords=[],body=methods,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=constants+funcs+[wrapper],type_ignores=[])),str(ROOT/'main.py'),'exec'),ns)
    return ns['Main'],ns


def adapter_methods():
    source=(ROOT/'core/env_adapters/libero_adapter.py').read_text();tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LiberoAdapter')
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'get_obs','get_policy_observation'}]
    ns={'torch':torch,'Dict':Dict}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Adapter',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])),str(ROOT/'core/env_adapters/libero_adapter.py'),'exec'),ns)
    return ns['Adapter']


def make_case(stub_adapter,monkeypatch,tmp_path,*,old=False,mode='N30',dtype=torch.float32,steps=17,gap=False,truncate=False):
    from core.rdt_policy_steer import RDTSteer
    from core.decision_evidence import DecisionEvidence
    policy=RDTSteer(rdt_model=_StubRDTModel(),num_inference_steps=5)
    provider=setup_policy(policy,stub_adapter,monkeypatch,dtype)
    provider._guidance_original_func.__code__=provider._guidance_original_func.__code__.replace(co_filename='<string>')
    file=tmp_path/'synthetic-provider.txt';file.write_text(provider._guidance_source_text);provider._guidance_source_path=str(file)
    encode=policy._rdt_model.encode_inputs
    def mask(*args):
        cond=encode(*args);cond['action_mask']=torch.zeros((1,1,128),dtype=dtype);cond['action_mask'][:,:,[10,39,40,41,42,43,44]]=1;return cond
    monkeypatch.setattr(policy._rdt_model,'encode_inputs',mask)
    class Recorder(DecisionEvidence):
        def flush(self):
            if not hasattr(self,'all_events'):self.all_events=[]
            self.all_events.extend(self._pending);self._pending=[]
    rec=Recorder(tmp_path/'recorder',episode=0)
    policy._decision_evidence=rec;stub_adapter._decision_evidence=rec
    state={'step':0,'cache_reads':0,'policy_reads':0,'steps':0,'renders':0,'reset_queries':0,'tracker_reads':0,'snapshots':0,'actions':[],'raw':[],'processed':[],'metrics':[]}
    def raw(step):
        eef=torch.tensor([[1.00000000000037-step/32.,.00000000000027,0.]],dtype=torch.float64)
        state['raw'].append(eef.clone())
        return {'observation.robot_state':{'eef':{'pos':eef}},'agentview_image':np.zeros((8,8,3),dtype=np.uint8),
            'robot0_eye_in_hand_image':np.zeros((8,8,3),dtype=np.uint8),'robot0_joint_pos':np.zeros(7,dtype=np.float32),
            'robot0_gripper_qpos':np.array([-.02,.02],dtype=np.float32)}
    stub_adapter._last_obs=raw(0);stub_adapter._env=[SimpleNamespace(task_description='synthetic task',task_id=0)];stub_adapter.current_task_idx=0
    real=adapter_methods()
    def get_obs(self):state['cache_reads']+=1;return real.get_obs(self)
    def get_policy(self,sample_num=1):state['policy_reads']+=1;return real.get_policy_observation(self,sample_num)
    stub_adapter.get_obs=MethodType(get_obs,stub_adapter);stub_adapter.get_policy_observation=MethodType(get_policy,stub_adapter)
    def preprocess(observation):
        removed=observation.pop('observation.robot_state');observation['observation.state']=removed['eef']['pos'].float()*777.+999.
        return observation
    stub_adapter.env_preprocessor=preprocess
    def forbidden(*a,**k):raise AssertionError('unapproved environment measurement/reset')
    stub_adapter.reset=forbidden;stub_adapter._get_raw_obs=forbidden;stub_adapter.get_ee_pose=forbidden
    def image():state['renders']+=1;return np.zeros((8,8,3),dtype=np.uint8)
    stub_adapter.get_vlm_image=image;stub_adapter.get_task_description=lambda:'synthetic task';stub_adapter.vlm_camera='synthetic'
    def step(action):
        state['actions'].append(action.clone());state['steps']+=1;state['step']+=1
        rec.record('executed_action',action_numpy=action.float())
        observation=raw(state['step']);terminal=state['step']==steps
        rec.pre_reset_outcome({'robot0_eef_pos':observation['observation.robot_state']['eef']['pos'][0]},reward=0.,terminated=terminal and not truncate,success=False)
        if terminal:
            # Real adapter may return reset observation; feedback must clear first.
            observation['observation.robot_state']['eef']['pos']=torch.full((1,3),99.,dtype=torch.float64)
        stub_adapter._last_obs=observation
        return observation,0.,terminal and not truncate,terminal and truncate,{'success':False,'behavior_name':'synthetic'}
    stub_adapter.step=step
    def positions():state['tracker_reads']+=1;return np.array([[.00000000000017,0.,0.],[.2,0.,0.]],dtype=np.float64)
    def snapshot():state['snapshots']+=1;return {'instance_id':7,'generation':1,'targets':{'0':{'valid':True,'status':'tracked'},'1':{'valid':True,'status':'tracked'}}}
    cls,ns=compile_main(old);app=cls();app.policy=policy;app.adapter=stub_adapter;app.policy_type='rdt';app.output_dir=str(tmp_path);app.success_count=0
    config=cfg() if mode=='N30' else json.loads((ROOT/'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())['profiles'][mode]['restored_profile']
    app.config={'guidance_type':'eds','use_guidance':True,'eds_config':config,'decision_evidence':{'enabled':True},
        'eds_mechanism_pretest':runtime_cfg(cfg())['mechanism_pretest'],'eds_eval':{'enabled':True,'write_metrics':True,'save_qualitative':False}}
    # Preserve production auxiliary scoring flags; suppress only synthetic trace persistence.
    app.config['eds_mechanism_pretest']={**app.config['eds_mechanism_pretest'],'max_chunks':0}
    app.guidance_fns={1:[provider]};app.keypoint_tracker=SimpleNamespace(get_keypoint_positions=positions,execution_feedback_tracking_snapshot=snapshot,get_mask_ids=lambda:None)
    def policy_process(observation):state['processed'].append(copy.deepcopy(observation));return observation
    app.policy_preprocessor=policy_process
    for name in ('_enable_phase_diagnostics','_enable_render_phase_diagnostics','_append_phase_timing','_append_episode_metadata','_append_safety_event'):
        setattr(app,name,lambda *a,**k:None)
    app._enable_decision_evidence=lambda ep:rec
    app._get_gripper_edge_values=lambda a:(None,None)
    app._get_gripper_value=lambda a,i:None
    def stage(s,*unused):
        updated=dict(s);updated['use_guidance']=not(gap and s['global_step']==8)
        if updated['use_guidance']!=s['use_guidance']:policy.reset_eds_chunk_memory('guidance_change')
        return updated
    app._update_stage=stage;app.video_recorder=SimpleNamespace(add_frame=lambda *a,**k:None,save_video=lambda **k:None)
    ns['append_jsonl']=lambda p,row:state['metrics'].append(copy.deepcopy(row))
    return app,policy,rec,state


def run(case):
    app,policy,rec,state=case;torch.manual_seed(3030);app._run_episode(0,app.output_dir,30)
    return {**state,'compute':policy.get_episode_compute_counters(),'rng':torch.random.get_rng_state(),'events':rec.all_events,'evidence_complete':rec.finished}


def test_original_full_method_reproduces_initial_unboundlocal(stub_adapter,monkeypatch,tmp_path):
    case=make_case(stub_adapter,monkeypatch,tmp_path,old=True)
    with pytest.raises(UnboundLocalError,match='obs'):run(case)
    assert case[3]['steps']==0 and case[3]['cache_reads']==0 and case[1].get_episode_compute_counters()['model_forward_calls']==0


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_full_run_episode_native_raw_context_and_two_prefixes(stub_adapter,monkeypatch,tmp_path,dtype):
    from scripts.qd_ed_n30_native import audit_events,compute_check
    case=make_case(stub_adapter,monkeypatch,tmp_path,dtype=dtype);out=run(case)
    packets=[e['values']['packet'] for e in out['events'] if e['event']=='n30_observation_context']
    assert len(packets)==3
    for packet,step in zip(packets,[0,8,16]):
        assert packet['start_eef'].dtype==torch.float64 and eq(packet['start_eef'],out['raw'][step].reshape(3))
        assert packet['keypoints'].dtype==torch.float64
    assert all('observation.robot_state' not in p for p in out['processed'])
    assert out['processed'][0]['observation.state'].dtype==torch.float32 and out['processed'][0]['observation.state'][0,0]>1000
    assert out['cache_reads']==1 and out['policy_reads']==18 and out['steps']==out['renders']==17
    assert out['tracker_reads']==out['snapshots']==3 and out['reset_queries']==0 and out['evidence_complete']
    compute={**out['compute'],'policy_counters_available':True};compute_check(compute,3)
    gate=audit_events('N30',out['metrics'],out['events'],compute)
    assert gate['active_insertions_verified']==2 and gate['completed_prefixes_verified']==2 and gate['actual_acknowledgments_verified']==17
    assert case[1]._executed_progress.pending is None and case[1]._executed_progress.completed is None
    assert case[1]._executed_progress.reason=='terminal_or_truncated'


@pytest.mark.parametrize('truncate',[False,True])
def test_full_method_guidance_gap_and_terminal_clear(stub_adapter,monkeypatch,tmp_path,truncate):
    from scripts.qd_ed_n30_native import audit_events,compute_check
    case=make_case(stub_adapter,monkeypatch,tmp_path,steps=24,gap=True,truncate=truncate);out=run(case)
    compute={**out['compute'],'policy_counters_available':True};compute_check(compute,2)
    gate=audit_events('N30',out['metrics'],out['events'],compute)
    assert gate['active_insertions_verified']==0 and gate['guided_decisions']==2 and gate['completed_prefixes_verified']==1
    assert out['cache_reads']==1 and out['policy_reads']==25 and out['steps']==24 and out['tracker_reads']==3
    assert case[1]._executed_progress.pending is None and case[1]._executed_progress.completed is None


@pytest.mark.parametrize('mode',['C0','Q0'])
def test_default_off_complete_loop_matches_original(stub_adapter,monkeypatch,tmp_path,mode):
    outputs=[]
    for old in (True,False):
        folder=tmp_path/str(old);folder.mkdir();outputs.append(run(make_case(stub_adapter,monkeypatch,folder,old=old,mode=mode,steps=16)))
    a,b=outputs
    assert all(eq(x,y) for x,y in zip(a['actions'],b['actions'])) and eq(a['rng'].float(),b['rng'].float())
    assert a['compute']==b['compute'] and a['steps']==b['steps']==16 and a['cache_reads']==b['cache_reads']==0
    assert a['policy_reads']==b['policy_reads']==17 and a['tracker_reads']==b['tracker_reads']==2 and a['renders']==b['renders']==16
    assert not any(e['event'].startswith('n30_') for e in b['events'])
