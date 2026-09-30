#!/usr/bin/env python3
"""CPU-only forensic eligibility; never repairs an invalid scientific outcome."""
from __future__ import annotations
import math
from pathlib import Path
import types
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_worker as worker

DERIVATIVE_FAILURES={
    'Codex token usage incomplete',
    'Codex Stage call failure invalidates the frozen transport condition',
    'Codex Stage event lacks one measured call with complete usage',
}


def finite(value):return type(value) in (int,float) and math.isfinite(value)


def timeout_event(event,*,named_step=None):
    require=worker.require;t=event.get('transport',{});life=t.get('lifecycle',{})
    require(event.get('query_ok') is False and event.get('query_status')=='error'
        and event.get('error')=='codex_timeout' and event.get('raw_response') is None
        and event.get('codex_logical_call_attempts')==1 and event.get('codex_completed_turns')==0
        and event.get('codex_failed_calls')==1 and event.get('codex_usage_complete_calls')==0,
        'typed timeout missing exact failed/no-completion call')
    require(t.get('backend')=='codex_cli' and t.get('model')=='gpt-6-astra'
        and t.get('reasoning_effort')=='low' and t.get('timeout_seconds')==180.
        and t.get('auth_mode')=='chatgpt' and t.get('completed_turns')==0
        and t.get('observed_usage')==[] and isinstance(t.get('event_types'),list)
        and isinstance(t.get('item_types'),list),'typed timeout transport/retained events absent')
    kinds=t['event_types'];items=t['item_types']
    require(kinds.count('thread.started')==kinds.count('turn.started')==1
        and kinds[:2]==['thread.started','turn.started']
        and all(k in {'thread.started','turn.started','item.started','item.updated','item.completed'} for k in kinds)
        and all(k=='reasoning' for k in items),'typed timeout contains completion/agent/error/unknown event')
    require(life.get('schema')=='codex-stage-lifecycle-v1' and life.get('observation_complete') is True
        and life.get('observer_error_category') is None and life.get('first_completed_observed_at') is None
        and life.get('first_complete_usage_observed_at') is None and life.get('complete_usage_observed') is False
        and isinstance(life.get('events'),list) and [e.get('kind') for e in life['events']]==kinds
        and [e.get('item_kind') for e in life['events'] if e.get('kind','').startswith('item.')]==items,
        'typed timeout retained lifecycle evidence incomplete')
    times=[life.get(k) for k in ('communicate_started_at','timeout_observed_at','cleanup_started_at','cleanup_returned_at','process_exit_observed_at')]
    require(all(finite(x) for x in times) and times==sorted(times) and times[1]-times[0]>=180.
        and finite(event.get('codex_call_latency_s')) and event['codex_call_latency_s']>=180.,
        'typed timeout 180s completed cleanup witness missing')
    # These are unchanged observed deltas, not actual failed-call usage. Unknown is explicit in our report.
    require(all(event.get('codex_'+k)==0 for k in ('input_tokens','cached_input_tokens','output_tokens')),
        'typed timeout unexpectedly contains token usage')
    if named_step is not None:
        require(event.get('global_step')==named_step and kinds==['thread.started','turn.started'] and items==[],
            'named predecessor timeout step/event shape differs')
    return {'global_step':event['global_step'],'unknown_token_calls':1,
        'token_usage':{'input_tokens':None,'cached_input_tokens':None,'output_tokens':None},
        'usage_interpretation':'unknown; observed episode token counters remain partial lower bounds'}


def diagnose(final,row,profile,runtime,r,*,native_report,named_step=None):
    """Record only preregistered derivative failures in a private validator copy.

    The live validator/global require function and original terminal remain untouched.
    This function never returns outcome_valid=True or an accepted scientific result.
    """
    require=worker.require;output=Path(final['output_dir'])
    require(sha_addendum_ok() and final.get('event')=='valid' and final.get('outcome_valid') is False
        and final.get('retry_of') is None and final.get('compute_outcome')=='completed'
        and final.get('reason') in DERIVATIVE_FAILURES-{ 'Codex Stage event lacks one measured call with complete usage' }
        and final.get('required_cost_telemetry_complete') is False
        and final.get('provider_token_usage_complete') is False
        and finite(final.get('gpu_process_wall_seconds')) and 0<final['gpu_process_wall_seconds']<=1800.,
        'typed recovery requires completed invalid primary with only timeout-derived incompleteness')
    require(final.get('identity')==r['episode_identity'](row) and final.get('init_row_sha256')==row['init_row_sha256'],
        'typed primary scientific identity differs')
    require(native_report.get('accepted') is True and native_report.get('evidence_complete') is True
        and native_report.get('schema')=='qd-ed-decision-evidence-audit-v1'
        and Path(native_report['episode_dir']).resolve()==(output/'eds_eval/decision_evidence/episode_000').resolve()
        and Path(native_report['episode_compute_file']).resolve()==(output/'eds_eval/episode_compute.jsonl').resolve(),
        'typed primary lacks independent native audit of this output')
    stages=r['read_events'](output/'eds_eval/stage_events.jsonl')
    actual=[e for e in stages if e.get('query_status')!='skipped']
    failed=[e for e in actual if e.get('query_ok') is not True]
    require(len(failed)==1 and len(actual)>1,'typed recovery requires exactly one failed Stage call and other successes')
    unknown=timeout_event(failed[0],named_step=named_step)
    for event in actual:
        if event is failed[0]:continue
        require(event.get('query_status')=='ok' and event.get('query_ok') is True
            and event.get('codex_completed_turns')==event.get('codex_usage_complete_calls')==1
            and event.get('codex_failed_calls')==0,'typed primary contains another incomplete/failed call')
    costs=r['episode_compute'](output,row,runtime)
    require(costs.get('provider_logical_call_attempts')==len(actual)
        and costs.get('provider_failed_calls')==1 and costs.get('stage_codex_failed_calls')==1
        and costs.get('provider_completed_turns')==costs.get('provider_usage_complete_calls')==len(actual)-1
        and costs.get('required_cost_telemetry_complete') is False and costs.get('provider_token_usage_complete') is False,
        'typed timeout cannot explain all episode counters')
    require(all(final.get(k)==v for k,v in costs.items()),'typed terminal/observed compute counters differ')
    recorded=[]
    def evidence_require(ok,reason):
        if ok:return
        if reason not in DERIVATIVE_FAILURES:raise r['GateError'](reason)
        recorded.append(reason)
    def private_function(fn):return types.FunctionType(fn.__code__,{**fn.__globals__,'require':evidence_require},fn.__name__,fn.__defaults__,fn.__closure__)
    reconcile=private_function(r['validate_codex_stage_events'])
    validator=r['validate_result'];scope={**validator.__globals__,'require':evidence_require,'validate_codex_stage_events':reconcile}
    diagnostic_validator=types.FunctionType(validator.__code__,scope,validator.__name__,validator.__defaults__,validator.__closure__)
    derived=diagnostic_validator(output,row,profile,runtime)
    require(sorted(recorded)==sorted(DERIVATIVE_FAILURES),'typed diagnostic did not observe exactly the three explained derivative gates')
    require(derived['compute_outcome']=='completed' and derived['stage_failed_queries']==1
        and derived['required_cost_telemetry_complete'] is False,'typed diagnostic lost original invalidity')
    return {'schema':'n23-v2-timeout-diagnostic-v1','attempt_id':final['attempt_id'],
        'source_commit':final['source_commit'],'plan_sha256':final['plan_sha256'],'evidence_files':evidence_files(output),
        'diagnostic_reader':c.ref(__file__),
        'eligible_infrastructure_only':True,'outcome_valid':False,
        'timeout_observability':c.ref(c.OBSERVABILITY),'derivative_gate_failures':recorded,**unknown,
        'guided_chunks':derived['guided_chunks'],'candidate_evaluations':derived['candidate_evaluations'],
        'score_batches':derived['score_batches'],'original_required_cost_telemetry_complete':False,
        'observed_token_totals':{k:costs['provider_'+k] for k in ('input_tokens','cached_input_tokens','output_tokens')},
        'all_attempt_token_usage_complete':False}


def sha_addendum_ok():return c.sha(c.OBSERVABILITY)==c.OBSERVABILITY_SHA


def evidence_files(output):
    output=Path(output)
    mapping={'stage_events':'eds_eval/stage_events.jsonl','episode_compute':'eds_eval/episode_compute.jsonl',
        'episode_metadata':'eds_eval/episode_metadata.jsonl','safety_events':'eds_eval/safety_events.jsonl',
        'metrics':'eds_eval/eds_metrics.jsonl','resolved_config':'.hydra/config.yaml','results':'results.txt'}
    result={}
    for key,name in mapping.items():
        path=output/name
        if key=='safety_events':
            worker.require(not path.is_symlink(),'typed safety evidence path cannot be a symlink')
            result[key]={'path':str(path.resolve()),'present':path.is_file(),
                'sha256':c.sha(path) if path.is_file() else None}
            worker.require(path.is_file() or not path.exists(),'typed safety evidence is neither file nor absent')
        else:result[key]=c.ref(path)
    return result


def terminal_binding(final,row,plan,plan_reference,r):
    worker.require(final.get('identity')==r['episode_identity'](row) and final.get('episode_key')==row['episode_key']
        and final.get('source_commit')==plan['source_commit'] and final.get('plan_sha256')==plan_reference['sha256']
        and final.get('profile_manifest_sha256')==plan['profiles_sha256']
        and final.get('runtime_manifest_sha256')==plan['runtime_manifest_sha256']
        and final.get('runtime_inventory_sha256')==plan['runtime_inventory_sha256']
        and final.get('init_row_sha256')==row['init_row_sha256'] and final.get('physical_gpu')==7,
        'N23 v2 charged attempt source/plan/runtime/profile/identity differs')
    r['owned'](final['output_dir'],plan['artifact_root'])


def create_eligibility(plan_path,plan,row,final,profile,runtime,events,root,r):
    worker.require(row in plan['episodes'] and row['iteration']==c.COHORT,'N23 v2 eligibility row not primary')
    check_cell_history(events,row,final['attempt_id'],r)
    terminal_binding(final,row,plan,c.ref(plan_path),r)
    output=Path(final['output_dir']);terminal_ref=c.ref(output/'attempt-result.json')
    worker.require(worker.read_ref(terminal_ref)==final,'N23 v2 primary terminal artifact differs')
    worker.require(final.get('n23_worker_receipt')==c.ref(output/'eds_eval/in-worker-audit-receipt.json'),
        'N23 v2 invalid primary lacks metered native receipt')
    report=c.read_worker_report(output,r)
    diagnostic=diagnose(final,row,profile,runtime,r,native_report=report)
    record={'schema':'n23-v2-typed-timeout-eligibility-v1','cohort_id':c.COHORT,'primary_attempt_id':final['attempt_id'],
        'episode_key':row['episode_key'],'scientific_row':row,'plan':c.ref(plan_path),'source_commit':plan['source_commit'],
        'protocol':c.ref(c.PROTOCOL),'timeout_observability':c.ref(c.OBSERVABILITY),'terminal':terminal_ref,
        'native_receipt':c.ref(output/'eds_eval/in-worker-audit-receipt.json'),
        'native_report':c.ref(output/'eds_eval/decision-evidence-audit.json'),'process':c.ref(output/'process.json'),
        'evidence_files':evidence_files(output),'diagnostic':diagnostic,'primary_outcome_valid':False,
        'unknown_token_calls':1,'retry_budget_bucket':'recovery','same_cell_max_recoveries':1}
    return record


def check_cell_history(events,row,primary_id,r):
    local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
    groups=r['event_groups'](local);own=[g for g in groups.values() if g[0].get('episode_key')==row['episode_key']]
    worker.require(len(own)==1 and own[0][0]['attempt_id']==primary_id
        and [e['event'] for e in own[0]]==['reserved','dispatched','valid'] and own[0][-1].get('outcome_valid') is False
        and all(e.get('retry_of') is None for e in own[0]) and own[0][0]['identity']==r['episode_identity'](row),
        'N23 v2 recovery requires one completed invalid primary; no retry of valid or recovery')
    recovered={e['attempt_id'] for e in local if e.get('retry_of')}
    worker.require(len(recovered)<2,'N23 v2 two recovery slots already consumed')
    return own[0][-1]


def verify_eligibility(reference,plan,row,events,root,r):
    record=worker.read_ref(reference)
    require=worker.require
    require(record.get('schema')=='n23-v2-typed-timeout-eligibility-v1'
        and record.get('cohort_id')==c.COHORT and record.get('episode_key')==row['episode_key']
        and record.get('scientific_row')==row and record.get('source_commit')==plan['source_commit']
        and worker.read_ref(record['plan'])==plan,'N23 v2 eligibility plan/source/scientific row differs')
    final=check_cell_history(events,row,record['primary_attempt_id'],r)
    manifest=r['read_json'](plan['profiles_path'])
    for arm,reference in plan['candidate_profiles'].items():
        manifest['profiles'][arm]=r['expand_candidate'](arm,worker.read_ref(reference),manifest['profiles']['Q0'])
    runtime=worker.read_ref({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']})
    rebuilt=create_eligibility(record['plan']['path'],plan,row,final,manifest['profiles'][row['profile']],runtime,events,root,r)
    require(record==rebuilt,'N23 v2 typed eligibility changed or is not source-bound actual evidence')
    return record


def check_retry(events,row,r):
    record=worker.read_ref(row['n23_v2_recovery_eligibility']);plan=worker.read_ref(record['plan'])
    primary=c.primary_row(plan,row)
    worker.require(row.get('retry_of')==record['primary_attempt_id'] and row['budget_bucket']=='recovery',
        'N23 v2 recovery requires explicit primary link/recovery bucket')
    verify_eligibility(row['n23_v2_recovery_eligibility'],plan,primary,events,Path(plan['worktree']),r)
