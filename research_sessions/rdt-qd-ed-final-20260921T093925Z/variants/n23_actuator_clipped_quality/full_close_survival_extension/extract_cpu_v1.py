"""Native-prefix command availability only; no geometric/reward/ranking recomputation."""
from pathlib import Path
import collections,csv,hashlib,io,json,os,re,signal,sys,time
import torch
H=Path(__file__).resolve().parent;M=H/'read-scope-v1.json';EXPECTED='535f11b8c7fb73b27298487049144a5281c67acaa13ae51dfc3533d7fc2fb144'
torch.set_num_threads(2)
def check(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(Path(p).read_bytes())}
def native(t):
 t=t.detach().cpu().contiguous();return {'dtype':str(t.dtype),'shape':list(t.shape),'sha256':sha(f'{t.dtype}:{tuple(t.shape)}:'.encode()+t.reshape(-1).view(torch.uint8).numpy().tobytes()),'values':t.tolist()}
def grip(pop):
 check(isinstance(pop,torch.Tensor) and pop.ndim==3 and tuple(pop.shape[1:])==(64,128),'population shape')
 g=pop[:,:8,10];check(bool(torch.isfinite(g).all()),'nonfinite prefix gripper');return g,(g>=0).sum(1)
def stats(n):
 return {'histogram_0_to_8':torch.bincount(n,minlength=9).tolist(),'any_positive':int((n>0).sum()),'transient_positive_1_to_7':int(((n>0)&(n<8)).sum()),'full_positive':int((n==8).sum()),'row_positive_counts':n.tolist()}
def category(seq,terminal,selected):
 return 'never_full_positive' if not any(seq) else 'ever_full_positive_then_terminal_none' if terminal==0 else 'terminal_full_positive_not_selected' if selected!=8 else 'selected_full_positive'
def main():
 started=time.monotonic()
 def timeout(sig,frame):raise TimeoutError('240 second native extraction bound exceeded')
 signal.signal(signal.SIGALRM,timeout);signal.alarm(240)
 check(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not torch.cuda.is_initialized(),'CPU-only')
 mb=M.read_bytes();check(sha(mb)==EXPECTED,'frozen scope changed');scope=json.loads(mb)
 for s in scope['source_files'].values():check(sha(Path(s['path']).read_bytes())==s['sha256'],'frozen source changed')
 allowed={str(Path(b['path']).resolve()) for a in scope['attempts'] for b in a['bundles']};allowed.add(str(Path(scope['task0_closed_result']['path']).resolve()));roots=[str(H.parents[2].resolve()),'/mnt/data/shared2/hynx/VLA-Pilot++'];blocked_reads=[];blocked_dispatch=[]
 def guard(event,args):
  if event in {'subprocess.Popen','os.system','os.fork','os.posix_spawn','os.spawn','os.exec','socket.connect','socket.bind','socket.getaddrinfo'}:blocked_dispatch.append(event);raise RuntimeError('forbidden dispatch')
  if event=='import' and isinstance(args[0],str) and args[0].split('.')[0] in {'robosuite','mujoco','libero','libero_pro','requests','httpx'}:blocked_dispatch.append(event+':'+args[0]);raise RuntimeError('runtime import forbidden')
  if event!='open':return
  p,mode,flags=args
  if isinstance(p,int):return
  p=str(Path(os.fsdecode(p)).resolve());write=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  if any(p.startswith(r+'/') for r in roots):
   if write and not p.startswith(str(H)+'/'):raise RuntimeError('write outside diagnostic')
   if not write and p not in allowed and not p.startswith(str(H)+'/'):blocked_reads.append(p);raise RuntimeError('read outside exact scope')
 sys.addaudithook(guard)
 def no_cuda(*a,**kw):blocked_dispatch.append('CUDA init');raise RuntimeError('CUDA forbidden')
 torch.cuda._lazy_init=no_cuda
 decisions=[];batches=[];rounds=[];loaded=set();new_rows=0;prefix_zero_values=0
 for a in scope['attempts']:
  audits={d['decision_id']:d for d in a['native_audit_guided_decisions']};observed=set()
  for bref in a['bundles']:
   path=bref['path'];check(path not in loaded,'repeated native bundle');loaded.add(path);bb=Path(path).read_bytes();check(sha(bb)==bref['sha256'],'bundle hash')
   payload=torch.load(io.BytesIO(bb),map_location='cpu',weights_only=True);check(payload['schema']=='qd-ed-decision-evidence-v1','schema')
   check([{k:e[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')} for e in payload['events']]==bref['events'],'metered index association')
   # Never inspect projection tensors/provider returns/other canonical latent dimensions.
   wanted={'decision_context','canonical_candidate_batch','effective_quality','archive_parent_allocation','parent_allocation','final_selection','policy_action_decode','decision_committed'}
   kinds=collections.defaultdict(list);seq={}
   for e in payload['events']:
    if e['event'] in wanted:kinds[e['event']].append(e);seq[e['sequence']]=e
   def one(k):check(len(kinds[k])==1,'singleton '+k);return kinds[k][0]
   ctx=one('decision_context');cv=ctx['values'];did=ctx['decision_id'];step=ctx['global_step'];reset=ctx['reset_sequence'];check(did in audits and did not in observed,'guided decision identity');observed.add(did);audit=audits[did]
   check(audit['global_step']==step and cv['use_guidance'] and cv['providers'],'guided/source step')
   check(all(e['decision_id']==did and e['reset_sequence']==reset for es in kinds.values() for e in es),'decision/reset association')
   canon=kinds['canonical_candidate_batch'];check([e['values']['iter_idx'] for e in canon]==list(range(-1,10)),'11 canonical batch coverage')
   parents={e['values']['iter_idx']:e for e in kinds['parent_allocation']};alloc={e['values']['iter_idx']:e for e in kinds['archive_parent_allocation']};pas={x['iter_idx']:x for x in audit['parent_associations']}
   check(set(parents)==set(alloc)==set(pas)==set(range(10)),'10 parent rounds')
   known={};own_batches=[];own_rounds=[]
   for ce,source in zip(canon,audit['canonical_sources']):
    v=ce['values'];it=v['iter_idx'];g,n=grip(v['candidates']);check(g.shape==(16,8) and g.dtype==torch.bfloat16,'native gripper dtype/shape');prefix_zero_values+=int((g==0).sum())
    check(source['iter_idx']==it and source['canonical_sequence']==ce['sequence'],'canonical audit association');fps=v['canonical_fingerprints'];oids=v['occurrence_ids']
    check(len(fps)==len(oids)==16 and all(isinstance(x,str) and re.fullmatch('[0-9a-f]{64}',x) for x in fps),'recorded fingerprints')
    check(oids==[f'{did}:q{ce["sequence"]}:r{i}' for i in range(16)],'recorded occurrence identities')
    effective=[e for e in kinds['effective_quality'] if e['values']['scoring_batch_id']==source['scoring_batch_id']];check(len(effective)==1,'original costs missing')
    ev=effective[0]['values'];cost=ev['costs'];q=v['effective_quality'];check(ev['quality_mode']==v['quality_mode']=='actuator_clipped_provider_v1' and torch.equal(q,ev['quality']) and torch.equal(cost,-q) and cost.dtype==q.dtype==g.dtype,'original native cost/quality association')
    check(cost.shape==q.shape==(16,) and bool(torch.isfinite(cost).all()),'native costs')
    if it>=0:
     pe=parents[it];pv=pe['values'];ae=alloc[it];av=ae['values'];pa=pas[it];pg,pn=grip(pv['source_population']);indices=pv['parent_indices']
     check(pa['parent_sequence']==pe['sequence'] and pa['allocation_sequence']==ae['sequence'] and ae['sequence']<pe['sequence']<source['scoring_batch_id']<ce['sequence'],'causal round association')
     check(pv['elite_count']==0 and torch.equal(indices,torch.arange(16)) and pv['offspring_sources']==['qd_archive_offspring']*16,'original fixed ordered offspring contract')
     check(pv['source_fingerprints']==av['parent_fingerprints'] and pv['parent_fingerprints']==[pv['source_fingerprints'][i] for i in indices.tolist()] and torch.equal(pv['source_costs'],av['parent_costs']) and torch.equal(pv['source_quality'],av['parent_rewards']) and torch.equal(pv['parent_cell_ids'],av['parent_cell_ids']),'actual parent allocation source')
     parent_records=[];links=[]
     for slot in range(16):
      match=pa['slots'][slot];check(match['slot']==slot and match['matching_occurrence_ids'],'native audit slot association')
      originals=[known[oid] for oid in match['matching_occurrence_ids']]
      for old in originals:check(old['fingerprint']==pv['source_fingerprints'][slot] and old['native_cost']==float(pv['source_costs'][slot]) and old['native_quality']==float(pv['source_quality'][slot]) and old['native_gripper']==native(pg[slot]),'exact recorded parent identity/gripper/cost association')
      p={'slot':slot,'cell_id':int(av['parent_cell_ids'][slot]),'fingerprint':pv['source_fingerprints'][slot],'positive_count':int(pn[slot]),'native_cost':float(pv['source_costs'][slot]),'matching_prior_occurrence_ids':match['matching_occurrence_ids']}
      parent_records.append(p)
     selected_counts=pn.index_select(0,indices)
     for child,source_slot in enumerate(indices.tolist()):links.append({'descendant_row':child,'descendant_occurrence_id':oids[child],'descendant_fingerprint':fps[child],'descendant_positive_count':int(n[child]),'descendant_native_cost':float(cost[child]),'recorded_source_slot':source_slot,'parent_fingerprint':pv['source_fingerprints'][source_slot],'parent_positive_count':int(pn[source_slot]),'same_recorded_fingerprint':fps[child]==pv['source_fingerprints'][source_slot]})
     rr={'task':a['task'],'decision_id':did,'global_step':step,'iter_idx':it,'allocation_sequence':ae['sequence'],'parent_sequence':pe['sequence'],'descendant_canonical_sequence':ce['sequence'],
      'source_pool':stats(pn),'selected_parent_pool':stats(selected_counts),'descendant_pool':stats(n),'native_parent_costs':native(pv['source_costs']),
      'parents':parent_records,'ordered_parent_descendant_associations':links,
      'full_parent_to_full_descendant':int(((selected_counts==8)&(n==8)).sum()),'full_parent_to_transient_descendant':int(((selected_counts==8)&(n>0)&(n<8)).sum()),'full_parent_to_zero_descendant':int(((selected_counts==8)&(n==0)).sum()),
      'nonfull_parent_to_full_descendant':int(((selected_counts<8)&(n==8)).sum()),'archive_insertion_replacement_history':'Unknown; not recorded'}
     own_rounds.append(rr);rounds.append(rr)
    records=[]
    for j in range(16):
     record={'row':j,'occurrence_id':oids[j],'fingerprint':fps[j],'positive_count':int(n[j]),'native_cost':float(cost[j]),'native_quality':float(q[j]),'native_gripper':native(g[j])}
     check(oids[j] not in known,'duplicate occurrence');known[oids[j]]=record;records.append(record)
    br={'task':a['task'],'decision_id':did,'global_step':step,'iter_idx':it,'canonical_sequence':ce['sequence'],'scoring_batch_id':source['scoring_batch_id'],**stats(n),'native_costs':native(cost),'native_quality':native(q),'full_positive_rows':[r for r in records if r['positive_count']==8],'row_fingerprints':fps,'row_occurrence_ids':oids,'prefix_gripper_native':native(g)}
    own_batches.append(br);batches.append(br);new_rows+=16
   fe=one('final_selection');fv=fe['values'];tv=fv['terminal_population'];fg,fn=grip(fv['population']);si=fv['selected_index'];selected_fingerprint=fv['selected_canonical_fingerprint'];last=own_batches[-1]
   check(native(fg)==last['prefix_gripper_native'] and native(tv['native_costs'])==last['native_costs']==audit['terminal_native_costs'] and selected_fingerprint==last['row_fingerprints'][si]==audit['selected_fingerprint'] and si==audit['selected_index'],'terminal exact prior association')
   check(tv['selected_occurrence_id']==last['row_occurrence_ids'][si] and torch.equal(tv['grasp_selection']['positive_commands'],fg>=0),'terminal occurrence/sign binding')
   decoded=one('policy_action_decode')['values'];committed=one('decision_committed')['values'];db=decoded['action_chunk'][0,:,6]
   check(decoded['selected_canonical_fingerprint']==selected_fingerprint and tuple(db.shape)==(8,) and torch.equal(db,committed['action_chunk'][0,:,6]) and torch.equal(db>0,fg[si]>=0),'selected decoded/committed gripper')
   ar=fv['archive_reference'];ag,an=grip(ar['population']);archive_rows=[]
   check(len(audit['archive_associations'])==len(ag),'final archive association coverage')
   for slot,aa in enumerate(audit['archive_associations']):
    check(aa['slot']==slot and aa['matching_occurrence_ids'],'archive slot');olds=[known[oid] for oid in aa['matching_occurrence_ids']];fp=olds[0]['fingerprint']
    for old in olds:check(old['fingerprint']==fp and old['native_gripper']==native(ag[slot]) and old['native_cost']==float(ar['costs'][slot]) and old['native_quality']==float(ar['rewards'][slot]),'archive native-audit association plus gripper/cost')
    archive_rows.append({'slot':slot,'cell_id':int(ar['cell_ids'][slot]),'positive_count':int(an[slot]),'native_cost':float(ar['costs'][slot]),'prior_recorded_fingerprint_bound_by_accepted_native_audit':fp,'matching_prior_occurrence_ids':aa['matching_occurrence_ids']})
   counts=[b['full_positive'] for b in own_batches];anycounts=[b['any_positive'] for b in own_batches];selected=int(fn[si]);target=tv['grasp_selection']['target_index'];check(target==audit['n5_grasp_selection']['target_index'],'target identity')
   loss=[]
   for i,r in enumerate(own_rounds):
    previous=counts[i];parent=r['selected_parent_pool']['full_positive'];desc=r['descendant_pool']['full_positive']
    if previous>0 and parent==0:loss.append({'round':i,'kind':'previous_canonical_full_positive_then_actual_allocated_parent_none','previous_canonical_full_count':previous,'parent_full_count':parent,'descendant_full_count':desc,'intermediate_archive_cause':'Unknown'})
    if parent>0 and desc==0:loss.append({'round':i,'kind':'actual_full_positive_parent_then_offspring_pool_none','previous_canonical_full_count':previous,'parent_full_count':parent,'descendant_full_count':desc,'intermediate_archive_cause':'not asserted'})
   decisions.append({'task':a['task'],'attempt_id':a['attempt_id'],'decision_id':did,'global_step':step,'bundle':bref,'stage':cv['stage'],'reset_sequence':reset,'target_index':target,'target_tracker_snapshot':cv.get('keypoint_tracking_snapshot'),
    'canonical_full_positive_counts':counts,'canonical_any_positive_counts':anycounts,'canonical_transient_positive_counts':[b['transient_positive_1_to_7'] for b in own_batches],
    'actual_parent_full_positive_counts':[r['selected_parent_pool']['full_positive'] for r in own_rounds],
    'initial_full_positive':counts[0],'terminal_full_positive':counts[-1],'terminal_any_positive':anycounts[-1],'final_archive_full_positive':int((an==8).sum()),'final_archive_any_positive':int((an>0).sum()),'selected_positive_count':selected,'selected_full_positive':selected==8,'selected_index':si,'selected_fingerprint':selected_fingerprint,'selected_occurrence_id':tv['selected_occurrence_id'],'selected_native_cost':float(tv['native_costs'][si]),
    'category':category(counts,counts[-1],selected),'observed_pool_level_losses':loss,'archive':{'summary':stats(an),'native_costs':native(ar['costs']),'rows':archive_rows},'source':'new_native_tasks1to3'})
  check(observed==set(audits),'decision coverage');print(json.dumps({'task':a['task'],'decisions':len(observed),'elapsed_seconds':time.monotonic()-started}),flush=True)
 check(len(decisions)==124 and len(batches)==1364 and new_rows==21824 and len(rounds)==1240 and len(loaded)==124,'bounded totals')
 native_elapsed=time.monotonic()-started;signal.alarm(0);check(native_elapsed<=240,'time')
 oldref=scope['task0_closed_result'];ob=Path(oldref['path']).read_bytes();check(sha(ob)==oldref['sha256'],'closed task0 changed');old=json.loads(ob);task0=[]
 for r in old['decisions']:
  bs=[b for b in old['batches'] if b['decision_id']==r['decision_id']];counts=[b['histogram_0_to_8'][8] for b in bs];anycounts=[b['positive_candidates'] for b in bs];af=r['archive']['histogram_0_to_8'][8];selected=r['selected_positive_commands']
  task0.append({'task':0,'decision_id':r['decision_id'],'global_step':r['global_step'],'canonical_full_positive_counts':counts,'canonical_any_positive_counts':anycounts,'canonical_transient_positive_counts':[b['positive_candidates']-b['histogram_0_to_8'][8] for b in bs],'actual_parent_full_positive_counts':[rr['histogram_0_to_8'][8] for rr in r['rounds']],
    'initial_full_positive':counts[0],'terminal_full_positive':counts[-1],'terminal_any_positive':anycounts[-1],'final_archive_full_positive':af,'final_archive_any_positive':r['archive']['positive_candidates'],'selected_positive_count':selected,'selected_full_positive':selected==8,'selected_index':r['selected_index'],'selected_native_cost':r['selected_native_cost'],'category':category(counts,counts[-1],selected),'source':'closed_task0_JSON_only'})
 all_decisions=task0+decisions;summaries=[]
 for task in [0,1,2,3,'new1to3','all0to3']:
  ds=[r for r in all_decisions if r['task']==task] if type(task) is int else decisions if task=='new1to3' else all_decisions
  summaries.append({'task':task,'decisions':len(ds),'categories':dict(collections.Counter(r['category'] for r in ds)),
   'never_any_positive':sum(not any(r['canonical_any_positive_counts']) for r in ds),'ever_any_but_never_full_positive':sum(any(r['canonical_any_positive_counts']) and not any(r['canonical_full_positive_counts']) for r in ds),
   'initial_full_positive_available':sum(r['initial_full_positive']>0 for r in ds),'initial_none_but_later_full_positive':sum(r['initial_full_positive']==0 and any(r['canonical_full_positive_counts']) for r in ds),
   'terminal_none_but_final_archive_full_positive':sum(r['terminal_full_positive']==0 and r['final_archive_full_positive']>0 for r in ds),
   'final_archive_full_positive_decisions':sum(r['final_archive_full_positive']>0 for r in ds)})
 hist=[sum(b['histogram_0_to_8'][i] for b in batches) for i in range(9)]
 # Representative choice is fixed chronological first per category, never outcome-based.
 reps={}
 for r in sorted(decisions,key=lambda r:(r['task'],r['global_step'])):reps.setdefault(r['category'],{'task':r['task'],'global_step':r['global_step'],'decision_id':r['decision_id']})
 check(not blocked_reads and not blocked_dispatch and not torch.cuda.is_initialized(),'guards')
 result={'schema':'n23-full-close-survival-extension-v1','scope':ref(M),'extractor':ref(__file__),'source_commit':scope['source_commit'],'native_elapsed_seconds':native_elapsed,'cpu_threads':2,'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'cuda_initialized':False,'blocked_reads':blocked_reads,'blocked_dispatch':blocked_dispatch,
  'new_native_coverage':{'decisions':124,'batches':1364,'rows':21824,'parent_rounds':1240,'parent_slots':1240*16,'bundles_each_once':124,'task0_tensor_reads':0,'canonical_histogram_0_to_8':hist,'gripper_exact_zero_values':prefix_zero_values},
  'summaries':summaries,'decisions':decisions,'task0_reused_decisions':task0,'batches':batches,'parent_rounds':rounds,'representatives_first_chronological_per_category':reps,
  'parent_to_descendant_slot_totals':{k:sum(r[k] for r in rounds) for k in ['full_parent_to_full_descendant','full_parent_to_transient_descendant','full_parent_to_zero_descendant','nonfull_parent_to_full_descendant']},
  'identity_scope':'Canonical and parent recorded full fingerprints plus exact first8gripper bytes/costs and accepted-native-audit occurrence associations. Final archive full-action association inherited from accepted native audit, not rehashed from forbidden non-gripper action components. All aliases preserved; unique insertion/replacement Unknown.',
  'limits':['All-positive is eight command labels, not measured closed fingers/contact/grasp/utility.','Parent/offspring association is the actually recorded ordered source-slot and subsequent canonical row; it does not identify unique original archive insertion or a single denoising operation as cause.','Payload serialization physically contains other tensors; only authorized fields inspected. No geometry, quality, score ranking or physical outcome recomputed.','Only completed tasks1..3 native plus closed task0JSON. No success-based selection, protected/current data, candidate/source/state/controller/budget mutation.']}
 f=H/'result-v1.json';check(not f.exists(),'immutable result');f.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 with (H/'all-decisions-v1.csv').open('w',newline='') as fp:
  cols=['task','global_step','initial_full_positive','canonical_full_positive_counts','canonical_any_positive_counts','actual_parent_full_positive_counts','terminal_full_positive','terminal_any_positive','final_archive_full_positive','final_archive_any_positive','selected_positive_count','category','source'];w=csv.DictWriter(fp,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(all_decisions)
 with (H/'canonical-batches-v1.csv').open('w',newline='') as fp:
  cols=['task','global_step','iter_idx','any_positive','transient_positive_1_to_7','full_positive','histogram_0_to_8'];w=csv.DictWriter(fp,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(batches)
 print(json.dumps({'result':ref(f),'coverage':result['new_native_coverage'],'summaries':summaries,'parent_transitions':result['parent_to_descendant_slot_totals'],'elapsed_seconds':native_elapsed},indent=2),flush=True)
if __name__=='__main__':main()
