#!/usr/bin/env python3
"""N4's closed Dev contract and CPU-only unfrozen plan preparation.

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
COHORT = 'N4_E1_TRANSPORT180_DEV_20260924'
TASKS = (0, 3, 6, 9)
ORIGINAL_PROTOCOL = 'experiments/iteration_004_terminal_population/protocol.md'
PROTOCOL = 'experiments/iteration_004_terminal_population/transport180-engineering-protocol-v1.md'
# Original study-wide interpretation: healthchecks count hours, not episode attempts.
CLARIFICATION = 'experiments/iteration_002_executed_quality/accounting-clarification.md'
ALLOCATION = PROTOCOL
PREREQUISITE = 'experiments/iteration_004_terminal_population/q0-transfer-check-protocol.md'
ORIGINAL_CAPS = {'baseline':20, 'development':100, 'validation':60, 'formal':40, 'recovery':20}
BUDGET_ALLOCATION = {'baseline_cells':[[t,'C0'] for t in TASKS],
    'development_cells':[[t,p] for t in TASKS for p in ('Q0','N4')],
    'retry_bucket':'recovery','bucket_caps':ORIGINAL_CAPS}
FROZEN_DOCS = {ORIGINAL_PROTOCOL:'b8562e3f9fffc77efc803c6b056441f7b426333a97eb176b52fdb0fe42088db2',
    PREREQUISITE:'3ff18d22eb934a24f790bef5b411089f9a4c9116b098cfb7baa2b36cbbc277ca',
    PROTOCOL:'a960f4075cca5962e3e9cd35956f96b49f7433f797529134896803f7b5473e2d'}
CONDITION_ID = 'N4_E1_t180'
STAGE_CONDITION = 'codex_login_astra_low_n4e1_t180_v1'
ISOLATION_SHA = '4026c141ff9bd06f31734c0a43122327b359c35bd847670f641961df9ce81f47'
SOURCE_DELTA = {'scripts/qd_ed_final_runner.py','scripts/qd_ed_available_gpu_queue.py',
    'scripts/qd_ed_n4e1_plan.py','scripts/qd_ed_n4e1_supervise.py','scripts/qd_ed_n4e1_report.py',
    PROTOCOL,'core/codex_stage.py','core/codex_stage_lifecycle.py'}
PREREQUISITE_REVIEW_SHA256 = '711cef1fdcec7b3c28d3c202fefb1294e02ec2672dfe53e4043fcdecbca1a0db'
PROFILE = 'configs/qd_ed_final/candidate_n4.json'
OBSERVED = 'configs/qd_ed_final/n4_observed_baseline_profiles.json'
MODULE = 'scripts/qd_ed_n4e1_plan.py'
SUPERVISOR = 'scripts/qd_ed_n4e1_supervise.py'
REPORT = 'scripts/qd_ed_n4e1_report.py'
SUPPORT = 'docs/03_evidence/qd_ed_final/continuation_20260923/observed-pairs-draft/supervisor-support.py'
DEPENDENCIES = 'docs/03_evidence/qd_ed_final/continuation_20260923/freshboot-model-first/native-dependency-freeze.json'
BOOT = '2a1fa95f-ab0d-488c-a298-fc488ddd2af7'
PREREQUISITES = {'health_result','health_contract','common_result','common_process','common_kernel'}
LIMITS = {'episode_dispatches': 16, 'unique_cells': 12, 'recoveries': 4,
          'dispatches_per_cell': 2, 'new_gpu_hours': 8.5, 'timeout_seconds': 1800,
          'cleanup_seconds': 40, 'physical_gpu': 3}
FIELDS = ('env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256')
TRANSPORT_GATE = 'Codex Stage call failure invalidates the frozen transport condition'
CHECKS = ('finite_action','source_compute','raw_stage_separation','substantive_qd_archive_parent_use',
          'native_terminal_population_first_argmin','native_selected_decode_dispatch_alignment',
          'preserved_archive_stage_scale')
NATIVE_AUDIT_SCHEMA = 'n4-native-terminal-population-audit-v1'
REQUIRED = {'core/codex_stage_lifecycle.py',ORIGINAL_PROTOCOL,'scripts/qd_ed_n4_plan.py','core/codex_stage.py','core/codex_stage_policy.py',MODULE, SUPERVISOR, REPORT, SUPPORT, DEPENDENCIES, PROFILE, OBSERVED, PROTOCOL, CLARIFICATION, ALLOCATION, PREREQUISITE, 'core/qd_executed_quality.py','core/qd_executed_feedback.py','core/qd_terminal_population.py',
            'main.py','core/keypoint_tracker.py','core/env_adapters/libero_adapter.py',
            'core/rdt_libero_action_converter.py','core/qd_ed.py','core/rdt_policy_steer.py','core/eds_eval_metrics.py','configs/config.yaml',
            'scripts/qd_ed_available_gpu_queue.py','scripts/qd_ed_gpu_probe.py','scripts/qd_ed_runtime_setup.py',
            'scripts/audit_decision_evidence.py'}


def api(value): return SimpleNamespace(**value) if isinstance(value, dict) else value


_native_spec=importlib.util.spec_from_file_location('n4e1_unchanged_native_contract',Path(__file__).with_name('qd_ed_n4_plan.py'))
_native=importlib.util.module_from_spec(_native_spec);_native_spec.loader.exec_module(_native)
native_audit_alignment=_native.native_audit_alignment


def original_bucket(task, profile):
    cell=[task,profile]
    if cell in BUDGET_ALLOCATION['baseline_cells']: return 'baseline'
    if cell in BUDGET_ALLOCATION['development_cells']: return 'development'
    raise ValueError('unplanned N4 cell')


def rows_from_dev(seeds):
    rows=[]
    for task in TASKS:
        matches=[x for x in seeds['blocks']['dev'] if x['task_id']==task]
        if len(matches)!=1: raise ValueError('frozen Dev task missing/ambiguous')
        for profile in ('C0','Q0','N4'):
            rows.append({**{key:matches[0][key] for key in FIELDS},'task_id':task,'profile':profile,
                'episode_key':f'n4e1_dev_t{task:02d}_{profile.lower()}_20260924','iteration':COHORT,
                'split':'dev','seed_block':'dev','budget_bucket':original_bucket(task,profile),'timeout_seconds':1800})
    return rows


def observed_profiles(baseline, baseline_sha):
    result=copy.deepcopy(baseline)
    result['observation_condition']={'name':'n4_common_decision_observed_v1',
        'baseline_path':'configs/qd_ed_final/baseline_profiles.json','baseline_sha256':baseline_sha}
    for profile in result['profiles'].values():
        profile['static_override_values']['main.decision_evidence.enabled']=True
        profile['static_override_values']['main.eds_config.qd_final_selection_mode']='archive_global_best'
        profile['resolved_eds_config']['qd_final_selection_mode']='archive_global_best'
        profile['hydra_overrides'] += ['main.decision_evidence.enabled=true','main.eds_config.qd_final_selection_mode=archive_global_best']
        profile['historical_label']+='__n4_common_decision_observed_v1'
    return result


def source_identity(plan):
    return hashlib.sha256(json.dumps(plan['code_files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()


def binding(plan, runtime):
    contract=plan['n4e1_cohort']
    return {'cohort_id':COHORT,'protocol_sha256':contract['protocol']['sha256'],
        'accounting_clarification_sha256':contract['accounting_clarification']['sha256'],
        **{k:plan[k] for k in ('source_commit','profiles_sha256','runtime_manifest_sha256',
                             'runtime_inventory_sha256','seed_plan_sha256')},
        'candidate_sha256':plan['candidate_profiles']['N4']['sha256'],
        'stage_public_config_sha256':runtime['frozen_stage_provider']['public_config_sha256'],
        'source_files_sha256':source_identity(plan),
        'resource_contract_sha256':hashlib.sha256(json.dumps({key:contract[key] for key in
            ('limits','health_resources','runtime_prerequisites','budget_allocation','budget_allocation_amendment','prerequisite_protocol','prerequisite_review','resource_authority','engineering_condition','source_mapping')},sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def validate_contract(plan, manifest, runtime, seeds, root, runner, *, metadata_only=False):
    r=api(runner); root=Path(root); contract=plan.get('n4e1_cohort',{})
    r.require(not any(k in plan for k in ('n2_cohort','n3_cohort','n4_cohort','n2_evaluation','n4_evaluation','native_probe_contract','diagnostic_only')),
              'N4 cannot reuse another cohort or diagnostic authorization')
    r.require(contract.get('schema')=='qd-ed-n4e1-cohort-v1' and contract.get('cohort_id')==COHORT,
              'N4 requires its explicit prospective cohort contract')
    r.require(contract.get('limits')==LIMITS, 'N4 local resource limits differ')
    r.require(contract.get('budget_allocation')==BUDGET_ALLOCATION,'N4 original-arm budget allocation differs')
    r.require(plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}, 'N4 Dev-only phase gate differs')
    paths={x['path']:x['sha256'] for x in plan['code_files']}
    r.require(REQUIRED<=set(paths), 'N4 runtime source fingerprints missing')
    r.require(len(paths)==len(plan['code_files']), 'N4 duplicate source fingerprints')
    for key,relative in [('protocol',PROTOCOL),('accounting_clarification',CLARIFICATION),('budget_allocation_amendment',ALLOCATION),('prerequisite_protocol',PREREQUISITE)]:
        r.require(contract.get(key)=={'path':relative,'sha256':paths[relative]} and
                  r.digest(root/relative)==paths[relative], 'N4 protocol/clarification differs')
    r.require(all(paths.get(p)==expected for p,expected in FROZEN_DOCS.items()), 'N4 approved document SHA differs')
    prerequisite_review(contract.get('prerequisite_review'),plan,r)
    resource_authority(plan,runtime,root,r,check_state=not metadata_only)
    r.require(set(plan['candidate_profiles'])=={'N4'}, 'N4 matrix cannot include another candidate')
    r.require(r.runtime_gpu(runtime)==3 and runtime['frozen_stage_provider'].get('backend')=='codex_cli',
              'N4-E1 requires GPU3 and frozen Codex transport')
    validate_engineering_mapping(plan,runtime,root,r)
    baseline_path=root/'configs/qd_ed_final/baseline_profiles.json'
    candidate=r.read_json(root/PROFILE)
    r.require(candidate.get('baseline_provenance')=={'path':'configs/qd_ed_final/baseline_profiles.json',
        'profile':'Q0.restored_profile','sha256':r.digest(baseline_path)} and candidate.get('action_chunk_horizon')==8,
        'N4 baseline provenance/horizon differs')
    expected=observed_profiles(r.read_json(baseline_path),r.digest(baseline_path))
    r.require(Path(plan['profiles_path']).resolve()==(root/OBSERVED).resolve() and
              r.read_json(plan['profiles_path'])==expected,'N4 common observed baseline drift')
    r.require(all(manifest['profiles'][p]['static_override_values']['main.decision_evidence.enabled'] is True
                  for p in ('C0','Q0','N4')),'N4 common observer is required')
    expected_rows=rows_from_dev(seeds); originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    r.require(originals==expected_rows,'N4 original 12 cells/order/seeds differ')
    recoveries=[x for x in plan['episodes'] if x.get('retry_of')]
    r.require(len(recoveries)<=4,'N4 recovery plan exceeds four')
    identities={json.dumps(r.episode_identity(x),sort_keys=True):x for x in expected_rows}
    used=set()
    for row in recoveries:
        identity=json.dumps(r.episode_identity(row),sort_keys=True)
        r.require(identity in identities and identity not in used,'N4 recovery scientific cell missing/repeated')
        used.add(identity); original=identities[identity]
        actual={k:v for k,v in row.items() if k not in {'episode_key','retry_of','n4e1_recovery_contract','budget_bucket'}}
        reference={k:v for k,v in original.items() if k not in {'episode_key','budget_bucket'}}
        r.require(actual==reference and row['budget_bucket']=='recovery' and row['episode_key']!=original['episode_key']
            and row.get('n4e1_recovery_contract')==binding(plan,runtime),'N4 recovery frozen identity differs')
    resources=contract.get('health_resources',[])
    r.require(isinstance(resources,list) and len({x['resource_id'] for x in resources})==len(resources)
        and all(set(x)=={'resource_id','scope'} and x['scope'] in {'reused_prior','new_n4e1'} for x in resources),
        'N4 health resource attribution differs')
    proof=runtime.get('cuda_egl_probe',{}).get('resource_id')
    r.require(proof and proof in {x['resource_id'] for x in resources},'N4 runtime proof must be explicitly attributed')
    prerequisites=contract.get('runtime_prerequisites',{})
    r.require(plan.get('boot_id')==BOOT and prerequisites.get('boot_id')==BOOT and
        prerequisites.get('reuse_scope')=='prior_engineering_only_not_N4E1_algorithm_validation' and
        set(prerequisites.get('references',{}))==PREREQUISITES and
        prerequisites.get('native_dependencies')=={'path':DEPENDENCIES,'sha256':paths[DEPENDENCIES]},
        'N4 current-boot engineering prerequisites missing/different')


def prerequisite_review(reference,plan,r):
    r=api(r)
    r.require(isinstance(reference,dict) and set(reference)=={'path','sha256'}
        and reference['sha256']==PREREQUISITE_REVIEW_SHA256, 'N4 exact prerequisite review missing/different')
    path=r.owned(reference['path'],plan['artifact_root'])
    r.require(r.digest(path)==reference['sha256'], 'N4 prerequisite review bytes differ')
    review=r.read_json(path)
    r.require(review.get('schema')=='n4-q0-transfer-complete-root-review-v1'
        and review.get('decision')=='PASS_FIXED_Q0_ACTIVITY_PREREQUISITE'
        and review.get('counts',{}).get('cells')==10 and review['counts'].get('guided')==155
        and review['counts'].get('Unknown')==0 and review['counts'].get('conjunction',0)>0,
        'N4 prerequisite not complete/passed')
    for key in ('index','provenance','status','launch_result'):
        item=review[key]; actual=r.owned(item['path'],plan['artifact_root'])
        r.require(r.digest(actual)==item['sha256'],'N4 prerequisite reference changed: '+key)
    return review


def resource_authority(plan,runtime,root,runner,*,check_state=True,admission=False):
    """Read only this study's private authority; never inspect/mutate a peer."""
    r=api(runner);root=Path(root);refs=plan['n4e1_cohort'].get('resource_authority',{})
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
        and study.get('bucket_caps')==ORIGINAL_CAPS
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
        r.require(state['budget']['reserved']==ORIGINAL_CAPS and state['budget']['max_episode_attempts']==240
            and state['budget']['max_gpu_hours']==48 and r.authorized_gpu(state)==3,'private resource caps/GPU differ')
        for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl',
                     'qd-ed-runner.lock','qd-ed-state.lock'):
            path=root/'data'/name
            r.require(path.is_file() and not path.is_symlink() and path.stat().st_nlink==1,
                'private resource must be an owned local regular file: '+name)
    return refs


def read_attestation(reference, plan, root, r, schema):
    r.require(isinstance(reference,dict) and set(reference)=={'path','sha256'},'N4 attestation not released')
    path=r.owned(reference['path'],plan['artifact_root'])
    r.require(r.digest(path)==reference['sha256'],'N4 attestation fingerprint differs')
    value=r.read_json(path)
    r.require(value.get('schema')==schema and value.get('cohort_id')==COHORT and
        value.get('source_commit')==plan['source_commit'] and
        value.get('source_files_sha256')==source_identity(plan) and
        value.get('protocol_sha256')==plan['n4e1_cohort']['protocol']['sha256'], 'N4 attestation identity differs')
    evidence=value.get('evidence')
    r.require(isinstance(evidence,list) and evidence,'N4 attestation evidence missing')
    for item in evidence:
        path=r.owned(item['path'],plan['artifact_root'])
        r.require(r.digest(path)==item['sha256'],'N4 attestation evidence changed')
    return value


def transport_recovery_eligibility(exc, outcome, plan, row, runtime, runner):
    """Separate prospective eligibility; never rewrite the original outcome."""
    r=api(runner)
    if not plan.get('n4e1_cohort') or not isinstance(exc,r.GateError) or str(exc)!=TRANSPORT_GATE:
        return None
    if (outcome.get('outcome_valid') is not False or outcome.get('compute_outcome')!='completed'
            or outcome.get('required_cost_telemetry_complete') is not True
            or outcome.get('stage_backend')!='codex_cli'
            or outcome.get('provider_failed_calls',0)<=0
            or outcome.get('stage_failed_queries',0)<=0):
        return None
    return {'schema':'qd-ed-n4e1-recovery-eligibility-v1','reason':'exact_codex_stage_transport_failure',
            'gate':TRANSPORT_GATE,'frozen_identity':binding(plan,runtime)}


def recoverable(final, expected):
    """Exact prospective causes only; raw legacy infrastructure labels are insufficient."""
    if final.get('outcome_valid') is not False or final.get('n4e1_frozen_identity') != expected:
        return False
    if final.get('event') == 'aborted' and final.get('retryable_infrastructure') is True:
        if final.get('reason') == 'external GPU3 process appeared during owned attempt':
            return True
        return (final.get('reason') == 'GPU3 nvidia-smi monitor query timed out after 15 seconds'
            and final.get('failure_detail') == 'gpu_monitor_timeout'
            and final.get('gpu_monitor_timeout') == {'physical_gpu':3,'timeout_seconds':15})
    eligible=final.get('n4e1_recovery_eligibility',{})
    return (final.get('event')=='valid' and final.get('compute_outcome')=='completed'
        and final.get('required_cost_telemetry_complete') is True
        and final.get('stage_backend')=='codex_cli' and final.get('provider_failed_calls',0)>0
        and final.get('stage_failed_queries',0)>0 and final.get('reason')==TRANSPORT_GATE
        and eligible=={'schema':'qd-ed-n4e1-recovery-eligibility-v1','reason':'exact_codex_stage_transport_failure',
                       'gate':TRANSPORT_GATE,'frozen_identity':expected})


def check_retry(events, row, runner):
    r=api(runner); groups=r.event_groups(events)
    prior=[g for g in groups.values() if g[0]['identity']==r.episode_identity(row)
           and any(e['event']=='dispatched' for e in g)]
    if not prior:
        r.require(not row.get('retry_of'), 'N4 retry has no dispatched predecessor')
        return
    certificate=row.get('n4e1_recovery_contract',{})
    r.require(len(prior)==1 and certificate.get('cohort_id')==COHORT
        and str(row['iteration'])==COHORT and row.get('retry_of')==prior[0][0]['attempt_id']
        and prior[0][0].get('n4e1_frozen_identity')==certificate
        and prior[0][0].get('n4e1_cohort_id')==COHORT and not prior[0][0].get('retry_of')
        and recoverable(prior[0][-1],certificate), 'N4 prior outcome cannot be retried')
    r.require(not any(g[0].get('retry_of')==row['retry_of'] and any(e['event']=='dispatched' for e in g)
                      for g in groups.values()),'N4 retry already consumed')


def protected_budget(state, events, resources, row, timeout, runner, *, plan=None):
    r=api(runner); snap=r.budget_snapshot(events,resources); budget=state['budget']
    r.require(r.BUCKETS==ORIGINAL_CAPS and budget['reserved']==ORIGINAL_CAPS
        and budget.get('gpu_hour_reservations')=={'validation':14.,'formal':10.}, 'N4 current resource caps/reserves differ')
    r.require(timeout==1800 and r.TERMINATION_GRACE_SECONDS==40, 'N4 requires full 1800+40 seconds')
    protected=sum(max(0.,hours-snap['gpu_hours_by_bucket'][bucket])
                  for bucket,hours in {'validation':14.,'formal':10.}.items())
    r.require(budget['max_gpu_hours']<=48 and budget['max_episode_attempts']<=240
        and snap['gpu_hours_consumed']+(1800+40)/3600+protected<=budget['max_gpu_hours'],
        'N4 cannot consume protected 24 GPU-hour allocation')
    protected_attempts=sum(max(0,cap-snap['by_bucket'][bucket]) for bucket,cap in {'validation':60,'formal':40}.items())
    r.require(snap['dispatched']+1+protected_attempts<=budget['max_episode_attempts'],
              'N4 cannot consume protected 100 episode allocations')

    if plan is not None:
        cohort=[g for g in r.event_groups(events).values() if g[0].get('identity',{}).get('iteration')==COHORT
                and any(e['event']=='dispatched' for e in g)]
        pending=[o for o in plan['episodes'] if not o.get('retry_of') and not any(
            g[0]['identity']==r.episode_identity(o) for g in cohort)]
        remaining={k:sum(o['budget_bucket']==k for o in pending) for k in ORIGINAL_CAPS}
        remaining['recovery']=4-sum(bool(g[0].get('retry_of')) for g in cohort)
        r.require(remaining['recovery']>=0 and all(snap['by_bucket'][k]+remaining[k]<=ORIGINAL_CAPS[k]
            for k in ORIGINAL_CAPS),'N4 remaining whole-cohort bucket capacity unavailable')
        r.require(snap['dispatched']+sum(remaining.values())+protected_attempts<=budget['max_episode_attempts'],
                  'N4 remaining whole-cohort capacity would consume protected attempts')


def admission(plan, runtime, row, events, resources, root, runner):
    r=api(runner); contract=plan['n4e1_cohort']; expected_binding=binding(plan,runtime)
    check_retry(events,row,r)
    groups=r.event_groups(events)
    cohort=[g for g in groups.values() if str(g[0]['identity']['iteration'])==COHORT]
    dispatched=[g for g in cohort if any(e['event']=='dispatched' for e in g)]
    r.require(all(g[0].get('n4e1_cohort_id')==COHORT and g[0].get('n4e1_frozen_identity')==expected_binding
                  for g in dispatched),'N4 prior dispatch frozen identity differs')
    r.require(all(g[-1]['event'] in r.TERMINAL for g in cohort),'N4 unfinished attempt')
    same=[g for g in dispatched if g[0]['identity']==r.episode_identity(row)]
    r.require(len(dispatched)<16 and len(same)<2,'N4 episode/cell dispatch allowance exhausted')
    recoveries=sum(bool(g[0].get('retry_of')) for g in dispatched)
    if row.get('retry_of'):
        r.require(len(same)==1 and recoveries<4 and same[0][0].get('retry_of') is None
            and row['retry_of']==same[0][0]['attempt_id'] and row.get('n4e1_recovery_contract')==expected_binding,
            'N4 recovery allowance/identity differs')
    else:
        r.require(not same,'N4 original cell already dispatched')
    local_seconds=sum(g[-1]['gpu_process_wall_seconds'] for g in cohort)
    r.require(all(e['resource_id'] in {x['resource_id'] for x in contract['health_resources']}
        for e in resources if e.get('n4e1_cohort_id')==COHORT), 'N4 health cost attribution missing')
    for reference in contract['health_resources']:
        matched=[e for e in resources if e['resource_id']==reference['resource_id']]
        r.require(matched and matched[-1]['event'] in {'completed','aborted'},'N4 declared health resource incomplete')
        if reference['scope']=='new_n4e1': local_seconds+=matched[-1]['gpu_process_wall_seconds']
    r.require(local_seconds+1800+r.TERMINATION_GRACE_SECONDS<=8.5*3600,'N4 8.5-hour allowance cannot cover complete episode/cleanup')
    prerequisite_review(contract.get('prerequisite_review'),plan,r)
    resource_authority(plan,runtime,root,r,admission=True)
    originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    cell_index=next(i for i,x in enumerate(originals) if r.episode_identity(x)==r.episode_identity(row))
    first_n4_alignment=None
    for earlier in originals[:cell_index]:
        completed=[g[-1] for g in dispatched if g[0]['identity']==r.episode_identity(earlier)
                   and g[-1]['event']=='valid' and g[-1].get('outcome_valid') is True]
        r.require(len(completed)==1,'N4 fixed cell order requires prior valid completion')
        audit_path=r.owned(Path(completed[0]['output_dir'])/'eds_eval/decision-evidence-audit.json',plan['artifact_root'])
        r.require(audit_path.is_file(),'N4 prior complete decision evidence audit missing')
        audit=r.read_json(audit_path)
        r.require(audit.get('accepted') is True and audit.get('evidence_complete') is True,
                  'N4 prior complete decision evidence audit rejected')
        if earlier['profile']=='N4':
            metrics=r.read_events(audit_path.with_name('eds_metrics.jsonl'))
            r.require(len(metrics)==completed[0].get('metric_chunks')==completed[0].get('guided_chunks'),'N4 prior native audit metric count differs')
            alignment=native_audit_alignment(audit,metrics,require=r.require)
            if earlier['episode_key']==originals[2]['episode_key']: first_n4_alignment=alignment
    if cell_index>=3:
        r.require(first_n4_alignment and first_n4_alignment['checked_decisions']>0,
                  'N4 checkpoint lacks native-audited archive-parent/consumer execution')
        checkpoint=read_attestation(contract.get('checkpoint_release'),plan,root,r,'qd-ed-n4e1-checkpoint-v1')
        r.require(checkpoint.get('checks')=={key:True for key in CHECKS},'N4 first-three correctness checkpoint not released')
        attempts=[g[-1]['attempt_id'] for first in originals[:3] for g in dispatched
                  if g[0]['identity']==r.episode_identity(first) and g[-1]['event']=='valid' and g[-1].get('outcome_valid') is True]
        r.require(checkpoint.get('attempt_ids')==attempts and len(attempts)==3,'N4 checkpoint attempt linkage differs')
    return {'n4e1_cohort_id':COHORT,'n4e1_frozen_identity':expected_binding}


def execution_release(reference,plan_path,plan,runtime,keys,root,runner):
    """One root release for one immutable plan and explicit phase/key scope; no plan cycle."""
    r=api(runner)
    r.require(isinstance(reference,dict) and set(reference)=={'path','sha256'},'N4 execution release reference missing')
    path=r.owned(reference['path'],plan['artifact_root'])
    r.require(r.digest(path)==reference['sha256'],'N4 execution release bytes differ')
    release=r.read_json(path)
    r.require(release.get('schema')=='qd-ed-n4e1-execution-release-v1' and release.get('status')=='authorized'
        and release.get('cohort_id')==COHORT and release.get('plan')=={'path':str(Path(plan_path).resolve()),'sha256':r.digest(plan_path)}
        and release.get('frozen_identity')==binding(plan,runtime)
        and release.get('source_commit')==plan['source_commit']
        and release.get('source_files_sha256')==source_identity(plan)
        and release.get('candidate_profiles')==plan['candidate_profiles']
        and release.get('resource_authority')==plan['n4e1_cohort']['resource_authority']
        and release.get('limits')==LIMITS and release.get('budget_allocation')==BUDGET_ALLOCATION
        and release.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}
        and release.get('physical_gpu')==3 and release.get('max_owned_GPU_workers')==1
        and release.get('gpu_mapping')==runtime['gpu_mapping'], 'N4 execution release frozen identity differs')
    r.require(release.get('episode_keys')==list(keys) and keys and len(set(keys))==len(keys),
        'N4 execution release key scope differs')
    originals=[row for row in plan['episodes'] if not row.get('retry_of')]
    rows={row['episode_key']:row for row in plan['episodes']}
    r.require(set(keys)<=set(rows),'N4 release unplanned key')
    indices=[next(i for i,o in enumerate(originals) if r.episode_identity(o)==r.episode_identity(rows[k])) for k in keys]
    r.require(indices==sorted(indices) and len(set(indices))==len(indices),'N4 release cell order/duplication differs')
    stage=release.get('stage')
    r.require((stage=='first3' and all(i<3 for i in indices)) or
              (stage=='remaining9' and all(i>=3 for i in indices)), 'N4 release phase/key scope differs')
    expected=plan['n4e1_cohort'].get('checkpoint_release') if stage=='remaining9' else None
    r.require(release.get('checkpoint_release')==expected and (stage!='remaining9' or expected is not None),
        'N4 later release lacks bound correctness checkpoint')
    if expected:
        checkpoint=read_attestation(expected,plan,root,r,'qd-ed-n4e1-checkpoint-v1')
        r.require(checkpoint.get('checks')==dict.fromkeys(CHECKS,True),'N4 execution release checkpoint failed')
    return release


_ACTIVE_SCOPE = None

@contextmanager
def supervised_dispatch(plan,keys,root,runner,queue,monitor,status_path,*,release_reference,plan_path,runtime):
    """An in-process capability, created only with the real lease and owned hooks.

    This is an accidental-entry guard, not a security boundary against arbitrary
    Python mutation. The frozen supervisor/source mapping supplies that trust.
    """
    global _ACTIVE_SCOPE
    r=api(runner);root=Path(root);saved=r.read_json(status_path)
    release=execution_release(release_reference,plan_path,plan,runtime,keys,root,r)
    pid,tid=os.getpid(),threading.get_ident();lock=root/'data/qd-ed-runner.lock'
    r.require(_ACTIVE_SCOPE is None,'N4 supervisor scope already active')
    r.require(saved.get('status')=='shared_runner_acquired' and saved.get('pid')==pid
        and saved.get('owner_thread_id')==tid and saved.get('boot_id')==plan['boot_id']
        and Path(saved.get('runner_lock_path','')).resolve()==lock.resolve(),
        'N4 verified shared lease status missing')
    st=lock.stat()
    r.require((saved.get('runner_lock_device'),saved.get('runner_lock_inode'))==(st.st_dev,st.st_ino),
              'N4 shared lease inode differs')
    # A second open-file description must not acquire the real flock. The
    # reentrant path must then succeed in this exact owner process/thread.
    with lock.open('a+') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:pass
        else:
            fcntl.flock(stream,fcntl.LOCK_UN)
            raise r.GateError('N4 real shared lease not held')
    with r.locked(lock,nonblocking=True):pass
    r.require(monitor.parent_pid==pid and monitor.root==root and monitor.episode_keys==frozenset(keys),
              'N4 owned monitor scope differs')
    for function in (r.gpu_admission,r.wait_exclusively,queue.pending_gate):
        r.require(any(c.cell_contents is monitor for c in (function.__closure__ or ())),
                  'N4 owned monitor hooks missing')
    r.require(Path(queue.bind_plan.__code__.co_filename).name=='qd_ed_n4e1_supervise.py' and queue.bind_plan.__name__=='bind',
              'N4 frozen hardware hook missing')
    monitor.require_boot()
    scope={'pid':pid,'thread':tid,'root':root,'binding':{'source_commit':plan['source_commit'],'code_files_sha256':source_identity(plan),'cohort':plan['n4e1_cohort']},'keys':frozenset(keys),
           'monitor':monitor,'queue':queue,'runner':r,'release_reference':copy.deepcopy(release_reference),
           'plan_path':Path(plan_path),'runtime':runtime,'ordered_keys':list(keys),'release':release,
           'hooks':(r.locked,r.gpu_admission,r.wait_exclusively,r.run_plan,queue.pending_gate,queue.bind_plan)}
    _ACTIVE_SCOPE=scope
    try:yield
    finally:_ACTIVE_SCOPE=None


def require_scope(plan,root,r,row=None):
    r=api(r)
    scope=_ACTIVE_SCOPE
    r.require(scope is not None and scope['pid']==os.getpid() and scope['thread']==threading.get_ident()
        and scope['root']==Path(root) and scope['binding']=={'source_commit':plan['source_commit'],'code_files_sha256':source_identity(plan),'cohort':plan['n4e1_cohort']},
        'protected N4 requires dedicated owned supervisor scope')
    execution_release(scope['release_reference'],scope['plan_path'],plan,scope['runtime'],scope['ordered_keys'],root,r)
    q=scope['queue']
    r.require(scope['hooks']==(r.locked,r.gpu_admission,r.wait_exclusively,r.run_plan,q.pending_gate,q.bind_plan),
              'N4 supervisor hooks changed')
    r.require(row is None or row['episode_key'] in scope['keys'],'episode outside N4 supervisor scope')
    scope['monitor'].require_boot()
    with r.locked(Path(root)/'data/qd-ed-runner.lock',nonblocking=True):pass



def read_ref(reference,plan,runner):
    r=api(runner)
    r.require(isinstance(reference,dict) and set(reference)=={'path','sha256'},'E1 exact metadata reference missing')
    path=r.owned(reference['path'],plan['artifact_root'])
    r.require(r.digest(path)==reference['sha256'],'E1 metadata fingerprint differs')
    return r.read_json(path)


def engineering_condition():
    return {'schema':'qd-ed-n4e1-transport-condition-v1','condition_id':CONDITION_ID,
        'algorithm_family':'8.1/N4','protocol':{'path':PROTOCOL,'sha256':FROZEN_DOCS[PROTOCOL]},
        'stage_timeout_seconds':180,'application_max_attempts':1,
        'old_condition':'codex_login_astra_low_v1','old_cohort_not_recoverable':True}


def runtime_variant(parent,runner):
    r=api(runner)
    r.require('stage_engineering_condition' not in parent and parent['frozen_stage_provider']['timeout_seconds']==90,
        'E1 runtime must derive from original90 condition')
    r.stage_overrides(parent)
    value=copy.deepcopy(parent);value['stage_engineering_condition']=engineering_condition()
    value['frozen_stage_provider']['timeout_seconds']=180
    value['frozen_stage_provider']['public_config_sha256']=r.codex_public_config_sha256(value['frozen_stage_provider'])
    return value


def validate_engineering_mapping(plan,runtime,root,runner):
    r=api(runner);c=plan['n4e1_cohort'];mapping=c.get('source_mapping',{})
    r.require(c.get('engineering_condition')==runtime.get('stage_engineering_condition')==engineering_condition(),
        'E1 engineering condition differs')
    r.require(runtime['frozen_stage_provider']['timeout_seconds']==180,'E1 Stage timeout differs')
    base=read_ref(mapping.get('parent_plan'),plan,r)
    r.require(base.get('frozen') is True and base.get('n4_cohort',{}).get('cohort_id')=='N4_TERMINAL_POPULATION_DEV_20260924'
        and base['n4_cohort']['protocol']['sha256']==FROZEN_DOCS[ORIGINAL_PROTOCOL], 'E1 source must map frozen old N4')
    parent_ref={'path':base['runtime_manifest_path'],'sha256':base['runtime_manifest_sha256']}
    r.require(mapping.get('runtime_parent')==parent_ref,'E1 runtime provenance differs')
    parent=read_ref(parent_ref,plan,r)
    r.require(runtime==runtime_variant(parent,r),'E1 runtime changed beyond exact public transport condition')
    before={x['path']:x['sha256'] for x in base['code_files']};after={x['path']:x['sha256'] for x in plan['code_files']}
    r.require(len(before)==len(base['code_files']) and len(after)==len(plan['code_files']) and set(before)<=set(after)
        and set(after)-set(before)<=SOURCE_DELTA,'E1 source inventory missing/duplicate/unapproved addition')
    unchanged=[x for x in base['code_files'] if x['path'] not in SOURCE_DELTA]
    r.require(mapping.get('allowed_changed_paths')==sorted(SOURCE_DELTA) and mapping.get('unchanged_sources')==unchanged
        and mapping.get('parent_source_commit')==base['source_commit']
        and all(after.get(x['path'])==x['sha256'] for x in unchanged),'E1 changed algorithm/provider/prompt/environment source')
    r.require(all(plan[k]==base[k] for k in ('runtime_inventory_sha256','seed_plan_sha256','profiles_sha256','candidate_profiles')),
        'E1 frozen algorithm/profile/model/seed identity differs')
    return base


def build_plan(base,base_reference,runtime,runtime_reference,head,root,resource_refs,runner):
    r=api(runner);root=Path(root);plan=copy.deepcopy(base)
    r.require(set(base.get('candidate_profiles',{}))=={'N4'},'E1 requires original N4 candidate only')
    for key in ('n4_cohort','preflight_index','preflight_index_sha256','frozen_at','resource_amendment','preparation_provenance'):
        plan.pop(key,None)
    seeds=r.read_json(base['seed_plan_path'])
    for key in ('seed_plan','runtime_inventory'):
        r.require(r.digest(base[key+'_path'])==base[key+'_sha256'],'E1 frozen input fingerprint differs')
    paths={x['path'] for x in base['code_files']}|REQUIRED|SOURCE_DELTA|r.REQUIRED_CODE
    for path in paths:
        r.require((root/path).read_bytes()==subprocess.check_output(['git','show',head+':'+path],cwd=root),
            'E1 uncommitted source: '+path)
    plan.update(frozen=False,worktree=str(root),source_commit=head,episodes=rows_from_dev(seeds),
        profiles_path=str(root/OBSERVED),profiles_sha256=r.digest(root/OBSERVED),
        runtime_manifest_path=runtime_reference['path'],runtime_manifest_sha256=runtime_reference['sha256'],
        phase_authorization={'dev':True,'validation':False,'formal':False},
        code_files=[{'path':p,'sha256':r.digest(root/p)} for p in sorted(paths)],
        scientific_config_files=sorted(set(base['scientific_config_files'])|{PROTOCOL}),
        candidate_profiles={'N4':{'path':str(root/PROFILE),'sha256':r.digest(root/PROFILE)}})
    original=base['n4_cohort']
    plan['n4e1_cohort']={
        'schema':'qd-ed-n4e1-cohort-v1','cohort_id':COHORT,'limits':LIMITS,
        'protocol':{'path':PROTOCOL,'sha256':FROZEN_DOCS[PROTOCOL]},
        'accounting_clarification':copy.deepcopy(original['accounting_clarification']),
        'budget_allocation':copy.deepcopy(BUDGET_ALLOCATION),
        'budget_allocation_amendment':{'path':PROTOCOL,'sha256':FROZEN_DOCS[PROTOCOL]},
        'health_resources':copy.deepcopy(original['health_resources']),
        'runtime_prerequisites':{**copy.deepcopy(original['runtime_prerequisites']),
            'reuse_scope':'prior_engineering_only_not_N4E1_algorithm_validation'},
        'prerequisite_protocol':copy.deepcopy(original['prerequisite_protocol']),
        'prerequisite_review':copy.deepcopy(original['prerequisite_review']),
        'resource_authority':copy.deepcopy(resource_refs),'engineering_condition':engineering_condition(),
        'source_mapping':{'parent_plan':base_reference,'parent_source_commit':base['source_commit'],
            'runtime_parent':{'path':base['runtime_manifest_path'],'sha256':base['runtime_manifest_sha256']},
            'allowed_changed_paths':sorted(SOURCE_DELTA),
            'unchanged_sources':[x for x in base['code_files'] if x['path'] not in SOURCE_DELTA]},
        'checkpoint_release':None}
    manifest=r.read_json(plan['profiles_path']);manifest['profiles']['N4']=r.expand_candidate('N4',r.read_json(root/PROFILE),manifest['profiles']['Q0'])
    validate_contract(plan,manifest,runtime,seeds,root,r)
    return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    cmd=sub.add_parser('runtime-draft');cmd.add_argument('--parent-runtime',type=Path,required=True);cmd.add_argument('--output',type=Path,required=True)
    cmd=sub.add_parser('prepare')
    for name in ('base-plan','runtime-manifest','resource-authority','output'):cmd.add_argument('--'+name,type=Path,required=True)
    cmd.add_argument('--source-head',required=True)
    args=parser.parse_args();import qd_ed_final_runner as r
    r.require(not args.output.exists(),'E1 output exists; preserve prior evidence')
    if args.command=='runtime-draft':
        parent=r.read_json(args.parent_runtime);result=runtime_variant(parent,r)
        destination=r.owned(args.output,parent['artifact_root'])
    else:
        r.require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==args.source_head,'E1 HEAD differs')
        base=r.read_json(args.base_plan);runtime=r.read_json(args.runtime_manifest)
        reference=lambda p:{'path':str(p.resolve()),'sha256':r.digest(p)}
        with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
            result=build_plan(base,reference(args.base_plan),runtime,reference(args.runtime_manifest),args.source_head,ROOT,
                r.read_json(args.resource_authority),r)
            import qd_ed_available_gpu_queue as q
            events,resources=q.no_unfinished(ROOT)
            state=r.read_state(ROOT/'research-state.yaml')
            protected_budget(state,events,resources,result['episodes'][0],1800,r,plan=result)
        destination=r.owned(args.output,base['artifact_root'])
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
    print(json.dumps({'status':'unfrozen_only','kind':args.command,'output':str(destination)}))


if __name__=='__main__':main()
