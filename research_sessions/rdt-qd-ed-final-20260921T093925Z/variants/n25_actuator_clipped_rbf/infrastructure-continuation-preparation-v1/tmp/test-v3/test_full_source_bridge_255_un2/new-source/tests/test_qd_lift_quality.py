import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from core.qd_lift_quality import LiftAfterCloseContract, close_then_lift_bonus
from core.rdt_libero_action_converter import rdt_action_to_libero_raw
from core.rdt_policy_steer import RDTSteer
from scripts.audit_decision_evidence import AuditFailure, _audit_n18_score
from scripts import qd_ed_final_runner as runner


def fixture(z_end=0.05, close_at=1, distance=0.02):
    xyz = torch.zeros(2, 9, 3)
    xyz[:, :, 0] = distance
    xyz[:, 8, 2] = z_end
    actions = torch.zeros(2, 8, 7)
    actions[:, :, 6] = -1
    if close_at is not None:
        actions[0, close_at - 1, 6] = 1
    return xyz, torch.zeros(1, 3), actions


def test_bonus_first_close_cap_and_inactive_exact_zero():
    xyz, keypoints, actions = fixture(z_end=0.08, close_at=2)
    xyz[0, 2, 2] = 0.01
    actions[0, 5, 6] = 1
    bonus = close_then_lift_bonus(xyz, keypoints, actions, target_index=0)
    assert bonus.tolist() == pytest.approx([0.05 ** 2, 0.0], abs=1e-9)
    xyz[0, 8, 2] = -0.01
    assert torch.equal(close_then_lift_bonus(xyz, keypoints, actions, target_index=0),
                       torch.zeros(2))
    xyz[0, 8, 2] = 0.08
    xyz[:, :, 0] = 0.05
    assert torch.equal(close_then_lift_bonus(xyz, keypoints, actions, target_index=0),
                       torch.zeros(2))


def test_deployed_gripper_binary_and_invalid_inputs():
    latent = torch.zeros(2, 8, 128)
    latent[0, 0, 10] = -0.1
    decoded = rdt_action_to_libero_raw(latent)
    assert decoded[0, 0, 6].item() == -1
    assert decoded[1, 0, 6].item() == 1
    xyz, keypoints, _ = fixture()
    assert close_then_lift_bonus(xyz, keypoints, decoded, target_index=0).shape == (2,)
    with pytest.raises(ValueError):
        close_then_lift_bonus(xyz, keypoints, decoded, target_index=1)
    with pytest.raises(FloatingPointError):
        close_then_lift_bonus(xyz.fill_(float("nan")), keypoints, decoded, target_index=0)


def test_scoring_changes_active_quality_without_new_provider_calls():
    xyz, keypoints, decoded = fixture()
    samples = torch.zeros(2, 64, 128)
    calls = []
    class Dummy:
        _decision_evidence = None
        def _score_particles(self, samples, keypoints, guidance_fns, *, slice_kind, projection_out):
            calls.append("provider")
            projection_out["projected_xyz"] = xyz
            return torch.tensor([-0.002, -0.001])
        def _decode_visualization_action_candidates(self, samples):
            return decoded
    base = SimpleNamespace(target_index=0, identity={"sha": "frozen"}, validate=lambda providers: None)
    costs, info = RDTSteer._eds_score_population_as_cost(
        Dummy(), samples, keypoints=keypoints, guidance_fns=[object()],
        qd_quality_contract=LiftAfterCloseContract(base))
    assert calls == ["provider"]
    assert torch.equal(info["raw_rewards"], torch.tensor([-0.002, -0.001]))
    assert info["lift_bonus"].tolist() == pytest.approx([0.0025, 0.0], abs=1e-9)
    assert costs.argmin().item() == 0
    decoded[:, :, 6] = -1
    costs_zero, info_zero = RDTSteer._eds_score_population_as_cost(
        Dummy(), samples, keypoints=keypoints, guidance_fns=[object()],
        qd_quality_contract=LiftAfterCloseContract(base))
    assert calls == ["provider", "provider"]
    assert torch.equal(costs_zero, -info_zero["raw_rewards"])
    assert torch.equal(info_zero["lift_bonus"], torch.zeros(2))


def test_sha_verified_native_score_link_rejects_tampering():
    xyz, keypoints, _ = fixture()
    latent = torch.zeros(2, 64, 128)
    latent[:, :8, 10] = -1
    latent[0, 0, 10] = 1
    raw = torch.tensor([-0.002, -0.001])
    bonus = torch.stack((torch.tensor(0.05).square(), torch.tensor(0.0)))
    scoring = {"samples": latent, "projected_xyz": xyz, "keypoints": keypoints}
    effective = {"quality_mode": "close_then_lift_v1", "target_index": 0,
                 "provider_identity": {"source_text_sha256": "frozen"},
                 "lift_bonus": bonus, "quality": raw + bonus}
    aggregate = {"aggregate_before_reward_mode": raw}
    assert _audit_n18_score(scoring, effective, aggregate) == 1
    with pytest.raises(AuditFailure, match="n18_raw_plus_bonus_mismatch"):
        _audit_n18_score(scoring, {**effective, "quality": raw}, aggregate)


def test_supervisor_and_runner_share_one_scope(tmp_path):
    plan = {"source_commit": "frozen"}
    episode_key = "n20_dev_t00_c0_20260929"
    support = runner.n20_support()
    with support.supervised_scope(plan, tmp_path, episode_key):
        support.require_scope(plan, tmp_path, runner.__dict__, {"episode_key": episode_key})


def test_full_n20_profile_passes_terminal_and_quality_contracts():
    profile = json.loads((Path(__file__).resolve().parents[1] /
        "configs/qd_ed_final/candidate_n20.json").read_text())["profile"]
    resolved = RDTSteer._resolve_eds_config_with_reference_defaults(None, profile)
    assert resolved.qd_quality_mode == "close_then_lift_v1"
    assert resolved.qd_final_selection_mode == "terminal_grasp_proximity_v1"
    with pytest.raises(ValueError, match="N4 terminal population requires qd_quality_mode"):
        RDTSteer._resolve_eds_config_with_reference_defaults(
            None, {**profile, "qd_quality_mode": "executed_prefix_v1"})
