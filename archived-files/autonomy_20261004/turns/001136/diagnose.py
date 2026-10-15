import json,pathlib,hashlib,math,collections,datetime,torch
ROOT=pathlib.Path(__file__).resolve().parent
review=ROOT.parent/'001135/mechanism-review-v1.json'
r=json.loads(review.read_text()); output=[]
for cell in r['cells']:
 if cell['identity']['task_id'] not in [0,6] or cell['identity']['profile'] not in ['N34','N35']:continue
 d=pathlib.Path(cell['metrics']['path']).parent/'decision_evidence'/'episode_000'; prefix=cell['identity']['profile'].lower(); decisions=[]; bindings=[]
 for line in (d/'events.jsonl').open():
  idx=json.loads(line)
  if not any(e['event']==prefix+'_observation_context' for e in idx['events']):continue
  p=d/idx['bundle']; raw=p.read_bytes(); assert hashlib.sha256(raw).hexdigest()==idx['sha256']
  events=torch.load(p,map_location='cpu',weights_only=True)['events']; bindings.append({'path':str(p),'sha256':idx['sha256']})
  obs=next(e for e in events if e['event']==prefix+'_observation_context'); packet=obs['values']['packet']
  opp=next((e for e in events if e['event']==prefix+'_capture_dwell_opportunity'),None)
  if opp is None:continue
  ident=opp['values']['identity']; ti=ident.get('target_index')
  if ti is None:continue
  target=packet['keypoints'][ti].double().tolist(); origin=packet['observed_eef'].double().tolist(); q=packet['hand_quaternion_xyzw'].double().tolist(); jaw=packet['gripper_qpos'].double().tolist()
  length=math.sqrt(math.fsum(v*v for v in q)); x,y,z,w=[v/length for v in q]
  matrix=((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),(2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),(2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
  delta=[a-b for a,b in zip(target,origin)]; local=[math.fsum(matrix[k][j]*delta[k] for k in range(3)) for j in range(3)]
  lo=[-.008,jaw[1]+.0005,-.0116]; hi=[.008,jaw[0]-.0005,.0044]; gaps=[max(lo[k]-local[k],local[k]-hi[k],0) for k in range(3)]
  sel=next((e['values'] for e in events if e['event']==prefix+'_selected_occurrence'),{})
  decisions.append({'decision_id':obs['decision_id'],'step':obs['global_step'],'stage':ident['stage'],'target_index':ti,'local_target':local,'lo':lo,'hi':hi,'outside_axes':['xyz'[k] for k,g in enumerate(gaps) if g>0],'distance_to_box_m':math.sqrt(sum(v*v for v in gaps)),'empty_gap':lo[1]>hi[1],'selected_origin':sel.get('origin'),'selected_ambiguous':sel.get('ambiguous'),'proposal_reasons':dict(collections.Counter(e['values']['reason'] for e in events if e['event']==prefix+'_capture_dwell_opportunity'))})
 summary={'attempt_id':cell['attempt_id'],'guided_with_geometry':len(decisions),'inside':sum(not a['outside_axes'] and not a['empty_gap'] for a in decisions),'outside_axes':dict(collections.Counter(''.join(a['outside_axes']) for a in decisions)),'selected_origins':dict(collections.Counter(str(a['selected_origin']) for a in decisions)),'closest':sorted(decisions,key=lambda x:x['distance_to_box_m'])[:4]}
 output.append({'summary':summary,'decisions':decisions,'bundles':bindings}); print(json.dumps(summary),flush=True)
result={'schema':'n35-bounded-dev-geometry-diagnosis-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':r['source'],'review':{'path':str(review),'sha256':hashlib.sha256(review.read_bytes()).hexdigest()},'ledger':r['ledger'],'scope':'tasks0,6 N34,N35; recorded observation/first opportunity bundles only; CPU binary64 geometry from frozen reference; no native audit rerun','cells':output,'limits':['Decision boundaries only; cannot exclude between-boundary capture.','Geometry predicates are proposal conditions, not physical grasp evidence.','Target identity can change across stages; unpaired consecutive positions cannot establish progress.','N34 selected occurrence origin not instrumented by this extraction.'],'target_met':False}
(ROOT/'geometry-diagnosis-v1.json').write_text(json.dumps(result,indent=2)+'\n')
