#!/usr/bin/env python3
"""One external continuation of the untouched N23 v2 suffix, original worker only."""
from __future__ import annotations
from pathlib import Path
import signal
import n23_continuation_contract as x


def execute(plan,manifest,runtime,owned,prefix,*,boundary,write,events,accept=None,one_attempt=None):
    """Sequential controller; injectable I/O enables CPU-only composition tests."""
    sup=owned.sup;c=owned.c;w=owned.w;r=owned.r
    accept=x.acceptor(plan,manifest,owned) if accept is None else accept
    one_attempt=sup.one_attempt if one_attempt is None else one_attempt
    attempts=[];outcomes=[];completed=[];successes={a:0 for a in c.ARMS}
    native={'N7':{'guided_decisions':0,'parent_rounds_verified':0},
        'N23':{'guided_decisions':0,'parent_rounds_verified':0,**{k:0 for k in sup.NATIVE_FIELDS}}}
    auxiliary={k:0 for k in sup.AUX_FIELDS}
    def status(phase,**extra):
        write({'schema':'n23-dev-supervisor-status-continuation-v1','status':phase,'cohort_id':c.COHORT,
            'completed_keys':completed,'attempts':attempts,'outcomes':outcomes,'successes':successes,'native':native,
            'auxiliary':auxiliary,**sup.summarize(outcomes,attempts),'dev_gate_promoted':False,
            'timeout_observability':c.ref(c.OBSERVABILITY),'protected_authorized':False,**extra})
    def record(final,row):
        item=sup.attempt_record(final,row);attempts.append(item);status('attempt_journaled');return item
    def add(row,evidence):
        final,refs,counts,aux=evidence
        if row['profile'] in native:
            for k,v in counts.items():native[row['profile']][k]+=v
        for k,v in aux.items():auxiliary[k]+=v
        outcomes.append({'task_id':row['task_id'],'profile':row['profile'],'success':final['success'],
            'attempt_id':final['attempt_id'],'recovered':final.get('retry_of') is not None})
        successes[row['profile']]+=int(final['success'] is True);completed.append(row['episode_key'])
    x.require(len(prefix)==3,'only exact three-prefix continuation is allowed')
    for row,evidence in zip(plan['episodes'][:3],prefix):
        attempts.append(sup.attempt_record(evidence[0],row));add(row,evidence)
    status('started_with_three_reconstructed_cells')
    try:
        for row in plan['episodes'][3:]:
            boundary()
            result=one_attempt(x.PLAN,plan,row);item=record(result,row)
            if result.get('outcome_valid') is not True:
                eligibility=owned.recovery.create_eligibility(x.PLAN,plan,row,result,
                    manifest['profiles'][row['profile']],runtime,events(),owned.root,vars(r))
                x.require(item['unknown_token_calls']==1,'typed eligibility unknown-call count differs')
                item['timeout_diagnostic']=eligibility['diagnostic']
                path=c.RUN_DIR/'eligibility-v2'/f"{result['attempt_id']}.json"
                w.atomic_json(path,eligibility);item['typed_eligibility']=c.ref(path)
                status('primary_invalid_typed_recovery_eligible')
                boundary()
                result=one_attempt(x.PLAN,plan,row,eligibility=c.ref(path));record(result,row)
            evidence=accept(plan,row,events())
            x.require(evidence[0]['attempt_id']==result['attempt_id'],
                'accepted selection differs from first valid attempt')
            add(row,evidence);status('cell_audited')
            if row['profile']=='N23':
                remaining=10-len(completed)//4
                if successes['N23']+remaining<5:
                    status('rejected_numeric_futility',remaining_tasks=remaining,
                        maximum_possible_candidate_successes=successes['N23']+remaining);return
        promoted=(len(completed)==40 and successes['N23']>=5
            and successes['N23']>=max(successes[a] for a in c.ARMS[:-1])
            and native['N23']['guided_decisions']>0 and native['N23']['parent_rounds_verified']>0)
        status('completed_all_forty_audited',dev_gate_promoted=promoted,
            mechanism_caveat='Clipping counts are descriptive; zero clipping is not an additional promotion veto.')
    except BaseException as exc:
        status('interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',failure_class=type(exc).__name__)
        raise


def main():
    owned=x.load_owned();r=owned.r
    # This separate lock serializes the coordinator for its entire lifetime.
    # Original runner/state locks retain ownership of every actual admission.
    with r.locked(x.HERE/'execution/continuation-controller-v1.lock',nonblocking=True):
        with r.locked(owned.root/'data/qd-ed-runner.lock',nonblocking=True),r.locked(owned.root/'data/qd-ed-state.lock'):
            plan,manifest,runtime=r.validate_plan(x.PLAN,root=owned.root)
            authority,prefix=x.check_boundary(plan,manifest,owned,initial=True)
            seal={'schema':'n23-continuation-launch-seal-v1','authority':authority,
                'process':owned.w.process_identity(),'prefix_attempt_ids':list(x.PREFIX_IDS),
                'pending_keys':[v['episode_key'] for v in plan['episodes'][3:]]}
            owned.w.atomic_json(x.SEAL,seal)
        provenance={'authority':authority,'launch_seal':x.ref(x.SEAL),'original_failed_review':x.ref(x.FAILURE),
            'original_source_commit':x.SOURCE,'original_plan':x.ref(x.PLAN),
            'external_source':x.source_record(),'imported_writer':x.ref(x.WRITER)}
        def write(value):r.durable_json(x.STATUS,{**value,'continuation':provenance})
        def boundary():
            with r.locked(owned.root/'data/qd-ed-runner.lock',nonblocking=True),r.locked(owned.root/'data/qd-ed-state.lock'):
                x.check_boundary(plan,manifest,owned,initial=False)
        execute(plan,manifest,runtime,owned,prefix,boundary=boundary,write=write,
            events=lambda:r.read_events(owned.root/'data/attempt-ledger.jsonl'))


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    main()
