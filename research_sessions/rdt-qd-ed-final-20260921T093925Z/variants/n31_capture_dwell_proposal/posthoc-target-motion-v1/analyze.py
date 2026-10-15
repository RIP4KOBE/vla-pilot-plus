import json,pathlib,hashlib,math,resource
resource.setrlimit(resource.RLIMIT_CPU,(30,30))
resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))
b=pathlib.Path(__file__).resolve().parent
s=json.loads((b/'scope-v1.json').read_text());p=b/s['input'];raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==s['sha256']
d=json.loads(raw);rows=[]
def step(r):return int(r['decision_id'].rsplit(':s',1)[1])
for task in range(6):
 rr=sorted([r for r in d['decisions'] if r['task']==task and r['profile']=='N31'],key=step)
 for n,r in enumerate(rr):
  selected=[o for o in r['opportunities'] if o['selected_content']]
  if not selected:continue
  o=selected[0];i=o['identity'];obs=o['observation'];idx=i['target_index']
  out={'task':task,'decision_id':r['decision_id'],'target_index':idx,'arrival_indices':sorted(set(x['arrival_index'] for x in selected)),'next_available_context':None,'capture':'Unknown'}
  nxt=next((x for x in rr[n+1:] if x.get('context')),None)
  if nxt:
   c=nxt['context'];t=c['keypoint_tracking_snapshot'];a=obs['tracker'];target=str(idx)
   same=a['instance_id']==t['instance_id'] and a['generation']==t['generation']
   valid=all(x.get('valid') and x.get('status')=='tracked' for x in [a['targets'].get(target,{}),t['targets'].get(target,{})])
   gap=step(nxt)-step(r)
   out.update(next_available_context=nxt['decision_id'],step_gap=gap,unguided_or_missing_context_gap=gap!=8,tracker_continuous_at_endpoints=same,target_valid_at_endpoints=valid,stage_changed=c['stage']!=i['stage'],provider_source_present=any(x.get('source_text_sha256')==i['provider']['source_text_sha256'] for x in c['providers']))
   if same and valid:
    v=[y-x for x,y in zip(obs['keypoints'][idx],c['keypoints'][idx])]
    out.update(target_before=obs['keypoints'][idx],target_after=c['keypoints'][idx],delta_xyz_m=v,displacement_m=math.sqrt(sum(x*x for x in v)))
  rows.append(out)
assert len(rows)==12
res={'schema':'n31-target-motion-v1','input_sha256':s['sha256'],'selected_decisions':len(rows),'comparable_endpoint_pairs':sum('delta_xyz_m' in r for r in rows),'rows':rows,'limitations':['Tracked keypoints are not ground-truth object poses or grasp evidence.','Endpoint tracker continuity cannot establish uninterrupted validity between contexts.','Step gaps include intervening actions; motion cannot be attributed causally to close/dwell.','Posthoc descriptive accepted Dev evidence; frozen cohort rejection unchanged.']}
(b/'findings.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2))
