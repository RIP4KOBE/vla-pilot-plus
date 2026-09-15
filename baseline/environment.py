"""A separate simulator instance, with existing PRO resources opened read-only."""
import os
from pathlib import Path
import time

from .simulator_startup import startup_deadline, startup_seconds


def simulator_status(adapter):
    """Read Robosuite's terminal counter, which LIBERO masks in step()."""
    wrapper = adapter._get_current_robosuite_env()
    env = getattr(wrapper, "env", wrapper)
    return {"done": bool(env.done), "timestep": int(env.timestep), "horizon": int(env.horizon)}


def step_environment(adapter, action):
    observation, reward, terminated, truncated, info = adapter.step(action)
    state = simulator_status(adapter)
    success = bool(info.get("success", info.get("is_success", False)))
    # Do not change ignore_done or extend the horizon to conceal the error.
    # The next call would otherwise throw before returning its transition.
    timeout = state["done"] and not success
    info = {**info, "simulator_timestep": state["timestep"], "simulator_horizon": state["horizon"]}
    if timeout:
        info["TimeLimit.truncated"] = True
    return observation, reward, terminated, bool(truncated or timeout), info


def use_perturbed_instruction(adapter, context):
    # create_libero_envs normally enables BDDL language through its resource
    # generation branch. Baselines disable generation, but must still consume
    # the same already-generated language/task perturbation as the main run.
    if context["perturbation_variant"] in ("use_language", "use_task"):
        for env in adapter._env:
            instruction = env._extract_language_from_bddl(env.bddl_file_name)
            if not instruction or not instruction.strip():
                raise ValueError("PRO language/task perturbation has no BDDL instruction")
            env.task_description = instruction
            env.read_language_from_bddl = True


def make_environment(cfg, context):
    # Set these before importing MuJoCo/PyOpenGL in this baseline process.
    os.environ.setdefault("MUJOCO_GL", "egl")
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    # The existing adapter's EGL compatibility patch selects render_device_id
    # independently of CUDA. Robosuite otherwise mistakes the two namespaces
    # for each other at import (hgpu1's working headless renderer is EGL 8).
    os.environ.pop("MUJOCO_EGL_DEVICE_ID", None)
    from core.env_adapters import create_adapter
    settings = {
        "suite_name": context["runtime_suite"], "task_id": context["task_index"],
        "task_ids_filter": [context["task_index"]], "episode_num": 1,
        "camera_name": "agentview_image, robot0_eye_in_hand_image",
        "obs_type": "pixels_agent_pos", "render_mode": "rgb_array",
        "render_gpu_device_id": cfg["render_gpu_device_id"],
        "observation_width": cfg["observation_width"], "observation_height": cfg["observation_height"],
        "visualization_width": 128, "visualization_height": 128,
        "init_states": True, "auto_reset": False, "num_steps_wait": cfg["num_steps_wait"],
        "max_episode_steps": cfg["max_episode_steps"], "auto_apply_perturbations": False,
    }
    seconds = startup_seconds(cfg)
    started = time.monotonic()
    with startup_deadline(seconds):
        adapter = create_adapter("libero", settings, device=cfg["device"])
    adapter._baseline_initialization_seconds = seconds
    if seconds is not None:
        print(f"baseline simulator initialized in {time.monotonic() - started:.2f}s (limit {seconds:g}s)", flush=True)
    try:
        use_perturbed_instruction(adapter, context)
        return adapter
    except Exception:
        adapter.close()
        raise


def reset_environment(adapter, context):
    with startup_deadline(getattr(adapter, "_baseline_initialization_seconds", None)):
        adapter.reset(seed=context["seed"], init_state_id=context["init_state_id"])
    actual = adapter.get_context_provenance()
    for key in ("runtime_suite", "task_id", "task_index", "perturbation_variant", "init_state_id"):
        if str(actual[key]) != str(context[key]):
            raise ValueError(f"PRO context mismatch for {key}: {actual[key]} != {context[key]}")
    actual["policy_instruction"] = adapter._env[adapter.current_task_idx].task_description
    return actual
