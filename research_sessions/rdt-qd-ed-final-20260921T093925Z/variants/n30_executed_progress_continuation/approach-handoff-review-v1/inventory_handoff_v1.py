"""N30 handoff inventory only; no payload open, production import or tests."""
import os,sys,pathlib,json,hashlib,time,stat,collections,resource
os.sched_setaffinity(0,{0,1});resource.setrlimit(resource.RLIMIT_CPU,(300,300))
T=time.process_time();WALL=time.monotonic();H=pathlib.Path(__file__).resolve().parent;P=H.parent;R=P.parents[1];L=P/'feedback-repair-continuation-v1';D=P/'lineage-diagnostic-v1';B=D/'decode-v1';W=R/'study_worktree'
READS=[];DENIED=[];ALLOWED={str(pathlib.Path(__file__).resolve())};TOTAL=5896

def guard(ev,args):
 if ev=='open':
  p,mode,flags=args
  if isinstance(p,int):return
  p=pathlib.Path(os.path.abspath(os.fsdecode(p)));write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
  if p.suffix in {'.pt','.npy','.npz','.jpg','.png','.mp4','.avi'} or (write and p.parent!=H) or (not write and str(p) not in ALLOWED and p.parent!=H):
   DENIED.append({'event':ev,'path':str(p),'write':write});raise PermissionError(str(p))
 elif ev.startswith(('socket.','subprocess.')) or ev in {'os.system','os.fork','os.posix_spawn'}:raise PermissionError(ev)
 elif ev=='import' and args[0].split('.')[0] in {'torch','numpy','core','main','PIL','cv2'}:raise PermissionError(args[0])
sys.addaudithook(guard)
def read(p,expected=None,text=False,lines=False):
 global TOTAL
 p=pathlib.Path(p);ALLOWED.add(str(p));st=p.stat();assert stat.S_ISREG(st.st_mode) and st.st_size<=32*1024**2 and TOTAL+st.st_size<=64*1024**2
 with p.open('rb') as f:b=f.read(32*1024**2+1)
 TOTAL+=len(b);assert len(b)==st.st_size
 st2=p.stat();assert (st.st_ino,st.st_size,st.st_mtime_ns)==(st2.st_ino,st2.st_size,st2.st_mtime_ns)
 sha=hashlib.sha256(b).hexdigest();READS.append({'path':str(p),'bytes':len(b),'sha256':sha})
 assert expected is None or expected==sha,(p,sha)
 if text:return b.decode()
 return [json.loads(a) for a in b.splitlines() if a] if lines else json.loads(b)
def ref(x):return read(x['path'],x['sha256'])
def write(n,x):
 with (H/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def main():
 review=read(L/'root-terminal-review-v1.json','0a840aebc3e63fd3f9940b0bd51b042fb471385e6522a74493c916b7b8c39f91')
 read(B/'root-terminal-review-v1.json','09b8d5e77df586478958fe1a15ccfafcc66667de363a5326110423e4ffcf505e')
 read(B/'summary-v1.md',text=True);read(B/'result-v1.json','a365d087f905093a6a323ac1f559c032645f8235be3793431cf22540ff5c6ccf')
 source=ref(review['source']);plan=ref(review['plan']);result=ref(review['result']);assert source['commit']==review['source_commit']=='6292fc8cffad2eec0f789e023d835ad3c1df146a'
 cells=[c for c in review['accepted_cells'] if c['profile']=='N30'];assert [c['task_id'] for c in cells]==[0,1]
 assert [c['attempt_id'].rsplit('__',1)[-1] for c in cells]==['4300bcf89485','1e52b07e1725']
 episodes=[];total_stat=0;total_files=0
 for c in cells:
  assert c in result['accepted_cells'];row=next(x for x in plan['episodes'] if x['episode_key']==c['episode_key']);assert row['task_id']==c['task_id']
  output=pathlib.Path(c['attempt_result']['path']).parent;er=output/'eds_eval/decision_evidence/episode_000'
  terminal=ref(c['attempt_result']);ctx=ref(c['worker_context']);receipt=ref(c['worker_receipt']);audit=ref(c['audit'])
  assert terminal['outcome_valid'] is True and terminal['attempt_id']==ctx['attempt_id']==receipt['attempt_id']==c['attempt_id']
  assert ctx['source']==receipt['source']==source and receipt['accepted'] and audit['accepted'] and audit['evidence_complete']
  assert ctx['plan']==receipt['plan']==review['plan'] and receipt['context']==c['worker_context'] and receipt['audit_report']==c['audit']
  hashes={x['path']:x['sha256'] for x in receipt['evidence']['files']}
  indexrel='eds_eval/decision_evidence/episode_000/events.jsonl';statusrel=indexrel.replace('events.jsonl','status.json')
  status=read(er/'status.json',hashes[statusrel]);assert status['complete'] and not status['failed'] and status['decisions']==status['committed_decisions']==90
  metrics=read(output/'eds_eval/eds_metrics.jsonl',receipt['n30_metrics']['sha256'],lines=True)
  read(output/'eds_eval/episode_compute.jsonl',lines=True)
  entries=read(er/'events.jsonl',hashes[indexrel],lines=True);assert len(entries)==status['bundles']
  events=[];entry_by_name={};nextseq=1
  for entry in entries:
   name=entry['bundle'];assert pathlib.PurePath(name).name==name and name.startswith('bundle_') and name.endswith('.pt') and name not in entry_by_name
   entry_by_name[name]=entry;assert entry['events'][0]['sequence']==entry['first_sequence'] and entry['events'][-1]['sequence']==entry['last_sequence']
   for e in entry['events']:
    assert set(e)=={'sequence','event','decision_id','global_step','reset_sequence'} and e['sequence']==nextseq
    nextseq+=1;events.append({**e,'bundle':name})
  bydecision=collections.defaultdict(list)
  for e in events:bydecision[e['decision_id']].append(e)
  contexts=[e for e in events if e['event']=='decision_context'];assert len(contexts)==90
  starts=[e['global_step'] for e in contexts];assert starts==list(range(0,720,8))
  census=[]
  for e in contexts:
   rows=bydecision[e['decision_id']];cnt=collections.Counter(x['event'] for x in rows)
   assert cnt['decision_context']==cnt['policy_action_decode']==cnt['decision_committed']==1 and cnt['executed_action']==cnt['pre_reset_outcome']==cnt['step_returned']==8
   assert cnt['canonical_candidate_batch'] in (0,11)
   census.append({'decision_id':e['decision_id'],'step':e['global_step'],'reset_sequence':e['reset_sequence'],'event_counts':dict(cnt)})
  metric_steps=[m['global_step'] for m in metrics]
  assert metric_steps==[x['step'] for x in census if x['event_counts'].get('canonical_candidate_batch',0)>0]
  pair=next(((a,b) for a,b in zip(census,census[1:]) if a['event_counts'].get('canonical_candidate_batch',0)>0 and b['event_counts'].get('canonical_candidate_batch',0)==0),None)
  if pair is None:episodes.append({'cell':c,'handoff':'NOT_FOUND'});continue
  a,b=pair;assert b['step']==a['step']+8
  wanted=set(['decision_context','n30_observation_context','n30_initial_proposal','n30_selected_native_plan','final_selection','n30_decode_binding','policy_action_decode','n30_commit_binding','decision_committed','executed_action','pre_reset_outcome','n30_actual_ack','step_returned'])
  selected=[];pairs=[]
  for decision in pair:
   did=decision['decision_id'];subset=bydecision[did]
   names={e['bundle'] for e in subset if e['event'] in wanted}
   for name in sorted(names):
    p=er/name;assert p.resolve()==p and not any(x.is_symlink() for x in (p,er,er.parent,er.parent.parent));st=p.lstat();assert stat.S_ISREG(st.st_mode)
    ent=entry_by_name[name];rel=str(p.relative_to(output));assert hashes[rel]==ent['sha256']
    total_stat+=st.st_size;total_files+=1;assert total_stat<=64*1024**2 and total_files<=100
    exact=[e for e in ent['events'] if e['decision_id']==did and e['event'] in wanted]
    extras=[e for e in ent['events'] if e not in exact]
    selected.append({'path':str(p),'stat_bytes':st.st_size,'existing_index_sha256':ent['sha256'],'existing_receipt_sha256':hashes[rel],'payload_hash_measured':False,'stat_identity':{'device':st.st_dev,'inode':st.st_ino,'mtime_ns':st.st_mtime_ns},'decision_id':did,'requested_events':exact,'co_resident_event_counts':dict(collections.Counter(e['event'] for e in extras)),'co_resident_events':extras})
   ordered=[]
   commit=next(e for e in subset if e['event']=='decision_committed')
   for s in range(decision['step'],decision['step']+8):
    kinds={k:[e for e in subset if e['event']==k and e['global_step']==s] for k in ('action_dispatch','executed_action','pre_reset_outcome','step_returned')};assert all(len(v)==1 for v in kinds.values())
    seq=[v[0]['sequence'] for v in kinds.values()];assert commit['sequence']<seq[0] and seq==sorted(seq)
    ordered.append({'step':s,**{k:{q:v[0][q] for q in ('sequence','bundle','reset_sequence')} for k,v in kinds.items()}})
   pairs.append({'decision':decision,'ordered_actual_feedback':ordered})
  assert len({x['path'] for x in selected})==len(selected)
  identity_keys=('stage','current_stage','use_guidance','global_step','episode','task_id')
  episode={'cell':c,'metric_steps':metric_steps,'guided_metric_identity_fields':[{k:m[k] for k in identity_keys if k in m} for m in metrics], 'complete_decision_census':census,'first_realized_eds_handoff':pairs,'containers':selected,'stat_bytes':sum(x['stat_bytes'] for x in selected),'count':len(selected),'metadata_identity_checks':'PASS','source_guidance_boolean_values':'UNKNOWN_INDEX_HAS_NO_VALUES','index_ref':{'path':str(er/'events.jsonl'),'sha256':hashes[indexrel]}}
  episodes.append(episode)
 write('handoff-bindings.disabled.v1.json',{'schema':'n30-first-realized-eds-handoff-bindings-v1','executable':False,'tensor_decode_authorized':False,'sampling':'all2 acceptedN30 cells; first consecutive canonical-EDS->no-canonical pair in full index, complete metrics reconciled','episodes':episodes,'limits':{'episodes':2,'decisions':4,'files':total_files,'stat_bytes':total_stat,'loads_per_file':1},'payload_hash_semantics':'Copied bound index/receipt only; no payload open/hash/decode.'})
 write('metadata-summary-v1.json',{'episodes':[{'task':e['cell']['task_id'],'metric_steps':e.get('metric_steps'),'pairs':[z['decision'] for z in e.get('first_realized_eds_handoff',[])],'container_count':e.get('count'),'stat_bytes':e.get('stat_bytes'),'guided_metric_identity_fields':e.get('guided_metric_identity_fields')} for e in episodes],'total_files':total_files,'total_stat_bytes':total_stat})
 print(json.dumps({'pairs':[(e['cell']['task_id'],[p['decision']['step'] for p in e['first_realized_eds_handoff']]) for e in episodes],'files':total_files,'stat_bytes':total_stat}))

error=None
try:main()
except BaseException as e:error={'type':type(e).__name__,'message':str(e)};raise
finally:
 write('metadata-resource-v1.json',{'reads':READS,'bytes_including_initial_scope':TOTAL,'cpu_seconds':time.process_time()-T,'wall_seconds':time.monotonic()-WALL,'affinity':[0,1],'threads_environment':2,'denied':DENIED,'error':error,'payload_opens':0,'payload_hash_measurements':0,'payload_decodes':0,'reader_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()})
