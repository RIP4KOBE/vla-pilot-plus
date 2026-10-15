"""N23 CPU-only semantics and actual static-metadata reader with controller stubs.

Controller methods are parsed from installed source, never imported or called;
no robosuite/MuJoCo instance, external service or simulator is created.
"""
import ast
import copy
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from core.qd_actuator_clipped_quality import ActuatorClippedContract, actuator_clipped_quality
from core.qd_executed_quality import TEMPLATE, recognize_executed_prefix_provider
from test_qd_executed_quality import provider


def static_adapter_fixture():
    root = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages/robosuite/controllers"
    namespace = {"__name__": "robosuite.controllers.osc"}
    for filename, classname, methods in (("base_controller.py", "Controller", {"scale_action"}),
                                         ("osc.py", "OperationalSpaceController", {"set_goal", "name"})):
        source = root / filename
        cls = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef) and n.name == classname)
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in methods]
        cls.decorator_list = []
        cls.keywords = []
        if classname == "Controller":
            cls.bases = []
        exec(compile(ast.Module(body=[cls], type_ignores=[]), str(source), "exec"), namespace)
    controller = namespace["OperationalSpaceController"]()
    controller.name_suffix = "POSE"
    controller.use_delta = controller.use_ori = True
    controller.control_dim = 6
    controller.impedance_mode = "fixed"
    controller.input_min = np.full(6, -1., dtype=np.float64)
    controller.input_max = np.ones(6, dtype=np.float64)
    controller.output_min = np.array([-.05] * 3 + [-.5] * 3)
    controller.output_max = -controller.output_min
    env = SimpleNamespace(robots=[SimpleNamespace(controller=controller)])
    wrapper = SimpleNamespace(_env=env)
    return SimpleNamespace(_env=[wrapper], current_task_idx=0, current_episode_idx=1,
                           _get_current_robosuite_env=lambda: env)


def native_inputs(dtype, commands=None):
    translations = (torch.tensor([
        [[2.2, -.2, -3.3], [-2.2, .4, 1.3], [.9, -.8, .7], [0, 0, 0],
         [.7, 2.8, 0], [-.8, -2.1, .2], [0., 0., -.2], [9., 9., 9.]],
        [[.1, -.2, .3]] * 7 + [[100., -100., 100.]],
        [[1., -1., 0.]] * 8,
    ], dtype=dtype) if commands is None else commands)
    origins = [torch.tensor([.12317, -.17312, .23141], dtype=torch.float64) for _ in translations]
    projected = torch.stack([torch.cat((o.to(dtype)[None], o.to(dtype) + torch.cumsum(a * .01, 0)))
                             for a, o in zip(translations, origins)])
    keypoints = torch.tensor([[.1124, -.071, .3154]], dtype=dtype)
    fn = provider()
    raw = torch.stack([fn(keypoints, p[None, 1:8]).to(dtype) for p in projected])
    return translations, origins, projected, keypoints, raw


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_native_clip_componentwise_both_signs_seven_points_and_raw_bits(dtype):
    args = native_inputs(dtype)
    translations, origins, projected, keypoints, raw = args
    before = translations.clone()
    quality, changed = actuator_clipped_quality(*args)
    assert changed.tolist() == [True, False, False]
    expected = []
    fn = provider()
    for action, origin in zip(translations, origins):
        bounded = torch.minimum(torch.maximum(action, torch.full_like(action, -1)), torch.ones_like(action))
        xyz = origin.to(dtype) + torch.cumsum(bounded * .01, 0)
        expected.append(fn(keypoints, xyz[None, :7]).to(dtype))
    assert torch.equal(quality, torch.stack(expected))
    assert torch.equal(quality[1:].view(torch.uint8), raw[1:].view(torch.uint8))
    assert quality[0] != raw[0]
    assert torch.equal(translations, before)
    # t8 may exceed limits but cannot change the quality or trigger recomputation.
    assert torch.equal(quality[1].view(1).view(torch.uint8), raw[1].view(1).view(torch.uint8))
    # Native BF16 projection rounds multiply/cumsum/add, unlike FP64 diagnostics.
    if dtype == torch.bfloat16:
        wrong = origins[0].double() + torch.cumsum(translations[0].double().clamp(-1, 1) * .01, 0)
        wrong_q = fn(keypoints.double(), wrong[None, :7]).to(dtype)
        assert quality[0] != wrong_q


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_no_clip_is_bitwise_raw_including_signed_zero(dtype):
    args = list(native_inputs(dtype, torch.zeros(3, 8, 3, dtype=dtype)))
    args[-1] = torch.tensor([-0., .314, -.217], dtype=dtype)
    quality, changed = actuator_clipped_quality(*args)
    assert not changed.any()
    assert torch.equal(quality.view(torch.uint8), args[-1].view(torch.uint8))


@pytest.mark.parametrize("fault", ["origin", "raw_projection", "dtype", "nan"])
def test_native_invalid_inputs_fail_closed(fault):
    args = list(native_inputs(torch.float32))
    if fault == "origin": args[1][0][0] += .01
    if fault == "raw_projection": args[2][0, 5, 0] += .01
    if fault == "dtype": args[3] = args[3].double()
    if fault == "nan": args[0][0, 0, 0] = float("nan")
    with pytest.raises((RuntimeError, ValueError, FloatingPointError)):
        actuator_clipped_quality(*args)


def make_contract(adapter=None, index=0):
    fn = provider(TEMPLATE.replace("[0], dtype", f"[{index}], dtype"))
    base, _ = recognize_executed_prefix_provider([fn], torch.zeros(3, 3))
    adapter = adapter or static_adapter_fixture()
    return ActuatorClippedContract(base, adapter), fn, adapter


@pytest.mark.parametrize("fault", ["bounds", "array_shape", "int_array", "delta", "impedance", "dimension", "type", "missing"])
def test_actual_static_reader_rejects_incompatible_controller(fault):
    adapter = static_adapter_fixture()
    controller = adapter._env[0]._env.robots[0].controller
    if fault == "bounds": controller.input_max[0] = .5
    if fault == "array_shape": controller.input_max = np.ones(3)
    if fault == "int_array": controller.input_max = np.ones(6, dtype=np.int64)
    if fault == "delta": controller.use_delta = False
    if fault == "impedance": controller.impedance_mode = "variable"
    if fault == "dimension": controller.control_dim = 3
    if fault == "type": adapter._env[0]._env.robots[0].controller = SimpleNamespace()
    if fault == "missing": del adapter._env
    with pytest.raises((RuntimeError, AttributeError)):
        make_contract(adapter)


@pytest.mark.parametrize("fault", ["reset", "episode", "task", "controller", "bounds", "method", "provider"])
def test_bound_context_and_provider_cannot_drift(fault):
    contract, fn, adapter = make_contract()
    contract.validate([fn])
    assert contract.metadata["semantics"]["input_min"] == [-1.] * 6
    if fault == "reset": adapter._env[0]._actuator_quality_reset_generation += 1
    if fault == "episode": adapter.current_episode_idx += 1
    if fault == "task": adapter.current_task_idx = 1
    if fault == "controller": adapter._env[0]._env.robots[0].controller = static_adapter_fixture()._env[0]._env.robots[0].controller
    if fault == "bounds": adapter._env[0]._env.robots[0].controller.input_min[0] = -.9
    if fault == "method": type(adapter._env[0]._env.robots[0].controller).set_goal = lambda self, action: None
    if fault == "provider": fn._guidance_source_text = fn._guidance_source_text.replace("3.0", "4.0")
    with pytest.raises(RuntimeError): contract.validate([fn])


def test_nonzero_target_fails_and_reset_instrumentation_is_passive():
    with pytest.raises(RuntimeError, match="target0"): make_contract(index=1)
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "core/env_adapters/libero_adapter.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LiberoEnv")
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "reset"]
    cls.bases = [ast.Name(id="Base", ctx=ast.Load())]
    class Base:
        def reset(self, seed=None): pass
    ns = {"Base": Base}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), "libero_adapter.py", "exec"), ns)
    wrapper = ns["LiberoEnv"]()
    wrapper._env = SimpleNamespace(seed=lambda _: None, reset=lambda: {"test": 1})
    wrapper.init_states = False; wrapper.num_steps_wait = 0
    wrapper._format_raw_obs = lambda x: x
    assert wrapper.reset()[0] == {"test": 1}
    assert not hasattr(wrapper, "_actuator_quality_reset_generation")
    wrapper._actuator_quality_reset_generation = 0
    assert wrapper.reset()[0] == {"test": 1}
    assert wrapper._actuator_quality_reset_generation == 1


def test_exact_n7_delta_and_closed_cpu_profile_expansion():
    import json
    from scripts import qd_ed_final_runner as runner
    root = Path(__file__).resolve().parents[1]
    n7 = json.loads((root / "configs/qd_ed_final/candidate_n7.json").read_text())
    n23 = json.loads((root / "configs/qd_ed_final/candidate_n23.json").read_text())
    baseline = json.loads((root / "configs/qd_ed_final/baseline_profiles.json").read_text())["profiles"]["Q0"]
    saved = copy.deepcopy(baseline)
    assert {k: v for k, v in n23["profile"].items() if k != "qd_quality_mode"} == n7["profile"]
    result = runner.expand_candidate("N23", n23, baseline)
    assert baseline == saved
    for name in ("qd_descriptor", "qd_final_selection_mode", "qd_quality_mode"):
        assert result["resolved_eds_config"][name] == n23["profile"][name]
        assert result["static_override_values"]["main.eds_config." + name] == n23["profile"][name]
    for name, value in (("qd_quality_mode", "close_then_lift_v1"), ("cem_iters", 11),
                        ("qd_descriptor", "target_relative_endpoint_xy"),
                        ("qd_final_selection_mode", "terminal_population_v1")):
        changed = copy.deepcopy(n23); changed["profile"][name] = value
        with pytest.raises(runner.GateError): runner.expand_candidate("N23", changed, baseline)
