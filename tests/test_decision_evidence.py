import ast
import __future__
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from core.decision_evidence import DecisionEvidence, DecisionEvidenceIncomplete


ROOT = Path(__file__).resolve().parents[1]


def read_events(root):
    result = []
    for line in (root / "events.jsonl").read_text().splitlines():
        ref = json.loads(line)
        data = root / ref["bundle"]
        assert hashlib.sha256(data.read_bytes()).hexdigest() == ref["sha256"]
        result.extend(torch.load(data, map_location="cpu", weights_only=True)["events"])
    return result


def begin(rec, stage=1, step=0):
    rec.begin_decision(global_step=step, stage=stage, use_guidance=False,
                       keypoints=np.array([[1., 2., 3.]], dtype=np.float64), providers=[])
    action = torch.zeros(1, 8, 7, dtype=torch.bfloat16)
    rec.record("policy_action_decode", selected_latent=action, action_chunk=action)
    rec.commit_decision(action_chunk=action, execution_horizon=8)


def method(path, cls, name):
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {"np": np, "torch": torch}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(ROOT / path), "exec",
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace[name]


def test_dtype_snapshot_and_roundtrip_are_lossless_and_do_not_alias(tmp_path):
    rec = DecisionEvidence(tmp_path, episode=0)
    begin(rec)
    value = torch.tensor([1.0078125, -0.50390625], dtype=torch.bfloat16)
    raw = np.array([1.0000000000000002], dtype=np.float64)
    rec.record("precision_probe", model=value, source=raw)
    value.zero_(); raw[:] = 0
    rec.finish()
    payload = next(x["values"] for x in read_events(rec.root) if x["event"] == "precision_probe")
    assert payload["model"].dtype == torch.bfloat16
    assert torch.equal(payload["model"], torch.tensor([1.0078125, -0.50390625], dtype=torch.bfloat16))
    assert payload["source"].dtype == torch.float64
    assert payload["source"].item() == 1.0000000000000002
    assert rec.status()["complete"] and rec.overhead_s > 0


@pytest.mark.parametrize("gripper", [-.25, 0., .25])
def test_actual_adapter_step_records_sent_action_and_terminal_before_reset(tmp_path, gripper):
    inner_step = method("core/env_adapters/libero_adapter.py", "LiberoEnv", "step")
    outer_step = method("core/env_adapters/libero_adapter.py", "LiberoAdapter", "step")
    def run(enabled):
        calls = []
        position = np.array([.125, .25, .5], dtype=np.float64)
        raw = {"robot0_eef_pos": position, "robot0_gripper_qpos": np.array([.02, .03])}
        class Native:
            def step(self, action):
                calls.append(("step", action.copy()))
                return raw, .75, True, {}
            def check_success(self):
                calls.append(("check_success",))
                return True
        class Inner:
            step = inner_step
            task = "task"
            task_id = 0
            _max_episode_steps = 40
            def __init__(self):
                self._env = Native()
            def _format_raw_obs(self, obs):
                calls.append(("format",))
                return obs
            def reset(self):
                calls.append(("reset",))
                position[:] = 99
        inner = Inner()
        def postprocess(transition):
            calls.append(("postprocess",))
            result = transition["action"].clone()
            result[0] += 1
            return {"action": result}
        outer = SimpleNamespace(_env=[inner], current_task_idx=0, episode_step=0,
                                env_postprocessor=postprocess)
        rec = DecisionEvidence(tmp_path / str(enabled), episode=0) if enabled else None
        if rec:
            outer._decision_evidence = rec
            begin(rec)
            rec.dispatch(global_step=0, execution_index=1)
        action = torch.tensor([.5, 0, 0, 0, 0, 0, gripper], dtype=torch.bfloat16)
        result = outer_step(outer, action)
        if rec:
            rec.step_returned(terminated=result[2], truncated=result[3], success=result[4]["success"])
            rec.finish()
        return calls, rec, position
    off, _, _ = run(False)
    on, rec, position = run(True)
    assert [x[0] for x in on] == [x[0] for x in off] == ["postprocess", "step", "check_success", "format", "reset"]
    assert np.array_equal(on[1][1], off[1][1])
    events = read_events(rec.root)
    sent = next(e["values"]["action_numpy"] for e in events if e["event"] == "executed_action")
    observed = next(e["values"] for e in events if e["event"] == "pre_reset_outcome")
    assert sent.dtype == torch.float32 and np.array_equal(sent.numpy(), on[1][1])
    assert sent[-1].item() == (1 if gripper > 0 else -1)
    assert observed["observation"]["robot0_eef_pos"].tolist() == [.125, .25, .5]
    assert position.tolist() == [99., 99., 99.]
    assert [e["event"] for e in events].count("automatic_reset_boundary") == 1
    assert rec.status()["complete"]


def test_original_projector_full_nine_points_and_native_origin(tmp_path):
    project = method("core/env_adapters/libero_adapter.py", "LiberoAdapter", "delta_actions_to_ee_trajectory")
    calls = []
    raw = np.array([.123456789012345, -.5, .3], dtype=np.float64)
    adapter = SimpleNamespace(get_ee_pose_world=lambda: (calls.append("pose") or SimpleNamespace(position=raw)))
    action = torch.zeros(8, 7, dtype=torch.bfloat16)
    action[-1, 2] = 1
    baseline = project(adapter, action)
    rec = DecisionEvidence(tmp_path, episode=0)
    begin(rec)
    adapter._decision_evidence = rec
    observed = project(adapter, action)
    rec.record("projection", xyz=observed)
    rec.finish()
    assert calls == ["pose", "pose"]
    assert observed.shape == (9, 3) and observed.dtype == torch.bfloat16
    assert torch.equal(baseline, observed) and not torch.equal(observed[7], observed[8])
    origin = next(e["values"] for e in read_events(rec.root) if e["event"] == "projection_origin")
    assert origin["source_eef_position"].dtype == torch.float64
    assert origin["source_eef_position"][0].item() == raw[0]
    assert origin["cast_eef_start"].dtype == torch.bfloat16


def test_missing_pre_reset_or_required_policy_hook_rejects_completeness(tmp_path):
    rec = DecisionEvidence(tmp_path / "outcome", episode=0)
    begin(rec)
    rec.dispatch(global_step=0, execution_index=1)
    rec.step_returned(terminated=True, truncated=False, success=True)
    assert rec.finish()["complete"] is False
    assert json.loads((rec.root / "status.json").read_text())["complete"] is False
    other = DecisionEvidence(tmp_path / "policy", episode=0)
    other.begin_decision(global_step=0, stage=1, use_guidance=False, keypoints=None, providers=[])
    other.commit_decision(action_chunk=torch.zeros(1, 8, 7), execution_horizon=8)
    assert other.finish()["complete"] is False


def test_write_failure_does_not_replace_original_error_or_claim_complete(tmp_path, monkeypatch):
    rec = DecisionEvidence(tmp_path, episode=0)
    begin(rec)
    original = ValueError("original execution error")
    def fail(*args, **kwargs):
        raise OSError("write failed")
    monkeypatch.setattr(torch, "save", fail)
    rec.record("before_error", value=1)
    try:
        raise original
    except ValueError as caught:
        rec.close()
        assert caught is original
    assert rec.failed and not rec.status()["complete"]
    assert json.loads((rec.root / "status.json").read_text())["complete"] is False


def test_pending_dispatch_and_stage_boundary_never_invent_eight_outcomes(tmp_path):
    rec = DecisionEvidence(tmp_path, episode=0)
    begin(rec, stage=1)
    rec.dispatch(global_step=0, execution_index=1)
    rec.pre_reset_outcome({"robot0_eef_pos": np.zeros(3)}, reward=0, terminated=False, success=False)
    rec.step_returned(terminated=False, truncated=False, success=False)
    begin(rec, stage=2, step=1)
    rec.dispatch(global_step=1, execution_index=1)
    rec.close()
    events = read_events(rec.root)
    contexts = [e for e in events if e["event"] == "decision_context"]
    assert contexts[1]["values"]["stage_changed"] is True
    assert contexts[1]["reset_sequence"] == 0
    assert sum(e["event"] == "pre_reset_outcome" for e in events) == 1
    assert rec.status()["pending_action"] and not rec.status()["complete"]


def test_terminal_outcome_is_persisted_before_actual_adapter_reset_failure(tmp_path):
    inner_step = method("core/env_adapters/libero_adapter.py", "LiberoEnv", "step")
    rec = DecisionEvidence(tmp_path, episode=0)
    begin(rec)
    rec.dispatch(global_step=0, execution_index=1)
    position = np.array([.125, .25, .5], dtype=np.float64)
    raw = {"robot0_eef_pos": position}
    calls = []
    class ResetAbort(BaseException):
        pass
    def reset():
        calls.append("reset")
        # No close/finish/step_returned has run, yet terminal evidence is on disk.
        events = read_events(rec.root)
        terminal = next(e for e in events if e["event"] == "pre_reset_outcome")
        boundary = next(e for e in events if e["event"] == "automatic_reset_boundary")
        assert terminal["values"]["observation"]["robot0_eef_pos"].tolist() == [.125, .25, .5]
        assert boundary["values"]["reset_will_follow"] is True
        assert boundary["values"]["reset_completed"] is None
        assert not any(e["event"] == "step_returned" for e in events)
        position[:] = 99
        raise ResetAbort()
    def step(action):
        calls.append("step")
        return raw, 1., True, {}
    env = SimpleNamespace(_env=SimpleNamespace(step=step, check_success=lambda: True),
        task="task", task_id=0, _format_raw_obs=lambda obs: obs,
        _decision_evidence=rec, reset=reset)
    with pytest.raises(ResetAbort):
        inner_step(env, np.zeros(7, dtype=np.float32))
    assert calls == ["step", "reset"]
    status = json.loads((rec.root / "status.json").read_text())
    assert status["complete"] is False and status["pending_action"] is True
    assert rec._pending == []  # Already flushed; the test did not rescue it via close().
