"""Independent synthetic writer-shaped records; never imports owning study modules."""
import copy
import json
from pathlib import Path
from bounded_metadata_v1 import canonical,digest
from metadata_semantics_v1 import COMMIT,COHORT,ARMS,COMPUTE,UNKNOWN_HTTP,TOKENS,COST,CLIP,AUX,DTYPES,KINDS,LAYOUTS,GPU,DEV_LIMITS,WORKER

class Fixture:
    def __init__(self,tmp,n=40,candidate=5,control=2,disposition=None,invalid=False,recovery=False,zero=False):
        self.root=Path(tmp);self.files=[];self.values={};self.refs={};self.bindings=[];self.events=[];self.attempts=[];self.cells=[]
        self.source_root=self.root/'study_worktree';self.source_root.mkdir()
        names=['scripts/qd_ed_n26_report.py','scripts/qd_ed_n26_supervise.py','scripts/qd_ed_n26_recovery.py','scripts/qd_ed_n23_v2_recovery.py']
        names += [f'core/frozen_{i:03}.py' for i in range(311)]
        files=[{'path':x,'sha256':digest(('source '+x).encode())} for x in sorted(names)]
        self.source={'commit':COMMIT,'files':files,'sha256':canonical(files)}
        self.put('source',self.source)
        self.rows=[{'episode_key':f'n26_dev_t{t:02}_{a.lower()}','split':'dev','iteration':COHORT,'profile':a,
                    'task_id':t,'env_seed':100+t,'policy_seed':200+t,'init_index':t,'init_row_sha256':'1'*64,
                    'budget_bucket':'baseline' if a=='C0' else 'development','timeout_seconds':1800}
                   for t in range(10) for a in ARMS]
        collector=self.root/'collector.py';collector.write_bytes(b'# synthetic collector; never executed\n')
        self.static_ref={'path':str(collector),'sha256':digest(collector.read_bytes())}
        self.runtime={'environment':{},'gpu_mapping':{'physical_gpu':7,'uuid':GPU,'egl_device_index':4},
           'frozen_stage_provider':{'backend':'codex_cli','model':'gpt-6-astra','reasoning_effort':'low','timeout_seconds':180.,
              'cli_path':'/usr/bin/codex','disabled_skill_paths':[],'public_config_sha256':'b'*64}}
        self.put('runtime',self.runtime)
        self.plan={'source_commit':COMMIT,'code_files':files,'frozen':True,
          'phase_authorization':{'dev':True,'validation':False,'formal':False},'worktree':str(self.source_root),
          'artifact_root':str(self.root/'artifacts'),'episodes':self.rows,'runtime_manifest_sha256':self.refs['runtime']['sha256'],
          'runtime_manifest_path':self.refs['runtime']['path'],'runtime_inventory_sha256':'c'*64,'profiles_sha256':'d'*64,
          'n26_cohort':{'final_review':None,'limits':DEV_LIMITS,'worker_audit':WORKER,
                        'authority':{'path':str(self.root/'authority.json'),'sha256':'f'*64}}}
        # Original N26 plan carries final_review; it has no source_bridge field.
        placeholder={'path':str(self.root/'source_review.json'),'sha256':'0'*64}
        self.plan['n26_cohort']['final_review']=placeholder
        self.put('plan',self.plan)
        templates=[{'episode_key':r['episode_key'],'argv':['/env/bin/python',str(self.source_root/'main.py'),'job=__N26_REVIEW_ATTEMPT__']} for r in self.rows]
        self.pre={'schema':'n26-terminal-prerequisite-attestation-v1','source':self.refs['source'],'plan':self.refs['plan'],
          'runtime':self.refs['runtime'],'source_commit':COMMIT,'source_files_verified':315,'operations':['validate_plan','build_command'],
          'all_prerequisites_passed':True,'model_api_sim_calls':0,'historical_proof_lineage_verified':True,'collector':self.static_ref,
          'source_bridge':None,'command_templates':templates}
        self.proof()
        predecessor={'path':str(self.root/'predecessor.json'),'sha256':'4'*64}
        bridge={'schema':'n26-source-equivalence-bridge-logical-v1','new_source':self.source,'runtime':self.refs['runtime'],
          'new_rbf_arithmetic_proof_required':True,'prior_n25_backend_proof':{'path':str(self.root/'old-proof.json'),'sha256':'5'*64},
          'prior_backend_proof':{'path':str(self.root/'quality-proof.json'),'sha256':'6'*64}}
        self.put('source_bridge',bridge)
        self.put('source_review',{'schema':'n26-source-runtime-review-v1','disposition':'accepted','source':self.source,
          'runtime':self.refs['runtime'],'source_bridge':self.refs['source_bridge'],'backend_proof':self.refs['proof'],
          'predecessor':predecessor,'no_gpu_release':True})
        self.plan['n26_cohort']['final_review']=self.refs['source_review'];self.put('plan',self.plan)
        self.pre.update(plan=self.refs['plan'],source_bridge=self.refs['source_bridge'],proof=self.refs['proof'],predecessor_current_subset_checked=True,
          historical_lineage={'predecessor':predecessor,'prior_n25_backend_proof':bridge['prior_n25_backend_proof'],
            'prior_quality_proof':bridge['prior_backend_proof'],'original_n25_disposition':'INVALID_OR_INTERRUPTED',
            'logical_n25_disposition':'REJECT_NUMERIC_FUTILITY'})
        self.put('precheck',self.pre)
        self.put('release',{'schema':'n26-dev-execution-release-v1','source_commit':COMMIT,'plan':self.refs['plan'],'cohort_id':COHORT,
            'episode_keys':[r['episode_key'] for r in self.rows],'physical_gpu':7,'limits':DEV_LIMITS,'authority':self.plan['n26_cohort']['authority'],
            'validation_authorized':False,'formal_authorized':False})
        self.controller_pid={'pid':9000,'proc_start_ticks':'90','boot_id':'old-boot'}
        self.put('controller',{'schema':'n26-root-controller-process-v1','process':self.controller_pid,'source_commit':COMMIT,
           'plan':self.refs['plan'],'release':self.refs['release'],'entrypoint':{'path':str(self.source_root/'scripts/qd_ed_n26_supervise.py'),
              'sha256':next(x['sha256'] for x in files if x['path']=='scripts/qd_ed_n26_supervise.py')},
           'wrapper':self.static_ref,'physical_gpu':7,'one_launch':True})
        self.native={a:{} for a in ARMS};self.aux={a:{} for a in ARMS};self.processes={'controller':self.controller_pid,'proof':self.proof_pid}
        for index,row in enumerate(self.rows[:n]):
            success=row['task_id']<(candidate if row['profile']=='N26' else control)
            if (index in recovery if isinstance(recovery,(tuple,list,set)) else recovery and index==0):
                primary=self.attempt(row,index,'primary',False,False,zero,typed=True)
                final=self.attempt(row,index,'recovery',True,success,zero,retry=primary)
                self.eligibility(primary,final,row)
            else:final=self.attempt(row,index,'primary',True,success,zero)
            self.accept(final,row,zero)
        self.invalid=invalid
        if invalid:self.attempt(self.rows[n],n,'primary',False,False,zero,audit_absent=True)
        self.put('journal',self.events)
        self.put('current_journal',self.projection('journal',self.events))
        self.put('cleanup_attestation',{'schema':'n26-terminal-cleanup-attestation-v1','plan':self.refs['plan'],
            'controller':self.refs['controller'],'current_journal':self.refs['current_journal'],'resources':self.refs['resources'],
            'expected_processes':self.processes,'collector':self.static_ref,'all_owned_processes_inspected':True})
        self.finish(disposition)
        self.data={'schema':'n26-terminal-metadata-input-v1','root_authorized':True,'executable':True,'source_root':str(self.source_root),
                   'files':self.files,'refs':self.refs,'attempts':self.bindings,'static_objects':[]}
    def put(self,role,value,path=None):
        p=Path(path) if path else self.root/(role+'.json')
        p.parent.mkdir(parents=True,exist_ok=True)
        b=(''.join(json.dumps(x,sort_keys=True)+'\n' for x in value) if p.suffix=='.jsonl' else json.dumps(value,sort_keys=True)).encode()
        p.write_bytes(b);r={'path':str(p),'sha256':digest(b)}
        entry={'role':role,'path':str(p),'present':True,'sha256':r['sha256'],'bytes':len(b)}
        existing=next((i for i,x in enumerate(self.files) if x['path']==str(p)),None)
        if existing is not None:self.files[existing]=entry
        else:self.files.append(entry)
        self.values[str(p)]=value
        if path is None:self.refs[role]=r
        return r
    def absent(self,role,path):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        self.files.append({'role':role,'path':str(p),'present':False,'sha256':None,'bytes':0})
        return {'path':str(p),'sha256':None}
    def projection(self,kind,events):
        path=self.root/(kind+'-private.jsonl')
        path.write_bytes(b'# synthetic stat anchor only\n');st=path.stat()
        return {'schema':'n26-current-terminal-'+('resource' if kind=='resource' else 'journal')+'-projection-v1',
           'cohort_id':COHORT,'all_matching_events':True,'events':events,'event_count':len(events),'collected_at':10000.,
           'source_ledger':{'path':str(path),'sha256':digest(path.read_bytes())},'collector':self.static_ref,
           'source_ledger_stat':{'size':st.st_size,'mtime_ns':st.st_mtime_ns,'inode':st.st_ino}}
    def backend(self):
        return {'kind':'cuda','logical_device':'cuda:0','physical_gpu':7,'physical_uuid':GPU,'actual_uuid':GPU[4:],
          'actual_uuid_type':'torch._C._CUuuid','actual_uuid_bytes_hex':GPU[4:].replace('-',''),'torch_version':'2.7.1+cu126',
          'cuda_version':'12.6','dtype_coverage':list(DTYPES),
          'identity_diagnostic':{'status':'matched','visible_device_count':1,'current_device':0,'cuda_visible_devices':'7'}}
    def proof(self):
        rid='synthetic__n26_tensor_arithmetic_v1';self.proof_pid={'pid':8000,'proc_start_ticks':'80','boot_id':'old-boot'}
        pp={'schema':'n26-tensor-resource-plan-v1','frozen':True,'kind':'n26_tensor_arithmetic_v1','resource_id':rid,
            'source':self.source,'runtime':self.refs['runtime'],'limits':{'resource_processes':1,'episode_attempts':0,'model_calls':0,'api_calls':0,'simulation_steps':0,
            'timeout_seconds':60,'cleanup_seconds':40,'physical_gpu':7,'health_gpu_hours_bucket':'recovery'}}
        pr=self.put('proof_plan',pp);proc=self.put('proof_process',{**self.proof_pid,'resource_id':rid})
        cases=[]
        for d in DTYPES:
            for k in KINDS:
                for l,(stride,offset) in LAYOUTS.items():
                    cases.append({'dtype':d,'case':k,'layout':l,'accepted':True,'candidate_rows':16,
                      'comparison':'native contiguous uint8; zero tolerance','custom_boundary_derivative_verified':True,
                      'clean_object_selection_verified':True,'clean_input_binding_verified':True,'wrong_source_rejected':True,
                      'signed_zero_rejected':True,'production_projection_calls':16,'production_origin_reads':16,
                      'invalid_inputs_rejected':['nonfinite','wrong_horizon'],'zero_gradient':False,'input_stride':stride,
                      'synthetic_storage_offset':offset,'sample_only_negative_controls':[None,'epsilon','v_prediction'],
                      'interior_original_parity':True if k=='strict_interior' else None,
                      'negative_controls_rejected':['input_xyz','projected_xyz','gradient_before','gradient_after','update_operand','model_output_before','model_output_after']})
        report={'schema':'n26-tensor-arithmetic-report-v1','accepted':True,'errors':[],'resource_id':rid,'source':self.source,
          'runtime':self.refs['runtime'],'plan':pr,'process':self.proof_pid,'process_unchanged':True,'model_calls':0,'api_calls':0,
          'simulation_steps':0,'episodes':0,'backend':self.backend(),'cases':cases,'worker_wall_seconds':1.}
        rr=self.put('proof_report',report)
        terminal={'event':'completed','kind':'n26_tensor_arithmetic_v1','resource_id':rid,'plan':pr,'report':rr,'process':proc,
                  'cleanup_complete':True,'cost_measurement_complete':True,'gpu_process_wall_seconds':2.}
        tr=self.put('proof_terminal',terminal)
        self.put('proof',{'schema':'n26-metered-tensor-proof-v1','accepted':True,'source':self.source,'runtime':self.refs['runtime'],
                         'plan':pr,'report':rr,'process':proc,'terminal':tr})
        events=[{'event':event,'kind':'n26_tensor_arithmetic_v1','resource_id':rid,'plan':pr} for event in ('reserved','dispatched')]+[terminal]
        self.put('resources',self.projection('resource',events))
    def metric(self,arm):
        m={'global_step':0,'score_call_count':11,'search_evaluation_count':176,'resample_count':10,'renoise_count':10,'rollout_count':10,
           'qd_archive_active_for_chunk':arm!='C0'}
        if arm in ('C0','Q0'):return m  # Actual provider serializer omits qd_quality_mode.
        m.update(qd_quality_mode='actuator_clipped_provider_v1',qd_descriptor='target_xy_quadrant_signed_height_v1',
                 qd_final_selection_mode='terminal_grasp_proximity_v1',qd_actuator_overhead_seconds=.25,
                 qd_actuator_quality_batches=11,qd_actuator_quality_candidates=176,qd_actuator_clipped_prefix_candidates=0,
                 initial_diversity_descriptor_mode='actuator_clipped_eef_v1',rollout_diversity_descriptor_mode='actuator_clipped_eef_v1',
                 initial_diversity_steps=4,rollout_diversity_steps_applied=15)
        def call(phase,i,j):
            v={'schema':arm.lower()+'-rbf-call-summary-v1','descriptor_mode':'actuator_clipped_eef_v1',
             'source':'core.qd_clean_output_rbf:model_output_sample_v1' if arm=='N26' else 'core.qd_actuator_clipped_rbf:clipped_rbf_gradient:v1',
             'absolute_fallback_used':False,'summary_only_not_exact_replay':True,'input_shape':[16,64,128],
             'input_dtype':'torch.bfloat16','horizon':8,'translation_indices':[39,40,41],'translation_components':384,
             'update_operand_is_measured_output_delta':False,'clipped_components':0,'boundary_components':0,'interior_components':384,
             'nonfinite_count':0,'zero_gradient':False,'phase':phase,'iteration':i,'denoising_step':j,'timestep':100-j,'global_step':0,'stage':1,
             'input_source':'model_output_sample_v1','prediction_type':'sample','input_binding':'same_forward_unmodified_model_output',
             'model_jacobian_used':False,'input_stride':[8576,128,1]}
            for k in ('gradient_before_normalization','gradient_after_normalization','masked_gradient','update_operand'):
                v[k]={'finite':True,'zero':False,'norm':1.,'norm_dtype':'torch.bfloat16'}
            return v
        m['initial_direction_rbf_evidence_by_step']=[call('initial',-1,j) for j in range(4)]
        m['rollout_direction_rbf_evidence_by_iter']=[];m['rollout_rbf_steps_by_iter']=[]
        for i,length in enumerate((3,2,2,2,2,1,1,1,1,1)):
            indices=list(range(2 if length>1 else 1));flags=[j in indices for j in range(length)]
            m['rollout_direction_rbf_evidence_by_iter'].append([call('rollout',i,j) for j in indices])
            m['rollout_rbf_steps_by_iter'].append({'n_trunc_steps':length,'iter_idx':i,'step_indices':indices,'step_flags':flags,
                                                  'step_count':len(indices),'fallback_used':False})
        return m
    def counts(self,arm,zero):
        n=0 if zero else 1;c={'guided_decisions':n,'parent_rounds_verified':0};a={}
        if arm not in ('C0','Q0'):
            if n:c.update(parent_rounds_verified=10,score_batches_verified=11,candidate_scores_verified=176,clipped_prefix_candidates=0,rank_changed_batches=0)
            c.update(all_call_summaries_verified=19*n,witness_calls_verified=11*n,zero_gradient_calls=0,clipped_components=0)
            if n:a={'qd_actuator_overhead_seconds':.25,'qd_actuator_quality_batches':11,'qd_actuator_quality_candidates':176,'qd_actuator_clipped_prefix_candidates':0}
        return c,a
    def attempt(self,row,index,kind,valid,success,zero,retry=None,typed=False,audit_absent=False):
        aid=f'run__{row["episode_key"]}__{kind}';out=self.root/'artifacts/attempts'/aid;rr={}
        n=0 if zero else 1
        compute={k:(None if k in UNKNOWN_HTTP else 0) for k in COMPUTE}
        compute.update(schema='qd-ed-episode-compute-v2',episode_id=0,task_id=row['task_id'],episode_seed=row['env_seed'],
         policy_counters_available=True,provider_counters_available=True,perception_counters_available=True,guided_chunks=n,
         model_forward_calls=1,model_batch_rows=16,model_forward_batch_sizes=[16],outcome='completed',
         provider_http_counters_available=False,provider_logical_counters_available=True,provider_token_usage_complete=not typed,
         rbf_gradient_calls=19*n if row['profile'] in ('N25','N26') else 0,rbf_gradient_batch_rows=304*n if row['profile'] in ('N25','N26') else 0)
        trans={**self.runtime['frozen_stage_provider'],'auth_mode':'chatgpt','application_max_attempts':1,
          'allow_recovered_error_events':True,'recovered_error_policy':'pre_final_only_v1','internal_http_retry_observation_available':False,'internal_retry_policy':'cli_managed_unknown'}
        compute['stage_transport']=trans
        for prefix in ('provider_','stage_codex_'):
            compute.update({prefix+'logical_call_attempts':3,prefix+'completed_turns':2 if typed else 3,
              prefix+'failed_calls':1 if typed else 0,prefix+'usage_complete_calls':2 if typed else 3,
              prefix+'input_tokens':30,prefix+'cached_input_tokens':10,prefix+'output_tokens':5,
              prefix+'reasoning_output_tokens':None,prefix+'call_latency_s':180. if typed else 1.})
        rr['compute']=self.put('compute',[compute],out/'eds_eval/episode_compute.jsonl')
        metrics=[] if zero else [self.metric(row['profile'])]
        rr['metrics']=self.absent('metrics',out/'eds_eval/eds_metrics.jsonl') if zero else self.put('metrics',metrics,out/'eds_eval/eds_metrics.jsonl')
        cmd=['/env/bin/python',str(self.source_root/'main.py'),'job='+aid]
        ctx={'schema':'n23-metered-worker-context-v1','attempt_id':aid,'episode_key':row['episode_key'],'profile':row['profile'],
         'output_dir':str(out),'worktree':str(self.source_root),'main_argv':cmd[1:],'plan':self.refs['plan'],'runtime':self.refs['runtime'],'source':self.source}
        rr['context']=self.put('context',ctx,out/'n23-worker-context.json')
        argv=[cmd[0],str(self.source_root/'scripts/qd_ed_n23_worker.py'),'--context',rr['context']['path'],'--main',cmd[1],'--',*cmd[2:]]
        rr['command']=self.put('command',{'argv':argv,'environment_public':{'CUDA_VISIBLE_DEVICES':'7','CUDA_DEVICE_ORDER':'PCI_BUS_ID','MUJOCO_EGL_DEVICE_ID':'4'}},out/'command.json')
        process={'pid':1000+len(self.attempts),'proc_start_ticks':str(100+len(self.attempts)),'boot_id':'old-boot','attempt_id':aid,'time_unix':float(len(self.events))}
        rr['process']=self.put('process',process,out/'process.json');pid={k:process[k] for k in ('pid','proc_start_ticks','boot_id')}
        self.processes[aid]=pid
        backend=self.backend() if row['profile'] in ('N25','N26') else {'kind':'cpu','logical_device':'cpu','dtype_coverage':[]}
        counts,aux=self.counts(row['profile'],zero)
        audit={'schema':'qd-ed-decision-evidence-audit-v1','accepted':True,'evidence_complete':True,
          'episode_dir':str(out/'eds_eval/decision_evidence/episode_000'),'episode_compute_file':str(out/'eds_eval/episode_compute.jsonl'),
          'observed_counts':{'canonical_candidate_batch':11*n},'n23_arithmetic_backend':backend}
        if row['profile'] not in ('C0','Q0'):
            if n:audit.update(n5_grasp_timing_audit={'checked_decisions':1,'parent_rounds_verified':10,'canonical_batches_verified':11,'canonical_candidates_verified':176},
                 n23_actuator_clipped_quality_audit={k:counts[k] for k in CLIP})
            gate='n26_clean_output_rbf_audit' if row['profile']=='N26' else 'n25_actuator_clipped_rbf_audit'
            audit[gate]={'schema':row['profile'].lower()+'-native-rbf-audit-v1','accepted':True,**counts}
        rr['audit']=self.absent('audit',out/'eds_eval/decision-evidence-audit.json') if audit_absent else self.put('audit',audit,out/'eds_eval/decision-evidence-audit.json')
        evidence=[{'path':'eds_eval/episode_compute.jsonl','sha256':rr['compute']['sha256']},
                  {'path':'eds_eval/decision_evidence/episode_000/status.json','sha256':'a'*64},
                  {'path':'eds_eval/decision_evidence/episode_000/events.jsonl','sha256':'b'*64},
                  {'path':'eds_eval/decision_evidence/episode_000/never-read.pt','sha256':'c'*64}]
        receipt={'schema':'n23-in-worker-audit-receipt-v1','accepted':True,'main_exit_code':0,'process':pid,'process_unchanged':True,
           **{k:ctx[k] for k in ('attempt_id','episode_key','profile','plan','runtime','source')},'context':rr['context'],
           'main_argv_sha256':canonical(cmd[1:]),'evidence':{'files':evidence,'sha256':canonical(evidence)},
           'audit_report':rr['audit'],'worker_cuda':self.backend(),'audit_backend':backend,'audit_seconds':.1,'worker_wall_seconds':1.,
           'n26_metrics':{'path':rr['metrics']['path'],'present':not zero,'sha256':rr['metrics']['sha256']},
           'n26_native_counts':counts,'n26_auxiliary':aux}
        rr['receipt']=self.absent('receipt',out/'eds_eval/in-worker-audit-receipt.json') if audit_absent else self.put('receipt',receipt,out/'eds_eval/in-worker-audit-receipt.json')
        rr['audit_start']=self.put('audit_start',{'schema':'n23-worker-start-v1','process':pid,'context':rr['context']},out/'eds_eval/in-worker-audit-start.json')
        ident={k:row[k] for k in ('split','iteration','profile','task_id','env_seed','policy_seed','init_index')}
        base={'attempt_id':aid,'episode_key':row['episode_key'],'identity':ident,'budget_bucket':'recovery' if retry else row['budget_bucket'],
          'retry_of':retry['attempt_id'] if retry else None,'source_commit':COMMIT,'plan_sha256':self.refs['plan']['sha256'],
          'profile_manifest_sha256':self.plan['profiles_sha256'],'runtime_manifest_sha256':self.plan['runtime_manifest_sha256'],
          'runtime_inventory_sha256':self.plan['runtime_inventory_sha256'],'init_row_sha256':row['init_row_sha256'],'physical_gpu':7,'output_dir':str(out)}
        final={**base,**{k:v for k,v in compute.items() if k in COMPUTE or k.startswith(('provider_','stage_codex_'))},
          'event':'valid','time_unix':float(len(self.events)+2),'outcome_valid':valid,'success':success if valid else None,
          'required_cost_telemetry_complete':valid,'provider_token_usage_complete':not typed,'compute_outcome':'completed',
          'gpu_process_wall_seconds':200. if typed else 2.,'n26_episode_dispatched':True,'process':process,
          'n23_worker_receipt':rr['receipt'],'candidate_evaluations':176*n,'score_batches':11*n}
        if not valid:final['reason']='Codex token usage incomplete' if typed else 'TimeoutExpired'
        rr['terminal']=self.put('terminal',final,out/'attempt-result.json')
        self.bindings.append({'attempt_id':aid,'refs':rr})
        self.events.extend([{**base,'event':'reserved','time_unix':float(len(self.events))},
                            {**base,'event':'dispatched','time_unix':float(len(self.events)+1)},final])
        self.attempts.append({'attempt_id':aid,'episode_key':row['episode_key'],'profile':row['profile'],'terminal':final})
        return final
    def eligibility(self,primary,final,row):
        pb=next(x for x in self.bindings if x['attempt_id']==primary['attempt_id'])
        rb=next(x for x in self.bindings if x['attempt_id']==final['attempt_id'])
        hashes={x['path']:x['sha256'] for x in self.source['files']}
        ef={'metrics':pb['refs']['metrics'],'episode_compute':pb['refs']['compute'],'stage_events':{'path':str(Path(primary['output_dir'])/'eds_eval/stage_events.jsonl'),'sha256':'8'*64}}
        diagnostic={'schema':'n23-v2-timeout-diagnostic-v1','attempt_id':primary['attempt_id'],'source_commit':COMMIT,
          'plan_sha256':self.refs['plan']['sha256'],'eligible_infrastructure_only':True,'outcome_valid':False,
          'derivative_gate_failures':['Codex token usage incomplete','Codex Stage call failure invalidates the frozen transport condition',
             'Codex Stage event lacks one measured call with complete usage'],'unknown_token_calls':1,
          'token_usage':{'input_tokens':None,'cached_input_tokens':None,'output_tokens':None},'evidence_files':ef,
          'diagnostic_reader':{'path':str(self.source_root/'scripts/qd_ed_n23_v2_recovery.py'),'sha256':hashes['scripts/qd_ed_n23_v2_recovery.py']}}
        record={'schema':'n26-typed-timeout-eligibility-v1','cohort_id':COHORT,'primary_attempt_id':primary['attempt_id'],
          'episode_key':row['episode_key'],'scientific_row':row,'source_commit':COMMIT,'plan':self.refs['plan'],
          'primary_outcome_valid':False,'unknown_token_calls':1,'retry_budget_bucket':'recovery','same_cell_max_recoveries':1,
          'diagnostic':diagnostic,'evidence_files':ef,'evidence_packaging_reader':{'path':str(self.source_root/'scripts/qd_ed_n26_recovery.py'),
          'sha256':hashes['scripts/qd_ed_n26_recovery.py']}}
        observability={'path':str(self.root/'timeout-observability.json'),'sha256':'fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'}
        diagnostic.update(timeout_observability=observability,guided_chunks=primary['guided_chunks'],candidate_evaluations=176*primary['guided_chunks'],
          score_batches=11*primary['guided_chunks'],original_required_cost_telemetry_complete=False,all_attempt_token_usage_complete=False,
          observed_token_totals={k:primary['provider_'+k] for k in ('input_tokens','cached_input_tokens','output_tokens')})
        record.update(terminal=pb['refs']['terminal'],native_receipt=pb['refs']['receipt'],native_report=pb['refs']['audit'],process=pb['refs']['process'],
          timeout_observability=observability,protocol={'path':str(self.root/'protocol.json'),'sha256':'7c64679c35ffc3c9a53d8309ceea7668de872f03fc5e2d2ed16bae2c43058b55'},
          evidence_packaging_mode='n26_absent_zero_guided_private_reader' if pb['refs']['metrics']['sha256'] is None else 'unchanged_original_reader')
        er=self.put('eligibility',record,self.root/('eligibility-'+primary['attempt_id']+'.json'));rb['eligibility']=er
        rb['recovery_attestation']=self.put('recovery_attestation',{'schema':'n26-original-typed-eligibility-attestation-v1',
          'eligibility':er,'source':self.refs['source'],'plan':self.refs['plan'],'primary_attempt_id':primary['attempt_id'],
          'method':'original_frozen_controller_and_classifier_metadata','classification_basis_sha256':canonical(record),
          'root_verified_original_basis':True,'stage_and_tensors_reaudited_by_terminal_reader':False,'collector':self.static_ref},self.root/('recovery-attestation-'+primary['attempt_id']+'.json'))
        for e in self.events:
            if e['attempt_id']==final['attempt_id']:e['n26_recovery_eligibility']=er
        final['n26_recovery_eligibility']=er;rb['refs']['terminal']=self.put('terminal',final,rb['refs']['terminal']['path'])
    def accept(self,final,row,zero):
        binding=self.bindings[-1]['refs']
        self.cells.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],
          'attempt_id':final['attempt_id'],'success':final['success'],'audit':binding['audit'],'worker_context':binding['context'],
          'worker_receipt':binding['receipt'],'attempt_result':binding['terminal']})
        c,a=self.counts(row['profile'],zero)
        for k,v in c.items():self.native[row['profile']][k]=self.native[row['profile']].get(k,0)+v
        for k,v in a.items():self.aux[row['profile']][k]=self.aux[row['profile']].get(k,0)+v
    def expected_summary(self):
        result={'accepted_cell_denominators':{},'primary_attempt_denominators':{},'all_attempt_denominators':{},'all_attempt_costs':{},'matched_comparisons':{}}
        for arm in ARMS:
            cells=[x for x in self.cells if x['profile']==arm];attempts=[x for x in self.attempts if x['profile']==arm]
            result['accepted_cell_denominators'][arm]=len(cells)
            result['primary_attempt_denominators'][arm]=len([x for x in attempts if x['terminal']['retry_of'] is None])
            result['all_attempt_denominators'][arm]=len(attempts)
            result['all_attempt_costs'][arm]={k:{'observed_total':sum(x['terminal'][k] for x in attempts if type(x['terminal'].get(k)) in (int,float)),
               'observed_attempts':sum(type(x['terminal'].get(k)) in (int,float) for x in attempts),
               'missing_attempts':[x['attempt_id'] for x in attempts if type(x['terminal'].get(k)) not in (int,float)]} for k in COST}
        candidate={x['task_id']:x['success'] for x in self.cells if x['profile']=='N26'}
        for arm in ARMS[:-1]:
            baseline={x['task_id']:x['success'] for x in self.cells if x['profile']==arm};same=candidate.keys()&baseline.keys()
            result['matched_comparisons'][arm]={'denominator':len(same),'gains':sum(candidate[k] and not baseline[k] for k in same),'losses':sum(baseline[k] and not candidate[k] for k in same)}
        known=[x for x in self.attempts if type(x['terminal'].get('provider_logical_call_attempts')) is int
               and type(x['terminal'].get('provider_usage_complete_calls')) is int]
        missing=[x['attempt_id'] for x in self.attempts if x not in known]
        unknown=sum(x['terminal']['provider_logical_call_attempts']-x['terminal']['provider_usage_complete_calls'] for x in known)
        result.update(known_unknown_token_calls=unknown,unknown_token_calls=None if missing else unknown,unmeasured_token_call_attempts=missing,
                      all_attempt_token_usage_complete=bool(self.attempts) and not missing and unknown==0
                        and all(x['terminal'].get('provider_token_usage_complete') is True for x in self.attempts),
                      token_cost_interpretation='observed token totals are partial lower bounds when usage is unknown')
        return result
    def finish(self,disposition=None):
        n=len(self.cells);counts={a:{'audited':sum(x['profile']==a for x in self.cells),
           'success':sum(x['profile']==a and x['success'] for x in self.cells)} for a in ARMS}
        win=counts['N26']['success'];active=self.native['N26'].get('parent_rounds_verified',0)>0
        promote=n==40 and win>=5 and win>=max(counts[a]['success'] for a in ARMS[:-1]) and active
        decision=disposition or ('ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promote else 'REJECT' if n==40 else
                'REJECT_NUMERIC_FUTILITY' if n%4==0 and win+10-n//4<5 and not self.invalid else 'INVALID_OR_INTERRUPTED')
        phase='completed_all_forty_audited' if n==40 else 'rejected_numeric_futility' if decision=='REJECT_NUMERIC_FUTILITY' else 'failed'
        costs=self.expected_summary();keys=[x['episode_key'] for x in self.cells]
        outcomes=[{k:x[k] for k in ('episode_key','task_id','profile','success','attempt_id')}|{'recovered':bool(next(a['terminal']['retry_of'] for a in self.attempts if a['attempt_id']==x['attempt_id']))} for x in self.cells]
        status={'schema':'n26-dev-supervisor-status-v1','status':phase,'cohort_id':COHORT,'source_commit':COMMIT,
           'plan':self.refs['plan'],'completed_keys':keys,'attempts':self.attempts,'outcomes':outcomes,
           'successes':{a:counts[a]['success'] for a in ARMS},'native':self.native,'auxiliary':self.aux,
           'dev_gate_promoted':promote,'protected_authorized':False,**costs}
        self.put('status',status)
        result={'schema':'n26-dev-cohort-result-v1','cohort_id':COHORT,'source_commit':COMMIT,'planned':40,
          'dispatched':len(self.attempts),'audited_cells':n,'counts':counts,'accepted_cells':self.cells,'attempts':self.attempts,
          'native':self.native,'auxiliary':self.aux,'dev_gate_promoted':promote,'decision':decision,
          'failure':{'episode_key':self.rows[n]['episode_key'],'reason':'invalid original outcome','failure_class':'GateError'} if self.invalid else None,
          'goal_status':'TARGET_NOT_MET','validation_authorized':False,'formal_authorized':False,**costs,
          'controller_evidence':{'completed_keys':keys,'journal_accepted_keys':keys,'consistent':True,'status_phase':phase},
          'plan':self.refs['plan'],'terminal_status':{**self.refs['status'],'content':status},'ledger_snapshot':self.refs['journal'],
          'reader':{'path':str(self.source_root/'scripts/qd_ed_n26_report.py'),'sha256':next(x['sha256'] for x in self.source['files'] if x['path']=='scripts/qd_ed_n26_report.py')},
          'source_bridge':self.refs['source_bridge']}
        self.put('result',result)

