import json
from pathlib import Path

from omegaconf import OmegaConf


GT_ROOT = Path("/mnt/data/hf_cache/hub/RDT-1B-LIBERO-Object")
GT_WEIGHT = GT_ROOT / "ema" / "model.safetensors"
T5 = Path("/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl")
SIGLIP = Path("/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384")
EXPECTED_IMG_HISTORY_AND_CAMERAS = [2, 3]


def test_gt_checkpoint_and_encoder_paths_exist():
    config_json = GT_ROOT / "config.json"

    assert GT_ROOT.is_dir(), f"Missing GT RDT root: {GT_ROOT}"
    assert config_json.is_file(), f"Missing GT RDT config: {config_json}"
    assert GT_WEIGHT.is_file(), f"Missing GT RDT EMA weights: {GT_WEIGHT}"
    assert T5.is_dir(), f"Missing local T5 encoder dir: {T5}"
    assert SIGLIP.is_dir(), f"Missing local SigLIP encoder dir: {SIGLIP}"


def test_gt_checkpoint_config_matches_rdt_libero_contract():
    cfg = json.loads((GT_ROOT / "config.json").read_text())

    assert cfg["pred_horizon"] == 64
    assert cfg["action_dim"] == 128
    assert cfg["state_token_dim"] == 128
    assert cfg["img_pos_embed_config"][0][1][:2] == EXPECTED_IMG_HISTORY_AND_CAMERAS
    assert cfg["lang_token_dim"] == 4096
    assert cfg["img_token_dim"] == 1152
    assert cfg["noise_scheduler"]["num_inference_timesteps"] == 5
    assert cfg["noise_scheduler"]["prediction_type"] == "sample"


def test_policy_yaml_keeps_rdt_route_and_gt_checkpoint():
    cfg = OmegaConf.load("configs/policy.yaml")

    assert cfg.type == "rdt"
    assert cfg.rdt.pretrained_path in {str(GT_ROOT), str(GT_WEIGHT)}
    assert cfg.rdt.weight_variant == "ema"
    assert cfg.rdt.text_encoder == str(T5)
    assert cfg.rdt.vision_encoder == str(SIGLIP)
    assert cfg.rdt.action_chunk_horizon == 8
    assert cfg.rdt.control_frequency == 20
    assert cfg.rdt.semantics == "libero_gt_rollout"


def test_backend_libero_matches_gt_rollout_protocol():
    cfg = OmegaConf.load("configs/backend/libero.yaml")

    assert cfg.libero.suite_name == "libero_object"
    assert cfg.libero.observation_width == 128
    assert cfg.libero.observation_height == 128
    assert cfg.libero.num_steps_wait == 5
    assert cfg.libero.max_episode_steps == 720
    assert cfg.libero.task_ids_filter is None
