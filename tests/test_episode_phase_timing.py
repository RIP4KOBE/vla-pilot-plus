"""CPU-only diagnostic tests; main, models and simulators are never imported."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def timing_runner(tmp_path, append=None, fault_enable=None):
    tree = ast.parse((ROOT / "main.py").read_text())
    main = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Main")
    methods = [node for node in main.body if isinstance(node, ast.FunctionDef)
               and node.name in {"_append_phase_timing", "_enable_phase_diagnostics"}]
    cls = ast.ClassDef(name="Runner", bases=[], keywords=[], body=methods, decorator_list=[])
    def writer(path, record):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(json.dumps(record, allow_nan=False) + "\n")
    warnings, fault_calls = [], []
    namespace = {"Path": Path, "append_jsonl": append or writer,
                 "_config_section_to_dict": lambda section, _: section or {},
                 "log": SimpleNamespace(warning=warnings.append),
                 "faulthandler": SimpleNamespace(enable=fault_enable or
                     (lambda **kwargs: fault_calls.append(kwargs)))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 "<phase-diagnostic-methods>", "exec"), namespace)
    runner = namespace["Runner"]()
    runner.config = {"eds_eval": {"enabled": True, "output_dir": str(tmp_path / "eds")}}
    runner.output_dir = str(tmp_path)
    return runner, warnings, main, fault_calls


def test_phase_pairs_append_only_public_scalars_to_eval_directory(tmp_path):
    runner, _, _, _ = timing_runner(tmp_path)
    for step in (0, 1):
        for event, elapsed in (("enter", 0.0), ("exit", 0.125)):
            runner._append_phase_timing(episode=2, global_step=step,
                name="adapter_step", event=event, elapsed_s=elapsed)
    records = [json.loads(line) for line in (tmp_path / "eds/phase_timing.jsonl").read_text().splitlines()]
    assert [(r["global_step"], r["event"]) for r in records] == [(0,"enter"),(0,"exit"),(1,"enter"),(1,"exit")]
    for record in records:
        assert record == {"schema": "qd-ed-phase-timing-v2", "episode": 2,
            "global_step": record["global_step"], "name": "adapter_step", "event": record["event"],
            "elapsed_s": 0.0 if record["event"] == "enter" else 0.125,
            "observed_wall_s": 0.0 if record["event"] == "enter" else 0.125, "nested_observer_s": 0.0}
    assert not (tmp_path / "phase_timing.jsonl").exists()


def test_disabled_eval_has_neither_timing_io_nor_fault_handler_change(tmp_path):
    runner, _, _, fault_calls = timing_runner(tmp_path)
    runner.config["eds_eval"]["enabled"] = False
    runner._enable_phase_diagnostics()
    runner._append_phase_timing(episode=0, global_step=0,
        name="adapter_step", event="enter", elapsed_s=0)
    assert not (tmp_path / "eds").exists()
    assert fault_calls == []


def test_diagnostic_write_failure_does_not_raise_or_expose_error_content(tmp_path):
    def broken(*_args):
        raise OSError("private provider value should not be logged")
    runner, warnings, _, _ = timing_runner(tmp_path, append=broken)
    for event in ("enter", "exit"):
        runner._append_phase_timing(episode=0, global_step=0,
            name="adapter_step", event=event, elapsed_s=0)
    assert warnings == ["Phase timing unavailable; diagnostic writes disabled"]
    assert runner._phase_timing_write_failed is True


def test_original_action_exception_leaves_enter_only_and_propagates_unchanged(tmp_path):
    records = []
    runner, _, main, _ = timing_runner(tmp_path, append=lambda _path, record: records.append(record))
    episode = next(node for node in main.body if isinstance(node, ast.FunctionDef)
                   and node.name == "_run_episode")
    loop = next(node for node in episode.body if isinstance(node, ast.While))
    position = next(i for i, node in enumerate(loop.body) if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "self.adapter.step")
    # Real enter/start/action/exit statements; no simulator or live process.
    statements = loop.body[position - 2:position + 2]
    error = RuntimeError("original action failure")
    def fail(_action):
        raise error
    runner.adapter = SimpleNamespace(step=fail)
    namespace = {"self": runner, "action_chunk": [[0]], "action_executed": 0,
                 "episode": 0, "global_steps": 0, "time": SimpleNamespace(perf_counter=lambda: 1)}
    with pytest.raises(RuntimeError) as caught:
        exec(compile(ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[])),
                     "<actual-action-phase-statements>", "exec"), namespace)
    assert caught.value is error
    assert len(records) == 1 and records[0]["event"] == "enter"
    assert records[0]["name"] == "adapter_step"


def test_fault_handler_uses_all_threads_and_existing_stderr(tmp_path):
    runner, _, _, fault_calls = timing_runner(tmp_path)
    runner._enable_phase_diagnostics()
    assert fault_calls == [{"all_threads": True}]


def test_fault_handler_setup_failure_does_not_interrupt_control_or_log_error(tmp_path):
    def broken(**_kwargs):
        raise OSError("private stderr initialization detail")
    runner, warnings, _, _ = timing_runner(tmp_path, fault_enable=broken)
    runner._enable_phase_diagnostics()
    assert warnings == ["Native-fault stack diagnostics unavailable"]


def test_parent_context_is_updated_even_after_main_writer_failure(tmp_path):
    runner, _, _, _ = timing_runner(tmp_path)
    calls = []
    runner._render_phase_diagnostics = SimpleNamespace(set_phase=lambda *args: calls.append(args))
    runner._phase_timing_write_failed = True
    runner._append_phase_timing(episode=1, global_step=4,
        name="adapter_step", event="exit", elapsed_s=0)
    assert calls == [(1, 4, "adapter_step", "exit")]


def test_cached_fresh_and_stage_instrumentation_remains_around_actual_calls(tmp_path):
    _, _, main, _ = timing_runner(tmp_path)
    episode = next(node for node in main.body if isinstance(node, ast.FunctionDef)
                   and node.name == "_run_episode")
    loop = next(node for node in episode.body if isinstance(node, ast.While))
    pos = next(i for i, node in enumerate(loop.body) if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "self.policy.select_action")
    assert ast.unparse(loop.body[pos - 2].value.func) == "self._append_phase_timing"
    assert ast.unparse(loop.body[pos + 2].value.func) == "self._append_phase_timing"
    for node in (loop.body[pos - 2], loop.body[pos + 2]):
        name = next(kw.value for kw in node.value.keywords if kw.arg == "name")
        assert isinstance(name, ast.IfExp)
        assert name.body.value == "select_action_fresh"
        assert name.orelse.value == "select_action_cached"
    markers = [node for node in ast.walk(episode) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == "_append_phase_timing"]
    stage = [node for node in markers if any(kw.arg == "name" and isinstance(kw.value, ast.Constant)
        and kw.value.value == "chunk_keypoints_stage" for kw in node.keywords)]
    assert [next(kw.value.value for kw in node.keywords if kw.arg == "event") for node in stage] == ["enter", "exit"]


def test_main_phase_separates_original_wall_and_nested_observer_estimate(tmp_path):
    captured = []
    runner, _, _, _ = timing_runner(tmp_path, append=lambda path, record: captured.append(record))
    runner._render_phase_diagnostics = SimpleNamespace(set_phase=lambda *args: 0.25)
    runner._append_phase_timing(episode=0, global_step=0,
        name="adapter_step", event="exit", elapsed_s=1.0)
    assert captured[0]["observed_wall_s"] == 1.0
    assert captured[0]["nested_observer_s"] == 0.25
    assert captured[0]["elapsed_s"] == 0.75


def lifecycle_runner(tmp_path):
    """Execute real Main lifecycle methods without importing main or GPU code."""
    import os
    tree = ast.parse((ROOT / "main.py").read_text())
    main = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Main")
    names = {"run", "run_test", "_close_render_phase_diagnostics"}
    methods = [node for node in main.body if isinstance(node, ast.FunctionDef) and node.name in names]
    cls = ast.ClassDef(name="Runner", bases=[], keywords=[], body=methods, decorator_list=[])
    namespace = {
        "os": os,
        "torch": SimpleNamespace(randint=lambda *a: SimpleNamespace(item=lambda: 321)),
        "_episode_seed_schedule": lambda *a, **kw: None,
        "_episode_seed_for_index": lambda *a, **kw: kw["sampled_seed"],
        "log": SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, error=lambda *a: None),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 "<actual-main-lifecycle-methods>", "exec"), namespace)
    runner = namespace["Runner"]()
    runner.config = {"episode_num": 2, "use_guidance": False}
    runner.output_dir = str(tmp_path)
    runner.backend = "libero"
    runner.current_guide_scale = 1.0
    runner.policy = SimpleNamespace(reset=lambda: None)
    runner.video_recorder = SimpleNamespace(clear=lambda: None)
    runner._begin_episode_compute = lambda: None
    runner._append_episode_compute = lambda **kwargs: None
    runner._save_execution_failure_video = lambda **kwargs: None
    return runner


@pytest.mark.parametrize("outcome", ["completed", "error", "interrupt"])
def test_real_run_releases_renderer_hooks_before_reset_and_on_episode_exit(tmp_path, outcome):
    from core.render_phase_diagnostics import RenderPhaseDiagnostics
    runner = lifecycle_runner(tmp_path)
    state = {"current": 0, "context": None}
    frees, resets, episodes, observers = [], [], [], []
    class Context:
        def __init__(self, owner):
            self.owner = owner
        def render(self):
            pass
        def __del__(self):
            frees.append((self.owner, state["current"]))
    state["context"] = Context(0)
    def install():
        observer = RenderPhaseDiagnostics(tmp_path / "not-written.jsonl")
        observer._hook(state["context"], "render", "offscreen_render")
        observers.append(observer)
        runner._render_phase_diagnostics = observer
    install()  # A previous observer exists before run, as on reused Main objects.
    def reset(*, seed):
        assert runner._render_phase_diagnostics is None
        assert "render" not in vars(state["context"])
        resets.append(seed)
        state["context"] = None  # Exact old-renderer finalization boundary.
        state["current"] += 1
        state["context"] = Context(state["current"])
    runner.adapter = SimpleNamespace(reset=reset, get_task_info=lambda: {})
    failure = KeyboardInterrupt() if outcome == "interrupt" else RuntimeError("episode failure")
    def episode(index, directory, seed):
        episodes.append(index)
        install()
        if outcome != "completed":
            raise failure
    runner._run_episode = episode
    if outcome == "interrupt":
        with pytest.raises(KeyboardInterrupt) as caught:
            runner.run()
        assert caught.value is failure
    else:
        runner.run()
    expected = 1 if outcome == "interrupt" else 2
    assert resets == [321] * expected
    assert episodes == list(range(expected))
    assert frees == [(owner, owner) for owner in range(expected)]
    assert runner._render_phase_diagnostics is None
    assert all(observer._hooks == [] for observer in observers)
    assert "render" not in vars(state["context"])
    assert not (tmp_path / "not-written.jsonl").exists()


def test_real_run_test_closes_previous_observer_before_its_reset(tmp_path):
    runner = lifecycle_runner(tmp_path)
    order = []
    runner._render_phase_diagnostics = SimpleNamespace(close=lambda: order.append("close"))
    stop = RuntimeError("stop after reset")
    def observation():
        raise stop
    runner.adapter = SimpleNamespace(reset=lambda: order.append("reset"),
                                     get_keypoint_detection_inputs=observation)
    with pytest.raises(RuntimeError) as caught:
        runner.run_test()
    assert caught.value is stop
    assert order == ["close", "reset"]
    assert runner._render_phase_diagnostics is None
