"""Bounded six-packet CPU selection review; no environment/model construction."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
import ast, json, hashlib, pathlib, sys, types, math, numbers, subprocess, traceback, datetime
import numpy as np
import torch
from typing import Union, Optional, List, Callable
from torch import Tensor
OUT=pathlib.Path(__file__).resolve().parent
ROOT=pathlib.Path.cwd()
BASE=OUT.parent.parent
SOURCE='52a87af0bf11f95b21ce17aba456dc98944d9774'
torch.set_num_threads(1);torch.set_num_interop_threads(1)
manifest={};errors=[]
def ref(path, expected=None, n=None):
 p=pathlib.Path(path).resolve()
 with p.open('rb') as f:b=f.read(n) if n is not None else f.read()
 h=hashlib.sha256(b).hexdigest()
 r={'path':str(p),'sha256':h}
 if n is not None:r['bytes']=n
 if expected:r.update(expected_sha256=expected,match=h==expected)
 manifest[str(p)+(f':prefix:{n}' if n else '')]=r
 if expected and h!=expected:raise ValueError(f'hash mismatch: {p}')
 return b

def readjson(p,expected=None):return json.loads(ref(p,expected))
def source(p):
 b=ref(ROOT/p);frozen=subprocess.check_output(['git','show',f'{SOURCE}:{p}'],cwd=ROOT)
 assert b==frozen,p
 manifest[str((ROOT/p).resolve())]['matches_frozen_git_blob']=True
 return b.decode()

def extract(p,names,ns):
 tree=ast.parse(source(p));nodes=[]
 for name in names:
  matches=[x for x in ast.walk(tree) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==name]
  assert len(matches)==1,(p,name,len(matches))
  nodes.append(matches[0])
 exec(compile(ast.Module(body=nodes,type_ignores=[]),p,'exec'),ns)
 return ns

def serial(x):
 if torch.is_tensor(x):return x.tolist()
 if isinstance(x,dict):return {k:serial(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [serial(v) for v in x]
 return x

def run():
 authority=readjson(OUT/'authority-v1.json')
 for k in ['user_authority','root_feasibility_review','ideation','ledger_prefix']:
  r=authority[k];ref(r['path'],r['sha256'],r.get('bytes'))
 root=readjson(authority['root_feasibility_review']['path'])
 for r in [root['data'],root['script'],*root['source_evidence']]:ref(r['path'],r['sha256'])
 idea=readjson(authority['ideation']['path'])
 for r in [idea['authority'],idea['constraints'],*idea['evidence']]:ref(r['path'],r['sha256'])
 auth=readjson(authority['user_authority']['path']);r=auth['approved_budget_proposal'];ref(r['path'],r['sha256'])
 data=readjson(root['data']['path']);link=readjson(data['parent']['path'],data['parent']['sha256'])
 package=types.ModuleType('core');package.__path__=[str(ROOT/'core')];sys.modules['core']=package
 for p in ['core/qd_observed_jaw_approach.py','core/qd_capture_dwell.py','core/qd_capture_dwell_proposal.py','core/rdt_libero_action_converter.py','core/qd_ed.py','core/qd_executed_quality.py','core/qd_closure_intent.py','core/decision_evidence.py']:
  source(p)
 from core.qd_observed_jaw_approach import propose
 from core.rdt_libero_action_converter import encode_libero_prefix,rdt_action_to_libero_raw
 from core.qd_ed import fingerprint_action,qd_descriptor,cell_ids,QDBounds,QDArchive
 from core.qd_executed_quality import _template_index,_code_signature
 ns=dict(torch=torch,np=np,Union=Union,Tensor=Tensor,Optional=Optional,List=List,Callable=Callable,RDT_GUIDED_ACTION_INDICES=[39,40,41,42,43,44,10],numbers=numbers)
 extract('core/env_adapters/libero_adapter.py',['delta_actions_to_ee_trajectory'],ns)
 extract('core/rdt_policy_steer.py',['_decode_rdt_actions_for_guidance','_rdt_sample_to_trajectory_3d','_trajectory_reward_slice','_score_particles'],ns)
 extract('utils/guidance_utils.py',['wrap_guidance_function_with_device_fix'],ns)
 class Adapter:
  delta_actions_to_ee_trajectory=ns['delta_actions_to_ee_trajectory']
  def get_ee_pose_world(self):return types.SimpleNamespace(position=self.origin.numpy())
 class Policy:
  _decode_rdt_actions_for_guidance=ns['_decode_rdt_actions_for_guidance']
  _rdt_sample_to_trajectory_3d=ns['_rdt_sample_to_trajectory_3d']
  _trajectory_reward_slice=ns['_trajectory_reward_slice']
  _score_particles=ns['_score_particles']
  _action_chunk_horizon=8
  def _increment_compute(self,*args):pass
  def _counted_reward(self,fn,k,t):return fn(k,t)
 policy=Policy();policy._adapter=Adapter()
 def sequential_projection(samples):
  # Diagnostic only: native sequential accumulation is not asserted to be the deployed kernel.
  actions=policy._decode_rdt_actions_for_guidance(samples)
  start=policy._adapter.origin.to(samples)
  outputs=[]
  for action in actions:
   delta=action[:,:3]*.01;acc=torch.zeros(3,dtype=delta.dtype);points=[start]
   for d in delta:
    acc=acc+d;points.append(start+acc)
   outputs.append(torch.stack(points))
  return torch.stack(outputs)
 def provider_quality(xyz,keypoints,dtype):
  return torch.stack([sum([provider(keypoints,xyz[i:i+1,1:8])]).to(dtype).reshape(()) for i in range(len(xyz))])
 rows=[]
 for cell in link['cells']:
  eligible=[r for r in data['rows'] if r['eligible'] and r['attempt_id']==cell['attempt_id']]
  allowed={r['current_step'] for r in eligible};events=[]
  for binding in cell['bindings']:
   ref(binding['path'],binding['sha256'])
   bundle=torch.load(binding['path'],map_location='cpu',weights_only=True)
   events.extend(e for e in bundle['events'] if e['global_step'] in allowed)
  for row in eligible:
   es=[e for e in events if e['global_step']==row['current_step']]
   def get(name):return [e for e in es if e['event']==name]
   opp=get('n35_capture_dwell_opportunity')[0]['values'];assert opp['iteration']==0
   obs=get('n35_observation_context')[0]['values']['packet'];context=get('decision_context')[0]['values']
   prov=context['providers'];assert len(prov)==1
   txt=ref(prov[0]['source_path'],prov[0]['source_text_sha256']).decode()
   _,name,index=_template_index(txt);assert index==opp['identity']['target_index']==0
   pn={'torch':torch};exec(compile(txt,'<string>','exec'),pn);fn=pn[name]
   codehash=hashlib.sha256(repr(_code_signature(fn.__code__)).encode()).hexdigest()
   assert codehash==opp['identity']['provider']['code_structure_sha256']
   provider=ns['wrap_guidance_function_with_device_fix'](fn)
   src=opp['source'];template=src['plan'];assert template.dtype==torch.bfloat16
   for path,h in opp['source_hashes'].items():ref(ROOT/path,h);source(path)
   score_events={e['sequence']:e['values'] for e in get('scoring_inputs')}
   initial=score_events[src['scoring_batch_id']]
   off=[v for v in score_events.values() if v['scoring_scope']['role']=='canonical_offspring' and v['scoring_scope']['iter_idx']==0][0]
   updates={e['values']['iter_idx']:e['values'] for e in get('n35_archive_update')}
   qualities={e['values']['scoring_batch_id']:e['values']['quality'] for e in get('effective_quality')}
   byseq={e['sequence']:e for e in es}
   checks=[]
   # Control replay: frozen projection/scoring vs recorded initial and first offspring, 32 rows per packet.
   for label,inp in [('initial',initial),('offspring0',off)]:
    seq=next(k for k,v in score_events.items() if v is inp)
    origins=[byseq[q]['values']['source_eef_position'] for q in inp['projection_origin_sequences']]
    assert all(torch.equal(torch.as_tensor(o),torch.as_tensor(origins[0])) for o in origins)
    policy._adapter.origin=torch.as_tensor(origins[0])
    xyz=policy._rdt_sample_to_trajectory_3d(inp['samples'])
    q=policy._score_particles(inp['samples'],inp['keypoints'],[provider],slice_kind='eds')
    sq=sequential_projection(inp['samples'])
    storedq=provider_quality(inp['projected_xyz'],inp['keypoints'],inp['samples'].dtype)
    seqq=provider_quality(sq,inp['keypoints'],inp['samples'].dtype)
    checks.append({'stored_projection_provider_quality_exact':torch.equal(storedq,qualities[seq]),'stored_projection_provider_quality_matching_rows':int((storedq==qualities[seq]).sum()),'sequential_projection_exact':torch.equal(sq,inp['projected_xyz']),'sequential_projection_matching_rows':int((sq==inp['projected_xyz']).flatten(1).all(1).sum()),'sequential_quality_exact':torch.equal(seqq,qualities[seq]),'batch':label,'candidates':len(q),'projection_exact':torch.equal(xyz,inp['projected_xyz']),'provider_slice_exact':torch.equal(policy._trajectory_reward_slice(xyz,'eds'),inp['provider_input_xyz']),'quality_exact':torch.equal(q,qualities[seq]),'max_quality_difference':float((q.float()-qualities[seq].float()).abs().max())})
   # Registered binary64 arithmetic, single native cast, unchanged remainder.
   point=obs['keypoints'][index].double().tolist();eef=obs['observed_eef'].double().tolist();quat=obs['hand_quaternion_xyzw'].double().tolist();jaw=obs['gripper_qpos'].double().tolist()
   norm=math.sqrt(math.fsum(v*v for v in quat));x,y,z,w=[v/norm for v in quat]
   R=((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),(2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),(2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
   center=(0.,(jaw[1]+.0005+jaw[0]-.0005)/2,-.0036)
   error=[point[k]-eef[k]-math.fsum(R[k][a]*center[a] for a in range(3)) for k in range(3)]
   assert error==row['error_world_m']
   axis=min(range(3),key=lambda k:abs(error[k]));unit=[float(k==axis) for k in range(3)]
   cross=[error[1]*unit[2]-error[2]*unit[1],error[2]*unit[0]-error[0]*unit[2],error[0]*unit[1]-error[1]*unit[0]]
   a=[max(-1.,min(1.,e/.08)) for e in error];b=[v/math.hypot(*cross)*math.hypot(*a) for v in cross]
   cmds=[[max(-1.,min(1.,a[k]+sign*b[k])) for k in range(3)]+[0.,0.,0.,-1.] for sign in [1]*4+[-1]*4]
   detour=encode_libero_prefix(template,torch.tensor(cmds,dtype=template.dtype))
   dr=propose(template,target=obs['keypoints'][index],observed_eef=obs['observed_eef'],hand_quaternion_xyzw=obs['hand_quaternion_xyzw'],gripper_qpos=obs['gripper_qpos'],target_recognized=True)
   direct=dr.candidate;assert direct is not None and torch.equal(direct,opp['candidate'])
   assert torch.equal(off['samples'],opp['actual_scored_population'])
   policy._adapter.origin=src['source_origin']
   assert torch.equal(policy._adapter.origin,torch.as_tensor(byseq[off['projection_origin_sequences'][15]]['values']['source_eef_position']))
   plans=torch.stack([detour,direct,template]);xyz=policy._rdt_sample_to_trajectory_3d(plans)
   q=policy._score_particles(plans,off['keypoints'],[provider],slice_kind='eds')
   desc=qd_descriptor(xyz,off['keypoints']);bounds=QDBounds(lo=updates[-1]['bounds_lo'],hi=updates[-1]['bounds_hi'],checksum="recorded_bounds_no_recalculation")
   ids,overflow=cell_ids(desc,bounds,[4,4]);fps=[fingerprint_action(p) for p in plans]
   # Conditional one-update intervention; unknown detour deployed score prevents an exact runtime claim.
   initbatch=initial['samples'];initq=qualities[src['scoring_batch_id']]
   archive=QDArchive(grid_shape=(4,4))
   archive.update(actions=initbatch,rewards=initq,costs=-initq,descriptors=updates[-1]['descriptors'],cell_ids=updates[-1]['cell_ids'],source_iter=-1)
   cf=off['samples'].clone();cf[15]=detour
   cfq=qualities[next(k for k,v in score_events.items() if v is off)].clone();cfq[15]=q[0]
   cfd=updates[0]['descriptors'].clone();cfd[15]=desc[0];cfi,_=cell_ids(cfd,bounds,[4,4])
   # The other fifteen scores/descriptors and initial state remain recorded, not CPU rescored.
   seqxyz=sequential_projection(plans)
   seqq=provider_quality(seqxyz,off['keypoints'],plans.dtype)
   seqdesc=qd_descriptor(seqxyz,off['keypoints']);seqids,_=cell_ids(seqdesc,bounds,[4,4])
   archive.update(actions=cf,rewards=cfq,costs=-cfq,descriptors=cfd,cell_ids=cfi,source_iter=0)
   bestcell,best=archive.select_global_best()
   detcell=int(ids[0]);inc=next((e for e in updates[-1]['archive'] if e['cell_id']==detcell),None)
   comp=[]
   for i,label in enumerate(['detour','direct','template']):
    comp.append({'name':label,'quality':float(q[i]),'sequential_accumulation_diagnostic_quality':float(seqq[i]),'sequential_accumulation_diagnostic_cell':int(seqids[i]),'quality_hex':float(q[i]).hex(),'fingerprint':fps[i],'descriptor':desc[i].tolist(),'cell_id':int(ids[i]),'overflow':bool(overflow[i]),'projected_xyz':xyz[i].float().tolist(),'decoded_prefix':rdt_action_to_libero_raw(plans[i,:8]).tolist()})
   samecell=int(ids[0])==int(ids[1]);wins=QDArchive._candidate_better(float(q[0]),fps[0],float(q[1]),fps[1])
   rows.append({'attempt_id':row['attempt_id'],'step':row['current_step'],'decision_id':get('decision_context')[0]['decision_id'],'first_opportunity_only':True,'control_replay':checks,'clipped_components':row['clipped_components'],'comparisons':comp,'detour_minus_direct':float(q[0])-float(q[1]),'detour_minus_template':float(q[0])-float(q[2]),'same_cell_as_direct':samecell,'detour_beats_direct_by_archive_order':wins,'initial_incumbent_in_detour_cell':inc,'one_update_counterfactual':{'status':'CONDITIONAL_CPU_DETOUR_WITH_RECORDED_OTHER15_NOT_EXACT_DEPLOYED_REPLAY','retained':detcell in archive.entries and archive.entries[detcell].fingerprint==fps[0],'global_best':best.fingerprint==fps[0],'global_best_quality':best.reward,'global_best_fingerprint':best.fingerprint,'global_best_cell':bestcell,'future_survival':'UNKNOWN: no counterfactual denoising or future archive reconstruction'},'recorded_template_quality':float(src['quality']),'recorded_direct_quality':float(qualities[next(k for k,v in score_events.items() if v is off)][15]),'scoring_keypoints_dtype':str(off['keypoints'].dtype),'origin_dtype':str(src['source_origin'].dtype),'native_dtype':str(template.dtype),'config':{k:v for k,v in opp['config'].items() if k.startswith('qd_') or k in ['reward_mode','population_size','cem_iters']}})
 return {'schema':'n36-independent-bounded-cpu-selection-results-v1','source':SOURCE,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'torch_version':torch.__version__,'threads':1,'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'rows':rows}
try:
 result=run()
except Exception:
 errors.append(traceback.format_exc());result={'incomplete':True};print(errors[-1],file=sys.stderr)
result['errors']=errors
ref(__file__)
result['hash_manifest']=list(manifest.values())
(OUT/'replay-results-v3.json').write_text(json.dumps(serial(result),indent=2)+'\n')
print(json.dumps({'errors':errors,'rows':[{k:r[k] for k in ['attempt_id','step','control_replay','detour_minus_direct','detour_minus_template','same_cell_as_direct','detour_beats_direct_by_archive_order','one_update_counterfactual']} for r in result.get('rows',[])]},indent=2))
