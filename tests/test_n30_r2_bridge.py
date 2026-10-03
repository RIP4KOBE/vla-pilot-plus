"""Synthetic original+r1 metadata closure, without tensor/ref recursion."""
import copy,json
from pathlib import Path
import pytest
from scripts import qd_ed_n30_r2_bridge as b,qd_ed_n23_worker as w
from n30_r2_synthetic import write
from test_n30_r1_bridge import bound as old_bound

@pytest.fixture
def bound(old_bound,monkeypatch):
    root,base,old_review,old_seal=old_bound;h=b.original.history(root);doc=root/b.DOC
    source={'commit':b.R1_SOURCE,'files':[{'path':f'source{i}.py','sha256':f'{i:064x}'} for i in range(457)]};source['sha256']=w.canonical_sha(source['files'])
    repaired={'commit':b.BASE,'files':[{'path':f'source{i}.py','sha256':f'{i:064x}'} for i in range(463)]};repaired['sha256']=w.canonical_sha(repaired['files'])
    write(doc/'r1-source-v1.json',source);write(doc/'base-source-v1.json',repaired)
    rows=[]
    for i,row in enumerate(h['plan']['episodes'][2:]):
        row=copy.deepcopy(row);row.update(iteration=b.R1,episode_key=row['episode_key'].replace('n30_dev_','n30_r1_dev_'),original_episode_key=row['episode_key'])
        if i==0:row.update(budget_bucket='recovery',retry_of=b.ORIGINAL_FAILED)
        rows.append(row)
    plan={**h['plan'],'source_commit':b.R1_SOURCE,'code_files':source['files'],'episodes':rows}
    pr=write(base/'r1-plan.json',plan);monkeypatch.setattr(b,'R1_PLAN_SHA',pr['sha256']);row=rows[0]
    common={'attempt_id':b.FAILED,'episode_key':row['episode_key'],'identity':{k:row[k] for k in ('split','iteration','profile','task_id','env_seed','policy_seed','init_index')},
        'budget_bucket':'recovery','source_commit':b.R1_SOURCE,'plan_sha256':pr['sha256'],'retry_of':b.ORIGINAL_FAILED}
    final={**common,'event':'valid','outcome_valid':False,'failure_class':'task_failure','gpu_process_wall_seconds':b.R1_SECONDS}
    events=h['events']+[{**common,'event':'reserved'},{**common,'event':'dispatched'},final]
    cells=[x['cell'] for x in h['imports']];ledger=write(base/'r1-ledger.json',events)
    result={'schema':'n30-r1-combined-result-v1','decision':'INVALID_OR_INTERRUPTED','dev_gate_promoted':False,'source_commit':b.R1_SOURCE,
        'new_dispatched':1,'all_dispatched':4,'audited_cells':2,'original_invalid_attempt':b.ORIGINAL_FAILED,'accepted_cells':cells,'plan':pr,'ledger_snapshot':ledger,
        'attempts':[{'terminal':g[-1]} for g in b.group(events)]}
    runtime={k.removeprefix('runtime_manifest_'):plan[k] for k in ('runtime_manifest_path','runtime_manifest_sha256')}
    ctx={'schema':'n23-metered-worker-context-v1','source':source,'plan':pr,'runtime':runtime,'attempt_id':b.FAILED,'episode_key':row['episode_key'],'profile':'N30'}
    ctxref=write(base/'r1-context.json',ctx)
    receipt={'schema':'n23-in-worker-audit-receipt-v1','source':source,'plan':pr,'runtime':runtime,'context':ctxref,
        'attempt_id':b.FAILED,'episode_key':row['episode_key'],'profile':'N30','accepted':False,'main_exit_code':0,'process_unchanged':True,
        'worker_error_type':'ValueError','audit_report':None,'evidence':None}
    bad={'attempt_id':b.FAILED,'retry_of':b.ORIGINAL_FAILED,'outcome_valid':False,'main_exit_code':0,'attempt_result':write(base/'r1-final.json',final),
        'context':ctxref,'receipt':write(base/'r1-receipt.json',receipt)}
    review={'schema':'n30-r1-root-terminal-review-v1','decision':'INVALID_OR_INTERRUPTED','root_classification':'NATIVE_AUDIT_TERMINAL_FEEDBACK_BINDING_FAILURE',
        'scientific_outcome':'Unknown','source_commit':b.R1_SOURCE,'source_files_rehashed':457,'new_dispatched':1,'combined_dispatched':4,'audited_cells':2,
        'controller_original_process_exited':True,'monitor_original_process_exited':True,'worker_original_process_exited':True,
        'new_episode_gpu_seconds':b.R1_SECONDS,'combined_episode_gpu_seconds':b.OLD_SECONDS,'gpu_preparation_seconds':0,'original_ledger_modified':False,
        'original_closure':{'path':b.release_path(h),'sha256':b.original.REVIEW_SHA},'source':write(base/'r1-source.json',source),'plan':pr,
        'result':write(base/'r1-result.json',result),'terminal_ledger':ledger,'accepted_cells':cells,'invalid_attempt':bad}
    repair={'schema':'n30-terminal-feedback-root-cpu-repair-review-v1','disposition':'ACCEPT_CPU_REPAIR_ONLY','source_commit':b.BASE,'base_commit':b.R1_SOURCE,
        'source_files_rehashed':463,'modified_base_files':['scripts/qd_ed_n30_native.py'],'unchanged_base_files':456,
        'whole_file_reverse_independently_verified':True,'original_receipt_stays_invalid':True,'source':write(base/'repair-source.json',repaired)}
    def seal():
        rr=write(base/'r1-review.json',review);repair['closed_gpu_execution']=rr;rep=write(base/'repair-review.json',repair)
        monkeypatch.setattr(b,'R1_REVIEW_SHA',rr['sha256']);monkeypatch.setattr(b,'REPAIR_SHA',rep['sha256'])
        write(doc/'root-cpu-integration-release-v1.json',{'base_source_commit':b.BASE,'closed_r1_execution_review':rr,'accepted_repair_review':rep})
    seal();return root,base,review,repair,seal


def test_four_old_charges_two_controls_and_no_replay(bound,monkeypatch):
    root,base,review,repair,seal=bound;reads=[];read=b.Reader.read
    monkeypatch.setattr(b.Reader,'read',lambda self,ref:(reads.append(ref['path']),read(self,ref))[1])
    h=b.history(root)
    assert len(h['events'])==12 and len(h['imports'])==2 and h['old_seconds']==b.OLD_SECONDS
    assert h['imports'][0]['cell']['source_commit']==b.OLD_SOURCE and h['events'][-1]['source_commit']==b.R1_SOURCE
    assert h['events'][-1]['outcome_valid'] is False and not any(p.endswith(('.pt','.log')) for p in reads)
    b.current_subset(h,h['events']+[{'identity':{'iteration':'later-independent'}}])
    with pytest.raises(ValueError):b.current_subset(h,h['events']+[h['events'][-1]])

@pytest.mark.parametrize('fault',['source','cost','cleanup','accepted_old','accepted_r1','reason','plan','receipt','context','repair_source','repair_scope','mutated_ledger','result_cost'])
def test_r2_history_tamper(bound,fault):
    root,base,review,repair,seal=bound
    if fault=='source':review['source_commit']='new'
    elif fault=='cost':review['new_episode_gpu_seconds']=0
    elif fault=='cleanup':review['worker_original_process_exited']=False
    elif fault=='accepted_old':review['accepted_cells'][0]['source_commit']=b.BASE
    elif fault=='accepted_r1':review['audited_cells']=3
    elif fault=='reason':review['root_classification']='generic invalid'
    elif fault=='plan':review['plan']['sha256']='0'*64
    elif fault=='repair_scope':repair['modified_base_files'].append('main.py')
    else:
        key,path,target={'receipt':('accepted',base/'r1-receipt.json',review['invalid_attempt']),
            'context':('profile',base/'r1-context.json',review['invalid_attempt']),
            'repair_source':('commit',base/'repair-source.json',repair),
            'mutated_ledger':('',base/'r1-ledger.json',review),
            'result_cost':('',base/'r1-result.json',review)}[fault]
        obj=json.loads(path.read_text())
        if fault=='receipt':obj[key]=True;target['receipt']=write(path,obj)
        elif fault=='context':obj[key]='Q0';target['context']=write(path,obj)
        elif fault=='repair_source':obj[key]='other';target['source']=write(path,obj)
        elif fault=='mutated_ledger':obj[-1]['outcome_valid']=True;target['terminal_ledger']=write(path,obj)
        else:obj['attempts'][-1]['terminal']['gpu_process_wall_seconds']=0;target['result']=write(path,obj)
    seal()
    with pytest.raises((ValueError,KeyError)):b.history(root)


def test_bounded_reader_rejects_before_allocation(tmp_path,monkeypatch):
    p=tmp_path/'metadata';p.write_text('{}');ref={'path':str(p),'sha256':w.sha(p)}
    monkeypatch.setattr(b,'MAX_TOTAL',1)
    with pytest.raises(ValueError,match='pre-read'):b.Reader().read(ref)
    monkeypatch.setattr(b,'MAX_TOTAL',10);monkeypatch.setattr(b,'MAX_FILE',1)
    with pytest.raises(ValueError,match='pre-read'):b.Reader().read(ref)


def test_only_two_reverse_routes_and_source_drift(tmp_path,monkeypatch):
    # Exercise the same new reverse implementation with synthetic files, not old Git/data.
    import hashlib
    root=tmp_path/'root';files=[];patch={'base_commit':b.BASE,'files':{}}
    for name in sorted(b.CHANGED):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('new\n')
        old=hashlib.sha256(b'old\n').hexdigest();files.append({'path':name,'sha256':old})
        patch['files'][name]={'old_sha256':old,'new_sha256':w.sha(p),'hunks':[{'start':0,'end':1,'old':['old\n'],'new':['new\n']}]}
    p=root/'scripts/qd_ed_n30_native.py';p.write_text('strict unchanged\n');files.append({'path':str(p.relative_to(root)),'sha256':w.sha(p)})
    write(root/b.DOC/'base-source-v1.json',{'commit':b.BASE,'files':files});write(root/b.DOC/'reverse-source-v1.json',patch)
    source={'files':[{'path':v['path'],'sha256':w.sha(root/v['path'])} for v in files]};monkeypatch.setattr(b,'source_paths',lambda _:set(v['path'] for v in files))
    assert b.reverse_source(root,source)['commit']==b.BASE
    p.write_text('loosened\n');source['files'][-1]['sha256']=w.sha(p)
    with pytest.raises(ValueError):b.reverse_source(root,source)
