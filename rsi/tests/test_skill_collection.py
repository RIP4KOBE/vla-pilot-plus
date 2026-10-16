import asyncio
import ast
import inspect
import json
from pathlib import Path
import time
from types import SimpleNamespace

import h5py
import numpy as np
import pytest

from mode_gate.codex_account import queue_command, write_json
from mode_gate.data_pipeline import DemoWriter, curate_ticket_demos
from mode_gate.libero_skill_controller import LiberoSkillController, damped_ik_delta, inverse_action_scaling
from mode_gate.skill_collection import (
    AutomaticCollection, CodexSkillPlanner, SkillCollectionConfig, SkillControlFailure, SkillPlan, validate_plan,
    trajectory_summary, path_diversity,
)
from mode_gate.skill_visuals import build_visual_context, failure_frame_indices
from mode_gate.teleop import TeleopSession
from mode_gate.teleop_supervisor import TeleopSupervisor
from mode_gate.io_utils import AtomicJsonl


def plan(**changes):
    skill = dict(operation="move", description_zh="接近目标", reference="ee", offset_m=[0, 0, .02],
        orientation_wxyz=None, gripper="keep", joint=None, joint_target=None,
        until_predicate=None, grasp_object=None, allow_contact_objects=[], max_steps=20)
    skill.update(changes)
    return SkillPlan(schema_version="libero-skill-plan-v1", ticket_id="test", coverage_cell="cell",
        explanation_zh="测试", skills=[skill])


SCENE = dict(instruction="test", references={"ee": {}}, objects={"object": {}},
    joints={"hinge": {"range": [0, 1]}}, available_predicates=[["open", "object"]])


@pytest.mark.parametrize("change", [
    {"reference": "invented"}, {"offset_m": [1, 0, 0]}, {"orientation_wxyz": [1, 1, 0, 0]},
    {"joint": "hinge"}, {"until_predicate": ["fake", "object"]},
    {"grasp_object": "fake"}, {"allow_contact_objects": ["fake"]},
    {"operation": "articulate", "joint": "hinge", "joint_target": 2},
    {"operation": "wait_predicate"},
])
def test_reject_invalid_plan(change):
    with pytest.raises(ValueError):
        validate_plan(plan(**change), SCENE, ticket_id="test", coverage_cell="cell")


def test_valid_plan_and_limits():
    validate_plan(plan(), SCENE, ticket_id="test", coverage_cell="cell")
    with pytest.raises(ValueError):
        validate_plan(plan(), SCENE, ticket_id="another", coverage_cell="cell")
    with pytest.raises(ValueError):
        SkillCollectionConfig(planner_transport="openai_api")
    with pytest.raises(ValueError):
        SkillCollectionConfig(consecutive_failure_limit=0)


def test_inverse_scaling_and_ik_are_bounded():
    osc = SimpleNamespace(output_min=np.array([-.02]*3 + [-.4]*3),
        output_max=np.array([.02]*3 + [.4]*3), input_min=-np.ones(6), input_max=np.ones(6))
    np.testing.assert_allclose(inverse_action_scaling(np.array([.01]*3 + [.2]*3), osc), .5)
    result = damped_ik_delta(np.eye(6, 7), np.ones(6), damping=.04, max_joint_step=.08)
    assert np.linalg.norm(result) <= .0800001


@pytest.mark.parametrize("changes", [
    {"operation": "teleport"}, {"operation": "reset"}, {"operation": "set_state"},
    {"qpos": [0, 0, 0]}, {"body_pos": [0, 0, 0]}, {"code": "sim.data.qpos[:] = 0"},
])
def test_skill_schema_has_no_teleport_or_state_write_channel(changes):
    with pytest.raises(ValueError):
        plan(**changes)


def test_ik_preview_leaves_live_simulator_data_unchanged():
    controller = object.__new__(LiberoSkillController)
    controller.config = SkillCollectionConfig()
    live = SimpleNamespace(qpos=np.zeros(7), qvel=np.arange(7, dtype=float),
        mocap_pos=np.ones((1, 3)), mocap_quat=np.array([[1., 0., 0., 0.]]))
    controller.sim = SimpleNamespace(data=live)
    controller.scratch = SimpleNamespace(**{name: np.zeros_like(value) for name, value in vars(live).items()})
    controller.osc = SimpleNamespace(J_full=np.eye(6, 7), update=lambda **kwargs: None)
    controller.qpos_indices = controller.qvel_indices = np.arange(7)
    controller.model = SimpleNamespace(dof_jntid=np.arange(7), jnt_limited=np.zeros(7, dtype=bool))
    previews = []
    def forward(model, data):
        assert model is controller.model and data is controller.scratch
        previews.append(data.qpos.copy())
    controller.mujoco = SimpleNamespace(mj_forward=forward)
    controller._contacts = lambda *args: []
    before = {name: value.copy() for name, value in vars(live).items()}
    controller._check_ik_motion(np.ones(6) * .01, [])
    assert len(previews) == 3 and np.linalg.norm(previews[-1]) > 0
    for name, value in before.items():
        np.testing.assert_array_equal(getattr(live, name), value)
        assert not np.shares_memory(getattr(live, name), getattr(controller.scratch, name))


def test_controller_has_no_live_state_setters_or_physics_writes():
    # Regression tripwire for direct writes. The independent physical replay
    # is the end-to-end check; a source scan is not a general security sandbox.
    tree = ast.parse(inspect.getsource(LiberoSkillController))
    protected = {"qpos", "qvel", "mocap_pos", "mocap_quat", "body_pos", "body_quat",
                 "geom_pos", "geom_quat", "body_mass", "geom_contype", "geom_conaffinity"}
    forbidden_calls = {"set_state", "set_state_from_flattened", "set_joint_qpos",
                       "restore_simulator_state", "restore_flattened_simulator_state", "reset"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for attr in ast.walk(target):
                    if isinstance(attr, ast.Attribute) and attr.attr in protected:
                        assert ast.unparse(attr.value) == "self.scratch", ast.unparse(target)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls, ast.unparse(node)


class Adapter:
    device = "cpu"

    def __init__(self):
        self.steps = 0
        self.success = False

    def capture_simulator_state(self):
        return {"flattened_sim_state": np.array([self.steps, 0, 0, 0])}

    def observation(self):
        image = np.zeros((256, 256, 3), dtype=np.uint8)
        return image, image, np.zeros(8), np.zeros(3)

    def step_teleop(self, action):
        self.steps += 1
        return {}, int(self.success), self.success, False, {"success": self.success}


def collector(tmp_path, *, succeeds=False, planner_error=False, failure_limit=None):
    adapter = Adapter()
    writers, saved = [], []

    def fresh():
        adapter.steps, adapter.success = 0, False
        writer = DemoWriter(tmp_path / f"demo-{len(writers)}.hdf5", task="test", ticket_id="test",
            operator="test", init_state_id="1", snapshot_id=None, hashes={}, coverage_cell="cell")
        writers.append(writer)
        return writer

    session = TeleopSession(adapter=adapter, writer=fresh(), observation_provider=adapter.observation,
        task_success_provider=lambda: adapter.success, reset_current=fresh,
        queue_position_provider=lambda: (1, 1), on_save=lambda path: saved.append(path))
    session.initialize()

    class Controller:
        def __init__(self, *args):
            pass

        def scene(self):
            return SCENE

        def execute(self, requested, session):
            adapter.success = succeeds
            session.execute_action(np.zeros(7))
            yield {"index": 1, "step": 1}
            if not succeeds:
                raise SkillControlFailure("no native success")

    class Planner:
        def plan(self, **kwargs):
            if planner_error:
                raise RuntimeError("account unavailable")
            return plan()

    driver = AutomaticCollection(session=session, controller_factory=Controller, planner=Planner(),
        ticket={"ticket_id": "test"}, output_root=tmp_path / "automatic",
        config=SkillCollectionConfig(**({"consecutive_failure_limit": failure_limit} if failure_limit is not None else {})))
    return driver, session, saved


def test_success_uses_native_predicate_without_browser(tmp_path):
    driver, session, saved = collector(tmp_path, succeeds=True)
    session.handle = lambda key: pytest.fail("automatic controller must not use browser keys")
    asyncio.run(driver.run())
    assert driver.state == "COMPLETE" and len(saved) == 1
    with h5py.File(saved[0]) as f:
        assert f.attrs["simulator_success"] and f.attrs["explicit_success"]
        assert f.attrs["demonstration_source"] == "codex_skill_controller"
        assert len(f["action"]) == 1 and len(f["simulator_state"]) == 2
    events = list(driver.events.iter_valid())
    assert events[-1]["event"] == "AUTO_DEMONSTRATION_SAVED"


def test_initialization_revision_reaches_planner_and_success_metadata(tmp_path):
    driver, session, saved = collector(tmp_path, succeeds=True)
    provenance = {"revision": "support-v1", "scope": "offline_demonstration_only"}
    session.writer.metadata["initialization_provenance"] = json.dumps(provenance)
    driver.controller_factory.scene = lambda self: dict(SCENE)
    observed = []

    def revised_plan(**kwargs):
        observed.append(kwargs["scene"]["initialization_provenance"])
        return plan()

    driver.planner.plan = revised_plan
    asyncio.run(driver.run())
    assert observed == [provenance]
    with h5py.File(saved[0]) as f:
        assert json.loads(f.attrs["initialization_provenance"]) == provenance


def test_three_real_failures_saved_and_survive_restart(tmp_path):
    driver, session, saved = collector(tmp_path, failure_limit=3)

    async def run():
        task = asyncio.create_task(driver.run())
        for _ in range(200):
            if driver.needs_human:
                break
            await asyncio.sleep(.01)
        assert driver.needs_human and driver.consecutive_failures == 3
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
    assert not saved and not list(tmp_path.glob("*.hdf5"))
    assert len(list((tmp_path / "automatic").glob("*/trajectory.npz"))) == 3
    for path in (tmp_path / "automatic").glob("*/failure.json"):
        assert json.loads(path.read_text())["training_eligible"] is False
    restored = AutomaticCollection(session=session, controller_factory=driver.controller_factory,
        planner=driver.planner, ticket=driver.ticket, output_root=driver.output_root, config=driver.config)
    assert restored.needs_human
    restored.human_demo_saved()
    assert not restored.needs_human and restored.consecutive_failures == 0


def test_default_collection_failure_limit_is_fifty():
    config = json.loads((Path(__file__).resolve().parents[2] / "configs/skill_collection.json").read_text())
    assert SkillCollectionConfig().consecutive_failure_limit == config["consecutive_failure_limit"] == 50


def test_fifty_physical_failures_before_human_handoff(tmp_path):
    driver, session, saved = collector(tmp_path)
    for index in range(50):
        session.execute_action(np.zeros(7))
        driver._failed(driver.output_root / f"attempt-{index}", SkillControlFailure("lost grasp"))
        assert driver.consecutive_failures == index + 1
        assert driver.needs_human is (index == 49)
    assert not saved and not list(tmp_path.glob("*.hdf5"))
    assert len(list(driver.output_root.glob("*/trajectory.npz"))) == 50
    assert len([e for e in driver.events.iter_valid() if e["event"] == "HUMAN_DEMONSTRATION_REQUESTED"]) == 1


@pytest.mark.parametrize("old_limit,new_limit", [(3, 20), (20, 50)])
def test_limit_increase_resumes_old_handoff_without_erasing_failures(tmp_path, old_limit, new_limit):
    driver, session, _ = collector(tmp_path, failure_limit=old_limit)
    for index in range(old_limit):
        session.execute_action(np.zeros(7))
        driver._failed(driver.output_root / f"attempt-{index}", SkillControlFailure("lost grasp"))
    assert driver.needs_human
    restored = AutomaticCollection(session=session, controller_factory=driver.controller_factory,
        planner=driver.planner, ticket=driver.ticket, output_root=driver.output_root,
        config=SkillCollectionConfig(consecutive_failure_limit=new_limit))
    assert restored.state == "AUTO_READY" and not restored.needs_human
    assert restored.consecutive_failures == old_limit and len(restored.failures) == 3
    assert restored.status()["failure_limit"] - restored.consecutive_failures == new_limit - old_limit


def test_planner_error_is_not_a_control_failure(tmp_path):
    driver, _, saved = collector(tmp_path, planner_error=True)
    asyncio.run(driver.run())
    assert driver.state == "PLANNER_ERROR" and not driver.needs_human
    assert driver.consecutive_failures == 0 and not saved


def test_pause_prevents_planning_and_actions(tmp_path):
    driver, session, _ = collector(tmp_path)
    driver.pause_path = tmp_path / "pause"
    driver.pause_path.touch()
    asyncio.run(driver.run())
    assert driver.state == "PAUSED" and not session.writer.actions
    assert not list(driver.output_root.glob("attempt-*"))


def test_auto_failure_cannot_be_written_as_hdf5(tmp_path):
    _, session, _ = collector(tmp_path)
    session.execute_action(np.zeros(7))
    session.writer.metadata["demonstration_source"] = "codex_skill_controller"
    session.writer.set_explicit_success(True)
    with pytest.raises(ValueError, match="diagnostic NPZ"):
        session.writer.save()


def test_curation_accepts_short_native_success_without_replay(tmp_path):
    driver, _, saved = collector(tmp_path, succeeds=True)
    asyncio.run(driver.run())
    result = curate_ticket_demos([Path(saved[0])], required_quotas={"cell": 1}, rejected_dir=tmp_path / "rejected")
    assert len(result.accepted) == 1 and not result.needs_more_demos


def test_queue_enforces_owner_and_no_api_fallback(tmp_path):
    request_id = "a" * 32
    write_json(tmp_path / request_id / "request.json", {"request_id": request_id, "expires_at": time.time() + 60})
    claim = queue_command(tmp_path, "claim", {"worker_id": "thread"})
    assert queue_command(tmp_path, "claim", {"worker_id": "other"}) == {"request": None}
    response = {"request_id": request_id, "claim_token": claim["claim_token"], "auth_mode": "apikey", "plan": {}}
    with pytest.raises(ValueError, match="ChatGPT-account"):
        queue_command(tmp_path, "complete", response)
    response["auth_mode"] = "chatgpt"
    assert queue_command(tmp_path, "complete", response)["accepted"]
    assert queue_command(tmp_path, "complete", response)["accepted"]


def test_public_portal_only_starts_on_human_fallback(tmp_path):
    supervisor = TeleopSupervisor.__new__(TeleopSupervisor)
    supervisor.collection_mode, supervisor.runtime_root = "auto_skill", tmp_path
    supervisor.port, supervisor.public_port, supervisor.host = 8768, 8765, "127.0.0.1"
    supervisor.events = AtomicJsonl(tmp_path / "events.jsonl")
    started = []
    supervisor.ensure_portal = lambda: started.append(True)
    base = {"job_id": "j", "ticket_id": "t", "collection_round": 1, "collection_mode": "auto_skill"}
    supervisor._collection_portal({**base, "collection_state": "PLANNING", "needs_human": False})
    assert not started
    supervisor._collection_portal({**base, "collection_state": "NEEDS_HUMAN", "needs_human": True,
        "consecutive_failures": 3})
    assert started and json.loads((tmp_path / "human_request.json").read_text())["needs_human"]


def test_actual_path_diversity_reports_repeats_and_meaningful_changes():
    path = np.column_stack([np.linspace(0, 1, 25), np.zeros(25), np.ones(25)])
    actions = np.zeros((24, 7))
    previous = trajectory_summary(path, actions, metadata={"init_state_id": "1"})
    assert path_diversity(previous, [previous])["near_duplicate_advisory"]
    varied = path.copy()
    varied[:, 1] = .15 * np.sin(np.linspace(0, np.pi, len(path)))
    summary = trajectory_summary(varied, actions, metadata={"init_state_id": "1"})
    assert not path_diversity(summary, [previous])["near_duplicate_advisory"]


def test_curation_preserves_all_successful_automatic_strategies(tmp_path):
    paths = []
    for index in range(3):
        driver, _, saved = collector(tmp_path / str(index), succeeds=True)
        asyncio.run(driver.run())
        with h5py.File(saved[0], "r+") as f:
            f.attrs["replay_validated"] = True
        paths.append(Path(saved[0]))

    result = curate_ticket_demos(paths, required_quotas={"cell": 3}, rejected_dir=tmp_path / "rejected")
    assert len(result.accepted) == 3 and not result.needs_more_demos
    assert "main_mode_fraction" not in result.coverage["cell"]
    assert result.coverage["cell"]["diversity_preserved"]


def test_initial_dual_camera_pixels_and_identity_are_preserved(tmp_path):
    from PIL import Image
    _, session, _ = collector(tmp_path)
    session.writer.frames[0].image[0, 0] = [10, 20, 30]
    session.writer.frames[0].image2[-1, -1] = [40, 50, 60]
    session.observation_provider = lambda: pytest.fail("must reuse frames without rendering")
    result = build_visual_context(session.writer, tmp_path / "attempt-one", [])
    assert len(result["images"]) == 2 and len(result["manifest_sha256"]) == 64
    assert {x["camera"] for x in result["images"]} == {"agentview", "robot0_eye_in_hand"}
    for item, field in zip(result["images"], ["image", "image2"]):
        assert item["phase"] == "initial" and item["frame_index"] == 0
        np.testing.assert_array_equal(np.array(Image.open(item["path"])), getattr(session.writer.frames[0], field))
    assert not session.writer.actions


def test_failure_keyframes_are_bounded_and_t_plus_one_aligned():
    actions = np.zeros((20, 7))
    actions[:, 6] = -1
    actions[10:, 6] = 1
    selected = failure_frame_indices(actions, 21, active_skill={"step": 4})
    assert selected == [(10, "before_last_gripper_change"), (16, "failure_skill_entry"), (20, "failure")]
    assert failure_frame_indices([], 1) == [(0, "failure")]
    assert len(failure_frame_indices(actions, 21, count=1)) == 1


def test_failure_images_reach_next_plan_and_do_not_become_training_data(tmp_path):
    driver, session, _ = collector(tmp_path)
    received = []

    class Planner:
        def plan(self, **kwargs):
            received.append(kwargs)
            if len(received) == 2:
                raise RuntimeError("stop after checking failure images")
            return plan()
    driver.planner = Planner()
    asyncio.run(driver.run())
    assert len(received[0]["visual_observations"]["images"]) == 2
    visuals = received[1]["visual_observations"]["images"]
    assert 4 <= len(visuals) <= 8
    failures = [x for x in visuals if x["phase"] == "failure"]
    assert {x["camera"] for x in failures} == {"agentview", "robot0_eye_in_hand"}
    assert any(x["frame_index"] == 1 for x in failures)
    assert all(x["failure_error"] == "no native success" for x in failures)
    assert driver.consecutive_failures == 1 and driver.state == "PLANNER_ERROR"
    assert not list(tmp_path.glob("*.hdf5"))


def test_old_failed_npz_can_supply_visuals_without_simulator_restart(tmp_path):
    from mode_gate.skill_collection import save_failed_attempt
    _, session, _ = collector(tmp_path)
    old = tmp_path / "old-attempt"
    for _ in range(3):
        session.execute_action(np.zeros(7))
    save_failed_attempt(session.writer, old, detail={"error": "lost grasp"})
    session.writer = session.reset_current()
    session.initialize()
    result = build_visual_context(session.writer, tmp_path / "new-attempt",
        [{"attempt": str(old), "error": "lost grasp", "active_skill": {"step": 2}}])
    assert len(result["images"]) <= 8
    assert any(x["phase"] == "failure" and x["frame_index"] == 3 for x in result["images"])
    assert (old / "failure_visuals.json").is_file()


def test_visual_queue_requires_current_images_and_review(tmp_path):
    request_id = "b" * 32
    visuals = {"manifest_sha256": "current", "images": [{"image_id": "outside"}, {"image_id": "wrist"}]}
    write_json(tmp_path / request_id / "request.json", {"request_id": request_id,
        "expires_at": time.time() + 60, "visual_observations": visuals})
    claim = queue_command(tmp_path, "claim", {"worker_id": "thread"})
    response = {"request_id": request_id, "claim_token": claim["claim_token"], "auth_mode": "chatgpt", "plan": {}}
    with pytest.raises(ValueError, match="visual_review"):
        queue_command(tmp_path, "complete", response)
    response["visual_review"] = {"manifest_sha256": "old", "viewed_image_ids": ["outside", "wrist"], "assessment_zh": "已看两幅图像"}
    with pytest.raises(ValueError, match="visual_review"):
        queue_command(tmp_path, "complete", response)
    response["visual_review"]["manifest_sha256"] = "current"
    response["visual_review"]["viewed_image_ids"] = ["outside"]
    with pytest.raises(ValueError, match="visual_review"):
        queue_command(tmp_path, "complete", response)
    response["visual_review"]["viewed_image_ids"].append("wrist")
    assert queue_command(tmp_path, "complete", response)["accepted"]
    saved = json.loads((tmp_path / request_id / "response.json").read_text())
    assert saved["visual_review"] == response["visual_review"]


def test_visual_planner_refuses_missing_images_without_spending_budget(tmp_path):
    planner = CodexSkillPlanner(config=SkillCollectionConfig(), ledger_path=tmp_path / "ledger.jsonl", queue_root=tmp_path / "queue")
    with pytest.raises(ValueError, match="initial camera images"):
        planner.plan(ticket={"ticket_id": "test"}, scene=SCENE, coverage_cell="cell", failures=[])
    assert not list((tmp_path / "queue").glob("*/request.json"))


def test_visual_feature_can_be_disabled_explicitly(tmp_path):
    from dataclasses import replace
    driver, _, _ = collector(tmp_path, succeeds=True)
    driver.config = replace(driver.config, use_visual_observations=False)
    asyncio.run(driver.run())
    assert not list(driver.output_root.glob("*/visuals/*.png"))
    with pytest.raises(ValueError, match="failure_keyframe_count"):
        SkillCollectionConfig(failure_keyframe_count=0)


def test_visual_request_and_review_complete_account_round_trip(tmp_path):
    _, session, _ = collector(tmp_path)
    visuals = build_visual_context(session.writer, tmp_path / "round-trip", [])
    planner = CodexSkillPlanner(config=SkillCollectionConfig(planner_timeout_seconds=5),
        ledger_path=tmp_path / "ledger.jsonl", queue_root=tmp_path / "queue")

    async def run():
        pending = asyncio.create_task(asyncio.to_thread(planner.plan, ticket={"ticket_id": "test"},
            scene=SCENE, coverage_cell="cell", failures=[], visual_observations=visuals))
        claim = {"request": None}
        for _ in range(100):
            claim = queue_command(tmp_path / "queue", "claim", {"worker_id": "test-account-worker"})
            if claim["request"] is not None:
                break
            await asyncio.sleep(.01)
        request = claim["request"]
        assert request is not None and request["auth_mode"] == "chatgpt"
        instructions = request["prompt"].split("\nTASK DATA:\n", 1)[0]
        assert "确保采集动作的多样性，不要每个示范都一样，起码包含2-3种" in instructions
        payload = json.loads(request["prompt"].split("\nTASK DATA:\n", 1)[1])
        assert payload["visual_observations"] == visuals
        review = {"manifest_sha256": visuals["manifest_sha256"],
            "viewed_image_ids": [x["image_id"] for x in visuals["images"]],
            "assessment_zh": "单元测试模拟视觉回执；不是真实场景成功证据。"}
        assert queue_command(tmp_path / "queue", "complete", {"request_id": request["request_id"],
            "claim_token": claim["claim_token"], "auth_mode": "chatgpt",
            "plan": plan().model_dump(mode="json"), "visual_review": review})["accepted"]
        result = await pending
        assert result.ticket_id == "test" and planner.last_visual_review == review
    asyncio.run(run())
