"""Terminal propagation and durable progress in resident LIBERO-PRO gates."""

from dataclasses import asdict
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from mode_gate.policy_evaluator import (
    EvaluationContext, RawEpisodeResult, RawPolicyEvaluator, _warm_episode_log,
)


@pytest.mark.parametrize("workers", [1, 3])
def test_gate_commits_completed_contexts_before_propagating_error(tmp_path, workers):
    contexts = tuple(EvaluationContext(
        suite="libero_10", task_id="task", task_index=3,
        perturbation_variant="use_environment", init_state_id=str(i),
        env_seed=1, policy_seed=2,
    ) for i in range(3))
    calls = []
    fail = True

    def execute(policy_id, checkpoint, context):
        calls.append(context.init_state_id)
        if fail and context.init_state_id == "1":
            raise RuntimeError("infrastructure failure, not a policy failure")
        return RawEpisodeResult(success=context.init_state_id != "2", steps=7)

    evaluator = RawPolicyEvaluator(executor=execute, ledger_path=tmp_path / "episodes.jsonl",
                                   manifest_hash="manifest", max_workers=workers)
    kwargs = dict(policy_id="candidate", checkpoint_path=tmp_path,
                  checkpoint_digest="digest", contexts=contexts)
    with pytest.raises(RuntimeError, match="infrastructure failure"):
        evaluator.evaluate(**kwargs)
    rows = list(evaluator.ledger.events.iter_valid())
    completed = {row["context"]["init_state_id"] for row in rows}
    assert completed == ({"0"} if workers == 1 else {"0", "2"})
    assert all(row["checkpoint_digest"] == "digest" for row in rows)
    fail = False
    calls.clear()
    result = evaluator.evaluate(**kwargs)
    assert set(calls) == {"0", "1", "2"} - completed
    assert result.raw_vector == (1, 1, 0)
    assert len(list(evaluator.ledger.events.iter_valid())) == 3
    calls.clear()
    assert evaluator.evaluate(**kwargs) == result
    assert calls == []


def test_serial_gate_persists_before_starting_next_context(tmp_path):
    contexts = [EvaluationContext("libero_10", "task", 3, "base", str(i), 1, 2)
                for i in range(2)]

    def execute(policy_id, checkpoint, context):
        if context is contexts[1]:
            rows = list(evaluator.ledger.events.iter_valid())
            assert rows[0]["context"] == asdict(contexts[0])
        return True

    evaluator = RawPolicyEvaluator(executor=execute, ledger_path=tmp_path / "episodes.jsonl",
                                   manifest_hash="manifest")
    assert evaluator.evaluate(policy_id="p", checkpoint_path=tmp_path,
                              checkpoint_digest="digest", contexts=contexts).episodes == 2


@pytest.mark.parametrize("raise_error", [False, True])
def test_warm_log_does_not_leave_closed_handler(tmp_path, raise_error):
    logger = logging.getLogger("test.gate-resident-console")
    console = sys.stdout
    handler = None
    try:
        try:
            with _warm_episode_log(tmp_path / "executor.log"):
                handler = logging.StreamHandler(sys.stdout)
                logger.addHandler(handler)
                if raise_error:
                    raise RuntimeError("test")
        except RuntimeError:
            assert raise_error
        assert handler.stream is console
        assert not handler.stream.closed
    finally:
        if handler is not None:
            logger.removeHandler(handler)


@pytest.fixture
def fake_adapter():
    import numpy as np
    from rsi.core.env_adapters.libero_adapter import LiberoAdapter, LiberoEnv

    class Wrapped:
        def __init__(self):
            self.env = SimpleNamespace(done=False, timestep=0, horizon=12)
            self.success = False
            self.calls = 0

        def step(self, action):
            assert not self.env.done, "no action may follow simulator termination"
            self.calls += 1
            self.env.timestep += 1
            self.env.done = self.env.timestep >= self.env.horizon
            # Reproduce BDDLBaseDomain masking the horizon with success.
            return {"image": np.zeros((1, 1, 3))}, 0.0, self.success, {}

        def check_success(self):
            return self.success

        def seed(self, seed):
            pass

        def reset(self):
            self.env.done, self.env.timestep = False, 0
            return {}

    env = LiberoEnv.__new__(LiberoEnv)
    env._env = Wrapped()
    env._max_episode_steps = 12
    env.num_steps_wait = 5
    env.init_states = False
    env.auto_reset = False
    env.task, env.task_id = "task", 3
    env._format_raw_obs = lambda raw: raw
    adapter = LiberoAdapter.__new__(LiberoAdapter)
    adapter._env = [env]
    adapter.current_task_idx = 0
    adapter.current_episode_idx = -1
    adapter.episodes_per_task = 1
    adapter.task_num = 1
    adapter.episode_step = 0
    adapter.env_postprocessor = lambda transition: transition
    return adapter


@pytest.mark.parametrize("teleop", [False, True])
def test_masked_simulator_timeout_is_returned_and_reset_is_clean(fake_adapter, teleop):
    import torch
    adapter = fake_adapter
    env = adapter._env[0]
    for _ in range(2):
        adapter.reset(seed=1)
        assert not env._env.env.done
        action = torch.zeros(7)
        step = adapter.step_teleop if teleop else adapter.step
        for index in range(7):
            _, _, terminated, truncated, info = step(action)
            assert not terminated and not info["success"]
            assert truncated == (index == 6)
        assert adapter.episode_step == 7
        assert env._env.env.timestep == 12
        assert info["TimeLimit.truncated"] is True
        assert info["final_info"]["success"] is False
    assert env._env.calls == 24  # 2 * (5 prescribed settling + 7 actions)


@pytest.mark.parametrize("teleop", [False, True])
@pytest.mark.parametrize("at_horizon", [False, True])
def test_native_success_is_immediate_even_at_horizon(fake_adapter, teleop, at_horizon):
    import torch
    adapter = fake_adapter
    env = adapter._env[0]
    env._env.success = True
    if at_horizon:
        env._env.env.timestep = env._env.env.horizon - 1
    step = adapter.step_teleop if teleop else adapter.step
    _, _, terminated, truncated, info = step(torch.zeros(7))
    assert terminated and not truncated and info["success"]
    assert env._env.calls == 1


def test_settling_stops_on_native_horizon_without_an_extra_action(fake_adapter):
    env = fake_adapter._env[0]
    env.num_steps_wait = 15
    with pytest.raises(RuntimeError, match="settling exhausted"):
        fake_adapter.reset(seed=1)
    assert env._env.calls == 12


def test_adapter_still_honors_its_own_step_limit(fake_adapter):
    import torch
    fake_adapter.episode_step = 11
    _, _, _, truncated, _ = fake_adapter.step(torch.zeros(7))
    assert truncated


@pytest.mark.skipif(os.environ.get("RUN_LIBERO_HORIZON_CANARY") != "1",
                    reason="opt-in real simulator regression; no policy model")
def test_real_libero_pro_horizon_and_reset():
    import numpy as np
    from rsi.core.env_adapters.libero_adapter import LiberoEnv, benchmark

    suite = benchmark.get_benchmark_dict()["libero_10_env"]()
    env = LiberoEnv(task_suite=suite, task_id=3, task_suite_name="libero_10_env",
                    observation_width=32, observation_height=32,
                    num_steps_wait=5, max_episode_steps=12,
                    camera_depths=False, read_language_from_bddl=True)
    try:
        for _ in range(2):
            env.reset(seed=17, init_state_id=0)
            assert not env._simulator_done()
            for step in range(7):
                _, _, terminated, truncated, info = env.step(np.zeros(7, dtype=np.float32))
                assert not terminated and not info["success"]
                assert truncated == (step == 6)
            assert env._simulator_done()
            assert env._env.env.timestep == env._env.env.horizon == 12
    finally:
        env.close()
