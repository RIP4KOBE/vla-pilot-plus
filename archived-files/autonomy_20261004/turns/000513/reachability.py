import pathlib,json,hashlib,collections,datetime,math,sys
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000513'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
ledger=root/'data/attempt-ledger.jsonl';lb=ledger.read_bytes();assert hashlib.sha256(lb).hexdigest()=='229878bc3a9d99fd596f363835f4ef1ae3c2757b7f34aa43e0aef985de1aa0f2'
statusp=out.parent/'000469/launch-v2/controller-status.json';status=json.loads(statusp.read_text());ids={x['attempt_id'] for x in status['outcomes']};cells=[json.loads(l) for l in lb.splitlines() if json.loads(l).get('event')=='valid' and json.loads(l).get('attempt_id') in ids];assert len(cells)==18
availability=[];indexes={}
for c in cells:
 p=pathlib.Path(c['output_dir'])/'eds_eval/decision_evidence/episode_000/events.jsonl';bs=[json.loads(l) for l in p.read_text().splitlines()];counts=collections.Counter(e['event'] for b in bs for e in b['events']);indexes[c['attempt_id']]=(p,bs)
 availability.append({'attempt_id':c['attempt_id'],'task':c['identity']['task_id'],'profile':c['identity']['profile'],'index':ref(p),'contexts':counts['decision_context'],'observation_packets':counts['n32_observation_context']})
(out/'availability-v1.json').write_text(json.dumps({'cells':availability,'ledger':ref(ledger),'controller_status':ref(statusp)},indent=2)+'\n');print('AVAILABILITY',availability,flush=True)
import torch
sys.path.insert(0,str(root));from scripts.qd_ed_n32_native import packet_identity
from scripts.qd_ed_n30_native import provider_target
manifest=[];rows=[]
for c in cells:
 idx,bs=indexes[c['attempt_id']];groups=collections.defaultdict(dict)
 for b in bs:
  if not any(e['event'] in {'decision_context','n32_observation_context'} for e in b['events']):continue
  p=idx.parent/b['bundle'];assert ref(p)['sha256']==b['sha256'];manifest.append({'path':str(p),'sha256':b['sha256']})
  for e in torch.load(p,map_location='cpu',weights_only=False)['events']:
   if e['event'] in {'decision_context','n32_observation_context'}:
    assert e['event'] not in groups[e['decision_id']];groups[e['decision_id']][e['event']]=e
 for did,g in groups.items():
  ctx=g['decision_context'];r={'attempt_id':c['attempt_id'],'task':c['identity']['task_id'],'profile':c['identity']['profile'],'decision':did,'guided':ctx['values']['use_guidance'],'recognized_target':False,'nonempty_jaw':None,'entry':None,'changed_opportunities':'Unknown'};rows.append(r)
  if 'n32_observation_context' not in g:r['reason']='Unknown_missing_observation_packet';continue
  packet=g['n32_observation_context']['values']['packet']
  try:
   binding=provider_target(ctx);identity,skip,target=packet_identity(ctx,packet,binding)
   r['recognized_target']=binding is not None;r['identity']=identity
   if skip:r['reason']=skip;continue
   vals=[]
   for v,n in [(packet['observed_eef'],3),(packet['hand_quaternion_xyzw'],4),(packet['gripper_qpos'],2),(target,3)]:
    assert torch.is_tensor(v) and tuple(v.shape)==(n,) and bool(torch.isfinite(v).all());vals.append(v.double().tolist())
   pos,quat,jaw,point=vals;length=math.sqrt(math.fsum(t*t for t in quat));assert math.isfinite(length) and length>0
   x,y,z,w=[t/length for t in quat];matrix=((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),(2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),(2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
   lo,hi=jaw[1]+.0005,jaw[0]-.0005;r['nonempty_jaw']=lo<=hi;d=[point[k]-pos[k] for k in range(3)];a=[math.fsum(matrix[k][axis]*d[k] for k in range(3)) for axis in range(3)];r['hand_coordinates']=a;r['jaw_interval']=[lo,hi]
   r['entry']=lo<=hi and -.008<=a[0]<=.008 and lo<=a[1]<=hi and -.0116<=a[2]<=.0044;r['reason']='current_entry' if r['entry'] else 'no_current_entry';r['changed_opportunities']=0 if not r['entry'] or not r['guided'] else 'Pending_native_parent_check'
  except (ValueError,AssertionError,TypeError,KeyError) as ex:r['reason']='Unknown_malformed_or_unverifiable';r['error']=str(ex)
 print(c['attempt_id'],'contexts',len(groups),'hits',sum(r['entry'] is True for r in rows if r['attempt_id']==c['attempt_id']),flush=True)
manifestp=out/'input-manifest.json';manifestp.write_text(json.dumps(manifest,indent=2)+'\n')
summary=[]
for c in availability:
 rr=[r for r in rows if r['attempt_id']==c['attempt_id']];assert len(rr)==c['contexts'];summary.append({**c,'guided':sum(r['guided'] for r in rr),'recognized_targets':sum(r['recognized_target'] for r in rr),'nonempty_jaw':sum(r['nonempty_jaw'] is True for r in rr),'entry_hits':sum(r['entry'] is True for r in rr),'guided_entry_hits':sum(r['entry'] is True and r['guided'] for r in rr),'reasons':dict(collections.Counter(r['reason'] for r in rr))})
assert ledger.read_bytes()==lb
report={'schema':'n33-current-observation-reachability-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'availability':ref(out/'availability-v1.json'),'extraction':ref(out/'reachability.py'),'literal_prism_reference':ref(root/'scripts/qd_ed_n31_reference.py'),'input_manifest':ref(manifestp),'ledger':ref(ledger),'cells':summary,'rows':rows,'limitations':['Controls lacking N32 observation packets remain Unknown.','Unguided entries are not admissible ordinary QD proposal opportunities.','Tracked keypoints are not verified grasp points.','Native-byte changes checked only after a guided current-entry hit.','CPU feasibility is not efficacy or scientific promotion.']}
(out/'reachability-v1.json').write_text(json.dumps(report,indent=2)+'\n');print('SUMMARY',json.dumps(summary),flush=True)
