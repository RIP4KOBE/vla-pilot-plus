"""Bounded synthetic source/history/adoption; no actual predecessor/proof reads."""
import copy,json,hashlib
from pathlib import Path
import pytest
from scripts import qd_ed_n28_bridge as bridge,qd_ed_n28_contract as c,qd_ed_n23_worker as w,qd_ed_final_runner as r
from test_n28_metering import write

@pytest.mark.parametrize('fault',['none','changed_byte','extra_delta','duplicate','reversal'])
def test_exact_reverse_source_bytes(tmp_path,monkeypatch,fault):
    names=bridge.CHANGED|{'core/unchanged.py'};old={'commit':bridge.BASE,'files':[]};new={'commit':'new','files':[]}
    patch={'base_commit':bridge.BASE,'files':{}}
    for name in sorted(names):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True)
        before=b'old\n';after=b'new\n' if name in bridge.CHANGED else before;path.write_bytes(after)
        old['files'].append({'path':name,'sha256':hashlib.sha256(before).hexdigest()});new['files'].append({'path':name,'sha256':w.sha(path)})
        if name in bridge.CHANGED:patch['files'][name]={'new_sha256':w.sha(path),'old_sha256':hashlib.sha256(before).hexdigest(),'hunks':[{'start':0,'end':1,'new':['new\n'],'old':['old\n']}]}
    write(tmp_path/bridge.DOC/'base-source-v1.json',old)
    if fault=='changed_byte':(tmp_path/'core/rdt_policy_steer.py').write_text('drift')
    if fault=='extra_delta':(tmp_path/'core/unchanged.py').write_text('new');new['files'][-1]['sha256']='wrong'
    if fault=='duplicate':new['files'].append(new['files'][0])
    if fault=='reversal':next(iter(patch['files'].values()))['hunks'][0]['old']=['wrong\n']
    write(tmp_path/bridge.DOC/'reverse-source-v1.json',patch);monkeypatch.setattr(bridge,'source_paths',lambda _:names)
    if fault=='none':assert bridge.reverse_source(tmp_path,new)==old
    else:
        with pytest.raises(ValueError):bridge.reverse_source(tmp_path,new)

@pytest.mark.parametrize('fault',['none','invalid_boolean','count','proof','source','runtime','hash'])
def test_four_bounded_historical_metadata_roles(tmp_path,fault):
    runtime={'path':'/synthetic/runtime','sha256':'r'};source={'commit':bridge.BASE,'files':[]}
    old={'commit':'095cfeecd6af55477d2529441c307ab712e8a8da','files':[]}
    plan={'source_commit':old['commit'],'code_files':[],'runtime_manifest_path':runtime['path'],'runtime_manifest_sha256':runtime['sha256']}
    proof={'schema':'n27-metered-tensor-proof-v1','accepted':True,'source':old,'runtime':runtime}
    if fault=='proof':proof['accepted']=False
    refs={'plan':write(tmp_path/'plan.json',plan),'proof':write(tmp_path/'proof.json',proof)}
    sourcebridge={'schema':'n27-hydra-source-bridge-v1','new_source':source,'reverse_exact':True,'historical_backend_proof':refs['proof'],'runtime':runtime}
    if fault=='source':sourcebridge['new_source']={**source,'commit':'other'}
    if fault=='runtime':sourcebridge['runtime']={'path':'wrong','sha256':'wrong'}
    refs['bridge']=write(tmp_path/'bridge.json',sourcebridge)
    review={'schema':'n27-hydra-root-terminal-review-v1','decision':'ACCEPT_TERMINAL_RECONSTRUCTION','cohort_disposition':'REJECT_SCREEN',
       'new_valid_cells':13,'imported_valid_cells':3,'all_dispatched_attempts':17,'controller_and_all_16_accepted_workers_exited':True,
       'original_invalid_retained':'rdt-qd-ed-final-20260921T093925Z__n27_screen_t00_n27_20261001__1af7d45d9a10',
       'counts':{a:{'audited':4,'success':0} for a in ('C0','Q0','N26','N27')}}
    if fault=='invalid_boolean':review['original_invalid_retained']=True
    if fault=='count':review['all_dispatched_attempts']=16
    refs['review']=write(tmp_path/'review.json',review)
    if fault=='hash':refs['review']['sha256']='0'*64
    write(tmp_path/bridge.DOC/'accepted-history-refs-v1.json',refs);write(tmp_path/bridge.DOC/'base-source-v1.json',source)
    if fault=='none':assert set(bridge.closed_records(tmp_path))=={'review','plan','bridge','proof'}
    else:
        with pytest.raises(ValueError):bridge.closed_records(tmp_path)

@pytest.mark.parametrize('fault',['none','missing','oldcaps','reserve','hold','gpu','amendment'])
def test_root_finite_budget_adoption(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(c,'BUDGET_AUTHORITY',tmp_path/'budget.json');write(c.BUDGET_AUTHORITY,{})
    budget={'caps':c.BASE_CAPS,'amendment':{'n28':True}};monkeypatch.setattr(c,'budget_authority',lambda:budget)
    state={'n28_budget_authority':c.ref(c.BUDGET_AUTHORITY),'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},
      'gpu_pool':[7],'max_concurrent_gpu_workers':1,'budget':{'max_episode_attempts':538,'max_gpu_hours':100.,
      'reserved':copy.deepcopy(c.BASE_CAPS['buckets']),'gpu_hour_reservations':copy.deepcopy(c.BASE_CAPS['protected_gpu_hours']),'amendment':{'n28':True}}}
    if fault=='missing':state.pop('n28_budget_authority')
    if fault=='oldcaps':state['budget']['max_episode_attempts']=522
    if fault=='reserve':state['budget']['gpu_hour_reservations']['formal']=0
    if fault=='hold':state['external_resource_hold']={'do_not_auto_resume':True}
    if fault=='gpu':state['gpu_pool']=[3]
    if fault=='amendment':state['budget']['amendment']={}
    if fault=='none':c.require_budget_state(state,vars(r))
    else:
        with pytest.raises(ValueError):c.require_budget_state(state,vars(r))
