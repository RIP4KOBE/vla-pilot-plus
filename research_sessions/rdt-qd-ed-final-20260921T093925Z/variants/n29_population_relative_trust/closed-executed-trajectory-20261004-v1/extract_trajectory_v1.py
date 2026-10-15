from pathlib import Path
import os,sys,json,hashlib,time,resource,math,statistics,io,zipfile,tempfile,stat,traceback,signal
H=Path(__file__).resolve().parent; START=time.process_time(); WALL=time.monotonic()
os.sched_setaffinity(0,{0,1});resource.setrlimit(resource.RLIMIT_CPU,(570,570));resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('600s wall cap')));signal.alarm(600)
(H/'tmp').mkdir(exist_ok=True);tempfile.tempdir=str(H/'tmp')
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
manifest_bytes=(H/'input-manifest-v1.json').read_bytes(); M=json.loads(manifest_bytes)
assert hashlib.sha256(manifest_bytes).hexdigest()=='762bc524ab24425869e48ad3047ef98999b3744c9402a0a27de86bcaa61204bd'
assert len(M['attempts'])==24 and M['native_stat_bytes']<=4*1024**3
ALLOW={str(Path(b['path']).resolve()):b for a in M['attempts'] for b in a['containers']}; assert len(ALLOW)==M['container_count']
DEPS=[Path(sys.prefix).resolve(),Path('/usr/lib').resolve(),Path('/lib').resolve(),Path('/usr/share/zoneinfo').resolve()]
DENIED=[];NATIVE_READS=0;NATIVE_BYTES=0;ZIP_BYTES=0;ERROR=None;ROWS=[];CURRENT=None;SEEN=set();TORCH_IMPORTED=False
null_stat=Path('/dev/null').stat();assert stat.S_ISCHR(null_stat.st_mode)
def deny(event,path=None):
 DENIED.append({'event':event,'path':str(path) if path is not None else None});raise PermissionError('diagnostic scope denial: '+event)
def guard(event,args):
 if event.startswith(('socket.','subprocess.')) or event in ('os.system','os.exec','os.posix_spawn','pty.spawn'):deny(event)
 if event=='import' and str(args[0]).split('.')[0] in ('requests','httpx','openai','robosuite','mujoco','transformers','diffusers','core','main'):deny(event,str(args[0]))
 if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
  p=Path(os.fsdecode(args[0])).resolve();mode=args[1];flags=args[2];writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  if p==Path('/dev/null'):return
  if writing:
   if not p.is_relative_to(H):deny(event,p)
  elif str(p) not in ALLOW and not p.is_relative_to(H) and not any(p.is_relative_to(d) for d in DEPS) and str(p) not in ('/proc/self/maps',f'/proc/{os.getpid()}/maps','/proc/cpuinfo','/etc/ld.so.cache','/etc/localtime'):
   deny(event,p)
sys.addaudithook(guard)
def save(name,obj):
 text=json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n'
 if len(text.encode())>128*1024**2:raise ValueError('export cap')
 with (H/name).open('x') as f:f.write(text)
def finite_vec(v,expected=None,maxdim=32):
 if v is None:return None
 if torch.is_tensor(v):
  if v.device.type!='cpu' or v.ndim!=1 or v.numel()>maxdim:raise ValueError('vector shape/device')
  if expected is not None and v.shape!=(expected,):raise ValueError('vector fixed shape')
  vals=v.tolist()
 elif isinstance(v,(list,tuple)):
  vals=list(v)
  if len(vals)>maxdim or (expected is not None and len(vals)!=expected):raise ValueError('list fixed shape')
 else:raise TypeError('vector type')
 if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in vals):raise ValueError('vector nonfinite/type')
 return [float(x) for x in vals]
def arr(v,cols):
 if v is None:return None
 if not torch.is_tensor(v) or v.device.type!='cpu' or v.ndim!=2 or v.shape[1]!=cols or len(v)>1024:raise ValueError('array shape/device')
 if not bool(torch.isfinite(v).all()):raise ValueError('array nonfinite')
 return v.tolist()
def chunk(v):
 if not torch.is_tensor(v) or v.device.type!='cpu' or v.ndim!=3 or v.shape[0]!=1 or v.shape[-1]!=7 or not 8<=v.shape[1]<=64:raise ValueError('action chunk shape')
 if not bool(torch.isfinite(v[:,:8]).all()):raise ValueError('executed prefix nonfinite')
 return {'native_dtype':str(v.dtype),'shape':list(v.shape),'prefix8':v[0,:8].tolist()}
def norm(x):return math.sqrt(sum(v*v for v in x))
def diff(a,b):return [x-y for x,y in zip(a,b)]
def dist(a,b):return norm(diff(a,b))
def stats(v):
 v=sorted(v)
 return {'n':len(v),'mean':statistics.mean(v) if v else None,'median':statistics.median(v) if v else None,'p90':v[max(0,math.ceil(.9*len(v))-1)] if v else None,'min':v[0] if v else None,'max':v[-1] if v else None}
def tracking(v):
 if v is None:return None
 if not isinstance(v,dict):raise ValueError('tracking snapshot type')
 if 'capture_error_type' in v:return {'capture_error_type':str(v['capture_error_type'])[:128]}
 if not isinstance(v.get('targets'),dict):raise ValueError('tracking targets')
 return {'instance_id':v.get('instance_id'),'generation':v.get('generation'),'targets':{str(k):{'valid':d.get('valid'),'status':str(d.get('status'))[:128]} for k,d in v['targets'].items()}}
def process_selected(a,bd,obj,commands,outcomes,contexts):
 assert obj['schema']=='qd-ed-decision-evidence-v1'; events=obj['events'];assert len(events)==bd['co_resident_event_count']
 wanted={e['sequence']:e for e in bd['selected_events']};found=set()
 for e in events:
  if e.get('sequence') not in wanted:continue
  k=wanted[e['sequence']];assert all(e.get(q)==k[q] for q in ('sequence','event','decision_id','global_step','reset_sequence'))
  assert e['sequence'] not in found;found.add(e['sequence']);v=e['values'];step=e['global_step'];kind=e['event']
  ident={q:e[q] for q in ('sequence','decision_id','global_step','reset_sequence')};ident['container_path']=bd['path']
  if kind=='executed_action':
   assert step not in commands;commands[step]={'identity':ident,'action':finite_vec(v.get('action_numpy'),7),'native_dtype':str(v['action_numpy'].dtype)}
  elif kind=='pre_reset_outcome':
   assert step not in outcomes; ob=v.get('observation');assert isinstance(ob,dict)
   outcomes[step]={'identity':ident,'origin':v.get('origin'),'eef_pos':finite_vec(ob.get('robot0_eef_pos'),3),'eef_quat_xyzw':finite_vec(ob.get('robot0_eef_quat'),4),'gripper_qpos':finite_vec(ob.get('robot0_gripper_qpos')),'gripper_qvel':finite_vec(ob.get('robot0_gripper_qvel')),'native_dtypes':{n:str(ob[n].dtype) for n in ('robot0_eef_pos','robot0_eef_quat','robot0_gripper_qpos','robot0_gripper_qvel') if n in ob}}
  else:
   c=contexts.setdefault(step,{'step':step,'events':{}});assert kind not in c['events'];c['events'][kind]=ident
   if kind=='decision_context':c.update({'stage':v.get('stage'),'use_guidance':v.get('use_guidance'),'keypoints':arr(v.get('keypoints'),3),'tracking_snapshot':tracking(v.get('keypoint_tracking_snapshot'))})
   elif kind=='projection_origin':c['first_projection_origin']={'source_eef_position':finite_vec(v.get('source_eef_position'),3),'cast_eef_start':finite_vec(v.get('cast_eef_start'),3),'scope':'first recorded projection origin at this decision, not a selected-candidate or all-origin equality assertion'}
   elif kind=='policy_action_decode':c['decoded']=chunk(v['action_chunk']);c['decode_selected_canonical_fingerprint']=v.get('selected_canonical_fingerprint')
   elif kind=='decision_committed':c['committed']=chunk(v['action_chunk']);c['execution_horizon']=v.get('execution_horizon')
   elif kind=='final_selection':
    t=v.get('terminal_population');g=t.get('grasp_selection') if isinstance(t,dict) else None
    c['selection']={'selected_index':v.get('selected_index'),'selected_fingerprint':v.get('selected_fingerprint'),'selected_canonical_fingerprint':v.get('selected_canonical_fingerprint'),'selection_rule':v.get('selection_rule'),'target_index':g.get('target_index') if isinstance(g,dict) else None,'recognition_reason':g.get('recognition_reason') if isinstance(g,dict) else None,'target_field_present':isinstance(g,dict) and 'target_index' in g}
 assert found==set(wanted)
def summarize(a,commands,outcomes,contexts):
 assert set(commands)==set(outcomes)==set(range(720)) and set(contexts)=={0,176,352,528,712}
 for t in range(720):
  ci=commands[t]['identity'];oi=outcomes[t]['identity'];assert all(ci[k]==oi[k] for k in ('decision_id','global_step','reset_sequence')) and ci['sequence']<oi['sequence']
  assert ci['decision_id']==f'e0:d{t//8+1}:s{t//8*8}' and ci['reset_sequence']==0
  assert outcomes[t]['origin']=='actual_env_step_before_automatic_reset'
 for t,c in contexts.items():
  assert all(e['decision_id']==f'e0:d{t//8+1}:s{t}' and e['reset_sequence']==0 for e in c['events'].values());assert c['execution_horizon']==8
  actionseq=commands[t]['identity']['sequence'];commitseq=c['events']['decision_committed']['sequence']
  assert c['events']['decision_context']['sequence']<commitseq<actionseq
  if 'projection_origin' in c['events']:
   originseq=c['events']['projection_origin']['sequence'];assert originseq<actionseq
   c['projection_origin_timing']={'before_executed_action':True,'after_commit':originseq>commitseq}
  if t:assert outcomes[t-1]['identity']['sequence']<c['events']['decision_context']['sequence']
  decode=c['decoded']['prefix8'];commit=c['committed']['prefix8'];actual=[commands[k]['action'] for k in range(t,t+8)]
  c['decode_commit_prefix_max_abs_difference']=max(abs(x-y) for dr,cr in zip(decode,commit) for x,y in zip(dr,cr))
  c['committed_actual_translation_max_abs_difference']=max(abs(x-y) for cr,ar in zip(commit,actual) for x,y in zip(cr[:3],ar[:3]))
  c['committed_actual_gripper_sign_agrees']=all((cr[-1]>0)==(ar[-1]>0) for cr,ar in zip(commit,actual))
  if 'selection' in c:assert c['selection']['selected_canonical_fingerprint']==c['decode_selected_canonical_fingerprint']
  observed_pre=outcomes[t-1]['eef_pos'] if t else None;origin=c.get('first_projection_origin',{}).get('source_eef_position')
  anchor=observed_pre if observed_pre is not None else origin
  c['eef_context_anchor']={'values':anchor,'source':'previous_step_pre_reset_outcome' if observed_pre is not None else ('first_projection_origin_source_eef_position' if origin is not None else 'Unknown'),'step':t-1 if observed_pre is not None else t}
  c['origin_vs_previous_outcome_distance_m']=dist(origin,observed_pre) if origin is not None and observed_pre is not None else None
  c['keypoint_distances_m']=[{'keypoint_index':i,'distance_m':dist(anchor,k),'tracking':(c.get('tracking_snapshot') or {}).get('targets',{}).get(str(i))} for i,k in enumerate(c['keypoints'] or [])] if anchor is not None else None
  ix=c.get('selection',{}).get('target_index'); c['recorded_target_distance_m']=None
  if isinstance(ix,int) and not isinstance(ix,bool) and c['keypoints'] is not None and 0<=ix<len(c['keypoints']) and anchor is not None:c['recorded_target_distance_m']=dist(anchor,c['keypoints'][ix])
  c['active_target_identity']='recorded_terminal_grasp_selection_index' if c.get('selection',{}).get('target_field_present') and ix is not None else 'Unknown'
 initial=contexts[0].get('first_projection_origin',{}).get('source_eef_position')
 pos=[outcomes[t]['eef_pos'] for t in range(720)]; ds=[dist(pos[t],pos[t-1]) for t in range(1,720) if pos[t] is not None and pos[t-1] is not None]
 if initial is not None and pos[0] is not None:ds=[dist(initial,pos[0])]+ds
 angles=[]
 for t in range(1,720):
  qa=outcomes[t-1]['eef_quat_xyzw'];qb=outcomes[t]['eef_quat_xyzw']
  if qa is None or qb is None:continue
  na=norm(qa);nb=norm(qb)
  if not na or not nb:raise ValueError('zero quaternion')
  angles.append(2*math.acos(min(1.,abs(sum(x*y for x,y in zip(qa,qb)))/(na*nb))))
 jumps=[dist(commands[t]['action'][:3],commands[t-1]['action'][:3]) for t in range(1,720)]
 cj=[jumps[t-1] for t in range(8,720,8)]; signs=[1 if commands[t]['action'][-1]>0 else -1 if commands[t]['action'][-1]<0 else 0 for t in range(720)]
 runs=[];start=0
 for t in range(1,721):
  if t==720 or signs[t]!=signs[start]:
   end=t-1;qps=[outcomes[j]['gripper_qpos'] for j in range(start,t)]; qpv=[q for q in qps if q is not None];positions=[outcomes[j]['eef_pos'] for j in range(start,t)]; pre=pos[start-1] if start else initial
   spans=[abs(q[0]-q[1]) for q in qpv if len(q)==2]
   runs.append({'start_step':start,'end_step':end,'length':t-start,'command_sign':signs[start],'qpos_first_post':qps[0],'qpos_last_post':qps[-1],'abs_joint_qpos_difference':stats(spans),'eef_first_to_last_post_displacement_m':dist(positions[0],positions[-1]) if positions[0] is not None and positions[-1] is not None else None,'eef_pre_to_last_displacement_m':dist(pre,positions[-1]) if pre is not None and positions[-1] is not None else None});start=t
 qpos=[x['gripper_qpos'] for x in outcomes.values() if x['gripper_qpos'] is not None];dims={len(x) for x in qpos};assert len(dims)<=1
 qvel=[x['gripper_qvel'] for x in outcomes.values() if x['gripper_qvel'] is not None]
 row={'task_id':a['task_id'],'arm':a['arm'],'attempt_id':a['attempt_id'],'steps':720,'initial_eef_source_available':initial is not None,'known_eef_increment_count':len(ds),'eef_path_m':sum(ds),'eef_displacement_from_context_origin_m':dist(initial,pos[-1]) if initial is not None and pos[-1] is not None else None,'eef_first_last_post_displacement_m':dist(pos[0],pos[-1]) if pos[0] is not None and pos[-1] is not None else None,'eef_step_motion_m':stats(ds),'orientation_increment_rad':stats(angles),'orientation_path_rad':sum(angles),'command_translation_jump_all':stats(jumps),'command_translation_jump_chunk_boundary':stats(cj),'positive_command_steps':signs.count(1),'negative_command_steps':signs.count(-1),'zero_command_steps':signs.count(0),'command_sign_switches':len(runs)-1,'longest_positive_command_run':max((x['length'] for x in runs if x['command_sign']==1),default=0),'qpos_observations':len(qpos),'qpos_min_by_joint':[min(x[j] for x in qpos) for j in range(next(iter(dims)))] if dims else None,'qpos_max_by_joint':[max(x[j] for x in qpos) for j in range(next(iter(dims)))] if dims else None,'qvel_norm':stats([norm(x) for x in qvel]),'abs_joint_qpos_difference_positive':stats([abs(outcomes[t]['gripper_qpos'][0]-outcomes[t]['gripper_qpos'][1]) for t in range(720) if signs[t]>0 and outcomes[t]['gripper_qpos'] is not None and len(outcomes[t]['gripper_qpos'])==2]),'abs_joint_qpos_difference_negative':stats([abs(outcomes[t]['gripper_qpos'][0]-outcomes[t]['gripper_qpos'][1]) for t in range(720) if signs[t]<0 and outcomes[t]['gripper_qpos'] is not None and len(outcomes[t]['gripper_qpos'])==2]),'fixed_contexts':len(contexts),'recorded_target_context_count':sum(c['active_target_identity']!='Unknown' for c in contexts.values()),'unknown_physical_grasp':True}
 return row,runs
try:
 import torch
 TORCH_IMPORTED=True;torch.set_num_threads(2);torch.set_num_interop_threads(2)
 assert not torch.cuda.is_initialized()
 with (H/'trajectory-data-v1.jsonl').open('x') as output:
  for a in M['attempts']:
   CURRENT={'task_id':a['task_id'],'arm':a['arm'],'attempt_id':a['attempt_id']}; commands={};outcomes={};contexts={}
   for bd in a['containers']:
    p=Path(bd['path']);assert str(p) not in SEEN;SEEN.add(str(p));assert p.stat().st_size==bd['bytes']
    with p.open('rb') as stream:b=stream.read(bd['bytes']+1)
    NATIVE_READS+=1;NATIVE_BYTES+=len(b);assert len(b)==bd['bytes'] and hashlib.sha256(b).hexdigest()==bd['sha256'];assert NATIVE_BYTES<=4*1024**3
    bio=io.BytesIO(b)
    with zipfile.ZipFile(bio) as z:ZIP_BYTES+=sum(x.file_size for x in z.infolist())
    bio.seek(0);obj=torch.load(bio,weights_only=True,map_location='cpu');process_selected(a,bd,obj,commands,outcomes,contexts);del obj,b,bio
   row,runs=summarize(a,commands,outcomes,contexts);ROWS.append(row)
   text=json.dumps({'task_id':a['task_id'],'arm':a['arm'],'attempt_id':a['attempt_id'],'steps':[{'step':t,'command':commands[t],'outcome':outcomes[t]} for t in range(720)],'fixed_contexts':[contexts[t] for t in sorted(contexts)],'command_runs':runs},allow_nan=False,separators=(',',':'))+'\n';output.write(text);output.flush()
   if output.tell()>128*1024**2:raise ValueError('export cap')
   print(json.dumps({'complete':len(ROWS),'task':a['task_id'],'arm':a['arm'],'eef_path_m':row['eef_path_m'],'positive_steps':row['positive_command_steps'],'sign_switches':row['command_sign_switches'],'cpu_seconds':time.process_time()-START}),flush=True)
  assert len(ROWS)==24 and NATIVE_READS==M['container_count'] and NATIVE_BYTES==M['native_stat_bytes'];assert not torch.cuda.is_initialized()
 save('result-v1.json',{'schema':'n29-closed-executed-trajectory-result-v1','complete':True,'rows':ROWS,'input_manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),'reader_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'numerical_scope':'CPU descriptive actual commands/proprioception and sparse native keypoint snapshots; no unexecuted candidate analysis','errors':None})
except BaseException as e:
 ERROR={'type':type(e).__name__,'message':str(e),'current_attempt':CURRENT};save('failure-v1.json',{'error':ERROR,'completed_rows':ROWS,'native_reads':NATIVE_READS,'native_bytes':NATIVE_BYTES,'traceback':traceback.format_exc()});print(json.dumps(ERROR),flush=True)
finally:
 save('resource-reader-v1.json',{'cpu_seconds':time.process_time()-START,'wall_seconds':time.monotonic()-WALL,'native_container_reads':NATIVE_READS,'native_bytes':NATIVE_BYTES,'zip_uncompressed_bytes':ZIP_BYTES,'completed_attempts':len(ROWS),'address_space_limit_bytes':resource.getrlimit(resource.RLIMIT_AS)[0],'cpu_limit_seconds':resource.getrlimit(resource.RLIMIT_CPU)[0],'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'torch_imported':TORCH_IMPORTED,'cuda_initialized':torch.cuda.is_initialized() if TORCH_IMPORTED else None,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'affinity':sorted(os.sched_getaffinity(0)),'denied':DENIED,'error':ERROR,'model_api_sim_calls':0,'whole_container_decode':True,'runtime_dependency_exceptions':['readonly own /proc/self/maps','readonly /proc/cpuinfo','verified character /dev/null sink'],'successful_passes':1 if ERROR is None else 0})
if ERROR:sys.exit(1)
