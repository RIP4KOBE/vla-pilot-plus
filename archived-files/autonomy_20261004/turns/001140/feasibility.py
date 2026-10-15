import pathlib,json,hashlib,math,datetime,sys
import torch
root=pathlib.Path.cwd();sys.path.insert(0,str(root))
import types
package=types.ModuleType('core');package.__path__=[str(root/'core')];sys.modules['core']=package
from core.rdt_libero_action_converter import encode_libero_prefix,rdt_action_to_libero_raw,LIBERO_ACTION_INDICES
from core.qd_observed_jaw_approach import propose
from core.qd_closure_intent import CONTINUITY
out=(root/'../autonomy_20261004/turns/001140').resolve()
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
parent=root/'../autonomy_20261004/turns/001137/action-link-v1.json'
assert ref(parent)['sha256']=='27d1ea4a3b1e88bd6f93cd2369fa06578679a7094840dcd6be728252bcbb01b1'
data=json.loads(parent.read_text());rows=[]
for cell in data['cells']:
 events=[]
 for b in cell['bindings']:
  assert ref(b['path'])==b
  events.extend(torch.load(b['path'],map_location='cpu',weights_only=True)['events'])
 for row in cell['rows']:
  step=row['step'];nstep=step+8
  es=[e for e in events if e['global_step']==step];ns=[e for e in events if e['global_step']==nstep]
  get=lambda seq,name:next(e['values'] for e in seq if e['event']==name)
  sel=get(es,'n35_selected_occurrence');dec=get(es,'n35_decode_binding');cur=get(ns,'n35_selected_occurrence')
  obs=get(ns,'n35_observation_context')['packet'];prev=get(es,'n35_observation_context')['packet']
  acks=[e['values'] for e in events if step<=e['global_step']<nstep and e['event']=='n35_step_acknowledged' and e['values']['native_identity']==sel['native_identity']]
  acks.sort(key=lambda a:a['index']);decoded=dec['decoded'].reshape(8,7)
  complete=any(e['event']=='n35_execution_complete' and e['values']['native_identity']==sel['native_identity'] for e in events if step<=e['global_step']<=nstep)
  commit=get(es,'n35_execution_commit')
  stable=all(k in sel['identity'] and k in cur['identity'] and sel['identity'][k]==cur['identity'][k] for k in CONTINUITY)
  p=decoded[:,:3].double().sum(0)*.01;d=obs['observed_eef'].double()-prev['observed_eef'].double();dot=float(torch.dot(p,d))
  valid=(stable and sel['origin']=='observed_open_approach' and not sel['ambiguous'] and complete and commit['horizon']==8 and commit['decoded_identity']==dec['decoded_identity'] and len(acks)==8 and [a['index'] for a in acks]==list(range(1,9)) and all(not a['ended'] and torch.equal(a['action'].reshape(7),decoded[i]) for i,a in enumerate(acks)))
  eligible=valid and bool(torch.isfinite(p).all()) and float(torch.linalg.vector_norm(p))>0 and dot<=0
  result={'attempt_id':cell['attempt_id'],'previous_step':step,'current_step':nstep,'full_identity_including_provider':stable,'complete_prefix_join':valid,'dot_p_d':dot,'eligible':eligible,'native_dtype':str(sel['native'].dtype)}
  if eligible:
   opp=get(ns,'n35_capture_dwell_opportunity');plan=opp['source']['plan'];ti=cur['identity']['target_index']
   point=obs['keypoints'][ti].double().tolist();eef=obs['observed_eef'].double().tolist();quat=obs['hand_quaternion_xyzw'].double().tolist();jaw=obs['gripper_qpos'].double().tolist()
   norm=math.sqrt(math.fsum(v*v for v in quat));x,y,z,w=[v/norm for v in quat]
   R=((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),(2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),(2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
   center=(0.,(jaw[1]+.0005+jaw[0]-.0005)/2,-.0036)
   error=[point[k]-eef[k]-math.fsum(R[k][a]*center[a] for a in range(3)) for k in range(3)]
   axis=min(range(3),key=lambda k:abs(error[k]));unit=[float(k==axis) for k in range(3)]
   cross=[error[1]*unit[2]-error[2]*unit[1],error[2]*unit[0]-error[0]*unit[2],error[0]*unit[1]-error[1]*unit[0]];cn=math.hypot(*cross)
   a=[max(-1.,min(1.,e/(8*.01))) for e in error];an=math.hypot(*a);b=[v/cn*an for v in cross]
   commands=[[max(-1.,min(1.,a[k]+sign*b[k])) for k in range(3)]+[0.,0.,0.,-1.] for sign in [1]*4+[-1]*4]
   checks=[]
   for dtype in [torch.bfloat16,torch.float32]:
    template=plan.to(dtype);cmd=torch.tensor(commands,dtype=dtype);cand=encode_libero_prefix(template,cmd);back=rdt_action_to_libero_raw(cand[:8]);direct=propose(template,target=obs['keypoints'][ti],observed_eef=obs['observed_eef'],hand_quaternion_xyzw=obs['hand_quaternion_xyzw'],gripper_qpos=obs['gripper_qpos'],target_recognized=True)
    directplan=direct.candidate if direct.candidate is not None else template
    mask=torch.ones_like(template,dtype=torch.bool);mask[:8,LIBERO_ACTION_INDICES]=False
    checks.append({'dtype':str(dtype),'encode_decode_exact':torch.equal(back,cmd.float()),'outside_prefix_channels_preserved':torch.equal(cand[mask],template[mask]),'distinct_from_direct':not torch.equal(cand,directplan),'bounded':bool((back[:,:3].abs()<=1).all()),'direct_reason':direct.reason,'decoded_translation_sum':back[:,:3].double().sum(0).tolist(),'max_abs_quantization_error':float((back.double()-torch.tensor(commands,dtype=torch.float64)).abs().max())})
   result.update(error_world_m=error,axis='xyz'[axis],cross_norm=cn,clipped_components=sum(abs(a[k]+sign*b[k])>1 for sign in [1,-1] for k in range(3)),native_checks=checks)
  rows.append(result)
report={'schema':'n36-bounded-cpu-feasibility-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'52a87af0bf11f95b21ce17aba456dc98944d9774','node_id':'15.6','parent':ref(parent),'ideation':ref(root/'../autonomy_20261004/turns/001139/n36-ideation-v1.json'),'script':ref(__file__),'rows':rows,'scope':'Seven already selected Dev windows only; no success estimate, new episode, implementation or scoring replay. Binary64 prospective arithmetic cast once to native dtype.','eligible_count':sum(r['eligible'] for r in rows),'gpu_authorized':False,'target_met':False}
(out/'feasibility-data-v1.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'eligible':report['eligible_count'],'rows':[{k:r[k] for k in ['attempt_id','current_step','full_identity_including_provider','complete_prefix_join','eligible']} for r in rows],'native_checks_pass':all(all(c['encode_decode_exact'] and c['outside_prefix_channels_preserved'] and c['distinct_from_direct'] and c['bounded'] for c in r.get('native_checks',[])) for r in rows)}))
