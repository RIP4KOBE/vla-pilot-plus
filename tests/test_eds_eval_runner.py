import importlib.util
from pathlib import Path


def _load_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "rdt_eds_eval_runner.py"
    spec = importlib.util.spec_from_file_location("rdt_eds_eval_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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
    }
    assert len(jobs) == 18


def test_level2_smoke_uses_libero_object_and_required_ablations():
    runner = _load_runner()

    jobs = runner.build_jobs("level2", episodes=3)
    labels = {job["label"] for job in jobs}

    assert {job["suite"] for job in jobs} == {"libero_object"}
    assert labels == {"unguided", "p16_c10", "zero", "shuffled", "inverted"}

    cmd = runner.build_main_command(jobs[0], gpu="0", timeout_seconds=120)
    assert "backend.libero.task_ids_filter=[0]" in cmd


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


def test_level_report_names_match_protocol():
    runner = _load_runner()

    assert runner.LEVEL_REPORTS["level0"] == "level_0_deployment_correctness.md"
    assert runner.LEVEL_REPORTS["level1"] == "level_1_mechanism_probe.md"
    assert runner.LEVEL_REPORTS["level2"] == "level_2_online_smoke.md"
    assert runner.LEVEL_REPORTS["level3"] == "level_3_libero_object_success.md"
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
