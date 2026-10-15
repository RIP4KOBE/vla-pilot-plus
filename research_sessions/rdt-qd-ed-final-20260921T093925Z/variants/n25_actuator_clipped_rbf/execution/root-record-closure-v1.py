"""Record the immutable engineering closure and descriptive CPU summary only."""
from pathlib import Path
import copy
import datetime
import hashlib
import json
import sys
import yaml

V = Path(__file__).resolve().parents[1]
R = V.parents[1]
W = R / "study_worktree"
RUN = "rdt-qd-ed-final-20260921T093925Z"
sys.path.insert(0, str(W))
sys.path.insert(0, "/home/hynx/.codex/skills/arbor-agent-tools/scripts")
from scripts import qd_ed_final_runner as runner
import arbor_state


def read(p):
    return json.loads(p.read_text())


def ref(p):
    return {"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def exclusive(p, value):
    with p.open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


now = datetime.datetime.now(datetime.timezone.utc).isoformat()
terminal_ref = ref(V / "root-terminal-review-v1.json")
assert terminal_ref["sha256"] == "a0b225efd8e35c17b5c6e801c3188a63b178079b7d31274f8b189a5641c59052"
review = read(V / "root-terminal-review-v1.json")
result = read(V / "result-v1.json")
assert review["result"] == ref(V / "result-v1.json")
assert result["decision"] == "INVALID_OR_INTERRUPTED" and result["audited_cells"] == 18
assert len(result["attempts"]) == 19 and result["unknown_token_calls"] == 6
for pid in (491392, 906907):
    assert not Path(f"/proc/{pid}").exists(), "Old process identity requires review"

ms = V / "measurement-summary-preparation-v1"
summary = read(ms / "result-v1.json")
assert ref(ms / "result-v1.json")["sha256"] == "1fcbace43b78c074c91f8e66f80dde2457ae44ef8c2ece0fb0dc4f51b700244c"
assert summary["schema"] == "n25-terminal-measurement-summary-v1"
assert [c["task_id"] for c in summary["cells"]] == [0, 1, 2, 3]
assert summary["input_manifest_sha256"] == ref(ms / "input-manifest-frozen-v1.json")["sha256"]
assert summary["guard"]["denied"] == [] and not summary["guard"]["torch_imported"]
assert summary["guard"]["network_calls"] == summary["guard"]["subprocess_calls"] == 0
assert all(x["read_count"] == 1 for x in summary["input_coverage"]["files"])
assert summary["input_coverage"]["file_count"] == 16 and summary["input_coverage"]["tensor_reads"] == 0
assert all(c["cost_consistency"]["status"] == "consistent" for c in summary["cells"])
all_calls = summary["aggregate"]["all_calls"]
assert all_calls["observed_call_rows"] == 703 and all_calls["zero_gradient"]["true"] == 0
assert all_calls["clipped_components"] + all_calls["boundary_components"] + all_calls["interior_components"] == 269952
assert sum(c["recorded_metrics"] for c in summary["cells"]) == 37
assert sum(c["bounded_witness"]["recorded_verified_calls"] for c in summary["cells"]) == 44
measurement_review = {
    "schema": "n25-measurement-root-review-v1", "recorded_at": now,
    "decision": "ACCEPT_DESCRIPTIVE_SUMMARY_OF_ALL_FOUR_ACCEPTED_N25_CELLS",
    "root_terminal_review": terminal_ref, "summary": ref(ms / "result-v1.json"),
    "manifest": ref(ms / "input-manifest-frozen-v1.json"), "release": ref(ms / "read-release-v1.json"),
    "cohort_disposition": "INVALID_OR_INTERRUPTED", "complete_dev_cohort": False,
    "accepted_tasks": [0, 1, 2, 3], "guided_decisions": 37, "rbf_calls": 703,
    "clipped_components": 77775, "components": 269952,
    "clipped_component_ratio": 77775 / 269952, "boundary_components": 924,
    "zero_gradient_calls": 0, "native_dtype": "torch.bfloat16",
    "existing_bounded_native_witness_calls": 44, "all_call_native_replay": False,
    "update_operand_norm_median": 20.0, "update_operand_is_actual_output_delta": False,
    "guard": summary["guard"],
    "interpretation": "Clipping is active and did not globally extinguish gradients in these four cells. This is not paired N23 gradient evidence or causal physical benefit; N25 remains 1/4, below an incomplete full Dev gate.",
    "changes_to_science_gates_or_next_variant": False, "target_achieved": False,
}
exclusive(ms / "root-review-v1.json", measurement_review)

pairs = set()
logical = completed = failed = usage = 0
for a in result["attempts"]:
    t = a["terminal"]
    transport = t["stage_transport"]
    pairs.add((transport["backend"], transport["auth_mode"], transport["model"], transport["reasoning_effort"]))
    assert t["guidance_api_request_attempts"] == t["grounding_api_request_attempts"] == 0
    logical += t["provider_logical_call_attempts"]
    completed += t["provider_completed_turns"]
    failed += t["provider_failed_calls"]
    usage += t["provider_usage_complete_calls"]
assert pairs == {("codex_cli", "chatgpt", "gpt-6-astra", "low")}
assert (logical, completed, failed, usage) == (362, 356, 6, 356)
provider_review = {
    "schema": "n25-root-terminal-provider-review-v1", "recorded_at": now,
    "result": ref(V / "result-v1.json"), "root_terminal_review": terminal_ref,
    "basis": "All19 immutable terminal transport/cost records; accepted18 additionally covered by root receipt review",
    "provider_pairs": [list(x) for x in sorted(pairs)], "logical_calls": logical,
    "completed_calls": completed, "failed_calls": failed, "usage_complete_calls": usage,
    "unknown_token_calls": 6, "http_request_internal_retry_billing_counts": "Unknown",
    "guidance_and_grounding_calls": 0, "poe_use_observed": False,
    "credential_files_read_or_modified": False, "alternate_provider_fallback_authorized": False,
    "policy": ref(W / "core/codex_stage_policy.py"),
    "transport": ref(W / "core/codex_stage.py"),
}
exclusive(V / "root-terminal-provider-review-v1.json", provider_review)
protocol = ref(V / "infrastructure-continuation-preparation-v1/root-implementation-protocol-v1.md")
with runner.locked(W / "data/qd-ed-state.lock"):
    state = runner.read_state(W / "research-state.yaml")
    assert state["current_iteration"]["candidate"] == "N25"
    closed = copy.deepcopy(state["current_iteration"])
    closed.update(status="CLOSED_ENGINEERING_INVALID", result=ref(V / "result-v1.json"),
                  root_terminal_review=terminal_ref, execution_authorized=False,
                  current_owned_workers=[], terminal_recorded_at=now)
    state["closed_n25_iteration"] = closed
    state["n25_terminal_result"] = ref(V / "result-v1.json")
    state["current_iteration"].update(
        status="INFRASTRUCTURE_CONTINUATION_CPU_PREPARATION",
        execution_authorized=False, current_owned_workers=[],
        original_cohort_disposition="INVALID_OR_INTERRUPTED",
        root_terminal_review=terminal_ref, continuation_protocol=protocol,
        next_gpu_execution_authorized=False)
    state["current_owned_workers"] = []
    state["next_action"] = "Review isolated bounded N25 infrastructure continuation; seal old prefix under5a, then integrate/freeze/release only after all gates. N26/validation inactive."
    state["updated_at"] = now
    arbor_state.atomic_write(W / "research-state.yaml", yaml.safe_dump(state, sort_keys=False, allow_unicode=True))

coordinator = W / ".arbor/sessions" / RUN / ".coordinator"
with arbor_state.state_lock(W, RUN):
    path = coordinator / "checkpoint.json"
    checkpoint = read(path)
    checkpoint["n25_closed_controller"] = checkpoint.get("active_controller")
    checkpoint.update(
        updated_at=now, phase="DISPATCH", status="N25_INFRASTRUCTURE_CONTINUATION_CPU_PREPARATION",
        active_controller=None, owned_gpu_workers=[], automatic_gpu_dispatch_authorized=False,
        n25_terminal_review=terminal_ref, n25_measurement_review=ref(ms / "root-review-v1.json"),
        n25_terminal_provider_review=ref(V / "root-terminal-provider-review-v1.json"),
        n25_infrastructure_protocol=protocol, in_flight_executor="/root/n22_cpu_executor",
        n26_status="INACTIVE_ORIGINAL_N25_ENGINEERING_INVALID_NOT_VALID_REJECTION",
        next_action=state["next_action"], target_met=False, target_achieved=False)
    arbor_state.atomic_write(path, json.dumps(checkpoint, indent=2) + "\n")
    tree_path = coordinator / "idea_tree.json"
    tree = read(tree_path)
    nodes = tree["nodes"].values() if isinstance(tree["nodes"], dict) else tree["nodes"]
    for node in nodes:
        if node["id"] == "11.1":
            node["status"] = "running"
            node["insight"] = "Original N25 Dev closed engineering INVALID after18 accepted cells plus exact task4/N23 transport/whole-worker timeout; native audit missing for that invalid cell. N25 accepted1/4 vsC0/Q0/N23 0 on matched first4; incomplete and not promoted/rejected scientifically.703RBF calls,77775/269952 components clipped,0zero-gradient,44existing bounded witnesses; causal efficacy unknown. Bounded named-once continuation CPU implementation under root protocol; old prefix/costs immutable; no GPU currently active, no new budget, validation/N26 remain inactive."
    arbor_state.atomic_write(tree_path, json.dumps(tree, indent=2) + "\n")
    ledger = W / "docs/03_evidence/qd_ed_final/iteration-ledger.md"
    with ledger.open("a") as f:
        f.write(f"\n### {now} — N25 engineering closure and bounded continuation preparation\n\n")
        f.write("Original cohort INVALID_OR_INTERRUPTED:18 accepted/19 dispatched, C0 0/5,Q0 0/5,N23 0/4,N25 1/4. Task4/N23 exceeded1800s after6Codex timeouts,43logical/37complete; native receipt/report absent. All19 charged8201.788167113322s;6token-usage calls unknown. Accepted18 had319/319 complete Codex calls; wholecohort362logical/356complete/6failed. NoPoe. Root terminal and descriptive measurement reviews recorded under N25. Algorithm not rejected or promoted. Named-once infrastructure continuation being implemented in isolation; no automatic old-cohort resume, no increased budget, all protected gates closed.\n")
print(json.dumps({"terminal_review": terminal_ref, "measurement_review": ref(ms / "root-review-v1.json"),
                  "provider_review": ref(V / "root-terminal-provider-review-v1.json"),
                  "status": "N25_INFRASTRUCTURE_CONTINUATION_CPU_PREPARATION"}))
