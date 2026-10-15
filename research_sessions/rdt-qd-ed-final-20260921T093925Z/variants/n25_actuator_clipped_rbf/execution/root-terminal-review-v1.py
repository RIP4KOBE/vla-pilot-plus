"""Root metadata review of a settled N25 cohort; no tensors, model, or GPU."""
from pathlib import Path
from collections import Counter, defaultdict
import datetime
import hashlib
import json
import math

V = Path(__file__).resolve().parents[1]
R = V.parents[1]
W = R / "study_worktree"
COHORT = "N25_ACTUATOR_CLIPPED_RBF_DEV_20260930"
ARMS = ("C0", "Q0", "N23", "N25")
COMMIT = "5a65ef15968cc68c82314e8c0773b3365ad45fa0"
UUID = "GPU-48473162-9548-1a19-04aa-ea86c5349187"
verified = set()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return {"path": str(Path(path).resolve()), "sha256": sha(path)}


def read(path):
    return json.loads(Path(path).read_text())


def read_ref(reference):
    assert sha(reference["path"]) == reference["sha256"], reference["path"]
    verified.add(reference["path"])
    return read(reference["path"])


def process_alive(pid, ticks):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19] == str(ticks) and fields[0] != "Z"
    except FileNotFoundError:
        return False


def main():
    result = read(V / "result-v1.json")  # Intentionally unavailable before terminal.
    controller = read(V / "controller-process-v1.json")
    assert not process_alive(controller["controller_pid"], controller["controller_start_ticks"])
    plan = read_ref(result["plan"])
    assert result["plan"] == controller["plan"]
    release = read_ref(controller["release"])
    assert release["plan"] == result["plan"]
    assert plan["source_commit"] == result["source_commit"] == COMMIT
    source_path = V / "source-manifest-controller-v1.json"
    assert sha(source_path) == "fafcb0d881c95d567cb14a6690145d4ad933abc84a5e0175dfbe1512efd836ee"
    source = read(source_path)
    assert source["commit"] == COMMIT and len(source["files"]) == 257
    for item in source["files"]:
        assert sha(W / item["path"]) == item["sha256"], item["path"]

    snapshot = read_ref(result["ledger_snapshot"])
    current = [json.loads(line) for line in (W / "data/attempt-ledger.jsonl").read_text().splitlines() if line.strip()]
    current = [row for row in current if row.get("identity", {}).get("iteration") == COHORT]
    assert current == snapshot
    groups = defaultdict(list)
    for row in current:
        groups[row["attempt_id"]].append(row)
    finals = {}
    for aid, rows in groups.items():
        assert rows[0]["event"] == "reserved" and rows[-1]["event"] in ("valid", "aborted")
        assert sum(row["event"] == "dispatched" for row in rows) <= 1
        finals[aid] = rows[-1]
    assert result["dispatched"] == sum(row["event"] == "dispatched" for row in current)
    assert {a["attempt_id"]: a["terminal"] for a in result["attempts"]} == finals

    accepted = result["accepted_cells"]
    assert [c["episode_key"] for c in accepted] == [p["episode_key"] for p in plan["episodes"][:len(accepted)]]
    assert result["audited_cells"] == len(accepted)
    wins, denominators = Counter(), Counter()
    native = {arm: Counter() for arm in ARMS}
    auxiliary = {arm: defaultdict(float) for arm in ARMS}
    providers = set()
    calls = complete = failed = 0
    for cell in accepted:
        final = finals[cell["attempt_id"]]
        assert final["event"] == "valid" and final["outcome_valid"] is True
        assert final["success"] is cell["success"] and type(cell["success"]) is bool
        assert final["episode_key"] == cell["episode_key"] and final["source_commit"] == COMMIT
        arm = cell["profile"]
        assert final["identity"]["profile"] == arm and final["identity"]["task_id"] == cell["task_id"]
        audit = read_ref(cell["audit"])
        context = read_ref(cell["worker_context"])
        receipt = read_ref(cell["worker_receipt"])
        attempt_result = read_ref(cell["attempt_result"])
        assert attempt_result["attempt_id"] == final["attempt_id"]
        assert audit["accepted"] is True and audit["evidence_complete"] is True and not audit["errors"]
        assert receipt["accepted"] is True and receipt["main_exit_code"] == 0 and receipt["process_unchanged"] is True
        assert receipt["attempt_id"] == final["attempt_id"] and receipt["episode_key"] == cell["episode_key"]
        assert receipt["profile"] == arm and receipt["audit_report"] == cell["audit"]
        assert receipt["context"] == cell["worker_context"] and receipt["plan"] == result["plan"]
        assert receipt["source"]["commit"] == COMMIT and receipt["source"]["sha256"] == source["sha256"]
        assert receipt["worker_cuda"]["physical_gpu"] == 7 and receipt["worker_cuda"]["physical_uuid"] == UUID
        if arm in ("N23", "N25"):
            assert receipt["audit_backend"]["kind"] == "cuda"
            assert receipt["audit_backend"]["physical_uuid"] == UUID
        else:
            assert receipt["audit_backend"]["kind"] == "cpu"
            assert receipt["audit_backend"]["physical_uuid"] is None
            assert receipt["audit_backend"]["dtype_coverage"] == []
        assert not process_alive(receipt["process"]["pid"], receipt["process"]["proc_start_ticks"])
        counts = receipt["n25_native_counts"]
        gate = audit.get("n25_actuator_clipped_rbf_audit")
        if arm == "N25":
            assert gate["schema"] == "n25-native-rbf-audit-v1" and gate["accepted"] is True
            assert gate["guided_decisions"] == counts["guided_decisions"]
            for key in ("all_call_summaries_verified", "witness_calls_verified", "zero_gradient_calls", "clipped_components"):
                assert type(gate[key]) is int and gate[key] >= 0 and gate[key] == counts[key]
            assert gate["all_call_summaries_verified"] == final["rbf_gradient_calls"]
            assert 0 <= gate["zero_gradient_calls"] <= gate["all_call_summaries_verified"]
            assert gate["clipped_components"] <= 384 * gate["all_call_summaries_verified"]
            assert gate["witness_calls_verified"] <= 11
            assert gate["witness_numeric_bytes"] <= 225280
            assert len(gate["witness_checks"]) == gate["witness_calls_verified"]
            assert all(check["accepted"] is True for check in gate["witness_checks"])
        else:
            assert not gate
        native[arm].update(counts)
        for k, v in receipt["n25_auxiliary"].items():
            auxiliary[arm][k] += v
        t = final["stage_transport"]
        providers.add((t["backend"], t["auth_mode"], t["model"], t["reasoning_effort"]))
        assert final["guidance_api_request_attempts"] == final["grounding_api_request_attempts"] == 0
        calls += final["stage_codex_logical_call_attempts"]
        complete += final["stage_codex_completed_turns"]
        failed += final["stage_codex_failed_calls"]
        wins[arm] += int(cell["success"])
        denominators[arm] += 1
    assert providers == ({("codex_cli", "chatgpt", "gpt-6-astra", "low")} if accepted else set())
    for arm in ARMS:
        assert result["counts"][arm] == {"audited": denominators[arm], "success": wins[arm]}
        assert result["native"][arm] == dict(native[arm])
        assert result["auxiliary"][arm] == dict(auxiliary[arm])
        if arm in ("N23", "N25"):
            g = native[arm]["guided_decisions"]
            assert native[arm]["parent_rounds_verified"] == 10 * g
            assert native[arm]["score_batches_verified"] == 11 * g
            assert native[arm]["candidate_scores_verified"] == 176 * g

    status = read_ref(result["terminal_status"])
    assert status == result["terminal_status"]["content"]
    consistent = result["controller_evidence"]["consistent"] is True
    assert status["completed_keys"] == [c["episode_key"] for c in accepted]
    promoted = (len(accepted) == 40 and wins["N25"] >= 5 and wins["N25"] >= max(wins[a] for a in ARMS[:-1])
                and native["N25"]["guided_decisions"] > 0 and native["N25"]["parent_rounds_verified"] > 0)
    futility = len(accepted) % 4 == 0 and wins["N25"] + 10 - len(accepted) // 4 < 5
    expected = ("ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION" if promoted else "REJECT" if len(accepted) == 40
                else "REJECT_NUMERIC_FUTILITY" if futility and result["failure"] is None else "INVALID_OR_INTERRUPTED")
    if not consistent:
        assert result.get("journal_reconstructed_disposition") == expected
        expected = "INVALID_OR_INTERRUPTED"
        promoted = False
    assert result["decision"] == expected and result["dev_gate_promoted"] is promoted
    assert result["validation_authorized"] is False and result["formal_authorized"] is False
    seconds = sum(v["gpu_process_wall_seconds"] for v in finals.values())
    assert math.isfinite(seconds) and seconds >= 0
    # Same nonnegative duration terms, summed once chronologically and once by arm.
    assert math.isclose(sum(result["all_attempt_costs"][a]["gpu_process_wall_seconds"]["observed_total"] for a in ARMS),
                        seconds, rel_tol=1e-12, abs_tol=1e-9)
    summary = {
        "schema": "n25-root-terminal-review-v1", "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "decision": "ACCEPT_TERMINAL_RECONSTRUCTION", "cohort_disposition": expected,
        "result": ref(V / "result-v1.json"), "ledger": result["ledger_snapshot"], "plan": result["plan"],
        "source": ref(source_path), "source_files_verified": len(source["files"]),
        "metadata_references_verified": len(verified), "accepted_cells": len(accepted), "counts": result["counts"],
        "native": result["native"], "auxiliary": result["auxiliary"], "mechanism_interpretation": "Clipping and zero-gradient counts are descriptive; update operand is not actual output delta; bounded witnesses do not cover all calls",
        "all_attempts": len(finals), "all_attempt_gpu_process_seconds": seconds,
        "accepted_cell_provider_calls": {"logical": calls, "completed": complete, "failed": failed},
        "accepted_cell_provider_pairs": [list(x) for x in sorted(providers)],
        "provider_http_requests_internal_retries_billing": "Unknown",
        "limitations": ["Metadata/receipt review only; no native tensors reopened or GPU audit repeated.",
                        "Partial cohort denominators retained; unrun tasks are not failures.",
                        "Gradient/clipping and witness counts establish measured execution, not causal physical benefit."],
        "target_achieved": False, "next_gpu_execution_authorized": False,
        "reader": ref(__file__),
    }
    path = V / "root-terminal-review-v1.json"
    with path.open("x") as out:
        json.dump(summary, out, indent=2)
        out.write("\n")
    print(json.dumps({"review": ref(path), "disposition": expected, "counts": result["counts"],
                      "calls": summary["accepted_cell_provider_calls"], "gpu_seconds": seconds}))


if __name__ == "__main__":
    main()
