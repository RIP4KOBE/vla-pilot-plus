"""N31 decision-local canonical cache and one pre-score proposal opportunity.

No observations, projections, providers or random operations are called here.
The pure geometry helper is unchanged; recorded provenance never controls policy.
"""
from __future__ import annotations
import copy
import hashlib
import time
import torch
from core.qd_capture_dwell_proposal import capture_dwell_proposal, _same_native_bytes
from core.qd_ed import fingerprint_action

MODE = "capture_dwell_proposal_v1"
OFF = "off"


def native_id(x):
    x = x.detach().cpu().contiguous()
    return hashlib.sha256(str((str(x.dtype), tuple(x.shape))).encode()
                          + x.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def vector(value, n, name):
    if value is None:
        return None
    x = torch.as_tensor(value).detach().cpu()
    if tuple(x.shape) not in {(n,), (1, n)} or not x.is_floating_point() or not bool(torch.isfinite(x).all()):
        raise ValueError(f"N31 malformed {name}")
    return x.reshape(n).clone()


def capture_context(observation, keypoints, tracking, episode):
    """Main's existing cached raw packet, no adapter/tracker calls."""
    robot = observation.get("observation.robot_state", {}) if isinstance(observation, dict) else {}
    if not isinstance(robot, dict):
        raise ValueError("N31 malformed robot observation")
    eef, grip = robot.get("eef", {}), robot.get("gripper", {})
    if not isinstance(eef, dict) or not isinstance(grip, dict):
        raise ValueError("N31 malformed proprioception mapping")
    points = None if keypoints is None else torch.as_tensor(keypoints).detach().cpu().clone()
    if points is not None and (points.ndim != 2 or points.shape[1] != 3 or not points.is_floating_point()
                               or not bool(torch.isfinite(points).all())):
        raise ValueError("N31 malformed keypoints")
    return {"episode": episode, "tracker": copy.deepcopy(tracking), "keypoints": points,
            "observed_eef": vector(eef.get("pos"), 3, "EEF"),
            "hand_quaternion_xyzw": vector(eef.get("quat"), 4, "quaternion"),
            "gripper_qpos": vector(grip.get("qpos"), 2, "qpos")}


def validate_config(cfg, horizon):
    mode = cfg.capture_dwell_proposal_mode
    if mode == OFF:
        return
    if mode != MODE or horizon != 8:
        raise ValueError("N31 requires explicit capture-dwell mode and horizon8")
    expected = {"population_size": 16, "cem_iters": 10, "use_cem": False,
        "reward_mode": "normal", "qd_archive_mode": "grid_archive", "qd_parent_sampling": "sparse_priority",
        "qd_quality_mode": "provider", "qd_descriptor": "target_relative_endpoint_xy",
        "qd_final_selection_mode": "archive_global_best", "qd_parent_survivor_count": 0,
        "qd_global_quality_anchor_count": 0, "qd_secondary_lane_mode": "none",
        "qd_gripper_rescue_mode": "none", "qd_degenerate_fallback_policy": "none",
        "chunk_population_mode": "fresh", "chunk_memory_fraction": 0., "elite_carryover_count": 0,
        "executed_progress_continuation_mode": "off", "executed_progress_continuation_control": "none",
        "diversity_update_mode": "legacy_additive", "diversity_input_source": "noisy_sample",
        "rollout_diversity_placement": "model_output",
        "initial_diversity_descriptor_mode": "absolute_eef", "rollout_diversity_descriptor_mode": "absolute_eef",
        "rollout_diversity_control_mode": "fixed", "search_schedule_mode": "legacy_linear",
        "qd_grid_shape": (4, 4), "qd_cell_capacity": 1, "qd_bounds_quantiles": (0.05, 0.95),
        "qd_bounds_expand_fraction": 0.10, "qd_min_axis_span_m": 0.08,
        "qd_bounds_update_policy": "fixed_initial", "use_initial_cache": False, "save_ed_cache": False, "save_initial_cache": False}
    for k, v in expected.items():
        if getattr(cfg, k, None) != v:
            raise ValueError(f"N31 requires {k}={v!r}")


class CaptureDwellDecision:
    """At most 176 canonical occurrences, ten opportunities, one decision."""
    def __init__(self, semantic, packet, keypoints, *, episode, stage, step, action_mask):
        if any(type(v) is not int or v < 0 for v in (episode, stage, step)):
            raise ValueError("N31 decision identity malformed")
        self.started = time.perf_counter()
        self.overhead_seconds = 0.
        self.entries = []
        self.scope = None
        self.pending = None
        self.opportunities = []
        self.batches = 0
        self.closed = False
        self.semantic = semantic
        self.packet = copy.deepcopy(packet) if packet is not None else None
        self.keypoints = None if keypoints is None else keypoints.detach().clone()
        self.identity = {"episode": episode, "stage": stage, "step": step,
                         "provider": None if semantic is None else copy.deepcopy(semantic.identity)}
        self.reason = None
        if tuple(action_mask.shape) != (1, 1, 128) or action_mask.dtype not in (torch.float32, torch.bfloat16):
            raise ValueError("N31 mask shape/dtype")
        expected = torch.zeros_like(action_mask)
        expected[:, :, [10, 39, 40, 41, 42, 43, 44]] = 1
        if not _same_native_bytes(action_mask, expected):
            raise ValueError("N31 active action mask differs")
        self.mask = action_mask.detach().clone()
        if self.packet is not None:
            if (not isinstance(self.packet, dict) or type(self.packet.get("episode")) is not int
                    or self.packet["episode"] != episode):
                raise ValueError("N31 observation episode identity")
            for name, n in (("observed_eef", 3), ("hand_quaternion_xyzw", 4), ("gripper_qpos", 2)):
                self.packet[name] = vector(self.packet.get(name), n, name)
            points = self.packet.get("keypoints")
            if points is not None and (not torch.is_tensor(points) or points.ndim != 2 or points.shape[1] != 3
                    or not points.is_floating_point() or not bool(torch.isfinite(points).all())):
                raise ValueError("N31 observation target malformed")
        if semantic is None:
            self.reason = "unrecognized_target"
        elif packet is None:
            self.reason = "observation_context_unavailable"
        else:
            self._bind_packet(self.packet, semantic, keypoints, episode)
        self.overhead_seconds += time.perf_counter() - self.started

    def _bind_packet(self, p, semantic, keypoints, episode):
        if not isinstance(p, dict) or type(p.get("episode")) is not int or p["episode"] != episode:
            raise ValueError("N31 observation episode identity")
        for name, n in (("observed_eef", 3), ("hand_quaternion_xyzw", 4), ("gripper_qpos", 2)):
            p[name] = vector(p.get(name), n, name)
        points = p.get("keypoints")
        if points is None:
            self.reason = "target_unavailable"
            return
        if (not torch.is_tensor(points) or points.ndim != 2 or points.shape[1] != 3
                or not points.is_floating_point() or not bool(torch.isfinite(points).all())
                or not 0 <= semantic.target_index < len(points)):
            raise ValueError("N31 observation target malformed")
        if keypoints is None or not _same_native_bytes(points.to(keypoints), keypoints):
            raise ValueError("N31 raw target/policy keypoints contradictory")
        tr = p.get("tracker")
        if tr is None:
            self.reason = "tracking_unavailable"
            return
        if (not isinstance(tr, dict) or type(tr.get("instance_id")) is not int
                or type(tr.get("generation")) is not int or not isinstance(tr.get("targets"), dict)):
            raise ValueError("N31 tracker malformed")
        state = tr["targets"].get(str(semantic.target_index))
        if state is not None and not isinstance(state, dict):
            raise ValueError("N31 tracker target malformed")
        if state is None or state.get("valid") is not True or state.get("status") not in {"tracked", "static_background"}:
            self.reason = "tracking_unavailable"
            return
        self.identity.update(target_index=semantic.target_index, tracker_instance=tr["instance_id"],
                             tracker_generation=tr["generation"], target_status=state["status"])
        self.target = points[semantic.target_index].detach().cpu().clone()

    def set_scope(self, role, iteration, site):
        if self.closed:
            raise RuntimeError("N31 closed decision")
        self.scope = (role, iteration, site)

    def canonical(self):
        return self.scope is not None and self.scope[0] in {"canonical_initial", "canonical_offspring"}

    def validate(self, keypoints, providers):
        if self.closed:
            raise RuntimeError("N31 closed decision")
        if self.semantic is not None:
            self.semantic.validate(providers)
        if ((self.keypoints is None) != (keypoints is None)
                or (keypoints is not None and not _same_native_bytes(self.keypoints, keypoints))):
            raise ValueError("N31 target changed within decision")

    def record_score(self, samples, projection, rewards, costs, evidence, *, projection_unavailable=False):
        start = time.perf_counter()
        if not self.canonical():
            return
        role, iteration, site = self.scope
        wanted = -1 if self.batches == 0 else self.batches - 1
        if iteration != wanted or role != ("canonical_initial" if wanted == -1 else "canonical_offspring"):
            raise RuntimeError("N31 canonical order/duplicate scoring")
        if self.batches >= 11 or tuple(samples.shape) != (16, 64, 128):
            raise RuntimeError("N31 canonical bound")
        xyz = None if projection is None else projection.get("projected_xyz")
        origins = None if projection is None else projection.get("source_origins")
        if xyz is None:
            if not projection_unavailable or self.semantic is not None or origins is not None:
                raise RuntimeError("N31 missing canonical projection")
            # Original _score_particles returns zeros before any projection when
            # there is no provider/target. Retain Unknown; never synthesize one.
        elif (projection_unavailable or tuple(xyz.shape) != (16, 9, 3)
                or xyz.dtype != samples.dtype or origins is None or len(origins) != 16):
            raise ValueError("N31 canonical projection shape/dtype")
        if (tuple(rewards.shape) != (16,) or rewards.dtype != samples.dtype
                or not torch.isfinite(samples).all() or (xyz is not None and not torch.isfinite(xyz).all())
                or not torch.isfinite(rewards).all() or not _same_native_bytes(costs, -rewards)):
            raise ValueError("N31 canonical native association")
        ids = []
        for row in range(16):
            origin = None if origins is None else vector(origins[row], 3, "source origin")
            if xyz is not None and (origin is None or not _same_native_bytes(origin.to(xyz), xyz[row, 0])):
                raise ValueError("N31 source/cast projection origin")
            entry = {"iteration": iteration, "row": row, "occurrence": len(self.entries),
                "plan": samples[row].detach().clone(), "projection": None if xyz is None else xyz[row, 1:9].detach().clone(),
                "source_origin": origin, "cast_origin": None if xyz is None else xyz[row, 0].detach().clone(),
                "projection_status": "Unknown_original_score_short_circuit" if xyz is None else "original_canonical",
                "quality": rewards[row].detach().clone(), "cost": costs[row].detach().clone(),
                "fingerprint": fingerprint_action(samples[row]), "native_identity": native_id(samples[row]),
                "scoring_batch_id": None if evidence is None else evidence.scoring_batch_id}
            self.entries.append(entry)
            ids.append(entry["native_identity"])
        self.batches += 1
        if self.pending is not None:
            raise RuntimeError("N31 pending proposal not consumed before scoring")
        if evidence is not None:
            evidence.record("n31_canonical_cache", identity=self.identity, role=role, iter_idx=iteration,
                            site=site, scoring_batch_id=evidence.scoring_batch_id,
                            action_mask=self.mask,
                            native_identities=ids, occurrence_start=len(self.entries)-16,
                            source_origins=origins, cast_origins=None if xyz is None else xyz[:, 0],
                            projected_outcomes=None if xyz is None else xyz[:, 1:9],
                            projection_status="Unknown_original_score_short_circuit" if xyz is None else "original_canonical")
        self.overhead_seconds += time.perf_counter() - start

    def prepare(self, archive, iteration, providers, keypoints, evidence):
        start = time.perf_counter()
        self.validate(keypoints, providers)
        if self.pending is not None or iteration != len(self.opportunities) or self.batches != iteration + 1:
            raise RuntimeError("N31 opportunity order")
        cell, best = archive.select_global_best()
        matches = [x for x in self.entries if x["iteration"] == best.source_iter
                   and x["fingerprint"] == best.fingerprint
                   and _same_native_bytes(x["plan"], best.action)]
        if not matches:
            raise RuntimeError("N31 archive source absent from canonical cache")
        first = matches[0]
        for m in matches:
            if (float(m["quality"]) != best.reward or float(m["cost"]) != best.cost
                    or any((first[k] is None) != (m[k] is None)
                           or (first[k] is not None and not _same_native_bytes(first[k], m[k])) for k in
                           ("projection", "quality", "cost", "source_origin", "cast_origin"))):
                raise RuntimeError("N31 contradictory duplicate canonical provenance")
        record = {"iteration": iteration, "identity": copy.deepcopy(self.identity),
                  "archive": {"cell": cell, "source_iter": best.source_iter,
                    "insert_sequence": best.insert_sequence, "fingerprint": best.fingerprint,
                    "native_identity": first["native_identity"]},
                  "matching_occurrences": [m["occurrence"] for m in matches],
                  "association": "unique_occurrence" if len(matches) == 1 else "identical_content_multiple_occurrences",
                  "source": first, "slot": 15}
        if self.reason:
            candidate, arrival, reason = None, None, self.reason
        else:
            result = capture_dwell_proposal(first["plan"], first["projection"], target=self.target,
                hand_quaternion_xyzw=self.packet["hand_quaternion_xyzw"],
                gripper_qpos=self.packet["gripper_qpos"], target_recognized=True)
            candidate, arrival, reason = result.candidate, result.arrival_index, result.reason
        record.update(candidate=candidate, arrival_index=arrival, reason=reason)
        self.pending = record
        self.overhead_seconds += time.perf_counter() - start

    def apply(self, population, evidence):
        start = time.perf_counter()
        record = self.pending
        if record is None:
            raise RuntimeError("N31 rollout lacks prepared opportunity or double insertion")
        if tuple(population.shape) != (16, 64, 128) or population.dtype != self.mask.dtype:
            raise ValueError("N31 rollout native shape/dtype")
        candidate = record["candidate"]
        before = population[15].detach().clone()
        # Passive commitment taken before substitution; absent with recorder off.
        ordinary_other15 = None if evidence is None else {
            "dtype": str(population.dtype), "shape": [15, 64, 128],
            "native_identity": native_id(population[:15])}
        if candidate is not None:
            if candidate.dtype != population.dtype or candidate.device != population.device:
                raise ValueError("N31 replacement dtype/device")
            if not _same_native_bytes(candidate * self.mask[0], candidate):
                # Active/inactive numerical validity is strict; signed inactive zeros
                # are retained by the existing native mask and never rewritten here.
                raise ValueError("N31 proposal violates active mask")
            population = population.clone()
            population[15] = candidate
        summary = {k: v for k, v in record.items() if k not in {"candidate", "source"}}
        summary["changed"] = candidate is not None
        self.opportunities.append(summary)
        self.pending = None
        if evidence is not None:
            evidence.record("n31_capture_dwell_opportunity", **record, original_post_rollout_slot15=before,
                            actual_scored_population=population, observation=self.packet,
                            ordinary_other15=ordinary_other15)
        self.overhead_seconds += time.perf_counter() - start
        return population

    def close(self):
        if self.pending is not None or self.batches != 11 or len(self.opportunities) != 10:
            raise RuntimeError("N31 incomplete decision cache")
        summary = {"schema": "n31-capture-dwell-scalar-v1", "mode": MODE,
            "canonical_batches": self.batches, "canonical_occurrences": len(self.entries),
            "opportunities": len(self.opportunities),
            "changed": sum(x["changed"] for x in self.opportunities),
            "reasons": [x["reason"] for x in self.opportunities],
            "overhead_seconds": self.overhead_seconds,
            "overhead_scope": "decision_init_record_prepare_apply_including_observer",
            "overhead_excludes": ["Main_packet", "provider_recognition", "score_validate",
                                  "adapter_capture_origin_copy", "archive_snapshot_observer", "whole_selection"]}
        self.entries.clear()
        self.closed = True
        return summary

