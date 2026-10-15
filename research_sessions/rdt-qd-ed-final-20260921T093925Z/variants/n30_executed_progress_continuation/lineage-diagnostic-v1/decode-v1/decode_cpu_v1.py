#!/usr/bin/env python3
"""One released N30 CPU metadata/content-lineage decode. No production imports."""
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
BINDINGS=D/'input-bindings.disabled.v1.json'
PROTOCOL=D/'decode-protocol.disabled.v1.md'
REVIEW=D/'root-inventory-review-v1.json'
SCOPE=H/'root-decoder-preparation-scope-v1.md'
MANIFEST=H/'decoder-source-manifest-v1.json'
RELEASE=H/'root-execution-release-v1.json'
SOURCE_COMMIT='6292fc8cffad2eec0f789e023d835ad3c1df146a'
W=D.parents[2]/'study_worktree'
SOURCE_PATHS={str(W/x) for x in ('core/decision_evidence.py','core/eds_mechanism_trace.py','core/rdt_policy_steer.py','core/qd_executed_progress.py','scripts/qd_ed_n30_native.py','core/qd_ed.py')}
INPUT_SHA='192e4605fa42b834d99bb3083007283c08dbd84e990b94c7d5dd6207b1a9f1ce'
PROTOCOL_SHA='28dbfea28ca0a858ebbf29bb4bc4bc64a813a0cf892ed074ae037f911567eccb'
REVIEW_SHA='95c126bc4a95180306c974fb91d79592f0e0b8c2b258abc4e4f1cd37516b70f4'
SCOPE_SHA='1d175453bc3123277ece4b6cea6a21bc2b08dffdc792ca6e570b10236bd9aa7f'
OUTPUT_NAMES={'invocation-v1.json','progress-v1.jsonl','partial-v1.json','result-v1.json','resource-v1.json','summary-v1.md'}
LIMITS={'containers':34,'container_bytes':24273690,'loads_per_container':1,'cpu_seconds':120,'wall_seconds':120,'address_space_bytes':16*1024**3,'zip_uncompressed_bytes':128*1024**2,'cpu_storage_bytes':128*1024**2,'threads':2,'affinity':[0,1]}
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
    require(release.get('schema')=='n30-first-active-lineage-execution-release-v1' and release.get('executable') is True,'not released')
    require(release.get('limits')==LIMITS,'release limits differ')
    require(release.get('source_commit')==SOURCE_COMMIT,'source commit differs')
    def fixed_ref(key,p,h=None):
        x=release[key];require(set(x)=={'path','sha256'} and x['path']==str(p),'release ref path differs: '+key)
        if h:require(x['sha256']==h,'release ref hash differs: '+key)
        return x['sha256']
    read_meta(__file__,fixed_ref('reader',pathlib.Path(__file__).resolve()),as_json=False)
    bindings=read_meta(BINDINGS,fixed_ref('input_bindings',BINDINGS,INPUT_SHA))
    read_meta(PROTOCOL,fixed_ref('protocol',PROTOCOL,PROTOCOL_SHA),as_json=False)
    read_meta(REVIEW,fixed_ref('phase_a_review',REVIEW,REVIEW_SHA))
    read_meta(SCOPE,SCOPE_SHA,as_json=False)
    manifest=read_meta(MANIFEST,fixed_ref('source_manifest',MANIFEST))
    require(manifest['source_commit']==SOURCE_COMMIT,'manifest source')
    require(manifest['reader']==release['reader'],'manifest reader binding')
    require(len(manifest['scientific_source_files'])==6 and {x['path'] for x in manifest['scientific_source_files']}==SOURCE_PATHS,'exact scientific source list')
    require(manifest['input_bindings']==release['input_bindings'] and manifest['protocol']==release['protocol'],'manifest inputs')
    for x in manifest['scientific_source_files']:
        p=pathlib.Path(x['path']);require(p.is_absolute() and p.suffix=='.py','source type')
        READ_ALLOW.add(str(p));read_meta(p,x['sha256'],as_json=False)
    require(bindings['limits']=={'episodes':2,'decisions':2,'containers':34,'container_bytes':24273690,'loads_per_container':1},'bindings limits')
    require([e['cell']['task_id'] for e in bindings['episodes']]==[0,1],'all cells/order')
    require([e['cell']['attempt_id'].rsplit('__',1)[-1] for e in bindings['episodes']]==['4300bcf89485','1e52b07e1725'],'attempt IDs')
    for ep in bindings['episodes']:
        require(ep['global_step']==8 and ep['decision_id']=='e0:d2:s8','first active identity')
        for b in ep['containers']:
            p=pathlib.Path(b['path']);require(p.is_absolute() and p.name.startswith('bundle_') and p.suffix=='.pt','payload name')
            require(ep['cell']['attempt_id'] in p.parts and p.parent.name=='episode_000','episode path')
            require(str(p) not in PAYLOAD,'duplicate payload')
            require(b['existing_index_sha256']==b['existing_receipt_sha256'],'index/receipt SHA disagree')
            PAYLOAD[str(p)]=b
    require(len(PAYLOAD)==34 and sum(x['stat_bytes'] for x in PAYLOAD.values())==24273690,'payload set size')
    APPROVED=True
    return bindings

VALUE_KEYS={
 'decision_context':{'stage','use_guidance','keypoints','keypoint_tracking_snapshot'},
 'n30_observation_context':{'packet'},
 'n30_initial_proposal':{'progress_state','current_context','previous_native_plan','previous_native_identity','fresh_native_population','fresh_tail','inserted_row','action_mask','control'},
 'canonical_candidate_batch':{'iter_idx','candidates','canonical_fingerprints','occurrence_ids'},
 'canonical_candidate_identity':{'iter_idx','fingerprints'},
 'archive_parent_allocation':{'iter_idx','parent_fingerprints','parent_lanes','parent_cell_ids','original_archive_occurrences','identity_scope'},
 'parent_allocation':{'iter_idx','source_population','parent_indices','elite_count','parent_cell_ids','offspring_sources','source_pool_id','source_fingerprints','parent_fingerprints','parent_source_occurrence_ids','original_archive_occurrences','source_identity_scope'},
 'n30_selected_native_plan':{'selected','native_plan'},
 'final_selection':{'population','selected_latent','selected_index','selected_fingerprint','selected_canonical_fingerprint','selected_cell','selection_rule'},
 'n30_decode_binding':{'raw','actions'},
 'policy_action_decode':{'selected_latent','action_chunk','selected_canonical_fingerprint'},
 'n30_commit_binding':{'actions','execution_horizon','step','committed'},
 'decision_committed':{'action_chunk','execution_horizon'},
 'executed_action':{'action_numpy'},
 'pre_reset_outcome':{'observation','terminated'},
 'n30_actual_ack':{'global_step','execution_index','action','endpoint','terminated','truncated','completed'},
 'step_returned':{'terminated','truncated'},
}

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
    require(len(obj['events'])==len(b['events']),'container/index event count')
    selected=[]
    for event,ix in zip(obj['events'],b['events']):
        require(all(event.get(k)==v for k,v in ix.items()),'container/index event identity')
        require(event['episode']==0 and event['decision_id']==ep['decision_id'] and event['reset_sequence']==ep['reset_sequence'],'episode/decision/reset identity')
        if event['event'] not in VALUE_KEYS:continue
        v=event['values'];picked={k:v[k] for k in VALUE_KEYS[event['event']] if k in v}
        if event['event']=='pre_reset_outcome':
            picked['observation']={k:v['observation'][k] for k in ('robot0_eef_pos','robot0_eef_quat','robot0_gripper_qpos','robot0_gripper_qvel') if k in v['observation']}
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
def fingerprint(x):return hashlib.sha256(x.detach().float().contiguous().numpy().astype('<f4',copy=False).tobytes()).hexdigest()
def flag(x):
    if type(x) is bool:return x
    require(TORCH.is_tensor(x) and x.device.type=='cpu' and x.dtype==TORCH.bool and x.ndim==0,'strict boolean')
    return bool(x.item())
def state_for(matches):
    if not matches:return {'class':'missing_origin','possibilities':['unknown']}
    possibilities=sorted(set(y for m in matches for y in m['state']['possibilities']))
    if len(matches)>1:return {'class':'ambiguous_content_origin','possibilities':possibilities}
    s=matches[0]['state']
    if s['class'] in ('ambiguous_content_origin','missing_origin','ambiguous_ancestry'):
        return {'class':'ambiguous_ancestry','possibilities':possibilities}
    return {'class':'unique_content_supported_warm' if possibilities==['warm'] else 'unique_content_supported_nonwarm','possibilities':possibilities}

def analyze(ep,events):
    ongoing={'task_id':ep['cell']['task_id'],'attempt_id':ep['cell']['attempt_id'],'decision_id':ep['decision_id'],'phase':'identity','parent_rounds':[],'feedback':[]}
    def checkpoint():write('partial-v1.json',{'complete':False,'episodes':PARTIAL,'current':ongoing})
    checkpoint()
    kinds=collections.defaultdict(list)
    for e in sorted(events,key=lambda e:e['sequence']):kinds[e['event']].append(e)
    def one(k):require(len(kinds[k])==1,'expected one '+k);return kinds[k][0]
    def values(k):return one(k)['values']
    prop=values('n30_initial_proposal');cur=prop['current_context'];ident=cur['identity']
    require(prop['progress_state']['active'] is True and prop['control']=='none','first-active evidence differs')
    require(cur['step']==8 and prop['progress_state']['previous_start_step']==0,'current/previous step')
    dc=values('decision_context');packet=values('n30_observation_context')['packet']
    require(dc['use_guidance'] is True and dc['stage']==ident['stage'] and packet['episode']==ident['episode']==0,'guided stage/episode identity')
    require(same(packet['keypoints'],dc['keypoints']) and equal_tree(packet['tracker'],dc.get('keypoint_tracking_snapshot')),'packet/context keypoints/tracker binding')
    tr=packet['tracker'];ti=ident['target_index']
    require(type(ti) is int and ti>=0 and tr['instance_id']==ident['tracker_instance'] and tr['generation']==ident['tracker_generation'],'tracker target identity')
    target_state=tr['targets'][str(ti)]
    require(target_state['valid'] is True and target_state['status']==ident['target_status'] and ident['target_status'] in {'tracked','static_background'},'target tracking validity')
    require(type(ident['reset_generation']) is int and ident['reset_generation']>=0,'helper reset generation metadata')
    fresh=tensor(prop['fresh_native_population'],(16,64,128));previous=tensor(prop['previous_native_plan'],(1,64,128))
    inserted=tensor(prop['inserted_row'],(64,128));mask=tensor(prop['action_mask'],(1,1,128))
    require(fresh.dtype==previous.dtype==inserted.dtype==mask.dtype,'native copy dtype')
    require(prop['previous_native_identity']==native_id(previous),'previous native identity')
    expected_mask=TORCH.zeros_like(mask);expected_mask[:,:,[10,39,40,41,42,43,44]]=1
    require(same(mask,expected_mask),'frozen mask differs')
    expected=fresh.clone();expected[15]=TORCH.cat((previous[0,8:64],fresh[15,56:64]),dim=0);expected=expected*mask.expand_as(expected)
    require(same(prop['fresh_tail'],fresh[15,56:64]) and same(inserted,expected[15]),'56+fresh8 insertion content')
    ongoing['insertion_content_verified']=True;checkpoint()
    canonical={e['values']['iter_idx']:e for e in kinds['canonical_candidate_batch']}
    identities={e['values']['iter_idx']:e for e in kinds['canonical_candidate_identity']}
    parents={e['values']['iter_idx']:e for e in kinds['parent_allocation']}
    archives={e['values']['iter_idx']:e for e in kinds['archive_parent_allocation']}
    require(len(canonical)==len(kinds['canonical_candidate_batch'])==11 and set(canonical)==set(range(-1,10)),'canonical count/order')
    require(set(identities)==set(canonical) and len(kinds['canonical_candidate_identity'])==11,'canonical identity coverage')
    require(set(parents)==set(archives)==set(range(10)) and len(kinds['parent_allocation'])==len(kinds['archive_parent_allocation'])==10,'parent coverage')
    require(same(canonical[-1]['values']['candidates'],expected),'canonical initial content/other15 differs')
    known=[];byfp=collections.defaultdict(list);rounds=[]
    def matching(row):return [x for x in byfp[fingerprint(row)] if same(row,x['row'])]
    def add(iteration,states):
        e=canonical[iteration];v=e['values'];rows=tensor(v['candidates'],(16,64,128));require(rows.dtype==fresh.dtype,'canonical dtype')
        fps=[fingerprint(row) for row in rows]
        require(fps==v['canonical_fingerprints']==identities[iteration]['values']['fingerprints'],'canonical fingerprint bytes')
        ids=[f"{ep['decision_id']}:q{e['sequence']}:r{i}" for i in range(16)]
        require(v['occurrence_ids']==ids,'canonical occurrence IDs')
        for i,row in enumerate(rows):
            item={'occurrence':ids[i],'iteration':iteration,'row_index':i,'row':row,'state':states[i]};known.append(item);byfp[fps[i]].append(item)
    add(-1,[{'class':'initial_occurrence','possibilities':['warm' if i==15 else 'nonwarm']} for i in range(16)])
    for i in range(10):
        pe=parents[i];pa=pe['values'];ae=archives[i];av=ae['values'];ce=canonical[i]
        require(canonical[i-1]['sequence']<ae['sequence']<pe['sequence']<ce['sequence'],'parent/offspring schedule order')
        pool=tensor(pa['source_population'],(16,64,128));require(pool.dtype==fresh.dtype,'parent dtype')
        idx=tensor(pa['parent_indices'],(16,));require(idx.dtype==TORCH.int64 and idx.tolist()==list(range(16)) and pa['elite_count']==0,'frozen N30 identity parent schedule')
        require(pa['original_archive_occurrences'] is None and av['original_archive_occurrences'] is None,'unexpected archive provenance schema')
        fps=[fingerprint(row) for row in pool]
        require(fps==pa['source_fingerprints']==pa['parent_fingerprints']==av['parent_fingerprints'],'actual allocated parent identities')
        require(same(pa['parent_cell_ids'],av['parent_cell_ids']),'paired allocation cell binding')
        lane_sources={'quality_anchor':'qd_global_quality_anchor_offspring','quality':'qd_archive_offspring','secondary':'qd_secondary_lane_offspring'}
        lanes=av['parent_lanes'];require(len(lanes)==16 and all(lane in lane_sources for lane in lanes),'parent lanes')
        require(len(pa['offspring_sources'])==16 and list(pa['offspring_sources'])==[lane_sources[lane] for lane in lanes],'offspring source lane order')
        require(pa['source_pool_id']==f"{ep['decision_id']}:q{pe['sequence']}" and pa['parent_source_occurrence_ids']==[pa['source_pool_id']+f':r{k}' for k in range(16)],'parent pool occurrence binding')
        matches=[matching(row) for row in pool];states=[state_for(ms) for ms in matches]
        direct=sum(same(row,inserted) for row in pool)
        add(i,states)
        rounds.append({'iteration':i,'parent_sequence':pe['sequence'],'offspring_canonical_sequence':ce['sequence'],'parent_slots':16,'direct_inserted_content_slots':direct,'content_match_class_counts':dict(collections.Counter(s['class'] for s in states)),
            'warm_possible_slots':sum('warm' in s['possibilities'] for s in states),'offspring_direct_inserted_content_rows':sum(same(row,inserted) for row in ce['values']['candidates']),
            'source_occurrence_matches':[{'slot':j,'matching_occurrences':[m['occurrence'] for m in ms],'ancestry':states[j]} for j,ms in enumerate(matches)],
            'ancestry_basis':'recorded actual parent slots + unchanged row schedule; archive insertion occurrence missing; not total causal ancestry'})
        ongoing['phase']='parent_rounds';ongoing['parent_rounds']=rounds;checkpoint()
    final=values('final_selection');selected=tensor(final['selected_latent'],(1,64,128));population=tensor(final['population'])
    require(population.ndim==3 and tuple(population.shape[1:])==(64,128) and 1<=population.shape[0]<=176,'final archive shape')
    ix=final['selected_index'];require(type(ix) is int and 0<=ix<population.shape[0],'selected index')
    require(same(population[ix:ix+1],selected),'final selected/archive content')
    fp=fingerprint(selected[0]);require(final['selected_fingerprint']==final['selected_canonical_fingerprint']==fp,'final fingerprint')
    sn=values('n30_selected_native_plan');require(same(sn['native_plan'],selected),'selected native duplicate binding')
    sm=sn['selected'];require(sm['native_identity']==native_id(selected) and sm['identity']==ident and sm['start_step']==8,'selected provenance')
    decode=values('policy_action_decode');require(same(decode['selected_latent'],selected.float()),'native/FP32 decoder boundary')
    actions=selected.float()[:,:8,[39,40,41,42,43,44,10]].clone();actions[:,:,-1]=TORCH.where(actions[:,:,-1]<0,-1.,1.)
    for key,field in [('policy_action_decode','action_chunk'),('n30_decode_binding','actions'),('n30_commit_binding','actions'),('decision_committed','action_chunk')]:require(same(values(key)[field],actions),'decoded/committed actions '+key)
    require(values('decision_committed')['execution_horizon']==values('n30_commit_binding')['execution_horizon']==8 and values('n30_commit_binding')['committed'] is True and values('n30_commit_binding')['step']==8,'full8 commit')
    order=[one(k)['sequence'] for k in ('n30_selected_native_plan','final_selection','policy_action_decode','n30_decode_binding','n30_commit_binding','decision_committed')]
    # decode-binding hook precedes/ follows decode recorder as defined by frozen source; only necessary causal boundaries below.
    require(order[0]<order[1]<order[-1] and one('policy_action_decode')['sequence']<one('decision_committed')['sequence'],'selection/commit order')
    start=tensor(cur['start'],(3,));target=tensor(cur['target'],(3,));packet=values('n30_observation_context')['packet']
    require(same(start,packet['start_eef'].reshape(3).double()) and same(sm['start_eef'],start) and same(sm['target_snapshot'],target),'raw start/target snapshot')
    ti=ident['target_index'];require(type(ti) is int and ti>=0,'target index')
    require(same(target,packet['keypoints'][ti].double()),'fixed target raw snapshot')
    feedback=[];prev=start.double();initial_distance=float(TORCH.linalg.vector_norm(prev-target.double()))
    terminal=False
    for j,step in enumerate(range(8,16)):
        def at(k):
            z=[e for e in kinds[k] if e['global_step']==step];require(len(z)==1,'one feedback '+k);return z[0]
        act,out,ack,ret=[at(k) for k in ('executed_action','pre_reset_outcome','n30_actual_ack','step_returned')]
        require(not terminal and act['sequence']<out['sequence']<ack['sequence']<ret['sequence'],'feedback order/reset')
        av=ack['values'];ov=out['values']['observation'];require(av['global_step']==step and av['execution_index']==j+1,'ack indices')
        require(same(act['values']['action_numpy'],actions[0,j]) and same(av['action'],actions[0,j]),'actual command binding')
        endpoint=tensor(ov['robot0_eef_pos']).reshape(3);require(same(av['endpoint'],endpoint),'actual endpoint binding')
        term=flag(ret['values']['terminated']);trunc=flag(ret['values']['truncated'])
        require(flag(out['values']['terminated'])==flag(av['terminated'])==term and flag(av['truncated'])==trunc,'feedback terminal flags')
        terminal=term or trunc;distance=float(TORCH.linalg.vector_norm(endpoint.double()-target.double()))
        qpos=ov.get('robot0_gripper_qpos');qvel=ov.get('robot0_gripper_qvel')
        def summary(v):
            if v is None:return None
            t=tensor(v);require(0<t.numel()<=16,'gripper vector bound');t=t.double();return {'shape':list(v.shape),'dtype':str(v.dtype),'min':float(t.min()),'max':float(t.max()),'mean':float(t.mean()),'l2':float(TORCH.linalg.vector_norm(t.reshape(-1)))}
        feedback.append({'step':step,'command_gripper':float(actions[0,j,-1]),'eef_movement_from_previous_observation_m':float(TORCH.linalg.vector_norm(endpoint.double()-prev)),
            'eef_distance_to_fixed_step8_target_m':distance,'approach_from_step8_start_m':initial_distance-distance,'gripper_qpos':summary(qpos),'gripper_qvel':summary(qvel),
            'eef_dtype':str(endpoint.dtype),'eef_quaternion_present':ov.get('robot0_eef_quat') is not None,'terminal_or_truncated':terminal,'contact_grasp_success':'UNKNOWN_NOT_INFERRED'})
        if j<7:require(av['completed'] is None,'premature completion')
        if not terminal and j==7:require(av['completed'] is not None,'missing complete8 acknowledgment')
        if av['completed'] is not None:require(not terminal and j==7 and av['completed']['selected_native_identity']==native_id(selected) and av['completed']['ack_count']==8,'completed native identity')
        prev=endpoint.double()
        ongoing['phase']='actual_feedback';ongoing['feedback']=feedback;checkpoint()
    smatches=matching(selected[0]);archive_matches=[matching(row) for row in population]
    return {'task_id':ep['cell']['task_id'],'attempt_id':ep['cell']['attempt_id'],'decision_id':ep['decision_id'],'global_step':8,'native_dtype':str(fresh.dtype),
        'insertion_content_verified':True,'canonical_initial_row15_verified':True,'other15_and_fresh_tail_verified':True,'canonical_rows':176,'parent_rounds':rounds,
        'final':{'selection_rule':final.get('selection_rule'),'selected_index':ix,'selected_cell':final.get('selected_cell'),'archive_population_rows':population.shape[0],
            'archive_direct_inserted_content_rows':sum(same(row,inserted) for row in population),'archive_unmatched_rows':sum(not ms for ms in archive_matches),
            'selected_direct_inserted_content':same(selected[0],inserted),'selected_content_matching_occurrences':[m['occurrence'] for m in smatches],'selected_ancestry':state_for(smatches),
            'selected_native_sha256':native_id(selected),'committed8_bound_to_selected':True},
        'fixed_snapshot_identity':{k:ident.get(k) for k in ('episode','stage','target_index','tracker_instance','tracker_generation','target_status','reset_generation')},
        'feedback':feedback,'start_distance_to_fixed_step8_target_m':initial_distance,'limitations':['First active only, not all18 insertions.','Archive original insertion occurrences missing: genealogy is content-supported inference or ambiguous, not recorded insertion provenance.','Single-parent schedule is not total causal ancestry: QD/ED population coupling remains unexcluded.','Prior step0 progress eligibility and native source validity inherited from bound worker audit; not replayed.','Fixed step8 snapshot is not live target ground truth; gripper/state is not grasp or success.']}

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
    require(len(OPEN_COUNTS)==34 and all(v==1 for v in OPEN_COUNTS.values()),'one filesystem read each')
    require(sum(x['bytes'] for x in READS if x['kind']=='payload')==24273690,'total payload bytes')
    require(not torch.cuda.is_initialized(),'CUDA initialized during CPU analysis')
    write('result-v1.json',{'schema':'n30-first-active-lineage-cpu-result-v1','complete':True,'source_commit':SOURCE_COMMIT,'input_sha256':INPUT_SHA,'episodes':PARTIAL,'algorithm_nomination':None,'scientific_result_authority':False})

if __name__=='__main__':
    try:main()
    except BaseException as e:
        ERROR={'type':type(e).__name__,'message':str(e)}
        traceback.print_exc()
    finally:
        signal.alarm(0)
        # Resource finalization never retries inputs. SIGKILL can leave progress log without final resource.
        record={'schema':'n30-lineage-decode-resource-v1','pid':os.getpid(),'cpu_seconds':time.process_time()-START_CPU,'wall_seconds':time.monotonic()-START_WALL,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rlimit_as_bytes':resource.getrlimit(resource.RLIMIT_AS)[0],'rlimit_cpu':list(resource.getrlimit(resource.RLIMIT_CPU)),
            'affinity':sorted(os.sched_getaffinity(0)),'threads':2,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'cuda_initialized':TORCH.cuda.is_initialized() if TORCH is not None else None,
            'explicit_cuda_tensor_work':0,'cuda_driver_probe_absence_claimed':False,'torch_imported':TORCH is not None,'reads':READS,'payload_open_counts':dict(OPEN_COUNTS),
            'zip_uncompressed_bytes':ZIP_BYTES,'decoded_cpu_storage_bytes':STORAGE_BYTES,'denied_probes':DENIED,'guard_clean':not DENIED,'dependency_opens':dict(DEPENDENCY_OPENS),'dependency_scans':dict(DEPENDENCY_SCANS),
            'complete':ERROR is None and len(PARTIAL)==2,'error':ERROR,'partial_completed_episodes':len(PARTIAL),'production_imports':False}
        if not (H/'resource-v1.json').exists():write('resource-v1.json',record,exclusive=True)
    if ERROR is not None:sys.exit(1)
