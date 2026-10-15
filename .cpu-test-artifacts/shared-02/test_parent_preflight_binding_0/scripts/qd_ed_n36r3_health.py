"""Separately approved finite N36R3 health reservation in the owning journals."""
import datetime as dt
import json
import os
import time
from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r
from scripts import qd_ed_n36_contract as c, qd_ed_n36_release as release
from scripts import qd_ed_n36_accounting as accounting, qd_ed_n36_runner as adapter
from scripts import qd_ed_n36_supervise as supervisor, qd_ed_n36r3_admission as gate


def reserve(plan_ref, health_release_ref, resource_id, *, timeout_seconds):
    w.require(type(timeout_seconds) is int and timeout_seconds == 20,
              'N36R3 exactly 20 probe plus 40 cleanup seconds')
    plan, runtime, authority = release.validate_health_release(plan_ref, health_release_ref)
    spec = gate.identity_contract(plan)
    root = gate.owner_root(plan)
    with r.locked(root/'data/qd-ed-runner.lock', nonblocking=True):
        with r.locked(root/'data/qd-ed-state.lock'):
            plan, runtime, authority = release.validate_health_release(plan_ref, health_release_ref)
            state, events, resources, reservations = adapter.snapshot(root, authority)
            local, health = gate.live_journals(plan, authority, events, resources, reservations)
            release.validate_state(plan, authority, state)
            w.require(state['run_name'] == plan['run_name']
                      and state['artifacts'] == runtime['artifact_root'], 'N36R3 owning run identity')
            result = supervisor.reconcile(plan, events,
                lambda row, final: adapter.worker.verify_terminal(plan_ref, row, final, final['release']),
                live_handles=adapter.existing_handles(plan, events))
            w.require(result['next_row'] is not None, 'health cannot bypass cohort stop or first C0 pause')
            w.require(all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(events).values()),
                      'health unsettled episode reservation')
            w.require(not any(e['resource_id'] == resource_id for e in resources), 'health replay forbidden')
            permitted = {'n36_healthcheck_' + result['next_row']['episode_key']}
            if not result['outcomes']:
                permitted.add(spec['health']['preparation_id'])
            w.require(resource_id in permitted, 'one preparation plus one check per primary cell')
            w.require(len({e['resource_id'] for e in health}) < 41
                      and not any(e['event'] == 'aborted' for e in health),
                      'health invocation ceiling or invalidity stop; no retry')
            snap = r.budget_snapshot(events, resources)
            # Existing state/journal and protected reserve checks; no episode
            # authority, readiness, attempt reservation, or 1840s deadline needed.
            w.require(r.check_budget_limits(state, snap, result['next_row'], reservations,
                      bucket_caps=c.CAPS['buckets'], amendment=authority['amendment']) >= 20,
                      'health budget unavailable')
            cohort = r.budget_snapshot(local, health)
            protected = sum(max(0., hours-snap['gpu_hours_by_bucket'][key])
                            for key, hours in c.CAPS['protected_gpu_hours'].items())
            reservation = accounting.headroom(snap, cohort,
                retained_margin_hours=accounting.retained_margin(root, gate.margin_reference(plan)),
                protected_hours=protected, healthcheck=True, need=60)
            now = dt.datetime.now(dt.timezone.utc)
            w.require(dt.datetime.fromisoformat(authority['starts_at'].replace('Z', '+00:00')) <= now,
                      'health authority not started')
            c.launch_guard(plan, authority, now=now, need=60)
            admission = adapter.device_check()
            c.launch_guard(plan, authority, need=60)
            record = {**c.operational_binding(plan), 'resource_id': resource_id,
                'event': 'reserved', 'kind': spec['kind'], 'plan': plan_ref, 'release': health_release_ref,
                'source_commit': plan['source']['commit'], 'runtime': plan['runtime'],
                'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID, 'timeout_seconds': 20,
                'cleanup_seconds': 40, 'reserved_gpu_seconds': 60,
                'accounting_admission': reservation, 'admission': admission, 'time_unix': time.time()}
            r.budget_snapshot(events, [*resources, record])
            with (root/'data/gpu-healthcheck-ledger.jsonl').open('a') as stream:
                stream.write(json.dumps(record, sort_keys=True, allow_nan=False)+'\n')
                stream.flush(); os.fsync(stream.fileno())
            r.sync_state_from_journal(root, events)
            return record
