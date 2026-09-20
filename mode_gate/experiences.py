"""Episode facts, revisioned Planner interpretations and real execution media.

Facts never become labels merely because a controller chose EXPANSION.
Images/videos are evidence references, not model input retroactively added to a decision.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import fcntl
import os
from pathlib import Path
from uuid import uuid4
import numpy as np
from .io_utils import AtomicJsonl, atomic_write_json, sha256_file
from .experiment_contract import FIXED_BUDGET_50_LABEL_VERSION


def artifact_ref(path, *, kind, **metadata):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path), "sha256": sha256_file(path), "kind": kind, **metadata}


class ExperienceLibrary:
    def __init__(self, root):
        self.root = Path(root)
        self.facts = AtomicJsonl(self.root / "episode_facts.jsonl")
        self.interpretations = AtomicJsonl(self.root / "planner_interpretations.jsonl")
        self.training_usage = AtomicJsonl(self.root / "training_usage.jsonl")
        self.training_requests = AtomicJsonl(self.root / "planner_retrain_requests.jsonl")
        self.media = AtomicJsonl(self.root / "episode_media.jsonl")
        self._writers = {}

    def record_fact(self, *, episode_id, context_id, kind, payload, event_id=None):
        value = {"schema_version": "experience-fact-v3", "event_id": event_id or uuid4().hex,
                 "episode_id": str(episode_id), "context_id": str(context_id),
                 "kind": str(kind), "payload": payload,
                 "recorded_at": datetime.now(timezone.utc).isoformat()}
        if event_id is not None:
            self.facts.append(value)
        else:
            # UUID events need no full-history dedup scan on every physical step.
            # Keep the append lock and durability barrier, reject a torn tail.
            encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode()
            with self.facts.lock_path.open("a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                with self.facts.path.open("a+b") as stream:
                    stream.seek(0, os.SEEK_END)
                    if stream.tell():
                        stream.seek(-1, os.SEEK_END)
                        if stream.read(1) != b"\n":
                            raise ValueError("torn experience-log tail requires recovery, cannot append")
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
        return value

    def episode(self, episode_id):
        return {"episode_id": episode_id,
                "facts": [x for x in self.facts.iter_valid() if x["episode_id"] == episode_id],
                "media": [x for x in self.media.iter_valid() if x["episode_id"] == episode_id],
                "interpretations": [x for x in self.interpretations.iter_valid()
                                    if x.get("episode_id") == episode_id]}

    def annotate(self, value, *, known_decisions):
        """Append a revision. Validate citations, not a fixed allowed data-source list."""
        value = dict(value)
        decision = known_decisions.get(value.get("record_id"))
        if decision is None:
            raise KeyError("Planner annotation must identify an actual decision")
        if value.get("label_version") != FIXED_BUDGET_50_LABEL_VERSION:
            raise ValueError("new annotations require fixed_budget_50-v2")
        recorded_episode = decision.get("provenance", {}).get("episode_id")
        if recorded_episode and value.get("episode_id") != recorded_episode:
            raise ValueError("Planner cannot reassign the recorded episode identity")
        if value.get("label") not in {"RE-STEER", "EXPANSION", "AMBIGUOUS/CENSORED", None}:
            raise ValueError("invalid Planner label")
        if not value.get("reason") or not value.get("planner_provenance"):
            raise ValueError("Planner interpretation requires reasoning and account provenance")
        if value["planner_provenance"].get("planner_thread_id") != "01a0893c-15b0-7203-881c-de3c5bcee058":
            raise ValueError("interpretations must come from the configured top-level Planner")
        refs = value.get("evidence_refs", [])
        facts = {x["event_id"]: x for x in self.facts.iter_valid()}
        has_independent_evidence = False
        for ref in refs:
            if ref.get("event_id"):
                fact = facts.get(ref["event_id"])
                if fact is None:
                    raise ValueError("unknown factual evidence citation")
                # A route prediction is not an observed outcome. Other factual records,
                # including failures/partial executions, can support a Planner hypothesis.
                if fact["kind"] != "decision_context":
                    p = fact["payload"]
                    route_only = (fact["kind"] == "retry_outcome" and p.get("censored")
                                  and not p.get("native_success"))
                    has_independent_evidence |= not route_only
            elif ref.get("path"):
                path = Path(ref["path"])
                if not path.is_file() or sha256_file(path) != ref.get("sha256"):
                    raise ValueError("missing or changed Planner evidence artifact")
                has_independent_evidence |= ref.get("kind") not in {"prediction", "decision", "predicted_candidates"}
            else:
                raise ValueError("evidence reference must identify a fact or hashed artifact")
        if value.get("use_for_training"):
            if value.get("label") not in {"RE-STEER", "EXPANSION"}:
                raise ValueError("ambiguous/censored interpretations are not binary training labels")
            if not refs or not has_independent_evidence:
                raise ValueError("a verifier prediction/early EXPANSION alone is not supervision")
            if decision.get("feature_schema") != "candidate-verifier-input-v3":
                raise ValueError("regenerate decision-time full-candidate inputs before training old experiences")
        previous = self.latest_annotations().get(value["record_id"])
        if value.get("supersedes") != (previous or {}).get("annotation_id"):
            raise ValueError("annotation revision must explicitly supersede the latest revision")
        value.update(schema_version="planner-interpretation-v3", annotation_id=uuid4().hex,
                     policy_id=decision["policy_id"], snapshot_hash=decision["snapshot_hash"],
                     labeled_at=datetime.now(timezone.utc).isoformat())
        value["event_id"] = value["annotation_id"]
        self.interpretations.append(value)
        return value

    def latest_annotations(self):
        result = {}
        for row in self.interpretations.iter_valid():
            result[row["record_id"]] = row
        return result

    def request_training(self, *, train_annotation_ids, independent_annotation_ids,
                         reason, planner_provenance, config=None):
        latest = {x["annotation_id"]: x for x in self.latest_annotations().values()}
        train, check = list(train_annotation_ids), list(independent_annotation_ids)
        if not train or len(train) != len(set(train)) or len(check) != len(set(check)):
            raise ValueError("training selection must be nonempty and unique")
        if set(train) & set(check):
            raise ValueError("training and independent experience selections overlap")
        for identity in train + check:
            if identity not in latest or not latest[identity].get("use_for_training"):
                raise ValueError("training selection names a withdrawn/unknown annotation")
        value = {"schema_version": "planner-retrain-request-v3", "event_id": uuid4().hex,
                 "train_annotation_ids": train, "independent_annotation_ids": check,
                 "reason": reason, "planner_provenance": planner_provenance,
                 "config": dict(config or {}), "recorded_at": datetime.now(timezone.utc).isoformat()}
        self.training_requests.append(value)
        return value

    def record_video_frame(self, episode_id, images, *, context_id, step):
        """Finite per-context segments survive later crashes; both cameras are retained."""
        import imageio.v2 as imageio
        from PIL import Image
        key = str(episode_id)
        state = self._writers.get(key)
        if state and state["context_id"] != context_id:
            self._close_segment(key)
            state = None
        frames = []
        for name, image in images.items():
            array = np.asarray(image)
            if array.dtype != np.uint8:
                array = np.clip(array * 255 if array.max() <= 1 else array, 0, 255).astype(np.uint8)
            frames.append((str(name), array[..., :3]))
        if not frames:
            return
        if state is None:
            folder = self.root / "videos" / hashlib.sha256(key.encode()).hexdigest()[:20]
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"segment_{step:06d}.mp4"
            initial = []
            for i, (camera, frame) in enumerate(frames):
                still = folder / f"frame_{step:06d}_camera_{i}.png"
                Image.fromarray(frame).save(still)
                initial.append(artifact_ref(still, kind="real_observation", camera=camera, step=step))
            state = {"writer": imageio.get_writer(path, fps=20, codec="libx264", macro_block_size=2),
                     "path": path, "episode_id": key, "context_id": context_id,
                     "start_step": step, "end_step": step, "initial_images": initial,
                     "cameras": [x[0] for x in frames]}
            self._writers[key] = state
        height = max(x[1].shape[0] for x in frames)
        joined = [np.asarray(Image.fromarray(x).resize((round(x.shape[1] * height / x.shape[0]), height)))
                  for _, x in frames]
        state["writer"].append_data(np.concatenate(joined, axis=1))
        state["end_step"] = step
        state["last_frames"] = frames

    def _close_segment(self, episode_id):
        from PIL import Image
        state = self._writers.pop(str(episode_id), None)
        if state is None:
            return
        state["writer"].close()
        final = []
        for i, (camera, frame) in enumerate(state["last_frames"]):
            path = state["path"].with_name(f"frame_{state['end_step']:06d}_end_{i}.png")
            Image.fromarray(frame).save(path)
            final.append(artifact_ref(path, kind="real_observation", camera=camera, step=state["end_step"]))
        value = {k: v for k, v in state.items() if k not in {"writer", "path", "last_frames"}}
        value.update(event_id=uuid4().hex, video=artifact_ref(state["path"], kind="executed_video"),
                     final_images=final, schema_version="episode-video-segment-v3")
        self.media.append(value)
        return value

    def finish_video(self, episode_id, *, finalize=False):
        self._close_segment(episode_id)
        segments = [x for x in self.media.iter_valid() if x["episode_id"] == str(episode_id)]
        if not segments:
            return None
        folder = Path(segments[0]["video"]["path"]).parent
        manifest = folder / f"episode_video_through_{segments[-1]['end_step']:06d}.json"
        full_video = None
        if finalize:
            import subprocess
            import imageio_ffmpeg
            output = folder / f"full_episode_through_{segments[-1]['end_step']:06d}.mp4"
            final_manifest = manifest.with_name(manifest.stem + "_complete.json")
            if final_manifest.is_file():
                return final_manifest
            # Segment names are generated locally, never supplied by Planner.
            concat = folder / f"concat_{segments[-1]['end_step']:06d}.txt"
            concat.write_text("".join("file '" + Path(x["video"]["path"]).name + "'\n" for x in segments))
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-hide_banner","-loglevel","error",
                "-y","-f","concat","-safe","1","-i",str(concat),"-c","copy",str(output)],
                check=True, capture_output=True)
            full_video = artifact_ref(output, kind="executed_video")
            manifest = final_manifest
        # Lossless complete episode entry point; clips reference these same original segments.
        atomic_write_json(manifest, {"schema_version": "complete-episode-video-v3",
                                    "episode_id": episode_id, "segments": segments,
                                    "full_video":full_video,
                                    "coverage": "all recorded execution frames in chronological order"})
        if finalize:
            self.record_fact(episode_id=episode_id, context_id="", kind="complete_episode_video",
                payload={"video":full_video,"manifest":artifact_ref(manifest,kind="complete_episode_video")},
                event_id="episode-video:"+str(episode_id)+":"+str(segments[-1]["end_step"]))
        return manifest
