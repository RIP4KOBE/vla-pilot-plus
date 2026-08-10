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
        / "eds_qd_stage_guidance_transition_runner.py"
    )
    spec = importlib.util.spec_from_file_location(
        "eds_qd_stage_guidance_transition_runner", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_formal_matrix_is_exactly_four_frozen_paired_jobs():
    runner = _load_runner()

    profiles = runner.formal_profiles()
    jobs = runner.build_jobs(runner.FORMAL_LEVEL, 10)

    assert [profile["label"] for profile in profiles] == [
        "eds_qd_uniform_expand20_p48_k20_transition_legacy_r0",
        "eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r0",
        "eds_qd_uniform_expand20_p48_k20_transition_legacy_r1",
        "eds_qd_uniform_expand20_p48_k20_transition_fsm_v1_r1",
    ]
    assert len(jobs) == runner.FORMAL_JOB_COUNT == 4
    assert sum(job["episodes"] for job in jobs) == runner.FORMAL_EPISODE_COUNT == 40
    assert {job["population_size"] for job in jobs} == {48}
    assert {job["cem_iters"] for job in jobs} == {20}
    assert {job["num_elites"] for job in jobs} == {16}
    assert {job["use_cem"] for job in jobs} == {False}
    assert {job["expected_evaluations_per_complete_chunk"] for job in jobs} == {1008}
    assert [job["round"] for job in jobs] == [0, 0, 1, 1]
    assert [job["transition_mode"] for job in jobs] == [
        "legacy_vlm",
        "physical_fsm_v1",
        "legacy_vlm",
        "physical_fsm_v1",
    ]
    assert jobs[0]["episode_seeds"] == jobs[1]["episode_seeds"] == runner.ROUND_SEEDS[0]
    assert jobs[2]["episode_seeds"] == jobs[3]["episode_seeds"] == runner.ROUND_SEEDS[1]
    assert runner.ROUND_SEEDS[1] == [value + 1000 for value in runner.ROUND_SEEDS[0]]
    with pytest.raises(ValueError, match="4-job"):
        runner.build_jobs("other", 10)
    with pytest.raises(ValueError, match="4-job"):
        runner.build_jobs(runner.FORMAL_LEVEL, 1)


def test_command_freezes_transition_round_seed_qd_and_has_no_credential(monkeypatch):
    runner = _load_runner()
    monkeypatch.setenv("OPENAI_API_KEY", "REDACTED")
    jobs = runner.build_jobs(runner.FORMAL_LEVEL, 10)
    legacy = runner._build_main_command(jobs[0], "4", 1)
    fsm = runner._build_main_command(jobs[3], "4", 1)

    for command in (legacy, fsm):
        assert "main.eds_config.population_size=48" in command
        assert "main.eds_config.cem_iters=20" in command
        assert "main.eds_config.num_elites=16" in command
        assert "main.eds_config.use_cem=false" in command
        assert "backend.libero.suite_name=libero_object_swap" in command
        assert "backend.libero.strict_perturbations=true" in command
        assert "REDACTED" not in " ".join(command)
        assert "OPENAI_API_KEY" not in " ".join(command)
    assert "main.stage_transition_mode=legacy_vlm" in legacy
    assert "seed=0" in legacy
    assert "main.stage_transition_mode=physical_fsm_v1" in fsm
    assert "seed=1" in fsm
    assert "main.physical_fsm.grasp_confirm_steps=4" in fsm
    assert "main.physical_fsm.drop_confirm_steps=3" in fsm
    assert "main.physical_fsm.release_verify_timeout_steps=8" in fsm


def test_storage_namespace_uses_direct_approved_root_and_nested_output_symlink(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    shared2 = tmp_path / "shared2"
    namespace = shared2 / runner.NAMESPACE
    namespace.mkdir(parents=True)
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    root_link = worktree / "outputs"
    root_link.symlink_to(namespace.absolute(), target_is_directory=True)
    target = namespace / "output_store"
    nested_link = root_link / "output_store_link"

    monkeypatch.setattr(runner, "WORKTREE_ROOT", worktree)
    monkeypatch.setattr(runner, "ROOT_OUTPUT_LINK", root_link)
    monkeypatch.setattr(runner, "EXPERIMENT_ROOT", namespace)
    monkeypatch.setattr(runner, "OUTPUT_TARGET", target)
    monkeypatch.setattr(runner, "OUTPUT_LINK", nested_link)
    monkeypatch.setattr(runner, "ALLOWED_STORAGE_PREFIX", shared2)
    monkeypatch.setattr(runner, "MIN_FREE_BYTES", 1)

    initialized = runner.initialize_storage()
    checked = runner.storage_preflight()

    assert initialized["namespace_realpath"] == str(namespace.resolve())
    assert checked["outputs_target"] == str(target.resolve())
    assert root_link.resolve() == namespace.resolve()
    assert nested_link.is_symlink()
    assert nested_link.resolve() == target.resolve()


def test_gpu_admission_requires_two_strictly_idle_samples():
    runner = _load_runner()
    calls = 0

    def snapshot():
        nonlocal calls
        calls += 1
        devices = []
        for index in range(8):
            devices.append(
                {
                    "index": index,
                    "uuid": f"gpu-{index}",
                    "name": "H200",
                    "memory_total_mib": 143771,
                    "memory_free_mib": 143770,
                    "utilization_percent": 0,
                    "compute_mode": "Default",
                    "compute_processes": [],
                }
            )
        devices[0]["compute_processes"] = [{"pid": 1, "used_memory_mib": 1}]
        devices[1]["utilization_percent"] = 10
        if calls == 2:
            devices[2]["compute_processes"] = [{"pid": 2, "used_memory_mib": 1}]
        return devices

    admission = runner.admit_gpus(
        reference_peak_vram_mib=50000,
        snapshot_fn=snapshot,
        wait_fn=lambda _: None,
    )

    assert admission["eligible_gpu_indices"] == [3, 4, 5, 6, 7]
    assert admission["external_compute_colocation_authorized"] is False
    assert admission["strict_idle_required"] is True
    assert admission["allowed_gpu_indices"] == list(range(8))


def test_attempt_ledger_hard_cap_is_40_plus_four(tmp_path):
    runner = _load_runner()
    ledger = tmp_path / "ledger.jsonl"
    jobs = runner.build_jobs(runner.FORMAL_LEVEL, 10)
    formal = runner._attempt_records_for_jobs(jobs, "formal")
    runner.append_attempt_records(ledger, formal)
    runner.append_attempt_records(
        ledger,
        [
            {**formal[index], "phase": "retry", "recovery_of_attempt_id": index + 1}
            for index in range(4)
        ],
    )
    assert runner.attempt_ledger_state(ledger)["active_reservation_count"] == 44
    with pytest.raises(RuntimeError, match="44"):
        runner.append_attempt_records(ledger, [{**formal[0], "phase": "retry"}])


def test_retry_cells_are_registered_unique_and_limited_to_four():
    runner = _load_runner()
    label = runner.formal_profiles()[0]["label"]

    selected = runner.select_retry_cells([(label, 0), (label, 9)])

    assert [(item["formal_label"], item["task_id"]) for item in selected] == [
        (label, 0),
        (label, 9),
    ]
    assert selected[0]["episode_seed"] == runner.ROUND_SEEDS[0][0]
    assert selected[1]["episode_seed"] == runner.ROUND_SEEDS[0][9]
    assert all(item["profile_fingerprint"] == selected[0]["profile_fingerprint"] for item in selected)
    with pytest.raises(ValueError, match="at most four"):
        runner.select_retry_cells([(label, index) for index in range(5)])
    with pytest.raises(ValueError, match="registered"):
        runner.select_retry_cells([("unknown", 0)])
    with pytest.raises(ValueError, match="unique"):
        runner.select_retry_cells([(label, 0), (label, 0)])


def test_retry_job_is_one_exact_same_seed_cell_in_separate_namespace():
    runner = _load_runner()
    label = runner.formal_profiles()[1]["label"]
    selected = runner.select_retry_cells([(label, 3)])

    job = runner._retry_jobs(selected, first_attempt_id=41)[0]
    command = runner._build_main_command(job, "4", 1)

    assert job["level"] == runner.RETRY_LEVEL
    assert job["episode_start_index"] == 3
    assert job["episode_stop_index"] == 4
    assert job["episode_seeds"] == runner.ROUND_SEEDS[0]
    assert runner.base._p2_expected_episode_ids(job) == {3}
    assert "+main.episode_start_index=3" in command
    assert "+main.episode_stop_index=4" in command
    assert f"main.eds_eval.method_label={label}" in command
    assert any("/retry/" in token for token in command)


def test_retry_jsonl_merge_replaces_only_selected_episode(tmp_path):
    runner = _load_runner()
    formal = tmp_path / "formal.jsonl"
    retry = tmp_path / "retry.jsonl"
    archive = tmp_path / "archive"
    archive.mkdir()
    formal.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {"episode": 0, "global_step": 1, "value": "old-0"},
                {"episode": 1, "global_step": 1, "value": "old-1"},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    retry.write_text(
        json.dumps({"episode": 1, "global_step": 1, "value": "new-1"}) + "\n",
        encoding="utf-8",
    )

    runner._merge_retry_jsonl(
        formal_path=formal, retry_path=retry, episode=1, archive_root=archive
    )

    rows = [json.loads(line) for line in formal.read_text().splitlines()]
    assert [row["value"] for row in rows] == ["old-0", "new-1"]
    assert (archive / "formal.jsonl").is_file()


def test_dimension_probe_is_static_and_consumes_zero_episodes(tmp_path, monkeypatch):
    runner = _load_runner()
    output = tmp_path / "dimension_probe.json"
    monkeypatch.setattr(runner, "DIMENSION_PROBE_PATH", output)

    payload = runner.run_dimension_probe()

    assert payload["passed"] is True
    assert payload["formal_episodes_consumed"] == 0
    assert payload["panda_gripper"]["maximum_aperture_m"] == pytest.approx(0.08)
    assert payload["keypoint_resolver"]["target_keypoint_index"] == 0
    assert payload["keypoint_resolver"]["destination_keypoint_index"] == 1
    assert output.is_file()


def test_run_manifest_freezes_seeds_matrix_thresholds_and_is_read_only(
    tmp_path, monkeypatch
):
    runner = _load_runner()
    design = tmp_path / "design.md"
    design.write_text("approved\n", encoding="utf-8")
    probe = tmp_path / "dimension_probe.json"
    probe.write_text(json.dumps({"passed": True}), encoding="utf-8")
    manifest = tmp_path / "run_manifest.json"
    monkeypatch.setattr(runner, "DESIGN_PATH", design)
    monkeypatch.setattr(runner, "DIMENSION_PROBE_PATH", probe)
    monkeypatch.setattr(runner, "RUN_MANIFEST_PATH", manifest)

    payload = runner.freeze_run_manifest(
        provenance={"branch": runner.TARGET_BRANCH, "code_commit": "a" * 40},
        storage={"passed": True},
        gpu_reference={"reference_peak_vram_mib": 50000},
        test_evidence={"passed": True, "tests": 100},
    )

    assert payload["formal_job_count"] == 4
    assert payload["formal_episode_count"] == 40
    assert payload["attempt_cap"] == 44
    assert payload["round_seeds"] == {"0": runner.ROUND_SEEDS[0], "1": runner.ROUND_SEEDS[1]}
    assert payload["fsm_thresholds"] == runner.FSM_THRESHOLDS
    assert stat.S_IMODE(manifest.stat().st_mode) == 0o444
