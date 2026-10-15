"""Adopt the reviewed one-use operational continuation without changing budget."""
import copy
import datetime
import json
import os
import sys
import n23_continuation_contract as x

def main():
    owned=x.load_owned();r=owned.r
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    proof=x.HERE/'root-continuation-review-v1.json'
    assert x.sha(proof)=='520cec3e63fe2c0ff28265f4a0263c32562b6fc6696320f22dc285a31d81500d'
    with r.locked(owned.root/'data/qd-ed-runner.lock',nonblocking=True),r.locked(owned.root/'data/qd-ed-state.lock'):
        plan=owned.w.read_ref(x.ref(x.PLAN));failure=x.immutable_inputs(owned)
        source=x.source_record();owning=x.owning_source(plan,owned)
        assert owned.w.read_ref(x.ref(x.REVIEW))==x.review_payload(plan,source,owning,owned)
        manifest=r.read_json(plan['profiles_path'])
        for arm,reference in plan['candidate_profiles'].items():
            manifest['profiles'][arm]=r.expand_candidate(arm,owned.w.read_ref(reference),manifest['profiles']['Q0'])
        events=r.read_events(owned.root/'data/attempt-ledger.jsonl')
        resources=r.read_events(owned.root/'data/gpu-healthcheck-ledger.jsonl')
        prefix=x.prefix_gate(plan,failure,events,owned,x.acceptor(plan,manifest,owned),initial=True)
        state=r.read_state(owned.root/'research-state.yaml');before_budget=copy.deepcopy(state['budget'])
        assert state.get(x.KEY) is None and not x.SEAL.exists() and not x.STATUS.exists()
        assert state['provider_user_restriction']=={'backend':'codex_cli','auth_mode':'chatgpt','poe_usage_allowed':False,'poe_credentials_preserved':True}
        x.quiescent(plan,owned,state,events,resources)
        authority=x.authority_payload(x.ref(x.REVIEW),plan,owned)
        owned.w.atomic_json(x.AUTHORITY,authority)
        state[x.KEY]=x.ref(x.AUTHORITY)
        state['current_iteration'].update(status='DEV_CONTINUATION_READY',current_owned_workers=[],
            continuation_authority=x.ref(x.AUTHORITY),continuation_source_review=x.ref(x.REVIEW),
            continuation_external_source=source,continuation_status_path=str(x.STATUS),
            original_v2_disposition='INVALID_OR_INTERRUPTED',validation_authorized=False,formal_authorized=False)
        assert state['budget']==before_budget
        temp=owned.root/'research-state.yaml.continuation-adoption-tmp'
        with temp.open('w') as stream:
            r.yaml.safe_dump(state,stream,sort_keys=False);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,owned.root/'research-state.yaml')
        assert x.authorization(plan,owned,state=r.read_state(owned.root/'research-state.yaml'))==x.ref(x.AUTHORITY)
        applied={'schema':'n23-legacy-metric-continuation-adoption-v1','recorded_at':now,
            'authority':x.ref(x.AUTHORITY),'root_review':x.ref(proof),'prefix_cells':len(prefix),
            'pending_primary_cells':37,'budget_snapshot':r.budget_snapshot(events,resources),
            'budget_changed':False,'owning_source_changed':False,'backend_preflight_authorized':False,
            'gpu_or_api_dispatched':False,'validation_authorized':False,'formal_authorized':False}
        target=x.AUTHORITY.parent/'applied.json';owned.w.atomic_json(target,applied)
    sys.path.insert(0,'/home/hynx/.codex/skills/arbor-agent-tools/scripts')
    import arbor_state
    with arbor_state.state_lock(owned.root,'rdt-qd-ed-final-20260921T093925Z'):
        checkpoint=owned.root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
        state=json.loads(checkpoint.read_text())
        state.update(phase='DISPATCH',status='N23_DEV_CONTINUATION_READY',updated_at=now,
            owned_gpu_workers=[],in_flight_executors=[],automatic_gpu_dispatch_authorized=True,
            target_achieved=False,pending_human_gate=None,continuation_authority=x.ref(x.AUTHORITY),
            continuation_adoption=x.ref(target),status_path=str(x.STATUS),
            validation_cpu_review_pending=True,no_new_validation_or_formal_dispatch=True)
        r.durable_json(checkpoint,state)
    print(json.dumps({'authority':x.ref(x.AUTHORITY),'adoption':x.ref(target),
        'pending_cells':37,'budget_changed':False,'source_unchanged':True,'dispatched':False}))

if __name__=='__main__':main()
