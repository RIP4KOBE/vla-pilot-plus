"""Numerical audit for the historical C0 reaching objective.

Finite probes detect known formula drift; they are not a proof over every input.
No stored historical function or Stage reply is read by this implementation.
"""
import random
import numpy as np
import torch


def validate_task(runner, keypoints, episode_dir):
    """Opt-in preparation gate; save rejected programs, never silently replace."""
    import json
    import re
    from pathlib import Path
    match=re.search(r'pick up (?:the )?(.+?) and place',runner.adapter.get_task_description().lower())
    target=match.group(1).replace(' ','_') if match else None
    indices=sorted(int(k) for k,v in runner.keypoint_id_to_object.items()
                   if target and str(v).lower().startswith(target+'_'))
    if not indices:
        result=dict(valid=False,reason='target_identity_unresolved')
    else:
        result=audit(runner.guidance_fns,keypoints,target_index=indices[0])
        result['target_index']=indices[0]
    result['contract']='c0_xyz_v1'
    path=Path(episode_dir)/'vlm_agent/c0_reward_contract.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n')
    if not result['valid']:
        raise ValueError('Generated reward violates c0_xyz_v1: '+result['reason'])
    return result


def reference(keypoints, trajectory, target_index):
    # Match the historical operation order and float32 temporal weights. With
    # bfloat16 trajectories, norm(...).square() differs from square().sum().
    horizon=trajectory.shape[1]
    times=torch.arange(horizon,device=trajectory.device)
    weights=torch.where(times>=int(.7*horizon),torch.tensor(3.,device=trajectory.device),
                        torch.tensor(1.,device=trajectory.device))
    weights=weights/weights.sum()
    distances=torch.norm(trajectory-keypoints[target_index],dim=-1)
    return -(distances.square()*weights).sum(-1).mean()


def audit(functions, keypoints, target_index=0):
    """CPU probes in float32 and actual bfloat16 execution input precision."""
    kp=torch.as_tensor(keypoints,dtype=torch.float32,device='cpu')
    if kp.ndim!=2 or kp.shape[1]!=3 or not torch.isfinite(kp).all() or not 0<=target_index<len(kp):
        return dict(valid=False,reason='invalid_keypoints')
    if set(functions)!={1,2}:
        return dict(valid=False,reason='requires_two_stages')
    generator=torch.Generator(device='cpu').manual_seed(81937)
    checks=[]
    python_state,np_state=random.getstate(),np.random.get_state()
    try:
        with torch.no_grad(),torch.random.fork_rng(devices=[]):
            for dtype in [torch.float32,torch.bfloat16]:
                for translation in [torch.zeros(3),torch.tensor([.21,-.13,.08])]:
                    points=(kp+translation).to(dtype)
                    for batch in [1,3]:
                        for horizon in [4,7,8,16]:
                            samples=(points[target_index].float()+torch.randn((batch,horizon,3),generator=generator)*.15).to(dtype)
                            for stage in [1,2]:
                                expected=float(reference(points,samples,target_index)) if stage==1 else 0.
                                actual=[]
                                for _ in range(2):
                                    total=0.
                                    for fn in functions[stage]:
                                        value=torch.as_tensor(fn(points.clone(),samples.clone()))
                                        if value.numel()!=1 or not torch.isfinite(value).all():
                                            return dict(valid=False,reason='invalid_output',stage=stage)
                                        total+=float(value)
                                    actual.append(total)
                                if actual[0]!=actual[1]:
                                    return dict(valid=False,reason='non_deterministic',stage=stage)
                                difference=abs(actual[0]-expected)
                                tolerance=1e-6+1e-5*abs(expected)
                                checks.append(dict(stage=stage,batch=batch,horizon=horizon,dtype=str(dtype),
                                    expected=expected,actual=actual[0],absolute_difference=difference,
                                    consistent=difference<=tolerance))
    except Exception as exc:
        return dict(valid=False,reason='probe_exception',error_type=type(exc).__name__,checks=checks)
    finally:
        random.setstate(python_state)
        np.random.set_state(np_state)
    return dict(valid=all(x['consistent'] for x in checks),
        reason='consistent_on_probes' if all(x['consistent'] for x in checks) else 'formula_drift',
        probe_count=len(checks),max_absolute_difference=max(x['absolute_difference'] for x in checks),checks=checks)
