"""Capture support for the legacy OpenAI-compatible Stage transport."""


import base64
import hashlib
import json
from pathlib import Path
from core.gemini_grounder import GeminiStageRecognizer


def sha(data):
    return hashlib.sha256(data).hexdigest()


class CapturedStageRecognizer(GeminiStageRecognizer):
    def __init__(self, config):
        self.capture_dir = Path(config["capture_dir"])
        self.capture_dir.mkdir(parents=True, exist_ok=False)
        self.cursor = 0
        self.context = {}
        self.fingerprint = None
        super().__init__(config)

    def set_trace_context(self, state, trigger_reason):
        self.context = {key: state.get(key) for key in (
            "episode_id", "task_id", "episode_seed", "global_step", "chunk_id")}
        self.context["trigger_reason"] = trigger_reason

    def _request_stage_response(self, content):
        index = self.cursor
        self.cursor += 1
        folder = self.capture_dir / f"request_{index:04d}"
        folder.mkdir()
        parts, images, texts = [], [], []
        for part in content:
            if part["type"] == "text":
                texts.append(part["text"])
                parts.append(dict(part))
            else:
                uri = part["image_url"]["url"]
                prefix = "data:image/png;base64,"
                if not uri.startswith(prefix):
                    raise ValueError("Expected original PNG data URL")
                data = base64.b64decode(uri[len(prefix):], validate=True)
                name = f"image_{len(images) + 1:02d}.png"
                (folder / name).write_bytes(data)
                images.append(sha(data))
                parts.append({"type": "image_url", "file": name, "sha256": sha(data)})
        prompt = "\n\n".join(texts)
        (folder / "prompt.txt").write_text(prompt)
        (folder / "parts.json").write_text(json.dumps(parts, indent=2) + "\n")
        self.fingerprint = {"prompt_sha256": sha(prompt.encode()), "image_png_sha256": images}
        metadata = {"query_index": index, "context": self.context,
                    "model": self.model, **self.fingerprint}
        try:
            # Preserve all original API parameters, SDK retries and raw text.
            response = super()._request_stage_response(content)
            metadata["raw_response"] = response
            return response
        except Exception as exc:
            metadata["transport_error_type"] = type(exc).__name__
            raise
        finally:
            if self.config.get("output_format") == "stage_observation_v1":
                metadata["completion_metadata"] = getattr(self, "_last_completion_metadata", None)
            (folder / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    def _record_transport_result(self, counter_before):
        super()._record_transport_result(counter_before)
        self._last_result["transport"] = {
            "backend": "openai_compatible", "request_fingerprint": self.fingerprint,
            "capture_query_index": self.cursor - 1,
        }
