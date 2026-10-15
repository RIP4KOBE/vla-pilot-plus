"""Closed, descriptive CPU witness extraction. No production imports/replay."""
import argparse
from collections import Counter
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import re
import sys
import time
import zipfile

COMMIT='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
COHORT='N26_CLEAN_OUTPUT_RBF_DEV_20260930'
TERMINAL_READER_SHA='29fb5e36e2ef0dac6a2522ec68d8e9a2dc69eb622049efa927418ef0c74f6051'
CONTROLS={'terminal_review','result','plan','source','terminal_input'}
FIELDS={'input_xyz','source_origins','cast_origins','projected_xyz','gradient_before','gradient_after',
        'update_operand','model_output_before','model_output_after'}
SLOTS=[['initial',-1]]+[['rollout',i] for i in range(10)]
MiB=1024**2
CAPS={'metadata_files':66,'metadata_file':16*MiB,'index_file':20*MiB,'metadata_total':128*MiB,
      'bundles':40,'bundles_per_attempt':2,'bundle_file':64*MiB,'bundle_total':1024*MiB,
      'zip_entries':8192,'pickle_bytes':8*MiB,'uncompressed_file':128*MiB,'uncompressed_total':2048*MiB,
      'storage_file':128*MiB,'storage_total':2048*MiB,'nodes':500000,'depth':64,'events':20000,'output':16*MiB}
T=None


class ExtractionError(ValueError):pass


def need(ok,message):
    if not ok:raise ExtractionError(message)


def digest(b):return sha256(b).hexdigest()
def canonical(v):return digest(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def integer(v):return type(v) is int and v>=0
def reference(path,blob):return {'path':str(path),'sha256':digest(blob)}


def pairs_unique(pairs):
    result={}
    for k,v in pairs:
        need(k not in result,'duplicate JSON key');result[k]=v
    return result


def decode(blob):
    return json.loads(blob,object_pairs_hook=pairs_unique,
                      parse_constant=lambda value:(_ for _ in ()).throw(ExtractionError('nonfinite JSON')))


def same_ref(a,b):
    return (type(a) is dict and type(b) is dict and set(a)==set(b)=={'path','sha256'}
            and a['sha256']==b['sha256'] and Path(a['path']).resolve()==Path(b['path']).resolve())


def torch_cpu():
    global T
    if T is None:
        import os,resource
        need(resource.getrlimit(resource.RLIMIT_AS)[0] in range(1,8*1024**3+1),'8 GiB address-space ceiling required before Torch')
        need(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CUDA must be hidden')
        import torch
        need(not torch.cuda.is_initialized(),'CUDA was initialized')
        torch.set_num_threads(2);torch.set_num_interop_threads(2);torch.set_grad_enabled(False);T=torch
    return T


class Reader:
    def __init__(self,records,loader=None,input_manifest_bytes=0):
        need(type(records) is list and len(records)<=106,'input file count')
        need(integer(input_manifest_bytes) and input_manifest_bytes<=CAPS['metadata_file'],'input manifest bytes')
        self.rows={};self.cache={};self.loader=loader;self.partial_attempts=[]
        self.progress={'metadata_bytes':0,'container_bytes':0,'containers_loaded':0,'attempted_containers':[],
                       'uncompressed_bytes':0,'decoded_storage_bytes':0,'completed_attempts':[], 'completed_calls':0}
        counts=Counter();sizes=Counter()
        for row in records:
            need(set(row)=={'role','path','sha256','bytes'},'inventory fields')
            p=Path(row['path']);role=row['role']
            need(role in CONTROLS|{'receipt','audit','index','bundle'} and p.is_absolute() and '..' not in p.parts,'inventory path/role')
            need(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None
                 and integer(row['bytes']),'inventory hash/size')
            key=str(p.resolve());need(key not in self.rows,'duplicate/aliased inventory path')
            need(str(p)==key,'noncanonical/symlink input path')
            need(row['bytes']<=CAPS['bundle_file' if role=='bundle' else 'index_file' if role=='index' else 'metadata_file'],'per-file cap')
            self.rows[key]=dict(row);counts[role]+=1;sizes['bundle' if role=='bundle' else 'metadata']+=row['bytes']
        need(all(counts[k]==1 for k in CONTROLS),'exact five control JSONs')
        need(sum(counts.values())-counts['bundle']<=65 and counts['bundle']<=CAPS['bundles'],'file ceilings')
        need(sizes['bundle']<=CAPS['bundle_total'] and sizes['metadata']+input_manifest_bytes<=CAPS['metadata_total'],'declared aggregate bytes')
        self.progress['input_manifest_bytes']=input_manifest_bytes

    def blob(self,ref,role):
        need(type(ref) is dict and set(ref)=={'path','sha256'},'reference fields')
        key=str(Path(ref['path']).resolve());need(key in self.rows,'undeclared reference')
        row=self.rows[key];need(row['role']==role and row['sha256']==ref['sha256'],'reference role/hash')
        need(role!='bundle' or key not in self.cache,'container second read forbidden')
        if key not in self.cache:
            cap=CAPS['bundle_file' if role=='bundle' else 'index_file' if role=='index' else 'metadata_file']
            if self.loader is None:
                p=Path(row['path']);need(p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'],'input file changed/missing/linked')
                with p.open('rb') as f:b=f.read(min(cap,row['bytes'])+1)
            else:b=self.loader(row)
            bucket='container_bytes' if role=='bundle' else 'metadata_bytes'
            self.progress[bucket]+=len(b)
            need(type(b) is bytes and len(b)==row['bytes']<=cap and digest(b)==row['sha256'],'input bytes/hash changed')
            self.cache[key]=None if role=='bundle' else b
            return b
        return self.cache[key]

    def json(self,ref,role):return decode(self.blob(ref,role))


def zip_inventory(blob):
    need(zipfile.is_zipfile(io.BytesIO(blob)),'unsupported non-ZIP/legacy serialization')
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        infos=z.infolist();need(0<len(infos)<=CAPS['zip_entries'],'ZIP member count')
        names=[v.filename for v in infos];need(len(names)==len(set(names)),'duplicate ZIP member')
        roots={n.split('/')[0] for n in names};need(len(roots)==1 and '' not in roots,'ZIP root')
        total=storage=0;pickle_count=0
        for v in infos:
            parts=v.filename.split('/');need(len(parts)>=2 and all(p not in ('','..','.') for p in parts),'ZIP traversal')
            local='/'.join(parts[1:]);need(v.compress_type==zipfile.ZIP_STORED and not v.flag_bits&1,'compressed/encrypted ZIP forbidden')
            allowed={'data.pkl','byteorder','version','.data/serialization_id','.format_version','.storage_alignment'}
            is_storage=re.fullmatch(r'data/[0-9]+',local) is not None
            need(local in allowed or is_storage,'unsupported ZIP layout')
            need(integer(v.file_size) and v.file_size==v.compress_size,'ZIP size mismatch')
            total+=v.file_size
            if is_storage:storage+=v.file_size
            if local=='data.pkl':
                pickle_count+=1;need(v.file_size<=CAPS['pickle_bytes'],'pickle metadata cap')
        need(pickle_count==1 and total<=CAPS['uncompressed_file'] and storage<=CAPS['storage_file'],'uncompressed/storage cap')
        return total,storage


def graph_storage(value):
    t=torch_cpu();seen=set();storages={};nodes=0
    def visit(x,depth,stack):
        nonlocal nodes
        nodes+=1;need(nodes<=CAPS['nodes'] and depth<=CAPS['depth'],'decoded graph cap')
        if t.is_tensor(x):
            need(x.device.type=='cpu' and x.layout==t.strided and not x.requires_grad,'unsupported tensor device/layout/grad')
            storage=x.untyped_storage();size=storage.nbytes();ident=(storage.data_ptr(),size)
            storages[ident]=size;need(sum(storages.values())<=CAPS['storage_file'],'backing storage cap')
        elif type(x) in (dict,list,tuple):
            ident=id(x);need(ident not in stack,'cyclic decoded graph')
            if ident in seen:return
            seen.add(ident);stack=stack|{ident}
            if type(x) is dict:
                need(all(type(k) is str for k in x),'nonstring metadata key')
                for k,v in x.items():visit(k,depth+1,stack);visit(v,depth+1,stack)
            else:
                for v in x:visit(v,depth+1,stack)
        else:need(x is None or type(x) in (str,bool,int,float),'unsupported decoded object')
    visit(value,0,set())
    return sum(storages.values()),nodes


def exact(a,b):
    t=torch_cpu()
    return a.shape==b.shape and a.dtype==b.dtype and t.equal(a.contiguous().view(t.uint8),b.contiguous().view(t.uint8))


def measure(tensors):
    t=torch_cpu();before=tensors['model_output_before'].double();after=tensors['model_output_after'].double()
    operand=tensors['update_operand'].double();delta=after-before;residual=delta-operand
    def particle(v):
        flat=v.reshape(16,24);return {'l2':flat.square().sum(1).sqrt().tolist(),'linf':flat.abs().amax(1).tolist()}
    def categories(v):return t.where(v.abs()>1,2,t.where(v.abs()==1,1,0))
    a,z=categories(before),categories(after)
    table=[[int(((a==i)&(z==j)).sum()) for j in range(3)] for i in range(3)]
    raw=tensors['input_xyz'].double();clipped=raw.clamp(-1,1);p=tensors['projected_xyz'];so=tensors['source_origins'];co=tensors['cast_origins']
    strata={f'{a}{b}':{'pairs':0,'source_byte_equal':0,'cast_byte_equal':0,'projected_equal':0,'projected_byte_equal':0,'raw_distinct_clip_equal':0,'clipped_distinct_projected_equal':0} for a in (0,1) for b in (0,1)}
    aliases=[]
    for i in range(16):
        for j in range(i+1,16):
            ss=t.equal(so[i],so[j]);cs=t.equal(co[i],co[j]);peq=t.equal(p[i],p[j]);ceq=t.equal(clipped[i],clipped[j]);rq=t.equal(raw[i],raw[j])
            row=strata[f'{int(ss)}{int(cs)}'];row['pairs']+=1;row['projected_equal']+=int(peq)
            row['source_byte_equal']+=int(exact(so[i],so[j]));row['cast_byte_equal']+=int(exact(co[i],co[j]))
            row['projected_byte_equal']+=int(exact(p[i],p[j]));row['raw_distinct_clip_equal']+=int(not rq and ceq)
            row['clipped_distinct_projected_equal']+=int(not ceq and peq)
            if not ceq and peq:aliases.append([i,j])
    unchanged=(after==before);nonzero=(operand!=0)
    byte_same=(tensors['model_output_after'].contiguous().view(t.uint8)==tensors['model_output_before'].contiguous().view(t.uint8)).reshape(16,8,3,-1).all(-1)
    return {'components':384,'particles':16,'pairs':120,'delta':particle(delta),'delta_minus_operand':particle(residual),
            'numerically_unchanged_components':int(unchanged.sum()),'byte_unchanged_components':int(byte_same.sum()),
            'nonzero_operand_components':int(nonzero.sum()),'absorbed_nonzero_components':int((nonzero&unchanged).sum()),
            'absorbed_nonzero_ratio':float((nonzero&unchanged).sum())/int(nonzero.sum()) if bool(nonzero.any()) else None,
            'range_labels':['interior','boundary','outside'],'range_transition':table,
            'before_range':[int((a==i).sum()) for i in range(3)],'after_range':[int((z==i).sum()) for i in range(3)],
            'origin_strata_source_equal_cast_equal':strata,'clipped_distinct_projected_equal_pairs':aliases}


def index_rows(blob):
    rows=[decode(v) for v in blob.splitlines() if v.strip()];need(len(rows)<=10000,'index row cap')
    seen=set();last=0;events=[]
    for row in rows:
        need(set(row)=={'bundle','sha256','first_sequence','last_sequence','events'} and re.fullmatch(r'bundle_[0-9]{6}\.pt',row['bundle']) is not None,'index row schema')
        need(row['bundle'] not in seen and type(row['events']) is list and row['events'],'duplicate/empty index bundle');seen.add(row['bundle'])
        for ev in row['events']:
            need(set(ev)=={'sequence','event','decision_id','global_step','reset_sequence'} and integer(ev['sequence']) and ev['sequence']>last,'index event/order')
            need(type(ev['event']) is str and type(ev['decision_id']) is str and integer(ev['global_step']) and integer(ev['reset_sequence']),'index identity')
            last=ev['sequence'];events.append((row,ev))
        need(row['first_sequence']==row['events'][0]['sequence'] and row['last_sequence']==last,'index sequence range')
    need(len(events)<=200000,'index event cap')
    return rows,events


def load_bundle(reader,ref,index):
    reader.progress['attempted_containers'].append(ref)
    blob=reader.blob(ref,'bundle');uncompressed,_=zip_inventory(blob)
    need(reader.progress['uncompressed_bytes']+uncompressed<=CAPS['uncompressed_total'],'aggregate uncompressed cap')
    reader.progress['uncompressed_bytes']+=uncompressed
    t=torch_cpu()
    try:value=t.load(io.BytesIO(blob),map_location='cpu',weights_only=True)
    except Exception as exc:
        # Do not export incidental pickle/object contents through an error string.
        raise ExtractionError('weights_only CPU container load failed: '+type(exc).__name__) from None
    storage,nodes=graph_storage(value)
    need(reader.progress['decoded_storage_bytes']+storage<=CAPS['storage_total'],'aggregate decoded storage cap')
    reader.progress['decoded_storage_bytes']+=storage;reader.progress['containers_loaded']+=1
    need(type(value) is dict and set(value)=={'schema','events'} and value['schema']=='qd-ed-decision-evidence-v1'
         and type(value['events']) is list and len(value['events'])<=CAPS['events'],'bundle schema/event cap')
    projected=[]
    for ev in value['events']:
        need(type(ev) is dict and set(ev)=={'sequence','event','episode','decision_id','global_step','reset_sequence','values'},'event envelope')
        projected.append({k:ev[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')})
    need(projected==index['events'],'index/container event envelope mismatch')
    return value,{'bytes':len(blob),'uncompressed_bytes':uncompressed,'decoded_storage_bytes':storage,'decoded_nodes':nodes}


def witness_values(ev,arm):
    t=torch_cpu();v=ev['values'];need(type(v) is dict and set(v)=={'metadata','tensors'},'witness values')
    m,x=v['metadata'],v['tensors'];need(type(x) is dict and set(x)==FIELDS,'nine witness tensor fields')
    source=('core.qd_clean_output_rbf:model_output_sample_v1' if arm=='N26' else 'core.qd_actuator_clipped_rbf:clipped_rbf_gradient:v1')
    need(m.get('schema')==arm.lower()+'-bounded-rbf-witness-v1' and m.get('source')==source and m.get('exact_cuda_replay_claim') is False,'witness source/schema')
    c=m.get('call',{});need(c.get('source')==source and c.get('schema')==arm.lower()+'-rbf-call-summary-v1'
         and c.get('descriptor_mode')=='actuator_clipped_eef_v1' and c.get('input_shape')==[16,64,128]
         and c.get('horizon')==8 and c.get('translation_indices')==[39,40,41] and c.get('translation_components')==384
         and c.get('absolute_fallback_used') is False and c.get('summary_only_not_exact_replay') is True
         and c.get('update_operand_is_measured_output_delta') is False,'witness call schema')
    slot=[c.get('phase'),c.get('iteration')];need(slot in SLOTS and integer(c.get('denoising_step')) and integer(c.get('timestep')),'witness slot/step')
    need(set(m.get('tensors',{}))==FIELDS,'tensor declarations')
    size=0
    for name,value in x.items():
        shape=(16,3) if name in {'source_origins','cast_origins'} else (16,8,3)
        need(t.is_tensor(value) and tuple(value.shape)==shape and value.device.type=='cpu' and value.is_floating_point()
             and not value.requires_grad and bool(t.isfinite(value).all()),'tensor shape/device/type/finite')
        info=m['tensors'][name]
        need(info.get('dtype')==str(value.dtype) and info.get('shape')==list(shape)
             and type(info.get('capture_stride_before_serialization')) is list
             and len(info['capture_stride_before_serialization'])==len(shape)
             and all(integer(a) for a in info['capture_stride_before_serialization']),'tensor metadata')
        size+=value.numel()*value.element_size()
    need(x['input_xyz'].dtype in (t.float32,t.bfloat16) and c.get('input_dtype')==str(x['input_xyz'].dtype),'native input dtype')
    need(all(x[k].dtype==x['input_xyz'].dtype for k in ('cast_origins','projected_xyz','gradient_before','gradient_after')),'geometry/gradient dtype')
    need(x['model_output_before'].dtype in (t.float32,t.bfloat16) and x['model_output_before'].dtype==x['model_output_after'].dtype==x['update_operand'].dtype,'output/operand dtype')
    need(size==m.get('numeric_bytes') and size<=20480 and len(json.dumps(m,allow_nan=False).encode())<=16384,'witness numeric/metadata cap')
    if arm=='N26':
        need(c.get('input_source')=='model_output_sample_v1' and c.get('prediction_type')=='sample'
             and c.get('input_binding')=='same_forward_unmodified_model_output' and c.get('model_jacobian_used') is False
             and exact(x['input_xyz'],x['model_output_before']),'N26 stored input/before binding')
    return slot,size,c,x


def analyse_attempt(reader,binding,cell,final,source,refs,original):
    arm=cell['profile'];rr=original['refs'];aid=cell['attempt_id']
    need(set(binding)=={'attempt_id','receipt','audit','index','bundles'} and binding['attempt_id']==aid,'attempt binding')
    need(same_ref(binding['receipt'],cell['worker_receipt']) and same_ref(binding['receipt'],rr['receipt'])
         and same_ref(binding['audit'],cell['audit']) and same_ref(binding['audit'],rr['audit'])
         and same_ref(cell['worker_context'],rr['context']) and same_ref(cell['attempt_result'],rr['terminal']),'accepted first-valid refs')
    receipt=reader.json(binding['receipt'],'receipt');audit=reader.json(binding['audit'],'audit')
    out=Path(final['output_dir']).resolve();episode=out/'eds_eval/decision_evidence/episode_000'
    need(Path(binding['receipt']['path']).resolve()==out/'eds_eval/in-worker-audit-receipt.json'
         and Path(binding['audit']['path']).resolve()==out/'eds_eval/decision-evidence-audit.json'
         and Path(binding['index']['path']).resolve()==episode/'events.jsonl','attempt output ownership')
    need(receipt.get('schema')=='n23-in-worker-audit-receipt-v1' and receipt.get('accepted') is True
         and receipt.get('attempt_id')==aid and receipt.get('episode_key')==cell['episode_key'] and receipt.get('profile')==arm
         and receipt.get('source')==source and same_ref(receipt.get('plan'),refs['plan'])
         and same_ref(receipt.get('runtime'),original['_runtime']) and same_ref(receipt.get('context'),rr['context'])
         and same_ref(receipt.get('audit_report'),binding['audit']) and receipt.get('main_exit_code')==0
         and receipt.get('process_unchanged') is True,'receipt source/runtime/identity')
    evidence=receipt.get('evidence',{});items=evidence.get('files')
    need(type(items) is list and evidence.get('sha256')==canonical(items),'receipt evidence-list digest')
    paths={}
    for row in items:
        need(set(row)=={'path','sha256'} and type(row['path']) is str and not Path(row['path']).is_absolute()
             and '..' not in Path(row['path']).parts and row['path'] not in paths,'receipt nested path/duplicate')
        paths[row['path']]=row['sha256']
    index_rel='eds_eval/decision_evidence/episode_000/events.jsonl'
    need(paths.get(index_rel)==binding['index']['sha256'],'index not bound to native receipt')
    gate_name='n26_clean_output_rbf_audit' if arm=='N26' else 'n25_actuator_clipped_rbf_audit'
    gate=audit.get(gate_name,{})
    need(audit.get('schema')=='qd-ed-decision-evidence-audit-v1' and audit.get('accepted') is True and audit.get('evidence_complete') is True
         and Path(audit.get('episode_dir','')).resolve()==episode
         and gate.get('schema')==arm.lower()+'-native-rbf-audit-v1' and gate.get('accepted') is True,'native profile gate')
    n=final.get('guided_chunks');calls=gate.get('witness_calls_verified')
    need(integer(n) and n==gate.get('guided_decisions') and integer(calls) and calls<=11
         and (arm!='N26' or calls==(11 if n else 0)),'native guided/witness counts')
    need(type(gate.get('witness_checks')) is list and len(gate['witness_checks'])==calls
         and all(x.get('accepted') is True and x.get('candidate_rows')==16 for x in gate['witness_checks']),'native witness attestation')
    native=receipt.get('n26_native_counts',{})
    need(native.get('guided_decisions')==n and native.get('witness_calls_verified')==calls,'receipt native count binding')
    rows,events=index_rows(reader.blob(binding['index'],'index'))
    wn=arm.lower()+'_rbf_witness';cn=wn+'_coverage';opposite=('n25' if arm=='N26' else 'n26')+'_rbf'
    need(not any(e['event'].startswith(opposite) for _,e in events),'cross-arm witness index')
    selected=[(row,e) for row,e in events if e['event'] in (wn,cn)]
    witnesses=[e for _,e in selected if e['event']==wn];cover=[e for _,e in selected if e['event']==cn]
    need(len(witnesses)==calls and len(cover)==(1 if n else 0),'index witness coverage')
    identities={(e['decision_id'],e['global_step'],e['reset_sequence']) for _,e in selected}
    need(len(identities)==(1 if n else 0),'cross-decision witness substitution')
    names=list(dict.fromkeys(row['bundle'] for row,_ in selected));need(len(names)<=2,'per-attempt container cap')
    expected=[]
    for name in names:
        row=next(v for v in rows if v['bundle']==name);rel='eds_eval/decision_evidence/episode_000/'+name
        need(paths.get(rel)==row['sha256'],'bundle not bound to native receipt')
        expected.append({'path':str(episode/name),'sha256':row['sha256']})
    need(len(binding['bundles'])==len(expected) and all(same_ref(a,b) for a,b in zip(binding['bundles'],expected)),'nonminimal/substituted container selection')
    result={'attempt_id':aid,'task_id':cell['task_id'],'arm':arm,'guided_decisions':n,'zero_guided':n==0,
            'recorded_witness_calls':calls,'all_call_summaries_verified':gate.get('all_call_summaries_verified'),
            'calls':[],'containers':[],'missing_slots':SLOTS if not n else None,
            'first_guided_and_origin_association':'relies on bound original same-worker native audit',
            'refs':{'receipt':binding['receipt'],'audit':binding['audit'],'index':binding['index']}}
    reader.partial_attempts.append(result)
    seen=[];coverage=None;numeric=0
    for ref in binding['bundles']:
        index=next(row for row in rows if row['bundle']==Path(ref['path']).name)
        bundle,info=load_bundle(reader,ref,index);result['containers'].append({'ref':ref,**info})
        for ev in bundle['events']:
            if ev['event'] not in (wn,cn):continue
            need(ev['episode']==0 and (ev['decision_id'],ev['global_step'],ev['reset_sequence']) in identities,'event attempt/decision identity')
            if ev['event']==cn:
                need(coverage is None,'duplicate coverage');coverage=ev['values'];continue
            slot,size,c,tensors=witness_values(ev,arm);need(slot not in seen,'duplicate witness slot');seen.append(slot);numeric+=size
            need(numeric<=225280,'episode witness numeric cap')
            result['calls'].append({'phase':slot[0],'iteration':slot[1],'sequence':ev['sequence'],'decision_id':ev['decision_id'],
                'global_step':ev['global_step'],'reset_sequence':ev['reset_sequence'],'denoising_step':c['denoising_step'],'timestep':c['timestep'],
                'input_dtype':c['input_dtype'],'output_dtype':str(tensors['model_output_before'].dtype),'numeric_bytes':size,
                'bundle':ref,**measure(tensors)})
            del tensors
            reader.progress['completed_calls']+=1
        del ev,bundle
    need(seen==[s for s in SLOTS if s in seen] and len(seen)==calls,'slot order/coverage')
    missing=[s for s in SLOTS if s not in seen]
    if n:
        need(coverage=={'selected_slots':seen,'missing_slots':missing,'numeric_bytes':numeric,'max_calls':11,'numeric_cap_bytes':225280},'coverage metadata mismatch')
    need(gate.get('witness_numeric_bytes')==numeric,'native witness numeric-byte count')
    result['missing_slots']=missing;reader.progress['completed_attempts'].append(aid)
    return result


def distribution(values):
    if not values:return {'count':0,'mean':None,'median':None,'p90':None}
    v=sorted(values)
    def quantile(q):
        a=(len(v)-1)*q;i=int(a);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(a-i)
    return {'count':len(v),'mean':sum(v)/len(v),'median':quantile(.5),'p90':quantile(.9)}


def aggregate(calls):
    nonzero=sum(c['nonzero_operand_components'] for c in calls)
    absorbed=sum(c['absorbed_nonzero_components'] for c in calls)
    return {'calls':len(calls),'components':384*len(calls),'particles':16*len(calls),'pairs':120*len(calls),
            'delta_l2':distribution([x for c in calls for x in c['delta']['l2']]),
            'delta_linf':distribution([x for c in calls for x in c['delta']['linf']]),
            'residual_l2':distribution([x for c in calls for x in c['delta_minus_operand']['l2']]),
            'residual_linf':distribution([x for c in calls for x in c['delta_minus_operand']['linf']]),
            'range_transition':[[sum(c['range_transition'][i][j] for c in calls) for j in range(3)] for i in range(3)],
            'before_outside':sum(c['before_range'][2] for c in calls),'after_outside':sum(c['after_range'][2] for c in calls),
            'numerically_unchanged_components':sum(c['numerically_unchanged_components'] for c in calls),
            'byte_unchanged_components':sum(c['byte_unchanged_components'] for c in calls),
            'nonzero_operand_components':nonzero,'absorbed_nonzero_components':absorbed,
            'absorbed_nonzero_ratio':absorbed/nonzero if nonzero else None,
            'clipped_distinct_projected_equal_pairs':sum(len(c['clipped_distinct_projected_equal_pairs']) for c in calls)}


def build(data,reader):
    need(data.get('schema')=='n26-bounded-witness-input-v1' and data.get('root_authorized') is True and data.get('executable') is True
         and data.get('whole_container_decoding_authorized') is True,'actual input disabled/unacknowledged full-container decoding')
    refs=data.get('refs',{});need(set(refs)==CONTROLS,'exact five controls')
    review=reader.json(refs['terminal_review'],'terminal_review');result=reader.json(refs['result'],'result')
    plan=reader.json(refs['plan'],'plan');source=reader.json(refs['source'],'source');inventory=reader.json(refs['terminal_input'],'terminal_input')
    need(review.get('schema')=='n26-root-terminal-review-v1' and review.get('decision')=='ACCEPT_TERMINAL_RECONSTRUCTION'
         and review.get('discrepancies')==[] and review.get('unsettled_attempts')==[]
         and all(same_ref(review.get(k),refs[k]) for k in ('result','plan','source'))
         and same_ref(review.get('input_manifest'),refs['terminal_input']),'accepted independent terminal review')
    need(review.get('reader',{}).get('sha256')==TERMINAL_READER_SHA,'accepted terminal reader identity')
    need(source.get('commit')==COMMIT and len(source.get('files',[]))==315 and source.get('sha256')==canonical(source['files'])
         and len({x['path'] for x in source['files']})==315,'source closure')
    need(plan.get('source_commit')==COMMIT and plan.get('code_files')==source['files'] and plan.get('frozen') is True
         and plan.get('phase_authorization')=={'dev':True,'validation':False,'formal':False},'frozen Dev source/phase')
    need(result.get('schema')=='n26-dev-cohort-result-v1' and result.get('cohort_id')==COHORT and result.get('source_commit')==COMMIT
         and result.get('planned')==40 and same_ref(result.get('plan'),refs['plan'])
         and result.get('decision')==review.get('cohort_disposition')
         and result['decision'] in {'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION','REJECT','REJECT_NUMERIC_FUTILITY','INVALID_OR_INTERRUPTED'},'original cohort disposition/identity')
    need(inventory.get('schema')=='n26-terminal-metadata-input-v1' and inventory.get('root_authorized') is True and inventory.get('executable') is True
         and all(same_ref(inventory.get('refs',{}).get(k),refs[k]) for k in ('result','plan','source')),'accepted terminal input binding')
    need(same_ref(inventory.get('refs',{}).get('runtime'),
                  {'path':plan.get('runtime_manifest_path'),'sha256':plan.get('runtime_manifest_sha256')}),'runtime identity binding')
    rows=plan['episodes'];accepted=result['accepted_cells']
    need(len(rows)==40 and [(r['task_id'],r['profile']) for r in rows]==[(i,a) for i in range(10) for a in ('C0','Q0','N25','N26')],'frozen matrix')
    need(len(accepted)<=40 and [x['episode_key'] for x in accepted]==[x['episode_key'] for x in rows[:len(accepted)]]
         and len({x['attempt_id'] for x in accepted})==len(accepted)
         and review.get('accepted_cells')==result.get('audited_cells')==len(accepted),'all accepted prefix/unique attempts')
    need(all(c['task_id']==r['task_id'] and c['profile']==r['profile'] and type(c['success']) is bool
             for c,r in zip(accepted,rows)),'all accepted cell row identities')
    counts={a:{'audited':sum(c['profile']==a for c in accepted),'success':sum(c['profile']==a and c['success'] is True for c in accepted)} for a in ('C0','Q0','N25','N26')}
    need(counts==review.get('counts')==result.get('counts'),'accepted denominators')
    targets=[c for c in accepted if c['profile'] in ('N25','N26')];bindings=data['attempts']
    need(len(targets)<=20 and [b['attempt_id'] for b in bindings]==[c['attempt_id'] for c in targets],'include every accepted arm cell in order')
    originals=inventory['attempts'];attempts=result['attempts']
    need(len({x['attempt_id'] for x in originals})==len(originals) and len({x['attempt_id'] for x in attempts})==len(attempts),'duplicate original/result attempt')
    outputs=[]
    for binding,cell in zip(bindings,targets):
        row=next(r for r in rows if r['episode_key']==cell['episode_key'])
        need(row['task_id']==cell['task_id'] and row['profile']==cell['profile'] and type(cell['success']) is bool,'cell identity')
        old=next((x for x in originals if x['attempt_id']==cell['attempt_id']),None)
        final=next((x['terminal'] for x in attempts if x['attempt_id']==cell['attempt_id']),None)
        need(old is not None and final is not None and final.get('outcome_valid') is True
             and final.get('episode_key')==cell['episode_key'],'accepted first-valid terminal')
        for role in ('receipt','audit'):
            matches=[v for v in inventory['files'] if v.get('role')==role and v.get('present') is True
                     and same_ref({'path':v.get('path'),'sha256':v.get('sha256')},binding[role])]
            need(len(matches)==1 and matches[0]['bytes']==reader.rows[str(Path(binding[role]['path']).resolve())]['bytes'],
                 'receipt/audit absent or changed from accepted terminal inventory')
        outputs.append(analyse_attempt(reader,binding,cell,final,source,refs,{**old,'_runtime':inventory['refs']['runtime']}))
    need(set(reader.cache)==set(reader.rows),'extra unused inventory file')
    groups={a:{p:aggregate([c for v in outputs if v['arm']==a for c in v['calls'] if c['phase']==p]) for p in ('initial','rollout')} for a in ('N25','N26')}
    pairs=[]
    for task in sorted({x['task_id'] for x in outputs}):
        for slot in SLOTS:
            cells={a:next((v for v in outputs if v['task_id']==task and v['arm']==a),None) for a in ('N25','N26')}
            cs={a:next((c for c in v['calls'] if [c['phase'],c['iteration']]==slot),None) if v else None for a,v in cells.items()}
            pairs.append({'task_id':task,'phase':slot[0],'iteration':slot[1],
                'N25':aggregate([cs['N25']]) if cs['N25'] else None,'N26':aggregate([cs['N26']]) if cs['N26'] else None,
                'same_state_or_particle_pair':False})
    return {'schema':'n26-bounded-witness-summary-v1','extraction_status':'COMPLETE','cohort_disposition':result['decision'],
        'accepted_prefix_cells':len(accepted),'planned_cells':40,'selected_attempts':len(outputs),
        'describes_partial_prefix_only':len(accepted)<40 or result['decision']=='INVALID_OR_INTERRUPTED','attempts':outputs,
        'arm_phase_summaries':groups,'task_slot_pairs':pairs,'read_progress':dict(reader.progress),'input_refs':refs,
        'limits':CAPS,'arithmetic':'FP64 descriptive subtraction/norms and clipping equivalence; no CUDA replay',
        'limitations':['First-guided snapshot only; origin association and first-active selection depend on original native audit.',
                       'Whole selected containers, including incidental events, were decoded; only witness statistics exported.',
                       'Model-output differences are not executed actions or physical outcomes; aliasing cause and task impact remain Unknown.'],
        'actual_read_release_granted_by_this_output':False,'gpu_authorized':False,'next_algorithm_authorized':False}


def main():
    # Import only this owned boundary before Torch, never a production helper.
    from cpu_boundary_v1 import establish,guard,observation,HERE
    establish(180);p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--input-sha256',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    target=Path(args.output).absolute();need(target.parent==HERE and not target.exists() and not target.is_symlink(),'output must be a new preparation artifact')
    inp=Path(args.input).absolute();need(inp.parent==HERE and inp.is_file() and not inp.is_symlink() and inp.stat().st_size<=16*MiB,'input manifest path/size')
    with inp.open('rb') as f:blob=f.read(16*MiB+1)
    need(len(blob)<=16*MiB and digest(blob)==args.input_sha256,'input manifest hash')
    data=decode(blob);files=data.get('files',[])
    allowed=[__file__,str(HERE/'cpu_boundary_v1.py'),str(inp)]+[v['path'] for v in files]
    guard(inputs=allowed,writes=[target]);start=time.monotonic();reader=None
    try:
        reader=Reader(files,input_manifest_bytes=len(blob));out=build(data,reader)
    except Exception as exc:
        out={'schema':'n26-bounded-witness-summary-v1','extraction_status':'INCOMPLETE','error_type':type(exc).__name__,
             'error':str(exc),'read_progress':reader.progress if reader else None,
             'partial_attempts':reader.partial_attempts if reader else [],'gpu_authorized':False,'next_algorithm_authorized':False}
    out.update(boundary=observation(),wall_seconds=time.monotonic()-start,input_manifest=reference(str(inp),blob))
    if out['boundary']['cuda_initialized'] or out['boundary']['guard_denials']:
        out['extraction_status']='INCOMPLETE'
    encoded=(json.dumps(out,allow_nan=False,sort_keys=True,indent=2)+'\n').encode();need(len(encoded)<=CAPS['output'],'output cap')
    with target.open('xb') as f:f.write(encoded)
    print(json.dumps({'extraction_status':out['extraction_status'],'output':str(target),'sha256':digest(encoded),'boundary':out['boundary']}))
    return 0 if out['extraction_status']=='COMPLETE' else 1


if __name__=='__main__':raise SystemExit(main())
