import importlib.util
import json
from pathlib import Path

import pytest


def _runner():
    path = Path(__file__).resolve().parents[1] / "scripts/p2_direction_normalized_rbf_runner.py"
    spec = importlib.util.spec_from_file_location("p2_direction_normalized_rbf_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_formal_matrix_is_exactly_preregistered_11_jobs():
    runner = _runner()
    jobs = runner.build_jobs(runner.LEVEL, 10)
    assert len(jobs) == 11
    assert sum(job["role"] == "control" for job in jobs) == 1
    assert sum(job["role"] == "rollout_only" for job in jobs) == 1
    global_jobs = [job for job in jobs if job["role"] == "global"]
    assert len(global_jobs) == 9
    assert {(job["weight_profile"], job["endpoint_profile"]) for job in global_jobs} == {
        (weight, endpoint) for weight in runner.WEIGHTS for endpoint in runner.ENDPOINT_SCALES
    }
    assert all(job["episodes"] == 10 and job["episode_seeds"] == runner.EPISODE_SEEDS for job in jobs)


def test_scope_and_primary_reference_only_change_approved_descriptor_fields():
    runner = _runner()
    jobs = runner.build_jobs(runner.LEVEL, 10)
    control = next(job for job in jobs if job["role"] == "control")
    rollout = next(job for job in jobs if job["role"] == "rollout_only")
    primary = next(job for job in jobs if job["label"].endswith("global_w0_e050"))
    assert control["initial_diversity_descriptor_mode"] == "absolute_eef"
    assert control["rollout_diversity_descriptor_mode"] == "absolute_eef"
    assert rollout["initial_diversity_descriptor_mode"] == "absolute_eef"
    assert rollout["rollout_diversity_descriptor_mode"] == "direction_normalized_eef"
    assert primary["initial_diversity_descriptor_mode"] == "direction_normalized_eef"
    assert primary["rollout_diversity_descriptor_mode"] == "direction_normalized_eef"
    assert (primary["direction_rbf_direction_weight"], primary["direction_rbf_shape_weight"], primary["direction_rbf_endpoint_weight"], primary["direction_rbf_endpoint_scale_m"]) == (0.6, 0.3, 0.1, 0.05)


def test_command_serializes_explicit_descriptor_configuration():
    runner = _runner()
    job = next(job for job in runner.build_jobs(runner.LEVEL, 10) if job["role"] == "rollout_only")
    command = runner._build_main_command(job, "0", 10)
    assert "main.eds_config.initial_diversity_descriptor_mode=absolute_eef" in command
    assert "main.eds_config.rollout_diversity_descriptor_mode=direction_normalized_eef" in command
    assert "main.eds_config.direction_rbf_endpoint_scale_m=0.05" in command
    assert "main.episode_seed_schedule=[44,235,43,546,6,621,197,87,151,548]" in command


def test_command_serializes_suffix_resume_without_changing_seed_schedule():
    runner = _runner()
    job = next(job for job in runner.build_jobs(runner.LEVEL, 10) if job["label"].endswith("global_w1_e025"))
    job["episode_start_index"] = 6

    command = runner._build_main_command(job, "0", 10)

    assert "main.episode_num=10" in command
    assert "main.episode_start_index=6" in command
    assert "backend.libero.task_ids_filter=[0,1,2,3,4,5,6,7,8,9]" in command
    assert "main.episode_seed_schedule=[44,235,43,546,6,621,197,87,151,548]" in command


def test_supplemental_recovery_plan_uses_suffix_only_for_an_exact_valid_prefix():
    runner = _runner()
    analysis = {
        "jobs": [
            {
                "label": "complete",
                "eligible": True,
                "accepted_episode_ids": list(range(10)),
            },
            {
                "label": "suffix",
                "eligible": False,
                "accepted_episode_ids": list(range(6)),
            },
        ]
    }

    assert runner.supplemental_recovery_plan(analysis) == {"suffix": 6}

    analysis["jobs"][1]["accepted_episode_ids"] = [0, 1, 3]
    assert runner.supplemental_recovery_plan(analysis) == {"suffix": 0}


def test_supplemental_recovery_plan_restarts_job_with_non_video_validity_gap():
    runner = _runner()
    analysis = {
        "jobs": [
            {
                "label": "stage_gap",
                "eligible": False,
                "accepted_episode_ids": list(range(8)),
                "validity_failures": [
                    "10/10 exact task/seed results required; found 8/10",
                    "episode 0 has no successful Stage query",
                ],
            },
            {
                "label": "complete_but_invalid",
                "eligible": False,
                "accepted_episode_ids": list(range(10)),
                "validity_failures": ["Hydra profile mismatch: direction_rbf_endpoint_scale_m"],
            },
        ]
    }

    assert runner.supplemental_recovery_plan(analysis) == {
        "stage_gap": 0,
        "complete_but_invalid": 0,
    }


def test_supplemental_ledger_is_append_only_and_separate_from_original_cap(tmp_path):
    runner = _runner()
    job = next(job for job in runner.build_jobs(runner.LEVEL, 10) if job["role"] == "control")
    ledger = tmp_path / "supplemental.jsonl"

    runner.append_supplemental_attempts(
        job,
        [8, 9],
        batch_id="recovery_20260805",
        authorization_id="user-2026-08-05-complete-videos",
        path=ledger,
    )

    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [row["episode"] for row in rows] == [8, 9]
    assert all(row["record_type"] == "supplemental_recovery_attempt" for row in rows)
    assert all(row["episode_seed"] == runner.EPISODE_SEEDS[row["episode"]] for row in rows)


def test_supplemental_joblib_safeguard_is_opt_in_and_recorded_in_job_semantics():
    runner = _runner()
    legacy = next(
        job
        for job in runner.build_jobs(runner.LEVEL, 10)
        if job["label"].endswith("global_w1_e100")
    )
    guarded = dict(legacy)

    runner.apply_supplemental_runtime_safeguards(
        guarded, disable_joblib_multiprocessing=True
    )

    assert "p2_joblib_multiprocessing" not in legacy
    assert guarded["p2_joblib_multiprocessing"] is False
    rebound = runner.base._bind_p2_execution_context(guarded)
    assert (
        rebound["execution_record"]["job_semantics"]["p2_joblib_multiprocessing"]
        is False
    )


def test_supplemental_render_gpu_safeguard_is_opt_in_and_recorded_in_job_semantics():
    runner = _runner()
    legacy = next(
        job
        for job in runner.build_jobs(runner.LEVEL, 10)
        if job["label"].endswith("global_w1_e100")
    )
    guarded = dict(legacy)

    runner.apply_supplemental_runtime_safeguards(
        guarded,
        disable_joblib_multiprocessing=True,
        render_gpu_index=3,
    )

    assert "p2_render_gpu_index" not in legacy
    assert guarded["p2_render_gpu_index"] == 3
    rebound = runner.base._bind_p2_execution_context(guarded)
    semantics = rebound["execution_record"]["job_semantics"]
    assert semantics["p2_render_gpu_index"] == 3
    assert semantics["p2_joblib_multiprocessing"] is False


def test_p2_validity_window_uses_only_the_requested_suffix():
    runner = _runner()

    assert runner.base._p2_expected_episode_ids(
        {"episodes": 10, "episode_start_index": 6}
    ) == {6, 7, 8, 9}
    assert runner.base._p2_expected_episode_ids({"episodes": 10}) == set(range(10))


def test_runtime_torch_hub_seed_copies_only_required_dinov2_assets(tmp_path):
    runner = _runner()
    seed = tmp_path / "seed"
    (seed / "facebookresearch_dinov2_main").mkdir(parents=True)
    (seed / "facebookresearch_dinov2_main/hubconf.py").write_text("# cached\n")
    (seed / "checkpoints").mkdir()
    (seed / "checkpoints/dinov2_vitb14_pretrain.pth").write_bytes(b"weights")
    (seed / "checkpoints/unrelated.pth").write_bytes(b"skip")
    (seed / "trusted_list").write_text("facebookresearch_dinov2_main\n")
    target = tmp_path / "target"

    runner.base._p2_seed_runtime_torch_hub(target, seed_root=seed)

    assert (target / "facebookresearch_dinov2_main/hubconf.py").is_file()
    assert (target / "checkpoints/dinov2_vitb14_pretrain.pth").read_bytes() == b"weights"
    assert not (target / "checkpoints/unrelated.pth").exists()


def test_hydra_override_parser_treats_scientific_epsilon_as_numeric():
    runner = _runner()

    key, value = runner.base._parse_override_assignment(
        "main.eds_config.direction_rbf_path_epsilon=1e-06"
    )

    assert key == "main.eds_config.direction_rbf_path_epsilon"
    assert value == pytest.approx(1.0e-6)
    assert isinstance(value, float)


def test_ranking_uses_preregistered_nine_levels():
    runner = _runner()
    base = {"eligible": True, "is_baseline": False, "success_count": 2, "baseline_task_retention": 1, "execution_qpos_error_episodes": 0, "collision_push_drop_wrong_object": 1, "selected_max_step_p95": .2, "selected_trajectory_length_p95": .4, "direction_retention_score": .9, "selection_latency_median": 2.0}
    records = [{**base, "label": "z"}, {**base, "label": "a"}, {**base, "label": "winner", "success_count": 3}]
    assert [row["label"] for row in runner.rank_candidates(records)] == ["winner", "a", "z"]
