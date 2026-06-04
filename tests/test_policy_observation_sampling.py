import importlib.util
import sys
from pathlib import Path


# Load by file path to avoid relying on package import path or core/__init__.py.
_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "policy_observation_sampling.py"
_SPEC = importlib.util.spec_from_file_location("policy_observation_sampling", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load policy observation sampling helper from {_MODULE_PATH}")
_sampling_module = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _sampling_module
_SPEC.loader.exec_module(_sampling_module)

policy_observation_sample_num = _sampling_module.policy_observation_sample_num


def test_rdt_fetches_single_online_observation_even_with_particle_batch_size():
    assert policy_observation_sample_num("rdt", 20) == 1


def test_non_rdt_policies_use_configured_sample_batch_size():
    assert policy_observation_sample_num("pi05", 20) == 20
    assert policy_observation_sample_num("diffusion", 20) == 20


def test_non_rdt_policies_default_to_twenty_when_unconfigured():
    assert policy_observation_sample_num("pi05", None) == 20
