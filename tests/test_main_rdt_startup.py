import sys
from pathlib import Path

from omegaconf import OmegaConf


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


def test_visualization_action_chunk_prefers_policy_side_channel_candidates():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import torch
    import main

    executed = torch.zeros(1, 4, 7)
    candidates = torch.ones(3, 4, 7)

    class _Policy:
        def get_last_visualization_action_candidates(self):
            return candidates

    class _Adapter:
        def __init__(self):
            self.seen_action = None

        def env_postprocessor(self, transition):
            self.seen_action = transition["action"]
            return {"action": transition["action"] + 2.0}

    adapter = _Adapter()

    result = main._get_visualization_action_chunk(_Policy(), adapter, executed)

    torch.testing.assert_close(adapter.seen_action, candidates)
    torch.testing.assert_close(result, candidates + 2.0)
    torch.testing.assert_close(executed, torch.zeros(1, 4, 7))


def test_visualization_action_chunk_falls_back_to_execution_action_without_side_channel():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import torch
    import main

    executed = torch.ones(1, 4, 7)

    result = main._get_visualization_action_chunk(object(), object(), executed)

    assert result is executed
