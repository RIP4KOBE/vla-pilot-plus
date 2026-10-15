import copy
import json
from pathlib import Path
import pytest
from bounded_metadata_v1 import Reader,MetadataError,MAX_FILE,MAX_TOTAL
from terminal_reader_v1 import reconstruct,summary,check_projection_freshness
from synthetic_fixtures_v1 import Fixture

def review(f):return reconstruct(f.data,Reader(f.files))
def replace(f,role,mutate):
    value=copy.deepcopy(f.values[f.refs[role]['path']]);mutate(value)
    f.put(role,value);return value
@pytest.mark.parametrize('n,candidate,control,decision',[(40,5,2,'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'),
 (40,5,6,'REJECT'),(24,0,1,'REJECT_NUMERIC_FUTILITY'),(28,1,1,'REJECT_NUMERIC_FUTILITY'),
 (0,0,0,'INVALID_OR_INTERRUPTED'),(3,0,0,'INVALID_OR_INTERRUPTED')])
def test_dispositions(tmp_path,n,candidate,control,decision):
    f=Fixture(tmp_path,n,candidate,control);r=review(f)
    assert r['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION',r['discrepancies']
    assert r['cohort_disposition']==decision
    assert r['accepted_cells']==n
    assert r['all_episode_gpu_process_seconds']==2*n
    assert r['tensor_resource_gpu_process_seconds']==2.
    assert r['validation_authorized'] is r['next_gpu_execution_authorized'] is False

def test_full_recovery_costs(tmp_path):
    f=Fixture(tmp_path,recovery=True);r=review(f)
    assert r['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION',r['discrepancies']
    assert len(r['all_attempts'])==41 and r['accepted_cells']==40
    assert r['all_episode_gpu_process_seconds']==280
    assert r['unknown_token_calls']==1 and not r['all_attempt_token_usage_complete']
    assert r['all_attempt_costs']['C0']['provider_input_tokens']['observed_total']==330

def test_native_zero_guided_absence(tmp_path):
    f=Fixture(tmp_path,zero=True);r=review(f)
    assert r['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION',r['discrepancies']
    assert r['cohort_disposition']=='REJECT'
    assert r['native']['N26']['witness_calls_verified']==0

def test_invalid_last_missing_audit_retains_cost(tmp_path):
    f=Fixture(tmp_path,n=18,candidate=1,invalid=True);r=review(f)
    assert r['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION',r['discrepancies']
    assert r['cohort_disposition']=='INVALID_OR_INTERRUPTED' and r['accepted_cells']==18
    assert len(r['all_attempts'])==19 and len(r['expected_processes'])==21

def test_metadata_never_follows_receipt_tensors(tmp_path):
    f=Fixture(tmp_path,n=4);reader=Reader(f.files);r=reconstruct(f.data,reader)
    assert r['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION'
    assert not any('decision_evidence' in x for x in reader.cache)

@pytest.mark.parametrize('role', ['plan','source','runtime','precheck','proof','proof_report','controller','release'])
def test_input_role_spoofing(tmp_path,role):
    f=Fixture(tmp_path,n=0)
    row=next(x for x in f.files if x['path']==f.refs[role]['path']);row['role']='metrics'
    with pytest.raises(MetadataError):review(f)

def test_duplicate_attempt_ids(tmp_path):
    f=Fixture(tmp_path,n=1);f.bindings.append(copy.deepcopy(f.bindings[0]))
    with pytest.raises(MetadataError,match='duplicate attempt'):review(f)

def test_late_current_matching_event(tmp_path):
    f=Fixture(tmp_path,n=0)
    replace(f,'current_journal',lambda v:(v['events'].append({'event':'reserved'}),v.update(event_count=1)))
    with pytest.raises(MetadataError,match='later/missing'):review(f)

def test_missing_result_no_repair(tmp_path):
    f=Fixture(tmp_path,n=4);p=Path(f.refs['result']['path']);p.unlink()
    e=next(x for x in f.files if x['role']=='result');e.update(present=False,sha256=None,bytes=0);f.refs['result']['sha256']=None
    r=review(f);assert r['decision']=='REJECT_TERMINAL_RECONSTRUCTION'
    assert 'missing_immutable_result' in r['discrepancies'] and not p.exists()

def test_observed_unknown_counts_not_zero_imputed():
    attempts=[{'attempt_id':'a','profile':'C0','terminal':{'gpu_process_wall_seconds':7.,'provider_logical_call_attempts':7,'provider_usage_complete_calls':1}},
              {'attempt_id':'b','profile':'C0','terminal':{'gpu_process_wall_seconds':3.}}]
    r=summary([],attempts)
    assert r['unknown_token_calls'] is None and r['known_unknown_token_calls']==6
    assert r['unmeasured_token_call_attempts']==['b']
    assert r['all_attempt_costs']['C0']['score_batches']['missing_attempts']==['a','b']

@pytest.mark.parametrize('role', ['metrics','receipt','audit'])
def test_typed_payload_path_denied(tmp_path,role):
    record={'role':role,'path':str(tmp_path/'forbidden.pt'),'present':True,'sha256':'a'*64,'bytes':1}
    with pytest.raises(MetadataError,match='forbidden'):Reader([record])

def test_inventory_caps_before_open(tmp_path):
    record={'role':'plan','path':str(tmp_path/'does-not-exist.json'),'present':True,'sha256':'a'*64,'bytes':MAX_FILE+1}
    with pytest.raises(MetadataError,match='size'):Reader([record])
    records=[{**record,'path':str(tmp_path/f'{i}.json'),'bytes':MAX_FILE} for i in range(9)]
    with pytest.raises(MetadataError,match='total'):Reader(records)

def test_absent_file_mutated_present(tmp_path):
    f=Fixture(tmp_path,n=0);path=tmp_path/'missing.json';reference=f.absent('receipt',path)
    r=Reader(f.files);path.write_text('{}')
    with pytest.raises(MetadataError,match='absence changed'):r.get(reference,'receipt')

def test_disposition_status_mismatch_never_promotes(tmp_path):
    f=Fixture(tmp_path)
    old=copy.deepcopy(f.values[f.refs['status']['path']]);old['status']='failed'
    f.put('status',old)
    result=copy.deepcopy(f.values[f.refs['result']['path']]);result['terminal_status']={**f.refs['status'],'content':old}
    f.put('result',result)
    r=review(f)
    assert r['cohort_disposition']=='INVALID_OR_INTERRUPTED' and r['decision']=='REJECT_TERMINAL_RECONSTRUCTION'

@pytest.mark.parametrize('recoveries,allowed', [([0,1],True),([0,1,2],False)])
def test_recovery_global_cap(tmp_path,recoveries,allowed):
    f=Fixture(tmp_path,recovery=recoveries)
    if not allowed:
        with pytest.raises(MetadataError,match='duplicate attempt binding|dispatch/recovery cap'):review(f)
    else:
        r=review(f)
        assert r['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION',r['discrepancies']
        assert len(r['all_attempts'])==42 and r['unknown_token_calls']==2
        assert r['all_episode_gpu_process_seconds']==480.

def rebind_attempt(f,index,role,mutate):
    b=f.bindings[index];reference=b['refs'][role];value=copy.deepcopy(f.values[reference['path']]);mutate(value)
    b['refs'][role]=f.put(role,value,reference['path'])
    final=next(x['terminal'] for x in f.attempts if x['attempt_id']==b['attempt_id'])
    if role=='receipt':final['n23_worker_receipt']=b['refs'][role]
    if role=='process':final['process']=value
    if role!='terminal':b['refs']['terminal']=f.put('terminal',final,b['refs']['terminal']['path'])
    f.put('journal',f.events);f.put('current_journal',f.projection('journal',f.events))
    cleanup=copy.deepcopy(f.values[f.refs['cleanup_attestation']['path']]);cleanup['current_journal']=f.refs['current_journal'];f.put('cleanup_attestation',cleanup)
    return value

@pytest.mark.parametrize('field,value', [('source',{}),('main_exit_code',1),('process_unchanged',False),
 ('audit_seconds',3.),('n26_native_counts',{}),('main_argv_sha256','f'*64)])
def test_native_receipt_mismatch(tmp_path,field,value):
    f=Fixture(tmp_path,n=1);rebind_attempt(f,0,'receipt',lambda x:x.update({field:value}))
    with pytest.raises(MetadataError,match='invalid status invented'):
        review(f)

@pytest.mark.parametrize('alter', ['case_missing','source','native_uuid','cost','model_call'])
def test_same_source_36_case_proof_negative(tmp_path,alter):
    f=Fixture(tmp_path,n=0)
    def mutate(q):
        if alter=='case_missing':q['cases'].pop()
        if alter=='source':q['source']['commit']='a'*40
        if alter=='native_uuid':q['backend']['actual_uuid']='00000000-0000-0000-0000-000000000000'
        if alter=='cost':q['worker_wall_seconds']=61
        if alter=='model_call':q['model_calls']=1
    reference=f.refs['proof_report'];value=copy.deepcopy(f.values[reference['path']]);mutate(value)
    new=f.put('proof_report',value)
    proof=copy.deepcopy(f.values[f.refs['proof']['path']]);proof['report']=new;f.put('proof',proof)
    # Source review/precheck still bind the immutable old proof: rejection cannot relabel it.
    with pytest.raises(MetadataError):review(f)

def test_missing_recovery_attestation(tmp_path):
    f=Fixture(tmp_path,recovery=True);f.bindings[1].pop('recovery_attestation')
    with pytest.raises(MetadataError,match='later attempted cells'):
        review(f)

def test_generic_repeat_not_typed(tmp_path):
    f=Fixture(tmp_path,recovery=True)
    first=f.attempts[0]['terminal'];first['reason']='TimeoutExpired'
    f.bindings[0]['refs']['terminal']=f.put('terminal',first,f.bindings[0]['refs']['terminal']['path'])
    f.put('journal',f.events);f.put('current_journal',f.projection('journal',f.events))
    with pytest.raises(MetadataError,match='later attempted cells'):
        review(f)

def test_journal_extra_duplicate_terminal(tmp_path):
    f=Fixture(tmp_path,n=1);f.events.append(copy.deepcopy(f.events[-1]))
    f.put('journal',f.events);f.put('current_journal',f.projection('journal',f.events))
    with pytest.raises(MetadataError,match='chronology'):review(f)

def test_omitted_attempt(tmp_path):
    f=Fixture(tmp_path,n=1);f.bindings.clear()
    with pytest.raises(MetadataError,match='unlisted attempt'):review(f)

def test_result_native_counter_not_trusted(tmp_path):
    f=Fixture(tmp_path,n=4)
    replace(f,'result',lambda q:q['native']['N26'].update(parent_rounds_verified=999))
    r=review(f);assert r['decision']=='REJECT_TERMINAL_RECONSTRUCTION'
    assert 'native' in r['discrepancies'] and r['native']['N26']['parent_rounds_verified']==10

def test_provider_mode_omission_preserved(tmp_path):
    f=Fixture(tmp_path,n=2)
    assert all('qd_quality_mode' not in f.values[b['refs']['metrics']['path']][0] for b in f.bindings)
    assert review(f)['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION'

def test_wrong_projection_scope_denied(tmp_path):
    f=Fixture(tmp_path,n=0);replace(f,'current_journal',lambda q:q.update(cohort_id='protected'))
    with pytest.raises(MetadataError,match='subset projection'):review(f)

def test_static_source_shape_not_accepted_from_old_n25(tmp_path):
    f=Fixture(tmp_path,n=0);replace(f,'source',lambda q:q.update(commit='5a65ef15968cc68c82314e8c0773b3365ad45fa0'))
    with pytest.raises(MetadataError,match='original315'):review(f)

def test_full_private_ledger_not_allowed_even_json_role(tmp_path):
    with pytest.raises(MetadataError,match='forbidden'):
        Reader([{'role':'journal','path':str(tmp_path/'attempt-ledger.jsonl'),'present':True,'sha256':'a'*64,'bytes':2}])

def test_preallocation_stat_limit(tmp_path,monkeypatch):
    import stat
    from bounded_metadata_v1 import load_bound
    p=tmp_path/'huge.json';p.write_text('{}')
    class S:
        st_size=MAX_FILE+1
        st_mode=stat.S_IFREG
    original=Path.stat
    monkeypatch.setattr(Path,'stat',lambda self,*a,**kw:S() if self==p else original(self,*a,**kw))
    called=[]
    monkeypatch.setattr(Path,'open',lambda *a,**kw:called.append(True))
    with pytest.raises(MetadataError,match='per-file bound'):load_bound(p)
    assert called==[]

def test_freshness_anchor_is_per_collection(tmp_path):
    from terminal_reader_v1 import check_fresh_stat
    p=tmp_path/'private.jsonl';p.write_text('[]');st=p.stat()
    projection={'source_ledger':{'path':str(p),'sha256':'a'*64},'source_ledger_stat':{'size':st.st_size,'mtime_ns':st.st_mtime_ns,'inode':st.st_ino}}
    check_fresh_stat([projection]);p.write_text('[1]')
    with pytest.raises(MetadataError,match='refresh'):check_fresh_stat([projection])
    st=p.stat();projection['source_ledger_stat']={'size':st.st_size,'mtime_ns':st.st_mtime_ns,'inode':st.st_ino}
    check_fresh_stat([projection])  # No forever-pinned full-ledger digest requirement.

def test_cleanup_known_process_and_orphan_group(tmp_path,monkeypatch):
    import terminal_reader_v1 as tr
    proc=tmp_path/'proc';(proc/'sys/kernel/random').mkdir(parents=True);(proc/'sys/kernel/random/boot_id').write_text('boot')
    real=Path
    monkeypatch.setattr(tr,'Path',lambda x:proc/str(x)[6:] if str(x).startswith('/proc/') else proc if str(x)=='/proc' else real(x))
    processes={'controller':{'pid':80,'proc_start_ticks':'10','boot_id':'boot'},'worker':{'pid':90,'proc_start_ticks':'11','boot_id':'boot'}}
    r=tr.inspect_cleanup(processes,tmp_path/'W');assert not r['signals_sent']
    orphan=proc/'91';orphan.mkdir()
    fields=['S','1','90','90']+['0']*15+['12']
    (orphan/'stat').write_text('91 (worker) '+' '.join(fields));(orphan/'cmdline').write_bytes(b'python')
    with pytest.raises(MetadataError,match='descendant'):tr.inspect_cleanup(processes,tmp_path/'W')



def refresh_events(f):
    f.put('journal',f.events);f.put('current_journal',f.projection('journal',f.events))
    c=copy.deepcopy(f.values[f.refs['cleanup_attestation']['path']])
    c.update(current_journal=f.refs['current_journal'],expected_processes=f.processes);f.put('cleanup_attestation',c)

@pytest.mark.parametrize('order',[(1,0,2,3),(0,2,1,3),(0,1,3,2)])
def test_cross_cell_group_reordering_rejected(tmp_path,order):
    f=Fixture(tmp_path,n=4)
    groups=[f.events[i:i+3] for i in range(0,12,3)]
    f.events[:]=[e for i in order for e in groups[i]]
    f.bindings[:]=[f.bindings[i] for i in order]
    # Make temporal order plausible so this tests the independent cell-order gate.
    for i,e in enumerate(f.events):e['time_unix']=float(i)
    refresh_events(f)
    with pytest.raises(MetadataError,match='global cell order'):review(f)

def test_cross_attempt_time_overlap_rejected(tmp_path):
    f=Fixture(tmp_path,n=2);f.events[3]['time_unix']=1.5;refresh_events(f)
    with pytest.raises(MetadataError,match='cross-attempt timestamp'):review(f)

@pytest.mark.parametrize('n',[25,28,40])
def test_no_dispatch_after_earliest_futility(tmp_path,n):
    f=Fixture(tmp_path,n=n,candidate=0);refresh_events(f)
    with pytest.raises(MetadataError,match='after first complete-quad'):review(f)

def test_actual_last_quad_futility_writer_conflict_stays_invalid(tmp_path):
    # Four early wins make futility first occur at cell40, never earlier.
    f=Fixture(tmp_path,candidate=4)
    s=copy.deepcopy(f.values[f.refs['status']['path']]);s['status']='rejected_numeric_futility';f.put('status',s)
    result=copy.deepcopy(f.values[f.refs['result']['path']])
    result.update(decision='INVALID_OR_INTERRUPTED',journal_reconstructed_disposition='REJECT',
                  terminal_status={**f.refs['status'],'content':s})
    result['controller_evidence'].update(consistent=False,status_phase=s['status'],
        disagreement='Controller status and independently reconstructed journal differ; no resume or promotion.')
    f.put('result',result)
    r=review(f)
    assert r['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION',r['discrepancies']
    assert r['cohort_disposition']=='INVALID_OR_INTERRUPTED' and r['accepted_cells']==40

def test_valid_journal_before_status_persistence_retains_cost(tmp_path):
    f=Fixture(tmp_path,n=4)
    s=copy.deepcopy(f.values[f.refs['status']['path']]);s['completed_keys'].pop();s['attempts']=s['attempts'][:-1]
    f.put('status',s)
    result=copy.deepcopy(f.values[f.refs['result']['path']]);result.update(journal_reconstructed_disposition='INVALID_OR_INTERRUPTED',
         terminal_status={**f.refs['status'],'content':s})
    result['controller_evidence'].update(completed_keys=s['completed_keys'],consistent=False,
         disagreement='Controller status and independently reconstructed journal differ; no resume or promotion.')
    f.put('result',result)
    r=review(f)
    assert r['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION',r['discrepancies']
    assert len(r['status_attempts_not_returned'])==1 and r['all_episode_gpu_process_seconds']==8.
    assert r['cohort_disposition']=='INVALID_OR_INTERRUPTED'

def make_absent(f,b,role):
    old=b['refs'][role];p=Path(old['path']);p.unlink()
    row=next(x for x in f.files if x['path']==str(p));row.update(present=False,sha256=None,bytes=0)
    b['refs'][role]={'path':str(p),'sha256':None}

def test_reserved_then_aborted_without_process_cost_is_not_fabricated(tmp_path):
    f=Fixture(tmp_path,n=1,invalid=True);b=f.bindings[-1];final=f.attempts[-1]['terminal']
    base=f.events[-3].copy()
    final.clear();final.update(base,event='aborted',outcome_valid=False,reason='prelaunch admission failed',
        time_unix=5.,gpu_process_wall_seconds=0.,n26_episode_dispatched=False)
    f.events[-2:]=[final]
    for role in ('compute','metrics','context','command','process','audit_start'):
        make_absent(f,b,role)
    f.processes[b['attempt_id']]=None
    b['refs']['terminal']=f.put('terminal',final,b['refs']['terminal']['path']);refresh_events(f);f.finish()
    result=copy.deepcopy(f.values[f.refs['result']['path']]);result['dispatched']=1;f.put('result',result)
    r=review(f)
    assert r['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION',r['discrepancies']
    assert r['expected_processes'][b['attempt_id']] is None
    assert r['unknown_token_calls'] is None and r['all_episode_gpu_process_seconds']==2.
    assert b['attempt_id'] in r['all_attempt_costs']['Q0']['score_batches']['missing_attempts']

def test_unsettled_reservation_never_gets_zero_cost_or_acceptance(tmp_path):
    f=Fixture(tmp_path,n=1,invalid=True);b=f.bindings[-1]
    f.events[-2:]=[];make_absent(f,b,'terminal');refresh_events(f)
    r=review(f)
    assert r['decision']=='REJECT_TERMINAL_RECONSTRUCTION' and r['unsettled_gpu_costs']=='Unknown'
    assert r['unsettled_attempts']==[b['attempt_id']] and len(r['all_attempts'])==1

def test_missing_pid_cleanup_remains_unknown(tmp_path,monkeypatch):
    import terminal_reader_v1 as tr
    proc=tmp_path/'proc';(proc/'sys/kernel/random').mkdir(parents=True);(proc/'sys/kernel/random/boot_id').write_text('boot')
    real=Path
    monkeypatch.setattr(tr,'Path',lambda x:proc/str(x)[6:] if str(x).startswith('/proc/') else proc if str(x)=='/proc' else real(x))
    r=tr.inspect_cleanup({'worker':None},tmp_path/'W')
    assert r['observations']['worker']['same_identity_alive'] is None
    assert r['observations']['worker']['owned_descendants'] is None
    assert r['unknown_process_identities']==['worker'] and not r['downstream_cleanup_gate_satisfied']

def cli_fixture(tmp_path):
    import terminal_reader_v1 as tr
    from bounded_metadata_v1 import ref
    f=Fixture(tmp_path,n=4)
    for item in f.source['files']:
        path=f.source_root/item['path'];path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(('source '+item['path']).encode())
    h=Path(tr.__file__).parent
    f.data['static_objects']=[ref(h/name) for name in ('terminal_reader_v1.py','bounded_metadata_v1.py','metadata_semantics_v1.py')]+[f.static_ref]
    output=tmp_path/'variants/n26_clean_output_rbf/root-terminal-review-v1.json'
    (output.parent/'execution').mkdir(parents=True);(output.parent/'execution/supervisor.lock').write_text('')
    (f.source_root/'data').mkdir();(f.source_root/'data/qd-ed-runner.lock').write_text('')
    manifest=tmp_path/'approved-synthetic-input.json';manifest.write_text(json.dumps(f.data))
    return f,manifest,output

def test_root_cli_composition_and_immutable_output(tmp_path,monkeypatch):
    import terminal_reader_v1 as tr
    f,manifest,output=cli_fixture(tmp_path)
    calls=[]
    def observed(processes,root):
        calls.append((processes,root))
        return {'schema':'synthetic-cleanup-observation','downstream_cleanup_gate_satisfied':True}
    monkeypatch.setattr(tr,'inspect_cleanup',observed)  # /proc itself has separate synthetic tests.
    result=tr.run_cli(manifest,output)
    assert result['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION' and len(calls)==1
    assert json.loads(output.read_text())==result
    with pytest.raises(MetadataError,match='immutable review'):tr.run_cli(manifest,output)

@pytest.mark.parametrize('fault',['source','output','live'])
def test_root_cli_source_path_live_process_failclosed(tmp_path,monkeypatch,fault):
    import terminal_reader_v1 as tr
    f,manifest,output=cli_fixture(tmp_path)
    if fault=='source':(f.source_root/f.source['files'][0]['path']).write_text('drift')
    if fault=='output':output=tmp_path/'escaped-review.json'
    def alive(*args):raise MetadataError('owned process/descendant still live')
    monkeypatch.setattr(tr,'inspect_cleanup',alive)
    with pytest.raises(MetadataError):tr.run_cli(manifest,output)
    assert not output.exists()
