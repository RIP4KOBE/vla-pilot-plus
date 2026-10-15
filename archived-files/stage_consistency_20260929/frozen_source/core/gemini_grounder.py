#!/usr/bin/env python3
"""
Gemini Grounder - Uses Poe's OpenAI-compatible API to call Gemini models
for object detection (grounding) and stage recognition.

No google-generativeai dependency required — uses the openai client with
base_url pointing to Poe (or any other OpenAI-compatible proxy).
"""

import numpy as np
import json
import base64
import os
import re
import io
import time
from typing import List, Dict, Tuple, Optional
from PIL import Image
from openai import OpenAI

from utils.logging_utils import SteerLogger

logger = SteerLogger("GeminiGrounder")


class APIRequestCounter:
    """Observe HTTP send attempts, including SDK retries, without payload data."""

    def __init__(self):
        self.request_attempts = 0
        self.sdk_retry_attempts = 0
        self.observation_available = False

    def on_request(self, request):
        self.request_attempts += 1
        # OpenAI 2.8.1 emits this non-secret count on every HTTP attempt.
        # Read only; neither headers nor retry behavior are modified.
        try:
            self.sdk_retry_attempts += int(request.headers.get("x-stainless-retry-count", "0")) > 0
        except (AttributeError, TypeError, ValueError):
            pass

    def snapshot(self):
        return {
            "request_attempts": int(self.request_attempts),
            "sdk_retry_attempts": int(self.sdk_retry_attempts),
            "observation_available": bool(self.observation_available),
        }


def observe_api_requests(client):
    """Attach an idempotent observer to the existing sync client's HTTP hooks.

    SDK requests/retries and any caller retries pass through the same hook.
    Only SDK retries are separately classified; caller retries remain included
    in total request attempts. Unsupported test/custom transports are reported
    unavailable instead of changing client behavior.
    """
    counter = getattr(client, "_qd_ed_http_request_counter", None)
    if isinstance(counter, APIRequestCounter):
        return counter
    counter = APIRequestCounter()
    http_client = getattr(client, "_client", None)
    hooks = getattr(http_client, "event_hooks", None)
    if isinstance(hooks, dict):
        hooks.setdefault("request", []).append(counter.on_request)
        counter.observation_available = True
    try:
        client._qd_ed_http_request_counter = counter
    except (AttributeError, TypeError):
        pass
    return counter


def _image_to_base64(rgb: np.ndarray) -> str:
    if rgb.dtype != np.uint8:
        rgb = (rgb * 255).astype(np.uint8) if rgb.max() <= 1.0 else rgb.astype(np.uint8)
    if rgb.ndim == 4:
        rgb = rgb[0]
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _make_client(config: dict) -> OpenAI:
    api_key = config.get("api_key") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = config.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    return OpenAI(api_key=api_key, base_url=base_url)


class GeminiGrounder:
    """
    Detect objects via Gemini visual grounding through an OpenAI-compatible API.
    Returns bounding boxes in [y_min, x_min, y_max, x_max] normalized to 0-1000.
    """

    def __init__(self, config: dict):
        self.config = config
        self.model = config.get("model", "gemini-2.5-flash")
        self.client = _make_client(config)
        self.api_request_counter = observe_api_requests(self.client)
        logger.info(f"GeminiGrounder initialized with model: {self.model}")

    def detect_objects(self, rgb: np.ndarray, object_names: List[str]) -> List[Dict]:
        H, W = rgb.shape[:2]
        objects_str = ", ".join(object_names)
        prompt = (
            f"Detect these objects in the image and return bounding boxes: {objects_str}\n\n"
            "Return a JSON array where each object has:\n"
            '- "label": the object name\n'
            '- "box_2d": [y_min, x_min, y_max, x_max] normalized to 0-1000\n\n'
            'Example: [{"label": "drawer handle", "box_2d": [500, 200, 600, 400]}]\n\n'
            "Only return the JSON array, no other text. If an object is not found, omit it."
        )

        b64 = _image_to_base64(rgb)
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
                max_tokens=512,
                temperature=0.0,
            )
            text = resp.choices[0].message.content.strip()

            # Strip markdown fences if present
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            detections = json.loads(text)
            for det in detections:
                box = det["box_2d"]
                det["box_pixel"] = [
                    int(box[0] * H / 1000),
                    int(box[1] * W / 1000),
                    int(box[2] * H / 1000),
                    int(box[3] * W / 1000),
                ]
            logger.info(f"Detected {len(detections)} objects: {[d['label'] for d in detections]}")
            return detections
        except Exception as e:
            logger.error(f"Gemini detection failed: {e}")
            return []

    def detect_to_segmentation(
        self, rgb: np.ndarray, object_names: List[str]
    ) -> Tuple[np.ndarray, Dict[int, str]]:
        H, W = rgb.shape[:2]
        detections = self.detect_objects(rgb, object_names)
        segmentation = np.zeros((H, W), dtype=np.int32)
        segment_id_to_name = {0: "background"}
        for i, det in enumerate(detections):
            seg_id = i + 1
            y_min, x_min, y_max, x_max = det["box_pixel"]
            y_min, x_min = max(0, y_min), max(0, x_min)
            y_max, x_max = min(H, y_max), min(W, x_max)
            mask = segmentation[y_min:y_max, x_min:x_max] == 0
            segmentation[y_min:y_max, x_min:x_max][mask] = seg_id
            segment_id_to_name[seg_id] = det["label"]
        return segmentation, segment_id_to_name

    def detect_points(self, rgb: np.ndarray, object_names: List[str]) -> Dict[str, Tuple[int, int]]:
        detections = self.detect_objects(rgb, object_names)
        return {
            det["label"]: (
                (det["box_pixel"][1] + det["box_pixel"][3]) // 2,
                (det["box_pixel"][0] + det["box_pixel"][2]) // 2,
            )
            for det in detections
        }


def create_gemini_grounder(config: dict) -> GeminiGrounder:
    return GeminiGrounder(config)


class GeminiStageRecognizer:
    """
    Use Gemini (via OpenAI-compatible API) to identify the current task stage
    and decide whether guidance is needed.
    """

    def __init__(self, config: dict):
        self.config = config
        self.model = config.get("model", "gemini-2.5-flash")
        self._configure_transport(config)
        self._last_result = None

        template_path = config.get("stage_template_path")
        if template_path is None:
            import pathlib
            template_path = pathlib.Path(__file__).parent.parent / "vlm_query" / "stage_template.txt"
        with open(template_path, "r") as f:
            self.prompt_template = f.read()

        logger.info(f"StageRecognizer initialized with model: {self.model}")

    def _configure_transport(self, config):
        self.client = _make_client(config)
        self.api_request_counter = observe_api_requests(self.client)

    def _request_stage_response(self, content):
        observation_mode = self.config.get("output_format") == "stage_observation_v1"
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=int(self.config.get("observation_max_tokens", 2048)) if observation_mode else 256,
            temperature=0.0,
        )
        if observation_mode:
            self._last_completion_metadata = {
                "finish_reason": getattr(response.choices[0], "finish_reason", None),
                "response_model": getattr(response, "model", None),
                "max_tokens": int(self.config.get("observation_max_tokens", 2048)),
            }
        return response.choices[0].message.content.strip()

    def _record_transport_result(self, counter_before):
        if counter_before is not None:
            counter_after = self.api_request_counter.snapshot()
            self._last_result.update(
                api_request_attempts=counter_after["request_attempts"] - counter_before["request_attempts"],
                api_sdk_retry_attempts=counter_after["sdk_retry_attempts"] - counter_before["sdk_retry_attempts"],
                api_request_counter_available=counter_after["observation_available"],
            )

    @property
    def last_result(self) -> Optional[Dict[str, object]]:
        """Return a copy of the latest query metadata for audit logging."""
        if self._last_result is None:
            return None
        return dict(self._last_result)

    def identify_stage_and_guidance(
        self,
        current_rgb: np.ndarray,
        instruction: str,
        stage_descriptions: str,
        init_img_with_keypoints: np.ndarray = None,
        keypoint_id_to_object: Dict[int, str] = None,
        num_stages: int = None,
        trigger_reason: str = None,
    ) -> Tuple[int, bool]:
        keypoint_info = "(No keypoint info)"
        if keypoint_id_to_object:
            keypoint_info = "\n".join(f"  Keypoint {k}: {v}" for k, v in keypoint_id_to_object.items())

        prompt = self.prompt_template.format(
            trigger_reason=trigger_reason or "initial query",
            instruction=instruction,
            stage_descriptions=stage_descriptions,
            keypoint_info=keypoint_info,
        )

        content = [{"type": "text", "text": prompt}]
        if init_img_with_keypoints is not None:
            content.append({"type": "text", "text": "**Initial Image (with keypoints):**"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{_image_to_base64(init_img_with_keypoints)}"},
            })
        content.append({"type": "text", "text": "**Current Image:**"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{_image_to_base64(current_rgb)}"},
        })

        stage_num, need_guidance = 1, True
        output = None
        evidence = ""
        error = None
        parse_ok = False
        query_start_s = time.perf_counter()
        counter = getattr(self, "api_request_counter", None)
        counter_before = counter.snapshot() if counter is not None else None
        try:
            output = self._request_stage_response(content)

            stage_match = re.search(r"stage\s+(\d+)", output.lower())
            if stage_match:
                stage_num = int(stage_match.group(1))
                if num_stages:
                    stage_num = min(stage_num, num_stages)

            guidance_match = re.search(r"guidance:\s*(yes|no)", output.lower())
            if guidance_match:
                need_guidance = guidance_match.group(1) == "yes"

            parse_ok = stage_match is not None and guidance_match is not None
            if not parse_ok:
                stage_num, need_guidance = 1, True
                error = "Failed to parse both stage and guidance from response"

            m = re.search(r"evidence:\s*(.+)", output, re.IGNORECASE)
            if m:
                evidence = m.group(1).strip()

            if parse_ok:
                backend = self.config.get("backend", "openai_compatible")
                logger.info(f"[Stage:{backend}] Stage:{stage_num} Guide:{'ON' if need_guidance else 'OFF'} | {evidence[:80]}")
            else:
                logger.error(error)
        except Exception as e:
            error = str(e)
            logger.error(f"Stage recognition failed: {e}")

        self._last_result = {
            "ok": error is None and parse_ok,
            "parse_ok": parse_ok,
            "raw_response": output,
            "parsed_stage": stage_num,
            "parsed_guidance": need_guidance,
            "evidence": evidence,
            "error": error,
            "query_latency_s": float(time.perf_counter() - query_start_s),
        }
        self._record_transport_result(counter_before)

        return stage_num, need_guidance


def create_gemini_stage_recognizer(config: dict) -> GeminiStageRecognizer:
    backend = config.get("backend", "openai_compatible")
    if config.get("output_format") == "stage_observation_v1":
        if backend != "openai_compatible":
            raise ValueError("stage_observation_v1 currently supports the OpenAI-compatible backend only")
        from core.stage_observation import ObservationStageRecognizer, CapturedObservationStageRecognizer
        cls = CapturedObservationStageRecognizer if config.get("capture_dir") else ObservationStageRecognizer
        return cls(config)
    if backend == "trace_replay_capture":
        from core.stage_capture_trace_replay import CaptureTraceReplayStageRecognizer
        return CaptureTraceReplayStageRecognizer(config)
    if backend == "trace_replay":
        from core.trace_replay_stage import TraceReplayStageRecognizer
        return TraceReplayStageRecognizer(config)
    if backend == "codex_cli":
        from core.codex_stage import CodexStageRecognizer
        return CodexStageRecognizer(config)
    if backend != "openai_compatible":
        raise ValueError("Unknown stage recognition backend")
    if config.get("capture_dir"):
        from core.poe_stage_capture import PoeCaptureStageRecognizer
        return PoeCaptureStageRecognizer(config)
    return GeminiStageRecognizer(config)
