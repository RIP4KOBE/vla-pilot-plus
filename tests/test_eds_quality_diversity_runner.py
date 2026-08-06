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


def test_attempt_ledger_is_append_only_and_enforces_shared_120_cap(tmp_path):
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

    before = ledger.read_bytes()
    parsed = runner.read_attempt_ledger(ledger)
    assert len(parsed) == 116
    assert [row["attempt_id"] for row in parsed] == list(range(1, 117))
    with pytest.raises(RuntimeError, match="120"):
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
                for index in range(5)
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
    assert result["attempt_cap"] == 120
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
