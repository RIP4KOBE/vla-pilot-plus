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
