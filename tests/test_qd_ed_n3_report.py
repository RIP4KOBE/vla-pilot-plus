"""New-cohort reporting uses synthetic public JSON only, never episode bundles."""
import copy
import sys
from pathlib import Path

import pytest
from test_qd_ed_n3_plan import r,n,load,ROOT,fixture,events,native_audit

sys.path.insert(0,str(ROOT/'scripts'))
d=load('n3_report_tests',ROOT/'scripts/qd_ed_n3_report.py')


def report_plan(plan):
    plan=copy.deepcopy(plan)
    plan['n3_cohort']['protocol']['sha256']=d.sha(d.PROTOCOL)
    return plan


def simple_attempt(plan,runtime,row,identifier,*,success=False,valid=True):
    terminal={'attempt_id':identifier,'episode_key':row['episode_key'],'identity':r.episode_identity(row),
        'n3_episode_dispatched':True,'physical_gpu':3,'event':'valid','outcome_valid':valid,'success':success,'task_failure':not success,
        'budget_bucket':row['budget_bucket'],'retry_of':row.get('retry_of'), 'time_unix':float(len(identifier)),
        'gpu_process_wall_seconds':13.,'n3_cohort_id':n.COHORT,'n3_frozen_identity':n.binding(plan,runtime),
        'source_commit':plan['source_commit'],'profile_manifest_sha256':plan['profiles_sha256'],
        'runtime_manifest_sha256':plan['runtime_manifest_sha256'],'runtime_inventory_sha256':plan['runtime_inventory_sha256'],
        'init_row_sha256':row['init_row_sha256'],'plan_sha256':'base-sha','output_dir':str(Path(plan['artifact_root'])/identifier)}
    metrics={'finite_executed_actions':True,'observer_wall_s':1.,'observer_bytes_written':100,'qd_active_chunks':1,
        'n3':{'records':[]}}
    return {'terminal':terminal,'status':'complete_valid' if valid else 'terminal_invalid','metrics':metrics}


def test_matched_complete_numeric_threshold_paired_no_authorization(fixture):
    _,original,_,runtime,*_=fixture;plan=report_plan(original)
    attempts=[]
    for i,row in enumerate(plan['episodes']):
        # N3 5/10, C0 4/10, Q0 5/10, all cells incl valid failures retained.
        successes={'C0':{0,1,2,3},'Q0':{1,2,3,4,5},'N3':{0,1,2,3,4}}
        attempts.append(simple_attempt(plan,runtime,row,str(i),success=row['task_id'] in successes[row['profile']]))
    result=d.summarize(plan,attempts)
    assert result['matrix']=='complete_valid_30' and result['protocol_numeric_dev_criterion'] is True
    assert result['phase_authorized'] is False
    assert result['paired_comparisons']['N3_vs_Q0']['gained_tasks']==[0]
    assert result['paired_comparisons']['N3_vs_Q0']['lost_tasks']==[5]
    assert result['profiles']['N3']['complete_valid']==10
    partial=d.summarize(plan,attempts[:-1])
    assert partial['matrix']=='incomplete' and partial['protocol_numeric_dev_criterion'] is None
    assert partial['profiles']['N3']['success_rate'] is None


def test_immutable_base_plus_recovery_revision_preserves_both_terminals_and_costs(fixture):
    _,original,_,runtime,*_=fixture;base=report_plan(original);saved=copy.deepcopy(base)
    row=base['episodes'][0];first=simple_attempt(base,runtime,row,'original',valid=False)
    first['terminal'].update(event='aborted',reason='external GPU3 process appeared during owned attempt',retryable_infrastructure=True,time_unix=1.)
    revised=copy.deepcopy(base)
    retry={**row,'episode_key':row['episode_key']+'_r1','retry_of':'original','budget_bucket':'recovery',
        'n3_recovery_contract':n.binding(base,runtime)}
    revised['episodes'].append(retry)
    second=simple_attempt(revised,runtime,retry,'recovered')
    second['terminal'].update(plan_sha256='revision-sha',time_unix=2.)
    d.validate_terminal(first['terminal'],base,'base-sha');d.validate_terminal(second['terminal'],revised,'revision-sha')
    result=d.summarize(base,[first,second]);cell=result['cells'][0]
    assert len(cell['attempts'])==2 and cell['valid_attempt_id']=='recovered'
    assert result['profiles']['C0']['all_attempt_gpu_seconds']['complete_total']==26
    assert base==saved
    second['terminal']['n3_frozen_identity']={**second['terminal']['n3_frozen_identity'],'source_commit':'changed'}
    with pytest.raises(ValueError,match='bindings differ|recovery linkage'):
        d.summarize(base,[first,second])


def test_invalid_terminal_never_opens_scientific_or_audit_payload(fixture,monkeypatch):
    _,original,_,runtime,*_=fixture;plan=report_plan(original)
    attempt=simple_attempt(plan,runtime,plan['episodes'][0],'bad',valid=False)
    terminal=attempt['terminal'];called=[]
    spec={'terminal':{'path':str(Path(terminal['output_dir'])/'attempt-result.json'),'sha256':'terminal-sha'}}
    def read(reference,**kwargs):
        assert reference==spec['terminal'];called.append(reference);return terminal
    monkeypatch.setattr(d,'read_ref',read)
    result=d.load_attempt(spec,{'base-sha':plan})
    assert result['status']=='terminal_invalid' and len(called)==1
    with pytest.raises(ValueError,match='terminal only'):
        d.load_attempt({**spec,'metrics':{'path':'forbidden','sha256':'x'}},{'base-sha':plan})


def test_unknown_Xid_or_valid_failure_is_not_replacement_eligible(fixture):
    _,original,_,runtime,*_=fixture;plan=report_plan(original);row=plan['episodes'][0]
    prior=simple_attempt(plan,runtime,row,'old',valid=False)
    prior['terminal'].update(event='aborted',reason='GPU3 owned process Xid detected; see sanitized kernel monitor evidence',
        retryable_infrastructure=True,time_unix=1.)
    retry={**row,'episode_key':row['episode_key']+'_r1','retry_of':'old','budget_bucket':'recovery'}
    current=simple_attempt(plan,runtime,retry,'new');current['terminal']['time_unix']=2.
    with pytest.raises(ValueError,match='exact prospective'):
        d.summarize(plan,[prior,current])


def test_prior_health_cost_disclosed_but_never_recharged(fixture,monkeypatch):
    _,plan,_,_,*_=fixture
    declared=plan['n3_cohort']['health_resources'][0]
    ref={'resource_id':declared['resource_id'],'scope':declared['scope'],
        'terminal':{'path':'synthetic.json','sha256':'fake'}}
    monkeypatch.setattr(d,'read_ref',lambda _: {'resource_id':declared['resource_id'],'event':'completed','gpu_process_wall_seconds':90000.})
    result=d.resource_costs(plan,[ref],[])
    assert result['new_cohort_seconds']==0 and result['reused_prior_health_seconds_not_recharged']==90000
    assert result['episode_dispatches_observed']==0
    with pytest.raises(ValueError,match='all frozen health'):d.resource_costs(plan,[],[])


def native(values,shape,dtype='torch.float32'):
    # Metadata is synthetic; full byte/value identity is the independent auditor's gate.
    return {'dtype':dtype,'shape':shape,'sha256':'a'*64,'values':values}


def metric_pair():
    projection=native([[float(i),0.,0.] for i in range(9)],[9,3]);origin=native([0.,0.,0.],[3])
    context={'episode_generation':1,'global_step':0,'stage':1,'provider_identity':{'code':'known'},
        'target_index':0,'registry_instance_id':1234,'registry_generation':2,'target_valid':True,'target_status':'tracked',
        'tracker_snapshot':{'instance_id':1234,'generation':2,'targets':{'0':{'valid':True,'status':'tracked'}}}}
    selected={'selected_native_sha256':'b'*64,'projection':projection,'source_origin':origin,
        'raw_provider_quality':native(-1.,[]),'start_global_step':0,'eligible':True}
    def record(step,active):
        return {'episode':0,'task_id':0,'global_step':step,'score_call_count':11,'search_evaluation_count':176,
            **dict.fromkeys(d.VIOLATIONS,0),'action_mask_violation_max':0.,'qd_archive_active_for_chunk':True,
            'qd_quality_mode':'executed_feedback_v1','qd_quality_applicable':True,'qd_quality_reason':'recognized',
            'qd_quality_target_index':0,'qd_quality_identity':{'code':'known'},'qd_quality_changed_candidates':176 if active else 0,
            'qd_quality_batches':[{'iter_idx':i,'raw_provider_quality':[-1.]*16,'quality':[-2. if active else -1.]*16,
                                   'fingerprints':['x']*16} for i in range(-1,10)],
            'qd_selected_raw_reward':-1.,'qd_final_best_raw_reward':-1.,'qd_selected_raw_gap':0.,
            'qd_best_observed_raw_reward':-1.,'selected_reward':-2. if active else -1.,
            'qd_feedback_overhead_scope':'canonical_native_copy_and_quality_only',
            'qd_feedback_active':active,'qd_feedback_reason':'eligible_immediate_full_prefix' if active else 'no_complete_history',
            'qd_feedback_context':{**context,'global_step':step},'qd_feedback_previous':{},
            'qd_feedback_selected':{**selected,'start_global_step':step},'qd_feedback_overhead_seconds':.01}
    first,second=record(0,False),record(8,True)
    second['qd_feedback_previous']={'start_global_step':0,'end_global_step':7,'ack_count':8,'feedback_was_active':False,'terminated':False,'truncated':False,
        'selected_native_sha256':'b'*64,'projection':projection,'source_origin':origin,
        'actual_endpoint':native([9.,0.,0.],[3]),'residual':native([1.,0.,0.],[3],dtype='torch.float64')}
    terminal={'identity':{'profile':'N3','task_id':0},'metric_chunks':2,'score_batches':22,'candidate_evaluations':352}
    return [first,second],terminal


def test_real_feedback_timing_is_separate_from_recognized_nohistory():
    metrics,terminal=metric_pair()
    result=d.summarize_metrics(metrics,terminal,native_audit(),{'guided_chunks':2,'execution_feedback_seconds_by_scope':{}})
    assert result['n3']['applicable_chunks']==2 and result['n3']['feedback_active_chunks']==1
    assert result['n3']['quality_changed_candidates']==176
    assert result['n3']['feedback_overhead_seconds']['complete_total']==.02
    assert result['n3']['selection_change_count'] is None
    alignment=result['n3']['native_feedback_bundle_alignment']
    assert alignment['status']=='verified' and alignment['active_decisions']==1
    assert alignment['search_activity_or_checkpoint_release'] is False


@pytest.mark.parametrize('mutate',[
    lambda a:a.pop('n3_feedback_audit'),
    lambda a:a['n3_feedback_audit'].update(schema='old-generic-audit'),
    lambda a:a['n3_feedback_audit'].update(scope='different claim'),
    lambda a:a['n3_feedback_audit'].update(checked_decisions=1),
    lambda a:a['n3_feedback_audit'].update(active_previous_ack_verified=2,inactive_decisions=0),
    lambda a:a['n3_feedback_audit'].update(active_previous_ack_verified=0,inactive_decisions=2),
    lambda a:a['n3_feedback_audit'].update(inactive_ack_clears_unknown=True),
    lambda a:a['n3_feedback_audit'].update(uncommitted_clears=-1),
])
def test_native_audit_requires_exact_counts_and_schema_not_generic_acceptance(mutate):
    metrics,terminal=metric_pair();audit=native_audit();mutate(audit)
    with pytest.raises(ValueError,match='native feedback audit'):
        d.summarize_metrics(metrics,terminal,audit,{'guided_chunks':2,'execution_feedback_seconds_by_scope':{}})


@pytest.mark.parametrize('mutate,message',[
    (lambda m:m[1]['qd_feedback_previous'].update(ack_count=7),'timing'),
    (lambda m:m[1]['qd_feedback_previous'].update(end_global_step=8),'timing'),
    (lambda m:m[1]['qd_feedback_previous'].update(terminated=True),'timing'),
    (lambda m:m[1]['qd_feedback_context'].update(target_valid=False),'target/registry'),
    (lambda m:m[1]['qd_feedback_context'].update(registry_generation=3),'tracker'),
    (lambda m:m[1]['qd_feedback_previous'].update(selected_native_sha256='c'*64),'native selected'),
    (lambda m:m[1]['qd_feedback_previous']['residual'].update(values=[2.,0.,0.]),'residual arithmetic'),
    (lambda m:m[0].update(selected_reward=-2.),'fallback'),
])
def test_feedback_metadata_contradictions_fail_not_Unknown(mutate,message):
    metrics,terminal=metric_pair();mutate(metrics)
    with pytest.raises(ValueError,match=message):
        d.summarize_metrics(metrics,terminal,{}, {'guided_chunks':2,'execution_feedback_seconds_by_scope':{}})


def test_unknown_provider_preserved_as_inactive_not_certified_feedback():
    metrics,terminal=metric_pair();m=metrics[0]
    m.update(qd_quality_applicable=False,qd_quality_reason='unsupported_provider',qd_quality_batches=[],
        qd_feedback_context={},qd_feedback_selected={},qd_feedback_reason='unsupported_provider')
    terminal.update(metric_chunks=1,score_batches=11,candidate_evaluations=176)
    result=d.summarize_metrics([m],terminal,{'accepted':True,'evidence_complete':True}, {'guided_chunks':1,'execution_feedback_seconds_by_scope':{}})
    assert result['n3']['feedback_active_chunks']==0 and result['n3']['inapplicable_chunks']==1
    assert result['n3']['native_feedback_bundle_alignment']['status']=='not_applicable'
    assert result['n3']['native_feedback_bundle_alignment']['search_activity_or_checkpoint_release'] is False


def test_multiple_predispatch_records_original_and_recovery_keep_full_journal_costs(fixture):
    _,original,_,runtime,*_=fixture;plan=report_plan(original);row=plan['episodes'][0]
    attempts=[];journal=[];specs=[]
    def add(attempt,dispatched):
        terminal=attempt['terminal'];terminal['n3_episode_dispatched']=dispatched
        if not dispatched:
            terminal.update(event='aborted',outcome_valid=False,success=False,gpu_process_wall_seconds=0.)
            attempt['status']='predispatch_rejected'
        journal.append({**terminal,'event':'reserved'})
        if dispatched:journal.append({**terminal,'event':'dispatched'})
        journal.append(copy.deepcopy(terminal));attempts.append(attempt)
        path=Path(terminal['output_dir'])/'attempt-result.json';path.parent.mkdir(parents=True,exist_ok=True);r.durable_json(path,terminal)
        specs.append({'terminal':{'path':str(path),'sha256':r.digest(path)}})
    for i in range(3):add(simple_attempt(plan,runtime,row,'pre'+str(i),valid=False),False)
    prior=simple_attempt(plan,runtime,row,'actual-original',valid=False)
    prior['terminal'].update(event='aborted',reason='external GPU3 process appeared during owned attempt',retryable_infrastructure=True,time_unix=10.)
    add(prior,True)
    retry={**row,'episode_key':row['episode_key']+'_r1','retry_of':'actual-original','budget_bucket':'recovery',
        'n3_recovery_contract':n.binding(plan,runtime)}
    revised=copy.deepcopy(plan);revised['episodes'].append(retry)
    pre_retry=simple_attempt(revised,runtime,retry,'retry-preadmission',valid=False)
    pre_retry['terminal']['plan_sha256']='revision-sha';add(pre_retry,False)
    good=simple_attempt(revised,runtime,retry,'actual-retry');good['terminal'].update(plan_sha256='revision-sha',time_unix=20.)
    add(good,True)
    excerpt={'schema':'qd-ed-n3-journal-excerpt-v1','cohort_id':n.COHORT,
        'extraction':'all_events_all_n3_attempts_through_snapshot',
        'source_journal':{'path':str(Path(plan['worktree'])/'data/attempt-ledger.jsonl'),'sha256':'f'*64},
        'events':journal,'inflight_attempt_ids':[],'terminal_attempt_ids':[a['terminal']['attempt_id'] for a in attempts]}
    plans={'base-sha':plan,'revision-sha':revised}
    d.validate_journal_excerpt(excerpt,specs,plans,plan)
    result=d.summarize(plan,attempts)
    assert result['terminal_records']==6 and result['episode_dispatches']==2
    assert len(result['predispatch_records'])==4 and len(result['cells'][0]['attempts'])==2
    assert result['cells'][0]['valid_attempt_id']=='actual-retry'
    assert result['profiles']['C0']['all_attempt_gpu_seconds']['complete_total']==26.
    assert result['predispatch_gpu_seconds']['complete_total']==0.
    with pytest.raises(ValueError,match='omitted/repeated'):
        d.validate_journal_excerpt(excerpt,specs[1:],plans,plan)
    changed=copy.deepcopy(excerpt);changed['events'][1]['n3_episode_dispatched']=True
    with pytest.raises(ValueError,match='disagrees'):
        d.validate_journal_excerpt(changed,specs,plans,plan)
    changed=copy.deepcopy(excerpt);changed['events'][0]['identity']['env_seed']+=1
    with pytest.raises(ValueError,match='identity changed'):
        d.validate_journal_excerpt(changed,specs,plans,plan)


def test_only_predispatch_records_never_satisfy_cell_or_checkpoint(fixture):
    _,original,_,runtime,*_=fixture;plan=report_plan(original)
    pre=simple_attempt(plan,runtime,plan['episodes'][0],'pre',valid=False)
    pre['terminal'].update(n3_episode_dispatched=False,event='aborted',gpu_process_wall_seconds=0.)
    pre['status']='predispatch_rejected'
    result=d.summarize(plan,[pre])
    assert result['first_three']['all_complete_valid'] is False
    assert result['cells'][0]['status']=='missing' and result['profiles']['C0']['complete_valid']==0


@pytest.mark.parametrize('dispatched',[False,True])
def test_running_journal_group_is_known_inflight_without_terminal_reads(fixture,monkeypatch,dispatched):
    _,original,_,runtime,*_=fixture;plan=report_plan(original)
    row=plan['episodes'][0];terminal=simple_attempt(plan,runtime,row,'running')['terminal']
    base={k:v for k,v in terminal.items() if k not in {'event','success','task_failure','outcome_valid',
        'n3_episode_dispatched','gpu_process_wall_seconds'}}
    group=[{**base,'event':'reserved'}]
    if dispatched:group.append({**base,'event':'dispatched'})
    excerpt={'schema':'qd-ed-n3-journal-excerpt-v1','cohort_id':n.COHORT,
        'extraction':'all_events_all_n3_attempts_through_snapshot',
        'source_journal':{'path':str(Path(plan['worktree'])/'data/attempt-ledger.jsonl'),'sha256':'e'*64},
        'events':group,'terminal_attempt_ids':[],'inflight_attempt_ids':['running']}
    def no_payload(*args,**kwargs):pytest.fail('no inflight outcome/audit/metrics read')
    monkeypatch.setattr(d,'read_ref',no_payload)
    active=d.validate_journal_excerpt(excerpt,[],{'base-sha':plan},plan)
    result=d.summarize(plan,[],active)
    assert result['episode_dispatches']==int(dispatched)
    assert result['cells'][0]['status']==('inflight_dispatched' if dispatched else 'reserved_no_dispatch')
    assert result['cells'][0]['success'] is None and result['first_three']['all_complete_valid'] is False
    assert result['profiles']['C0']['all_attempt_gpu_seconds']['complete_total'] is None
    assert result['profiles']['C0']['all_attempt_gpu_seconds']['missing_values']==1
    costs=d.resource_costs({**plan,'n3_cohort':{**plan['n3_cohort'],'health_resources':[]}},[],[],active)
    assert costs['new_cohort_seconds'] is None and costs['within_local_8_hours'] is None
    assert costs['new_cohort_seconds_observed_subtotal']==0 and costs['inflight_costs_settled'] is False
    missing=copy.deepcopy(excerpt);missing['inflight_attempt_ids']=[]
    with pytest.raises(ValueError,match='inflight inventory'):
        d.validate_journal_excerpt(missing,[],{'base-sha':plan},plan)
