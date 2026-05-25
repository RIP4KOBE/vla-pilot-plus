import numpy as np
import torch
from scipy.spatial.transform import Rotation as R


LIBERO_RDT_INDICES = [30, 31, 32, 33, 34, 35, 36, 37, 38, 10]
ACTIVE_INDICES_SORTED = sorted(LIBERO_RDT_INDICES)
EEF_POS_SLICE = slice(30, 33)
EEF_ROT6D_SLICE = slice(33, 39)
GRIPPER_OPEN_INDEX = 10
OSC_POS_SCALE = np.array([0.05, 0.05, 0.05], dtype=np.float32)
OSC_ROT_SCALE = np.array([0.5, 0.5, 0.5], dtype=np.float32)


def rotvec_to_ortho6d(rotvec):
    rotvec = np.asarray(rotvec, dtype=np.float32)
    original_shape = rotvec.shape[:-1]
    matrix = R.from_rotvec(rotvec.reshape(-1, 3)).as_matrix().astype(np.float32)
    ortho6d = matrix[:, :, :2].transpose(0, 2, 1).reshape(-1, 6)
    return ortho6d.reshape(original_shape + (6,))


def _normalize_vector(vector):
    norm = np.linalg.norm(vector, axis=-1, keepdims=True)
    return vector / np.maximum(norm, 1e-8)


def ortho6d_to_rotmat(ortho6d):
    ortho6d = np.asarray(ortho6d, dtype=np.float32)
    original_shape = ortho6d.shape[:-1]
    flat = ortho6d.reshape(-1, 6)
    x_raw = flat[:, 0:3]
    y_raw = flat[:, 3:6]
    x_norm = np.linalg.norm(x_raw, axis=-1, keepdims=True)
    y_norm = np.linalg.norm(y_raw, axis=-1, keepdims=True)
    x = _normalize_vector(x_raw)
    z_raw = np.cross(x, y_raw)
    z_norm = np.linalg.norm(z_raw, axis=-1, keepdims=True)
    invalid = ((x_norm < 1e-8) | (y_norm < 1e-8) | (z_norm < 1e-8)).reshape(-1)
    x[invalid] = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    z_raw[invalid] = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    z = _normalize_vector(z_raw)
    y = np.cross(z, x)
    matrix = np.stack([x, y, z], axis=-1)
    return matrix.reshape(original_shape + (3, 3)).astype(np.float32)


def ortho6d_to_rotvec(ortho6d):
    matrix = ortho6d_to_rotmat(ortho6d)
    original_shape = matrix.shape[:-2]
    rotvec = R.from_matrix(matrix.reshape(-1, 3, 3)).as_rotvec().astype(np.float32)
    return rotvec.reshape(original_shape + (3,))


def map_libero_gripper_action_to_open(raw_gripper):
    raw_gripper = np.asarray(raw_gripper, dtype=np.float32)
    return np.clip((1.0 - raw_gripper) / 2.0, 0.0, 1.0).astype(np.float32)


def map_open_to_libero_gripper(open_scalar):
    open_scalar = np.asarray(open_scalar, dtype=np.float32)
    return (1.0 - 2.0 * np.clip(open_scalar, 0.0, 1.0)).astype(np.float32)


def map_libero_gripper_state(gripper_qpos):
    gripper_qpos = np.asarray(gripper_qpos, dtype=np.float32)
    width = gripper_qpos[..., 0] - gripper_qpos[..., 1]
    return np.clip(width / 0.08, 0.0, 1.0).astype(np.float32)


def libero_raw_to_rdt_action(raw_action_7d):
    raw_action_7d = np.asarray(raw_action_7d, dtype=np.float32)
    if raw_action_7d.shape[-1] != 7:
        raise ValueError("Expected raw LIBERO action with last dimension 7")

    action = np.zeros(raw_action_7d.shape[:-1] + (128,), dtype=np.float32)
    action[..., EEF_POS_SLICE] = raw_action_7d[..., :3] * OSC_POS_SCALE
    action[..., EEF_ROT6D_SLICE] = rotvec_to_ortho6d(raw_action_7d[..., 3:6] * OSC_ROT_SCALE)
    action[..., GRIPPER_OPEN_INDEX] = map_libero_gripper_action_to_open(raw_action_7d[..., 6])
    return action


def rdt_action_to_libero_raw(action_128d):
    action_128d = np.asarray(action_128d, dtype=np.float32)
    if action_128d.shape[-1] != 128:
        raise ValueError("Expected RDT action with last dimension 128")

    raw = np.zeros(action_128d.shape[:-1] + (7,), dtype=np.float32)
    raw[..., :3] = action_128d[..., EEF_POS_SLICE] / OSC_POS_SCALE
    raw[..., 3:6] = ortho6d_to_rotvec(action_128d[..., EEF_ROT6D_SLICE]) / OSC_ROT_SCALE
    raw[..., :6] = np.clip(raw[..., :6], -1.0, 1.0)
    raw_gripper = map_open_to_libero_gripper(action_128d[..., GRIPPER_OPEN_INDEX])
    raw[..., 6] = np.where(raw_gripper > 0.0, 1.0, -1.0).astype(np.float32)
    return raw


def decode_rdt_libero_action_chunk(pred_actions_128, action_chunk_horizon):
    if not torch.is_tensor(pred_actions_128):
        raise TypeError("Expected pred_actions_128 to be a torch tensor")
    if (
        pred_actions_128.ndim != 3
        or pred_actions_128.shape[1] != 64
        or pred_actions_128.shape[2] != 128
    ):
        raise ValueError("Expected pred_actions_128 with shape (B, 64, 128)")
    if action_chunk_horizon < 1 or action_chunk_horizon > pred_actions_128.shape[1]:
        raise ValueError("action_chunk_horizon must fit within the action chunk")

    particle = pred_actions_128[0, :action_chunk_horizon].detach().cpu().numpy()
    decoded = rdt_action_to_libero_raw(particle)
    return torch.as_tensor(decoded, dtype=torch.float32, device=pred_actions_128.device).unsqueeze(0)
