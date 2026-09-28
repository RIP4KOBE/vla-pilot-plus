"""The passive tracking observer cannot change the policy's keypoint/action bytes."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import torch

from core.decision_evidence import DecisionEvidence
from core.keypoint_tracker import read_keypoints_with_passive_tracking


class _Tracker:
    def __init__(self, points):
        self.points = points
        self.pose_reads = 0
        self.snapshot_reads = 0

    def get_keypoint_positions(self):
        self.pose_reads += 1
        return self.points

    def execution_feedback_tracking_snapshot(self):
        self.snapshot_reads += 1
        return {"instance_id": 73, "generation": 2,
                "targets": {"0": {"valid": True, "status": "tracked"},
                            "1": {"valid": False, "status": "current_pose_fallback"}},
                "credential": "must_not_be_persisted"}


def _synthetic_action(points):
    # Representative policy consumer: the same input bytes imply same action bytes.
    return np.array([points[0, 0], points[0, 1], points[0, 2],
                     points[1, 0], points[1, 1], points[1, 2], 1], dtype=np.float32)


def test_tracking_snapshot_is_passive_and_persisted(tmp_path):
    points = np.array([[0.125, -0.25, 0.375], [0.5, 0.625, 0.75]], dtype=np.float64)
    plain = _Tracker(points.copy())
    observed = _Tracker(points.copy())
    original_keypoints = plain.get_keypoint_positions()
    original_action = _synthetic_action(original_keypoints)

    keypoints, snapshot = read_keypoints_with_passive_tracking(observed, evidence_enabled=True)
    observed_action = _synthetic_action(keypoints)
    assert keypoints is observed.points
    assert keypoints.tobytes() == original_keypoints.tobytes()
    assert observed_action.tobytes() == original_action.tobytes()
    assert (plain.pose_reads, observed.pose_reads, observed.snapshot_reads) == (1, 1, 1)
    assert snapshot == {"instance_id": 73, "generation": 2,
                        "targets": {"0": {"valid": True, "status": "tracked"},
                                    "1": {"valid": False, "status": "current_pose_fallback"}}}

    evidence = DecisionEvidence(tmp_path, episode=0)
    evidence.begin_decision(global_step=0, stage=1, use_guidance=False,
                            keypoints=keypoints, providers=None,
                            keypoint_tracking_snapshot=snapshot)
    action_tensor = torch.from_numpy(observed_action.copy()).reshape(1, 1, 7)
    evidence.record("policy_action_decode", selected_latent=torch.zeros((1, 1)),
                    action_chunk=action_tensor)
    evidence.commit_decision(action_chunk=action_tensor, execution_horizon=1)
    assert evidence.finish()["complete"] is True

    folder = tmp_path / "episode_000"
    entry = json.loads((folder / "events.jsonl").read_text().strip())
    bundle = folder / entry["bundle"]
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == entry["sha256"]
    events = torch.load(bundle, map_location="cpu", weights_only=True)["events"]
    context = next(event["values"] for event in events if event["event"] == "decision_context")
    committed = next(event["values"] for event in events if event["event"] == "decision_committed")
    assert context["keypoints"].numpy().tobytes() == original_keypoints.tobytes()
    assert context["keypoint_tracking_snapshot"] == snapshot
    assert committed["action_chunk"].numpy().tobytes() == action_tensor.numpy().tobytes()
    assert "credential" not in str(context)


def test_tracking_snapshot_failure_does_not_change_keypoints():
    points = np.array([[1., 2., 3.]], dtype=np.float64)
    tracker = _Tracker(points)
    tracker.execution_feedback_tracking_snapshot = lambda: 3
    keypoints, snapshot = read_keypoints_with_passive_tracking(tracker, evidence_enabled=True)
    assert keypoints is points
    assert keypoints.tobytes() == points.tobytes()
    assert snapshot == {"capture_error_type": "TypeError"}
    assert tracker.pose_reads == 1
