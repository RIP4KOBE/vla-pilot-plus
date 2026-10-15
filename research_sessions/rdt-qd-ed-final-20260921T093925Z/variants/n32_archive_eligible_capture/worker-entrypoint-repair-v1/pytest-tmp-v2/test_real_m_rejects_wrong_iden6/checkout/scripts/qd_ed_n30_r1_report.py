"""Combined logical result, with original INVALID and every charge preserved."""
from pathlib import Path
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n30_r1_contract as c
from scripts import qd_ed_n30_r1_bridge as b
from scripts import qd_ed_n30_native as native
from scripts.qd_ed_n30_report import summary,futile


def historical_attempts(h):
    return [{'attempt_id':g[-1]['attempt_id'],'episode_key':g[-1]['episode_key'],'profile':g[-1]['identity']['profile'],
        'terminal':g[-1],'inherited_cost':True} for g in b.group(h['events'])]


def analyze(plan,events,h,acceptor):
    rows=plan['episodes'];w.require(rows==c.expected_rows(h),'r1 report fixed matrix')
    b.current_subset(h,events);keys=[x['episode_key'] for x in rows]
    local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT];groups=b.group(local)
    w.require(len(groups)<=10 and local==sum(groups,[]) and [g[0]['episode_key'] for g in groups]==keys[:len(groups)],'r1 chronological prefix')
    attempts=historical_attempts(h);dispatched=0
    for row,g in zip(rows,groups):
        w.require([e['event'] for e in g] in (['reserved','dispatched','valid'],['reserved','dispatched','aborted'],['reserved','aborted'])
            and all(e['episode_key']==row['episode_key'] and e.get('retry_of')==row.get('retry_of') for e in g),'r1 settled journal/retry')
        final=g[-1];dispatched+=sum(e['event']=='dispatched' for e in g)
        attempts.append({'attempt_id':final['attempt_id'],'episode_key':row['episode_key'],'profile':row['profile'],'terminal':final,'inherited_cost':False})
    accepted=[x['cell'] for x in h['imports']];failure=None;native_totals={a:{} for a in c.ARMS};aux={a:{} for a in c.ARMS}
    def add(arm,counts,cost):
        for k,v in counts.items():native_totals[arm][k]=native_totals[arm].get(k,0)+v
        for k,v in cost.items():aux[arm][k]=aux[arm].get(k,0)+v
    for x in h['imports']:add(x['cell']['profile'],x['native'],x['auxiliary'])
    for row,g in zip(rows,groups):
        try:cell,counts,cost=acceptor(row,events)
        except (OSError,ValueError,RuntimeError,KeyError,AssertionError) as exc:
            failure={'episode_key':row['episode_key'],'failure_class':type(exc).__name__,'reason':str(exc)};break
        w.require(cell['episode_key']==row['episode_key'] and cell['task_id']==row['task_id'] and cell['profile']==row['profile']
            and cell['attempt_id']==g[-1]['attempt_id'] and type(cell['success']) is bool,'r1 accepted mapping')
        accepted.append(cell);add(row['profile'],counts,cost)
        if futile(accepted):
            w.require(len(groups)==len(accepted)-2,'r1 dispatch after futility');break
    w.require(len(groups)<=len(accepted)-2+(failure is not None),'r1 dispatch past invalid')
    counts={a:{'audited':sum(v['profile']==a for v in accepted),'success':sum(v['profile']==a and v['success'] for v in accepted)} for a in c.ARMS}
    complete=len(accepted)==12;wins=counts['N30']['success']
    substantive=all(native_totals['N30'].get(k,0)>0 for k in ('guided_decisions','parent_rounds_verified','active_insertions_verified'))
    promoted=complete and failure is None and wins>=3 and wins>=max(counts[a]['success'] for a in ('C0','Q0')) and substantive
    decision=('ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promoted else 'REJECT_NUMERIC_DEV_FUTILITY' if failure is None and futile(accepted) else 'REJECT' if complete and failure is None else 'INVALID_OR_INTERRUPTED')
    return {'schema':'n30-r1-combined-result-v1','cohort_id':c.COHORT,'source_commit':plan['source_commit'],
        'original_cohort_id':b.OLD,'original_source_commit':b.OLD_SOURCE,'original_disposition':'INVALID_OR_INTERRUPTED',
        'original_invalid_attempt':b.FAILED,'planned_logical_cells':12,'planned_new_cells':10,
        'new_dispatched':dispatched,'all_dispatched':3+dispatched,'audited_cells':len(accepted),'inherited_cells':2,
        'accepted_cells':accepted,'attempts':attempts,'counts':counts,'native':native_totals,'auxiliary':aux,
        'decision':decision,'dev_gate_promoted':promoted,'failure':failure,'goal_status':'TARGET_NOT_MET',
        'validation_authorized':False,'formal_authorized':False,**summary(accepted,attempts)}


def write_terminal(plan_path,plan,status_path,root,r):
    try:status=w.read_ref(c.ref(status_path));status_ref=c.ref(status_path)
    except (OSError,ValueError,KeyError) as exc:
        status={'status':'unavailable','failure_class':type(exc).__name__};status_ref={'path':str(Path(status_path).resolve()),'sha256':None}
    h=c.history();events=r['read_events'](Path(root)/'data/attempt-ledger.jsonl')
    def accept(row,events):
        final=c.accepted_cell(plan,row,events,root,r);out=Path(final['output_dir'])
        counts,aux=native.from_output(row['profile'],out,c.read_worker_report(out,r),final['guided_chunks'])
        cell={'episode_key':row['episode_key'],'original_episode_key':row['original_episode_key'],'task_id':row['task_id'],'profile':row['profile'],
            'attempt_id':final['attempt_id'],'success':final['success'],'source_commit':plan['source_commit'],'inherited':False,
            'audit':c.ref(out/'eds_eval/decision-evidence-audit.json'),'worker_context':c.ref(out/'n23-worker-context.json'),
            'worker_receipt':c.ref(out/'eds_eval/in-worker-audit-receipt.json'),'attempt_result':c.ref(out/'attempt-result.json')}
        return cell,counts,aux
    result=analyze(plan,events,h,accept);keys=[v['episode_key'] for v in result['accepted_cells']];phase=status.get('status')
    consistent=status.get('completed_keys')==keys and status.get('dev_gate_promoted')==result['dev_gate_promoted']
    consistent=consistent and ((phase=='completed_all_twelve_audited' and result['audited_cells']==12)
        or (phase=='rejected_numeric_futility' and result['decision']=='REJECT_NUMERIC_DEV_FUTILITY')
        or (phase=='resource_budget_incomplete' and result['decision']=='INVALID_OR_INTERRUPTED' and result['failure'] is None)
        or (phase in {'failed','interrupted'} and result['decision']=='INVALID_OR_INTERRUPTED'))
    result['controller_evidence']={'completed_keys':status.get('completed_keys'),'journal_accepted_keys':keys,'consistent':consistent,'status_phase':phase}
    if consistent and phase=='resource_budget_incomplete':result['decision']='RESOURCE_BUDGET_INCOMPLETE'
    if not consistent:
        result['journal_reconstructed_disposition']=result['decision'];result['decision']='INVALID_OR_INTERRUPTED';result['dev_gate_promoted']=False
    snapshot=c.RUN_DIR/'execution/terminal-ledger-v1.json'
    w.atomic_json(snapshot,[e for e in events if e.get('identity',{}).get('iteration') in {b.OLD,c.COHORT}])
    result.update(plan=c.ref(plan_path),terminal_status={**status_ref,'content':status},ledger_snapshot=c.ref(snapshot),
        reader=c.ref(Path(root)/'scripts/qd_ed_n30_r1_report.py'),source_bridge=c.ref(c.BRIDGE))
    w.atomic_json(c.RUN_DIR/'result-v1.json',result);return result
