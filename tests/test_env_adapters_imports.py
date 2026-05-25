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
