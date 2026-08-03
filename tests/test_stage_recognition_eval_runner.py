import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "rdt_eds_eval_runner.py"
    spec = importlib.util.spec_from_file_location("rdt_eds_stage_eval_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage_recognition_ablation_jobs_are_paired_720_step_profiles():
    runner = _load_runner()

    jobs = runner.build_jobs("stage_recognition_ablation", episodes=10)

    assert [job["label"] for job in jobs] == [
        "p1_stage_off",
        "p1_stage_on",
        "p2_stage_off",
        "p2_stage_on",
    ]
    assert len(jobs) == 4
    assert {job["suite"] for job in jobs} == {"libero_object_swap"}
    assert {job["episodes"] for job in jobs} == {10}
    assert {job["max_episode_steps"] for job in jobs} == {720}
    assert {job["gemini_grounding_enabled"] for job in jobs} == {False}
    assert [job["stage_recognition_enabled"] for job in jobs] == [
        False,
        True,
        False,
        True,
    ]
    assert {
        (
            job["profile"],
            job["renoise_t_max"],
            job["rollout_diversity_scale"],
            job["rollout_diversity_start_ratio"],
            job["rollout_diversity_iters"],
        )
        for job in jobs
    } == {
        ("p1", 2, 5.0, 0.2, "all"),
        ("p2", 3, 20.0, 0.6, "all"),
    }
    assert {job["population_size"] for job in jobs} == {16}
    assert {job["cem_iters"] for job in jobs} == {10}
    assert {job["num_elites"] for job in jobs} == {16}
    assert {job["initial_diversity_scale"] for job in jobs} == {20.0}
    assert {job["initial_diversity_start_ratio"] for job in jobs} == {0.8}


def test_stage_recognition_pretest_targets_tasks_zero_and_six():
    runner = _load_runner()

    jobs = runner.build_jobs("stage_recognition_pretest", episodes=2)

    assert len(jobs) == 1
    assert jobs[0]["label"] == "p1_stage_on_pretest"
    assert jobs[0]["stage_recognition_enabled"] is True
    assert jobs[0]["gemini_grounding_enabled"] is False
    assert jobs[0]["task_ids_filter"] == [0, 6]
    assert jobs[0]["episodes"] == 2
    assert jobs[0]["max_episode_steps"] == 720


def test_stage_ablation_commands_decouple_stage_recognition_and_grounding():
    runner = _load_runner()
    jobs = runner.build_jobs("stage_recognition_ablation", episodes=10)
    off_job, on_job = jobs[0], jobs[1]

    off_cmd = runner.build_main_command(off_job, gpu="2", timeout_seconds=1)
    on_cmd = runner.build_main_command(on_job, gpu="2", timeout_seconds=1)

    for command in (off_cmd, on_cmd):
        assert "backend.libero.suite_name=libero_object_swap" in command
        assert "backend.libero.strict_perturbations=true" in command
        assert "backend.libero.max_episode_steps=720" in command
        assert "perception.gemini_grounding.enabled=false" in command
        assert "seed=0" in command
        assert not any(part.startswith("backend.libero.task_ids_filter=") for part in command)
        assert "main.eds_config.initial_diversity_scale=20.0" in command
        assert "main.eds_config.initial_diversity_start_ratio=0.8" in command

    assert "main.use_vlm_stage_recognition=false" in off_cmd
    assert "main.use_vlm_stage_recognition=true" in on_cmd
    assert "main.eds_config.renoise_t_max=2" in on_cmd
    assert "main.eds_config.rollout_diversity_scale=5.0" in on_cmd
    assert "main.eds_config.rollout_diversity_start_ratio=0.2" in on_cmd
    assert "main.eds_config.rollout_diversity_iters=all" in on_cmd


def test_stage_pretest_command_filters_tasks_and_uses_independent_output_root():
    runner = _load_runner()
    job = runner.build_jobs("stage_recognition_pretest", episodes=2)[0]

    command = runner.build_main_command(job, gpu="2", timeout_seconds=1)

    expected = runner.STAGE_RECOGNITION_RUN_ROOT / "mechanism_pretest" / job["job_id"]
    assert "backend.libero.task_ids_filter=[0,6]" in command
    assert f"hydra.run.dir={expected}" in command
    assert f"main.eds_eval.output_dir={expected / 'eds_eval'}" in command


def test_stage_on_runtime_forces_poe_endpoint_without_logging_key(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    runner.STATUS_CSV = runner.EVIDENCE_ROOT / "status.csv"
    job = runner.build_jobs("stage_recognition_ablation", episodes=10)[1]
    captured = {}

    def fake_run(command, *, cwd, env, stdout, stderr, text, timeout):
        captured["command"] = command
        captured["env"] = env
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value-for-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://wrong.invalid/v1")

    runner.run_job(job, gpu="2", timeout_seconds=1)

    assert captured["env"]["OPENAI_BASE_URL"] == "https://api.poe.com/v1"
    assert captured["env"]["OPENAI_API_KEY"] == "secret-value-for-test"
    log_text = runner._log_file_for_job(job).read_text()
    assert "secret-value-for-test" not in log_text
    assert "OPENAI_API_KEY=" not in log_text


def _write_stage_job_artifacts(runner, job, *, stage_query_ok=True):
    output_dir = runner._output_dir(job)
    metrics_dir = output_dir / "eds_eval"
    hydra_dir = output_dir / ".hydra"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    hydra_dir.mkdir(exist_ok=True)
    for episode in range(int(job["episodes"])):
        episode_dir = output_dir / f"episode_{episode + 1}"
        episode_dir.mkdir(exist_ok=True)
        result = "success" if episode == 0 else "fail"
        (episode_dir / f"episode_{episode + 1}_{result}.mp4").write_bytes(b"video")
    (output_dir / "results.txt").write_text(
        f"Success count: 1/{job['episodes']}\n"
        f"Success rate: {100 / int(job['episodes']):.2f}%\n",
        encoding="utf-8",
    )
    metrics = []
    episode_metadata = []
    task_ids = job.get("task_ids_filter") or list(range(int(job["episodes"])))
    for episode in range(int(job["episodes"])):
        task_id = int(task_ids[episode % len(task_ids)])
        metrics.append(
            {
                "episode": episode,
                "task_id": task_id,
                "nonfinite_count": 0,
                "action_mask_violation_max": 0.0,
                "initial_diversity_fallback_used": False,
                "rollout_diversity_fallback_used": False,
            }
        )
        episode_metadata.append(
            {
                "episode_id": episode,
                "task_id": task_id,
                "episode_seed": 100 + episode,
            }
        )
        qualitative = (
            metrics_dir
            / "qualitative"
            / f"episode_{episode:03d}"
            / "chunk_000000"
        )
        qualitative.mkdir(parents=True, exist_ok=True)
        (qualitative / "00_initial_population_3d.png").write_bytes(b"png")
    (metrics_dir / "eds_metrics.jsonl").write_text(
        "\n".join(json.dumps(record) for record in metrics) + "\n",
        encoding="utf-8",
    )
    (metrics_dir / "episode_metadata.jsonl").write_text(
        "\n".join(json.dumps(record) for record in episode_metadata) + "\n",
        encoding="utf-8",
    )
    if job["stage_recognition_enabled"]:
        (metrics_dir / "stage_events.jsonl").write_text(
            json.dumps(
                {
                    "episode_id": 0,
                    "task_id": 0,
                    "episode_seed": 123,
                    "global_step": 64,
                    "chunk_id": 8,
                    "trigger_reason": "gripper closed",
                    "query_status": "ok" if stage_query_ok else "error",
                    "query_ok": stage_query_ok,
                    "stage_before": 1,
                    "stage_after": 2 if stage_query_ok else 1,
                    "guidance_before": True,
                    "guidance_after": False if stage_query_ok else True,
                    "parsed_stage": 2 if stage_query_ok else 1,
                    "parsed_guidance": False if stage_query_ok else True,
                    "query_latency_s": 0.25,
                    "error": None if stage_query_ok else "api failed",
                }
            )
            + "\n",
            encoding="utf-8",
        )
    overrides = [
        part
        for part in runner.build_main_command(job, gpu="2", timeout_seconds=1)
        if "=" in part and not part.startswith("hydra.run.dir=")
    ]
    (hydra_dir / "overrides.yaml").write_text(
        "\n".join(f"- {line}" for line in overrides) + "\n",
        encoding="utf-8",
    )
    (hydra_dir / "config.yaml").write_text(
        "backend:\n  libero:\n    suite_name: libero_object_swap\n",
        encoding="utf-8",
    )
    return output_dir


def test_stage_ablation_validity_requires_720_grounding_off_and_successful_query(tmp_path):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    on_job = runner.build_jobs("stage_recognition_ablation", episodes=10)[1]

    output_dir = _write_stage_job_artifacts(runner, on_job, stage_query_ok=False)
    failed = runner._job_validity(on_job)
    assert failed["valid"] is False
    assert "successful stage query" in failed["failure_reason"]

    (output_dir / "eds_eval" / "stage_events.jsonl").write_text(
        json.dumps(
            {
                "episode_id": 0,
                "task_id": 0,
                "episode_seed": 100,
                "global_step": 64,
                "chunk_id": 8,
                "trigger_reason": "gripper closed",
                "query_status": "ok",
                "query_ok": True,
                "stage_before": 1,
                "stage_after": 2,
                "guidance_before": True,
                "guidance_after": False,
                "parsed_stage": 2,
                "parsed_guidance": False,
                "query_latency_s": 0.25,
                "error": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    valid = runner._job_validity(on_job)
    assert valid["valid"] is True

    overrides = output_dir / ".hydra" / "overrides.yaml"
    overrides.write_text(
        overrides.read_text().replace(
            "backend.libero.max_episode_steps=720",
            "backend.libero.max_episode_steps=240",
        ),
        encoding="utf-8",
    )
    stale = runner._job_validity(on_job)
    assert stale["valid"] is False
    assert "max_episode_steps=720" in stale["failure_reason"]


def test_stage_validity_rejects_incomplete_episode_and_hydra_evidence(tmp_path):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    job = runner.build_jobs("stage_recognition_ablation", episodes=10)[0]
    output_dir = _write_stage_job_artifacts(runner, job)

    (output_dir / ".hydra" / "config.yaml").unlink()
    missing_config = runner._job_validity(job)
    assert missing_config["valid"] is False
    assert ".hydra/config.yaml" in missing_config["failure_reason"]

    (output_dir / ".hydra" / "config.yaml").write_text("enabled: false\n")
    video = next((output_dir / "episode_3").glob("*.mp4"))
    video.unlink()
    missing_episode_video = runner._job_validity(job)
    assert missing_episode_video["valid"] is False
    assert "episode 2 video" in missing_episode_video["failure_reason"]

    (output_dir / "episode_3" / "episode_3_fail_agentview.mp4").write_bytes(b"video")
    metadata_path = output_dir / "eds_eval" / "episode_metadata.jsonl"
    metadata_path.write_text(metadata_path.read_text().splitlines()[0] + "\n")
    missing_seeds = runner._job_validity(job)
    assert missing_seeds["valid"] is False
    assert "episode seed metadata" in missing_seeds["failure_reason"]


def test_stage_validity_uses_exact_grounding_override_and_complete_query_fields(tmp_path):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    job = runner.build_jobs("stage_recognition_ablation", episodes=10)[1]
    output_dir = _write_stage_job_artifacts(runner, job)

    overrides = output_dir / ".hydra" / "overrides.yaml"
    overrides.write_text(
        overrides.read_text().replace(
            "perception.gemini_grounding.enabled=false",
            "perception.gemini_grounding.enabled=true",
        )
        + "- some.other.enabled=false\n"
    )
    wrong_grounding = runner._job_validity(job)
    assert wrong_grounding["valid"] is False
    assert "perception.gemini_grounding.enabled=false" in wrong_grounding["failure_reason"]

    _write_stage_job_artifacts(runner, job)
    event_path = output_dir / "eds_eval" / "stage_events.jsonl"
    event = json.loads(event_path.read_text())
    event.pop("parsed_guidance")
    event_path.write_text(json.dumps(event) + "\n")
    incomplete_event = runner._job_validity(job)
    assert incomplete_event["valid"] is False
    assert "stage query fields" in incomplete_event["failure_reason"]


def test_stage_validity_rejects_runtime_api_key_in_artifacts(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    job = runner.build_jobs("stage_recognition_ablation", episodes=10)[1]
    output_dir = _write_stage_job_artifacts(runner, job)
    monkeypatch.setenv("OPENAI_API_KEY", "arbitrary-secret-without-known-prefix")
    event_path = output_dir / "eds_eval" / "stage_events.jsonl"
    event_path.write_text(
        event_path.read_text() + "arbitrary-secret-without-known-prefix\n"
    )

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "API key material" in validity["failure_reason"]


@pytest.mark.parametrize(
    "relative_path",
    ["episode_1/error.txt", "debug/leak.yml"],
)
def test_stage_validity_scans_text_artifacts_for_runtime_api_key(
    tmp_path, monkeypatch, relative_path
):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = (
        runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    )
    job = runner.build_jobs("stage_recognition_ablation", episodes=10)[1]
    output_dir = _write_stage_job_artifacts(runner, job)
    monkeypatch.setenv("OPENAI_API_KEY", "arbitrary-secret-without-known-prefix")
    error_path = output_dir / relative_path
    error_path.parent.mkdir(parents=True, exist_ok=True)
    error_path.write_text("arbitrary-secret-without-known-prefix\n")

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "API key material" in validity["failure_reason"]


def test_stage_validity_rejects_duplicate_episode_metadata(tmp_path):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = (
        runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    )
    job = runner.build_jobs("stage_recognition_ablation", episodes=10)[0]
    output_dir = _write_stage_job_artifacts(runner, job)
    metadata_path = output_dir / "eds_eval" / "episode_metadata.jsonl"
    first_record = metadata_path.read_text().splitlines()[0]
    metadata_path.write_text(metadata_path.read_text() + first_record + "\n")

    validity = runner._job_validity(job)

    assert validity["valid"] is False
    assert "episode seed metadata count" in validity["failure_reason"]


def test_stage_ablation_report_contains_paired_results_and_horizon_caveat(tmp_path):
    runner = _load_runner()
    runner.WORKTREE_ROOT = tmp_path
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    runner.EVIDENCE_ROOT = tmp_path / "docs" / "03_evidence" / "eds_init_pg_diverse_sampling"
    runner.STATUS_CSV = runner.EVIDENCE_ROOT / "status.csv"
    runner.STAGE_RECOGNITION_REPORT = "stage-report.md"
    for job in runner.build_jobs("stage_recognition_ablation", episodes=10):
        _write_stage_job_artifacts(runner, job)

    report = runner.write_stage_recognition_ablation_report(episodes=10)
    text = report.read_text(encoding="utf-8")

    assert report == runner.EVIDENCE_ROOT / "stage-report.md"
    assert "p1_stage_off" in text
    assert "p1_stage_on" in text
    assert "p2_stage_off" in text
    assert "p2_stage_on" in text
    assert "720-step" in text
    assert "240-step" in text
    assert "2x2" in text
    assert "Stage Recognition" in text
    assert "## Mechanism Pretest" in text
    assert "## Episode Seed Pairing" in text
    assert "## EDS Metrics" in text
    assert "## Stage Event Summary" in text
    assert "## Stage/Guidance Timeline Artifacts" in text
    assert "## Failure Classification" in text
    paired_section = text.split("## Paired A/B Comparison", 1)[1].split(
        "## Episode Seed Pairing", 1
    )[0]
    seed_section = text.split("## Episode Seed Pairing", 1)[1].split(
        "## Historical 240-Step Context", 1
    )[0]
    assert "| `p1` | 1/10 | 1/10 | 0 | 0.00 |" in paired_section
    assert "| `p2` | 1/10 | 1/10 | 0 | 0.00 |" in paired_section
    assert "1/10" not in seed_section


def test_stage_timeline_artifacts_cover_every_stage_on_episode(tmp_path):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = (
        runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    )
    jobs = runner.build_jobs("stage_recognition_ablation", episodes=2)
    for job in jobs:
        if job["stage_recognition_enabled"]:
            _write_stage_job_artifacts(runner, job)

    paths = runner.write_stage_recognition_timeline_artifacts(episodes=2)

    assert len(paths) == 4
    assert all(path.exists() and path.stat().st_size > 0 for path in paths)
    assert {path.parent.name for path in paths} == {
        "stage_ablation_libero_object_swap_p1_stage_on",
        "stage_ablation_libero_object_swap_p2_stage_on",
    }


def test_stage_ablation_init_writes_independent_run_manifest(tmp_path):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    runner.STAGE_STATUS_CSV = runner.STAGE_RECOGNITION_RUN_ROOT / "run_manifest.csv"
    runner.EVIDENCE_ROOT = tmp_path / "evidence"

    assert runner.init("stage_recognition_ablation", episodes=10) == 0

    text = runner.STAGE_STATUS_CSV.read_text(encoding="utf-8")
    assert "p1_stage_off" in text
    assert "p2_stage_on" in text
    assert "stage_recognition_enabled" in text


def test_stage_report_blocks_mismatched_paired_episode_seeds(tmp_path):
    runner = _load_runner()
    runner.WORKTREE_ROOT = tmp_path
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    runner.STAGE_RECOGNITION_REPORT = "stage-report.md"
    jobs = runner.build_jobs("stage_recognition_ablation", episodes=10)
    for job in jobs:
        _write_stage_job_artifacts(runner, job)
    _write_stage_job_artifacts(
        runner,
        runner.build_jobs("stage_recognition_pretest", episodes=2)[0],
    )
    on_output = runner._output_dir(jobs[1])
    metadata_path = on_output / "eds_eval" / "episode_metadata.jsonl"
    records = [json.loads(line) for line in metadata_path.read_text().splitlines()]
    records[0]["episode_seed"] = 999
    metadata_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n"
    )

    text = runner.write_stage_recognition_ablation_report(episodes=10).read_text()

    assert "Verdict: `blocked`" in text
    assert "| `p1` |" in text
    assert "`False`" in text


def test_stage_levels_reject_any_gpu_other_than_two(tmp_path):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    runner.STAGE_STATUS_CSV = runner.STAGE_RECOGNITION_RUN_ROOT / "run_manifest.csv"
    runner.EVIDENCE_ROOT = tmp_path / "evidence"

    with pytest.raises(SystemExit, match="GPU 2"):
        runner.run_level(
            "stage_recognition_ablation",
            episodes=10,
            gpus="3",
            timeout_seconds=1,
        )


def test_gpu_two_uses_its_physical_egl_device():
    runner = _load_runner()

    assert runner._gpu_runtime("2") == {
        "cuda_visible_devices": "2",
        "mujoco_egl_device_id": "1",
    }


def test_stage_ablation_requires_valid_pretest_and_real_api_key(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    runner.STAGE_STATUS_CSV = runner.STAGE_RECOGNITION_RUN_ROOT / "run_manifest.csv"
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    monkeypatch.setenv("OPENAI_API_KEY", "real-key-for-test")
    monkeypatch.setattr(runner, "_poe_healthcheck", lambda: True)

    with pytest.raises(SystemExit, match="pretest"):
        runner.run_level(
            "stage_recognition_ablation",
            episodes=10,
            gpus="2",
            timeout_seconds=1,
        )

    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    with pytest.raises(SystemExit, match="API key"):
        runner.run_level(
            "stage_recognition_pretest",
            episodes=2,
            gpus="2",
            timeout_seconds=1,
        )

    monkeypatch.setenv("OPENAI_API_KEY", "real-key-for-test")
    with pytest.raises(SystemExit, match="offline-vlm"):
        runner.run_level(
            "stage_recognition_pretest",
            episodes=2,
            gpus="2",
            timeout_seconds=1,
            offline_vlm=True,
        )


def test_stage_pretest_rejects_failed_poe_healthcheck(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    runner.STAGE_STATUS_CSV = runner.STAGE_RECOGNITION_RUN_ROOT / "run_manifest.csv"
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    monkeypatch.setenv("OPENAI_API_KEY", "real-key-for-test")
    monkeypatch.setattr(runner, "_poe_healthcheck", lambda: False)

    with pytest.raises(SystemExit, match="health check"):
        runner.run_level(
            "stage_recognition_pretest",
            episodes=2,
            gpus="2",
            timeout_seconds=1,
        )


def test_stage_resume_with_only_off_job_pending_does_not_require_api(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = (
        runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    )
    runner.STAGE_STATUS_CSV = runner.STAGE_RECOGNITION_RUN_ROOT / "run_manifest.csv"
    runner.EVIDENCE_ROOT = tmp_path / "evidence"

    pretest_job = runner.build_jobs("stage_recognition_pretest", episodes=2)[0]
    _write_stage_job_artifacts(runner, pretest_job)
    jobs = runner.build_jobs("stage_recognition_ablation", episodes=10)
    pending_job = next(job for job in jobs if job["label"] == "p2_stage_off")
    for job in jobs:
        if job is not pending_job:
            _write_stage_job_artifacts(runner, job)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        runner,
        "_poe_healthcheck",
        lambda: (_ for _ in ()).throw(AssertionError("healthcheck should not run")),
    )

    def fake_run_job(job, **kwargs):
        assert job["job_id"] == pending_job["job_id"]
        _write_stage_job_artifacts(runner, job)
        validity = runner._job_validity(job)
        return {
            **runner._status_row(job, "done", gpu="2"),
            "exit_code": 0,
            "valid": validity["valid"],
            "failure_reason": validity["failure_reason"],
        }

    monkeypatch.setattr(runner, "run_job", fake_run_job)
    monkeypatch.setattr(
        runner,
        "write_stage_recognition_ablation_report",
        lambda episodes: tmp_path / "report.md",
    )

    assert runner.run_level(
        "stage_recognition_ablation",
        episodes=10,
        gpus="2",
        timeout_seconds=1,
        resume=True,
    ) == 0


def test_stage_runner_records_worker_exception_in_manifest(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    runner.STAGE_STATUS_CSV = runner.STAGE_RECOGNITION_RUN_ROOT / "run_manifest.csv"
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    monkeypatch.setenv("OPENAI_API_KEY", "real-key-for-test")
    monkeypatch.setattr(runner, "_poe_healthcheck", lambda: True)
    monkeypatch.setattr(
        runner,
        "run_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("worker boom")),
    )

    result = runner.run_level(
        "stage_recognition_pretest",
        episodes=2,
        gpus="2",
        timeout_seconds=1,
    )

    assert result == 1
    manifest = runner.STAGE_STATUS_CSV.read_text()
    assert "failed" in manifest
    assert "worker boom" in manifest


def test_stage_runner_archives_stale_artifacts_before_rerun(tmp_path, monkeypatch):
    runner = _load_runner()
    runner.OOD_RUN_ROOT = tmp_path / "outputs" / "ood_eval"
    runner.STAGE_RECOGNITION_RUN_ROOT = (
        runner.OOD_RUN_ROOT / "stage_recognition_ablation"
    )
    runner.STAGE_STATUS_CSV = runner.STAGE_RECOGNITION_RUN_ROOT / "run_manifest.csv"
    runner.EVIDENCE_ROOT = tmp_path / "evidence"
    job = runner.build_jobs("stage_recognition_pretest", episodes=2)[0]
    output_dir = runner._output_dir(job)
    output_dir.mkdir(parents=True)
    (output_dir / "stale.jsonl").write_text('{"episode": 0}\n')
    secret = "arbitrary-secret-without-known-prefix"
    (output_dir / "error.txt").write_text(f"request failed with {secret}\n")
    log_file = runner._log_file_for_job(job)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(f"stale log {secret}\n")
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setattr(runner, "_validate_stage_level_start", lambda *args, **kwargs: None)

    def fake_run_job(running_job, **kwargs):
        assert running_job["job_id"] == job["job_id"]
        assert not output_dir.exists()
        assert not log_file.exists()
        return {
            **runner._status_row(running_job, "done", gpu="2"),
            "exit_code": 0,
            "failure_reason": "",
        }

    monkeypatch.setattr(runner, "run_job", fake_run_job)

    result = runner.run_level(
        "stage_recognition_pretest",
        episodes=2,
        gpus="2",
        timeout_seconds=1,
        resume=True,
    )

    assert result == 0
    stale_runs = list((runner.STAGE_RECOGNITION_RUN_ROOT / "stale").glob("*"))
    assert len(stale_runs) == 1
    assert (stale_runs[0] / "output" / "stale.jsonl").exists()
    assert (stale_runs[0] / "runner.log").read_text() == "stale log [REDACTED]\n"
    assert (stale_runs[0] / "output" / "error.txt").read_text() == (
        "request failed with [REDACTED]\n"
    )
