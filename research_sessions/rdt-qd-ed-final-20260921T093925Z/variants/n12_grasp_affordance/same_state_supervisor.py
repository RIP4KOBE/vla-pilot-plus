#!/usr/bin/env python3
"""Account for one separately approved GPU3 diagnostic; fail closed on drift."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time


HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
WORKTREE = SESSION / "study_worktree"
spec = importlib.util.spec_from_file_location("qd_ed_final_runner", WORKTREE / "scripts/qd_ed_final_runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def preflight(plan):
    if plan["schema"] != "n12-task3-same-state-plan-v1" or plan["approved"] is not True:
        raise RuntimeError("explicit user approval missing")
    if plan["physical_gpu"] != 3 or plan["gpu_uuid"] != "GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315":
        raise RuntimeError("GPU3 identity changed")
    if plan["egl_device_index"] != 0 or plan["max_diagnostic_transitions"] != 96:
        raise RuntimeError("diagnostic scope changed")
    if plan["max_settling_steps"] != 40 or plan["resets_max"] != 4:
        raise RuntimeError("reset/settling scope changed")
    if plan["timeout_seconds"] != 900 or plan["cleanup_seconds"] != 40:
        raise RuntimeError("time limit changed")
    if plan["validation_authorized"] or plan["formal_authorized"] or plan["automatic_retry"]:
        raise RuntimeError("protected phase or retry unexpectedly enabled")
    if plan["boot_id"] != Path("/proc/sys/kernel/random/boot_id").read_text().strip():
        raise RuntimeError("server rebooted since diagnostic release")
    for path_key, hash_key in (
        ("source_plan", "source_plan_sha256"), ("source_report", "source_report_sha256"),
        ("source_config", "source_config_sha256"), ("source_bundle", "source_bundle_sha256"),
        ("runtime_manifest", "runtime_manifest_sha256"), ("protocol", "protocol_sha256"),
    ):
        if runner.digest(plan[path_key]) != plan[hash_key]:
            raise RuntimeError(f"{path_key} hash changed")
    if runner.digest(HERE / "same_state_child.py") != plan["child_sha256"]:
        raise RuntimeError("child changed after freeze")
    if runner.digest(__file__) != plan["supervisor_sha256"]:
        raise RuntimeError("supervisor changed after freeze")
    runner.verify_files(plan["critical_code"])
    runner.verify_files(plan["task_input_files"])
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip() != plan["source_commit"]:
        raise RuntimeError("study code identity changed")
    source = runner.read_json(plan["source_plan"])
    row = next(x for x in source["episodes"] if x["profile"] == "N7" and x["task_id"] == 3)
    if row["env_seed"] != plan["env_seed"] or row["init_row_sha256"] != plan["init_row_sha256"]:
        raise RuntimeError("frozen Dev task3 identity changed")
    runtime = runner.read_json(plan["runtime_manifest"])
    mapping = runtime["gpu_mapping"]
    if mapping["physical_gpu"] != 3 or mapping["uuid"] != plan["gpu_uuid"] or mapping["egl_device_index"] != 0:
        raise RuntimeError("GPU/EGL runtime mapping changed")
    state = runner.read_state(WORKTREE / "research-state.yaml")
    if state["external_resource_hold"]["active"] is not False:
        raise RuntimeError("study under external resource hold")
    episode = {
        "split": "dev", "iteration": "N12_TASK3_SAME_STATE_DIAGNOSTIC_20260928",
        "profile": "N7_DIAGNOSTIC_ONLY", "task_id": 3, "env_seed": plan["env_seed"],
        "policy_seed": plan["env_seed"], "init_index": 0,
        "budget_bucket": "development", "timeout_seconds": 900,
    }
    events = runner.read_events(WORKTREE / "data/attempt-ledger.jsonl")
    runner.check_retry(events, episode)
    admitted_timeout = runner.check_budget(
        state, events, episode,
        runner.read_events(WORKTREE / "data/gpu-healthcheck-ledger.jsonl"),
        runner.read_events(WORKTREE / "data/gpu-hour-reservation-ledger.jsonl"),
        physical_gpu=3,
    )
    if admitted_timeout != 900:
        raise RuntimeError("runner changed diagnostic timeout")
    admission = runner.gpu_admission(physical_gpu=3, expected_uuid=plan["gpu_uuid"])
    environment = runner.child_environment(runtime)
    if environment.get("CUDA_VISIBLE_DEVICES") != "3" or environment.get("MUJOCO_EGL_DEVICE_ID") != "0":
        raise RuntimeError("child GPU/EGL environment changed")
    return episode, runtime, environment, admission


def main():
    release_path = HERE / "same-state-plan.approved.v1.json"
    plan = runner.read_json(release_path)
    with runner.locked(WORKTREE / "data/qd-ed-runner.lock", nonblocking=True):
        episode, runtime, environment, admission = preflight(plan)
        output = Path(plan["output_dir"])
        if output.exists() or (HERE / "same-state-attempt-result.json").exists():
            raise RuntimeError("diagnostic already launched")
        base = {
            "attempt_id": plan["attempt_id"], "identity": runner.episode_identity(episode),
            "episode_key": "n12_same_state_t03_20260928", "budget_bucket": "development",
            "diagnostic_only": True, "official_task_success_rate": None,
            "plan_sha256": runner.digest(release_path), "protocol_sha256": plan["protocol_sha256"],
            "source_config_sha256": plan["source_config_sha256"],
            "runtime_manifest_sha256": plan["runtime_manifest_sha256"],
            "init_row_sha256": plan["init_row_sha256"],
            "source_commit": plan["source_commit"], "output_dir": str(output),
            "physical_gpu": 3, "gpu_uuid": plan["gpu_uuid"],
            "stage_backend": "recorded_no_new_stage", "stage_model": "none",
            "stage_condition": "N7_E2_RECORDED_PREFIX_DIAGNOSTIC",
        }
        runner.append_event(WORKTREE, {**base, "event": "reserved", "time_unix": time.time(), "admission": admission})
        process = None
        dispatched = False
        started = time.monotonic()
        outcome = {"outcome_valid": False, "diagnostic_valid": False, "retryable_infrastructure": False}
        final_event = "aborted"
        try:
            runner.gpu_admission(physical_gpu=3, expected_uuid=plan["gpu_uuid"])
            if runner.runtime_gpu(runtime, runner.read_state(WORKTREE / "research-state.yaml")) != 3:
                raise RuntimeError("runtime GPU mapping changed")
            runner.append_event(WORKTREE, {**base, "event": "dispatched", "time_unix": time.time(),
                                           "timeout_seconds": 900})
            dispatched = True
            started = time.monotonic()
            command = [str(runner.PYTHON), str(HERE / "same_state_child.py"), str(release_path)]
            with (HERE / "same-state-child.log").open("x") as log:
                process = subprocess.Popen(command, cwd=WORKTREE, env=environment, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                runner.durable_json(HERE / "same-state-process.json", {
                    "pid": process.pid, "attempt_id": plan["attempt_id"],
                    "boot_id": plan["boot_id"], "time_unix": time.time(), "command": command,
                })
                exit_code = runner.wait_exclusively(process, 900, physical_gpu=3)
            if exit_code != 0:
                raise RuntimeError(f"diagnostic child exit {exit_code}")
            result = runner.read_json(output / "result.json")
            if result["schema"] != "n12-task3-same-state-result-v1" or result["attempt_id"] != plan["attempt_id"]:
                raise RuntimeError("diagnostic result identity changed")
            if result["official_task_success_rate"] is not None or result["diagnostic_only"] is not True:
                raise RuntimeError("diagnostic misclassified as official SR")
            if result["status"] not in ("INFEASIBLE_STATE_RESTORE", "COMPLETED_CONTRAST"):
                raise RuntimeError("unexpected diagnostic status")
            counts = result["resource_counts"]
            if counts["transitions"] > 96 or counts["resets"] > 4 or counts["settling_steps"] > 40:
                raise RuntimeError("diagnostic transition/reset bound exceeded")
            outcome.update(diagnostic_status=result["status"], diagnostic_valid=True,
                           resource_counts=counts, result_sha256=runner.digest(output / "result.json"))
            final_event = "valid"
        except BaseException as error:
            outcome.update(failure_class=type(error).__name__, reason=str(error)[:700])
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
        finally:
            runner.terminate_owned(process)
            elapsed = time.monotonic() - started if dispatched else 0.0
            terminal = {**base, **outcome, "event": final_event, "time_unix": time.time(),
                        "gpu_process_wall_seconds": elapsed,
                        "gpu_time_measurement": "exclusive GPU3 process wall-time upper bound including startup/cleanup"}
            runner.append_event(WORKTREE, terminal)
            runner.durable_json(HERE / "same-state-attempt-result.json", terminal)
            print(json.dumps({"event": final_event, "status": outcome.get("diagnostic_status"),
                              "gpu_process_wall_seconds": elapsed,
                              "failure_class": outcome.get("failure_class")}), flush=True)
        if final_event != "valid":
            raise RuntimeError("diagnostic stopped; no automatic retry")


if __name__ == "__main__":
    main()
