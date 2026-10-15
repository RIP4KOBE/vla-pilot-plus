#!/usr/bin/env python3
"""Root-only independent N26 terminal metadata reconstruction; never repairs results."""
import argparse
from collections import OrderedDict
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import time
from bounded_metadata_v1 import Reader, MetadataError, need, canonical, digest, decode, load_bound, same_ref, is_ref, ref
from metadata_semantics_v1 import *

SENTINEL='__N26_REVIEW_ATTEMPT__'
def projection(v,kind):
    need(v.get('schema')==kind and v.get('cohort_id')==COHORT and v.get('all_matching_events') is True
         and isinstance(v.get('events'),list) and is_ref(v.get('source_ledger')) and is_ref(v.get('collector'))
         and number(v.get('collected_at')) and v.get('event_count')==len(v['events']),'root current subset projection')
    return v['events']
def file_ref(refs,key,reader,role=None):
    need(key in refs,'missing required reference: '+key)
    return reader.get(refs[key],role or key)
def summary(cells,attempts):
    by={a:{v['task_id']:v['success'] for v in cells if v['profile']==a} for a in ARMS}
    costs={a:{k:{'observed_total':0,'observed_attempts':0,'missing_attempts':[]} for k in COST} for a in ARMS}
    unknown=[];unmeasured=[]
    for x in attempts:
        f=x['terminal'];total=f.get('provider_logical_call_attempts');complete=f.get('provider_usage_complete_calls')
        if integer(total) and integer(complete) and complete<=total:unknown.append(total-complete)
        else:unmeasured.append(x['attempt_id'])
        for k in COST:
            slot=costs[x['profile']][k];value=f.get(k)
            if number(value):slot['observed_total']+=value;slot['observed_attempts']+=1
            else:slot['missing_attempts'].append(x['attempt_id'])
    pairs={}
    for a in ARMS[:-1]:
        matching=set(by['N26'])&set(by[a])
        pairs[a]={'denominator':len(matching),'gains':sum(by['N26'][t] and not by[a][t] for t in matching),
                  'losses':sum(not by['N26'][t] and by[a][t] for t in matching)}
    return {'accepted_cell_denominators':{a:len(v) for a,v in by.items()},'matched_comparisons':pairs,
      'primary_attempt_denominators':{a:sum(x['profile']==a and not x['terminal'].get('retry_of') for x in attempts) for a in ARMS},
      'all_attempt_denominators':{a:sum(x['profile']==a for x in attempts) for a in ARMS},'all_attempt_costs':costs,
      'known_unknown_token_calls':sum(unknown),'unknown_token_calls':None if unmeasured else sum(unknown),
      'unmeasured_token_call_attempts':unmeasured,'all_attempt_token_usage_complete':bool(attempts) and not unmeasured and not sum(unknown)
       and all(x['terminal'].get('provider_token_usage_complete') is True for x in attempts),
      'token_cost_interpretation':'observed token totals are partial lower bounds when usage is unknown'}
def terminal_binding(final,row,plan,planref):
    need(final.get('identity')==identity(row) and final.get('episode_key')==row['episode_key']
         and final.get('source_commit')==COMMIT and final.get('plan_sha256')==planref['sha256']
         and final.get('profile_manifest_sha256')==plan['profiles_sha256']
         and final.get('runtime_manifest_sha256')==plan['runtime_manifest_sha256']
         and final.get('runtime_inventory_sha256')==plan['runtime_inventory_sha256']
         and final.get('init_row_sha256')==row['init_row_sha256'] and final.get('physical_gpu')==7,'terminal frozen identity')
def audit_metadata(reader,binding,final,row,plan,source,runtime,refs,precheck):
    rr=binding['refs'];out=Path(final['output_dir']);ctx=file_ref(rr,'context',reader)
    need(ctx is not None,'native context absent')
    expected=next(x for x in precheck['command_templates'] if x['episode_key']==row['episode_key'])
    cmd=[x.replace(SENTINEL,final['attempt_id']) for x in expected['argv']]
    need(ctx=={'schema':'n23-metered-worker-context-v1','attempt_id':final['attempt_id'],'episode_key':row['episode_key'],
      'profile':row['profile'],'output_dir':str(out.resolve()),'worktree':str(Path(plan['worktree']).resolve()),
      'main_argv':cmd[1:],'plan':refs['plan'],'runtime':refs['runtime'],'source':source},'context original command/source')
    need(same_ref(rr['context'],{'path':str(out/'n23-worker-context.json'),'sha256':rr['context']['sha256']}),'context output ownership')
    command=file_ref(rr,'command',reader)
    wrapped=[cmd[0],str(Path(plan['worktree'])/'scripts/qd_ed_n23_worker.py'),'--context',str(Path(rr['context']['path']).resolve()),'--main',cmd[1],'--',*cmd[2:]]
    env={**runtime['environment'],'CUDA_VISIBLE_DEVICES':'7','CUDA_DEVICE_ORDER':'PCI_BUS_ID','MUJOCO_EGL_DEVICE_ID':str(runtime['gpu_mapping']['egl_device_index'])}
    need(command=={'argv':wrapped,'environment_public':env},'original wrapped command')
    process=file_ref(rr,'process',reader);receipt=file_ref(rr,'receipt',reader);audit=file_ref(rr,'audit',reader);start=file_ref(rr,'audit_start',reader)
    need(all(isinstance(x,dict) for x in (process,receipt,audit,start)),'native process/audit/receipt absent')
    pid=process_identity(process)
    need(process.get('attempt_id')==final['attempt_id'] and final.get('process')==process
         and same_ref(final.get('n23_worker_receipt'),rr['receipt']),'terminal metered receipt')
    need(receipt.get('schema')=='n23-in-worker-audit-receipt-v1' and receipt.get('accepted') is True
         and receipt.get('main_exit_code')==0 and receipt.get('process')==pid and receipt.get('process_unchanged') is True
         and same_ref(receipt.get('context'),rr['context'])
         and all(receipt.get(k)==ctx[k] for k in ('attempt_id','episode_key','profile','plan','runtime','source'))
         and receipt.get('main_argv_sha256')==canonical(cmd[1:]),'receipt identity')
    need(start=={'schema':'n23-worker-start-v1','process':pid,'context':rr['context']},'native start identity')
    ev=receipt.get('evidence',{});items=ev.get('files')
    need(isinstance(items,list) and len(items)>=3 and ev.get('sha256')==canonical(items),'canonical evidence-index digest')
    paths=[q.get('path') for q in items]
    need(len(paths)==len(set(paths)) and all(isinstance(p,str) and not Path(p).is_absolute() and '..' not in Path(p).parts for p in paths)
         and all(set(q)=={'path','sha256'} and isinstance(q['sha256'],str) and len(q['sha256'])==64 for q in items)
         and {'eds_eval/episode_compute.jsonl','eds_eval/decision_evidence/episode_000/status.json','eds_eval/decision_evidence/episode_000/events.jsonl'}<=set(paths),'evidence index structure')
    compute=file_ref(rr,'compute',reader);metrics=file_ref(rr,'metrics',reader)
    need(isinstance(compute,list) and len(compute)==1 and isinstance(compute[0],dict),'compute record')
    need(next(x['sha256'] for x in items if x['path']=='eds_eval/episode_compute.jsonl')==rr['compute']['sha256'],'compute evidence digest')
    need(same_ref(receipt.get('audit_report'),rr['audit']) and audit.get('accepted') is True and audit.get('evidence_complete') is True
         and audit.get('schema')=='qd-ed-decision-evidence-audit-v1'
         and Path(audit['episode_dir']).resolve()==out.resolve()/'eds_eval/decision_evidence/episode_000'
         and Path(audit['episode_compute_file']).resolve()==out.resolve()/'eds_eval/episode_compute.jsonl','native report association')
    actual=receipt.get('worker_cuda',{});cuda_identity(actual)
    backend=receipt.get('audit_backend',{});kind='cuda' if row['profile'] in {'N25','N26'} else 'cpu'
    need(backend.get('kind')==kind and backend.get('logical_device')==('cuda:0' if kind=='cuda' else 'cpu')
         and audit.get('n23_arithmetic_backend')==backend,'receipt native backend')
    if kind=='cuda':
        need(backend.get('physical_uuid')==GPU and backend.get('torch_version')==actual.get('torch_version')
             and backend.get('cuda_version')==actual.get('cuda_version') and isinstance(backend.get('dtype_coverage'),list),'backend version')
    need(number(receipt.get('audit_seconds')) and number(receipt.get('worker_wall_seconds'))
         and receipt['audit_seconds']<=receipt['worker_wall_seconds']<=final['gpu_process_wall_seconds'],'same-worker metering')
    expected_metric={'path':str(out/'eds_eval/eds_metrics.jsonl'),'present':metrics is not None,'sha256':rr['metrics']['sha256']}
    need(receipt.get('n26_metrics')==expected_metric,'metric presence/receipt binding')
    if metrics is None:metrics=[]
    need(isinstance(metrics,list),'metrics JSONL')
    compute_binding(compute[0],row,final,runtime,final.get('outcome_valid') is True)
    counts,aux=native_counts(row['profile'],metrics,compute[0],audit,final)
    need(receipt.get('n26_native_counts')==counts and receipt.get('n26_auxiliary')==aux,'native count receipt')
    return counts,aux
def recovery_metadata(reader,binding,primary_binding,primary,recovered,row,plan,refs,source):
    reference=binding.get('eligibility');record=reader.get(reference,'eligibility')
    attest=reader.get(binding.get('recovery_attestation'),'recovery_attestation')
    need(record.get('schema')=='n26-typed-timeout-eligibility-v1' and record.get('cohort_id')==COHORT
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
         and record['protocol']['sha256']=='7c64679c35ffc3c9a53d8309ceea7668de872f03fc5e2d2ed16bae2c43058b55'
         and record.get('evidence_packaging_mode') in {'unchanged_original_reader','n26_absent_zero_guided_private_reader'}
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
    for reference,path in ((record.get('evidence_packaging_reader'),'scripts/qd_ed_n26_recovery.py'),
                           (d.get('diagnostic_reader'),'scripts/qd_ed_n23_v2_recovery.py')):
        need(is_ref(reference) and Path(reference['path']).resolve()==Path(plan['worktree']).resolve()/path
             and reference['sha256']==source_hash[path],'original classifier source')
    need(attest.get('schema')=='n26-original-typed-eligibility-attestation-v1'
         and same_ref(attest.get('eligibility'),binding['eligibility']) and attest.get('source')==refs['source']
         and attest.get('plan')==refs['plan'] and attest.get('primary_attempt_id')==primary['attempt_id']
         and attest.get('method')=='original_frozen_controller_and_classifier_metadata'
         and attest.get('classification_basis_sha256')==canonical(record)
         and attest.get('root_verified_original_basis') is True
         and attest.get('stage_and_tensors_reaudited_by_terminal_reader') is False
         and is_ref(attest.get('collector')),'missing explicit root classifier provenance')
    need(recovered.get('retry_of')==primary['attempt_id'] and recovered.get('budget_bucket')=='recovery'
         and same_ref(recovered.get('n26_recovery_eligibility'),binding['eligibility']),'retry identity')
def check_projection_freshness(snapshot,current):
    need(snapshot==current,'later/missing/reordered matching events')
def reconstruct(data,reader):
    need(data.get('schema')=='n26-terminal-metadata-input-v1' and data.get('root_authorized') is True
         and data.get('executable') is True,'root authorized metadata inventory required')
    refs=data['refs'];plan=file_ref(refs,'plan',reader);source=file_ref(refs,'source',reader);source_record(source)
    runtime=file_ref(refs,'runtime',reader);pre=file_ref(refs,'precheck',reader)
    original_review=file_ref(refs,'source_review',reader);bridge=file_ref(refs,'source_bridge',reader)
    need(same_ref(plan['n26_cohort'].get('final_review'),refs['source_review'])
         and original_review.get('schema')=='n26-source-runtime-review-v1' and original_review.get('disposition')=='accepted'
         and original_review.get('source')==source and same_ref(original_review.get('runtime'),refs['runtime'])
         and same_ref(original_review.get('source_bridge'),refs['source_bridge'])
         and same_ref(original_review.get('backend_proof'),refs['proof']) and original_review.get('no_gpu_release') is True,
         'original final source review/proof/bridge')
    need(bridge.get('schema')=='n26-source-equivalence-bridge-logical-v1' and bridge.get('new_source')==source
         and same_ref(bridge.get('runtime'),refs['runtime']) and bridge.get('new_rbf_arithmetic_proof_required') is True,
         'historical logical source bridge')
    need(plan.get('source_commit')==COMMIT and plan.get('code_files')==source['files'] and plan.get('frozen') is True
         and plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False}
         and refs['runtime']['sha256']==plan['runtime_manifest_sha256']
         and plan['n26_cohort'].get('limits')==DEV_LIMITS and plan['n26_cohort'].get('worker_audit')==WORKER,
         'plan source/runtime/native/limits')
    rows=plan['episodes'];keys=[x['episode_key'] for x in rows]
    need(len(rows)==len(set(keys))==40 and [(x['task_id'],x['profile']) for x in rows]==[(i,a) for i in range(10) for a in ARMS]
         and all(x['iteration']==COHORT and x['split']=='dev' and x['timeout_seconds']==1800 for x in rows),'40-cell frozen matrix')
    need(pre.get('schema')=='n26-terminal-prerequisite-attestation-v1' and pre.get('source')==refs['source']
         and pre.get('plan')==refs['plan'] and pre.get('runtime')==refs['runtime']
         and pre.get('source_commit')==COMMIT and pre.get('source_files_verified')==315
         and pre.get('operations')==['validate_plan','build_command']
         and pre.get('all_prerequisites_passed') is True and pre.get('model_api_sim_calls')==0
         and pre.get('historical_proof_lineage_verified') is True and is_ref(pre.get('collector'))
         and same_ref(pre.get('source_bridge'),refs['source_bridge'])
         and pre.get('historical_lineage')=={'predecessor':original_review.get('predecessor'),
              'prior_n25_backend_proof':bridge.get('prior_n25_backend_proof'),'prior_quality_proof':bridge.get('prior_backend_proof'),
              'original_n25_disposition':'INVALID_OR_INTERRUPTED','logical_n25_disposition':pre.get('historical_lineage',{}).get('logical_n25_disposition')}
         and pre['historical_lineage']['logical_n25_disposition'] in {'REJECT','REJECT_NUMERIC_FUTILITY'}
         and pre.get('predecessor_current_subset_checked') is True,'root original-plan/source prerequisite attestation')
    templates=pre.get('command_templates',[])
    need(len(templates)==40 and [x.get('episode_key') for x in templates]==keys
         and all(isinstance(x.get('argv'),list) and len(x['argv'])>=2 and all(isinstance(s,str) for s in x['argv'])
                 and x['argv'][1]==str(Path(plan['worktree'])/'main.py') and any(SENTINEL in s for s in x['argv']) for x in templates),'40 original command templates')
    events=file_ref(refs,'journal',reader)
    need(isinstance(events,list) and all(e.get('identity',{}).get('iteration')==COHORT for e in events),'N26-only journal')
    current=projection(file_ref(refs,'current_journal',reader),'n26-current-terminal-journal-projection-v1')
    check_projection_freshness(events,current)
    resource_projection=file_ref(refs,'resources',reader)
    resources=projection(resource_projection,'n26-current-terminal-resource-projection-v1')
    proof,proof_seconds,proof_process=proof_metadata(reader,refs['proof'],source,refs['runtime'],resources)
    need(same_ref(refs['proof'],pre.get('proof')),'precheck proof binding')
    controller=file_ref(refs,'controller',reader);release=file_ref(refs,'release',reader)
    need(controller.get('schema')=='n26-root-controller-process-v1' and controller.get('source_commit')==COMMIT
         and same_ref(controller.get('plan'),refs['plan']) and same_ref(controller.get('release'),refs['release'])
         and controller.get('physical_gpu')==7 and controller.get('one_launch') is True and is_ref(controller.get('wrapper')),'controller identity')
    source_hash={v['path']:v['sha256'] for v in source['files']}
    need(controller.get('entrypoint')=={'path':str(Path(plan['worktree'])/'scripts/qd_ed_n26_supervise.py'),
          'sha256':source_hash['scripts/qd_ed_n26_supervise.py']},'controller source')
    need(release.get('schema')=='n26-dev-execution-release-v1' and release.get('source_commit')==COMMIT
         and same_ref(release.get('plan'),refs['plan']) and release.get('cohort_id')==COHORT and release.get('episode_keys')==keys
         and release.get('physical_gpu')==7 and release.get('authority')==plan['n26_cohort']['authority']
         and release.get('limits')==DEV_LIMITS
         and release.get('validation_authorized') is False and release.get('formal_authorized') is False,'controller release')
    bindings=data['attempts'];ids=[x['attempt_id'] for x in bindings]
    need(len(ids)==len(set(ids))<=42,'duplicate attempt binding')
    lookup={v['attempt_id']:v for v in bindings};groups=OrderedDict();last_id=None;closed_ids=set()
    for e in events:
        aid=e.get('attempt_id');need(aid in lookup and e.get('episode_key') in keys,'unlisted attempt/cell')
        if aid!=last_id:
            need(aid not in closed_ids,'interleaved/repeated attempt group')
            if last_id is not None:closed_ids.add(last_id)
            last_id=aid
        groups.setdefault(aid,[]).append(e)
    need(list(groups)==ids,'attempt inventory order/omitted attempt')
    # The serial controller cannot return to an earlier cell or reserve the next
    # cell before settling the previous attempt. A retry stays at the same index.
    previous_index=-1;previous_end=None
    for group in groups.values():
        index=keys.index(group[0]['episode_key'])
        need(index in {previous_index,previous_index+1} and index>=0
             and (index!=previous_index or group[0].get('retry_of') is not None),
             'global cell order is not a contiguous task-major prefix')
        need(all(number(e.get('time_unix')) for e in group)
             and (previous_end is None or group[0]['time_unix']>=previous_end),'cross-attempt timestamp order')
        previous_index=index;previous_end=group[-1]['time_unix']
    attempts=[];bycell={k:[] for k in keys};processes={'controller':process_identity(controller['process']),
        'proof':process_identity(proof_process)};unsettled=[];dispatch=0
    for aid,group in groups.items():
        first=group[0];key=first['episode_key'];row=rows[keys.index(key)]
        kinds=[e.get('event') for e in group]
        need(kinds in (['reserved'],['reserved','dispatched'],['reserved','aborted'],['reserved','dispatched','valid'],['reserved','dispatched','aborted']),'attempt chronology')
        dispatched='dispatched' in kinds;dispatch+=dispatched
        need(all(e['attempt_id']==aid and e['episode_key']==key and e.get('retry_of')==first.get('retry_of') for e in group),'group association')
        need(all(number(e.get('time_unix')) for e in group) and [e['time_unix'] for e in group]==sorted(e['time_unix'] for e in group),'event timestamps')
        for e in group:terminal_binding(e,row,plan,refs['plan'])
        rr=lookup[aid]['refs']
        expected_output=(Path(plan['artifact_root'])/'attempts'/aid).resolve()
        need(Path(aid).name==aid and all(Path(e['output_dir']).resolve()==expected_output for e in group),'attempt output ownership')
        names={'terminal':'attempt-result.json','context':'n23-worker-context.json','command':'command.json','process':'process.json',
          'audit_start':'eds_eval/in-worker-audit-start.json','receipt':'eds_eval/in-worker-audit-receipt.json',
          'audit':'eds_eval/decision-evidence-audit.json','metrics':'eds_eval/eds_metrics.jsonl','compute':'eds_eval/episode_compute.jsonl'}
        need(set(rr)==set(names) and all(Path(rr[k]['path']).resolve()==expected_output/v for k,v in names.items()),'typed attempt paths')
        # Every declared absence is checked even for the last invalid worker.
        for role in names:
            if rr[role]['sha256'] is None:reader.get(rr[role],role)
        process=file_ref(rr,'process',reader)
        if process is not None:
            need(process.get('attempt_id')==aid,'worker process association');processes[aid]=process_identity(process)
        elif dispatched:
            # A dispatched launch may fail before recording its PID. Preserve the absence,
            # but require a root cleanup attestation; no identity is fabricated.
            processes[aid]=None
        else:processes[aid]=None
        if kinds[-1] not in {'valid','aborted'}:
            unsettled.append(aid);bycell[key].append(group);continue
        final=group[-1];need(file_ref(rr,'terminal',reader)==final,'terminal artifact/journal mismatch')
        if final.get('outcome_valid') is not True:
            partial=reader.get(rr['compute'],'compute')
            if partial is not None:
                need(isinstance(partial,list) and len(partial)==1,'partial compute shape')
                q=partial[0]
                need(q.get('task_id')==row['task_id'] and q.get('episode_seed')==row['env_seed'],'partial compute identity')
                for k in (*COMPUTE,*('provider_'+v for v in TOKENS),*('stage_codex_'+v for v in TOKENS)):
                    if k in final and k in q:need(final[k]==q[k],'partial terminal/compute counter mismatch')
        need(number(final.get('gpu_process_wall_seconds')) and final['gpu_process_wall_seconds']<=1840
             and final.get('n26_episode_dispatched') is dispatched
             and (dispatched or final['gpu_process_wall_seconds']==0),'metered final')
        need(final['budget_bucket']==('recovery' if first.get('retry_of') else row['budget_bucket'])
             and all(e.get('budget_bucket')==final['budget_bucket'] for e in group),'budget bucket')
        attempts.append({'attempt_id':aid,'episode_key':key,'profile':row['profile'],'terminal':final});bycell[key].append(group)
    need(dispatch<=42 and sum(bool(g[0].get('retry_of')) for g in groups.values())<=2,'dispatch/recovery cap')
    accepted=[];native={a:{} for a in ARMS};aux={a:{} for a in ARMS};failure=None
    for row in rows:
        own=bycell[row['episode_key']]
        if not own:break
        need(len(own)<=2 and own[0][0].get('retry_of') is None,'primary/recovery count')
        first=own[0][-1];final=first
        try:
            need(first['event'] in {'valid','aborted'},'unsettled primary')
            if len(own)==2:
                second=own[1];final=second[-1]
                need([e['event'] for e in own[0]]==[e['event'] for e in second]==['reserved','dispatched','valid']
                     and first.get('outcome_valid') is False and final.get('retry_of')==first['attempt_id'],'first-valid recovery chronology')
                rb=lookup[final['attempt_id']]
                recovery_metadata(reader,rb,lookup[first['attempt_id']],first,final,row,plan,refs,source)
                need(all(same_ref(e.get('n26_recovery_eligibility'),rb['eligibility']) for e in second),'recovery group eligibility')
                audit_metadata(reader,lookup[first['attempt_id']],first,row,plan,source,runtime,refs,pre)
            need(final['event']=='valid' and final.get('outcome_valid') is True
                 and final.get('required_cost_telemetry_complete') is True and type(final.get('success')) is bool,'no valid scientific result')
            counts,extra=audit_metadata(reader,lookup[final['attempt_id']],final,row,plan,source,runtime,refs,pre)
        except (MetadataError,KeyError,TypeError,ValueError) as exc:
            failure={'episode_key':row['episode_key'],'independent_reason':str(exc),'failure_class':type(exc).__name__};break
        rr=lookup[final['attempt_id']]['refs']
        accepted.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'attempt_id':final['attempt_id'],
                         'success':final['success'],'audit':rr['audit'],'worker_context':rr['context'],'worker_receipt':rr['receipt'],'attempt_result':rr['terminal']})
        for k,v in counts.items():native[row['profile']][k]=native[row['profile']].get(k,0)+v
        for k,v in extra.items():aux[row['profile']][k]=aux[row['profile']].get(k,0)+v
        if len(accepted)%4==0:
            wins_so_far=sum(v['profile']=='N26' and v['success'] for v in accepted)
            if wins_so_far+10-len(accepted)//4<5:
                need(not any(keys.index(e['episode_key'])>=len(accepted) for e in events),
                     'dispatch/reservation after first complete-quad numeric futility')
    prefix=[v['episode_key'] for v in accepted]
    allowed=set(prefix)|({keys[len(prefix)]} if len(prefix)<40 else set())
    need(all(e['episode_key'] in allowed for e in events),'later attempted cells after invalid/gap')
    counts={a:{'audited':sum(v['profile']==a for v in accepted),'success':sum(v['profile']==a and v['success'] for v in accepted)} for a in ARMS}
    wins=counts['N26']['success'];substantive=native['N26'].get('guided_decisions',0)>0 and native['N26'].get('parent_rounds_verified',0)>0
    promoted=len(accepted)==40 and wins>=5 and wins>=max(counts[a]['success'] for a in ARMS[:-1]) and substantive
    futility=len(accepted)%4==0 and wins+10-len(accepted)//4<5
    raw=('ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promoted else 'REJECT' if len(accepted)==40
         else 'REJECT_NUMERIC_FUTILITY' if futility and failure is None and not unsettled else 'INVALID_OR_INTERRUPTED')
    status=file_ref(refs,'status',reader);result=file_ref(refs,'result',reader)
    status=status or {'status':'unavailable','failure_class':'FileNotFoundError'}
    phase=status.get('status')
    consistent=status.get('completed_keys')==prefix and status.get('dev_gate_promoted') is promoted
    consistent=consistent and ((phase=='rejected_numeric_futility' and raw=='REJECT_NUMERIC_FUTILITY')
       or (phase=='completed_all_forty_audited' and len(accepted)==40)
       or (phase in {'failed','interrupted'} and raw=='INVALID_OR_INTERRUPTED'))
    decision=raw if consistent else 'INVALID_OR_INTERRUPTED'
    costs=summary(accepted,attempts)
    visible={'schema':'n26-dev-cohort-result-v1','cohort_id':COHORT,'source_commit':COMMIT,'planned':40,
      'dispatched':dispatch,'audited_cells':len(accepted),'counts':counts,'accepted_cells':accepted,
      'attempts':attempts,'native':native,'auxiliary':aux,'dev_gate_promoted':promoted if consistent else False,
      'decision':decision,'goal_status':'TARGET_NOT_MET','validation_authorized':False,'formal_authorized':False,**costs}
    discrepancies=[]
    if result is not None:
        for k,v in visible.items():
            if result.get(k)!=v:discrepancies.append(k)
        ce={'completed_keys':status.get('completed_keys'),'journal_accepted_keys':prefix,'consistent':consistent,'status_phase':phase}
        if not consistent:
            ce['disagreement']='Controller status and independently reconstructed journal differ; no resume or promotion.'
            if result.get('journal_reconstructed_disposition')!=raw:discrepancies.append('journal_reconstructed_disposition')
        if result.get('controller_evidence')!=ce:discrepancies.append('controller_evidence')
        for k,expected in (('plan',refs['plan']),('ledger_snapshot',refs['journal']),('source_bridge',pre['source_bridge'])):
            if not same_ref(result.get(k),expected):discrepancies.append(k)
        sr={'path':str(Path(plan['worktree'])/'scripts/qd_ed_n26_report.py'),'sha256':source_hash['scripts/qd_ed_n26_report.py']}
        if not same_ref(result.get('reader'),sr):discrepancies.append('reader')
        t=result.get('terminal_status',{})
        if not (t.get('content')==status and t.get('path')==refs['status']['path'] and t.get('sha256')==refs['status']['sha256']):discrepancies.append('terminal_status')
        rf=result.get('failure')
        # Free-form old exception text is retained, never invented as independent causality.
        if failure is None:
            if rf is not None:discrepancies.append('failure')
        elif not (isinstance(rf,dict) and rf.get('episode_key')==failure['episode_key']
                  and isinstance(rf.get('reason'),str) and isinstance(rf.get('failure_class'),str)):discrepancies.append('failure')
    else:discrepancies.append('missing_immutable_result')
    # For complete scientific dispositions the status must reconstruct in full.
    outcomes=[{k:v[k] for k in ('episode_key','task_id','profile','success','attempt_id')}|{'recovered':bool(next(a['terminal'].get('retry_of') for a in attempts if a['attempt_id']==v['attempt_id']))} for v in accepted]
    if decision!='INVALID_OR_INTERRUPTED':
        expected={'schema':'n26-dev-supervisor-status-v1','cohort_id':COHORT,'source_commit':COMMIT,'plan':refs['plan'],
          'attempts':attempts,'outcomes':outcomes,'successes':{a:counts[a]['success'] for a in ARMS},
          'native':native,'auxiliary':aux,'protected_authorized':False,**costs}
        discrepancies += ['status.'+k for k,v in expected.items() if status.get(k)!=v]
    else:
        # A shorter status prefix is evidence of the original interruption, not lost costs.
        sk=status.get('completed_keys',[])
        need(isinstance(sk,list) and sk==prefix[:len(sk)],'invalid status invented/reordered accepted cells')
    cleanup=file_ref(refs,'cleanup_attestation',reader)
    need(cleanup.get('schema')=='n26-terminal-cleanup-attestation-v1' and cleanup.get('plan')==refs['plan']
         and cleanup.get('controller')==refs['controller'] and cleanup.get('current_journal')==refs['current_journal']
         and cleanup.get('resources')==refs['resources'] and cleanup.get('expected_processes')==processes
         and is_ref(cleanup.get('collector')) and cleanup.get('all_owned_processes_inspected') is True,'root cleanup provenance')
    if unsettled:discrepancies.append('unsettled_attempt_costs')
    result_decision='ACCEPT_TERMINAL_RECONSTRUCTION' if not discrepancies else 'REJECT_TERMINAL_RECONSTRUCTION'
    return {'schema':'n26-root-terminal-review-v1','decision':result_decision,'cohort_disposition':decision,
      'accepted_cells':len(accepted),'counts':counts,'native':native,'auxiliary':aux,'all_attempts':attempts,**costs,
      'all_episode_gpu_process_seconds':sum(a['terminal']['gpu_process_wall_seconds'] for a in attempts),
      'tensor_resource_gpu_process_seconds':proof_seconds,'source':refs['source'],'plan':refs['plan'],'result':refs['result'],
      'status':refs['status'],'journal':refs['journal'],'current_journal':refs['current_journal'],'controller':refs['controller'],
      'proof':refs['proof'],'prerequisite_attestation':refs['precheck'],'cleanup_attestation':refs['cleanup_attestation'],
      'expected_processes':processes,'discrepancies':discrepancies,'independent_invalid_evidence':failure,
      'unsettled_attempts':unsettled,'unsettled_gpu_costs':'Unknown' if unsettled else None,
      'status_attempts_not_returned':[a['attempt_id'] for a in attempts if a['attempt_id'] not in {x.get('attempt_id') for x in status.get('attempts',[])}],
      'historical_trust':'Original same-process tensor audit and frozen timeout classifier are attested, not replayed; nested payload refs never followed.',
      'next_gpu_execution_authorized':False,'validation_authorized':False,'formal_authorized':False,
      'metadata_files_read':len(reader.cache),'metadata_distinct_bytes_read':reader.bytes_read}

def inspect_cleanup(processes,worktree):
    """Public /proc metadata only, no signals; include reparented session children."""
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    table={};owned=[]
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():continue
        try:
            fields=(directory/'stat').read_text().rsplit(')',1)[1].split()
            pid=int(directory.name);table[pid]={'ppid':int(fields[1]),'pgrp':int(fields[2]),'session':int(fields[3]),'ticks':fields[19]}
            command=(directory/'cmdline').read_bytes()
            if str(Path(worktree).resolve()).encode() in command and any(x in command for x in
                (b'qd_ed_n23_worker.py',b'qd_ed_n26_supervise.py',b'qd_ed_n26_preflight.py')):
                owned.append(pid)
        except (OSError,IndexError,ValueError):continue  # A process may exit during enumeration.
    observed={}
    for key,identity in processes.items():
        if identity is None:
            observed[key]={'identity':None,'original_process_record':'verified_absent','same_identity_alive':None,
                           'owned_descendants':None,'identity_history':'Unknown'}
            continue
        pid=identity['pid'];sameboot=identity['boot_id']==boot
        same=sameboot and pid in table and table[pid]['ticks']==identity['proc_start_ticks']
        descendants=[p for p,v in table.items() if sameboot and p!=os.getpid() and
                     (v['ppid']==pid or (key!='controller' and (v['pgrp']==pid or v['session']==pid)))]
        need(not same and not descendants,'owned process/descendant still live')
        observed[key]={'identity':identity,'same_identity_alive':False,'owned_descendants':[],
                       'boot_relation':'same' if sameboot else 'different'}
    need(not owned,'owned worktree controller/worker/preflight still live')
    return {'schema':'n26-independent-process-cleanup-v1','boot_id':boot,'observed_at':time.time(),
            'owned_worktree_processes':[],'observations':observed,'signals_sent':False,
            'all_historical_process_identities_verified':all(x is not None for x in processes.values()),
            'unknown_process_identities':[k for k,v in processes.items() if v is None],
            'downstream_cleanup_gate_satisfied':all(x is not None for x in processes.values()),
            'limitation':'Missing PID/start/boot history remains Unknown and cannot authorize downstream dispatch; the current owned-command scan is auxiliary only.'}

def verify_static(data,source):
    root=Path(data['source_root']).resolve()
    for item in source['files']:
        p=root/item['path']
        need(p.resolve().is_relative_to(root) and p.is_file() and not p.is_symlink(),'static source ownership')
        need(digest(load_bound(p))==item['sha256'],'actual frozen source bytes drift')
    objects=data.get('static_objects',[])
    need(isinstance(objects,list) and len(objects)<=32,'external static count')
    for q in objects:
        need(set(q)=={'path','sha256'} and Path(q['path']).suffix=='.py' and is_ref(q),'external static shape')
        need(digest(load_bound(q['path'],512*1024))==q['sha256'],'external static reader/collector drift')
    need(len({str(Path(x['path']).resolve()) for x in objects})==len(objects),'duplicate external source')
    for name in ('terminal_reader_v1.py','bounded_metadata_v1.py','metadata_semantics_v1.py'):
        need(any(same_ref(x,ref(Path(__file__).parent/name)) for x in objects),'external reader source closure')
    return root

def check_fresh_stat(projections):
    # Root-attested subset extraction is refreshed under the normal lock. Stat
    # anchors close the extraction-to-read race without opening full private journals.
    for q in projections:
        anchor=q.get('source_ledger_stat');need(isinstance(anchor,dict) and set(anchor)=={'size','mtime_ns','inode'},'current projection stat anchor')
        p=Path(q['source_ledger']['path']);s=p.stat()
        need(anchor=={'size':s.st_size,'mtime_ns':s.st_mtime_ns,'inode':s.st_ino},'source journal appended/changed; root must refresh subset')
def external_sources(reader,refs,data):
    allowed=data['static_objects']
    for role in ('precheck','current_journal','resources','cleanup_attestation'):
        value=reader.get(refs[role],role)
        need(any(same_ref(value.get('collector'),x) for x in allowed),'collector outside static scope')
    controller=reader.get(refs['controller'],'controller')
    need(any(same_ref(controller.get('wrapper'),x) for x in allowed),'wrapper outside static scope')
    for row in data['attempts']:
        if row.get('recovery_attestation'):
            value=reader.get(row['recovery_attestation'],'recovery_attestation')
            need(any(same_ref(value.get('collector'),x) for x in allowed),'recovery collector outside static scope')
def run_cli(input_path,output):
    data=decode(load_bound(input_path));need(data.get('root_authorized') is True and data.get('executable') is True,'disabled inventory')
    reader=Reader(data['files']);refs=data['refs'];source=reader.get(refs['source'],'source')
    root=verify_static(data,source);plan=reader.get(refs['plan'],'plan')
    need(root==Path(plan['worktree']).resolve() and root.name=='study_worktree','approved owning study only')
    n26=root.parent/'variants/n26_clean_output_rbf'
    need(Path(output).resolve()==(n26/'root-terminal-review-v1.json').resolve(),'fixed external root-review path')
    need(not Path(output).exists(),'immutable review already exists')
    with ExitStack() as stack:
        for path in (n26/'execution/supervisor.lock',root/'data/qd-ed-runner.lock'):
            need(path.is_file(),'existing operational lock required')
            stream=stack.enter_context(path.open('r+'))
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        external_sources(reader,refs,data)
        projections=[reader.get(refs[k],k) for k in ('current_journal','resources')]
        check_fresh_stat(projections)
        result=reconstruct(data,reader)
        cleanup=inspect_cleanup(result['expected_processes'],root)
        check_fresh_stat(projections)
        verify_static(data,source)
        result.update(cleanup=cleanup,reader=ref(__file__),reader_dependencies=[ref(Path(__file__).parent/x) for x in
             ('bounded_metadata_v1.py','metadata_semantics_v1.py')],input_manifest=ref(input_path))
        result['metadata_files_read']=len(reader.cache);result['metadata_distinct_bytes_read']=reader.bytes_read
        with Path(output).open('x') as f:
            json.dump(result,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:
        result=run_cli(args.input,args.output)
        print(json.dumps({k:result[k] for k in ('decision','cohort_disposition','accepted_cells','next_gpu_execution_authorized')}))
        return 0 if result['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION' else 1
    except (MetadataError,OSError,KeyError,TypeError,ValueError) as exc:
        print(json.dumps({'decision':'REJECT_TERMINAL_RECONSTRUCTION','failure_class':type(exc).__name__,
                          'reason':str(exc),'next_gpu_execution_authorized':False}))
        return 1
if __name__=='__main__':raise SystemExit(main())


