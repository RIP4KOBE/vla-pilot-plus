"""One-time, resumable final-sealed evaluation coordinator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .checkpoint_math import checkpoint_digest
from .eval_manifest import FinalSealGuard
from .io_utils import atomic_write_json, sha256_file
from .policy_evaluator import (
    HydraRawEpisodeExecutor,
    RawPolicyEvaluator,
    contexts_from_authorized_final_seal,
)


@dataclass(frozen=True)
class FinalEvaluationSubject:
    subject_id: str
    checkpoint_path: str
    checkpoint_digest: str
    hydra_overrides: tuple[str, ...]
    evaluation_profile: Mapping[str, Any]
    require_raw_profile: bool = False

    def __post_init__(self) -> None:
        if not self.subject_id or not self.evaluation_profile:
            raise ValueError("final subject requires an ID and explicit frozen profile")
        checkpoint = Path(self.checkpoint_path)
        if not checkpoint.exists():
            raise FileNotFoundError(checkpoint)
        if checkpoint_digest(checkpoint) != self.checkpoint_digest:
            raise ValueError(f"checkpoint digest mismatch for {self.subject_id}")
        object.__setattr__(self, "hydra_overrides", tuple(self.hydra_overrides))
        object.__setattr__(self, "evaluation_profile", dict(self.evaluation_profile))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FinalEvaluationSubject":
        return cls(
            subject_id=str(value["subject_id"]),
            checkpoint_path=str(value["checkpoint_path"]),
            checkpoint_digest=str(value["checkpoint_digest"]),
            hydra_overrides=tuple(map(str, value.get("hydra_overrides", ()))),
            evaluation_profile=dict(value["evaluation_profile"]),
            require_raw_profile=bool(value.get("require_raw_profile", False)),
        )


ExecutorFactory = Callable[[FinalEvaluationSubject], HydraRawEpisodeExecutor]


class FinalSealedEvaluationCoordinator:
    def __init__(
        self,
        *,
        manifest: Mapping[str, Any],
        seal_guard: FinalSealGuard,
        ledger_path: Path,
        output_path: Path,
        executor_factory: ExecutorFactory,
        max_workers: int = 1,
    ) -> None:
        self.manifest = dict(manifest)
        self.seal_guard = seal_guard
        self.ledger_path = Path(ledger_path)
        self.output_path = Path(output_path)
        self.executor_factory = executor_factory
        self.max_workers = int(max_workers)
        if self.max_workers <= 0:
            raise ValueError("max_workers must be positive")

    def run(
        self,
        subjects: Sequence[FinalEvaluationSubject],
        *,
        purpose: str,
        authorization_token: str | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        subjects = tuple(subjects)
        subject_ids = tuple(item.subject_id for item in subjects)
        if not subjects or len(set(subject_ids)) != len(subject_ids):
            raise ValueError("final subjects must be non-empty and unique")
        if resume:
            authorized = self.seal_guard.resume(
                purpose=purpose, subjects=subject_ids
            )
        else:
            if authorization_token is None:
                raise PermissionError("opening final seal requires its one-time token")
            authorized = self.seal_guard.open(
                purpose=purpose,
                authorization_token=authorization_token,
                subjects=subject_ids,
            )
        contexts = contexts_from_authorized_final_seal(self.manifest, authorized)
        summaries = []
        for subject in subjects:
            evaluator = RawPolicyEvaluator(
                executor=self.executor_factory(subject),
                ledger_path=self.ledger_path,
                manifest_hash=str(self.manifest["manifest_sha256"]),
                max_workers=self.max_workers,
            )
            summary = evaluator.evaluate(
                policy_id=subject.subject_id,
                checkpoint_path=Path(subject.checkpoint_path),
                checkpoint_digest=subject.checkpoint_digest,
                contexts=contexts,
                metric_role="deployed_final",
                require_raw_profile=subject.require_raw_profile,
                evaluation_profile=subject.evaluation_profile,
            )
            summaries.append(
                {
                    "subject": asdict(subject),
                    "summary": asdict(summary),
                }
            )
        result = {
            "schema_version": "deployed-final-report-v1",
            "metric_role": "deployed_final",
            "manifest_sha256": self.manifest["manifest_sha256"],
            "purpose": purpose,
            "context_count": len(contexts),
            "subjects": summaries,
        }
        atomic_write_json(self.output_path, result)
        self.seal_guard.complete(
            purpose=purpose,
            subjects=subject_ids,
            result_path=self.output_path,
            result_sha256=sha256_file(self.output_path),
        )
        return result


def make_hydra_executor_factory(
    *,
    repo_root: Path,
    python_executable: Path,
    rollout_root: Path,
    timeout_seconds: float = 1800.0,
) -> ExecutorFactory:
    def build(subject: FinalEvaluationSubject) -> HydraRawEpisodeExecutor:
        return HydraRawEpisodeExecutor(
            repo_root=repo_root,
            python_executable=python_executable,
            output_root=Path(rollout_root) / subject.subject_id,
            timeout_seconds=timeout_seconds,
            extra_overrides=subject.hydra_overrides,
        )

    return build


__all__ = [
    "FinalEvaluationSubject",
    "FinalSealedEvaluationCoordinator",
    "make_hydra_executor_factory",
]
