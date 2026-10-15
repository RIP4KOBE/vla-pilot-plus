from pathlib import Path
import hashlib,json,datetime
import torch

BASE=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/steering-integration')
NEW=BASE/'runs/eds-common-20261013';OLD=BASE/'runs/eds-migration-20261013'
NE=NEW/'output/evaluation';OE=OLD/'output/eds_eval'
report={'schema':'steering_initial_migration_comparison_v1','scope':'Task0 initial evidence and available action prefix only; live cohort validity/performance is not assessed','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'current':str(NEW),'reference':str(OLD),'cohort_valid':None,'files_read':{},'online_responses_replayed':False}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):
 raw=path.read_bytes();report['files_read'][str(path)]={'sha256':sha(raw),'bytes':len(raw)};return raw
def js(path):return json.loads(read(path))
def rows(path):
 if not path.exists():return []
 raw=read(path);result=[]
 for line in raw.splitlines():
  try:result.append(json.loads(line))
  except json.JSONDecodeError:break
 return result

def files(a,b):
 aa=read(a);bb=read(b);return {'current_sha256':sha(aa),'reference_sha256':sha(bb),'byte_identical':aa==bb}
report['status_snapshot']=js(NEW/'status.json');report['progress_snapshot']=js(NEW/'progress.json')
report['commits']={'current':js(NEW/'manifest.json')['commit'],'reference':js(OLD/'manifest.json')['commit']}
report['rng']={}
for phase in ('prepare','rollout'):
 a=[r for r in rows(NE/'episode_rng_events.jsonl') if r['metadata']==dict(episode_seed=44,phase=phase,task_id=0)]
 b=[r for r in rows(OE/'episode_rng_events.jsonl') if r['metadata']==dict(episode_seed=44,phase=phase,task_id=0)]
 report['rng'][phase]={'exact_record_match':len(a)==len(b)==1 and a[0]==b[0],'current':a}
report['fresh_reward_inputs']={name:files(NEW/'output/episode_1/vlm_agent'/name,OLD/'output/episode_1/vlm_agent'/name) for name in ('query_img.png','prompt.txt')}
report['stage_inputs']={}
for index,label in ((0,'identity'),(1,'first_observation')):
 a=NEW/f'output/captured_stage_inputs/request_{index:04d}';b=OLD/f'output/captured_stage_inputs/request_{index:04d}'
 entry={name:files(a/name,b/name) for name in ('image_01.png','codex_prompt.txt')}
 ar=js(a/'response.json');br=js(b/'response.json')
 entry['both_requests_ok']=ar['ok'] is True and br['ok'] is True
 entry['raw_response_identical']=ar['raw_response']==br['raw_response']
 entry['current_raw_response']=ar['raw_response'];entry['reference_raw_response']=br['raw_response']
 if index==1:
  prefix='Target appearance from the initial reference (identity only): '
  ap=(a/'codex_prompt.txt').read_text().splitlines();bp=(b/'codex_prompt.txt').read_text().splitlines()
  entry['prompt_identical_except_generated_identity_line']=[x for x in ap if not x.startswith(prefix)]==[x for x in bp if not x.startswith(prefix)]
  ao=json.loads(ar['raw_response']);bo=json.loads(br['raw_response'])
  entry['symbolic_observation_fields']={k:{'current':ao[k],'reference':bo[k],'identical':ao[k]==bo[k]} for k in ('target_visibility','target_location','grasp','support')}
 report['stage_inputs'][label]=entry
report['trace_comparisons']=[]

def leafdiff(a,b,p='',stats=None,diffs=None):
 if torch.is_tensor(a) or torch.is_tensor(b):
  stats['tensor_leaves']+=1
  same=torch.is_tensor(a) and torch.is_tensor(b) and a.dtype==b.dtype and a.shape==b.shape and a.contiguous().view(torch.uint8).numpy().tobytes()==b.contiguous().view(torch.uint8).numpy().tobytes()
  if not same:
   d={'path':p,'kind':'tensor','current_dtype':str(getattr(a,'dtype',None)),'reference_dtype':str(getattr(b,'dtype',None)),'current_shape':list(a.shape) if torch.is_tensor(a) else None,'reference_shape':list(b.shape) if torch.is_tensor(b) else None}
   if torch.is_tensor(a) and torch.is_tensor(b) and a.shape==b.shape:d['max_absolute_difference']=float((a.double()-b.double()).abs().max())
   diffs.append(d)
 elif isinstance(a,dict) and isinstance(b,dict):
  for k in sorted(set(a)|set(b)):
   q=p+'.'+str(k) if p else str(k)
   if k not in a or k not in b:diffs.append({'path':q,'kind':'missing_key','current_present':k in a,'reference_present':k in b})
   else:leafdiff(a[k],b[k],q,stats,diffs)
 elif isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
  if len(a)!=len(b):diffs.append({'path':p,'kind':'length','current':len(a),'reference':len(b)})
  for i,(aa,bb) in enumerate(zip(a,b)):leafdiff(aa,bb,f'{p}[{i}]',stats,diffs)
 else:
  stats['scalar_leaves']+=1
  if type(a)!=type(b) or a!=b:diffs.append({'path':p,'kind':'scalar','current':a,'reference':b})

for step in (0,8):
 rel=Path(f'qualitative/episode_000/chunk_{step:06d}/tensors/mechanism_trace.pt')
 if not (NE/rel).exists():continue
 ar=read(NE/rel);br=read(OE/rel)
 import io
 a=torch.load(io.BytesIO(ar),map_location='cpu',weights_only=True);b=torch.load(io.BytesIO(br),map_location='cpu',weights_only=True)
 stats={'tensor_leaves':0,'scalar_leaves':0};diffs=[];leafdiff(a,b,stats=stats,diffs=diffs)
 excluded={'metadata.initial_sampler_info.initial_sampler_latency_s'}
 report['trace_comparisons'].append({'step':step,'counts':stats,'differences':diffs,'excluded_timing_paths':sorted(excluded),'scientific_tensor_scalar_exact':not any(d['path'] not in excluded for d in diffs),'all_tensor_leaves_bitwise_exact':not any(d['kind']=='tensor' for d in diffs)})
report['metric_comparisons']=[]
a=[r for r in rows(NE/'eds_metrics.jsonl') if r.get('task_id')==0];b={r['global_step']:r for r in rows(OE/'eds_metrics.jsonl') if r.get('task_id')==0}
excluded={'eds_loop_latency_s','initial_sampler_latency_s','job_id','method_label','select_action_latency_s','qualitative_artifacts'}
for row in a[:2]:
 old=b[row['global_step']];diffs=[key for key in sorted(row.keys()|old.keys()) if row.get(key)!=old.get(key)]
 report['metric_comparisons'].append({'step':row['global_step'],'different_fields':diffs,'scientific_fields_exact':not any(k not in excluded for k in diffs),'selected_reward':row.get('final_best_reward'),'selected_index':row.get('selected_idx')})
report['metric_excluded_metadata_fields']=sorted(excluded)
a=[r for r in rows(NE/'safety_events.jsonl') if r.get('episode')==0 and r.get('task_id')==0 and r.get('event')=='stage_grasp_guard_action']
b={r['global_step']:r for r in rows(OE/'safety_events.jsonl') if r.get('episode')==0 and r.get('task_id')==0 and r.get('event')=='stage_grasp_guard_action'}
exits={r['global_step'] for r in rows(NE/'phase_timing.jsonl') if r.get('episode')==0 and r.get('name')=='adapter_step' and r.get('event')=='exit'}
a=[r for r in a if r['global_step'] in exits and r['global_step'] < 104]
report['actions']={'completed_action_prefix_count':len(a),'steps_contiguous_from_zero':[r['global_step'] for r in a]==list(range(len(a))),'different_executed_action_steps':[r['global_step'] for r in a if r['executed_action']!=b[r['global_step']]['executed_action']],'different_raw_action_steps':[r['global_step'] for r in a if r['raw_action']!=b[r['global_step']]['raw_action']],'all_new_actions_passed_through':all(r['raw_action']==r['executed_action'] and r.get('override') is False for r in a)}
report['cuda_initialized']=torch.cuda.is_initialized()
report['limits']=['This snapshot is only an initial task0 prefix; later trajectories and full cohort may differ.','Fresh identity and observation text may differ without source or image changes; comparisons explicitly retain those differences.','Saved tensor comparison uses weights-only CPU loading; no model execution, service calls, simulator or CUDA probes.','Only timing/path/label metadata enumerated in each comparison is excluded; different scientific values remain failures of exact equivalence.']
assert not report['cuda_initialized']
destination=BASE/'checks/eds-common-initial-comparison.json'
destination.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'report':str(destination),'rng':{k:v['exact_record_match'] for k,v in report['rng'].items()},'traces':report['trace_comparisons'],'metrics':report['metric_comparisons'],'actions':report['actions'],'cuda_initialized':report['cuda_initialized']},ensure_ascii=False,indent=2))
