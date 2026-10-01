"""Conditional N26 provenance composition only; all histories are synthetic."""
import ast,copy,hashlib,json
from contextlib import nullcontext
from pathlib import Path
import pytest
from scripts import qd_ed_n26_logical as l,qd_ed_n26_contract as c,qd_ed_n26_bridge as bridge
from scripts import qd_ed_n26_backend as backend,qd_ed_n26_prepare as prep,qd_ed_n26_supervise as sup
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w
from n26_logical_fixtures import gate_fixture,put,ACTUAL


@pytest.mark.parametrize('kind',['reject','futility'])
def test_actual_common_composition_rejects_only(tmp_path,monkeypatch,kind):
    record,evidence,data,calls=gate_fixture(tmp_path,monkeypatch,kind)
    assert c.predecessor()==c.ref(c.PREDECESSOR)
    assert len(calls)==2 and evidence['cost_coverage']['combined']['unknown_token_calls']==6
    assert evidence['allow_validation'] is evidence['allow_n26'] is False
    assert evidence['accepted_mapping'][18]['origin']=='new_successor'
    assert evidence['settled_original_resource']['new_proof_executed'] is False


@pytest.mark.parametrize('fault',['original_invalid','continuation_invalid','promotion','validation_rejection','missing_named_gate','old_fallback',
 'missing_root_review','wrong_root_review','changed_evidence','lost_unknown','status_disagreement','wrong_runtime','wrong_proof','wrong_reader','wrong_addendum','wrong_gate_shape'])
def test_logical_predecessor_has_no_permissive_path(tmp_path,monkeypatch,fault):
    record,evidence,data,_=gate_fixture(tmp_path,monkeypatch)
    if fault in {'original_invalid','continuation_invalid','promotion','validation_rejection'}:
        record['logical_disposition']={'original_invalid':'INVALID_OR_INTERRUPTED','continuation_invalid':'INVALID_OR_INTERRUPTED','promotion':'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION','validation_rejection':'VALIDATION_REJECT'}[fault];put(c.PREDECESSOR,record)
    elif fault in {'missing_named_gate','old_fallback'}:
        c.PREDECESSOR.unlink()
        if fault=='old_fallback':put(c.RUN_DIR/'predecessor-review-v1.json',{'schema':'n26-predecessor-review-v1','disposition':'VALID_DEV_REJECTION','allow_n26':True})
    elif fault=='missing_root_review':Path(record['continuation_root_review']['path']).unlink()
    elif fault in {'wrong_root_review','wrong_runtime','wrong_proof','wrong_reader','wrong_addendum'}:
        key={'wrong_root_review':'continuation_root_review','wrong_runtime':'runtime','wrong_proof':'historical_backend_proof','wrong_reader':'common_reader','wrong_addendum':'admission_addendum'}[fault]
        record[key]={**record[key],'sha256':'0'*64};put(c.PREDECESSOR,record)
    elif fault=='wrong_gate_shape':record['allow_validation']=True;put(c.PREDECESSOR,record)
    elif fault=='status_disagreement':
        p=Path(data['references']['status']['path']);v=json.loads(p.read_text());v['status']='failed';put(p,v)
    else:
        if fault=='lost_unknown':evidence['cost_coverage']['combined']['unknown_token_calls']=0
        else:evidence['counts']['N25']['success']+=1
        record['common_evidence']=put(record['common_evidence']['path'],evidence);put(c.PREDECESSOR,record)
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):c.predecessor()


@pytest.mark.parametrize('fault',['none','later_dev_reservation','later_resource_reservation','changed_event','unrelated_appends'])
def test_release_current_matching_projection_hook(tmp_path,monkeypatch,fault):
    _,evidence,data,_=gate_fixture(tmp_path,monkeypatch,'futility')
    jp=json.loads(Path(data['references']['journal_projection']['path']).read_text());rp=json.loads(Path(data['references']['resource_projection']['path']).read_text())
    events=jp['original_events']+jp['continuation_events'];resources=rp['events']
    if fault=='later_dev_reservation':events.append({**events[-1],'event':'reserved','attempt_id':'later'})
    if fault=='later_resource_reservation':resources.append({**resources[0],'resource_id':'other','event':'reserved'})
    if fault=='changed_event':events[-1]['success']=not events[-1]['success']
    if fault=='unrelated_appends':
        events.append({'identity':{'iteration':'NEW_LEGITIMATE_COHORT'},'event':'valid'})
        resources.append({'kind':'UNRELATED_RESOURCE','resource_id':'unrelated','event':'completed'})
    if fault in {'none','unrelated_appends'}:assert l.current_matching(events,resources)==c.ref(c.PREDECESSOR)
    else:
        with pytest.raises(ValueError,match='later/changed'):l.current_matching(events,resources)


def test_exact_science_shared_and_provenance_byte_composition(monkeypatch):
    accepted,common=l.manifests(ACTUAL);expected={}
    for source in (accepted,common):
        for row in source['files']:
            p=row['path']
            if source['commit']==l.COMMON and p in {q['path'] for q in accepted['files']}:continue
            b=l.restore_shared(ACTUAL,p) if p in l.SHARED else l.restore_provenance(ACTUAL,p) if p in l.PROVENANCE_FUNCTIONS else (ACTUAL/p).read_bytes()
            assert hashlib.sha256(b).hexdigest()==row['sha256'];expected[source['commit']+':'+p]=b
    monkeypatch.setattr(l.subprocess,'check_output',lambda args,**kw:expected[args[2]])
    source={'files':[{'path':p} for p in sorted(l.source_paths(ACTUAL))]}
    value=l.verify_composition(ACTUAL,source)
    assert len(value['accepted_unchanged'])==280 and len(value['common_administrative_unchanged'])==19
    worker='scripts/qd_ed_n23_worker.py';functions=bridge.functions
    before=functions(l.restore_shared(ACTUAL,worker).decode());after=functions((ACTUAL/worker).read_text())
    assert before['run_worker']==after['run_worker'] and before['verify_receipt']==after['verify_receipt']
    assert value['historical_proof_relabelled'] is False


@pytest.mark.parametrize('path',['scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'])
def test_shared_union_preserves_only_reviewed_insertions(path):
    a=bridge.functions(l.restore_shared(ACTUAL,path).decode());z=bridge.functions((ACTUAL/path).read_text())
    wanted={'metered_support','check_budget','check_retry'} if path.endswith('final_runner.py') else {'validate_context'}
    assert set(a)==set(z) and {k for k in a if a[k]!=z[k]}==wanted
    assert all('n25_infrastructure_continuation' in z[k] or 'N25_ACTUATOR_CLIPPED_RBF_DEV_INFRA_CONTINUATION' in z[k] for k in wanted)


def test_mixed_continuation_n26_marker_cannot_bypass_exact_plan(tmp_path,monkeypatch):
    _,_,data,_=gate_fixture(tmp_path,monkeypatch)
    cont=l.common.c;seal=json.loads(Path(data['references']['seal']['path']).read_text());plan=json.loads(Path(data['references']['plan']['path']).read_text())
    plan['n26_cohort']={'schema':'forged'}
    assert r.metered_support(plan) is cont
    monkeypatch.setattr(cont,'history',lambda:seal);monkeypatch.setattr(cont,'source_paths',lambda rr:{x['path'] for x in plan['code_files']})
    monkeypatch.setattr(cont.w,'source_record',lambda *a:{'commit':plan['source_commit'],'files':plan['code_files']})
    monkeypatch.setattr(cont.old,'imports_owned',lambda *a:None)
    monkeypatch.setattr(cont,'metadata',lambda *a:plan['n25_infrastructure_continuation'])
    with pytest.raises(ValueError,match='original plan/runtime/science changed'):cont.validate_contract(plan,{}, {},{},Path(data['owning_root']),{'ROOT':data['owning_root']})


@pytest.mark.parametrize('entry',['backend','freeze','launch','per_cell'])
def test_existing_admission_chain_always_reaches_current_hook(tmp_path,monkeypatch,entry):
    from test_qd_ed_n26_controller import rows,state
    calls=[]
    class Reached(Exception):pass
    def hook(events,resources):calls.append((events,resources));raise Reached()
    monkeypatch.setattr(l,'current_matching',hook)
    monkeypatch.setattr(c,'require_state',lambda *a:None);monkeypatch.setattr(c,'require_budget_state',lambda *a:None)
    monkeypatch.setattr(c,'budget_authority',lambda:{'caps':c.BASE_CAPS});monkeypatch.setattr(c,'validate_runtime',lambda *a:None)
    monkeypatch.setattr(c,'RUN_DIR',tmp_path);monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge.json');put(c.BRIDGE,{})
    monkeypatch.setattr(c,'AUTHORITY',tmp_path/'authority.json');put(c.AUTHORITY,{'local_gpu_hours':1.})
    rt=put(tmp_path/'runtime.json',{});monkeypatch.setattr(c,'runtime_ref',lambda:rt)
    source={'commit':'synthetic','files':[]};plan={'episodes':rows(),'source_commit':'synthetic','n26_cohort':{'authority':c.ref(c.AUTHORITY)}}
    planpath=tmp_path/'plan.frozen.v1.gpu7.json';put(planpath,plan)
    monkeypatch.setattr(r,'read_state',lambda *a:state());monkeypatch.setattr(r,'read_events',lambda *a:[])
    monkeypatch.setattr(r,'locked',lambda *a,**k:nullcontext())
    monkeypatch.setattr(c,'final_review',lambda *a:{});monkeypatch.setattr(c,'authority',lambda *a:{})
    monkeypatch.setattr(w,'source_record',lambda *a:source);monkeypatch.setattr(c,'source_paths',lambda *a:set())
    monkeypatch.setattr(backend,'authority',lambda *a:{})
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(plan,{},{}));monkeypatch.setattr(sup,'ROOT',tmp_path)
    release=tmp_path/'execution-release-v1.json';put(release,{'schema':'n26-dev-execution-release-v1','plan':c.ref(planpath),
        'source_commit':'synthetic','cohort_id':c.COHORT,'episode_keys':[x['episode_key'] for x in plan['episodes']],
        'authority':plan['n26_cohort']['authority'],'physical_gpu':7,'limits':c.LIMITS,'validation_authorized':False,'formal_authorized':False})
    with pytest.raises(Reached):
        if entry=='backend':backend.admission(state(),[],[],vars(r),source,rt,tmp_path,reservation_events=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':c.BASE_CAPS['protected_gpu_hours']}])
        elif entry=='freeze':prep.freeze(planpath,root=tmp_path)
        elif entry=='launch':sup.launch(planpath,release,tmp_path/'execution/supervisor-status-v1.json')
        else:c.protected_budget(state(),[],[],rows()[0],1800,vars(r),plan=plan)
    assert calls==[([],[])]


def test_prospective_matrix_and_logical_gate_remain_disabled(tmp_path,monkeypatch):
    from test_qd_ed_n26_controller import draft,rows
    monkeypatch.setattr(c,'LOGICAL_PROTOCOL',ACTUAL/l.DOC/'protocol-v1.md')
    plan=draft.__wrapped__(tmp_path,monkeypatch)
    assert plan['episodes']==rows() and len(plan['episodes'])==40 and not plan['frozen']
    assert plan['n26_cohort']['logical_predecessor'] is None and plan['n26_cohort']['authority'] is None
    assert plan['n26_cohort']['composition_protocol']==c.ref(c.LOGICAL_PROTOCOL)
    assert plan['phase_authorization']=={'dev':True,'validation':False,'formal':False}
    assert {(x['timeout_seconds'],x['profile']) for x in plan['episodes']}=={(1800,a) for a in c.ARMS}


@pytest.mark.parametrize('fault',['none','review_protocol','missing_addendum','proof_missing','authority_missing_logical','authority_wrong_gate','authority_protocol'])
def test_final_review_and_authority_close_new_provenance(tmp_path,monkeypatch,fault):
    source={'commit':'new-final-source','files':[],'sha256':'s'};runtime=put(tmp_path/'runtime.json',{})
    for name in ('FINAL_REVIEW','AUTHORITY','BRIDGE','PROTOCOL','SOURCE_PLAN','PREDECESSOR','BACKEND_PROOF','ARITHMETIC_PROTOCOL','CLARIFICATION','BUDGET_AUTHORITY','LOGICAL_PROTOCOL'):
        p=tmp_path/name;put(p,{});monkeypatch.setattr(c,name,p)
    put(tmp_path/l.DOC/'admission-addendum-v1.md',{})
    monkeypatch.setattr(c,'require_protocols',lambda root:None)
    monkeypatch.setattr(c,'predecessor',lambda:c.ref(c.PREDECESSOR));monkeypatch.setattr(c,'budget_authority',lambda:{'caps':c.BASE_CAPS})
    monkeypatch.setattr(bridge,'verify',lambda *a:{'new_source':source})
    def proof(*a):
        if fault=='proof_missing':raise ValueError('actual new proof missing')
        return {'accepted':True}
    monkeypatch.setattr(backend,'verify_proof',proof)
    review={'schema':'n26-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
      'protocol':c.ref(c.PROTOCOL),'source_plan':c.ref(c.SOURCE_PLAN),'source_bridge':c.ref(c.BRIDGE),
      'predecessor':c.predecessor(),'backend_proof':c.ref(c.BACKEND_PROOF),'arithmetic_protocol':c.ref(c.ARITHMETIC_PROTOCOL),
      'admission_clarification':c.ref(c.CLARIFICATION),'composition_protocol':c.ref(c.LOGICAL_PROTOCOL),
      'logical_admission_addendum':c.ref(tmp_path/l.DOC/'admission-addendum-v1.md'),'no_gpu_release':True}
    if fault=='review_protocol':review['composition_protocol']['sha256']='0'*64
    if fault=='missing_addendum':review.pop('logical_admission_addendum')
    put(c.FINAL_REVIEW,review)
    authority={'schema':'n26-dev-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':runtime,'protocol':c.ref(c.PROTOCOL),
      'final_review':c.ref(c.FINAL_REVIEW),'budget_authority':c.ref(c.BUDGET_AUTHORITY),'limits':c.LIMITS,'local_gpu_hours':1.,
      'recorded_at':'synthetic','authority_interpretation':'synthetic','admission_clarification':c.ref(c.CLARIFICATION),
      'composition_protocol':c.ref(c.LOGICAL_PROTOCOL),'logical_predecessor':c.predecessor(),'validation_authorized':False,'formal_authorized':False}
    if fault=='authority_missing_logical':authority.pop('logical_predecessor')
    if fault=='authority_wrong_gate':authority['logical_predecessor']['sha256']='0'*64
    if fault=='authority_protocol':authority['composition_protocol']['sha256']='0'*64
    put(c.AUTHORITY,authority)
    if fault=='none':assert c.authority(source,runtime,tmp_path)==c.ref(c.AUTHORITY)
    else:
        with pytest.raises(ValueError):c.authority(source,runtime,tmp_path)
