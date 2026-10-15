"""Actual Main.__init__ AST; no torch, model, simulator, or native imports."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
META = json.loads((HERE / "metadata.json").read_text())


def sources():
    original = (Path(META["worktree"]) / "main.py").read_text()
    assert hashlib.sha256(original.encode()).hexdigest() == META["main_before_sha256"]
    patch = (HERE / "cuda-before-adapter.patch").read_text()
    assert hashlib.sha256(patch.encode()).hexdigest() == META["patch_sha256"]
    header, body = patch.split("@@", 2)[1:]
    first = int(re.search(r"-(\d+)", header).group(1)) - 1
    hunk = body.splitlines(keepends=True)[1:]
    old = [line[1:] for line in hunk if line[:1] in (" ", "-")]
    new = [line[1:] for line in hunk if line[:1] in (" ", "+")]
    lines = original.splitlines(keepends=True)
    assert lines[first:first + len(old)] == old
    lines[first:first + len(old)] = new
    candidate = "".join(lines)
    assert hashlib.sha256(candidate.encode()).hexdigest() == META["main_candidate_sha256"]
    return original, candidate


class Config(dict):
    __getattr__ = dict.__getitem__


def exercise(source, *, policy_type="rdt", device="cuda:0", init_error=None):
    events = []
    tree = ast.parse(source)
    original_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Main")
    init = next(n for n in original_class.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    cls = ast.ClassDef(name="Runner", bases=[], keywords=[], body=[init], decorator_list=[])
    cfg = Config(seed=73, device=device,
        main=Config(episode_num=1, episode_start_index=0, instruction="frozen instruction", output_dir="unused/"),
        backend=Config(backend="libero", libero={"task_ids_filter": [0]}),
        policy={"type": policy_type, policy_type: {"pretrained_path": "frozen-checkpoint", "num_inference_steps": 10,
            "vision_encoder": "frozen-vision", "text_encoder": "frozen-text", "weight_variant": "ema", "control_frequency": 20}})
    adapter = SimpleNamespace(get_task_info=lambda: {"instruction": "task", "recommended_guide_scale": 80.0})

    def cuda_init():
        events.append(("cuda.init",))
        if init_error is not None:
            raise init_error

    def create_adapter(backend, env_config):
        events.append(("adapter", backend, copy.deepcopy(env_config)))
        return adapter

    def post_init(**kwargs):
        assert kwargs["adapter"] is adapter
        assert kwargs["postprocessor"]("value") == "value"
        events.append(("post_init", kwargs["sample_batch_size"], copy.deepcopy(kwargs["policy_config"])))

    policy = SimpleNamespace(config=SimpleNamespace(device=device),
        to=lambda value: events.append(("to", value)),
        post_init=post_init, eval=lambda: events.append(("eval",)), reset=lambda: events.append(("reset",)))

    def from_pretrained(*args, **kwargs):
        events.append(("load", args, kwargs))
        return policy

    factories = {
        "core.rdt_policy_steer": SimpleNamespace(RDTSteer=SimpleNamespace(from_pretrained=from_pretrained)),
        "core.diffusion_policy_steer": SimpleNamespace(DiffusionPolicySteer=SimpleNamespace(from_pretrained=from_pretrained)),
        "core.pi05_steer": SimpleNamespace(PI05PolicySteer=SimpleNamespace(from_pretrained=from_pretrained)),
        "lerobot.policies.factory": SimpleNamespace(make_pre_post_processors=lambda **_: (lambda x: x, lambda x: x)),
    }

    def safe_import(name, *args, **kwargs):
        assert name in factories, "Unexpected import: " + name
        return factories[name]

    import builtins
    namespace = {
        "__builtins__": dict(vars(builtins), __import__=safe_import), "DictConfig": Config,
        "log": SimpleNamespace(info=lambda *_: None),
        "OmegaConf": SimpleNamespace(to_yaml=lambda *_a, **_kw: "", to_container=lambda value, **_: copy.deepcopy(value)),
        "np": SimpleNamespace(random=SimpleNamespace(seed=lambda seed: events.append(("numpy.seed", seed)))),
        "torch": SimpleNamespace(manual_seed=lambda seed: events.append(("torch.manual_seed", seed)),
            device=lambda value: SimpleNamespace(type=value.split(":")[0]),
            cuda=SimpleNamespace(manual_seed=lambda seed: events.append(("cuda.manual_seed", seed)), init=cuda_init)),
        "os": SimpleNamespace(makedirs=lambda *_a, **_kw: None),
        "_adapter_episode_window": lambda **kwargs: kwargs,
        "_main_vls_config": lambda _: {"guide_scale": 80.0, "sample_batch_size": 1},
        "create_adapter": create_adapter,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), "<actual-main-init>", "exec"), namespace)
    runner_class = namespace["Runner"]
    runner_class._init_components = lambda self, config: events.append(("components",))
    try:
        runner = runner_class(cfg)
        assert runner.adapter is adapter
        assert runner.current_guide_scale == 80.0
        error = None
    except BaseException as caught:
        error = caught
    return events, error


def test_rdt_cuda_initializes_after_original_seeds_before_adapter_without_reordering_loader():
    original, candidate = sources()
    old_events, old_error = exercise(original)
    events, error = exercise(candidate)
    assert old_error is error is None
    assert [event[0] for event in events] == ["numpy.seed", "torch.manual_seed", "cuda.manual_seed",
        "cuda.init", "adapter", "load", "to", "post_init", "eval", "components", "reset"]
    assert [event for event in events if event[0] != "cuda.init"] == old_events
    assert events[:3] == [("numpy.seed", 73), ("torch.manual_seed", 73), ("cuda.manual_seed", 73)]


def test_cuda_init_original_exception_propagates_without_creating_environment_or_loading_model():
    _, candidate = sources()
    failure = RuntimeError("synthetic initialization failure")
    events, error = exercise(candidate, init_error=failure)
    assert error is failure
    assert [event[0] for event in events] == ["numpy.seed", "torch.manual_seed", "cuda.manual_seed", "cuda.init"]


def test_cpu_and_other_policy_paths_preserve_original_calls_and_seed_values():
    original, candidate = sources()
    for policy_type, device in (("rdt", "cpu"), ("diffusion", "cuda:0"), ("pi05", "cpu")):
        old_events, old_error = exercise(original, policy_type=policy_type, device=device)
        events, error = exercise(candidate, policy_type=policy_type, device=device)
        assert old_error is error is None
        assert events == old_events
        assert not any(event[0] == "cuda.init" for event in events)
