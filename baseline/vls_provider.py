"""Independent API providers for the pinned official VLS implementation.

Stage prompt, image ordering and decision parsing follow VLS commit b6e87ed.
The transport uses the installed google-genai SDK instead of its legacy SDK.
See references/vls/LICENSE (MIT, Copyright (c) 2025 Shuo Liu).
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import time

from .io import append_json, digest, write_json
from .vls_guidance import InvalidGuidanceResponse, install_guidance_validation
from .vls_retry import retry_provider_call

SOURCE_COMMIT = "b6e87edc217a2a7682caadba285677fc79eb6f81"
REWARD_MODEL = "gpt-5.1"
STAGE_MODEL = "gemini-3-flash-preview"
PROVIDER = "vls_official_api_v1"
REFERENCE = Path(__file__).resolve().parent / "references/vls"


class InvalidStageResponse(ValueError):
    pass


def parse_stage(output, num_stages):
    """Keep upstream stage clamping; reject missing decisions instead of guessing."""
    stage = re.search(r"stage\s+(\d+)", output.lower())
    guidance = re.search(r"guidance:\s*(yes|no)", output.lower())
    if stage is None or guidance is None:
        raise InvalidStageResponse("Gemini response is missing a stage or guidance decision")
    stage_num = int(stage.group(1))
    if num_stages is not None and stage_num > 0:
        stage_num = min(stage_num, num_stages)
    return stage_num, guidance.group(1) == "yes"


def _image(rgb):
    import numpy as np
    from PIL import Image
    rgb = np.asarray(rgb)
    if rgb.dtype != np.uint8:
        rgb = (rgb * 255 if rgb.max() <= 1.0 else rgb).astype(np.uint8)
    if rgb.ndim == 4:
        rgb = rgb[0]
    return Image.fromarray(rgb)


class VLSGeminiStageRecognizer:
    def __init__(self, config):
        if config["model"] != STAGE_MODEL:
            raise ValueError("VLS requires the pinned official Gemini model")
        api_key = config.get("api_key") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is missing from the project .env")
        from google import genai
        from google.genai import types
        self.client = genai.Client(vertexai=False, api_key=api_key, http_options=types.HttpOptions(
            timeout=config["timeout_ms"], retry_options=types.HttpRetryOptions(attempts=1)))
        self.model = STAGE_MODEL
        self.prompt_template = Path(config["stage_template_path"]).read_text()
        self.ledger = Path(config["call_ledger_path"])
        self.calls_root = self.ledger.parent / "stage_api_calls"
        self.calls_root.mkdir(parents=True, exist_ok=True)
        self.max_calls = config["max_provider_calls"]
        self.calls = 0

    def close(self):
        self.client.close()

    def identify_stage_and_guidance(self, current_rgb, instruction, stage_descriptions,
                                    init_img_with_keypoints=None, keypoint_id_to_object=None,
                                    num_stages=None, trigger_reason=None):
        if self.calls >= self.max_calls:
            raise RuntimeError("VLS stage API call budget exhausted")
        self.calls += 1
        call_dir = self.calls_root / f"call_{self.calls:03d}"
        call_dir.mkdir()
        keypoint_info = "(No keypoint info)"
        if keypoint_id_to_object:
            keypoint_info = "\n".join(f"  Keypoint {k}: {v}" for k, v in keypoint_id_to_object.items())
        prompt = self.prompt_template.format(
            trigger_reason=trigger_reason or "initial query", instruction=instruction,
            stage_descriptions=stage_descriptions, keypoint_info=keypoint_info)
        (call_dir / "prompt.txt").write_text(prompt)
        content = [prompt]
        if init_img_with_keypoints is not None:
            initial = _image(init_img_with_keypoints)
            initial.save(call_dir / "initial.png")
            content.extend(["**Initial Image (with keypoints):**", initial])
        current = _image(current_rgb)
        current.save(call_dir / "current.png")
        content.extend(["**Current Image:**", current])
        record = {"provider": "google_genai", "api": "generate_content", "model": self.model,
                  "call": self.calls, "started_at": datetime.now(timezone.utc).isoformat(),
                  "status": "requesting", "trigger_reason": trigger_reason,
                  "inputs": {p.name: digest(p) for p in call_dir.iterdir() if p.is_file()}}
        write_json(call_dir / "status.json", record)
        started = time.monotonic()

        def request(attempt):
            # Upstream does not override temperature, thinking or generation length.
            response = self.client.models.generate_content(model=self.model, contents=content)
            output = (response.text or "").strip()
            (call_dir / "response.txt").write_text(output)
            attempt.update(response_id=getattr(response, "response_id", None),
                           response_model=getattr(response, "model_version", None))
            usage = getattr(response, "usage_metadata", None)
            if usage is not None:
                attempt["usage"] = usage.model_dump(mode="json")
            stage, guidance = parse_stage(output, num_stages)
            attempt.update(stage=stage, guidance=guidance)
            return stage, guidance
        try:
            return retry_provider_call(request, record, attempts_path=call_dir / "attempts.jsonl",
                status_path=call_dir / "status.json", activity_path=self.ledger.parent / "provider_status.json",
                retry_errors=(InvalidStageResponse,))
        except Exception as exc:
            # Only permanent errors escape; no fallback stage or provider is used.
            record.update(status="failed", error_type=type(exc).__name__)
            raise
        finally:
            record["seconds"] = time.monotonic() - started
            write_json(call_dir / "status.json", record)
            append_json(self.ledger, record)


def create_reward_agent(config, base_dir=None, env_type=None):
    """Use the exact upstream generator and prompts, recording actual API models."""
    if config["model"] != REWARD_MODEL:
        raise ValueError("VLS requires the pinned official reward model")
    from .references.vls.vlm_query.vlm_agent import VLMAgent
    agent = VLMAgent(config=config, base_dir=base_dir, env_type=env_type)
    agent.client.timeout = config["timeout_ms"] / 1000
    agent.client.max_retries = 0
    original_create = agent.client.chat.completions.create
    ledger = Path(base_dir) / "reward_provider_calls.jsonl"
    calls = 0

    def create(**kwargs):
        nonlocal calls
        if kwargs.get("model") != REWARD_MODEL:
            raise ValueError("unexpected reward model substitution")
        calls += 1
        call_dir = ledger.parent / "reward_api_calls" / f"call_{calls:03d}"
        call_dir.mkdir(parents=True)
        started = time.monotonic()
        record = {"provider": "openai", "api": "chat.completions", "model": REWARD_MODEL,
                  "call": calls, "started_at": datetime.now(timezone.utc).isoformat(), "status": "requesting"}

        def request(attempt):
            response = original_create(**kwargs)
            if not kwargs.get("stream"):
                attempt.update(response_id=response.id, response_model=response.model)
                return response
            # Buffer a complete attempt before upstream sees any text. A failed
            # stream must never be concatenated with a newly generated response.
            chunks = []
            try:
                for chunk in response:
                    attempt.update(response_id=chunk.id, response_model=chunk.model)
                    for choice in chunk.choices:
                        if choice.finish_reason:
                            attempt["finish_reason"] = choice.finish_reason
                    chunks.append(chunk)
                    attempt["chunks_received"] = len(chunks)
                if attempt.get("finish_reason") is None:
                    raise ConnectionError("VLS reward stream ended before its completion marker")
                if attempt["finish_reason"] == "length":
                    raise InvalidGuidanceResponse("VLS reward response did not finish normally: token limit reached")
                if attempt["finish_reason"] != "stop":
                    raise RuntimeError("VLS reward response did not finish normally")
                return iter(chunks)
            finally:
                response.close()
        try:
            return retry_provider_call(request, record, attempts_path=call_dir / "attempts.jsonl",
                status_path=call_dir / "status.json", activity_path=ledger.parent / "provider_status.json")
        except Exception as exc:
            record.update(status="failed", error_type=type(exc).__name__)
            raise
        finally:
            record["seconds"] = time.monotonic() - started
            write_json(call_dir / "status.json", record)
            append_json(ledger, record)

    agent.client.chat.completions.create = create
    return install_guidance_validation(agent)


def _disabled_grounder(config):
    raise RuntimeError("This LIBERO VLS baseline uses native segmentation; grounding is disabled")


@contextmanager
def official_engine_factories(engine):
    """Replace only this baseline process's factories before Main initializes them."""
    replacements = {"create_gemini_stage_recognizer": VLSGeminiStageRecognizer,
                    "create_gemini_grounder": _disabled_grounder, "VLMAgent": create_reward_agent}
    original = {name: getattr(engine, name) for name in replacements}
    try:
        for name, factory in replacements.items():
            setattr(engine, name, factory)
        yield
    finally:
        for name, factory in original.items():
            setattr(engine, name, factory)
