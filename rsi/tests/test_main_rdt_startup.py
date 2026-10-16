import sys
import json
from pathlib import Path
from types import SimpleNamespace

from omegaconf import OmegaConf
import torch


def test_mode_gate_expansion_branch_saves_terminal_video():
    source = (Path(__file__).resolve().parents[2] / "rsi/main.py").read_text()

    assert "Mode gate: REQUEST_EXPANSION" in source
    assert "episode_{episode + 1}_mode_gate_expansion" in source
    assert "self.video_recorder.save_video" in source


def test_optional_local_tokenizer_is_forwarded_as_processor_override():
    source = (Path(__file__).resolve().parents[2] / "rsi/main.py").read_text()

    assert 'type_config.get("tokenizer_path", None)' in source
    assert 'preprocessor_overrides["tokenizer_processor"]' in source


def test_mode_gate_context_uses_current_vlm_stage_description():
    source = (Path(__file__).resolve().parents[2] / "rsi/main.py").read_text()

    assert 'line.lower().startswith(f"stage {current_stage}:")' in source
    assert "task_stage=stage_label" in source


def test_enabled_stage_recognizer_advances_guidance_and_resets_reward():
    from rsi import main
    import numpy as np

    calls = []
    resets = []

    def identify(**kwargs):
        calls.append(kwargs)
        return 2, True

    runner = main.Main.__new__(main.Main)
    runner.config = OmegaConf.create({'use_guidance': True,
        'use_vlm_stage_recognition': True, 'vlm_query_limit': 50})
    runner.policy = SimpleNamespace(get_normalized_reward=lambda: 0.9,
        reset_stage=lambda: resets.append(True))
    runner.adapter = SimpleNamespace(get_vlm_image=lambda: np.zeros((8, 8, 3), np.uint8),
        get_task_description=lambda: 'switch stove on and put moka pot on it')
    runner.gemini_stage_recognizer = SimpleNamespace(identify_stage_and_guidance=identify)
    runner.guidance_fns = {1: [object()], 2: [object()], 3: [object()]}
    runner.stage_descriptions = 'Stage 1: stove on\nStage 2: grasp pot\nStage 3: place pot'
    runner.init_img_with_keypoints = None
    runner.keypoint_id_to_object = {}
    state = {'current_stage': 1, 'use_guidance': True, 'prev_norm_reward': 0.5,
        'prev_gripper_open': None, 'vlm_query_count': 0}
    updated = runner._update_stage(state, None, 0.8, 0.6)
    assert updated['current_stage'] == 2 and updated['use_guidance'] is True
    assert updated['prev_norm_reward'] == 0.0 and updated['vlm_query_count'] == 1
    assert calls[0]['num_stages'] == 3
    assert len(calls) == len(resets) == 1


def test_init_components_skips_vlm_when_guidance_disabled(monkeypatch, tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from rsi import main
    def _raise_if_vlm_constructed(*args, **kwargs):
        raise AssertionError("VLMAgent should not be constructed when guidance is disabled")

    monkeypatch.setattr(main, "VLMAgent", _raise_if_vlm_constructed)

    runner = main.Main.__new__(main.Main)
    runner.config = OmegaConf.create(
        {
            "use_guidance": False,
            "output_dir": str(tmp_path),
            "cached_functions_dir": None,
            "use_vlm_stage_recognition": False,
        }
    )
    runner.output_dir = str(tmp_path)
    runner.backend = "libero"
    runner.adapter = object()

    runner._init_components(OmegaConf.create({"perception": {}}))

    assert runner.vlm_agent is None
    assert runner.keypoint_detector is None
    assert runner.video_recorder is not None


def test_account_grounding_and_stage_start_without_google_credentials(monkeypatch, tmp_path):
    from rsi import main
    from mode_gate.planner_account import CodexPlannerClient

    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "MODE_GATE_GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(main, "KeypointDetector", lambda **kwargs: object())
    monkeypatch.setattr(main, "KeypointTracker", lambda adapter: object())
    monkeypatch.setattr(main, "VLMAgent", lambda **kwargs: object())
    monkeypatch.setattr(main, "TrajectoryVideoRecorder", lambda **kwargs: object())
    original_create = main.create_gemini_grounder
    seen = []

    def account_grounder(config):
        seen.append(config)
        assert "api_key" not in config
        return original_create(config)

    monkeypatch.setattr(main, "create_gemini_grounder", account_grounder)
    runner = main.Main.__new__(main.Main)
    runner.config = OmegaConf.create({"use_guidance": True, "use_vlm_stage_recognition": True})
    runner.output_dir, runner.backend, runner.adapter = str(tmp_path), "libero", object()
    runner._init_components(OmegaConf.create({"perception": {
        "keypoint_detector": {}, "vlm_agent": {},
        "gemini_grounding": {"enabled": True, "api_key": "unused-legacy-placeholder"},
        "gemini": {"model": "gpt-6-astra", "thinking_level": "ultra"},
    }}))
    assert seen and runner.use_gemini
    assert isinstance(runner.gemini_grounder.client, CodexPlannerClient)
    assert isinstance(runner.gemini_stage_recognizer.client, CodexPlannerClient)


def test_visualization_action_chunk_prefers_policy_candidates():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from rsi import main
    fallback = torch.zeros(1, 3, 7)
    candidates = torch.arange(2 * 3 * 7, dtype=torch.float32).reshape(2, 3, 7)

    class Policy:
        def get_last_visualization_action_candidates(self):
            return candidates

    class Adapter:
        def env_postprocessor(self, transition):
            return {"action": transition["action"] + 1.0}

    visualized = main._get_visualization_action_chunk(Policy(), Adapter(), fallback)

    torch.testing.assert_close(visualized, candidates + 1.0)


def test_active_bootstrap_theta0_skips_redundant_episode_boundary_reload(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from rsi import main
    checkpoint = tmp_path / "theta0"
    checkpoint.mkdir()
    registry_root = tmp_path / "registry"
    (registry_root / "base/theta_0").mkdir(parents=True)
    (registry_root / "attempts").mkdir(parents=True)
    digest = "a" * 64
    (registry_root / "base/theta_0/ref.json").write_text(
        json.dumps(
            {
                "schema_version": "theta0-reference-v1",
                "checkpoint_path": str(checkpoint),
                "checkpoint_digest": digest,
                "metadata": {},
            }
        )
    )
    first = {
        "deployment_revision": 1,
        "policy_id": "policy_000",
        "controller_mode": "fixed_budget_4",
        "verifier_id": None,
        "manifest_hash": "manifest-v1",
        "transaction_id": "tx1",
        "updated_at": "ignored",
    }
    second = {
        **first,
        "deployment_revision": 2,
        "manifest_hash": "manifest-v2",
        "transaction_id": "tx2",
    }
    (registry_root / "attempts/transaction_tx1.json").write_text(
        json.dumps(
            {
                "status": "COMMITTED",
                "reason": "bootstrap_theta0",
                "previous": None,
                "next": first,
            }
        )
    )
    (registry_root / "attempts/transaction_tx2.json").write_text(
        json.dumps(
            {
                "status": "COMMITTED",
                "reason": "promotion",
                "previous": first,
                "next": second,
            }
        )
    )

    assert main._active_deployment_is_loaded_theta0(
        SimpleNamespace(root=registry_root),
        SimpleNamespace(**second),
        base_pretrained_path=str(checkpoint),
        loaded_checkpoint_digest=digest,
    )

    third = {
        **second,
        "deployment_revision": 3,
        "controller_mode": "learned_verifier",
        "verifier_id": "verifier-initializer",
        "transaction_id": "tx3",
    }
    (registry_root / "attempts/transaction_tx3.json").write_text(json.dumps({
        "status": "COMMITTED", "reason": "enable_initializer", "previous": second,
        "next": third,
    }))
    assert main._active_deployment_is_loaded_theta0(
        SimpleNamespace(root=registry_root), SimpleNamespace(**third),
        base_pretrained_path=str(checkpoint), loaded_checkpoint_digest=digest,
    )


def test_active_non_theta0_policy_does_not_skip_reload(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from rsi import main
    checkpoint = tmp_path / "theta0"
    checkpoint.mkdir()
    registry_root = tmp_path / "registry"
    (registry_root / "base/theta_0").mkdir(parents=True)
    (registry_root / "attempts").mkdir(parents=True)
    digest = "b" * 64
    (registry_root / "base/theta_0/ref.json").write_text(
        json.dumps(
            {
                "schema_version": "theta0-reference-v1",
                "checkpoint_path": str(checkpoint),
                "checkpoint_digest": digest,
                "metadata": {},
            }
        )
    )
    active = {
        "deployment_revision": 2,
        "policy_id": "policy_001",
        "controller_mode": "fixed_budget_10",
        "verifier_id": None,
        "manifest_hash": "manifest-v2",
        "transaction_id": "tx2",
        "updated_at": "ignored",
    }
    (registry_root / "attempts/transaction_tx2.json").write_text(
        json.dumps(
            {
                "status": "COMMITTED",
                "reason": "promotion",
                "previous": None,
                "next": active,
            }
        )
    )

    assert not main._active_deployment_is_loaded_theta0(
        SimpleNamespace(root=registry_root),
        SimpleNamespace(**active),
        base_pretrained_path=str(checkpoint),
        loaded_checkpoint_digest=digest,
    )
