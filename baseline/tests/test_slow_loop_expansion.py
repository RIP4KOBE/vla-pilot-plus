import copy
from pathlib import Path

import pytest
import torch
from safetensors.torch import save_file

from baseline.config import METHODS, load_config
from baseline.io import read_json, write_json
from baseline.slow_loop_metrics import continual_report, summarize_episodes
from baseline.slow_loop_train import CoFTInputView
from baseline.references.slow_loop_main_20260914.checkpoint_math import (
    CheckpointView, compose_policy, extract_full_delta, verify_full_delta_reconstruction)
from baseline.references.slow_loop_main_20260914.candidates import DeltaLineageEntry, compose_expansion_candidates
from baseline.references.slow_loop_main_20260914.training import SourceAwareSampler


def checkpoint(root, offset=0):
    root.mkdir()
    weights = {
        "model.paligemma.model.vision_tower.weight": torch.tensor([1., 2.]) + offset,
        "model.paligemma.model.language_model.weight": torch.tensor([3., 4.]) + offset,
        "model.action_out_proj.weight": torch.tensor([5., 6.]) + offset,
        "counter": torch.tensor([3], dtype=torch.int64),
    }
    save_file(weights, str(root / "model.safetensors"))
    write_json(root / "config.json", {"type": "pi05"})
    return weights


def test_two_expansions_use_uniform_point_eight_and_preserve_prior_lineage(tmp_path):
    base, ft1, delta1 = tmp_path / "base", tmp_path / "ft1", tmp_path / "delta1"
    initial = checkpoint(base)
    checkpoint(ft1, 1)
    extract_full_delta(base, ft1, delta1, parent_policy_id="v44")
    assert verify_full_delta_reconstruction(base, delta1, ft1)["passed"]
    grid = compose_expansion_candidates(theta0_checkpoint=base, parent_policy_id="v44", accepted_lineage=[],
              new_delta_id="first", new_delta_path=delta1, output_root=tmp_path / "merged1", alpha_l_values=[.8])
    first = grid["candidates"][0]
    parent = Path(first["checkpoint_path"])
    with CheckpointView(parent) as view:
        for key in initial:
            torch.testing.assert_close(view.tensor(key), initial[key] + .8 if initial[key].is_floating_point() else initial[key])
    ft2 = tmp_path / "ft2"
    ft2.mkdir()
    with CheckpointView(parent) as view:
        values = {key: view.tensor(key) + 2 if view.tensor(key).is_floating_point() else view.tensor(key) for key in view.keys}
    save_file(values, str(ft2 / "model.safetensors"))
    delta2 = tmp_path / "delta2"
    extract_full_delta(parent, ft2, delta2, parent_policy_id=first["policy_id"])
    lineage = [DeltaLineageEntry(**x) for x in read_json(parent / "candidate.json")["lineage"]]
    second = compose_expansion_candidates(theta0_checkpoint=base, parent_policy_id=first["policy_id"], accepted_lineage=lineage,
             new_delta_id="second", new_delta_path=delta2, output_root=tmp_path / "merged2", alpha_l_values=[.8])
    assert len(second["candidates"]) == 1
    with CheckpointView(Path(second["candidates"][0]["checkpoint_path"])) as view:
        for key in initial:
            torch.testing.assert_close(view.tensor(key), initial[key] + 2.4 if initial[key].is_floating_point() else initial[key])
    assert second["candidates"][0]["alpha_map"] == {k: .8 for k in ("vision", "language", "action")}


def summary(rates):
    return {"per_task_success": rates, "per_variant": {}}


def test_forgetting_matrix_keeps_future_cells_missing_and_handles_positive_bwt():
    report = continual_report(["a", "b", "c"], [summary({"a": .5}), summary({"a": 1., "b": .5}),
                                                  summary({"a": .5, "b": 1., "c": 0.})])
    assert report["matrix"][:2] == [[.5, None, None], [1., .5, None]]
    assert report["stages"][0]["forgetting"] is None
    assert report["stages"][1]["backward_transfer"] == .5
    assert report["latest"]["forgetting"] == .25
    assert report["latest"]["backward_transfer"] == .25


@pytest.mark.parametrize("rates", [{"b": .5}, {"a": .5, "b": .5}, {"a": float('nan')}, {"a": 1.1}])
def test_invalid_or_future_task_results_do_not_enter_matrix(rates):
    with pytest.raises(ValueError):
        continual_report(["a", "b"], [summary(rates)])


def test_eval_summary_requires_complete_exact_paired_contexts():
    contexts = [{"task_key": "a", "init_state_id": i, "seed": 7 + i,
                 "split": "fixed_development_probe", "perturbation_variant": "use_swap"} for i in (40, 41)]
    rows = [{"context": c, "success": i == 0} for i, c in enumerate(contexts)]
    result = summarize_episodes(rows, contexts)
    assert result["per_variant"]["use_swap"] == {"successes": 1, "episodes": 2, "success_rate": .5}
    for invalid in [rows[:1], rows[::-1], [rows[0], rows[0]]]:
        with pytest.raises(ValueError):
            summarize_episodes(invalid, contexts)


@pytest.mark.parametrize("has_old,counts", [(False, (16, 0, 16)), (True, (16, 8, 8))])
def test_main_source_sampler_keeps_exact_ratios_and_resume_offset(has_old, counts):
    args = dict(new_indices=[0, 1], old_ticket_indices={"old": [2, 3]} if has_old else {},
                replay_indices=[4, 5], num_samples=32, seed=3)
    draws = list(SourceAwareSampler(**args))
    assert tuple(sum((x < 2 if role == 0 else 2 <= x < 4 if role == 1 else x >= 4) for x in draws) for role in range(3)) == counts
    assert list(SourceAwareSampler(**args, start_index=8)) == draws[8:]


def test_replay_view_preserves_native_orientation_state_and_actions():
    pixels = torch.tensor([[10, 20], [30, 40]], dtype=torch.float32).expand(3, 2, 2) / 255
    row = {"observation.images.image": pixels, "observation.images.image2": pixels,
           "observation.state": torch.arange(8.), "action": torch.arange(350.).reshape(50, 7)}
    view = CoFTInputView([row], None, {"observation_height": 2, "observation_width": 2})
    result = view[0]
    for key in row:
        torch.testing.assert_close(row[key], result[key], rtol=0, atol=0)


def test_new_standalone_method_preserves_existing_scheduler_and_config_contract():
    assert METHODS == ("clare", "mlr_ifa", "continual_vla_rl", "rl2_vla")
    cfg = load_config(overrides={"method": "slow_loop_expansion"})
    assert cfg["global_batch_size"] == 32
    assert "demonstration_contract" not in load_config(overrides={"method": "continual_vla_rl"})


def test_settings_reject_gpu6_and_other_merge_coefficients(tmp_path):
    from baseline.slow_loop_expansion import load_settings
    cfg = {"schema_version": "baseline-slow-loop-expansion-v1", "method": "slow_loop_expansion", "gpu_index": 4,
           "alpha": .8, "evaluation_split": "fixed_development_probe",
           "runtime": load_config(overrides={"method": "slow_loop_expansion", "output_root": "/tmp/baseline_runs/test"})}
    path = tmp_path / "cfg.json"
    write_json(path, cfg)
    assert load_settings(path)["alpha"] == .8
    for key, value in [("gpu_index", 6), ("alpha", .6)]:
        bad = copy.deepcopy(cfg)
        bad[key] = value
        write_json(path, bad)
        with pytest.raises(ValueError):
            load_settings(path)


def test_device_is_resolved_by_physical_uuid_before_cuda_and_other_gpu_is_rejected(monkeypatch):
    from baseline.slow_loop_expansion import configure_gpu, require_selected_gpu
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    monkeypatch.setattr("baseline.slow_loop_expansion.subprocess.check_output", lambda *a, **kw: "4, GPU-four\n6, GPU-six\n")
    configure_gpu(4)
    require_selected_gpu(4)
    with pytest.raises(ValueError):
        configure_gpu(6)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-six")
    with pytest.raises(ValueError):
        require_selected_gpu(4)
