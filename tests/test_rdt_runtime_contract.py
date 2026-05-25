import json
from pathlib import Path

from omegaconf import OmegaConf


CHECKPOINT = Path(
    "/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000"
)
T5 = Path("/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl")
SIGLIP = Path("/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384")
EXPECTED_IMG_HISTORY_AND_CAMERAS = [2, 3]


def test_target_checkpoint_and_encoder_paths_exist():
    config_json = CHECKPOINT / "config.json"
    ema_weights = CHECKPOINT / "ema" / "model.safetensors"

    assert CHECKPOINT.is_dir(), f"Missing RDT checkpoint dir: {CHECKPOINT}"
    assert config_json.is_file(), f"Missing RDT checkpoint config: {config_json}"
    assert ema_weights.is_file(), f"Missing RDT EMA weights: {ema_weights}"
    assert T5.is_dir(), f"Missing local T5 encoder dir: {T5}"
    assert SIGLIP.is_dir(), f"Missing local SigLIP encoder dir: {SIGLIP}"


def test_checkpoint_config_matches_rdt_libero_contract():
    cfg = json.loads((CHECKPOINT / "config.json").read_text())
    assert cfg["pred_horizon"] == 64
    assert cfg["action_dim"] == 128
    assert cfg["state_token_dim"] == 128
    assert cfg["img_pos_embed_config"][0][1][:2] == EXPECTED_IMG_HISTORY_AND_CAMERAS, (
        "RDT LIBERO checkpoint must use 2-frame history x 3 camera slots"
    )
    assert cfg["lang_token_dim"] == 4096
    assert cfg["img_token_dim"] == 1152


def test_policy_yaml_keeps_rdt_route_and_libero_checkpoint():
    cfg = OmegaConf.load("configs/policy.yaml")
    assert cfg.type == "rdt"
    assert cfg.rdt.pretrained_path == str(CHECKPOINT)
    assert cfg.rdt.weight_variant == "ema"
    assert cfg.rdt.text_encoder == str(T5)
    assert cfg.rdt.vision_encoder == str(SIGLIP)
    assert cfg.rdt.semantics == "libero_finetuned"
