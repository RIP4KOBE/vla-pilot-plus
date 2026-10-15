from __future__ import annotations

import torch


LIBERO_STATE_INDICES = [0, 1, 2, 3, 4, 5, 6, 10, 11]
LIBERO_ACTION_INDICES = [39, 40, 41, 42, 43, 44, 10]

ACTIVE_STATE_INDICES_SORTED = sorted(LIBERO_STATE_INDICES)
ACTIVE_ACTION_INDICES_SORTED = sorted(LIBERO_ACTION_INDICES)

# Backward-compatible names used by rdt_policy_steer.py.
LIBERO_RDT_INDICES = LIBERO_ACTION_INDICES
ACTIVE_INDICES_SORTED = ACTIVE_STATE_INDICES_SORTED


def _as_tensor(action_128d) -> torch.Tensor:
    if torch.is_tensor(action_128d):
        return action_128d
    return torch.as_tensor(action_128d, dtype=torch.float32)


def rotvec_to_ortho6d(*args, **kwargs):
    raise RuntimeError("rotvec_to_ortho6d is not part of the GT LIBERO RDT rollout path")


def map_libero_gripper_state(*args, **kwargs):
    raise RuntimeError("map_libero_gripper_state is not part of the GT LIBERO RDT rollout path")


def rdt_action_to_libero_raw(action_128d) -> torch.Tensor:
    action = _as_tensor(action_128d)
    if action.shape[-1] != 128:
        raise ValueError(f"Expected RDT action with last dimension 128, got {tuple(action.shape)}")

    decoded = action[..., LIBERO_ACTION_INDICES].clone().to(dtype=torch.float32)
    decoded[..., -1] = torch.where(
        decoded[..., -1] < 0.0,
        torch.tensor(-1.0, device=decoded.device, dtype=decoded.dtype),
        torch.tensor(1.0, device=decoded.device, dtype=decoded.dtype),
    )
    return decoded


def decode_rdt_libero_action_chunk(pred_actions_128, action_chunk_horizon: int) -> torch.Tensor:
    if not torch.is_tensor(pred_actions_128):
        raise TypeError("Expected pred_actions_128 to be a torch tensor")
    if (
        pred_actions_128.ndim != 3
        or pred_actions_128.shape[1] != 64
        or pred_actions_128.shape[2] != 128
    ):
        raise ValueError(
            f"Expected pred_actions_128 with shape (B, 64, 128), got {tuple(pred_actions_128.shape)}"
        )
    if pred_actions_128.shape[0] < 1:
        raise ValueError("pred_actions_128 must contain at least one batch/particle")
    if action_chunk_horizon < 1 or action_chunk_horizon > pred_actions_128.shape[1]:
        raise ValueError("action_chunk_horizon must fit within the action chunk horizon")

    first_particle = pred_actions_128[0:1, :action_chunk_horizon, :]
    return rdt_action_to_libero_raw(first_particle).to(device=pred_actions_128.device)
