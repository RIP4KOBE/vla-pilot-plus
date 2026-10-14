import copy
import hashlib
import json
from pathlib import Path
import pytest
from scripts.steering_transport_audit import audit_transport, WARNING_TEMPLATE, FALLBACK_PREFIX
from steering_audit_fixture import read_fixture_file
@pytest.fixture
def pair():
    base='output/captured_stage_inputs/request_0001/'
    return json.loads(read_fixture_file(base+'response.json')),json.loads(read_fixture_file(base+'public-policy.json'))
def passing(pair):
    checks=audit_transport(*pair)
    assert all(v is True for v in checks.values()), checks

def test_real_completed_request(pair): passing(pair)

def test_reasoning_and_agent_start_update_are_legal(pair):
    r,p=pair;t=r['transport']
    t['event_types']=['thread.started','turn.started','item.started','item.updated','item.completed','item.started','item.updated','item.completed','turn.completed']
    t['item_types']=['reasoning']*3+['agent_message']*3
    passing(pair)

def recovery(pair):
    r,p=pair;t=r['transport']
    t['event_types']=['thread.started','item.completed','turn.started','error','error','item.completed','error','item.completed','item.completed','turn.completed']
    t['item_types']=['error','error','reasoning','agent_message']
    warning=WARNING_TEMPLATE.format(model=p['model']);fallback=FALLBACK_PREFIX+'connection closed'
    t['model_metadata_warning_notices']=[dict(event_index=1,classification='exact_model_metadata_fallback_warning',message_sha256=hashlib.sha256(warning.encode()).hexdigest(),message_length=len(warning))]
    t['transport_fallback_notices']=[dict(event_index=5,classification='websocket_to_https_fallback_notice',message_sha256=hashlib.sha256(fallback.encode()).hexdigest(),message_length=len(fallback))]
    t['error_events']=[dict(event_index=i,classification='numbered_reconnecting_notice',message_sha256='a'*64,message_length=22,attempt=n,maximum=5) for i,n in [(3,1),(4,2),(6,1)]]
    t['error_diagnostics']=[dict(event_index=i,source='error_item',contains_nul=False,contains_line_break=False) for i in (1,5)]
    return pair

def test_v6_known_warning_fallback_and_reconnect_restart_are_legal(pair): passing(recovery(pair))

def test_legal_incomplete_retry_does_not_count_as_failed_response(pair):
    r,p=pair;t=r['transport'];t['physical_call_attempts']=2;r['counters']['logical_call_attempts']=2
    t['failed_transport_attempts']=[dict(error='codex_timeout',completed_turns=0,event_types=['thread.started','turn.started'],stderr_diagnostic={'signals':['timeout']},error_diagnostics=[])]
    passing(pair)

def test_eight_rate_limit_retries_keep_one_complete_response(pair):
    r,p=pair;t=r['transport']
    t['transport_retry_count']=8
    t['transport_retry_backoff_seconds']=30.
    t['physical_call_attempts']=9
    r['counters']['logical_call_attempts']=9
    t['failed_transport_attempts']=[dict(error='codex_expected_one_completed_turn',
        completed_turns=0,event_types=['thread.started','turn.failed'],
        stderr_diagnostic={'signals':[]},
        error_diagnostics=[{'signals':['rate_limited'],'http_status_codes':[429]}]) for _ in range(8)]
    passing(pair)
    t['transport_retry_count']=7
    assert audit_transport(r,p)['bounded_transport_retries'] is False

@pytest.mark.parametrize('reasoning',[None,0])
def test_reasoning_unknown_remains_unknown_across_requests(pair,reasoning):
    r,p=pair;r['counters']['reasoning_output_tokens']=None
    r['transport']['observed_usage'][0]['reasoning_output_tokens']=reasoning
    r['completion_metadata']['usage'][0]['reasoning_output_tokens']=reasoning
    passing(pair)

@pytest.mark.parametrize('mutation',[
    'extra_response','missing_item_summary','unknown_item','nonzero_exit','timeout',
    'wrong_model','wrong_policy','wrong_tokens','missing_usage','extra_retry',
    'completed_retry','terminal_retry','semantic_retry','unrecognized_error',
    'duplicate_reconnect','wrong_warning_hash','wrong_notice_index','missing_notice',
])
def test_corrupt_transport_is_rejected(pair,mutation):
    r,p=recovery(pair);t=r['transport']
    if mutation=='extra_response': t['event_types'].insert(-1,'item.completed');t['item_types'].append('agent_message')
    elif mutation=='missing_item_summary': t['item_types'].pop()
    elif mutation=='unknown_item': t['item_types'][-1]='command_execution'
    elif mutation=='nonzero_exit': t['process_returncode']=1
    elif mutation=='timeout': t['process_timed_out']=True
    elif mutation=='wrong_model': t['model']='wrong'
    elif mutation=='wrong_policy': t['event_policy']='strict_v1'
    elif mutation=='wrong_tokens': r['counters']['input_tokens']+=1
    elif mutation=='missing_usage': t['observed_usage']=[]
    elif mutation=='extra_retry': t['physical_call_attempts']=3
    elif mutation in ('completed_retry','terminal_retry','semantic_retry'):
        t['physical_call_attempts']=2;r['counters']['logical_call_attempts']=2
        failure=dict(error='codex_timeout',completed_turns=0,event_types=[],stderr_diagnostic={'signals':[]})
        if mutation=='completed_retry': failure['completed_turns']=1
        elif mutation=='terminal_retry': failure['stderr_diagnostic']['signals']=['authentication_failed']
        else: failure['error']='codex_empty_response'
        t['failed_transport_attempts']=[failure]
    elif mutation=='unrecognized_error': t['error_events'][0]['classification']='unrecognized_error'
    elif mutation=='duplicate_reconnect': t['error_events'][1]['attempt']=1
    elif mutation=='wrong_warning_hash': t['model_metadata_warning_notices'][0]['message_sha256']='a'*64
    elif mutation=='wrong_notice_index': t['transport_fallback_notices'][0]['event_index']=8
    elif mutation=='missing_notice': t['transport_fallback_notices']=[]
    assert any(v is False for v in audit_transport(r,p).values()), mutation

def test_malformed_data_fails_without_exception(): assert audit_transport({}, {})=={'transport_summary_well_formed':False}
