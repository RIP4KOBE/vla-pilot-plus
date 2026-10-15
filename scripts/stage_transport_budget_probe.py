#!/usr/bin/env python3
"""Same archived malformed-response input, prospective transport diagnostic."""
import base64
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from c0_poe_resilient_worker import make_client
from core.stage_evidence import parse_observation


def main():
    folder=ROOT/'artifacts/stage_closed_loop_20260929/transport_budget_probe'
    folder.mkdir(exist_ok=False)
    source=ROOT/'artifacts/stage_closed_loop_20260929/runs/proprio_v4_dev389/output/captured_stage_inputs/request_0012'
    parts=json.loads((source/'parts.json').read_text()); content=[]
    for part in parts:
        if part['type']=='text':content.append(part)
        else:content.append(dict(type='image_url',image_url=dict(url='data:image/png;base64,'+
                           base64.b64encode((source/part['file']).read_bytes()).decode())))
    client=make_client(api_key=Path('/home/hynx/.config/vla-pilot/poe-stage-gpu2.key').read_text().strip(),
                       base_url='https://api.poe.com/v1')
    results=[]
    for label,tokens,body in [('default_2048',2048,None),('default_8192',8192,None),
                              ('requested_low_8192',8192,{'reasoning_effort':'low'})]:
        start=time.monotonic();row=dict(label=label,max_tokens=tokens,extra_body=body)
        try:
            kwargs=dict(model='gemini-3-flash',messages=[dict(role='user',content=content)],
                        max_tokens=tokens,temperature=0.)
            if body:kwargs['extra_body']=body
            response=client.chat.completions.create(**kwargs)
            row.update(raw_response=response.choices[0].message.content,
                finish_reason=response.choices[0].finish_reason,model=response.model,
                usage=response.usage.model_dump() if response.usage else None)
            try:row['observation']=parse_observation(row['raw_response']);row['valid']=True
            except Exception as exc:row.update(valid=False,error_type=type(exc).__name__)
        except Exception as exc:row.update(valid=False,error_type=type(exc).__name__)
        row['elapsed_seconds']=time.monotonic()-start;results.append(row)
        (folder/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(row),flush=True)


if __name__=='__main__':main()
