"""Immutable protected evidence; independent aggregate disposition only for steering."""
from pathlib import Path
from scripts import qd_ed_n24_validation_contract as c
from scripts import qd_ed_n24_report as dev_reporting
from scripts import qd_ed_n24_native as native
from scripts import qd_ed_n23_worker as w


def output_directory(directory,r):
    """Controller evidence belongs to the fixed variant directory, not attempt storage."""
    path=r['owned'](directory,c.RUN_DIR)
    c.require(path==(c.RUN_DIR/'validation-execution').resolve(),'N24 exact validation controller directory differs')
    return path


def summarize(plan,events,root,r,*,force_invalid=False,controller_completed=None):
    local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
    keys=[x['episode_key'] for x in plan['episodes']]
    c.require(len(keys)==len(set(keys))==60 and all(e.get('episode_key') in keys for e in local),'N24 validation report matrix differs')
    groups=r['event_groups'](local);attempts=[];cells=[];outcomes=[];invalid=force_invalid
    native_totals={a:{} for a in c.ARMS};auxiliary={a:{} for a in c.ARMS};prefix=[];closed=False
    for row in plan['episodes']:
        own=[g for g in groups.values() if g[0]['episode_key']==row['episode_key']]
        for g in own:
            c.require(g[-1]['event'] in r['TERMINAL'],'N24 validation report unfinished attempt')
            attempts.append({'attempt_id':g[-1]['attempt_id'],'episode_key':row['episode_key'],'profile':row['profile'],'terminal':g[-1]})
        final=None;error=None
        if own:
            if closed:invalid=True;error='journal_outside_first_valid_prefix'
            else:
                try:
                    final=c.accepted_cell(plan,row,local,root,r)
                    counts,aux=native.from_output(row['profile'],final['output_dir'],c.read_worker_report(final['output_dir'],r),final['guided_chunks'])
                    for k,v in counts.items():native_totals[row['profile']][k]=native_totals[row['profile']].get(k,0)+v
                    for k,v in aux.items():auxiliary[row['profile']][k]=auxiliary[row['profile']].get(k,0)+v
                except (ValueError,RuntimeError,KeyError,OSError,TypeError) as exc:invalid=True;error=type(exc).__name__;final=None
        if final is None:closed=True
        else:
            prefix.append(row['episode_key'])
            outcomes.append({'task_id':(row['seed_block'],row['task_id']),'profile':row['profile'],'success':final['success'],
                'attempt_id':final['attempt_id'],'recovered':bool(final.get('retry_of'))})
        cells.append({**row,'accepted_attempt_id':final['attempt_id'] if final else None,'success':final['success'] if final else None,
            'status':'accepted_native' if final else 'invalid' if own else 'not_run','attempts':own,'adjudication_error_class':error,
            'audit':c.ref(Path(final['output_dir'])/'eds_eval/decision-evidence-audit.json') if final else None,
            'receipt':c.ref(Path(final['output_dir'])/'eds_eval/in-worker-audit-receipt.json') if final else None})
    if controller_completed is not None and controller_completed!=len(prefix):invalid=True
    summary=dev_reporting.summary(outcomes,attempts)
    for field in ('accepted_cell_denominators','primary_attempt_denominators','all_attempt_denominators','all_attempt_costs'):
        summary[field]={a:summary[field][a] for a in c.ARMS}
    summary['matched_comparisons']={a:summary['matched_comparisons'][a] for a in ('C0','Q0')}
    counts={a:sum(x['success'] is True for x in outcomes if x['profile']==a) for a in c.ARMS}
    full=len(prefix)==60 and not invalid
    active=native_totals['N24'].get('guided_decisions',0)>0 and native_totals['N24'].get('parent_rounds_verified',0)>0
    promoted=full and active and counts['N24']>=10 and counts['N24']>=max(counts[a] for a in ('C0','Q0'))
    decision='PROMOTE' if promoted else 'REJECT' if full else 'INVALID' if invalid else 'INCOMPLETE'
    detail={'schema':'n24-protected-validation-detail-v1','cohort_id':c.COHORT,'seed_cohort':plan['n24_validation']['seed_cohort'],
        'plan':c.ref(c.VALIDATION_PLAN),'source_commit':plan['source_commit'],'source_bridge':plan['n24_validation']['source_bridge'],
        'dev_review':plan['n24_validation']['dev_review'],'cells':cells,'attempts':attempts,'native':native_totals,'auxiliary':auxiliary,
        'dispatched':sum(e['event']=='dispatched' for e in local),'recoveries':len({e['attempt_id'] for e in local if e.get('retry_of')}),
        'accepted_cells':len(prefix),'success_counts':counts,'decision':decision,'controller_completed':controller_completed,
        'journal_accepted_keys':prefix,'metadata_selection':plan['n24_validation']['metadata_selection'],
        'same_layout_seed_robustness':True,'new_layout_generalization':False,'formal_authorized':False,**summary}
    aggregate={'schema':'n24-validation-aggregate-disposition-v1','cohort_id':c.COHORT,'aggregate_only':True,
        'terminal':decision!='INCOMPLETE','outcome_valid':bool(full),'gate_passed':bool(promoted),'decision':decision,
        'dev_promoted':True,'formal_authorized':False,'goal_status':'TARGET_NOT_MET'}
    return detail,aggregate


def write_reports(plan,events,directory,root,r,*,force_invalid=False,controller_completed=None):
    directory=output_directory(directory,r);directory.mkdir(parents=True,exist_ok=True)
    try:detail,aggregate=summarize(plan,events,root,r,force_invalid=force_invalid,controller_completed=controller_completed)
    except (ValueError,RuntimeError,KeyError,OSError,TypeError) as exc:
        detail={'schema':'n24-protected-validation-unadjudicated-v1','failure_class':type(exc).__name__,
            'planned_rows':plan['episodes'],'events':[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]}
        aggregate={'schema':'n24-validation-aggregate-disposition-v1','cohort_id':c.COHORT,'aggregate_only':True,
            'terminal':True,'outcome_valid':False,'gate_passed':False,'decision':'INVALID','dev_promoted':True,
            'formal_authorized':False,'goal_status':'TARGET_NOT_MET'}
    w.atomic_json(directory/'protected-detail-v1.json',detail)
    w.atomic_json(directory/'aggregate-disposition-v1.json',aggregate)
    return aggregate
