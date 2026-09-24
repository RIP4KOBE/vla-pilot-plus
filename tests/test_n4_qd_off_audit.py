"""CPU synthetic evidence only; real search plumbing uses the existing stub model."""
import copy
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from torch import nn

from test_rdt_steer import (_patch_core_imports, stub_steer, stub_adapter, mock_batch,
    _valid_qd_config, _n2_fixture_provider)
from scripts import audit_n4_qd_off_evidence as off


@pytest.mark.parametrize('dtype', [torch.float32, torch.bfloat16])
def test_real_cpu_c0_and_qd_off_same_active_search_rng_calls_and_native_audit(
        stub_steer, stub_adapter, mock_batch, monkeypatch, tmp_path, dtype):
    from core.decision_evidence import DecisionEvidence
    stub_steer._dit.register_parameter('_dtype_anchor', nn.Parameter(torch.zeros((), dtype=dtype), requires_grad=False))
    stub_steer.post_init(adapter=stub_adapter, postprocessor=lambda x: x, sample_batch_size=16,
                         policy_config={'action_chunk_horizon': 8})
    initial = torch.linspace(-.12, .19, 16*64*128).reshape(16,64,128).to(dtype)
    monkeypatch.setattr(stub_steer, '_eds_initial_population', lambda **kw: initial.clone())
    original_project = stub_adapter.delta_actions_to_ee_trajectory
    synthetic = _n2_fixture_provider()
    points = np.array([[9.,9.,9.],[.13,-.21,.39]], dtype=np.float32)
    runs = []
    for sampling in ('uniform_cells', 'sparse_priority'):
        stub_steer.reset(); calls = []
        rec = DecisionEvidence(tmp_path/sampling, episode=0); stub_steer._decision_evidence = rec
        def project(actions):
            result = original_project(actions); calls.append(tuple(actions.shape))
            rec.record('projection_origin', source_eef_position=torch.zeros(3), cast_eef_start=result[0])
            return result
        monkeypatch.setattr(stub_adapter, 'delta_actions_to_ee_trajectory', project)
        rec.begin_decision(global_step=0, stage=0, use_guidance=True, keypoints=torch.tensor(points), providers=[synthetic])
        cfg = _valid_qd_config(qd_archive_mode='none', qd_parent_sampling=sampling,
            qd_final_selection_mode='archive_global_best')
        torch.manual_seed(6654)
        action = stub_steer.select_action(mock_batch, generate_new_chunk=True, use_guidance=True,
            guidance_type='eds', eds_config=cfg, guidance_fns=[synthetic], keypoints=points,
            global_step=0, current_stage=0)
        rng = torch.get_rng_state().clone(); counts = stub_steer.get_episode_compute_counters()
        metrics = stub_steer.get_last_eds_metrics()
        # main.py:1902-1908 attaches episode/step identity to the unchanged
        # policy metric payload; the stub does not run a simulator/Main loop.
        metrics = {**metrics, 'episode': 0, 'global_step': 0, 'task_id': 0}
        rec.commit_decision(action_chunk=action, execution_horizon=8)
        for i in range(3):  # An early success/terminal can end inside the chunk.
            rec.dispatch(global_step=i, execution_index=i+1)
            rec.record('executed_action', action_numpy=action[0,i].numpy())
            rec.pre_reset_outcome({'robot0_eef_pos': np.zeros(3)}, reward=0., terminated=i==2, success=True)
            rec.step_returned(terminated=i==2, truncated=False, success=True)
        rec.finish(); compute = tmp_path/sampling/'episode_compute.jsonl'
        compute.write_text(json.dumps({'episode_id':0,'outcome':'completed','decision_evidence':rec.status()})+'\n')
        audit = off.audit_episode(rec.root, compute)
        assert audit['accepted'], audit['errors']
        gate = off.native_audit_alignment(audit, [metrics], require=lambda ok,msg: None if ok else pytest.fail(msg))
        assert gate['checked_decisions'] == 1 and gate['actual_actions_verified'] == 3
        assert gate['canonical_batches_verified'] == 11 and gate['canonical_candidates_verified'] == 176
        assert gate['parent_rounds_verified'] == 10
        runs.append((action, rng, counts, calls, audit, metrics, rec, compute))
    assert torch.equal(runs[0][0], runs[1][0]) and torch.equal(runs[0][1], runs[1][1])
    assert runs[0][2:4] == runs[1][2:4]  # Same stub model/provider/scoring/projection counts.
    assert runs[0][4]['n4_qd_off_audit']['decisions'] == runs[1][4]['n4_qd_off_audit']['decisions']
    # Attack already-recorded synthetic events, with no repeated search/model,
    # decoder-as-provider, or new scoring call to manufacture the expected value.
    rec = runs[1][6]
    base = off.module(off.ROOT/'scripts/audit_decision_evidence.py', '_test_off_base')
    decoder = off.module(off.ROOT/'core/rdt_libero_action_converter.py', '_test_off_decoder')
    rows = base.load_events(rec.root, rec.status()); kinds = defaultdict(list)
    for row in rows: kinds[row['event']].append(row)
    context = kinds['decision_context'][0]
    for fault in ('parent_dtype','wrong_cost','wrong_selection','wrong_dispatch','archive','auxiliary_only'):
        changed = copy.deepcopy(kinds)
        if fault=='parent_dtype': changed['parent_allocation'][0]['values']['source_population']=changed['parent_allocation'][0]['values']['source_population'].double()
        if fault=='wrong_cost': changed['effective_quality'][-1]['values']['costs'][0]+=1
        if fault=='wrong_selection': changed['final_selection'][0]['values']['selected_index']=True
        if fault=='wrong_dispatch': changed['executed_action'][0]['values']['action_numpy'][0]+=1
        if fault=='archive': changed['archive_parent_allocation']=[{}]
        if fault=='auxiliary_only': changed['scoring_inputs'][-1]['values']['scoring_scope']['role']='auxiliary_pretest'
        with pytest.raises(base.AuditFailure): off.check_decision(changed,context,base,decoder)
    assert not torch.cuda.is_initialized()


def summary():
    costs = [0., 0.] + [1.] * 14
    decision = {'global_step':0,'selected_index':0,'selected_cost':0.,'selected_raw_reward':-0.,
        'minimum_cost_tie_indices':[0,1], 'terminal_native_costs':{'shape':[16],'values':costs},
        'canonical_batches_verified':11,'canonical_candidates_verified':176,'parent_rounds_verified':10,'actual_prefix_length':3}
    audit = {'accepted':True,'evidence_complete':True,'errors':[], 'n4_qd_off_audit':{
        'schema':off.SCHEMA,'checked_decisions':1,'decisions':[decision],
        'canonical_batches_verified':11,'canonical_candidates_verified':176,'parent_rounds_verified':10,'actual_actions_verified':3}}
    metric = {'global_step':0,'selected_idx':0,'selected_cost':0.,'selected_reward':-0.,
        'qd_archive_active_for_chunk':False,'qd_archive_enabled':False}
    return audit, [metric]


@pytest.mark.parametrize('fault', ['metric_raw','metric_index','archive','ties','prefix','step','count','accepted'])
def test_metadata_alignment_rejects_wrong_native_consumer(fault):
    audit, metrics = summary(); gate=audit['n4_qd_off_audit']; d=gate['decisions'][0]
    if fault=='metric_raw': metrics[0]['selected_reward']=1.
    if fault=='metric_index': metrics[0]['selected_idx']=1
    if fault=='archive': metrics[0]['qd_archive_active_for_chunk']=True
    if fault=='ties': d['minimum_cost_tie_indices']=[0]
    if fault=='prefix': d['actual_prefix_length']=0
    if fault=='step': d['global_step']=8
    if fault=='count': gate['canonical_batches_verified']=10
    if fault=='accepted': audit['accepted']=False
    def require(ok,msg):
        if not ok: raise ValueError(msg)
    with pytest.raises(ValueError): off.native_audit_alignment(audit,metrics,require=require)


def test_metadata_empty_guided_and_signed_zero_are_not_activity_rejections():
    audit,metrics=summary()
    def require(ok,msg): assert ok,msg
    off.native_audit_alignment(audit,metrics,require=require)
    gate=audit['n4_qd_off_audit']; gate.update(decisions=[],checked_decisions=0,canonical_batches_verified=0,
        canonical_candidates_verified=0,parent_rounds_verified=0,actual_actions_verified=0)
    assert off.native_audit_alignment(audit,[],require=require)['checked_decisions']==0


def test_production_auditor_and_decoder_are_unchanged():
    import hashlib
    root=Path(__file__).resolve().parents[1]
    assert hashlib.sha256((root/'scripts/audit_decision_evidence.py').read_bytes()).hexdigest() == '4fdc8793d2a4cc4935e571c5db58e38e4ed48aae388f2ef598928a2b322491df'
    assert hashlib.sha256((root/'core/rdt_libero_action_converter.py').read_bytes()).hexdigest() == '5e880cce86acc2aea77077cbe2dee708ac23cec79c172cb6738f79d693e6d82d'
