#!/usr/bin/env python3
"""One frozen CPU reference pass; no algorithm/runtime imports or ranking."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '2'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import sys
sys.dont_write_bytecode = True
import json, hashlib, io, csv, time, signal, traceback
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
SCOPE_SHA = '9845a9915caaffff30d33b0ab5e41b4a618fce2f01ef95bc671ddf5c379cef28'
PYROOT = Path('/home/hynx/miniconda3/envs/vla-pilot').resolve()
START = time.monotonic()
BLOCKED = []
READS = Counter()
LOADS = []
NATIVE_BYTES = 0
ALLOWED = {HERE / 'read-scope-v1.json', HERE / 'input-manifest-v2.json', Path(__file__).resolve()}
OUTPUTS = {HERE / n for n in ('result-v1.json', 'partial-v1.json', 'error-v1.json', 'all-decisions-v1.csv', 'all-candidates-v1.csv', 'guard-result-v1.json')}

def deny(event, obj):
    BLOCKED.append({'event': event, 'value': str(obj)})
    raise PermissionError('scope guard: ' + event + ':' + str(obj))

def audit(event, args):
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, int): return
        p = Path(os.fsdecode(path)).absolute()
        resolved = p.resolve()
        writing = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or (isinstance(flags, int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
        if writing:
            if p not in OUTPUTS or resolved != p: deny('write', p)
            return
        if p in ALLOWED and resolved == p:
            READS[str(p)] += 1
            if p.suffix == '.pt' and READS[str(p)] != 1: deny('native_reread', p)
            return
        # Trusted interpreter/stdlib/Torch imports only; never any study payload.
        if (resolved.is_relative_to(PYROOT) or resolved.is_relative_to(Path('/usr/lib'))
                or resolved.is_relative_to(Path('/lib'))) and resolved.suffix in ('.py', '.pyc', '.so', '.pth', '.txt'):
            return
        if resolved in (Path('/dev/null'), Path('/proc/meminfo'), Path('/proc/cpuinfo')): return
        deny('read', p)
    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.fork')) or event in ('os.system', 'pty.spawn'):
        deny(event, args[:1])
    if event in ('os.remove', 'os.rename', 'os.rmdir', 'os.mkdir', 'os.symlink', 'os.link', 'os.truncate', 'os.chmod'):
        deny(event, args[:2])
    if event == 'import':
        mod = args[0]
        if mod.split('.')[0] in ('core', 'main', 'scripts', 'libero', 'robosuite', 'mujoco', 'transformers', 'openai', 'requests', 'httpx'):
            deny('runtime_import', mod)
    if event == 'ctypes.dlopen' and any(s in str(args[0]).lower() for s in ('libcuda.so', 'libnvidia')):
        deny('cuda_dlopen', args[0])

sys.addaudithook(audit)

def need(ok, message):
    if not ok: raise ValueError(message)

def read(ref):
    p = Path(ref['path'])
    data = p.read_bytes()
    need(hashlib.sha256(data).hexdigest() == ref['sha256'], 'input sha mismatch:' + str(p))
    return data

def write(name, obj):
    (HERE / name).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')

def ref(p):
    p = Path(p)
    return {'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def expire(*_): raise TimeoutError('frozen 120 second extraction limit')

DECISIONS=[]
CANDIDATES=[]
ERROR=None
TORCH=None
try:
    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, 120)
    scope = json.loads(read({'path':str(HERE/'read-scope-v1.json'),'sha256':SCOPE_SHA}))
    manifest = json.loads((HERE/'input-manifest-v2.json').read_bytes())
    need(manifest['scope']['sha256'] == SCOPE_SHA, 'manifest scope')
    need(ref(__file__) == manifest['extractor'], 'extractor frozen bytes')
    for item in manifest['inputs'] + manifest['source_files'] + manifest['bundles']:
        p = Path(item['path']); need(p.is_absolute(), 'relative input'); ALLOWED.add(p)
    need(manifest['bundles'] == [{k:b[k] for k in ('path','sha256','decision_id','global_step')} for b in scope['bundles']], 'bundle manifest')
    for item in manifest['source_files']: read(item)
    # Closed JSON is a frozen identity/command witness, not newly inspected outcomes.
    command=json.loads(read(scope['inputs']['closed_command_result']))
    membership=json.loads(read(scope['inputs']['closed_membership_result']))
    read(scope['inputs']['closed_membership_review'])
    cm={r['decision_id']:r for r in command['decisions']}
    mm={r['decision_id']:r for r in membership['decisions']}
    cb={r['decision_id']:r for r in command['canonical_batches'] if r['iter_idx']==9}
    need(len(cm)==len(mm)==len(cb)==len(scope['bundles'])==14,'fourteen frozen pools')
    import torch
    TORCH=torch
    torch.set_num_threads(2); torch.set_num_interop_threads(2)
    need(not torch.cuda.is_initialized(), 'CUDA initialized')
    def no_cuda(*args, **kwargs): deny('cuda_call', 'blocked')
    torch.cuda._lazy_init=no_cuda
    torch.Tensor.cuda=no_cuda
    torch.cuda.init=no_cuda
    need(torch.get_default_dtype()==torch.float32,'default dtype')

    def tensor(t, shape=None, dtype=None):
        need(isinstance(t,torch.Tensor) and t.device.type=='cpu','CPU tensor required')
        need(shape is None or tuple(t.shape)==tuple(shape), 'shape mismatch '+str(t.shape))
        need(dtype is None or t.dtype==dtype,'dtype mismatch')
        need(bool(torch.isfinite(t).all()),'nonfinite allowed tensor')
        return t
    def bytesame(a,b):
        return a.dtype==b.dtype and a.shape==b.shape and torch.equal(a.contiguous().view(torch.uint8),b.contiguous().view(torch.uint8))
    def ids(x): return torch.nonzero(x,as_tuple=False).reshape(-1).tolist()
    def elig(dist, positive):
        return (positive & (dist <= .06) & (dist <= dist.min()+.03)).any(dim=1)
    def summary_guard():
        return {'blocked':BLOCKED,'cuda_initialized':torch.cuda.is_initialized(),'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'cpu_threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads(),'native_read_counts':{k:v for k,v in READS.items() if k.endswith('.pt')},'runtime_imports':0,'network_calls':0,'child_processes':0}

    for bundle_ref in scope['bundles']:
        decision=bundle_ref['decision_id']; witness=cm[decision]; member=mm[decision]; canonical=cb[decision]
        need(witness['bundle']=={k:bundle_ref[k] for k in ('path','sha256')}, 'closed bundle binding')
        raw_bytes=read(bundle_ref); NATIVE_BYTES+=len(raw_bytes)
        payload=torch.load(io.BytesIO(raw_bytes),map_location='cpu',weights_only=True)
        LOADS.append(bundle_ref['path']); del raw_bytes
        need(payload['schema']=='qd-ed-decision-evidence-v1','payload schema')
        events=payload['events']
        header_keys=('sequence','event','decision_id','global_step','reset_sequence')
        need([{k:e[k] for k in header_keys} for e in events]==bundle_ref['events'],'event header binding')
        ev={e['sequence']:e for e in events}
        need(len(ev)==len(events),'duplicate sequence')
        ce=ev[canonical['canonical_sequence']]; se=ev[canonical['scoring_batch_id']]
        need(ce['event']=='canonical_candidate_batch' and ce['values']['iter_idx']==9,'canonical terminal')
        need(se['event']=='scoring_inputs' and se['values']['scoring_scope']['iter_idx']==9 and se['values']['scoring_scope']['role']=='canonical_offspring','scoring identity')
        fs=[e for e in events if e['event']=='final_selection']; need(len(fs)==1,'final selection unique'); fe=fs[0]
        for e in (ce,se,fe):
            need(e['decision_id']==decision and e['global_step']==bundle_ref['global_step'] and e['reset_sequence']==witness['reset_sequence'],'context association')
        need(se['sequence']<ce['sequence']<fe['sequence'],'same-call ordering')
        cv=ce['values']; sv=se['values']; fv=fe['values']; terminal=fv['terminal_population']; grasp=terminal['grasp_selection']
        need(terminal['iter_idx']==9 and terminal['population_size']==16 and terminal['canonical_event_sequence']==ce['sequence'] and terminal['scoring_batch_id']==se['sequence'],'terminal identity')
        for field in ('selected_index','selected_fingerprint','selected_occurrence_id'):
            need(terminal[field]==member[field]==witness[field], 'selected metadata '+field)
        selected=terminal['selected_index']; need(type(selected)==int and 0<=selected<16,'selected index')
        need(fv['selected_index']==selected and fv['selected_fingerprint']==terminal['selected_fingerprint'],'final selected metadata')
        need(terminal['selected_occurrence_id']==canonical['row_occurrence_ids'][selected] and terminal['selected_fingerprint']==canonical['row_fingerprints'][selected],'canonical selected occurrence')
        need(grasp['target_index']==member['target_index']==0 and grasp['recognition_reason']==member['recognition_reason'],'target recognition metadata')
        need(grasp['absolute_reach_m']==.06 and grasp['relative_reach_m']==.03,'frozen thresholds')
        # Touch no other canonical dimensions, provider return or cost/quality field.
        population=cv['candidates']; need(tuple(population.shape)==(16,64,128),'native population shape')
        translation=tensor(population[:,:8,39:42],(16,8,3)); grip=tensor(population[:,:8,10],(16,8),translation.dtype)
        need(translation.dtype in (torch.float32,torch.bfloat16),'native dtype')
        xyz=tensor(sv['projected_xyz'],(16,9,3),translation.dtype)
        keypoints=sv['keypoints']; need(keypoints.ndim==2 and keypoints.shape[1]==3 and len(keypoints)>0,'target shape')
        target=tensor(keypoints[0],(3,),translation.dtype)
        positives=tensor(grasp['positive_commands'],(16,8),torch.bool)
        need(torch.equal(grip>=0,positives),'native recorded deployed signs')
        need(positives.tolist()==[[v>0 for v in row] for row in canonical['gripper_prefix']],'closed canonical signs')
        dist=tensor(grasp['projected_distances_m'],(16,8),torch.float32)
        original=grasp['eligible_indices']
        need(original==member['eligible_indices']==ids(elig(dist,positives)),'recorded authoritative membership')
        need(type(grasp['best_reach_m'])==float and grasp['best_reach_m']==float(dist.min()),'recorded best reach')
        origins=sv['projection_origin_sequences']; need(type(origins)==list and len(origins)==16,'16 origins')
        clipped=[]; reconstructed=[]; origin_dtypes=[]
        for index,seq in enumerate(origins):
            oe=ev[seq]
            need(oe['event']=='projection_origin' and oe['decision_id']==decision and oe['reset_sequence']==witness['reset_sequence'] and oe['global_step']==bundle_ref['global_step'] and seq<se['sequence'],'direct origin association')
            source=tensor(oe['values']['source_eef_position'],(3,)); origin_dtypes.append(str(source.dtype))
            origin=source.to(dtype=translation.dtype)
            need(bytesame(origin,xyz[index,0]),'origin bytes differ')
            reconstructed.append(origin+torch.cumsum(translation[index]*.01,dim=0))
            clipped.append(origin+torch.cumsum(translation[index].clamp(-1.,1.)*.01,dim=0))
        raw_cpu=torch.stack(reconstructed); clip_cpu=torch.stack(clipped)
        raw_dist=torch.linalg.vector_norm(xyz[:,1:9].float()-target.float(),dim=-1)
        clip_dist=torch.linalg.vector_norm(clip_cpu.float()-target.float(),dim=-1)
        raw_ids=ids(elig(raw_dist,positives)); clip_ids=ids(elig(clip_dist,positives))
        full_ids=ids(positives.all(dim=1)); need(full_ids==member['terminal_full8_indices'],'full8 identity')
        mask7=((translation[:,:7]<-1)|(translation[:,:7]>1)).any(dim=(1,2)); mask8=((translation<-1)|(translation>1)).any(dim=(1,2))
        mismatch=~(raw_cpu==xyz[:,1:9]); numerical_equal=bytesame(raw_cpu,xyz[:,1:9]); origin_refs=list(origins)
        gains=sorted(set(clip_ids)-set(original)); losses=sorted(set(original)-set(clip_ids))
        row={'decision_id':decision,'global_step':bundle_ref['global_step'],'bundle':{k:bundle_ref[k] for k in ('path','sha256')},'canonical_sequence':ce['sequence'],'scoring_sequence':se['sequence'],'final_sequence':fe['sequence'],'projection_origin_sequences':origin_refs,'origin_dtypes':origin_dtypes,'reset_sequence':witness['reset_sequence'],'native_dtype':str(translation.dtype),'target_index':0,'recognition_reason':grasp['recognition_reason'],'category':member['classification'],'selected_index':selected,'selected_fingerprint':terminal['selected_fingerprint'],'selected_occurrence_id':terminal['selected_occurrence_id'],'full8_indices':full_ids,'recorded_eligible_indices':original,'raw_projection_cpu_norm_eligible_indices':raw_ids,'cpu_clipped_reference_eligible_indices':clip_ids,'gained_indices':gains,'lost_indices':losses,'gained_full8_indices':sorted(set(gains)&set(full_ids)),'lost_full8_indices':sorted(set(losses)&set(full_ids)),'recorded_eligible_full8_indices':sorted(set(original)&set(full_ids)),'cpu_clipped_eligible_full8_indices':sorted(set(clip_ids)&set(full_ids)),'selected_recorded_eligible':selected in original,'selected_cpu_reference_eligible':selected in clip_ids,'clipped_first7_indices':ids(mask7),'clipped_full8_indices':ids(mask8),'raw_reconstruction_byte_equal':numerical_equal,'raw_reconstruction_different_components':int(mismatch.sum()),'raw_reconstruction_max_abs_error_m':float((raw_cpu.float()-xyz[:,1:9].float()).abs().max()),'raw_norm_max_abs_error_m':float((raw_dist-dist).abs().max()),'raw_norm_byte_equal':bytesame(raw_dist,dist),'raw_norm_membership_equal':raw_ids==original,'recorded_best_reach_m':grasp['best_reach_m'],'cpu_clipped_reference_best_reach_m':float(clip_dist.min()),'hypothetical_cuda_clipped_membership':'Unknown','reference_scope':'CPU native-dtype formula, no CUDA replay; original recorded eligibility authoritative'}
        DECISIONS.append(row)
        for i in range(16):
            CANDIDATES.append({'decision_id':decision,'global_step':row['global_step'],'candidate_index':i,'occurrence_id':canonical['row_occurrence_ids'][i],'recorded_fingerprint':canonical['row_fingerprints'][i],'positive_commands':int(positives[i].sum()),'full8':i in full_ids,'original_selected':i==selected,'recorded_eligible':i in original,'raw_projection_cpu_norm_eligible':i in raw_ids,'cpu_clipped_reference_eligible':i in clip_ids,'gained':i in gains,'lost':i in losses,'first7_clipping':bool(mask7[i]),'full8_clipping':bool(mask8[i]),'raw_reconstruction_byte_equal':bytesame(raw_cpu[i],xyz[i,1:9]),'raw_reconstruction_max_abs_error_m':float((raw_cpu[i].float()-xyz[i,1:9].float()).abs().max()),'recorded_distances_m':dist[i].tolist(),'cpu_clipped_reference_distances_m':clip_dist[i].tolist(),'hypothetical_cuda_clipped_membership':'Unknown'})
        write('partial-v1.json', {'completed_pools':len(DECISIONS),'decisions':DECISIONS,'candidates':CANDIDATES,'native_bytes_read':NATIVE_BYTES,'native_loads':LOADS})
        print(json.dumps({'completed':len(DECISIONS),'step':row['global_step'],'raw_cpu_norm_agrees':row['raw_norm_membership_equal'],'gain':gains,'loss':losses,'cuda':'Unknown'}),flush=True)
        del payload,events,ev,population,cv,sv,fv,terminal,grasp
    need(len(DECISIONS)==14 and len(CANDIDATES)==224 and NATIVE_BYTES==243123318 and len(LOADS)==14,'coverage mismatch')
    need(not BLOCKED and not torch.cuda.is_initialized(),'runtime boundary')
    result={'schema':'n24-clipped-eligibility-cpu-reference-v1','status':'COMPLETED_CPU_REFERENCE_ONLY','scope':manifest['scope'],'input_manifest':ref(HERE/'input-manifest-v2.json'),'extractor':manifest['extractor'],'source_commit':scope['source_commit'],'decisions':DECISIONS,'candidates':CANDIDATES,'summary':{'pools':14,'rows':224,'changed_pools':sum(bool(r['gained_indices'] or r['lost_indices']) for r in DECISIONS),'gained_rows':sum(len(r['gained_indices']) for r in DECISIONS),'lost_rows':sum(len(r['lost_indices']) for r in DECISIONS),'gained_full8_rows':sum(len(r['gained_full8_indices']) for r in DECISIONS),'lost_full8_rows':sum(len(r['lost_full8_indices']) for r in DECISIONS),'raw_norm_membership_agreed_pools':sum(r['raw_norm_membership_equal'] for r in DECISIONS),'raw_reconstruction_byte_equal_pools':sum(r['raw_reconstruction_byte_equal'] for r in DECISIONS),'raw_norm_max_abs_error_m':max(r['raw_norm_max_abs_error_m'] for r in DECISIONS),'raw_reconstruction_max_abs_error_m':max(r['raw_reconstruction_max_abs_error_m'] for r in DECISIONS),'categories':dict(Counter(r['category'] for r in DECISIONS))},'native_bytes_read':NATIVE_BYTES,'native_loads':LOADS,'elapsed_seconds':time.monotonic()-START,'guard':summary_guard(),'limitations':['All hypothetical CUDA memberships Unknown.','CPU reference, not production arithmetic/trajectory/efficacy proof.','Eight-point clipping is prospective hypothesis; production N23 quality uses seven points.','Original recorded eligibility remains authoritative.','No costs/quality/provider values, ranking, new selection or physical outcome inference.','Full candidate fingerprints are recorded identity only; no disallowed native dimensions rehashed.']}
    write('result-v1.json',result)
    for name,rows in [('all-decisions-v1.csv',DECISIONS),('all-candidates-v1.csv',CANDIDATES)]:
        with (HERE/name).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader()
            for row in rows:writer.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    print(json.dumps({'status':result['status'],'summary':result['summary'],'seconds':result['elapsed_seconds'],'guard':result['guard']},sort_keys=True),flush=True)
except BaseException as exc:
    ERROR={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'completed_pools':len(DECISIONS),'native_bytes_read':NATIVE_BYTES,'native_loads':LOADS,'elapsed_seconds':time.monotonic()-START,'rerun_authorized':False}
    write('error-v1.json',ERROR)
    print(json.dumps(ERROR),flush=True)
finally:
    signal.setitimer(signal.ITIMER_REAL,0)
    write('guard-result-v1.json',{'blocked':BLOCKED,'native_read_counts':{k:v for k,v in READS.items() if k.endswith('.pt')},'cuda_initialized':None if TORCH is None else TORCH.cuda.is_initialized(),'cpu_threads':None if TORCH is None else TORCH.get_num_threads(),'error':ERROR is not None})
if ERROR is not None: sys.exit(1)
