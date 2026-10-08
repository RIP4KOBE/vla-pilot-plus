"""Strict operational delta and fresh composed hashes, using tiny CPU fixtures."""
import hashlib
import json
from pathlib import Path
import subprocess
import pytest
from scripts import qd_ed_n32r3_release as release, qd_ed_n32r3_contract as c
from scripts import qd_ed_n32r3_bridge as b, qd_ed_n23_worker as w
from test_n32r3_continuation import write, dummy_ref


@pytest.mark.parametrize('fault',['none','old_commit','science','shared_audit','foreign_file','missing_inventory','missing_approval','wrong_parent','old_source_digest'])
def test_source_attestation(tmp_path,monkeypatch,fault):
    shared='scripts/qd_ed_final_runner.py';added='scripts/qd_ed_n32r3_contract.py'
    original=subprocess.check_output(['git','show',c.BASE_SOURCE+':'+shared],cwd=c.ROOT)
    shared_hash=w.sha(c.ROOT/shared)
    old={'commit':c.BASE_SOURCE,'files':[{'path':shared,'sha256':hashlib.sha256(original).hexdigest()},
                                     {'path':'core/science.py','sha256':'science'}]}
    new={'commit':'b'*40,'files':[{'path':shared,'sha256':shared_hash},{'path':'core/science.py','sha256':'science'},
                                {'path':added,'sha256':'added'}]}
    changed=[shared,added]
    plan={'worktree':str(c.ROOT),'scientific_source':old,'source':new,
          **{k:dummy_ref(tmp_path,k+'.json') for k in ('parent_plan','parent_release','carry_forward_map','command_candidates')}}
    review={'schema':'n32r3-source-continuity-review-v1','approved':True,
        **{k:plan[k] for k in ('parent_plan','parent_release','carry_forward_map','command_candidates')},
        'scientific_source':old,'operational_source':new,'changed_files':{shared:shared_hash,added:'added'},
        'scientific_changes':[],'audit_changes':[],'shared_routing':[shared]}
    plan['source_continuity']=write(tmp_path/'review.json',review)
    if fault=='old_commit':new['commit']=c.BASE_SOURCE
    if fault=='science':new['files'][1]['sha256']='changed'
    if fault=='shared_audit':new['files'][0]['sha256']='changed'
    if fault=='foreign_file':changed.append('core/another.py')
    if fault=='missing_inventory':new['files'].pop()
    if fault=='missing_approval':Path(plan['source_continuity']['path']).unlink()
    if fault=='wrong_parent':plan['parent_release']=plan['parent_plan']
    if fault=='old_source_digest':new['files'][0]['sha256']=old['files'][0]['sha256']
    monkeypatch.setattr(release.subprocess if hasattr(release,'subprocess') else subprocess,'check_output',lambda *args,**kwargs:('\n'.join(changed)+'\n').encode())
    monkeypatch.setattr(w,'_committed_source',lambda *args:original)
    if fault=='none':release.verify_continuity(plan)
    else:
        with pytest.raises(ValueError):release.verify_continuity(plan)


def test_fresh_config_hashes_and_scientific_source_binding(tmp_path,monkeypatch):
    row=c.expected_rows()[0]
    scientific={'commit':c.BASE_SOURCE,'files':[{'path':'core/'+name,'sha256':'science'} for name in b.RUNTIME_SOURCES]+[{'path':'main.py','sha256':'main'}]}
    plan={'worktree':str(c.ROOT),'episodes':c.expected_rows(),'source':{'commit':'b'*40},'scientific_source':scientific,
          **{k:dummy_ref(tmp_path,k+'.json') for k in ('runtime','parent_plan','parent_release','parent_review','carry_forward_map','command_candidates','source_continuity','preparation_review')}}
    runtime={'tasks':{'4':{'task_id':4,'init_index':0,'init_path':'init','bddl_path':'bddl'}},
             'files':[{'path':'init','sha256':row['init_file_sha256']},{'path':'bddl','sha256':row['bddl_sha256']}]}
    monkeypatch.setattr(b,'command',lambda *args:(['python','main.py','new_run_id'],tmp_path/'new'))
    config={'backend':{'libero':{'max_episode_steps':720}},'policy':{'rdt':{'control_frequency':20,'action_chunk_horizon':8}},'run_id':row['episode_key']}
    resolved={'n32_runtime_binding':{'source_commit':c.BASE_SOURCE,'run_id':row['episode_key'],'task_id':4},'scientific_value':123}
    calls=[]
    def compose(*args):calls.append(args);return config,resolved
    monkeypatch.setattr(b.old,'compose_launch',compose)
    result=b.manifest(plan,runtime,row)
    assert calls and result['source']['commit']=='b'*40
    assert result['expected_runtime']['binding']['source_commit']==c.BASE_SOURCE
    assert result['composed_config_sha256']==w.canonical_sha(config)
    assert result['expected_runtime']['config_sha256']==hashlib.sha256(json.dumps(resolved,sort_keys=True,allow_nan=False).encode()).hexdigest()
    monkeypatch.setattr(w,'verify_source',lambda *args:None)
    monkeypatch.setattr(b,'source_paths',lambda *args:set())
    plan['source']['files']=[]
    plan['runtime']=write(Path(plan['runtime']['path']),runtime)
    result=b.manifest(plan,runtime,row)
    result['composed_config_sha256']='old_digest'
    with pytest.raises(ValueError):b.verify_manifest(write(tmp_path/'manifest.json',result),plan,runtime,row)
