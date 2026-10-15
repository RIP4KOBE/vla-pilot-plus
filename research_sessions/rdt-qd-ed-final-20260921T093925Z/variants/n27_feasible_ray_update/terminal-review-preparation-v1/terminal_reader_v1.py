"""Independent finite N27 terminal metadata review; never replays native evidence."""
import argparse
from pathlib import Path
from collections import OrderedDict
import json
from bounded_json_v1 import Reader,need,canonical,is_ref,same_ref,MetadataError,bounded_bytes,parse
from metadata_checks_v1 import (COMMIT,COHORT,ARMS,GPU,DEV_LIMITS,WORKER,COST,CLIP,AUX,
 number,integer,identity,process_identity,source_record,cuda_identity,proof_metadata,recovery_metadata)

SENTINEL='__N27_REVIEW_ATTEMPT__'
CONTROL=('plan','source','result','status','journal','resources','precheck','cleanup','proof','proof_plan',
 'proof_report','proof_process','proof_terminal','bridge','source_review','authority','controller','release')
NAMES={'terminal':'attempt-result.json','context':'n23-worker-context.json','process':'process.json',
 'receipt':'eds_eval/in-worker-audit-receipt.json','audit':'eds_eval/decision-evidence-audit.json'}
TRUST=('Original same-process native arithmetic and raw-evidence integrity are inherited from hash-bound audit/receipt and root source/proof review; '
 'this reader does not rehash tensor/metric/compute/Stage payloads. Root attests extraction completeness and process cleanup.')

def projection(v,role):
    need(v.get('schema')==f'n27-current-terminal-{role}-projection-v1' and v.get('cohort_id')==COHORT
     and v.get('all_matching_events') is True and isinstance(v.get('events'),list)
     and v.get('event_count')==len(v['events']) and is_ref(v.get('source_ledger')) and is_ref(v.get('collector'))
     and number(v.get('collected_at')),'root complete current projection')
    return v['events']

def summary(cells,attempts):
    costs={a:{k:{'observed_total':0,'observed_attempts':0,'missing_attempts':[]} for k in COST} for a in ARMS}
    known=0;unknown=[]
    for x in attempts:
        t=x['terminal'];n=t.get('provider_logical_call_attempts');m=t.get('provider_usage_complete_calls')
        if integer(n) and integer(m) and m<=n:known+=n-m
        else:unknown.append(x['attempt_id'])
        for k in COST:
            slot=costs[x['profile']][k];v=t.get(k)
            if number(v):slot['observed_total']+=v;slot['observed_attempts']+=1
            else:slot['missing_attempts'].append(x['attempt_id'])
    by={a:{c['task_id']:c['success'] for c in cells if c['profile']==a} for a in ARMS};pairs={}
    for a in ARMS[:-1]:
        keys=by[a].keys()&by['N27'].keys();pairs[a]={'denominator':len(keys),'gains':sum(by['N27'][k] and not by[a][k] for k in keys),'losses':sum(by[a][k] and not by['N27'][k] for k in keys)}
    return {'accepted_cell_denominators':{a:len(by[a]) for a in ARMS},'matched_comparisons':pairs,
     'primary_attempt_denominators':{a:sum(x['profile']==a and not x['terminal'].get('retry_of') for x in attempts) for a in ARMS},
     'all_attempt_denominators':{a:sum(x['profile']==a for x in attempts) for a in ARMS},'all_attempt_costs':costs,
     'known_unknown_token_calls':known,'unknown_token_calls':None if unknown else known,'unmeasured_token_call_attempts':unknown,
     'all_attempt_token_usage_complete':bool(attempts) and not unknown and known==0 and all(x['terminal'].get('provider_token_usage_complete') is True for x in attempts),
     'token_cost_interpretation':'observed token totals are partial lower bounds when usage is unknown'}

def terminal_binding(v,row,plan,ref):
    need(v.get('identity')==identity(row) and v.get('episode_key')==row['episode_key'] and v.get('source_commit')==COMMIT
     and v.get('plan_sha256')==ref['sha256'] and v.get('profile_manifest_sha256')==plan['profiles_sha256']
     and v.get('runtime_manifest_sha256')==plan['runtime_manifest_sha256']
     and v.get('runtime_inventory_sha256')==plan['runtime_inventory_sha256'] and v.get('init_row_sha256')==row['init_row_sha256']
     and v.get('physical_gpu')==7,'terminal plan/source/identity')

def audit_metadata(reader,binding,final,row,plan,source,refs,pre):
    rr=binding['refs'];ctx=reader.get(rr['context'],'context');receipt=reader.get(rr['receipt'],'receipt')
    audit=reader.get(rr['audit'],'audit');process=reader.get(rr['process'],'process')
    need(all(isinstance(x,dict) for x in (ctx,receipt,audit,process)),'missing accepted native metadata')
    out=Path(plan['artifact_root'])/'attempts'/final['attempt_id'];pid=process_identity(process)
    template=next(x['argv'] for x in pre['command_templates'] if x['episode_key']==row['episode_key'])
    argv=[v.replace(SENTINEL,final['attempt_id']) for v in template][1:]
    runtime={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}
    expected={'schema':'n23-metered-worker-context-v1','attempt_id':final['attempt_id'],'episode_key':row['episode_key'],
     'profile':row['profile'],'output_dir':str(out),'worktree':plan['worktree'],'main_argv':argv,'plan':refs['plan'],'runtime':runtime,'source':source}
    need(ctx==expected and process.get('attempt_id')==final['attempt_id'] and final.get('process')==process
     and same_ref(final.get('n23_worker_receipt'),rr['receipt']),'context/terminal/process association')
    need(receipt.get('schema')=='n23-in-worker-audit-receipt-v1' and receipt.get('accepted') is True
     and receipt.get('main_exit_code')==0 and receipt.get('process')==pid and receipt.get('process_unchanged') is True
     and same_ref(receipt.get('context'),rr['context']) and all(receipt.get(k)==ctx[k] for k in ('attempt_id','episode_key','profile','plan','runtime','source'))
     and receipt.get('main_argv_sha256')==canonical(argv),'receipt source/command/process')
    ev=receipt.get('evidence',{});items=ev.get('files');need(isinstance(items,list) and 3<=len(items)<=100000 and ev.get('sha256')==canonical(items),'canonical native evidence metadata digest')
    paths=[x.get('path') for x in items]
    need(len(paths)==len(set(paths)) and all(isinstance(p,str) and not Path(p).is_absolute() and '..' not in Path(p).parts for p in paths)
     and all(set(x)=={'path','sha256'} and is_ref({'path':'/'+x['path'],'sha256':x['sha256']}) for x in items)
     and {'eds_eval/episode_compute.jsonl','eds_eval/decision_evidence/episode_000/status.json','eds_eval/decision_evidence/episode_000/events.jsonl'}<=set(paths),'native evidence metadata paths')
    need(same_ref(receipt.get('audit_report'),rr['audit']) and audit.get('accepted') is True and audit.get('evidence_complete') is True
     and audit.get('schema')=='qd-ed-decision-evidence-audit-v1' and audit.get('episode_dir')==str(out/'eds_eval/decision_evidence/episode_000')
     and audit.get('episode_compute_file')==str(out/'eds_eval/episode_compute.jsonl'),'audit association')
    cuda_identity(receipt.get('worker_cuda',{}));backend=receipt.get('audit_backend',{});kind='cuda' if row['profile'] in {'N26','N27'} else 'cpu'
    need(backend.get('kind')==kind and backend.get('logical_device')==('cuda:0' if kind=='cuda' else 'cpu') and audit.get('n23_arithmetic_backend')==backend,'audit backend')
    if kind=='cuda':need(backend.get('physical_uuid')==GPU and backend.get('torch_version')==receipt['worker_cuda'].get('torch_version') and backend.get('cuda_version')==receipt['worker_cuda'].get('cuda_version'),'backend identity')
    need(number(receipt.get('audit_seconds')) and number(receipt.get('worker_wall_seconds')) and receipt['audit_seconds']<=receipt['worker_wall_seconds']<=final['gpu_process_wall_seconds'],'same-process audit cost')
    n=final.get('guided_chunks');need(integer(n),'guided count unknown')
    observed=audit.get('observed_counts',{});need(type(observed.get('canonical_candidate_batch',0)) is int and observed.get('canonical_candidate_batch',0)==11*n,'native canonical denominator')
    counts=receipt.get('n27_native_counts');aux=receipt.get('n27_auxiliary')
    need(isinstance(counts,dict) and isinstance(aux,dict) and all(number(v) for v in [*counts.values(),*aux.values()]) and counts.get('guided_decisions')==n,'native scalar receipt')
    metric=receipt.get('n27_metrics',{});need(metric.get('path')==str(out/'eds_eval/eds_metrics.jsonl') and type(metric.get('present')) is bool,'metric-presence evidence')
    need(is_ref({'path':metric['path'],'sha256':metric.get('sha256')}) if metric['present'] else n==0 and metric.get('sha256') is None,'zero-guided metrics absence')
    gates=('n25_actuator_clipped_rbf_audit','n26_clean_output_rbf_audit','n27_feasible_ray_rbf_audit')
    arm=row['profile'];own=2 if arm=='N27' else 1 if arm=='N26' else None
    need(all(not audit.get(k) for i,k in enumerate(gates) if i!=own),'cross-profile native marker')
    if own is None:
        need(counts=={'guided_decisions':n,'parent_rounds_verified':0} and aux=={}
         and not audit.get('n23_actuator_clipped_quality_audit') and not audit.get('n24_gripper_parent_rescue_audit'),'legacy control counters')
    else:
        gate=audit.get(gates[own],{});need(gate.get('schema')==f'{arm.lower()}-native-rbf-audit-v1' and gate.get('accepted') is True and gate.get('guided_decisions')==n,'profile-bound gate missing')
        fields=('all_call_summaries_verified','witness_calls_verified','zero_gradient_calls','clipped_components')+(('limited_rows','realized_nonzero_delta_components') if arm=='N27' else ())
        need(all(integer(gate.get(k)) and counts.get(k)==gate[k] for k in fields) and gate['all_call_summaries_verified']==19*n
         and gate['witness_calls_verified']==(11 if n else 0) and gate['zero_gradient_calls']<=19*n,'RBF receipt/native counts')
        need(final.get('rbf_gradient_calls')==19*n and final.get('rbf_gradient_batch_rows')==16*19*n,'RBF measured cost')
        if n:
            selection=audit.get('n5_grasp_timing_audit',{});clip=audit.get('n23_actuator_clipped_quality_audit',{})
            need(all(selection.get(k)==v for k,v in {'checked_decisions':n,'parent_rounds_verified':10*n,'canonical_batches_verified':11*n,'canonical_candidates_verified':176*n}.items())
             and counts.get('parent_rounds_verified')==10*n and all(integer(clip.get(k)) and counts.get(k)==clip[k] for k in CLIP)
             and clip['score_batches_verified']==11*n and clip['candidate_scores_verified']==176*n and set(aux)==set(AUX),'QD/ED native coverage')
        else:need(counts.get('parent_rounds_verified')==0 and not audit.get('n5_grasp_timing_audit') and not audit.get('n23_actuator_clipped_quality_audit') and aux=={},'unguided native coverage')
    if final.get('outcome_valid') is True:
        need(final.get('required_cost_telemetry_complete') is True and final.get('provider_token_usage_complete') is True
         and integer(final.get('provider_logical_call_attempts')) and final.get('provider_usage_complete_calls')==final['provider_logical_call_attempts']
         and final.get('provider_failed_calls')==0 and final.get('candidate_evaluations')==176*n and final.get('score_batches')==11*n
         and all(number(final.get(k)) for k in COST) and type(final.get('success')) is bool,'accepted complete costs/result')
    return counts,aux


def reconstruct(data,reader):
    need(data.get('schema')=='n27-terminal-metadata-input-v1' and data.get('root_authorized') is True and data.get('executable') is True,'disabled/unreviewed inventory')
    refs=data['refs'];need(set(refs)==set(CONTROL),'exact control roles')
    get=lambda role:reader.get(refs[role],role)
    plan=get('plan');source=get('source');source_record(source);pre=get('precheck');sr=get('source_review');bridge=get('bridge');authority=get('authority')
    runtime={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']};cohort=plan.get('n27_cohort',{})
    need(plan.get('source_commit')==COMMIT and plan.get('code_files')==source['files'] and plan.get('frozen') is True
     and plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}
     and cohort.get('cohort_id')==COHORT and cohort.get('limits')==DEV_LIMITS and cohort.get('worker_audit')==WORKER
     and cohort.get('early_stop')=='none_full_sixteen_required','plan/source/screen contract')
    rows=plan['episodes'];keys=[r['episode_key'] for r in rows]
    need(len(rows)==len(set(keys))==16 and [(r['task_id'],r['profile']) for r in rows]==[(t,a) for t in range(4) for a in ARMS]
     and all(r['split']=='dev' and r['iteration']==COHORT and r['timeout_seconds']==1800 for r in rows),'exact16 matrix')
    need(sr.get('schema')=='n27-source-runtime-review-v1' and sr.get('disposition')=='accepted' and sr.get('source')==source and sr.get('runtime')==runtime
     and same_ref(sr.get('backend_proof'),refs['proof']) and same_ref(sr.get('source_bridge'),refs['bridge']) and same_ref(cohort.get('final_review'),refs['source_review'])
     and sr.get('no_gpu_release') is True and bridge.get('new_source')==source and bridge.get('runtime')==runtime,'source/proof bridge')
    need(authority.get('schema')=='n27-screen-authority-v1' and authority.get('source')==source and authority.get('runtime')==runtime
     and same_ref(authority.get('final_review'),refs['source_review']) and same_ref(cohort.get('authority'),refs['authority'])
     and authority.get('limits')==DEV_LIMITS and authority.get('local_gpu_hours')==9.25
     and authority.get('validation_authorized') is False and authority.get('formal_authorized') is False,'finite authority')
    need(bridge.get('schema')=='n27-source-equivalence-bridge-v1' and bridge.get('gpu_release') is False
     and bridge.get('changed_existing')==['core/rdt_policy_steer.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py']
     and bridge.get('unchanged_original_files')==312 and bridge.get('original_source',{}).get('commit')=='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
     and len(bridge['original_source'].get('files',[]))==315 and bridge['original_source'].get('sha256')==canonical(bridge['original_source']['files'])
     and set(bridge.get('predecessor_refs',{}))=={'review','result','source','plan','budget'}
     and all(is_ref(v) for v in bridge['predecessor_refs'].values()),'bounded historical source bridge shape')
    need(authority.get('cohort_id')==COHORT and all(is_ref(sr.get(k)) and authority.get(k)==sr[k] and cohort.get(k)==sr[k]
      for k in ('protocol','predecessor','budget_reuse')) and sr['predecessor']==bridge['predecessor_refs']['review'],
      'visible authority/protocol/predecessor chain')
    bound={k:refs[k] for k in ('plan','source','proof','bridge','source_review','authority','release')}
    need(pre.get('schema')=='n27-terminal-prerequisite-attestation-v1' and pre.get('bindings')==bound
     and pre.get('runtime')==runtime and pre.get('source_commit')==COMMIT and pre.get('source_files_verified')==345
     and pre.get('operations')==['validate_plan','build_command'] and pre.get('all_prerequisites_passed') is True
     and pre.get('historical_proof_lineage_verified') is True and pre.get('model_api_sim_calls')==0 and is_ref(pre.get('collector')),'root source/plan/proof attestation')
    templates=pre.get('command_templates',[])
    need([x.get('episode_key') for x in templates]==keys and all(isinstance(x.get('argv'),list) and len(x['argv'])>=2
     and all(isinstance(s,str) for s in x['argv']) and x['argv'][1]==str(Path(plan['worktree'])/'main.py') and any(SENTINEL in s for s in x['argv']) for x in templates),'bound16 original commands')
    journal=get('journal');events=projection(journal,'journal');resources=projection(get('resources'),'resource')
    need(is_ref(journal.get('snapshot')) and journal.get('snapshot_events_sha256')==canonical(events),'snapshot attestation binding')
    need(all(e.get('identity',{}).get('iteration')==COHORT for e in events),'only N27 journal events')
    proof,proof_seconds,proof_process=proof_metadata(reader,refs['proof'],source,runtime,resources)
    need(all(same_ref(proof[k],refs['proof_'+k]) for k in ('plan','report','process','terminal')),'proof explicit inventory refs')
    controller=get('controller');release=get('release');source_hash={v['path']:v['sha256'] for v in source['files']}
    need(controller.get('schema')=='n27-root-controller-process-v1' and controller.get('source_commit')==COMMIT and controller.get('plan')==refs['plan']
     and controller.get('release')==refs['release'] and controller.get('physical_gpu')==7 and controller.get('one_launch') is True and is_ref(controller.get('wrapper'))
     and controller.get('entrypoint')=={'path':str(Path(plan['worktree'])/'scripts/qd_ed_n27_supervise.py'),'sha256':source_hash['scripts/qd_ed_n27_supervise.py']},'controller identity')
    need(release=={'schema':'n27-dev-execution-release-v1','plan':refs['plan'],'source_commit':COMMIT,'cohort_id':COHORT,'episode_keys':keys,
     'authority':refs['authority'],'physical_gpu':7,'limits':DEV_LIMITS,'validation_authorized':False,'formal_authorized':False},'exact release')
    bindings=data['attempts'];ids=[v['attempt_id'] for v in bindings];need(len(ids)==len(set(ids))<=18,'unique bounded attempts')
    lookup={b['attempt_id']:b for b in bindings};groups=OrderedDict();closed=set();previous=None
    for e in events:
        aid=e.get('attempt_id');need(aid in lookup and e.get('episode_key') in keys,'unlisted attempt')
        if aid!=previous:
            need(aid not in closed,'interleaved attempt')
            if previous is not None:closed.add(previous)
            previous=aid
        groups.setdefault(aid,[]).append(e)
    need(list(groups)==ids,'complete ordered attempt inventory')
    attempts=[];bycell={k:[] for k in keys};processes={'controller':process_identity(controller['process']),'proof':process_identity(proof_process)}
    dispatched=0;index=-1;end=None;unsettled=[]
    for aid,g in groups.items():
        first=g[0];pos=keys.index(first['episode_key']);row=rows[pos];rr=lookup[aid]['refs'];kinds=[x['event'] for x in g]
        need(pos in {index,index+1} and pos>=0 and (pos!=index or first.get('retry_of')),'contiguous global cell order')
        need(kinds in (['reserved'],['reserved','dispatched'],['reserved','aborted'],['reserved','dispatched','valid'],['reserved','dispatched','aborted']),'attempt lifecycle')
        need(all(number(x.get('time_unix')) for x in g) and [x['time_unix'] for x in g]==sorted(x['time_unix'] for x in g)
         and (end is None or first['time_unix']>=end),'global serial chronology');index=pos;end=g[-1]['time_unix']
        out=Path(plan['artifact_root'])/'attempts'/aid;need(Path(aid).name==aid and set(rr)==set(NAMES)
         and all(Path(rr[k]['path'])==out/v for k,v in NAMES.items()),'attempt role/path scope')
        for e in g:
            terminal_binding(e,row,plan,refs['plan']);need(e.get('output_dir')==str(out) and e.get('retry_of')==first.get('retry_of'),'group identity')
        for role,ref in rr.items():reader.get(ref,role)  # Explicit inventory only; no raw evidence follow.
        process=reader.get(rr['process'],'process');sent='dispatched' in kinds;dispatched+=sent
        if process is not None:need(process.get('attempt_id')==aid,'process belongs to attempt')
        processes[aid]=process_identity(process) if process is not None else None
        final=g[-1]
        if final['event'] not in {'valid','aborted'}:unsettled.append(aid)
        else:need(reader.get(rr['terminal'],'terminal')==final,'terminal/journal mismatch')
        need(all(e.get('budget_bucket')==('recovery' if first.get('retry_of') else row['budget_bucket']) for e in g),'attempt budget bucket')
        if final['event'] in {'valid','aborted'}:
            cost=final.get('gpu_process_wall_seconds')
            need(cost is None or number(cost) and cost<=1840,'invalid measured wall cost')
            if not sent:need(cost in (None,0),'undispatched nonzero wall cost')
            need(final.get('n27_episode_dispatched') is sent,'terminal dispatch marker')
        attempts.append({'attempt_id':aid,'episode_key':row['episode_key'],'profile':row['profile'],'terminal':final});bycell[row['episode_key']].append(g)
    need(dispatched<=18 and sum(bool(g[0].get('retry_of')) for g in groups.values())<=2,'dispatch/recovery cap')
    accepted=[];native={a:{} for a in ARMS};aux={a:{} for a in ARMS};failure=None
    for row in rows:
        own=bycell[row['episode_key']]
        if not own:break
        need(1<=len(own)<=2 and own[0][0].get('retry_of') is None,'one primary plus at most one retry')
        first=own[0][-1];final=first
        if len(own)==2:
            final=own[1][-1];need(first.get('outcome_valid') is False and final.get('retry_of')==first['attempt_id']
             and [e['event'] for e in own[0]]==['reserved','dispatched','valid'],'sole-timeout retry chronology')
            # A failed/aborted recovery still needs its original dispatch authority.
            recovery_metadata(reader,lookup[final['attempt_id']],lookup[first['attempt_id']],first,final,row,plan,refs,source)
            need(all(e.get('n27_recovery_eligibility')==lookup[final['attempt_id']]['eligibility'] for e in own[1]),'all retry events bind eligibility')
            audit_metadata(reader,lookup[first['attempt_id']],first,row,plan,source,refs,pre)
        try:
            need(final.get('event')=='valid' and final.get('outcome_valid') is True,'no valid scientific outcome')
            counts,extra=audit_metadata(reader,lookup[final['attempt_id']],final,row,plan,source,refs,pre)
        except (MetadataError,KeyError,TypeError,ValueError) as e:
            failure={'episode_key':row['episode_key'],'independent_reason':str(e)};break
        rr=lookup[final['attempt_id']]['refs'];accepted.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],
         'attempt_id':final['attempt_id'],'success':final['success'],'audit':rr['audit'],'worker_context':rr['context'],'worker_receipt':rr['receipt'],'attempt_result':rr['terminal']})
        for k,v in counts.items():native[row['profile']][k]=native[row['profile']].get(k,0)+v
        for k,v in extra.items():aux[row['profile']][k]=aux[row['profile']].get(k,0)+v
    prefix=[x['episode_key'] for x in accepted];allowed=set(prefix)|({keys[len(prefix)]} if len(prefix)<16 else set())
    need(all(e['episode_key'] in allowed for e in events),'later cell after invalid or gap')
    counts={a:{'audited':sum(c['profile']==a for c in accepted),'success':sum(c['profile']==a and c['success'] for c in accepted)} for a in ARMS}
    wins=counts['N27']['success'];promoted=len(accepted)==16 and wins>=2 and wins>=max(counts[a]['success'] for a in ARMS[:-1]) and wins>counts['N26']['success'] and native['N27'].get('guided_decisions',0)>0 and native['N27'].get('parent_rounds_verified',0)>0
    raw='ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV' if promoted else 'REJECT_SCREEN' if len(accepted)==16 else 'INVALID_OR_INTERRUPTED'
    status=get('status') or {'status':'unavailable','failure_class':'FileNotFoundError'};result=get('result');phase=status.get('status')
    consistent=status.get('completed_keys')==prefix and status.get('dev_gate_promoted') is promoted
    consistent=consistent and ((phase=='completed_all_sixteen_audited' and len(accepted)==16) or (phase in {'failed','interrupted'} and raw=='INVALID_OR_INTERRUPTED'))
    decision=raw if consistent else 'INVALID_OR_INTERRUPTED';costs=summary(accepted,attempts)
    visible={'schema':'n27-dev-cohort-result-v1','cohort_id':COHORT,'source_commit':COMMIT,'planned':16,'dispatched':dispatched,'audited_cells':len(accepted),
     'counts':counts,'accepted_cells':accepted,'attempts':attempts,'native':native,'auxiliary':aux,'dev_gate_promoted':promoted if consistent else False,'decision':decision,
     'goal_status':'TARGET_NOT_MET','validation_authorized':False,'formal_authorized':False,**costs}
    errors=[]
    if result is None:errors.append('missing_immutable_result')
    else:
        errors.extend(k for k,v in visible.items() if result.get(k)!=v)
        ce={'completed_keys':status.get('completed_keys'),'journal_accepted_keys':prefix,'consistent':consistent,'status_phase':phase}
        if not consistent:
            ce['disagreement']='Controller status and independently reconstructed journal differ; no resume or promotion.'
            if result.get('journal_reconstructed_disposition')!=raw:errors.append('journal_reconstructed_disposition')
        if result.get('controller_evidence')!=ce:errors.append('controller_evidence')
        for k,v in {'plan':refs['plan'],'source_bridge':refs['bridge'],'ledger_snapshot':journal.get('snapshot'),
         'reader':{'path':str(Path(plan['worktree'])/'scripts/qd_ed_n27_report.py'),'sha256':source_hash['scripts/qd_ed_n27_report.py']},
         'terminal_status':{**refs['status'],'content':status}}.items():
            if result.get(k)!=v:errors.append(k)
        f=result.get('failure')
        if failure is None:
            if f is not None:errors.append('failure')
        elif not(isinstance(f,dict) and f.get('episode_key')==failure['episode_key'] and isinstance(f.get('reason'),str) and isinstance(f.get('failure_class'),str)):errors.append('failure')
    if decision!='INVALID_OR_INTERRUPTED':
        outcomes=[{k:x[k] for k in ('episode_key','task_id','profile','success','attempt_id')}|{'recovered':bool(next(t['terminal'].get('retry_of') for t in attempts if t['attempt_id']==x['attempt_id']))} for x in accepted]
        expected={'schema':'n27-dev-supervisor-status-v1','cohort_id':COHORT,'source_commit':COMMIT,'plan':refs['plan'],'completed_keys':prefix,
         'attempts':attempts,'outcomes':outcomes,'successes':{a:counts[a]['success'] for a in ARMS},'native':native,'auxiliary':aux,'dev_gate_promoted':promoted,'protected_authorized':False,**costs}
        errors.extend('status.'+k for k,v in expected.items() if status.get(k)!=v)
    cleanup=get('cleanup');need(cleanup.get('schema')=='n27-root-cleanup-attestation-v1' and cleanup.get('plan')==refs['plan'] and cleanup.get('source')==refs['source']
     and cleanup.get('controller')==refs['controller'] and cleanup.get('journal')==refs['journal'] and cleanup.get('resources')==refs['resources']
     and cleanup.get('process_identities')==processes and is_ref(cleanup.get('collector')) and number(cleanup.get('collected_at'))
     and cleanup.get('locks_held') is True and cleanup.get('current_matching_subsets_equal') is True,'bound root cleanup/current projection')
    checks=cleanup.get('checks',{});need(set(checks)==set(processes),'all process cleanup roles')
    for key,pid in processes.items():
        need(checks[key].get('identity')==pid,'cleanup identity')
        if pid is None:need(checks[key].get('same_identity_alive') is None and checks[key].get('group_alive') is None,'missing historical PID remains Unknown')
        else:need(checks[key].get('same_identity_alive') is False and checks[key].get('group_alive') is False,'known owned process not cleaned')
    cleanup_complete=all(pid is not None or not any(x['attempt_id']==key and x['event']=='dispatched' for x in events) for key,pid in processes.items())
    reader.require_consumed()
    return {'schema':'n27-root-terminal-review-v1','decision':'ACCEPT_TERMINAL_RECONSTRUCTION' if not errors and not unsettled else 'REJECT_TERMINAL_RECONSTRUCTION',
     'cohort_disposition':decision,'result':refs['result'],'plan':refs['plan'],'source':refs['source'],'journal':refs['journal'],'resources':refs['resources'],
     'counts':counts,'accepted_cells':len(accepted),'dispatched':dispatched,'attempts':attempts,'costs':costs,'native':native,'auxiliary':aux,
     'proof_seconds':proof_seconds,'controller_consistent':consistent,'cleanup_complete':cleanup_complete,'cleanup_unknown':[k for k,p in processes.items() if p is None],
     'discrepancies':errors,'unsettled_attempts':unsettled,'failure':failure,'evidence_scope':TRUST,
     'native_payload_rehashed':False,'native_arithmetic_replayed':False,'resume_authorized':False,'dispatch_authorized':False,
     'validation_authorized':False,'formal_authorized':False,'goal_status':'TARGET_NOT_MET'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    inventory_bytes=bounded_bytes(a.inventory.absolute(),16*1024*1024);data=parse(inventory_bytes);need(a.output.is_absolute() and a.output.name=='root-terminal-review-v1.json' and not a.output.exists(),'new explicit root review output')
    reader=Reader(data['files']);result=reconstruct(data,reader)
    result.update(reader={'path':str(Path(__file__).absolute()),'sha256':__import__('hashlib').sha256(Path(__file__).read_bytes()).hexdigest()},input_inventory={'path':str(a.inventory.absolute()),'sha256':__import__('hashlib').sha256(inventory_bytes).hexdigest()},metadata_bytes_read=reader.bytes)
    own=[{'path':str(Path(__file__).absolute().parent/name),'sha256':__import__('hashlib').sha256((Path(__file__).absolute().parent/name).read_bytes()).hexdigest()}
         for name in ('bounded_json_v1.py','metadata_checks_v1.py','terminal_reader_v1.py')]
    result['reader_sources']={'files':own,'sha256':canonical(own)}
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
if __name__=='__main__':main()
