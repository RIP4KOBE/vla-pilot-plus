import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['OMP_NUM_THREADS']='2'
import json,pathlib,hashlib,io,time,resource,collections
import torch
torch.set_num_threads(2)
resource.setrlimit(resource.RLIMIT_CPU,(300,300))
start=time.monotonic(); cpu=time.process_time()
base=pathlib.Path(__file__).resolve().parent
scope=base.parent/'posthoc-native-metadata-v1/decode-scope-v1.json'
assert hashlib.sha256(scope.read_bytes()).hexdigest()=='e12543bad29f431986995966712b4f4b2ca2ff0f0382f41067918c848e4c7303'
s=json.loads(scope.read_text()); rows={}; counts=collections.Counter()
def small(v):
 if torch.is_tensor(v): return v.tolist() if v.numel()<=100 else {'shape':list(v.shape),'omitted':True}
 if isinstance(v,dict):return {k:small(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [small(x) for x in v]
 return v
for ref in s['inputs']:
 assert time.monotonic()-start<590
 b=pathlib.Path(ref['path']).read_bytes();assert len(b)==ref['bytes'] and hashlib.sha256(b).hexdigest()==ref['sha256']
 events=torch.load(io.BytesIO(b),map_location='cpu',weights_only=True)['events'];counts['bundles']+=1
 finals={e['decision_id']:e['values']['selected_latent'] for e in events if e['event']=='final_selection'}
 for e in events:
  kind=e['event'];v=e['values']; key=(ref['identity']['task_id'],ref['identity']['profile'],e['decision_id'])
  if kind not in ['decision_context','n31_capture_dwell_opportunity','policy_action_decode','executed_action','pre_reset_outcome']:continue
  row=rows.setdefault(key,{'task':key[0],'profile':key[1],'decision_id':key[2],'opportunities':[],'executed':[],'outcomes':[]})
  if kind=='decision_context':row['context']=small(v)
  elif kind=='n31_capture_dwell_opportunity':
   cand=v['candidate']; final=finals.get(e['decision_id']); selected=cand is not None and final is not None and torch.equal(cand.reshape(-1),final.reshape(-1))
   row['opportunities'].append({'iteration':v['iteration'],'reason':v['reason'],'arrival_index':v['arrival_index'],'changed':cand is not None,'selected_content':selected,'identity':small(v['identity']),'observation':small(v['observation'])})
   counts['changed']+=cand is not None
  elif kind=='policy_action_decode': row['decoded_actions']=small(v['action_chunk'])
  elif kind=='executed_action':row['executed'].append({'step':e['global_step'],'action':small(v['action_numpy'])})
  else:row['outcomes'].append({'step':e['global_step'],**small(v)})
 del events,b
 assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<4294967296
summary=[]
for task in range(6):
 for arm in ['Q0','N31']:
  rr=[r for r in rows.values() if r['task']==task and r['profile']==arm]
  selected=[r['decision_id'] for r in rr if any(o['selected_content'] for o in r['opportunities'])]
  summary.append({'task':task,'profile':arm,'decisions':len(rr),'changed_proposals':sum(o['changed'] for r in rr for o in r['opportunities']),'selected_content_decisions':selected,'executed_actions':sum(len(r['executed']) for r in rr)})
result={'schema':'n31-posthoc-native-decode-v1','scope_sha256':hashlib.sha256(scope.read_bytes()).hexdigest(),'counts':dict(counts),'summary':summary,'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'limitations':['Descriptive accepted Dev only; no promotion.','Target keypoints are tracked observations, not ground-truth capture.','Only frozen guided-decision bundles decoded; omitted decisions are not negative evidence.'],'decisions':list(rows.values())}
(base/'decoded.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='decisions'},indent=2))
