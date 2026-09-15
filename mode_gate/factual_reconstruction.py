"""Import historical audit outcomes as facts, never automatically as verifier labels."""
from pathlib import Path
import hashlib
import json
from .incidents import IncidentMemory
from .io_utils import AtomicJsonl, atomic_write_json, sha256_file
from .experiences import artifact_ref
from .experiment_contract import FIXED_BUDGET_50_LABEL_VERSION


def reconstruct_factual_labels(*, incidents, episodes, replay_plan, output,
                               label_version=FIXED_BUDGET_50_LABEL_VERSION,
                               apply=False, excluded_record_ids=()):
    """Historical CLI name retained; only native outcomes/factual provenance are imported.

    No old remaining_budget is rewritten. Planner must create a revisioned fixed50
    interpretation and decision-time v3 inputs before selecting training examples.
    """
    memory = IncidentMemory(Path(incidents))
    plan_path, episodes_path = Path(replay_plan), Path(episodes)
    plan = json.loads(plan_path.read_text())
    contexts = {str(x.get("record_id")): x for x in plan.get("contexts", [])}
    excluded = set(excluded_record_ids)
    facts = []
    for episode in AtomicJsonl(episodes_path).iter_valid():
        if episode.get("status") not in {"COMPLETED", "completed", "success", "failed"} and episode.get("event") != "EPISODE_COMPLETED":
            continue
        root = Path(str(episode.get("output_dir", "")))
        if not root.is_dir():
            continue
        for summary_path in sorted(root.rglob("runtime_decision.json")):
            summary = json.loads(summary_path.read_text())
            record_id = str(summary.get("record_id") or "")
            if not record_id or record_id in excluded or record_id not in contexts:
                continue
            # Stage recognition/advancement is not task success. Preserve the
            # collector's native result and all controller observations separately.
            native = episode.get("task_success", episode.get("success"))
            payload = {"runtime_summary": artifact_ref(summary_path, kind="recorded_decision"),
                       "episode": dict(episode), "original_context": contexts[record_id],
                       "native_success": native if isinstance(native, bool) else None,
                       "label_status": "PLANNER_INTERPRETATION_REQUIRED",
                       "historical_budget_preserved": True,
                       "import_plan": artifact_ref(plan_path, kind="historical_replay_plan")}
            identity = hashlib.sha256(
                (record_id + sha256_file(summary_path) + json.dumps(payload, sort_keys=True)).encode()).hexdigest()
            fact = {"episode_id":str(episode.get("episode_key", episode.get("context_id", root))),
                    "context_id":record_id, "kind":"historical_episode_outcome",
                    "payload":payload, "event_id":"historical:" + identity}
            facts.append(fact)
    if apply:
        existing = {x["event_id"] for x in memory.experiences.facts.iter_valid()}
        for fact in facts:
            if fact["event_id"] not in existing:
                memory.record_fact(**fact)
                existing.add(fact["event_id"])
    report = {"schema_version":"historical-outcome-import-v3", "applied":bool(apply),
              "facts":facts, "fact_count":len(facts), "labels_attached":0,
              "label_version":label_version, "automatic_binary_labels":False,
              "decision_inputs_modified":False, "historical_remaining_budget_modified":False}
    atomic_write_json(Path(output), report)
    return report
