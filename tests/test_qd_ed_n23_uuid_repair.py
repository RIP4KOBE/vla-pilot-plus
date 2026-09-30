"""Prospective exact UUID repair: synthetic source/ledger/proof, never CUDA."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
import yaml
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_v2_backend as b
from scripts import qd_ed_n23_v2_preflight_admit as admit
from scripts import qd_ed_n23_v2_prepare as prepare
from scripts import qd_ed_n23_uuid_repair as repair
from scripts.qd_ed_audit_backend import AuditBackend


def write(path,value,lines=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(v)+'\n' for v in value) if lines else json.dumps(value))
    return c.ref(path)


@pytest.fixture(autouse=True)
def no_cuda():
    yield
    assert not torch.cuda.is_initialized()


@pytest.fixture
def case(tmp_path,monkeypatch):
    source={'commit':'repaired-source','files':[],'sha256':'source'}
    old_source={'commit':repair.ORIGINAL_SOURCE,'files':[],'sha256':'old-source'}
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID,'egl_device_index':4}}
    runtimeref=write(tmp_path/'runtime.json',runtime)
    monkeypatch.setattr(c,'GPU7_RUNTIME',Path(runtimeref['path']))
    old={'schema':'n23-backend-preflight-plan-v2','source':old_source,'worktree':str(tmp_path),
        'artifact_root':str(tmp_path/'artifacts'),'limits':b.LIMITS,'protocol':c.ref(c.BACKEND_PROTOCOL),
        'runtime':runtimeref,'corpus':{'index':write(tmp_path/'index.json',{}),'expected_batches':176,'expected_candidates':2816},
        'predecessor_review':{'path':'synthetic-prerequisite','sha256':'p'},'timeout_observability':c.ref(c.OBSERVABILITY),
        'synthetic_cases':'fp32_bf16_native_seven_point_v1','task_outcome':False,'requires_separate_release':True}
    oldref=write(tmp_path/'original-plan.json',old);monkeypatch.setattr(repair,'ORIGINAL_PLAN_SHA',oldref['sha256'])
    process={'pid':123,'proc_start_ticks':'456','boot_id':'synthetic'}
    report={'schema':'n23-backend-preflight-proof-v2','plan':oldref,'source':old_source,'attempt_id':repair.FAILED_ATTEMPT,
        'accepted':False,'task_outcome':False,'errors':[repair.ERROR],'batches':[],'synthetic':[],
        'runtime':runtimeref,'process':process}
    reportref=write(tmp_path/'original-report.json',report)
    row=admit.diagnostic_row();base={'attempt_id':repair.FAILED_ATTEMPT,'identity':r.episode_identity(row),
        'episode_key':row['episode_key'],'budget_bucket':'recovery','retry_of':None,'source_commit':repair.ORIGINAL_SOURCE,
        'plan_sha256':oldref['sha256'],'n23_backend_preflight':True,'task_outcome':False}
    terminal={**base,'event':'aborted','outcome_valid':False,'gpu_process_wall_seconds':repair.ORIGINAL_SECONDS,
        'n23_preflight_dispatched':True,'process':process}
    events=[{**base,'event':'reserved'},{**base,'event':'dispatched'},terminal]
    probe={'schema':'qd-ed-gpu-context-probe-v2','resource_id':c.GPU7_PROOF,'physical_gpu':7,'torch_logical_device':0,
        'torch_visible_device_count':1,'nvidia_physical_gpu':7,'nvidia_uuid':c.GPU7_UUID,'torch_uuid':c.GPU7_UUID[4:],
        'torch_version':'fixture','validation_status':'passed','simulation_steps':0,'cuda_visible_devices':'7','display_egl_device_index':4}
    proberef=write(tmp_path/'probe.json',probe)
    failure={'schema':'n23-preflight-uuid-fault-review-v1','attempt_id':repair.FAILED_ATTEMPT,
        'status':'INVALID_INFRASTRUCTURE_BEFORE_ARITHMETIC','task_outcome':False,'dev_dispatched':False,
        'arithmetic_batches':0,'synthetic_batches':0,'original_opportunity_consumed':True,
        'original_v1_v2_retry_authorized':False,'gpu_process_wall_seconds':repair.ORIGINAL_SECONDS,
        'current_failed_worker_raw_uuid':'not recorded; exact live value unavailable',
        'plan':oldref,'report':reportref,'attempt_result':write(tmp_path/'original-terminal.json',terminal),
        'original_source':old_source,'historical_accounted_probe':proberef,
        'historical_uuid_evidence':{k:probe[k] for k in ('torch_uuid','nvidia_uuid','torch_version','physical_gpu')}}
    failurepath=tmp_path/'failure-review.json';write(failurepath,failure)
    monkeypatch.setattr(repair,'FAILURE_REVIEW',failurepath);monkeypatch.setattr(repair,'FAILURE_SHA',c.sha(failurepath))
    review={'schema':'n23-final-source-runtime-review-uuid-repair-v1','disposition':'accepted','source':source,
        'runtime':runtimeref,'dev_protocol':c.ref(c.PROTOCOL),'backend_protocol':c.ref(c.BACKEND_PROTOCOL),
        'amendment':c.ref(c.BUDGET_AMENDMENT),'timeout_observability':c.ref(c.OBSERVABILITY),
        'exception':c.ref(repair.EXCEPTION),'failed_review':c.ref(failurepath),'no_gpu_release':True}
    reviewpath=tmp_path/'final-review.json';write(reviewpath,review);monkeypatch.setattr(repair,'FINAL_REVIEW',reviewpath)
    auth={'schema':'n23-uuid-repair-authority-v1','exception':c.ref(repair.EXCEPTION),'failed_review':c.ref(failurepath),
        'final_source_review':c.ref(reviewpath),'source':source,'runtime':runtimeref,'authority_interpretation':'synthetic',
        'recorded_at':'synthetic','user_message':c.AUTONOMOUS_REPLY,'cumulative_caps':repair.CAPS,'limits':repair.LIMITS,
        'validation_authorized':False,'formal_authorized':False}
    authpath=tmp_path/'authority.json';write(authpath,auth);monkeypatch.setattr(repair,'AUTHORITY',authpath)
    meta=repair.binding();plan={**old,'source':source,'uuid_repair':meta}
    state={'run_name':'synthetic','worktree':str(tmp_path),'artifacts':old['artifact_root'],'gpu_pool':[7],
        'max_concurrent_gpu_workers':1,'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':478,'max_gpu_hours':100.,'reserved':dict(r.N23_BUCKETS),
            'amendment':dict(r.GPU7_N23_V2_AMENDMENT),'dispatched':1,'gpu_hours_consumed':repair.ORIGINAL_SECONDS/3600,
            'running':0,'gpu_hour_reservations':{'validation':32.,'formal':12.}},
        'n23_v2_gpu7_binding':{'scope':c.COHORT+'_and_backend_preflight_only','user_reply':c.AUTONOMOUS_REPLY,
            'selected_gpu':7,'addendum_path':str(c.PROTOCOL),'addendum_sha256':c.PROTOCOL_SHA},'n23_uuid_repair_authority':meta['authority']}
    return SimpleNamespace(root=tmp_path,source=source,old=old,oldref=oldref,plan=plan,meta=meta,events=events,
        terminal=terminal,report=report,failure=failure,probe=probe,state=state,review=review,auth=auth,runtime=runtime)


@pytest.mark.parametrize('fault',['none','other_attempt','other_error','partial_arithmetic','partial_synthetic','valid_terminal',
    'cost_changed','source_changed','plan_changed','unsettled','missing_charge','wrong_probe','probe_diff','raw_claim'])
def test_named_failure_is_exact_before_arithmetic_and_retains_original_cost(case,monkeypatch,fault):
    x=case;f=x.failure
    if fault=='other_attempt':f['attempt_id']='other'
    if fault=='other_error':x.report['errors']=['other failure']
    if fault=='partial_arithmetic':x.report['batches']=[{}]
    if fault=='partial_synthetic':x.report['synthetic']=[{}]
    if fault=='valid_terminal':x.terminal['event']='valid'
    if fault=='cost_changed':x.terminal['gpu_process_wall_seconds']=0
    if fault=='source_changed':x.terminal['source_commit']='other'
    if fault=='plan_changed':x.report['plan']['sha256']='other'
    if fault=='unsettled':x.events.pop()
    if fault=='missing_charge':x.events.pop(1)
    if fault=='wrong_probe':f['historical_uuid_evidence']['torch_uuid']='00000000-0000-0000-0000-000000000001'
    if fault=='probe_diff':x.probe['display_egl_device_index']=3
    if fault=='raw_claim':f['current_failed_worker_raw_uuid']=c.GPU7_UUID[4:]
    f['report']=write(x.root/'original-report.json',x.report);f['attempt_result']=write(x.root/'original-terminal.json',x.terminal)
    f['historical_accounted_probe']=write(x.root/'probe.json',x.probe)
    write(repair.FAILURE_REVIEW,f);monkeypatch.setattr(repair,'FAILURE_SHA',c.sha(repair.FAILURE_REVIEW))
    if fault=='none':assert repair.named_failure(x.events,vars(r))[2]==x.terminal
    else:
        with pytest.raises((ValueError,KeyError)):repair.named_failure(x.events,vars(r))


@pytest.mark.parametrize('fault',['none','missing','not_adopted','source','runtime','limit','caps','protected','review','generic'])
def test_external_authority_is_explicit_finite_and_hash_bound(case,fault):
    x=case
    if fault=='missing':repair.AUTHORITY.unlink()
    if fault=='not_adopted':x.state.pop('n23_uuid_repair_authority')
    if fault=='source':x.auth['source']={'commit':'other'}
    if fault=='runtime':x.auth['runtime']={'path':'other','sha256':'other'}
    if fault=='limit':x.auth['limits']={**x.auth['limits'],'additional_backend_attempts':2}
    if fault=='caps':x.auth['cumulative_caps']={**x.auth['cumulative_caps'],'attempts':479}
    if fault=='protected':x.auth['formal_authorized']=True
    if fault=='review':x.auth['final_source_review']['sha256']='other'
    if fault=='generic':x.meta['retry_of']='other'
    if fault not in {'missing','generic','not_adopted'}:
        write(repair.AUTHORITY,x.auth);x.meta['authority']=c.ref(repair.AUTHORITY);x.state['n23_uuid_repair_authority']=x.meta['authority']
    if fault=='none':repair.authority(x.meta,x.source,x.plan['runtime'],x.state)
    else:
        with pytest.raises((ValueError,FileNotFoundError)):repair.authority(x.meta,x.source,x.plan['runtime'],x.state)


@pytest.mark.parametrize('fault',['none','source','corpus','runtime','protocol','arithmetic','worktree'])
def test_repair_plan_only_changes_source_and_explicit_lineage(case,monkeypatch,fault):
    x=case;monkeypatch.setattr(repair,'source_delta',lambda *_:[])
    if fault=='source':x.plan['source']={'commit':'other'}
    if fault=='corpus':x.plan['corpus']={**x.old['corpus'],'expected_candidates':2815}
    if fault=='runtime':x.plan['runtime']={'path':'other','sha256':'other'}
    if fault=='protocol':x.plan['protocol']={'path':'other','sha256':'other'}
    if fault=='arithmetic':x.plan['synthetic_cases']='changed'
    if fault=='worktree':x.plan['worktree']=str(x.root/'other')
    if fault=='none':assert repair.validate_plan(x.plan)==x.plan
    else:
        with pytest.raises(ValueError):repair.validate_plan(x.plan)


def stub_admission_inputs(x,monkeypatch):
    monkeypatch.setattr(w,'source_record',lambda *_:x.source)
    monkeypatch.setattr(c,'predecessor_review',lambda:x.old['predecessor_review'])
    monkeypatch.setattr(b,'validate_plan',lambda *_:x.runtime)
    monkeypatch.setattr(c,'validate_runtime',lambda *_:None)


@pytest.mark.parametrize('fault',['none','dev_reserved','v1_dev','other_backend','repair_reserved','repair_failed','unsettled',
    'not_adopted','protected','slots'])
def test_one_additional_opportunity_and_full_existing_reserves(case,monkeypatch,fault):
    x=case;stub_admission_inputs(x,monkeypatch)
    if fault in {'dev_reserved','v1_dev'}:x.events.append({'attempt_id':'dev','event':'reserved','identity':{'iteration':c.COHORT if fault=='dev_reserved' else c.v1.COHORT}})
    if fault in {'other_backend','repair_reserved','repair_failed'}:
        x.events.append({'attempt_id':'extra','event':'aborted' if fault=='repair_failed' else 'reserved',
            'identity':{'iteration':c.PREFLIGHT},'retry_of':repair.FAILED_ATTEMPT,'n23_backend_preflight':True})
    if fault=='unsettled':x.events.pop()
    if fault=='not_adopted':x.state.pop('n23_uuid_repair_authority')
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


def composition_setup(x,monkeypatch):
    # Full wrapper/admission/strict JSON proof composition with a CPU arithmetic stub.
    # Numeric checks and UUID device binding have their own focused CPU tests.
    x.source['files']=[{'path':p,'sha256':'synthetic'} for p in sorted(c.source_paths(vars(r)))]
    write(repair.FINAL_REVIEW,x.review);x.auth['final_source_review']=c.ref(repair.FINAL_REVIEW)
    write(repair.AUTHORITY,x.auth);x.meta['authority']=c.ref(repair.AUTHORITY);x.state['n23_uuid_repair_authority']=x.meta['authority']
    write(x.root/'data/attempt-ledger.jsonl',x.events,True)
    write(x.root/'data/gpu-hour-reservation-ledger.jsonl',[{'event':'gpu_hour_reservations_changed',
        'gpu_hour_reservations':{'validation':32.,'formal':12.},'rationale':'synthetic','time_unix':1.}],True)
    (x.root/'research-state.yaml').write_text(yaml.safe_dump(x.state))
    monkeypatch.setattr(b,'ROOT',x.root);monkeypatch.setattr(w,'source_record',lambda *_:copy.deepcopy(x.source))
    monkeypatch.setattr(w,'verify_source',lambda *_:None);monkeypatch.setattr(repair,'source_delta',lambda *_:[])
    monkeypatch.setattr(b,'corpus_from_index',lambda _:copy.deepcopy(x.old['corpus']))
    monkeypatch.setattr(b,'verify_corpus_files',lambda *_:None)
    monkeypatch.setattr(b,'predecessor_gate',lambda *_:{})
    monkeypatch.setattr(c,'predecessor_review',lambda:x.old['predecessor_review'])
    monkeypatch.setattr(c,'validate_runtime',lambda *_:None)
    monkeypatch.setattr(admit,'gpu_gate',lambda *a,**k:{'uuid':c.GPU7_UUID})
    monkeypatch.setattr(r,'child_environment',lambda *_:{})
    monkeypatch.setattr(r,'verify_provider',lambda *a,**k:(_ for _ in ()).throw(AssertionError('provider forbidden')))
    arithmetic=AuditBackend(torch.device('cpu'),{'kind':'cuda','logical_device':'cuda:0','physical_uuid':c.GPU7_UUID,
        'torch_version':'fixture','cuda_version':'fixture','actual_uuid':c.GPU7_UUID[4:]})
    arithmetic.dtypes.update(['torch.float32','torch.bfloat16'])
    monkeypatch.setattr(b,'create_backend',lambda *a,**k:arithmetic)
    monkeypatch.setattr(b,'iter_batches',lambda _:iter([{'batch':i} for i in range(176)]))
    monkeypatch.setattr(b,'synthetic_batches',lambda _:iter([{'synthetic':True}]*2))
    monkeypatch.setattr(b,'check_batch',lambda batch,_:{'accepted':True,'candidates':16,'mismatches':[]})
    monkeypatch.setattr(r,'terminate_owned',lambda _:None)


@pytest.mark.parametrize('fault',['none','worker_error','worker_timeout','missing_proof','launch_error'])
def test_repaired_preflight_charge_proof_and_unchanged_dev_composition(case,monkeypatch,fault):
    x=case;composition_setup(x,monkeypatch)
    path=x.root/'backend-preflight-plan.uuid-repair.frozen.v1.json';write(path,x.plan)
    calls=[];returncodes=[]
    def popen(command,**kwargs):
        calls.append(command);events=r.read_events(x.root/'data/attempt-ledger.jsonl')
        assert events[-1]['event']=='dispatched' and events[-1]['retry_of']==repair.FAILED_ATTEMPT
        assert r.budget_snapshot(events)['by_bucket']['recovery']==2
        assert str(x.root/'main.py') in command and '--ownership-main' in command
        if fault=='launch_error':raise OSError('synthetic launch error')
        if fault in {'none','worker_error'}:
            if fault=='worker_error':monkeypatch.setattr(b,'create_backend',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('synthetic error')))
            returncodes.append(b.run_preflight(command[command.index('--plan')+1],command[command.index('--release')+1],
                command[command.index('--attempt-context')+1]))
        return SimpleNamespace(pid=os.getpid())
    monkeypatch.setattr(admit.subprocess,'Popen',popen)
    def wait(*a,**k):
        if fault=='worker_timeout':raise TimeoutError('whole-worker timeout')
        return returncodes[-1] if returncodes else 0
    monkeypatch.setattr(r,'wait_exclusively',wait)
    if fault=='none':terminal=admit.run(path,root=x.root)
    else:
        with pytest.raises((ValueError,r.GateError,OSError,TimeoutError)):admit.run(path,root=x.root)
    events=r.read_events(x.root/'data/attempt-ledger.jsonl');snap=r.budget_snapshot(events)
    assert snap['dispatched']==snap['by_bucket']['recovery']==2 and snap['running']==0
    assert events[:3]==x.events and events[-1]['retry_of']==repair.FAILED_ATTEMPT
    assert snap['gpu_hours_consumed']*3600>=repair.ORIGINAL_SECONDS and len(calls)==1
    assert events[-1]['outcome_valid'] is (fault=='none')
    # No third attempt, even after launch failure or timeout; earlier outputs remain immutable.
    with pytest.raises(ValueError):admit.run(path,root=x.root)
    assert len(calls)==1 and r.read_events(x.root/'data/attempt-ledger.jsonl')==events
    if fault!='none':return
    output=Path(terminal['output_dir']);reference=json.loads((output/'backend-proof-reference.json').read_text())
    assert Path(reference['report']['path']).name=='n23-backend-uuid-repair-report-v1.json'
    assert c.backend_proof(reference,x.source,x.root,vars(r))==reference
    # Construct original40-cell Dev with unchanged identities/profiles; only provenance gains repair metadata.
    parent={'n22_cohort':{'cohort_id':'N22_HOLD_LIFT_DEV_20260930'},'scientific_config_files':[],
        'runtime_manifest_path':str(c.GPU7_RUNTIME),'stage_condition':r.E2_STAGE_CONDITION}
    parentpath=x.root/'parent-dev.json';write(parentpath,parent);monkeypatch.setattr(c,'SOURCE_PLAN',parentpath)
    rows=[{'episode_key':f'{t}-{arm}','task_id':t,'profile':arm,'split':'dev','iteration':c.COHORT} for t in range(10) for arm in c.ARMS]
    monkeypatch.setattr(c,'expected_rows',lambda:copy.deepcopy(rows))
    original=prepare.build_plan(predecessor=x.old['predecessor_review'],review=c.ref(repair.FINAL_REVIEW),proof=reference)
    dev=prepare.build_plan(predecessor=x.old['predecessor_review'],review=c.ref(repair.FINAL_REVIEW),proof=reference,uuid_repair=x.meta)
    assert dev['episodes']==rows and dev['source_commit']==x.source['commit']
    assert dev['n23_cohort']['backend_proof']==reference and dev['n23_cohort']['uuid_repair']==x.meta
    assert dev['phase_authorization']=={'dev':True,'validation':False,'formal':False}
    manifest=r.read_json(r.ROOT/'configs/qd_ed_final/baseline_profiles.json')
    for arm in ('N7','N23'):
        manifest['profiles'][arm]=r.expand_candidate(arm,w.read_ref(dev['candidate_profiles'][arm]),manifest['profiles']['Q0'])
    dispatch_reader=dict(vars(r));dispatch_reader['read_state']=lambda *_:x.state
    dispatch_reader['read_events']=lambda *_:events
    c.validate_contract(dev,manifest,x.runtime,None,r.ROOT,dispatch_reader)
    del dev['n23_cohort']['uuid_repair'];assert dev==original


@pytest.mark.parametrize('fault',['none','third','unsettled','missing_retry','changed_review','dev_before_repair','dev_after_repair'])
def test_repaired_proof_retains_both_attempts_and_temporal_dev_boundary(case,monkeypatch,fault):
    x=case;source=x.source;review=c.ref(repair.FINAL_REVIEW)
    planref=write(x.root/'repair-plan.json',x.plan)
    reference={'attempt_id':'repaired','plan':planref}
    base={'attempt_id':'repaired','identity':{'iteration':c.PREFLIGHT},'n23_backend_preflight':True,
        'source_commit':source['commit'],'plan_sha256':planref['sha256'],'budget_bucket':'recovery','physical_gpu':7,
        'retry_of':repair.FAILED_ATTEMPT,'n23_uuid_repair':x.meta,'n23_final_review':review}
    new=[{**base,'event':e,**({'outcome_valid':True} if e=='valid' else {})} for e in ('reserved','dispatched','valid')]
    if fault=='missing_retry':new[0]['retry_of']=None
    if fault=='changed_review':new[-1]['n23_final_review']=None
    if fault=='unsettled':new.pop()
    events=x.events+new
    if fault=='third':events.append({'attempt_id':'third','event':'reserved','n23_backend_preflight':True})
    dev={'attempt_id':'dev','event':'reserved','identity':{'iteration':c.COHORT}}
    if fault=='dev_before_repair':events.insert(3,dev)
    if fault=='dev_after_repair':events.append(dev)
    if fault in {'none','dev_after_repair'}:assert repair.verify_lineage(x.plan,reference,events,source,vars(r))==new[-1]
    else:
        with pytest.raises(ValueError):repair.verify_lineage(x.plan,reference,events,source,vars(r))


@pytest.mark.parametrize('which',['PROTOCOL','BACKEND_PROTOCOL','BUDGET_AMENDMENT','OBSERVABILITY','EXCEPTION','FAILURE_REVIEW'])
def test_repair_final_review_rechecks_all_frozen_hashes_before_dispatch(case,monkeypatch,which):
    x=case;owner=repair if which in {'EXCEPTION','FAILURE_REVIEW'} else c
    path=x.root/'changed-document';path.write_text('changed')
    monkeypatch.setattr(owner,which,path)
    with pytest.raises(ValueError,match='immutable'):repair.final_review(x.source,x.plan['runtime'])


@pytest.mark.parametrize('changed',[['scripts/qd_ed_audit_backend.py','scripts/qd_ed_n23_uuid_repair.py'],
    ['core/qd_actuator_clipped_quality.py'],['configs/qd_ed_final/candidate_n23.json'],['main.py']])
def test_repair_source_scope_rejects_any_scientific_delta(monkeypatch,changed):
    monkeypatch.setattr(repair.subprocess,'check_output',lambda *a,**k:'\n'.join(changed))
    if set(changed)<=repair.ALLOWED_DELTA:assert repair.source_delta(r.ROOT)==sorted(changed)
    else:
        with pytest.raises(ValueError,match='scientific'):repair.source_delta(r.ROOT)
