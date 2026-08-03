#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
import yaml
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Iterable


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))
EVIDENCE_ROOT = (
    WORKTREE_ROOT / "docs" / "03_evidence" / "eds_init_pg_diverse_sampling"
)
RUN_ROOT = WORKTREE_ROOT / "outputs" / "rdt_eds_eval"
OOD_RUN_ROOT = WORKTREE_ROOT / "outputs" / "ood_eval"
STAGE_RECOGNITION_RUN_ROOT = OOD_RUN_ROOT / "stage_recognition_ablation"
STAGE_STATUS_CSV = STAGE_RECOGNITION_RUN_ROOT / "run_manifest.csv"
STAGE_CACHED_FUNCTIONS_DIR = Path(
    "/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent"
)
P2_OUTPUT_ROOT = OOD_RUN_ROOT / "p2_adaptive_eds_rbf"
P2_EXPECTED_OUTPUT_TARGET = Path(
    "/mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/"
    "outputs/ood_eval/p2_adaptive_eds_rbf"
)
P2_ALLOWED_OUTPUT_PREFIX = Path("/mnt/data/shared2/hynx/VLA-Pilot++")
P2_MIN_FREE_BYTES = 20 * 1024**3
P2_STATUS_ROOT = P2_OUTPUT_ROOT
P2_MANIFEST_NAME = "p2_adaptive_eds_rbf_integration_manifest.json"
P2_STAGE_A_REPORT_PATH = (
    EVIDENCE_ROOT / "2026-08-02-p2-adaptive-eds-rbf-stage-a-report.md"
)
P2_PRETEST_REPORT_PATH = (
    EVIDENCE_ROOT / "2026-08-02-p2-adaptive-eds-rbf-pretest-report.md"
)
P2_LEVELS = {
    "p2_adaptive_eds_rbf_pretest",
    "p2_adaptive_eds_rbf_stage_a",
    "p2_adaptive_eds_rbf_stage_b",
}
P2_ALLOWED_GPUS = {"2", "3", "4", "5"}
P2_GPU_MEMORY_BUSY_MIB = 1024
P2_GPU_PROBE_FAILURE_LIMIT = 3
P2_CREDENTIAL_SCAN_MAX_TEXT_BYTES = 128 * 1024**2
P2_CREDENTIAL_SCAN_CHUNK_BYTES = 64 * 1024
P2_REQUIRED_MOUNT = Path("/mnt/data/shared2")
STATUS_CSV = EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
AGGRESSIVE_RBF_REPORT = "2026-07-09-aggressive-rbf-parameter-sweep.md"
ROLLOUT_RBF_REPORT = "2026-07-11-rollout-rbf-level3-parameter-sweep.md"
OBJECT_SWAP_OOD_RBF_REPORT = (
    "2026-07-12-libero-pro-object-swap-rdt-eds-rbf-report.md"
)
STAGE_RECOGNITION_REPORT = (
    "2026-07-31-libero-pro-object-swap-vlm-stage-recognition-ablation-report.md"
)


def _default_reference_level4_report() -> Path:
    requested_reference = (
        WORKTREE_ROOT.parents[1]
        / "feat"
        / "rdt_ed_steering_integration"
        / "docs"
        / "03_evidence"
        / "eds_steering"
        / "level_4_vls_pi05_libero_pro_ood.md"
    )
    if requested_reference.exists():
        return requested_reference
    return (
        WORKTREE_ROOT
        / "docs"
        / "03_evidence"
        / "eds_steering"
        / "level_4_vls_pi05_libero_pro_ood.md"
    )


REFERENCE_LEVEL4_REPORT = _default_reference_level4_report()
LIBERO_PRO_ROOT = WORKTREE_ROOT / "third_party" / "libero_pro"
LIBERO_CONFIG_PATH = WORKTREE_ROOT / ".libero_config"
BASE_SUITE = "libero_object"
OOD_SUITES = [
    "libero_object_object",
    "libero_object_swap",
    "libero_object_lan",
    "libero_object_task",
    "libero_object_env",
    "libero_object_temp",
]
REFERENCE_RENOISE = {"renoise_t_max": 5, "renoise_t_min": 1}
WEAK_RENOISE = {"renoise_t_max": 3, "renoise_t_min": 1}
METHODS = [
    {
        "method": "unguided",
        "label": "unguided",
        "population_size": "",
        "cem_iters": "",
        "use_cem": "",
        "num_elites": "",
        "temperature": "",
        "renoise_t_max": "",
        "renoise_t_min": "",
        "reward_mode": "",
    },
    {
        "method": "p16_c10",
        "label": "p16_c10",
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        **REFERENCE_RENOISE,
        "reward_mode": "normal",
    },
    {
        "method": "p16_c20",
        "label": "p16_c20",
        "population_size": 16,
        "cem_iters": 20,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        **REFERENCE_RENOISE,
        "reward_mode": "normal",
    },
    {
        "method": "p32_c10",
        "label": "p32_c10",
        "population_size": 32,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        **REFERENCE_RENOISE,
        "reward_mode": "normal",
    },
    {
        "method": "p32_c20",
        "label": "p32_c20",
        "population_size": 32,
        "cem_iters": 20,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        **REFERENCE_RENOISE,
        "reward_mode": "normal",
    },
    {
        "method": "p32_c10_cem",
        "label": "p32_c10_cem",
        "population_size": 32,
        "cem_iters": 10,
        "use_cem": True,
        "num_elites": 8,
        "temperature": 0.1,
        **REFERENCE_RENOISE,
        "reward_mode": "normal",
    },
    {
        "method": "zero",
        "label": "zero",
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        **REFERENCE_RENOISE,
        "reward_mode": "zero",
    },
    {
        "method": "shuffled",
        "label": "shuffled",
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        **REFERENCE_RENOISE,
        "reward_mode": "shuffled_keypoints",
    },
    {
        "method": "inverted",
        "label": "inverted",
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        **REFERENCE_RENOISE,
        "reward_mode": "inverted",
    },
]
RBF_DIVERSE_INITIAL_METHOD = {
    "method": "eds_rbf_diverse_initial",
    "label": "eds_rbf_diverse_initial",
    "population_size": 16,
    "cem_iters": 10,
    "use_cem": False,
    "num_elites": 32,
    "temperature": 0.1,
    **REFERENCE_RENOISE,
    "reward_mode": "normal",
    "initial_sampling_mode": "rbf_diverse_denoise",
    "initial_diversity_scale": 1.0,
    "initial_diversity_start_ratio": None,
}


def _level2_eds_sweep_method(
    label: str,
    *,
    initial_sampling_mode: str,
    initial_diversity_scale: float = 1.0,
    initial_diversity_start_ratio: float | None = None,
) -> dict[str, object]:
    return {
        "method": label,
        "label": label,
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        **REFERENCE_RENOISE,
        "reward_mode": "normal",
        "initial_sampling_mode": initial_sampling_mode,
        "initial_diversity_scale": initial_diversity_scale,
        "initial_diversity_start_ratio": initial_diversity_start_ratio,
    }


LEVEL2_METHODS = [
    _level2_eds_sweep_method("iid_baseline", initial_sampling_mode="iid"),
    _level2_eds_sweep_method(
        "rbf_s1_start_null",
        initial_sampling_mode="rbf_diverse_denoise",
    ),
    _level2_eds_sweep_method(
        "rbf_s5_start06",
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=5.0,
        initial_diversity_start_ratio=0.6,
    ),
    _level2_eds_sweep_method(
        "rbf_s10_start06",
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=10.0,
        initial_diversity_start_ratio=0.6,
    ),
    _level2_eds_sweep_method(
        "rbf_s20_start06",
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=20.0,
        initial_diversity_start_ratio=0.6,
    ),
    _level2_eds_sweep_method(
        "rbf_s5_start08",
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=5.0,
        initial_diversity_start_ratio=0.8,
    ),
    _level2_eds_sweep_method(
        "rbf_s10_start08",
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=10.0,
        initial_diversity_start_ratio=0.8,
    ),
    _level2_eds_sweep_method(
        "rbf_s20_start08",
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=20.0,
        initial_diversity_start_ratio=0.8,
    ),
]


def _start_ratio_label(start_ratio: float) -> str:
    return f"start{int(round(start_ratio * 10)):02d}"


def _value_label(value: float | int) -> str:
    value_f = float(value)
    if value_f.is_integer():
        return str(int(value_f))
    return str(value)


def _renoise_tmax_ablation_method(start_ratio: float, renoise_t_max: int) -> dict[str, object]:
    start_label = _start_ratio_label(start_ratio)
    return {
        "method": f"rbf_s20_{start_label}_rt{renoise_t_max}to1",
        "label": f"rbf_s20_{start_label}_rt{renoise_t_max}to1",
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        "renoise_t_max": renoise_t_max,
        "renoise_t_min": 1,
        "reward_mode": "normal",
        "initial_sampling_mode": "rbf_diverse_denoise",
        "initial_diversity_scale": 20.0,
        "initial_diversity_start_ratio": start_ratio,
        "save_mechanism_trace_to_qualitative": True,
    }


RENOISE_TMAX_ABLATION_METHODS = [
    _renoise_tmax_ablation_method(0.6, 4),
    _renoise_tmax_ablation_method(0.6, 3),
    _renoise_tmax_ablation_method(0.6, 2),
    _renoise_tmax_ablation_method(0.8, 4),
    _renoise_tmax_ablation_method(0.8, 3),
    _renoise_tmax_ablation_method(0.8, 2),
]


def _rollout_iters_label(rollout_diversity_iters: int | str) -> str:
    return "all" if rollout_diversity_iters == "all" else str(rollout_diversity_iters)


def _rollout_rbf_ablation_method(
    renoise_t_max: int,
    rollout_diversity_scale: float,
    rollout_diversity_start_ratio: float,
    rollout_diversity_iters: int | str,
) -> dict[str, object]:
    rollout_scale_label = _value_label(rollout_diversity_scale)
    rollout_start_label = _start_ratio_label(rollout_diversity_start_ratio)
    rollout_iters_label = _rollout_iters_label(rollout_diversity_iters)
    label = (
        f"rbf_s20_start08_rt{renoise_t_max}to1_rollrbf_s{rollout_scale_label}_"
        f"{rollout_start_label}_iter{rollout_iters_label}"
    )
    return {
        "method": label,
        "label": label,
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 16,
        "temperature": 0.1,
        "renoise_t_max": renoise_t_max,
        "renoise_t_min": 1,
        "reward_mode": "normal",
        "initial_sampling_mode": "rbf_diverse_denoise",
        "initial_diversity_scale": 20.0,
        "initial_diversity_start_ratio": 0.8,
        "truncated_rollout_mode": "rbf_diverse",
        "rollout_diversity_scale": float(rollout_diversity_scale),
        "rollout_diversity_start_ratio": rollout_diversity_start_ratio,
        "rollout_diversity_iters": rollout_diversity_iters,
        "rollout_diversity_skip_final_steps": 0,
        "save_mechanism_trace_to_qualitative": True,
    }


ROLLOUT_RBF_ABLATION_METHODS = [
    _rollout_rbf_ablation_method(
        renoise_t_max,
        rollout_diversity_scale,
        rollout_diversity_start_ratio,
        rollout_diversity_iters,
    )
    for renoise_t_max in [4, 3, 2, 1]
    for rollout_diversity_scale in [5, 10, 15, 20]
    for rollout_diversity_start_ratio in [0.6, 0.8]
    for rollout_diversity_iters in [1, 3, 6, "all"]
]


OBJECT_SWAP_OOD_RBF_INIT_METHOD = {
    "method": "eds_rbf_init_s20_start08",
    "label": "eds_rbf_init_s20_start08",
    "population_size": 16,
    "cem_iters": 10,
    "use_cem": False,
    "num_elites": 16,
    "temperature": 0.1,
    "renoise_t_max": 1,
    "renoise_t_min": 1,
    "reward_mode": "normal",
    "initial_sampling_mode": "rbf_diverse_denoise",
    "initial_diversity_scale": 20.0,
    "initial_diversity_start_ratio": 0.8,
    "truncated_rollout_mode": "baseline",
    "save_mechanism_trace_to_qualitative": True,
}
OBJECT_SWAP_OOD_RBF_METHODS = [
    OBJECT_SWAP_OOD_RBF_INIT_METHOD,
    *[
        _rollout_rbf_ablation_method(
            renoise_t_max,
            rollout_diversity_scale,
            rollout_diversity_start_ratio,
            rollout_diversity_iters,
        )
        for renoise_t_max in [4, 3, 2, 1]
        for rollout_diversity_scale in [5, 10, 15, 20]
        for rollout_diversity_start_ratio in [0.2, 0.4, 0.6, 0.8]
        for rollout_diversity_iters in [1, 3, 6, "all"]
    ],
]


P2_BASE_PROFILE = {
    "population_size": 16,
    "cem_iters": 10,
    "use_cem": False,
    "num_elites": 16,
    "temperature": 0.1,
    "renoise_t_max": 3,
    "renoise_t_min": 1,
    "reward_mode": "normal",
    "initial_sampling_mode": "rbf_diverse_denoise",
    "initial_diversity_scale": 20.0,
    "initial_diversity_start_ratio": 0.8,
    "truncated_rollout_mode": "rbf_diverse",
    "rollout_diversity_scale": 20.0,
    "rollout_diversity_start_ratio": 0.6,
    "rollout_diversity_iters": "all",
    "rollout_diversity_skip_final_steps": 0,
    "parent_weighting_mode": "legacy_temperature",
    "selection_ess_target_ratio": 0.6,
    "selection_beta_max": 100.0,
    "selection_bisection_steps": 24,
    "parent_coverage_mode": "none",
    "parent_anchor_count": 0,
    "parent_anchor_reward_quantile": 0.5,
    "elite_carryover_count": 0,
    "rollout_diversity_control_mode": "fixed",
    "rollout_diversity_target_ratio": 1.0,
    "rollout_diversity_band_ratio": 0.2,
    "rollout_diversity_scale_min": 0.0,
    "rollout_diversity_scale_max": 20.0,
    "rollout_diversity_decay_floor": 0.25,
    "chunk_population_mode": "fresh",
    "chunk_memory_fraction": 0.0,
    "chunk_memory_renoise_steps": 2,
    "chunk_memory_reward_guard_quantile": 0.25,
    "search_schedule_mode": "legacy_linear",
    "adaptive_min_cem_iters": 4,
    "adaptive_early_stop_patience": 2,
    "adaptive_reward_improvement_eps": 1e-3,
    "execution_horizon_mode": "fixed",
    "execution_horizon_far": 8,
    "execution_horizon_near": 4,
    "execution_horizon_contact": 2,
    "execution_near_distance": 0.08,
    "execution_contact_distance": 0.04,
    "max_episode_steps": 720,
    "stage_recognition_enabled": True,
    "gemini_grounding_enabled": False,
    "seed": 0,
    "save_mechanism_trace_to_qualitative": True,
}


def _p2_profile(label: str, **overrides: object) -> dict[str, object]:
    return {
        **P2_BASE_PROFILE,
        "method": label,
        "label": label,
        **overrides,
    }


P2_STAGE_A_METHODS = [
    _p2_profile("p2_legacy_stage_on_rerun"),
    _p2_profile(
        "p2_sel_ess05",
        parent_weighting_mode="adaptive_ess",
        selection_ess_target_ratio=0.5,
    ),
    _p2_profile(
        "p2_sel_ess07",
        parent_weighting_mode="adaptive_ess",
        selection_ess_target_ratio=0.7,
    ),
    _p2_profile(
        "p2_adaptrbf_t08_s10",
        rollout_diversity_control_mode="adaptive_band",
        rollout_diversity_target_ratio=0.8,
        rollout_diversity_scale_max=10.0,
    ),
    _p2_profile(
        "p2_adaptrbf_t10_s20",
        rollout_diversity_control_mode="adaptive_band",
    ),
    _p2_profile(
        "p2_divres_k2_e1",
        parent_coverage_mode="eef_kcenter",
        parent_anchor_count=2,
        elite_carryover_count=1,
    ),
    _p2_profile(
        "p2_divres_k4_e2",
        parent_coverage_mode="eef_kcenter",
        parent_anchor_count=4,
        elite_carryover_count=2,
    ),
    _p2_profile(
        "p2_memory25",
        chunk_population_mode="warm_start_mix",
        chunk_memory_fraction=0.25,
    ),
    _p2_profile(
        "p2_memory50",
        chunk_population_mode="warm_start_mix",
        chunk_memory_fraction=0.5,
    ),
    _p2_profile(
        "p2_schedule_balanced",
        search_schedule_mode="adaptive",
        execution_horizon_mode="adaptive_prefix",
        execution_horizon_contact=4,
    ),
    _p2_profile(
        "p2_schedule_contact",
        search_schedule_mode="adaptive",
        execution_horizon_mode="adaptive_prefix",
    ),
]
P2_STAGE_A_LABELS = tuple(method["label"] for method in P2_STAGE_A_METHODS)
_P2_PRETEST_LABELS = (
    "p2_legacy_stage_on_rerun",
    "p2_sel_ess05",
    "p2_adaptrbf_t10_s20",
    "p2_divres_k4_e2",
    "p2_memory25",
    "p2_schedule_contact",
)
P2_PRETEST_METHODS = [
    {**method, "task_ids_filter": [0, 8]}
    for label in _P2_PRETEST_LABELS
    for method in P2_STAGE_A_METHODS
    if method["label"] == label
]


P2_MANIFEST_OVERRIDE_KEYS = {
    "main.eds_config.parent_weighting_mode": "parent_weighting_mode",
    "main.eds_config.selection_ess_target_ratio": "selection_ess_target_ratio",
    "main.eds_config.selection_beta_max": "selection_beta_max",
    "main.eds_config.selection_bisection_steps": "selection_bisection_steps",
    "main.eds_config.parent_coverage_mode": "parent_coverage_mode",
    "main.eds_config.parent_anchor_count": "parent_anchor_count",
    "main.eds_config.parent_anchor_reward_quantile": "parent_anchor_reward_quantile",
    "main.eds_config.elite_carryover_count": "elite_carryover_count",
    "main.eds_config.rollout_diversity_control_mode": "rollout_diversity_control_mode",
    "main.eds_config.rollout_diversity_target_ratio": "rollout_diversity_target_ratio",
    "main.eds_config.rollout_diversity_band_ratio": "rollout_diversity_band_ratio",
    "main.eds_config.rollout_diversity_scale_min": "rollout_diversity_scale_min",
    "main.eds_config.rollout_diversity_scale_max": "rollout_diversity_scale_max",
    "main.eds_config.rollout_diversity_decay_floor": "rollout_diversity_decay_floor",
    "main.eds_config.chunk_population_mode": "chunk_population_mode",
    "main.eds_config.chunk_memory_fraction": "chunk_memory_fraction",
    "main.eds_config.chunk_memory_renoise_steps": "chunk_memory_renoise_steps",
    "main.eds_config.chunk_memory_reward_guard_quantile": "chunk_memory_reward_guard_quantile",
    "main.eds_config.search_schedule_mode": "search_schedule_mode",
    "main.eds_config.adaptive_min_cem_iters": "adaptive_min_cem_iters",
    "main.eds_config.adaptive_early_stop_patience": "adaptive_early_stop_patience",
    "main.eds_config.adaptive_reward_improvement_eps": "adaptive_reward_improvement_eps",
    "main.execution_horizon_mode": "execution_horizon_mode",
    "main.execution_horizon_far": "execution_horizon_far",
    "main.execution_horizon_near": "execution_horizon_near",
    "main.execution_horizon_contact": "execution_horizon_contact",
    "main.execution_near_distance": "execution_near_distance",
    "main.execution_contact_distance": "execution_contact_distance",
}
P2_INTEGRATION_LABELS = {"p2_integrated_full", "p2_integrated_minimal"}
P2_EDS_CONFIG_FIELDS = (
    "parent_weighting_mode",
    "selection_ess_target_ratio",
    "selection_beta_max",
    "selection_bisection_steps",
    "parent_coverage_mode",
    "parent_anchor_count",
    "parent_anchor_reward_quantile",
    "elite_carryover_count",
    "rollout_diversity_control_mode",
    "rollout_diversity_target_ratio",
    "rollout_diversity_band_ratio",
    "rollout_diversity_scale_min",
    "rollout_diversity_scale_max",
    "rollout_diversity_decay_floor",
    "chunk_population_mode",
    "chunk_memory_fraction",
    "chunk_memory_renoise_steps",
    "chunk_memory_reward_guard_quantile",
    "search_schedule_mode",
    "adaptive_min_cem_iters",
    "adaptive_early_stop_patience",
    "adaptive_reward_improvement_eps",
)
P2_MAIN_EXECUTION_FIELDS = (
    "execution_horizon_mode",
    "execution_horizon_far",
    "execution_horizon_near",
    "execution_horizon_contact",
    "execution_near_distance",
    "execution_contact_distance",
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _canonical_manifest_sha256(manifest: dict[str, object]) -> str:
    canonical = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return hashlib.sha256(_canonical_json(canonical).encode("utf-8")).hexdigest()


def _default_p2_manifest_path() -> Path:
    return EVIDENCE_ROOT / P2_MANIFEST_NAME


def _contains_secret_text(value: object) -> bool:
    text = _canonical_json(value)
    return (
        "sk-poe-" in text
        or "OPENAI_API_KEY" in text
        or "GOOGLE_API_KEY" in text
        or _p2_text_has_credential(text, _p2_runtime_secret_values())
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"cannot hash required file {path}: {exc}") from exc
    return digest.hexdigest()


def _p2_stage_a_job(label: str) -> dict[str, object]:
    try:
        method = next(item for item in P2_STAGE_A_METHODS if item["label"] == label)
    except StopIteration as exc:
        raise ValueError(f"P2 integration source is not a Stage A label: {label!r}") from exc
    job = {
        **method,
        "job_id": f"p2_adaptive_eds_rbf_stage_a_libero_object_swap_{label}",
        "level": "p2_adaptive_eds_rbf_stage_a",
        "suite": "libero_object_swap",
        "episodes": 10,
    }
    return _bind_p2_execution_context(job)


def _p2_stage_a_profile_diff(label: str) -> dict[str, object]:
    source = _p2_stage_a_job(label)
    result: dict[str, object] = {}
    for hydra_key, field in P2_MANIFEST_OVERRIDE_KEYS.items():
        if source[field] != P2_BASE_PROFILE[field]:
            result[hydra_key] = source[field]
    return result


def _p2_episode_outcomes(output_dir: Path, episodes: int) -> dict[int, str]:
    outcomes: dict[int, str] = {}
    for episode in range(episodes):
        videos = list((output_dir / f"episode_{episode + 1}").glob("*.mp4"))
        if any("_success_" in path.name for path in videos):
            outcomes[episode] = "success"
        elif any("_fail_" in path.name for path in videos):
            outcomes[episode] = "fail"
        else:
            outcomes[episode] = "unknown"
    return outcomes


def _finite_median(values: Iterable[object]) -> float | None:
    finite = sorted(
        float(value)
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
    if not finite:
        return None
    middle = len(finite) // 2
    if len(finite) % 2:
        return finite[middle]
    return (finite[middle - 1] + finite[middle]) / 2.0


def _p2_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return int(value)


def _p2_finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _p2_actual_stage_a_evidence(label: str) -> dict[str, object]:
    job = _p2_stage_a_job(label)
    validity = _p2_job_validity(job)
    output_dir = _output_dir(job)
    parsed = _parse_results_file(output_dir / "results.txt")
    metrics = _read_jsonl(output_dir / "eds_eval" / "eds_metrics.jsonl")
    return {
        "job": job,
        "valid": validity["valid"],
        "failure_reason": validity["failure_reason"],
        "success_count": parsed.get("success"),
        "success_rate": parsed.get("success_rate"),
        "metrics": metrics,
        "median_latency_s": _finite_median(
            record.get("select_action_latency_s") for record in metrics
        ),
        "outcomes": _p2_episode_outcomes(output_dir, 10),
    }


def _p2_equal_sr_mechanism_gate(
    label: str,
    source: dict[str, object],
    baseline: dict[str, object],
) -> bool:
    if not isinstance(source, dict) or not isinstance(baseline, dict):
        return False
    source_latency = source.get("median_latency_s")
    baseline_latency = baseline.get("median_latency_s")
    if not (
        isinstance(source_latency, (int, float))
        and isinstance(baseline_latency, (int, float))
        and math.isfinite(float(source_latency))
        and math.isfinite(float(baseline_latency))
        and float(source_latency) <= 1.5 * float(baseline_latency)
    ):
        return False
    source_outcomes = source.get("outcomes")
    baseline_outcomes = baseline.get("outcomes")
    metrics = source.get("metrics")
    source_job = source.get("job")
    if (
        not isinstance(source_outcomes, dict)
        or not isinstance(baseline_outcomes, dict)
        or not isinstance(metrics, list)
        or any(not isinstance(record, dict) for record in metrics)
        or not isinstance(source_job, dict)
    ):
        return False
    if any(
        source_outcomes.get(task) not in {"success", "fail", "unknown"}
        or baseline_outcomes.get(task) not in {"success", "fail", "unknown"}
        for task in range(10)
    ):
        return False
    if any(
        baseline_outcomes.get(task) == "success"
        and source_outcomes.get(task) != "success"
        for task in range(10)
    ):
        return False
    if label.startswith("p2_sel_ess"):
        target = _p2_finite_number(source_job.get("selection_ess_target_ratio"))
        if target is None:
            return False
        raw_values = [record.get("selection_ess_ratio_mean") for record in metrics]
        if any(value is not None and _p2_finite_number(value) is None for value in raw_values):
            return False
        error = _finite_median(
            abs(float(value) - target)
            for value in raw_values
            if _p2_finite_number(value) is not None
        )
        return error is not None and error <= 0.1
    if label.startswith("p2_adaptrbf"):
        raw_scales = [record.get("adaptive_rbf_scale_applied_mean") for record in metrics]
        if any(value is not None and _p2_finite_number(value) is None for value in raw_scales):
            return False
        scales = {
            number
            for value in raw_scales
            if (number := _p2_finite_number(value)) is not None
        }
        return len(scales) >= 2
    if label.startswith("p2_divres"):
        return any(
            (_p2_nonnegative_int(record.get("anchor_count_observed")) or 0) > 0
            and (
                _p2_nonnegative_int(record.get("elite_carryover_count_observed"))
                or 0
            )
            > 0
            for record in metrics
        )
    if label.startswith("p2_memory"):
        return any(record.get("chunk_memory_used") is True for record in metrics)
    if label.startswith("p2_schedule"):
        renoise: list[int] = []
        horizons: list[int] = []
        for record in metrics:
            per_iter = record.get("per_iter")
            if not isinstance(per_iter, list) or any(
                not isinstance(item, dict) for item in per_iter
            ):
                return False
            for item in per_iter:
                value = item.get("n_trunc_steps")
                parsed = _p2_nonnegative_int(value)
                if parsed is None:
                    return False
                renoise.append(parsed)
            horizon = _p2_nonnegative_int(record.get("execution_horizon_resolved"))
            if horizon is None:
                return False
            horizons.append(horizon)
        return len(set(renoise)) >= 2 or len(set(horizons)) >= 2
    return False


def _p2_stage_a_evidence_common_schema_valid(evidence: object) -> bool:
    if not isinstance(evidence, dict):
        return False
    latency = _p2_finite_number(evidence.get("median_latency_s"))
    outcomes = evidence.get("outcomes")
    metrics = evidence.get("metrics")
    job = evidence.get("job")
    return bool(
        latency is not None
        and isinstance(outcomes, dict)
        and all(
            outcomes.get(task) in {"success", "fail", "unknown"}
            for task in range(10)
        )
        and isinstance(metrics, list)
        and all(isinstance(record, dict) for record in metrics)
        and isinstance(job, dict)
    )


def _p2_stage_a_component_schema_valid(
    label: str, evidence: dict[str, object]
) -> bool:
    metrics = evidence["metrics"]
    job = evidence["job"]
    if label.startswith("p2_sel_ess"):
        if _p2_finite_number(job.get("selection_ess_target_ratio")) is None:
            return False
        values = [record.get("selection_ess_ratio_mean") for record in metrics]
        return bool(values) and all(
            value is None or _p2_finite_number(value) is not None for value in values
        ) and any(_p2_finite_number(value) is not None for value in values)
    if label.startswith("p2_adaptrbf"):
        values = [record.get("adaptive_rbf_scale_applied_mean") for record in metrics]
        return bool(values) and all(
            value is None or _p2_finite_number(value) is not None for value in values
        ) and any(_p2_finite_number(value) is not None for value in values)
    if label.startswith("p2_divres"):
        return bool(metrics) and all(
            _p2_nonnegative_int(record.get("anchor_count_observed")) is not None
            and _p2_nonnegative_int(record.get("elite_carryover_count_observed"))
            is not None
            for record in metrics
        )
    if label.startswith("p2_memory"):
        return bool(metrics) and all(
            isinstance(record.get("chunk_memory_used"), bool) for record in metrics
        )
    if label.startswith("p2_schedule"):
        for record in metrics:
            per_iter = record.get("per_iter")
            if not isinstance(per_iter, list) or any(
                not isinstance(item, dict)
                or _p2_nonnegative_int(item.get("n_trunc_steps")) is None
                for item in per_iter
            ):
                return False
            if _p2_nonnegative_int(record.get("execution_horizon_resolved")) is None:
                return False
        return bool(metrics)
    return False


def _p2_source_is_actually_eligible(
    label: str,
    source: dict[str, object],
    baseline: dict[str, object],
) -> bool:
    if not isinstance(source, dict) or not isinstance(baseline, dict):
        return False
    if source.get("valid") is not True or baseline.get("valid") is not True:
        return False
    if not _p2_stage_a_evidence_common_schema_valid(
        source
    ) or not _p2_stage_a_evidence_common_schema_valid(baseline):
        return False
    if not _p2_stage_a_component_schema_valid(label, source):
        return False
    source_success = source.get("success_count")
    baseline_success = baseline.get("success_count")
    if (
        not isinstance(source_success, int)
        or isinstance(source_success, bool)
        or not isinstance(baseline_success, int)
        or isinstance(baseline_success, bool)
        or not 0 <= source_success <= 10
        or not 0 <= baseline_success <= 10
    ):
        return False
    if source_success > baseline_success:
        return True
    if source_success == baseline_success:
        return _p2_equal_sr_mechanism_gate(label, source, baseline)
    return False


def _load_p2_integration_manifest(path: str | Path | None) -> dict[str, object]:
    manifest_path = Path(path) if path is not None else _default_p2_manifest_path()
    if not manifest_path.is_file():
        raise ValueError(f"P2 integration manifest missing: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"P2 integration manifest is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("P2 integration manifest must be a JSON object")
    required = {
        "schema_version",
        "created_at",
        "git_revision",
        "code_state_sha256",
        "stage_a_report_sha256",
        "manifest_sha256",
        "profiles",
    }
    if set(payload) != required:
        raise ValueError(
            "P2 integration manifest schema fields mismatch: "
            + ",".join(sorted(set(payload) ^ required))
        )
    if payload["schema_version"] != 1:
        raise ValueError("P2 integration manifest schema_version must be 1")
    if not isinstance(payload["created_at"], str):
        raise ValueError("P2 integration manifest created_at must be a string")
    try:
        created_at = dt.datetime.fromisoformat(payload["created_at"])
    except ValueError as exc:
        raise ValueError("P2 integration manifest created_at is invalid") from exc
    if created_at.tzinfo is None:
        raise ValueError("P2 integration manifest created_at must include timezone")
    for field in ("git_revision", "code_state_sha256", "stage_a_report_sha256"):
        expected_length = 40 if field == "git_revision" else 64
        if not re.fullmatch(rf"[0-9a-f]{{{expected_length}}}", str(payload[field])):
            raise ValueError(f"P2 integration manifest {field} is invalid")
    expected_hash = _canonical_manifest_sha256(payload)
    if payload["manifest_sha256"] != expected_hash:
        raise ValueError("P2 integration manifest hash mismatch")
    if _contains_secret_text(payload):
        raise ValueError("P2 integration manifest contains credential material")
    if payload["git_revision"] != _git_head_revision():
        raise ValueError("P2 integration manifest git_revision does not match current HEAD")
    if payload["code_state_sha256"] != _p2_code_state_sha256():
        raise ValueError("P2 integration manifest code state does not match current files")
    if not P2_STAGE_A_REPORT_PATH.is_file():
        raise ValueError(f"P2 Stage A report missing: {P2_STAGE_A_REPORT_PATH}")
    if payload["stage_a_report_sha256"] != _sha256_file(P2_STAGE_A_REPORT_PATH):
        raise ValueError("P2 integration manifest Stage A report hash mismatch")
    profiles = payload["profiles"]
    if not isinstance(profiles, list):
        raise ValueError("P2 integration manifest profiles must be a list")
    if len(profiles) > 2:
        raise ValueError("P2 integration manifest supports at most 2 profiles")
    baseline = _p2_actual_stage_a_evidence("p2_legacy_stage_on_rerun") if profiles else None
    if baseline is not None and baseline["valid"] is not True:
        raise ValueError(
            "actual Stage A baseline is invalid: " + str(baseline["failure_reason"])
        )
    labels: list[str] = []
    for profile in profiles:
        if not isinstance(profile, dict):
            raise ValueError("P2 integration manifest profile must be an object")
        label = profile.get("label")
        if label not in P2_INTEGRATION_LABELS:
            raise ValueError(f"P2 integration profile label is invalid: {label!r}")
        labels.append(str(label))
        status = profile.get("status")
        if status not in {"active", "not_eligible"}:
            raise ValueError(f"P2 integration profile {label} has invalid status")
        if status == "not_eligible":
            if set(profile) != {"label", "status", "selection_reason"}:
                raise ValueError(f"P2 integration profile {label} not_eligible schema invalid")
            if not isinstance(profile.get("selection_reason"), str) or not profile["selection_reason"].strip():
                raise ValueError(f"P2 integration profile {label} selection_reason invalid")
            continue
        if set(profile) != {
            "label", "status", "overrides", "source_stage_a_jobs", "selection_reason"
        }:
            raise ValueError(f"P2 integration profile {label} active schema invalid")
        if not isinstance(profile.get("selection_reason"), str) or not profile["selection_reason"].strip():
            raise ValueError(f"P2 integration profile {label} selection_reason invalid")
        overrides = profile.get("overrides")
        if not isinstance(overrides, dict) or not overrides:
            raise ValueError(f"P2 integration profile {label} requires overrides")
        unknown = set(overrides) - set(P2_MANIFEST_OVERRIDE_KEYS)
        if unknown:
            raise ValueError("P2 integration manifest has unknown override keys: " + ",".join(sorted(unknown)))
        sources = profile.get("source_stage_a_jobs")
        if not isinstance(sources, list) or not sources:
            raise ValueError(f"P2 integration profile {label} requires eligible sources")
        combined_overrides: dict[str, object] = {}
        source_labels: set[str] = set()
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError("P2 integration eligible source must be an object")
            if set(source) != {
                "label", "valid", "eligible", "success_count", "success_rate", "selection_reason"
            }:
                raise ValueError("P2 integration eligible source schema invalid")
            if source.get("label") not in P2_STAGE_A_LABELS:
                raise ValueError(f"P2 integration source is not a Stage A label: {source.get('label')!r}")
            if source.get("valid") is not True or source.get("eligible") is not True:
                raise ValueError(f"P2 integration profile {label} has an ineligible source")
            source_label = str(source["label"])
            if source_label == "p2_legacy_stage_on_rerun" or source_label in source_labels:
                raise ValueError(f"P2 integration profile {label} has invalid duplicate/baseline source")
            source_labels.add(source_label)
            if (
                not isinstance(source.get("success_count"), int)
                or isinstance(source.get("success_count"), bool)
                or not 0 <= int(source["success_count"]) <= 10
                or not isinstance(source.get("success_rate"), (int, float))
                or isinstance(source.get("success_rate"), bool)
                or not math.isfinite(float(source["success_rate"]))
                or not 0.0 <= float(source["success_rate"]) <= 100.0
                or not isinstance(source.get("selection_reason"), str)
                or not source["selection_reason"].strip()
            ):
                raise ValueError("P2 integration eligible source type/range invalid")
            actual = _p2_actual_stage_a_evidence(source_label)
            if actual["valid"] is not True:
                raise ValueError(
                    f"actual Stage A source {source_label} is invalid: {actual['failure_reason']}"
                )
            if (
                source["success_count"] != actual["success_count"]
                or abs(float(source["success_rate"]) - float(actual["success_rate"])) > 0.02
            ):
                raise ValueError(f"P2 integration source {source_label} evidence mismatch")
            if not _p2_source_is_actually_eligible(source_label, actual, baseline):
                raise ValueError(f"actual Stage A source {source_label} is not eligible")
            for key, value in _p2_stage_a_profile_diff(source_label).items():
                if key in combined_overrides and combined_overrides[key] != value:
                    raise ValueError(f"P2 integration sources have conflicting override {key}")
                combined_overrides[key] = value
        if _canonical_json(overrides) != _canonical_json(combined_overrides):
            raise ValueError(
                f"P2 integration profile {label} overrides do not equal exact Stage A source diff"
            )
    if len(labels) != len(set(labels)):
        raise ValueError("P2 integration profile labels must be unique")
    return {**payload, "manifest_path": str(manifest_path.resolve())}


def _git_head_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    revision = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("unable to resolve current git HEAD for P2 execution")
    return revision


def _p2_relevant_code_paths(root: Path) -> list[Path]:
    excluded_parts = {"docs", "tests", "outputs", ".git", "__pycache__"}
    suffixes = {".py", ".yaml", ".yml"}
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode == 0:
        candidates = [root / line for line in result.stdout.splitlines() if line]
    else:
        candidates = list(root.rglob("*"))
    return sorted(
        path
        for path in candidates
        if path.is_file()
        and path.suffix.lower() in suffixes
        and not excluded_parts.intersection(path.relative_to(root).parts)
    )


def _p2_code_state_sha256(
    *,
    root: Path | None = None,
    head_revision: str | None = None,
) -> str:
    source_root = Path(root or WORKTREE_ROOT).resolve(strict=True)
    digest = hashlib.sha256()
    revision = head_revision or _git_head_revision()
    digest.update(b"HEAD\0")
    digest.update(revision.encode("ascii"))
    digest.update(b"\0")
    paths = _p2_relevant_code_paths(source_root)
    if not paths:
        raise RuntimeError(f"P2 code-state source set is empty: {source_root}")
    for path in paths:
        relative = path.relative_to(source_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _default_p2_real_root() -> Path:
    return P2_OUTPUT_ROOT.resolve(strict=False)


def _p2_execution_record(
    job: dict[str, object],
    *,
    real_root: Path | None = None,
    cached_functions_dir: str | None = None,
    offline_vlm: bool | None = None,
    git_revision: str | None = None,
    code_state_sha256: str | None = None,
) -> dict[str, object]:
    root = Path(
        real_root
        if real_root is not None
        else job.get("p2_output_real_root", _default_p2_real_root())
    ).resolve(strict=False)
    cache_dir = str(
        cached_functions_dir
        if cached_functions_dir is not None
        else job.get("p2_cached_functions_dir", STAGE_CACHED_FUNCTIONS_DIR)
    )
    effective_offline = bool(
        job.get("p2_offline_vlm", False) if offline_vlm is None else offline_vlm
    )
    command = build_main_command(
        job,
        gpu="2",
        timeout_seconds=1,
        cached_functions_dir=cache_dir,
        offline_vlm=effective_offline,
    )
    ignored = {
        "config_fingerprint",
        "execution_record",
        "manifest_path",
        "p2_storage_enforced",
    }
    record = {
        "schema": "p2-adaptive-eds-rbf-execution-v2",
        "normalized_command": command,
        "cached_functions_dir": cache_dir,
        "offline_vlm": effective_offline,
        "git_revision": git_revision or _git_head_revision(),
        "code_state_sha256": code_state_sha256 or _p2_code_state_sha256(),
        "manifest_sha256": job.get("manifest_sha256"),
        "output_real_root": str(root),
        "job_semantics": {
            key: value for key, value in job.items() if key not in ignored
        },
    }
    if _contains_secret_text(record):
        raise ValueError("P2 execution record contains credential material")
    return record


def _p2_fingerprint_from_record(record: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()


def _bind_p2_execution_context(
    job: dict[str, object],
    *,
    real_root: Path | None = None,
    cached_functions_dir: str | None = None,
    offline_vlm: bool = False,
    storage_enforced: bool = False,
    git_revision: str | None = None,
    code_state_sha256: str | None = None,
) -> dict[str, object]:
    if job.get("level") not in P2_LEVELS:
        return job
    root = Path(real_root if real_root is not None else _default_p2_real_root()).resolve(
        strict=False
    )
    cache_dir = str(cached_functions_dir or STAGE_CACHED_FUNCTIONS_DIR)
    job["p2_output_real_root"] = str(root)
    job["p2_cached_functions_dir"] = cache_dir
    job["p2_offline_vlm"] = bool(offline_vlm)
    job["p2_storage_enforced"] = bool(storage_enforced)
    record = _p2_execution_record(
        job,
        real_root=root,
        cached_functions_dir=cache_dir,
        offline_vlm=offline_vlm,
        git_revision=git_revision,
        code_state_sha256=code_state_sha256,
    )
    job["execution_record"] = record
    job["config_fingerprint"] = _p2_fingerprint_from_record(record)
    return job


def _p2_config_fingerprint(job: dict[str, object]) -> str:
    record = _p2_execution_record(job)
    return _p2_fingerprint_from_record(record)


def _nearest_mountpoint(path: Path) -> Path:
    candidate = path.resolve(strict=True)
    while not os.path.ismount(candidate):
        if candidate.parent == candidate:
            break
        candidate = candidate.parent
    return candidate


def _path_device(path: Path) -> int:
    return int(path.stat().st_dev)


def _validate_p2_output_storage(
    *,
    link_path: Path | None = None,
    expected_target: Path | None = None,
    allowed_prefix: Path | None = None,
    min_free_bytes: int = P2_MIN_FREE_BYTES,
    disk_usage_fn=shutil.disk_usage,
    writable_fn=os.access,
    device_fn=_path_device,
    mountpoint_fn=_nearest_mountpoint,
    required_mount: Path = P2_REQUIRED_MOUNT,
    comparison_paths: Iterable[Path] | None = None,
) -> Path:
    link = Path(link_path) if link_path is not None else P2_OUTPUT_ROOT
    expected = Path(expected_target) if expected_target is not None else P2_EXPECTED_OUTPUT_TARGET
    prefix = Path(allowed_prefix) if allowed_prefix is not None else P2_ALLOWED_OUTPUT_PREFIX
    if not link.is_symlink():
        raise RuntimeError(f"P2 output path must be a symlink: {link}")
    try:
        resolved = link.resolve(strict=True)
        expected_resolved = expected.resolve(strict=True)
        prefix_resolved = prefix.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"P2 output symlink is dangling or invalid: {link}: {exc}") from exc
    if resolved != expected_resolved:
        raise RuntimeError(f"P2 output target mismatch: {resolved} != {expected_resolved}")
    try:
        resolved.relative_to(prefix_resolved)
    except ValueError as exc:
        raise RuntimeError(f"P2 output target is outside allowed shared2 prefix: {resolved}") from exc
    if not resolved.is_dir():
        raise RuntimeError(f"P2 output target is not a directory: {resolved}")
    if not writable_fn(resolved, os.W_OK):
        raise RuntimeError(f"P2 output target is not writable: {resolved}")
    free = int(disk_usage_fn(resolved).free)
    if free < int(min_free_bytes):
        raise RuntimeError(
            f"P2 output target has only {free} free bytes; requires {int(min_free_bytes)}"
        )
    try:
        actual_mount = Path(mountpoint_fn(resolved)).resolve(strict=True)
        expected_mount = Path(required_mount).resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"P2 shared2 mount cannot be verified: {exc}") from exc
    if actual_mount != expected_mount:
        raise RuntimeError(
            f"P2 output target is not on required mount: {actual_mount} != {expected_mount}"
        )
    target_device = int(device_fn(resolved))
    compared = list(comparison_paths or (WORKTREE_ROOT, Path.home(), Path("/")))
    for comparison in compared:
        comparison_path = Path(comparison).resolve(strict=False)
        if target_device == int(device_fn(comparison_path)):
            raise RuntimeError(
                "P2 output target device matches worktree/home/root device: "
                f"{resolved} and {comparison_path}"
            )
    return resolved


def _stage_recognition_method(
    profile: str,
    *,
    stage_recognition_enabled: bool,
) -> dict[str, object]:
    if profile == "p1":
        renoise_t_max = 2
        rollout_scale = 5.0
        rollout_start_ratio = 0.2
    elif profile == "p2":
        renoise_t_max = 3
        rollout_scale = 20.0
        rollout_start_ratio = 0.6
    else:
        raise ValueError(f"Unsupported stage-recognition profile: {profile}")
    stage_label = "on" if stage_recognition_enabled else "off"
    label = f"{profile}_stage_{stage_label}"
    return {
        "method": label,
        "label": label,
        "profile": profile,
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 16,
        "temperature": 0.1,
        "renoise_t_max": renoise_t_max,
        "renoise_t_min": 1,
        "reward_mode": "normal",
        "initial_sampling_mode": "rbf_diverse_denoise",
        "initial_diversity_scale": 20.0,
        "initial_diversity_start_ratio": 0.8,
        "truncated_rollout_mode": "rbf_diverse",
        "rollout_diversity_scale": rollout_scale,
        "rollout_diversity_start_ratio": rollout_start_ratio,
        "rollout_diversity_iters": "all",
        "rollout_diversity_skip_final_steps": 0,
        "save_mechanism_trace_to_qualitative": True,
        "stage_recognition_enabled": stage_recognition_enabled,
        "gemini_grounding_enabled": False,
        "max_episode_steps": 720,
        "seed": 0,
    }


STAGE_RECOGNITION_ABLATION_METHODS = [
    _stage_recognition_method("p1", stage_recognition_enabled=False),
    _stage_recognition_method("p1", stage_recognition_enabled=True),
    _stage_recognition_method("p2", stage_recognition_enabled=False),
    _stage_recognition_method("p2", stage_recognition_enabled=True),
]

STAGE_RECOGNITION_PRETEST_METHOD = {
    **_stage_recognition_method("p1", stage_recognition_enabled=True),
    "method": "p1_stage_on_pretest",
    "label": "p1_stage_on_pretest",
    "task_ids_filter": [0, 6],
}
LEVEL3_METHODS = METHODS
LEVEL4_METHODS = [
    METHODS[0],
    RBF_DIVERSE_INITIAL_METHOD,
    {
        "method": "eds_softmax_strong_weak_renoise",
        "label": "eds_softmax_strong_weak_renoise",
        "population_size": 32,
        "cem_iters": 20,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 1.0,
        **WEAK_RENOISE,
        "reward_mode": "normal",
    },
    {
        "method": "eds_cem_resample_weak_renoise",
        "label": "eds_cem_resample_weak_renoise",
        "population_size": 32,
        "cem_iters": 20,
        "use_cem": True,
        "num_elites": 8,
        "temperature": 1.0,
        **WEAK_RENOISE,
        "reward_mode": "normal",
    },
]
LEVEL_REPORTS = {
    "level0": "level_0_deployment_correctness.md",
    "level1": "level_1_mechanism_probe.md",
    "level2": "level_2_online_smoke.md",
    "level3": "level_3_libero_object_success.md",
    "rollout_rbf_ablation": ROLLOUT_RBF_REPORT,
    "object_swap_ood_rbf": OBJECT_SWAP_OOD_RBF_REPORT,
    "stage_recognition_ablation": STAGE_RECOGNITION_REPORT,
    "level4": "level_4_libero_pro_ood.md",
    "final": "rdt_eds_final_evaluation_report.md",
}
STATUS_FIELDS = [
    "job_id",
    "level",
    "suite",
    "method",
    "label",
    "status",
    "episodes",
    "population_size",
    "cem_iters",
    "use_cem",
    "num_elites",
    "temperature",
    "renoise_t_max",
    "renoise_t_min",
    "reward_mode",
    "initial_sampling_mode",
    "initial_diversity_scale",
    "initial_diversity_start_ratio",
    "truncated_rollout_mode",
    "rollout_diversity_scale",
    "rollout_diversity_start_ratio",
    "rollout_diversity_iters",
    "rollout_diversity_skip_final_steps",
    *P2_EDS_CONFIG_FIELDS,
    *P2_MAIN_EXECUTION_FIELDS,
    "config_fingerprint",
    "manifest_sha256",
    "profile",
    "stage_recognition_enabled",
    "gemini_grounding_enabled",
    "max_episode_steps",
    "seed",
    "output_dir",
    "metrics_dir",
    "log_file",
    "gpu",
    "exit_code",
    "wall_clock_s",
    "success_count",
    "success_rate",
    "videos",
    "metrics_records",
    "qualitative_png",
    "valid",
    "failure_reason",
    "strict_perturbations_verified",
    "suite_verified",
    "start_time",
    "end_time",
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _hydra_optional(value: object) -> str:
    return "null" if value is None else str(value)


def ensure_dirs() -> None:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_ROOT / "logs").mkdir(parents=True, exist_ok=True)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    OOD_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    STAGE_RECOGNITION_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    (STAGE_RECOGNITION_RUN_ROOT / "runner_logs").mkdir(parents=True, exist_ok=True)


def _p2_stage_dir(level: object) -> str:
    mapping = {
        "p2_adaptive_eds_rbf_pretest": "pretest",
        "p2_adaptive_eds_rbf_stage_a": "stage_a",
        "p2_adaptive_eds_rbf_stage_b": "stage_b",
    }
    try:
        return mapping[str(level)]
    except KeyError as exc:
        raise ValueError(f"Unsupported P2 level: {level!r}") from exc


def _p2_safe_child_path(real_root: Path, *parts: object) -> Path:
    root = Path(real_root).absolute()
    try:
        root_stat = os.lstat(root)
    except FileNotFoundError:
        root_resolved = root.resolve(strict=False)
    except OSError as exc:
        raise RuntimeError(f"cannot lstat P2 real root {root}: {exc}") from exc
    else:
        if stat.S_ISLNK(root_stat.st_mode):
            raise RuntimeError(f"P2 real root must not be a symlink: {root}")
        root_resolved = root.resolve(strict=True)

    cursor = root
    for raw_part in parts:
        part = str(raw_part)
        parsed = Path(part)
        if (
            not part
            or parsed.is_absolute()
            or len(parsed.parts) != 1
            or part in {".", ".."}
        ):
            raise RuntimeError(f"unsafe P2 child path component: {part!r}")
        cursor = cursor / part
        try:
            child_stat = os.lstat(cursor)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise RuntimeError(f"cannot lstat P2 child path {cursor}: {exc}") from exc
        else:
            if stat.S_ISLNK(child_stat.st_mode):
                raise RuntimeError(f"P2 child path must not be a symlink: {cursor}")
        resolved = cursor.resolve(strict=False)
        try:
            resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise RuntimeError(f"P2 child path escapes real root: {resolved}") from exc
    return cursor


def _output_root_for_job(job: dict[str, object]) -> Path:
    if job.get("level") in P2_LEVELS:
        real_root = Path(job.get("p2_output_real_root", P2_OUTPUT_ROOT))
        return _p2_safe_child_path(real_root, _p2_stage_dir(job.get("level")))
    if job.get("level") == "stage_recognition_pretest":
        return STAGE_RECOGNITION_RUN_ROOT / "mechanism_pretest"
    if job.get("level") == "stage_recognition_ablation":
        return STAGE_RECOGNITION_RUN_ROOT
    if job.get("level") == "object_swap_ood_rbf":
        return OOD_RUN_ROOT
    return RUN_ROOT


def _output_dir(job: dict[str, object]) -> Path:
    if job.get("level") in P2_LEVELS:
        real_root = Path(job.get("p2_output_real_root", P2_OUTPUT_ROOT))
        return _p2_safe_child_path(
            real_root,
            _p2_stage_dir(job.get("level")),
            str(job["label"]),
        )
    return _output_root_for_job(job) / str(job["job_id"])


def _log_file_for_job(job: dict[str, object]) -> Path:
    if job.get("level") in P2_LEVELS:
        real_root = Path(job.get("p2_output_real_root", P2_OUTPUT_ROOT))
        return _p2_safe_child_path(
            real_root,
            "runner_logs",
            _p2_stage_dir(job.get("level")),
            f"{job['label']}.log",
        )
    if job.get("level") in {
        "stage_recognition_pretest",
        "stage_recognition_ablation",
    }:
        return STAGE_RECOGNITION_RUN_ROOT / "runner_logs" / f"{job['job_id']}.log"
    return EVIDENCE_ROOT / "logs" / f"{job['job_id']}.log"


def _archive_stage_job_artifacts(job: dict[str, object]) -> Path | None:
    if job.get("level") not in {
        "stage_recognition_pretest",
        "stage_recognition_ablation",
    }:
        return None
    output_dir = _output_dir(job)
    log_file = _log_file_for_job(job)
    if not output_dir.exists() and not log_file.exists():
        return None
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive_dir = (
        STAGE_RECOGNITION_RUN_ROOT
        / "stale"
        / f"{job['job_id']}_{timestamp}"
    )
    archive_dir.mkdir(parents=True, exist_ok=False)
    if output_dir.exists():
        shutil.move(str(output_dir), str(archive_dir / "output"))
    if log_file.exists():
        shutil.move(str(log_file), str(archive_dir / "runner.log"))
    _redact_secrets_in_text_tree(archive_dir)
    return archive_dir


def _revalidate_p2_job_storage(job: dict[str, object]) -> Path:
    if job.get("level") not in P2_LEVELS:
        return _output_dir(job)
    expected_root = Path(
        job.get("p2_output_real_root", _default_p2_real_root())
    ).resolve(strict=False)
    if job.get("p2_storage_enforced"):
        current_root = _validate_p2_output_storage()
        if current_root.resolve(strict=True) != expected_root.resolve(strict=True):
            raise RuntimeError(
                f"P2 storage link changed from fixed root {expected_root} to {current_root}"
            )
    stage = _p2_stage_dir(job.get("level"))
    label = str(job.get("label", ""))
    if not label or Path(label).name != label or label in {".", ".."}:
        raise RuntimeError(f"unsafe P2 job label: {label!r}")
    candidate = _p2_safe_child_path(expected_root, stage, label)
    if candidate.exists() and not candidate.is_dir():
        raise RuntimeError(f"P2 stage/job path is not a directory: {candidate}")
    return candidate


def _p2_job_manifest_payload(job: dict[str, object]) -> dict[str, object]:
    execution_record = _p2_execution_record(job)
    fingerprint = _p2_fingerprint_from_record(execution_record)
    resolved_job = {
        key: value
        for key, value in job.items()
        if key
        not in {
            "config_fingerprint",
            "execution_record",
            "manifest_path",
            "p2_storage_enforced",
        }
    }
    payload = {
        "schema": "p2-adaptive-eds-rbf-job-v2",
        "job": resolved_job,
        "execution_record": execution_record,
        "config_fingerprint": fingerprint,
        "manifest_sha256": job.get("manifest_sha256"),
    }
    if _contains_secret_text(payload):
        raise ValueError("P2 job manifest contains credential material")
    return payload


def _write_p2_job_identity(job: dict[str, object]) -> None:
    if job.get("level") not in P2_LEVELS:
        return
    output_dir = _revalidate_p2_job_storage(job)
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = _p2_config_fingerprint(job)
    declared = job.get("config_fingerprint")
    if declared is not None and declared != expected:
        raise RuntimeError(
            f"P2 job carries stale config fingerprint: {declared} != {expected}"
        )
    real_root = Path(job.get("p2_output_real_root", P2_OUTPUT_ROOT))
    stage = _p2_stage_dir(job.get("level"))
    label = str(job["label"])
    fingerprint_path = _p2_safe_child_path(
        real_root, stage, label, "config_fingerprint.txt"
    )
    if not fingerprint_path.exists() and any(output_dir.iterdir()):
        raise RuntimeError(
            f"existing nonempty P2 output has no config fingerprint: {output_dir}"
        )
    if fingerprint_path.exists():
        existing = fingerprint_path.read_text(encoding="utf-8", errors="replace").strip()
        if existing != expected:
            raise RuntimeError(
                f"P2 config fingerprint conflict for {job['label']}: {existing} != {expected}"
            )
    manifest_path = _p2_safe_child_path(real_root, stage, label, "job_manifest.json")
    payload = _p2_job_manifest_payload(job)
    if manifest_path.exists():
        try:
            existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"P2 job manifest is not parseable: {manifest_path}") from exc
        if existing_manifest.get("config_fingerprint") != expected:
            raise RuntimeError(f"P2 job manifest fingerprint conflict: {manifest_path}")
    fingerprint_path.write_text(expected + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _archive_p2_job_artifacts(job: dict[str, object]) -> Path | None:
    if job.get("level") not in P2_LEVELS:
        return None
    output_dir = _revalidate_p2_job_storage(job)
    log_file = _log_file_for_job(job)
    if not output_dir.exists() and not log_file.exists():
        return None
    expected = _p2_config_fingerprint(job)
    fingerprint_path = output_dir / "config_fingerprint.txt"
    if output_dir.exists():
        if not fingerprint_path.is_file():
            raise RuntimeError(
                f"existing P2 output has no config fingerprint: {output_dir}"
            )
        existing = fingerprint_path.read_text(encoding="utf-8", errors="replace").strip()
        if existing != expected:
            raise RuntimeError(
                f"P2 config fingerprint conflict for existing output {output_dir}"
            )
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    real_root = Path(job.get("p2_output_real_root", P2_OUTPUT_ROOT))
    archive_dir = _p2_safe_child_path(
        real_root,
        "stale",
        _p2_stage_dir(job.get("level")),
        f"{job['label']}_{timestamp}",
    )
    archive_dir.mkdir(parents=True, exist_ok=False)
    if output_dir.exists():
        shutil.move(str(output_dir), str(_p2_safe_child_path(archive_dir, "output")))
    if log_file.exists():
        shutil.move(str(log_file), str(_p2_safe_child_path(archive_dir, "runner.log")))
    _redact_secrets_in_text_tree(archive_dir)
    return archive_dir


def _redact_secrets_in_text_tree(root: Path) -> None:
    runtime_secrets = _p2_runtime_secret_values()
    try:
        paths = [
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in _P2_CREDENTIAL_TEXT_SUFFIXES
        ]
        for path in paths:
            _p2_stream_redact_file(path, runtime_secrets)
    except (OSError, UnicodeError, RuntimeError) as exc:
        failure_path = _p2_safe_child_path(
            root, "credential_redaction_failure.json"
        )
        failure_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "failure_reason": f"credential redaction error: {type(exc).__name__}",
                    "timestamp": now_iso(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise RuntimeError(f"P2 archive credential redaction failed: {exc}") from exc
    if _p2_tree_contains_credential(root):
        failure_path = _p2_safe_child_path(
            root, "credential_redaction_failure.json"
        )
        failure_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "failure_reason": "credential material remains after streaming redaction",
                    "timestamp": now_iso(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise RuntimeError("P2 archive still contains credential material after redaction")


def build_jobs(
    level: str,
    episodes: int,
    *,
    manifest_path: str | Path | None = None,
) -> list[dict[str, object]]:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    manifest: dict[str, object] | None = None
    if level == "p2_adaptive_eds_rbf_pretest":
        if episodes != 2:
            raise ValueError("p2_adaptive_eds_rbf_pretest requires exactly 2 episodes")
        suites = ["libero_object_swap"]
        methods = P2_PRETEST_METHODS
    elif level == "p2_adaptive_eds_rbf_stage_a":
        if episodes != 10:
            raise ValueError("p2_adaptive_eds_rbf_stage_a requires exactly 10 episodes")
        suites = ["libero_object_swap"]
        methods = P2_STAGE_A_METHODS
    elif level == "p2_adaptive_eds_rbf_stage_b":
        if episodes != 10:
            raise ValueError("p2_adaptive_eds_rbf_stage_b requires exactly 10 episodes")
        suites = ["libero_object_swap"]
        manifest = _load_p2_integration_manifest(manifest_path)
        methods = []
        for profile in manifest["profiles"]:
            if profile["status"] != "active":
                continue
            method = _p2_profile(str(profile["label"]))
            for hydra_key, value in profile["overrides"].items():
                method[P2_MANIFEST_OVERRIDE_KEYS[hydra_key]] = value
            method.update(
                {
                    "manifest_sha256": manifest["manifest_sha256"],
                    "manifest_path": manifest["manifest_path"],
                    "stage_a_report_sha256": manifest["stage_a_report_sha256"],
                    "source_stage_a_jobs": profile["source_stage_a_jobs"],
                }
            )
            methods.append(method)
    elif level == "level2":
        suites = [BASE_SUITE]
        methods = LEVEL2_METHODS
    elif level == "level3":
        suites = [BASE_SUITE]
        methods = LEVEL3_METHODS
    elif level == "renoise_ablation":
        suites = [BASE_SUITE]
        methods = RENOISE_TMAX_ABLATION_METHODS
    elif level == "rollout_rbf_ablation":
        suites = [BASE_SUITE]
        methods = ROLLOUT_RBF_ABLATION_METHODS
    elif level == "object_swap_ood_rbf":
        suites = ["libero_object_swap"]
        methods = OBJECT_SWAP_OOD_RBF_METHODS
    elif level == "stage_recognition_pretest":
        if episodes != 2:
            raise ValueError("stage_recognition_pretest requires exactly 2 episodes")
        suites = ["libero_object_swap"]
        methods = [STAGE_RECOGNITION_PRETEST_METHOD]
    elif level == "stage_recognition_ablation":
        suites = ["libero_object_swap"]
        methods = STAGE_RECOGNITION_ABLATION_METHODS
    elif level == "level4":
        suites = OOD_SUITES
        methods = LEVEL4_METHODS
    else:
        raise ValueError(f"Unsupported online level: {level}")

    jobs: list[dict[str, object]] = []
    for suite in suites:
        for method in methods:
            label = str(method["label"])
            job_level = (
                "level3"
                if level in {"renoise_ablation", "rollout_rbf_ablation"}
                else "level4"
                if level == "object_swap_ood_rbf"
                else "stage_pretest"
                if level == "stage_recognition_pretest"
                else "stage_ablation"
                if level == "stage_recognition_ablation"
                else level
            )
            job_id = f"{job_level}_{suite}_{label}"
            jobs.append(
                {
                    **method,
                    "job_id": job_id,
                    "level": level,
                    "suite": suite,
                    "episodes": episodes,
                }
            )
    if level in P2_LEVELS:
        git_revision = _git_head_revision()
        code_state_sha256 = _p2_code_state_sha256()
        for job in jobs:
            _bind_p2_execution_context(
                job,
                git_revision=git_revision,
                code_state_sha256=code_state_sha256,
            )
    return jobs


def build_main_command(
    job: dict[str, object],
    gpu: str,
    timeout_seconds: int,
    *,
    cached_functions_dir: str | None = None,
    offline_vlm: bool = False,
) -> list[str]:
    del gpu, timeout_seconds
    output_dir = _output_dir(job)
    metrics_dir = output_dir / "eds_eval"
    is_p2 = job["level"] in P2_LEVELS
    is_stage_eval = job["level"] in {
        "stage_recognition_pretest",
        "stage_recognition_ablation",
    } or is_p2
    is_strict_ood = job["level"] in {
        "level4",
        "object_swap_ood_rbf",
        "stage_recognition_pretest",
        "stage_recognition_ablation",
    } or is_p2
    max_episode_steps = int(job.get("max_episode_steps", 240))
    stage_recognition_enabled = bool(
        job.get("stage_recognition_enabled", not offline_vlm)
    )
    gemini_grounding_enabled = bool(
        job.get("gemini_grounding_enabled", not offline_vlm)
    )
    if is_stage_eval and cached_functions_dir is None:
        cached_functions_dir = str(STAGE_CACHED_FUNCTIONS_DIR)
    command = [
        "conda",
        "run",
        "-n",
        "vla-pilot",
        "python",
        "main.py",
        "policy.type=rdt",
        "backend=libero",
        f"backend.libero.suite_name={job['suite']}",
        f"main.episode_num={job['episodes']}",
        f"backend.libero.max_episode_steps={max_episode_steps}",
        f"backend.libero.strict_perturbations={str(is_strict_ood).lower()}",
        "main.use_vlm_stage_recognition="
        f"{str(stage_recognition_enabled).lower()}",
        "perception.gemini_grounding.enabled="
        f"{str(gemini_grounding_enabled).lower()}",
        f"main.render={str(is_strict_ood).lower()}",
        "main.visualize_trajectory=true",
        "main.debug_draw_trajectory=true",
        "main.eds_eval.enabled=true",
        "main.eds_eval.write_metrics=true",
        "main.eds_eval.save_qualitative=true",
        f"main.eds_eval.method_label={job['label']}",
        f"main.eds_eval.job_id={job['job_id']}",
        f"main.eds_eval.output_dir={metrics_dir}",
        f"hydra.run.dir={output_dir}",
    ]
    if is_stage_eval:
        command.extend(
            [
                f"seed={int(job.get('seed', 0))}",
                "main.vlm_query_limit=50",
            ]
        )
    if is_strict_ood:
        command.extend(
            [
                "perception.vlm_agent.api_max_retries=8",
                "perception.vlm_agent.api_retry_backoff_seconds=5.0",
                "perception.vlm_agent.api_retry_max_backoff_seconds=30.0",
            ]
        )
    task_ids_filter = job.get("task_ids_filter")
    if task_ids_filter is not None:
        task_ids = ",".join(str(int(task_id)) for task_id in task_ids_filter)
        command.append(f"backend.libero.task_ids_filter=[{task_ids}]")
    elif job["level"] in {"level2", "renoise_ablation", "rollout_rbf_ablation"}:
        command.append("backend.libero.task_ids_filter=[0]")

    if job["method"] == "unguided":
        command.append("main.use_guidance=false")
    else:
        if cached_functions_dir is not None:
            command.append(f"main.cached_functions_dir={cached_functions_dir}")
        command.extend(
            [
                "main.use_guidance=true",
                "main.guidance_type=eds",
                f"main.eds_config.population_size={job['population_size']}",
                f"main.eds_config.cem_iters={job['cem_iters']}",
                f"main.eds_config.use_cem={str(job['use_cem']).lower()}",
                f"main.eds_config.num_elites={job['num_elites']}",
                f"main.eds_config.temperature={job['temperature']}",
                f"main.eds_config.renoise_t_max={job['renoise_t_max']}",
                f"main.eds_config.renoise_t_min={job['renoise_t_min']}",
                f"main.eds_eval.reward_mode={job['reward_mode']}",
                f"main.eds_config.initial_sampling_mode={job.get('initial_sampling_mode', 'iid')}",
                f"main.eds_config.initial_diversity_scale={job.get('initial_diversity_scale', 1.0)}",
                "main.eds_config.initial_diversity_start_ratio="
                f"{_hydra_optional(job.get('initial_diversity_start_ratio'))}",
            ]
        )
        truncated_rollout_mode = job.get("truncated_rollout_mode")
        if truncated_rollout_mode == "rbf_diverse":
            command.extend(
                [
                    "main.eds_config.truncated_rollout_mode=rbf_diverse",
                    "main.eds_config.rollout_diversity_scale="
                    f"{job['rollout_diversity_scale']}",
                    "main.eds_config.rollout_diversity_start_ratio="
                    f"{job['rollout_diversity_start_ratio']}",
                    "main.eds_config.rollout_diversity_iters="
                    f"{job['rollout_diversity_iters']}",
                    "main.eds_config.rollout_diversity_skip_final_steps="
                    f"{job['rollout_diversity_skip_final_steps']}",
                ]
            )
        elif truncated_rollout_mode == "baseline":
            command.append("main.eds_config.truncated_rollout_mode=baseline")
        if bool(job.get("save_mechanism_trace_to_qualitative", False)):
            command.extend(
                [
                    "main.eds_mechanism_pretest.enabled=true",
                    "main.eds_mechanism_pretest.first_chunk_only=false",
                    "main.eds_mechanism_pretest.output_mode=qualitative_chunk",
                    "main.eds_mechanism_pretest.max_chunks=2",
                    "main.eds_mechanism_pretest.save_tensors=true",
                    "main.eds_mechanism_pretest.plot_3d=true",
                    f"main.eds_mechanism_pretest.max_full_process_iters={job['cem_iters']}",
                ]
            )
        if is_p2:
            command.extend(
                f"main.eds_config.{field}={_hydra_scalar(job[field])}"
                for field in P2_EDS_CONFIG_FIELDS
            )
            command.extend(
                f"main.{field}={_hydra_scalar(job[field])}"
                for field in P2_MAIN_EXECUTION_FIELDS
            )
    return command


def _gpu_runtime(gpu: str) -> dict[str, str]:
    """Return CUDA/EGL settings for a physical GPU index on this host."""
    gpu = str(gpu).strip()
    # EGL_EXT_device_query reports this host's physical CUDA-to-EGL mapping.
    egl_device_by_cuda_gpu = {
        "0": "2",
        "1": "3",
        "2": "1",
        "3": "0",
        "4": "6",
        "5": "7",
        "6": "5",
        "7": "4",
    }
    return {
        "cuda_visible_devices": gpu,
        "mujoco_egl_device_id": egl_device_by_cuda_gpu.get(
            gpu,
            gpu.split(",", 1)[0],
        ),
    }


def _p2_gpu_probe(gpu: str) -> tuple[str, str]:
    gpu = str(gpu).strip()
    if gpu not in P2_ALLOWED_GPUS:
        return "error", f"GPU {gpu} is outside the approved P2 set"
    try:
        compute = subprocess.run(
            [
                "nvidia-smi",
                "-i",
                gpu,
                "--query-compute-apps=pid",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        memory = subprocess.run(
            [
                "nvidia-smi",
                "-i",
                gpu,
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except OSError as exc:
        return "error", f"nvidia-smi unavailable: {exc}"
    except subprocess.TimeoutExpired:
        return "error", "nvidia-smi timeout"
    if compute.returncode != 0:
        return "error", f"nvidia-smi compute probe exit={compute.returncode}"
    if memory.returncode != 0:
        return "error", f"nvidia-smi memory probe exit={memory.returncode}"
    process_lines = [line.strip() for line in compute.stdout.splitlines() if line.strip()]
    process_lines = [line for line in process_lines if "no running" not in line.lower()]
    if process_lines:
        return "busy", "compute process present"
    try:
        memory_used_mib = int(memory.stdout.strip().splitlines()[0])
    except (IndexError, ValueError):
        return "error", "nvidia-smi returned invalid memory usage"
    if memory_used_mib >= P2_GPU_MEMORY_BUSY_MIB:
        return "busy", f"memory.used={memory_used_mib} MiB"
    return "idle", ""


def _p2_gpu_is_idle(gpu: str) -> bool:
    status, _reason = _p2_gpu_probe(gpu)
    return status == "idle"


def _write_p2_gpu_probe_failure(
    level: str,
    gpu: str,
    reason: str,
    failure_count: int,
    *,
    real_root: Path | None = None,
) -> Path:
    root = Path(real_root if real_root is not None else P2_STATUS_ROOT)
    failure_dir = _p2_safe_child_path(root, "failures", _p2_stage_dir(level))
    failure_dir.mkdir(parents=True, exist_ok=True)
    path = _p2_safe_child_path(
        root, "failures", _p2_stage_dir(level), f"gpu_{gpu}_probe_failure.json"
    )
    path.write_text(
        json.dumps(
            {
                "gpu": str(gpu),
                "status": "failed",
                "failure_reason": reason,
                "consecutive_probe_failures": int(failure_count),
                "timestamp": now_iso(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _poe_healthcheck() -> bool:
    """Verify the configured Poe credential without serializing it."""
    env = os.environ.copy()
    env["OPENAI_BASE_URL"] = "https://api.poe.com/v1"
    script = (
        "import os; from openai import OpenAI; "
        "response=OpenAI(api_key=os.environ['OPENAI_API_KEY'], "
        "base_url=os.environ['OPENAI_BASE_URL']).chat.completions.create("
        "model='gemini-2.5-flash', "
        "messages=[{'role':'user','content':'Reply with exactly OK.'}], "
        "max_tokens=64, temperature=0.0); "
        "content=response.choices[0].message.content or ''; "
        "raise SystemExit(0 if content.strip() else 3)"
    )
    try:
        result = subprocess.run(
            [
                "conda",
                "run",
                "--no-capture-output",
                "-n",
                "vla-pilot",
                "python",
                "-c",
                script,
            ],
            cwd=WORKTREE_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _validate_stage_level_start(
    level: str,
    *,
    offline_vlm: bool,
    require_online_api: bool = True,
) -> None:
    if level not in {
        "stage_recognition_pretest",
        "stage_recognition_ablation",
        *P2_LEVELS,
    }:
        return
    if offline_vlm:
        raise SystemExit("Stage-recognition experiments do not allow --offline-vlm")
    if require_online_api:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key or api_key.lower() == "dummy":
            raise SystemExit("A real Poe API key in OPENAI_API_KEY is required")
        if not _poe_healthcheck():
            raise SystemExit("Poe Gemini health check failed")
    if level == "stage_recognition_ablation":
        pretest_job = build_jobs("stage_recognition_pretest", episodes=2)[0]
        pretest_validity = _job_validity(pretest_job)
        if not pretest_validity["valid"]:
            raise SystemExit(
                "Stage-recognition pretest must pass before the formal ablation: "
                + str(pretest_validity["failure_reason"])
            )


def preflight() -> int:
    ensure_dirs()
    failures: list[str] = []
    checks: list[str] = []
    os.environ.setdefault("LIBERO_CONFIG_PATH", str(LIBERO_CONFIG_PATH))
    pythonpath_parts = [str(LIBERO_PRO_ROOT)]
    if os.environ.get("PYTHONPATH"):
        pythonpath_parts.append(os.environ["PYTHONPATH"])
    os.environ["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    required_paths = [
        WORKTREE_ROOT / "configs" / "config.yaml",
        WORKTREE_ROOT / "main.py",
        WORKTREE_ROOT / "core" / "rdt_policy_steer.py",
        LIBERO_CONFIG_PATH / "config.yaml",
        STAGE_CACHED_FUNCTIONS_DIR,
    ]
    for path in required_paths:
        if not path.exists():
            failures.append(f"missing required path: {path.relative_to(WORKTREE_ROOT)}")

    libero_pro = LIBERO_PRO_ROOT
    for name in [
        "perturbation.py",
        "evaluation_config.yaml",
        "libero/libero/bddl_files/libero_object",
        "libero/libero/init_files/libero_object",
        "libero_ood/ood_environment.yaml",
        "libero_ood/ood_spatial_relation.yaml",
        "libero_ood/ood_object.yaml",
        "libero_ood/ood_language.yaml",
        "libero_ood/ood_task.yaml",
    ]:
        path = libero_pro / name
        if not path.exists():
            failures.append(f"missing required path: {path.relative_to(WORKTREE_ROOT)}")

    try:
        libero_pro_path = str(libero_pro)
        if libero_pro_path not in sys.path:
            sys.path.insert(0, libero_pro_path)
        from libero.libero import benchmark, get_libero_path

        available = benchmark.get_benchmark_dict()
        missing_suites = [suite for suite in OOD_SUITES if suite not in available]
        if missing_suites:
            failures.append(
                "LIBERO-PRO benchmark suites not registered: "
                + ", ".join(missing_suites)
            )
        for key in ["bddl_files", "init_states", "assets"]:
            resolved = Path(get_libero_path(key)).resolve()
            if LIBERO_PRO_ROOT.resolve() not in resolved.parents:
                failures.append(
                    f"LIBERO {key} path does not point to this worktree's LIBERO-PRO: {resolved}"
                )
        if not failures:
            from core.env_adapters import libero_adapter

            for suite in OOD_SUITES:
                actual_suite, _read_language = libero_adapter._apply_perturbations(suite)
                if actual_suite == BASE_SUITE:
                    failures.append(f"LIBERO-PRO suite {suite} fell back to {BASE_SUITE}")
                    continue
                bddl_dir = Path(get_libero_path("bddl_files")) / actual_suite
                init_dir = Path(get_libero_path("init_states")) / actual_suite
                if not bddl_dir.is_dir() or not init_dir.is_dir():
                    failures.append(
                        f"LIBERO-PRO suite {suite} missing generated dirs: "
                        f"{bddl_dir} / {init_dir}"
                    )
                    continue
                bddl_files = sorted(bddl_dir.glob("*.bddl"))
                init_files = sorted(init_dir.glob("*.pruned_init"))
                if not bddl_files or not init_files:
                    failures.append(
                        f"LIBERO-PRO suite {suite} has empty generated files: "
                        f"{len(bddl_files)} bddl / {len(init_files)} init"
                    )
                    continue
                base_bddl_dir = Path(get_libero_path("bddl_files")) / BASE_SUITE
                differs_from_base = False
                for bddl_file in bddl_files:
                    base_file = base_bddl_dir / bddl_file.name
                    if not base_file.exists() or base_file.read_text(encoding="utf-8") != bddl_file.read_text(encoding="utf-8"):
                        differs_from_base = True
                        break
                if not differs_from_base:
                    failures.append(
                        f"LIBERO-PRO suite {suite} generated BDDL identical to {BASE_SUITE}"
                    )
                    continue
                checks.append(
                    f"- `{suite}` -> `{actual_suite}`: {len(bddl_files)} BDDL / "
                    f"{len(init_files)} init files, BDDL differs from `{BASE_SUITE}`."
                )
    except Exception as exc:  # noqa: BLE001
        failures.append(f"failed to import LIBERO-PRO benchmark registry: {exc}")

    lines = [
        "# RDT+EDS Evaluation Preflight",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        f"Status: `{'blocked' if failures else 'pass'}`",
        "",
    ]
    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["## Checks", "", "- Required files are present."])
        if checks:
            lines.extend(["", "## OOD Suite Verification", ""])
            lines.extend(checks)
    report_text = "\n".join(lines) + "\n"
    reports = [
        EVIDENCE_ROOT / "preflight.md",
        EVIDENCE_ROOT / "level4_preflight.md",
    ]
    for report in reports:
        report.write_text(report_text, encoding="utf-8")
    print(reports[-1])
    return 2 if failures else 0


def _results_path(job: dict[str, object]) -> Path:
    return _output_dir(job) / "results.txt"


def _metrics_path(job: dict[str, object]) -> Path:
    return _output_dir(job) / "eds_eval" / "eds_metrics.jsonl"


def _job_has_complete_outputs(job: dict[str, object]) -> bool:
    if job.get("level") in {
        "object_swap_ood_rbf",
        "stage_recognition_pretest",
        "stage_recognition_ablation",
        *P2_LEVELS,
    }:
        return bool(_job_validity(job)["valid"])
    results_path = _results_path(job)
    if not results_path.exists():
        return False
    text = results_path.read_text(encoding="utf-8", errors="replace")
    if "Success count:" not in text or "Success rate:" not in text:
        return False
    if job["method"] == "unguided":
        return True
    metrics_path = _metrics_path(job)
    return metrics_path.exists() and metrics_path.stat().st_size > 0


def _parse_results_file(path: Path) -> dict[str, object]:
    parsed: dict[str, object] = {
        "success": None,
        "total": None,
        "success_rate": None,
    }
    if not path.exists():
        return parsed
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("Success count:"):
            value = line.split(":", 1)[1].strip()
            if "/" in value:
                left, right = value.split("/", 1)
                parsed["success"] = int(left.strip())
                parsed["total"] = int(right.strip())
        elif line.startswith("Success rate:"):
            value = line.split(":", 1)[1].strip().rstrip("%")
            parsed["success_rate"] = float(value)
    return parsed


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _read_p2_jsonl_strict(
    path: Path, *, label: str
) -> tuple[list[dict[str, object]], list[str]]:
    if not path.exists():
        return [], []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [], [f"{label} JSONL is not readable: {exc}"]
    rows: list[dict[str, object]] = []
    failures: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (ValueError, RecursionError):
            failures.append(f"{label} JSONL line {line_number} is not valid JSON")
            continue
        if not isinstance(value, dict):
            failures.append(f"{label} JSONL line {line_number} is not a JSON object")
            continue
        rows.append(value)
    return rows, failures


def _mean(values: list[float]) -> float | None:
    finite = [
        float(value)
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ]
    if not finite:
        return None
    return float(sum(finite) / len(finite))


def _metric_values(records: list[dict[str, object]], key: str) -> list[float]:
    values = []
    for record in records:
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        value_f = float(value)
        if math.isfinite(value_f):
            values.append(value_f)
    return values


def _metric_mean(records: list[dict[str, object]], key: str) -> float | None:
    return _mean(_metric_values(records, key))


def _metric_sum(records: list[dict[str, object]], key: str) -> int:
    return int(sum(_metric_values(records, key)))


def _metric_max(records: list[dict[str, object]], key: str) -> float | None:
    values = _metric_values(records, key)
    return max(values) if values else None


def _fmt_float(value: float | int | None, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


def _fmt_optional(value: object) -> str:
    return "null" if value is None else str(value)


def _rel_or_abs(path: Path) -> Path:
    try:
        return path.relative_to(WORKTREE_ROOT)
    except ValueError:
        return path


def _artifact_counts(output_dir: Path) -> dict[str, int]:
    return {
        "videos": len(list(output_dir.glob("episode_*/*.mp4"))),
        "qualitative_png": len(list((output_dir / "eds_eval").glob("qualitative/**/*.png"))),
        "metrics_records": len(_read_jsonl(output_dir / "eds_eval" / "eds_metrics.jsonl")),
    }


def _rollout_rbf_artifact_counts(output_dir: Path) -> dict[str, int]:
    qualitative = output_dir / "eds_eval" / "qualitative"
    return {
        "rollout_rbf_metrics_json": len(
            list(qualitative.glob("**/Rollout_RBF_diversity/rollout_rbf_diversity_metrics.json"))
        ),
        "rollout_rbf_png": len(
            list(qualitative.glob("**/Rollout_RBF_diversity/*.png"))
        ),
        "rollout_rbf_npz": len(
            list(qualitative.glob("**/Rollout_RBF_diversity/rollout_rbf_diversity_trace.npz"))
        ),
    }


def _hydra_text(output_dir: Path) -> str:
    hydra_dir = output_dir / ".hydra"
    parts = []
    for name in ["overrides.yaml", "config.yaml"]:
        path = hydra_dir / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _hydra_overrides_text(output_dir: Path) -> str:
    path = output_dir / ".hydra" / "overrides.yaml"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _hydra_bool_verified(text: str, key: str) -> bool:
    normalized = text.lower().replace(" ", "")
    key = key.lower()
    return f"{key}=true" in normalized or f"{key}:true" in normalized


def _hydra_suite_verified(text: str, suite: str) -> bool:
    normalized = text.replace(" ", "")
    return (
        f"backend.libero.suite_name={suite}" in normalized
        or f"suite_name:{suite}" in normalized
        or f"suite_name='{suite}'" in normalized
        or f'suite_name:"{suite}"' in normalized
    )


def _hydra_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _hydra_assignment_verified(text: str, key: str, value: object) -> bool:
    normalized = (
        text.lower()
        .replace(" ", "")
        .replace('"', "")
        .replace("'", "")
    )
    key_norm = key.lower()
    value_norm = _hydra_scalar(value).lower().replace(" ", "")
    leaf_key = key_norm.rsplit(".", 1)[-1]
    return (
        f"{key_norm}={value_norm}" in normalized
        or f"{key_norm}:{value_norm}" in normalized
        or f"{leaf_key}:{value_norm}" in normalized
    )


def _hydra_exact_override_verified(text: str, key: str, value: object) -> bool:
    expected = f"{key.lower()}={_hydra_scalar(value).lower().replace(' ', '')}"
    for line in text.splitlines():
        normalized = (
            line.strip()
            .removeprefix("-")
            .strip()
            .lower()
            .replace(" ", "")
            .replace('"', "")
            .replace("'", "")
        )
        if normalized == expected:
            return True
    return False


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.YAMLError(f"duplicate YAML mapping key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _parse_override_assignment(value: str) -> tuple[str, object]:
    if not isinstance(value, str) or "=" not in value:
        raise ValueError(f"Hydra override must be a key=value string: {value!r}")
    key, raw_value = value.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError("Hydra override key must be nonempty")
    try:
        parsed_value = yaml.safe_load(raw_value)
    except yaml.YAMLError as exc:
        raise ValueError(f"Hydra override value is invalid YAML: {value!r}") from exc
    return key, parsed_value


def _p2_normalized_command_overrides(
    job: dict[str, object],
    *,
    cached_functions_dir: str | None = None,
) -> dict[str, object]:
    if cached_functions_dir is None:
        cached_functions_dir = str(
            job.get("p2_cached_functions_dir", STAGE_CACHED_FUNCTIONS_DIR)
        )
    command = build_main_command(
        job,
        gpu="2",
        timeout_seconds=1,
        cached_functions_dir=cached_functions_dir,
    )
    normalized: dict[str, object] = {}
    for item in command:
        if "=" not in item:
            continue
        key, value = _parse_override_assignment(item)
        if key in normalized:
            raise ValueError(f"build_main_command emitted duplicate override: {key}")
        normalized[key] = value
    if not normalized:
        raise ValueError("build_main_command emitted no Hydra overrides")
    return normalized


def _parse_p2_overrides_file(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(".hydra/overrides.yaml missing")
    text = path.read_text(encoding="utf-8", errors="strict")
    if not text.strip():
        raise ValueError(".hydra/overrides.yaml empty")
    try:
        loaded = yaml.load(text, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f".hydra/overrides.yaml parse error: {exc}") from exc
    if not isinstance(loaded, list) or not loaded:
        raise ValueError(".hydra/overrides.yaml must be a nonempty YAML list")
    normalized: dict[str, object] = {}
    for item in loaded:
        key, value = _parse_override_assignment(item)
        if key in normalized:
            conflict = "conflicting" if normalized[key] != value else "duplicate"
            raise ValueError(f".hydra/overrides.yaml {conflict} override: {key}")
        normalized[key] = value
    return normalized


def _nested_config_value(config: dict[str, object], dotted_key: str) -> object:
    current: object = config
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted_key)
        current = current[part]
    return current


def _p2_structured_config_failures(
    path: Path,
    expected_overrides: dict[str, object],
) -> list[str]:
    if not path.is_file():
        return [".hydra/config.yaml missing"]
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
        config = yaml.load(text, Loader=_UniqueKeySafeLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [f".hydra/config.yaml parse error: {exc}"]
    if not isinstance(config, dict):
        return [".hydra/config.yaml must be a mapping"]
    failures = []
    for key, expected in expected_overrides.items():
        if key in {"backend", "hydra.run.dir"}:
            continue
        try:
            actual = _nested_config_value(config, key)
        except KeyError:
            failures.append(f".hydra/config.yaml missing key: {key}")
            continue
        if _canonical_json(actual) != _canonical_json(expected):
            failures.append(
                f".hydra/config.yaml mismatch: {key}={actual!r} expected={expected!r}"
            )
    return failures


def _p2_hydra_runtime_failures(hydra_path: Path, output_dir: Path) -> list[str]:
    if not hydra_path.is_file() or hydra_path.is_symlink():
        return [".hydra/hydra.yaml missing or symlinked"]
    try:
        payload = yaml.safe_load(hydra_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [f".hydra/hydra.yaml is not parseable: {exc}"]
    if not isinstance(payload, dict):
        return [".hydra/hydra.yaml must be a mapping"]
    hydra = payload.get("hydra")
    if not isinstance(hydra, dict):
        return [".hydra/hydra.yaml missing hydra mapping"]
    run = hydra.get("run")
    runtime = hydra.get("runtime")
    run_dir = run.get("dir") if isinstance(run, dict) else None
    runtime_dir = runtime.get("output_dir") if isinstance(runtime, dict) else None
    expected = output_dir.resolve(strict=False)
    failures: list[str] = []
    for field, value in (
        ("hydra.run.dir", run_dir),
        ("hydra.runtime.output_dir", runtime_dir),
    ):
        if not isinstance(value, str) or not value.strip():
            failures.append(f".hydra/hydra.yaml {field} missing")
            continue
        if Path(value).resolve(strict=False) != expected:
            failures.append(
                f".hydra/hydra.yaml {field} mismatch: {value!r}"
            )
    return failures


def _expected_object_swap_hydra_overrides(
    job: dict[str, object],
) -> list[tuple[str, object]]:
    overrides: list[tuple[str, object]] = [
        ("policy.type", "rdt"),
        ("backend", "libero"),
        ("backend.libero.suite_name", job["suite"]),
        ("main.episode_num", job["episodes"]),
        ("backend.libero.max_episode_steps", 240),
        ("backend.libero.strict_perturbations", True),
        ("main.use_guidance", True),
        ("main.guidance_type", "eds"),
        ("main.eds_config.population_size", job["population_size"]),
        ("main.eds_config.cem_iters", job["cem_iters"]),
        ("main.eds_config.use_cem", job["use_cem"]),
        ("main.eds_config.num_elites", job["num_elites"]),
        ("main.eds_config.temperature", job["temperature"]),
        ("main.eds_config.renoise_t_max", job["renoise_t_max"]),
        ("main.eds_config.renoise_t_min", job["renoise_t_min"]),
        ("main.eds_eval.reward_mode", job["reward_mode"]),
        ("main.eds_config.initial_sampling_mode", job["initial_sampling_mode"]),
        ("main.eds_config.initial_diversity_scale", job["initial_diversity_scale"]),
        (
            "main.eds_config.initial_diversity_start_ratio",
            job["initial_diversity_start_ratio"],
        ),
        (
            "main.eds_config.truncated_rollout_mode",
            job["truncated_rollout_mode"],
        ),
        ("main.eds_mechanism_pretest.enabled", True),
        ("main.eds_mechanism_pretest.output_mode", "qualitative_chunk"),
    ]
    if job.get("truncated_rollout_mode") == "rbf_diverse":
        overrides.extend(
            [
                ("main.eds_config.rollout_diversity_scale", job["rollout_diversity_scale"]),
                (
                    "main.eds_config.rollout_diversity_start_ratio",
                    job["rollout_diversity_start_ratio"],
                ),
                ("main.eds_config.rollout_diversity_iters", job["rollout_diversity_iters"]),
                (
                    "main.eds_config.rollout_diversity_skip_final_steps",
                    job["rollout_diversity_skip_final_steps"],
                ),
            ]
        )
    return overrides


def _expected_stage_recognition_hydra_overrides(
    job: dict[str, object],
) -> list[tuple[str, object]]:
    overrides = [
        (key, value)
        for key, value in _expected_object_swap_hydra_overrides(job)
        if key != "backend.libero.max_episode_steps"
    ]
    overrides.extend(
        [
            ("backend.libero.max_episode_steps", 720),
            (
                "main.use_vlm_stage_recognition",
                job["stage_recognition_enabled"],
            ),
            ("perception.gemini_grounding.enabled", False),
            ("main.cached_functions_dir", str(STAGE_CACHED_FUNCTIONS_DIR)),
            ("seed", 0),
        ]
    )
    if job.get("task_ids_filter") is not None:
        overrides.append(
            ("backend.libero.task_ids_filter", job["task_ids_filter"])
        )
    return overrides


def _expected_p2_hydra_overrides(job: dict[str, object]) -> list[tuple[str, object]]:
    overrides: list[tuple[str, object]] = [
        ("policy.type", "rdt"),
        ("backend", "libero"),
        ("backend.libero.suite_name", "libero_object_swap"),
        ("backend.libero.strict_perturbations", True),
        ("backend.libero.max_episode_steps", 720),
        ("main.episode_num", job["episodes"]),
        ("main.use_vlm_stage_recognition", True),
        ("perception.gemini_grounding.enabled", False),
        ("seed", 0),
        ("main.use_guidance", True),
        ("main.guidance_type", "eds"),
        ("main.cached_functions_dir", str(STAGE_CACHED_FUNCTIONS_DIR)),
        ("main.eds_config.population_size", job["population_size"]),
        ("main.eds_config.cem_iters", job["cem_iters"]),
        ("main.eds_config.use_cem", job["use_cem"]),
        ("main.eds_config.num_elites", job["num_elites"]),
        ("main.eds_config.temperature", job["temperature"]),
        ("main.eds_config.renoise_t_max", job["renoise_t_max"]),
        ("main.eds_config.renoise_t_min", job["renoise_t_min"]),
        ("main.eds_eval.reward_mode", job["reward_mode"]),
        ("main.eds_config.initial_sampling_mode", job["initial_sampling_mode"]),
        ("main.eds_config.initial_diversity_scale", job["initial_diversity_scale"]),
        ("main.eds_config.initial_diversity_start_ratio", job["initial_diversity_start_ratio"]),
        ("main.eds_config.truncated_rollout_mode", job["truncated_rollout_mode"]),
        ("main.eds_config.rollout_diversity_scale", job["rollout_diversity_scale"]),
        ("main.eds_config.rollout_diversity_start_ratio", job["rollout_diversity_start_ratio"]),
        ("main.eds_config.rollout_diversity_iters", job["rollout_diversity_iters"]),
        (
            "main.eds_config.rollout_diversity_skip_final_steps",
            job["rollout_diversity_skip_final_steps"],
        ),
        ("main.eds_eval.save_qualitative", True),
        ("main.eds_mechanism_pretest.enabled", True),
        ("main.eds_mechanism_pretest.output_mode", "qualitative_chunk"),
    ]
    overrides.extend((f"main.eds_config.{field}", job[field]) for field in P2_EDS_CONFIG_FIELDS)
    overrides.extend((f"main.{field}", job[field]) for field in P2_MAIN_EXECUTION_FIELDS)
    if job.get("task_ids_filter") is not None:
        overrides.append(("backend.libero.task_ids_filter", job["task_ids_filter"]))
    return overrides


_P2_CREDENTIAL_TEXT_SUFFIXES = {
    ".yaml",
    ".yml",
    ".json",
    ".jsonl",
    ".log",
    ".txt",
    ".md",
    ".csv",
}
_P2_CREDENTIAL_VALUE_PATTERN = re.compile(
    r"(?i)\b(?:openai[_-]?|google[_-]?|anthropic[_-]?)?"
    r"(?:api[_-]?key|auth[_-]?token|access[_-]?token|secret[_-]?key)\b"
    r"[\"']?\s*[:,=]\s*[\"']?([^\s\"',}\]]{8,4096})"
)
_P2_CREDENTIAL_TOKEN_PATTERN = re.compile(
    r"(?i)(?<![a-z0-9_])(?:sk-(?:poe-)?[a-z0-9_-]{8,4096}|AIza[a-z0-9_-]{12,4096})"
)


def _p2_runtime_secret_values() -> set[str]:
    secret_name = re.compile(
        r"(?i)(?:API_KEY|AUTH_TOKEN|ACCESS_TOKEN|SECRET_KEY|CLIENT_SECRET)$"
    )
    return {
        value
        for name, value in os.environ.items()
        if secret_name.search(name)
        and isinstance(value, str)
        and len(value) >= 8
        and value.lower() not in {"dummy", "none", "null", "[redacted]"}
    }


def _p2_text_has_credential(text: str, runtime_secrets: set[str]) -> bool:
    if any(secret in text for secret in runtime_secrets):
        return True
    if _P2_CREDENTIAL_TOKEN_PATTERN.search(text):
        return True
    for match in _P2_CREDENTIAL_VALUE_PATTERN.finditer(text):
        value = match.group(1).strip().lower()
        if len(value) >= 8 and value not in {
            "dummy",
            "none",
            "null",
            "redacted",
            "[redacted]",
            "${oc.env:openai_api_key}",
            "${oc.env:google_api_key}",
        }:
            return True
    return False


def _p2_sensitive_spans(text: str, runtime_secrets: set[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for secret in runtime_secrets:
        start = 0
        while True:
            index = text.find(secret, start)
            if index < 0:
                break
            spans.append((index, index + len(secret)))
            start = index + len(secret)
    spans.extend(match.span() for match in _P2_CREDENTIAL_TOKEN_PATTERN.finditer(text))
    spans.extend(
        match.span()
        for match in _P2_CREDENTIAL_VALUE_PATTERN.finditer(text)
        if match.group(1).strip().lower()
        not in {
            "dummy",
            "none",
            "null",
            "redacted",
            "[redacted]",
            "${oc.env:openai_api_key}",
            "${oc.env:google_api_key}",
        }
    )
    if not spans:
        return []
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _p2_redact_text(text: str, runtime_secrets: set[str]) -> str:
    spans = _p2_sensitive_spans(text, runtime_secrets)
    if not spans:
        return text
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(text[cursor:start])
        pieces.append("[REDACTED]")
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _p2_stream_redact_file(path: Path, runtime_secrets: set[str]) -> None:
    if path.is_symlink():
        raise RuntimeError(f"refusing to redact symlinked archive file: {path}")
    if any(len(secret) > 4096 for secret in runtime_secrets):
        raise RuntimeError("runtime credential exceeds safe streaming overlap")
    temp_path = _p2_safe_child_path(path.parent, f".{path.name}.redacting")
    overlap_size = max(4096, *(len(secret) + 128 for secret in runtime_secrets))
    carry = ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as source, temp_path.open(
            "x", encoding="utf-8"
        ) as destination:
            while True:
                chunk = source.read(P2_CREDENTIAL_SCAN_CHUNK_BYTES)
                if not chunk:
                    destination.write(_p2_redact_text(carry, runtime_secrets))
                    break
                window = carry + chunk
                safe_end = max(0, len(window) - overlap_size)
                for start, end in _p2_sensitive_spans(window, runtime_secrets):
                    if start < safe_end < end:
                        safe_end = start
                        break
                destination.write(
                    _p2_redact_text(window[:safe_end], runtime_secrets)
                )
                carry = window[safe_end:]
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _p2_stream_file_has_credential(
    path: Path,
    runtime_secrets: set[str],
) -> bool:
    try:
        if path.stat().st_size > P2_CREDENTIAL_SCAN_MAX_TEXT_BYTES:
            return True
        overlap = ""
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            while True:
                chunk = handle.read(P2_CREDENTIAL_SCAN_CHUNK_BYTES)
                if not chunk:
                    break
                window = overlap + chunk
                if _p2_text_has_credential(window, runtime_secrets):
                    return True
                overlap = window[-4096:]
    except (OSError, UnicodeError):
        return True
    return False


def _p2_tree_contains_credential(root: Path) -> bool:
    runtime_secrets = _p2_runtime_secret_values()
    try:
        candidates = [
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in _P2_CREDENTIAL_TEXT_SUFFIXES
        ]
    except OSError:
        return True
    return any(
        path.is_symlink() or _p2_stream_file_has_credential(path, runtime_secrets)
        for path in candidates
    )


def _contains_serialized_api_key(job: dict[str, object], output_dir: Path) -> bool:
    if output_dir.exists() and _p2_tree_contains_credential(output_dir):
        return True
    log_path = _log_file_for_job(job)
    if not log_path.exists():
        return False
    if not log_path.is_file() or log_path.is_symlink():
        return True
    return _p2_stream_file_has_credential(log_path, _p2_runtime_secret_values())


def _has_nonempty_qualitative_artifact(metrics_dir: Path) -> bool:
    qualitative_dir = metrics_dir / "qualitative"
    if not qualitative_dir.exists():
        return False
    return any(
        path.is_file() and path.stat().st_size > 0
        for path in qualitative_dir.rglob("*")
    )


def _ffprobe_video_readable(path: Path) -> bool:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "video" in result.stdout.lower()


def _nested_true_fallback(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            (str(key).endswith("fallback_used") and item is True)
            or _nested_true_fallback(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_nested_true_fallback(item) for item in value)
    return False


def _nested_fallback_evidence(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            key_lower = str(key).lower()
            if key_lower.endswith("fallback_used") and item is True:
                return True
            if (
                key_lower.endswith("fallback_reason")
                and item is not None
                and item is not False
                and item != ""
            ):
                return True
            if (
                (key_lower.endswith("grad_failure_count") or key_lower.endswith("fallback_count"))
                and isinstance(item, (int, float))
                and not isinstance(item, bool)
                and float(item) > 0
            ):
                return True
            if _nested_fallback_evidence(item):
                return True
    elif isinstance(value, list):
        return any(_nested_fallback_evidence(item) for item in value)
    return False


def _nested_named_values(value: object, name_fragment: str) -> list[tuple[str, object]]:
    found: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if name_fragment in str(key).lower():
                found.append((str(key), item))
            found.extend(_nested_named_values(item, name_fragment))
    elif isinstance(value, list):
        for item in value:
            found.extend(_nested_named_values(item, name_fragment))
    return found


def _p2_safety_metric_failures(records: list[dict[str, object]]) -> list[str]:
    failures: list[str] = []
    required = {
        "nonfinite_count": ("zero", 0.0),
        "action_mask_violation_max": ("absolute_threshold", 1e-8),
    }
    for record_index, record in enumerate(records):
        for field, (rule, threshold) in required.items():
            values = _nested_named_values(record, field)
            if not values:
                failures.append(f"record {record_index} safety field {field} missing")
                continue
            for matched_key, value in values:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                ):
                    failures.append(
                        f"record {record_index} safety field {matched_key} "
                        "must be numeric and finite"
                    )
                    continue
                value_f = float(value)
                if rule == "zero" and value_f != threshold:
                    failures.append(
                        f"record {record_index} safety field {matched_key} must equal 0"
                    )
                elif rule == "absolute_threshold" and abs(value_f) > threshold:
                    failures.append(
                        f"record {record_index} safety field {matched_key} "
                        f"exceeds {threshold}"
                    )

        for fragment in ("grad_failure_count", "fallback_count"):
            for matched_key, value in _nested_named_values(record, fragment):
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                ):
                    failures.append(
                        f"record {record_index} safety field {matched_key} "
                        "must be numeric and finite"
                    )
                elif float(value) != 0.0:
                    failures.append(
                        f"record {record_index} safety field {matched_key} must equal 0"
                    )
    return failures


def _is_p2_mechanism_artifact(path: Path, episode_root: Path) -> bool:
    relative = path.relative_to(episode_root)
    text = relative.as_posix().lower()
    markers = (
        "mechanism",
        "trace",
        "metadata",
        "tensors/",
        "selection/",
        "memory/",
        "schedule/",
        "single_step",
    )
    return any(marker in text for marker in markers)


_P2_PRETEST_COMMON_ARTIFACTS = (
    "first_chunk_metadata.json",
    "single_step_inner_loop/single_step_particles.csv",
    "tensors/mechanism_trace.pt",
    "full_eds_process/reward_curve.png",
)
_P2_PRETEST_SELECTION_ARTIFACTS = (
    "selection/parent_source_trajectories_3d.png",
    "selection/parent_rank_and_probability.csv",
    "selection/elite_anchor_survival.json",
)
_P2_PRETEST_MEMORY_ARTIFACTS = (
    "memory/fresh_vs_memory_trajectories_3d.png",
    "memory/memory_acceptance.json",
)
_P2_PRETEST_SCHEDULE_ARTIFACTS = (
    "schedule/adaptive_decisions.json",
    "schedule/reward_diversity_schedule.png",
)


def _p2_recursive_artifact_matches(root: Path, suffix: str) -> list[Path]:
    expected_parts = Path(suffix).parts
    return sorted(
        path
        for path in root.rglob(expected_parts[-1])
        if path.is_file()
        and tuple(path.relative_to(root).parts[-len(expected_parts) :])
        == expected_parts
    )


def _p2_artifact_read_failure(path: Path) -> str | None:
    if path.is_symlink():
        return "symlink is not allowed"
    try:
        if path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8", errors="strict") as handle:
                json.load(handle)
        elif path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", errors="strict", newline="") as handle:
                rows = list(csv.reader(handle))
            if len(rows) < 2 or not rows[0] or not any(cell.strip() for cell in rows[0]):
                return "CSV must contain a header and data row"
            if not any(any(cell.strip() for cell in row) for row in rows[1:]):
                return "CSV data rows are empty"
        elif path.suffix.lower() == ".png":
            from PIL import Image

            with Image.open(path) as image:
                if image.format != "PNG" or image.width <= 0 or image.height <= 0:
                    return "image is not a nonempty PNG"
                image.load()
        elif path.suffix.lower() == ".pt":
            from core.eds_mechanism_trace import load_mechanism_trace

            load_mechanism_trace(path)
        else:
            return f"unsupported artifact type {path.suffix!r}"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _p2_memory_trace_roots(episode_root: Path) -> dict[int, Path]:
    required_stages = {
        "memory_fresh_initial",
        "memory_adapted_candidates",
        "memory_composed_initial",
    }
    roots: dict[int, Path] = {}
    for trace_path in _p2_recursive_artifact_matches(
        episode_root, "tensors/mechanism_trace.pt"
    ):
        try:
            from core.eds_mechanism_trace import load_mechanism_trace

            trace = load_mechanism_trace(trace_path)
        except Exception:
            continue
        info = trace.chunk_memory_info or {}
        stage_names = {stage.stage for stage in trace.stages}
        if (
            bool(info.get("enabled"))
            and info.get("chunk_memory_available") is True
            and isinstance(info.get("chunk_memory_candidate_count"), int)
            and not isinstance(info.get("chunk_memory_candidate_count"), bool)
            and int(info["chunk_memory_candidate_count"]) > 0
            and required_stages <= stage_names
        ):
            roots[int(trace.global_step)] = trace_path.parent.parent
    return roots


def _p2_coverage_trace_failures(
    job: dict[str, object], episode_root: Path
) -> list[str]:
    expected_population = int(job["population_size"])
    expected_counts = {
        "elite": int(job["elite_carryover_count"]),
        "anchor_offspring": int(job["parent_anchor_count"]),
    }
    expected_counts["weighted_offspring"] = expected_population - sum(
        expected_counts.values()
    )
    failures: list[str] = []
    for trace_path in _p2_recursive_artifact_matches(
        episode_root, "tensors/mechanism_trace.pt"
    ):
        try:
            from core.eds_mechanism_trace import load_mechanism_trace

            trace = load_mechanism_trace(trace_path)
        except Exception as exc:
            failures.append(
                f"coverage trace unreadable: {type(exc).__name__}: {exc}"
            )
            continue
        per_iter = trace.selection_info.get("per_iter")
        if not isinstance(per_iter, list) or not per_iter:
            failures.append("coverage trace selection per_iter missing or invalid")
            continue
        for iter_index, item in enumerate(per_iter):
            prefix = f"coverage trace iter {iter_index}"
            if not isinstance(item, dict):
                failures.append(f"{prefix} is not a mapping")
                continue
            counts = item.get("parent_count_by_source")
            sources = item.get("parent_sources")
            kinds = item.get("parent_selection_kinds")
            indices = item.get("parent_indices")
            normalized_counts = (
                {
                    key: _p2_nonnegative_int(counts.get(key))
                    for key in expected_counts
                }
                if isinstance(counts, dict)
                else {}
            )
            if normalized_counts != expected_counts:
                failures.append(f"{prefix} parent_count_by_source invalid")
            if (
                not isinstance(sources, list)
                or len(sources) != expected_population
                or any(not isinstance(source, str) for source in sources)
                or {key: sources.count(key) for key in expected_counts}
                != expected_counts
            ):
                failures.append(f"{prefix} parent_sources invalid")
            if (
                not isinstance(kinds, list)
                or len(kinds) != expected_population
                or any(not isinstance(kind, str) for kind in kinds)
            ):
                failures.append(f"{prefix} parent_selection_kinds invalid")
            if (
                not isinstance(indices, list)
                or len(indices) != expected_population
                or any(_p2_nonnegative_int(index) is None for index in indices)
            ):
                failures.append(f"{prefix} parent_indices invalid")
    return failures


def _p2_pretest_qualitative_failures(
    job: dict[str, object],
    episode_root: Path,
    episode_metrics: list[dict[str, object]] | None = None,
) -> tuple[list[str], int, int]:
    if job.get("level") != "p2_adaptive_eds_rbf_pretest":
        return [], 0, 0

    required = list(_P2_PRETEST_COMMON_ARTIFACTS)
    if (
        job.get("parent_weighting_mode") == "adaptive_ess"
        or job.get("parent_coverage_mode") == "eef_kcenter"
    ):
        required.extend(_P2_PRETEST_SELECTION_ARTIFACTS)
    if (
        job.get("rollout_diversity_control_mode") == "adaptive_band"
        or job.get("search_schedule_mode") == "adaptive"
    ):
        required.extend(_P2_PRETEST_SCHEDULE_ARTIFACTS)

    failures: list[str] = []
    artifact_count = 0
    readable_count = 0

    if job.get("parent_coverage_mode") == "eef_kcenter":
        failures.extend(_p2_coverage_trace_failures(job, episode_root))

    if job.get("chunk_population_mode") == "warm_start_mix":
        metric_steps: set[int] = set()
        for record in episode_metrics or []:
            if record.get("chunk_memory_available") is not True:
                continue
            candidate_count = record.get("chunk_memory_candidate_count")
            if (
                not isinstance(candidate_count, int)
                or isinstance(candidate_count, bool)
                or candidate_count <= 0
            ):
                continue
            global_step = record.get("global_step")
            if not isinstance(global_step, int) or isinstance(global_step, bool):
                failures.append(
                    "memory metrics missing integer global_step for available candidates"
                )
                continue
            metric_steps.add(global_step)

        trace_roots = _p2_memory_trace_roots(episode_root)
        extra_trace_steps = sorted(set(trace_roots) - metric_steps)
        first_metric_step = min(metric_steps) if metric_steps else None
        if first_metric_step is not None and first_metric_step not in trace_roots:
            failures.append(
                "memory trace missing for first eligible metric global_step: "
                + str(first_metric_step)
            )
        if extra_trace_steps:
            failures.append(
                "memory trace has no matching metric global_step(s): "
                + ",".join(str(step) for step in extra_trace_steps)
            )
        evidence_steps = set(trace_roots) & metric_steps
        if first_metric_step is not None:
            evidence_steps.add(first_metric_step)
        for step in sorted(evidence_steps):
            chunk_root = trace_roots.get(
                step, episode_root / f"chunk_{step:06d}"
            )
            for suffix in _P2_PRETEST_MEMORY_ARTIFACTS:
                matches = _p2_recursive_artifact_matches(chunk_root, suffix)
                if not matches:
                    failures.append(
                        f"memory global_step {step} required qualitative artifact missing: {suffix}"
                    )
                    continue
                artifact_count += len(matches)
                for path in matches:
                    read_failure = _p2_artifact_read_failure(path)
                    if read_failure is None:
                        readable_count += 1
                    else:
                        failures.append(
                            f"memory global_step {step} required qualitative artifact "
                            f"unreadable: {suffix} ({read_failure})"
                        )

    for suffix in required:
        matches = _p2_recursive_artifact_matches(episode_root, suffix)
        if not matches:
            failures.append(f"required qualitative artifact missing: {suffix}")
            continue
        artifact_count += len(matches)
        for path in matches:
            read_failure = _p2_artifact_read_failure(path)
            if read_failure is None:
                readable_count += 1
            else:
                failures.append(
                    f"required qualitative artifact unreadable: {suffix} ({read_failure})"
                )
    return failures, artifact_count, readable_count


def _p2_has_normal_libero_fallback(job: dict[str, object], output_dir: Path) -> bool:
    candidates = [
        output_dir / "results.txt",
        output_dir / ".hydra" / "config.yaml",
        output_dir / ".hydra" / "overrides.yaml",
        _log_file_for_job(job),
    ]
    phrases = (
        "falling back to normal libero",
        "fallback to normal libero",
        "libero-pro unavailable",
        "strict_perturbations=false",
        "strict_perturbations: false",
    )
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        if any(phrase in text for phrase in phrases):
            return True
    return False


def _p2_component_telemetry_failures(
    job: dict[str, object], records: list[dict[str, object]]
) -> list[str]:
    def has_field(value: object, field_names: tuple[str, ...]) -> bool:
        if isinstance(value, dict):
            return any(name in value for name in field_names) or any(
                has_field(item, field_names) for item in value.values()
            )
        if isinstance(value, list):
            return any(has_field(item, field_names) for item in value)
        return False

    def field_values(value: object, field_names: tuple[str, ...]) -> list[object]:
        found: list[object] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if key in field_names:
                    found.append(item)
                found.extend(field_values(item, field_names))
        elif isinstance(value, list):
            for item in value:
                found.extend(field_values(item, field_names))
        return found

    required: list[tuple[bool, tuple[str, ...], str]] = [
        (
            job["parent_weighting_mode"] == "adaptive_ess",
            (
                "selection_ess_ratio_mean",
                "selection_ess_ratio",
                "selection_effective_sample_size_ratio",
            ),
            "adaptive ESS telemetry missing",
        ),
        (
            job["rollout_diversity_control_mode"] == "adaptive_band",
            (
                "adaptive_rbf_scale_requested_mean",
                "adaptive_rbf_scale_requested",
                "adaptive_rbf_requested_scale",
                "rollout_diversity_scale_requested",
            ),
            "adaptive RBF telemetry missing",
        ),
        (
            job["parent_coverage_mode"] == "eef_kcenter",
            ("anchor_count_observed", "parent_anchor_count_observed"),
            "coverage telemetry missing",
        ),
        (
            int(job["elite_carryover_count"]) > 0,
            ("elite_carryover_count_observed",),
            "elite telemetry missing",
        ),
        (
            job["chunk_population_mode"] == "warm_start_mix",
            ("chunk_memory_used",),
            "chunk memory telemetry missing",
        ),
        (
            job["search_schedule_mode"] == "adaptive",
            ("eds_iters_executed", "resolved_renoise_steps", "search_schedule_mode"),
            "adaptive search telemetry missing",
        ),
        (
            job["execution_horizon_mode"] == "adaptive_prefix",
            ("execution_horizon_resolved",),
            "adaptive execution telemetry missing",
        ),
    ]
    failures = []
    for enabled, alternatives, failure in required:
        if enabled and not any(has_field(record, alternatives) for record in records):
            failures.append(failure)

    validation_specs = [
        (
            job["parent_weighting_mode"] == "adaptive_ess",
            (
                "selection_ess_ratio_mean",
                "selection_ess_ratio",
                "selection_effective_sample_size_ratio",
            ),
            lambda value: (
                (number := _p2_finite_number(value)) is not None
                and 0.0 <= number <= 1.0
            ),
            "adaptive ESS telemetry invalid",
        ),
        (
            job["parent_weighting_mode"] == "adaptive_ess",
            ("selection_degenerate_reward_count",),
            lambda value: _p2_nonnegative_int(value) is not None,
            "adaptive ESS degeneracy telemetry invalid",
        ),
        (
            job["rollout_diversity_control_mode"] == "adaptive_band",
            (
                "adaptive_rbf_scale_requested_mean",
                "adaptive_rbf_scale_requested",
                "adaptive_rbf_requested_scale",
                "rollout_diversity_scale_requested",
            ),
            lambda value: _p2_finite_number(value) is not None,
            "adaptive RBF telemetry invalid",
        ),
        (
            job["rollout_diversity_control_mode"] == "adaptive_band",
            (
                "adaptive_rbf_scale_applied_mean",
                "adaptive_rbf_scale_applied",
                "resolved_rollout_diversity_scale",
            ),
            lambda value: _p2_finite_number(value) is not None,
            "adaptive RBF telemetry invalid",
        ),
        (
            job["rollout_diversity_control_mode"] == "adaptive_band",
            (
                "adaptive_rbf_active_iter_count",
                "adaptive_rbf_active_particle_count",
            ),
            lambda value: _p2_nonnegative_int(value) is not None,
            "adaptive RBF activity telemetry invalid",
        ),
        (
            job["parent_coverage_mode"] == "eef_kcenter",
            ("anchor_count_observed", "parent_anchor_count_observed"),
            lambda value: _p2_nonnegative_int(value) is not None,
            "coverage telemetry invalid",
        ),
        (
            int(job["elite_carryover_count"]) > 0,
            ("elite_carryover_count_observed",),
            lambda value: _p2_nonnegative_int(value) is not None,
            "elite telemetry invalid",
        ),
        (
            job["chunk_population_mode"] == "warm_start_mix",
            ("chunk_memory_candidate_count",),
            lambda value: _p2_nonnegative_int(value) is not None,
            "chunk memory telemetry invalid",
        ),
        (
            job["chunk_population_mode"] == "warm_start_mix",
            ("chunk_memory_available", "chunk_memory_used"),
            lambda value: isinstance(value, bool),
            "chunk memory telemetry invalid",
        ),
        (
            job["chunk_population_mode"] == "warm_start_mix",
            ("chunk_memory_fraction_observed", "chunk_memory_acceptance_ratio"),
            lambda value: (
                (number := _p2_finite_number(value)) is not None
                and 0.0 <= number <= 1.0
            ),
            "chunk memory telemetry invalid",
        ),
        (
            job["execution_horizon_mode"] == "adaptive_prefix",
            ("execution_horizon_resolved",),
            lambda value: (
                (parsed := _p2_nonnegative_int(value)) is not None and parsed > 0
            ),
            "adaptive execution telemetry invalid",
        ),
        (
            job["search_schedule_mode"] == "adaptive",
            ("eds_iters_executed", "n_trunc_steps"),
            lambda value: _p2_nonnegative_int(value) is not None,
            "adaptive search telemetry invalid",
        ),
    ]
    for enabled, names, validator, failure in validation_specs:
        if not enabled:
            continue
        values = [
            item
            for record in records
            for item in field_values(record, names)
            if item is not None
        ]
        if any(not validator(value) for value in values):
            failures.append(failure)

    if job["parent_weighting_mode"] == "adaptive_ess":
        ess_ratio_names = (
            "selection_ess_ratio_mean",
            "selection_ess_ratio",
            "selection_effective_sample_size_ratio",
        )
        ess_ratio_values = [
            item
            for record in records
            for item in field_values(record, ess_ratio_names)
        ]
        if not any(_p2_finite_number(value) is not None for value in ess_ratio_values):
            failures.append("finite adaptive ESS ratio telemetry missing")

    requires_per_iter = (
        job["parent_weighting_mode"] == "adaptive_ess"
        or job["rollout_diversity_control_mode"] == "adaptive_band"
        or job["search_schedule_mode"] == "adaptive"
    )
    if requires_per_iter:
        for record_index, record in enumerate(records):
            if "per_iter" not in record:
                continue
            per_iter = record.get("per_iter")
            if not isinstance(per_iter, list) or any(
                not isinstance(item, dict) for item in per_iter
            ):
                failures.append(
                    f"record {record_index} per_iter telemetry invalid"
                )
    if job["chunk_population_mode"] == "warm_start_mix" and not any(
        record.get("chunk_memory_used") is True for record in records
    ):
        failures.append("chunk memory was never used")
    return failures


def _p2_stage_query_failures(
    stage_events: list[dict[str, object]],
    episode_metadata: list[dict[str, object]],
    expected_episode_ids: set[int],
    *,
    max_episode_steps: int,
) -> tuple[list[str], int]:
    failures: list[str] = []
    metadata_by_episode: dict[int, dict[str, object]] = {}
    for record in episode_metadata:
        episode_id = record.get("episode_id")
        if isinstance(episode_id, int) and not isinstance(episode_id, bool):
            metadata_by_episode[episode_id] = record

    required_fields = {
        "episode_id",
        "task_id",
        "episode_seed",
        "global_step",
        "chunk_id",
        "trigger_reason",
        "stage_before",
        "stage_after",
        "guidance_before",
        "guidance_after",
        "parsed_stage",
        "parsed_guidance",
        "query_latency_s",
        "query_status",
        "query_ok",
    }
    allowed_statuses = {
        "ok",
        "error",
        "completed_without_result_metadata",
        "skipped",
    }
    successful_episode_ids: set[int] = set()
    successful_count = 0

    event_identity_counts: dict[tuple[int, int], int] = {}
    for event in stage_events:
        episode_id = event.get("episode_id")
        global_step = event.get("global_step")
        if (
            isinstance(episode_id, int)
            and not isinstance(episode_id, bool)
            and isinstance(global_step, int)
            and not isinstance(global_step, bool)
        ):
            identity = (episode_id, global_step)
            event_identity_counts[identity] = event_identity_counts.get(identity, 0) + 1
    duplicate_event_identities = sorted(
        identity for identity, count in event_identity_counts.items() if count > 1
    )
    if duplicate_event_identities:
        failures.append(
            "duplicate stage query episode/global_step identity: "
            + ",".join(
                f"{episode_id}/{global_step}"
                for episode_id, global_step in duplicate_event_identities
            )
        )

    for index, event in enumerate(stage_events):
        prefix = f"stage query event {index}"
        missing = sorted(required_fields - set(event))
        if missing:
            failures.append(f"{prefix} fields missing: {','.join(missing)}")
            continue

        integer_fields = ("episode_id", "task_id", "episode_seed", "global_step", "chunk_id")
        if any(
            not isinstance(event.get(field), int) or isinstance(event.get(field), bool)
            for field in integer_fields
        ):
            failures.append(f"{prefix} integer field type invalid")
            continue

        episode_id = int(event["episode_id"])
        global_step = int(event["global_step"])
        chunk_id = int(event["chunk_id"])
        if episode_id not in expected_episode_ids:
            failures.append(f"{prefix} episode_id out of range")
            continue
        if not 0 <= global_step <= max_episode_steps:
            failures.append(f"{prefix} global_step out of range")
            continue
        if chunk_id < 0:
            failures.append(f"{prefix} chunk_id out of range")
            continue

        status = event.get("query_status")
        query_ok = event.get("query_ok")
        latency = event.get("query_latency_s")
        if not isinstance(status, str) or status not in allowed_statuses:
            failures.append(f"{prefix} status invalid")
            continue
        if query_ok is not None and not isinstance(query_ok, bool):
            failures.append(f"{prefix} query_ok type invalid")
            continue
        if status == "ok" and query_ok is not True:
            failures.append(f"{prefix} successful status/query_ok conflict")
            continue
        if status != "ok" and query_ok is True:
            failures.append(f"{prefix} failed status/query_ok conflict")
            continue
        if (
            not isinstance(latency, (int, float))
            or isinstance(latency, bool)
            or not math.isfinite(float(latency))
            or float(latency) < 0.0
        ):
            failures.append(f"{prefix} latency invalid")
            continue
        if not isinstance(event.get("trigger_reason"), str) or not str(
            event["trigger_reason"]
        ).strip():
            failures.append(f"{prefix} trigger_reason invalid")
            continue
        if any(
            not isinstance(event.get(field), bool)
            for field in ("guidance_before", "guidance_after", "parsed_guidance")
        ):
            failures.append(f"{prefix} guidance field type invalid")
            continue
        if any(
            value is not None
            and not (
                (isinstance(value, int) and not isinstance(value, bool) and value >= 0)
                or (isinstance(value, str) and bool(value.strip()))
            )
            for value in (
                event.get("stage_before"),
                event.get("stage_after"),
                event.get("parsed_stage"),
            )
        ):
            failures.append(f"{prefix} stage field type/range invalid")
            continue

        if status != "ok":
            continue
        metadata = metadata_by_episode.get(episode_id)
        if metadata is None:
            failures.append(f"{prefix} has no aligned episode metadata")
            continue
        if event["task_id"] != metadata.get("task_id"):
            failures.append(f"{prefix} task_id does not match episode metadata")
            continue
        if event["episode_seed"] != metadata.get("episode_seed"):
            failures.append(f"{prefix} episode_seed does not match episode metadata")
            continue
        successful_episode_ids.add(episode_id)
        successful_count += 1

    missing_success = sorted(expected_episode_ids - successful_episode_ids)
    if missing_success:
        failures.append(
            "successful stage query missing for episodes: "
            + ",".join(str(value) for value in missing_success)
        )
    return failures, successful_count


def _p2_job_validity(job: dict[str, object]) -> dict[str, object]:
    output_dir = _output_dir(job)
    metrics_dir = output_dir / "eds_eval"
    failures: list[str] = []
    if output_dir.exists():
        try:
            symlinks = [
                path.relative_to(output_dir).as_posix()
                for path in output_dir.rglob("*")
                if path.is_symlink()
            ]
        except OSError as exc:
            symlinks = []
            failures.append(f"cannot inspect output evidence tree: {exc}")
        if symlinks:
            failures.append(
                "symlinked output evidence is not allowed: " + ",".join(symlinks)
            )
    expected_episodes = int(job["episodes"])
    results_path = output_dir / "results.txt"
    try:
        parsed = _parse_results_file(results_path)
    except (TypeError, ValueError):
        parsed = {"success": None, "total": None, "success_rate": None}
        failures.append("results.txt is not parseable")
    if not results_path.is_file():
        failures.append("results.txt missing")
    elif parsed["total"] != expected_episodes:
        failures.append(f"results total {parsed['total']} != episodes {expected_episodes}")
    elif (
        not isinstance(parsed["success"], int)
        or not 0 <= parsed["success"] <= expected_episodes
        or not isinstance(parsed["success_rate"], (int, float))
        or not math.isfinite(float(parsed["success_rate"]))
        or abs(float(parsed["success_rate"]) - 100.0 * parsed["success"] / expected_episodes) > 0.02
    ):
        failures.append("results.txt success count/rate is inconsistent")

    config_path = output_dir / ".hydra" / "config.yaml"
    overrides_path = output_dir / ".hydra" / "overrides.yaml"
    hydra_path = output_dir / ".hydra" / "hydra.yaml"
    hydra_text = _hydra_text(output_dir)
    strict_verified = _hydra_bool_verified(hydra_text, "backend.libero.strict_perturbations")
    suite_verified = _hydra_suite_verified(hydra_text, "libero_object_swap")
    if not strict_verified:
        failures.append("strict perturbations not verified")
    if not suite_verified:
        failures.append("suite libero_object_swap not verified")
    expected_overrides = _p2_normalized_command_overrides(job)
    serialized_expected_overrides = {
        key: value
        for key, value in expected_overrides.items()
        if key != "hydra.run.dir"
    }
    try:
        actual_overrides = _parse_p2_overrides_file(overrides_path)
    except (OSError, UnicodeError, ValueError) as exc:
        actual_overrides = {}
        failures.append(str(exc))
    missing_overrides = sorted(
        set(serialized_expected_overrides) - set(actual_overrides)
    )
    extra_overrides = sorted(
        set(actual_overrides) - set(serialized_expected_overrides)
    )
    mismatched_overrides = sorted(
        key
        for key in set(serialized_expected_overrides) & set(actual_overrides)
        if _canonical_json(serialized_expected_overrides[key])
        != _canonical_json(actual_overrides[key])
    )
    if missing_overrides:
        failures.append("hydra overrides missing: " + ",".join(missing_overrides))
    if extra_overrides:
        failures.append("hydra overrides unexpected: " + ",".join(extra_overrides))
    if mismatched_overrides:
        failures.append("hydra overrides value mismatch: " + ",".join(mismatched_overrides))
    failures.extend(_p2_structured_config_failures(config_path, expected_overrides))
    failures.extend(_p2_hydra_runtime_failures(hydra_path, output_dir))

    fingerprint_path = output_dir / "config_fingerprint.txt"
    manifest_path = output_dir / "job_manifest.json"
    expected_fingerprint = _p2_config_fingerprint(job)
    if not fingerprint_path.is_file():
        failures.append("config_fingerprint.txt missing")
    elif fingerprint_path.read_text(encoding="utf-8", errors="replace").strip() != expected_fingerprint:
        failures.append("config fingerprint mismatch")
    if not manifest_path.is_file():
        failures.append("job_manifest.json missing")
    else:
        serialized_manifest: dict[str, object] = {}
        try:
            manifest_value = json.loads(
                manifest_path.read_text(encoding="utf-8", errors="strict")
            )
        except (OSError, UnicodeError, ValueError, RecursionError):
            failures.append("job_manifest.json is not parseable")
        else:
            if not isinstance(manifest_value, dict):
                failures.append("job_manifest.json must be a JSON object")
            else:
                serialized_manifest = manifest_value
        if serialized_manifest.get("config_fingerprint") != expected_fingerprint:
            failures.append("job manifest fingerprint mismatch")
        if serialized_manifest.get("manifest_sha256") != job.get("manifest_sha256"):
            failures.append("job manifest Stage B hash mismatch")
        if serialized_manifest and serialized_manifest != _p2_job_manifest_payload(job):
            failures.append("job manifest payload mismatch")

    expected_episode_ids = set(range(expected_episodes))
    video_count = 0
    for episode_id in sorted(expected_episode_ids):
        episode_dir = output_dir / f"episode_{episode_id + 1}"
        videos = list(episode_dir.glob("*.mp4")) if episode_dir.is_dir() else []
        video_count += len(videos)
        if len(videos) != 1:
            failures.append(f"episode {episode_id} video count {len(videos)} != 1")
        elif not _ffprobe_video_readable(videos[0]):
            failures.append(f"episode {episode_id} video is not ffprobe-readable")
    all_videos = list(output_dir.glob("episode_*/*.mp4"))
    if len(all_videos) != expected_episodes:
        failures.append(f"total video count {len(all_videos)} != {expected_episodes}")

    metrics_path = metrics_dir / "eds_metrics.jsonl"
    metrics, metrics_jsonl_failures = _read_p2_jsonl_strict(
        metrics_path, label="metrics"
    )
    failures.extend(metrics_jsonl_failures)
    if not metrics_path.is_file() or metrics_path.stat().st_size <= 0:
        failures.append("metrics JSONL missing or empty")
    metric_identity_counts: dict[tuple[int, int], int] = {}
    for record_index, record in enumerate(metrics):
        episode_id = record.get("episode")
        global_step = record.get("global_step")
        if (
            not isinstance(episode_id, int)
            or isinstance(episode_id, bool)
            or not isinstance(global_step, int)
            or isinstance(global_step, bool)
        ):
            failures.append(f"metrics record {record_index} identity field type invalid")
            continue
        if episode_id not in expected_episode_ids or not 0 <= global_step <= 720:
            failures.append(f"metrics record {record_index} identity out of range")
            continue
        identity = (episode_id, global_step)
        metric_identity_counts[identity] = metric_identity_counts.get(identity, 0) + 1
    duplicate_metric_identities = sorted(
        identity for identity, count in metric_identity_counts.items() if count > 1
    )
    if duplicate_metric_identities:
        failures.append(
            "duplicate metrics episode/global_step identity: "
            + ",".join(
                f"{episode_id}/{global_step}"
                for episode_id, global_step in duplicate_metric_identities
            )
        )
    metric_episode_ids = {
        int(record["episode"])
        for record in metrics
        if isinstance(record.get("episode"), int)
        and not isinstance(record.get("episode"), bool)
    }
    if metric_episode_ids != expected_episode_ids:
        failures.append(
            f"metrics episode coverage {sorted(metric_episode_ids)} != {sorted(expected_episode_ids)}"
        )
    if any(_nested_fallback_evidence(record) for record in metrics):
        failures.append("explicit fallback recorded")
    failures.extend(_p2_safety_metric_failures(metrics))
    failures.extend(_p2_component_telemetry_failures(job, metrics))

    qualitative_root = metrics_dir / "qualitative"
    mechanism_count = 0
    mechanism_episode_count = 0
    qualitative_artifact_failures: list[str] = []
    required_qualitative_artifacts = 0
    readable_qualitative_artifacts = 0
    for episode_id in sorted(expected_episode_ids):
        episode_qualitative = qualitative_root / f"episode_{episode_id:03d}"
        files = [path for path in episode_qualitative.rglob("*") if path.is_file() and path.stat().st_size > 0]
        if not files:
            failures.append(f"episode {episode_id} qualitative evidence missing")
        episode_mechanism_count = sum(
            1 for path in files if _is_p2_mechanism_artifact(path, episode_qualitative)
        )
        mechanism_count += episode_mechanism_count
        if episode_mechanism_count <= 0:
            failures.append(f"episode {episode_id} mechanism evidence missing")
        else:
            mechanism_episode_count += 1
        artifact_failures, artifact_count, readable_count = (
            _p2_pretest_qualitative_failures(
                job,
                episode_qualitative,
                [
                    record
                    for record in metrics
                    if record.get("episode") == episode_id
                ],
            )
        )
        qualitative_artifact_failures.extend(
            f"episode {episode_id} {failure}" for failure in artifact_failures
        )
        required_qualitative_artifacts += artifact_count + sum(
            " missing:" in failure for failure in artifact_failures
        )
        readable_qualitative_artifacts += readable_count
    failures.extend(qualitative_artifact_failures)

    episode_metadata, metadata_jsonl_failures = _read_p2_jsonl_strict(
        metrics_dir / "episode_metadata.jsonl", label="episode metadata"
    )
    failures.extend(metadata_jsonl_failures)
    expected_task_ids = [
        int(value)
        for value in (job.get("task_ids_filter") or list(range(expected_episodes)))
    ]
    metadata_identity_counts: dict[int, int] = {}
    valid_metadata: list[dict[str, object]] = []
    for record_index, record in enumerate(episode_metadata):
        if any(
            not isinstance(record.get(field), int)
            or isinstance(record.get(field), bool)
            for field in ("episode_id", "episode_seed", "task_id")
        ):
            failures.append(f"episode metadata record {record_index} schema invalid")
            continue
        episode_id = int(record["episode_id"])
        task_id = int(record["task_id"])
        if episode_id not in expected_episode_ids:
            failures.append(f"episode metadata record {record_index} identity out of range")
            continue
        metadata_identity_counts[episode_id] = (
            metadata_identity_counts.get(episode_id, 0) + 1
        )
        if task_id != expected_task_ids[episode_id]:
            failures.append(
                f"episode metadata record {record_index} task_id mismatch"
            )
            continue
        valid_metadata.append(record)
    duplicate_metadata_ids = sorted(
        episode_id
        for episode_id, count in metadata_identity_counts.items()
        if count > 1
    )
    if duplicate_metadata_ids:
        failures.append(
            "duplicate episode metadata identity: "
            + ",".join(str(value) for value in duplicate_metadata_ids)
        )
    metadata_ids = {int(record["episode_id"]) for record in valid_metadata}
    if metadata_ids != expected_episode_ids:
        failures.append("episode metadata incomplete")
    recorded_task_ids = [int(record["task_id"]) for record in valid_metadata]
    if sorted(recorded_task_ids) != sorted(expected_task_ids):
        failures.append(
            "episode metadata task ids mismatch: "
            f"recorded={sorted(recorded_task_ids)} expected={sorted(expected_task_ids)}"
        )

    stage_events, stage_jsonl_failures = _read_p2_jsonl_strict(
        metrics_dir / "stage_events.jsonl", label="stage events"
    )
    failures.extend(stage_jsonl_failures)
    stage_query_failures, successful_stage_queries = _p2_stage_query_failures(
        stage_events,
        episode_metadata,
        expected_episode_ids,
        max_episode_steps=720,
    )
    failures.extend(stage_query_failures)

    runner_log = _log_file_for_job(job)
    runner_log_verified = runner_log.is_file() and not runner_log.is_symlink()
    if not runner_log_verified:
        failures.append("runner log missing or not a regular file")
    if _p2_has_normal_libero_fallback(job, output_dir):
        failures.append("normal LIBERO fallback detected")
    if _contains_serialized_api_key(job, output_dir):
        failures.append("API key material found in serialized artifacts")
    return {
        "valid": not failures,
        "failure_reason": "; ".join(dict.fromkeys(failures)),
        "strict_perturbations_verified": strict_verified,
        "suite_verified": suite_verified,
        "videos": video_count,
        "metrics_records": len(metrics),
        "qualitative_artifact": (
            mechanism_episode_count == expected_episodes
            and not qualitative_artifact_failures
        ),
        "required_qualitative_artifacts": required_qualitative_artifacts,
        "readable_qualitative_artifacts": readable_qualitative_artifacts,
        "qualitative_artifact_failures": "; ".join(qualitative_artifact_failures),
        "stage_events": len(stage_events),
        "successful_stage_queries": successful_stage_queries,
        "episode_metadata_records": len(episode_metadata),
        "config_fingerprint_verified": "config fingerprint mismatch" not in failures,
        "runner_log_verified": runner_log_verified,
    }


def _job_validity(job: dict[str, object]) -> dict[str, object]:
    if job.get("level") in P2_LEVELS:
        return _p2_job_validity(job)
    output_dir = _output_dir(job)
    metrics_dir = output_dir / "eds_eval"
    results_path = output_dir / "results.txt"
    metrics_path = metrics_dir / "eds_metrics.jsonl"
    failures: list[str] = []

    parsed = _parse_results_file(results_path)
    if not results_path.exists():
        failures.append("results.txt missing")
    elif parsed["total"] != job.get("episodes"):
        failures.append(
            f"results total {parsed['total']} != episodes {job.get('episodes')}"
        )

    metrics = _read_jsonl(metrics_path)
    if not metrics_path.exists() or metrics_path.stat().st_size <= 0:
        failures.append("metrics JSONL missing or empty")
    elif not metrics:
        failures.append("metrics JSONL has no parseable records")

    videos = _artifact_counts(output_dir)["videos"]
    expected_videos = int(job.get("episodes", 0))
    if videos < expected_videos:
        failures.append(f"videos {videos}/{expected_videos}")

    hydra_text = _hydra_text(output_dir)
    hydra_overrides_text = _hydra_overrides_text(output_dir)
    strict_verified = _hydra_bool_verified(
        hydra_text,
        "backend.libero.strict_perturbations",
    ) or _hydra_bool_verified(hydra_text, "strict_perturbations")
    suite_verified = _hydra_suite_verified(hydra_text, str(job["suite"]))
    if not hydra_text:
        failures.append(".hydra overrides/config missing")
    if not strict_verified:
        failures.append("strict perturbations not verified")
    if not suite_verified:
        failures.append(f"suite {job['suite']} not verified")
    level = job.get("level")
    is_stage_level = level in {
        "stage_recognition_pretest",
        "stage_recognition_ablation",
    }
    if is_stage_level:
        config_path = output_dir / ".hydra" / "config.yaml"
        overrides_path = output_dir / ".hydra" / "overrides.yaml"
        if not config_path.exists():
            failures.append(".hydra/config.yaml missing")
        if not overrides_path.exists():
            failures.append(".hydra/overrides.yaml missing")
    if level in {
        "object_swap_ood_rbf",
        "stage_recognition_pretest",
        "stage_recognition_ablation",
    } and hydra_text:
        expected_overrides = (
            _expected_stage_recognition_hydra_overrides(job)
            if level in {"stage_recognition_pretest", "stage_recognition_ablation"}
            else _expected_object_swap_hydra_overrides(job)
        )
        for key, expected in expected_overrides:
            verified = (
                _hydra_exact_override_verified(hydra_overrides_text, key, expected)
                if is_stage_level
                else _hydra_assignment_verified(hydra_text, key, expected)
            )
            if not verified:
                failures.append(f"hydra override mismatch: {key}={_hydra_scalar(expected)}")

    qualitative_ok = _has_nonempty_qualitative_artifact(metrics_dir)
    if not qualitative_ok:
        failures.append("qualitative artifact missing or empty")

    stage_events: list[dict[str, object]] = []
    successful_stage_queries = 0
    episode_metadata: list[dict[str, object]] = []
    if is_stage_level:
        expected_episode_ids = set(range(expected_videos))
        for episode_id in sorted(expected_episode_ids):
            episode_videos = list(
                (output_dir / f"episode_{episode_id + 1}").glob("*.mp4")
            )
            if len(episode_videos) != 1:
                failures.append(
                    f"episode {episode_id} video count {len(episode_videos)} != 1"
                )

        metric_episode_ids = {
            int(record["episode"])
            for record in metrics
            if isinstance(record.get("episode"), int)
        }
        missing_metric_episodes = expected_episode_ids - metric_episode_ids
        if missing_metric_episodes:
            failures.append(
                "metrics missing episodes "
                + ",".join(str(value) for value in sorted(missing_metric_episodes))
            )

        qualitative_root = metrics_dir / "qualitative"
        for episode_id in sorted(expected_episode_ids):
            episode_qualitative = qualitative_root / f"episode_{episode_id:03d}"
            if not any(
                path.is_file() and path.stat().st_size > 0
                for path in episode_qualitative.rglob("*")
            ):
                failures.append(f"episode {episode_id} qualitative evidence missing")

        episode_metadata = _read_jsonl(metrics_dir / "episode_metadata.jsonl")
        if len(episode_metadata) != expected_videos:
            failures.append(
                "episode seed metadata count "
                f"{len(episode_metadata)}/{expected_videos}"
            )
        metadata_episode_ids = [
            int(record["episode_id"])
            for record in episode_metadata
            if isinstance(record.get("episode_id"), int)
        ]
        if len(metadata_episode_ids) != len(set(metadata_episode_ids)):
            failures.append("duplicate episode seed metadata")
        metadata_by_episode = {
            int(record["episode_id"]): record
            for record in episode_metadata
            if isinstance(record.get("episode_id"), int)
        }
        valid_seed_episode_ids = {
            episode_id
            for episode_id, record in metadata_by_episode.items()
            if isinstance(record.get("episode_seed"), int)
            and isinstance(record.get("task_id"), int)
        }
        if valid_seed_episode_ids != expected_episode_ids:
            failures.append(
                "episode seed metadata incomplete: "
                f"{len(valid_seed_episode_ids)}/{expected_videos}"
            )
        expected_task_ids = job.get("task_ids_filter")
        if expected_task_ids is not None:
            recorded_task_ids = {
                int(record["task_id"])
                for record in episode_metadata
                if isinstance(record.get("task_id"), int)
            }
            if recorded_task_ids != {int(value) for value in expected_task_ids}:
                failures.append(
                    "pretest task ids mismatch: "
                    f"recorded={sorted(recorded_task_ids)} "
                    f"expected={sorted(int(value) for value in expected_task_ids)}"
                )

        stage_events_path = metrics_dir / "stage_events.jsonl"
        stage_events = _read_jsonl(stage_events_path)
        successful_stage_queries = sum(
            1
            for event in stage_events
            if event.get("query_ok") is True or event.get("query_status") == "ok"
        )
        if bool(job.get("stage_recognition_enabled")) and successful_stage_queries <= 0:
            failures.append("no successful stage query recorded")
        required_query_fields = {
            "episode_id",
            "task_id",
            "episode_seed",
            "global_step",
            "chunk_id",
            "trigger_reason",
            "stage_before",
            "stage_after",
            "guidance_before",
            "guidance_after",
            "parsed_stage",
            "parsed_guidance",
            "query_latency_s",
            "query_status",
        }
        for event in stage_events:
            if event.get("query_ok") is True or event.get("query_status") == "ok":
                missing_fields = required_query_fields - set(event)
                if missing_fields:
                    failures.append(
                        "successful stage query fields missing: "
                        + ",".join(sorted(missing_fields))
                    )
                    break
        if _contains_serialized_api_key(job, output_dir):
            failures.append("API key material found in serialized artifacts")

    return {
        "valid": not failures,
        "failure_reason": "; ".join(failures),
        "strict_perturbations_verified": strict_verified,
        "suite_verified": suite_verified,
        "videos": videos,
        "metrics_records": len(metrics),
        "qualitative_artifact": qualitative_ok,
        "stage_events": len(stage_events),
        "successful_stage_queries": successful_stage_queries,
        "episode_metadata_records": len(episode_metadata),
    }


def _status_rows_by_job_id() -> dict[str, dict[str, str]]:
    if not STATUS_CSV.exists():
        return {}
    with STATUS_CSV.open(newline="", encoding="utf-8") as handle:
        return {row["job_id"]: row for row in csv.DictReader(handle)}


def _failure_excerpt(log_file: Path, max_lines: int = 5) -> str:
    if not log_file.exists():
        return "log missing"
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    markers = [
        "Traceback",
        "Error executing job",
        "RemoteDisconnected",
        "CUDA out of memory",
        "failed.",
        "KeyboardInterrupt",
    ]
    hits = [line.strip() for line in lines if any(marker in line for marker in markers)]
    if hits:
        return " | ".join(hits[-max_lines:])
    tail = [line.strip() for line in lines[-max_lines:] if line.strip()]
    return " | ".join(tail) if tail else "no failure excerpt"


def write_status(
    rows: list[dict[str, object]],
    path: Path | None = None,
) -> None:
    ensure_dirs()
    destination = path or STATUS_CSV
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in STATUS_FIELDS})


def _status_row(job: dict[str, object], status: str, gpu: str = "") -> dict[str, object]:
    output_dir = _output_dir(job)
    return {
        **job,
        "status": status,
        "output_dir": str(output_dir),
        "metrics_dir": str(output_dir / "eds_eval"),
        "log_file": str(_log_file_for_job(job)),
        "gpu": gpu,
    }


def _p2_status_path(level: str, real_root: Path | None = None) -> Path:
    root = Path(real_root if real_root is not None else P2_STATUS_ROOT)
    return _p2_safe_child_path(root, _p2_stage_dir(level), "run_manifest.csv")


def init(
    level: str,
    episodes: int,
    *,
    manifest_path: str | Path | None = None,
) -> int:
    p2_real_root: Path | None = None
    if level in P2_LEVELS:
        p2_real_root = _validate_p2_output_storage()
    jobs = build_jobs(level, episodes, manifest_path=manifest_path)
    if p2_real_root is not None:
        for job in jobs:
            _bind_p2_execution_context(
                job,
                real_root=p2_real_root,
                storage_enforced=True,
            )
    status_path = (
        _p2_status_path(level, p2_real_root)
        if level in P2_LEVELS
        else
        STAGE_STATUS_CSV
        if level in {"stage_recognition_pretest", "stage_recognition_ablation"}
        else STATUS_CSV
    )
    write_status([_status_row(job, "pending") for job in jobs], path=status_path)
    print(status_path)
    return 0


def _evidence_lines(evidence: str | Iterable[str]) -> list[str]:
    if isinstance(evidence, str):
        return [evidence] if evidence else []
    return [str(item) for item in evidence]


def _p2_pretest_job_evidence(job: dict[str, object]) -> dict[str, object]:
    output_dir = _output_dir(job)
    try:
        results = _parse_results_file(output_dir / "results.txt")
    except (OSError, TypeError, ValueError):
        results = {"success": None, "total": None, "success_rate": None}
    metrics = _read_jsonl(output_dir / "eds_eval" / "eds_metrics.jsonl")
    stage_events = _read_jsonl(output_dir / "eds_eval" / "stage_events.jsonl")
    validity = _p2_job_validity(job)
    fallback = any(_nested_fallback_evidence(record) for record in metrics)
    safety_failures = _p2_safety_metric_failures(metrics) if metrics else []
    nonfinite_values = [
        float(value)
        for record in metrics
        for _key, value in _nested_named_values(record, "nonfinite_count")
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ]
    mask_values = [
        abs(float(value))
        for record in metrics
        for _key, value in _nested_named_values(record, "action_mask_violation_max")
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ]
    safety_status = (
        "INCONCLUSIVE"
        if not metrics
        else "PASS"
        if not safety_failures and not fallback
        else "FAIL"
    )
    return {
        "job": job,
        "output_dir": output_dir,
        "results": results,
        "metrics": metrics,
        "stage_events": stage_events,
        "validity": validity,
        "safety_status": safety_status,
        "fallback": fallback,
        "nonfinite_max": max(nonfinite_values) if nonfinite_values else None,
        "mask_violation_max": max(mask_values) if mask_values else None,
    }


def _p2_pretest_gate_status(
    evidence: dict[str, object], *, samples_present: bool, passed: bool
) -> str:
    if not samples_present:
        return "INCONCLUSIVE"
    if evidence["validity"]["valid"] is not True or evidence["safety_status"] != "PASS":
        return "FAIL"
    return "PASS" if passed else "FAIL"


def _p2_pretest_iter_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for record in records:
        per_iter = record.get("per_iter")
        if not isinstance(per_iter, list):
            continue
        result.extend(item for item in per_iter if isinstance(item, dict))
    return result


def _p2_pretest_gate_rows(
    evidence_by_label: dict[str, dict[str, object]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    ess = evidence_by_label["p2_sel_ess05"]
    ess_metrics = ess["metrics"]
    ess_target = float(ess["job"]["selection_ess_target_ratio"])
    ess_iter_records = _p2_pretest_iter_records(ess_metrics)
    ess_values = [
        float(item["selection_ess_ratio"])
        for item in ess_iter_records
        if isinstance(item.get("selection_ess_ratio"), (int, float))
        and not isinstance(item.get("selection_ess_ratio"), bool)
        and math.isfinite(float(item["selection_ess_ratio"]))
    ]
    ess_error = _finite_median(abs(value - ess_target) for value in ess_values)
    degenerate_iterations = int(
        sum(
            int(record["selection_degenerate_reward_count"])
            for record in ess_metrics
            if _p2_nonnegative_int(
                record.get("selection_degenerate_reward_count")
            )
            is not None
        )
    )
    degenerate_chunks = sum(
        (_p2_nonnegative_int(record.get("selection_degenerate_reward_count")) or 0)
        > 0
        for record in ess_metrics
    )
    equal_reward_iterations = sum(
        item.get("selection_degenerate_reward") is True
        for item in ess_iter_records
    )
    beta_max = float(ess["job"]["selection_beta_max"])
    unreachable_target_iterations = sum(
        item.get("selection_degenerate_reward") is False
        and isinstance(item.get("selection_beta"), (int, float))
        and not isinstance(item.get("selection_beta"), bool)
        and math.isfinite(float(item["selection_beta"]))
        and math.isclose(float(item["selection_beta"]), beta_max, rel_tol=1e-9, abs_tol=1e-9)
        and isinstance(item.get("selection_ess_ratio"), (int, float))
        and not isinstance(item.get("selection_ess_ratio"), bool)
        and math.isfinite(float(item["selection_ess_ratio"]))
        and float(item["selection_ess_ratio"]) > ess_target + 1e-6
        for item in ess_iter_records
    )
    rows.append(
        {
            "gate": "Adaptive ESS",
            "profile": "p2_sel_ess05",
            "samples": f"iterations={len(ess_values)}; chunks={len(ess_metrics)}",
            "values": (
                f"target={ess_target:.3f}; median_abs_error={_fmt_float(ess_error, 6)}; "
                f"equal_reward_iterations={equal_reward_iterations}; "
                f"unreachable_target_iterations={unreachable_target_iterations}"
            ),
            "status": _p2_pretest_gate_status(
                ess,
                samples_present=bool(ess_values),
                passed=(
                    ess_error is not None
                    and ess_error <= 0.1
                    and ess["job"]["parent_weighting_mode"] == "adaptive_ess"
                ),
            ),
            "detail": (
                f"degenerate_iterations={degenerate_iterations}; "
                f"degenerate_chunks={degenerate_chunks}; all samples included"
            ),
        }
    )

    rbf = evidence_by_label["p2_adaptrbf_t10_s20"]
    rbf_metrics = rbf["metrics"]
    rbf_iter_records = _p2_pretest_iter_records(rbf_metrics)
    finite_applied_items = [
        item
        for item in rbf_iter_records
        if isinstance(item.get("adaptive_rbf_scale_applied"), (int, float))
        and not isinstance(item.get("adaptive_rbf_scale_applied"), bool)
        and math.isfinite(float(item["adaptive_rbf_scale_applied"]))
    ]
    missing_activity_items = [
        item
        for item in finite_applied_items
        if not isinstance(item.get("adaptive_rbf_active_particle_count"), (int, float))
        or isinstance(item.get("adaptive_rbf_active_particle_count"), bool)
        or not math.isfinite(float(item["adaptive_rbf_active_particle_count"]))
    ]
    active_items = [
        item
        for item in finite_applied_items
        if isinstance(item.get("adaptive_rbf_active_particle_count"), (int, float))
        and not isinstance(item.get("adaptive_rbf_active_particle_count"), bool)
        and math.isfinite(float(item["adaptive_rbf_active_particle_count"]))
        and float(item["adaptive_rbf_active_particle_count"]) > 0
    ]
    inactive_iterations = sum(
        isinstance(item.get("adaptive_rbf_active_particle_count"), (int, float))
        and not isinstance(item.get("adaptive_rbf_active_particle_count"), bool)
        and math.isfinite(float(item["adaptive_rbf_active_particle_count"]))
        and float(item["adaptive_rbf_active_particle_count"]) <= 0
        for item in finite_applied_items
    )
    active_applied_scales = [
        float(item["adaptive_rbf_scale_applied"]) for item in active_items
    ]
    active_requested_scales = [
        float(item["adaptive_rbf_scale_requested"])
        for item in active_items
        if isinstance(item.get("adaptive_rbf_scale_requested"), (int, float))
        and not isinstance(item.get("adaptive_rbf_scale_requested"), bool)
        and math.isfinite(float(item["adaptive_rbf_scale_requested"]))
    ]
    unique_active_scales = sorted(
        {round(value, 6) for value in active_applied_scales}
    )
    chunk_active_counts = [
        int(record["adaptive_rbf_active_iter_count"])
        for record in rbf["metrics"]
        if isinstance(record.get("adaptive_rbf_active_iter_count"), int)
        and not isinstance(record.get("adaptive_rbf_active_iter_count"), bool)
        and int(record["adaptive_rbf_active_iter_count"]) >= 0
    ]
    chunk_activity_missing = len(chunk_active_counts) != len(rbf["metrics"])
    chunk_active_iterations = sum(chunk_active_counts)
    activity_contradiction = (
        not chunk_activity_missing
        and chunk_active_iterations != len(active_items)
    )
    if rbf["validity"]["valid"] is not True or rbf["safety_status"] != "PASS":
        rbf_status = "FAIL"
        rbf_detail = "strict validity or safety failed"
    elif missing_activity_items:
        rbf_status = "INCONCLUSIVE"
        rbf_detail = (
            "per-iteration active particle telemetry missing; "
            "chunk-level active counts cannot prove which scales were active"
        )
    elif chunk_activity_missing:
        rbf_status = "INCONCLUSIVE"
        rbf_detail = "chunk-level adaptive RBF activity telemetry missing"
    elif activity_contradiction:
        rbf_status = "FAIL"
        rbf_detail = "per-iter/chunk activity contradiction"
    elif not active_items:
        rbf_status = "FAIL"
        rbf_detail = "no explicitly active adaptive RBF iteration observed"
    else:
        rbf_status = (
            "PASS"
            if len(unique_active_scales) >= 2
            and unique_active_scales != [20.0]
            else "FAIL"
        )
        rbf_detail = "only explicitly active per-iteration scales are gate evidence"
    rows.append(
        {
            "gate": "Adaptive rollout RBF",
            "profile": "p2_adaptrbf_t10_s20",
            "samples": (
                f"active_iterations={len(active_items)}; "
                f"chunk_active_iterations={chunk_active_iterations}; "
                f"inactive_iterations={inactive_iterations}; "
                f"missing_activity_iterations={len(missing_activity_items)}"
            ),
            "values": (
                f"unique_active_applied={unique_active_scales}; "
                f"active_requested_samples={len(active_requested_scales)}"
            ),
            "status": rbf_status,
            "detail": rbf_detail,
        }
    )

    coverage = evidence_by_label["p2_divres_k4_e2"]
    expected_sources = {"elite": 2, "anchor_offspring": 4, "weighted_offspring": 10}
    selection_iterations: list[dict[str, object]] = []
    trace_failures = 0
    for trace_path in sorted(
        (coverage["output_dir"] / "eds_eval" / "qualitative").rglob(
            "mechanism_trace.pt"
        )
    ):
        try:
            from core.eds_mechanism_trace import load_mechanism_trace

            trace = load_mechanism_trace(trace_path)
            selection_iterations.extend(
                item
                for item in (trace.selection_info.get("per_iter") or [])
                if isinstance(item, dict)
            )
        except Exception:
            trace_failures += 1
    matching_iterations = 0
    anchor_shortfalls: list[int] = []
    anchor_reason_counts: dict[str, int] = {}
    for item in selection_iterations:
        counts = item.get("parent_count_by_source")
        sources = item.get("parent_sources")
        kinds = item.get("parent_selection_kinds")
        indices = item.get("parent_indices")
        explicit_shortfall = item.get("anchor_shortfall")
        if isinstance(explicit_shortfall, int) and not isinstance(
            explicit_shortfall, bool
        ):
            shortfall = max(0, explicit_shortfall)
        elif isinstance(counts, dict) and _p2_nonnegative_int(
            counts.get("anchor_offspring")
        ) is not None:
            shortfall = max(
                0,
                expected_sources["anchor_offspring"]
                - int(counts["anchor_offspring"]),
            )
        else:
            shortfall = expected_sources["anchor_offspring"]
        anchor_shortfalls.append(shortfall)
        explicit_reason = item.get("anchor_fallback_reason")
        reason = (
            str(explicit_reason)
            if isinstance(explicit_reason, str) and explicit_reason.strip()
            else "not_serialized"
            if shortfall > 0
            else "none"
        )
        anchor_reason_counts[reason] = anchor_reason_counts.get(reason, 0) + 1
        normalized_counts = (
            {
                key: _p2_nonnegative_int(counts.get(key))
                for key in expected_sources
            }
            if isinstance(counts, dict)
            else {}
        )
        if not (
            normalized_counts == expected_sources
            and isinstance(sources, list)
            and len(sources) == 16
            and all(isinstance(source, str) for source in sources)
            and {key: sources.count(key) for key in expected_sources} == expected_sources
            and isinstance(kinds, list)
            and len(kinds) == 16
            and all(isinstance(kind, str) for kind in kinds)
            and isinstance(indices, list)
            and len(indices) == 16
            and all(_p2_nonnegative_int(index) is not None for index in indices)
        ):
            continue
        source_kind_ok = all(
            (source != "elite" or kind == "deterministic_elite")
            and (source != "anchor_offspring" or kind == "deterministic_anchor")
            for source, kind in zip(sources, kinds)
        )
        deterministic_indices = [
            index
            for index, source in zip(indices, sources)
            if source in {"elite", "anchor_offspring"}
        ]
        if source_kind_ok and len(deterministic_indices) == len(set(deterministic_indices)):
            matching_iterations += 1
    rows.append(
        {
            "gate": "k-center + elite carryover",
            "profile": "p2_divres_k4_e2",
            "samples": f"trace_iterations={len(selection_iterations)}",
            "values": (
                f"matching_iterations={matching_iterations}/{len(selection_iterations)}; "
                "expected=elite:2,anchor:4,weighted:10; "
                f"anchor_shortfall_iterations={sum(value > 0 for value in anchor_shortfalls)}; "
                f"anchor_shortfall_total={sum(anchor_shortfalls)}"
            ),
            "status": _p2_pretest_gate_status(
                coverage,
                samples_present=bool(selection_iterations),
                passed=(
                    matching_iterations == len(selection_iterations)
                    and trace_failures == 0
                    and all(value == 0 for value in anchor_shortfalls)
                    and not any(
                        reason != "none" for reason in anchor_reason_counts
                    )
                ),
            ),
            "detail": (
                f"unreadable traces={trace_failures}; anchor_reasons="
                + ",".join(
                    f"{reason}:{count}"
                    for reason, count in sorted(anchor_reason_counts.items())
                    if reason != "none"
                )
                if any(reason != "none" for reason in anchor_reason_counts)
                else f"unreadable traces={trace_failures}; anchor_reasons=none"
            ),
        }
    )

    memory = evidence_by_label["p2_memory25"]
    memory_metrics = memory["metrics"]
    memory_job = memory["job"]
    expected_episode_ids = set(range(int(memory_job["episodes"])))
    expected_population = int(memory_job["population_size"])
    expected_fraction = float(memory_job["chunk_memory_fraction"])
    expected_candidates = max(
        0,
        min(
            expected_population,
            int(round(expected_population * expected_fraction)),
        ),
    )
    metrics_by_episode: dict[int, list[dict[str, object]]] = {}
    for record in memory_metrics:
        episode = record.get("episode")
        if isinstance(episode, int) and not isinstance(episode, bool):
            metrics_by_episode.setdefault(episode, []).append(record)
    for episode_records in metrics_by_episode.values():
        episode_records.sort(
            key=lambda item: (
                item.get("global_step")
                if isinstance(item.get("global_step"), (int, float))
                and not isinstance(item.get("global_step"), bool)
                else math.inf,
                item.get("chunk_id")
                if isinstance(item.get("chunk_id"), (int, float))
                and not isinstance(item.get("chunk_id"), bool)
                else math.inf,
            )
        )
    fresh_first = sum(
        bool(records)
        and records[0].get("chunk_memory_available") is False
        and records[0].get("chunk_memory_used") is False
        for records in metrics_by_episode.values()
    )
    first_eligible_by_episode: dict[int, dict[str, object]] = {}
    known_usage_failures: list[str] = []
    missing_cross_evidence: list[str] = []
    valid_use_episodes: set[int] = set()
    acceptance_values: list[float] = []
    fraction_values: list[float] = []
    selected_sources: list[str] = []
    for episode in sorted(expected_episode_ids):
        records = metrics_by_episode.get(episode, [])
        if not records:
            known_usage_failures.append(f"episode {episode} metrics missing")
            continue
        if not (
            records[0].get("chunk_memory_available") is False
            and records[0].get("chunk_memory_used") is False
        ):
            known_usage_failures.append(f"episode {episode} first chunk is not fresh")
        first_eligible = next(
            (
                record
                for record in records[1:]
                if record.get("chunk_memory_available") is True
            ),
            None,
        )
        if first_eligible is None:
            known_usage_failures.append(
                f"episode {episode} first memory-eligible chunk missing"
            )
            continue
        first_eligible_by_episode[episode] = first_eligible
        candidate_count = first_eligible.get("chunk_memory_candidate_count")
        if (
            not isinstance(candidate_count, int)
            or isinstance(candidate_count, bool)
            or candidate_count != expected_candidates
        ):
            known_usage_failures.append(
                f"episode {episode} candidate_count={candidate_count!r} "
                f"expected={expected_candidates}"
            )
        if first_eligible.get("chunk_memory_used") is not True:
            known_usage_failures.append(f"episode {episode} memory was not used")
        source_counts = first_eligible.get("chunk_memory_source_counts")
        memory_count = (
            source_counts.get("memory") if isinstance(source_counts, dict) else None
        )
        if (
            not isinstance(memory_count, int)
            or isinstance(memory_count, bool)
            or memory_count <= 0
        ):
            known_usage_failures.append(
                f"episode {episode} memory source count is not positive"
            )
            continue

        acceptance = first_eligible.get("chunk_memory_acceptance_ratio")
        fraction = first_eligible.get("chunk_memory_fraction_observed")
        selected_source = first_eligible.get("selected_chunk_population_source")
        acceptance_ok = (
            isinstance(acceptance, (int, float))
            and not isinstance(acceptance, bool)
            and math.isfinite(float(acceptance))
            and expected_candidates > 0
            and math.isclose(
                float(acceptance),
                memory_count / expected_candidates,
                rel_tol=1e-6,
                abs_tol=1e-8,
            )
        )
        fraction_ok = (
            isinstance(fraction, (int, float))
            and not isinstance(fraction, bool)
            and math.isfinite(float(fraction))
            and math.isclose(
                float(fraction),
                memory_count / expected_population,
                rel_tol=1e-6,
                abs_tol=1e-8,
            )
        )
        selected_source_ok = (
            isinstance(selected_source, str)
            and bool(selected_source.strip())
            and isinstance(source_counts, dict)
            and isinstance(source_counts.get(selected_source), int)
            and int(source_counts[selected_source]) > 0
        )
        if not acceptance_ok:
            missing_cross_evidence.append(
                f"episode {episode} acceptance ratio evidence missing or inconsistent"
            )
        else:
            acceptance_values.append(float(acceptance))
        if not fraction_ok:
            missing_cross_evidence.append(
                f"episode {episode} observed fraction evidence missing or inconsistent"
            )
        else:
            fraction_values.append(float(fraction))
        if not selected_source_ok:
            missing_cross_evidence.append(
                f"episode {episode} selected source evidence missing or inconsistent"
            )
        else:
            selected_sources.append(str(selected_source))
        if (
            candidate_count == expected_candidates
            and first_eligible.get("chunk_memory_used") is True
            and acceptance_ok
            and fraction_ok
            and selected_source_ok
        ):
            valid_use_episodes.add(episode)
    stage_changes = [
        event
        for event in memory["stage_events"]
        if event.get("stage_before") is not None
        and event.get("stage_after") is not None
        and event.get("stage_before") != event.get("stage_after")
        and isinstance(event.get("episode_id"), int)
        and isinstance(event.get("global_step"), int)
    ]
    eds_enabled_changes = [
        event for event in stage_changes if event.get("guidance_after") is True
    ]
    guidance_off_changes = [
        event for event in stage_changes if event.get("guidance_after") is False
    ]
    guidance_unknown_changes = [
        event
        for event in stage_changes
        if event.get("guidance_after") is not True
        and event.get("guidance_after") is not False
    ]
    reset_matches = 0
    reset_evidence_missing = 0
    reset_evidence_invalid = 0
    consumed_metric_keys: set[tuple[int, int]] = set()
    for event in eds_enabled_changes:
        episode_id = int(event["episode_id"])
        global_step = int(event["global_step"])
        metric_key = (episode_id, global_step)
        exact = [
            record
            for record in metrics_by_episode.get(episode_id, [])
            if isinstance(record.get("global_step"), int)
            and not isinstance(record.get("global_step"), bool)
            and int(record["global_step"]) == global_step
        ]
        if not exact or metric_key in consumed_metric_keys:
            reset_evidence_missing += 1
            continue
        if len(exact) != 1:
            reset_evidence_invalid += 1
            continue
        consumed_metric_keys.add(metric_key)
        if (
            exact[0].get("chunk_memory_reset_reason") == "stage_change"
            and exact[0].get("chunk_memory_used") is False
        ):
            reset_matches += 1
        else:
            reset_evidence_invalid += 1
    if not memory_metrics:
        memory_status = "INCONCLUSIVE"
        memory_detail = "memory metrics not observed"
    elif memory["validity"]["valid"] is not True or memory["safety_status"] != "PASS":
        memory_status = "FAIL"
        memory_detail = "strict validity or safety failed"
    elif known_usage_failures:
        memory_status = "FAIL"
        memory_detail = "; ".join(known_usage_failures)
    elif missing_cross_evidence:
        memory_status = "INCONCLUSIVE"
        memory_detail = "; ".join(missing_cross_evidence)
    elif not stage_changes:
        memory_status = "INCONCLUSIVE"
        memory_detail = "stage change not observed; reset cannot be assessed"
    elif guidance_unknown_changes:
        memory_status = "INCONCLUSIVE"
        memory_detail = "stage-change guidance state missing or invalid"
    elif reset_evidence_invalid:
        memory_status = "FAIL"
        memory_detail = "EDS-enabled exact-step reset evidence is invalid"
    elif reset_evidence_missing:
        memory_status = "INCONCLUSIVE"
        memory_detail = "EDS-enabled reset metric missing at exact stage-change step"
    else:
        memory_status = "PASS"
        memory_detail = (
            "memory use and all EDS-enabled exact-step resets verified; "
            "guidance-off transitions are not applicable"
        )
    rows.append(
        {
            "gate": "Cross-chunk population memory",
            "profile": "p2_memory25",
            "samples": (
                f"first_eligible={len(first_eligible_by_episode)}; "
                f"episodes_with_valid_use={len(valid_use_episodes)}/"
                f"{len(expected_episode_ids)}; "
                f"stage_changes={len(stage_changes)}; "
                f"eds_enabled={len(eds_enabled_changes)}; "
                f"guidance_off={len(guidance_off_changes)}"
            ),
            "values": (
                f"expected_candidates={expected_candidates}; "
                f"first_eligible_valid={len(valid_use_episodes)}/"
                f"{len(expected_episode_ids)}; fresh_first={fresh_first}/"
                f"{len(expected_episode_ids)}; acceptance={acceptance_values}; "
                f"fraction={fraction_values}; selected_sources={sorted(set(selected_sources))}; "
                f"exact_resets={reset_matches}/{len(eds_enabled_changes)}"
            ),
            "status": memory_status,
            "detail": memory_detail,
        }
    )

    schedule = evidence_by_label["p2_schedule_contact"]
    schedule_metrics = schedule["metrics"]
    renoise_values = [
        int(item["n_trunc_steps"])
        for item in _p2_pretest_iter_records(schedule_metrics)
        if isinstance(item.get("n_trunc_steps"), int)
        and not isinstance(item.get("n_trunc_steps"), bool)
    ]
    horizon_values = [
        int(record["execution_horizon_resolved"])
        for record in schedule_metrics
        if isinstance(record.get("execution_horizon_resolved"), int)
        and not isinstance(record.get("execution_horizon_resolved"), bool)
    ]
    executed_values = [
        int(record["eds_iters_executed"])
        for record in schedule_metrics
        if isinstance(record.get("eds_iters_executed"), int)
        and not isinstance(record.get("eds_iters_executed"), bool)
    ]
    unique_renoise = sorted(set(renoise_values))
    unique_horizons = sorted(set(horizon_values))
    early_stop_chunks = sum(
        record.get("early_stop_used") is True for record in schedule_metrics
    )
    early_stop_reason_counts: dict[str, int] = {}
    for record in schedule_metrics:
        if record.get("early_stop_used") is not True:
            continue
        reason = record.get("early_stop_reason")
        reason_text = (
            str(reason) if isinstance(reason, str) and reason.strip() else "missing_reason"
        )
        early_stop_reason_counts[reason_text] = (
            early_stop_reason_counts.get(reason_text, 0) + 1
        )
    early_stop_reasons = (
        ",".join(
            f"{reason}:{count}"
            for reason, count in sorted(early_stop_reason_counts.items())
        )
        or "none"
    )
    rows.append(
        {
            "gate": "Adaptive search / execution schedule",
            "profile": "p2_schedule_contact",
            "samples": (
                f"renoise_iterations={len(renoise_values)}; horizons={len(horizon_values)}"
            ),
            "values": (
                f"unique_renoise={unique_renoise}; unique_horizons={unique_horizons}; "
                f"eds_iters={sorted(set(executed_values))}; "
                f"early_stop_chunks={early_stop_chunks}; "
                f"early_stop_reasons={early_stop_reasons}"
            ),
            "status": _p2_pretest_gate_status(
                schedule,
                samples_present=bool(renoise_values or horizon_values),
                passed=len(unique_renoise) >= 2 or len(unique_horizons) >= 2,
            ),
            "detail": "EDS iteration variation is supporting evidence only",
        }
    )
    return rows


def _p2_markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def write_p2_adaptive_eds_rbf_pretest_report() -> Path:
    jobs = build_jobs("p2_adaptive_eds_rbf_pretest", episodes=2)
    if len(jobs) != 6:
        raise RuntimeError(f"P2 pretest report requires exactly 6 jobs, got {len(jobs)}")
    evidence_by_label = {
        str(job["label"]): _p2_pretest_job_evidence(job) for job in jobs
    }
    gates = _p2_pretest_gate_rows(evidence_by_label)
    gate_statuses = [row["status"] for row in gates]
    all_jobs_valid = all(
        evidence["validity"]["valid"] is True
        for evidence in evidence_by_label.values()
    )
    overall = (
        "FAIL"
        if "FAIL" in gate_statuses or (not all_jobs_valid and any(e["metrics"] for e in evidence_by_label.values()))
        else "INCONCLUSIVE"
        if "INCONCLUSIVE" in gate_statuses or not all_jobs_valid
        else "PASS"
    )
    lines = [
        "# P2 Adaptive EDS/RBF Mechanism Pretest Report",
        "",
        f"- Generated: `{now_iso()}`",
        "- Scope: `libero_object_swap`, Tasks `[0, 8]`, 6 jobs, 12 episodes.",
        f"- Overall mechanism status: **{overall}**.",
        "- Gate status vocabulary: PASS / FAIL / INCONCLUSIVE.",
        "- SR is descriptive only and is not used to eliminate profiles from Stage A.",
        "",
        "## Job validity and safety",
        "",
        "| Profile | SR (non-elimination) | Validity | Artifact | Strict | Stage | Safety | Failure |",
        "|---|---:|---|---|---|---|---|---|",
    ]
    for job in jobs:
        evidence = evidence_by_label[str(job["label"])]
        validity = evidence["validity"]
        results = evidence["results"]
        sr = "-"
        if isinstance(results.get("success"), int) and isinstance(results.get("total"), int):
            sr = f"{results['success']}/{results['total']} ({_fmt_float(results.get('success_rate'), 2)}%)"
        artifact = (
            f"{'PASS' if validity['qualitative_artifact'] else 'FAIL'} "
            f"{validity.get('readable_qualitative_artifacts', 0)}/"
            f"{validity.get('required_qualitative_artifacts', 0)} readable"
        )
        strict = (
            "PASS"
            if validity["strict_perturbations_verified"] and validity["suite_verified"]
            else "FAIL"
        )
        stage = (
            f"{'PASS' if validity['successful_stage_queries'] >= 2 else 'FAIL'} "
            f"{validity['successful_stage_queries']}/2 queries"
        )
        safety = (
            f"{evidence['safety_status']} nonfinite={_fmt_float(evidence['nonfinite_max'], 0)}; "
            f"mask={_fmt_float(evidence['mask_violation_max'], 8)}; "
            f"fallback={'yes' if evidence['fallback'] else 'no'}"
        )
        lines.append(
            "| "
            + " | ".join(
                _p2_markdown_cell(value)
                for value in (
                    job["label"],
                    sr,
                    "VALID" if validity["valid"] else "INVALID",
                    artifact,
                    strict,
                    stage,
                    safety,
                    validity["failure_reason"] or "none",
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Mechanism gates",
            "",
            "| Gate | Profile | Samples | Values | Status | Detail |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in gates:
        lines.append(
            "| "
            + " | ".join(
                _p2_markdown_cell(row[key])
                for key in ("gate", "profile", "samples", "values", "status", "detail")
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Mechanism pretest outcomes gate code correctness and evidence completeness only.",
            "- Episode success/failure and SR are retained for context, never for profile elimination.",
            "- Any invalid job, unreadable artifact, strict-suite failure, stage-query gap, nonfinite value, mask violation, fallback, or serialized credential remains visible above.",
        ]
    )
    report_text = "\n".join(lines) + "\n"
    runtime_secrets = _p2_runtime_secret_values()
    report_text = _p2_redact_text(report_text, runtime_secrets)
    if _p2_text_has_credential(report_text, runtime_secrets):
        raise RuntimeError("refusing to write P2 pretest report containing credential material")
    P2_PRETEST_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    P2_PRETEST_REPORT_PATH.write_text(report_text, encoding="utf-8")
    return P2_PRETEST_REPORT_PATH


def write_level_report(level: str, verdict: str, evidence: str | Iterable[str]) -> Path:
    ensure_dirs()
    if level not in LEVEL_REPORTS or level == "final":
        raise ValueError(f"Unknown report level: {level}")
    path = EVIDENCE_ROOT / LEVEL_REPORTS[level]
    evidence_items = _evidence_lines(evidence)
    lines = [
        f"# RDT+EDS {level.upper()} Evaluation Report",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        f"Verdict: `{verdict}`",
        "",
        "## Evidence",
        "",
    ]
    lines.extend(f"- {item}" for item in evidence_items)
    if not evidence_items:
        lines.append("- No evidence supplied.")
    lines.extend(
        [
            "",
            "## Analysis",
            "",
            "This report is generated by `scripts/rdt_eds_eval_runner.py`.",
            "A human reviewer must compare saved metrics, qualitative artifacts, and failure labels against the protocol before changing the verdict.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _aggressive_rbf_rows(episodes: int) -> list[dict[str, object]]:
    rows = []
    for job in build_jobs("level2", episodes):
        output_dir = RUN_ROOT / str(job["job_id"])
        metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
        parsed = _parse_results_file(output_dir / "results.txt")
        metrics = _read_jsonl(metrics_path)
        action_mask_violation_max = _metric_max(metrics, "action_mask_violation_max")
        fallback_count = sum(
            1 for record in metrics if record.get("initial_diversity_fallback_used") is True
        )
        rows.append(
            {
                "job": job,
                "label": job["label"],
                "scale": job.get("initial_diversity_scale"),
                "start_ratio": job.get("initial_diversity_start_ratio"),
                "complete": _job_has_complete_outputs(job),
                "success": parsed["success"],
                "total": parsed["total"],
                "success_rate": parsed["success_rate"],
                "records": len(metrics),
                "diversity_steps": _metric_mean(metrics, "initial_diversity_steps"),
                "fallback_count": fallback_count,
                "grad_failures": _metric_sum(
                    metrics,
                    "initial_diversity_grad_failure_count",
                ),
                "nonfinite": _metric_sum(metrics, "nonfinite_count"),
                "action_mask_violation_max": action_mask_violation_max,
                "initial_eef_diversity_before_rbf": _metric_mean(
                    metrics,
                    "initial_eef_diversity_before_rbf",
                ),
                "initial_eef_diversity_after_rbf_phase": _metric_mean(
                    metrics,
                    "initial_eef_diversity_after_rbf_phase",
                ),
                "initial_eef_diversity_final": _metric_mean(
                    metrics,
                    "initial_eef_diversity_final",
                ),
                "initial_eef_diversity_retention_ratio": _metric_mean(
                    metrics,
                    "initial_eef_diversity_retention_ratio",
                ),
                "endpoint_spread_before_rbf": _metric_mean(
                    metrics,
                    "endpoint_spread_before_rbf",
                ),
                "endpoint_spread_after_rbf_phase": _metric_mean(
                    metrics,
                    "endpoint_spread_after_rbf_phase",
                ),
                "endpoint_spread_final": _metric_mean(
                    metrics,
                    "endpoint_spread_final",
                ),
                "selected_reward": _metric_mean(metrics, "selected_reward"),
                "target_distance_after": _metric_mean(
                    metrics,
                    "target_distance_after",
                ),
                "select_action_latency_s": _metric_mean(
                    metrics,
                    "select_action_latency_s",
                ),
                "initial_sampler_latency_s": _metric_mean(
                    metrics,
                    "initial_sampler_latency_s",
                ),
                "output_dir": output_dir,
                "metrics_path": metrics_path,
            }
        )
    return rows


def _delta(value: object, baseline: object) -> float | None:
    if not isinstance(value, (int, float)) or not isinstance(baseline, (int, float)):
        return None
    if isinstance(value, bool) or isinstance(baseline, bool):
        return None
    value_f = float(value)
    baseline_f = float(baseline)
    if not math.isfinite(value_f) or not math.isfinite(baseline_f):
        return None
    return value_f - baseline_f


def _success_cell(row: dict[str, object]) -> str:
    if row["success"] is None or row["total"] is None:
        return "-"
    return f"{row['success']}/{row['total']}"


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _is_aggressive_rbf_row(row: dict[str, object]) -> bool:
    return str(row["label"]) not in {"iid_baseline", "rbf_s1_start_null"}


def _missing_required_metrics(row: dict[str, object]) -> list[str]:
    required = [
        "initial_eef_diversity_final",
        "endpoint_spread_final",
        "selected_reward",
        "target_distance_after",
    ]
    if row["label"] != "iid_baseline" and int(row["fallback_count"]) == 0:
        required.extend(
            [
                "initial_eef_diversity_before_rbf",
                "initial_eef_diversity_after_rbf_phase",
                "initial_eef_diversity_retention_ratio",
                "endpoint_spread_before_rbf",
                "endpoint_spread_after_rbf_phase",
            ]
        )
    return [field for field in required if not _is_finite_number(row.get(field))]


def _safety_verdict(row: dict[str, object]) -> str:
    action_mask_violation = row["action_mask_violation_max"]
    mask_ok = (
        action_mask_violation is None
        or (
            isinstance(action_mask_violation, (int, float))
            and not isinstance(action_mask_violation, bool)
            and float(action_mask_violation) == 0.0
        )
    )
    passed = (
        int(row["fallback_count"]) == 0
        and int(row["grad_failures"]) == 0
        and int(row["nonfinite"]) == 0
        and mask_ok
    )
    return "pass" if passed else "fail"


def _mechanism_verdict(
    row: dict[str, object],
    iid_row: dict[str, object] | None,
    default_rbf_row: dict[str, object] | None,
) -> str:
    if not _is_aggressive_rbf_row(row):
        return "reference"
    if iid_row is None or default_rbf_row is None:
        return "blocked"
    required = [
        row.get("initial_eef_diversity_after_rbf_phase"),
        row.get("initial_eef_diversity_final"),
        row.get("endpoint_spread_final"),
        iid_row.get("initial_eef_diversity_final"),
        iid_row.get("endpoint_spread_final"),
        default_rbf_row.get("initial_eef_diversity_after_rbf_phase"),
    ]
    if not all(_is_finite_number(value) for value in required):
        return "blocked"
    after_ok = (
        float(row["initial_eef_diversity_after_rbf_phase"])
        > float(default_rbf_row["initial_eef_diversity_after_rbf_phase"])
    )
    final_ok = float(row["initial_eef_diversity_final"]) >= (
        float(iid_row["initial_eef_diversity_final"]) * 1.10
    )
    endpoint_ok = float(row["endpoint_spread_final"]) >= (
        float(iid_row["endpoint_spread_final"]) * 1.10
    )
    return "pass" if after_ok and final_ok and endpoint_ok else "fail"


def _utility_verdict(
    row: dict[str, object],
    iid_row: dict[str, object] | None,
) -> str:
    if not _is_aggressive_rbf_row(row):
        return "reference"
    if iid_row is None:
        return "blocked"
    required = [
        row.get("selected_reward"),
        row.get("target_distance_after"),
        iid_row.get("selected_reward"),
        iid_row.get("target_distance_after"),
    ]
    if not all(_is_finite_number(value) for value in required):
        return "blocked"
    reward_ok = float(row["selected_reward"]) >= float(iid_row["selected_reward"]) - 1e-3
    distance_ok = (
        float(row["target_distance_after"])
        <= float(iid_row["target_distance_after"]) + 5e-3
    )
    return "pass" if reward_ok and distance_ok else "fail"


def _combined_rbf_verdict(
    row: dict[str, object],
    mechanism_verdict: str,
    utility_verdict: str,
) -> str:
    if not _is_aggressive_rbf_row(row):
        return "reference"
    if "blocked" in {mechanism_verdict, utility_verdict}:
        return "blocked"
    if (
        _safety_verdict(row) == "pass"
        and mechanism_verdict == "pass"
        and utility_verdict == "pass"
    ):
        return "pass"
    return "fail"


def write_aggressive_rbf_report(episodes: int = 3) -> Path:
    ensure_dirs()
    path = EVIDENCE_ROOT / AGGRESSIVE_RBF_REPORT
    rows = _aggressive_rbf_rows(episodes)
    incomplete = [str(row["label"]) for row in rows if not row["complete"]]
    iid_row = next((row for row in rows if row["label"] == "iid_baseline"), None)
    default_rbf_row = next(
        (row for row in rows if row["label"] == "rbf_s1_start_null"),
        None,
    )
    for row in rows:
        row["missing_required_metrics"] = _missing_required_metrics(row)
        row["mechanism_verdict"] = _mechanism_verdict(row, iid_row, default_rbf_row)
        row["utility_verdict"] = _utility_verdict(row, iid_row)
        row["combined_verdict"] = _combined_rbf_verdict(
            row,
            str(row["mechanism_verdict"]),
            str(row["utility_verdict"]),
        )
    missing_metrics = {
        str(row["label"]): row["missing_required_metrics"]
        for row in rows
        if row["missing_required_metrics"]
    }
    safety_failures = [
        str(row["label"]) for row in rows if _safety_verdict(row) != "pass"
    ]
    mechanism_pass = any(
        row["mechanism_verdict"] == "pass" for row in rows if _is_aggressive_rbf_row(row)
    )
    utility_pass = any(
        row["utility_verdict"] == "pass" for row in rows if _is_aggressive_rbf_row(row)
    )
    if incomplete or missing_metrics:
        verdict = "blocked"
    elif safety_failures or not mechanism_pass or not utility_pass:
        verdict = "fail"
    else:
        verdict = "pass"
    lines = [
        "# RBF+EDS Aggressive Initial Diversity Parameter Sweep",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        f"Verdict: `{verdict}`",
        "",
        "## Scope",
        "",
        "- Level: `level2` online smoke on `libero_object` task filter `[0]`.",
        "- Methods: `iid_baseline`, `rbf_s1_start_null`, and aggressive RBF scale/start-ratio sweep.",
        "- Existing EDS metrics are retained; the EEF trajectory-space fields below are additional diagnostics.",
        f"- Evidence root: `{_rel_or_abs(EVIDENCE_ROOT)}`.",
        "",
        "## Main Metrics",
        "",
        "| Run | Scale | Start Ratio | Complete | Success | Records | Diversity Steps | Fallbacks | Grad Failures | Nonfinite | Action Mask Max | initial_eef_diversity_before_rbf | initial_eef_diversity_after_rbf_phase | initial_eef_diversity_final | initial_eef_diversity_retention_ratio | endpoint_spread_before_rbf | endpoint_spread_after_rbf_phase | endpoint_spread_final | selected_reward | target_distance_after | select_action_latency_s | initial_sampler_latency_s |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['label']}` | {_fmt_optional(row['scale'])} | "
            f"{_fmt_optional(row['start_ratio'])} | `{row['complete']}` | "
            f"{_success_cell(row)} | {row['records']} | "
            f"{_fmt_float(row['diversity_steps'])} | {row['fallback_count']} | "
            f"{row['grad_failures']} | {row['nonfinite']} | "
            f"{_fmt_float(row['action_mask_violation_max'])} | "
            f"{_fmt_float(row['initial_eef_diversity_before_rbf'])} | "
            f"{_fmt_float(row['initial_eef_diversity_after_rbf_phase'])} | "
            f"{_fmt_float(row['initial_eef_diversity_final'])} | "
            f"{_fmt_float(row['initial_eef_diversity_retention_ratio'])} | "
            f"{_fmt_float(row['endpoint_spread_before_rbf'])} | "
            f"{_fmt_float(row['endpoint_spread_after_rbf_phase'])} | "
            f"{_fmt_float(row['endpoint_spread_final'])} | "
            f"{_fmt_float(row['selected_reward'])} | "
            f"{_fmt_float(row['target_distance_after'])} | "
            f"{_fmt_float(row['select_action_latency_s'])} | "
            f"{_fmt_float(row['initial_sampler_latency_s'])} |"
        )

    lines.extend(
        [
            "",
            "## Safety Gate",
            "",
            "| Run | Fallbacks | Grad Failures | Nonfinite | Action Mask Max | Verdict |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['label']}` | {row['fallback_count']} | {row['grad_failures']} | "
            f"{row['nonfinite']} | {_fmt_float(row['action_mask_violation_max'])} | "
            f"`{_safety_verdict(row)}` |"
        )

    if missing_metrics:
        lines.extend(["", "## Missing Required Metrics", ""])
        for label, fields in missing_metrics.items():
            lines.append(f"- `{label}`: {', '.join(fields)}")

    lines.extend(
        [
            "",
            "## Mechanism Gate",
            "",
            "| Run | After RBF > Default RBF | Final EEF >= IID * 1.10 | Endpoint >= IID * 1.10 | Verdict |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        if not _is_aggressive_rbf_row(row):
            continue
        after_delta = _delta(
            row["initial_eef_diversity_after_rbf_phase"],
            default_rbf_row["initial_eef_diversity_after_rbf_phase"] if default_rbf_row else None,
        )
        final_ratio = (
            float(row["initial_eef_diversity_final"])
            / float(iid_row["initial_eef_diversity_final"])
            if iid_row
            and _is_finite_number(row["initial_eef_diversity_final"])
            and _is_finite_number(iid_row["initial_eef_diversity_final"])
            and float(iid_row["initial_eef_diversity_final"]) != 0.0
            else None
        )
        endpoint_ratio = (
            float(row["endpoint_spread_final"])
            / float(iid_row["endpoint_spread_final"])
            if iid_row
            and _is_finite_number(row["endpoint_spread_final"])
            and _is_finite_number(iid_row["endpoint_spread_final"])
            and float(iid_row["endpoint_spread_final"]) != 0.0
            else None
        )
        lines.append(
            f"| `{row['label']}` | {_fmt_float(after_delta)} | "
            f"{_fmt_float(final_ratio)} | {_fmt_float(endpoint_ratio)} | "
            f"`{row['mechanism_verdict']}` |"
        )

    lines.extend(
        [
            "",
            "## Utility Gate",
            "",
            "| Run | selected_reward - IID | target_distance_after - IID | Verdict |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        if not _is_aggressive_rbf_row(row):
            continue
        lines.append(
            f"| `{row['label']}` | "
            f"{_fmt_float(_delta(row['selected_reward'], iid_row['selected_reward']) if iid_row else None)} | "
            f"{_fmt_float(_delta(row['target_distance_after'], iid_row['target_distance_after']) if iid_row else None)} | "
            f"`{row['utility_verdict']}` |"
        )

    lines.extend(
        [
            "",
            "## Delta vs IID Baseline",
            "",
            "| Run | Δ initial_eef_diversity_final | Δ endpoint_spread_final | Δ selected_reward | Δ target_distance_after | Verdict |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        if row["label"] == "iid_baseline":
            continue
        lines.append(
            f"| `{row['label']}` | "
            f"{_fmt_float(_delta(row['initial_eef_diversity_final'], iid_row['initial_eef_diversity_final']) if iid_row else None)} | "
            f"{_fmt_float(_delta(row['endpoint_spread_final'], iid_row['endpoint_spread_final']) if iid_row else None)} | "
            f"{_fmt_float(_delta(row['selected_reward'], iid_row['selected_reward']) if iid_row else None)} | "
            f"{_fmt_float(_delta(row['target_distance_after'], iid_row['target_distance_after']) if iid_row else None)} | "
            f"`{row['combined_verdict']}` |"
        )

    lines.extend(
        [
            "",
            "## Delta vs Default RBF",
            "",
            "| Run | Δ initial_eef_diversity_final vs s1 | Δ endpoint_spread_final vs s1 | Δ selected_reward vs s1 | Δ target_distance_after vs s1 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        if row["label"] in {"iid_baseline", "rbf_s1_start_null"}:
            continue
        lines.append(
            f"| `{row['label']}` | "
            f"{_fmt_float(_delta(row['initial_eef_diversity_final'], default_rbf_row['initial_eef_diversity_final']) if default_rbf_row else None)} | "
            f"{_fmt_float(_delta(row['endpoint_spread_final'], default_rbf_row['endpoint_spread_final']) if default_rbf_row else None)} | "
            f"{_fmt_float(_delta(row['selected_reward'], default_rbf_row['selected_reward']) if default_rbf_row else None)} | "
            f"{_fmt_float(_delta(row['target_distance_after'], default_rbf_row['target_distance_after']) if default_rbf_row else None)} |"
        )

    lines.extend(["", "## Output Index", ""])
    for row in rows:
        lines.append(
            f"- `{row['label']}`: output `{_rel_or_abs(row['output_dir'])}`, "
            f"metrics `{_rel_or_abs(row['metrics_path'])}`"
        )

    lines.extend(["", "## Completion Gate", ""])
    if incomplete:
        lines.append("Blocked/incomplete jobs:")
        lines.extend(f"- `{label}`" for label in incomplete)
    else:
        lines.append("- All aggressive RBF level2 sweep jobs have complete outputs.")
        lines.append("- Every EDS job has a non-empty `eds_eval/eds_metrics.jsonl`.")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `OPENAI_API_KEY=dummy` may appear in offline cached-guidance runs only to satisfy client initialization; cached-guidance mode does not call an online VLM for reward generation.",
            "- Negative `Δ target_distance_after` is favorable because smaller target distance is better.",
            "- Safety failures must be read together with logs before interpreting mechanism or utility deltas.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _rollout_rbf_rows(episodes: int) -> list[dict[str, object]]:
    status_by_id = _status_rows_by_job_id()
    rows = []
    for job in build_jobs("rollout_rbf_ablation", episodes):
        output_dir = RUN_ROOT / str(job["job_id"])
        metrics_path = _metrics_path(job)
        parsed = _parse_results_file(_results_path(job))
        metrics = _read_jsonl(metrics_path)
        artifacts = _artifact_counts(output_dir)
        rollout_artifacts = _rollout_rbf_artifact_counts(output_dir)
        status_row = status_by_id.get(str(job["job_id"]), {})
        fallback_count = sum(
            1 for record in metrics if record.get("rollout_diversity_fallback_used") is True
        )
        enabled_count = sum(
            1 for record in metrics if record.get("rollout_diversity_enabled") is True
        )
        rows.append(
            {
                "job": job,
                "job_id": job["job_id"],
                "label": job["label"],
                "status": status_row.get("status", "unknown"),
                "gpu": status_row.get("gpu", ""),
                "exit_code": status_row.get("exit_code", ""),
                "wall_clock_s": status_row.get("wall_clock_s", ""),
                "complete": _job_has_complete_outputs(job),
                "success": parsed["success"],
                "total": parsed["total"],
                "success_rate": parsed["success_rate"],
                "records": len(metrics),
                "renoise_t_max": job["renoise_t_max"],
                "rollout_diversity_scale": job["rollout_diversity_scale"],
                "rollout_diversity_start_ratio": job["rollout_diversity_start_ratio"],
                "rollout_diversity_iters": job["rollout_diversity_iters"],
                "enabled_count": enabled_count,
                "fallback_count": fallback_count,
                "nonfinite": _metric_sum(metrics, "nonfinite_count"),
                "action_mask_violation_max": _metric_max(metrics, "action_mask_violation_max"),
                "rollout_diversity_steps_applied": _metric_mean(
                    metrics,
                    "rollout_diversity_steps_applied",
                ),
                "rollout_diversity_iters_applied": _metric_mean(
                    metrics,
                    "rollout_diversity_iters_applied",
                ),
                "rollout_diversity_grad_norm_mean": _metric_mean(
                    metrics,
                    "rollout_diversity_grad_norm_mean",
                ),
                "rollout_diversity_grad_norm_max": _metric_max(
                    metrics,
                    "rollout_diversity_grad_norm_max",
                ),
                "initial_eef_diversity_final": _metric_mean(
                    metrics,
                    "initial_eef_diversity_final",
                ),
                "eef_diversity_before_rollout": _metric_mean(
                    metrics,
                    "eef_diversity_before_rollout",
                ),
                "eef_diversity_after_rollout_rbf_phase": _metric_mean(
                    metrics,
                    "eef_diversity_after_rollout_rbf_phase",
                ),
                "eef_diversity_after_rollout_final": _metric_mean(
                    metrics,
                    "eef_diversity_after_rollout_final",
                ),
                "eef_diversity_rollout_retention_ratio": _metric_mean(
                    metrics,
                    "eef_diversity_rollout_retention_ratio",
                ),
                "endpoint_spread_before_rollout": _metric_mean(
                    metrics,
                    "endpoint_spread_before_rollout",
                ),
                "endpoint_spread_after_rollout_rbf_phase": _metric_mean(
                    metrics,
                    "endpoint_spread_after_rollout_rbf_phase",
                ),
                "endpoint_spread_after_rollout_final": _metric_mean(
                    metrics,
                    "endpoint_spread_after_rollout_final",
                ),
                "selected_reward": _metric_mean(metrics, "selected_reward"),
                "target_distance_after": _metric_mean(metrics, "target_distance_after"),
                "select_action_latency_s": _metric_mean(
                    metrics,
                    "select_action_latency_s",
                ),
                "eds_loop_latency_s": _metric_mean(metrics, "eds_loop_latency_s"),
                "initial_sampler_latency_s": _metric_mean(
                    metrics,
                    "initial_sampler_latency_s",
                ),
                "qualitative_png": artifacts["qualitative_png"],
                "rollout_rbf_metrics_json": rollout_artifacts["rollout_rbf_metrics_json"],
                "rollout_rbf_png": rollout_artifacts["rollout_rbf_png"],
                "rollout_rbf_npz": rollout_artifacts["rollout_rbf_npz"],
                "output_dir": output_dir,
                "metrics_path": metrics_path,
                "log_file": EVIDENCE_ROOT / "logs" / f"{job['job_id']}.log",
            }
        )
    return rows


def _rollout_rbf_safety_verdict(row: dict[str, object]) -> str:
    if not row["complete"]:
        return "blocked"
    mask_value = row.get("action_mask_violation_max")
    mask_ok = mask_value is None or (
        _is_finite_number(mask_value) and float(mask_value) == 0.0
    )
    if (
        int(row["fallback_count"]) == 0
        and int(row["nonfinite"]) == 0
        and mask_ok
    ):
        return "pass"
    return "fail"


def write_rollout_rbf_report(episodes: int = 3) -> Path:
    ensure_dirs()
    path = EVIDENCE_ROOT / ROLLOUT_RBF_REPORT
    rows = _rollout_rbf_rows(episodes)
    incomplete = [row for row in rows if not row["complete"]]
    failed_rows = [row for row in rows if row["status"] == "failed"]
    safety_failures = [
        row for row in rows if _rollout_rbf_safety_verdict(row) not in {"pass", "blocked"}
    ]
    if incomplete:
        execution_verdict = "blocked"
        verdict = "blocked"
    elif safety_failures:
        execution_verdict = "fail"
        verdict = "fail"
    else:
        execution_verdict = "pass"
        verdict = "inconclusive"

    lines = [
        "# RBF-Assisted Truncated Rollout Level3 Parameter Sweep",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        f"Execution Verdict: `{execution_verdict}`",
        "",
        f"Verdict: `{verdict}`",
        "",
        "## Scope",
        "",
        "- Benchmark: `libero_object`, task filter `[0]`, `episodes=3` per job.",
        "- Fixed initial sampler: `initial_sampling_mode=rbf_diverse_denoise`, `initial_diversity_scale=20.0`, `initial_diversity_start_ratio=0.8`.",
        "- Sweep: `renoise_t_max in [4,3,2,1]`, `renoise_t_min=1`, rollout RBF scale `[5,10,15,20]`, start ratio `[0.6,0.8]`, iterations `[1,3,6,all]`.",
        "- Baseline references: `2026-07-10-renoise-tmax-ablation-report.md` and `2026-07-11-renoise-rt1to1-start08-supplement.md`.",
        "",
        "## Completion Summary",
        "",
        f"- Jobs expected: `{len(rows)}`",
        f"- Jobs complete: `{sum(1 for row in rows if row['complete'])}`",
        f"- Jobs incomplete/failed: `{len(incomplete)}`",
        f"- Status CSV: `{_rel_or_abs(STATUS_CSV)}`",
        f"- Output root: `{_rel_or_abs(RUN_ROOT)}`",
        "",
        "## Main Metrics",
        "",
        "| Job | Status | Success | Records | rtmax | Scale | Start | Iters | Enabled Records | Fallbacks | Nonfinite | Mask Max | Rollout Steps | Rollout Iters | EEF before | EEF after RBF | EEF final | Retention | Endpoint before | Endpoint after RBF | Endpoint final | selected_reward | target_distance_after | select_latency | EDS latency | Qual PNG | Rollout JSON |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['label']}` | `{row['status']}` | {_success_cell(row)} | "
            f"{row['records']} | {row['renoise_t_max']} | "
            f"{_fmt_float(row['rollout_diversity_scale'], digits=1)} | "
            f"{_fmt_float(row['rollout_diversity_start_ratio'], digits=1)} | "
            f"`{row['rollout_diversity_iters']}` | {row['enabled_count']} | "
            f"{row['fallback_count']} | {row['nonfinite']} | "
            f"{_fmt_float(row['action_mask_violation_max'])} | "
            f"{_fmt_float(row['rollout_diversity_steps_applied'])} | "
            f"{_fmt_float(row['rollout_diversity_iters_applied'])} | "
            f"{_fmt_float(row['eef_diversity_before_rollout'])} | "
            f"{_fmt_float(row['eef_diversity_after_rollout_rbf_phase'])} | "
            f"{_fmt_float(row['eef_diversity_after_rollout_final'])} | "
            f"{_fmt_float(row['eef_diversity_rollout_retention_ratio'])} | "
            f"{_fmt_float(row['endpoint_spread_before_rollout'])} | "
            f"{_fmt_float(row['endpoint_spread_after_rollout_rbf_phase'])} | "
            f"{_fmt_float(row['endpoint_spread_after_rollout_final'])} | "
            f"{_fmt_float(row['selected_reward'])} | "
            f"{_fmt_float(row['target_distance_after'])} | "
            f"{_fmt_float(row['select_action_latency_s'])} | "
            f"{_fmt_float(row['eds_loop_latency_s'])} | "
            f"{row['qualitative_png']} | {row['rollout_rbf_metrics_json']} |"
        )

    complete_rows = [row for row in rows if row["complete"]]
    ranked = sorted(
        complete_rows,
        key=lambda row: (
            float(row["success_rate"]) if _is_finite_number(row["success_rate"]) else -1.0,
            float(row["eef_diversity_after_rollout_final"]) if _is_finite_number(row["eef_diversity_after_rollout_final"]) else -1.0,
        ),
        reverse=True,
    )
    lines.extend(
        [
            "",
            "## Top Complete Settings",
            "",
            "| Rank | Job | Success Rate | EEF final | Endpoint final | selected_reward | target_distance_after |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for rank, row in enumerate(ranked[:10], start=1):
        lines.append(
            f"| {rank} | `{row['label']}` | {_fmt_float(row['success_rate'])} | "
            f"{_fmt_float(row['eef_diversity_after_rollout_final'])} | "
            f"{_fmt_float(row['endpoint_spread_after_rollout_final'])} | "
            f"{_fmt_float(row['selected_reward'])} | "
            f"{_fmt_float(row['target_distance_after'])} |"
        )

    lines.extend(
        [
            "",
            "## Safety And Failure Summary",
            "",
            "| Job | Complete | Status | Fallbacks | Nonfinite | Mask Max | Safety | Failure Excerpt |",
            "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in rows:
        safety = _rollout_rbf_safety_verdict(row)
        if row["complete"] and safety == "pass":
            continue
        excerpt = _failure_excerpt(Path(row["log_file"]))
        lines.append(
            f"| `{row['label']}` | `{row['complete']}` | `{row['status']}` | "
            f"{row['fallback_count']} | {row['nonfinite']} | "
            f"{_fmt_float(row['action_mask_violation_max'])} | `{safety}` | "
            f"{excerpt[:280]} |"
        )
    if not failed_rows and not incomplete and not safety_failures:
        lines.append("| all jobs | `True` | `done` | 0 | 0 | 0.000 | `pass` | - |")

    lines.extend(["", "## Output Index", ""])
    for row in rows:
        lines.append(
            f"- `{row['label']}`: output `{_rel_or_abs(Path(row['output_dir']))}`, "
            f"metrics `{_rel_or_abs(Path(row['metrics_path']))}`, "
            f"log `{_rel_or_abs(Path(row['log_file']))}`"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `Rollout JSON` counts `Rollout_RBF_diversity/rollout_rbf_diversity_metrics.json` files under qualitative chunk directories.",
            "- The report preserves all existing EDS metrics and adds rollout RBF-specific metrics for mechanism debugging.",
            "- Negative or smaller `target_distance_after` is favorable; higher success rate is primary for downstream OOD selection.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _clean_markdown_cell(cell: str) -> str:
    return cell.strip().strip("`").strip()


def _parse_percent_cell(cell: str) -> float | None:
    text = _clean_markdown_cell(cell).rstrip("%").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_reference_level4_baselines(
    path: Path,
    suite: str = "libero_object_swap",
) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    wanted = {
        "RDT unguided": "rdt_unguided",
        "RDT+EDS softmax": "eds_iid_baseline",
    }
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|") or "Suite" not in line:
            continue
        headers = [_clean_markdown_cell(cell) for cell in _split_markdown_row(line)]
        if not set(wanted).issubset(headers):
            continue
        for row_line in lines[index + 1 :]:
            if not row_line.lstrip().startswith("|"):
                break
            cells = _split_markdown_row(row_line)
            if len(cells) != len(headers):
                continue
            if set(_clean_markdown_cell(cell).replace("-", "") for cell in cells) == {""}:
                continue
            row = dict(zip(headers, cells))
            if _clean_markdown_cell(row.get("Suite", "")) != suite:
                continue
            baselines: dict[str, dict[str, object]] = {}
            for source_method, key in wanted.items():
                success_rate = _parse_percent_cell(row.get(source_method, ""))
                if success_rate is None:
                    continue
                total = 10
                success = int(math.floor((success_rate / 100.0 * total) + 0.5))
                baselines[key] = {
                    "source": "referenced_level4",
                    "source_method": source_method,
                    "suite": suite,
                    "success": success,
                    "total": total,
                    "success_rate": success_rate,
                }
            return baselines
    return {}


def _object_swap_ood_rbf_rows(episodes: int) -> list[dict[str, object]]:
    status_by_id = _status_rows_by_job_id()
    rows = []
    for job in build_jobs("object_swap_ood_rbf", episodes):
        output_dir = _output_dir(job)
        metrics_path = _metrics_path(job)
        parsed = _parse_results_file(_results_path(job))
        metrics = _read_jsonl(metrics_path)
        artifacts = _artifact_counts(output_dir)
        validity = _job_validity(job)
        status_row = status_by_id.get(str(job["job_id"]), {})
        initial_fallback_count = sum(
            1 for record in metrics if record.get("initial_diversity_fallback_used") is True
        )
        rollout_fallback_count = sum(
            1 for record in metrics if record.get("rollout_diversity_fallback_used") is True
        )
        rows.append(
            {
                "job": job,
                "job_id": job["job_id"],
                "label": job["label"],
                "source": "new_run",
                "status": status_row.get("status", "unknown"),
                "gpu": status_row.get("gpu", ""),
                "exit_code": status_row.get("exit_code", ""),
                "wall_clock_s": status_row.get("wall_clock_s", ""),
                "success": parsed["success"],
                "total": parsed["total"],
                "success_rate": parsed["success_rate"],
                "records": len(metrics),
                "videos": artifacts["videos"],
                "qualitative_png": artifacts["qualitative_png"],
                "valid": validity["valid"],
                "failure_reason": validity["failure_reason"],
                "strict_perturbations_verified": validity[
                    "strict_perturbations_verified"
                ],
                "suite_verified": validity["suite_verified"],
                "renoise_t_max": job.get("renoise_t_max"),
                "rollout_diversity_scale": job.get("rollout_diversity_scale"),
                "rollout_diversity_start_ratio": job.get(
                    "rollout_diversity_start_ratio"
                ),
                "rollout_diversity_iters": job.get("rollout_diversity_iters"),
                "initial_fallback_count": initial_fallback_count,
                "rollout_fallback_count": rollout_fallback_count,
                "nonfinite": _metric_sum(metrics, "nonfinite_count"),
                "action_mask_violation_max": _metric_max(
                    metrics,
                    "action_mask_violation_max",
                ),
                "eef_diversity_after_rollout_final": _metric_mean(
                    metrics,
                    "eef_diversity_after_rollout_final",
                ),
                "eef_diversity_rollout_retention_ratio": _metric_mean(
                    metrics,
                    "eef_diversity_rollout_retention_ratio",
                ),
                "selected_reward": _metric_mean(metrics, "selected_reward"),
                "target_distance_after": _metric_mean(
                    metrics,
                    "target_distance_after",
                ),
                "select_action_latency_s": _metric_mean(
                    metrics,
                    "select_action_latency_s",
                ),
                "eds_loop_latency_s": _metric_mean(metrics, "eds_loop_latency_s"),
                "initial_sampler_latency_s": _metric_mean(
                    metrics,
                    "initial_sampler_latency_s",
                ),
                "output_dir": output_dir,
                "metrics_path": metrics_path,
                "log_file": EVIDENCE_ROOT / "logs" / f"{job['job_id']}.log",
            }
        )
    return rows


def _sr_delta(row: dict[str, object], baseline: dict[str, object] | None) -> float | None:
    if baseline is None:
        return None
    return _delta(row.get("success_rate"), baseline.get("success_rate"))


def write_object_swap_ood_rbf_report(episodes: int = 10) -> Path:
    ensure_dirs()
    path = EVIDENCE_ROOT / OBJECT_SWAP_OOD_RBF_REPORT
    baselines = _parse_reference_level4_baselines(
        REFERENCE_LEVEL4_REPORT,
        suite="libero_object_swap",
    )
    rows = _object_swap_ood_rbf_rows(episodes)
    valid_rows = [row for row in rows if row["valid"]]
    result_rows = [row for row in rows if row["total"] is not None]
    valid_result_rows = [row for row in valid_rows if row["total"] is not None]
    best_row = max(
        valid_result_rows,
        key=lambda row: (
            float(row["success_rate"]) if _is_finite_number(row["success_rate"]) else -1.0,
            float(row["records"]) if _is_finite_number(row["records"]) else -1.0,
        ),
        default=None,
    )
    rdt_baseline = baselines.get("rdt_unguided")
    iid_baseline = baselines.get("eds_iid_baseline")
    verdict = "inconclusive"
    if not valid_rows:
        verdict = "blocked"
    elif any(
        row["success_rate"] is not None
        and iid_baseline is not None
        and float(row["success_rate"]) > float(iid_baseline["success_rate"])
        for row in valid_rows
    ):
        verdict = "pass"

    lines = [
        "# LIBERO-PRO Object-Swap RDT+EDS RBF Report",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        f"Verdict: `{verdict}`",
        "",
        "## Scope",
        "",
        "- Suite: `libero_object_swap`",
        f"- Episodes per job: `{episodes}`",
        "- Level: `object_swap_ood_rbf` using strict LIBERO-PRO perturbations.",
        "- Fixed initial sampler: `rbf_diverse_denoise`, scale `20.0`, start ratio `0.8`.",
        "- Sweep: `renoise_t_max in [4,3,2,1]`, rollout RBF scale `[5,10,15,20]`, start ratio `[0.2,0.4,0.6,0.8]`, iterations `[1,3,6,all]`.",
        f"- Output root: `{_rel_or_abs(OOD_RUN_ROOT)}`.",
        f"- Referenced Level-4 aggregate: `{_rel_or_abs(REFERENCE_LEVEL4_REPORT)}`.",
        "",
        "## Referenced Baselines",
        "",
        "| Method | Source | Success | SR | Source Method |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    if baselines:
        for key in ["rdt_unguided", "eds_iid_baseline"]:
            baseline = baselines.get(key)
            if baseline is None:
                continue
            lines.append(
                f"| `{key}` | `{baseline['source']}` | "
                f"{baseline['success']}/{baseline['total']} | "
                f"{_fmt_float(baseline['success_rate'], digits=2)} | "
                f"{baseline['source_method']} |"
            )
    else:
        lines.append("| none | `missing_reference_level4` | - | - | - |")

    lines.extend(
        [
            "",
            "## New Results",
            "",
            "| Method | Source | Status | Valid | Success | SR | Records | Videos | Qual PNG | rtmax | Rollout Scale | Rollout Start | Iters | select_latency | EDS latency | Failure Reason |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['label']}` | `{row['source']}` | `{row['status']}` | "
            f"`{row['valid']}` | {_success_cell(row)} | "
            f"{_fmt_float(row['success_rate'], digits=2)} | {row['records']} | "
            f"{row['videos']} | {row['qualitative_png']} | "
            f"{_fmt_optional(row['renoise_t_max'])} | "
            f"{_fmt_optional(row['rollout_diversity_scale'])} | "
            f"{_fmt_optional(row['rollout_diversity_start_ratio'])} | "
            f"`{_fmt_optional(row['rollout_diversity_iters'])}` | "
            f"{_fmt_float(row['select_action_latency_s'])} | "
            f"{_fmt_float(row['eds_loop_latency_s'])} | "
            f"{str(row['failure_reason'])[:220]} |"
        )

    lines.extend(
        [
            "",
            "## SR Comparison",
            "",
            "| Method | Source | Success | SR | Delta vs RDT unguided | Delta vs EDS IID baseline |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for key in ["rdt_unguided", "eds_iid_baseline"]:
        baseline = baselines.get(key)
        if baseline is None:
            continue
        comparison_row = {
            "success_rate": baseline["success_rate"],
            "success": baseline["success"],
            "total": baseline["total"],
        }
        lines.append(
            f"| `{key}` | `{baseline['source']}` | "
            f"{baseline['success']}/{baseline['total']} | "
            f"{_fmt_float(baseline['success_rate'], digits=2)} | "
            f"{_fmt_float(_sr_delta(comparison_row, rdt_baseline), digits=2)} | "
            f"{_fmt_float(_sr_delta(comparison_row, iid_baseline), digits=2)} |"
        )
    for row in valid_result_rows:
        lines.append(
            f"| `{row['label']}` | `{row['source']}` | {_success_cell(row)} | "
            f"{_fmt_float(row['success_rate'], digits=2)} | "
            f"{_fmt_float(_sr_delta(row, rdt_baseline), digits=2)} | "
            f"{_fmt_float(_sr_delta(row, iid_baseline), digits=2)} |"
        )

    lines.extend(
        [
            "",
            "## Aggregated Analysis",
            "",
            f"- Expected jobs: `{len(rows)}`.",
            f"- Jobs with result files: `{len(result_rows)}`.",
            f"- Jobs passing validity gate: `{len(valid_rows)}`.",
        ]
    )
    if best_row is None:
        lines.append("- Best observed setting: unavailable; no validated new result parsed yet.")
    else:
        lines.append(
            "- Best observed setting: "
            f"`{best_row['label']}` with `{_success_cell(best_row)}` "
            f"(`{_fmt_float(best_row['success_rate'], digits=2)}` SR)."
        )

    lines.extend(
        [
            "",
            "## Safety/Validity Gate",
            "",
            "| Method | Valid | Strict | Suite | Videos | Metrics | Qualitative | Failure Reason |",
            "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in rows:
        strict_text = (
            "Strict perturbation verified"
            if row["strict_perturbations_verified"]
            else "Strict perturbation missing"
        )
        suite_text = (
            "suite verified" if row["suite_verified"] else "suite missing"
        )
        qualitative_text = (
            "present" if row["qualitative_png"] or row["valid"] else "missing"
        )
        lines.append(
            f"| `{row['label']}` | `{row['valid']}` | {strict_text} | "
            f"{suite_text} | {row['videos']} | {row['records']} | "
            f"{qualitative_text} | {str(row['failure_reason'])[:260]} |"
        )

    lines.extend(["", "## Conclusion", ""])
    if verdict == "blocked":
        lines.append(
            "The object-swap OOD RBF report is blocked until at least one new run passes the strict validity gate."
        )
    elif verdict == "pass":
        lines.append(
            "At least one validated RBF run improves over the referenced EDS IID baseline on object-swap OOD."
        )
    else:
        lines.append(
            "Validated object-swap OOD RBF runs are present, but the current evidence does not yet show a clear SR improvement over the referenced baseline."
        )

    lines.extend(["", "## Output Index", ""])
    for row in rows:
        lines.append(
            f"- `{row['label']}`: output `{_rel_or_abs(Path(row['output_dir']))}`, "
            f"metrics `{_rel_or_abs(Path(row['metrics_path']))}`, "
            f"log `{_rel_or_abs(Path(row['log_file']))}`"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _stage_recognition_rows(episodes: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for job in build_jobs("stage_recognition_ablation", episodes):
        output_dir = _output_dir(job)
        metrics = _read_jsonl(output_dir / "eds_eval" / "eds_metrics.jsonl")
        stage_events = _read_jsonl(output_dir / "eds_eval" / "stage_events.jsonl")
        episode_metadata = _read_jsonl(
            output_dir / "eds_eval" / "episode_metadata.jsonl"
        )
        parsed = _parse_results_file(output_dir / "results.txt")
        validity = _job_validity(job)
        artifacts = _artifact_counts(output_dir)
        query_events = [
            event
            for event in stage_events
            if event.get("query_status") not in {None, "skipped", "unavailable"}
        ]
        successful_queries = [
            event
            for event in stage_events
            if event.get("query_ok") is True or event.get("query_status") == "ok"
        ]
        transitions = [
            event
            for event in stage_events
            if event.get("stage_before") != event.get("stage_after")
            or event.get("guidance_before") != event.get("guidance_after")
        ]
        guidance_off = [
            event
            for event in stage_events
            if event.get("guidance_before") is True
            and event.get("guidance_after") is False
        ]
        outcomes: dict[int, str] = {}
        for episode in range(1, int(job["episodes"]) + 1):
            videos = list((output_dir / f"episode_{episode}").glob("*.mp4"))
            outcome = "missing"
            if any("_success_" in video.name for video in videos):
                outcome = "success"
            elif any("_fail_" in video.name for video in videos):
                outcome = "fail"
            outcomes[episode - 1] = outcome
        rows.append(
            {
                "job": job,
                "label": job["label"],
                "profile": job["profile"],
                "stage_enabled": job["stage_recognition_enabled"],
                "output_dir": output_dir,
                "validity": validity,
                "valid": validity["valid"],
                "failure_reason": validity["failure_reason"],
                "success": parsed["success"],
                "total": parsed["total"],
                "success_rate": parsed["success_rate"],
                "videos": artifacts["videos"],
                "metrics_records": len(metrics),
                "qualitative_png": artifacts["qualitative_png"],
                "stage_events": len(stage_events),
                "query_events": len(query_events),
                "successful_queries": len(successful_queries),
                "transitions": len(transitions),
                "guidance_off": len(guidance_off),
                "query_latency_s": _metric_mean(stage_events, "query_latency_s"),
                "select_action_latency_s": _metric_mean(
                    metrics, "select_action_latency_s"
                ),
                "initial_eef_diversity_final": _metric_mean(
                    metrics, "initial_eef_diversity_final"
                ),
                "endpoint_spread_final": _metric_mean(
                    metrics, "endpoint_spread_final"
                ),
                "rollout_eef_diversity_final": _metric_mean(
                    metrics, "eef_diversity_after_rollout_final"
                ),
                "rollout_diversity_retention": _metric_mean(
                    metrics, "eef_diversity_rollout_retention_ratio"
                ),
                "selected_reward": _metric_mean(metrics, "selected_reward"),
                "target_distance_after": _metric_mean(
                    metrics, "target_distance_after"
                ),
                "initial_fallbacks": sum(
                    record.get("initial_diversity_fallback_used") is True
                    for record in metrics
                ),
                "rollout_fallbacks": sum(
                    record.get("rollout_diversity_fallback_used") is True
                    for record in metrics
                ),
                "nonfinite": _metric_sum(metrics, "nonfinite_count"),
                "action_mask_violation_max": _metric_max(
                    metrics, "action_mask_violation_max"
                ),
                "episode_seeds": {
                    int(record["episode_id"]): int(record["episode_seed"])
                    for record in episode_metadata
                    if isinstance(record.get("episode_id"), int)
                    and isinstance(record.get("episode_seed"), int)
                },
                "events_by_episode": {
                    episode_id: [
                        event
                        for event in stage_events
                        if event.get("episode_id") == episode_id
                    ]
                    for episode_id in range(int(job["episodes"]))
                },
                "outcomes": outcomes,
            }
        )
    return rows


def _historical_stage_profile_results() -> list[dict[str, object]]:
    labels = {
        "p1": "level4_libero_object_swap_rbf_s20_start08_rt2to1_rollrbf_s5_start02_iterall",
        "p2": "level4_libero_object_swap_rbf_s20_start08_rt3to1_rollrbf_s20_start06_iterall",
    }
    rows = []
    for profile, label in labels.items():
        output_dir = OOD_RUN_ROOT / label
        parsed = _parse_results_file(output_dir / "results.txt")
        rows.append(
            {
                "profile": profile,
                "label": label,
                "success": parsed["success"],
                "total": parsed["total"],
                "success_rate": parsed["success_rate"],
                "output_dir": output_dir,
            }
        )
    return rows


def _stage_seed_pairing_matches(rows: list[dict[str, object]]) -> bool:
    by_label = {str(row["label"]): row for row in rows}
    return all(
        by_label[f"{profile}_stage_off"]["episode_seeds"]
        == by_label[f"{profile}_stage_on"]["episode_seeds"]
        and bool(by_label[f"{profile}_stage_off"]["episode_seeds"])
        for profile in ("p1", "p2")
    )


def write_stage_recognition_timeline_artifacts(
    episodes: int = 10,
) -> list[Path]:
    """Render per-episode stage, guidance, trigger, and query timelines."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    root = STAGE_RECOGNITION_RUN_ROOT / "qualitative_review" / "stage_timelines"
    written: list[Path] = []
    for job in build_jobs("stage_recognition_ablation", episodes):
        if not job["stage_recognition_enabled"]:
            continue
        output_dir = _output_dir(job)
        events = _read_jsonl(output_dir / "eds_eval" / "stage_events.jsonl")
        metadata = _read_jsonl(output_dir / "eds_eval" / "episode_metadata.jsonl")
        metadata_by_episode = {
            int(record["episode_id"]): record
            for record in metadata
            if isinstance(record.get("episode_id"), int)
        }
        job_root = root / str(job["job_id"])
        job_root.mkdir(parents=True, exist_ok=True)
        max_steps = int(job["max_episode_steps"])

        for episode_id in range(int(job["episodes"])):
            episode_events = sorted(
                (
                    event
                    for event in events
                    if event.get("episode_id") == episode_id
                    and isinstance(event.get("global_step"), int)
                ),
                key=lambda event: int(event["global_step"]),
            )
            steps = [0]
            stages = [1]
            guidance = [1]
            for event in episode_events:
                steps.append(int(event["global_step"]))
                stages.append(int(event.get("stage_after", stages[-1])))
                guidance.append(1 if event.get("guidance_after", bool(guidance[-1])) else 0)
            steps.append(max_steps)
            stages.append(stages[-1])
            guidance.append(guidance[-1])

            figure, (stage_ax, guidance_ax) = plt.subplots(
                2,
                1,
                figsize=(12, 4.8),
                sharex=True,
                gridspec_kw={"height_ratios": [2, 1]},
            )
            stage_ax.step(steps, stages, where="post", color="#1864ab", linewidth=2)
            guidance_ax.step(
                steps,
                guidance,
                where="post",
                color="#2b8a3e",
                linewidth=2,
            )
            for event in episode_events:
                step = int(event["global_step"])
                query_ok = event.get("query_ok") is True
                color = "#2b8a3e" if query_ok else "#c92a2a"
                stage_ax.axvline(step, color=color, alpha=0.25, linewidth=1)
                stage_ax.scatter(
                    [step],
                    [int(event.get("stage_after", 1))],
                    color=color,
                    marker="o" if query_ok else "x",
                    s=24,
                    zorder=3,
                )

            info = metadata_by_episode.get(episode_id, {})
            task_id = info.get("task_id", "?")
            episode_seed = info.get("episode_seed", "?")
            figure.suptitle(
                f"{job['label']} | episode {episode_id} | task {task_id} | "
                f"seed {episode_seed}"
            )
            stage_ax.set_ylabel("Stage")
            stage_ax.set_yticks([0, 1, 2])
            stage_ax.set_ylim(-0.25, 2.25)
            stage_ax.grid(axis="y", alpha=0.25)
            stage_ax.text(
                0.995,
                0.97,
                "green=o query OK; red=x query failure",
                transform=stage_ax.transAxes,
                ha="right",
                va="top",
                fontsize=8,
            )
            guidance_ax.set_ylabel("Guide")
            guidance_ax.set_yticks([0, 1], labels=["OFF", "ON"])
            guidance_ax.set_ylim(-0.2, 1.2)
            guidance_ax.set_xlabel("Environment step")
            guidance_ax.set_xlim(0, max_steps)
            guidance_ax.grid(axis="both", alpha=0.25)
            figure.tight_layout()

            path = job_root / f"episode_{episode_id:03d}_stage_timeline.png"
            figure.savefig(path, dpi=150, bbox_inches="tight")
            plt.close(figure)
            written.append(path)
    return written


def write_stage_recognition_ablation_report(episodes: int = 10) -> Path:
    ensure_dirs()
    path = EVIDENCE_ROOT / STAGE_RECOGNITION_REPORT
    timeline_paths = write_stage_recognition_timeline_artifacts(episodes)
    rows = _stage_recognition_rows(episodes)
    by_label = {str(row["label"]): row for row in rows}
    historical = _historical_stage_profile_results()
    valid_rows = [row for row in rows if row["valid"]]
    valid_on_rows = [row for row in valid_rows if row["stage_enabled"]]
    best_on = max(
        valid_on_rows,
        key=lambda row: float(row["success_rate"] or -1.0),
        default=None,
    )
    pretest_job = build_jobs("stage_recognition_pretest", episodes=2)[0]
    pretest_output = _output_dir(pretest_job)
    pretest_validity = _job_validity(pretest_job)
    pretest_results = _parse_results_file(pretest_output / "results.txt")
    seed_pairing_matches = _stage_seed_pairing_matches(rows)
    verdict = "blocked"
    if len(valid_rows) == 4 and pretest_validity["valid"] and seed_pairing_matches:
        best_successes = int(best_on["success"] or 0) if best_on else 0
        paired_deltas = []
        for profile in ("p1", "p2"):
            off = by_label[f"{profile}_stage_off"]
            on = by_label[f"{profile}_stage_on"]
            if off["success"] is not None and on["success"] is not None:
                paired_deltas.append(int(on["success"]) - int(off["success"]))
        if best_successes >= 5:
            verdict = "strong_positive"
        elif paired_deltas and max(paired_deltas) >= 2:
            verdict = "promising"
        elif paired_deltas and max(paired_deltas) < 0:
            verdict = "negative"
        else:
            verdict = "neutral"

    lines = [
        "# LIBERO-PRO Object-Swap 720-Step VLM Stage Recognition Ablation Report",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        f"Verdict: `{verdict}`",
        "",
        "## Experiment Overview",
        "",
        "- Suite: `libero_object_swap` with strict LIBERO-PRO perturbations.",
        f"- Jobs: `4`; episodes per job: `{episodes}`; total episodes: `{4 * episodes}`.",
        "- All new jobs use `max_episode_steps=720`, `seed=0`, Gemini grounding OFF, and cached guidance.",
        "- Stage Recognition is the only within-run A/B variable for each P1/P2 profile.",
        "- Historical runs used 240-step Stage OFF. Because no 240-step Stage ON cell exists, this is not a complete 2x2 factorial experiment and no horizon x stage interaction is claimed.",
        "- GPU policy: GPU 2 only.",
        f"- Output root: `{_rel_or_abs(STAGE_RECOGNITION_RUN_ROOT)}`.",
        f"- Cached guidance: `{STAGE_CACHED_FUNCTIONS_DIR}`.",
        "- Policy/checkpoint and all resolved parameters are preserved in each job's `.hydra/config.yaml` and `.hydra/overrides.yaml`.",
        "",
        "## Mechanism Pretest",
        "",
        f"- Job: `{pretest_job['job_id']}` on task IDs `[0, 6]`.",
        f"- Valid: `{pretest_validity['valid']}`; successful queries: `{pretest_validity['successful_stage_queries']}`; stage events: `{pretest_validity['stage_events']}`.",
        f"- Result: `{pretest_results['success']}/{pretest_results['total']}`; failure reason: `{pretest_validity['failure_reason'] or '-'}`.",
        f"- Output: `{_rel_or_abs(pretest_output)}`.",
        "",
        "## Main Results",
        "",
        "| Method | Profile | Stage | Valid | Success | SR | Videos | Metrics | Qual PNG | Stage Events | Query OK/All | Transitions | Guidance OFF | Query Latency | Select Latency | Failure Reason | Output |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['label']}` | `{row['profile']}` | "
            f"`{'ON' if row['stage_enabled'] else 'OFF'}` | `{row['valid']}` | "
            f"{_success_cell(row)} | {_fmt_float(row['success_rate'], 2)} | "
            f"{row['videos']} | {row['metrics_records']} | {row['qualitative_png']} | "
            f"{row['stage_events']} | {row['successful_queries']}/{row['query_events']} | "
            f"{row['transitions']} | {row['guidance_off']} | "
            f"{_fmt_float(row['query_latency_s'])} | "
            f"{_fmt_float(row['select_action_latency_s'])} | "
            f"{row['failure_reason'] or '-'} | `{_rel_or_abs(row['output_dir'])}` |"
        )

    lines.extend(
        [
            "",
            "## EDS Metrics",
            "",
            "All values are means over saved EDS chunk records; `-` means the metric was not available.",
            "",
            "| Method | Initial EEF Final | Endpoint Final | Rollout EEF Final | Retention | Selected Reward | Target Distance | Initial Fallback | Rollout Fallback | Nonfinite | Mask Violation |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['label']}` | {_fmt_float(row['initial_eef_diversity_final'])} | "
            f"{_fmt_float(row['endpoint_spread_final'])} | "
            f"{_fmt_float(row['rollout_eef_diversity_final'])} | "
            f"{_fmt_float(row['rollout_diversity_retention'])} | "
            f"{_fmt_float(row['selected_reward'])} | "
            f"{_fmt_float(row['target_distance_after'])} | "
            f"{row['initial_fallbacks']} | {row['rollout_fallbacks']} | "
            f"{row['nonfinite']} | {_fmt_float(row['action_mask_violation_max'])} |"
        )

    lines.extend(
        [
            "",
            "## Paired A/B Comparison",
            "",
            "| Profile | 720-step OFF | 720-step ON | Success Delta | SR Delta (pp) |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for profile in ("p1", "p2"):
        off = by_label[f"{profile}_stage_off"]
        on = by_label[f"{profile}_stage_on"]
        success_delta = (
            int(on["success"]) - int(off["success"])
            if on["success"] is not None and off["success"] is not None
            else None
        )
        sr_delta = _delta(on["success_rate"], off["success_rate"])
        lines.append(
            f"| `{profile}` | {_success_cell(off)} | {_success_cell(on)} | "
            f"{success_delta if success_delta is not None else '-'} | "
            f"{_fmt_float(sr_delta, 2)} |"
        )

    lines.extend(
        [
            "",
            "## Episode Seed Pairing",
            "",
            "| Profile | OFF seeds | ON seeds | Exact Match |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for profile in ("p1", "p2"):
        off_seeds = by_label[f"{profile}_stage_off"]["episode_seeds"]
        on_seeds = by_label[f"{profile}_stage_on"]["episode_seeds"]
        lines.append(
            f"| `{profile}` | `{json.dumps(off_seeds, sort_keys=True)}` | "
            f"`{json.dumps(on_seeds, sort_keys=True)}` | `{off_seeds == on_seeds}` |"
        )

    lines.extend(
        [
            "",
            "## Historical 240-Step Context",
            "",
            "This comparison is descriptive only. It can reveal timeout-sensitive failures but cannot isolate a causal horizon effect across separately executed runs.",
            "",
            "| Profile | Historical Stage OFF | 240-step Success | New 720-step OFF | 720-step Success |",
            "| --- | --- | ---: | --- | ---: |",
        ]
    )
    for old in historical:
        off = by_label[f"{old['profile']}_stage_off"]
        old_success = (
            f"{old['success']}/{old['total']}"
            if old["success"] is not None and old["total"] is not None
            else "-"
        )
        lines.append(
            f"| `{old['profile']}` | `{_rel_or_abs(old['output_dir'])}` | "
            f"{old_success} | `{off['label']}` | {_success_cell(off)} |"
        )

    lines.extend(
        [
            "",
            "## Task-Level Outcomes",
            "",
            "| Task | P1 OFF | P1 ON | P2 OFF | P2 ON |",
            "| ---: | --- | --- | --- | --- |",
        ]
    )
    for task_id in range(episodes):
        lines.append(
            f"| {task_id} | {by_label['p1_stage_off']['outcomes'][task_id]} | "
            f"{by_label['p1_stage_on']['outcomes'][task_id]} | "
            f"{by_label['p2_stage_off']['outcomes'][task_id]} | "
            f"{by_label['p2_stage_on']['outcomes'][task_id]} |"
        )

    lines.extend(
        [
            "",
            "## Stage Event Summary",
            "",
            "| Task | P1 ON events/query-ok/transitions/guidance-off | P2 ON events/query-ok/transitions/guidance-off |",
            "| ---: | --- | --- |",
        ]
    )
    for task_id in range(episodes):
        cells = []
        for profile in ("p1", "p2"):
            events = by_label[f"{profile}_stage_on"]["events_by_episode"][task_id]
            ok_count = sum(
                event.get("query_ok") is True or event.get("query_status") == "ok"
                for event in events
            )
            transition_count = sum(
                event.get("stage_before") != event.get("stage_after")
                or event.get("guidance_before") != event.get("guidance_after")
                for event in events
            )
            guidance_off_count = sum(
                event.get("guidance_before") is True
                and event.get("guidance_after") is False
                for event in events
            )
            cells.append(
                f"{len(events)}/{ok_count}/{transition_count}/{guidance_off_count}"
            )
        lines.append(f"| {task_id} | `{cells[0]}` | `{cells[1]}` |")

    timeline_root = (
        STAGE_RECOGNITION_RUN_ROOT / "qualitative_review" / "stage_timelines"
    )
    lines.extend(
        [
            "",
            "## Stage/Guidance Timeline Artifacts",
            "",
            f"- Generated `{len(timeline_paths)}` per-episode timelines with "
            "stage, guidance, trigger, and query-status markers.",
            f"- Root: `{_rel_or_abs(timeline_root)}`.",
        ]
    )
    for job in build_jobs("stage_recognition_ablation", episodes):
        if not job["stage_recognition_enabled"]:
            continue
        job_root = timeline_root / str(job["job_id"])
        count = sum(path.parent == job_root for path in timeline_paths)
        lines.append(f"- `{job['label']}`: `{count}` timelines in `{_rel_or_abs(job_root)}`.")

    lines.extend(
        [
            "",
            "## Failure Classification",
            "",
            "The automatic table below identifies success and missing-query cases. Final grasp/transport/place labels require video review and must be completed in the final evidence pass.",
            "",
            "| Task | P1 OFF | P1 ON | P2 OFF | P2 ON | Evidence Root |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for task_id in range(episodes):
        labels = []
        for label in ("p1_stage_off", "p1_stage_on", "p2_stage_off", "p2_stage_on"):
            row = by_label[label]
            outcome = row["outcomes"][task_id]
            if outcome == "success":
                classification = "success"
            elif row["stage_enabled"] and not row["events_by_episode"][task_id]:
                classification = "fail:no-stage-trigger"
            else:
                classification = "fail:video-review"
            labels.append(classification)
        lines.append(
            f"| {task_id} | {labels[0]} | {labels[1]} | {labels[2]} | {labels[3]} | "
            f"`{_rel_or_abs(STAGE_RECOGNITION_RUN_ROOT)}` |"
        )

    lines.extend(
        [
            "",
            "## Validity Gate",
            "",
            f"- Valid jobs: `{len(valid_rows)}/4`.",
            f"- Jobs with parsed results: `{sum(row['total'] is not None for row in rows)}/4`.",
            f"- Jobs with 10 videos: `{sum(row['videos'] >= episodes for row in rows)}/4`.",
            f"- Stage-ON jobs with successful query trace: `{sum(row['stage_enabled'] and row['successful_queries'] > 0 for row in rows)}/2`.",
            f"- Exact OFF/ON episode-seed pairing: `{seed_pairing_matches}`.",
            "- Hydra validity checks cover strict perturbation, suite, 720-step budget, Stage ON/OFF, grounding OFF, cached guidance, EDS/RBF parameters, and seed 0.",
            "- Serialized config/log checks reject Poe API key material.",
            "",
            "## Conclusion",
            "",
            (
                f"- Best valid Stage-ON setting: `{best_on['label']}` with "
                f"{_success_cell(best_on)} ({_fmt_float(best_on['success_rate'], 2)}%)."
                if best_on is not None
                else "- No valid Stage-ON result is available."
            ),
            "- The initial engineering target is at least 5/10 successes on the same ten swap tasks.",
            "- Qualitative interpretation must distinguish no-trigger/API failure, premature transition, successful grasp with guidance remaining ON, transport failure, and placement failure.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_level4_report(episodes: int = 10) -> Path:
    ensure_dirs()
    path = EVIDENCE_ROOT / LEVEL_REPORTS["level4"]
    jobs = build_jobs("level4", episodes)
    rows = []
    incomplete = []
    for job in jobs:
        output_dir = RUN_ROOT / str(job["job_id"])
        results_path = output_dir / "results.txt"
        metrics_path = output_dir / "eds_eval" / "eds_metrics.jsonl"
        parsed = _parse_results_file(results_path)
        metrics = _read_jsonl(metrics_path)
        artifacts = _artifact_counts(output_dir)
        complete = _job_has_complete_outputs(job)
        if not complete:
            incomplete.append(str(job["job_id"]))
        latency_values = [
            float(record["select_action_latency_s"])
            for record in metrics
            if isinstance(record.get("select_action_latency_s"), (int, float))
        ]
        eds_latency_values = [
            float(record["eds_loop_latency_s"])
            for record in metrics
            if isinstance(record.get("eds_loop_latency_s"), (int, float))
        ]
        initial_sampler_latency_values = [
            float(record["initial_sampler_latency_s"])
            for record in metrics
            if isinstance(record.get("initial_sampler_latency_s"), (int, float))
        ]
        initial_fallback_count = sum(
            1 for record in metrics if record.get("initial_diversity_fallback_used") is True
        )
        rows.append(
            {
                "suite": job["suite"],
                "method": job["label"],
                "complete": complete,
                "success": parsed["success"],
                "total": parsed["total"],
                "success_rate": parsed["success_rate"],
                "select_latency_mean": _mean(latency_values),
                "eds_latency_mean": _mean(eds_latency_values),
                "initial_sampler_latency_mean": _mean(initial_sampler_latency_values),
                "initial_fallback_count": initial_fallback_count,
                "videos": artifacts["videos"],
                "metrics_records": artifacts["metrics_records"],
                "qualitative_png": artifacts["qualitative_png"],
                "output_dir": output_dir,
                "metrics_path": metrics_path,
            }
        )

    verdict = "pass" if not incomplete else "blocked"
    lines = [
        "# RDT+EDS Level 4 LIBERO-PRO OOD Evaluation",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        f"Verdict: `{verdict}`",
        "",
        "## Scope",
        "",
        "- Policy: `rdt` only.",
        "- Benchmark: LIBERO-PRO OOD perturbations on `libero_object` only.",
        "- Episodes per job: `10`.",
        "- Methods: `unguided`, `eds_rbf_diverse_initial`, `eds_softmax_strong_weak_renoise`, `eds_cem_resample_weak_renoise`.",
        "- RDT+VLS, PI05, and previous wrong-checkpoint OOD runs are excluded.",
        "",
        "## Method Configs",
        "",
        "| Method | Guidance | population_size | cem_iters | use_cem | num_elites | temperature | renoise_t_max -> min | initial_sampling_mode | initial_diversity_scale | initial_diversity_start_ratio |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | --- | --- | ---: | --- |",
    ]
    for method in LEVEL4_METHODS:
        if method["method"] == "unguided":
            lines.append("| unguided | off | - | - | - | - | - | - | - | - | - |")
        else:
            initial_sampling_mode = method.get("initial_sampling_mode", "iid")
            initial_diversity_scale = method.get("initial_diversity_scale", 1.0)
            initial_diversity_start_ratio = _hydra_optional(
                method.get("initial_diversity_start_ratio")
            )
            lines.append(
                f"| {method['label']} | EDS | {method['population_size']} | "
                f"{method['cem_iters']} | {method['use_cem']} | {method['num_elites']} | "
                f"{method['temperature']} | {method['renoise_t_max']} -> "
                f"{method['renoise_t_min']} | {initial_sampling_mode} | "
                f"{initial_diversity_scale} | {initial_diversity_start_ratio} |"
            )

    lines.extend(
        [
            "",
            "## Success Rates",
            "",
            "| Suite | Method | Complete | Success | SR | Select Latency Mean | EDS Latency Mean | Initial Sampler Latency Mean | Initial Fallback Count | Videos | Metrics | Qual PNG |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        success_cell = (
            f"{row['success']}/{row['total']}"
            if row["success"] is not None and row["total"] is not None
            else "-"
        )
        sr_cell = f"{row['success_rate']:.2f}" if row["success_rate"] is not None else "-"
        select_latency = (
            f"{row['select_latency_mean']:.3f}"
            if row["select_latency_mean"] is not None
            else "-"
        )
        eds_latency = (
            f"{row['eds_latency_mean']:.3f}"
            if row["eds_latency_mean"] is not None
            else "-"
        )
        initial_sampler_latency = (
            f"{row['initial_sampler_latency_mean']:.3f}"
            if row["initial_sampler_latency_mean"] is not None
            else "-"
        )
        lines.append(
            f"| `{row['suite']}` | `{row['method']}` | `{row['complete']}` | "
            f"{success_cell} | {sr_cell} | {select_latency} | {eds_latency} | "
            f"{initial_sampler_latency} | {row['initial_fallback_count']} | "
            f"{row['videos']} | {row['metrics_records']} | {row['qualitative_png']} |"
        )

    lines.extend(
        [
            "",
            "## Output Index",
            "",
        ]
    )
    for row in rows:
        rel_output = row["output_dir"].relative_to(WORKTREE_ROOT)
        rel_metrics = row["metrics_path"].relative_to(WORKTREE_ROOT)
        lines.append(
            f"- `{row['suite']}` / `{row['method']}`: output `{rel_output}`, metrics `{rel_metrics}`"
        )

    lines.extend(["", "## Completion Gate", ""])
    if incomplete:
        lines.append("Blocked/incomplete jobs:")
        lines.extend(f"- `{job_id}`" for job_id in incomplete)
    else:
        lines.append("- All 24 Level 4 jobs have complete output markers.")
        lines.append("- Every EDS job has a non-empty `eds_eval/eds_metrics.jsonl`.")
        lines.append("- `backend.libero.strict_perturbations=true` was used for Level 4 commands.")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Success/failure is parsed from each job's `results.txt`; process exit code alone is not treated as the result.",
            "- Video counts are based on `episode_*/*.mp4` under each job output directory.",
            "- Qualitative counts include saved keypoint, selected trajectory, population cloud, per-iteration best trajectory, and initial-vs-final overlays.",
            "- Initial fallback count is the number of metrics records with `initial_diversity_fallback_used=true`.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_final_report() -> Path:
    ensure_dirs()
    lines = [
        "# RDT+EDS Final Evaluation Report",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        "## Scope",
        "",
        "- Policy: `rdt` only.",
        "- Base suite: `libero_object` only.",
        "- OOD suites: LIBERO-PRO perturbations of `libero_object` only.",
        "- Alternative guidance and policy comparisons are excluded.",
        "",
        "## Per-Level Reports",
        "",
    ]
    for level in [
        "level0",
        "level1",
        "level2",
        "rollout_rbf_ablation",
        "level3",
        "level4",
        "object_swap_ood_rbf",
    ]:
        report = EVIDENCE_ROOT / LEVEL_REPORTS[level]
        status = "present" if report.exists() else "missing"
        lines.append(f"- `{report.relative_to(WORKTREE_ROOT)}`: `{status}`")
    lines.extend(
        [
            "",
            "## Final Verdict",
            "",
            "- Deployment correctness: `inconclusive` until Level 0 passes.",
            "- Algorithm effectiveness: `inconclusive` until Level 1 through Level 4 are reviewed.",
            "",
            "Previous non-`libero_object` OOD results are excluded because they were caused by wrong checkpoint loading and are not evidence against EDS.",
        ]
    )
    path = EVIDENCE_ROOT / LEVEL_REPORTS["final"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def level0_command() -> list[str]:
    return [
        "conda",
        "run",
        "-n",
        "vla-pilot",
        "pytest",
        "tests/test_rdt_steer.py::test_eds_loop_records_deployment_counters",
        "tests/test_rdt_steer.py::test_eds_zero_reward_records_no_reward_spread",
        "tests/test_rdt_steer.py::test_eds_artifacts_are_decoded_action_candidates",
        "tests/test_rdt_steer.py::test_eds_config_rejects_invalid_reward_mode",
        "-q",
    ]


def level1_command(reward_mode: str = "normal") -> list[str]:
    if reward_mode not in {"normal", "zero", "shuffled_keypoints", "inverted"}:
        raise ValueError(f"Unsupported level1 reward_mode={reward_mode!r}")
    label = {
        "normal": "normal",
        "zero": "zero",
        "shuffled_keypoints": "shuffled",
        "inverted": "inverted",
    }[reward_mode]
    output_dir = RUN_ROOT / "level1_mechanism_probe" / label
    return [
        "conda",
        "run",
        "-n",
        "vla-pilot",
        "python",
        "main.py",
        "policy.type=rdt",
        "backend=libero",
        "backend.libero.suite_name=libero_object",
        "backend.libero.task_ids_filter=[0]",
        "main.episode_num=1",
        "backend.libero.max_episode_steps=20",
        "main.use_vlm_stage_recognition=true",
        "perception.gemini_grounding.enabled=true",
        "main.render=false",
        "main.visualize_trajectory=true",
        "main.debug_draw_trajectory=true",
        "main.use_guidance=true",
        "main.guidance_type=eds",
        "main.eds_config.population_size=16",
        "main.eds_config.cem_iters=10",
        "main.eds_config.use_cem=false",
        "main.eds_eval.enabled=true",
        "main.eds_eval.write_metrics=true",
        "main.eds_eval.save_qualitative=true",
        f"main.eds_eval.reward_mode={reward_mode}",
        f"main.eds_eval.output_dir={output_dir / 'eds_eval'}",
        f"hydra.run.dir={output_dir}",
    ]


def level1_commands() -> list[list[str]]:
    return [
        level1_command("normal"),
        level1_command("zero"),
        level1_command("shuffled_keypoints"),
        level1_command("inverted"),
    ]


def run_job(
    job: dict[str, object],
    gpu: str,
    timeout_seconds: int,
    *,
    cached_functions_dir: str | None = None,
    offline_vlm: bool = False,
) -> dict[str, object]:
    ensure_dirs()
    output_dir = _output_dir(job)
    if job.get("level") in P2_LEVELS:
        _revalidate_p2_job_storage(job)
        if cached_functions_dir is None:
            cached_functions_dir = str(
                job.get("p2_cached_functions_dir", STAGE_CACHED_FUNCTIONS_DIR)
            )
        offline_vlm = bool(job.get("p2_offline_vlm", offline_vlm))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    _write_p2_job_identity(job)
    log_file = _log_file_for_job(job)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    command = build_main_command(
        job,
        gpu,
        timeout_seconds,
        cached_functions_dir=cached_functions_dir,
        offline_vlm=offline_vlm,
    )
    env = os.environ.copy()
    is_p2 = job.get("level") in P2_LEVELS
    if is_p2:
        runtime = _gpu_runtime(gpu)
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        env["CUDA_VISIBLE_DEVICES"] = runtime["cuda_visible_devices"]
        env["MUJOCO_EGL_DEVICE_ID"] = runtime["mujoco_egl_device_id"]
    else:
        runtime = None
        env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    env["PYTHONUNBUFFERED"] = "1"
    stage_recognition_enabled = bool(job.get("stage_recognition_enabled", not offline_vlm))
    if "stage_recognition_enabled" in job and stage_recognition_enabled:
        env["OPENAI_BASE_URL"] = "https://api.poe.com/v1"
    else:
        env.setdefault("OPENAI_BASE_URL", "https://api.poe.com/v1")
    if offline_vlm:
        env.setdefault("OPENAI_API_KEY", "dummy")
        for key in (
            "ALL_PROXY",
            "all_proxy",
            "HTTP_PROXY",
            "http_proxy",
            "HTTPS_PROXY",
            "https_proxy",
        ):
            env.pop(key, None)
    env["LIBERO_CONFIG_PATH"] = str(LIBERO_CONFIG_PATH)
    pythonpath_parts = [str(LIBERO_PRO_ROOT)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    start = now_iso()
    start_perf = time.perf_counter()
    return_code = 1
    timed_out = False
    with log_file.open("a", encoding="utf-8", buffering=1) as handle:
        handle.write(f"===== START {job['job_id']} {start} GPU={gpu} =====\n")
        if runtime is not None:
            handle.write(
                "Runtime: "
                f"CUDA_VISIBLE_DEVICES={runtime['cuda_visible_devices']} "
                f"MUJOCO_EGL_DEVICE_ID={runtime['mujoco_egl_device_id']} "
                f"OPENAI_API_KEY_PRESENT={str(bool(env.get('OPENAI_API_KEY'))).lower()}\n"
            )
        handle.write("Command: " + shlex.join(command) + "\n")
        try:
            process = subprocess.run(
                command,
                cwd=WORKTREE_ROOT,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
            )
            return_code = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            return_code = 124
            handle.write(f"Timed out after {timeout_seconds} seconds.\n")
        handle.write(f"===== END {job['job_id']} {now_iso()} exit={return_code} =====\n")

    status = "timeout" if timed_out else "done" if return_code == 0 else "failed"
    output_dir = _output_dir(job)
    result_summary = _parse_results_file(output_dir / "results.txt")
    artifacts = _artifact_counts(output_dir)
    validity = (
        _job_validity(job)
        if job.get("level") in {
            "object_swap_ood_rbf",
            "stage_recognition_pretest",
            "stage_recognition_ablation",
            *P2_LEVELS,
        }
        else {
            "valid": "",
            "failure_reason": "",
            "strict_perturbations_verified": "",
            "suite_verified": "",
        }
    )
    if (
        job.get("level") in {
            "object_swap_ood_rbf",
            "stage_recognition_pretest",
            "stage_recognition_ablation",
            *P2_LEVELS,
        }
        and status == "done"
        and not validity["valid"]
    ):
        status = "invalid" if job.get("level") in P2_LEVELS else "failed"
    if job.get("level") in P2_LEVELS and status != "done":
        failure_payload = {
            "job_id": job["job_id"],
            "status": status,
            "exit_code": return_code,
            "failure_reason": validity.get("failure_reason") or "process failed",
            "timestamp": now_iso(),
        }
        (output_dir / "failure_reason.json").write_text(
            json.dumps(failure_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return {
        **_status_row(job, status, gpu=gpu),
        "exit_code": return_code,
        "wall_clock_s": f"{time.perf_counter() - start_perf:.3f}",
        "success_count": (
            f"{result_summary['success']}/{result_summary['total']}"
            if result_summary["success"] is not None and result_summary["total"] is not None
            else ""
        ),
        "success_rate": (
            f"{result_summary['success_rate']:.2f}"
            if result_summary["success_rate"] is not None
            else ""
        ),
        "videos": artifacts["videos"],
        "metrics_records": artifacts["metrics_records"],
        "qualitative_png": artifacts["qualitative_png"],
        "valid": validity["valid"],
        "failure_reason": validity["failure_reason"],
        "strict_perturbations_verified": validity["strict_perturbations_verified"],
        "suite_verified": validity["suite_verified"],
        "start_time": start,
        "end_time": now_iso(),
    }


def run_level(
    level: str,
    episodes: int,
    gpus: str,
    timeout_seconds: int,
    resume: bool = False,
    *,
    cached_functions_dir: str | None = None,
    offline_vlm: bool = False,
    manifest_path: str | Path | None = None,
    gpu_poll_interval_s: float = 30.0,
    gpu_probe_failure_limit: int = P2_GPU_PROBE_FAILURE_LIMIT,
) -> int:
    p2_real_root: Path | None = None
    if level in P2_LEVELS:
        p2_real_root = _validate_p2_output_storage()
    ensure_dirs()
    gpu_list = [gpu.strip() for gpu in gpus.split(",") if gpu.strip()]
    if not gpu_list:
        raise SystemExit("No GPUs specified")
    if len(gpu_list) != len(set(gpu_list)):
        raise SystemExit("GPU list must contain unique physical GPU indices")
    if level in P2_LEVELS:
        if len(gpu_list) > 4 or not set(gpu_list) <= P2_ALLOWED_GPUS:
            raise SystemExit("P2 experiments may use only GPUs 2,3,4,5 with at most 4 workers")
        if not math.isfinite(float(gpu_poll_interval_s)) or float(gpu_poll_interval_s) <= 0:
            raise SystemExit("gpu_poll_interval_s must be finite and positive")
        if (
            not isinstance(gpu_probe_failure_limit, int)
            or isinstance(gpu_probe_failure_limit, bool)
            or gpu_probe_failure_limit <= 0
        ):
            raise SystemExit("gpu_probe_failure_limit must be a positive integer")
        if offline_vlm:
            raise SystemExit("P2 experiments require online VLM stage recognition")
    if level in {"stage_recognition_pretest", "stage_recognition_ablation"} and gpu_list != ["2"]:
        raise SystemExit("Stage-recognition experiments must run on GPU 2 only")

    jobs = build_jobs(level, episodes, manifest_path=manifest_path)
    if p2_real_root is not None:
        for job in jobs:
            _bind_p2_execution_context(
                job,
                real_root=p2_real_root,
                cached_functions_dir=cached_functions_dir,
                offline_vlm=offline_vlm,
                storage_enforced=True,
            )
    status_path = (
        _p2_status_path(level, p2_real_root)
        if level in P2_LEVELS
        else
        STAGE_STATUS_CSV
        if level in {"stage_recognition_pretest", "stage_recognition_ablation"}
        else STATUS_CSV
    )
    rows_by_id = {}
    runnable_jobs = []
    for job in jobs:
        job_id = str(job["job_id"])
        if resume and _job_has_complete_outputs(job):
            output_dir = _output_dir(job)
            result_summary = _parse_results_file(output_dir / "results.txt")
            artifacts = _artifact_counts(output_dir)
            validity = (
                _job_validity(job)
                if job.get("level") in {
                    "object_swap_ood_rbf",
                    "stage_recognition_pretest",
                    "stage_recognition_ablation",
                    *P2_LEVELS,
                }
                else {
                    "valid": "",
                    "failure_reason": "",
                    "strict_perturbations_verified": "",
                    "suite_verified": "",
                }
            )
            rows_by_id[job_id] = {
                **_status_row(job, "done"),
                "exit_code": 0,
                "wall_clock_s": "resume-skip",
                "success_count": (
                    f"{result_summary['success']}/{result_summary['total']}"
                    if result_summary["success"] is not None and result_summary["total"] is not None
                    else ""
                ),
                "success_rate": (
                    f"{result_summary['success_rate']:.2f}"
                    if result_summary["success_rate"] is not None
                    else ""
                ),
                "videos": artifacts["videos"],
                "metrics_records": artifacts["metrics_records"],
                "qualitative_png": artifacts["qualitative_png"],
                "valid": validity["valid"],
                "failure_reason": validity["failure_reason"],
                "strict_perturbations_verified": validity["strict_perturbations_verified"],
                "suite_verified": validity["suite_verified"],
                "start_time": "resume-skip",
                "end_time": now_iso(),
            }
        else:
            rows_by_id[job_id] = _status_row(job, "pending")
            runnable_jobs.append(job)
    _validate_stage_level_start(
        level,
        offline_vlm=offline_vlm,
        require_online_api=any(
            bool(job.get("stage_recognition_enabled")) for job in runnable_jobs
        ),
    )
    write_status(list(rows_by_id.values()), path=status_path)

    job_queue: Queue[dict[str, object]] = Queue()
    for job in runnable_jobs:
        job_queue.put(job)

    lock = Lock()

    def worker(gpu: str) -> None:
        consecutive_probe_failures = 0
        while True:
            if job_queue.empty():
                return
            if level in P2_LEVELS:
                probe_status, probe_reason = _p2_gpu_probe(gpu)
                if probe_status == "busy":
                    consecutive_probe_failures = 0
                    time.sleep(float(gpu_poll_interval_s))
                    continue
                if probe_status == "error":
                    consecutive_probe_failures += 1
                    if consecutive_probe_failures >= gpu_probe_failure_limit:
                        _write_p2_gpu_probe_failure(
                            level,
                            gpu,
                            probe_reason,
                            consecutive_probe_failures,
                            real_root=p2_real_root,
                        )
                        return
                    time.sleep(float(gpu_poll_interval_s))
                    continue
                if probe_status != "idle":
                    _write_p2_gpu_probe_failure(
                        level,
                        gpu,
                        f"unknown GPU probe status: {probe_status!r}",
                        consecutive_probe_failures + 1,
                        real_root=p2_real_root,
                    )
                    return
                consecutive_probe_failures = 0
            try:
                job = job_queue.get_nowait()
            except Empty:
                return
            job_id = str(job["job_id"])
            try:
                if level in P2_LEVELS:
                    _archive_p2_job_artifacts(job)
                _archive_stage_job_artifacts(job)
                with lock:
                    rows_by_id[job_id] = _status_row(job, "running", gpu=gpu)
                    write_status(list(rows_by_id.values()), path=status_path)
                row = run_job(
                    job,
                    gpu=gpu,
                    timeout_seconds=timeout_seconds,
                    cached_functions_dir=cached_functions_dir,
                    offline_vlm=offline_vlm,
                )
                with lock:
                    rows_by_id[job_id] = row
                    write_status(list(rows_by_id.values()), path=status_path)
            except Exception as exc:
                reason = f"worker exception {type(exc).__name__}: {exc}"
                for secret_name in ("OPENAI_API_KEY", "GOOGLE_API_KEY"):
                    secret = os.environ.get(secret_name)
                    if secret:
                        reason = reason.replace(secret, "[REDACTED]")
                with lock:
                    rows_by_id[job_id] = {
                        **_status_row(job, "failed", gpu=gpu),
                        "exit_code": 1,
                        "failure_reason": reason,
                        "end_time": now_iso(),
                    }
                    write_status(list(rows_by_id.values()), path=status_path)
                if level in P2_LEVELS:
                    failure_root = Path(
                        p2_real_root if p2_real_root is not None else P2_STATUS_ROOT
                    )
                    failure_dir = _p2_safe_child_path(
                        failure_root, "failures", _p2_stage_dir(level)
                    )
                    failure_dir.mkdir(parents=True, exist_ok=True)
                    failure_path = _p2_safe_child_path(
                        failure_root,
                        "failures",
                        _p2_stage_dir(level),
                        f"{job['label']}.json",
                    )
                    failure_path.write_text(
                        json.dumps(
                            {
                                "job_id": job_id,
                                "status": "failed",
                                "failure_reason": reason,
                                "timestamp": now_iso(),
                            },
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
            finally:
                job_queue.task_done()

    threads = [Thread(target=worker, args=(gpu,), daemon=False) for gpu in gpu_list]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if level == "stage_recognition_ablation":
        stage_rows = _stage_recognition_rows(episodes)
        if not _stage_seed_pairing_matches(stage_rows):
            for profile in ("p1", "p2"):
                job_id = f"stage_ablation_libero_object_swap_{profile}_stage_on"
                row = rows_by_id.get(job_id)
                if row is not None:
                    row["status"] = "failed"
                    existing = str(row.get("failure_reason") or "")
                    row["failure_reason"] = "; ".join(
                        value
                        for value in [existing, "OFF/ON episode seed mismatch"]
                        if value
                    )
            write_status(list(rows_by_id.values()), path=status_path)

    if level == "level2":
        print(write_aggressive_rbf_report(episodes))
    elif level == "rollout_rbf_ablation":
        print(write_rollout_rbf_report(episodes))
    elif level == "object_swap_ood_rbf":
        print(write_object_swap_ood_rbf_report(episodes))
    elif level == "stage_recognition_ablation":
        print(write_stage_recognition_ablation_report(episodes))
    elif level == "level4":
        print(write_level4_report(episodes))

    failures = [row for row in rows_by_id.values() if row.get("status") != "done"]
    return 1 if failures else 0


def _add_online_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--level",
        choices=[
            "level2",
            "level3",
            "level4",
            "renoise_ablation",
            "rollout_rbf_ablation",
            "object_swap_ood_rbf",
            "stage_recognition_pretest",
            "stage_recognition_ablation",
            "p2_adaptive_eds_rbf_pretest",
            "p2_adaptive_eds_rbf_stage_a",
            "p2_adaptive_eds_rbf_stage_b",
        ],
        required=True,
    )
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--cached-functions-dir", default=None)
    parser.add_argument(
        "--manifest-path",
        default=None,
        help="Immutable integration manifest required by the P2 Stage B level.",
    )
    parser.add_argument(
        "--offline-vlm",
        action="store_true",
        help="Disable Gemini/VLM stage services and set a dummy OpenAI key for cached-guidance runs.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="RDT+EDS-only evaluation runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preflight")

    init_parser = sub.add_parser("init")
    _add_online_args(init_parser)

    command_parser = sub.add_parser("print-command")
    _add_online_args(command_parser)
    command_parser.add_argument("--job-index", type=int, default=0)
    command_parser.add_argument("--gpu", default="0")
    command_parser.add_argument("--timeout-seconds", type=int, default=28800)

    report_parser = sub.add_parser("write-report")
    report_parser.add_argument(
        "--level",
        choices=[
            "level0",
            "level1",
            "level2",
            "level3",
            "level4",
            "renoise_ablation",
            "rollout_rbf_ablation",
            "object_swap_ood_rbf",
            "stage_recognition_ablation",
            "p2_adaptive_eds_rbf_pretest",
        ],
        required=True,
    )
    report_parser.add_argument(
        "--verdict",
        choices=["pass", "fail", "blocked", "inconclusive"],
        required=True,
    )
    report_parser.add_argument("--evidence", action="append", default=[])

    sub.add_parser("write-final-report")
    aggressive_report_parser = sub.add_parser("write-aggressive-rbf-report")
    aggressive_report_parser.add_argument("--episodes", type=int, default=3)
    level4_report_parser = sub.add_parser("write-level4-report")
    level4_report_parser.add_argument("--episodes", type=int, default=10)
    object_swap_report_parser = sub.add_parser("write-object-swap-ood-rbf-report")
    object_swap_report_parser.add_argument("--episodes", type=int, default=10)
    stage_report_parser = sub.add_parser("write-stage-recognition-ablation-report")
    stage_report_parser.add_argument("--episodes", type=int, default=10)
    sub.add_parser("print-level0-command")
    sub.add_parser("print-level1-command")
    sub.add_parser("print-level1-commands")

    run_parser = sub.add_parser("run-level")
    _add_online_args(run_parser)
    run_parser.add_argument("--gpus", default="0")
    run_parser.add_argument("--timeout-seconds", type=int, default=28800)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--gpu-poll-interval-s", type=float, default=30.0)

    args = parser.parse_args()

    if args.cmd == "preflight":
        return preflight()
    if args.cmd == "init":
        return init(args.level, args.episodes, manifest_path=args.manifest_path)
    if args.cmd == "print-command":
        jobs = build_jobs(args.level, args.episodes, manifest_path=args.manifest_path)
        if args.job_index < 0 or args.job_index >= len(jobs):
            raise SystemExit(f"job-index must be between 0 and {len(jobs) - 1}")
        print(
            shlex.join(
                build_main_command(
                    jobs[args.job_index],
                    args.gpu,
                    args.timeout_seconds,
                    cached_functions_dir=args.cached_functions_dir,
                    offline_vlm=args.offline_vlm,
                )
            )
        )
        return 0
    if args.cmd == "write-report":
        if args.level == "rollout_rbf_ablation":
            print(write_rollout_rbf_report(episodes=3))
            return 0
        if args.level == "object_swap_ood_rbf":
            print(write_object_swap_ood_rbf_report(episodes=10))
            return 0
        if args.level == "stage_recognition_ablation":
            print(write_stage_recognition_ablation_report(episodes=10))
            return 0
        if args.level == "p2_adaptive_eds_rbf_pretest":
            print(write_p2_adaptive_eds_rbf_pretest_report())
            return 0
        print(write_level_report(args.level, args.verdict, args.evidence))
        return 0
    if args.cmd == "write-final-report":
        print(write_final_report())
        return 0
    if args.cmd == "write-aggressive-rbf-report":
        print(write_aggressive_rbf_report(args.episodes))
        return 0
    if args.cmd == "write-level4-report":
        print(write_level4_report(args.episodes))
        return 0
    if args.cmd == "write-object-swap-ood-rbf-report":
        print(write_object_swap_ood_rbf_report(args.episodes))
        return 0
    if args.cmd == "write-stage-recognition-ablation-report":
        print(write_stage_recognition_ablation_report(args.episodes))
        return 0
    if args.cmd == "print-level0-command":
        print(shlex.join(level0_command()))
        return 0
    if args.cmd == "print-level1-command":
        print(shlex.join(level1_command()))
        return 0
    if args.cmd == "print-level1-commands":
        for command in level1_commands():
            print(shlex.join(command))
        return 0
    if args.cmd == "run-level":
        return run_level(
            args.level,
            args.episodes,
            args.gpus,
            args.timeout_seconds,
            args.resume,
            cached_functions_dir=args.cached_functions_dir,
            offline_vlm=args.offline_vlm,
            manifest_path=args.manifest_path,
            gpu_poll_interval_s=args.gpu_poll_interval_s,
        )
    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
