import importlib.util
import csv
import json
import threading
from pathlib import Path

import pytest
import yaml


def _load_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "rdt_eds_eval_runner.py"
    spec = importlib.util.spec_from_file_location("rdt_eds_eval_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_aggressive_rbf_fixture(
    runner,
    *,
    old_schema=False,
    safety_fail_label=None,
):
    values = {
        "iid_baseline": (1.00, 0.40, 0.70, 0.50),
        "rbf_s1_start_null": (1.05, 0.42, 0.71, 0.49),
        "rbf_s5_start06": (1.20, 0.48, 0.72, 0.48),
        "rbf_s10_start06": (1.30, 0.52, 0.73, 0.47),
        "rbf_s20_start06": (1.10, 0.44, 0.69, 0.51),
        "rbf_s5_start08": (1.25, 0.50, 0.72, 0.48),
        "rbf_s10_start08": (1.40, 0.56, 0.74, 0.46),
        "rbf_s20_start08": (1.15, 0.46, 0.68, 0.52),
    }
    for job in runner.build_jobs("level2", episodes=3):
        output_dir = runner.RUN_ROOT / job["job_id"]
        metrics_dir = output_dir / "eds_eval"
        metrics_dir.mkdir(parents=True)
        final_div, endpoint, selected_reward, target_distance = values[job["label"]]
        (output_dir / "results.txt").write_text(
            "Success count: 1/3\nSuccess rate: 33.33%\n",
            encoding="utf-8",
        )
        record = {
            "initial_sampling_mode": job["initial_sampling_mode"],
            "initial_diversity_scale": job["initial_diversity_scale"],
            "initial_diversity_start_ratio": job["initial_diversity_start_ratio"],
            "initial_diversity_steps": 3,
            "initial_diversity_fallback_used": job["label"] == safety_fail_label,
            "initial_diversity_grad_failure_count": 0,
            "nonfinite_count": 0,
            "action_mask_violation_max": 0.0,
            "selected_reward": selected_reward,
            "target_distance_after": target_distance,
            "select_action_latency_s": 2.0,
            "initial_sampler_latency_s": 0.2,
        }
        if not old_schema:
            record.update(
                {
                    "initial_eef_diversity_before_rbf": 0.9
                    if job["label"] != "iid_baseline"
                    else None,
                    "initial_eef_diversity_after_rbf_phase": final_div + 0.1
                    if job["label"] != "iid_baseline"
                    else None,
                    "initial_eef_diversity_final": final_div,
                    "initial_eef_diversity_retention_ratio": 0.8
                    if job["label"] != "iid_baseline"
                    else None,
                    "endpoint_spread_before_rbf": 0.3
                    if job["label"] != "iid_baseline"
                    else None,
                    "endpoint_spread_after_rbf_phase": endpoint + 0.1
                    if job["label"] != "iid_baseline"
                    else None,
                    "endpoint_spread_final": endpoint,
                }
            )
        (metrics_dir / "eds_metrics.jsonl").write_text(
            json.dumps(record) + "\n",
            encoding="utf-8",
        )


def test_level3_restricted_to_libero_object_and_no_other_modes():
    runner = _load_runner()
    forbidden_guidance = "v" + "ls"
    forbidden_policy = "pi" + "05"

    jobs = runner.build_jobs("level3", episodes=10)
    labels = {job["label"] for job in jobs}
    serialized = "\n".join(str(job) for job in jobs).lower()

    assert {job["suite"] for job in jobs} == {"libero_object"}
    assert labels == {
        "unguided",
        "p16_c10",
        "p16_c20",
        "p32_c10",
        "p32_c20",
        "p32_c10_cem",
        "zero",
        "shuffled",
        "inverted",
    }
    assert forbidden_guidance not in serialized
    assert forbidden_policy not in serialized


def test_level4_only_libero_object_perturbation_suites():
    runner = _load_runner()

    jobs = runner.build_jobs("level4", episodes=10)
    suites = {job["suite"] for job in jobs}
    labels = {job["label"] for job in jobs}

    assert suites == set(runner.OOD_SUITES)
    assert suites == {
        "libero_object_object",
        "libero_object_swap",
        "libero_object_lan",
        "libero_object_task",
        "libero_object_env",
        "libero_object_temp",
    }
    assert all(suite.startswith("libero_object_") for suite in suites)
    assert labels == {
        "unguided",
        "eds_softmax_strong_weak_renoise",
        "eds_cem_resample_weak_renoise",
        "eds_rbf_diverse_initial",
    }
    assert len(jobs) == 24


def test_level4_jobs_include_rbf_diverse_initial_sampler_variant():
    runner = _load_runner()

    jobs = runner.build_jobs("level4", episodes=10)
    job = next(job for job in jobs if job["label"] == "eds_rbf_diverse_initial")

    assert job["method"] == "eds_rbf_diverse_initial"
    assert job["initial_sampling_mode"] == "rbf_diverse_denoise"


def test_default_evidence_root_uses_experiment_specific_directory():
    runner = _load_runner()

    assert runner.EVIDENCE_ROOT == (
        runner.WORKTREE_ROOT
        / "docs"
        / "03_evidence"
        / "eds_init_pg_diverse_sampling"
    )
    assert runner.STATUS_CSV == runner.EVIDENCE_ROOT / "rdt_eds_eval_status.csv"


def test_level2_smoke_uses_libero_object_and_aggressive_rbf_sweep():
    runner = _load_runner()

    jobs = runner.build_jobs("level2", episodes=3)
    labels = [job["label"] for job in jobs]
    job_ids = [job["job_id"] for job in jobs]
    expected_labels = [
        "iid_baseline",
        "rbf_s1_start_null",
        "rbf_s5_start06",
        "rbf_s10_start06",
        "rbf_s20_start06",
        "rbf_s5_start08",
        "rbf_s10_start08",
        "rbf_s20_start08",
    ]

    assert {job["suite"] for job in jobs} == {"libero_object"}
    assert labels == expected_labels
    assert job_ids == [f"level2_libero_object_{label}" for label in expected_labels]
    assert len(set(labels)) == len(labels)
    assert len(set(job_ids)) == len(job_ids)

    cmd = runner.build_main_command(jobs[0], gpu="0", timeout_seconds=120)
    assert "backend.libero.task_ids_filter=[0]" in cmd
    assert "main.eds_config.initial_sampling_mode=iid" in cmd
    assert "main.eds_config.initial_diversity_scale=1.0" in cmd
    assert "main.eds_config.initial_diversity_start_ratio=null" in cmd


def test_renoise_tmax_ablation_jobs_match_requested_sweep():
    runner = _load_runner()

    jobs = runner.build_jobs("renoise_ablation", episodes=3)
    labels = [job["label"] for job in jobs]
    job_ids = [job["job_id"] for job in jobs]

    assert labels == [
        "rbf_s20_start06_rt4to1",
        "rbf_s20_start06_rt3to1",
        "rbf_s20_start06_rt2to1",
        "rbf_s20_start08_rt4to1",
        "rbf_s20_start08_rt3to1",
        "rbf_s20_start08_rt2to1",
    ]
    assert {job["suite"] for job in jobs} == {"libero_object"}
    assert job_ids == [f"level3_libero_object_{label}" for label in labels]
    assert [job["renoise_t_max"] for job in jobs] == [4, 3, 2, 4, 3, 2]
    assert {job["renoise_t_min"] for job in jobs} == {1}
    assert {job["initial_sampling_mode"] for job in jobs} == {"rbf_diverse_denoise"}
    assert {job["initial_diversity_scale"] for job in jobs} == {20.0}
    assert [job["initial_diversity_start_ratio"] for job in jobs] == [
        0.6,
        0.6,
        0.6,
        0.8,
        0.8,
        0.8,
    ]


def test_renoise_tmax_ablation_command_saves_qualitative_chunk_traces():
    runner = _load_runner()
    job = runner.build_jobs("renoise_ablation", episodes=3)[0]

    cmd = runner.build_main_command(job, gpu="0", timeout_seconds=120)

    assert "main.eds_mechanism_pretest.enabled=true" in cmd
    assert "main.eds_mechanism_pretest.first_chunk_only=false" in cmd
    assert "main.eds_mechanism_pretest.output_mode=qualitative_chunk" in cmd
    assert "main.eds_mechanism_pretest.max_chunks=2" in cmd
    assert "backend.libero.task_ids_filter=[0]" in cmd
    assert "main.eds_config.renoise_t_max=4" in cmd
    assert "main.eds_config.renoise_t_min=1" in cmd


def test_rollout_rbf_ablation_jobs_match_requested_matrix():
    runner = _load_runner()

    jobs = runner.build_jobs("rollout_rbf_ablation", episodes=3)
    labels = [job["label"] for job in jobs]
    job_ids = [job["job_id"] for job in jobs]

    assert len(jobs) == 128
    assert len(set(labels)) == 128
    assert len(set(job_ids)) == 128
    assert {job["suite"] for job in jobs} == {"libero_object"}
    assert {
        "rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1",
        "rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall",
    }.issubset(set(labels))
    assert {
        "level3_libero_object_rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1",
        "level3_libero_object_rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall",
    }.issubset(set(job_ids))
    assert {job["renoise_t_max"] for job in jobs} == {1, 2, 3, 4}
    assert {job["renoise_t_min"] for job in jobs} == {1}
    assert {job["rollout_diversity_scale"] for job in jobs} == {5.0, 10.0, 15.0, 20.0}
    assert {job["rollout_diversity_start_ratio"] for job in jobs} == {0.6, 0.8}
    assert {job["rollout_diversity_iters"] for job in jobs} == {1, 3, 6, "all"}
    assert {job["initial_sampling_mode"] for job in jobs} == {"rbf_diverse_denoise"}
    assert {job["initial_diversity_scale"] for job in jobs} == {20.0}
    assert {job["initial_diversity_start_ratio"] for job in jobs} == {0.8}
    assert {job["population_size"] for job in jobs} == {16}
    assert {job["cem_iters"] for job in jobs} == {10}
    assert {job["use_cem"] for job in jobs} == {False}
    assert {job["num_elites"] for job in jobs} == {16}
    assert {job["temperature"] for job in jobs} == {0.1}
    assert {job["save_mechanism_trace_to_qualitative"] for job in jobs} == {True}


def test_rollout_rbf_ablation_command_adds_rollout_overrides_and_qualitative_traces():
    runner = _load_runner()
    job = next(
        job
        for job in runner.build_jobs("rollout_rbf_ablation", episodes=3)
        if job["label"] == "rbf_s20_start08_rt4to1_rollrbf_s5_start06_iter1"
    )

    cmd = runner.build_main_command(job, gpu="0", timeout_seconds=120)

    assert "backend.libero.task_ids_filter=[0]" in cmd
    assert "main.eds_config.population_size=16" in cmd
    assert "main.eds_config.cem_iters=10" in cmd
    assert "main.eds_config.use_cem=false" in cmd
    assert "main.eds_config.num_elites=16" in cmd
    assert "main.eds_config.temperature=0.1" in cmd
    assert "main.eds_config.renoise_t_max=4" in cmd
    assert "main.eds_config.renoise_t_min=1" in cmd
    assert "main.eds_config.initial_sampling_mode=rbf_diverse_denoise" in cmd
    assert "main.eds_config.initial_diversity_scale=20.0" in cmd
    assert "main.eds_config.initial_diversity_start_ratio=0.8" in cmd
    assert "main.eds_config.truncated_rollout_mode=rbf_diverse" in cmd
    assert "main.eds_config.rollout_diversity_scale=5.0" in cmd
    assert "main.eds_config.rollout_diversity_start_ratio=0.6" in cmd
    assert "main.eds_config.rollout_diversity_iters=1" in cmd
    assert "main.eds_config.rollout_diversity_skip_final_steps=0" in cmd
    assert "main.eds_mechanism_pretest.enabled=true" in cmd
    assert "main.eds_mechanism_pretest.first_chunk_only=false" in cmd
    assert "main.eds_mechanism_pretest.output_mode=qualitative_chunk" in cmd
    assert "main.eds_mechanism_pretest.max_chunks=2" in cmd


def test_rollout_rbf_ablation_command_serializes_iterall_and_start08_label():
    runner = _load_runner()
    job = next(
        job
        for job in runner.build_jobs("rollout_rbf_ablation", episodes=3)
        if job["label"] == "rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall"
    )

    cmd = runner.build_main_command(job, gpu="0", timeout_seconds=120)

    assert "main.eds_config.renoise_t_max=1" in cmd
    assert "main.eds_config.rollout_diversity_scale=20.0" in cmd
    assert "main.eds_config.rollout_diversity_start_ratio=0.8" in cmd
    assert "main.eds_config.rollout_diversity_iters=all" in cmd


def test_rollout_rbf_ablation_status_row_preserves_sweep_parameters(tmp_path):
    runner = _load_runner()
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    runner.RUN_ROOT = tmp_path / "runs"
    runner.STATUS_CSV = runner.EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
    job = next(
        job
        for job in runner.build_jobs("rollout_rbf_ablation", episodes=3)
        if job["label"] == "rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall"
    )

    row = runner._status_row(job, "pending", gpu="0")
    runner.write_status([row])
    text = runner.STATUS_CSV.read_text(encoding="utf-8")

    assert "initial_sampling_mode" in text
    assert "initial_diversity_scale" in text
    assert "truncated_rollout_mode" in text
    assert "rollout_diversity_scale" in text
    assert "rollout_diversity_iters" in text
    assert "rbf_diverse_denoise" in text
    assert "rbf_diverse" in text
    assert "20.0" in text
    assert "all" in text


def test_rollout_rbf_ablation_write_report_uses_explicit_report_path(tmp_path):
    runner = _load_runner()
    runner.EVIDENCE_ROOT = tmp_path / "evidence"

    report = runner.write_level_report(
        "rollout_rbf_ablation",
        "inconclusive",
        ["rollout-rbf evidence"],
    )
    text = report.read_text(encoding="utf-8")

    assert report == runner.EVIDENCE_ROOT / "2026-07-11-rollout-rbf-level3-parameter-sweep.md"
    assert "Verdict: `inconclusive`" in text
    assert "- rollout-rbf evidence" in text


def test_object_swap_ood_rbf_jobs_match_requested_matrix():
    runner = _load_runner()

    jobs = runner.build_jobs("object_swap_ood_rbf", episodes=10)
    labels = [job["label"] for job in jobs]

    assert len(jobs) == 257
    assert len(set(labels)) == 257
    assert {job["suite"] for job in jobs} == {"libero_object_swap"}
    assert labels[0] == "eds_rbf_init_s20_start08"
    assert {
        "rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1",
        "rbf_s20_start08_rt1to1_rollrbf_s20_start08_iterall",
    }.issubset(set(labels))
    assert {job["renoise_t_max"] for job in jobs if job.get("truncated_rollout_mode") == "rbf_diverse"} == {1, 2, 3, 4}
    assert {job["rollout_diversity_scale"] for job in jobs if job.get("truncated_rollout_mode") == "rbf_diverse"} == {5.0, 10.0, 15.0, 20.0}
    assert {job["rollout_diversity_start_ratio"] for job in jobs if job.get("truncated_rollout_mode") == "rbf_diverse"} == {0.2, 0.4, 0.6, 0.8}
    assert {job["rollout_diversity_iters"] for job in jobs if job.get("truncated_rollout_mode") == "rbf_diverse"} == {1, 3, 6, "all"}
    assert {job["initial_sampling_mode"] for job in jobs} == {"rbf_diverse_denoise"}
    assert {job["initial_diversity_scale"] for job in jobs} == {20.0}
    assert {job["initial_diversity_start_ratio"] for job in jobs} == {0.8}
    assert {job["population_size"] for job in jobs} == {16}
    assert {job["cem_iters"] for job in jobs} == {10}
    assert {job["use_cem"] for job in jobs} == {False}
    assert {job["num_elites"] for job in jobs} == {16}
    assert {job["temperature"] for job in jobs} == {0.1}


def test_object_swap_ood_rbf_command_uses_strict_ood_root_and_qualitative_traces():
    runner = _load_runner()
    job = next(
        job
        for job in runner.build_jobs("object_swap_ood_rbf", episodes=10)
        if job["label"] == "rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1"
    )

    cmd = runner.build_main_command(job, gpu="0", timeout_seconds=120)

    assert "backend.libero.suite_name=libero_object_swap" in cmd
    assert "backend.libero.strict_perturbations=true" in cmd
    assert "backend.libero.task_ids_filter=[0]" not in cmd
    assert "main.render=true" in cmd
    assert f"main.eds_eval.output_dir={runner.OOD_RUN_ROOT / job['job_id'] / 'eds_eval'}" in cmd
    assert f"hydra.run.dir={runner.OOD_RUN_ROOT / job['job_id']}" in cmd
    assert "main.eds_config.initial_sampling_mode=rbf_diverse_denoise" in cmd
    assert "main.eds_config.initial_diversity_scale=20.0" in cmd
    assert "main.eds_config.initial_diversity_start_ratio=0.8" in cmd
    assert "main.eds_config.truncated_rollout_mode=rbf_diverse" in cmd
    assert "main.eds_config.rollout_diversity_start_ratio=0.2" in cmd
    assert "main.eds_mechanism_pretest.output_mode=qualitative_chunk" in cmd


def test_object_swap_ood_rbf_initial_only_command_sets_baseline_rollout():
    runner = _load_runner()
    job = runner.build_jobs("object_swap_ood_rbf", episodes=10)[0]

    cmd = runner.build_main_command(job, gpu="0", timeout_seconds=120)

    assert job["label"] == "eds_rbf_init_s20_start08"
    assert "main.eds_config.truncated_rollout_mode=baseline" in cmd
    assert not any("rollout_diversity_scale" in part for part in cmd)


def test_object_swap_ood_validity_rejects_missing_videos_or_strict_config(tmp_path):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "ood_eval"
    job = runner.build_jobs("object_swap_ood_rbf", episodes=10)[0]
    output_dir = runner.OOD_RUN_ROOT / job["job_id"]
    metrics_dir = output_dir / "eds_eval"
    hydra_dir = output_dir / ".hydra"
    metrics_dir.mkdir(parents=True)
    hydra_dir.mkdir()
    (output_dir / "results.txt").write_text(
        "Success count: 1/10\nSuccess rate: 10.00%\n",
        encoding="utf-8",
    )
    (metrics_dir / "eds_metrics.jsonl").write_text(
        json.dumps({"select_action_latency_s": 1.0}) + "\n",
        encoding="utf-8",
    )
    (hydra_dir / "overrides.yaml").write_text(
        "- backend.libero.suite_name=libero_object_swap\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "videos" in validity["failure_reason"]
    assert "strict" in validity["failure_reason"]


def _write_object_swap_job_artifacts(
    runner,
    job,
    *,
    success=2,
    total=10,
    hydra_lines=None,
    videos=10,
    qualitative=True,
):
    output_dir = runner.OOD_RUN_ROOT / job["job_id"]
    metrics_dir = output_dir / "eds_eval"
    hydra_dir = output_dir / ".hydra"
    metrics_dir.mkdir(parents=True)
    hydra_dir.mkdir()
    for idx in range(videos):
        ep_dir = output_dir / f"episode_{idx:03d}"
        ep_dir.mkdir()
        (ep_dir / "video.mp4").write_bytes(b"fake")
    (output_dir / "results.txt").write_text(
        f"Success count: {success}/{total}\nSuccess rate: {success / total * 100:.2f}%\n",
        encoding="utf-8",
    )
    records = [
        {
            "select_action_latency_s": 1.0,
            "eds_loop_latency_s": 0.8,
            "initial_sampler_latency_s": 0.1,
            "initial_diversity_fallback_used": False,
            "rollout_diversity_fallback_used": False,
            "nonfinite_count": 0,
            "action_mask_violation_max": 0.0,
            "eef_diversity_after_rollout_final": 0.2,
            "eef_diversity_rollout_retention_ratio": 1.0,
        }
    ]
    (metrics_dir / "eds_metrics.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    if qualitative:
        qualitative_dir = metrics_dir / "qualitative" / "episode_000" / "chunk_000000"
        qualitative_dir.mkdir(parents=True)
        (qualitative_dir / "00_initial_population_3d.png").write_bytes(b"fake")
    if hydra_lines is None:
        hydra_lines = [
            part
            for part in runner.build_main_command(job, gpu="0", timeout_seconds=120)
            if "=" in part and not part.startswith("hydra.run.dir=")
        ]
    (hydra_dir / "overrides.yaml").write_text(
        "\n".join(f"- {line}" for line in hydra_lines) + "\n",
        encoding="utf-8",
    )
    return output_dir


def test_object_swap_ood_validity_rejects_stale_hydra_parameter(tmp_path):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "ood_eval"
    job = next(
        job
        for job in runner.build_jobs("object_swap_ood_rbf", episodes=10)
        if job["label"] == "rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1"
    )
    hydra_lines = [
        part
        for part in runner.build_main_command(job, gpu="0", timeout_seconds=120)
        if "=" in part and not part.startswith("hydra.run.dir=")
    ]
    hydra_lines = [
        "main.eds_config.renoise_t_max=3"
        if line == "main.eds_config.renoise_t_max=4"
        else line
        for line in hydra_lines
    ]
    _write_object_swap_job_artifacts(runner, job, hydra_lines=hydra_lines)

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "main.eds_config.renoise_t_max" in validity["failure_reason"]


def test_parse_reference_level4_baselines_for_object_swap(tmp_path):
    runner = _load_runner()
    report = tmp_path / "level_4_vls_pi05_libero_pro_ood.md"
    report.write_text(
        "\n".join(
            [
                "| Suite | RDT unguided | RDT+EDS softmax | RDT+EDS CEM | RDT+VLS | PI05 unguided | PI05+VLS |",
                "|---|---:|---:|---:|---:|---:|---:|",
                "| `libero_object_swap` | 0.00 | 10.00 | 20.00 | 0.00 | 0.00 | 40.00 |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    baselines = runner._parse_reference_level4_baselines(
        report,
        suite="libero_object_swap",
    )

    assert baselines["rdt_unguided"]["success"] == 0
    assert baselines["rdt_unguided"]["total"] == 10
    assert baselines["eds_iid_baseline"]["success"] == 1
    assert baselines["eds_iid_baseline"]["total"] == 10
    assert baselines["eds_iid_baseline"]["source_method"] == "RDT+EDS softmax"


def test_default_reference_level4_report_uses_requested_worktree_when_available():
    runner = _load_runner()
    requested = (
        runner.WORKTREE_ROOT.parents[1]
        / "feat"
        / "rdt_ed_steering_integration"
        / "docs"
        / "03_evidence"
        / "eds_steering"
        / "level_4_vls_pi05_libero_pro_ood.md"
    )

    if requested.exists():
        assert runner.REFERENCE_LEVEL4_REPORT == requested
    assert runner._parse_reference_level4_baselines(
        runner.REFERENCE_LEVEL4_REPORT,
        suite="libero_object_swap",
    )["eds_iid_baseline"]["source_method"] == "RDT+EDS softmax"


def test_object_swap_ood_report_includes_new_results_and_referenced_baselines(tmp_path):
    runner = _load_runner()
    runner.WORKTREE_ROOT = tmp_path
    runner.EVIDENCE_ROOT = tmp_path / "docs" / "03_evidence" / "eds_init_pg_diverse_sampling"
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STATUS_CSV = runner.EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
    runner.REFERENCE_LEVEL4_REPORT = tmp_path / "reference_level4.md"
    runner.REFERENCE_LEVEL4_REPORT.write_text(
        "\n".join(
            [
                "| Suite | RDT unguided | RDT+EDS softmax | RDT+EDS CEM | RDT+VLS | PI05 unguided | PI05+VLS |",
                "|---|---:|---:|---:|---:|---:|---:|",
                "| `libero_object_swap` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 40.00 |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    job = runner.build_jobs("object_swap_ood_rbf", episodes=10)[0]
    _write_object_swap_job_artifacts(runner, job, success=2, total=10)
    runner.write_status(
        [
            {
                **runner._status_row(job, "done", gpu="0"),
                "exit_code": 0,
                "wall_clock_s": "12.3",
            }
        ]
    )

    report = runner.write_object_swap_ood_rbf_report(episodes=10)
    text = report.read_text(encoding="utf-8")

    assert report == runner.EVIDENCE_ROOT / "2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md"
    assert "Suite: `libero_object_swap`" in text
    assert "`rdt_unguided` | `referenced_level4`" in text
    assert "`eds_iid_baseline` | `referenced_level4`" in text
    assert "`eds_rbf_init_s20_start08` | `new_run`" in text
    assert "Strict perturbation verified" in text
    assert "## Aggregated Analysis" in text


def test_object_swap_ood_report_best_setting_uses_only_valid_rows(tmp_path):
    runner = _load_runner()
    runner.WORKTREE_ROOT = tmp_path
    runner.EVIDENCE_ROOT = tmp_path / "docs" / "03_evidence" / "eds_init_pg_diverse_sampling"
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STATUS_CSV = runner.EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
    runner.REFERENCE_LEVEL4_REPORT = tmp_path / "reference_level4.md"
    runner.REFERENCE_LEVEL4_REPORT.write_text(
        "\n".join(
            [
                "| Suite | RDT unguided | RDT+EDS softmax | RDT+EDS CEM | RDT+VLS | PI05 unguided | PI05+VLS |",
                "|---|---:|---:|---:|---:|---:|---:|",
                "| `libero_object_swap` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 40.00 |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    valid_job = runner.build_jobs("object_swap_ood_rbf", episodes=10)[0]
    invalid_job = runner.build_jobs("object_swap_ood_rbf", episodes=10)[1]
    _write_object_swap_job_artifacts(runner, valid_job, success=2, total=10)
    _write_object_swap_job_artifacts(
        runner,
        invalid_job,
        success=9,
        total=10,
        hydra_lines=[
            "- backend.libero.suite_name=libero_object_swap",
            "- backend.libero.strict_perturbations=true",
        ],
    )

    report = runner.write_object_swap_ood_rbf_report(episodes=10)
    text = report.read_text(encoding="utf-8")

    assert "Best observed setting: `eds_rbf_init_s20_start08`" in text
    assert "Best observed setting: `rbf_s20_start08_rt4to1_rollrbf_s5_start02_iter1`" not in text


def test_final_report_lists_object_swap_ood_rbf_report(tmp_path):
    runner = _load_runner()
    runner.WORKTREE_ROOT = tmp_path
    runner.EVIDENCE_ROOT = tmp_path / "docs" / "03_evidence" / "eds_init_pg_diverse_sampling"

    report = runner.write_final_report()
    text = report.read_text(encoding="utf-8")

    assert "2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md" in text


def test_build_main_command_uses_rdt_eds_metrics_dir():
    runner = _load_runner()
    forbidden_override = "guidance_type=" + "v" + "ls"
    forbidden_policy = "pi" + "05"
    job = next(job for job in runner.build_jobs("level3", episodes=7) if job["label"] == "p16_c10")

    cmd = runner.build_main_command(job, gpu="0", timeout_seconds=120)
    text = " ".join(cmd)

    assert cmd[:6] == ["conda", "run", "-n", "vla-pilot", "python", "main.py"]
    assert "policy.type=rdt" in cmd
    assert "backend.libero.suite_name=libero_object" in cmd
    assert "backend.libero.max_episode_steps=240" in cmd
    assert "backend.libero.task_ids_filter=[0]" not in cmd
    assert "main.eds_eval.enabled=true" in cmd
    assert "main.eds_eval.write_metrics=true" in cmd
    assert "main.eds_eval.save_qualitative=true" in cmd
    assert "main.render=false" in cmd
    assert "main.visualize_trajectory=true" in cmd
    assert "main.debug_draw_trajectory=true" in cmd
    assert f"main.eds_eval.output_dir={runner.RUN_ROOT / job['job_id'] / 'eds_eval'}" in cmd
    assert "main.use_guidance=true" in cmd
    assert "main.guidance_type=eds" in cmd
    assert "main.eds_config.population_size=16" in cmd
    assert "main.eds_config.cem_iters=10" in cmd
    assert "main.eds_config.num_elites=32" in cmd
    assert "main.eds_config.temperature=0.1" in cmd
    assert "main.eds_config.renoise_t_max=5" in cmd
    assert "main.eds_config.renoise_t_min=1" in cmd
    assert "main.eds_eval.reward_mode=normal" in cmd
    assert forbidden_override not in text
    assert forbidden_policy not in text


def test_build_main_command_can_use_cached_guidance_offline():
    runner = _load_runner()
    job = next(
        job for job in runner.build_jobs("level2", episodes=3) if job["label"] == "iid_baseline"
    )

    cmd = runner.build_main_command(
        job,
        gpu="3",
        timeout_seconds=120,
        cached_functions_dir="/tmp/vlm_cache",
        offline_vlm=True,
    )

    assert "main.use_vlm_stage_recognition=false" in cmd
    assert "perception.gemini_grounding.enabled=false" in cmd
    assert "main.cached_functions_dir=/tmp/vlm_cache" in cmd
    assert "main.use_guidance=true" in cmd


def test_unguided_offline_command_omits_cached_guidance_override():
    runner = _load_runner()
    job = next(job for job in runner.build_jobs("level3", episodes=3) if job["label"] == "unguided")

    cmd = runner.build_main_command(
        job,
        gpu="3",
        timeout_seconds=120,
        cached_functions_dir="/tmp/vlm_cache",
        offline_vlm=True,
    )

    assert "main.use_vlm_stage_recognition=false" in cmd
    assert "perception.gemini_grounding.enabled=false" in cmd
    assert "main.use_guidance=false" in cmd
    assert not any(part.startswith("main.cached_functions_dir=") for part in cmd)


def test_unguided_main_command_disables_guidance_without_guidance_type():
    runner = _load_runner()
    forbidden_override = "guidance_type=" + "v" + "ls"
    job = next(job for job in runner.build_jobs("level3", episodes=3) if job["label"] == "unguided")

    cmd = runner.build_main_command(job, gpu="0", timeout_seconds=120)
    text = " ".join(cmd)

    assert "policy.type=rdt" in cmd
    assert "main.use_guidance=false" in cmd
    assert "main.guidance_type=eds" not in cmd
    assert forbidden_override not in text


def test_level4_command_uses_strict_perturbations_video_and_method_overrides():
    runner = _load_runner()
    job = next(
        job
        for job in runner.build_jobs("level4", episodes=10)
        if job["label"] == "eds_cem_resample_weak_renoise"
    )

    cmd = runner.build_main_command(job, gpu="0", timeout_seconds=120)

    assert "backend.libero.strict_perturbations=true" in cmd
    assert "main.render=true" in cmd
    assert "main.guidance_type=eds" in cmd
    assert "main.eds_eval.method_label=eds_cem_resample_weak_renoise" in cmd
    assert f"main.eds_eval.job_id={job['job_id']}" in cmd
    assert "main.eds_config.population_size=32" in cmd
    assert "main.eds_config.cem_iters=20" in cmd
    assert "main.eds_config.use_cem=true" in cmd
    assert "main.eds_config.num_elites=8" in cmd
    assert "main.eds_config.temperature=1.0" in cmd
    assert "main.eds_config.renoise_t_max=3" in cmd
    assert "main.eds_config.renoise_t_min=1" in cmd


def test_level2_rbf_sweep_commands_add_initial_sampler_overrides():
    runner = _load_runner()
    expected = {
        "rbf_s1_start_null": (1.0, None),
        "rbf_s5_start06": (5.0, 0.6),
        "rbf_s10_start06": (10.0, 0.6),
        "rbf_s20_start06": (20.0, 0.6),
        "rbf_s5_start08": (5.0, 0.8),
        "rbf_s10_start08": (10.0, 0.8),
        "rbf_s20_start08": (20.0, 0.8),
    }

    jobs_by_label = {job["label"]: job for job in runner.build_jobs("level2", episodes=10)}

    for label, (scale, start_ratio) in expected.items():
        job = jobs_by_label[label]
        cmd = runner.build_main_command(job, gpu="3", timeout_seconds=120)

        assert job["initial_sampling_mode"] == "rbf_diverse_denoise"
        assert job["initial_diversity_scale"] == scale
        assert job["initial_diversity_start_ratio"] == start_ratio
        assert f"main.eds_eval.method_label={label}" in cmd
        assert f"main.eds_eval.job_id=level2_libero_object_{label}" in cmd
        assert "main.eds_config.initial_sampling_mode=rbf_diverse_denoise" in cmd
        assert f"main.eds_config.initial_diversity_scale={scale}" in cmd
        expected_start = "null" if start_ratio is None else str(start_ratio)
        assert f"main.eds_config.initial_diversity_start_ratio={expected_start}" in cmd


def test_level2_run_level_submits_all_sweep_jobs_to_supplied_gpu_workers(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    runner.RUN_ROOT = tmp_path / "runs"
    runner.STATUS_CSV = runner.EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
    seen_jobs = []
    first_wave_gpus = []
    lock = threading.Lock()
    first_wave = threading.Barrier(3)

    def fake_run_job(
        job,
        gpu,
        timeout_seconds,
        *,
        cached_functions_dir=None,
        offline_vlm=False,
    ):
        del timeout_seconds, cached_functions_dir, offline_vlm
        with lock:
            seen_jobs.append((job["label"], gpu))
            if len(first_wave_gpus) < 3:
                first_wave_gpus.append(gpu)
                wait_for_worker = True
            else:
                wait_for_worker = False
        if wait_for_worker:
            try:
                first_wave.wait(timeout=2)
            except threading.BrokenBarrierError:
                pass
        return runner._status_row(job, "done", gpu=gpu)

    monkeypatch.setattr(runner, "run_job", fake_run_job)

    exit_code = runner.run_level("level2", 3, "0,1,2", timeout_seconds=120)

    assert exit_code == 0
    expected_labels = [
        "iid_baseline",
        "rbf_s1_start_null",
        "rbf_s5_start06",
        "rbf_s10_start06",
        "rbf_s20_start06",
        "rbf_s5_start08",
        "rbf_s10_start08",
        "rbf_s20_start08",
    ]
    assert len(seen_jobs) == len(expected_labels)
    assert {label for label, _gpu in seen_jobs} == set(expected_labels)
    assert set(first_wave_gpus) == {"0", "1", "2"}


def test_aggressive_rbf_report_includes_eef_metrics_and_delta_tables(tmp_path):
    runner = _load_runner()
    runner.WORKTREE_ROOT = tmp_path
    runner.EVIDENCE_ROOT = tmp_path / "docs" / "03_evidence" / "eds_init_pg_diverse_sampling"
    runner.RUN_ROOT = tmp_path / "outputs" / "rdt_eds_eval"
    runner.STATUS_CSV = runner.EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
    _write_aggressive_rbf_fixture(runner)

    report = runner.write_aggressive_rbf_report(episodes=3)
    text = report.read_text(encoding="utf-8")

    assert report == (
        runner.EVIDENCE_ROOT / "2026-07-09-aggressive-rbf-parameter-sweep.md"
    )
    assert "# RBF+EDS Aggressive Initial Diversity Parameter Sweep" in text
    assert "Verdict: `pass`" in text
    assert "initial_eef_diversity_final" in text
    assert "endpoint_spread_final" in text
    assert "## Mechanism Gate" in text
    assert "## Utility Gate" in text
    assert "## Delta vs IID Baseline" in text
    assert "## Delta vs Default RBF" in text
    assert "| `rbf_s10_start08` | 10.0 | 0.8 |" in text
    assert "| `rbf_s10_start08` | 0.400 | 0.160 | 0.040 | -0.040 | `pass` |" in text
    assert "| `rbf_s10_start08` | 0.350 | 0.140 | 0.030 | -0.030 |" in text


def test_aggressive_rbf_report_blocks_old_schema_metrics(tmp_path):
    runner = _load_runner()
    runner.WORKTREE_ROOT = tmp_path
    runner.EVIDENCE_ROOT = tmp_path / "docs" / "03_evidence" / "eds_init_pg_diverse_sampling"
    runner.RUN_ROOT = tmp_path / "outputs" / "rdt_eds_eval"
    runner.STATUS_CSV = runner.EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
    _write_aggressive_rbf_fixture(runner, old_schema=True)

    report = runner.write_aggressive_rbf_report(episodes=3)
    text = report.read_text(encoding="utf-8")

    assert "Verdict: `blocked`" in text
    assert "## Missing Required Metrics" in text
    assert "`iid_baseline`: initial_eef_diversity_final, endpoint_spread_final" in text


def test_aggressive_rbf_report_fails_on_safety_gate_failure(tmp_path):
    runner = _load_runner()
    runner.WORKTREE_ROOT = tmp_path
    runner.EVIDENCE_ROOT = tmp_path / "docs" / "03_evidence" / "eds_init_pg_diverse_sampling"
    runner.RUN_ROOT = tmp_path / "outputs" / "rdt_eds_eval"
    runner.STATUS_CSV = runner.EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
    _write_aggressive_rbf_fixture(runner, safety_fail_label="rbf_s20_start06")

    report = runner.write_aggressive_rbf_report(episodes=3)
    text = report.read_text(encoding="utf-8")

    assert "Verdict: `fail`" in text
    assert "| `rbf_s20_start06` | 1 | 0 | 0 | 0.000 | `fail` |" in text


def test_unguided_main_command_omits_initial_sampler_overrides():
    runner = _load_runner()
    job = next(job for job in runner.build_jobs("level4", episodes=10) if job["label"] == "unguided")

    cmd = runner.build_main_command(job, gpu="3", timeout_seconds=120)

    assert not any(part.startswith("main.eds_config.initial_sampling_mode=") for part in cmd)
    assert not any(part.startswith("main.eds_config.initial_diversity_scale=") for part in cmd)
    assert not any(part.startswith("main.eds_config.initial_diversity_start_ratio=") for part in cmd)


def test_level4_report_includes_initial_sampler_latency_and_fallbacks(tmp_path):
    runner = _load_runner()
    runner.WORKTREE_ROOT = tmp_path
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    runner.RUN_ROOT = tmp_path / "runs"
    job = next(
        job
        for job in runner.build_jobs("level4", episodes=10)
        if job["label"] == "eds_rbf_diverse_initial"
    )
    output_dir = runner.RUN_ROOT / job["job_id"]
    metrics_dir = output_dir / "eds_eval"
    metrics_dir.mkdir(parents=True)
    (output_dir / "results.txt").write_text(
        "Success count: 1/2\nSuccess rate: 50.00%\n",
        encoding="utf-8",
    )
    records = [
        {
            "select_action_latency_s": 2.0,
            "eds_loop_latency_s": 0.5,
            "initial_sampler_latency_s": 0.1,
            "initial_diversity_fallback_used": True,
        },
        {
            "select_action_latency_s": 4.0,
            "eds_loop_latency_s": 1.5,
            "initial_sampler_latency_s": 0.3,
            "initial_diversity_fallback_used": False,
        },
    ]
    (metrics_dir / "eds_metrics.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    report = runner.write_level4_report(episodes=10)
    text = report.read_text(encoding="utf-8")

    assert (
        "| Suite | Method | Complete | Success | SR | Select Latency Mean | EDS Latency Mean | "
        "Initial Sampler Latency Mean | Initial Fallback Count | Videos | Metrics | Qual PNG |"
    ) in text
    assert "| `libero_object_object` | `eds_rbf_diverse_initial` | `True` | 1/2 | 50.00 | 3.000 | 1.000 | 0.200 | 1 | 0 | 2 | 0 |" in text


def test_level_report_names_match_protocol():
    runner = _load_runner()

    assert runner.LEVEL_REPORTS["level0"] == "level_0_deployment_correctness.md"
    assert runner.LEVEL_REPORTS["level1"] == "level_1_mechanism_probe.md"
    assert runner.LEVEL_REPORTS["level2"] == "level_2_online_smoke.md"
    assert runner.LEVEL_REPORTS["level3"] == "level_3_libero_object_success.md"
    assert (
        runner.LEVEL_REPORTS["rollout_rbf_ablation"]
        == "2026-07-11-rollout-rbf-level3-parameter-sweep.md"
    )
    assert runner.LEVEL_REPORTS["level4"] == "level_4_libero_pro_ood.md"
    assert runner.LEVEL_REPORTS["final"] == "rdt_eds_final_evaluation_report.md"


def test_level0_and_level1_commands_exposed():
    runner = _load_runner()
    forbidden_override = "guidance_type=" + "v" + "ls"

    level0 = " ".join(runner.level0_command())
    level1 = " ".join(runner.level1_command())

    assert "test_eds_loop_records_deployment_counters" in level0
    assert "test_eds_zero_reward_records_no_reward_spread" in level0
    assert "test_eds_artifacts_are_decoded_action_candidates" in level0
    assert "test_eds_config_rejects_invalid_reward_mode" in level0
    assert "policy.type=rdt" in level1
    assert "backend.libero.suite_name=libero_object" in level1
    assert "backend.libero.task_ids_filter=[0]" in level1
    assert "main.guidance_type=eds" in level1
    assert forbidden_override not in level1


def test_level1_commands_cover_required_reward_modes():
    runner = _load_runner()

    commands = [" ".join(command) for command in runner.level1_commands()]

    assert len(commands) == 4
    assert any("main.eds_eval.reward_mode=normal" in command for command in commands)
    assert any("main.eds_eval.reward_mode=zero" in command for command in commands)
    assert any("main.eds_eval.reward_mode=shuffled_keypoints" in command for command in commands)
    assert any("main.eds_eval.reward_mode=inverted" in command for command in commands)


def test_run_level_callable():
    runner = _load_runner()

    assert callable(runner.run_level)


P2_STAGE_A_LABELS = [
    "p2_legacy_stage_on_rerun",
    "p2_sel_ess05",
    "p2_sel_ess07",
    "p2_adaptrbf_t08_s10",
    "p2_adaptrbf_t10_s20",
    "p2_divres_k2_e1",
    "p2_divres_k4_e2",
    "p2_memory25",
    "p2_memory50",
    "p2_schedule_balanced",
    "p2_schedule_contact",
]


def _p2_manifest(runner, path, profiles):
    runner.P2_OUTPUT_ROOT = path.parent / "p2_outputs"
    runner.P2_STAGE_A_REPORT_PATH = path.parent / "stage_a_report.md"
    runner.P2_STAGE_A_REPORT_PATH.write_text("stage a evidence\n", encoding="utf-8")
    runner._ffprobe_video_readable = lambda _path: True
    source_labels = {
        source.get("label")
        for profile in profiles
        if isinstance(profile, dict)
        for source in profile.get("source_stage_a_jobs", [])
        if isinstance(source, dict) and source.get("label") in P2_STAGE_A_LABELS
    }
    jobs = {
        job["label"]: job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)
    }
    _write_valid_p2_job(
        runner, jobs["p2_legacy_stage_on_rerun"], success_count=4
    )
    for label in source_labels:
        _write_valid_p2_job(runner, jobs[label], success_count=5)
    normalized_profiles = []
    for original in profiles:
        profile = dict(original)
        profile.setdefault("selection_reason", "pre-registered Stage A selection")
        sources = []
        for original_source in profile.get("source_stage_a_jobs", []):
            source = dict(original_source)
            source.setdefault("success_count", 5)
            source.setdefault("success_rate", 50.0)
            source.setdefault("selection_reason", "higher SR than baseline")
            sources.append(source)
        if "source_stage_a_jobs" in profile:
            profile["source_stage_a_jobs"] = sources
        normalized_profiles.append(profile)
    payload = {
        "schema_version": 1,
        "created_at": "2026-08-02T00:00:00+00:00",
        "git_revision": runner._git_head_revision(),
        "code_state_sha256": runner._p2_code_state_sha256(),
        "stage_a_report_sha256": runner._sha256_file(runner.P2_STAGE_A_REPORT_PATH),
        "profiles": normalized_profiles,
    }
    payload["manifest_sha256"] = runner._canonical_manifest_sha256(payload)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _active_p2_profile(
    label="p2_integrated_full", overrides=None, source_label="p2_sel_ess05"
):
    return {
        "label": label,
        "status": "active",
        "overrides": overrides
        or {
            "main.eds_config.parent_weighting_mode": "adaptive_ess",
            "main.eds_config.selection_ess_target_ratio": 0.5,
        },
        "source_stage_a_jobs": [
            {
                "label": source_label,
                "valid": True,
                "eligible": True,
            }
        ],
    }


def test_p2_stage_a_matrix_has_11_controlled_jobs():
    runner = _load_runner()

    jobs = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", episodes=10)

    assert [job["label"] for job in jobs] == P2_STAGE_A_LABELS
    assert len(jobs) == 11
    assert {job["suite"] for job in jobs} == {"libero_object_swap"}
    assert {job["episodes"] for job in jobs} == {10}
    assert all("task_ids_filter" not in job for job in jobs)


def test_p2_pretest_has_6_profiles_and_tasks_0_8():
    runner = _load_runner()

    jobs = runner.build_jobs("p2_adaptive_eds_rbf_pretest", episodes=2)

    assert [job["label"] for job in jobs] == [
        "p2_legacy_stage_on_rerun",
        "p2_sel_ess05",
        "p2_adaptrbf_t10_s20",
        "p2_divres_k4_e2",
        "p2_memory25",
        "p2_schedule_contact",
    ]
    assert len(jobs) == 6
    assert all(job["task_ids_filter"] == [0, 8] for job in jobs)
    assert sum(job["episodes"] for job in jobs) == 12
    with pytest.raises(ValueError, match="exactly 2"):
        runner.build_jobs("p2_adaptive_eds_rbf_pretest", episodes=10)


def test_p2_stage_a_profiles_are_single_factor_diffs():
    runner = _load_runner()
    jobs = {
        job["label"]: job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_stage_a", episodes=10)
    }
    ignored = {"label", "method", "job_id", "config_fingerprint", "execution_record"}
    baseline = {key: value for key, value in jobs[P2_STAGE_A_LABELS[0]].items() if key not in ignored}
    expected_diffs = {
        "p2_sel_ess05": {"parent_weighting_mode", "selection_ess_target_ratio"},
        "p2_sel_ess07": {"parent_weighting_mode", "selection_ess_target_ratio"},
        "p2_adaptrbf_t08_s10": {
            "rollout_diversity_control_mode",
            "rollout_diversity_target_ratio",
            "rollout_diversity_scale_max",
        },
        "p2_adaptrbf_t10_s20": {"rollout_diversity_control_mode"},
        "p2_divres_k2_e1": {
            "parent_coverage_mode",
            "parent_anchor_count",
            "elite_carryover_count",
        },
        "p2_divres_k4_e2": {
            "parent_coverage_mode",
            "parent_anchor_count",
            "elite_carryover_count",
        },
        "p2_memory25": {"chunk_population_mode", "chunk_memory_fraction"},
        "p2_memory50": {"chunk_population_mode", "chunk_memory_fraction"},
        "p2_schedule_balanced": {
            "search_schedule_mode",
            "execution_horizon_mode",
            "execution_horizon_contact",
        },
        "p2_schedule_contact": {"search_schedule_mode", "execution_horizon_mode"},
    }
    for label, expected in expected_diffs.items():
        profile = {key: value for key, value in jobs[label].items() if key not in ignored}
        assert {key for key in baseline if baseline[key] != profile[key]} == expected


def test_p2_baseline_contains_all_fixed_and_component_fields():
    runner = _load_runner()
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", episodes=10)[0]
    expected = {
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 16,
        "temperature": 0.1,
        "renoise_t_max": 3,
        "renoise_t_min": 1,
        "initial_sampling_mode": "rbf_diverse_denoise",
        "initial_diversity_scale": 20.0,
        "initial_diversity_start_ratio": 0.8,
        "truncated_rollout_mode": "rbf_diverse",
        "rollout_diversity_scale": 20.0,
        "rollout_diversity_start_ratio": 0.6,
        "rollout_diversity_iters": "all",
        "rollout_diversity_skip_final_steps": 0,
        "parent_weighting_mode": "legacy_temperature",
        "selection_ess_target_ratio": 0.6,
        "selection_beta_max": 100.0,
        "selection_bisection_steps": 24,
        "parent_coverage_mode": "none",
        "parent_anchor_count": 0,
        "parent_anchor_reward_quantile": 0.5,
        "elite_carryover_count": 0,
        "rollout_diversity_control_mode": "fixed",
        "rollout_diversity_target_ratio": 1.0,
        "rollout_diversity_band_ratio": 0.2,
        "rollout_diversity_scale_min": 0.0,
        "rollout_diversity_scale_max": 20.0,
        "rollout_diversity_decay_floor": 0.25,
        "chunk_population_mode": "fresh",
        "chunk_memory_fraction": 0.0,
        "chunk_memory_renoise_steps": 2,
        "chunk_memory_reward_guard_quantile": 0.25,
        "search_schedule_mode": "legacy_linear",
        "adaptive_min_cem_iters": 4,
        "adaptive_early_stop_patience": 2,
        "adaptive_reward_improvement_eps": 1e-3,
        "execution_horizon_mode": "fixed",
        "execution_horizon_far": 8,
        "execution_horizon_near": 4,
        "execution_horizon_contact": 2,
        "execution_near_distance": 0.08,
        "execution_contact_distance": 0.04,
    }
    assert {key: job[key] for key in expected} == expected


@pytest.mark.parametrize(
    "profiles,count",
    [
        ([], 0),
        ([_active_p2_profile()], 1),
        (
            [
                _active_p2_profile(),
                _active_p2_profile(
                    "p2_integrated_minimal",
                    {"main.eds_config.chunk_population_mode": "warm_start_mix", "main.eds_config.chunk_memory_fraction": 0.25},
                    "p2_memory25",
                ),
            ],
            2,
        ),
    ],
)
def test_p2_stage_b_accepts_zero_to_two_active_profiles(tmp_path, profiles, count):
    runner = _load_runner()
    manifest = tmp_path / "manifest.json"
    payload = _p2_manifest(runner, manifest, profiles)

    jobs = runner.build_jobs(
        "p2_adaptive_eds_rbf_stage_b",
        episodes=10,
        manifest_path=manifest,
    )

    assert len(jobs) == count
    assert all(job["manifest_sha256"] == payload["manifest_sha256"] for job in jobs)
    assert all(job["config_fingerprint"] == runner._p2_config_fingerprint(job) for job in jobs)


def test_p2_stage_b_skips_not_eligible_slots(tmp_path):
    runner = _load_runner()
    manifest = tmp_path / "manifest.json"
    _p2_manifest(
        runner,
        manifest,
        [
            {
                "label": "p2_integrated_full",
                "status": "not_eligible",
                "selection_reason": "no eligible composition",
            },
            _active_p2_profile("p2_integrated_minimal"),
        ],
    )
    jobs = runner.build_jobs("p2_adaptive_eds_rbf_stage_b", 10, manifest_path=manifest)
    assert [job["label"] for job in jobs] == ["p2_integrated_minimal"]


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda profiles: profiles * 3, "at most 2"),
        (lambda profiles: [{**profiles[0], "label": "result_driven_best"}], "label"),
        (lambda profiles: [profiles[0], profiles[0]], "unique"),
        (lambda profiles: [{**profiles[0], "overrides": {"qd_archive_mode": "map_elites"}}], "unknown"),
        (
            lambda profiles: [
                {
                    **profiles[0],
                    "source_stage_a_jobs": [{"label": "p2_sel_ess05", "valid": False, "eligible": True}],
                }
            ],
            "eligible source",
        ),
        (
            lambda profiles: [
                {
                    **profiles[0],
                    "source_stage_a_jobs": [{"label": "not_stage_a", "valid": True, "eligible": True}],
                }
            ],
            "Stage A",
        ),
    ],
)
def test_p2_stage_b_rejects_invalid_profiles(tmp_path, mutator, match):
    runner = _load_runner()
    manifest = tmp_path / "manifest.json"
    _p2_manifest(runner, manifest, mutator([_active_p2_profile()]))
    with pytest.raises(ValueError, match=match):
        runner.build_jobs("p2_adaptive_eds_rbf_stage_b", 10, manifest_path=manifest)


def test_p2_stage_b_rejects_missing_or_tampered_manifest(tmp_path):
    runner = _load_runner()
    with pytest.raises(ValueError, match="manifest"):
        runner.build_jobs("p2_adaptive_eds_rbf_stage_b", 10, manifest_path=tmp_path / "missing.json")
    manifest = tmp_path / "manifest.json"
    payload = _p2_manifest(runner, manifest, [_active_p2_profile()])
    payload["git_revision"] = "c" * 40
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        runner.build_jobs("p2_adaptive_eds_rbf_stage_b", 10, manifest_path=manifest)


def test_p2_stage_b_rejects_current_head_report_and_code_state_mismatch(tmp_path):
    runner = _load_runner()
    manifest = tmp_path / "manifest.json"
    payload = _p2_manifest(runner, manifest, [_active_p2_profile()])
    for field, value, match in [
        ("git_revision", "a" * 40, "HEAD"),
        ("stage_a_report_sha256", "b" * 64, "Stage A report"),
        ("code_state_sha256", "c" * 64, "code state"),
    ]:
        changed = {**payload, field: value}
        changed["manifest_sha256"] = runner._canonical_manifest_sha256(changed)
        manifest.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(ValueError, match=match):
            runner.build_jobs("p2_adaptive_eds_rbf_stage_b", 10, manifest_path=manifest)


def test_p2_stage_b_rejects_declared_source_when_actual_stage_a_is_invalid(tmp_path):
    runner = _load_runner()
    manifest = tmp_path / "manifest.json"
    _p2_manifest(runner, manifest, [_active_p2_profile()])
    source = runner.P2_OUTPUT_ROOT / "stage_a" / "p2_sel_ess05"
    next(source.glob("episode_*/*.mp4")).unlink()
    with pytest.raises(ValueError, match="actual Stage A.*invalid"):
        runner.build_jobs("p2_adaptive_eds_rbf_stage_b", 10, manifest_path=manifest)


def test_p2_stage_b_rejects_overrides_not_exactly_derived_from_sources(tmp_path):
    runner = _load_runner()
    manifest = tmp_path / "manifest.json"
    profile = _active_p2_profile(
        overrides={
            "main.eds_config.parent_weighting_mode": "adaptive_ess",
            "main.eds_config.selection_ess_target_ratio": 0.5,
            "main.eds_config.chunk_population_mode": "warm_start_mix",
            "main.eds_config.chunk_memory_fraction": 0.99,
        }
    )
    _p2_manifest(runner, manifest, [profile])
    with pytest.raises(ValueError, match="exact Stage A source diff"):
        runner.build_jobs("p2_adaptive_eds_rbf_stage_b", 10, manifest_path=manifest)


def test_p2_storage_gate_accepts_only_expected_shared_target(tmp_path):
    runner = _load_runner()
    allowed = tmp_path / "mnt" / "data" / "shared2" / "hynx" / "VLA-Pilot++"
    target = allowed / "exp" / "outputs"
    target.mkdir(parents=True)
    link = tmp_path / "worktree" / "outputs" / "p2"
    link.parent.mkdir(parents=True)
    link.symlink_to(target, target_is_directory=True)
    usage = lambda _path: type("Usage", (), {"free": 21 * 1024**3})()

    assert runner._validate_p2_output_storage(
        link_path=link,
        expected_target=target,
        allowed_prefix=allowed,
        disk_usage_fn=usage,
        writable_fn=lambda _path, _mode: True,
        device_fn=lambda path: 2 if Path(path).resolve() == target.resolve() else 1,
        mountpoint_fn=lambda _path: allowed.parents[1],
        required_mount=allowed.parents[1],
        comparison_paths=[tmp_path / "worktree", tmp_path / "home", Path("/")],
    ) == target.resolve()


@pytest.mark.parametrize("case", ["regular", "dangling", "wrong", "unwritable", "low_free"])
def test_p2_storage_gate_rejects_unsafe_paths(tmp_path, case):
    runner = _load_runner()
    allowed = tmp_path / "mnt" / "data" / "shared2" / "hynx" / "VLA-Pilot++"
    expected = allowed / "expected"
    expected.mkdir(parents=True)
    link = tmp_path / "worktree" / "p2"
    link.parent.mkdir(parents=True)
    if case == "regular":
        link.mkdir()
    elif case == "dangling":
        link.symlink_to(tmp_path / "missing", target_is_directory=True)
    elif case == "wrong":
        wrong = tmp_path / "home" / "output"
        wrong.mkdir(parents=True)
        link.symlink_to(wrong, target_is_directory=True)
    else:
        link.symlink_to(expected, target_is_directory=True)
    free = 19 * 1024**3 if case == "low_free" else 21 * 1024**3
    with pytest.raises(RuntimeError):
        runner._validate_p2_output_storage(
            link_path=link,
            expected_target=expected,
            allowed_prefix=allowed,
            disk_usage_fn=lambda _path: type("Usage", (), {"free": free})(),
            writable_fn=lambda _path, _mode: case != "unwritable",
            device_fn=lambda path: 2 if Path(path).resolve() == expected.resolve() else 1,
            mountpoint_fn=lambda _path: allowed.parents[1],
            required_mount=allowed.parents[1],
            comparison_paths=[tmp_path / "worktree", tmp_path / "home", Path("/")],
        )


@pytest.mark.parametrize("failure", ["same_device", "wrong_mount"])
def test_p2_storage_gate_rejects_unmounted_or_home_device_target(tmp_path, failure):
    runner = _load_runner()
    shared_mount = tmp_path / "mnt" / "data" / "shared2"
    allowed = shared_mount / "hynx" / "VLA-Pilot++"
    target = allowed / "outputs"
    target.mkdir(parents=True)
    worktree = tmp_path / "home" / "worktree"
    worktree.mkdir(parents=True)
    link = worktree / "p2"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(RuntimeError, match="device|mount"):
        runner._validate_p2_output_storage(
            link_path=link,
            expected_target=target,
            allowed_prefix=allowed,
            disk_usage_fn=lambda _path: type("Usage", (), {"free": 21 * 1024**3})(),
            writable_fn=lambda _path, _mode: True,
            device_fn=(
                (lambda _path: 1)
                if failure == "same_device"
                else (lambda path: 2 if Path(path).resolve() == target.resolve() else 1)
            ),
            mountpoint_fn=lambda _path: (
                shared_mount if failure == "same_device" else tmp_path / "mnt"
            ),
            required_mount=shared_mount,
            comparison_paths=[worktree, tmp_path / "home", Path("/")],
        )


def test_p2_job_storage_revalidation_rejects_link_swap_and_child_symlink(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    real_root = tmp_path / "shared2" / "p2"
    real_root.mkdir(parents=True)
    link = tmp_path / "worktree" / "p2"
    link.parent.mkdir(parents=True)
    link.symlink_to(real_root, target_is_directory=True)
    runner.P2_OUTPUT_ROOT = link
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    runner._bind_p2_execution_context(job, real_root=real_root, storage_enforced=True)
    monkeypatch.setattr(runner, "_validate_p2_output_storage", lambda: link.resolve())
    runner._revalidate_p2_job_storage(job)

    other = tmp_path / "other"
    other.mkdir()
    link.unlink()
    link.symlink_to(other, target_is_directory=True)
    with pytest.raises(RuntimeError, match="changed|root"):
        runner._revalidate_p2_job_storage(job)

    link.unlink()
    link.symlink_to(real_root, target_is_directory=True)
    outside_stage = tmp_path / "outside-stage"
    outside_stage.mkdir()
    (real_root / "stage_a").symlink_to(outside_stage, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink"):
        runner._revalidate_p2_job_storage(job)


@pytest.mark.parametrize("route", ["output", "status", "log", "stale", "failure"])
def test_p2_all_write_routes_reject_symlink_escape(tmp_path, monkeypatch, route):
    runner = _load_runner()
    root = tmp_path / "real"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    runner.P2_OUTPUT_ROOT = root
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    runner._bind_p2_execution_context(job, real_root=root)

    if route in {"output", "status"}:
        (root / "stage_a").symlink_to(outside, target_is_directory=True)
    elif route == "log":
        (root / "runner_logs").symlink_to(outside, target_is_directory=True)
    elif route == "stale":
        output = runner._output_dir(job)
        output.mkdir(parents=True)
        (output / "config_fingerprint.txt").write_text(
            runner._p2_config_fingerprint(job) + "\n", encoding="utf-8"
        )
        (root / "stale").symlink_to(outside, target_is_directory=True)
    else:
        (root / "failures").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink|escape"):
        if route == "output":
            runner._revalidate_p2_job_storage(job)
        elif route == "status":
            runner._p2_status_path("p2_adaptive_eds_rbf_stage_a", root)
        elif route == "log":
            runner._log_file_for_job(job)
        elif route == "stale":
            runner._archive_p2_job_artifacts(job)
        else:
            runner._write_p2_gpu_probe_failure(
                "p2_adaptive_eds_rbf_stage_a",
                "2",
                "probe failed",
                3,
                real_root=root,
            )


def test_p2_fingerprint_binds_command_cache_head_and_code_state(tmp_path, monkeypatch):
    runner = _load_runner()
    root = tmp_path / "real-root"
    monkeypatch.setattr(runner, "_git_head_revision", lambda: "a" * 40)
    monkeypatch.setattr(runner, "_p2_code_state_sha256", lambda: "b" * 64)
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    runner._bind_p2_execution_context(
        job,
        real_root=root,
        cached_functions_dir="/cache/one",
    )
    first = job["config_fingerprint"]
    record = job["execution_record"]
    assert record["cached_functions_dir"] == "/cache/one"
    assert record["git_revision"] == "a" * 40
    assert record["code_state_sha256"] == "b" * 64
    assert record["normalized_command"] == runner.build_main_command(
        job,
        gpu="2",
        timeout_seconds=1,
        cached_functions_dir="/cache/one",
    )

    runner._bind_p2_execution_context(
        job,
        real_root=root,
        cached_functions_dir="/cache/two",
    )
    assert job["config_fingerprint"] != first
    second = job["config_fingerprint"]
    monkeypatch.setattr(runner, "_git_head_revision", lambda: "c" * 40)
    runner._bind_p2_execution_context(job, real_root=root, cached_functions_dir="/cache/two")
    assert job["config_fingerprint"] != second
    third = job["config_fingerprint"]
    monkeypatch.setattr(runner, "_p2_code_state_sha256", lambda: "d" * 64)
    runner._bind_p2_execution_context(job, real_root=root, cached_functions_dir="/cache/two")
    assert job["config_fingerprint"] != third


@pytest.mark.parametrize(
    "relative",
    [
        "configs/config.yaml",
        "core/gemini_grounder.py",
        "core/keypoint_detector.py",
        "core/rdt_libero_obs_processor.py",
        "main.py",
        "utils/helper.py",
        "backend/adapter.py",
        "policy/model.py",
        "scripts/rdt_eds_eval_runner.py",
    ],
)
def test_p2_code_state_hash_covers_full_inference_and_config_tree(tmp_path, relative):
    runner = _load_runner()
    paths = [
        "configs/config.yaml",
        "core/gemini_grounder.py",
        "core/keypoint_detector.py",
        "core/rdt_libero_obs_processor.py",
        "main.py",
        "utils/helper.py",
        "backend/adapter.py",
        "policy/model.py",
        "scripts/rdt_eds_eval_runner.py",
    ]
    for item in paths:
        path = tmp_path / item
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"content:{item}\n", encoding="utf-8")
    before = runner._p2_code_state_sha256(
        root=tmp_path,
        head_revision="a" * 40,
    )
    changed = tmp_path / relative
    changed.write_text(changed.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    after = runner._p2_code_state_sha256(
        root=tmp_path,
        head_revision="a" * 40,
    )
    assert after != before


def test_current_p2_storage_link_is_valid():
    runner = _load_runner()
    assert runner._validate_p2_output_storage() == runner.P2_EXPECTED_OUTPUT_TARGET.resolve()


def test_p2_command_is_exact_explicit_and_secret_free():
    runner = _load_runner()
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    cmd = runner.build_main_command(job, gpu="2", timeout_seconds=120)
    text = " ".join(cmd)
    expected = {
        "backend.libero.suite_name": "libero_object_swap",
        "backend.libero.strict_perturbations": "true",
        "backend.libero.max_episode_steps": "720",
        "main.episode_num": "10",
        "main.use_vlm_stage_recognition": "true",
        "perception.gemini_grounding.enabled": "false",
        "seed": "0",
        "main.use_guidance": "true",
        "main.guidance_type": "eds",
        "main.eds_config.population_size": "16",
        "main.eds_config.parent_weighting_mode": "legacy_temperature",
        "main.eds_config.rollout_diversity_control_mode": "fixed",
        "main.eds_config.parent_coverage_mode": "none",
        "main.eds_config.chunk_population_mode": "fresh",
        "main.eds_config.search_schedule_mode": "legacy_linear",
        "main.execution_horizon_mode": "fixed",
        "main.eds_mechanism_pretest.enabled": "true",
        "main.eds_mechanism_pretest.output_mode": "qualitative_chunk",
    }
    for key, value in expected.items():
        assert f"{key}={value}" in cmd
    assert not any("task_ids_filter" in part for part in cmd)
    assert "OPENAI_API_KEY" not in text
    assert "sk-poe-" not in text


def test_p2_pretest_command_filters_tasks_0_8():
    runner = _load_runner()
    job = runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)[0]
    cmd = runner.build_main_command(job, gpu="2", timeout_seconds=120)
    assert "backend.libero.task_ids_filter=[0,8]" in cmd
    assert "main.episode_num=2" in cmd


@pytest.mark.parametrize(
    "label,expected_field",
    [
        ("p2_sel_ess05", "selection_ess_ratio_mean"),
        ("p2_adaptrbf_t10_s20", "adaptive_rbf_scale_requested_mean"),
        ("p2_divres_k4_e2", "anchor_count_observed"),
    ],
)
def test_p2_component_telemetry_accepts_real_chunk_metric_fields(
    label, expected_field
):
    runner = _load_runner()
    from core.eds_eval_metrics import EDSChunkMetrics

    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)
        if job["label"] == label
    )
    record = EDSChunkMetrics(
        selection_ess_ratio_mean=0.5,
        adaptive_rbf_scale_requested_mean=10.0,
        anchor_count_observed=4,
        elite_carryover_count_observed=2,
    ).to_jsonable()

    assert expected_field in record
    assert runner._p2_component_telemetry_failures(job, [record]) == []


@pytest.mark.parametrize(
    "label,legacy_field,legacy_value",
    [
        ("p2_sel_ess05", "selection_ess_ratio", 0.5),
        ("p2_adaptrbf_t10_s20", "adaptive_rbf_requested_scale", 10.0),
        ("p2_divres_k4_e2", "parent_anchor_count_observed", 4),
    ],
)
def test_p2_component_telemetry_keeps_legacy_aliases(
    label, legacy_field, legacy_value
):
    runner = _load_runner()
    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)
        if job["label"] == label
    )
    record = {
        legacy_field: legacy_value,
        "elite_carryover_count_observed": job["elite_carryover_count"],
    }

    assert runner._p2_component_telemetry_failures(job, [record]) == []


def test_p2_output_dirs_use_exact_stage_and_label(tmp_path):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    stage_a = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    pretest = runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)[0]
    assert runner._output_dir(stage_a) == runner.P2_OUTPUT_ROOT / "stage_a" / stage_a["label"]
    assert runner._output_dir(pretest) == runner.P2_OUTPUT_ROOT / "pretest" / pretest["label"]


def _write_test_png(path):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2, 2), color=(12, 34, 56)).save(path)


def _write_valid_p2_qualitative_chunk(
    job,
    chunk_root,
    *,
    episode=0,
    global_step=0,
    memory_trace_available=True,
):
    import torch

    from core.eds_mechanism_trace import (
        EDSMechanismTrace,
        EDSParticleStage,
        save_mechanism_trace,
    )

    source_counts = {
        "elite": int(job["elite_carryover_count"]),
        "anchor_offspring": int(job["parent_anchor_count"]),
        "weighted_offspring": (
            int(job["population_size"])
            - int(job["elite_carryover_count"])
            - int(job["parent_anchor_count"])
        ),
    }
    parent_sources = [
        source
        for source, count in source_counts.items()
        for _ in range(count)
    ]
    selection_info = {
        "enabled": (
            job["parent_weighting_mode"] == "adaptive_ess"
            or job["parent_coverage_mode"] == "eef_kcenter"
        ),
        "per_iter": [
            {
                "iter_idx": 0,
                "selection_beta": 1.0,
                "selection_ess_ratio": float(job["selection_ess_target_ratio"]),
                "selection_degenerate_reward": False,
                "parent_count_by_source": source_counts,
                "anchor_shortfall": 0,
                "anchor_fallback_reason": None,
                "parent_indices": list(range(int(job["population_size"]))),
                "parent_sources": parent_sources,
                "parent_selection_kinds": [
                    "deterministic_elite"
                    if source == "elite"
                    else "deterministic_anchor"
                    if source == "anchor_offspring"
                    else str(job["parent_weighting_mode"])
                    for source in parent_sources
                ],
            }
        ],
    }
    stages = [
        EDSParticleStage(
            stage="initial",
            iter_idx=0,
            actions=torch.zeros(1, 64, 128),
            trajectories=torch.zeros(1, 64, 3),
            rewards=torch.zeros(1),
            costs=torch.zeros(1),
        )
    ]
    memory_trace_generated = (
        job["chunk_population_mode"] == "warm_start_mix"
        and memory_trace_available
    )
    if memory_trace_generated:
        for stage_name in (
            "memory_fresh_initial",
            "memory_adapted_candidates",
            "memory_composed_initial",
        ):
            stages.append(
                EDSParticleStage(
                    stage=stage_name,
                    iter_idx=0,
                    actions=torch.zeros(1, 64, 128),
                    trajectories=torch.zeros(1, 64, 3),
                    rewards=torch.zeros(1),
                    costs=torch.zeros(1),
                )
            )
    trace = EDSMechanismTrace(
        suite="libero_object_swap",
        task_id=0,
        episode=episode,
        global_step=global_step,
        reward_mode="normal",
        population_size=int(job["population_size"]),
        cem_iters=int(job["cem_iters"]),
        use_cem=bool(job["use_cem"]),
        keypoints=None,
        stages=stages,
        selection_info=selection_info,
        adaptive_rollout_info={
            "per_iter": [
                {
                    "adaptive_rbf_scale_requested": 10.0,
                    "adaptive_rbf_scale_applied": 10.0,
                    "adaptive_rbf_active_particle_count": 16,
                }
            ]
        },
        chunk_memory_info={
            "enabled": memory_trace_generated,
            "chunk_memory_available": memory_trace_generated,
            "chunk_memory_used": memory_trace_generated,
            "chunk_memory_candidate_count": 4 if memory_trace_generated else 0,
            "chunk_memory_reset_reason": (
                None if memory_trace_generated else "stage_change"
            ),
        },
        search_schedule_info={"per_iter": [{"n_trunc_steps": 1}]},
        execution_info={"execution_horizon_resolved": 4},
    )
    save_mechanism_trace(chunk_root, trace, save_tensors=True)
    _write_test_png(chunk_root / "full_eds_process" / "reward_curve.png")

    if selection_info["enabled"]:
        selection = chunk_root / "selection"
        _write_test_png(selection / "parent_source_trajectories_3d.png")
        (selection / "parent_rank_and_probability.csv").write_text(
            "iter_idx,parent_id,parent_probability\n0,0,0.5\n",
            encoding="utf-8",
        )
        (selection / "elite_anchor_survival.json").write_text(
            json.dumps({"elite": source_counts["elite"]}) + "\n",
            encoding="utf-8",
        )

    if memory_trace_generated:
        memory = chunk_root / "memory"
        _write_test_png(memory / "fresh_vs_memory_trajectories_3d.png")
        (memory / "memory_acceptance.json").write_text(
            json.dumps({"available": True, "used": True}) + "\n",
            encoding="utf-8",
        )

    if (
        job["rollout_diversity_control_mode"] == "adaptive_band"
        or job["search_schedule_mode"] == "adaptive"
    ):
        schedule = chunk_root / "schedule"
        schedule.mkdir(parents=True, exist_ok=True)
        (schedule / "adaptive_decisions.json").write_text(
            json.dumps({"adaptive": True}) + "\n",
            encoding="utf-8",
        )
        _write_test_png(schedule / "reward_diversity_schedule.png")


def _write_valid_p2_job(
    runner,
    job,
    *,
    ffprobe_ok=True,
    success_count=None,
    memory_available_episodes=None,
):
    output_dir = runner._output_dir(job)
    output_dir.mkdir(parents=True)
    runner._write_p2_job_identity(job)
    metrics_dir = output_dir / "eds_eval"
    hydra_dir = output_dir / ".hydra"
    hydra_dir.mkdir()
    metrics_dir.mkdir(parents=True)
    successes = min(5, job["episodes"]) if success_count is None else int(success_count)
    (output_dir / "results.txt").write_text(
        f"Success count: {successes}/{job['episodes']}\n"
        f"Success rate: {100 * successes / job['episodes']:.2f}%\n",
        encoding="utf-8",
    )
    command_overrides = [
        part
        for part in runner.build_main_command(job, gpu="2", timeout_seconds=120)
        if "=" in part and not part.startswith("hydra.run.dir=")
    ]
    (hydra_dir / "overrides.yaml").write_text(
        yaml.safe_dump(command_overrides, sort_keys=False), encoding="utf-8"
    )
    config = {}
    for override in command_overrides:
        key, raw_value = override.split("=", 1)
        if key in {"backend", "hydra.run.dir"}:
            continue
        cursor = config
        parts = key.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = yaml.safe_load(raw_value)
    (hydra_dir / "config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    (hydra_dir / "hydra.yaml").write_text(
        yaml.safe_dump(
            {
                "hydra": {
                    "run": {"dir": str(output_dir)},
                    "runtime": {"output_dir": str(output_dir)},
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    records = []
    for episode in range(job["episodes"]):
        ep_dir = output_dir / f"episode_{episode + 1}"
        ep_dir.mkdir()
        outcome = "success" if episode < successes else "fail"
        (ep_dir / f"episode_{outcome}_video.mp4").write_bytes(
            b"readable" if ffprobe_ok else b"bad"
        )
        qualitative = metrics_dir / "qualitative" / f"episode_{episode:03d}" / "chunk_000000"
        memory_available = (
            job["chunk_population_mode"] == "warm_start_mix"
            and (
                memory_available_episodes is None
                or episode in memory_available_episodes
            )
        )
        _write_valid_p2_qualitative_chunk(
            job,
            qualitative,
            episode=episode,
            global_step=0,
            memory_trace_available=memory_available,
        )
        records.append(
            {
                "episode": episode,
                "global_step": 0,
                "chunk_id": 0,
                "initial_diversity_fallback_used": False,
                "rollout_diversity_fallback_used": False,
                "adaptive_rbf_fallback_used": False,
                "chunk_memory_fallback_used": False,
                "nonfinite_count": 0,
                "action_mask_violation_max": 0.0,
                "select_action_latency_s": 1.0,
                "parent_weighting_mode": job["parent_weighting_mode"],
                "selection_ess_ratio_mean": job["selection_ess_target_ratio"],
                "rollout_diversity_control_mode": job["rollout_diversity_control_mode"],
                "adaptive_rbf_scale_requested_mean": 1.0,
                "adaptive_rbf_scale_applied_mean": 1.0,
                "adaptive_rbf_active_iter_count": 1,
                "parent_coverage_mode": job["parent_coverage_mode"],
                "anchor_count_observed": job["parent_anchor_count"],
                "elite_carryover_count_observed": job["elite_carryover_count"],
                "chunk_population_mode": job["chunk_population_mode"],
                "chunk_memory_available": memory_available,
                "chunk_memory_used": memory_available,
                "chunk_memory_candidate_count": 4 if memory_available else 0,
                "chunk_memory_fraction_observed": 0.25 if memory_available else 0.0,
                "chunk_memory_acceptance_ratio": 1.0 if memory_available else None,
                "chunk_memory_source_counts": (
                    {"fresh": 12, "memory": 4}
                    if memory_available
                    else {"fresh": 16, "memory": 0}
                ),
                "chunk_memory_reset_reason": (
                    None if memory_available else "stage_change"
                ),
                "selected_chunk_population_source": (
                    "memory" if memory_available else "fresh"
                ),
                "search_schedule_mode": job["search_schedule_mode"],
                "execution_horizon_mode": job["execution_horizon_mode"],
                "execution_horizon_resolved": job["execution_horizon_far"],
                "per_iter": [
                    {
                        "selection_ess_ratio": job["selection_ess_target_ratio"],
                        "selection_beta": 1.0,
                        "selection_degenerate_reward": False,
                        "adaptive_rbf_scale_requested": 1.0,
                        "adaptive_rbf_scale_applied": 1.0,
                        "adaptive_rbf_active_particle_count": 16,
                        "n_trunc_steps": job["renoise_t_min"],
                    }
                ],
            }
        )
    (metrics_dir / "eds_metrics.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    task_ids = job.get("task_ids_filter") or list(range(job["episodes"]))
    metadata = [
        {
            "episode_id": episode,
            "episode_seed": episode,
            "task_id": int(task_ids[episode]),
        }
        for episode in range(job["episodes"])
    ]
    (metrics_dir / "episode_metadata.jsonl").write_text(
        "\n".join(json.dumps(record) for record in metadata) + "\n",
        encoding="utf-8",
    )
    events = [
        {
            "episode_id": episode,
            "task_id": int(task_ids[episode]),
            "episode_seed": episode,
            "global_step": 0,
            "chunk_id": 0,
            "trigger_reason": "initial",
            "stage_before": None,
            "stage_after": "grasp",
            "guidance_before": True,
            "guidance_after": True,
            "parsed_stage": "grasp",
            "parsed_guidance": True,
            "query_latency_s": 0.1,
            "query_status": "ok",
            "query_ok": True,
        }
        for episode in range(job["episodes"])
    ]
    (metrics_dir / "stage_events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    runner._log_file_for_job(job).parent.mkdir(parents=True, exist_ok=True)
    runner._log_file_for_job(job).write_text("strict LIBERO-PRO loaded\n", encoding="utf-8")
    return output_dir


def test_p2_strict_validity_accepts_complete_job(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    assert runner._job_validity(job)["valid"] is True
    assert runner._job_has_complete_outputs(job) is True


def test_p2_strict_validity_rejects_missing_runner_log(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)[0]
    _write_valid_p2_job(runner, job)
    runner._log_file_for_job(job).unlink()
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "runner log missing" in validity["failure_reason"]


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "missing_one",
        "wrong_value",
        "duplicate_same",
        "duplicate_conflict",
        "extra",
    ],
)
def test_p2_resume_rejects_invalid_overrides_file(tmp_path, monkeypatch, mutation):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    overrides = output_dir / ".hydra" / "overrides.yaml"
    values = yaml.safe_load(overrides.read_text(encoding="utf-8"))
    if mutation == "empty":
        overrides.write_text("", encoding="utf-8")
    elif mutation == "missing_one":
        overrides.write_text(
            yaml.safe_dump(
                [
                    value
                    for value in values
                    if not value.startswith("main.eds_config.parent_weighting_mode=")
                ],
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    elif mutation == "wrong_value":
        overrides.write_text(
            yaml.safe_dump(
                [
                    value.replace(
                    "main.eds_config.parent_weighting_mode=legacy_temperature",
                    "main.eds_config.parent_weighting_mode=adaptive_ess",
                )
                    for value in values
                ],
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    elif mutation == "duplicate_same":
        values.append("main.eds_config.parent_weighting_mode=legacy_temperature")
        overrides.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
    elif mutation == "duplicate_conflict":
        values.append("main.eds_config.parent_weighting_mode=adaptive_ess")
        overrides.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
    else:
        values.append("main.unapproved_debug_mode=true")
        overrides.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
    validity = runner._job_validity(job)
    assert validity["valid"] is False
    assert "overrides" in validity["failure_reason"]
    assert runner._job_has_complete_outputs(job) is False


@pytest.mark.parametrize(
    "mutation",
    ["wrong_algorithm", "wrong_benchmark", "wrong_cache", "nonmapping", "duplicate_key"],
)
def test_p2_resume_rejects_structured_config_mismatch(tmp_path, monkeypatch, mutation):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    config_path = output_dir / ".hydra" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if mutation == "wrong_algorithm":
        config["main"]["eds_config"]["population_size"] = 99
    elif mutation == "wrong_benchmark":
        config["backend"]["libero"]["strict_perturbations"] = False
    elif mutation == "wrong_cache":
        config["main"]["cached_functions_dir"] = "/tmp/stale-cache"
    elif mutation == "nonmapping":
        config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    else:
        config_path.write_text(
            "main:\n  use_guidance: true\n  use_guidance: false\n",
            encoding="utf-8",
        )
    if mutation not in {"nonmapping", "duplicate_key"}:
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    validity = runner._job_validity(job)
    assert validity["valid"] is False
    assert "config.yaml" in validity["failure_reason"]
    assert runner._job_has_complete_outputs(job) is False


def test_p2_pretest_validity_accepts_exact_task_multiset_0_8(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)[0]
    _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    assert runner._job_validity(job)["valid"] is True


@pytest.mark.parametrize(
    "label",
    [
        "p2_legacy_stage_on_rerun",
        "p2_sel_ess05",
        "p2_adaptrbf_t10_s20",
        "p2_divres_k4_e2",
        "p2_memory25",
        "p2_schedule_contact",
    ],
)
def test_p2_pretest_accepts_recursive_profile_specific_artifacts(
    tmp_path, monkeypatch, label
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)
        if job["label"] == label
    )
    _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)

    validity = runner._job_validity(job)

    assert validity["valid"] is True, validity["failure_reason"]


def test_p2_pretest_memory_artifacts_only_required_for_available_traced_chunks(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)
        if job["label"] == "p2_memory25"
    )
    output_dir = _write_valid_p2_job(
        runner,
        job,
        memory_available_episodes={0},
    )
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)

    unavailable_episode = output_dir / "eds_eval" / "qualitative" / "episode_001"
    assert not list(unavailable_episode.rglob("memory_acceptance.json"))
    validity = runner._job_validity(job)

    assert validity["valid"] is True, validity["failure_reason"]


def test_p2_pretest_memory_metrics_require_matching_trace_and_artifacts(
    tmp_path, monkeypatch
):
    import torch

    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)
        if job["label"] == "p2_memory25"
    )
    output_dir = _write_valid_p2_job(
        runner,
        job,
        memory_available_episodes={0},
    )
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    episode_root = output_dir / "eds_eval" / "qualitative" / "episode_000"
    trace_path = next(episode_root.rglob("mechanism_trace.pt"))
    payload = torch.load(trace_path, map_location="cpu", weights_only=True)
    payload["metadata"]["chunk_memory_info"] = {}
    payload["chunk_memory_info"] = {}
    torch.save(payload, trace_path)
    for path in list((episode_root / "chunk_000000" / "memory").rglob("*")):
        if path.is_file():
            path.unlink()

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "memory trace" in validity["failure_reason"]
    assert "memory/memory_acceptance.json" in validity["failure_reason"]


def test_p2_pretest_memory_allows_untraced_metrics_after_first_eligible_chunk(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)
        if job["label"] == "p2_memory25"
    )
    output_dir = _write_valid_p2_job(
        runner,
        job,
        memory_available_episodes={0},
    )
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    later_untraced = dict(
        next(
            record
            for record in records
            if record["episode"] == 0
            and record.get("chunk_memory_available") is True
        )
    )
    later_untraced.update({"global_step": 16, "chunk_id": 2})
    records.append(later_untraced)
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is True, validity["failure_reason"]


@pytest.mark.parametrize(
    "label,artifact_suffix",
    [
        ("p2_legacy_stage_on_rerun", "first_chunk_metadata.json"),
        (
            "p2_sel_ess05",
            "selection/parent_source_trajectories_3d.png",
        ),
        ("p2_adaptrbf_t10_s20", "schedule/adaptive_decisions.json"),
        ("p2_divres_k4_e2", "selection/elite_anchor_survival.json"),
        ("p2_memory25", "memory/memory_acceptance.json"),
        (
            "p2_schedule_contact",
            "schedule/reward_diversity_schedule.png",
        ),
    ],
)
def test_p2_pretest_rejects_missing_profile_specific_artifact(
    tmp_path, monkeypatch, label, artifact_suffix
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)
        if job["label"] == label
    )
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    episode_root = output_dir / "eds_eval" / "qualitative" / "episode_000"
    target = next(
        path
        for path in episode_root.rglob(Path(artifact_suffix).name)
        if path.relative_to(episode_root).as_posix().endswith(artifact_suffix)
    )
    target.unlink()

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert artifact_suffix in validity["failure_reason"]


@pytest.mark.parametrize(
    "artifact_suffix,corrupt_content",
    [
        ("first_chunk_metadata.json", b"{"),
        (
            "single_step_inner_loop/single_step_particles.csv",
            b"stage,iter_idx\n",
        ),
        ("full_eds_process/reward_curve.png", b"not-a-png"),
        ("tensors/mechanism_trace.pt", b"not-a-safe-trace"),
    ],
)
def test_p2_pretest_type_reads_required_json_csv_png_and_pt(
    tmp_path, monkeypatch, artifact_suffix, corrupt_content
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    episode_root = output_dir / "eds_eval" / "qualitative" / "episode_000"
    target = next(
        path
        for path in episode_root.rglob(Path(artifact_suffix).name)
        if path.relative_to(episode_root).as_posix().endswith(artifact_suffix)
    )
    target.write_bytes(corrupt_content)

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert artifact_suffix in validity["failure_reason"]


def _write_p2_pretest_report_fixture(runner):
    jobs = runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)
    for job_index, job in enumerate(jobs):
        output_dir = _write_valid_p2_job(
            runner,
            job,
            success_count=job_index % 3,
            memory_available_episodes=(
                set() if job["label"] == "p2_memory25" else None
            ),
        )
        metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
        records = runner._read_jsonl(metrics_path)
        label = job["label"]
        if label == "p2_sel_ess05":
            for record, ratio in zip(records, (0.45, 0.55)):
                record["selection_ess_ratio_mean"] = ratio
                record["per_iter"][0]["selection_ess_ratio"] = ratio
        elif label == "p2_adaptrbf_t10_s20":
            for record, scale in zip(records, (5.0, 10.0)):
                record["adaptive_rbf_active_iter_count"] = 1
                record["adaptive_rbf_scale_requested_mean"] = scale
                record["adaptive_rbf_scale_applied_mean"] = scale
                record["per_iter"][0]["adaptive_rbf_scale_requested"] = scale
                record["per_iter"][0]["adaptive_rbf_scale_applied"] = scale
                record["per_iter"][0]["adaptive_rbf_active_particle_count"] = 16
        elif label == "p2_memory25":
            expanded = []
            for record in records:
                _write_valid_p2_qualitative_chunk(
                    job,
                    output_dir
                    / "eds_eval"
                    / "qualitative"
                    / f"episode_{record['episode']:03d}"
                    / "chunk_000001",
                    episode=int(record["episode"]),
                    global_step=8,
                    memory_trace_available=True,
                )
                first = dict(record)
                first.update(
                    {
                        "global_step": 0,
                        "chunk_id": 0,
                        "chunk_memory_available": False,
                        "chunk_memory_used": False,
                        "chunk_memory_candidate_count": 0,
                        "chunk_memory_fraction_observed": 0.0,
                        "chunk_memory_acceptance_ratio": None,
                        "chunk_memory_source_counts": {"fresh": 16, "memory": 0},
                        "chunk_memory_reset_reason": None,
                        "selected_chunk_population_source": "fresh",
                    }
                )
                used = dict(record)
                used.update(
                    {
                        "global_step": 8,
                        "chunk_id": 1,
                        "chunk_memory_available": True,
                        "chunk_memory_used": True,
                        "chunk_memory_candidate_count": 4,
                        "chunk_memory_source_counts": {"fresh": 12, "memory": 4},
                        "chunk_memory_fraction_observed": 0.25,
                        "chunk_memory_acceptance_ratio": 1.0,
                        "chunk_memory_reset_reason": None,
                        "selected_chunk_population_source": "memory",
                    }
                )
                reset = dict(record)
                reset.update(
                    {
                        "global_step": 16,
                        "chunk_id": 2,
                        "chunk_memory_available": False,
                        "chunk_memory_used": False,
                        "chunk_memory_candidate_count": 0,
                        "chunk_memory_fraction_observed": 0.0,
                        "chunk_memory_acceptance_ratio": None,
                        "chunk_memory_source_counts": {"fresh": 16, "memory": 0},
                        "chunk_memory_reset_reason": "stage_change",
                        "selected_chunk_population_source": "fresh",
                    }
                )
                expanded.extend((first, used, reset))
            records = expanded
            events_path = output_dir / "eds_eval" / "stage_events.jsonl"
            events = runner._read_jsonl(events_path)
            for event in events:
                event.update(
                    {
                        "global_step": 16,
                        "stage_before": "grasp",
                        "stage_after": "transport",
                        "parsed_stage": "transport",
                    }
                )
            events_path.write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )
        elif label == "p2_schedule_contact":
            for record, (renoise, horizon) in zip(records, ((1, 2), (3, 8))):
                record["execution_horizon_resolved"] = horizon
                record["eds_iters_executed"] = 10
                record["per_iter"][0]["n_trunc_steps"] = renoise
            records[0]["early_stop_used"] = True
            records[0]["early_stop_reason"] = "adaptive_plateau_stable_in_band"
        metrics_path.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
    return jobs


def test_p2_pretest_report_aggregates_six_jobs_and_five_mechanism_gates(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "evidence" / (
        "2026-08-02-p2-adaptive-eds-rbf-pretest-report.md"
    )
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    monkeypatch.setenv("OPENAI_API_KEY", "runtime-report-secret-value")
    jobs = _write_p2_pretest_report_fixture(runner)

    report = runner.write_p2_adaptive_eds_rbf_pretest_report()
    text = report.read_text(encoding="utf-8")

    assert report == runner.P2_PRETEST_REPORT_PATH
    assert report.name == "2026-08-02-p2-adaptive-eds-rbf-pretest-report.md"
    assert all(job["label"] in text for job in jobs)
    for gate in (
        "Adaptive ESS",
        "Adaptive rollout RBF",
        "k-center + elite carryover",
        "Cross-chunk population memory",
        "Adaptive search / execution schedule",
    ):
        assert gate in text
    assert text.count("| PASS |") >= 5
    assert "PASS / FAIL / INCONCLUSIVE" in text
    assert "sample" in text.lower()
    assert "SR is descriptive only and is not used to eliminate profiles" in text
    assert "equal_reward_iterations=0" in text
    assert "degenerate_iterations=0" in text
    assert "degenerate_chunks=0" in text
    assert "unreachable_target_iterations=0" in text
    assert "anchor_shortfall_iterations=0" in text
    assert "anchor_reasons=none" in text
    assert "early_stop_chunks=1" in text
    assert "adaptive_plateau_stable_in_band:1" in text
    for column in ("Validity", "Artifact", "Strict", "Stage", "Safety", "Failure"):
        assert column in text
    assert "runtime-report-secret-value" not in text


def test_p2_pretest_rbf_gate_ignores_inactive_iteration_scales(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    rbf_job = next(job for job in jobs if job["label"] == "p2_adaptrbf_t10_s20")
    metrics_path = runner._output_dir(rbf_job) / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    for record, (scale, active_particles) in zip(records, ((5.0, 0), (20.0, 16))):
        record["adaptive_rbf_active_iter_count"] = int(active_particles > 0)
        record["per_iter"][0]["adaptive_rbf_scale_applied"] = scale
        record["per_iter"][0]["adaptive_rbf_scale_requested"] = scale
        record["per_iter"][0]["adaptive_rbf_active_particle_count"] = active_particles
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    rbf_row = next(
        line for line in text.splitlines() if line.startswith("| Adaptive rollout RBF ")
    )

    assert "| FAIL |" in rbf_row
    assert "unique_active_applied=[20.0]" in rbf_row
    assert "inactive_iterations=1" in rbf_row


def test_p2_pretest_rbf_gate_is_inconclusive_without_per_iter_activity(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    rbf_job = next(job for job in jobs if job["label"] == "p2_adaptrbf_t10_s20")
    metrics_path = runner._output_dir(rbf_job) / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    for record in records:
        record["per_iter"][0].pop("adaptive_rbf_active_particle_count")
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    rbf_row = next(
        line for line in text.splitlines() if line.startswith("| Adaptive rollout RBF ")
    )

    assert "| INCONCLUSIVE |" in rbf_row
    assert "per-iteration active particle telemetry missing" in rbf_row


def test_p2_pretest_rbf_gate_rejects_chunk_activity_contradiction(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    rbf_job = next(job for job in jobs if job["label"] == "p2_adaptrbf_t10_s20")
    metrics_path = runner._output_dir(rbf_job) / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    for record in records:
        record["adaptive_rbf_active_iter_count"] = 0
        assert record["per_iter"][0]["adaptive_rbf_active_particle_count"] > 0
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    rbf_row = next(
        line for line in text.splitlines() if line.startswith("| Adaptive rollout RBF ")
    )

    assert "| FAIL |" in rbf_row
    assert "chunk_active_iterations=0" in rbf_row
    assert "per-iter/chunk activity contradiction" in rbf_row


def test_p2_pretest_kcenter_gate_rejects_explicit_anchor_shortfall(
    tmp_path, monkeypatch
):
    import torch

    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    coverage_job = next(job for job in jobs if job["label"] == "p2_divres_k4_e2")
    trace_path = next(
        (
            runner._output_dir(coverage_job) / "eds_eval" / "qualitative"
        ).rglob("mechanism_trace.pt")
    )
    payload = torch.load(trace_path, map_location="cpu", weights_only=True)
    selection_iter = payload["metadata"]["selection_info"]["per_iter"][0]
    selection_iter["anchor_shortfall"] = 1
    selection_iter["anchor_fallback_reason"] = "eligible_parent_shortfall"
    payload["selection_info"] = payload["metadata"]["selection_info"]
    torch.save(payload, trace_path)

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    coverage_row = next(
        line for line in text.splitlines() if line.startswith("| k-center + elite carryover ")
    )

    assert "| FAIL |" in coverage_row
    assert "anchor_shortfall_iterations=1" in coverage_row
    assert "eligible_parent_shortfall:1" in coverage_row


@pytest.mark.parametrize("bad_parent_id", [[0], "parent-zero", True])
def test_p2_kcenter_trace_rejects_non_integer_parent_ids(
    tmp_path, monkeypatch, bad_parent_id
):
    import torch

    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    coverage_job = next(job for job in jobs if job["label"] == "p2_divres_k4_e2")
    trace_path = next(
        (runner._output_dir(coverage_job) / "eds_eval" / "qualitative").rglob(
            "mechanism_trace.pt"
        )
    )
    payload = torch.load(trace_path, map_location="cpu", weights_only=True)
    selection_iter = payload["metadata"]["selection_info"]["per_iter"][0]
    selection_iter["parent_indices"][0] = bad_parent_id
    payload["selection_info"] = payload["metadata"]["selection_info"]
    torch.save(payload, trace_path)

    validity = runner._job_validity(coverage_job)
    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    coverage_row = next(
        line
        for line in text.splitlines()
        if line.startswith("| k-center + elite carryover ")
    )

    assert validity["valid"] is False
    assert "parent_indices" in validity["failure_reason"]
    assert "| PASS |" not in coverage_row


def test_p2_pretest_report_rejects_malformed_component_telemetry(
    tmp_path, monkeypatch
):
    import torch

    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)

    ess_job = next(job for job in jobs if job["label"] == "p2_sel_ess05")
    ess_metrics_path = runner._output_dir(ess_job) / "eds_eval" / "eds_metrics.jsonl"
    ess_records = runner._read_jsonl(ess_metrics_path)
    ess_records[0]["selection_degenerate_reward_count"] = float("nan")
    ess_metrics_path.write_text(
        "\n".join(json.dumps(record) for record in ess_records) + "\n",
        encoding="utf-8",
    )

    coverage_job = next(job for job in jobs if job["label"] == "p2_divres_k4_e2")
    trace_path = next(
        (runner._output_dir(coverage_job) / "eds_eval" / "qualitative").rglob(
            "mechanism_trace.pt"
        )
    )
    payload = torch.load(trace_path, map_location="cpu", weights_only=True)
    payload["metadata"]["selection_info"]["per_iter"][0][
        "parent_count_by_source"
    ]["anchor_offspring"] = "invalid"
    payload["selection_info"] = payload["metadata"]["selection_info"]
    torch.save(payload, trace_path)

    report = runner.write_p2_adaptive_eds_rbf_pretest_report()
    text = report.read_text(encoding="utf-8")
    ess_row = next(line for line in text.splitlines() if line.startswith("| Adaptive ESS "))
    coverage_row = next(
        line
        for line in text.splitlines()
        if line.startswith("| k-center + elite carryover ")
    )
    assert "| PASS |" not in ess_row
    assert "| PASS |" not in coverage_row


def test_p2_validity_rejects_malformed_component_telemetry(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)
        if job["label"] == "p2_divres_k4_e2"
    )
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    records[0]["anchor_count_observed"] = "invalid"
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "coverage telemetry invalid" in validity["failure_reason"]


@pytest.mark.parametrize(
    "label,mutation,expected_failure",
    [
        (
            "p2_sel_ess05",
            "scalar_per_iter",
            "per_iter telemetry invalid",
        ),
        (
            "p2_adaptrbf_t10_s20",
            "bool_applied_scale",
            "adaptive RBF telemetry invalid",
        ),
        (
            "p2_memory25",
            "string_candidate_count",
            "chunk memory telemetry invalid",
        ),
        (
            "p2_schedule_contact",
            "infinite_execution_horizon",
            "adaptive execution telemetry invalid",
        ),
    ],
)
def test_p2_validity_rejects_malformed_component_schema(
    tmp_path, monkeypatch, label, mutation, expected_failure
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)
        if job["label"] == label
    )
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    if mutation == "scalar_per_iter":
        records[0]["per_iter"] = float("nan")
    elif mutation == "bool_applied_scale":
        records[0]["adaptive_rbf_scale_applied_mean"] = True
    elif mutation == "string_candidate_count":
        records[0]["chunk_memory_candidate_count"] = "four"
    elif mutation == "infinite_execution_horizon":
        records[0]["execution_horizon_resolved"] = float("inf")
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert expected_failure in validity["failure_reason"]


def test_p2_pretest_report_handles_scalar_per_iter_and_infinite_schedule(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    ess_job = next(job for job in jobs if job["label"] == "p2_sel_ess05")
    ess_path = runner._output_dir(ess_job) / "eds_eval" / "eds_metrics.jsonl"
    ess_records = runner._read_jsonl(ess_path)
    ess_records[0]["per_iter"] = True
    ess_path.write_text(
        "\n".join(json.dumps(record) for record in ess_records) + "\n",
        encoding="utf-8",
    )
    schedule_job = next(job for job in jobs if job["label"] == "p2_schedule_contact")
    schedule_path = runner._output_dir(schedule_job) / "eds_eval" / "eds_metrics.jsonl"
    schedule_records = runner._read_jsonl(schedule_path)
    schedule_records[0]["execution_horizon_resolved"] = float("inf")
    schedule_path.write_text(
        "\n".join(json.dumps(record) for record in schedule_records) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )

    ess_row = next(line for line in text.splitlines() if line.startswith("| Adaptive ESS "))
    schedule_row = next(
        line
        for line in text.splitlines()
        if line.startswith("| Adaptive search / execution schedule ")
    )
    assert "| PASS |" not in ess_row
    assert "| PASS |" not in schedule_row


@pytest.mark.parametrize(
    "mutation",
    [
        "bool_success",
        "malformed_outcomes",
        "bool_rbf_scale",
        "malformed_schedule",
    ],
)
def test_p2_stage_b_eligibility_fails_closed_on_malformed_evidence(mutation):
    runner = _load_runner()
    baseline = {
        "valid": True,
        "success_count": 3,
        "median_latency_s": 1.0,
        "outcomes": {task: "fail" for task in range(10)},
        "metrics": [],
        "job": {},
    }
    source = {
        "valid": True,
        "success_count": 3,
        "median_latency_s": 1.0,
        "outcomes": {task: "fail" for task in range(10)},
        "metrics": [
            {
                "adaptive_rbf_scale_applied_mean": 5.0,
                "per_iter": [{"n_trunc_steps": 1}],
                "execution_horizon_resolved": 2,
            },
            {
                "adaptive_rbf_scale_applied_mean": 10.0,
                "per_iter": [{"n_trunc_steps": 3}],
                "execution_horizon_resolved": 8,
            },
        ],
        "job": {"selection_ess_target_ratio": 0.5},
    }
    label = "p2_adaptrbf_t10_s20"
    if mutation == "bool_success":
        source["success_count"] = True
    elif mutation == "malformed_outcomes":
        source["outcomes"] = "not-a-mapping"
    elif mutation == "bool_rbf_scale":
        source["metrics"][0]["adaptive_rbf_scale_applied_mean"] = True
        source["metrics"][1]["adaptive_rbf_scale_applied_mean"] = False
    elif mutation == "malformed_schedule":
        label = "p2_schedule_contact"
        source["metrics"][0]["per_iter"] = "invalid"
        source["metrics"][0]["execution_horizon_resolved"] = float("nan")
        source["metrics"][1]["per_iter"] = True
        source["metrics"][1]["execution_horizon_resolved"] = "eight"

    assert runner._p2_source_is_actually_eligible(label, source, baseline) is False


@pytest.mark.parametrize(
    "mutation",
    ["higher_sr_malformed_evidence", "bool_latency"],
)
def test_p2_stage_b_eligibility_validates_common_schema_before_sr_branch(mutation):
    runner = _load_runner()
    baseline = {
        "valid": True,
        "success_count": 3,
        "median_latency_s": 1.0,
        "outcomes": {task: "fail" for task in range(10)},
        "metrics": [],
        "job": {},
    }
    source = {
        "valid": True,
        "success_count": 4 if mutation == "higher_sr_malformed_evidence" else 3,
        "median_latency_s": float("nan") if mutation == "higher_sr_malformed_evidence" else True,
        "outcomes": (
            "invalid"
            if mutation == "higher_sr_malformed_evidence"
            else {task: "fail" for task in range(10)}
        ),
        "metrics": (
            True
            if mutation == "higher_sr_malformed_evidence"
            else [
                {"adaptive_rbf_scale_applied_mean": 5.0},
                {"adaptive_rbf_scale_applied_mean": 10.0},
            ]
        ),
        "job": {},
    }

    assert (
        runner._p2_source_is_actually_eligible(
            "p2_adaptrbf_t10_s20", source, baseline
        )
        is False
    )


def test_p2_ess_requires_at_least_one_finite_ratio_for_validity_and_eligibility(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = next(
        job
        for job in runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)
        if job["label"] == "p2_sel_ess05"
    )
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    for record in records:
        record["selection_ess_ratio_mean"] = None
        for item in record["per_iter"]:
            item["selection_ess_ratio"] = None
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)
    source = {
        "valid": True,
        "success_count": 4,
        "median_latency_s": 1.0,
        "outcomes": {task: "fail" for task in range(10)},
        "metrics": records,
        "job": {"selection_ess_target_ratio": 0.5},
    }
    baseline = {
        "valid": True,
        "success_count": 3,
        "median_latency_s": 1.0,
        "outcomes": {task: "fail" for task in range(10)},
        "metrics": [],
        "job": {},
    }

    assert validity["valid"] is False
    assert "finite adaptive ESS ratio" in validity["failure_reason"]
    assert runner._p2_source_is_actually_eligible("p2_sel_ess05", source, baseline) is False


def test_p2_pretest_memory_gate_checks_first_eligible_chunk(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    memory_job = next(job for job in jobs if job["label"] == "p2_memory25")
    metrics_path = runner._output_dir(memory_job) / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    injected = []
    for episode in (0, 1):
        valid_used = next(
            record
            for record in records
            if record["episode"] == episode and record.get("chunk_memory_available") is True
        )
        invalid_first = dict(valid_used)
        invalid_first.update(
            {
                "global_step": 4,
                "chunk_id": 1,
                "chunk_memory_candidate_count": 3,
                "chunk_memory_fraction_observed": 3 / 16,
                "chunk_memory_source_counts": {"fresh": 13, "memory": 3},
            }
        )
        injected.append(invalid_first)
    records.extend(injected)
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    memory_row = next(
        line for line in text.splitlines() if line.startswith("| Cross-chunk population memory ")
    )

    assert "| FAIL |" in memory_row
    assert "first_eligible_valid=0/2" in memory_row


def test_p2_pretest_memory_gate_requires_use_in_each_episode(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    memory_job = next(job for job in jobs if job["label"] == "p2_memory25")
    metrics_path = runner._output_dir(memory_job) / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    episode_zero_used = next(
        record
        for record in records
        if record["episode"] == 0 and record.get("chunk_memory_available") is True
    )
    duplicate = dict(episode_zero_used)
    duplicate.update({"global_step": 9, "chunk_id": 2})
    for record in records:
        if record["episode"] == 1 and record.get("chunk_memory_available") is True:
            record.update(
                {
                    "chunk_memory_available": False,
                    "chunk_memory_used": False,
                    "chunk_memory_candidate_count": 0,
                    "chunk_memory_fraction_observed": 0.0,
                    "chunk_memory_acceptance_ratio": None,
                    "chunk_memory_source_counts": {"fresh": 16, "memory": 0},
                    "selected_chunk_population_source": "fresh",
                }
            )
    records.append(duplicate)
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    memory_row = next(
        line for line in text.splitlines() if line.startswith("| Cross-chunk population memory ")
    )

    assert "| FAIL |" in memory_row
    assert "episodes_with_valid_use=1/2" in memory_row


def test_p2_pretest_memory_gate_reports_missing_cross_evidence(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    memory_job = next(job for job in jobs if job["label"] == "p2_memory25")
    metrics_path = runner._output_dir(memory_job) / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    first_used = next(record for record in records if record.get("chunk_memory_used") is True)
    first_used["selected_chunk_population_source"] = None
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    memory_row = next(
        line for line in text.splitlines() if line.startswith("| Cross-chunk population memory ")
    )

    assert "| INCONCLUSIVE |" in memory_row
    assert "selected source evidence missing" in memory_row


def test_p2_pretest_ess_report_separates_degenerate_and_unreachable_counts(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    ess_job = next(job for job in jobs if job["label"] == "p2_sel_ess05")
    metrics_path = runner._output_dir(ess_job) / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    records[0]["selection_degenerate_reward_count"] = 2
    records[0]["per_iter"] = [
        {
            "selection_beta": 0.0,
            "selection_ess_ratio": 1.0,
            "selection_degenerate_reward": True,
        },
        {
            "selection_beta": 0.0,
            "selection_ess_ratio": 1.0,
            "selection_degenerate_reward": True,
        },
    ]
    records[1]["selection_degenerate_reward_count"] = 0
    records[1]["per_iter"][0].update(
        {
            "selection_beta": 100.0,
            "selection_ess_ratio": 0.8,
            "selection_degenerate_reward": False,
        }
    )
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    ess_row = next(line for line in text.splitlines() if line.startswith("| Adaptive ESS "))

    assert "equal_reward_iterations=2" in ess_row
    assert "degenerate_iterations=2" in ess_row
    assert "degenerate_chunks=1" in ess_row
    assert "unreachable_target_iterations=1" in ess_row


def test_p2_pretest_report_marks_unobserved_memory_reset_inconclusive(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    memory_job = next(job for job in jobs if job["label"] == "p2_memory25")
    events_path = runner._output_dir(memory_job) / "eds_eval" / "stage_events.jsonl"
    events = runner._read_jsonl(events_path)
    for event in events:
        event["stage_before"] = event["stage_after"]
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )

    memory_row = next(
        line for line in text.splitlines() if line.startswith("| Cross-chunk population memory ")
    )
    assert "| INCONCLUSIVE |" in memory_row
    assert "stage change not observed" in memory_row


def test_p2_pretest_memory_report_does_not_reuse_reset_metric(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    memory_job = next(job for job in jobs if job["label"] == "p2_memory25")
    events_path = runner._output_dir(memory_job) / "eds_eval" / "stage_events.jsonl"
    events = runner._read_jsonl(events_path)
    unmatched = dict(events[0])
    unmatched.update(
        {
            "global_step": 12,
            "chunk_id": 99,
            "stage_before": "approach",
            "stage_after": "grasp",
            "guidance_before": False,
            "guidance_after": True,
        }
    )
    events.append(unmatched)
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    memory_row = next(
        line for line in text.splitlines() if line.startswith("| Cross-chunk population memory ")
    )

    assert "| INCONCLUSIVE |" in memory_row
    assert "exact_resets=2/3" in memory_row
    assert "EDS-enabled reset metric missing" in memory_row


def test_p2_pretest_memory_report_marks_guidance_off_transition_not_applicable(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    memory_job = next(job for job in jobs if job["label"] == "p2_memory25")
    events_path = runner._output_dir(memory_job) / "eds_eval" / "stage_events.jsonl"
    events = runner._read_jsonl(events_path)
    guidance_off = dict(events[0])
    guidance_off.update(
        {
            "global_step": 12,
            "chunk_id": 99,
            "stage_before": "grasp",
            "stage_after": "transport",
            "guidance_before": True,
            "guidance_after": False,
        }
    )
    events.append(guidance_off)
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    memory_row = next(
        line for line in text.splitlines() if line.startswith("| Cross-chunk population memory ")
    )

    assert "| PASS |" in memory_row
    assert "exact_resets=2/2" in memory_row
    assert "guidance_off=1" in memory_row


def test_p2_validity_rejects_duplicate_metric_identity(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    duplicate = dict(records[0])
    records.append(duplicate)
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "duplicate metrics episode/global_step identity" in validity["failure_reason"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("episode", False),
        ("episode", 0.0),
        ("global_step", False),
        ("global_step", 0.0),
        ("episode", 10),
        ("global_step", 721),
    ],
)
def test_p2_validity_rejects_malformed_metric_identity(
    tmp_path, monkeypatch, field, value
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    records[0][field] = value
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "metrics record 0 identity" in validity["failure_reason"]


@pytest.mark.parametrize("payload", ["{not-json}", "null", "[]"])
def test_p2_validity_rejects_malformed_metrics_jsonl(
    tmp_path, monkeypatch, payload
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    metrics_path.write_text(
        metrics_path.read_text(encoding="utf-8") + payload + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "metrics JSONL line" in validity["failure_reason"]


@pytest.mark.parametrize(
    "payload",
    [
        '{"episode":' + "9" * 5000 + "}",
        "[" * 2000 + "0" + "]" * 2000,
    ],
)
def test_p2_validity_handles_json_decoder_limits(tmp_path, monkeypatch, payload):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    metrics_path.write_text(
        metrics_path.read_text(encoding="utf-8") + payload + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "metrics JSONL line" in validity["failure_reason"]


@pytest.mark.parametrize("record", [{}, {"note": "extra"}])
def test_p2_validity_rejects_metadata_object_without_schema(
    tmp_path, monkeypatch, record
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metadata_path = output_dir / "eds_eval" / "episode_metadata.jsonl"
    metadata_path.write_text(
        metadata_path.read_text(encoding="utf-8") + json.dumps(record) + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "episode metadata record 10 schema invalid" in validity["failure_reason"]


def test_p2_validity_rejects_duplicate_episode_metadata_identity(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metadata_path = output_dir / "eds_eval" / "episode_metadata.jsonl"
    records = runner._read_jsonl(metadata_path)
    metadata_path.write_text(
        "\n".join(json.dumps(record) for record in [*records, dict(records[0])])
        + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "duplicate episode metadata identity" in validity["failure_reason"]


@pytest.mark.parametrize("payload", ["[]", "null", '"x"'])
def test_p2_validity_rejects_non_object_job_manifest(
    tmp_path, monkeypatch, payload
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    (output_dir / "job_manifest.json").write_text(payload, encoding="utf-8")

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "job_manifest.json must be a JSON object" in validity["failure_reason"]


def test_p2_validity_rejects_duplicate_stage_event_identity(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    events_path = output_dir / "eds_eval" / "stage_events.jsonl"
    events = runner._read_jsonl(events_path)
    duplicate = dict(events[0])
    duplicate["guidance_after"] = not bool(events[0]["guidance_after"])
    events.append(duplicate)
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "duplicate stage query episode/global_step identity" in validity["failure_reason"]


def test_p2_pretest_memory_report_prioritizes_invalid_reset_over_missing(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_PRETEST_REPORT_PATH = tmp_path / "pretest.md"
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    jobs = _write_p2_pretest_report_fixture(runner)
    memory_job = next(job for job in jobs if job["label"] == "p2_memory25")
    output_dir = runner._output_dir(memory_job)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    invalid_reset = next(
        record
        for record in records
        if record["episode"] == 0 and record["global_step"] == 16
    )
    invalid_reset["chunk_memory_used"] = True
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    events_path = output_dir / "eds_eval" / "stage_events.jsonl"
    events = runner._read_jsonl(events_path)
    missing = dict(events[0])
    missing.update(
        {
            "global_step": 12,
            "chunk_id": 99,
            "stage_before": "approach",
            "stage_after": "grasp",
            "guidance_before": False,
            "guidance_after": True,
        }
    )
    events.append(missing)
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    text = runner.write_p2_adaptive_eds_rbf_pretest_report().read_text(
        encoding="utf-8"
    )
    memory_row = next(
        line for line in text.splitlines() if line.startswith("| Cross-chunk population memory ")
    )

    assert "| FAIL |" in memory_row
    assert "exact-step reset evidence is invalid" in memory_row


def test_write_report_cli_supports_p2_adaptive_pretest(monkeypatch, tmp_path):
    runner = _load_runner()
    expected = tmp_path / "pretest.md"
    called = []
    monkeypatch.setattr(
        runner,
        "write_p2_adaptive_eds_rbf_pretest_report",
        lambda: called.append(True) or expected,
        raising=False,
    )
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "rdt_eds_eval_runner.py",
            "write-report",
            "--level",
            "p2_adaptive_eds_rbf_pretest",
            "--verdict",
            "inconclusive",
        ],
    )

    assert runner.main() == 0
    assert called == [True]


@pytest.mark.parametrize(
    "task_ids",
    [
        [0],
        [0, 0],
        [0, 7],
    ],
)
def test_p2_pretest_rejects_missing_duplicate_or_wrong_task_multiset(
    tmp_path, monkeypatch, task_ids
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_pretest", 2)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metadata = [
        {"episode_id": idx, "episode_seed": idx, "task_id": task_id}
        for idx, task_id in enumerate(task_ids)
    ]
    (output_dir / "eds_eval" / "episode_metadata.jsonl").write_text(
        "\n".join(json.dumps(record) for record in metadata) + "\n",
        encoding="utf-8",
    )
    validity = runner._job_validity(job)
    assert validity["valid"] is False
    assert "task ids" in validity["failure_reason"]
    assert runner._job_has_complete_outputs(job) is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("nonfinite_count", float("nan")),
        ("nonfinite_count", float("inf")),
        ("nonfinite_count", None),
        ("nonfinite_count", "0"),
        ("action_mask_violation_max", float("nan")),
        ("action_mask_violation_max", float("inf")),
        ("action_mask_violation_max", None),
        ("action_mask_violation_max", True),
    ],
)
def test_p2_safety_metrics_require_numeric_finite_zero(
    tmp_path, monkeypatch, field, value
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
    records = runner._read_jsonl(metrics_path)
    records[0][field] = value
    metrics_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    validity = runner._job_validity(job)
    assert validity["valid"] is False
    assert field in validity["failure_reason"]
    assert runner._job_has_complete_outputs(job) is False


def test_p2_requires_mechanism_evidence_in_every_episode(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    missing_episode = output_dir / "eds_eval" / "qualitative" / "episode_004"
    for path in missing_episode.rglob("*"):
        if path.is_file() and runner._is_p2_mechanism_artifact(path, missing_episode):
            path.unlink()
    validity = runner._job_validity(job)
    assert validity["valid"] is False
    assert "episode 4 mechanism evidence missing" in validity["failure_reason"]
    assert runner._job_has_complete_outputs(job) is False


def test_p2_rejects_symlinked_core_evidence(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    results_path = output_dir / "results.txt"
    outside = tmp_path / "outside-results.txt"
    outside.write_text(results_path.read_text(encoding="utf-8"), encoding="utf-8")
    results_path.unlink()
    results_path.symlink_to(outside)

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "symlink" in validity["failure_reason"]
    assert runner._job_has_complete_outputs(job) is False


def test_p2_accepts_hydra_special_run_dir_only_in_hydra_runtime(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)

    validity = runner._job_validity(job)

    assert validity["valid"] is True, validity["failure_reason"]


def test_p2_credential_token_pattern_does_not_match_task_specific_text():
    runner = _load_runner()

    assert runner._p2_text_has_credential("task-specific notes", set()) is False
    assert runner._p2_text_has_credential("token=sk-poe-secret", set()) is True


def test_p2_credential_scan_streams_markdown_and_runtime_secrets(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_LOG_ROOT = tmp_path / "logs"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    secret = "runtime-test-secret-value"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    report = output_dir / "report.md"
    report.write_text("prefix\n" + secret + "\nsuffix\n", encoding="utf-8")
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *args, **kwargs: pytest.fail("credential scanner must stream text"),
    )

    assert runner._contains_serialized_api_key(
        {"level": "p2_adaptive_eds_rbf_stage_a", "label": "x"}, output_dir
    ) is True


@pytest.mark.parametrize(
    "serialized",
    [
        "OPENAI_API_KEY=sk-test-serialized-value",
        "google_api_key: AIzaSerializedCredentialValue",
        'auth_token: "token-serialized-value"',
    ],
)
def test_p2_credential_scan_detects_common_key_patterns(tmp_path, serialized):
    runner = _load_runner()
    runner.P2_LOG_ROOT = tmp_path / "logs"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "notes.md").write_text(serialized, encoding="utf-8")

    assert runner._contains_serialized_api_key(
        {"level": "p2_adaptive_eds_rbf_stage_a", "label": "x"}, output_dir
    ) is True


def test_p2_credential_scan_fails_closed_on_oversized_text(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_LOG_ROOT = tmp_path / "logs"
    monkeypatch.setattr(runner, "P2_CREDENTIAL_SCAN_MAX_TEXT_BYTES", 8)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "large.md").write_text("ordinary text", encoding="utf-8")

    assert runner._contains_serialized_api_key(
        {"level": "p2_adaptive_eds_rbf_stage_a", "label": "x"}, output_dir
    ) is True


def test_p2_credential_scan_skips_video_and_tensor_binary(tmp_path):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_OUTPUT_ROOT.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "video.mp4").write_bytes(b"sk-poe-binary-content")
    (output_dir / "trace.pt").write_bytes(b"OPENAI_API_KEY=sk-binary-content")

    assert runner._contains_serialized_api_key(
        {"level": "p2_adaptive_eds_rbf_stage_a", "label": "x"}, output_dir
    ) is False


def test_p2_archive_redactor_streams_markdown_csv_and_chunk_boundaries(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    monkeypatch.setattr(runner, "P2_CREDENTIAL_SCAN_CHUNK_BYTES", 32)
    secret = "runtime-secret-crosses-chunk-boundary"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    archive = tmp_path / "archive"
    archive.mkdir()
    markdown = archive / "report.md"
    csv_path = archive / "metrics.csv"
    markdown.write_text("x" * 29 + secret + "\n" + "z" * 200000, encoding="utf-8")
    csv_path.write_text(
        "name,value\napi_key,serialized-common-secret-value\n" + "q" * 200000,
        encoding="utf-8",
    )

    runner._redact_secrets_in_text_tree(archive)

    assert secret not in markdown.read_text(encoding="utf-8")
    assert "serialized-common-secret-value" not in csv_path.read_text(encoding="utf-8")
    assert runner._p2_tree_contains_credential(archive) is False


@pytest.mark.parametrize(
    "mutation",
    [
        "only_episode_zero",
        "wrong_task",
        "wrong_seed",
        "nan_latency",
        "illegal_status",
        "negative_step",
        "bad_episode_type",
    ],
)
def test_p2_stage_trace_requires_valid_aligned_query_per_episode(
    tmp_path, monkeypatch, mutation
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    events_path = output_dir / "eds_eval" / "stage_events.jsonl"
    events = runner._read_jsonl(events_path)
    if mutation == "only_episode_zero":
        events = events[:1]
    elif mutation == "wrong_task":
        events[4]["task_id"] = 9
    elif mutation == "wrong_seed":
        events[4]["episode_seed"] = 999
    elif mutation == "nan_latency":
        events[4]["query_latency_s"] = float("nan")
    elif mutation == "illegal_status":
        events[4]["query_status"] = "maybe"
    elif mutation == "negative_step":
        events[4]["global_step"] = -1
    else:
        events[4]["episode_id"] = "4"
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    validity = runner._job_validity(job)
    assert validity["valid"] is False
    assert "stage query" in validity["failure_reason"]
    assert runner._job_has_complete_outputs(job) is False


@pytest.mark.parametrize(
    "failure",
    [
        "results",
        "video",
        "unreadable_video",
        "hydra",
        "query",
        "qualitative",
        "metrics",
        "fingerprint",
        "credential",
        "fallback",
        "nonfinite",
        "mask",
        "normal_fallback",
        "extra_video",
    ],
)
def test_p2_resume_rejects_each_invalid_output(tmp_path, monkeypatch, failure):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = _write_valid_p2_job(runner, job)
    monkeypatch.setattr(
        runner,
        "_ffprobe_video_readable",
        lambda _path: failure != "unreadable_video",
    )
    metrics_dir = output_dir / "eds_eval"
    if failure == "results":
        (output_dir / "results.txt").unlink()
    elif failure == "video":
        next(output_dir.glob("episode_*/*.mp4")).unlink()
    elif failure == "hydra":
        (output_dir / ".hydra" / "config.yaml").unlink()
    elif failure == "query":
        (metrics_dir / "stage_events.jsonl").write_text("", encoding="utf-8")
    elif failure == "qualitative":
        for path in (metrics_dir / "qualitative").rglob("*"):
            if path.is_file():
                path.unlink()
    elif failure == "metrics":
        (metrics_dir / "eds_metrics.jsonl").write_text(
            json.dumps({"episode": 0, "nonfinite_count": 0}) + "\n",
            encoding="utf-8",
        )
    elif failure == "fingerprint":
        (output_dir / "config_fingerprint.txt").write_text("bad\n", encoding="utf-8")
    elif failure == "credential":
        (output_dir / "serialized.log").write_text("sk-poe-secret", encoding="utf-8")
    elif failure == "normal_fallback":
        runner._log_file_for_job(job).write_text(
            "falling back to normal LIBERO\n", encoding="utf-8"
        )
    elif failure == "extra_video":
        extra = output_dir / "episode_999"
        extra.mkdir()
        (extra / "video.mp4").write_bytes(b"readable")
    elif failure in {"fallback", "nonfinite", "mask"}:
        records = runner._read_jsonl(metrics_dir / "eds_metrics.jsonl")
        field, value = {
            "fallback": ("rollout_diversity_fallback_used", True),
            "nonfinite": ("nonfinite_count", 1),
            "mask": ("action_mask_violation_max", 0.1),
        }[failure]
        records[0][field] = value
        (metrics_dir / "eds_metrics.jsonl").write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
    assert runner._job_validity(job)["valid"] is False
    assert runner._job_has_complete_outputs(job) is False


def test_p2_job_identity_refuses_fingerprint_conflict(tmp_path):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = runner._output_dir(job)
    output_dir.mkdir(parents=True)
    (output_dir / "config_fingerprint.txt").write_text("other\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="fingerprint"):
        runner._write_p2_job_identity(job)


def test_p2_job_identity_refuses_unowned_nonempty_directory(tmp_path):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    output_dir = runner._output_dir(job)
    output_dir.mkdir(parents=True)
    (output_dir / "stale.txt").write_text("old", encoding="utf-8")
    with pytest.raises(RuntimeError, match="fingerprint"):
        runner._write_p2_job_identity(job)


def test_p2_init_validates_storage_before_building_jobs(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_STATUS_ROOT = tmp_path / "status"
    order = []
    original_build = runner.build_jobs
    monkeypatch.setattr(runner, "_validate_p2_output_storage", lambda: order.append("storage"))

    def build(*args, **kwargs):
        order.append("build")
        return original_build(*args, **kwargs)

    monkeypatch.setattr(runner, "build_jobs", build)
    assert runner.init("p2_adaptive_eds_rbf_stage_a", 10) == 0
    assert order[:2] == ["storage", "build"]


def test_p2_run_rejects_storage_before_build_or_gpu_submission(monkeypatch):
    runner = _load_runner()
    calls = []

    def reject_storage():
        calls.append("storage")
        raise RuntimeError("unsafe storage")

    monkeypatch.setattr(runner, "_validate_p2_output_storage", reject_storage)
    monkeypatch.setattr(
        runner,
        "build_jobs",
        lambda *args, **kwargs: pytest.fail("jobs built before storage gate"),
    )
    with pytest.raises(RuntimeError, match="unsafe storage"):
        runner.run_level("p2_adaptive_eds_rbf_stage_a", 10, "2", 10)
    assert calls == ["storage"]


def test_p2_resume_skips_only_strictly_valid_job(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_STATUS_ROOT = tmp_path / "status"
    job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    _write_valid_p2_job(runner, job)
    monkeypatch.setattr(runner, "P2_STAGE_A_METHODS", [runner.P2_STAGE_A_METHODS[0]])
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    monkeypatch.setattr(runner, "_validate_p2_output_storage", lambda: None)
    monkeypatch.setattr(runner, "_validate_stage_level_start", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "run_job",
        lambda *args, **kwargs: pytest.fail("strictly valid resume output was rerun"),
    )
    assert runner.run_level(
        "p2_adaptive_eds_rbf_stage_a", 10, "2", 10, resume=True
    ) == 0


def test_p2_resume_does_not_skip_when_runtime_cache_changes(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_STATUS_ROOT = tmp_path / "status"
    original_job = runner.build_jobs("p2_adaptive_eds_rbf_stage_a", 10)[0]
    _write_valid_p2_job(runner, original_job)
    monkeypatch.setattr(runner, "P2_STAGE_A_METHODS", [runner.P2_STAGE_A_METHODS[0]])
    monkeypatch.setattr(runner, "_ffprobe_video_readable", lambda _path: True)
    monkeypatch.setattr(runner, "_validate_p2_output_storage", lambda: runner.P2_OUTPUT_ROOT)
    monkeypatch.setattr(runner, "_validate_stage_level_start", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_p2_gpu_probe", lambda _gpu: ("idle", ""))
    called = []
    monkeypatch.setattr(
        runner,
        "run_job",
        lambda *args, **kwargs: called.append((args, kwargs))
        or runner._status_row(args[0], "done", gpu=kwargs["gpu"]),
    )

    exit_code = runner.run_level(
        "p2_adaptive_eds_rbf_stage_a",
        10,
        "2",
        10,
        resume=True,
        cached_functions_dir="/different/cache",
    )

    assert exit_code == 1
    assert called == []
    status = list(csv.DictReader(runner._p2_status_path(
        "p2_adaptive_eds_rbf_stage_a", runner.P2_OUTPUT_ROOT
    ).open(encoding="utf-8")))[0]
    assert status["status"] == "failed"
    assert "fingerprint" in status["failure_reason"]


def test_p2_gpu_policy_rejects_unapproved_or_duplicate_devices(monkeypatch):
    runner = _load_runner()
    monkeypatch.setattr(runner, "_validate_p2_output_storage", lambda: None)
    for gpus in ["0", "1,2", "2,6", "7", "2,2", "2,3,4,5,2"]:
        with pytest.raises(SystemExit):
            runner.run_level("p2_adaptive_eds_rbf_pretest", 2, gpus, 10)


def test_p2_gpu_workers_wait_until_physical_gpu_is_idle(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_STATUS_ROOT = tmp_path / "status"
    monkeypatch.setattr(runner, "_validate_p2_output_storage", lambda: None)
    monkeypatch.setattr(runner, "_validate_stage_level_start", lambda *args, **kwargs: None)
    idle_checks = []
    sleeps = []

    def fake_probe(gpu):
        idle_checks.append(gpu)
        return ("idle", "") if len(idle_checks) > 1 else ("busy", "compute process")

    seen = []

    def fake_run(job, gpu, timeout_seconds, **kwargs):
        del timeout_seconds, kwargs
        seen.append((job["label"], gpu))
        return runner._status_row(job, "done", gpu=gpu)

    monkeypatch.setattr(runner, "_p2_gpu_probe", fake_probe)
    monkeypatch.setattr(runner.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(runner, "run_job", fake_run)
    monkeypatch.setattr(runner, "_archive_p2_job_artifacts", lambda _job: None)

    assert runner.run_level(
        "p2_adaptive_eds_rbf_pretest",
        2,
        "2",
        10,
        gpu_poll_interval_s=0.25,
    ) == 0
    assert len(seen) == 6
    assert idle_checks[:2] == ["2", "2"]
    assert sleeps == [0.25]


def test_p2_busy_worker_does_not_reserve_job_from_idle_worker(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_STATUS_ROOT = tmp_path / "status"
    monkeypatch.setattr(runner, "_validate_p2_output_storage", lambda: None)
    monkeypatch.setattr(runner, "_validate_stage_level_start", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_p2_gpu_probe",
        lambda gpu: ("busy", "compute process") if gpu == "2" else ("idle", ""),
    )
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(runner, "_archive_p2_job_artifacts", lambda _job: None)
    seen = []

    def fake_run(job, gpu, timeout_seconds, **kwargs):
        del timeout_seconds, kwargs
        seen.append((job["label"], gpu))
        return runner._status_row(job, "done", gpu=gpu)

    monkeypatch.setattr(runner, "run_job", fake_run)

    assert runner.run_level(
        "p2_adaptive_eds_rbf_pretest",
        2,
        "2,3",
        10,
        gpu_poll_interval_s=0.001,
    ) == 0
    assert len(seen) == 6
    assert {gpu for _label, gpu in seen} == {"3"}


def test_p2_probe_failure_is_machine_readable_without_blocking_idle_worker(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.P2_OUTPUT_ROOT = tmp_path / "p2"
    runner.P2_LOG_ROOT = tmp_path / "logs"
    runner.P2_STATUS_ROOT = tmp_path / "status"
    monkeypatch.setattr(runner, "_validate_p2_output_storage", lambda: None)
    monkeypatch.setattr(runner, "_validate_stage_level_start", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_p2_gpu_probe",
        lambda gpu: ("error", "nvidia-smi timeout") if gpu == "2" else ("idle", ""),
    )
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(runner, "_archive_p2_job_artifacts", lambda _job: None)
    seen = []

    def fake_run(job, gpu, timeout_seconds, **kwargs):
        del timeout_seconds, kwargs
        seen.append((job["label"], gpu))
        return runner._status_row(job, "done", gpu=gpu)

    monkeypatch.setattr(runner, "run_job", fake_run)

    assert runner.run_level(
        "p2_adaptive_eds_rbf_pretest",
        2,
        "2,3",
        10,
        gpu_poll_interval_s=0.001,
        gpu_probe_failure_limit=2,
    ) == 0
    assert len(seen) == 6
    assert {gpu for _label, gpu in seen} == {"3"}
    failure = (
        runner.P2_STATUS_ROOT
        / "failures"
        / "pretest"
        / "gpu_2_probe_failure.json"
    )
    payload = json.loads(failure.read_text(encoding="utf-8"))
    assert payload["gpu"] == "2"
    assert payload["status"] == "failed"
    assert payload["failure_reason"] == "nvidia-smi timeout"


def test_old_level_matrix_and_command_regression_after_p2_extension():
    runner = _load_runner()
    assert len(runner.build_jobs("level4", 10)) == 24
    assert len(runner.build_jobs("object_swap_ood_rbf", 10)) == 257
    old = runner.build_jobs("level3", 10)[0]
    assert "backend.libero.max_episode_steps=240" in runner.build_main_command(old, "0", 10)


def test_old_level_run_job_preserves_pre_p2_gpu_environment(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    runner.RUN_ROOT = tmp_path / "runs"
    monkeypatch.delenv("CUDA_DEVICE_ORDER", raising=False)
    monkeypatch.delenv("MUJOCO_EGL_DEVICE_ID", raising=False)
    captured = {}

    def fake_subprocess_run(*args, **kwargs):
        del args
        captured.update(kwargs["env"])
        return runner.subprocess.CompletedProcess([], 1)

    monkeypatch.setattr(runner.subprocess, "run", fake_subprocess_run)
    job = runner.build_jobs("level2", 3)[0]
    runner.run_job(job, gpu="2", timeout_seconds=1)

    assert captured["CUDA_VISIBLE_DEVICES"] == "2"
    assert "CUDA_DEVICE_ORDER" not in captured
    assert "MUJOCO_EGL_DEVICE_ID" not in captured
