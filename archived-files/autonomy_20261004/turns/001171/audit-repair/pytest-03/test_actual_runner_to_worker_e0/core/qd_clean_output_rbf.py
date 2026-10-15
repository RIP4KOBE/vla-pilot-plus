"""N26 input-source binding only. Numerical geometry remains in the N25 helper."""
from collections.abc import Mapping
import torch
from core.qd_actuator_clipped_rbf import MODE, BoundedWitness

NOISY_SOURCE = "noisy_sample"
CLEAN_SOURCE = "model_output_sample_v1"
SOURCE = "core.qd_clean_output_rbf:model_output_sample_v1"


def validate_source_option(cfg):
    source = cfg.diversity_input_source
    if source not in {NOISY_SOURCE, CLEAN_SOURCE}:
        raise ValueError("unsupported diversity_input_source")
    if source == CLEAN_SOURCE:
        expected = {"initial_diversity_descriptor_mode": MODE,
                    "rollout_diversity_descriptor_mode": MODE,
                    "initial_sampling_mode": "rbf_diverse_denoise",
                    "truncated_rollout_mode": "rbf_diverse",
                    "use_initial_cache": False,
                    "initial_population_cache": None, "ed_population_cache": None,
                    "save_initial_cache": False, "save_ed_cache": False}
        for name, value in expected.items():
            if getattr(cfg, name) != value:
                raise ValueError(f"N26 requires {name}={value!r}")


def require_sample_scheduler(cfg, scheduler):
    validate_source_option(cfg)
    if cfg.diversity_input_source == NOISY_SOURCE:
        return
    config = getattr(scheduler, "config", None)
    prediction = config.get("prediction_type") if isinstance(config, Mapping) else getattr(config, "prediction_type", None)
    if prediction != "sample":
        raise ValueError("N26 requires the actual scheduler.config.prediction_type=sample")


def geometry_input(noisy_sample, model_output, cfg, scheduler):
    """Return the same tensor object; detach/leaf creation happens in shared math."""
    require_sample_scheduler(cfg, scheduler)
    return model_output if cfg.diversity_input_source == CLEAN_SOURCE else noisy_sample


def bind_input_evidence(evidence, cfg, scheduler):
    if cfg.diversity_input_source == CLEAN_SOURCE:
        require_sample_scheduler(cfg, scheduler)
        evidence.update(schema="n26-rbf-call-summary-v1", source=SOURCE,
                        input_source=CLEAN_SOURCE, prediction_type="sample",
                        input_binding="same_forward_unmodified_model_output",
                        model_jacobian_used=False)


class CleanOutputWitness(BoundedWitness):
    SOURCE = SOURCE
    SCHEMA = "n26-bounded-rbf-witness-v1"
    EVENT = "n26_rbf_witness"
    COVERAGE_EVENT = "n26_rbf_witness_coverage"

    def emit(self, capture, evidence):
        if capture is not None:
            if (evidence.get("schema") != "n26-rbf-call-summary-v1"
                    or evidence.get("source") != SOURCE
                    or evidence.get("input_source") != CLEAN_SOURCE
                    or evidence.get("prediction_type") != "sample"
                    or evidence.get("input_binding") != "same_forward_unmodified_model_output"
                    or evidence.get("model_jacobian_used") is not False):
                raise ValueError("N26 clean-output witness source binding differs")
            a, b = capture.get("input_xyz"), capture.get("model_output_before")
            if (not torch.is_tensor(a) or not torch.is_tensor(b) or a.dtype != b.dtype
                    or a.device != b.device or a.shape != b.shape
                    or not torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8))):
                raise ValueError("N26 input differs from unmodified model output bytes")
        super().emit(capture, evidence)
