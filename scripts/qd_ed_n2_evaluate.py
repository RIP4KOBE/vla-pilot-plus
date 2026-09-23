#!/usr/bin/env python3
"""Prepare closed protected-phase plans or run an explicitly released frozen phase."""
import argparse
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import signal
import subprocess

import qd_ed_final_runner as r
import qd_ed_n2_plan as dev
import qd_ed_n2_evaluation as e
import qd_ed_n2_supervise as supervision


def prepare(base,phase,head,root):
    plan=copy.deepcopy(base);runtime=r.read_json(base['runtime_manifest_path'])
    seeds=r.read_json(base['seed_plan_path'])
    r.require(base['n2_cohort']['cohort_id']==dev.COHORT and base['seed_plan_sha256']==e.SEED_SHA,'selected Dev base required')
    r.require(r.runtime_gpu(runtime)==3,'GPU3 required')
    cbase=plan.pop('n2_cohort')
    for key in ('frozen_at','preflight_index','preflight_index_sha256','hardware_selection'):plan.pop(key,None)
    paths={x['path'] for x in base['code_files']}|e.TOOLING
    for path in paths:
        r.require((root/path).read_bytes()==subprocess.check_output(['git','show',head+':'+path],cwd=root),'uncommitted phase source: '+path)
    plan.update(frozen=False,worktree=str(root),source_commit=head,
        profiles_path=str(root/e.PROFILE),profiles_sha256=r.digest(root/e.PROFILE),
        episodes=e.rows(seeds,phase),phase_authorization={'dev':False,'validation':False,'formal':False},
        code_files=[{'path':p,'sha256':r.digest(root/p)} for p in sorted(paths)],
        scientific_config_files=sorted(set(base['scientific_config_files'])|{e.PROFILE,e.PROTOCOL,e.CLARIFICATION}))
    before={x['path']:x['sha256'] for x in base['code_files']}
    production=[{'path':p,'sha256':before[p]} for p in sorted(set(before)-e.TOOLING)]
    fingerprint=e.sha_json({'production_files':production,'candidate_profiles':base['candidate_profiles'],
        'runtime_manifest_sha256':base['runtime_manifest_sha256'],'runtime_inventory_sha256':base['runtime_inventory_sha256'],
        'seed_plan_sha256':base['seed_plan_sha256']})
    plan['n2_evaluation']={'schema':e.SCHEMA,'phase':phase,**e.PHASES[phase],
        'limits':e.PHASES[phase],'protocol':{'path':e.PROTOCOL,'sha256':e.PROTOCOL_SHA},
        'budget_clarification':{'path':e.CLARIFICATION,'sha256':e.CLARIFICATION_SHA},
        'dev_reporter':{'path':str(e.DEV_REPORT),'sha256':e.DEV_REPORT_SHA},
        'dev_plan':None,'candidate_fingerprint':fingerprint,'promotion_certificate':None,
        'source_mapping':{'dev_source_commit':base['source_commit'],'evaluation_source_commit':head,
            'allowed_tooling':sorted(e.TOOLING),'production_files':production},
        'runtime_prerequisites':cbase['runtime_prerequisites'],'health_resources':cbase['health_resources']}
    return plan


@contextmanager
def phase_pending(r,q,plan,runtime):
    """CPU preflight with the same certified phase hours, without allocating rows.

    Multi-row queue prechecks may inspect later rows before their predecessors
    run. Actual dispatch still enforces sequential valid/audited predecessors.
    """
    previous=q.pending_gate
    def pending(root,row):
        state=r.read_state(root/'research-state.yaml');candidates=q.candidate_indices(state)
        events,resources=q.no_unfinished(root)
        r.check_retry(events,row)
        permission=e.validated_budget_context(plan,runtime,row,events,resources,root,r,check_order=False)
        timeout=r.check_budget(state,events,row,resources,r.read_events(root/'data/gpu-hour-reservation-ledger.jsonl'),
            physical_gpu=3,evaluation_context=permission)
        r.require(timeout==1800,'protected N2 evaluation requires full 1800s plus cleanup; no clipping')
        return state,candidates
    q.pending_gate=pending
    try:yield
    finally:q.pending_gate=previous


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--dev-plan',type=Path,required=True)
    prep.add_argument('--phase',choices=e.PHASES,required=True);prep.add_argument('--source-head',required=True)
    prep.add_argument('--output',type=Path,required=True)
    run=sub.add_parser('run');run.add_argument('--plan',type=Path,required=True)
    run.add_argument('--episode-key',action='append',required=True);run.add_argument('--status-path',type=Path,required=True)
    args=p.parse_args();root=e.ROOT
    if args.command=='prepare':
        r.require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==args.source_head,'HEAD differs')
        plan=prepare(r.read_json(args.dev_plan),args.phase,args.source_head,root)
        plan['n2_evaluation']['dev_plan']={'path':str(args.dev_plan.resolve()),'sha256':r.digest(args.dev_plan)}
        e.scientific_mapping(plan,root,r)
        output=r.owned(args.output,Path(plan['artifact_root'])/'continuation_20260923')
        r.require(not output.exists(),'preserve prior plan');output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x') as f:json.dump(plan,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
        print(json.dumps({'status':'nonrunnable_prepared','episodes':len(plan['episodes']),'phase_authorization':plan['phase_authorization']}))
        return
    r.require(root==supervision.AUTHORITATIVE_ROOT,'isolated preparation worktree cannot dispatch')
    import qd_ed_available_gpu_queue as q
    import audit_decision_evidence
    plan,_,runtime=r.validate_plan(args.plan,root=root)
    phase=plan['n2_evaluation']['phase'];r.require(plan['phase_authorization'].get(phase) is True,'protected phase remains closed')
    keys=args.episode_key;available={x['episode_key']:x for x in plan['episodes']}
    r.require(len(set(keys))==len(keys) and set(keys)<=set(available),'evaluation requested keys invalid')
    positions={e.cell(x):i for i,x in enumerate(x for x in plan['episodes'] if not x.get('retry_of'))}
    r.require([positions[e.cell(available[k])] for k in keys]==sorted(positions[e.cell(available[k])] for k in keys),
        'evaluation request order differs')
    status=r.owned(args.status_path,plan['artifact_root']);r.require(not status.exists(),'preserve launch status')
    status.parent.mkdir(parents=True,exist_ok=True)
    support=supervision.load_support(root,dev.SUPPORT);monitor=support.Monitor(r,root,status.parent,episode_keys=keys)
    proxy={**plan,'n2_cohort':plan['n2_evaluation']}
    check=lambda:supervision.prerequisite(r,dev,proxy,runtime,root)
    previous=signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    entered=False
    try:
        with support.shared_runner_lease(r,q,root,status,args.plan,monitor,check,episode_keys=keys):
            state=r.read_state(root/'research-state.yaml')
            r.require(q.candidate_indices(state)==[3] and r.authorized_gpu(state)==3,'GPU3-only state required')
            e.reviewed_promotion(plan,r.read_events(root/'data/attempt-ledger.jsonl'),root,r)
            with phase_pending(r,q,plan,runtime),support.supervise_calls(r,q,monitor,check),supervision.frozen_hardware(r,q),supervision.audited_calls(r,audit_decision_evidence.audit_episode),e.supervised_dispatch(plan,keys,root,r,q,monitor,status):
                entered=True
                result=q.run_queue(args.plan,keys,poll_seconds=30,idle_seconds=120,status_path=status,root=root)
    except BaseException as exc:
        if not entered:r.durable_json(status,{'status':'failed','selected_physical_gpu':None,
            'reason':str(exc) if isinstance(exc,r.GateError) else type(exc).__name__})
        raise
    finally:signal.signal(signal.SIGTERM,previous)
    print(json.dumps({'status':result['status'],'completed_keys':result.get('completed_keys',[])}))


if __name__=='__main__':main()
