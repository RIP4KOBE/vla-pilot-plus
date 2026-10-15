"""Read-only compact monitor: no environment/credentials/raw VLM text output."""
import datetime
import json
from pathlib import Path

VARIANT = Path(__file__).resolve().parents[1]
SESSION = VARIANT.parents[1]
COHORT = "N25_ACTUATOR_CLIPPED_RBF_DEV_20260930"


def rows(path):
    if not path.exists():
        return []
    result = []
    for line in path.read_bytes().splitlines():
        try:
            result.append(json.loads(line))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # Writer may have an incomplete final line; never mutate it.
    return result


status_path = VARIANT / "execution/supervisor-status-v1.json"
status = json.loads(status_path.read_text()) if status_path.exists() else {}
events = [row for row in rows(SESSION / "study_worktree/data/attempt-ledger.jsonl")
          if row.get("identity", {}).get("iteration") == COHORT]
result = {
    "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "status": status.get("status", "startup"),
    "accepted": len(status.get("completed_keys", [])),
    "wins": status.get("successes", {}),
    "denominators": status.get("accepted_cell_denominators", {}),
    "failure": status.get("failure"),
    "result_exists": (VARIANT / "result-v1.json").exists(),
}
if events:
    event = events[-1]
    output = Path(event["output_dir"])
    stage = rows(output / "eds_eval/stage_events.jsonl")
    metrics = rows(output / "eds_eval/eds_metrics.jsonl")
    proc_path = output / "process.json"
    proc = json.loads(proc_path.read_text()) if proc_path.exists() else {}
    result["latest"] = {
        "event": event["event"], "cell": event["episode_key"],
        "attempt": event["attempt_id"], "worker_pid": proc.get("pid"),
        "worker_exists": Path(f'/proc/{proc.get("pid")}').exists(),
        "stage_calls": sum(x.get("codex_logical_call_attempts", 0) for x in stage),
        "stage_complete": sum(x.get("codex_completed_turns", 0) for x in stage),
        "stage_failed": sum(x.get("codex_failed_calls", 0) for x in stage),
        "provider_pairs": sorted({(x.get("transport", {}).get("backend", "unknown"),
                                   x.get("transport", {}).get("auth_mode", "unknown")) for x in stage}),
        "last_stage_step": stage[-1].get("global_step") if stage else None,
        "recorded_chunks": len(metrics),
        "last_chunk_step": metrics[-1].get("global_step") if metrics else None,
    }
print(json.dumps(result, ensure_ascii=False))
