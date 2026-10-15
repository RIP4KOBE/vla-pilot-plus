"""CPU mocks only: no main, torch, CUDA, MuJoCo or simulator imports."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_phase_under_test", ROOT / "core/render_phase_diagnostics.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
RenderPhaseDiagnostics = module.RenderPhaseDiagnostics


def fixture_graph():
    calls = []
    pixels = object()
    class Context:
        def render(self, *args, **kwargs):
            calls.append(("context.render", args, kwargs))
        def read_pixels(self, *args, **kwargs):
            calls.append(("context.read_pixels", args, kwargs))
            return pixels
    class Sim:
        def __init__(self):
            self._render_context_offscreen = Context()
        def forward(self, *args, **kwargs):
            calls.append(("forward", args, kwargs))
        def step(self, *args, **kwargs):
            calls.append(("physics.step", args, kwargs))
        def render(self, width=None, height=None, *, camera_name=None, depth=False, segmentation=False):
            calls.append(("sim.render", (width, height), dict(camera_name=camera_name, depth=depth, segmentation=segmentation)))
            self._render_context_offscreen.render(width=width, height=height, camera_id=0, segmentation=segmentation)
            return self._render_context_offscreen.read_pixels(width, height, depth=depth, segmentation=segmentation)
    class Domain:
        def __init__(self):
            self.sim = Sim()
        def _pre_action(self, *args, **kwargs):
            calls.append(("pre_action", args, kwargs))
        def _update_observables(self, *args, **kwargs):
            calls.append(("update_observables", args, kwargs))
            return self.sim.render(width=128, height=128, camera_name="robot0_eye_in_hand", depth=True)
    class Env:
        def __init__(self):
            self._env = SimpleNamespace(env=Domain())
        def _format_raw_obs(self, observation):
            calls.append(("format_raw_obs", (observation,), {}))
            return observation
    env = Env()
    adapter = SimpleNamespace(_env=[env], current_task_idx=0)
    return adapter, env, env._env.env, env._env.env.sim, pixels, calls


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_original_call_order_arguments_objects_and_return_are_preserved(tmp_path):
    adapter, env, domain, sim, pixels, calls = fixture_graph()
    token = object()
    def operations():
        sim.forward(token, flag=True)
        domain._pre_action(token, policy_step=False)
        sim.step(False)
        assert domain._update_observables(force=True) is pixels
        assert env._format_raw_obs(token) is token
    operations()
    expected = list(calls)
    calls.clear()
    observer = RenderPhaseDiagnostics(tmp_path / "phases.jsonl")
    observer.install(adapter)
    observer.set_phase(1, 3, "adapter_step", "enter")
    operations()
    assert calls == expected
    assert calls[0][1][0] is token
    observer.close()


def test_shared_render_has_nested_ids_and_distinct_overlay_observation_parents(tmp_path):
    adapter, _, domain, sim, pixels, _ = fixture_graph()
    path = tmp_path / "phases.jsonl"
    observer = RenderPhaseDiagnostics(path)
    observer.install(adapter)
    observer.set_phase(0, 2, "debug_visualization_overlay", "enter")
    assert sim.render(640, 480, camera_name="agentview") is pixels
    observer.set_phase(0, 2, "debug_visualization_overlay", "exit")
    observer.set_phase(0, 2, "adapter_step", "enter")
    assert domain._update_observables() is pixels
    rows = records(path)
    enters = {r["call_id"]: r for r in rows if r["event"] == "enter"}
    assert len(rows) == 14
    for row in rows:
        assert set(row) <= {"schema", "episode", "global_step", "parent_phase", "name", "call_id", "parent_call_id", "event", "elapsed_s", "observed_wall_s", "nested_observer_s", "camera", "width", "height", "depth", "segmentation"}
        assert row["elapsed_s"] >= 0
        if row["event"] == "exit":
            assert row["name"] == enters[row["call_id"]]["name"]
        if row["name"] in {"offscreen_render", "read_pixels"}:
            assert enters[row["parent_call_id"]]["name"] == "sim_render_total"
    assert {r["camera"] for r in rows if r["name"] == "sim_render_total"} == {"agentview", "robot0_eye_in_hand"}
    assert {r["parent_phase"] for r in rows} == {"debug_visualization_overlay", "adapter_step"}
    observer.close()


def test_phase_overhead_summary_counts_records_and_excludes_nested_logging(tmp_path):
    adapter, _, domain, _, _, _ = fixture_graph()
    path = tmp_path / "phases.jsonl"
    observer = RenderPhaseDiagnostics(path)
    observer.install(adapter)
    observer.set_phase(0, 0, "adapter_step", "enter")
    domain._update_observables()
    overhead = observer.set_phase(0, 0, "adapter_step", "exit")
    summary = records(tmp_path / "render_phase_overhead.jsonl")[0]
    assert summary["record_count"] == len(records(path)) == 8
    assert summary["estimated_observer_s"] == overhead
    assert overhead >= summary["append_io_s"] >= 0
    for row in records(path):
        assert row["elapsed_s"] == max(0, row["observed_wall_s"] - row["nested_observer_s"])
    render = next(r for r in records(path) if r["name"] == "sim_render_total" and r["event"] == "exit")
    assert render["nested_observer_s"] > 0
    observer.close()


def test_operation_exception_is_identical_and_leaves_unmatched_enter(tmp_path):
    adapter, _, _, sim, _, calls = fixture_graph()
    error = RuntimeError("private operation detail")
    def fail(*args, **kwargs):
        calls.append(("failure", args, kwargs))
        raise error
    sim._render_context_offscreen.read_pixels = fail
    path = tmp_path / "phases.jsonl"
    observer = RenderPhaseDiagnostics(path)
    observer.install(adapter)
    observer.set_phase(0, 0, "debug_visualization_overlay", "enter")
    with pytest.raises(RuntimeError) as caught:
        sim.render(640, 480)
    assert caught.value is error
    assert [r["event"] for r in records(path) if r["name"] == "read_pixels"] == ["enter"]
    assert [r["event"] for r in records(path) if r["name"] == "sim_render_total"] == ["enter"]
    assert "private" not in path.read_text()
    assert observer._stack == []
    assert sum(c[0] == "failure" for c in calls) == 1
    observer.close()


def test_write_failure_does_not_change_operation_result_or_retry_it(tmp_path):
    adapter, _, _, sim, pixels, calls = fixture_graph()
    blocked = tmp_path / "file_not_directory"
    blocked.write_text("existing")
    observer = RenderPhaseDiagnostics(blocked / "phases.jsonl")
    observer.install(adapter)
    observer.set_phase(0, 0, "debug_visualization_overlay", "enter")
    assert sim.render(640, 480) is pixels
    assert observer._failed
    assert [c[0] for c in calls] == ["sim.render", "context.render", "context.read_pixels"]
    observer.close()


def test_no_phase_means_no_io_and_close_restores_inherited_and_instance_bindings(tmp_path):
    adapter, env, domain, sim, pixels, _ = fixture_graph()
    original_forward = lambda *args, **kwargs: None
    sim.forward = original_forward
    objects = [env, domain, sim, sim._render_context_offscreen]
    original_keys = [set(vars(obj)) for obj in objects]
    path = tmp_path / "phases.jsonl"
    observer = RenderPhaseDiagnostics(path)
    observer.install(adapter)
    assert sim.render(640, 480) is pixels
    assert not path.exists()
    observer.close()
    assert [set(vars(obj)) for obj in objects] == original_keys
    assert sim.forward is original_forward
    assert sim.render.__func__ is type(sim).render


def test_public_camera_allowlist_and_no_input_or_environment_serialization(tmp_path, monkeypatch):
    adapter, _, _, sim, pixels, _ = fixture_graph()
    monkeypatch.setenv("POE_API_KEY", "not-a-real-secret-must-not-appear")
    path = tmp_path / "phases.jsonl"
    observer = RenderPhaseDiagnostics(path)
    observer.install(adapter)
    observer.set_phase(0, 0, "debug_visualization_overlay", "enter")
    assert sim.render(640, 480, camera_name="private-camera-name") is pixels
    data = path.read_text()
    assert "private-camera-name" not in data and "not-a-real-secret" not in data and "POE" not in data
    assert {r["camera"] for r in records(path)} == {"other"}
    observer.close()


def test_existing_replacement_context_gets_wrapped_without_extra_render(tmp_path):
    adapter, _, _, sim, pixels, calls = fixture_graph()
    path = tmp_path / "phases.jsonl"
    observer = RenderPhaseDiagnostics(path)
    observer.install(adapter)
    sim._render_context_offscreen = type(sim._render_context_offscreen)()
    observer.set_phase(0, 0, "debug_visualization_overlay", "enter")
    assert sim.render(640, 480) is pixels
    assert len(calls) == 3
    assert [r["name"] for r in records(path) if r["event"] == "enter"] == ["sim_render_total", "offscreen_render", "read_pixels"]
    observer.close()


def test_failed_install_rolls_back_all_partial_bindings(tmp_path):
    adapter, env, domain, sim, _, _ = fixture_graph()
    domain._update_observables = None
    observer = RenderPhaseDiagnostics(tmp_path / "phases.jsonl")
    with pytest.raises(TypeError):
        observer.install(adapter)
    assert "_format_raw_obs" not in vars(env)
    assert "_pre_action" not in vars(domain)
    assert "forward" not in vars(sim)
    assert observer._hooks == []
