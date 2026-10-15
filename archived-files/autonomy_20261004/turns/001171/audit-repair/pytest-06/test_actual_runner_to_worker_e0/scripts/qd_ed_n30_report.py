"""Immutable N30 terminal reconstruction from its own journal and metered receipts."""
import math
from pathlib import Path
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n30_contract as c
from scripts import qd_ed_n30_native as native
COST_FIELDS=('gpu_process_wall_seconds','guided_chunks','unguided_chunks','candidate_evaluations','score_batches',
 'rbf_gradient_calls','rbf_gradient_batch_rows','model_forward_calls','model_batch_rows','reward_calls','reward_evaluations','reward_scoring_batches',
 'provider_logical_call_attempts','stage_codex_logical_call_attempts','provider_input_tokens',
 'provider_output_tokens','provider_cached_input_tokens','provider_failed_calls')


def summary(outcomes,attempts):
    by={a:{v['task_id']:v['success'] for v in outcomes if v['profile']==a} for a in c.ARMS}
    costs={a:{k:{'observed_total':0,'observed_attempts':0,'missing_attempts':[]} for k in COST_FIELDS} for a in c.ARMS}
    unknown=[];unmeasured=[]
    for item in attempts:
        final=item['terminal']
        logical=final.get('provider_logical_call_attempts');complete=final.get('provider_usage_complete_calls')
        if type(logical) is int and type(complete) is int and 0<=complete<=logical:unknown.append(logical-complete)
        else:unmeasured.append(item['attempt_id'])
        for k in COST_FIELDS:
            v=final.get(k);slot=costs[item['profile']][k]
            if type(v) in (int,float) and math.isfinite(v) and v>=0:slot['observed_total']+=v;slot['observed_attempts']+=1
            else:slot['missing_attempts'].append(item['attempt_id'])
    pairs={}
    for a in c.ARMS[:-1]:
        matched=set(by['N30'])&set(by[a]);pairs[a]={'denominator':len(matched),
            'gains':sum(by['N30'][t] and not by[a][t] for t in matched),
            'losses':sum(not by['N30'][t] and by[a][t] for t in matched)}
    return {'accepted_cell_denominators':{a:len(v) for a,v in by.items()},'matched_comparisons':pairs,
        'primary_attempt_denominators':{a:sum(v['profile']==a and not v['terminal'].get('retry_of') for v in attempts) for a in c.ARMS},
        'all_attempt_denominators':{a:sum(v['profile']==a for v in attempts) for a in c.ARMS},
        'all_attempt_costs':costs,'known_unknown_token_calls':sum(unknown),'unknown_token_calls':None if unmeasured else sum(unknown),
        'unmeasured_token_call_attempts':unmeasured,'all_attempt_token_usage_complete':bool(attempts) and not unmeasured and not sum(unknown)
            and all(v['terminal'].get('provider_token_usage_complete') is True for v in attempts),
        'token_cost_interpretation':'observed token totals are partial lower bounds when usage is unknown'}


def futile(outcomes):
    candidate=[v for v in outcomes if v['profile']=='N30']
    return bool(outcomes) and len(outcomes)%3==0 and len(candidate)*3==len(outcomes) and sum(v['success'] for v in candidate)+4-len(candidate)<3


def analyze(plan,events,acceptor):
    rows=plan['episodes'];keys=[x['episode_key'] for x in rows]
    w.require(len(rows)==12 and len(set(keys))==12 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(4) for a in c.ARMS],
        'N30 report matrix differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
    groups={}
    for e in local:
        w.require(e.get('episode_key') in keys,'N30 unknown journal cell')
        groups.setdefault(e['attempt_id'],[]).append(e)
    w.require(len(groups)<=12 and [g[0]['episode_key'] for g in groups.values()]==keys[:len(groups)]
        and local==[e for g in groups.values() for e in g] and not any(e.get('retry_of') for e in local),
        'N30 chronological untouched prefix/no retry differs')
    attempts=[];dispatch=0
    for aid,group in groups.items():
        w.require(group[0]['event']=='reserved' and group[-1]['event'] in {'valid','aborted'}
            and [e['event'] for e in group] in (['reserved','dispatched','valid'],['reserved','dispatched','aborted'],['reserved','aborted']),'N30 report unsettled or malformed journal')
        final=group[-1];row=rows[keys.index(final['episode_key'])]
        dispatch+=sum(e['event']=='dispatched' for e in group)
        attempts.append({'attempt_id':aid,'episode_key':row['episode_key'],'profile':row['profile'],'terminal':final})
    accepted=[];failure=None;seen=[];native_counts={a:{} for a in c.ARMS};aux={a:{} for a in c.ARMS}
    for row in rows:
        own=[g for g in groups.values() if g[0]['episode_key']==row['episode_key']]
        if not own:break
        try:cell,counts,cost=acceptor(row,local)
        except (ValueError,RuntimeError,OSError,KeyError,AssertionError) as exc:
            failure={'episode_key':row['episode_key'],'reason':str(exc),'failure_class':type(exc).__name__};break
        accepted.append(cell);seen.append(row['episode_key'])
        for k,v in counts.items():native_counts[row['profile']][k]=native_counts[row['profile']].get(k,0)+v
        for k,v in cost.items():aux[row['profile']][k]=aux[row['profile']].get(k,0)+v
        if len(accepted)%3==0 and futile(accepted):
            w.require(len(groups)==len(accepted),'N30 dispatch continued after numeric futility')
            break
    allowed=set(seen)|({rows[len(seen)]['episode_key']} if len(seen)<12 else set())
    w.require(all(e['episode_key'] in allowed for e in local),'N30 journal skips or continues past invalid cell')
    counts={a:{'audited':sum(v['profile']==a for v in accepted),'success':sum(v['profile']==a and v['success'] for v in accepted)} for a in c.ARMS}
    wins=counts['N30']['success'];complete=len(accepted)==12
    substantive=native_counts['N30'].get('guided_decisions',0)>0 and native_counts['N30'].get('parent_rounds_verified',0)>0 and native_counts['N30'].get('active_insertions_verified',0)>0
    promoted=complete and wins>=3 and wins>=max(counts[a]['success'] for a in ('C0','Q0')) and substantive
    decision=('ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promoted else 'REJECT_NUMERIC_DEV_FUTILITY' if failure is None and futile(accepted) else 'REJECT' if complete and failure is None else 'INVALID_OR_INTERRUPTED')
    return {'schema':'n30-dev-cohort-result-v1','cohort_id':c.COHORT,'source_commit':plan['source_commit'],
        'planned':12,'dispatched':dispatch,'audited_cells':len(accepted),'counts':counts,'accepted_cells':accepted,
        'attempts':attempts,'native':native_counts,'auxiliary':aux,'dev_gate_promoted':promoted,'decision':decision,
        'failure':failure,'goal_status':'TARGET_NOT_MET','validation_authorized':False,'formal_authorized':False,
        'unrun_candidate_tasks':4-counts['N30']['audited'],
        'mechanism_interpretation':'An inserted row need not be selected; actual progress is against its fixed previous target snapshot, not physical grasp or task benefit.',
        **summary(accepted,attempts)}


def write_terminal(plan_path,plan,status_path,root,r):
    try:status=w.read_ref(c.ref(status_path));status_ref=c.ref(status_path)
    except (OSError,ValueError,KeyError) as exc:
        status={'status':'unavailable','failure_class':type(exc).__name__};status_ref={'path':str(Path(status_path).resolve()),'sha256':None}
    events=r['read_events'](Path(root)/'data/attempt-ledger.jsonl')
    local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
    def accept(row,events):
        final=c.accepted_cell(plan,row,events,root,r);output=Path(final['output_dir'])
        report=c.read_worker_report(output,r);counts,aux=native.from_output(row['profile'],output,report,final.get('guided_chunks'))
        return {'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],
            'attempt_id':final['attempt_id'],'success':final['success'],'audit':c.ref(output/'eds_eval/decision-evidence-audit.json'),
            'worker_context':c.ref(output/'n23-worker-context.json'),'worker_receipt':c.ref(output/'eds_eval/in-worker-audit-receipt.json'),
            'attempt_result':c.ref(output/'attempt-result.json')},counts,aux
    result=analyze(plan,local,accept)
    journal_prefix=[x['episode_key'] for x in result['accepted_cells']]
    consistent=(status.get('completed_keys')==journal_prefix and status.get('dev_gate_promoted')==result['dev_gate_promoted'])
    phase=status.get('status')
    consistent=consistent and ((phase=='completed_all_twelve_audited' and result['audited_cells']==12)
        or (phase=='rejected_numeric_futility' and result['decision']=='REJECT_NUMERIC_DEV_FUTILITY')
        or (phase=='resource_budget_incomplete' and result['decision']=='INVALID_OR_INTERRUPTED' and result['failure'] is None)
        or (phase in {'failed','interrupted'} and result['decision']=='INVALID_OR_INTERRUPTED'))
    if consistent and phase=='resource_budget_incomplete':result['decision']='RESOURCE_BUDGET_INCOMPLETE'
    result['controller_evidence']={'completed_keys':status.get('completed_keys'),'journal_accepted_keys':journal_prefix,
        'consistent':consistent,'status_phase':phase}
    if not consistent:
        result['journal_reconstructed_disposition']=result['decision']
        result['decision']='INVALID_OR_INTERRUPTED';result['dev_gate_promoted']=False
        result['controller_evidence']['disagreement']='Controller status and independently reconstructed journal differ; no resume or promotion.'
    snapshot=c.RUN_DIR/'execution/terminal-ledger-v1.json';w.atomic_json(snapshot,local)
    result.update(plan=c.ref(plan_path),terminal_status={**status_ref,'content':status},ledger_snapshot=c.ref(snapshot),
        reader=c.ref(Path(root)/'scripts/qd_ed_n30_report.py'),source_bridge=c.ref(c.BRIDGE))
    w.atomic_json(c.RUN_DIR/'result-v1.json',result)
    return result
