"""Statistical trajectory-mode analysis, independent of steering semantics."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .cards import ModeCardRenderer
from .config import ModeGateConfig
from .features import TrajectoryDescriptorEncoder
from .mixture import TrajectoryModeFitter
from .protocols import TrajectoryProjector
from .types import ActionChunkBatch, GateContext, ModeEvidence, RoundEvidence


class TrajectoryModeGate:
    def __init__(
        self,
        config: ModeGateConfig,
        projector: TrajectoryProjector,
        renderer: ModeCardRenderer,
    ) -> None:
        self.config = config
        self.projector = projector
        self.renderer = renderer
        self.encoder = TrajectoryDescriptorEncoder(config.phase_points)
        self.fitter = TrajectoryModeFitter(
            max_components=config.max_components,
            pca_dims=config.pca_dims,
            seed=config.seed,
            n_init=config.gmm_n_init,
            reg_covar=config.gmm_reg_covar,
            max_iter=config.gmm_max_iter,
        )

    def analyze(
        self,
        context: GateContext,
        batch: ActionChunkBatch,
        round_dir: Path,
    ) -> RoundEvidence:
        if batch.context_id != context.context_id:
            raise ValueError("action batch context does not match the gate context")
        if batch.sample_count != self.config.sample_count:
            raise ValueError(
                f"expected exactly {self.config.sample_count} samples, "
                f"got {batch.sample_count}"
            )
        trajectories = self.projector.project(batch, context)
        descriptor_batch = self.encoder.encode(trajectories)
        fit = self.fitter.fit(descriptor_batch.descriptors)

        modes = []
        for fitted in fit.modes:
            mode_id = f"r{batch.round_id:03d}-m{fitted.component_index:02d}"
            representative_sample_ids = {
                role: batch.sample_ids[index]
                for role, index in fitted.representative_indices.items()
            }
            card = self.renderer.render(
                observation_image=context.observation_image,
                mode_id=mode_id,
                weight=fitted.weight,
                representative_indices=fitted.representative_indices,
                positions=trajectories.positions,
                relative_positions=descriptor_batch.relative_positions,
                relative_rotvecs=descriptor_batch.relative_rotvecs,
                grippers=descriptor_batch.grippers,
                output_path=round_dir / f"mode_card_{mode_id}.png",
            )
            responsibilities = fit.responsibilities[:, fitted.component_index]
            member_responsibilities = responsibilities[fitted.member_indices]
            statistics = {
                "member_count": int(len(fitted.member_indices)),
                "responsibility_mean": (
                    float(member_responsibilities.mean())
                    if len(member_responsibilities)
                    else 0.0
                ),
                "responsibility_min": (
                    float(member_responsibilities.min())
                    if len(member_responsibilities)
                    else 0.0
                ),
                "responsibility_max": (
                    float(member_responsibilities.max())
                    if len(member_responsibilities)
                    else 0.0
                ),
                "representative_backfill": fitted.representative_backfill,
            }
            modes.append(
                ModeEvidence(
                    mode_id=mode_id,
                    component_index=fitted.component_index,
                    weight=fitted.weight,
                    member_indices=fitted.member_indices.copy(),
                    representative_indices=dict(fitted.representative_indices),
                    representative_sample_ids=representative_sample_ids,
                    card_path=card.path,
                    projection_unavailable=card.projection_unavailable,
                    statistics=statistics,
                )
            )

        return RoundEvidence(
            context_id=context.context_id,
            round_id=batch.round_id,
            checkpoint_id=batch.checkpoint_id,
            action_batch=batch,
            trajectories=trajectories,
            normalized_positions=descriptor_batch.relative_positions,
            normalized_rotvecs=descriptor_batch.relative_rotvecs,
            normalized_grippers=descriptor_batch.grippers,
            descriptors=descriptor_batch.descriptors,
            reduced_descriptors=fit.reduced_descriptors,
            labels=fit.labels,
            responsibilities=fit.responsibilities,
            modes=tuple(modes),
            fit_degraded=fit.fit_degraded,
            fit_metadata=fit.metadata,
        )

