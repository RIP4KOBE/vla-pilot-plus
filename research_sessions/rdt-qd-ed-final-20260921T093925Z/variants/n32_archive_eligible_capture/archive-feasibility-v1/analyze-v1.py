#!/usr/bin/env python3
"""Bounded N32 descriptive CPU feasibility; no owning-state writes or audit replay."""
import os
for k,v in {'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','NUMEXPR_NUM_THREADS':'2','PYTHONDONTWRITEBYTECODE':'1'}.items():os.environ[k]=v
import sys,time,json,pathlib,hashlib,resource,subprocess,signal,collections,importlib,importlib.util,types,io,dataclasses,traceback
BASE=pathlib.Path(__file__).resolve().parent
WORK=BASE.parent/'implementation_worktree'
SCOPE_HASH='67c3bc258e6f9d97a9133fe8c3f11c59d6c1b89bb12bf1ede2ca5addce82ccce'
COMMAND="CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python ../archive-feasibility-v1/analyze-v1.py"
def digest(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def save(name,x): (BASE/name).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def check(ok,msg):
 if not ok:raise ValueError(msg)
LIMITATIONS=[
 'Descriptive counterfactual on listed accepted N31 Dev opportunities only; no task success, physical capture, fresh efficacy or scientific promotion is established.',
 'Recorded provider recognition/target index are inherited from accepted evidence. Provider files were not accessed or executed; internal packet/tracker/provider hash consistency was checked, not independent source-template recognition.',
 'Original native cell assignments/projections/rewards are inherited. No GPU cell arithmetic, projection, reward, model or simulation recomputation; this is not a rerun of the accepted auditor.',
 'Counterfactual selection does not alter subsequent recorded N31 archives: each opportunity starts from its factual preceding N31 archive, not an N32 rollout.',
 'Unknown/missing and contradictory associations are excluded from valid denominators and never counted as negative eligibility. Multiple identical occurrences are content associations, not unique lineage.',
 'CPU selector cost excludes future device transfer, runtime recording and production integration. Additional eligibility only supports later integration/auditor review, never GPU release.',
 'Only frozen listed bundles were decoded; omitted decisions/tasks are not negative evidence.'
]
def worker():
 start=time.monotonic(); cpu=time.process_time()
 resource.setrlimit(resource.RLIMIT_CPU,(600,600));resource.setrlimit(resource.RLIMIT_RSS,(4*1024**3,4*1024**3))
 # Address-space cap additionally makes the 4 GiB resident ceiling conservative.
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
 import torch
 torch.set_num_threads(2);torch.set_num_interop_threads(2)
 pkg=types.ModuleType('_n32_feasibility');pkg.__path__=[str(WORK/'core')];sys.modules[pkg.__name__]=pkg
 selector=importlib.import_module(pkg.__name__+'.qd_archive_eligible_capture')
 spec=importlib.util.spec_from_file_location('_n31_frozen_reference',WORK/'scripts/qd_ed_n31_reference.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
 same,optional,shape,native_id=ref.same,ref.optional,ref.shape,ref.native_id
 scope_path=BASE/'scope-v1.json';check(digest(scope_path)==SCOPE_HASH,'scope hash');scope=json.loads(scope_path.read_text())
 delivery=json.loads((BASE.parent/'cpu-executor-result-v1.json').read_text())
 expected={**delivery['unchanged_source_sha256'],'core/qd_archive_eligible_capture.py':delivery['changed_file_sha256']['core/qd_archive_eligible_capture.py']}
 sources={str(WORK/k):digest(WORK/k) for k in expected}
 for k,h in expected.items():check(sources[str(WORK/k)]==h,'source hash '+k)
 sources[str(pathlib.Path(__file__).resolve())]=digest(__file__)
 sources[str(BASE.parent/'hypothesis-and-cpu-scope-v1.md')]=digest(BASE.parent/'hypothesis-and-cpu-scope-v1.md')
 sources[str(BASE.parent/'root-cpu-delivery-review-v1.json')]=digest(BASE.parent/'root-cpu-delivery-review-v1.json')
 manifest=scope['input_manifest'];check(digest(manifest['path'])==manifest['sha256'],'input manifest hash')
 old=json.loads(pathlib.Path(manifest['path']).read_text());allowed={x['path']:x for x in old['inputs']}
 check(len({x['path'] for x in scope['inputs']})==len(scope['inputs']),'duplicate input path')
 for x in scope['inputs']:check(x==allowed.get(x['path']) and x['identity']['profile']=='N31' and x['identity']['split']=='dev','exact manifest N31 subset')
 results=[];decisions=[];inputs=[];errors=[];counts=collections.Counter();seen=set();selector_wall=[];selector_cpu=[]
 def eq(a,b):
  if torch.is_tensor(a) or torch.is_tensor(b):return same(a,b)
  if isinstance(a,dict) and isinstance(b,dict):return set(a)==set(b) and all(eq(a[k],b[k]) for k in a)
  if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):return len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
  return a==b
 def classify(msg):return 'Unknown_missing' if any(x in msg.lower() for x in ('missing','unavailable','unknown','incomplete','absent')) else 'invalid_contradiction'
 def process(events,ident,path):
  byseq={e['sequence']:e for e in events};check(len(byseq)==len(events),'duplicate event sequence')
  groups=collections.defaultdict(list)
  for e in events:groups[e['decision_id']].append(e)
  for did,evs in groups.items():
   kinds=collections.defaultdict(list)
   for e in evs:kinds[e['event']].append(e)
   if not kinds['n31_capture_dwell_opportunity']:continue
   key=(ident['task_id'],did);check(key not in seen,'decision split/duplicated across bundles');seen.add(key)
   ops=kinds['n31_capture_dwell_opportunity'];pending=[]
   try:
    def one(k):check(len(kinds[k])==1,'missing/duplicate '+k);return kinds[k][0]
    context=one('decision_context');cv=context['values'];pe=one('n31_observation_context');packet=pe['values']['packet']
    check(cv['use_guidance'] is True,'opportunity not guided')
    check(all(e['episode']==context['episode'] and (not e['event'].startswith('n31_') or e['reset_sequence']==context['reset_sequence']) for e in evs),'event decision/reset envelope')
    check(packet['episode']==context['episode'] and optional(packet['keypoints'],cv['keypoints']) and packet['tracker']==cv.get('keypoint_tracking_snapshot'),'packet/context contradiction')
    canon=kinds['canonical_candidate_batch'];caches=kinds['n31_canonical_cache'];updates=kinds['n31_archive_update']
    check(len(canon)==len(caches)==len(updates)==11 and len(ops)==10,'incomplete canonical opportunity coverage')
    check([e['values']['iter_idx'] for e in canon]==list(range(-1,10)),'canonical order')
    identity=caches[0]['values']['identity'];decision_id=(context['episode'],cv['stage'],context['global_step'])
    check(tuple(identity[k] for k in ('episode','stage','step'))==decision_id,'identity context contradiction')
    providers=cv['providers'];recognition=identity.get('provider')
    if recognition is not None:
     check(len(providers)==1 and recognition['source_text_sha256']==providers[0]['source_text_sha256'],'recorded provider hash contradiction')
    target=None;skip=None
    if recognition is None:skip='unrecognized_target'
    elif packet['keypoints'] is None:skip='target_unavailable'
    elif 'target_index' not in identity:skip='tracking_unavailable'
    else:
     idx=identity['target_index'];tr=packet['tracker'];check(type(idx)is int and 0<=idx<len(packet['keypoints']),'target index')
     check(isinstance(tr,dict) and identity['tracker_instance']==tr['instance_id'] and identity['tracker_generation']==tr['generation'],'tracker identity')
     ts=tr['targets'].get(str(idx));check(isinstance(ts,dict) and ts.get('valid')is True and ts['status']==identity['target_status'] and ts['status'] in ('tracked','static_background'),'target tracker state')
     target=packet['keypoints'][idx]
    archive={};entries=[];insert=0;bounds=None
    for b,(ca,ce,ue) in enumerate(zip(canon,caches,updates)):
     it=b-1;v=ce['values'];u=ue['values'];c=ca['values']
     actions=shape(c['candidates'],(16,64,128),True);quality=shape(c['effective_quality'],(16,),True)
     check(actions.dtype==quality.dtype and v['identity']==identity and v['iter_idx']==u['iter_idx']==it and v['occurrence_start']==16*b,'canonical identity/iteration')
     check(pe['sequence']<ce['sequence']<ca['sequence']<ue['sequence'],'canonical temporal order')
     role='canonical_initial' if it==-1 else 'canonical_offspring';site='initial_population' if it==-1 else 'rollout'
     check(v['role']==role and v['site']==site,'cache role/site')
     mask=torch.zeros((1,1,128),dtype=actions.dtype);mask[:,:,[10,39,40,41,42,43,44]]=1
     check(same(v['action_mask'],mask) and bool((actions*(1-mask)==0).all()),'canonical mask')
     source=byseq.get(v['scoring_batch_id']);xyz=None
     if source is None:
      check(v['scoring_batch_id'] is None and not providers and recognition is None and v['projection_status']=='Unknown_original_score_short_circuit' and v['projected_outcomes'] is None and v['source_origins'] is None and v['cast_origins'] is None and same(quality,torch.zeros_like(quality)),'missing/contradictory original score')
      effects=[e for e in kinds['effective_quality'] if e['values']['scoring_scope']=={'role':role,'iter_idx':it,'site':site}]
     else:
      check(source['event']=='scoring_inputs' and source['decision_id']==did and source['sequence']<ce['sequence'],'scoring batch binding')
      sv=source['values'];check(sv['scoring_scope']=={'role':role,'iter_idx':it,'site':site} and same(sv['samples'],actions),'canonical score population')
      xyz=shape(sv['projected_xyz'],(16,9,3),True)
      check(xyz.dtype==actions.dtype and v['projection_status']=='original_canonical' and same(v['projected_outcomes'],xyz[:,1:9]) and same(v['cast_origins'],xyz[:,0]),'original projection contradiction')
      check(optional(sv['keypoints'],packet['keypoints'].to(sv['keypoints']) if packet['keypoints'] is not None else None),'scoring target contradiction')
      check(len(v['source_origins'])==len(sv['projection_origin_sequences'])==16,'origin coverage')
      effects=[e for e in kinds['effective_quality'] if e['values']['scoring_batch_id']==source['sequence']]
     check(len(effects)==1 and same(effects[0]['values']['quality'],quality) and same(effects[0]['values']['costs'],-quality),'canonical quality/cost')
     current=[]
     for j in range(16):
      if xyz is not None:
       origin=byseq.get(sv['projection_origin_sequences'][j]);check(origin is not None,'missing origin');o=origin['values']
       check(origin['event']=='projection_origin' and origin['decision_id']==did and origin['sequence']<source['sequence'] and same(v['source_origins'][j],o['source_eef_position']) and same(o['cast_eef_start'],xyz[j,0]) and same(o['source_eef_position'].to(xyz),xyz[j,0]),'origin contradiction')
      current.append(dict(iteration=it,row=j,occurrence=len(entries)+j,plan=actions[j],projection=None if xyz is None else xyz[j,1:9],source_origin=None if xyz is None else v['source_origins'][j],cast_origin=None if xyz is None else xyz[j,0],projection_status=v['projection_status'],quality=quality[j],cost=-quality[j],fingerprint=ref.fingerprint(actions[j]),native_identity=native_id(actions[j]),scoring_batch_id=v['scoring_batch_id']))
     check(v['native_identities']==[r['native_identity'] for r in current] and c['canonical_fingerprints']==[r['fingerprint'] for r in current],'canonical byte commitments')
     if it>=0:
      op=ops[it];ov=op['values'];check(updates[b-1]['sequence']<op['sequence']<(source['sequence'] if source else ce['sequence']),'preceding archive opportunity timing')
      best_cell,best=min(archive.items(),key=lambda x:(-x[1]['reward'],x[1]['fingerprint'],x[0]))
      ar=dict(cell=best_cell,source_iter=best['source_iter'],insert_sequence=best['insert_sequence'],fingerprint=best['fingerprint'],native_identity=native_id(best['plan']))
      check(ov['iteration']==it and ov['identity']==identity and ov['archive']==ar and ov['slot']==15,'recorded global best contradiction')
      matches=[r for r in entries if r['iteration']==best['source_iter'] and r['fingerprint']==best['fingerprint'] and same(r['plan'],best['plan'])]
      check(matches and ov['matching_occurrences']==[r['occurrence'] for r in matches] and ov['association']==('unique_occurrence' if len(matches)==1 else 'identical_content_multiple_occurrences'),'best source occurrence contradiction')
      check(eq(ov['source'],matches[0]) and eq(ov['observation'],packet),'best source/observation contradiction')
      # Independent arithmetic parity for factual global-best proposal only.
      candidate,arrival,reason=(None,None,skip) if skip else ref.reconstruct(best['plan'],matches[0]['projection'],target,packet['hand_quaternion_xyzw'],packet['gripper_qpos'])
      check(optional(candidate,ov['candidate']) and arrival==ov['arrival_index'] and reason==ov['reason'],'factual best reference parity')
      occupied={cell:selector.QDArchiveEntry(e['plan'],e['reward'],e['cost'],torch.tensor(e['descriptor_xy_m']),e['fingerprint'],e['source_iter'],e['parent_cell_id'],e['insert_sequence']) for cell,e in archive.items()}
      kw=dict(decision_id=decision_id,iteration=it,action_mask=mask,target=target,hand_quaternion_xyzw=packet['hand_quaternion_xyzw'],gripper_qpos=packet['gripper_qpos'],target_recognized=recognition is not None)
      row=dict(task_id=ident['task_id'],decision_id=did,identity=identity,iteration=it,bundle=path,opportunity_sequence=op['sequence'],preceding_update_sequence=updates[b-1]['sequence'],canonical_occurrences=len(entries),occupied_cells=len(archive),global_best_cell=best_cell,recorded_best_reason=reason,recorded_best_changed=candidate is not None,parents=[])
      cache=selector.CanonicalCache(decision_id,entries)
      t=time.perf_counter();p=time.process_time()
      try:
       selected=selector.select_eligible_parent(occupied,cache,**kw)
       row['parents']=[dataclasses.asdict(x) for x in selected.parents]
       check(skip is None,'Unknown observation/recognition: '+str(skip))
       bp=next(x for x in selected.parents if x.cell_id==best_cell)
       check(bp.eligible==(candidate is not None) and bp.reason==reason,'selector best parity')
       row.update(status='valid',global_best_eligible=bp.eligible,any_eligible=selected.selected is not None,additional_secondary_eligible=not bp.eligible and selected.selected is not None,selected=None if selected.selected is None else dataclasses.asdict(selected.selected),selected_candidate_native_sha256=None if selected.candidate is None else native_id(selected.candidate))
      except (selector.AssociationError,ValueError) as exc:
       row.update(status=classify(str(exc)),error=str(exc),global_best_eligible=None,any_eligible=None,additional_secondary_eligible=None)
       # Retain parent-level diagnostics without converting a failed opportunity to negative.
       row['parents']=[]
       for cell,entry in occupied.items():
        try:
         partial=selector.select_eligible_parent({cell:entry},cache,**kw)
         row['parents'].append({**dataclasses.asdict(partial.parents[0]),'status':'associated' if skip is None else 'Unknown_observation'})
        except (selector.AssociationError,ValueError) as sub:
         row['parents'].append(dict(cell_id=cell,source_iter=entry.source_iter,fingerprint=entry.fingerprint,status=classify(str(sub)),error=str(sub)))
      selector_wall.append(time.perf_counter()-t);selector_cpu.append(time.process_time()-p)
      pending.append(row)
     entries.extend(current)
     cells=u['cell_ids'];check(type(cells)is torch.Tensor and cells.dtype==torch.int64 and cells.shape==(16,) and bool(((cells>=0)&(cells<16)).all()),'native cells')
     desc=shape(u['descriptors'],(16,2));lo=shape(u['bounds_lo'],(2,));hi=shape(u['bounds_hi'],(2,))
     check(desc.dtype==lo.dtype==hi.dtype==torch.float32 and bool((hi>lo).all()),'native descriptor bounds')
     if bounds is None:bounds=(lo,hi)
     check(same(lo,bounds[0]) and same(hi,bounds[1]),'fixed bounds contradiction')
     parent=u['parent_cell_ids'];check((parent is None) if it==-1 else (type(parent)is torch.Tensor and parent.shape==(16,) and parent.dtype==torch.int64),'parent cells')
     if it>=0:
      arc=kinds['archive_parent_allocation'][it]['values'];check(torch.equal(parent,arc['parent_cell_ids']),'archive parent cell association')
     for cell in sorted(set(cells.tolist())):
      choices=[r for r,cid in zip(current,cells.tolist()) if cid==cell];winner=min(choices,key=lambda r:(-float(r['quality']),r['fingerprint']));inc=archive.get(cell)
      if inc is None or (-float(winner['quality']),winner['fingerprint'])<(-inc['reward'],inc['fingerprint']):
       j=winner['row'];archive[cell]=dict(cell_id=cell,reward=float(winner['quality']),cost=float(winner['cost']),descriptor_xy_m=desc[j].tolist(),fingerprint=winner['fingerprint'],source_iter=it,parent_cell_id=None if parent is None else int(parent[j]),insert_sequence=insert,plan=winner['plan']);insert+=1
     check(u['archive']==[{k:x for k,x in e.items() if k!='plan'} for _,e in sorted(archive.items())],'recorded archive snapshot contradiction')
    results.extend(pending);decisions.append(dict(task_id=ident['task_id'],decision_id=did,status='reconstruction_verified',canonical_occurrences=len(entries),snapshots=11,opportunities=len(pending)))
   except Exception as exc:
    # Any reconstruction contradiction invalidates the entire decision, including earlier rows.
    msg=type(exc).__name__+': '+str(exc);errors.append(dict(task_id=ident['task_id'],decision_id=did,bundle=path,error=msg,traceback=traceback.format_exc()))
    for op in ops:
     results.append(dict(task_id=ident['task_id'],decision_id=did,iteration=op['values'].get('iteration'),bundle=path,status=classify(msg),error=msg,additional_secondary_eligible=None,global_best_eligible=None,parents=[]))
    decisions.append(dict(task_id=ident['task_id'],decision_id=did,status=classify(msg),error=msg))
 for i,x in enumerate(scope['inputs']):
  check(time.monotonic()-start<890,'measurement wall cap approaching')
  data=pathlib.Path(x['path']).read_bytes();h=hashlib.sha256(data).hexdigest();check(len(data)==x['bytes'] and h==x['sha256'],'payload hash/size '+x['path'])
  bundle=torch.load(io.BytesIO(data),map_location='cpu',weights_only=True);check(bundle['schema']=='qd-ed-decision-evidence-v1','bundle schema')
  process(bundle['events'],x['identity'],x['path']);inputs.append({**x,'verified_sha256':h,'verified_bytes':len(data)})
  counts.update(e['event'] for e in bundle['events']);del bundle,data
  check(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<4*1024**3,'RSS cap')
  if (i+1)%200==0:print(json.dumps({'verified_bundles':i+1,'opportunities':len(results),'wall_seconds':time.monotonic()-start}),flush=True)
 def summarize(rows):
  valid=[r for r in rows if r['status']=='valid'];abstain=[r for r in valid if not r['global_best_eligible']]
  additional=sum(r['additional_secondary_eligible'] for r in valid)
  return dict(listed_opportunities=len(rows),valid_opportunities=len(valid),unknown_opportunities=sum(r['status'].startswith('Unknown') for r in rows),invalid_contradiction_opportunities=sum(r['status']=='invalid_contradiction' for r in rows),global_best_eligible=sum(r['global_best_eligible'] for r in valid),valid_global_best_abstentions=len(abstain),additional_secondary_eligible=additional,additional_over_valid=None if not valid else additional/len(valid),additional_over_valid_best_abstentions=None if not abstain else additional/len(abstain),any_eligible=sum(r['any_eligible'] for r in valid),recorded_best_reasons=dict(collections.Counter(r.get('recorded_best_reason','Unknown') for r in rows)),parent_association_errors=dict(collections.Counter(p['error'] for r in rows for p in r['parents'] if 'error'in p)),ambiguous_parent_associations=sum(len(p.get('matching_occurrences',[]))>1 for r in rows for p in r['parents']))
 summary=summarize(results)
 result=dict(schema='n32-archive-feasibility-result-v1',node='15.2',status='descriptive_measurement_complete',scope_sha256=SCOPE_HASH,scope_decision_rule=scope['decision_rule'],selector_commit=scope['selector_commit'],command=COMMAND,cwd=str(WORK),source_sha256=sources,input_manifest=manifest,input_verifications=inputs,input_count=len(inputs),payload_bytes=sum(x['bytes'] for x in inputs),event_counts=dict(counts),summary=summary,per_task=[dict(task_id=t,**summarize([r for r in results if r['task_id']==t])) for t in range(6)],decisions=decisions,opportunities=results,reconstruction_errors=errors,limits=scope['limits'],timings=dict(worker_cpu_seconds=time.process_time()-cpu,worker_wall_seconds=time.monotonic()-start,max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,selector_calls=len(selector_wall),selector_and_failure_diagnostics_wall_seconds=sum(selector_wall),selector_and_failure_diagnostics_cpu_seconds=sum(selector_cpu),selector_call_max_wall_seconds=max(selector_wall,default=0)),limits_enforcement=dict(cpu='RLIMIT_CPU 600 seconds',wall='parent watchdog 900 seconds',memory='RLIMIT_AS and RLIMIT_RSS 4 GiB plus RSS watchdog',threads='two-CPU affinity; torch intra/inter-op=2 and BLAS environment=2',cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES']),limitations=LIMITATIONS,score=None,gpu_authorized=False,validation_authorized=False,formal_authorized=False,target_met=False)
 save('result-v1.json',result)
 print(json.dumps({'summary':summary,'timings':result['timings']}),flush=True)
def supervise():
 begin=time.monotonic();child_start=resource.getrusage(resource.RUSAGE_CHILDREN);reason=None;peak=0
 proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--worker'],cwd=WORK)
 while proc.poll() is None:
  try:
   st=pathlib.Path(f'/proc/{proc.pid}/status').read_text();rss=int(next(l.split()[1] for l in st.splitlines() if l.startswith('VmRSS:')))*1024;peak=max(peak,rss)
   if rss>=4*1024**3:reason='4 GiB RSS cap'
  except (FileNotFoundError,StopIteration):pass
  if time.monotonic()-begin>=900:reason='900 seconds wall cap'
  if reason:proc.kill();break
  time.sleep(.02)
 code=proc.wait();rusage=resource.getrusage(resource.RUSAGE_CHILDREN)
 if code!=0:
  save('result-v1.json',dict(schema='n32-archive-feasibility-result-v1',status='measurement_failed_Unknown',exit_code=code,error=reason or 'worker failed; see returned tool stderr',scope_sha256=SCOPE_HASH,command=COMMAND,source_sha256={str(pathlib.Path(__file__).resolve()):digest(__file__)},limitations=LIMITATIONS,gpu_authorized=False,target_met=False))
 result=json.loads((BASE/'result-v1.json').read_text());result['supervisor']=dict(exit_code=code,wall_seconds=time.monotonic()-begin,child_cpu_seconds=rusage.ru_utime+rusage.ru_stime-child_start.ru_utime-child_start.ru_stime,max_rss_bytes=rusage.ru_maxrss*1024,sampled_peak_rss_bytes=peak,cap_stop_reason=reason);save('result-v1.json',result)
 report=['# Node 15.2 bounded CPU archive feasibility','',f"Status: {result['status']}. Scope SHA256 `{SCOPE_HASH}`.",'']
 if 'summary'in result:
  s=result['summary'];report += [f"Verified {result['input_count']} exact listed bundles ({result['payload_bytes']} bytes). Reconstructed {sum(d['status']=='reconstruction_verified' for d in result['decisions'])} decisions. Denominator: {s['valid_opportunities']} valid of {s['listed_opportunities']} listed opportunities; {s['unknown_opportunities']} Unknown and {s['invalid_contradiction_opportunities']} contradictory opportunities excluded.",'',f"Global best eligible: {s['global_best_eligible']}/{s['valid_opportunities']}. Secondary-parent additional eligibility: **{s['additional_secondary_eligible']}/{s['valid_global_best_abstentions']} valid best-abstaining opportunities** ({s['additional_secondary_eligible']}/{s['valid_opportunities']} valid total).",'', '| Task | Listed | Valid | Best eligible | Additional | Unknown | Contradictory |','|---|---:|---:|---:|---:|---:|---:|']
  for t in result['per_task']:report.append('| '+ ' | '.join(str(t[k]) for k in ('task_id','listed_opportunities','valid_opportunities','global_best_eligible','additional_secondary_eligible','unknown_opportunities','invalid_contradiction_opportunities'))+' |')
  report+=['',f"Resource use: {result['supervisor']['child_cpu_seconds']:.3f} CPU seconds; {result['supervisor']['wall_seconds']:.3f} wall seconds; peak RSS {result['supervisor']['max_rss_bytes']} bytes. Limits: 600 CPU seconds / 900 wall seconds / two threads / 4 GiB; CUDA hidden.",'',f"Root decision rule unchanged: {result['scope_decision_rule']}",'']
  if s['additional_secondary_eligible']:report+=['Positive eligibility supports only later integration/auditor review. Unknown/contradictions still require bounded diagnosis. No GPU release.','']
  else:report+=['No positive eligibility established. Apply the root rule only with the stated valid denominator; Unknown/contradictions are not negative findings.','']
 report+=['Exact command:',f'```sh\n{COMMAND}\n```','', 'Analysis script: `analyze-v1.py`; detailed result and exact input/source hashes: `result-v1.json`; final output hashes: `output-hashes-v1.json`.','','Limitations:','']+['- '+x for x in LIMITATIONS]
 (BASE/'report-v1.md').write_text('\n'.join(report)+'\n')
 save('output-hashes-v1.json',dict(schema='n32-feasibility-output-hashes-v1',scope_sha256=SCOPE_HASH,outputs=[dict(path=str(BASE/n),sha256=digest(BASE/n),bytes=(BASE/n).stat().st_size) for n in ('analyze-v1.py','result-v1.json','report-v1.md')]))
 return code
if __name__=='__main__':
 if '--worker'in sys.argv:worker()
 else:sys.exit(supervise())
