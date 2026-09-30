"""Protected validation control flow uses synthetic metadata/results only."""
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n22_validation_contract as c
from scripts import qd_ed_n22_validation_prepare as prep
from scripts import qd_ed_n22_validation_report as reporting
from scripts import qd_ed_n22_validation_supervise as sup


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return c.ref(path)


def seeds():
    blocks={}
    for index,name in enumerate(['dev','formal']+[f'validation_c{a}_b{b}' for a in range(1,5) for b in (1,2)]):
        blocks[name]=[{'task_id':t,'env_seed':1000*index+t,'policy_seed':10000+1000*index+t,
            'init_index':0,'init_row_sha256':f'{t:064x}','init_file_sha256':'a'*64,'bddl_sha256':'b'*64} for t in range(10)]
    return {'backend_task_order':list(range(10)),'blocks':blocks}


def state():
    dev=runner.n22_support()
    return {'gpu_pool':[7],'max_concurrent_gpu_workers':1,
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':438,'max_gpu_hours':100.,'amendment':runner.GPU7_N22_AMENDMENT,
            'reserved':dict(runner.N22_BUCKETS),'dispatched':0,'running':0,'gpu_hours_consumed':0.,
            'gpu_hour_reservations':{'validation':32.,'formal':12.}},
        'n22_gpu7_binding':{'scope':dev.COHORT+'_only','selected_gpu':7,'user_reply':dev.AUTONOMOUS_REPLY,
            'addendum_path':str(dev.GPU7_ADDENDUM),'addendum_sha256':dev.sha(dev.GPU7_ADDENDUM)},
        'n22_validation_authorization':{'schema':'n22-validation-authorization-v1','cohort_id':c.COHORT,
            'seed_cohort':'c2','protocol_sha256':c.PROTOCOL_SHA,'dev_review':{'synthetic':1},
            'source_review':{'synthetic':2},'run_once':True,'physical_gpu':7}}


def reservation():return [{'event':'gpu_hour_reservations_changed','gpu_hour_reservations':{'validation':32.,'formal':12.},'rationale':'fixture','time_unix':1.}]


def dispatch(task,seed,*,iteration='OLD',arm='Q0',event='dispatched',aid='old'):
    return {'event':event,'attempt_id':aid,'pair':(task,seed),'iteration':iteration,'profile':arm,'split':'validation'}


def test_first_unused_checks_all_dispatches_registry_and_all_four_cohorts():
    s=seeds();p=c.pair(s['blocks']['validation_c1_b1'][0]);d=[dispatch(*p)]
    with pytest.raises(ValueError,match='reconciliation'):c.first_unused(s,[],[],d)
    assert c.first_unused(s,[],[{'pair':p}],d)=='c2'
    hist=[{'pair':c.pair(s['blocks'][f'validation_c{a}_b1'][0])} for a in (1,2,3)]
    assert c.first_unused(s,hist,[],[])=='c4'
    hist.append({'pair':c.pair(s['blocks']['validation_c4_b2'][8])})
    with pytest.raises(ValueError,match='no untouched'):c.first_unused(s,hist,[],[])


@pytest.mark.parametrize('fault',['task_order','duplicate_task','duplicate_seed','policy_seed','dev_overlap','formal_overlap'])
def test_identity_integrity_and_non_outcome_based_choice(fault):
    s=seeds()
    if fault=='task_order':s['backend_task_order'].reverse()
    if fault=='duplicate_task':s['blocks']['validation_c1_b1'][1]['task_id']=0
    if fault=='duplicate_seed':s['blocks']['validation_c1_b2'][0]['env_seed']=s['blocks']['validation_c1_b1'][0]['env_seed']
    if fault=='policy_seed':s['blocks']['validation_c1_b2'][0]['policy_seed']=None
    if fault=='dev_overlap':s['blocks']['validation_c1_b1'][0]['env_seed']=s['blocks']['dev'][0]['env_seed']
    if fault=='formal_overlap':s['blocks']['validation_c1_b1'][0]['env_seed']=s['blocks']['formal'][0]['env_seed']
    if fault.endswith('overlap'):assert c.first_unused(s,[],[],[])=='c2'
    else:
        with pytest.raises(ValueError):c.first_unused(s,[],[],[])


def test_current_owned_exposure_is_excluded_but_foreign_or_second_n22_is_closed():
    s=seeds();p=c.pair(s['blocks']['validation_c1_b1'][0]);own=dispatch(*p,iteration=c.COHORT,arm='N22',aid='own')
    registry=[{'pair':p,'cohort_id':c.COHORT,'attempt_id':'own'}]
    with pytest.raises(ValueError):c.first_unused(s,[],registry,[own])
    assert c.first_unused(s,[],registry,[own],allow_own=True)=='c1'
    assert c.first_unused(s,[],registry+[{'pair':p}], [own],allow_own=True)=='c2'
    with pytest.raises(ValueError,match='one cohort'):c.first_unused(s,[],registry,[own,dispatch(1,1,arm='N22')],allow_own=True)


def test_metadata_projects_identity_without_retaining_outcomes(tmp_path,monkeypatch):
    s=seeds();seed=dump(tmp_path/'seeds.json',s);d=tmp_path/'data';d.mkdir()
    hist=d/'historical-exposure-inventory.jsonl';hist.write_text(json.dumps({'task_id':1,'episode_seed':1,'success':'DO_NOT_RETAIN'})+'\n')
    monkeypatch.setattr(c,'HISTORY_SHA',c.sha(hist))
    (d/'exposure-registry.jsonl').write_text(json.dumps({'task_id':1,'episode_seed':1,'success':False})+'\n')
    (d/'attempt-ledger.jsonl').write_text('\n'.join(json.dumps(v) for v in [
        {'event':'dispatched','attempt_id':'old','identity':{'split':'validation','task_id':1,'env_seed':1,'profile':'Q0','iteration':'OLD'},'success':'SECRET'},
        {'event':'valid','attempt_id':'old','success':'SECRET'}])+'\n')
    out=c.metadata(tmp_path,{'seed_plan_path':seed['path'],'seed_plan_sha256':seed['sha256']})
    assert 'SECRET' not in json.dumps(out) and 'DO_NOT_RETAIN' not in json.dumps(out)
    assert out[-1]['protected_outcomes_read'] is False and c.first_unused(*out[:4])=='c1'


def test_matrix_has_exact_60_ordered_original_cells_and_separate_routing():
    s=seeds();rows=c.rows_for(s,'c2')
    assert [(v['seed_block'],v['task_id'],v['profile']) for v in rows]==[(f'validation_c2_b{b}',t,a) for b in (1,2) for t in range(10) for a in c.ARMS]
    assert all(v['split']==v['budget_bucket']=='validation' and v['timeout_seconds']==1800 and 'retry_of' not in v for v in rows)
    p={'n22_validation':{},'candidate_profiles':{'N22':{}}}
    assert runner.is_n22_validation_plan(p) and not runner.is_n22_plan(p) and not runner.is_n21_plan(p)
    assert runner.is_n22_plan({'candidate_profiles':{'N22':{},'N21':{}}})


@pytest.mark.parametrize('fault',['none','missing_auth','gpu','budget','validation_cap','formal_reserve','wrong_iteration','formal_scope','old_gpu3','hold'])
def test_separate_validation_budget_gate(fault):
    s=state();row=c.rows_for(seeds(),'c2')[0]
    if fault=='missing_auth':s.pop('n22_validation_authorization')
    if fault=='gpu':s['gpu_pool']=[3]
    if fault=='budget':s['budget']['max_episode_attempts']=478
    if fault=='validation_cap':s['budget']['reserved']['validation']=181
    if fault=='formal_reserve':s['budget']['gpu_hour_reservations']['formal']=11.
    if fault=='wrong_iteration':row['iteration']='N22_VALIDATION_OTHER'
    if fault=='formal_scope':row['split']=row['budget_bucket']='formal'
    if fault=='old_gpu3':s['budget']['amendment']=runner.GPU3_AMENDMENT
    if fault=='hold':s['external_resource_hold']={'do_not_auto_resume':True}
    if fault=='none':assert runner.check_budget(s,[],row,reservation_events=reservation())==1800
    else:
        with pytest.raises((ValueError,runner.GateError)):runner.check_budget(s,[],row,reservation_events=reservation())


def test_full_matrix_32_hours_and_formal_reserve_admission():
    row=c.rows_for(seeds(),'c2')[0];plan={'episodes':c.rows_for(seeds(),'c2')};r=dict(vars(runner));s=state()
    snap=runner.budget_snapshot([]);snap['gpu_hours_consumed']=56.
    r['budget_snapshot']=lambda *_:copy.deepcopy(snap)
    c.protected_budget(s,[],[],row,1800,r,plan=plan)
    snap['gpu_hours_consumed']=56.001
    with pytest.raises(ValueError,match='entire local'):c.protected_budget(s,[],[],row,1800,r,plan=plan)
    snap['gpu_hours_consumed']=0.;snap['by_bucket']['validation']=121
    with pytest.raises(ValueError,match='full matrix'):c.protected_budget(s,[],[],row,1800,r,plan=plan)
    snap['by_bucket']['validation']=0;snap['dispatched']=339
    with pytest.raises(ValueError,match='full matrix'):c.protected_budget(s,[],[],row,1800,r,plan=plan)
    with pytest.raises(ValueError):c.protected_budget(s,[],[],row,1799,r,plan=plan)


def test_no_retry_prefix_and_checkpoint_required(tmp_path,monkeypatch):
    plan=plan_fixture(tmp_path,monkeypatch);rows=plan['episodes']
    events=[charged_result(tmp_path,plan,rows[0],0)]
    assert c.admission(plan,{},rows[1],events,[],tmp_path,vars(runner))['n22_validation_cohort_id']==c.COHORT
    with pytest.raises(ValueError,match='no retry'):c.admission(plan,{},rows[0],events,[],tmp_path,vars(runner))
    with pytest.raises(ValueError,match='invalid predecessor'):c.admission(plan,{},rows[2],events,[],tmp_path,vars(runner))
    events[0]['outcome_valid']=False
    with pytest.raises(ValueError):c.admission(plan,{},rows[1],events,[],tmp_path,vars(runner))


def test_journaled_dispatch_registers_identity_without_outcomes(tmp_path):
    import yaml
    (tmp_path/'data').mkdir();(tmp_path/'research-state.yaml').write_text(yaml.safe_dump(state()))
    row=c.rows_for(seeds(),'c2')[0]
    base={'attempt_id':'one','identity':runner.episode_identity(row),'episode_key':row['episode_key'],'budget_bucket':'validation',
        'n22_validation_seed_block':row['seed_block'],'init_row_sha256':row['init_row_sha256'],'success':'DO_NOT_COPY'}
    for event in ('reserved','dispatched'):runner.append_event(tmp_path,{**base,'event':event,'time_unix':1.})
    text=(tmp_path/'data/exposure-registry.jsonl').read_text();v=json.loads(text)
    assert 'success' not in text and 'DO_NOT_COPY' not in text and v['episode_seed']==row['env_seed']
    assert v['outcomes_read'] is False and runner.budget_snapshot(runner.read_events(tmp_path/'data/attempt-ledger.jsonl'))['dispatched']==1


def native(n=1):
    return {'accepted':True,'evidence_complete':True,
        **({'n22_hold_lift_quality_audit':{'score_batches_verified':11*n,'candidate_scores_verified':176*n},
        'n5_grasp_timing_audit':{'checked_decisions':n,'parent_rounds_verified':10*n}} if n else {})}


def plan_fixture(tmp_path,monkeypatch):
    (tmp_path/'data').mkdir(exist_ok=True)
    p={'episodes':c.rows_for(seeds(),'c2'),'source_commit':'test','profiles_sha256':'profiles',
       'runtime_manifest_sha256':'runtime','runtime_inventory_sha256':'inventory','artifact_root':str(tmp_path),
       'n22_validation':{'seed_cohort':'c2'}}
    path=tmp_path/'frozen.json';dump(path,p);monkeypatch.setattr(c,'VALIDATION_PLAN',path)
    return p


def charged_result(tmp_path,plan,row,index,success=True,n=1):
    # Mirrors qd_ed_final_runner.run_plan's actual base dictionary, not invented top-level seed fields.
    out=tmp_path/f'attempt-{index}';out.mkdir(exist_ok=True)
    value={'attempt_id':f'attempt-{index}','identity':runner.episode_identity(row),'episode_key':row['episode_key'],
        'budget_bucket':row['budget_bucket'],'plan_sha256':c.sha(c.VALIDATION_PLAN),
        'profile_manifest_sha256':plan['profiles_sha256'],'runtime_manifest_sha256':plan['runtime_manifest_sha256'],
        'runtime_inventory_sha256':plan['runtime_inventory_sha256'],'source_commit':plan['source_commit'],
        'init_row_sha256':row['init_row_sha256'],'retry_of':None,'output_dir':str(out),'physical_gpu':7,
        'event':'valid','outcome_valid':True,'success':success,'required_cost_telemetry_complete':True,
        **{k:0 for k in reporting.COST_FIELDS},'guided_chunks':n,'candidate_evaluations':176*n,'score_batches':11*n,
        'gpu_process_wall_seconds':100.}
    report=dump(out/'eds_eval/decision-evidence-audit.json',native(n) if row['profile']=='N22' else {'accepted':True,'evidence_complete':True})
    checkpoint={'schema':'n22-validation-cell-audit-v1','accepted':True,
        **{k:row[k] for k in ('episode_key','profile',*c.FIELDS)},'seed_block':row.get('seed_block'),
        **{k:value[k] for k in ('attempt_id','source_commit','plan_sha256','success','guided_chunks')},'native_report':report}
    dump(out/'eds_eval/n22-validation-cell-audit.json',checkpoint)
    return value


def test_real_terminal_shape_complete_matrix_and_protected_aggregate(tmp_path,monkeypatch):
    p=plan_fixture(tmp_path,monkeypatch);events=[charged_result(tmp_path,p,row,i) for i,row in enumerate(p['episodes'])]
    detail,aggregate=reporting.summarize(p,events)
    assert detail['decision']=='PROMOTE' and detail['accepted_cells']==60
    assert detail['costs']['N22']['candidate_evaluations']==3520
    assert set(aggregate)=={'schema','cohort_id','aggregate_only','terminal','gate_passed','outcome_valid','dev_promoted'}
    assert aggregate['gate_passed'] and aggregate['outcome_valid']
    assert all(k not in events[0] for k in ('init_index','init_file_sha256','bddl_sha256'))
    reporting.write_reports(p,events,tmp_path/'reports')
    assert len(c.read(tmp_path/'reports/protected-detail.json')['cells'])==60
    c.admission(p,{},p['episodes'][-1],events[:-1],[],tmp_path,vars(runner))


@pytest.mark.parametrize('fault',['below10','inferior','no_guidance','missing_cost','aborted','incomplete','duplicate','checkpoint_seed','terminal_seed','plan','runtime','profile','native_hash'])
def test_report_reject_invalid_and_corruptions(tmp_path,monkeypatch,fault):
    p=plan_fixture(tmp_path,monkeypatch);events=[charged_result(tmp_path,p,row,i) for i,row in enumerate(p['episodes'])]
    if fault in {'below10','inferior','no_guidance'}:
        for i,row in enumerate(p['episodes']):
            events[i]=charged_result(tmp_path,p,row,i,success=(i//3<9 if fault=='below10' and row['profile']=='N22'
                else i//3<10 if fault=='inferior' and row['profile']=='N22' else True),n=0 if fault=='no_guidance' else 1)
    if fault=='missing_cost':events[0].pop('provider_cached_input_tokens')
    if fault=='aborted':events[0].update(event='aborted',outcome_valid=False)
    if fault=='incomplete':events.pop()
    if fault=='duplicate':events.append(dict(events[0],attempt_id='other'))
    if fault=='terminal_seed':events[0]['identity']['policy_seed']=-1
    if fault in {'plan','runtime','profile'}:
        events[0][{'plan':'plan_sha256','runtime':'runtime_manifest_sha256','profile':'profile_manifest_sha256'}[fault]]='changed'
    path=Path(events[0]['output_dir'])/'eds_eval/n22-validation-cell-audit.json'
    if fault=='checkpoint_seed':v=c.read(path);v['policy_seed']=-1;dump(path,v)
    if fault=='native_hash':dump(Path(events[0]['output_dir'])/'eds_eval/decision-evidence-audit.json',{'accepted':False})
    if fault in {'duplicate','checkpoint_seed','terminal_seed','plan','runtime','profile','native_hash'}:
        with pytest.raises(ValueError):reporting.summarize(p,events)
    else:
        detail,aggregate=reporting.summarize(p,events)
        assert not aggregate['gate_passed']
        assert detail['decision']==('REJECT' if fault in {'below10','inferior','no_guidance'} else 'INCOMPLETE' if fault=='incomplete' else 'INVALID')
        assert aggregate['outcome_valid']==(fault in {'below10','inferior','no_guidance'})


@pytest.mark.parametrize('arm,n,fault', [('N22',1,None),('N22',0,None),('Q0',1,None),('C0',1,None),
 ('N22',1,'gate'),('N22',1,'compute'),('N22',1,'qd'),('N22',1,'cost'),('Q0',1,'compute'),('C0',1,'qd'),('N22',1,'invalid')])
def test_audit_result_preserves_native_compute_and_unguided(tmp_path,monkeypatch,arm,n,fault):
    p=plan_fixture(tmp_path,monkeypatch);row=next(v for v in p['episodes'] if v['profile']==arm)
    value=charged_result(tmp_path,p,row,0,n=n);report=native(n) if arm=='N22' else {'accepted':True,'evidence_complete':True}
    metrics=[{'qd_quality_mode':'close_hold_then_lift_v1','qd_archive_active_for_chunk':True,'qd_archive_enabled':False,
        'score_call_count':11,'search_evaluation_count':176,'resample_count':10,'renoise_count':10,'rollout_count':10} for _ in range(n)]
    if fault=='gate':report.pop('n22_hold_lift_quality_audit')
    if fault=='compute':metrics[0]['score_call_count']=12
    if fault=='qd':metrics[0].update(qd_archive_active_for_chunk=False,qd_archive_enabled=True)
    if fault=='cost':value['required_cost_telemetry_complete']=False
    if fault=='invalid':value['outcome_valid']=False
    monkeypatch.setattr(sup.audit,'audit_episode',lambda *_:report)
    monkeypatch.setattr(runner,'read_events',lambda *_:metrics)
    if fault:
        with pytest.raises(ValueError):sup.audit_result(value,row)
    else:
        checkpoint=sup.audit_result(value,row)
        assert c.verify_checkpoint(checkpoint,value,row,p,vars(runner))['accepted']


def dev_fixture(tmp_path,monkeypatch):
    parent={'episodes':[], 'source_commit':c.DEV_COMMIT,'profiles_sha256':'p','runtime_manifest_sha256':'r','runtime_inventory_sha256':'i'}
    for t in range(10):
        for arm in ('C0','Q0','N21','N22'):
            parent['episodes'].append({**seeds()['blocks']['dev'][t],'iteration':c.DEV_COHORT,'profile':arm,
                'split':'dev','budget_bucket':'baseline' if arm=='C0' else 'development','episode_key':f'd{t}_{arm}'})
    paths={k:tmp_path/name for k,name in [('DEV_PLAN','dev-plan.json'),('DEV_RESULT','result.json'),('DEV_REVIEW','review.json'),('DEV_READER','reader.py')]}
    for key,path in paths.items():monkeypatch.setattr(c,key,path)
    paths['DEV_READER'].write_text('# synthetic reader bytes; output schema follows actual summarize_cohort_cpu_v1.py\n')
    dump(c.DEV_PLAN,parent);monkeypatch.setattr(c,'DEV_PLAN_SHA',c.sha(c.DEV_PLAN))
    monkeypatch.setattr(c,'DEV_STATUS',tmp_path/'status.json');monkeypatch.setattr(c,'VALIDATION_PLAN',c.DEV_PLAN)
    events=[];audits=[];result_rows=[]
    for i,row in enumerate(parent['episodes']):
        final=charged_result(tmp_path,parent,row,i)
        events.extend([dict(final,event='dispatched'),final]);ar=c.ref(Path(final['output_dir'])/'eds_eval/decision-evidence-audit.json')
        audits.append({'attempt_id':final['attempt_id'],'report':ar})
        result_rows.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'arm':row['profile'],
            'attempt_id':final['attempt_id'],'event':'valid','outcome_valid':True,'success':True,'native_valid':True,'audit':ar})
    status={'status':'completed_all_forty_audited','dev_gate_promoted':True,'completed_keys':[x['episode_key'] for x in parent['episodes']],
        'successes':{a:10 for a in ('C0','Q0','N21','N22')},'native':{'N22':{'guided_decisions':10,'parent_rounds_verified':100}}}
    sr=dump(tmp_path/'status.json',status)
    result={'schema':'n22-dev-cohort-result-v1','cohort_id':c.DEV_COHORT,'source_commit':c.DEV_COMMIT,'plan':c.ref(c.DEV_PLAN),
        'terminal_status':{**sr,'content':status},'decision':'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION','dev_gate_promoted':True,
        'dispatched':40,'audited_cells':40,'planned':40,'cost_missing_fields':[],'reader_sha256':c.sha(c.DEV_READER),
        'rows':result_rows,'counts':{a:{'audited':10,'success':10} for a in status['successes']}}
    review={'schema':'n22-dev-promotion-review-v1','disposition':'promoted','allow_validation':True,'dev_plan':c.ref(c.DEV_PLAN),
        'dev_status':sr,'dev_result':dump(c.DEV_RESULT,result),'cell_audits':audits}
    dump(c.DEV_REVIEW,review);r=dict(vars(runner));r['read_events']=lambda *_:events
    return parent,status,result,review,events,r


@pytest.mark.parametrize('fault',[None,'partial','unpromoted','invalid','missing_gate','canonical','result_status','result_source','result_counts','result_decision','audit_hash','final_identity'])
def test_dev_gate_uses_actual_complete_result_status_native_cells(tmp_path,monkeypatch,fault):
    parent,status,result,review,events,r=dev_fixture(tmp_path,monkeypatch)
    if fault=='partial':status['completed_keys'].pop()
    if fault=='unpromoted':status['dev_gate_promoted']=False
    if fault=='invalid':events[-1]['outcome_valid']=False
    if fault=='missing_gate':
        ar=review['cell_audits'][-1];v=c.read(ar['report']['path']);v.pop('n22_hold_lift_quality_audit')
        ar['report']=dump(Path(ar['report']['path']),v);result['rows'][-1]['audit']=ar['report']
    if fault=='canonical':events[-1]['candidate_evaluations']-=1
    if fault=='result_status':result['terminal_status']['content']={'status':'failed'}
    if fault=='result_source':result['source_commit']='other'
    if fault=='result_counts':result['counts']['N22']['success']=9
    if fault=='result_decision':result['decision']='REJECT'
    if fault=='audit_hash':review['cell_audits'][-1]['report']['sha256']='bad'
    if fault=='final_identity':events[-1]['identity']['policy_seed']=-1
    if fault in {'partial','unpromoted'}:review['dev_status']=dump(tmp_path/'status.json',status);result['terminal_status']={**review['dev_status'],'content':status}
    review['dev_result']=dump(c.DEV_RESULT,result);dump(c.DEV_REVIEW,review)
    if fault:
        with pytest.raises(ValueError):c.dev_promotion(tmp_path,r)
    else:assert c.dev_promotion(tmp_path,r)==c.ref(c.DEV_REVIEW)


@pytest.mark.parametrize('fault',[None,'science','provider','extra_file','uncommitted','protocol'])
def test_source_record_preserves_scientific_bytes_and_closes_manifest(tmp_path,monkeypatch,fault):
    def git(*args):return subprocess.check_output(['git',*args],cwd=tmp_path,text=True).strip()
    git('init','-q');git('config','user.name','CPU fixture');git('config','user.email','cpu@example.invalid')
    originals=['main.py','core/policy.py','provider.py','scripts/qd_ed_final_runner.py']
    for name in originals:path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('# frozen\n')
    git('add','.');git('commit','-qm','frozen');base=git('rev-parse','HEAD');monkeypatch.setattr(c,'DEV_COMMIT',base)
    parent={'source_commit':base,'code_files':[{'path':n,'sha256':c.sha(tmp_path/n)} for n in originals]}
    for name in c.ADDITIONS:path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('# evaluation only\n')
    protocol=tmp_path/'experiments/iteration_022_hold_lift/protocol-validation-conditional-v1.md';monkeypatch.setattr(c,'PROTOCOL_SHA',c.sha(protocol))
    (tmp_path/'scripts/qd_ed_final_runner.py').write_text('# isolated routing\n')
    if fault=='science':(tmp_path/'core/policy.py').write_text('# changed\n')
    if fault=='provider':(tmp_path/'provider.py').write_text('# changed\n')
    if fault=='extra_file':(tmp_path/'extra.py').write_text('# extra\n')
    if fault=='protocol':protocol.write_text('# wrong protocol\n')
    git('add','.');git('commit','-qm','evaluation')
    if fault=='uncommitted':(tmp_path/'main.py').write_text('# dirty\n')
    if fault:
        with pytest.raises((ValueError,subprocess.CalledProcessError)):c.source_record(tmp_path,parent)
    else:
        value=c.source_record(tmp_path,parent)
        assert value['scientific_unchanged'] and value['files']==sorted(value['files'],key=lambda v:v['path'])
        assert set(value['changed_paths'])==c.ADDITIONS|c.ALLOWED_MODIFIED


def contract_fixture(tmp_path,monkeypatch):
    p=plan_fixture(tmp_path,monkeypatch)
    runtime={'gpu_mapping':{'uuid':c.GPU7_UUID,'egl_device_index':4},'cuda_egl_verified':True,
        'cuda_egl_probe':{'resource_id':c.GPU7_PROOF},'frozen_stage_provider':{'backend':'codex_cli'},
        'stage_recovered_error_condition':runner.E2_STAGE_CONDITION}
    runtime_path=tmp_path/'runtime.json';rr=dump(runtime_path,runtime)
    source={'commit':'test','files':[]};parent={**p,'runtime_manifest_path':str(runtime_path),'runtime_manifest_sha256':rr['sha256'],
        'seed_plan_sha256':'seeds','candidate_profiles':{'N22':{'sha256':'candidate'}}}
    devpath=tmp_path/'dev-plan.json';dump(devpath,parent);monkeypatch.setattr(c,'DEV_PLAN',devpath)
    monkeypatch.setattr(c,'source_record',lambda *_:source)
    monkeypatch.setattr(c,'dev_promotion',lambda *_:{'synthetic':1})
    monkeypatch.setattr(c,'review_source',lambda *_:{'synthetic':2})
    snapshot=(seeds(),[{'pair':c.pair(seeds()['blocks']['validation_c1_b1'][0])}],[],[],{'fixture':True})
    monkeypatch.setattr(c,'metadata',lambda *_:snapshot)
    p=prep.build_plan(parent,seeds(),'c2',source=source,dev_review={'synthetic':1},source_review={'synthetic':2})
    p['frozen']=True;dump(c.VALIDATION_PLAN,p)
    r=dict(vars(runner));r['read_state']=lambda *_:state();r['runtime_gpu']=lambda *_:7
    return p,{'profiles':{a:{} for a in c.ARMS}},runtime,r


@pytest.mark.parametrize('fault',[None,'no_dev_review','source','matrix','arm','phase','candidate','runtime','poe','egl','probe','cohort','authorization'])
def test_contract_closes_source_profile_runtime_and_phase(tmp_path,monkeypatch,fault):
    p,m,rt,r=contract_fixture(tmp_path,monkeypatch)
    if fault=='no_dev_review':p['n22_validation']['dev_review']=None
    if fault=='source':p['source_commit']='other'
    if fault=='matrix':p['episodes'].reverse()
    if fault=='arm':p['candidate_profiles']['N7']={}
    if fault=='phase':p['phase_authorization']['formal']=True
    if fault=='candidate':p['candidate_profiles']['N22']['sha256']='wrong'
    if fault=='runtime':p['runtime_manifest_sha256']='changed'
    if fault=='poe':rt['frozen_stage_provider']['backend']='poe'
    if fault=='egl':rt['gpu_mapping']['egl_device_index']=0
    if fault=='probe':rt['cuda_egl_probe']['resource_id']='different'
    if fault=='cohort':monkeypatch.setattr(c,'metadata',lambda *_:(seeds(),[],[],[],{}))
    if fault=='authorization':st=state();st['n22_validation_authorization']['dev_review']={};r['read_state']=lambda *_:st
    dump(c.VALIDATION_PLAN,p)
    if fault:
        with pytest.raises((ValueError,runner.GateError)):c.validate_contract(p,m,rt,seeds(),tmp_path,r)
    else:c.validate_contract(p,m,rt,seeds(),tmp_path,r)


def test_external_source_review_exact_and_preview_never_executable(tmp_path,monkeypatch):
    p,m,rt,r=contract_fixture(tmp_path,monkeypatch);parent=c.read(c.DEV_PLAN);source={'commit':'test','files':[]}
    # Restore real function because contract_fixture isolates the higher-level entry gate.
    import importlib.util
    spec=importlib.util.spec_from_file_location('isolated_review_module',c.__file__);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    monkeypatch.setattr(mod,'DEV_PLAN',c.DEV_PLAN);monkeypatch.setattr(mod,'SOURCE_REVIEW',tmp_path/'source-review.json')
    exact={'schema':'n22-validation-source-review-v1','disposition':'accepted','dev_plan':c.ref(c.DEV_PLAN),
        'protocol':c.ref(c.PROTOCOL),'source':source,'allowed_modified':sorted(c.ALLOWED_MODIFIED),'allowed_added':sorted(c.ADDITIONS),
        'runtime':{'path':parent['runtime_manifest_path'],'sha256':parent['runtime_manifest_sha256']},'no_execution_release':True}
    dump(mod.SOURCE_REVIEW,exact);assert mod.review_source(source,parent)==c.ref(mod.SOURCE_REVIEW)
    exact['source']['commit']='other';dump(mod.SOURCE_REVIEW,exact)
    with pytest.raises(ValueError):mod.review_source({'commit':'test','files':[]},parent)
    draft=prep.build_plan(parent,seeds(),'c2',source={'commit':'test','files':[]})
    assert draft['frozen'] is False and draft['n22_validation']['dev_review'] is None
    assert not draft['phase_authorization']['formal']


@pytest.mark.parametrize('fault',[None,'missing','stale_cohort','wrong_hash','scope'])
def test_release_rechecks_metadata_and_separate_exact_authority(tmp_path,monkeypatch,fault):
    p,m,rt,r=contract_fixture(tmp_path,monkeypatch);monkeypatch.setattr(sup,'ROOT',tmp_path)
    release={'schema':'n22-validation-execution-release-v1','plan':c.ref(c.VALIDATION_PLAN),'source_commit':p['source_commit'],
        'cohort_id':c.COHORT,'seed_cohort':'c2','episode_keys':[x['episode_key'] for x in p['episodes']],
        'dev_review':p['n22_validation']['dev_review'],'source_review':p['n22_validation']['source_review'],
        'physical_gpu':7,'uuid':c.GPU7_UUID,'validation_authorized':True,'formal_authorized':False}
    path=tmp_path/'release.json'
    if fault=='wrong_hash':release['plan']['sha256']='wrong'
    if fault=='scope':release['formal_authorized']=True
    if fault=='stale_cohort':monkeypatch.setattr(c,'metadata',lambda *_:(seeds(),[],[],[],{}))
    if fault!='missing':dump(path,release)
    monkeypatch.setattr(runner,'read_state',lambda *_:state())
    monkeypatch.setattr(runner,'read_events',lambda path:reservation() if 'reservation' in str(path) else [])
    if fault:
        with pytest.raises((ValueError,FileNotFoundError)):sup.release_check(path,c.VALIDATION_PLAN,p)
    else:sup.release_check(path,c.VALIDATION_PLAN,p)


@pytest.mark.parametrize('fault',[None,'invalid_second','missing_native_second','busy','wrong_probe'])
def test_supervisor_mocked_real_event_shapes_full_matrix_or_immediate_stop(tmp_path,monkeypatch,fault):
    p=plan_fixture(tmp_path,monkeypatch);p['candidate_profiles']={'N22':{}};rt={'gpu_mapping':{'uuid':c.GPU7_UUID}}
    output=tmp_path/'supervisor';seen=[];events=[]
    monkeypatch.setattr(sup,'ROOT',tmp_path)
    monkeypatch.setattr(sys,'argv',['supervise','--plan',str(c.VALIDATION_PLAN),'--release',str(tmp_path/'release.json'),'--output-dir',str(output)])
    monkeypatch.setattr(runner,'validate_plan',lambda *a,**kw:(p,{},rt))
    monkeypatch.setattr(sup,'release_check',lambda *a:None)
    monkeypatch.setattr(sup.queue,'inventory',lambda:{7:{'uuid':c.GPU7_UUID}})
    monkeypatch.setattr(sup.queue,'reservation_admission',lambda *_:None)
    def gpu(**_):
        if fault=='busy':raise runner.GateError('synthetic busy')
    monkeypatch.setattr(runner,'gpu_admission',gpu)
    monkeypatch.setattr(sup.queue,'current_metadata',lambda *a,**kw:rt['gpu_mapping'])
    monkeypatch.setattr(sup.queue,'same_mapping',lambda *a:True)
    monkeypatch.setattr(sup.queue,'find_probe',lambda *a,**kw:None if fault=='wrong_probe' else {'resource_id':c.GPU7_PROOF})
    def run(*a,**kw):
        assert kw['split']=='validation' and kw['iteration']==c.COHORT and len(kw['episode_keys'])==1
        row=p['episodes'][len(seen)];assert kw['episode_keys']==[row['episode_key']]
        c.require_scope(p,tmp_path,vars(runner),row)
        value=charged_result(tmp_path,p,row,len(seen));seen.append(row['episode_key'])
        if fault=='invalid_second' and len(seen)==2:value.update(event='aborted',outcome_valid=False)
        events.extend([dict(value,event='dispatched'),value]);return [value]
    monkeypatch.setattr(runner,'run_plan',run)
    def audit_ep(path,*_):
        if fault=='missing_native_second' and len(seen)==2:return {'accepted':False}
        return native() if p['episodes'][len(seen)-1]['profile']=='N22' else {'accepted':True,'evidence_complete':True}
    monkeypatch.setattr(sup.audit,'audit_episode',audit_ep)
    metric={'qd_quality_mode':'close_hold_then_lift_v1','qd_archive_active_for_chunk':True,'qd_archive_enabled':False,
        'score_call_count':11,'search_evaluation_count':176,'resample_count':10,'renoise_count':10,'rollout_count':10}
    monkeypatch.setattr(runner,'read_events',lambda path:events if 'attempt-ledger' in str(path) else [metric] if 'eds_metrics' in str(path) else [])
    if fault:
        with pytest.raises((ValueError,runner.GateError)):sup.main()
        assert len(seen)==(2 if fault.endswith('second') else 0)
        assert c.read(output/'aggregate-disposition.json')['outcome_valid'] is False
        assert c.read(output/'aggregate-progress.json')['phase']=='invalid_or_interrupted'
    else:
        sup.main();assert len(seen)==60 and c.read(output/'aggregate-disposition.json')['gate_passed']
        assert c.read(output/'aggregate-progress.json')['completed_count']==60
        with pytest.raises(ValueError,match='cannot resume'):sup.main()


def test_dev_result_writer_logical_status_path_equals_canonical_symlink_reference(tmp_path,monkeypatch):
    parent,status,result,review,events,r=dev_fixture(tmp_path,monkeypatch)
    physical=tmp_path/'physical-execution';physical.mkdir()
    logical=tmp_path/'execution';logical.symlink_to(physical,target_is_directory=True)
    status_path=logical/'supervisor-status-gpu7-v1.json';monkeypatch.setattr(c,'DEV_STATUS',status_path)
    review['dev_status']=dump(status_path,status)  # Contract reference is canonical/physical.
    result['terminal_status']={'path':str(status_path),'sha256':c.sha(status_path),'content':status}  # Existing writer preserves logical path.
    review['dev_result']=dump(c.DEV_RESULT,result);dump(c.DEV_REVIEW,review)
    assert result['terminal_status']['path']!=review['dev_status']['path']
    assert c.dev_promotion(tmp_path,r)==c.ref(c.DEV_REVIEW)
    result['terminal_status']['sha256']='wrong';review['dev_result']=dump(c.DEV_RESULT,result);dump(c.DEV_REVIEW,review)
    with pytest.raises(ValueError,match='terminal result'):c.dev_promotion(tmp_path,r)
