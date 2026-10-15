"""One frozen container, CPU-only exploratory parent-domain measurement."""
import os, sys, resource, signal, time, pathlib, hashlib, json, io, zipfile, stat, types, tempfile, collections
START_WALL=time.monotonic(); START_CPU=time.process_time()
os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',CUDA_VISIBLE_DEVICES='')
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
resource.setrlimit(resource.RLIMIT_CPU,(60,60))
sys.dont_write_bytecode=True
H=pathlib.Path(__file__).resolve().parent; W=H.parents[2]/'study_worktree'
PROTOCOL_SHA='90b6dcfc459048293bb9f2ee51e4e12629c91f2c1ebfaff0e6b9c9b422906fa0'
SOURCE={
 'core/decision_evidence.py':'899659e6060822e6abf31c25ca3624066633527beb20a5883560a64ee29e2295',
 'core/rdt_policy_steer.py':'768fd9d1072f1f2abc0e3a1f87f764facd69b99e102399c041b73167b6ef00fe',
 'core/qd_actuator_clipped_rbf.py':'d0a516046f9d9efc8694916a9ff845c8b67868d8d7d2d01381894bcc05b89408',
 'core/qd_feasible_ray_update.py':'146163977866af87d2c643b0446be9ebac12f83cf9337d534b736874c623203e',
 'core/qd_feasible_ray_rbf.py':'f2494d1a2c55f4899d848d5f7e8af03cc8518cd53749c8875a117c1ff15a3207',
 'core/env_adapters/libero_adapter.py':'22e8be88e1a68bcffdd72536b79e7f9e4d56efdc0b12b5a0c3fb1c7877930c64'}
class Stop(Exception): pass
def need(condition,tag):
 if not condition: raise Stop(tag)
def digest(b): return hashlib.sha256(b).hexdigest()
def dump(name,value):
 (H/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def deadline(*args): raise Stop('wall60_exceeded')
signal.signal(signal.SIGALRM,deadline);signal.alarm(60)
meta={'schema':'n27-parent-domain-cpu-execution-v1','status':'STARTING','script_sha256':digest(pathlib.Path(__file__).read_bytes()),'payload_reads':0,'payload_bytes_returned':0,'cpu_decodes':0,'index_reads':0,'index_bytes_returned':0,'blocked_operations':[],'source_refs':[], 'model_calls':0,'api_calls':0,'simulation_steps':0,'cuda_initialized':None,'cpu_affinity':sorted(os.sched_getaffinity(0)),'threads':2,'as_limit_bytes':8*1024**3,'cpu_limit_seconds':60,'wall_limit_seconds':60}
need(len(meta['cpu_affinity'])==2,'affinity')
need(not (H/'execution-metadata-v1.json').exists(),'one_execution_no_retry')
dump('execution-metadata-v1.json',meta)
result={'schema':'n27-parent-domain-cpu-result-v1','status':'INCOMPLETE','rounds':[],'cuda_equivalence':'Unknown','model_transmission':'Unknown','task_efficacy':'Unknown','new_candidate_authorized':False}
stage='startup'
try:
 raw=(H/'protocol.frozen.v1.json').read_bytes();need(digest(raw)==PROTOCOL_SHA,'protocol_hash');P=json.loads(raw)
 meta['protocol_sha256']=PROTOCOL_SHA
 ip=pathlib.Path(P['index']['path']).resolve();bp=pathlib.Path(P['payload']['path']).resolve()
 exact={str(ip),str(bp)}|{str((W/x).resolve()) for x in SOURCE}
 prefix=os.path.realpath(sys.prefix)+os.sep
 self_maps=os.path.realpath('/proc/self/maps')
 temp_prefix=str(H)+os.sep
 tempfile.tempdir=str(H)
 need(stat.S_ISCHR(os.stat('/dev/null').st_mode),'devnull_not_character_device')
 def guard(event,args):
  if event=='open':
   name,mode,flags=args
   if isinstance(name,int):return
   p=os.path.realpath(os.fsdecode(name));writing=bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_APPEND|os.O_CREAT|os.O_TRUNC))
   okay=(p=='/dev/null' or p.startswith(temp_prefix) or (not writing and (p in exact or p.startswith(prefix) or p==self_maps)))
   if not okay:meta['blocked_operations'].append({'event':event,'path':p,'writing':writing});raise Stop('path_guard')
  elif event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.posix_spawn','os.exec','os.fork','os.forkpty','os.spawn'}:
   meta['blocked_operations'].append({'event':event});raise Stop('dispatch_network_guard')
 sys.addaudithook(guard)
 source_bytes={}
 for path,sha in SOURCE.items():
  data=(W/path).read_bytes();need(digest(data)==sha,'source_hash')
  meta['source_refs'].append({'path':str(W/path),'sha256':sha,'bytes':len(data)})
  if path in ('core/qd_actuator_clipped_rbf.py','core/qd_feasible_ray_update.py'):source_bytes[path]=data
 stage='torch_import'
 import torch
 torch.set_num_threads(2);torch.set_num_interop_threads(2)
 need(not torch.cuda.is_initialized(),'cuda_initialized')
 meta.update(torch_version=torch.__version__,cuda_initialized=False)
 def load_pure(name,path):
  mod=types.ModuleType(name);mod.__file__=str(W/path);sys.modules[name]=mod
  exec(compile(source_bytes[path],str(W/path),'exec'),mod.__dict__);return mod
 geom=load_pure('parent_audit_clipped_rbf','core/qd_actuator_clipped_rbf.py')
 ray=load_pure('parent_audit_feasible_ray','core/qd_feasible_ray_update.py')
 stage='first_index_line'
 with ip.open('rb',buffering=0) as f:line=f.readline(P['index']['max_bytes']+1)
 meta['index_reads']+=1;meta['index_bytes_returned']+=len(line)
 need(len(line)<=P['index']['max_bytes'] and line.endswith(b'\n'),'index_limit')
 need(digest(line)==P['index']['sha256'],'index_hash');idx=json.loads(line)
 need(idx['bundle']==bp.name and idx['sha256']==P['payload']['sha256'],'index_payload_binding')
 stage='one_payload_read'
 need(bp.stat().st_size==P['payload']['expected_bytes']<=P['payload']['max_input_bytes'],'input_stat_limit')
 with bp.open('rb',buffering=0) as f:data=f.read(P['payload']['max_input_bytes']+1)
 meta['payload_reads']+=1;meta['payload_bytes_returned']+=len(data)
 need(len(data)==P['payload']['expected_bytes'] and digest(data)==P['payload']['sha256'],'payload_bytes_hash')
 bio=io.BytesIO(data)
 with zipfile.ZipFile(bio) as z:
  infos=z.infolist();need(len(infos)<=65536,'zip_entries_limit')
  total=sum(x.file_size for x in infos);need(total<=P['payload']['max_zip_uncompressed_bytes'],'zip_uncompressed_limit')
  need(all(not x.flag_bits&1 and x.file_size>=0 for x in infos),'zip_flags')
 meta['zip_uncompressed_bytes']=total
 bio.seek(0);stage='one_weights_only_cpu_decode';meta['cpu_decodes']+=1
 payload=torch.load(bio,map_location='cpu',weights_only=True)
 del data,bio
 need(payload.get('schema')=='qd-ed-decision-evidence-v1','bundle_schema')
 # Size-only traversal of all co-resident storages; no unrelated values analyzed.
 storages={};stack=[payload];nodes=0
 while stack:
  obj=stack.pop();nodes+=1;need(nodes<=500000,'decoded_nodes_limit')
  if torch.is_tensor(obj):
   need(obj.device.type=='cpu' and obj.layout==torch.strided,'decoded_tensor_device_layout')
   st=obj.untyped_storage();storages[st.data_ptr()]=st.nbytes()
   need(sum(storages.values())<=P['payload']['max_distinct_decoded_storage_bytes'],'decoded_storage_limit')
  elif isinstance(obj,dict):stack.extend(obj.values())
  elif isinstance(obj,(list,tuple)):stack.extend(obj)
  else:need(obj is None or type(obj) in (str,bool,int,float),'decoded_object_type')
 meta['distinct_decoded_storage_bytes']=sum(storages.values());meta['decoded_tensor_storages']=len(storages)
 events=payload['events'];need(len(events)==len(idx['events']),'event_count')
 for event,entry in zip(events,idx['events'],strict=True):
  need({k:event.get(k) for k in entry}==entry,'index_event_identity')
  need(event['decision_id']==P['decision_id'] and event['global_step']==0 and event['reset_sequence']==0,'single_decision_identity')
 context=[e for e in events if e['event']=='decision_context'];need(len(context)==1 and context[0]['values']['use_guidance'] is True,'guided_context')
 pars=[e for e in events if e['event']=='parent_allocation'];ars=[e for e in events if e['event']=='archive_parent_allocation']
 need(len(pars)==len(ars)==10,'ten_parent_rounds')
 need([e['values']['iter_idx'] for e in pars]==list(range(10)),'parent_iterations')
 need([e['values']['iter_idx'] for e in ars]==list(range(10)),'archive_iterations')
 wit=[e for e in events if e['event']=='n27_rbf_witness']
 def native_bytes(x):return x.detach().contiguous().view(torch.uint8).numpy().tobytes()
 def fp32finger(x):return digest(x.detach().float().contiguous().numpy().astype('<f4',copy=False).tobytes())
 def duplicates(x):
  sizes=sorted(collections.Counter(native_bytes(row) for row in x).values(),reverse=True)
  return {'groups':len(sizes),'group_sizes':sizes,'duplicate_slots':len(x)-len(sizes),'duplicate_slot_fraction':(len(x)-len(sizes))/len(x)}
 def all_finite(x):return bool(torch.isfinite(x).all())
 same_origins=None;hyp=[];origin_errors={}
 for i in range(10):
  selected=[e for e in wit if e['values'].get('metadata',{}).get('call',{}).get('phase')=='rollout' and e['values']['metadata']['call'].get('iteration')==i]
  if len(selected)!=1:origin_errors[i]='missing_or_nonunique_rollout_origin_witness';continue
  e=selected[0];vs=e['values'];orig=vs.get('tensors',{}).get('source_origins');cast=vs.get('tensors',{}).get('cast_origins')
  valid=torch.is_tensor(orig) and tuple(orig.shape)==(16,3) and all_finite(orig) and torch.is_tensor(cast) and tuple(cast.shape)==(16,3)
  valid=valid and pars[i]['sequence']<e['sequence']<(pars[i+1]['sequence'] if i<9 else idx['last_sequence'])
  if not valid:origin_errors[i]='invalid_origin_shape_or_association';continue
  if not all(native_bytes(row)==native_bytes(orig[0]) for row in orig):origin_errors[i]='row_origins_differ';continue
  if same_origins is None:same_origins=native_bytes(orig)
  if native_bytes(orig)!=same_origins:origin_errors[i]='cross_iteration_origins_differ';continue
  hyp.append((i,e['sequence'],orig,cast))
 origins={i:(seq,o,cast) for i,seq,o,cast in hyp}
 result.update(decision_id=P['decision_id'],global_step=0,attempt_id=P['attempt_id'],source_commit=P['source_commit'],index_first_line_sha256=P['index']['sha256'],payload_sha256=P['payload']['sha256'],origin_assumption=P['origin_interpretation'])
 stage='ten_parent_measurements'
 cpu_rng=torch.random.get_rng_state().clone()
 for i,(pe,ae) in enumerate(zip(pars,ars,strict=True)):
  v=pe['values'];a=ae['values'];x=v['source_population'];ids=v['parent_indices']
  need(v['elite_count']==0 and not v.get('gripper_rescue_mode'),'no_elites_rescue')
  need(torch.is_tensor(x) and tuple(x.shape)==(16,64,128) and x.dtype in (torch.float32,torch.bfloat16) and all_finite(x),'parent_shape_dtype_finite')
  need(torch.is_tensor(ids) and tuple(ids.shape)==(16,) and ids.dtype==torch.int64 and bool(((ids>=0)&(ids<16)).all()),'parent_indices')
  need(ids.tolist()==list(range(16)),'original_allocation_slot_order')
  need(ae['sequence']<pe['sequence'],'archive_parent_order')
  fprints=[fp32finger(row) for row in x]
  need(fprints==v['source_fingerprints']==a['parent_fingerprints'],'parent_archive_fingerprints')
  need(v['parent_fingerprints']==[fprints[j] for j in ids.tolist()],'actual_parent_fingerprints')
  need(torch.equal(v['parent_cell_ids'],a['parent_cell_ids']),'actual_parent_cells')
  offspring=x.index_select(0,ids);prefix=offspring[:,:8,(39,40,41)]
  interior=(prefix>-1)&(prefix<1);boundary=(prefix==-1)|(prefix==1);outside=(prefix<-1)|(prefix>1)
  row={'iteration':i,'archive_sequence':ae['sequence'],'parent_sequence':pe['sequence'],'native_dtype':str(x.dtype),'source_shape':list(x.shape),'source_stride':list(x.stride()),'whole_action_duplicates':duplicates(offspring),'raw_xyz_duplicates':duplicates(prefix),'clipped_xyz_duplicates':duplicates(prefix.clamp(-1,1)),'components':384,'strict_interior_components':int(interior.sum()),'boundary_components':int(boundary.sum()),'outside_components':int(outside.sum()),'particle_interior_counts':[int(z) for z in interior.sum(dim=(1,2)).tolist()],'particles_with_support':int(interior.flatten(1).any(1).sum()),'hypothetical_update':None}
  if origin_errors:
   row['hypothetical_update_unknown_reason']='origin_set_not_completely_consistent';result['origin_issues']=origin_errors
  else:
   seq,orig,cast=origins[i];need(native_bytes(orig.to(x.dtype))==native_bytes(cast),'origin_cast_bytes')
   seen=[0]
   def project(candidate):
    j=seen[0];seen[0]+=1;need(j<16,'project_calls')
    start=orig[j].detach().to(dtype=candidate.dtype,device=candidate.device).clone()
    delta=candidate[0,:8,(39,40,41)]*.01
    return torch.cat((start.unsqueeze(0),start+torch.cumsum(delta,dim=0)),dim=0).unsqueeze(0)
   grad,evidence=geom.clipped_rbf_gradient(offspring,project=project,horizon=8)
   need(seen[0]==16,'sixteen_project_calls')
   operand=-1.*20.*grad[:,:8,(39,40,41)]
   feasible=ray.feasible_ray_update(prefix,operand);delta=feasible.prefix.float()-prefix.float();moving=operand!=0
   invariant=bool((~moving|interior).all()) and native_bytes(feasible.prefix[~moving])==native_bytes(prefix[~moving]) and int(((feasible.prefix<-1)|(feasible.prefix>1)).sum())==int(outside.sum())
   need(invariant,'feasible_invariants')
   row['hypothetical_update']={'arithmetic_backend':'cpu','reference_only_not_cuda_proof':True,'origin_witness_sequence':seq,'source_origin_dtype':str(orig.dtype),'all_origins_identical':True,'gradient_zero':evidence['zero_gradient'],'gradient_native_norm':evidence['gradient_before_normalization']['norm'],'operand_nonzero_components':int(moving.sum()),'operand_native_norm':float(torch.norm(operand)),'assigned_nonzero_components':int(torch.count_nonzero(delta)),'assigned_nonzero_particles':int(delta.ne(0).flatten(1).any(1).sum()),'assigned_delta_norm_fp32':float(torch.norm(delta)),'alpha_min':float(feasible.alpha.min()),'alpha_max':float(feasible.alpha.max()),'alpha_mean':float(feasible.alpha.mean()),'alpha_limited_particles':int((feasible.alpha<1).sum()),'alpha_zero_particles':int((feasible.alpha==0).sum()),'zero_operand_bytes_preserved':True,'new_outside_components':0,'strict_support_valid':True,'cpu_projector_calls':16}
  result['rounds'].append(row)
 need(torch.equal(cpu_rng,torch.random.get_rng_state()),'rng_unchanged')
 need(not torch.cuda.is_initialized(),'cuda_after')
 result['status']='COMPLETE' if not origin_errors else 'COMPLETE_DUPLICATES_SUPPORT_HYPOTHESIS_UNKNOWN'
 result['coverage']={'rounds':10,'parent_slots':160,'xyz_components':3840,'cpu_hypothetical_updates':sum(x['hypothetical_update'] is not None for x in result['rounds'])}
 result['aggregate']={k:sum(x[k] for x in result['rounds']) for k in ['strict_interior_components','boundary_components','outside_components','particles_with_support']}
 result['aggregate']['whole_action_unique_slots_sum']=sum(x['whole_action_duplicates']['groups'] for x in result['rounds'])
 result['aggregate']['zero_gradient_rounds']=sum(x['hypothetical_update']['gradient_zero'] for x in result['rounds'] if x['hypothetical_update'] is not None) if not origin_errors else None
 result['aggregate']['zero_assigned_update_rounds']=sum(x['hypothetical_update']['assigned_nonzero_components']==0 for x in result['rounds'] if x['hypothetical_update'] is not None) if not origin_errors else None
except BaseException as exc:
 result.update(status='INCOMPLETE',error_type=type(exc).__name__,error_tag=str(exc) if isinstance(exc,Stop) else 'external_exception_no_payload_export',error_stage=stage)
finally:
 signal.alarm(0)
 meta.update(status=result['status'],wall_seconds=time.monotonic()-START_WALL,cpu_seconds=time.process_time()-START_CPU,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,stage=stage,read_exceptions=['Python environment dependency reads','/proc/self/maps read only','/dev/null character-device sink','owned temporary files'],actual_payload_data_exported=False)
 if 'torch' in globals():meta['cuda_initialized']=torch.cuda.is_initialized()
 if meta['blocked_operations']:result['status']='INCOMPLETE_GUARD_DENIED';meta['status']=result['status']
 dump('result-v1.json',result);dump('execution-metadata-v1.json',meta)
 lines=['# 固定首 guided chunk 的 CPU 父代域检查','',f"状态：**{result['status']}**。一次已授权容器读取；无模型/API/仿真/GPU。CPU参考不能证明CUDA逐位结果、去噪后影响或任务收益。",'',f"输入读取{meta['payload_reads']}次／{meta['payload_bytes_returned']} bytes；weights_only CPU解码{meta['cpu_decodes']}次；耗时{meta['wall_seconds']:.3f}s，CPU{meta['cpu_seconds']:.3f}s，峰值RSS{meta['peak_rss_kib']} KiB（不是2GiB RSS承诺）。",'',f"脚本SHA256 `{meta['script_sha256']}`；协议SHA256 `{PROTOCOL_SHA}`。",'','| iter | full-action unique/16 | xyz unique/16 | clipped xyz unique/16 | interior/boundary/outside | CPU gradient zero | assigned changed components |','|---:|---:|---:|---:|---|---|---:|']
 for v in result['rounds']:
  z=v['hypothetical_update'];lines.append(f"| {v['iteration']} | {v['whole_action_duplicates']['groups']} | {v['raw_xyz_duplicates']['groups']} | {v['clipped_xyz_duplicates']['groups']} | {v['strict_interior_components']}/{v['boundary_components']}/{v['outside_components']} | {z['gradient_zero'] if z else 'Unknown'} | {z['assigned_nonzero_components'] if z else 'Unknown'} |")
 lines+=['','origin沿用同一决策原rollout witness，显式假设搜索期间当前EEF固定；它不是新pre-renoise测量。未分析或导出共存quality/provider-return/selection数值。全部10轮为固定分母，不按活跃性挑选；重复组相对其他组可共同移动，不能以重复率单独判定零梯度。','',f"原投影静态来源：{W/'core/env_adapters/libero_adapter.py'}:1631–1690，SHA256 {SOURCE['core/env_adapters/libero_adapter.py']}；policy:7695–7723。该纯CPU参考保留原origin cast→delta*.01→cumsum→加origin次序，未调用环境。",'',f"result SHA256 `{digest((H/'result-v1.json').read_bytes())}`；execution metadata SHA256 `{digest((H/'execution-metadata-v1.json').read_bytes())}`。"]
 if result['status'].startswith('INCOMPLETE'):lines+=['',f"停止阶段 {result.get('error_stage',stage)}；错误类型 {result.get('error_type','guard')}，tag {result.get('error_tag','guard_denied')}。不重试或扩读。"]
 (H/'report-v1.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({'status':result['status'],'coverage':result.get('coverage'),'aggregate':result.get('aggregate'),'payload_reads':meta['payload_reads'],'cpu_decodes':meta['cpu_decodes'],'guard_denials':len(meta['blocked_operations']),'wall_seconds':meta['wall_seconds']}))
