"""Synthetic protected-validation readiness; no real outcome inputs or release."""
import copy
import json
from pathlib import Path
import pytest
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n24_contract as dev
from scripts import qd_ed_n24_report as dev_report
from scripts import qd_ed_n24_validation_contract as c
from scripts import qd_ed_n24_validation_identity as identity
from scripts import qd_ed_n24_validation_bridge as bridge
from scripts import qd_ed_n24_validation_prepare as prep
from scripts import qd_ed_n24_validation_evidence as evidence
from scripts import qd_ed_n24_validation_recovery as recovery
from test_qd_ed_n24_controller import write,rows as dev_rows,metric,native_report,state


def seeds():
    blocks={}
    for i,name in enumerate(['dev','formal']+[f'validation_c{a}_b{b}' for a in range(1,5) for b in (1,2)]):
        blocks[name]=[dict(task_id=t,env_seed=1000*i+t,policy_seed=20000+1000*i+t,init_index=0,
            init_row_sha256=f'{t:064x}',init_file_sha256='a'*64,bddl_sha256='b'*64) for t in range(10)]
    return {'backend_task_order':list(range(10)),'blocks':blocks}


def events_for(row,aid='fixture',*,valid=True,success=False,retry=None):
    base={'attempt_id':aid,'identity':r.episode_identity(row),'episode_key':row['episode_key'],
        'budget_bucket':'recovery' if retry else row['budget_bucket'],'retry_of':retry}
    return [{**base,'event':'reserved'},{**base,'event':'dispatched'},{**base,'event':'valid','outcome_valid':valid,
        'success':success,'gpu_process_wall_seconds':1.,'guided_chunks':1,'candidate_evaluations':176,'score_batches':11,
        'required_cost_telemetry_complete':valid,'provider_logical_call_attempts':2,'provider_usage_complete_calls':2 if valid else 1,
        'provider_token_usage_complete':valid}]


def test_matrix_route_preserves_dev_and_native_binding():
    rows=identity.rows_for(seeds(),'c2')
    assert [(x['seed_block'],x['task_id'],x['profile']) for x in rows]==[(f'validation_c2_b{b}',t,a) for b in (1,2) for t in range(10) for a in c.ARMS]
    assert len(rows)==60 and all(x['split']==x['budget_bucket']=='validation' for x in rows)
    plan={'n24_validation':{},'n24_cohort':c.WORKER_MARKER,'candidate_profiles':{'N24':{}}}
    assert r.metered_plan(plan) and r.typed_metered_plan(plan) and r.metered_support(plan) is c
    assert not any(f(plan) for f in (r.is_n24_plan,r.is_n23_plan,r.is_n23_v2_plan,r.is_n7_plan))
    assert r.metered_support({'n24_cohort':{},'candidate_profiles':{'N23':{},'N24':{}}}) is dev


@pytest.mark.parametrize('source',['history','registry','reserved','dispatched'])
def test_any_exposure_consumes_entire_cohort(source):
    seed=seeds();pair=identity.pair(seed['blocks']['validation_c1_b2'][9])
    hist=[{'pair':pair}] if source=='history' else []
    registry=[{'pair':pair}] if source in {'registry','dispatched'} else []
    ledger=[{'pair':pair,'attempt_id':'old','iteration':'old','profile':'C0','split':'validation','event':source}] if source in {'reserved','dispatched'} else []
    assert identity.first_unused(seed,hist,registry,ledger)=='c2'
    if source=='dispatched':
        with pytest.raises(ValueError,match='reconciliation'):identity.first_unused(seed,[],[],ledger)


@pytest.mark.parametrize('fault',['duplicate','task_order','policy_missing','all_used','previous_candidate','own_initial','foreign_overlap'])
def test_no_substitution_or_second_validation(fault):
    seed=seeds();pair=identity.pair(seed['blocks']['validation_c1_b1'][0]);hist=[];registry=[];ledger=[]
    if fault=='duplicate':seed['blocks']['validation_c1_b2'][0]['env_seed']=pair[1]
    if fault=='task_order':seed['backend_task_order'].reverse()
    if fault=='policy_missing':seed['blocks']['validation_c1_b1'][0]['policy_seed']=None
    if fault=='all_used':hist=[{'pair':identity.pair(seed['blocks'][f'validation_c{i}_b1'][0])} for i in range(1,5)]
    if fault in {'previous_candidate','own_initial','foreign_overlap'}:
        ledger=[{'pair':pair,'attempt_id':'prior','iteration':'OTHER' if fault=='previous_candidate' else c.COHORT,'profile':'N24','split':'validation','event':'dispatched'}]
        registry=[{'pair':pair,'attempt_id':'prior','cohort_id':ledger[0]['iteration']}]
    if fault=='foreign_overlap':
        registry.append({'pair':pair,'attempt_id':'foreign','cohort_id':'OTHER'})
        assert identity.first_unused(seed,hist,registry,ledger,allow_own=True)=='c2'
    else:
        with pytest.raises(ValueError):identity.first_unused(seed,hist,registry,ledger)


def test_metadata_only_projection_and_exposure_append(tmp_path,monkeypatch):
    seed=write(tmp_path/'seed.json',seeds());data=tmp_path/'data'
    history=write(data/'historical-exposure-inventory.jsonl',[{'task_id':0,'episode_seed':9,'success':'PROTECTED_SENTINEL'}],True)
    monkeypatch.setattr(identity,'HISTORY_SHA',history['sha256']);write(data/'exposure-registry.jsonl',[],True)
    write(data/'attempt-ledger.jsonl',[{'event':'dispatched','attempt_id':'a','identity':{'task_id':0,'env_seed':9,'split':'validation','iteration':'OLD','profile':'C0'},'success':'PROTECTED_SENTINEL'},
        {'event':'valid','attempt_id':'a','success':'PROTECTED_SENTINEL'}],True)
    value=identity.metadata(tmp_path,{'seed_plan_path':seed['path'],'seed_plan_sha256':seed['sha256']})
    assert 'PROTECTED_SENTINEL' not in json.dumps(value) and value[-1]['protected_outcomes_read'] is False
    row=identity.rows_for(seeds(),'c2')[0];event=events_for(row)[1]
    event.update(n24_validation_seed_block=row['seed_block'],init_row_sha256=row['init_row_sha256'])
    identity.register_dispatch(tmp_path,event)
    stored=json.loads((data/'exposure-registry.jsonl').read_text());assert stored['attempt_id']=='fixture' and stored['outcomes_read'] is False
    assert not any(k in stored for k in ('success','reward','native'))


@pytest.mark.parametrize('fault',['none','budget','bucket','hold','gpu','resource','missing_authority'])
def test_separate_validation_budget_authority(tmp_path,monkeypatch,fault):
    st=state();monkeypatch.setattr(c,'original_plan',lambda:{})
    monkeypatch.setattr(c,'source_record',lambda *a:({},{}));seen=[]
    monkeypatch.setattr(c,'authority',lambda *a:(c.require(fault!='missing_authority','missing') or seen.append(a)))
    if fault=='budget':st['budget']['max_episode_attempts']=479
    if fault=='bucket':st['budget']['reserved']['formal']=39
    if fault=='hold':st['external_resource_hold']={'do_not_auto_resume':True}
    if fault=='gpu':st['gpu_pool']=[3]
    if fault=='resource':st['resource_isolation']['private_budget']=False
    if fault=='none':c.require_budget_state(st,vars(r));assert seen
    else:
        with pytest.raises((ValueError,r.GateError)):c.require_budget_state(st,vars(r))


@pytest.mark.parametrize('fault',['none','hours','validation','recovery','formal_attempts','running','unsettled'])
def test_full_matrix_and_formal_reserve(fault,monkeypatch):
    monkeypatch.setattr(c,'require_budget_state',lambda *a:None);snap=r.budget_snapshot([]);snap['gpu_hours_consumed']=55.;events=[]
    if fault=='hours':snap['gpu_hours_consumed']=57.
    if fault=='validation':snap['by_bucket']['validation']=121
    if fault=='recovery':snap['by_bucket']['recovery']=19
    if fault=='formal_attempts':snap['dispatched']=377
    if fault=='running':snap['running']=1
    if fault=='unsettled':events=events_for(identity.rows_for(seeds(),'c2')[0])[:2]
    env=dict(vars(r),budget_snapshot=lambda *a:snap)
    if fault=='none':c.full_capacity(state(),events,[],env)
    else:
        with pytest.raises((ValueError,r.GateError)):c.full_capacity(state(),events,[],env)


def test_exact_reversible_source_changes_and_worker_functions():
    original_root=Path(r.ROOT).parent/'implementation'
    before=(original_root/'scripts/qd_ed_n23_worker.py').read_text();after=(r.ROOT/'scripts/qd_ed_n23_worker.py').read_text()
    assert after.count(bridge.WORKER_INSERT)==1 and after.replace(bridge.WORKER_INSERT,'',1)==before
    before=(original_root/'scripts/qd_ed_final_runner.py').read_text();after=(r.ROOT/'scripts/qd_ed_final_runner.py').read_text()
    for old,new,count in reversed(bridge.RUNNER_EDITS):assert after.count(new)==count;after=after.replace(new,old,count)
    assert after==before


@pytest.mark.parametrize('fault',['none','core','worker_run','old_runner','manifest'])
def test_source_bridge_all230_scope(fault,monkeypatch):
    original_root=Path(r.ROOT).parent/'implementation'
    source=json.loads((original_root.parent/'source-manifest-controller-v1.json').read_text())
    parent={'source_commit':source['commit'],'code_files':source['files']}
    monkeypatch.setattr(bridge,'original',lambda root,path:(original_root/path).read_bytes())
    monkeypatch.setattr(bridge.subprocess,'check_output',lambda *a,**k:'scripts/qd_ed_n23_worker.py\nscripts/qd_ed_final_runner.py\n')
    original=Path.read_bytes
    def read(path):
        data=original(path)
        if fault=='core' and path==r.ROOT/'core/qd_gripper_parent_rescue.py':return data+b'\n# changed'
        if fault=='worker_run' and path==r.ROOT/'scripts/qd_ed_n23_worker.py':return data.replace(b'def run_worker(',b'def changed_worker(')
        if fault=='old_runner' and path==r.ROOT/'scripts/qd_ed_final_runner.py':return data+b'\n# changed'
        return data
    monkeypatch.setattr(Path,'read_bytes',read)
    if fault=='manifest':parent['code_files']=parent['code_files'][:-1]
    if fault=='none':bridge.verify_delta(r.ROOT,parent)
    else:
        with pytest.raises(ValueError):bridge.verify_delta(r.ROOT,parent)


@pytest.fixture
def promoted_dev(tmp_path,monkeypatch):
    root=tmp_path/'root';path=root/'scripts/qd_ed_n24_report.py';path.parent.mkdir(parents=True);path.write_bytes((r.ROOT/'scripts/qd_ed_n24_report.py').read_bytes())
    parent={'source_commit':c.DEV_COMMIT,'episodes':dev_rows(),'code_files':[{'path':'scripts/qd_ed_n24_report.py','sha256':w.sha(path)}]}
    planref=write(tmp_path/'dev-plan.json',parent);monkeypatch.setattr(c,'DEV_PLAN',Path(planref['path']));monkeypatch.setattr(c,'original_plan',lambda:parent)
    for key,name in [('DEV_RESULT','result.json'),('DEV_STATUS','status.json'),('DEV_REVIEW','review.json')]:monkeypatch.setattr(c,key,tmp_path/name)
    events=[];entries={};native={}
    for i,row in enumerate(parent['episodes']):
        group=events_for(row,str(i),success=row['profile']=='N24' and row['task_id']<5);final=group[-1];out=tmp_path/'outputs'/str(i)
        final['output_dir']=str(out);events+=group;entries[row['episode_key']]=final
        native[row['episode_key']]=native_report(row['profile'])
        write(out/'eds_eval/eds_metrics.jsonl',[metric(row['profile'])],True)
        write(out/'eds_eval/episode_compute.jsonl',[{'policy_counters_available':True,'guided_chunks':1}],True)
        for name in ('attempt-result.json','eds_eval/decision-evidence-audit.json','eds_eval/in-worker-audit-receipt.json','n23-worker-context.json'):write(out/name,final if name=='attempt-result.json' else {})
    monkeypatch.setattr(recovery,'historical_dev_cell',lambda plan,row,*a:entries[row['episode_key']])
    monkeypatch.setattr(evidence,'historical_receipt',lambda final,row,*a:native[row['episode_key']])
    monkeypatch.setattr(evidence,'historical_backend',lambda *a:None)
    monkeypatch.setattr(r,'read_events',lambda path:events)
    def accept(row,local):
        final=entries[row['episode_key']];out=Path(final['output_dir'])
        counts,aux=c.native.from_output(row['profile'],out,native[row['episode_key']],1)
        return {'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'attempt_id':final['attempt_id'],'success':final['success'],
            'audit':c.ref(out/'eds_eval/decision-evidence-audit.json'),'worker_context':c.ref(out/'n23-worker-context.json'),
            'worker_receipt':c.ref(out/'eds_eval/in-worker-audit-receipt.json'),'attempt_result':c.ref(out/'attempt-result.json')},counts,aux
    result=dev_report.analyze(parent,events,accept)
    prefix=[x['episode_key'] for x in result['accepted_cells']]
    outcomes=[{'episode_key':x['episode_key'],'task_id':x['task_id'],'profile':x['profile'],'success':x['success'],'attempt_id':x['attempt_id'],'recovered':False} for x in result['accepted_cells']]
    status={'schema':'n24-dev-supervisor-status-v1','status':'completed_all_forty_audited','cohort_id':dev.COHORT,'source_commit':c.DEV_COMMIT,
        'plan':planref,'completed_keys':prefix,'dev_gate_promoted':True,'attempts':result['attempts'],'outcomes':outcomes,
        'successes':{a:result['counts'][a]['success'] for a in dev.ARMS},'native':result['native'],'auxiliary':result['auxiliary'],**dev_report.summary(outcomes,result['attempts'])}
    write(c.DEV_STATUS,status);snapshot=write(tmp_path/'dev-only-ledger.json',events);source_bridge=write(tmp_path/'bridge.json',{})
    result.update(plan=planref,terminal_status={**c.ref(c.DEV_STATUS),'content':status},ledger_snapshot=snapshot,reader=c.ref(path),source_bridge=source_bridge,
        controller_evidence={'completed_keys':prefix,'journal_accepted_keys':prefix,'consistent':True,'status_phase':'completed_all_forty_audited'})
    write(c.DEV_RESULT,result)
    review={'schema':'n24-dev-promotion-review-v1','disposition':'promoted','dev_plan':planref,'dev_status':c.ref(c.DEV_STATUS),
        'dev_result':c.ref(c.DEV_RESULT),'dev_source_bridge':source_bridge,'allow_validation':True};write(c.DEV_REVIEW,review)
    return root,parent,result,status,review,entries,native


@pytest.mark.parametrize('fault',['none','incomplete','invalid','root_reject','source','reader','status','counts','cost','guided_missing','result_plan','prefix_mismatch','path_alias'])
def test_actual_dev_result_schema_promotion_recomputed(promoted_dev,fault):
    root,parent,result,status,review,entries,native=promoted_dev
    if fault=='incomplete':result['audited_cells']=39
    if fault=='invalid':result['decision']='INVALID_OR_INTERRUPTED'
    if fault=='root_reject':review['allow_validation']=False
    if fault=='source':result['source_commit']='wrong'
    if fault=='reader':result['reader']['sha256']='wrong'
    if fault=='status':status['status']='failed'
    if fault=='counts':result['counts']['N24']['success']=6
    if fault=='cost':result['all_attempt_costs']['N24']['gpu_process_wall_seconds']['observed_total']+=1
    if fault=='guided_missing':native[parent['episodes'][3]['episode_key']].pop('n24_gripper_parent_rescue_audit')
    if fault=='result_plan':result['plan']['sha256']='other'
    if fault=='prefix_mismatch':result['controller_evidence']['consistent']=False
    write(c.DEV_STATUS,status);review['dev_status']=c.ref(c.DEV_STATUS);result['terminal_status']={**c.ref(c.DEV_STATUS),'content':status}
    if fault=='path_alias':
        alias=c.DEV_STATUS.parent/'logical-status.json';alias.symlink_to(c.DEV_STATUS)
        result['terminal_status']['path']=str(alias)
    write(c.DEV_RESULT,result);review['dev_result']=c.ref(c.DEV_RESULT);write(c.DEV_REVIEW,review)
    if fault in {'none','path_alias'}:assert c.dev_promotion(root,vars(r))==c.ref(c.DEV_REVIEW)
    else:
        with pytest.raises((ValueError,r.GateError)):c.dev_promotion(root,vars(r))

@pytest.fixture
def validation_draft(tmp_path,monkeypatch):
    parent={'source_commit':c.DEV_COMMIT,'code_files':[],'candidate_profiles':{'N24':{'path':str(r.ROOT/'configs/qd_ed_final/candidate_n24.json'),
        'sha256':w.sha(r.ROOT/'configs/qd_ed_final/candidate_n24.json')}},'episodes':dev_rows(),
        'runtime_manifest_path':str(tmp_path/'runtime.json'),'runtime_manifest_sha256':write(tmp_path/'runtime.json',{})['sha256']}
    source={'commit':'synthetic','files':[],'sha256':w.canonical_sha([])};source_bridge={'synthetic':True}
    monkeypatch.setattr(c,'original_plan',lambda:parent);monkeypatch.setattr(c,'source_record',lambda *a:(source,source_bridge))
    monkeypatch.setattr(c,'VALIDATION_PLAN',tmp_path/'validation-plan.json')
    monkeypatch.setattr(c,'dev_promotion',lambda *a:{'dev-review':True});monkeypatch.setattr(c,'review_source',lambda *a:{'source-review':True})
    auth=write(tmp_path/'authority.json',{'seed_cohort':'c2'});monkeypatch.setattr(c,'authority',lambda *a:auth)
    monkeypatch.setattr(c,'require_budget_state',lambda *a:None);monkeypatch.setattr(r,'read_state',lambda *a:{'n24_validation_authority':auth})
    monkeypatch.setattr(dev,'validate_runtime',lambda *a:None)
    monkeypatch.setattr(identity,'metadata',lambda *a:(seeds(),[],[],[],{}));monkeypatch.setattr(identity,'first_unused',lambda *a,**k:'c2')
    plan=prep.build_plan(parent,seeds(),'c2',source=source,source_bridge=source_bridge,
        dev_review={'dev-review':True},source_review={'source-review':True},authorization=auth,selection={})
    profiles={'profiles':dict.fromkeys(c.ARMS,{})}
    return plan,profiles,parent,source,source_bridge


@pytest.mark.parametrize('fault',['none','draft','row','source','mode_marker','phase','profile','runtime','freshness','missing_promotion','missing_adoption','metadata'])
def test_frozen_contract_closes_matrix_source_and_freshness(validation_draft,monkeypatch,fault):
    plan,profiles,parent,source,source_bridge=validation_draft
    plan['frozen']=True
    if fault=='draft':plan['frozen']=False
    if fault=='row':plan['episodes'][59]['env_seed']+=1
    if fault=='source':plan['source_commit']='different'
    if fault=='mode_marker':plan['n24_cohort']={}
    if fault=='phase':plan['phase_authorization']['formal']=True
    if fault=='profile':plan['candidate_profiles']['N24']['sha256']='wrong'
    if fault=='runtime':plan['runtime_manifest_sha256']='wrong'
    if fault=='freshness':monkeypatch.setattr(identity,'first_unused',lambda *a,**k:'c3')
    if fault=='missing_promotion':monkeypatch.setattr(c,'dev_promotion',lambda *a:(_ for _ in ()).throw(ValueError('no promotion')))
    if fault=='missing_adoption':monkeypatch.setattr(c,'require_budget_state',lambda *a:(_ for _ in ()).throw(ValueError('no adoption')))
    if fault=='metadata':plan['n24_validation']['protocol']['sha256']='changed'
    write(c.VALIDATION_PLAN,plan)
    if fault=='none':c.validate_contract(plan,profiles,{},seeds(),r.ROOT,vars(r))
    else:
        with pytest.raises((ValueError,r.GateError)):c.validate_contract(plan,profiles,{},seeds(),r.ROOT,vars(r))


@pytest.mark.parametrize('fault',['none','missing','rootreview','source','runtime','caps','scope','seed','adopted','formal'])
def test_exact_separate_authority_and_non_circular_root_review(tmp_path,monkeypatch,fault):
    parent={'runtime_manifest_path':str(tmp_path/'runtime.json'),'runtime_manifest_sha256':'runtime'}
    source={'commit':'synthetic','files':[],'sha256':'source'};source_bridge={'dev_source':'old','validation_source':source}
    for key in ('DEV_PLAN','DEV_REVIEW','SOURCE_REVIEW','AUTHORITY'):monkeypatch.setattr(c,key,tmp_path/(key+'.json'))
    write(c.DEV_PLAN,{});write(c.DEV_REVIEW,{'dev_source_bridge':{'old-proof':True}})
    review={'schema':'n24-validation-source-review-v1','disposition':'accepted','dev_plan':c.ref(c.DEV_PLAN),
        'protocol':c.ref(c.PROTOCOL),'source':source,'source_bridge':source_bridge,'runtime':{'path':parent['runtime_manifest_path'],'sha256':'runtime'},
        'dev_source_bridge':{'old-proof':True},'no_execution_release':True}
    if fault=='rootreview':review['no_execution_release']=False
    write(c.SOURCE_REVIEW,review)
    auth={'schema':'n24-validation-authority-v1','cohort_id':c.COHORT,'seed_cohort':'c2','source':copy.deepcopy(source),
        'dev_review':c.ref(c.DEV_REVIEW),'source_review':c.ref(c.SOURCE_REVIEW),'protocol':c.ref(c.PROTOCOL),'runtime':copy.deepcopy(review['runtime']),
        'limits':copy.deepcopy(c.LIMITS),'caps':copy.deepcopy(dev.CAPS),'recorded_at':'synthetic','authority_interpretation':'synthetic',
        'validation_authorized':True,'formal_authorized':False}
    if fault=='source':auth['source']['commit']='old'
    if fault=='runtime':auth['runtime']['sha256']='wrong'
    if fault=='caps':auth['caps']['attempts']=479
    if fault=='scope':auth['limits']['recoveries']=3
    if fault=='seed':auth['seed_cohort']='c5'
    if fault=='formal':auth['formal_authorized']=True
    if fault!='missing':write(c.AUTHORITY,auth)
    st={'n24_validation_authority':c.ref(c.AUTHORITY)} if fault!='missing' else {}
    if fault=='adopted':st={}
    if fault=='none':assert c.authority(source,source_bridge,parent,st)==c.ref(c.AUTHORITY)
    else:
        with pytest.raises((OSError,ValueError)):c.authority(source,source_bridge,parent,st)
