"""Independent JSON-only semantics. No production imports or tensor operations."""
import math
import uuid
from pathlib import Path
from bounded_json_v1 import need, canonical, same_ref, is_ref

COMMIT='095cfeecd6af55477d2529441c307ab712e8a8da'
COHORT='N27_FEASIBLE_RAY_SCREEN_20261001'
ARMS=('C0','Q0','N26','N27')
GPU='GPU-48473162-9548-1a19-04aa-ea86c5349187'
DEV_LIMITS={'primary_cells':16,'episode_dispatches':18,'recoveries':2,'recoveries_per_cell':1,
 'maximum_local_gpu_hours':9.25,'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
WORKER={'schema':'n27-same-process-native-audit-v1','arms':list(ARMS),'cuda_arithmetic_arms':['N26','N27'],
 'other_arm_backend':'cpu','timeout_includes_audit':True,'profile_bound_rbf_audit':True,'witness_exact_backend':'assigned_cuda'}
KINDS=('strict_interior','exact_boundary','mixed_saturation','distinct_saturated','coincident_saturated','coincident_interior')
LAYOUTS={'contiguous':([8192,128,1],0),'transpose':([8192,1,64],0),'model_slice':([8576,128,1],384)}
DTYPES=('torch.float32','torch.bfloat16')
CLIP=('score_batches_verified','candidate_scores_verified','clipped_prefix_candidates','rank_changed_batches')
AUX=('qd_actuator_overhead_seconds','qd_actuator_quality_batches','qd_actuator_quality_candidates','qd_actuator_clipped_prefix_candidates')
COST=('gpu_process_wall_seconds','guided_chunks','unguided_chunks','candidate_evaluations','score_batches',
 'rbf_gradient_calls','rbf_gradient_batch_rows','model_forward_calls','model_batch_rows','reward_calls','reward_evaluations','reward_scoring_batches',
 'provider_logical_call_attempts','stage_codex_logical_call_attempts','provider_input_tokens','provider_output_tokens','provider_cached_input_tokens','provider_failed_calls')
DERIVATIVE={'Codex token usage incomplete','Codex Stage call failure invalidates the frozen transport condition',
 'Codex Stage event lacks one measured call with complete usage'}
def number(x):return type(x) in (int,float) and math.isfinite(x) and x>=0
def integer(x):return type(x) is int and x>=0
def identity(row):return {k:row[k] for k in ('split','iteration','profile','task_id','env_seed','policy_seed','init_index')}
def process_identity(p):
    v={k:p[k] for k in ('pid','proc_start_ticks','boot_id')}
    need(type(v['pid']) is int and v['pid']>0 and isinstance(v['proc_start_ticks'],str)
         and v['proc_start_ticks'].isdigit() and isinstance(v['boot_id'],str) and bool(v['boot_id']),'process identity')
    return v
def source_record(source):
    need(set(source)=={'commit','files','sha256'} and source['commit']==COMMIT and len(source['files'])==345,'original345 source')
    names=[x['path'] for x in source['files']]
    need(names==sorted(set(names)) and all(set(x)=={'path','sha256'} and not Path(x['path']).is_absolute()
         and '..' not in Path(x['path']).parts for x in source['files']) and canonical(source['files'])==source['sha256'],'source closure')
def cuda_identity(v):
    raw=v.get('actual_uuid');need(isinstance(raw,str),'public UUID string missing')
    try:normal='GPU-'+str(uuid.UUID(raw.removeprefix('GPU-').removeprefix('gpu-')))
    except (ValueError,AttributeError):need(False,'malformed public UUID')
    diag=v.get('identity_diagnostic',{})
    need(normal==v.get('physical_uuid')==GPU and v.get('physical_gpu')==7 and v.get('logical_device')=='cuda:0'
         and v.get('actual_uuid_type') in {'builtins.str','torch._C._CUuuid'} and diag.get('status')=='matched'
         and diag.get('visible_device_count')==1 and diag.get('current_device')==0 and diag.get('cuda_visible_devices') in {'7',GPU},'native CUDA identity')
    need(v.get('actual_uuid_bytes_hex')==(GPU[4:].replace('-','') if v['actual_uuid_type']=='torch._C._CUuuid' else None),'UUID native bytes')

def proof_metadata(reader,reference,source,runtime_ref,events):
    p=reader.get(reference,'proof')
    need(set(p)=={'schema','accepted','source','runtime','plan','report','process','terminal'} and p['schema']=='n27-metered-tensor-proof-v1'
         and p['accepted'] is True and p['source']==source and same_ref(p['runtime'],runtime_ref),'same-source36 proof')
    plan=reader.get(p['plan'],'proof_plan');report=reader.get(p['report'],'proof_report')
    process=reader.get(p['process'],'proof_process');terminal=reader.get(p['terminal'],'proof_terminal')
    limits={'resource_processes':1,'episode_attempts':0,'model_calls':0,'api_calls':0,'simulation_steps':0,
      'timeout_seconds':120,'cleanup_seconds':40,'physical_gpu':7,'health_gpu_hours_bucket':'recovery'}
    need(plan.get('schema')=='n27-tensor-resource-plan-v1' and plan.get('frozen') is True and plan.get('kind')=='n27_tensor_arithmetic_v1'
         and plan.get('source')==source and same_ref(plan.get('runtime'),runtime_ref) and plan.get('limits')==limits,'proof plan')
    group=[e for e in events if e.get('resource_id')==plan['resource_id']]
    need(group==events and [e['event'] for e in group]==['reserved','dispatched','completed']
         and all(e.get('kind')=='n27_tensor_arithmetic_v1' and same_ref(e.get('plan'),p['plan']) for e in group),'one settled resource')
    need(group[-1]==terminal and terminal.get('cleanup_complete') is True and terminal.get('cost_measurement_complete') is True
         and same_ref(terminal.get('report'),p['report']) and same_ref(terminal.get('process'),p['process'])
         and report.get('resource_id')==process.get('resource_id')==plan['resource_id'],'proof process/terminal')
    need(report.get('schema')=='n27-tensor-arithmetic-report-v1' and report.get('accepted') is True and report.get('errors')==[]
         and report.get('source')==source and same_ref(report.get('runtime'),runtime_ref) and same_ref(report.get('plan'),p['plan'])
         and report.get('process')==process_identity(process) and report.get('process_unchanged') is True
         and all(type(report.get(k)) is int and report[k]==0 for k in ('model_calls','api_calls','simulation_steps','episodes')),'proof report')
    cuda_identity(report.get('backend',{}));need(set(DTYPES)<=set(report['backend'].get('dtype_coverage',[])),'proof dtypes')
    expected=[(d,k,l) for d in DTYPES for k in KINDS for l in LAYOUTS];cases=report.get('cases',[])
    need([(x.get('dtype'),x.get('case'),x.get('layout')) for x in cases]==expected,'36-case coverage')
    for q in cases:
        need(q.get('accepted') is True and q.get('candidate_rows')==16 and q.get('comparison')=='native contiguous uint8; zero tolerance'
             and all(q.get(k) is True for k in ('custom_boundary_derivative_verified','clean_object_selection_verified','clean_input_binding_verified','wrong_source_rejected','signed_zero_rejected','feasible_ray_verified','tail_mask_rng_verified'))
             and q.get('rng_scope')=='cpu_and_assigned_cuda'
             and q.get('production_projection_calls')==q.get('production_origin_reads')==16
             and q.get('invalid_inputs_rejected')==['nonfinite','wrong_horizon'] and type(q.get('zero_gradient')) is bool
             and q.get('input_stride')==LAYOUTS[q['layout']][0] and q.get('synthetic_storage_offset')==LAYOUTS[q['layout']][1]
             and q.get('sample_only_negative_controls')==[None,'epsilon','v_prediction']
             and q.get('interior_original_parity')==(True if q['case']=='strict_interior' else None)
             and q.get('negative_controls_rejected')==['input_xyz','projected_xyz','gradient_before','gradient_after','update_operand','model_output_before','model_output_after'],'proof cases')
    need(number(report.get('worker_wall_seconds')) and number(terminal.get('gpu_process_wall_seconds'))
         and report['worker_wall_seconds']<=120 and report['worker_wall_seconds']<=terminal['gpu_process_wall_seconds']<=160,'proof health cost')
    return p,terminal['gpu_process_wall_seconds'],process

def recovery_metadata(reader,binding,primary_binding,primary,recovered,row,plan,refs,source):
    reference=binding.get('eligibility');record=reader.get(reference,'eligibility')
    attest=reader.get(binding.get('recovery_attestation'),'recovery_attestation')
    need(record.get('schema')=='n27-typed-timeout-eligibility-v1' and record.get('cohort_id')==COHORT
         and record.get('primary_attempt_id')==primary['attempt_id'] and record.get('episode_key')==row['episode_key']
         and record.get('scientific_row')==row and record.get('source_commit')==COMMIT
         and same_ref(record.get('plan'),refs['plan']) and record.get('primary_outcome_valid') is False
         and record.get('unknown_token_calls')==1 and record.get('retry_budget_bucket')=='recovery'
         and record.get('same_cell_max_recoveries')==1,'typed recovery envelope')
    d=record.get('diagnostic',{})
    pr=primary_binding['refs']
    need(all(same_ref(record.get(k),pr[v]) for k,v in
         (('terminal','terminal'),('native_receipt','receipt'),('native_report','audit'),('process','process'))),
         'eligibility exact primary evidence')
    need(d.get('schema')=='n23-v2-timeout-diagnostic-v1' and d.get('attempt_id')==primary['attempt_id']
         and d.get('source_commit')==COMMIT and d.get('plan_sha256')==refs['plan']['sha256']
         and d.get('eligible_infrastructure_only') is True and d.get('outcome_valid') is False
         and set(d.get('derivative_gate_failures',[]))==DERIVATIVE and len(d['derivative_gate_failures'])==3
         and d.get('unknown_token_calls')==1 and d.get('token_usage')=={'input_tokens':None,'cached_input_tokens':None,'output_tokens':None}
         and d.get('evidence_files')==record.get('evidence_files'),'typed derivative metadata')
    need(record.get('timeout_observability')==d.get('timeout_observability')
         and is_ref(record.get('timeout_observability'))
         and record['timeout_observability']['sha256']=='fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'
         and is_ref(record.get('protocol'))
         and record['protocol']['sha256']=='165d4efd83a7bf86a5bc1c42c0bea31272b69a86501ee22598bd2a1c6c9fa280'
         and record.get('evidence_packaging_mode') in {'unchanged_original_reader','n27_absent_zero_guided_private_reader'}
         and d.get('guided_chunks')==primary.get('guided_chunks')
         and d.get('candidate_evaluations')==176*primary['guided_chunks']
         and d.get('score_batches')==11*primary['guided_chunks']
         and d.get('original_required_cost_telemetry_complete') is False
         and d.get('all_attempt_token_usage_complete') is False
         and d.get('observed_token_totals')=={k:primary['provider_'+k] for k in ('input_tokens','cached_input_tokens','output_tokens')},
         'typed frozen protocol/derived counters')
    need(primary.get('event')=='valid' and primary.get('outcome_valid') is False and primary.get('compute_outcome')=='completed'
         and primary.get('reason') in DERIVATIVE-{'Codex Stage event lacks one measured call with complete usage'}
         and primary.get('required_cost_telemetry_complete') is False and primary.get('provider_token_usage_complete') is False
         and 0<primary['gpu_process_wall_seconds']<=1800 and primary.get('provider_failed_calls')==1
         and primary.get('stage_codex_failed_calls')==1 and primary.get('provider_logical_call_attempts',0)>1
         and primary.get('provider_usage_complete_calls')==primary['provider_logical_call_attempts']-1
         and primary.get('provider_completed_turns')==primary['provider_logical_call_attempts']-1,'sole completed timeout identity')
    source_hash={x['path']:x['sha256'] for x in source['files']}
    for reference,path in ((record.get('evidence_packaging_reader'),'scripts/qd_ed_n27_recovery.py'),
                           (d.get('diagnostic_reader'),'scripts/qd_ed_n23_v2_recovery.py')):
        need(is_ref(reference) and Path(reference['path']).resolve()==Path(plan['worktree']).resolve()/path
             and reference['sha256']==source_hash[path],'original classifier source')
    need(attest.get('schema')=='n27-original-typed-eligibility-attestation-v1'
         and same_ref(attest.get('eligibility'),binding['eligibility']) and attest.get('source')==refs['source']
         and attest.get('plan')==refs['plan'] and attest.get('primary_attempt_id')==primary['attempt_id']
         and attest.get('method')=='original_frozen_controller_and_classifier_metadata'
         and attest.get('classification_basis_sha256')==canonical(record)
         and attest.get('root_verified_original_basis') is True
         and attest.get('stage_and_tensors_reaudited_by_terminal_reader') is False
         and is_ref(attest.get('collector')),'missing explicit root classifier provenance')
    need(recovered.get('retry_of')==primary['attempt_id'] and recovered.get('budget_bucket')=='recovery'
         and same_ref(recovered.get('n27_recovery_eligibility'),binding['eligibility']),'retry identity')
