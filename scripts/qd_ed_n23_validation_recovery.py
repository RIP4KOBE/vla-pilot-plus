"""Validation-only typed recovery; unchanged Dev diagnostic is a shared leaf."""
from pathlib import Path
from scripts import qd_ed_n23_validation_contract as c
from scripts import qd_ed_n23_v2_contract as dev
from scripts import qd_ed_n23_v2_recovery as original
from scripts import qd_ed_n23_worker as w

KEY='n23_validation_recovery_eligibility'


def check_cell_history(events,row,primary_id,r,*,cohort=c.COHORT):
    local=[v for v in events if v.get('identity',{}).get('iteration')==cohort]
    groups=r['event_groups'](local);own=[g for g in groups.values() if g[0].get('episode_key')==row['episode_key']]
    w.require(len(own)==1 and own[0][0]['attempt_id']==primary_id
        and [v['event'] for v in own[0]]==['reserved','dispatched','valid']
        and own[0][-1].get('outcome_valid') is False and all(v.get('retry_of') is None for v in own[0])
        and own[0][0]['identity']==r['episode_identity'](row),'validation recovery requires one completed invalid primary')
    w.require(len({v['attempt_id'] for v in local if v.get('retry_of')})<2,'validation two recovery slots consumed')
    return own[0][-1]


def create_eligibility(plan_path,plan,row,final,profile,runtime,events,root,r,*,historical_dev=False):
    cohort=dev.COHORT if historical_dev else c.COHORT
    w.require(row in plan['episodes'] and row['iteration']==cohort,'validation recovery row not primary')
    check_cell_history(events,row,final['attempt_id'],r,cohort=cohort)
    original.terminal_binding(final,row,plan,c.ref(plan_path),r)
    output=Path(final['output_dir']);terminal_ref=c.ref(output/'attempt-result.json')
    w.require(w.read_ref(terminal_ref)==final,'validation recovery terminal artifact differs')
    w.require(final.get('n23_worker_receipt')==c.ref(output/'eds_eval/in-worker-audit-receipt.json'),
        'validation recovery lacks metered native receipt')
    if historical_dev:
        from scripts import qd_ed_n23_validation_evidence as evidence
        report=evidence.historical_receipt(final,row,plan,c.ref(plan_path),r)
    else:report=c.read_worker_report(output,r)
    diagnostic=original.diagnose(final,row,profile,runtime,r,native_report=report)
    return {'schema':'n23-v2-typed-timeout-eligibility-v1' if historical_dev else 'n23-validation-typed-timeout-eligibility-v1',
        'cohort_id':cohort,'primary_attempt_id':final['attempt_id'],'episode_key':row['episode_key'],
        'scientific_row':row,'plan':c.ref(plan_path),'source_commit':plan['source_commit'],
        'protocol':c.ref(dev.PROTOCOL if historical_dev else c.PROTOCOL),'timeout_observability':c.ref(dev.OBSERVABILITY),
        'terminal':terminal_ref,'native_receipt':c.ref(output/'eds_eval/in-worker-audit-receipt.json'),
        'native_report':c.ref(output/'eds_eval/decision-evidence-audit.json'),'process':c.ref(output/'process.json'),
        'evidence_files':original.evidence_files(output),'diagnostic':diagnostic,'primary_outcome_valid':False,
        'unknown_token_calls':1,'retry_budget_bucket':'recovery','same_cell_max_recoveries':1}


def verify_eligibility(reference,plan,row,events,root,r,*,historical_dev=False):
    record=w.read_ref(reference);cohort=dev.COHORT if historical_dev else c.COHORT
    w.require(record.get('schema')==('n23-v2-typed-timeout-eligibility-v1' if historical_dev else 'n23-validation-typed-timeout-eligibility-v1')
        and record.get('cohort_id')==cohort and record.get('episode_key')==row['episode_key']
        and record.get('scientific_row')==row and record.get('source_commit')==plan['source_commit']
        and w.read_ref(record['plan'])==plan,'validation typed eligibility identity/source differs')
    final=check_cell_history(events,row,record['primary_attempt_id'],r,cohort=cohort)
    profiles=c.manifest(plan,r);runtime=w.read_ref({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']})
    rebuilt=create_eligibility(record['plan']['path'],plan,row,final,profiles['profiles'][row['profile']],runtime,events,root,r,
        historical_dev=historical_dev)
    w.require(record==rebuilt,'validation typed eligibility changed/non-derivative fault')
    return record


def check_retry(events,row,r):
    record=w.read_ref(row[KEY]);plan=w.read_ref(record['plan']);primary=c.primary_row(plan,row)
    w.require(row.get('retry_of')==record['primary_attempt_id'] and row['budget_bucket']=='recovery',
        'validation recovery link/bucket differs')
    verify_eligibility(row[KEY],plan,primary,events,Path(plan['worktree']),r)


def selected_terminal(plan,row,events,root,r,*,historical_dev=False):
    cohort=dev.COHORT if historical_dev else c.COHORT
    local=[v for v in events if v.get('identity',{}).get('iteration')==cohort and v.get('episode_key')==row['episode_key']]
    groups=list(r['event_groups'](local).values())
    w.require(1<=len(groups)<=2,'validation cell missing or repeated')
    primary=groups[0][-1]
    w.require([v['event'] for v in groups[0]]==['reserved','dispatched','valid']
        and all(not v.get('retry_of') for v in groups[0]),'validation primary incomplete/interrupted')
    final=primary
    if len(groups)==2:
        key='n23_v2_recovery_eligibility' if historical_dev else KEY
        final=groups[1][-1];reference=groups[1][0].get(key)
        w.require([v['event'] for v in groups[1]]==['reserved','dispatched','valid']
            and primary.get('outcome_valid') is False and final.get('retry_of')==primary['attempt_id']
            and final.get('budget_bucket')=='recovery' and reference is not None
            and all(v.get(key)==reference and v.get('retry_of')==primary['attempt_id'] for v in groups[1]),
            'validation recovery is not exact sole typed retry')
        boundary=next(i for i,v in enumerate(events) if v['attempt_id']==final['attempt_id'])
        verify_eligibility(reference,plan,row,events[:boundary],root,r,historical_dev=historical_dev)
    w.require(final.get('event')=='valid' and final.get('outcome_valid') is True
        and final.get('required_cost_telemetry_complete') is True and type(final.get('success')) is bool,
        'validation no first valid native scientific result')
    plan_ref=c.ref(c.DEV_PLAN if historical_dev else c.VALIDATION_PLAN)
    original.terminal_binding(final,row,plan,plan_ref,r)
    w.require(w.read_ref(c.ref(Path(final['output_dir'])/'attempt-result.json'))==final,
        'validation accepted terminal artifact differs')
    return final


def historical_dev_cell(plan,row,events,root,r):
    return selected_terminal(plan,row,events,root,r,historical_dev=True)


def accepted_cell(plan,row,events,root,r):
    from scripts import qd_ed_n23_v2_supervise as supervision
    final=selected_terminal(plan,row,events,root,r)
    report=c.read_worker_report(final['output_dir'],r)
    w.require(report.get('accepted') is True and report.get('evidence_complete') is True,'validation native audit missing')
    n=final.get('guided_chunks')
    w.require(type(n) is int and n>=0 and final.get('candidate_evaluations')==176*n
        and final.get('score_batches')==11*n,'validation canonical count differs')
    supervision.native_counts(final,row,report)
    return final
