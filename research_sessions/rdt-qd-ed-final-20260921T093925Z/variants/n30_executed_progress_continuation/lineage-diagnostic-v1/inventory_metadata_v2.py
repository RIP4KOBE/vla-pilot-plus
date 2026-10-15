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
def meta():
 review=read(L/'root-terminal-review-v1.json','0a840aebc3e63fd3f9940b0bd51b042fb471385e6522a74493c916b7b8c39f91')
 static=read(L/'conditional-next-hypothesis-v1/root-static-review-v1.json','79e99569fd17f4e4d1a6ffabb0247271cb9d1607f7374d69173074bfb3b7614f')
 read(static['report']['path'],static['report']['sha256'],text=True)
 read(L/'conditional-next-hypothesis-v1/read-source-windows-v1.json')
 source=ref(review['source']);plan=ref(review['plan']);result=ref(review['result'])
 assert review['decision']=='REJECT_NUMERIC_DEV_FUTILITY' and review['source_commit']==SOURCE
 assert source['commit']==SOURCE and result['source_commit']==SOURCE
 write('control-shapes-v2.json',{'plan':shape(plan,2),'result':shape(result,2)})
 cells=[x for x in review['accepted_cells'] if x['profile']=='N30']
 assert [x['task_id'] for x in cells]==[0,1]
 assert [x['attempt_id'].rsplit('__',1)[-1] for x in cells]==['4300bcf89485','1e52b07e1725']
 assert all(x in result['accepted_cells'] for x in cells)
 episodes=[]
 for cell in cells:
  terminal=ref(cell['attempt_result']);context=ref(cell['worker_context']);receipt=ref(cell['worker_receipt']);audit=ref(cell['audit'])
  output=pathlib.Path(cell['attempt_result']['path']).parent; er=output/'eds_eval/decision_evidence/episode_000'
  proc_ref=next(x['process'] for x in review['new_attempts'] if x['attempt_id']==cell['attempt_id']);process=ref(proc_ref)
  status=read(er/'status.json',cap=32*1024**2)
  metrics=read(output/'eds_eval/eds_metrics.jsonl',cap=32*1024**2,jsonl=True)
  compute=read(output/'eds_eval/episode_compute.jsonl',cap=32*1024**2,jsonl=True)
  # Explicit metadata only: retain key names/types, identity/context scalars and activity flags.
  assert terminal['attempt_id']==cell['attempt_id'] and terminal['outcome_valid'] is True
  assert context['attempt_id']==cell['attempt_id']
  assert context.get('source_commit',context.get('source',{}).get('commit'))==SOURCE
  assert audit['accepted'] is True and audit['evidence_complete'] is True and status['complete'] is True
  metric_rows=[]
  for m in metrics:
   state=m.get('executed_progress_continuation')
   metric_rows.append({'context':m.get('context'),'top_identity':{k:m[k] for k in ('global_step','step','decision_id','episode','task_id') if k in m},
     'progress':{k:state.get(k) for k in ('mode','active','status','reason','previous_start_step','invalid_evidence_count','control') if k in state} if isinstance(state,dict) else None})
  # Only references already present in receipt; never follow them. Index/status bindings are later checked.
  refs=[]
  def collect(x):
   if isinstance(x,dict):
    if isinstance(x.get('path'),str) and isinstance(x.get('sha256'),str):refs.append({'path':x['path'],'sha256':x['sha256']})
    for v in x.values():collect(v)
   elif isinstance(x,list):
    for v in x:collect(v)
  collect(receipt)
  episodes.append({'cell':cell,'episode_root':str(er),'status':status,'metric_rows':metric_rows,
   'index_receipt_refs':[x for x in refs if x['path'].endswith(('events.jsonl','status.json'))],
   'receipt_payload_refs':[x for x in refs if x['path'].endswith('.pt')],
   'identity_checks':{'terminal_source':terminal.get('source_commit'),'context_source':context.get('source_commit',context.get('source',{}).get('commit')),'receipt_source':receipt.get('source_commit',receipt.get('source',{}).get('commit'))},
   'metadata_shapes':{'terminal':shape(terminal,1),'context':shape(context,2),'receipt':shape(receipt,2),'audit':shape(audit,1),'compute':shape(compute,1)},
   'process_identity':{k:process.get(k) for k in ('attempt_id','pid','start_ticks','boot_id')},
   'audit_counts':audit.get('n30_executed_progress_continuation')})
 write('episode-metadata-catalog-v1.json',{'episodes':episodes,'plan_shape':shape(plan,1),'result_shape':shape(result,1),'source_ref':review['source'],'plan_ref':review['plan'],'result_ref':review['result']})
 for ep in episodes:print(json.dumps({'task':ep['cell']['task_id'],'metric_rows':ep['metric_rows'],'metadata_shapes':ep['metadata_shapes'],'index_receipt_refs':ep['index_receipt_refs']},ensure_ascii=False))

if __name__=='__main__':
 name=sys.argv[1];error=None
 try:
  if name=='metadata':meta()
  else:raise ValueError(name)
 except BaseException as e:
  error={'type':type(e).__name__,'message':str(e)};raise
 finally:
  write('resource-'+name+'-v2.json',{'reader_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'reads':READS,'metadata_bytes_including_preparation':consumed,'cpu_seconds':time.process_time()-T0,'wall_seconds':time.monotonic()-WALL,'affinity':sorted(os.sched_getaffinity(0)),'denied':DENIED,'error':error,'tensor_opens':0,'production_imports':False})
