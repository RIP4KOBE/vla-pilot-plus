"""Two predeclared arithmetic descriptions; static source reads, never runtime imports."""
from pathlib import Path
import collections,csv,hashlib,json,math,os,signal,statistics,sys,time
H=Path(__file__).resolve().parent;M=H/'read-scope-v1.json';EXPECTED='82848e3bf21292449f05d3648887084ecb249eab3c94503184069de89cc954d3'
def check(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(Path(p).read_bytes())}
def norm(v):return math.sqrt(sum(x*x for x in v))
def minus(a,b):return [x-y for x,y in zip(a,b)]
def add(vs):return [sum(v[i] for v in vs) for i in range(3)]
def quantile(xs,p):
 xs=sorted(xs)
 if not xs:return None
 pos=(len(xs)-1)*p;lo=int(math.floor(pos));hi=int(math.ceil(pos));return xs[lo]*(hi-pos)+xs[hi]*(pos-lo) if lo!=hi else xs[lo]
def summary(rows,formula):
 known=[r for r in rows if r['observed_displacement_m'] is not None];rs=[r[formula]['residual_xyz_m'] for r in known];ns=[r[formula]['residual_norm_m'] for r in known]
 return {'total':len(rows),'known':len(known),'unknown':len(rows)-len(known),
 'signed_mean_xyz_residual_m':[sum(r[i] for r in rs)/len(rs) for i in range(3)] if rs else None,
 'euclidean_residual_mean_m':sum(ns)/len(ns) if ns else None,'euclidean_residual_median_m':statistics.median(ns) if ns else None,'euclidean_residual_p90_m':quantile(ns,.9)}
def partitions(rows):
 result=[]
 for task in [None,0,1,2,3]:
  base=[r for r in rows if task is None or r['task']==task]
  slices=[('all','all',base)]
  for g in [True,False]:slices.append(('guidance','guided' if g else 'unguided',[r for r in base if r['guided']==g]))
  grips=sorted({r['gripper_group'] for r in base})
  for gr in grips:slices.append(('commanded_gripper',gr,[r for r in base if r['gripper_group']==gr]))
  for g in [True,False]:
   for gr in grips:slices.append(('guidance_x_commanded_gripper',('guided' if g else 'unguided')+'/'+gr,[r for r in base if r['guided']==g and r['gripper_group']==gr]))
  for dimension,label,selected in slices:result.append({'task':'all' if task is None else task,'dimension':dimension,'group':label,'A':summary(selected,'A'),'B':summary(selected,'B')})
 return result

def main():
 started=time.monotonic()
 def timeout(sig,frame):raise TimeoutError('120 second extraction bound; no automatic rerun')
 signal.signal(signal.SIGALRM,timeout);signal.alarm(120)
 check(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CUDA must be invisible');mb=M.read_bytes();check(sha(mb)==EXPECTED,'scope drift');scope=json.loads(mb)
 allowed={str(Path(r['path']).resolve()) for r in [scope['closed_proprioception_result'],*scope['source_files'].values(),*[a['metrics'] for a in scope['attempts']]]}
 roots=[str(H.parents[2].resolve()),'/mnt/data/shared2/hynx/VLA-Pilot++'];blocked_reads=[];blocked_dispatch=[]
 def guard(event,args):
  if event in {'subprocess.Popen','os.system','os.fork','os.posix_spawn','os.spawn','os.exec','socket.connect','socket.bind','socket.getaddrinfo'}:
   blocked_dispatch.append(event);raise RuntimeError('forbidden dispatch')
  if event=='import' and isinstance(args[0],str) and args[0].split('.')[0] in {'torch','mujoco','robosuite','libero','libero_pro','requests','httpx'}:
   blocked_dispatch.append('import:'+args[0]);raise RuntimeError('runtime import forbidden')
  if event!='open':return
  name,mode,flags=args
  if isinstance(name,int):return
  p=str(Path(os.fsdecode(name)).resolve());write=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  if any(p.startswith(r+'/') for r in roots):
   if write and not p.startswith(str(H)+'/'):raise RuntimeError('write outside diagnostic')
   if not write and p not in allowed and not p.startswith(str(H)+'/'):blocked_reads.append(p);raise RuntimeError('read outside exact scope')
 sys.addaudithook(guard)
 sources={}
 for k,r in scope['source_files'].items():
  b=Path(r['path']).read_bytes();check(sha(b)==r['sha256'],'source changed');sources[k]=b.decode()
 rr=scope['closed_proprioception_result'];rb=Path(rr['path']).read_bytes();check(sha(rb)==rr['sha256'],'closed proprioception changed');d=json.loads(rb)
 check(d['source_commit']==scope['source_commit'] and d['coverage']['transitions']==2880,'closed result identity')
 metadata=[];bytask={}
 for a in scope['attempts']:
  r=a['metrics'];b=Path(r['path']).read_bytes();check(sha(b)==r['sha256'],'metrics changed');safe=[]
  for line in b.decode().splitlines():
   row=json.loads(line);safe.append({k:row.get(k) for k in scope['allowed_metric_fields']});del row
  prefixes=[p for p in d['prefixes'] if p['task']==a['task']];guided={p['step']:p for p in prefixes if p['guided']};check(len(safe)==len(guided) and len(safe)>0,'guided metadata coverage')
  semantics=None;context=None;steps=set();actual=[]
  for row in safe:
   step=row['global_step'];m=row['qd_actuator_metadata'];check(type(step) is int and step in guided and step not in steps,'step identity');steps.add(step)
   check(isinstance(m,dict) and m.get('schema')=='n23-static-actuator-snapshot-v1','live controller metadata missing')
   sem=m['semantics'];ctx=m['context'];check(sem['controller_type']=='robosuite.controllers.osc.OperationalSpaceController' and sem['name']=='OSC_POSE' and sem['use_delta'] is True and sem['use_ori'] is True and sem['control_dim']==6 and sem['impedance_mode']=='fixed','actual controller mode contradiction')
   for key in ['input_min','input_max','output_min','output_max']:
    check(isinstance(sem[key],list) and len(sem[key])==6 and all(type(x) in [int,float] and math.isfinite(x) for x in sem[key]),'actual bounds malformed')
   check(all(sem['input_min'][i]<sem['input_max'][i] and sem['output_min'][i]<sem['output_max'][i] for i in range(6)),'actual bound order')
   check(sem['input_min'][:3]==[-1.]*3 and sem['input_max'][:3]==[1.]*3,'N23 input bound contradiction')
   check(ctx['task_index']==a['task'] and all(type(x) is int and x>=0 for x in ctx.values()),'actual controller lifecycle identity:'+repr(ctx))
   if semantics is None:semantics=sem;context=ctx
   else:check(semantics==sem and context==ctx,'metadata bounds or controller/reset identity drift')
   for method,sourcekey,qualname in [('set_goal','installed_robosuite/osc.py','OperationalSpaceController.set_goal'),('scale_action','installed_robosuite/base_controller.py','Controller.scale_action')]:
    refsrc=m['source'][method];frozen=scope['source_files'][sourcekey]
    check(Path(refsrc['path']).resolve()==Path(frozen['path']).resolve() and refsrc['sha256']==frozen['sha256'] and refsrc['qualname']==qualname,'actual controller method-source mismatch')
   actual.append({'step':step,'episode':row['episode'],'metadata':m})
  check(steps==set(guided),'metadata guided steps differ')
  bytask[a['task']]=semantics
  metadata.append({'task':a['task'],'attempt_id':a['attempt_id'],'metrics':r,'recorded_snapshot_count':len(actual),'snapshot_steps':sorted(steps),'same_controller_context':context,'semantics':semantics,
    'snapshots':actual,'unguided_boundaries_without_snapshot':len(prefixes)-len(actual),
    'B_coverage_interpretation':'same per-attempt recorded static bounds; not a live snapshot at every action; final goal, position_limits and cached action_scale unobserved'})
 check(sum(m['recorded_snapshot_count'] for m in metadata)==139,'snapshot count')
 # Validate the source trace text without importing or invoking controller/environment classes.
 check('ACTION_SCALE_POS = 0.01' in sources['core/env_adapters/libero_adapter.py'] and 'clamp(-1., 1.) * .01' in sources['core/qd_actuator_clipped_quality.py'],'A source trace')
 check('np.clip(action, self.input_min, self.input_max)' in sources['installed_robosuite/base_controller.py'] and '(action - self.action_input_transform) * self.action_scale + self.action_output_transform' in sources['installed_robosuite/base_controller.py'],'affine source trace')
 check('scaled_delta = self.scale_action(delta)' in sources['installed_robosuite/osc.py'] and 'scaled_delta[:3], self.ee_pos, position_limit=self.position_limits, set_pos=set_pos' in sources['installed_robosuite/osc.py'],'B pre-position-limit source trace')
 steps=[];bykey={};byattempt=collections.defaultdict(list)
 for r in d['transitions']:byattempt[r['task']].append(r)
 for task,rows in sorted(byattempt.items()):
  check(len(rows)==720 and [r['step'] for r in rows]==list(range(720)),'derived transitions order');sem=bytask[task]
  for i,r in enumerate(rows):
   xyz=r['actual_action'][:3];A=[.01*max(-1.,min(1.,x)) for x in xyz];B=[]
   for j,x in enumerate(xyz):
    imin,imax,omin,omax=[sem[k][j] for k in ['input_min','input_max','output_min','output_max']]
    clipped=max(imin,min(imax,x));B.append((clipped-(imax+imin)/2)*abs(omax-omin)/abs(imax-imin)+(omax+omin)/2)
   prev=rows[i-1] if i>0 and rows[i-1]['reset_sequence']==r['reset_sequence'] else None
   obs=minus(r['observation']['robot0_eef_pos']['values'],prev['observation']['robot0_eef_pos']['values']) if prev is not None else None
   out={'task':task,'step':i,'guided':r['guided'],'gripper_group':'positive' if r['gripper_command']>0 else 'nonpositive','gripper_command':r['gripper_command'],'reset_sequence':r['reset_sequence'],
     'observed_displacement_m':obs,'origin_status':'known_previous_contiguous_poststep' if obs is not None else 'Unknown_missing_initial_origin',
     'actual_xyz_action':xyz,'A':{'increment_xyz_m':A,'residual_xyz_m':minus(A,obs) if obs is not None else None},'B':{'increment_xyz_m':B,'residual_xyz_m':minus(B,obs) if obs is not None else None}}
   for k in ['A','B']:out[k]['residual_norm_m']=norm(out[k]['residual_xyz_m']) if obs is not None else None
   steps.append(out);bykey[(task,i)]=out
 blocks=[]
 for p in d['prefixes']:
  rows=[bykey[(p['task'],i)] for i in range(p['start_step'],p['end_step']+1)];obs=p['robot0_eef_pos']['net_change'];A=add([r['A']['increment_xyz_m'] for r in rows]);B=add([r['B']['increment_xyz_m'] for r in rows])
  out={'task':p['task'],'step':p['step'],'guided':p['guided'],'gripper_group':p['prefix_type'],'actual_command_bits':p['actual_command_bits'],'observed_displacement_m':obs,'origin_status':p['start_status'],
   'A':{'increment_xyz_m':A,'residual_xyz_m':minus(A,obs) if obs is not None else None},'B':{'increment_xyz_m':B,'residual_xyz_m':minus(B,obs) if obs is not None else None}}
  for k in ['A','B']:out[k]['residual_norm_m']=norm(out[k]['residual_xyz_m']) if obs is not None else None
  blocks.append(out)
 check(len(steps)==2880 and sum(x['observed_displacement_m'] is not None for x in steps)==2876 and len(blocks)==360 and sum(x['observed_displacement_m'] is not None for x in blocks)==356,'known/unknown fixed denominator')
 check(not blocked_reads and not blocked_dispatch and 'torch' not in sys.modules,'guard')
 elapsed=time.monotonic()-started;check(elapsed<=120,'wall');signal.alarm(0)
 result={'schema':'n23-actuator-goal-scale-descriptive-v1','scope':ref(M),'script':ref(__file__),'source_commit':scope['source_commit'],'status':'completed_static_bounds_descriptive_comparison','metadata':metadata,
  'arithmetic':'Python float64 evaluation on exact saved action values; A is mathematical internal-increment view, not a bitwise reproduction of GPU BF16 quality/projection. B is affine scaled_delta before unrecorded position limits/cache/final goal.',
  'B_unobserved_runtime_fields':['position_limits','cached action_scale/input/output transforms','final goal_pos','substep dynamics'],
  'comparison_count':2,'residual_sign':'formula minus observed EEF displacement','quantile_rule':'linear interpolation at (n-1)*p, p=0.9','steps':steps,'blocks':blocks,
  'step_summaries':partitions(steps),'block_summaries':partitions(blocks),'coverage':{'steps_total':2880,'steps_known':2876,'steps_unknown':4,'blocks_total':360,'blocks_known':356,'blocks_unknown':4},
  'elapsed_seconds':elapsed,'cpu_execution_threads':1,'cpu_thread_limit':2,'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'runtime_imports':[],'blocked_reads':blocked_reads,'blocked_dispatch':blocked_dispatch,
  'limits':['Actual recorded bounds verify metadata values, not a per-step final-goal log. Unguided rows use common per-attempt recorded-static contract, no live snapshot at that boundary.',
   'B is position-limit-before affine scaled_delta; live position limits/cache/final goal Unknown. Defaults are not used to impute them.',
   'Sum of intended increments is not a realized OSC trajectory prediction. Impedance/orientation/contact/state dynamics can change actual displacement.',
   'No reward/success/contact/object state selection, fitted scale/threshold, extra formula, ranking, new quality evaluation, candidate or physical counterfactual. Error statistics do not establish task benefit.']}
 f=H/'result-v1.json';check(not f.exists(),'immutable result');f.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 for filename,rows in [('one-step-summaries-v1.csv',result['step_summaries']),('eight-step-summaries-v1.csv',result['block_summaries'])]:
  compact=[]
  for row in rows:
   for formula in ['A','B']:
    s=row[formula];compact.append({**{k:row[k] for k in ['task','dimension','group']},'formula':formula,**{k:v for k,v in s.items() if k!='signed_mean_xyz_residual_m'},'signed_mean_xyz_residual_m':json.dumps(s['signed_mean_xyz_residual_m'])})
  with (H/filename).open('w',newline='') as fp:
   writer=csv.DictWriter(fp,fieldnames=list(compact[0]));writer.writeheader();writer.writerows(compact)
 print(json.dumps({'result':ref(f),'metadata_counts':[m['recorded_snapshot_count'] for m in metadata],'actual_xyz_output_bounds':[{'task':m['task'],'min':m['semantics']['output_min'][:3],'max':m['semantics']['output_max'][:3]} for m in metadata],
   'coverage':result['coverage'],'one_step_all':result['step_summaries'][0],'eight_step_all':result['block_summaries'][0],'elapsed_seconds':elapsed,'blocked_reads':blocked_reads,'blocked_dispatch':blocked_dispatch},indent=2))
if __name__=='__main__':main()
