"""Fabricated JSON only; expected totals constructed independently of the reviewer."""
import copy
from pathlib import Path
from bounded_json_v1 import canonical
import terminal_reader_v1 as t
from metadata_checks_v1 import KINDS,LAYOUTS,DTYPES

class MemoryReader:
    """Pure checker fixtures represent decoded, already hash-verified JSON."""
    def __init__(self):self.values={};self.refs={}
    def put(self,role,path,obj):
        ref={'path':str(path),'sha256':canonical(obj) if obj is not None else None}
        self.values[(role,str(path))]=obj;self.refs[(role,str(path))]=ref;return ref
    def get(self,ref,role):return self.values[(role,ref['path'])]
    def require_consumed(self):pass

def cuda():return {'kind':'cuda','physical_gpu':7,'logical_device':'cuda:0','physical_uuid':t.GPU,'actual_uuid':t.GPU[4:],
 'actual_uuid_type':'torch._C._CUuuid','actual_uuid_bytes_hex':t.GPU[4:].replace('-',''),'torch_version':'synthetic','cuda_version':'synthetic',
 'dtype_coverage':list(DTYPES),'identity_diagnostic':{'status':'matched','visible_device_count':1,'current_device':0,'cuda_visible_devices':'7'}}
def proc(i):return {'pid':i,'proc_start_ticks':str(i*10),'boot_id':'synthetic-boot'}
def bare(path):return {'path':str(path),'sha256':'a'*64}

def fixture(*,size=16,wins=2,n26_wins=1,zero_guided=False,invalid=False,aborted=False,mismatch=False,missing_process=False):
    rd=MemoryReader();home=Path('/synthetic');out=home/'attempts';root=home/'W';refs={}
    put=lambda role,obj:rd.put(role,home/(role+'.json'),obj)
    critical=['scripts/qd_ed_n27_report.py','scripts/qd_ed_n27_supervise.py','scripts/qd_ed_n27_recovery.py','scripts/qd_ed_n23_v2_recovery.py']
    files=[{'path':n,'sha256':'1'*64} for n in sorted(critical+[f'fixture/{i:03}.py' for i in range(341)])]
    source={'commit':t.COMMIT,'files':files,'sha256':canonical(files)};refs['source']=put('source',source)
    runtime=bare(home/'runtime.json');rows=[]
    for task in range(4):
        for arm in t.ARMS:rows.append({'episode_key':f't{task}_{arm}','task_id':task,'profile':arm,'split':'dev','iteration':t.COHORT,'env_seed':10+task,
         'policy_seed':20+task,'init_index':task,'init_row_sha256':'b'*64,'timeout_seconds':1800,'budget_bucket':'baseline' if arm=='C0' else 'development'})
    # Proof contents are a fabricated 36-case strict PASS, no torch operations.
    pp={'schema':'n27-tensor-resource-plan-v1','frozen':True,'kind':'n27_tensor_arithmetic_v1','resource_id':'synthetic-proof','source':source,'runtime':runtime,
     'limits':{'resource_processes':1,'episode_attempts':0,'model_calls':0,'api_calls':0,'simulation_steps':0,'timeout_seconds':120,'cleanup_seconds':40,'physical_gpu':7,'health_gpu_hours_bucket':'recovery'}}
    refs['proof_plan']=put('proof_plan',pp);pr=proc(90)|{'resource_id':pp['resource_id']};refs['proof_process']=put('proof_process',pr)
    cases=[]
    for dtype in DTYPES:
      for kind in KINDS:
       for layout,(stride,offset) in LAYOUTS.items():
        q={'dtype':dtype,'case':kind,'layout':layout,'accepted':True,'candidate_rows':16,'comparison':'native contiguous uint8; zero tolerance',
         'production_projection_calls':16,'production_origin_reads':16,'invalid_inputs_rejected':['nonfinite','wrong_horizon'],'zero_gradient':False,
         'input_stride':stride,'synthetic_storage_offset':offset,'sample_only_negative_controls':[None,'epsilon','v_prediction'],
         'interior_original_parity':True if kind=='strict_interior' else None,'rng_scope':'cpu_and_assigned_cuda',
         'negative_controls_rejected':['input_xyz','projected_xyz','gradient_before','gradient_after','update_operand','model_output_before','model_output_after']}
        q.update({k:True for k in ('custom_boundary_derivative_verified','clean_object_selection_verified','clean_input_binding_verified','wrong_source_rejected','signed_zero_rejected','feasible_ray_verified','tail_mask_rng_verified')});cases.append(q)
    proofreport={'schema':'n27-tensor-arithmetic-report-v1','accepted':True,'errors':[],'source':source,'runtime':runtime,'plan':refs['proof_plan'],
     'process':proc(90),'process_unchanged':True,'model_calls':0,'api_calls':0,'simulation_steps':0,'episodes':0,'resource_id':pp['resource_id'],
     'backend':cuda(),'cases':cases,'worker_wall_seconds':10.}
    refs['proof_report']=put('proof_report',proofreport)
    resources=[{'event':e,'kind':pp['kind'],'resource_id':pp['resource_id'],'plan':refs['proof_plan']} for e in ('reserved','dispatched','completed')]
    resources[-1].update(cleanup_complete=True,cost_measurement_complete=True,report=refs['proof_report'],process=refs['proof_process'],gpu_process_wall_seconds=11.)
    refs['proof_terminal']=put('proof_terminal',resources[-1]);refs['proof']=put('proof',{'schema':'n27-metered-tensor-proof-v1','accepted':True,'source':source,'runtime':runtime,**{k:refs['proof_'+k] for k in ('plan','report','process','terminal')}})
    bridge={'schema':'n27-source-equivalence-bridge-v1','new_source':source,'runtime':runtime,'gpu_release':False,'changed_existing':['core/rdt_policy_steer.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'],'unchanged_original_files':312,'original_source':{'commit':'6026794cd5d52f3a5054bf2704ebb3c516f9f47e','files':files[:315],'sha256':canonical(files[:315])},'predecessor_refs':{k:bare(home/('old-'+k+'.json')) for k in ('review','result','source','plan','budget')}};refs['bridge']=put('bridge',bridge)
    sr={'schema':'n27-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,'backend_proof':refs['proof'],'source_bridge':refs['bridge'],'no_gpu_release':True,'protocol':bare(home/'protocol.json'),'predecessor':bridge['predecessor_refs']['review'],'budget_reuse':bare(home/'budget-reuse.json')};refs['source_review']=put('source_review',sr)
    authority={**{k:sr[k] for k in ('protocol','predecessor','budget_reuse')},'cohort_id':t.COHORT,'schema':'n27-screen-authority-v1','source':source,'runtime':runtime,'final_review':refs['source_review'],'limits':t.DEV_LIMITS,'local_gpu_hours':9.25,'validation_authorized':False,'formal_authorized':False};refs['authority']=put('authority',authority)
    plan={'source_commit':t.COMMIT,'code_files':files,'frozen':True,'phase_authorization':{'dev':True,'validation':False,'formal':False},'worktree':str(root),'artifact_root':str(home),
     'runtime_manifest_path':runtime['path'],'runtime_manifest_sha256':runtime['sha256'],'runtime_inventory_sha256':'c'*64,'profiles_sha256':'d'*64,'episodes':rows,
     'n27_cohort':{**{k:sr[k] for k in ('protocol','predecessor','budget_reuse')},'cohort_id':t.COHORT,'limits':t.DEV_LIMITS,'worker_audit':t.WORKER,'early_stop':'none_full_sixteen_required','final_review':refs['source_review'],'authority':refs['authority']}}
    refs['plan']=put('plan',plan)
    release={'schema':'n27-dev-execution-release-v1','plan':refs['plan'],'source_commit':t.COMMIT,'cohort_id':t.COHORT,'episode_keys':[x['episode_key'] for x in rows],
     'authority':refs['authority'],'physical_gpu':7,'limits':t.DEV_LIMITS,'validation_authorized':False,'formal_authorized':False};refs['release']=put('release',release)
    commands=[{'episode_key':r['episode_key'],'argv':['python',str(root/'main.py'),'output='+str(out/t.SENTINEL)]} for r in rows]
    pre={'schema':'n27-terminal-prerequisite-attestation-v1','bindings':{k:refs[k] for k in ('plan','source','proof','bridge','source_review','authority','release')},'runtime':runtime,
     'source_commit':t.COMMIT,'source_files_verified':345,'operations':['validate_plan','build_command'],'all_prerequisites_passed':True,'historical_proof_lineage_verified':True,
     'model_api_sim_calls':0,'collector':bare(home/'collector.py'),'command_templates':commands};refs['precheck']=put('precheck',pre)
    controller={'schema':'n27-root-controller-process-v1','source_commit':t.COMMIT,'plan':refs['plan'],'release':refs['release'],'physical_gpu':7,'one_launch':True,
     'wrapper':bare(home/'wrapper.py'),'entrypoint':{'path':str(root/'scripts/qd_ed_n27_supervise.py'),'sha256':'1'*64},'process':proc(99)};refs['controller']=put('controller',controller)
    bindings=[];events=[];accepted=[];attempts=[];native={a:{} for a in t.ARMS};aux={a:{} for a in t.ARMS};processes={'controller':proc(99),'proof':proc(90)}
    for i,row in enumerate(rows[:size]):
        aid=f'a{i:02}';arm=row['profile'];task=row['task_id'];path=out/aid;n=0 if zero_guided else 1
        rr={};process=proc(100+i)|{'attempt_id':aid};rr['process']=rd.put('process',path/t.NAMES['process'],None if missing_process and i==size-1 else process)
        argv=[x.replace(t.SENTINEL,aid) for x in commands[i]['argv']][1:]
        ctx={'schema':'n23-metered-worker-context-v1','attempt_id':aid,'episode_key':row['episode_key'],'profile':arm,'output_dir':str(path),'worktree':str(root),'main_argv':argv,'plan':refs['plan'],'runtime':runtime,'source':source};rr['context']=rd.put('context',path/t.NAMES['context'],ctx)
        backend=cuda() if arm in ('N26','N27') else {'kind':'cpu','logical_device':'cpu'}
        audit={'schema':'qd-ed-decision-evidence-audit-v1','accepted':True,'evidence_complete':True,'episode_dir':str(path/'eds_eval/decision_evidence/episode_000'),
         'episode_compute_file':str(path/'eds_eval/episode_compute.jsonl'),'observed_counts':{'canonical_candidate_batch':11*n},'n23_arithmetic_backend':backend}
        nc={'guided_decisions':n,'parent_rounds_verified':0};ac={}
        if arm in ('N26','N27'):
            if n:
                audit['n5_grasp_timing_audit']={'checked_decisions':n,'parent_rounds_verified':10*n,'canonical_batches_verified':11*n,'canonical_candidates_verified':176*n}
                clip=dict(zip(t.CLIP,(11*n,176*n,0,0)));audit['n23_actuator_clipped_quality_audit']=clip;nc.update(clip);nc['parent_rounds_verified']=10*n
                ac=dict(zip(t.AUX,(0.,11*n,176*n,0)))
            gate={'schema':f'{arm.lower()}-native-rbf-audit-v1','accepted':True,'guided_decisions':n,'all_call_summaries_verified':19*n,'witness_calls_verified':11 if n else 0,'zero_gradient_calls':0,'clipped_components':0}
            if arm=='N27':gate.update(limited_rows=0,realized_nonzero_delta_components=0)
            audit['n27_feasible_ray_rbf_audit' if arm=='N27' else 'n26_clean_output_rbf_audit']=gate
            nc.update({k:v for k,v in gate.items() if k not in ('schema','accepted','guided_decisions')})
        rr['audit']=rd.put('audit',path/t.NAMES['audit'],audit)
        evid=[{'path':s,'sha256':'e'*64} for s in ('eds_eval/episode_compute.jsonl','eds_eval/decision_evidence/episode_000/status.json','eds_eval/decision_evidence/episode_000/events.jsonl')]
        receipt={'schema':'n23-in-worker-audit-receipt-v1',**{k:ctx[k] for k in ('attempt_id','episode_key','profile','plan','runtime','source')},'process':proc(100+i),
         'accepted':True,'main_exit_code':0,'process_unchanged':True,'context':rr['context'],'main_argv_sha256':canonical(argv),'evidence':{'files':evid,'sha256':canonical(evid)},
         'audit_report':rr['audit'],'worker_cuda':cuda(),'audit_backend':backend,'audit_seconds':1.,'worker_wall_seconds':9.,'n27_native_counts':nc,'n27_auxiliary':ac,
         'n27_metrics':{'path':str(path/'eds_eval/eds_metrics.jsonl'),'present':bool(n),'sha256':'f'*64 if n else None}}
        rr['receipt']=rd.put('receipt',path/t.NAMES['receipt'],receipt)
        base={'attempt_id':aid,'episode_key':row['episode_key'],'identity':t.identity(row),'output_dir':str(path),'source_commit':t.COMMIT,'plan_sha256':refs['plan']['sha256'],
         'profile_manifest_sha256':plan['profiles_sha256'],'runtime_manifest_sha256':runtime['sha256'],'runtime_inventory_sha256':plan['runtime_inventory_sha256'],'init_row_sha256':row['init_row_sha256'],'physical_gpu':7,'budget_bucket':row['budget_bucket']}
        last_invalid=invalid and i==size-1;sent=not(aborted and i==size-1)
        final={**base,'event':'valid' if sent else 'aborted','time_unix':i*20+10,'process':process,'n23_worker_receipt':rr['receipt'],
         'outcome_valid':not last_invalid and sent,'required_cost_telemetry_complete':not last_invalid and sent,'provider_token_usage_complete':not last_invalid and sent,
         'success':task<(wins if arm=='N27' else n26_wins if arm=='N26' else 0),'compute_outcome':'completed','n27_episode_dispatched':sent,
         **{k:0 for k in t.COST},'gpu_process_wall_seconds':10. if sent else 0.,'guided_chunks':n,'unguided_chunks':90-n,'candidate_evaluations':176*n,'score_batches':11*n,
         'rbf_gradient_calls':19*n if arm in ('N26','N27') else 0,'rbf_gradient_batch_rows':304*n if arm in ('N26','N27') else 0,
         'provider_logical_call_attempts':2,'stage_codex_logical_call_attempts':2,'provider_usage_complete_calls':1 if last_invalid else 2,
         'provider_failed_calls':1 if last_invalid else 0,'provider_input_tokens':100,'provider_cached_input_tokens':20,'provider_output_tokens':10}
        if not sent:
            for k in ('provider_logical_call_attempts','provider_usage_complete_calls','stage_codex_logical_call_attempts','provider_input_tokens','provider_cached_input_tokens','provider_output_tokens'):final.pop(k,None)
        rr['terminal']=rd.put('terminal',path/t.NAMES['terminal'],final)
        group=[base|{'event':'reserved','time_unix':i*20}]
        if sent:group.append(base|{'event':'dispatched','time_unix':i*20+1})
        group.append(final);events.extend(group);bindings.append({'attempt_id':aid,'refs':rr});attempts.append({'attempt_id':aid,'episode_key':row['episode_key'],'profile':arm,'terminal':final})
        processes[aid]=None if missing_process and i==size-1 else proc(100+i)
        if final['outcome_valid']:
            accepted.append({'episode_key':row['episode_key'],'task_id':task,'profile':arm,'attempt_id':aid,'success':final['success'],'audit':rr['audit'],'worker_context':rr['context'],'worker_receipt':rr['receipt'],'attempt_result':rr['terminal']})
            for k,v in nc.items():native[arm][k]=native[arm].get(k,0)+v
            for k,v in ac.items():aux[arm][k]=aux[arm].get(k,0)+v
    for role,es in [('journal',events),('resources',resources)]:
        val={'schema':f"n27-current-terminal-{'journal' if role=='journal' else 'resource'}-projection-v1",'cohort_id':t.COHORT,'all_matching_events':True,'events':es,'event_count':len(es),'source_ledger':bare(home/(role+'.jsonl')),'collector':bare(home/'collector.py'),'collected_at':1000.}
        if role=='journal':val.update(snapshot=bare(home/'terminal-ledger-v1.json'),snapshot_events_sha256=canonical(es))
        refs[role]=put(role,val)
    # Independent expected aggregation, without calls to reader.summary/reconstruct.
    costs={a:{} for a in t.ARMS}
    for arm in t.ARMS:
      selected=[x for x in attempts if x['profile']==arm]
      for k in t.COST:
        measured=[x['terminal'][k] for x in selected if k in x['terminal']]
        costs[arm][k]={'observed_total':sum(measured),'observed_attempts':len(measured),'missing_attempts':[x['attempt_id'] for x in selected if k not in x['terminal']]}
    count={a:{'audited':len([x for x in accepted if x['profile']==a]),'success':len([x for x in accepted if x['profile']==a and x['success']])} for a in t.ARMS}
    pairs={}
    for arm in t.ARMS[:-1]:
        pairs[arm]={'denominator':0,'gains':0,'losses':0}
        for task in range(4):
            x=[x for x in accepted if x['profile']==arm and x['task_id']==task];y=[x for x in accepted if x['profile']=='N27' and x['task_id']==task]
            if x and y:
                pairs[arm]['denominator']+=1;pairs[arm]['gains']+=int(y[0]['success'] and not x[0]['success']);pairs[arm]['losses']+=int(x[0]['success'] and not y[0]['success'])
    unknown_ids=[x['attempt_id'] for x in attempts if 'provider_usage_complete_calls' not in x['terminal']];known=sum(x['terminal'].get('provider_logical_call_attempts',0)-x['terminal'].get('provider_usage_complete_calls',0) for x in attempts)
    sums={'accepted_cell_denominators':{a:count[a]['audited'] for a in t.ARMS},'matched_comparisons':pairs,
     'primary_attempt_denominators':{a:sum(x['profile']==a for x in attempts) for a in t.ARMS},'all_attempt_denominators':{a:sum(x['profile']==a for x in attempts) for a in t.ARMS},
     'all_attempt_costs':costs,'known_unknown_token_calls':known,'unknown_token_calls':None if unknown_ids else known,'unmeasured_token_call_attempts':unknown_ids,
     'all_attempt_token_usage_complete':bool(attempts) and known==0 and not unknown_ids and all(x['terminal']['provider_token_usage_complete'] for x in attempts),
     'token_cost_interpretation':'observed token totals are partial lower bounds when usage is unknown'}
    full=len(accepted)==16;promoted=full and not zero_guided and wins>=2 and wins>n26_wins;raw='ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV' if promoted else 'REJECT_SCREEN' if full else 'INVALID_OR_INTERRUPTED'
    prefix=[x['episode_key'] for x in accepted];phase='completed_all_sixteen_audited' if full else 'failed';consistent=not mismatch
    status={'schema':'n27-dev-supervisor-status-v1','status':phase,'cohort_id':t.COHORT,'source_commit':t.COMMIT,'plan':refs['plan'],'completed_keys':prefix[:-1] if mismatch else prefix,
     'attempts':attempts,'outcomes':[{k:x[k] for k in ('episode_key','task_id','profile','success','attempt_id')}|{'recovered':False} for x in accepted],
     'successes':{a:count[a]['success'] for a in t.ARMS},'native':native,'auxiliary':aux,'dev_gate_promoted':promoted,'protected_authorized':False,**sums};refs['status']=put('status',status)
    result={'schema':'n27-dev-cohort-result-v1','cohort_id':t.COHORT,'source_commit':t.COMMIT,'planned':16,'dispatched':size-int(aborted),'audited_cells':len(accepted),'counts':count,'accepted_cells':accepted,
     'attempts':attempts,'native':native,'auxiliary':aux,'dev_gate_promoted':promoted if consistent else False,'decision':raw if consistent else 'INVALID_OR_INTERRUPTED','goal_status':'TARGET_NOT_MET','validation_authorized':False,'formal_authorized':False,**sums,
     'failure':{'episode_key':rows[size-1]['episode_key'],'reason':'synthetic invalid','failure_class':'GateError'} if invalid or aborted else None,
     'controller_evidence':{'completed_keys':status['completed_keys'],'journal_accepted_keys':prefix,'consistent':consistent,'status_phase':phase},'plan':refs['plan'],'source_bridge':refs['bridge'],
     'ledger_snapshot':rd.get(refs['journal'],'journal')['snapshot'],'reader':{'path':str(root/'scripts/qd_ed_n27_report.py'),'sha256':'1'*64},'terminal_status':{**refs['status'],'content':status}}
    if mismatch:result['journal_reconstructed_disposition']=raw;result['controller_evidence']['disagreement']='Controller status and independently reconstructed journal differ; no resume or promotion.'
    refs['result']=put('result',result)
    cleanup={'schema':'n27-root-cleanup-attestation-v1','plan':refs['plan'],'source':refs['source'],'controller':refs['controller'],'journal':refs['journal'],'resources':refs['resources'],
     'process_identities':processes,'collector':bare(home/'cleanup.py'),'collected_at':1001.,'locks_held':True,'current_matching_subsets_equal':True,
     'checks':{k:{'identity':v,'same_identity_alive':False if v else None,'group_alive':False if v else None} for k,v in processes.items()}};refs['cleanup']=put('cleanup',cleanup)
    return {'schema':'n27-terminal-metadata-input-v1','root_authorized':True,'executable':True,'refs':refs,'attempts':bindings},rd

def recovery_fixture(*,failed=False,missing_attestation=False):
    """One primary timeout + one valid/failed recovery, no later rows."""
    from metadata_checks_v1 import DERIVATIVE
    data,rd=fixture(size=1);refs=data['refs'];plan=rd.get(refs['plan'],'plan');row=plan['episodes'][0];old=data['attempts'][0];rr=old['refs']
    primary=rd.get(rr['terminal'],'terminal');original=copy.deepcopy(primary)
    primary.update(outcome_valid=False,required_cost_telemetry_complete=False,provider_token_usage_complete=False,provider_usage_complete_calls=1,
     provider_failed_calls=1,stage_codex_failed_calls=1,provider_completed_turns=1,reason='Codex token usage incomplete')
    new_id='retry00';newrefs={};out=Path(plan['artifact_root'])/'attempts'/new_id
    def replace(v):
        if isinstance(v,str):return v.replace('a00',new_id)
        if isinstance(v,list):return [replace(x) for x in v]
        if isinstance(v,dict):return {k:replace(x) for k,x in v.items()}
        return v
    process=proc(300)|{'attempt_id':new_id};newrefs['process']=rd.put('process',out/t.NAMES['process'],process)
    ctx=replace(copy.deepcopy(rd.get(rr['context'],'context')));newrefs['context']=rd.put('context',out/t.NAMES['context'],ctx)
    audit=replace(copy.deepcopy(rd.get(rr['audit'],'audit')));newrefs['audit']=rd.put('audit',out/t.NAMES['audit'],audit)
    receipt=replace(copy.deepcopy(rd.get(rr['receipt'],'receipt')));receipt.update(context=newrefs['context'],audit_report=newrefs['audit'],process=proc(300),main_argv_sha256=canonical(ctx['main_argv']))
    newrefs['receipt']=rd.put('receipt',out/t.NAMES['receipt'],receipt)
    eligibility_ref=bare(Path('/synthetic/eligibility.json'))
    final=replace(original);final.update(retry_of=primary['attempt_id'],budget_bucket='recovery',n27_recovery_eligibility=eligibility_ref,time_unix=19,
     n23_worker_receipt=newrefs['receipt'],process=process)
    if failed:final.update(outcome_valid=False,required_cost_telemetry_complete=False,provider_token_usage_complete=False,provider_usage_complete_calls=1,provider_failed_calls=1,reason='failed recovery')
    newrefs['terminal']=rd.put('terminal',out/t.NAMES['terminal'],final)
    observability={'path':'/synthetic/timeout-observability.json','sha256':'fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'}
    diagnostic={'schema':'n23-v2-timeout-diagnostic-v1','attempt_id':'a00','source_commit':t.COMMIT,'plan_sha256':refs['plan']['sha256'],
     'eligible_infrastructure_only':True,'outcome_valid':False,'derivative_gate_failures':sorted(DERIVATIVE),'unknown_token_calls':1,
     'token_usage':{'input_tokens':None,'cached_input_tokens':None,'output_tokens':None},'evidence_files':[],
     'timeout_observability':observability,'guided_chunks':1,'candidate_evaluations':176,'score_batches':11,
     'original_required_cost_telemetry_complete':False,'all_attempt_token_usage_complete':False,
     'observed_token_totals':{'input_tokens':100,'cached_input_tokens':20,'output_tokens':10},
     'diagnostic_reader':{'path':plan['worktree']+'/scripts/qd_ed_n23_v2_recovery.py','sha256':'1'*64}}
    record={'schema':'n27-typed-timeout-eligibility-v1','cohort_id':t.COHORT,'primary_attempt_id':'a00','episode_key':row['episode_key'],'scientific_row':row,
     'source_commit':t.COMMIT,'plan':refs['plan'],'primary_outcome_valid':False,'unknown_token_calls':1,'retry_budget_bucket':'recovery','same_cell_max_recoveries':1,
     'terminal':rr['terminal'],'native_receipt':rr['receipt'],'native_report':rr['audit'],'process':rr['process'],'diagnostic':diagnostic,'evidence_files':[],
     'timeout_observability':observability,'protocol':{'path':'/synthetic/protocol.json','sha256':'165d4efd83a7bf86a5bc1c42c0bea31272b69a86501ee22598bd2a1c6c9fa280'},
     'evidence_packaging_mode':'unchanged_original_reader','evidence_packaging_reader':{'path':plan['worktree']+'/scripts/qd_ed_n27_recovery.py','sha256':'1'*64}}
    eligibility_ref=rd.put('eligibility','/synthetic/eligibility.json',record);final['n27_recovery_eligibility']=eligibility_ref
    attest={'schema':'n27-original-typed-eligibility-attestation-v1','eligibility':eligibility_ref,'source':refs['source'],'plan':refs['plan'],'primary_attempt_id':'a00',
     'method':'original_frozen_controller_and_classifier_metadata','classification_basis_sha256':canonical(record),'root_verified_original_basis':True,
     'stage_and_tensors_reaudited_by_terminal_reader':False,'collector':bare('/synthetic/classifier-reader.py')}
    attref=rd.put('recovery_attestation','/synthetic/recovery-attestation.json',None if missing_attestation else attest)
    new={'attempt_id':new_id,'refs':newrefs,'eligibility':eligibility_ref,'recovery_attestation':attref};data['attempts'].append(new)
    journal=rd.get(refs['journal'],'journal');base={k:v for k,v in final.items() if k not in t.COST and k not in {'event','time_unix'}}
    journal['events']+= [base|{'event':'reserved','time_unix':11},base|{'event':'dispatched','time_unix':12},final]
    journal['event_count']=6;journal['snapshot_events_sha256']=canonical(journal['events'])
    cleanup=rd.get(refs['cleanup'],'cleanup');cleanup['process_identities'][new_id]=proc(300);cleanup['checks'][new_id]={'identity':proc(300),'same_identity_alive':False,'group_alive':False}
    status=rd.get(refs['status'],'status');result=rd.get(refs['result'],'result')
    item={'attempt_id':new_id,'episode_key':row['episode_key'],'profile':'C0','terminal':final}
    status['attempts'].append(item)  # Fixture status/result share original attempts list by construction.
    if failed:
        result['accepted_cells']=[];result['audited_cells']=0;result['counts']['C0']={'audited':0,'success':0};result['native']['C0']={};result['auxiliary']['C0']={}
        result['failure']={'episode_key':row['episode_key'],'reason':'failed recovery','failure_class':'GateError'};status['completed_keys']=[];status['outcomes']=[]
        status['native']['C0']={};status['successes']['C0']=0;result['controller_evidence']['completed_keys']=[];result['controller_evidence']['journal_accepted_keys']=[]
    else:
        cell=result['accepted_cells'][0];cell.update(attempt_id=new_id,audit=newrefs['audit'],worker_context=newrefs['context'],worker_receipt=newrefs['receipt'],attempt_result=newrefs['terminal'])
        status['outcomes'][0].update(attempt_id=new_id,recovered=True)
    result['dispatched']=2
    # Hand-computed expected two-attempt costs and partial tokens, no aggregation oracle.
    for obj in (status,result):
        obj['all_attempt_denominators']=dict(obj['all_attempt_denominators'],C0=2)
        obj['accepted_cell_denominators']=dict(obj['accepted_cell_denominators'],C0=0 if failed else 1)
        obj['known_unknown_token_calls']=obj['unknown_token_calls']=2 if failed else 1;obj['all_attempt_token_usage_complete']=False
        obj['all_attempt_costs']=copy.deepcopy(obj['all_attempt_costs'])
        for key in t.COST:
            obj['all_attempt_costs']['C0'][key]={'observed_total':primary[key]+final[key],'observed_attempts':2,'missing_attempts':[]}
    return data,rd
