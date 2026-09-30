"""Synthetic continuation composition using real serializer, receipt and journal schemas."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'continuation'))
import n23_continuation_contract as x
import n23_continuation_supervise as s
import n23_continuation_report as report_writer
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_supervise as old
from scripts import qd_ed_n23_v2_recovery as recovery
from test_n23_n7_metrics_adapter import case as metric_case


def write(path,value,lines=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text((''.join(json.dumps(v)+'\n' for v in value)) if lines else json.dumps(value))
    return x.ref(path)


@pytest.fixture(autouse=True)
def no_cuda():
    yield
    assert not torch.cuda.is_initialized()


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    owned=SimpleNamespace(root=tmp_path,r=r,c=c,w=w,sup=old,recovery=recovery)
    rows=[{'episode_key':f'n23v2_dev_t{t:02}_{a.lower()}_fixture','task_id':t,'profile':a,
        'iteration':c.COHORT,'split':'dev','seed_block':'dev','env_seed':100+t,'policy_seed':200+t,
        'init_index':0,'init_row_sha256':'a'*64,'budget_bucket':'baseline' if a=='C0' else 'development',
        'timeout_seconds':1800} for t in range(10) for a in c.ARMS]
    plan={'episodes':rows,'source_commit':x.SOURCE,'profiles_sha256':'profile','runtime_manifest_sha256':'runtime',
        'runtime_inventory_sha256':'inventory','artifact_root':str(tmp_path),'candidate_profiles':{
            'N7':{'path':str(ROOT/'configs/qd_ed_final/candidate_n7.json'),'sha256':w.sha(ROOT/'configs/qd_ed_final/candidate_n7.json')}},
        'n23_cohort':{'backend_proof':{'fixture':True}}}
    planpath=tmp_path/'plan.json';planref=write(planpath,plan)
    monkeypatch.setattr(x,'PLAN',planpath);monkeypatch.setattr(x,'PLAN_SHA',planref['sha256'])
    monkeypatch.setattr(c,'RUN_DIR',tmp_path)
    monkeypatch.setattr(old,'ROOT',tmp_path)
    # Original profile files are static inputs; no protected or native data is consulted.
    manifest=metric_case(tmp_path/'unused')[1]
    manifest['profiles']['N23']=r.expand_candidate('N23',r.read_json(ROOT/'configs/qd_ed_final/candidate_n23.json'),manifest['profiles']['Q0'])
    runtime={'gpu_mapping':{'uuid':c.GPU7_UUID}}
    monkeypatch.setattr(w,'validate_context',lambda ctx,argv:(None,Path(ctx['output_dir']),runtime))
    journal=[];prefix=[];failure={'prefix':[]};result_refs={}
    def materialize(row,aid,*,valid=True,success=False,retry_of=None,bucket=None):
        output=tmp_path/'artifacts'/aid;arm=row['profile']
        raw_case=metric_case(output,arm if arm in {'N7','N23'} else 'N7')
        metrics=raw_case[2];native=raw_case[3]
        if arm not in {'N7','N23'}:native.pop('n5_grasp_timing_audit')
        if arm=='N23':native['n23_actuator_clipped_quality_audit']={
            'score_batches_verified':11,'candidate_scores_verified':176,'clipped_prefix_candidates':0,'rank_changed_batches':0}
        backend={'kind':'cuda' if arm=='N23' else 'cpu','logical_device':'cuda:0' if arm=='N23' else 'cpu'}
        if arm=='N23':backend.update(physical_uuid=c.GPU7_UUID,dtype_coverage=['torch.bfloat16'],torch_version='fixture',cuda_version='fixture')
        native['n23_arithmetic_backend']=backend
        auditref=write(output/'eds_eval/decision-evidence-audit.json',native)
        metricref=write(output/'eds_eval/eds_metrics.jsonl',[metrics],True)
        write(output/'eds_eval/episode_compute.jsonl',[],True)
        write(output/'eds_eval/decision_evidence/episode_000/status.json',{})
        write(output/'eds_eval/decision_evidence/episode_000/events.jsonl',[],True)
        ctx={'plan':planref,'output_dir':str(output),'attempt_id':aid,'episode_key':row['episode_key'],'profile':arm,
            'main_argv':['policy.type=rdt'],'runtime':{'path':'synthetic','sha256':'r'},'source':{'commit':x.SOURCE}}
        ctxref=write(output/'n23-worker-context.json',ctx)
        pid={'pid':1234,'proc_start_ticks':'5678','boot_id':'synthetic-boot'}
        write(output/'process.json',{**pid,'attempt_id':aid})
        cuda={'physical_gpu':7,'uuid':c.GPU7_UUID,'physical_uuid':c.GPU7_UUID,'actual_uuid':c.GPU7_UUID[4:],
            'logical_device':'cuda:0','actual_uuid_type':'torch._C._CUuuid',
            'actual_uuid_bytes_hex':c.GPU7_UUID[4:].replace('-',''),'torch_version':'fixture','cuda_version':'fixture'}
        receipt={'schema':'n23-in-worker-audit-receipt-v1','process':pid,'process_unchanged':True,'attempt_id':aid,
            'episode_key':row['episode_key'],'profile':arm,'accepted':True,'main_exit_code':0,'context':ctxref,
            'plan':ctx['plan'],'runtime':ctx['runtime'],'source':ctx['source'],'main_argv_sha256':w.canonical_sha(ctx['main_argv']),
            'evidence':w.evidence_record(output),'audit_backend':backend,'worker_cuda':cuda,'audit_report':auditref,
            'audit_seconds':1.,'worker_wall_seconds':2.}
        write(output/'eds_eval/in-worker-audit-start.json',{'schema':'n23-worker-start-v1','process':pid,'context':ctxref})
        receiptref=write(output/'eds_eval/in-worker-audit-receipt.json',receipt)
        base={'attempt_id':aid,'identity':r.episode_identity(row),'episode_key':row['episode_key'],
            'budget_bucket':bucket or row['budget_bucket'],'retry_of':retry_of,'source_commit':x.SOURCE,
            'plan_sha256':planref['sha256'],'profile_manifest_sha256':'profile','runtime_manifest_sha256':'runtime',
            'runtime_inventory_sha256':'inventory','init_row_sha256':row['init_row_sha256'],'physical_gpu':7,
            'output_dir':str(output),'n23_worker_receipt':receiptref}
        if row.get('n23_v2_recovery_eligibility'):base['n23_v2_recovery_eligibility']=row['n23_v2_recovery_eligibility']
        final={**base,'event':'valid','outcome_valid':valid,'required_cost_telemetry_complete':valid,
            'success':success if valid else None,'gpu_process_wall_seconds':7.,'guided_chunks':1,
            'provider_logical_call_attempts':2,'provider_usage_complete_calls':2 if valid else 1,
            'provider_token_usage_complete':valid}
        terminalref=write(output/'attempt-result.json',final)
        journal.extend([{**base,'event':'reserved'},{**base,'event':'dispatched'},final])
        write(tmp_path/'data/attempt-ledger.jsonl',journal,True)
        result_refs[aid]={'terminal':terminalref,'metrics':metricref,'native_report':auditref,'native_receipt':receiptref}
        return final
    # Adapter's exact N7 static profile uses the source root, whereas receipts use synthetic output roots.
    def accept(pl,row,events):
        final=c.accepted_cell(pl,row,events,tmp_path,vars(r));output=Path(final['output_dir'])
        native=c.read_worker_report(output,vars(r))
        from n23_n7_metrics_adapter import native_counts
        counts,aux=native_counts(final,row,native,plan=pl,manifest=manifest,root=ROOT,r=vars(r),w=w,original=old)
        refs={k:x.ref(output/p) for k,p in [('audit','eds_eval/decision-evidence-audit.json'),
            ('worker_context','n23-worker-context.json'),('worker_receipt','eds_eval/in-worker-audit-receipt.json'),
            ('attempt_result','attempt-result.json')]}
        assert w.read_ref(refs['attempt_result'])==final
        return final,refs,counts,aux
    for row,aid in zip(rows,x.PREFIX_IDS):
        final=materialize(row,aid);prefix.append(accept(plan,row,journal))
        failure['prefix'].append({'episode_key':row['episode_key'],'profile':row['profile'],'attempt_id':aid,
            'success':False,'outcome_valid':True,'gpu_process_wall_seconds':7.,**result_refs[aid]})
    failure['original_dev_snapshot']=write(tmp_path/'prefix-ledger.jsonl',journal,True)
    # Protocol references are independently bound in integration, use bounded synthetic paths here.
    for name in ('FAILURE','EXCEPTION','WRITER'):
        p=tmp_path/(name+'.json');write(p,{});monkeypatch.setattr(x,name,p)
    return SimpleNamespace(owned=owned,plan=plan,manifest=manifest,runtime=runtime,journal=journal,
        prefix=prefix,failure=failure,materialize=materialize,accept=accept,refs=result_refs)


@pytest.mark.parametrize('fault',['none','extra','duplicate','order','recovery','unsettled','success','cost','plan','runtime','init',
    'receipt','receipt_process','receipt_context','native','metrics','journal','missing_first'])
def test_exact_three_prefix_original_receipt_journal_native_binding(fixture,fault):
    f=fixture;events=f.journal
    target=events[-1];output=Path(target['output_dir'])
    if fault=='extra':f.materialize(f.plan['episodes'][3],'extra')
    if fault=='duplicate':events.extend(copy.deepcopy(events[-3:]))
    if fault=='order':events[:6]=events[3:6]+events[:3]
    if fault=='recovery':events[-3]['retry_of']=events[0]['attempt_id']
    if fault=='unsettled':events.pop()
    if fault=='success':target['success']=True
    if fault=='cost':target['gpu_process_wall_seconds']=8.
    if fault=='plan':target['plan_sha256']='other'
    if fault=='runtime':target['runtime_manifest_sha256']='other'
    if fault=='init':target['init_row_sha256']='other'
    if fault=='receipt':target['n23_worker_receipt']['sha256']='other'
    if fault=='receipt_process':
        p=output/'process.json';value=r.read_json(p);value['pid']+=1;write(p,value)
    if fault=='receipt_context':
        p=output/'n23-worker-context.json';value=r.read_json(p);value['main_argv'].append('other');write(p,value)
    if fault=='native':
        p=output/'eds_eval/decision-evidence-audit.json';value=r.read_json(p);value['accepted']=False;write(p,value)
    if fault=='metrics':write(output/'eds_eval/eds_metrics.jsonl',[],True)
    if fault=='journal':events[-1]['extra']='tampered'
    if fault=='missing_first':del events[:3]
    if fault=='none':
        found=x.prefix_gate(f.plan,f.failure,events,f.owned,f.accept,initial=True)
        assert [v[0]['attempt_id'] for v in found]==list(x.PREFIX_IDS)
        assert sum(v[0]['gpu_process_wall_seconds'] for v in found)==21.
    else:
        with pytest.raises((ValueError,r.GateError,AssertionError)):
            x.prefix_gate(f.plan,f.failure,events,f.owned,f.accept,initial=True)


def test_prefix_later_boundary_still_preserves_original_three(fixture):
    f=fixture;f.materialize(f.plan['episodes'][3],'fourth')
    assert len(x.prefix_gate(f.plan,f.failure,f.journal,f.owned,f.accept,initial=False))==3
    with pytest.raises(ValueError):x.prefix_gate(f.plan,f.failure,f.journal,f.owned,f.accept,initial=True)


@pytest.mark.parametrize('name',['scripts.qd_ed_final_runner','scripts.qd_ed_n23_worker','scripts.qd_ed_n23_v2_contract',
    'scripts.qd_ed_n23_v2_supervise','core.eds_eval_metrics','qd_ed_available_gpu_queue'])
def test_imports_cannot_resolve_to_external_clone(tmp_path,name):
    own=tmp_path/'own';clone=tmp_path/'clone'
    x.module_origins(own,{name:SimpleNamespace(__file__=str(own/'module.py'))})
    with pytest.raises(ValueError,match='shadowed'):
        x.module_origins(own,{name:SimpleNamespace(__file__=str(clone/'module.py'))})


def test_namespace_shadow_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='namespace'):
        x.module_origins(tmp_path/'own',{'scripts':SimpleNamespace(__path__=[str(tmp_path/'clone/scripts')])})


@pytest.mark.parametrize('active',[True,False])
def test_owned_worker_scan_has_no_cuda_and_requires_no_active_audit(tmp_path,active):
    own=tmp_path/'own';own.mkdir();proc=tmp_path/'proc';proc.mkdir();p=proc/'123';p.mkdir()
    (p/'cwd').symlink_to(own,target_is_directory=True)
    (p/'cmdline').write_bytes(b'python\0'+(b'qd_ed_n23_worker.py' if active else b'nonworker.py')+b'\0')
    if active:
        with pytest.raises(ValueError,match='still active'):x.no_owned_worker(own,proc=proc)
    else:x.no_owned_worker(own,proc=proc)


@pytest.mark.parametrize('fault',['none','missing_adoption','authority_extra','review_source','review_backend','drift'])
def test_exact_external_review_authority_and_adoption(fixture,tmp_path,monkeypatch,fault):
    f=fixture;pl=f.plan;pl['runtime_manifest_path']=str(tmp_path/'runtime.json');write(Path(pl['runtime_manifest_path']),{})
    source={'commit':'new','files':[]};own={'commit':x.SOURCE,'files':[]}
    monkeypatch.setattr(x,'source_record',lambda:source)
    monkeypatch.setattr(x,'owning_source',lambda *_:own)
    review=tmp_path/'review.json';authority=tmp_path/'authority.json'
    monkeypatch.setattr(x,'REVIEW',review);monkeypatch.setattr(x,'AUTHORITY',authority)
    value=x.review_payload(pl,source,own,f.owned)
    if fault=='review_source':value['external_source']={}
    if fault=='review_backend':value['backend_proof']={}
    write(review,value)
    auth=x.authority_payload(x.ref(review),pl,f.owned)
    if fault=='authority_extra':auth['generic_resume']=True
    write(authority,auth);state={x.KEY:x.ref(authority)}
    if fault=='missing_adoption':state={}
    if fault=='drift':source['new']='unreviewed'
    if fault=='none':assert x.authorization(pl,f.owned,state=state)==x.ref(authority)
    else:
        with pytest.raises(ValueError):x.authorization(pl,f.owned,state=state)


@pytest.mark.parametrize('scenario,expected,status,promoted',[
    ('full',37,'completed_all_forty_audited',True),('futility',21,'rejected_numeric_futility',False),
    ('recovery',38,'completed_all_forty_audited',True),('failed_recovery',2,'failed',False),
    ('ineligible',1,'failed',False),('source_stop',0,'failed',False)])
def test_original_one_attempt_scope_exact_suffix_costs_and_terminal_report(fixture,tmp_path,monkeypatch,scenario,expected,status,promoted):
    f=fixture;calls=[];boundaries=[];statuses=[]
    monkeypatch.setattr(x,'acceptor',lambda *_:f.accept)
    # Real one_attempt and scoped routing, only the actual runner launch is mocked.
    def run_plan(path,*,split,iteration,episode_keys,root):
        row=next(v for v in f.plan['episodes'] if v['episode_key']==episode_keys[0])
        c.require_scope(f.plan,root,vars(r),row)
        effective=c.effective_row(f.plan,row,f.journal,root,vars(r))
        aid='suffix'+str(len(calls));calls.append(copy.deepcopy(effective))
        valid=not(scenario in {'recovery','failed_recovery','ineligible'} and len(calls)==1)
        if scenario=='failed_recovery' and len(calls)==2:valid=False
        success=(row['profile']=='N23' and scenario!='futility' and valid)
        final=f.materialize(effective,aid,valid=valid,success=success,retry_of=effective.get('retry_of'),bucket=effective['budget_bucket'])
        if not valid:raise r.GateError('synthetic charged invalid terminal')
        return [final]
    monkeypatch.setattr(r,'run_plan',run_plan)
    def eligible(path,pl,row,final,*args):
        recovery.check_cell_history(f.journal,row,final['attempt_id'],vars(r))
        if scenario=='ineligible':raise ValueError('not typed timeout')
        return {'primary_attempt_id':final['attempt_id'],'diagnostic':{'unknown_token_calls':1}}
    monkeypatch.setattr(recovery,'create_eligibility',eligible)
    def verify(reference,pl,row,events,*_):
        value=w.read_ref(reference);recovery.check_cell_history(events,row,value['primary_attempt_id'],vars(r));return value
    monkeypatch.setattr(recovery,'verify_eligibility',verify)
    def boundary():
        boundaries.append(1)
        if scenario=='source_stop':raise ValueError('source drift')
    write_status=lambda v:statuses.append(copy.deepcopy(v))
    args=dict(boundary=boundary,write=write_status,events=lambda:copy.deepcopy(f.journal))
    if status=='failed':
        with pytest.raises((ValueError,r.GateError)):
            s.execute(f.plan,f.manifest,f.runtime,f.owned,f.prefix,**args)
    else:s.execute(f.plan,f.manifest,f.runtime,f.owned,f.prefix,**args)
    terminal=statuses[-1]
    assert len(calls)==expected and terminal['status']==status and terminal['dev_gate_promoted'] is promoted
    assert [v['episode_key'] for v in calls if not v.get('retry_of')]==[v['episode_key'] for v in f.plan['episodes'][3:3+len([v for v in calls if not v.get('retry_of')])]]
    assert terminal['attempts'][:3]==[old.attempt_record(v[0],row) for v,row in zip(f.prefix,f.plan['episodes'])]
    assert len(terminal['attempts'])==3+expected
    assert sum(v['terminal']['gpu_process_wall_seconds'] for v in terminal['attempts'])==7*(3+expected)
    if scenario in {'recovery','failed_recovery'}:
        assert calls[1]['retry_of']=='suffix0' and calls[1]['budget_bucket']=='recovery'
        assert terminal['unknown_token_calls']==(1 if scenario=='recovery' else 2)
    # Reuse the original real writer analyze; only redirect its constant plan hash for this synthetic plan.
    spec=importlib.util.spec_from_file_location('synthetic_writer',ROOT.parent/'summarize_cohort_cpu_v2.py')
    writer=importlib.util.module_from_spec(spec);spec.loader.exec_module(writer)
    monkeypatch.setattr(writer,'PLAN_SHA',x.PLAN_SHA)
    result=writer.analyze(f.plan,terminal,f.journal,f.accept)
    assert result['dispatched']==3+expected and result['gpu_process_wall_seconds']==7*(3+expected)
    assert result['dev_gate_promoted'] is promoted
    assert result['decision']==('ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promoted else 'REJECT' if scenario=='futility' else 'INVALID_OR_INTERRUPTED')


def test_external_source_record_rejects_uncommitted_or_imported_writer_drift(tmp_path,monkeypatch):
    p=tmp_path/'helper.py';p.write_text('exact source\n')
    writer=tmp_path/'writer.py';writer.write_text('frozen writer\n')
    monkeypatch.setattr(x,'FILES',{'helper.py'});monkeypatch.setattr(x,'WRITER',writer)
    monkeypatch.setattr(x,'WRITER_SHA',x.sha(writer))
    def git(argv,**kwargs):return 'commit\n' if argv[1]=='rev-parse' else b'exact source\n'
    monkeypatch.setattr(x.subprocess,'check_output',git)
    record=x.source_record(tmp_path);assert record['files']==[{'path':'helper.py','sha256':x.sha(p)}]
    p.write_text('changed source\n')
    with pytest.raises(ValueError,match='uncommitted'):x.source_record(tmp_path)
    p.write_text('exact source\n');writer.write_text('changed writer\n')
    with pytest.raises(ValueError,match='writer changed'):x.source_record(tmp_path)


@pytest.mark.parametrize('fault',['none','status_exists','seal_exists','different_process','missing_seal'])
def test_one_initial_launch_and_same_live_process_only(fixture,tmp_path,monkeypatch,fault):
    f=fixture;status=tmp_path/'new-status.json';seal=tmp_path/'seal.json'
    monkeypatch.setattr(x,'STATUS',status);monkeypatch.setattr(x,'SEAL',seal)
    monkeypatch.setattr(x,'immutable_inputs',lambda _:f.failure)
    monkeypatch.setattr(x,'authorization',lambda *a,**k:{'path':'authority','sha256':'a'})
    monkeypatch.setattr(x,'acceptor',lambda *_:f.accept)
    monkeypatch.setattr(x,'quiescent',lambda *args:None)
    monkeypatch.setattr(r,'read_state',lambda *_:{})
    monkeypatch.setattr(w,'process_identity',lambda:{'pid':1,'proc_start_ticks':'2','boot_id':'3'})
    initial=fault not in {'different_process','missing_seal'}
    if fault=='status_exists':write(status,{})
    if fault in {'seal_exists','different_process'}:
        write(seal,{'authority':{'path':'authority','sha256':'a'},'process':{'pid':4,'proc_start_ticks':'2','boot_id':'3'}})
    if fault=='none':
        _,prefix=x.check_boundary(f.plan,f.manifest,f.owned,initial=True);assert len(prefix)==3
        write(seal,{'authority':{'path':'authority','sha256':'a'},'process':w.process_identity()})
        assert len(x.check_boundary(f.plan,f.manifest,f.owned,initial=False)[1])==3
    else:
        with pytest.raises((ValueError,FileNotFoundError)):
            x.check_boundary(f.plan,f.manifest,f.owned,initial=initial)


def adopted_state():
    return {'gpu_pool':[7],'max_concurrent_gpu_workers':1,
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':478,'max_gpu_hours':100.,'reserved':dict(r.N23_BUCKETS),
            'amendment':dict(r.GPU7_N23_V2_AMENDMENT),'gpu_hour_reservations':{'validation':32.,'formal':12.}},
        'n23_v2_gpu7_binding':{'scope':c.COHORT+'_and_backend_preflight_only','user_reply':c.AUTONOMOUS_REPLY,
            'selected_gpu':7,'addendum_path':str(c.PROTOCOL),'addendum_sha256':c.PROTOCOL_SHA}}


@pytest.mark.parametrize('fault',['none','gpu','uuid','reservation','active_worker','unsettled','capacity','protected','state','resource_inflight'])
def test_original_capacity_resource_and_protected_reserve_admission(fixture,monkeypatch,fault):
    f=fixture;state=adopted_state();resources=[];devices={7:{'uuid':c.GPU7_UUID}}
    seen=[];f.owned.queue=SimpleNamespace(inventory=lambda:devices,
        reservation_admission=lambda _:(seen.append('reservation') if fault!='reservation' else x.require(False,'reserved')))
    monkeypatch.setattr(r,'gpu_admission',lambda **kw:seen.append('gpu'))
    monkeypatch.setattr(x,'no_owned_worker',lambda *_:x.require(fault!='active_worker','active worker'))
    if fault=='gpu':devices={}
    if fault=='uuid':devices[7]['uuid']='other'
    if fault=='unsettled':f.journal[-1]['event']='dispatched'
    if fault=='state':state['budget']['max_episode_attempts']=479
    if fault=='capacity':state['budget']['reserved']['recovery']=0
    if fault=='protected':
        old_snap=r.budget_snapshot
        monkeypatch.setattr(r,'budget_snapshot',lambda *args:{**old_snap(*args),'gpu_hours_consumed':99.})
    if fault=='resource_inflight':resources=[{'event':'reserved','resource_id':'health'}]
    if fault=='none':
        x.quiescent(f.plan,f.owned,state,f.journal,resources);assert seen==['reservation','gpu']
    else:
        with pytest.raises((ValueError,r.GateError)):
            x.quiescent(f.plan,f.owned,state,f.journal,resources)


@pytest.mark.parametrize('fault',['none','source','authority','plan','failure','writer'])
def test_new_result_schema_preserves_original_failure_and_provenance(fixture,monkeypatch,fault):
    f=fixture;authority={'path':'authority','sha256':'a'};source={'commit':'external'}
    provenance={'authority':authority,'external_source':source,'original_source_commit':x.SOURCE,
        'original_plan':x.ref(x.PLAN),'original_failed_review':x.ref(x.FAILURE),'imported_writer':x.ref(x.WRITER)}
    if fault=='source':provenance['external_source']={}
    if fault=='authority':provenance['authority']={}
    if fault=='plan':provenance['original_plan']={}
    if fault=='failure':provenance['original_failed_review']={}
    if fault=='writer':provenance['imported_writer']={}
    status={'schema':'n23-dev-supervisor-status-continuation-v1','continuation':provenance}
    writer=SimpleNamespace(analyze=lambda *args:{'schema':'old','dev_gate_promoted':False})
    if fault=='none':
        result=report_writer.analyze(f.plan,status,f.journal,f.accept,writer,authority=authority,source=source)
        assert result['schema']=='n23-dev-continuation-result-v1'
        assert result['original_v2_disposition']=='INVALID_OR_INTERRUPTED' and result['original_v2_record_preserved']
    else:
        with pytest.raises(ValueError):report_writer.analyze(f.plan,status,f.journal,f.accept,writer,authority=authority,source=source)
