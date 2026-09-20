#!/usr/bin/env python3
"""Visual grounding/stage contracts backed by the Codex account planner.

Legacy class/config names remain readable; production makes no Gemini calls.
"""

import numpy as np
import json
import base64
import hashlib
import os
import io
from typing import List, Dict, Tuple, Optional
from PIL import Image

from utils.logging_utils import SteerLogger
from mode_gate.semantic_planner import _ProviderCallBudget

logger = SteerLogger("AccountVisualPlanner")


def _image_to_base64(rgb: np.ndarray) -> str:
    if rgb.dtype != np.uint8:
        rgb = (rgb * 255).astype(np.uint8) if rgb.max() <= 1.0 else rgb.astype(np.uint8)
    if rgb.ndim == 4:
        rgb = rgb[0]
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


ROBOTICS_MODEL = "gpt-6-astra"


def _make_client(config: dict):
    injected = config.get("client")
    if injected is not None:
        return injected
    from mode_gate.planner_account import CodexPlannerClient
    return CodexPlannerClient()


def _interaction_json(
    client,
    *,
    model: str,
    prompt: str,
    images: list[np.ndarray],
    schema: dict,
    thinking_level: str = "medium",
    provider_budget: _ProviderCallBudget | None = None,
    purpose: str = "gemini_visual",
) -> object:
    content = [{"type": "text", "text": prompt}]
    for image in images:
        content.append(
            {
                "type": "image",
                "data": _image_to_base64(image),
                "mime_type": "image/png",
            }
        )
    if provider_budget is not None:
        provider_budget.reserve(
            model=model,
            prompt_version=f"{purpose}-v1",
            cache_key=hashlib.sha256(
                (prompt + "\0" + str(len(images))).encode()
            ).hexdigest(),
            attempt=0,
            purpose=purpose,
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
        generation_config={"thinking_level": thinking_level},
        store=False,
    )
    output_text = getattr(interaction, "output_text", None)
    if not output_text:
        raise ValueError("Gemini Robotics interaction returned no output_text")
    if getattr(interaction, "planner_metadata", None) is not None:
        client.last_planner_metadata = interaction.planner_metadata
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
        self.thinking_level = str(config.get("thinking_level", "ultra" if self.model == ROBOTICS_MODEL else "medium"))
        self.provider_budget = _ProviderCallBudget(
            max_calls=int(config.get("max_provider_calls", 0)),
            ledger_path=config.get("call_ledger_path"),
        )
        if self.model != ROBOTICS_MODEL and not (config.get("client") is not None and self.model == "gemini-robotics-er-2-preview"):
            raise ValueError(
                f"fixed_budget_10 GeminiGrounder requires {ROBOTICS_MODEL}"
            )
        self.client = _make_client(config)
        logger.info(f"Visual grounder initialized with model: {self.model}")

    def reconfigure_provider_call_budget(
        self, *, max_provider_calls: int, call_ledger_path: str
    ) -> None:
        """Switch run-local accounting without recreating the warm client."""

        self.provider_budget = _ProviderCallBudget(
            max_calls=int(max_provider_calls),
            ledger_path=call_ledger_path,
        )

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
                thinking_level=self.thinking_level,
                provider_budget=self.provider_budget,
                purpose="gemini_grounding",
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
        self.thinking_level = str(config.get("thinking_level", "ultra" if self.model == ROBOTICS_MODEL else "medium"))
        self.provider_budget = _ProviderCallBudget(
            max_calls=int(config.get("max_provider_calls", 0)),
            ledger_path=config.get("call_ledger_path"),
        )
        if self.model != ROBOTICS_MODEL and not (config.get("client") is not None and self.model == "gemini-robotics-er-2-preview"):
            raise ValueError(
                f"fixed_budget_10 GeminiStageRecognizer requires {ROBOTICS_MODEL}"
            )
        self.client = _make_client(config)

        template_path = config.get("stage_template_path")
        if template_path is None:
            import pathlib
            template_path = pathlib.Path(__file__).parent.parent / "vlm_query" / "stage_template.txt"
        with open(template_path, "r") as f:
            self.prompt_template = f.read()

        logger.info(f"Stage recognizer initialized with model: {self.model}")

    def reconfigure_provider_call_budget(
        self, *, max_provider_calls: int, call_ledger_path: str
    ) -> None:
        """Switch run-local accounting without recreating the warm client."""

        self.provider_budget = _ProviderCallBudget(
            max_calls=int(max_provider_calls),
            ledger_path=call_ledger_path,
        )

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
                thinking_level=self.thinking_level,
                provider_budget=self.provider_budget,
                purpose="gemini_stage_recognition",
            )
            stage_num = int(payload["stage_num"])
            if num_stages:
                stage_num = min(stage_num, num_stages)
            need_guidance = bool(payload["need_guidance"])
            evidence = str(payload["evidence"]).strip()

            logger.info(f"[Account planner] Stage:{stage_num} Guide:{'ON' if need_guidance else 'OFF'} | {evidence[:80]}")
        except Exception as e:
            logger.error(f"Account stage recognition failed: {e}")
            raise

        return stage_num, need_guidance


def create_gemini_stage_recognizer(config: dict) -> GeminiStageRecognizer:
    return GeminiStageRecognizer(config)
