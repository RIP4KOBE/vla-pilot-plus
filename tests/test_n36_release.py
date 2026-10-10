"""Public release DAG with synthetic deployment leaves, no usable runtime release.

The actual frozen protocol/accounting references are read only. Synthetic source,
runtime, controller and task leaves are explicitly mocked; source mechanics are
covered separately by pinned dependency tests.
"""
import copy
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import qd_ed_n36_release as release, qd_ed_n36_contract as c, qd_ed_n36_bridge as b
from scripts import qd_ed_n36_worker as worker
from scripts import qd_ed_n23_worker as w
from test_n36_composition import write

PROTOCOL={'path':'/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001147/protocol-preparation/protocol-v1.json',
          'sha256':c.PROTOCOL_SHA}


@pytest.fixture
def boundary(tmp_path,monkeypatch):
    from test_n36_build import synthetic_build
    native_build=synthetic_build(tmp_path/'build')
    calls=[]
    protocol_review={'path':'/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001151/protocol-root-review-v1.json','sha256':c.PROTOCOL_REVIEW_SHA}
    protocol=w.read_ref(PROTOCOL)
    assert protocol['episodes']==c.expected_rows()
    source_path=tmp_path/'synthetic.py';source_path.write_text('# synthetic only\n')
    source={'commit':'a'*40,'files':[{'path':'synthetic.py','sha256':w.sha(source_path)}]}
    runtime={'schema':'qd-ed-runtime-setup-v1','worktree':str(b.ROOT),'artifact_root':str(tmp_path),
        'files':[],'tasks':{},'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU_UUID,'egl_device_index':4},
        'cuda_egl_verified':True,'provider_ready':True,'stage_recovered_error_condition':release.r.E2_STAGE_CONDITION,
        'frozen_stage_provider':{'backend':'codex_cli'}}
    runtime_ref=write(tmp_path/'runtime.json',runtime)
    authority={'schema':'n36-budget-authority-v1','approved':True,'cohort':c.COHORT,'limits':c.LIMITS,
        'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':c.DEADLINE,
        'caps':copy.deepcopy(c.CAPS),'automatic_recoveries':0,'protocol':PROTOCOL,'accounting':protocol['accounting'],
        'weekly_window':{'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.,'ends_at':c.DEADLINE},
        'approval_basis':write(tmp_path/'basis.json',{'synthetic_only':True})}
    plan={'native_build':native_build,'protocol_review':protocol_review,'schema':'n36-released-plan-v1','frozen':True,'release_enabled':True,'worktree':str(b.ROOT),
        'artifact_root':str(tmp_path/'artifacts'),'episodes':c.expected_rows(),'limits':copy.deepcopy(c.LIMITS),
        'worker_contract':c.WORKER_CONTRACT,'deadline':c.DEADLINE,'stop_path':c.stop_path(), 'stop_authority':c.stop.binding(),
        'phase_authorization':{'dev':True,'validation':False,'formal':False},'attempt_identity':'episode_key',
        'source':source,'scientific_source':copy.deepcopy(source),'runtime':runtime_ref,
        'runtime_closure':write(tmp_path/'closure.json',{'synthetic_only':True}),
        'controller_semantics':write(tmp_path/'controller.json',{'synthetic_only':True}),
        'protocol':PROTOCOL,'authority':write(tmp_path/'authority.json',authority),
        'expected_manifests':{row['episode_key']:write(tmp_path/(row['episode_key']+'.json'),{'row':row,'argv':['python','synthetic-main']}) for row in c.expected_rows()}}
    def source_check(plan):
        calls.append('source');w.require(plan['source']==plan['scientific_source'] and w.sha(source_path)==source['files'][0]['sha256'],'synthetic source changed')
    def checked(name,fn):
        def check(*args,**kwargs):calls.append(name);return fn(*args,**kwargs)
        return check
    monkeypatch.setattr(b,'verify_sources',source_check)
    monkeypatch.setattr(b,'attest_loaded',checked('loaded',lambda *args:{}))
    monkeypatch.setattr(b,'source_paths',lambda *args:{'synthetic.py'})
    monkeypatch.setattr(b.closure,'verify_runtime',checked('runtime',lambda doc,ref:doc))
    monkeypatch.setattr(worker.controller,'verify_semantics',checked('controller',lambda ref,*args:w.read_ref(ref)))
    monkeypatch.setattr(release.r,'stage_overrides',checked('provider',lambda *args:[]))
    monkeypatch.setattr(release.r,'verify_files',checked('files',lambda *args,**kwargs:None))
    monkeypatch.setattr(release.r,'validate_runtime_inputs',checked('inputs',lambda *args:None))
    def manifest(ref,plan,runtime,row):
        doc=w.read_ref(ref);w.require(doc['row']==row,'manifest row');return doc
    monkeypatch.setattr(b,'_verify_manifest_bound',checked('manifest',manifest))
    return SimpleNamespace(plan=plan,root=tmp_path,source_path=source_path,calls=calls,authority=authority)


def freeze(f):
    ref=write(f.root/'plan.json',f.plan)
    expected={'schema':'n36-execution-release-v1','approved':True,'plan':ref,
        **({k:f.plan[k] for k in ('cohort','accounting')} if f.plan.get('cohort')==c.RECOVERY_COHORT else {}),
        **{k:f.plan[k] for k in ('native_build','authority','protocol','protocol_review','source','scientific_source','runtime_closure','controller_semantics','runtime','limits','phase_authorization')}}
    review=write(f.root/'review.json',{**expected,'schema':'n36-root-production-review-v1','decision':'APPROVED'})
    return ref,write(f.root/'release.json',{**expected,'root_review':review})


def test_public_release_binds_all40_and_worker_context(boundary):
    f=boundary;plan_ref,release_ref=freeze(f)
    plan,runtime,authority=release.validate_release(plan_ref,release_ref)
    assert f.calls.count('manifest')==40
    assert {'source','loaded','runtime','controller','provider','files','inputs'}<=set(f.calls)
    row=plan['episodes'][3]
    context=worker.context_for(plan_ref,row,release_ref)
    assert context['worker_contract']==c.WORKER_CONTRACT
    cref=write(f.root/'context.json',context)
    assert worker.validate_context(cref)[3]==row


@pytest.mark.parametrize('fault',['draft','phase','recovery','protocol_hash','source','source_bytes','runtime_hash','manifest_hash','weekly_origin','absolute_cap','native_build'])
def test_detached_release_cannot_reauthorize_different_science(boundary,fault):
    f=boundary
    if fault=='draft':f.plan.update(schema='n36-release-draft-v1',release_enabled=False)
    elif fault=='phase':f.plan['phase_authorization']['validation']=True
    elif fault=='recovery':f.plan['limits']['automatic_recoveries']=1
    elif fault=='protocol_hash':f.plan['protocol']={**PROTOCOL,'sha256':'0'*64}
    elif fault=='source':f.plan['scientific_source']['commit']='b'*40
    elif fault=='source_bytes':f.source_path.write_text('# altered\n')
    elif fault=='runtime_hash':f.plan['runtime']['sha256']='0'*64
    elif fault=='manifest_hash':next(iter(f.plan['expected_manifests'].values()))['sha256']='0'*64
    elif fault=='weekly_origin':f.authority['weekly_window']['origin_gpu_hours']+=1
    elif fault=='native_build':f.plan['native_build']['sha256']='0'*64
    elif fault=='absolute_cap':f.authority['caps']['gpu_hours']+=1
    f.plan['authority']=write(f.root/'authority.json',f.authority)
    refs=freeze(f)
    with pytest.raises((ValueError,KeyError)):release.validate_release(*refs)


def test_cpu_authority_never_confers_execution_release():
    with pytest.raises(ValueError):c.require_release({'approved':True,'release_enabled':True})
    with pytest.raises(ValueError):release.validate_release(PROTOCOL,PROTOCOL)
