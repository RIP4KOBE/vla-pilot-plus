#!/usr/bin/env python3
"""Prospective exact-input API repeats; replies never enter robot control."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from c0_poe_resilient_worker import make_client
from core.stage_evidence import parse_observation


def main():
    artifact = ROOT/'artifacts/stage_closed_loop_20260929'
    out = artifact/'exact_input_repeat_probe_488'
    out.mkdir(exist_ok=False)
    client = make_client(api_key=Path('/home/hynx/.config/vla-pilot/poe-stage-gpu2.key').read_text().strip(),
                         base_url='https://api.poe.com/v1')
    payloads = []
    for run in ['payload_release_v5_c0_contract_online_full10',
                'recovery_priority_v6_c0_contract_online_full10']:
        source = artifact/'runs'/run/'output'
        events = [json.loads(x) for x in (source/'eds_eval/stage_events.jsonl').read_text().splitlines()]
        event = next(x for x in events if x['task_id']==0 and x['global_step']==488)
        request = source/'captured_stage_inputs'/f'request_{event["validation_attempts"][0]["capture_query_index"]:04d}'
        content = []
        for part in json.loads((request/'parts.json').read_text()):
            if part['type']=='text':
                content.append(part)
            else:
                content.append(dict(type='image_url', image_url=dict(url='data:image/png;base64,'+
                    base64.b64encode((request/part['file']).read_bytes()).decode())))
        payloads.append((run, request, content, event['transport']['request_fingerprint']))
    results = []
    for repeat in range(3):
        for run, request, content, fingerprint in payloads:
            row = dict(run=run, repeat=repeat, source=str(request.relative_to(ROOT)), fingerprint=fingerprint,
                       payload_sha256=hashlib.sha256(json.dumps(content,sort_keys=True).encode()).hexdigest())
            start = time.monotonic()
            try:
                response = client.chat.completions.create(model='gemini-3-flash',
                    messages=[dict(role='user',content=content)], max_tokens=8192, temperature=0.)
                row.update(raw_response=response.choices[0].message.content,
                           finish_reason=response.choices[0].finish_reason, response_model=response.model,
                           usage=response.usage.model_dump() if response.usage else None)
                row['observation'] = parse_observation(row['raw_response'])
                row['valid'] = response.choices[0].finish_reason != 'length'
            except Exception as exc:
                row.update(valid=False, error_type=type(exc).__name__)
            row['elapsed_seconds'] = time.monotonic()-start
            results.append(row)
            (out/'results.json').write_text(json.dumps(dict(
                note='Offline exact-input repetitions, not task episodes or performance evidence.',
                model='gemini-3-flash',temperature=0.,max_tokens=8192,results=results),indent=2)+'\n')
            print(json.dumps({k:row.get(k) for k in ['run','repeat','valid','observation','elapsed_seconds']}),flush=True)


if __name__=='__main__':
    main()
