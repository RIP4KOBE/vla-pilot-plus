import sys
from pathlib import Path

from omegaconf import OmegaConf
import torch


def test_init_components_skips_vlm_when_guidance_disabled(monkeypatch, tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    def _raise_if_vlm_constructed(*args, **kwargs):
        raise AssertionError("VLMAgent should not be constructed when guidance is disabled")

    monkeypatch.setattr(main, "VLMAgent", _raise_if_vlm_constructed)

    runner = main.Main.__new__(main.Main)
    runner.config = OmegaConf.create(
        {
            "use_guidance": False,
            "output_dir": str(tmp_path),
            "cached_functions_dir": None,
            "use_vlm_stage_recognition": False,
        }
    )
    runner.output_dir = str(tmp_path)
    runner.backend = "libero"
    runner.adapter = object()

    runner._init_components(OmegaConf.create({"perception": {}}))

    assert runner.vlm_agent is None
    assert runner.keypoint_detector is None
    assert runner.video_recorder is not None


def test_visualization_action_chunk_prefers_policy_candidates():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    fallback = torch.zeros(1, 3, 7)
    candidates = torch.arange(2 * 3 * 7, dtype=torch.float32).reshape(2, 3, 7)

    class Policy:
        def get_last_visualization_action_candidates(self):
            return candidates

    class Adapter:
        def env_postprocessor(self, transition):
            return {"action": transition["action"] + 1.0}

    visualized = main._get_visualization_action_chunk(Policy(), Adapter(), fallback)

    torch.testing.assert_close(visualized, candidates + 1.0)


def test_main_flat_vls_overrides_merge_into_grouped_config():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    cfg = OmegaConf.create(
        {
            "vls_config": {
                "guide_scale": 40.0,
                "sample_batch_size": 20,
                "use_diversity": True,
                "diversity_scale": 10.0,
                "use_fkd": True,
                "fkd": {"resample_frequency": 5},
            },
            "guide_scale": 12.5,
            "sample_batch_size": 3,
            "use_diversity": False,
            "diversity_scale": 0.75,
            "use_fkd": False,
            "MCMC_steps": 2,
            "sigmoid_k": 6.0,
            "sigmoid_x0": 0.3,
            "start_ratio": 0.4,
            "fkd_config": {"resample_frequency": 9},
        }
    )

    merged = main._main_vls_config(cfg)

    assert merged["guide_scale"] == 12.5
    assert merged["sample_batch_size"] == 3
    assert merged["use_diversity"] is False
    assert merged["diversity_scale"] == 0.75
    assert merged["use_fkd"] is False
    assert merged["MCMC_steps"] == 2
    assert merged["sigmoid_k"] == 6.0
    assert merged["sigmoid_x0"] == 0.3
    assert merged["start_ratio"] == 0.4
    assert merged["fkd"] == {"resample_frequency": 9}
