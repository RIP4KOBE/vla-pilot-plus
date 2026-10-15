#!/usr/bin/env python3
"""CPU-only integrated preflight for the reward-degenerate QD fallback."""

from __future__ import annotations

import argparse
import hashlib
import json
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
    "run_022_reward_degenerate_mechanism_preflight"
)
ANALYSIS_ROOT = OWNED_ROOT / "analysis"
CANONICAL_PATH = ANALYSIS_ROOT / "mechanism_preflight.v1.json"
REPLAY_PATH = ANALYSIS_ROOT / "mechanism_preflight.replay.json"
SEED = 22022
EXPECTED_HASHES = {
    "core/rdt_policy_steer.py": (
        "890068dd804d38771608dbaafd5e38b70a14252f86d7e352b19fa477aca6159e"
    ),
    "core/eds_eval_metrics.py": (
        "cbe31284abf40e4d8ebc54c78b8c534f946e2e1df60f0eab8f898f77b834a450"
    ),
    "configs/config.yaml": (
        "c5844368c803f97540775365a1d5f3211997e6d77f6a0f0f581ffdf0cad63acc"
    ),
}
SECRET_PATTERNS = (
    re.compile(r"sk-poe-[A-Za-z0-9_-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(?:api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{16,}"),
)


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
    return sha256_bytes(torch.random.get_rng_state().cpu().numpy().tobytes())


def make_population(score_mode: str) -> torch.Tensor:
    population = torch.zeros(16, 64, 128, dtype=torch.float64)
    endpoint_values = torch.tensor([-0.06, -0.02, 0.02, 0.06], dtype=torch.float64)
    for index in range(16):
        population[index, :4, 39] = endpoint_values[index % 4] / 4.0
        population[index, :4, 40] = endpoint_values[index // 4] / 4.0
    if score_mode == "near_equal":
        population[-1, :, 42] = 1.0e-12
    elif score_mode == "nondegenerate":
        population[:, :, 42] = (
            torch.arange(16, dtype=torch.float64)[:, None] * 1.0e-3
        )
    return population


def qd_config(*, qd_enabled: bool, policy: str) -> dict[str, Any]:
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
        "elite_carryover_count": 0,
        "chunk_population_mode": "fresh",
        "rollout_diversity_control_mode": "fixed",
        "search_schedule_mode": "legacy_linear",
        "qd_archive_mode": "grid_archive" if qd_enabled else "none",
        "qd_degenerate_fallback_policy": policy,
        "qd_descriptor": "target_relative_endpoint_xy",
        "qd_grid_shape": [4, 4],
        "qd_cell_capacity": 1,
        "qd_parent_sampling": "sparse_priority",
        "qd_sparse_exponent": 1.0,
        "qd_bounds_quantiles": [0.05, 0.95],
        "qd_bounds_expand_fraction": 0.10,
        "qd_min_axis_span_m": 0.08,
        "qd_bounds_update_policy": "causal_envelope_v1",
        "qd_overflow_policy": "clamp_edge",
        "qd_tie_break": "stable_fingerprint",
        "qd_metrics_observer": False,
    }


def _score_rewards(samples: torch.Tensor, score_mode: str) -> torch.Tensor:
    if score_mode == "exact_zero":
        return torch.zeros(samples.shape[0], dtype=samples.dtype)
    if score_mode == "equal_negative":
        return torch.full((samples.shape[0],), -0.25, dtype=samples.dtype)
    return samples[:, 0, 42].detach().clone()


def make_runtime(*, score_mode: str, qd_enabled: bool, policy: str):
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
    state = {"score_mode": score_mode}

    def initial_population(**kwargs):
        return make_population(state["score_mode"])

    def score_population(samples, **kwargs):
        rewards = _score_rewards(samples, state["score_mode"])
        return -rewards, {"rewards": rewards}

    def rollout(**kwargs):
        children = kwargs["noisy_action"].clone()
        iteration = int(kwargs["iter_idx"]) + 1
        rows = torch.arange(children.shape[0], dtype=children.dtype)
        children[:, :4, 39] += ((rows % 4) - 1.5)[:, None] * iteration * 1.0e-4
        children[:, :4, 40] += ((rows // 4) - 1.5)[:, None] * iteration * 1.0e-4
        children[:, :, 42] = (
            (rows + 1.0)[:, None] * iteration * (2.0 ** -10)
        )
        costs, info = score_population(children)
        return children, costs, info

    steer._eds_initial_population = initial_population
    steer._eds_score_population_as_cost = score_population
    steer._eds_renoise_reference = lambda samples, steps: samples
    steer._eds_rollout_reference = rollout
    steer._decode_visualization_action_candidates = lambda samples: samples
    config = steer._resolve_eds_config_with_reference_defaults(
        qd_config(qd_enabled=qd_enabled, policy=policy)
    )
    return steer, cond, config, state


def _archive_snapshots(artifacts: dict[str, Any]) -> dict[str, Any]:
    initial = artifacts.get("qd_initial_archive") or {}
    return {
        "initial": initial.get("archive", []),
        "per_iter": [
            item.get("archive", [])
            for item in artifacts.get("qd_archive_by_iter", [])
        ],
    }


def _tensor_list(value: torch.Tensor) -> list[Any]:
    return value.detach().cpu().tolist()


def execute_chunk(steer, cond, config) -> dict[str, Any]:
    from core.qd_ed import fingerprint_action

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
    final_actions = artifacts["final_actions"]
    deterministic_metrics = {
        field: metrics.get(field)
        for field in (
            "qd_archive_enabled",
            "qd_archive_active_for_chunk",
            "qd_degenerate_fallback_policy",
            "qd_degenerate_fallback_used",
            "qd_degenerate_fallback_reason",
            "qd_degenerate_reward_value",
            "search_evaluation_count",
            "score_call_count",
            "qd_evaluation_count",
            "selected_chunk_population_source",
            "selected_idx",
            "selected_reward",
            "qd_selected_action_fingerprint",
            "qd_global_best_action_fingerprint",
            "nonfinite_count",
            "action_mask_violation_max",
            "qd_accounting_violation_count",
            "qd_elite_monotonicity_violation_count",
            "qd_final_selection_mismatch_count",
            "qd_bounds_checksum_by_iter",
            "qd_cumulative_cell_visits_by_iter",
        )
    }
    return {
        "selected_action_fingerprint": fingerprint_action(selected[0]),
        "selected_action": _tensor_list(selected),
        "final_action_fingerprints": [
            fingerprint_action(action) for action in final_actions
        ],
        "final_action_set_sha256": sha256_bytes(
            final_actions.detach().cpu().contiguous().numpy().astype("<f8").tobytes()
        ),
        "final_scores": _tensor_list(artifacts["final_scores"]),
        "archive_snapshots": _archive_snapshots(artifacts),
        "metrics": deterministic_metrics,
        "terminal_torch_rng_sha256": rng_checksum(),
    }


CASE_SPECS = {
    "candidate_exact_zero": ("exact_zero", True, "control_v1"),
    "control_exact_zero": ("exact_zero", False, "control_v1"),
    "legacy_qd_exact_zero": ("exact_zero", True, "none"),
    "candidate_equal_negative": ("equal_negative", True, "control_v1"),
    "candidate_near_equal": ("near_equal", True, "control_v1"),
    "legacy_qd_near_equal": ("near_equal", True, "none"),
    "candidate_nondegenerate": ("nondegenerate", True, "control_v1"),
    "legacy_qd_nondegenerate": ("nondegenerate", True, "none"),
}


def run_case(name: str) -> dict[str, Any]:
    score_mode, qd_enabled, policy = CASE_SPECS[name]
    reset_rng()
    steer, cond, config, _ = make_runtime(
        score_mode=score_mode,
        qd_enabled=qd_enabled,
        policy=policy,
    )
    return execute_chunk(steer, cond, config)


def sequential_state_probe() -> dict[str, Any]:
    reset_rng()
    steer, cond, config, state = make_runtime(
        score_mode="exact_zero",
        qd_enabled=True,
        policy="control_v1",
    )
    first = execute_chunk(steer, cond, config)
    state["score_mode"] = "nondegenerate"
    second = execute_chunk(steer, cond, config)
    return {
        "first_fallback_used": first["metrics"]["qd_degenerate_fallback_used"],
        "first_archive_active": first["metrics"]["qd_archive_active_for_chunk"],
        "second_fallback_used": second["metrics"]["qd_degenerate_fallback_used"],
        "second_archive_active": second["metrics"]["qd_archive_active_for_chunk"],
        "second_qd_evaluation_count": second["metrics"]["qd_evaluation_count"],
    }


def _identity(left: dict[str, Any], right: dict[str, Any], *, archive: bool) -> bool:
    fields = (
        "selected_action_fingerprint",
        "selected_action",
        "final_action_fingerprints",
        "final_action_set_sha256",
        "final_scores",
        "terminal_torch_rng_sha256",
    )
    if any(left[field] != right[field] for field in fields):
        return False
    left_metrics = left["metrics"]
    right_metrics = right["metrics"]
    if left_metrics["selected_chunk_population_source"] != right_metrics[
        "selected_chunk_population_source"
    ]:
        return False
    if archive:
        archive_fields = (
            "qd_bounds_checksum_by_iter",
            "qd_cumulative_cell_visits_by_iter",
            "search_evaluation_count",
            "score_call_count",
            "qd_evaluation_count",
            "qd_selected_action_fingerprint",
            "qd_global_best_action_fingerprint",
        )
        if any(left_metrics[field] != right_metrics[field] for field in archive_fields):
            return False
        if left["archive_snapshots"] != right["archive_snapshots"]:
            return False
    return True


def _complete_case_safe(case: dict[str, Any]) -> bool:
    metrics = case["metrics"]
    return (
        metrics["search_evaluation_count"] == 176
        and metrics["score_call_count"] == 11
        and metrics["nonfinite_count"] == 0
        and metrics["action_mask_violation_max"] == 0.0
        and metrics["qd_accounting_violation_count"] == 0
        and metrics["qd_elite_monotonicity_violation_count"] == 0
        and metrics["qd_final_selection_mismatch_count"] == 0
    )


def run_scientific_suite() -> dict[str, Any]:
    actual_hashes = {
        path: sha256_file(REPO_ROOT / path) for path in EXPECTED_HASHES
    }
    if actual_hashes != EXPECTED_HASHES:
        raise RuntimeError("frozen algorithm/config hash mismatch")
    if torch.cuda.is_initialized():
        raise RuntimeError("run_022 must remain CPU-only")

    cases = {name: run_case(name) for name in CASE_SPECS}
    sequential = sequential_state_probe()
    zero = cases["candidate_exact_zero"]
    negative = cases["candidate_equal_negative"]
    legacy_zero = cases["legacy_qd_exact_zero"]
    near = cases["candidate_near_equal"]
    nondegenerate = cases["candidate_nondegenerate"]
    gates = {
        "frozen_hashes_match": actual_hashes == EXPECTED_HASHES,
        "cpu_only": not torch.cuda.is_initialized(),
        "exact_zero_triggers": (
            zero["metrics"]["qd_degenerate_fallback_used"] is True
            and zero["metrics"]["qd_archive_active_for_chunk"] is False
            and zero["metrics"]["qd_degenerate_fallback_reason"]
            == "initial_rewards_exactly_equal"
            and zero["metrics"]["qd_degenerate_reward_value"] == 0.0
            and zero["metrics"]["qd_evaluation_count"] == 0
            and zero["metrics"]["qd_selected_action_fingerprint"] is None
        ),
        "equal_negative_triggers": (
            negative["metrics"]["qd_degenerate_fallback_used"] is True
            and negative["metrics"]["qd_archive_active_for_chunk"] is False
            and negative["metrics"]["qd_degenerate_reward_value"] == -0.25
            and negative["metrics"]["qd_evaluation_count"] == 0
        ),
        "exact_zero_matches_control": _identity(
            zero, cases["control_exact_zero"], archive=False
        ),
        "legacy_exact_zero_preserved": (
            legacy_zero["metrics"]["qd_archive_active_for_chunk"] is True
            and legacy_zero["metrics"]["qd_degenerate_fallback_used"] is False
            and legacy_zero["metrics"]["qd_evaluation_count"] == 176
            and legacy_zero["metrics"]["selected_chunk_population_source"]
            == "qd_archive"
            and legacy_zero["metrics"]["qd_selected_action_fingerprint"]
            == legacy_zero["selected_action_fingerprint"]
        ),
        "near_equal_does_not_trigger": (
            near["metrics"]["qd_degenerate_fallback_used"] is False
            and near["metrics"]["qd_archive_active_for_chunk"] is True
            and near["metrics"]["qd_evaluation_count"] == 176
        ),
        "near_equal_legacy_identity": _identity(
            near, cases["legacy_qd_near_equal"], archive=True
        ),
        "nondegenerate_legacy_identity": _identity(
            nondegenerate,
            cases["legacy_qd_nondegenerate"],
            archive=True,
        ),
        "complete_accounting_and_safety": all(
            _complete_case_safe(case) for case in cases.values()
        ),
        "no_hidden_fallback_state": sequential
        == {
            "first_fallback_used": True,
            "first_archive_active": False,
            "second_fallback_used": False,
            "second_archive_active": True,
            "second_qd_evaluation_count": 176,
        },
    }
    fixture = {
        "seed": SEED,
        "dtype": "float64",
        "population_shape": [16, 64, 128],
        "endpoint_values": [-0.06, -0.02, 0.02, 0.06],
        "rollout_batches": 10,
        "case_specs": CASE_SPECS,
    }
    return {
        "fixture": fixture,
        "fixture_sha256": canonical_sha256(fixture),
        "frozen_hashes": actual_hashes,
        "cases": cases,
        "sequential_state_probe": sequential,
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
        "scripts/eds_qd_degenerate_fallback_preflight.py": sha256_file(
            Path(__file__).resolve()
        ),
        "tests/test_eds_qd_degenerate_fallback_preflight.py": sha256_file(
            REPO_ROOT / "tests/test_eds_qd_degenerate_fallback_preflight.py"
        ),
    }
    payload = {
        "schema_version": 1,
        "experiment_id": "run_022_reward_degenerate_mechanism_preflight",
        "hypothesis_id": "H2",
        "algorithm_iteration": 2,
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
    matches = strict_secret_match_count(payload)
    payload["credential_match_count"] = matches
    if matches:
        raise RuntimeError("strict credential scan failed")
    if not payload["passed"]:
        raise RuntimeError("run_022 offline mechanism preflight failed")
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
