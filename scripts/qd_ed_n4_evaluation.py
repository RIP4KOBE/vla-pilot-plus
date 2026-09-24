#!/usr/bin/env python3
"""Closed, conditional N4 evaluation contracts. No automatic phase release."""
import copy
from contextlib import contextmanager
import fcntl
import os
import threading
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import qd_ed_n4_plan as dev

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='qd-ed-n4-evaluation-v1'
PROTOCOL='experiments/iteration_004_terminal_population/protected-evaluation-protocol-v1.md'
PROTOCOL_SHA='09881ae7ae24e363ee710c6a2dc8455c01fa74b25b6dec279dafc9a1946564f8'
CLARIFICATION=PROTOCOL
CLARIFICATION_SHA=PROTOCOL_SHA
SEED_SHA='9bbcf7107f6be4f739870a034ea84c4695819bdc1bffe5aa1148f453acf4a6b1'
DEV_REPORT_SHA='d26769d73e43e6b10b8171f6930604bc510d15b26174ca3a767bcdf84a72c2fb'
DEV_REPORT=ROOT/'scripts/qd_ed_n4_report.py'
SEED_REVIEW_SHA='10cf6516514f8616014e8f3bf34f02ccc1ea591e8f3855d5d6eb4c394a672e6c'
ISOLATION_SHA='4026c141ff9bd06f31734c0a43122327b359c35bd847670f641961df9ce81f47'
OFF_AUDIT='scripts/audit_n4_qd_off_evidence.py'
PROFILE='configs/qd_ed_final/n4_evaluation_profiles.json'
MODULE='scripts/qd_ed_n4_evaluation.py'
REPORT='scripts/qd_ed_n4_evaluation_report.py'
SUPERVISOR='scripts/qd_ed_n4_evaluate.py'
# Only these runtime files may differ from the frozen Dev code inventory.
# Tests/docs can be separately committed, but may not authorize production drift.
TOOLING={MODULE,REPORT,SUPERVISOR,PROFILE,PROTOCOL,CLARIFICATION,OFF_AUDIT,
         'scripts/qd_ed_final_runner.py','scripts/qd_ed_available_gpu_queue.py'}
PHASES={'validation':{'cohort_id':'N4_VALIDATION_C1_20260924','originals':60,'recoveries':4,'per_arm':20,'threshold':10},
        'formal':{'cohort_id':'N4_FORMAL_20260924','originals':40,'recoveries':2,'per_arm':10,'threshold':5}}
CHECKS=dev.CHECKS
FIELDS=('task_id','env_seed','policy_seed','init_index','profile','seed_block')


def api(r):return dev.api(r)
def sha_json(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def cell(row):return tuple(row[k] for k in FIELDS)
def sample(row):return tuple(row[k] for k in ('task_id','env_seed','policy_seed','init_index','seed_block'))


def read_ref(ref,plan,r):
    r.require(isinstance(ref,dict) and set(ref)=={'path','sha256'},'evaluation reference missing')
    path=r.owned(ref['path'],plan['artifact_root'])
    r.require(r.digest(path)==ref['sha256'],'evaluation reference changed')
    return r.read_json(path)


def frozen_report(r):
    r.require(r.digest(DEV_REPORT)==DEV_REPORT_SHA,'frozen Dev reporter changed')
    spec=importlib.util.spec_from_file_location('frozen_n4_dev_report',DEV_REPORT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def rows(seeds,phase):
    blocks=('validation_c1_b1','validation_c1_b2') if phase=='validation' else ('formal',)
    profiles=('C0','Q0','N4') if phase=='validation' else ('C0','Q0','N4','N4_QD_OFF')
    result=[]
    for block in blocks:
        for task in range(10):
            matched=[x for x in seeds['blocks'][block] if x['task_id']==task]
            if len(matched)!=1:raise ValueError('evaluation seed task missing/ambiguous')
            for profile in profiles:
                result.append({**{key:matched[0][key] for key in dev.FIELDS},'task_id':task,'profile':profile,
                    'episode_key':f'n4_{block}_t{task:02d}_{profile.lower()}_20260924',
                    'iteration':PHASES[phase]['cohort_id'],'split':phase,'seed_block':block,
                    'budget_bucket':phase,'timeout_seconds':1800})
    return result


def evaluation_profiles(observed,candidate,r):
    result=copy.deepcopy(observed)
    active=r.expand_candidate('N4',candidate,result['profiles']['Q0'])
    off=copy.deepcopy(active)
    for name in ('restored_profile','resolved_eds_config'):
        off[name]['qd_archive_mode']='none'
        off[name]['qd_final_selection_mode']='archive_global_best'
    off['static_override_values']['main.eds_config.qd_archive_mode']='none'
    off['static_override_values']['main.eds_config.qd_final_selection_mode']='archive_global_best'
    off['hydra_overrides']=[('main.eds_config.qd_archive_mode=none' if x.startswith('main.eds_config.qd_archive_mode=') else 'main.eds_config.qd_final_selection_mode=archive_global_best' if x.startswith('main.eds_config.qd_final_selection_mode=') else x) for x in off['hydra_overrides']]
    off['historical_label']='n4_total_qd_removed_ablation_v1'
    result['profiles']['N4_QD_OFF']=off
    return result


def source_identity(plan,runner):
    """Exact recorded source identity; plan release/recovery rows may differ."""
    r=api(runner);records=plan['code_files']
    files={x['path']:x['sha256'] for x in records}
    r.require(len(files)==len(records),'duplicate frozen source record')
    return {'source_commit':plan['source_commit'],'code_files':files}


def scientific_mapping(plan,root,r):
    c=plan['n4_evaluation'];base=read_ref(c['dev_plan'],plan,r)
    before=source_identity(base,r)['code_files']
    after=source_identity(plan,r)['code_files']
    r.require(set(before)<=set(after) and set(after)-set(before)<=TOOLING,
              'evaluation source inventory added/removed unapproved runtime files')
    r.require(all(after[name]==value for name,value in before.items() if name not in TOOLING),
              'evaluation production source changed from selected Dev candidate')
    r.require(c['source_mapping']=={'dev_source_commit':base['source_commit'],
        'evaluation_source_commit':plan['source_commit'],'allowed_tooling':sorted(TOOLING),
        'production_files':[{'path':p,'sha256':before[p]} for p in sorted(set(before)-TOOLING)]},
        'evaluation source mapping differs')
    for key in ('seed_plan_sha256','runtime_inventory_sha256','runtime_manifest_sha256','candidate_profiles'):
        r.require(plan[key]==base[key],'evaluation scientific/input/transport binding changed: '+key)
    for key in ('runtime_prerequisites','health_resources'):
        r.require(c[key]==base['n4_cohort'][key],'evaluation prior engineering proof attribution changed')
    candidate=r.read_json(root/dev.PROFILE)
    expected=evaluation_profiles(r.read_json(root/dev.OBSERVED),candidate,r)
    r.require(r.read_json(plan['profiles_path'])==expected,'evaluation controls/ablation profile differs')
    r.require(base['profiles_sha256']==r.digest(root/dev.OBSERVED),'Dev observed profile changed')
    fingerprint=sha_json({'production_files':c['source_mapping']['production_files'],
        'candidate_profiles':base['candidate_profiles'],'runtime_manifest_sha256':base['runtime_manifest_sha256'],
        'runtime_inventory_sha256':base['runtime_inventory_sha256'],'seed_plan_sha256':base['seed_plan_sha256']})
    r.require(c['candidate_fingerprint']==fingerprint,'selected scientific candidate fingerprint differs')
    return base


def binding(plan):
    c=plan['n4_evaluation']
    return {'cohort_id':c['cohort_id'],'phase':c['phase'],'protocol_sha256':PROTOCOL_SHA,
        'budget_clarification_sha256':CLARIFICATION_SHA,'candidate_fingerprint':c['candidate_fingerprint'],
        **{k:plan[k] for k in ('source_commit','profiles_sha256','runtime_manifest_sha256','runtime_inventory_sha256','seed_plan_sha256')},
        'candidate_sha256':plan['candidate_profiles']['N4']['sha256'],
        'boot_id':plan['boot_id'],'code_files_sha256':sha_json(plan['code_files']),
        'resource_authority':c['resource_authority'],'seed_exposure_review':c['seed_exposure_review']}


def validate_contract(plan,manifest,runtime,seeds,root,runner):
    r=api(runner);root=Path(root);c=plan.get('n4_evaluation',{});phase=c.get('phase')
    r.require(c.get('schema')==SCHEMA and phase in PHASES,'explicit evaluation contract required')
    r.require(c.get('cohort_id')==PHASES[phase]['cohort_id'] and c.get('limits')==PHASES[phase],
              'evaluation phase limits/identity differ')
    r.require(not plan.get('n4_cohort') and plan['seed_plan_sha256']==SEED_SHA,'evaluation must not relax Dev or seed contract')
    r.require(set(plan['candidate_profiles'])=={'N4'} and r.runtime_gpu(runtime)==3 and plan['boot_id']==dev.BOOT,'evaluation N4/GPU3/boot identity differs')
    resource_authority(plan,runtime,root,r,check_state=False)
    paths={x['path']:x['sha256'] for x in plan['code_files']}
    r.require(TOOLING<=set(paths) and paths[PROTOCOL]==PROTOCOL_SHA==r.digest(root/PROTOCOL),'evaluation tooling/protocol freeze missing')
    r.require(c.get('protocol')=={'path':PROTOCOL,'sha256':PROTOCOL_SHA},'evaluation protocol differs')
    r.require(paths.get(CLARIFICATION)==CLARIFICATION_SHA==r.digest(root/CLARIFICATION) and
        c.get('budget_clarification')=={'path':CLARIFICATION,'sha256':CLARIFICATION_SHA},
        'evaluation budget clarification freeze differs')
    r.require(c.get('dev_reporter')=={'path':str(DEV_REPORT),'sha256':DEV_REPORT_SHA},'Dev reporter binding differs')
    expected=rows(seeds,phase);originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    r.require(originals==expected,'evaluation exact matrix/order/seed identity differs')
    recoveries=[x for x in plan['episodes'] if x.get('retry_of')]
    r.require(len(recoveries)<=PHASES[phase]['recoveries'] and len({cell(x) for x in recoveries})==len(recoveries),'evaluation retry allowance differs')
    by_cell={cell(x):x for x in originals}
    for row in recoveries:
        r.require(cell(row) in by_cell,'recovery outside evaluation matrix')
        original=by_cell[cell(row)]
        skip={'episode_key','budget_bucket','retry_of','n4_evaluation_recovery_contract','recovery_release'}
        r.require({k:v for k,v in row.items() if k not in skip}=={k:v for k,v in original.items() if k not in skip}
            and row['budget_bucket']=='recovery' and row.get('n4_evaluation_recovery_contract')==binding(plan),
            'evaluation recovery binding differs')
        r.require(isinstance(row.get('recovery_release'),dict) and set(row['recovery_release'])=={'path','sha256'},
                  'evaluation recovery immutable certificate missing')
    closed={'dev':False,'validation':False,'formal':False}
    released={**closed,phase:True}
    r.require(plan.get('phase_authorization') in (closed,released),'evaluation phase gate differs')
    if plan.get('phase_authorization')==released:
        r.require(c.get('promotion_certificate') is not None,'promotion certificate missing')
    r.require(set(manifest['profiles'])=={'C0','Q0','N4','N4_QD_OFF'},'evaluation profile set differs')
    r.require(all(manifest['profiles'][p]['static_override_values'].get('main.decision_evidence.enabled') is True
                  for p in manifest['profiles']),'evaluation observer must remain common')
    scientific_mapping(plan,root,r)
    verify_seed_metadata(plan,root,r)


def recoverable(final,expected):
    if final.get('outcome_valid') is not False or final.get('n4_episode_dispatched') is not True:return False
    if final.get('n4_evaluation_frozen_identity')!=expected:return False
    if final.get('event')=='aborted' and final.get('retryable_infrastructure') is True:
        # Owned attribution alone cannot establish that Xid/native faults are
        # unrelated to the algorithm. Only these measured resource cases qualify.
        if final.get('reason')=='external GPU3 process appeared during owned attempt':return True
        if (final.get('reason')=='GPU3 nvidia-smi monitor query timed out after 15 seconds'
            and final.get('failure_detail')=='gpu_monitor_timeout'
            and final.get('gpu_monitor_timeout')=={'physical_gpu':3,'timeout_seconds':15}):return True
        return False
    e=final.get('n4_evaluation_recovery_eligibility',{})
    return (final.get('event')=='valid' and e.get('schema')=='qd-ed-n4-evaluation-recovery-eligibility-v1'
        and e.get('frozen_identity')==expected and e.get('reason')=='exact_codex_stage_transport_failure'
        and final.get('reason')==e.get('gate')==dev.TRANSPORT_GATE and final.get('compute_outcome')=='completed'
        and final.get('required_cost_telemetry_complete') is True and final.get('stage_backend')=='codex_cli'
        and final.get('provider_failed_calls',0)>0 and final.get('stage_failed_queries',0)>0)


def transport_eligibility(exc,outcome,plan,runner):
    r=api(runner)
    if (isinstance(exc,r.GateError) and str(exc)==dev.TRANSPORT_GATE and outcome.get('outcome_valid') is False
        and outcome.get('compute_outcome')=='completed' and outcome.get('required_cost_telemetry_complete') is True
        and outcome.get('stage_backend')=='codex_cli' and outcome.get('provider_failed_calls',0)>0 and outcome.get('stage_failed_queries',0)>0):
        return {'schema':'qd-ed-n4-evaluation-recovery-eligibility-v1','reason':'exact_codex_stage_transport_failure',
                'gate':dev.TRANSPORT_GATE,'frozen_identity':binding(plan)}
    return None


def retry_exception(events,row,runner):
    r=api(runner);b=row.get('n4_evaluation_recovery_contract',{})
    if b.get('phase') not in PHASES or b.get('cohort_id')!=PHASES[b['phase']]['cohort_id']:return False
    groups=r.event_groups(events)
    previous=[g for g in groups.values() if g[0]['identity']==r.episode_identity(row) and any(e['event']=='dispatched' for e in g)]
    return (len(previous)==1 and previous[0][0]['attempt_id']==row.get('retry_of') and not previous[0][0].get('retry_of')
            and previous[0][0].get('n4_evaluation_frozen_identity')==b and recoverable(previous[0][-1],b))


def recovery_release(plan,row,original,r):
    certificate=read_ref(row.get('recovery_release'),plan,r)
    r.require(certificate.get('schema')=='qd-ed-n4-evaluation-recovery-v1'
        and certificate.get('retry_of')==original['attempt_id'] and certificate.get('frozen_identity')==binding(plan),
        'evaluation recovery certificate identity differs')
    terminal=read_ref(certificate.get('original_terminal'),plan,r)
    r.require(terminal==original and recoverable(terminal,binding(plan)),
              'evaluation recovery certificate lacks exact eligible original terminal')


def reviewed_promotion(plan,events,root,runner):
    """Recompute the exact predecessor report, never trust a claimed release bool."""
    r=api(runner);c=plan['n4_evaluation'];certificate=read_ref(c.get('promotion_certificate'),plan,r)
    r.require(certificate.get('schema')=='qd-ed-n4-evaluation-promotion-v1'
        and certificate.get('target_phase')==c['phase']
        and certificate.get('target_binding')==binding(plan)
        and certificate.get('protocol_sha256')==PROTOCOL_SHA
        and certificate.get('candidate_fingerprint')==c['candidate_fingerprint'],
        'promotion certificate identity differs')
    report=read_ref(certificate.get('report'),plan,r)
    import qd_ed_n4_evaluation_report as er
    function=er.recompute_dev if c['phase']=='validation' else er.recompute
    computed,attempts,base=function(report['input_manifest'],root,r)
    r.require(all(report.get(k)==v for k,v in computed.items()),'promotion report differs from recomputed evidence')
    selected=read_ref(c['dev_plan'],plan,r)
    if c['phase']=='validation':
        r.require(computed.get('matrix')=='complete_valid_12'
            and computed.get('protocol_numeric_dev_criterion') is True
            and computed.get('protocol_execution_activity_criterion') is True
            and computed.get('input_scope_complete') is True,'Dev promotion incomplete/numeric/activity failure')
        predecessor=dev.COHORT
        candidate=computed['profiles']['N4']
        r.require(candidate.get('qd_active_chunks',0)>0 and
            candidate.get('n4_consumer_summary',{}).get('actual_prefix_different_decisions',0)>=1,
            'Dev promotion lacks substantive native QD/actual-prefix activity')
        reported_dev=base
    else:
        r.require(base['n4_evaluation']['phase']=='validation' and computed.get('complete') is True
            and computed.get('numeric_pass') is True and computed.get('input_scope_complete') is True,
            'validation promotion incomplete/numeric failure')
        r.require(base['n4_evaluation']['candidate_fingerprint']==c['candidate_fingerprint'],
            'candidate changed between validation/formal')
        reported_dev=read_ref(base['n4_evaluation']['dev_plan'],plan,r)
        predecessor=PHASES['validation']['cohort_id']
    r.require(source_identity(reported_dev,r)==source_identity(selected,r),
        'promotion reported Dev source differs from selected Dev source')
    for key in ('candidate_profiles','runtime_manifest_sha256','runtime_inventory_sha256','seed_plan_sha256'):
        r.require(base[key]==selected[key],'promotion selected candidate/input identity differs: '+key)
    # Include all predispatch terminals and invalid costs, not only successful dispatches.
    groups={k:g for k,g in r.event_groups(events).items() if g[0]['identity']['iteration']==predecessor}
    r.require(all(g[-1]['event'] in r.TERMINAL for g in groups.values()),'promotion predecessor in flight')
    supplied={a['terminal']['attempt_id']:a for a in attempts}
    r.require(len(supplied)==len(attempts) and set(groups)==set(supplied),
        'promotion terminal inventory differs from complete private journal')
    for key,g in groups.items():
        terminal=supplied[key]['terminal']
        r.require(all(g[-1].get(k)==v for k,v in terminal.items()),'promotion differs from authoritative terminal')
        r.require(terminal.get('n4_episode_dispatched') is any(x['event']=='dispatched' for x in g),
            'promotion dispatched presence differs from journal')
    review=read_ref(certificate.get('review'),plan,r)
    r.require(review.get('schema')=='qd-ed-n4-evaluation-scientific-review-v1'
        and review.get('report')==certificate['report']
        and review.get('candidate_fingerprint')==c['candidate_fingerprint']
        and review.get('checks')==dict.fromkeys(CHECKS,True),'reviewed scientific correctness evidence missing')
    evidence=review.get('evidence_by_check',{})
    r.require(set(evidence)==set(CHECKS) and all(isinstance(v,list) and v for v in evidence.values()),
        'scientific review evidence missing')
    for refs in evidence.values():
        for ref in refs:read_ref(ref,plan,r)
    return certificate


def allocate(plan,events,root,runner):
    """Caller owns global runner lease; state lock makes allocation/latch atomic."""
    r=api(runner);c=plan['n4_evaluation'];artifact=Path(plan['artifact_root'])
    folder=r.owned(artifact/'continuation_20260924/evaluation-allocations',artifact)
    name=c['cohort_id']+'.json';expected={'schema':'qd-ed-n4-evaluation-allocation-v1','binding':binding(plan)}
    with r.locked(Path(root)/'data/qd-ed-state.lock'):
        verify_seed_metadata(plan,root,r)
        fresh=r.read_events(Path(root)/'data/attempt-ledger.jsonl')
        r.require(fresh==events,'journal changed during evaluation allocation')
        if c['phase']=='validation':
            cells={(x['task_id'],x['env_seed']) for x in plan['episodes']}
            r.require(not any((x.get('identity',{}).get('task_id'),x.get('identity',{}).get('env_seed')) in cells
                and x.get('identity',{}).get('iteration')!=c['cohort_id'] for x in fresh),
                'validation c1 exposed by another cohort')
        folder.mkdir(parents=True,exist_ok=True)
        if c['phase']=='formal':
            latch=Path(root)/'data/qd-ed-final-candidate-latch.json'
            value={'schema':'qd-ed-final-candidate-latch-v1','candidate_fingerprint':c['candidate_fingerprint']}
            if latch.exists():r.require(r.read_json(latch)==value,'another final candidate already latched')
            else:
                r.require(not any(x.get('identity',{}).get('split')=='formal' and x.get('event') in {'reserved','dispatched'} for x in fresh),
                    'formal reservation exists without this candidate latch')
                r.durable_json(latch,value)
        destination=folder/name
        if destination.exists():r.require(r.read_json(destination)==expected,'evaluation allocation binding changed')
        else:
            if c['phase']=='validation':
                identities={(x['task_id'],x['env_seed']) for x in plan['episodes']}
                observed=set()
                for filename in ('exposure-registry.jsonl','historical-exposure-inventory.jsonl'):
                    for item in r.read_events(Path(root)/'data'/filename):
                        observed.add((item.get('task_id'),item.get('episode_seed')))
                for item in fresh:
                    identity=item.get('identity',{})
                    observed.add((identity.get('task_id'),identity.get('env_seed')))
                r.require(not identities.intersection(observed),'validation c1 already exposed; no silent cohort switch')
            r.durable_json(destination,expected)



def admission(plan,runtime,row,events,resources,root,runner,*,allocate_now=True,check_order=True):
    r=api(runner);c=plan['n4_evaluation'];phase=c['phase'];b=binding(plan)
    resource_authority(plan,runtime,root,r)
    require_scope(plan,root,r,row)
    r.require(plan['phase_authorization'].get(phase) is True and plan.get('frozen') is True,'evaluation phase not released')
    reviewed_promotion(plan,events,root,r)
    r.require(any(x==row for x in plan['episodes']),'evaluation row outside exact frozen plan')
    check_seed_exposure(plan,events,root,r)
    groups=[g for g in r.event_groups(events).values() if g[0]['identity']['iteration']==c['cohort_id']]
    r.require(all(g[-1]['event'] in r.TERMINAL for g in groups),'unfinished evaluation attempt')
    dispatched=[g for g in groups if any(e['event']=='dispatched' for e in g)]
    r.require(all(g[0].get('n4_evaluation_frozen_identity')==b and
        g[0].get('n4_evaluation_cohort_id')==c['cohort_id'] for g in groups),'evaluation prior binding differs')
    r.require(all(g[-1].get('n4_episode_dispatched') is any(x['event']=='dispatched' for x in g)
        for g in groups),'evaluation terminal dispatch marker differs')
    same=[g for g in dispatched if g[0]['identity']==r.episode_identity(row)]
    r.require(len(dispatched)<PHASES[phase]['originals']+PHASES[phase]['recoveries'] and len(same)<2,'evaluation dispatch allowance exhausted')
    if row.get('retry_of'):
        r.require(sum(bool(g[0].get('retry_of')) for g in dispatched)<PHASES[phase]['recoveries']
            and retry_exception(events,row,r),'evaluation recovery ineligible or exhausted')
        recovery_release(plan,row,same[0][-1],r)
    else:r.require(not same,'evaluation original already dispatched')
    originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    index=next(i for i,x in enumerate(originals) if cell(x)==cell(row))
    for earlier in originals[:index] if check_order else []:
        valid=[g[-1] for g in dispatched if g[0]['identity']==r.episode_identity(earlier) and g[-1]['event']=='valid' and g[-1].get('outcome_valid') is True]
        r.require(len(valid)==1,'evaluation prior cell invalid/incomplete')
        audit_path=r.owned(Path(valid[0]['output_dir'])/'eds_eval/decision-evidence-audit.json',plan['artifact_root'])
        audit=r.read_json(audit_path)
        verify_phase_audit(earlier,valid[0],audit,r)
    if allocate_now:allocate(plan,events,root,r)
    return {'n4_evaluation_cohort_id':c['cohort_id'],'n4_evaluation_frozen_identity':b}


_ACTIVE_SCOPE=None


@contextmanager
def supervised_dispatch(plan,keys,root,runner,queue,monitor,status_path,*,release_reference,plan_path,runtime):
    """An in-process capability, created only with the real lease and owned hooks.

    This is an accidental-entry guard, not a security boundary against arbitrary
    Python mutation. The frozen supervisor/source mapping supplies that trust.
    """
    global _ACTIVE_SCOPE
    r=api(runner);root=Path(root);saved=r.read_json(status_path)
    execution_release(release_reference,plan_path,plan,runtime,keys,root,r)
    pid,tid=os.getpid(),threading.get_ident();lock=root/'data/qd-ed-runner.lock'
    r.require(_ACTIVE_SCOPE is None,'evaluation supervisor scope already active')
    r.require(saved.get('status')=='shared_runner_acquired' and saved.get('pid')==pid
        and saved.get('owner_thread_id')==tid and saved.get('boot_id')==plan['boot_id']
        and Path(saved.get('runner_lock_path','')).resolve()==lock.resolve(),
        'evaluation verified shared lease status missing')
    st=lock.stat()
    r.require((saved.get('runner_lock_device'),saved.get('runner_lock_inode'))==(st.st_dev,st.st_ino),
              'evaluation shared lease inode differs')
    # A second open-file description must not acquire the real flock. The
    # reentrant path must then succeed in this exact owner process/thread.
    with lock.open('a+') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:pass
        else:
            fcntl.flock(stream,fcntl.LOCK_UN)
            raise r.GateError('evaluation real shared lease not held')
    with r.locked(lock,nonblocking=True):pass
    r.require(monitor.parent_pid==pid and monitor.root==root and monitor.episode_keys==frozenset(keys),
              'evaluation owned monitor scope differs')
    for function in (r.gpu_admission,r.wait_exclusively,queue.pending_gate):
        r.require(any(c.cell_contents is monitor for c in (function.__closure__ or ())),
                  'evaluation owned monitor hooks missing')
    r.require(Path(queue.bind_plan.__code__.co_filename).name=='qd_ed_n4_supervise.py' and queue.bind_plan.__name__=='bind',
              'evaluation frozen hardware hook missing')
    monitor.require_boot()
    scope={'pid':pid,'thread':tid,'root':root,'binding':binding(plan),'keys':frozenset(keys),
           'monitor':monitor,'queue':queue,'runner':r,
           'release_reference':copy.deepcopy(release_reference),'plan_path':Path(plan_path),
           'runtime':runtime,'ordered_keys':list(keys),
           'hooks':(r.locked,r.gpu_admission,r.wait_exclusively,r.run_plan,queue.pending_gate,queue.bind_plan)}
    _ACTIVE_SCOPE=scope
    try:yield
    finally:_ACTIVE_SCOPE=None


def require_scope(plan,root,r,row=None):
    r=api(r)
    scope=_ACTIVE_SCOPE
    r.require(scope is not None and scope['pid']==os.getpid() and scope['thread']==threading.get_ident()
        and scope['root']==Path(root) and scope['binding']==binding(plan),
        'protected evaluation requires dedicated owned supervisor scope')
    execution_release(scope['release_reference'],scope['plan_path'],plan,scope['runtime'],scope['ordered_keys'],root,r)
    q=scope['queue']
    r.require(scope['hooks']==(r.locked,r.gpu_admission,r.wait_exclusively,r.run_plan,q.pending_gate,q.bind_plan),
              'evaluation supervisor hooks changed')
    r.require(row is None or row['episode_key'] in scope['keys'],'episode outside evaluation supervisor scope')
    scope['monitor'].require_boot()
    with r.locked(Path(root)/'data/qd-ed-runner.lock',nonblocking=True):pass


class _BudgetPermission:
    """Opaque permission bound to one independently admitted row and journal view."""
    def __init__(self,plan,row,events,resources,root,base):
        self.plan,self.row,self.root=plan,copy.deepcopy(row),Path(root)
        self.events_sha,self.resources_sha=sha_json(events),sha_json(resources)
        self.base=base;self.scope=_ACTIVE_SCOPE


def validated_budget_context(plan,runtime,row,events,resources,root,runner,*,check_order=True):
    r=api(runner)
    base=admission(plan,runtime,row,events,resources,root,r,allocate_now=False,check_order=check_order)
    return _BudgetPermission(plan,row,events,resources,root,base)


def hour_reservation_exclusion(permission,state,events,row,resources,reservations,runner):
    r=api(runner)
    r.require(type(permission) is _BudgetPermission and permission.scope is not None
        and permission.scope is _ACTIVE_SCOPE,'unvalidated evaluation budget context')
    plan=permission.plan;phase=plan['n4_evaluation']['phase']
    require_scope(plan,permission.root,r,row)
    r.require(row==permission.row and sha_json(events)==permission.events_sha and sha_json(resources)==permission.resources_sha,
              'evaluation budget permission row/journal changed')
    r.require(row['split']==phase and (row['budget_bucket']==phase or
        (row['budget_bucket']=='recovery' and row.get('n4_evaluation_recovery_contract')==binding(plan))),
        'evaluation budget permission wrong phase')
    policy=state['budget'].get('gpu_hour_reservations',{'validation':14.,'formal':10.})
    if policy!={'validation':14.,'formal':10.}:
        verify_reservation_release(plan,state,events,resources,reservations,permission.root,r)
    return phase


def prepare_reservation_release(plan,events,resources,root,runner,*,healthcheck_inventory,rationale,time_unix):
    """Return a reviewable event only. Never append it or alter state/reservations.

    An explicit SHA-bound list recognizes every raw settled health resource at
    the release boundary. Unknown/new resources require engineering review;
    neither a guessed kind nor a favorable summary can silently omit its cost.
    """
    r=api(runner);c=plan['n4_evaluation']
    r.require(c['phase']=='formal','only completed validation can release its hour reservation for formal')
    r.require(bool(rationale) and isinstance(rationale,str) and type(time_unix) in (int,float)
        and math.isfinite(time_unix),'reservation release rationale/time missing')
    reviewed_promotion(plan,events,root,r)
    groups=r.event_groups(events)
    r.require(all(g[-1]['event'] in r.TERMINAL for g in groups.values()),'reservation release has unsettled episode cost')
    r.require(not any(g[0]['identity']['iteration']==c['cohort_id'] for g in groups.values()),
              'validation reservation release must precede formal allocation')
    normalized=[{**x,'attempt_id':x['resource_id'],'event':'valid' if x['event']=='completed' else x['event']} for x in resources]
    health=r.event_groups(normalized)
    r.require(all(g[-1]['event'] in r.TERMINAL for g in health.values()),'reservation release has unsettled healthcheck cost')
    inventory=read_ref(healthcheck_inventory,plan,r)
    r.require(inventory.get('schema')=='qd-ed-settled-healthcheck-inventory-v1','healthcheck recognition inventory missing')
    listed=inventory.get('resources',[])
    r.require(len(listed)==len({x['resource_id'] for x in listed}) and {x['resource_id'] for x in listed}==set(health),
              'reservation release contains unrecognized/missing healthchecks')
    actual={x['resource_id']:x for x in resources if x['event'] in {'completed','aborted'}}
    for entry in listed:
        r.require(read_ref(entry['terminal'],plan,r)==actual[entry['resource_id']],
                  'reservation release healthcheck terminal differs')
    snap=r.budget_snapshot(events,resources)  # Validates every raw duration, including failed work.
    return {'event':'gpu_hour_reservations_changed','gpu_hour_reservations':{'validation':0.,'formal':10.},
        'rationale':rationale,'time_unix':time_unix,
        'n4_evaluation_release':{'schema':'qd-ed-n4-validation-reservation-release-v1','formal_binding':binding(plan),
            'promotion_certificate':c['promotion_certificate'],'budget_clarification_sha256':CLARIFICATION_SHA,
            'settled_episode_prefix':{'count':len(events),'sha256':sha_json(events)},
            'settled_healthcheck_prefix':{'count':len(resources),'sha256':sha_json(resources)},
            'healthcheck_inventory':healthcheck_inventory,'raw_budget_snapshot':snap}}


def verify_reservation_release(plan,state,events,resources,reservations,root,runner):
    r=api(runner)
    r.require(bool(reservations),'evaluation reservation release ledger missing')
    event=reservations[-1];bound=event.get('n4_evaluation_release',{})
    r.require(event.get('gpu_hour_reservations')==state['budget'].get('gpu_hour_reservations')
        =={'validation':0.,'formal':10.} and bound.get('formal_binding')==binding(plan),
        'evaluation reservation release state/event/phase binding differs')
    prefixes=[]
    for name,full in (('settled_episode_prefix',events),('settled_healthcheck_prefix',resources)):
        info=bound.get(name,{})
        r.require(type(info.get('count')) is int and 0<=info['count']<=len(full),'reservation release prefix missing')
        prefix=full[:info['count']]
        r.require(sha_json(prefix)==info.get('sha256'),'reservation release raw ledger prefix differs')
        prefixes.append(prefix)
    expected=prepare_reservation_release(plan,*prefixes,root,r,healthcheck_inventory=bound.get('healthcheck_inventory'),
        rationale=event.get('rationale'),time_unix=event.get('time_unix'))
    r.require(event==expected,'reservation release certificate/evidence differs')


def resource_authority(plan,runtime,root,runner,*,check_state=True):
    """Read only this study's private authority; never inspect/mutate a peer."""
    r=api(runner);root=Path(root);refs=plan['n4_evaluation'].get('resource_authority',{})
    r.require(set(refs)=={'authorization','migration','validation'},'private resource authority missing')
    r.require(refs['authorization']['sha256']==ISOLATION_SHA,'private user budget authority differs')
    auth=read_ref(refs['authorization'],plan,r)
    studies=[s for s in auth.get('studies',[]) if s.get('study_id')==plan['run_name']]
    r.require(auth.get('schema')=='explicit-user-two-study-resource-isolation-v1' and len(studies)==1,
        'private study authorization missing')
    study=studies[0]
    r.require(study.get('artifact_root')==plan['artifact_root'] and study.get('worktree')==str(root)
        and study.get('physical_gpu')==3 and study.get('gpu_uuid')==runtime['gpu_mapping']['uuid']
        and study.get('max_episode_attempts')==240 and study.get('max_gpu_hours')==48
        and study.get('bucket_caps')==dev.ORIGINAL_CAPS
        and auth.get('max_owned_workers_per_study')==1,'private study budget/owner/GPU binding differs')
    migrated=read_ref(refs['migration'],plan,r);validation=read_ref(refs['validation'],plan,r)
    r.require(migrated.get('schema')=='two-study-resource-migration-v1'
        and migrated.get('authorization')==refs['authorization']
        and migrated.get('exact_owner_partition_verified') is True
        and migrated.get('source_plan_runtime_pointer_contract_unchanged') is True
        and validation.get('schema')=='two-study-resource-isolation-root-validation-v1'
        and validation.get('status')=='PASS' and validation.get('authorization')==refs['authorization']
        and validation.get('migration')==refs['migration'],'private migration validation differs')
    if check_state:
        state=r.read_state(root/'research-state.yaml');isolation=state.get('resource_isolation',{})
        r.require(state.get('run_name')==plan['run_name'] and state.get('artifacts')==plan['artifact_root']
            and isolation.get('status')=='ACTIVE' and isolation.get('private_budget') is True
            and isolation.get('owning_worktree_after_migration')==str(root)
            and all(isolation.get(k)==ref for k,ref in refs.items()),'private ACTIVE state/owner differs')
        r.require(state['budget']['reserved']==dev.ORIGINAL_CAPS and state['budget']['max_episode_attempts']==240
            and state['budget']['max_gpu_hours']==48 and r.authorized_gpu(state)==3,'private resource caps/GPU differ')
        for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl',
                     'qd-ed-runner.lock','qd-ed-state.lock'):
            path=root/'data'/name
            r.require(path.is_file() and not path.is_symlink() and path.stat().st_nlink==1,
                'private resource must be an owned local regular file: '+name)
    return refs


def check_retry(events,row,runner):
    r=api(runner)
    prior=[g for g in r.event_groups(events).values() if g[0]['identity']==r.episode_identity(row)
        and any(x['event']=='dispatched' for x in g)]
    if not prior:
        r.require(not row.get('retry_of'),'evaluation recovery has no dispatched parent')
        return
    r.require(row.get('retry_of') is not None and retry_exception(events,row,r),
        'evaluation repeat requires one exact eligible dispatched parent')


def whole_phase_budget(plan,state,events,resources,row,timeout,runner):
    r=api(runner);phase=plan['n4_evaluation']['phase'];limits=PHASES[phase]
    r.require(timeout==1800 and r.TERMINATION_GRACE_SECONDS==40,'evaluation requires full 1800+40; no clipping')
    r.require(state['budget']['reserved']==dev.ORIGINAL_CAPS and r.BUCKETS==dev.ORIGINAL_CAPS,
        'evaluation fixed bucket caps changed')
    snap=r.budget_snapshot(events,resources)
    groups=[g for g in r.event_groups(events).values() if g[0]['identity']['iteration']==limits['cohort_id']
        and any(x['event']=='dispatched' for x in g)]
    pending=[o for o in plan['episodes'] if not o.get('retry_of') and not any(
        r.episode_identity(o)==g[0]['identity'] for g in groups)]
    remaining_recoveries=limits['recoveries']-sum(bool(g[0].get('retry_of')) for g in groups)
    other='formal' if phase=='validation' else 'validation'
    reserve_other=max(0,dev.ORIGINAL_CAPS[other]-snap['by_bucket'][other])
    r.require(remaining_recoveries>=0 and snap['by_bucket'][phase]+len(pending)<=dev.ORIGINAL_CAPS[phase]
        and snap['by_bucket']['recovery']+remaining_recoveries<=dev.ORIGINAL_CAPS['recovery'],
        'evaluation remaining originals/recovery bucket capacity unavailable')
    r.require(snap['dispatched']+len(pending)+remaining_recoveries+reserve_other<=state['budget']['max_episode_attempts'],
        'evaluation cannot preserve all remaining original/recovery slots')


def verify_phase_audit(row,terminal,audit,runner):
    """No bundle reread: match saved audited native gates to exact guided metrics."""
    r=api(runner)
    r.require(audit.get('accepted') is True and audit.get('evidence_complete') is True,
        'evaluation prior audit incomplete')
    output=Path(terminal['output_dir']);metrics=r.read_events(output/'eds_eval/eds_metrics.jsonl')
    r.require(len(metrics)==terminal.get('metric_chunks')==terminal.get('guided_chunks'),
        'evaluation guided metric/compute count differs')
    if row['profile']=='N4':
        return dev.native_audit_alignment(audit,metrics,require=r.require)
    if row['profile']=='N4_QD_OFF':
        import audit_n4_qd_off_evidence as off
        return off.native_audit_alignment(audit,metrics,require=r.require)
    return {'status':'legacy_common_control'}


def execution_release(reference,plan_path,plan,runtime,keys,root,runner):
    r=api(runner);release=read_ref(reference,plan,r);c=plan['n4_evaluation']
    r.require(plan.get('frozen') is True and plan['phase_authorization']=={
        'dev':False,'validation':c['phase']=='validation','formal':c['phase']=='formal'},
        'evaluation phase remains closed')
    expected={'schema':'qd-ed-n4-evaluation-execution-release-v1','status':'authorized',
        'plan':{'path':str(Path(plan_path).resolve()),'sha256':r.digest(plan_path)},
        'frozen_identity':binding(plan),'source_identity':source_identity(plan,r),
        'candidate_profiles':plan['candidate_profiles'],'resource_authority':c['resource_authority'],
        'promotion_certificate':c['promotion_certificate'],'phase':c['phase'],
        'physical_gpu':3,'max_owned_GPU_workers':1,'gpu_mapping':runtime['gpu_mapping'],
        'episode_keys':list(keys),'limits':PHASES[c['phase']],
        'bucket_caps':dev.ORIGINAL_CAPS,'timeout_seconds':1800,'cleanup_seconds':40}
    r.require(release==expected,'evaluation execution release exact binding differs')
    rows_by_key={x['episode_key']:x for x in plan['episodes']}
    originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    r.require(keys and len(set(keys))==len(keys) and set(keys)<=set(rows_by_key),'evaluation release keys invalid')
    positions={cell(x):i for i,x in enumerate(originals)}
    order=[positions[cell(rows_by_key[k])] for k in keys]
    r.require(order==sorted(set(order)),'evaluation release cell order/duplicates differ')
    return release


def verify_seed_metadata(plan,root,runner):
    """Frozen pre-migration exposure sources remain scientific history.

    Their reviewed bytes are fixed; the private ledger is additionally checked
    at allocation. Changes need another prospective review, never an empty-ledger
    inference or silent seed-block substitution.
    """
    r=api(runner);reference=plan['n4_evaluation'].get('seed_exposure_review',{})
    r.require(reference.get('sha256')==SEED_REVIEW_SHA,'reviewed historical exposure provenance missing')
    review=read_ref(reference,plan,r)
    r.require(review.get('schema')=='n4-prospective-seed-exposure-metadata-review-v1'
        and review.get('phase_authorized') is False and review.get('known_seed_intersections')==[]
        and review.get('c1_cells')==20 and review.get('all_c1_init_rows_match_formal') is True,
        'provisional exposure metadata review differs')
    inputs=review.get('inputs',[])
    for name in ('exposure-registry.jsonl','historical-exposure-inventory.jsonl'):
        path=Path(root)/'data'/name
        refs=[x for x in inputs if Path(x['path']).resolve()==path.resolve()]
        r.require(len(refs)==1 and r.digest(path)==refs[0]['sha256'],
            'reviewed historical/rolling exposure source changed: '+name)
    r.require(any(x.get('sha256')==SEED_SHA and Path(x['path']).resolve()==Path(plan['seed_plan_path']).resolve()
        for x in inputs),'reviewed frozen seed metadata provenance missing')
    return review


def check_seed_exposure(plan,events,root,runner):
    """Read-only recheck usable by preparation and every admission under lease."""
    r=api(runner);c=plan['n4_evaluation'];verify_seed_metadata(plan,root,r)
    if c['phase']!='validation':return
    cells={(x['task_id'],x['env_seed']) for x in plan['episodes']}
    for name in ('exposure-registry.jsonl','historical-exposure-inventory.jsonl'):
        known={(x.get('task_id'),x.get('episode_seed')) for x in r.read_events(Path(root)/'data'/name)}
        r.require(not cells.intersection(known),'validation seeds already exposed in reviewed history')
    hits=[x for x in events if (x.get('identity',{}).get('task_id'),x.get('identity',{}).get('env_seed')) in cells]
    r.require(all(x['identity']['iteration']==c['cohort_id'] for x in hits),
        'validation seeds exposed by another own cohort')
    if hits:
        allocation=Path(plan['artifact_root'])/'continuation_20260924/evaluation-allocations'/(c['cohort_id']+'.json')
        expected={'schema':'qd-ed-n4-evaluation-allocation-v1','binding':binding(plan)}
        r.require(allocation.exists() and r.read_json(allocation)==expected,
            'validation reservation exists without this exact seed allocation')
