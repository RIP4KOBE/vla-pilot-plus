"""Top-level fixed-context mode-gate controller."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Sequence

from .artifacts import ArtifactStore
from .config import ModeGateConfig
from .gate import TrajectoryModeGate
from .protocols import Planner, SteeringBlackBox, Verifier
from .types import (
    ControllerResult,
    ControllerStatus,
    ExpansionRequest,
    GateContext,
    PlannerAction,
    PlannerDecision,
    RoundEvidence,
    VerifierEvidence,
)


class ModeGateController:
    def __init__(
        self,
        config: ModeGateConfig,
        gate: TrajectoryModeGate,
        planner: Planner,
        verifier: Verifier,
    ) -> None:
        self.config = config
        self.gate = gate
        self.planner = planner
        self.verifier = verifier
        self._executor = ThreadPoolExecutor(
            max_workers=config.verifier_workers,
            thread_name_prefix="mode-gate-verifier",
        )

    def preflight(self) -> None:
        planner_preflight = getattr(self.planner, "preflight", None)
        verifier_preflight = getattr(self.verifier, "preflight", None)
        if callable(planner_preflight):
            planner_preflight()
        if callable(verifier_preflight):
            verifier_preflight()

    def run(
        self,
        context: GateContext,
        black_box: SteeringBlackBox,
        artifact_root: Path,
    ) -> ControllerResult:
        store = ArtifactStore(artifact_root, context)
        history: list[RoundEvidence] = []
        pending: dict[tuple[int, str], Future[VerifierEvidence]] = {}
        submitted: set[tuple[int, str]] = set()
        completed: list[VerifierEvidence] = []
        last_decision: PlannerDecision | None = None
        last_snapshot = None

        try:
            for expected_round in range(1, self.config.max_rounds + 1):
                last_snapshot = black_box.advance(context)
                batch = black_box.sample(
                    last_snapshot,
                    context,
                    self.config.sample_count,
                )
                if batch.round_id != expected_round:
                    raise ValueError(
                        f"black box returned round {batch.round_id}; expected {expected_round}"
                    )
                evidence = self.gate.analyze(
                    context,
                    batch,
                    store.round_dir(expected_round),
                )
                history.append(evidence)
                store.save_round_analysis(evidence)

                last_decision = self.planner.decide(context, tuple(history))
                store.save_planner_decision(expected_round, last_decision)
                self._submit_selected(
                    context,
                    history,
                    last_decision.verifier_candidate_mode_ids,
                    pending,
                    submitted,
                )
                completed.extend(self._collect_finished(pending, store, wait=False))

                if last_decision.decision is PlannerAction.REQUEST_EXPANSION:
                    completed.extend(self._collect_finished(pending, store, wait=True))
                    request = self._expansion_request(
                        context,
                        last_snapshot.checkpoint_id,
                        last_decision,
                        completed,
                        store,
                        trigger="planner_requested_expansion",
                    )
                    store.save_expansion_request(request)
                    store.finalize(ControllerStatus.REQUEST_EXPANSION)
                    return ControllerResult(
                        status=ControllerStatus.REQUEST_EXPANSION,
                        snapshot=last_snapshot,
                        expansion_request=request,
                        rounds=expected_round,
                    )

                if last_snapshot.is_complete:
                    self._archive_in_background(pending, store)
                    store.finalize(ControllerStatus.STEERING_COMPLETE)
                    return ControllerResult(
                        status=ControllerStatus.STEERING_COMPLETE,
                        snapshot=last_snapshot,
                        execution_action_chunk=last_snapshot.execution_action_chunk,
                        rounds=expected_round,
                    )

                if expected_round == self.config.max_rounds:
                    completed.extend(self._collect_finished(pending, store, wait=True))
                    request = self._expansion_request(
                        context,
                        last_snapshot.checkpoint_id,
                        last_decision,
                        completed,
                        store,
                        trigger="max_steering_rounds_reached",
                    )
                    store.save_expansion_request(request)
                    store.finalize(ControllerStatus.REQUEST_EXPANSION)
                    return ControllerResult(
                        status=ControllerStatus.REQUEST_EXPANSION,
                        snapshot=last_snapshot,
                        expansion_request=request,
                        rounds=expected_round,
                    )

            raise RuntimeError("mode-gate loop exited without a terminal result")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            for future in pending.values():
                future.cancel()
            store.finalize(ControllerStatus.ABORTED, error=error)
            return ControllerResult(
                status=ControllerStatus.ABORTED,
                snapshot=last_snapshot,
                rounds=len(history),
                error=error,
            )

    def _submit_selected(
        self,
        context: GateContext,
        history: Sequence[RoundEvidence],
        selected_mode_ids: Sequence[str],
        pending: dict[tuple[int, str], Future[VerifierEvidence]],
        submitted: set[tuple[int, str]],
    ) -> None:
        mode_lookup = {
            mode.mode_id: (round_item, mode)
            for round_item in history
            for mode in round_item.modes
        }
        unknown = set(selected_mode_ids) - set(mode_lookup)
        if unknown:
            raise ValueError(f"Planner selected unknown verifier modes: {sorted(unknown)}")
        for mode_id in selected_mode_ids:
            round_item, mode = mode_lookup[mode_id]
            key = (round_item.round_id, mode_id)
            if key in submitted:
                continue
            submitted.add(key)
            pending[key] = self._executor.submit(
                self.verifier.verify,
                context,
                round_item,
                mode,
            )

    @staticmethod
    def _collect_finished(
        pending: dict[tuple[int, str], Future[VerifierEvidence]],
        store: ArtifactStore,
        *,
        wait: bool,
    ) -> list[VerifierEvidence]:
        completed = []
        for key, future in list(pending.items()):
            if not wait and not future.done():
                continue
            evidence = future.result()  # intentionally no timeout for expansion
            store.save_verifier_evidence(key[0], evidence)
            completed.append(evidence)
            del pending[key]
        return completed

    @staticmethod
    def _archive_in_background(
        pending: dict[tuple[int, str], Future[VerifierEvidence]],
        store: ArtifactStore,
    ) -> None:
        for (round_id, mode_id), future in list(pending.items()):
            def archive(
                finished: Future[VerifierEvidence],
                *,
                saved_round_id: int = round_id,
                saved_mode_id: str = mode_id,
            ) -> None:
                try:
                    store.save_verifier_evidence(saved_round_id, finished.result())
                except Exception as exc:
                    store.record_background_error(saved_round_id, saved_mode_id, exc)

            future.add_done_callback(archive)
        pending.clear()

    @staticmethod
    def _expansion_request(
        context: GateContext,
        checkpoint_id: str,
        decision: PlannerDecision,
        verifier_evidence: Sequence[VerifierEvidence],
        store: ArtifactStore,
        *,
        trigger: str,
    ) -> ExpansionRequest:
        missing = decision.required_trajectory_pattern
        if verifier_evidence:
            verifier_missing = sorted(
                {
                    item
                    for evidence in verifier_evidence
                    for item in evidence.missing_subpatterns
                    if item
                }
            )
            if verifier_missing:
                missing = "; ".join(verifier_missing)
        return ExpansionRequest(
            context_id=context.context_id,
            trigger_reason=trigger,
            missing_or_hard_pattern=missing,
            steering_checkpoint_id=checkpoint_id,
            planner_decision=decision,
            verifier_evidence=tuple(verifier_evidence),
            artifact_manifest=store.manifest_path,
        )
