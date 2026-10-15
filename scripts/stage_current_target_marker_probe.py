#!/usr/bin/env python3
"""Offline current-target annotation diagnostic using already logged keypoints.

Camera values match this LIBERO floor scene's fixed agentview. This script is
not a runtime controller and never sends its replies into a rollout.
"""
import base64
import hashlib
import json
from pathlib import Path
import sys
import time
import cv2
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from c0_poe_resilient_worker import make_client
from core.stage_evidence import parse_observation


def project(point):
    q=[.6182166934013367,.3432307541370392,.3432314395904541,.6182177066802979]
    rotation=Rotation.from_quat([q[1],q[2],q[3],q[0]]).as_matrix()
    rotation[:,2]*=-1
    camera=rotation.T@(np.asarray(point)-np.array([.8965773716836134,5.216182733499864e-7,.65]))
    assert camera[2]>0
    focal=320/np.tan(np.radians(45)/2)
    return [float(focal*camera[0]/camera[2]+320),float(639-(focal*camera[1]/camera[2]+320))]


def main():
    root=ROOT/'artifacts/stage_closed_loop_20260929'
    out=root/'current_target_marker_probe_v7_pudding'
    out.mkdir(exist_ok=False)
    source=root/'runs/physical_carry_v7_c0_contract_online_full10/output'
    events=[json.loads(x) for x in (source/'eds_eval/stage_events.jsonl').read_text().splitlines()]
    requests=[]
    for step in [160,192]:
        event=next(x for x in events if x['task_id']==8 and x['global_step']==step)
        request=source/'captured_stage_inputs'/f'request_{event["validation_attempts"][0]["capture_query_index"]:04d}'
        point=event['robot_evidence']['geometry']['target_position']
        pixel=project(point)
        content=[]
        for part in json.loads((request/'parts.json').read_text()):
            if part['type']=='text':
                content.append(dict(type='text',text=part['text']+'\nThe magenta circle marked TARGET locates the instructed target using its tracked keypoint in this CURRENT image. It is an identity aid only: it does not prove grasp, visibility, support, containment, or success. Judge visible evidence around that location; use unknown/occluded if hidden. Do not judge a different object left at the target\'s initial location.'))
            else:
                image=cv2.imread(str(request/part['file']))
                assert image.shape[:2]==(640,640)
                x,y=[int(round(v)) for v in pixel]
                cv2.circle(image,(x,y),24,(255,0,255),2)
                cv2.putText(image,'TARGET',(max(0,x-29),max(15,y-30)),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,0,255),2)
                image_path=out/f'step_{step}_current_target.png'
                cv2.imwrite(str(image_path),image)
                content.append(dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode(image_path.read_bytes()).decode())))
        requests.append(dict(step=step,target_world_position=point,target_pixel=pixel,content=content,source=str(request.relative_to(ROOT))))
    client=make_client(api_key=Path('/home/hynx/.config/vla-pilot/poe-stage-gpu2.key').read_text().strip(),base_url='https://api.poe.com/v1')
    results=[]
    for repeat in range(2):
        for request in requests:
            row={k:v for k,v in request.items() if k!='content'}
            row.update(repeat=repeat,payload_sha256=hashlib.sha256(json.dumps(request['content'],sort_keys=True).encode()).hexdigest())
            start=time.monotonic()
            try:
                response=client.chat.completions.create(model='gemini-3-flash',messages=[dict(role='user',content=request['content'])],max_tokens=8192,temperature=0.)
                row.update(raw_response=response.choices[0].message.content,finish_reason=response.choices[0].finish_reason,
                    response_model=response.model,usage=response.usage.model_dump() if response.usage else None)
                row['observation']=parse_observation(row['raw_response'])
                row['valid']=row['finish_reason']!='length'
            except Exception as exc:
                row.update(valid=False,error_type=type(exc).__name__)
            row['elapsed_seconds']=time.monotonic()-start
            results.append(row)
            (out/'results.json').write_text(json.dumps(dict(note='Offline input annotation diagnostic. Current tracked target location added; not an unchanged-input model comparison or a task-success result.',results=results),indent=2)+'\n')
            print(json.dumps({k:row.get(k) for k in ['step','repeat','valid','observation','elapsed_seconds']}),flush=True)


if __name__=='__main__':
    main()
