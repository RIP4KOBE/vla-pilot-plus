"""Synthetic N23 v2 gate tests. Real historical evidence is forbidden by path guard."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import pytest
import torch
import yaml
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_v2_recovery as recovery
from scripts import qd_ed_n23_v2_backend as backend
from scripts import qd_ed_n23_worker as worker


def write(path,value,jsonl=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(('\n'.join(json.dumps(x) for x in value)+'\n') if jsonl else json.dumps(value))
    return c.ref(path)


@pytest.fixture(autouse=True)
def no_cuda():
    yield
    assert not torch.cuda.is_initialized()


def authority():
    return {'gpu_pool':[7],'max_concurrent_gpu_workers':1,
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
        'budget':{'max_episode_attempts':478,'max_gpu_hours':100.,'reserved':dict(runner.N23_BUCKETS),
            'amendment':dict(runner.GPU7_N23_V2_AMENDMENT),'dispatched':0,'gpu_hours_consumed':0.,'running':0,
            'gpu_hour_reservations':{'validation':32.,'formal':12.}},
        'n23_v2_gpu7_binding':{'scope':c.COHORT+'_and_backend_preflight_only','user_reply':c.AUTONOMOUS_REPLY,
            'selected_gpu':7,'addendum_path':str(c.PROTOCOL),'addendum_sha256':c.PROTOCOL_SHA}}


def test_versions_keep_legacy_routing_and_exact_static_algorithm():
    assert runner.n23_support({'n23_cohort':{'schema':'n23-clipped-quality-dev-v2'}}) is c
    assert runner.n23_support().__name__.endswith('qd_ed_n23_dev_contract')
    assert not runner.is_n7_plan({'n23_cohort':{'schema':'n23-clipped-quality-dev-v2'},'candidate_profiles':{'N7':{},'N23':{}}})
    old=runner.n23_support().expected_rows();new=c.expected_rows()
    for a,b in zip(old,new):
        assert {k:v for k,v in a.items() if k not in {'iteration','episode_key'}}=={k:v for k,v in b.items() if k not in {'iteration','episode_key'}}
    assert backend.check_batch is backend.legacy.check_batch and backend.synthetic_batches is backend.legacy.synthetic_batches
    assert backend.iter_batches is backend.legacy.iter_batches and backend.LIMITS==backend.legacy.LIMITS


@pytest.mark.parametrize('iteration',list(c.ALL_PREFLIGHTS|c.ALL_COHORTS))
@pytest.mark.parametrize('event',['reserved','dispatched','valid','aborted'])
def test_cross_version_preflight_is_one_opportunity(iteration,event):
    with pytest.raises(ValueError):c.cross_version_unused([{'identity':{'iteration':iteration},'event':event}])
    c.cross_version_unused([])


def test_full_capacity_reserves_two_recoveries_and_preflight():
    r=dict(vars(runner));snap=runner.budget_snapshot([])
    r['budget_snapshot']=lambda *_:copy.deepcopy(snap)
    c.full_capacity(authority(),[],[],r,preflight=True)
    snap['by_bucket']['recovery']=18
    with pytest.raises(ValueError,match='capacity'):c.full_capacity(authority(),[],[],r,preflight=True)
    c.full_capacity(authority(),[],[],r,preflight=False)
    snap['by_bucket']['recovery']=0;snap['gpu_hours_consumed']=34.
    c.full_capacity(authority(),[],[],r)
    with pytest.raises(ValueError,match='ceiling'):c.full_capacity(authority(),[],[],r,preflight=True)
    snap['gpu_hours_consumed']=0.;snap['dispatched']=216
    with pytest.raises(ValueError,match='protected attempts'):c.full_capacity(authority(),[],[],r,preflight=True)


def failing_case(tmp_path,monkeypatch):
    # Reuse the existing generic runner's real format builder, then execute its unchanged validator/failed_outcome.
    spec=importlib.util.spec_from_file_location('v2_real_runner_format',runner.ROOT/'tests/test_qd_ed_final_runner.py')
    helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    row,profile,runtime,path,compute=helpers.codex_compute_case(tmp_path,monkeypatch,calls=2)
    r=helpers.runner;row.update(iteration=c.COHORT,profile='C0',episode_key='n23v2_dev_t08_c0_fixture',
        timeout_seconds=1800,budget_bucket='baseline',init_row_sha256='a'*64)
    frozen=runtime['frozen_stage_provider'];frozen.update(timeout_seconds=180,allow_recovered_error_events=True)
    frozen['public_config_sha256']=r.codex_public_config_sha256(frozen)
    runtime.update(stage_recovered_error_condition=r.E2_STAGE_CONDITION,
        stage_engineering_condition=r.n4e1_support().engineering_condition())
    resolved=yaml.safe_load((tmp_path/'.hydra/config.yaml').read_text())
    resolved['perception']['gemini'].update({k:frozen[k] for k in r.CODEX_CONFIG_KEYS},allow_recovered_error_events=True)
    (tmp_path/'.hydra/config.yaml').write_text(yaml.safe_dump(resolved))
    transport={**{k:frozen[k] for k in r.CODEX_CONFIG_KEYS},'auth_mode':'chatgpt','public_config_sha256':frozen['public_config_sha256'],
        'application_max_attempts':1,'internal_http_retry_observation_available':False,'internal_retry_policy':'cli_managed_unknown',
        'allow_recovered_error_events':True,'recovered_error_policy':'pre_final_only_v1'}
    compute.update(stage_transport=transport,provider_token_usage_complete=False)
    for prefix in ('stage_codex_','provider_'):
        compute.update({prefix+'failed_calls':1,prefix+'completed_turns':1,prefix+'usage_complete_calls':1,
            prefix+'input_tokens':100,prefix+'cached_input_tokens':20,prefix+'output_tokens':10,prefix+'call_latency_s':183.})
    write(path,[compute],True)
    base={'episode_id':0,'task_id':row['task_id'],'episode_seed':row['env_seed'],'api_request_attempts':None,
        'api_sdk_retry_attempts':None,'api_request_counter_available':False,
        'codex_logical_call_attempts':1,'codex_completed_turns':1,'codex_failed_calls':0,'codex_usage_complete_calls':1,
        'codex_input_tokens':100,'codex_cached_input_tokens':20,'codex_output_tokens':10,'codex_call_latency_s':2.,
        'query_ok':True,'query_status':'ok','transport':{**transport,'recoverable_error_event_count':0,
            'recoverable_error_item_count':0,'recovered_error_events_accepted':False}}
    ok={**base,'global_step':0}
    failed={**copy.deepcopy(base),'global_step':112,'query_ok':False,'query_status':'error','error':'codex_timeout','raw_response':None,
        'codex_completed_turns':0,'codex_failed_calls':1,'codex_usage_complete_calls':0,'codex_input_tokens':0,
        'codex_cached_input_tokens':0,'codex_output_tokens':0,'codex_call_latency_s':181.}
    failed['transport'].update(event_types=['thread.started','turn.started'],item_types=[],observed_usage=[],completed_turns=0,
        lifecycle={'schema':'codex-stage-lifecycle-v1','observation_complete':True,'observer_error_category':None,
            'first_completed_observed_at':None,'first_complete_usage_observed_at':None,'complete_usage_observed':False,
            'communicate_started_at':100.,'timeout_observed_at':280.1,'cleanup_started_at':280.2,
            'cleanup_returned_at':280.3,'process_exit_observed_at':280.4,
            'events':[{'kind':'thread.started'},{'kind':'turn.started'}]})
    write(tmp_path/'eds_eval/stage_events.jsonl',[ok,failed],True)
    for name in ('eds_metrics.jsonl','safety_events.jsonl'):write(tmp_path/'eds_eval'/name,[],True)
    with pytest.raises(r.GateError,match='token usage incomplete') as caught:r.validate_result(tmp_path,row,profile,runtime)
    event,outcome=r.failed_outcome(caught.value,tmp_path,row,runtime=runtime)
    final={'event':event,**outcome,'attempt_id':'fixture','identity':r.episode_identity(row),'episode_key':row['episode_key'],
        'init_row_sha256':row['init_row_sha256'],'gpu_process_wall_seconds':1717.,'output_dir':str(tmp_path),
        'source_commit':'synthetic','plan_sha256':'plan-sha','retry_of':None}
    return r,row,profile,runtime,final,[ok,failed],compute


def native_report(output):
    return {'schema':'qd-ed-decision-evidence-audit-v1','accepted':True,'evidence_complete':True,
        'episode_dir':str(output/'eds_eval/decision_evidence/episode_000'),
        'episode_compute_file':str(output/'eds_eval/episode_compute.jsonl')}


def test_real_validator_timeout_unknown_cost_is_eligible_but_never_valid(tmp_path,monkeypatch):
    r,row,profile,runtime,final,events,compute=failing_case(tmp_path,monkeypatch)
    before=copy.deepcopy(final);original_require=r.require
    d=recovery.diagnose(final,row,profile,runtime,vars(r),native_report=native_report(tmp_path))
    assert d['eligible_infrastructure_only'] and d['outcome_valid'] is False and d['unknown_token_calls']==1
    assert d['token_usage']=={'input_tokens':None,'cached_input_tokens':None,'output_tokens':None}
    assert d['observed_token_totals']=={'input_tokens':100,'cached_input_tokens':20,'output_tokens':10}
    assert r.require is original_require and final==before and final['required_cost_telemetry_complete'] is False
    assert 'candidate_evaluations' not in final and d['candidate_evaluations']==0
    with pytest.raises(r.GateError,match='token usage incomplete'):r.validate_result(tmp_path,row,profile,runtime)


@pytest.mark.parametrize('fault',['agent','completed','other_error','missing_events','incomplete_observer','early_timeout',
    'extra_failure','wrong_usage','token_imputed','native','valid','recovery','interrupted','wall_timeout','qpos','config','compute_outcome','counter_missing','scoring_postgate'])
def test_typed_timeout_rejects_every_extra_fault(tmp_path,monkeypatch,fault):
    r,row,profile,runtime,final,events,compute=failing_case(tmp_path,monkeypatch)
    bad=events[1];report=native_report(tmp_path)
    if fault=='agent':bad['transport']['item_types']=['agent_message']
    if fault=='completed':bad['transport']['event_types'].append('turn.completed')
    if fault=='other_error':bad['error']='codex_transport_failure'
    if fault=='missing_events':bad['transport'].pop('event_types')
    if fault=='incomplete_observer':bad['transport']['lifecycle']['observation_complete']=False
    if fault=='early_timeout':bad['transport']['lifecycle']['timeout_observed_at']=279.
    if fault=='extra_failure':events[0]['query_ok']=False
    if fault=='wrong_usage':events[0]['codex_usage_complete_calls']=0
    if fault=='token_imputed':final['required_cost_telemetry_complete']=True
    if fault=='native':report['accepted']=False
    if fault=='valid':final['outcome_valid']=True
    if fault=='recovery':final['retry_of']='earlier'
    if fault=='interrupted':final['event']='aborted'
    if fault=='wall_timeout':final['gpu_process_wall_seconds']=1801.
    if fault=='qpos':write(tmp_path/'eds_eval/safety_events.jsonl',[{'event':'gripper_qpos_violation','count':1}],True)
    if fault=='config':p=tmp_path/'.hydra/config.yaml';v=yaml.safe_load(p.read_text());v['seed']=-1;p.write_text(yaml.safe_dump(v))
    if fault=='compute_outcome':compute['outcome']='interrupted'
    if fault=='counter_missing':compute.pop('model_forward_calls')
    if fault=='scoring_postgate':compute['guided_chunks']=1
    write(tmp_path/'eds_eval/episode_compute.jsonl',[compute],True);write(tmp_path/'eds_eval/stage_events.jsonl',events,True)
    with pytest.raises((ValueError,r.GateError,KeyError)):
        recovery.diagnose(final,row,profile,runtime,vars(r),native_report=report)
