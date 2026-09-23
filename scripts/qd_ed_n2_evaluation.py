#!/usr/bin/env python3
"""Closed, conditional N2 evaluation contracts. No automatic phase release."""
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

import qd_ed_n2_plan as dev

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='qd-ed-n2-evaluation-v1'
PROTOCOL='experiments/iteration_002_executed_quality/runner/future-evaluation/protocol-v1.md'
PROTOCOL_SHA='75766ff02c4722c25f772e647937fc68cf9a3361129791585430115595f0e8fa'
CLARIFICATION='experiments/iteration_002_executed_quality/runner/future-evaluation/budget-entry-clarification-v1.md'
CLARIFICATION_SHA='9b1ccf9932f8fe2bf637d0e2a4674fae866740424ef523d83d665bac8c14c77c'
SEED_SHA='9bbcf7107f6be4f739870a034ea84c4695819bdc1bffe5aa1148f453acf4a6b1'
DEV_REPORT_SHA='8299647ed0ec904e230058a96a8d0b2d2714e2a3879341ea6917416093c3dfe2'
DEV_REPORT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n2-matrix-report/source-v1/summarize_matrix.py')
PROFILE='configs/qd_ed_final/n2_evaluation_profiles.json'
MODULE='scripts/qd_ed_n2_evaluation.py'
REPORT='scripts/qd_ed_n2_evaluation_report.py'
SUPERVISOR='scripts/qd_ed_n2_evaluate.py'
# Only these runtime files may differ from the frozen Dev code inventory.
# Tests/docs can be separately committed, but may not authorize production drift.
TOOLING={MODULE,REPORT,SUPERVISOR,PROFILE,PROTOCOL,CLARIFICATION,
         'scripts/qd_ed_final_runner.py','scripts/qd_ed_available_gpu_queue.py'}
PHASES={'validation':{'cohort_id':'N2_VALIDATION_C1_20260923','originals':60,'recoveries':4,'per_arm':20,'threshold':10},
        'formal':{'cohort_id':'N2_FORMAL_20260923','originals':40,'recoveries':2,'per_arm':10,'threshold':5}}
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
    spec=importlib.util.spec_from_file_location('frozen_n2_dev_report',DEV_REPORT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def rows(seeds,phase):
    blocks=('validation_c1_b1','validation_c1_b2') if phase=='validation' else ('formal',)
    profiles=('C0','Q0','N2') if phase=='validation' else ('C0','Q0','N2','N2_QD_OFF')
    result=[]
    for block in blocks:
        for task in range(10):
            matched=[x for x in seeds['blocks'][block] if x['task_id']==task]
            if len(matched)!=1:raise ValueError('evaluation seed task missing/ambiguous')
            for profile in profiles:
                result.append({**{key:matched[0][key] for key in dev.FIELDS},'task_id':task,'profile':profile,
                    'episode_key':f'n2_{block}_t{task:02d}_{profile.lower()}_20260923',
                    'iteration':PHASES[phase]['cohort_id'],'split':phase,'seed_block':block,
                    'budget_bucket':phase,'timeout_seconds':1800})
    return result


def evaluation_profiles(observed,candidate,r):
    result=copy.deepcopy(observed)
    active=r.expand_candidate('N2',candidate,result['profiles']['Q0'])
    off=copy.deepcopy(active)
    for name in ('restored_profile','resolved_eds_config'):
        off[name]['qd_archive_mode']='none'
    off['static_override_values']['main.eds_config.qd_archive_mode']='none'
    off['hydra_overrides']=[('main.eds_config.qd_archive_mode=none' if x.startswith('main.eds_config.qd_archive_mode=') else x) for x in off['hydra_overrides']]
    off['historical_label']='n2_executed_prefix_qd_removed_ablation_v1'
    result['profiles']['N2_QD_OFF']=off
    return result


def scientific_mapping(plan,root,r):
    c=plan['n2_evaluation'];base=read_ref(c['dev_plan'],plan,r)
    before={x['path']:x['sha256'] for x in base['code_files']}
    after={x['path']:x['sha256'] for x in plan['code_files']}
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
        r.require(c[key]==base['n2_cohort'][key],'evaluation prior engineering proof attribution changed')
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
    c=plan['n2_evaluation']
    return {'cohort_id':c['cohort_id'],'phase':c['phase'],'protocol_sha256':PROTOCOL_SHA,
        'budget_clarification_sha256':CLARIFICATION_SHA,'candidate_fingerprint':c['candidate_fingerprint'],
        **{k:plan[k] for k in ('source_commit','profiles_sha256','runtime_manifest_sha256','runtime_inventory_sha256','seed_plan_sha256')},
        'candidate_sha256':plan['candidate_profiles']['N2']['sha256']}


def validate_contract(plan,manifest,runtime,seeds,root,runner):
    r=api(runner);root=Path(root);c=plan.get('n2_evaluation',{});phase=c.get('phase')
    r.require(c.get('schema')==SCHEMA and phase in PHASES,'explicit evaluation contract required')
    r.require(c.get('cohort_id')==PHASES[phase]['cohort_id'] and c.get('limits')==PHASES[phase],
              'evaluation phase limits/identity differ')
    r.require(not plan.get('n2_cohort') and plan['seed_plan_sha256']==SEED_SHA,'evaluation must not relax Dev or seed contract')
    r.require(set(plan['candidate_profiles'])=={'N2'} and r.runtime_gpu(runtime)==3,'evaluation N2/GPU3 identity differs')
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
        skip={'episode_key','budget_bucket','retry_of','n2_evaluation_recovery_contract','recovery_release'}
        r.require({k:v for k,v in row.items() if k not in skip}=={k:v for k,v in original.items() if k not in skip}
            and row['budget_bucket']=='recovery' and row.get('n2_evaluation_recovery_contract')==binding(plan),
            'evaluation recovery binding differs')
        r.require(isinstance(row.get('recovery_release'),dict) and set(row['recovery_release'])=={'path','sha256'},
                  'evaluation recovery immutable certificate missing')
    closed={'dev':False,'validation':False,'formal':False}
    released={**closed,phase:True}
    r.require(plan.get('phase_authorization') in (closed,released),'evaluation phase gate differs')
    if plan.get('phase_authorization')==released:
        r.require(c.get('promotion_certificate') is not None,'promotion certificate missing')
    r.require(set(manifest['profiles'])=={'C0','Q0','N2','N2_QD_OFF'},'evaluation profile set differs')
    r.require(all(manifest['profiles'][p]['static_override_values'].get('main.decision_evidence.enabled') is True
                  for p in manifest['profiles']),'evaluation observer must remain common')
    scientific_mapping(plan,root,r)


def recoverable(final,expected):
    if final.get('outcome_valid') is not False:return False
    if final.get('n2_frozen_identity')!=expected:return False
    if final.get('event')=='aborted' and final.get('retryable_infrastructure') is True:
        # Owned attribution alone cannot establish that Xid/native faults are
        # unrelated to the algorithm. Only these measured resource cases qualify.
        if final.get('reason')=='external GPU3 process appeared during owned attempt':return True
        if (final.get('reason')=='GPU3 nvidia-smi monitor query timed out after 15 seconds'
            and final.get('failure_detail')=='gpu_monitor_timeout'
            and final.get('gpu_monitor_timeout')=={'physical_gpu':3,'timeout_seconds':15}):return True
        return False
    e=final.get('n2_recovery_eligibility',{})
    return (final.get('event')=='valid' and e.get('schema')=='qd-ed-n2-recovery-eligibility-v1'
        and e.get('frozen_identity')==expected and e.get('reason')=='exact_codex_stage_transport_failure'
        and final.get('reason')==e.get('gate')==dev.TRANSPORT_GATE and final.get('compute_outcome')=='completed'
        and final.get('required_cost_telemetry_complete') is True and final.get('stage_backend')=='codex_cli'
        and final.get('provider_failed_calls',0)>0 and final.get('stage_failed_queries',0)>0)


def transport_eligibility(exc,outcome,plan,runner):
    r=api(runner)
    if (isinstance(exc,r.GateError) and str(exc)==dev.TRANSPORT_GATE and outcome.get('outcome_valid') is False
        and outcome.get('compute_outcome')=='completed' and outcome.get('required_cost_telemetry_complete') is True
        and outcome.get('stage_backend')=='codex_cli' and outcome.get('provider_failed_calls',0)>0 and outcome.get('stage_failed_queries',0)>0):
        return {'schema':'qd-ed-n2-recovery-eligibility-v1','reason':'exact_codex_stage_transport_failure',
                'gate':dev.TRANSPORT_GATE,'frozen_identity':binding(plan)}
    return None


def retry_exception(events,row,runner):
    r=api(runner);b=row.get('n2_evaluation_recovery_contract',{})
    if b.get('phase') not in PHASES or b.get('cohort_id')!=PHASES[b['phase']]['cohort_id']:return False
    groups=r.event_groups(events)
    previous=[g for g in groups.values() if g[0]['identity']==r.episode_identity(row) and any(e['event']=='dispatched' for e in g)]
    return (len(previous)==1 and previous[0][0]['attempt_id']==row.get('retry_of') and not previous[0][0].get('retry_of')
            and previous[0][0].get('n2_frozen_identity')==b and recoverable(previous[0][-1],b))


def recovery_release(plan,row,original,r):
    certificate=read_ref(row.get('recovery_release'),plan,r)
    r.require(certificate.get('schema')=='qd-ed-n2-evaluation-recovery-v1'
        and certificate.get('retry_of')==original['attempt_id'] and certificate.get('frozen_identity')==binding(plan),
        'evaluation recovery certificate identity differs')
    terminal=read_ref(certificate.get('original_terminal'),plan,r)
    r.require(terminal==original and recoverable(terminal,binding(plan)),
              'evaluation recovery certificate lacks exact eligible original terminal')


def reviewed_promotion(plan,events,root,runner):
    """Recompute SHA-bound report inputs; a claimed boolean cannot release a phase."""
    r=api(runner);c=plan['n2_evaluation'];certificate=read_ref(c.get('promotion_certificate'),plan,r)
    r.require(certificate.get('schema')=='qd-ed-n2-evaluation-promotion-v1' and certificate.get('target_phase')==c['phase']
        and certificate.get('candidate_fingerprint')==c['candidate_fingerprint']
        and certificate.get('protocol_sha256')==PROTOCOL_SHA
        and certificate.get('budget_clarification_sha256')==CLARIFICATION_SHA
        and certificate.get('target_binding')==binding(plan),'promotion certificate identity differs')
    report=read_ref(certificate.get('report'),plan,r)
    if c['phase']=='validation':
        d=frozen_report(r);m=report['input_manifest'];r.require(m['script_sha256']==DEV_REPORT_SHA,'promotion reporter differs')
        authorization=d.read_ref(m['authorization'])
        r.require(m['protocol_sha256']==r.digest(DEV_REPORT.with_name('protocol.md')) and
            authorization.get('script')=={'path':str(DEV_REPORT),'sha256':DEV_REPORT_SHA}
            and authorization.get('protocol_sha256')==m['protocol_sha256']
            and authorization.get('base_plan_sha256')==d.BASE_PLAN_SHA,'promotion report authorization differs')
        r.require(m['base_plan']['sha256']==d.BASE_PLAN_SHA and m.get('input_scope_complete') is True,'incomplete Dev report scope')
        base=d.read_ref(m['base_plan']);plans={m['base_plan']['sha256']:base}
        for reference in m.get('plan_revisions',[]):
            revision=d.read_ref(reference)
            r.require(d.plan_contract(revision)==d.plan_contract(base) and all(revision[k]==base[k] for k in d.BINDING)
                and revision['candidate_profiles']==base['candidate_profiles'],'promotion Dev revision identity differs')
            plans[reference['sha256']]=revision
        attempts=[d.load_attempt(spec,plans) for spec in m['attempts']]
        computed=d.summarize(base,attempts)
        r.require(all(report.get(k)==value for k,value in computed.items()),'promotion report differs from recomputed Dev evidence')
        r.require(computed['matrix']=='complete_valid_30' and computed['protocol_numeric_dev_criterion'] is True,'Dev promotion incomplete/numeric failure')
        predecessor=dev.COHORT
    else:
        import qd_ed_n2_evaluation_report as er
        computed,attempts,base=er.recompute(report['input_manifest'],root,r)
        r.require(all(report.get(k)==value for k,value in computed.items()),'promotion report differs from recomputed validation evidence')
        r.require(base['n2_evaluation']['phase']=='validation' and computed['complete'] and computed['numeric_pass'] is True,'validation promotion incomplete/numeric failure')
        r.require(base['n2_evaluation']['candidate_fingerprint']==c['candidate_fingerprint'],'candidate changed between validation/formal')
        predecessor=PHASES['validation']['cohort_id']
    selected_base=read_ref(c['dev_plan'],plan,r)
    r.require(all(base[k]==selected_base[k] for k in ('candidate_profiles','runtime_manifest_sha256','runtime_inventory_sha256','seed_plan_sha256')),
              'promotion evidence does not bind selected candidate inputs')
    observations=[a['metrics'] for a in attempts if a['status']=='complete_valid' and a['terminal']['identity']['profile']=='N2']
    r.require(any(m['qd_active_chunks']>0 and m['n2']['applicable_chunks']>0 and m['n2']['quality_changed_candidates']>0
        for m in observations),'promotion lacks observed QD/quality activity')
    actual={g[0]['attempt_id'] for g in r.event_groups(events).values() if g[0]['identity']['iteration']==predecessor
        and any(e['event']=='dispatched' for e in g)}
    supplied={a['terminal']['attempt_id'] for a in attempts}
    r.require(actual==supplied,'promotion terminal inventory differs from full dispatched journal')
    journal=r.event_groups(events)
    for attempt in attempts:
        terminal=attempt['terminal'];original=journal[terminal['attempt_id']][-1]
        r.require(all(original.get(k)==v for k,v in terminal.items()),'promotion result differs from raw authoritative terminal')
    review=read_ref(certificate.get('review'),plan,r)
    r.require(review.get('schema')=='qd-ed-n2-scientific-review-v1' and review.get('report')==certificate['report']
        and review.get('candidate_fingerprint')==c['candidate_fingerprint'] and review.get('checks')=={k:True for k in CHECKS},
        'reviewed scientific correctness/activation evidence missing')
    evidence=review.get('evidence_by_check',{})
    r.require(set(evidence)==set(CHECKS) and all(isinstance(v,list) and v for v in evidence.values()),'scientific review evidence missing')
    for references in evidence.values():
        for ref in references:read_ref(ref,plan,r)
    return certificate


def allocate(plan,events,root,runner):
    """Caller owns global runner lease; state lock makes allocation/latch atomic."""
    r=api(runner);c=plan['n2_evaluation'];artifact=Path(plan['artifact_root'])
    folder=r.owned(artifact/'continuation_20260923/evaluation-allocations',artifact)
    name=c['cohort_id']+'.json';expected={'schema':'qd-ed-n2-evaluation-allocation-v1','binding':binding(plan)}
    with r.locked(Path(root)/'data/qd-ed-state.lock'):
        fresh=r.read_events(Path(root)/'data/attempt-ledger.jsonl')
        r.require(fresh==events,'journal changed during evaluation allocation')
        if c['phase']=='validation':
            cells={(x['task_id'],x['env_seed']) for x in plan['episodes']}
            r.require(not any((x.get('identity',{}).get('task_id'),x.get('identity',{}).get('env_seed')) in cells
                and x.get('identity',{}).get('iteration')!=c['cohort_id'] for x in fresh),
                'validation c1 exposed by another cohort')
        folder.mkdir(parents=True,exist_ok=True)
        if c['phase']=='formal':
            latch=folder/'formal-candidate-latch.json'
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
    r=api(runner);c=plan['n2_evaluation'];phase=c['phase'];b=binding(plan)
    require_scope(plan,root,r,row)
    r.require(plan['phase_authorization'].get(phase) is True and plan.get('frozen') is True,'evaluation phase not released')
    reviewed_promotion(plan,events,root,r)
    r.require(any(x==row for x in plan['episodes']),'evaluation row outside exact frozen plan')
    groups=[g for g in r.event_groups(events).values() if g[0]['identity']['iteration']==c['cohort_id']]
    r.require(all(g[-1]['event'] in r.TERMINAL for g in groups),'unfinished evaluation attempt')
    dispatched=[g for g in groups if any(e['event']=='dispatched' for e in g)]
    r.require(all(g[0].get('n2_frozen_identity')==b for g in dispatched),'evaluation prior binding differs')
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
        r.require(audit.get('accepted') is True and audit.get('evidence_complete') is True,'evaluation prior audit incomplete')
    if allocate_now:allocate(plan,events,root,r)
    return {'n2_cohort_id':c['cohort_id'],'n2_frozen_identity':b}


_ACTIVE_SCOPE=None


@contextmanager
def supervised_dispatch(plan,keys,root,runner,queue,monitor,status_path):
    """An in-process capability, created only with the real lease and owned hooks.

    This is an accidental-entry guard, not a security boundary against arbitrary
    Python mutation. The frozen supervisor/source mapping supplies that trust.
    """
    global _ACTIVE_SCOPE
    r=api(runner);root=Path(root);saved=r.read_json(status_path)
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
    r.require(queue.bind_plan.__module__=='qd_ed_n2_supervise' and queue.bind_plan.__name__=='bind',
              'evaluation frozen hardware hook missing')
    monitor.require_boot()
    scope={'pid':pid,'thread':tid,'root':root,'binding':binding(plan),'keys':frozenset(keys),
           'monitor':monitor,'queue':queue,'runner':r,
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
    plan=permission.plan;phase=plan['n2_evaluation']['phase']
    require_scope(plan,permission.root,r,row)
    r.require(row==permission.row and sha_json(events)==permission.events_sha and sha_json(resources)==permission.resources_sha,
              'evaluation budget permission row/journal changed')
    r.require(row['split']==phase and (row['budget_bucket']==phase or
        (row['budget_bucket']=='recovery' and row.get('n2_evaluation_recovery_contract')==binding(plan))),
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
    r=api(runner);c=plan['n2_evaluation']
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
        'n2_evaluation_release':{'schema':'qd-ed-n2-validation-reservation-release-v1','formal_binding':binding(plan),
            'promotion_certificate':c['promotion_certificate'],'budget_clarification_sha256':CLARIFICATION_SHA,
            'settled_episode_prefix':{'count':len(events),'sha256':sha_json(events)},
            'settled_healthcheck_prefix':{'count':len(resources),'sha256':sha_json(resources)},
            'healthcheck_inventory':healthcheck_inventory,'raw_budget_snapshot':snap}}


def verify_reservation_release(plan,state,events,resources,reservations,root,runner):
    r=api(runner)
    r.require(bool(reservations),'evaluation reservation release ledger missing')
    event=reservations[-1];bound=event.get('n2_evaluation_release',{})
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
