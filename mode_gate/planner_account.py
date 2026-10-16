"""Strict JSON planning through one native, account-authenticated Codex task.

The task itself reasons over the original prompts and images. This is a file
queue, not an API client, nested Codex process, credential bridge or scheduler.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
from uuid import uuid4

from .codex_account import validate_visual_review
from .io_utils import atomic_write_json


MODEL = "gpt-6-astra"
REASONING = "ultra"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs/planner_account.json"


def load_planner_account_config(path: Path | None = None) -> dict:
    path = Path(path) if path is not None else Path(os.environ.get("VLA_RSI_PLANNER_CONFIG", str(DEFAULT_CONFIG)))
    value = json.loads(path.read_text())
    if (value.get("schema_version") != "codex-top-level-planner-v1"
            or value.get("auth_mode") != "chatgpt"
            or value.get("model") != MODEL or value.get("reasoning_effort") != REASONING
            or not value.get("planner_thread_id") or float(value.get("timeout_seconds", 0)) <= 0
            or not Path(value.get("queue_root", "")).is_absolute()):
        raise ValueError("invalid Codex account planner configuration; no provider fallback")
    return value


def validate_planner_response(request: dict, response: dict) -> None:
    """Identity, image inspection and JSON contract are checked before commit."""
    for key in ("request_id", "request_sha256", "planner_thread_id", "model", "reasoning_effort", "auth_mode"):
        if response.get(key) != request.get(key):
            raise ValueError(f"planner response {key} mismatch")
    if response.get("error"):
        raise ValueError(f"planner reported an error: {response['error']}")
    validate_visual_review(request, response)
    from jsonschema import Draft202012Validator
    Draft202012Validator(request["schema"]).validate(response.get("result"))


class CodexPlannerClient:
    """Compatibility at the structured-output boundary, with truthful provenance."""
    auth_mode = "chatgpt"

    def __init__(self, config: dict | None = None, *, ignore_experiment_pause: bool = False):
        self.config = dict(config) if config is not None else load_planner_account_config()
        if self.config.get("model") != MODEL or self.config.get("reasoning_effort") != REASONING:
            raise ValueError("Codex planner must use gpt-6-astra / ultra")
        self.queue_root = Path(self.config["queue_root"])
        self.timeout_seconds = float(self.config["timeout_seconds"])
        self.ignore_experiment_pause = ignore_experiment_pause
        self.interactions = self.models = self

    def get(self, *, model: str):
        self._check_model(model)
        return SimpleNamespace(name=model, auth_mode=self.auth_mode)

    def _check_model(self, model: str) -> None:
        if model != MODEL:
            raise ValueError("Gemini/API model substitution is disabled for the account planner")

    def create(self, *, model, system_instruction, input, response_format,
               generation_config=None, store=False):
        self._check_model(model)
        del store
        if (generation_config or {}).get("thinking_level", REASONING) != REASONING:
            raise ValueError("account planner reasoning must remain ultra")
        texts, images = [], []
        for item in input:
            if item["type"] == "text":
                texts.append(item["text"])
            elif item["type"] == "image":
                images.append((base64.b64decode(item["data"], validate=True), item["mime_type"]))
            else:
                raise ValueError("unsupported planner input")
        return self.request(prompt=system_instruction + "\n\n" + "\n\n".join(texts),
                            schema=response_format["schema"], images=images)

    def generate_content(self, *, model, contents, config):
        self._check_model(model)
        if not isinstance(config, dict):
            raise ValueError("account planning requires a plain JSON output contract")
        return self.request(prompt="\n\n".join(contents), schema=config["response_json_schema"])

    def request(self, *, prompt: str, schema: dict, images=(), purpose="structured_planning"):
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(schema)
        request_id = uuid4().hex
        folder = self.queue_root / request_id
        folder.mkdir(parents=True)
        image_items = []
        for index, (data, mime) in enumerate(images):
            if mime not in {"image/png", "image/jpeg"}:
                raise ValueError("unsupported planning image MIME type")
            from io import BytesIO
            from PIL import Image
            with Image.open(BytesIO(data)) as im:
                im.verify()
            path = folder / f"image_{index:02d}.{'png' if mime == 'image/png' else 'jpg'}"
            with path.open("xb") as stream:
                stream.write(data)
            image_items.append({"image_id": f"{request_id}:{index}", "path": str(path),
                                "sha256": hashlib.sha256(data).hexdigest(), "mime_type": mime})
        visuals = {"schema_version": "planner-visuals-v1", "images": image_items,
                   "source": "original_planner_inputs", "required_review": "all images"}
        visuals["manifest_sha256"] = hashlib.sha256(json.dumps(visuals, sort_keys=True).encode()).hexdigest()
        value = {"schema_version": "codex-planner-request-v1", "request_id": request_id,
                 "created_at": time.time(), "expires_at": time.time() + self.timeout_seconds,
                 "model": MODEL, "reasoning_effort": REASONING, "auth_mode": self.auth_mode,
                 "planner_thread_id": self.config["planner_thread_id"], "purpose": purpose,
                 "schema": schema, "prompt": prompt, "visual_observations": visuals}
        value["request_sha256"] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        atomic_write_json(folder / "request.json", value)
        deadline = time.monotonic() + self.timeout_seconds
        try:
            while not (folder / "response.json").exists():
                output = self.config.get("experiment_output")
                if output and not self.ignore_experiment_pause and any(
                    (Path(output) / name).exists() for name in ("park.request", "stop.request", "supervisor.stop.request")
                ):
                    raise InterruptedError("account planner paused at request boundary")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Codex account planner timed out; no Gemini/API fallback")
                time.sleep(0.25)
            response = json.loads((folder / "response.json").read_text())
            validate_planner_response(value, response)
        except BaseException as exc:
            atomic_write_json(folder / "cancelled.json", {"reason": f"{type(exc).__name__}: {exc}"})
            raise
        metadata = {key: value[key] for key in ("model", "reasoning_effort", "auth_mode", "planner_thread_id", "request_sha256", "request_id")}
        metadata.update(request_path=str(folder / "request.json"),
                        visual_review=response.get("visual_review"), provider="codex_account")
        text = json.dumps(response["result"], ensure_ascii=False)
        return SimpleNamespace(text=text, output_text=text, usage_metadata=None,
                               planner_metadata=metadata)
