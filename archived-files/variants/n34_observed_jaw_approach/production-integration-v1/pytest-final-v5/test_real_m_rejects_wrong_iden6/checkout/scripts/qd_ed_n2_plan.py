#!/usr/bin/env python3
"""N2's closed Dev contract and CPU-only unfrozen plan preparation.

No GPU/provider/model call, freeze, dispatch, state or ledger write is provided.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
COHORT = 'N2_EXECUTED_QUALITY_DEV_20260923'
PROTOCOL = 'experiments/iteration_002_executed_quality/protocol.md'
CLARIFICATION = 'experiments/iteration_002_executed_quality/accounting-clarification.md'
PROFILE = 'configs/qd_ed_final/candidate_n2.json'
OBSERVED = 'configs/qd_ed_final/n2_observed_baseline_profiles.json'
MODULE = 'scripts/qd_ed_n2_plan.py'
SUPERVISOR = 'scripts/qd_ed_n2_supervise.py'
SUPPORT = 'docs/03_evidence/qd_ed_final/continuation_20260923/observed-pairs-draft/supervisor-support.py'
DEPENDENCIES = 'docs/03_evidence/qd_ed_final/continuation_20260923/freshboot-model-first/native-dependency-freeze.json'
BOOT = '2a1fa95f-ab0d-488c-a298-fc488ddd2af7'
PREREQUISITES = {'health_result','health_contract','common_result','common_process','common_kernel'}
LIMITS = {'episode_dispatches': 34, 'unique_cells': 30, 'recoveries': 4,
          'dispatches_per_cell': 2, 'new_gpu_hours': 18., 'timeout_seconds': 1800,
          'cleanup_seconds': 40, 'physical_gpu': 3}
FIELDS = ('env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256')
TRANSPORT_GATE = 'Codex Stage call failure invalidates the frozen transport condition'
CHECKS = ('finite_action','source_compute','raw_stage_separation','substantive_qd_activation')
REQUIRED = {MODULE, SUPERVISOR, SUPPORT, DEPENDENCIES, PROFILE, OBSERVED, PROTOCOL, CLARIFICATION, 'core/qd_executed_quality.py',
            'core/qd_ed.py','core/rdt_policy_steer.py','core/eds_eval_metrics.py','configs/config.yaml',
            'scripts/qd_ed_available_gpu_queue.py','scripts/qd_ed_gpu_probe.py','scripts/qd_ed_runtime_setup.py',
            'scripts/audit_decision_evidence.py'}


def api(value): return SimpleNamespace(**value) if isinstance(value, dict) else value


def rows_from_dev(seeds):
    rows=[]
    for task in range(10):
        matches=[x for x in seeds['blocks']['dev'] if x['task_id']==task]
        if len(matches)!=1: raise ValueError('frozen Dev task missing/ambiguous')
        for profile in ('C0','Q0','N2'):
            rows.append({**{key:matches[0][key] for key in FIELDS},'task_id':task,'profile':profile,
                'episode_key':f'n2_dev_t{task:02d}_{profile.lower()}_20260923','iteration':COHORT,
                'split':'dev','seed_block':'dev','budget_bucket':'development','timeout_seconds':1800})
    return rows


def observed_profiles(baseline, baseline_sha):
    result=copy.deepcopy(baseline)
    result['observation_condition']={'name':'n2_common_decision_observed_v1',
        'baseline_path':'configs/qd_ed_final/baseline_profiles.json','baseline_sha256':baseline_sha}
    for profile in result['profiles'].values():
        profile['static_override_values']['main.decision_evidence.enabled']=True
        profile['hydra_overrides'].append('main.decision_evidence.enabled=true')
        profile['historical_label']+='__n2_common_decision_observed_v1'
    return result


def binding(plan, runtime):
    contract=plan['n2_cohort']
    return {'cohort_id':COHORT,'protocol_sha256':contract['protocol']['sha256'],
        'accounting_clarification_sha256':contract['accounting_clarification']['sha256'],
        **{k:plan[k] for k in ('source_commit','profiles_sha256','runtime_manifest_sha256',
                             'runtime_inventory_sha256','seed_plan_sha256')},
        'candidate_sha256':plan['candidate_profiles']['N2']['sha256'],
        'stage_public_config_sha256':runtime['frozen_stage_provider']['public_config_sha256']}


def validate_contract(plan, manifest, runtime, seeds, root, runner):
    r=api(runner); root=Path(root); contract=plan.get('n2_cohort',{})
    r.require(contract.get('schema')=='qd-ed-n2-cohort-v1' and contract.get('cohort_id')==COHORT,
              'N2 requires its explicit prospective cohort contract')
    r.require(contract.get('limits')==LIMITS, 'N2 local resource limits differ')
    r.require(plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}, 'N2 Dev-only phase gate differs')
    paths={x['path']:x['sha256'] for x in plan['code_files']}
    r.require(REQUIRED<=set(paths), 'N2 runtime source fingerprints missing')
    for key,relative in [('protocol',PROTOCOL),('accounting_clarification',CLARIFICATION)]:
        r.require(contract.get(key)=={'path':relative,'sha256':paths[relative]} and
                  r.digest(root/relative)==paths[relative], 'N2 protocol/clarification differs')
    r.require(set(plan['candidate_profiles'])=={'N2'}, 'N2 matrix cannot include another candidate')
    r.require(r.runtime_gpu(runtime)==3 and runtime['frozen_stage_provider'].get('backend')=='codex_cli',
              'N2 requires GPU3 and frozen Codex transport')
    baseline_path=root/'configs/qd_ed_final/baseline_profiles.json'
    candidate=r.read_json(root/PROFILE)
    r.require(candidate.get('baseline_provenance')=={'path':'configs/qd_ed_final/baseline_profiles.json',
        'profile':'Q0.restored_profile','sha256':r.digest(baseline_path)} and candidate.get('action_chunk_horizon')==8,
        'N2 baseline provenance/horizon differs')
    expected=observed_profiles(r.read_json(baseline_path),r.digest(baseline_path))
    r.require(Path(plan['profiles_path']).resolve()==(root/OBSERVED).resolve() and
              r.read_json(plan['profiles_path'])==expected,'N2 common observed baseline drift')
    r.require(all(manifest['profiles'][p]['static_override_values']['main.decision_evidence.enabled'] is True
                  for p in ('C0','Q0','N2')),'N2 common observer is required')
    expected_rows=rows_from_dev(seeds); originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    r.require(originals==expected_rows,'N2 original 30 cells/order/seeds differ')
    recoveries=[x for x in plan['episodes'] if x.get('retry_of')]
    r.require(len(recoveries)<=4,'N2 recovery plan exceeds four')
    identities={json.dumps(r.episode_identity(x),sort_keys=True):x for x in expected_rows}
    used=set()
    for row in recoveries:
        identity=json.dumps(r.episode_identity(row),sort_keys=True)
        r.require(identity in identities and identity not in used,'N2 recovery scientific cell missing/repeated')
        used.add(identity); original=identities[identity]
        actual={k:v for k,v in row.items() if k not in {'episode_key','retry_of','n2_recovery_contract','budget_bucket'}}
        reference={k:v for k,v in original.items() if k not in {'episode_key','budget_bucket'}}
        r.require(actual==reference and row['budget_bucket']=='recovery' and row['episode_key']!=original['episode_key']
            and row.get('n2_recovery_contract')==binding(plan,runtime),'N2 recovery frozen identity differs')
    resources=contract.get('health_resources',[])
    r.require(isinstance(resources,list) and len({x['resource_id'] for x in resources})==len(resources)
        and all(set(x)=={'resource_id','scope'} and x['scope'] in {'reused_prior','new_n2'} for x in resources),
        'N2 health resource attribution differs')
    proof=runtime.get('cuda_egl_probe',{}).get('resource_id')
    r.require(proof and proof in {x['resource_id'] for x in resources},'N2 runtime proof must be explicitly attributed')
    prerequisites=contract.get('runtime_prerequisites',{})
    r.require(plan.get('boot_id')==BOOT and prerequisites.get('boot_id')==BOOT and
        prerequisites.get('reuse_scope')=='prior_engineering_only_not_N2_algorithm_validation' and
        set(prerequisites.get('references',{}))==PREREQUISITES and
        prerequisites.get('native_dependencies')=={'path':DEPENDENCIES,'sha256':paths[DEPENDENCIES]},
        'N2 current-boot engineering prerequisites missing/different')


def read_attestation(reference, plan, root, r, schema):
    r.require(isinstance(reference,dict) and set(reference)=={'path','sha256'},'N2 attestation not released')
    path=r.owned(reference['path'],plan['artifact_root'])
    r.require(r.digest(path)==reference['sha256'],'N2 attestation fingerprint differs')
    value=r.read_json(path)
    r.require(value.get('schema')==schema and value.get('cohort_id')==COHORT and
        value.get('source_commit')==plan['source_commit'] and
        value.get('protocol_sha256')==plan['n2_cohort']['protocol']['sha256'], 'N2 attestation identity differs')
    evidence=value.get('evidence')
    r.require(isinstance(evidence,list) and evidence,'N2 attestation evidence missing')
    for item in evidence:
        path=r.owned(item['path'],plan['artifact_root'])
        r.require(r.digest(path)==item['sha256'],'N2 attestation evidence changed')
    return value


def transport_recovery_eligibility(exc, outcome, plan, row, runtime, runner):
    """Separate prospective eligibility; never rewrite the original outcome."""
    r=api(runner)
    if not plan.get('n2_cohort') or not isinstance(exc,r.GateError) or str(exc)!=TRANSPORT_GATE:
        return None
    if (outcome.get('outcome_valid') is not False or outcome.get('compute_outcome')!='completed'
            or outcome.get('required_cost_telemetry_complete') is not True
            or outcome.get('stage_backend')!='codex_cli'
            or outcome.get('provider_failed_calls',0)<=0
            or outcome.get('stage_failed_queries',0)<=0):
        return None
    return {'schema':'qd-ed-n2-recovery-eligibility-v1','reason':'exact_codex_stage_transport_failure',
            'gate':TRANSPORT_GATE,'frozen_identity':binding(plan,runtime)}


def retry_exception(events, row, runner):
    r=api(runner); certificate=row.get('n2_recovery_contract')
    if not isinstance(certificate,dict) or certificate.get('cohort_id')!=COHORT or str(row['iteration'])!=COHORT:
        return False
    groups=r.event_groups(events)
    prior=[g for g in groups.values() if g[0]['identity']==r.episode_identity(row) and any(e['event']=='dispatched' for e in g)]
    if len(prior)!=1 or row.get('retry_of') not in groups or groups[row['retry_of']]!=prior[0]: return False
    group=prior[0]; final=group[-1]; eligible=final.get('n2_recovery_eligibility',{})
    return (group[0].get('n2_frozen_identity')==certificate==eligible.get('frozen_identity')
        and group[0].get('n2_cohort_id')==COHORT and not group[0].get('retry_of')
        and final['event']=='valid' and final.get('outcome_valid') is False
        and final.get('compute_outcome')=='completed' and final.get('required_cost_telemetry_complete') is True
        and final.get('stage_backend')=='codex_cli' and final.get('provider_failed_calls',0)>0
        and final.get('stage_failed_queries',0)>0
        and final.get('reason')==TRANSPORT_GATE
        and eligible.get('schema')=='qd-ed-n2-recovery-eligibility-v1'
        and eligible.get('reason')=='exact_codex_stage_transport_failure' and eligible.get('gate')==TRANSPORT_GATE)


def admission(plan, runtime, row, events, resources, root, runner):
    r=api(runner); contract=plan['n2_cohort']; expected_binding=binding(plan,runtime)
    groups=r.event_groups(events)
    cohort=[g for g in groups.values() if str(g[0]['identity']['iteration'])==COHORT]
    dispatched=[g for g in cohort if any(e['event']=='dispatched' for e in g)]
    r.require(all(g[0].get('n2_cohort_id')==COHORT and g[0].get('n2_frozen_identity')==expected_binding
                  for g in dispatched),'N2 prior dispatch frozen identity differs')
    r.require(all(g[-1]['event'] in r.TERMINAL for g in cohort),'N2 unfinished attempt')
    same=[g for g in dispatched if g[0]['identity']==r.episode_identity(row)]
    r.require(len(dispatched)<34 and len(same)<2,'N2 episode/cell dispatch allowance exhausted')
    recoveries=sum(bool(g[0].get('retry_of')) for g in dispatched)
    if row.get('retry_of'):
        r.require(len(same)==1 and recoveries<4 and same[0][0].get('retry_of') is None
            and row['retry_of']==same[0][0]['attempt_id'] and row.get('n2_recovery_contract')==expected_binding,
            'N2 recovery allowance/identity differs')
    else:
        r.require(not same,'N2 original cell already dispatched')
    local_seconds=sum(g[-1]['gpu_process_wall_seconds'] for g in dispatched)
    for reference in contract['health_resources']:
        matched=[e for e in resources if e['resource_id']==reference['resource_id']]
        r.require(matched and matched[-1]['event'] in {'completed','aborted'},'N2 declared health resource incomplete')
        if reference['scope']=='new_n2': local_seconds+=matched[-1]['gpu_process_wall_seconds']
    r.require(local_seconds+1800+r.TERMINATION_GRACE_SECONDS<=18*3600,'N2 18-hour allowance cannot cover complete episode/cleanup')
    review=read_attestation(contract.get('recorded_candidate_review'),plan,root,r,'qd-ed-n2-recorded-check-v1')
    r.require(review.get('passed') is True and review.get('changed_recorded_choice') is True,
              'N2 fixed-candidate mechanism prerequisite not met')
    originals=[x for x in plan['episodes'] if not x.get('retry_of')]
    cell_index=next(i for i,x in enumerate(originals) if r.episode_identity(x)==r.episode_identity(row))
    for earlier in originals[:cell_index]:
        completed=[g[-1] for g in dispatched if g[0]['identity']==r.episode_identity(earlier)
                   and g[-1]['event']=='valid' and g[-1].get('outcome_valid') is True]
        r.require(len(completed)==1,'N2 fixed cell order requires prior valid completion')
        audit_path=r.owned(Path(completed[0]['output_dir'])/'eds_eval/decision-evidence-audit.json',plan['artifact_root'])
        r.require(audit_path.is_file(),'N2 prior complete decision evidence audit missing')
        audit=r.read_json(audit_path)
        r.require(audit.get('accepted') is True and audit.get('evidence_complete') is True,
                  'N2 prior complete decision evidence audit rejected')
    if cell_index>=3:
        checkpoint=read_attestation(contract.get('checkpoint_release'),plan,root,r,'qd-ed-n2-checkpoint-v1')
        r.require(checkpoint.get('checks')=={key:True for key in CHECKS},'N2 first-three correctness/activation checkpoint not released')
        attempts=[g[-1]['attempt_id'] for first in originals[:3] for g in dispatched
                  if g[0]['identity']==r.episode_identity(first) and g[-1]['event']=='valid' and g[-1].get('outcome_valid') is True]
        r.require(checkpoint.get('attempt_ids')==attempts and len(attempts)==3,'N2 checkpoint attempt linkage differs')
    return {'n2_cohort_id':COHORT,'n2_frozen_identity':expected_binding}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-plan',type=Path,required=True);parser.add_argument('--runtime-manifest',type=Path,required=True)
    parser.add_argument('--source-head',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--recorded-candidate-review',type=Path)
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('n2_builder_runner',ROOT/'scripts/qd_ed_final_runner.py')
    r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    r.require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==args.source_head,'HEAD differs')
    base=r.read_json(args.base_plan); plan=copy.deepcopy(base); seeds=r.read_json(base['seed_plan_path'])
    runtime=r.read_json(args.runtime_manifest)
    r.require(Path(runtime['worktree']).resolve()==ROOT and r.runtime_gpu(runtime)==3,'integrate/runtime-bind GPU3 before preparation')
    for key in ('seed_plan','runtime_inventory'):
        r.require(r.digest(base[key+'_path'])==base[key+'_sha256'],'frozen input identity differs: '+key)
    for key in ('candidate_profiles','native_probe_contract','diagnostic_only','diagnostic_scope','queue_contract',
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
        candidate_profiles={'N2':{'path':str(ROOT/PROFILE),'sha256':r.digest(ROOT/PROFILE)}})
    scientific={*base['scientific_config_files'],PROFILE,OBSERVED,PROTOCOL,CLARIFICATION}
    paths={x['path'] for x in base['code_files']} | r.REQUIRED_CODE | REQUIRED | scientific
    for path in paths:
        actual=r.owned(ROOT/path,ROOT)
        r.require(actual.read_bytes()==subprocess.check_output(['git','show',args.source_head+':'+path],cwd=ROOT),
                  'source not committed: '+path)
    plan.update(code_files=[{'path':p,'sha256':r.digest(ROOT/p)} for p in sorted(paths)],scientific_config_files=sorted(scientific))
    reference=lambda p:{'path':str(p.resolve()),'sha256':r.digest(p)}
    prior=copy.deepcopy(base['observed_pair_prerequisites'])
    r.require(set(prior)==PREREQUISITES,'base current-boot prerequisites differ')
    health=r.read_json(prior['health_result']['path'])
    plan['n2_cohort']={'schema':'qd-ed-n2-cohort-v1','cohort_id':COHORT,'limits':LIMITS,
        'protocol':{'path':PROTOCOL,'sha256':r.digest(ROOT/PROTOCOL)},
        'accounting_clarification':{'path':CLARIFICATION,'sha256':r.digest(ROOT/CLARIFICATION)},
        'health_resources':[{'resource_id':identifier,'scope':'reused_prior'} for identifier in
            dict.fromkeys([runtime['cuda_egl_probe']['resource_id'],health['resource_id']])],
        'runtime_prerequisites':{'boot_id':BOOT,'references':prior,
            'reuse_scope':'prior_engineering_only_not_N2_algorithm_validation',
            'native_dependencies':{'path':DEPENDENCIES,'sha256':r.digest(ROOT/DEPENDENCIES)}},
        'recorded_candidate_review':reference(args.recorded_candidate_review) if args.recorded_candidate_review else None,
        'checkpoint_release':None}
    plan['preparation_provenance']={'base_plan':reference(args.base_plan),'builder_sha256':r.digest(__file__)}
    destination=r.owned(args.output,Path(plan['artifact_root'])/'continuation_20260923')
    r.require(not destination.exists(),'refusing to overwrite plan')
    manifest=r.read_json(plan['profiles_path']);candidate=r.read_json(ROOT/PROFILE)
    manifest['profiles']['N2']=r.expand_candidate('N2',candidate,manifest['profiles']['Q0'])
    validate_contract(plan,manifest,runtime,seeds,ROOT,r)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x') as stream: json.dump(plan,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps({'status':'unfrozen_prepared','episodes':30,'output':str(destination),
                      'first_checkpoint_keys':[x['episode_key'] for x in plan['episodes'][:3]]}))


if __name__=='__main__': main()
