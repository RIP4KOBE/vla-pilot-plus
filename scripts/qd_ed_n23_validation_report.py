"""Full protected evidence on disk; only aggregate disposition may steer later work."""
from pathlib import Path
from scripts import qd_ed_n23_validation_contract as c
from scripts import qd_ed_n23_v2_supervise as dev_reporting
from scripts import qd_ed_final_runner as runner


def summarize(plan,events,root,r,*,force_invalid=False):
    local=[v for v in events if v.get('identity',{}).get('iteration')==c.COHORT]
    known={v['episode_key'] for v in plan['episodes']}
    c.require(all(v.get('episode_key') in known for v in local),'validation out-of-matrix journal entry')
    groups=r['event_groups'](local);attempts=[];cells=[];outcomes=[];active=0;invalid=force_invalid
    for row in plan['episodes']:
        own=[g for g in groups.values() if g[0].get('episode_key')==row['episode_key']]
        for group in own:
            attempts.append(dev_reporting.attempt_record(group[-1],row))
        final=None;native=None;error=None
        if own:
            try:
                final=c.accepted_cell(plan,row,events,root,r)
                native=c.read_worker_report(final['output_dir'],r)
                if row['profile']=='N23':active+=final['guided_chunks']
            except (ValueError,RuntimeError,KeyError,OSError,TypeError) as exc:
                invalid=True;error=type(exc).__name__
        if final is not None:
            outcomes.append({'task_id':(row['seed_block'],row['task_id']),'profile':row['profile'],
                'success':final['success'],'attempt_id':final['attempt_id'],'recovered':bool(final.get('retry_of'))})
        cells.append({**row,'accepted_attempt_id':final['attempt_id'] if final else None,
            'success':final['success'] if final else None,'status':'accepted_native' if final else 'invalid' if own else 'not_run',
            'attempts':[g for g in own],'native_report':c.ref(Path(final['output_dir'])/'eds_eval/decision-evidence-audit.json') if final else None,
            'adjudication_error_class':error})
    # Reuse cost arithmetic with compound task keys; blocks must never collapse.
    sums=dev_reporting.summarize(outcomes,attempts)
    for key in ('accepted_cell_denominators','primary_attempt_denominators','all_attempt_denominators','all_attempt_costs'):
        sums[key]={a:sums[key][a] for a in c.ARMS}
    sums['matched_comparisons']={a:sums['matched_comparisons'][a] for a in ('C0','Q0')}
    sums.pop('dependent_exposed_dev_reuse')
    counts={a:sum(v['success'] is True for v in outcomes if v['profile']==a) for a in c.ARMS}
    full=len(outcomes)==60 and len(plan['episodes'])==60 and not invalid
    promoted=full and active>0 and counts['N23']>=10 and counts['N23']>=max(counts['C0'],counts['Q0'])
    decision='PROMOTE' if promoted else 'REJECT' if full else 'INVALID' if invalid else 'INCOMPLETE'
    detail={'schema':'n23-protected-validation-detail-v1','cohort_id':c.COHORT,
        'seed_cohort':plan['n23_validation']['seed_cohort'],'plan':c.ref(c.VALIDATION_PLAN),
        'source_commit':plan['source_commit'],'source_bridge':plan['n23_validation']['source_bridge'],
        'backend_proof':plan['n23_validation']['backend_proof'],'cells':cells,'attempts':attempts,
        'dispatched':sum(v['event']=='dispatched' for v in local),'recoveries':len({v['attempt_id'] for v in local if v.get('retry_of')}),
        'accepted_cells':len(outcomes),'success_counts':counts,'decision':decision,**sums,
        'native_guided_decisions':active,'same_layout_seed_robustness':True,'new_layout_generalization':False,
        'metadata_selection':plan['n23_validation']['metadata_selection'],'formal_authorized':False}
    aggregate={'schema':'n23-validation-aggregate-disposition-v1','cohort_id':c.COHORT,
        'aggregate_only':True,'terminal':decision!='INCOMPLETE','gate_passed':bool(promoted),
        'outcome_valid':bool(full),'dev_promoted':True,'decision':decision,'formal_authorized':False}
    return detail,aggregate


def write_reports(plan,events,directory,root,r,*,force_invalid=False):
    directory=r['owned'](directory,plan['artifact_root']);directory.mkdir(parents=True,exist_ok=True)
    try:detail,aggregate=summarize(plan,events,root,r,force_invalid=force_invalid)
    except (ValueError,RuntimeError,KeyError,TypeError,OSError) as exc:
        r['durable_json'](directory/'protected-unadjudicated-evidence.json',{'failure_class':type(exc).__name__,
            'planned_rows':plan['episodes'],'events':[v for v in events if v.get('identity',{}).get('iteration')==c.COHORT]})
        aggregate={'schema':'n23-validation-aggregate-disposition-v1','cohort_id':c.COHORT,'aggregate_only':True,
            'terminal':True,'gate_passed':False,'outcome_valid':False,'dev_promoted':True,'decision':'INVALID','formal_authorized':False}
        r['durable_json'](directory/'aggregate-disposition.json',aggregate)
        raise
    r['durable_json'](directory/'protected-detail.json',detail)
    r['durable_json'](directory/'aggregate-disposition.json',aggregate)
    return aggregate
