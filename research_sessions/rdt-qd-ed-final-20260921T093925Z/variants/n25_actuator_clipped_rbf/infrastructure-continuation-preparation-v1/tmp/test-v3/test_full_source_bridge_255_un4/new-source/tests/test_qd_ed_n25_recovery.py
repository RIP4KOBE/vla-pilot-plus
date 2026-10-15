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
from scripts import qd_ed_n25_contract as c
from scripts import qd_ed_n25_recovery as recovery
from test_qd_ed_n25_controller import rows,write,state,triplet

from n25_cpu_synthetic import old_builders,install_classifier
old=old_builders()

@pytest.fixture(autouse=True)
def synthetic_classifier(monkeypatch):
    install_classifier(monkeypatch)



@pytest.mark.parametrize('fault',['none','agent','completed','other_error','missing_events','extra_failure','native',
    'valid','recovery','interrupted','wall_timeout','qpos','config','counter_missing','scoring_postgate','source','receipt','safety_presence','absent_metrics','absent_then_present','absent_terminal_unknown','absent_native_nonzero','absent_compute_nonzero'])
def test_actual_classifier_and_new_eligibility_envelope(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(old.c,'OBSERVABILITY',r.ROOT/'experiments/iteration_023_actuator_clipped_quality/timeout-observability-addendum-v2.md')
    output=tmp_path/'output';output.mkdir()
    rr,row,profile,runtime,final,stage,compute=old.failing_case(output,monkeypatch)
    row.update(iteration=c.COHORT,episode_key='n25_timeout_fixture');final.update(identity=rr.episode_identity(row),episode_key=row['episode_key'])
    manifest=write(tmp_path/'profiles.json',{'profiles':{'C0':profile}});rt=write(tmp_path/'runtime.json',runtime)
    for k in ('PROTOCOL','OBSERVABILITY'):
        p=tmp_path/k;p.write_text(k);monkeypatch.setattr(c,k,p)
    plan={'episodes':[row],'source_commit':'synthetic','profiles_path':manifest['path'],'profiles_sha256':manifest['sha256'],
        'candidate_profiles':{},'runtime_manifest_path':rt['path'],'runtime_manifest_sha256':rt['sha256'],
        'runtime_inventory_sha256':'inventory','artifact_root':str(tmp_path),'worktree':str(tmp_path)}
    planref=write(tmp_path/'plan.json',plan);receipt=write(output/'eds_eval/in-worker-audit-receipt.json',{})
    report=old.native_report(output);report['observed_counts']={'decision_context':1}
    final.update(plan_sha256=planref['sha256'],profile_manifest_sha256=manifest['sha256'],runtime_manifest_sha256=rt['sha256'],
        runtime_inventory_sha256='inventory',physical_gpu=7,n23_worker_receipt=receipt,budget_bucket='baseline')
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
    original_reader=recovery.classifier().evidence_files
    record=recovery.create_eligibility(planref['path'],plan,row,final,profile,runtime,journal,tmp_path,vars(rr))
    assert recovery.classifier().evidence_files is original_reader
    assert record['evidence_packaging_reader']==c.ref(recovery.__file__)
    assert record['diagnostic']['diagnostic_reader']==c.ref(recovery.classifier().__file__)
    if fault.startswith('absent'):assert record['evidence_packaging_mode']=='n25_absent_zero_guided_private_reader' and record['evidence_files']['metrics']['present'] is False
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
            assert actual==dict(row,budget_bucket='recovery',retry_of=final['attempt_id'],n25_recovery_eligibility=reference)
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
        'candidate_profiles':{'N23':{},'N25':{}},'n25_cohort':{'schema':'n25-gripper-parent-rescue-dev-v1'},'episodes':[row],
        'phase_authorization':{'dev':True,'validation':False,'formal':False},'profiles_sha256':'p',
        'runtime_manifest_sha256':'r','runtime_manifest_path':'synthetic','runtime_inventory_sha256':'i'}
    path=tmp_path/'plan.json';write(path,plan)
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID,'egl_device_index':4},'environment':{}}
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(plan,{'profiles':{arm:{}}},runtime))
    monkeypatch.setattr(c,'require_state',lambda *a:None);monkeypatch.setattr(c,'budget_authority',lambda:{'caps':c.BASE_CAPS});monkeypatch.setattr(c,'protected_budget',lambda *a,**k:None)
    monkeypatch.setattr(c,'admission',lambda *a,**k:{'n25_cohort_id':c.COHORT})
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
        if scenario=='valid':r.run_plan(path,split='dev',iteration=c.COHORT,root=tmp_path)
        else:
            with pytest.raises(r.GateError):r.run_plan(path,split='dev',iteration=c.COHORT,root=tmp_path)
    primary=r.read_events(tmp_path/'data/attempt-ledger.jsonl')[-1]
    if scenario in {'typed_recovery','failed_recovery'}:
        assert primary['n23_worker_receipt'] and primary['process']['pid']==os.getpid()
        record={'primary_attempt_id':primary['attempt_id'],'plan':c.ref(path)};ref=write(tmp_path/'eligibility.json',record)
        monkeypatch.setattr(recovery,'verify_eligibility',lambda *a:record)
        with c.supervised_scope(plan,tmp_path,row['episode_key'],eligibility=ref):
            if scenario=='typed_recovery':r.run_plan(path,split='dev',iteration=c.COHORT,root=tmp_path)
            else:
                with pytest.raises(r.GateError):r.run_plan(path,split='dev',iteration=c.COHORT,root=tmp_path)
        assert selected[1]==dict(row,budget_bucket='recovery',retry_of=primary['attempt_id'],n25_recovery_eligibility=ref)
    events=r.read_events(tmp_path/'data/attempt-ledger.jsonl');snap=r.budget_snapshot(events)
    expected=2 if 'recovery' in scenario else 1
    assert snap['dispatched']==expected and snap['running']==0 and len(launched)==len(providers)==len(cleaned)==expected
    assert snap['by_bucket'][row['budget_bucket']]==1 and snap['by_bucket']['recovery']==expected-1
    assert all(e['identity']==r.episode_identity(row) for e in events)
    assert events[-1]['outcome_valid'] is (scenario in {'valid','typed_recovery'}) and events[-1]['n25_episode_dispatched']
