"""N28 one current-chunk parent mutation, before unchanged renoise/denoise."""
import json
import time
import torch
from core.qd_actuator_clipped_rbf import applied_evidence
from core.qd_clean_output_rbf import require_sample_scheduler
from core.qd_feasible_ray_rbf import (FeasibleRayWitness, validate_update_option,
    MODE as UPDATE_MODE, observe)
from core.qd_feasible_ray_update import feasible_ray_update

DEFAULT = "model_output"
MODE = "parent_before_renoise_v1"
SOURCE = "core.qd_parent_before_renoise:parent_before_renoise_v1"
INPUT = "current_chunk_selected_parent_offspring"


def validate_placement(cfg):
    mode = getattr(cfg, "rollout_diversity_placement", DEFAULT)
    if mode not in {DEFAULT, MODE}:
        raise ValueError("unsupported rollout_diversity_placement")
    if mode == DEFAULT:
        return
    validate_update_option(cfg)
    if cfg.diversity_update_mode != UPDATE_MODE:
        raise ValueError("N28 requires N27 feasible-ray update")


def mutate(offspring, *, cfg, scheduler, compute_gradient, mask_gradient,
           witness, iteration, parent_allocation_sequence):
    """Mutate only the actual selected copy; no RNG/model/score calls."""
    validate_placement(cfg)
    if cfg.rollout_diversity_placement != MODE:
        raise ValueError("N28 requires explicit parent placement")
    require_sample_scheduler(cfg, scheduler)
    if tuple(offspring.shape) != (16, 64, 128):
        raise ValueError("N28 requires 16 selected parent offspring")
    if type(iteration) is not int or not 0 <= iteration < 10:
        raise ValueError("N28 parent iteration outside fixed ten rounds")
    capture = witness.prepare("parent", iteration)
    gradient, evidence = compute_gradient(
        offspring, descriptor_mode=cfg.rollout_diversity_descriptor_mode,
        descriptor_cfg=cfg.__dict__,
        **({"capture_out": capture} if capture is not None else {}))
    if gradient is None or not bool(torch.isfinite(gradient).all()):
        raise ValueError("N28 missing/nonfinite parent gradient")
    masked = mask_gradient(gradient).to(device=offspring.device, dtype=offspring.dtype)
    operand = -1.0 * float(cfg.rollout_diversity_scale) * masked[:, :8, (39, 40, 41)]
    before = offspring[:, :8, (39, 40, 41)].detach().clone()
    started = time.perf_counter()
    feasible = feasible_ray_update(before, operand)
    offspring[:, :8, (39, 40, 41)] = feasible.prefix
    after = offspring[:, :8, (39, 40, 41)]
    applied_evidence(evidence, masked=masked, update=operand, phase="parent",
                     iteration=iteration, step=None, timestep=None)
    observe(evidence, before, after, operand, feasible.alpha, started)
    evidence.update(schema="n28-parent-rbf-call-summary-v1", source=SOURCE,
        input_source=INPUT, input_binding="selected_offspring_before_original_renoise",
        rollout_diversity_placement=MODE, parent_allocation_sequence=parent_allocation_sequence,
        prediction_type="sample", model_jacobian_used=False,
        update_operand_semantics="unconstrained_native_parent_proposal_before_feasible_ray",
        after_semantics="assigned_parent_offspring; not model output or final action",
        original_renoise_and_denoise_follow=True)
    if capture is not None:
        capture.update(update_operand=operand.detach().clone(),
                       parent_offspring_before=before,
                       parent_offspring_after=after.detach().clone())
        witness.emit(capture, evidence)
    return evidence


class ParentWitness(FeasibleRayWitness):
    """First guided decision: original initial slot plus ten parent slots."""
    SOURCE = SOURCE
    SCHEMA = "n28-bounded-rbf-witness-v1"
    EVENT = "n28_rbf_witness"
    COVERAGE_EVENT = "n28_rbf_witness_coverage"
    SLOTS = (("initial", -1),) + tuple(("parent", i) for i in range(10))

    def emit(self, capture, evidence):
        if capture is None:
            return
        if evidence.get("phase") == "initial":
            # Original N27 initial math and same-forward binding remain truthful.
            return super().emit(capture, evidence)
        if (evidence.get("schema") != "n28-parent-rbf-call-summary-v1"
            or evidence.get("source") != SOURCE or evidence.get("input_source") != INPUT
            or evidence.get("input_binding") != "selected_offspring_before_original_renoise"
            or evidence.get("phase") != "parent" or evidence.get("denoising_step") is not None
            or evidence.get("timestep") is not None or evidence.get("model_jacobian_used") is not False):
            raise ValueError("N28 parent witness semantic downgrade")
        if not self.active or self.recorder is None:
            raise ValueError("N28 witness outside first guided decision")
        key = ("parent", evidence["iteration"])
        if key not in self.seen or key in self.recorded or len(self.recorded) >= 11:
            raise ValueError("N28 duplicate/unselected witness")
        expected = {"input_xyz", "source_origins", "cast_origins", "projected_xyz",
                    "gradient_before", "gradient_after", "update_operand",
                    "parent_offspring_before", "parent_offspring_after"}
        if set(capture) != expected:
            raise ValueError("N28 witness tensor fields differ")
        for name, value in capture.items():
            shape = (16, 3) if name in {"source_origins", "cast_origins"} else (16, 8, 3)
            if not torch.is_tensor(value) or tuple(value.shape) != shape or not bool(torch.isfinite(value).all()):
                raise ValueError("N28 witness tensor shape/nonfinite")
        a, b = capture["input_xyz"], capture["parent_offspring_before"]
        if a.dtype != b.dtype or a.device != b.device or not torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8)):
            raise ValueError("N28 input is not selected parent before assignment")
        count = sum(v.numel() * v.element_size() for v in capture.values())
        if count > self.NUMERIC_CALL_CAP or self.numeric_bytes + count > self.NUMERIC_EPISODE_CAP:
            raise ValueError("N28 numeric witness cap")
        metadata = {"schema": self.SCHEMA, "source": self.SOURCE, "call": dict(evidence),
            "numeric_bytes": count, "tensors": {n: {"dtype": str(v.dtype), "shape": list(v.shape),
            "capture_stride_before_serialization": list(v.stride())} for n, v in capture.items()},
            "identity_binding": "enclosing decision plus actual parent_allocation sequence; current chunk selected offspring",
            "exact_cuda_replay_claim": False}
        if len(json.dumps(metadata, allow_nan=False).encode()) > self.METADATA_CALL_CAP:
            raise ValueError("N28 metadata witness cap")
        self.recorder.record(self.EVENT, metadata=metadata, tensors=capture)
        self.numeric_bytes += count
        self.recorded.append(key)
