from __future__ import annotations

import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest


def _load_runner():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eds_quality_diversity_runner.py"
    )
    spec = importlib.util.spec_from_file_location(
        "eds_quality_diversity_runner", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_formal_matrix_is_exact_registered_ofat_and_seed_paired():
    runner = _load_runner()
    profiles = runner.formal_profiles()
    jobs = runner.build_jobs(runner.FORMAL_LEVEL, 10)

    assert [profile["label"] for profile in profiles] == [
        "p2_stage_on_abs_rbf_control",
        "eds_quality_diversity_uniform_primary",
        "eds_quality_diversity_sparse_primary",
        "eds_quality_diversity_uniform_grid3",
        "eds_quality_diversity_uniform_grid5",
        "eds_quality_diversity_uniform_q00100",
        "eds_quality_diversity_uniform_q1090",
        "eds_quality_diversity_uniform_expand00",
        "eds_quality_diversity_uniform_expand20",
        "eds_quality_diversity_uniform_span04",
        "eds_quality_diversity_uniform_span12",
    ]
    assert len(jobs) == 11
    assert {tuple(job["task_ids_filter"]) for job in jobs} == {tuple(range(10))}
    assert {tuple(job["episode_seeds"]) for job in jobs} == {
        tuple(runner.EPISODE_SEEDS)
    }
    primary = next(
        profile
        for profile in profiles
        if profile["label"] == "eds_quality_diversity_uniform_primary"
    )
    qd_fields = runner.QD_PROFILE_FIELDS
    for profile in profiles[2:]:
        if profile["label"] == "eds_quality_diversity_sparse_primary":
            differences = [
                field
                for field in qd_fields
                if profile[field] != primary[field]
            ]
            assert differences == ["qd_parent_sampling"]
        elif profile["role"] == "parameter_ofat":
            differences = [
                field
                for field in qd_fields
                if profile[field] != primary[field]
            ]
            assert len(differences) == 1


def test_preflight_matrix_is_exact_three_profiles_two_registered_tasks():
    runner = _load_runner()
    jobs = runner.build_preflight_jobs()

    assert [job["formal_label"] for job in jobs] == [
        "p2_stage_on_abs_rbf_control",
        "eds_quality_diversity_uniform_primary",
        "eds_quality_diversity_sparse_primary",
    ]
    assert all(job["task_ids_filter"] == [0, 8] for job in jobs)
    assert all(job["episode_seeds"] == [44, 151] for job in jobs)
    assert sum(int(job["episodes"]) for job in jobs) == 6


def test_normalized_command_overrides_accepts_only_identical_duplicates(
    monkeypatch, tmp_path
):
    runner = _load_runner()
    monkeypatch.setattr(
        runner.base,
        "build_main_command",
        lambda *args, **kwargs: [
            "python",
            "main.py",
            "main.eds_mechanism_pretest.enabled=true",
            "main.eds_mechanism_pretest.enabled=true",
        ],
    )
    assert runner.base._p2_normalized_command_overrides(
        {}, allow_identical_duplicates=True
    ) == {
        "main.eds_mechanism_pretest.enabled": True
    }

    monkeypatch.setattr(
        runner.base,
        "build_main_command",
        lambda *args, **kwargs: [
            "python",
            "main.py",
            "main.eds_mechanism_pretest.enabled=true",
            "main.eds_mechanism_pretest.enabled=false",
        ],
    )
    with pytest.raises(ValueError, match="conflicting duplicate override"):
        runner.base._p2_normalized_command_overrides({})

    overrides = tmp_path / "overrides.yaml"
    overrides.write_text(
        "- main.eds_mechanism_pretest.enabled=true\n"
        "- main.eds_mechanism_pretest.enabled=true\n",
        encoding="utf-8",
    )
    assert runner.base._parse_p2_overrides_file(
        overrides, allow_identical_duplicates=True
    ) == {
        "main.eds_mechanism_pretest.enabled": True
    }
    overrides.write_text(
        "- main.eds_mechanism_pretest.enabled=true\n"
        "- main.eds_mechanism_pretest.enabled=false\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="conflicting override"):
        runner.base._parse_p2_overrides_file(overrides)


def test_main_command_contains_all_frozen_qd_fields_and_no_credential(monkeypatch):
    runner = _load_runner()
    monkeypatch.setenv("OPENAI_API_KEY", "REDACTED")
    job = next(
        job
        for job in runner.build_jobs(runner.FORMAL_LEVEL, 10)
        if job["label"] == "eds_quality_diversity_uniform_grid3"
    )

    command = runner._build_main_command(job, "0", 10)
    text = " ".join(command)

    assert "backend.libero.suite_name=libero_object_swap" in text
    assert "backend.libero.strict_perturbations=true" in text
    assert "main.episode_seed_schedule=[44,235,43,546,6,621,197,87,151,548]" in text
    assert "main.eds_config.qd_archive_mode=grid_archive" in text
    assert "main.eds_config.qd_grid_shape=[3,3]" in text
    assert "main.eds_config.qd_metrics_observer=true" in text
    assert "main.eds_config.initial_diversity_descriptor_mode=absolute_eef" in text
    assert "main.eds_config.rollout_diversity_descriptor_mode=absolute_eef" in text
    assert "REDACTED" not in text
    assert "OPENAI_API_KEY" not in text


def test_storage_preflight_requires_entire_outputs_absolute_symlink(tmp_path, monkeypatch):
    runner = _load_runner()
    experiment_root = tmp_path / "shared2" / "eds-quality-diversity"
    output_target = experiment_root / "outputs"
    output_target.mkdir(parents=True)
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    output_link = worktree / "outputs"
    output_link.symlink_to(output_target.absolute(), target_is_directory=True)
    monkeypatch.setattr(runner, "EXPERIMENT_ROOT", experiment_root)
    monkeypatch.setattr(runner, "OUTPUT_TARGET", output_target)
    monkeypatch.setattr(runner, "OUTPUT_LINK", output_link)
    monkeypatch.setattr(runner, "ALLOWED_STORAGE_PREFIX", tmp_path / "shared2")
    monkeypatch.setattr(runner, "MIN_FREE_BYTES", 1)

    result = runner.storage_preflight()

    assert result["outputs_link"] == str(output_link)
    assert result["outputs_target"] == str(output_target.resolve())
    assert not any(output_target.glob(".qd_storage_probe*"))
    output_link.unlink()
    output_link.mkdir()
    with pytest.raises(RuntimeError, match="absolute symlink"):
        runner.storage_preflight()


def test_runtime_cache_is_exclusive_copied_and_checksum_validated(tmp_path):
    runner = _load_runner()
    source = tmp_path / "source"
    source.mkdir()
    for index, name in enumerate(runner.RUNTIME_CACHE_REQUIRED_FILES):
        (source / name).write_bytes(f"artifact-{index}".encode())
    target = tmp_path / "shared2" / "runtime_cache" / "cached_functions"
    manifest = target.parent / "cached_functions.provenance.json"

    prepared = runner.prepare_runtime_cache(
        source=source,
        target=target,
        manifest_path=manifest,
    )

    assert prepared["target_realpath"] == str(target.resolve())
    assert runner.validate_runtime_cache(
        target=target, manifest_path=manifest
    )["files"] == prepared["files"]
    with pytest.raises(FileExistsError):
        runner.prepare_runtime_cache(
            source=source,
            target=target,
            manifest_path=manifest,
        )
    (target / runner.RUNTIME_CACHE_REQUIRED_FILES[0]).write_text("tampered")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        runner.validate_runtime_cache(target=target, manifest_path=manifest)


def test_attempt_ledger_is_append_only_and_enforces_shared_124_cap(tmp_path):
    runner = _load_runner()
    ledger = tmp_path / "attempts.jsonl"
    records = [
        {
            "phase": "preflight",
            "label": "control",
            "task_id": index,
            "episode_seed": index,
            "config_fingerprint": "a" * 64,
        }
        for index in range(6)
    ]
    runner.append_attempt_records(ledger, records)
    runner.append_attempt_records(
        ledger,
        [
            {
                "phase": "formal",
                "label": "job",
                "task_id": index,
                "episode_seed": index,
                "config_fingerprint": "b" * 64,
            }
            for index in range(110)
        ],
    )

    parsed = runner.read_attempt_ledger(ledger)
    assert len(parsed) == 116
    assert [row["attempt_id"] for row in parsed] == list(range(1, 117))
    runner.append_attempt_records(
        ledger,
        [
            {
                "phase": "retry",
                "label": "job",
                "task_id": index,
                "episode_seed": index,
                "config_fingerprint": "b" * 64,
            }
            for index in range(6)
        ],
    )
    runner.append_attempt_records(
        ledger,
        [
            {
                "phase": "retry",
                "label": "job",
                "task_id": 100 + index,
                "episode_seed": 100 + index,
                "config_fingerprint": "c" * 64,
            }
            for index in range(2)
        ],
    )
    assert len(runner.read_attempt_ledger(ledger)) == 124
    before = ledger.read_bytes()
    with pytest.raises(RuntimeError, match="124"):
        runner.append_attempt_records(
            ledger,
            [
                {
                    "phase": "retry",
                    "label": "job",
                    "task_id": index,
                    "episode_seed": index,
                    "config_fingerprint": "b" * 64,
                }
                for index in range(1)
            ],
        )
    assert ledger.read_bytes() == before


def test_attempt_reservations_require_append_only_dispatch_event(tmp_path):
    runner = _load_runner()
    ledger = tmp_path / "ledger.jsonl"
    reservations = runner.append_attempt_records(
        ledger,
        [
            {
                "phase": "preflight",
                "label": "preflight__control",
                "formal_label": "control",
                "task_id": 0,
                "episode_seed": 44,
                "config_fingerprint": "a" * 64,
            }
        ],
    )
    state = runner.attempt_ledger_state(ledger)
    assert state["reserved_attempt_count"] == 1
    assert state["dispatched_attempt_count"] == 0
    assert runner.reusable_phase_reservations(
        ledger, phase="preflight", expected=reservations
    ) == [1]

    runner.append_ledger_event(
        ledger,
        {
            "record_type": "phase_dispatch",
            "phase": "preflight",
            "attempt_ids": [1],
        },
    )
    state = runner.attempt_ledger_state(ledger)
    assert state["dispatched_attempt_count"] == 1
    assert state["dispatch_events"] == 1
    with pytest.raises(RuntimeError, match="already dispatched"):
        runner.reusable_phase_reservations(
            ledger, phase="preflight", expected=reservations
        )
    runner.append_ledger_event(
        ledger,
        {
            "record_type": "dispatch_aborted_pre_episode",
            "phase": "preflight",
            "attempt_ids": [1],
            "reason": "model import failed before episode initialization",
        },
    )
    state = runner.attempt_ledger_state(ledger)
    assert state["dispatched_attempt_count"] == 0
    assert state["aborted_pre_episode_attempt_ids"] == [1]
    assert runner.reusable_phase_reservations(
        ledger, phase="preflight", expected=reservations
    ) == []


def test_formal_readiness_requires_passed_offline_libero_and_six_dispatches(tmp_path):
    runner = _load_runner()
    offline = tmp_path / "offline.json"
    preflight = tmp_path / "preflight.json"
    ledger = tmp_path / "ledger.jsonl"
    offline.write_text(json.dumps({"passed": True}))
    labels = [
        "p2_stage_on_abs_rbf_control",
        "eds_quality_diversity_uniform_primary",
        "eds_quality_diversity_sparse_primary",
    ]
    preflight.write_text(
        json.dumps(
            {
                "passed": True,
                "credential_audit": {"passed": True},
                "jobs": [
                    {
                        "formal_label": label,
                        "config_fingerprint": label,
                        "code_state_sha256": "c" * 64,
                        "valid": True,
                        "mechanism_hard": {"passed": True},
                        "task_outcomes": {"0": "fail", "8": "fail"},
                    }
                    for label in labels
                ],
            }
        )
    )
    reservations = []
    for label in labels:
        for task, seed in ((0, 44), (8, 151)):
            reservations.append(
                {
                    "phase": "preflight",
                    "label": f"preflight__{label}",
                    "formal_label": label,
                    "task_id": task,
                    "episode_seed": seed,
                    "config_fingerprint": label,
                    "code_state_sha256": "c" * 64,
                }
            )
    created = runner.append_attempt_records(ledger, reservations)
    with pytest.raises(RuntimeError, match="six preflight attempts"):
        runner.validate_formal_readiness(
            offline_path=offline,
            preflight_audit_path=preflight,
            ledger_path=ledger,
        )
    runner.append_ledger_event(
        ledger,
        {
            "record_type": "phase_dispatch",
            "phase": "preflight",
            "attempt_ids": [row["attempt_id"] for row in created],
        },
    )
    result = runner.validate_formal_readiness(
        offline_path=offline,
        preflight_audit_path=preflight,
        ledger_path=ledger,
    )
    assert result["passed"] is True
    retry_reservations = [
        {
            **record,
            "config_fingerprint": f"{record['formal_label']}-retry",
            "code_state_sha256": "d" * 64,
        }
        for record in reservations
    ]
    retried = runner.append_attempt_records(ledger, retry_reservations)
    runner.append_ledger_event(
        ledger,
        {
            "record_type": "phase_dispatch",
            "phase": "preflight",
            "attempt_ids": [row["attempt_id"] for row in retried],
        },
    )
    payload = json.loads(preflight.read_text())
    for job in payload["jobs"]:
        job["config_fingerprint"] = f"{job['formal_label']}-retry"
        job["code_state_sha256"] = "d" * 64
    preflight.write_text(json.dumps(payload))
    result = runner.validate_formal_readiness(
        offline_path=offline,
        preflight_audit_path=preflight,
        ledger_path=ledger,
    )
    assert result["dispatched_preflight_attempts"] == 12
    assert result["accepted_latest_preflight_attempt_ids"] == list(range(7, 13))
    preflight.write_text(json.dumps({"passed": False}))
    with pytest.raises(RuntimeError, match="preflight audit did not pass"):
        runner.validate_formal_readiness(
            offline_path=offline,
            preflight_audit_path=preflight,
            ledger_path=ledger,
        )


def _write_recovery_artifacts(runner, root, jobs, *, corrupt_label=None):
    stage = root / "libero_preflight"
    log_root = root / "runner_logs" / "libero_preflight"
    failure_root = root / "failures" / "libero_preflight"
    stage.mkdir(parents=True)
    log_root.mkdir(parents=True)
    failure_root.mkdir(parents=True)
    rows = ["job_id,status,exit_code,failure_reason"]
    for job in jobs:
        output = stage / job["label"]
        output.mkdir()
        fingerprint = "a" * 64
        (output / "config_fingerprint.txt").write_text(fingerprint + "\n")
        manifest_label = (
            "wrong-label" if corrupt_label == job["label"] else job["label"]
        )
        (output / "job_manifest.json").write_text(
            json.dumps(
                {
                    "schema": "p2-adaptive-eds-rbf-job-v2",
                    "config_fingerprint": fingerprint,
                    "job": {
                        "label": manifest_label,
                        "formal_label": job["formal_label"],
                        "level": runner.PREFLIGHT_LEVEL,
                        "task_ids_filter": [0, 8],
                        "episode_seeds": [44, 151],
                    },
                }
            )
            + "\n"
        )
        (output / "results.txt").write_text("old failure\n")
        (log_root / f"{job['label']}.log").write_text("old log\n")
        (failure_root / f"{job['label']}.json").write_text(
            json.dumps({"status": "failed", "job_id": job["job_id"]}) + "\n"
        )
        rows.append(f"{job['job_id']},failed,1,pre-dispatch failure")
    (stage / "run_manifest.csv").write_text("\n".join(rows) + "\n")


def test_recovery_archives_consistent_old_fingerprint_artifacts_before_dispatch(
    tmp_path,
):
    runner = _load_runner()
    jobs = [
        {
            "level": runner.PREFLIGHT_LEVEL,
            "label": f"preflight__profile_{index}",
            "formal_label": f"profile_{index}",
            "job_id": f"job-{index}",
            "task_ids_filter": [0, 8],
            "episode_seeds": [44, 151],
            "config_fingerprint": "b" * 64,
        }
        for index in range(3)
    ]
    _write_recovery_artifacts(runner, tmp_path, jobs)

    result = runner.archive_recovery_artifacts(
        jobs,
        real_root=tmp_path,
        timestamp="20260807T060000000000Z",
    )

    archive = Path(result["archive_root"])
    assert archive.is_dir()
    assert result["archived_job_count"] == 3
    assert result["archive_manifest_sha256"]
    assert not (tmp_path / "libero_preflight" / "run_manifest.csv").exists()
    for job in jobs:
        assert not (tmp_path / "libero_preflight" / job["label"]).exists()
        assert not (
            tmp_path / "runner_logs" / "libero_preflight" / f"{job['label']}.log"
        ).exists()
        archived = archive / "jobs" / job["label"]
        assert (archived / "output" / "results.txt").is_file()
        assert (archived / "runner.log").is_file()
        assert (archived / "failure.json").is_file()
    payload = json.loads((archive / "archive_manifest.json").read_text())
    assert payload["schema"] == "eds-qd-recovery-archive-v1"
    assert payload["jobs"][0]["existing_config_fingerprint"] == "a" * 64
    assert payload["jobs"][0]["next_config_fingerprint"] == "b" * 64
    assert payload["status_csv"]["sha256"]


def test_recovery_archive_rejects_inconsistent_identity_without_moving_anything(
    tmp_path,
):
    runner = _load_runner()
    jobs = [
        {
            "level": runner.PREFLIGHT_LEVEL,
            "label": f"preflight__profile_{index}",
            "formal_label": f"profile_{index}",
            "job_id": f"job-{index}",
            "task_ids_filter": [0, 8],
            "episode_seeds": [44, 151],
            "config_fingerprint": "b" * 64,
        }
        for index in range(3)
    ]
    _write_recovery_artifacts(
        runner, tmp_path, jobs, corrupt_label=jobs[-1]["label"]
    )

    with pytest.raises(RuntimeError, match="identity mismatch"):
        runner.archive_recovery_artifacts(
            jobs,
            real_root=tmp_path,
            timestamp="20260807T060000000000Z",
        )

    assert (tmp_path / "libero_preflight" / "run_manifest.csv").is_file()
    assert all(
        (tmp_path / "libero_preflight" / job["label"]).is_dir()
        for job in jobs
    )
    assert not (tmp_path / "stale").exists()


def test_recovery_phase_archives_before_reservation_and_dispatch(tmp_path, monkeypatch):
    runner = _load_runner()
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text("{}\n")
    manifest.chmod(0o444)
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(runner, "RUN_MANIFEST_PATH", manifest)
    monkeypatch.setattr(runner, "ATTEMPT_LEDGER_PATH", ledger)
    monkeypatch.setattr(runner, "storage_preflight", lambda: {})
    monkeypatch.setattr(runner, "validate_runtime_cache", lambda: {})
    monkeypatch.setattr(runner, "validate_runtime_credential", lambda: {})
    monkeypatch.setattr(runner.base, "_poe_healthcheck", lambda: True)
    monkeypatch.setattr(
        runner, "load_gpu_reference", lambda: {"reference_peak_vram_mib": 1.0}
    )
    monkeypatch.setattr(
        runner,
        "admit_gpus",
        lambda **_kwargs: {
            "eligible_gpu_indices": [3],
            "selected_gpu_indices": [3],
        },
    )
    monkeypatch.setattr(runner, "_write_gpu_admission", lambda *_args: tmp_path)
    jobs = [
        {
            "level": runner.PREFLIGHT_LEVEL,
            "label": f"preflight__profile_{index}",
            "formal_label": f"profile_{index}",
            "job_id": f"job-{index}",
            "task_ids_filter": [0, 8],
            "episode_seeds": [44, 151],
            "config_fingerprint": chr(ord("a") + index) * 64,
            "execution_record": {"code_state_sha256": "c" * 64},
        }
        for index in range(3)
    ]
    monkeypatch.setattr(runner, "build_jobs", lambda *_args, **_kwargs: jobs)
    prior = runner.append_attempt_records(
        ledger, runner._attempt_records_for_jobs(jobs, "preflight")
    )
    runner.append_ledger_event(
        ledger,
        {
            "record_type": "phase_dispatch",
            "phase": "preflight",
            "attempt_ids": [row["attempt_id"] for row in prior],
        },
    )
    prior_records = runner._attempt_records_for_jobs(jobs, "preflight")
    interrupted = runner.append_attempt_records(
        ledger,
        [
            {**prior_records[0], "recovery_of_attempt_id": 1},
            {**prior_records[2], "recovery_of_attempt_id": 3},
        ],
    )
    runner.append_ledger_event(
        ledger,
        {
            "record_type": "phase_dispatch",
            "phase": "preflight",
            "attempt_ids": [row["attempt_id"] for row in interrupted],
        },
    )
    order = []
    original_append_attempts = runner.append_attempt_records
    original_append_event = runner.append_ledger_event

    def archive(_jobs):
        order.append("archive")
        return {
            "archive_root": "/shared2/archive",
            "archive_manifest": "/shared2/archive/archive_manifest.json",
            "archive_manifest_sha256": "d" * 64,
            "archived_job_count": 3,
        }

    def append_attempts(path, records):
        order.append("reserve")
        return original_append_attempts(path, records)

    def append_event(path, event):
        if event["record_type"] == "phase_dispatch":
            order.append("dispatch")
        return original_append_event(path, event)

    monkeypatch.setattr(runner, "archive_recovery_artifacts", archive)
    monkeypatch.setattr(runner, "append_attempt_records", append_attempts)
    monkeypatch.setattr(runner, "append_ledger_event", append_event)

    def run_level(*_args, **_kwargs):
        order.append("run")
        return 0

    monkeypatch.setattr(runner.base, "run_level", run_level)

    assert (
        runner._run_phase(
            phase="preflight",
            requested_gpus="auto",
            timeout_seconds=1,
            recovery=True,
        )
        == 0
    )
    assert order == ["archive", "reserve", "dispatch", "run"]
    event = runner.read_attempt_ledger(ledger)[-1]
    assert event["recovery_archive"]["archive_manifest_sha256"] == "d" * 64
    recovered = [
        row
        for row in runner.read_attempt_ledger(ledger)
        if row.get("record_type") == "episode_attempt" and row["attempt_id"] >= 9
    ]
    assert [row["recovery_of_attempt_id"] for row in recovered] == [7, 2, 8, 4, 5, 6]


def test_offline_mechanism_preflight_records_all_profiles_and_passes(tmp_path):
    runner = _load_runner()
    path = tmp_path / "offline.json"

    result = runner.offline_mechanism_preflight(path)

    assert result["passed"] is True
    assert result["evaluation_budget"] == 176
    assert set(result["grid_mapping"]) == {"3x3", "4x4", "5x5"}
    assert len(result["archive_iterations"]) == 10
    assert result["uniform_allocation_passed"] is True
    assert result["sparse_allocation_passed"] is True
    assert result["global_rng_unchanged"] is True
    assert result["control_observer_bitwise_equality"]["passed"] is True
    assert result["zero_spread_bounds"]["passed"] is True
    assert result["nonfinite_fail_closed"]["passed"] is True
    assert result["replacement_and_tie_break"]["passed"] is True
    assert result["fixed_bounds_unchanged"] is True
    assert result["input_checksum"]
    assert json.loads(path.read_text())["passed"] is True


def _gpu(index, *, free=50000, util=0, processes=None, mode="Default"):
    return {
        "index": index,
        "uuid": f"GPU-{index}",
        "name": "GPU",
        "memory_total_mib": 80000,
        "memory_free_mib": free,
        "utilization_percent": util,
        "compute_mode": mode,
        "compute_processes": list(processes or []),
    }


def test_gpu_admission_requires_two_clean_snapshots_and_headroom():
    runner = _load_runner()
    snapshots = iter(
        [
            [_gpu(0), _gpu(1, processes=[{"pid": 9}]), _gpu(8)],
            [_gpu(0), _gpu(1), _gpu(8)],
        ]
    )

    result = runner.admit_gpus(
        reference_peak_vram_mib=30000,
        snapshot_fn=lambda: next(snapshots),
        wait_fn=lambda _seconds: None,
        wait_seconds=0,
    )

    assert result["required_free_vram_mib"] == 37500
    assert result["eligible_gpu_indices"] == [0]
    assert result["max_concurrency"] == 1
    assert result["excluded"]["1"]
    assert result["excluded"]["8"]


def test_gpu_admission_can_pin_gpu5_and_allow_authorized_colocation():
    runner = _load_runner()
    shared = _gpu(
        5,
        free=50000,
        util=100,
        processes=[{"pid": 99, "used_memory_mib": 888}],
    )

    result = runner.admit_gpus(
        reference_peak_vram_mib=30000,
        snapshot_fn=lambda: [_gpu(4), shared, _gpu(6)],
        wait_fn=lambda _seconds: None,
        wait_seconds=0,
        pinned_gpu_index=5,
        allow_external_compute=True,
    )

    assert result["eligible_gpu_indices"] == [5]
    assert result["max_concurrency"] == 1
    assert result["pinned_gpu_index"] == 5
    assert result["external_compute_colocation_authorized"] is True
    assert result["excluded"]["4"] == ["not user-pinned GPU 5"]
    assert result["excluded"]["6"] == ["not user-pinned GPU 5"]


def test_runtime_gpu_probe_only_admits_shared_gpu5_with_vram_headroom(monkeypatch):
    runner = _load_runner()
    monkeypatch.setattr(
        runner,
        "load_gpu_reference",
        lambda: {"required_free_vram_mib": 22401.25},
    )
    monkeypatch.setattr(
        runner,
        "gpu_snapshot",
        lambda: [
            _gpu(4),
            _gpu(
                5,
                free=50000,
                util=100,
                processes=[{"pid": 99, "used_memory_mib": 888}],
            ),
        ],
    )

    assert runner._gpu_probe("5") == ("idle", "admitted shared GPU 5")
    assert runner._gpu_probe("4") == ("busy", "only user-pinned GPU 5 is allowed")


def test_freeze_manifest_is_readonly_contains_provenance_and_is_immutable(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    path = tmp_path / "manifests" / "qd_ed_run_manifest.json"
    monkeypatch.setattr(runner, "RUN_MANIFEST_PATH", path)
    provenance = {
        "base_commit": "b" * 40,
        "source_branch": "exp/eds-init-pg-diverse-sampling",
        "new_branch": "exp/eds-quality-diversity",
        "new_worktree_realpath": "/tmp/worktree",
        "code_commit": "c" * 40,
        "code_state_sha256": "d" * 64,
    }
    storage = {"outputs_target": "/mnt/data/shared2/test"}
    reference = {"reference_peak_vram_mib": 30000}

    result = runner.freeze_run_manifest(
        provenance=provenance,
        storage=storage,
        gpu_reference=reference,
    )

    assert result["formal_episode_count"] == 110
    assert result["preflight_episode_count"] == 6
    assert result["attempt_cap"] == 124
    assert result["recovery_attempt_limit"] == 8
    assert result["pinned_gpu_index"] == 5
    assert result["external_compute_colocation_authorized"] is True
    assert result["provenance"] == provenance
    assert stat.S_IMODE(path.stat().st_mode) == 0o444
    existing = path.read_bytes()
    with pytest.raises(FileExistsError):
        runner.freeze_run_manifest(
            provenance=provenance,
            storage=storage,
            gpu_reference=reference,
        )
    assert path.read_bytes() == existing


def test_runtime_credential_check_reads_environment_without_returning_secret(monkeypatch):
    runner = _load_runner()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-runtime-only")

    result = runner.validate_runtime_credential()

    assert result == {"credential_present": True, "source": "environment"}
    assert "sk-runtime-only" not in json.dumps(result)
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(RuntimeError, match="environment"):
        runner.validate_runtime_credential()
