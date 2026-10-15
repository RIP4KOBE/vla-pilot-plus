"""One-pass, exact-path N29 closed metadata diagnostic; never decodes tensor bundles."""
import os,sys,json,hashlib,time,resource,math,statistics,collections,csv,io
from pathlib import Path
H=Path(__file__).resolve().parent;V=H.parent
os.sched_setaffinity(0,{0,1});assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(220,225))
START=time.monotonic();CPU=time.process_time();READ=0;DENIED=[];READS=[];ROWS=[];DETAIL=[];NEXT=[];ERROR=None
scope=json.loads((H/'input-scope.frozen.v1.json').read_text());control=json.loads((H/'control-input-inventory-v1.json').read_text())
ALLOW={str(Path(x['path']).resolve()) for a in scope['attempts'] for x in a['files'] if x['present']}
ALLOW|={str(Path(x['path']).resolve()) for x in control['references']}
ALLOW|={str((H/'input-scope.frozen.v1.json').resolve()),str((H/'control-input-inventory-v1.json').resolve())}
PYROOT=Path(sys.prefix).resolve()
def inside(p,root):return p==root or root in p.parents
def guard(event,args):
 if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn','socket.connect','socket.bind','socket.getaddrinfo'):
  DENIED.append({'event':event});raise RuntimeError('forbidden operation '+event)
 if event=='import' and str(args[0]).split('.')[0] in {'torch','numpy','PIL','cv2','openai','requests','httpx'}:
  DENIED.append({'import':str(args[0])});raise RuntimeError('forbidden import')
 if event=='open' and not isinstance(args[0],int):
  p=Path(os.fsdecode(args[0])).absolute().resolve();mode=args[1];flags=args[2] or 0
  writing=(isinstance(mode,str) and any(x in mode for x in 'wa+')) or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  ok=inside(p,H) if writing else str(p) in ALLOW or inside(p,H) or inside(p,PYROOT)
  if p.suffix.lower() in {'.pt','.npz','.npy','.png','.jpg','.jpeg','.mp4','.gif','.safetensors','.bin'}:ok=False
  if not ok:DENIED.append({'path':str(p),'writing':writing});raise RuntimeError('metadata guard rejected '+str(p))
sys.addaudithook(guard)
def load(role):
 global READ
 p=Path(role['path']);size=p.stat().st_size
 assert role.get('present',True) and size==role.get('stat_bytes',role.get('bytes',size)) and size<=128*1024**2
 digest=hashlib.sha256();n=0;out=[]
 with p.open('rb') as f:
  if p.suffix=='.jsonl':
   for line in f:
    n+=len(line);READ+=len(line);assert READ<=1024**3
    digest.update(line)
    if line.strip():out.append(json.loads(line))
  else:
   raw=f.read(128*1024**2+1);n=len(raw);READ+=n;assert READ<=1024**3 and n<=128*1024**2;digest.update(raw);out=json.loads(raw)
 assert n==size
 actual=digest.hexdigest()
 if role.get('sha256') is not None:assert actual==role['sha256']
 READS.append({'role':role.get('role'),'path':str(p),'bytes':n,'sha256':actual,'read_count':1})
 return out

def finite(v):return type(v) in (int,float) and math.isfinite(v)
def stats(values):
 x=sorted(float(v) for v in values if finite(v));n=len(x)
 return {'available':n,'unavailable':len(values)-n,'mean':sum(x)/n if n else None,'median':statistics.median(x) if n else None,'p90':x[max(0,math.ceil(.9*n)-1)] if n else None,'min':x[0] if n else None,'max':x[-1] if n else None,'exact_zero':sum(v==0 for v in x)}
def category(v):
 if not isinstance(v,str):return 'Unavailable'
 for prefix,label in [('gripper closed','gripper_closed'),('gripper opened','gripper_opened'),('reward rose','reward_rose'),('reward dropped','reward_dropped')]:
  if v.startswith(prefix):return label
 return 'other_trigger'
def longest(bits):
 run=best=0
 for bit in bits:
  run=run+1 if bit else 0;best=max(best,run)
 return best
METRIC_KEYS=('global_step','episode','task_id','guidance_type','reward_mode','chunk_population_mode','selected_chunk_population_source','selected_parent_source',
 'chunk_memory_available','chunk_memory_used','chunk_memory_candidate_count','chunk_memory_fraction_observed','chunk_memory_reset_reason','chunk_memory_acceptance_ratio',
 'chunk_to_chunk_selected_trajectory_distance','chunk_boundary_action_jump','target_distance_before','target_distance_after',
 'initial_best_reward','final_best_reward','initial_mean_reward','final_mean_reward','reward_spread','selected_reward','selected_cost','selected_idx',
 'score_entropy','search_evaluation_count','score_call_count','resample_count','renoise_count','rollout_count','eds_iters_executed','early_stop_used','early_stop_reason',
 'execution_horizon_resolved','execution_horizon_reason','execution_horizon_stage_change','replan_count','qd_final_selection_mode')
STAGE_KEYS=('episode_id','task_id','global_step','chunk_id','episode_seed','stage_before','stage_after','guidance_before','guidance_after','vlm_query_count','vlm_query_limit',
 'query_status','query_ok','skipped_reason','query_latency_s','api_request_attempts','api_sdk_retry_attempts','codex_logical_call_attempts','codex_completed_turns','codex_failed_calls','codex_usage_complete_calls','codex_input_tokens','codex_output_tokens','codex_cached_input_tokens','codex_reasoning_output_tokens','codex_call_latency_s')
COMPUTE_KEYS=('guided_chunks','unguided_chunks','rbf_gradient_calls','rbf_gradient_batch_rows','model_forward_calls','model_batch_rows','reward_calls','reward_evaluations','reward_scoring_batches','denoising_invocations','renoise_invocations','actual_steps','environment_steps','policy_counters_available')

def audit_attempt(entry,cell,item):
 files={x['role']:x for x in entry['files']};term=load(files['terminal'])
 assert term==item['terminal'] and term['attempt_id']==cell['attempt_id']==entry['attempt_id'] and term['source_commit']==scope['source_commit']
 assert term['outcome_valid'] is True and term['required_cost_telemetry_complete'] is True and term['identity']['task_id']==entry['task_id'] and term['identity']['profile']==entry['profile']
 metrics=[]
 if files['metrics']['present']:
  raw=load(files['metrics'])
  for m in raw:
   row={k:m.get(k) if type(m.get(k)) in (int,float,str,bool,type(None)) else None for k in METRIC_KEYS}
   row['chunk_memory_source_counts']={k:v for k,v in m.get('chunk_memory_source_counts',{}).items() if k in {'fresh','memory'} and type(v) is int}
   row['archive_reference_projected_distance_after']=m.get('qd_archive_reference',{}).get('target_distance_after')
   row['field_presence']={k:k in m for k in METRIC_KEYS}
   metrics.append(row)
  del raw
 stages=[]
 if files['stage']['present']:
  raw=load(files['stage'])
  for s in raw:
   row={k:s.get(k) if type(s.get(k)) in (int,float,str,bool,type(None)) else None for k in STAGE_KEYS}
   row['trigger_category']=category(s.get('trigger_reason'))
   tr=s.get('transport');row['transport']={k:tr.get(k) for k in ('backend','auth_mode','model','reasoning_effort') if isinstance(tr,dict) and type(tr.get(k)) in (str,type(None))}
   stages.append(row)
  del raw
 raw=load(files['compute']) if files['compute']['present'] else []
 compute={k:raw[-1].get(k) for k in COMPUTE_KEYS if type(raw[-1].get(k)) in (int,float,bool,type(None))} if raw else {}
 compute_keys=list(raw[-1]) if raw else [];del raw
 audit=load(files['audit']);audit_info={'accepted':audit.get('accepted'),'evidence_complete':audit.get('evidence_complete'),'observed_counts':{k:v for k,v in audit.get('observed_counts',{}).items() if type(v) is int}}
 assert audit_info['accepted'] is True and audit_info['evidence_complete'] is True;del audit
 status=load(files['status']);status_info={k:status.get(k) for k in ('schema','episode','complete','failed','decisions','committed_decisions','pending_action','bundles')}
 assert status_info['complete'] is True and status_info['failed'] is False
 indices=load(files['events']);decisions=[];categories=collections.Counter();bydecision=collections.defaultdict(list);bundle_map={};all_events=[]
 for idx in indices:
  assert set(idx)=={'bundle','sha256','first_sequence','last_sequence','events'} and Path(idx['bundle']).name==idx['bundle'] and idx['bundle'].endswith('.pt')
  for e in idx['events']:
   assert set(e)=={'sequence','event','decision_id','global_step','reset_sequence'}
   categories[e['event']]+=1;all_events.append((e,idx));bydecision[e['decision_id']].append((e,idx))
   if e['event']=='decision_context':decisions.append({'decision_id':e['decision_id'],'step':e['global_step'],'reset_sequence':e['reset_sequence']})
  bundle_map[idx['bundle']]=idx
 assert len(decisions)==status_info['decisions'] and len(indices)==status_info['bundles']
 guided_steps={m['global_step'] for m in metrics};actual_guided=term['guided_chunks'];actual_unguided=term['unguided_chunks']
 assert len(metrics)==actual_guided and len(decisions)==actual_guided+actual_unguided
 # Stage is a carried recognizer state at decision boundaries, never physical grasp truth.
 initial_stage=stages[0]['stage_before'] if stages else 1
 initial_guidance=stages[0]['guidance_before'] if stages else None
 timeline=[];stage=initial_stage;guidance=initial_guidance;j=0
 ordered=sorted(stages,key=lambda x:x['global_step'] if type(x['global_step']) is int else -1)
 assert all(type(s['global_step']) is int for s in ordered)
 for d in decisions:
  while j<len(ordered) and ordered[j]['global_step']<=d['step']:
   stage=ordered[j]['stage_after'];guidance=ordered[j]['guidance_after'];j+=1
  timeline.append({**d,'recognizer_stage_carried':stage,'recognizer_guidance_carried':guidance,'guided_search_observed':d['step'] in guided_steps})
 bystep={d['step']:d for d in timeline}
 for m in metrics:m['recognizer_stage_carried']=bystep.get(m['global_step'],{}).get('recognizer_stage_carried')
 jumps=[m['chunk_boundary_action_jump'] for m in metrics]
 stcounts=collections.Counter(str(d['recognizer_stage_carried']) for d in timeline)
 memory={k:dict(collections.Counter(str(m.get(k)) for m in metrics)) for k in ('chunk_population_mode','chunk_memory_available','chunk_memory_used','chunk_memory_candidate_count','chunk_memory_reset_reason','selected_chunk_population_source','selected_parent_source')}
 row={'task_id':entry['task_id'],'arm':entry['profile'],'attempt_id':entry['attempt_id'],'success':term['success'],'decisions':len(decisions),'guided_chunks':actual_guided,'unguided_chunks':actual_unguided,
  'first_guided_step':min(guided_steps) if guided_steps else None,'last_guided_step':max(guided_steps) if guided_steps else None,'longest_consecutive_guided_decisions':longest([d['guided_search_observed'] for d in timeline]),
  'guidance_state_switches':sum(a['recognizer_guidance_carried']!=b['recognizer_guidance_carried'] for a,b in zip(timeline,timeline[1:]) if a['recognizer_guidance_carried'] is not None and b['recognizer_guidance_carried'] is not None),
  'stage_occupancy_decisions':dict(stcounts),'stage_transitions':sum(a['recognizer_stage_carried']!=b['recognizer_stage_carried'] for a,b in zip(timeline,timeline[1:])),
  'query_events':len(stages),'query_ok':sum(s['query_ok'] is True for s in stages),'query_failed':sum(s['query_ok'] is False for s in stages),'trigger_categories':dict(collections.Counter(s['trigger_category'] for s in stages)),
  'metric_rows':len(metrics),'metrics_present':files['metrics']['present'],'command_jump':stats(jumps),'selected_trajectory_distance':stats([m['chunk_to_chunk_selected_trajectory_distance'] for m in metrics]),
  'projected_initial_best_target_distance':stats([m['target_distance_before'] for m in metrics]),'projected_selected_target_distance_after':stats([m['target_distance_after'] for m in metrics]),
  'projected_archive_reference_distance_after':stats([m['archive_reference_projected_distance_after'] for m in metrics]),'reward_spread':stats([m['reward_spread'] for m in metrics]),
  'selected_reward':stats([m['selected_reward'] for m in metrics]),'memory':memory,'event_categories':dict(categories),'compute':compute,
  'actual_actions':categories['action_dispatch'],'actual_outcome_events_available':categories['pre_reset_outcome'],'actual_outcome_values_read':False,'physical_target_progress':'Unknown: no outcome tensor or contemporaneous target pose read',
  'stage_inference':'carried query before/after state at recorded decision steps; initial Stage1 static default only if no query; recognizer guidance is distinct from policy search',
  'gpu_process_wall_seconds':term['gpu_process_wall_seconds'],'provider_logical_calls':term['provider_logical_call_attempts']}
 # One prospective, outcome-independent window: first actual guided decision (else first recorded decision), its full executed chunk, next decision, and prior outcome if available.
 chosen=next((d for d in decisions if d['step'] in guided_steps),decisions[0] if decisions else None);selected=[]
 if chosen:
  ordinal=decisions.index(chosen);following=decisions[ordinal+1] if ordinal+1<len(decisions) else None
  allowed_events=[]
  for e,idx in bydecision[chosen['decision_id']]:
   if e['event'] in {'decision_context','policy_action_decode','decision_committed','pre_reset_outcome'}:allowed_events.append((e,idx))
  if following:
   allowed_events += [(e,idx) for e,idx in bydecision[following['decision_id']] if e['event']=='decision_context']
  prior=[(e,idx) for e,idx in all_events if e['event']=='pre_reset_outcome' and e['sequence']<next(e['sequence'] for e,_ in bydecision[chosen['decision_id']] if e['event']=='decision_context')]
  if prior:allowed_events.append(prior[-1])
  chosen_bundles={idx['bundle']:idx for e,idx in allowed_events}
  for name,idx in chosen_bundles.items():
   p=Path(files['events']['path']).parent/name
   selected.append({'path':str(p),'stat_bytes':p.stat().st_size if p.is_file() else None,'sha256_from_index':idx['sha256'],'categories_selected':dict(collections.Counter(e['event'] for e,i in allowed_events if i['bundle']==name)),
    'first_sequence':idx['first_sequence'],'last_sequence':idx['last_sequence'],'co_resident_event_count':len(idx['events'])})
  NEXT.append({'task_id':entry['task_id'],'arm':entry['profile'],'attempt_id':entry['attempt_id'],'selection_rule':'first observed guided decision; if none, first recorded decision; no outcome-based selection','chosen_decision':chosen,'next_decision':following,'prior_outcome_available':bool(prior),'bundles':selected,'total_container_stat_bytes':sum(x['stat_bytes'] or 0 for x in selected),'full_container_decode_not_authorized':True})
 DETAIL.append({'task_id':entry['task_id'],'arm':entry['profile'],'metrics_whitelist':metrics,'stage_public_fields':stages,'decision_timeline':timeline,'compute_key_names_only':compute_keys,'status_whitelist':status_info,'audit_whitelist':audit_info})
 ROWS.append(row)
 print(json.dumps({'completed':len(ROWS),'task':entry['task_id'],'arm':entry['profile'],'guided':actual_guided,'decisions':len(decisions)}),flush=True)

try:
 ctrl={Path(x['path']).name:load(x) for x in control['references']}
 result=ctrl['result-v1.json'];review=ctrl['root-terminal-review-v1.json'];source=ctrl['source-manifest-execution-v1.json']
 assert review['result']['sha256']==next(x['sha256'] for x in control['references'] if Path(x['path']).name=='result-v1.json')
 assert result['source_commit']==review['source_commit']==source['commit']=='d855cfd690482e018bb40ce98edec80fad9700e0'
 assert result['decision']==review['decision']=='REJECT_NUMERIC_DEV_FUTILITY' and result['audited_cells']==review['audited_cells']==24
 assert [(x['task_id'],x['profile']) for x in scope['attempts']]==[(t,a) for t in range(6) for a in ('C0','Q0','N28','N29')]
 for entry,cell,item in zip(scope['attempts'],result['accepted_cells'],result['attempts']):audit_attempt(entry,cell,item)
 assert len(ROWS)==24
except BaseException as exc:
 ERROR={'type':type(exc).__name__,'message':str(exc)}
finally:
 result={'schema':'n29-closed-task-relevance-metadata-v1','complete':ERROR is None and len(ROWS)==24,'error':ERROR,'selection':'all24 frozen accepted attempts; tasks6..9 unrun','rows':ROWS,'detail':DETAIL,'next_read_proposal':NEXT,'proposed_gpu_candidate':'NO_JUSTIFIED_CANDIDATE','new_payload_authorized':False}
 (H/'result-v1.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 (H/'input-manifest-v1.json').write_text(json.dumps({'schema':'n29-read-input-manifest-v1','files':READS,'metadata_bytes_read':READ,'tensor_reads':0},indent=2)+'\n')
 resource_record={'schema':'n29-task-relevance-resource-v1','reader_cpu_seconds':time.process_time()-CPU,'reader_wall_seconds':time.monotonic()-START,'metadata_bytes':READ,'affinity':sorted(os.sched_getaffinity(0)),'thread_environment':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},'address_space_limit_bytes':resource.getrlimit(resource.RLIMIT_AS)[0],'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'torch_imported':'torch' in sys.modules,'denied':DENIED,'error':ERROR,'completed_attempts':len(ROWS),'gpu_model_api_sim_calls':0,'tensor_payload_reads':0}
 (H/'resource-reader-v1.json').write_text(json.dumps(resource_record,indent=2)+'\n');print(json.dumps(resource_record),flush=True)
 if ERROR:sys.exit(1)
