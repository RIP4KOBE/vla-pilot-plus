"""Single CPU episode load; one original and one repaired N30-only replay."""
from pathlib import Path
import os,sys,json,hashlib,io,time,resource,tempfile,stat,importlib
J=Path(__file__).resolve().parent;I=J/'implementation';TMP=J/'cpu-fixtures';TMP.mkdir(exist_ok=True)
os.sched_setaffinity(0,{0,1})
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='2'
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True;sys.pycache_prefix=str(TMP/'empty-pycache');tempfile.tempdir=str(TMP)
resource.setrlimit(resource.RLIMIT_CPU,(870,880));resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
start=time.process_time();wall=time.monotonic();denied=[];reads={};total=0;old_calls=0;new_calls=0;events=[]
manifest_path=J/'input-manifest.frozen.v2.json';manifest_bytes=manifest_path.read_bytes();manifest=json.loads(manifest_bytes)
assert hashlib.sha256(manifest_bytes).hexdigest()=='b81311625cd09f7c9d7c73b629cb80a9b16a86b8f090d9ffcf7ab961839a46e2'
allowed={Path(x['path']).resolve() for x in manifest['metadata'].values()}|{Path(x['path']).resolve() for x in manifest['bundles']}|{Path(x['path']).resolve() for x in manifest['provider_sources']}
source_roots=[I/'scripts',I/'core',I/'utils'];dependency=Path(sys.base_prefix).resolve();maps=Path('/proc/self/maps').resolve();null=Path('/dev/null');assert stat.S_ISCHR(null.stat().st_mode)
outputs={J/'real-replay-v1.json',J/'real-replay-resource-v1.json',J/'first-triple-v1.json'}
assert not any(p.exists() for p in outputs)
def within(p,r):return p==r or r in p.parents
def fail(event,p):denied.append({'event':event,'path':str(p)});raise PermissionError('diagnostic guard: '+str(p))
def guard(event,args):
 if event.startswith(('socket.','subprocess.')) or event in {'os.system','os.fork','os.forkpty','os.exec','os.posix_spawn'}:fail(event,event)
 if event not in {'open','os.listdir','os.scandir'}:return
 raw=args[0]
 if isinstance(raw,int):return
 try:p=Path(os.fsdecode(raw)).absolute().resolve()
 except (TypeError,ValueError):fail(event,'non-path')
 if p==null:return
 writing=False
 if event=='open':
  mode=args[1];flags=args[2] or 0;writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
 if writing:
  if p in outputs or within(p,TMP):return
  fail(event,p)
 if p in allowed or p in {manifest_path,J/'replay_once_v1.py',maps,Path('/proc/cpuinfo')} or within(p,TMP):return
 if within(p,dependency) or within(p,Path('/usr/lib').resolve()) or within(p,Path('/lib').resolve()):return
 if event!='open':
  if within(p,I) or p in (J,*J.parents):return
 elif any(within(p,r) for r in source_roots) and p.suffix in {'.py','.pyi'}:return
 fail(event,p)
sys.addaudithook(guard);sys.path[:0]=[str(I)];result={'schema':'n30-terminal-feedback-real-replay-v1','attempt_id':manifest['attempt_id'],
 'input_manifest':{'path':str(manifest_path),'sha256':hashlib.sha256(manifest_bytes).hexdigest()},'original_receipt_stays_invalid':True,
 'scientific_acceptance':False,'generic_native_replay':False}
def read(r,cap):
 global total
 p=Path(r['path']);assert p.is_file() and not p.is_symlink() and p.stat().st_size==r['bytes']<=cap
 with p.open('rb') as f:data=f.read(cap+1)
 assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
 reads[str(p)]=reads.get(str(p),0)+1;total+=len(data);return data
def save(path,value):
 with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def description(v):
 if type(v) is bool:return {'type':'builtins.bool','value':v}
 if torch.is_tensor(v):return {'type':'torch.Tensor','dtype':str(v.dtype),'shape':list(v.shape),'device':str(v.device),'value':v.item() if v.ndim==0 and v.dtype==torch.bool else None}
 return {'type':type(v).__module__+'.'+type(v).__name__,'value':None}
try:
 import torch
 torch.set_num_threads(2);assert not torch.cuda.is_initialized()
 from scripts import qd_ed_n30_native as native
 original_sha=hashlib.sha256((I/'scripts/qd_ed_n30_native.py').read_bytes()).hexdigest();assert original_sha==manifest['original_native_sha256']
 index=[json.loads(s) for s in read(manifest['metadata']['index'],16*1024**2).splitlines() if s]
 status=json.loads(read(manifest['metadata']['status'],16*1024**2));assert status['complete'] is True and status['failed'] is False and status['pending_action'] is False
 assert len(index)==status['bundles']==manifest['bundle_count']<=2500 and manifest['bundle_bytes']<=512*1024**2
 for r in manifest['provider_sources']:read(r,1024**2) # exact frozen source bytes; never call a provider
 bundle_bytes=0
 for number,(entry,r) in enumerate(zip(index,manifest['bundles']),1):
  p=Path(r['path']);assert p.parent==Path(manifest['episode_root']) and p.name==entry['bundle']==f'bundle_{number:06d}.pt' and r['sha256']==entry['sha256']
  data=read(r,512*1024**2);bundle_bytes+=len(data);assert bundle_bytes<=512*1024**2
  payload=torch.load(io.BytesIO(data),map_location='cpu',weights_only=True);assert payload['schema']=='qd-ed-decision-evidence-v1'
  rows=payload['events'];assert rows and entry['first_sequence']==rows[0]['sequence'] and entry['last_sequence']==rows[-1]['sequence']
  assert entry['events']==[{k:e[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')} for e in rows]
  events.extend(rows)
 assert bundle_bytes==manifest['bundle_bytes'] and [e['sequence'] for e in events]==list(range(1,len(events)+1)) and all(e['episode']==status['episode'] for e in events)
 metrics=[json.loads(s) for s in read(manifest['metadata']['metrics'],16*1024**2).splitlines() if s]
 compute=[json.loads(s) for s in read(manifest['metadata']['compute'],16*1024**2).splitlines() if s];assert len(compute)==1
 receipt=json.loads(read(manifest['metadata']['receipt'],16*1024**2));assert receipt['accepted'] is False
 triple={kind:next(e for e in events if e['event']==kind) for kind in ('pre_reset_outcome','n30_actual_ack','step_returned')}
 evidence={kind:{'sequence':e['sequence'],'global_step':e['global_step'],'flags':{k:description(e['values'][k]) for k in ('terminated','truncated') if k in e['values']}} for kind,e in triple.items()}
 save(J/'first-triple-v1.json',evidence);print('FIRST_TRIPLE',json.dumps(evidence),flush=True)
 old_calls+=1
 try:result['old_counts']=native.audit_events('N30',metrics,events,compute[0]);result['old_error']=None
 except Exception as exc:result['old_error']={'type':type(exc).__name__,'message':str(exc)}
 result['old_source_sha256']=original_sha
 print('OLD_REPLAY',json.dumps(result.get('old_error')),flush=True)
 assert result['old_error']=={'type':'ValueError','message':'N30 native: terminal feedback binding'},'different old cause; no conditional repair replay'
 print('WAITING_FOR_REPAIRED_SOURCE_ON_STDIN',flush=True)
 assert sys.stdin.readline().strip()=='repaired'
 native=importlib.reload(native);repaired_sha=hashlib.sha256((I/'scripts/qd_ed_n30_native.py').read_bytes()).hexdigest();assert repaired_sha!=original_sha
 new_calls+=1
 try:
  native.compute_check(compute[0],len(metrics));result['repaired_counts']=native.audit_events('N30',metrics,events,compute[0]);result['repaired_error']=None
 except Exception as exc:result['repaired_error']={'type':type(exc).__name__,'message':str(exc)}
 result['repaired_source_sha256']=repaired_sha;result['native_dtypes']=sorted({str(e['values']['native_plan'].dtype) for e in events if e['event']=='n30_selected_native_plan'})
 result['interpretation']='N30-specific offline diagnostic only; no generic arithmetic replay, no replacement same-worker receipt or accepted task outcome.'
except BaseException as exc:
 result['diagnostic_failure']={'type':type(exc).__name__,'message':str(exc)}
 raise
finally:
 result.update(bundle_reads=sum(reads.get(x['path'],0) for x in manifest['bundles']),bundle_bytes=sum(x['bytes']*reads.get(x['path'],0) for x in manifest['bundles']),old_replays=old_calls,repaired_replays=new_calls)
 save(J/'real-replay-v1.json',result)
 state={'schema':'n30-terminal-feedback-replay-resource-v1','cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,
  'affinity':sorted(os.sched_getaffinity(0)),'threads':2,'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],
  'cuda_initialized':sys.modules['torch'].cuda.is_initialized() if 'torch' in sys.modules else None,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
  'rlimit_as_bytes':16*1024**3,'read_counts':reads,'read_bytes':total,'denied':denied,'guard_clean':not denied}
 save(J/'real-replay-resource-v1.json',state)
 print('REPLAY_CLOSURE',json.dumps({k:v for k,v in result.items() if k not in {'input_manifest'}}),flush=True)
