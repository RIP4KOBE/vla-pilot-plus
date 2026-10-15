"""Synthetic only: no episode payloads, model/provider/projector or GPU calls."""
import copy
import hashlib
import importlib.util
import io
import marshal
import os
from pathlib import Path
import sys
import types

os.environ['CUDA_VISIBLE_DEVICES'] = ''
import pytest
import torch

HERE = Path(__file__).parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

c=load('n3_activity_test_subject',HERE/'check_activity.py')
SOURCE=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/selected-tracking-preparation-v1/source-v1/read_selected_tracking.py')
N=Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-executed-quality-20260923')
st=load('n3_test_tracking',SOURCE)
semantic=load('core.qd_executed_quality',N/'core/qd_executed_quality.py')
helper=load('n3_test_helper',N/'core/qd_executed_feedback.py')


def provider(text=None):
    text=text or semantic.TEMPLATE
    code=compile(text,sys.intern('<string>'),'exec',flags=0,dont_inherit=True,optimize=0)
    fn=next(x for x in code.co_consts if isinstance(x,types.CodeType))
    return {'ordinal':0,'code_sha256':'b'*64,'original_code_sha256':hashlib.sha256(marshal.dumps(fn)).hexdigest(),
            'source_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'source_path':'/synthetic/approach.txt'},text


def fixture(dtype=torch.bfloat16):
    p,text=provider();scope={'role':'canonical_initial','iter_idx':0,'site':'synthetic'}
    samples=torch.zeros((2,64,128),dtype=dtype);samples[1]=2
    x=torch.zeros((2,9,3),dtype=dtype);x[0,1:,0]=1;x[1,1:,0]=2
    kp=torch.zeros((1,3),dtype=dtype);raw=torch.tensor([-1.,-4.],dtype=dtype)
    rows=[]
    def event(kind,**values):
        row={'sequence':len(rows)+1,'event':kind,'episode':0,'decision_id':'d2','global_step':8,'reset_sequence':0,'values':values};rows.append(row);return row
    event('decision_context',stage=1,use_guidance=True,providers=[p])
    for i in range(2):event('projection_origin',source_eef_position=torch.zeros(3),cast_eef_start=x[i,0])
    score=event('scoring_inputs',samples=samples,projected_xyz=x,keypoints=kp,provider_input_xyz=x[:,1:8],slice_kind='eds',projection_origin_sequences=[2,3],scoring_scope=scope)
    for i in range(2):event('provider_return',scoring_batch_id=score['sequence'],candidate_index=i,provider_ordinal=0,context_provider_ordinal=0,result=raw[i].float(),scoring_scope=scope)
    event('scoring_aggregate',scoring_batch_id=score['sequence'],aggregate_before_reward_mode=raw,scoring_scope=scope)
    event('effective_quality',scoring_batch_id=score['sequence'],reward_mode='normal',quality=raw,scoring_scope=scope)
    event('canonical_candidate_batch',iter_idx=0,candidates=samples,effective_quality=raw,occurrence_ids=['occ0','occ1'])
    event('final_selection',population=samples,selected_latent=samples[0:1],selected_index=0,selected_quality=-1.,selected_canonical_fingerprint=st.fingerprint(samples[0]))
    event('policy_action_decode',selected_latent=samples[0:1].float(),selected_canonical_fingerprint=st.fingerprint(samples[0]))
    chosen,error=st.selected(rows);assert error is None
    derived={'decision_id':'d2','global_step':8,'reset_sequence':0,'providers':st.providers([p])[0],
             'provider_identity_known':True,'stage':1,'use_guidance':True,'m':8,
             'selected_native':st.native_info(chosen['chosen']),
             'projected':{'native':st.native_info(chosen['x']),'origin_native':st.native_info(chosen['origin'])}}
    residual=[-4.,0.,0.]
    previous={**derived,'decision_id':'d1','global_step':0,'last_global_step':7,'ended':False,
              'tracking':[{'e_disp':residual}]}
    pair={'status':'retrospective_predictive_check','current_decision_id':'d2','previous_decision_id':'d1','previous_e_disp_8':residual,'current_m':8}
    return rows,derived,pair,previous,{p['source_path']:text}


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_full_native_pool_real_helper(dtype):
    rows,d,p,prev,sources=fixture(dtype);rng=torch.random.get_rng_state().clone()
    before={r['sequence']:copy.deepcopy(r) for r in rows}
    result=c.check_decision(rows,d,p,prev,sources,st,semantic,helper.executed_feedback_quality)
    assert result['status']=='conditional_mathematical_check'
    assert result['tie_robust_native_changed_choice'] and result['all_native_internal_maximum_slots']==[1]
    assert result['native_storage_dtype']==str(dtype)
    assert result['historical_runtime_eligibility'].startswith('Unknown')
    assert result['slots'][1]['raw_quality']==-4 and result['actual_selected_raw_quality']==-1
    assert torch.equal(torch.random.get_rng_state(),rng)
    for row in rows:
        for key,value in row['values'].items():
            if torch.is_tensor(value):assert st.same(value,before[row['sequence']]['values'][key])


@pytest.mark.parametrize('fault,reason',[
    ('selected_raw','actual_selected_raw_quality_mismatch'),('raw_link','raw_quality_association'),
    ('provider_result','provider_return_native_storage_mismatch'),('slice','native_original_T7_contract'),
    ('quality_dtype','native_original_T7_contract'),('selected_index','selected_pool_identity'),
    ('origin','origin_cast_association')])
def test_bad_raw_native_associations_fail(fault,reason):
    rows,*_=fixture()
    if fault=='selected_raw':rows[-2]['values']['selected_quality']=5.
    if fault=='raw_link':rows[6]['values']['aggregate_before_reward_mode']=torch.zeros(2,dtype=torch.bfloat16)
    if fault=='provider_result':rows[4]['values']['result']=torch.tensor(9.)
    if fault=='slice':rows[3]['values']['provider_input_xyz']=rows[3]['values']['projected_xyz'][:,:7]
    if fault=='quality_dtype':rows[7]['values']['quality']=rows[7]['values']['quality'].float()
    if fault=='selected_index':rows[-2]['values']['selected_index']=1
    if fault=='origin':rows[1]['values']['source_eef_position']=torch.ones(3)
    with pytest.raises(ValueError,match=reason):
        c.final_pool(rows,torch.tensor([-4.,0.,0.],dtype=torch.float64),0,st,helper.executed_feedback_quality)


def test_no_native_match_is_unknown_not_float_fingerprint_join():
    rows,*_=fixture();rows[-2]['values']['population']=rows[-2]['values']['population'].float()
    rows[-2]['values']['selected_latent']=rows[-2]['values']['selected_latent'].float()
    result=c.final_pool(rows,torch.zeros(3,dtype=torch.float64),0,st,helper.executed_feedback_quality)
    assert result['status']=='Unknown' and result['reason']=='final_slot_has_no_exact_native_canonical_occurrence'


def test_duplicate_native_occurrences_require_geometry_agreement():
    rows,*_=fixture();score=rows[3]['values'];score['samples'][1]=score['samples'][0]
    raw=torch.tensor([-1.,-1.],dtype=torch.bfloat16)
    rows[5]['values']['result']=torch.tensor(-1.)
    for row,key in ((rows[6],'aggregate_before_reward_mode'),(rows[7],'quality'),(rows[8],'effective_quality')):row['values'][key]=raw
    result=c.final_pool(rows,torch.zeros(3,dtype=torch.float64),0,st,helper.executed_feedback_quality)
    assert result['status']=='Unknown' and 'conflicting_occurrences' in result['reason']
    score['projected_xyz'][1]=score['projected_xyz'][0]
    result=c.final_pool(rows,torch.zeros(3,dtype=torch.float64),0,st,helper.executed_feedback_quality)
    assert result['status']=='conditional_mathematical_check'
    assert len(result['slots'][0]['matching_occurrences'])==2
    assert result['all_native_internal_maximum_slots']==[0,1]
    assert not result['tie_robust_native_changed_choice']


def rank(old,new,identities=None):
    slots=[{'fingerprint':str(i),'native_identity':(identities or [str(j) for j in range(len(old))])[i]} for i in range(len(old))]
    return c.ranking(slots,list(torch.tensor(old,dtype=torch.bfloat16)),list(torch.tensor(new,dtype=torch.bfloat16)),0,st)


@pytest.mark.parametrize('old,new,changed,witness',[
    ([-1,-2],[-2,-3],False,False),([-1,-2],[-3,-2],True,True),
    ([-1,-1],[-1,-1],False,False),([-1,-2],[-1,-1],False,True),
    ([-1,-1],[-1,-2],False,True),([-1,-2],[-1.001,-1.002],False,True)])
def test_native_exact_ties_and_ranking_activity(old,new,changed,witness):
    result=rank(old,new)
    assert result['tie_robust_native_changed_choice']==changed
    assert bool(result['quality_dependent_ranking_witnesses'])==witness
    if new==[-1.001,-1.002]:assert result['all_native_internal_maximum_slots']==[0,1]


def test_empty_pool_and_not_raw_max_reject():
    with pytest.raises(ValueError,match='empty'):c.ranking([],[],[],0,st)
    with pytest.raises(ValueError,match='not_raw_maximum'):rank([-2,-1],[-3,-1])


@pytest.mark.parametrize('reason',['no_previous_decision','unguided_boundary','reset_or_terminal_boundary','previous_prefix_not_full_eight','provider_identity_unknown'])
def test_ineligible_disposition_never_calls_quality(reason):
    rows,d,p,prev,sources=fixture();p={'current_decision_id':'d2','status':'Unknown_or_ineligible','reason':reason}
    def forbidden(*a,**k):raise AssertionError('no scoring for excluded pair')
    result=c.check_decision(rows,d,p,prev,sources,st,semantic,forbidden)
    assert result['status']=='not_structurally_eligible' and result['reason']==reason


@pytest.mark.parametrize('fault',['partial','terminal','gap','provider','past_residual'])
def test_eligible_pair_contradictions_do_not_silently_score(fault):
    rows,d,p,prev,sources=fixture()
    if fault=='partial':prev['m']=7
    if fault=='terminal':prev['ended']=True
    if fault=='gap':prev['last_global_step']=6
    if fault=='provider':prev['providers']=[{}]
    if fault=='past_residual':p['previous_e_disp_8']=[1.,2.,3.]
    with pytest.raises(ValueError):c.check_decision(rows,d,p,prev,sources,st,semantic,helper.executed_feedback_quality)


def test_provider_generic_index_code_and_source_binding_no_exec():
    text=semantic.TEMPLATE.replace('torch.tensor([0]','torch.tensor([3]');p,text=provider(text)
    assert c.provider_semantics([p],text,semantic)[0]==3
    bad=copy.deepcopy(p);bad['original_code_sha256']='0'*64
    assert c.provider_semantics([bad],text,semantic)[1]=='Unknown_provider_original_code_mismatch'
    assert c.provider_semantics([p],text+'\n',semantic)[1]=='Unknown_provider_source_text_mismatch'
    assert c.provider_semantics([p],None,semantic)[1]=='Unknown_provider_source_unavailable'
    assert c.provider_semantics([p,p],text,semantic)[0] is None


@pytest.mark.parametrize('extra',["\nraise AssertionError('executed')\n",'\nimport os\n','\nprint(1)\n'])
def test_top_level_side_effects_rejected_without_execution(extra):
    text=semantic.TEMPLATE+extra;p,text=provider(text)
    assert c.provider_semantics([p],text,semantic)==(None,'unsupported_complete_provider_template')


def test_unknown_semantics_retained_without_scoring():
    rows,d,p,prev,sources=fixture()
    def forbidden(*a,**k):raise AssertionError('unknown provider scored')
    result=c.check_decision(rows,d,p,prev,{},st,semantic,forbidden)
    assert result['status']=='Unknown'
    out=c.summary([result]);assert out['structurally_eligible']==1 and not out['conditional_activity_gate']


def test_declared_incomplete_universe_rejected_before_bundles():
    names={'matrix_report':c.REPORT_SHA,'tracking_index':c.TRACK_INDEX_SHA,'tracking_provenance':c.TRACK_PROVENANCE_SHA,
           'tracking_status':c.TRACK_STATUS_SHA,'fresh_audit_bindings':c.BINDING_SHA}
    manifest={'schema':'n3-recorded-final-pool-input-v1',**{k:{'path':k,'sha256':v} for k,v in names.items()}}
    values={'matrix_report':{'matrix':'complete_valid_30','cells':[]},'tracking_index':{'complete':True,'cells':[]},
            'tracking_provenance':{'complete':True,'source_commit':c.SOURCE,'cuda_initialized':False,'input_hashes':{}},
            'tracking_status':{'complete':True,'cells':30},'fresh_audit_bindings':{}}
    class Inputs:
        def read(self,ref):return values[ref['path']]
        def raw(self,ref):raise AssertionError('bundle read before universe verified')
    with pytest.raises(ValueError,match='exact_all_Q0_universe'):c.admit(manifest,Inputs(),st)


def test_real_torch_cpu_stream_preserves_decisions_and_prunes_auxiliary(monkeypatch):
    rows,*_=fixture()
    rows.append({**rows[3], 'sequence':12, 'values':{**rows[3]['values'],'scoring_scope':{'role':'auxiliary_pretest'}}})
    rows.append({**rows[0], 'sequence':13, 'decision_id':'d3','global_step':16})
    f=io.BytesIO();torch.save({'schema':'qd-ed-decision-evidence-v1','events':rows},f);data=f.getvalue()
    meta={'bundle':'bundle_000001.pt','sha256':c.digest(data),'events':[{k:r[k] for k in st.META} for r in rows]}
    calls=[];original=torch.load
    def checked(*a,**kw):
        calls.append(kw);return original(*a,**kw)
    monkeypatch.setattr(torch,'load',checked)
    class Inputs:
        def raw(self,ref):assert ref['sha256']==c.digest(data);return data
    result=list(c.stream({'index':[meta],'episode':Path('/synthetic')},Inputs(),st))
    assert len(result)==2 and len(result[0])==11 and result[1][0]['decision_id']=='d3'
    assert calls==[{'map_location':'cpu','weights_only':True}]
    assert not torch.cuda.is_initialized()


def test_mutating_quality_helper_fails_closed():
    rows,*_=fixture()
    def bad(x,k,**kwargs):
        x[0,1,0]+=1
        return torch.ones(1,dtype=x.dtype)
    with pytest.raises(ValueError,match='helper_mutated_input'):
        c.final_pool(rows,torch.zeros(3,dtype=torch.float64),0,st,bad)


def test_admit_exact_ten_excludes_invalid_and_other_arms_before_decode(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'ROOT',tmp_path)
    refs={'matrix_report':c.REPORT_SHA,'tracking_index':c.TRACK_INDEX_SHA,
          'tracking_provenance':c.TRACK_PROVENANCE_SHA,'tracking_status':c.TRACK_STATUS_SHA,
          'fresh_audit_bindings':c.BINDING_SHA}
    manifest={'schema':'n3-recorded-final-pool-input-v1',**{k:{'path':str(tmp_path/k),'sha256':h} for k,h in refs.items()},'provider_sources':[]}
    values={};bound={};cells=[];entries=[];certs=[];bundles=[]
    for task in range(10):
        key=f't{task:02d}-q0';aid=f'owned-{task}';ep=tmp_path/'attempts'/aid/'eds_eval/decision_evidence/episode_000'
        ep.mkdir(parents=True);(ep/'bundle_000001.pt').write_bytes(b'synthetic-not-decoded')
        ident={'task_id':task,'profile':'Q0'}
        cells.append({'identity':ident,'valid_attempt_id':aid,'status':'complete_valid',
                      'attempts':[{'status':'terminal_invalid','path':'DO_NOT_READ_INVALID'}]})
        entries.append({'cell':key,'attempt_id':aid,'path':key+'.json','sha256':'d'*64})
        values[str(tmp_path/(key+'.json'))]={'attempt_id':aid,'identity':ident,'decisions':[]}
        ir={'path':str(ep/'events.jsonl'),'sha256':'a'*64};sr={'path':str(ep/'status.json'),'sha256':'b'*64};fr={'path':str(tmp_path/(key+'-audit.json')),'sha256':'c'*64}
        certs.append({'attempt_id':aid,'cell':key,'accepted':True,'evidence_complete':True,'errors':[],
                      'fresh_audit':fr,'episode_dir':str(ep),'bundle_index':ir,'collector_status':sr,'bundle_hash_count':1})
        values[fr['path']]={'accepted':True,'evidence_complete':True,'errors':[],'episode_dir':str(ep)}
        values[ir['path']]=[{'bundle':'bundle_000001.pt','sha256':'e'*64}]
        values[sr['path']]={'complete':True,'failed':False,'pending_action':False,'bundles':1}
        bound.update({ir['path']:ir['sha256'],sr['path']:sr['sha256'],str(ep/'bundle_000001.pt'):'e'*64})
    values.update({str(tmp_path/'matrix_report'):{'matrix':'complete_valid_30','cells':cells},
                   str(tmp_path/'tracking_index'):{'complete':True,'cells':entries},
                   str(tmp_path/'tracking_provenance'):{'complete':True,'source_commit':c.SOURCE,'cuda_initialized':False,'input_hashes':bound},
                   str(tmp_path/'tracking_status'):{'complete':True,'cells':30},
                   str(tmp_path/'fresh_audit_bindings'):{'cells':certs}})
    class Inputs:
        def read(self,ref,lines=False):return values[ref['path']]
        def path(self,path):return Path(path)
        def raw(self,ref):bundles.append(ref['path']);return b'synthetic-not-decoded'
    result,sources=c.admit(manifest,Inputs(),st)
    assert len(result)==10 and sources=={} and len(bundles)==10
    assert {r['cell'] for r in result}=={f't{i:02d}-q0' for i in range(10)}
    # No torch.load, old audit execution, invalid predecessor, or C0/N2 payload path.
    assert all('owned-' in path and path.endswith('bundle_000001.pt') for path in bundles)
