import subprocess
import sys


def _run_python(script):
    return subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
    )


def test_env_adapters_import_does_not_require_pybullet():
    script = r'''
import builtins

original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "pybullet":
        raise ModuleNotFoundError("blocked pybullet")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

from core.env_adapters import BaseEnvAdapter, create_adapter

assert BaseEnvAdapter is not None
assert callable(create_adapter)
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr


def test_libero_adapter_reraises_missing_lerobot_transitive_dependency():
    script = r'''
import builtins
import sys
import types

libero = types.ModuleType("libero")
libero_libero = types.ModuleType("libero.libero")
libero_envs = types.ModuleType("libero.libero.envs")
libero_libero.benchmark = object()
libero_libero.get_libero_path = lambda name: "/tmp"
libero_envs.OffScreenRenderEnv = object
sys.modules["libero"] = libero
sys.modules["libero.libero"] = libero_libero
sys.modules["libero.libero.envs"] = libero_envs

original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "accelerate":
        raise ModuleNotFoundError("No module named 'accelerate'", name="accelerate")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

import core.env_adapters.libero_adapter
'''
    result = _run_python(script)

    assert result.returncode != 0
    assert "accelerate" in result.stderr


def test_libero_adapter_uses_fallback_when_lerobot_unavailable():
    script = r'''
import builtins
import sys
import types

libero = types.ModuleType("libero")
libero_libero = types.ModuleType("libero.libero")
libero_envs = types.ModuleType("libero.libero.envs")
libero_libero.benchmark = object()
libero_libero.get_libero_path = lambda name: "/tmp"
libero_envs.OffScreenRenderEnv = object
sys.modules["libero"] = libero
sys.modules["libero.libero"] = libero_libero
sys.modules["libero.libero.envs"] = libero_envs

original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "lerobot" or name.startswith("lerobot."):
        raise ModuleNotFoundError("No module named 'lerobot'", name="lerobot")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

import core.env_adapters.libero_adapter as adapter

assert adapter.OBS_IMAGES == "observation.images"
assert adapter.OBS_STATE == "observation.state"
assert adapter.LiberoProcessorStep is not None
assert adapter.PolicyProcessorPipeline is not None
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr


def test_libero_env_reset_applies_init_state_after_reset_and_stabilizes():
    script = r'''
import builtins
import sys
import types

libero = types.ModuleType("libero")
libero_libero = types.ModuleType("libero.libero")
libero_envs = types.ModuleType("libero.libero.envs")
libero_libero.benchmark = object()
libero_libero.get_libero_path = lambda name: "/tmp"
libero_envs.OffScreenRenderEnv = object
sys.modules["libero"] = libero
sys.modules["libero.libero"] = libero_libero
sys.modules["libero.libero.envs"] = libero_envs

original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "lerobot" or name.startswith("lerobot."):
        raise ModuleNotFoundError("No module named 'lerobot'", name="lerobot")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

import core.env_adapters.libero_adapter as adapter


class FakeEnv:
    def __init__(self):
        self.calls = []
        self.step_count = 0

    def seed(self, seed):
        pass

    def reset(self):
        self.calls.append("reset")
        return "reset_obs"

    def set_init_state(self, init_state):
        self.calls.append(("set_init_state", init_state))
        return "init_state_obs"

    def step(self, action):
        self.step_count += 1
        self.calls.append(("step", tuple(action)))
        return f"step_obs_{self.step_count}", 0.0, False, {}


env = adapter.LiberoEnv.__new__(adapter.LiberoEnv)
fake = FakeEnv()
env._env = fake
env.init_states = True
env._init_states = ["state-0"]
env._init_state_id = 0
env.num_steps_wait = 3
formatted_raw_obs = []

def format_raw_obs(raw_obs):
    formatted_raw_obs.append(raw_obs)
    return {"formatted": raw_obs}

env._format_raw_obs = format_raw_obs

observation, info = env.reset(seed=123)

assert fake.calls == [
    "reset",
    ("set_init_state", "state-0"),
    ("step", (0, 0, 0, 0, 0, 0, -1)),
    ("step", (0, 0, 0, 0, 0, 0, -1)),
    ("step", (0, 0, 0, 0, 0, 0, -1)),
]
assert formatted_raw_obs == ["step_obs_3"]
assert observation == {"formatted": "step_obs_3"}
assert info == {"is_success": False}
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr
