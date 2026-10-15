"""Correct only N17's post-success auto-reset time semantics, with no GPU run."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SESSION = HERE.parents[1]
ORIGINAL_STATUS = HERE / "supervisor-status.json"
CORRECTED_STATUS = HERE / "supervisor-status-corrected-v2.json"
TASK9_ID = "rdt-qd-ed-final-20260921T093925Z__n17_physics_t09_n7_20260929__bd78f45e8c35"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if CORRECTED_STATUS.exists():
        raise FileExistsError(CORRECTED_STATUS)
    original = json.loads(ORIGINAL_STATUS.read_text())
    if original["status"] != "failed" or original["reason"] != "GateError" or len(original["completed"]) != 1:
        raise ValueError("N17 original supervisor verdict changed")
    output = SESSION / "artifacts/attempts" / TASK9_ID
    result = json.loads((output / "attempt-result.json").read_text())
    native = json.loads((output / "eds_eval/decision-evidence-audit.json").read_text())
    if result["event"] != "valid" or result["outcome_valid"] is not True or result["success"] is not True:
        raise ValueError("task9 native episode was not valid successful")
    if native["accepted"] is not True or native["evidence_complete"] is not True:
        raise ValueError("task9 native evidence not accepted")
    trace = output / "eds_eval/passive_physics_episode_000.jsonl"
    rows = [json.loads(line) for line in trace.open()]
    if len(rows) < 2 or len(rows) > 720 or any(row["global_step"] != i for i, row in enumerate(rows)):
        raise ValueError("passive trace step sequence incomplete")
    violations = [i for i in range(1, len(rows)) if rows[i]["sim_time"] <= rows[i - 1]["sim_time"]]
    if violations != [len(rows) - 1] or rows[-1]["success"] is not True or any(row["success"] for row in rows[:-1]):
        raise ValueError("time reset is not exactly the success-terminal auto-reset")
    if rows[-1]["sim_time"] >= rows[-2]["sim_time"] or not all(row["target_tracker_valid"] for row in rows[:-1]):
        raise ValueError("preterminal physics not continuously tracked")
    body_names = {row["target_object_name"] for row in rows[:-1]}
    if len(body_names) != 1 or None in body_names:
        raise ValueError("target identity unstable before reset")
    audit = {
        "schema": "n17-passive-physics-terminal-reset-audit-v2",
        "attempt_id": TASK9_ID,
        "trace_sha256": sha(trace),
        "total_action_rows": len(rows),
        "preterminal_physics_rows": len(rows) - 1,
        "post_reset_row": len(rows) - 1,
        "preterminal_last_sim_time": rows[-2]["sim_time"],
        "post_reset_sim_time": rows[-1]["sim_time"],
        "terminal_success": True,
        "native_audit_sha256": sha(output / "eds_eval/decision-evidence-audit.json"),
        "attempt_result_sha256": sha(output / "attempt-result.json"),
        "adapter_source": "core/env_adapters/libero_adapter.py:807-842 resets on terminated after pre_reset_outcome",
        "interpretation": "All real action rows are preserved; the final row's physics snapshot is post-reset and excluded from object/contact analysis. The native terminal success remains valid.",
    }
    audit_path = output / "eds_eval/passive-physics-audit-corrected-v2.json"
    with audit_path.open("x") as stream:
        json.dump(audit, stream, indent=2, sort_keys=True)
        stream.write("\n")
    corrected = {"status": "completed_two_audited_with_terminal_reset_correction",
                 "original_supervisor_status_sha256": sha(ORIGINAL_STATUS),
                 "correction_audit_path": str(audit_path),
                 "correction_audit_sha256": sha(audit_path),
                 "completed": [*original["completed"], {
                     "attempt_id": TASK9_ID, "task_id": 9, "success": True,
                     "physics": {"sha256": sha(trace), "steps": len(rows),
                                 "preterminal_physics_rows": len(rows) - 1}}],
                 "new_gpu_dispatches": 0}
    with CORRECTED_STATUS.open("x") as stream:
        json.dump(corrected, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"corrected_status": str(CORRECTED_STATUS),
                      "sha256": sha(CORRECTED_STATUS), "task9_physics": audit}, sort_keys=True))


if __name__ == "__main__":
    main()
