"""Exactly three prespecified synthetic CPU transport checks; no retries."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
OUT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/analysis/stage-json-live-check')
sys.path.insert(0, str(ROOT))
from core.codex_stage import CodexStageRecognizer
import numpy as np
from PIL import Image, ImageDraw

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

OUT.mkdir(parents=True, exist_ok=False)
plan = json.loads((ROOT / 'data/qd-ed-n1r-post-reboot-plan.json').read_text())
runtime = json.loads(Path(plan['runtime_manifest_path']).read_text())
config = dict(runtime['frozen_stage_provider'])
config['output_format'] = 'json_schema_v1'
config['stage_template_path'] = str(ROOT / 'vlm_query/stage_template.txt')
recognizer = CodexStageRecognizer(config)
images = []
for index in range(3):
    image = Image.new('RGB', (256, 256), '#ddd6c8')
    d = ImageDraw.Draw(image)
    d.rectangle((155, 140, 235, 220), fill='#34884c', outline='black', width=3)
    x, y = [(65, 175), (110, 100), (190, 180)][index]
    d.rectangle((x-14, y-14, x+14, y+14), fill='#cd2424', outline='black', width=2)
    d.line([(x-20, 50), (x-20, y-18), (x-8, y-18)], fill='#454545', width=8)
    d.line([(x+20, 50), (x+20, y-18), (x+8, y-18)], fill='#454545', width=8)
    image.save(OUT / f'input-{index}.png')
    images.append(np.array(image))
manifest = {'created_at': now(), 'source_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
    'code_sha256': {p: sha(ROOT / p) for p in ['core/codex_stage.py','core/codex_stage_policy.py','core/gemini_grounder.py','vlm_query/stage_template.txt']},
    'script_sha256': sha(Path(__file__)), 'input_sha256': [sha(OUT / f'input-{i}.png') for i in range(3)],
    'public_policy': recognizer.public_policy, 'transport': recognizer.transport_metadata,
    'synthetic_only': True, 'gpu_used': False, 'episode_attempts': 0, 'gpu_hours': 0,
    'prespecified_calls': 3, 'retry_allowed': False,
    'instruction': 'Pick up the red block and put it into the green tray.',
    'stage_descriptions': 'Stage 1: reach and grasp the red block.\nStage 2: transport the held block to the green tray and release it.',
    'triggers': ['initial query','gripper closed','gripper opened']}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
def event(value):
    with (OUT / 'events.jsonl').open('a') as f:
        f.write(json.dumps(value) + '\n'); f.flush(); os.fsync(f.fileno())
for i in range(3):
    event({'event':'started', 'index':i, 'at':now()})
    returned = recognizer.identify_stage_and_guidance(current_rgb=images[i], init_img_with_keypoints=images[0],
        instruction=manifest['instruction'], stage_descriptions=manifest['stage_descriptions'],
        keypoint_id_to_object={0:'red block',1:'green tray'}, num_stages=2, trigger_reason=manifest['triggers'][i])
    result = recognizer.last_result
    event({'event':'finished','index':i,'at':now(),'returned':returned,'result':result})
    print(json.dumps({'index':i,'ok':result['ok'],'seconds':result['query_latency_s'],
        'raw_response':result['raw_response'],'logical_calls':result.get('codex_logical_call_attempts'),
        'usage_complete':result.get('codex_usage_complete_calls'),'input_tokens':result.get('codex_input_tokens'),
        'output_tokens':result.get('codex_output_tokens'),'error':result.get('error')}), flush=True)
    if not result['ok'] or result.get('codex_usage_complete_calls') != 1:
        (OUT / 'result.json').write_text(json.dumps({'status':'FAILED_STOPPED','finished':i+1,'counter':recognizer.api_request_counter.snapshot()},indent=2))
        raise SystemExit(1)
(OUT / 'result.json').write_text(json.dumps({'status':'PASSED','finished':3,'counter':recognizer.api_request_counter.snapshot()},indent=2))
