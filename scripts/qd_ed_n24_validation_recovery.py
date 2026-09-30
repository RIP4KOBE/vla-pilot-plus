"""One validation recovery per cell, two total; exact frozen N24 timeout diagnostic."""
from pathlib import Path
from scripts import qd_ed_n24_validation_contract as c
from scripts import qd_ed_n24_recovery as original
from scripts import qd_ed_n24_native as native
from scripts import qd_ed_n23_worker as w
KEY='n24_validation_recovery_eligibility'


def check_cell_history(events,row,primary_id,r,*,historical=False):
    cohort=c.dev.COHORT if historical else c.COHORT
    local=[e for e in events if e.get('identity',{}).get('iteration')==cohort]
    groups=r['event_groups'](local);own=[g for g in groups.values() if g[0]['episode_key']==row['episode_key']]
    w.require(len(own)==1 and own[0][0]['attempt_id']==primary_id
        and [e['event'] for e in own[0]]==['reserved','dispatched','valid']
        and own[0][-1].get('outcome_valid') is False and all(e.get('retry_of') is None for e in own[0])
        and own[0][0]['identity']==r['episode_identity'](row),'N24 validation recovery primary differs')
    w.require(len({e['attempt_id'] for e in local if e.get('retry_of')})<2,'N24 validation recovery cap consumed')
    return own[0][-1]


def create_eligibility(plan_path,plan,row,final,profile,runtime,events,root,r,*,historical=False):
    cohort=c.dev.COHORT if historical else c.COHORT
    w.require(row in plan['episodes'] and row['iteration']==cohort
        and check_cell_history(events,row,final['attempt_id'],r,historical=historical)==final,'N24 validation recovery row/journal differs')
    original.terminal_binding(final,row,plan,c.ref(plan_path),r)
    output=Path(final['output_dir']);terminal=c.ref(output/'attempt-result.json')
    w.require(w.read_ref(terminal)==final and final.get('n23_worker_receipt')==c.ref(output/'eds_eval/in-worker-audit-receipt.json'),
        'N24 validation primary terminal/receipt differs')
    if historical:
        from scripts import qd_ed_n24_validation_evidence as evidence
        report=evidence.historical_receipt(final,row,plan,c.ref(plan_path),r)
    else:report=c.read_worker_report(output,r)
    w.require(type(final.get('guided_chunks')) is int,'N24 validation guided telemetry missing')
    native.from_output(row['profile'],output,report,final['guided_chunks'])
    diagnostic=original.diagnose(final,row,profile,runtime,r,report)
    return {'schema':'n24-typed-timeout-eligibility-v1' if historical else 'n24-validation-typed-timeout-eligibility-v1',
        'cohort_id':cohort,'primary_attempt_id':final['attempt_id'],'episode_key':row['episode_key'],'scientific_row':row,
        'plan':c.ref(plan_path),'source_commit':plan['source_commit'],'protocol':c.ref(c.dev.PROTOCOL if historical else c.PROTOCOL),
        'timeout_observability':c.ref(c.dev.OBSERVABILITY),'terminal':terminal,
        'native_receipt':c.ref(output/'eds_eval/in-worker-audit-receipt.json'),'native_report':c.ref(output/'eds_eval/decision-evidence-audit.json'),
        'process':c.ref(output/'process.json'),'evidence_files':diagnostic['evidence_files'],'diagnostic':diagnostic,
        'evidence_packaging_reader':c.ref(original.__file__),
        'evidence_packaging_mode':'unchanged_original_reader' if (output/'eds_eval/eds_metrics.jsonl').exists() else 'n24_absent_zero_guided_private_reader',
        'primary_outcome_valid':False,'unknown_token_calls':1,'retry_budget_bucket':'recovery','same_cell_max_recoveries':1}


def verify_eligibility(reference,plan,row,events,root,r,*,historical=False):
    record=w.read_ref(reference);cohort=c.dev.COHORT if historical else c.COHORT
    w.require(record.get('schema')==('n24-typed-timeout-eligibility-v1' if historical else 'n24-validation-typed-timeout-eligibility-v1')
        and record.get('cohort_id')==cohort and record.get('scientific_row')==row and record.get('episode_key')==row['episode_key']
        and record.get('source_commit')==plan['source_commit'] and w.read_ref(record['plan'])==plan,'N24 validation eligibility source/plan differs')
    final=check_cell_history(events,row,record['primary_attempt_id'],r,historical=historical)
    profiles=c.manifest(plan,r);runtime=w.read_ref({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']})
    rebuilt=create_eligibility(record['plan']['path'],plan,row,final,profiles['profiles'][row['profile']],runtime,events,root,r,historical=historical)
    w.require(record==rebuilt,'N24 validation typed evidence changed/non-derivative fault')
    return record


def check_retry(events,row,r):
    record=w.read_ref(row[KEY]);plan=w.read_ref(record['plan']);primary=c.primary_row(plan,row)
    w.require(row.get('retry_of')==record['primary_attempt_id'] and row['budget_bucket']=='recovery','N24 validation retry lineage differs')
    verify_eligibility(row[KEY],plan,primary,events,Path(plan['worktree']),r)


def selected_terminal(plan,row,events,root,r,*,historical=False):
    cohort=c.dev.COHORT if historical else c.COHORT
    groups=list(r['event_groups']([e for e in events if e.get('identity',{}).get('iteration')==cohort
        and e.get('episode_key')==row['episode_key']]).values())
    w.require(1<=len(groups)<=2 and [e['event'] for e in groups[0]]==['reserved','dispatched','valid']
        and all(e.get('retry_of') is None for e in groups[0]),'N24 validation primary interrupted/duplicate')
    final=groups[0][-1]
    if len(groups)==2:
        key='n24_recovery_eligibility' if historical else KEY
        primary=final;final=groups[1][-1];reference=groups[1][0].get(key)
        w.require([e['event'] for e in groups[1]]==['reserved','dispatched','valid'] and primary.get('outcome_valid') is False
            and final.get('retry_of')==primary['attempt_id'] and final.get('budget_bucket')=='recovery' and reference is not None
            and all(e.get(key)==reference and e.get('retry_of')==primary['attempt_id'] for e in groups[1]),'N24 validation recovery linkage differs')
        boundary=next(i for i,e in enumerate(events) if e['attempt_id']==final['attempt_id'])
        verify_eligibility(reference,plan,row,events[:boundary],root,r,historical=historical)
    w.require(final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True and type(final.get('success')) is bool,
        'N24 validation no first valid outcome')
    original.terminal_binding(final,row,plan,c.ref(c.DEV_PLAN if historical else c.VALIDATION_PLAN),r)
    output=Path(final['output_dir']);context=w.read_ref(c.ref(output/'n23-worker-context.json'))
    w.require(w.read_ref(c.ref(output/'attempt-result.json'))==final
        and final.get('n23_worker_receipt')==c.ref(output/'eds_eval/in-worker-audit-receipt.json')
        and c.same_ref(context['plan'],c.ref(c.DEV_PLAN if historical else c.VALIDATION_PLAN))
        and w.read_ref(context['plan'])==plan,'N24 validation terminal/plan/receipt artifact differs')
    return final


def historical_dev_cell(plan,row,events,root,r):return selected_terminal(plan,row,events,root,r,historical=True)


def accepted_cell(plan,row,events,root,r):
    final=selected_terminal(plan,row,events,root,r)
    n=final.get('guided_chunks')
    w.require(type(n) is int and n>=0 and final.get('candidate_evaluations')==176*n and final.get('score_batches')==11*n,
        'N24 validation canonical denominator differs')
    report=c.read_worker_report(final['output_dir'],r)
    native.from_output(row['profile'],final['output_dir'],report,n)
    return final
