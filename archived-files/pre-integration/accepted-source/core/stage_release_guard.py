"""Prospective payload-based release permission and bounded open-command dwell.

The existing controller tests hand-center alignment. A carried object may be
above the basket even when its hand center is outside that region. This helper
uses the existing tracked object keypoints, never a success/contact predicate.
It does not initiate a release: the learned policy must first request OPEN.
"""
import re
import numpy as np


def payload_geometry(runner):
    match=re.search(r'pick up (?:the )?(.+?) and place',runner.adapter.get_task_description().lower())
    if not match:return None
    target=match.group(1).replace(' ','_')
    mapping=runner.keypoint_id_to_object
    ids=[int(k) for k,v in mapping.items() if str(v).lower().startswith(target+'_')]
    basket=[int(k) for k,v in mapping.items() if 'basket' in str(v).lower()]
    if not ids or len(basket)<2:return None
    points=np.asarray(runner.stage_live_keypoints,dtype=float)
    if not np.isfinite(points[ids+basket]).all():return None
    destination=points[basket]
    return dict(target_position=points[ids].mean(0).tolist(),goal_low=destination.min(0).tolist(),
                goal_high=destination.max(0).tolist())


def aligned_payload(geometry, margin=.005):
    if geometry is None:return False
    target=np.asarray(geometry['target_position']);low=np.asarray(geometry['goal_low']);high=np.asarray(geometry['goal_high'])
    if not np.isfinite(np.r_[target,low,high]).all():return False
    # Do not treat a basket moved across a tabletop target as a carrying/release
    # situation. Sparse surface keypoints only approximate the basket bounds.
    minimum_height=max(low[2]+.04,high[2]-.035)
    return bool(np.all(target[:2]>=low[:2]+margin) and np.all(target[:2]<=high[:2]-margin)
                and target[2]>=minimum_height)


def apply(state, raw, guarded, reason, *, step, width, distance, geometry, config):
    until=state.get('payload_release_until')
    if until is not None and step<until:
        return -1.,'complete_policy_requested_payload_release'
    aligned=aligned_payload(geometry,float(config.get('payload_release_margin_m',.005)))
    plausible_carry=(state.get('current_stage')==2 and state.get('visual_hold')
                     and width is not None and .005<width<.075
                     and distance is not None and distance<.12)
    if raw<0 and aligned and plausible_carry:
        dwell=int(config.get('payload_release_dwell_steps',8))
        if not 1<=dwell<=16:raise ValueError('payload release dwell must be 1..16 steps')
        state['payload_release_until']=step+dwell
        return -1.,'allow_policy_release_payload_over_destination'
    return guarded,reason
