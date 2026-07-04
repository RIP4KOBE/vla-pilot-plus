import importlib.util
from pathlib import Path


def _load_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "rdt_eds_mechanism_pretest_runner.py"
    spec = importlib.util.spec_from_file_location("rdt_eds_mechanism_pretest_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_pretest_command_targets_libero_object_task1_first_chunk():
    runner = _load_runner()
    cmd = runner.build_pretest_command(reward_mode="normal", output_root=Path("outputs/pretest"))

    assert "policy.type=rdt" in cmd
    assert "backend.libero.suite_name=libero_object" in cmd
    assert "backend.libero.task_ids_filter=[1]" in cmd
    assert "main.episode_num=1" in cmd
    assert "main.guidance_type=eds" in cmd
    assert "main.eds_config.population_size=16" in cmd
    assert "main.eds_config.cem_iters=10" in cmd
    assert "main.eds_eval.reward_mode=normal" in cmd
    assert "main.eds_mechanism_pretest.enabled=true" in cmd
    assert "main.eds_mechanism_pretest.first_chunk_only=true" in cmd
    assert "main.eds_mechanism_pretest.output_dir=outputs/pretest" in cmd


def test_build_control_commands_include_zero_and_inverted_only():
    runner = _load_runner()
    commands = runner.build_control_commands(output_root=Path("outputs/pretest"))
    joined = [" ".join(cmd) for cmd in commands]

    assert any("main.eds_eval.reward_mode=zero" in item for item in joined)
    assert any("main.eds_eval.reward_mode=inverted" in item for item in joined)
    assert not any("shuffled_keypoints" in item for item in joined)


def test_build_pretest_command_can_enable_rbf_diverse_initial_sampler():
    runner = _load_runner()

    cmd = runner.build_pretest_command(
        reward_mode="normal",
        output_root=Path("outputs/pretest"),
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=1.0,
        initial_diversity_start_ratio=None,
    )

    assert "main.eds_config.initial_sampling_mode=rbf_diverse_denoise" in cmd
    assert "main.eds_config.initial_diversity_scale=1.0" in cmd
    assert "main.eds_config.initial_diversity_start_ratio=null" in cmd
