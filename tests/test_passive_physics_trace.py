from types import SimpleNamespace

import numpy as np
import pytest

from core.passive_physics_trace import PassivePhysicsTrace, physics_snapshot


class FakeModel:
    geom_bodyid = [0, 1]

    @staticmethod
    def geom_id2name(index):
        return ("finger_geom", "cup_geom")[index]

    @staticmethod
    def body_id2name(index):
        return ("robot_finger", "cup")[index]


class FakeTracker:
    @staticmethod
    def get_object_name_by_keypoint(index):
        assert index == 0
        return "cup"

    @staticmethod
    def execution_feedback_tracking_snapshot():
        return {"instance_id": 1, "generation": 2,
                "targets": {0: {"valid": True, "status": "tracked"}}}


def fake_adapter():
    contact = SimpleNamespace(geom1=0, geom2=1, dist=-.001)
    data = SimpleNamespace(body_xpos=np.array([[0., 0., 0.], [.1, .2, .3]]),
                           body_xquat=np.array([[1., 0., 0., 0.], [1., 0., 0., 0.]]),
                           contact=[contact], ncon=1, time=.05)
    sim = SimpleNamespace(data=data, model=FakeModel())
    env = SimpleNamespace(obj_body_id={"cup": 1})
    control = SimpleNamespace(env=env, sim=sim)
    return SimpleNamespace(_env=[SimpleNamespace(_env=control)]), data


def test_observer_copies_physics_without_mutation(tmp_path):
    adapter, data = fake_adapter()
    action = np.array([0., 0., 0., 0., 0., 0., -1.], dtype=np.float32)
    before_action = action.copy()
    before_positions = data.body_xpos.copy()
    row = physics_snapshot(adapter, FakeTracker(), global_step=0, action=action,
                           stage=1, guided=True, success=False)
    assert row["target_tracker_valid"] is True
    assert row["target_object_name"] == "cup"
    assert row["contacts_at_action_boundary"][0]["body_names"] == ["robot_finger", "cup"]
    np.testing.assert_array_equal(action, before_action)
    np.testing.assert_array_equal(data.body_xpos, before_positions)
    trace = PassivePhysicsTrace(tmp_path / "trace.jsonl")
    trace.record(adapter, FakeTracker(), global_step=0, action=action,
                 stage=1, guided=True, success=False)
    assert len((tmp_path / "trace.jsonl").read_text().splitlines()) == 1
    with pytest.raises(ValueError, match="index gap"):
        trace.record(adapter, FakeTracker(), global_step=0, action=action,
                     stage=1, guided=True, success=False)
