import importlib.util
import json
import stat
from pathlib import Path


def _load_runner():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "p2_rollout_clean_tail_runner.py"
    )
    spec = importlib.util.spec_from_file_location(
        "p2_rollout_clean_tail_runner", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _ranking_record(label, **overrides):
    record = {
        "label": label,
        "eligible": True,
        "is_baseline": False,
        "success_count": 3,
        "baseline_task_retention": 2,
        "execution_qpos_error_episodes": 0,
        "collision_push_drop_episodes": 1,
        "selected_max_step_p95": 0.2,
        "selected_trajectory_length_p95": 1.2,
        "eef_direction_diversity_median": 0.7,
        "select_action_latency_median_s": 2.0,
    }
    record.update(overrides)
    return record


def test_phase_a_matrix_is_twelve_sweep_jobs_plus_one_baseline():
    runner = _load_runner()

    jobs = runner.build_jobs(runner.PHASE_A_LEVEL, episodes=10)
    candidates = [job for job in jobs if not job["is_baseline"]]
    controls = [job for job in jobs if job["is_baseline"]]

    assert len(jobs) == 13
    assert len(candidates) == 12
    assert len(controls) == 1
    assert {job["renoise_t_max"] for job in candidates} == {2, 3}
    assert {job["renoise_t_min"] for job in candidates} == {1}
    assert {job["rollout_diversity_scale"] for job in candidates} == {
        5.0,
        10.0,
        15.0,
    }
    assert {job["rollout_diversity_start_ratio"] for job in candidates} == {
        0.4,
        0.6,
    }
    assert {job["rollout_diversity_skip_final_steps"] for job in jobs} == {0}
    assert controls[0]["label"] == (
        "p2_stage_on_baseline_rerun_rt3to1_s20_start06_skip0"
    )


def test_baseline_never_participates_in_winner_ranking():
    runner = _load_runner()
    baseline = _ranking_record(
        "baseline", is_baseline=True, success_count=10
    )
    candidate = _ranking_record("candidate", success_count=0)

    ranked = runner.rank_phase_a_candidates([baseline, candidate])

    assert [record["label"] for record in ranked] == ["candidate"]


def test_nine_level_tie_breaker_is_deterministic():
    runner = _load_runner()
    records = [
        _ranking_record("z_label"),
        _ranking_record("a_label"),
        _ranking_record("more_success", success_count=4),
        _ranking_record("more_retained", baseline_task_retention=3),
        _ranking_record("fewer_qpos", execution_qpos_error_episodes=-1),
        _ranking_record("fewer_collisions", collision_push_drop_episodes=0),
        _ranking_record("smaller_step", selected_max_step_p95=0.1),
        _ranking_record("shorter", selected_trajectory_length_p95=1.0),
        _ranking_record("more_direction", eef_direction_diversity_median=0.8),
        _ranking_record("lower_latency", select_action_latency_median_s=1.0),
    ]

    ranked = runner.rank_phase_a_candidates(records)

    assert [record["label"] for record in ranked] == [
        "more_success",
        "more_retained",
        "fewer_qpos",
        "fewer_collisions",
        "smaller_step",
        "shorter",
        "more_direction",
        "lower_latency",
        "a_label",
        "z_label",
    ]


def test_winner_manifest_is_exclusive_read_only_and_phase_b_is_derived(tmp_path):
    runner = _load_runner()
    output_dir = tmp_path / "winner"
    (output_dir / ".hydra").mkdir(parents=True)
    (output_dir / "eds_eval").mkdir()
    (output_dir / "results.txt").write_text(
        "Success count: 3/10\nSuccess rate: 30.00%\n", encoding="utf-8"
    )
    (output_dir / ".hydra" / "config.yaml").write_text("seed: 0\n", encoding="utf-8")
    (output_dir / ".hydra" / "overrides.yaml").write_text(
        "- seed=0\n", encoding="utf-8"
    )
    (output_dir / "eds_eval" / "eds_metrics.jsonl").write_text("{}\n", encoding="utf-8")
    winner_job = next(
        job
        for job in runner.build_jobs(runner.PHASE_A_LEVEL, episodes=10)
        if not job["is_baseline"]
    )
    winner = _ranking_record(winner_job["label"])
    winner.update({"job": winner_job, "output_dir": str(output_dir)})
    manifest_path = tmp_path / "winner_manifest.json"

    manifest = runner.freeze_winner_manifest(
        [winner],
        path=manifest_path,
        source_report_path=tmp_path / "report.md",
    )

    assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o444
    assert manifest["winner_label"] == winner_job["label"]
    assert manifest["ranking_rule_version"] == runner.RANKING_RULE_VERSION
    assert set(manifest["checksums"]) == {
        "results.txt",
        "eds_eval/eds_metrics.jsonl",
        ".hydra/config.yaml",
        ".hydra/overrides.yaml",
    }
    try:
        runner.freeze_winner_manifest(
            [winner], path=manifest_path, source_report_path=tmp_path / "report.md"
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("immutable manifest was overwritten")

    phase_b = runner.build_jobs(
        runner.PHASE_B_LEVEL, episodes=10, manifest_path=manifest_path
    )
    assert len(phase_b) == 1
    changed = runner.phase_b_profile_diff(winner_job, phase_b[0])
    assert changed == {"rollout_diversity_skip_final_steps": (0, 1)}


def test_resume_partition_reruns_invalid_and_skips_only_valid_complete_jobs():
    runner = _load_runner()
    jobs = [{"job_id": "good"}, {"job_id": "bad"}, {"job_id": "missing"}]

    skipped, runnable = runner.partition_resume_jobs(
        jobs,
        has_outputs=lambda job: job["job_id"] != "missing",
        validity=lambda job: {"valid": job["job_id"] == "good"},
    )

    assert [job["job_id"] for job in skipped] == ["good"]
    assert [job["job_id"] for job in runnable] == ["bad", "missing"]


def test_specialized_validity_requires_new_metrics_and_clean_tail_masks(tmp_path):
    runner = _load_runner()
    metrics = [
        {
            "rollout_rbf_steps_by_iter": [
                {
                    "iter_idx": 0,
                    "n_trunc_steps": 1,
                    "step_indices": [],
                    "step_count": 0,
                    "final_step_rbf_applied": False,
                    "fallback_used": False,
                }
            ],
            "selected_trajectory_length_by_iter": [1.0],
            "population_trajectory_length_mean_by_iter": [1.1],
            "population_trajectory_length_p90_by_iter": [1.2],
            "population_trajectory_length_max_by_iter": [1.3],
            "selected_max_step_displacement_by_iter": [0.2],
            "population_max_step_mean_by_iter": [0.2],
            "population_max_step_p90_by_iter": [0.3],
            "population_max_step_max_by_iter": [0.4],
            "trajectory_length_expansion_ratio_by_iter": [
                {"selected": 1.0, "population_mean": 1.0}
            ],
            "max_step_expansion_ratio_by_iter": [
                {"selected": 1.0, "population_mean": 1.0}
            ],
            "eef_direction_diversity_by_iter": [0.5],
            "endpoint_direction_spread_by_iter": [0.4],
            "chunk_boundary_action_jump": None,
            "gripper_qpos_violation_count": 0,
        }
    ]

    assert runner.sweep_metric_failures(metrics, skip_final_steps=1) == []
    broken = json.loads(json.dumps(metrics))
    broken[0]["rollout_rbf_steps_by_iter"][0]["final_step_rbf_applied"] = True
    assert any(
        "final denoise step" in failure
        for failure in runner.sweep_metric_failures(broken, skip_final_steps=1)
    )



def test_report_writer_emits_required_sections(tmp_path):
    runner = _load_runner()
    report_path = tmp_path / "report.md"
    runner.write_final_report(
        path=report_path,
        phase_a_records=[_ranking_record("candidate", success_count=5)],
        baseline_record=_ranking_record("baseline", is_baseline=True),
        winner_manifest={"winner_label": "candidate", "winner_profile": {}},
        phase_b_record=_ranking_record("candidate_cleantail_skip1", success_count=6),
        storage_audit={"real_root": str(tmp_path), "symlink": "outputs/link"},
        failed_invalid_jobs=[],
    )
    text = report_path.read_text(encoding="utf-8")

    for heading in (
        "Phase A 参数主效应",
        "Winner Ranking",
        "Phase B Clean-Tail 增量",
        "Task-Level SR",
        "方向多样性、轨迹长度与 Max-Step",
        "失败、Latency 与 Qualitative Evidence",
        "Validity Audit",
    ):
        assert heading in text
