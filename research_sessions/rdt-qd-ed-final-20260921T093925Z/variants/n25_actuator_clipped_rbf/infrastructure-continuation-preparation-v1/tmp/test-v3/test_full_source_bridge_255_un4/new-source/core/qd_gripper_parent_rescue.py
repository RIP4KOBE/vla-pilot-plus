"""N24 search-local, already-scored canonical proposal rescue (default off).

This module never scores, projects, decodes, inserts into the spatial archive,
or samples randomness. Canonical birth order is independent of instrumentation.
"""
from dataclasses import dataclass
import copy
import hashlib

import torch

from core.qd_ed import fingerprint_action

MODE = "canonical_full_close_v1"


def native_identity(value):
    value = value.detach().cpu().contiguous()
    return {"dtype": str(value.dtype), "shape": list(value.shape),
            "sha256": hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()}


def full_close(actions):
    if (not torch.is_tensor(actions) or actions.ndim != 3
            or actions.shape[1:] != (64, 128) or not actions.is_floating_point()
            or not torch.isfinite(actions).all()):
        raise ValueError("N24 invalid native action batch")
    return (actions[:, :8, 10] >= 0).all(dim=1)


@dataclass
class ActualParents:
    actions: torch.Tensor
    costs: torch.Tensor
    quality: torch.Tensor
    raw: torch.Tensor
    cells: torch.Tensor
    descriptors: torch.Tensor
    slot: int | None
    witness: dict


class CanonicalCloseCache:
    def __init__(self, context, bounds):
        self.context = copy.deepcopy(context)
        self.bounds = tuple(x.detach().clone() for x in bounds)
        self.next_iteration = -1
        self.entry = None

    def _context(self, context, bounds):
        if (context != self.context or len(bounds) != 2
                or any(a.dtype != b.dtype or a.shape != b.shape or not torch.equal(a, b)
                       for a, b in zip(bounds, self.bounds))):
            raise ValueError("N24 changed search context or descriptor bounds")

    def observe(self, *, iteration, actions, costs, quality, raw, descriptors, cells,
                context, bounds, canonical_sequence=None, scoring_batch_id=None, decision_id=None):
        self._context(context, bounds)
        if type(iteration) is not int or iteration != self.next_iteration or iteration > 9:
            raise ValueError("N24 canonical birth order")
        mask = full_close(actions)
        if actions.shape != (16, 64, 128):
            raise ValueError("N24 canonical population shape")
        for name, value in (("cost", costs), ("quality", quality), ("raw", raw)):
            if (not torch.is_tensor(value) or value.shape != (16,) or value.dtype != actions.dtype
                    or value.device != actions.device or not torch.isfinite(value).all()):
                raise ValueError("N24 native " + name + " association")
        if not torch.equal(costs, -quality):
            raise ValueError("N24 paired effective cost/quality mismatch")
        if (descriptors.shape != (16, 2) or descriptors.dtype != torch.float32
                or not torch.isfinite(descriptors).all() or cells.shape != (16,)
                or cells.dtype != torch.int64 or not ((cells >= 0) & (cells < 16)).all()):
            raise ValueError("N24 descriptor/cell association")
        lo, hi = bounds
        if lo.shape != (2,) or hi.shape != (2,) or not torch.isfinite(lo).all() or not torch.isfinite(hi).all() or not (hi > lo).all():
            raise ValueError("N24 invalid descriptor bounds")
        mapped = torch.floor((descriptors - lo) / (hi - lo) * 4).long().clamp(0, 3)
        if not torch.equal(mapped[:, 1] * 4 + mapped[:, 0], cells):
            raise ValueError("N24 descriptor/cell mismatch")
        changed = False
        update_count = 0
        for row in torch.nonzero(mask, as_tuple=False).flatten().tolist():
            cost = costs[row].item()
            if self.entry is None or cost < self.entry["cost"].item():
                # Strict comparison preserves the earliest (iteration,row) tie.
                self.entry = {"iteration": iteration, "row": row,
                    "action": actions[row].detach().clone(), "cost": costs[row].detach().clone(),
                    "quality": quality[row].detach().clone(), "raw": raw[row].detach().clone(),
                    "descriptor": descriptors[row].detach().clone(), "cell": int(cells[row].item()),
                    "fingerprint": fingerprint_action(actions[row]),
                    "canonical_sequence": canonical_sequence, "scoring_batch_id": scoring_batch_id,
                    "occurrence_id": (f"{decision_id}:q{canonical_sequence}:r{row}"
                                      if canonical_sequence is not None else None)}
                changed = True
                update_count += 1
        self.next_iteration += 1
        return {"iter_idx": iteration, "full_close_rows": torch.nonzero(mask).flatten(),
                "updated": changed, "update_count": update_count, "cache": self.reference(), "context": copy.deepcopy(self.context)}

    def reference(self):
        if self.entry is None:
            return None
        return {k: v for k, v in self.entry.items() if k != "action"}

    def supply(self, allocation, descriptors, *, iteration, context, bounds):
        self._context(context, bounds)
        if iteration != self.next_iteration or not 0 <= iteration < 10:
            raise ValueError("N24 future or stale allocation")
        original_mask = full_close(allocation.parent_actions)
        if allocation.parent_actions.shape != (16, 64, 128):
            raise ValueError("N24 parent shape")
        for value in (allocation.parent_costs, allocation.parent_rewards, allocation.parent_raw_rewards):
            if not torch.is_tensor(value) or value.shape != (16,) or value.dtype != torch.float32 or not torch.isfinite(value).all():
                raise ValueError("N24 invalid allocated score association")
        if not torch.equal(allocation.parent_costs, -allocation.parent_rewards):
            raise ValueError("N24 allocated cost/quality mismatch")
        if tuple(fingerprint_action(row) for row in allocation.parent_actions) != allocation.parent_fingerprints:
            raise ValueError("N24 allocated fingerprint mismatch")
        if descriptors.shape != (16, 2) or descriptors.dtype != torch.float32 or not torch.isfinite(descriptors).all():
            raise ValueError("N24 allocated descriptor mismatch")
        slot = None
        values = [allocation.parent_actions, allocation.parent_costs, allocation.parent_rewards,
                  allocation.parent_raw_rewards, allocation.parent_cell_ids, descriptors]
        if self.entry is not None and not original_mask.any():
            slot = int(torch.argmax(allocation.parent_costs).item())
            values = [v.clone() for v in values]
            entry = self.entry
            if (entry["iteration"] >= iteration or not full_close(entry["action"].unsqueeze(0)).item()
                    or fingerprint_action(entry["action"]) != entry["fingerprint"]):
                raise ValueError("N24 corrupted cache identity")
            for value, key in zip(values, ("action", "cost", "quality", "raw", "cell", "descriptor")):
                value[slot] = entry[key]
        witness = {"iter_idx": iteration, "mode": MODE, "context": copy.deepcopy(self.context),
                   "cache": self.reference(), "original_full_close_mask": original_mask,
                   "replacement_slot": slot, "exact_survivor": False,
                   "original_is_archive_allocation": True, "actual_is_archive_allocation": slot is None}
        return ActualParents(*values, slot, witness)
