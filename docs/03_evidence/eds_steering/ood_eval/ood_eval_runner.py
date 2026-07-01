#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = SCRIPT_DIR.parents[3]
MANIFEST = SCRIPT_DIR / "jobs_manifest.csv"
STATUS = SCRIPT_DIR / "job_status.csv"
LOCK = SCRIPT_DIR / ".job_status.lock"
LOG_DIR = SCRIPT_DIR / "logs"
MARKER_DIR = SCRIPT_DIR / "markers"
REPORT = SCRIPT_DIR / "rdt_eds_ood_evaluation.md"
TERMINAL_STATUSES = {"done", "failed", "timeout", "paused"}

STATUS_FIELDS = [
    "job_id",
    "status",
    "suite",
    "method",
    "eds_label",
    "population_size",
    "cem_iters",
    "use_cem",
    "max_steps",
    "gpu_id",
    "start_time",
    "end_time",
    "exit_code",
    "success_count",
    "success_rate",
    "wall_clock_s",
    "output_dir",
    "log_file",
    "note",
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKTREE_ROOT))
    except ValueError:
        return str(path)


def abs_from_root(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else WORKTREE_ROOT / path


def ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MARKER_DIR.mkdir(parents=True, exist_ok=True)
    (WORKTREE_ROOT / "outputs" / "ood_eval").mkdir(parents=True, exist_ok=True)


def read_manifest() -> List[Dict[str, str]]:
    with MANIFEST.open(newline="") as f:
        return list(csv.DictReader(f))


def read_status_unlocked() -> Dict[str, Dict[str, str]]:
    if not STATUS.exists():
        return {}
    with STATUS.open(newline="") as f:
        return {row["job_id"]: row for row in csv.DictReader(f)}


def write_status_unlocked(rows: Iterable[Dict[str, str]]) -> None:
    tmp = STATUS.with_suffix(".tmp")
    ordered = sorted(rows, key=lambda row: row["job_id"])
    with tmp.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        for row in ordered:
            writer.writerow({field: row.get(field, "") for field in STATUS_FIELDS})
    tmp.replace(STATUS)


def with_lock(fn):
    ensure_dirs()
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def marker(job_id: str, kind: str) -> Path:
    return MARKER_DIR / f"{job_id}.{kind}.marker"


def parse_results(output_dir: Path) -> tuple[str, str]:
    results = output_dir / "results.txt"
    if not results.exists():
        return "", ""
    text = results.read_text(errors="replace")
    count = ""
    rate = ""
    m = re.search(r"Success count:\s*([0-9]+/[0-9]+)", text)
    if m:
        count = m.group(1)
    m = re.search(r"Success rate:\s*([0-9.]+)%", text)
    if m:
        rate = m.group(1)
    return count, rate


def parse_wall_clock(log_file: Path) -> str:
    if not log_file.exists():
        return ""
    real = ""
    for line in log_file.read_text(errors="replace").splitlines():
        m = re.match(r"real\s+([0-9.]+)", line.strip())
        if m:
            real = m.group(1)
    return real


def job_to_status_row(
    job: Dict[str, str],
    existing: Optional[Dict[str, str]] = None,
    *,
    reset_running: bool = False,
) -> Dict[str, str]:
    output_dir = abs_from_root(job["output_dir"])
    log_file = abs_from_root(job["log_file"])
    row = dict(existing or {})
    row.update(
        {
            "job_id": job["job_id"],
            "suite": job["suite"],
            "method": job["method"],
            "eds_label": job["eds_label"],
            "population_size": job["population_size"],
            "cem_iters": job["cem_iters"],
            "use_cem": job["use_cem"],
            "max_steps": job["max_steps"],
            "output_dir": rel(output_dir),
            "log_file": rel(log_file),
        }
    )
    if (output_dir / "results.txt").exists() or marker(job["job_id"], "done").exists():
        count, rate = parse_results(output_dir)
        row.update(
            {
                "status": "done",
                "success_count": count,
                "success_rate": rate,
                "wall_clock_s": parse_wall_clock(log_file),
                "note": "results.txt present",
            }
        )
    elif marker(job["job_id"], "paused").exists():
        row["status"] = "paused"
        row.setdefault("note", "paused")
    elif marker(job["job_id"], "timeout").exists() and row.get("status") != "running":
        row["status"] = "timeout"
    elif marker(job["job_id"], "failed").exists() and row.get("status") != "running":
        row["status"] = "failed"
    else:
        row.setdefault("status", "pending")
        if reset_running and row.get("status") == "running":
            row["status"] = "pending"
            row["gpu_id"] = ""
            row["note"] = "reset stale running state"
    for field in STATUS_FIELDS:
        row.setdefault(field, "")
    return row


def init_status(*, reset_running: bool = False) -> None:
    def _init():
        existing = read_status_unlocked()
        rows = []
        for job in read_manifest():
            rows.append(job_to_status_row(job, existing.get(job["job_id"]), reset_running=reset_running))
        write_status_unlocked(rows)

    with_lock(_init)
    write_report()


def claim_next_job(gpu_id: str) -> Optional[Dict[str, str]]:
    def _claim():
        manifest = {job["job_id"]: job for job in read_manifest()}
        status = read_status_unlocked()
        rows = []
        claim: Optional[Dict[str, str]] = None
        for job_id, job in manifest.items():
            row = job_to_status_row(job, status.get(job_id))
            if claim is None and row.get("status") == "pending":
                claim = job
                row.update(
                    {
                        "status": "running",
                        "gpu_id": gpu_id,
                        "start_time": now_iso(),
                        "end_time": "",
                        "exit_code": "",
                        "note": "claimed",
                    }
                )
            rows.append(row)
        write_status_unlocked(rows)
        return claim

    return with_lock(_claim)


def update_job(job: Dict[str, str], **updates: str) -> None:
    def _update():
        status = read_status_unlocked()
        rows = []
        for manifest_job in read_manifest():
            row = job_to_status_row(manifest_job, status.get(manifest_job["job_id"]))
            if manifest_job["job_id"] == job["job_id"]:
                row.update({key: str(value) for key, value in updates.items()})
            rows.append(row)
        write_status_unlocked(rows)

    with_lock(_update)


def pause_jobs(job_ids: List[str], note: str) -> None:
    requested = set(job_ids)

    def _pause():
        manifest_jobs = {job["job_id"]: job for job in read_manifest()}
        unknown = sorted(requested - set(manifest_jobs))
        if unknown:
            raise SystemExit("Unknown job_id(s): " + ", ".join(unknown))

        status = read_status_unlocked()
        rows = []
        for manifest_job in read_manifest():
            job_id = manifest_job["job_id"]
            row = job_to_status_row(manifest_job, status.get(job_id))
            if job_id in requested:
                marker(job_id, "paused").touch()
                for kind in ("failed", "timeout"):
                    stale = marker(job_id, kind)
                    if stale.exists():
                        stale.unlink()
                row.update(
                    {
                        "status": "paused",
                        "end_time": now_iso(),
                        "exit_code": "paused",
                        "note": note,
                    }
                )
            rows.append(row)
        write_status_unlocked(rows)

    with_lock(_pause)
    write_report()


def resume_jobs(job_ids: List[str], note: str) -> None:
    requested = set(job_ids)

    def _resume():
        manifest_jobs = {job["job_id"]: job for job in read_manifest()}
        unknown = sorted(requested - set(manifest_jobs))
        if unknown:
            raise SystemExit("Unknown job_id(s): " + ", ".join(unknown))

        status = read_status_unlocked()
        rows = []
        for manifest_job in read_manifest():
            job_id = manifest_job["job_id"]
            row = job_to_status_row(manifest_job, status.get(job_id))
            if job_id in requested:
                for kind in ("paused", "failed", "timeout"):
                    stale = marker(job_id, kind)
                    if stale.exists():
                        stale.unlink()
                row.update(
                    {
                        "status": "pending",
                        "gpu_id": "",
                        "start_time": "",
                        "end_time": "",
                        "exit_code": "",
                        "success_count": "",
                        "success_rate": "",
                        "wall_clock_s": "",
                        "note": note,
                    }
                )
            rows.append(row)
        write_status_unlocked(rows)

    with_lock(_resume)
    write_report()


def build_command(job: Dict[str, str], timeout_seconds: int) -> List[str]:
    method = job["method"]
    args = [
        "conda",
        "run",
        "-n",
        "vla-pilot",
        "python",
        "main.py",
        "policy.type=rdt",
        f"backend.libero.suite_name={job['suite']}",
        "main.episode_num=10",
        f"backend.libero.max_episode_steps={job['max_steps']}",
        "main.use_vlm_stage_recognition=true",
        "perception.gemini_grounding.enabled=true",
        "perception.vlm_agent.base_url=https://api.poe.com/v1",
        "perception.vlm_agent.model=GPT-4o",
        "perception.vlm_agent.temperature=0.0",
        "main.render=false",
        "main.visualize_trajectory=true",
        "main.debug_draw_trajectory=true",
        f"hydra.run.dir={job['output_dir']}",
    ]
    if method == "unguided":
        args.extend(["main.use_guidance=false"])
    elif method == "vls":
        args.extend(["main.use_guidance=true", "main.guidance_type=vls"])
    elif method == "eds":
        args.extend(
            [
                "main.use_guidance=true",
                "main.guidance_type=eds",
                f"main.eds_config.population_size={job['population_size']}",
                f"main.eds_config.cem_iters={job['cem_iters']}",
                f"main.eds_config.use_cem={job['use_cem']}",
            ]
        )
    else:
        raise ValueError(f"Unknown method: {method}")
    return ["/usr/bin/time", "-p", "timeout", str(timeout_seconds)] + args


def run_one(job: Dict[str, str], gpu_id: str, timeout_seconds: int) -> None:
    job_id = job["job_id"]
    output_dir = abs_from_root(job["output_dir"])
    log_file = abs_from_root(job["log_file"])
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    if (output_dir / "results.txt").exists():
        count, rate = parse_results(output_dir)
        update_job(
            job,
            status="done",
            end_time=now_iso(),
            exit_code="0",
            success_count=count,
            success_rate=rate,
            wall_clock_s=parse_wall_clock(log_file),
            note="skipped existing results.txt",
        )
        marker(job_id, "done").touch()
        return

    for kind in ("failed", "timeout"):
        path = marker(job_id, kind)
        if path.exists():
            path.unlink()

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("OPENAI_BASE_URL", "https://api.poe.com/v1")

    cmd = build_command(job, timeout_seconds)
    update_job(job, note="running")
    with log_file.open("a", buffering=1) as log:
        log.write(f"\n===== JOB {job_id} START {now_iso()} GPU={gpu_id} =====\n")
        log.write("Command: <redacted-env> " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(WORKTREE_ROOT),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log.write(f"===== JOB {job_id} END {now_iso()} exit={proc.returncode} =====\n")

    count, rate = parse_results(output_dir)
    wall = parse_wall_clock(log_file)
    if proc.returncode == 0 and (output_dir / "results.txt").exists():
        marker(job_id, "done").touch()
        status = "done"
        note = "completed"
    elif proc.returncode == 124:
        marker(job_id, "timeout").touch()
        status = "timeout"
        note = "timeout"
    else:
        marker(job_id, "failed").touch()
        status = "failed"
        note = "failed or missing results.txt"
    update_job(
        job,
        status=status,
        end_time=now_iso(),
        exit_code=str(proc.returncode),
        success_count=count,
        success_rate=rate,
        wall_clock_s=wall,
        note=note,
    )
    write_report()


def worker(gpu_id: str, timeout_seconds: int) -> None:
    while True:
        job = claim_next_job(gpu_id)
        if job is None:
            return
        run_one(job, gpu_id, timeout_seconds)


def run(gpus: str, max_parallel: int, timeout_seconds: int) -> None:
    missing = []
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.environ.get("GOOGLE_API_KEY"):
        missing.append("GOOGLE_API_KEY")
    if missing:
        raise SystemExit("BLOCKED: missing " + ", ".join(missing))
    init_status(reset_running=True)
    gpu_list = [gpu.strip() for gpu in gpus.split(",") if gpu.strip()]
    if not gpu_list:
        raise SystemExit("No GPUs specified")
    gpu_list = gpu_list[: max(1, int(max_parallel))]
    children: List[subprocess.Popen] = []
    for gpu in gpu_list:
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "worker",
            "--gpu",
            gpu,
            "--timeout-seconds",
            str(timeout_seconds),
        ]
        children.append(subprocess.Popen(cmd, cwd=str(WORKTREE_ROOT), env=os.environ.copy()))
        time.sleep(1)
    exit_code = 0
    for child in children:
        exit_code = max(exit_code, child.wait())
    write_report()
    raise SystemExit(exit_code)


def status_summary() -> None:
    if not STATUS.exists():
        init_status()
    rows = list(read_status_unlocked().values())
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    total = len(rows)
    print(f"status_file={STATUS}")
    print(f"report={REPORT}")
    print("summary=" + ", ".join(f"{key}:{counts[key]}" for key in sorted(counts)))
    print(f"total={total}")
    for row in sorted(rows, key=lambda r: (r["suite"], r["job_id"])):
        print(
            f"{row['job_id']}: {row['status']} gpu={row['gpu_id']} "
            f"sr={row['success_count']} rate={row['success_rate']} log={row['log_file']}"
        )


def table_rows_by_suite(rows: List[Dict[str, str]]) -> str:
    lines = [
        "| Suite | Job | Method | Params | Status | Success | SR | Wall-clock | Output |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in sorted(rows, key=lambda r: (r["suite"], r["method"], r["eds_label"])):
        params = "n/a"
        if row["method"] == "eds":
            params = f"pop={row['population_size']},cem_iters={row['cem_iters']},use_cem={row['use_cem']}"
        lines.append(
            f"| `{row['suite']}` | `{row['job_id']}` | `{row['method']}` | `{params}` | "
            f"`{row['status']}` | `{row['success_count']}` | `{row['success_rate']}` | "
            f"`{row['wall_clock_s']}` | `{row['output_dir']}` |"
        )
    return "\n".join(lines)


def gate_summary(rows: List[Dict[str, str]]) -> str:
    lines = [
        "| Suite | Best EDS SR | VLS SR | Minimum gate | Target vs VLS |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    suites = sorted({row["suite"] for row in rows})
    for suite in suites:
        suite_rows = [row for row in rows if row["suite"] == suite and row["status"] == "done"]
        vls = next((row for row in suite_rows if row["method"] == "vls"), None)
        eds_rows = [row for row in suite_rows if row["method"] == "eds"]
        best_eds = max((float(row["success_rate"] or "nan") for row in eds_rows), default=math.nan)
        vls_sr = float(vls["success_rate"]) if vls and vls["success_rate"] else math.nan
        minimum = "pending"
        target = "pending"
        if not math.isnan(best_eds):
            minimum = "pass" if best_eds > 0.0 else "fail"
        if not math.isnan(best_eds) and not math.isnan(vls_sr):
            target = "pass" if best_eds + 1e-6 >= vls_sr - 15.0 else "fail"
        lines.append(
            f"| `{suite}` | `{'' if math.isnan(best_eds) else best_eds}` | "
            f"`{'' if math.isnan(vls_sr) else vls_sr}` | `{minimum}` | `{target}` |"
        )
    return "\n".join(lines)


def write_report() -> None:
    ensure_dirs()
    if not STATUS.exists():
        rows = []
    else:
        rows = list(read_status_unlocked().values())
    completed = sum(1 for row in rows if row.get("status") == "done")
    terminal = sum(1 for row in rows if row.get("status") in TERMINAL_STATUSES)
    total = len(rows)
    text = f"""# RDT EDS OOD Evaluation

Date: {now_iso()}

Worktree: `{WORKTREE_ROOT}`

This document is generated by `docs/03_evidence/eds_steering/ood_eval/run_ood_eval.sh`.

## Current Status

- Terminal jobs: `{terminal}/{total}`
- Completed jobs: `{completed}/{total}`
- Status file: `{rel(STATUS)}`
- Manifest: `{rel(MANIFEST)}`
- Logs: `{rel(LOG_DIR)}`

## Experiment Setup

- Suites: `libero_spatial`, `libero_goal`, `libero_10`
- Methods: unguided RDT, RDT+VLS, RDT+EDS
- VLM stage recognition: `true`
- Gemini grounding: `true`
- Trajectory visualization: `true`
- Debug trajectory drawing: `true`
- Render: `false`
- Poe/OpenAI-compatible VLM endpoint: `https://api.poe.com/v1`
- Secrets: not written to files; runtime reads `OPENAI_API_KEY` and `GOOGLE_API_KEY`.

## Acceptance Gates

{gate_summary(rows)}

## Results

{table_rows_by_suite(rows)}

## EDS Deployment Evidence To Check

For completed EDS jobs, inspect the corresponding log for:

- `guidance_type=eds`
- `eds_loop=true`
- `eds_population_size=<population_size>`

The code route is:

- `core/rdt_policy_steer.py:1012`: guided path from `select_action()`
- `core/rdt_policy_steer.py:1154`: VLS branch
- `core/rdt_policy_steer.py:1166`: EDS branch
- `core/rdt_policy_steer.py:1540`: `_eds_guided_denoise_loop()`
- `core/rdt_policy_steer.py:1558`: population scoring
- `core/rdt_policy_steer.py:1586`: resampling
- `core/rdt_policy_steer.py:1593`: renoise
- `core/rdt_policy_steer.py:1595`: rollout denoise
- `core/rdt_policy_steer.py:1611`: best candidate selection

## Preliminary Analysis Template

The runner updates this document during evaluation. Final analysis should compare:

- EDS vs VLS per OOD suite.
- EDS vs unguided per OOD suite.
- Whether larger population or more `cem_iters` improves SR or only increases wall-clock.
- Whether CEM improves over MPPI-style resampling.
- Whether visualization/debug artifacts are useful enough to justify their overhead.

## Recommended Follow-up Questions

- Does EDS remain non-zero on all OOD suites?
- Does EDS close the gap to VLS or exceed it on `libero_spatial`, `libero_goal`, and `libero_10`?
- Does reward scoring distinguish candidates strongly enough, or do we need zero-reward/random-reward ablations?
- Should EDS use adaptive `population_size`/`cem_iters` based on suite difficulty or reward spread?
- Should `select_action()` latency be instrumented separately from end-to-end rollout time?
"""
    REPORT.write_text(text)


def verify() -> None:
    init_status()
    rows = list(read_status_unlocked().values())
    expected = len(read_manifest())
    terminal = [row for row in rows if row["status"] in TERMINAL_STATUSES]
    print(f"expected_jobs={expected}")
    print(f"terminal_jobs={len(terminal)}")
    print(f"report={REPORT}")
    if len(terminal) != expected:
        raise SystemExit(1)


def preflight() -> None:
    init_status()
    missing = []
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.environ.get("GOOGLE_API_KEY"):
        missing.append("GOOGLE_API_KEY")
    rows = list(read_status_unlocked().values())
    running = [row for row in rows if row["status"] == "running"]
    print(f"worktree={WORKTREE_ROOT}")
    print(f"manifest={MANIFEST}")
    print(f"status={STATUS}")
    print(f"report={REPORT}")
    print(f"jobs={len(rows)}")
    print(f"running_jobs={len(running)}")
    if missing:
        print("blocked_missing_env=" + ",".join(missing))
        raise SystemExit(1)
    print("preflight=ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("preflight")
    sub.add_parser("status")
    sub.add_parser("report")
    sub.add_parser("verify")
    pause_p = sub.add_parser("pause")
    pause_p.add_argument("jobs", nargs="+")
    pause_p.add_argument("--note", default="paused by operator")
    resume_p = sub.add_parser("resume")
    resume_p.add_argument("jobs", nargs="+")
    resume_p.add_argument("--note", default="resumed by operator")
    run_p = sub.add_parser("run")
    run_p.add_argument("--gpus", required=True)
    run_p.add_argument("--max-parallel", type=int, required=True)
    run_p.add_argument("--timeout-seconds", type=int, required=True)
    worker_p = sub.add_parser("worker")
    worker_p.add_argument("--gpu", required=True)
    worker_p.add_argument("--timeout-seconds", type=int, required=True)
    args = parser.parse_args()
    ensure_dirs()
    if args.cmd == "init":
        init_status(reset_running=True)
    elif args.cmd == "preflight":
        preflight()
    elif args.cmd == "status":
        status_summary()
    elif args.cmd == "report":
        init_status()
        write_report()
        print(REPORT)
    elif args.cmd == "verify":
        verify()
    elif args.cmd == "pause":
        pause_jobs(args.jobs, args.note)
    elif args.cmd == "resume":
        resume_jobs(args.jobs, args.note)
    elif args.cmd == "run":
        run(args.gpus, args.max_parallel, args.timeout_seconds)
    elif args.cmd == "worker":
        worker(args.gpu, args.timeout_seconds)


if __name__ == "__main__":
    main()
