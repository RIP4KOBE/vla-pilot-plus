"""N30: one executed winner's continuation, without new sampling or scoring."""
from __future__ import annotations
import copy
import hashlib
import math
import torch

MODE = "executed_progress_continuation_v1"
OFF = "off"


def identity(x):
    x = x.detach().cpu().contiguous()
    return hashlib.sha256(str((str(x.dtype), tuple(x.shape))).encode() +
                          x.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def finite_tensor(x, shape):
    return (torch.is_tensor(x) and x.is_floating_point() and tuple(x.shape) == shape
            and bool(torch.isfinite(x).all()))


def capture_context(observation, keypoints, tracking, episode):
    """Copy only already-returned observations; never query tracker/environment."""
    try:
        start = observation["observation.robot_state"]["eef"]["pos"]
    except (KeyError, TypeError, AttributeError):
        start = None
    if torch.is_tensor(start) and tuple(start.shape) in {(3,), (1, 3)}:
        start = start.detach().reshape(3).cpu().clone()
    else:
        start = None
    try:
        points = torch.as_tensor(keypoints).detach().cpu().clone() if keypoints is not None else None
    except (TypeError, ValueError):
        points = None
    return {"start_eef": start, "keypoints": points,
            "tracker": copy.deepcopy(tracking), "episode": episode}


def validate_config(cfg, horizon):
    mode = cfg.executed_progress_continuation_mode
    control = getattr(cfg, "executed_progress_continuation_control", "none")
    if control not in {"none", "qd_off_v1"} or (mode == OFF and control != "none"):
        raise ValueError("N30 future control requires explicit continuation")
    if mode == OFF:
        return
    if mode != MODE:
        raise ValueError("N30 continuation mode unsupported")
    required = {"population_size": 16, "cem_iters": 10,
        "qd_archive_mode": "none" if control == "qd_off_v1" else "grid_archive",
        "qd_parent_sampling": "uniform_cells" if control == "qd_off_v1" else "sparse_priority",
        "qd_quality_mode": "provider",
        "qd_descriptor": "target_relative_endpoint_xy", "qd_final_selection_mode": "archive_global_best",
        "chunk_population_mode": "fresh", "chunk_memory_fraction": 0.,
        "qd_gripper_rescue_mode": "none", "qd_parent_survivor_count": 0,
        "qd_global_quality_anchor_count": 0, "qd_secondary_lane_mode": "none",
        "diversity_update_mode": "legacy_additive", "diversity_input_source": "noisy_sample",
        "rollout_diversity_placement": "model_output", "initial_diversity_descriptor_mode": "absolute_eef",
        "rollout_diversity_descriptor_mode": "absolute_eef"}
    if horizon != 8:
        raise ValueError("N30 requires executed horizon8")
    for k, v in required.items():
        if getattr(cfg, k, None) != v:
            raise ValueError(f"N30 requires {k}={v!r}")


class ProgressContinuation:
    """One immediately completed chunk. Decisions never depend on a recorder."""
    def __init__(self):
        self.generation = 0
        self.invalid_evidence_count = 0
        self.clear("no_history")

    def clear(self, reason, *, invalid=False, reset=False):
        self.pending = self.completed = self.previous = self.current = None
        self.reason = reason
        self.status = "invalid_evidence" if invalid else "inactive"
        self.active = False
        if invalid:
            self.invalid_evidence_count += 1
        if reset:
            self.generation += 1

    def scalar(self):
        return {"mode": MODE, "active": self.active, "status": self.status, "reason": self.reason,
                "slot": 15 if self.active else None, "invalid_evidence_count": self.invalid_evidence_count,
                "previous_start_step": None if self.previous is None else self.previous["start_step"],
                "distance_before_m": None if self.previous is None else self.previous["distance_before_m"],
                "distance_after_m": None if self.previous is None else self.previous["distance_after_m"],
                "distance_scope": "previous_observed_target_snapshot_cpu_float64"}

    def begin(self, semantic, packet, *, stage, step):
        previous = self.completed
        self.completed = self.previous = None
        self.active = False
        if self.pending is not None:
            self.clear("incomplete_predecessor", invalid=True)
            previous = None
        if semantic is None:
            self.clear("unrecognized_single_target_provider")
            return self.scalar()
        p = packet if isinstance(packet, dict) else {}
        tr = p.get("tracker") if isinstance(p.get("tracker"), dict) else {}
        targets = tr.get("targets")
        target_state = targets.get(str(semantic.target_index), {}) if isinstance(targets, dict) else {}
        points = p.get("keypoints")
        if (type(step) is not int or step < 0 or type(stage) is not int
                or type(p.get("episode")) is not int or p["episode"] < 0
                or type(tr.get("instance_id")) is not int or type(tr.get("generation")) is not int
                or not isinstance(target_state, dict) or target_state.get("valid") is not True
                or target_state.get("status") not in {"tracked", "static_background"}
                or not finite_tensor(p.get("start_eef"), (3,))
                or not torch.is_tensor(points) or points.ndim != 2 or points.shape[1] != 3
                or not points.is_floating_point() or not bool(torch.isfinite(points).all())
                or not 0 <= semantic.target_index < len(points)):
            self.clear("missing_or_invalid_observation_identity", invalid=True)
            return self.scalar()
        ctx = {"episode": p["episode"], "reset_generation": self.generation, "stage": stage,
               "provider": copy.deepcopy(semantic.identity), "target_index": semantic.target_index,
               "tracker_instance": tr["instance_id"], "tracker_generation": tr["generation"],
               "target_status": target_state["status"]}
        self.current = {"identity": ctx, "step": step, "start": p["start_eef"].double().cpu().clone(),
                        "target": points[semantic.target_index].double().cpu().clone()}
        if previous is None:
            return self.scalar()
        if previous["identity"] != ctx:
            self.reason, self.status = "identity_changed", "inactive"
        elif step != previous["start_step"] + 8 or previous["ack_count"] != 8:
            self.reason, self.status = "nonconsecutive_history", "invalid_evidence"
            self.invalid_evidence_count += 1
        elif previous["distance_after_m"] >= previous["distance_before_m"]:
            self.reason, self.status = "no_strict_observed_approach", "inactive"
        else:
            self.previous = previous
            self.active = True
            self.reason, self.status = "strict_observed_approach", "eligible"
        return self.scalar()

    def propose(self, fresh):
        if not self.active:
            return fresh
        if not finite_tensor(fresh, (16, 64, 128)):
            raise RuntimeError("N30 fresh population shape/nonfinite")
        prior = self.previous["native_plan"]
        if not finite_tensor(prior, (1, 64, 128)) or prior.dtype != fresh.dtype or prior.device != fresh.device:
            raise RuntimeError("N30 predecessor native dtype/device/shape mismatch")
        output = fresh.clone()
        output[15] = torch.cat((prior[0, 8:64], fresh[15, 56:64]), dim=0)
        return output

    def select(self, selected):
        self.pending = None
        if self.current is None:
            return None
        if not finite_tensor(selected, (1, 64, 128)):
            self.clear("selected_plan_invalid", invalid=True)
            raise RuntimeError("N30 selected native plan invalid")
        self.pending = {"native_plan": selected.detach().clone(), "native_identity": identity(selected),
                        "identity": copy.deepcopy(self.current["identity"]),
                        "start_step": self.current["step"], "start": self.current["start"],
                        "target": self.current["target"], "ack_count": 0,
                        "actions": None, "committed": False}
        return {"native_identity": self.pending["native_identity"], "start_step": self.pending["start_step"],
                "identity": copy.deepcopy(self.pending["identity"]),
                "start_eef": self.pending["start"], "target_snapshot": self.pending["target"],
                "native_dtype": str(selected.dtype)}

    def bind_decode(self, raw, actions):
        if self.pending is None:
            return
        p = self.pending
        # This proves the forward native->FP32 representation, never an inverse cast.
        if (not finite_tensor(raw, (1, 64, 128)) or raw.dtype != torch.float32
                or identity(raw) != identity(p["native_plan"].float())
                or not finite_tensor(actions, (1, 8, 7))):
            self.clear("decode_binding_mismatch", invalid=True)
            raise RuntimeError("N30 native-to-FP32 decode binding mismatch")
        p["actions"] = actions.detach().cpu().clone()

    def commit(self, actions, horizon, step):
        if self.pending is None:
            return
        p = self.pending
        if horizon != 8:
            self.clear("partial_horizon")
            return
        if (step != p["start_step"] or p["committed"] or p["actions"] is None
                or not finite_tensor(actions, (1, 8, 7)) or identity(actions) != identity(p["actions"])):
            self.clear("commit_binding_mismatch", invalid=True)
            raise RuntimeError("N30 commit binding mismatch")
        p["committed"] = True

    def acknowledge(self, *, global_step, execution_index, action, endpoint, terminated, truncated):
        if terminated or truncated:
            self.clear("terminal_or_truncated", reset=True)
            return None
        p = self.pending
        if p is None:
            if self.completed is not None:
                self.clear("duplicate_after_complete", invalid=True)
            return None
        if (type(global_step) is not int or type(execution_index) is not int
                or not p["committed"] or execution_index != p["ack_count"] + 1
                or global_step != p["start_step"] + p["ack_count"]
                or not finite_tensor(action, (7,))
                or identity(action) != identity(p["actions"][0, p["ack_count"]])):
            self.clear("missing_or_mismatched_action_ack", invalid=True)
            return None
        if not finite_tensor(endpoint, (3,)):
            self.clear("missing_or_nonfinite_actual_eef", invalid=True)
            return None
        p["ack_count"] += 1
        if p["ack_count"] != 8:
            return None
        before = float(torch.linalg.vector_norm(p["start"] - p["target"]).item())
        after = float(torch.linalg.vector_norm(endpoint.detach().double().cpu() - p["target"]).item())
        if not math.isfinite(before) or not math.isfinite(after):
            self.clear("nonfinite_progress_distance", invalid=True)
            return None
        self.completed = {**p, "distance_before_m": before, "distance_after_m": after}
        self.pending = None
        self.reason, self.status = "completed_prefix", "inactive"
        return {"selected_native_identity": p["native_identity"], "ack_count": 8,
                "distance_before_m": before, "distance_after_m": after,
                "progress": before - after, "comparison": "strictly_lower_to_previous_snapshot"}
