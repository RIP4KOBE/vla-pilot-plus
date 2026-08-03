import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.gemini_grounder import GeminiStageRecognizer


def _response_client(text):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )
    completions = SimpleNamespace(create=lambda **kwargs: response)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _failing_client(error):
    def _raise(**kwargs):
        raise error

    completions = SimpleNamespace(create=_raise)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _recognizer(client):
    recognizer = GeminiStageRecognizer.__new__(GeminiStageRecognizer)
    recognizer.config = {}
    recognizer.model = "gemini-test"
    recognizer.client = client
    recognizer.prompt_template = (
        "trigger={trigger_reason}\n"
        "instruction={instruction}\n"
        "stages={stage_descriptions}\n"
        "keypoints={keypoint_info}"
    )
    return recognizer


def _identify(recognizer):
    return recognizer.identify_stage_and_guidance(
        current_rgb=np.zeros((2, 2, 3), dtype=np.uint8),
        instruction="move the object",
        stage_descriptions="Stage 1: grasp\nStage 2: place",
        num_stages=2,
        trigger_reason="gripper closed",
    )


def test_stage_recognizer_last_result_is_none_before_first_query(
    monkeypatch, tmp_path
):
    import core.gemini_grounder as gemini_grounder

    template_path = tmp_path / "stage_template.txt"
    template_path.write_text(
        "{trigger_reason} {instruction} {stage_descriptions} {keypoint_info}"
    )
    monkeypatch.setattr(
        gemini_grounder,
        "_make_client",
        lambda config: _response_client("Stage 1\nGuidance: yes"),
    )

    recognizer = GeminiStageRecognizer({"stage_template_path": str(template_path)})

    assert recognizer.last_result is None


def test_stage_recognizer_exposes_successful_last_result():
    recognizer = _recognizer(
        _response_client("Stage 2\nGuidance: no\nEvidence: object is grasped")
    )

    result = _identify(recognizer)

    assert result == (2, False)
    assert recognizer.last_result == {
        "ok": True,
        "parse_ok": True,
        "raw_response": "Stage 2\nGuidance: no\nEvidence: object is grasped",
        "parsed_stage": 2,
        "parsed_guidance": False,
        "evidence": "object is grasped",
        "error": None,
        "query_latency_s": pytest.approx(
            recognizer.last_result["query_latency_s"], abs=0.0
        ),
    }
    assert recognizer.last_result["query_latency_s"] >= 0.0


def test_stage_recognizer_exposes_failed_last_result_and_keeps_fallback():
    recognizer = _recognizer(_failing_client(RuntimeError("service unavailable")))

    result = _identify(recognizer)

    assert result == (1, True)
    assert recognizer.last_result["ok"] is False
    assert recognizer.last_result["raw_response"] is None
    assert recognizer.last_result["parsed_stage"] == 1
    assert recognizer.last_result["parsed_guidance"] is True
    assert recognizer.last_result["evidence"] == ""
    assert "service unavailable" in recognizer.last_result["error"]
    assert recognizer.last_result["query_latency_s"] >= 0.0


def test_stage_recognizer_marks_unparseable_response_as_failed_query():
    recognizer = _recognizer(_response_client("The scene is ambiguous."))

    result = _identify(recognizer)

    assert result == (1, True)
    assert recognizer.last_result["ok"] is False
    assert recognizer.last_result["parse_ok"] is False
    assert recognizer.last_result["raw_response"] == "The scene is ambiguous."
    assert "parse" in recognizer.last_result["error"].lower()


class _Policy:
    def __init__(self):
        self.reset_stage_calls = 0

    def get_normalized_reward(self):
        return 0.0

    def reset_stage(self):
        self.reset_stage_calls += 1


class _Adapter:
    def get_vlm_image(self):
        return np.zeros((2, 2, 3), dtype=np.uint8)

    def get_task_description(self):
        return "move the object"


class _SuccessfulRecognizer:
    def __init__(self, secret):
        self.config = {"api_key": secret}
        self._secret = secret
        self.calls = 0
        self.last_result = None

    def identify_stage_and_guidance(self, **kwargs):
        self.calls += 1
        self.last_result = {
            "ok": True,
            "raw_response": f"Stage 2; Guidance: no; token={self._secret}",
            "parsed_stage": 2,
            "parsed_guidance": False,
            "evidence": "object is grasped",
            "error": None,
            "query_latency_s": 0.25,
        }
        return 2, False


def _main_module():
    import main

    return main


def _runner(tmp_path, recognizer, query_limit=10):
    main = _main_module()
    runner = main.Main.__new__(main.Main)
    runner.config = {
        "vlm_query_limit": query_limit,
        "eds_eval": {"output_dir": str(tmp_path / "eds_eval")},
    }
    runner.output_dir = str(tmp_path / "hydra")
    runner.policy = _Policy()
    runner.adapter = _Adapter()
    runner.gemini_stage_recognizer = recognizer
    runner.stage_descriptions = "Stage 1: grasp\nStage 2: place"
    runner.init_img_with_keypoints = np.zeros((2, 2, 3), dtype=np.uint8)
    runner.keypoint_id_to_object = {0: "target object"}
    runner.guidance_fns = {1: [object()], 2: []}
    return runner


def _trigger_state(query_count=0):
    return {
        "prev_norm_reward": 0.0,
        "prev_gripper_open": True,
        "current_stage": 1,
        "use_guidance": True,
        "vlm_query_count": query_count,
        "episode_id": 3,
        "task_id": 7,
        "global_step": 64,
        "chunk_id": 8,
        "episode_seed": 321,
        "previous_gripper_value": -1.0,
        "first_gripper_value": 0.5,
        "last_gripper_value": 1.0,
    }


def _read_events(tmp_path):
    path = tmp_path / "eds_eval" / "stage_events.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_stage_trigger_appends_auditable_redacted_event(tmp_path):
    secret = "stage-api-secret"
    recognizer = _SuccessfulRecognizer(secret)
    runner = _runner(tmp_path, recognizer)

    state = runner._update_stage(_trigger_state(), 1.0, 0.8, 0.6)

    assert state["current_stage"] == 2
    assert state["use_guidance"] is False
    assert state["vlm_query_count"] == 1
    assert runner.policy.reset_stage_calls == 1
    event = _read_events(tmp_path)[0]
    assert event == {
        "episode_id": 3,
        "task_id": 7,
        "global_step": 64,
        "chunk_id": 8,
        "episode_seed": 321,
        "trigger_reason": "gripper closed",
        "stage_before": 1,
        "stage_after": 2,
        "guidance_before": True,
        "guidance_after": False,
        "vlm_query_count": 1,
        "vlm_query_limit": 10,
        "gripper_value_used": 1.0,
        "previous_gripper_value": -1.0,
        "first_gripper_value": 0.5,
        "last_gripper_value": 1.0,
        "query_status": "ok",
        "query_ok": True,
        "skipped_reason": None,
        "raw_response": "Stage 2; Guidance: no; token=[REDACTED]",
        "parsed_stage": 2,
        "parsed_guidance": False,
        "evidence": "object is grasped",
        "error": None,
        "query_latency_s": 0.25,
    }
    assert secret not in json.dumps(event)


@pytest.mark.parametrize(
    ("recognizer", "query_count", "query_limit", "skipped_reason"),
    [
        (None, 0, 10, "recognizer_unavailable"),
        (object(), 2, 2, "query_limit_reached"),
    ],
)
def test_stage_trigger_records_skipped_query(
    tmp_path, recognizer, query_count, query_limit, skipped_reason
):
    runner = _runner(tmp_path, recognizer, query_limit=query_limit)

    state = runner._update_stage(
        _trigger_state(query_count=query_count), 1.0, 0.8, 0.6
    )

    assert state["current_stage"] == 1
    assert state["use_guidance"] is True
    event = _read_events(tmp_path)[0]
    assert event["query_status"] == "skipped"
    assert event["skipped_reason"] == skipped_reason
    assert event["vlm_query_count"] == query_count
    assert event["stage_before"] == event["stage_after"] == 1
    assert event["guidance_before"] is event["guidance_after"] is True


def test_stage_trace_write_failure_warns_without_interrupting_control_loop(
    monkeypatch, tmp_path
):
    main = _main_module()
    runner = _runner(tmp_path, recognizer=None)
    warnings = []
    monkeypatch.setattr(
        main,
        "append_jsonl",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr(main.log, "warning", warnings.append)

    state = runner._update_stage(_trigger_state(), 1.0, 0.8, 0.6)

    assert state["current_stage"] == 1
    assert any("stage-event trace" in warning and "disk full" in warning for warning in warnings)


def test_run_passes_generated_episode_seed_to_run_episode(monkeypatch, tmp_path):
    main = _main_module()
    runner = main.Main.__new__(main.Main)
    runner.config = {"episode_num": 1, "use_guidance": False}
    runner.output_dir = f"{tmp_path}/"
    runner.backend = "libero"
    runner.current_guide_scale = 80.0
    runner.policy = SimpleNamespace(reset=lambda: None)
    runner.video_recorder = SimpleNamespace(clear=lambda: None)
    reset_seeds = []
    runner.adapter = SimpleNamespace(
        reset=lambda *, seed: reset_seeds.append(seed),
        get_task_info=lambda: {"task_id": 7, "recommended_guide_scale": None},
    )
    episode_calls = []
    runner._run_episode = lambda episode, episode_dir, episode_seed: episode_calls.append(
        (episode, episode_dir, episode_seed)
    )
    monkeypatch.setattr(
        main.torch,
        "randint",
        lambda *args, **kwargs: SimpleNamespace(item=lambda: 321),
    )

    runner.run()

    assert reset_seeds == [321]
    assert episode_calls == [(0, str(tmp_path / "episode_1"), 321)]


def test_episode_metadata_records_seed_for_stage_pairing(tmp_path):
    runner = _runner(tmp_path, recognizer=None)

    runner._append_episode_metadata(episode=3, episode_seed=321, task_id=7)

    path = tmp_path / "eds_eval" / "episode_metadata.jsonl"
    assert json.loads(path.read_text().strip()) == {
        "episode_id": 3,
        "episode_seed": 321,
        "task_id": 7,
    }
