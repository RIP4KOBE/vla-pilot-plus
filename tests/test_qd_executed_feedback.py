"""Synthetic CPU checks for frozen N3 arithmetic and lifecycle, no real provider."""
import copy
from types import SimpleNamespace

import pytest
import torch

from core.qd_executed_feedback import (
    ExecutedFeedbackHistory, FeedbackContract, executed_displacement_residual,
    executed_feedback_quality, native_identity,
)
from core.qd_executed_quality import TEMPLATE, recognize_executed_prefix_provider
from test_qd_executed_quality import provider


def semantic(dtype=torch.float32):
    fn = provider(TEMPLATE.replace("[0], dtype", "[2], dtype"))
    contract, _ = recognize_executed_prefix_provider([fn], torch.zeros(3, 3, dtype=dtype))
    return contract


def tracker(generation=1, status="tracked", valid=True):
    return {"instance_id": 13, "generation": generation, "targets": {"2": {"valid": valid, "status": status}}}


def selected_plan(history, *, step=0, stage=1, contract=None):
    contract = contract or history.begin(semantic(), stage=stage, global_step=step, tracker=tracker())
    sample = torch.zeros(1, 64, 128, dtype=torch.bfloat16)
    projection = torch.arange(27, dtype=torch.bfloat16).reshape(1, 9, 3) / 100
    origin = torch.tensor([.01321, .01222, -.03141], dtype=torch.float32)
    contract.record(sample, projection, [origin], torch.tensor([-.1], dtype=torch.bfloat16))
    record = history.select(contract, sample)
    actions = torch.arange(56, dtype=torch.float32).reshape(1, 8, 7) / 101
    history.bind_decode(sample.float(), actions, [10, 39, 40, 41, 42, 43, 44])
    history.commit(actions, 8, step)
    return contract, actions, projection[0], origin, record


def acknowledge(history, actions, *, start=0, count=8, terminal=False):
    result = None
    for i in range(count):
        result = history.acknowledge(global_step=start + i, execution_index=i + 1,
            action=actions[0, i], endpoint=torch.tensor([.03456 + i / 13, -.051, .25], dtype=torch.float64),
            terminated=terminal and i == count - 1, truncated=False)
    return result


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_native_t7_matches_expression_with_nonzero_generic_index(dtype):
    projection = torch.linspace(-.283, .47, 3 * 9 * 3).reshape(3, 9, 3).to(dtype)
    keypoints = torch.tensor([[7., 8., 9.], [3., 4., 5.], [.023, -.113, .238]], dtype=dtype)
    residual = torch.tensor([.039932, -.071324, .025927], dtype=torch.float64)
    ramp = torch.arange(1, 8, dtype=dtype) / 8
    corrected = projection[:, 1:8] + ramp[None, :, None] * residual.to(dtype)
    fn = provider(TEMPLATE.replace("[0], dtype", "[2], dtype"))
    expected = torch.stack([fn(keypoints, row[None]).to(dtype).reshape(()) for row in corrected])
    actual = executed_feedback_quality(projection, keypoints, target_index=2, residual_previous=residual)
    assert actual.dtype == dtype and torch.equal(actual, expected)
    # t0/t8 must not directly enter T7 reward, unlike N2's horizon extension.
    altered = projection.clone(); altered[:, [0, 8]] = 99
    assert torch.equal(actual, executed_feedback_quality(altered, keypoints, target_index=2, residual_previous=residual))
    assert not torch.cuda.is_initialized()


def test_residual_uses_native_source_origin_not_rounded_t0():
    projection = torch.zeros(9, 3, dtype=torch.bfloat16)
    projection[0] = torch.tensor([.10001, -.02381, .25221])
    projection[8] = torch.tensor([.17, .24, -.33])
    origin = torch.tensor([.10001, -.02381, .25221], dtype=torch.float32)
    endpoint = torch.tensor([.2313123434123, -.173245754341, .05124134], dtype=torch.float64)
    actual = executed_displacement_residual(projection, origin, endpoint)
    assert torch.equal(actual, (endpoint - origin.double()) - (projection[8].double() - projection[0].double()))
    assert not torch.equal(actual, endpoint - projection[8].double())


def test_history_only_next_full_ack_prefix_and_preserves_native_snapshot():
    history = ExecutedFeedbackHistory()
    first, actions, projection, origin, record = selected_plan(history)
    assert not first.active and first.residual is None
    completion = acknowledge(history, actions)
    assert completion["ack_count"] == 8 and completion["actual_endpoint"]["dtype"] == "torch.float64"
    second = history.begin(semantic(), stage=1, global_step=8, tracker=tracker())
    assert second.active and second.previous["end_global_step"] == 7
    assert torch.equal(second.residual, executed_displacement_residual(projection, origin,
        torch.tensor([.03456 + 7 / 13, -.051, .25], dtype=torch.float64)))
    frozen = second.residual.clone()
    assert history.completed is None
    selected_plan(history, step=8, contract=second)
    acknowledge(history, actions, start=8)
    assert torch.equal(second.residual, frozen)  # current endpoint cannot affect its own search


@pytest.mark.parametrize("change", ["gap", "stage", "provider", "registry", "invalid", "initial_unknown", "partial", "terminal", "off", "reset", "duplicate"])
def test_ineligible_predecessors_are_cleared(change):
    history = ExecutedFeedbackHistory()
    _, actions, *_ = selected_plan(history)
    acknowledge(history, actions, count=3 if change == "partial" else 8, terminal=change == "terminal")
    kw = dict(stage=1, global_step=8, tracker=tracker())
    sem = semantic()
    if change == "gap": kw["global_step"] = 16
    if change == "stage": kw["stage"] = 2
    if change == "provider": sem = SimpleNamespace(target_index=2, identity={"changed": True})
    if change == "registry": kw["tracker"] = tracker(generation=2)
    if change in {"invalid", "initial_unknown"}: kw["tracker"] = tracker(status=change, valid=False)
    if change == "off": history.clear("guidance_off")
    if change == "reset": history.clear("episode_reset", reset=True)
    if change == "duplicate": acknowledge(history, actions, start=0, count=1)
    current = history.begin(sem, **kw)
    assert not current.active and current.residual is None


def test_static_background_valid_and_active_action_contradiction_fails():
    history = ExecutedFeedbackHistory()
    first, actions, *_ = selected_plan(history)
    acknowledge(history, actions)
    second = history.begin(semantic(), stage=1, global_step=8, tracker=tracker(status="static_background"))
    assert second.active
    selected_plan(history, step=8, contract=second)
    with pytest.raises(RuntimeError, match="active execution feedback contradiction"):
        history.acknowledge(global_step=8, execution_index=1, action=actions[0, 0] + 1,
            endpoint=torch.zeros(3), terminated=False, truncated=False)
    assert history.pending is None and history.completed is None


@pytest.mark.parametrize("case", ["shape", "nan", "dtype", "overflow", "target"])
def test_quality_active_errors_do_not_silently_revert(case):
    projection = torch.zeros(2, 9, 3, dtype=torch.bfloat16)
    points = torch.zeros(3, 3, dtype=torch.bfloat16)
    residual = torch.zeros(3, dtype=torch.float64)
    if case == "shape": projection = projection[:, :8]
    if case == "nan": residual[0] = float("nan")
    if case == "dtype": residual = residual.float()
    if case == "overflow": residual[0] = 1e300
    if case == "target": points[2, 0] = float("nan")
    with pytest.raises((RuntimeError, FloatingPointError, ValueError)):
        executed_feedback_quality(projection, points, target_index=2, residual_previous=residual)


def test_same_native_candidate_different_origin_is_not_arbitrarily_selected():
    history = ExecutedFeedbackHistory()
    contract, actions, projection, origin, _ = selected_plan(history)
    contract.record(torch.zeros(1, 64, 128, dtype=torch.bfloat16), projection[None], [origin + .1], torch.tensor([-.1], dtype=torch.bfloat16))
    assert not contract.eligible and contract.reason == "ambiguous_native_candidate_association"
    acknowledge(history, actions)
    active = history.begin(semantic(), stage=1, global_step=8, tracker=tracker())
    selected_plan(history, step=8, contract=active)
    with pytest.raises(RuntimeError, match="active duplicate"):
        active.record(torch.zeros(1, 64, 128, dtype=torch.bfloat16), projection[None], [origin + .1], torch.tensor([-.1], dtype=torch.bfloat16))


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_scalar_native_identity_keeps_shape_dtype_and_exact_value(dtype):
    scalar = torch.tensor(-.125, dtype=dtype)
    assert len(native_identity(scalar)) == 64
    assert native_identity(scalar) != native_identity(scalar.reshape(1))
    assert native_identity(scalar) != native_identity(scalar.double())


def test_duplicate_after_active_eighth_ack_fails_and_terminal_eighth_clears():
    history = ExecutedFeedbackHistory()
    _, actions, *_ = selected_plan(history)
    acknowledge(history, actions)
    active = history.begin(semantic(), stage=1, global_step=8, tracker=tracker())
    selected_plan(history, step=8, contract=active)
    acknowledge(history, actions, start=8)
    with pytest.raises(RuntimeError, match="duplicate_ack_after_complete"):
        acknowledge(history, actions, start=8, count=1)
    assert history.completed is None
    selected_plan(history)
    acknowledge(history, actions, terminal=True)
    assert history.completed is None and history.pending is None


@pytest.mark.parametrize("active", [False, True])
def test_missing_endpoint_before_activation_unknown_after_activation_fails(active):
    history = ExecutedFeedbackHistory()
    _, actions, *_ = selected_plan(history)
    if active:
        acknowledge(history, actions)
        contract = history.begin(semantic(), stage=1, global_step=8, tracker=tracker())
        selected_plan(history, step=8, contract=contract)
    packet = dict(global_step=8 if active else 0, execution_index=1,
                  action=actions[0, 0], endpoint=None, terminated=False, truncated=False)
    if active:
        with pytest.raises(RuntimeError, match="actual_endpoint_missing_or_invalid"):
            history.acknowledge(**packet)
    else:
        assert history.acknowledge(**packet) is None
    assert history.completed is None and history.pending is None


def test_passive_tracker_preserves_values_and_pose_query_count():
    import numpy as np
    from core.keypoint_tracker import KeypointTracker
    from core.env_adapters.base_adapter import Pose3D
    pose = Pose3D(position=np.array([.1, -.2, .3]), quaternion=np.array([1., 0., 0., 0.]))
    class Adapter:
        def __init__(self): self.calls = []; self.available = False
        def get_object_pose_by_segment(self, segment):
            self.calls.append(segment)
            return pose if self.available and segment != 0 else None
        def get_robot_base_pose(self): return pose
    adapter = Adapter()
    tracker_instance = KeypointTracker(adapter)
    points = np.array([[1., 2., 3.], [4., 5., 6.]])
    tracker_instance.register_keypoints(points, np.array([0, 1]), {0: "background", 1: "object"})
    generation = tracker_instance.execution_feedback_tracking_snapshot()["generation"]
    assert adapter.calls == [0, 1]
    adapter.available = True
    returned = tracker_instance.get_keypoint_positions()
    snapshot = tracker_instance.execution_feedback_tracking_snapshot()
    assert snapshot["targets"]["0"] == {"valid": True, "status": "static_background"}
    assert snapshot["targets"]["1"] == {"valid": False, "status": "initial_pose_unavailable"}
    assert adapter.calls == [0, 1, 1]
    assert np.array_equal(returned[0], points[0])
    assert np.array_equal(returned[1], points[1] + pose.position)  # Existing fallback-derived numeric rule unchanged.
    tracker_instance.register_keypoints(points, np.array([0, 1]), {0: "background", 1: "object"})
    assert tracker_instance.execution_feedback_tracking_snapshot()["generation"] == generation + 1
    adapter.available = False
    returned = tracker_instance.get_keypoint_positions()
    assert np.array_equal(returned, points)
    assert tracker_instance.execution_feedback_tracking_snapshot()["targets"]["1"]["status"] == "current_pose_fallback"
    tracker_instance.reset()
    assert tracker_instance.execution_feedback_tracking_snapshot() == {"instance_id": id(tracker_instance), "generation": generation + 2, "targets": {}}
