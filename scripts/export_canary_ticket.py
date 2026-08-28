#!/usr/bin/env python
"""Export every replay-valid ticket demo to an isolated canary dataset.

This intentionally does not relax or overwrite the production curation result.
The resulting dataset is marked canary-only and cannot be promoted by the
production slow-loop worker.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import h5py


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.data_pipeline import export_lerobot_v3  # noqa: E402
from mode_gate.io_utils import atomic_write_json, sha256_file  # noqa: E402


_DEMO = re.compile(r"^demo-(\d{3})-[^.]+\.hdf5$")


def _steps(path: Path) -> int:
    with h5py.File(path, "r") as handle:
        return int(handle["action"].shape[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--max-episodes", type=int, default=0)
    args = parser.parse_args()

    ticket = json.loads(args.ticket.read_text(encoding="utf-8"))
    selected: dict[int, Path] = {}
    rejected: list[dict[str, str]] = []
    for directory in (args.ticket.parent / "raw", args.ticket.parent / "rejected"):
        for path in sorted(directory.glob("demo-*.hdf5")):
            match = _DEMO.match(path.name)
            if match is None:
                continue
            index = int(match.group(1))
            with h5py.File(path, "r") as handle:
                valid = all(
                    (
                        bool(handle.attrs.get("explicit_success", False)),
                        bool(handle.attrs.get("simulator_success", False)),
                        bool(handle.attrs.get("replay_validated", False)),
                        int(handle["simulator_state"].shape[0])
                        == int(handle["action"].shape[0]) + 1,
                        int(handle["observation/state"].shape[0])
                        == int(handle["action"].shape[0]) + 1,
                    )
                )
            if not valid:
                rejected.append({"path": str(path), "reason": "not_replay_valid"})
                continue
            if index in selected:
                raise ValueError(f"duplicate replay-valid collection index {index}")
            selected[index] = path
    if not selected:
        raise RuntimeError("ticket has no replay-valid demonstrations")

    complete = args.output / "meta" / "info.json"
    if args.output.exists() and not complete.is_file():
        raise RuntimeError(f"refusing to overwrite incomplete export: {args.output}")
    all_paths = tuple(
        sorted(selected.values(), key=lambda path: (_steps(path), path.name))
    )
    paths = (
        all_paths[: args.max_episodes]
        if int(args.max_episodes) > 0
        else all_paths
    )
    for path in all_paths[len(paths) :]:
        rejected.append({"path": str(path), "reason": "canary_episode_budget"})
    if not complete.is_file():
        export_lerobot_v3(paths, output_root=args.output, repo_id=args.repo_id)

    manifest = {
        "schema_version": "ticket-canary-dataset-v1",
        "canary_only": True,
        "production_eligible": False,
        "ticket_id": ticket["ticket_id"],
        "ticket_sha256": sha256_file(args.ticket),
        "repo_id": args.repo_id,
        "dataset_root": str(args.output.resolve()),
        "episodes": len(paths),
        "transitions": sum(_steps(path) for path in paths),
        "selected": [
            {"path": str(path.resolve()), "sha256": sha256_file(path)}
            for path in paths
        ],
        "excluded": rejected,
        "selection": "explicit_success+simulator_success+fresh_replay_validated",
    }
    atomic_write_json(args.output.parent / "canary_dataset_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
