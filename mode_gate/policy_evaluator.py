"""Resumable, paired raw-policy evaluation over frozen manifest contexts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping, Sequence

from .evaluation import EpisodeLedger, PolicyScore, assert_raw_profile, wilson_interval


@dataclass(frozen=True)
class EvaluationContext:
    suite: str
    task_id: str
    task_index: int
    perturbation_variant: str
    init_state_id: str
    env_seed: int
    policy_seed: int

    @property
    def task_key(self) -> str:
        return "::".join((self.suite, self.task_id, self.perturbation_variant))

    @property
    def episode_key(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True)
class RawEpisodeResult:
    success: bool
    steps: int | None = None
    output_dir: str = ""
    metadata: Mapping[str, Any] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True)
class PolicyEvaluationSummary:
    policy_id: str
    checkpoint_digest: str
    metric_role: str
    successes: int
    episodes: int
    micro_sr: float
    wilson95: tuple[float, float]
    macro_sr: float
    per_task_sr: Mapping[str, float]
    raw_vector: tuple[int, ...]
    evaluation_profile_hash: str = ""

    def policy_score(self, *, alpha_l: float) -> PolicyScore:
        return PolicyScore(
            candidate_id=self.policy_id,
            alpha_l=float(alpha_l),
            macro_sr=self.macro_sr,
            per_task_sr=self.per_task_sr,
        )


EpisodeExecutor = Callable[[str, Path, EvaluationContext], RawEpisodeResult | bool]


def contexts_from_manifest(
    manifest: Mapping[str, Any],
    *,
    split: str,
    policy_seed_repeats: int = 1,
) -> tuple[EvaluationContext, ...]:
    if split not in {"policy_alpha_selection", "policy_regression"}:
        raise ValueError("development evaluator cannot open final_sealed")
    if policy_seed_repeats <= 0:
        raise ValueError("policy_seed_repeats must be positive")
    contexts = []
    for task in sorted(manifest["tasks"], key=lambda value: value["task_key"]):
        task_index = int(task["task_index"])
        if not 0 <= task_index < 10:
            raise ValueError(f"invalid frozen task_index: {task_index}")
        for init_state_id in task["splits"][split]:
            for repeat in range(policy_seed_repeats):
                seed_material = (
                    f"raw-eval-v1\0{manifest['manifest_sha256']}\0{split}\0"
                    f"{task['task_key']}\0{init_state_id}\0{repeat}"
                )
                digest = hashlib.sha256(seed_material.encode()).digest()
                contexts.append(
                    EvaluationContext(
                        suite=str(task["suite"]),
                        task_id=str(task["task_id"]),
                        task_index=task_index,
                        perturbation_variant=str(task["perturbation_variant"]),
                        init_state_id=str(init_state_id),
                        env_seed=int.from_bytes(digest[:4], "big"),
                        policy_seed=int.from_bytes(digest[4:12], "big") % (2**63 - 1),
                    )
                )
    expected = {"policy_alpha_selection": 100, "policy_regression": 250}[split]
    if len(contexts) != expected * policy_seed_repeats:
        raise ValueError(
            f"frozen {split} view has {len(contexts)} episodes, expected "
            f"{expected * policy_seed_repeats}"
        )
    return tuple(contexts)


def contexts_from_authorized_final_seal(
    manifest: Mapping[str, Any],
    authorized_contexts: Sequence[Mapping[str, Any]],
) -> tuple[EvaluationContext, ...]:
    """Materialize the 500 final contexts only after ``FinalSealGuard.open``."""

    expected: dict[tuple[str, str, str, str], int] = {}
    for task in manifest["tasks"]:
        for init_state_id in task["splits"]["policy_final_sealed"]:
            key = (
                str(task["suite"]),
                str(task["task_id"]),
                str(task["perturbation_variant"]),
                str(init_state_id),
            )
            expected[key] = int(task["task_index"])
    provided = {
        (
            str(value["suite"]),
            str(value["task_id"]),
            str(value["perturbation_variant"]),
            str(value["init_state_id"]),
        ): int(value["task_index"])
        for value in authorized_contexts
    }
    if len(provided) != len(authorized_contexts):
        raise ValueError("authorized final context bank contains duplicates")
    if provided != expected or len(expected) != 500:
        raise ValueError("authorized context bank is not the exact final seal")
    contexts = []
    for key in sorted(expected):
        seed_material = (
            f"deployed-final-v1\0{manifest['manifest_sha256']}\0"
            + "\0".join(key)
        )
        digest = hashlib.sha256(seed_material.encode()).digest()
        contexts.append(
            EvaluationContext(
                suite=key[0],
                task_id=key[1],
                task_index=expected[key],
                perturbation_variant=key[2],
                init_state_id=key[3],
                env_seed=int.from_bytes(digest[:4], "big"),
                policy_seed=int.from_bytes(digest[4:12], "big") % (2**63 - 1),
            )
        )
    return tuple(contexts)


class RawPolicyEvaluator:
    def __init__(
        self,
        *,
        executor: EpisodeExecutor,
        ledger_path: Path,
        manifest_hash: str,
        max_workers: int = 1,
    ) -> None:
        self.executor = executor
        self.ledger = EpisodeLedger(Path(ledger_path))
        self.manifest_hash = str(manifest_hash)
        self.max_workers = int(max_workers)
        if self.max_workers <= 0:
            raise ValueError("max_workers must be positive")

    def evaluate(
        self,
        *,
        policy_id: str,
        checkpoint_path: Path,
        checkpoint_digest: str,
        contexts: Sequence[EvaluationContext],
        metric_role: str = "promotion_raw",
        raw_profile: Mapping[str, object] | None = None,
        require_raw_profile: bool = True,
        evaluation_profile: Mapping[str, Any] | None = None,
    ) -> PolicyEvaluationSummary:
        profile = dict(
            raw_profile
            or {
                "use_guidance": False,
                "mode_gate.enabled": False,
                "use_vlm_stage_recognition": False,
            }
        )
        if require_raw_profile:
            assert_raw_profile(profile)
        profile_value = {
            "raw_profile": profile,
            "evaluation_profile": dict(evaluation_profile or {}),
            "require_raw_profile": bool(require_raw_profile),
        }
        profile_hash = hashlib.sha256(
            json.dumps(profile_value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        existing = {
            item["episode_key"]: item
            for item in self.ledger.events.iter_valid()
            if item.get("policy_id") == policy_id
            and item.get("metric_role") == metric_role
            and item.get("manifest_hash") == self.manifest_hash
            and item.get("evaluation_profile_hash") == profile_hash
        }
        pending = [
            context
            for context in contexts
            if _ledger_key(metric_role, policy_id, context, profile_hash) not in existing
        ]

        def run(context: EvaluationContext) -> tuple[EvaluationContext, RawEpisodeResult]:
            value = self.executor(policy_id, Path(checkpoint_path), context)
            if isinstance(value, bool):
                value = RawEpisodeResult(value)
            return context, value

        if self.max_workers == 1:
            completed = [run(context) for context in pending]
        else:
            completed = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {pool.submit(run, context): context for context in pending}
                for future in as_completed(futures):
                    completed.append(future.result())
        for context, result in completed:
            key = _ledger_key(metric_role, policy_id, context, profile_hash)
            self.ledger.append(
                key,
                {
                    "policy_id": policy_id,
                    "checkpoint_digest": checkpoint_digest,
                    "manifest_hash": self.manifest_hash,
                    "metric_role": metric_role,
                    "evaluation_profile": profile_value,
                    "evaluation_profile_hash": profile_hash,
                    "context": asdict(context),
                    "success": bool(result.success),
                    "steps": result.steps,
                    "output_dir": result.output_dir,
                    "metadata": dict(result.metadata),
                },
            )
        rows_by_key = {
            item["episode_key"]: item
            for item in self.ledger.events.iter_valid()
            if item.get("policy_id") == policy_id
            and item.get("metric_role") == metric_role
            and item.get("manifest_hash") == self.manifest_hash
            and item.get("evaluation_profile_hash") == profile_hash
        }
        ordered = []
        for context in contexts:
            key = _ledger_key(metric_role, policy_id, context, profile_hash)
            row = rows_by_key.get(key)
            if row is None:
                raise RuntimeError(f"missing raw evaluation row {key}")
            if row["checkpoint_digest"] != checkpoint_digest:
                raise ValueError("policy ID reused with a different checkpoint digest")
            ordered.append(row)
        per_task_values: dict[str, list[int]] = {}
        vector = []
        for context, row in zip(contexts, ordered):
            value = int(bool(row["success"]))
            vector.append(value)
            per_task_values.setdefault(context.task_key, []).append(value)
        per_task = {
            task: sum(values) / len(values)
            for task, values in sorted(per_task_values.items())
        }
        successes = sum(vector)
        return PolicyEvaluationSummary(
            policy_id=policy_id,
            checkpoint_digest=checkpoint_digest,
            metric_role=metric_role,
            successes=successes,
            episodes=len(vector),
            micro_sr=successes / len(vector),
            wilson95=wilson_interval(successes, len(vector)),
            macro_sr=sum(per_task.values()) / len(per_task),
            per_task_sr=per_task,
            raw_vector=tuple(vector),
            evaluation_profile_hash=profile_hash,
        )


class HydraRawEpisodeExecutor:
    """One-process reference executor; a scheduler may wrap it for 32–64 workers."""

    def __init__(
        self,
        *,
        repo_root: Path,
        python_executable: Path,
        output_root: Path,
        timeout_seconds: float = 1800.0,
        extra_overrides: Sequence[str] = (),
    ) -> None:
        self.repo_root = Path(repo_root)
        self.python_executable = Path(python_executable)
        self.output_root = Path(output_root)
        self.timeout_seconds = float(timeout_seconds)
        self.extra_overrides = tuple(extra_overrides)

    def __call__(
        self, policy_id: str, checkpoint_path: Path, context: EvaluationContext
    ) -> RawEpisodeResult:
        runtime_suite = runtime_suite_name(context.suite, context.perturbation_variant)
        run_dir = self.output_root / policy_id / context.episode_key
        run_dir.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.python_executable),
            "main.py",
            "backend=libero",
            f"backend.libero.suite_name={runtime_suite}",
            f"backend.libero.task_ids_filter=[{context.task_index}]",
            "main.episode_num=1",
            f"main.init_state_id={context.init_state_id}",
            f"main.env_seed={context.env_seed}",
            f"main.policy_seed={context.policy_seed}",
            "main.use_guidance=false",
            "main.use_vlm_stage_recognition=false",
            "mode_gate.enabled=false",
            "policy.type=pi05",
            f"policy.pi05.pretrained_path={checkpoint_path}",
            f"hydra.run.dir={run_dir}",
            *self.extra_overrides,
        ]
        environment = dict(os.environ)
        environment.setdefault("PYOPENGL_PLATFORM", "egl")
        environment.setdefault("MUJOCO_GL", "egl")
        process = subprocess.run(
            command,
            cwd=self.repo_root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=self.timeout_seconds,
            check=False,
        )
        (run_dir / "executor.log").write_text(process.stdout, encoding="utf-8")
        if process.returncode != 0:
            raise RuntimeError(
                f"raw episode failed with exit {process.returncode}; see {run_dir / 'executor.log'}"
            )
        result_path = run_dir / "results.txt"
        if not result_path.is_file():
            raise RuntimeError(f"raw episode produced no results.txt under {run_dir}")
        text = result_path.read_text(encoding="utf-8")
        matches = re.findall(r"Success count:\s*(\d+)\s*/\s*(\d+)", text)
        if not matches or matches[-1][1] != "1":
            raise RuntimeError(f"cannot parse one-episode raw result from {result_path}")
        return RawEpisodeResult(
            success=matches[-1][0] == "1",
            output_dir=str(run_dir),
            metadata={"runtime_suite": runtime_suite, "returncode": process.returncode},
        )


def _ledger_key(
    metric_role: str,
    policy_id: str,
    context: EvaluationContext,
    evaluation_profile_hash: str,
) -> str:
    return hashlib.sha256(
        f"{metric_role}\0{policy_id}\0{evaluation_profile_hash}\0{context.episode_key}".encode()
    ).hexdigest()


def runtime_suite_name(suite: str, variant: str) -> str:
    if variant == "base":
        return suite
    suffix = {
        "use_object": "object",
        "use_swap": "swap",
        "use_language": "lan",
        "use_task": "task",
        "use_environment": "env",
    }.get(variant)
    if suffix is None:
        raise ValueError(
            f"variant {variant!r} requires an explicit pinned runtime suite mapping"
        )
    return f"{suite}_{suffix}"


__all__ = [
    "EvaluationContext",
    "HydraRawEpisodeExecutor",
    "PolicyEvaluationSummary",
    "RawEpisodeResult",
    "RawPolicyEvaluator",
    "contexts_from_manifest",
    "contexts_from_authorized_final_seal",
    "runtime_suite_name",
]
