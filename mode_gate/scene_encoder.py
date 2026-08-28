"""Immutable theta-0 scene/signature feature extraction and fp16 caching."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import numpy as np

from .io_utils import sha256_file


@dataclass(frozen=True)
class MaskedHiddenStates:
    hidden: np.ndarray
    attention_mask: np.ndarray

    def __post_init__(self) -> None:
        hidden = np.asarray(self.hidden, dtype=np.float32)
        mask = np.asarray(self.attention_mask, dtype=bool)
        if hidden.ndim != 2 or hidden.shape[1] != 2048:
            raise ValueError("prefix hidden states must have shape (T, 2048)")
        if mask.shape != (hidden.shape[0],) or not np.any(mask):
            raise ValueError("attention mask must select at least one prefix token")
        if not np.isfinite(hidden).all():
            raise ValueError("prefix hidden states contain non-finite values")
        object.__setattr__(self, "hidden", hidden)
        object.__setattr__(self, "attention_mask", mask)


class PrefixFeatureSource(Protocol):
    def encode_joint(self, image: np.ndarray, instruction: str) -> MaskedHiddenStates: ...

    def encode_goal(self, instruction: str) -> MaskedHiddenStates: ...

    def encode_observation(self, image: np.ndarray) -> MaskedHiddenStates: ...


@dataclass(frozen=True)
class SceneSignatureFeatures:
    joint_feature: np.ndarray
    e_goal: np.ndarray
    e_obs: np.ndarray
    feature_id: str
    cache_path: Path | None
    metadata: dict[str, Any]


class Theta0SceneEncoder:
    """Read-only encoder whose cache key binds every relevant theta-0 input."""

    def __init__(
        self,
        source: PrefixFeatureSource,
        *,
        theta0_checksum: str,
        processor_hash: str,
        hook_name: str = "final_prefix_hidden_states",
        cache_dir: Path | None = None,
    ) -> None:
        if len(theta0_checksum) < 16 or len(processor_hash) < 16:
            raise ValueError("theta0 and processor hashes are required")
        self.source = source
        self.theta0_checksum = theta0_checksum
        self.processor_hash = processor_hash
        self.hook_name = hook_name
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def encode(self, image: np.ndarray, instruction: str) -> SceneSignatureFeatures:
        image = np.asarray(image)
        if image.ndim != 3 or image.shape[2] not in (3, 4):
            raise ValueError("image must have shape (H, W, 3|4)")
        source_fingerprint = getattr(self.source, "input_fingerprint", None)
        if callable(source_fingerprint):
            # PI0.5 consumes both agent-view and wrist images from the adapter.
            # Hash the exact pinned-processor batches rather than only the RGB
            # used for the Gemini overlay, otherwise two different robot states
            # could alias the same cached theta-0 feature.
            input_hash = str(source_fingerprint(image, instruction))
            if len(input_hash) != 64:
                raise ValueError("source input fingerprint must be a SHA256 digest")
        else:
            input_hash = hashlib.sha256(
                b"\0".join(
                    [
                        image.tobytes(),
                        str(image.dtype).encode(),
                        instruction.encode("utf-8"),
                    ]
                )
            ).hexdigest()
        feature_id = hashlib.sha256(
            b"\0".join(
                [
                    self.theta0_checksum.encode(),
                    self.processor_hash.encode(),
                    self.hook_name.encode(),
                    input_hash.encode(),
                ]
            )
        ).hexdigest()
        cached = self._load(feature_id)
        if cached is not None:
            return cached

        joint = _masked_mean(self.source.encode_joint(image, instruction))
        goal = _l2_normalize(_masked_mean(self.source.encode_goal(instruction)))
        observation = _l2_normalize(
            _masked_mean(self.source.encode_observation(image))
        )
        metadata = {
            "schema_version": "theta0-scene-signature-v1",
            "theta0_checksum": self.theta0_checksum,
            "processor_hash": self.processor_hash,
            "hook_name": self.hook_name,
            "hidden_size": 2048,
            "input_hash": input_hash,
        }
        path = self._save(feature_id, joint, goal, observation, metadata)
        if path is not None:
            # The persisted representation is fp16 by contract.  Return that
            # same quantized value on a cache miss so cache hits cannot change
            # verifier/signature inputs within a run.
            joint = joint.astype(np.float16).astype(np.float32)
            goal = goal.astype(np.float16).astype(np.float32)
            observation = observation.astype(np.float16).astype(np.float32)
        return SceneSignatureFeatures(
            joint_feature=joint,
            e_goal=goal,
            e_obs=observation,
            feature_id=feature_id,
            cache_path=path,
            metadata=metadata,
        )

    def _load(self, feature_id: str) -> SceneSignatureFeatures | None:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / f"{feature_id}.npz"
        metadata_path = self.cache_dir / f"{feature_id}.json"
        if not path.exists() or not metadata_path.exists():
            return None
        try:
            with np.load(path, allow_pickle=False) as data:
                joint = data["joint"].astype(np.float32)
                goal = data["goal"].astype(np.float32)
                observation = data["observation"].astype(np.float32)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return None
        if any(value.shape != (2048,) for value in (joint, goal, observation)):
            return None
        return SceneSignatureFeatures(
            joint_feature=joint,
            e_goal=goal,
            e_obs=observation,
            feature_id=feature_id,
            cache_path=path,
            metadata=metadata,
        )

    def _save(
        self,
        feature_id: str,
        joint: np.ndarray,
        goal: np.ndarray,
        observation: np.ndarray,
        metadata: dict[str, Any],
    ) -> Path | None:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / f"{feature_id}.npz"
        temporary = self.cache_dir / f".{feature_id}.{os.getpid()}.npz.tmp"
        with temporary.open("wb") as stream:
            np.savez_compressed(
                stream,
                joint=joint.astype(np.float16),
                goal=goal.astype(np.float16),
                observation=observation.astype(np.float16),
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        metadata_path = self.cache_dir / f"{feature_id}.json"
        metadata_tmp = self.cache_dir / f".{feature_id}.{os.getpid()}.json.tmp"
        metadata_tmp.write_text(
            json.dumps(metadata, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        os.replace(metadata_tmp, metadata_path)
        return path


class Pi05PrefixFeatureSource:
    """Adapter for a frozen PI0.5 model and a caller-supplied batch factory.

    The batch factory owns theta-0 preprocessing and must return the exact
    pinned processor output for ``joint``, ``goal`` or ``observation``.  This
    keeps active-policy processors from leaking into signature features.
    """

    def __init__(self, policy: Any, batch_factory: Any) -> None:
        self.policy = policy
        self.batch_factory = batch_factory
        self.policy.eval()
        for parameter in self.policy.parameters():
            parameter.requires_grad_(False)
        self._prepared_batches: dict[str, dict[str, Any]] = {}

    def input_fingerprint(self, image: np.ndarray, instruction: str) -> str:
        """Prepare and hash the exact three theta-0 processor batches.

        The prepared values are consumed by the subsequent encode calls, so
        the cache key and hidden states are guaranteed to describe the same
        adapter observation even if a caller mutates simulator state later.
        """

        batches = {
            "joint": self.batch_factory("joint", image, instruction),
            "goal": self.batch_factory("goal", None, instruction),
            "observation": self.batch_factory("observation", image, ""),
        }
        digest = hashlib.sha256()
        _update_digest(digest, batches)
        self._prepared_batches = batches
        return digest.hexdigest()

    def _batch(self, kind: str, image: np.ndarray | None, instruction: str) -> dict[str, Any]:
        batch = self._prepared_batches.pop(kind, None)
        if batch is None:
            return self.batch_factory(kind, image, instruction)
        if not self._prepared_batches:
            self._prepared_batches = {}
        return batch

    def encode_joint(self, image: np.ndarray, instruction: str) -> MaskedHiddenStates:
        return self._encode(
            self._batch("joint", image, instruction), selection="joint"
        )

    def encode_goal(self, instruction: str) -> MaskedHiddenStates:
        return self._encode(
            self._batch("goal", None, instruction), selection="goal"
        )

    def encode_observation(self, image: np.ndarray) -> MaskedHiddenStates:
        return self._encode(
            self._batch("observation", image, ""), selection="observation"
        )

    def _encode(
        self, batch: dict[str, Any], *, selection: str
    ) -> MaskedHiddenStates:
        import torch
        from lerobot.utils.constants import (
            OBS_LANGUAGE_ATTENTION_MASK,
            OBS_LANGUAGE_TOKENS,
        )

        with torch.inference_mode(), torch.autocast(
            device_type="cuda", dtype=torch.bfloat16
        ):
            images, image_masks = self.policy._preprocess_images(batch)
            tokens = batch[OBS_LANGUAGE_TOKENS]
            masks = batch[OBS_LANGUAGE_ATTENTION_MASK]
            prefix_embs, prefix_pad_masks, prefix_att_masks = self.policy.model.embed_prefix(
                images, image_masks, tokens, masks
            )
            from lerobot.policies.pi05.modeling_pi05 import make_att_2d_masks

            attention_2d = make_att_2d_masks(prefix_pad_masks, prefix_att_masks)
            positions = torch.cumsum(prefix_pad_masks, dim=1) - 1
            attention_4d = self.policy.model._prepare_attention_masks_4d(attention_2d)
            output, _ = self.policy.model.paligemma_with_expert.forward(
                attention_mask=attention_4d,
                position_ids=positions,
                past_key_values=None,
                inputs_embeds=[prefix_embs, None],
                use_cache=False,
            )
        # The pinned LeRobot PI0.5 port returns
        # ``[final_prefix_hidden, final_suffix_hidden]`` directly.  This is the
        # post-final-norm representation used by the policy's KV-cache path.
        hidden = output[0] if isinstance(output, (tuple, list)) else None
        if hidden is None:
            hidden = _extract_last_hidden(output)
        text_tokens = int(masks.shape[1])
        selected_mask = prefix_pad_masks.detach().clone().bool()
        if selection == "goal":
            selected_mask[:, :-text_tokens] = False
            selected_mask[:, -text_tokens:] &= masks.bool()
        elif selection == "observation":
            selected_mask[:, -text_tokens:] = False
        elif selection != "joint":
            raise ValueError(f"unknown prefix feature selection {selection!r}")
        return MaskedHiddenStates(
            hidden=hidden[0].detach().float().cpu().numpy(),
            attention_mask=selected_mask[0].cpu().numpy(),
        )


def processor_artifact_digest(
    checkpoint_root: Path,
    *,
    tokenizer_root: Path | None = None,
) -> str:
    """Hash every pinned theta-0 processor and local tokenizer artifact."""

    checkpoint_root = Path(checkpoint_root)
    paths = sorted(
        path
        for path in checkpoint_root.iterdir()
        if path.is_file()
        and (
            path.name.startswith("policy_preprocessor")
            or path.name.startswith("policy_postprocessor")
            or "tokenizer" in path.name
        )
    )
    labeled: list[tuple[str, Path]] = [
        (f"checkpoint/{path.name}", path) for path in paths
    ]
    if tokenizer_root is not None:
        tokenizer_root = Path(tokenizer_root)
        labeled.extend(
            (f"tokenizer/{path.relative_to(tokenizer_root).as_posix()}", path)
            for path in sorted(tokenizer_root.rglob("*"))
            if path.is_file()
        )
    if not labeled:
        raise RuntimeError("theta0 processor artifacts are missing")
    digest = hashlib.sha256()
    for label, path in labeled:
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _extract_last_hidden(output: Any) -> Any:
    candidates = output if isinstance(output, (tuple, list)) else (output,)
    for candidate in candidates:
        hidden_states = getattr(candidate, "hidden_states", None)
        if hidden_states:
            return hidden_states[-1]
        last_hidden = getattr(candidate, "last_hidden_state", None)
        if last_hidden is not None:
            return last_hidden
        if hasattr(candidate, "ndim") and candidate.ndim == 3:
            return candidate
    raise RuntimeError("PI0.5 prefix hook did not expose final hidden states")


def _masked_mean(value: MaskedHiddenStates) -> np.ndarray:
    selected = value.hidden[value.attention_mask]
    return selected.mean(axis=0, dtype=np.float64).astype(np.float32)


def _l2_normalize(value: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(value))
    if norm <= 1e-12:
        raise ValueError("cannot normalize a zero scene/signature vector")
    return (value / norm).astype(np.float32)


def _update_digest(digest: "hashlib._Hash", value: Any) -> None:
    """Canonical recursive hashing for processor outputs."""

    if isinstance(value, Mapping):
        digest.update(b"mapping\0")
        for key in sorted(value, key=str):
            _update_digest(digest, str(key))
            _update_digest(digest, value[key])
        return
    if isinstance(value, (str, bytes)):
        payload = value.encode("utf-8") if isinstance(value, str) else value
        digest.update(type(value).__name__.encode("ascii"))
        digest.update(len(payload).to_bytes(8, "little"))
        digest.update(payload)
        return
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(value)
    elif hasattr(value, "detach") and hasattr(value, "cpu"):
        array = np.ascontiguousarray(value.detach().cpu().numpy())
    elif isinstance(value, Sequence):
        digest.update(b"sequence\0")
        digest.update(len(value).to_bytes(8, "little"))
        for item in value:
            _update_digest(digest, item)
        return
    elif value is None or isinstance(value, (bool, int, float)):
        digest.update(repr(value).encode("ascii"))
        digest.update(b"\0")
        return
    else:
        raise TypeError(f"unsupported processor value in feature fingerprint: {type(value)!r}")
    digest.update(b"array\0")
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(json.dumps(array.shape).encode("ascii"))
    digest.update(array.tobytes(order="C"))


__all__ = [
    "MaskedHiddenStates",
    "Pi05PrefixFeatureSource",
    "processor_artifact_digest",
    "SceneSignatureFeatures",
    "Theta0SceneEncoder",
]
