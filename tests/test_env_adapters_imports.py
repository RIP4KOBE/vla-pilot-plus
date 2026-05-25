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


def test_libero_dummy_action_is_all_zero_7d_action():
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

assert adapter.get_libero_dummy_action() == [0, 0, 0, 0, 0, 0, 0]
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
    ("step", (0, 0, 0, 0, 0, 0, 0)),
    ("step", (0, 0, 0, 0, 0, 0, 0)),
    ("step", (0, 0, 0, 0, 0, 0, 0)),
]
assert formatted_raw_obs == ["step_obs_3"]
assert observation == {"formatted": "step_obs_3"}
assert info == {"is_success": False}
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr


def test_create_libero_envs_forwards_libero_env_configuration():
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

class FakeSuite:
    tasks = [object(), object()]

captured_kwargs = []

class FakeLiberoEnv:
    def __init__(self, **kwargs):
        captured_kwargs.append(kwargs)

adapter._get_suite = lambda suite_name: FakeSuite()
adapter.LiberoEnv = FakeLiberoEnv

envs = adapter.create_libero_envs(
    suite_name="libero_object",
    camera_name="agentview_image, robot0_eye_in_hand_image",
    auto_apply_perturbations=False,
    task_ids_filter=[1],
    observation_width=128,
    observation_height=129,
    visualization_width=640,
    visualization_height=641,
    num_steps_wait=5,
    max_episode_steps=600,
)

assert len(envs) == 1
kwargs = captured_kwargs[0]
assert kwargs["observation_width"] == 128
assert kwargs["observation_height"] == 129
assert kwargs["visualization_width"] == 640
assert kwargs["visualization_height"] == 641
assert kwargs["num_steps_wait"] == 5
assert kwargs["max_episode_steps"] == 600
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr


def test_libero_adapter_step_binarizes_gripper_before_sending_numpy_action():
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

import numpy as np
import torch
import core.env_adapters.libero_adapter as adapter

class IdentityPipeline:
    def __call__(self, transition):
        return transition

class FakeCurrentEnv:
    task_id = 3
    _max_episode_steps = 100
    task_description = "fake task"

    def __init__(self):
        self.received_action = None

    def step(self, action):
        self.received_action = action.copy()
        return {"obs": True}, 0.0, False, False, {}

fake_env = FakeCurrentEnv()
libero_adapter = adapter.LiberoAdapter.__new__(adapter.LiberoAdapter)
libero_adapter.env_postprocessor = IdentityPipeline()
libero_adapter._env = [fake_env]
libero_adapter.current_task_idx = 0
libero_adapter.episode_step = 0

action = torch.tensor([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2], dtype=torch.float64)
libero_adapter.step(action)

assert isinstance(fake_env.received_action, np.ndarray)
assert fake_env.received_action.dtype == np.float32
assert fake_env.received_action[-1] == 1.0
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr
