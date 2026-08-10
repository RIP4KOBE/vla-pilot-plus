from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Iterable

import torch
from torch import Tensor


def _finite_tensor(value: Tensor, *, name: str, ndim: int | None = None) -> Tensor:
    if not torch.is_tensor(value):
        raise ValueError(f"{name} must be a torch.Tensor")
    if ndim is not None and value.ndim != ndim:
        raise ValueError(f"{name} must have {ndim} dimensions")
    if not bool(torch.isfinite(value).all().item()):
        raise FloatingPointError(f"{name} contains nonfinite values")
    return value


def _grid_shape(value: Iterable[int]) -> tuple[int, int]:
    try:
        shape = tuple(value)
    except TypeError as exc:
        raise ValueError("QD grid shape must contain two integers") from exc
    if (
        len(shape) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in shape)
        or any(item <= 0 for item in shape)
    ):
        raise ValueError("QD grid shape must contain two positive integers")
    return int(shape[0]), int(shape[1])


def fingerprint_action(action: Tensor) -> str:
    """Hash canonical contiguous little-endian float32 action bytes."""
    _finite_tensor(action, name="QD action")
    canonical = action.detach().to(device="cpu", dtype=torch.float32).contiguous()
    array = canonical.numpy().astype("<f4", copy=False)
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def qd_descriptor(trajectories: Tensor, keypoints: Tensor | None) -> Tensor:
    """Return the frozen MVP BD: target-relative final EEF endpoint XY."""
    trajectories = _finite_tensor(
        trajectories, name="QD trajectories", ndim=3
    )
    if trajectories.shape[0] <= 0 or trajectories.shape[1] <= 0 or trajectories.shape[2] < 3:
        raise ValueError("QD trajectories must have shape (population, time, >=3)")
    if keypoints is None:
        raise ValueError("QD descriptor requires keypoints")
    keypoints = _finite_tensor(keypoints, name="QD keypoints")
    flat_target = keypoints.reshape(-1)
    if flat_target.numel() < 3:
        raise ValueError("QD keypoints must contain at least one 3D target")
    endpoint_xy = trajectories[:, -1, :2].detach().to(dtype=torch.float32)
    target_xy = flat_target[:2].detach().to(
        device=endpoint_xy.device, dtype=torch.float32
    )
    descriptor = endpoint_xy - target_xy.unsqueeze(0)
    if not bool(torch.isfinite(descriptor).all().item()):
        raise FloatingPointError("QD descriptor contains nonfinite values")
    return descriptor


@dataclass(frozen=True)
class QDBounds:
    lo: Tensor
    hi: Tensor
    checksum: str


def freeze_bounds(
    descriptors: Tensor,
    *,
    quantiles: tuple[float, float] | list[float],
    expand_fraction: float,
    min_axis_span_m: float,
) -> QDBounds:
    descriptors = _finite_tensor(
        descriptors, name="QD initial descriptors", ndim=2
    ).detach().to(dtype=torch.float32)
    if descriptors.shape[0] <= 0 or descriptors.shape[1] != 2:
        raise ValueError("QD initial descriptors must have shape (population, 2)")
    if not isinstance(quantiles, (tuple, list)) or len(quantiles) != 2:
        raise ValueError("QD bounds quantiles must contain two values")
    q_lo, q_hi = (float(quantiles[0]), float(quantiles[1]))
    if not all(math.isfinite(value) for value in (q_lo, q_hi)) or not (
        0.0 <= q_lo < q_hi <= 1.0
    ):
        raise ValueError("QD bounds quantiles must satisfy 0 <= lo < hi <= 1")
    expand_fraction = float(expand_fraction)
    min_axis_span_m = float(min_axis_span_m)
    if not math.isfinite(expand_fraction) or expand_fraction < 0.0:
        raise ValueError("QD bounds expand fraction must be finite and nonnegative")
    if not math.isfinite(min_axis_span_m) or min_axis_span_m <= 0.0:
        raise ValueError("QD minimum axis span must be finite and positive")

    q_values = torch.tensor(
        [q_lo, q_hi], device=descriptors.device, dtype=descriptors.dtype
    )
    quantile_values = torch.quantile(descriptors, q_values, dim=0)
    raw_span = quantile_values[1] - quantile_values[0]
    lo = quantile_values[0] - expand_fraction * raw_span
    hi = quantile_values[1] + expand_fraction * raw_span
    too_small = (hi - lo) < min_axis_span_m
    if bool(too_small.any().item()):
        center = torch.quantile(descriptors, 0.5, dim=0)
        half_span = 0.5 * min_axis_span_m
        lo = torch.where(too_small, center - half_span, lo)
        hi = torch.where(too_small, center + half_span, hi)
    if not bool(torch.isfinite(lo).all().item()) or not bool(
        torch.isfinite(hi).all().item()
    ):
        raise FloatingPointError("QD bounds contain nonfinite values")
    if not bool(((hi - lo) > 0.0).all().item()):
        raise ValueError("QD bounds must have positive span on both axes")
    canonical_descriptors = sorted(
        descriptors.detach().cpu().tolist(), key=lambda row: (row[0], row[1])
    )
    payload = {
        "descriptors": canonical_descriptors,
        "quantiles": [q_lo, q_hi],
        "expand_fraction": expand_fraction,
        "min_axis_span_m": min_axis_span_m,
        "lo": lo.detach().cpu().tolist(),
        "hi": hi.detach().cpu().tolist(),
    }
    checksum = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return QDBounds(lo=lo.detach().clone(), hi=hi.detach().clone(), checksum=checksum)


def expand_bounds(
    bounds: QDBounds,
    descriptors: Tensor,
) -> tuple[QDBounds, bool]:
    """Causally expand bounds to include a finite current descriptor batch."""
    descriptors = _finite_tensor(
        descriptors, name="QD causal-envelope descriptors", ndim=2
    ).detach().to(dtype=torch.float32)
    if descriptors.shape[0] <= 0 or descriptors.shape[1] != 2:
        raise ValueError(
            "QD causal-envelope descriptors must have shape (population, 2)"
        )
    lo = _finite_tensor(bounds.lo, name="QD bounds lower").to(
        device=descriptors.device, dtype=descriptors.dtype
    )
    hi = _finite_tensor(bounds.hi, name="QD bounds upper").to(
        device=descriptors.device, dtype=descriptors.dtype
    )
    if lo.shape != (2,) or hi.shape != (2,) or not bool(((hi - lo) > 0).all().item()):
        raise ValueError("QD bounds must contain finite positive spans for two axes")
    expanded_lo = torch.minimum(lo, descriptors.amin(dim=0))
    expanded_hi = torch.maximum(hi, descriptors.amax(dim=0))
    changed = not (
        bool(torch.equal(expanded_lo, lo)) and bool(torch.equal(expanded_hi, hi))
    )
    if not changed:
        return bounds, False
    canonical_descriptors = sorted(
        descriptors.detach().cpu().tolist(), key=lambda row: (row[0], row[1])
    )
    payload = {
        "policy": "causal_envelope_v1",
        "previous_checksum": bounds.checksum,
        "descriptors": canonical_descriptors,
        "lo": expanded_lo.detach().cpu().tolist(),
        "hi": expanded_hi.detach().cpu().tolist(),
    }
    checksum = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return (
        QDBounds(
            lo=expanded_lo.detach().clone(),
            hi=expanded_hi.detach().clone(),
            checksum=checksum,
        ),
        True,
    )


def cell_ids(
    descriptors: Tensor,
    bounds: QDBounds,
    grid_shape: tuple[int, int] | list[int],
) -> tuple[Tensor, Tensor]:
    descriptors = _finite_tensor(
        descriptors, name="QD descriptors", ndim=2
    ).detach().to(dtype=torch.float32)
    if descriptors.shape[1] != 2:
        raise ValueError("QD descriptors must have shape (population, 2)")
    grid_x, grid_y = _grid_shape(grid_shape)
    lo = _finite_tensor(bounds.lo, name="QD bounds lower").to(
        device=descriptors.device, dtype=descriptors.dtype
    )
    hi = _finite_tensor(bounds.hi, name="QD bounds upper").to(
        device=descriptors.device, dtype=descriptors.dtype
    )
    if lo.shape != (2,) or hi.shape != (2,) or not bool(((hi - lo) > 0).all().item()):
        raise ValueError("QD bounds must contain finite positive spans for two axes")
    normalized = (descriptors - lo) / (hi - lo)
    overflow = ((descriptors < lo) | (descriptors > hi)).any(dim=1)
    cell_x = torch.floor(normalized[:, 0] * grid_x).to(dtype=torch.long)
    cell_y = torch.floor(normalized[:, 1] * grid_y).to(dtype=torch.long)
    cell_x = cell_x.clamp(0, grid_x - 1)
    cell_y = cell_y.clamp(0, grid_y - 1)
    return grid_x * cell_y + cell_x, overflow


def within_cell_endpoint_sse(descriptors: Tensor, assigned_cell_ids: Tensor) -> float:
    """Return candidate-normalized within-cell endpoint squared error."""
    descriptors = _finite_tensor(
        descriptors, name="QD endpoint-SSE descriptors", ndim=2
    ).detach().to(dtype=torch.float32)
    if descriptors.shape[0] <= 0 or descriptors.shape[1] != 2:
        raise ValueError("QD endpoint-SSE descriptors must have shape (population, 2)")
    if not torch.is_tensor(assigned_cell_ids):
        raise ValueError("QD endpoint-SSE cell ids must be a torch.Tensor")
    assigned = assigned_cell_ids.detach().to(
        device=descriptors.device, dtype=torch.long
    ).reshape(-1)
    if assigned.numel() != descriptors.shape[0]:
        raise ValueError("QD endpoint-SSE cell ids must match descriptor count")
    total = torch.zeros((), device=descriptors.device, dtype=torch.float32)
    for assigned_cell in torch.unique(assigned, sorted=True):
        points = descriptors[assigned == assigned_cell]
        centered = points - points.mean(dim=0, keepdim=True)
        total = total + centered.square().sum()
    return float((total / descriptors.shape[0]).detach().cpu().item())


@dataclass(frozen=True)
class QDArchiveEntry:
    action: Tensor
    reward: float
    cost: float
    descriptor_xy_m: Tensor
    fingerprint: str
    source_iter: int
    parent_cell_id: int | None
    insert_sequence: int


@dataclass(frozen=True)
class QDUpdateSummary:
    insertions: int
    replacements: int
    rejections: int
    total: int


@dataclass(frozen=True)
class QDRebinSummary:
    occupied_before: int
    occupied_after: int
    collisions: int
    visit_sum_before: int
    visit_sum_after: int


@dataclass(frozen=True)
class QDParentAllocation:
    parent_cell_ids: Tensor
    parent_actions: Tensor
    parent_rewards: Tensor
    parent_costs: Tensor
    parent_fingerprints: tuple[str, ...]
    slot_counts: dict[int, int]
    weights: dict[int, float]


class QDArchive:
    def __init__(self, *, grid_shape: tuple[int, int] | list[int]) -> None:
        self.grid_shape = _grid_shape(grid_shape)
        self.cell_count = self.grid_shape[0] * self.grid_shape[1]
        self.entries: dict[int, QDArchiveEntry] = {}
        self.cumulative_visits = torch.zeros(self.cell_count, dtype=torch.long)
        self.accounting_violation_count = 0
        self.elite_monotonicity_violation_count = 0
        self._next_insert_sequence = 0

    @staticmethod
    def _candidate_better(
        reward: float,
        fingerprint: str,
        incumbent_reward: float,
        incumbent_fingerprint: str,
    ) -> bool:
        return reward > incumbent_reward or (
            reward == incumbent_reward and fingerprint < incumbent_fingerprint
        )

    def update(
        self,
        *,
        actions: Tensor,
        rewards: Tensor,
        costs: Tensor,
        descriptors: Tensor,
        cell_ids: Tensor,
        source_iter: int,
        parent_cell_ids: Tensor | None = None,
    ) -> QDUpdateSummary:
        actions = _finite_tensor(actions, name="QD candidate actions")
        if actions.ndim < 2 or actions.shape[0] <= 0:
            raise ValueError("QD candidate actions must be a nonempty batch")
        candidate_count = int(actions.shape[0])
        rewards = _finite_tensor(rewards, name="QD candidate rewards").reshape(-1)
        costs = _finite_tensor(costs, name="QD candidate costs").reshape(-1)
        descriptors = _finite_tensor(
            descriptors, name="QD candidate descriptors", ndim=2
        )
        if descriptors.shape != (candidate_count, 2):
            raise ValueError("QD candidate descriptors must have shape (population, 2)")
        if not torch.is_tensor(cell_ids):
            raise ValueError("QD candidate cell ids must be a torch.Tensor")
        cell_ids = cell_ids.detach().to(device="cpu", dtype=torch.long).reshape(-1)
        if rewards.numel() != candidate_count or costs.numel() != candidate_count or cell_ids.numel() != candidate_count:
            raise ValueError("QD candidate batch fields must have matching lengths")
        if bool(((cell_ids < 0) | (cell_ids >= self.cell_count)).any().item()):
            raise ValueError("QD candidate cell id is outside the configured grid")
        if parent_cell_ids is None:
            parent_values: list[int | None] = [None] * candidate_count
        else:
            if not torch.is_tensor(parent_cell_ids):
                raise ValueError("QD parent cell ids must be a torch.Tensor")
            parents = parent_cell_ids.detach().to(device="cpu", dtype=torch.long).reshape(-1)
            if parents.numel() != candidate_count:
                raise ValueError("QD parent cell ids must match candidate count")
            if bool(((parents < 0) | (parents >= self.cell_count)).any().item()):
                raise ValueError("QD parent cell id is outside the configured grid")
            parent_values = [int(value) for value in parents.tolist()]

        visits = torch.bincount(cell_ids, minlength=self.cell_count)
        self.cumulative_visits += visits
        grouped: dict[int, list[dict[str, object]]] = {}
        for index in range(candidate_count):
            cell = int(cell_ids[index].item())
            reward = float(rewards[index].detach().cpu().item())
            cost = float(costs[index].detach().cpu().item())
            action = actions[index].detach().clone()
            descriptor = descriptors[index].detach().to(dtype=torch.float32).clone()
            fingerprint = fingerprint_action(action)
            grouped.setdefault(cell, []).append(
                {
                    "action": action,
                    "reward": reward,
                    "cost": cost,
                    "descriptor": descriptor,
                    "fingerprint": fingerprint,
                    "parent_cell_id": parent_values[index],
                }
            )

        insertions = replacements = rejections = 0
        for cell in sorted(grouped):
            candidates = sorted(
                grouped[cell],
                key=lambda item: (-float(item["reward"]), str(item["fingerprint"])),
            )
            winner = candidates[0]
            incumbent = self.entries.get(cell)
            should_write = incumbent is None or self._candidate_better(
                float(winner["reward"]),
                str(winner["fingerprint"]),
                incumbent.reward,
                incumbent.fingerprint,
            )
            if should_write:
                if incumbent is None:
                    insertions += 1
                else:
                    replacements += 1
                    if float(winner["reward"]) < incumbent.reward:
                        self.elite_monotonicity_violation_count += 1
                self.entries[cell] = QDArchiveEntry(
                    action=winner["action"],
                    reward=float(winner["reward"]),
                    cost=float(winner["cost"]),
                    descriptor_xy_m=winner["descriptor"],
                    fingerprint=str(winner["fingerprint"]),
                    source_iter=int(source_iter),
                    parent_cell_id=winner["parent_cell_id"],
                    insert_sequence=self._next_insert_sequence,
                )
                self._next_insert_sequence += 1
                rejections += len(candidates) - 1
            else:
                rejections += len(candidates)

        total = insertions + replacements + rejections
        if total != candidate_count:
            self.accounting_violation_count += 1
            raise RuntimeError(
                f"QD archive accounting mismatch: {total} != {candidate_count}"
            )
        return QDUpdateSummary(
            insertions=insertions,
            replacements=replacements,
            rejections=rejections,
            total=total,
        )

    def select_global_best(self) -> tuple[int, QDArchiveEntry]:
        if not self.entries:
            raise RuntimeError("QD archive is empty")
        cell, entry = min(
            self.entries.items(),
            key=lambda item: (-item[1].reward, item[1].fingerprint, item[0]),
        )
        return int(cell), entry

    def rebin(self, target_cell_ids: Tensor) -> QDRebinSummary:
        """Move current elites and their cell visits into a new partition."""
        if not torch.is_tensor(target_cell_ids):
            raise ValueError("QD rebin target cell ids must be a torch.Tensor")
        targets = target_cell_ids.detach().to(device="cpu", dtype=torch.long).reshape(-1)
        old_cells = sorted(self.entries)
        if targets.numel() != len(old_cells):
            raise ValueError("QD rebin requires one target cell for every archive elite")
        if bool(((targets < 0) | (targets >= self.cell_count)).any().item()):
            raise ValueError("QD rebin target cell id is outside the configured grid")
        positive_visit_cells = set(
            torch.nonzero(self.cumulative_visits > 0, as_tuple=False)
            .reshape(-1)
            .tolist()
        )
        if not positive_visit_cells.issubset(set(old_cells)):
            raise RuntimeError("QD rebin cannot map visits for an empty archive cell")

        visit_sum_before = int(self.cumulative_visits.sum().item())
        remapped_visits = torch.zeros_like(self.cumulative_visits)
        grouped: dict[int, list[QDArchiveEntry]] = {}
        for old_cell, target_cell_tensor in zip(old_cells, targets, strict=True):
            target_cell = int(target_cell_tensor.item())
            grouped.setdefault(target_cell, []).append(self.entries[old_cell])
            remapped_visits[target_cell] += self.cumulative_visits[old_cell]

        remapped_entries: dict[int, QDArchiveEntry] = {}
        for target_cell in sorted(grouped):
            remapped_entries[target_cell] = min(
                grouped[target_cell],
                key=lambda entry: (-entry.reward, entry.fingerprint),
            )
        visit_sum_after = int(remapped_visits.sum().item())
        if visit_sum_after != visit_sum_before:
            raise RuntimeError("QD rebin failed to preserve cumulative visits")
        occupied_before = len(self.entries)
        occupied_after = len(remapped_entries)
        self.entries = remapped_entries
        self.cumulative_visits = remapped_visits
        return QDRebinSummary(
            occupied_before=occupied_before,
            occupied_after=occupied_after,
            collisions=occupied_before - occupied_after,
            visit_sum_before=visit_sum_before,
            visit_sum_after=visit_sum_after,
        )

    def elite_tensors(self) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
        if not self.entries:
            raise RuntimeError("QD archive is empty")
        cells = sorted(self.entries)
        entries = [self.entries[cell] for cell in cells]
        action_device = entries[0].action.device
        return (
            torch.stack([entry.action for entry in entries]),
            torch.tensor([entry.reward for entry in entries], device=action_device),
            torch.tensor([entry.cost for entry in entries], device=action_device),
            torch.stack([entry.descriptor_xy_m for entry in entries]).to(action_device),
            torch.tensor(cells, device=action_device, dtype=torch.long),
        )

    def snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "cell_id": cell,
                "reward": entry.reward,
                "cost": entry.cost,
                "descriptor_xy_m": entry.descriptor_xy_m.detach().cpu().tolist(),
                "fingerprint": entry.fingerprint,
                "source_iter": entry.source_iter,
                "parent_cell_id": entry.parent_cell_id,
                "insert_sequence": entry.insert_sequence,
            }
            for cell, entry in sorted(self.entries.items())
        ]

    def endpoint_xy_spread_m(self) -> float:
        if len(self.entries) < 2:
            return 0.0
        descriptors = torch.stack(
            [entry.descriptor_xy_m.detach().float().cpu() for entry in self.entries.values()]
        )
        return float(torch.pdist(descriptors, p=2).mean().item())

    def occupancy_entropy(self) -> float:
        visits = self.cumulative_visits[self.cumulative_visits > 0].float()
        if visits.numel() <= 1:
            return 0.0
        probabilities = visits / visits.sum()
        entropy = -(probabilities * probabilities.log()).sum()
        return float((entropy / math.log(self.cell_count)).item())


def _local_generator(
    *, run_seed: int, episode: int, global_step: int, iter_idx: int
) -> torch.Generator:
    seed_material = f"{int(run_seed)}:{int(episode)}:{int(global_step)}:{int(iter_idx)}"
    digest = hashlib.sha256(seed_material.encode("ascii")).digest()
    seed = int.from_bytes(digest[:8], byteorder="big", signed=False) & ((1 << 63) - 1)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    return generator


def allocate_parent_slots(
    archive: QDArchive,
    *,
    population_size: int,
    sampling: str,
    sparse_exponent: float,
    run_seed: int,
    episode: int,
    global_step: int,
    iter_idx: int,
) -> QDParentAllocation:
    if isinstance(population_size, bool) or not isinstance(population_size, int) or population_size <= 0:
        raise ValueError("QD population size must be a positive integer")
    if sampling not in {"uniform_cells", "sparse_priority"}:
        raise ValueError("QD parent sampling must be uniform_cells or sparse_priority")
    sparse_exponent = float(sparse_exponent)
    if not math.isfinite(sparse_exponent) or sparse_exponent <= 0.0:
        raise ValueError("QD sparse exponent must be finite and positive")
    occupied = sorted(archive.entries)
    if not occupied:
        raise RuntimeError("QD archive is empty")
    generator = _local_generator(
        run_seed=run_seed,
        episode=episode,
        global_step=global_step,
        iter_idx=iter_idx,
    )
    permutation = torch.randperm(len(occupied), generator=generator).tolist()
    tie_rank = {occupied[offset]: rank for rank, offset in enumerate(permutation)}

    if sampling == "uniform_cells":
        base, remainder = divmod(population_size, len(occupied))
        slot_counts = {cell: base for cell in occupied}
        for offset in permutation[:remainder]:
            slot_counts[occupied[offset]] += 1
        raw_weights = {cell: 1.0 for cell in occupied}
    else:
        raw_weights = {
            cell: (float(archive.cumulative_visits[cell].item()) + 1.0)
            ** (-sparse_exponent)
            for cell in occupied
        }
        weight_sum = sum(raw_weights.values())
        exact = {
            cell: population_size * raw_weights[cell] / weight_sum for cell in occupied
        }
        slot_counts = {cell: int(math.floor(exact[cell])) for cell in occupied}
        remainder = population_size - sum(slot_counts.values())
        ranked = sorted(
            occupied,
            key=lambda cell: (-(exact[cell] - slot_counts[cell]), tie_rank[cell]),
        )
        for cell in ranked[:remainder]:
            slot_counts[cell] += 1

    parent_cells = [
        cell for cell in occupied for _ in range(int(slot_counts[cell]))
    ]
    if len(parent_cells) != population_size:
        raise RuntimeError(
            f"QD parent allocation mismatch: {len(parent_cells)} != {population_size}"
        )
    entries = [archive.entries[cell] for cell in parent_cells]
    action_device = entries[0].action.device
    parent_cell_ids = torch.tensor(
        parent_cells, device=action_device, dtype=torch.long
    )
    return QDParentAllocation(
        parent_cell_ids=parent_cell_ids,
        parent_actions=torch.stack([entry.action for entry in entries]),
        parent_rewards=torch.tensor(
            [entry.reward for entry in entries], device=action_device
        ),
        parent_costs=torch.tensor(
            [entry.cost for entry in entries], device=action_device
        ),
        parent_fingerprints=tuple(entry.fingerprint for entry in entries),
        slot_counts={cell: int(slot_counts[cell]) for cell in occupied},
        weights={cell: float(raw_weights[cell]) for cell in occupied},
    )
