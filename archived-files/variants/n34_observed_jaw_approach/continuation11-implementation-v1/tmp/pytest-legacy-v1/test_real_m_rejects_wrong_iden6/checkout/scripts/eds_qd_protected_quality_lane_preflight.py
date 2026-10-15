#!/usr/bin/env python3
"""Deterministic CPU preflight for the protected EDS-QD quality lane."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BASE_HARNESS_PATH = REPO_ROOT / "scripts/eds_qd_global_quality_anchor_preflight.py"
BASE_HARNESS_SHA256 = (
    "a2c517a1b3d785cb0f6010bc0f78ddb3732ffcfb75a579a51d92782e215fb04b"
)
BASE_SPEC = importlib.util.spec_from_file_location(
    "eds_qd_global_quality_anchor_preflight_base", BASE_HARNESS_PATH
)
if BASE_SPEC is None or BASE_SPEC.loader is None:
    raise RuntimeError("unable to load frozen CPU harness base")
base = importlib.util.module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(base)

OWNED_ROOT = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/"
    "eds-qd-autoresearch-libero-swap-ood/"
    "run_043_protected_quality_lane_cpu_mechanism"
)
ANALYSIS_ROOT = OWNED_ROOT / "analysis"
CANONICAL_PATH = ANALYSIS_ROOT / "mechanism_preflight.v1.json"
REPLAY_PATH = ANALYSIS_ROOT / "mechanism_preflight.replay.json"
SEED = 43043
EXPECTED_HASHES = {
    "core/qd_ed.py": (
        "2246193f87a27dc8568f434e3c9933aa4cf354e770417c62e463f7c565e1247e"
    ),
    "core/rdt_policy_steer.py": (
        "5afaf8ed4fed0da04f22a7e7b9ec19c8c77b5647a1b57a8fa15963101c2c26f6"
    ),
    "core/eds_eval_metrics.py": (
        "c621c579a411ac4d4f88a38e33f86a91b60e5d6e7c8b6b424886603ff0d89049"
    ),
    "configs/config.yaml": (
        "be98e1127a93b30864c0f42832ba71adc11b115c34b1e2e0f748e2f3cb5bd55a"
    ),
}
CASE_SPECS = {
    "candidate_expanding": {
        "secondary_lane_mode": "protected_reward_v1",
        "expanding": True,
    },
    "comparator_expanding": {
        "secondary_lane_mode": "none",
        "expanding": True,
    },
    "candidate_stable": {
        "secondary_lane_mode": "protected_reward_v1",
        "expanding": False,
    },
}
QUALITY_IDENTITY_FIELDS = (
    "qd_bounds_xy_m",
    "qd_bounds_xy_m_by_iter",
    "qd_bounds_checksum_by_iter",
    "qd_bounds_expanded_by_iter",
    "qd_bounds_expansion_count",
    "qd_archive_rebin_collisions_by_iter",
    "qd_archive_rebin_visit_sum_before_by_iter",
    "qd_archive_rebin_visit_sum_after_by_iter",
    "qd_occupied_cells_by_iter",
    "qd_cumulative_cell_visits_by_iter",
    "qd_per_cell_elite_reward_by_iter",
    "qd_archive_best_reward_by_iter",
    "qd_archive_mean_elite_reward_by_iter",
    "qd_parent_slots_by_cell_by_iter",
    "qd_sparse_parent_slots_by_cell_by_iter",
    "qd_global_quality_anchor_cell_by_iter",
    "qd_global_quality_anchor_fingerprint_by_iter",
    "qd_global_quality_anchor_sparse_slot_count_by_iter",
    "qd_global_quality_anchor_rescued_by_iter",
    "qd_selected_cell",
    "qd_selected_reward",
    "qd_selected_action_fingerprint",
    "qd_global_best_action_fingerprint",
    "selected_reward",
    "selected_chunk_population_source",
)


def reset_rng() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)


def rng_checksum() -> str:
    return base.sha256_bytes(torch.random.get_rng_state().cpu().numpy().tobytes())


def make_population(*, expanding: bool, iteration: int) -> torch.Tensor:
    effective_iteration = iteration if expanding else 0
    population = base.make_population("overlap", iteration=effective_iteration)
    for row in range(int(population.shape[0])):
        population[row, :, 43] = (row + 1) / 1000.0
    return population


def qd_config(*, secondary_lane_mode: str) -> dict[str, Any]:
    config = base.qd_config(anchor_count=1)
    config["qd_secondary_lane_mode"] = secondary_lane_mode
    return config


def make_runtime(*, secondary_lane_mode: str, expanding: bool):
    from core.rdt_policy_steer import RDTSteer

    steer = RDTSteer(rdt_model=base._StubRDTModel(), num_inference_steps=5)
    steer.post_init(
        adapter=base._Adapter(),
        postprocessor=lambda value: value,
        sample_batch_size=16,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = steer._rdt_model.encode_inputs(
        torch.zeros(1, 128, dtype=torch.float64),
        torch.zeros(1, 128, dtype=torch.float64),
        [],
        torch.zeros(1, 1, 4, dtype=torch.float64),
    )
    rollout_batch_sizes: list[int] = []

    def initial_population(**kwargs):
        return make_population(expanding=expanding, iteration=0)

    def score_population(samples, **kwargs):
        rewards = samples[:, 0, 42].detach().clone()
        return -rewards, {"rewards": rewards}

    def rollout(**kwargs):
        rollout_batch_sizes.append(int(kwargs["noisy_action"].shape[0]))
        children = make_population(
            expanding=expanding,
            iteration=int(kwargs["iter_idx"]) + 1,
        )
        costs, info = score_population(children)
        return children, costs, info

    steer._eds_initial_population = initial_population
    steer._eds_score_population_as_cost = score_population
    steer._eds_renoise_reference = lambda samples, steps: samples
    steer._eds_rollout_reference = rollout
    steer._decode_visualization_action_candidates = lambda samples: samples
    config = steer._resolve_eds_config_with_reference_defaults(
        qd_config(secondary_lane_mode=secondary_lane_mode)
    )
    return steer, cond, config, rollout_batch_sizes


def secondary_artifact_evidence(artifacts: dict[str, Any]) -> dict[str, Any]:
    distinct_by_iter: list[bool] = []
    occupied_by_iter: list[int] = []
    for item in artifacts["qd_archive_by_iter"]:
        quality = {
            int(entry["cell_id"]): str(entry["fingerprint"])
            for entry in item["archive"]
        }
        secondary = item.get("secondary_archive", [])
        occupied_by_iter.append(len(secondary))
        distinct_by_iter.append(
            bool(secondary)
            and all(
                int(entry["cell_id"]) in quality
                and str(entry["fingerprint"])
                != quality[int(entry["cell_id"])]
                for entry in secondary
            )
        )
    return {
        "secondary_artifact_occupied_by_iter": occupied_by_iter,
        "secondary_artifact_distinct_by_iter": distinct_by_iter,
    }


def execute_case(*, secondary_lane_mode: str, expanding: bool) -> dict[str, Any]:
    from core.qd_ed import fingerprint_action

    reset_rng()
    start_rng = rng_checksum()
    steer, cond, config, rollout_batch_sizes = make_runtime(
        secondary_lane_mode=secondary_lane_mode,
        expanding=expanding,
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
    artifacts = steer.get_last_eds_artifacts()
    metric_fields = (
        "qd_archive_enabled",
        "qd_archive_active_for_chunk",
        "qd_degenerate_fallback_policy",
        "qd_degenerate_fallback_used",
        "qd_secondary_lane_mode",
        "qd_global_quality_anchor_count",
        "qd_global_quality_anchor_activation_count",
        "qd_secondary_occupied_cells_by_iter",
        "qd_secondary_parent_count_by_iter",
        "qd_secondary_parent_ratio_by_iter",
        "qd_secondary_parent_fingerprints_by_iter",
        "qd_secondary_parent_slots_by_cell_by_iter",
        "qd_secondary_parent_activation_count",
        "qd_secondary_rebin_discard_count_by_iter",
        "qd_secondary_rebin_discard_count",
        "qd_secondary_invariant_violation_count",
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
        *QUALITY_IDENTITY_FIELDS,
    )
    deterministic_metrics = {field: metrics.get(field) for field in metric_fields}
    return {
        "secondary_lane_mode": secondary_lane_mode,
        "expanding": expanding,
        "rollout_batch_sizes": rollout_batch_sizes,
        "selected_action_fingerprint": fingerprint_action(selected[0]),
        "start_torch_rng_sha256": start_rng,
        "terminal_torch_rng_sha256": rng_checksum(),
        "metrics": deterministic_metrics,
        **secondary_artifact_evidence(artifacts),
    }


def run_case(name: str) -> dict[str, Any]:
    return execute_case(**CASE_SPECS[name])


def complete_case_safe(case: dict[str, Any]) -> bool:
    metrics = case["metrics"]
    return (
        metrics["qd_archive_enabled"] is True
        and metrics["qd_archive_active_for_chunk"] is True
        and metrics["qd_degenerate_fallback_policy"] == "none"
        and metrics["qd_degenerate_fallback_used"] is False
        and case["rollout_batch_sizes"] == [16] * 10
        and metrics["search_evaluation_count"] == 176
        and metrics["qd_evaluation_count"] == 176
        and metrics["score_call_count"] == 11
        and metrics["nonfinite_count"] == 0
        and metrics["action_mask_violation_max"] == 0.0
        and metrics["gripper_qpos_violation_count"] == 0
        and metrics["qd_accounting_violation_count"] == 0
        and metrics["qd_elite_monotonicity_violation_count"] == 0
        and metrics["qd_secondary_invariant_violation_count"] == 0
        and metrics["qd_final_selection_mismatch_count"] == 0
        and metrics["qd_selected_action_fingerprint"]
        == metrics["qd_global_best_action_fingerprint"]
        == case["selected_action_fingerprint"]
        and metrics["qd_selected_reward"] == metrics["selected_reward"]
        and metrics["qd_archive_rebin_visit_sum_before_by_iter"]
        == metrics["qd_archive_rebin_visit_sum_after_by_iter"]
        and all(
            sum(slots.values()) == 16
            for slots in metrics["qd_parent_slots_by_cell_by_iter"]
        )
        and all(
            sum(slots.values()) == 15
            for slots in metrics["qd_sparse_parent_slots_by_cell_by_iter"]
        )
    )


def protected_case_active(case: dict[str, Any]) -> bool:
    metrics = case["metrics"]
    sources = metrics["parent_count_by_source"]
    return (
        metrics["qd_secondary_lane_mode"] == "protected_reward_v1"
        and len(metrics["qd_secondary_occupied_cells_by_iter"]) == 10
        and all(value > 0 for value in metrics["qd_secondary_occupied_cells_by_iter"])
        and len(metrics["qd_secondary_parent_count_by_iter"]) == 10
        and all(value > 0 for value in metrics["qd_secondary_parent_count_by_iter"])
        and sum(metrics["qd_secondary_parent_count_by_iter"])
        == metrics["qd_secondary_parent_activation_count"]
        and all(metrics["qd_secondary_parent_fingerprints_by_iter"])
        and all(case["secondary_artifact_distinct_by_iter"])
        and sources["qd_global_quality_anchor_offspring"] == 10
        and sources["qd_secondary_lane_offspring"] > 0
        and sources["qd_archive_offspring"]
        + sources["qd_secondary_lane_offspring"]
        == 150
    )


def comparator_inactive(case: dict[str, Any]) -> bool:
    metrics = case["metrics"]
    return (
        metrics["qd_secondary_lane_mode"] == "none"
        and metrics["qd_secondary_occupied_cells_by_iter"] == [0] * 10
        and metrics["qd_secondary_parent_count_by_iter"] == [0] * 10
        and metrics["qd_secondary_parent_activation_count"] == 0
        and metrics["qd_secondary_parent_fingerprints_by_iter"] == [[]] * 10
        and case["secondary_artifact_occupied_by_iter"] == [0] * 10
        and "qd_secondary_lane_offspring" not in metrics["parent_count_by_source"]
        and metrics["parent_count_by_source"]["qd_archive_offspring"] == 150
        and metrics["parent_count_by_source"][
            "qd_global_quality_anchor_offspring"
        ]
        == 10
    )


def quality_projection(case: dict[str, Any]) -> dict[str, Any]:
    metrics = case["metrics"]
    return {field: metrics[field] for field in QUALITY_IDENTITY_FIELDS}


def run_scientific_suite() -> dict[str, Any]:
    actual_hashes = {
        path: base.sha256_file(REPO_ROOT / path) for path in EXPECTED_HASHES
    }
    actual_base_hash = base.sha256_file(BASE_HARNESS_PATH)
    if actual_hashes != EXPECTED_HASHES or actual_base_hash != BASE_HARNESS_SHA256:
        raise RuntimeError("frozen source hash mismatch")
    if torch.cuda.is_initialized():
        raise RuntimeError("run_043 must remain CPU-only")

    cases = {name: run_case(name) for name in CASE_SPECS}
    case_replays = {name: run_case(name) for name in CASE_SPECS}
    candidate = cases["candidate_expanding"]
    comparator = cases["comparator_expanding"]
    stable = cases["candidate_stable"]
    per_case_identity = all(
        base.canonical_bytes(cases[name]) == base.canonical_bytes(case_replays[name])
        for name in CASE_SPECS
    )
    gates = {
        "identity_cpu_finite_secret": (
            actual_hashes == EXPECTED_HASHES
            and actual_base_hash == BASE_HARNESS_SHA256
            and not torch.cuda.is_initialized()
            and all(base.all_finite(case) for case in cases.values())
            and base.strict_secret_match_count(cases) == 0
        ),
        "protected_secondary_active": (
            protected_case_active(candidate) and protected_case_active(stable)
        ),
        "comparator_secondary_inactive": comparator_inactive(comparator),
        "one_plus_fifteen_and_cell_identity": (
            all(complete_case_safe(case) for case in cases.values())
            and candidate["metrics"]["qd_parent_slots_by_cell_by_iter"]
            == comparator["metrics"]["qd_parent_slots_by_cell_by_iter"]
            and candidate["metrics"]["qd_sparse_parent_slots_by_cell_by_iter"]
            == comparator["metrics"]["qd_sparse_parent_slots_by_cell_by_iter"]
        ),
        "authoritative_quality_identity": (
            quality_projection(candidate) == quality_projection(comparator)
            and len(
                candidate["metrics"]["qd_secondary_rebin_discard_count_by_iter"]
            )
            == 10
        ),
        "bounds_and_rebin_contract": (
            candidate["metrics"]["qd_bounds_expansion_count"] > 0
            and comparator["metrics"]["qd_bounds_expansion_count"] > 0
            and stable["metrics"]["qd_bounds_expansion_count"] == 0
            and stable["metrics"]["qd_bounds_expanded_by_iter"] == [False] * 10
        ),
        "compute_safety_archive_final_selection": all(
            complete_case_safe(case) for case in cases.values()
        ),
        "rng_and_per_case_replay_identity": (
            per_case_identity
            and all(
                case["start_torch_rng_sha256"]
                == case["terminal_torch_rng_sha256"]
                for case in cases.values()
            )
        ),
        "harness_sources_present": (
            Path(__file__).is_file()
            and (
                REPO_ROOT
                / "tests/test_eds_qd_protected_quality_lane_preflight.py"
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
        "occupied_descriptor_cells": 4,
        "fingerprint_distinct_candidates_per_cell": 4,
        "case_specs": CASE_SPECS,
    }
    return {
        "fixture": fixture,
        "fixture_sha256": base.canonical_sha256(fixture),
        "frozen_hashes": actual_hashes,
        "frozen_base_harness_sha256": actual_base_hash,
        "cases": cases,
        "per_case_replay_sha256": {
            name: base.canonical_sha256(case_replays[name]) for name in CASE_SPECS
        },
        "gates": gates,
        "passed": all(gates.values()),
    }


def current_revision() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def build_payload() -> dict[str, Any]:
    first = run_scientific_suite()
    second = run_scientific_suite()
    replay_identical = base.canonical_bytes(first) == base.canonical_bytes(second)
    source_hashes = {
        "scripts/eds_qd_protected_quality_lane_preflight.py": base.sha256_file(
            Path(__file__).resolve()
        ),
        "tests/test_eds_qd_protected_quality_lane_preflight.py": base.sha256_file(
            REPO_ROOT / "tests/test_eds_qd_protected_quality_lane_preflight.py"
        ),
    }
    payload = {
        "schema_version": 1,
        "experiment_id": "run_043_protected_quality_lane_cpu_mechanism",
        "hypothesis_id": "H5-v5",
        "algorithm_iteration": 5,
        "implementation_revision": current_revision(),
        "source_hashes": source_hashes,
        "scientific_payload": first,
        "scientific_payload_sha256": base.canonical_sha256(first),
        "independent_replay_sha256": base.canonical_sha256(second),
        "double_run_byte_identical": replay_identical,
        "online_episode_attempts": 0,
        "gpu_hours": 0.0,
        "credential_match_count": 0,
    }
    payload["passed"] = bool(first["passed"] and replay_identical)
    payload["credential_match_count"] = base.strict_secret_match_count(payload)
    if payload["credential_match_count"]:
        raise RuntimeError("strict credential scan failed")
    if not base.all_finite(payload):
        raise RuntimeError("nonfinite preflight payload")
    if not payload["passed"]:
        failed = [
            name for name, passed in first["gates"].items() if not passed
        ]
        raise RuntimeError(f"run_043 CPU mechanism preflight failed: {failed}")
    return payload


def write_immutable_artifacts(payload: dict[str, Any]) -> dict[str, Any]:
    encoded = base.canonical_bytes(payload)
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
        "file_sha256": base.sha256_bytes(encoded),
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
