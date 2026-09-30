"""Synthetic result-schema, whole-matrix and receipt/timeout regression."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_qd_ed_n23_validation import write,seeds,state,events_for,no_cuda
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as dev
from scripts import qd_ed_n23_v2_supervise as ds
from scripts import qd_ed_n23_validation_contract as c
from scripts import qd_ed_n23_validation_identity as identity
from scripts import qd_ed_n23_validation_evidence as evidence
from scripts import qd_ed_n23_validation_recovery as recovery
from scripts import qd_ed_n23_validation_supervise as sup
from scripts import qd_ed_n23_validation_report as reporting
from scripts import qd_ed_n23_validation_prepare as prepare


@pytest.mark.parametrize('arm',c.ARMS)
@pytest.mark.parametrize('fault',['none','agent','other_api','qpos','missing_receipt','whole_timeout','valid_failure'])
def test_validation_typed_timeout_leaf_on_real_runner_shapes_all_arms(tmp_path,monkeypatch,arm,fault):
    from test_qd_ed_n23_v2 import failing_case,native_report
    from scripts import qd_ed_n23_v2_recovery as original
    rr,row,profile,runtime,final,stages,compute=failing_case(tmp_path,monkeypatch)
    row.update(iteration=c.COHORT,split='validation',profile=arm,budget_bucket='validation',seed_block='validation_c2_b1')
    final.update(identity=rr.episode_identity(row),episode_key=row['episode_key'],physical_gpu=7,budget_bucket='validation',
        profile_manifest_sha256='p',runtime_manifest_sha256='r',runtime_inventory_sha256='i')
    plan={'episodes':[row],'source_commit':final['source_commit'],'artifact_root':str(tmp_path.parent),
        'profiles_sha256':'p','runtime_manifest_sha256':'r','runtime_inventory_sha256':'i'}
    plan_ref=write(tmp_path/'plan.json',plan);final['plan_sha256']=plan_ref['sha256']
    final['n23_worker_receipt']=write(tmp_path/'eds_eval/in-worker-audit-receipt.json',{'synthetic':'receipt'})
    write(tmp_path/'process.json',{'synthetic':'process'})
    write(tmp_path/'eds_eval/decision-evidence-audit.json',native_report(tmp_path))
    if fault=='agent':stages[1]['transport']['item_types']=['agent_message']
    if fault=='other_api':stages[1]['error']='codex_transport_failure'
    if fault=='qpos':
        write(tmp_path/'eds_eval/safety_events.jsonl',[{'event':'gripper_qpos_violation','count':1}],True)
    if fault=='missing_receipt':final.pop('n23_worker_receipt')
    if fault=='whole_timeout':final.update(event='timeout',compute_outcome='interrupted')
    if fault=='valid_failure':final.update(outcome_valid=True,success=False)
    write(tmp_path/'eds_eval/stage_events.jsonl',stages,True)
    write(tmp_path/'attempt-result.json',final)
    base={**final,'budget_bucket':'validation','retry_of':None}
    events=[{**base,'event':'reserved'},{**base,'event':'dispatched'},final]
    monkeypatch.setattr(c,'read_worker_report',lambda *args:native_report(tmp_path))
    if fault=='none':
        value=recovery.create_eligibility(plan_ref['path'],plan,row,final,profile,runtime,events,tmp_path,vars(rr))
        assert value['schema']=='n23-validation-typed-timeout-eligibility-v1'
        assert value['cohort_id']==c.COHORT and value['primary_outcome_valid'] is False
        assert value['diagnostic']['outcome_valid'] is False and value['diagnostic']['unknown_token_calls']==1
        assert value['diagnostic']['token_usage']['input_tokens'] is None
    else:
        with pytest.raises((ValueError,rr.GateError,KeyError)):recovery.create_eligibility(
            plan_ref['path'],plan,row,final,profile,runtime,events,tmp_path,vars(rr))


def historical_receipt_fixture(tmp_path,monkeypatch):
    from test_qd_ed_n23_uuid_native_repair import identity as cuda_identity
    row={'episode_key':'historical','profile':'C0'}
    source={'commit':c.DEV_COMMIT,'files':[],'sha256':w.canonical_sha([])}
    rt=write(tmp_path/'runtime.json',{'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID}})
    parent={'source_commit':c.DEV_COMMIT,'code_files':[],'worktree':str(tmp_path),
        'runtime_manifest_path':rt['path'],'runtime_manifest_sha256':rt['sha256']}
    planref=write(tmp_path/'historical-plan.json',parent);out=tmp_path/'a';command=[str(Path('/python')),str(tmp_path/'main.py'),'policy.type=rdt']
    context={'schema':'n23-metered-worker-context-v1','attempt_id':'a','episode_key':row['episode_key'],'profile':'C0',
        'output_dir':str(out),'worktree':str(tmp_path),'main_argv':command[1:],'plan':planref,'runtime':rt,'source':source}
    contextref=write(out/'n23-worker-context.json',context)
    process={'pid':123,'proc_start_ticks':'321','boot_id':'synthetic','attempt_id':'a'}
    write(out/'process.json',process)
    pid={k:process[k] for k in ('pid','proc_start_ticks','boot_id')}
    write(out/'eds_eval/in-worker-audit-start.json',{'schema':'n23-worker-start-v1','process':pid,'context':contextref})
    write(out/'eds_eval/episode_compute.jsonl',[],True)
    write(out/'eds_eval/decision_evidence/episode_000/status.json',{'synthetic':True})
    write(out/'eds_eval/decision_evidence/episode_000/events.jsonl',[],True)
    arithmetic={'kind':'cpu','logical_device':'cpu','dtype_coverage':[]}
    report={'accepted':True,'evidence_complete':True,'n23_arithmetic_backend':arithmetic}
    reportref=write(out/'eds_eval/decision-evidence-audit.json',report)
    receipt={'schema':'n23-in-worker-audit-receipt-v1','accepted':True,'main_exit_code':0,'context':contextref,
        'process':pid,'process_unchanged':True,**{k:context[k] for k in ('attempt_id','episode_key','profile','plan','runtime','source')},
        'main_argv_sha256':w.canonical_sha(command[1:]),'evidence':w.evidence_record(out),
        'worker_cuda':cuda_identity(),'audit_backend':arithmetic,'audit_report':reportref,'audit_seconds':.1,'worker_wall_seconds':.5}
    receiptref=write(out/'eds_eval/in-worker-audit-receipt.json',receipt)
    final={'attempt_id':'a','output_dir':str(out),'n23_worker_receipt':receiptref,'process':process,'gpu_process_wall_seconds':1.}
    api=dict(vars(r));api['build_command']=lambda *_:(command,out)
    monkeypatch.setattr(c,'manifest',lambda *_:{})
    return SimpleNamespace(row=row,parent=parent,planref=planref,receipt=receipt,final=final,out=out,api=api,report=report)


@pytest.mark.parametrize('fault',['none','current_source','native_hash','process','main_exit','argv','runtime','identity','wall','evidence'])
def test_historical_receipt_keeps_old_source_and_no_unmetered_cuda(tmp_path,monkeypatch,fault):
    x=historical_receipt_fixture(tmp_path,monkeypatch)
    if fault=='current_source':x.receipt['source']={**x.receipt['source'],'commit':'evaluation'}
    if fault=='native_hash':x.receipt['audit_report']['sha256']='bad'
    if fault=='process':x.receipt['process']['pid']=999
    if fault=='main_exit':x.receipt['main_exit_code']=1
    if fault=='argv':x.receipt['main_argv_sha256']='bad'
    if fault=='runtime':x.receipt['runtime']={}
    if fault=='identity':x.receipt['worker_cuda']['actual_uuid_type']='object'
    if fault=='wall':x.receipt['worker_wall_seconds']=2.
    if fault=='evidence':x.receipt['evidence']['sha256']='bad'
    x.final['n23_worker_receipt']=write(x.out/'eds_eval/in-worker-audit-receipt.json',x.receipt)
    if fault=='none':
        assert evidence.historical_receipt(x.final,x.row,x.parent,x.planref,x.api)==x.report
    else:
        with pytest.raises((ValueError,KeyError)):evidence.historical_receipt(x.final,x.row,x.parent,x.planref,x.api)


@pytest.mark.parametrize('fault',['none','missing','source','runtime','cohort','profile','main_override'])
def test_new_worker_validation_route_exact_context(tmp_path,monkeypatch,fault):
    from scripts import qd_ed_n23_validation_bridge as b
    row=identity.rows_for(seeds(),'c2')[0];runtime={'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID}}
    rt=write(tmp_path/'runtime.json',runtime);source={'commit':'eval','files':[],'sha256':w.canonical_sha([])}
    parent={'synthetic':'dev'};monkeypatch.setattr(c,'DEV_PLAN',tmp_path/'dev.json');write(c.DEV_PLAN,parent)
    monkeypatch.setattr(c,'VALIDATION_PLAN',tmp_path/'plan.json')
    command=['python',str(tmp_path/'main.py'),'exact=original'];out=tmp_path/'attempts/a'
    meta={'schema':'n23-protected-validation-v1','cohort_id':c.COHORT,'limits':c.LIMITS,'worker_audit':w.WORKER_CONTRACT,
        'source_bridge':{'strict':True},'source_review':{'review':'bound'}}
    plan={'worktree':str(tmp_path),'artifact_root':str(tmp_path),'runtime_manifest_path':rt['path'],
        'runtime_manifest_sha256':rt['sha256'],'episodes':[row],'n23_validation':meta,'source_commit':'eval','code_files':[],
        'phase_authorization':{'dev':False,'validation':True,'formal':False}}
    context={'schema':'n23-metered-worker-context-v1','attempt_id':'a','episode_key':row['episode_key'],'profile':'C0',
        'output_dir':str(out),'worktree':str(tmp_path),'main_argv':command[1:],'runtime':rt,'source':source,
        'plan':write(c.VALIDATION_PLAN,plan)}
    monkeypatch.setattr(w,'ROOT',tmp_path);monkeypatch.setattr(w,'verify_source',lambda root,value:w.require(value==source,'changed'))
    monkeypatch.setattr(c,'source_record',lambda *_:(source,{'strict':True}))
    monkeypatch.setattr(c,'review_source',lambda *_:{'review':'bound'});monkeypatch.setattr(c,'manifest',lambda *_:{})
    monkeypatch.setattr(r,'build_command',lambda *_:(command,out))
    if fault=='missing':context.pop('source')
    if fault=='source':context['source']={**source,'commit':'wrong'}
    if fault=='runtime':context['runtime']['sha256']='bad'
    if fault=='cohort':plan['n23_validation']['cohort_id']='OTHER';context['plan']=write(c.VALIDATION_PLAN,plan)
    if fault=='profile':context['profile']='N7'
    argv=list(command[1:])
    if fault=='main_override':argv.append('changed=true');context['main_argv']=argv
    if fault=='none':assert w.validate_context(context,argv)==(tmp_path,out,runtime)
    else:
        with pytest.raises((ValueError,KeyError)):w.validate_context(context,argv)


def promotion_fixture(tmp_path,monkeypatch):
    rows=[{**v,'iteration':dev.COHORT,'split':'dev','seed_block':'dev','budget_bucket':'baseline' if arm=='C0' else 'development',
        'profile':arm,'episode_key':f'dev{v["task_id"]}{arm}','timeout_seconds':1800} for v in seeds()['blocks']['dev'] for arm in dev.ARMS]
    parent={'source_commit':c.DEV_COMMIT,'episodes':rows,'frozen':True,'phase_authorization':{'dev':True,'validation':False,'formal':False},
        'n23_cohort':{'backend_proof':{'synthetic':True}}}
    for key,name in [('DEV_PLAN','plan.json'),('DEV_RESULT','result.json'),('DEV_REVIEW','review.json'),('DEV_READER','reader.py')]:
        monkeypatch.setattr(c,key,tmp_path/name)
    c.DEV_READER.write_text('# synthetic reader byte binding\n')
    write(c.DEV_PLAN,parent);monkeypatch.setattr(c,'DEV_PLAN_SHA',c.sha(c.DEV_PLAN));monkeypatch.setattr(c,'DEV_READER_SHA',c.sha(c.DEV_READER))
    monkeypatch.setattr(dev,'expected_rows',lambda:copy.deepcopy(rows))
    monkeypatch.setattr(evidence,'historical_backend',lambda *args:args[0])
    monkeypatch.setattr(evidence,'historical_receipt',lambda *args:{'accepted':True})
    totals={'N7':{'guided_decisions':10,'parent_rounds_verified':100},
        'N23':{'guided_decisions':10,'parent_rounds_verified':100,**{k:10 if k not in ('candidate_scores_verified','score_batches_verified') else 1760 if k=='candidate_scores_verified' else 110 for k in ds.NATIVE_FIELDS}}}
    def native(final,row,report):
        if row['profile'] not in totals:return {'guided_decisions':0,'parent_rounds_verified':0},{k:0 for k in ds.AUX_FIELDS}
        return {k:v//10 for k,v in totals[row['profile']].items()},{k:1 for k in ds.AUX_FIELDS}
    monkeypatch.setattr(ds,'native_counts',native)
    events=[];entries=[];outcomes=[];attempts=[]
    for i,row in enumerate(rows):
        group=events_for(row,aid=f'cell{i}',success=row['task_id']<5)
        final=group[-1];out=tmp_path/'attempts'/final['attempt_id']
        final.update(output_dir=str(out),source_commit=c.DEV_COMMIT,plan_sha256=c.sha(c.DEV_PLAN),provider_token_usage_complete=True)
        refs={k:write(out/name,final if k=='attempt_result' else {'synthetic':k}) for k,name in [
            ('audit','eds_eval/decision-evidence-audit.json'),('worker_context','n23-worker-context.json'),
            ('worker_receipt','eds_eval/in-worker-audit-receipt.json'),('attempt_result','attempt-result.json')]}
        events+=group;entries.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],
            'attempt_id':final['attempt_id'],'success':final['success'],**refs})
        outcomes.append({'task_id':row['task_id'],'profile':row['profile'],'success':final['success'],'attempt_id':final['attempt_id'],'recovered':False})
        attempts.append(ds.attempt_record(final,row))
    def chosen(plan,row,ev,root,api):
        return next(v for v in ev if v['event']=='valid' and v['episode_key']==row['episode_key'])
    monkeypatch.setattr(recovery,'historical_dev_cell',chosen)
    counts={a:5 for a in dev.ARMS}
    status={'schema':'n23-dev-supervisor-status-v2','status':'completed_all_forty_audited','cohort_id':dev.COHORT,
        'completed_keys':[v['episode_key'] for v in rows],'dev_gate_promoted':True,'successes':counts,'native':totals,
        'auxiliary':{k:20 for k in ds.AUX_FIELDS},'outcomes':outcomes,'attempts':attempts,**ds.summarize(outcomes,attempts)}
    physical=tmp_path/'physical';physical.mkdir();logical=tmp_path/'execution';logical.symlink_to(physical,target_is_directory=True)
    status_path=logical/'status.json';status_ref=write(status_path,status)
    result={'schema':'n23-dev-cohort-result-v2','cohort_id':dev.COHORT,'source_commit':c.DEV_COMMIT,
        'plan':c.ref(c.DEV_PLAN),'terminal_status':{'path':str(status_path),'sha256':status_ref['sha256'],'content':status},
        'planned':40,'dispatched':40,'audited_cells':40,'dev_gate_promoted':True,
        'decision':'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION','goal_status':'TARGET_NOT_MET','reader':c.ref(c.DEV_READER),
        'backend_proof':parent['n23_cohort']['backend_proof'],'ledger_snapshot':write(tmp_path/'snapshot.jsonl',events,True),
        'accepted_cells':entries,'attempts':attempts,'counts':{a:{'audited':10,'success':5} for a in dev.ARMS},
        'native':totals,'auxiliary':status['auxiliary'],**ds.summarize(outcomes,attempts)}
    review={'schema':'n23-dev-promotion-review-v1','disposition':'promoted','allow_validation':True,
        'dev_plan':c.ref(c.DEV_PLAN),'dev_status':status_ref,'dev_result':write(c.DEV_RESULT,result),'backend_proof':result['backend_proof']}
    write(c.DEV_REVIEW,review)
    api=dict(vars(r));api['read_events']=lambda p:events if str(p).endswith('attempt-ledger.jsonl') else r.read_events(p)
    return SimpleNamespace(parent=parent,status=status,result=result,review=review,events=events,api=api,status_path=status_path)


@pytest.mark.parametrize('fault',['none','partial','status','invalid','comparison','false_gate','wrong_source','reorder',
    'missing_native','result_status','missing_receipt','reader','snapshot','unreported_attempt','cost_unknown','backend'])
def test_real_writer_schema_promotion_and_logical_path_alias(tmp_path,monkeypatch,fault):
    x=promotion_fixture(tmp_path,monkeypatch)
    if fault=='partial':x.result['audited_cells']=39
    if fault=='status':x.status['status']='rejected_numeric_futility'
    if fault=='invalid':x.result['decision']='INVALID_OR_INTERRUPTED'
    if fault=='comparison':x.status['successes']['Q0']=6
    if fault=='false_gate':x.status['dev_gate_promoted']=False
    if fault=='wrong_source':x.result['source_commit']='other'
    if fault=='reorder':x.result['accepted_cells'].reverse()
    if fault=='missing_native':monkeypatch.setattr(ds,'native_counts',lambda *args:({'guided_decisions':0,'parent_rounds_verified':0},{k:0 for k in ds.AUX_FIELDS}))
    if fault=='result_status':x.result['terminal_status']['content']={}
    if fault=='missing_receipt':x.result['accepted_cells'][0].pop('worker_receipt')
    if fault=='reader':c.DEV_READER.write_text('changed')
    if fault=='snapshot':Path(x.result['ledger_snapshot']['path']).write_text('')
    if fault=='unreported_attempt':x.result['attempts']=x.result['attempts'][:-1]
    if fault=='cost_unknown':x.result['unknown_token_calls']=99
    if fault=='backend':x.result['backend_proof']={}
    x.review['dev_status']=write(x.status_path,x.status)
    x.result['terminal_status']['sha256']=x.review['dev_status']['sha256']
    x.review['dev_result']=write(c.DEV_RESULT,x.result);write(c.DEV_REVIEW,x.review)
    if fault=='none':
        assert x.result['terminal_status']['path']!=x.review['dev_status']['path']
        assert c.dev_promotion(tmp_path,x.api)==c.ref(c.DEV_REVIEW)
    else:
        with pytest.raises((ValueError,KeyError)):c.dev_promotion(tmp_path,x.api)


def report_fixture(tmp_path,monkeypatch,*,invalid_primary=False):
    rows=identity.rows_for(seeds(),'c2');events=[]
    plan={'source_commit':'eval','artifact_root':str(tmp_path),'episodes':rows,
        'n23_validation':{'seed_cohort':'c2','source_bridge':{},'backend_proof':{},'metadata_selection':{'protected_outcomes_read':False}}}
    monkeypatch.setattr(c,'VALIDATION_PLAN',tmp_path/'plan.json');write(c.VALIDATION_PLAN,plan)
    for i,row in enumerate(rows):
        if invalid_primary and i==0:
            events+=events_for(row,aid='invalid_primary',valid=False)
        group=events_for(row,aid=f'a{i}',success=(row['task_id']<5 if row['profile']=='N23' else row['task_id']<4),
            retry='invalid_primary' if invalid_primary and i==0 else None,bucket='recovery' if invalid_primary and i==0 else None)
        group[-1].update(output_dir=str(tmp_path/f'a{i}'),guided_chunks=1,provider_token_usage_complete=True)
        write(tmp_path/f'a{i}'/'eds_eval/decision-evidence-audit.json',{'accepted':True})
        events+=group
    def accepted(plan,row,ev,root,api):
        final=[v for v in ev if v.get('episode_key')==row['episode_key'] and v['event']=='valid'][-1]
        if not final.get('outcome_valid'):raise ValueError('invalid')
        return final
    monkeypatch.setattr(c,'accepted_cell',accepted);monkeypatch.setattr(c,'read_worker_report',lambda *_:{'accepted':True})
    return plan,events


@pytest.mark.parametrize('invalid_primary',[False,True])
def test_two_blocks_do_not_collapse_and_invalid_costs_unknown_tokens_retained(tmp_path,monkeypatch,invalid_primary):
    plan,events=report_fixture(tmp_path,monkeypatch,invalid_primary=invalid_primary)
    detail,aggregate=reporting.summarize(plan,events,tmp_path,vars(r))
    assert aggregate['decision']=='PROMOTE' and detail['accepted_cells']==60
    assert detail['accepted_cell_denominators']=={a:20 for a in c.ARMS}
    assert detail['matched_comparisons']['C0']=={'denominator':20,'gains':2,'losses':0}
    assert detail['all_attempt_denominators']['C0']==20+invalid_primary
    assert detail['unknown_token_calls']==int(invalid_primary)
    assert detail['all_attempt_token_usage_complete'] is not invalid_primary
    assert detail['all_attempt_costs']['C0']['gpu_process_wall_seconds']['observed_total']==20+invalid_primary
    assert not any(k in aggregate for k in ('success_counts','cells','attempts','seed_cohort','task_id','matched_comparisons'))


@pytest.mark.parametrize('fault',['partial','invalid','recovery_failed','lower_success','force_invalid'])
def test_no_validation_futility_and_full_only_promotion(tmp_path,monkeypatch,fault):
    plan,events=report_fixture(tmp_path,monkeypatch)
    if fault=='partial':events=events[:6]
    if fault=='invalid':events[-1]['outcome_valid']=False
    if fault=='recovery_failed':
        row=plan['episodes'][-1];events[-1]['outcome_valid']=False
        events+=events_for(row,aid='badretry',valid=False,retry='a59',bucket='recovery')
    if fault=='lower_success':
        for e in events:
            if e.get('identity',{}).get('profile')=='N23' and e['event']=='valid':e['success']=False
    detail,aggregate=reporting.summarize(plan,events,tmp_path,vars(r),force_invalid=fault=='force_invalid')
    assert not aggregate['gate_passed']
    assert aggregate['decision']==('INCOMPLETE' if fault=='partial' else 'REJECT' if fault=='lower_success' else 'INVALID')
    assert aggregate['outcome_valid'] is (fault=='lower_success')


@pytest.mark.parametrize('fault',['none','invalid_second','failed_recovery','busy'])
def test_serial_supervisor_calls_real_run_plan_interface_and_preserves_terminal_after_raise(tmp_path,monkeypatch,fault):
    plan,all_events=report_fixture(tmp_path,monkeypatch)
    out=tmp_path/'supervisor';seen=[];events=[]
    monkeypatch.setattr(sup,'ROOT',tmp_path);monkeypatch.setattr(c,'RUN_DIR',tmp_path)
    monkeypatch.setattr(sup.queue,'inventory',lambda:{7:{'uuid':c.GPU7_UUID}})
    monkeypatch.setattr(sup.queue,'reservation_admission',lambda *_:None)
    def gpu(**_):
        if fault=='busy':raise r.GateError('busy')
    monkeypatch.setattr(r,'gpu_admission',gpu)
    monkeypatch.setattr(r,'read_events',lambda path:events if 'attempt-ledger' in str(path) else [])
    def run(plan_path,**kw):
        assert kw['split']=='validation' and kw['iteration']==c.COHORT and len(kw['episode_keys'])==1
        row=next(v for v in plan['episodes'] if v['episode_key']==kw['episode_keys'][0])
        c.require_scope(plan,tmp_path,vars(r),row)
        eligibility=c._SCOPE['eligibility'];group=copy.deepcopy(all_events[3*plan['episodes'].index(row):3*(plan['episodes'].index(row)+1)])
        seen.append((row['episode_key'],eligibility))
        if fault in {'invalid_second','failed_recovery'} and len(seen)==2:
            group[-1]['outcome_valid']=False;events.extend(group);raise r.GateError('invalid after journal')
        if eligibility is not None:
            for v in group:v.update(attempt_id='recovery',retry_of='a1',budget_bucket='recovery')
            group[-1]['outcome_valid']=False
        events.extend(group);return [group[-1]]
    monkeypatch.setattr(r,'run_plan',run)
    def eligibility(*args,**kw):
        if fault=='invalid_second':raise ValueError('ineligible infrastructure')
        return {'synthetic':True}
    monkeypatch.setattr(recovery,'create_eligibility',eligibility)
    if fault=='none':
        result=sup.execute(c.VALIDATION_PLAN,plan,{'profiles':{a:{} for a in c.ARMS}}, {},out)
        assert result['gate_passed'] and len(seen)==60
        with pytest.raises(ValueError,match='cannot resume'):sup.execute(c.VALIDATION_PLAN,plan,{}, {},out)
    else:
        with pytest.raises((ValueError,r.GateError)):
            sup.execute(c.VALIDATION_PLAN,plan,{'profiles':{a:{} for a in c.ARMS}}, {},out)
        assert len(seen)=={'invalid_second':2,'failed_recovery':3,'busy':0}[fault]
        assert c.read(out/'aggregate-disposition.json')['decision']=='INVALID'
        assert not c.read(out/'aggregate-progress.json')['protected_outcomes_disclosed']



@pytest.mark.parametrize('fault',['none','source','runtime','process','wall','fp32','missing_batch','identity','old_authority'])
def test_historical_backend_preserves_real_source_without_current_head_check(tmp_path,monkeypatch,fault):
    from scripts import qd_ed_n23_v2_backend as b
    from scripts import qd_ed_n23_arithmetic_repair as repair
    from test_qd_ed_n23_uuid_native_repair import identity as cuda_identity
    source={'commit':c.DEV_COMMIT,'files':[],'sha256':w.canonical_sha([])}
    runtime=write(tmp_path/'runtime.json',{'gpu_mapping':{'uuid':c.GPU7_UUID}})
    protocol=write(tmp_path/'backend.md',{});observation=write(tmp_path/'observation.md',{})
    monkeypatch.setattr(dev,'BACKEND_PROTOCOL',Path(protocol['path']));monkeypatch.setattr(dev,'OBSERVABILITY',Path(observation['path']))
    predecessor={'fixture':'rootreview'};monkeypatch.setattr(dev,'predecessor_review',lambda:predecessor)
    meta={'schema':'n23-arithmetic-repair-binding-v3'}
    plan={'source':source,'runtime':runtime,'uuid_repair':meta,'protocol':protocol,'timeout_observability':observation,
        'predecessor_review':predecessor,'corpus':{'index':{'fixture':True}},'limits':b.LIMITS}
    planref=write(tmp_path/'backend-plan.json',plan)
    out=tmp_path/'attempts/fourth';process={'pid':12,'boot_id':'synthetic','proc_start_ticks':'99'}
    release={'schema':'n23-backend-preflight-release-v2','plan':planref,'source':source,'runtime':runtime,'limits':b.LIMITS,
        'attempt_id':'fourth','predecessor_review':predecessor,'retry_of':repair.FAILED_ATTEMPT}
    context={'schema':'n23-recovery-attempt-context-v2','attempt_id':'fourth','output_dir':str(out),'budget_bucket':'recovery',
        'plan':planref,'timeout_seconds':120,'cleanup_seconds':40,'retry_of':repair.FAILED_ATTEMPT}
    good={'accepted':True,'mismatches':[],'production_helper_passed':True,'independent_passed':True,'wrong_score_rejected':True}
    actual=cuda_identity();actual.update(kind='cuda',logical_device='cuda:0',torch_version='synthetic',cuda_version='synthetic',
        dtype_coverage=['torch.float32','torch.bfloat16'])
    report={'schema':'n23-backend-preflight-proof-v2','accepted':True,'task_outcome':False,'plan':planref,
        'source':source,'runtime':runtime,'limits':b.LIMITS,'attempt_id':'fourth','uuid_repair':meta,
        'retry_of':repair.FAILED_ATTEMPT,'process':process,'worker_wall_seconds':16.,'backend':actual,
        'release':write(out/'release.json',release),'attempt_context':write(out/'context.json',context),
        'batches':[{**good,'dtype':'torch.bfloat16','candidates':16} for _ in range(176)],
        'synthetic':[{**good,'dtype':dtype,'candidates':4} for dtype in ('torch.float32','torch.bfloat16')],
        'wrong_bounds_rejected':True,'errors':[]}
    write(out/b.artifact_name(plan,'start'),{'schema':'n23-backend-preflight-start-v2','process':process,'plan':planref,
        'attempt_id':'fourth','source':source})
    reportref=write(out/b.artifact_name(plan,'report'),report)
    reference={'attempt_id':'fourth','plan':planref,'report':reportref}
    parent={'source_commit':c.DEV_COMMIT,'code_files':[],'runtime_manifest_path':runtime['path'],
        'runtime_manifest_sha256':runtime['sha256'],'n23_cohort':{'backend_proof':reference}}
    terminal={'process':process,'backend_preflight_report':reportref,'gpu_process_wall_seconds':16.3}
    seen=[]
    def lineage(plan,reference,events,historical_source,api):
        seen.append(historical_source);return terminal
    monkeypatch.setattr(repair,'verify_lineage',lineage)
    monkeypatch.setattr(b,'verify_corpus_files',lambda *_:None)
    monkeypatch.setattr(b,'corpus_from_index',lambda _:plan['corpus'])
    monkeypatch.setattr(b,'validate_plan',lambda *_:(_ for _ in ()).throw(AssertionError('must not compare current HEAD to old source')))
    if fault=='source':report['source']={**source,'commit':'eval'}
    if fault=='runtime':report['runtime']={}
    if fault=='process':report['process']={'pid':999}
    if fault=='wall':terminal['gpu_process_wall_seconds']=15.
    if fault=='fp32':report['synthetic'][0]['accepted']=False
    if fault=='missing_batch':report['batches'].pop()
    if fault=='identity':report['backend']['actual_uuid_type']='arbitrary'
    if fault=='old_authority':report['uuid_repair']={'schema':'n23-uuid-repair-binding-v1'}
    newref=write(out/b.artifact_name(plan,'report'),report)
    reference['report']=newref;terminal['backend_preflight_report']=newref
    if fault=='none':
        assert evidence.historical_backend(reference,parent,[],vars(r))==reference
        assert seen==[source]
    else:
        with pytest.raises((ValueError,KeyError)):evidence.historical_backend(reference,parent,[],vars(r))


def validation_contract_fixture(tmp_path,monkeypatch):
    from scripts import qd_ed_n23_validation_prepare as p
    parent={'source_commit':c.DEV_COMMIT,'code_files':[],'worktree':str(tmp_path),'artifact_root':str(tmp_path/'artifacts'),
        'candidate_profiles':{'N23':{'path':str(tmp_path/'configs/qd_ed_final/candidate_n23.json'),'sha256':'n23'}},
        'n23_cohort':{'backend_proof':{'frozen':'backend'}},
        'profiles_path':str(tmp_path/'profiles.json'),'profiles_sha256':'profiles',
        'runtime_inventory_path':str(tmp_path/'inventory.json'),'runtime_inventory_sha256':'inventory',
        'seed_plan_path':str(tmp_path/'seeds.json'),'seed_plan_sha256':'seeds','shared_overrides':['original=true']}
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID},'synthetic':True}
    runtime_ref=write(tmp_path/'runtime.json',runtime)
    parent.update(runtime_manifest_path=runtime_ref['path'],runtime_manifest_sha256=runtime_ref['sha256'])
    source={'commit':'evaluation','files':[],'sha256':w.canonical_sha([])};source_bridge={'source':'strictbridge'}
    monkeypatch.setattr(c,'DEV_PLAN',tmp_path/'dev.json');write(c.DEV_PLAN,parent)
    monkeypatch.setattr(c,'VALIDATION_PLAN',tmp_path/'validation.json');monkeypatch.setattr(p,'ROOT',tmp_path)
    source_review={'synthetic':'source-review'};dev_review={'synthetic':'dev-review'}
    plan=p.build_plan(parent,seeds(),'c2',source=source,source_bridge=source_bridge,
        dev_review=dev_review,source_review=source_review,selection={'metadata':'only'})
    plan['frozen']=True;write(c.VALIDATION_PLAN,plan)
    st=state();st['n23_validation_authorization'].update(dev_review=dev_review,source_review=source_review)
    api=dict(vars(r));api['read_state']=lambda *_:st
    monkeypatch.setattr(c,'source_record',lambda *_:(source,source_bridge))
    monkeypatch.setattr(c,'dev_promotion',lambda *_:dev_review)
    monkeypatch.setattr(c,'review_source',lambda *_:source_review)
    monkeypatch.setattr(dev,'validate_runtime',lambda *_:None)
    # c1 has a consumed seed; no protected outcome appears in this fixture.
    snap=(seeds(),[{'pair':identity.pair(seeds()['blocks']['validation_c1_b1'][0])}],[],[],{})
    monkeypatch.setattr(identity,'metadata',lambda *_:snap)
    return plan,{ 'profiles':{a:{} for a in c.ARMS}},runtime,api,parent,st


@pytest.mark.parametrize('fault',['none','main_overrides','candidate','runtime','formal','rows','old_dev_meta','freshness','auth'])
def test_full_plan_is_exact_parent_plus_evaluation_fields(tmp_path,monkeypatch,fault):
    plan,profiles,runtime,api,parent,st=validation_contract_fixture(tmp_path,monkeypatch)
    if fault=='main_overrides':plan['shared_overrides']=['changed=true']
    if fault=='candidate':plan['candidate_profiles']['N23']['sha256']='different'
    if fault=='runtime':plan['runtime_manifest_sha256']='different'
    if fault=='formal':plan['phase_authorization']['formal']=True
    if fault=='rows':plan['episodes'][0]['env_seed']+=1
    if fault=='old_dev_meta':plan['n23_cohort']={}
    if fault=='freshness':monkeypatch.setattr(identity,'metadata',lambda *_:(seeds(),[],[],[],{}))
    if fault=='auth':st['n23_validation_authorization']['source_review']={}
    write(c.VALIDATION_PLAN,plan)
    if fault=='none':c.validate_contract(plan,profiles,runtime,seeds(),tmp_path,api)
    else:
        with pytest.raises((ValueError,r.GateError)):c.validate_contract(plan,profiles,runtime,seeds(),tmp_path,api)


@pytest.mark.parametrize('fault',['none','missing','scope','hash','stale_cohort','missing_auth'])
def test_root_release_rechecks_freshness_capacity_and_does_not_dispatch(tmp_path,monkeypatch,fault):
    plan,profiles,runtime,api,parent,st=validation_contract_fixture(tmp_path,monkeypatch)
    (tmp_path/'data').mkdir();monkeypatch.setattr(sup,'ROOT',tmp_path)
    release={'schema':'n23-validation-execution-release-v1','plan':c.ref(c.VALIDATION_PLAN),
        'source_commit':plan['source_commit'],'cohort_id':c.COHORT,'seed_cohort':'c2',
        'episode_keys':[v['episode_key'] for v in plan['episodes']],'limits':c.LIMITS,
        'dev_review':plan['n23_validation']['dev_review'],'source_review':plan['n23_validation']['source_review'],
        'backend_proof':plan['n23_validation']['backend_proof'],'physical_gpu':7,'uuid':c.GPU7_UUID,
        'validation_authorized':True,'formal_authorized':False}
    if fault=='scope':release['formal_authorized']=True
    if fault=='hash':release['plan']['sha256']='changed'
    if fault=='stale_cohort':monkeypatch.setattr(identity,'metadata',lambda *_:(seeds(),[],[],[],{}))
    if fault=='missing_auth':st.pop('n23_validation_authorization')
    path=tmp_path/'release.json'
    if fault!='missing':write(path,release)
    monkeypatch.setattr(r,'read_state',lambda *_:st)
    reservation=[{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':{'validation':32.,'formal':12.},
        'rationale':'fixture','time_unix':1.}]
    monkeypatch.setattr(r,'read_events',lambda path:reservation if 'reservation' in str(path) else [])
    if fault=='none':sup.release_check(path,c.VALIDATION_PLAN,plan)
    else:
        with pytest.raises((ValueError,r.GateError,FileNotFoundError)):sup.release_check(path,c.VALIDATION_PLAN,plan)
    assert not (tmp_path/'data/attempt-ledger.jsonl').exists()
