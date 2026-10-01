import ast, copy, hashlib, json, os

from pathlib import Path

from types import MethodType, SimpleNamespace

import pytest, torch

from test_rdt_steer import _patch_core_imports, stub_steer, stub_adapter, _rollout_cond, _n2_fixture_provider

from test_n25_clipped_rbf import native_adapter, input_tensor, config

from test_n26_clean_output_rbf import layout, bytes_equal

ROOT = Path(__file__).resolve().parents[1]

def setup(steer, adapter, monkeypatch):
    origins = native_adapter(adapter, monkeypatch)
    steer.post_init(adapter=adapter, postprocessor=lambda x:x, sample_batch_size=16,
                    policy_config={'action_chunk_horizon':8})
    steer._noise_scheduler.config={'prediction_type':'sample'}
    return origins

def base_methods(steer):
    """Actual base52 source functions, compiled only for a synthetic old-path comparison."""
    source=Path(os.environ['N29_BASE_POLICY']).read_text();tree=ast.parse(source)
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='RDTSteer')
    names={'_eds_initial_denoise_rbf_diverse','_eds_guided_denoise_loop','_eds_rbf_witness','_eds_renoise_reference'}
    import core.rdt_policy_steer as module
    scope=dict(vars(module));nodes=[x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name in names]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'base52_synthetic_original_methods','exec'),scope)
    return {name:MethodType(scope[name],steer) for name in names}

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_full_loop_original_parity_n29_allocation_order_witness(stub_steer,stub_adapter,monkeypatch,tmp_path,dtype):
    from core.decision_evidence import DecisionEvidence
    from test_qd_actuator_clipped_quality import static_adapter_fixture
    import core.rdt_policy_steer as policy
    for k,v in vars(static_adapter_fixture()).items():monkeypatch.setattr(stub_adapter,k,v,raising=False)
    origins=setup(stub_steer,stub_adapter,monkeypatch)
    monkeypatch.setattr(stub_steer._rdt_model.dit,'forward',lambda *a:layout(input_tensor(dtype,16),'model_slice'))
    points=torch.tensor([[.1124,-.071,.3154],[.13,-.21,.39]],dtype=dtype);provider=_n2_fixture_provider(index=0)
    old_methods=base_methods(stub_steer);new_methods={n:getattr(stub_steer,n) for n in old_methods}
    original_mutate=policy.mutate_trust_parent;original_renoise=stub_steer._eds_renoise_reference
    original_rollout=stub_steer._eds_rollout_rbf_diverse_reference;original_step=stub_steer._noise_scheduler.step
    runs={};order=[];pending={};denoise=[]
    def mutate(x,**kw):
        order.append(('P',kw['iteration']));before=x.clone();rng=torch.random.get_rng_state().clone()
        evidence=original_mutate(x,**kw);pending.update(before=before,after=x.clone(),sequence=kw['parent_allocation_sequence'])
        assert torch.equal(rng,torch.random.get_rng_state());return evidence
    def renoise(x,n):
        order.append(('N',n))
        if pending:assert bytes_equal(x,pending['after'])
        return original_renoise(x,n)
    def rollout(**kw):
        order.append(('D',kw['n_trunc_steps']));return original_rollout(**kw)
    def step(out,t,x):denoise.append((int(t),tuple(out.shape)));return original_step(out,t,x)
    monkeypatch.setattr(policy,'mutate_trust_parent',mutate)
    monkeypatch.setattr(stub_steer,'_eds_renoise_reference',renoise)
    monkeypatch.setattr(stub_steer,'_eds_rollout_rbf_diverse_reference',rollout)
    monkeypatch.setattr(stub_steer._noise_scheduler,'step',step)
    for mode,recording,baseline in [('N28',False,True),('N28',False,False),('N29',False,False),('N29',True,False)]:
        for n,m in (old_methods if baseline else new_methods).items():
            if n!='_eds_renoise_reference':monkeypatch.setattr(stub_steer,n,m)
        original_renoise=(old_methods if baseline else new_methods)['_eds_renoise_reference']
        stub_steer.reset();torch.manual_seed(2828);origins.clear();order.clear();pending.clear();denoise.clear();saved=[]
        rec=DecisionEvidence(tmp_path/'synthetic',episode=0) if recording else None
        if rec:
            record=rec.record
            def capture(event,**values):
                if event.startswith('n29_rbf') or event=='parent_allocation':saved.append((event,copy.deepcopy(values)))
                return record(event,**values)
            monkeypatch.setattr(rec,'record',capture)
            rec.begin_decision(global_step=24,stage=1,use_guidance=True,keypoints=points,providers=[provider])
        stub_steer._decision_evidence=rec
        monkeypatch.setattr(stub_adapter,'_decision_evidence',rec,raising=False)
        selected=stub_steer._eds_guided_denoise_loop(x_t=input_tensor(dtype,16),cond=_rollout_cond(stub_steer),keypoints=points,
            guidance_fns=[provider],eds_config=config(stub_steer,mode),verbose=False,global_step=24,current_stage=1)
        m=stub_steer.get_last_eds_metrics();json.dumps(m,allow_nan=False);c=stub_steer.get_episode_compute_counters()
        assert m['search_evaluation_count']==176 and m['score_call_count']==11
        assert m['resample_count']==m['renoise_count']==m['rollout_count']==10
        assert c['model_forward_calls']==21 and c['rbf_gradient_calls']==14
        nsteps=[3,2,2,2,2,1,1,1,1,1]
        assert [n for k,n in order if k=='N']==nsteps and [n for k,n in order if k=='D']==nsteps
        expected=[(t,(16,64,128)) for t in range(4,-1,-1)]+[(t,(16,64,128)) for n in nsteps for t in range(n-1,-1,-1)]
        assert denoise==expected
        if mode=='N29':
            assert order==[event for i,n in enumerate(nsteps) for event in [('P',i),('N',n),('D',n)]]
            assert len(m['initial_direction_rbf_evidence_by_step'])==4
            calls=m['rollout_direction_rbf_evidence_by_iter'];assert len(calls)==10 and all(len(x)==1 for x in calls)
            assert [x[0]['iteration'] for x in calls]==list(range(10))
            assert all(x[0]['phase']=='parent' and x[0]['denoising_step'] is None for x in calls)
            assert all(x['input_binding']=='same_forward_unmodified_model_output' for x in m['initial_direction_rbf_evidence_by_step'])
            if rec:
                from scripts import qd_ed_n29_native as native
                from scripts.qd_ed_audit_backend import create_backend
                metrics={**m,'global_step':24}; compute={**c,'guided_chunks':1}
                gate=native.audit_events('N29',[metrics],rec._pending,compute,create_backend('cpu'))
                assert gate['witness_calls_verified']==11 and gate['parent_boundaries_verified']==10
                witness=[v for k,v in saved if k=='n29_rbf_witness'];coverage=[v for k,v in saved if k=='n29_rbf_witness_coverage']
                assert len(witness)==11 and len(coverage)==1 and coverage[0]['missing_slots']==[]
                assert coverage[0]['numeric_bytes']<=220*1024
                parents=[v for k,v in saved if k=='parent_allocation'];assert len(parents)==10
                for i,v in enumerate(witness[1:]):
                    md=v['metadata'];ts=v['tensors'];a=parents[i]
                    assert md['call']['phase']=='parent' and type(md['call']['parent_allocation_sequence']) is int
                    assert bytes_equal(ts['input_xyz'],ts['parent_offspring_before'])
                    assert bytes_equal(ts['input_xyz'],a['source_population'].index_select(0,a['parent_indices'])[:,:8,[39,40,41]])
                    assert 'model_output_before' not in ts and len(json.dumps(md).encode())<=16*1024
                assert 'model_output_before' in witness[0]['tensors']
                assert stub_steer._n29_rbf_witness.prepare('parent',0) is None
        key=(mode,recording,baseline);runs[key]=(selected.clone(),c,torch.random.get_rng_state().clone(),len(origins))
    for a,b in [(('N28',False,True),('N28',False,False)),(('N29',False,False),('N29',True,False))]:
        x,y=runs[a],runs[b];assert bytes_equal(x[0],y[0]) and x[1]==y[1] and torch.equal(x[2],y[2]) and x[3]==y[3]
    assert torch.equal(runs[('N28',False,False)][2],runs[('N29',False,False)][2])


def test_config_only_delta_and_incompatible_routes(stub_steer):
    a=json.loads((ROOT/'configs/qd_ed_final/candidate_n28.json').read_text())
    b=json.loads((ROOT/'configs/qd_ed_final/candidate_n29.json').read_text())
    assert b['profile']==a['profile']|{'diversity_update_mode':'population_relative_trust_v1'}
    assert b['parent_candidate']['sha256']==hashlib.sha256((ROOT/'configs/qd_ed_final/candidate_n28.json').read_bytes()).hexdigest()
    cfg=stub_steer._resolve_eds_config_with_reference_defaults(b['profile'])
    assert cfg.diversity_update_mode=='population_relative_trust_v1'
    for delta in ({'rollout_diversity_placement':'model_output'},{'rollout_diversity_control_mode':'adaptive_target_band'},
        {'rollout_diversity_scale':21.},{'diversity_input_source':'noisy_sample'},{'num_elites':15}):
        with pytest.raises(ValueError):stub_steer._resolve_eds_config_with_reference_defaults(b['profile']|delta)
