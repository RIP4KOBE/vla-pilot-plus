"""Lossless projection of all sampled candidates; no clustering or subsampling."""
from pathlib import Path

from .config import ModeGateConfig
from .protocols import TrajectoryProjector
from .types import ActionChunkBatch, CandidateEvidence, GateContext, RoundEvidence, SamplingDiagnostics


class TrajectoryCandidateGate:
    def __init__(self, config: ModeGateConfig, projector: TrajectoryProjector) -> None:
        self.config, self.projector = config, projector

    def analyze(self, context: GateContext, batch: ActionChunkBatch, round_dir: Path) -> RoundEvidence:
        if batch.context_id != context.context_id:
            raise ValueError("action batch context does not match the current decision")
        if batch.sample_count != self.config.sample_count:
            raise ValueError("sampler must return the complete requested candidate batch")
        trajectories = self.projector.project(batch, context)
        # FK ancestry describes sampling only. Duplicate descendants remain
        # separate candidates, without filtering, clustering or extra weights.
        raw = batch.metadata.get("sampling_diagnostics")
        diagnostics = raw if isinstance(raw, SamplingDiagnostics) else (
            SamplingDiagnostics(**raw) if raw is not None else None)
        if diagnostics is not None and len(diagnostics.ancestor_ids) != batch.sample_count:
            raise ValueError("sampling diagnostics must cover every candidate")
        return RoundEvidence(context.context_id, batch.round_id, batch.checkpoint_id,
            batch, trajectories, tuple(CandidateEvidence(sample_id, index, sample_id)
                for index, sample_id in enumerate(batch.sample_ids)), diagnostics)
