"""Regression checks for the replay worker's descriptor-exhaustion hang."""

import errno
from pathlib import Path
import signal
from types import SimpleNamespace

import pytest

from patches.libero_pro import (
    disable_mujoco_316_asset_cache,
    libero_initialization_deadline,
    patch_control_env_reset,
)


class PlacementError(Exception):
    pass


def _wrapper(reset, **limits):
    class Control:
        def reset(self):
            raise AssertionError("upstream reset must be replaced")

    patch_control_env_reset(Control, PlacementError, **limits)
    wrapper = Control()
    wrapper.env = SimpleNamespace(reset=reset)
    return wrapper


def test_descriptor_exhaustion_propagates_without_retry():
    calls = []

    def reset():
        calls.append(1)
        raise OSError(errno.EMFILE, "Too many open files")

    with pytest.raises(OSError) as caught:
        _wrapper(reset).reset()
    assert caught.value.errno == errno.EMFILE
    assert len(calls) == 1


def test_placement_retries_recover_and_are_bounded():
    calls = []

    def reset():
        calls.append(1)
        if len(calls) < 3:
            raise PlacementError("overlap")
        return {"observation": "ready"}

    assert _wrapper(reset, max_attempts=3).reset() == {"observation": "ready"}
    calls.clear()
    with pytest.raises(PlacementError):
        _wrapper(reset, max_attempts=2).reset()
    assert len(calls) == 2


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="POSIX alarm required")
def test_reset_deadline_interrupts_busy_loop_and_restores_handler():
    previous = signal.getsignal(signal.SIGALRM)

    def busy_reset():
        while True:
            pass

    with pytest.raises(TimeoutError, match="initialization exceeded"):
        _wrapper(busy_reset, timeout_seconds=0.02).reset()
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="POSIX alarm required")
def test_nested_initialization_preserves_outer_deadline():
    with pytest.raises(TimeoutError, match="initialization exceeded"):
        with libero_initialization_deadline(0.02):
            with libero_initialization_deadline(100):
                while True:
                    pass
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_adapter_close_releases_all_environments_and_is_idempotent():
    adapter_module = pytest.importorskip("core.env_adapters.libero_adapter")
    closed = []
    adapter = object.__new__(adapter_module.LiberoAdapter)
    adapter._env = [SimpleNamespace(close=lambda: closed.append(1))]
    adapter._last_obs = {"cached": True}
    adapter._robot_state = {"cached": True}
    adapter.close()
    adapter.close()
    assert closed == [1]
    assert adapter._env == []
    assert adapter._last_obs is None
    assert adapter._robot_state is None


def test_adapter_close_cleans_other_environments_after_one_failure():
    adapter_module = pytest.importorskip("core.env_adapters.libero_adapter")
    closed = []

    def failed_close():
        closed.append(1)
        raise RuntimeError("close failed")

    adapter = object.__new__(adapter_module.LiberoAdapter)
    adapter._env = [
        SimpleNamespace(close=failed_close),
        SimpleNamespace(close=lambda: closed.append(2)),
    ]
    with pytest.raises(RuntimeError, match="close failed"):
        adapter.close()
    assert closed == [1, 2]
    assert adapter._env == []
    assert adapter._last_obs is None


def test_pinned_mujoco_repeated_obj_compile_does_not_leak(tmp_path):
    mujoco = pytest.importorskip("mujoco")
    if mujoco.__version__ != "3.1.6" or not Path("/proc/self/fd").is_dir():
        pytest.skip("regression requires pinned MuJoCo 3.1.6 on Linux")
    import numpy as np

    mesh = tmp_path / "tetra.obj"
    mesh.write_text(
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\n"
        "f 1 3 2\nf 1 2 4\nf 1 4 3\nf 2 3 4\n"
    )
    xml = (
        f'<mujoco><asset><mesh name="mesh" file="{mesh}"/></asset>'
        '<worldbody><geom type="mesh" mesh="mesh"/></worldbody></mujoco>'
    )
    reference = mujoco.MjModel.from_xml_string(xml)
    assert disable_mujoco_316_asset_cache()
    baseline = len(list(Path("/proc/self/fd").iterdir()))
    for _ in range(25):
        model = mujoco.MjModel.from_xml_string(xml)
        np.testing.assert_array_equal(model.mesh_vert, reference.mesh_vert)
        np.testing.assert_array_equal(model.mesh_face, reference.mesh_face)
    assert len(list(Path("/proc/self/fd").iterdir())) == baseline
