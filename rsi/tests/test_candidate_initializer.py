import json
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
from omegaconf import OmegaConf

from scripts import initialize_candidate_verifier as initializer


def test_explicit_main_method_reload_preserves_policy_and_frozen_encoder(tmp_path, monkeypatch):
    import hashlib
    import importlib
    import pytest
    monkeypatch.setattr(initializer, 'REPO', tmp_path)
    source = tmp_path/'rsi/main.py'
    source.parent.mkdir(parents=True)
    source.write_text('# tested compatible method fix')
    class OldMain:
        def version(self): return 'old'
    class PatchedMain:
        def __init__(self): raise AssertionError('must not construct/load a new model')
        def version(self): return 'fixed'
    runner = OldMain()
    policy = runner.policy = object()
    encoder = runner.theta0_scene_encoder = object()
    monkeypatch.setattr(importlib, 'reload', lambda _: SimpleNamespace(Main=PatchedMain))
    monkeypatch.setattr(importlib, 'import_module', lambda _: object())
    with pytest.raises(ValueError, match='digest'):
        initializer.reload_main_in_place(runner, 'wrong')
    assert runner.version() == 'old'
    result = initializer.reload_main_in_place(runner, hashlib.sha256(source.read_bytes()).hexdigest())
    assert runner.version() == 'fixed'
    assert runner.policy is policy and runner.theta0_scene_encoder is encoder
    assert result['weights_reloaded'] is False


def test_rejected_warm_reload_request_does_not_unload_or_exit(tmp_path, monkeypatch):
    (tmp_path/'resume.request').write_text('{"reload_main_sha256":"wrong"}')
    statuses=[]
    def reject(*args): raise ValueError('wrong source digest')
    monkeypatch.setattr(initializer, 'reload_main_in_place', reject)
    def sleep(_): (tmp_path/'resume.request').write_text('resume without code reload')
    monkeypatch.setattr(initializer.time, 'sleep', sleep)
    assert initializer.wait_for_warm_resume(tmp_path, object(), lambda state,**kw: statuses.append(state))
    assert statuses == ['ERROR_WARM','RESUMING_WARM']


def test_initialization_retry_keeps_same_loaded_policy_and_separates_failed_attempt(tmp_path, monkeypatch):
    output=tmp_path/'initialization'; output.mkdir()
    (output/'untrained_head.pt').write_bytes(b'test-placeholder-no-gpu-allocation')
    context={'context_id':'context','task_key':'task','init_state_id':'2'}
    (output/'plan_000.json').write_text(json.dumps({'contexts':[context]}))
    manifest=tmp_path/'manifest.json'; manifest.write_text('{}')
    monkeypatch.setattr('dotenv.load_dotenv',lambda *args,**kwargs:None)
    monkeypatch.setattr('mode_gate.campaign.demonstration_bank',lambda _:[])
    monkeypatch.setattr('mode_gate.campaign.baseline_steering_profile',
                        lambda:{'policy':{'pretrained_path':str(tmp_path)}})
    active=SimpleNamespace(policy_id='pi05_v44_original',verifier_id='new-head')
    monkeypatch.setattr('mode_gate.registry.PolicyRegistry',lambda _:SimpleNamespace(active=lambda:active))
    monkeypatch.setattr('mode_gate.verifier_refresh.VerifierRefreshCoordinator',
        lambda **kwargs:SimpleNamespace(run=lambda **kw:{'refreshed':True}))
    monkeypatch.setattr(initializer,'initialization_settings',lambda:{
        'task_keys':['task','second-task'], 'auto_start_formal':False})
    # All graphics/offline flags are restored after the test.
    for key in ('PYOPENGL_PLATFORM','MUJOCO_GL','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE',
                'TOKENIZERS_PARALLELISM','PYTORCH_CUDA_ALLOC_CONF'):
        monkeypatch.setenv(key,'test-original')
    def config(*args):
        return OmegaConf.create({'mode_gate':{},'main':{},'backend':{'libero':{}}})
    monkeypatch.setitem(sys.modules,'run_full_experiment',SimpleNamespace(make_config=config))
    identities=[]; constructions=[]
    class Adapter:
        def __init__(self,*args,**kwargs): pass
        def close(self): pass
    class Main:
        def __init__(self,cfg):
            constructions.append(self)
            self.policy=object(); self.adapter=Adapter(); self.device='cpu'
            self.config=cfg.main
        def run(self):
            identities.append(id(self.policy))
            if len(identities)==1:
                raise RuntimeError('transient provider failure')
            self.success_count=1
    monkeypatch.setitem(sys.modules,'rsi.main',SimpleNamespace(Main=Main))
    def sleep(_):
        status=json.loads((output/'status.json').read_text())
        if status['state']=='ERROR_WARM':
            (output/'resume.request').write_text('operator resumed after repair')
        elif status['state']=='INITIALIZED_WARM':
            (output/'stop.request').write_text('test completed')
        else:
            raise AssertionError(status)
    monkeypatch.setattr(initializer.time,'sleep',sleep)
    initializer.run(SimpleNamespace(root=tmp_path,manifest=manifest,gpu=6))
    assert len(constructions)==1 and identities[0]==identities[1]
    rows=[json.loads(x) for x in (output/'episodes.jsonl').read_text().splitlines()]
    assert len(rows)==1 and rows[0]['native_success'] is True and rows[0]['formal_result'] is False
    assert rows[0]['output_dir'].endswith('/attempt_002')
    assert (output/'rollouts/context/attempt_001/config.json').exists()
    assert (output/'completion.json').exists()


def test_formal_handoff_keeps_same_warm_runner_and_starts_without_schedule(tmp_path,monkeypatch):
    from scripts import run_full_experiment
    active=SimpleNamespace(controller_mode='learned_verifier',verifier_id='head',policy_id='v44')
    registry=SimpleNamespace(active=lambda:active)
    runner=SimpleNamespace(policy=object())
    calls=[]
    monkeypatch.setattr(run_full_experiment,'run',lambda args,**kw:calls.append((args,kw)))
    monkeypatch.setattr(initializer,'initialization_settings',lambda:{'formal_passes':1})
    initializer.start_formal_with_warm_runner(
        SimpleNamespace(root=tmp_path,manifest=tmp_path/'manifest',gpu=6),runner,registry,
        lambda *args,**kwargs:None)
    assert calls[0][1]['warm_runner'] is runner
    assert calls[0][0].gpu_index==6 and calls[0][0].output==tmp_path/'formal_experiment'
    record=json.loads((tmp_path/'initialization/formal_handoff.json').read_text())
    assert record['same_process'] and not record['scheduled_task']


def test_warm_driver_handoff_is_pinned_and_does_not_resume_old_plan(tmp_path,monkeypatch):
    import hashlib,os,pytest
    output=tmp_path/'initialization';output.mkdir()
    manifest=tmp_path/'manifest.json';manifest.write_text('{}')
    request=output/'driver_handoff.request'
    options={'pid':os.getpid(),'driver_sha256':'wrong','manifest':str(manifest)}
    request.write_text(json.dumps(options))
    runner=SimpleNamespace(device='cuda:6',policy=object(),cfg=SimpleNamespace(mode_gate=SimpleNamespace(
        registry_root=str(tmp_path/'registry'),slow_loop_root=str(output/'unused_slow_loop'))))
    with pytest.raises(ValueError,match='hash mismatch'):
        initializer.continue_driver_if_requested(runner)
    assert request.is_file()
    options['driver_sha256']=hashlib.sha256(Path(initializer.__file__).read_bytes()).hexdigest()
    request.write_text(json.dumps(options))
    calls=[]
    monkeypatch.setattr(initializer,'run',lambda args,**kw:calls.append((args,kw)))
    monkeypatch.setattr(initializer,'reload_driver_modules',lambda:None)
    with pytest.raises(SystemExit) as stopped:
        initializer.continue_driver_if_requested(runner)
    assert stopped.value.code==0
    assert calls[0][1]=={'warm_runner':runner,'inherited_lock':True}
    assert not request.exists()
    assert json.loads((output/'driver_handoff.json').read_text())['model_reloaded'] is False


def test_initializer_never_asks_planner_for_a_third_task(monkeypatch):
    from mode_gate import campaign
    tasks=[{'task_key':key,'splits':{'verifier_train':['0','1']}} for key in ('first','second','third')]
    monkeypatch.setattr(campaign,'selected_tasks',lambda _:tasks)
    monkeypatch.setattr(initializer,'initialization_settings',lambda:{'task_keys':['first','second']})
    captured=[]
    def request(**kw):
        captured.append(kw)
        return SimpleNamespace(text=json.dumps({'contexts':[{'task_key':'second','init_state_id':'1'}],
                                                'reason':'independent'}),planner_metadata={})
    plan=initializer.plan_contexts(SimpleNamespace(request=request),{},[])
    assert plan['contexts'][0]['task_key']=='second'
    assert captured[0]['schema']['properties']['contexts']['items']['properties']['task_key']['enum']==['first','second']


def test_initializer_training_scope_rejects_third_task_before_loading_features():
    import pytest
    from mode_gate.verifier_training import build_verifier_examples
    from mode_gate.experiment_contract import FIXED_BUDGET_50_LABEL_VERSION
    memory=SimpleNamespace(experiences=SimpleNamespace(latest_annotations=lambda:{'a':{
        'annotation_id':'a','record_id':'d','use_for_training':True,'label_version':FIXED_BUDGET_50_LABEL_VERSION}}),
        decisions=SimpleNamespace(iter_valid=lambda:iter([{'record_id':'d','provenance':{
            'group':{'suite':'libero_goal','task_id':'third','perturbation_variant':'use_swap'}}}])))
    with pytest.raises(ValueError,match='two-task scope'):
        build_verifier_examples(memory,policy_id='v44',allowed_task_keys=('first','second'),
            request={'train_annotation_ids':['a'],'independent_annotation_ids':[]})


@pytest.mark.parametrize('planner_enabled',[False,True])
def test_formal_phase_rebinds_initializer_controller_without_constructing_policy(tmp_path,monkeypatch,planner_enabled):
    from scripts import run_full_experiment as formal
    from mode_gate.registry import ActiveDeployment
    from mode_gate.config import ModeGateConfig
    output=tmp_path/'formal_experiment'
    manifest=tmp_path/'manifest.json';manifest.write_text('{"manifest_sha256":"hash"}')
    context={'context_id':'context','task_id':'drawer','runtime_suite':'libero_goal_env',
        'perturbation_variant':'use_environment','init_state_id':'0'}
    active=ActiveDeployment(2,'v44','learned_verifier','head','hash','txn','now')
    monkeypatch.setattr(formal,'contexts_from_manifest',lambda *args:[context])
    monkeypatch.setattr('dotenv.load_dotenv',lambda *args,**kw:None)
    monkeypatch.setattr('mode_gate.preflight.source_revision',lambda _: 'test-source')
    monkeypatch.setattr('mode_gate.registry.PolicyRegistry',lambda _:SimpleNamespace(
        root=tmp_path/'registry',active=lambda:active))
    monkeypatch.setattr('mode_gate.verifier.DeployedVerifierPredictor',lambda _:None)
    monkeypatch.setattr('mode_gate.experiment_supervisor.apply_pause_after_slow_loop',lambda **kw:False)
    monkeypatch.setattr('mode_gate.verifier_refresh.VerifierRefreshCoordinator',
        lambda **kw:SimpleNamespace(run=lambda **args:{'refreshed':False}))
    def config(*args):
        return OmegaConf.create({'main':{'use_guidance':True,'use_vlm_stage_recognition':True,
                                        'planner_steering_enabled':planner_enabled},
            'backend':{'libero':{}},'mode_gate':{'enabled':True,'controller_mode':'learned_verifier',
                                               'auto_start_expansion_worker':True}})
    monkeypatch.setattr(formal,'make_config',config)
    class Adapter:
        def __init__(self,*args,**kw): pass
        def close(self): pass
        def get_context_provenance(self): return context
    policy=object();rebound=[]
    runner=SimpleNamespace(adapter=Adapter(),device='cuda:6',policy=policy,success_count=1,
        gemini_stage_recognizer=object() if planner_enabled else None,
        mode_gate_incidents=object(),mode_gate_config=ModeGateConfig())
    runner._init_mode_gate=lambda:rebound.append(runner.mode_gate_config)
    runner.run=lambda:(output/'stop.request').write_text('one test context completed')
    # Restore graphics/offline variables modified by the driver after this test.
    for key in ('PYOPENGL_PLATFORM','MUJOCO_GL','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE',
                'TOKENIZERS_PARALLELISM','PYTORCH_CUDA_ALLOC_CONF'):
        monkeypatch.setenv(key,'test-original')
    formal.run(SimpleNamespace(root=tmp_path,output=output,manifest=manifest,passes=1,gpu_index=6),
               warm_runner=runner)
    assert len(rebound)==1 and rebound[0].auto_start_expansion_worker
    assert rebound[0].controller_mode=='learned_verifier' and runner.policy is policy
    episode=json.loads((output/'episodes.jsonl').read_text().splitlines()[0])
    assert episode['event']=='EPISODE_COMPLETED' and episode['success'] is True
