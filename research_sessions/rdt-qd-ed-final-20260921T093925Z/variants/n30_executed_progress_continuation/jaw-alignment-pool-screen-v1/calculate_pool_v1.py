#!/usr/bin/env python3
"""Fixed two-pool N30 point-alignment screen. One CPU decode; no production imports."""
import os, sys, pathlib, json, hashlib, time, resource, signal, stat, io, zipfile
import tempfile, collections, traceback
START_CPU=time.process_time(); START_WALL=time.monotonic()
os.sched_setaffinity(0,{0,1})
resource.setrlimit(resource.RLIMIT_CPU,(120,120))
resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[k]='2'
os.environ['CUDA_VISIBLE_DEVICES']=''
import math, csv
H=pathlib.Path(__file__).resolve().parent
INPUT=H/"input-manifest.frozen.v1.json"
DECL=H/"measurement-declaration-v1.json"
MANIFEST=H/"calculation-source-manifest-v1.json"
PRIOR=H.parent/"approach-handoff-review-v1/decode-v1/result-v1.json"
OUTPUT_NAMES={"invocation-v1.json","progress-v1.jsonl","partial-v1.json","result-v1.json","resource-v1.json","pool-table-v1.csv"}
READS=[]; DENIED=[]; PAYLOAD={}; OPEN_COUNTS=collections.Counter(); ACTIVE_PAYLOAD=None
APPROVED=False; ZIP_BYTES=0; STORAGE_BYTES=0; TORCH=None; PARTIAL=[]; ERROR=None
READ_ALLOW={str(p) for p in (INPUT,DECL,MANIFEST,PRIOR,pathlib.Path(__file__).resolve())}
DEPENDENCY_ROOTS=tuple(pathlib.Path(p).resolve() for p in (sys.prefix,sys.base_prefix,'/usr/lib','/usr/lib64','/usr/local/lib','/lib','/lib64'))
RUNTIME_READS={'/proc/self/maps','/proc/cpuinfo','/etc/ld.so.cache','/etc/localtime','/etc/os-release','/usr/lib/os-release','/sys/devices/system/cpu/online'}
DEPENDENCY_OPENS=collections.Counter(); DEPENDENCY_SCANS=collections.Counter()

def require(ok,what):
    if not ok: raise ValueError(what)
def inside(p,root): return p==root or root in p.parents
def permitted_dependency(p):
    return any(inside(p,root) for root in DEPENDENCY_ROOTS) and p.suffix not in {'.pt','.pth','.pkl','.pickle','.npy','.npz','.safetensors','.ckpt'}
def audit(event,args):
    global ACTIVE_PAYLOAD
    if event=='open':
        raw,mode,flags=args
        if isinstance(raw,int): return
        p=pathlib.Path(os.path.abspath(os.fsdecode(raw)))
        writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
        if str(p)=='/dev/null':
            st=os.stat(p); ok=stat.S_ISCHR(st.st_mode) and os.major(st.st_rdev)==1 and os.minor(st.st_rdev)==3
        elif writing: ok=(p.parent==H and p.name in OUTPUT_NAMES) or inside(p,H/'tmp')
        elif str(p) in PAYLOAD:
            ok=APPROVED and str(p)==ACTIVE_PAYLOAD and OPEN_COUNTS[str(p)]==0
            if ok:OPEN_COUNTS[str(p)]+=1
        elif p.suffix in {'.pt','.npy','.npz','.safetensors','.ckpt'}:ok=False
        else:
            ok=str(p) in READ_ALLOW or str(p) in RUNTIME_READS or permitted_dependency(p.resolve()) or inside(p,H/'tmp')
            if ok and str(p) not in READ_ALLOW:DEPENDENCY_OPENS[str(p)]+=1
        if not ok:
            DENIED.append({'event':event,'path':str(p),'writing':writing});raise PermissionError('read/write guard: '+str(p))
    elif event in {'os.listdir','os.scandir'}:
        raw=args[0]
        if isinstance(raw,int):return
        p=pathlib.Path(os.path.abspath(os.fsdecode(raw)))
        ok=p==H or inside(p,H/'tmp') or any(inside(p.resolve(),q) for q in DEPENDENCY_ROOTS)
        if not ok:DENIED.append({'event':event,'path':str(p)});raise PermissionError(event+': '+str(p))
        DEPENDENCY_SCANS[str(p)]+=1
    elif event.startswith(('socket.','subprocess.')) or event in {'os.system','os.exec','os.fork','os.posix_spawn','pty.spawn'}:
        DENIED.append({'event':event});raise PermissionError(event)
    elif event=='import' and args[0].split('.')[0] in {'core','main','requests','httpx'}:
        DENIED.append({'event':event,'module':args[0]});raise PermissionError('production/network import')
sys.addaudithook(audit)
require((H/'tmp').is_dir(),'owned tmp missing')
tempfile.tempdir=str(H/'tmp')
def timeout_handler(*_):raise TimeoutError('bounded wall/CPU deadline')
signal.signal(signal.SIGALRM,timeout_handler);signal.signal(signal.SIGXCPU,timeout_handler);signal.alarm(179)

def write(name,x,exclusive=False):
    require(name in OUTPUT_NAMES,'output name')
    with (H/name).open('x' if exclusive else 'w') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
def read_meta(p,sha=None,cap=8*1024**2,as_json=True):
    p=pathlib.Path(p);st=p.stat();require(stat.S_ISREG(st.st_mode) and st.st_size<=cap,'metadata bound')
    with p.open('rb') as f:b=f.read(cap+1)
    require(len(b)==st.st_size and len(b)<=cap,'metadata changed/oversize')
    h=hashlib.sha256(b).hexdigest();READS.append({'path':str(p),'bytes':len(b),'sha256':h,'kind':'metadata/source'})
    require(sha is None or h==sha,'metadata/source SHA differs')
    return json.loads(b) if as_json else b

def load_one(b):
    global ACTIVE_PAYLOAD, ZIP_BYTES, STORAGE_BYTES
    p=pathlib.Path(b['path']);st=p.lstat()
    require(p.resolve()==p and stat.S_ISREG(st.st_mode) and st.st_size==b['stat_bytes'],'payload path/stat')
    require({k:getattr(st,v) for k,v in [('device','st_dev'),('inode','st_ino'),('mtime_ns','st_mtime_ns')]}==b['stat_identity'],'stat drift')
    ACTIVE_PAYLOAD=str(p)
    try:
        with p.open('rb') as f:raw=f.read(b['stat_bytes']+1)
    finally:ACTIVE_PAYLOAD=None
    h=hashlib.sha256(raw).hexdigest()
    rec={'kind':'payload','path':str(p),'bytes':len(raw),'sha256':h,'load_invocations':0,'decode_succeeded':False}
    READS.append(rec)
    require(len(raw)==b['stat_bytes'] and h==b['sha256'],'payload SHA/length')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();require(len(infos)<=10000 and len({x.filename for x in infos})==len(infos),'ZIP member bound')
        require(all(x.file_size>=0 and not pathlib.PurePosixPath(x.filename).is_absolute() and '..' not in pathlib.PurePosixPath(x.filename).parts for x in infos),'ZIP paths')
        n=sum(x.file_size for x in infos);ZIP_BYTES+=n;rec['zip_uncompressed_bytes']=n
        require(ZIP_BYTES<=128*1024**2,'ZIP cumulative bound')
    rec['load_invocations']=1
    obj=TORCH.load(io.BytesIO(raw),weights_only=True,map_location='cpu');rec['decode_succeeded']=True
    stores={};todo=[obj]
    while todo:
        v=todo.pop()
        if TORCH.is_tensor(v):
            require(v.device.type=='cpu','nonCPU tensor');s=v.untyped_storage();stores[(s.data_ptr(),s.nbytes())]=s.nbytes()
        elif isinstance(v,dict):todo.extend(v.values())
        elif isinstance(v,(list,tuple)):todo.extend(v)
        else:require(v is None or type(v) in (str,int,float,bool),'unexpected object')
    n=sum(stores.values());STORAGE_BYTES+=n;rec['decoded_storage_bytes']=n
    require(STORAGE_BYTES<=128*1024**2,'storage cumulative bound')
    require(obj['schema']=='qd-ed-decision-evidence-v1' and len(obj['events'])==len(b['events']),'container schema/count')
    for e,ix in zip(obj['events'],b['events']):
        require(all(e.get(k)==v for k,v in ix.items()) and e['episode']==0 and e['reset_sequence']==0,'event identity')
        require(e['decision_id']==('e0:d3:s16' if b['role']=='terminal_pool' else 'e0:d2:s8'),'fixed decision identity')
    with (H/'progress-v1.jsonl').open('a') as f:f.write(json.dumps(rec)+'\n')
    return obj['events']

def tensor(x,shape=None):
    require(TORCH.is_tensor(x) and x.device.type=='cpu','CPU tensor required')
    require(shape is None or tuple(x.shape)==tuple(shape),'tensor shape')
    require(bool(TORCH.isfinite(x).all()),'nonfinite allowed field')
    return x
def rawbytes(x):return x.detach().contiguous().reshape(-1).view(TORCH.uint8).numpy().tobytes()
def same(a,b):return TORCH.is_tensor(a) and TORCH.is_tensor(b) and a.dtype==b.dtype and a.shape==b.shape and rawbytes(a)==rawbytes(b)
def equal_tree(a,b):
    if TORCH.is_tensor(a) or TORCH.is_tensor(b):return same(a,b)
    if type(a)!=type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(equal_tree(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal_tree(x,y) for x,y in zip(a,b))
    return a==b
def flag(x):
    if type(x) is bool:return x
    require(type(x) is TORCH.Tensor and x.dtype==TORCH.bool and x.device.type=='cpu' and x.ndim==0,'strict bool')
    return bool(x.item())
def one(events,kind):
    xs=[e for e in events if e['event']==kind];require(len(xs)==1,'one '+kind);return xs[0]
def fingerprint(x):return hashlib.sha256(rawbytes(x.float())).hexdigest()
def geometry(xyz,target,q,g):
    norm=math.sqrt(math.fsum(v*v for v in q));require(math.isfinite(norm) and norm>0,'quaternion norm')
    x,y,z,w=[v/norm for v in q]
    R=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
       [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
       [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
    lower=g[1]+.0005;upper=g[0]-.0005;out=[]
    for pos in xyz:
        delta=[target[j]-pos[j] for j in range(3)]
        a=[math.fsum(R[j][i]*delta[j] for j in range(3)) for i in range(3)]
        excess=[max(abs(a[0])-.008,0),max(lower-a[1],a[1]-upper,0),max(abs(a[2]+.0036)-.008,0)]
        out.append({'target_hand_xyz_m':a,'euclidean_reach_m':math.sqrt(math.fsum(v*v for v in delta)),
            'point_to_prism_m':None if lower>upper else math.sqrt(math.fsum(v*v for v in excess))})
    return out

def analyze(ep,events,prior):
    task=ep['cell']['task_id'];pool_events=[e for e in events if e['decision_id']=='e0:d3:s16']
    before=one(events,'pre_reset_outcome');ret=one(events,'step_returned')
    require(before['global_step']==ret['global_step']==15 and before['sequence']<ret['sequence'],'prior step15 order')
    require(not flag(before['values']['terminated']) and not flag(ret['values']['terminated']) and not flag(ret['values']['truncated']),'reset before decision16')
    obs=before['values']['observation'];pos=tensor(obs['robot0_eef_pos'],(3,));quat=tensor(obs['robot0_eef_quat'],(4,));qpos=tensor(obs['robot0_gripper_qpos'],(2,))
    dc=one(pool_events,'decision_context');pk=one(pool_events,'n30_observation_context');packet=pk['values']['packet'];cur=one(pool_events,'n30_initial_proposal')['values']['current_context']
    require(ret['sequence']<dc['sequence']<pk['sequence'] and dc['global_step']==16,'pre-action order')
    require(packet['episode']==0 and same(tensor(packet['start_eef']).reshape(3),pos),'step15 to decision16 raw EEF dtype/bytes')
    require(equal_tree(packet['keypoints'],dc['values']['keypoints']) and equal_tree(packet['tracker'],dc['values']['keypoint_tracking_snapshot']),'packet/context identity')
    require(flag(dc['values']['use_guidance']) and cur['step']==16 and cur['identity']['episode']==0 and cur['identity']['stage']==dc['values']['stage'],'guided context')
    points=tensor(packet['keypoints']);ti=cur['identity']['target_index'];target=tensor(cur['target'],(3,))
    require(type(ti) is int and 0<=ti<len(points) and same(target,points[ti].double()) and same(cur['start'],pos.double()),'current target/start')
    tr=packet['tracker'];tid=tr['targets'][str(ti)]
    require(tr['instance_id']==cur['identity']['tracker_instance'] and tr['generation']==cur['identity']['tracker_generation'] and tid['status']==cur['identity']['target_status'] and flag(tid['valid']),'tracker binding')
    sel=one(pool_events,'final_selection');sv=sel['values'];term=sv['terminal_population']
    require(term.get('grasp_selection',{}).get('target_index')==ti,'final selector/current target binding')
    population=tensor(sv['population'],(16,64,128));selected=tensor(sv['selected_latent'],(1,64,128))
    byseq={e['sequence']:e for e in pool_events}
    canon=byseq[term['canonical_event_sequence']];score=byseq[term['scoring_batch_id']]
    require(canon['event']=='canonical_candidate_batch' and canon['values']['iter_idx']==9 and same(population,canon['values']['candidates']),'terminal canonical binding')
    require(score['event']=='scoring_inputs' and score['values']['scoring_scope']['iter_idx']==9 and same(population,score['values']['samples']),'terminal scoring binding')
    projection=tensor(score['values']['projected_xyz'],(16,9,3));originseqs=score['values']['projection_origin_sequences']
    require(isinstance(originseqs,list) and len(originseqs)==16 and len(set(originseqs))==16,'16 directly linked origins')
    origin_meta=[]
    for seq in originseqs:
        oe=byseq[seq];require(oe['event']=='projection_origin' and pk['sequence']<seq<score['sequence'],'projection-origin order')
        origin_meta.append({'sequence':seq,'field_names':sorted(oe['values'])})
    costs=tensor(term['native_costs'],(16,));quality=tensor(term['raw_provider_quality'],(16,))
    require(same(quality,canon['values']['effective_quality']),'provider-mode quality/canonical equality')
    ni=one(pool_events,'n30_selected_native_plan')['values'];require(same(ni['native_plan'],selected),'native selected binding')
    require(ni['selected']['start_step']==16 and equal_tree(ni['selected']['identity'],cur['identity']) and same(ni['selected']['target_snapshot'],target),'selected context')
    matches=[i for i in range(16) if same(selected[0],population[i])]
    idx=sv['selected_index'];require(type(idx) is int and 0<=idx<16 and same(selected[0],population[idx]),'selected row identity')
    require(fingerprint(selected[0])==sv['selected_fingerprint'] and fingerprint(selected[0])==canon['values']['canonical_fingerprints'][idx],'selected fingerprint')
    decoded=selected[:,:8,[39,40,41,42,43,44,10]].float().clone()
    decoded[:,:,-1]=TORCH.where(decoded[:,:,-1]<0,-1.,1.)
    for kind,key in [('policy_action_decode','action_chunk'),('n30_decode_binding','actions'),('n30_commit_binding','actions'),('decision_committed','action_chunk')]:
        require(same(decoded,one(pool_events,kind)['values'][key]),'selected decode/commit '+kind)
    require(one(pool_events,'n30_commit_binding')['values']['step']==16 and one(pool_events,'decision_committed')['values']['execution_horizon']==8,'commit step/horizon')
    prior_ep=[e for e in prior['episodes'] if e['attempt_id']==ep['cell']['attempt_id']];require(len(prior_ep)==1,'prior accepted actual commands episode')
    pd=[v for v in prior_ep[0]['decisions'] if v['global_step']==16];require(len(pd)==1,'prior decision16')
    require(same(decoded[0],TORCH.tensor(pd[0]['recorded_first8_commands'],dtype=TORCH.float32)),'prior recorded command binding')
    require([o['step'] for o in pd[0]['observed_steps']]==list(range(16,24)),'actual step coverage')
    for j,o in enumerate(pd[0]['observed_steps']):require(same(decoded[0,j],TORCH.tensor(o['command']['values'],dtype=TORCH.float32)),'prior actual executed command')
    rows=[]
    for i in range(16):
        fp=fingerprint(population[i]);require(fp==canon['values']['canonical_fingerprints'][i],'row fingerprint')
        steps=geometry(projection[i,1:9].double().tolist(),target.tolist(),quat.double().tolist(),qpos.double().tolist())
        signs=[-1 if v<0 else 1 for v in population[i,:8,10].float().tolist()]
        for j,v in enumerate(steps):v.update(offset=j+1,gripper_command=signs[j])
        def minimum(key,close):
            vs=[v[key] for v in steps if v[key] is not None and (not close or v['gripper_command']>0)]
            return min(vs) if vs else None
        rows.append({'task_id':task,'row':i,'selected':i==idx,'same_native_content_as_selected':i in matches,
            'canonical_fingerprint':fp,'occurrence_id':canon['values']['occurrence_ids'][i],
            'native_quality':float(quality[i]),'native_cost':float(costs[i]),'quality_dtype':str(quality.dtype),'cost_dtype':str(costs.dtype),
            'native_plan_dtype':str(population.dtype),'projection_dtype':str(projection.dtype),'close_commands':signs.count(1),'steps':steps,
            'prism_all8_min_m':minimum('point_to_prism_m',False),'prism_close_min_m':minimum('point_to_prism_m',True),
            'reach_all8_min_m':minimum('euclidean_reach_m',False),'reach_close_min_m':minimum('euclidean_reach_m',True)})
    keys=['prism_all8_min_m','prism_close_min_m','reach_all8_min_m','reach_close_min_m','native_cost']
    for row in rows:
        for key in keys:row[key+'_rank']=None if row[key] is None else 1+sum(x[key] is not None and x[key]<row[key] for x in rows)
    selected_row=rows[idx];comparisons={}
    for subset in ('all8','close'):
        pk='prism_'+subset+'_min_m';rk='reach_'+subset+'_min_m'
        comparisons[subset]={'rows_with_both_metrics':sum(x[pk] is not None and x[rk] is not None for x in rows),
            'rank_changed_rows':[x['row'] for x in rows if x[pk+'_rank']!=x[rk+'_rank']],
            'unselected_strictly_better_prism':[x['row'] for x in rows if not x['selected'] and x[pk] is not None and selected_row[pk] is not None and x[pk]<selected_row[pk]],
            'strict_pair_order_reversals':[[i,j] for i in range(16) for j in range(i+1,16) if all(rows[k][v] is not None for k in (i,j) for v in (pk,rk)) and (rows[i][pk]-rows[j][pk])*(rows[i][rk]-rows[j][rk])<0]}
    return {'task_id':task,'attempt_id':ep['cell']['attempt_id'],'decision_id':'e0:d3:s16','selected_row':idx,'selected_native_matching_rows':matches,
        'analyzed_plans':16,'additional_selected_plan_needed':False,'target_index':ti,'target_snapshot':target.tolist(),
        'fixed_state':{'source_step':15,'eef_dtype':str(pos.dtype),'quat_dtype':str(quat.dtype),'qpos_dtype':str(qpos.dtype),'quat_xyzw':quat.tolist(),'qpos':qpos.tolist(),'gap_m':float(qpos[0])-float(qpos[1])-.001},
        'bindings':{'pre_action_raw_eef_bytes_equal':True,'no_reset':True,'selected_actual8_commands_equal':True,'original_receipt_attestation_inherited':ep['receipt'],
            'canonical_sequence':canon['sequence'],'scoring_sequence':score['sequence'],'projection_origins':origin_meta,'selected_sequence':sel['sequence']},
        'projection':'recorded native raw canonical projected_xyz[:,1:9], no reconstruction or clipping; fixed observed hand orientation and qpos',
        'rows':rows,'comparisons':comparisons,'physical_capture_or_future_feasibility':'Unknown'}

def main():
    global TORCH,APPROVED
    require(len(sys.argv)==1,'no argument variation')
    require(not any((H/n).exists() for n in OUTPUT_NAMES),'prior invocation/output, no retry')
    write('invocation-v1.json',{'pid':os.getpid(),'started_unix':time.time(),'payload_reads_yet':0},True)
    manifest=read_meta(MANIFEST);require(manifest['executable_one_pass'] is True,'not frozen')
    for key,path in [('reader',pathlib.Path(__file__).resolve()),('input_manifest',INPUT),('measurement_declaration',DECL)]:
        require(manifest[key]['path']==str(path),'manifest path');read_meta(path,manifest[key]['sha256'],as_json=False)
    inputs=read_meta(INPUT,manifest['input_manifest']['sha256']);read_meta(DECL,manifest['measurement_declaration']['sha256'])
    require(inputs['source_commit']=='6292fc8cffad2eec0f789e023d835ad3c1df146a','source')
    require([e['cell']['task_id'] for e in inputs['episodes']]==[0,1],'both tasks')
    for ep in inputs['episodes']:
        require(ep['receipt_identity']['accepted'] is True and ep['receipt_identity']['attempt_id']==ep['cell']['attempt_id'],'bound original audit accepted')
        for b in ep['containers']:
            require(ep['cell']['attempt_id'] in pathlib.Path(b['path']).parts and b['path'] not in PAYLOAD,'exact attempt/path');PAYLOAD[b['path']]=b
    require(len(PAYLOAD)==4 and sum(x['stat_bytes'] for x in PAYLOAD.values())==inputs['limits']['encoded_bytes']<=64*1024**2,'four-container byte cap')
    prior=read_meta(PRIOR,inputs['prior_executed_commands']['sha256']);require(prior['complete'] is True,'prior complete')
    APPROVED=True
    import torch
    TORCH=torch;torch.set_num_threads(2);torch.set_num_interop_threads(2)
    require(not torch.cuda.is_initialized(),'CUDA initialized')
    for ep in inputs['episodes']:
        events=[]
        for b in ep['containers']:events.extend(load_one(b))
        PARTIAL.append(analyze(ep,events));write('partial-v1.json',{'complete':False,'episodes':PARTIAL});del events
    require(len(OPEN_COUNTS)==4 and all(v==1 for v in OPEN_COUNTS.values()),'single filesystem opens')
    require(not torch.cuda.is_initialized(),'CUDA initialized')
    write('result-v1.json',{'schema':'n30-fixed-jaw-pool-screen-v1','complete':True,'episodes':PARTIAL,'precision':'CPU binary64 geometry on recorded native projection, no CUDA replay','new_score_calls':0,'physical_benefit':'Unknown','algorithm_release':False})
    rows=[{k:v for k,v in row.items() if k!='steps'} for ep in PARTIAL for row in ep['rows']]
    with (H/'pool-table-v1.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

if __name__=='__main__':
    try:main()
    except BaseException as e:
        ERROR={'type':type(e).__name__,'message':str(e)};traceback.print_exc()
    finally:
        signal.alarm(0)
        record={'pid':os.getpid(),'complete':ERROR is None and len(PARTIAL)==2,'error':ERROR,'cpu_seconds':time.process_time()-START_CPU,'wall_seconds':time.monotonic()-START_WALL,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rlimit_cpu':list(resource.getrlimit(resource.RLIMIT_CPU)),'rlimit_as':resource.getrlimit(resource.RLIMIT_AS)[0],
            'affinity':sorted(os.sched_getaffinity(0)),'threads':2,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'cuda_initialized':TORCH.cuda.is_initialized() if TORCH is not None else None,
            'explicit_cuda_tensor_work':0,'no_driver_probe_claim':False,'reads':READS,'payload_open_counts':dict(OPEN_COUNTS),'zip_uncompressed_bytes':ZIP_BYTES,'decoded_cpu_storage_bytes':STORAGE_BYTES,
            'denied_probes':DENIED,'guard_clean':not DENIED,'dependency_opens':dict(DEPENDENCY_OPENS),'dependency_scans':dict(DEPENDENCY_SCANS),'automatic_retries':0,'completed_episodes':len(PARTIAL)}
        if not (H/'resource-v1.json').exists():write('resource-v1.json',record,True)
    if ERROR is not None:sys.exit(1)
