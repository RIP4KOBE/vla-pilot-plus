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
