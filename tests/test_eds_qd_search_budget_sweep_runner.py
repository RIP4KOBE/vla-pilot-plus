from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path

import pytest


def _load_runner():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eds_qd_search_budget_sweep_runner.py"
    )
    spec = importlib.util.spec_from_file_location(
        "eds_qd_search_budget_sweep_runner", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_formal_matrix_is_exact_2x3x3_without_extra_jobs():
    runner = _load_runner()

    profiles = runner.formal_profiles()
    jobs = runner.build_jobs(runner.FORMAL_LEVEL, 10)

    assert len(profiles) == len(jobs) == 18
    assert [profile["label"] for profile in profiles] == [
        f"eds_qd_{family}_p{population}_k{iterations}"
        for family in ("uniform_expand20", "sparse_primary")
        for population in (32, 48, 64)
        for iterations in (15, 20, 25)
    ]
    assert {
        (job["family"], job["population_size"], job["cem_iters"])
        for job in jobs
    } == {
        (family, population, iterations)
        for family in ("uniform_expand20", "sparse_primary")
        for population in (32, 48, 64)
        for iterations in (15, 20, 25)
    }
    assert {job["num_elites"] for job in jobs} == {16}
    assert {job["use_cem"] for job in jobs} == {False}
    assert {tuple(job["task_ids_filter"]) for job in jobs} == {tuple(range(10))}
    assert {tuple(job["episode_seeds"]) for job in jobs} == {
        tuple(runner.EPISODE_SEEDS)
    }
    assert sum(int(job["episodes"]) for job in jobs) == 180
    with pytest.raises(ValueError, match="18-job formal matrix"):
        runner.build_jobs("control", 10)
    with pytest.raises(ValueError, match="18-job formal matrix"):
        runner.build_jobs(runner.FORMAL_LEVEL, 2)


def test_family_profiles_only_change_approved_budget_and_family_fields():
    runner = _load_runner()
    profiles = runner.formal_profiles()

    uniform = [profile for profile in profiles if profile["family"] == "uniform_expand20"]
    sparse = [profile for profile in profiles if profile["family"] == "sparse_primary"]

    assert {profile["qd_parent_sampling"] for profile in uniform} == {
        "uniform_cells"
    }
    assert {profile["qd_bounds_expand_fraction"] for profile in uniform} == {0.20}
    assert {profile["qd_parent_sampling"] for profile in sparse} == {
        "sparse_priority"
    }
    assert {profile["qd_bounds_expand_fraction"] for profile in sparse} == {0.10}
    assert all("p2_render_gpu_index" not in profile for profile in profiles)
    assert all(profile["qd_grid_shape"] == [4, 4] for profile in profiles)
    assert all(profile["qd_cell_capacity"] == 1 for profile in profiles)


def test_command_contains_exact_budget_qd_and_no_credential(monkeypatch):
    runner = _load_runner()
    monkeypatch.setenv("OPENAI_API_KEY", "REDACTED")
    job = next(
        job
        for job in runner.build_jobs(runner.FORMAL_LEVEL, 10)
        if job["label"] == "eds_qd_sparse_primary_p64_k25"
    )

    command = runner._build_main_command(job, "7", 10)
    text = " ".join(command)

    assert "main.eds_config.population_size=64" in command
    assert "main.eds_config.cem_iters=25" in command
    assert "main.eds_config.num_elites=16" in command
    assert "main.eds_config.use_cem=false" in command
    assert "main.eds_config.qd_parent_sampling=sparse_priority" in command
    assert "main.eds_config.qd_bounds_expand_fraction=0.1" in command
    assert "backend.libero.suite_name=libero_object_swap" in command
    assert "backend.libero.strict_perturbations=true" in command
    assert "REDACTED" not in text
    assert "OPENAI_API_KEY" not in text


@pytest.mark.parametrize(
    ("population", "iterations", "expected"),
    [
        (32, 15, 512),
        (32, 20, 672),
        (32, 25, 832),
        (48, 15, 768),
        (48, 20, 1008),
        (48, 25, 1248),
        (64, 15, 1024),
        (64, 20, 1344),
        (64, 25, 1664),
    ],
)
def test_parameterized_complete_chunk_evaluation_budget(
    population, iterations, expected
):
    runner = _load_runner()
    assert runner.expected_evaluations(population, iterations) == expected


def test_storage_namespace_is_reached_only_through_shared2_symlink(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    shared2 = tmp_path / "shared2"
    legacy_target = shared2 / "eds-quality-diversity" / "outputs"
    legacy_target.mkdir(parents=True)
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    root_link = worktree / "outputs"
    root_link.symlink_to(legacy_target.absolute(), target_is_directory=True)
    experiment_root = legacy_target / runner.NAMESPACE
    output_target = experiment_root / "output_store"
    output_link = root_link / runner.NAMESPACE / "outputs"

    monkeypatch.setattr(runner, "ROOT_OUTPUT_LINK", root_link)
    monkeypatch.setattr(runner, "LEGACY_OUTPUT_TARGET", legacy_target)
    monkeypatch.setattr(runner, "EXPERIMENT_ROOT", experiment_root)
    monkeypatch.setattr(runner, "OUTPUT_TARGET", output_target)
    monkeypatch.setattr(runner, "OUTPUT_LINK", output_link)
    monkeypatch.setattr(runner, "ALLOWED_STORAGE_PREFIX", shared2)
    monkeypatch.setattr(runner, "MIN_FREE_BYTES", 1)

    initialized = runner.initialize_storage()
    checked = runner.storage_preflight()

    assert initialized["outputs_target"] == str(output_target.resolve())
    assert checked["namespace_realpath"] == str(experiment_root.resolve())
    assert output_link.is_symlink()
    assert output_link.resolve() == output_target.resolve()
    assert root_link.is_symlink()


def test_gpu_admission_allows_external_compute_on_any_0_to_7():
    runner = _load_runner()

    def snapshot():
        return [
            {
                "index": index,
                "uuid": f"gpu-{index}",
                "name": "H200",
                "memory_total_mib": 143771,
                "memory_free_mib": 120000 - index,
                "utilization_percent": 100 if index == 3 else 0,
                "compute_mode": "Default",
                "compute_processes": (
                    [{"pid": 1000 + index, "used_memory_mib": 1000}]
                    if index in {0, 3}
                    else []
                ),
            }
            for index in range(8)
        ]

    admission = runner.admit_gpus(
        reference_peak_vram_mib=runner.SCALED_REFERENCE_PEAK_VRAM_MIB,
        snapshot_fn=snapshot,
        wait_fn=lambda _: None,
    )

    assert admission["eligible_gpu_indices"] == list(range(8))
    assert admission["external_compute_colocation_authorized"] is True
    assert admission["max_concurrency"] == 4


def test_attempt_ledger_enforces_180_formal_plus_20_recovery_cap(tmp_path):
    runner = _load_runner()
    ledger = tmp_path / "ledger.jsonl"
    formal = [
        {
            "phase": "formal",
            "label": f"job-{index // 10}",
            "task_id": index % 10,
            "episode_seed": index,
            "config_fingerprint": "a" * 64,
        }
        for index in range(180)
    ]
    runner.append_attempt_records(ledger, formal)
    runner.append_attempt_records(
        ledger,
        [
            {
                **formal[index],
                "phase": "retry",
            }
            for index in range(20)
        ],
    )

    assert len(
        [
            row
            for row in runner.read_attempt_ledger(ledger)
            if row.get("record_type") == "episode_attempt"
        ]
    ) == 200
    with pytest.raises(RuntimeError, match="200"):
        runner.append_attempt_records(ledger, [formal[0]])


def test_recovery_selection_is_same_config_and_at_most_two_full_jobs():
    runner = _load_runner()
    labels = [
        "eds_qd_uniform_expand20_p32_k15",
        "eds_qd_sparse_primary_p64_k25",
    ]

    jobs = runner.select_recovery_jobs(labels)

    assert [job["label"] for job in jobs] == labels
    assert sum(job["episodes"] for job in jobs) == 20
    assert all(job["level"] == runner.FORMAL_LEVEL for job in jobs)
    with pytest.raises(ValueError, match="at most two"):
        runner.select_recovery_jobs(
            labels + ["eds_qd_uniform_expand20_p48_k20"]
        )
    with pytest.raises(ValueError, match="registered formal label"):
        runner.select_recovery_jobs(["new_unregistered_job"])


def test_manifest_freezes_only_18_formal_jobs_and_no_preflight(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    design = tmp_path / "design.md"
    design.write_text("approved\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    no_op = tmp_path / "no_op.json"
    no_op.write_text(json.dumps({"passed": True}), encoding="utf-8")
    monkeypatch.setattr(runner, "DESIGN_PATH", design)
    monkeypatch.setattr(runner, "RUN_MANIFEST_PATH", manifest)
    monkeypatch.setattr(runner, "NO_OP_AUDIT_PATH", no_op)

    payload = runner.freeze_run_manifest(
        provenance={"code_commit": "a" * 40},
        storage={"outputs_target": "/shared2/output"},
        gpu_reference={"reference_peak_vram_mib": 1.0},
    )

    assert payload["formal_job_count"] == 18
    assert payload["formal_episode_count"] == 180
    assert payload["preflight_episode_count"] == 0
    assert payload["recovery_attempt_limit"] == 20
    assert payload["attempt_cap"] == 200
    assert len(payload["formal_profiles"]) == 18
    assert "preflight_profiles" not in payload
    assert stat.S_IMODE(manifest.stat().st_mode) & 0o222 == 0
