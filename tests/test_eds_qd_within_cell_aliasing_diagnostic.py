from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest
import torch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/eds_qd_within_cell_aliasing_diagnostic.py"
)
SPEC = importlib.util.spec_from_file_location("within_cell_aliasing_diagnostic", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
diagnostic = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = diagnostic
SPEC.loader.exec_module(diagnostic)


def _entry(fingerprint: str, reward: float, x: float, y: float):
    return diagnostic.ReplayEntry(
        action=torch.tensor([reward], dtype=torch.float32),
        reward=reward,
        cost=-reward,
        descriptor=torch.tensor([x, y], dtype=torch.float32),
        fingerprint=fingerprint,
    )


def test_capacity_two_keeps_unique_reward_top_two_and_quality_winner():
    archive = diagnostic.ReplayArchive(capacity=2)
    summary = archive.update(
        entries=[
            _entry("c", 1.0, 0.0, 0.0),
            _entry("a", 3.0, 0.0, 0.0),
            _entry("b", 2.0, 0.0, 0.0),
            _entry("a", 3.0, 0.0, 0.0),
        ],
        cell_ids=[4, 4, 4, 4],
    )

    assert [entry.fingerprint for entry in archive.entries[4]] == ["a", "b"]
    assert summary.total == 4
    assert summary.accepted_fingerprints == ("a", "b")
    assert archive.quality_entries()[4].fingerprint == "a"


def test_capacity_two_rebin_follows_quality_entry_for_visits_and_retains_top_two():
    archive = diagnostic.ReplayArchive(capacity=2)
    archive.entries = {
        0: [_entry("a", 4.0, 0.8, 0.8), _entry("b", 1.0, -0.8, -0.8)],
        1: [_entry("c", 3.0, 0.7, 0.7), _entry("d", 2.0, 0.6, 0.6)],
    }
    archive.visits[0] = 7
    archive.visits[1] = 5

    summary = archive.rebin(
        entry_target_cells={"a": 6, "b": 1, "c": 6, "d": 6}
    )

    assert summary.visit_sum_before == summary.visit_sum_after == 12
    assert archive.visits[6].item() == 12
    assert [entry.fingerprint for entry in archive.entries[6]] == ["a", "c"]
    assert [entry.fingerprint for entry in archive.entries[1]] == ["b"]


def test_one_plus_fifteen_allocation_preserves_cell_counts_and_global_rng():
    archive = diagnostic.ReplayArchive(capacity=2)
    archive.entries = {
        0: [_entry("a", 4.0, 0.0, 0.0), _entry("b", 3.0, 0.0, 0.0)],
        1: [_entry("c", 2.0, 0.0, 0.0), _entry("d", 1.0, 0.0, 0.0)],
    }
    archive.visits[:2] = torch.tensor([20, 1])
    torch_before = torch.random.get_rng_state().clone()
    python_before = random.getstate()

    allocation = diagnostic.allocate_top2_parents(
        archive,
        run_seed=0,
        episode=2,
        global_step=8,
        iter_idx=3,
    )

    assert allocation.anchor_count == 1
    assert allocation.sparse_count == 15
    assert len(allocation.parent_fingerprints) == 16
    assert allocation.parent_fingerprints[0] == "a"
    assert sum(allocation.total_cell_counts.values()) == 16
    assert allocation.secondary_sparse_slots > 0
    assert torch.equal(torch_before, torch.random.get_rng_state())
    assert python_before == random.getstate()


def test_top_two_geometry_statistics_use_reward_order():
    trajectories = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[0.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
        ]
    )
    result = diagnostic.stream_collision_metrics(
        trajectories=trajectories,
        rewards=[3.0, 2.0, 1.0],
        fingerprints=["a", "b", "c"],
        cell_ids=[5, 5, 5],
    )

    assert result.colliding_cells == 1
    assert result.colliding_candidates == 3
    assert result.top_two_reward_gaps == pytest.approx([1.0])
    assert result.top_two_direction_distances[0] > 0.7


def test_mismatch_summary_does_not_conflate_capacity_one_and_two():
    summary = diagnostic.summarize_mismatch_counts(
        [
            {
                "capacity_one_mismatches": [],
                "capacity_two_mismatches": [
                    "iter4:quality_retention",
                    "iter5:global_best_retention",
                    "iter6:capacity_or_duplicate",
                ],
            }
        ]
    )

    assert summary == {
        "capacity_one_exact_mismatch_count": 0,
        "capacity_two_retention_mismatch_count": 2,
        "capacity_two_integrity_mismatch_count": 1,
    }


def test_manifest_validation_rejects_checksum_mismatch(tmp_path):
    trace = tmp_path / "trace.pt"
    trace.write_bytes(b"trace")
    manifest = {
        "artifact_root": str(tmp_path),
        "trace_count": 1,
        "candidate_stream_count": 11,
        "total_size_bytes": 5,
        "traces": [
            {
                "path": "trace.pt",
                "size_bytes": 5,
                "sha256": "0" * 64,
                "streams": 11,
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        diagnostic.load_input_specs(path)


def test_main_rejects_output_outside_owned_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        diagnostic,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {
                "input_manifest": tmp_path / "manifest.json",
                "core_qd": tmp_path / "qd.py",
                "core_qd_sha256": "0" * 64,
                "core_rdt": tmp_path / "rdt.py",
                "core_rdt_sha256": "0" * 64,
                "design": tmp_path / "design.md",
                "design_sha256": "0" * 64,
                "owned_root": tmp_path / "owned",
                "output": tmp_path / "outside.json",
            },
        )(),
    )
    with pytest.raises(ValueError, match="below the owned artifact root"):
        diagnostic.main()
