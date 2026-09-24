"""N4 reporting synthetic public JSON only; no study outcomes/bundles."""
import copy
import json
import sys
from pathlib import Path
import pytest
from test_qd_ed_n4_plan import r,n,load,ROOT,fixture,events,native_audit,metric
sys.path.insert(0,str(ROOT/'scripts'))
d=load('n4_report_tests',ROOT/'scripts/qd_ed_n4_report.py')
def report_plan(plan):return copy.deepcopy(plan)


def simple_attempt(plan,runtime,row,identifier,*,success=False,valid=True):
    terminal={'attempt_id':identifier,'episode_key':row['episode_key'],'identity':r.episode_identity(row),
        'n4_episode_dispatched':True,'physical_gpu':3,'event':'valid','outcome_valid':valid,'success':success,'task_failure':not success,
        'budget_bucket':row['budget_bucket'],'retry_of':row.get('retry_of'), 'time_unix':float(len(identifier)),
        'gpu_process_wall_seconds':13.,'n4_cohort_id':n.COHORT,'n4_frozen_identity':n.binding(plan,runtime),
        'source_commit':plan['source_commit'],'profile_manifest_sha256':plan['profiles_sha256'],
        'runtime_manifest_sha256':plan['runtime_manifest_sha256'],'runtime_inventory_sha256':plan['runtime_inventory_sha256'],
        'init_row_sha256':row['init_row_sha256'],'plan_sha256':'base-sha','output_dir':str(Path(plan['artifact_root'])/identifier)}
    metrics={'finite_executed_actions':True,'observer_wall_s':1.,'observer_bytes_written':100,'qd_active_chunks':1,
        'n4':{'records':[],'native_terminal_population_alignment':{'checked_decisions':1},'actual_prefix_different_decisions':0}}
    return {'terminal':terminal,'status':'complete_valid' if valid else 'terminal_invalid','metrics':metrics}


def test_report_preserves_budget_assignment_and_rejects_terminal_or_contract_relabel(fixture):
    _,original,_,runtime,*_=fixture;plan=report_plan(original)
    row=plan['episodes'][0];assert row['budget_bucket']=='baseline'
    terminal=simple_attempt(plan,runtime,row,'c0')['terminal']
    d.plan_contract(plan);d.validate_terminal(terminal,plan,'base-sha')
    terminal['budget_bucket']='development'
    with pytest.raises(ValueError,match='frozen condition differs'):
        d.validate_terminal(terminal,plan,'base-sha')
    changed=copy.deepcopy(plan);changed['n4_cohort']['budget_allocation']['baseline_cells'].pop()
    with pytest.raises(ValueError,match='budget allocation/amendment'):
        d.plan_contract(changed)


def test_immutable_base_plus_recovery_revision_preserves_both_terminals_and_costs(fixture):
    _,original,_,runtime,*_=fixture;base=report_plan(original);saved=copy.deepcopy(base)
    row=base['episodes'][0];first=simple_attempt(base,runtime,row,'original',valid=False)
    first['terminal'].update(event='aborted',reason='external GPU3 process appeared during owned attempt',retryable_infrastructure=True,time_unix=1.)
    revised=copy.deepcopy(base)
    retry={**row,'episode_key':row['episode_key']+'_r1','retry_of':'original','budget_bucket':'recovery',
        'n4_recovery_contract':n.binding(base,runtime)}
    revised['episodes'].append(retry)
    second=simple_attempt(revised,runtime,retry,'recovered')
    second['terminal'].update(plan_sha256='revision-sha',time_unix=2.)
    d.validate_terminal(first['terminal'],base,'base-sha');d.validate_terminal(second['terminal'],revised,'revision-sha')
    result=d.summarize(base,[first,second]);cell=result['cells'][0]
    assert len(cell['attempts'])==2 and cell['valid_attempt_id']=='recovered'
    assert result['profiles']['C0']['all_attempt_gpu_seconds']['complete_total']==26
    assert base==saved
    second['terminal']['n4_frozen_identity']={**second['terminal']['n4_frozen_identity'],'source_commit':'changed'}
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
    declared=plan['n4_cohort']['health_resources'][0]
    ref={'resource_id':declared['resource_id'],'scope':declared['scope'],
        'terminal':{'path':'synthetic.json','sha256':'fake'}}
    monkeypatch.setattr(d,'read_ref',lambda _: {'resource_id':declared['resource_id'],'event':'completed','gpu_process_wall_seconds':90000.})
    result=d.resource_costs(plan,[ref],[])
    assert result['new_cohort_seconds']==0 and result['reused_prior_health_seconds_not_recharged']==90000
    assert result['episode_dispatches_observed']==0
    with pytest.raises(ValueError,match='all frozen health'):d.resource_costs(plan,[],[])


def test_multiple_predispatch_records_original_and_recovery_keep_full_journal_costs(fixture):
    _,original,_,runtime,*_=fixture;plan=report_plan(original);row=plan['episodes'][0]
    attempts=[];journal=[];specs=[]
    def add(attempt,dispatched):
        terminal=attempt['terminal'];terminal['n4_episode_dispatched']=dispatched
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
        'n4_recovery_contract':n.binding(plan,runtime)}
    revised=copy.deepcopy(plan);revised['episodes'].append(retry)
    pre_retry=simple_attempt(revised,runtime,retry,'retry-preadmission',valid=False)
    pre_retry['terminal']['plan_sha256']='revision-sha';add(pre_retry,False)
    good=simple_attempt(revised,runtime,retry,'actual-retry');good['terminal'].update(plan_sha256='revision-sha',time_unix=20.)
    add(good,True)
    excerpt={'schema':'qd-ed-n4-journal-excerpt-v1','cohort_id':n.COHORT,
        'extraction':'all_events_all_n4_attempts_through_snapshot',
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
    changed=copy.deepcopy(excerpt);changed['events'][1]['n4_episode_dispatched']=True
    with pytest.raises(ValueError,match='disagrees'):
        d.validate_journal_excerpt(changed,specs,plans,plan)
    changed=copy.deepcopy(excerpt);changed['events'][0]['identity']['env_seed']+=1
    with pytest.raises(ValueError,match='identity changed'):
        d.validate_journal_excerpt(changed,specs,plans,plan)


def test_only_predispatch_records_never_satisfy_cell_or_checkpoint(fixture):
    _,original,_,runtime,*_=fixture;plan=report_plan(original)
    pre=simple_attempt(plan,runtime,plan['episodes'][0],'pre',valid=False)
    pre['terminal'].update(n4_episode_dispatched=False,event='aborted',gpu_process_wall_seconds=0.)
    pre['status']='predispatch_rejected'
    result=d.summarize(plan,[pre])
    assert result['first_three']['all_complete_valid'] is False
    assert result['cells'][0]['status']=='missing' and result['profiles']['C0']['complete_valid']==0


@pytest.mark.parametrize('dispatched',[False,True])
def test_running_journal_group_is_known_inflight_without_terminal_reads(fixture,monkeypatch,dispatched):
    _,original,_,runtime,*_=fixture;plan=report_plan(original)
    row=plan['episodes'][0];terminal=simple_attempt(plan,runtime,row,'running')['terminal']
    base={k:v for k,v in terminal.items() if k not in {'event','success','task_failure','outcome_valid',
        'n4_episode_dispatched','gpu_process_wall_seconds'}}
    group=[{**base,'event':'reserved'}]
    if dispatched:group.append({**base,'event':'dispatched'})
    excerpt={'schema':'qd-ed-n4-journal-excerpt-v1','cohort_id':n.COHORT,
        'extraction':'all_events_all_n4_attempts_through_snapshot',
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
    costs=d.resource_costs({**plan,'n4_cohort':{**plan['n4_cohort'],'health_resources':[]}},[],[],active)
    assert costs['new_cohort_seconds'] is None and costs['within_local_8_5_hours'] is None
    assert costs['new_cohort_seconds_observed_subtotal']==0 and costs['inflight_costs_settled'] is False
    missing=copy.deepcopy(excerpt);missing['inflight_attempt_ids']=[]
    with pytest.raises(ValueError,match='inflight inventory'):
        d.validate_journal_excerpt(missing,[],{'base-sha':plan},plan)


def test_all_twelve_numeric_and_actual_prefix_activity_are_independent(fixture):
    _,plan,_,runtime,*_=fixture;attempts=[]
    successes={'C0':{0},'Q0':{0,6},'N4':{0,3}}
    for i,row in enumerate(plan['episodes']):
        attempts.append(simple_attempt(plan,runtime,row,str(i),success=row['task_id'] in successes[row['profile']]))
    result=d.summarize(plan,attempts)
    assert result['matrix']=='complete_valid_12' and result['protocol_numeric_dev_criterion'] is True
    assert result['protocol_execution_activity_criterion'] is False and result['phase_authorized'] is False
    assert result['paired_comparisons']['N4_vs_Q0']['gained_tasks']==[3]
    assert result['paired_comparisons']['N4_vs_Q0']['lost_tasks']==[6]
    attempts[2]['metrics']['n4']['actual_prefix_different_decisions']=1
    assert d.summarize(plan,attempts)['protocol_execution_activity_criterion'] is True
    partial=d.summarize(plan,attempts[:-1])
    assert partial['protocol_numeric_dev_criterion'] is None and partial['profiles']['N4']['success_rate'] is None
    assert partial['protocol_execution_activity_criterion'] is None


def test_n4_metrics_must_match_compute_and_native_consumer_not_legacy_acceptance():
    m={**metric(),**dict.fromkeys(d.VIOLATIONS,0),'episode':0,'task_id':0,
       'score_call_count':11,'search_evaluation_count':176,'action_mask_violation_max':0.,'qd_archive_active_for_chunk':True}
    terminal={'identity':{'profile':'N4','task_id':0},'metric_chunks':1,'score_batches':11,'candidate_evaluations':176}
    compute={'guided_chunks':1}
    result=d.summarize_metrics([m],terminal,native_audit(),compute)
    assert result['n4']['actual_prefix_different_decisions']==0
    with pytest.raises(ValueError,match='guided metric counts'):d.summarize_metrics([m],terminal,native_audit(),{'guided_chunks':2})
    for missing in ['qd_final_selection_mode','qd_terminal_population','qd_archive_reference']:
        changed=copy.deepcopy(m);changed.pop(missing)
        with pytest.raises(ValueError,match='consumer metrics'):d.summarize_metrics([changed],terminal,native_audit(),compute)
    with pytest.raises(ValueError,match='audit missing'):
        d.summarize_metrics([m],terminal,{'accepted':True,'evidence_complete':True},compute)


@pytest.mark.parametrize('mutate',[
    lambda a:a['n4_terminal_population_audit'].update(checked_decisions=0),
    lambda a:a['n4_terminal_population_audit'].update(parent_rounds_verified=9),
    lambda a:a['n4_terminal_population_audit'].update(decoded_reference_actual_prefix_different_decisions=1),
    lambda a:a['n4_terminal_population_audit'].update(actual_actions_verified=7),
    lambda a:a['n4_terminal_population_audit']['decisions'][0].update(global_step=8),
    lambda a:a['n4_terminal_population_audit']['decisions'][0].update(decoded_reference_actual_prefix_diff_positions=[[8,0]]),
])
def test_native_summary_corruption_never_degrades_to_generic_accepted(mutate):
    audit=native_audit();mutate(audit)
    with pytest.raises(ValueError):n.native_audit_alignment(audit,[metric()],require=d.require)


@pytest.mark.parametrize('mutate',[
    lambda m:m.update(qd_terminal_population={}),
    lambda m:m['qd_terminal_population'].update(selected_index=1),
    lambda m:m['qd_terminal_population'].update(selected_occurrence_id='other'),
    lambda m:m['qd_terminal_population'].update(selected_cost=-99.),
    lambda m:m['qd_terminal_population'].update(selected_raw_reward=99.),
    lambda m:m['qd_terminal_population'].update(minimum_cost_tie_indices=[0]),
    lambda m:m['qd_terminal_population'].update(scoring_batch_id=-1),
    lambda m:m['qd_terminal_population'].update(cost_dtype='torch.bfloat16'),
    lambda m:m['qd_archive_reference'].update(selected_fingerprint='corrupt'),
    lambda m:m['qd_archive_reference'].update(costs=[-4.,-2.]),
    lambda m:m.update(qd_global_best_action_fingerprint='corrupt'),
    lambda m:m.update(selected_reward=0.),
    lambda m:m.update(target_distance_after=0.),
])
def test_metrics_must_be_same_native_audited_selected_and_reference(mutate):
    m=metric();mutate(m)
    with pytest.raises(ValueError):n.native_audit_alignment(native_audit(),[m],require=d.require)


def test_native_actual_prefix_cannot_be_empty_or_count_nonexecuted_tail_difference():
    audit=native_audit(1,1);decision=audit['n4_terminal_population_audit']['decisions'][0]
    decision['actual_prefix_length']=0
    with pytest.raises(ValueError,match='prefix length'):n.native_audit_alignment(audit,[metric()],require=d.require)
    decision['actual_prefix_length']=3
    decision['decoded_reference_first8_diff_positions']=[[6,0]]
    decision['decoded_reference_actual_prefix_diff_positions']=[]
    audit['n4_terminal_population_audit'].update(actual_actions_verified=3,decoded_reference_actual_prefix_different_decisions=0)
    result=n.native_audit_alignment(audit,[metric()],require=d.require)
    assert result['actual_prefix_different_decisions']==0
