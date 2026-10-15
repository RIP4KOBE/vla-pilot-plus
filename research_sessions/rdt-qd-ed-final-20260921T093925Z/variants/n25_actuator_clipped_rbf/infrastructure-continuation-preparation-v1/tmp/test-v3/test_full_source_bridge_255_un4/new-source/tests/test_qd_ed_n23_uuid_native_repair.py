"""Synthetic third-opportunity admission and JSON proof; no actual CUDA/data."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
import yaml
from test_qd_ed_n23_uuid_repair import case as prior_case, write, no_cuda
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_v2_backend as b
from scripts import qd_ed_n23_v2_preflight_admit as admit
from scripts import qd_ed_n23_v2_prepare as prepare
from scripts import qd_ed_n23_uuid_repair as prior
from scripts import qd_ed_n23_uuid_native_repair as repair
from scripts.qd_ed_audit_backend import AuditBackend


@pytest.fixture
def case(prior_case,monkeypatch):
    first=prior_case;root=first.root
    first.source['commit']=repair.FAILED_SOURCE
    write(prior.FINAL_REVIEW,first.review);first.auth['final_source_review']=c.ref(prior.FINAL_REVIEW)
    write(prior.AUTHORITY,first.auth);first.meta['authority']=c.ref(prior.AUTHORITY)
    secondplan=write(root/'second-plan.json',first.plan)
    base={'attempt_id':repair.FAILED_ATTEMPT,'identity':r.episode_identity(admit.diagnostic_row(first.plan)),
        'episode_key':admit.diagnostic_row(first.plan)['episode_key'],'budget_bucket':'recovery',
        'retry_of':prior.FAILED_ATTEMPT,'source_commit':repair.FAILED_SOURCE,'plan_sha256':secondplan['sha256'],
        'n23_backend_preflight':True,'task_outcome':False,'physical_gpu':7,'n23_uuid_repair':first.meta,
        'n23_final_review':c.ref(prior.FINAL_REVIEW)}
    process={'pid':321,'proc_start_ticks':'654','boot_id':'synthetic'}
    report={'schema':'n23-backend-preflight-proof-v2','plan':secondplan,'source':first.source,
        'attempt_id':repair.FAILED_ATTEMPT,'accepted':False,'task_outcome':False,'errors':[prior.ERROR],
        'batches':[],'synthetic':[],'runtime':first.old['runtime'],'process':process,'uuid_repair':first.meta,
        'retry_of':prior.FAILED_ATTEMPT,'worker_wall_seconds':repair.FAILED_WORKER_SECONDS}
    terminal={**base,'event':'aborted','outcome_valid':False,'gpu_process_wall_seconds':repair.FAILED_SECONDS,
        'n23_preflight_dispatched':True,'process':process}
    events=first.events+[{**base,'event':'reserved'},{**base,'event':'dispatched'},terminal]
    failure={'schema':'n23-uuid-repair-native-type-failure-review-v1','attempt_id':repair.FAILED_ATTEMPT,
        'status':'INVALID_INFRASTRUCTURE_BEFORE_ARITHMETIC','task_outcome':False,'dev_dispatched':False,
        'gpu_process_wall_seconds':repair.FAILED_SECONDS,'additional_gpu_recovery_under_v1_authorized':False,
        'current_failed_worker_raw_uuid':'not recorded; neither failed worker exposed its live value',
        'prior_failure':c.ref(prior.FAILURE_REVIEW),'authority':c.ref(prior.AUTHORITY),'source':first.source,
        'plan':secondplan,'report':write(root/'second-report.json',report),
        'attempt_result':write(root/'second-terminal.json',terminal)}
    failurepath=root/'second-failure-review.json';write(failurepath,failure)
    monkeypatch.setattr(repair,'FAILURE_REVIEW',failurepath);monkeypatch.setattr(repair,'FAILURE_SHA',c.sha(failurepath))
    source={'commit':'native-source','files':[],'sha256':'native-source-hash'}
    review={'schema':'n23-final-source-runtime-review-uuid-native-repair-v2','disposition':'accepted',
        'source':source,'runtime':first.old['runtime'],'dev_protocol':c.ref(c.PROTOCOL),
        'backend_protocol':c.ref(c.BACKEND_PROTOCOL),'amendment':c.ref(c.BUDGET_AMENDMENT),
        'timeout_observability':c.ref(c.OBSERVABILITY),'exception':c.ref(repair.EXCEPTION),
        'failed_review':c.ref(failurepath),'prior_failure':c.ref(prior.FAILURE_REVIEW),'no_gpu_release':True}
    reviewpath=root/'native-review.json';write(reviewpath,review);monkeypatch.setattr(repair,'FINAL_REVIEW',reviewpath)
    auth={'schema':'n23-uuid-native-repair-authority-v2','exception':c.ref(repair.EXCEPTION),
        'failed_review':c.ref(failurepath),'prior_failure':c.ref(prior.FAILURE_REVIEW),
        'final_source_review':c.ref(reviewpath),'source':source,'runtime':first.old['runtime'],
        'authority_interpretation':'synthetic explicit engineering exception','recorded_at':'synthetic',
        'user_message':c.AUTONOMOUS_REPLY,'cumulative_caps':repair.CAPS,'limits':repair.LIMITS,
        'validation_authorized':False,'formal_authorized':False}
    authpath=root/'native-authority.json';write(authpath,auth);monkeypatch.setattr(repair,'AUTHORITY',authpath)
    meta=repair.binding();plan={**first.old,'source':source,'uuid_repair':meta}
    state=copy.deepcopy(first.state);state['n23_uuid_native_repair_authority']=meta['authority']
    state['budget']['dispatched']=2;state['budget']['gpu_hours_consumed']=(prior.ORIGINAL_SECONDS+repair.FAILED_SECONDS)/3600
    return SimpleNamespace(first=first,root=root,source=source,plan=plan,meta=meta,events=events,report=report,
        terminal=terminal,failure=failure,state=state,review=review,auth=auth,runtime=first.runtime)


@pytest.mark.parametrize('fault',['none','wrong_attempt','wrong_source','wrong_error','arithmetic','synthetic','cost',
    'worker_cost','retry','authority','prior_ref','missing_first','missing_second','unsettled','reordered','raw_claim'])
def test_exact_both_named_failures_and_costs(case,monkeypatch,fault):
    x=case
    if fault=='wrong_attempt':x.failure['attempt_id']='other'
    if fault=='wrong_source':x.report['source']={'commit':'other'}
    if fault=='wrong_error':x.report['errors']=['other']
    if fault=='arithmetic':x.report['batches']=[{}]
    if fault=='synthetic':x.report['synthetic']=[{}]
    if fault=='cost':x.terminal['gpu_process_wall_seconds']=0
    if fault=='worker_cost':x.report['worker_wall_seconds']=0
    if fault=='retry':x.terminal['retry_of']=None
    if fault=='authority':x.failure['authority']=None
    if fault=='prior_ref':x.failure['prior_failure']=None
    if fault=='missing_first':x.events=x.events[3:]
    if fault=='missing_second':x.events=x.events[:3]
    if fault=='unsettled':x.events.pop()
    if fault=='reordered':x.events=x.events[3:]+x.events[:3]
    if fault=='raw_claim':x.failure['current_failed_worker_raw_uuid']=c.GPU7_UUID
    x.failure['report']=write(x.root/'second-report.json',x.report)
    x.failure['attempt_result']=write(x.root/'second-terminal.json',x.terminal)
    write(repair.FAILURE_REVIEW,x.failure);monkeypatch.setattr(repair,'FAILURE_SHA',c.sha(repair.FAILURE_REVIEW))
    if fault=='none':assert repair.named_failures(x.events,vars(r))[2]==x.terminal
    else:
        with pytest.raises((ValueError,KeyError)):repair.named_failures(x.events,vars(r))


@pytest.mark.parametrize('fault',['none','missing','not_adopted','old_only','source','runtime','limit','fourth','caps',
    'protected','review','retry','schema','prior_attempt'])
def test_separate_exact_authority_never_reinterprets_v1(case,fault):
    x=case
    if fault=='missing':repair.AUTHORITY.unlink()
    if fault in {'not_adopted','old_only'}:x.state.pop('n23_uuid_native_repair_authority')
    if fault=='source':x.auth['source']={'commit':'other'}
    if fault=='runtime':x.auth['runtime']=None
    if fault=='limit':x.auth['limits']={**x.auth['limits'],'additional_backend_attempts':2}
    if fault=='fourth':x.auth['limits']={**x.auth['limits'],'max_total_backend_attempts':4}
    if fault=='caps':x.auth['cumulative_caps']={**x.auth['cumulative_caps'],'attempts':479}
    if fault=='protected':x.auth['validation_authorized']=True
    if fault=='review':x.auth['final_source_review']=None
    if fault=='retry':x.meta['retry_of']=prior.FAILED_ATTEMPT
    if fault=='schema':x.meta['schema']='generic_retry'
    if fault=='prior_attempt':x.meta['prior_attempt']='other'
    if fault not in {'missing','not_adopted','old_only','retry','schema','prior_attempt'}:
        write(repair.AUTHORITY,x.auth);x.meta['authority']=c.ref(repair.AUTHORITY);x.state['n23_uuid_native_repair_authority']=x.meta['authority']
    if fault=='none':assert repair.authority(x.meta,x.source,x.plan['runtime'],x.state)==x.auth
    else:
        with pytest.raises((ValueError,FileNotFoundError)):repair.authority(x.meta,x.source,x.plan['runtime'],x.state)
    if fault=='schema':
        with pytest.raises(ValueError):c.repair_module(x.meta)


@pytest.mark.parametrize('fault',['none','corpus','runtime','protocol','arithmetic','worktree','source'])
def test_only_source_and_lineage_differ_from_original_plan(case,monkeypatch,fault):
    x=case;monkeypatch.setattr(repair,'source_delta',lambda *_:[])
    key={'corpus':'corpus','runtime':'runtime','protocol':'protocol','arithmetic':'synthetic_cases','worktree':'worktree','source':'source'}.get(fault)
    if key:x.plan[key]='other'
    if fault=='none':assert repair.validate_plan(x.plan)==x.plan
    else:
        with pytest.raises(ValueError):repair.validate_plan(x.plan)


def stub_inputs(x,monkeypatch):
    monkeypatch.setattr(w,'source_record',lambda *_:x.source)
    monkeypatch.setattr(c,'predecessor_review',lambda:x.first.old['predecessor_review'])
    monkeypatch.setattr(b,'validate_plan',lambda *_:x.runtime)
    monkeypatch.setattr(c,'validate_runtime',lambda *_:None)


@pytest.mark.parametrize('fault',['none','dev_reserved','v1_dev','third_reserved','third_failed','fourth','unsettled',
    'not_adopted','protected','slots'])
def test_at_most_third_opportunity_and_unchanged_protected_reserves(case,monkeypatch,fault):
    x=case;stub_inputs(x,monkeypatch)
    if fault in {'dev_reserved','v1_dev'}:x.events.append({'attempt_id':'dev','event':'reserved','identity':{'iteration':c.COHORT if fault=='dev_reserved' else c.v1.COHORT}})
    if fault in {'third_reserved','third_failed','fourth'}:
        x.events.append({'attempt_id':'extra','event':'aborted' if fault=='third_failed' else 'reserved',
            'identity':{'iteration':c.PREFLIGHT},'retry_of':repair.FAILED_ATTEMPT,'n23_backend_preflight':True})
    if fault=='unsettled':x.events.pop()
    if fault=='not_adopted':x.state.pop('n23_uuid_native_repair_authority')
    if fault in {'protected','slots'}:
        original=r.budget_snapshot
        def snap(*a):
            value=original(*a)
            if fault=='protected':value['gpu_hours_consumed']=34.
            else:value['by_bucket']['recovery']=18
            return value
        monkeypatch.setattr(r,'budget_snapshot',snap)
    reserve=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':{'validation':32.,'formal':12.},'rationale':'synthetic','time_unix':1.}]
    if fault=='none':assert admit.admission(x.plan,x.state,x.events,[],reserve,root=x.root)==x.runtime
    else:
        with pytest.raises((ValueError,r.GateError)):admit.admission(x.plan,x.state,x.events,[],reserve,root=x.root)
    # Old exception remains exhausted even with new authority present.
    with pytest.raises(ValueError):prior.admission(x.first.plan,x.state,x.events,[],reserve,root=x.root,r=vars(r))


def identity(kind='torch._C._CUuuid'):
    raw=c.GPU7_UUID[4:]
    return {'kind':'cuda','logical_device':'cuda:0','physical_uuid':c.GPU7_UUID,'torch_version':'fixture','cuda_version':'fixture',
        'actual_uuid':raw,'actual_uuid_type':kind,'actual_uuid_bytes_hex':raw.replace('-','') if kind=='torch._C._CUuuid' else None,
        'cuda_visible_devices':'7','identity_diagnostic':{'schema':'n23-public-cuda-identity-diagnostic-v1',
            'expected_physical_gpu':7,'expected_uuid':c.GPU7_UUID,'cuda_visible_devices':'7','visible_device_count':1,
            'current_device':0,'uuid_public_type':kind,'serialized_raw_uuid':raw,'canonical_uuid':c.GPU7_UUID,'status':'matched'}}


@pytest.mark.parametrize('fault',['native','str','missing_raw','wrong_raw','type','missing_hex','wrong_hex','str_hex',
    'missing_diagnostic','count','count_bool','logical','logical_bool','mask','status','diagnostic_raw','canonical','expected'])
def test_proof_requires_json_safe_raw_type_hex_and_matched_diagnostic(case,fault):
    value=identity('builtins.str' if fault in {'str','str_hex'} else 'torch._C._CUuuid')
    if fault=='missing_raw':value.pop('actual_uuid')
    if fault=='wrong_raw':value['actual_uuid']='00000000-0000-0000-0000-000000000001'
    if fault=='type':value['actual_uuid_type']='fake'
    if fault=='missing_hex':value.pop('actual_uuid_bytes_hex')
    if fault in {'wrong_hex','str_hex'}:value['actual_uuid_bytes_hex']='00'*16
    if fault=='missing_diagnostic':value.pop('identity_diagnostic')
    if fault in {'count','logical','mask','status','diagnostic_raw','canonical','expected'}:
        key={'count':'visible_device_count','logical':'current_device','mask':'cuda_visible_devices','status':'status',
            'diagnostic_raw':'serialized_raw_uuid','canonical':'canonical_uuid','expected':'expected_uuid'}[fault]
        value['identity_diagnostic'][key]='other'
    if fault=='count_bool':value['identity_diagnostic']['visible_device_count']=True
    if fault=='logical_bool':value['identity_diagnostic']['current_device']=False
    if fault in {'native','str'}:repair.verify_identity(json.loads(json.dumps(value)),case.runtime)
    else:
        with pytest.raises(ValueError):repair.verify_identity(value,case.runtime)


def composition_setup(x,monkeypatch):
    x.source['files']=[{'path':p,'sha256':'synthetic'} for p in sorted(c.source_paths(vars(r)))]
    write(repair.FINAL_REVIEW,x.review);x.auth['final_source_review']=c.ref(repair.FINAL_REVIEW)
    write(repair.AUTHORITY,x.auth);x.meta['authority']=c.ref(repair.AUTHORITY);x.state['n23_uuid_native_repair_authority']=x.meta['authority']
    write(x.root/'data/attempt-ledger.jsonl',x.events,True)
    write(x.root/'data/gpu-hour-reservation-ledger.jsonl',[{'event':'gpu_hour_reservations_changed',
        'gpu_hour_reservations':{'validation':32.,'formal':12.},'rationale':'synthetic','time_unix':1.}],True)
    (x.root/'research-state.yaml').write_text(yaml.safe_dump(x.state))
    monkeypatch.setattr(b,'ROOT',x.root);monkeypatch.setattr(w,'source_record',lambda *_:copy.deepcopy(x.source))
    monkeypatch.setattr(w,'verify_source',lambda *_:None);monkeypatch.setattr(repair,'source_delta',lambda *_:[])
    monkeypatch.setattr(b,'corpus_from_index',lambda _:copy.deepcopy(x.first.old['corpus']))
    monkeypatch.setattr(b,'verify_corpus_files',lambda *_:None);monkeypatch.setattr(b,'predecessor_gate',lambda *_:{})
    monkeypatch.setattr(c,'predecessor_review',lambda:x.first.old['predecessor_review'])
    monkeypatch.setattr(c,'validate_runtime',lambda *_:None);monkeypatch.setattr(admit,'gpu_gate',lambda *a,**k:{'uuid':c.GPU7_UUID})
    monkeypatch.setattr(r,'child_environment',lambda *_:{})
    monkeypatch.setattr(r,'verify_provider',lambda *a,**k:(_ for _ in ()).throw(AssertionError('provider forbidden')))
    arithmetic=AuditBackend(torch.device('cpu'),identity());arithmetic.dtypes.update(['torch.float32','torch.bfloat16'])
    monkeypatch.setattr(b,'create_backend',lambda *a,**k:arithmetic)
    monkeypatch.setattr(b,'iter_batches',lambda _:iter([{'batch':i} for i in range(176)]))
    monkeypatch.setattr(b,'synthetic_batches',lambda _:iter([{'synthetic':True}]*2))
    monkeypatch.setattr(b,'check_batch',lambda batch,_:{'accepted':True,'candidates':16,'mismatches':[]})
    monkeypatch.setattr(r,'terminate_owned',lambda _:None)


@pytest.mark.parametrize('fault',['none','worker_error','worker_timeout','missing_proof','launch_error','bad_identity_proof'])
def test_native_preflight_charge_proof_then_unchanged_dev_and_no_fourth(case,monkeypatch,fault):
    x=case;composition_setup(x,monkeypatch)
    path=x.root/'backend-preflight-plan.uuid-native-repair.frozen.v2.json';write(path,x.plan)
    calls=[];returncodes=[];cleanup=[]
    def popen(command,**kwargs):
        calls.append(command);events=r.read_events(x.root/'data/attempt-ledger.jsonl')
        assert events[-1]['event']=='dispatched' and events[-1]['retry_of']==repair.FAILED_ATTEMPT
        assert r.budget_snapshot(events)['by_bucket']['recovery']==3
        assert str(x.root/'main.py') in command and '--ownership-main' in command
        if fault=='launch_error':raise OSError('synthetic launch error')
        if fault in {'none','worker_error','bad_identity_proof'}:
            if fault=='worker_error':monkeypatch.setattr(b,'create_backend',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('synthetic error')))
            if fault=='bad_identity_proof':
                broken=identity();broken.pop('actual_uuid_type')
                arithmetic=AuditBackend(torch.device('cpu'),broken);arithmetic.dtypes.update(['torch.float32','torch.bfloat16'])
                monkeypatch.setattr(b,'create_backend',lambda *a,**k:arithmetic)
            returncodes.append(b.run_preflight(command[command.index('--plan')+1],command[command.index('--release')+1],
                command[command.index('--attempt-context')+1]))
        return SimpleNamespace(pid=os.getpid())
    monkeypatch.setattr(admit.subprocess,'Popen',popen)
    monkeypatch.setattr(r,'terminate_owned',lambda p:cleanup.append(p))
    def wait(*a,**k):
        if fault=='worker_timeout':raise TimeoutError('whole-worker timeout')
        return returncodes[-1] if returncodes else 0
    monkeypatch.setattr(r,'wait_exclusively',wait)
    if fault=='none':terminal=admit.run(path,root=x.root)
    else:
        with pytest.raises((ValueError,r.GateError,OSError,TimeoutError)):admit.run(path,root=x.root)
    events=r.read_events(x.root/'data/attempt-ledger.jsonl');snap=r.budget_snapshot(events)
    assert snap['dispatched']==snap['by_bucket']['recovery']==3 and snap['running']==0 and len(cleanup)==1
    assert events[:6]==x.events and events[-1]['retry_of']==repair.FAILED_ATTEMPT
    assert snap['gpu_hours_consumed']*3600>=prior.ORIGINAL_SECONDS+repair.FAILED_SECONDS and len(calls)==1
    assert events[-1]['outcome_valid'] is (fault=='none')
    with pytest.raises(ValueError):admit.run(path,root=x.root)
    assert len(calls)==1 and r.read_events(x.root/'data/attempt-ledger.jsonl')==events
    if fault!='none':return
    output=Path(terminal['output_dir']);reference=json.loads((output/'backend-proof-reference.json').read_text())
    assert Path(reference['report']['path']).name=='n23-backend-uuid-native-repair-report-v2.json'
    assert c.backend_proof(reference,x.source,x.root,vars(r))==reference
    parent={'n22_cohort':{'cohort_id':'N22_HOLD_LIFT_DEV_20260930'},'scientific_config_files':[],
        'runtime_manifest_path':str(c.GPU7_RUNTIME),'stage_condition':r.E2_STAGE_CONDITION}
    parentpath=x.root/'parent-dev.json';write(parentpath,parent);monkeypatch.setattr(c,'SOURCE_PLAN',parentpath)
    rows=[{'episode_key':f'{t}-{arm}','task_id':t,'profile':arm,'split':'dev','iteration':c.COHORT} for t in range(10) for arm in c.ARMS]
    monkeypatch.setattr(c,'expected_rows',lambda:copy.deepcopy(rows))
    original=prepare.build_plan(predecessor=x.first.old['predecessor_review'],review=c.ref(repair.FINAL_REVIEW),proof=reference)
    dev=prepare.build_plan(predecessor=x.first.old['predecessor_review'],review=c.ref(repair.FINAL_REVIEW),proof=reference,uuid_repair=x.meta)
    assert dev['episodes']==rows and dev['source_commit']==x.source['commit']
    assert dev['phase_authorization']=={'dev':True,'validation':False,'formal':False}
    manifest=r.read_json(r.ROOT/'configs/qd_ed_final/baseline_profiles.json')
    for arm in ('N7','N23'):manifest['profiles'][arm]=r.expand_candidate(arm,w.read_ref(dev['candidate_profiles'][arm]),manifest['profiles']['Q0'])
    reader=dict(vars(r));reader['read_state']=lambda *_:x.state;reader['read_events']=lambda *_:events
    c.validate_contract(dev,manifest,x.runtime,None,r.ROOT,reader)
    del dev['n23_cohort']['uuid_repair'];assert dev==original


@pytest.mark.parametrize('fault',['none','fourth','unsettled','missing_retry','wrong_review','dev_before','dev_after','wrong_order'])
def test_valid_proof_preserves_three_groups_and_dev_temporal_boundary(case,fault):
    x=case;planref=write(x.root/'native-plan.json',x.plan);reference={'attempt_id':'third','plan':planref}
    base={'attempt_id':'third','identity':{'iteration':c.PREFLIGHT},'n23_backend_preflight':True,
        'source_commit':x.source['commit'],'plan_sha256':planref['sha256'],'budget_bucket':'recovery','physical_gpu':7,
        'retry_of':repair.FAILED_ATTEMPT,'n23_uuid_repair':x.meta,'n23_final_review':c.ref(repair.FINAL_REVIEW)}
    new=[{**base,'event':e,**({'outcome_valid':True} if e=='valid' else {})} for e in ('reserved','dispatched','valid')]
    if fault=='missing_retry':new[0]['retry_of']=None
    if fault=='wrong_review':new[-1]['n23_final_review']=None
    if fault=='unsettled':new.pop()
    events=x.events+new
    if fault=='fourth':events.append({'attempt_id':'fourth','event':'reserved','n23_backend_preflight':True})
    dev={'attempt_id':'dev','event':'reserved','identity':{'iteration':c.COHORT}}
    if fault=='dev_before':events.insert(6,dev)
    if fault=='dev_after':events.append(dev)
    if fault=='wrong_order':events=new+x.events
    if fault in {'none','dev_after'}:assert repair.verify_lineage(x.plan,reference,events,x.source,vars(r))==new[-1]
    else:
        with pytest.raises(ValueError):repair.verify_lineage(x.plan,reference,events,x.source,vars(r))


@pytest.mark.parametrize('which',['PROTOCOL','BACKEND_PROTOCOL','BUDGET_AMENDMENT','OBSERVABILITY','EXCEPTION','FAILURE_REVIEW',
    'prior.EXCEPTION','prior.FAILURE_REVIEW'])
def test_all_frozen_documents_rechecked_before_release(case,monkeypatch,which):
    owner=prior if which.startswith('prior.') else repair if which in {'EXCEPTION','FAILURE_REVIEW'} else c
    name=which.split('.')[-1];path=case.root/'drift.md';path.write_text('changed');monkeypatch.setattr(owner,name,path)
    with pytest.raises(ValueError,match='immutable'):repair.final_review(case.source,case.plan['runtime'])


@pytest.mark.parametrize('changed',[['scripts/qd_ed_n23_uuid_native_repair.py','scripts/qd_ed_audit_backend.py'],
    ['main.py'],['core/qd_actuator_clipped_quality.py'],['configs/qd_ed_final/candidate_n23.json'],['scripts/unrelated.py']])
def test_no_numerical_profile_stage_or_unrelated_source_delta(monkeypatch,changed):
    monkeypatch.setattr(repair.subprocess,'check_output',lambda *a,**k:'\n'.join(changed))
    if set(changed)<=repair.ALLOWED_DELTA:assert repair.source_delta(r.ROOT)==sorted(changed)
    else:
        with pytest.raises(ValueError,match='scientific'):repair.source_delta(r.ROOT)
