import copy
from pathlib import Path
import pytest
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w
from scripts import qd_ed_n27_cont_contract as c,qd_ed_n27_cont_history as h
from scripts import qd_ed_n27_cont_prepare as prep
from n27_cont_fixtures import group,write
from test_n27_continuation import fixture

@pytest.mark.parametrize('fault',[None,'plan','context','receipt','identity','budget','cost','audit','zero_gate'])
def test_actual_terminal_schema_and_native_acceptor(fixture,tmp_path,monkeypatch,fault):
    p=prep.build_plan(fixture,{'commit':'new','files':[]});write(c.PLAN,p);row=p['episodes'][0]
    events=group(row,'new',source='new',plan_sha=w.sha(c.PLAN));f=events[-1];out=tmp_path/'attempt';f['output_dir']=str(out)
    receipt=write(out/'eds_eval/in-worker-audit-receipt.json',{});f['n23_worker_receipt']=receipt
    context={'plan':c.ref(c.PLAN)};write(out/'n23-worker-context.json',context)
    write(out/'attempt-result.json',f)
    calls=[]
    monkeypatch.setattr(c,'read_worker_report',lambda *a:calls.append('receipt') or {})
    def native(*args):
        calls.append(('native',args[0],args[-1]))
        if fault in {'audit','zero_gate'}:raise ValueError('profile-bound audit missing')
        return {},{}
    monkeypatch.setattr(c.native,'from_output',native)
    if fault=='plan':f['plan_sha256']='bad'
    elif fault=='context':write(out/'n23-worker-context.json',{'plan':{'path':str(c.PLAN),'sha256':'bad'}})
    elif fault=='receipt':f['n23_worker_receipt']={'path':receipt['path'],'sha256':'bad'}
    elif fault=='identity':f['identity']['policy_seed']+=1
    elif fault=='budget':f['budget_bucket']='development'
    elif fault=='cost':f['required_cost_telemetry_complete']=False
    elif fault=='zero_gate':f['guided_chunks']=0;write(out/'attempt-result.json',f)
    if fault is None:assert c.accepted_cell(p,row,events,tmp_path,vars(r))==f and calls==['receipt',('native','N27',1)]
    else:
        with pytest.raises(ValueError):c.accepted_cell(p,row,events,tmp_path,vars(r))
    if fault=='zero_gate':assert calls==['receipt',('native','N27',0)]

@pytest.mark.parametrize('fault',[None,'missing_adoption','caps','protected','resource','hold','gpu'])
def test_state_admission_exact_caps(fixture,tmp_path,monkeypatch,fault):
    budget={'caps':c.CAPS,'amendment':{'synthetic':True}};write(tmp_path/'budget.json',budget);fixture['budget_authority']=c.ref(tmp_path/'budget.json')
    record={'source':{},'runtime':{},'budget_authority':fixture['budget_authority']};write(c.AUTHORITY,record)
    # Source/review authority is tested separately; this test checks actual state constraints.
    def auth(source,runtime,root,state):
        w.require(state.get('n27_hydra_continuation_authority')==c.ref(c.AUTHORITY),'adoption required');return record
    monkeypatch.setattr(c,'authority',auth)
    state={'n27_hydra_continuation_authority':c.ref(c.AUTHORITY),'n26_budget_authority':fixture['budget_authority'],
        'budget':{'max_episode_attempts':522,'max_gpu_hours':100.,'reserved':copy.deepcopy(c.CAPS['buckets']),
            'gpu_hour_reservations':copy.deepcopy(c.CAPS['protected_gpu_hours']),'amendment':budget['amendment']},
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},'max_concurrent_gpu_workers':1,'gpu_pool':[7]}
    if fault=='missing_adoption':state.pop('n27_hydra_continuation_authority')
    elif fault=='caps':state['budget']['reserved']['development']+=1
    elif fault=='protected':state['budget']['gpu_hour_reservations']['validation']-=1
    elif fault=='resource':state['resource_isolation']['private_budget']=False
    elif fault=='hold':state['external_resource_hold']={'do_not_auto_resume':True}
    elif fault=='gpu':state['gpu_pool']=[3]
    if fault is None:c.require_state(state,vars(r))
    else:
        with pytest.raises((ValueError,r.GateError)):c.require_state(state,vars(r))

@pytest.mark.parametrize('fault',[None,'caps','source','protocol','limits','missing','extra'])
def test_authority_exact_schema(fixture,tmp_path,monkeypatch,fault):
    runtime=fixture['runtime'];source={'commit':'new','files':[]};review={'path':str(tmp_path/'review'),'sha256':'x'*64}
    monkeypatch.setattr(c,'final_review',lambda *a:review)
    budget={'caps':c.CAPS};write(tmp_path/'budget',budget);fixture['budget_authority']=c.ref(tmp_path/'budget')
    monkeypatch.setattr(c,'PROTOCOL',tmp_path/'protocol');(tmp_path/'protocol').write_text('synthetic')
    data={'schema':'n27-hydra-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':runtime,'protocol':c.ref(c.PROTOCOL),
        'seal':c.ref(c.SEAL),'final_review':review,'budget_authority':fixture['budget_authority'],'caps':copy.deepcopy(c.CAPS),
        'limits':copy.deepcopy(c.LIMITS),'old_gpu_seconds':fixture['old_gpu_seconds'],'validation_authorized':False,'formal_authorized':False,
        'recorded_at':'synthetic','authority_interpretation':'synthetic only'}
    if fault=='caps':data['caps']['attempts']+=1
    elif fault=='source':data['source']={'commit':'wrong'}
    elif fault=='protocol':data['protocol']['sha256']='bad'
    elif fault=='limits':data['limits']['additional_retries']=1
    elif fault=='missing':data.pop('final_review')
    elif fault=='extra':data['executable']=False
    write(c.AUTHORITY,data)
    if fault is None:assert c.authority(source,runtime,tmp_path)==data
    else:
        with pytest.raises(ValueError):c.authority(source,runtime,tmp_path)
