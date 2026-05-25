import json
from pathlib import Path

from omegaconf import OmegaConf


CHECKPOINT = Path(
    "/mnt/data/rdt_checkpoints/rdt-libero-full-formal-20260523-140903/checkpoint-60000"
)
T5 = Path("/mnt/data/hf_cache/hub/models--google--t5-v1_1-xxl")
SIGLIP = Path("/mnt/data/hf_cache/hub/models--google--siglip-so400m-patch14-384")


def test_target_checkpoint_and_encoder_paths_exist():
    assert CHECKPOINT.is_dir()
    assert (CHECKPOINT / "config.json").is_file()
    assert (CHECKPOINT / "ema" / "model.safetensors").is_file()
    assert T5.is_dir()
    assert SIGLIP.is_dir()


def test_checkpoint_config_matches_rdt_libero_contract():
    cfg = json.loads((CHECKPOINT / "config.json").read_text())
    assert cfg["pred_horizon"] == 64
    assert cfg["action_dim"] == 128
    assert cfg["state_token_dim"] == 128
    assert cfg["img_pos_embed_config"][0][1][:2] == [2, 3]
    assert cfg["lang_token_dim"] == 4096
    assert cfg["img_token_dim"] == 1152


def test_policy_yaml_keeps_rdt_route_and_libero_checkpoint():
    cfg = OmegaConf.load("configs/policy.yaml")
    assert cfg.type in {"pi05", "rdt", "diffusion"}
    assert cfg.rdt.pretrained_path == str(CHECKPOINT)
    assert cfg.rdt.weight_variant == "ema"
    assert cfg.rdt.text_encoder == str(T5)
    assert cfg.rdt.vision_encoder == str(SIGLIP)
    assert cfg.rdt.semantics == "libero_finetuned"
