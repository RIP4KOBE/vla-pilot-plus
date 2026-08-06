import json
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import p2_direction_normalized_rbf_audit as audit


def test_select_episode_attempts_rejects_wrong_seed_and_prefers_valid_formal():
    rows = [
        {"episode": 9, "task_id": 9, "episode_seed": 683, "source": "resume", "video_readable": True},
        {"episode": 9, "task_id": 9, "episode_seed": 548, "source": "formal", "video_readable": True},
        {"episode": 8, "task_id": 8, "episode_seed": 151, "source": "formal", "video_readable": False},
    ]

    selected, rejected = audit.select_episode_attempts(
        rows,
        expected_seeds=audit.EPISODE_SEEDS,
    )

    assert selected[9]["source"] == "formal"
    assert 8 not in selected
    assert {row["rejection_reason"] for row in rejected} == {
        "episode_seed_mismatch:683!=548",
        "video_missing_or_unreadable",
    }


def test_select_episode_attempts_prefers_complete_evidence_over_source_priority():
    rows = [
        {
            "episode": 0,
            "task_id": 0,
            "episode_seed": audit.EPISODE_SEEDS[0],
            "source": "formal",
            "video_readable": True,
            "evidence_complete": False,
        },
        {
            "episode": 0,
            "task_id": 0,
            "episode_seed": audit.EPISODE_SEEDS[0],
            "source": "supplemental:recovery_complete",
            "video_readable": True,
            "evidence_complete": True,
        },
    ]

    selected, rejected = audit.select_episode_attempts(
        rows,
        expected_seeds=audit.EPISODE_SEEDS,
    )

    assert selected[0]["source"] == "supplemental:recovery_complete"
    assert rejected[0]["source"] == "formal"
    assert rejected[0]["rejection_reason"] == "duplicate_complete_episode"


def test_selected_execution_fingerprint_comes_from_selected_recovery_source(tmp_path):
    formal = tmp_path / "formal"
    recovery = tmp_path / "supplemental_recovery/recovery_ok/formal/label"
    formal.mkdir()
    recovery.mkdir(parents=True)
    (formal / "job_manifest.json").write_text(
        json.dumps(
            {
                "config_fingerprint": "stale-formal",
                "execution_record": {
                    "code_state_sha256": "stale-code",
                    "git_revision": "revision",
                },
            }
        )
    )
    (recovery / "job_manifest.json").write_text(
        json.dumps(
            {
                "config_fingerprint": "selected-recovery",
                "execution_record": {
                    "code_state_sha256": "selected-code",
                    "git_revision": "revision",
                },
            }
        )
    )

    fingerprint = audit._stored_fingerprint(
        "label",
        selected_sources={recovery},
        formal_root=formal,
    )

    assert fingerprint["config_fingerprint"] == "selected-recovery"
    assert fingerprint["code_state_sha256"] == "selected-code"
    assert fingerprint["selected_execution_contexts"] == [
        {
            "output_dir": str(recovery),
            "config_fingerprint": "selected-recovery",
            "code_state_sha256": "selected-code",
            "git_revision": "revision",
        }
    ]


def test_runtime_gpu_roles_parse_split_compute_and_egl_devices():
    text = (
        "===== START job 2026-08-05T11:17:50+00:00 GPU=2 =====\n"
        "Runtime: CUDA_VISIBLE_DEVICES=2 MUJOCO_EGL_DEVICE_ID=0 "
        "P2_RENDER_GPU_INDEX=3 JOBLIB_MULTIPROCESSING=0\n"
    )

    assert audit._runtime_gpu_roles_from_log(text) == {
        "compute_gpu_index": 2,
        "render_gpu_index": 3,
        "mujoco_egl_device_id": 0,
    }


def test_attempt_rows_marks_metrics_stage_and_qualitative_complete(monkeypatch, tmp_path):
    label = "p2_stage_on_dirnorm_rbf_global_w2_e050"
    directory = tmp_path / "formal" / label
    episode_dir = directory / "episode_1"
    qualitative = directory / "eds_eval/qualitative/episode_000"
    episode_dir.mkdir(parents=True)
    qualitative.mkdir(parents=True)
    (episode_dir / "episode_1_fail_agentview.mp4").write_bytes(b"video")
    (qualitative / "frame.png").write_bytes(b"png")
    (directory / "eds_eval/episode_metadata.jsonl").write_text(
        json.dumps({"episode_id": 0, "task_id": 0, "episode_seed": audit.EPISODE_SEEDS[0]}) + "\n"
    )
    (directory / "eds_eval/eds_metrics.jsonl").write_text(
        json.dumps({"episode": 0, "task_id": 0}) + "\n"
    )
    (directory / "eds_eval/stage_events.jsonl").write_text(
        json.dumps({"episode_id": 0, "query_ok": True}) + "\n"
    )
    monkeypatch.setattr(audit, "OUTPUT_TARGET", tmp_path)
    monkeypatch.setattr(audit, "_ffprobe_readable", lambda _path: True)

    rows, failures = audit._attempt_rows(label)

    assert failures == []
    assert len(rows) == 1
    assert rows[0]["metrics_present"] is True
    assert rows[0]["stage_query_success"] is True
    assert rows[0]["qualitative_present"] is True
    assert rows[0]["evidence_complete"] is True


def test_supplemental_attempt_directories_are_discovered_in_batch_order(tmp_path):
    label = "p2_stage_on_dirnorm_rbf_global_w1_e050"
    expected = []
    for batch in ("recovery_b", "recovery_a"):
        directory = tmp_path / "supplemental_recovery" / batch / "formal" / label
        directory.mkdir(parents=True)
        expected.append(directory)

    assert audit._supplemental_attempt_directories(label, root=tmp_path) == sorted(expected)


def test_materialize_complete_video_views_hardlinks_exact_selected_attempts(tmp_path):
    label = "p2_stage_on_dirnorm_rbf_global_w1_e050"
    selected = {}
    for episode in range(10):
        source_dir = tmp_path / "source" / label / f"episode_{episode + 1}"
        source_dir.mkdir(parents=True)
        video = source_dir / f"episode_{episode + 1}_fail_agentview.mp4"
        video.write_bytes(f"video-{episode}".encode())
        selected[str(episode)] = {"video": str(video), "video_readable": True}
    analysis = {
        "generated_at": "2026-08-05T00:00:00+00:00",
        "jobs": [
            {
                "label": label,
                "accepted_episode_count": 10,
                "selected_attempts": selected,
            }
        ],
    }
    destination = tmp_path / "formal_complete_videos"

    manifest = audit.materialize_complete_video_views(
        analysis,
        destination,
        ffprobe_fn=lambda _path: True,
    )

    assert manifest["job_count"] == 1
    assert manifest["video_count"] == 10
    for episode in range(10):
        source = Path(selected[str(episode)]["video"])
        linked = next((destination / label / f"episode_{episode + 1}").glob("*.mp4"))
        assert source.stat().st_ino == linked.stat().st_ino


def test_rank_candidates_uses_preregistered_first_decisive_key():
    records = [
        {"label": "b", "eligible": True, "is_baseline": False, "success_count": 0},
        {"label": "a", "eligible": True, "is_baseline": False, "success_count": 1},
        {"label": "control", "eligible": True, "is_baseline": True, "success_count": 9},
    ]

    ranked = audit.rank_candidates(records)

    assert [row["label"] for row in ranked] == ["a", "b"]


def test_freeze_and_verify_decision_manifest_is_read_only_and_canonical(tmp_path):
    path = tmp_path / "decision.json"
    payload = {"schema": "test", "no_adoption": True, "profiles": [{"label": "x"}]}

    frozen = audit.freeze_decision_manifest(payload, path)

    assert frozen["canonical_manifest_checksum"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o444
    assert audit.verify_decision_manifest(path) == frozen
    with pytest.raises(FileExistsError):
        audit.freeze_decision_manifest(payload, path)

    serialized = json.loads(path.read_text())
    serialized["no_adoption"] = False
    path.chmod(0o644)
    path.write_text(json.dumps(serialized))
    path.chmod(0o444)
    with pytest.raises(ValueError, match="checksum"):
        audit.verify_decision_manifest(path)


def test_render_report_keeps_current_validity_and_no_adoption_explicit():
    report = audit.render_report(
        {
            "generated_at": "2026-08-05T00:00:00+00:00",
            "ledger": {"effective_attempt_count": 120, "attempt_cap": 120},
            "jobs": [
                {
                    "label": "p2_stage_on_abs_rbf_control",
                    "role": "control",
                    "eligible": False,
                    "accepted_episode_count": 0,
                    "success_count": 0,
                    "success_tasks": [],
                    "failure_reason": "native abort",
                },
                {
                    "label": "p2_stage_on_dirnorm_rbf_global_w0_e025",
                    "role": "global",
                    "weight_profile": "w0",
                    "endpoint_profile": "e025",
                    "eligible": True,
                    "accepted_episode_count": 10,
                    "success_count": 0,
                    "success_tasks": [],
                    "failure_reason": "",
                },
            ],
            "historical_baseline": {"success_count": 3, "success_tasks": [3, 8, 9]},
            "ranking": {"winner_label": "p2_stage_on_dirnorm_rbf_global_w0_e025"},
            "gates": {"task": "FAIL", "mechanism": "INCONCLUSIVE", "safety": "INCONCLUSIVE"},
            "no_adoption": True,
            "main_effects": {"estimable": False, "reason": "grid incomplete"},
            "classification_summary": {},
            "storage": {},
            "preflight": {},
            "implementation": {},
            "runtime_diagnostics": {
                "status": "confirmed-native-driver-abort",
                "root_cause": "libnvidia-eglcore abort after Xid 31/109",
                "recovery": "independently admitted split CUDA/EGL devices",
            },
        }
    )

    assert "no_adoption" in report
    assert "3×3" in report
    assert "native abort" in report
    assert "libnvidia-eglcore abort after Xid 31/109" in report
    assert "independently admitted split CUDA/EGL devices" in report
    assert "不授权改变已批准矩阵" in report
