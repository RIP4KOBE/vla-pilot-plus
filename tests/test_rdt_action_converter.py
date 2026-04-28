"""
Unit tests for core/rdt_action_converter.py.
All CPU-only, no GPU or checkpoint required.
"""
import numpy as np
import pytest
from core.rdt_action_converter import (
    franka_fk_pose,
    denormalize_rdt_joints,
    rdt_chunk_to_libero_actions,
    FRANKA_Q_MIN,
    FRANKA_Q_MAX,
    RDT_ACTION_MIN,
    RDT_ACTION_MAX,
)


def test_fk_at_zero_joints():
    """FK at all-zero joints should return a non-zero EEF position."""
    q = np.zeros(7)
    pos, rot = franka_fk_pose(q)
    assert pos.shape == (3,)
    assert rot.shape == (3, 3)
    # EEF should be above the base, not at origin
    assert abs(pos[2]) > 0.1, f"Expected z > 0.1, got {pos[2]}"


def test_fk_rotation_is_orthogonal():
    """Rotation matrix must be orthogonal (R.T @ R ≈ I)."""
    q = np.array([0.1, -0.5, 0.2, -2.0, 0.1, 2.5, 0.3])
    _, rot = franka_fk_pose(q)
    residual = np.max(np.abs(rot.T @ rot - np.eye(3)))
    assert residual < 1e-6, f"Rotation not orthogonal: residual={residual}"


def test_fk_different_configs_differ():
    """Two different joint configs must produce different EEF positions."""
    q1 = np.zeros(7)
    q2 = np.array([0.5, 0.2, -0.3, -1.5, 0.1, 2.0, 0.8])
    pos1, _ = franka_fk_pose(q1)
    pos2, _ = franka_fk_pose(q2)
    assert np.linalg.norm(pos1 - pos2) > 0.01


def test_denormalize_identity_endpoints():
    """Normalized +1 should denormalize to action_max, -1 to action_min."""
    ones = np.ones(7)
    result_max = denormalize_rdt_joints(ones)
    np.testing.assert_allclose(result_max, np.clip(RDT_ACTION_MAX, FRANKA_Q_MIN, FRANKA_Q_MAX),
                               atol=1e-5)

    neg_ones = -np.ones(7)
    result_min = denormalize_rdt_joints(neg_ones)
    np.testing.assert_allclose(result_min, np.clip(RDT_ACTION_MIN, FRANKA_Q_MIN, FRANKA_Q_MAX),
                               atol=1e-5)


def test_chunk_output_shape():
    """rdt_chunk_to_libero_actions must return (H, 7)."""
    H = 8
    rdt_chunk = np.random.uniform(-0.5, 0.5, (H, 8)).astype(np.float32)
    current_q = np.array([0.0, 0.15, 0.0, -2.54, 0.0, 2.80, 0.78])
    result = rdt_chunk_to_libero_actions(rdt_chunk, current_q)
    assert result.shape == (H, 7), f"Expected ({H}, 7), got {result.shape}"


def test_chunk_output_in_range():
    """All LIBERO actions must be clipped to [-1, 1]."""
    H = 8
    rdt_chunk = np.random.uniform(-1.0, 1.0, (H, 8)).astype(np.float32)
    current_q = np.array([0.0, 0.15, 0.0, -2.54, 0.0, 2.80, 0.78])
    result = rdt_chunk_to_libero_actions(rdt_chunk, current_q)
    assert np.all(result >= -1.0) and np.all(result <= 1.0), \
        f"Actions out of [-1,1]: min={result.min():.3f} max={result.max():.3f}"


def test_zero_motion_chunk_near_zero_delta():
    """Constant predicted config = current config → EEF delta ≈ zero."""
    current_q = np.array([0.0, 0.15, 0.0, -2.54, 0.0, 2.80, 0.78])
    H = 4
    rdt_chunk = np.zeros((H, 8), dtype=np.float32)
    # Set arm joints to the normalized value of current_q[0..6]
    for j in range(7):
        norm_val = (current_q[j] - RDT_ACTION_MIN[j]) / (RDT_ACTION_MAX[j] - RDT_ACTION_MIN[j]) * 2 - 1
        rdt_chunk[:, j] = np.clip(norm_val, -1.0, 1.0)
    result = rdt_chunk_to_libero_actions(rdt_chunk, current_q)
    # All steps should be near-zero (same config, no motion)
    assert np.all(np.abs(result[:, :6]) < 0.05), \
        f"Expected near-zero EEF deltas, got max={np.abs(result[:, :6]).max():.4f}"
