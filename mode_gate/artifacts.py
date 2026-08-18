"""NPZ/JSON/PNG session artifacts for audit and later expansion."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
import re
from threading import Lock
from typing import Any

import numpy as np

from .types import (
    ControllerStatus,
    ExpansionRequest,
    GateContext,
    PlannerDecision,
    RoundEvidence,
    VerifierEvidence,
)


class ArtifactStore:
    def __init__(self, root: Path, context: GateContext) -> None:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", context.context_id)
        self.session_dir = Path(root) / safe_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.session_dir / "session_manifest.json"
        self._lock = Lock()
        self._manifest: dict[str, Any] = {
            "context": {
                "context_id": context.context_id,
                "task_instruction": context.task_instruction,
                "task_stage": context.task_stage,
                "metadata": _jsonable(context.metadata),
            },
            "rounds": [],
            "verifier_evidence": [],
            "status": "RUNNING",
        }
        self._write_manifest()

    def round_dir(self, round_id: int) -> Path:
        path = self.session_dir / f"round_{round_id:03d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_round_analysis(self, evidence: RoundEvidence) -> None:
        round_dir = self.round_dir(evidence.round_id)
        np.savez_compressed(
            round_dir / "analysis.npz",
            actions=evidence.action_batch.actions,
            positions=evidence.trajectories.positions,
            orientations=evidence.trajectories.orientations,
            grippers=evidence.trajectories.grippers,
            normalized_positions=evidence.normalized_positions,
            normalized_rotvecs=evidence.normalized_rotvecs,
            normalized_grippers=evidence.normalized_grippers,
            descriptors=evidence.descriptors,
            reduced_descriptors=evidence.reduced_descriptors,
            labels=evidence.labels,
            responsibilities=evidence.responsibilities,
        )
        metadata = {
            "context_id": evidence.context_id,
            "round_id": evidence.round_id,
            "checkpoint_id": evidence.checkpoint_id,
            "sample_ids": list(evidence.action_batch.sample_ids),
            "action_space": evidence.action_batch.action_space,
            "coordinate_frame": evidence.action_batch.coordinate_frame,
            "fit_degraded": evidence.fit_degraded,
            "fit_metadata": evidence.fit_metadata,
            "modes": [_jsonable(mode) for mode in evidence.modes],
        }
        _write_json(round_dir / "analysis.json", metadata)
        with self._lock:
            self._manifest["rounds"].append(
                {
                    "round_id": evidence.round_id,
                    "checkpoint_id": evidence.checkpoint_id,
                    "analysis": str((round_dir / "analysis.npz").relative_to(self.session_dir)),
                    "metadata": str((round_dir / "analysis.json").relative_to(self.session_dir)),
                    "mode_cards": [
                        str(mode.card_path.relative_to(self.session_dir))
                        for mode in evidence.modes
                    ],
                }
            )
            self._write_manifest()

    def save_planner_decision(self, round_id: int, decision: PlannerDecision) -> None:
        path = self.round_dir(round_id) / "planner_decision.json"
        _write_json(path, _jsonable(decision))
        with self._lock:
            for item in self._manifest["rounds"]:
                if item["round_id"] == round_id:
                    item["planner_decision"] = str(path.relative_to(self.session_dir))
                    break
            self._write_manifest()

    def save_verifier_evidence(
        self,
        round_id: int,
        evidence: VerifierEvidence,
    ) -> None:
        path = self.round_dir(round_id) / f"verifier_{evidence.mode_id}.json"
        _write_json(path, _jsonable(evidence))
        with self._lock:
            self._manifest["verifier_evidence"].append(
                {
                    "round_id": round_id,
                    "mode_id": evidence.mode_id,
                    "path": str(path.relative_to(self.session_dir)),
                }
            )
            self._write_manifest()

    def save_expansion_request(self, request: ExpansionRequest) -> Path:
        path = self.session_dir / "expansion_request.json"
        _write_json(path, request)
        with self._lock:
            self._manifest["expansion_request"] = str(path.relative_to(self.session_dir))
            self._write_manifest()
        return path

    def finalize(self, status: ControllerStatus, error: str | None = None) -> None:
        with self._lock:
            self._manifest["status"] = status.value
            if error is not None:
                self._manifest["error"] = error
            self._write_manifest()

    def record_background_error(
        self,
        round_id: int,
        mode_id: str,
        error: Exception,
    ) -> None:
        with self._lock:
            self._manifest.setdefault("background_errors", []).append(
                {
                    "round_id": round_id,
                    "mode_id": mode_id,
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            self._write_manifest()

    def _write_manifest(self) -> None:
        _write_json(self.manifest_path, self._manifest)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_jsonable(value), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
