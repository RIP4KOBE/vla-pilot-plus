"""Replay the archived C0 Stage replies with exact query-order checks.

This diagnostic intentionally preserves malformed Poe replies: the historical
parser maps those to stage 1 / guidance on. It never contacts a model service.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.gemini_grounder import GeminiStageRecognizer


class ReplayMismatch(BaseException):
    """Abort the entire evaluation rather than count a divergent run as C0."""


class TraceReplayStageRecognizer(GeminiStageRecognizer):
    def __init__(self, config: dict):
        self.trace_path = Path(config["replay_trace_path"]).resolve()
        self.rows = [json.loads(line) for line in self.trace_path.read_text().splitlines() if line.strip()]
        if not self.rows or any(row.get("query_status") not in ("ok", "error") for row in self.rows):
            raise ValueError("Historical C0 trace contains no queries or unsupported rows")
        self.cursor = 0
        self.context = None
        super().__init__(config)

    def _configure_transport(self, config):
        self.client = None
        self.api_request_counter = None

    def _record_transport_result(self, counter_before):
        pass

    def set_trace_context(self, state: dict, trigger_reason: str) -> None:
        self.context = {
            "episode_id": state.get("episode_id"),
            "task_id": state.get("task_id"),
            "episode_seed": state.get("episode_seed"),
            "global_step": state.get("global_step"),
            "chunk_id": state.get("chunk_id"),
            "trigger_reason": trigger_reason,
            "stage_before": state.get("current_stage"),
            "guidance_before": state.get("use_guidance"),
        }

    def _request_stage_response(self, content):
        if self.cursor >= len(self.rows):
            raise ReplayMismatch(f"Historical Stage trace exhausted at query {self.cursor}")
        expected = self.rows[self.cursor]
        actual = self.context
        if actual is None:
            raise ReplayMismatch("Historical Stage query missing caller context")
        different = {
            key: {"expected": expected.get(key), "actual": actual.get(key)}
            for key in actual if expected.get(key) != actual.get(key)
        }
        if different:
            raise ReplayMismatch(
                f"Historical Stage query {self.cursor} differs: {json.dumps(different, sort_keys=True)}"
            )
        self.cursor += 1
        self.context = None
        response = expected.get("raw_response")
        if not isinstance(response, str):
            raise ReplayMismatch(f"Historical Stage query {self.cursor - 1} has no raw reply")
        return response
