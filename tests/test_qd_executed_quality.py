"""Synthetic CPU contracts; no checkpoint, environment, or real provider calls."""
import ast
import copy

import pytest
import torch

from core.qd_executed_quality import (
    TEMPLATE, executed_prefix_quality, recognize_executed_prefix_provider,
)
from core.qd_ed import QDArchive
from utils.guidance_utils import wrap_guidance_function_with_device_fix


def provider(source=TEMPLATE):
    namespace = {"torch": torch}
    exec(compile(source, "<synthetic-provider>", "exec", dont_inherit=True), namespace)
    name = next(n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef))
    original = namespace[name]
    wrapped = wrap_guidance_function_with_device_fix(original)
    wrapped._guidance_original_func = original
    wrapped._guidance_source_text = source
    return wrapped


@pytest.mark.parametrize("index", [0, 1, 4, 17])
def test_recognizes_generic_index_without_names_path_or_stage(index):
    source = TEMPLATE.replace("[0], dtype", f"[{index}], dtype").replace("approach", "unrelated_name").replace("target_pos", "goal").replace("keypoints", "points")
    fn = provider(source)
    contract, reason = recognize_executed_prefix_provider([fn], torch.zeros(index + 1, 3))
    assert contract.target_index == index
    assert reason == "recognized_weighted_distance_template"
    contract.validate([fn])


@pytest.mark.parametrize("change", [
    lambda s: s.replace("-(all_dists", "(all_dists"),
    lambda s: s.replace("3.0", "4.0"),
    lambda s: s.replace("0.7", "0.8"),
    lambda s: s.replace("return reward.mean()", "return reward.mean() * 0"),
    lambda s: s.replace("[0], dtype", "[int(keypoints[0, 0])], dtype"),
    lambda s: s.replace("target_pos = keypoints[target_idx][0]", "target_pos = keypoints[target_idx][0] + keypoints[1]"),
    lambda s: s.replace("return reward.mean()", "return -reward.mean()"),
    lambda s: "def constant(keypoints, action_sequence):\n    return 0.0\n# " + s.replace("\n", "\n# "),
])
def test_unknown_expressions_fall_back_without_calling_function(change):
    fn = provider(change(TEMPLATE))
    contract, reason = recognize_executed_prefix_provider([fn], torch.zeros(2, 3))
    assert contract is None and reason


def test_binding_mismatch_and_multifunction_are_unknown_then_drift_fails():
    fn = provider()
    assert recognize_executed_prefix_provider([fn, fn], torch.zeros(1, 3))[0] is None
    contract, _ = recognize_executed_prefix_provider([fn], torch.zeros(1, 3))
    fn._guidance_source_text = TEMPLATE.replace("3.0", "4.0")
    assert recognize_executed_prefix_provider([fn], torch.zeros(1, 3))[0] is None
    with pytest.raises(RuntimeError, match="identity changed"):
        contract.validate([fn])
    fn = provider()
    fn._guidance_original_func = provider()._guidance_original_func
    assert recognize_executed_prefix_provider([fn], torch.zeros(1, 3))[1] == "wrapper_original_mismatch"
    fn = provider()
    fn._guidance_original_func.__code__ = provider(TEMPLATE.replace("3.0", "4.0"))._guidance_original_func.__code__
    assert recognize_executed_prefix_provider([fn], torch.zeros(1, 3))[1] == "source_original_code_mismatch"


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16, torch.float64])
def test_native_quality_matches_exact_fixture_provider_on_eight_points(dtype):
    # Deliberately nonzero target, nontrivial tail, and nonrepresentable BF16 values.
    projected = torch.linspace(-0.23, 0.57, 4 * 9 * 3).reshape(4, 9, 3).to(dtype)
    keypoints = torch.tensor([[7., 8., 9.], [0.013, -0.127, 0.238]], dtype=dtype)
    fn = provider(TEMPLATE.replace("[0], dtype", "[1], dtype"))
    expected = torch.stack([fn(keypoints, p[None, 1:9]).to(dtype).reshape(()) for p in projected])
    result = executed_prefix_quality(projected, keypoints, target_index=1)
    assert result.dtype == dtype and torch.equal(result, expected)
    assert not torch.cuda.is_initialized()


def test_exact_weights_tail_and_t0_exclusion():
    projection = torch.zeros(2, 9, 3)
    projection[:, 0] = 1000
    projection[0, 1, 0] = 1
    projection[1, 8, 0] = 1
    result = executed_prefix_quality(projection, torch.zeros(1, 3), target_index=0)
    assert torch.equal(result, -torch.tensor([1., 3.]) / 14)


@pytest.mark.parametrize("case", ["index", "shape", "dtype", "nan", "overflow", "keypoint_nan"])
def test_invalid_numerics_fail_explicitly(case):
    points = torch.zeros(1, 9, 3)
    keypoints = torch.zeros(1, 3)
    index = 0
    if case == "index": index = 1
    if case == "shape": points = points[:, :8]
    if case == "dtype": keypoints = keypoints.double()
    if case == "nan": points[0, 8, 0] = float("nan")
    if case == "overflow": points[0, 8, 0] = 1e30
    if case == "keypoint_nan": keypoints[0, 0] = float("nan")
    with pytest.raises((ValueError, FloatingPointError)):
        executed_prefix_quality(points, keypoints, target_index=index)


def test_raw_rewards_follow_actual_archive_occurrence_not_fingerprint_lookup():
    archive = QDArchive(grid_shape=(4, 4))
    actions = torch.zeros(2, 64, 128)  # Duplicate latent, distinct test occurrences.
    archive.update(actions=actions, rewards=torch.tensor([1., 2.]), costs=torch.tensor([-1., -2.]),
                   raw_rewards=torch.tensor([-0.1, -0.2], dtype=torch.bfloat16),
                   descriptors=torch.zeros(2, 2), cell_ids=torch.tensor([0, 0]), source_iter=-1)
    expected = float(torch.tensor(-0.2, dtype=torch.bfloat16))
    assert archive.select_global_best()[1].raw_reward == expected
    assert archive.elite_raw_rewards().dtype == torch.float32
    assert archive.elite_raw_rewards().tolist() == [expected]
    # Rejected duplicate must not overwrite winning occurrence's original reward.
    archive.update(actions=actions[:1], rewards=torch.tensor([0.]), costs=torch.tensor([0.]),
                   raw_rewards=torch.tensor([100.]), descriptors=torch.zeros(1, 2),
                   cell_ids=torch.tensor([0]), source_iter=0)
    assert archive.select_global_best()[1].raw_reward == expected
    archive.rebin(torch.tensor([2]))
    assert archive.elite_raw_rewards().tolist() == [expected]
    with pytest.raises(RuntimeError, match="channel changed"):
        archive.update(actions=actions[:1], rewards=torch.tensor([3.]), costs=torch.tensor([-3.]),
                       descriptors=torch.zeros(1, 2), cell_ids=torch.tensor([2]), source_iter=1)
