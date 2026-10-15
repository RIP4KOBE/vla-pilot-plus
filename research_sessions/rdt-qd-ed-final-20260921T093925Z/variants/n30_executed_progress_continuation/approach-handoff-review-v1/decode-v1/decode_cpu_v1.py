#!/usr/bin/env python3
"""One released N30 CPU approach-to-handoff decode. No production imports."""
import os, sys, pathlib, json, hashlib, time, resource, signal, stat, io, zipfile
import tempfile, collections, traceback
START_CPU=time.process_time(); START_WALL=time.monotonic()
os.sched_setaffinity(0,{0,1})
resource.setrlimit(resource.RLIMIT_CPU,(120,120))
resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[k]='2'
os.environ['CUDA_VISIBLE_DEVICES']=''
H=pathlib.Path(__file__).resolve().parent; D=H.parent
BINDINGS=D/'handoff-bindings.disabled.v1.json'
PROTOCOL=D/'minimum-evidence-proposal.disabled.v1.json'
REVIEW=D/'root-terminal-review-v1.json'
SCOPE=H/'root-preparation-scope-v1.md'
MANIFEST=H/'decoder-source-manifest-v1.json'
RELEASE=H/'root-execution-release-v1.json'
SOURCE_COMMIT='6292fc8cffad2eec0f789e023d835ad3c1df146a'
W=D.parents[2]/'study_worktree'
SOURCE_PATHS={str(W/x) for x in ('core/decision_evidence.py','core/rdt_policy_steer.py','core/qd_executed_progress.py','scripts/qd_ed_n30_native.py')}
INPUT_SHA='a0e91ccb47a312a37e46b9c9ac9d6dcf8c3ec211d2cbb07a8084b6f8b6ad4345'
PROTOCOL_SHA='b3d1ce66d932f517be84100cecc33f2a2e669efb47eeb4c41199ab86f4e05e97'
REVIEW_SHA='9abbe70fcc2797f11798624d2c5b73007bc54f6616a37133b85f3eea38cec58e'
SCOPE_SHA='da8415d563b1641df753db8bf22e5131efa8f62f35f92ce55a104697b3497ce8'
OUTPUT_NAMES={'invocation-v1.json','progress-v1.jsonl','partial-v1.json','result-v1.json','resource-v1.json','summary-v1.md'}
LIMITS={'containers':68,'container_bytes':24429984,'loads_per_container':1,'cpu_seconds':120,'wall_seconds':120,'address_space_bytes':16*1024**3,'zip_uncompressed_bytes':64*1024**2,'cpu_storage_bytes':64*1024**2,'threads':2,'affinity':[0,1]}
READS=[]; DENIED=[]; PAYLOAD={}; OPEN_COUNTS=collections.Counter(); ACTIVE_PAYLOAD=None
APPROVED=False; ZIP_BYTES=0; STORAGE_BYTES=0; TORCH=None; PARTIAL=[]; ERROR=None
READ_ALLOW={str(p) for p in (BINDINGS,PROTOCOL,REVIEW,SCOPE,MANIFEST,RELEASE,pathlib.Path(__file__).resolve())}
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
signal.signal(signal.SIGALRM,timeout_handler);signal.signal(signal.SIGXCPU,timeout_handler);signal.alarm(119)

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

def authorize():
    global APPROVED
    require(len(sys.argv)==3 and sys.argv[1]=='--release' and pathlib.Path(sys.argv[2]).absolute()==RELEASE,'exact release CLI required')
    require(not any((H/n).exists() for n in OUTPUT_NAMES),'prior invocation/output exists: no automatic retry')
    write('invocation-v1.json',{'pid':os.getpid(),'started_unix':time.time(),'source_commit':SOURCE_COMMIT,'payload_access_yet':False},exclusive=True)
    release=read_meta(RELEASE,cap=65536)
    require(release.get('schema')=='n30-approach-handoff-execution-release-v1' and release.get('executable') is True,'not released')
    require(release.get('limits')==LIMITS,'release limits differ')
    require(release.get('source_commit')==SOURCE_COMMIT,'source commit differs')
    def fixed_ref(key,p,h=None):
        x=release[key];require(set(x)=={'path','sha256'} and x['path']==str(p),'release ref path differs: '+key)
        if h:require(x['sha256']==h,'release ref hash differs: '+key)
        return x['sha256']
    read_meta(__file__,fixed_ref('reader',pathlib.Path(__file__).resolve()),as_json=False)
    bindings=read_meta(BINDINGS,fixed_ref('input_bindings',BINDINGS,INPUT_SHA))
    read_meta(PROTOCOL,fixed_ref('protocol',PROTOCOL,PROTOCOL_SHA))
    read_meta(REVIEW,fixed_ref('phase_c_review',REVIEW,REVIEW_SHA))
    read_meta(SCOPE,SCOPE_SHA,as_json=False)
    manifest=read_meta(MANIFEST,fixed_ref('source_manifest',MANIFEST))
    require(manifest['source_commit']==SOURCE_COMMIT,'manifest source')
    require(manifest['reader']==release['reader'],'manifest reader binding')
    require(len(manifest['scientific_source_files'])==4 and {x['path'] for x in manifest['scientific_source_files']}==SOURCE_PATHS,'exact scientific source list')
    require(manifest['input_bindings']==release['input_bindings'] and manifest['protocol']==release['protocol'],'manifest inputs')
    for x in manifest['scientific_source_files']:
        p=pathlib.Path(x['path']);require(p.is_absolute() and p.suffix=='.py','source type')
        READ_ALLOW.add(str(p));read_meta(p,x['sha256'],as_json=False)
    require(bindings['limits']=={'episodes':2,'decisions':4,'files':68,'stat_bytes':24429984,'loads_per_file':1},'bindings limits')
    require([e['cell']['task_id'] for e in bindings['episodes']]==[0,1],'all cells/order')
    require([e['cell']['attempt_id'].rsplit('__',1)[-1] for e in bindings['episodes']]==['4300bcf89485','1e52b07e1725'],'attempt IDs')
    for ep in bindings['episodes']:
        require(ep['cell']['source_commit']==SOURCE_COMMIT and ep['cell']['profile']=='N30','cell/source identity')
        pairs=ep['first_realized_eds_handoff']
        require([(x['decision']['decision_id'],x['decision']['step'],x['decision']['reset_sequence']) for x in pairs]==[('e0:d3:s16',16,0),('e0:d4:s24',24,0)],'fixed first handoff identity')
        require(len(ep['containers'])==34,'per episode container count')
        for b in ep['containers']:
            p=pathlib.Path(b['path']);require(p.is_absolute() and p.name.startswith('bundle_') and p.suffix=='.pt','payload name')
            require(ep['cell']['attempt_id'] in p.parts and p.parent.name=='episode_000','episode path')
            require(b['decision_id'] in {'e0:d3:s16','e0:d4:s24'},'fixed payload decision')
            require(str(p) not in PAYLOAD,'duplicate payload')
            require(b['existing_index_sha256']==b['existing_receipt_sha256'],'index/receipt SHA disagree')
            PAYLOAD[str(p)]=b
    require(len(PAYLOAD)==68 and sum(x['stat_bytes'] for x in PAYLOAD.values())==24429984,'payload set size')
    APPROVED=True
    return bindings

# Only these fields survive the whole-container load. No candidate values/scores.
VALUE_KEYS={
 'decision_context':{'stage','previous_stage','previous_decision_id','stage_changed','use_guidance','keypoints','keypoint_tracking_snapshot','providers'},
 'n30_observation_context':{'packet'},
 'n30_initial_proposal':{'current_context'},
 'n30_selected_native_plan':{'selected'},
 'final_selection':{'selected_index','selected_fingerprint','selected_canonical_fingerprint'},
 'n30_decode_binding':{'actions'},
 'policy_action_decode':{'action_chunk'},
 'n30_commit_binding':{'actions','execution_horizon','step','committed'},
 'decision_committed':{'action_chunk','execution_horizon'},
 'executed_action':{'action_numpy'},
 'pre_reset_outcome':{'observation','terminated','origin','contemporaneous_target_pose'},
 'n30_actual_ack':{'global_step','execution_index','action','endpoint','terminated','truncated','completed'},
 'step_returned':{'terminated','truncated'},
}
PROVIDER_DIGEST_KEYS=('code_sha256','original_code_sha256','source_text_sha256')
CONTEXT_IDENTITY_KEYS=('episode','reset_generation','stage','target_index','tracker_instance','tracker_generation','target_status')

def narrowed_identity(value):
    return {k:value[k] for k in CONTEXT_IDENTITY_KEYS if k in value} if isinstance(value,dict) else value

def provider_digests(value):
    if value is None:return None
    require(isinstance(value,list) and len(value)<=64,'provider identity count/type')
    result=[]
    for i,p in enumerate(value):
        require(isinstance(p,dict) and p.get('ordinal')==i,'provider ordinal')
        r={'ordinal':i}
        for k in PROVIDER_DIGEST_KEYS:
            v=p.get(k);require(v is None or (isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v)),'provider digest format')
            r[k]=v
        result.append(r)
    return result

def load_one(b,ep):
    global ACTIVE_PAYLOAD, ZIP_BYTES, STORAGE_BYTES
    p=pathlib.Path(b['path'])
    for q in (p,p.parent,p.parent.parent,p.parent.parent.parent):require(not q.is_symlink(),'payload symlink')
    st=p.lstat();require(stat.S_ISREG(st.st_mode) and st.st_size==b['stat_bytes'],'payload stat size/type')
    require(p.resolve()==p,'payload path resolves elsewhere')
    require({k:getattr(st,{'device':'st_dev','inode':'st_ino','mtime_ns':'st_mtime_ns'}[k]) for k in b['stat_identity']}==b['stat_identity'],'payload stat identity drift')
    ACTIVE_PAYLOAD=str(p)
    try:
        with p.open('rb') as f:raw=f.read(b['stat_bytes']+1)
    finally:ACTIVE_PAYLOAD=None
    digest=hashlib.sha256(raw).hexdigest()
    record={'path':str(p),'bytes':len(raw),'sha256':digest,'kind':'payload','filesystem_opens':OPEN_COUNTS[str(p)],'load_invocations':0,'decode_succeeded':False}
    READS.append(record)
    require(len(raw)==b['stat_bytes'] and digest==b['existing_index_sha256'],'payload bytes/hash differ')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();require(len(infos)<=10000 and len({i.filename for i in infos})==len(infos),'ZIP member count/duplicate')
        for i in infos:require(i.file_size>=0 and not pathlib.PurePosixPath(i.filename).is_absolute() and '..' not in pathlib.PurePosixPath(i.filename).parts,'ZIP member')
        size=sum(i.file_size for i in infos);ZIP_BYTES+=size;require(ZIP_BYTES<=LIMITS['zip_uncompressed_bytes'],'ZIP cumulative uncompressed cap')
    record['zip_uncompressed_bytes']=size
    record['load_invocations']=1
    obj=TORCH.load(io.BytesIO(raw),weights_only=True,map_location='cpu')
    record['decode_succeeded']=True
    stores={};walk=[obj]
    while walk:
        v=walk.pop()
        if TORCH.is_tensor(v):
            require(v.device.type=='cpu','nonCPU tensor')
            stg=v.untyped_storage();stores[(stg.data_ptr(),stg.nbytes())]=stg.nbytes()
        elif isinstance(v,dict):walk.extend(v.values())
        elif isinstance(v,(list,tuple)):walk.extend(v)
        else:require(v is None or type(v) in (str,int,float,bool),'unexpected decoded object type')
    sb=sum(stores.values());STORAGE_BYTES+=sb;require(STORAGE_BYTES<=LIMITS['cpu_storage_bytes'],'cumulative decoded storage cap')
    record['deduplicated_storage_bytes']=sb
    require(obj['schema']=='qd-ed-decision-evidence-v1','container schema')
    indexes=sorted(b['requested_events']+b['co_resident_events'],key=lambda x:x['sequence'])
    require(len({x['sequence'] for x in indexes})==len(indexes),'duplicate indexed sequence')
    require(len(obj['events'])==len(indexes),'container/index event count')
    selected=[]
    for event,ix in zip(obj['events'],indexes):
        require(all(event.get(k)==v for k,v in ix.items()),'container/index event identity')
        require(event['episode']==0 and event['decision_id']==b['decision_id'] and event['reset_sequence']==0,'episode/decision/reset identity')
        if event['event'] not in VALUE_KEYS:continue
        v=event['values'];picked={k:v[k] for k in VALUE_KEYS[event['event']] if k in v}
        if event['event']=='decision_context':
            picked['providers']=provider_digests(picked.get('providers'))
        if event['event']=='n30_initial_proposal' and isinstance(picked.get('current_context'),dict):
            cur=picked['current_context'];picked['current_context']={k:cur[k] for k in ('step','start','target') if k in cur}
            picked['current_context']['identity']=narrowed_identity(cur.get('identity'))
        if event['event']=='n30_selected_native_plan' and isinstance(picked.get('selected'),dict):
            sel=picked['selected'];picked['selected']={k:sel[k] for k in ('native_identity','start_step','start_eef','target_snapshot','native_dtype') if k in sel}
            picked['selected']['identity']=narrowed_identity(sel.get('identity'))
        if event['event']=='pre_reset_outcome':
            picked['observation']={k:v.get('observation',{}).get(k) for k in ('robot0_eef_pos','robot0_eef_quat','robot0_gripper_qpos','robot0_gripper_qvel')}
            picked['contemporaneous_target_pose_present']=picked.pop('contemporaneous_target_pose',None) is not None
        if event['event']=='n30_actual_ack' and picked.get('completed') is not None:
            picked['completed']={k:picked['completed'][k] for k in ('selected_native_identity','ack_count')}
        selected.append({k:event[k] for k in ('sequence','event','episode','decision_id','global_step','reset_sequence')}|{'values':picked})
    with (H/'progress-v1.jsonl').open('a') as f:f.write(json.dumps(record,allow_nan=False)+'\n')
    return selected

def tensor(x,shape=None):
    require(TORCH.is_tensor(x) and x.device.type=='cpu','CPU tensor required')
    require(shape is None or tuple(x.shape)==tuple(shape),'tensor shape')
    require(bool(TORCH.isfinite(x).all()),'nonfinite allowed-field tensor')
    return x

def rawbytes(x):return x.detach().contiguous().reshape(-1).view(TORCH.uint8).numpy().tobytes()
def same(a,b):return TORCH.is_tensor(a) and TORCH.is_tensor(b) and a.dtype==b.dtype and tuple(a.shape)==tuple(b.shape) and rawbytes(a)==rawbytes(b)
def equal_tree(a,b):
    if TORCH.is_tensor(a) or TORCH.is_tensor(b):return same(a,b)
    if type(a)!=type(b):return False
    if isinstance(a,dict):return set(a)==set(b) and all(equal_tree(a[k],b[k]) for k in a)
    if isinstance(a,(tuple,list)):return len(a)==len(b) and all(equal_tree(x,y) for x,y in zip(a,b))
    return a==b
def native_id(x):return hashlib.sha256(str((str(x.dtype),tuple(x.shape))).encode()+rawbytes(x)).hexdigest()
def flag(x):
    if type(x) is bool:return x
    require(type(x) is TORCH.Tensor and x.device.type=='cpu' and x.dtype==TORCH.bool and x.ndim==0,'strict boolean')
    return bool(x.item())

def optional_float_tensor(x,shape=None,vector_cap=None):
    if x is None:return None
    x=tensor(x,shape);require(x.is_floating_point(),'floating observed field required')
    if vector_cap is not None:require(x.ndim==1 and 0<x.numel()<=vector_cap,'bounded observed vector')
    return x

def observed(x,shape=None,vector_cap=None):
    x=optional_float_tensor(x,shape,vector_cap)
    return None if x is None else {'dtype':str(x.dtype),'shape':list(x.shape),'values':x.tolist()}

def vector(x,shape=(3,)):
    return optional_float_tensor(x,shape)

def optional_int(x):
    require(x is None or type(x) is int,'integer identity or missing required');return x

def distance(a,b):
    return None if a is None or b is None else float(TORCH.linalg.vector_norm(a.double()-b.double()))

def difference(a,b):
    return None if a is None or b is None else (a.double()-b.double()).tolist()

def target_identity(tr,ti):
    if not isinstance(tr,dict) or ti is None:return None
    targets=tr.get('targets');v=targets.get(str(ti)) if isinstance(targets,dict) else None
    if not isinstance(v,dict):return None
    valid=None if v.get('valid') is None else flag(v['valid'])
    status=v.get('status');require(status is None or isinstance(status,str),'target status type')
    return {'tracker_instance':optional_int(tr.get('instance_id')),
            'tracker_generation':optional_int(tr.get('generation')),'target_index':ti,
            'valid':valid,'status':status}

def analyze(ep,events):
    ongoing={'task_id':ep['cell']['task_id'],'attempt_id':ep['cell']['attempt_id'],
        'source_commit':SOURCE_COMMIT,'decisions':[],'complete':False}
    def checkpoint():write('partial-v1.json',{'complete':False,'episodes':PARTIAL,'current':ongoing})
    checkpoint()
    require(len({e['sequence'] for e in events})==len(events),'duplicate extracted events')
    previous_endpoint=None;previous_action=None;previous_return_seq=None;previous_terminal=False
    fixed_target=None;fixed_ti=None;fixed_ident=None;first_stage=None;first_dc=None
    for pair in ep['first_realized_eds_handoff']:
        require(not previous_terminal,'decision after previous terminal/truncation')
        meta=pair['decision'];did=meta['decision_id'];step0=meta['step'];kinds=collections.defaultdict(list)
        for e in sorted(events,key=lambda x:x['sequence']):
            if e['decision_id']==did:kinds[e['event']].append(e)
        def one(k):require(len(kinds[k])==1,'expected one '+k);return kinds[k][0]
        def val(k):return one(k)['values']
        dc=val('decision_context');packet=val('n30_observation_context').get('packet')
        require(isinstance(packet,dict),'observation packet missing')
        require(packet.get('episode')==0,'packet episode identity')
        require(one('decision_context')['global_step']==one('n30_observation_context')['global_step']==step0,'decision start step')
        require(one('decision_context')['sequence']<one('n30_observation_context')['sequence'],'context packet order')
        points=optional_float_tensor(packet.get('keypoints'))
        if points is not None:require(points.ndim==2 and points.shape[1]==3 and points.shape[0]<=256,'keypoint shape bound')
        dc_points=optional_float_tensor(dc.get('keypoints'))
        require(equal_tree(points,dc_points),'packet/context keypoints differ')
        tr=packet.get('tracker');require(equal_tree(tr,dc.get('keypoint_tracking_snapshot')),'packet/context tracker differs')
        start=vector(packet.get('start_eef'))
        stage=optional_int(dc.get('stage'));prev_stage=optional_int(dc.get('previous_stage'))
        guided=None if dc.get('use_guidance') is None else flag(dc['use_guidance'])
        changed=None if dc.get('stage_changed') is None else flag(dc['stage_changed'])
        if stage is not None and prev_stage is not None and changed is not None:require(changed==(stage!=prev_stage),'recorded stage-change mismatch')
        if step0==24:
            require(dc.get('previous_decision_id')=='e0:d3:s16','adjacent decision link')
            if prev_stage is not None and first_stage is not None:require(prev_stage==first_stage,'previous stage link')
        providers=dc.get('providers')  # Already sanitized to exact digest keys by load_one.
        proposal=val('n30_initial_proposal') if kinds['n30_initial_proposal'] else None
        cur=proposal.get('current_context') if proposal is not None else None
        selected=val('n30_selected_native_plan').get('selected') if kinds['n30_selected_native_plan'] else None
        ci=cur.get('identity') if isinstance(cur,dict) else None
        target=None;ti=None
        if cur is not None:
            require(isinstance(cur,dict) and isinstance(ci,dict) and cur.get('step')==step0,'current target identity')
            ti=optional_int(ci.get('target_index'))
            target=vector(cur.get('target'));cs=vector(cur.get('start'))
            require(start is not None and cs is not None and same(cs,start.double()),'recorded current/raw start mismatch')
            require(ci.get('episode')==0 and ci.get('stage')==stage,'current episode/stage mismatch')
            if ti is not None:
                require(ti>=0 and points is not None and ti<points.shape[0],'recorded target index bound')
                require(target is not None and same(target,points[ti].double()),'recorded target/raw snapshot mismatch')
                tid=target_identity(tr,ti)
                require(tid is not None and tid['tracker_instance']==ci.get('tracker_instance') and tid['tracker_generation']==ci.get('tracker_generation') and tid['status']==ci.get('target_status'),'current/tracker identity mismatch')
            require(selected is None or (isinstance(selected,dict) and selected.get('start_step')==step0 and equal_tree(selected.get('identity'),ci)),'selected/current identity mismatch')
            if selected is not None:
                require(same(selected.get('start_eef'),cs) and same(selected.get('target_snapshot'),target),'selected context snapshot mismatch')
        if step0==16:
            fixed_target=target;fixed_ti=ti;fixed_ident=target_identity(tr,ti);first_stage=stage;first_dc=dc
        inherited_ti_snapshot=None
        next_old_ident=target_identity(tr,fixed_ti)
        same_tracker=(fixed_ident is not None and next_old_ident is not None and all(fixed_ident[k] is not None and fixed_ident[k]==next_old_ident[k] for k in ('tracker_instance','tracker_generation','target_index')))
        if fixed_ti is not None and points is not None and fixed_ti<points.shape[0] and same_tracker:
            inherited_ti_snapshot=points[fixed_ti]
        # This observation is of the predecessor's keypoint index, not an inferred new-task target.
        phase={'decision_id':did,'global_step':step0,'reset_sequence':meta['reset_sequence'],
            'stage':stage,'previous_stage':prev_stage,'stage_changed':changed,'use_guidance':guided,
            'original_stage_query_need_guidance':None,'disable_cause':'Unknown: final context cannot distinguish Stage response from Main missing functions',
            'provider_count':None if providers is None else len(providers),'provider_identity_digests':providers,
            'current_recognized_target_index':ti,'current_recognized_target_snapshot':observed(target,(3,)),
            'predecessor_target_identity':fixed_ident,'current_snapshot_of_predecessor_target_identity':next_old_ident,
            'same_predecessor_tracker_identity':same_tracker if fixed_ident is not None and next_old_ident is not None else None,
            'current_snapshot_at_predecessor_target_index':observed(inherited_ti_snapshot,(3,)),
            'keypoint_snapshot_metadata':None if points is None else {'shape':list(points.shape),'dtype':str(points.dtype)},
            'start_eef':observed(start,(3,)),'start_distance_to_fixed_step16_target_m':distance(start,fixed_target),
            'distance_scope':'fixed predecessor step16 snapshot; not contemporaneous object ground truth or necessarily current-stage target',
            'realized_canonical_batches':meta['event_counts'].get('canonical_candidate_batch',0),
            'native_selection_arithmetic':'inherited bound worker audit; not replayed or latent-rehashed here',
            'observed_steps':[],'complete':False}
        ongoing['decisions'].append(phase);checkpoint()
        if step0==24:
            phase['stage_same_as_predecessor']=None if stage is None or first_stage is None else stage==first_stage
            phase['provider_digests_same_as_predecessor']=None if providers is None or first_dc.get('providers') is None else providers==first_dc['providers']
            phase['start24_vs_step23_outcome_native_equal']=None if start is None or previous_endpoint is None else same(start,previous_endpoint)
            if start is not None and previous_endpoint is not None:require(same(start,previous_endpoint),'start24/step23 raw feedback mismatch')
        commands=optional_float_tensor(val('decision_committed').get('action_chunk'),(1,8,7))
        require(commands is not None and commands.dtype==TORCH.float32,'recorded decoded command dtype/shape')
        for k,field in [('policy_action_decode','action_chunk'),('n30_decode_binding','actions'),('n30_commit_binding','actions')]:
            require(same(val(k).get(field),commands),'recorded decode/commit command mismatch: '+k)
        cm=val('n30_commit_binding');require(val('decision_committed').get('execution_horizon')==cm.get('execution_horizon')==8 and cm.get('step')==step0,'recorded full8 horizon/step')
        phase['n30_history_committed']=flag(cm.get('committed'))
        phase['actual_execution_gate']='decision_committed + indexed dispatch + executed_action + outcome + returned; N30 history flag is not an execution gate'
        require(one('policy_action_decode')['sequence']<one('n30_commit_binding')['sequence']<one('decision_committed')['sequence'],'decoded/commit order')
        require(one('n30_decode_binding')['sequence']<one('decision_committed')['sequence'],'N30 decode/commit order')
        require(one('n30_observation_context')['sequence']<one('decision_committed')['sequence'],'raw observation precedes commit')
        phase['command_dtype']=str(commands.dtype);phase['recorded_first8_commands']=commands[0].tolist()
        if kinds['final_selection']:
            f=val('final_selection');phase['selection_identity']={k:f.get(k) for k in ('selected_index','selected_fingerprint','selected_canonical_fingerprint')}
        else:phase['selection_identity']=None
        expected_steps=list(range(step0,step0+8))
        require([x['step'] for x in pair['ordered_actual_feedback']]==expected_steps,'indexed actual step coverage')
        for k in ('executed_action','pre_reset_outcome','step_returned'):
            require([e['global_step'] for e in kinds[k]]==expected_steps,'actual event coverage: '+k)
        require(len(kinds['n30_actual_ack']) in (0,8),'partial recorded N30 ack coverage')
        phase['n30_ack_count']=len(kinds['n30_actual_ack'])
        terminal=False;prefix_start=start;prev=start;initial_distance=distance(start,fixed_target)
        for i,ix in enumerate(pair['ordered_actual_feedback']):
            step=ix['step'];act=kinds['executed_action'][i];out=kinds['pre_reset_outcome'][i];ret=kinds['step_returned'][i]
            require(not terminal,'actual feedback continues beyond termination')
            for kind,e in [('executed_action',act),('pre_reset_outcome',out),('step_returned',ret)]:
                require(e['sequence']==ix[kind]['sequence'] and e['reset_sequence']==ix[kind]['reset_sequence']==0,'indexed event binding: '+kind)
            require(one('decision_committed')['sequence']<ix['action_dispatch']['sequence']<act['sequence']<out['sequence']<ret['sequence'],'dispatch/action/outcome/return order')
            if previous_return_seq is not None:require(previous_return_seq<act['sequence'],'cross-step feedback order')
            action=optional_float_tensor(act['values'].get('action_numpy'),(7,));require(action is not None and same(action,commands[0,i]),'actual command differs from recorded commit')
            ov=out['values'];obs=ov.get('observation',{});endpoint=vector(obs.get('robot0_eef_pos'))
            quat=vector(obs.get('robot0_eef_quat'),(4,));qpos=optional_float_tensor(obs.get('robot0_gripper_qpos'),vector_cap=16);qvel=optional_float_tensor(obs.get('robot0_gripper_qvel'),vector_cap=16)
            term=flag(ret['values'].get('terminated'));trunc=flag(ret['values'].get('truncated'))
            require(flag(ov.get('terminated'))==term,'pre-reset/return terminal mismatch')
            if kinds['n30_actual_ack']:
                ack=kinds['n30_actual_ack'][i];av=ack['values']
                require(ack['global_step']==av.get('global_step')==step and av.get('execution_index')==i+1,'N30 ack 1-based step identity')
                require(out['sequence']<ack['sequence']<ret['sequence'],'N30 ack ordering')
                require(same(av.get('action'),action) and equal_tree(av.get('endpoint'),endpoint),'N30 ack actual command/endpoint mismatch')
                require(flag(av.get('terminated'))==term and flag(av.get('truncated'))==trunc,'N30 ack terminal mismatch')
                completed=av.get('completed')
                if completed is not None:
                    require(i==7 and not(term or trunc) and completed.get('ack_count')==8,'N30 completion timing')
                    require(isinstance(selected,dict) and completed.get('selected_native_identity')==selected.get('native_identity'),'N30 completion selected identity')
            terminal=term or trunc
            dist=distance(endpoint,fixed_target)
            row={'step':step,'execution_index_from_bound_commit':i+1,
                'event_sequences':{'dispatch_index':ix['action_dispatch']['sequence'],'executed_action':act['sequence'],'pre_reset_outcome':out['sequence'],'step_returned':ret['sequence']},
                'command':observed(action,(7,)),'eef_position':observed(endpoint,(3,)),'eef_quaternion':observed(quat,(4,)),
                'gripper_qpos':observed(qpos,vector_cap=16),'gripper_qvel':observed(qvel,vector_cap=16),
                'eef_displacement_from_previous_observation_m':difference(endpoint,prev),'eef_step_distance_m':distance(endpoint,prev),
                'distance_to_fixed_step16_target_m':dist,'approach_from_this_prefix_start_to_fixed_snapshot_m':None if initial_distance is None or dist is None else initial_distance-dist,
                'terminated':term,'truncated':trunc,'outcome_origin':ov.get('origin'),'contemporaneous_target_pose_present':ov.get('contemporaneous_target_pose_present'),
                'contact_grasp_holding':'Unknown, not inferred from gripper/EEF'}
            if step==24:
                row['boundary23_to24_command_translation_change_l2']=None if previous_action is None else distance(action[:3],previous_action[:3])
                row['boundary23_to24_command_gripper_sign_changed']=None if previous_action is None else bool((action[-1]>=0).item())!=bool((previous_action[-1]>=0).item())
                row['boundary23_to24_eef_motion_m']=difference(endpoint,previous_endpoint)
                row['boundary23_to24_old_snapshot_distance_change_m']=None if endpoint is None or previous_endpoint is None or fixed_target is None else distance(endpoint,fixed_target)-distance(previous_endpoint,fixed_target)
            phase['observed_steps'].append(row)
            prev=endpoint;previous_endpoint=endpoint;previous_action=action;previous_return_seq=ret['sequence'];previous_terminal=terminal;checkpoint()
        final_distance=distance(prev,fixed_target)
        phase['net_eef_motion_m']=difference(prev,prefix_start)
        phase['net_eef_displacement_norm_m']=distance(prev,prefix_start)
        phase['net_approach_to_fixed_step16_snapshot_m']=None if initial_distance is None or final_distance is None else initial_distance-final_distance
        phase['command_gripper_sign_changes_within8']=sum(bool((commands[0,j,-1]>=0).item())!=bool((commands[0,j-1,-1]>=0).item()) for j in range(1,8))
        phase['complete']=True;checkpoint()
    ongoing['fixed_step16_target_snapshot']=observed(fixed_target,(3,));ongoing['complete']=True
    ongoing['limitations']=['Two preregistered first handoffs only, not complete-episode dynamics.',
        'Final use_guidance is not the original Stage query response; disable cause remains Unknown.',
        'Target identity is native-recorded identity; semantic correct-object identity and grasp/contact are not established.',
        'Distances use the one step16 target snapshot, not moving object ground truth or new-stage progress.',
        'Native selection/decoder source validity inherited from accepted worker audit; this reader only binds recorded commands, never reruns decoder/model/scorer.',
        'No causal effect or benefit of retaining EDS, memory, or warm ancestry follows from temporal change.']
    checkpoint();return ongoing

def main():
    global TORCH
    bindings=authorize()
    import torch
    TORCH=torch;torch.set_num_threads(2);torch.set_num_interop_threads(2)
    require(not torch.cuda.is_initialized(),'CUDA initialized at import')
    for ep in bindings['episodes']:
        events=[]
        for b in ep['containers']:events.extend(load_one(b,ep))
        PARTIAL.append(analyze(ep,events));write('partial-v1.json',{'complete':False,'episodes':PARTIAL})
        del events
    require(len(OPEN_COUNTS)==68 and all(v==1 for v in OPEN_COUNTS.values()),'one filesystem read each')
    require(sum(x['bytes'] for x in READS if x['kind']=='payload')==24429984,'total payload bytes')
    require(not torch.cuda.is_initialized(),'CUDA initialized during CPU analysis')
    write('result-v1.json',{'schema':'n30-approach-handoff-cpu-result-v1','complete':True,'source_commit':SOURCE_COMMIT,'input_sha256':INPUT_SHA,
        'episodes':PARTIAL,'algorithm_nomination':None,'scientific_result_authority':False})

if __name__=='__main__':
    try:main()
    except BaseException as e:
        ERROR={'type':type(e).__name__,'message':str(e)}
        traceback.print_exc()
    finally:
        signal.alarm(0)
        # Resource finalization never retries inputs. SIGKILL can leave progress without final resource.
        record={'schema':'n30-handoff-decode-resource-v1','pid':os.getpid(),'cpu_seconds':time.process_time()-START_CPU,'wall_seconds':time.monotonic()-START_WALL,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rlimit_as_bytes':resource.getrlimit(resource.RLIMIT_AS)[0],'rlimit_cpu':list(resource.getrlimit(resource.RLIMIT_CPU)),
            'affinity':sorted(os.sched_getaffinity(0)),'threads':2,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'cuda_initialized':TORCH.cuda.is_initialized() if TORCH is not None else None,
            'explicit_cuda_tensor_work':0,'cuda_driver_probe_absence_claimed':False,'torch_imported':TORCH is not None,'reads':READS,'payload_open_counts':dict(OPEN_COUNTS),
            'zip_uncompressed_bytes':ZIP_BYTES,'decoded_cpu_storage_bytes':STORAGE_BYTES,'denied_probes':DENIED,'guard_clean':not DENIED,'dependency_opens':dict(DEPENDENCY_OPENS),'dependency_scans':dict(DEPENDENCY_SCANS),
            'complete':ERROR is None and len(PARTIAL)==2,'error':ERROR,'partial_completed_episodes':len(PARTIAL),'production_imports':False}
        if not (H/'resource-v1.json').exists():write('resource-v1.json',record,exclusive=True)
    if ERROR is not None:sys.exit(1)
