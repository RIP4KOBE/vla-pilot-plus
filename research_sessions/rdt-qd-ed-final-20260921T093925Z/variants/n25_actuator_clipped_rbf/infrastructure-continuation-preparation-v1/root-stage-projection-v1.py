"""Root public metadata projection for one immutable infrastructure-invalid attempt."""
from pathlib import Path
import hashlib
import json

D = Path(__file__).resolve().parent
V = D.parent
FAILED = "rdt-qd-ed-final-20260921T093925Z__n25_dev_t04_n23_20260930__8b236af507d8"


def ref(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


review_path = V / "root-terminal-review-v1.json"
assert ref(review_path)["sha256"] == "a0b225efd8e35c17b5c6e801c3188a63b178079b7d31274f8b189a5641c59052"
review = json.loads(review_path.read_text())
assert review["cohort_disposition"] == "INVALID_OR_INTERRUPTED"
assert review["result"] == ref(V / "result-v1.json")
result = json.loads((V / "result-v1.json").read_text())
finals = [a["terminal"] for a in result["attempts"] if a["attempt_id"] == FAILED]
assert len(finals) == 1
final = finals[0]
assert final["outcome_valid"] is False and final["reason"] == "TimeoutExpired"
path = Path(final["output_dir"]) / "eds_eval/stage_events.jsonl"
assert path.stat().st_size <= 16 * 1024 * 1024
raw = path.read_bytes()
source_ref = {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}
fields = {
    "global_step", "chunk_id", "episode_id", "query_ok", "query_status", "error",
    "codex_logical_call_attempts", "codex_completed_turns", "codex_failed_calls",
    "codex_usage_complete_calls", "codex_input_tokens", "codex_output_tokens",
    "codex_cached_input_tokens", "codex_reasoning_output_tokens", "codex_call_latency_s",
}
transport_fields = {
    "backend", "auth_mode", "model", "reasoning_effort", "timeout_seconds",
    "completed_turns", "observed_usage", "event_types", "item_types",
    "public_config_sha256", "lifecycle",
}
calls = []
for position, line in enumerate(raw.splitlines()):
    if not line.strip():
        continue
    event = json.loads(line)
    if event.get("codex_logical_call_attempts", 0) == 0:
        assert event.get("query_status") == "skipped"
        continue
    assert event["codex_logical_call_attempts"] == 1
    assert event["transport"]["backend"] == "codex_cli"
    assert event["transport"]["auth_mode"] == "chatgpt"
    call = {"event_position": position, **{k: event[k] for k in fields if k in event}}
    call["transport"] = {k: event["transport"][k] for k in transport_fields if k in event["transport"]}
    calls.append(call)
assert len(calls) == 43
assert [sum(c[k] for c in calls) for k in (
    "codex_logical_call_attempts", "codex_completed_turns", "codex_failed_calls",
    "codex_usage_complete_calls")] == [43, 37, 6, 37]
failed = [c for c in calls if c["codex_failed_calls"]]
assert [c["global_step"] for c in failed] == [96, 120, 128, 136, 168, 176]
assert all(c["error"] == "codex_timeout" and c["query_ok"] is False for c in failed)
projection = {
    "schema": "n25-public-stage-metadata-v1", "attempt_id": FAILED,
    "response_payloads_included": False, "source_stage_events": source_ref,
    "attestation": {"root_terminal_review": ref(review_path),
                    "source_stage_events": source_ref, "public_fields_only": True,
                    "all_logical_calls_included": True, "reader": ref(Path(__file__))},
    "calls": calls,
}
output = D / "root-public-stage-metadata-v1.json"
with output.open("x") as f:
    json.dump(projection, f, indent=2, sort_keys=True, allow_nan=False)
    f.write("\n")
print(json.dumps({"projection": ref(output), "calls": 43, "failed": 6,
                  "source_bytes_read_once": len(raw), "response_payloads_included": False}))
