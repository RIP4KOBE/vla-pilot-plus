#!/usr/bin/env python3
"""Post-hoc geometric proxies for pick/place failure; no rollout changes."""
import argparse
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]/'artifacts/stage_closed_loop_20260929/runs'


def diagnose(name):
    folder=ROOT/name
    events=[json.loads(x) for x in (folder/'output/eds_eval/stage_events.jsonl').read_text().splitlines()]
    tasks=[]
    for task in sorted({x['task_id'] for x in events}):
        rows=[x for x in events if x['task_id']==task]
        points=[(x,(x.get('robot_evidence') or {}).get('geometry')) for x in rows]
        points=[(x,g) for x,g in points if g]
        if not points:continue
        base=points[0][1]['target_position'][2]
        lifted=[];held=[];inside=[];comove=[]
        previous=None
        for x,g in points:
            step=x['global_step'];p=np.array(g['target_position']);width=x['gripper_width_m'];dist=x['target_distance_m']
            if p[2]-base>.03:lifted.append(step)
            if p[2]-base>.03 and .005<width<.075 and dist<.10:held.append(step)
            low,high=np.array(g['goal_xy_low']),np.array(g['goal_xy_high'])
            if np.all(p[:2]>=low) and np.all(p[:2]<=high):inside.append(step)
        target_positions=np.array([g['target_position'] for _,g in points])
        goal_positions=np.array([(np.array(g['goal_xy_low'])+np.array(g['goal_xy_high']))/2 for _,g in points])
        target_goal_dist=np.linalg.norm(target_positions[:,:2]-goal_positions,axis=1)
        lift_width_close_set=set(held)
        contradictions=[x['global_step'] for x,g in points if x['global_step'] in lift_width_close_set
            and (x.get('observation') or {}).get('grasp')=='not_held']
        tasks.append(dict(task=task,chunks=len(rows),lifted_steps=lifted,
            lifted_nonempty_near_hand_steps=held,target_in_goal_xy_steps=inside,
            visual_not_held_despite_lift_nonempty_near_hand_steps=contradictions,
            maximum_target_lift_m=float(target_positions[:,2].max()-base),
            minimum_target_goal_xy_distance_m=float(target_goal_dist.min()),
            goal_xy_displacement_m=float(np.linalg.norm(goal_positions-goal_positions[0],axis=1).max()),
            stage2_chunks=sum(x['stage_after']==2 for x in rows),
            stage2_guided_chunks=sum(x['stage_after']==2 and x['guidance_after'] for x in rows)))
    result=dict(run=name,note='Diagnostic proxies from existing tracked keypoints and finger qpos, not simulator grasp truth; 3 cm lift is a fixed diagnostic threshold, not a controller.',tasks=tasks)
    (folder/'motion-diagnostic.json').write_text(json.dumps(result,indent=2)+'\n')
    for x in tasks:
        print(x['task'],'lifted',len(x['lifted_steps']),'grasp_proxy',len(x['lifted_nonempty_near_hand_steps']),
              'goal_xy',len(x['target_in_goal_xy_steps']),'max_lift',round(x['maximum_target_lift_m'],3),
              'closest_xy',round(x['minimum_target_goal_xy_distance_m'],3),'basket_motion',round(x['goal_xy_displacement_m'],3),
              'negative_VLM',x['visual_not_held_despite_lift_nonempty_near_hand_steps'])
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');diagnose(p.parse_args().name)
