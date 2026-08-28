"""Deterministic unique-ancestor DPGMM fitting for trajectory modes."""

from __future__ import annotations

from dataclasses import dataclass
import warnings

import numpy as np
from sklearn.decomposition import PCA
from sklearn.exceptions import ConvergenceWarning
from sklearn.mixture import BayesianGaussianMixture
from sklearn.preprocessing import StandardScaler

# Compatibility name used by the original numerical-fallback test.  It is an
# alias, not the old BIC-selected GaussianMixture implementation.
GaussianMixture = BayesianGaussianMixture


@dataclass(frozen=True)
class FittedMode:
    component_index: int
    weight: float
    member_indices: np.ndarray
    representative_indices: dict[str, int]
    representative_backfill: bool
    unique_ancestor_count: int = 0


@dataclass(frozen=True)
class MixtureFitResult:
    reduced_descriptors: np.ndarray
    labels: np.ndarray
    responsibilities: np.ndarray
    modes: tuple[FittedMode, ...]
    fit_degraded: bool
    metadata: dict


class TrajectoryModeFitter:
    """Fit a DP mixture on unique ancestors, then aggregate original FK mass.

    scikit-learn's BayesianGaussianMixture intentionally has no
    ``sample_weight`` argument.  Repeated FK descendants therefore never enter
    ``fit`` twice.  They are assigned after fitting and affect mode mass only.
    """

    def __init__(
        self,
        *,
        max_components: int = 4,
        pca_dims: int = 8,
        seed: int = 0,
        n_init: int = 5,
        reg_covar: float = 1e-5,
        max_iter: int = 500,
        min_mode_mass: float = 0.05,
        min_unique_ancestors: int = 2,
    ) -> None:
        self.max_components = int(max_components)
        self.pca_dims = int(pca_dims)
        self.seed = int(seed)
        self.n_init = int(n_init)
        self.reg_covar = float(reg_covar)
        self.max_iter = int(max_iter)
        self.min_mode_mass = float(min_mode_mass)
        self.min_unique_ancestors = int(min_unique_ancestors)

    def fit(
        self,
        descriptors: np.ndarray,
        *,
        ancestor_ids: np.ndarray | None = None,
        particle_mass: np.ndarray | None = None,
    ) -> MixtureFitResult:
        descriptors = np.asarray(descriptors, dtype=np.float64)
        if descriptors.ndim != 2 or descriptors.shape[0] < 3:
            raise ValueError("descriptors must have shape (N, D) with N >= 3")
        if not np.isfinite(descriptors).all():
            raise ValueError("descriptors contain non-finite values")

        count = len(descriptors)
        ancestors = (
            np.arange(count, dtype=np.int64)
            if ancestor_ids is None
            else np.asarray(ancestor_ids, dtype=np.int64)
        )
        if ancestors.shape != (count,) or np.any(ancestors < 0):
            raise ValueError("ancestor_ids must be a non-negative vector of length N")
        mass = (
            np.full(count, 1.0 / count, dtype=np.float64)
            if particle_mass is None
            else np.asarray(particle_mass, dtype=np.float64)
        )
        if mass.shape != (count,) or not np.isfinite(mass).all() or np.any(mass < 0):
            raise ValueError("particle_mass must be a finite non-negative vector of length N")
        if float(mass.sum()) <= 0:
            raise ValueError("particle_mass must have positive total mass")
        mass = mass / mass.sum()

        unique_indices = _first_unique_indices(ancestors)
        unique_descriptors = descriptors[unique_indices]
        multiplicities = {
            str(int(ancestor)): int(np.sum(ancestors == ancestor))
            for ancestor in ancestors[unique_indices]
        }
        base_metadata = {
            "algorithm": "BayesianGaussianMixture",
            "covariance_type": "diag",
            "weight_concentration_prior_type": "dirichlet_process",
            "input_count": count,
            "unique_ancestor_count": int(len(unique_indices)),
            "multiplicities": multiplicities,
            "min_mode_mass": self.min_mode_mass,
            "min_unique_ancestors": self.min_unique_ancestors,
        }

        try:
            if len(unique_indices) < self.min_unique_ancestors:
                raise RuntimeError("insufficient unique ancestors for DPGMM")
            scaler = StandardScaler()
            unique_standardized = scaler.fit_transform(unique_descriptors)
            if float(np.var(unique_standardized)) <= 1e-15:
                raise RuntimeError("unique trajectory descriptors have zero variance")
            dimensions = min(
                self.pca_dims,
                unique_standardized.shape[0],
                unique_standardized.shape[1],
            )
            if dimensions < 1:
                raise RuntimeError("no PCA dimensions available")
            pca = PCA(n_components=dimensions, svd_solver="full")
            unique_reduced = pca.fit_transform(unique_standardized)
            reduced = pca.transform(scaler.transform(descriptors))

            model = GaussianMixture(
                n_components=min(self.max_components, len(unique_reduced)),
                covariance_type="diag",
                weight_concentration_prior_type="dirichlet_process",
                n_init=self.n_init,
                reg_covar=self.reg_covar,
                max_iter=self.max_iter,
                random_state=self.seed,
                init_params="kmeans",
            )
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ConvergenceWarning)
                model.fit(unique_reduced)
            if not model.converged_ or any(
                issubclass(item.category, ConvergenceWarning) for item in caught
            ):
                raise RuntimeError("DPGMM did not converge")
            raw_responsibilities = model.predict_proba(reduced)
            if not np.isfinite(raw_responsibilities).all():
                raise RuntimeError("DPGMM produced non-finite responsibilities")

            raw_labels = raw_responsibilities.argmax(axis=1)
            active: list[tuple[int, float, int]] = []
            rejected: dict[str, dict[str, float | int]] = {}
            for component in range(model.n_components):
                members = np.flatnonzero(raw_labels == component)
                component_mass = float(mass[members].sum())
                unique_count = int(len(np.unique(ancestors[members])))
                if (
                    component_mass >= self.min_mode_mass
                    and unique_count >= self.min_unique_ancestors
                ):
                    active.append((component, component_mass, unique_count))
                else:
                    rejected[str(component)] = {
                        "mass": component_mass,
                        "unique_ancestors": unique_count,
                    }
            if not active:
                raise RuntimeError("all DPGMM components failed active-mode criteria")

            active.sort(key=lambda item: (-item[1], item[0]))
            columns = [item[0] for item in active]
            responsibilities = raw_responsibilities[:, columns]
            row_sums = responsibilities.sum(axis=1, keepdims=True)
            responsibilities = np.divide(
                responsibilities,
                row_sums,
                out=np.full_like(responsibilities, 1.0 / len(columns)),
                where=row_sums > 1e-12,
            )
            initial_labels = responsibilities.argmax(axis=1).astype(np.int64)
            initial_mass = np.asarray(
                [mass[initial_labels == index].sum() for index in range(len(columns))],
                dtype=np.float64,
            )
            stable_order = sorted(
                range(len(columns)),
                key=lambda index: (-initial_mass[index], columns[index]),
            )
            columns = [columns[index] for index in stable_order]
            responsibilities = responsibilities[:, stable_order]
            labels = responsibilities.argmax(axis=1).astype(np.int64)

            modes: list[FittedMode] = []
            stable_mass = np.asarray(
                [mass[labels == index].sum() for index in range(len(columns))],
                dtype=np.float64,
            )
            stable_mass /= stable_mass.sum()
            for stable_component in range(len(columns)):
                representatives, backfill = _select_representatives(
                    reduced,
                    labels,
                    responsibilities,
                    stable_component,
                )
                members = np.flatnonzero(labels == stable_component)
                modes.append(
                    FittedMode(
                        component_index=stable_component,
                        weight=float(stable_mass[stable_component]),
                        member_indices=members,
                        representative_indices=representatives,
                        representative_backfill=backfill,
                        unique_ancestor_count=int(len(np.unique(ancestors[members]))),
                    )
                )

            metadata = {
                **base_metadata,
                "selected_components": len(modes),
                "raw_components": int(model.n_components),
                "raw_weights": model.weights_.tolist(),
                "active_raw_components": columns,
                "rejected_components": rejected,
                "scaler_mean": scaler.mean_.tolist(),
                "scaler_scale": scaler.scale_.tolist(),
                "pca_components": pca.components_.tolist(),
                "pca_mean": pca.mean_.tolist(),
                "pca_explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
                "dpgmm_means": model.means_.tolist(),
                "dpgmm_covariances": model.covariances_.tolist(),
            }
            return MixtureFitResult(
                reduced_descriptors=reduced,
                labels=labels,
                responsibilities=responsibilities,
                modes=tuple(modes),
                fit_degraded=False,
                metadata=metadata,
            )
        except Exception as exc:  # numerical failures degrade, never cause expansion
            return _empirical_fallback(
                descriptors,
                ancestors,
                base_metadata,
                f"{type(exc).__name__}: {exc}",
            )


def _first_unique_indices(values: np.ndarray) -> np.ndarray:
    seen: set[int] = set()
    indices: list[int] = []
    for index, raw in enumerate(values):
        value = int(raw)
        if value in seen:
            continue
        seen.add(value)
        indices.append(index)
    return np.asarray(indices, dtype=np.int64)


def _empirical_fallback(
    descriptors: np.ndarray,
    ancestors: np.ndarray,
    metadata: dict,
    reason: str,
) -> MixtureFitResult:
    scaler = StandardScaler()
    standardized = scaler.fit_transform(descriptors)
    dimensions = max(1, min(2, standardized.shape[0], standardized.shape[1]))
    if float(np.var(standardized)) <= 1e-15:
        reduced = np.zeros((len(standardized), dimensions), dtype=np.float64)
    else:
        reduced = PCA(n_components=dimensions, svd_solver="full").fit_transform(standardized)
    labels = np.zeros(len(descriptors), dtype=np.int64)
    responsibilities = np.ones((len(descriptors), 1), dtype=np.float64)
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
                unique_ancestor_count=int(len(np.unique(ancestors))),
            ),
        ),
        fit_degraded=True,
        metadata={**metadata, "selected_components": 1, "fallback_reason": reason},
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
        np.argsort(responsibilities[members, component], kind="stable")[::-1]
    ]
    high_count = max(1, int(np.ceil(len(ranked_members) / 2)))
    high_candidates = [
        int(index) for index in ranked_members[:high_count] if int(index) not in selected
    ]
    if high_candidates:
        selected.append(
            max(
                high_candidates,
                key=lambda index: (float(np.linalg.norm(reduced[index] - reduced[medoid])), -index),
            )
        )

    boundary_candidates = [
        int(index)
        for index in members[
            np.argsort(responsibilities[members, component], kind="stable")
        ]
        if int(index) not in selected
    ]
    if boundary_candidates:
        selected.append(boundary_candidates[0])

    backfill = len(selected) < 3
    fallback_order = np.argsort(responsibilities[:, component], kind="stable")[::-1]
    for index in fallback_order:
        if len(selected) >= 3:
            break
        if int(index) not in selected:
            selected.append(int(index))
    if len(selected) != 3:
        raise RuntimeError("at least three real samples are required for representatives")
    return {
        "medoid": selected[0],
        "diverse": selected[1],
        "boundary": selected[2],
    }, backfill


__all__ = [
    "FittedMode",
    "MixtureFitResult",
    "TrajectoryModeFitter",
]
