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


def test_temp_suite_preserves_enabled_flags_from_evaluation_config(tmp_path):
    adapter_path = Path(__file__).resolve().parents[1] / "core" / "env_adapters" / "libero_adapter.py"
    root = tmp_path / "libero_pro"
    bddl_root = tmp_path / "bddl_files"
    init_root = tmp_path / "init_files"
    (root / "libero_ood").mkdir(parents=True)
    (bddl_root / "libero_object").mkdir(parents=True)
    (init_root / "libero_object").mkdir(parents=True)
    (root / "evaluation_config.yaml").write_text(
        "\n".join(
            [
                "use_environment: true",
                "use_swap: false",
                "use_object: false",
                "use_language: false",
                "use_task: false",
                "ood_task_configs: {}",
                "perturbation_mapping:",
                "  use_environment: env",
                "  use_swap: swap",
                "  use_object: object",
                "  use_language: lan",
                "  use_task: task",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    script = r'''
import importlib.util
import sys
import types
from pathlib import Path

adapter_path = "__ADAPTER_PATH__"
libero_pro_root = Path("__LIBERO_PRO_ROOT__")
bddl_root = Path("__BDDL_ROOT__")
init_root = Path("__INIT_ROOT__")
seen = {}

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
libero_libero.get_libero_path = lambda name: str(
    bddl_root if name == "bddl_files" else init_root
)
libero_envs.OffScreenRenderEnv = object
sys.modules["libero"] = libero
sys.modules["libero.libero"] = libero_libero
sys.modules["libero.libero.envs"] = libero_envs

spec = importlib.util.spec_from_file_location("core.env_adapters.libero_adapter", adapter_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def fake_create_env(configs):
    seen.update(configs)
    temp_bddl = bddl_root / "libero_object_temp"
    temp_init = init_root / "libero_object_temp"
    temp_bddl.mkdir(parents=True, exist_ok=True)
    temp_init.mkdir(parents=True, exist_ok=True)
    (temp_bddl / "task.bddl").write_text("perturbed", encoding="utf-8")
    (temp_init / "task.pruned_init").write_text("init", encoding="utf-8")

module.LIBERO_PRO_PATH = libero_pro_root
module.PERTURBATION_AVAILABLE = True
module.perturbation_module = types.SimpleNamespace(create_env=fake_create_env)

actual, read_language = module._apply_perturbations("libero_object_temp")

assert actual == "libero_object_temp"
assert read_language is False
assert seen["use_environment"] is True, seen
assert seen["use_swap"] is False, seen
assert seen["use_object"] is False, seen
assert seen["use_language"] is False, seen
assert seen["use_task"] is False, seen
assert (bddl_root / "libero_object_temp" / "log.txt").read_text() == "False,False,False,False,True"
'''
    script = script.replace("__ADAPTER_PATH__", str(adapter_path))
    script = script.replace("__LIBERO_PRO_ROOT__", str(root))
    script = script.replace("__BDDL_ROOT__", str(bddl_root))
    script = script.replace("__INIT_ROOT__", str(init_root))

    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
