#!/usr/bin/env python3
"""N3's closed Dev contract and CPU-only unfrozen plan preparation.

No GPU/provider/model call, freeze, dispatch, state or ledger write is provided.
"""
import argparse
import copy
import importlib.util
import json
import hashlib
import os
import threading
import fcntl
from contextlib import contextmanager
from pathlib import Path
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
COHORT = 'N3_EXECUTED_FEEDBACK_DEV_20260923'
PROTOCOL = 'experiments/iteration_003_executed_feedback/protocol.md'
# Original study-wide interpretation: healthchecks count hours, not episode attempts.
CLARIFICATION = 'experiments/iteration_002_executed_quality/accounting-clarification.md'
ALLOCATION = 'experiments/iteration_003_executed_feedback/accounting-clarification.md'
BUDGET_ALLOCATION = {'original_by_profile':{'C0':'baseline','Q0':'development','N3':'development'},
                     'retry_bucket':'recovery'}
PROFILE = 'configs/qd_ed_final/candidate_n3.json'
OBSERVED = 'configs/qd_ed_final/n3_observed_baseline_profiles.json'
MODULE = 'scripts/qd_ed_n3_plan.py'
SUPERVISOR = 'scripts/qd_ed_n3_supervise.py'
REPORT = 'scripts/qd_ed_n3_report.py'
SUPPORT = 'docs/03_evidence/qd_ed_final/continuation_20260923/observed-pairs-draft/supervisor-support.py'
DEPENDENCIES = 'docs/03_evidence/qd_ed_final/continuation_20260923/freshboot-model-first/native-dependency-freeze.json'
BOOT = '2a1fa95f-ab0d-488c-a298-fc488ddd2af7'
PREREQUISITES = {'health_result','health_contract','common_result','common_process','common_kernel'}
LIMITS = {'episode_dispatches': 34, 'unique_cells': 30, 'recoveries': 4,
          'dispatches_per_cell': 2, 'new_gpu_hours': 8., 'timeout_seconds': 1800,
          'cleanup_seconds': 40, 'physical_gpu': 3}
FIELDS = ('env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256')
TRANSPORT_GATE = 'Codex Stage call failure invalidates the frozen transport condition'
CHECKS = ('finite_action','source_compute','raw_stage_separation','substantive_qd_activation',
          'exact_native_past_feedback_timing_selection','native_feedback_bundle_alignment',
          'runtime_tracking_validity','substantive_feedback_search_activity')
NATIVE_AUDIT_SCOPE = ('recognized N3 decisions; native canonical selected projection/origin/raw; '
    'nonterminal acknowledged command/EEF; immediate complete predecessor/residual; '
    'explicit inactive clears and terminal endpoints are excluded from usable feedback; no task-effect claim')
REQUIRED = {MODULE, SUPERVISOR, REPORT, SUPPORT, DEPENDENCIES, PROFILE, OBSERVED, PROTOCOL, CLARIFICATION, ALLOCATION, 'core/qd_executed_quality.py','core/qd_executed_feedback.py',
            'main.py','core/keypoint_tracker.py','core/env_adapters/libero_adapter.py',
            'core/qd_ed.py','core/rdt_policy_steer.py','core/eds_eval_metrics.py','configs/config.yaml',
            'scripts/qd_ed_available_gpu_queue.py','scripts/qd_ed_gpu_probe.py','scripts/qd_ed_runtime_setup.py',
            'scripts/audit_decision_evidence.py'}


def api(value): return SimpleNamespace(**value) if isinstance(value, dict) else value


def native_audit_alignment(audit, metrics, *, require):
    """Match the frozen native auditor to public metrics; no tensor reread or activity release."""
    require(audit.get('accepted') is True and audit.get('evidence_complete') is True,
            'N3 native alignment requires accepted complete audit')
    require(all(m.get('qd_quality_mode')=='executed_feedback_v1'
        and type(m.get('qd_quality_applicable')) is bool and type(m.get('qd_feedback_active')) is bool
        and (not m['qd_feedback_active'] or m['qd_quality_applicable']) for m in metrics),
        'N3 native alignment metric applicability/active fields differ')
    recognized=sum(m['qd_quality_applicable'] for m in metrics)
    active=sum(m['qd_feedback_active'] for m in metrics)
    gate=audit.get('n3_feedback_audit')
    if not recognized:
        require(gate is None,'N3 native audit unexpectedly claims unrecognized decisions')
        return {'status':'not_applicable','recognized_decisions':0,'active_decisions':0,
                'scope':NATIVE_AUDIT_SCOPE,'search_activity_or_checkpoint_release':False}
    counters=('checked_decisions','active_previous_ack_verified','inactive_decisions','uncommitted_clears',
              'inactive_ack_clears_unknown','complete_nonterminal_prefixes')
    require(isinstance(gate,dict) and gate.get('schema')=='n3-native-feedback-audit-v1'
        and gate.get('scope')==NATIVE_AUDIT_SCOPE,'N3 native feedback audit schema/scope missing or differs')
    require(all(type(gate.get(k)) is int and 0<=gate[k]<=recognized for k in counters)
        and gate['checked_decisions']==recognized and gate['active_previous_ack_verified']==active
        and gate['inactive_decisions']==recognized-active,'N3 native feedback audit counts differ from metrics')
    return {'status':'verified','recognized_decisions':recognized,'active_decisions':active,
            'audit':copy.deepcopy(gate),'search_activity_or_checkpoint_release':False}


def rows_from_dev(seeds):
    rows=[]
    for task in range(10):
        matches=[x for x in seeds['blocks']['dev'] if x['task_id']==task]
        if len(matches)!=1: raise ValueError('frozen Dev task missing/ambiguous')
        for profile in ('C0','Q0','N3'):
            rows.append({**{key:matches[0][key] for key in FIELDS},'task_id':task,'profile':profile,
                'episode_key':f'n3_dev_t{task:02d}_{profile.lower()}_20260923','iteration':COHORT,
                'split':'dev','seed_block':'dev','budget_bucket':BUDGET_ALLOCATION['original_by_profile'][profile],'timeout_seconds':1800})
    return rows


def observed_profiles(baseline, baseline_sha):
    result=copy.deepcopy(baseline)
    result['observation_condition']={'name':'n3_common_decision_observed_v1',
        'baseline_path':'configs/qd_ed_final/baseline_profiles.json','baseline_sha256':baseline_sha}
    for profile in result['profiles'].values():
        profile['static_override_values']['main.decision_evidence.enabled']=True
        profile['hydra_overrides'].append('main.decision_evidence.enabled=true')
        profile['historical_label']+='__n3_common_decision_observed_v1'
    return result


def source_identity(plan):
    return hashlib.sha256(json.dumps(plan['code_files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()


def binding(plan, runtime):
    contract=plan['n3_cohort']
    return {'cohort_id':COHORT,'protocol_sha256':contract['protocol']['sha256'],
        'accounting_clarification_sha256':contract['accounting_clarification']['sha256'],
        **{k:plan[k] for k in ('source_commit','profiles_sha256','runtime_manifest_sha256',
                             'runtime_inventory_sha256','seed_plan_sha256')},
        'candidate_sha256':plan['candidate_profiles']['N3']['sha256'],
        'stage_public_config_sha256':runtime['frozen_stage_provider']['public_config_sha256'],
        'source_files_sha256':source_identity(plan),
        'resource_contract_sha256':hashlib.sha256(json.dumps({key:contract[key] for key in
            ('limits','health_resources','runtime_prerequisites','budget_allocation','budget_allocation_amendment')},sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    r=api(runner); root=Path(root); contract=plan.get('n3_cohort',{})
    r.require(not any(k in plan for k in ('n2_cohort','n2_evaluation','native_probe_contract','diagnostic_only')),
              'N3 cannot reuse another cohort or diagnostic authorization')
    r.require(contract.get('schema')=='qd-ed-n3-cohort-v1' and contract.get('cohort_id')==COHORT,
              'N3 requires its explicit prospective cohort contract')
    r.require(contract.get('limits')==LIMITS, 'N3 local resource limits differ')
    r.require(contract.get('budget_allocation')==BUDGET_ALLOCATION,'N3 original-arm budget allocation differs')
    r.require(plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}, 'N3 Dev-only phase gate differs')
    paths={x['path']:x['sha256'] for x in plan['code_files']}
    r.require(REQUIRED<=set(paths), 'N3 runtime source fingerprints missing')
    r.require(len(paths)==len(plan['code_files']), 'N3 duplicate source fingerprints')
    for key,relative in [('protocol',PROTOCOL),('accounting_clarification',CLARIFICATION),('budget_allocation_amendment',ALLOCATION)]:
        r.require(contract.get(key)=={'path':relative,'sha256':paths[relative]} and
                  r.digest(root/relative)==paths[relative], 'N3 protocol/clarification differs')
    r.require(set(plan['candidate_profiles'])=={'N3'}, 'N3 matrix cannot include another candidate')
    r.require(r.runtime_gpu(runtime)==3 and runtime['frozen_stage_provider'].get('backend')=='codex_cli',
              'N3 requires GPU3 and frozen Codex transport')
    baseline_path=root/'configs/qd_ed_final/baseline_profiles.json'
    candidate=r.read_json(root/PROFILE)
    r.require(candidate.get('baseline_provenance')=={'path':'configs/qd_ed_final/baseline_profiles.json',
        'profile':'Q0.restored_profile','sha256':r.digest(baseline_path)} and candidate.get('action_chunk_horizon')==8,
        'N3 baseline provenance/horizon differs')
    expected=observed_profiles(r.read_json(baseline_path),r.digest(baseline_path))
    r.require(Path(plan['profiles_path']).resolve()==(root/OBSERVED).resolve() and
              r.read_json(plan['profiles_path'])==expected,'N3 common observed baseline drift')
    r.require(all(manifest['profiles'][p]['static_override_values']['main.decision_evidence.enabled'] is True
                  for p in ('C0','Q0','N3')),'N3 common observer is required')
    expected_rows=rows_from_dev(seeds); originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    r.require(originals==expected_rows,'N3 original 30 cells/order/seeds differ')
    recoveries=[x for x in plan['episodes'] if x.get('retry_of')]
    r.require(len(recoveries)<=4,'N3 recovery plan exceeds four')
    identities={json.dumps(r.episode_identity(x),sort_keys=True):x for x in expected_rows}
    used=set()
    for row in recoveries:
        identity=json.dumps(r.episode_identity(row),sort_keys=True)
        r.require(identity in identities and identity not in used,'N3 recovery scientific cell missing/repeated')
        used.add(identity); original=identities[identity]
        actual={k:v for k,v in row.items() if k not in {'episode_key','retry_of','n3_recovery_contract','budget_bucket'}}
        reference={k:v for k,v in original.items() if k not in {'episode_key','budget_bucket'}}
        r.require(actual==reference and row['budget_bucket']=='recovery' and row['episode_key']!=original['episode_key']
            and row.get('n3_recovery_contract')==binding(plan,runtime),'N3 recovery frozen identity differs')
    resources=contract.get('health_resources',[])
    r.require(isinstance(resources,list) and len({x['resource_id'] for x in resources})==len(resources)
        and all(set(x)=={'resource_id','scope'} and x['scope'] in {'reused_prior','new_n3'} for x in resources),
        'N3 health resource attribution differs')
    proof=runtime.get('cuda_egl_probe',{}).get('resource_id')
    r.require(proof and proof in {x['resource_id'] for x in resources},'N3 runtime proof must be explicitly attributed')
    prerequisites=contract.get('runtime_prerequisites',{})
    r.require(plan.get('boot_id')==BOOT and prerequisites.get('boot_id')==BOOT and
        prerequisites.get('reuse_scope')=='prior_engineering_only_not_N3_algorithm_validation' and
        set(prerequisites.get('references',{}))==PREREQUISITES and
        prerequisites.get('native_dependencies')=={'path':DEPENDENCIES,'sha256':paths[DEPENDENCIES]},
        'N3 current-boot engineering prerequisites missing/different')


def read_attestation(reference, plan, root, r, schema):
    r.require(isinstance(reference,dict) and set(reference)=={'path','sha256'},'N3 attestation not released')
    path=r.owned(reference['path'],plan['artifact_root'])
    r.require(r.digest(path)==reference['sha256'],'N3 attestation fingerprint differs')
    value=r.read_json(path)
    r.require(value.get('schema')==schema and value.get('cohort_id')==COHORT and
        value.get('source_commit')==plan['source_commit'] and
        value.get('source_files_sha256')==source_identity(plan) and
        value.get('protocol_sha256')==plan['n3_cohort']['protocol']['sha256'], 'N3 attestation identity differs')
    evidence=value.get('evidence')
    r.require(isinstance(evidence,list) and evidence,'N3 attestation evidence missing')
    for item in evidence:
        path=r.owned(item['path'],plan['artifact_root'])
        r.require(r.digest(path)==item['sha256'],'N3 attestation evidence changed')
    return value


def transport_recovery_eligibility(exc, outcome, plan, row, runtime, runner):
    """Separate prospective eligibility; never rewrite the original outcome."""
    r=api(runner)
    if not plan.get('n3_cohort') or not isinstance(exc,r.GateError) or str(exc)!=TRANSPORT_GATE:
        return None
    if (outcome.get('outcome_valid') is not False or outcome.get('compute_outcome')!='completed'
            or outcome.get('required_cost_telemetry_complete') is not True
            or outcome.get('stage_backend')!='codex_cli'
            or outcome.get('provider_failed_calls',0)<=0
            or outcome.get('stage_failed_queries',0)<=0):
        return None
    return {'schema':'qd-ed-n3-recovery-eligibility-v1','reason':'exact_codex_stage_transport_failure',
            'gate':TRANSPORT_GATE,'frozen_identity':binding(plan,runtime)}


def recoverable(final, expected):
    """Exact prospective causes only; raw legacy infrastructure labels are insufficient."""
    if final.get('outcome_valid') is not False or final.get('n3_frozen_identity') != expected:
        return False
    if final.get('event') == 'aborted' and final.get('retryable_infrastructure') is True:
        if final.get('reason') == 'external GPU3 process appeared during owned attempt':
            return True
        return (final.get('reason') == 'GPU3 nvidia-smi monitor query timed out after 15 seconds'
            and final.get('failure_detail') == 'gpu_monitor_timeout'
            and final.get('gpu_monitor_timeout') == {'physical_gpu':3,'timeout_seconds':15})
    eligible=final.get('n3_recovery_eligibility',{})
    return (final.get('event')=='valid' and final.get('compute_outcome')=='completed'
        and final.get('required_cost_telemetry_complete') is True
        and final.get('stage_backend')=='codex_cli' and final.get('provider_failed_calls',0)>0
        and final.get('stage_failed_queries',0)>0 and final.get('reason')==TRANSPORT_GATE
        and eligible=={'schema':'qd-ed-n3-recovery-eligibility-v1','reason':'exact_codex_stage_transport_failure',
                       'gate':TRANSPORT_GATE,'frozen_identity':expected})


def check_retry(events, row, runner):
    r=api(runner); groups=r.event_groups(events)
    prior=[g for g in groups.values() if g[0]['identity']==r.episode_identity(row)
           and any(e['event']=='dispatched' for e in g)]
    if not prior:
        r.require(not row.get('retry_of'), 'N3 retry has no dispatched predecessor')
        return
    certificate=row.get('n3_recovery_contract',{})
    r.require(len(prior)==1 and certificate.get('cohort_id')==COHORT
        and str(row['iteration'])==COHORT and row.get('retry_of')==prior[0][0]['attempt_id']
        and prior[0][0].get('n3_frozen_identity')==certificate
        and prior[0][0].get('n3_cohort_id')==COHORT and not prior[0][0].get('retry_of')
        and recoverable(prior[0][-1],certificate), 'N3 prior outcome cannot be retried')
    r.require(not any(g[0].get('retry_of')==row['retry_of'] and any(e['event']=='dispatched' for e in g)
                      for g in groups.values()),'N3 retry already consumed')


def protected_budget(state, events, resources, row, timeout, runner):
    r=api(runner); snap=r.budget_snapshot(events,resources); budget=state['budget']
    r.require(timeout==1800 and r.TERMINATION_GRACE_SECONDS==40, 'N3 requires full 1800+40 seconds')
    protected=sum(max(0.,hours-snap['gpu_hours_by_bucket'][bucket])
                  for bucket,hours in {'validation':14.,'formal':10.}.items())
    r.require(budget['max_gpu_hours']<=48 and budget['max_episode_attempts']<=240
        and snap['gpu_hours_consumed']+(1800+40)/3600+protected<=budget['max_gpu_hours'],
        'N3 cannot consume protected 24 GPU-hour allocation')
    protected_attempts=sum(max(0,cap-snap['by_bucket'][bucket]) for bucket,cap in {'validation':60,'formal':40}.items())
    r.require(snap['dispatched']+1+protected_attempts<=budget['max_episode_attempts'],
              'N3 cannot consume protected 100 episode allocations')


def admission(plan, runtime, row, events, resources, root, runner):
    r=api(runner); contract=plan['n3_cohort']; expected_binding=binding(plan,runtime)
    check_retry(events,row,r)
    groups=r.event_groups(events)
    cohort=[g for g in groups.values() if str(g[0]['identity']['iteration'])==COHORT]
    dispatched=[g for g in cohort if any(e['event']=='dispatched' for e in g)]
    r.require(all(g[0].get('n3_cohort_id')==COHORT and g[0].get('n3_frozen_identity')==expected_binding
                  for g in dispatched),'N3 prior dispatch frozen identity differs')
    r.require(all(g[-1]['event'] in r.TERMINAL for g in cohort),'N3 unfinished attempt')
    same=[g for g in dispatched if g[0]['identity']==r.episode_identity(row)]
    r.require(len(dispatched)<34 and len(same)<2,'N3 episode/cell dispatch allowance exhausted')
    recoveries=sum(bool(g[0].get('retry_of')) for g in dispatched)
    if row.get('retry_of'):
        r.require(len(same)==1 and recoveries<4 and same[0][0].get('retry_of') is None
            and row['retry_of']==same[0][0]['attempt_id'] and row.get('n3_recovery_contract')==expected_binding,
            'N3 recovery allowance/identity differs')
    else:
        r.require(not same,'N3 original cell already dispatched')
    local_seconds=sum(g[-1]['gpu_process_wall_seconds'] for g in dispatched)
    r.require(all(e['resource_id'] in {x['resource_id'] for x in contract['health_resources']}
        for e in resources if e.get('n3_cohort_id')==COHORT), 'N3 health cost attribution missing')
    for reference in contract['health_resources']:
        matched=[e for e in resources if e['resource_id']==reference['resource_id']]
        r.require(matched and matched[-1]['event'] in {'completed','aborted'},'N3 declared health resource incomplete')
        if reference['scope']=='new_n3': local_seconds+=matched[-1]['gpu_process_wall_seconds']
    r.require(local_seconds+1800+r.TERMINATION_GRACE_SECONDS<=8*3600,'N3 8-hour allowance cannot cover complete episode/cleanup')
    review=read_attestation(contract.get('recorded_candidate_review'),plan,root,r,'qd-ed-n3-recorded-check-v1')
    r.require(review.get('passed') is True and review.get('historical_tracking_validity')=='Unknown'
        and review.get('scope')=='conditional_recorded_final_pool_only'
        and (review.get('changed_recorded_choice') is True or review.get('quality_dependent_ranking_witness') is True),
              'N3 fixed-candidate mechanism prerequisite not met')
    originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    cell_index=next(i for i,x in enumerate(originals) if r.episode_identity(x)==r.episode_identity(row))
    first_n3_alignment=None
    for earlier in originals[:cell_index]:
        completed=[g[-1] for g in dispatched if g[0]['identity']==r.episode_identity(earlier)
                   and g[-1]['event']=='valid' and g[-1].get('outcome_valid') is True]
        r.require(len(completed)==1,'N3 fixed cell order requires prior valid completion')
        audit_path=r.owned(Path(completed[0]['output_dir'])/'eds_eval/decision-evidence-audit.json',plan['artifact_root'])
        r.require(audit_path.is_file(),'N3 prior complete decision evidence audit missing')
        audit=r.read_json(audit_path)
        r.require(audit.get('accepted') is True and audit.get('evidence_complete') is True,
                  'N3 prior complete decision evidence audit rejected')
        if earlier['profile']=='N3':
            metrics=r.read_events(audit_path.with_name('eds_metrics.jsonl'))
            r.require(len(metrics)==completed[0].get('metric_chunks'),'N3 prior native audit metric count differs')
            alignment=native_audit_alignment(audit,metrics,require=r.require)
            if earlier['episode_key']==originals[2]['episode_key']: first_n3_alignment=alignment
    if cell_index>=3:
        r.require(first_n3_alignment and first_n3_alignment['active_decisions']>0,
                  'N3 checkpoint lacks actual native-audited active feedback')
        checkpoint=read_attestation(contract.get('checkpoint_release'),plan,root,r,'qd-ed-n3-checkpoint-v1')
        r.require(checkpoint.get('checks')=={key:True for key in CHECKS} and checkpoint.get('runtime_tracking_validity')=='known_valid','N3 first-three correctness/activation checkpoint not released')
        attempts=[g[-1]['attempt_id'] for first in originals[:3] for g in dispatched
                  if g[0]['identity']==r.episode_identity(first) and g[-1]['event']=='valid' and g[-1].get('outcome_valid') is True]
        r.require(checkpoint.get('attempt_ids')==attempts and len(attempts)==3,'N3 checkpoint attempt linkage differs')
    return {'n3_cohort_id':COHORT,'n3_frozen_identity':expected_binding}


_ACTIVE_SCOPE = None

@contextmanager
def supervised_dispatch(plan,keys,root,runner,queue,monitor,status_path):
    """An in-process capability, created only with the real lease and owned hooks.

    This is an accidental-entry guard, not a security boundary against arbitrary
    Python mutation. The frozen supervisor/source mapping supplies that trust.
    """
    global _ACTIVE_SCOPE
    r=api(runner);root=Path(root);saved=r.read_json(status_path)
    pid,tid=os.getpid(),threading.get_ident();lock=root/'data/qd-ed-runner.lock'
    r.require(_ACTIVE_SCOPE is None,'N3 supervisor scope already active')
    r.require(saved.get('status')=='shared_runner_acquired' and saved.get('pid')==pid
        and saved.get('owner_thread_id')==tid and saved.get('boot_id')==plan['boot_id']
        and Path(saved.get('runner_lock_path','')).resolve()==lock.resolve(),
        'N3 verified shared lease status missing')
    st=lock.stat()
    r.require((saved.get('runner_lock_device'),saved.get('runner_lock_inode'))==(st.st_dev,st.st_ino),
              'N3 shared lease inode differs')
    # A second open-file description must not acquire the real flock. The
    # reentrant path must then succeed in this exact owner process/thread.
    with lock.open('a+') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:pass
        else:
            fcntl.flock(stream,fcntl.LOCK_UN)
            raise r.GateError('N3 real shared lease not held')
    with r.locked(lock,nonblocking=True):pass
    r.require(monitor.parent_pid==pid and monitor.root==root and monitor.episode_keys==frozenset(keys),
              'N3 owned monitor scope differs')
    for function in (r.gpu_admission,r.wait_exclusively,queue.pending_gate):
        r.require(any(c.cell_contents is monitor for c in (function.__closure__ or ())),
                  'N3 owned monitor hooks missing')
    r.require(Path(queue.bind_plan.__code__.co_filename).name=='qd_ed_n3_supervise.py' and queue.bind_plan.__name__=='bind',
              'N3 frozen hardware hook missing')
    monitor.require_boot()
    scope={'pid':pid,'thread':tid,'root':root,'binding':{'source_commit':plan['source_commit'],'code_files_sha256':source_identity(plan),'cohort':plan['n3_cohort']},'keys':frozenset(keys),
           'monitor':monitor,'queue':queue,'runner':r,
           'hooks':(r.locked,r.gpu_admission,r.wait_exclusively,r.run_plan,queue.pending_gate,queue.bind_plan)}
    _ACTIVE_SCOPE=scope
    try:yield
    finally:_ACTIVE_SCOPE=None


def require_scope(plan,root,r,row=None):
    r=api(r)
    scope=_ACTIVE_SCOPE
    r.require(scope is not None and scope['pid']==os.getpid() and scope['thread']==threading.get_ident()
        and scope['root']==Path(root) and scope['binding']=={'source_commit':plan['source_commit'],'code_files_sha256':source_identity(plan),'cohort':plan['n3_cohort']},
        'protected N3 requires dedicated owned supervisor scope')
    q=scope['queue']
    r.require(scope['hooks']==(r.locked,r.gpu_admission,r.wait_exclusively,r.run_plan,q.pending_gate,q.bind_plan),
              'N3 supervisor hooks changed')
    r.require(row is None or row['episode_key'] in scope['keys'],'episode outside N3 supervisor scope')
    scope['monitor'].require_boot()
    with r.locked(Path(root)/'data/qd-ed-runner.lock',nonblocking=True):pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-plan',type=Path,required=True);parser.add_argument('--runtime-manifest',type=Path,required=True)
    parser.add_argument('--source-head',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--recorded-candidate-review',type=Path)
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('n3_builder_runner',ROOT/'scripts/qd_ed_final_runner.py')
    r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    r.require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==args.source_head,'HEAD differs')
    base=r.read_json(args.base_plan); plan=copy.deepcopy(base); seeds=r.read_json(base['seed_plan_path'])
    runtime=r.read_json(args.runtime_manifest)
    r.require(Path(runtime['worktree']).resolve()==ROOT and r.runtime_gpu(runtime)==3,'integrate/runtime-bind GPU3 before preparation')
    for key in ('seed_plan','runtime_inventory'):
        r.require(r.digest(base[key+'_path'])==base[key+'_sha256'],'frozen input identity differs: '+key)
    for key in ('n2_cohort','n3_cohort','candidate_profiles','native_probe_contract','diagnostic_only','diagnostic_scope','queue_contract',
                'hardware_selection','frozen_at','preflight_index','preflight_index_sha256',
                'analysis_contract','observed_pair_prerequisites','engineering_prerequisite',
                'scheduling_only_revision','resource_amendment'):
        plan.pop(key,None)
    plan.update(frozen=False,worktree=str(ROOT),source_commit=args.source_head,boot_id=BOOT,episodes=rows_from_dev(seeds),
        profiles_path=str(ROOT/OBSERVED),profiles_sha256=r.digest(ROOT/OBSERVED),
        runtime_manifest_path=str(args.runtime_manifest.resolve()),runtime_manifest_sha256=r.digest(args.runtime_manifest),
        phase_authorization={'dev':True,'validation':False,'formal':False},
        observational_overrides={'main.decision_evidence.enabled':True},
        decision_evidence_gate='stop_remaining_on_incomplete_preserve_task_outcome',resource_amendment=PROTOCOL,
        candidate_profiles={'N3':{'path':str(ROOT/PROFILE),'sha256':r.digest(ROOT/PROFILE)}})
    scientific={*base['scientific_config_files'],PROFILE,OBSERVED,PROTOCOL,CLARIFICATION,ALLOCATION}
    paths={x['path'] for x in base['code_files']} | r.REQUIRED_CODE | REQUIRED | scientific
    for path in paths:
        actual=r.owned(ROOT/path,ROOT)
        r.require(actual.read_bytes()==subprocess.check_output(['git','show',args.source_head+':'+path],cwd=ROOT),
                  'source not committed: '+path)
    plan.update(code_files=[{'path':p,'sha256':r.digest(ROOT/p)} for p in sorted(paths)],scientific_config_files=sorted(scientific))
    reference=lambda p:{'path':str(p.resolve()),'sha256':r.digest(p)}
    prior=copy.deepcopy(base.get('observed_pair_prerequisites') or
        base.get('n2_cohort',{}).get('runtime_prerequisites',{}).get('references') or
        base.get('n3_cohort',{}).get('runtime_prerequisites',{}).get('references'))
    r.require(set(prior)==PREREQUISITES,'base current-boot prerequisites differ')
    health=r.read_json(prior['health_result']['path'])
    plan['n3_cohort']={'schema':'qd-ed-n3-cohort-v1','cohort_id':COHORT,'limits':LIMITS,
        'protocol':{'path':PROTOCOL,'sha256':r.digest(ROOT/PROTOCOL)},
        'accounting_clarification':{'path':CLARIFICATION,'sha256':r.digest(ROOT/CLARIFICATION)},
        'budget_allocation':copy.deepcopy(BUDGET_ALLOCATION),
        'budget_allocation_amendment':{'path':ALLOCATION,'sha256':r.digest(ROOT/ALLOCATION)},
        'health_resources':[{'resource_id':identifier,'scope':'reused_prior'} for identifier in
            dict.fromkeys([runtime['cuda_egl_probe']['resource_id'],health['resource_id']])],
        'runtime_prerequisites':{'boot_id':BOOT,'references':prior,
            'reuse_scope':'prior_engineering_only_not_N3_algorithm_validation',
            'native_dependencies':{'path':DEPENDENCIES,'sha256':r.digest(ROOT/DEPENDENCIES)}},
        'recorded_candidate_review':reference(args.recorded_candidate_review) if args.recorded_candidate_review else None,
        'checkpoint_release':None}
    plan['preparation_provenance']={'base_plan':reference(args.base_plan),'builder_sha256':r.digest(__file__)}
    destination=r.owned(args.output,Path(plan['artifact_root'])/'continuation_20260923')
    r.require(not destination.exists(),'refusing to overwrite plan')
    manifest=r.read_json(plan['profiles_path']);candidate=r.read_json(ROOT/PROFILE)
    manifest['profiles']['N3']=r.expand_candidate('N3',candidate,manifest['profiles']['Q0'])
    validate_contract(plan,manifest,runtime,seeds,ROOT,r)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x') as stream: json.dump(plan,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps({'status':'unfrozen_prepared','episodes':30,'output':str(destination),
                      'first_checkpoint_keys':[x['episode_key'] for x in plan['episodes'][:3]]}))


if __name__=='__main__': main()
