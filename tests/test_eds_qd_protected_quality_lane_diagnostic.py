from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import torch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/eds_qd_protected_quality_lane_diagnostic.py"
)
SPEC = importlib.util.spec_from_file_location("protected_quality_lane_diagnostic", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
diagnostic = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = diagnostic
SPEC.loader.exec_module(diagnostic)


def _entry(fingerprint: str, reward: float, x: float = 0.0, y: float = 0.0):
    return diagnostic.base.ReplayEntry(
        action=torch.tensor([reward], dtype=torch.float32),
        reward=reward,
        cost=-reward,
        descriptor=torch.tensor([x, y], dtype=torch.float32),
        fingerprint=fingerprint,
    )


def _bounds():
    return diagnostic.base._bounds([[-1.0, -1.0], [1.0, 1.0]])


def test_update_protects_quality_and_keeps_best_distinct_secondary():
    archive = diagnostic.ProtectedArchive()
    entries = [_entry("q", 3.0), _entry("s", 2.0), _entry("low", 1.0)]
    cells = [10, 10, 10]
    archive.quality.visits[10] += 3
    archive.update(entries=entries, cell_ids=cells, bounds=_bounds())

    assert archive.quality.entries[10][0].fingerprint == "q"
    assert archive.secondary[10].fingerprint == "s"

    archive.quality.visits[10] += 2
    archive.update(
        entries=[_entry("new", 4.0), _entry("other", 3.5)],
        cell_ids=[10, 10],
        bounds=_bounds(),
    )

    assert archive.quality.entries[10][0].fingerprint == "new"
    assert archive.secondary[10].fingerprint == "other"


def test_rebin_secondary_cannot_create_cell_or_move_visits():
    archive = diagnostic.ProtectedArchive()
    archive.quality.entries = {0: [_entry("q", 3.0, 0.5, 0.5)]}
    archive.quality.visits[0] = 7
    archive.secondary = {0: _entry("s", 2.0, -0.5, -0.5)}
    bounds = _bounds()

    archive.rebin(bounds=bounds)

    quality_cells = set(archive.quality.entries)
    assert set(archive.secondary).issubset(quality_cells)
    assert int(archive.quality.visits.sum()) == 7
    assert all(
        entry.fingerprint != archive.quality.entries[cell][0].fingerprint
        for cell, entry in archive.secondary.items()
    )


def test_parent_allocation_keeps_cell_counts_anchor_and_final_quality_only():
    archive = diagnostic.ProtectedArchive()
    archive.quality.entries = {
        0: [_entry("q0", 4.0)],
        1: [_entry("q1", 2.0)],
    }
    archive.quality.visits[:2] = torch.tensor([20, 1])
    archive.secondary = {0: _entry("s0", 3.0), 1: _entry("s1", 1.0)}

    comparator = diagnostic.base.allocate_top2_parents(
        archive.quality, run_seed=0, episode=1, global_step=8, iter_idx=2
    )
    candidate = diagnostic.allocate_protected_parents(
        archive, run_seed=0, episode=1, global_step=8, iter_idx=2
    )

    assert candidate.total_cell_counts == comparator.total_cell_counts
    assert candidate.parent_fingerprints[0] == "q0"
    assert candidate.final_fingerprint == "q0"
    assert candidate.secondary_sparse_slots > 0
    assert len(candidate.parent_fingerprints) == 16
