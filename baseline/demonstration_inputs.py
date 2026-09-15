"""Versioned conversion from recorded teleop inputs to the v44 online contract.

The source LeRobot export and ticket HDF5 files remain read-only. Small state
sidecars preserve episode/frame indices; images are converted on dataset read.
"""
import hashlib
from pathlib import Path

from .io import digest, read_json


CONTRACT = "libero-pi05-eef-two-fingers-flip-hw-v1"
MARKER = "_baseline_demonstration_contract"


def state_action_digest(states, actions):
    import numpy as np
    h = hashlib.sha256()
    for value in (states, actions):
        array = np.ascontiguousarray(value, dtype="<f4")
        h.update(str(array.shape).encode())
        h.update(array.tobytes())
    return h.hexdigest()


def policy_state(positions, quaternions_xyzw, fingers):
    """Use the installed online processor's quaternion convention unchanged."""
    import torch
    from lerobot.processor.env_processor import LiberoProcessorStep
    observation = {"observation.robot_state": {
        "eef": {"pos": torch.as_tensor(positions, dtype=torch.float32),
                "quat": torch.as_tensor(quaternions_xyzw, dtype=torch.float32)},
        "gripper": {"qpos": torch.as_tensor(fingers, dtype=torch.float32)}}}
    result = LiberoProcessorStep()._process_observation(observation)["observation.state"]
    if result.ndim != 2 or result.shape[1] != 8 or not torch.isfinite(result).all():
        raise ValueError("reconstructed v44 state must be finite [N,8]")
    return result


def policy_image(image, height, width):
    """Decode CHW [0,1], area-resize raw pixels, then apply the online flip."""
    import cv2
    import numpy as np
    import torch
    if image.ndim != 3 or image.shape[0] != 3 or not torch.isfinite(image).all():
        raise ValueError("demonstration image must be finite RGB CHW")
    if image.min() < 0 or image.max() > 1:
        raise ValueError("LeRobot demonstration pixels must be in [0,1]")
    pixels = image.detach().cpu().mul(255).round().to(torch.uint8).permute(1, 2, 0).numpy()
    pixels = cv2.resize(pixels, (width, height), interpolation=cv2.INTER_AREA)
    return torch.from_numpy(np.ascontiguousarray(pixels[::-1, ::-1])).permute(2, 0, 1).float() / 255


def read_conversion(source, cfg):
    if cfg.get("demonstration_contract") != CONTRACT:
        raise ValueError("CLARE/MLR training requires the corrected demonstration contract")
    reference = source.get("policy_input", {})
    if reference.get("contract") != CONTRACT or not reference.get("manifest"):
        raise ValueError("demonstration lacks a verified v44 state conversion; prepare inputs first")
    path = Path(reference["manifest"])
    if digest(path) != reference.get("sha256"):
        raise ValueError("demonstration conversion manifest checksum mismatch")
    value = read_json(path)
    expected = {"contract": CONTRACT, "task_key": source["task_key"],
                "source_curation_sha256": source["source_curation_sha256"],
                "raw_root": str(Path(source["root"]).resolve()),
                "height": cfg["observation_height"], "width": cfg["observation_width"]}
    if any(value.get(k) != v for k, v in expected.items()):
        raise ValueError("demonstration conversion belongs to another source or input contract")
    if value["source_info_sha256"] != digest(Path(source["root"]) / "meta/info.json"):
        raise ValueError("raw demonstration metadata changed after conversion")
    if not value.get("validation", {}).get("passed"):
        raise ValueError("demonstration conversion did not pass online-input validation")
    episodes = value["episodes"]
    if len(episodes) != len(source["episodes"]) or {r["episode_index"] for r in episodes} != set(source["episodes"]):
        raise ValueError("conversion does not cover exactly the selected episodes")
    return value


class PolicyInputDataset:
    def __init__(self, dataset, source, cfg):
        import numpy as np
        self.dataset, self.cfg = dataset, cfg
        conversion = read_conversion(source, cfg)
        self.states = {}
        for row in conversion["episodes"]:
            if digest(row["states_path"]) != row["states_sha256"]:
                raise ValueError("converted state sidecar checksum mismatch")
            states = np.load(row["states_path"], mmap_mode="r", allow_pickle=False)
            if states.dtype != np.float32 or states.shape != (row["frames"], 8) or not np.isfinite(states).all():
                raise ValueError("converted state sidecar has invalid shape or values")
            self.states[row["episode_index"]] = states
        if sum(len(v) for v in self.states.values()) != len(dataset):
            raise ValueError("converted and raw demonstration frame counts differ")

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, index):
        import torch
        raw = dict(self.dataset[index])
        if MARKER in raw:
            raise ValueError("demonstration input conversion must be applied exactly once")
        episode, frame = int(raw["episode_index"]), int(raw["frame_index"])
        if episode not in self.states or not 0 <= frame < len(self.states[episode]):
            raise ValueError("raw episode/frame index is absent from the state conversion")
        raw["observation.state"] = torch.from_numpy(self.states[episode][frame].copy())
        for key in ("observation.images.image", "observation.images.image2"):
            raw[key] = policy_image(raw[key], self.cfg["observation_height"], self.cfg["observation_width"])
        raw[MARKER] = CONTRACT
        return raw


def checked_training_batch(raw, cfg):
    marker = raw.get(MARKER)
    markers = [marker] if isinstance(marker, str) else marker
    if cfg.get("demonstration_contract") != CONTRACT or not markers or any(v != CONTRACT for v in markers):
        raise ValueError("refusing unconverted demonstration inputs")
    return {k: v for k, v in raw.items() if k != MARKER}
