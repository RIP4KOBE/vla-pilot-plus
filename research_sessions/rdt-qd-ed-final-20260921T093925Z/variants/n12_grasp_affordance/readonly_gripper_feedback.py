#!/usr/bin/env python3
"""Read-only, SHA-verified executed gripper/EEF traces from exposed N11 Dev."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import torch


HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
ARTIFACTS = SESSION / "artifacts"
REPORT = SESSION / "variants/n11_parent_survival/dev-comparison-v1.json"
OUTPUT = HERE / "gripper-feedback-readonly-v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"immutable output exists: {OUTPUT}")
    report = json.loads(REPORT.read_text())
    assert report["all_sixteen_valid"]
    by_task = {}
    bundle_hashes = {}
    for task, arms in report["tasks"].items():
        for profile in ("N7", "N11"):
            cell = arms[profile]
            folder = ARTIFACTS / "attempts" / cell["attempt_id"] / "eds_eval/decision_evidence/episode_000"
            actions, observations = {}, {}
            for line in (folder / "events.jsonl").open():
                entry = json.loads(line)
                relevant = [e for e in entry["events"] if e["event"] in ("executed_action", "pre_reset_outcome") and e["global_step"] < 120]
                if not relevant:
                    continue
                path = folder / entry["bundle"]
                digest = sha256(path)
                assert digest == entry["sha256"]
                events = torch.load(path, map_location="cpu", weights_only=True)["events"]
                for event in events:
                    step = event["global_step"]
                    if step >= 120:
                        continue
                    if event["event"] == "executed_action":
                        action = event["values"]["action_numpy"]
                        assert action.shape == (7,) and torch.isfinite(action).all()
                        actions[step] = [float(v) for v in action]
                    elif event["event"] == "pre_reset_outcome":
                        value = event["values"]
                        obs = value["observation"]
                        qpos = obs["robot0_gripper_qpos"]
                        eef = obs["robot0_eef_pos"]
                        assert qpos.shape == (2,) and eef.shape == (3,)
                        observations[step] = {
                            "qpos": [float(v) for v in qpos],
                            "eef": [float(v) for v in eef],
                            "success": bool(value["success"]),
                        }
                bundle_hashes[str(path.relative_to(SESSION))] = digest
            assert set(actions) == set(observations), (task, profile)
            rows = []
            for step in sorted(actions):
                action = actions[step]
                obs = observations[step]
                qpos = obs["qpos"]
                rows.append({
                    "step": step,
                    "close_command": action[6] > 0,
                    "aperture_sum_abs": sum(abs(v) for v in qpos),
                    "jaw_asymmetry": abs(abs(qpos[0]) - abs(qpos[1])),
                    "eef_z": obs["eef"][2],
                    "success": obs["success"],
                })
            assert rows and rows[0]["step"] == 0
            closing = [r for r in rows if r["close_command"]]
            first_close = closing[0]["step"] if closing else None
            post_close_lift = []
            if first_close is not None:
                for row in rows:
                    if first_close <= row["step"] <= first_close + 32:
                        post_close_lift.append(row["eef_z"])
            key = f"task{task}/{profile}"
            by_task[key] = {
                "success": bool(cell["success"]),
                "sampled_steps": len(rows),
                "first_close_step": first_close,
                "close_command_steps": len(closing),
                "max_jaw_asymmetry_during_close": max((r["jaw_asymmetry"] for r in closing), default=None),
                "min_aperture_during_close": min((r["aperture_sum_abs"] for r in closing), default=None),
                "max_aperture_during_close": max((r["aperture_sum_abs"] for r in closing), default=None),
                "eef_lift_32_steps_after_first_close": max(post_close_lift) - min(post_close_lift) if post_close_lift else None,
                "sample_every_8_steps": [r for r in rows if r["step"] % 8 == 0],
            }
    result = {
        "schema": "gripper-feedback-readonly-v1",
        "scope": "N7/N11 eight already exposed matched Dev episodes, first 120 executed steps each; no alternate actions",
        "report_sha256": sha256(REPORT),
        "bundle_hashes": bundle_hashes,
        "by_task": by_task,
        "limits": [
            "Gripper joint position and EEF height do not certify object contact or a held object.",
            "An episode-level success label must not be used by a deployed feedback rule.",
            "The first 120 steps are descriptive and do not support task-specific thresholds without prospective testing.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"path": str(OUTPUT), "sha256": sha256(OUTPUT), "by_task": {
        k: {name: value for name, value in v.items() if name != "sample_every_8_steps"} for k, v in by_task.items()
    }}, indent=2))


if __name__ == "__main__":
    main()
