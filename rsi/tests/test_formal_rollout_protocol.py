from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from mode_gate.config import ModeGateConfig
from mode_gate.state_machine import EpisodeChunkController
from mode_gate.types import ControllerPhase, ControllerRoute, ProgressEvidence


def formal_config():
    return ModeGateConfig(controller_mode='learned_verifier', require_learned_verifier=True,
                          require_complete_rollout_before_expansion=True)


def route(controller, choice):
    controller.state.verification_due = True
    controller.begin_sampling()
    controller.mark_abstracted()
    controller.mark_scored(has_safe_candidate=True)
    return controller.route_scored_batch(verifier_decision=choice)


def test_formal_rejects_fixed_budget_fallback_and_baseline_override():
    formal_config().validate()
    with pytest.raises(ValueError, match='fixed-budget routing'):
        replace(formal_config(), controller_mode='fixed_budget_50').validate()
    with pytest.raises(ValueError, match='fixed-budget routing'):
        replace(formal_config(), baseline_kind='resteer_only').validate()


def test_early_expansion_is_only_proposal_until_native_rollout_completes():
    controller = EpisodeChunkController(formal_config())
    controller.start_episode()
    decision = route(controller, ControllerRoute.EXPAND)
    assert decision.route is ControllerRoute.EXECUTE
    assert decision.reason == 'expansion_deferred_until_complete_rollout'
    assert decision.verifier_called and not decision.label_eligible
    assert controller.state.retry_index == 0 and not controller.state.terminal
    final = controller.observe_chunk(ProgressEvidence('UNKNOWN', False, 0., 'native_terminal'),
                                     terminal_timeout=True)
    assert final.route is ControllerRoute.EXPAND and controller.state.rollout_complete
    assert not final.label_eligible


def test_resteer_cap_is_not_a_quota_or_refilled_for_completion_continuation():
    controller = EpisodeChunkController(formal_config())
    controller.start_episode()
    assert route(controller, ControllerRoute.RESTEER).route is ControllerRoute.RESTEER
    assert controller.state.retry_index == 1
    controller.state.retry_index = 50
    final = route(controller, ControllerRoute.RESTEER)
    assert final.route is ControllerRoute.EXECUTE
    assert final.reason == 'retry_cap_reached_waiting_for_complete_rollout'
    assert controller.state.retry_index == 50 and final.remaining_budget == 0
    assert not final.verifier_called and not final.label_eligible


def test_safety_veto_never_forces_unsafe_completion_or_premature_expansion():
    controller = EpisodeChunkController(formal_config())
    controller.start_episode()
    decision = controller.force_expand('no_safe_candidates')
    assert decision.route is ControllerRoute.ABORT and not decision.label_eligible
    assert not controller.state.rollout_complete


def test_new_attempt_cannot_reuse_a_previous_completed_rollout():
    controller = EpisodeChunkController(formal_config())
    controller.start_episode()
    controller.state.rollout_complete = True
    assert route(controller, ControllerRoute.EXPAND).route is ControllerRoute.EXPAND
    controller.start_episode()
    assert route(controller, ControllerRoute.EXPAND).route is ControllerRoute.EXECUTE


def test_native_success_completes_rollout_without_expansion():
    controller = EpisodeChunkController(formal_config())
    controller.start_episode()
    route(controller, ControllerRoute.EXPAND)
    decision = controller.observe_chunk(ProgressEvidence('native', False, 1., 'predicate', True))
    assert decision.route is ControllerRoute.EXECUTE and decision.reason == 'task_success'
    assert controller.state.rollout_complete and not decision.label_eligible


def test_warm_update_rejects_wrong_process_before_changing_any_model(tmp_path, monkeypatch):
    from omegaconf import OmegaConf
    from mode_gate.formal_protocol import apply_requested_warm_update
    output = tmp_path / 'formal_experiment'
    output.mkdir()
    (output / 'runtime_protocol_update.request.json').write_text(json.dumps({'pid':-1}))
    runner = SimpleNamespace(cfg=OmegaConf.create({'mode_gate': {'registry_root': str(tmp_path/'registry')}}),
                             policy=object())
    original = runner.policy
    with pytest.raises(ValueError, match='process/protocol'):
        apply_requested_warm_update(runner)
    assert runner.policy is original


def test_formal_promotion_cannot_drop_initialized_verifier(tmp_path, monkeypatch):
    from mode_gate import promotion
    installed = []
    registry = SimpleNamespace(active=lambda: SimpleNamespace(controller_mode='learned_verifier'),
                               install_artifact=lambda *args: installed.append(args))
    monkeypatch.setattr(promotion, 'checkpoint_digest', lambda path: 'digest')
    report = {'schema_version':'raw-policy-gate-report-v1', 'decision': {'status':'POLICY_STAGED',
              'winner':{'policy_id':'new','checkpoint_path':str(tmp_path),'checkpoint_digest':'digest','alpha_l':.2}}}
    with pytest.raises(RuntimeError, match='fixed-budget fallback'):
        promotion.deploy_policy_gate(report=report, registry=registry, expected_revision=2)
    assert not installed


def test_complete_rollout_requirement_is_not_fifty_forced_retries():
    controller = EpisodeChunkController(formal_config())
    controller.start_episode()
    for chunk in range(72):
        decision = route(controller, ControllerRoute.EXPAND)
        assert decision.route is ControllerRoute.EXECUTE
        assert controller.state.retry_index == 0
        observed = controller.observe_chunk(ProgressEvidence('same', False, 1., 'predicate'),
                                            terminal_timeout=chunk == 71)
        assert (observed.route is ControllerRoute.EXPAND) == (chunk == 71)


def test_cancelled_early_expansion_is_terminal_without_deployment(tmp_path):
    from mode_gate.slow_loop import SlowLoopState, SlowLoopStore
    from mode_gate.expansion_automation import wait_for_expansion_demonstrations
    store = SlowLoopStore(tmp_path)
    job = store.create(active_policy_id='v44', input_hash='input')
    job = store.advance(job.job_id, expected_state=job.state, next_state=SlowLoopState.LOOKUP_PENDING,
                        input_hash=job.input_hash, output_hash='lookup')
    store.advance(job.job_id, expected_state=job.state, next_state=SlowLoopState.CANCELLED,
                  input_hash=job.input_hash, output_hash='cancelled', metadata={'formal_result':False})
    assert not store.resumable_jobs()
    wait_for_expansion_demonstrations(store=store, job_id=job.job_id, wait_for_completion=True)


def test_requested_warm_update_preserves_all_three_model_objects(tmp_path, monkeypatch):
    import hashlib
    import os
    import sys
    from omegaconf import OmegaConf
    from mode_gate import formal_protocol
    monkeypatch.setattr(formal_protocol, 'REPO', tmp_path)
    hashes = {}
    for name in formal_protocol.REQUIRED_SOURCES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('checked code')
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    output = tmp_path / 'formal_experiment'
    output.mkdir()
    (output / 'runtime_protocol_update.request.json').write_text(json.dumps({
        'pid':os.getpid(), 'schema_version':'formal-rollout-protocol-update-v1',
        'event_id':'migration-test', 'source_sha256':hashes}))
    class Runtime: pass
    class UpdatedRuntime: pass
    runtime = Runtime()
    verifier = runtime.verifier = object()
    runtime.gate = SimpleNamespace()
    cfg = OmegaConf.create({'mode_gate':{'registry_root':str(tmp_path/'registry')}, 'main':{}})
    policy, encoder = object(), object()
    runner = SimpleNamespace(cfg=cfg, policy=policy, theta0_scene_encoder=encoder,
        mode_aware_runtime=runtime, mode_gate_registry=SimpleNamespace(active=lambda:SimpleNamespace(
            controller_mode='learned_verifier')), mode_gate_deployment_manager=SimpleNamespace(),
        _fresh_load_registry_verifier=lambda x:None, _deployment_canary=lambda *x:None,
        output_dir=str(output))
    from mode_gate import config, state_machine
    modules = {'mode_gate.config':config, 'mode_gate.state_machine':state_machine,
               'mode_gate.runtime':SimpleNamespace(CandidateRuntime=UpdatedRuntime),
               'mode_gate.slow_loop':SimpleNamespace(), 'mode_gate.expansion_automation':SimpleNamespace()}
    monkeypatch.setattr(formal_protocol.importlib, 'import_module', lambda name:modules[name])
    monkeypatch.setattr(formal_protocol.importlib, 'reload', lambda module:module)
    result = formal_protocol.apply_requested_warm_update(runner)
    assert runner.policy is policy and runner.theta0_scene_encoder is encoder and runtime.verifier is verifier
    assert runner.mode_gate_config.require_complete_rollout_before_expansion
    assert result['old_labels_modified'] is False
    assert not (output / 'runtime_protocol_update.request.json').exists()


def test_checked_main_role_backport_preserves_instance_and_does_not_run_constructor(tmp_path, monkeypatch):
    import hashlib
    import os
    from omegaconf import OmegaConf
    from rsi import main
    from mode_gate import formal_protocol, campaign
    monkeypatch.setattr(campaign, 'configuration', lambda:{'root':str(tmp_path)})
    source = formal_protocol.REPO / 'rsi/main.py'
    hashes = {name:hashlib.sha256((formal_protocol.REPO/name).read_bytes()).hexdigest()
              for name in formal_protocol.REQUIRED_SOURCES}
    output = tmp_path / 'formal_experiment'
    output.mkdir()
    options = {'schema_version':'formal-rollout-protocol-update-v1','pid':os.getpid(),
               'event_id':'role-test','source_sha256':hashes,'reload_planner_role_methods':True}
    request = output / 'runtime_protocol_update.request.json'
    class ResidentMain:
        def __init__(self): raise AssertionError('must not load models')
    app = ResidentMain.__new__(ResidentMain)
    policy = app.policy = SimpleNamespace(get_normalized_reward=lambda:.9)
    encoder = app.theta0_scene_encoder = object()
    verifier = app.mode_aware_runtime = object()
    adapter = app.adapter = object()
    app.config = OmegaConf.create({'planner_steering_enabled':False,'use_vlm_stage_recognition':True})
    app.gemini_stage_recognizer = object()  # Must never be queried.
    fake_module = SimpleNamespace(**{**vars(main), '__file__':str(source),'Main':ResidentMain})
    monkeypatch.setitem(formal_protocol.sys.modules, 'rsi.main', fake_module)
    request.write_text(json.dumps({**options,'pid':-1}))
    assert formal_protocol.prepare_requested_main_methods() is None
    assert not hasattr(ResidentMain, '_update_stage')
    request.write_text(json.dumps({**options,'source_sha256':{**hashes,'rsi/main.py':'wrong'}}))
    with pytest.raises(ValueError, match='hash mismatch'):
        formal_protocol.prepare_requested_main_methods()
    assert not hasattr(ResidentMain, '_update_stage')
    request.write_text(json.dumps(options))
    result = formal_protocol.prepare_requested_main_methods()
    state = {'prev_norm_reward':0.,'prev_gripper_open':True,'current_stage':1,
             'use_guidance':True,'vlm_query_count':0}
    assert app._update_stage(state,-1.,.8,.6)['use_guidance'] is True
    assert app.policy is policy and app.theta0_scene_encoder is encoder
    assert app.mode_aware_runtime is verifier and app.adapter is adapter
    assert not result['model_constructor_called']
    assert formal_protocol.prepare_requested_main_methods() is None  # idempotent
