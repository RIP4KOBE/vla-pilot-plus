"""Deterministic PCA + diagonal-GMM fitting for trajectory descriptors."""

from __future__ import annotations

from dataclasses import dataclass
import warnings

import numpy as np
from sklearn.decomposition import PCA
from sklearn.exceptions import ConvergenceWarning
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class FittedMode:
    component_index: int
    weight: float
    member_indices: np.ndarray
    representative_indices: dict[str, int]
    representative_backfill: bool


@dataclass(frozen=True)
class MixtureFitResult:
    reduced_descriptors: np.ndarray
    labels: np.ndarray
    responsibilities: np.ndarray
    modes: tuple[FittedMode, ...]
    fit_degraded: bool
    metadata: dict


class TrajectoryModeFitter:
    def __init__(
        self,
        *,
        max_components: int = 4,
        pca_dims: int = 8,
        seed: int = 0,
        n_init: int = 5,
        reg_covar: float = 1e-5,
        max_iter: int = 200,
    ) -> None:
        self.max_components = int(max_components)
        self.pca_dims = int(pca_dims)
        self.seed = int(seed)
        self.n_init = int(n_init)
        self.reg_covar = float(reg_covar)
        self.max_iter = int(max_iter)

    def fit(self, descriptors: np.ndarray) -> MixtureFitResult:
        descriptors = np.asarray(descriptors, dtype=np.float64)
        if descriptors.ndim != 2 or descriptors.shape[0] < 3:
            raise ValueError("descriptors must have shape (N, D) with N >= 3")
        if not np.isfinite(descriptors).all():
            raise ValueError("descriptors contain non-finite values")

        scaler = StandardScaler()
        standardized = scaler.fit_transform(descriptors)
        dimensions = min(self.pca_dims, standardized.shape[0], standardized.shape[1])
        pca = PCA(n_components=dimensions, svd_solver="full")
        reduced = pca.fit_transform(standardized)

        candidates: list[tuple[float, GaussianMixture]] = []
        failures: dict[int, str] = {}
        for components in range(1, min(self.max_components, len(reduced)) + 1):
            try:
                model = GaussianMixture(
                    n_components=components,
                    covariance_type="diag",
                    n_init=self.n_init,
                    reg_covar=self.reg_covar,
                    max_iter=self.max_iter,
                    random_state=self.seed,
                )
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always", ConvergenceWarning)
                    model.fit(reduced)
                if not model.converged_ or any(
                    issubclass(item.category, ConvergenceWarning) for item in caught
                ):
                    raise RuntimeError("GMM did not converge")
                bic = float(model.bic(reduced))
                probabilities = model.predict_proba(reduced)
                if not (
                    np.isfinite(bic)
                    and np.isfinite(probabilities).all()
                    and np.all(model.weights_ > 0)
                ):
                    raise RuntimeError("GMM produced a degenerate solution")
                candidates.append((bic, model))
            except Exception as exc:  # numerical failures must degrade, not expand
                failures[components] = f"{type(exc).__name__}: {exc}"

        base_metadata = {
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_scale": scaler.scale_.tolist(),
            "pca_components": pca.components_.tolist(),
            "pca_mean": pca.mean_.tolist(),
            "pca_explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
            "candidate_failures": failures,
        }
        if not candidates:
            labels = np.zeros(len(reduced), dtype=np.int64)
            responsibilities = np.ones((len(reduced), 1), dtype=np.float64)
            representative_indices, backfill = _select_representatives(
                reduced, labels, responsibilities, component=0
            )
            return MixtureFitResult(
                reduced_descriptors=reduced,
                labels=labels,
                responsibilities=responsibilities,
                modes=(
                    FittedMode(
                        component_index=0,
                        weight=1.0,
                        member_indices=np.arange(len(reduced)),
                        representative_indices=representative_indices,
                        representative_backfill=backfill,
                    ),
                ),
                fit_degraded=True,
                metadata={**base_metadata, "selected_components": 1, "bic": None},
            )

        bic, model = min(candidates, key=lambda item: item[0])
        responsibilities = model.predict_proba(reduced)
        labels = responsibilities.argmax(axis=1).astype(np.int64)
        modes = []
        for component in range(model.n_components):
            representatives, backfill = _select_representatives(
                reduced, labels, responsibilities, component
            )
            modes.append(
                FittedMode(
                    component_index=component,
                    weight=float(model.weights_[component]),
                    member_indices=np.flatnonzero(labels == component),
                    representative_indices=representatives,
                    representative_backfill=backfill,
                )
            )
        metadata = {
            **base_metadata,
            "selected_components": int(model.n_components),
            "bic": bic,
            "candidate_bic": {str(item.n_components): score for score, item in candidates},
            "gmm_weights": model.weights_.tolist(),
            "gmm_means": model.means_.tolist(),
            "gmm_covariances": model.covariances_.tolist(),
        }
        return MixtureFitResult(
            reduced_descriptors=reduced,
            labels=labels,
            responsibilities=responsibilities,
            modes=tuple(modes),
            fit_degraded=False,
            metadata=metadata,
        )


def _select_representatives(
    reduced: np.ndarray,
    labels: np.ndarray,
    responsibilities: np.ndarray,
    component: int,
) -> tuple[dict[str, int], bool]:
    members = np.flatnonzero(labels == component)
    if len(members) == 0:
        members = np.asarray([int(np.argmax(responsibilities[:, component]))])

    member_points = reduced[members]
    pairwise = np.linalg.norm(
        member_points[:, None, :] - member_points[None, :, :], axis=-1
    )
    medoid = int(members[int(np.argmin(pairwise.sum(axis=1)))])
    selected = [medoid]

    ranked_members = members[
        np.argsort(responsibilities[members, component])[::-1]
    ]
    high_count = max(1, int(np.ceil(len(ranked_members) / 2)))
    high_members = ranked_members[:high_count]
    high_candidates = [int(index) for index in high_members if int(index) not in selected]
    if high_candidates:
        diverse = max(
            high_candidates,
            key=lambda index: float(np.linalg.norm(reduced[index] - reduced[medoid])),
        )
        selected.append(diverse)

    boundary_candidates = [
        int(index)
        for index in members[np.argsort(responsibilities[members, component])]
        if int(index) not in selected
    ]
    if boundary_candidates:
        selected.append(boundary_candidates[0])

    backfill = len(selected) < 3
    fallback_order = np.argsort(responsibilities[:, component])[::-1]
    if len(selected) < 3:
        for index in fallback_order:
            if int(index) not in selected:
                selected.append(int(index))
            if len(selected) >= 3:
                break
    if len(selected) != 3:
        raise RuntimeError("at least three real samples are required for representatives")
    return {
        "medoid": selected[0],
        "diverse": selected[1],
        "boundary": selected[2],
    }, backfill
