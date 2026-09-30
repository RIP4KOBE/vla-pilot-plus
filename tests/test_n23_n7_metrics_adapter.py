"""Serializer-faithful N7 operational compatibility, no native data or CUDA."""
import copy
import json
from pathlib import Path
import sys
import pytest
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'continuation'))
from n23_n7_metrics_adapter import native_counts
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_supervise as old
from core.eds_eval_metrics import EDSChunkMetrics


@pytest.fixture(autouse=True)
def no_cuda():
    yield
    assert not torch.cuda.is_initialized()


def case(tmp_path,arm='N7'):
    original=r.read_json(ROOT/'configs/qd_ed_final/baseline_profiles.json')
    candidate=r.read_json(ROOT/f'configs/qd_ed_final/candidate_{arm.lower()}.json')
    original['profiles'][arm]=r.expand_candidate(arm,candidate,original['profiles']['Q0'])
    plan={'candidate_profiles':{arm:{'path':str(ROOT/f'configs/qd_ed_final/candidate_{arm.lower()}.json'),
        'sha256':w.sha(ROOT/f'configs/qd_ed_final/candidate_{arm.lower()}.json')}}}
    metrics=EDSChunkMetrics(qd_quality_mode='provider' if arm=='N7' else 'actuator_clipped_provider_v1',
        qd_descriptor='target_xy_quadrant_signed_height_v1',qd_final_selection_mode='terminal_grasp_proximity_v1',
        qd_archive_active_for_chunk=True,score_call_count=11,search_evaluation_count=176,
        resample_count=10,renoise_count=10,rollout_count=10).to_jsonable()
    raw={'dtype':'torch.bfloat16','shape':[16],'sha256':'a'*64,'values':[float(i)/8 for i in range(16)]}
    cost={**raw,'sha256':'b'*64,'values':[-v for v in raw['values']]}
    decision={'terminal_raw_provider_quality':raw,'terminal_native_costs':cost,
        'selected_index':0,'selected_raw_reward':0.,'selected_cost':0.}
    report={'accepted':True,'evidence_complete':True,'n5_grasp_timing_audit':{
        'schema':'n5-native-grasp-timing-audit-v1','checked_decisions':1,'parent_rounds_verified':10,
        'canonical_batches_verified':11,'canonical_candidates_verified':176,'decisions':[decision]}}
    final={'output_dir':str(tmp_path),'guided_chunks':1};row={'profile':arm}
    return plan,original,metrics,report,final,row


def invoke(tmp_path,value):
    plan,manifest,metrics,report,final,row=value
    p=tmp_path/'eds_eval/eds_metrics.jsonl';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(metrics)+'\n')
    return native_counts(final,row,report,plan=plan,manifest=manifest,root=ROOT,r=vars(r),w=w,original=old)


@pytest.mark.parametrize('mode',['omitted','explicit'])
def test_real_legacy_serializer_and_provider_identity_accept(tmp_path,mode):
    values=case(tmp_path);m=values[2]
    assert 'qd_quality_mode' not in m and not any(k.startswith('qd_quality_') for k in m)
    if mode=='explicit':m['qd_quality_mode']='provider'
    before=copy.deepcopy(values)
    path=tmp_path/'eds_eval/eds_metrics.jsonl';path.parent.mkdir();path.write_text(json.dumps(m)+'\n')
    if mode=='omitted':
        with pytest.raises(ValueError,match='substantive'):old.native_counts(values[4],values[5],values[3])
    else:assert old.native_counts(values[4],values[5],values[3])[0]=={'guided_decisions':1,'parent_rounds_verified':10}
    assert invoke(tmp_path,values)[0]=={'guided_decisions':1,'parent_rounds_verified':10}
    assert values==before


@pytest.mark.parametrize('bad',[None,'','actuator_clipped_provider_v1','close_then_lift_v1',0,False,{},[]])
def test_explicit_wrong_mode_is_never_defaulted(tmp_path,bad):
    values=case(tmp_path);values[2]['qd_quality_mode']=bad
    with pytest.raises(ValueError):invoke(tmp_path,values)


@pytest.mark.parametrize('fault',['profile','resolved','raw','count','parent','source','selected','acceptance','missing_raw','intervention'])
def test_missing_mode_requires_profile_and_complete_raw_parent_native_proof(tmp_path,fault):
    plan,manifest,metrics,report,final,row=values=case(tmp_path)
    gate=report['n5_grasp_timing_audit'];decision=gate['decisions'][0]
    if fault=='profile':plan['candidate_profiles']['N7']['sha256']='wrong'
    if fault=='resolved':manifest['profiles']['N7']['resolved_eds_config']['qd_quality_mode']='other'
    if fault=='raw':decision['terminal_native_costs']['values'][1]=0.
    if fault=='count':metrics['search_evaluation_count']=175
    if fault=='parent':gate['parent_rounds_verified']=9
    if fault=='source':gate['canonical_batches_verified']=10
    if fault=='selected':decision['selected_cost']=1.
    if fault=='acceptance':report['accepted']=False
    if fault=='missing_raw':decision.pop('terminal_raw_provider_quality')
    if fault=='intervention':report['n23_actuator_clipped_quality_audit']={}
    with pytest.raises(ValueError):invoke(tmp_path,values)


def test_n23_serializer_preserves_mode_and_missing_value_still_fails(tmp_path):
    values=case(tmp_path,'N23')
    assert values[2]['qd_quality_mode']=='actuator_clipped_provider_v1'
    values[2].pop('qd_quality_mode')
    with pytest.raises(ValueError):invoke(tmp_path,values)



def n23_gate(values):
    values[3]['n23_actuator_clipped_quality_audit']={
        'score_batches_verified':11,'candidate_scores_verified':176,
        'clipped_prefix_candidates':0,'rank_changed_batches':0}


def test_n23_actual_serializer_retains_every_required_field(tmp_path):
    values=case(tmp_path,'N23');n23_gate(values)
    m=values[2]
    assert all(k in m for k in old.AUX_FIELDS)
    counts,aux=invoke(tmp_path,values)
    assert counts=={'guided_decisions':1,'parent_rounds_verified':10,
        'score_batches_verified':11,'candidate_scores_verified':176,
        'clipped_prefix_candidates':0,'rank_changed_batches':0}
    assert aux=={k:m[k] for k in old.AUX_FIELDS}


@pytest.mark.parametrize('key',old.AUX_FIELDS)
def test_n23_missing_serialized_auxiliary_is_still_fatal(tmp_path,key):
    values=case(tmp_path,'N23');n23_gate(values);values[2].pop(key)
    with pytest.raises(ValueError,match='auxiliary'):invoke(tmp_path,values)
