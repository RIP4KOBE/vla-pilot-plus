"""Small atomic/fsync primitives shared by the persistent slow loop."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterator

import fcntl


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


class AtomicJsonl:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def append(self, event: dict[str, Any], *, idempotency_key: str = "event_id") -> bool:
        event_id = str(event.get(idempotency_key, ""))
        if not event_id:
            raise ValueError(f"event requires {idempotency_key}")
        encoded = (
            json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if any(
                str(item.get(idempotency_key, "")) == event_id
                for item in self.iter_valid()
            ):
                return False
            with self.path.open("ab", buffering=0) as stream:
                stream.write(encoded)
                os.fsync(stream.fileno())
            _fsync_directory(self.path.parent)
            return True

    def iter_valid(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        data = self.path.read_bytes()
        lines = data.splitlines(keepends=True)
        for index, raw in enumerate(lines):
            complete = raw.endswith(b"\n")
            try:
                yield json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                if index == len(lines) - 1 and not complete:
                    return
                raise ValueError(f"corrupt JSONL record {index + 1} in {self.path}")

    def read_all(self) -> list[dict[str, Any]]:
        return list(self.iter_valid())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = ["AtomicJsonl", "atomic_write_json", "sha256_file"]
