#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Iterable


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))
EVIDENCE_ROOT = WORKTREE_ROOT / "docs" / "03_evidence" / "eds_steering"
RUN_ROOT = WORKTREE_ROOT / "outputs" / "rdt_eds_eval"
STATUS_CSV = EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
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
LEVEL2_METHODS = [
    method
    for method in METHODS
    if method["label"] in {"unguided", "p16_c10", "zero", "shuffled", "inverted"}
]
LEVEL3_METHODS = METHODS
LEVEL4_METHODS = [
    METHODS[0],
    {
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
    },
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


def build_jobs(level: str, episodes: int) -> list[dict[str, object]]:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    if level == "level2":
        suites = [BASE_SUITE]
        methods = LEVEL2_METHODS
    elif level == "level3":
        suites = [BASE_SUITE]
        methods = LEVEL3_METHODS
    elif level == "level4":
        suites = OOD_SUITES
        methods = LEVEL4_METHODS
    else:
        raise ValueError(f"Unsupported online level: {level}")

    jobs: list[dict[str, object]] = []
    for suite in suites:
        for method in methods:
            label = str(method["label"])
            job_id = f"{level}_{suite}_{label}"
            jobs.append(
                {
                    **method,
                    "job_id": job_id,
                    "level": level,
                    "suite": suite,
                    "episodes": episodes,
                }
            )
    return jobs


def build_main_command(
    job: dict[str, object],
    gpu: str,
    timeout_seconds: int,
) -> list[str]:
    del gpu, timeout_seconds
    output_dir = RUN_ROOT / str(job["job_id"])
    metrics_dir = output_dir / "eds_eval"
    is_level4 = job["level"] == "level4"
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
        "backend.libero.max_episode_steps=240",
        f"backend.libero.strict_perturbations={str(is_level4).lower()}",
        "main.use_vlm_stage_recognition=true",
        "perception.gemini_grounding.enabled=true",
        f"main.render={str(is_level4).lower()}",
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
    if is_level4:
        command.extend(
            [
                "perception.vlm_agent.api_max_retries=8",
                "perception.vlm_agent.api_retry_backoff_seconds=5.0",
                "perception.vlm_agent.api_retry_max_backoff_seconds=30.0",
            ]
        )
    if job["level"] == "level2":
        command.append("backend.libero.task_ids_filter=[0]")

    if job["method"] == "unguided":
        command.append("main.use_guidance=false")
    else:
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
    return command


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
    return RUN_ROOT / str(job["job_id"]) / "results.txt"


def _metrics_path(job: dict[str, object]) -> Path:
    return RUN_ROOT / str(job["job_id"]) / "eds_eval" / "eds_metrics.jsonl"


def _job_has_complete_outputs(job: dict[str, object]) -> bool:
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


def _mean(values: list[float]) -> float | None:
    finite = [value for value in values if isinstance(value, (int, float))]
    if not finite:
        return None
    return float(sum(finite) / len(finite))


def _artifact_counts(output_dir: Path) -> dict[str, int]:
    return {
        "videos": len(list(output_dir.glob("episode_*/*.mp4"))),
        "qualitative_png": len(list((output_dir / "eds_eval").glob("qualitative/**/*.png"))),
        "metrics_records": len(_read_jsonl(output_dir / "eds_eval" / "eds_metrics.jsonl")),
    }


def write_status(rows: list[dict[str, object]]) -> None:
    ensure_dirs()
    with STATUS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in STATUS_FIELDS})


def _status_row(job: dict[str, object], status: str, gpu: str = "") -> dict[str, object]:
    output_dir = RUN_ROOT / str(job["job_id"])
    return {
        **job,
        "status": status,
        "output_dir": str(output_dir),
        "metrics_dir": str(output_dir / "eds_eval"),
        "log_file": str(EVIDENCE_ROOT / "logs" / f"{job['job_id']}.log"),
        "gpu": gpu,
    }


def init(level: str, episodes: int) -> int:
    jobs = build_jobs(level, episodes)
    write_status([_status_row(job, "pending") for job in jobs])
    print(STATUS_CSV)
    return 0


def _evidence_lines(evidence: str | Iterable[str]) -> list[str]:
    if isinstance(evidence, str):
        return [evidence] if evidence else []
    return [str(item) for item in evidence]


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
    for level in ["level0", "level1", "level2", "level3", "level4"]:
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


def run_job(job: dict[str, object], gpu: str, timeout_seconds: int) -> dict[str, object]:
    ensure_dirs()
    output_dir = RUN_ROOT / str(job["job_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = EVIDENCE_ROOT / "logs" / f"{job['job_id']}.log"
    command = build_main_command(job, gpu, timeout_seconds)
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("OPENAI_BASE_URL", "https://api.poe.com/v1")
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
    output_dir = RUN_ROOT / str(job["job_id"])
    result_summary = _parse_results_file(output_dir / "results.txt")
    artifacts = _artifact_counts(output_dir)
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
        "start_time": start,
        "end_time": now_iso(),
    }


def run_level(level: str, episodes: int, gpus: str, timeout_seconds: int, resume: bool = False) -> int:
    ensure_dirs()
    gpu_list = [gpu.strip() for gpu in gpus.split(",") if gpu.strip()]
    if not gpu_list:
        raise SystemExit("No GPUs specified")

    jobs = build_jobs(level, episodes)
    rows_by_id = {}
    runnable_jobs = []
    for job in jobs:
        job_id = str(job["job_id"])
        if resume and _job_has_complete_outputs(job):
            output_dir = RUN_ROOT / str(job["job_id"])
            result_summary = _parse_results_file(output_dir / "results.txt")
            artifacts = _artifact_counts(output_dir)
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
                "start_time": "resume-skip",
                "end_time": now_iso(),
            }
        else:
            rows_by_id[job_id] = _status_row(job, "pending")
            runnable_jobs.append(job)
    write_status(list(rows_by_id.values()))

    job_queue: Queue[dict[str, object]] = Queue()
    for job in runnable_jobs:
        job_queue.put(job)

    lock = Lock()

    def worker(gpu: str) -> None:
        while True:
            try:
                job = job_queue.get_nowait()
            except Empty:
                return
            job_id = str(job["job_id"])
            try:
                with lock:
                    rows_by_id[job_id] = _status_row(job, "running", gpu=gpu)
                    write_status(list(rows_by_id.values()))
                row = run_job(job, gpu=gpu, timeout_seconds=timeout_seconds)
                with lock:
                    rows_by_id[job_id] = row
                    write_status(list(rows_by_id.values()))
            finally:
                job_queue.task_done()

    threads = [Thread(target=worker, args=(gpu,), daemon=False) for gpu in gpu_list]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if level == "level4":
        print(write_level4_report(episodes))

    failures = [row for row in rows_by_id.values() if row.get("status") != "done"]
    return 1 if failures else 0


def _add_online_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--level", choices=["level2", "level3", "level4"], required=True)
    parser.add_argument("--episodes", type=int, default=10)


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
        choices=["level0", "level1", "level2", "level3", "level4"],
        required=True,
    )
    report_parser.add_argument(
        "--verdict",
        choices=["pass", "fail", "blocked", "inconclusive"],
        required=True,
    )
    report_parser.add_argument("--evidence", action="append", default=[])

    sub.add_parser("write-final-report")
    level4_report_parser = sub.add_parser("write-level4-report")
    level4_report_parser.add_argument("--episodes", type=int, default=10)
    sub.add_parser("print-level0-command")
    sub.add_parser("print-level1-command")
    sub.add_parser("print-level1-commands")

    run_parser = sub.add_parser("run-level")
    _add_online_args(run_parser)
    run_parser.add_argument("--gpus", default="0")
    run_parser.add_argument("--timeout-seconds", type=int, default=28800)
    run_parser.add_argument("--resume", action="store_true")

    args = parser.parse_args()

    if args.cmd == "preflight":
        return preflight()
    if args.cmd == "init":
        return init(args.level, args.episodes)
    if args.cmd == "print-command":
        jobs = build_jobs(args.level, args.episodes)
        if args.job_index < 0 or args.job_index >= len(jobs):
            raise SystemExit(f"job-index must be between 0 and {len(jobs) - 1}")
        print(shlex.join(build_main_command(jobs[args.job_index], args.gpu, args.timeout_seconds)))
        return 0
    if args.cmd == "write-report":
        print(write_level_report(args.level, args.verdict, args.evidence))
        return 0
    if args.cmd == "write-final-report":
        print(write_final_report())
        return 0
    if args.cmd == "write-level4-report":
        print(write_level4_report(args.episodes))
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
        return run_level(args.level, args.episodes, args.gpus, args.timeout_seconds, args.resume)
    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
