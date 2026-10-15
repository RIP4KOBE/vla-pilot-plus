"""Synthetic recorded-QD fixtures; no claimed online result, no repository imports."""
import copy
import hashlib
import json
import math
from pathlib import Path
import pytest
import torch
from audit_qd_mechanism import FIXED,audit_chunk,allocate_parents,assign_cells,digest,freeze_bounds,reconstruct


def synthetic(two_cells=False):
    """Hand-computed low-coverage/all-tied run:16 initial +10 batches, unchanged winners."""
    config=copy.deepcopy(FIXED);config['shuffle_seed']=0
    desc=([[0.,0.]]*10+[[.2,.2]]*6) if two_cells else [[0.,0.]]*16
    batch=dict(descriptors_xy_m=desc,rewards=[0.]*16,fingerprints=[f'{n:064x}' for n in range(16)])
    stream=[dict(iter_idx=i,**copy.deepcopy(batch)) for i in range(-1,10)]
    # Bounds/checksum float32 are independently replayable arithmetic; all archive,
    # slot, visit and final-selection expectations below are hand specified.
    bounds,checksum=freeze_bounds(desc)
    cells=[0,15] if two_cells else [10];initial=[10,6] if two_cells else [16]
    parents={'0':6,'15':10} if two_cells else {'10':16};cell_count=len(cells)
    m=dict(episode=0,task_id=0,global_step=0,guidance_type='eds',reward_mode='normal',selected_parent_source='qd_archive',
        eds_enter_count=1,nonfinite_count=0,execution_horizon_resolved=8,parent_count_by_source={'elite':0,'anchor_offspring':0,'weighted_offspring':0,'qd_archive_offspring':160},
        population_size_observed=16,population_shape=[16,64,128],cem_iters=10,eds_iters_executed=10,
        score_call_count=11,search_evaluation_count=176,qd_archive_enabled=True,qd_archive_active_for_chunk=True,
        qd_evaluation_count=176,selected_chunk_population_source='qd_archive',shadow_qd_observer_enabled=True,
        shadow_qd_candidate_stream=stream,shadow_qd_observer_checksum=digest(stream),
        qd_bounds_xy_m=bounds,qd_bounds_source_initial_checksum=checksum,
        qd_initial_accounting=dict(insertions=cell_count,replacements=0,rejections=16-cell_count,total=16),
        qd_initial_occupied_cells=cell_count,qd_initial_descriptor_overflow_count=0,
        qd_selected_cell=cells[0],qd_selected_action_fingerprint='0'*64,qd_global_best_action_fingerprint='0'*64,
        qd_selected_reward=0.,selected_reward=0.,final_best_reward=0.,selected_idx=0)
    for k in ('qd_descriptor','qd_grid_shape','qd_cell_capacity','qd_parent_sampling','qd_secondary_lane_mode','qd_global_quality_anchor_count','qd_bounds_update_policy','qd_degenerate_fallback_policy'):m[k]=copy.deepcopy(FIXED[k])
    for k in ('qd_degenerate_fallback_used','qd_fallback_used','early_stop_used','chunk_memory_used'):m[k]=False
    for k in ('qd_global_quality_anchor_activation_count','qd_global_quality_anchor_rescue_count','qd_secondary_parent_activation_count','qd_secondary_invariant_violation_count','qd_secondary_rebin_discard_count','qd_accounting_violation_count','qd_elite_monotonicity_violation_count','qd_final_selection_mismatch_count','qd_bounds_expansion_count'):m[k]=0
    for k in ('qd_archive_replacements_by_iter','qd_archive_insertions_by_iter','qd_descriptor_overflow_count_by_iter','qd_raw_initial_bounds_overflow_count_by_iter','qd_archive_rebin_collisions_by_iter','qd_secondary_occupied_cells_by_iter','qd_secondary_parent_count_by_iter'):m[k]=[0]*10
    for k in ('qd_descriptor_overflow_ratio_by_iter','qd_archive_best_reward_by_iter','qd_archive_mean_elite_reward_by_iter','qd_archive_turnover_ratio_by_iter'):m[k]=[0.]*10
    m.update(qd_bounds_xy_m_by_iter=[bounds]*10,qd_bounds_checksum_by_iter=[checksum]*10,qd_bounds_expanded_by_iter=[False]*10,
        qd_parent_slots_by_cell_by_iter=[parents]*10,qd_sparse_parent_slots_by_cell_by_iter=[parents]*10,
        qd_parent_weights_by_cell_by_iter=[{str(c):1/(n*(i+1)+1) for c,n in zip(cells,initial)} for i in range(10)],
        qd_parent_covered_cell_ratio_by_iter=[1.]*10,qd_parent_cell_unique_ratio_by_iter=[cell_count/16]*10,
        qd_occupied_cells_by_iter=[cell_count]*10,qd_coverage_ratio_by_iter=[cell_count/16]*10,
        qd_cumulative_cell_visits_by_iter=[[dict(zip(cells,initial)).get(c,0)*(i+2) for c in range(16)] for i in range(10)],
        qd_per_cell_elite_reward_by_iter=[{str(c):0. for c in cells}]*10,qd_archive_rejections_by_iter=[16]*10,
        qd_global_quality_anchor_cell_by_iter=[None]*10,qd_global_quality_anchor_fingerprint_by_iter=[None]*10,
        qd_global_quality_anchor_rescued_by_iter=[False]*10,
        qd_archive_rebin_visit_sum_before_by_iter=[16*(i+1) for i in range(10)],
        qd_archive_rebin_visit_sum_after_by_iter=[16*(i+1) for i in range(10)])
    return m,config

@pytest.mark.parametrize('two_cells',[False,True])
def test_low_coverage_and_all_equal_rewards_valid(two_cells):
    m,c=synthetic(two_cells);r=audit_chunk(m,c)
    assert r['recorded_mechanism_valid'],[k for k,v in r['checks'].items() if v=='fail']
    assert r['reconstruction']['final_occupied_cells'] in (1,2)
    assert r['parent_tensor_verified_iterations']==[]
    assert r['descriptor_geometry_verified'] is False
    assert r['cohort_valid'] is None

@pytest.mark.parametrize('case',['inactive','shadow_only','budget','missing_batch','wrong_checksum','wrong_bounds','moving_bounds','wrong_visits','wrong_sparse_slots','wrong_weights','wrong_elite','wrong_final_fp','wrong_final_reward','wrong_accounting','inherited_visits','fingerprint_conflict','wrong_descriptor','missing_config','wrong_lane','fake_classic_parents','extra_sampler_change','wrong_horizon'])
def test_corruption_fails(case):
    m,c=synthetic(True)
    if case=='inactive':m['qd_archive_active_for_chunk']=False
    elif case=='shadow_only':m.update(qd_archive_enabled=False,qd_archive_active_for_chunk=False,qd_evaluation_count=0)
    elif case=='budget':m['score_call_count']=12
    elif case=='missing_batch':m['shadow_qd_candidate_stream'].pop();m['shadow_qd_observer_checksum']=digest(m['shadow_qd_candidate_stream'])
    elif case=='wrong_checksum':m['shadow_qd_observer_checksum']='f'*64
    elif case=='wrong_bounds':m['qd_bounds_xy_m']=[[0,0],[1,1]]
    elif case=='moving_bounds':m['qd_bounds_expanded_by_iter'][0]=True
    elif case=='wrong_visits':m['qd_cumulative_cell_visits_by_iter'][0][0]+=1
    elif case=='wrong_sparse_slots':m['qd_parent_slots_by_cell_by_iter'][0]={'0':8,'15':8}
    elif case=='wrong_weights':m['qd_parent_weights_by_cell_by_iter'][0]['0']=.5
    elif case=='wrong_elite':m['qd_per_cell_elite_reward_by_iter'][0]['0']=.1
    elif case=='wrong_final_fp':m['qd_selected_action_fingerprint']='a'*64
    elif case=='wrong_final_reward':m['selected_reward']=-1.
    elif case=='wrong_accounting':m['qd_archive_rejections_by_iter'][0]=15
    elif case=='inherited_visits':m['qd_cumulative_cell_visits_by_iter'][0]=[v+16 for v in m['qd_cumulative_cell_visits_by_iter'][0]]
    elif case=='fingerprint_conflict':m['shadow_qd_candidate_stream'][1]['rewards'][0]=.1;m['shadow_qd_observer_checksum']=digest(m['shadow_qd_candidate_stream'])
    elif case=='wrong_descriptor':m['qd_descriptor']=c['qd_descriptor']='target_distance_gripper_duty_v1'
    elif case=='missing_config':c.pop('qd_bounds_update_policy')
    elif case=='extra_sampler_change':c['initial_sampling_mode']='iid'
    elif case=='wrong_horizon':m['execution_horizon_resolved']=7
    elif case=='fake_classic_parents':m['parent_count_by_source']={'elite':0,'anchor_offspring':0,'weighted_offspring':160}
    elif case=='wrong_lane':m['selected_chunk_population_source']='weighted_offspring'
    assert not audit_chunk(m,c)['recorded_mechanism_valid'],case


def test_sparse_counts_are_cumulative_candidate_visits_not_parent_visits():
    m,c=synthetic(True);r=reconstruct(m['shadow_qd_candidate_stream'],0,0,0)
    assert r['iterations'][0]['parent_slots']=={'0':6,'15':10}
    assert r['iterations'][0]['visits'][0]==20 and r['iterations'][0]['visits'][15]==12
    assert r['iterations'][-1]['visits'][0]==110 and r['iterations'][-1]['visits'][15]==66


def test_local_tie_permutation_does_not_touch_global_rng():
    state=torch.get_rng_state().clone();a={0:{},1:{},2:{}};v=[5,5,6]+[0]*13
    first=allocate_parents(a,v,0,0,0,0);second=allocate_parents(a,v,0,0,0,0)
    assert first==second and torch.equal(state,torch.get_rng_state())
    assert sorted(first[0].values())==[5,5,6] and sum(first[0].values())==16


def test_overflow_is_legal_clamp_not_invalid():
    cells,count=assign_cells([[-1,1],[1,-1],[0,0]], [[-.04,-.04],[.04,.04]])
    assert cells==[12,3,10] and count==2


def test_stable_fingerprint_tie_and_replacement_are_order_independent():
    m,c=synthetic();stream=m['shadow_qd_candidate_stream'];a=reconstruct(stream,0,0,0)
    reverse=copy.deepcopy(stream)
    for b in reverse:
        for key in ('descriptors_xy_m','rewards','fingerprints'):b[key].reverse()
    b=reconstruct(reverse,0,0,0)
    assert a['selected']==b['selected'] and a['selected']['fingerprint']=='0'*64


def test_missing_seed_reports_reviewed_default():
    m,c=synthetic();c.pop('shuffle_seed');r=audit_chunk(m,c)
    assert r['recorded_mechanism_valid'] and r['effective_shuffle_seed']==0
    assert r['shuffle_seed_origin']=='reviewed_runtime_default_zero'


def test_bad_structure_fails_closed():
    m,c=synthetic();m['shadow_qd_candidate_stream'][0]['descriptors_xy_m'][0]=[float('nan'),0]
    assert not audit_chunk(m,c)['recorded_mechanism_valid']


def test_higher_reward_replaces_then_worse_candidates_do_not_evict():
    m,c=synthetic();stream=m['shadow_qd_candidate_stream'];stream[1]['rewards'][0]=.5;stream[1]['fingerprints'][0]='f'*64
    r=reconstruct(stream,0,0,0)
    assert r['iterations'][0]['accounting']==dict(insertions=0,replacements=1,rejections=15,total=16)
    assert all(x['accounting']['replacements']==0 for x in r['iterations'][1:])
    assert r['selected']['reward']==.5 and r['selected']['fingerprint']=='f'*64 and r['selected']['source_iter']==0


def traced_fixture():
    m,c=synthetic();actions=torch.arange(16*64*128,dtype=torch.float32).reshape(16,64,128)
    fps=[hashlib.sha256(a.numpy().astype('<f4',copy=False).tobytes()).hexdigest() for a in actions]
    winner=min(range(16),key=lambda i:fps[i])
    for batch in m['shadow_qd_candidate_stream']:batch['fingerprints']=fps[:]
    m['shadow_qd_observer_checksum']=digest(m['shadow_qd_candidate_stream'])
    m['qd_selected_action_fingerprint']=m['qd_global_best_action_fingerprint']=fps[winner]
    payload=dict(metadata=dict(task_id=0,episode=0,global_step=0),stages=[
        dict(stage='initial',iter_idx=0,actions=actions,particle_sources=None),
        dict(stage='resampled',iter_idx=0,actions=actions[winner].unsqueeze(0).repeat(16,1,1),parent_selection_kinds=['qd_sparse_priority']*16,particle_sources=['qd_archive_offspring']*16)])
    return m,c,payload,actions,winner


def test_saved_initial_and_resampled_tensors_bind_actual_first_parent_batch():
    m,c,p,_,_=traced_fixture();r=audit_chunk(m,c,p)
    assert r['recorded_mechanism_valid']
    assert r['parent_tensor_verified_iterations']==[0] and r['candidate_tensor_verified_batches']==[-1]
    assert r['executed_selected_tensor_verified'] is False and r['descriptor_geometry_verified'] is False


def test_tensors_catch_fake_active_flags_with_wrong_actual_parent():
    m,c,p,actions,winner=traced_fixture();p['stages'][1]['actions'][0]=actions[(winner+1)%16]
    r=audit_chunk(m,c,p)
    assert not r['recorded_mechanism_valid'] and r['checks']['trace/parent_tensor_fingerprints/0']=='fail'


def test_trace_identity_is_bound_to_chunk():
    m,c,p,_,_=traced_fixture();p['metadata']['global_step']=8
    assert not audit_chunk(m,c,p)['recorded_mechanism_valid']


def test_real_eds_shadow_observer_is_not_qd_activation():
    directory=Path(__file__).parent/'fixtures'
    m=json.loads((directory/'eds-control-firstchunk.json').read_bytes());c=json.loads((directory/'eds-config.json').read_bytes())
    control=audit_chunk(m,c,expected_mode='eds')
    assert control['recorded_mechanism_valid'],[k for k,v in control['checks'].items() if v=='fail']
    assert not audit_chunk(m,c,expected_mode='eds_qd')['recorded_mechanism_valid']
    assert m['shadow_qd_observer_enabled'] is True and m['qd_archive_active_for_chunk'] is False
    assert control['reconstruction']['final_occupied_cells']>0  # shadow occupancy is not activation


def test_duplicate_trace_stage_cannot_overwrite_failed_tensor_evidence():
    m,c,p,actions,winner=traced_fixture()
    good=copy.deepcopy(p['stages'][1])
    p['stages'][1]['actions'][0]=actions[(winner+1)%16]
    p['stages'].append(good)
    r=audit_chunk(m,c,p)
    assert not r['recorded_mechanism_valid']
    assert r['checks']['trace/trace_stage_identity_unique']=='fail'


@pytest.mark.parametrize('name,iteration',[('initial',999),('initial',-1),('scored',999),('scored',-1),('resampled',10),('resampled',-1)])
def test_trace_stage_identity_rejects_wrong_iteration(name,iteration):
    m,c,p,_,_=traced_fixture()
    stage=p['stages'][0] if name in ('initial','scored') else p['stages'][1]
    stage['stage']=name;stage['iter_idx']=iteration
    r=audit_chunk(m,c,p)
    assert not r['recorded_mechanism_valid']
    if name in ('initial','scored'):assert r['candidate_tensor_verified_batches']==[]
    else:assert r['parent_tensor_verified_iterations']==[]

@pytest.mark.parametrize('stage_name',['resampled','after_rollout','full_process_after_rollout'])
def test_qd_trace_rejects_classic_particle_lineage(stage_name):
    m,c,p,_,_=traced_fixture();p['stages'][1]['stage']=stage_name
    p['stages'][1]['particle_sources']=['weighted_offspring']*16
    r=audit_chunk(m,c,p)
    assert not r['recorded_mechanism_valid'] and r['parent_tensor_verified_iterations']==[]

@pytest.mark.parametrize('key,value',[('guidance_type','vls'),('selected_parent_source','weighted_offspring'),('reward_mode','inverted')])
def test_qd_metric_route_source_and_reward_mode_are_bound(key,value):
    m,c=synthetic();m[key]=value
    assert not audit_chunk(m,c)['recorded_mechanism_valid']

def test_inverted_reward_config_and_record_cannot_change_fixed_protocol_together():
    m,c=synthetic();c['reward_mode']=m['reward_mode']='inverted'
    assert not audit_chunk(m,c)['recorded_mechanism_valid']

def test_missing_reward_mode_reports_reviewed_default_normal():
    m,c=synthetic();c.pop('reward_mode');r=audit_chunk(m,c)
    assert r['recorded_mechanism_valid'] and r['effective_reward_mode']=='normal'
    assert r['reward_mode_origin']=='reviewed_runtime_default_normal'

@pytest.mark.parametrize('case',['qd_parent_count','qd_selected_source','qd_parent_source','qd_selected_cell','qd_selected_reward','qd_global_fingerprint','qd_archive_visits','qd_initial_archive','wrong_guidance','inverted_reward'])
def test_eds_control_cannot_claim_qd_lineage_or_archive(case):
    directory=Path(__file__).parent/'fixtures'
    m=json.loads((directory/'eds-control-firstchunk.json').read_bytes());c=json.loads((directory/'eds-config.json').read_bytes())
    if case=='qd_parent_count':m['parent_count_by_source']={'elite':0,'anchor_offspring':0,'weighted_offspring':0,'qd_archive_offspring':160}
    elif case=='qd_selected_source':m['selected_chunk_population_source']='qd_archive'
    elif case=='qd_parent_source':m['selected_parent_source']='qd_archive'
    elif case=='qd_selected_cell':m['qd_selected_cell']=10
    elif case=='qd_selected_reward':m['qd_selected_reward']=0.
    elif case=='qd_global_fingerprint':m['qd_global_best_action_fingerprint']='f'*64
    elif case=='qd_archive_visits':m['qd_cumulative_cell_visits_by_iter']=[[0]*16]*10
    elif case=='qd_initial_archive':m['qd_initial_occupied_cells']=1
    elif case=='wrong_guidance':m['guidance_type']='vls'
    elif case=='inverted_reward':m['reward_mode']=c['reward_mode']='inverted'
    assert not audit_chunk(m,c,expected_mode='eds')['recorded_mechanism_valid']


@pytest.mark.parametrize('batch,key,value',[(0,'descriptors_xy_m',1e100),(0,'descriptors_xy_m',1e30),(1,'descriptors_xy_m',1e100),(0,'rewards',1e100)])
def test_float32_overflow_or_collapsed_bounds_fail_with_serializable_report(batch,key,value):
    m,c=synthetic()
    m['shadow_qd_candidate_stream'][batch][key]=([[value,value]]*16 if key=='descriptors_xy_m' else [value]*16)
    if value==1e30:
        for item in m['shadow_qd_candidate_stream']:item[key]=[[value,value]]*16
    m['shadow_qd_observer_checksum']=digest(m['shadow_qd_candidate_stream'])
    r=audit_chunk(m,c)
    assert not r['recorded_mechanism_valid']
    json.dumps(r,allow_nan=False)

@pytest.mark.parametrize('stage_name',['initial','scored','resampled','after_rollout','full_process_after_rollout'])
@pytest.mark.parametrize('key',['rewards','costs'])
def test_provided_trace_scores_must_join_corresponding_candidate_or_parent_record(stage_name,key):
    m,c,p,_,_=traced_fixture()
    stage=p['stages'][0] if stage_name in ('initial','scored') else p['stages'][1]
    stage['stage']=stage_name;stage[key]=torch.full((16,),999.)
    r=audit_chunk(m,c,p)
    assert not r['recorded_mechanism_valid']
    assert r['checks'][f'trace/{stage_name}/0/{key}_join']=='fail'

def test_consistent_provided_trace_scores_remain_valid():
    m,c,p,_,_=traced_fixture()
    for stage in p['stages']:
        stage['rewards']=torch.zeros(16);stage['costs']=torch.zeros(16)
    r=audit_chunk(m,c,p)
    assert r['recorded_mechanism_valid'] and r['parent_tensor_verified_iterations']==[0]



def test_boolean_stream_iteration_is_not_integer_iteration():
    m,c=synthetic();m['shadow_qd_candidate_stream'][1]['iter_idx']=False
    m['shadow_qd_observer_checksum']=digest(m['shadow_qd_candidate_stream'])
    assert not audit_chunk(m,c)['recorded_mechanism_valid']

def test_boolean_trace_task_identity_is_not_integer_identity():
    m,c,p,_,_=traced_fixture();p['metadata']['task_id']=False
    assert not audit_chunk(m,c,p)['recorded_mechanism_valid']
