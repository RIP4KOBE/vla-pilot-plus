"""Source/synthetic only: no real .pt, provider files, episode results or GPU."""
import copy
import importlib.util
import os
from pathlib import Path
import sys

os.environ['CUDA_VISIBLE_DEVICES']=''
import pytest
import torch

E=Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-decision-evidence-20260923')
D=E/'docs/03_evidence/qd_ed_final/continuation_20260923/n3-fixed-candidate-activity'
spec=importlib.util.spec_from_file_location('n3_activity_fixture_review',D/'test_check_activity.py')
f=importlib.util.module_from_spec(spec);sys.modules[spec.name]=f;spec.loader.exec_module(f)
c,st=f.c,f.st


def test_alias_native_maximum_prevents_false_changed_choice_even_when_index_changes():
    slots=[{'fingerprint':'fp0','native_identity':'same-native'},
           {'fingerprint':'fp0','native_identity':'same-native'},
           {'fingerprint':'fp1','native_identity':'different-native'}]
    # Unit-test ranking's identity semantics independently of pool deduplication.
    old=list(torch.tensor([-1.,-1.,-2.],dtype=torch.bfloat16))
    new=list(torch.tensor([-2.,-1.,-1.],dtype=torch.bfloat16))
    out=c.ranking(slots,old,new,0,st)
    assert out['all_native_internal_maximum_slots']==[1,2]
    assert out['tie_robust_native_changed_choice'] is False
    assert out['conditional_mathematical_activity'] is True  # Actual changed ordering, not robust choice.
    assert len(out['quality_dependent_ranking_witnesses'])>0


def test_auxiliary_only_match_cannot_fill_a_missing_native_final_candidate():
    rows,*_=f.fixture(torch.float32)
    # Alter the final second latent, then provide its geometry only in an auxiliary scope.
    rows[-2]['values']['population']=rows[-2]['values']['population'].clone()
    rows[-2]['values']['population'][1].fill_(3.)
    extra=copy.deepcopy(rows[3]);extra['sequence']=100
    extra['values']['samples'][1].fill_(3.)
    extra['values']['scoring_scope']['role']='auxiliary_pretest'
    rows.append(extra);calls=[]
    def helper(*a,**kw):calls.append(1);return f.helper.executed_feedback_quality(*a,**kw)
    out=c.final_pool(rows,torch.zeros(3,dtype=torch.float64),0,st,helper)
    assert out['status']=='Unknown' and out['reason']=='final_slot_has_no_exact_native_canonical_occurrence'
    assert 'conditional_mathematical_activity' not in out
    assert len(calls)<=1  # A preceding known slot cannot turn this decision into a witness.


def test_residual_mutation_by_helper_cannot_finish_check():
    rows,*_=f.fixture(torch.float32)
    def helper(x,k,*,target_index,residual_previous):
        residual_previous[0]+=1
        return torch.zeros(1,dtype=x.dtype)
    with pytest.raises(ValueError,match='helper_mutated_input'):
        c.final_pool(rows,torch.zeros(3,dtype=torch.float64),0,st,helper)


def test_same_values_in_wrong_keypoint_dtype_do_not_join():
    rows,*_=f.fixture(torch.bfloat16)
    rows[3]['values']['keypoints']=rows[3]['values']['keypoints'].float()
    with pytest.raises(ValueError,match='native_original_T7_contract'):
        c.final_pool(rows,torch.zeros(3,dtype=torch.float64),0,st,f.helper.executed_feedback_quality)


@pytest.mark.parametrize('kind',['dtype','shape','nonfinite'])
def test_helper_contract_drift_never_produces_activity(kind):
    rows,*_=f.fixture(torch.bfloat16)
    def helper(x,k,**kw):
        if kind=='dtype':return torch.zeros(1,dtype=torch.float32)
        if kind=='shape':return torch.zeros((1,1),dtype=x.dtype)
        return torch.tensor([float('nan')],dtype=x.dtype)
    with pytest.raises(ValueError,match='N3_helper_storage_contract'):
        c.final_pool(rows,torch.zeros(3,dtype=torch.float64),0,st,helper)
    assert not torch.cuda.is_initialized()
