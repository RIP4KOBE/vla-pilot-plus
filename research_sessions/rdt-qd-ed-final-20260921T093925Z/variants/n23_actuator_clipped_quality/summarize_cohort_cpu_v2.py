"""Terminal N23 v2 report; CPU-only, preserve every attempt and first-valid cells."""
from __future__ import annotations
import datetime,json,math,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]/'study_worktree'
sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_supervise as sup
SOURCE='51104470983cdbafd08feb87f2f39b7553779405'
PLAN_SHA='acd2b2c639f7756cdc353b6a7eea8c93a4d735a8ce6ee25838d9502c938d07f0'
TERMINAL={'completed_all_forty_audited','rejected_numeric_futility','failed','interrupted'}
require=w.require

def analyze(plan,status,events,acceptor):
    require(status.get('status') in TERMINAL,'cohort not terminal')
    rows=plan['episodes'];expected={v['episode_key']:v for v in rows}
    require(len(rows)==len(expected)==40 and [(v['task_id'],v['profile']) for v in rows]
        ==[(t,a) for t in range(10) for a in c.ARMS],'frozen forty-cell matrix differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
    groups=r.event_groups(local)
    require(all(g[-1]['event'] in r.TERMINAL for g in groups.values()),'unsettled cohort attempt')
    finals=[g[-1] for g in groups.values()]
    require(all(v['episode_key'] in expected for v in finals),'unexpected scientific identity')
    primary=[g[0]['episode_key'] for g in groups.values() if not g[0].get('retry_of')]
    require(primary==list(expected)[:len(primary)],'primary order or duplicate differs')
    retries=[g for g in groups.values() if g[0].get('retry_of')]
    require(len(retries)<=2 and len(groups)<=42,'finite recovery/attempt limit exceeded')
    for group in retries:
        first=groups.get(group[0]['retry_of'])
        require(first and not first[0].get('retry_of') and first[-1].get('outcome_valid') is False
            and first[0]['episode_key']==group[0]['episode_key']
            and sum(g[0].get('retry_of')==first[0]['attempt_id'] for g in retries)==1
            and group[0]['budget_bucket']=='recovery','invalid recovery lineage')
    for v in finals:
        row=expected[v['episode_key']]
        require(v.get('identity')==r.episode_identity(row)
            and v.get('source_commit')==plan['source_commit'] and v.get('plan_sha256')==PLAN_SHA,
            'terminal/source/plan identity differs')
    attempts=[sup.attempt_record(v,expected[v['episode_key']]) for v in finals]
    completed=status.get('completed_keys',[])
    require(completed==list(expected)[:len(completed)],'accepted cells are not frozen prefix')
    accepted=[];outcomes=[];native={'N7':{'guided_decisions':0,'parent_rounds_verified':0},
        'N23':{'guided_decisions':0,'parent_rounds_verified':0,**{k:0 for k in sup.NATIVE_FIELDS}}}
    auxiliary={k:0 for k in sup.AUX_FIELDS}
    for key in completed:
        row=expected[key];final,refs,counts,aux=acceptor(plan,row,events)
        require(final==groups[final['attempt_id']][-1] and final['episode_key']==key
            and final['event']=='valid' and final.get('outcome_valid') is True
            and final.get('required_cost_telemetry_complete') is True and type(final.get('success')) is bool,
            'accepted cell not supported by exact terminal evidence')
        accepted.append({'episode_key':key,'task_id':row['task_id'],'profile':row['profile'],
            'attempt_id':final['attempt_id'],'success':final['success'],**refs})
        outcomes.append({'task_id':row['task_id'],'profile':row['profile'],'success':final['success'],
            'attempt_id':final['attempt_id'],'recovered':final.get('retry_of') is not None})
        if row['profile'] in native:
            for k,v in counts.items():native[row['profile']][k]+=v
        for k,v in aux.items():auxiliary[k]+=v
    require(outcomes==status.get('outcomes') and native==status.get('native'),'supervisor outcomes/native counters differ')
    require(set(auxiliary)==set(status.get('auxiliary',{})) and all(math.isclose(v,status['auxiliary'][k],
        rel_tol=1e-9,abs_tol=1e-8) for k,v in auxiliary.items()),'auxiliary counters differ')
    successes={a:sum(v['success'] for v in accepted if v['profile']==a) for a in c.ARMS}
    require(successes==status.get('successes'),'success totals differ')
    observed=status.get('attempts',[]);ids=[v['attempt_id'] for v in observed]
    require(ids==[v['attempt_id'] for v in attempts[:len(ids)]]
        and all(v['terminal']==groups[v['attempt_id']][-1] for v in observed),'supervisor attempt records differ')
    for k,v in sup.summarize(outcomes,observed).items():require(status.get(k)==v,'supervisor summary differs: '+k)
    complete=status['status']=='completed_all_forty_audited'
    futile=status['status']=='rejected_numeric_futility'
    if complete or futile:
        require(len(observed)==len(attempts) and len(completed)==len(primary)
            and all(g[-1].get('outcome_valid') is True for g in groups.values() if not any(x[0].get('retry_of')==g[0]['attempt_id'] for x in retries)),
            'scientific terminal has unaccepted or unreported attempts')
    if complete:require(len(accepted)==40,'complete status lacks forty accepted cells')
    if futile:
        remaining=10-len(accepted)//4
        require(len(accepted)%4==0 and successes['N23']+remaining<5
            and status.get('maximum_possible_candidate_successes')==successes['N23']+remaining,'futility arithmetic differs')
    promoted=(complete and len(accepted)==40 and successes['N23']>=5
        and successes['N23']>=max(successes[a] for a in c.ARMS[:-1])
        and native['N23']['guided_decisions']>0 and native['N23']['parent_rounds_verified']>0)
    require(status.get('dev_gate_promoted') is promoted,'promotion differs from frozen gate')
    summary=sup.summarize(outcomes,attempts)
    return {'schema':'n23-dev-cohort-result-v2','cohort_id':c.COHORT,'source_commit':plan['source_commit'],
        'planned':40,'dispatched':sum(any(e['event']=='dispatched' for e in g) for g in groups.values()),
        'audited_cells':len(accepted),'counts':{a:{'audited':sum(v['profile']==a for v in accepted),'success':successes[a]} for a in c.ARMS},
        'accepted_cells':accepted,'attempts':attempts,'native':native,'auxiliary':auxiliary,**summary,
        'charged_attempts_not_returned_to_supervisor':[v['attempt_id'] for v in attempts[len(ids):]],
        'gpu_process_wall_seconds':sum(v['terminal'].get('gpu_process_wall_seconds',0) or 0 for v in attempts),
        'dev_gate_promoted':promoted,'decision':'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promoted else
        'REJECT' if complete or futile else 'INVALID_OR_INTERRUPTED','goal_status':'TARGET_NOT_MET',
        'interpretation':'Exposed Dev reuse; first valid scientific cell only. All invalid and recovery costs retained. Unknown token usage stays partial. Mechanism counters do not establish task benefit; protected execution remains separately gated.'}

def actual_acceptor(plan,row,events):
    final=c.accepted_cell(plan,row,events,ROOT,vars(r))
    output=Path(final['output_dir']);report=c.read_worker_report(output,vars(r))
    counts,aux=sup.native_counts(final,row,report)
    refs={k:c.ref(output/p) for k,p in (
        ('audit','eds_eval/decision-evidence-audit.json'),('worker_context','n23-worker-context.json'),
        ('worker_receipt','eds_eval/in-worker-audit-receipt.json'),('attempt_result','attempt-result.json'))}
    require(w.read_ref(refs['attempt_result'])==final,'attempt result differs from private journal')
    return final,refs,counts,aux

def main():
    plan_path=HERE/'plan.frozen.v2.gpu7.json';status_path=HERE/'execution/supervisor-status-gpu7-v2.json'
    target=HERE/'result-v2.json';snapshot=HERE/'dev-terminal-ledger-snapshot-v2.jsonl'
    require(not target.exists(),'immutable result already exists')
    with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True),r.locked(ROOT/'data/qd-ed-state.lock'):
        require(c.sha(plan_path)==PLAN_SHA,'Dev plan differs')
        plan,_,_=r.validate_plan(plan_path,root=ROOT)
        require(plan['source_commit']==SOURCE,'Dev source differs')
        status=r.read_json(status_path);require(status.get('status') in TERMINAL,'cohort still active')
        events=r.read_events(ROOT/'data/attempt-ledger.jsonl')
        result=analyze(plan,status,events,actual_acceptor)
        local=[v for v in events if v.get('identity',{}).get('iteration')==c.COHORT]
        text=''.join(json.dumps(v,sort_keys=True,allow_nan=False)+'\n' for v in local)
        if snapshot.exists():require(snapshot.read_text()==text,'immutable cohort snapshot differs')
        else:snapshot.write_text(text)
        result.update(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            plan=c.ref(plan_path),terminal_status={**c.ref(status_path),'content':status},
            ledger_snapshot=c.ref(snapshot),backend_proof=plan['n23_cohort']['backend_proof'],reader=c.ref(__file__))
        w.atomic_json(target,result)
        print(json.dumps({'result':c.ref(target),'decision':result['decision'],'counts':result['counts'],
            'dispatched':result['dispatched'],'gpu_process_wall_seconds':result['gpu_process_wall_seconds']}))
if __name__=='__main__':main()

