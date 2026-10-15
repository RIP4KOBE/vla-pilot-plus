import importlib.util
from pathlib import Path
import pytest

ROOT = Path.cwd()
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

controller = load("draft_stage_evidence", Path(__file__).with_name("stage_evidence.py"))
fixture = load("reference_test_helpers", ROOT / "tests/test_stage_evidence.py")

@pytest.mark.parametrize("preserve", [False, True])
def test_pure_off_to_on_switch_preserves_reference_only_when_enabled(preserve):
    runner = fixture.fake_runner([fixture.outside()])
    runner.config["stage_preserve_reward_reference_on_guidance_toggle"] = preserve
    cleared = []
    runner.policy.reset_eds_chunk_memory = cleared.append
    state = fixture.state(use_guidance=False)
    controller.update_stage(runner, state, -1.)
    assert state["current_stage"] == 1 and state["use_guidance"]
    assert runner.events[-1]["normalized_reward_diagnostic"] is None
    assert runner.events[-1]["reward_reference_reset"] is (not preserve)
    assert runner.resets == ([] if preserve else [1])
    assert cleared == (["guidance_change"] if preserve else [])

@pytest.mark.parametrize("preserve", [False, True])
def test_semantic_stage_change_always_resets_reference(preserve):
    observation = fixture.obs()
    observation.update(grasp="held", support="unsupported", target_location="outside_goal")
    runner = fixture.fake_runner([observation])
    runner.config["stage_preserve_reward_reference_on_guidance_toggle"] = preserve
    cleared = []
    runner.policy.reset_eds_chunk_memory = cleared.append
    state = fixture.state()
    controller.update_stage(runner, state, 1.)
    assert state["current_stage"] == 2 and not state["use_guidance"]
    assert runner.events[-1]["reward_reference_reset"]
    assert runner.resets == [1] and cleared == []


def test_default_preserves_existing_rebase_behavior():
    runner = fixture.fake_runner([fixture.outside()])
    state = fixture.state(use_guidance=False)
    controller.update_stage(runner, state, -1.)
    assert runner.resets == [1]
    assert runner.events[-1]["reward_reference_mode"] == "guidance_rebase_v1"


def test_unchanged_gate_does_not_reset_either_memory():
    runner = fixture.fake_runner([fixture.outside()])
    runner.config["stage_preserve_reward_reference_on_guidance_toggle"] = True
    cleared = []
    runner.policy.reset_eds_chunk_memory = cleared.append
    state = fixture.state()
    controller.update_stage(runner, state, -1.)
    assert runner.resets == [] and cleared == []
    assert not runner.events[-1]["reward_reference_reset"]
