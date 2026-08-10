#!/usr/bin/env python3
"""Audit and freeze the approved physical stage/guidance FSM study."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = Path(__file__).resolve().parents[1]
for import_root in (SCRIPT_DIR, WORKTREE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import eds_qd_search_budget_sweep_audit as sweep_audit
import eds_qd_stage_guidance_transition_runner as runner
import eds_quality_diversity_audit as prior_audit


ANALYSIS_PATH = runner.EXPERIMENT_ROOT / "analysis/formal_audit.json"
REPORT_PATH = runner.EXPERIMENT_ROOT / "analysis/final_report.md"
DECISION_PATH = runner.EXPERIMENT_ROOT / "manifests/decision_manifest.json"
JOB_AUDIT_ROOT = runner.EXPERIMENT_ROOT / "analysis/jobs"
HISTORICAL_AUDIT_PATH = Path(
    "/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/"
    "outputs/search_budget_sweep_20260808/analysis/formal_audit.json"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    if not path.is_file():
        return records, [f"missing JSONL: {path}"]
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            value = json.loads(line)
        except (ValueError, RecursionError) as exc:
            failures.append(f"{path.name}:{line_number}: {type(exc).__name__}")
            continue
        if not isinstance(value, dict):
            failures.append(f"{path.name}:{line_number}: record is not an object")
            continue
        records.append(value)
    return records, failures


def _latency_summary(values: list[int]) -> dict[str, object] | str:
    if not values:
        return "N/A"
    return {
        "event_count": len(values),
        "max_steps": max(values),
        "values_steps": values,
        "passed": max(values) <= 1,
    }


def fsm_mechanism_gate(
    traces: list[dict[str, Any]], *, test_evidence_passed: bool
) -> dict[str, object]:
    """Evaluate the preregistered physical-FSM mechanism invariants."""
    mapping = {
        "ACQUIRE": (1, True),
        "GRASP_VERIFY": (1, True),
        "TRANSPORT": (2, False),
        "RELEASE_VERIFY": (2, False),
        "RECOVERY": (1, True),
        "DONE": (0, False),
    }
    guidance_off_unconfirmed = 0
    illegal_combinations = 0
    missing_transition_evidence = 0
    transition_without_invalidation = 0
    vlm_control_rows = 0
    drop_latencies: list[int] = []
    regrasp_latencies: list[int] = []
    transition_count = 0
    transition_confusion: Counter[str] = Counter()
    seen_drop_by_episode: set[int] = set()

    for row in traces:
        state_after = str(row.get("state_after", ""))
        guidance = row.get("use_guidance")
        confirmed = row.get("grasp_confirmed") is True
        if guidance is False and not confirmed and state_after not in {"DONE"}:
            guidance_off_unconfirmed += 1
        if mapping.get(state_after) != (row.get("current_stage"), guidance):
            illegal_combinations += 1
        advisory = row.get("vlm_advisory")
        if not isinstance(advisory, dict) or advisory.get("control_authority") is not False:
            vlm_control_rows += 1
        if row.get("state_changed") is not True:
            continue
        transition_count += 1
        transition_confusion[
            f"{row.get('state_before')}->{state_after}"
        ] += 1
        evidence = row.get("physical_evidence")
        if not row.get("transition_reason") or not isinstance(evidence, dict) or not evidence:
            missing_transition_evidence += 1
        if row.get("chunk_invalidated") is not True:
            transition_without_invalidation += 1
        latency = row.get("commit_latency_steps")
        if not isinstance(latency, int) or isinstance(latency, bool) or latency < 0:
            latency = 10**9
        episode = int(row.get("episode", -1))
        if state_after == "RECOVERY" and str(row.get("state_before")) in {
            "TRANSPORT",
            "RELEASE_VERIFY",
        }:
            drop_latencies.append(latency)
            seen_drop_by_episode.add(episode)
        if (
            state_after == "TRANSPORT"
            and str(row.get("state_before")) == "GRASP_VERIFY"
            and episode in seen_drop_by_episode
        ):
            regrasp_latencies.append(latency)

    evidence_coverage = (
        (transition_count - missing_transition_evidence) / transition_count
        if transition_count
        else 0.0
    )
    drop_summary = _latency_summary(drop_latencies)
    regrasp_summary = _latency_summary(regrasp_latencies)
    latency_passed = all(
        value == "N/A" or value.get("passed") is True
        for value in (drop_summary, regrasp_summary)
    )
    vlm_replay = {
        "passed": bool(traces) and vlm_control_rows == 0,
        "trace_row_count": len(traces),
        "control_authority_violation_count": vlm_control_rows,
        "method": "trace replay of advisory control_authority and FSM-derived state",
    }
    passed = (
        bool(traces)
        and bool(test_evidence_passed)
        and guidance_off_unconfirmed == 0
        and illegal_combinations == 0
        and evidence_coverage == 1.0
        and transition_without_invalidation == 0
        and vlm_replay["passed"] is True
        and latency_passed
    )
    return {
        "passed": passed,
        "trace_row_count": len(traces),
        "transition_count": transition_count,
        "guidance_off_without_grasp_confirmed_count": guidance_off_unconfirmed,
        "illegal_stage_guidance_combination_count": illegal_combinations,
        "transition_evidence_coverage": evidence_coverage,
        "transition_without_chunk_invalidation_count": transition_without_invalidation,
        "vlm_shadow_replay": vlm_replay,
        "drop_commit_latency": drop_summary,
        "regrasp_commit_latency": regrasp_summary,
        "transition_confusion": dict(sorted(transition_confusion.items())),
        "test_evidence_passed": bool(test_evidence_passed),
    }


def paired_gate_analysis(jobs: list[dict[str, Any]]) -> dict[str, object]:
    by_key = {
        (int(job["round"]), str(job["transition_mode"])): job for job in jobs
    }
    rounds: dict[str, object] = {}
    gained_total = 0
    lost_total = 0
    legacy_total = 0
    fsm_total = 0
    round_gate_passed = True
    for round_id in (0, 1):
        legacy = by_key.get((round_id, "legacy_vlm"), {})
        fsm = by_key.get((round_id, "physical_fsm_v1"), {})
        legacy_success = {int(value) for value in legacy.get("success_tasks", [])}
        fsm_success = {int(value) for value in fsm.get("success_tasks", [])}
        gained = sorted(fsm_success - legacy_success)
        lost = sorted(legacy_success - fsm_success)
        legacy_count = int(legacy.get("success_count", 0))
        fsm_count = int(fsm.get("success_count", 0))
        legacy_total += legacy_count
        fsm_total += fsm_count
        gained_total += len(gained)
        lost_total += len(lost)
        round_gate = fsm_count >= 5
        round_gate_passed = round_gate_passed and round_gate
        rounds[str(round_id)] = {
            "legacy_success_count": legacy_count,
            "fsm_success_count": fsm_count,
            "legacy_success_rate": legacy_count / 10,
            "fsm_success_rate": fsm_count / 10,
            "fsm_round_5_of_10_gate_passed": round_gate,
            "gained_tasks": gained,
            "lost_tasks": lost,
            "retained_tasks": sorted(fsm_success & legacy_success),
            "both_failed_tasks": sorted(set(range(10)) - (fsm_success | legacy_success)),
        }
    all_jobs_valid = len(jobs) == 4 and all(job.get("valid") is True for job in jobs)
    safety_passed = len(jobs) == 4 and all(
        job.get("safety_gate", {}).get("passed") is True for job in jobs
    )
    fsm_jobs = [
        job for job in jobs if job.get("transition_mode") == "physical_fsm_v1"
    ]
    mechanism_passed = len(fsm_jobs) == 2 and all(
        job.get("fsm_mechanism_gate", {}).get("passed") is True
        for job in fsm_jobs
    )
    mean_rate = fsm_total / 20
    mean_gate = fsm_total >= 10
    paired_gate = gained_total >= lost_total
    total_gate = fsm_total >= legacy_total
    adoption = all(
        (
            all_jobs_valid,
            mean_gate,
            safety_passed,
            mechanism_passed,
            paired_gate,
            total_gate,
        )
    )
    return {
        "rounds": rounds,
        "legacy_total_success_count": legacy_total,
        "fsm_total_success_count": fsm_total,
        "legacy_mean_success_rate": legacy_total / 20,
        "fsm_mean_success_rate": mean_rate,
        "fsm_round_gates_passed": round_gate_passed,
        "mean_gate_passed": mean_gate,
        "all_four_jobs_valid": all_jobs_valid,
        "safety_gate_passed": safety_passed,
        "fsm_mechanism_gate_passed": mechanism_passed,
        "aggregate_gained_task_count": gained_total,
        "aggregate_lost_task_count": lost_total,
        "paired_gained_not_less_than_lost": paired_gate,
        "fsm_total_not_less_than_legacy": total_gate,
        "adoption_passed": adoption,
        "decision": (
            "adopt_physical_fsm_v1" if adoption else "negative_result_keep_legacy"
        ),
        "additional_experiments_authorized": False,
    }


def _configure_prior_audit() -> None:
    sweep_audit.runner = runner
    prior_audit.runner = runner
    prior_audit.OUTPUT_TARGET = runner.OUTPUT_TARGET
    prior_audit.EXPERIMENT_ROOT = runner.EXPERIMENT_ROOT
    prior_audit.WORKTREE_ROOT = WORKTREE_ROOT
    prior_audit.qd_mechanism_hard_gate = sweep_audit.qd_mechanism_hard_gate
    prior_audit.validate_parent_allocation_replay = (
        sweep_audit.validate_parent_allocation_replay
    )


def _expected_formal_cells() -> set[tuple[str, int, int]]:
    return {
        (str(profile["label"]), task, runner.ROUND_SEEDS[int(profile["round"])][task])
        for profile in runner.formal_profiles()
        for task in range(10)
    }


def _trace_completeness(
    traces: list[dict[str, Any]], failures: list[str]
) -> dict[str, object]:
    required = {
        "schema",
        "episode",
        "task_id",
        "episode_seed",
        "global_step",
        "state_before",
        "state_after",
        "transition_reason",
        "state_changed",
        "current_stage",
        "use_guidance",
        "grasp_confirmed",
        "confirmation_counters",
        "chunk_invalidated",
        "physical_evidence",
        "vlm_advisory",
    }
    missing_fields = sum(not required <= set(row) for row in traces)
    episodes = sorted(
        {int(row["episode"]) for row in traces if isinstance(row.get("episode"), int)}
    )
    task_ids = sorted(
        {int(row["task_id"]) for row in traces if isinstance(row.get("task_id"), int)}
    )
    if missing_fields:
        failures.append(f"{missing_fields} FSM trace rows miss required fields")
    if episodes != list(range(10)):
        failures.append("FSM trace does not cover exactly episodes 0..9")
    if task_ids != list(range(10)):
        failures.append("FSM trace does not cover exactly tasks 0..9")
    return {
        "passed": not missing_fields
        and episodes == list(range(10))
        and task_ids == list(range(10)),
        "row_count": len(traces),
        "episodes": episodes,
        "task_ids": task_ids,
        "missing_required_field_row_count": missing_fields,
    }


def _safety_gate(job: dict[str, Any], credential_passed: bool) -> dict[str, object]:
    checks = {
        "ten_unique_records": int(job.get("accepted_episode_count", 0)) == 10,
        "ten_videos": int(job.get("video_count", 0)) == 10,
        "metrics_present": int(job.get("metrics_record_count", 0)) > 0,
        "fingerprints_present": bool(job.get("config_fingerprint"))
        and bool(job.get("code_state_sha256")),
        "zero_nonfinite": int(job.get("nonfinite_count", -1)) == 0,
        "zero_action_mask_violation": int(
            job.get("action_mask_violation_count", -1)
        )
        == 0,
        "zero_qd_fallback": int(job.get("qd_fallback_count", -1)) == 0,
        "zero_qpos_execution_error": int(
            job.get("execution_qpos_error_episodes", -1)
        )
        == 0,
        "credential_audit": credential_passed,
        "qd_accounting": job.get("mechanism_hard", {}).get("passed") is True,
    }
    return {"passed": all(checks.values()), "checks": checks}


def _qualitative_video_audit(
    output_dir: Path, traces: list[dict[str, Any]]
) -> dict[str, object]:
    events = []
    for row in traces:
        if row.get("state_changed") is not True or row.get("state_after") != "RECOVERY":
            continue
        episode = int(row.get("episode", -1))
        videos = sorted((output_dir / f"episode_{episode + 1}").glob("*.mp4"))
        video = videos[0] if len(videos) == 1 else None
        readable = False
        if video is not None:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_name,nb_frames",
                    "-of",
                    "json",
                    str(video),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            readable = probe.returncode == 0
        events.append(
            {
                "episode": episode,
                "task_id": row.get("task_id"),
                "global_step": row.get("global_step"),
                "transition": f"{row.get('state_before')}->{row.get('state_after')}",
                "reason": row.get("transition_reason"),
                "physical_evidence": row.get("physical_evidence"),
                "video_path": str(video) if video else None,
                "video_readable": readable,
            }
        )
    return {
        "event_count": len(events),
        "status": "N/A" if not events else "audited",
        "all_event_videos_readable": (
            "N/A" if not events else all(event["video_readable"] for event in events)
        ),
        "events": events,
    }


def _gpu_audit() -> dict[str, object]:
    manifests = sorted((runner.EXPERIMENT_ROOT / "manifests").glob("gpu_*.json"))
    rows = []
    failures = []
    dispatch_count = 0
    for path in manifests:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"{path.name}: {type(exc).__name__}")
            continue
        selected = [int(value) for value in payload.get("selected_gpu_indices", [])]
        eligible = {int(value) for value in payload.get("eligible_gpu_indices", [])}
        if "dispatch" in path.name:
            dispatch_count += 1
            if not selected:
                failures.append(f"{path.name}: no selected GPU")
            if not set(selected) <= eligible:
                failures.append(f"{path.name}: selected GPU not eligible")
            if any(value not in runner.ALLOWED_GPU_INDICES for value in selected):
                failures.append(f"{path.name}: GPU outside 0..7")
            if payload.get("external_compute_colocation_authorized") is not False:
                failures.append(f"{path.name}: external colocation not forbidden")
        rows.append(
            {
                "path": str(path),
                "sha256": _sha256_file(path),
                "selected_gpu_indices": selected,
                "eligible_gpu_indices": sorted(eligible),
            }
        )
    if dispatch_count == 0:
        failures.append("no GPU dispatch admission manifest")
    return {
        "passed": not failures,
        "dispatch_manifest_count": dispatch_count,
        "manifests": rows,
        "failures": failures,
    }


def _git_audit(run_manifest: dict[str, Any]) -> dict[str, object]:
    source = Path("/home/hynx/VLA-Pilot++/.worktrees/exp/eds-quality-diversity")

    def git(path: Path, *args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=path, text=True).strip()

    failures = []
    target_head = git(WORKTREE_ROOT, "rev-parse", "HEAD")
    target_branch = git(WORKTREE_ROOT, "branch", "--show-current")
    target_status = git(WORKTREE_ROOT, "status", "--short")
    source_head = git(source, "rev-parse", "HEAD")
    source_branch = git(source, "branch", "--show-current")
    source_status = git(source, "status", "--short")
    provenance = run_manifest.get("provenance", {})
    if target_head != provenance.get("code_commit"):
        failures.append("target HEAD changed after manifest freeze")
    if target_branch != runner.TARGET_BRANCH:
        failures.append("target branch mismatch")
    if target_status:
        failures.append("target worktree is dirty")
    if source_head != runner.BASE_COMMIT or source_branch != "exp/eds-quality-diversity":
        failures.append("source provenance changed")
    if source_status:
        failures.append("source worktree is dirty")
    return {
        "passed": not failures,
        "target": {
            "path": str(WORKTREE_ROOT),
            "head": target_head,
            "branch": target_branch,
            "status": target_status or "clean",
        },
        "source": {
            "path": str(source),
            "head": source_head,
            "branch": source_branch,
            "status": source_status or "clean",
        },
        "failures": failures,
    }


def process_audit() -> dict[str, object]:
    output = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True)
    own_pid = os.getpid()
    matches = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid == own_pid or "ps -eo pid=,args=" in command:
            continue
        try:
            process_cwd = Path(f"/proc/{pid}/cwd").resolve(strict=True)
        except (OSError, RuntimeError):
            process_cwd = None
        relevant = bool(
            (
                process_cwd == WORKTREE_ROOT.resolve(strict=True)
                or str(WORKTREE_ROOT) in command
            )
            and (
                "main.py" in command
                or "eds_qd_stage_guidance_transition_runner.py" in command
            )
        )
        if relevant:
            matches.append(
                {
                    "pid": pid,
                    "command": command,
                    "cwd": str(process_cwd) if process_cwd else None,
                }
            )
    return {"passed": not matches, "residual_processes": matches}


def _historical_background() -> dict[str, object]:
    if not HISTORICAL_AUDIT_PATH.is_file():
        return {"present": False, "path": str(HISTORICAL_AUDIT_PATH)}
    payload = json.loads(HISTORICAL_AUDIT_PATH.read_text(encoding="utf-8"))
    label = "eds_qd_uniform_expand20_p48_k20"
    job = next((row for row in payload.get("jobs", []) if row.get("label") == label), None)
    return {
        "present": job is not None,
        "path": str(HISTORICAL_AUDIT_PATH),
        "sha256": _sha256_file(HISTORICAL_AUDIT_PATH),
        "cross_run_background_only": True,
        "label": label,
        "success_count": job.get("success_count") if job else None,
        "success_tasks": job.get("success_tasks") if job else None,
    }


def audit_formal() -> dict[str, object]:
    _configure_prior_audit()
    run_manifest = json.loads(runner.RUN_MANIFEST_PATH.read_text(encoding="utf-8"))
    test_evidence = json.loads(runner.TEST_EVIDENCE_PATH.read_text(encoding="utf-8"))
    credential = prior_audit.scan_credentials(
        [runner.EXPERIMENT_ROOT, WORKTREE_ROOT]
    )
    jobs: list[dict[str, Any]] = []
    for frozen_job in runner.build_jobs(runner.FORMAL_LEVEL, 10):
        audited, _metrics = prior_audit.audit_job(
            frozen_job, credential_passed=bool(credential["passed"])
        )
        audited["round"] = int(frozen_job["round"])
        audited["transition_mode"] = str(frozen_job["transition_mode"])
        if audited.get("mechanism_hard", {}).get("passed") is not True:
            audited["validity_failures"] = list(
                dict.fromkeys(
                    [*audited.get("validity_failures", []), "QD mechanism gate failed"]
                )
            )
            audited["valid"] = False
        trace_path = Path(audited["output_dir"]) / "eds_eval/fsm_trace.jsonl"
        if frozen_job["transition_mode"] == "physical_fsm_v1":
            traces, trace_failures = _read_jsonl(trace_path)
            completeness = _trace_completeness(traces, trace_failures)
            mechanism = fsm_mechanism_gate(
                traces, test_evidence_passed=bool(test_evidence.get("passed"))
            )
            if trace_failures or not completeness["passed"]:
                mechanism["passed"] = False
                mechanism["trace_failures"] = trace_failures
            audited["fsm_trace"] = completeness
            audited["fsm_mechanism_gate"] = mechanism
            audited["qualitative_drop_recovery_video_audit"] = (
                _qualitative_video_audit(Path(audited["output_dir"]), traces)
            )
        else:
            audited["fsm_trace"] = {"applicable": False, "passed": True}
            audited["fsm_mechanism_gate"] = {
                "applicable": False,
                "passed": True,
            }
            audited["qualitative_drop_recovery_video_audit"] = {
                "status": "N/A",
                "event_count": 0,
            }
        audited["safety_gate"] = _safety_gate(
            audited, bool(credential["passed"])
        )
        if audited["safety_gate"]["passed"] is not True:
            audited["valid"] = False
            audited["validity_failures"] = list(
                dict.fromkeys(
                    [*audited.get("validity_failures", []), "safety gate failed"]
                )
            )
        JOB_AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
        job_path = JOB_AUDIT_ROOT / f"{audited['label']}.json"
        job_path.write_text(
            json.dumps(audited, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        jobs.append(audited)

    ledger = prior_audit.audit_attempt_ledger(
        runner.ATTEMPT_LEDGER_PATH,
        expected_formal=_expected_formal_cells(),
        expected_preflight=set(),
        cap=runner.ATTEMPT_CAP,
        recovery_limit=runner.RETRY_ATTEMPT_LIMIT,
    )
    paired = paired_gate_analysis(jobs)
    storage = runner.storage_preflight()
    gpu = _gpu_audit()
    git = _git_audit(run_manifest)
    processes = process_audit()
    completed = sum(int(job.get("accepted_episode_count", 0)) for job in jobs)
    invalid = [str(job["label"]) for job in jobs if job.get("valid") is not True]
    payload: dict[str, object] = {
        "schema": "eds-qd-stage-guidance-transition-formal-audit-v1",
        "created_at": _now(),
        "jobs": jobs,
        "paired_analysis": paired,
        "completion": {
            "status": "complete" if completed == 40 else "incomplete",
            "formal_expected_episodes": 40,
            "formal_completed_episodes": completed,
            "formal_missing_episodes": 40 - completed,
            "invalid_or_failed_jobs": invalid,
        },
        "attempt_ledger": ledger,
        "storage_audit": storage,
        "gpu_audit": gpu,
        "credential_audit": credential,
        "git_audit": git,
        "process_audit": processes,
        "historical_background": _historical_background(),
        "run_manifest": {
            "path": str(runner.RUN_MANIFEST_PATH),
            "sha256": _sha256_file(runner.RUN_MANIFEST_PATH),
            "read_only": stat.S_IMODE(runner.RUN_MANIFEST_PATH.stat().st_mode)
            == 0o444,
        },
        "test_evidence": {
            "path": str(runner.TEST_EVIDENCE_PATH),
            "sha256": _sha256_file(runner.TEST_EVIDENCE_PATH),
            "passed": test_evidence.get("passed") is True,
        },
        "additional_experiments_authorized": False,
    }
    audit_passed = all(
        (
            completed == 40,
            ledger.get("passed") is True,
            storage.get("passed") is True,
            gpu.get("passed") is True,
            credential.get("passed") is True,
            git.get("passed") is True,
            processes.get("passed") is True,
            payload["run_manifest"]["read_only"] is True,
        )
    )
    payload["audit_passed"] = audit_passed
    if prior_audit._contains_credential(payload):
        raise RuntimeError("formal audit contains credential material")
    ANALYSIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def freeze_report(text: str) -> dict[str, str]:
    return prior_audit.freeze_report(text, REPORT_PATH)


def freeze_decision_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return prior_audit.freeze_decision_manifest(payload, DECISION_PATH)


def verify_decision_manifest() -> dict[str, Any]:
    return prior_audit.verify_decision_manifest(DECISION_PATH)


def _report_text(analysis: dict[str, Any]) -> str:
    paired = analysis["paired_analysis"]
    lines = [
        "# EDS-QD Stage/Guidance Transition 最终报告",
        "",
        f"生成时间：`{analysis['created_at']}`",
        "",
        "## 结论",
        "",
        f"- 决策：`{paired['decision']}`。",
        f"- FSM 两轮合计：`{paired['fsm_total_success_count']}/20`，mean SR "
        f"`{paired['fsm_mean_success_rate']:.2f}`；mean gate："
        f"`{'PASS' if paired['mean_gate_passed'] else 'FAIL'}`。",
        f"- FSM mechanism gate：`{'PASS' if paired['fsm_mechanism_gate_passed'] else 'FAIL'}`；"
        f"safety gate：`{'PASS' if paired['safety_gate_passed'] else 'FAIL'}`。",
        "",
        "## 两轮 paired 结果",
        "",
    ]
    for round_id in ("0", "1"):
        row = paired["rounds"][round_id]
        lines.append(
            f"- Round {round_id}: legacy `{row['legacy_success_count']}/10`，"
            f"FSM `{row['fsm_success_count']}/10`，gained `{row['gained_tasks']}`，"
            f"lost `{row['lost_tasks']}`。"
        )
    lines.extend(
        [
            "",
            "## 逐 job 审计",
            "",
        ]
    )
    for job in analysis["jobs"]:
        lines.append(
            f"- `{job['label']}`: success `{job['success_count']}/10`，"
            f"valid `{'PASS' if job['valid'] else 'FAIL'}`，"
            f"safety `{'PASS' if job['safety_gate']['passed'] else 'FAIL'}`，"
            f"FSM mechanism `{'PASS' if job['fsm_mechanism_gate']['passed'] else 'FAIL'}`。"
        )
    lines.extend(
        [
            "",
            "## 执行与审计",
            "",
            f"- formal episodes：`{analysis['completion']['formal_completed_episodes']}/40`；"
            f"attempts：`{analysis['attempt_ledger']['actual_episode_attempt_count']}/44`。",
            f"- GPU：`{'PASS' if analysis['gpu_audit']['passed'] else 'FAIL'}`；"
            f"shared2 storage：`{'PASS' if analysis['storage_audit']['passed'] else 'FAIL'}`。",
            f"- Git：`{'PASS' if analysis['git_audit']['passed'] else 'FAIL'}`；"
            f"credential：`{'PASS' if analysis['credential_audit']['passed'] else 'FAIL'}`；"
            f"process cleanup：`{'PASS' if analysis['process_audit']['passed'] else 'FAIL'}`。",
            f"- 无效或失败 jobs：`{analysis['completion']['invalid_or_failed_jobs']}`。",
            "- 本设计不授权依据结果追加实验或调参。",
            "",
        ]
    )
    return "\n".join(lines)


def finalize() -> dict[str, Any]:
    analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
    if analysis.get("audit_passed") is not True:
        raise RuntimeError("formal audit is not complete and clean")
    if process_audit().get("passed") is not True:
        raise RuntimeError("residual evaluation process detected")
    report = freeze_report(_report_text(analysis))
    payload = {
        "schema": "eds-qd-stage-guidance-transition-decision-manifest-v1",
        "created_at": _now(),
        "decision": analysis["paired_analysis"]["decision"],
        "adoption_passed": analysis["paired_analysis"]["adoption_passed"],
        "additional_experiments_authorized": False,
        "paired_analysis": analysis["paired_analysis"],
        "completion": analysis["completion"],
        "attempt_ledger": {
            key: analysis["attempt_ledger"].get(key)
            for key in (
                "passed",
                "actual_episode_attempt_count",
                "formal_unique_cells",
                "recovery_attempts",
                "failures",
            )
        },
        "audits": {
            key: analysis[key]
            for key in (
                "gpu_audit",
                "storage_audit",
                "credential_audit",
                "git_audit",
                "process_audit",
            )
        },
        "jobs": [
            {
                key: job.get(key)
                for key in (
                    "label",
                    "round",
                    "transition_mode",
                    "valid",
                    "validity_failures",
                    "success_count",
                    "success_tasks",
                    "task_outcomes",
                    "safety_gate",
                    "fsm_mechanism_gate",
                    "config_fingerprint",
                    "code_state_sha256",
                    "checksums",
                )
            }
            for job in analysis["jobs"]
        ],
        "run_manifest": analysis["run_manifest"],
        "formal_audit": {
            "path": str(ANALYSIS_PATH),
            "sha256": _sha256_file(ANALYSIS_PATH),
        },
        "report": report,
    }
    frozen = freeze_decision_manifest(payload)
    verify_decision_manifest()
    return frozen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("audit-formal", "finalize", "verify"))
    args = parser.parse_args()
    if args.command == "audit-formal":
        print(json.dumps(audit_formal(), indent=2, sort_keys=True))
        return 0
    if args.command == "finalize":
        print(json.dumps(finalize(), indent=2, sort_keys=True))
        return 0
    print(json.dumps(verify_decision_manifest(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
