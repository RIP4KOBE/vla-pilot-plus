"""N4's sole new consumer: native last-population first-cost argmin.

No reward/decoder/model/environment calls. Archive search is owned by the caller.
"""
from dataclasses import dataclass

import torch

MODE = "terminal_population_v1"
DEFAULT_MODE = "archive_global_best"


@dataclass(frozen=True)
class TerminalPopulation:
    actions: torch.Tensor
    costs: torch.Tensor
    rewards: torch.Tensor
    cell_ids: torch.Tensor
    parent_cell_ids: torch.Tensor
    canonical_event_sequence: int | None
    scoring_batch_id: int | None
    decision_id: str | None
    raw_rewards: torch.Tensor | None = None

    @classmethod
    def capture(cls, actions, costs, rewards, cell_ids, parent_cell_ids, *,
                canonical_event_sequence=None, scoring_batch_id=None, decision_id=None,
                raw_rewards=None):
        for name, value, shape in (("actions", actions, (16, 64, 128)),
                                   ("costs", costs, (16,)), ("rewards", rewards, (16,))):
            if not torch.is_tensor(value) or tuple(value.shape) != shape or not value.is_floating_point():
                raise RuntimeError(f"N4 {name} shape/dtype invalid")
            if value.dtype != actions.dtype or value.device != actions.device:
                raise RuntimeError(f"N4 {name} native association invalid")
            if not torch.isfinite(value).all():
                raise FloatingPointError(f"N4 {name} nonfinite")
        if not torch.equal(costs, -rewards):
            raise RuntimeError("N4 same-call original reward/cost sign mismatch")
        if raw_rewards is not None:
            if (not torch.is_tensor(raw_rewards) or tuple(raw_rewards.shape) != (16,)
                    or raw_rewards.dtype != actions.dtype or raw_rewards.device != actions.device):
                raise RuntimeError("N20 terminal raw provider reward association invalid")
            if not torch.isfinite(raw_rewards).all():
                raise FloatingPointError("N20 terminal raw provider reward nonfinite")
        for name, value in (("cell_ids", cell_ids), ("parent_cell_ids", parent_cell_ids)):
            if not torch.is_tensor(value) or tuple(value.shape) != (16,) or value.dtype != torch.long:
                raise RuntimeError(f"N4 {name} shape/dtype invalid")
            if not ((value >= 0) & (value < 16)).all():
                raise RuntimeError(f"N4 {name} outside fixed grid")
        return cls(*(x.detach().clone() for x in (actions, costs, rewards, cell_ids, parent_cell_ids)),
                   canonical_event_sequence, scoring_batch_id, decision_id,
                   raw_rewards.detach().clone() if raw_rewards is not None else None)

    def select_index(self):
        # Keep native dtype. In particular, do not rerank rounded BF16 costs.
        return int(torch.argmin(self.costs).item())

    def tie_indices(self):
        return torch.nonzero(self.costs == self.costs.min(), as_tuple=False).flatten().cpu().tolist()

    def occurrence_id(self, index):
        if self.decision_id is None or self.canonical_event_sequence is None:
            return None
        return f"{self.decision_id}:q{self.canonical_event_sequence}:r{index}"
