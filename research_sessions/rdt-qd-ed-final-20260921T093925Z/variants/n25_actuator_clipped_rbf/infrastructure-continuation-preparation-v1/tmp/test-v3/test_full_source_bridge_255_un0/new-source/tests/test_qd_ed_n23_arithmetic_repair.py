"""Synthetic four-group arithmetic repair authority/proof; no real outcomes."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
import yaml
from test_qd_ed_n23_uuid_repair import case as prior_case,write,no_cuda
from test_qd_ed_n23_uuid_native_repair import case as native_case,identity
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_v2_backend as b
from scripts import qd_ed_n23_v2_preflight_admit as admit
from scripts import qd_ed_n23_v2_prepare as prepare
from scripts import qd_ed_n23_uuid_repair as first
from scripts import qd_ed_n23_uuid_native_repair as prior
from scripts import qd_ed_n23_arithmetic_repair as repair
from scripts.qd_ed_audit_backend import AuditBackend


@pytest.fixture
def case(native_case,monkeypatch):
    previous=native_case;root=previous.root;previous.source['commit']=repair.FAILED_SOURCE
    write(prior.FINAL_REVIEW,previous.review);previous.auth['final_source_review']=c.ref(prior.FINAL_REVIEW)
    write(prior.AUTHORITY,previous.auth);previous.meta['authority']=c.ref(prior.AUTHORITY)
    thirdplan=write(root/'third-plan.json',previous.plan);monkeypatch.setattr(repair,'FAILED_PLAN_SHA',thirdplan['sha256'])
    base={'attempt_id':repair.FAILED_ATTEMPT,'identity':r.episode_identity(admit.diagnostic_row(previous.plan)),
        'episode_key':admit.diagnostic_row(previous.plan)['episode_key'],'budget_bucket':'recovery',
        'retry_of':prior.FAILED_ATTEMPT,'source_commit':repair.FAILED_SOURCE,'plan_sha256':thirdplan['sha256'],
        'n23_backend_preflight':True,'task_outcome':False,'physical_gpu':7,'n23_uuid_repair':previous.meta,
        'n23_final_review':c.ref(prior.FINAL_REVIEW)}
    batches=[{'decision_id':f'synthetic_{i}','score_sequence':i,'dtype':'torch.bfloat16','candidates':16,
        'mismatches':[],'production_helper_passed':True,'independent_passed':True,'wrong_score_rejected':True,'accepted':True} for i in range(176)]
    for i in range(7):batches[i].update(accepted=False,mismatches=[{'check':'clipped_quality_or_mask'}])
    for i in range(7,14):
        mismatch=[{'check':'raw_score','candidate':j,'stored':-.01,'reconstructed':-.0101} for j in range(2 if i==7 else 1)]
        mismatch.append({'check':'independent_arithmetic','error':'AuditFailure:n23_seven_point_raw_provider'})
        batches[i].update(accepted=False,independent_passed=False,mismatches=mismatch)
    synthetic=[{'decision_id':'synthetic_'+dt,'score_sequence':-1,'dtype':dt,'candidates':4,'production_helper_passed':True,
        'independent_passed':True,'wrong_score_rejected':True,'accepted':i==1,
        'mismatches':[] if i else [{'check':'clipped_quality_or_mask'}]} for i,dt in enumerate(['torch.float32','torch.bfloat16'])]
    process={'pid':987,'proc_start_ticks':'654','boot_id':'synthetic'}
    report={'schema':'n23-backend-preflight-proof-v2','plan':thirdplan,'source':previous.source,
        'attempt_id':repair.FAILED_ATTEMPT,'accepted':False,'task_outcome':False,'errors':[],
        'batches':batches,'synthetic':synthetic,'runtime':previous.plan['runtime'],'process':process,'uuid_repair':previous.meta,
        'retry_of':prior.FAILED_ATTEMPT,'worker_wall_seconds':15.,'backend':identity(),'wrong_bounds_rejected':True}
    terminal={**base,'event':'aborted','outcome_valid':False,'gpu_process_wall_seconds':repair.FAILED_SECONDS,
        'n23_preflight_dispatched':True,'process':process}
    events=previous.events+[{**base,'event':'reserved'},{**base,'event':'dispatched'},terminal]
    failure={'schema':'n23-native-backend-arithmetic-failure-review-v1','attempt_id':repair.FAILED_ATTEMPT,
        'status':'INVALID_BACKEND_ARITHMETIC','task_outcome':False,'dev_dispatched':False,
        'gpu_process_wall_seconds':repair.FAILED_SECONDS,'backend_opportunities_consumed':3,
        'additional_gpu_under_v2_authorized':False,'stage_provider_calls':0,'authority':c.ref(prior.AUTHORITY),
        'source':previous.source,'plan':thirdplan,'report':write(root/'third-report.json',report),
        'attempt_result':write(root/'third-terminal.json',terminal),'batch_count':176,'candidate_count':2816,'accepted_batches':162,
        'mismatch_counts':{'clipped_quality_or_mask':7,'raw_score':8,'independent_arithmetic':7},
        'rejected_batches':[v for v in batches if not v['accepted']],'synthetic':synthetic,
        'identity_diagnostic':identity()['identity_diagnostic']}
    failurepath=root/'third-review.json';write(failurepath,failure)
    monkeypatch.setattr(repair,'FAILURE_REVIEW',failurepath);monkeypatch.setattr(repair,'FAILURE_SHA',c.sha(failurepath))
    source={'commit':'arithmetic-source','files':[],'sha256':'arithmetic-source-hash'}
    review={'schema':'n23-final-source-runtime-review-arithmetic-repair-v3','disposition':'accepted',
        'source':source,'runtime':previous.plan['runtime'],'dev_protocol':c.ref(c.PROTOCOL),
        'backend_protocol':c.ref(c.BACKEND_PROTOCOL),'amendment':c.ref(c.BUDGET_AMENDMENT),
        'timeout_observability':c.ref(c.OBSERVABILITY),'exception':c.ref(repair.EXCEPTION),
        'failed_review':c.ref(failurepath),'prior_failure':c.ref(prior.FAILURE_REVIEW),'audit_correction':repair.CORRECTION,'no_gpu_release':True}
    reviewpath=root/'arithmetic-review.json';write(reviewpath,review);monkeypatch.setattr(repair,'FINAL_REVIEW',reviewpath)
    auth={'schema':'n23-arithmetic-repair-authority-v3','exception':c.ref(repair.EXCEPTION),'failed_review':c.ref(failurepath),
        'prior_failure':c.ref(prior.FAILURE_REVIEW),'final_source_review':c.ref(reviewpath),'source':source,'runtime':previous.plan['runtime'],
        'authority_interpretation':'synthetic independent exception','recorded_at':'synthetic','user_message':c.AUTONOMOUS_REPLY,
        'cumulative_caps':repair.CAPS,'limits':repair.LIMITS,'validation_authorized':False,'formal_authorized':False}
    authpath=root/'arithmetic-authority.json';write(authpath,auth);monkeypatch.setattr(repair,'AUTHORITY',authpath)
    meta=repair.binding();plan={**previous.first.old,'source':source,'uuid_repair':meta}
    state=copy.deepcopy(previous.state);state['n23_arithmetic_repair_authority']=meta['authority']
    state['budget']['dispatched']=3
    state['budget']['gpu_hours_consumed']=(first.ORIGINAL_SECONDS+prior.FAILED_SECONDS+repair.FAILED_SECONDS)/3600
    return SimpleNamespace(previous=previous,first=previous.first,root=root,source=source,plan=plan,meta=meta,events=events,
        report=report,terminal=terminal,failure=failure,state=state,review=review,auth=auth,runtime=previous.runtime)


@pytest.mark.parametrize('fault',['none','wrong_attempt','wrong_source','other_error','missing_batch','added_batch','raw_projection',
    'other_arithmetic','no_wrong_bounds','fp32_pass','bf16_fail','cost','retry','identity','prior_missing','unsettled','reorder','dev_claim'])
def test_exact_three_failed_reports_costs_and_numerical_categories(case,monkeypatch,fault):
    x=case
    if fault=='wrong_attempt':x.failure['attempt_id']='other'
    if fault=='wrong_source':x.report['source']={'commit':'other'}
    if fault=='other_error':x.report['errors']=['error']
    if fault=='missing_batch':x.report['batches'].pop()
    if fault=='added_batch':x.report['batches'].append(copy.deepcopy(x.report['batches'][-1]))
    if fault=='raw_projection':x.report['batches'][20]['mismatches']=[{'check':'raw_projection'}]
    if fault=='other_arithmetic':x.report['batches'][7]['mismatches'][-1]['error']='other error'
    if fault=='no_wrong_bounds':x.report['wrong_bounds_rejected']=False
    if fault=='fp32_pass':x.report['synthetic'][0]['accepted']=True
    if fault=='bf16_fail':x.report['synthetic'][1]['accepted']=False
    if fault=='cost':x.terminal['gpu_process_wall_seconds']=0
    if fault=='retry':x.terminal['retry_of']=first.FAILED_ATTEMPT
    if fault=='identity':x.report['backend']['actual_uuid_bytes_hex']='00'*16
    if fault=='prior_missing':x.events=x.events[3:]
    if fault=='unsettled':x.events.pop()
    if fault=='reorder':x.events=x.events[6:]+x.events[:6]
    if fault=='dev_claim':x.failure['dev_dispatched']=True
    x.failure['report']=write(x.root/'third-report.json',x.report)
    x.failure['attempt_result']=write(x.root/'third-terminal.json',x.terminal)
    write(repair.FAILURE_REVIEW,x.failure);monkeypatch.setattr(repair,'FAILURE_SHA',c.sha(repair.FAILURE_REVIEW))
    if fault=='none':assert repair.named_failures(x.events,vars(r))[2]==x.terminal
    else:
        with pytest.raises((ValueError,KeyError)):repair.named_failures(x.events,vars(r))


@pytest.mark.parametrize('fault',['none','missing','not_adopted','source','runtime','fifth','two_more','caps','protected','review','retry','schema'])
def test_new_separate_authority_is_finite_and_not_old_uuid_authority(case,fault):
    x=case
    if fault=='missing':repair.AUTHORITY.unlink()
    if fault=='not_adopted':x.state.pop('n23_arithmetic_repair_authority')
    if fault=='source':x.auth['source']=None
    if fault=='runtime':x.auth['runtime']=None
    if fault=='fifth':x.auth['limits']={**x.auth['limits'],'max_total_backend_attempts':5}
    if fault=='two_more':x.auth['limits']={**x.auth['limits'],'additional_backend_attempts':2}
    if fault=='caps':x.auth['cumulative_caps']={**x.auth['cumulative_caps'],'attempts':479}
    if fault=='protected':x.auth['formal_authorized']=True
    if fault=='review':x.auth['final_source_review']=None
    if fault=='retry':x.meta['retry_of']=prior.FAILED_ATTEMPT
    if fault=='schema':x.meta['schema']='generic'
    if fault not in {'missing','not_adopted','retry','schema'}:
        write(repair.AUTHORITY,x.auth);x.meta['authority']=c.ref(repair.AUTHORITY);x.state['n23_arithmetic_repair_authority']=x.meta['authority']
    if fault=='none':assert repair.authority(x.meta,x.source,x.plan['runtime'],x.state)==x.auth
    else:
        with pytest.raises((ValueError,FileNotFoundError)):repair.authority(x.meta,x.source,x.plan['runtime'],x.state)


@pytest.mark.parametrize('fault',['none','dev','v1_dev','fourth_reserved','fourth_failed','unsettled','not_adopted','protected','slots'])
def test_fourth_only_admission_and_no_protected_borrowing(case,monkeypatch,fault):
    x=case
    monkeypatch.setattr(w,'source_record',lambda *_:x.source);monkeypatch.setattr(c,'predecessor_review',lambda:x.first.old['predecessor_review'])
    monkeypatch.setattr(b,'validate_plan',lambda *_:x.runtime);monkeypatch.setattr(c,'validate_runtime',lambda *_:None)
    if fault in {'dev','v1_dev'}:x.events.append({'attempt_id':'dev','event':'reserved','identity':{'iteration':c.COHORT if fault=='dev' else c.v1.COHORT}})
    if fault in {'fourth_reserved','fourth_failed'}:x.events.append({'attempt_id':'other','event':'aborted' if fault=='fourth_failed' else 'reserved','n23_backend_preflight':True})
    if fault=='unsettled':x.events.pop()
    if fault=='not_adopted':x.state.pop('n23_arithmetic_repair_authority')
    if fault in {'protected','slots'}:
        old=r.budget_snapshot
        def snap(*a):
            value=old(*a)
            if fault=='protected':value['gpu_hours_consumed']=34.
            else:value['by_bucket']['recovery']=18
            return value
        monkeypatch.setattr(r,'budget_snapshot',snap)
    reserve=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':{'validation':32.,'formal':12.},'rationale':'fixture','time_unix':1.}]
    if fault=='none':assert admit.admission(x.plan,x.state,x.events,[],reserve,root=x.root)==x.runtime
    else:
        with pytest.raises((ValueError,r.GateError)):admit.admission(x.plan,x.state,x.events,[],reserve,root=x.root)
    with pytest.raises(ValueError):prior.admission(x.previous.plan,x.state,x.events,[],reserve,root=x.root,r=vars(r))


def setup_composition(x,monkeypatch):
    x.source['files']=[{'path':p,'sha256':'fixture'} for p in sorted(c.source_paths(vars(r)))]
    write(repair.FINAL_REVIEW,x.review);x.auth['final_source_review']=c.ref(repair.FINAL_REVIEW)
    write(repair.AUTHORITY,x.auth);x.meta['authority']=c.ref(repair.AUTHORITY);x.state['n23_arithmetic_repair_authority']=x.meta['authority']
    write(x.root/'data/attempt-ledger.jsonl',x.events,True)
    write(x.root/'data/gpu-hour-reservation-ledger.jsonl',[{'event':'gpu_hour_reservations_changed',
        'gpu_hour_reservations':{'validation':32.,'formal':12.},'rationale':'fixture','time_unix':1.}],True)
    (x.root/'research-state.yaml').write_text(yaml.safe_dump(x.state))
    monkeypatch.setattr(b,'ROOT',x.root);monkeypatch.setattr(w,'source_record',lambda *_:copy.deepcopy(x.source))
    monkeypatch.setattr(w,'verify_source',lambda *_:None);monkeypatch.setattr(repair,'source_delta',lambda *_:[])
    monkeypatch.setattr(b,'corpus_from_index',lambda _:copy.deepcopy(x.first.old['corpus']))
    monkeypatch.setattr(b,'verify_corpus_files',lambda *_:None);monkeypatch.setattr(b,'predecessor_gate',lambda *_:{})
    monkeypatch.setattr(c,'predecessor_review',lambda:x.first.old['predecessor_review']);monkeypatch.setattr(c,'validate_runtime',lambda *_:None)
    monkeypatch.setattr(admit,'gpu_gate',lambda *a,**k:{'uuid':c.GPU7_UUID});monkeypatch.setattr(r,'child_environment',lambda *_:{})
    monkeypatch.setattr(r,'verify_provider',lambda *a,**k:(_ for _ in ()).throw(AssertionError('provider forbidden')))
    backend=AuditBackend(torch.device('cpu'),identity());backend.dtypes.update(['torch.float32','torch.bfloat16'])
    monkeypatch.setattr(b,'create_backend',lambda *a,**k:backend)
    monkeypatch.setattr(b,'iter_batches',lambda _:iter([{'batch':i,'dtype':'torch.bfloat16'} for i in range(176)]))
    monkeypatch.setattr(b,'synthetic_batches',lambda _:iter([{'synthetic':True,'dtype':dt} for dt in ('torch.float32','torch.bfloat16')]))
    monkeypatch.setattr(b,'check_batch',lambda batch,_:{'accepted':True,'candidates':4 if batch.get('synthetic') else 16,
        'dtype':batch['dtype'],'mismatches':[],'production_helper_passed':True,'independent_passed':True,'wrong_score_rejected':True})


@pytest.mark.parametrize('fault',['none','worker_error','worker_timeout','missing_proof','launch_error','fp32_rejected','identity'])
def test_one_charge_four_groups_same_source_dev_composition_and_no_fifth(case,monkeypatch,fault):
    x=case;setup_composition(x,monkeypatch);path=x.root/'backend-preflight-plan.arithmetic-repair.frozen.v3.json';write(path,x.plan)
    calls=[];codes=[];cleanup=[]
    def popen(command,**kwargs):
        calls.append(command);events=r.read_events(x.root/'data/attempt-ledger.jsonl')
        assert events[-1]['event']=='dispatched' and events[-1]['retry_of']==repair.FAILED_ATTEMPT
        assert r.budget_snapshot(events)['by_bucket']['recovery']==4 and str(x.root/'main.py') in command
        if fault=='launch_error':raise OSError('synthetic')
        if fault in {'none','worker_error','fp32_rejected','identity'}:
            if fault=='worker_error':monkeypatch.setattr(b,'create_backend',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('synthetic')))
            if fault=='fp32_rejected':monkeypatch.setattr(b,'check_batch',lambda batch,_:{'accepted':not batch.get('synthetic',False),'candidates':16,'mismatches':[{'check':'clipped_quality_or_mask'}] if batch.get('synthetic') else []})
            if fault=='identity':
                bad=identity();bad.pop('identity_diagnostic');backend=AuditBackend(torch.device('cpu'),bad);backend.dtypes.update(['torch.float32','torch.bfloat16'])
                monkeypatch.setattr(b,'create_backend',lambda *a,**k:backend)
            codes.append(b.run_preflight(command[command.index('--plan')+1],command[command.index('--release')+1],command[command.index('--attempt-context')+1]))
        return SimpleNamespace(pid=os.getpid())
    monkeypatch.setattr(admit.subprocess,'Popen',popen);monkeypatch.setattr(r,'terminate_owned',lambda p:cleanup.append(p))
    def wait(*a,**k):
        if fault=='worker_timeout':raise TimeoutError('synthetic')
        return codes[-1] if codes else 0
    monkeypatch.setattr(r,'wait_exclusively',wait)
    if fault=='none':terminal=admit.run(path,root=x.root)
    else:
        with pytest.raises((ValueError,r.GateError,OSError,TimeoutError)):admit.run(path,root=x.root)
    events=r.read_events(x.root/'data/attempt-ledger.jsonl');snap=r.budget_snapshot(events)
    assert snap['dispatched']==snap['by_bucket']['recovery']==4 and snap['running']==0 and len(cleanup)==1
    assert events[:9]==x.events and events[-1]['retry_of']==repair.FAILED_ATTEMPT
    assert snap['gpu_hours_consumed']*3600>=first.ORIGINAL_SECONDS+prior.FAILED_SECONDS+repair.FAILED_SECONDS
    assert events[-1]['outcome_valid'] is (fault=='none')
    with pytest.raises(ValueError):admit.run(path,root=x.root)
    assert len(calls)==1 and r.read_events(x.root/'data/attempt-ledger.jsonl')==events
    if fault!='none':return
    reference=json.loads((Path(terminal['output_dir'])/'backend-proof-reference.json').read_text())
    assert Path(reference['report']['path']).name=='n23-backend-arithmetic-repair-report-v3.json'
    assert c.backend_proof(reference,x.source,x.root,vars(r))==reference
    parent={'n22_cohort':{'cohort_id':'N22_HOLD_LIFT_DEV_20260930'},'scientific_config_files':[],
        'runtime_manifest_path':str(c.GPU7_RUNTIME),'stage_condition':r.E2_STAGE_CONDITION}
    parentpath=x.root/'parent.json';write(parentpath,parent);monkeypatch.setattr(c,'SOURCE_PLAN',parentpath)
    rows=[{'episode_key':f'{t}-{a}','task_id':t,'profile':a,'split':'dev','iteration':c.COHORT} for t in range(10) for a in c.ARMS]
    monkeypatch.setattr(c,'expected_rows',lambda:copy.deepcopy(rows))
    base=prepare.build_plan(predecessor=x.first.old['predecessor_review'],review=c.ref(repair.FINAL_REVIEW),proof=reference)
    dev=prepare.build_plan(predecessor=x.first.old['predecessor_review'],review=c.ref(repair.FINAL_REVIEW),proof=reference,uuid_repair=x.meta)
    manifest=r.read_json(r.ROOT/'configs/qd_ed_final/baseline_profiles.json')
    for arm in ('N7','N23'):manifest['profiles'][arm]=r.expand_candidate(arm,w.read_ref(dev['candidate_profiles'][arm]),manifest['profiles']['Q0'])
    reader=dict(vars(r));reader['read_state']=lambda *_:x.state;reader['read_events']=lambda *_:events
    c.validate_contract(dev,manifest,x.runtime,None,r.ROOT,reader)
    assert dev['episodes']==rows and dev['phase_authorization']=={'dev':True,'validation':False,'formal':False}
    del dev['n23_cohort']['uuid_repair'];assert dev==base


@pytest.mark.parametrize('fault',['none','fifth','unsettled','missing_retry','wrong_review','dev_before','dev_after','wrong_order'])
def test_four_group_proof_chronology_and_closed_temporal_dev_boundary(case,fault):
    x=case;planref=write(x.root/'fourth-plan.json',x.plan);reference={'attempt_id':'fourth','plan':planref}
    base={'attempt_id':'fourth','identity':{'iteration':c.PREFLIGHT},'n23_backend_preflight':True,
        'source_commit':x.source['commit'],'plan_sha256':planref['sha256'],'budget_bucket':'recovery','physical_gpu':7,
        'retry_of':repair.FAILED_ATTEMPT,'n23_uuid_repair':x.meta,'n23_final_review':c.ref(repair.FINAL_REVIEW)}
    new=[{**base,'event':e,**({'outcome_valid':True} if e=='valid' else {})} for e in ('reserved','dispatched','valid')]
    if fault=='missing_retry':new[0]['retry_of']=None
    if fault=='wrong_review':new[-1]['n23_final_review']=None
    if fault=='unsettled':new.pop()
    events=x.events+new
    if fault=='fifth':events.append({'attempt_id':'fifth','event':'reserved','n23_backend_preflight':True})
    dev={'attempt_id':'dev','event':'reserved','identity':{'iteration':c.COHORT}}
    if fault=='dev_before':events.insert(9,dev)
    if fault=='dev_after':events.append(dev)
    if fault=='wrong_order':events=new+x.events
    if fault in {'none','dev_after'}:assert repair.verify_lineage(x.plan,reference,events,x.source,vars(r))==new[-1]
    else:
        with pytest.raises(ValueError):repair.verify_lineage(x.plan,reference,events,x.source,vars(r))


@pytest.mark.parametrize('fault',['none','main','core','profile','audit_drift','preflight_drift'])
def test_exact_minimal_numerical_correction_and_scientific_source_gate(monkeypatch,tmp_path,fault):
    names={'main':'main.py','core':'core/qd_actuator_clipped_quality.py','profile':'configs/qd_ed_final/candidate_n23.json'}
    changed=[names[fault]] if fault in names else list(repair.CORRECTION)
    monkeypatch.setattr(repair.subprocess,'check_output',lambda *a,**k:'\n'.join(changed))
    if fault in {'audit_drift','preflight_drift'}:
        expected=dict(repair.CORRECTION);expected[list(expected)[int(fault=='preflight_drift')]]='changed';monkeypatch.setattr(repair,'CORRECTION',expected)
    if fault=='none':assert repair.source_delta(r.ROOT)==sorted(changed)
    else:
        with pytest.raises(ValueError):repair.source_delta(r.ROOT)


@pytest.mark.parametrize('owner,field',[(c,'PROTOCOL'),(c,'BACKEND_PROTOCOL'),(c,'BUDGET_AMENDMENT'),(c,'OBSERVABILITY'),
    (first,'EXCEPTION'),(first,'FAILURE_REVIEW'),(prior,'EXCEPTION'),(prior,'FAILURE_REVIEW'),(repair,'EXCEPTION'),(repair,'FAILURE_REVIEW')])
def test_immutable_scope_rechecked_before_release(case,monkeypatch,owner,field):
    changed=case.root/'drift.md';changed.write_text('changed');monkeypatch.setattr(owner,field,changed)
    with pytest.raises(ValueError,match='immutable'):repair.final_review(case.source,case.plan['runtime'])


@pytest.mark.parametrize('fault',['none','missing_wrong_score','wrong_bounds','wrong_dtype','wrong_synthetic_count',
    'unaccepted_fp32','helper','independent','errors','missing_batch'])
def test_success_proof_explicitly_requires_all_dtype_coverage_and_negative_controls(fault):
    good={'accepted':True,'mismatches':[],'production_helper_passed':True,'independent_passed':True,'wrong_score_rejected':True}
    report={'errors':[],'wrong_bounds_rejected':True,'batches':[{**good,'candidates':16,'dtype':'torch.bfloat16'} for _ in range(176)],
        'synthetic':[{**good,'candidates':4,'dtype':d} for d in ('torch.float32','torch.bfloat16')]}
    if fault=='missing_wrong_score':report['batches'][0].pop('wrong_score_rejected')
    if fault=='wrong_bounds':report['wrong_bounds_rejected']=False
    if fault=='wrong_dtype':report['synthetic'][0]['dtype']='torch.bfloat16'
    if fault=='wrong_synthetic_count':report['synthetic'][0]['candidates']=16
    if fault=='unaccepted_fp32':report['synthetic'][0]['accepted']=False
    if fault=='helper':report['batches'][0]['production_helper_passed']=False
    if fault=='independent':report['batches'][0]['independent_passed']=False
    if fault=='errors':report['errors']=['error']
    if fault=='missing_batch':report['batches'].pop()
    if fault=='none':repair.verify_arithmetic_success(report)
    else:
        with pytest.raises(ValueError):repair.verify_arithmetic_success(report)
