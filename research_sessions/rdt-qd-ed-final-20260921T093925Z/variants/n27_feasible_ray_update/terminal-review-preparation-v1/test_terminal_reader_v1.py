import copy
import json
from pathlib import Path
import pytest
import terminal_reader_v1 as t
from bounded_json_v1 import Reader,MetadataError,parse,canonical,MAX_FILE,MAX_TOTAL,MAX_FILES
from synthetic_v1 import fixture,MemoryReader,proc,bare

def get(data,reader,role):return reader.get(data['refs'][role],role)
def test_full_promotion_hand_checked():
    data,reader=fixture();out=t.reconstruct(data,reader)
    assert out['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION'
    assert out['cohort_disposition']=='ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV'
    assert out['counts']=={'C0':{'audited':4,'success':0},'Q0':{'audited':4,'success':0},'N26':{'audited':4,'success':1},'N27':{'audited':4,'success':2}}
    assert out['costs']['all_attempt_costs']['N27']['gpu_process_wall_seconds']=={'observed_total':40.,'observed_attempts':4,'missing_attempts':[]}
    assert out['costs']['matched_comparisons']['N26']=={'denominator':4,'gains':1,'losses':0}
    assert out['proof_seconds']==11 and out['cleanup_complete'] is True and out['dispatch_authorized'] is False
@pytest.mark.parametrize('options,disposition',[
 ({'wins':0,'n26_wins':0},'REJECT_SCREEN'),({'wins':2,'n26_wins':2},'REJECT_SCREEN'),
 ({'zero_guided':True},'REJECT_SCREEN'),({'size':4,'wins':0,'n26_wins':0},'INVALID_OR_INTERRUPTED'),
 ({'size':1,'invalid':True},'INVALID_OR_INTERRUPTED'),({'size':1,'aborted':True},'INVALID_OR_INTERRUPTED'),
 ({'size':0},'INVALID_OR_INTERRUPTED'),({'size':4,'mismatch':True},'INVALID_OR_INTERRUPTED')])
def test_complete_and_partial(options,disposition):
    data,reader=fixture(**options);out=t.reconstruct(data,reader)
    assert out['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION'
    assert out['cohort_disposition']==disposition
    if options.get('invalid'):assert out['costs']['unknown_token_calls']==1 and out['costs']['all_attempt_costs']['C0']['gpu_process_wall_seconds']['observed_total']==10.
    if options.get('aborted'):assert out['dispatched']==0 and out['costs']['unknown_token_calls'] is None

def test_status_lag_retains_valid_cell_and_cost():
    data,reader=fixture(size=1,mismatch=True);out=t.reconstruct(data,reader)
    assert out['accepted_cells']==1 and len(out['attempts'])==1 and out['cohort_disposition']=='INVALID_OR_INTERRUPTED'
    assert not out['controller_consistent']

def test_missing_process_unknown_not_dead():
    data,reader=fixture(size=1,invalid=True,missing_process=True);out=t.reconstruct(data,reader)
    assert out['cleanup_complete'] is False and 'a00' in out['cleanup_unknown']
    get(data,reader,'cleanup')['checks']['a00']['same_identity_alive']=False
    with pytest.raises(MetadataError,match='Unknown'):t.reconstruct(data,reader)

@pytest.mark.parametrize('role,key,value',[
 ('plan','source_commit','wrong'),('plan','frozen',False),('source','commit','wrong'),
 ('precheck','all_prerequisites_passed',False),('precheck','historical_proof_lineage_verified',False),
 ('proof_report','accepted',False),('proof_report','model_calls',1),('proof_terminal','cleanup_complete',False),
 ('release','physical_gpu',3),('authority','local_gpu_hours',22),('cleanup','current_matching_subsets_equal',False),
 ('journal','all_matching_events',False),('resources','all_matching_events',False)])
def test_control_corruption(role,key,value):
    data,reader=fixture(size=1);get(data,reader,role)[key]=value
    with pytest.raises((MetadataError,KeyError)):t.reconstruct(data,reader)

@pytest.mark.parametrize('change',['duplicate_attempt','reorder_cells','time_overlap','missing_source_file','proof_case','proof_rng','wrong_context','missing_audit','missing_gate','cross_gate','cost','wrong_receipt','wrong_result','wrong_status_cost','live_process','extra_reservation'])
def test_specific_semantic_negatives(change):
    data,reader=fixture();events=get(data,reader,'journal')['events'];binding=data['attempts'][3];rr=binding['refs']
    if change=='duplicate_attempt':data['attempts'].append(data['attempts'][0])
    elif change=='reorder_cells':events[:6]=events[3:6]+events[:3]
    elif change=='time_overlap':events[3]['time_unix']=0
    elif change=='missing_source_file':get(data,reader,'source')['files'].pop()
    elif change=='proof_case':get(data,reader,'proof_report')['cases'].pop()
    elif change=='proof_rng':get(data,reader,'proof_report')['cases'][0]['rng_scope']='cpu_only'
    elif change=='wrong_context':reader.get(rr['context'],'context')['profile']='N26'
    elif change=='missing_audit':reader.values[('audit',rr['audit']['path'])]=None
    elif change=='missing_gate':reader.get(rr['audit'],'audit').pop('n27_feasible_ray_rbf_audit')
    elif change=='cross_gate':reader.get(rr['audit'],'audit')['n26_clean_output_rbf_audit']={'accepted':True}
    elif change=='cost':reader.get(rr['terminal'],'terminal')['provider_token_usage_complete']=False
    elif change=='wrong_receipt':reader.get(rr['receipt'],'receipt')['main_argv_sha256']='0'*64
    elif change=='wrong_result':get(data,reader,'result')['counts']['N27']['success']=4
    elif change=='wrong_status_cost':get(data,reader,'status')['all_attempt_costs']=None
    elif change=='live_process':get(data,reader,'cleanup')['checks']['a00']['same_identity_alive']=True
    elif change=='extra_reservation':events.append(copy.deepcopy(events[0]))
    if change in {'wrong_result','wrong_status_cost'}:assert t.reconstruct(data,reader)['decision']=='REJECT_TERMINAL_RECONSTRUCTION'
    else:
        with pytest.raises((MetadataError,KeyError,TypeError)):t.reconstruct(data,reader)

def test_noneligible_invalid_has_measured_unknown_not_zero():
    data,reader=fixture(size=1,invalid=True);out=t.reconstruct(data,reader)
    assert out['costs']['known_unknown_token_calls']==out['costs']['unknown_token_calls']==1
    final=out['attempts'][0]['terminal'];partial=copy.deepcopy(final);partial.pop('provider_usage_complete_calls')
    totals=t.summary([], [{'attempt_id':'missing','profile':'C0','terminal':partial}])
    assert totals['unknown_token_calls'] is None and totals['unmeasured_token_call_attempts']==['missing']

@pytest.mark.parametrize('blob',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}'])
def test_strict_json(blob):
    with pytest.raises(MetadataError):parse(blob)

def entry(path,obj,role='plan'):
    b=json.dumps(obj,sort_keys=True,separators=(',',':')).encode();path.write_bytes(b)
    return {'role':role,'path':str(path),'sha256':canonical(obj),'bytes':len(b),'present':True}

def test_bounded_reads_hash_absence_and_reuse(tmp_path):
    p=tmp_path/'v.json';e=entry(p,{'x':1});r=Reader([e]);ref={k:e[k] for k in ('path','sha256')}
    assert r.get(ref,'plan')==r.get(ref,'plan')=={'x':1};assert r.bytes==e['bytes'];r.require_consumed()
    p.write_text('{}')
    with pytest.raises(MetadataError):Reader([e]).get(ref,'plan')
    absent={'role':'audit','path':str(tmp_path/'absent.json'),'sha256':None,'present':False,'bytes':0};r=Reader([absent]);ref={k:absent[k] for k in ('path','sha256')}
    assert r.get(ref,'audit') is None
    Path(absent['path']).write_text('{}')
    with pytest.raises(MetadataError):Reader([absent]).get(ref,'audit')

def test_bounded_caps_before_read(tmp_path):
    e={'role':'plan','path':str(tmp_path/'big.json'),'sha256':'a'*64,'present':True,'bytes':MAX_FILE+1}
    with pytest.raises(MetadataError):Reader([e])
    e['bytes']=MAX_FILE
    with pytest.raises(MetadataError):Reader([{**e,'path':str(tmp_path/f'{i}.json')} for i in range(9)])
    with pytest.raises(MetadataError):Reader([{**e,'bytes':0,'path':str(tmp_path/f'{i}.json')} for i in range(MAX_FILES+1)])
    # Sparse physical file verifies pre-allocation stat gate; no 16MiB read.
    with open(e['path'],'wb') as f:f.truncate(MAX_FILE+1)
    with pytest.raises(MetadataError,match='cap'):Reader([e]).get({k:e[k] for k in ('path','sha256')},'plan')

def test_forbidden_and_unlisted_metadata(tmp_path):
    p=tmp_path/'ok.json';e=entry(p,{});r=Reader([e])
    with pytest.raises(MetadataError):r.get({'path':str(tmp_path/'other.json'),'sha256':'a'*64},'plan')
    with pytest.raises(MetadataError):r.require_consumed()
    for path in [tmp_path/'a.pt',tmp_path/'decision_evidence'/'index.json']:
        with pytest.raises(MetadataError):Reader([{**e,'path':str(path)}])

def test_disabled_and_duplicate_physical_path(tmp_path):
    data,rd=fixture();data['root_authorized']=False
    with pytest.raises(MetadataError):t.reconstruct(data,rd)
    e=entry(tmp_path/'v.json',{})
    with pytest.raises(MetadataError):Reader([e,{**e,'role':'audit'}])

@pytest.mark.parametrize('failed',[False,True])
def test_recovery_first_valid_and_all_costs(failed):
    from synthetic_v1 import recovery_fixture
    data,rd=recovery_fixture(failed=failed);out=t.reconstruct(data,rd)
    assert out['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION'
    assert out['accepted_cells']==(0 if failed else 1)
    assert out['costs']['all_attempt_denominators']['C0']==2 and out['costs']['primary_attempt_denominators']['C0']==1
    assert out['costs']['unknown_token_calls']==(2 if failed else 1)
    assert out['costs']['all_attempt_costs']['C0']['gpu_process_wall_seconds']['observed_total']==20.
    assert out['cohort_disposition']=='INVALID_OR_INTERRUPTED'  # Only one of16 cells, never resume.

@pytest.mark.parametrize('change',['generic_fault','many_failures','missing_basis','wrong_source','valid_retry','missing_attestation','wrong_row','failed_unknown_zero'])
def test_recovery_basis_negatives(change):
    from synthetic_v1 import recovery_fixture
    data,rd=recovery_fixture(failed=True,missing_attestation=change=='missing_attestation');b=data['attempts'][1]
    e=rd.get(b['eligibility'],'eligibility');p=rd.get(data['attempts'][0]['refs']['terminal'],'terminal')
    if change=='generic_fault':p['reason']='generic timeout'
    elif change=='many_failures':p['provider_failed_calls']=6
    elif change=='missing_basis':rd.get(b['recovery_attestation'],'recovery_attestation')['root_verified_original_basis']=False
    elif change=='wrong_source':e['source_commit']='wrong'
    elif change=='valid_retry':p['outcome_valid']=True
    elif change=='wrong_row':e['scientific_row']={**e['scientific_row'],'policy_seed':99}
    elif change=='failed_unknown_zero':e['unknown_token_calls']=0
    with pytest.raises((MetadataError,TypeError,AttributeError)):t.reconstruct(data,rd)

def test_disk_materialized_complete_metadata_composition(tmp_path):
    data,mem=fixture(size=1)
    # Recursively serialize the exact synthetic reference DAG, including all hashes.
    bypath={path:(role,obj) for (role,path),obj in mem.values.items()};done={};entries=[]
    def rewrite(x):
        if isinstance(x,dict):
            if set(x)=={'path','sha256'} and x['path'] in bypath:return materialize(x['path'])
            return {k:rewrite(v) for k,v in x.items()}
        if isinstance(x,list):return [rewrite(v) for v in x]
        if isinstance(x,str) and x.startswith('/synthetic'):return str(tmp_path/'synthetic')+x[len('/synthetic'):]
        return x
    def materialize(path):
        if path in done:return done[path]
        role,obj=bypath[path];p=Path(str(tmp_path/'synthetic')+path[len('/synthetic'):]);p.parent.mkdir(parents=True,exist_ok=True)
        value=rewrite(obj)
        if obj is None:e={'role':role,'path':str(p),'sha256':None,'present':False,'bytes':0}
        else:e=entry(p,value,role)
        entries.append(e);done[path]={k:e[k] for k in ('path','sha256')};return done[path]
    live=rewrite(data);live['files']=entries
    # source and evidence canonical hashes are unchanged by path rewrite; snapshot
    # payload digest and original argv digest legitimately change with fixture root.
    # The full disk reader composes bounded I/O for all references; semantic check
    # remains separately covered using original immutable synthetic DAG above.
    r=Reader(entries)
    for e in entries:assert r.get({k:e[k] for k in ('path','sha256')},e['role']) is not None
    r.require_consumed();assert len(entries)==23 and r.bytes<16*1024*1024

def test_three_recoveries_rejected_before_acceptance():
    data,rd=fixture(size=3);journal=get(data,rd,'journal')
    for e in journal['events']:e['retry_of']='unrelated';e['budget_bucket']='recovery'
    journal['snapshot_events_sha256']=canonical(journal['events'])
    with pytest.raises(MetadataError,match='dispatch/recovery cap'):t.reconstruct(data,rd)

def test_nineteen_attempt_bindings_rejected():
    data,rd=fixture();data['attempts']+=[{'attempt_id':f'extra{i}','refs':{}} for i in range(3)]
    with pytest.raises(MetadataError,match='bounded attempts'):t.reconstruct(data,rd)

@pytest.mark.parametrize('mutation',['bridge_commit','bridge_counter','predecessor','budget_ref','source_review_ref'])
def test_historical_bridge_and_authority_chain(mutation):
    data,rd=fixture(size=1)
    if mutation=='bridge_commit':get(data,rd,'bridge')['original_source']['commit']='wrong'
    elif mutation=='bridge_counter':get(data,rd,'bridge')['unchanged_original_files']=315
    elif mutation=='predecessor':get(data,rd,'authority')['predecessor']=bare('/wrong.json')
    elif mutation=='budget_ref':get(data,rd,'plan')['n27_cohort']['budget_reuse']=bare('/wrong.json')
    elif mutation=='source_review_ref':get(data,rd,'authority')['final_review']=bare('/wrong.json')
    with pytest.raises(MetadataError):t.reconstruct(data,rd)

def test_symlink_and_wrong_inode_type_rejected(tmp_path):
    e=entry(tmp_path/'a.json',{})
    link=tmp_path/'b.json';link.symlink_to(tmp_path/'a.json');e={**e,'path':str(link)}
    with pytest.raises(MetadataError,match='symlink'):Reader([e]).get({k:e[k] for k in ('path','sha256')},'plan')

@pytest.mark.parametrize('existing',[False,True])
def test_disabled_cli_never_writes(tmp_path,monkeypatch,existing):
    source=tmp_path/'inventory.json';source.write_text(json.dumps({'schema':'n27-terminal-metadata-input-v1','root_authorized':False,'executable':False,'files':[]}))
    output=tmp_path/'root-terminal-review-v1.json'
    if existing:output.write_text('immutable')
    monkeypatch.setattr('sys.argv',['reader','--inventory',str(source),'--output',str(output)])
    with pytest.raises(MetadataError):t.main()
    assert output.read_text()=='immutable' if existing else not output.exists()

def test_all_zero_rbf_gradients_are_legal_no_activity_veto():
    data,rd=fixture()
    for binding in data['attempts']:
        rr=binding['refs'];receipt=rd.get(rr['receipt'],'receipt');arm=receipt['profile']
        if arm not in ('N26','N27'):continue
        audit=rd.get(rr['audit'],'audit');key='n27_feasible_ray_rbf_audit' if arm=='N27' else 'n26_clean_output_rbf_audit'
        audit[key]['zero_gradient_calls']=19;receipt['n27_native_counts']['zero_gradient_calls']=19
    for role in ('result','status'):
        for arm in ('N26','N27'):get(data,rd,role)['native'][arm]['zero_gradient_calls']=76
    result=t.reconstruct(data,rd)
    assert result['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION' and result['cohort_disposition']=='ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV'

def test_cli_separate_output_binds_all_three_reader_sources(tmp_path,monkeypatch):
    source=tmp_path/'inventory.json';source.write_text(json.dumps({'files':[]}));output=tmp_path/'root-terminal-review-v1.json'
    monkeypatch.setattr('sys.argv',['reader','--inventory',str(source),'--output',str(output)])
    monkeypatch.setattr(t,'reconstruct',lambda *_:{'decision':'synthetic-only','dispatch_authorized':False})
    t.main();result=json.loads(output.read_text())
    assert result['decision']=='synthetic-only' and result['metadata_bytes_read']==0
    own=result['reader_sources'];assert len(own['files'])==3 and own['sha256']==canonical(own['files'])
    assert {Path(x['path']).name for x in own['files']}=={'bounded_json_v1.py','metadata_checks_v1.py','terminal_reader_v1.py'}
