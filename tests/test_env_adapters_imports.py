import subprocess
import sys


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
    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
