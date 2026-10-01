import copy,json
from pathlib import Path
import pytest
from scripts import qd_ed_n25_cont_downstream as d,qd_ed_n25_cont_evidence as e
from n25_downstream_fixtures import complete_fixture,fake_cleanup,put

@pytest.mark.parametrize('kind,expected',[('promotion','ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'),('reject','REJECT'),('futility','REJECT_NUMERIC_FUTILITY')])
def test_three_valid_non_authorizing_dispositions(tmp_path,monkeypatch,kind,expected):
    data,objects=complete_fixture(tmp_path,monkeypatch,kind)
    result=d.build(data,objects=objects,cleanup=fake_cleanup)
    assert result['logical_disposition']==expected
    assert result['allow_validation'] is result['allow_n26'] is result['gpu_authorized'] is False
    assert result['cost_coverage']['old']['unknown_token_calls']==6
    assert result['cost_coverage']['new']['unknown_token_calls']==0
    assert result['cost_coverage']['combined']['all_attempt_token_usage_complete'] is False
    assert len(result['attempt_ids'])==result['accepted_cells']+1
    assert result['settled_original_resource']['gpu_process_wall_seconds']==11
    assert all(Path(p).suffix!='.pt' for _,p in objects.reads)

def rewrite(data,key,change):
    ref=data['references'][key];obj=json.loads(Path(ref['path']).read_text());change(obj);new=put(ref['path'],obj)
    data['references'][key]=new
    data['files']=[new if x['path']==ref['path'] else x for x in data['files']]
    return obj


def rewrite_events(data,change):
    result=json.loads(Path(data['references']['result']['path']).read_text());lr=result['ledger_snapshot'];events=json.loads(Path(lr['path']).read_text());change(events)
    new=put(lr['path'],events);data['files']=[new if x['path']==lr['path'] else x for x in data['files']]
    rewrite(data,'result',lambda q:q.update(ledger_snapshot=new))
    rewrite(data,'journal_projection',lambda q:q.update(continuation_events=events,continuation_event_count=len(events)))


@pytest.mark.parametrize('fault',[
 'unreviewed','wrong_owner','missing_review','original_invalid','status_disagreement','source_shape','wrong_protocol',
 'cost_duplicate','drop_import','unknown_erased','old_cost_erased','new_cost_erased','new_invalid','new_incomplete','new_unknown',
 'wrong_retry','reorder','later_reserved','omitted_current_event','projection_incomplete','projection_counts','extra_health_reservation',
 'wrong_proof_source','unsettled_resource','wrong_resource_cost','bad_proof_cases','missing_receipt','late_audit',
 'source_git_drift','source_manifest_drift','reverse_drift','runtime_alias','helper_drift','helper_shadow'])
def test_corrupted_evidence_refuses_creation(tmp_path,monkeypatch,fault):
    data,objects=complete_fixture(tmp_path,monkeypatch)
    if fault=='unreviewed':data['root_authorized']=False
    elif fault=='wrong_owner':data['owning_root']=str(tmp_path/'other')
    elif fault=='missing_review':data['references'].pop('root_review')
    elif fault=='original_invalid':rewrite(data,'result',lambda q:q.update(decision='INVALID_OR_INTERRUPTED'))
    elif fault=='status_disagreement':rewrite(data,'result',lambda q:q['controller_evidence'].update(consistent=False))
    elif fault=='source_shape':
        rr=rewrite(data,'root_review',lambda q:q.update(source=data['references']['source']))
        for k in ('journal_projection','resource_projection'):rewrite(data,k,lambda q:q.update(root_terminal_review=data['references']['root_review']))
    elif fault=='wrong_protocol':(d.ROOT/d.DOC/'protocol-v1.md').write_text('wrong')
    elif fault=='cost_duplicate':rewrite(data,'result',lambda q:q['attempts'].append(copy.deepcopy(q['attempts'][-1])))
    elif fault=='drop_import':rewrite(data,'result',lambda q:q['accepted_cells'].pop(1))
    elif fault=='unknown_erased':rewrite(data,'seal',lambda q:q['historical_unknowns'].update(unknown_token_calls=0))
    elif fault in {'old_cost_erased','new_cost_erased'}:
        rewrite(data,'result',lambda q:q['old_costs' if fault.startswith('old') else 'new_costs']['all_attempt_costs']['N23']['gpu_process_wall_seconds'].update(observed_total=0))
    elif fault in {'new_invalid','new_incomplete','new_unknown','wrong_retry'}:
        def edit(ev):
            key,value={'new_invalid':('outcome_valid',False),'new_incomplete':('provider_token_usage_complete',False),'new_unknown':('provider_usage_complete_calls',0),'wrong_retry':('retry_of','other')}[fault]
            ev[2][key]=value
        rewrite_events(data,edit)
    elif fault=='reorder':rewrite_events(data,lambda q:q.__setitem__(slice(0,6),q[3:6]+q[:3]))
    elif fault=='later_reserved':rewrite_events(data,lambda q:q.append({**q[-1],'event':'reserved','attempt_id':'late'}))
    elif fault=='omitted_current_event':rewrite(data,'journal_projection',lambda q:q['continuation_events'].pop())
    elif fault=='projection_incomplete':rewrite(data,'journal_projection',lambda q:q.update(all_matching_events_included=False))
    elif fault=='projection_counts':rewrite(data,'journal_projection',lambda q:q.update(original_event_count=0))
    elif fault=='extra_health_reservation':rewrite(data,'resource_projection',lambda q:q['events'].append({**q['events'][0],'resource_id':'other'}))
    elif fault in {'wrong_proof_source','unsettled_resource','wrong_resource_cost','bad_proof_cases'}:
        seal=json.loads(Path(data['references']['seal']['path']).read_text());pref=seal['historical_backend_proof'];proof=json.loads(Path(pref['path']).read_text())
        ref=pref if fault=='wrong_proof_source' else proof['terminal'] if fault in {'unsettled_resource','wrong_resource_cost'} else proof['report']
        obj=json.loads(Path(ref['path']).read_text())
        if fault=='wrong_proof_source':obj['source']['commit']=d.HISTORICAL
        elif fault=='unsettled_resource':obj['event']='aborted'
        elif fault=='wrong_resource_cost':obj['gpu_process_wall_seconds']=101
        else:obj['cases'].pop()
        Path(ref['path']).write_text(json.dumps(obj))  # Original closed ref must reject, never silently rehash evidence.
    elif fault=='missing_receipt':
        result=json.loads(Path(data['references']['result']['path']).read_text());q=result['accepted_cells'][-1]['worker_receipt'];data['files']=[x for x in data['files'] if x['path']!=q['path']]
    elif fault=='late_audit':
        seal=json.loads(Path(data['references']['seal']['path']).read_text());put(seal['failed_audits_absent'][0]['path'],{'late':True})
    elif fault=='source_git_drift':objects.values[e.BASE,'fake_source_000.py']=b'changed\n'
    elif fault=='source_manifest_drift':rewrite(data,'source',lambda q:q['files'].pop())
    elif fault=='reverse_drift':objects.values[d.HISTORICAL,'experiments/qd_ed_n25_continuation/reverse-routes-v1.json']=b'{}'
    elif fault=='runtime_alias':
        seal=json.loads(Path(data['references']['seal']['path']).read_text());q=seal['runtime'];v=json.loads(Path(q['path']).read_text());v['worktree']='/other';Path(q['path']).write_text(json.dumps(v))
    elif fault=='helper_drift':(d.ROOT/'scripts/qd_ed_n25_cont_terminal.py').write_text('changed')
    else:monkeypatch.setattr(d.terminal,'__file__',str(tmp_path/'shadow.py'))
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):d.build(data,objects=objects,cleanup=fake_cleanup)


def test_current_projection_hook_ignores_full_ledger_append_hash_but_rejects_matching_changes(tmp_path,monkeypatch):
    data,objects=complete_fixture(tmp_path,monkeypatch,'futility')
    jp=json.loads(Path(data['references']['journal_projection']['path']).read_text());rp=json.loads(Path(data['references']['resource_projection']['path']).read_text())
    events=jp['original_events']+jp['continuation_events']
    d.check_current_matching_events(jp,events,rp,rp['events'])
    jp['source_ledger']['sha256']='b'*64  # source hash is attestation provenance, not a forever-frozen full ledger.
    d.check_current_matching_events(jp,events,rp,rp['events'])
    with pytest.raises(ValueError):d.check_current_matching_events(jp,events+[events[-1]],rp,rp['events'])
    with pytest.raises(ValueError):d.check_current_matching_events(jp,[{'identity':{'iteration':'protected'}}],rp,rp['events'])


def test_live_controller_rejected_and_no_forbidden_fallback(tmp_path,monkeypatch):
    data,objects=complete_fixture(tmp_path,monkeypatch)
    def blocked(*a,**k):raise AssertionError('forbidden reconstruction path')
    for module,name in ((d.terminal,'main'),(d.terminal.report,'analyze'),(d.terminal.report,'write_terminal'),(d.terminal.w,'evidence_record'),(d.terminal.r,'validate_plan')):monkeypatch.setattr(module,name,blocked)
    def live(ps):
        if any(x['pid']==600000 for x in ps):raise ValueError('live controller')
        return fake_cleanup(ps)
    with pytest.raises(ValueError,match='live controller'):d.build(data,objects=objects,cleanup=live)
    assert d.build(data,objects=objects,cleanup=fake_cleanup)['tensor_reads']==0


@pytest.mark.parametrize('fault',['overcount','oversize','unknown_ref','bad_hash','tensor','raw_directory'])
def test_reader_closed_bounds(tmp_path,fault):
    p=tmp_path/'a.json';ref=put(p,{'x':1})
    if fault=='overcount':
        with pytest.raises(ValueError):e.Reader([ref]*513)
    elif fault=='oversize':
        with p.open('wb') as f:f.truncate(16*1024*1024+1)
        with pytest.raises(ValueError,match='before read'):e.Reader([ref]).read_bytes(ref)
    elif fault=='unknown_ref':
        q=put(tmp_path/'b.json',{})
        with pytest.raises(ValueError,match='uninventoried'):e.Reader([ref]).json(q)
    elif fault=='bad_hash':
        p.write_text('{}')
        with pytest.raises(ValueError,match='hash changed'):e.Reader([ref]).json(ref)
    else:
        q={'path':str(tmp_path/('a.pt' if fault=='tensor' else 'decision_evidence/a.json')),'sha256':'a'*64}
        with pytest.raises(ValueError):e.Reader([q])

@pytest.mark.parametrize('fault',['plan_science','plan_authority','authority_extra','authority_nonfinite','status_attempts','status_outcomes','counter_none','counter_bool','success_int'])
def test_exact_frozen_plan_status_and_new_counter_shape(tmp_path,monkeypatch,fault):
    data,objects=complete_fixture(tmp_path,monkeypatch)
    if fault=='plan_science':rewrite(data,'plan',lambda q:q.update(runtime_inventory_sha256='changed'))
    elif fault=='plan_authority':rewrite(data,'plan',lambda q:q['n25_infrastructure_continuation'].update(authority=None))
    elif fault=='authority_extra':rewrite(data,'authority',lambda q:q.update(allow_extra_retry=True))
    elif fault=='authority_nonfinite':rewrite(data,'authority',lambda q:q.update(remaining_local_gpu_hours=float('inf')))
    elif fault.startswith('status_'):
        status=rewrite(data,'status',lambda q:q['attempts' if fault=='status_attempts' else 'outcomes'].pop())
        rewrite(data,'result',lambda q:q.update(terminal_status={**data['references']['status'],'content':status}))
    else:
        def change(ev):
            if fault=='success_int':ev[2]['success']=0
            else:
                ev[2]['provider_logical_call_attempts']=ev[2]['provider_usage_complete_calls']=None if fault=='counter_none' else True
        rewrite_events(data,change)
    with pytest.raises((ValueError,KeyError)):d.build(data,objects=objects,cleanup=fake_cleanup)

@pytest.mark.parametrize('which',['worker','old_report','backend'])
def test_imported_helper_identity_is_owning_source(tmp_path,monkeypatch,which):
    from scripts import qd_ed_n25_backend as backend
    data,objects=complete_fixture(tmp_path,monkeypatch)
    module={'worker':d.terminal.w,'old_report':d.terminal.report.old_report,'backend':backend}[which]
    monkeypatch.setattr(module,'__file__',str(tmp_path/'other_source.py'))
    with pytest.raises(ValueError,match='owning study|shadowing'):d.build(data,objects=objects,cleanup=fake_cleanup)

@pytest.mark.parametrize('name',['stage_events.jsonl','events.jsonl','attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl'])
def test_raw_stage_index_or_full_ledger_inventory_rejected_without_read(tmp_path,name):
    with pytest.raises(ValueError,match='forbidden'):
        d.MetadataReader([{'path':str(tmp_path/name),'sha256':'a'*64}])


@pytest.mark.parametrize('which',['qd_ed_n25_contract','qd_ed_audit_backend','qd_ed_n25_reference'])
def test_transitive_proof_helper_bytes_bound(tmp_path,monkeypatch,which):
    data,objects=complete_fixture(tmp_path,monkeypatch)
    (d.ROOT/'scripts'/(which+'.py')).write_text('changed helper')
    with pytest.raises(ValueError,match='helper drift'):d.build(data,objects=objects,cleanup=fake_cleanup)


@pytest.mark.parametrize('which',['original_contract','backend_contract_identity','audit_backend','reference'])
def test_transitive_proof_helper_imports_owned(tmp_path,monkeypatch,which):
    from types import SimpleNamespace
    from scripts import qd_ed_n25_backend as backend,qd_ed_audit_backend as audit_backend,qd_ed_n25_reference as reference
    data,objects=complete_fixture(tmp_path,monkeypatch)
    if which=='backend_contract_identity':
        monkeypatch.setattr(backend,'c',SimpleNamespace(__file__=d.c.old.__file__))
    else:
        module={'original_contract':d.c.old,'audit_backend':audit_backend,'reference':reference}[which]
        monkeypatch.setattr(module,'__file__',str(tmp_path/'shadow.py'))
    with pytest.raises(ValueError,match='owning study|shadowing|helper identity'):d.build(data,objects=objects,cleanup=fake_cleanup)
