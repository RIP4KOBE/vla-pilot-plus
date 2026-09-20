"""Every experimental expansion must learn from its own demonstrations."""

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mode_gate.promotion import PolicyPromotionCoordinator, deploy_policy_gate
from mode_gate.config import ModeGateConfig
from mode_gate.slow_loop import MANDATORY_DEMOS_PROTOCOL, SlowLoopJob, SlowLoopState
from mode_gate.slow_worker import SlowLoopWorker
from mode_gate.state_machine import EpisodeChunkController
from mode_gate.types import ControllerRoute, ProgressEvidence


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def current_task(tmp_path):
    task = {"suite": "libero_10", "task_id": "drawer", "perturbation_variant": "use_environment"}
    ticket = tmp_path / "tickets/current/ticket.json"
    dataset = ticket.parent / "exports/lerobot_v3"
    write_json(ticket, {**task, "ticket_id": "current", "parent_policy_id": "parent"})
    write_json(dataset / "meta/info.json", {"total_episodes": 3})
    write_json(ticket.parent / "curation.json", {
        "ticket_id": "current", "needs_more_demos": False, "export_root": str(dataset),
    })
    training = write_json(tmp_path / "work/job/coft/training_result.json", {
        "job_id": "job", "ticket_id": "current", "parent_policy_id": "parent",
        "current_ticket_dataset_path": str(dataset),
    })
    candidates = write_json(tmp_path / "work/job/candidates.json", [{
        "policy_id": "candidate", "candidate_kind": "EXPANSION", "target_delta_id": "new-delta",
    }])
    job = SlowLoopJob("job", SlowLoopState.ALPHA_SELECTING, "parent", "current", "h", None, 8, {
        **task, "gate_kind": "EXPANSION", "ticket_path": str(ticket),
        "curation_needs_more_demos": False, "current_ticket_dataset_path": str(dataset),
        "training_result_path": str(training), "delta_id": "new-delta",
        "candidates_json_path": str(candidates), "parent_candidate_path": str(tmp_path / "parent.json"),
    })
    worker = SlowLoopWorker.__new__(SlowLoopWorker)
    worker.work_root = tmp_path / "work"
    worker.protocol_manifest_path = tmp_path / "manifest.json"
    worker.protocol_manifest = {"manifest_sha256": "manifest", "tasks": [task]}
    return worker, job


def test_lookup_never_reads_features_or_remedy_library(tmp_path):
    worker = SlowLoopWorker.__new__(SlowLoopWorker)
    worker.work_root = tmp_path
    job = SlowLoopJob("job", SlowLoopState.LOOKUP_PENDING, "parent", None, "h", None, 1, {"lookup_enabled":False})
    result = worker._lookup(job)
    assert result.next_state is SlowLoopState.TICKET_READY
    assert result.metadata["lookup_disabled"]
    assert result.metadata["current_task_demonstrations_required"]
    assert result.metadata["slow_loop_protocol"] == MANDATORY_DEMOS_PROTOCOL
    assert json.loads(result.artifacts[0].read_text())["matches"] == []




def test_real_current_task_evidence_enters_gate_without_reuse(current_task):
    worker, job = current_task
    evidence = worker._require_current_task_training(job)
    result = worker._prepare_policy_gate(job)
    spec = json.loads(Path(result.metadata["policy_gate_job_path"]).read_text())
    assert result.metadata["current_task_training_evidence"] == evidence
    assert spec["current_task_training_evidence"] == evidence
    assert spec["slow_loop_protocol"] == MANDATORY_DEMOS_PROTOCOL
    assert "--reuse" not in spec["command"]
    assert job.metadata["ticket_path"] in spec["command"]


@pytest.mark.parametrize("fault", ["no_ticket", "other_task", "other_parent", "empty_demos",
    "uncurated", "missing_training", "wrong_training_job", "wrong_training_ticket",
    "wrong_training_parent", "old_delta", "reuse_candidate", "outside_ticket"])
def test_missing_or_unrelated_demonstrations_cannot_enter_policy_gate(current_task, tmp_path, fault):
    worker, job = current_task
    meta = dict(job.metadata)
    ticket = Path(meta["ticket_path"])
    if fault == "no_ticket":
        job = replace(job, ticket_id=None)
    elif fault in {"other_task", "other_parent"}:
        value = json.loads(ticket.read_text())
        value["task_id" if fault == "other_task" else "parent_policy_id"] = "unrelated"
        write_json(ticket, value)
    elif fault == "empty_demos":
        write_json(Path(meta["current_ticket_dataset_path"]) / "meta/info.json", {"total_episodes": 0})
    elif fault == "uncurated":
        meta["curation_needs_more_demos"] = True
    elif fault == "missing_training":
        meta.pop("training_result_path")
    elif fault.startswith("wrong_training_"):
        path = Path(meta["training_result_path"])
        value = json.loads(path.read_text())
        value[{"wrong_training_job": "job_id", "wrong_training_ticket": "ticket_id",
               "wrong_training_parent": "parent_policy_id"}[fault]] = "unrelated"
        write_json(path, value)
    elif fault in {"old_delta", "reuse_candidate"}:
        path = Path(meta["candidates_json_path"])
        value = json.loads(path.read_text())
        value[0]["target_delta_id" if fault == "old_delta" else "candidate_kind"] = (
            "old-delta" if fault == "old_delta" else "REUSE")
        write_json(path, value)
    elif fault == "outside_ticket":
        meta["current_ticket_dataset_path"] = str(tmp_path / "another-ticket")
        write_json(Path(meta["current_ticket_dataset_path"]) / "meta/info.json", {"total_episodes": 9})
    with pytest.raises(ValueError):
        worker._prepare_policy_gate(replace(job, metadata=meta))


def test_evidence_is_checked_again_before_deployment(current_task):
    worker, job = current_task
    evidence = worker._require_current_task_training(job)
    meta = {**job.metadata, "current_task_training_evidence": evidence}
    info = Path(meta["current_ticket_dataset_path"]) / "meta/info.json"
    write_json(info, {"total_episodes": 4})
    with pytest.raises(ValueError, match="evidence changed"):
        worker._deploy(replace(job, state=SlowLoopState.READY_FIXED_BUDGET, metadata=meta))


def test_precollected_source_can_have_old_parent_but_sft_must_use_current_parent(current_task, tmp_path):
    worker, job = current_task
    task = worker.protocol_manifest['tasks'][0]
    source = tmp_path/'precollected/source/ticket.json'
    dataset = source.parent/'exports/lerobot_v3'
    write_json(source, {**task, 'ticket_id':'source', 'parent_policy_id':'discarded-old-parent'})
    write_json(dataset/'meta/info.json', {'total_episodes':15})
    write_json(source.parent/'curation.json', {'ticket_id':'source','needs_more_demos':False,
                                              'export_root':str(dataset)})
    write_json(Path(job.metadata['training_result_path']), {
        'job_id':job.job_id, 'ticket_id':job.ticket_id, 'parent_policy_id':job.active_policy_id,
        'current_ticket_dataset_path':str(dataset)})
    meta = {**job.metadata, 'current_ticket_dataset_path':str(dataset),
            'demonstration_source_ticket_path':str(source), 'precollected_demonstrations':True}
    evidence = worker._require_current_task_training(replace(job, metadata=meta))
    assert evidence['parent_policy_id']=='parent'
    source_value=json.loads(source.read_text()); source_value['task_id']='unrelated'
    write_json(source,source_value)
    with pytest.raises(ValueError,match='another task'):
        worker._require_current_task_training(replace(job,metadata=meta))


def test_planner_selects_existing_dataset_and_records_video_evidence(current_task, tmp_path, monkeypatch):
    from mode_gate.incidents import IncidentMemory
    from mode_gate.io_utils import sha256_file
    worker, job = current_task
    worker.incidents=IncidentMemory(tmp_path/'incidents')
    task={**worker.protocol_manifest['tasks'][0], 'task_key':'environment-drawer'}
    demo=tmp_path/'success.hdf5'; demo.write_bytes(b'native-success-fixture')
    video=tmp_path/'success.mp4'; video.write_bytes(b'video-fixture')
    dataset=Path(job.metadata['current_ticket_dataset_path'])
    bank=[{'task_key':task['task_key'],'ticket_id':'old-source','ticket_path':job.metadata['ticket_path'],
           'dataset_root':str(dataset),'repo_id':'completed/task','video_paths':[str(video)],
           'accepted':{str(demo):{'bytes':demo.stat().st_size,'sha256':sha256_file(demo)}}}]
    monkeypatch.setattr('mode_gate.campaign.demonstration_bank',lambda _:bank)
    monkeypatch.setattr('mode_gate.experience_planner.ExperiencePlanner.select_demonstrations',
        lambda self,current,candidates:{'ticket_id':'old-source','reason':'same task; native success'})
    meta, artifacts=worker._select_precollected_demonstrations(job,task,Path(job.metadata['ticket_path']))
    assert meta['current_ticket_dataset_path']==str(dataset) and meta['teleop_auto_started'] is False
    fact=list(worker.incidents.experiences.facts.iter_valid())[-1]
    assert fact['payload']['new_collection_required'] is False
    assert fact['payload']['demonstrations'][0]['sha256']==sha256_file(demo)
    assert fact['payload']['viewing_videos'][0]['kind']=='executed_video'


def test_rejected_merge_never_recollects_precollected_demonstrations(current_task, tmp_path, monkeypatch):
    worker, job = current_task
    report = write_json(tmp_path/'rejected.json', {'schema_version':'raw-policy-gate-report-v1',
        'manifest_hash':'manifest', 'parent':{'policy_id':'parent'}, 'gate_kind':'EXPANSION',
        'decision':{'status':'POLICY_REJECTED','reason':'no passing merge'}})
    monkeypatch.setattr(worker,'_require_current_task_training',lambda job: {})
    meta={**job.metadata,'precollected_demonstrations':True,'current_task_training_evidence':{},
          'policy_gate_report_path':str(report)}
    result=worker._consume_policy_gate(replace(job,state=SlowLoopState.TRIGGER_RECHECK,metadata=meta),trigger_phase=True)
    assert result.next_state is SlowLoopState.POLICY_REJECTED
    assert result.metadata['new_collection_required'] is False


def test_reuse_needs_measured_current_policy_evidence():
    worker = SlowLoopWorker.__new__(SlowLoopWorker)
    job = SlowLoopJob("old",SlowLoopState.RAW_REGRESSION,"parent",None,"h",None,4,{"gate_kind":"REUSE"})
    with pytest.raises(ValueError,match="Planner evidence"):
        worker._require_current_task_training(job)


def test_verifier_resteer_does_not_enter_expansion():
    controller = EpisodeChunkController(ModeGateConfig(controller_mode="learned_verifier"))
    controller.start_episode(stage_id="1")
    controller.state.verification_due = True
    controller.begin_sampling()
    controller.mark_abstracted()
    controller.mark_scored(has_safe_candidate=True)
    decision = controller.route_scored_batch(verifier_decision=ControllerRoute.RESTEER)
    assert decision.route is ControllerRoute.RESTEER
    assert decision.reason == "verifier_head_argmax:RE-STEER"


def test_native_success_takes_precedence_over_expansion_at_horizon():
    controller = EpisodeChunkController(ModeGateConfig(controller_mode="learned_verifier"))
    controller.start_episode(stage_id="1")
    controller.begin_sampling()
    controller.mark_abstracted()
    controller.mark_scored(has_safe_candidate=True)
    controller.route_scored_batch()
    decision = controller.observe_chunk(ProgressEvidence(
        stage_id="done", advanced=False, confidence=1.0, source="LIBERO-PRO predicate",
        task_success=True,
    ), terminal_timeout=True)
    assert decision.route is not ControllerRoute.EXPAND
    assert decision.reason == "task_success"
    assert not controller.state.verification_due
