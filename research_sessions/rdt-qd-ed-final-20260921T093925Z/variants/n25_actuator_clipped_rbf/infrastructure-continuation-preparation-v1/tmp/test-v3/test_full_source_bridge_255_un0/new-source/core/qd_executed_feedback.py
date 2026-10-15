"""N3: fixed previous executed-prefix feedback; no model or environment calls."""
from __future__ import annotations

import copy
import hashlib
import time

import torch

from core.qd_executed_quality import _validate_keypoints

MODE = "executed_feedback_v1"


def native_identity(value):
    value = value.detach().cpu().contiguous()
    prefix = f"{value.dtype}:{tuple(value.shape)}:".encode()
    return hashlib.sha256(prefix + value.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def native_record(value):
    value = value.detach().cpu().clone()
    return {"dtype": str(value.dtype), "shape": list(value.shape),
            "sha256": native_identity(value), "values": value.tolist()}


def _finite(value, shape, name):
    if not torch.is_tensor(value) or tuple(value.shape) != tuple(shape) or not value.is_floating_point():
        raise RuntimeError(f"N3 {name} shape/dtype invalid")
    if not torch.isfinite(value).all():
        raise FloatingPointError(f"N3 {name} nonfinite")


def executed_displacement_residual(projected_xyz, source_origin, actual_endpoint):
    """Exact diagnostic bookkeeping from stored native values, CPU float64."""
    _finite(projected_xyz, (9, 3), "selected projection")
    _finite(source_origin, (3,), "source origin")
    _finite(actual_endpoint, (3,), "actual endpoint")
    x = projected_xyz.detach().to(device="cpu", dtype=torch.float64)
    origin = source_origin.detach().to(device="cpu", dtype=torch.float64)
    endpoint = actual_endpoint.detach().to(device="cpu", dtype=torch.float64)
    residual = (endpoint - origin) - (x[8] - x[0])
    _finite(residual, (3,), "displacement residual")
    return residual


def executed_feedback_quality(projected_xyz, keypoints, *, target_index, residual_previous):
    """Original T7 expression on native x_i + (i/8)*cast(r); native storage."""
    if not torch.is_tensor(projected_xyz) or projected_xyz.ndim != 3:
        raise RuntimeError("N3 projection must be (B,9,3)")
    _finite(projected_xyz, (projected_xyz.shape[0], 9, 3), "projection")
    _validate_keypoints(keypoints, target_index)
    if keypoints.dtype != projected_xyz.dtype or keypoints.device != projected_xyz.device:
        raise RuntimeError("N3 keypoint/projection dtype/device mismatch")
    _finite(residual_previous, (3,), "previous residual")
    if residual_previous.dtype != torch.float64 or residual_previous.device.type != "cpu":
        raise RuntimeError("N3 residual bookkeeping must be CPU float64")
    if torch.get_default_dtype() != torch.float32:
        raise RuntimeError("N3 original weight contract requires default float32")
    residual = residual_previous.to(device=projected_xyz.device, dtype=projected_xyz.dtype)
    ramp = torch.arange(1, 8, device=projected_xyz.device, dtype=projected_xyz.dtype) / 8
    points = projected_xyz[:, 1:8] + ramp[None, :, None] * residual
    _finite(points, (projected_xyz.shape[0], 7, 3), "corrected view")
    timesteps = torch.arange(7, device=points.device)
    weights = torch.where(timesteps >= int(.7 * 7), torch.tensor(3., device=points.device),
                          torch.tensor(1., device=points.device))
    weights = weights / weights.sum()
    target_pos = keypoints[torch.tensor([target_index], dtype=torch.long, device=keypoints.device)][0]
    # Preserve provider's per-candidate arithmetic, mean, and native storage.
    results = []
    for b in range(points.shape[0]):
        distances = torch.norm(points[b:b + 1] - target_pos, dim=-1)
        reward = -(distances ** 2 * weights).sum(dim=1)
        results.append(reward.mean().to(dtype=projected_xyz.dtype))
    output = torch.stack(results)
    _finite(output, (projected_xyz.shape[0],), "internal quality")
    return output


class FeedbackContract:
    mode = MODE

    def __init__(self, semantic, context, *, eligible, reason, previous=None):
        self.semantic = semantic
        self.target_index = semantic.target_index
        self.identity = semantic.identity
        self.context = copy.deepcopy(context)
        self.eligible = eligible
        self.reason = reason
        self.previous = previous
        self.residual = None if previous is None else previous["residual"].clone()
        self.active = self.residual is not None
        self.candidates = {}
        self.overhead_seconds = 0.

    def validate(self, providers):
        self.semantic.validate(providers)

    def record(self, samples, projected_xyz, origins, raw_rewards):
        started = time.perf_counter()
        _finite(samples, (samples.shape[0], 64, 128), "canonical candidates")
        _finite(projected_xyz, (samples.shape[0], 9, 3), "canonical projection")
        _finite(raw_rewards, (samples.shape[0],), "canonical raw quality")
        if samples.dtype != projected_xyz.dtype or raw_rewards.dtype != samples.dtype:
            raise RuntimeError("N3 canonical native dtype association mismatch")
        if len(origins) != samples.shape[0]:
            raise RuntimeError("N3 origin/candidate association mismatch")
        for sample, projection, origin, raw in zip(samples, projected_xyz, origins, raw_rewards):
            _finite(origin, (3,), "canonical source origin")
            fingerprint = native_identity(sample)
            row = {"sample": sample.detach().cpu().clone(),
                   "projection": projection.detach().cpu().clone(),
                   "origin": origin.detach().cpu().clone(), "raw": raw.detach().cpu().clone()}
            old = self.candidates.get(fingerprint)
            if old is not None and any(native_identity(old[k]) != native_identity(row[k])
                                       for k in ("sample", "projection", "origin", "raw")):
                # Same native action with incompatible observations cannot certify history.
                if self.active:
                    raise RuntimeError("N3 active duplicate selected association contradiction")
                self.eligible = False
                self.reason = "ambiguous_native_candidate_association"
            else:
                self.candidates[fingerprint] = row
        self.overhead_seconds += time.perf_counter() - started

    def selected(self, selected):
        row = self.candidates.get(native_identity(selected[0]))
        if row is None or native_identity(row["sample"]) != native_identity(selected[0]):
            raise RuntimeError("N3 selected candidate missing canonical native association")
        return row

    def previous_record(self):
        if self.previous is None:
            return {}
        return {k: native_record(v) if torch.is_tensor(v) else copy.deepcopy(v)
                for k, v in self.previous.items() if k != "context"}


class ExecutedFeedbackHistory:
    """One completed predecessor, consumed only at the next fresh decision."""
    def __init__(self):
        self.generation = 0
        self.pending = None
        self.completed = None
        self.reason = "no_complete_history"

    def clear(self, reason, *, reset=False):
        self.pending = self.completed = None
        self.reason = reason
        if reset:
            self.generation += 1

    def begin(self, semantic, *, stage, global_step, tracker):
        tracker = copy.deepcopy(tracker) if isinstance(tracker, dict) else {}
        targets = tracker.get("targets", {})
        target = targets.get(str(semantic.target_index), {}) if isinstance(targets, dict) else {}
        target = target if isinstance(target, dict) else {}
        eligible = (type(stage) is int and type(global_step) is int and global_step >= 0
                    and type(tracker.get("generation")) is int and type(tracker.get("instance_id")) is int
                    and target.get("valid") is True
                    and target.get("status") in {"tracked", "static_background"})
        context = {"episode_generation": self.generation, "global_step": global_step, "stage": stage,
                   "provider_identity": copy.deepcopy(semantic.identity), "target_index": semantic.target_index,
                   "registry_instance_id": tracker.get("instance_id"), "registry_generation": tracker.get("generation"), "target_status": target.get("status", "unknown"),
                   "target_valid": eligible, "tracker_snapshot": tracker}
        previous = self.completed
        reason = self.reason
        if self.pending is not None:
            self.clear("partial_or_missing_acknowledgements")
            previous = None
            reason = self.reason
        if not eligible:
            self.clear("target_tracking_or_context_unknown")
            previous = None
            reason = self.reason
        elif previous is not None:
            old = previous["context"]
            fields = ("episode_generation", "stage", "provider_identity", "target_index", "registry_instance_id", "registry_generation")
            if any(old[k] != context[k] for k in fields):
                self.clear("provider_stage_or_registry_changed")
                previous = None
                reason = self.reason
            elif global_step != previous["end_global_step"] + 1:
                self.clear("noncontiguous_decision")
                previous = None
                reason = self.reason
            else:
                reason = "eligible_immediate_full_prefix"
        self.completed = None  # No history may skip a decision or influence itself.
        return FeedbackContract(semantic, context, eligible=eligible, reason=reason, previous=previous)

    def select(self, contract, selected):
        row = contract.selected(selected)
        record = {"selected_native_sha256": native_identity(row["sample"]),
                  "projection": native_record(row["projection"]), "source_origin": native_record(row["origin"]),
                  "raw_provider_quality": native_record(row["raw"]),
                  "start_global_step": contract.context["global_step"], "eligible": contract.eligible}
        self.pending = None
        if contract.eligible:
            self.pending = {**row, "context": copy.deepcopy(contract.context), "active": contract.active,
                            "selected_native_sha256": record["selected_native_sha256"], "ack_count": 0,
                            "start_global_step": contract.context["global_step"], "actions": None}
        self.reason = contract.reason
        return record

    def bind_decode(self, raw, actions, active_indices):
        if self.pending is None:
            return
        plan = self.pending
        expected = plan["sample"][:, active_indices].float()
        actual = raw[0].detach().cpu()[:, active_indices]
        if actual.dtype != torch.float32 or not torch.equal(expected, actual):
            self._contradiction("selected_decode_identity_mismatch")
            return
        _finite(actions, (1, 8, 7), "decoded execution prefix")
        plan["actions"] = actions.detach().cpu().clone()

    def commit(self, actions, horizon, global_step):
        if self.pending is None:
            return
        plan = self.pending
        if horizon != 8:
            self.clear("partial_execution_horizon")
            return
        if type(global_step) is not int or global_step != plan["start_global_step"]:
            self._contradiction("commit_global_step_mismatch")
            return
        if plan["actions"] is None or native_identity(actions) != native_identity(plan["actions"]):
            self._contradiction("committed_action_identity_mismatch")
            return
        if plan.get("committed"):
            self._contradiction("duplicate_commit")
            return
        plan["committed"] = True

    def _contradiction(self, reason):
        active = self.pending is not None and self.pending["active"]
        self.clear(reason)
        if active:
            raise RuntimeError(f"N3 active execution feedback contradiction: {reason}")

    def acknowledge(self, *, global_step, execution_index, action, endpoint, terminated, truncated):
        plan = self.pending
        if plan is None:
            if self.completed is not None:
                active = self.completed["feedback_was_active"]
                self.clear("duplicate_ack_after_complete")
                if active:
                    raise RuntimeError("N3 active execution feedback contradiction: duplicate_ack_after_complete")
            return None
        if (type(global_step) is not int or type(execution_index) is not int
                or not plan.get("committed") or execution_index != plan["ack_count"] + 1
                or global_step != plan["start_global_step"] + plan["ack_count"]):
            self._contradiction("duplicate_missing_or_out_of_order_ack")
            return None
        if native_identity(action) != native_identity(plan["actions"][0, execution_index - 1]):
            self._contradiction("acknowledged_action_identity_mismatch")
            return None
        if terminated or truncated:
            self.clear("terminal_or_truncated")
            return None
        try:
            _finite(endpoint, (3,), "pre_reset_actual_endpoint")
        except (RuntimeError, FloatingPointError):
            self._contradiction("actual_endpoint_missing_or_invalid")
            return None
        endpoint = endpoint.detach().cpu().clone()
        plan["ack_count"] += 1
        if plan["ack_count"] < 8:
            return None
        residual = executed_displacement_residual(plan["projection"], plan["origin"], endpoint)
        self.completed = {"context": plan["context"], "selected_native_sha256": plan["selected_native_sha256"],
            "start_global_step": plan["start_global_step"], "end_global_step": global_step, "ack_count": 8, "feedback_was_active": plan["active"],
            "terminated": False, "truncated": False, "projection": plan["projection"],
            "source_origin": plan["origin"], "actual_endpoint": endpoint, "residual": residual}
        self.pending = None
        self.reason = "complete_predecessor"
        return {k: native_record(v) if torch.is_tensor(v) else copy.deepcopy(v)
                for k, v in self.completed.items()}
