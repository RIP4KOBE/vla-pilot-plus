"""Capture exact C0 Stage inputs while replaying the frozen historical replies.

The replay decision is unchanged. Each accepted query writes the original
multimodal part order, exact PNG bytes and the Codex CLI prompt serialization.
No online model is contacted by this backend.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from core.trace_replay_stage import ReplayMismatch, TraceReplayStageRecognizer


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
                raise ValueError("C0 Stage capture requires initial and current images")
            codex_prompt = "\n\n".join(texts)
            (target / "codex_prompt.txt").write_text(codex_prompt)
            (target / "parts.json").write_text(json.dumps(parts, ensure_ascii=False, indent=2) + "\n")
            (target / "metadata.json").write_text(json.dumps({
                "schema": "c0-stage-input-capture-v1", "query_index": index,
                "context": context, "historical_raw_response": response,
                "codex_prompt_sha256": hashlib.sha256(codex_prompt.encode()).hexdigest(),
                "image_png_sha256": images,
            }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        except Exception as exc:
            raise ReplayMismatch(f"Stage capture failed at query {index}: {type(exc).__name__}") from None
        return response
