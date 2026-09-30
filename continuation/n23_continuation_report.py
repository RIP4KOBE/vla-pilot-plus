#!/usr/bin/env python3
"""New immutable terminal result; preserve the failed v2 result and all old costs."""
from __future__ import annotations
import datetime
import json
import n23_continuation_contract as x


def analyze(plan,status,events,acceptor,writer,*,authority,source):
    x.require(status.get('schema')=='n23-dev-supervisor-status-continuation-v1',
        'wrong continuation status schema')
    p=status.get('continuation',{})
    x.require(p.get('authority')==authority and p.get('external_source')==source
        and p.get('original_source_commit')==x.SOURCE and p.get('original_plan')==x.ref(x.PLAN)
        and p.get('original_failed_review')==x.ref(x.FAILURE) and p.get('imported_writer')==x.ref(x.WRITER),
        'continuation report provenance differs')
    result=writer.analyze(plan,status,events,acceptor)
    result.update(schema='n23-dev-continuation-result-v1',continuation=p,
        original_v2_disposition='INVALID_OR_INTERRUPTED',original_v2_record_preserved=True)
    return result


def main():
    owned=x.load_owned();r=owned.r;writer=x.load_writer(owned)
    x.require(not x.RESULT.exists(),'immutable continuation result already exists')
    with r.locked(x.HERE/'execution/continuation-controller-v1.lock',nonblocking=True),\
         r.locked(owned.root/'data/qd-ed-runner.lock',nonblocking=True),r.locked(owned.root/'data/qd-ed-state.lock'):
        plan,manifest,_=r.validate_plan(x.PLAN,root=owned.root)
        failure=x.immutable_inputs(owned);authority=x.authorization(plan,owned)
        status=r.read_json(x.STATUS);seal=owned.w.read_ref(x.ref(x.SEAL))
        x.require(seal.get('authority')==authority and status['continuation']['launch_seal']==x.ref(x.SEAL),
            'terminal launch seal differs')
        x.no_owned_worker(owned.root)
        events=r.read_events(owned.root/'data/attempt-ledger.jsonl')
        accept=x.acceptor(plan,manifest,owned)
        x.prefix_gate(plan,failure,events,owned,accept,initial=False)
        result=analyze(plan,status,events,accept,writer,authority=authority,source=x.source_record())
        local=[v for v in events if v.get('identity',{}).get('iteration')==owned.c.COHORT]
        text=''.join(json.dumps(v,sort_keys=True,allow_nan=False)+'\n' for v in local)
        if x.SNAPSHOT.exists():x.require(x.SNAPSHOT.read_text()==text,'immutable continuation snapshot differs')
        else:x.SNAPSHOT.write_text(text)
        result.update(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            plan=x.ref(x.PLAN),terminal_status={**x.ref(x.STATUS),'content':status},
            ledger_snapshot=x.ref(x.SNAPSHOT),backend_proof=plan['n23_cohort']['backend_proof'],
            reader=x.ref(__file__),original_failed_result=failure['original_failed_result'])
        owned.w.atomic_json(x.RESULT,result)
        print(json.dumps({'result':x.ref(x.RESULT),'decision':result['decision'],'counts':result['counts'],
            'dispatched':result['dispatched'],'gpu_process_wall_seconds':result['gpu_process_wall_seconds']}))


if __name__=='__main__':main()
