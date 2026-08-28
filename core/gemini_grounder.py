#!/usr/bin/env python3
"""Gemini Robotics visual grounding and stage recognition.

Both visual paths use Google's official Interactions API.  They intentionally
share the exact model used by the mode semantic planner so formal rollouts
cannot silently fall back to a generic Gemini model or an unconfigured
OpenAI-compatible endpoint.
"""

import numpy as np
import json
import base64
import os
import io
from typing import List, Dict, Tuple, Optional
from PIL import Image

from utils.logging_utils import SteerLogger

logger = SteerLogger("GeminiGrounder")


def _image_to_base64(rgb: np.ndarray) -> str:
    if rgb.dtype != np.uint8:
        rgb = (rgb * 255).astype(np.uint8) if rgb.max() <= 1.0 else rgb.astype(np.uint8)
    if rgb.ndim == 4:
        rgb = rgb[0]
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


ROBOTICS_MODEL = "gemini-robotics-er-2-preview"


def _make_client(config: dict):
    injected = config.get("client")
    if injected is not None:
        return injected
    api_key = (
        config.get("api_key")
        or os.environ.get("MODE_GATE_GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is required for Gemini Robotics grounding")
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60_000),
    )


def _interaction_json(client, *, model: str, prompt: str, images: list[np.ndarray], schema: dict) -> object:
    content = [{"type": "text", "text": prompt}]
    for image in images:
        content.append(
            {
                "type": "image",
                "data": _image_to_base64(image),
                "mime_type": "image/png",
            }
        )
    interaction = client.interactions.create(
        model=model,
        system_instruction=(
            "You are a robot visual-grounding module. Use only the supplied "
            "images and task text. Return exactly the requested strict JSON."
        ),
        input=content,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        },
        generation_config={"thinking_level": "high"},
        store=False,
    )
    output_text = getattr(interaction, "output_text", None)
    if not output_text:
        raise ValueError("Gemini Robotics interaction returned no output_text")
    return json.loads(output_text)


class GeminiGrounder:
    """Detect objects with Gemini Robotics through the Interactions API.

    Bounding boxes use ``[y_min, x_min, y_max, x_max]`` normalized to 0-1000.
    Provider failures propagate so the controller can record a retryable abort;
    they must never be converted into an empty scene or an expansion decision.
    """

    def __init__(self, config: dict):
        self.config = config
        self.model = config.get("model", ROBOTICS_MODEL)
        if self.model != ROBOTICS_MODEL:
            raise ValueError(f"GeminiGrounder is frozen to {ROBOTICS_MODEL}")
        self.client = _make_client(config)
        logger.info(f"GeminiGrounder initialized with model: {self.model}")

    def detect_objects(self, rgb: np.ndarray, object_names: List[str]) -> List[Dict]:
        H, W = rgb.shape[:2]
        objects_str = ", ".join(object_names)
        prompt = (
            f"Detect these objects in the image and return bounding boxes: {objects_str}\n\n"
            'Return one JSON object with a "detections" array. Each detection has:\n'
            '- "label": the object name\n'
            '- "box_2d": [y_min, x_min, y_max, x_max] normalized to 0-1000\n\n'
            'Example: {"detections": [{"label": "drawer handle", '
            '"box_2d": [500, 200, 600, 400]}]}\n\n'
            "Return only that JSON object. If an object is not found, omit its detection."
        )

        try:
            payload = _interaction_json(
                self.client,
                model=self.model,
                prompt=prompt,
                images=[rgb],
                schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "detections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "label": {"type": "string"},
                                    "box_2d": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 4,
                                        "maxItems": 4,
                                    },
                                },
                                "required": ["label", "box_2d"],
                            },
                        }
                    },
                    "required": ["detections"],
                },
            )
            detections = payload["detections"]
            for det in detections:
                box = det["box_2d"]
                if len(box) != 4 or not all(np.isfinite(float(value)) for value in box):
                    raise ValueError(f"invalid Gemini bounding box: {box!r}")
                box = [min(1000.0, max(0.0, float(value))) for value in box]
                if box[2] <= box[0] or box[3] <= box[1]:
                    raise ValueError(f"degenerate Gemini bounding box: {box!r}")
                det["box_2d"] = box
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
            raise

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
    """Identify task stage with Gemini Robotics via the Interactions API."""

    def __init__(self, config: dict):
        self.config = config
        self.model = config.get("model", ROBOTICS_MODEL)
        if self.model != ROBOTICS_MODEL:
            raise ValueError(f"GeminiStageRecognizer is frozen to {ROBOTICS_MODEL}")
        self.client = _make_client(config)

        template_path = config.get("stage_template_path")
        if template_path is None:
            import pathlib
            template_path = pathlib.Path(__file__).parent.parent / "vlm_query" / "stage_template.txt"
        with open(template_path, "r") as f:
            self.prompt_template = f.read()

        logger.info(f"GeminiStageRecognizer initialized with model: {self.model}")

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

        images = []
        if init_img_with_keypoints is not None:
            prompt += "\nThe first image is the initial image with keypoints."
            images.append(init_img_with_keypoints)
        prompt += "\nThe final image is the current observation."
        images.append(current_rgb)

        try:
            payload = _interaction_json(
                self.client,
                model=self.model,
                prompt=prompt,
                images=images,
                schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "stage_num": {"type": "integer", "minimum": 1},
                        "need_guidance": {"type": "boolean"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["stage_num", "need_guidance", "evidence"],
                },
            )
            stage_num = int(payload["stage_num"])
            if num_stages:
                stage_num = min(stage_num, num_stages)
            need_guidance = bool(payload["need_guidance"])
            evidence = str(payload["evidence"]).strip()

            logger.info(f"[Gemini] Stage:{stage_num} Guide:{'ON' if need_guidance else 'OFF'} | {evidence[:80]}")
        except Exception as e:
            logger.error(f"Gemini stage recognition failed: {e}")
            raise

        return stage_num, need_guidance


def create_gemini_stage_recognizer(config: dict) -> GeminiStageRecognizer:
    return GeminiStageRecognizer(config)
