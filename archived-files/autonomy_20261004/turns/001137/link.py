import json,pathlib,hashlib,datetime,torch,math
out=pathlib.Path(__file__).resolve().parent
p=out.parent/'001136/geometry-diagnosis-v1.json'; old=json.loads(p.read_text()); cells=[]
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def plain(x):
 if isinstance(x,torch.Tensor):return x.tolist()
 if isinstance(x,dict):return {k:plain(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [plain(v) for v in x]
 return x
for cell in old['cells']:
 aid=cell['summary']['attempt_id']
 if '_n35_' not in aid:continue
 steps=[688,696,704] if '_t00_' in aid else [560,568,576,648]
 directory=pathlib.Path(cell['bundles'][0]['path']).parent
 wanted=set(steps)|{s+8 for s in steps}; events=[]; bindings=[]
 for line in (directory/'events.jsonl').open():
  ix=json.loads(line)
  if not any(e.get('event','').startswith('n35_') and (e.get('global_step') in wanted or any(s<=e.get('global_step',-1)<s+8 for s in steps)) for e in ix['events']):continue
  bp=directory/ix['bundle']; assert ref(bp)['sha256']==ix['sha256'];bindings.append(ref(bp))
  es=torch.load(bp,map_location='cpu',weights_only=True)['events']
  events.extend(e for e in es if e['event'] in ['n35_observation_context','n35_selected_occurrence','n35_decode_binding','n35_step_acknowledged','n35_execution_complete','n35_execution_commit','n35_capture_dwell_opportunity'])
 rows=[]
 for s in steps:
  es=[e for e in events if e['global_step']==s]
  get=lambda name:next(e['values'] for e in es if e['event']==name)
  sel=get('n35_selected_occurrence');dec=get('n35_decode_binding');obs=get('n35_observation_context')['packet'];ti=sel['identity']['target_index']
  ne=[e for e in events if e['global_step']==s+8]
  nxt=next(e['values']['packet'] for e in ne if e['event']=='n35_observation_context')
  ns=next(e['values'] for e in ne if e['event']=='n35_selected_occurrence')
  acks=[e for e in events if s<=e['global_step']<s+8 and e['event']=='n35_step_acknowledged' and e['values']['native_identity']==sel['native_identity']]
  acks.sort(key=lambda e:e['values']['step'])
  decoded=dec['decoded'].reshape(-1,7); actions=torch.stack([e['values']['action'] for e in acks]) if acks else None
  stable=all(sel['identity'][k]==ns['identity'][k] for k in ['episode','stage','target_index','tracker_instance','tracker_generation'])
  eef_delta=nxt['observed_eef'].double()-obs['observed_eef'].double(); target_delta=nxt['keypoints'][ti].double()-obs['keypoints'][ti].double()
  rows.append(plain({'step':s,'identity':sel['identity'],'next_identity':ns['identity'],'same_target_stage_tracker':stable,'origin':sel['origin'],'ambiguous':sel['ambiguous'],'native_identity':sel['native_identity'],'decoded_identity':dec['decoded_identity'],'ack_count':len(acks),'ack_indices':[a['values']['index'] for a in acks],'all_ack_actions_equal_decoded':actions is not None and actions.shape==decoded.shape and torch.equal(actions,decoded),'decoded_prefix':decoded,'observed_eef':obs['observed_eef'],'next_eef':nxt['observed_eef'],'eef_delta':eef_delta,'eef_delta_norm_m':torch.linalg.vector_norm(eef_delta).item(),'target_delta':target_delta,'target_delta_norm_m':torch.linalg.vector_norm(target_delta).item(),'jaw':obs['gripper_qpos'],'next_jaw':nxt['gripper_qpos'],'geometry':next(d for d in cell['decisions'] if d['step']==s),'next_geometry':next(d for d in cell['decisions'] if d['step']==s+8)}))
 cells.append({'attempt_id':aid,'rows':rows,'bindings':bindings})
 print(aid,[(r['step'],r['ack_count'],r['all_ack_actions_equal_decoded'],r['eef_delta_norm_m'],r['target_delta_norm_m'],r['same_target_stage_tracker']) for r in rows])
result={'schema':'n35-dev-selected-action-link-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':old['source'],'ledger':old['ledger'],'parent':ref(p),'script':ref(pathlib.Path(__file__)),'cells':cells,'limits':['Selected Dev task0/task6 windows only.','Acknowledgments prove recorded environment-step action submission, not physical grasp or commanded pose attainment.','No within-chunk end-effector trajectory or contact-force inference.','Stable tracked identity does not establish physical target accuracy.'],'target_met':False}
(out/'action-link-v1.json').write_text(json.dumps(result,indent=2)+'\n')
