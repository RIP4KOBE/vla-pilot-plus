"""Root metadata-only terminal review. No simulation, CUDA, tensors, or API calls."""
import collections,datetime,hashlib,json,os,pathlib,resource,signal,time
N=pathlib.Path("/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n28_parent_before_renoise")
W=pathlib.Path("/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree")
ARMS=('C0','Q0','N27','N28')
COHORT='N28_PARENT_BEFORE_RENOISE_SCREEN_20261001'
START=time.process_time()
signal.alarm(60)
def require(condition,message):
    if not condition:raise RuntimeError(message)
def read(p):
    p=pathlib.Path(p)
    require(p.stat().st_size<32*1024*1024,'metadata input exceeds32MiB')
    return json.loads(p.read_text())
def rows(p):
    p=pathlib.Path(p)
    require(p.stat().st_size<64*1024*1024,'journal input exceeds64MiB')
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def ref(p):
    p=pathlib.Path(p)
    return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def verify_ref(r):
    require(ref(r['path'])['sha256']==r['sha256'],'reference mismatch:'+r['path'])
def original_alive(r):
    pid=r['pid'];p=pathlib.Path('/proc')/str(pid)/'stat'
    if not p.exists():return False
    return (p.read_text().split(') ',1)[1].split()[19]==str(r.get('start_ticks',r.get('proc_start_ticks')))
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==r['boot_id'])
plan=read(N/'plan.frozen.v1.gpu7.json')
result=read(N/'result-v1.json')
status=read(N/'execution/supervisor-status-v1.json')
controller=read(N/'execution/controller-process-v1.json')
require(not original_alive(controller),'original controller still alive')
require(result['source_commit']==plan['source_commit']=="52b9eb0a8a365ee2ea12daffdb7a98c76bec0a72",'source commit differs')
manifest=read(N/'source-manifest-execution-v1.json')
for entry in manifest['files']:
    require(ref(W/entry['path'])['sha256']==entry['sha256'],'live source differs:'+entry['path'])
require(len(manifest['files'])==383,'source count differs')
events=[e for e in rows(W/'data/attempt-ledger.jsonl') if e.get('identity',{}).get('iteration')==COHORT]
groups={}
for e in events:groups.setdefault(e['attempt_id'],[]).append(e)
ordered=list(groups.values())
expected=[e['episode_key'] for e in plan['episodes']]
require(len(ordered)<=16 and [g[0]['episode_key'] for g in ordered]==expected[:len(ordered)],'journal prefix differs')
require(events==[e for g in ordered for e in g],'interleaved local attempts')
require(not any(e.get('retry_of') for e in events),'retry observed')
accepted=[];invalid=[];observed_calls=0;observed_failed=0;observed_tokens=collections.Counter()
unknown_attempts=[];cost_seconds=0.;dispatches=0;stage_bindings=collections.Counter()
closed=[];all_refs=0;native={a:collections.Counter() for a in ARMS};auxiliary={a:collections.Counter() for a in ARMS}
results_by_id={a['attempt_id']:a['terminal'] for a in result['attempts']}
for group in ordered:
    order=[e['event'] for e in group]
    require(order in (['reserved','dispatched','valid'],['reserved','dispatched','aborted'],['reserved','aborted']),'unsettled journal')
    e=group[-1];aid=e['attempt_id'];d=pathlib.Path(e['output_dir'])
    require(d.resolve().parent==(N/'artifacts/attempts').resolve(),'attempt output escapes N28')
    require(results_by_id.get(aid)==e,'terminal result differs from original journal')
    dispatches+=sum(x['event']=='dispatched' for x in group)
    if (d/'process.json').exists():
        proc=read(d/'process.json');require(not original_alive(proc),'original worker still alive:'+aid);closed.append(aid)
    wall=e.get('gpu_process_wall_seconds')
    if isinstance(wall,(float,int)):cost_seconds+=wall
    else:unknown_attempts.append(aid)
    if e.get('outcome_valid') is not True:
        invalid.append({'attempt_id':aid,'episode_key':e['episode_key'],'event':e['event']})
        continue
    require(e['event']=='valid' and type(e['success']) is bool,'valid outcome malformed')
    stages=[x for x in rows(d/'eds_eval/stage_events.jsonl') if x.get('query_status')!='skipped']
    require(len(stages)==e['provider_logical_call_attempts'],'Stage call reconciliation differs')
    totals=collections.Counter()
    for x in stages:
        t=x['transport'];require(t.get('backend')=='codex_cli' and t.get('auth_mode')=='chatgpt' and t.get('model')=='gpt-6-astra','provider binding differs')
        require(t.get('public_config_sha256')==e['stage_transport']['public_config_sha256'],'Stage public policy hash differs')
        require(x.get('query_status')=='ok' and x.get('query_ok') is True,'valid cell has failed Stage')
        require(x.get('api_request_attempts') is None and x.get('api_sdk_retry_attempts') is None,'HTTP unknown counters imputed')
        require(x.get('codex_logical_call_attempts')==1 and x.get('codex_usage_complete_calls')==1,'logical/usage event counter differs')
        stage_bindings[(t['backend'],t['auth_mode'],t['model'])]+=1
        for k in ('input_tokens','output_tokens','cached_input_tokens'):totals[k]+=x['codex_'+k]
    for k,v in totals.items():require(e['provider_'+k]==v,'token reconciliation differs')
    observed_calls+=len(stages);observed_failed+=e['provider_failed_calls'];observed_tokens.update(totals)
    require(e['provider_failed_calls']==0,'valid provider failed')
    for k in ('guidance_api_request_attempts','grounding_api_request_attempts','guidance_api_sdk_retry_attempts','grounding_api_sdk_retry_attempts'):
        require(e[k]==0,'additional guidance/grounding API observed')
    candidates=[x for x in result['accepted_cells'] if x['attempt_id']==aid]
    if not candidates:
        require(result.get('failure') is not None,'valid journal missing accepted cell without reported failure')
        invalid.append({'attempt_id':aid,'episode_key':e['episode_key'],'event':e['event'],'native_acceptance_failed':True,'reported_failure':result['failure']})
        continue
    require(len(candidates)==1,'duplicate accepted cell')
    cell=candidates[0];accepted.append(e)
    require(cell['success']==e['success'] and cell['episode_key']==e['episode_key'],'accepted cell differs')
    for k in ('audit','worker_context','worker_receipt','attempt_result'):
        verify_ref(cell[k]);all_refs+=1
    receipt=read(cell['worker_receipt']['path']);arm=e['identity']['profile']
    require(receipt['accepted'] is True and receipt['process_unchanged'] is True and receipt['main_exit_code']==0,'worker receipt did not accept')
    require(receipt['attempt_id']==aid and receipt['profile']==arm,'worker receipt identity differs')
    require(receipt['worker_cuda']['physical_gpu']==7 and receipt['worker_cuda']['uuid']=='GPU-48473162-9548-1a19-04aa-ea86c5349187','worker device differs')
    require(receipt['audit_backend']['kind']==('cuda' if arm in ('N27','N28') else 'cpu'),'receipt audit backend differs')
    native[arm].update(receipt['n28_native_counts']);auxiliary[arm].update(receipt['n28_auxiliary'])
require(dispatches==result['dispatched'],'dispatch denominator differs')
require(len(accepted)==result['audited_cells'],'accepted denominator differs')
require([e['episode_key'] for e in accepted]==status['completed_keys'],'supervisor accepted prefix differs')
counts={a:{'audited':sum(e['identity']['profile']==a for e in accepted),'success':sum(e['identity']['profile']==a and e['success'] for e in accepted)} for a in ARMS}
require(counts==result['counts'],'success denominator differs')
require({a:dict(v) for a,v in native.items()}==result['native'],'native same-worker receipt aggregate differs')
require({a:dict(v) for a,v in auxiliary.items()}==result['auxiliary'],'auxiliary same-worker receipt aggregate differs')
proof=read(N/'arithmetic-preflight/proof-v1.json')
proof_review=read(N/'root-native-proof-review-v1.json')
prelaunch=read(N/'root-final-prelaunch-review-v1.json')
verify_ref(prelaunch['native_review'])
verify_ref(proof['terminal'])
proof_seconds=read(proof['terminal']['path'])['gpu_process_wall_seconds']
require((cost_seconds+proof_seconds)/3600<=8.25,'episode-plus-proof local cap exceeded')
complete=len(accepted)==16 and not invalid
gate=(complete and counts['N28']['success']>=2 and counts['N28']['success']>=max(counts[a]['success'] for a in ARMS[:-1]) and counts['N28']['success']>counts['N27']['success']
      and result['native']['N28'].get('guided_decisions',0)>0 and result['native']['N28'].get('parent_rounds_verified',0)>0)
decision='ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV' if gate else 'REJECT_SCREEN' if complete else 'INVALID_OR_INTERRUPTED'
require(decision==result['decision'] and gate==result['dev_gate_promoted'],'independent gate differs')
require(result['validation_authorized'] is False and result['formal_authorized'] is False and result['goal_status']=='TARGET_NOT_MET','protected/goal assertion differs')
out={'schema':'n28-root-terminal-review-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
     'review_type':'independent original-journal, metadata, provider-event and process reconciliation; no tensor replay',
     'decision':decision,'result':ref(N/'result-v1.json'),'plan':ref(N/'plan.frozen.v1.gpu7.json'),
     'source_commit':plan['source_commit'],'source_files_rehashed':len(manifest['files']),
     'journal_events':len(events),'dispatched':dispatches,'audited_cells':len(accepted),'counts':counts,
     'invalid_attempts':invalid,'artifact_references_rehashed':all_refs,
     'native_counts':{a:dict(v) for a,v in native.items()},'native_audit_interpretation':'original same-worker CUDA receipts for candidates; root performed metadata reconciliation only',
     'controller_original_process_exited':True,'worker_original_processes_exited':closed,
     'observed_valid_stage_logical_calls':observed_calls,'observed_valid_stage_failed_calls':observed_failed,
     'stage_bindings':[{'backend':k[0],'auth_mode':k[1],'model':k[2],'calls':v} for k,v in stage_bindings.items()],
     'observed_valid_tokens':dict(observed_tokens),'http_requests':None,'http_retries':None,
     'episode_gpu_seconds_observed':cost_seconds,'proof_gpu_seconds':proof_seconds,'local_gpu_hours_observed':(cost_seconds+proof_seconds)/3600,'gpu_cost_unknown_attempts':unknown_attempts,
     'native_proof_review':ref(N/'root-native-proof-review-v1.json'),
     'poe_allowed':False,'alternate_account_fallback_allowed':False,'protected_authorized':False,
     'goal_status':'TARGET_NOT_MET','cpu_seconds':time.process_time()-START,'reader_max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
with (N/'root-terminal-review-v1.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({k:out[k] for k in ('decision','counts','dispatched','audited_cells','observed_valid_stage_logical_calls','cpu_seconds')},ensure_ascii=False))

