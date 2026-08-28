"""Immutable policy/verifier registry with CAS promotion and rollback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

import fcntl

from .io_utils import AtomicJsonl, atomic_write_json, sha256_file


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ActiveDeployment:
    deployment_revision: int
    policy_id: str
    controller_mode: str
    verifier_id: str | None
    manifest_hash: str
    transaction_id: str
    updated_at: str


class PolicyRegistry:
    def __init__(
        self, root: Path, *, artifact_install_mode: str = "copy"
    ) -> None:
        self.root = Path(root)
        if artifact_install_mode not in {"copy", "hardlink_canary"}:
            raise ValueError("artifact_install_mode must be copy or hardlink_canary")
        normalized_root = self.root.resolve()
        if artifact_install_mode == "hardlink_canary" and "/audit/canary/" not in (
            str(normalized_root) + "/"
        ):
            raise ValueError("hardlink_canary is restricted to an isolated audit/canary registry")
        self.artifact_install_mode = artifact_install_mode
        for relative in (
            "base/theta_0",
            "deltas",
            "policies",
            "verifiers",
            "attempts",
            ".staging",
        ):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        self.lock_path = self.root / ".lock"
        self.lineage = AtomicJsonl(self.root / "lineage.jsonl")

    def initialize_base(self, *, checkpoint_path: str, digest: str, metadata: dict) -> None:
        reference = self.root / "base/theta_0/ref.json"
        value = {
            "schema_version": "theta0-reference-v1",
            "checkpoint_path": checkpoint_path,
            "checkpoint_digest": digest,
            "metadata": metadata,
        }
        if reference.exists():
            existing = json.loads(reference.read_text(encoding="utf-8"))
            if existing != value:
                raise ValueError("theta0 registry reference is immutable")
            return
        atomic_write_json(reference, value)

    def install_artifact(self, kind: str, artifact_id: str, source: Path) -> Path:
        directory_name = {
            "delta": "deltas",
            "policy": "policies",
            "verifier": "verifiers",
            "attempt": "attempts",
        }.get(kind)
        if directory_name is None:
            raise ValueError(f"unsupported registry artifact kind {kind}")
        target = self.root / directory_name / artifact_id
        source = Path(source)
        if target.exists():
            if self.artifact_install_mode == "hardlink_canary":
                expected_manifest = _hardlink_tree_manifest(source, target)
                manifest_path = target / "registry_manifest.json"
                installed_manifest = (
                    json.loads(manifest_path.read_text(encoding="utf-8"))
                    if manifest_path.is_file()
                    else None
                )
                matches = installed_manifest == expected_manifest
            else:
                matches = _tree_manifest(target) == _tree_manifest(source)
            if not matches:
                raise ValueError(f"immutable artifact collision: {artifact_id}")
            return target
        staging = self.root / ".staging" / f"{artifact_id}.{uuid4().hex}"
        copy_function = (
            os.link
            if self.artifact_install_mode == "hardlink_canary"
            else _clone_or_copy
        )
        shutil.copytree(source, staging, copy_function=copy_function)
        tree_manifest = (
            _hardlink_tree_manifest(source, staging)
            if self.artifact_install_mode == "hardlink_canary"
            else _tree_manifest(staging)
        )
        atomic_write_json(staging / "registry_manifest.json", tree_manifest)
        os.replace(staging, target)
        return target

    def bootstrap_base_policy(
        self,
        *,
        checkpoint_path: Path,
        digest: str,
        metadata: dict[str, Any],
        policy_id: str,
        manifest_hash: str,
    ) -> ActiveDeployment:
        """Install theta0 as the first immutable policy and create revision 1."""

        from .checkpoint_math import checkpoint_digest

        checkpoint_path = Path(checkpoint_path).resolve()
        self.initialize_base(
            checkpoint_path=str(checkpoint_path),
            digest=str(digest),
            metadata=dict(metadata),
        )
        installed = self.install_artifact("policy", str(policy_id), checkpoint_path)
        installed_digest = (
            str(digest)
            if self.artifact_install_mode == "hardlink_canary"
            else checkpoint_digest(installed)
        )
        if installed_digest != str(digest):
            raise ValueError("installed theta0 policy digest does not match base reference")
        current = self.active()
        if current is None:
            return self.promote(
                policy_id=str(policy_id),
                verifier_id=None,
                controller_mode="fixed_budget_4",
                manifest_hash=str(manifest_hash),
                expected_revision=0,
                reason="bootstrap_theta0",
            )
        expected = (
            str(policy_id),
            "fixed_budget_4",
            None,
            str(manifest_hash),
        )
        actual = (
            current.policy_id,
            current.controller_mode,
            current.verifier_id,
            current.manifest_hash,
        )
        if actual != expected:
            raise RuntimeError("registry is already active with a different deployment")
        return current

    def active(self) -> ActiveDeployment | None:
        path = self.root / "active.json"
        if not path.exists():
            return None
        return ActiveDeployment(**json.loads(path.read_text(encoding="utf-8")))

    def promote(
        self,
        *,
        policy_id: str,
        verifier_id: str | None,
        controller_mode: str,
        manifest_hash: str,
        expected_revision: int,
        reason: str = "promotion",
    ) -> ActiveDeployment:
        if controller_mode not in {"learned_verifier", "fixed_budget_4"}:
            raise ValueError("invalid controller mode")
        if controller_mode == "learned_verifier" and verifier_id is None:
            raise ValueError("learned_verifier deployment requires verifier_id")
        if controller_mode == "fixed_budget_4" and verifier_id is not None:
            raise ValueError("fixed_budget_4 deployment must not name a verifier")
        if not (self.root / "policies" / policy_id).exists():
            raise FileNotFoundError(f"policy is not installed: {policy_id}")
        if verifier_id is not None and not (self.root / "verifiers" / verifier_id).exists():
            raise FileNotFoundError(f"verifier is not installed: {verifier_id}")
        if verifier_id is not None:
            verifier_manifest_path = (
                self.root / "verifiers" / verifier_id / "manifest.json"
            )
            if not verifier_manifest_path.is_file():
                raise ValueError("verifier artifact has no manifest.json")
            verifier_manifest = json.loads(
                verifier_manifest_path.read_text(encoding="utf-8")
            )
            if verifier_manifest.get("metadata", {}).get("policy_id") != policy_id:
                raise ValueError("verifier artifact policy_id does not match deployment policy")
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self.active()
            actual_revision = 0 if current is None else current.deployment_revision
            if actual_revision != expected_revision:
                raise RuntimeError(
                    f"active revision changed: expected {expected_revision}, got {actual_revision}"
                )
            transaction_id = uuid4().hex
            next_value = ActiveDeployment(
                deployment_revision=actual_revision + 1,
                policy_id=policy_id,
                controller_mode=controller_mode,
                verifier_id=verifier_id,
                manifest_hash=manifest_hash,
                transaction_id=transaction_id,
                updated_at=_now(),
            )
            transaction_path = self.root / "attempts" / f"transaction_{transaction_id}.json"
            atomic_write_json(
                transaction_path,
                {
                    "transaction_id": transaction_id,
                    "status": "PREPARED",
                    "previous": asdict(current) if current is not None else None,
                    "next": asdict(next_value),
                    "reason": reason,
                },
            )
            atomic_write_json(self.root / "active.json", asdict(next_value))
            atomic_write_json(
                transaction_path,
                {
                    "transaction_id": transaction_id,
                    "status": "COMMITTED",
                    "previous": asdict(current) if current is not None else None,
                    "next": asdict(next_value),
                    "reason": reason,
                },
            )
            lineage_event = {
                "event_id": f"deployment:{next_value.deployment_revision}",
                "event": "DEPLOYED",
                **asdict(next_value),
                "reason": reason,
            }
            self.lineage.append(lineage_event)
            return next_value

    def rollback(self, *, to_revision: int, expected_revision: int) -> ActiveDeployment:
        candidates = {
            int(item["deployment_revision"]): item
            for item in self.lineage.iter_valid()
            if item.get("event") == "DEPLOYED"
        }
        target = candidates.get(int(to_revision))
        if target is None:
            raise KeyError(f"unknown deployment revision {to_revision}")
        return self.promote(
            policy_id=target["policy_id"],
            verifier_id=target.get("verifier_id"),
            controller_mode=target["controller_mode"],
            manifest_hash=target["manifest_hash"],
            expected_revision=expected_revision,
            reason=f"rollback_to_revision_{to_revision}",
        )

    def recover_transactions(self) -> list[str]:
        active = self.active()
        recovered = []
        for path in sorted((self.root / "attempts").glob("transaction_*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("status") != "PREPARED":
                continue
            if active is not None and active.transaction_id == value["transaction_id"]:
                value["status"] = "COMMITTED"
                value["recovered_at"] = _now()
            else:
                value["status"] = "ABORTED"
                value["recovered_at"] = _now()
            atomic_write_json(path, value)
            recovered.append(value["transaction_id"])
        return recovered


def _tree_manifest(root: Path) -> dict[str, Any]:
    root = Path(root)
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "registry_manifest.json":
            continue
        # Policy artifacts are multi-gigabyte checkpoints.  Hash them as a
        # stream so registry install/promotion never materializes a whole
        # model file in host RAM.
        digest = sha256_file(path)
        files[str(path.relative_to(root))] = {"size": path.stat().st_size, "sha256": digest}
    return {"files": files}


def _hardlink_tree_manifest(source: Path, target: Path) -> dict[str, Any]:
    """Validate a canary hardlink tree without rereading multi-GB tensors."""

    source = Path(source)
    target = Path(target)
    trusted: dict[str, dict[str, Any]] = {}
    source_registry_manifest = source / "registry_manifest.json"
    if source_registry_manifest.is_file():
        value = json.loads(source_registry_manifest.read_text(encoding="utf-8"))
        trusted.update(
            {
                str(name): dict(metadata)
                for name, metadata in value.get("files", {}).items()
            }
        )
    source_meta = source / "meta.json"
    if source_meta.is_file():
        value = json.loads(source_meta.read_text(encoding="utf-8"))
        for shard in value.get("shards", ()):
            trusted[str(shard["file"])] = {
                "size": int(shard["size"]),
                "sha256": str(shard["sha256"]),
            }

    files = {}
    for path in sorted(target.rglob("*")):
        if not path.is_file() or path.name == "registry_manifest.json":
            continue
        relative = path.relative_to(target)
        source_path = source / relative
        if not source_path.is_file():
            raise ValueError(f"hardlink target has no source file: {relative}")
        source_stat = source_path.stat()
        target_stat = path.stat()
        if (source_stat.st_dev, source_stat.st_ino, source_stat.st_size) != (
            target_stat.st_dev,
            target_stat.st_ino,
            target_stat.st_size,
        ):
            raise ValueError(f"canary artifact is not an exact hardlink: {relative}")
        name = str(relative)
        metadata = trusted.get(name)
        if metadata is not None:
            # Sharded checkpoint metadata records tensor payload bytes, while
            # stat size also includes the safetensors header.  Exact source ↔
            # target size equality was already enforced via the hardlink tuple.
            digest = str(metadata["sha256"])
        else:
            digest = sha256_file(path)
        files[name] = {"size": target_stat.st_size, "sha256": digest}
    return {"files": files}


def _clone_or_copy(source: str, destination: str) -> str:
    """CoW-clone an artifact file when supported, otherwise copy it normally."""

    source_path = Path(source)
    destination_path = Path(destination)
    # Linux FICLONE creates an independent copy-on-write inode.  This keeps the
    # registry's immutable-file semantics while avoiding a redundant 7.5 GB
    # physical transfer when source and registry share a reflink filesystem.
    ficlone = 0x40049409
    try:
        with source_path.open("rb") as source_stream, destination_path.open(
            "wb"
        ) as destination_stream:
            fcntl.ioctl(destination_stream.fileno(), ficlone, source_stream.fileno())
        shutil.copystat(source_path, destination_path)
        return str(destination_path)
    except OSError as exc:
        if exc.errno not in {
            errno.EXDEV,
            errno.EINVAL,
            errno.ENOTTY,
            errno.EOPNOTSUPP,
            errno.ENOSYS,
        }:
            raise
    shutil.copy2(source_path, destination_path)
    return str(destination_path)


__all__ = ["ActiveDeployment", "PolicyRegistry"]
