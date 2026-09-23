import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from core.decision_evidence import DecisionEvidence


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_decision_evidence.py"
spec = importlib.util.spec_from_file_location("decision_evidence_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def episode(tmp_path, *, auxiliary=False, terminal_return=True, n2=False):
    rec = DecisionEvidence(tmp_path, episode=0)
    provider = lambda keypoints, trajectories: None
    rec.begin_decision(global_step=0, stage=1, use_guidance=True,
                       keypoints=torch.zeros(1, 3), providers=[provider])
    samples = torch.zeros(2, 64, 128, dtype=torch.bfloat16)
    samples[1, :8, 39] = .125
    full = torch.zeros(2, 9, 3, dtype=torch.bfloat16)
    full[:, :, :3] = torch.tensor([.125, .25, .5], dtype=torch.bfloat16)
    full[1, 1:, 0] += torch.arange(1, 9, dtype=torch.bfloat16) * .125
    quality = torch.tensor([0., 1.], dtype=torch.bfloat16)
    scopes = [("canonical_initial", -1), ("canonical_offspring", 0)]
    if auxiliary:
        scopes.insert(1, ("auxiliary_pretest", 0))
    for role, iteration in scopes:
        rec.set_scoring_scope(role=role, iter_idx=iteration, site="fixture_existing_return")
        rec.begin_score_call()
        for row in full:
            rec.record("projection_origin", source_eef_position=np.array([.125, .25, .5]),
                       cast_eef_start=row[0])
        rec.begin_scoring(samples=samples, keypoints=torch.zeros(1, 3), projected_xyz=full,
                          provider_input_xyz=full[:, 1:8], slice_kind="eds")
        for index in range(2):
            rec.scoring_candidate_index = index
            rec.scoring_provider_index = 0
            rec.provider_return(provider, quality[index].double())
        rec.record("scoring_aggregate", scoring_batch_id=rec.scoring_batch_id,
                   aggregate_before_reward_mode=quality)
        active = n2 and role != "auxiliary_pretest"
        internal = quality + 1 if active else quality
        dual = {"quality_mode": "executed_prefix_v1", "raw_provider_quality": quality} if active else {}
        rec.record("effective_quality", scoring_batch_id=rec.scoring_batch_id,
                   reward_mode="normal", quality=internal, costs=-internal, **dual)
        if role != "auxiliary_pretest":
            rec.record("canonical_candidate_batch", iter_idx=iteration,
                       candidates=samples, effective_quality=internal, **dual)
    rec.record("parent_allocation", iter_idx=0, source_population=samples,
               source_quality=quality, source_costs=-quality,
               parent_indices=torch.tensor([0, 1]), elite_count=0,
               parent_cell_ids=None, offspring_sources=["softmax", "softmax"])
    selected = samples[1:2]
    rec.record("final_selection", population=samples, selected_latent=selected,
               selected_index=1, selected_quality=2. if n2 else 1., selected_cost=-2. if n2 else -1.,
               **({"quality_mode": "executed_prefix_v1", "raw_provider_quality": quality,
                   "selected_raw_provider_quality": 1.} if n2 else {}),
               selected_fingerprint=None, selected_cell=None, selection_rule="cost_argmin")
    chunk = torch.zeros(1, 8, 7, dtype=torch.bfloat16)
    chunk[:, :, -1] = 1
    rec.record("policy_action_decode", selected_latent=selected, action_chunk=chunk)
    rec.commit_decision(action_chunk=chunk, execution_horizon=8)
    rec.dispatch(global_step=0, execution_index=1)
    rec.record("executed_action", action_numpy=chunk[0, 0].float().numpy())
    rec.pre_reset_outcome({"robot0_eef_pos": np.array([.13, .25, .5])},
                          reward=1., terminated=True, success=True)
    if terminal_return:
        rec.step_returned(terminated=True, truncated=False, success=True)
        rec.finish()
    compute = tmp_path / "episode_compute.jsonl"
    compute.write_text(json.dumps({"episode_id": 0, "outcome": "completed" if terminal_return else "execution_error",
                                  "decision_evidence": rec.status()}) + "\n")
    return rec, compute


def rewrite(root, edit):
    refs = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    changed = False
    for ref in refs:
        path = root / ref["bundle"]
        payload = torch.load(path, weights_only=True)
        for row in payload["events"]:
            if not changed and edit(row):
                changed = True
        torch.save(payload, path)
        ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        ref["first_sequence"] = payload["events"][0]["sequence"]
        ref["last_sequence"] = payload["events"][-1]["sequence"]
        ref["events"] = [{k: row[k] for k in ("sequence", "event", "decision_id", "global_step", "reset_sequence")}
                         for row in payload["events"]]
    assert changed
    (root / "events.jsonl").write_text("".join(json.dumps(ref) + "\n" for ref in refs))


def test_valid_native_projection_roles_and_one_action_terminal_prefix(tmp_path, monkeypatch, capsys):
    rec, compute = episode(tmp_path, auxiliary=True)
    report = audit.audit_episode(rec.root, compute)
    assert report["accepted"] and report["original_execution_outcome"] == "completed"
    assert report["observed_scoring_roles"] == {"canonical_initial": 1, "canonical_offspring": 1, "auxiliary_pretest": 1}
    assert report["observed_counts"]["pre_reset_outcome"] == 1  # No invented t2..t8 feedback.
    assert all(row["projection_dtype"] == "torch.bfloat16" and row["points_including_t0"] == 9
               for row in report["projection_dtypes"])
    monkeypatch.setattr("sys.argv", [str(SCRIPT), str(rec.root), "--episode-compute", str(compute)])
    assert audit.main() == 0
    assert json.loads(capsys.readouterr().out)["accepted"]


def test_sha_failure_rejects_before_loading_tensor_payload(tmp_path, monkeypatch):
    rec, compute = episode(tmp_path)
    path = rec.root / "bundle_000001.pt"
    path.write_bytes(path.read_bytes() + b"corruption")
    monkeypatch.setattr(torch, "load", lambda *a, **k: pytest.fail("must check SHA first"))
    report = audit.audit_episode(rec.root, compute)
    assert not report["accepted"] and report["errors"] == ["bundle_sha_mismatch"]
    assert report["original_execution_outcome"] == "completed"
    assert report["observed_counts"] is None


@pytest.mark.parametrize("corruption", ["sequence", "role_link", "t8_missing", "selected", "dispatch_index", "eef_missing", "reset_claim", "stage_change", "reset_sequence", "wrapper_identity_only", "provider_link"])
def test_semantic_corruption_fails_even_with_updated_valid_bundle_sha(tmp_path, corruption):
    rec, compute = episode(tmp_path)
    targets = {"sequence": "decision_context", "role_link": "provider_return",
               "t8_missing": "scoring_inputs", "selected": "final_selection",
               "dispatch_index": "action_dispatch", "eef_missing": "pre_reset_outcome",
               "reset_claim": "automatic_reset_boundary", "stage_change": "decision_context",
               "reset_sequence": "step_returned", "wrapper_identity_only": "decision_context",
               "provider_link": "provider_return"}
    def edit(row):
        if row["event"] != targets[corruption]:
            return False
        value = row["values"]
        if corruption == "sequence": row["sequence"] += 1
        elif corruption == "role_link": value["scoring_scope"]["role"] = "auxiliary_pretest"
        elif corruption == "t8_missing": value["projected_xyz"] = value["projected_xyz"][:, :-1]
        elif corruption == "selected": value["selected_canonical_fingerprint"] = "0" * 64
        elif corruption == "dispatch_index": value["execution_index"] = 8
        elif corruption == "eef_missing": value["observation"] = {}
        elif corruption == "reset_claim": value["reset_completed"] = True
        elif corruption == "stage_change": value["stage_changed"] = True
        elif corruption == "reset_sequence": row["reset_sequence"] = 0
        elif corruption == "wrapper_identity_only":
            value["providers"][0]["original_code_sha256"] = None
            value["providers"][0]["source_text_sha256"] = None
        elif corruption == "provider_link": value["context_provider_ordinal"] = 1
        return True
    rewrite(rec.root, edit)
    report = audit.audit_episode(rec.root, compute)
    assert not report["accepted"] and report["errors"]
    assert report["original_execution_outcome"] == "completed"


def test_pending_reset_has_persisted_terminal_but_no_invented_next_state(tmp_path):
    rec, compute = episode(tmp_path, terminal_return=False)
    report = audit.audit_episode(rec.root, compute)
    assert not report["accepted"] and report["evidence_complete"] is False
    assert report["original_execution_outcome"] == "execution_error"
    assert report["observed_counts"]["pre_reset_outcome"] == 1
    assert "step_returned" not in report["observed_counts"]


def test_missing_status_keeps_original_outcome_and_unknown_evidence_completeness(tmp_path):
    rec, compute = episode(tmp_path)
    (rec.root / "status.json").unlink()
    report = audit.audit_episode(rec.root, compute)
    assert not report["accepted"] and report["evidence_complete"] is None
    assert report["original_execution_outcome"] == "completed"
    assert report["observed_counts"] is None


def test_n2_audit_preserves_raw_aggregate_and_selected_association(tmp_path):
    rec, compute = episode(tmp_path, auxiliary=True, n2=True)
    assert audit.audit_episode(rec.root, compute)["accepted"]
    def corrupt(row):
        if row["event"] != "final_selection": return False
        row["values"]["selected_raw_provider_quality"] = 2.0
        return True
    rewrite(rec.root, corrupt)
    result = audit.audit_episode(rec.root, compute)
    assert not result["accepted"] and result["errors"] == ["n2_selected_raw_index_mismatch"]


def test_n2_audit_rejects_raw_relabelled_as_internal_quality(tmp_path):
    rec, compute = episode(tmp_path, n2=True)
    def corrupt(row):
        if row["event"] != "effective_quality": return False
        row["values"]["raw_provider_quality"] = row["values"]["quality"]
        return True
    rewrite(rec.root, corrupt)
    result = audit.audit_episode(rec.root, compute)
    assert not result["accepted"] and result["errors"] == ["n2_raw_aggregate_mismatch"]


@pytest.mark.parametrize("corruption,expected", [
    ("raw_dtype", "n2_raw_aggregate_mismatch"),
    ("one_candidate_mode", "n2_canonical_mode_missing"),
    ("one_effective_mode", "n2_effective_mode_missing"),
    ("final_mode", "n2_final_mode_missing"),
    ("final_only_n2", "n2_canonical_mode_missing"),
])
def test_n2_audit_fails_closed_on_mixed_modes_or_raw_dtype(tmp_path, corruption, expected):
    rec, compute = episode(tmp_path, n2=corruption != "final_only_n2")
    target = {"raw_dtype": "effective_quality", "one_candidate_mode": "canonical_candidate_batch",
              "one_effective_mode": "effective_quality", "final_mode": "final_selection",
              "final_only_n2": "final_selection"}[corruption]
    def corrupt(row):
        if row["event"] != target: return False
        if corruption == "raw_dtype": row["values"]["raw_provider_quality"] = row["values"]["raw_provider_quality"].float()
        elif corruption == "final_only_n2": row["values"]["quality_mode"] = "executed_prefix_v1"
        else: row["values"].pop("quality_mode")
        return True
    rewrite(rec.root, corrupt)
    result = audit.audit_episode(rec.root, compute)
    assert not result["accepted"] and result["errors"] == [expected]
