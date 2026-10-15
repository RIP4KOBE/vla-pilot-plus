"""Bounded recorded-proprioception extraction; no reward/contact/outcome feature reads."""
from pathlib import Path
import collections,csv,hashlib,io,json,math,os,signal,sys,time
import torch
H=Path(__file__).resolve().parent;MANIFEST=H/'read-scope-v1.json';EXPECTED='562c021300c743db343975ea63c20cb7be451839ac22464902e48943d9e31eab'
FIELDS={'robot0_eef_pos':3,'robot0_eef_quat':4,'robot0_gripper_qpos':2,'robot0_gripper_qvel':2}
torch.set_num_threads(2)
def check(ok,msg):
 if not ok:raise ValueError(msg)
def digest(b):return hashlib.sha256(b).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':digest(Path(p).read_bytes())}
def unknown(reason):return {'status':'Unknown','reason':reason}
def field(v,expected):
 if not isinstance(v,torch.Tensor):return {'status':'missing','values':None}
 shape=list(v.shape);flat=v.detach().reshape(-1)
 if len(flat)!=expected:return {'status':'wrong_shape','shape':shape,'dtype':str(v.dtype),'values':None}
 good=torch.isfinite(flat);values=[float(x) if bool(good[i]) else None for i,x in enumerate(flat)]
 return {'status':'finite' if bool(good.all()) else 'nonfinite','shape':shape,'dtype':str(v.dtype),'values':values,'nonfinite_count':int((~good).sum())}
def values(row,name):
 if row is None:return None
 v=row['observation'][name];return v['values'] if v['status']=='finite' else None
def vector_delta(a,b):return [y-x for x,y in zip(a,b)] if a is not None and b is not None else None
def norm(v):return math.sqrt(sum(x*x for x in v)) if v is not None else None
def ranges(vs,n):
 vs=[v for v in vs if v is not None]
 return {'count':len(vs),'min':[min(v[i] for v in vs) for i in range(n)] if vs else None,'max':[max(v[i] for v in vs) for i in range(n)] if vs else None}
def stats(xs):
 xs=[float(x) for x in xs if x is not None]
 return {'count':len(xs),'min':min(xs) if xs else None,'mean':sum(xs)/len(xs) if xs else None,'max':max(xs) if xs else None}
def interval_summary(rows,start,end):
 prior=rows[start-1] if start>0 and rows[start-1]['reset_sequence']==rows[start]['reset_sequence'] else None
 finish=rows[end];out={'start_step':start,'end_step':end,'actions':end-start+1,'start_observation_source_step':start-1 if prior else None,
 'start_status':'recorded_preceding_poststep' if prior else 'Unknown: no initial/pre-reset-compatible observation','end_status':'recorded_pre_reset_poststep',
 'end_observation_source_step':end,'reset_sequence':rows[start]['reset_sequence']}
 observations=([prior] if prior else [])+rows[start:end+1]
 for name,size in FIELDS.items():
  a=values(prior,name);b=values(finish,name);out[name]={'start':a,'end':b,'net_change':vector_delta(a,b),'observed_range':ranges([values(r,name) for r in observations],size)}
 out['eef_net_displacement_m']=norm(out['robot0_eef_pos']['net_change'])
 lengths=[]
 for left,right in zip(observations,observations[1:]):
  if left['reset_sequence']==right['reset_sequence']:
   v=vector_delta(values(left,'robot0_eef_pos'),values(right,'robot0_eef_pos'))
   if v is not None:lengths.append(norm(v))
 out['eef_observed_path_length_m']=sum(lengths);out['eef_path_segments_observed']=len(lengths)
 out['eef_path_is_complete_for_actions']=len(lengths)==end-start+1
 return out

def main():
 started=time.monotonic()
 def timeout(sig,frame):raise TimeoutError('180 second native-screen bound exceeded; no implicit retry')
 signal.signal(signal.SIGALRM,timeout);signal.alarm(180)
 check(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CUDA must be invisible');check(not torch.cuda.is_initialized(),'CUDA initialized')
 mb=MANIFEST.read_bytes();check(digest(mb)==EXPECTED,'read manifest changed');scope=json.loads(mb)
 for s in scope['source_files'].values():check(digest(Path(s['path']).read_bytes())==s['sha256'],'source changed')
 allowed={str(Path(b['path']).resolve()) for a in scope['attempts'] for b in a['bundles']};roots=[str(H.parents[2].resolve()),'/mnt/data/shared2/hynx/VLA-Pilot++'];blocked_reads=[];blocked_dispatch=[]
 def guard(event,args):
  if event in {'subprocess.Popen','os.system','os.fork','os.posix_spawn','os.spawn','os.exec','socket.connect','socket.bind','socket.getaddrinfo'}:
   blocked_dispatch.append(event);raise RuntimeError('forbidden dispatch '+event)
  if event!='open':return
  name,mode,flags=args
  if isinstance(name,int):return
  p=str(Path(os.fsdecode(name)).resolve());write=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  if any(p.startswith(r+'/') for r in roots):
   if write and not p.startswith(str(H)+'/'):raise RuntimeError('write outside diagnostic')
   if not write and p not in allowed and not p.startswith(str(H)+'/'):blocked_reads.append(p);raise RuntimeError('read outside frozen scope')
 sys.addaudithook(guard)
 def no_cuda(*a,**kw):blocked_dispatch.append('torch.cuda initialization');raise RuntimeError('CUDA forbidden')
 torch.cuda._lazy_init=no_cuda
 attempts=[];transitions=[];allruns=[];allprefixes=[];loaded=set();progress=[]
 for a in scope['attempts']:
  bydid={b['decision_id']:b for b in a['boundaries_from_prior_derived']};records={};decodes={};commits={}
  for b in a['bundles']:
   path=b['path'];check(path not in loaded,'bundle read twice');loaded.add(path)
   bb=Path(path).read_bytes();check(digest(bb)==b['sha256'],'bundle hash')
   payload=torch.load(io.BytesIO(bb),map_location='cpu',weights_only=True);check(payload['schema']=='qd-ed-decision-evidence-v1','bundle schema')
   check([{k:e[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')} for e in payload['events']]==b['events'],'hash-linked index association')
   for event in payload['events']:
    kind=event['event']
    if kind not in {'action_dispatch','executed_action','pre_reset_outcome','step_returned','policy_action_decode','decision_committed'}:continue
    did=event['decision_id'];check(did in bydid,'unknown decision');v=event['values'];seq=event['sequence'];step=event['global_step'];reset=event['reset_sequence']
    if kind in {'policy_action_decode','decision_committed'}:
     dest=decodes if kind=='policy_action_decode' else commits;check(did not in dest,'duplicate decode/commit')
     chunk=v['action_chunk'];check(isinstance(chunk,torch.Tensor) and tuple(chunk.shape)==(1,8,7) and bool(torch.isfinite(chunk).all()),'action chunk shape')
     record={'chunk':chunk.detach().clone(),'sequence':seq,'step':step,'reset':reset,'bundle':path}
     if kind=='policy_action_decode':check(v['selected_canonical_fingerprint']==bydid[did]['selected_fingerprint'],'prior exact decoder identity')
     else:check(v['execution_horizon']==8,'execution horizon')
     dest[did]=record;continue
    r=records.setdefault(step,{'task':a['task'],'attempt_id':a['attempt_id'],'step':step,'decision_id':did,'event_refs':{},'reset_sequence':reset})
    check(r['decision_id']==did and kind not in r['event_refs'],'transition identity/duplicate');r['event_refs'][kind]={'sequence':seq,'bundle':path,'reset_sequence':reset}
    if kind=='action_dispatch':r['execution_index']=v['execution_index']
    elif kind=='executed_action':
     action=v['action_numpy'];check(isinstance(action,torch.Tensor) and tuple(action.shape)==(7,) and bool(torch.isfinite(action).all()),'executed action');r['action']=action.detach().clone()
    elif kind=='pre_reset_outcome':
     # The other co-resident fields (reward/success/terminated) are deliberately never accessed.
     obs=v['observation'];r['observation']={name:field(obs.get(name),n) for name,n in FIELDS.items()}
    # step_returned values are deliberately ignored: identity/sequence only.
  check(set(records)==set(range(720)),'finite 720 transition coverage');rows=[]
  for step in range(720):
   r=records[step];did=r['decision_id'];context=bydid[did];de=decodes[did];co=commits[did];ev=r['event_refs']
   check(set(ev)=={'action_dispatch','executed_action','pre_reset_outcome','step_returned'},'transition association incomplete')
   check(de['sequence']<co['sequence']<ev['action_dispatch']['sequence']<ev['executed_action']['sequence']<ev['pre_reset_outcome']['sequence']<ev['step_returned']['sequence'],'causal event order')
   check(de['step']==co['step']==context['step'] and de['reset']==co['reset']==context['reset_sequence']==r['reset_sequence']
     and all(ev[k]['reset_sequence']==context['reset_sequence'] for k in ['action_dispatch','executed_action','pre_reset_outcome']),'pre-reset identity')
   index=step-context['step'];check(index==r['execution_index']-1 and 0<=index<8,'execution prefix index')
   check(torch.equal(de['chunk'],co['chunk']) and torch.equal(r['action'],co['chunk'][0,index]),'actual executed action vs committed prefix')
   command=float(r['action'][6]);check(command in [-1.,1.],'binary gripper')
   check((command>0)==(context['selected_prefix0_7_bits'][index]=='1'),'prior derived command identity')
   r.update({'actual_action':r.pop('action').tolist(),'gripper_command':int(command),'stage':context['stage'],'guided':context['guided'],'target_identity':context['target_identity'],'returned_reset_sequence':ev['step_returned']['reset_sequence']})
   rows.append(r)
  coverage={name:dict(collections.Counter(r['observation'][name]['status'] for r in rows)) for name in FIELDS}
  prefixes=[]
  for context in sorted(bydid.values(),key=lambda x:x['step']):
   s=context['step'];positive=sum(r['gripper_command']>0 for r in rows[s:s+8]);kind='all_positive' if positive==8 else 'all_nonpositive' if positive==0 else 'mixed'
   pr={'task':a['task'],'decision_id':context['decision_id'],'step':s,'guided':context['guided'],'stage':context['stage'],'target_identity':context['target_identity'],'actual_command_bits':''.join('1' if r['gripper_command']>0 else '0' for r in rows[s:s+8]),'positive_commands':positive,'prefix_type':kind,**interval_summary(rows,s,s+7)}
   prefixes.append(pr);allprefixes.append(pr)
  runs=[];s=0
  for step in range(1,721):
   if step==720 or rows[step]['gripper_command']!=rows[s]['gripper_command'] or rows[step]['reset_sequence']!=rows[s]['reset_sequence']:
    rs=rows[s:step];run={'task':a['task'],'run_index':len(runs),'command':rows[s]['gripper_command'],'decision_ids':list(dict.fromkeys(r['decision_id'] for r in rs)),'stages':list(dict.fromkeys(r['stage'] for r in rs)),'guided_values':list(dict.fromkeys(r['guided'] for r in rs)),**interval_summary(rows,s,step-1)}
    runs.append(run);allruns.append(run);s=step
  whole=interval_summary(rows,0,719)
  # First-to-last observed change is separately named; initial state is never imputed.
  observed_change={name:vector_delta(values(rows[0],name),values(rows[-1],name)) for name in FIELDS}
  attempts.append({'task':a['task'],'attempt_id':a['attempt_id'],'transitions':720,'prefixes':90,'runs':len(runs),'coverage':coverage,
     'positive_actions':sum(r['gripper_command']>0 for r in rows),'negative_actions':sum(r['gripper_command']<0 for r in rows),'whole_episode_observations':whole,'first_observed_step0_to_last_observed_step719_change':observed_change})
  transitions.extend(rows);progress.append({'task':a['task'],'transitions':len(rows),'elapsed_seconds':time.monotonic()-started});print(json.dumps(progress[-1]),flush=True)
 check(len(transitions)==2880 and len(allprefixes)==360 and len(loaded)==9000,'bounded total')
 native_elapsed=time.monotonic()-started;signal.alarm(0);check(native_elapsed<=180,'wall bound')
 byprefix={(p['task'],p['step']):p for p in allprefixes};pair_rows=[]
 for pair in scope['strict_full_positive_pairs']:
  prev=byprefix[(pair['task'],pair['previous_step'])];nxt=byprefix[(pair['task'],pair['next_step'])]
  check(prev['target_identity']==nxt['target_identity'] and prev['target_identity']['status']=='recorded' and prev['guided'] and nxt['guided'] and prev['stage']==nxt['stage'] and prev['reset_sequence']==nxt['reset_sequence'],'strict pair identity')
  check(nxt['actual_command_bits']==pair['next_selected_prefix0_7_bits'],'prior pair binding')
  pair_rows.append({'task':pair['task'],'previous_step':pair['previous_step'],'next_step':pair['next_step'],'previous_predicted_tail_bits':pair['predicted_previous_offsets8_15_bits'],
    'next_prefix_category':'retained_all_positive' if nxt['positive_commands']==8 else 'all_nonpositive' if nxt['positive_commands']==0 else 'mixed',
    'same_recorded_stage_reset_target':True,'target_displacement_m_from_prior_diagnostic':pair['target_displacement_m'],
    'previous_executed_prefix':prev,'next_executed_prefix':nxt,'physical_grasp':'Unknown','unexecuted_tail_counterfactual_effect':'Unknown'})
 summaries={}
 for kind in ['all_positive','mixed','all_nonpositive']:
  ps=[p for p in allprefixes if p['prefix_type']==kind];entry={'prefixes':len(ps),'task_counts':dict(collections.Counter(p['task'] for p in ps)),
   'eef_net_displacement_m':stats(p['eef_net_displacement_m'] for p in ps),'eef_observed_path_length_m':stats(p['eef_observed_path_length_m'] for p in ps)}
  for name,n in FIELDS.items():
   ns=[p[name]['net_change'] for p in ps];entry[name]={'net_change_known_prefixes':sum(x is not None for x in ns),'net_change_each_coordinate':[stats(x[i] if x is not None else None for x in ns) for i in range(n)],
      'pooled_observed_min':[min(p[name]['observed_range']['min'][i] for p in ps if p[name]['observed_range']['count']) for i in range(n)] if ps else None,
      'pooled_observed_max':[max(p[name]['observed_range']['max'][i] for p in ps if p[name]['observed_range']['count']) for i in range(n)] if ps else None}
  summaries[kind]=entry
 check(len(pair_rows)==15 and not blocked_reads and not blocked_dispatch and not torch.cuda.is_initialized(),'completed guard')
 result={'schema':'n23-executed-proprioceptive-continuity-v1','scope':ref(MANIFEST),'extractor':ref(__file__),'source_commit':scope['source_commit'],'native_screen_elapsed_seconds':native_elapsed,'cpu_threads':2,'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'cuda_initialized':False,'blocked_reads':blocked_reads,'blocked_dispatch':blocked_dispatch,'native_bundle_read_count':len(loaded),
  'coverage':{'attempts':4,'transitions':2880,'prefixes':360,'command_sign_runs':len(allruns),'strict_pairs':15},'attempts':attempts,'prefix_type_summaries':summaries,'strict_pairs':pair_rows,'transitions':transitions,'prefixes':allprefixes,'command_runs':allruns,
  'limits':['Only policy-visible recorded EEF xyz/quaternion and two gripper qpos/qvel joints are measured; reward, success, termination outcomes/contact/object poses are not accessed as data features.',
   'Episode initial observation is missing. First prefix/run start and net changes are Unknown; first recorded poststep-to-last is separately labelled.',
   'State is actual pre-reset post-action observation. A next boundary start uses immediately preceding observation only with matching reset identity.',
   'Command runs are maximal same-sign actual command sequences within each episode/reset; they may span Stage/guidance changes, which are retained.',
   'Joint stalls, gaps, commanded closure and tracked target co-motion do not establish contact or grasp. Physical grasp and old-tail alternative outcomes remain Unknown.',
   'No fitted threshold, coefficients, candidate, scorer, trajectory projection, counterfactual replay or new environment transitions. Correlated descriptive data only.']}
 f=H/'result-v1.json';check(not f.exists(),'immutable output');f.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 def write_table(path,rows,columns):
  with path.open('w',newline='') as fp:
   w=csv.DictWriter(fp,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
 write_table(H/'command-runs-v1.csv',allruns,['task','run_index','command','start_step','end_step','actions','start_status','eef_net_displacement_m','eef_observed_path_length_m'])
 write_table(H/'prefixes-v1.csv',allprefixes,['task','step','prefix_type','actual_command_bits','positive_commands','stage','guided','start_status','eef_net_displacement_m','eef_observed_path_length_m'])
 compact=[]
 for p in pair_rows:
  a,b=p['previous_executed_prefix'],p['next_executed_prefix'];compact.append({'task':p['task'],'previous_step':p['previous_step'],'next_step':p['next_step'],'category':p['next_prefix_category'],'previous_executed_bits':a['actual_command_bits'],'predicted_tail_bits':p['previous_predicted_tail_bits'],'next_executed_bits':b['actual_command_bits'],'target_displacement_m':p['target_displacement_m_from_prior_diagnostic'],'previous_qpos_start':a['robot0_gripper_qpos']['start'],'previous_qpos_end':a['robot0_gripper_qpos']['end'],'next_qpos_start':b['robot0_gripper_qpos']['start'],'next_qpos_end':b['robot0_gripper_qpos']['end'],'previous_eef_start':a['robot0_eef_pos']['start'],'previous_eef_end':a['robot0_eef_pos']['end'],'next_eef_start':b['robot0_eef_pos']['start'],'next_eef_end':b['robot0_eef_pos']['end']})
 write_table(H/'strict-pairs-v1.csv',compact,list(compact[0]))
 print(json.dumps({'result':ref(f),'coverage':result['coverage'],'native_screen_elapsed_seconds':native_elapsed,'field_coverage':[{'task':a['task'],'coverage':a['coverage']} for a in attempts],'cuda_initialized':False,'blocked_reads':blocked_reads,'blocked_dispatch':blocked_dispatch},indent=2),flush=True)
if __name__=='__main__':main()
