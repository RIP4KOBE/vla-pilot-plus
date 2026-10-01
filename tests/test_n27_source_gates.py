"""Synthetic closed metadata/source/authority gates; no actual predecessor reads."""
import copy,hashlib,json
from pathlib import Path
import pytest
from scripts import qd_ed_n27_contract as c,qd_ed_n27_bridge as b,qd_ed_n23_worker as w,qd_ed_final_runner as r
from scripts import qd_ed_n27_backend as backend
from test_n27_controller import write

@pytest.fixture
def closed(tmp_path):
    folder=tmp_path/'experiments/qd_ed_n27';folder.mkdir(parents=True)
    source={'commit':b.BASE,'files':[{'path':str(i),'sha256':'a'*64} for i in range(315)],'sha256':'s'}
    plan={'source_commit':b.BASE,'code_files':source['files']}
    result={'source_commit':b.BASE,'audited_cells':24,'decision':'REJECT_NUMERIC_FUTILITY','dev_gate_promoted':False,'controller_evidence':{'consistent':True}}
    refs={'source':write(tmp_path/'source.json',source),'plan':write(tmp_path/'plan.json',plan),'result':write(tmp_path/'result.json',result),
          'budget':write(tmp_path/'budget.json',{'schema':'n26-finite-budget-authority-v1','caps':c.BASE_CAPS})}
    review={'schema':'n26-root-terminal-review-v1','decision':'ACCEPT_TERMINAL_RECONSTRUCTION','cohort_disposition':'REJECT_NUMERIC_FUTILITY',
            'accepted_cells':24,'source':refs['source'],'plan':refs['plan'],'result':refs['result'],'cleanup':{'downstream_cleanup_gate_satisfied':True}}
    refs['review']=write(tmp_path/'review.json',review)
    write(folder/'accepted-n26-source-v1.json',source);write(folder/'accepted-predecessor-refs-v1.json',refs)
    return tmp_path,refs

@pytest.mark.parametrize('fault',['none','invalid','promotion','missing_cleanup','source','result_ref','changed_bytes','oversize','symlink'])
def test_exact_closed_predecessor_no_nested_follows(closed,fault):
    root,refs=closed
    if fault in {'invalid','promotion','missing_cleanup','source','result_ref'}:
        review=json.loads(Path(refs['review']['path']).read_text())
        if fault=='invalid':review['cohort_disposition']='INVALID_OR_INTERRUPTED'
        if fault=='promotion':review['cohort_disposition']='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'
        if fault=='missing_cleanup':review['cleanup']={}
        if fault=='source':review['source']={'path':'/FORBIDDEN','sha256':'x'}
        if fault=='result_ref':review['result']=refs['plan']
        refs['review']=write(Path(refs['review']['path']),review)
        write(root/'experiments/qd_ed_n27/accepted-predecessor-refs-v1.json',refs)
    if fault=='changed_bytes':Path(refs['result']['path']).write_text('{}')
    if fault=='oversize':
        with Path(refs['result']['path']).open('wb') as f:f.truncate(b.MAX_FILE+1)
    if fault=='symlink':
        p=Path(refs['result']['path']);copy_path=root/'copy.json';copy_path.write_bytes(p.read_bytes());p.unlink();p.symlink_to(copy_path)
    if fault=='none':assert b.closed_records(root)['source']['commit']==b.BASE
    else:
        with pytest.raises(ValueError):b.closed_records(root)


def test_byte_bridge_all315_and_phase_a_frozen(monkeypatch):
    root=r.ROOT
    source={'files':[{'path':p,'sha256':w.sha(root/p)} for p in sorted(b.source_paths(root))]}
    value=b.reverse_source(root,source)
    assert value['unchanged_original_files']==312 and value['changed_existing']==list(b.CHANGED)
    bad=copy.deepcopy(source);next(v for v in bad['files'] if v['path']=='core/rdt_policy_steer.py')['sha256']='0'*64
    with pytest.raises(ValueError):b.reverse_source(root,bad)


def test_missing_authority_proof_review_are_closed(tmp_path,monkeypatch):
    for name in ('BUDGET_REUSE','AUTHORITY','FINAL_REVIEW','BACKEND_PROOF'):monkeypatch.setattr(c,name,tmp_path/name)
    for fn,args in ((c.budget_reuse,()),(c.authority,({}, {},tmp_path)),(backend.verify_proof,({'path':str(c.BACKEND_PROOF),'sha256':'a'*64},{},{},tmp_path))):
        with pytest.raises((OSError,ValueError,KeyError)):fn(*args)


def test_no_old_proof_recursion_static():
    text=(r.ROOT/'scripts/qd_ed_n27_bridge.py').read_text()
    assert 'qd_ed_n26_bridge' not in text and 'settled_control_proofs' not in text and 'subprocess' not in text
    source=(r.ROOT/'scripts/qd_ed_n27_backend.py').read_text()
    assert 'settled_control_proofs' not in source and 'qd_ed_n26_backend' not in source


@pytest.mark.parametrize('fault',['none','reuse_missing','old_authority','caps','bucket','hours','protected','hold','resource','gpu'])
def test_finite_reuse_state_gate_no_new_budget(tmp_path,monkeypatch,fault):
    for name in ('BUDGET_AUTHORITY','BUDGET_REUSE'):
        path=tmp_path/name;write(path,{});monkeypatch.setattr(c,name,path)
    calls=[];monkeypatch.setattr(c,'budget_reuse',lambda:calls.append('reuse'))
    old={'caps':c.BASE_CAPS,'amendment':'existing-finite'};monkeypatch.setattr(c,'budget_authority',lambda:old)
    state={'n26_budget_authority':c.ref(c.BUDGET_AUTHORITY),'n27_budget_reuse_authority':c.ref(c.BUDGET_REUSE),
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},'max_concurrent_gpu_workers':1,'gpu_pool':[7],
        'budget':{'gpu_hour_reservations':copy.deepcopy(c.BASE_CAPS['protected_gpu_hours']), 'max_episode_attempts':522,'max_gpu_hours':100.,
            'reserved':copy.deepcopy(c.BASE_CAPS['buckets']),'amendment':'existing-finite'}}
    if fault=='reuse_missing':state.pop('n27_budget_reuse_authority')
    if fault=='old_authority':state['n26_budget_authority']={}
    if fault=='caps':state['budget']['max_episode_attempts']=523
    if fault=='bucket':state['budget']['reserved']['development']+=1
    if fault=='hours':state['budget']['max_gpu_hours']=101
    if fault=='protected':state['budget']['gpu_hour_reservations']['validation']=31
    if fault=='hold':state['external_resource_hold']={'do_not_auto_resume':True}
    if fault=='resource':state['resource_isolation']['private_budget']=False
    if fault=='gpu':state['gpu_pool']=[3]
    if fault=='none':c.require_budget_state(state,vars(r));assert calls==['reuse']
    else:
        with pytest.raises(ValueError):c.require_budget_state(state,vars(r))
