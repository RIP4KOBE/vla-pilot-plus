import subprocess
import sys
from pathlib import Path


def test_libero_object_is_base_suite_and_double_object_is_perturbation():
    adapter_path = Path(__file__).resolve().parents[1] / "core" / "env_adapters" / "libero_adapter.py"
    script = r'''
import importlib.util
import sys
import types

adapter_path = "__ADAPTER_PATH__"

core = types.ModuleType("core")
core.__path__ = []
env_adapters = types.ModuleType("core.env_adapters")
env_adapters.__path__ = []
base_adapter = types.ModuleType("core.env_adapters.base_adapter")
base_adapter.BaseEnvAdapter = object
base_adapter.Pose3D = object
base_adapter.CameraParams = object
base_adapter.TrackedObject = object
base_adapter.InteractableObject = object
sys.modules["core"] = core
sys.modules["core.env_adapters"] = env_adapters
sys.modules["core.env_adapters.base_adapter"] = base_adapter

logging_utils = types.ModuleType("utils.logging_utils")
logging_utils.SteerLogger = lambda *args, **kwargs: types.SimpleNamespace(
    info=lambda *a, **k: None,
    debug=lambda *a, **k: None,
    warning=lambda *a, **k: None,
    error=lambda *a, **k: None,
)
sys.modules["utils"] = types.ModuleType("utils")
sys.modules["utils.logging_utils"] = logging_utils

pipeline = types.ModuleType("lerobot.processor.pipeline")
pipeline.PolicyProcessorPipeline = object
pipeline.ProcessorStep = object
env_processor = types.ModuleType("lerobot.processor.env_processor")
env_processor.LiberoProcessorStep = object
constants = types.ModuleType("lerobot.utils.constants")
constants.OBS_ENV_STATE = "observation.environment_state"
constants.OBS_IMAGE = "observation.image"
constants.OBS_IMAGES = "observation.images"
constants.OBS_STATE = "observation.state"
constants.OBS_STR = "observation"
sys.modules["lerobot"] = types.ModuleType("lerobot")
sys.modules["lerobot.processor"] = types.ModuleType("lerobot.processor")
sys.modules["lerobot.processor.pipeline"] = pipeline
sys.modules["lerobot.processor.env_processor"] = env_processor
sys.modules["lerobot.utils"] = types.ModuleType("lerobot.utils")
sys.modules["lerobot.utils.constants"] = constants

libero = types.ModuleType("libero")
libero_libero = types.ModuleType("libero.libero")
libero_envs = types.ModuleType("libero.libero.envs")
libero_libero.benchmark = types.SimpleNamespace(get_benchmark_dict=lambda: {})
libero_libero.get_libero_path = lambda name: "/tmp"
libero_envs.OffScreenRenderEnv = object
sys.modules["libero"] = libero
sys.modules["libero.libero"] = libero_libero
sys.modules["libero.libero.envs"] = libero_envs

spec = importlib.util.spec_from_file_location("core.env_adapters.libero_adapter", adapter_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
_parse_perturbation_type = module._parse_perturbation_type

base, flags = _parse_perturbation_type("libero_object")
assert base == "libero_object", (base, flags)
assert not any(flags.values()), flags

base, flags = _parse_perturbation_type("libero_object_object")
assert base == "libero_object", (base, flags)
assert flags["use_object"] is True, flags
assert flags["use_swap"] is False, flags
assert flags["use_language"] is False, flags
assert flags["use_task"] is False, flags
assert flags["use_environment"] is False, flags
'''.replace("__ADAPTER_PATH__", str(adapter_path))
    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
