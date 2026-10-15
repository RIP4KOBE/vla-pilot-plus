"""Offline historical Stage replay and exact input capture; never online results."""
from __future__ import annotations

import json
from pathlib import Path
from core.gemini_grounder import GeminiStageRecognizer
import base64
import hashlib


class ReplayMismatch(BaseException):
    """Abort the entire evaluation rather than count a divergent replay as valid."""


class TraceReplayStageRecognizer(GeminiStageRecognizer):
    def __init__(self, config: dict):
        self.trace_path = Path(config["replay_trace_path"]).resolve()
        self.rows = [json.loads(line) for line in self.trace_path.read_text().splitlines() if line.strip()]
        if not self.rows or any(row.get("query_status") not in ("ok", "error") for row in self.rows):
            raise ValueError("Recorded Stage trace contains no queries or unsupported rows")
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


class CaptureTraceReplayStageRecognizer(TraceReplayStageRecognizer):
    def __init__(self, config: dict):
        root = Path(config["capture_dir"]).resolve()
        if root.exists():
            raise ValueError("Stage capture directory must not already exist")
        root.mkdir(parents=True)
        self.capture_dir = root
        super().__init__(config)

    def _request_stage_response(self, content):
        index = self.cursor
        context = dict(self.context or {})
        response = super()._request_stage_response(content)
        target = self.capture_dir / f"request_{index:04d}"
        try:
            target.mkdir()
            parts = []
            texts = []
            images = []
            for part in content:
                if part["type"] == "text":
                    value = part["text"]
                    if not isinstance(value, str):
                        raise ValueError("Stage text part must be a string")
                    parts.append({"type": "text", "text": value})
                    texts.append(value)
                elif part["type"] == "image_url":
                    uri = part["image_url"]["url"]
                    prefix = "data:image/png;base64,"
                    if not isinstance(uri, str) or not uri.startswith(prefix):
                        raise ValueError("Stage image must be a PNG data URL")
                    data = base64.b64decode(uri[len(prefix):], validate=True)
                    name = f"image_{len(images) + 1:02d}.png"
                    (target / name).write_bytes(data)
                    digest = hashlib.sha256(data).hexdigest()
                    parts.append({"type": "image", "file": name, "sha256": digest})
                    images.append(digest)
                else:
                    raise ValueError("Unexpected Stage content type")
            if len(images) != 2:
                raise ValueError("Stage capture requires initial and current images")
            codex_prompt = "\n\n".join(texts)
            (target / "codex_prompt.txt").write_text(codex_prompt)
            (target / "parts.json").write_text(json.dumps(parts, ensure_ascii=False, indent=2) + "\n")
            (target / "metadata.json").write_text(json.dumps({
                "schema": "stage-input-capture-v1", "query_index": index,
                "context": context, "historical_raw_response": response,
                "codex_prompt_sha256": hashlib.sha256(codex_prompt.encode()).hexdigest(),
                "image_png_sha256": images,
            }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        except Exception as exc:
            raise ReplayMismatch(f"Stage capture failed at query {index}: {type(exc).__name__}") from None
        return response
