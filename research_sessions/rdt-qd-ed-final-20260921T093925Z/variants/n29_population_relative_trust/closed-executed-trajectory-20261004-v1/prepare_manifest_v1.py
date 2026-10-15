from pathlib import Path
import os,sys,json,hashlib,time,resource,traceback
H=Path(__file__).resolve().parent; M=H.parent/'closed-task-relevance-20261004-v1'
START=time.process_time(); WALL=time.monotonic(); resource.setrlimit(resource.RLIMIT_CPU,(60,60)); resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3)); os.sched_setaffinity(0,{0,1})
BYTES=0; REFS=[]; DENIED=[]; ALLOWED=set()
def load(p,expected=None):
 global BYTES
 p=Path(p).resolve(); n=p.stat().st_size
 if n>128*1024**2 or BYTES+n>512*1024**2: raise ValueError('metadata cap')
 b=p.read_bytes();BYTES+=len(b); sh=hashlib.sha256(b).hexdigest()
 if expected is not None and sh!=expected: raise ValueError('metadata hash')
 REFS.append({'path':str(p),'bytes':len(b),'sha256':sh});return json.loads(b)
def save(n,x):
 with (H/n).open('x') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
release=load(H/'root-release-v1.json','7128dfbfe0d12701abdf0405a7cadc3dae1bb9e2a90bee0c90cdb264d6a6bddd')
for k in ('preceding_metadata_review','preceding_delivery'):load(release[k]['path'],release[k]['sha256'])
delivery=load(M/'delivery-manifest-v1.json','d129e65cd86754f45cf4e6a0a90fd41507b81d9e291d2868692137d692212d79')
oldrefs={Path(v['path']).name:v for v in delivery['references']}
oldscope=load(M/'input-scope.frozen.v1.json',oldrefs['input-scope.frozen.v1.json']['sha256'])
oldinputs=load(M/'input-manifest-v1.json',oldrefs['input-manifest-v1.json']['sha256'])
expected={str(Path(x['path']).resolve()):x for x in oldinputs['files']}
assert oldscope['source_commit']=='d855cfd690482e018bb40ce98edec80fad9700e0'
assert {(x['task_id'],x['profile']) for x in oldscope['attempts']}=={(t,a) for t in range(6) for a in ('C0','Q0','N28','N29')}
ALLOWED={str(Path(next(f['path'] for f in x['files'] if f['role']=='events')).resolve()) for x in oldscope['attempts']}
def guard(event,args):
 if event.startswith(('socket.','subprocess.')) or event in ('os.system','os.exec','os.posix_spawn'):DENIED.append(event);raise PermissionError(event)
 if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
  p=Path(os.fsdecode(args[0])).resolve();mode=args[1];flags=args[2];write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  if (write and not p.is_relative_to(H)) or (not write and str(p) not in ALLOWED and not p.is_relative_to(H)):
   DENIED.append({'event':event,'path':str(p),'write':bool(write)});raise PermissionError('outside metadata scope')
sys.addaudithook(guard)
AT=[];NATIVE=0;INDEXCOUNT=0;error=None
try:
 for a in oldscope['attempts']:
  ep=Path(next(f['path'] for f in a['files'] if f['role']=='events')).resolve(); before=ep.stat();assert before.st_size==expected[str(ep)]['bytes']
  hh=hashlib.sha256();indexbytes=0;selected=[];counts={k:0 for k in ('executed_action','pre_reset_outcome')};steps={k:set() for k in counts};contextcounts={t:{} for t in (0,176,352,528,712)};seen_origin=set();seqprior=0
  with ep.open('rb') as f:
   while True:
    b=f.readline(16*1024**2+1)
    if not b:break
    if len(b)>16*1024**2:raise ValueError('index line cap')
    BYTES+=len(b);indexbytes+=len(b);hh.update(b)
    if BYTES>512*1024**2:raise ValueError('metadata cap')
    ent=json.loads(b);assert set(ent)=={'bundle','sha256','first_sequence','last_sequence','events'}
    assert isinstance(ent['bundle'],str) and Path(ent['bundle']).name==ent['bundle'] and ent['bundle'].endswith('.pt')
    assert ent['first_sequence']>seqprior and ent['last_sequence']>=ent['first_sequence'];seqprior=ent['last_sequence']
    want=[]
    for e in ent['events']:
     assert set(e)=={'sequence','event','decision_id','global_step','reset_sequence'}
     kind=e['event'];step=e['global_step'];use=False
     if kind in counts:
      assert isinstance(step,int) and 0<=step<720 and step not in steps[kind];steps[kind].add(step);counts[kind]+=1;use=True
     elif step in contextcounts and kind in ('decision_context','policy_action_decode','decision_committed','final_selection','projection_origin'):
      if kind!='projection_origin' or step not in seen_origin:
       use=True;contextcounts[step][kind]=contextcounts[step].get(kind,0)+1
       if kind=='projection_origin':seen_origin.add(step)
     if use:want.append(e)
    if want:
     p=(ep.parent/ent['bundle']).resolve();assert p.parent==ep.parent and p.is_file();size=p.stat().st_size;NATIVE+=size
     if NATIVE>4*1024**3:raise ValueError('native stat cap')
     selected.append({'path':str(p),'bytes':size,'sha256':ent['sha256'],'first_sequence':ent['first_sequence'],'last_sequence':ent['last_sequence'],'co_resident_event_count':len(ent['events']),'selected_events':want})
  assert indexbytes==before.st_size and hh.hexdigest()==expected[str(ep)]['sha256'];after=ep.stat();assert (after.st_size,after.st_mtime_ns)==(before.st_size,before.st_mtime_ns)
  assert all(v==set(range(720)) for v in steps.values())
  for t,d in contextcounts.items():
   assert all(d.get(k)==1 for k in ('decision_context','policy_action_decode','decision_committed'));assert d.get('final_selection',0)<=1 and d.get('projection_origin',0)<=1
  REFS.append({'role':'event_index','path':str(ep),'bytes':indexbytes,'sha256':hh.hexdigest(),'read_count':1});INDEXCOUNT+=1
  AT.append({'task_id':a['task_id'],'arm':a['profile'],'attempt_id':a['attempt_id'],'index_ref':REFS[-1],'counts':counts,'fixed_context_event_counts':contextcounts,'native_bytes':sum(x['bytes'] for x in selected),'containers':selected})
  print(json.dumps({'completed':len(AT),'task':a['task_id'],'arm':a['profile'],'containers':len(selected),'native_bytes':AT[-1]['native_bytes']}),flush=True)
 assert INDEXCOUNT==24
 save('input-manifest-v1.json',{'schema':'n29-closed-executed-native-inputs-v1','source_commit':oldscope['source_commit'],'release_sha256':'7128dfbfe0d12701abdf0405a7cadc3dae1bb9e2a90bee0c90cdb264d6a6bddd','selection':'all24 all720 executed_action/outcome; fixed contexts0,176,352,528,712','whole_selected_container_decode_authorized':True,'index_refs':REFS,'metadata_bytes':BYTES,'native_stat_bytes':NATIVE,'container_count':sum(len(a['containers']) for a in AT),'attempts':AT})
except BaseException as e:
 error={'type':type(e).__name__,'message':str(e)};save('manifest-error-v1.json',{'error':error,'completed_attempts':AT,'refs':REFS});print(json.dumps(error),flush=True)
finally:
 save('resource-manifest-v1.json',{'cpu_seconds':time.process_time()-START,'wall_seconds':time.monotonic()-WALL,'metadata_bytes':BYTES,'native_stat_bytes':NATIVE,'index_files':INDEXCOUNT,'denied':DENIED,'error':error,'tensor_reads':0,'affinity':sorted(os.sched_getaffinity(0))})
if error:sys.exit(1)
