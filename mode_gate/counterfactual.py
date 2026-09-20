"""Exact snapshot counterfactual replay with adaptive 16→32 branches."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import inspect
from pathlib import Path
import random
from typing import Any, Callable, Mapping, Protocol

import numpy as np
import torch

from .evaluation import (
    adaptive_counterfactual_target,
    counterfactual_posterior_status,
)
from .experiment_contract import (
    DEFAULT_RETRY_SCHEDULE_50,
    FIXED_BUDGET_50_CONTRACT,
    label_contract_payload,
    require_fixed_budget_50_contract,
)
from .incidents import IncidentMemory, VerifierLabelRecord
from .io_utils import AtomicJsonl, atomic_write_json
from .snapshots import DecisionSnapshotStore
from .types import ProgressEvidence, SamplingCondition


REPLAY_PROGRESS_CONTRACT = "libero-native-success-terminal-fixed50-v3"


@dataclass(frozen=True)
class BranchOutcome:
    success: bool
    chunks_executed: int
    stage_advanced: bool = False
    task_success: bool = False
    terminal_timeout: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CounterfactualResult:
    record_id: str
    policy_id: str
    branches: int
    successes: int
    p_expansion: float
    posterior_interval: tuple[float, float]
    posterior_side_probability: float
    label_status: str
    censored: bool
    label_attached: bool


class BranchExecutor(Protocol):
    def __call__(
        self,
        *,
        adapter: Any,
        policy: Any,
        branch_seed: int,
        remaining_budget: int,
        controller_state: Mapping[str, Any],
    ) -> BranchOutcome | bool: ...


class NewPolicyFeatureBuilder(Protocol):
    def __call__(
        self,
        *,
        context: Mapping[str, Any],
        policy_id: str,
        output_path: Path,
    ) -> Path: ...


@dataclass(frozen=True)
class FreshCandidateSelection:
    """One already-scored, safe candidate in executable environment action space."""

    actions: np.ndarray
    candidate_id: str
    sample_index: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        value = np.asarray(self.actions, dtype=np.float32)
        if value.ndim == 3:
            if value.shape[0] != 1:
                raise ValueError("fresh candidate selection must contain exactly one chunk")
            value = value[0]
        if value.ndim != 2 or value.shape[1] < 7 or len(value) < 1:
            raise ValueError("fresh candidate actions must have shape (H, 7+)")
        if not np.isfinite(value).all():
            raise ValueError("fresh candidate actions contain non-finite values")
        if not self.candidate_id or self.sample_index < 0:
            raise ValueError("fresh candidate selection requires a valid mode/sample")
        object.__setattr__(self, "actions", value)
        object.__setattr__(self, "metadata", dict(self.metadata))


class FreshCandidateSampler(Protocol):
    def __call__(
        self,
        *,
        adapter: Any,
        policy: Any,
        condition: SamplingCondition,
    ) -> FreshCandidateSelection | None: ...


class FixedBudgetResteerExecutor:
    """Execute the configured RE-STEER schedule from an exact snapshot.

    ``fresh_sampler`` owns policy sampling, full candidate projection, geometry safety,
    and semantic candidate selection.  This executor owns the estimand-defining
    behavior policy: every failed opportunity gets a new sample, executes at
    most one 10-step chunk, and never consults the learned verifier.
    """

    def __init__(
        self,
        *,
        fresh_sampler: FreshCandidateSampler,
        retry_schedule: tuple[tuple[float, float], ...] = DEFAULT_RETRY_SCHEDULE_50,
        chunk_horizon: int = 10,
        progress_observer: Callable[..., ProgressEvidence] | None = None,
    ) -> None:
        if not retry_schedule:
            raise ValueError("counterfactual retry schedule must be non-empty")
        if int(chunk_horizon) <= 0:
            raise ValueError("counterfactual chunk horizon must be positive")
        self.fresh_sampler = fresh_sampler
        self.retry_schedule = tuple(
            (float(guide), float(diversity))
            for guide, diversity in retry_schedule
        )
        self.chunk_horizon = int(chunk_horizon)
        self.progress_observer = progress_observer

    def __call__(
        self,
        *,
        adapter: Any,
        policy: Any,
        branch_seed: int,
        remaining_budget: int,
        controller_state: Mapping[str, Any],
    ) -> BranchOutcome:
        retry_budget = int(controller_state.get("retry_budget", len(self.retry_schedule)))
        if retry_budget != len(self.retry_schedule):
            raise ValueError("controller retry budget and schedule length disagree")
        if not 1 <= int(remaining_budget) <= retry_budget:
            raise ValueError(
                "counterfactual replay requires an actionable remaining budget"
            )
        retry_index = int(
            controller_state.get("retry_index", retry_budget - remaining_budget)
        )
        if retry_index < 0 or retry_index + remaining_budget > retry_budget:
            raise ValueError("snapshot retry index and remaining budget are inconsistent")
        attempts: list[dict[str, Any]] = []
        chunks_executed = 0
        def condition_for(offset: int) -> SamplingCondition:
            schedule_index = retry_index + offset
            guide, diversity = self.retry_schedule[schedule_index]
            return SamplingCondition(
                seed=_attempt_seed(branch_seed, offset),
                retry_index=schedule_index,
                guide_mult=guide,
                diversity_mult=diversity,
            )

        for offset in range(int(remaining_budget)):
            condition = condition_for(offset)
            schedule_index = condition.retry_index
            guide, diversity = condition.guide_mult, condition.diversity_mult
            seed = condition.seed
            random.seed(seed)
            np.random.seed(seed % (2**32))
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
            selection = self.fresh_sampler(
                adapter=adapter,
                policy=policy,
                condition=condition,
            )
            attempt = {
                "schedule_index": schedule_index,
                "seed": seed,
                "guide_mult": guide,
                "diversity_mult": diversity,
                "no_safe_mode": selection is None,
            }
            if selection is None:
                attempts.append(attempt)
                continue
            attempt.update(
                {
                    "candidate_id": selection.candidate_id,
                    "sample_index": selection.sample_index,
                    "selection_metadata": dict(selection.metadata),
                }
            )
            before = _progress_snapshot(adapter)
            terminal = False
            task_success = False
            executed_steps = 0
            for action in selection.actions[: self.chunk_horizon]:
                # FreshCandidateSelection is deliberately serialized in NumPy
                # environment-action space.  LeRobot adapters, however,
                # require a torch PolicyAction at their processor boundary.
                # Normalize that contract here so offline replay cannot feed
                # an ndarray into a policy processor.
                adapter_action = torch.as_tensor(
                    action,
                    dtype=torch.float32,
                )
                step_value = adapter.step(adapter_action)
                _, _, terminated, truncated, info = _unpack_step(step_value)
                executed_steps += 1
                task_success = bool(info.get("success", False)) or _adapter_success(
                    adapter
                )
                terminal = bool(terminated or truncated)
                if task_success or terminal:
                    break
            chunks_executed += 1
            if task_success:
                attempt.update(
                    {
                        "executed_steps": executed_steps,
                        "stage_advanced": False,
                        "task_success": True,
                        "terminal": terminal,
                        "progress_stage_id": "TASK_SUCCESS",
                        "progress_confidence": 1.0,
                        "progress_source": "libero_success",
                    }
                )
                attempts.append(attempt)
                return BranchOutcome(
                    success=True,
                    chunks_executed=chunks_executed,
                    task_success=True,
                    metadata={"attempts": attempts},
                )
            if terminal:
                attempt.update(
                    {
                        "executed_steps": executed_steps,
                        "stage_advanced": False,
                        "task_success": False,
                        "terminal": True,
                        "progress_stage_id": "TERMINAL",
                        "progress_confidence": 1.0,
                        "progress_source": "libero_terminal",
                    }
                )
                attempts.append(attempt)
                return BranchOutcome(
                    success=False,
                    chunks_executed=chunks_executed,
                    terminal_timeout=True,
                    metadata={"attempts": attempts},
                )
            after = _progress_snapshot(adapter)
            has_next_attempt = offset + 1 < int(remaining_budget)
            next_condition = (
                condition_for(offset + 1)
                if has_next_attempt
                else SamplingCondition(
                    seed=_progress_probe_seed(branch_seed, offset),
                    retry_index=schedule_index,
                    guide_mult=guide,
                    diversity_mult=diversity,
                )
            )
            progress = self._observe_progress(
                adapter=adapter,
                before=before,
                after=after,
                task_success=task_success,
                selection=selection,
                next_condition=next_condition,
                cache_next_selection=has_next_attempt,
                terminal=terminal,
            )
            attempt.update(
                {
                    "executed_steps": executed_steps,
                    "stage_advanced": progress.advanced,
                    "task_success": progress.task_success,
                    "terminal": terminal,
                    "progress_stage_id": progress.stage_id,
                    "progress_confidence": progress.confidence,
                    "progress_source": progress.source,
                }
            )
            attempts.append(attempt)
            if progress.task_success:
                return BranchOutcome(
                    success=True,
                    chunks_executed=chunks_executed,
                    stage_advanced=progress.advanced,
                    task_success=progress.task_success,
                    metadata={"attempts": attempts},
                )
        return BranchOutcome(
            success=False,
            chunks_executed=chunks_executed,
            metadata={"attempts": attempts},
        )

    def _observe_progress(
        self,
        *,
        adapter: Any,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        task_success: bool,
        selection: FreshCandidateSelection,
        next_condition: SamplingCondition,
        cache_next_selection: bool,
        terminal: bool,
    ) -> ProgressEvidence:
        if self.progress_observer is not None:
            kwargs = {
                "adapter": adapter,
                "before": before,
                "after": after,
                "task_success": task_success,
            }
            optional = {
                "selection": selection,
                "next_condition": next_condition,
                "cache_next_selection": cache_next_selection,
                "terminal": terminal,
            }
            parameters = inspect.signature(self.progress_observer).parameters
            accepts_kwargs = any(
                item.kind is inspect.Parameter.VAR_KEYWORD
                for item in parameters.values()
            )
            if accepts_kwargs:
                kwargs.update(optional)
            else:
                kwargs.update(
                    {key: value for key, value in optional.items() if key in parameters}
                )
            value = self.progress_observer(
                **kwargs,
            )
            if not isinstance(value, ProgressEvidence):
                raise TypeError("progress_observer must return ProgressEvidence")
            return value
        before_stage = before.get("stage_id")
        after_stage = after.get("stage_id")
        explicit_advanced = after.get("advanced")
        advanced = bool(explicit_advanced) or (
            before_stage is not None
            and after_stage is not None
            and str(before_stage) != str(after_stage)
        )
        confidence = 1.0 if explicit_advanced is not None or advanced else 0.0
        return ProgressEvidence(
            stage_id=str(after_stage or "UNKNOWN"),
            advanced=advanced,
            confidence=confidence,
            source="simulator_predicate" if confidence else "unknown",
            task_success=bool(task_success),
        )


class CounterfactualReplayWorker:
    """Replay one decision context without changing the active deployment."""

    def __init__(
        self,
        *,
        incidents: IncidentMemory,
        snapshots: DecisionSnapshotStore,
        adapter: Any,
        policy_loader: Callable[[str], Any],
        branch_executor: BranchExecutor,
        ledger_path: Path,
        stateful_components: Mapping[str, Any] | None = None,
    ) -> None:
        self.incidents = incidents
        self.snapshots = snapshots
        self.adapter = adapter
        self.policy_loader = policy_loader
        self.branch_executor = branch_executor
        self.ledger = AtomicJsonl(Path(ledger_path))
        self.stateful_components = dict(stateful_components or {})

    def run(
        self,
        *,
        record_id: str,
        policy_id: str,
        label_version: str,
        source: str = "counterfactual_replay",
        verifier_feature_path: Path | None = None,
        data_split: str | None = None,
        label_config: Mapping[str, Any] | None = None,
        budget_state: Mapping[str, Any] | None = None,
    ) -> CounterfactualResult:
        contract_payload = dict(
            label_config or label_contract_payload(FIXED_BUDGET_50_CONTRACT)
        )
        contract = require_fixed_budget_50_contract(contract_payload)
        if label_version != contract.label_version:
            raise ValueError("counterfactual label version/config mismatch")
        decision = self._decision(record_id)
        budget_state = dict(budget_state or {})
        retry_budget = int(budget_state.get("retry_budget", contract.retry_budget))
        retry_index = int(budget_state.get("retry_index", 0))
        remaining_budget = int(
            budget_state.get("remaining_budget", retry_budget - retry_index)
        )
        if (
            retry_budget != contract.retry_budget
            or retry_index < 0
            or remaining_budget != retry_budget - retry_index
            or remaining_budget <= 0
        ):
            raise ValueError(
                "counterfactual budget state is not fixed_budget_50 actionable"
            )
        budget_state.update(
            {
                "retry_budget": retry_budget,
                "retry_index": retry_index,
                "remaining_budget": remaining_budget,
            }
        )
        if verifier_feature_path is None:
            if policy_id != str(decision["policy_id"]):
                raise ValueError(
                    "new-policy replay requires its fresh-mode verifier feature sidecar"
                )
            verifier_feature_path = Path(str(decision["verifier_feature_path"]))
        verifier_feature_path = Path(verifier_feature_path)
        if not verifier_feature_path.is_file():
            raise FileNotFoundError(verifier_feature_path)
        policy = self.policy_loader(policy_id)
        if isinstance(policy, Mapping) and "policy" in policy:
            policy = policy["policy"]
        completed = self._completed(
            record_id,
            policy_id,
            label_version=label_version,
            contract_hash=contract.contract_hash,
        )
        target = contract.counterfactual_initial_branches
        interval = (0.0, 1.0)
        while True:
            for branch_index in range(target):
                if branch_index in completed:
                    continue
                outcome = self._run_branch(
                    decision=decision,
                    policy=policy,
                    policy_id=policy_id,
                    branch_index=branch_index,
                    budget_state=budget_state,
                    label_version=label_version,
                    contract_hash=contract.contract_hash,
                )
                event = {
                    "event_id": _branch_id(
                        record_id,
                        policy_id,
                        branch_index,
                        label_version=label_version,
                        contract_hash=contract.contract_hash,
                    ),
                    "event": "COUNTERFACTUAL_BRANCH_COMPLETED",
                    "record_id": record_id,
                    "policy_id": policy_id,
                    "branch_index": branch_index,
                    "branch_seed": _branch_seed(
                        record_id,
                        policy_id,
                        branch_index,
                        label_version=label_version,
                        contract_hash=contract.contract_hash,
                    ),
                    "label_version": label_version,
                    "label_contract_hash": contract.contract_hash,
                    "budget_state": dict(budget_state),
                    **asdict(outcome),
                }
                self.ledger.append(event)
                completed[branch_index] = event
            successes = sum(
                bool(completed[index]["success"]) for index in range(target)
            )
            next_target, interval = adaptive_counterfactual_target(
                successes=successes,
                trials=target,
                posterior_confidence=contract.posterior_confidence,
                decision_boundary=contract.decision_boundary,
                initial_branches=contract.counterfactual_initial_branches,
                max_branches=contract.counterfactual_max_branches,
            )
            if next_target == target:
                break
            target = next_target

        posterior = counterfactual_posterior_status(
            successes=successes,
            trials=target,
            posterior_confidence=contract.posterior_confidence,
            decision_boundary=contract.decision_boundary,
        )
        p_expansion = 1.0 - successes / target
        attached = False
        if posterior["label_status"] == "LABELED":
            label = VerifierLabelRecord(
                record_id=record_id,
                label_version=label_version,
                source=source,
                branches=target,
                successes=successes,
                p_expansion=p_expansion,
                policy_id=policy_id,
                snapshot_hash=str(decision["snapshot_hash"]),
                verifier_feature_path=str(verifier_feature_path.resolve()),
                data_split=data_split,
                weak=False,
                weight=1.0,
                label_config=contract_payload,
            )
            attached = self.incidents.attach_label(label)
        return CounterfactualResult(
            record_id=record_id,
            policy_id=policy_id,
            branches=target,
            successes=successes,
            p_expansion=p_expansion,
            posterior_interval=interval,
            posterior_side_probability=float(
                posterior["posterior_side_probability"]
            ),
            label_status=str(posterior["label_status"]),
            censored=posterior["label_status"] != "LABELED",
            label_attached=attached,
        )

    def _run_branch(
        self,
        *,
        decision: Mapping[str, Any],
        policy: Any,
        policy_id: str,
        branch_index: int,
        budget_state: Mapping[str, Any],
        label_version: str,
        contract_hash: str,
    ) -> BranchOutcome:
        restored = self.snapshots.restore(
            str(decision["snapshot_id"]),
            adapter=self.adapter,
            policy=policy,
            stateful_components=self.stateful_components,
            restore_policy_state=policy_id == str(decision["policy_id"]),
        )
        manifest = restored["manifest"]
        if manifest["snapshot_hash"] != decision["snapshot_hash"]:
            raise RuntimeError("decision/snapshot hash mismatch during replay")
        seed = _branch_seed(
            str(decision["record_id"]),
            policy_id,
            branch_index,
            label_version=label_version,
            contract_hash=contract_hash,
        )
        random.seed(seed)
        np.random.seed(seed % (2**32))
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        value = self.branch_executor(
            adapter=self.adapter,
            policy=policy,
            branch_seed=seed,
            remaining_budget=int(budget_state["remaining_budget"]),
            controller_state=budget_state,
        )
        if isinstance(value, bool):
            return BranchOutcome(
                success=value,
                chunks_executed=int(budget_state["remaining_budget"]),
                task_success=value,
            )
        if value.chunks_executed < 0 or value.chunks_executed > int(
            budget_state["remaining_budget"]
        ):
            raise ValueError("branch executor exceeded the configured retry budget")
        if value.success != value.task_success:
            raise ValueError("branch success must be LIBERO-PRO native task success")
        return value

    def _decision(self, record_id: str) -> dict[str, Any]:
        matches = [
            item
            for item in self.incidents.decisions.iter_valid()
            if item.get("record_id") == record_id
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one verifier decision {record_id!r}, got {len(matches)}")
        return matches[0]

    def _completed(
        self,
        record_id: str,
        policy_id: str,
        *,
        label_version: str,
        contract_hash: str,
    ) -> dict[int, dict[str, Any]]:
        result = {}
        for item in self.ledger.iter_valid():
            if item.get("record_id") != record_id or item.get("policy_id") != policy_id:
                continue
            if (
                str(item.get("label_version")) != label_version
                or str(item.get("label_contract_hash")) != contract_hash
            ):
                continue
            index = int(item["branch_index"])
            if index in result and result[index] != item:
                raise ValueError(f"conflicting counterfactual branch {index}")
            result[index] = item
        return result


class NewPolicyReplayCoordinator:
    """Execute a code-owned staged-policy replay plan and attach all labels.

    ``feature_builder`` is the simulator integration boundary: it must restore
    the listed post-failure snapshot, fresh-sample the staged policy, recompute
    modes/geometry/Gemini channels, and persist the resulting verifier input at
    the exact requested path. ``CounterfactualReplayWorker`` then independently
    restores that snapshot for each adaptive 16→32 retry branch.
    """

    def __init__(
        self,
        *,
        replay_worker: CounterfactualReplayWorker,
        feature_builder: NewPolicyFeatureBuilder,
    ) -> None:
        self.replay_worker = replay_worker
        self.feature_builder = feature_builder

    def run_plan(self, plan_path: Path) -> dict[str, Any]:
        plan_path = Path(plan_path)
        plan = json_load(plan_path)
        if plan.get("schema_version") != "new-policy-counterfactual-plan-v3":
            raise ValueError("unsupported new-policy replay plan")
        if plan.get("decision_rule") != "head_argmax":
            raise ValueError("new-policy replay plan must use direct head argmax")
        if plan.get("progress_contract") != REPLAY_PROGRESS_CONTRACT:
            raise ValueError(
                "new-policy replay plan uses a stale progress contract"
            )
        expected_hash = str(plan.get("plan_sha256") or "")
        unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
        actual_hash = hashlib.sha256(
            json_dumps(unsigned).encode("utf-8")
        ).hexdigest()
        if expected_hash != actual_hash:
            raise ValueError("new-policy replay plan checksum mismatch")
        contract_payload = dict(plan.get("label_config") or {})
        contract = require_fixed_budget_50_contract(contract_payload)
        if str(plan.get("label_version")) != contract.label_version:
            raise ValueError("new-policy replay plan label/config mismatch")
        if tuple(map(int, plan.get("adaptive_branches", ()))) != (
            contract.counterfactual_initial_branches,
            contract.counterfactual_max_branches,
        ):
            raise ValueError("new-policy replay plan branch schedule is not fixed10")
        policy_id = str(plan["policy_id"])
        contexts = tuple(plan.get("contexts", ()))
        record_ids = [str(item["record_id"]) for item in contexts]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("new-policy replay plan contains duplicate records")
        results = []
        label_version = contract.label_version
        for context in contexts:
            budget_state = dict(context.get("budget_state") or {})
            if (
                int(budget_state.get("retry_budget", -1)) != contract.retry_budget
                or int(budget_state.get("remaining_budget", -1))
                != contract.retry_budget - int(budget_state.get("retry_index", -1))
                or not 1
                <= int(budget_state.get("remaining_budget", -1))
                <= contract.retry_budget
            ):
                raise ValueError(
                    "new-policy replay context has no actionable fixed10 budget"
                )
            output_path = Path(str(context["fresh_feature_output_path"]))
            built = Path(
                self.feature_builder(
                    context=context,
                    policy_id=policy_id,
                    output_path=output_path,
                )
            )
            if built.resolve() != output_path.resolve() or not built.is_file():
                raise ValueError(
                    "new-policy feature builder must write the exact planned sidecar"
                )
            result = self.replay_worker.run(
                record_id=str(context["record_id"]),
                policy_id=policy_id,
                label_version=label_version,
                source="counterfactual_replay",
                verifier_feature_path=built,
                data_split=str(context["data_split"]),
                label_config=contract_payload,
                budget_state=budget_state,
            )
            results.append(asdict(result))
        value = {
            "schema_version": "new-policy-counterfactual-result-v2",
            "plan_sha256": expected_hash,
            "policy_id": policy_id,
            "label_version": label_version,
            "label_config": contract_payload,
            "complete": True,
            "contexts_planned": len(contexts),
            "contexts_completed": len(results),
            "results": results,
        }
        result_path = Path(str(plan["result_path"]))
        atomic_write_json(result_path, value)
        return value


def _branch_seed(
    record_id: str,
    policy_id: str,
    branch_index: int,
    *,
    label_version: str = FIXED_BUDGET_50_CONTRACT.label_version,
    contract_hash: str = FIXED_BUDGET_50_CONTRACT.contract_hash,
) -> int:
    digest = hashlib.sha256(
        (
            f"counterfactual-v2\0{label_version}\0{contract_hash}\0"
            f"{record_id}\0{policy_id}\0{branch_index}"
        ).encode()
    ).digest()
    return int.from_bytes(digest[:8], "big") % (2**63 - 1)


def _branch_id(
    record_id: str,
    policy_id: str,
    branch_index: int,
    *,
    label_version: str = FIXED_BUDGET_50_CONTRACT.label_version,
    contract_hash: str = FIXED_BUDGET_50_CONTRACT.contract_hash,
) -> str:
    return hashlib.sha256(
        (
            f"branch-v2\0{label_version}\0{contract_hash}\0"
            f"{record_id}\0{policy_id}\0{branch_index}"
        ).encode()
    ).hexdigest()


def _attempt_seed(branch_seed: int, offset: int) -> int:
    digest = hashlib.sha256(
        f"resteer-attempt-v1\0{int(branch_seed)}\0{int(offset)}".encode()
    ).digest()
    return int.from_bytes(digest[:8], "big") % (2**63 - 1)


def _progress_probe_seed(branch_seed: int, offset: int) -> int:
    digest = hashlib.sha256(
        f"resteer-progress-probe-v1\0{int(branch_seed)}\0{int(offset)}".encode()
    ).digest()
    return int.from_bytes(digest[:8], "big") % (2**63 - 1)


def _progress_snapshot(adapter: Any) -> dict[str, Any]:
    getter = getattr(adapter, "get_progress_predicate", None)
    if not callable(getter):
        return {}
    value = getter()
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("adapter progress predicate must return a mapping")
    return dict(value)


def _adapter_success(adapter: Any) -> bool:
    checker = getattr(adapter, "check_success", None)
    return bool(checker()) if callable(checker) else False


def _unpack_step(value: Any) -> tuple[Any, float, bool, bool, Mapping[str, Any]]:
    if not isinstance(value, tuple):
        raise TypeError("adapter.step must return a tuple")
    if len(value) == 5:
        observation, reward, terminated, truncated, info = value
    elif len(value) == 4:
        observation, reward, done, info = value
        terminated, truncated = bool(done), False
    else:
        raise ValueError("adapter.step must return four or five values")
    if not isinstance(info, Mapping):
        raise TypeError("adapter.step info must be a mapping")
    return observation, float(reward), bool(terminated), bool(truncated), info


def json_load(path: Path) -> dict[str, Any]:
    import json

    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("counterfactual plan must be a JSON object")
    return value


def json_dumps(value: Mapping[str, Any]) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


__all__ = [
    "BranchOutcome",
    "CounterfactualReplayWorker",
    "CounterfactualResult",
    "FixedBudgetResteerExecutor",
    "FreshCandidateSelection",
    "NewPolicyFeatureBuilder",
    "NewPolicyReplayCoordinator",
]
