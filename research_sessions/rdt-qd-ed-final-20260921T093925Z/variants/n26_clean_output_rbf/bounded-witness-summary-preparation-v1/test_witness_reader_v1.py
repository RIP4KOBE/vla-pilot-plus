"""Synthetic-only checks; expected measurements are hand computed."""
import copy
import io
import json
import math
from pathlib import Path
import zipfile
import pytest
import witness_reader_v1 as w

HERE=Path(__file__).resolve().parent

def encoded(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def witness(arm='N25',slot=('initial',-1),dtype=None):
    t=w.torch_cpu();dtype=dtype or t.float32
    before=t.full((16,8,3),.25,dtype=dtype);operand=t.full_like(before,.25)
    x={k:t.zeros_like(before) for k in w.FIELDS if k not in {'source_origins','cast_origins'}}
    x.update(input_xyz=before.clone(),model_output_before=before,model_output_after=before+operand,update_operand=operand,
             source_origins=t.zeros((16,3),dtype=t.float64),cast_origins=t.zeros((16,3),dtype=dtype))
    source='core.qd_clean_output_rbf:model_output_sample_v1' if arm=='N26' else 'core.qd_actuator_clipped_rbf:clipped_rbf_gradient:v1'
    call={'schema':arm.lower()+'-rbf-call-summary-v1','source':source,'descriptor_mode':'actuator_clipped_eef_v1',
          'input_shape':[16,64,128],'horizon':8,'translation_indices':[39,40,41],'translation_components':384,
          'absolute_fallback_used':False,'summary_only_not_exact_replay':True,'update_operand_is_measured_output_delta':False,
          'phase':slot[0],'iteration':slot[1],'denoising_step':0,'timestep':9,'input_dtype':str(dtype)}
    if arm=='N26':call.update(input_source='model_output_sample_v1',prediction_type='sample',input_binding='same_forward_unmodified_model_output',model_jacobian_used=False)
    m={'schema':arm.lower()+'-bounded-rbf-witness-v1','source':source,'exact_cuda_replay_claim':False,'call':call,
       'numeric_bytes':sum(v.numel()*v.element_size() for v in x.values()),
       'tensors':{k:{'shape':list(v.shape),'dtype':str(v.dtype),'capture_stride_before_serialization':list(v.stride())} for k,v in x.items()}}
    return {'metadata':m,'tensors':x}

class Fixture:
    def __init__(self,*,prefix=3,guided=1,slots=None,mutate=None,dtype=None,split=False):
        self.store={};self.records=[];self.loads={};self.objects={};self.container=None
        root=HERE/'fixture'
        def put(name,role,obj,raw=False):
            p=root/name;b=obj if raw else encoded(obj);r=w.reference(p,b)
            self.store[str(p.resolve())]=b;self.records.append({'role':role,**r,'bytes':len(b)});self.objects[role]=obj
            return r
        source={'commit':w.COMMIT,'files':[{'path':f'synthetic/{i}.py','sha256':'1'*64} for i in range(315)]};source['sha256']=w.canonical(source['files'])
        sr=put('source.json','source',source)
        rows=[{'episode_key':f't{i}_{a}','task_id':i,'profile':a} for i in range(10) for a in ('C0','Q0','N25','N26')]
        runtime={'path':str(root/'UNREAD-runtime.json'),'sha256':'2'*64}
        plan={'source_commit':w.COMMIT,'code_files':source['files'],'frozen':True,'phase_authorization':{'dev':True,'validation':False,'formal':False},
              'episodes':rows,'runtime_manifest_path':runtime['path'],'runtime_manifest_sha256':runtime['sha256']}
        pr=put('plan.json','plan',plan);accepted=[];attempts=[];original=[];bindings=[]
        for i,row in enumerate(rows[:prefix]):
            aid=f'synthetic_{row["episode_key"]}';arm=row['profile'];out=root/f'attempt-{arm}'
            context={'path':str(out/'context.json'),'sha256':'3'*64};terminal={'path':str(out/'terminal.json'),'sha256':'4'*64}
            cell={**row,'attempt_id':aid,'success':False,'worker_context':context,'attempt_result':terminal}
            final={'outcome_valid':True,'episode_key':row['episode_key'],'output_dir':str(out),'guided_chunks':guided}
            if arm in ('N25','N26'):
                ss=[] if not guided else (w.SLOTS if arm=='N26' else (slots or [w.SLOTS[0]]))
                events=[];total=0
                for slot in ss:
                    value=witness(arm,slot,dtype);total+=value['metadata']['numeric_bytes']
                    events.append({'sequence':len(events)+1,'event':arm.lower()+'_rbf_witness','episode':0,
                                   'decision_id':'decision_0','global_step':24,'reset_sequence':0,'values':value})
                if guided:
                    events.append({'sequence':len(events)+1,'event':arm.lower()+'_rbf_witness_coverage','episode':0,'decision_id':'decision_0','global_step':24,'reset_sequence':0,
                        'values':{'selected_slots':ss,'missing_slots':[s for s in w.SLOTS if s not in ss],'numeric_bytes':total,'max_calls':11,'numeric_cap_bytes':225280}})
                    events.append({'sequence':len(events)+1,'event':'incidental_unexported','episode':0,'decision_id':'decision_0','global_step':24,'reset_sequence':0,
                                   'values':{'text':'SECRET_UNRELATED_PROMPT','backing':w.torch_cpu().zeros(1024)}})
                bundle={'schema':'qd-ed-decision-evidence-v1','events':events}
                if mutate:mutate(bundle,arm)
                self.container=bundle;bundles=[];evidence=[];indexes=[]
                if guided:
                    parts=[events[:6],events[6:]] if split else [events]
                    for part_index,part in enumerate(parts):
                        name=f'bundle_{part_index:06d}.pt';buf=io.BytesIO()
                        w.torch_cpu().save({'schema':bundle['schema'],'events':part},buf);raw=buf.getvalue()
                        br=put(f'attempt-{arm}/eds_eval/decision_evidence/episode_000/{name}','bundle',raw,True);bundles.append(br)
                        indexes.append({'bundle':name,'sha256':br['sha256'],'first_sequence':part[0]['sequence'],'last_sequence':part[-1]['sequence'],
                                        'events':[{k:e[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')} for e in part]})
                        evidence.append({'path':'eds_eval/decision_evidence/episode_000/'+name,'sha256':br['sha256']})
                ir=put(f'attempt-{arm}/eds_eval/decision_evidence/episode_000/events.jsonl','index',b''.join(encoded(x) for x in indexes),True)
                evidence.append({'path':'eds_eval/decision_evidence/episode_000/events.jsonl','sha256':ir['sha256']})
                gn='n26_clean_output_rbf_audit' if arm=='N26' else 'n25_actuator_clipped_rbf_audit'
                audit={'schema':'qd-ed-decision-evidence-audit-v1','accepted':True,'evidence_complete':True,'episode_dir':str(out/'eds_eval/decision_evidence/episode_000'),
                       gn:{'schema':arm.lower()+'-native-rbf-audit-v1','accepted':True,'guided_decisions':guided,'witness_calls_verified':len(ss),'witness_numeric_bytes':total,
                           'all_call_summaries_verified':11*guided,'witness_checks':[{'accepted':True,'candidate_rows':16} for s in ss]}}
                ar=put(f'attempt-{arm}/eds_eval/decision-evidence-audit.json','audit',audit)
                receipt={'schema':'n23-in-worker-audit-receipt-v1','accepted':True,'attempt_id':aid,'episode_key':row['episode_key'],'profile':arm,
                         'source':source,'plan':pr,'runtime':runtime,'context':context,'audit_report':ar,'main_exit_code':0,'process_unchanged':True,
                         'evidence':{'files':evidence,'sha256':w.canonical(evidence)},'n26_native_counts':{'guided_decisions':guided,'witness_calls_verified':len(ss)}}
                rr=put(f'attempt-{arm}/eds_eval/in-worker-audit-receipt.json','receipt',receipt)
                cell.update(worker_receipt=rr,audit=ar);original.append({'attempt_id':aid,'refs':{'context':context,'terminal':terminal,'receipt':rr,'audit':ar}})
                bindings.append({'attempt_id':aid,'receipt':rr,'audit':ar,'index':ir,'bundles':bundles})
            accepted.append(cell);attempts.append({'attempt_id':aid,'terminal':final})
        counts={a:{'audited':sum(c['profile']==a for c in accepted),'success':0} for a in ('C0','Q0','N25','N26')}
        result={'schema':'n26-dev-cohort-result-v1','cohort_id':w.COHORT,'source_commit':w.COMMIT,'planned':40,'audited_cells':prefix,
                'plan':pr,'decision':'INVALID_OR_INTERRUPTED','accepted_cells':accepted,'attempts':attempts,'counts':counts}
        rr=put('result.json','result',result)
        inventory={'schema':'n26-terminal-metadata-input-v1','root_authorized':True,'executable':True,'refs':{'result':rr,'plan':pr,'source':sr,'runtime':runtime},
                   'attempts':original,'files':[{**r,'present':True} for r in self.records if r['role'] in ('receipt','audit')]}
        ir=put('terminal-input.json','terminal_input',inventory)
        review={'schema':'n26-root-terminal-review-v1','decision':'ACCEPT_TERMINAL_RECONSTRUCTION','discrepancies':[],'unsettled_attempts':[],
                'cohort_disposition':result['decision'],'result':rr,'plan':pr,'source':sr,'input_manifest':ir,'accepted_cells':prefix,'counts':counts,
                'reader':{'path':'/synthetic/UNREAD-reader.py','sha256':w.TERMINAL_READER_SHA}}
        tr=put('review.json','terminal_review',review)
        self.data={'schema':'n26-bounded-witness-input-v1','root_authorized':True,'executable':True,'whole_container_decoding_authorized':True,
                   'refs':{'terminal_review':tr,'result':rr,'plan':pr,'source':sr,'terminal_input':ir},'attempts':bindings,'files':self.records}
    def reader(self):
        def load(row):
            p=str(Path(row['path']).resolve());self.loads[p]=self.loads.get(p,0)+1;return self.store[p]
        return w.Reader(self.records,load)
    def run(self):return w.build(self.data,self.reader())


def test_complete_all_slots_and_incidental_storage():
    f=Fixture(slots=w.SLOTS);o=f.run();a=o['attempts'][0]
    assert len(a['calls'])==11 and a['missing_slots']==[] and o['describes_partial_prefix_only']
    assert all(n==1 for n in f.loads.values()) and o['read_progress']['containers_loaded']==1
    assert a['containers'][0]['decoded_storage_bytes']>sum(c['numeric_bytes'] for c in a['calls'])
    assert 'SECRET_UNRELATED_PROMPT' not in json.dumps(o) and o['cohort_disposition']=='INVALID_OR_INTERRUPTED'
    assert o['task_slot_pairs'][0]['N26'] is None


def test_both_arms_keep_failures():
    o=Fixture(prefix=4).run();assert [a['arm'] for a in o['attempts']]==['N25','N26']
    assert len(o['attempts'][1]['calls'])==11 and o['task_slot_pairs'][0]['same_state_or_particle_pair'] is False


def test_zero_guided_retained():
    o=Fixture(prefix=4,guided=0).run()
    assert len(o['attempts'])==2 and o['read_progress']['containers_loaded']==0
    assert all(a['zero_guided'] and a['missing_slots']==w.SLOTS for a in o['attempts'])
    assert o['arm_phase_summaries']['N26']['initial']['delta_l2']['mean'] is None

@pytest.mark.parametrize('field',['root_authorized','executable','whole_container_decoding_authorized'])
def test_disabled(field):
    f=Fixture(guided=0);f.data[field]=False
    with pytest.raises(w.ExtractionError):f.run()

@pytest.mark.parametrize('kind',['attempt','recovery','extra','missing','receipt','audit','index','alias'])
def test_binding_errors(kind):
    f=Fixture(guided=0);b=f.data['attempts'][0]
    if kind=='attempt':b['attempt_id']='wrong'
    elif kind=='recovery':b['attempt_id']+='__invalid_primary'
    elif kind=='extra':f.data['attempts'].append(copy.deepcopy(b))
    elif kind=='missing':f.data['attempts']=[]
    elif kind in ('receipt','audit','index'):b[kind]={**b[kind],'sha256':'a'*64}
    elif kind=='alias':f.records.append({**f.records[0],'path':f.records[0]['path']+'/../'+Path(f.records[0]['path']).name})
    with pytest.raises(w.ExtractionError):f.run()

@pytest.mark.parametrize('role',['source','plan','terminal_review','terminal_input','receipt','audit','index','bundle'])
def test_changed_hash(role):
    f=Fixture();row=next(r for r in f.records if r['role']==role);f.store[str(Path(row['path']).resolve())]+=b' '
    with pytest.raises(w.ExtractionError,match='bytes/hash'):f.run()

@pytest.mark.parametrize('role',['source','bundle'])
def test_preallocation_size_cap(role):
    f=Fixture();row=next(r for r in f.records if r['role']==role);row['bytes']=w.CAPS['bundle_file' if role=='bundle' else 'metadata_file']+1
    with pytest.raises(w.ExtractionError,match='per-file'):f.reader()
    assert not f.loads

@pytest.mark.parametrize('kind',['cross_decision','duplicate_slot','extra_slot','missing_slot','cross_arm','zero_contradiction'])
def test_slot_faults(kind):
    def mutate(b,arm):
        es=b['events']
        if kind=='cross_decision':es[0]['decision_id']='later'
        elif kind=='cross_arm':es[0]['event']='n26_rbf_witness'
        elif kind=='extra_slot':es[0]['values']['metadata']['call']['iteration']=12
        elif kind=='missing_slot':es[0]['event']='non_witness'
        elif kind=='duplicate_slot':es.insert(1,copy.deepcopy(es[0]));[e.update(sequence=i+1) for i,e in enumerate(es)]
        elif kind=='zero_contradiction':es[1]['values']['numeric_bytes']=0
    f=Fixture(mutate=mutate)
    with pytest.raises(w.ExtractionError):f.run()

@pytest.mark.parametrize('kind',['shape','dtype','nonfinite','n26_input','source','runtime_call'])
def test_witness_corruption(kind):
    t=w.torch_cpu();v=witness('N26');x=v['tensors']
    if kind=='shape':x['gradient_after']=t.zeros(1)
    elif kind=='dtype':x['gradient_after']=x['gradient_after'].double()
    elif kind=='nonfinite':x['gradient_after'][0,0,0]=float('nan')
    elif kind=='n26_input':x['input_xyz'][0,0,0]=.5
    elif kind=='source':v['metadata']['source']='other'
    elif kind=='runtime_call':v['metadata']['call']['prediction_type']='epsilon'
    with pytest.raises(w.ExtractionError):w.witness_values({'values':v},'N26')

@pytest.mark.parametrize('dtype_name',['float32','bfloat16'])
def test_hand_update(dtype_name):
    t=w.torch_cpu();x=witness(dtype=getattr(t,dtype_name))['tensors'];m=w.measure(x)
    assert m['delta']['l2']==[math.sqrt(24)*.25]*16 and m['delta']['linf']==[.25]*16
    assert m['delta_minus_operand']['l2']==[0.0]*16 and m['absorbed_nonzero_components']==0
    assert m['range_transition']==[[384,0,0],[0,0,0],[0,0,0]]
    assert m['origin_strata_source_equal_cast_equal']['11']['pairs']==120


def test_absorbed_operand_signed_zero_range_both_directions():
    t=w.torch_cpu();x=witness(dtype=t.bfloat16)['tensors'];x['model_output_before'].fill_(256);x['model_output_after'].fill_(256);x['update_operand'].fill_(.25)
    m=w.measure(x);assert m['absorbed_nonzero_components']==384 and m['absorbed_nonzero_ratio']==1 and m['delta']['l2']==[0.]*16
    x['model_output_before'].zero_();x['model_output_after'].zero_();x['update_operand'].zero_();x['model_output_after'][0,0,0]=-0.
    x['model_output_before'][0,0,1]=2;x['model_output_after'][0,0,1]=.5
    x['model_output_before'][0,0,2]=.5;x['model_output_after'][0,0,2]=2
    m=w.measure(x);assert m['numerically_unchanged_components']==382 and m['byte_unchanged_components']==381
    assert m['range_transition'][2][0]==m['range_transition'][0][2]==1 and m['absorbed_nonzero_ratio'] is None


def test_aliasing_unequal_origin_and_cast_loss():
    t=w.torch_cpu();x=witness()['tensors']
    for i in range(16):x['input_xyz'][i].fill_(i/32);x['source_origins'][i].fill_(i/10000)
    m=w.measure(x);s=m['origin_strata_source_equal_cast_equal']['01'];assert s['pairs']==120 and s['clipped_distinct_projected_equal']==120
    for i in range(16):x['input_xyz'][i].fill_(i+2)
    m=w.measure(x);assert m['origin_strata_source_equal_cast_equal']['01']['raw_distinct_clip_equal']==120
    assert not m['clipped_distinct_projected_equal_pairs']


def test_storage_counts_backing_once_and_graph_bounds(monkeypatch):
    t=w.torch_cpu();back=t.zeros(4096);size,n=w.graph_storage({'a':back[:1],'b':back[2:3]});assert size==4096*4
    monkeypatch.setitem(w.CAPS,'storage_file',100)
    with pytest.raises(w.ExtractionError,match='backing storage'):w.graph_storage({'a':back[:1]})
    cyclic=[];cyclic.append(cyclic)
    with pytest.raises(w.ExtractionError,match='cyclic'):w.graph_storage(cyclic)

@pytest.mark.parametrize('kind',['compressed','traversal','unknown','legacy','oversize_pickle'])
def test_zip_rejection(kind,monkeypatch):
    b=io.BytesIO()
    if kind=='legacy':raw=b'not zip'
    else:
        with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED if kind=='compressed' else zipfile.ZIP_STORED) as z:
            name={'traversal':'archive/../data.pkl','unknown':'archive/foreign','oversize_pickle':'archive/data.pkl'}.get(kind,'archive/data.pkl');z.writestr(name,b'x'*10)
        raw=b.getvalue()
    if kind=='oversize_pickle':monkeypatch.setitem(w.CAPS,'pickle_bytes',2)
    with pytest.raises(w.ExtractionError):w.zip_inventory(raw)


def test_partial_failure_preserves_calls_and_no_second_load():
    def mutate(b,arm):b['events'][1]['values']['tensors']['gradient_after'][0,0,0]=float('nan')
    f=Fixture(slots=w.SLOTS,mutate=mutate);r=f.reader()
    with pytest.raises(w.ExtractionError):w.build(f.data,r)
    assert r.progress['completed_calls']==1 and len(r.partial_attempts[0]['calls'])==1 and r.progress['containers_loaded']==1
    with pytest.raises(w.ExtractionError,match='second read'):r.blob(f.data['attempts'][0]['bundles'][0],'bundle')


def test_source_runtime_and_original_inventory_gates(monkeypatch):
    f=Fixture(guided=0);r=f.reader();original=r.json
    def bad(ref,role):
        obj=copy.deepcopy(original(ref,role))
        if role=='receipt':obj['runtime']['sha256']='a'*64
        return obj
    monkeypatch.setattr(r,'json',bad)
    with pytest.raises(w.ExtractionError,match='runtime/identity'):w.build(f.data,r)
    r=f.reader();original=r.json
    def absent(ref,role):
        obj=copy.deepcopy(original(ref,role))
        if role=='terminal_input':obj['files']=[]
        return obj
    monkeypatch.setattr(r,'json',absent)
    with pytest.raises(w.ExtractionError,match='terminal inventory'):w.build(f.data,r)

@pytest.mark.parametrize('role,change',[
    ('source',lambda v:v.update(commit='0'*40)),
    ('plan',lambda v:v.update(runtime_manifest_sha256='0'*64)),
    ('terminal_review',lambda v:v['reader'].update(sha256='0'*64)),
    ('receipt',lambda v:v.update(attempt_id='different_attempt')),
    ('receipt',lambda v:v['source'].update(commit='0'*40)),
    ('audit',lambda v:v['n25_actuator_clipped_rbf_audit'].update(guided_decisions=1)),
    ('audit',lambda v:v.update(evidence_complete=False)),
    ('result',lambda v:v['accepted_cells'][0].update(profile='N25')),
])
def test_semantic_binding_negatives(role,change,monkeypatch):
    f=Fixture(guided=0);r=f.reader();original=r.json
    def altered(ref,current):
        obj=copy.deepcopy(original(ref,current))
        if current==role:change(obj)
        return obj
    monkeypatch.setattr(r,'json',altered)
    with pytest.raises(w.ExtractionError):w.build(f.data,r)


def test_n26_signed_zero_binding_is_bytewise():
    v=witness('N26');v['tensors']['input_xyz'].zero_();v['tensors']['model_output_before'].zero_()
    v['tensors']['input_xyz'][0,0,0]=-0.
    assert w.torch_cpu().equal(v['tensors']['input_xyz'],v['tensors']['model_output_before'])
    with pytest.raises(w.ExtractionError,match='input/before'):w.witness_values({'values':v},'N26')


def test_graph_depth_and_node_limits(monkeypatch):
    monkeypatch.setitem(w.CAPS,'depth',2)
    with pytest.raises(w.ExtractionError,match='graph cap'):w.graph_storage([[[[0]]]])
    monkeypatch.setitem(w.CAPS,'depth',64);monkeypatch.setitem(w.CAPS,'nodes',3)
    with pytest.raises(w.ExtractionError,match='graph cap'):w.graph_storage([0,1,2,3])


def test_declared_metadata_includes_manifest(monkeypatch):
    f=Fixture(guided=0);total=sum(r['bytes'] for r in f.records)
    monkeypatch.setitem(w.CAPS,'metadata_total',total)
    with pytest.raises(w.ExtractionError,match='aggregate'):w.Reader(f.records,input_manifest_bytes=1)

class UnapprovedObject:pass

def test_weights_only_no_unsafe_fallback():
    f=Fixture();r=f.reader();ref=f.data['attempts'][0]['bundles'][0];key=str(Path(ref['path']).resolve())
    b=io.BytesIO();w.torch_cpu().save({'unrelated':UnapprovedObject()},b);raw=b.getvalue()
    f.store[key]=raw;ref['sha256']=w.digest(raw);r.rows[key].update(sha256=ref['sha256'],bytes=len(raw))
    with pytest.raises(w.ExtractionError,match='weights_only CPU container load failed'):
        w.load_bundle(r,ref,{'events':[]})
    assert r.progress['containers_loaded']==0


def test_two_containers_released_before_next(monkeypatch):
    import weakref
    f=Fixture(slots=w.SLOTS,split=True);original=w.load_bundle;previous=[];calls=[]
    def wrapped(reader,ref,index):
        assert all(v() is None for v in previous)
        value,info=original(reader,ref,index)
        previous[:]=[weakref.ref(t) for e in value['events'] if e['event']=='n25_rbf_witness' for t in e['values']['tensors'].values()]
        calls.append(ref);return value,info
    monkeypatch.setattr(w,'load_bundle',wrapped)
    result=f.run();assert len(calls)==2 and result['read_progress']['containers_loaded']==2
    assert len(result['attempts'][0]['calls'])==11 and all(n==1 for n in f.loads.values())


def test_second_container_fault_keeps_first_partial():
    f=Fixture(slots=w.SLOTS,split=True);second=f.data['attempts'][0]['bundles'][1]
    f.store[str(Path(second['path']).resolve())]+=b'corrupt';reader=f.reader()
    with pytest.raises(w.ExtractionError,match='bytes/hash'):w.build(f.data,reader)
    assert reader.progress['containers_loaded']==1 and reader.progress['completed_calls']==6
    assert len(reader.partial_attempts[0]['calls'])==6 and len(reader.progress['attempted_containers'])==2


def test_native_bf16_both_arm_witnesses():
    result=Fixture(prefix=4,dtype=w.torch_cpu().bfloat16).run()
    assert [len(a['calls']) for a in result['attempts']]==[1,11]
    assert all(c['input_dtype']==c['output_dtype']=='torch.bfloat16' for a in result['attempts'] for c in a['calls'])
