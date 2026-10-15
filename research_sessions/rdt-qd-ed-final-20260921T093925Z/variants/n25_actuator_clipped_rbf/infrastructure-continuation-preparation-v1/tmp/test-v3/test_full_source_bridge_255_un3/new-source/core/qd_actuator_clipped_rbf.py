"""N25 opt-in RBF geometry. No scoring, model calls, RNG or execution changes."""
from __future__ import annotations

import math
import json

import torch

MODE = "actuator_clipped_eef_v1"
HORIZON = 8
TRANSLATION = (39, 40, 41)
SOURCE = "core.qd_actuator_clipped_rbf:clipped_rbf_gradient:v1"


class _StrictInteriorClip(torch.autograd.Function):
    """Native clamp forward; explicitly zero derivative at both exact bounds."""

    @staticmethod
    def forward(ctx, values):
        ctx.save_for_backward((values > -1) & (values < 1))
        return values.clamp(-1, 1)

    @staticmethod
    def backward(ctx, upstream):
        (interior,) = ctx.saved_tensors
        return upstream * interior.to(dtype=upstream.dtype)


def strict_interior_clip(values):
    return _StrictInteriorClip.apply(values)


def tensor_summary(value):
    """Native scalar summaries, explicitly not a byte-exact replay witness."""
    value = value.detach()
    if not bool(torch.isfinite(value).all()):
        raise ValueError("N25 nonfinite tensor")
    norm = float(torch.norm(value).item())
    if not math.isfinite(norm):
        raise ValueError("N25 nonfinite norm")
    return {"finite": True, "zero": not bool(torch.count_nonzero(value)),
            "norm": norm, "norm_dtype": str(value.dtype)}


def clipped_rbf_gradient(x_t, *, project, horizon, capture_out=None):
    """Use the SAME per-row native projector/origin calls as absolute RBF.

    Only its temporary RBF input has clipped translation. In particular, this
    does not replace the policy's score/descriptor/decoder projector. The native
    LIBERO projector provides origin+cumsum(delta*.01), including its start row.
    """
    if (x_t.ndim != 3 or tuple(x_t.shape[1:]) != (64, 128)
            or x_t.shape[0] < 2 or horizon != HORIZON
            or x_t.dtype not in (torch.float32, torch.bfloat16)):
        raise ValueError("N25 requires B>=2, (B,64,128), horizon8 and FP32/BF16")
    if not bool(torch.isfinite(x_t).all()):
        raise ValueError("N25 nonfinite input")
    B = x_t.shape[0]
    with torch.enable_grad():
        x_grad = x_t.detach().requires_grad_(True)
        proposal = x_grad.clone()
        translation = x_grad[:, :HORIZON, TRANSLATION]
        proposal[:, :HORIZON, TRANSLATION] = strict_interior_clip(translation)
        # Preserve absolute RBF's per-candidate projection and concatenation.
        projections = []
        origins = []
        for b in range(B):
            if capture_out is None:
                projections.append(project(proposal[b:b + 1]))
            else:
                metadata = {}
                projections.append(project(proposal[b:b + 1], origin_out=metadata))
                if len(metadata.get("source_origins", [])) != 1:
                    raise ValueError("N25 missing same-call origin witness")
                origins.append(metadata["source_origins"][0])
        trajs = torch.cat(projections, dim=0)
        if tuple(trajs.shape) != (B, HORIZON + 1, 3) or trajs.dtype != x_t.dtype:
            raise ValueError("N25 projector shape/dtype mismatch")
        if trajs.device != x_t.device or not bool(torch.isfinite(trajs).all()):
            raise ValueError("N25 projector device/nonfinite mismatch")
        flat = trajs[:, 1:, :3].reshape(B, -1)
        sq_dist = torch.sum((flat.unsqueeze(1) - flat.unsqueeze(0)) ** 2, dim=2)
        mask = ~torch.eye(B, dtype=torch.bool, device=x_t.device)
        dist = torch.sqrt(sq_dist + 1e-6)
        inv_dist = (1.0 / (dist + 1e-6)) * mask.float()
        potential = inv_dist.sum()
        if not bool(torch.isfinite(potential)):
            raise ValueError("N25 nonfinite potential")
        grad = torch.autograd.grad(potential, x_grad, create_graph=False, allow_unused=True)[0]
        if grad is None:
            raise ValueError("N25 missing gradient; no fallback")
        before = tensor_summary(grad)
        g_norm = before["norm"]
        normalized = grad / (g_norm + 1e-8) if g_norm > 1e-8 else grad
        after = tensor_summary(normalized)
        if capture_out is not None:
            capture_out.update({
                "input_xyz": translation.detach().clone(),
                "source_origins": torch.stack(origins),
                "cast_origins": trajs[:, 0, :].detach().clone(),
                "projected_xyz": trajs[:, 1:, :].detach().clone(),
                "gradient_before": grad[:, :HORIZON, TRANSLATION].detach().clone(),
                "gradient_after": normalized[:, :HORIZON, TRANSLATION].detach().clone(),
            })
    raw = translation.detach()
    evidence = {
        "descriptor_mode": MODE, "source": SOURCE, "schema": "n25-rbf-call-summary-v1",
        "summary_only_not_exact_replay": True, "absolute_fallback_used": False,
        "input_shape": list(x_t.shape), "input_dtype": str(x_t.dtype),
        "input_stride": list(x_t.stride()), "horizon": HORIZON,
        "translation_indices": list(TRANSLATION), "translation_components": raw.numel(),
        "clipped_components": int(((raw < -1) | (raw > 1)).sum().item()),
        "boundary_components": int(((raw == -1) | (raw == 1)).sum().item()),
        "interior_components": int(((raw > -1) & (raw < 1)).sum().item()),
        "gradient_before_normalization": before, "gradient_after_normalization": after,
        "zero_gradient": after["zero"], "nonfinite_count": 0,
        "projection_origin_binding": "same per-row native projector invocation; no second read",
    }
    return normalized, evidence


def applied_evidence(evidence, *, masked, update, phase, iteration, step, timestep):
    """Observe already computed operands; no shadow gradient/projector/model."""
    evidence.update({"phase": phase, "iteration": iteration, "denoising_step": step,
                     "timestep": timestep, "masked_gradient": tensor_summary(masked),
                     "update_operand": tensor_summary(update),
                     "update_operand_is_measured_output_delta": False,
                     "decision_binding": "enclosing EDSChunkMetrics; global_step/stage attached at loop closure"})


def bind_decision_metrics(metrics, *, global_step, stage):
    groups = [metrics.initial_direction_rbf_evidence_by_step,
              *metrics.rollout_direction_rbf_evidence_by_iter]
    for group in groups:
        for row in group:
            if row.get("descriptor_mode") == MODE:
                row.update({"global_step": int(global_step), "stage": int(stage)})


class BoundedWitness:
    """First guided decision only; first active call per fixed stage/iteration.

    Reset by policy episode reset, never by Stage. Selection does not inspect
    values, outcome or recorder availability. No backfill across decisions.
    """
    NUMERIC_CALL_CAP = 20 * 1024
    NUMERIC_EPISODE_CAP = 220 * 1024
    METADATA_CALL_CAP = 16 * 1024
    SLOTS = (("initial", -1),) + tuple(("rollout", i) for i in range(10))

    def __init__(self):
        self.first_consumed = False
        self.active = False
        self.seen = set()
        self.numeric_bytes = 0
        self.recorded = []

    def begin(self, recorder):
        self.active = not self.first_consumed
        self.first_consumed = True
        self.recorder = recorder
        self.seen = set()

    def prepare(self, phase, iteration):
        key = (phase, iteration)
        if not self.active or key in self.seen:
            return None
        if key not in self.SLOTS:
            raise ValueError("N25 witness unregistered slot")
        self.seen.add(key)
        return {} if self.recorder is not None else None

    def emit(self, capture, evidence):
        if capture is None:
            return
        if not self.active or self.recorder is None:
            raise ValueError("N25 witness outside first guided decision")
        key = (evidence["phase"], evidence["iteration"])
        if key not in self.seen or key in self.recorded or len(self.recorded) >= 11:
            raise ValueError("N25 witness duplicate/unselected call")
        expected = {"input_xyz", "source_origins", "cast_origins", "projected_xyz",
                    "gradient_before", "gradient_after", "update_operand",
                    "model_output_before", "model_output_after"}
        if set(capture) != expected:
            raise ValueError("N25 witness tensor fields mismatch")
        for name, value in capture.items():
            shape = (16, 3) if name in {"source_origins", "cast_origins"} else (16, 8, 3)
            if not torch.is_tensor(value) or tuple(value.shape) != shape:
                raise ValueError("N25 witness tensor shape mismatch")
            if not bool(torch.isfinite(value).all()):
                raise ValueError("N25 witness nonfinite tensor")
        count = sum(v.numel() * v.element_size() for v in capture.values())
        if count > self.NUMERIC_CALL_CAP or self.numeric_bytes + count > self.NUMERIC_EPISODE_CAP:
            raise ValueError("N25 witness numeric byte cap exceeded")
        metadata = {"schema": "n25-bounded-rbf-witness-v1", "source": SOURCE,
                    "call": dict(evidence), "numeric_bytes": count,
                    "tensors": {name:{"dtype":str(value.dtype), "shape":list(value.shape),
                                      "capture_stride_before_serialization":list(value.stride())} for name,value in capture.items()},
                    "identity_binding": "enclosing decision event and metered worker source/runtime receipt; no identity probe here",
                    "exact_cuda_replay_claim": False}
        if len(json.dumps(metadata, allow_nan=False).encode()) > self.METADATA_CALL_CAP:
            raise ValueError("N25 witness identity metadata cap exceeded")
        self.recorder.record("n25_rbf_witness", metadata=metadata, tensors=capture)
        self.numeric_bytes += count
        self.recorded.append(key)

    def finish(self):
        if self.active and self.recorder is not None:
            self.recorder.record("n25_rbf_witness_coverage", selected_slots=[list(x) for x in self.recorded],
                                 missing_slots=[list(x) for x in self.SLOTS if x not in self.recorded],
                                 numeric_bytes=self.numeric_bytes, max_calls=11,
                                 numeric_cap_bytes=self.NUMERIC_EPISODE_CAP)
        self.active = False
