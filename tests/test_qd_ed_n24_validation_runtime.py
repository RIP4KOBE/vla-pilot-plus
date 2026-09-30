"""Reuse actual original validator synthetic builders; never legacy real-data tests."""
import copy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n24_validation_contract as c
from scripts import qd_ed_n24_validation_recovery as recovery
from scripts import qd_ed_n24_recovery as frozen_recovery
from scripts import qd_ed_n24_validation_identity as identity
from scripts import qd_ed_n24_validation_report as reporting
from scripts import qd_ed_n24_validation_supervise as sup
from test_qd_ed_n24_validation import seeds,events_for
from test_qd_ed_n24_controller import write,state,triplet,metric,native_report

def rows():return identity.rows_for(seeds(),"c2")

spec=importlib.util.spec_from_file_location('n24_old_synthetic_builders',r.ROOT/'tests/test_qd_ed_n23_v2.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)


@pytest.mark.parametrize('fault',['none','agent','completed','other_error','missing_events','extra_failure','native',
    'valid','recovery','interrupted','wall_timeout','qpos','config','counter_missing','scoring_postgate','source','receipt','safety_presence','absent_metrics','absent_then_present','absent_terminal_unknown','absent_native_nonzero','absent_compute_nonzero'])
def test_actual_classifier_and_new_eligibility_envelope(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(old.c,'OBSERVABILITY',r.ROOT/'experiments/iteration_023_actuator_clipped_quality/timeout-observability-addendum-v2.md')
    output=tmp_path/'output';output.mkdir()
    rr,row,profile,runtime,final,stage,compute=old.failing_case(output,monkeypatch)
    row.update(iteration=c.COHORT,split="validation",budget_bucket="validation",episode_key='n24_timeout_fixture');final.update(identity=rr.episode_identity(row),episode_key=row['episode_key'])
    manifest=write(tmp_path/'profiles.json',{'profiles':{'C0':profile}});rt=write(tmp_path/'runtime.json',runtime)
    for module,k in ((c,'PROTOCOL'),(c.dev,'OBSERVABILITY')):
        p=tmp_path/k;p.write_text(k);monkeypatch.setattr(module,k,p)
    plan={'episodes':[row],'source_commit':'synthetic','profiles_path':manifest['path'],'profiles_sha256':manifest['sha256'],
        'candidate_profiles':{},'runtime_manifest_path':rt['path'],'runtime_manifest_sha256':rt['sha256'],
        'runtime_inventory_sha256':'inventory','artifact_root':str(tmp_path),'worktree':str(tmp_path)}
    planref=write(tmp_path/'plan.json',plan);receipt=write(output/'eds_eval/in-worker-audit-receipt.json',{})
    report=old.native_report(output);report['observed_counts']={'decision_context':1}
    final.update(plan_sha256=planref['sha256'],profile_manifest_sha256=manifest['sha256'],runtime_manifest_sha256=rt['sha256'],
        runtime_inventory_sha256='inventory',physical_gpu=7,n23_worker_receipt=receipt,budget_bucket='validation')
    if fault=='agent':stage[1]['transport']['item_types']=['agent_message']
    if fault=='completed':stage[1]['transport']['event_types'].append('turn.completed')
    if fault=='other_error':stage[1]['error']='codex_transport_failure'
    if fault=='missing_events':stage[1]['transport'].pop('event_types')
    if fault=='extra_failure':stage[0]['query_ok']=False
    if fault=='native':report['accepted']=False
    if fault=='valid':final['outcome_valid']=True
    if fault=='recovery':final['retry_of']='earlier'
    if fault=='interrupted':final['event']='aborted'
    if fault=='wall_timeout':final['gpu_process_wall_seconds']=1801.
    if fault=='qpos':write(output/'eds_eval/safety_events.jsonl',[{'event':'gripper_qpos_violation','count':1}],True)
    if fault=='config':p=output/'.hydra/config.yaml';v=yaml.safe_load(p.read_text());v['seed']=-1;p.write_text(yaml.safe_dump(v))
    if fault=='counter_missing':compute.pop('model_forward_calls')
    if fault in {'scoring_postgate','absent_compute_nonzero'}:compute['guided_chunks']=1
    if fault.startswith('absent'):(output/'eds_eval/eds_metrics.jsonl').unlink()
    if fault=='absent_terminal_unknown':final['guided_chunks']=None
    if fault=='absent_native_nonzero':report['observed_counts']['canonical_candidate_batch']=11
    write(output/'eds_eval/stage_events.jsonl',stage,True);write(output/'eds_eval/episode_compute.jsonl',[compute],True)
    write(output/'eds_eval/decision-evidence-audit.json',report);write(output/'process.json',{'pid':1})
    write(output/'attempt-result.json',final)
    journal=triplet(row,final['attempt_id'],valid=False);journal[-1]=final
    monkeypatch.setattr(c,'read_worker_report',lambda *a:report)
    if fault not in {'none','source','receipt','safety_presence','absent_metrics','absent_then_present'}:
        with pytest.raises((ValueError,r.GateError,rr.GateError,KeyError)):
            recovery.create_eligibility(planref['path'],plan,row,final,profile,runtime,journal,tmp_path,vars(rr))
        return
    # Absence is a real legal no-event state, bound without creating a historical file.
    (output/'eds_eval/safety_events.jsonl').unlink()
    original_reader=frozen_recovery.classifier().evidence_files
    record=recovery.create_eligibility(planref['path'],plan,row,final,profile,runtime,journal,tmp_path,vars(rr))
    assert frozen_recovery.classifier().evidence_files is original_reader
    assert record['evidence_packaging_reader']==c.ref(frozen_recovery.__file__)
    assert record['diagnostic']['diagnostic_reader']==c.ref(frozen_recovery.classifier().__file__)
    if fault.startswith('absent'):assert record['evidence_packaging_mode']=='n24_absent_zero_guided_private_reader' and record['evidence_files']['metrics']['present'] is False
    assert record['diagnostic']['outcome_valid'] is False and record['unknown_token_calls']==1
    assert final['provider_token_usage_complete'] is False and final['required_cost_telemetry_complete'] is False
    reference=write(tmp_path/'eligibility.json',record)
    if fault=='source':record['source_commit']='other';reference=write(tmp_path/'eligibility.json',record)
    if fault=='receipt':write(output/'eds_eval/in-worker-audit-receipt.json',{'changed':True})
    if fault=='safety_presence':write(output/'eds_eval/safety_events.jsonl',[],True)
    if fault=='absent_then_present':write(output/'eds_eval/eds_metrics.jsonl',[],True)
    if fault in {'none','absent_metrics'}:
        assert recovery.verify_eligibility(reference,plan,row,journal,tmp_path,vars(rr))==record
        with c.supervised_scope(plan,tmp_path,row['episode_key'],eligibility=reference):
            actual=c.effective_row(plan,row,journal,tmp_path,vars(rr))
            assert actual==dict(row,budget_bucket='recovery',retry_of=final['attempt_id'],n24_validation_recovery_eligibility=reference)
        with pytest.raises(rr.GateError):rr.validate_result(output,row,profile,runtime)
    else:
        with pytest.raises((ValueError,rr.GateError)):recovery.verify_eligibility(reference,plan,row,journal,tmp_path,vars(rr))


@pytest.mark.parametrize('fault',['none','valid','duplicate','two_prior','recovery','aborted','missing','identity'])
def test_one_recovery_per_cell_two_total(fault):
    row=rows()[0];events=triplet(row,'a',valid=False)
    if fault=='valid':events[-1]['outcome_valid']=True
    if fault=='duplicate':events+=triplet(row,'b',valid=False)
    if fault=='two_prior':
        for i in (1,2):events+=triplet(rows()[i],str(i),retry='earlier')
    if fault=='recovery':events[0]['retry_of']='earlier'
    if fault=='aborted':events[-1]['event']='aborted'
    if fault=='missing':events.pop(1)
    if fault=='identity':events[0]['identity']['task_id']=9
    if fault=='none':assert recovery.check_cell_history(events,row,'a',vars(r))==events[-1]
    else:
        with pytest.raises((ValueError,r.GateError)):recovery.check_cell_history(events,row,'a',vars(r))


@pytest.mark.parametrize('arm',c.ARMS)
@pytest.mark.parametrize('scenario',['valid','typed_recovery','failed_recovery','missing_receipt','timeout','launch_error'])
def test_real_runner_wrapper_charge_cleanup_and_same_cell(tmp_path,monkeypatch,arm,scenario):
    (tmp_path/'data').mkdir();st=state();st['budget'].update(dispatched=0,gpu_hours_consumed=0.,running=0);st.update(run_name='CPU',worktree=str(tmp_path),artifacts=str(tmp_path/'artifact'))
    (tmp_path/'research-state.yaml').write_text(yaml.safe_dump(st));write(tmp_path/'data/gpu-hour-reservation-ledger.jsonl',old.reservations(),True)
    row=next(v for v in rows() if v['profile']==arm)
    plan={'source_commit':'synthetic','run_name':'CPU','worktree':str(tmp_path),'artifact_root':st['artifacts'],
        'candidate_profiles':{'N24':{}},'n24_cohort':c.WORKER_MARKER,'n24_validation':{},'episodes':[row],
        'phase_authorization':{'dev':False,'validation':True,'formal':False},'profiles_sha256':'p',
        'runtime_manifest_sha256':'r','runtime_manifest_path':'synthetic','runtime_inventory_sha256':'i'}
    path=tmp_path/'plan.json';write(path,plan)
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID,'egl_device_index':4},'environment':{}}
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(plan,{'profiles':{arm:{}}},runtime))
    monkeypatch.setattr(c,'require_budget_state',lambda *a:None);monkeypatch.setattr(c,'protected_budget',lambda *a,**k:None)
    monkeypatch.setattr(c,'admission',lambda *a,**k:{'n24_validation_cohort_id':c.COHORT,'n24_validation_seed_block':row['seed_block']})
    monkeypatch.setattr(r,'gpu_admission',lambda **k:{});monkeypatch.setattr(r,'child_environment',lambda *a:{})
    providers=[];monkeypatch.setattr(r,'verify_provider',lambda *a,**k:providers.append(1))
    monkeypatch.setattr(w,'build_context',lambda *a:{'synthetic':True})
    original=[str(r.PYTHON),str(tmp_path/'main.py'),'policy.type=rdt','literal=value with spaces']
    selected=[];launched=[];cleaned=[]
    def command(p,m,rt,row,aid):selected.append(copy.deepcopy(row));return original,Path(p['artifact_root'])/'attempts'/aid
    monkeypatch.setattr(r,'build_command',command)
    def popen(argv,**kwargs):
        launched.append(argv);assert argv[argv.index('--')+1:]==original[2:] and str(tmp_path/'main.py') in argv
        assert r.read_events(tmp_path/'data/attempt-ledger.jsonl')[-1]['event']=='dispatched'
        if scenario=='launch_error':raise OSError('synthetic launch failure')
        return SimpleNamespace(pid=os.getpid())
    monkeypatch.setattr(r.subprocess,'Popen',popen)
    def wait(p,t,**kwargs):
        assert t==1800
        if scenario=='timeout':raise TimeoutError('whole worker timeout')
        return 0
    monkeypatch.setattr(r,'wait_exclusively',wait);monkeypatch.setattr(r,'terminate_owned',lambda p:cleaned.append(p))
    def outcome(*a):
        if scenario in {'typed_recovery','failed_recovery'} and (len(launched)==1 or scenario=='failed_recovery'):raise r.GateError('Codex token usage incomplete')
        return {'success':False,'outcome_valid':True,'required_cost_telemetry_complete':True}
    monkeypatch.setattr(r,'validate_result',outcome)
    def audit(output,env):
        if scenario=='missing_receipt':raise ValueError('missing receipt')
        assert json.loads((output/'process.json').read_text())['pid']==os.getpid()
        write(output/'eds_eval/in-worker-audit-receipt.json',{})
        return {'accepted':True,'evidence_complete':True}
    monkeypatch.setattr(c,'read_worker_report',audit)
    with c.supervised_scope(plan,tmp_path,row['episode_key']):
        if scenario=='valid':r.run_plan(path,split='validation',iteration=c.COHORT,root=tmp_path)
        else:
            with pytest.raises(r.GateError):r.run_plan(path,split='validation',iteration=c.COHORT,root=tmp_path)
    primary=r.read_events(tmp_path/'data/attempt-ledger.jsonl')[-1]
    if scenario in {'typed_recovery','failed_recovery'}:
        assert primary['n23_worker_receipt'] and primary['process']['pid']==os.getpid()
        record={'primary_attempt_id':primary['attempt_id'],'plan':c.ref(path)};ref=write(tmp_path/'eligibility.json',record)
        monkeypatch.setattr(recovery,'verify_eligibility',lambda *a:record)
        with c.supervised_scope(plan,tmp_path,row['episode_key'],eligibility=ref):
            if scenario=='typed_recovery':r.run_plan(path,split='validation',iteration=c.COHORT,root=tmp_path)
            else:
                with pytest.raises(r.GateError):r.run_plan(path,split='validation',iteration=c.COHORT,root=tmp_path)
        assert selected[1]==dict(row,budget_bucket='recovery',retry_of=primary['attempt_id'],n24_validation_recovery_eligibility=ref)
    events=r.read_events(tmp_path/'data/attempt-ledger.jsonl');snap=r.budget_snapshot(events)
    expected=2 if 'recovery' in scenario else 1
    assert snap['dispatched']==expected and snap['running']==0 and len(launched)==len(providers)==len(cleaned)==expected
    assert snap['by_bucket'][row['budget_bucket']]==1 and snap['by_bucket']['recovery']==expected-1
    assert all(e['identity']==r.episode_identity(row) for e in events)
    assert events[-1]['outcome_valid'] is (scenario in {'valid','typed_recovery'}) and events[-1]['n24_validation_episode_dispatched']

@pytest.fixture
def cohort(tmp_path,monkeypatch):
    plan={'source_commit':'synthetic','artifact_root':str(tmp_path),'episodes':rows(),
        'n24_validation':{'seed_cohort':'c2','source_bridge':{},'dev_review':{'synthetic':True},'metadata_selection':{'protected_outcomes_read':False}}}
    planpath=tmp_path/'validation-plan.json';write(planpath,plan);monkeypatch.setattr(c,'VALIDATION_PLAN',planpath)
    monkeypatch.setattr(sup,'ROOT',tmp_path);monkeypatch.setattr(c,'RUN_DIR',tmp_path)
    ledger=[];reports={}
    def add(row,valid=True,success=False,retry=None):
        aid=str(len(ledger));group=events_for(row,aid,valid=valid,success=success,retry=retry);out=tmp_path/'attempts'/aid
        final=group[-1];final.update(output_dir=str(out));ledger.extend(group)
        reports[str(out)]=native_report(row['profile'])
        write(out/'eds_eval/eds_metrics.jsonl',[metric(row['profile'])],True)
        write(out/'eds_eval/episode_compute.jsonl',[{'policy_counters_available':True,'guided_chunks':1}],True)
        for file in ('attempt-result.json','eds_eval/in-worker-audit-receipt.json','eds_eval/decision-evidence-audit.json'):write(out/file,final if file=='attempt-result.json' else {})
        return final
    def accept(plan,row,events,*args):
        groups=list(r.event_groups([e for e in events if e['episode_key']==row['episode_key']]).values())
        c.require(bool(groups) and groups[-1][-1]['outcome_valid'] is True,'synthetic invalid')
        return groups[-1][-1]
    monkeypatch.setattr(c,'accepted_cell',accept);monkeypatch.setattr(c,'read_worker_report',lambda output,*a:reports[str(output)])
    monkeypatch.setattr(r,'read_events',lambda *a:ledger)
    monkeypatch.setattr(sup.dev_supervisor,'device_check',lambda:None)
    return SimpleNamespace(plan=plan,path=planpath,ledger=ledger,add=add,output=tmp_path/'validation-execution',reports=reports)


@pytest.mark.parametrize('case',['promote','reject','control_better','incomplete','invalid','recovered','failed_recovery','controller_fault','markers_deleted'])
def test_full_denominator_cost_and_aggregate_privacy(cohort,case):
    j=cohort
    for i,row in enumerate(j.plan['episodes'][:3 if case=='incomplete' else 60]):
        recovered=case in {'recovered','failed_recovery'} and i<2
        primary=j.add(row,valid=not recovered,success=row['profile']=='N24' and case not in {'reject','control_better'})
        if recovered:j.add(row,valid=case=='recovered',success=False,retry=primary['attempt_id'])
        if case=='control_better' and row['profile']=='C0':primary['success']=True
    if case=='invalid':j.ledger[2]['outcome_valid']=False
    if case=='markers_deleted':
        out=j.ledger[8]['output_dir'];j.reports[out].pop('n24_gripper_parent_rescue_audit')
        write(Path(out)/'eds_eval/eds_metrics.jsonl',[metric('N23')],True)
    detail,aggregate=reporting.summarize(j.plan,j.ledger,sup.ROOT,vars(r),force_invalid=case=='controller_fault',controller_completed=59 if case=='controller_fault' else None)
    assert aggregate['aggregate_only'] and not any(k in aggregate for k in ('cells','success_counts','attempts','task_id','seed_cohort'))
    assert detail['dispatched']==(3 if case=='incomplete' else 62 if case in {'recovered','failed_recovery'} else 60)
    assert sum(v['gpu_process_wall_seconds']['observed_total'] for v in detail['all_attempt_costs'].values())==detail['dispatched']
    assert sum(detail['all_attempt_denominators'].values())==detail['dispatched']
    if case in {'promote','recovered'}:
        assert aggregate['decision']=='PROMOTE' and detail['accepted_cells']==60
        assert detail['accepted_cell_denominators']==dict.fromkeys(c.ARMS,20)
        if case=='recovered':
            assert detail['recoveries']==2 and detail['unknown_token_calls']==2
    elif case in {'reject','control_better'}:
        assert aggregate['decision']=='REJECT' and detail['accepted_cells']==60
    elif case=='incomplete':assert aggregate['decision']=='INCOMPLETE' and detail['accepted_cells']==3
    else:assert aggregate['decision']=='INVALID' and not aggregate['outcome_valid']


@pytest.mark.parametrize('case',['all_failed','promoted','recover','failed_recovery','invalid_primary','status_after_terminal','postprocessing'])
def test_supervisor_60cells_no_futility_and_terminal_fault_retention(cohort,monkeypatch,case):
    j=cohort;calls=[];device=[]
    monkeypatch.setattr(sup.dev_supervisor,'device_check',lambda:device.append(1))
    def attempt(path,plan,row,eligibility=None):
        i=len(calls);calls.append((row['episode_key'],eligibility))
        invalid=case in {'recover','failed_recovery','invalid_primary'} and i==0 or case=='failed_recovery' and i==1
        final=j.add(row,valid=not invalid,success=case=='promoted' and row['profile']=='N24',retry='0' if eligibility else None)
        return final
    monkeypatch.setattr(sup,'one_attempt',attempt)
    def eligibility(*a):
        c.require(case!='invalid_primary','not typed');return {'synthetic':True}
    monkeypatch.setattr(recovery,'create_eligibility',eligibility)
    if case=='status_after_terminal':
        original=r.durable_json
        def durable(path,value):
            if value.get('accepted_cells')==1:raise OSError('synthetic status write failure')
            return original(path,value)
        monkeypatch.setattr(r,'durable_json',durable)
    if case=='postprocessing':monkeypatch.setattr(c,'accepted_cell',lambda *a:(_ for _ in ()).throw(ValueError('synthetic postprocessor failure')))
    profiles={'profiles':{a:{} for a in c.ARMS}}
    if case in {'all_failed','promoted','recover'}:
        result=sup.execute(j.path,j.plan,profiles,{},j.output)
        assert result['decision']==('PROMOTE' if case=='promoted' else 'REJECT')
        assert len(calls)==(61 if case=='recover' else 60) # no validation futility rule
    else:
        with pytest.raises((OSError,ValueError)):sup.execute(j.path,j.plan,profiles,{},j.output)
    detail=json.loads((j.output/'protected-detail-v1.json').read_text());aggregate=json.loads((j.output/'aggregate-disposition-v1.json').read_text())
    assert detail['dispatched']==len(calls)==len(device)
    assert sum(v['gpu_process_wall_seconds']['observed_total'] for v in detail['all_attempt_costs'].values())==len(calls)
    if case=='status_after_terminal':assert detail['accepted_cells']==1 and detail['controller_completed']==1 and aggregate['decision']=='INVALID'
    if case=='postprocessing':assert detail['accepted_cells']==0 and detail['attempts'][0]['terminal']['outcome_valid'] is True
    if case in {'failed_recovery','invalid_primary'}:assert aggregate['decision']=='INVALID' and not aggregate['outcome_valid']
    with pytest.raises(ValueError,match='cannot resume'):sup.execute(j.path,j.plan,profiles,{},j.output)


@pytest.mark.parametrize('fault',['none','duplicate','recovery','receipt','plan_sha','terminal_identity','markers','guided_bool'])
def test_real_terminal_schema_and_profile_gate(tmp_path,monkeypatch,fault):
    row=rows()[2];plan={'episodes':[row],'source_commit':'synthetic','profiles_sha256':'profiles',
        'runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory','artifact_root':str(tmp_path)}
    path=tmp_path/'plan.json';reference=write(path,plan);monkeypatch.setattr(c,'VALIDATION_PLAN',path)
    output=tmp_path/'output';receipt=write(output/'eds_eval/in-worker-audit-receipt.json',{})
    write(output/'n23-worker-context.json',{'plan':reference})
    group=events_for(row,'primary');final=group[-1]
    final.update(output_dir=str(output),source_commit='synthetic',plan_sha256=reference['sha256'],profile_manifest_sha256='profiles',
        runtime_manifest_sha256='runtime',runtime_inventory_sha256='inventory',physical_gpu=7,init_row_sha256=row['init_row_sha256'],n23_worker_receipt=receipt)
    if fault=='plan_sha':final['plan_sha256']='wrong'
    if fault=='terminal_identity':final['identity']['init_index']=1
    if fault=='guided_bool':final['guided_chunks']=True
    write(output/'attempt-result.json',final)
    if fault=='receipt':write(output/'eds_eval/in-worker-audit-receipt.json',{'changed':True})
    if fault in {'duplicate','recovery'}:group+=events_for(row,'duplicate',retry=final['attempt_id'] if fault=='recovery' else None)
    write(output/'eds_eval/eds_metrics.jsonl',[metric('N23' if fault=='markers' else 'N24')],True)
    write(output/'eds_eval/episode_compute.jsonl',[{'policy_counters_available':True,'guided_chunks':1}],True)
    monkeypatch.setattr(c,'read_worker_report',lambda *a:native_report('N23' if fault=='markers' else 'N24'))
    if fault=='none':assert recovery.accepted_cell(plan,row,group,tmp_path,vars(r))==final
    else:
        with pytest.raises((ValueError,r.GateError)):recovery.accepted_cell(plan,row,group,tmp_path,vars(r))

from test_qd_ed_n24_controller import worker_job
from scripts import qd_ed_n24_validation_evidence as evidence

@pytest.fixture
def validation_worker(worker_job,monkeypatch):
    import torch
    job=worker_job;job.row=copy.deepcopy(rows()[2]);job.plan.pop('n23_cohort')
    job.plan.update(frozen=True,n24_cohort=c.WORKER_MARKER,n24_validation={'schema':'n24-protected-validation-v1','cohort_id':c.COHORT,
        'limits':c.LIMITS,'source_bridge':{'synthetic':True},'source_review':{'review':True}},episodes=[job.row],
        phase_authorization={'dev':False,'validation':True,'formal':False})
    job.context.update(profile='N24',episode_key=job.row['episode_key'])
    job.context['plan']=write(Path(job.plan_ref['path']),job.plan);job.context_path=job.output/'n23-worker-context.json';write(job.context_path,job.context)
    monkeypatch.setattr(c,'VALIDATION_PLAN',Path(job.plan_ref['path']));monkeypatch.setattr(c,'original_plan',lambda:{})
    monkeypatch.setattr(c,'source_record',lambda *a:(job.context['source'],{'synthetic':True}))
    monkeypatch.setattr(c,'review_source',lambda *a:{'review':True});monkeypatch.setattr(c,'manifest',lambda *a:{})
    monkeypatch.setattr(r,'build_command',lambda *a:(job.command,job.output))
    assigned=w.assigned_cuda_identity
    def identity(binding):
        value=assigned(binding);value['identity_diagnostic']={'schema':'n23-public-cuda-identity-diagnostic-v1',
            'expected_physical_gpu':7,'expected_uuid':c.GPU7_UUID,'cuda_visible_devices':'7','visible_device_count':1,'current_device':0,
            'uuid_public_type':'builtins.str','serialized_raw_uuid':c.GPU7_UUID,'canonical_uuid':c.GPU7_UUID,'status':'matched'}
        return value
    monkeypatch.setattr(w,'assigned_cuda_identity',identity)
    def audit(episode,compute,*,arithmetic_backend):
        job.calls.append('audit');arithmetic_backend.native(torch.zeros(1,dtype=torch.bfloat16))
        return {**native_report(job.context['profile']),'n23_arithmetic_backend':arithmetic_backend.report()}
    monkeypatch.setattr(w.audit,'audit_episode',audit)
    write(job.output/'eds_eval/episode_compute.jsonl',[{'policy_counters_available':True,'guided_chunks':1}],True)
    write(job.output/'eds_eval/eds_metrics.jsonl',[metric('N24')],True)
    return job


@pytest.mark.parametrize('fault',['none','phase','mode_marker','row','limits','plan','source_bridge','source_review','argv'])
def test_validation_worker_explicit_route_and_same_process(validation_worker,monkeypatch,fault):
    job=validation_worker
    if fault=='phase':job.plan['phase_authorization']['dev']=True
    if fault=='mode_marker':job.plan['n24_cohort']={}
    if fault=='row':job.plan['episodes'][0]['split']='dev'
    if fault=='limits':job.plan['n24_validation']['limits']={}
    if fault=='source_bridge':job.plan['n24_validation']['source_bridge']={}
    if fault=='source_review':job.plan['n24_validation']['source_review']={}
    job.context['plan']=write(Path(job.plan_ref['path']),job.plan)
    if fault=='plan':monkeypatch.setattr(c,'VALIDATION_PLAN',job.root/'missing.json')
    if fault=='argv':job.context['main_argv'].append('altered=true')
    write(job.context_path,job.context)
    if fault=='none':
        assert w.run_worker(job.context_path,job.command[1:])==0
        assert job.calls==['identity','cuda','audit'];job.calls.clear()
        assert w.verify_receipt(job.context_path,job.process)['accepted'] and not job.calls
        receipt=json.loads((job.output/'eds_eval/in-worker-audit-receipt.json').read_text())
        assert receipt['n24_native_counts']['guided_decisions']==1 and receipt['n24_metrics']['present']
    else:
        with pytest.raises((ValueError,OSError)):w.run_worker(job.context_path,job.command[1:])
        assert not job.calls


@pytest.mark.parametrize('fault',['none','plan','argv','process','start','receipt','runtime','uuid','backend','audit','cost','metrics','marker','old_source'])
def test_historical_dev_receipt_remains_bound_to_original_source(validation_worker,monkeypatch,fault):
    job=validation_worker
    assert w.run_worker(job.context_path,job.command[1:])==0
    write(job.output/'process.json',job.process)
    final={'output_dir':str(job.output),'attempt_id':job.output.name,'n23_worker_receipt':c.ref(job.output/'eds_eval/in-worker-audit-receipt.json'),
        'process':copy.deepcopy(job.process),'gpu_process_wall_seconds':60.,'guided_chunks':1}
    # The historical checker consumes the recorded source without requiring current evaluation HEAD.
    monkeypatch.setattr(w,'verify_source',lambda *a:pytest.fail('historical receipt must not verify against current HEAD'))
    receipt_path=job.output/'eds_eval/in-worker-audit-receipt.json';receipt=json.loads(receipt_path.read_text())
    if fault=='plan':job.plan['changed']=True
    if fault=='argv':receipt['main_argv_sha256']='wrong'
    if fault=='process':final['process']['proc_start_ticks']='wrong'
    if fault=='start':write(job.output/'eds_eval/in-worker-audit-start.json',{})
    if fault=='receipt':receipt['accepted']=False
    if fault=='runtime':receipt['runtime']['sha256']='wrong'
    if fault=='uuid':receipt['worker_cuda']['identity_diagnostic']['visible_device_count']=2
    if fault=='backend':receipt['audit_backend']['kind']='cpu'
    if fault=='audit':receipt['audit_report']['sha256']='wrong'
    if fault=='cost':final['gpu_process_wall_seconds']=0.
    if fault=='metrics':write(job.output/'eds_eval/eds_metrics.jsonl',[metric('N24',1)],True)
    if fault=='marker':receipt['n24_native_counts']={}
    if fault=='old_source':job.plan['source_commit']='other_original_source'
    write(receipt_path,receipt);final['n23_worker_receipt']=c.ref(receipt_path)
    if fault=='none':assert evidence.historical_receipt(final,job.row,job.plan,c.ref(job.plan_ref['path']),vars(r))['accepted']
    else:
        with pytest.raises((ValueError,OSError)):evidence.historical_receipt(final,job.row,job.plan,c.ref(job.plan_ref['path']),vars(r))


@pytest.mark.parametrize('index',[0,1,3,24,59])
def test_validation_prefix_has_no_development_futility(index,monkeypatch):
    plan={'episodes':rows()};prior=[e for i,row in enumerate(rows()[:index]) for e in events_for(row,str(i))]
    checked=[];monkeypatch.setattr(c,'accepted_cell',lambda plan,row,*a:checked.append(row['episode_key']) or {'success':False})
    assert c.admission(plan,{},rows()[index],prior,[],r.ROOT,vars(r))['n24_validation_cohort_id']==c.COHORT
    assert len(checked)==index
    with pytest.raises(ValueError,match='prefix'):c.admission(plan,{},rows()[index],prior+events_for(rows()[-1],'future'),[],r.ROOT,vars(r))

@pytest.mark.parametrize('fault',['none','release','freshness','capacity','running','already_started'])
def test_release_rechecks_metadata_capacity_and_no_restart(tmp_path,monkeypatch,fault):
    from contextlib import nullcontext
    monkeypatch.setattr(c,'RUN_DIR',tmp_path);monkeypatch.setattr(sup,'ROOT',tmp_path)
    plan={'source_commit':'synthetic','episodes':rows(),'n24_validation':{'seed_cohort':'c2','dev_review':{},'source_review':{},'authority':{}}}
    path=tmp_path/'plan.json';write(path,plan);out=tmp_path/'validation-execution';release=tmp_path/'validation-execution-release-v1.json'
    value={'schema':'n24-validation-execution-release-v1','plan':c.ref(path),'source_commit':'synthetic','cohort_id':c.COHORT,
        'seed_cohort':'c2','episode_keys':[x['episode_key'] for x in rows()],'limits':c.LIMITS,'dev_review':{},'source_review':{},'authority':{},
        'physical_gpu':7,'uuid':c.GPU7_UUID,'validation_authorized':True,'formal_authorized':False}
    if fault=='release':value['episode_keys'].pop()
    write(release,value)
    monkeypatch.setattr(r,'locked',lambda *a,**k:nullcontext());monkeypatch.setattr(c,'original_plan',lambda:{})
    monkeypatch.setattr(identity,'metadata',lambda *a:(seeds(),[],[],[],{}))
    monkeypatch.setattr(identity,'first_unused',lambda *a,**k:'c3' if fault=='freshness' else 'c2')
    monkeypatch.setattr(r,'read_events',lambda *a:[]);monkeypatch.setattr(r,'read_state',lambda *a:{})
    monkeypatch.setattr(c,'full_capacity',lambda *a:c.require(fault not in {'capacity','running'},'synthetic full-capacity rejection'))
    monkeypatch.setattr(r,'check_budget',lambda *a,**k:None);monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(plan,{},{}))
    called=[];monkeypatch.setattr(sup,'execute',lambda *a:called.append(1) or {'aggregate_only':True})
    if fault=='already_started':write(out/'aggregate-progress-v1.json',{'phase':'started'})
    if fault=='none':assert sup.launch(path,release,out)=={'aggregate_only':True} and called==[1]
    else:
        with pytest.raises(ValueError):sup.launch(path,release,out)
        assert not called


@pytest.mark.parametrize('old_arm',['C0','Q0','N23','N24'])
def test_existing_worker_dev_routes_remain_unchanged(worker_job,monkeypatch,old_arm):
    import torch
    job=worker_job;job.plan.pop('n23_cohort');job.plan['n24_cohort']={'worker_audit':c.dev.WORKER_CONTRACT};job.plan['frozen']=True
    job.plan['episodes'][0].update(iteration=c.dev.COHORT,profile=old_arm);job.context['profile']=old_arm
    job.context['plan']=write(Path(job.plan_ref['path']),job.plan);write(job.context_path,job.context)
    write(job.output/'eds_eval/episode_compute.jsonl',[{'policy_counters_available':True,'guided_chunks':1}],True)
    write(job.output/'eds_eval/eds_metrics.jsonl',[metric(old_arm)],True)
    def audit(*a,arithmetic_backend):
        job.calls.append('audit')
        if old_arm in {'N23','N24'}:arithmetic_backend.native(torch.zeros(1,dtype=torch.bfloat16))
        return {**native_report(old_arm),'n23_arithmetic_backend':arithmetic_backend.report()}
    monkeypatch.setattr(w.audit,'audit_episode',audit)
    assert w.run_worker(job.context_path,job.command[1:])==0
    assert job.calls==['identity','cuda' if old_arm in {'N23','N24'} else 'cpu','audit']
    job.calls.clear();assert w.verify_receipt(job.context_path,job.process)['accepted'] and not job.calls

@pytest.mark.parametrize('fault',['none','different_variant','attempt_root','escape_link'])
def test_production_split_variant_and_attempt_roots(tmp_path,monkeypatch,fault):
    variant=tmp_path/'source-volume/variant';variant.mkdir(parents=True)
    artifacts=tmp_path/'artifact-volume/attempt-data';artifacts.mkdir(parents=True)
    monkeypatch.setattr(c,'RUN_DIR',variant);monkeypatch.setattr(sup,'ROOT',tmp_path/'worktree')
    plan={'source_commit':'synthetic','artifact_root':str(artifacts),'episodes':rows(),
        'n24_validation':{'seed_cohort':'c2','source_bridge':{},'dev_review':{},'metadata_selection':{}}}
    path=variant/'plan.json';write(path,plan);monkeypatch.setattr(c,'VALIDATION_PLAN',path)
    output=variant/'validation-execution'
    if fault=='different_variant':output=variant/'elsewhere'
    if fault=='attempt_root':output=artifacts/'validation-execution'
    if fault=='escape_link':output.symlink_to(artifacts/'escaped-controller',target_is_directory=True)
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(plan,{'profiles':{}},{}))
    monkeypatch.setattr(r,'read_events',lambda *a:[])
    monkeypatch.setattr(sup,'release_check',lambda *a:None)
    monkeypatch.setattr(sup.dev_supervisor,'device_check',lambda:None)
    monkeypatch.setattr(sup,'one_attempt',lambda *a,**k:(_ for _ in ()).throw(ValueError('synthetic before first attempt')))
    if fault=='none':
        with pytest.raises(ValueError,match='synthetic'):sup.launch(path,variant/'release.json',output)
        assert (output/'aggregate-disposition-v1.json').is_file()
        value=json.loads((output/'protected-detail-v1.json').read_text())
        assert value['dispatched']==0 and value['accepted_cells']==0 and value['decision']=='INVALID'
        assert list(artifacts.iterdir())==[]
    else:
        # Every public boundary enforces the same exact owned controller path.
        for call in (lambda:sup.launch(path,variant/'release.json',output),
                     lambda:sup.execute(path,plan,{'profiles':{}},{},output),
                     lambda:reporting.write_reports(plan,[],output,tmp_path,vars(r))):
            with pytest.raises((ValueError,r.GateError)):call()
        assert not (artifacts/'escaped-controller').exists()

@pytest.mark.parametrize('name',['execution/attempt.json','validation-execution/protected-detail-v1.json','validation-execution-release-v1.json',
    'plan.frozen.v1.gpu7.json','validation-plan.frozen.v1.gpu7.json','result-v1.json','root-review-v1.json',
    'adoption-v1/authority.json','validation-adoption-v1/authority.json','validation-source-review-v1.json'])
def test_guard_v3_sensitive_paths_deny_read_and_write_without_io(tmp_path,name):
    import ast
    # Execute only the guard callback in a synthetic namespace, never open a sensitive path.
    tree=ast.parse((Path(r.ROOT).parent/'n24_validation_cpu_guard_v3.py').read_text())
    node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='audit')
    namespace={'Path':Path,'os':os,'HERE':tmp_path/'variant','ROOT':tmp_path,'WORKTREES':(), 'STATIC':tmp_path/'static.json','BLOCKED':[]}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<synthetic-guard-callback>','exec'),namespace)
    for mode,flags in [('r',os.O_RDONLY),('w',os.O_WRONLY|os.O_CREAT),('a',os.O_WRONLY|os.O_APPEND)]:
        with pytest.raises(PermissionError):namespace['audit']('open',(str(namespace['HERE']/name),mode,flags))
    assert len(namespace['BLOCKED'])==3 and not namespace['HERE'].exists()
    # Drafts are in the distinct non-executable template directory, never execution-prefix exceptions.
    namespace['audit']('open',(str(namespace['HERE']/'validation-cpu-templates-v2/release.json'),'w',os.O_WRONLY|os.O_CREAT))
    assert len(namespace['BLOCKED'])==3
