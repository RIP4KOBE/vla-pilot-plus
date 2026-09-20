import copy
import random
import signal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from baseline.config import load_config
from baseline.io import load_tensors, read_json, seed_all
from baseline.simulator_startup import RL_STARTUP_SECONDS, startup_deadline, startup_seconds


def test_startup_allowance_is_only_for_rl_and_restores_the_signal_handler():
    assert startup_seconds({"method": "continual_vla_rl"}) == 600
    assert startup_seconds({"method": "rl2_vla"}) == 600
    for method in ["clare", "mlr_ifa", "v44_vls"]:
        assert startup_seconds({"method": method}) is None
    handler = signal.getsignal(signal.SIGALRM)
    with pytest.raises(RuntimeError, match="inside constructor"):
        with startup_deadline(RL_STARTUP_SECONDS):
            assert signal.getitimer(signal.ITIMER_REAL)[0] > 590
            # The native adapter leaves an already active timer intact.
            with startup_deadline(120):
                assert signal.getitimer(signal.ITIMER_REAL)[0] > 590
            raise RuntimeError("inside constructor")
    assert signal.getitimer(signal.ITIMER_REAL) == (0, 0)
    assert signal.getsignal(signal.SIGALRM) is handler


def test_startup_does_not_cancel_or_extend_an_existing_alarm():
    signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        with startup_deadline(600):
            assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= 60
        assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= 60
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def test_baseline_deadline_really_interrupts_a_stuck_startup():
    with pytest.raises(TimeoutError, match="baseline LIBERO initialization"):
        with startup_deadline(.02):
            signal.pause()
    assert signal.getitimer(signal.ITIMER_REAL) == (0, 0)


def test_recovery_chooses_only_current_failed_work_and_retains_other_workers(tmp_path):
    from baseline.campaign import recover_failed_inputs, finished_job
    state = {"methods": {"continual_vla_rl": {"state": "QUEUED", "tasks_completed": 3},
                         "rl2_vla": {"state": "QUEUED", "tasks_collected": 2}},
             "collection_shards": ["done0", "done1"], "jobs": []}
    for owner, phase, suffix, name, file in [
        ("continual_vla_rl", "train", "stage_003", "current_rl", "continual_optimizer_checkpoint.pt"),
        ("continual_vla_rl", "train", "stage_002", "older_rl", "continual_optimizer_checkpoint.pt"),
        ("rl2_vla", "collect", "collect_002", "current_collection", "rollouts.json"),
        ("rl2_vla", "collect", "collect_001", "older_collection", "rollouts.json"),
    ]:
        folder = tmp_path / name; folder.mkdir(); (folder / file).touch()
        state["jobs"].append(dict(owner=owner, phase=phase, suffix=suffix, name=name, returncode=1))
    before = copy.deepcopy(state)
    recover_failed_inputs(state, tmp_path, {"rl2_vla"})
    assert state["methods"]["rl2_vla"] == before["methods"]["rl2_vla"]
    assert state["methods"]["continual_vla_rl"]["optimizer_resume"].endswith("current_rl/continual_optimizer_checkpoint.pt")
    recover_failed_inputs(state, tmp_path, set())
    assert state["methods"]["rl2_vla"]["collection_resume"].endswith("current_collection")
    job = dict(owner="rl2_vla", phase="collect", name="new_collection")
    finished_job(state, job, tmp_path, 20)
    assert state["methods"]["rl2_vla"]["tasks_collected"] == 3
    assert "collection_resume" not in state["methods"]["rl2_vla"]


def test_rng_round_trip_includes_numpy_torch_and_shuffle():
    from baseline.continual_checkpoint import random_state, restore_random_state
    seed_all(42); rng = random.Random(9)
    state = random_state(rng)
    expected = (random.random(), rng.random(), np.random.random(), torch.rand(3))
    seed_all(100); rng.seed(100)
    restore_random_state(state, rng)
    assert (random.random(), rng.random(), np.random.random()) == expected[:3]
    torch.testing.assert_close(torch.rand(3), expected[3], rtol=0, atol=0)


def test_grpo_resume_matches_uninterrupted_optimizer_updates(tmp_path, monkeypatch):
    from baseline import train, rollout, continual_checkpoint
    torch.set_num_threads(1)
    cfg = load_config(overrides={"method": "continual_vla_rl", "batch_size": 1,
        "gradient_accumulation_steps": 1, "global_batch_size": 1, "steps_per_stage": 20,
        "learning_rate": .01, "output_root": str(tmp_path), "fresh_baseline_inputs": True,
        "continual_vla_rl": {"group_size": 2, "groups_per_stage": 4, "update_epochs": 1}})
    runtime = SimpleNamespace(identity={"sha256": "v44"}, device=torch.device("cpu"), prefix=lambda x: x)
    protocol = SimpleNamespace(digest="fixed-protocol")

    class Method:
        def __init__(self):
            self.weight = torch.nn.Parameter(torch.randn(1))
            self.stages = ["previous_task"]
        def parameters(self):
            return [self.weight]
        def state(self):
            return {"weight": self.weight.detach().clone(), "stages": list(self.stages)}
        def restore(self, state):
            self.weight.data.copy_(state["weight"])
            self.stages = list(state["stages"])
        def transition_loss(self, embedded, transition, advantage):
            # Include actual random draws and optimizer momentum in the comparison.
            return ((self.weight - transition["value"]).square() * advantage * torch.rand(())).mean()

    monkeypatch.setattr(train, "make_method", lambda *a: Method())
    monkeypatch.setattr(train, "training_contexts", lambda *a: [{"task_key": "task", "seed": 10}])
    def optimizer(parameters, _):
        value = torch.optim.AdamW(parameters, lr=.01)
        return value, torch.optim.lr_scheduler.ExponentialLR(value, gamma=.9)
    monkeypatch.setattr(train, "policy_optimizer", optimizer)
    def episode(runtime, cfg, context, **kwargs):
        seed_all(context["policy_seed"])
        summary = {"context": context, "success": bool(context["policy_seed"] % 2), "steps": 10}
        return summary, [{"embedded": {"x": torch.ones(1, 1)},
                          "transitions": [{"value": torch.tensor([[float(context["policy_seed"] % 7)]])}]}]
    monkeypatch.setattr(rollout, "episode", episode)
    full_dir, interrupted_dir, resumed_dir = (tmp_path / name for name in ["full", "interrupted", "resumed"])
    for folder in [full_dir, interrupted_dir, resumed_dir]: folder.mkdir()
    full = train.train_continual_rl(runtime, cfg, protocol, full_dir, task_keys=["task"])
    original = continual_checkpoint.save_checkpoint
    def fail_after_checkpoint(*args, **kwargs):
        original(*args, **kwargs)
        if kwargs["groups_completed"] == 1:
            raise RuntimeError("simulated scene failure after saved group")
    monkeypatch.setattr(continual_checkpoint, "save_checkpoint", fail_after_checkpoint)
    with pytest.raises(RuntimeError, match="simulated scene failure"):
        train.train_continual_rl(runtime, cfg, protocol, interrupted_dir, task_keys=["task"])
    checkpoint = interrupted_dir / "continual_optimizer_checkpoint.pt"
    assert load_tensors(checkpoint)["stage_updates"] == 2
    monkeypatch.setattr(continual_checkpoint, "save_checkpoint", original)
    resumed = train.train_continual_rl(runtime, cfg, protocol, resumed_dir, task_keys=["task"], optimizer_resume=checkpoint)
    torch.testing.assert_close(resumed.weight, full.weight, rtol=0, atol=0)
    assert resumed.stages == full.stages == ["previous_task", "task"]
    full_state, resumed_state = (load_tensors(folder / "continual_optimizer_checkpoint.pt") for folder in [full_dir, resumed_dir])
    assert full_state["stage_updates"] == resumed_state["stage_updates"] == 8
    assert full_state["environment_steps"] == resumed_state["environment_steps"] == 80
    assert full_state["scheduler"] == resumed_state["scheduler"]
    assert read_json(resumed_dir / "optimizer_continuation.json")["groups_completed"] == 1
    wrong = copy.deepcopy(cfg); wrong["batch_size"] = 2
    with pytest.raises(ValueError, match="different configuration"):
        continual_checkpoint.read_checkpoint(checkpoint, runtime, wrong, protocol, ["task"])
    with pytest.raises(ValueError, match="another task"):
        continual_checkpoint.read_checkpoint(checkpoint, runtime, cfg, protocol, ["wrong_task"])
