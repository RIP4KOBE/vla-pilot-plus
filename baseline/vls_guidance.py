"""Validate and adapt generated VLS rewards before the native engine loads them."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path
import shutil
import time

from .io import append_json, digest, read_json, write_json


class InvalidGuidanceResponse(RuntimeError):
    """A generated program needs another generation, not another robot episode."""


def normalize_source(source):
    """Remove only an unaliased import of the already-injected torch namespace.

    Other imports and unsafe operations remain subject to the existing AST
    validator. Never execute the unvalidated original program.
    """
    from utils.guidance_utils import validate_guidance_ast
    tree = ast.parse(source)
    redundant = [n for n in ast.walk(tree) if isinstance(n, ast.Import)
                 and len(n.names) == 1 and n.names[0].name == "torch" and n.names[0].asname is None]
    if redundant:
        for node in ast.walk(tree):
            if ((isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == "torch")
                    or (isinstance(node, ast.arg) and node.arg == "torch")):
                raise InvalidGuidanceResponse("torch must remain the loader-provided namespace")
        class RemoveRedundantImport(ast.NodeTransformer):
            def visit_Import(self, node):
                return None if node in redundant else node
        tree = RemoveRedundantImport().visit(tree)
        source = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    validate_guidance_ast(source)
    return source, [node.lineno for node in redundant]


def validate_program(directory, metadata):
    """Use the unchanged native loader and exercise actual keypoint dimensions.

    Deterministic CPU inputs cover FK scoring (B=1,T=9) and policy guidance
    (B=1/40,T=10), without consuming the simulator or policy RNG.
    """
    import torch
    from utils.guidance_utils import load_functions_from_txt
    directory = Path(directory)
    try:
        program = read_json(directory / "metadata.json")
        stages = program["num_stages"]
        if isinstance(stages, bool) or not isinstance(stages, int) or not 1 <= stages <= 50:
            raise ValueError("num_stages must be an integer between 1 and 50")
        names = {f"stage{i}_guidance.txt" for i in range(1, stages + 1)}
        if {p.name for p in directory.glob("stage*_guidance.txt")} != names:
            raise ValueError("generated stage files do not match num_stages")
        keypoints = torch.as_tensor(metadata["init_keypoint_positions"], dtype=torch.float32, device="cpu")
        if tuple(keypoints.shape) != (int(metadata["num_keypoints"]), 3) or not torch.isfinite(keypoints).all():
            raise ValueError("invalid scene keypoint dimensions or values")
        if len(keypoints) == 0:
            raise ValueError("scene has no keypoints")
        report = {"status": "valid", "native_ast_guard": "unchanged", "files": {}}
        originals = directory / "original_guidance"
        originals.mkdir()
        for name in sorted(names):
            path = directory / name
            original_sha = digest(path)
            shutil.copy2(path, originals / name)
            normalized, removed = normalize_source(path.read_text())
            path.write_text(normalized)
            functions = load_functions_from_txt(str(path), validate=False)
            if not functions:
                raise ValueError(f"{name} contains no reward functions")
            probes = []
            with torch.enable_grad():
                for batch, horizon in ((1, 9), (1, 10), (40, 10)):
                    for function in functions:
                        trajectory = (keypoints[0] + torch.linspace(-0.06, 0.06, batch * horizon * 3)
                                      .reshape(batch, horizon, 3)).requires_grad_(True)
                        reward = function(keypoints, trajectory)
                        if (not isinstance(reward, torch.Tensor) or reward.numel() not in (1, batch)
                                or not torch.isfinite(reward).all()):
                            raise ValueError(f"{name} must return finite scalar/per-particle rewards")
                        if reward.requires_grad:
                            gradient, = torch.autograd.grad(reward.sum(), trajectory)
                            if not torch.isfinite(gradient).all():
                                raise ValueError(f"{name} produced non-finite action gradients")
                            reward_mode, gradient_finite = "differentiable_reward", True
                        elif torch.count_nonzero(reward).item() == 0:
                            # The official prompt explicitly uses zero for stages
                            # that need no reward guidance. The native loader also
                            # converts Python 0 to a tensor, and PI05 skips its
                            # gradient while retaining the normal FK/diversity path.
                            reward_mode, gradient_finite = "zero_reward", None
                        else:
                            raise ValueError(f"{name} nonzero rewards must be differentiable with respect to actions")
                        probes.append({"batch": batch, "horizon": horizon,
                                       "reward_shape": list(reward.shape), "reward_mode": reward_mode,
                                       "gradient_finite": gradient_finite})
            report["files"][name] = {"original_sha256": original_sha, "normalized_sha256": digest(path),
                                    "removed_redundant_torch_import_lines": removed, "probes": probes}
        write_json(directory / "validation.json", report)
        return report
    except (ArithmeticError, AssertionError, AttributeError, IndexError, KeyError,
            NameError, SyntaxError, TypeError, ValueError, RuntimeError) as exc:
        raise InvalidGuidanceResponse(str(exc)) from exc


def correction_prompt(error):
    from utils.guidance_utils import _SAFE_TORCH_MEMBERS
    return ("\n\nExecution compatibility feedback: the previous generated program was rejected before any robot action.\n"
            f"Validation error: {error[:1000]}\n"
            "Regenerate a complete concise program for the SAME task and image, retaining the requested output format. "
            "Include num_stages and exactly stage1_guidance through stageN_guidance, each with two plain arguments "
            "(keypoints, action_sequence). torch is already provided; do not import modules, use aliases, annotations, "
            "helpers, loops, branches or external state. Use tensor expressions and torch.where when needed. "
            "Use only the keypoint IDs in the scene. Return finite scalar rewards (or one per trajectory). "
            "For stages where the task-specific rules request no reward guidance, return 0 or a zero tensor; "
            "these zero-reward stages do not need gradients. All nonzero rewards must be differentiable with "
            "respect to action_sequence. "
            "keypoints is (N,3), action_sequence is (B,T,3), B can be 1 or 40 and T can be 9 or 10. "
            "Avoid division by zero and undefined gradients. Keep the complete response within 2000 tokens. "
            f"Available torch operations/constants: {', '.join(sorted(_SAFE_TORCH_MEMBERS))}.\n")


def install_guidance_validation(agent):
    original_generate = agent.generate_guidance

    def generate(img, instruction, metadata):
        destination = Path(agent.task_dir)
        attempts_root = destination.parent / "guidance_attempts"
        attempts_root.mkdir(exist_ok=True)
        first = 1 + max([int(p.name.split("_")[-1]) for p in attempts_root.glob("attempt_[0-9]*")], default=0)
        original_template = agent.prompt_template
        last_error = None
        try:
            for attempt in count(1):
                directory = attempts_root / f"attempt_{first + attempt - 1:03d}"
                directory.mkdir()
                agent.task_dir = str(directory)
                agent.prompt_template = original_template + (correction_prompt(last_error) if last_error else "")
                record = {"attempt": attempt, "directory": str(directory), "status": "generating",
                          "started_at": datetime.now(timezone.utc).isoformat(), "max_attempts": None}
                write_json(destination.parent / "guidance_status.json", record)
                try:
                    try:
                        generated = original_generate(img, instruction, deepcopy(metadata))
                    except (ValueError, KeyError, NameError, TypeError, SyntaxError) as exc:
                        if not (directory / "output_raw.txt").exists():
                            raise
                        raise InvalidGuidanceResponse(f"generated response could not be parsed: {exc}") from exc
                    if Path(generated).resolve() != directory.resolve():
                        raise RuntimeError("reward generator wrote outside its owned attempt directory")
                    validation = validate_program(directory, metadata)
                except InvalidGuidanceResponse as exc:
                    last_error = str(exc)
                    delay = min(2 ** min(attempt, 6), 60)
                    record.update(status="regenerating", error_type=type(exc).__name__, error=last_error,
                                  retry_delay_seconds=delay,
                                  next_retry_at=(datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat())
                    write_json(directory / "attempt_status.json", record)
                    append_json(attempts_root / "attempts.jsonl", record)
                    write_json(destination.parent / "guidance_status.json", record)
                    print(f"VLS reward program rejected; regenerating attempt {attempt + 1} in {delay}s: {last_error}", flush=True)
                    time.sleep(delay)
                    continue
                # Publish only a fully checked program to the native Main loader.
                destination.mkdir(exist_ok=True)
                for old in destination.glob("stage*_guidance.txt"):
                    if old.name not in validation["files"]:
                        old.unlink()
                for source in directory.iterdir():
                    if source.is_file():
                        temporary = destination / (source.name + ".partial")
                        shutil.copy2(source, temporary)
                        temporary.replace(destination / source.name)
                record.update(status="valid", normalized_torch_imports=sum(
                    len(v["removed_redundant_torch_import_lines"]) for v in validation["files"].values()))
                write_json(directory / "attempt_status.json", record)
                append_json(attempts_root / "attempts.jsonl", record)
                write_json(destination.parent / "guidance_status.json", record)
                return str(destination)
        finally:
            agent.task_dir = str(destination)
            agent.prompt_template = original_template

    agent.generate_guidance = generate
    return agent
