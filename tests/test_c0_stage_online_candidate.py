"""CPU-only checks for the frozen C0 online candidate dispatcher."""

import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from c0_stage_online_candidate import command, stage_errors_seen
from c0_stage_prompt_probe import NAME as PROMPT_CONDITION


def test_online_command_replaces_replay_backend_and_freezes_codex_condition():
    args = command("B_text_low_v6", 1)
    assert "perception.gemini.backend=codex_cli" in args
    assert "perception.gemini.output_format=legacy_text" in args
    assert "perception.gemini.event_policy=completed_transport_cycles_v6" in args
    assert "perception.gemini.reasoning_effort=low" in args
    assert "+perception.gemini.transport_retry_count=12" in args
    assert any(item.startswith("+perception.gemini.capture_dir=") for item in args)
    assert not any("replay_trace_path" in item for item in args)


def test_online_prompt_candidate_uses_variant_template():
    args = command(PROMPT_CONDITION, 1)
    assert any(item.startswith("+perception.gemini.stage_template_path=") and
               item.endswith("stage_template_codex_guidance_persistence_v1.txt") for item in args)
    assert "perception.gemini.event_policy=completed_transport_cycles_v6" in args


def test_recovery_attempt_has_new_output_and_preserves_first_attempt():
    first = command(PROMPT_CONDITION, 1, 1)
    second = command(PROMPT_CONDITION, 1, 2)
    assert first != second
    assert any("replicate1_attempt2/captured_stage_inputs" in item for item in second)
    assert any("replicate1/eds_eval" in item for item in first)


def test_online_monitor_detects_stage_failure_without_parsing_partial_line(tmp_path):
    path = tmp_path / "eds_eval/stage_events.jsonl"
    path.parent.mkdir()
    path.write_text(json.dumps({"query_status": "ok"}) + "\n" +
                    json.dumps({"query_status": "error"}) + "\n" +
                    '{"query_status":')
    assert stage_errors_seen(tmp_path) == 1
