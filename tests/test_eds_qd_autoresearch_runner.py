from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_runner():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eds_qd_autoresearch_runner.py"
    )
    spec = importlib.util.spec_from_file_location("eds_qd_autoresearch_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_profiles_have_one_candidate_difference_from_sparse_reference():
    runner = _load_runner()
    profiles = runner.profiles()

    assert [profile["label"] for profile in profiles] == [
        "p2_stage_on_abs_rbf_control",
        "eds_quality_diversity_sparse_primary",
        "eds_quality_diversity_sparse_causal_envelope_v1",
    ]
    reference, candidate = profiles[1:]
    differences = sorted(
        key
        for key in set(reference) | set(candidate)
        if key not in {"method", "label", "role"}
        and reference.get(key) != candidate.get(key)
    )
    assert differences == ["qd_bounds_update_policy"]
    assert reference["qd_bounds_update_policy"] == "fixed_initial"
    assert candidate["qd_bounds_update_policy"] == "causal_envelope_v1"
    assert all("p2_render_gpu_index" not in profile for profile in profiles)


def test_phase_matrices_are_exact_and_have_no_formal_phase():
    runner = _load_runner()
    preflight = runner.build_jobs(runner.MECHANISM_PREFLIGHT_LEVEL, bind=False)
    dev_a = runner.build_jobs(runner.DEV_A_LEVEL, bind=False)

    assert [job["formal_label"] for job in preflight] == [
        "p2_stage_on_abs_rbf_control",
        "eds_quality_diversity_sparse_primary",
        "eds_quality_diversity_sparse_causal_envelope_v1",
    ]
    assert all(job["task_ids_filter"] == [3, 5] for job in preflight)
    assert all(job["episode_seeds"] == [512905, 150741] for job in preflight)
    assert all(job["max_chunks"] == 2 for job in preflight)
    assert [job["formal_label"] for job in dev_a] == [
        "p2_stage_on_abs_rbf_control",
        "eds_quality_diversity_sparse_causal_envelope_v1",
    ]
    assert all(job["task_ids_filter"] == [3, 5, 8, 9] for job in dev_a)
    assert all(
        job["episode_seeds"] == [512905, 150741, 463456, 452903]
        for job in dev_a
    )
    with pytest.raises(ValueError, match="phase"):
        runner.build_jobs("formal", bind=False)


def test_candidate_command_has_unique_bounds_policy_and_preflight_limit():
    runner = _load_runner()
    candidate = runner.build_jobs(
        runner.MECHANISM_PREFLIGHT_LEVEL, bind=False
    )[-1]

    command = runner._build_main_command(candidate, "4", 100)
    override_keys = [
        token.split("=", 1)[0].lstrip("+") for token in command if "=" in token
    ]

    assert len(override_keys) == len(set(override_keys))
    assert (
        "main.eds_config.qd_bounds_update_policy=causal_envelope_v1" in command
    )
    assert "main.eds_mechanism_pretest.enabled=true" in command
    assert "main.eds_mechanism_pretest.max_chunks=2" in command


def test_pause_and_storage_preflight_are_fail_closed(tmp_path):
    runner = _load_runner()
    experiment_root = tmp_path / "owned"
    experiment_root.mkdir()
    output_link = tmp_path / "outputs"
    output_link.symlink_to(experiment_root, target_is_directory=True)
    pause = tmp_path / "PAUSE"

    result = runner.storage_preflight(
        experiment_root=experiment_root,
        output_link=output_link,
        allowed_prefix=tmp_path,
        minimum_free_bytes=1,
    )
    assert result["passed"] is True
    runner.pause_preflight(pause)
    pause.write_text("pause\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="paused"):
        runner.pause_preflight(pause)


def test_attempt_ledger_enforces_global_cap_and_exact_identity(tmp_path):
    runner = _load_runner()
    path = tmp_path / "attempts.jsonl"
    records = [
        {
            "phase": "dev_a",
            "label": "candidate",
            "task_id": index,
            "episode_seed": 100 + index,
            "config_fingerprint": "cfg",
            "code_state_sha256": "code",
        }
        for index in range(2)
    ]

    reserved = runner.reserve_attempts(path, records, cap=2)
    assert [row["attempt_id"] for row in reserved] == [1, 2]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    with pytest.raises(RuntimeError, match="cap"):
        runner.reserve_attempts(path, records[:1], cap=2)
    parsed = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [(row["task_id"], row["episode_seed"]) for row in parsed] == [
        (0, 100),
        (1, 101),
    ]


def test_attempt_ledger_rejects_implicit_same_cell_recovery(tmp_path):
    runner = _load_runner()
    path = tmp_path / "attempts.jsonl"
    record = {
        "phase": "dev_a",
        "label": "candidate",
        "formal_label": "candidate",
        "task_id": 3,
        "episode_seed": 512905,
        "config_fingerprint": "cfg",
        "code_state_sha256": "code",
    }

    runner.reserve_attempts(path, [record])
    with pytest.raises(RuntimeError, match="protocol-audited"):
        runner.reserve_attempts(path, [record])


def test_artifact_and_credential_audits_fail_closed(tmp_path, monkeypatch):
    runner = _load_runner()
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "safe.json").write_text('{"ok": true}\n', encoding="utf-8")
    inventory = runner.artifact_inventory(root)
    assert inventory["file_count"] == 1
    assert runner.credential_tree_audit(root)["passed"] is True

    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret-value")
    (root / "leak.log").write_text("unit-test-secret-value\n", encoding="utf-8")
    assert runner.credential_tree_audit(root)["passed"] is False

    link = root / "forbidden-link"
    link.symlink_to(root / "safe.json")
    with pytest.raises(RuntimeError, match="symlinked"):
        runner.artifact_inventory(root)


def test_gpu_admission_uses_only_idle_authorized_indices():
    runner = _load_runner()
    snapshots = iter(
        [
            [
                {
                    "index": 4,
                    "uuid": "GPU-4",
                    "name": "gpu",
                    "memory_total_mib": 80000,
                    "memory_free_mib": 79000,
                    "utilization_percent": 0,
                    "compute_mode": "Default",
                    "compute_processes": [],
                },
                {
                    "index": 8,
                    "uuid": "GPU-8",
                    "name": "gpu",
                    "memory_total_mib": 80000,
                    "memory_free_mib": 79000,
                    "utilization_percent": 0,
                    "compute_mode": "Default",
                    "compute_processes": [],
                },
            ],
            [
                {
                    "index": 4,
                    "uuid": "GPU-4",
                    "name": "gpu",
                    "memory_total_mib": 80000,
                    "memory_free_mib": 79000,
                    "utilization_percent": 0,
                    "compute_mode": "Default",
                    "compute_processes": [],
                },
                {
                    "index": 8,
                    "uuid": "GPU-8",
                    "name": "gpu",
                    "memory_total_mib": 80000,
                    "memory_free_mib": 79000,
                    "utilization_percent": 0,
                    "compute_mode": "Default",
                    "compute_processes": [],
                },
            ],
        ]
    )

    result = runner.admit_gpus(
        reference_peak_vram_mib=20000,
        snapshot_fn=lambda: next(snapshots),
        wait_fn=lambda _: None,
        wait_seconds=0,
    )

    assert result["eligible_gpu_indices"] == [4]
    assert "8" in result["excluded"]
