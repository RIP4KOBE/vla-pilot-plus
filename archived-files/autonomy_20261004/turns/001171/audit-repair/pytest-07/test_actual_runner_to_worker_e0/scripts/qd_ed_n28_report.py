"""Immutable N28 terminal reconstruction from its own journal and metered receipts."""
import math
from pathlib import Path
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n28_contract as c
from scripts import qd_ed_n28_native as native
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
        matched=set(by['N28'])&set(by[a]);pairs[a]={'denominator':len(matched),
            'gains':sum(by['N28'][t] and not by[a][t] for t in matched),
            'losses':sum(not by['N28'][t] and by[a][t] for t in matched)}
    return {'accepted_cell_denominators':{a:len(v) for a,v in by.items()},'matched_comparisons':pairs,
        'primary_attempt_denominators':{a:sum(v['profile']==a and not v['terminal'].get('retry_of') for v in attempts) for a in c.ARMS},
        'all_attempt_denominators':{a:sum(v['profile']==a for v in attempts) for a in c.ARMS},
        'all_attempt_costs':costs,'known_unknown_token_calls':sum(unknown),'unknown_token_calls':None if unmeasured else sum(unknown),
        'unmeasured_token_call_attempts':unmeasured,'all_attempt_token_usage_complete':bool(attempts) and not unmeasured and not sum(unknown)
            and all(v['terminal'].get('provider_token_usage_complete') is True for v in attempts),
        'token_cost_interpretation':'observed token totals are partial lower bounds when usage is unknown'}


def analyze(plan,events,acceptor):
    rows=plan['episodes'];keys=[x['episode_key'] for x in rows]
    w.require(len(rows)==16 and len(set(keys))==16 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(4) for a in c.ARMS],
        'N28 report matrix differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
    groups={}
    for e in local:
        w.require(e.get('episode_key') in keys,'N28 unknown journal cell')
        groups.setdefault(e['attempt_id'],[]).append(e)
    w.require(len(groups)<=16 and [g[0]['episode_key'] for g in groups.values()]==keys[:len(groups)]
        and local==[e for g in groups.values() for e in g] and not any(e.get('retry_of') for e in local),
        'N28 chronological untouched prefix/no retry differs')
    attempts=[];dispatch=0
    for aid,group in groups.items():
        w.require(group[0]['event']=='reserved' and group[-1]['event'] in {'valid','aborted'}
            and [e['event'] for e in group] in (['reserved','dispatched','valid'],['reserved','dispatched','aborted'],['reserved','aborted']),'N28 report unsettled or malformed journal')
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
    allowed=set(seen)|({rows[len(seen)]['episode_key']} if len(seen)<16 else set())
    w.require(all(e['episode_key'] in allowed for e in local),'N28 journal skips or continues past invalid cell')
    counts={a:{'audited':sum(v['profile']==a for v in accepted),'success':sum(v['profile']==a and v['success'] for v in accepted)} for a in c.ARMS}
    wins=counts['N28']['success'];complete=len(accepted)==16
    substantive=native_counts['N28'].get('guided_decisions',0)>0 and native_counts['N28'].get('parent_rounds_verified',0)>0
    promoted=complete and wins>=2 and wins>=max(counts[a]['success'] for a in c.ARMS[:-1]) and wins>counts['N27']['success'] and substantive
    decision=('ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV' if promoted else 'REJECT_SCREEN' if complete and failure is None else 'INVALID_OR_INTERRUPTED')
    return {'schema':'n28-dev-cohort-result-v1','cohort_id':c.COHORT,'source_commit':plan['source_commit'],
        'planned':16,'dispatched':dispatch,'audited_cells':len(accepted),'counts':counts,'accepted_cells':accepted,
        'attempts':attempts,'native':native_counts,'auxiliary':aux,'dev_gate_promoted':promoted,'decision':decision,
        'failure':failure,'goal_status':'TARGET_NOT_MET','validation_authorized':False,'formal_authorized':False,
        'mechanism_interpretation':'parent alpha, clipping and zero-gradient counts are descriptive, never an activity promotion veto',
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
    consistent=consistent and ((phase=='completed_all_sixteen_audited' and result['audited_cells']==16)
        or (phase in {'failed','interrupted'} and result['decision']=='INVALID_OR_INTERRUPTED'))
    result['controller_evidence']={'completed_keys':status.get('completed_keys'),'journal_accepted_keys':journal_prefix,
        'consistent':consistent,'status_phase':phase}
    if not consistent:
        result['journal_reconstructed_disposition']=result['decision']
        result['decision']='INVALID_OR_INTERRUPTED';result['dev_gate_promoted']=False
        result['controller_evidence']['disagreement']='Controller status and independently reconstructed journal differ; no resume or promotion.'
    snapshot=c.RUN_DIR/'execution/terminal-ledger-v1.json';w.atomic_json(snapshot,local)
    result.update(plan=c.ref(plan_path),terminal_status={**status_ref,'content':status},ledger_snapshot=c.ref(snapshot),
        reader=c.ref(Path(root)/'scripts/qd_ed_n28_report.py'),source_bridge=c.ref(c.BRIDGE))
    w.atomic_json(c.RUN_DIR/'result-v1.json',result)
    return result
