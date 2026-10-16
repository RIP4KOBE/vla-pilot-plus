import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from baseline import vls_guidance
from baseline.io import read_json, write_json
from baseline.vls_guidance import InvalidGuidanceResponse, install_guidance_validation, normalize_source, validate_program
from rsi.utils.guidance_utils import UnsafeGuidanceCode, load_functions_from_txt, validate_guidance_ast


GOOD = """def stage1_guidance(keypoints, action_sequence):
    import torch
    delta = action_sequence - keypoints[1]
    return -(delta.square().sum(dim=-1)).mean()
"""


def metadata():
    return {"init_keypoint_positions": np.linspace(0.1, 0.6, 27).reshape(9, 3), "num_keypoints": 9}


def test_import_is_replaced_by_existing_namespace_without_changing_reward_or_gradient(tmp_path):
    with pytest.raises(UnsafeGuidanceCode, match="Import"):
        validate_guidance_ast(GOOD)
    normalized, removed = normalize_source(GOOD)
    assert removed == [2] and "import" not in normalized
    path = tmp_path / "reward.txt"
    path.write_text(normalized)
    fn, = load_functions_from_txt(path, validate=False)
    kp = torch.tensor(metadata()["init_keypoint_positions"], dtype=torch.float32)
    a = torch.linspace(-0.1, 0.1, 60).reshape(2, 10, 3).requires_grad_(True)
    value = fn(kp, a)
    expected = -((a - kp[1]).square().sum(dim=-1)).mean()
    assert torch.equal(value, expected)
    assert torch.equal(torch.autograd.grad(value, a, retain_graph=True)[0], torch.autograd.grad(expected, a)[0])
    # The shared execution guard remains strict even after normalization runs.
    with pytest.raises(UnsafeGuidanceCode, match="Import"):
        validate_guidance_ast(GOOD)


@pytest.mark.parametrize("statement", ["import os", "import torch as t", "from torch import norm",
    "import torch, os", "x = torch.load('anything')", "x = open('anything')"])
def test_normalization_does_not_enable_other_imports_or_unsafe_operations(statement):
    code = GOOD.replace("    import torch", "    import torch\n    " + statement)
    with pytest.raises((UnsafeGuidanceCode, InvalidGuidanceResponse)):
        normalize_source(code)


def test_torch_shadowing_cannot_change_import_semantics():
    with pytest.raises(InvalidGuidanceResponse, match="loader-provided"):
        normalize_source(GOOD.replace("    delta =", "    torch = keypoints\n    delta ="))


def test_exact_failed_episode_program_passes_native_loader_and_all_gradient_probes(tmp_path):
    raw = (Path(__file__).parent / "fixtures/vls_episode007_import_torch.txt").read_text()
    code = raw.strip().removeprefix("```python").removesuffix("```").strip()
    tree = ast.parse(code)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            (tmp_path / f"{node.name}.txt").write_text(ast.get_source_segment(code, node) + "\n")
    write_json(tmp_path / "metadata.json", {"num_stages": 4})
    rng = torch.get_rng_state().clone()
    report = validate_program(tmp_path, metadata())
    assert len(report["files"]) == 4
    for file in report["files"].values():
        assert len(file["removed_redundant_torch_import_lines"]) == 1
        assert [(p["batch"], p["horizon"]) for p in file["probes"]] == [(1, 9), (1, 10), (40, 10)]
        assert all(p["gradient_finite"] for p in file["probes"])
    assert torch.equal(torch.get_rng_state(), rng)


def fake_agent(tmp_path, candidates):
    seen = []
    agent = SimpleNamespace(task_dir=str(tmp_path / "vlm_agent"), prompt_template="original official prompt")
    def generate(img, instruction, data):
        seen.append({"template": agent.prompt_template, "image": img, "instruction": instruction, "metadata": deepcopy(data)})
        directory = Path(agent.task_dir)
        candidate = candidates[len(seen) - 1]
        if isinstance(candidate, InvalidGuidanceResponse):
            raise candidate
        (directory / "output_raw.txt").write_text(candidate or "bad metadata")
        (directory / "prompt.txt").write_text(agent.prompt_template)
        if candidate is None:
            raise ValueError("num_stages not found in output")
        (directory / "stage1_guidance.txt").write_text(candidate)
        data["init_keypoint_positions"] = data["init_keypoint_positions"].tolist()
        write_json(directory / "metadata.json", {**data, "num_stages": 1})
        return str(directory)
    agent.generate_guidance = generate
    return install_guidance_validation(agent), seen


def test_invalid_programs_are_archived_and_regenerated_in_same_scene(tmp_path, monkeypatch):
    waits = []
    monkeypatch.setattr(vls_guidance.time, "sleep", waits.append)
    bad = GOOD.replace("keypoints[1]", "keypoints[99]")
    agent, seen = fake_agent(tmp_path, [None, bad, GOOD])
    data, image = metadata(), np.zeros((2, 2, 3), dtype=np.uint8)
    original = deepcopy(data)
    result = agent.generate_guidance(image, "same task", data)
    assert result == str(tmp_path / "vlm_agent") and waits == [2, 4]
    assert seen[0]["template"] == "original official prompt"
    assert all("Execution compatibility feedback" in v["template"] for v in seen[1:])
    assert all(v["image"] is image and v["instruction"] == "same task" for v in seen)
    assert np.array_equal(data["init_keypoint_positions"], original["init_keypoint_positions"])
    assert agent.prompt_template == "original official prompt" and agent.task_dir == result
    assert "keypoints[99]" in (tmp_path / "guidance_attempts/attempt_002/output_raw.txt").read_text()
    assert "keypoints[99]" not in (Path(result) / "stage1_guidance.txt").read_text()
    assert read_json(tmp_path / "guidance_status.json")["status"] == "valid"
    assert read_json(tmp_path / "guidance_status.json")["attempt"] == 3


def test_truncated_generation_gets_complete_new_program(tmp_path, monkeypatch):
    waits = []
    monkeypatch.setattr(vls_guidance.time, "sleep", waits.append)
    agent, _ = fake_agent(tmp_path, [InvalidGuidanceResponse("token limit"), GOOD])
    agent.generate_guidance(np.zeros((2, 2, 3)), "task", metadata())
    assert waits == [2]
    assert read_json(tmp_path / "guidance_status.json")["status"] == "valid"


@pytest.mark.parametrize("candidate", [GOOD.replace("keypoints[1]", "keypoints[99]"),
    GOOD.replace("return -(delta.square().sum(dim=-1)).mean()", "return torch.tensor(1.0)"),
    GOOD.replace("return -(delta.square().sum(dim=-1)).mean()", "return action_sequence.sum() / 0.0")])
def test_bad_keypoints_or_invalid_active_rewards_are_rejected(tmp_path, candidate):
    (tmp_path / "stage1_guidance.txt").write_text(candidate)
    write_json(tmp_path / "metadata.json", {"num_stages": 1})
    with pytest.raises(InvalidGuidanceResponse):
        validate_program(tmp_path, metadata())


@pytest.mark.parametrize("expression", ["0", "0.0", "torch.tensor(0.0)",
    "torch.zeros(())", "torch.zeros(action_sequence.shape[0])",
    "torch.zeros(action_sequence.shape[0], device=action_sequence.device).mean()"])
def test_official_zero_reward_stages_pass_without_regeneration_or_code_changes(tmp_path, monkeypatch, expression):
    code = f"def stage1_guidance(keypoints, action_sequence):\n    return {expression}\n"
    waits = []
    monkeypatch.setattr(vls_guidance.time, "sleep", waits.append)
    agent, seen = fake_agent(tmp_path, [code])
    rng = torch.get_rng_state().clone()
    result = Path(agent.generate_guidance(np.zeros((2, 2, 3)), "task", metadata()))
    assert len(seen) == 1 and waits == []
    assert seen[0]["template"] == "original official prompt"
    assert (result / "stage1_guidance.txt").read_text() == code
    probes = read_json(result / "validation.json")["files"]["stage1_guidance.txt"]["probes"]
    assert len(probes) == 3
    assert all(p["reward_mode"] == "zero_reward" and p["gradient_finite"] is None for p in probes)
    assert torch.equal(torch.get_rng_state(), rng)
    # Exercise the unchanged loader used by Main, including numeric-zero conversion.
    fn, = load_functions_from_txt(result / "stage1_guidance.txt")
    trajectory = torch.ones(40, 10, 3, requires_grad=True)
    reward = fn(torch.ones(9, 3), trajectory)
    assert isinstance(reward, torch.Tensor) and torch.count_nonzero(reward).item() == 0
    assert not reward.requires_grad


@pytest.mark.parametrize("expression", ["torch.zeros(2)", "torch.tensor(0.0) / 0.0",
    "torch.tensor(1.0) / 0.0", "torch.sqrt((action_sequence - action_sequence).square().sum())"])
def test_zero_reward_exception_keeps_shape_finiteness_and_connected_gradient_checks(tmp_path, expression):
    (tmp_path / "stage1_guidance.txt").write_text(
        f"def stage1_guidance(keypoints, action_sequence):\n    return {expression}\n")
    write_json(tmp_path / "metadata.json", {"num_stages": 1})
    with pytest.raises(InvalidGuidanceResponse):
        validate_program(tmp_path, metadata())


def test_exact_episode021_program_accepts_active_and_zero_stages_with_real_keypoints(tmp_path):
    fixture = Path(__file__).parent / "fixtures"
    raw = (fixture / "vls_episode021_zero_reward.txt").read_text()
    data = read_json(fixture / "vls_episode021_metadata.json")
    code = raw.strip().removeprefix("```python").removesuffix("```").strip()
    for node in ast.parse(code).body:
        if isinstance(node, ast.FunctionDef):
            (tmp_path / f"{node.name}.txt").write_text(ast.get_source_segment(code, node) + "\n")
    write_json(tmp_path / "metadata.json", data)
    report = validate_program(tmp_path, data)
    assert len(data["init_keypoint_positions"]) == 11
    assert len(report["files"]) == 2
    for p in report["files"]["stage1_guidance.txt"]["probes"]:
        assert p["reward_mode"] == "differentiable_reward" and p["gradient_finite"]
    for p in report["files"]["stage2_guidance.txt"]["probes"]:
        assert p["reward_mode"] == "zero_reward" and p["gradient_finite"] is None


@pytest.mark.parametrize("candidate", [GOOD.replace("return -(delta.square().sum(dim=-1)).mean()", "return ("),
    GOOD.replace("return -(delta.square().sum(dim=-1)).mean()", "return (1).mean()"),
    GOOD.replace("    delta =", "    assert False\n    delta =")])
def test_parser_truncation_and_generated_runtime_errors_regenerate(tmp_path, monkeypatch, candidate):
    waits = []
    monkeypatch.setattr(vls_guidance.time, "sleep", waits.append)
    agent, seen = fake_agent(tmp_path, [candidate, GOOD])
    agent.generate_guidance(np.zeros((2, 2, 3)), "task", metadata())
    assert waits == [2] and len(seen) == 2
    assert read_json(tmp_path / "guidance_status.json")["status"] == "valid"


def test_failure_before_any_model_output_is_not_hidden_by_regeneration(tmp_path, monkeypatch):
    def generate(*args, **kwargs):
        raise ValueError("bad input image")
    agent = SimpleNamespace(generate_guidance=generate, task_dir=str(tmp_path / "vlm_agent"), prompt_template="official")
    install_guidance_validation(agent)
    with pytest.raises(ValueError, match="bad input image"):
        agent.generate_guidance(None, "task", metadata())
    assert agent.task_dir == str(tmp_path / "vlm_agent") and agent.prompt_template == "official"
