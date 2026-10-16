"""Episode-boundary active revision loader with fresh-load canary semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .registry import ActiveDeployment, PolicyRegistry


@dataclass(frozen=True)
class DeploymentBundle:
    deployment: ActiveDeployment
    policy: Any
    verifier: Any | None
    canary: dict[str, Any]


class EpisodeBoundaryDeploymentManager:
    def __init__(
        self,
        *,
        registry: PolicyRegistry,
        policy_loader: Callable[[ActiveDeployment], Any],
        verifier_loader: Callable[[ActiveDeployment], Any | None],
        canary: Callable[[Any, Any | None, ActiveDeployment], dict[str, Any]],
        initial_revision: int = 0,
    ) -> None:
        self.registry = registry
        self.policy_loader = policy_loader
        self.verifier_loader = verifier_loader
        self.canary = canary
        self.current_revision = int(initial_revision)

    def reload_if_changed(self, *, at_episode_boundary: bool) -> DeploymentBundle | None:
        if not at_episode_boundary:
            raise RuntimeError("active policy may only be read at an episode boundary")
        active = self.registry.active()
        if active is None or active.deployment_revision == self.current_revision:
            return None
        if active.deployment_revision < self.current_revision:
            raise RuntimeError("active deployment revision moved backwards")
        # Nothing visible is mutated until all fresh loads and canaries pass.
        policy = self.policy_loader(active)
        verifier = self.verifier_loader(active)
        if active.controller_mode == "learned_verifier" and verifier is None:
            raise RuntimeError("learned verifier deployment has no loadable verifier")
        canary_result = self.canary(policy, verifier, active)
        if not bool(canary_result.get("passed", False)):
            raise RuntimeError(f"deployment canary failed: {canary_result}")
        self.current_revision = active.deployment_revision
        return DeploymentBundle(active, policy, verifier, canary_result)


__all__ = ["DeploymentBundle", "EpisodeBoundaryDeploymentManager"]
