import copy
import random
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from baseline.config import load_config, METHODS
from baseline.experiment import task_order, training_contexts
from baseline.io import read_json, write_json
from baseline.protocol import Protocol


EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments/env_position20_20260910"


def frozen_config():
    cfg = load_config(EXPERIMENT / "rl2_vla.json")
    cfg["task_selection"] = str(EXPERIMENT / "task_selection.json")
    cfg["experiment_plan"] = str(EXPERIMENT / "parent_plan.json")
    return cfg


def test_selected_twenty_keep_main_states_seeds_and_reject_other_variants():
    from baseline.scope import check_task_keys
    cfg = frozen_config()
    p = Protocol(EXPERIMENT / "parent_protocol.json")
    keys = task_order(cfg, p)
    assert len(keys) == 20
    assert sum(p.tasks[k]["perturbation_variant"] == "use_environment" for k in keys) == 10
    assert sum(p.tasks[k]["perturbation_variant"] == "use_swap" for k in keys) == 10
    assert len(p.contexts("fixed_development_probe", cfg["seed"], keys)) == 40
    contexts = training_contexts(cfg, p, keys)
    assert len(contexts) == 134
    main = {(r["task_key"], str(r["init_state_id"])): r for r in read_json(cfg["experiment_plan"])["contexts"]}
    for row in contexts:
        pair = main.get((row["task_key"], str(row["init_state_id"])))
        if pair:
            assert row["seed"] == pair["env_seed"] and row["policy_seed"] == pair["policy_seed"]
    with pytest.raises(ValueError, match="outside"):
        check_task_keys([next(k for k in p.tasks if k not in keys)], cfg, p)
    with pytest.raises(ValueError):
        p.contexts("policy_final_sealed", cfg["seed"], keys)


def test_common_configuration_matches_live_main_snapshot_and_reference_recipe():
    training = read_json(EXPERIMENT / "main_reference.json")["training"]
    for method in METHODS:
        cfg = load_config(EXPERIMENT / f"{method}.json")
        assert cfg["batch_size"] == training["per_device_batch_size"] == 4
        assert cfg["gradient_accumulation_steps"] == training["gradient_accumulation_steps"] == 8
        assert cfg["global_batch_size"] == training["global_batch_size"] == 32
        assert cfg["fresh_baseline_inputs"] and cfg["max_grad_norm"] == training["grad_clip"]
        assert cfg["learning_rate"] == training["peak_lr"]
    options = cfg["rl2_vla"]
    assert options["qam_steps"] == 500000 and options["safe_epochs"] == 2000
    assert options["q_ensemble"] == 10 and options["safe_hidden"] == 256
    assert options["learning_rate"] == 3e-4 and options["inverse_temperature"] == .1
    assert options["safe_weight_decay"] == 0 and options["safe_regularization"] == .1


def test_fresh_scope_rejects_retired_paths_including_symlinks(tmp_path):
    from baseline.scope import check_input_root
    root = tmp_path / "fresh"; root.mkdir()
    retired = tmp_path / "retired"; retired.mkdir()
    cfg = load_config(overrides={"fresh_baseline_inputs": True, "output_root": str(root)})
    (root / "escape").symlink_to(retired, target_is_directory=True)
    check_input_root(root / "new.pt", cfg)
    for path in (retired / "old.pt", root / "escape/old.pt"):
        with pytest.raises(ValueError, match="another baseline"):
            check_input_root(path, cfg)


def test_two_gpu_pool_excludes_protected_device():
    from baseline.campaign import validate_pool
    configs = {m: load_config(overrides={"method": m}) for m in METHODS}
    validate_pool([4, 5], configs)
    for bad in ([4, 6], [6], [4, 4], []):
        with pytest.raises(ValueError):
            validate_pool(bad, configs)


def test_scheduler_fills_two_gpu_slots_without_waiting_for_demonstrations(tmp_path, monkeypatch):
    from baseline import campaign, demo_source
    experiment = tmp_path / "config"; experiment.mkdir()
    for method in METHODS:
        cfg = frozen_config()
        cfg.update(method=method, output_root=str(tmp_path / "outputs"), protocol=str(EXPERIMENT / "parent_protocol.json"))
        write_json(experiment / f"{method}.json", cfg)
    monkeypatch.setattr(campaign, "cpu_environment", lambda: None)
    monkeypatch.setattr(campaign.os, "nice", lambda _: None)
    monkeypatch.setattr(campaign.signal, "signal", lambda *a: None)
    monkeypatch.setattr(demo_source, "snapshot_curated_source", lambda *a: None)
    monkeypatch.setattr(campaign.subprocess, "check_output", lambda *a, **k: "4, GPU-4, 79000\n5, GPU-5, 79000\n6, GPU-6, 79000\n")
    created = []
    def popen(command, **kwargs):
        child = SimpleNamespace(pid=1000000 + len(created), poll=lambda: None)
        created.append((command, kwargs["env"]["CUDA_VISIBLE_DEVICES"]))
        return child
    monkeypatch.setattr(campaign.subprocess, "Popen", popen)
    class EndCheck(Exception):
        pass
    monkeypatch.setattr(campaign.time, "sleep", lambda _: (_ for _ in ()).throw(EndCheck()))
    args = SimpleNamespace(experiment_dir=experiment, gpus=[4, 5], ticket_root=tmp_path / "tickets", collect_repeats=5, resume=False)
    with pytest.raises(EndCheck):
        campaign.run(args)
    status = read_json(tmp_path / "outputs/queue/status.json")
    assert len(created) == len(status["active_jobs"]) == 2
    assert {gpu for _, gpu in created} == {"GPU-4", "GPU-5"}
    assert {j["owner"] for j in status["jobs"]} == {"v44_reference", "rl2_vla"}
    assert all(status["methods"][m]["state"] == "WAITING_FOR_DEMONSTRATIONS" for m in ("clare", "mlr_ifa"))


def episodes():
    return [{"summary": {"success": bool(i % 2)}, "records": [
        {"latent": torch.full((4,), (i + j) / 10), "next_latent": torch.zeros(4),
         "actions": torch.zeros(7), "reward": torch.tensor(float(i % 2)), "bootstrap_discount": torch.tensor(0.)}
        for j in range(i + 1)]} for i in range(4)]


def test_safe_epochs_cover_dataset_and_mask_sequence_padding():
    from baseline.rl2_training import epoch_batch_indices, safe_loss
    from baseline.methods.rl2_vla import FailureLSTM
    indices = list(epoch_batch_indices(470, 32, 12, 0))
    assert len(indices) == 15 and all(len(row) == 32 for row in indices)
    assert set(sum(indices, [])) == set(range(470))
    detector = FailureLSTM(4, 3)
    data = episodes()
    together, _ = safe_loss(detector, data, "cpu", 0.)
    separate = torch.stack([safe_loss(detector, [v], "cpu", 0.)[0] for v in data]).mean()
    torch.testing.assert_close(together, separate)
    penalized, _ = safe_loss(detector, data, "cpu", .1)
    penalty = .1 * sum(p.square().sum() for name, p in detector.named_parameters() if "bias" not in name)
    torch.testing.assert_close(penalized - together, penalty)


def test_reference_qam_uses_paper_network_and_adam_configuration():
    from baseline.methods.rl2_vla import QAM
    from baseline.rl2_training import reference_optimizer
    cfg = frozen_config()
    qam = QAM(4, 7, {**cfg["rl2_vla"], "hidden_dim": 8, "hidden_layers": 1})
    assert len(qam.critic.members) == 10
    assert isinstance(qam.critic.members[0][1], nn.GELU)
    assert isinstance(qam.critic.members[0][2], nn.LayerNorm)
    optimizer = reference_optimizer(qam.parameters(), "qam", cfg)
    assert type(optimizer) is torch.optim.Adam and optimizer.defaults["betas"] == (.9, .999)
    assert optimizer.defaults["lr"] == 3e-4 and optimizer.defaults["weight_decay"] == 0


def test_rl2_optimizer_resume_matches_uninterrupted_training(tmp_path, monkeypatch):
    from baseline import rl2_training
    from baseline.methods.rl2_vla import RL2VLA
    torch.set_num_threads(1)
    cfg = load_config(overrides={"method": "rl2_vla", "batch_size": 1, "gradient_accumulation_steps": 2,
         "global_batch_size": 2, "steps_per_stage": 2, "execution_horizon": 1, "output_root": str(tmp_path),
         "fresh_baseline_inputs": True, "rl2_vla": {"training_recipe": "paper_reference", "qam_steps": 2,
         "safe_epochs": 2, "hidden_dim": 8, "hidden_layers": 1, "safe_hidden": 3,
         "flow_steps": 2, "q_ensemble": 2, "checkpoint_every": 1, "safe_regularization": .1}})
    runtime = SimpleNamespace(hidden_dim=4, device=torch.device("cpu"), identity={"sha256": "v44"}, cfg=cfg)
    protocol = SimpleNamespace(digest="protocol")
    full_dir = tmp_path / "full"; full_dir.mkdir()
    partial = tmp_path / "partial"; partial.mkdir()
    resumed = tmp_path / "resumed"; resumed.mkdir()
    torch.manual_seed(42)
    full = RL2VLA(runtime, cfg["rl2_vla"])
    rl2_training.fit_reference(full, runtime, cfg, protocol, full_dir, episodes(), "bank", lambda _: None)
    torch.manual_seed(42)
    interrupted = RL2VLA(runtime, cfg["rl2_vla"])
    original = rl2_training.save_optimizer_checkpoint
    def stop(path, method, optimizer, rng, phase, updates, contract):
        original(path, method, optimizer, rng, phase, updates, contract)
        if phase == "qam" and updates == 1:
            raise RuntimeError("simulated interruption")
    monkeypatch.setattr(rl2_training, "save_optimizer_checkpoint", stop)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        rl2_training.fit_reference(interrupted, runtime, cfg, protocol, partial, episodes(), "bank", lambda _: None)
    monkeypatch.setattr(rl2_training, "save_optimizer_checkpoint", original)
    restored = RL2VLA(runtime, cfg["rl2_vla"])
    rl2_training.fit_reference(restored, runtime, cfg, protocol, resumed, episodes(), "bank", lambda _: None,
                               partial / "optimizer_checkpoint.pt")
    for name in ("qam", "detector", "verifier"):
        for k, v in getattr(full, name).state_dict().items():
            torch.testing.assert_close(v, getattr(restored, name).state_dict()[k], rtol=0, atol=0)
    wrong = copy.deepcopy(cfg); wrong["rl2_vla"]["learning_rate"] *= 2
    with pytest.raises(ValueError, match="different data, configuration"):
        rl2_training.fit_reference(restored, runtime, wrong, protocol, resumed, episodes(), "bank", lambda _: None,
                                   partial / "optimizer_checkpoint.pt")
