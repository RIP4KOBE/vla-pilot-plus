"""N30 Phase A only: bounded JSON/index reads; tensor paths are stat-only."""
import os, sys, json, hashlib, time, pathlib, stat, collections, resource
os.sched_setaffinity(0,{0,1})
resource.setrlimit(resource.RLIMIT_CPU,(300,300))
T0=time.process_time(); WALL=time.monotonic()
D=pathlib.Path(__file__).resolve().parent
P=D.parent; L=P/'feedback-repair-continuation-v1'; W=P.parents[1]/'study_worktree'
SOURCE='6292fc8cffad2eec0f789e023d835ad3c1df146a'
READS=[]; ALLOWED={str(pathlib.Path(__file__).resolve())}; DENIED=[]
BUDGET=128*1024**2; consumed=0
for previous in ('preparation-read-record-v1.json','source-locator-record-v1.json','source-schema-record-v1.json'):
 x=json.loads((D/previous).read_text()); consumed+=sum(r['bytes'] for r in x['reads'])
 if previous=='preparation-read-record-v1.json':consumed+=x['scope_release_initial_read_bytes']
consumed+=sum(r['bytes'] for r in json.loads((D/'resource-metadata-v1.json').read_text())['reads'])

def guard(event,args):
 if event=='open':
  p=args[0]
  if isinstance(p,int):return
  p=pathlib.Path(os.fsdecode(p)); absolute=str(p.absolute()); mode=args[1];flags=args[2]
  writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
  if p.suffix in {'.pt','.npy','.npz'} or (writing and p.parent.resolve()!=D) or (not writing and absolute not in ALLOWED and p.parent.resolve()!=D):
   DENIED.append({'event':event,'path':absolute});raise PermissionError(absolute)
 elif event.startswith(('socket.','subprocess.')) or event in {'os.system','os.exec','os.fork'}:raise PermissionError(event)
 elif event=='import' and args[0].split('.')[0] in {'torch','numpy','core','requests'}:raise PermissionError(event+str(args[0]))
sys.addaudithook(guard)

def read(p,expected=None,cap=8*1024**2,jsonl=False,text=False):
 global consumed
 p=pathlib.Path(p).absolute();assert p.suffix in {'.json','.jsonl','.md','.py'}
 ALLOWED.add(str(p)); st=p.stat();assert stat.S_ISREG(st.st_mode) and st.st_size<=cap
 assert consumed+st.st_size<=BUDGET
 with p.open('rb') as f:b=f.read(cap+1)
 consumed+=len(b);assert len(b)==st.st_size and len(b)<=cap
 st2=p.stat();assert (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(st2.st_dev,st2.st_ino,st2.st_size,st2.st_mtime_ns)
 sha=hashlib.sha256(b).hexdigest();READS.append({'path':str(p),'bytes':len(b),'sha256':sha,'expected_sha256':expected})
 if expected:assert sha==expected,(p,sha,expected)
 if text:return b.decode()
 return [json.loads(line) for line in b.splitlines() if line] if jsonl else json.loads(b)

def ref(x):return read(x['path'],x['sha256'])
def write(n,x):
 with (D/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def shape(x,depth=2):
 if isinstance(x,dict):return {k:shape(v,depth-1) if depth>0 else type(v).__name__ for k,v in x.items()}
 if isinstance(x,list):return {'type':'list','length':len(x),'item':shape(x[0],depth-1) if x and depth>0 else None}
 return type(x).__name__
def scalar(x):return {k:v for k,v in x.items() if v is None or isinstance(v,(str,int,float,bool))}
def indexes():
 global consumed
 prev=json.loads((D/'resource-metadata-v2.json').read_text());consumed=prev['metadata_bytes_including_preparation']
 catalog=json.loads((D/'episode-metadata-catalog-v1.json').read_text())
 plan=ref(catalog['plan_ref']);source=ref(catalog['source_ref'])
 selected=[];allstats=[];total_bytes=0;total_count=0
 for ep in catalog['episodes']:
  cell=ep['cell'];output=pathlib.Path(cell['attempt_result']['path']).parent;er=pathlib.Path(ep['episode_root'])
  terminal=ref(cell['attempt_result']);ctx=ref(cell['worker_context']);receipt=ref(cell['worker_receipt'])
  assert terminal['identity']['profile']=='N30' and terminal['identity']['task_id']==cell['task_id']
  row=next(r for r in plan['episodes'] if r['episode_key']==cell['episode_key'])
  assert row['profile']=='N30' and row['task_id']==cell['task_id']
  assert ctx['profile']==receipt['profile']=='N30' and ctx['episode_key']==receipt['episode_key']==cell['episode_key']
  assert receipt['attempt_id']==cell['attempt_id'] and receipt['accepted'] is True and receipt['main_exit_code']==0
  assert ctx['source']==receipt['source']==source
  assert ctx['plan']==receipt['plan']==catalog['plan_ref'] and terminal['plan_sha256']==catalog['plan_ref']['sha256']
  assert receipt['context']==cell['worker_context'] and receipt['audit_report']==cell['audit'] and terminal['n23_worker_receipt']==cell['worker_receipt']
  assert pathlib.Path(ctx['output_dir']).resolve()==output.resolve()==pathlib.Path(terminal['output_dir']).resolve()
  metric_ref=receipt['n30_metrics']; mr=next(r for r in prev['reads'] if r['path']==str(output/'eds_eval/eds_metrics.jsonl'))
  assert metric_ref['present'] is True and metric_ref['sha256']==mr['sha256']
  ordered=[m for m in ep['metric_rows'] if m['progress'] is not None]
  steps=[m['top_identity']['global_step'] for m in ordered];assert steps==sorted(set(steps))
  active=[m for m in ordered if m['progress']['active'] is True]
  first=min(active,key=lambda m:m['top_identity']['global_step']) if active else None
  if first is None:
   selected.append({'cell':cell,'selection':'NO_ACTIVE_DECISION'});continue
  step=first['top_identity']['global_step'];assert first['top_identity']['episode']==0
  indexref=next(x for x in ep['index_receipt_refs'] if x['path'].endswith('/events.jsonl'))
  entries=read(er/'events.jsonl',indexref['sha256'],cap=32*1024**2,jsonl=True)
  statusref=next(x for x in ep['index_receipt_refs'] if x['path'].endswith('/status.json'))
  sr=next(r for r in prev['reads'] if r['path']==str(er/'status.json'));assert sr['sha256']==statusref['sha256']
  assert len(entries)==ep['status']['bundles']
  receipt_hashes={str((output/x['path']).absolute()):x['sha256'] for x in ep['receipt_payload_refs']}
  assert len(receipt_hashes)==len(entries)
  seen=set();events=[];localstats=[];next_sequence=1
  for entry in entries:
   name=entry['bundle'];assert isinstance(name,str) and pathlib.PurePath(name).name==name and name.startswith('bundle_') and name.endswith('.pt')
   p=er/name;assert p not in seen;seen.add(p)
   for parent in (er,er.parent,er.parent.parent,p):assert not parent.is_symlink()
   assert p.resolve().parent==er.resolve()
   st=p.lstat();assert stat.S_ISREG(st.st_mode)
   total_count+=1;total_bytes+=st.st_size;assert total_count<=10000 and total_bytes<=2*1024**3
   assert receipt_hashes[str(p)]==entry['sha256']
   es=entry['events'];assert es and es[0]['sequence']==entry['first_sequence'] and es[-1]['sequence']==entry['last_sequence']
   for e in es:
    assert set(e)=={'sequence','event','decision_id','global_step','reset_sequence'} and e['sequence']==next_sequence
    next_sequence+=1;events.append({**e,'bundle':name})
   localstats.append({'path':str(p),'stat_bytes':st.st_size,'existing_index_sha256':entry['sha256'],'existing_receipt_sha256':receipt_hashes[str(p)],'payload_hash_measured':False,'events':es,'stat_identity':{'device':st.st_dev,'inode':st.st_ino,'mtime_ns':st.st_mtime_ns}})
  assert sum(x['stat_bytes'] for x in localstats)==ep['status']['bytes_written']
  dc=[e for e in events if e['event']=='decision_context' and e['global_step']==step];assert len(dc)==1
  did=dc[0]['decision_id'];subset=[e for e in events if e['decision_id']==did]
  counts=collections.Counter(e['event'] for e in subset)
  for kind,n in {'n30_initial_proposal':1,'canonical_candidate_batch':11,'canonical_candidate_identity':11,'parent_allocation':10,'archive_parent_allocation':10,'final_selection':1,'n30_selected_native_plan':1,'policy_action_decode':1,'decision_committed':1,'executed_action':8,'pre_reset_outcome':8,'n30_actual_ack':8}.items():assert counts[kind]==n,(cell['task_id'],kind,counts[kind])
  requested={'decision_context','n30_observation_context','n30_initial_proposal','canonical_candidate_batch','canonical_candidate_identity','parent_allocation','archive_parent_allocation','n30_selected_native_plan','final_selection','n30_decode_binding','policy_action_decode','n30_commit_binding','decision_committed','executed_action','pre_reset_outcome','n30_actual_ack','step_returned'}
  bundles={e['bundle'] for e in subset if e['event'] in requested}
  chosen=[]
  for b in localstats:
   if pathlib.Path(b['path']).name not in bundles:continue
   requested_events=[e for e in b['events'] if e['decision_id']==did and e['event'] in requested]
   extra=[e for e in b['events'] if e not in requested_events]
   chosen.append({**b,'requested_events':requested_events,'co_resident_event_counts':dict(collections.Counter(e['event'] for e in extra)),'co_resident_events':extra})
  # Ordering only; no action, outcome, target or numerical values are inspected.
  committed=next(e for e in subset if e['event']=='decision_committed')
  feedback=[]
  for s0 in range(step,step+8):
   e=[e for e in subset if e['global_step']==s0];k={kind:[x for x in e if x['event']==kind] for kind in ('action_dispatch','executed_action','pre_reset_outcome','n30_actual_ack','step_returned')}
   assert all(len(v)==1 for v in k.values())
   seq=[k[kind][0]['sequence'] for kind in k];assert seq==sorted(seq) and committed['sequence']<seq[0]
   feedback.append({'global_step':s0,**{kind:{key:v[0][key] for key in ('sequence','bundle')} for kind,v in k.items()}})
  allstats.extend(localstats)
  selected.append({'cell':cell,'selection':'EARLIEST_ACTIVE','global_step':step,'decision_id':did,'reset_sequence':dc[0]['reset_sequence'],'metric_rows':len(ordered),'active_rows':len(active),'progress_metadata':first['progress'],'index_ref':{'path':str(er/'events.jsonl'),'sha256':indexref['sha256']},'all_index_bundles':len(entries),'all_index_stat_bytes':sum(x['stat_bytes'] for x in localstats),'decision_event_counts':dict(counts),'requested_event_kinds':sorted(requested),'containers':chosen,'selected_container_count':len(chosen),'selected_container_bytes':sum(x['stat_bytes'] for x in chosen),'feedback_ordering':feedback,'source_plan_receipt_identity_checks':'PASS_METADATA_ONLY','native_payload_validity':'INHERITED_BOUND_SAME_WORKER_ATTESTATION_NOT_REPLAYED'})
 write('all-listed-payload-stat-v1.json',{'payload_open_hash_decode_count':0,'count':total_count,'stat_bytes':total_bytes,'files':[{k:v for k,v in x.items() if k!='events'} for x in allstats]})
 write('input-bindings.disabled.v1.json',{'schema':'n30-first-active-lineage-input-bindings-v1','executable':False,'payload_read_authorized':False,'decision_sampling':'all accepted N30 cells; earliest active global_step in frozen plan order','source':catalog['source_ref'],'plan':catalog['plan_ref'],'result':catalog['result_ref'],'episodes':selected,'limits':{'episodes':2,'decisions':2,'containers':sum(x.get('selected_container_count',0) for x in selected),'container_bytes':sum(x.get('selected_container_bytes',0) for x in selected),'loads_per_container':1},'hash_semantics':'Payload SHA copied from hash-verified index and receipt. No payload was opened or newly hashed.'})
 for x in selected:print(json.dumps({k:v for k,v in x.items() if k in ('global_step','decision_id','metric_rows','active_rows','all_index_bundles','all_index_stat_bytes','decision_event_counts','selected_container_count','selected_container_bytes')},ensure_ascii=False))

if __name__=='__main__':
 name=sys.argv[1];error=None
 try:
  if name=='indexes':indexes()
  else:raise ValueError(name)
 except BaseException as e:
  error={'type':type(e).__name__,'message':str(e)};raise
 finally:
  write('resource-'+name+'-v1.json',{'reader_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'reads':READS,'metadata_bytes_including_preparation':consumed,'cpu_seconds':time.process_time()-T0,'wall_seconds':time.monotonic()-WALL,'affinity':sorted(os.sched_getaffinity(0)),'denied':DENIED,'error':error,'tensor_opens':0,'production_imports':False})
