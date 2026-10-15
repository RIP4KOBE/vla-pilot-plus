#!/usr/bin/env python3
"""Archived-image diagnostic. Replies are never replayed into robot control."""
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from c0_poe_resilient_worker import install
from core.gemini_grounder import _image_to_base64
from core.stage_observation import CapturedObservationStageRecognizer


def run():
    out=ROOT/'artifacts/stage_closed_loop_20260929/identity_memory_probe'
    out.mkdir(exist_ok=False)
    install()
    observer=CapturedObservationStageRecognizer(dict(
        api_key=Path('/home/hynx/.config/vla-pilot/poe-stage-gpu2.key').read_text().strip(),
        base_url='https://api.poe.com/v1',model='gemini-3-flash',output_format='stage_observation_v1',
        capture_dir=str(out/'requests')))
    source=ROOT/'artifacts/stage_closed_loop_20260929/runs/grasp_v3_dev389/output/captured_stage_inputs'
    initial=np.array(Image.open(source/'request_0000/image_01.png').convert('RGB'))
    question=('Identify only the instructed target: pick up the bbq sauce and place it in the basket. '
        'The marked point 0 belongs to bbq_sauce_1_main. Describe this exact object by visible shape, '
        'colors, label and size, so it can be recognized in another camera frame. '
        'Do not describe robot actions or infer any current grasp or task success. Use under 100 words.')
    identity=observer._request_stage_response([dict(type='text',text=question),
        dict(type='image_url',image_url=dict(url='data:image/png;base64,'+_image_to_base64(initial)))])
    (out/'identity.txt').write_text(identity)
    result=[]
    for i in (5,11,20,29):
        folder=source/f'request_{i:04d}'
        metadata=json.loads((folder/'metadata.json').read_text())
        observer.set_trace_context(metadata['context'],'offline_identity_memory_probe')
        observation=observer.observe_scene(current_rgb=np.array(Image.open(folder/'image_02.png').convert('RGB')),
            instruction='pick up the bbq sauce and place it in the basket. Target identity from initial reference: '+identity,
            stage_descriptions='',init_img_with_keypoints=None,keypoint_id_to_object={})
        result.append(dict(source=str(folder.relative_to(ROOT)),context=metadata['context'],
            original_response=metadata['raw_response'],observation=observation,result=observer.last_result))
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(index=i,observation=observation)),flush=True)


if __name__=='__main__':run()
