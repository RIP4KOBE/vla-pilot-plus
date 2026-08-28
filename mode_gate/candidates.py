"""Deterministic expansion and REUSE candidate checkpoint composition."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .checkpoint_math import checkpoint_digest, compose_policy
from .io_utils import atomic_write_json


V2_LANGUAGE_ONLY = "v2_language_only"
RETAIN_UNIFORM = "retain_uniform"


@dataclass(frozen=True)
class DeltaLineageEntry:
    delta_id: str
    path: str
    alpha_v: float = 1.0
    alpha_l: float = 1.0
    alpha_a: float = 1.0
    merge_method: str = V2_LANGUAGE_ONLY

    def __post_init__(self) -> None:
        if not self.delta_id:
            raise ValueError("delta_id must be non-empty")
        alphas = (float(self.alpha_v), float(self.alpha_l), float(self.alpha_a))
        if any(not 0.0 <= value <= 1.0 for value in alphas):
            raise ValueError("all alpha values must be in [0, 1]")
        if self.merge_method == V2_LANGUAGE_ONLY:
            if self.alpha_v != 1.0 or self.alpha_a != 1.0:
                raise ValueError("v2 fixes alpha_v=alpha_a=1")
        elif self.merge_method == RETAIN_UNIFORM:
            if not self.alpha_v == self.alpha_l == self.alpha_a:
                raise ValueError("RETAIN requires one uniform alpha for all groups")
        else:
            raise ValueError(f"unsupported merge_method {self.merge_method!r}")
        if not Path(self.path).exists():
            raise FileNotFoundError(self.path)

    @property
    def alpha_map(self) -> dict[str, float]:
        return {
            "vision": float(self.alpha_v),
            "language": float(self.alpha_l),
            "action": float(self.alpha_a),
        }


def compose_expansion_candidates(
    *,
    theta0_checkpoint: Path,
    parent_policy_id: str,
    accepted_lineage: Sequence[DeltaLineageEntry],
    new_delta_id: str,
    new_delta_path: Path,
    output_root: Path,
    alpha_l_values: Sequence[float] = (0.2, 0.4, 0.6, 0.8),
) -> dict[str, Any]:
    accepted = tuple(accepted_lineage)
    if new_delta_id in {item.delta_id for item in accepted}:
        raise ValueError("new expansion delta already appears in accepted lineage")
    alphas = tuple(sorted({round(float(value), 8) for value in alpha_l_values}))
    if alphas != (0.2, 0.4, 0.6, 0.8):
        raise ValueError("expansion candidate grid is frozen at 0.2/0.4/0.6/0.8")
    base = [asdict(item) for item in accepted]
    return _compose_grid(
        theta0_checkpoint=theta0_checkpoint,
        parent_policy_id=parent_policy_id,
        base_lineage=base,
        target_delta_id=new_delta_id,
        target_delta_path=Path(new_delta_path),
        target_alphas=alphas,
        candidate_kind="EXPANSION",
        target_merge_method=V2_LANGUAGE_ONLY,
        output_root=output_root,
    )


def compose_retain_expansion_candidates(
    *,
    theta0_checkpoint: Path,
    parent_policy_id: str,
    accepted_lineage: Sequence[DeltaLineageEntry],
    new_delta_id: str,
    new_delta_path: Path,
    output_root: Path,
    alpha_values: Sequence[float] = (0.2, 0.4, 0.6, 0.8),
) -> dict[str, Any]:
    """Compose the Always-Expansion + RETAIN control.

    For the newly trained task vector this implements the paper/control
    equation exactly: ``parent + alpha * (theta_ft - parent)``.  The same
    scalar is applied to vision, language, and action tensors.  Prior accepted
    lineage entries retain their original, immutable alpha maps.
    """

    accepted = tuple(accepted_lineage)
    if new_delta_id in {item.delta_id for item in accepted}:
        raise ValueError("new RETAIN delta already appears in accepted lineage")
    alphas = tuple(sorted({round(float(value), 8) for value in alpha_values}))
    if alphas != (0.2, 0.4, 0.6, 0.8):
        raise ValueError("RETAIN candidate grid is frozen at 0.2/0.4/0.6/0.8")
    return _compose_grid(
        theta0_checkpoint=theta0_checkpoint,
        parent_policy_id=parent_policy_id,
        base_lineage=[asdict(item) for item in accepted],
        target_delta_id=new_delta_id,
        target_delta_path=Path(new_delta_path),
        target_alphas=alphas,
        candidate_kind="EXPANSION",
        target_merge_method=RETAIN_UNIFORM,
        output_root=output_root,
    )


def compose_reuse_candidates(
    *,
    theta0_checkpoint: Path,
    parent_policy_id: str,
    accepted_lineage: Sequence[DeltaLineageEntry],
    target_delta_id: str,
    output_root: Path,
    increments: Sequence[float] = (0.15, 0.30, 0.50),
) -> dict[str, Any]:
    accepted = tuple(accepted_lineage)
    matches = [item for item in accepted if item.delta_id == target_delta_id]
    if len(matches) != 1:
        raise KeyError(f"expected one REUSE delta {target_delta_id!r}")
    target = matches[0]
    if target.merge_method != V2_LANGUAGE_ONLY:
        raise ValueError("signature REUSE is undefined for RETAIN-uniform lineage")
    if 1.0 - target.alpha_l < 0.15 - 1e-12:
        raise ValueError("REUSE target has less than 0.15 language-alpha headroom")
    target_alphas = tuple(
        sorted(
            {
                round(min(1.0, target.alpha_l + float(increment)), 8)
                for increment in increments
                if min(1.0, target.alpha_l + float(increment)) > target.alpha_l
            }
        )
    )
    if not target_alphas:
        raise ValueError("REUSE produced no distinct alpha candidates")
    base = [asdict(item) for item in accepted]
    return _compose_grid(
        theta0_checkpoint=theta0_checkpoint,
        parent_policy_id=parent_policy_id,
        base_lineage=base,
        target_delta_id=target.delta_id,
        target_delta_path=Path(target.path),
        target_alphas=target_alphas,
        candidate_kind="REUSE",
        target_merge_method=V2_LANGUAGE_ONLY,
        output_root=output_root,
    )


def _compose_grid(
    *,
    theta0_checkpoint: Path,
    parent_policy_id: str,
    base_lineage: Sequence[Mapping[str, Any]],
    target_delta_id: str,
    target_delta_path: Path,
    target_alphas: Sequence[float],
    candidate_kind: str,
    target_merge_method: str,
    output_root: Path,
) -> dict[str, Any]:
    theta0_checkpoint = Path(theta0_checkpoint).resolve()
    target_delta_path = Path(target_delta_path).resolve()
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    entries = [DeltaLineageEntry(**dict(value)) for value in base_lineage]
    if len({item.delta_id for item in entries}) != len(entries):
        raise ValueError("accepted delta lineage contains duplicate IDs")
    input_value = {
        "schema_version": "candidate-compose-input-v1",
        "candidate_kind": candidate_kind,
        "theta0_checkpoint_digest": checkpoint_digest(theta0_checkpoint),
        "parent_policy_id": parent_policy_id,
        "base_lineage": [asdict(item) for item in entries],
        "target_delta_id": target_delta_id,
        "target_delta_path": str(target_delta_path),
        "target_delta_digest": checkpoint_digest(target_delta_path),
        "target_alphas": list(target_alphas),
        "target_merge_method": target_merge_method,
    }
    attempt_hash = _digest(input_value)
    candidates = []
    for alpha_l in target_alphas:
        if target_merge_method == RETAIN_UNIFORM:
            target_entry = DeltaLineageEntry(
                delta_id=target_delta_id,
                path=str(target_delta_path),
                alpha_v=float(alpha_l),
                alpha_l=float(alpha_l),
                alpha_a=float(alpha_l),
                merge_method=RETAIN_UNIFORM,
            )
        else:
            target_entry = DeltaLineageEntry(
                delta_id=target_delta_id,
                path=str(target_delta_path),
                alpha_l=float(alpha_l),
                merge_method=V2_LANGUAGE_ONLY,
            )
        if candidate_kind == "REUSE":
            lineage = [
                target_entry if item.delta_id == target_delta_id else item
                for item in entries
            ]
            if not any(item.delta_id == target_delta_id for item in entries):
                raise ValueError("REUSE target disappeared from accepted lineage")
        else:
            lineage = [*entries, target_entry]
        candidate_input = {
            **input_value,
            "target_alpha_l": float(alpha_l),
            "lineage": [asdict(item) for item in lineage],
        }
        policy_id = "policy_" + _digest(candidate_input)[:16]
        checkpoint_path = output_root / policy_id
        policy_metadata = {
            "schema_version": "candidate-policy-v1",
            "policy_id": policy_id,
            "parent_policy_id": parent_policy_id,
            "candidate_kind": candidate_kind,
            "target_delta_id": target_delta_id,
            "alpha_l": float(alpha_l),
            "alpha_map": target_entry.alpha_map,
            "merge_method": target_entry.merge_method,
            "lineage": [asdict(item) for item in lineage],
            "compose_input_sha256": _digest(candidate_input),
        }
        if checkpoint_path.exists():
            existing = json.loads(
                (checkpoint_path / "candidate.json").read_text(encoding="utf-8")
            )
            if any(existing.get(key) != value for key, value in policy_metadata.items()):
                raise ValueError(f"immutable candidate collision: {policy_id}")
            digest = checkpoint_digest(checkpoint_path)
            if existing.get("checkpoint_digest") != digest:
                raise ValueError(f"candidate checkpoint changed: {policy_id}")
        else:
            compose_policy(
                theta0_checkpoint,
                [(Path(item.path), item.alpha_map) for item in lineage],
                checkpoint_path,
                allow_uniform_alpha=any(
                    item.merge_method == RETAIN_UNIFORM for item in lineage
                ),
            )
            digest = checkpoint_digest(checkpoint_path)
            atomic_write_json(
                checkpoint_path / "candidate.json",
                {**policy_metadata, "checkpoint_digest": digest},
            )
        candidates.append(
            {
                "policy_id": policy_id,
                "checkpoint_path": str(checkpoint_path.resolve()),
                "checkpoint_digest": digest,
                "alpha_l": float(alpha_l),
                "candidate_kind": candidate_kind,
                "target_delta_id": target_delta_id,
                "alpha_map": target_entry.alpha_map,
                "merge_method": target_entry.merge_method,
            }
        )
    manifest = {
        "schema_version": "candidate-grid-v1",
        "attempt_hash": attempt_hash,
        "candidate_kind": candidate_kind,
        "parent_policy_id": parent_policy_id,
        "theta0_checkpoint_digest": input_value["theta0_checkpoint_digest"],
        "target_delta_id": target_delta_id,
        "target_delta_digest": input_value["target_delta_digest"],
        "candidates": candidates,
    }
    manifest_path = output_root / f"candidate_grid_{attempt_hash[:16]}.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("immutable candidate grid collision")
    else:
        atomic_write_json(manifest_path, manifest)
    return manifest


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


__all__ = [
    "DeltaLineageEntry",
    "compose_expansion_candidates",
    "compose_retain_expansion_candidates",
    "compose_reuse_candidates",
    "RETAIN_UNIFORM",
    "V2_LANGUAGE_ONLY",
]
