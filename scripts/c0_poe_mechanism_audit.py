#!/usr/bin/env python3
"""CPU-only analysis of frozen C0 logs and unmodified controller methods.

No API call, simulator rollout, weight loading, or production source edit.
"""
import ast
import collections
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import numpy as np
import torch

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY / "artifacts/c0_poe_online_20260929"
NEW = ROOT / "outputs/c0_poe_gemini3_flash_attempt1"
OLD = Path("/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-quality-diversity/outputs/formal/p2_stage_on_abs_rbf_control")
REPLAY = STUDY / "artifacts/c0_online_stage_diagnostic_20260928/outputs/capture_replay"
CACHE = STUDY / "artifacts/c0_codex_repro_20260925/cache/cached_functions"
OUT = ROOT / "mechanism_audit"


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_method(path, cls, name):
    tree = ast.parse(path.read_text())
    node = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == cls)
    method = next(f for f in node.body if isinstance(f, ast.FunctionDef) and f.name == name)
    namespace = {"Optional": Optional, "np": np,
                 "log": SimpleNamespace(info=lambda *a: None, debug=lambda *a: None)}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


def cpu_probes():
    update = extract_method(STUDY / "main.py", "Main", "_update_stage")
    gripper = extract_method(STUDY / "main.py", "Main", "_get_gripper_value")
    result = {}
    for enabled in (False, True):
        queries, events = [], []
        def identify(**kwargs):
            queries.append(kwargs["trigger_reason"])
            return 1, True
        recognizer = SimpleNamespace(identify_stage_and_guidance=identify,
                                    last_result={"ok": True}, config={})
        runner = SimpleNamespace(
            config={"vlm_query_limit": 50},
            policy=SimpleNamespace(get_normalized_reward=lambda: 0.1, reset_stage=lambda: None),
            adapter=SimpleNamespace(get_vlm_image=lambda: np.zeros((2, 2, 3)),
                                    get_task_description=lambda: "put target in basket"),
            gemini_stage_recognizer=recognizer, stage_descriptions="stage 1", guidance_fns={1: []},
            init_img_with_keypoints=None, keypoint_id_to_object={0: "target"},
            _append_stage_event=events.append)
        state = {"prev_norm_reward": 0.95, "prev_gripper_open": True,
                 "current_stage": 1, "use_guidance": enabled, "global_step": 160,
                 "vlm_query_count": 0}
        update(runner, state, -1.0, 0.8, 0.6)
        result[f"reward_drop_guidance_{enabled}"] = {"query_count": len(queries), "triggers": queries}
    assert result["reward_drop_guidance_False"]["query_count"] == 0
    assert result["reward_drop_guidance_True"]["query_count"] == 1
    actions = np.zeros((1, 8, 7)); actions[0, :, -1] = [-1] * 7 + [1]
    result["chunk_boundary_gripper"] = {"stage_code_index_after_horizon_reset": 0,
        "value_used_by_current_code": gripper(None, actions, 0),
        "last_executed_command": gripper(None, actions, 7)}
    assert result["chunk_boundary_gripper"]["value_used_by_current_code"] != result["chunk_boundary_gripper"]["last_executed_command"]
    namespace = {"torch": torch}
    for name in ("stage1_guidance", "stage2_guidance"):
        exec((CACHE / (name + ".txt")).read_text(), namespace)
    keypoints = torch.tensor([[0., 0., 0.], [1., 0., 0.]])
    poses = [torch.tensor([[[x, 0., 0.]] * 9]) for x in (0., .5, 1.)]
    result["reward_probe"] = {"candidate_eef_x": [0., .5, 1.], "target_x": 0., "basket_x": 1.,
        "stage1_rewards": [float(namespace["stage1_guidance"](keypoints, p)) for p in poses],
        "stage2_rewards": [float(namespace["stage2_guidance"](keypoints, p)) for p in poses]}
    assert result["reward_probe"]["stage2_rewards"] == [0., 0., 0.]
    result["all_probes_passed"] = True
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    new_events = rows(NEW / "eds_eval/stage_events.jsonl")
    old_events = rows(OLD / "eds_eval/stage_events.jsonl")
    new_compute = rows(NEW / "eds_eval/episode_compute.jsonl")
    old_compute = rows(REPLAY / "eds_eval/episode_compute.jsonl")
    metrics = rows(NEW / "eds_eval/eds_metrics.jsonl")
    task_rows = []
    for task in range(10):
        n = next(r for r in new_compute if r["task_id"] == task)
        o = next(r for r in old_compute if r["task_id"] == task)
        steps = [r["global_step"] for r in metrics if r["episode"] == task]
        relative = f"eds_eval/qualitative/episode_{task:03d}/chunk_000000/single_step_inner_loop/single_step_particles.csv"
        task_rows.append({"task_id": task, "new_guided_chunks": n["guided_chunks"],
            "new_unguided_chunks": n["unguided_chunks"], "old_guided_chunks": o["guided_chunks"],
            "old_unguided_chunks": o["unguided_chunks"], "new_guided_steps": steps,
            "last_guided_step": max(steps), "first_particle_csv_equal": sha(NEW / relative) == sha(OLD / relative),
            "guidance_api_attempts": n["guidance_api_request_attempts"]})
    mismatch = [{k: r.get(k) for k in ("task_id", "global_step", "trigger_reason", "gripper_value_used",
                  "first_gripper_value", "last_gripper_value")} for r in new_events
               if r["first_gripper_value"] != r["last_gripper_value"]]
    stage_intervals = collections.Counter()
    for task in range(10):
        ev = [e for e in new_events if e["task_id"] == task]
        for step in range(0, 720, 8):
            before = [e for e in ev if e["global_step"] <= step]
            stage, guide = (before[-1]["stage_after"], before[-1]["guidance_after"]) if before else (1, True)
            stage_intervals[f"stage{stage}/{'on' if guide else 'off'}"] += 1
    result = {"scope": "offline analysis only; no new GPU or API calls", "per_task": task_rows,
        "new_guided_chunks": sum(r["guided_chunks"] for r in new_compute),
        "new_unguided_chunks": sum(r["unguided_chunks"] for r in new_compute),
        "old_guided_chunks": sum(r["guided_chunks"] for r in old_compute),
        "old_unguided_chunks": sum(r["unguided_chunks"] for r in old_compute),
        "chunk_stage_guidance_distribution": dict(stage_intervals),
        "gripper_first_last_mismatch_events": mismatch,
        "used_gripper_equals_first_count": sum(r["gripper_value_used"] == r["first_gripper_value"] for r in new_events),
        "stage_event_count": len(new_events),
        "historical_fallbacks_by_task": dict(collections.Counter(r["task_id"] for r in old_events if not r["query_ok"])),
        "cpu_probes": cpu_probes(),
        "source_sha256": {name: sha(STUDY / name) for name in
            ("main.py", "core/rdt_policy_steer.py", "vlm_query/stage_template.txt", "scripts/c0_poe_mechanism_audit.py")}}
    assert result["new_guided_chunks"] == stage_intervals["stage1/on"] == len(metrics)
    (OUT / "mechanism-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("per_task", "gripper_first_last_mismatch_events", "source_sha256")}, indent=2))


if __name__ == "__main__":
    main()
