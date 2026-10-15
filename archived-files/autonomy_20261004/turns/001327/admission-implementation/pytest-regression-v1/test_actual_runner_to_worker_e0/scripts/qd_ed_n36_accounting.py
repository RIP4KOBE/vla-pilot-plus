"""Prospective N36 accounting guards. No live ledger reads at import, no dispatch.

All reservation writes belong to a later root-released runner transaction. The
retained margin is a conservative admission deduction, not a rewrite of costs.
"""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r, qd_ed_n36_contract as c

ABSOLUTE_HOURS=Decimal('224')
WEEKLY_HOURS=Decimal('53.08404692669838')+Decimal('168')


def seconds(value):
    c.finite(value,'accounting hours')
    return Decimal(str(value))*3600


def retained_margin(root, reference):
    w.require(reference['sha256']==c.ACCOUNTING_SHA,'frozen accounting v2 required')
    accounting=w.read_ref(reference)
    rows={}
    for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl'):
        anchor=accounting['ledger_prefixes'][name];path=Path(root)/'data'/name
        w.require(path.is_file() and not path.is_symlink(),'retained accounting prefix path')
        with path.open('rb') as stream:content=stream.read(anchor['bytes'])
        w.require(len(content)==anchor['bytes'] and hashlib.sha256(content).hexdigest()==anchor['sha256'],'retained accounting prefix differs')
        rows[name]=[json.loads(line) for line in content.splitlines() if line.strip()]
    # The reviewed N36 normalization already includes incremental healthchecks.
    frozen=accounting['cost_reconciliation']
    margin=frozen['retained_admission_margin_gpu_hours']
    c.finite(margin,'retained admission margin')
    w.require(Decimal(str(margin))==Decimal('0.23357169027962'),'reviewed retained margin')
    return margin


def headroom(snap, cohort, *, retained_margin_hours, protected_hours, healthcheck=False, need=1840):
    w.require(type(need) is int and need>0 and (need<=1800 if healthcheck else need==1840),'bounded full reservation')
    charge=seconds(snap['gpu_hours_consumed'])+seconds(retained_margin_hours)
    protected=seconds(protected_hours)
    local=seconds(cohort['gpu_hours_consumed'])
    w.require(charge+protected+need<=ABSOLUTE_HOURS*3600,'absolute cumulative cap/protected reserves')
    w.require(charge+protected+need<=WEEKLY_HOURS*3600,'weekly cumulative cap/protected reserves')
    w.require(local+need<=c.LIMITS['cohort_gpu_seconds'],'cohort cumulative cap')
    health=seconds(cohort['gpu_healthcheck_hours'])
    w.require(health+(need if healthcheck else 0)<=c.LIMITS['healthcheck_seconds'],'separate cumulative healthcheck bound')
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0,'unsettled worker/healthcheck reservation')
    return {'reserved_gpu_seconds':need,'retained_margin_gpu_hours':retained_margin_hours,
        'charged_gpu_hours':snap['gpu_hours_consumed'],'cohort_charged_gpu_hours':cohort['gpu_hours_consumed'],
        'protected_gpu_hours':protected_hours,'absolute_cap_gpu_hours':str(ABSOLUTE_HOURS),
        'weekly_cap_gpu_hours':str(WEEKLY_HOURS),'kind':'healthcheck' if healthcheck else 'episode'}


def reserve_healthcheck(plan_ref, release_ref, resource_id, *, timeout_seconds):
    """Separate root-released probe reservation, never an episode or auto probe.

    The explicit n36_healthcheck wrapper runs the fixed probe under timeout_seconds
    and the existing 40-second owned cleanup bound, then settles the journal.
    An unsettled reservation prevents every episode and probe admission.
    """
    if c.cohort(w.read_ref(plan_ref)) == c.DRAFT_N36R3_COHORT:
        from scripts.qd_ed_n36r3_health import reserve
        return reserve(plan_ref, release_ref, resource_id, timeout_seconds=timeout_seconds)
    import datetime as dt
    import os
    import re
    import time
    from scripts import qd_ed_n36_release as release, qd_ed_n36_runner as adapter
    from scripts import qd_ed_n36_supervise as supervisor
    w.require(isinstance(resource_id,str) and re.fullmatch(r'n36_healthcheck_[a-zA-Z0-9_-]+',resource_id), 'N36 healthcheck identity')
    w.require(type(timeout_seconds) is int and 0<timeout_seconds<=60,'healthcheck timeout including full cleanup')
    plan,_,_=release.validate_release(plan_ref,release_ref)
    from scripts.qd_ed_n36r2_admission import owner_root, PREPARATION_ID, KIND
    root=owner_root(plan)
    if c.cohort(plan)==c.DRAFT_RECOVERY_COHORT:
        w.require(timeout_seconds<=20, 'N36R2 60s including cleanup ceiling')
    with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
        with r.locked(root/'data/qd-ed-state.lock'):
            plan,runtime,authority=release.validate_release(plan_ref,release_ref)
            state,events,resources,reservations=adapter.snapshot(root,authority)
            reconciled=supervisor.reconcile(plan,events,
                lambda row,final:adapter.worker.verify_terminal(plan_ref,row,final,release_ref),
                live_handles=adapter.existing_handles(plan,events))
            w.require(reconciled['next_row'] is not None,'healthcheck cannot bypass cohort stop')
            w.require(not any(e['resource_id']==resource_id for e in resources),'healthcheck replay forbidden')
            # Episode admission is at least as strict as the <=1800s probe. No
            # future episode attempt is consumed by this independent resource.
            snap=release.admission(plan,authority,state,events,resources,reservations,
                reconciled['next_row'],now=dt.datetime.now(dt.timezone.utc),gpu_idle=True,release_refs=(plan_ref,release_ref))
            selected={e['resource_id'] for e in resources if e.get('cohort')==c.cohort(plan)
                      or (c.cohort(plan)==c.COHORT and e.get('kind')=='n36_resource_preparation_v1')}
            if c.cohort(plan)==c.RECOVERY_COHORT:
                from scripts.qd_ed_n36_recovery import resource_events
                selected = {e['resource_id'] for e in resource_events(plan, resources)}
            if c.cohort(plan)==c.DRAFT_RECOVERY_COHORT:
                from scripts.qd_ed_n36r2_admission import resource_events
                selected = {e['resource_id'] for e in resource_events(plan, resources)}
            w.require(len(selected)<41,'healthcheck invocation ceiling')
            permitted={'n36_healthcheck_'+reconciled['next_row']['episode_key']}
            if not reconciled['outcomes']:
                permitted.add('n36_healthcheck_preparation' if c.cohort(plan)==c.COHORT
                              else PREPARATION_ID if c.cohort(plan)==c.DRAFT_RECOVERY_COHORT
                              else 'n36_healthcheck_n36r1_preparation_001203')
            w.require(resource_id in permitted,'one preparation plus one check per primary cell')
            cohort=r.budget_snapshot(c.cohort_events(plan['episodes'],events),
                                    [e for e in resources if e['resource_id'] in selected])
            need=timeout_seconds+40
            reservation=headroom(snap,cohort,retained_margin_hours=snap['n36_reservation']['retained_margin_gpu_hours'],
                protected_hours=snap['n36_reservation']['protected_gpu_hours'],healthcheck=True,need=need)
            admission=adapter.device_check()
            c.launch_guard(plan, authority, need=1840+need)
            record={**c.operational_binding(plan), 'resource_id':resource_id,'event':'reserved','cohort':c.cohort(plan),
                'kind':('n36_resource_preparation_v1' if c.cohort(plan)==c.COHORT else KIND if c.cohort(plan)==c.DRAFT_RECOVERY_COHORT else 'n36r1_resource_preparation_v1'),'plan':plan_ref,'release':release_ref,
                'source_commit':plan['source']['commit'],'runtime':plan['runtime'],
                'physical_gpu':7,'gpu_uuid':c.GPU_UUID,'timeout_seconds':timeout_seconds,
                'cleanup_seconds':40,'reserved_gpu_seconds':need,'accounting_admission':reservation,
                'admission':admission,'time_unix':time.time()}
            r.budget_snapshot(events,[*resources,record])
            path=root/'data/gpu-healthcheck-ledger.jsonl'
            with path.open('a') as stream:
                stream.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
            r.sync_state_from_journal(root,events)
            return record
