import pathlib,json,hashlib,torch,collections
root=pathlib.Path.cwd(); out=(root.parent/'autonomy_20261004/turns/000877').resolve()
def read(p):return json.loads(pathlib.Path(p).read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def clean(v):
 if isinstance(v,torch.Tensor):return v.tolist()
 if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 return v
prev=read(out.parent/'000876/mechanism-comparison-v1.json'); tasks=[]
for t in prev['tasks']:
 p=pathlib.Path(t['receipt']['path']).parent/'decision_evidence/episode_000';idx=p/'events.jsonl'; rows=[json.loads(l) for l in idx.read_text().splitlines()];lo,hi=(0,24) if 't05' in t['attempt_id'] else (528,552)
 events=[]; refs=[]
 for r in rows:
  if not any(lo<=e['global_step']<=hi for e in r['events']):continue
  f=p/r['bundle'];rr=ref(f);assert rr['sha256']==r['sha256'];refs.append(rr)
  events.extend(e for e in torch.load(f,map_location='cpu',weights_only=False)['events'] if lo<=e['global_step']<=hi)
 decisions=[]; actions=[];outcomes=[]
 for did in dict.fromkeys(e['decision_id'] for e in events):
  es=[e for e in events if e['decision_id']==did]; contexts=[e for e in es if e['event']=='n34_observation_context'];fs=[e for e in es if e['event']=='final_selection'];ops=[e for e in es if e['event']=='n34_capture_dwell_opportunity']
  if not contexts:continue
  packet=contexts[0]['values']['packet'];target=ops[0]['values']['identity']['target_index'] if ops else None
  o={'decision_id':did,'step':contexts[0]['global_step'],'observed_eef':clean(packet['observed_eef']),'gripper_qpos':clean(packet['gripper_qpos']),'target_index':target,'tracked_target':clean(packet['keypoints'][target]) if target is not None else None,'proposals':[]}
  taint=set();direct=set();parent_hits=[];lastparents=None;op=None
  for e in es:
   v=e['values'];n=e['event']
   if n=='parent_allocation':lastparents=v['parent_fingerprints'];parent_hits.append({'iteration':v['iter_idx'],'possible_proposal_descendant_slots':[i for i,f in enumerate(lastparents) if f in taint]})
   if n=='n34_capture_dwell_opportunity':
    op=v;o['proposals'].append({'iteration':v['iteration'],'reason':v['reason'],'arrival_index':v['arrival_index'],'source_iteration':v.get('source',{}).get('iteration'),'source_row':v.get('source',{}).get('row')})
   if n=='canonical_candidate_identity':
    fps=v['fingerprints'];it=v['iter_idx']
    if it>=0 and lastparents is not None:
     parent_taint=[fp in taint for fp in lastparents]
     for i,fp in enumerate(fps):
      if parent_taint[i]:taint.add(fp)
    if op is not None and op['iteration']==it and op['reason']!='no_native_change':direct.add(fps[15]);taint.add(fps[15])
  o['parent_proposal_content_paths']=parent_hits
  if fs:
   v=fs[0]['values'];fp=v['selected_canonical_fingerprint'];o['selected_fingerprint']=fp;o['selected_direct_proposal_content']=fp in direct;o['selected_possible_descendant_content']=fp in taint
  dec=[e for e in es if e['event']=='policy_action_decode']
  if dec:o['decoded_first8_actions']=clean(dec[0]['values']['action_chunk'].reshape(-1,7)[:8])
  decisions.append(o)
 for e in events:
  if e['event']=='executed_action':actions.append({'step':e['global_step'],'decision_id':e['decision_id'],'action':clean(e['values']['action_numpy'])})
  if e['event']=='pre_reset_outcome':outcomes.append({'step':e['global_step'],'decision_id':e['decision_id'],**clean(e['values'])})
 tasks.append({'attempt_id':t['attempt_id'],'success':t['success'],'event_index':ref(idx),'range_inclusive':[lo,hi],'bundles':refs,'decisions':decisions,'executed_actions':actions,'outcomes':outcomes})
d={'schema':'n34-bounded-native-mechanism-v1','prior_comparison':ref(out.parent/'000876/mechanism-comparison-v1.json'),'scope':'Dev-only retrospective native observations; no GPU or protected reads','tasks':tasks,'lineage_limit':'Fingerprint propagation is possible content ancestry, not original occurrence ancestry or counterfactual causal proof; coupled search can cause effects outside a parent path. Original archive occurrence IDs are unavailable. No cross-decision lineage assertion.','target_motion_limit':'Tracked keypoints are not privileged object pose; contemporaneous_target_pose may be absent.','target_met':False}
(out/'native-mechanism-extraction-v1.json').write_text(json.dumps(d,indent=2)+'\n')
for t in tasks:
 print(t['attempt_id'],'actions',len(t['executed_actions']),'outcomes',len(t['outcomes']))
 for z in t['decisions']:
  print({k:z.get(k) for k in ['step','observed_eef','gripper_qpos','tracked_target','selected_direct_proposal_content','selected_possible_descendant_content']},'parent_hits',sum(len(q['possible_proposal_descendant_slots']) for q in z['parent_proposal_content_paths']))
 print('gripper commands',[(a['step'],a['action'][-1]) for a in t['executed_actions']])
print(ref(out/'native-mechanism-extraction-v1.json'))
