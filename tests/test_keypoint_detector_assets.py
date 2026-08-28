from pathlib import Path

import pytest
import torch

from core.keypoint_detector import KeypointDetector
from mode_gate.preflight import _directory_fingerprint


class _DummyDino:
    def __init__(self):
        self.loaded = None
        self.strict = None
        self.device = None

    def load_state_dict(self, state_dict, *, strict):
        self.loaded = state_dict
        self.strict = strict

    def eval(self):
        return self

    def to(self, device):
        self.device = device
        return self


def _detector(repo: Path, weights: Path) -> KeypointDetector:
    detector = KeypointDetector.__new__(KeypointDetector)
    detector.config = {
        "dinov2_repo_path": str(repo),
        "dinov2_weights_path": str(weights),
    }
    detector.device = torch.device("cpu")
    return detector


def test_dinov2_load_is_local_strict_and_offline(tmp_path, monkeypatch):
    repo = tmp_path / "dinov2"
    repo.mkdir()
    (repo / "hubconf.py").write_text("# frozen\n", encoding="utf-8")
    weights = tmp_path / "weights.pth"
    weights.write_bytes(b"placeholder")
    model = _DummyDino()
    calls = {}

    def fake_hub_load(repo_or_dir, model_name, **kwargs):
        calls["hub"] = (repo_or_dir, model_name, kwargs)
        return model

    def fake_torch_load(path, **kwargs):
        calls["weights"] = (path, kwargs)
        return {"layer.weight": torch.ones(1)}

    monkeypatch.setattr(torch.hub, "load", fake_hub_load)
    monkeypatch.setattr(torch, "load", fake_torch_load)
    detector = _detector(repo, weights)
    detector._load_dinov2("dinov2_vitb14")

    assert calls["hub"] == (
        str(repo.resolve()),
        "dinov2_vitb14",
        {"source": "local", "pretrained": False},
    )
    assert calls["weights"][0] == weights.resolve()
    assert calls["weights"][1] == {
        "map_location": "cpu",
        "weights_only": True,
        "mmap": True,
    }
    assert model.strict is True
    assert model.device == torch.device("cpu")


def test_dinov2_missing_assets_fail_before_torch_hub(tmp_path, monkeypatch):
    called = False

    def fake_hub_load(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(torch.hub, "load", fake_hub_load)
    detector = _detector(tmp_path / "missing-repo", tmp_path / "missing.pth")
    with pytest.raises(FileNotFoundError, match="source is missing"):
        detector._load_dinov2("dinov2_vitb14")
    assert called is False


def test_dinov2_runtime_download_configuration_is_rejected():
    detector = KeypointDetector.__new__(KeypointDetector)
    detector.config = {}
    detector.device = torch.device("cpu")
    with pytest.raises(RuntimeError, match="runtime downloads are disabled"):
        detector._load_dinov2("dinov2_vitb14")


def test_frozen_source_fingerprint_ignores_runtime_bytecode(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "hubconf.py"
    source.write_text("revision = 1\n", encoding="utf-8")
    first = _directory_fingerprint(repo)

    cache = repo / "__pycache__"
    cache.mkdir()
    (cache / "hubconf.pyc").write_bytes(b"runtime cache")
    assert _directory_fingerprint(repo) == first

    source.write_text("revision = 2\n", encoding="utf-8")
    assert _directory_fingerprint(repo) != first
