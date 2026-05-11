"""
rdt_action_converter.py — Convert RDT joint-space predictions to LIBERO EEF-delta actions.

RDT-ManiSkill predicts absolute joint angles (after denormalization) for a Franka Panda arm.
LIBERO uses OSC (Operational Space Control): 7D EEF-delta [dx, dy, dz, drx, dry, drz, gripper].

Conversion pipeline:
  1. Denormalize RDT normalized output ∈ [-1,1] → actual joint angles (radians).
  2. Compute Franka FK for consecutive predicted joint configs.
  3. Convert incremental EEF-pose differences to LIBERO OSC action vectors.
"""
from __future__ import annotations
from typing import Tuple

import numpy as np

# ── Franka Panda DH parameters ────────────────────────────────────────────────
# Source: Franka Panda technical specifications, modified DH convention.
# [a (m), d (m), alpha (rad)] — theta_i = q_i (no constant offset for joints 0–6).
_FRANKA_DH = [
    (0,        0.333,   0.0),           # joint 1
    (0,        0.0,    -np.pi / 2),     # joint 2
    (0,        0.316,   np.pi / 2),     # joint 3
    (0.0825,   0.0,     np.pi / 2),     # joint 4
    (-0.0825,  0.384,  -np.pi / 2),     # joint 5
    (0,        0.0,     np.pi / 2),     # joint 6
    (0.088,    0.0,     np.pi / 2),     # joint 7
    (0,        0.107,   0.0),           # flange (fixed, theta=0)
]

# Franka Panda joint limits (URDF) — used to clip RDT predictions.
FRANKA_Q_MIN = np.array([-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973])
FRANKA_Q_MAX = np.array([ 2.8973,  1.7628,  2.8973, -0.0698,  2.8973,  3.7525,  2.8973])

# RDT DATA_STAT — the training data normalization constants.
# action_min/max for the 7 arm joints (dim 7 = gripper, handled separately).
RDT_ACTION_MIN = np.array([-0.7472, -0.0863, -0.4995, -2.6584, -0.5751,  1.8291, -2.2452])
RDT_ACTION_MAX = np.array([ 0.7655,  1.4984,  0.4679, -0.3818,  0.5517,  3.2916,  2.5758])

# LIBERO OSC action scale (empirical from LIBERO/robosuite docs).
# OSC maps action ∈ [-1, 1] to:
#   position delta: ±0.05 m  per unit (kp ≈ 150, action_scale ≈ 0.05)
#   orientation delta: ±0.5 rad per unit
_POS_SCALE = 0.05   # m per unit action
_ORI_SCALE = 0.5    # rad per unit action

# ── DIAGNOSTIC PROBE P6 (round-4): module-level state set by caller. ───────────
# Caller (_postprocess_actions in rdt_policy_steer.py) sets these before invoking
# rdt_chunk_to_libero_actions to indicate whether to emit FK-chain diagnostics.
# Purely additive — main conversion logic is unchanged.
_DIAG_TRIGGER = False
_DIAG_STEP = 0
# ──────────────────────────────────────────────────────────────────────────────


def _dh_matrix(a: float, d: float, alpha: float, theta: float) -> np.ndarray:
    """Compute a 4x4 homogeneous DH transformation matrix."""
    ct, st = np.cos(theta), np.sin(theta)
    ca, sa = np.cos(alpha), np.sin(alpha)
    return np.array([
        [ct, -st * ca,  st * sa, a * ct],
        [st,  ct * ca, -ct * sa, a * st],
        [0.0,       sa,       ca,      d],
        [0.0,      0.0,      0.0,    1.0],
    ])


def franka_fk_pose(q: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute Franka Panda forward kinematics.

    Args:
        q: (7,) joint angles in radians.

    Returns:
        pos: (3,) EEF position in robot base frame (meters).
        rot: (3, 3) EEF rotation matrix in robot base frame.
    """
    T = np.eye(4)
    for i, (a, d, alpha) in enumerate(_FRANKA_DH[:7]):
        T = T @ _dh_matrix(a, d, alpha, float(q[i]))
    # Flange (fixed transformation, theta=0)
    a, d, alpha = _FRANKA_DH[7]
    T = T @ _dh_matrix(a, d, alpha, 0.0)
    return T[:3, 3].copy(), T[:3, :3].copy()


def _rot_to_axisangle(R: np.ndarray) -> np.ndarray:
    """Convert a 3x3 rotation matrix to a 3D axis-angle vector."""
    cos_angle = np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0)
    angle = float(np.arccos(cos_angle))
    if abs(angle) < 1e-7:
        return np.zeros(3)
    axis = np.array([R[2, 1] - R[1, 2],
                     R[0, 2] - R[2, 0],
                     R[1, 0] - R[0, 1]], dtype=np.float64)
    axis /= (2.0 * np.sin(angle) + 1e-9)
    return axis * angle


def denormalize_rdt_joints(x_norm: np.ndarray) -> np.ndarray:
    """
    Denormalize RDT's 7D joint output from [-1, 1] to actual joint angles (radians).

    Uses DATA_STAT action_min/max from maniskill_model.py (proven Franka-compatible).
    Clips to Franka URDF limits to prevent extrapolation.

    Args:
        x_norm: (7,) normalized joint values ∈ [-1, 1].

    Returns:
        (7,) joint angles in radians, clipped to Franka limits.
    """
    joints = (x_norm + 1.0) / 2.0 * (RDT_ACTION_MAX - RDT_ACTION_MIN) + RDT_ACTION_MIN
    return np.clip(joints, FRANKA_Q_MIN, FRANKA_Q_MAX)


def rdt_chunk_to_libero_actions(
    rdt_normalized_chunk: np.ndarray,   # (H, 8) normalized RDT output ∈ [-1, 1]
    current_joints: np.ndarray,         # (7,) current Franka joint angles from adapter
) -> np.ndarray:
    """
    Convert an RDT action chunk to LIBERO OSC EEF-delta actions.

    Steps:
      1. Denormalize RDT joints using DATA_STAT.
      2. Compute FK for the current config and each predicted config.
      3. Compute INCREMENTAL EEF deltas (each step relative to the previous).
      4. Scale position and orientation deltas to LIBERO's [-1, 1] action space.
      5. Append RDT's gripper dimension (already in [-1, 1]).

    The incremental formulation means:
      - Step 0 moves from current EEF to predicted EEF[0].
      - Step i moves from predicted EEF[i-1] to predicted EEF[i].
    This correctly drives LIBERO's receding-horizon OSC controller.

    Args:
        rdt_normalized_chunk: (H, 8) where columns 0-6 are arm joints, column 7 is gripper.
        current_joints: (7,) current joint angles in radians.

    Returns:
        (H, 7) LIBERO action chunk: [dx, dy, dz, drx, dry, drz, gripper] each ∈ [-1, 1].
    """
    H = rdt_normalized_chunk.shape[0]

    # Denormalize arm joints; gripper is already in [-1, 1] per DATA_STAT.
    arm_norm = rdt_normalized_chunk[:, :7]   # (H, 7)
    gripper   = rdt_normalized_chunk[:, 7]   # (H,)  already ∈ [-1, 1]

    # FK for each step.
    # q_sequence[0] = current; q_sequence[1..H] = predicted.
    q_sequence = [current_joints.copy()]
    for i in range(H):
        q_sequence.append(denormalize_rdt_joints(arm_norm[i]))

    poses = [franka_fk_pose(q) for q in q_sequence]  # list of (pos, rot)

    # ── DIAGNOSTIC PROBE P6: FK + denormalization health (revert via git revert HEAD) ──
    # Purely additive — captures pre-clip raw delta magnitudes too. No logic changes below.
    if _DIAG_TRIGGER:
        try:
            from pathlib import Path as _P
            import logging as _logging
            _lp = _P(__file__).resolve().parents[1] / "docs/superpowers/03_evidence/rdt_intergration/round-4/20260511_action_probes.log"
            _lp.parent.mkdir(parents=True, exist_ok=True)
            _q_seq_arr = np.array(q_sequence)  # (H+1, 7)
            _pos_arr = np.array([p[0] for p in poses])  # (H+1, 3)
            _q0_match = float(np.linalg.norm(_q_seq_arr[0] - current_joints, ord=np.inf))
            _q_step_diff = np.linalg.norm(np.diff(_q_seq_arr, axis=0), ord=np.inf, axis=1) if _q_seq_arr.shape[0] > 1 else np.array([0.0])
            _q_clip_count = int(np.sum(
                (_q_seq_arr[1:] == FRANKA_Q_MIN[None, :]) | (_q_seq_arr[1:] == FRANKA_Q_MAX[None, :])
            ))
            _pos_step_diff = np.linalg.norm(np.diff(_pos_arr, axis=0), axis=1) if _pos_arr.shape[0] > 1 else np.array([0.0])
            _rot0 = poses[0][1]
            _rot0_ortho_err = float(np.linalg.norm(_rot0 @ _rot0.T - np.eye(3), ord='fro'))
            # Pre-clip raw delta magnitudes (re-compute to avoid touching main loop)
            _pre_clip_pos_norms = []
            _pre_clip_ori_norms = []
            for _i in range(H):
                _dp = poses[_i + 1][0] - poses[_i][0]
                _drm = poses[_i + 1][1] @ poses[_i][1].T
                _daa = _rot_to_axisangle(_drm)
                _pre_clip_pos_norms.append(float(np.max(np.abs(_dp / _POS_SCALE))))
                _pre_clip_ori_norms.append(float(np.max(np.abs(_daa / _ORI_SCALE))))
            _pre_clip_pos_max = max(_pre_clip_pos_norms) if _pre_clip_pos_norms else 0.0
            _pre_clip_ori_max = max(_pre_clip_ori_norms) if _pre_clip_ori_norms else 0.0
            _npy_p6_q = _lp.parent / f"20260511_P6_q_sequence_step{_DIAG_STEP}.npy"
            _npy_p6_pos = _lp.parent / f"20260511_P6_eef_pos_step{_DIAG_STEP}.npy"
            np.save(str(_npy_p6_q), _q_seq_arr)
            np.save(str(_npy_p6_pos), _pos_arr)
            # 3D trajectory PNG (Stage S3 visualization)
            _png_p6 = _lp.parent / f"20260511_P6_eef_traj3d_step{_DIAG_STEP}.png"
            try:
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as _plt
                from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
                _fig = _plt.figure(figsize=(6, 5))
                _ax = _fig.add_subplot(111, projection='3d')
                _ax.plot(_pos_arr[:, 0], _pos_arr[:, 1], _pos_arr[:, 2], 'b-o', markersize=3)
                _ax.scatter([_pos_arr[0, 0]], [_pos_arr[0, 1]], [_pos_arr[0, 2]], c='g', s=80, label='start (current)')
                _ax.scatter([_pos_arr[-1, 0]], [_pos_arr[-1, 1]], [_pos_arr[-1, 2]], c='r', s=80, label='end')
                _ax.set_xlabel('x (m)'); _ax.set_ylabel('y (m)'); _ax.set_zlabel('z (m)')
                _ax.set_title(f'EEF trajectory step={_DIAG_STEP} (H+1={_pos_arr.shape[0]} poses)')
                _ax.legend()
                _fig.tight_layout()
                _fig.savefig(str(_png_p6), dpi=100)
                _plt.close(_fig)
                _png_saved = str(_png_p6)
            except Exception as _pe:
                _png_saved = f"FAILED:{_pe}"
            with open(_lp, "a") as _f:
                _f.write(
                    f"[P6 fk_chain step={_DIAG_STEP}] "
                    f"q_seq_shape={_q_seq_arr.shape} "
                    f"q0_match_inf_norm={_q0_match:.2e} "
                    f"q_step_diff_max={float(_q_step_diff.max()):.4f} "
                    f"q_step_diff_mean={float(_q_step_diff.mean()):.4f} "
                    f"q_clip_count={_q_clip_count} "
                    f"pos0={[float(x) for x in _pos_arr[0]]} "
                    f"pos_x_range=({float(_pos_arr[:, 0].min()):.3f},{float(_pos_arr[:, 0].max()):.3f}) "
                    f"pos_y_range=({float(_pos_arr[:, 1].min()):.3f},{float(_pos_arr[:, 1].max()):.3f}) "
                    f"pos_z_range=({float(_pos_arr[:, 2].min()):.3f},{float(_pos_arr[:, 2].max()):.3f}) "
                    f"pos_step_diff_max={float(_pos_step_diff.max()):.4f} "
                    f"pos_step_diff_mean={float(_pos_step_diff.mean()):.4f} "
                    f"rot0_ortho_err={_rot0_ortho_err:.2e} "
                    f"pre_clip_pos_max={_pre_clip_pos_max:.4f} "
                    f"pre_clip_ori_max={_pre_clip_ori_max:.4f} "
                    f"npy_q={str(_npy_p6_q)} "
                    f"npy_pos={str(_npy_p6_pos)} "
                    f"png={_png_saved}\n"
                )
        except Exception as _e:
            import logging as _logging
            _logging.getLogger("rdt_action_converter").warning(f"[P6] probe failed: {_e}")
    # ── END P6 ─────────────────────────────────────────────────────────────────

    # Incremental EEF deltas.
    libero_actions = np.zeros((H, 7), dtype=np.float32)
    for i in range(H):
        pos_prev, rot_prev = poses[i]
        pos_curr, rot_curr = poses[i + 1]

        delta_pos = pos_curr - pos_prev                        # (3,) meters
        delta_rot_mat = rot_curr @ rot_prev.T                  # rotation from prev→curr
        delta_axisangle = _rot_to_axisangle(delta_rot_mat)    # (3,) axis-angle

        # Normalize to LIBERO [-1, 1] scale.
        action_pos = np.clip(delta_pos / _POS_SCALE, -1.0, 1.0)
        action_ori = np.clip(delta_axisangle / _ORI_SCALE, -1.0, 1.0)

        # LIBERO gripper: -1 = open, +1 = close.
        # RDT gripper_open: high value = open. Negate to match LIBERO convention.
        action_gripper = float(-gripper[i])

        libero_actions[i] = np.concatenate([action_pos, action_ori, [action_gripper]])

    return libero_actions
