"""Local Git and fake OSC objects test fail-closed plumbing, not deployment."""
import copy
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import pytest
from scripts import qd_ed_n34_source as source, qd_ed_n34_controller as controller
from scripts import qd_ed_n23_worker as w
from test_n32_submodule_freeze import repo, git, commit, RDT


def test_pinned_closure_roundtrip_and_foreign_model(repo, monkeypatch):
    root,path,_,pin,other=repo
    paths=source.rdt_paths(root)
    assert paths=={RDT} and pin!=other
    record=source.source_record(root,paths|{'file.py'})
    source.verify_source(root,record)
    model=SimpleNamespace(__file__=str(path))
    monkeypatch.setattr(source,'sys',SimpleNamespace(modules={'scripts.maniskill_model':model,'models.rdt':model}))
    loaded=source.attest_loaded(root,record)
    assert set(loaded)=={'scripts.maniskill_model','models.rdt'}
    source.sys.modules['models.rdt']=SimpleNamespace(__file__=str(root.parent/'other/model.py'))
    with pytest.raises(ValueError,match='adjacent'):source.attest_loaded(root,record)


@pytest.mark.parametrize('fault',['missing','bytes','hash','pin','link','database','omit'])
def test_source_closure_rejects(repo,fault):
    root,path,database,pin,other=repo
    record=source.source_record(root,{RDT,'file.py'})
    if fault=='missing':path.unlink()
    elif fault=='bytes':path.write_text('wrong')
    elif fault=='hash':record['files'][0]['sha256']='0'*64
    elif fault=='pin':
        git(root,'update-index','--cacheinfo','160000,'+other+',third_party/rdt');commit(root)
    elif fault=='link':path.unlink();path.symlink_to(root/'file.py')
    elif fault=='database':database.rename(database.with_name('absent'))
    elif fault=='omit':record['files'].pop()
    with pytest.raises(ValueError):source.verify_source(root,record)


def write(path,value):
    path.write_text(json.dumps(value));return {'path':str(path),'sha256':w.sha(path)}


@pytest.fixture
def proof(tmp_path,monkeypatch):
    runtime={'path':str(tmp_path/'runtime.json'),'sha256':'a'*64}
    code=tmp_path/'osc.py';code.write_text('# synthetic controller source, not deployed\n')
    record={'path':str(code),'sha256':w.sha(code)}
    module=ModuleType('robosuite.controllers.osc');module.__file__=str(code)
    monkeypatch.setitem(sys.modules,module.__name__,module)
    values=dict(control_delta=True,control_ori=True,control_dim=6,impedance_mode='fixed',
                input_min=[-1]*6,input_max=[1]*6,output_min=[-.05]*3+[-.5]*3,output_max=[.05]*3+[.5]*3,
                policy_freq=20,uncouple_pos_ori=True,interpolator_pos=None,interpolator_ori=None)
    def init(self):self.__dict__.update(copy.deepcopy(values))
    cls=type('OperationalSpaceController',(),{'__module__':module.__name__,'__init__':init})
    module.OperationalSpaceController=cls
    evidence=write(tmp_path/'review.json',{'kind':'deployed_source_review','runtime':runtime,'fixture_only':False})
    # These fake documents exercise validation only; they are NOT release proof.
    p={'schema':'n34-deployed-controller-semantics-v1','runtime':runtime,'status':'ROOT_REVIEWED',
       'physical_gain_certified':False,'module':module.__name__,'class':cls.__name__,'source':record,'instance':values,
       'semantics':{'translation':'scaled_world_delta','rotation':'scaled_axis_angle_delta',
                    'zero_rotation':'zero_increment_not_absolute_pose','gripper':'minus_open_plus_close',
                    'projector_0_01':'convention_not_measured_gain'},
       'review_evidence':{key:evidence for key in ('set_goal','scale_action','wrapper_and_gripper')}}
    closure={'modules':{module.__name__:record},'required_after':[module.__name__]}
    return p,cls,runtime,closure


def test_actual_instance_observed_without_changing_settings(proof,tmp_path):
    p,cls,rt,cl=proof
    controller.verify_semantics(write(tmp_path/'proof.json',p),rt,cl)
    original=cls.__init__
    with controller.observe_instances(p) as records:
        obj=cls()
        assert obj.control_delta is True
    assert len(records)==1 and cls.__init__ is original
    with pytest.raises(ValueError,match='no deployed'):
        with controller.observe_instances(p):pass
    assert cls.__init__ is original


@pytest.mark.parametrize('fault',['delta','absolute_rotation','scale','frequency','interpolation','source','fixture','runtime'])
def test_wrong_deployed_semantics_rejected(proof,tmp_path,fault):
    p,cls,rt,cl=proof
    if fault=='delta':p['instance']['control_delta']=False
    if fault=='absolute_rotation':p['semantics']['rotation']='absolute'
    if fault=='scale':p['instance']['output_min'][0]=0
    if fault=='frequency':p['instance']['policy_freq']=10
    if fault=='interpolation':p['instance']['interpolator_ori']='linear'
    if fault=='source':p['source']={**p['source'],'sha256':'0'*64}
    if fault=='fixture':p['review_evidence']['set_goal']=write(tmp_path/'fixture.json',{'kind':'deployed_source_review','runtime':rt,'fixture_only':True})
    if fault=='runtime':p['runtime']={}
    with pytest.raises(ValueError):controller.verify_semantics(write(tmp_path/'proof.json',p),rt,cl)


def test_actual_instance_wrong_config_rejected(proof):
    p,cls,_,_=proof
    obj=cls();obj.control_delta=False
    with pytest.raises(ValueError,match='config/delta'):controller.attest_instance(obj,p)


def test_full_external_module_inventory_not_just_known_prefixes(tmp_path,monkeypatch):
    path=tmp_path/'unknown_dependency.py';path.write_text('VALUE=1\n')
    record={'path':str(path),'sha256':w.sha(path)}
    closure={'modules':{'unanticipated_dependency':record},'required_after':['unanticipated_dependency']}
    monkeypatch.setattr(source,'verify_runtime',lambda *a:None)
    monkeypatch.setattr(source,'sys',SimpleNamespace(modules={'unanticipated_dependency':SimpleNamespace(__file__=str(path))}))
    assert source.attest_runtime(closure,{},after=True)==closure['modules']
    with pytest.raises(ValueError,match='not frozen'):source.attest_runtime({'modules':{},'required_after':[]},{})
    path.write_text('VALUE=2\n')
    with pytest.raises(ValueError,match='not frozen'):source.attest_runtime(closure,{})


@pytest.mark.parametrize('fault',['none','runtime','interpreter','source','required','version'])
def test_runtime_closure_verification(tmp_path,monkeypatch,fault):
    path=tmp_path/'runtime_module.py';path.write_text('pass\n')
    runtime={'path':str(tmp_path/'runtime.json'),'sha256':'a'*64}
    closure={'schema':'n34-runtime-source-closure-v1','runtime':runtime,
             'modules':{'deployed.module':{'path':str(path),'sha256':w.sha(path)}},'required_after':['deployed.module'],
             'versions':{k:'fixture' for k in ('python','torch','libero','robosuite','mujoco')},
             'interpreter':{'path':str(Path(sys.executable).resolve()),'sha256':w.sha(Path(sys.executable).resolve()),'version':sys.version},
             'distribution_versions':{k:'fixture' for k in ('torch','numpy','robosuite','mujoco','transformers')}}
    monkeypatch.setattr(source.importlib.metadata,'version',lambda _: 'fixture')
    if fault=='runtime':closure['runtime']={}
    if fault=='interpreter':closure['interpreter']['version']='other'
    if fault=='source':path.write_text('changed\n')
    if fault=='required':closure['required_after']=['unknown.module']
    if fault=='version':closure['distribution_versions']['torch']='other'
    if fault=='none':assert source.verify_runtime(closure,runtime)==closure
    else:
        with pytest.raises(ValueError):source.verify_runtime(closure,runtime)
