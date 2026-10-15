from types import SimpleNamespace
import hashlib
import cv2
import numpy as np
import pytest
from core.stage_target_marker import annotate, save_raw_frame


def runner():
    camera=SimpleNamespace(width=100,height=100,intrinsic=np.array([[100.,0,50],[0,100,50],[0,0,1]]),extrinsic=np.eye(4))
    adapter=SimpleNamespace(_env_config={'vlm_camera':'agentview'},get_camera_params=lambda name:camera,
        get_task_description=lambda:'pick up the chocolate pudding and place it in the basket')
    return SimpleNamespace(backend='libero',adapter=adapter,keypoint_id_to_object={0:'chocolate_pudding_1_main',1:'basket_1_main'},
                           stage_live_keypoints=np.array([[0.,0.,1.],[.5,.4,1.]]))


def test_projects_current_keypoints_with_vertical_image_flip_without_mutation():
    r=runner();raw=np.zeros((100,100,3),dtype=np.uint8);original=raw.copy();kp=r.stage_live_keypoints.copy()
    marked,metadata=annotate(r,raw)
    assert metadata['target_pixel']==[50.,49.] and metadata['status']=='drawn'
    assert np.array_equal(raw,original) and np.array_equal(r.stage_live_keypoints,kp)
    assert not np.array_equal(marked,raw)
    assert metadata['raw_rgb_sha256']==hashlib.sha256(raw.tobytes()).hexdigest()
    r.stage_live_keypoints[0,0]=.1
    _,new=annotate(r,raw)
    assert new['target_pixel']==[60.,49.]


@pytest.mark.parametrize('point,status', [([0,0,-1],'behind_camera'),([2,0,1],'outside_image')])
def test_does_not_clamp_invisible_target_into_frame(point,status):
    r=runner();r.stage_live_keypoints[0]=point;raw=np.zeros((100,100,3),dtype=np.uint8)
    marked,metadata=annotate(r,raw)
    assert metadata['status']==status and np.array_equal(marked,raw)


def test_uses_mean_of_target_points_and_excludes_basket():
    r=runner();r.keypoint_id_to_object[2]='chocolate_pudding_1_main'
    r.stage_live_keypoints=np.array([[0.,0.,1.],[.5,.4,1.],[.2,0,1.]])
    _,metadata=annotate(r,np.zeros((100,100,3),dtype=np.uint8))
    assert metadata['target_keypoint_indices']==[0,2]
    assert metadata['target_pixel']==[60.,49.]


@pytest.mark.parametrize('problem', ['resolution','nonfinite','mapping','backend'])
def test_invalid_geometry_and_configuration_fail_closed(problem):
    r=runner();raw=np.zeros((100,100,3),dtype=np.uint8)
    if problem=='resolution':raw=np.zeros((50,50,3),dtype=np.uint8)
    if problem=='nonfinite':r.stage_live_keypoints[0,0]=np.nan
    if problem=='mapping':r.keypoint_id_to_object={5:'chocolate_pudding_1_main'}
    if problem=='backend':r.backend='different'
    with pytest.raises(ValueError):annotate(r,raw)


def test_retains_unmarked_rgb_and_rejects_overwrite(tmp_path):
    raw=np.zeros((100,100,3),dtype=np.uint8);raw[:,:,0]=101;raw[:,:,2]=23
    metadata=save_raw_frame(tmp_path,dict(episode_id=8,global_step=160),raw,{})
    actual=cv2.cvtColor(cv2.imread(metadata['raw_png_path']),cv2.COLOR_BGR2RGB)
    assert np.array_equal(actual,raw)
    with pytest.raises(RuntimeError):save_raw_frame(tmp_path,dict(episode_id=8,global_step=160),raw,{})
