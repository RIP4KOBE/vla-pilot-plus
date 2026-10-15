"""N22 CPU contract checks. No environment, GPU, model, or provider service."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from core.qd_lift_quality import (
    HOLD_MODE, LiftAfterCloseContract, close_hold_then_lift_bonus, close_then_lift_bonus,
)
from core.rdt_policy_steer import RDTSteer
from scripts.audit_decision_evidence import AuditFailure, _audit_n18_score, _audit_n22_score
from scripts import qd_ed_final_runner as runner


def inputs(grips, *, distance=.02, final_z=.05):
    xyz = torch.zeros(1, 9, 3)
    xyz[:, :, 0] = distance
    xyz[:, 8, 2] = final_z
    decoded = torch.zeros(1, 8, 7)
    decoded[0, :, 6] = torch.tensor(grips)
    return xyz, torch.zeros(1, 3), decoded


@pytest.mark.parametrize('grips,kept', [
    ([1, -1, -1, -1, -1, -1, -1, -1], False),
    ([1, 1, 1, 1, 1, 1, 1, -1], False),
    ([1, 1, -1, 1, 1, 1, 1, 1], False),
    ([1, 1, 1, 1, 1, 1, 1, 1], True),
    ([-1, -1, 1, 1, 1, 1, 1, 1], True),
    ([-1, -1, -1, -1, -1, -1, -1, -1], False),
])
def test_hold_must_persist_from_first_eligible_close(grips, kept):
    args = inputs(grips)
    old = close_then_lift_bonus(*args, target_index=0)
    new = close_hold_then_lift_bonus(*args, target_index=0)
    assert new.tolist() == pytest.approx([.0025 if kept else 0.], abs=1e-9)
    if kept:
        assert torch.equal(old, new)
    elif 1 in grips:
        assert old.item() > 0


def test_first_eligible_close_ignores_earlier_far_close_and_release():
    xyz, keypoints, decoded = inputs([1, -1, 1, 1, 1, 1, 1, 1])
    xyz[:, 1, 0] = .1  # First close is too far; qualifying contact is action three.
    assert close_hold_then_lift_bonus(xyz, keypoints, decoded, target_index=0).item() == pytest.approx(.0025)


@pytest.mark.parametrize('distance,final_z', [(.05, .05), (.02, 0.), (.02, -.05)])
def test_no_contact_or_lift_has_exact_zero_bonus(distance, final_z):
    args = inputs([1] * 8, distance=distance, final_z=final_z)
    assert torch.equal(close_hold_then_lift_bonus(*args, target_index=0), torch.zeros(1))


@pytest.mark.parametrize('bad', ['projection_shape', 'action_shape', 'keypoint_shape',
                                  'nan_projection', 'inf_keypoint', 'nan_action',
                                  'gripper_nonbinary', 'target'])
def test_new_mode_rejects_invalid_native_inputs(bad):
    xyz, keypoints, decoded = inputs([1] * 8)
    target = 0
    if bad == 'projection_shape': xyz = xyz[:, :8]
    if bad == 'action_shape': decoded = decoded[:, :7]
    if bad == 'keypoint_shape': keypoints = keypoints.reshape(3)
    if bad == 'nan_projection': xyz[0, 1, 0] = float('nan')
    if bad == 'inf_keypoint': keypoints[0, 0] = float('inf')
    if bad == 'nan_action': decoded[0, 0, 0] = float('nan')
    if bad == 'gripper_nonbinary': decoded[0, 0, 6] = 0
    if bad == 'target': target = 1
    with pytest.raises((ValueError, FloatingPointError)):
        close_hold_then_lift_bonus(xyz, keypoints, decoded, target_index=target)


@pytest.mark.parametrize('dtype', [torch.float32, torch.bfloat16])
def test_old_mode_default_remains_bitwise_equivalent(dtype):
    gen = torch.Generator().manual_seed(222)
    xyz = (torch.randn(64, 9, 3, generator=gen) * .025).to(dtype)
    keypoints = torch.zeros(1, 3, dtype=dtype)
    decoded = torch.zeros(64, 8, 7, dtype=dtype)
    decoded[:, :, 6] = torch.where(torch.rand(64, 8, generator=gen) > .5, 1., -1.)
    distance = torch.linalg.vector_norm(xyz[:, 1:].float() - keypoints[0].float(), dim=2)
    eligible = (distance <= .04) & (decoded[:, :, 6] > 0)
    first = eligible.int().argmax(dim=1)
    z = xyz.float()[torch.arange(len(xyz)), first + 1, 2]
    rise = (xyz[:, 8, 2].float() - z).clamp(min=0., max=.05)
    expected = torch.where(eligible.any(dim=1), rise.square(), torch.zeros_like(rise))
    assert torch.equal(close_then_lift_bonus(xyz, keypoints, decoded, target_index=0), expected)


def test_native_auditor_rejects_unfiltered_release_bonus_and_mode_relabel():
    xyz, keypoints, decoded = inputs([1, 1, -1, 1, 1, 1, 1, 1])
    latent = torch.zeros(1, 64, 128)
    latent[0, :8, 10] = decoded[0, :, 6]
    raw = torch.tensor([-.001])
    old_bonus = close_then_lift_bonus(xyz, keypoints, decoded, target_index=0)
    scoring = {'samples': latent, 'projected_xyz': xyz, 'keypoints': keypoints}
    effective = {'quality_mode': HOLD_MODE, 'target_index': 0, 'provider_identity': {},
                 'lift_bonus': torch.zeros_like(raw), 'quality': raw}
    aggregate = {'aggregate_before_reward_mode': raw}
    assert _audit_n22_score(scoring, effective, aggregate) == 0
    with pytest.raises(AuditFailure, match='n22_native_bonus_mismatch'):
        _audit_n22_score(scoring, {**effective, 'quality': raw + old_bonus,
                                  'lift_bonus': old_bonus}, aggregate)
    with pytest.raises(AuditFailure, match='n18_semantic_identity_missing'):
        _audit_n18_score(scoring, effective, aggregate)
    with pytest.raises(AuditFailure, match='n22_semantic_identity_missing'):
        _audit_n22_score(scoring, {**effective, 'quality_mode': 'close_then_lift_v1'}, aggregate)


def test_only_opt_in_profile_field_changes_and_expansion_is_closed():
    root = Path(__file__).resolve().parents[1]
    n21 = json.loads((root / 'configs/qd_ed_final/candidate_n21.json').read_text())
    n22 = json.loads((root / 'configs/qd_ed_final/candidate_n22.json').read_text())
    base = json.loads((root / 'configs/qd_ed_final/baseline_profiles.json').read_text())['profiles']['Q0']
    before = copy.deepcopy(base)
    assert {k for k in n21['profile'] if n21['profile'][k] != n22['profile'][k]} == {'qd_quality_mode'}
    expanded = runner.expand_candidate('N22', n22, base)
    assert expanded['resolved_eds_config']['qd_quality_mode'] == HOLD_MODE
    assert base == before
    resolved = RDTSteer._resolve_eds_config_with_reference_defaults(None, n22['profile'])
    assert resolved.qd_quality_mode == HOLD_MODE
    assert resolved.qd_final_selection_mode == 'terminal_grasp_proximity_v1'
    for key, value in [('qd_descriptor', 'target_relative_endpoint_xy'), ('population_size', 8)]:
        changed = copy.deepcopy(n22); changed['profile'][key] = value
        with pytest.raises(runner.GateError):
            runner.expand_candidate('N22', changed, base)
        with pytest.raises(ValueError):
            RDTSteer._resolve_eds_config_with_reference_defaults(None, changed['profile'])
    with pytest.raises(runner.GateError):
        runner.expand_candidate('N21', n22, base)
    contract = LiftAfterCloseContract(SimpleNamespace(validate=lambda _: None, target_index=0), mode='unknown')
    with pytest.raises(RuntimeError, match='Unsupported lift quality mode'):
        contract.validate([])
