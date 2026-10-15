"""Prospective N35 accounting guards. No live ledger reads at import, no dispatch.

All reservation writes belong to a later root-released runner transaction. The
retained margin is a conservative admission deduction, not a rewrite of costs.
"""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r, qd_ed_n35_contract as c

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
    attempts=r.budget_snapshot(rows['attempt-ledger.jsonl'])['gpu_hours_consumed']
    health=r.budget_snapshot([],rows['gpu-healthcheck-ledger.jsonl'])['gpu_healthcheck_hours']
    frozen=accounting['cost_reconciliation']
    # Preserve the explicitly conservative bound even if the old aggregate had
    # already included some healthchecks. New charges are added independently.
    return float(max(Decimal(0),Decimal(str(frozen['attempt_charge_gpu_hours']))-Decimal(str(attempts)))
               + max(Decimal(0),Decimal(str(frozen['separate_healthcheck_gpu_hours']))-Decimal(str(health))))


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

    The explicit n35_healthcheck wrapper runs the fixed probe under timeout_seconds
    and the existing 40-second owned cleanup bound, then settles the journal.
    An unsettled reservation prevents every episode and probe admission.
    """
    import datetime as dt
    import os
    import re
    import time
    from scripts import qd_ed_n35_release as release, qd_ed_n35_runner as adapter
    from scripts import qd_ed_n35_supervise as supervisor
    w.require(isinstance(resource_id,str) and re.fullmatch(r'n35_healthcheck_[a-zA-Z0-9_-]+',resource_id), 'N35 healthcheck identity')
    w.require(type(timeout_seconds) is int and 0<timeout_seconds<=1760,'healthcheck timeout including full cleanup')
    plan,_,_=release.validate_release(plan_ref,release_ref)
    root=Path(plan['worktree'])
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
                reconciled['next_row'],now=dt.datetime.now(dt.timezone.utc),gpu_idle=True)
            selected={e['resource_id'] for e in resources if e.get('cohort')==c.COHORT
                      or e.get('kind')=='n35_resource_preparation_v1'}
            cohort=r.budget_snapshot(c.cohort_events(plan['episodes'],events),
                                    [e for e in resources if e['resource_id'] in selected])
            need=timeout_seconds+40
            reservation=headroom(snap,cohort,retained_margin_hours=snap['n35_reservation']['retained_margin_gpu_hours'],
                protected_hours=snap['n35_reservation']['protected_gpu_hours'],healthcheck=True,need=need)
            admission=adapter.device_check()
            now=dt.datetime.now(dt.timezone.utc)
            end=min(dt.datetime.fromisoformat(x.replace('Z','+00:00')) for x in
                    (c.DEADLINE,authority['coordinator_ends_at'],authority['weekly_window']['ends_at']))
            stop=Path(plan['stop_path'])
            w.require(not stop.exists() and not stop.is_symlink() and now<end,'STOP/deadline before healthcheck reservation')
            record={'resource_id':resource_id,'event':'reserved','cohort':c.COHORT,
                'kind':'n35_resource_preparation_v1','plan':plan_ref,'release':release_ref,
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
