import copy,json
from pathlib import Path
import pytest
from scripts import qd_ed_n30_r1_bridge as b,qd_ed_n23_worker as w
from n30_r1_synthetic import history,write

@pytest.fixture
def bound(tmp_path,monkeypatch):
    h=history();root=tmp_path/'owning';base=tmp_path/'metadata';doc=root/b.DOC;doc.mkdir(parents=True)
    source={'commit':b.OLD_SOURCE,'files':[{'path':f'source{i}.py','sha256':f'{i:064x}'} for i in range(439)]};source['sha256']=w.canonical_sha(source['files'])
    write(doc/'original-source-v1.json',source)
    budget={'schema':'n29-finite-budget-authority-v1','caps':{},'amendment':{},'validation_authorized':False,'formal_authorized':False}
    plan={**h['plan'],'frozen':True,'source_commit':b.OLD_SOURCE,'code_files':source['files'],'runtime_manifest_path':str(base/'runtime.json'),'runtime_manifest_sha256':'c'*64,
        'n30_cohort':{'budget_reuse':write(base/'budget.json',budget)}}
    planref=write(base/'plan.json',plan);monkeypatch.setattr(b,'PLAN_SHA',planref['sha256'])
    for e in h['events']:e['plan_sha256']=planref['sha256']
    cells=[]
    for i,imp in enumerate(h['imports']):
        row=plan['episodes'][i];final=h['events'][i*3+2];cell=copy.deepcopy(imp['cell']);cell.pop('source_commit');cell.pop('inherited')
        context={'source':source,'plan':planref,'attempt_id':cell['attempt_id'],'episode_key':row['episode_key'],'profile':row['profile'],
            'runtime':{'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}}
        ctx=write(base/f'context{i}.json',context)
        audit=write(base/f'audit{i}.json',{'accepted':True,'evidence_complete':True,'n30_executed_progress_audit':{'profile':row['profile']}})
        evidence=[{'path':'/PROHIBITED/do-not-follow/tensor.pt','sha256':'a'*64}]
        receipt={'source':source,'plan':planref,'runtime':context['runtime'],'context':ctx,'attempt_id':cell['attempt_id'],
            'episode_key':row['episode_key'],'profile':row['profile'],'accepted':True,'main_exit_code':0,'process_unchanged':True,'audit_report':audit,
            'evidence':{'files':evidence,'sha256':w.canonical_sha(evidence)},'audit_backend':{'kind':'cpu'},'n30_native_counts':imp['native'],'n30_auxiliary':{}}
        rec=write(base/f'receipt{i}.json',receipt);final['n23_worker_receipt']=rec
        cell.update(worker_context=ctx,audit=audit,worker_receipt=rec,attempt_result=write(base/f'final{i}.json',final));cells.append(cell)
    error=base/'error.txt';error.write_text("_run_episode\nUnboundLocalError: cannot access local variable 'obs' where it is not associated with a value\n")
    bad={'attempt_id':b.FAILED,'episode_key':plan['episodes'][2]['episode_key'],'outcome_valid':False,
        'root_classification':'ENGINEERING_INITIAL_OBSERVATION_UNBOUNDLOCAL','model_forward_calls':0,'guided_chunks':0,'unguided_chunks':0,
        'provider_logical_call_attempts':0,'attempt_result':write(base/'bad.json',h['events'][-1]),'error':{'path':str(error),'sha256':w.sha(error)}}
    review={'schema':'n30-root-terminal-review-v1','decision':'INVALID_OR_INTERRUPTED','source_commit':b.OLD_SOURCE,'source_files_rehashed':439,
        'dispatched':3,'audited_cells':2,'controller_original_process_exited':True,'monitor_original_process_exited':True,'retry_count':0,
        'gpu_preparation_seconds':0,'episode_gpu_seconds_observed':b.OLD_SECONDS,'original_ledger_modified':False,'new_gpu_release':False,
        'source':write(base/'source.json',source),'plan':planref,'result':write(base/'result.json',{'decision':'INVALID_OR_INTERRUPTED','source_commit':b.OLD_SOURCE,
            'audited_cells':2,'dispatched':3,'accepted_cells':cells}), 'terminal_ledger':write(base/'ledger.json',h['events']),
        'worker_original_processes_exited':[{'attempt_id':g[-1]['attempt_id'],'original_process_exited':True} for g in b.group(h['events'])],
        'accepted_cells':cells,'invalid_attempts':[bad]}
    repair={'schema':'n30-root-initial-observation-repair-review-v1','disposition':'ACCEPT_CPU_REPAIR_ONLY','base_commit':b.OLD_SOURCE,
        'commit':b.BASE,'algorithm_changed':False,'old_complete_method_ast_independently_bound':True}
    def seal():
        reviewref=write(base/'review.json',review);repairref=write(base/'repair.json',repair)
        monkeypatch.setattr(b,'REVIEW_SHA',reviewref['sha256']);monkeypatch.setattr(b,'REPAIR_SHA',repairref['sha256'])
        write(doc/'root-cpu-integration-release-v1.json',{'closed_original':reviewref,'repair_review':repairref})
    seal();return root,base,review,seal


def test_metadata_only_prefix_does_not_follow_tensors(bound,monkeypatch):
    root,base,review,seal=bound;reads=[];original=b.Reader.read
    def read(self,ref,**kw):reads.append(ref['path']);return original(self,ref,**kw)
    monkeypatch.setattr(b.Reader,'read',read);h=b.history(root)
    assert len(h['imports'])==2 and h['old_seconds']==b.OLD_SECONDS and len(reads)<32
    assert not any(p.endswith('.pt') for p in reads)
    assert h['imports'][0]['cell']['source_commit']==b.OLD_SOURCE
    b.current_subset(h,h['events']+[{'identity':{'iteration':'unrelated'}}])
    with pytest.raises(ValueError):b.current_subset(h,h['events']+[h['events'][0]])

@pytest.mark.parametrize('fault',['source','success','failure_error','signature','cleanup','receipt','prefix','evidence_digest'])
def test_history_tamper(bound,fault):
    root,base,review,seal=bound
    if fault=='source':review['source_commit']='wrong'
    elif fault=='success':review['accepted_cells'][0]['success']=True
    elif fault=='failure_error':
        p=base/'error.txt';p.write_text('a different exception');review['invalid_attempts'][0]['error']['sha256']=w.sha(p)
    elif fault=='signature':review['invalid_attempts'][0]['guided_chunks']=1
    elif fault=='cleanup':review['worker_original_processes_exited'][0]['original_process_exited']=False
    elif fault=='prefix':review['accepted_cells'].append(review['accepted_cells'][0])
    else:
        p=base/'receipt0.json';obj=json.loads(p.read_text())
        if fault=='receipt':obj['source']['commit']='NEW'
        else:obj['evidence']['sha256']='wrong'
        review['accepted_cells'][0]['worker_receipt']=write(p,obj)
    seal()
    with pytest.raises(ValueError):b.history(root)


def test_reader_stat_bound_before_open_and_hash(tmp_path,monkeypatch):
    p=tmp_path/'large';p.write_bytes(b'x'*20);monkeypatch.setattr(b,'MAX_FILE',10)
    with pytest.raises(ValueError,match='size'):b.Reader().read({'path':str(p),'sha256':'wrong'})
    p.write_bytes(b'{}')
    with pytest.raises(ValueError,match='hash'):b.Reader().read({'path':str(p),'sha256':'wrong'})
    monkeypatch.setattr(b,'MAX_TOTAL',1)
    with pytest.raises(ValueError,match='bound'):b.Reader().read({'path':str(p),'sha256':w.sha(p)})


def test_exact_reverse_byte_bridge_rejects_unlisted_drift(tmp_path,monkeypatch):
    root=tmp_path/'root';files=[];patch={'base_commit':b.BASE,'files':{}}
    for name in sorted(b.CHANGED):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);old=b'old\n';new=b'new\n';p.write_bytes(new)
        import hashlib
        sha=lambda x:hashlib.sha256(x).hexdigest()
        files.append({'path':name,'sha256':sha(old)});patch['files'][name]={'old_sha256':sha(old),'new_sha256':sha(new),'hunks':[{'start':0,'end':1,'old':['old\n'],'new':['new\n']}]}
    immutable=root/'main.py';immutable.write_text('unchanged\n');files.append({'path':'main.py','sha256':w.sha(immutable)})
    write(root/b.DOC/'base-source-v1.json',{'commit':b.BASE,'files':files});write(root/b.DOC/'reverse-source-v1.json',patch)
    source={'files':[{'path':v['path'],'sha256':w.sha(root/v['path'])} for v in files]}
    monkeypatch.setattr(b,'source_paths',lambda _:set(v['path'] for v in files))
    assert b.reverse_source(root,source)['commit']==b.BASE
    immutable.write_text('changed\n');source['files'][-1]['sha256']=w.sha(immutable)
    with pytest.raises(ValueError):b.reverse_source(root,source)
