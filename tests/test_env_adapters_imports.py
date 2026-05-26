import subprocess
import sys
from pathlib import Path

import yaml


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


def test_main_import_does_not_require_lerobot_policy_dependencies():
    script = r'''
import builtins

original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "lerobot" or name.startswith("lerobot."):
        raise ModuleNotFoundError("No module named 'lerobot'", name="lerobot")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import

import main

assert main.Main is not None
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
    if name == "lerobot.processor.pipeline":
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


def test_libero_env_format_raw_obs_preserves_rdt_raw_keys_unflipped():
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
import core.env_adapters.libero_adapter as adapter

class FakeController:
    ee_ori_mat = np.eye(3)

class FakeRobot:
    controller = FakeController()

class FakeRobosuiteEnv:
    robots = [FakeRobot()]

env = adapter.LiberoEnv.__new__(adapter.LiberoEnv)
env.camera_name = ["agentview_image", "robot0_eye_in_hand_image"]
env.camera_name_mapping = {
    "agentview_image": "image",
    "robot0_eye_in_hand_image": "image2",
}
env.task_description = "pick up the bowl"
env._env = FakeRobosuiteEnv()

agent_image = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
wrist_image = np.arange(12, 24, dtype=np.uint8).reshape(2, 2, 3)
joint_pos = np.linspace(0.0, 0.6, 7)
gripper_qpos = np.array([0.01, 0.02])

obs = env._format_raw_obs({
    "agentview_image": agent_image,
    "robot0_eye_in_hand_image": wrist_image,
    "robot0_joint_pos": joint_pos,
    "robot0_joint_vel": np.zeros(7),
    "robot0_gripper_qpos": gripper_qpos,
    "robot0_gripper_qvel": np.zeros(2),
    "robot0_eef_pos": np.zeros(3),
    "robot0_eef_quat": np.array([0.0, 0.0, 0.0, 1.0]),
})

np.testing.assert_array_equal(obs["agentview_image"], agent_image)
np.testing.assert_array_equal(obs["robot0_eye_in_hand_image"], wrist_image)
np.testing.assert_array_equal(obs["robot0_joint_pos"], joint_pos)
np.testing.assert_array_equal(obs["robot0_gripper_qpos"], gripper_qpos)
assert obs["task"] == "pick up the bowl"
assert "observation.images.image" in obs
assert "observation.robot_state" in obs
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr


def test_libero_adapter_policy_observation_preserves_rdt_raw_keys_after_preprocessor():
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

class DroppingPreprocessor:
    def __call__(self, obs):
        return {"observation.state": torch.ones(1, 9)}

class FakeCurrentEnv:
    task_description = "place the mug"

libero_adapter = adapter.LiberoAdapter.__new__(adapter.LiberoAdapter)
libero_adapter._env = [FakeCurrentEnv()]
libero_adapter.current_task_idx = 0
libero_adapter.env_preprocessor = DroppingPreprocessor()
libero_adapter._diag_p1_done = True
libero_adapter._diag_p2_done = True

agent_image = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
wrist_image = np.arange(12, 24, dtype=np.uint8).reshape(2, 2, 3)
joint_pos = np.linspace(0.0, 0.6, 7)
gripper_qpos = np.array([0.01, 0.02])
libero_adapter._last_obs = {
    "agentview_image": agent_image,
    "robot0_eye_in_hand_image": wrist_image,
    "robot0_joint_pos": joint_pos,
    "robot0_gripper_qpos": gripper_qpos,
    "observation.images.image": torch.zeros(1, 3, 2, 2),
}

obs = libero_adapter.get_policy_observation(sample_num=1)

np.testing.assert_array_equal(obs["agentview_image"], agent_image)
np.testing.assert_array_equal(obs["robot0_eye_in_hand_image"], wrist_image)
np.testing.assert_array_equal(obs["robot0_joint_pos"], joint_pos)
np.testing.assert_array_equal(obs["robot0_gripper_qpos"], gripper_qpos)
assert obs["task"] == ["place the mug"]
assert "observation.state" in obs
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


def test_libero_adapter_init_wires_env_config_into_create_libero_envs():
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

captured = {}

class FakeCurrentEnv:
    task_id = 0
    task_description = "fake task"
    task = "fake"

def fake_create_libero_envs(*args, **kwargs):
    captured["args"] = args
    captured["kwargs"] = kwargs
    return [FakeCurrentEnv()]

adapter.create_libero_envs = fake_create_libero_envs

env_config = {
    "suite_name": "libero_object",
    "camera_name": "agentview_image, robot0_eye_in_hand_image",
    "auto_apply_perturbations": False,
    "task_ids_filter": [2],
    "observation_width": 128,
    "observation_height": 129,
    "visualization_width": 640,
    "visualization_height": 641,
    "num_steps_wait": 5,
    "max_episode_steps": 600,
}

libero_adapter = adapter.LiberoAdapter(None, env_config, device="cpu")

assert libero_adapter.task_num == 1
assert captured["args"] == (
    "libero_object",
    "agentview_image, robot0_eye_in_hand_image",
    False,
    [2],
)
assert captured["kwargs"] == {
    "observation_width": 128,
    "observation_height": 129,
    "visualization_width": 640,
    "visualization_height": 641,
    "num_steps_wait": 5,
    "max_episode_steps": 600,
}
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr


def test_libero_env_max_episode_steps_override_and_num_steps_wait_are_exact():
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

adapter.LiberoEnv._make_envs_task = lambda self, task_suite, task_id: object()

env = adapter.LiberoEnv(
    task_suite=object(),
    task_id=0,
    task_suite_name="libero_10",
    init_states=False,
    num_steps_wait=5,
    max_episode_steps=600,
)

assert env.num_steps_wait == 5
assert env._max_episode_steps == 600
'''
    result = _run_python(script)

    assert result.returncode == 0, result.stderr


def test_libero_backend_config_defaults_match_eval_parity():
    config_path = Path(__file__).resolve().parents[1] / "configs" / "backend" / "libero.yaml"

    config = yaml.safe_load(config_path.read_text())
    libero_config = config["libero"]

    assert libero_config["observation_width"] == 128
    assert libero_config["observation_height"] == 128
    assert libero_config["num_steps_wait"] == 5
    assert libero_config["max_episode_steps"] == 720
    assert libero_config["visualization_width"] == 640
    assert libero_config["visualization_height"] == 640


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
