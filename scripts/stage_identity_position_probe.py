#!/usr/bin/env python3
"""Offline paired current-image probe, removing only stale initial position text."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from c0_poe_resilient_worker import make_client
from core.stage_evidence import parse_observation


def main():
    root=ROOT/'artifacts/stage_closed_loop_20260929'
    out=root/'identity_position_probe_v7_pudding'
    out.mkdir(exist_ok=False)
    source=root/'runs/physical_carry_v7_c0_contract_online_full10/output'
    events=[json.loads(x) for x in (source/'eds_eval/stage_events.jsonl').read_text().splitlines()]
    original='It is the smallest item, positioned behind the orange juice carton (labels 6, 7) and to the left of the BBQ sauce bottle (label 8).'
    replacement='It is the smallest item.'
    requests=[]
    for step in [160,192]:
        event=next(x for x in events if x['task_id']==8 and x['global_step']==step)
        request=source/'captured_stage_inputs'/f'request_{event["validation_attempts"][0]["capture_query_index"]:04d}'
        content=[]
        for part in json.loads((request/'parts.json').read_text()):
            if part['type']=='text':
                content.append(part)
            else:
                content.append(dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode((request/part['file']).read_bytes()).decode())))
        assert sum(p.get('text','').count(original) for p in content)==1
        for group in ['original_identity','appearance_without_initial_position']:
            modified=json.loads(json.dumps(content))
            if group!='original_identity':
                for part in modified:
                    if part['type']=='text':
                        part['text']=part['text'].replace(original,replacement)
            requests.append(dict(step=step,group=group,content=modified,source=str(request.relative_to(ROOT))))
    (out/'intervention.json').write_text(json.dumps(dict(task=8,steps=[160,192],removed=original,inserted=replacement,
        protocol='Two repetitions of each fixed payload, interleaved; replies never enter robot control.'),indent=2)+'\n')
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
            (out/'results.json').write_text(json.dumps(dict(note='Offline semantic diagnostic, not rollout or task success evidence.',results=results),indent=2)+'\n')
            print(json.dumps({k:row.get(k) for k in ['step','group','repeat','valid','observation','elapsed_seconds']}),flush=True)


if __name__=='__main__':
    main()
