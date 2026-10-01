"""Synthetic N26 caller, independent geometry and evidence checks; no runtime."""
import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from test_rdt_steer import (_patch_core_imports, stub_steer, stub_adapter,
                            _rollout_cond, _n2_fixture_provider)
from test_n25_clipped_rbf import native_adapter, config, input_tensor

ROOT = Path(__file__).resolve().parents[1]


def bytes_equal(a, b):
    return (a.dtype == b.dtype and a.shape == b.shape and
            torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8)))


def independent_reference(values):
    """Independent leaf/where derivative, pure per-row cumulative projection.

    No production clip/helper/projector call; native dtype/operation ordering.
    This is a CPU expression check, not a claim about CUDA reduction parity.
    """
    leaf = values.detach().requires_grad_(True)
    xyz = leaf[:, :8, [39, 40, 41]]
    interior = (xyz > -1) & (xyz < 1)
    clipped = torch.where(interior, xyz, xyz.detach().clamp(-1, 1))
    origin = torch.tensor([.12317, -.17312, .23141], dtype=values.dtype)
    paths = torch.stack([origin + (row * .01).cumsum(0) for row in clipped])
    flat = paths.reshape(len(values), -1)
    pair = flat[:, None, :] - flat[None, :, :]
    distance = (pair.square().sum(-1) + 1e-6).sqrt()
    mask = (~torch.eye(len(values), dtype=torch.bool)).float()
    potential = ((1.0 / (distance + 1e-6)) * mask).sum()
    gradient = torch.autograd.grad(potential, leaf)[0]
    norm = torch.norm(gradient).item()
    return gradient / (norm + 1e-8) if norm > 1e-8 else gradient


def layout(values, noncontiguous):
    if noncontiguous == 'model_slice':
        backing=torch.zeros(len(values),67,128,dtype=values.dtype)
        output=backing[:,-64:]
        output.copy_(values)
        assert output.stride()==(8576,128,1) and output.storage_offset()==384
        return output
    return values.transpose(1, 2).contiguous().transpose(1, 2) if noncontiguous else values


@pytest.mark.parametrize('dtype', [torch.float32, torch.bfloat16])
@pytest.mark.parametrize('noncontiguous', [False, True, 'model_slice'])
@pytest.mark.parametrize('case', ['interior', 'boundary', 'saturated', 'coincident', 'mixed'])
def test_independent_clean_geometry(stub_steer, stub_adapter, monkeypatch, dtype, noncontiguous, case):
    from core.qd_clean_output_rbf import geometry_input
    origins = native_adapter(stub_adapter, monkeypatch)
    stub_steer.post_init(adapter=stub_adapter, postprocessor=lambda x:x, sample_batch_size=16,
                         policy_config={'action_chunk_horizon':8})
    values = input_tensor(dtype, 16)
    if case == 'boundary': values[:, :8, 39:42] = torch.tensor([-1., 1.], dtype=dtype).repeat(8)[:, None, None]
    if case == 'saturated': values[:, :8, 39:42] = 2
    if case == 'coincident': values[:, :8, 39:42] = .25
    if case == 'mixed': values[0, :8, 39:42] = 2; values[1, :8, 39] = -1
    values = layout(values, noncontiguous)
    original = values.clone(); rng = torch.random.get_rng_state().clone()
    cfg = config(stub_steer, 'N26')
    scheduler = SimpleNamespace(config={'prediction_type':'sample'})
    argument = geometry_input(torch.zeros_like(values), values, cfg, scheduler)
    assert argument is values and argument.stride() == values.stride()
    gradient, e = stub_steer._compute_eds_diversity_gradient(argument,
        descriptor_mode=cfg.initial_diversity_descriptor_mode, descriptor_cfg=cfg.__dict__)
    reference = independent_reference(values)
    assert bytes_equal(gradient, reference)
    assert bytes_equal(values, original) and torch.equal(rng, torch.random.get_rng_state())
    assert len(origins) == 16
    assert e['translation_components'] == 384
    assert e['input_stride'] == list(values.stride())
    if case in {'boundary', 'saturated', 'coincident'}:
        assert e['zero_gradient'] and not torch.count_nonzero(gradient)


def test_profile_and_default_closed_options(stub_steer):
    from core.qd_clean_output_rbf import geometry_input, require_sample_scheduler
    a = json.loads((ROOT/'configs/qd_ed_final/candidate_n25.json').read_text())
    b = json.loads((ROOT/'configs/qd_ed_final/candidate_n26.json').read_text())
    assert b['parent_candidate']['sha256'] == hashlib.sha256((ROOT/'configs/qd_ed_final/candidate_n25.json').read_bytes()).hexdigest()
    assert {k for k in a['profile'].keys() | b['profile'].keys() if a['profile'].get(k) != b['profile'].get(k)} == {'diversity_input_source'}
    default = config(stub_steer); new = config(stub_steer, 'N26')
    assert default.diversity_input_source == 'noisy_sample'
    assert new.qd_gripper_rescue_mode == 'none'
    x, out = object(), object()
    for scheduler in (None, SimpleNamespace(), SimpleNamespace(config={'prediction_type':'epsilon'})):
        require_sample_scheduler(default, scheduler)
        assert geometry_input(x, out, default, scheduler) is x
        with pytest.raises(ValueError, match='actual scheduler'):
            require_sample_scheduler(new, scheduler)
    for config_value in ({'prediction_type':'sample'}, SimpleNamespace(prediction_type='sample')):
        assert geometry_input(x, out, new, SimpleNamespace(config=config_value)) is out
    for change in ({'diversity_input_source':'bad'}, {'diversity_input_source':None},
                   {'use_initial_cache':True}, {'initial_population_cache':'synthetic-forbidden'}, {'ed_population_cache':'synthetic-forbidden'}, {'save_initial_cache':True},
                   {'save_ed_cache':True}, {'initial_diversity_descriptor_mode':'absolute_eef'},
                   {'rollout_diversity_descriptor_mode':'absolute_eef'}, {'initial_sampling_mode':'iid'},
                   {'truncated_rollout_mode':'baseline'}):
        with pytest.raises(ValueError):
            stub_steer._resolve_eds_config_with_reference_defaults({**b['profile'], **change})


def invoke(steer, phase, x, cond, cfg):
    if phase == 'initial':
        return steer._eds_initial_denoise_rbf_diverse(x_t=x, cond=cond, cfg=cfg)
    return steer._eds_rollout_rbf_diverse_reference(cond=cond, action_mask=cond['action_mask'],
        noisy_action=x, keypoints=torch.zeros(1,3), guidance_fns=[], n_trunc_steps=3,
        cfg=cfg, iter_idx=0, reward_mode='normal', shuffle_seed=0)


@pytest.mark.parametrize('dtype', [torch.float32, torch.bfloat16])
@pytest.mark.parametrize('noncontiguous', [False, True, 'model_slice'])
@pytest.mark.parametrize('phase', ['initial', 'rollout'])
def test_same_forward_unmodified_output_order_sign_mask_and_no_model_backward(
        stub_steer, stub_adapter, monkeypatch, dtype, noncontiguous, phase):
    origins = native_adapter(stub_adapter, monkeypatch)
    stub_steer.post_init(adapter=stub_adapter, postprocessor=lambda x:x, sample_batch_size=16,
                         policy_config={'action_chunk_horizon':8})
    cfg = config(stub_steer, 'N26'); cond = _rollout_cond(stub_steer)
    monkeypatch.setattr(stub_steer,'_eds_score_population_as_cost',lambda values,**kw:(torch.zeros(16,dtype=dtype),{}))
    scheduler = stub_steer._noise_scheduler
    scheduler.config = SimpleNamespace(prediction_type='sample')
    trace = []; current = {}; model_parameter = torch.nn.Parameter(torch.ones((), dtype=dtype))
    outputs = []; original_step = scheduler.step
    def forward(x, t, cond):
        assert not torch.is_grad_enabled()
        out = layout(input_tensor(dtype, 16) * model_parameter, noncontiguous)
        current.update(output=out, before=out.clone(), gradient=None, noisy=x)
        assert out is not x and out.grad_fn is None
        outputs.append(out); trace.append('forward'); return out
    monkeypatch.setattr(stub_steer._rdt_model.dit, 'forward', forward)
    original_gradient = stub_steer._compute_eds_diversity_gradient
    def gradient(argument, **kw):
        assert argument is current['output'] and argument is not current['noisy']
        assert bytes_equal(argument, current['before'])
        assert argument.stride() == current['output'].stride()
        result, e = original_gradient(argument, **kw)
        current['gradient'] = result; trace.append('rbf'); return result, e
    monkeypatch.setattr(stub_steer, '_compute_eds_diversity_gradient', gradient)
    def step(out, t, x):
        assert out is current['output']
        expected = current['before'].clone()
        if current['gradient'] is not None:
            expected[:, :, [39,40,41]] += -20.0 * current['gradient'][:, :, [39,40,41]]
        assert bytes_equal(out, expected)
        assert out.stride() == outputs[-1].stride()
        trace.append('step'); return original_step(out, t, x)
    monkeypatch.setattr(scheduler, 'step', step)
    invoke(stub_steer, phase, input_tensor(dtype,16), cond, cfg)
    expected_forwards, expected_rbf = (5,4) if phase == 'initial' else (3,2)
    assert trace.count('forward') == trace.count('step') == expected_forwards
    assert trace.count('rbf') == expected_rbf
    assert ''.join({'forward':'F','rbf':'G','step':'S'}[x] for x in trace) == ('FGS'*expected_rbf+'FS')
    assert model_parameter.grad is None
    counters = stub_steer.get_episode_compute_counters()
    assert counters['model_forward_calls'] == expected_forwards
    assert counters['rbf_gradient_calls'] == expected_rbf
    # Rollout also scores/spread-projects; production helper itself had exactly16 reads/call.
    assert len(origins) >= expected_rbf * 16


@pytest.mark.parametrize('phase', ['initial', 'rollout'])
@pytest.mark.parametrize('prediction', [None, 'epsilon', 'v_prediction'])
def test_actual_scheduler_gate_before_forward(stub_steer, monkeypatch, phase, prediction):
    stub_steer._noise_scheduler.config = SimpleNamespace(prediction_type=prediction)
    monkeypatch.setattr(stub_steer, '_counted_dit', lambda *a:pytest.fail('forward before sample gate'))
    with pytest.raises(ValueError, match='actual scheduler'):
        invoke(stub_steer, phase, input_tensor(torch.float32,16), _rollout_cond(stub_steer), config(stub_steer,'N26'))


@pytest.mark.parametrize('dtype', [torch.float32, torch.bfloat16])
def test_full_search_witness_serializer_counts_default_parity(stub_steer, stub_adapter, monkeypatch, tmp_path, dtype):
    from core.decision_evidence import DecisionEvidence
    from test_qd_actuator_clipped_quality import static_adapter_fixture
    for name,value in vars(static_adapter_fixture()).items(): monkeypatch.setattr(stub_adapter,name,value,raising=False)
    origins = native_adapter(stub_adapter, monkeypatch)
    stub_steer.post_init(adapter=stub_adapter, postprocessor=lambda x:x, sample_batch_size=16,
                         policy_config={'action_chunk_horizon':8})
    stub_steer._noise_scheduler.config = {'prediction_type':'sample'}
    # Nonzero, noncontiguous estimate; model construction itself remains synthetic.
    monkeypatch.setattr(stub_steer._rdt_model.dit, 'forward',
        lambda *a:layout(input_tensor(dtype,16),True))
    points = torch.tensor([[.1124,-.071,.3154],[.13,-.21,.39]],dtype=dtype)
    provider = _n2_fixture_provider(index=0)
    runs = []
    for mode, instrumented in [('N25',False), ('N25-explicit-default',False), ('N26',False), ('N26',True)]:
        stub_steer.reset(); torch.manual_seed(2626); origins.clear(); events=[]
        recorder = DecisionEvidence(tmp_path/'synthetic',episode=0) if instrumented else None
        if recorder:
            original_record=recorder.record
            def record(name,**values):
                if name.startswith('n26_rbf') or name.startswith('n25_rbf'):events.append((name,values))
                return original_record(name,**values)
            monkeypatch.setattr(recorder,'record',record)
            recorder.begin_decision(global_step=24,stage=1,use_guidance=True,keypoints=points,providers=[provider])
        stub_steer._decision_evidence = recorder
        profile = json.loads((ROOT/f'configs/qd_ed_final/candidate_{"n26" if mode=="N26" else "n25"}.json').read_text())['profile']
        if mode == 'N25-explicit-default': profile['diversity_input_source']='noisy_sample'
        cfg = stub_steer._resolve_eds_config_with_reference_defaults(profile)
        selected = stub_steer._eds_guided_denoise_loop(x_t=input_tensor(dtype,16),cond=_rollout_cond(stub_steer),
            keypoints=points,guidance_fns=[provider],eds_config=cfg,verbose=False,global_step=24,current_stage=1)
        metrics = stub_steer.get_last_eds_metrics(); json.dumps(metrics,allow_nan=False)
        counter = stub_steer.get_episode_compute_counters()
        assert metrics['search_evaluation_count']==176 and metrics['score_call_count']==11
        assert counter['model_forward_calls']==21 and counter['rbf_gradient_calls']==19
        assert metrics['resample_count']==metrics['renoise_count']==metrics['rollout_count']==10
        groups = [metrics['initial_direction_rbf_evidence_by_step'],*metrics['rollout_direction_rbf_evidence_by_iter']]
        rows = [row for group in groups for row in group]
        assert len(rows)==19
        for row in rows:
            assert row['translation_components']==384 and row['input_dtype']==str(dtype)
            assert row['update_operand_is_measured_output_delta'] is False
            if mode=='N26':
                assert row['schema']=='n26-rbf-call-summary-v1' and row['prediction_type']=='sample'
                assert row['input_source']=='model_output_sample_v1' and row['model_jacobian_used'] is False
            else:
                assert row['schema']=='n25-rbf-call-summary-v1' and 'input_source' not in row
        if instrumented:
            witness = [v for name,v in events if name=='n26_rbf_witness']
            coverage = [v for name,v in events if name=='n26_rbf_witness_coverage']
            assert len(witness)==11 and len(coverage)==1 and not coverage[0]['missing_slots']
            assert not any(name.startswith('n25_rbf') for name,_ in events)
            for item in witness:
                tensors, meta = item['tensors'], item['metadata']
                assert meta['schema']=='n26-bounded-rbf-witness-v1'
                assert bytes_equal(tensors['input_xyz'],tensors['model_output_before'])
                assert bytes_equal(tensors['model_output_after'],tensors['model_output_before']+tensors['update_operand'])
                assert meta['numeric_bytes']<=20*1024 and len(json.dumps(meta).encode())<=16*1024
            assert coverage[0]['numeric_bytes']<=220*1024
            manager=stub_steer._n26_rbf_witness
            manager.begin(recorder); assert manager.prepare('initial',-1) is None; manager.finish()
            assert len([n for n,_ in events if n=='n26_rbf_witness_coverage'])==1
            stub_steer.reset(); assert not stub_steer._n26_rbf_witness.first_consumed
        runs.append((selected.clone(),counter,torch.random.get_rng_state().clone(),len(origins),rows))
    for a,b in [(runs[0],runs[1]),(runs[2],runs[3])]:
        assert bytes_equal(a[0],b[0]) and a[1]==b[1] and torch.equal(a[2],b[2]) and a[3:]==b[3:]
    assert runs[0][1]==runs[2][1]


@pytest.mark.parametrize('fault',['input','signed_zero','schema','source','prediction','jacobian','field','size','metadata'])
def test_witness_rejects_wrong_clean_binding_and_caps(fault):
    from core.qd_clean_output_rbf import CleanOutputWitness, SOURCE
    manager=CleanOutputWitness();manager.begin(SimpleNamespace(record=lambda *a,**kw:None));manager.prepare('initial',-1)
    fields={'input_xyz','source_origins','cast_origins','projected_xyz','gradient_before','gradient_after',
            'update_operand','model_output_before','model_output_after'}
    capture={k:torch.zeros((16,3) if 'origins' in k else (16,8,3)) for k in fields}
    evidence={'schema':'n26-rbf-call-summary-v1','source':SOURCE,'input_source':'model_output_sample_v1',
        'prediction_type':'sample','input_binding':'same_forward_unmodified_model_output',
        'model_jacobian_used':False,'phase':'initial','iteration':-1}
    if fault=='input':capture['input_xyz'][0,0,0]=1
    if fault=='signed_zero':capture['input_xyz'][0,0,0]=-0.0
    if fault=='schema':evidence['schema']='n25-rbf-call-summary-v1'
    if fault=='source':evidence['input_source']='noisy_sample'
    if fault=='prediction':evidence['prediction_type']='epsilon'
    if fault=='jacobian':evidence['model_jacobian_used']=True
    if fault=='field':capture['latent']=torch.zeros(16,64,128)
    if fault=='size':manager.NUMERIC_CALL_CAP=1
    if fault=='metadata':evidence['bad']='x'*16384
    with pytest.raises(ValueError):manager.emit(capture,evidence)


@pytest.mark.parametrize('phase',['initial','rollout'])
@pytest.mark.parametrize('fault',['nan','inf'])
def test_nonfinite_clean_sample_rejected(stub_steer,stub_adapter,monkeypatch,phase,fault):
    native_adapter(stub_adapter,monkeypatch)
    stub_steer.post_init(adapter=stub_adapter,postprocessor=lambda x:x,sample_batch_size=16,policy_config={'action_chunk_horizon':8})
    stub_steer._noise_scheduler.config={'prediction_type':'sample'}
    monkeypatch.setattr(stub_steer._rdt_model.dit,'forward',lambda x,*a:torch.full_like(x,float(fault)))
    with pytest.raises(ValueError,match='nonfinite'):
        invoke(stub_steer,phase,input_tensor(torch.float32,16),_rollout_cond(stub_steer),config(stub_steer,'N26'))


def test_source_no_extra_forward_math_byte_identity_and_wiring():
    expected=json.loads((ROOT/'experiments/qd_ed_n26/base-function-hashes-v1.json').read_text())
    for filename, functions in expected.items():
        source=(ROOT/filename).read_text(); tree=ast.parse(source)
        for name, sha in functions.items():
            node=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
            segment=ast.get_source_segment(source,node)
            assert hashlib.sha256(segment.encode()).hexdigest()==sha
    tree=ast.parse((ROOT/'core/rdt_policy_steer.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RDTSteer')
    for method in ('_eds_initial_denoise_rbf_diverse','_eds_rollout_rbf_diverse_reference'):
        node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==method)
        calls=[n for n in ast.walk(node) if isinstance(n,ast.Call)]
        forwards=[n for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='_counted_dit']
        assert len(forwards)==1
        assert any(isinstance(n,ast.With) and any(isinstance(i.context_expr,ast.Call) and
            isinstance(i.context_expr.func,ast.Attribute) and i.context_expr.func.attr=='no_grad' for i in n.items)
            and forwards[0] in list(ast.walk(n)) for n in ast.walk(node))
        assert sum(isinstance(n.func,ast.Name) and n.func.id=='geometry_input' for n in calls)==1
        assert sum(isinstance(n.func,ast.Attribute) and n.func.attr=='_counted_scheduler_step' for n in calls)==1
