import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from omegaconf import OmegaConf
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_execution_horizon_fixed_preserves_policy_horizon():
    import main

    resolved, reason = main._resolve_execution_horizon(
        mode="fixed",
        policy_horizon=8,
        guidance_enabled=True,
        stage_changed=True,
        target_distance=0.01,
        gripper_transition=True,
    )

    assert (resolved, reason) == (8, "fixed")


def test_execution_horizon_adaptive_guidance_off_is_conservative():
    import main

    resolved, reason = main._resolve_execution_horizon(
        mode="adaptive_prefix",
        policy_horizon=8,
        guidance_enabled=False,
        stage_changed=False,
        target_distance=0.20,
        gripper_transition=False,
    )

    assert (resolved, reason) == (8, "guidance_off")


@pytest.mark.parametrize(
    ("stage_changed", "target_distance", "gripper_transition", "expected"),
    [
        (False, 0.20, True, (2, "gripper_transition")),
        (False, 0.01, False, (2, "contact_distance")),
        (True, 0.20, False, (4, "stage_change")),
    ],
)
def test_execution_horizon_events_precede_guidance_off(
    stage_changed,
    target_distance,
    gripper_transition,
    expected,
):
    import main

    assert main._resolve_execution_horizon(
        mode="adaptive_prefix",
        policy_horizon=8,
        guidance_enabled=False,
        stage_changed=stage_changed,
        target_distance=target_distance,
        gripper_transition=gripper_transition,
    ) == expected


def test_execution_horizon_accepts_approved_adaptive_prefix_mode():
    import main

    assert main._resolve_execution_horizon(
        mode="adaptive_prefix",
        policy_horizon=8,
        guidance_enabled=True,
        stage_changed=False,
        target_distance=0.06,
        gripper_transition=False,
    ) == (4, "near_distance")


@pytest.mark.parametrize(
    ("stage_changed", "target_distance", "gripper_transition", "expected"),
    [
        (True, 0.20, False, (4, "stage_change")),
        (False, 0.04, False, (2, "contact_distance")),
        (False, 0.20, True, (2, "gripper_transition")),
        (False, 0.08, False, (4, "near_distance")),
        (False, 0.20, False, (8, "far_distance")),
        (True, 0.20, True, (2, "gripper_transition")),
        (True, 0.04, False, (2, "contact_distance")),
    ],
)
def test_execution_horizon_adaptive_priority(
    stage_changed,
    target_distance,
    gripper_transition,
    expected,
):
    import main

    assert main._resolve_execution_horizon(
        mode="adaptive_prefix",
        policy_horizon=8,
        guidance_enabled=True,
        stage_changed=stage_changed,
        target_distance=target_distance,
        gripper_transition=gripper_transition,
    ) == expected


def test_execution_horizon_missing_target_is_explicit_and_conservative():
    import main

    assert main._resolve_execution_horizon(
        mode="adaptive_prefix",
        policy_horizon=8,
        guidance_enabled=True,
        stage_changed=False,
        target_distance=None,
        gripper_transition=False,
    ) == (8, "target_distance_unavailable")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "mystery"},
        {"mode": "adaptive"},
        {"policy_horizon": 0},
        {"policy_horizon": 6},
        {"far_steps": 4, "near_steps": 8},
        {"near_steps": 2, "contact_steps": 4},
        {"near_distance": -0.1},
        {"near_distance": False},
        {"contact_distance": 0.09},
        {"contact_distance": True},
        {"target_distance": True},
        {"target_distance": float("nan")},
        {"target_distance": float("inf")},
    ],
)
def test_execution_horizon_rejects_invalid_inputs(kwargs):
    import main

    defaults = {
        "mode": "adaptive_prefix",
        "policy_horizon": 8,
        "guidance_enabled": True,
        "stage_changed": False,
        "target_distance": 0.2,
        "gripper_transition": False,
        "far_steps": 8,
        "near_steps": 4,
        "contact_steps": 2,
        "near_distance": 0.08,
        "contact_distance": 0.04,
    }
    defaults.update(kwargs)

    with pytest.raises(ValueError):
        main._resolve_execution_horizon(**defaults)


def test_gripper_transition_detects_torch_and_numpy_prefix_edges():
    import main

    torch_chunk = torch.zeros((1, 8, 7), dtype=torch.float32)
    torch_chunk[0, :, -1] = torch.tensor([-1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0])
    numpy_chunk = torch_chunk.numpy()
    no_edge_chunk = torch.ones((1, 8, 7), dtype=torch.float32)

    assert main._gripper_transition_in_prefix(torch_chunk, prefix_steps=2) is True
    assert main._gripper_transition_in_prefix(numpy_chunk, prefix_steps=2) is True
    assert main._gripper_transition_in_prefix(no_edge_chunk, prefix_steps=2) is False


@pytest.mark.parametrize(
    ("previous_command", "current_command"),
    [(-1.0, 1.0), (1.0, -1.0)],
)
def test_gripper_transition_detects_cross_chunk_boundary(
    previous_command,
    current_command,
):
    import main

    chunk = torch.zeros((1, 8, 7), dtype=torch.float32)
    chunk[0, :, -1] = current_command

    assert main._gripper_transition_in_prefix(
        chunk,
        prefix_steps=2,
        previous_gripper_command=previous_command,
    ) is True


def test_gripper_transition_only_none_is_unavailable():
    import main

    assert main._gripper_transition_in_prefix(None, prefix_steps=2) is None


@pytest.mark.parametrize(
    ("chunk", "prefix_steps"),
    [
        (object(), 2),
        ([[[0.0] * 7] * 8], 2),
        (np.zeros((8, 7)), 2),
        (np.zeros((2, 8, 7)), 2),
        (np.zeros((1, 8, 6)), 2),
        (np.zeros((1, 0, 7)), 2),
        (np.zeros((1, 1, 7)), 2),
        (np.zeros((1, 8, 7)), 1),
        (np.zeros((1, 8, 7)), 9),
        (np.zeros((1, 8, 7)), 2.5),
        (torch.zeros((8, 7)), 2),
        (torch.zeros((1, 8, 6)), 2),
        (torch.zeros((1, 1, 7)), 2),
    ],
)
def test_gripper_transition_rejects_invalid_type_shape_time_or_prefix(
    chunk,
    prefix_steps,
):
    import main

    with pytest.raises(ValueError):
        main._gripper_transition_in_prefix(chunk, prefix_steps=prefix_steps)


@pytest.mark.parametrize(
    "chunk",
    [
        np.full((1, 8, 7), np.nan),
        np.full((1, 8, 7), np.inf),
    ],
)
def test_gripper_transition_rejects_nonfinite_values(chunk):
    import main

    with pytest.raises(ValueError, match="gripper"):
        main._gripper_transition_in_prefix(chunk, prefix_steps=2)


def _run_execution_horizon_episode(
    monkeypatch,
    tmp_path,
    *,
    mode,
    target_distances,
    max_steps=9,
    use_guidance=True,
    stage_sequence=None,
    action_chunk=None,
    expose_metrics=True,
    config_overrides=None,
    guidance_type="eds",
    policy_horizon=8,
    guidance_sequence=None,
    termination_kind="terminated",
    postprocessor=None,
    mechanism_trace=None,
):
    import main

    appended = []
    monkeypatch.setattr(main, "append_jsonl", lambda path, record: appended.append(dict(record)))
    monkeypatch.setattr(main, "add_text_to_image", lambda image, text: image)
    saved_trace_execution_info = []
    if mechanism_trace is not None:
        monkeypatch.setattr(
            main,
            "save_mechanism_trace",
            lambda output_dir, trace, save_tensors: (
                saved_trace_execution_info.append(dict(trace.execution_info)) or []
            ),
        )

    if action_chunk is None:
        action_chunk = torch.zeros((1, policy_horizon, 7), dtype=torch.float32)
        action_chunk[0, :, -1] = 1.0

    class Policy:
        def __init__(self):
            self._action_chunk_horizon = policy_horizon
            self.select_flags = []
            self.plan_index = -1
            self.metrics_reads = 0
            self.current_chunk = None

        def select_action(self, *, generate_new_chunk, guidance_type=None, **kwargs):
            self.select_flags.append(bool(generate_new_chunk))
            if generate_new_chunk:
                self.plan_index += 1
                if isinstance(action_chunk, torch.Tensor):
                    self.current_chunk = action_chunk.clone()
                    row_ids = torch.arange(
                        self.current_chunk.shape[1],
                        dtype=self.current_chunk.dtype,
                        device=self.current_chunk.device,
                    )
                else:
                    self.current_chunk = np.array(action_chunk, copy=True)
                    row_ids = np.arange(self.current_chunk.shape[1])
                self.current_chunk[0, :, 0] = self.plan_index * 100 + row_ids
            return self.current_chunk

        def get_last_eds_metrics(self):
            self.metrics_reads += 1
            distance = target_distances[min(self.plan_index, len(target_distances) - 1)]
            return {} if distance is None else {"target_distance_after": distance}

        def get_normalized_reward(self):
            return 0.0

        def get_last_scale(self):
            return 0.0

        def get_last_eds_mechanism_trace(self):
            return mechanism_trace

    policy = Policy()
    policy.saved_trace_execution_info = saved_trace_execution_info
    if not expose_metrics:
        policy.get_last_eds_metrics = None

    class Adapter:
        suite_name = "libero_object_swap"
        task_id = 0
        vlm_camera = "agentview"

        def __init__(self):
            self.steps = 0
            self.executed_rows = []
            self.postprocess_calls = 0

        def get_task_description(self):
            return "swap objects"

        def get_vlm_image(self):
            return np.zeros((8, 8, 3), dtype=np.uint8)

        def env_postprocessor(self, transition):
            self.postprocess_calls += 1
            processed = transition["action"]
            if postprocessor is not None:
                processed = postprocessor(processed)
            return {"action": processed}

        def step(self, action):
            self.steps += 1
            row_id = action[0]
            self.executed_rows.append(
                float(row_id.item() if hasattr(row_id, "item") else row_id)
            )
            episode_end = self.steps >= max_steps
            terminated = episode_end and termination_kind == "terminated"
            truncated = episode_end and termination_kind == "truncated"
            return {}, 0.0, terminated, truncated, {
                "success": False,
                "behavior_name": "timeout",
            }

    runner = main.Main.__new__(main.Main)
    runner.policy = policy
    runner.policy_type = "rdt"
    runner.adapter = Adapter()
    runner.output_dir = str(tmp_path)
    runner.success_count = 0
    runner.video_recorder = SimpleNamespace(
        add_frame=lambda *args, **kwargs: None,
        save_video=lambda *args, **kwargs: None,
    )
    runner._get_policy_observation = lambda: {}
    runner._append_episode_metadata = lambda **kwargs: None
    runner.keypoint_tracker = SimpleNamespace(
        get_keypoint_positions=lambda: np.zeros((1, 3)),
        get_mask_ids=lambda: np.zeros((1,), dtype=np.int64),
    )
    runner.guidance_fns = {1: [lambda *args: 0.0], 2: [lambda *args: 0.0]}
    runner.current_guide_scale = 1.0
    runner.config = OmegaConf.create(
        {
            "use_guidance": use_guidance,
            "guidance_type": guidance_type,
            "debug_draw_trajectory": False,
            "debug_draw_keypoints": False,
            "execution_horizon_mode": mode,
            "execution_horizon_far": 8,
            "execution_horizon_near": 4,
            "execution_horizon_contact": 2,
            "execution_near_distance": 0.08,
            "execution_contact_distance": 0.04,
            "eds_config": {},
            "eds_eval": {
                "enabled": True,
                "write_metrics": True,
                "save_qualitative": False,
                "output_dir": str(tmp_path),
            },
            "eds_mechanism_pretest": {"enabled": False},
        }
    )
    for key, value in (config_overrides or {}).items():
        runner.config[key] = value

    stages = iter(stage_sequence or [])
    guidance_values = iter(guidance_sequence or [])

    def update_stage(state, gripper_val, upper, lower):
        updated = dict(state)
        updated["current_stage"] = next(stages, updated["current_stage"])
        updated["use_guidance"] = next(
            guidance_values,
            updated["use_guidance"],
        )
        return updated

    runner._update_stage = update_stage
    runner._run_episode(episode=0, episode_dir=str(tmp_path), episode_seed=7)
    metrics_records = [record for record in appended if "execution_horizon_resolved" in record]
    return runner, policy, metrics_records


def test_main_attaches_execution_decision_before_saving_mechanism_trace(
    monkeypatch,
    tmp_path,
):
    from core.eds_mechanism_trace import EDSMechanismTrace

    trace = EDSMechanismTrace(
        suite=None,
        task_id=None,
        episode=None,
        global_step=0,
        reward_mode="normal",
        population_size=4,
        cem_iters=1,
        use_cem=False,
        keypoints=None,
    )
    _, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[0.06],
        max_steps=1,
        mechanism_trace=trace,
        config_overrides={
            "eds_mechanism_pretest": {
                "enabled": True,
                "first_chunk_only": True,
                "max_chunks": 1,
                "seed": 0,
                "save_tensors": False,
                "plot_3d": False,
                "output_dir": str(tmp_path),
            }
        },
    )

    assert records[0]["execution_horizon_resolved"] == 4
    assert policy.saved_trace_execution_info == [
        {
            "enabled": True,
            "execution_horizon_resolved": 4,
            "execution_horizon_reason": "near_distance",
            "execution_horizon_stage_change": False,
            "replan_count": 1,
        }
    ]


def test_fixed_episode_replans_every_eight_steps_without_changing_policy_horizon(
    monkeypatch,
    tmp_path,
):
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="fixed",
        target_distances=[0.01, 0.01],
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [0, 8]
    assert policy._action_chunk_horizon == 8
    assert [record["execution_horizon_resolved"] for record in records] == [8, 8]
    assert [record["replan_count"] for record in records] == [1, 2]


@pytest.mark.parametrize(
    ("target_distance", "expected_steps", "expected_reason"),
    [
        (0.01, [0, 2, 4, 6, 8], "contact_distance"),
        (0.06, [0, 4, 8], "near_distance"),
        (0.20, [0, 8], "far_distance"),
    ],
)
def test_adaptive_episode_replans_at_resolved_prefix_without_mutating_policy(
    monkeypatch,
    tmp_path,
    target_distance,
    expected_steps,
    expected_reason,
):
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[target_distance],
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == expected_steps
    assert policy._action_chunk_horizon == 8
    assert {record["execution_horizon_resolved"] for record in records} == {
        expected_steps[1] - expected_steps[0]
    }
    assert {record["execution_horizon_reason"] for record in records} == {expected_reason}
    assert policy.metrics_reads == len(expected_steps)
    prefix = expected_steps[1] - expected_steps[0]
    assert runner.adapter.executed_rows == [
        float((step // prefix) * 100 + step % prefix)
        for step in range(9)
    ]


def test_execution_horizon_telemetry_marks_only_the_stage_change_chunk(
    monkeypatch,
    tmp_path,
):
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[0.20],
        max_steps=13,
        stage_sequence=[1, 2, 2, 2],
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [0, 8, 12]
    assert [record["execution_horizon_stage_change"] for record in records] == [False, True, False]
    assert [record["execution_horizon_reason"] for record in records] == [
        "far_distance",
        "stage_change",
        "far_distance",
    ]
    assert [record["replan_count"] for record in records] == [1, 2, 3]


def test_execution_horizon_guidance_off_and_missing_metrics_hook_are_compatible(
    monkeypatch,
    tmp_path,
):
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[0.01],
        use_guidance=False,
        expose_metrics=False,
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [0, 8]
    assert records == []


def test_execution_horizon_guidance_on_without_metrics_hook_is_conservative(
    monkeypatch,
    tmp_path,
):
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[0.01],
        use_guidance=True,
        expose_metrics=False,
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [0, 8]
    assert records == []


def test_execution_horizon_gripper_edge_overrides_far_target_in_episode(
    monkeypatch,
    tmp_path,
):
    action_chunk = torch.zeros((1, 8, 7), dtype=torch.float32)
    action_chunk[0, :, -1] = torch.tensor([-1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[0.20],
        action_chunk=action_chunk,
        max_steps=5,
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [0, 2, 4]
    assert {record["execution_horizon_reason"] for record in records} == {
        "gripper_transition"
    }


def test_execution_horizon_defaults_are_fixed_and_eight_steps():
    config = OmegaConf.load(Path(__file__).resolve().parents[1] / "configs" / "config.yaml")

    assert config.main.execution_horizon_mode == "fixed"
    assert config.main.execution_horizon_far == 8
    assert config.main.execution_horizon_near == 4
    assert config.main.execution_horizon_contact == 2
    assert config.main.execution_near_distance == pytest.approx(0.08)
    assert config.main.execution_contact_distance == pytest.approx(0.04)


def test_execution_horizon_missing_target_uses_far_prefix_with_explicit_reason(
    monkeypatch,
    tmp_path,
):
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[None],
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [0, 8]
    assert [record["execution_horizon_reason"] for record in records] == [
        "target_distance_unavailable",
        "target_distance_unavailable",
    ]


def test_execution_horizon_nonfinite_metric_fails_loudly(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="target_distance"):
        _run_execution_horizon_episode(
            monkeypatch,
            tmp_path,
            mode="adaptive_prefix",
            target_distances=[float("nan")],
        )


def test_execution_horizon_loop_rejects_fractional_step_config(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="contact_steps"):
        _run_execution_horizon_episode(
            monkeypatch,
            tmp_path,
            mode="adaptive_prefix",
            target_distances=[0.20],
            config_overrides={"execution_horizon_contact": 2.5},
        )


def test_vls_guidance_on_gripper_edge_keeps_policy_horizon(monkeypatch, tmp_path):
    action_chunk = torch.zeros((1, 8, 7), dtype=torch.float32)
    action_chunk[0, :, -1] = torch.tensor([-1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[0.01],
        action_chunk=action_chunk,
        guidance_type="vls",
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [0, 8]
    assert policy._action_chunk_horizon == 8
    assert records == []


@pytest.mark.parametrize(
    ("mode", "guidance_type", "policy_horizon"),
    [
        ("fixed", "eds", 10),
        ("adaptive_prefix", "vls", 16),
    ],
)
def test_fixed_and_non_eds_paths_never_call_adaptive_helper(
    monkeypatch,
    tmp_path,
    mode,
    guidance_type,
    policy_horizon,
):
    import main

    def fail_if_called(**kwargs):
        raise AssertionError("adaptive execution helper must not be called")

    monkeypatch.setattr(main, "_resolve_execution_horizon", fail_if_called)
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode=mode,
        target_distances=[0.01],
        guidance_type=guidance_type,
        policy_horizon=policy_horizon,
        max_steps=policy_horizon + 1,
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [
        0,
        policy_horizon,
    ]
    assert policy._action_chunk_horizon == policy_horizon


def test_stage_change_precedes_guidance_off_for_adaptive_eds(monkeypatch, tmp_path):
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[0.20],
        max_steps=13,
        stage_sequence=[1, 2, 2],
        guidance_sequence=[True, False, False],
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [0, 8, 12]
    assert runner.adapter.executed_rows == [
        *[float(row) for row in range(8)],
        100.0,
        101.0,
        102.0,
        103.0,
        200.0,
    ]


@pytest.mark.parametrize(
    ("first_sign", "second_sign"),
    [(-1.0, 1.0), (1.0, -1.0)],
)
def test_cross_chunk_gripper_edge_uses_postprocessed_executed_command(
    monkeypatch,
    tmp_path,
    first_sign,
    second_sign,
):
    def apply_plan_gripper(action):
        processed = action.clone()
        plan_id = int(float(processed[0, 0, 0].item()) // 100)
        processed[0, :, -1] = first_sign if plan_id == 0 else second_sign
        return processed

    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[0.20],
        max_steps=9,
        postprocessor=apply_plan_gripper,
    )

    assert [idx for idx, flag in enumerate(policy.select_flags) if flag] == [0, 8]
    assert [record["execution_horizon_reason"] for record in records] == [
        "far_distance",
        "gripper_transition",
    ]
    assert runner.adapter.postprocess_calls == len(policy.select_flags)


@pytest.mark.parametrize("termination_kind", ["terminated", "truncated"])
def test_episode_end_executes_no_extra_action(monkeypatch, tmp_path, termination_kind):
    runner, policy, records = _run_execution_horizon_episode(
        monkeypatch,
        tmp_path,
        mode="adaptive_prefix",
        target_distances=[0.01],
        max_steps=3,
        termination_kind=termination_kind,
    )

    assert runner.adapter.executed_rows == [0.0, 1.0, 100.0]
    assert len(policy.select_flags) == 3


def test_init_components_skips_vlm_when_guidance_disabled(monkeypatch, tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    def _raise_if_vlm_constructed(*args, **kwargs):
        raise AssertionError("VLMAgent should not be constructed when guidance is disabled")

    monkeypatch.setattr(main, "VLMAgent", _raise_if_vlm_constructed)

    runner = main.Main.__new__(main.Main)
    runner.config = OmegaConf.create(
        {
            "use_guidance": False,
            "output_dir": str(tmp_path),
            "cached_functions_dir": None,
            "use_vlm_stage_recognition": False,
        }
    )
    runner.output_dir = str(tmp_path)
    runner.backend = "libero"
    runner.adapter = object()

    runner._init_components(OmegaConf.create({"perception": {}}))

    assert runner.vlm_agent is None
    assert runner.keypoint_detector is None
    assert runner.video_recorder is not None


def test_visualization_action_chunk_prefers_policy_candidates():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    fallback = torch.zeros(1, 3, 7)
    candidates = torch.arange(2 * 3 * 7, dtype=torch.float32).reshape(2, 3, 7)

    class Policy:
        def get_last_visualization_action_candidates(self):
            return candidates

    class Adapter:
        def env_postprocessor(self, transition):
            return {"action": transition["action"] + 1.0}

    visualized = main._get_visualization_action_chunk(Policy(), Adapter(), fallback)

    torch.testing.assert_close(visualized, candidates + 1.0)


def test_main_flat_vls_overrides_merge_into_grouped_config():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    cfg = OmegaConf.create(
        {
            "vls_config": {
                "guide_scale": 40.0,
                "sample_batch_size": 20,
                "use_diversity": True,
                "diversity_scale": 10.0,
                "use_fkd": True,
                "fkd": {"resample_frequency": 5},
            },
            "guide_scale": 12.5,
            "sample_batch_size": 3,
            "use_diversity": False,
            "diversity_scale": 0.75,
            "use_fkd": False,
            "MCMC_steps": 2,
            "sigmoid_k": 6.0,
            "sigmoid_x0": 0.3,
            "start_ratio": 0.4,
            "fkd_config": {"resample_frequency": 9},
        }
    )

    merged = main._main_vls_config(cfg)

    assert merged["guide_scale"] == 12.5
    assert merged["sample_batch_size"] == 3
    assert merged["use_diversity"] is False
    assert merged["diversity_scale"] == 0.75
    assert merged["use_fkd"] is False
    assert merged["MCMC_steps"] == 2
    assert merged["sigmoid_k"] == 6.0
    assert merged["sigmoid_x0"] == 0.3
    assert merged["start_ratio"] == 0.4
    assert merged["fkd"] == {"resample_frequency": 9}


def test_eds_mechanism_pretest_output_root_can_target_qualitative_chunk(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    eds_eval_config = {
        "output_dir": str(tmp_path / "eds_eval"),
    }
    eds_pretest_config = {
        "output_mode": "qualitative_chunk",
        "output_dir": str(tmp_path / "pretest_fallback"),
    }

    root = main._eds_mechanism_pretest_output_root(
        eds_pretest_config=eds_pretest_config,
        eds_eval_config=eds_eval_config,
        run_id="ignored_run_id",
        output_dir=str(tmp_path / "hydra"),
        episode=2,
        global_step=16,
    )

    assert root == (
        tmp_path
        / "eds_eval"
        / "qualitative"
        / "episode_002"
        / "chunk_000016"
    )


def test_execution_failure_saves_partial_episode_video(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    calls = []
    runner = main.Main.__new__(main.Main)
    runner.video_recorder = SimpleNamespace(
        save_video=lambda **kwargs: calls.append(kwargs)
    )

    runner._save_execution_failure_video(
        episode=4,
        episode_dir=str(tmp_path / "episode_5"),
        error=ValueError("bad gripper state"),
    )

    assert calls == [
        {
            "save_path": str(tmp_path / "episode_5" / "episode_5_fail_error"),
            "success": False,
            "behavior_name": "execution_error_ValueError",
        }
    ]


def test_guidance_toggle_without_stage_change_resets_eds_chunk_memory(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    calls = []

    class Recognizer:
        last_result = {}

        def identify_stage_and_guidance(self, **kwargs):
            return 1, False

    runner = main.Main.__new__(main.Main)
    runner.policy = SimpleNamespace(
        get_normalized_reward=lambda: 0.0,
        reset_stage=lambda: calls.append("stage"),
        reset_eds_chunk_memory=lambda reason: calls.append(reason),
    )
    runner.config = {"vlm_query_limit": 10}
    runner.gemini_stage_recognizer = Recognizer()
    runner.adapter = SimpleNamespace(
        get_vlm_image=lambda: torch.zeros(2, 2, 3).numpy(),
        get_task_description=lambda: "swap objects",
    )
    runner.stage_descriptions = ["pick", "place"]
    runner.init_img_with_keypoints = None
    runner.keypoint_id_to_object = {}
    runner.guidance_fns = {1: [], 2: []}
    runner._append_stage_event = lambda event: None
    state = {
        "prev_norm_reward": 0.0,
        "prev_gripper_open": True,
        "current_stage": 1,
        "use_guidance": True,
        "vlm_query_count": 0,
    }

    updated = runner._update_stage(state, 1.0, 0.8, 0.6)

    assert updated["current_stage"] == 1
    assert updated["use_guidance"] is False
    assert calls == ["guidance_change"]


def test_guidance_toggle_without_memory_hook_is_valid_for_vls_policy(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main

    class Recognizer:
        last_result = {}

        def identify_stage_and_guidance(self, **kwargs):
            return 1, False

    runner = main.Main.__new__(main.Main)
    runner.policy = SimpleNamespace(
        get_normalized_reward=lambda: 0.0,
        reset_stage=lambda: None,
    )
    runner.config = {"vlm_query_limit": 10}
    runner.gemini_stage_recognizer = Recognizer()
    runner.adapter = SimpleNamespace(
        get_vlm_image=lambda: torch.zeros(2, 2, 3).numpy(),
        get_task_description=lambda: "swap objects",
    )
    runner.stage_descriptions = ["pick", "place"]
    runner.init_img_with_keypoints = None
    runner.keypoint_id_to_object = {}
    runner.guidance_fns = {1: [], 2: []}
    runner._append_stage_event = lambda event: None

    updated = runner._update_stage(
        {
            "prev_norm_reward": 0.0,
            "prev_gripper_open": True,
            "current_stage": 1,
            "use_guidance": True,
            "vlm_query_count": 0,
        },
        1.0,
        0.8,
        0.6,
    )

    assert updated["current_stage"] == 1
    assert updated["use_guidance"] is False
