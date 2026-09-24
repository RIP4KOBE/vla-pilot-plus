#!/usr/bin/env python3
"""Conditional private-study N4 protected phases. Preparation is never release."""
import argparse
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import resource
import signal
import subprocess
import time

import qd_ed_final_runner as r
import qd_ed_n4_plan as dev
import qd_ed_n4_evaluation as e
import qd_ed_n4_supervise as supervision


def skeleton(base,phase,head,root,dev_reference,resource_authority,seed_exposure_review):
    """No seed table read and no protected rows produced by this metadata step."""
    r.require(base['n4_cohort']['cohort_id']==dev.COHORT and base['seed_plan_sha256']==e.SEED_SHA,
        'selected frozen N4 Dev base required')
    plan=copy.deepcopy(base);previous=plan.pop('n4_cohort')
    for key in ('frozen_at','preflight_index','preflight_index_sha256','hardware_selection'):
        plan.pop(key,None)
    paths={x['path'] for x in base['code_files']}|e.TOOLING
    for path in paths:
        r.require((root/path).read_bytes()==subprocess.check_output(['git','show',head+':'+path],cwd=root),
            'uncommitted evaluation runtime source: '+path)
    plan.update(frozen=False,worktree=str(root),source_commit=head,episodes=[],
        profiles_path=str(root/e.PROFILE),profiles_sha256=r.digest(root/e.PROFILE),
        phase_authorization={'dev':False,'validation':False,'formal':False},
        code_files=[{'path':p,'sha256':r.digest(root/p)} for p in sorted(paths)],
        scientific_config_files=sorted(set(base['scientific_config_files'])|{e.PROFILE,e.PROTOCOL}))
    before={x['path']:x['sha256'] for x in base['code_files']}
    production=[{'path':p,'sha256':before[p]} for p in sorted(set(before)-e.TOOLING)]
    fingerprint=e.sha_json({'production_files':production,'candidate_profiles':base['candidate_profiles'],
        'runtime_manifest_sha256':base['runtime_manifest_sha256'],
        'runtime_inventory_sha256':base['runtime_inventory_sha256'],'seed_plan_sha256':base['seed_plan_sha256']})
    plan['n4_evaluation']={'schema':e.SCHEMA,'phase':phase,'cohort_id':e.PHASES[phase]['cohort_id'],
        'limits':e.PHASES[phase],'protocol':{'path':e.PROTOCOL,'sha256':e.PROTOCOL_SHA},
        'budget_clarification':{'path':e.PROTOCOL,'sha256':e.PROTOCOL_SHA},
        'dev_reporter':{'path':str(e.DEV_REPORT),'sha256':e.DEV_REPORT_SHA},
        'dev_plan':dev_reference,'candidate_fingerprint':fingerprint,'promotion_certificate':None,
        'resource_authority':copy.deepcopy(resource_authority),'seed_exposure_review':copy.deepcopy(seed_exposure_review),
        'source_mapping':{'dev_source_commit':base['source_commit'],'evaluation_source_commit':head,
            'allowed_tooling':sorted(e.TOOLING),'production_files':production},
        'runtime_prerequisites':previous['runtime_prerequisites'],'health_resources':previous['health_resources']}
    e.scientific_mapping(plan,root,r)
    return plan


def prepare(plan,promotion_reference,events,root,runner=r):
    """Gate on a recomputed predecessor before reading real protected seed rows."""
    api=e.api(runner);plan=copy.deepcopy(plan)
    plan['n4_evaluation']['promotion_certificate']=promotion_reference
    e.reviewed_promotion(plan,events,root,api)
    seed_path=api.owned(plan['seed_plan_path'],root)
    api.require(api.digest(seed_path)==plan['seed_plan_sha256'],'frozen seed metadata changed')
    plan['episodes']=e.rows(api.read_json(seed_path),plan['n4_evaluation']['phase'])
    runtime=api.read_json(plan['runtime_manifest_path'])
    manifest=api.read_json(plan['profiles_path'])
    manifest['profiles']['N4']=api.expand_candidate('N4',api.read_json(Path(root)/dev.PROFILE),manifest['profiles']['Q0'])
    e.validate_contract(plan,manifest,runtime,api.read_json(seed_path),root,api)
    e.check_seed_exposure(plan,events,root,api)
    return plan


@contextmanager
def phase_pending(r,q,plan,runtime):
    old=q.pending_gate
    def pending(root,row):
        state=r.read_state(root/'research-state.yaml');candidates=q.candidate_indices(state)
        events,resources=q.no_unfinished(root)
        r.check_retry(events,row)
        permission=e.validated_budget_context(plan,runtime,row,events,resources,root,r,check_order=False)
        timeout=r.check_budget(state,events,row,resources,r.read_events(root/'data/gpu-hour-reservation-ledger.jsonl'),
            physical_gpu=3,evaluation_context=permission)
        e.whole_phase_budget(plan,state,events,resources,row,timeout,r)
        return state,candidates
    q.pending_gate=pending
    try:yield
    finally:q.pending_gate=old


@contextmanager
def audited_calls(r,audit,off_audit):
    original=r.run_plan
    def run(*args,**kwargs):
        r.require(len(kwargs.get('episode_keys') or [])==1,'protected phase dispatch must select one row')
        results=original(*args,**kwargs)
        for result in results:
            output=Path(result['output_dir']);start=time.monotonic()
            before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            function=off_audit if result['identity']['profile']=='N4_QD_OFF' else audit
            error=None;report=None
            try:
                report=function(output/'eds_eval/decision_evidence/episode_000',output/'eds_eval/episode_compute.jsonl')
                alignment=e.verify_phase_audit(result['identity'],result,report,r)
            except Exception as exc:
                error=type(exc).__name__
                report=report if isinstance(report,dict) else {'accepted':False,'evidence_complete':False,'errors':['audit_exception:'+error]}
                alignment={'status':'failed','error_type':error}
            report['wrapper_observation']={'audit_wall_seconds':time.monotonic()-start,
                'parent_ru_maxrss_before_kib':before,'parent_ru_maxrss_after_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'memory_scope':'Linux cumulative parent peak including imports/queue/prior audits; not audit-exclusive; peak difference is not memory usage',
                'phase_native_alignment':alignment}
            r.durable_json(output/'eds_eval/decision-evidence-audit.json',report)
            r.require(error is None and report.get('accepted') is True and report.get('evidence_complete') is True,
                'protected phase audit failed; original terminal/cost retained; no retry release')
        return results
    r.run_plan=run
    try:yield
    finally:r.run_plan=original


def prerequisite(plan,runtime,root):
    e.resource_authority(plan,runtime,root,r)
    base=e.read_ref(plan['n4_evaluation']['dev_plan'],plan,r)
    proxy={**plan,'n4_cohort':base['n4_cohort']}
    # These references prove unchanged engineering inputs, not a new algorithm pass.
    supervision.prerequisite(r,dev,proxy,runtime,root)
    records={x['path']:x['sha256'] for x in plan['code_files']}
    for name in e.TOOLING:r.require(records.get(name)==r.digest(root/name),'protected phase tooling changed: '+name)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for name in ('describe','prepare'):
        cmd=sub.add_parser(name);cmd.add_argument('--dev-plan',type=Path,required=True)
        cmd.add_argument('--phase',choices=e.PHASES,required=True);cmd.add_argument('--source-head',required=True)
        cmd.add_argument('--resource-authority',type=Path,required=True)
        cmd.add_argument('--seed-exposure-review',type=Path,required=True)
        if name=='prepare':
            cmd.add_argument('--promotion-certificate',type=Path,required=True);cmd.add_argument('--promotion-sha256',required=True)
            cmd.add_argument('--output',type=Path,required=True)
    cmd=sub.add_parser('run');cmd.add_argument('--plan',type=Path,required=True)
    cmd.add_argument('--episode-key',action='append',required=True);cmd.add_argument('--status-path',type=Path,required=True)
    cmd.add_argument('--execution-release',type=Path,required=True);cmd.add_argument('--execution-release-sha256',required=True)
    args=parser.parse_args();root=e.ROOT
    if args.command in {'describe','prepare'}:
        r.require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==args.source_head,'HEAD differs')
        plan=skeleton(r.read_json(args.dev_plan),args.phase,args.source_head,root,
            {'path':str(args.dev_plan.resolve()),'sha256':r.digest(args.dev_plan)},r.read_json(args.resource_authority),
            {'path':str(args.seed_exposure_review.resolve()),'sha256':r.digest(args.seed_exposure_review)})
        if args.command=='describe':
            print(json.dumps({'status':'identity_only_no_plan_or_seed_allocation','target_binding':e.binding(plan)}));return
        with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
            plan=prepare(plan,{'path':str(args.promotion_certificate.resolve()),'sha256':args.promotion_sha256},
                r.read_events(root/'data/attempt-ledger.jsonl'),root)
            output=r.owned(args.output,plan['artifact_root']);r.require(not output.exists(),'preserve previous plan')
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open('x') as stream:json.dump(plan,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
        print(json.dumps({'status':'nonrunnable_prepared','episodes':len(plan['episodes']),
            'phase_authorization':plan['phase_authorization']}));return
    r.require(root==supervision.AUTHORITATIVE_ROOT,'isolated preparation worktree cannot dispatch')
    import qd_ed_available_gpu_queue as q
    import audit_decision_evidence
    import audit_n4_qd_off_evidence as off
    plan,_,runtime=r.validate_plan(args.plan,root=root)
    reference={'path':str(args.execution_release.resolve()),'sha256':args.execution_release_sha256}
    e.execution_release(reference,args.plan,plan,runtime,args.episode_key,root,r)
    status=r.owned(args.status_path,plan['artifact_root']);r.require(not status.exists(),'preserve prior launch status')
    status.parent.mkdir(parents=True,exist_ok=True)
    support=supervision.load_support(root,dev.SUPPORT)
    monitor=support.Monitor(r,root,status.parent,episode_keys=args.episode_key)
    check=lambda:prerequisite(plan,runtime,root)
    previous=signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    entered=False
    try:
        with support.shared_runner_lease(r,q,root,status,args.plan,monitor,check,episode_keys=args.episode_key):
            e.reviewed_promotion(plan,r.read_events(root/'data/attempt-ledger.jsonl'),root,r)
            with phase_pending(r,q,plan,runtime),support.supervise_calls(r,q,monitor,check),supervision.frozen_hardware(r,q),audited_calls(r,audit_decision_evidence.audit_episode,off.audit_episode):
                with e.supervised_dispatch(plan,args.episode_key,root,r,q,monitor,status,
                        release_reference=reference,plan_path=args.plan,runtime=runtime):
                    entered=True
                    result=q.run_queue(args.plan,args.episode_key,poll_seconds=30,idle_seconds=120,status_path=status,root=root)
    except BaseException as exc:
        if not entered:r.durable_json(status,{'status':'failed','selected_physical_gpu':None,
            'reason':str(exc) if isinstance(exc,r.GateError) else type(exc).__name__})
        raise
    finally:signal.signal(signal.SIGTERM,previous)
    print(json.dumps({'status':result['status'],'completed_keys':result.get('completed_keys',[])}))


if __name__=='__main__':main()
