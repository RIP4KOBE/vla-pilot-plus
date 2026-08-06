from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.qd_ed import (
    QDArchive,
    allocate_parent_slots,
    cell_ids,
    fingerprint_action,
    freeze_bounds,
    qd_descriptor,
)


def _actions(values: list[float]) -> torch.Tensor:
    return torch.stack(
        [torch.full((4, 5), value, dtype=torch.float64) for value in values]
    )


def test_target_relative_endpoint_xy_descriptor_uses_first_target():
    trajectories = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [1.5, 2.0, 3.0]],
            [[0.0, 0.0, 0.0], [-1.0, 0.5, 4.0]],
        ]
    )
    keypoints = torch.tensor([[1.0, 1.5, 9.0], [99.0, 99.0, 99.0]])

    descriptor = qd_descriptor(trajectories, keypoints)

    assert descriptor.dtype == torch.float32
    assert torch.equal(
        descriptor,
        torch.tensor([[0.5, 0.5], [-2.0, -1.0]], dtype=torch.float32),
    )


@pytest.mark.parametrize(
    ("grid_shape", "expected"),
    [((3, 3), [0, 0, 4, 8, 8, 2]), ((4, 4), [0, 0, 10, 15, 15, 3]), ((5, 5), [0, 0, 12, 24, 24, 4])],
)
def test_fixed_bounds_edges_and_overflow_clamp(grid_shape, expected):
    bounds = freeze_bounds(
        torch.tensor([[0.0, 0.0], [1.0, 1.0]]),
        quantiles=(0.0, 1.0),
        expand_fraction=0.0,
        min_axis_span_m=0.04,
    )
    descriptors = torch.tensor(
        [[0.0, 0.0], [-0.1, -0.2], [0.5, 0.5], [1.0, 1.0], [1.2, 1.3], [1.0, 0.0]]
    )

    ids, overflow = cell_ids(descriptors, bounds, grid_shape)

    assert ids.tolist() == expected
    assert overflow.tolist() == [False, True, False, False, True, False]
    assert bounds.checksum


@pytest.mark.parametrize("minimum_span", [0.04, 0.08, 0.12])
def test_zero_spread_population_uses_finite_minimum_span(minimum_span):
    descriptors = torch.full((16, 2), 0.25)
    bounds = freeze_bounds(
        descriptors,
        quantiles=(0.05, 0.95),
        expand_fraction=0.10,
        min_axis_span_m=minimum_span,
    )

    assert torch.isfinite(bounds.lo).all()
    assert torch.isfinite(bounds.hi).all()
    assert torch.allclose(
        bounds.hi - bounds.lo,
        torch.full((2,), minimum_span),
        atol=1e-7,
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda: qd_descriptor(torch.full((2, 3, 3), float("nan")), torch.zeros(1, 3)),
        lambda: qd_descriptor(torch.zeros(2, 3, 3), None),
        lambda: freeze_bounds(
            torch.tensor([[0.0, float("inf")]]),
            quantiles=(0.05, 0.95),
            expand_fraction=0.1,
            min_axis_span_m=0.08,
        ),
    ],
)
def test_descriptor_and_bounds_fail_closed(call):
    with pytest.raises((ValueError, FloatingPointError)):
        call()


def test_archive_batch_update_is_permutation_equivariant_and_detached():
    actions = _actions([1.0, 2.0, 3.0, 4.0]).requires_grad_(True)
    rewards = torch.tensor([1.0, 5.0, 2.0, 4.0])
    costs = -rewards
    descriptors = torch.tensor([[0.1, 0.1], [0.2, 0.2], [0.8, 0.8], [0.9, 0.9]])
    ids = torch.tensor([0, 0, 3, 3])

    archive = QDArchive(grid_shape=(2, 2))
    summary = archive.update(
        actions=actions,
        rewards=rewards,
        costs=costs,
        descriptors=descriptors,
        cell_ids=ids,
        source_iter=-1,
    )
    permuted = QDArchive(grid_shape=(2, 2))
    permutation = torch.tensor([3, 0, 2, 1])
    permuted.update(
        actions=actions[permutation],
        rewards=rewards[permutation],
        costs=costs[permutation],
        descriptors=descriptors[permutation],
        cell_ids=ids[permutation],
        source_iter=-1,
    )

    assert summary.insertions == 2
    assert summary.replacements == 0
    assert summary.rejections == 2
    assert summary.total == 4
    assert archive.snapshot() == permuted.snapshot()
    assert [entry.reward for entry in archive.entries.values()] == [5.0, 4.0]
    assert all(not entry.action.requires_grad and entry.action.grad_fn is None for entry in archive.entries.values())


def test_archive_replacement_rejection_monotonicity_and_global_best():
    archive = QDArchive(grid_shape=(2, 2))
    archive.update(
        actions=_actions([1.0, 2.0]),
        rewards=torch.tensor([1.0, 2.0]),
        costs=torch.tensor([-1.0, -2.0]),
        descriptors=torch.tensor([[0.1, 0.1], [0.9, 0.9]]),
        cell_ids=torch.tensor([0, 3]),
        source_iter=-1,
    )
    before = {cell: entry.reward for cell, entry in archive.entries.items()}

    summary = archive.update(
        actions=_actions([3.0, 4.0, 5.0]),
        rewards=torch.tensor([3.0, 1.0, 0.5]),
        costs=torch.tensor([-3.0, -1.0, -0.5]),
        descriptors=torch.tensor([[0.2, 0.2], [0.8, 0.8], [0.5, 0.5]]),
        cell_ids=torch.tensor([0, 3, 2]),
        source_iter=0,
        parent_cell_ids=torch.tensor([0, 3, 0]),
    )
    selected_cell, selected = archive.select_global_best()

    assert (summary.insertions, summary.replacements, summary.rejections) == (1, 1, 1)
    assert all(archive.entries[cell].reward >= reward for cell, reward in before.items())
    assert selected_cell == 0
    assert selected.reward == 3.0
    assert selected.fingerprint == fingerprint_action(_actions([3.0])[0])
    assert archive.elite_monotonicity_violation_count == 0
    assert archive.accounting_violation_count == 0


def test_exact_reward_tie_keeps_lexicographically_smallest_fingerprint():
    candidates = _actions([11.0, 12.0])
    fingerprints = [fingerprint_action(action) for action in candidates]
    archive = QDArchive(grid_shape=(2, 2))
    archive.update(
        actions=candidates,
        rewards=torch.tensor([7.0, 7.0]),
        costs=torch.tensor([-7.0, -7.0]),
        descriptors=torch.tensor([[0.1, 0.1], [0.2, 0.2]]),
        cell_ids=torch.tensor([0, 0]),
        source_iter=-1,
    )

    assert archive.entries[0].fingerprint == min(fingerprints)


def _occupied_archive(cell_count: int) -> QDArchive:
    archive = QDArchive(grid_shape=(4, 4))
    archive.update(
        actions=_actions([float(i) for i in range(cell_count)]),
        rewards=torch.arange(cell_count, dtype=torch.float32),
        costs=-torch.arange(cell_count, dtype=torch.float32),
        descriptors=torch.stack(
            [torch.tensor([float(i), 0.0]) for i in range(cell_count)]
        ),
        cell_ids=torch.arange(cell_count),
        source_iter=-1,
    )
    return archive


def test_uniform_parent_slots_are_balanced_deterministic_and_rng_isolated():
    archive = _occupied_archive(6)
    rng_before = torch.random.get_rng_state().clone()

    first = allocate_parent_slots(
        archive,
        population_size=16,
        sampling="uniform_cells",
        sparse_exponent=1.0,
        run_seed=0,
        episode=8,
        global_step=24,
        iter_idx=3,
    )
    second = allocate_parent_slots(
        archive,
        population_size=16,
        sampling="uniform_cells",
        sparse_exponent=1.0,
        run_seed=0,
        episode=8,
        global_step=24,
        iter_idx=3,
    )

    assert sum(first.slot_counts.values()) == 16
    assert max(first.slot_counts.values()) - min(first.slot_counts.values()) <= 1
    assert torch.equal(first.parent_cell_ids, second.parent_cell_ids)
    assert torch.equal(torch.random.get_rng_state(), rng_before)


def test_sparse_parent_slots_follow_inverse_visitation_largest_remainder():
    archive = _occupied_archive(3)
    archive.cumulative_visits[:] = 0
    archive.cumulative_visits[:3] = torch.tensor([0, 3, 7])

    allocation = allocate_parent_slots(
        archive,
        population_size=16,
        sampling="sparse_priority",
        sparse_exponent=1.0,
        run_seed=0,
        episode=0,
        global_step=0,
        iter_idx=0,
    )

    assert allocation.weights == pytest.approx({0: 1.0, 1: 0.25, 2: 0.125})
    assert allocation.slot_counts == {0: 12, 1: 3, 2: 1}
    assert sum(allocation.slot_counts.values()) == 16
    assert allocation.slot_counts[0] >= allocation.slot_counts[1] >= allocation.slot_counts[2]


@pytest.mark.parametrize("cell_count", [1, 16])
def test_parent_allocation_degenerate_occupied_counts_are_finite(cell_count):
    archive = _occupied_archive(cell_count)
    allocation = allocate_parent_slots(
        archive,
        population_size=16,
        sampling="uniform_cells",
        sparse_exponent=1.0,
        run_seed=0,
        episode=0,
        global_step=0,
        iter_idx=0,
    )

    assert allocation.parent_cell_ids.shape == (16,)
    assert set(allocation.parent_cell_ids.tolist()) == set(range(cell_count))


def test_ten_iterations_preserve_archive_and_fixed_evaluation_budget():
    archive = _occupied_archive(2)
    initial_bounds_token = copy.deepcopy(archive.snapshot())
    evaluations = 16
    for iteration in range(10):
        archive.update(
            actions=_actions([float(iteration)] * 16),
            rewards=torch.full((16,), float(iteration + 10)),
            costs=torch.full((16,), -float(iteration + 10)),
            descriptors=torch.zeros(16, 2),
            cell_ids=torch.zeros(16, dtype=torch.long),
            source_iter=iteration,
            parent_cell_ids=torch.zeros(16, dtype=torch.long),
        )
        evaluations += 16

    assert evaluations == 176
    assert 1 in archive.entries
    assert archive.entries[0].source_iter == 9
    assert initial_bounds_token[1]["fingerprint"] == archive.snapshot()[1]["fingerprint"]
    assert archive.accounting_violation_count == 0
