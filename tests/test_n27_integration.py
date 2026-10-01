"""N27 actual caller/config/evidence synthetic coverage, zero real model/runtime."""
import copy,json
from pathlib import Path
from types import SimpleNamespace
import pytest,torch
from test_rdt_steer import _patch_core_imports,stub_steer,stub_adapter,_rollout_cond,_n2_fixture_provider
from test_n25_clipped_rbf import native_adapter,input_tensor,config
from test_n26_clean_output_rbf import layout,invoke,bytes_equal
ROOT=Path(__file__).resolve().parents[1]


def test_real_expansion_resolution_and_exact_overrides(stub_steer):
    from scripts import qd_ed_final_runner as r
    baseline=json.loads((ROOT/'configs/qd_ed_final/baseline_profiles.json').read_text())['profiles']['Q0']
    old=json.loads((ROOT/'configs/qd_ed_final/candidate_n26.json').read_text())
    new=json.loads((ROOT/'configs/qd_ed_final/candidate_n27.json').read_text())
    a=r.expand_candidate('N26',old,baseline);b=r.expand_candidate('N27',new,baseline)
    assert b['resolved_eds_config']=={**a['resolved_eds_config'],'diversity_update_mode':'feasible_ray_v1'}
    cfg=stub_steer._resolve_eds_config_with_reference_defaults(b['resolved_eds_config'])
    assert cfg.diversity_update_mode=='feasible_ray_v1' and cfg.population_size==16 and cfg.cem_iters==10
    assert set(b['hydra_overrides'])==set(a['hydra_overrides'])|{'main.eds_config.diversity_update_mode=feasible_ray_v1'}
    assert config(stub_steer,'N26').diversity_update_mode=='legacy_additive'


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('noncontiguous',[False,True,'model_slice'])
@pytest.mark.parametrize('phase',['initial','rollout'])
@pytest.mark.parametrize('mode',['N26','N27'])
def test_actual_same_forward_assignment_order_mask(stub_steer,stub_adapter,monkeypatch,dtype,noncontiguous,phase,mode):
    from scripts.qd_ed_n27_reference import reconstruct_update
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    cfg=config(stub_steer,mode);cond=_rollout_cond(stub_steer)
    monkeypatch.setattr(stub_steer,'_eds_score_population_as_cost',lambda values,**kw:(torch.zeros(16,dtype=dtype),{}))
    scheduler=stub_steer._noise_scheduler;scheduler.config={'prediction_type':'sample'}
    trace=[];current={};original_step=scheduler.step;parameter=torch.nn.Parameter(torch.ones((),dtype=dtype))
    def forward(x,t,cond):
        assert not torch.is_grad_enabled()
        out=layout(input_tensor(dtype,16)*parameter,noncontiguous)
        current.update(out=out,before=out.clone(),gradient=None);trace.append('F');return out
    monkeypatch.setattr(stub_steer._rdt_model.dit,'forward',forward)
    original=stub_steer._compute_eds_diversity_gradient
    def gradient(arg,**kw):
        assert arg is current['out'] and bytes_equal(arg,current['before'])
        g,e=original(arg,**kw);current['gradient']=g;trace.append('G');return g,e
    monkeypatch.setattr(stub_steer,'_compute_eds_diversity_gradient',gradient)
    def step(out,t,x):
        expected=current['before'].clone();g=current['gradient']
        if g is not None:
            if mode=='N27':expected[:,:8,[39,40,41]]=reconstruct_update(expected[:,:8,[39,40,41]],-20.*g[:,:8,[39,40,41]])[0]
            else:expected[:,:,[39,40,41]]+=-20.*g[:,:,[39,40,41]]
        assert out is current['out'] and bytes_equal(out,expected)
        trace.append('S');return original_step(out,t,x)
    monkeypatch.setattr(scheduler,'step',step)
    invoke(stub_steer,phase,input_tensor(dtype,16),cond,cfg)
    assert ''.join(trace)==('FGS'*(4 if phase=='initial' else 2)+'FS')
    assert parameter.grad is None
    counters=stub_steer.get_episode_compute_counters()
    assert counters['model_forward_calls']==(5 if phase=='initial' else 3)
    assert counters['rbf_gradient_calls']==(4 if phase=='initial' else 2)


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_full_search_native_serializer_witness_instrumentation_parity(stub_steer,stub_adapter,monkeypatch,tmp_path,dtype):
    from core.decision_evidence import DecisionEvidence
    from scripts import qd_ed_n27_native as n
    from scripts.qd_ed_audit_backend import create_backend
    from test_qd_actuator_clipped_quality import static_adapter_fixture
    for name,value in vars(static_adapter_fixture()).items():monkeypatch.setattr(stub_adapter,name,value,raising=False)
    origins=native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    stub_steer._noise_scheduler.config={'prediction_type':'sample'}
    monkeypatch.setattr(stub_steer._rdt_model.dit,'forward',lambda *a:layout(input_tensor(dtype,16),'model_slice'))
    points=torch.tensor([[.1124,-.071,.3154],[.13,-.21,.39]],dtype=dtype);provider=_n2_fixture_provider(index=0);runs=[]
    for instrumented in (False,True):
        stub_steer.reset();torch.manual_seed(2727);origins.clear();saved=[]
        recorder=DecisionEvidence(tmp_path/'synthetic',episode=0) if instrumented else None
        if recorder:
            original_record=recorder.record
            def record(event,**values):
                if event.startswith('n27_rbf'):saved.append((event,values))
                return original_record(event,**values)
            monkeypatch.setattr(recorder,'record',record)
            recorder.begin_decision(global_step=24,stage=1,use_guidance=True,keypoints=points,providers=[provider])
        stub_steer._decision_evidence=recorder
        selected=stub_steer._eds_guided_denoise_loop(x_t=input_tensor(dtype,16),cond=_rollout_cond(stub_steer),keypoints=points,
            guidance_fns=[provider],eds_config=config(stub_steer,'N27'),verbose=False,global_step=24,current_stage=1)
        metrics=stub_steer.get_last_eds_metrics();metrics['global_step']=24;json.dumps(metrics,allow_nan=False);rows=n.call_rows(metrics)
        assert len(rows)==19 and metrics['search_evaluation_count']==176 and metrics['score_call_count']==11
        assert metrics['resample_count']==metrics['renoise_count']==metrics['rollout_count']==10
        counters=stub_steer.get_episode_compute_counters();assert counters['model_forward_calls']==21 and counters['rbf_gradient_calls']==19
        if recorder:
            witnesses=[v for k,v in saved if k=='n27_rbf_witness'];coverage=[v for k,v in saved if k=='n27_rbf_witness_coverage']
            assert len(witnesses)==11 and len(coverage)==1 and coverage[0]['missing_slots']==[]
            backend=create_backend('cpu')
            for v in witnesses:
                assert n.audit_witness(v['tensors'],v['metadata'],backend)['feasible_ray_verified']
                for fault in ('alpha','schema','update_operand_semantics'):
                    bad=copy.deepcopy(v);bad['metadata']['call'][fault]=[0.]*16 if fault=='alpha' else 'wrong'
                    with pytest.raises(ValueError):n.audit_witness(bad['tensors'],bad['metadata'],backend)
            assert coverage[0]['numeric_bytes']<=220*1024
            assert all(len(json.dumps(v['metadata']).encode())<=16*1024 for v in witnesses)
        runs.append((selected.clone(),counters,torch.random.get_rng_state().clone(),len(origins)))
    assert bytes_equal(runs[0][0],runs[1][0]) and runs[0][1]==runs[1][1] and torch.equal(runs[0][2],runs[1][2]) and runs[0][3]==runs[1][3]


def test_native_zero_guided_requires_profile_gate(tmp_path):
    from scripts import qd_ed_n27_native as n
    report={'accepted':True,'evidence_complete':True,'observed_counts':{'canonical_candidate_batch':0}}
    with pytest.raises(ValueError):n.counts('N27',[],report,0)
    gate=n.audit_events('N27',[],[],{'guided_chunks':0,'rbf_gradient_calls':0,'rbf_gradient_batch_rows':0},None)
    report[n.GATE]=gate
    counts,_=n.counts('N27',[],report,0);assert counts['guided_decisions']==0
    for arm in ('C0','Q0','N26'):
        with pytest.raises(ValueError):n.counts(arm,[],report,0)


def test_exact_n27_build_command_carries_codex_e2_and_update(tmp_path):
    from scripts import qd_ed_final_runner as r
    baseline=json.loads((ROOT/'configs/qd_ed_final/baseline_profiles.json').read_text())['profiles']['Q0']
    candidate=json.loads((ROOT/'configs/qd_ed_final/candidate_n27.json').read_text())
    profile=r.expand_candidate('N27',candidate,baseline)
    frozen={'backend':'codex_cli','model':'gpt-6-astra','auth_mode':'chatgpt','reasoning_effort':'low','timeout_seconds':180,
        'cli_path':str(tmp_path/'codex'),'cli_version':'0.155.1','cli_sha256':'a'*64,'disabled_skill_paths':[str(tmp_path/'disabled')],
        'allow_recovered_error_events':True}
    frozen['public_config_sha256']=r.codex_public_config_sha256(frozen)
    runtime={'frozen_stage_provider':frozen,'stage_engineering_condition':r.n4e1_support().engineering_condition(),
        'stage_recovered_error_condition':r.E2_STAGE_CONDITION,'tasks':{'0':{'cache_dir':str(tmp_path/'cache')}},
        'main_overrides':['+main.require_task_cache_identity=true']}
    plan={'worktree':str(ROOT),'artifact_root':str(tmp_path),'candidate_profiles':{'N26':{},'N27':{}},'n27_cohort':{}}
    row={'profile':'N27','task_id':0,'policy_seed':24,'env_seed':25}
    cmd,out=r.build_command(plan,{'profiles':{'N27':profile}},runtime,row,'synthetic-command')
    assert 'main.eds_config.diversity_update_mode=feasible_ray_v1' in cmd
    assert 'perception.gemini.backend=codex_cli' in cmd and runtime['frozen_stage_provider']['auth_mode']=='chatgpt'
    assert not any(x.startswith('perception.gemini.auth_mode=') for x in cmd)
    bad=copy.deepcopy(runtime);bad['frozen_stage_provider']['auth_mode']='api'
    with pytest.raises(r.GateError):r.stage_overrides(bad)
    assert 'perception.gemini.timeout_seconds=180' in cmd and 'perception.gemini.model=gpt-6-astra' in cmd
    assert not any('api_key' in x or 'base_url' in x for x in cmd)
    assert out==tmp_path/'attempts/synthetic-command'
