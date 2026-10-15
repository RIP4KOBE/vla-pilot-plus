"""Independent JSON-only semantics. No production imports or tensor operations."""
import math
import uuid
from pathlib import Path
from bounded_metadata_v1 import need, canonical, same_ref, is_ref

COMMIT='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
COHORT='N26_CLEAN_OUTPUT_RBF_DEV_20260930'
ARMS=('C0','Q0','N25','N26')
GPU='GPU-48473162-9548-1a19-04aa-ea86c5349187'
DEV_LIMITS={'primary_cells':40,'episode_dispatches':42,'recoveries':2,'recoveries_per_cell':1,
 'maximum_local_gpu_hours':22.,'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
WORKER={'schema':'n26-same-process-native-audit-v1','arms':list(ARMS),'cuda_arithmetic_arms':['N25','N26'],
 'other_arm_backend':'cpu','timeout_includes_audit':True,'profile_bound_rbf_audit':True,'witness_exact_backend':'assigned_cuda'}
KINDS=('strict_interior','exact_boundary','mixed_saturation','distinct_saturated','coincident_saturated','coincident_interior')
LAYOUTS={'contiguous':([8192,128,1],0),'transpose':([8192,1,64],0),'model_slice':([8576,128,1],384)}
DTYPES=('torch.float32','torch.bfloat16')
CLIP=('score_batches_verified','candidate_scores_verified','clipped_prefix_candidates','rank_changed_batches')
AUX=('qd_actuator_overhead_seconds','qd_actuator_quality_batches','qd_actuator_quality_candidates','qd_actuator_clipped_prefix_candidates')
COST=('gpu_process_wall_seconds','guided_chunks','unguided_chunks','candidate_evaluations','score_batches',
 'rbf_gradient_calls','rbf_gradient_batch_rows','model_forward_calls','model_batch_rows','reward_calls','reward_evaluations','reward_scoring_batches',
 'provider_logical_call_attempts','stage_codex_logical_call_attempts','provider_input_tokens','provider_output_tokens','provider_cached_input_tokens','provider_failed_calls')
COMPUTE=('model_forward_calls','model_batch_rows','denoising_invocations','model_denoising_steps','denoising_step_batch_rows',
 'reward_calls','reward_evaluations','reward_scoring_batches','guided_chunks','unguided_chunks','stage_api_request_attempts','stage_api_sdk_retry_attempts',
 'guidance_api_request_attempts','guidance_api_sdk_retry_attempts','grounding_api_request_attempts','grounding_api_sdk_retry_attempts',
 'provider_request_attempts','provider_sdk_retry_attempts','rbf_gradient_calls','rbf_gradient_batch_rows','renoise_invocations',
 'vision_encoder_forward_calls','vision_encoder_batch_rows','text_encoder_forward_calls','text_encoder_batch_rows','dino_forward_calls','dino_batch_rows')
UNKNOWN_HTTP={'stage_api_request_attempts','stage_api_sdk_retry_attempts','provider_request_attempts','provider_sdk_retry_attempts'}
TOKENS=('logical_call_attempts','completed_turns','failed_calls','usage_complete_calls','input_tokens','cached_input_tokens','output_tokens')
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
    need(set(source)=={'commit','files','sha256'} and source['commit']==COMMIT and len(source['files'])==315,'original315 source')
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
def calls(metric,arm):
    initial=metric.get('initial_direction_rbf_evidence_by_step');roll=metric.get('rollout_direction_rbf_evidence_by_iter')
    rounds=metric.get('rollout_rbf_steps_by_iter')
    need(metric.get('initial_diversity_descriptor_mode')==metric.get('rollout_diversity_descriptor_mode')=='actuator_clipped_eef_v1','RBF mode')
    need(isinstance(initial,list) and isinstance(roll,list) and len(roll)==10 and isinstance(rounds,list) and len(rounds)==10,'RBF group shape')
    need(len(initial)==metric.get('initial_diversity_steps') and (arm!='N26' or len(initial)==4),'initial calls')
    need(sum(map(len,roll))==metric.get('rollout_diversity_steps_applied'),'rollout calls')
    for i,(rows,info,length) in enumerate(zip(roll,rounds,(3,2,2,2,2,1,1,1,1,1))):
        flags=[j<math.ceil(length*.6) for j in range(length)];indices=[j for j,v in enumerate(flags) if v]
        need(info.get('n_trunc_steps')==length and info.get('iter_idx')==i and info.get('step_indices')==indices
             and info.get('step_flags')==flags and info.get('step_count')==len(rows)==len(indices) and info.get('fallback_used') is False,'rollout schedule')
        need([v.get('denoising_step') for v in rows]==indices and all(v.get('phase')=='rollout' and v.get('iteration')==i for v in rows),'rollout identity')
    need([v.get('denoising_step') for v in initial]==list(range(len(initial)))
         and all(v.get('phase')=='initial' and v.get('iteration')==-1 for v in initial),'initial identity')
    for rows in [initial,*roll]:
        need(all(a['timestep']>b['timestep'] for a,b in zip(rows,rows[1:])),'denoising order')
    allrows=initial+[v for rows in roll for v in rows]
    for v in allrows:
        need(v.get('schema')==arm.lower()+'-rbf-call-summary-v1' and v.get('descriptor_mode')=='actuator_clipped_eef_v1'
             and v.get('source')==('core.qd_clean_output_rbf:model_output_sample_v1' if arm=='N26' else 'core.qd_actuator_clipped_rbf:clipped_rbf_gradient:v1')
             and v.get('absolute_fallback_used') is False and v.get('summary_only_not_exact_replay') is True
             and v.get('input_shape')==[16,64,128] and v.get('input_dtype') in DTYPES and v.get('horizon')==8
             and v.get('translation_indices')==[39,40,41] and v.get('translation_components')==384
             and v.get('update_operand_is_measured_output_delta') is False,'scalar provenance')
        need(all(integer(v.get(k)) for k in ('clipped_components','boundary_components','interior_components'))
             and sum(v[k] for k in ('clipped_components','boundary_components','interior_components'))==384
             and v.get('nonfinite_count')==0 and type(v.get('zero_gradient')) is bool,'component denominator')
        for k in ('gradient_before_normalization','gradient_after_normalization','masked_gradient','update_operand'):
            q=v.get(k,{})
            need(q.get('finite') is True and type(q.get('zero')) is bool and number(q.get('norm'))
                 and q.get('norm_dtype') in DTYPES and (not q['zero'] or q['norm']==0),'norm metadata')
        need(v['zero_gradient']==v['gradient_after_normalization']['zero'] and v.get('global_step')==metric.get('global_step')
             and all(type(v.get(k)) is int for k in ('iteration','denoising_step','timestep','global_step','stage'))
             and v['denoising_step']>=0 and v['timestep']>=0,'call identity/zero')
        if arm=='N26':
            need(v.get('input_source')=='model_output_sample_v1' and v.get('prediction_type')=='sample'
                 and v.get('input_binding')=='same_forward_unmodified_model_output' and v.get('model_jacobian_used') is False
                 and v.get('input_stride') in [x[0] for x in LAYOUTS.values()],'clean input provenance')
    return allrows
def native_counts(arm,metrics,compute,audit,final):
    need(audit.get('accepted') is True and audit.get('evidence_complete') is True,'native report not accepted')
    n=len(metrics);observed=audit.get('observed_counts',{})
    need(type(final.get('guided_chunks')) is int and final['guided_chunks']==n==compute.get('guided_chunks')
         and compute.get('policy_counters_available') is True and observed.get('canonical_candidate_batch',0)==11*n,'native guided/canonical denominator')
    need(all(m.get('score_call_count')==11 and m.get('search_evaluation_count')==176
             and all(m.get(k)==10 for k in ('resample_count','renoise_count','rollout_count')) for m in metrics),'fixed compute')
    result={'guided_decisions':n,'parent_rounds_verified':0};aux={}
    if arm in ('C0','Q0'):
        need(all(m.get('qd_quality_mode','provider')=='provider' and m.get('qd_gripper_rescue_mode','none')=='none'
                 and m.get('qd_archive_active_for_chunk') is (arm=='Q0')
                 and m.get('initial_diversity_descriptor_mode','absolute_eef')==m.get('rollout_diversity_descriptor_mode','absolute_eef')=='absolute_eef' for m in metrics),'legacy control fields')
        need(not any(audit.get(k) for k in ('n24_gripper_parent_rescue_audit','n23_actuator_clipped_quality_audit','n25_actuator_clipped_rbf_audit','n26_clean_output_rbf_audit')),'control non-default audit')
        return result,aux
    selection=audit.get('n5_grasp_timing_audit',{});clip=audit.get('n23_actuator_clipped_quality_audit',{})
    need(not audit.get('n24_gripper_parent_rescue_audit'),'rescue must remain off')
    if n:
        need(all(selection.get(k)==v for k,v in {'checked_decisions':n,'parent_rounds_verified':10*n,
             'canonical_batches_verified':11*n,'canonical_candidates_verified':176*n}.items()),'parent/selection evidence')
        need(all(m.get('qd_archive_active_for_chunk') is True and m.get('qd_quality_mode')=='actuator_clipped_provider_v1'
             and m.get('qd_descriptor')=='target_xy_quadrant_signed_height_v1' and m.get('qd_final_selection_mode')=='terminal_grasp_proximity_v1'
             and m.get('qd_gripper_rescue_mode','none')=='none' for m in metrics),'frozen scientific modes')
        need(clip.get('score_batches_verified')==11*n and clip.get('candidate_scores_verified')==176*n
             and all(integer(clip.get(k)) for k in CLIP),'quality counters')
        result.update({k:clip[k] for k in CLIP});result['parent_rounds_verified']=10*n
        for k in AUX:
            need(all(number(m.get(k)) for m in metrics),'auxiliary missing');aux[k]=sum(m[k] for m in metrics)
        need(aux['qd_actuator_quality_batches']==11*n and aux['qd_actuator_quality_candidates']==176*n
             and aux['qd_actuator_clipped_prefix_candidates']==clip['clipped_prefix_candidates'],'auxiliary counters')
    else:need(not selection and not clip,'unguided nonempty quality gate')
    key='n26_clean_output_rbf_audit' if arm=='N26' else 'n25_actuator_clipped_rbf_audit'
    opposite='n25_actuator_clipped_rbf_audit' if arm=='N26' else 'n26_clean_output_rbf_audit'
    gate=audit.get(key);need(not audit.get(opposite) and isinstance(gate,dict) and gate.get('schema')==arm.lower()+'-native-rbf-audit-v1'
        and gate.get('accepted') is True and gate.get('guided_decisions')==n,'profile-bound native gate missing')
    allcalls=[q for m in metrics for q in calls(m,arm)]
    need(gate.get('all_call_summaries_verified')==len(allcalls) and integer(gate.get('witness_calls_verified'))
         and (gate['witness_calls_verified']==(11 if n else 0) if arm=='N26' else gate['witness_calls_verified']<=11),'witness coverage')
    need(compute.get('rbf_gradient_calls')==len(allcalls) and compute.get('rbf_gradient_batch_rows')==16*len(allcalls),'RBF compute')
    need(gate.get('zero_gradient_calls')==sum(v['zero_gradient'] for v in allcalls)
         and gate.get('clipped_components')==sum(v['clipped_components'] for v in allcalls),'scalar counters')
    result.update({k:gate[k] for k in ('all_call_summaries_verified','witness_calls_verified','zero_gradient_calls','clipped_components')})
    return result,aux
def compute_binding(compute,row,final,runtime,valid):
    need(compute.get('schema')=='qd-ed-episode-compute-v2' and compute.get('episode_id')==0
         and compute.get('task_id')==row['task_id'] and compute.get('episode_seed')==row['env_seed'],'compute identity')
    need(all(compute.get(k) is True for k in ('policy_counters_available','provider_counters_available','perception_counters_available')),'compute availability')
    for k in COMPUTE:
        need((k in compute and compute[k] is None) if k in UNKNOWN_HTTP else integer(compute.get(k)),'compute counter')
        need(final.get(k)==compute[k],'terminal/compute counter')
    sizes=compute.get('model_forward_batch_sizes')
    need(isinstance(sizes,list) and all(type(x) is int and x>0 for x in sizes)
         and len(sizes)==compute['model_forward_calls'] and sum(sizes)==compute['model_batch_rows'],'model call accounting')
    frozen=runtime.get('frozen_stage_provider',{});transport=compute.get('stage_transport',{})
    need(frozen.get('backend')=='codex_cli' and frozen.get('model')=='gpt-6-astra' and frozen.get('reasoning_effort')=='low'
         and frozen.get('timeout_seconds')==180 and all(transport.get(k)==frozen[k] for k in
          ('backend','model','reasoning_effort','timeout_seconds','cli_path','disabled_skill_paths','public_config_sha256'))
         and transport.get('auth_mode')=='chatgpt' and transport.get('application_max_attempts')==1
         and transport.get('allow_recovered_error_events') is True and transport.get('recovered_error_policy')=='pre_final_only_v1'
         and transport.get('internal_http_retry_observation_available') is False and transport.get('internal_retry_policy')=='cli_managed_unknown','Codex-only frozen transport')
    need(compute.get('provider_http_counters_available') is False and compute.get('provider_logical_counters_available') is True
         and all(compute[k]==0 for k in ('guidance_api_request_attempts','guidance_api_sdk_retry_attempts','grounding_api_request_attempts','grounding_api_sdk_retry_attempts')),'provider observation scope')
    for suffix in (*TOKENS,'call_latency_s','reasoning_output_tokens'):
        a=compute.get('provider_'+suffix);b=compute.get('stage_codex_'+suffix)
        need(a==b and final.get('provider_'+suffix)==a and final.get('stage_codex_'+suffix)==b,'provider/Stage/terminal counters')
        need((a is None or integer(a)) if suffix=='reasoning_output_tokens' else number(a) if suffix=='call_latency_s' else integer(a),'provider counter type')
    count=compute['provider_logical_call_attempts'];complete=compute['provider_usage_complete_calls']
    need(all(compute['provider_'+k]<=count for k in ('completed_turns','failed_calls','usage_complete_calls'))
         and compute['provider_cached_input_tokens']<=compute['provider_input_tokens']
         and compute.get('provider_token_usage_complete') is (count==complete)
         and final.get('provider_token_usage_complete') is (count==complete),'unknown-token labels')
    need(final.get('compute_outcome')==compute.get('outcome'),'compute outcome')
    if valid:
        need(final.get('required_cost_telemetry_complete') is True and count==complete and compute['provider_failed_calls']==0
             and final.get('candidate_evaluations')==176*compute['guided_chunks'] and final.get('score_batches')==11*compute['guided_chunks'],'valid scientific compute')
def proof_metadata(reader,reference,source,runtime_ref,events):
    p=reader.get(reference,'proof')
    need(set(p)=={'schema','accepted','source','runtime','plan','report','process','terminal'} and p['schema']=='n26-metered-tensor-proof-v1'
         and p['accepted'] is True and p['source']==source and same_ref(p['runtime'],runtime_ref),'same-source36 proof')
    plan=reader.get(p['plan'],'proof_plan');report=reader.get(p['report'],'proof_report')
    process=reader.get(p['process'],'proof_process');terminal=reader.get(p['terminal'],'proof_terminal')
    limits={'resource_processes':1,'episode_attempts':0,'model_calls':0,'api_calls':0,'simulation_steps':0,
      'timeout_seconds':60,'cleanup_seconds':40,'physical_gpu':7,'health_gpu_hours_bucket':'recovery'}
    need(plan.get('schema')=='n26-tensor-resource-plan-v1' and plan.get('frozen') is True and plan.get('kind')=='n26_tensor_arithmetic_v1'
         and plan.get('source')==source and same_ref(plan.get('runtime'),runtime_ref) and plan.get('limits')==limits,'proof plan')
    group=[e for e in events if e.get('resource_id')==plan['resource_id']]
    need(group==events and [e['event'] for e in group]==['reserved','dispatched','completed']
         and all(e.get('kind')=='n26_tensor_arithmetic_v1' and same_ref(e.get('plan'),p['plan']) for e in group),'one settled resource')
    need(group[-1]==terminal and terminal.get('cleanup_complete') is True and terminal.get('cost_measurement_complete') is True
         and same_ref(terminal.get('report'),p['report']) and same_ref(terminal.get('process'),p['process'])
         and report.get('resource_id')==process.get('resource_id')==plan['resource_id'],'proof process/terminal')
    need(report.get('schema')=='n26-tensor-arithmetic-report-v1' and report.get('accepted') is True and report.get('errors')==[]
         and report.get('source')==source and same_ref(report.get('runtime'),runtime_ref) and same_ref(report.get('plan'),p['plan'])
         and report.get('process')==process_identity(process) and report.get('process_unchanged') is True
         and all(type(report.get(k)) is int and report[k]==0 for k in ('model_calls','api_calls','simulation_steps','episodes')),'proof report')
    cuda_identity(report.get('backend',{}));need(set(DTYPES)<=set(report['backend'].get('dtype_coverage',[])),'proof dtypes')
    expected=[(d,k,l) for d in DTYPES for k in KINDS for l in LAYOUTS];cases=report.get('cases',[])
    need([(x.get('dtype'),x.get('case'),x.get('layout')) for x in cases]==expected,'36-case coverage')
    for q in cases:
        need(q.get('accepted') is True and q.get('candidate_rows')==16 and q.get('comparison')=='native contiguous uint8; zero tolerance'
             and all(q.get(k) is True for k in ('custom_boundary_derivative_verified','clean_object_selection_verified','clean_input_binding_verified','wrong_source_rejected','signed_zero_rejected'))
             and q.get('production_projection_calls')==q.get('production_origin_reads')==16
             and q.get('invalid_inputs_rejected')==['nonfinite','wrong_horizon'] and type(q.get('zero_gradient')) is bool
             and q.get('input_stride')==LAYOUTS[q['layout']][0] and q.get('synthetic_storage_offset')==LAYOUTS[q['layout']][1]
             and q.get('sample_only_negative_controls')==[None,'epsilon','v_prediction']
             and q.get('interior_original_parity')==(True if q['case']=='strict_interior' else None)
             and q.get('negative_controls_rejected')==['input_xyz','projected_xyz','gradient_before','gradient_after','update_operand','model_output_before','model_output_after'],'proof cases')
    need(number(report.get('worker_wall_seconds')) and number(terminal.get('gpu_process_wall_seconds'))
         and report['worker_wall_seconds']<=60 and report['worker_wall_seconds']<=terminal['gpu_process_wall_seconds']<=100,'proof health cost')
    return p,terminal['gpu_process_wall_seconds'],process

