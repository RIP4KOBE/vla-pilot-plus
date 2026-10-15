#!/usr/bin/env python3
"""Deterministic CPU preflight for the EDS-QD global-quality anchor."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import torch
from torch import nn


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
OWNED_ROOT = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/"
    "eds-qd-autoresearch-libero-swap-ood/"
    "run_032_global_quality_anchor_cpu_mechanism"
)
ANALYSIS_ROOT = OWNED_ROOT / "analysis"
CANONICAL_PATH = ANALYSIS_ROOT / "mechanism_preflight.v1.json"
REPLAY_PATH = ANALYSIS_ROOT / "mechanism_preflight.replay.json"
SEED = 32032
EXPECTED_HASHES = {
    "core/qd_ed.py": (
        "4a43cc2db1f1f87eaabf2146058347f119f6059beb4bdf2e67e36f9b6680b653"
    ),
    "core/rdt_policy_steer.py": (
        "bdc523f602453c402aa290ed40e495952578a5e028e0c9374365161255e7cd41"
    ),
    "core/eds_eval_metrics.py": (
        "870636edbaf1023b6c8a71f7f0778e6efa29833fc24f64b651e48714a0d61a31"
    ),
    "configs/config.yaml": (
        "f8a9f07d52ea69ee3a69202ab5b89b4214353208ec27961ebcaef9b3d5b02d57"
    ),
}
SECRET_PATTERNS = (
    re.compile(r"sk-poe-[A-Za-z0-9_-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(?:api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{16,}"),
)
CASE_SPECS = {
    "candidate_rescue": {"fixture": "rescue", "anchor_count": 1},
    "legacy_rescue_fixture": {"fixture": "rescue", "anchor_count": 0},
    "candidate_overlap": {"fixture": "overlap", "anchor_count": 1},
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def strict_secret_match_count(value: Any) -> int:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return sum(len(pattern.findall(serialized)) for pattern in SECRET_PATTERNS)


def all_finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(all_finite(item) for item in value)
    return False


class _StubDiT(nn.Module):
    def forward(self, x, t, cond):
        return torch.zeros_like(x)


class _StubScheduler:
    def __init__(self, steps: int = 5):
        self.timesteps = torch.arange(steps - 1, -1, -1, dtype=torch.long)
        self.alphas_cumprod = torch.linspace(0.9, 0.1, steps)

    def set_timesteps(self, steps: int) -> None:
        self.timesteps = torch.arange(steps - 1, -1, -1, dtype=torch.long)
        self.alphas_cumprod = torch.linspace(0.9, 0.1, steps)

    def step(self, model_output, timestep, sample):
        return SimpleNamespace(
            prev_sample=sample + model_output,
            pred_original_sample=None,
        )

    def add_noise(self, original_samples, noise, timesteps):
        return original_samples + noise


class _StubRDTModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.dit = _StubDiT()
        self.noise_scheduler = _StubScheduler()

    def encode_inputs(self, state_128, state_mask_128, images, text_embeds):
        action_mask = torch.zeros(1, 1, 128, dtype=torch.float64)
        action_mask[0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0
        return {
            "lang_cond": torch.zeros(1, 1, 4, dtype=torch.float64),
            "lang_attn_mask": torch.ones(1, 1, dtype=torch.bool),
            "img_cond": torch.zeros(1, 1, 4, dtype=torch.float64),
            "state_traj": torch.zeros(1, 1, 4, dtype=torch.float64),
            "action_mask": action_mask,
            "ctrl_freqs": torch.tensor([20]),
            "action_indices": [39, 40, 41, 42, 43, 44, 10],
            "unified_action_dim": 128,
        }


class _Adapter:
    def delta_actions_to_ee_trajectory(self, sequence):
        start = torch.zeros(1, 3, device=sequence.device, dtype=sequence.dtype)
        deltas = torch.cumsum(sequence[:, :3], dim=0)
        return torch.cat([start, deltas], dim=0)


def reset_rng() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)


def rng_checksum() -> str:
    state = torch.random.get_rng_state().cpu().numpy().tobytes()
    return sha256_bytes(state)


def fixture_cells(fixture: str) -> list[int]:
    if fixture == "rescue":
        return [0] * 13 + [1, 2, 3]
    if fixture == "overlap":
        return [0, 1, 2, 3] * 4
    raise ValueError(f"unknown fixture: {fixture}")


def make_population(fixture: str, *, iteration: int) -> torch.Tensor:
    population = torch.zeros(16, 64, 128, dtype=torch.float64)
    scale = 0.04 + 0.002 * iteration
    corners = {
        0: (-scale, -scale),
        1: (scale, -scale),
        2: (-scale, scale),
        3: (scale, scale),
    }
    for row, cell in enumerate(fixture_cells(fixture)):
        endpoint_x, endpoint_y = corners[cell]
        population[row, :4, 39] = endpoint_x / 4.0
        population[row, :4, 40] = endpoint_y / 4.0
        reward = 100.0 + iteration if cell == 0 else 10.0 + cell
        population[row, :, 42] = reward
    return population


def qd_config(*, anchor_count: int) -> dict[str, Any]:
    return {
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "renoise_t_max": 3,
        "renoise_t_min": 1,
        "initial_sampling_mode": "rbf_diverse_denoise",
        "initial_diversity_descriptor_mode": "absolute_eef",
        "initial_diversity_scale": 20.0,
        "initial_diversity_start_ratio": 0.8,
        "truncated_rollout_mode": "rbf_diverse",
        "rollout_diversity_descriptor_mode": "absolute_eef",
        "rollout_diversity_scale": 20.0,
        "rollout_diversity_start_ratio": 0.6,
        "rollout_diversity_iters": "all",
        "rollout_diversity_skip_final_steps": 0,
        "parent_weighting_mode": "legacy_temperature",
        "parent_coverage_mode": "none",
        "parent_anchor_count": 0,
        "elite_carryover_count": 0,
        "chunk_population_mode": "fresh",
        "chunk_memory_fraction": 0.0,
        "rollout_diversity_control_mode": "fixed",
        "search_schedule_mode": "legacy_linear",
        "qd_archive_mode": "grid_archive",
        "qd_degenerate_fallback_policy": "none",
        "qd_descriptor": "target_relative_endpoint_xy",
        "qd_grid_shape": [4, 4],
        "qd_cell_capacity": 1,
        "qd_parent_sampling": "sparse_priority",
        "qd_global_quality_anchor_count": anchor_count,
        "qd_sparse_exponent": 1.0,
        "qd_bounds_quantiles": [0.05, 0.95],
        "qd_bounds_expand_fraction": 0.10,
        "qd_min_axis_span_m": 0.08,
        "qd_bounds_update_policy": "causal_envelope_v1",
        "qd_overflow_policy": "clamp_edge",
        "qd_tie_break": "stable_fingerprint",
        "qd_metrics_observer": False,
    }


def make_runtime(*, fixture: str, anchor_count: int):
    from core.rdt_policy_steer import RDTSteer

    steer = RDTSteer(rdt_model=_StubRDTModel(), num_inference_steps=5)
    steer.post_init(
        adapter=_Adapter(),
        postprocessor=lambda value: value,
        sample_batch_size=16,
        policy_config={"action_chunk_horizon": 4},
    )
    model = steer._rdt_model
    cond = model.encode_inputs(
        torch.zeros(1, 128, dtype=torch.float64),
        torch.zeros(1, 128, dtype=torch.float64),
        [],
        torch.zeros(1, 1, 4, dtype=torch.float64),
    )
    rollout_batch_sizes: list[int] = []

    def initial_population(**kwargs):
        return make_population(fixture, iteration=0)

    def score_population(samples, **kwargs):
        rewards = samples[:, 0, 42].detach().clone()
        return -rewards, {"rewards": rewards}

    def rollout(**kwargs):
        rollout_batch_sizes.append(int(kwargs["noisy_action"].shape[0]))
        children = make_population(fixture, iteration=int(kwargs["iter_idx"]) + 1)
        costs, info = score_population(children)
        return children, costs, info

    steer._eds_initial_population = initial_population
    steer._eds_score_population_as_cost = score_population
    steer._eds_renoise_reference = lambda samples, steps: samples
    steer._eds_rollout_reference = rollout
    steer._decode_visualization_action_candidates = lambda samples: samples
    config = steer._resolve_eds_config_with_reference_defaults(
        qd_config(anchor_count=anchor_count)
    )
    return steer, cond, config, rollout_batch_sizes


def execute_case(*, fixture: str, anchor_count: int) -> dict[str, Any]:
    from core.qd_ed import fingerprint_action

    reset_rng()
    start_rng = rng_checksum()
    steer, cond, config, rollout_batch_sizes = make_runtime(
        fixture=fixture,
        anchor_count=anchor_count,
    )
    selected = steer._eds_guided_denoise_loop(
        x_t=torch.zeros(16, 64, 128, dtype=torch.float64),
        cond=cond,
        keypoints=torch.zeros(1, 3, dtype=torch.float64),
        guidance_fns=None,
        eds_config=config,
        verbose=False,
        global_step=24,
        current_stage=2,
    )
    metrics = steer.get_last_eds_metrics()
    deterministic_metrics = {
        field: metrics.get(field)
        for field in (
            "qd_archive_enabled",
            "qd_archive_active_for_chunk",
            "qd_degenerate_fallback_policy",
            "qd_degenerate_fallback_used",
            "qd_global_quality_anchor_count",
            "qd_global_quality_anchor_activation_count",
            "qd_global_quality_anchor_rescue_count",
            "qd_global_quality_anchor_cell_by_iter",
            "qd_global_quality_anchor_fingerprint_by_iter",
            "qd_global_quality_anchor_sparse_slot_count_by_iter",
            "qd_global_quality_anchor_rescued_by_iter",
            "qd_sparse_parent_slots_by_cell_by_iter",
            "qd_parent_slots_by_cell_by_iter",
            "parent_count_by_source",
            "search_evaluation_count",
            "qd_evaluation_count",
            "score_call_count",
            "nonfinite_count",
            "action_mask_violation_max",
            "gripper_qpos_violation_count",
            "qd_accounting_violation_count",
            "qd_elite_monotonicity_violation_count",
            "qd_final_selection_mismatch_count",
            "qd_bounds_expansion_count",
            "qd_bounds_expanded_by_iter",
            "qd_archive_rebin_visit_sum_before_by_iter",
            "qd_archive_rebin_visit_sum_after_by_iter",
            "qd_selected_action_fingerprint",
            "qd_global_best_action_fingerprint",
            "qd_selected_reward",
            "selected_reward",
            "selected_chunk_population_source",
        )
    }
    return {
        "fixture": fixture,
        "anchor_count": anchor_count,
        "rollout_batch_sizes": rollout_batch_sizes,
        "selected_action_fingerprint": fingerprint_action(selected[0]),
        "start_torch_rng_sha256": start_rng,
        "terminal_torch_rng_sha256": rng_checksum(),
        "metrics": deterministic_metrics,
    }


def run_case(name: str) -> dict[str, Any]:
    spec = CASE_SPECS[name]
    return execute_case(
        fixture=str(spec["fixture"]),
        anchor_count=int(spec["anchor_count"]),
    )


def allocation_relation(case: dict[str, Any], *, relation: str) -> bool:
    metrics = case["metrics"]
    for cell, sparse, total, rescued in zip(
        metrics["qd_global_quality_anchor_cell_by_iter"],
        metrics["qd_sparse_parent_slots_by_cell_by_iter"],
        metrics["qd_parent_slots_by_cell_by_iter"],
        metrics["qd_global_quality_anchor_rescued_by_iter"],
        strict=True,
    ):
        sparse_count = int(sparse[str(cell)])
        total_count = int(total[str(cell)])
        if relation == "rescue" and not (
            sparse_count == 0 and total_count == 1 and rescued is True
        ):
            return False
        if relation == "overlap" and not (
            sparse_count > 0
            and total_count == sparse_count + 1
            and rescued is False
        ):
            return False
    return True


def complete_case_safe(case: dict[str, Any]) -> bool:
    metrics = case["metrics"]
    return (
        metrics["qd_archive_enabled"] is True
        and metrics["qd_archive_active_for_chunk"] is True
        and metrics["qd_degenerate_fallback_policy"] == "none"
        and metrics["qd_degenerate_fallback_used"] is False
        and metrics["search_evaluation_count"] == 176
        and metrics["qd_evaluation_count"] == 176
        and metrics["score_call_count"] == 11
        and metrics["nonfinite_count"] == 0
        and metrics["action_mask_violation_max"] == 0.0
        and metrics["gripper_qpos_violation_count"] == 0
        and metrics["qd_accounting_violation_count"] == 0
        and metrics["qd_elite_monotonicity_violation_count"] == 0
        and metrics["qd_final_selection_mismatch_count"] == 0
        and metrics["qd_selected_action_fingerprint"]
        == metrics["qd_global_best_action_fingerprint"]
        == case["selected_action_fingerprint"]
        and metrics["qd_selected_reward"] == metrics["selected_reward"]
        and metrics["qd_archive_rebin_visit_sum_before_by_iter"]
        == metrics["qd_archive_rebin_visit_sum_after_by_iter"]
    )


def candidate_shape(case: dict[str, Any]) -> bool:
    metrics = case["metrics"]
    return (
        metrics["qd_global_quality_anchor_count"] == 1
        and metrics["qd_global_quality_anchor_activation_count"] == 10
        and case["rollout_batch_sizes"] == [16] * 10
        and all(
            sum(slots.values()) == 15
            for slots in metrics["qd_sparse_parent_slots_by_cell_by_iter"]
        )
        and all(
            sum(slots.values()) == 16
            for slots in metrics["qd_parent_slots_by_cell_by_iter"]
        )
    )


def run_scientific_suite() -> dict[str, Any]:
    actual_hashes = {
        path: sha256_file(REPO_ROOT / path) for path in EXPECTED_HASHES
    }
    if actual_hashes != EXPECTED_HASHES:
        raise RuntimeError("frozen algorithm/config hash mismatch")
    if torch.cuda.is_initialized():
        raise RuntimeError("run_032 must remain CPU-only")

    cases = {name: run_case(name) for name in CASE_SPECS}
    case_replays = {name: run_case(name) for name in CASE_SPECS}
    rescue = cases["candidate_rescue"]
    overlap = cases["candidate_overlap"]
    comparator = cases["legacy_rescue_fixture"]
    comparator_metrics = comparator["metrics"]
    per_case_identity = all(
        canonical_bytes(cases[name]) == canonical_bytes(case_replays[name])
        for name in CASE_SPECS
    )
    gates = {
        "identity_cpu_finite_secret": (
            actual_hashes == EXPECTED_HASHES
            and not torch.cuda.is_initialized()
            and all(all_finite(case) for case in cases.values())
            and strict_secret_match_count(cases) == 0
        ),
        "candidate_one_plus_fifteen": (
            candidate_shape(rescue) and candidate_shape(overlap)
        ),
        "rescue_fixture": (
            rescue["metrics"]["qd_global_quality_anchor_rescue_count"] == 10
            and allocation_relation(rescue, relation="rescue")
        ),
        "overlap_fixture": (
            overlap["metrics"]["qd_global_quality_anchor_rescue_count"] == 0
            and allocation_relation(overlap, relation="overlap")
        ),
        "legacy_comparator": (
            comparator_metrics["qd_global_quality_anchor_count"] == 0
            and comparator_metrics["qd_global_quality_anchor_activation_count"] == 0
            and comparator_metrics["qd_global_quality_anchor_rescue_count"] == 0
            and comparator["rollout_batch_sizes"] == [16] * 10
            and all(
                sum(slots.values()) == 16
                for slots in comparator_metrics["qd_sparse_parent_slots_by_cell_by_iter"]
            )
        ),
        "compute_safety_archive_final_selection": all(
            complete_case_safe(case) for case in cases.values()
        ),
        "parent_source_accounting": (
            rescue["metrics"]["parent_count_by_source"]
            == {
                "elite": 0,
                "anchor_offspring": 0,
                "weighted_offspring": 0,
                "qd_global_quality_anchor_offspring": 10,
                "qd_archive_offspring": 150,
            }
            and comparator_metrics["parent_count_by_source"]
            == {
                "elite": 0,
                "anchor_offspring": 0,
                "weighted_offspring": 0,
                "qd_archive_offspring": 160,
            }
        ),
        "rng_and_per_case_replay_identity": per_case_identity,
        "harness_sources_present": (
            Path(__file__).is_file()
            and (
                REPO_ROOT
                / "tests/test_eds_qd_global_quality_anchor_preflight.py"
            ).is_file()
        ),
        "owned_artifact_path_contract": (
            CANONICAL_PATH.parent == ANALYSIS_ROOT
            and REPLAY_PATH.parent == ANALYSIS_ROOT
            and ANALYSIS_ROOT.parent == OWNED_ROOT
            and CANONICAL_PATH != REPLAY_PATH
        ),
    }
    fixture = {
        "seed": SEED,
        "dtype": "float64",
        "population_shape": [16, 64, 128],
        "iterations": 10,
        "case_specs": CASE_SPECS,
        "visit_shapes": {
            "rescue": [13, 1, 1, 1],
            "overlap": [4, 4, 4, 4],
        },
    }
    return {
        "fixture": fixture,
        "fixture_sha256": canonical_sha256(fixture),
        "frozen_hashes": actual_hashes,
        "cases": cases,
        "per_case_replay_sha256": {
            name: canonical_sha256(case_replays[name]) for name in CASE_SPECS
        },
        "gates": gates,
        "passed": all(gates.values()),
    }


def current_revision() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()


def build_payload() -> dict[str, Any]:
    first = run_scientific_suite()
    second = run_scientific_suite()
    replay_identical = canonical_bytes(first) == canonical_bytes(second)
    source_hashes = {
        "scripts/eds_qd_global_quality_anchor_preflight.py": sha256_file(
            Path(__file__).resolve()
        ),
        "tests/test_eds_qd_global_quality_anchor_preflight.py": sha256_file(
            REPO_ROOT / "tests/test_eds_qd_global_quality_anchor_preflight.py"
        ),
    }
    payload = {
        "schema_version": 1,
        "experiment_id": "run_032_global_quality_anchor_cpu_mechanism",
        "hypothesis_id": "H4-v3",
        "algorithm_iteration": 3,
        "implementation_revision": current_revision(),
        "source_hashes": source_hashes,
        "scientific_payload": first,
        "scientific_payload_sha256": canonical_sha256(first),
        "independent_replay_sha256": canonical_sha256(second),
        "double_run_byte_identical": replay_identical,
        "online_episode_attempts": 0,
        "gpu_hours": 0.0,
        "credential_match_count": 0,
    }
    payload["passed"] = bool(first["passed"] and replay_identical)
    payload["credential_match_count"] = strict_secret_match_count(payload)
    if payload["credential_match_count"]:
        raise RuntimeError("strict credential scan failed")
    if not all_finite(payload):
        raise RuntimeError("nonfinite preflight payload")
    if not payload["passed"]:
        raise RuntimeError("run_032 CPU mechanism preflight failed")
    return payload


def write_immutable_artifacts(payload: dict[str, Any]) -> dict[str, Any]:
    encoded = canonical_bytes(payload)
    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    for path in (CANONICAL_PATH, REPLAY_PATH):
        if path.exists():
            if path.read_bytes() != encoded:
                raise RuntimeError(f"immutable artifact mismatch: {path.name}")
        else:
            temporary = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
            temporary.write_bytes(encoded)
            os.chmod(temporary, 0o444)
            os.replace(temporary, path)
        os.chmod(path, 0o444)
    if CANONICAL_PATH.read_bytes() != REPLAY_PATH.read_bytes():
        raise RuntimeError("canonical and replay artifacts differ")
    return {
        "canonical_path": str(CANONICAL_PATH),
        "replay_path": str(REPLAY_PATH),
        "file_sha256": sha256_bytes(encoded),
        "size_bytes": len(encoded),
        "mode": "0444",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    payload = build_payload()
    summary = {
        "passed": payload["passed"],
        "scientific_payload_sha256": payload["scientific_payload_sha256"],
        "double_run_byte_identical": payload["double_run_byte_identical"],
        "credential_match_count": payload["credential_match_count"],
    }
    if not args.no_write:
        summary.update(write_immutable_artifacts(payload))
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
