import base64
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core.gemini_grounder import GeminiStageRecognizer, create_gemini_stage_recognizer
from core.stage_capture import CapturedStageRecognizer


@pytest.mark.parametrize("reply,decision", [("stage 2\nguidance: no", (2, False)),
                                            ("stage 1\nguidance:", (1, True))])
def test_capture_preserves_exact_request_response_and_original_parser(tmp_path, monkeypatch, reply, decision):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr("core.gemini_grounder._make_client", lambda config: client)
    config = {"model": "gemini-3-flash", "backend": "openai_compatible"}
    plain = GeminiStageRecognizer(config)
    captured = create_gemini_stage_recognizer({**config, "capture_dir": str(tmp_path / "capture")})
    assert isinstance(captured, CapturedStageRecognizer)
    kwargs = dict(current_rgb=np.zeros((2, 2, 3), dtype=np.uint8),
                  init_img_with_keypoints=np.ones((2, 2, 3), dtype=np.uint8),
                  instruction="put soup in basket", stage_descriptions="stage 1: grasp", num_stages=2)
    assert plain.identify_stage_and_guidance(**kwargs) == captured.identify_stage_and_guidance(**kwargs) == decision
    assert calls[0] == calls[1]
    assert calls[0]["max_tokens"] == 256 and calls[0]["temperature"] == 0.0
    folder = tmp_path / "capture/request_0000"
    parts = json.loads((folder / "parts.json").read_text())
    for recorded, sent in zip(parts, calls[0]["messages"][0]["content"]):
        if recorded["type"] == "text":
            assert recorded == sent
        else:
            assert (folder / recorded["file"]).read_bytes() == base64.b64decode(sent["image_url"]["url"].split(",")[1])
    assert json.loads((folder / "metadata.json").read_text())["raw_response"] == reply
    assert plain.last_result["parse_ok"] == captured.last_result["parse_ok"]

