"""Current-frame observations, target identity and image annotation."""


import hashlib
from pathlib import Path
import re
import cv2
import numpy as np
import time
from core.gemini_grounder import GeminiStageRecognizer, _image_to_base64
from core.online.capture import CapturedStageRecognizer
from core.stage.controller import FORMAT
from core.stage.contract import request_validated, ObservationValidationError
from core.online.codex import CodexVisionTransport


def identify(observer, *, instruction, initial_image, mapping):
    from core.gemini_grounder import _image_to_base64
    if initial_image is None:
        raise ValueError('identity memory requires the actual initial reference image')
    context = getattr(observer, 'context', {})
    image_hash = hashlib.sha256(initial_image.tobytes()).hexdigest()
    key = (context.get('episode_id'), context.get('task_id'), instruction, image_hash)
    if getattr(observer, '_identity_memory_key', None) == key:
        return observer._identity_memory, False
    labels = '\n'.join(f'{k}: {v}' for k, v in mapping.items())
    prompt = ('Identify only the instructed target object. Task: '+instruction+'\n'
              'The initial image is annotated with these object keypoint labels:\n'+labels+'\n'
              'Describe the exact target by visible shape, colors, label and size so it can be '
              'recognized in another camera frame. Distinguish it from neighboring distractors. '
              'Do not describe robot actions or infer any current grasp or task success. '
              'Do not give commands or control decisions. Use under 100 words.')
    description = observer._request_stage_response([dict(type='text',text=prompt),
        dict(type='image_url',image_url=dict(url='data:image/png;base64,'+_image_to_base64(initial_image)))])
    if (observer._last_completion_metadata or {}).get('finish_reason') == 'length':
        raise ValueError('truncated identity description')
    if not isinstance(description,str) or not description.strip() or len(description)>2400:
        raise ValueError('invalid identity description')
    observer._identity_memory_key = key
    observer._identity_memory = description
    return description, True


PROMPT = ("The magenta circle marked TARGET locates the instructed target using its tracked keypoint "
    "in this CURRENT image. It is an identity aid only: it does not prove grasp, visibility, support, "
    "containment, or success. Judge visible evidence around that location; use unknown/occluded if "
    "hidden. Do not judge a different object left at the target's initial location. A point outside "
    "this image is not drawn; absence of a marker is not evidence of task completion.")


def annotate(runner, image):
    if runner.backend != 'libero':
        raise ValueError('Current-target marker currently supports the verified LIBERO camera convention')
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError('Marker requires a uint8 RGB frame')
    match=re.search(r'pick up (?:the )?(.+?) and place',runner.adapter.get_task_description().lower())
    if not match:
        raise ValueError('Cannot identify instructed target')
    target=match.group(1).replace(' ','_')
    indices=sorted(int(k) for k,v in runner.keypoint_id_to_object.items()
        if str(v).lower()==target or str(v).lower().startswith(target+'_'))
    points=np.asarray(runner.stage_live_keypoints,dtype=float)
    if not indices or min(indices)<0 or max(indices)>=len(points):
        raise ValueError('Target keypoint mapping is invalid')
    position=points[indices].mean(axis=0)
    camera_name=runner.adapter._env_config.get('vlm_camera','agentview')
    camera=runner.adapter.get_camera_params(camera_name)
    height,width=image.shape[:2]
    if (camera.width,camera.height)!=(width,height):
        raise ValueError('Camera calibration resolution differs from current image')
    intrinsic=np.asarray(camera.intrinsic,dtype=float)
    extrinsic=np.asarray(camera.extrinsic,dtype=float)
    if intrinsic.shape!=(3,3) or extrinsic.shape!=(4,4) or not all(np.isfinite(x).all() for x in (position,intrinsic,extrinsic)):
        raise ValueError('Nonfinite or invalid camera/keypoint data')
    camera_point=(extrinsic@np.r_[position,1.])[:3]
    pixel=None
    status='behind_camera'
    result=image.copy()
    if camera_point[2]>1e-6:
        projection=intrinsic@camera_point
        pixel=[float(projection[0]/projection[2]),float(height-1-projection[1]/projection[2])]
        x,y=pixel
        status='outside_image'
        if 0<=x<width and 0<=y<height:
            center=(int(round(x)),int(round(y)))
            cv2.circle(result,center,24,(255,0,255),2)
            cv2.putText(result,'TARGET',(max(0,center[0]-29),max(15,center[1]-30)),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,0,255),2)
            status='drawn'
    metadata=dict(schema='stage_current_target_marker_v1',status=status,camera=camera_name,
        target_keypoint_indices=indices,target_world_position=position.tolist(),target_pixel=pixel,
        camera_intrinsic=intrinsic.tolist(),camera_extrinsic=extrinsic.tolist(),
        camera_depth=float(camera_point[2]),image_width=width,image_height=height,
        raw_rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest(),marked_rgb_sha256=hashlib.sha256(result.tobytes()).hexdigest())
    return result,metadata


def save_raw_frame(output_dir, state, raw, metadata):
    folder=Path(output_dir)/'stage_unmarked_frames'/f"episode_{int(state['episode_id']):03d}"
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/f"step_{int(state['global_step']):06d}.png"
    if path.exists():
        raise RuntimeError('Never overwrite a recorded current frame')
    if not cv2.imwrite(str(path),cv2.cvtColor(raw,cv2.COLOR_RGB2BGR)):
        raise RuntimeError('Failed to save current-frame comparison evidence')
    metadata['raw_png_path']=str(path)
    metadata['raw_png_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    return metadata


class ObservationMixin:
    def __init__(self, config):
        config = dict(config)
        config["stage_template_path"] = str(Path(__file__).resolve().parents[2] /
                                              "vlm_query/stage_observation_v1.txt")
        super().__init__(config)
        self.output_format = FORMAT

    def identify_stage_and_guidance(self, **kwargs):
        raise RuntimeError("stage_observation_v1 requires main.stage_controller=evidence")

    def _record_transport_result(self, counter_before):
        super()._record_transport_result(counter_before)
        self._last_result["completion_metadata"] = getattr(self, "_last_completion_metadata", None)

    def observe_scene(self, *, current_rgb, instruction, stage_descriptions,
                      init_img_with_keypoints=None, keypoint_id_to_object=None, trigger_reason=None,
                      current_target_marker=None):
        # Deliberately exclude generated stage descriptions (which contain control
        # directives) and trigger reason (a command is not evidence of a grasp).
        started = time.perf_counter()
        counter = getattr(self, "api_request_counter", None)
        before = counter.snapshot() if counter else None
        raw, observation, error = None, None, None
        identity, identity_generated = None, False
        validation_attempts = []
        self._last_completion_metadata = None
        try:
            reference = init_img_with_keypoints
            if self.config.get('identity_memory_enabled', False):
                identity, identity_generated = identify(self, instruction=instruction,
                    initial_image=init_img_with_keypoints, mapping=keypoint_id_to_object or {})
                instruction += '\nTarget appearance from the initial reference (identity only): '+identity
                reference = None  # Avoid mixing old and current robot poses.
            prompt = self.prompt_template.format(
                instruction=instruction,
                keypoint_info="\n".join(f"{k}: {v}" for k, v in (keypoint_id_to_object or {}).items()))
            if current_target_marker is not None:
                if current_target_marker.get('schema') != 'stage_current_target_marker_v1':
                    raise ValueError('Unrecognized current target marker metadata')
                prompt += '\n' + PROMPT
            content = [{"type": "text", "text": prompt}]
            for label, rgb in (("Initial reference only; NOT current state", reference),
                               ("Current observation; judge this image", current_rgb)):
                if rgb is not None:
                    content.extend([{"type": "text", "text": label}, {"type": "image_url", "image_url": {
                        "url": "data:image/png;base64," + _image_to_base64(rgb)}}])
            raw, observation, validation_attempts = request_validated(self, content,
                self.config.get('observation_validation_max_attempts', 1))
        except Exception as exc:
            # Keep credentials/HTTP bodies out of logs. Captured transport stores
            # only an exception type; complete malformed replies remain auditable.
            error = type(exc).__name__
            if isinstance(exc, ObservationValidationError):
                validation_attempts = exc.attempts
                raw = validation_attempts[-1]['raw_response']
        self._last_result = {
            "ok": observation is not None, "parse_ok": observation is not None,
            "raw_response": raw, "observation": observation, "error": error,
            "evidence": observation["evidence"] if observation else "",
            "query_latency_s": time.perf_counter() - started,
            "identity_memory": identity, "identity_generated_this_query": identity_generated,
            "validation_attempts": validation_attempts,
            "observation_validation_retries": max(0, len(validation_attempts)-1),
            "current_target_marker": current_target_marker,
        }
        self._record_transport_result(before)
        return observation


class ObservationStageRecognizer(ObservationMixin, GeminiStageRecognizer):
    pass


class CapturedObservationStageRecognizer(ObservationMixin, CapturedStageRecognizer):
    pass


class CodexObservationStageRecognizer(ObservationMixin, CodexVisionTransport):
    pass
