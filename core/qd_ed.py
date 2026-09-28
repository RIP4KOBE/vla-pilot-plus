from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Iterable

import torch
from torch import Tensor

EXECUTION_INTENT_DESCRIPTOR = "target_distance_gripper_duty_v1"
HEIGHT_AWARE_DESCRIPTOR = "target_horizontal_radius_signed_height_v1"
DIRECTION_HEIGHT_DESCRIPTOR = "target_xy_quadrant_signed_height_v1"


def select_parent_survivor_slots(rewards: Tensor, cell_ids: Tensor, count: int) -> tuple[int, ...]:
    """Choose exact, distinct-cell parents using existing same-chunk quality."""
    if type(count) is not int or count not in (0, 4):
        raise ValueError("QD parent survivor count must be 0 or 4")
    if rewards.ndim != 1 or cell_ids.ndim != 1 or rewards.numel() != cell_ids.numel():
        raise ValueError("QD parent survivor inputs must be aligned vectors")
    if not bool(torch.isfinite(rewards).all().item()):
        raise FloatingPointError("QD parent survivor rewards are nonfinite")
    if count == 0:
        return ()
    if rewards.numel() != 16:
        raise ValueError("QD parent survivor allocation must contain 16 slots")
    qualities = rewards.detach().cpu().tolist()
    cells = cell_ids.detach().cpu().tolist()
    if any(type(cell) is not int or cell < 0 for cell in cells):
        raise ValueError("QD parent survivor cells are invalid")
    ranked = sorted(range(16), key=lambda slot: (-qualities[slot], cells[slot], slot))
    chosen = []
    used_cells = set()
    for slot in ranked:
        if cells[slot] not in used_cells:
            chosen.append(slot)
            used_cells.add(cells[slot])
            if len(chosen) == count:
                break
    return tuple(chosen)
DIRECTION_HEIGHT_AXES = (
    {"name": "target_relative_xy_quadrant", "unit": "category"},
    {"name": "target_relative_signed_height", "unit": "m"},
)
HEIGHT_AWARE_AXES = (
    {"name": "target_horizontal_radius", "unit": "m"},
    {"name": "target_relative_signed_height", "unit": "m"},
)
EXECUTION_INTENT_AXES = (
    {"name": "target_distance", "unit": "m"},
    {"name": "positive_gripper_command_duty", "unit": "fraction"},
)


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


def height_aware_descriptor(trajectories: Tensor, keypoints: Tensor | None) -> Tensor:
    """Describe native eighth-step horizontal radius and signed target height."""
    trajectories = _finite_tensor(trajectories, name="QD trajectories", ndim=3)
    if trajectories.shape[0] <= 0 or tuple(trajectories.shape[1:]) != (9, 3):
        raise ValueError("Height-aware QD requires start plus eight projected positions")
    if keypoints is None:
        raise ValueError("Height-aware QD requires keypoints")
    keypoints = _finite_tensor(keypoints, name="QD keypoints")
    target = keypoints.reshape(-1)
    if target.numel() < 3:
        raise ValueError("Height-aware QD requires a 3D target")
    endpoint = trajectories[:, 8, :3].detach().float()
    target = target[:3].detach().to(endpoint)
    radial = torch.linalg.vector_norm(endpoint[:, :2] - target[:2], dim=1)
    height = endpoint[:, 2] - target[2]
    return _finite_tensor(torch.stack((radial, height), dim=1),
                          name="QD height-aware descriptor").detach()


def direction_height_descriptor(trajectories: Tensor, keypoints: Tensor | None) -> Tensor:
    """Use the native eighth projected endpoint's XY sign and signed height."""
    trajectories = _finite_tensor(trajectories, name="QD trajectories", ndim=3)
    if trajectories.shape[0] <= 0 or tuple(trajectories.shape[1:]) != (9, 3):
        raise ValueError("Direction-height QD requires start plus eight projected positions")
    if keypoints is None:
        raise ValueError("Direction-height QD requires keypoints")
    target = _finite_tensor(keypoints, name="QD keypoints").reshape(-1)
    if target.numel() < 3:
        raise ValueError("Direction-height QD requires a 3D target")
    endpoint = trajectories[:, 8, :3].detach().float()
    delta = endpoint - target[:3].detach().to(endpoint)
    quadrant = 2 * (delta[:, 0] >= 0).float() + (delta[:, 1] >= 0).float()
    result = torch.stack((quadrant, delta[:, 2]), dim=1)
    return _finite_tensor(result, name="QD direction-height descriptor").detach()


def execution_intent_descriptor(
    trajectories: Tensor, keypoints: Tensor | None, decoded_actions: Tensor
) -> Tensor:
    """Describe the executed t8 endpoint and exact eight-command gripper duty.

    Projected geometry is a current-observation kinematic proxy, not a simulator
    counterfactual. Decoded gripper commands must already be exactly -1/+1.
    """
    trajectories = _finite_tensor(trajectories, name="QD trajectories", ndim=3)
    decoded_actions = _finite_tensor(decoded_actions, name="QD decoded actions", ndim=3)
    if trajectories.shape[0] <= 0 or tuple(trajectories.shape[1:]) != (9, 3):
        raise ValueError("Execution-intent QD requires start plus eight projected positions")
    if tuple(decoded_actions.shape) != (trajectories.shape[0], 8, 7):
        raise ValueError("Execution-intent QD requires exactly eight decoded 7D actions")
    if keypoints is None:
        raise ValueError("QD descriptor requires keypoints")
    target = _finite_tensor(keypoints, name="QD keypoints").reshape(-1)
    if target.numel() < 3:
        raise ValueError("QD keypoints must contain at least one 3D target")
    grip = decoded_actions[:, :, 6]
    if not bool(((grip == -1) | (grip == 1)).all().item()):
        raise ValueError("QD gripper duty requires deployed binary decoded commands")
    endpoint = trajectories[:, 8, :3].detach().float()
    radial = torch.linalg.vector_norm(endpoint - target[:3].detach().to(endpoint), dim=1)
    duty = (grip > 0).float().mean(dim=1).to(endpoint)
    result = torch.stack((radial, duty), dim=1)
    return _finite_tensor(result, name="QD execution-intent descriptor").detach()


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


def freeze_execution_intent_bounds(
    descriptors: Tensor,
    *,
    quantiles: tuple[float, float] | list[float],
    expand_fraction: float,
    min_axis_span_m: float,
) -> QDBounds:
    """Use unchanged historical radial quantiles; duty has fixed [0,1] bounds."""
    descriptors = _finite_tensor(descriptors, name="QD execution-intent descriptors", ndim=2).detach().float()
    if descriptors.shape[0] <= 0 or descriptors.shape[1] != 2:
        raise ValueError("QD execution-intent descriptors must have shape (population, 2)")
    if bool((descriptors[:, 0] < 0).any()) or bool(((descriptors[:, 1] < 0) | (descriptors[:, 1] > 1)).any()):
        raise ValueError("QD radial distance must be nonnegative and duty in [0,1]")
    # Duplicate the meter-valued radial axis to reuse the frozen calculation
    # exactly; the historical minimum span never applies to the duty axis.
    radial = freeze_bounds(descriptors[:, :1].expand(-1, 2), quantiles=quantiles,
                           expand_fraction=expand_fraction, min_axis_span_m=min_axis_span_m)
    lo, hi = radial.lo.clone(), radial.hi.clone()
    lo[1], hi[1] = 0.0, 1.0
    payload = {"descriptor": EXECUTION_INTENT_DESCRIPTOR, "axes": EXECUTION_INTENT_AXES,
               "radial_checksum": radial.checksum,
               "descriptors": sorted(descriptors.cpu().tolist()),
               "lo": lo.cpu().tolist(), "hi": hi.cpu().tolist()}
    checksum = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return QDBounds(lo=lo, hi=hi, checksum=checksum)


def freeze_direction_height_bounds(
    descriptors: Tensor,
    *,
    quantiles: tuple[float, float] | list[float],
    expand_fraction: float,
    min_axis_span_m: float,
) -> QDBounds:
    """Fix categorical columns and freeze metre-valued height from the initial pool."""
    descriptors = _finite_tensor(descriptors, name="QD direction-height descriptors", ndim=2).detach().float()
    if descriptors.shape[0] <= 0 or descriptors.shape[1] != 2:
        raise ValueError("QD direction-height descriptors must have shape (population, 2)")
    q = descriptors[:, 0]
    if not bool(((q >= 0) & (q <= 3) & (q == q.round())).all().item()):
        raise ValueError("QD direction-height quadrant must be an integer in [0,3]")
    height = descriptors[:, 1:2].expand(-1, 2)
    base = freeze_bounds(height, quantiles=quantiles,
                         expand_fraction=expand_fraction, min_axis_span_m=min_axis_span_m)
    lo = torch.stack((q.new_tensor(-.5), base.lo[0]))
    hi = torch.stack((q.new_tensor(3.5), base.hi[0]))
    payload = {"descriptor": DIRECTION_HEIGHT_DESCRIPTOR, "axes": DIRECTION_HEIGHT_AXES,
               "height_checksum": base.checksum, "descriptors": sorted(descriptors.cpu().tolist()),
               "lo": lo.cpu().tolist(), "hi": hi.cpu().tolist()}
    checksum = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return QDBounds(lo=lo, hi=hi, checksum=checksum)


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
    raw_reward: float | None = None


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
    secondary_discard_count: int = 0


@dataclass(frozen=True)
class QDParentAllocation:
    parent_cell_ids: Tensor
    parent_actions: Tensor
    parent_rewards: Tensor
    parent_costs: Tensor
    parent_fingerprints: tuple[str, ...]
    slot_counts: dict[int, int]
    weights: dict[int, float]
    sparse_slot_counts: dict[int, int]
    global_quality_anchor_count: int
    global_quality_anchor_cell_id: int | None
    global_quality_anchor_fingerprint: str | None
    parent_lanes: tuple[str, ...] = ()
    secondary_parent_count: int = 0
    secondary_slot_counts: dict[int, int] = field(default_factory=dict)
    parent_raw_rewards: Tensor | None = None


class QDArchive:
    def __init__(
        self,
        *,
        grid_shape: tuple[int, int] | list[int],
        secondary_lane_mode: str = "none",
        descriptor_mode: str = "target_relative_endpoint_xy",
    ) -> None:
        if secondary_lane_mode not in {"none", "protected_reward_v1"}:
            raise ValueError(
                "QD secondary lane mode must be none or protected_reward_v1"
            )
        self.grid_shape = _grid_shape(grid_shape)
        self.cell_count = self.grid_shape[0] * self.grid_shape[1]
        self.secondary_lane_mode = secondary_lane_mode
        if descriptor_mode not in {"target_relative_endpoint_xy", EXECUTION_INTENT_DESCRIPTOR,
                                   HEIGHT_AWARE_DESCRIPTOR, DIRECTION_HEIGHT_DESCRIPTOR}:
            raise ValueError("Unsupported QD archive descriptor mode")
        self.descriptor_mode = descriptor_mode
        self.entries: dict[int, QDArchiveEntry] = {}
        self.secondary_entries: dict[int, QDArchiveEntry] = {}
        self.cumulative_visits = torch.zeros(self.cell_count, dtype=torch.long)
        self.accounting_violation_count = 0
        self.elite_monotonicity_violation_count = 0
        self.secondary_invariant_violation_count = 0
        self.secondary_rebin_discard_count = 0
        self._next_insert_sequence = 0
        self._raw_channel_active: bool | None = None

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
        raw_rewards: Tensor | None = None,
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

        if raw_rewards is not None:
            raw_rewards = _finite_tensor(raw_rewards, name="QD original provider rewards").reshape(-1)
            if raw_rewards.numel() != candidate_count:
                raise ValueError("QD original provider rewards must match candidate count")
        if self._raw_channel_active is not None and self._raw_channel_active != (raw_rewards is not None):
            raise RuntimeError("QD original reward channel changed within archive")
        self._raw_channel_active = raw_rewards is not None
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
                    "raw_reward": float(raw_rewards[index].detach().cpu().item()) if raw_rewards is not None else None,
                    "cost": cost,
                    "descriptor": descriptor,
                    "fingerprint": fingerprint,
                    "parent_cell_id": parent_values[index],
                }
            )

        secondary_pool: dict[int, list[QDArchiveEntry]] = {}
        if self.secondary_lane_mode == "protected_reward_v1":
            for cell, entry in self.entries.items():
                secondary_pool.setdefault(cell, []).append(entry)
            for cell, entry in self.secondary_entries.items():
                secondary_pool.setdefault(cell, []).append(entry)
            for cell, candidates in grouped.items():
                for candidate in candidates:
                    secondary_pool.setdefault(cell, []).append(
                        QDArchiveEntry(
                            action=candidate["action"],
                            reward=float(candidate["reward"]),
                            cost=float(candidate["cost"]),
                            descriptor_xy_m=candidate["descriptor"],
                            fingerprint=str(candidate["fingerprint"]),
                            source_iter=int(source_iter),
                            parent_cell_id=candidate["parent_cell_id"],
                            insert_sequence=-1,
                            raw_reward=candidate["raw_reward"],
                        )
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
                    raw_reward=winner["raw_reward"],
                )
                self._next_insert_sequence += 1
                rejections += len(candidates) - 1
            else:
                rejections += len(candidates)

        if self.secondary_lane_mode == "protected_reward_v1":
            selected_secondary: dict[int, QDArchiveEntry] = {}
            for cell, quality in sorted(self.entries.items()):
                alternates = {
                    entry.fingerprint: entry
                    for entry in secondary_pool.get(cell, [])
                    if entry.fingerprint != quality.fingerprint
                }
                if alternates:
                    selected_secondary[cell] = min(
                        alternates.values(),
                        key=lambda entry: (-entry.reward, entry.fingerprint),
                    )
            self.secondary_entries = selected_secondary
            self._validate_secondary_invariants()

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

    def rebin(
        self,
        target_cell_ids: Tensor,
        *,
        secondary_target_cell_ids: Tensor | None = None,
    ) -> QDRebinSummary:
        """Move current elites and their cell visits into a new partition."""
        if not torch.is_tensor(target_cell_ids):
            raise ValueError("QD rebin target cell ids must be a torch.Tensor")
        targets = target_cell_ids.detach().to(device="cpu", dtype=torch.long).reshape(-1)
        old_cells = sorted(self.entries)
        if targets.numel() != len(old_cells):
            raise ValueError("QD rebin requires one target cell for every archive elite")
        if bool(((targets < 0) | (targets >= self.cell_count)).any().item()):
            raise ValueError("QD rebin target cell id is outside the configured grid")
        old_secondary_cells = sorted(self.secondary_entries)
        if self.secondary_lane_mode == "protected_reward_v1":
            if secondary_target_cell_ids is None or not torch.is_tensor(
                secondary_target_cell_ids
            ):
                raise ValueError(
                    "QD protected secondary rebin requires secondary target cells"
                )
            secondary_targets = secondary_target_cell_ids.detach().to(
                device="cpu", dtype=torch.long
            ).reshape(-1)
            if secondary_targets.numel() != len(old_secondary_cells):
                raise ValueError(
                    "QD protected secondary rebin requires one target per secondary"
                )
            if bool(
                ((secondary_targets < 0) | (secondary_targets >= self.cell_count))
                .any()
                .item()
            ):
                raise ValueError("QD secondary rebin target is outside the grid")
        else:
            if secondary_target_cell_ids is not None:
                raise ValueError(
                    "QD secondary rebin targets require protected_reward_v1"
                )
            secondary_targets = torch.empty(0, dtype=torch.long)
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
        secondary_discard_count = 0
        if self.secondary_lane_mode == "protected_reward_v1":
            alternate_pool: dict[int, list[QDArchiveEntry]] = {}
            for target, entries in grouped.items():
                alternate_pool.setdefault(int(target), []).extend(entries)
            for old_cell, target in zip(
                old_secondary_cells, secondary_targets.tolist(), strict=True
            ):
                alternate_pool.setdefault(int(target), []).append(
                    self.secondary_entries[old_cell]
                )
            selected_secondary: dict[int, QDArchiveEntry] = {}
            for cell, quality in sorted(self.entries.items()):
                alternates = {
                    entry.fingerprint: entry
                    for entry in alternate_pool.get(cell, [])
                    if entry.fingerprint != quality.fingerprint
                }
                if alternates:
                    selected_secondary[cell] = min(
                        alternates.values(),
                        key=lambda entry: (-entry.reward, entry.fingerprint),
                    )
            retained = {entry.fingerprint for entry in selected_secondary.values()}
            secondary_discard_count = sum(
                entry.fingerprint not in retained
                for entries in alternate_pool.values()
                for entry in entries
                if entry.fingerprint
                not in {quality.fingerprint for quality in self.entries.values()}
            )
            self.secondary_entries = selected_secondary
            self.secondary_rebin_discard_count += secondary_discard_count
            self._validate_secondary_invariants()
        return QDRebinSummary(
            occupied_before=occupied_before,
            occupied_after=occupied_after,
            collisions=occupied_before - occupied_after,
            visit_sum_before=visit_sum_before,
            visit_sum_after=visit_sum_after,
            secondary_discard_count=secondary_discard_count,
        )

    def _validate_secondary_invariants(self) -> None:
        if self.secondary_lane_mode == "none":
            if self.secondary_entries:
                self.secondary_invariant_violation_count += 1
                raise RuntimeError("QD disabled secondary lane contains entries")
            return
        if not set(self.secondary_entries).issubset(set(self.entries)) or any(
            entry.fingerprint == self.entries[cell].fingerprint
            for cell, entry in self.secondary_entries.items()
        ):
            self.secondary_invariant_violation_count += 1
            raise RuntimeError("QD protected secondary lane invariant violation")

    def secondary_tensors(self) -> tuple[Tensor, Tensor]:
        cells = sorted(self.secondary_entries)
        if not cells:
            return torch.empty(0, 2), torch.empty(0, dtype=torch.long)
        descriptors = torch.stack(
            [self.secondary_entries[cell].descriptor_xy_m for cell in cells]
        )
        return descriptors, torch.tensor(cells, dtype=torch.long)

    def secondary_snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "cell_id": cell,
                "reward": entry.reward,
                "cost": entry.cost,
                **({"raw_reward": entry.raw_reward} if entry.raw_reward is not None else {}),
                "descriptor_xy_m": entry.descriptor_xy_m.detach().cpu().tolist(),
                "fingerprint": entry.fingerprint,
                "source_iter": entry.source_iter,
                "parent_cell_id": entry.parent_cell_id,
                "insert_sequence": entry.insert_sequence,
                "lane": "secondary",
            }
            for cell, entry in sorted(self.secondary_entries.items())
        ]

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

    def elite_raw_rewards(self) -> Tensor:
        """Same sorted entries and native-value -> FP32 restoration as elite_tensors."""
        entries = [self.entries[cell] for cell in sorted(self.entries)]
        if not entries or any(entry.raw_reward is None for entry in entries):
            raise RuntimeError("QD original reward association is missing")
        return torch.tensor([entry.raw_reward for entry in entries], device=entries[0].action.device)

    def snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "cell_id": cell,
                "reward": entry.reward,
                "cost": entry.cost,
                **({"raw_reward": entry.raw_reward} if entry.raw_reward is not None else {}),
                ("descriptor_values" if self.descriptor_mode == EXECUTION_INTENT_DESCRIPTOR else "descriptor_xy_m"): entry.descriptor_xy_m.detach().cpu().tolist(),
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


def _secondary_rotation_start(
    *, run_seed: int, episode: int, global_step: int, iter_idx: int, cell: int
) -> int:
    material = (
        f"{int(run_seed)}:{int(episode)}:{int(global_step)}:"
        f"{int(iter_idx)}:{int(cell)}:protected_reward_v1"
    )
    return int.from_bytes(
        hashlib.sha256(material.encode("ascii")).digest()[:8],
        byteorder="big",
        signed=False,
    ) % 2


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
    global_quality_anchor_count: int = 0,
) -> QDParentAllocation:
    if isinstance(population_size, bool) or not isinstance(population_size, int) or population_size <= 0:
        raise ValueError("QD population size must be a positive integer")
    if sampling not in {"uniform_cells", "sparse_priority"}:
        raise ValueError("QD parent sampling must be uniform_cells or sparse_priority")
    if (
        isinstance(global_quality_anchor_count, bool)
        or not isinstance(global_quality_anchor_count, int)
        or global_quality_anchor_count not in {0, 1}
    ):
        raise ValueError("QD global quality anchor count must be 0 or 1")
    if global_quality_anchor_count == 1 and sampling != "sparse_priority":
        raise ValueError("QD global quality anchor count 1 requires sparse_priority")
    sparse_population_size = population_size - global_quality_anchor_count
    if sparse_population_size <= 0:
        raise ValueError("QD global quality anchor count must be less than population size")
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
        base, remainder = divmod(sparse_population_size, len(occupied))
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
            cell: sparse_population_size * raw_weights[cell] / weight_sum
            for cell in occupied
        }
        slot_counts = {cell: int(math.floor(exact[cell])) for cell in occupied}
        remainder = sparse_population_size - sum(slot_counts.values())
        ranked = sorted(
            occupied,
            key=lambda cell: (-(exact[cell] - slot_counts[cell]), tie_rank[cell]),
        )
        for cell in ranked[:remainder]:
            slot_counts[cell] += 1

    sparse_slot_counts = {cell: int(slot_counts[cell]) for cell in occupied}
    sparse_parent_cells = [
        cell for cell in occupied for _ in range(int(slot_counts[cell]))
    ]
    anchor_cell: int | None = None
    anchor_fingerprint: str | None = None
    if global_quality_anchor_count == 1:
        anchor_cell, anchor_entry = archive.select_global_best()
        anchor_fingerprint = anchor_entry.fingerprint
        parent_cells = [anchor_cell, *sparse_parent_cells]
        slot_counts[anchor_cell] += 1
    else:
        parent_cells = sparse_parent_cells
    if len(parent_cells) != population_size:
        raise RuntimeError(
            f"QD parent allocation mismatch: {len(parent_cells)} != {population_size}"
        )
    parent_entries: list[QDArchiveEntry] = []
    parent_lanes: list[str] = []
    secondary_slot_counts = {cell: 0 for cell in occupied}
    sparse_offsets = {cell: 0 for cell in occupied}
    for parent_index, cell in enumerate(parent_cells):
        if global_quality_anchor_count == 1 and parent_index == 0:
            parent_entries.append(archive.entries[cell])
            parent_lanes.append("quality_anchor")
            continue
        secondary = archive.secondary_entries.get(cell)
        use_secondary = False
        if (
            archive.secondary_lane_mode == "protected_reward_v1"
            and secondary is not None
        ):
            start = _secondary_rotation_start(
                run_seed=run_seed,
                episode=episode,
                global_step=global_step,
                iter_idx=iter_idx,
                cell=cell,
            )
            use_secondary = (start + sparse_offsets[cell]) % 2 == 1
        sparse_offsets[cell] += 1
        if use_secondary:
            parent_entries.append(secondary)
            parent_lanes.append("secondary")
            secondary_slot_counts[cell] += 1
        else:
            parent_entries.append(archive.entries[cell])
            parent_lanes.append("quality")
    action_device = parent_entries[0].action.device
    parent_cell_ids = torch.tensor(
        parent_cells, device=action_device, dtype=torch.long
    )
    return QDParentAllocation(
        parent_cell_ids=parent_cell_ids,
        parent_actions=torch.stack([entry.action for entry in parent_entries]),
        parent_rewards=torch.tensor(
            [entry.reward for entry in parent_entries], device=action_device
        ),
        parent_costs=torch.tensor(
            [entry.cost for entry in parent_entries], device=action_device
        ),
        parent_raw_rewards=(torch.tensor([entry.raw_reward for entry in parent_entries], device=action_device)
                            if archive._raw_channel_active else None),
        parent_fingerprints=tuple(entry.fingerprint for entry in parent_entries),
        slot_counts={cell: int(slot_counts[cell]) for cell in occupied},
        weights={cell: float(raw_weights[cell]) for cell in occupied},
        sparse_slot_counts=sparse_slot_counts,
        global_quality_anchor_count=global_quality_anchor_count,
        global_quality_anchor_cell_id=anchor_cell,
        global_quality_anchor_fingerprint=anchor_fingerprint,
        parent_lanes=tuple(parent_lanes),
        secondary_parent_count=sum(secondary_slot_counts.values()),
        secondary_slot_counts=secondary_slot_counts,
    )
