"""Exactly one bounded selected-plan extraction, without canonical-history analysis."""
from pathlib import Path
import collections,csv,hashlib,importlib.util,io,json,math,os,subprocess,sys,time
import torch
HERE=Path(__file__).resolve().parent;W=HERE.parents[2]/'study_worktree';MANIFEST=HERE/'read-scope-v1.json'
SHA='65e0381d8ad3e1e9321be09b63e5cbf5a11ece46f1950adf76a2aceed640d452'
torch.set_num_threads(2)
def check(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(Path(p).read_bytes())}
def native_id(t):
 t=t.detach().cpu().contiguous();return sha(f'{t.dtype}:{tuple(t.shape)}:'.encode()+t.reshape(-1).view(torch.uint8).numpy().tobytes())
def fingerprint(t):return sha(t.float().contiguous().numpy().astype('<f4',copy=False).tobytes())
def bits(t):return ''.join('1' if x else '0' for x in t.tolist())
def unknown(reason):return {'status':'Unknown','reason':reason}
def main():
 started=time.monotonic();mb=MANIFEST.read_bytes();check(sha(mb)==SHA,'scope drift');scope=json.loads(mb)
 check(not torch.cuda.is_initialized(),'CUDA initialized');check(subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==scope['source_commit'],'source drift')
 for f in scope['source_files'].values():check(sha(Path(f['path']).read_bytes())==f['sha256'],'source byte drift')
 dp=Path(scope['source_files']['core/rdt_libero_action_converter.py']['path']);spec=importlib.util.spec_from_file_location('selected_plan_decoder',dp);decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)
 allowed={str(Path(b['path']).resolve()) for a in scope['attempts'] for b in a['bundle_refs']};roots=[str(HERE.parents[2].resolve()),'/mnt/data/shared2/hynx/VLA-Pilot++'];blocked=[]
 def guard(event,args):
  if event!='open':return
  name,mode,flags=args
  if isinstance(name,int):return
  p=str(Path(os.fsdecode(name)).resolve());write=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  if any(p.startswith(r+'/') for r in roots):
   if write and not p.startswith(str(HERE)+'/'):raise RuntimeError('write outside diagnostic')
   if not write and p not in allowed and not p.startswith(str(HERE)+'/'):blocked.append(p);raise RuntimeError('read outside exact frozen bundle scope')
 sys.addaudithook(guard)
 boundaries=[];pairs=[];loaded=0;attempt_stats=[]
 for a in scope['attempts']:
  byid={b['decision_id']:b for b in a['boundaries']};audited={d['decision_id']:d for d in a['native_audit_guided_decisions']};selected={}
  for f in a['bundle_refs']:
   bb=Path(f['path']).read_bytes();check(sha(bb)==f['sha256'],'bundle drift');payload=torch.load(io.BytesIO(bb),map_location='cpu',weights_only=True);loaded+=1
   check(payload['schema']=='qd-ed-decision-evidence-v1','bundle schema')
   check([{k:e[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')} for e in payload['events']]==f['events'],'index association')
   # Only allowed selected events are retained or inspected; all score/canonical payloads are ignored.
   for e in payload['events']:
    if e['event'] in {'decision_context','policy_action_decode','decision_committed','final_selection'}:
     kinds=selected.setdefault(e['decision_id'],{});check(e['event'] not in kinds,'duplicate selected event');kinds[e['event']]=e
  own=[]
  for meta in sorted(a['boundaries'],key=lambda x:x['global_step']):
   did=meta['decision_id'];kinds=selected.get(did,{});base={'task':a['task'],'attempt_id':a['attempt_id'],'decision_id':did,'step':meta['global_step'],'reset_sequence':meta['reset_sequence']}
   missing=[k for k in ['decision_context','policy_action_decode','decision_committed'] if k not in kinds]
   if missing:
    own.append({**base,'record_status':'Unknown','reason':'missing '+','.join(missing)});continue
   context=kinds['decision_context'];cv=context['values'];de=kinds['policy_action_decode'];dv=de['values'];co=kinds['decision_committed'];raw=dv.get('selected_latent');chunk=dv.get('action_chunk')
   check(all(e['decision_id']==did and e['reset_sequence']==meta['reset_sequence'] and e['global_step']==meta['global_step'] for e in kinds.values()),'boundary event identity')
   check([kinds[k]['sequence'] for k in ('decision_context','policy_action_decode','decision_committed')]==[meta['selected_event_sequences'][k][0] for k in ('decision_context','policy_action_decode','decision_committed')],'selected index association')
   check(isinstance(raw,torch.Tensor) and raw.ndim==3 and raw.shape[0]==1 and raw.shape[2]==128 and bool(torch.isfinite(raw).all()),'selected latent')
   check(fingerprint(raw[0])==dv['selected_canonical_fingerprint'],'selected fingerprint')
   full=decoder.rdt_action_to_libero_raw(raw[:,:16,:]);check(full.shape[1]>=8 and torch.equal(full[:,:8],chunk) and torch.equal(chunk,co['values']['action_chunk']) and co['values']['execution_horizon']==8,'saved prefix decode/commit')
   dispatch=meta['dispatch_steps'];n=len(dispatch)
   check(0<n<=8 and dispatch==list(range(meta['global_step'],meta['global_step']+n)) and meta['dispatch_reset_sequences']==[meta['reset_sequence']]*n,'native audited action count/reset index')
   check(meta['event_counts']['executed_action']==meta['event_counts']['step_returned']==n,'index executed count')
   guided=bool(cv.get('use_guidance') and cv.get('providers'));target_index=None;availability=unknown('no terminal population in same selected bundle');selected_idx=None;target_evidence=None
   if 'final_selection' in kinds:
    fv=kinds['final_selection']['values'];check(torch.equal(fv['selected_latent'].float(),raw.float()) and fv['selected_canonical_fingerprint']==dv['selected_canonical_fingerprint'],'final-selected identity')
    selected_idx=fv['selected_index'];tv=fv.get('terminal_population',{});target_index=tv.get('grasp_selection',{}).get('target_index')
    if guided:
     check(did in audited and audited[did]['selected_index']==selected_idx and audited[did]['selected_fingerprint']==dv['selected_canonical_fingerprint']
           and audited[did]['actual_prefix_length']==n and audited[did]['selected_native_sha256']==native_id(fv['selected_latent'][0]),'accepted guided audit binding')
     check(target_index==audited[did]['n5_grasp_selection']['target_index'],'audited target')
    pop=fv.get('population')
    if isinstance(pop,torch.Tensor) and pop.ndim==3 and pop.shape[1]>=8 and pop.shape[2]==128:
     check(torch.equal(pop[selected_idx:selected_idx+1].float(),raw.float()),'terminal selected binding')
     pc=(decoder.rdt_action_to_libero_raw(pop[:,:8,:])[:,:,6]>0).sum(1)
     availability={'status':'recorded_same_bundle','positive_counts':pc.tolist(),'histogram_0_to_8':torch.bincount(pc,minlength=9).tolist(),'positive_candidates':int((pc>0).sum()),'fully_positive_candidates':int((pc==8).sum())}
   elif guided:check(False,'guided selection missing despite accepted audit')
   tracker=cv.get('keypoint_tracking_snapshot');identity=unknown('target_index or passive tracker snapshot unavailable');target_position=None
   if type(target_index) is int and isinstance(tracker,dict) and type(tracker.get('instance_id')) is int and type(tracker.get('generation')) is int and isinstance(tracker.get('targets'),dict):
    tv=tracker['targets'].get(str(target_index))
    if isinstance(tv,dict) and tv.get('valid') is True and tv.get('status') in {'tracked','static_background'}:
     hashes=[p.get('source_text_sha256') or p.get('original_code_sha256') for p in cv.get('providers',[])]
     if hashes and all(isinstance(x,str) and len(x)==64 for x in hashes):
      identity={'status':'recorded','tracker_instance':tracker['instance_id'],'tracker_generation':tracker['generation'],'target_index':target_index,'target_tracking_status':tv['status'],'provider_hashes':hashes}
      kp=cv.get('keypoints')
      if isinstance(kp,torch.Tensor) and kp.ndim==2 and kp.shape[1]==3 and target_index<len(kp) and bool(torch.isfinite(kp[target_index]).all()):target_position=kp[target_index].tolist()
    else:identity=unknown('tracked target invalid/unavailable');identity['recorded_target_status']=tv
   before=(full[0,:8,6]>0);tail=(full[0,8:16,6]>0) if full.shape[1]>=16 else None
   row={**base,'record_status':'verified','event_sequences':{k:e['sequence'] for k,e in kinds.items()},'stage':cv.get('stage'),'previous_stage':cv.get('previous_stage'),'previous_decision_id':cv.get('previous_decision_id'),'use_guidance':cv.get('use_guidance'),'guided':guided,'provider_count':len(cv.get('providers',[])),
    'target_identity':identity,'passive_tracker_snapshot':tracker,'target_position_m':target_position,'eef_position':unknown('EEF not recorded in decision_context; no projection/action-outcome expansion'),
    'selected_index':selected_idx,'selected_fingerprint':dv['selected_canonical_fingerprint'],'selected_native_dtype':str(raw.dtype),'selected_shape':list(raw.shape),
    'selected_prefix0_7_bits':bits(before),'selected_prefix_positive_count':int(before.sum()),'predicted_offsets8_15_bits':bits(tail) if tail is not None else None,'predicted_tail_positive_count':int(tail.sum()) if tail is not None else None,
    'executed_prefix_length':n,'executed_positive_count':int(before[:n].sum()),'terminal_population_availability':availability,'selected_gripper_zero_values':int((raw[0,:16,10]==0).sum())}
   own.append(row)
  check(sum(r['executed_prefix_length'] for r in own if r['record_status']=='verified')==a['native_audit_observed_counts']['action_dispatch'],'audit total actions binding')
  for prev,nxt in zip(own,own[1:]):
   pair={'task':a['task'],'previous_decision_id':prev['decision_id'],'next_decision_id':nxt['decision_id'],'previous_step':prev['step'],'next_step':nxt['step']}
   if prev['record_status']!='verified' or nxt['record_status']!='verified':pair.update({'status':'Unknown','reason':'missing boundary evidence'});pairs.append(pair);continue
   flags={'adjacent_steps':nxt['step']==prev['step']+8,'previous_full_eight_executed':prev['executed_prefix_length']==8,
      'native_context_predecessor_matches':nxt['previous_decision_id']==prev['decision_id'],
      'same_reset':prev['reset_sequence']==nxt['reset_sequence'],'same_stage':prev['stage']==nxt['stage'],
      'same_guidance':prev['guided']==nxt['guided'],'both_guided':prev['guided'] and nxt['guided']}
   check(flags['native_context_predecessor_matches'],'predecessor mismatch')
   oldid,newid=prev['target_identity'],nxt['target_identity'];id_known=oldid['status']==newid['status']=='recorded'
   sameidentity=id_known and oldid==newid;flags.update({'target_identity_both_recorded':id_known,'same_recorded_target_identity':sameidentity})
   if not all(flags[k] for k in ['adjacent_steps','previous_full_eight_executed','same_reset']):category='incomplete_or_reset_boundary'
   elif not flags['same_stage']:category='stage_changed'
   elif not flags['same_guidance']:category='guidance_changed'
   elif not flags['both_guided']:category='both_unguided'
   elif not id_known:category='both_guided_same_stage_identity_Unknown'
   elif not sameidentity:category='both_guided_same_stage_identity_changed'
   else:category='strict_same_guided_stage_reset_target'
   tail=prev['predicted_offsets8_15_bits'];now=nxt['selected_prefix0_7_bits'];pc=prev['predicted_tail_positive_count'];nc=nxt['selected_prefix_positive_count']
   comparable=bool(tail is not None and flags['adjacent_steps'] and flags['previous_full_eight_executed'] and flags['same_reset'])
   pair.update({'status':'comparable_plan_bits' if comparable else 'Unknown','category':category,'flags':flags,
       'previous_stage':prev['stage'],'next_stage':nxt['stage'],'previous_guided':prev['guided'],'next_guided':nxt['guided'],
       'predicted_previous_offsets8_15_bits':tail,'next_selected_prefix0_7_bits':now,'predicted_positive_count':pc,'next_selected_positive_count':nc,
       'next_actual_prefix_length':nxt['executed_prefix_length'],'next_actual_positive_count':nxt['executed_positive_count'],
       'hamming_bits':sum(x!=y for x,y in zip(tail,now)) if comparable else None,
       'fully_positive_plan_then_nonpositive_or_mixed':bool(comparable and pc==8 and nc<8),
       'fully_positive_plan_then_all_nonpositive':bool(comparable and pc==8 and nc==0),
       'fully_positive_plan_then_mixed':bool(comparable and pc==8 and 0<nc<8),
       'next_terminal_availability':nxt['terminal_population_availability'],
       'target_displacement_m':math.dist(prev['target_position_m'],nxt['target_position_m']) if sameidentity and prev['target_position_m'] is not None and nxt['target_position_m'] is not None else None,
       'target_displacement_status':'recorded_policy_context_same_identity' if sameidentity and prev['target_position_m'] is not None and nxt['target_position_m'] is not None else 'Unknown',
       'eef_displacement_status':'Unknown; absent from decision_context',
       'physical_counterfactual':'Unknown; previous tail was never executed'})
   pairs.append(pair)
  boundaries.extend(own)
  attempt_stats.append({'task':a['task'],'attempt_id':a['attempt_id'],'boundaries':len(own),'guided_boundaries':sum(r.get('guided',False) for r in own),'native_action_count':a['native_audit_observed_counts']['action_dispatch']})
 check(len(boundaries)<=360 and loaded==360 and not blocked and not torch.cuda.is_initialized(),'bounded extraction')
 summary={}
 for category in sorted({p.get('category','Unknown') for p in pairs}):
  ps=[p for p in pairs if p.get('category','Unknown')==category];vs=[p for p in ps if p['status']=='comparable_plan_bits']
  summary[category]={'pairs':len(ps),'comparable':len(vs),'exact_bit_agreement':sum(p['hamming_bits']==0 for p in vs),'fully_positive_predicted':sum(p['predicted_positive_count']==8 for p in vs),'fully_positive_then_all_nonpositive':sum(p['fully_positive_plan_then_all_nonpositive'] for p in vs),'fully_positive_then_mixed':sum(p['fully_positive_plan_then_mixed'] for p in vs),'bit_hamming_total':sum(p['hamming_bits'] for p in vs)}
 result={'schema':'n23-planned-gripper-continuity-readonly-v1','scope':ref(MANIFEST),'script':ref(__file__),'source_commit':scope['source_commit'],'cpu_threads':2,'cuda_initialized':False,'blocked_reads':blocked,'selected_bundles_loaded_once':loaded,
     'attempts':attempt_stats,'boundary_count':len(boundaries),'pair_count':len(pairs),'summary_by_category':summary,'boundaries':boundaries,'pairs':pairs,'elapsed_seconds':time.monotonic()-started,
     'limitations':['Offsets8..15 are unexecuted model predictions, not observed future or counterfactual physics.','Same-guided stratum requires exact recorded Stage/reset/tracker instance+generation/target index/valid status/provider hashes; coordinate equality is never an identity proof.','Tracking fields are passive registry identity, not certainty about object contact or model-plan reliability.','No scores, quality or hypothetical trajectories recomputed. Terminal population availability only when present in same selected bundle.','EEF displacement Unknown because decision contexts do not record EEF position; no extra bundles sought.','Four completed chronological exposed Dev paths only; correlated observations, no independent control or success effect.']}
 f=HERE/'result-v1.json';check(not f.exists(),'immutable result');f.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 columns=['task','previous_step','next_step','status','category','predicted_previous_offsets8_15_bits','next_selected_prefix0_7_bits','predicted_positive_count','next_selected_positive_count','hamming_bits','fully_positive_plan_then_all_nonpositive','fully_positive_plan_then_mixed','target_displacement_m']
 with (HERE/'pairs-v1.csv').open('w',newline='') as fp:
  writer=csv.DictWriter(fp,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(pairs)
 print(json.dumps({'result':ref(f),'attempts':attempt_stats,'boundaries':len(boundaries),'pairs':len(pairs),'categories':summary,'cuda_initialized':False,'blocked_reads':blocked,'elapsed_seconds':result['elapsed_seconds']},indent=2))
if __name__=='__main__':main()
