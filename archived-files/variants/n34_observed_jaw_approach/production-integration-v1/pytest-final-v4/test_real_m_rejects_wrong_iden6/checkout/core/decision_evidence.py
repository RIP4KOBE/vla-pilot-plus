"""Optional append-only observations, with no decision/outcome read API.

Tensor payloads retain their source dtype. CPU copies and persistence have
measurable overhead (including implicit device-copy synchronization).
"""
from __future__ import annotations

import hashlib
import json
import logging
import marshal
import os
from pathlib import Path
import time
from types import CodeType

import numpy as np
import torch


class DecisionEvidenceIncomplete(RuntimeError):
    pass


def _snapshot(value):
    if torch.is_tensor(value):
        return value.detach().cpu().clone()
    if isinstance(value, np.ndarray):
        return torch.from_numpy(value.copy())
    if isinstance(value, np.generic):
        return _snapshot(np.asarray(value))
    if value is None or type(value) in (str, bool, int, float):
        return value
    if isinstance(value, dict):
        return {str(key): _snapshot(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_snapshot(item) for item in value]
    raise TypeError("unsupported evidence value")


def _fingerprints(cpu_batch):
    """Same canonical bytes as QD; applied only to the observer's CPU copy."""
    return [hashlib.sha256(row.float().contiguous().numpy().astype("<f4", copy=False).tobytes()).hexdigest()
            for row in cpu_batch]


def _provider_identity(fn, ordinal):
    """Hash existing code/loader metadata; never call a provider or reopen source."""
    code = getattr(fn, "__code__", None)
    missing = object()
    original = getattr(fn, "_guidance_original_func", missing)
    origin = "direct_callable" if original is missing else "loader_attached_original"
    original_code = getattr(fn if original is missing else original, "__code__", None)
    if any(value is not None and not isinstance(value, CodeType) for value in (code, original_code)):
        raise TypeError("guidance code metadata must be code or unknown")
    source_text = getattr(fn, "_guidance_source_text", None)
    source_path = getattr(fn, "_guidance_source_path", None)
    if source_text is not None and not isinstance(source_text, str):
        raise TypeError("guidance source text metadata must be text or unknown")
    if source_path is not None and not isinstance(source_path, str):
        raise TypeError("guidance source path metadata must be text or unknown")
    return {"ordinal": ordinal,
            "code_sha256": hashlib.sha256(marshal.dumps(code)).hexdigest() if code is not None else None,
            "original_code_sha256": hashlib.sha256(marshal.dumps(original_code)).hexdigest() if original_code is not None else None,
            "original_identity_origin": origin,
            "source_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest() if source_text is not None else None,
            "source_text_origin": "loader_attached_text" if source_text is not None else "unknown",
            "source_path": source_path}


class DecisionEvidence:
    """One episode, write-only for policy; failures invalidate audit completeness."""

    def __init__(self, output_dir, *, episode):
        self.root = Path(output_dir) / f"episode_{int(episode):03d}"
        self._status_writable = False
        self.episode = int(episode)
        self.decision_id = None
        self.global_step = None
        self.stage = None
        self.reset_sequence = 0
        self.failed = False
        self.finished = False
        self.closed = False
        self.error_type = None
        self.overhead_s = 0.0
        self.bytes_written = 0
        self._sequence = self._bundle = self._decisions = self._committed = 0
        self._pending = []
        self._dispatch_pending = False
        self._outcome_observed = False
        self._provider_ids = {}
        self.scoring_batch_id = None
        self.scoring_candidate_index = None
        self.scoring_provider_index = 0
        self._next_scoring_scope = None
        self.scoring_scope = {"role": "unknown", "iter_idx": None, "site": None}
        self._decision_events = set()
        self._requires_quality = False
        self._projection_origins = []
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if any(self.root.iterdir()):
                raise DecisionEvidenceIncomplete("evidence episode directory already exists")
            self._status_writable = True
            self._write_status()
        except Exception as error:
            self._fail(error)

    def status(self):
        return {"schema": "qd-ed-decision-evidence-v1", "episode": self.episode,
                "complete": self.finished and not self.failed,
                "failed": self.failed, "error_type": self.error_type,
                "decisions": self._decisions, "committed_decisions": self._committed,
                "pending_action": self._dispatch_pending, "bundles": self._bundle,
                "observer_wall_s": self.overhead_s, "bytes_written": self.bytes_written,
                "observer_wall_scope": "snapshot, payload fingerprint, bundle serialization and flush; excludes provider identity, status and scalar bookkeeping",
                "precision": "source tensor dtype; no precision reconstructed",
                "scope": "observed decisions and executed prefixes only"}

    def _write_status(self):
        temporary = self.root / "status.json.tmp"
        temporary.write_text(json.dumps(self.status(), allow_nan=False) + "\n")
        temporary.replace(self.root / "status.json")

    def _fail(self, error):
        self.failed = True
        self.error_type = type(error).__name__
        logging.getLogger(__name__).error("Decision evidence incomplete: %s", self.error_type)
        if self._status_writable:
            try:
                self._write_status()
            except Exception:
                pass  # Missing/initial incomplete status never establishes completeness.

    def record(self, event, **values):
        if self.failed or self.closed:
            return None
        started = time.perf_counter()
        try:
            self._sequence += 1
            item = {"sequence": self._sequence, "event": event, "episode": self.episode,
                    "decision_id": self.decision_id, "global_step": self.global_step,
                    "reset_sequence": self.reset_sequence, "values": _snapshot(values)}
            frozen = item["values"]
            if event in ("scoring_inputs", "provider_return", "scoring_aggregate", "effective_quality"):
                frozen["scoring_scope"] = dict(self.scoring_scope)
            if event == "canonical_candidate_batch":
                frozen["canonical_fingerprints"] = _fingerprints(frozen["candidates"])
                frozen["occurrence_ids"] = [f"{self.decision_id}:q{self._sequence}:r{i}"
                                             for i in range(len(frozen["candidates"]))]
            elif event == "parent_allocation":
                fingerprints = _fingerprints(frozen["source_population"])
                indices = frozen["parent_indices"].tolist()
                frozen["source_pool_id"] = f"{self.decision_id}:q{self._sequence}"
                frozen["source_fingerprints"] = fingerprints
                frozen["parent_fingerprints"] = [fingerprints[i] for i in indices]
                frozen["parent_source_occurrence_ids"] = [f"{frozen['source_pool_id']}:r{i}" for i in indices]
                frozen["source_identity_scope"] = ("actual parent pool after conditional N24 canonical rescue; not an archive membership claim"
                    if frozen.get("gripper_rescue_mode") == "canonical_full_close_v1" else
                    "eligible pool slots, which QD has already allocated; not original archive occurrences")
                frozen["original_archive_occurrences"] = None
            elif event in ("final_selection", "policy_action_decode"):
                frozen["selected_canonical_fingerprint"] = _fingerprints(frozen["selected_latent"])[0]
            self._pending.append(item)
            self._decision_events.add(event)
            if event == "projection_origin":
                self._projection_origins.append(self._sequence)
            return self._sequence
        except Exception as error:
            self._fail(error)
            return None
        finally:
            self.overhead_s += time.perf_counter() - started

    def begin_decision(self, *, global_step, stage, use_guidance, keypoints, providers,
                       keypoint_tracking_snapshot=None):
        if self.failed or self.closed:
            return
        if self._dispatch_pending or self._decisions != self._committed:
            self._fail(DecisionEvidenceIncomplete("unfinished previous decision"))
            return
        previous_stage = self.stage
        previous_decision_id = self.decision_id
        self._decisions += 1
        self.decision_id = f"e{self.episode}:d{self._decisions}:s{int(global_step)}"
        self.global_step, self.stage = int(global_step), int(stage)
        self.scoring_batch_id = self.scoring_candidate_index = None
        self._next_scoring_scope = None
        self.scoring_scope = {"role": "unknown", "iter_idx": None, "site": None}
        self._decision_events = set()
        self._projection_origins = []
        self._requires_quality = bool(use_guidance and providers)
        self._provider_ids = {id(fn): index for index, fn in enumerate(providers or ())}
        try:
            identities = [_provider_identity(fn, index) for index, fn in enumerate(providers or ())]
        except Exception as error:
            self._fail(error)
            return
        self.record("decision_context", stage=self.stage, previous_stage=previous_stage,
                    previous_decision_id=previous_decision_id,
                    stage_changed=previous_stage is not None and previous_stage != self.stage,
                    use_guidance=bool(use_guidance), keypoints=keypoints, providers=identities,
                    target_observation="existing_chunk_keypoint_read",
                    **({"keypoint_tracking_snapshot": keypoint_tracking_snapshot}
                       if keypoint_tracking_snapshot is not None else {}))

    def set_scoring_scope(self, *, role, iter_idx, site):
        """Called at the actual scoring caller, never inferred from equal actions."""
        self._next_scoring_scope = {"role": role, "iter_idx": iter_idx, "site": site}

    def begin_score_call(self):
        self.scoring_scope = self._next_scoring_scope or {"role": "unknown", "iter_idx": None, "site": None}
        self._next_scoring_scope = None
        self.scoring_batch_id = self.scoring_candidate_index = None

    def begin_scoring(self, **values):
        count = int(values["samples"].shape[0])
        values["projection_origin_sequences"] = (
            self._projection_origins[-count:] if len(self._projection_origins) >= count else None)
        self.scoring_batch_id = self.record("scoring_inputs", **values)
        self.scoring_candidate_index = None

    def provider_return(self, fn, value):
        self.record("provider_return", scoring_batch_id=self.scoring_batch_id,
                    candidate_index=self.scoring_candidate_index,
                    provider_ordinal=self.scoring_provider_index,
                    context_provider_ordinal=self._provider_ids.get(id(fn)), result=value)
        self.scoring_provider_index += 1

    def commit_decision(self, *, action_chunk, execution_horizon):
        required = {"policy_action_decode"}
        if self._requires_quality:
            required.update(("scoring_inputs", "provider_return", "effective_quality",
                             "canonical_candidate_batch", "final_selection"))
        if not required <= self._decision_events:
            self._fail(DecisionEvidenceIncomplete("required policy evidence hook missing"))
        self.record("decision_committed", action_chunk=action_chunk,
                    execution_horizon=int(execution_horizon))
        self._committed += 1
        self.flush()

    def dispatch(self, *, global_step, execution_index):
        if self._dispatch_pending:
            self._fail(DecisionEvidenceIncomplete("outcome missing for previous dispatch"))
        self.global_step = int(global_step)
        self._dispatch_pending = True
        self._outcome_observed = False
        self.record("action_dispatch", execution_index=int(execution_index))
        self.flush()  # A native failure leaves an explicit pending dispatch.

    def pre_reset_outcome(self, raw_obs, *, reward, terminated, success):
        # Only fields already exposed to policy; no images or evaluator internals.
        names = ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos", "robot0_gripper_qvel")
        self.record("pre_reset_outcome", observation={k: raw_obs[k] for k in names if k in raw_obs},
                    reward=reward, terminated=bool(terminated), success=bool(success),
                    origin="actual_env_step_before_automatic_reset",
                    contemporaneous_target_pose=None)
        self._outcome_observed = True
        if terminated:
            self.record("automatic_reset_boundary", terminal_episode=self.episode,
                        reset_will_follow=True, reset_completed=None)
            self.flush()  # Persist the old episode before reset can fail natively.
            self.reset_sequence += 1

    def step_returned(self, *, terminated, truncated, success):
        if not self._dispatch_pending or not self._outcome_observed:
            self._fail(DecisionEvidenceIncomplete("pre-reset outcome missing"))
        self.record("step_returned", terminated=bool(terminated), truncated=bool(truncated),
                    success=bool(success))
        self._dispatch_pending = False
        self.flush()

    def flush(self):
        if self.failed or not self._pending:
            return
        started = time.perf_counter()
        try:
            number = self._bundle + 1
            name = f"bundle_{number:06d}.pt"
            temporary = self.root / (name + ".tmp")
            torch.save({"schema": "qd-ed-decision-evidence-v1", "events": self._pending}, temporary)
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            temporary.replace(self.root / name)
            data = (self.root / name).read_bytes()
            entry = {"bundle": name, "sha256": hashlib.sha256(data).hexdigest(),
                     "first_sequence": self._pending[0]["sequence"],
                     "last_sequence": self._pending[-1]["sequence"],
                     "events": [{k: item[k] for k in ("sequence", "event", "decision_id", "global_step", "reset_sequence")}
                                for item in self._pending]}
            with (self.root / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(entry, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            directory_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            self._bundle = number
            self.bytes_written += len(data)
            self._pending.clear()
        except Exception as error:
            self._fail(error)
        finally:
            self.overhead_s += time.perf_counter() - started
        try:
            self._write_status()
        except Exception as error:
            self._fail(error)

    def finish(self):
        """Return audit validity separately; never change the original task outcome."""
        self.flush()
        if self._dispatch_pending or self._decisions != self._committed:
            self._fail(DecisionEvidenceIncomplete("unfinished evidence"))
        if not self.failed:
            self.finished = True
            try:
                self._write_status()
            except Exception as error:
                self._fail(error)
        return self.status()

    def close(self):
        """On an existing execution error, preserve it and leave complete=false."""
        self.flush()
        self.closed = True
        return self.status()
