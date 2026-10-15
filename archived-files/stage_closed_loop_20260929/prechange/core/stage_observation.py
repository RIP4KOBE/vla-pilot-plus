"""Visual fact contract for evidence_v1; shared Poe transport and request capture."""
from pathlib import Path
import time

from core.gemini_grounder import GeminiStageRecognizer, _image_to_base64
from core.poe_stage_capture import PoeCaptureStageRecognizer
from core.stage_evidence import FORMAT, parse_observation


class ObservationMixin:
    def __init__(self, config):
        config = dict(config)
        config["stage_template_path"] = str(Path(__file__).resolve().parents[1] /
                                              "vlm_query/stage_observation_v1.txt")
        super().__init__(config)
        self.output_format = FORMAT

    def identify_stage_and_guidance(self, **kwargs):
        raise RuntimeError("stage_observation_v1 requires main.stage_controller=evidence_v1")

    def _record_transport_result(self, counter_before):
        super()._record_transport_result(counter_before)
        self._last_result["completion_metadata"] = getattr(self, "_last_completion_metadata", None)

    def observe_scene(self, *, current_rgb, instruction, stage_descriptions,
                      init_img_with_keypoints=None, keypoint_id_to_object=None, trigger_reason=None):
        # Deliberately exclude generated stage descriptions (which contain control
        # directives) and trigger reason (a command is not evidence of a grasp).
        prompt = self.prompt_template.format(
            instruction=instruction,
            keypoint_info="\n".join(f"{k}: {v}" for k, v in (keypoint_id_to_object or {}).items()))
        content = [{"type": "text", "text": prompt}]
        for label, rgb in (("Initial reference only; NOT current state", init_img_with_keypoints),
                           ("Current observation; judge this image", current_rgb)):
            if rgb is not None:
                content.extend([{"type": "text", "text": label}, {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + _image_to_base64(rgb)}}])
        started = time.perf_counter()
        counter = getattr(self, "api_request_counter", None)
        before = counter.snapshot() if counter else None
        raw, observation, error = None, None, None
        self._last_completion_metadata = None
        try:
            raw = self._request_stage_response(content)
            if (self._last_completion_metadata or {}).get("finish_reason") == "length":
                raise ValueError("truncated observation")
            observation = parse_observation(raw)
        except Exception as exc:
            # Keep credentials/HTTP bodies out of logs. Captured transport stores
            # only an exception type; complete malformed replies remain auditable.
            error = type(exc).__name__
        self._last_result = {
            "ok": observation is not None, "parse_ok": observation is not None,
            "raw_response": raw, "observation": observation, "error": error,
            "evidence": observation["evidence"] if observation else "",
            "query_latency_s": time.perf_counter() - started,
        }
        self._record_transport_result(before)
        return observation


class ObservationStageRecognizer(ObservationMixin, GeminiStageRecognizer):
    pass


class CapturedObservationStageRecognizer(ObservationMixin, PoeCaptureStageRecognizer):
    pass
