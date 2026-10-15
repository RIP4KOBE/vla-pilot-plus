#!/usr/bin/env python3
"""Freeze a *pending*, unapproved task3 diagnostic from SHA-verified Dev evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import torch


HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
WORKTREE = SESSION / "study_worktree"
ARTIFACTS = SESSION / "artifacts"
REPORT = SESSION / "variants/n11_parent_survival/dev-comparison-v1.json"
SOURCE_PLAN = ARTIFACTS / "continuation_20260928/n11-parent-survival-dev-v1/plan.frozen.v2.json"
OUTPUT = HERE / "same-state-plan.pending.v3.json"
sys.path.insert(0, str(WORKTREE))
from core.rdt_libero_action_converter import rdt_action_to_libero_raw


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"immutable pending plan exists: {OUTPUT}")
    report = json.loads(REPORT.read_text())
    assert report["all_sixteen_valid"]
    source = json.loads(SOURCE_PLAN.read_text())
    assert source["source_commit"] == subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip()
    cell = report["tasks"]["3"]["N7"]
    attempt = cell["attempt_id"]
    identity = next(row for row in source["episodes"] if row["task_id"] == 3 and row["profile"] == "N7")
    assert identity["env_seed"] == identity["policy_seed"] == 851784825
    assert identity["init_index"] == 0
    assert identity["init_row_sha256"] == "faa3e635dd29229f763f8748098f92543b7f680fb4212e7036ec49ba55d57c93"
    folder = ARTIFACTS / "attempts" / attempt / "eds_eval/decision_evidence/episode_000"
    entries = [json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()]
    replay = {}
    selected = {}
    historic_step15 = None
    final_bundle = None
    final = None
    terminal = None
    candidate = None
    checked = {}
    for entry in entries:
        summaries = entry["events"]
        wanted = any(e["event"] == "executed_action" and e["global_step"] < 24 for e in summaries)
        wanted |= any(e["event"] == "pre_reset_outcome" and e["global_step"] == 15 for e in summaries)
        wanted |= any(e["event"] == "final_selection" and e["global_step"] == 16 for e in summaries)
        if not wanted:
            continue
        path = folder / entry["bundle"]
        digest = sha256(path)
        assert digest == entry["sha256"], path
        events = torch.load(path, map_location="cpu", weights_only=True)["events"]
        checked[str(path.relative_to(SESSION))] = digest
        for event in events:
            step = int(event["global_step"])
            if event["event"] == "executed_action" and step < 24:
                action = event["values"]["action_numpy"]
                assert action.shape == (7,) and torch.isfinite(action).all()
                (replay if step < 16 else selected)[step] = action
            if event["event"] == "pre_reset_outcome" and step == 15:
                obs = event["values"]["observation"]
                historic_step15 = {
                    "eef_xyz": [float(v) for v in obs["robot0_eef_pos"]],
                    "gripper_qpos": [float(v) for v in obs["robot0_gripper_qpos"]],
                }
            if event["event"] == "final_selection" and step == 16:
                final_bundle = {"path": str(path), "sha256": digest}
                final = event["values"]
                terminal = final["terminal_population"]
                candidate = next(e["values"] for e in events if e["event"] == "canonical_candidate_batch" and e["values"]["iter_idx"] == 9)
                committed = next(e["values"] for e in events if e["event"] == "decision_committed")
                assert torch.equal(committed["action_chunk"], rdt_action_to_libero_raw(candidate["candidates"][7:8, :8, :]))
    assert set(replay) == set(range(16)) and set(selected) == set(range(16, 24))
    assert historic_step15 is not None and final_bundle is not None
    assert final["selected_index"] == 7 and terminal["population_size"] == 16
    assert terminal["grasp_selection"]["eligible_indices"] == []
    alternate = rdt_action_to_libero_raw(candidate["candidates"][6:7, :8, :])[0]
    assert bool((alternate[:, 6] == 1).all()) and bool((torch.stack([selected[i] for i in range(16, 24)])[:, 6] == -1).all())
    assert 0.058 < float(terminal["grasp_selection"]["projected_distances_m"][6].min()) < 0.060
    assert candidate["canonical_fingerprints"][6] == "369d2a8482e9aff9a611cd725914871be624ac3299dd7bce487a142aa88a4391"
    source_config = ARTIFACTS / "attempts" / attempt / ".hydra/config.yaml"
    critical = [
        "core/env_adapters/libero_adapter.py", "core/rdt_libero_action_converter.py",
        "core/decision_evidence.py", "core/rdt_policy_steer.py",
    ]
    runtime = json.loads(Path(source["runtime_manifest_path"]).read_text())
    gpu = runtime["gpu_mapping"]
    assert gpu["physical_gpu"] == 3 and gpu["uuid"] == "GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315"
    task_input = runtime["tasks"]["3"]
    assert task_input["task_id"] == 3
    assert task_input["expected_target_object"] == "bbq_sauce_1_main"
    runtime_files = {item["path"]: item for item in runtime["files"]}
    task_input_files = [runtime_files[task_input[key]] for key in ("bddl_path", "init_path")]
    payload = {
        "schema": "n12-task3-same-state-plan-v1", "approved": False,
        "diagnostic_only": True, "official_task_success_rate": None,
        "attempt_id": None, "output_dir": None,
        "study_worktree": str(WORKTREE), "source_commit": source["source_commit"],
        "source_plan": str(SOURCE_PLAN), "source_plan_sha256": sha256(SOURCE_PLAN),
        "runtime_manifest": source["runtime_manifest_path"],
        "runtime_manifest_sha256": source["runtime_manifest_sha256"],
        "source_report": str(REPORT), "source_report_sha256": sha256(REPORT),
        "source_config": str(source_config), "source_config_sha256": sha256(source_config),
        "source_bundle": final_bundle["path"], "source_bundle_sha256": final_bundle["sha256"],
        "checked_native_bundles": checked,
        "critical_code": [{"path": str(WORKTREE / name), "sha256": sha256(WORKTREE / name)} for name in critical],
        "task_input_files": task_input_files,
        "expected_target_object": task_input["expected_target_object"],
        "expected_basket_object": task_input["expected_basket_object"],
        "protocol": str(HERE / "same-state-diagnostic-scope-v1.md"),
        "protocol_sha256": sha256(HERE / "same-state-diagnostic-scope-v1.md"),
        "child_sha256": sha256(HERE / "same_state_child.py"),
        "supervisor_sha256": sha256(HERE / "same_state_supervisor.py"),
        "task_id": 3, "env_seed": 851784825, "init_index": 0,
        "init_row_sha256": identity["init_row_sha256"],
        "physical_gpu": 3, "gpu_uuid": gpu["uuid"], "egl_device_index": gpu["egl_device_index"],
        "selected_index": 7, "selected_fingerprint": candidate["canonical_fingerprints"][7],
        "alternative_index": 6, "alternative_fingerprint": candidate["canonical_fingerprints"][6],
        "replay_actions": [[float(v) for v in replay[i]] for i in range(16)],
        "selected_actions": [[float(v) for v in selected[i]] for i in range(16, 24)],
        "alternative_actions": [[float(v) for v in row] for row in alternate],
        "historic_step15_observation": historic_step15,
        "max_diagnostic_transitions": 96, "max_settling_steps": 40,
        "resets_max": 4, "prefix_actions_max": 8,
        "timeout_seconds": 900, "cleanup_seconds": 40,
        "budget_bucket": "development", "validation_authorized": False,
        "formal_authorized": False, "automatic_retry": False,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"path": str(OUTPUT), "sha256": sha256(OUTPUT),
                      "selected_fingerprint": payload["selected_fingerprint"],
                      "alternative_fingerprint": payload["alternative_fingerprint"],
                      "native_bundles_checked": len(checked)}, indent=2))


if __name__ == "__main__":
    main()
