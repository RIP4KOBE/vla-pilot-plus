from pathlib import Path
import sys


RDT_ROOT = Path(__file__).resolve().parents[1]
if str(RDT_ROOT) not in sys.path:
    sys.path.insert(0, str(RDT_ROOT))


def test_from_pretrained_accepts_new_hub_without_proxies_or_resume_download(tmp_path, monkeypatch):
    from models.hub_mixin import CompatiblePyTorchModelHubMixin

    class DummyModel(CompatiblePyTorchModelHubMixin):
        def __init__(self):
            pass

    loaded = object()

    def fake_load_as_pickle(model, model_file, map_location, strict):
        assert model_file == str(tmp_path / "pytorch_model.bin")
        assert map_location == "cpu"
        assert strict is False
        return loaded

    monkeypatch.setattr(DummyModel, "_load_as_pickle", staticmethod(fake_load_as_pickle))

    assert DummyModel._from_pretrained(
        model_id=str(tmp_path),
        revision=None,
        cache_dir=None,
        force_download=False,
        local_files_only=False,
        token=None,
    ) is loaded
