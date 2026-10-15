#!/usr/bin/env python3
"""N4-only entry: original queue/runner + shared lease, owned Xid, complete CPU audit.

No retry is created here. Every attempt keeps the runner's original terminal and
accounting. Failed audit stops the queue after that accounting, without retry.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
AUTHORITATIVE_ROOT=Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')


def load_support(root, relative):
    spec=importlib.util.spec_from_file_location('n4_supervisor_support',root/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def prerequisite(r,n,plan,runtime,root,*,boot=None,gpu_metadata=None):
    """Reuse prior *engineering* evidence, not its obsolete algorithm/source claim."""
    n.resource_authority(plan,runtime,root,r)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip() if boot is None else boot
    r.require(boot==plan['boot_id']==n.BOOT,'N4 GPU3 boot changed')
    records={item['path']:item['sha256'] for item in plan['code_files']}
    for relative in (n.SUPPORT,n.DEPENDENCIES,n.SUPERVISOR,n.MODULE,n.PROTOCOL,n.CLARIFICATION,n.ALLOCATION,n.PREREQUISITE):
        r.require(records.get(relative)==r.digest(root/relative),'N4 supervisor/dependency source freeze differs')
    deps=r.read_json(root/n.DEPENDENCIES)
    r.verify_files(deps['files'])
    refs=plan['n4e1_cohort']['runtime_prerequisites']['references'];loaded={}
    r.require(set(refs)==n.PREREQUISITES,'N4 prior engineering references differ')
    for name,ref in refs.items():
        path=r.owned(ref['path'],plan['artifact_root'])
        r.require(r.digest(path)==ref['sha256'],'N4 prior engineering reference changed: '+name)
        loaded[name]=r.read_json(path)
    health,contract=loaded['health_result'],loaded['health_contract']
    r.require(health['event']=='completed' and health.get('faults')==[] and
        health['boot_id']==contract['boot_id']==boot and health['physical_gpu']==contract['physical_gpu']==3 and
        health['resource_id']==contract['resource_id'] and health['contract_sha256']==refs['health_contract']['sha256'],
        'N4 current-boot health evidence differs')
    r.require(any(x=={'resource_id':health['resource_id'],'scope':'reused_prior'}
        for x in plan['n4e1_cohort']['health_resources']),'N4 prior freshboot resource attribution missing')
    prior_runtime=r.owned(contract['runtime_manifest_path'],plan['artifact_root'])
    r.require(r.digest(prior_runtime)==contract['runtime_manifest_sha256'],'N4 prior runtime changed')
    previous=r.read_json(prior_runtime)['gpu_mapping'];current=runtime['gpu_mapping']
    fields=('physical_gpu','uuid','pci_bus_id','driver_version','egl_device_index')
    r.require(all(previous[k]==current[k] for k in fields),'N4 current/prior GPU identity differs')
    r.require(all(contract[key]==plan[key] for key in ('runtime_inventory_sha256','seed_plan_sha256')),
              'N4 reused model inventory/seed identity differs')
    r.verify_files(contract['dependency_sources'])
    result,process,kernel=(loaded[k] for k in ('common_result','common_process','common_kernel'))
    r.require(result['event']=='valid' and result.get('outcome_valid') is True and result['physical_gpu']==3 and
        result['episode_key']=='freshboot_c0_t00_20260923','N4 common-condition result differs')
    r.require(process['attempt_id']==kernel['attempt_id']==result['attempt_id'] and
        process['pid']==kernel['pid'] and str(process['proc_start_ticks'])==str(kernel['proc_start_ticks']) and
        process['boot_id']==kernel['boot_id']==boot and kernel['physical_gpu']==3 and
        kernel['kind']=='episode' and kernel['faults']==[],'N4 common-condition process/kernel evidence differs')
    if gpu_metadata is None:
        gpu_metadata=subprocess.check_output(['nvidia-smi','-i','3',
            '--query-gpu=uuid,pci.bus_id,driver_version','--format=csv,noheader'],text=True,timeout=15).strip()
    actual=[value.strip() for value in gpu_metadata.split(',')]
    r.require(actual==[current['uuid'],current['pci_bus_id'],current['driver_version']],
              'N4 current GPU UUID/PCI/driver differs')


@contextmanager
def frozen_hardware(r,q):
    """N4 keeps its frozen runtime; no implicit probe or hardware revision."""
    original=q.bind_plan
    def bind(path,plan,runtime,device,row,events_path,*,root):
        with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
            q.pending_gate(root,row)
            r.validate_plan(path,root=root)
            mapping=q.current_metadata(3,root=root)
            r.require(device['physical_gpu']==3 and device['uuid']==mapping['uuid'] and
                q.same_mapping(runtime['gpu_mapping'],mapping),'N4 frozen GPU mapping changed')
            resources=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl')
            proof=q.find_probe(runtime,mapping,resources,root=root)
            r.require(proof and proof==runtime.get('cuda_egl_probe') and runtime.get('cuda_egl_verified') is True,
                'N4 frozen GPU proof unavailable; no automatic probe or runtime revision')
            q.reservation_admission(device)
            r.gpu_admission(physical_gpu=3,expected_uuid=mapping['uuid'])
            return Path(path),plan,runtime
    q.bind_plan=bind
    try:yield
    finally:q.bind_plan=original


@contextmanager
def audited_calls(r,audit,n):
    original=r.run_plan
    def run(*args,**kwargs):
        # Exactly one episode per queue call; audit before any later dispatch.
        r.require(len(kwargs.get('episode_keys') or [])==1,'N4 supervised dispatch must select exactly one row')
        results=original(*args,**kwargs)
        for result in results:
            output=Path(result['output_dir']);before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            started=time.monotonic()
            try:
                report=audit(output/'eds_eval/decision_evidence/episode_000',output/'eds_eval/episode_compute.jsonl')
            except Exception as exc:
                report={'schema':'qd-ed-decision-evidence-wrapper-error-v1','accepted':False,
                    'evidence_complete':False,'errors':['audit_exception:'+type(exc).__name__]}
            report['wrapper_observation']={'audit_wall_seconds':time.monotonic()-started,
                'parent_ru_maxrss_before_kib':before,
                'parent_ru_maxrss_after_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'memory_scope':'Linux cumulative parent peak including imports/queue/prior audits; not audit-exclusive; peak difference is not memory usage'}
            alignment_error=None
            if report.get('accepted') is True and report.get('evidence_complete') is True and result['identity']['profile']=='N4':
                try:
                    metrics=r.read_events(output/'eds_eval/eds_metrics.jsonl')
                    r.require(len(metrics)==result.get('metric_chunks')==result.get('guided_chunks'),'N4 native audit metric count differs')
                    report['wrapper_observation']['native_terminal_population_alignment']=n.native_audit_alignment(report,metrics,require=r.require)
                except Exception as exc:
                    alignment_error=type(exc).__name__
                    report['wrapper_observation']['native_terminal_population_alignment']={'status':'failed','error_type':alignment_error}
            r.durable_json(output/'eds_eval/decision-evidence-audit.json',report)
            r.require(report.get('accepted') is True and report.get('evidence_complete') is True,
                'N4 decision evidence incomplete; later undispatched rows stopped; original terminal preserved')
            r.require(alignment_error is None,
                'N4 native terminal-population audit alignment failed; later undispatched rows stopped; original terminal preserved')
        return results
    r.run_plan=run
    try:yield
    finally:r.run_plan=original


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--episode-key',action='append',required=True)
    parser.add_argument('--status-path',type=Path,required=True)
    parser.add_argument('--execution-release',type=Path,required=True)
    parser.add_argument('--execution-release-sha256',required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(ROOT/'scripts'))
    import qd_ed_final_runner as r
    import qd_ed_available_gpu_queue as q
    n=r.n4e1_support()
    import audit_decision_evidence
    r.require(ROOT==AUTHORITATIVE_ROOT,'N4 integrate into authoritative worktree before dispatch')
    plan,_,runtime=r.validate_plan(args.plan,root=ROOT)  # Full model validation once; runner caches hashes.
    r.require(plan.get('n4e1_cohort',{}).get('cohort_id')==n.COHORT,'N4 cohort required')
    keys=args.episode_key
    rows={row['episode_key']:row for row in plan['episodes']}
    r.require(len(set(keys))==len(keys) and set(keys)<=set(rows),'N4 selected keys missing/duplicate')
    r.require([r.episode_identity(rows[k]) for k in keys]==sorted(
        [r.episode_identity(rows[k]) for k in keys],key=lambda identity:next(
        i for i,row in enumerate(plan['episodes']) if r.episode_identity(row)==identity)),
        'N4 requested keys must preserve frozen cell order')
    release_reference={'path':str(args.execution_release.resolve()),'sha256':args.execution_release_sha256}
    n.execution_release(release_reference,args.plan,plan,runtime,keys,ROOT,r)
    status=r.owned(args.status_path,plan['artifact_root'])
    r.require(not status.exists(),'N4 status already exists; preserve prior launch evidence')
    status.parent.mkdir(parents=True,exist_ok=True)
    support=load_support(ROOT,n.SUPPORT)
    monitor=support.Monitor(r,ROOT,status.parent,episode_keys=keys)
    check=lambda:prerequisite(r,n,plan,runtime,ROOT)
    previous=signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    entered=False
    try:
        with support.shared_runner_lease(r,q,ROOT,status,args.plan,monitor,check,episode_keys=keys):
            state=r.read_state(ROOT/'research-state.yaml')
            r.require(q.candidate_indices(state)==[3] and r.authorized_gpu(state)==3,'N4 GPU3-only state required')
            with support.supervise_calls(r,q,monitor,check),frozen_hardware(r,q),audited_calls(r,audit_decision_evidence.audit_episode,n):
                with n.supervised_dispatch(plan,keys,ROOT,r,q,monitor,status,release_reference=release_reference,plan_path=args.plan,runtime=runtime):
                    entered=True
                    result=q.run_queue(args.plan,keys,poll_seconds=30,idle_seconds=120,status_path=status,root=ROOT)
    except BaseException as exc:
        if not entered:
            r.durable_json(status,{'status':'interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
                'episode_keys':keys,'selected_physical_gpu':None,
                'reason':str(exc) if isinstance(exc,r.GateError) else type(exc).__name__})
        raise
    finally:signal.signal(signal.SIGTERM,previous)
    print(json.dumps({'status':result['status'],'completed_keys':result.get('completed_keys',[]),
        'attempts':[{k:row.get(k) for k in ('attempt_id','event','outcome_valid','success')} for row in result.get('results',[])]}))


if __name__=='__main__':main()
