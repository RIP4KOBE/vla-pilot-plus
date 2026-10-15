"""Current-frame target identity aid using the controller's existing keypoints.

No grasp, contact, reward, stage, or task-success state enters this annotation.
It never invents visibility for an occluded point or clamps an offscreen point.
"""
import hashlib
from pathlib import Path
import re
import cv2
import numpy as np

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
