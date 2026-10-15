#!/usr/bin/env python3
"""Diagnostic only: saved, label-free images; new Poe observations; no rollout."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.gemini_grounder import create_gemini_stage_recognizer
from core.stage_evidence import assess_reward, decide, parse_observation
from utils.guidance_utils import load_functions_from_txt

FRESH = ROOT/'artifacts/c0_poe_fresh_20260929/outputs/c0_poe_fresh_attempt2'
OLD = ROOT/'artifacts/c0_online_stage_diagnostic_20260928/captured_stage_inputs'
OUT = ROOT/'artifacts/stage_consistency_20260929'


def reward_audit():
    result = []
    for task in range(10):
        folder = FRESH/f'episode_{task+1}/vlm_agent'
        metadata = json.loads((folder/'metadata.json').read_text())
        for stage in (1, 2):
            path = folder/f'stage{stage}_guidance.txt'
            fns = load_functions_from_txt(path, validate=False)
            capability = assess_reward(fns, metadata['init_keypoint_positions'])
            result.append(dict(task_id=task, stage=stage, source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                               **capability))
    (OUT/'reward-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def online(label):
    from c0_poe_resilient_worker import install
    install()
    output = OUT/label
    output.mkdir(exist_ok=True)
    # Resume local reporting failures from already saved complete replies; do
    # not call the provider twice to select a more favorable semantic answer.
    captures = sorted(output.glob('captured_inputs*/request_*/metadata.json'))
    recognizer = create_gemini_stage_recognizer(dict(
        api_key=Path('/home/hynx/.config/vla-pilot/poe-stage-gpu2.key').read_text().strip(),
        base_url='https://api.poe.com/v1', model='gemini-3-flash',
        output_format='stage_observation_v1', capture_dir=str(output/('captured_inputs' if not captures else f'captured_inputs_resume{len(captures)}'))))
    fresh_inputs = FRESH/'captured_stage_inputs'
    cases = [(fresh_inputs, i) for i in (0, 53, 54, 94)] + [(OLD, i) for i in (33, 116, 126)]
    rows = []
    for case_index, (folder, index) in enumerate(cases):
        request = folder/f'request_{index:04d}'
        prompt = '\n'.join(p['text'] for p in json.loads((request/'parts.json').read_text()) if p['type']=='text')
        instruction = re.search(r'\*\*Task Instruction:\*\*\s*([^\n]+)', prompt).group(1)
        mapping = dict((int(k), value.strip()) for k, value in re.findall(r'Keypoint (\d+): ([^\n]+)', prompt))
        metadata = json.loads((request/'metadata.json').read_text())
        recognizer.set_trace_context(metadata['context'], 'offline image check')
        if case_index < len(captures):
            saved = json.loads(captures[case_index].read_text())
            assert saved['context']['task_id'] == metadata['context']['task_id']
            assert saved['context']['global_step'] == metadata['context']['global_step']
            raw = saved.get('raw_response')
            try:
                observation = parse_observation(raw)
                result = dict(ok=True, observation=observation, raw_response=raw, resumed_saved_reply=True)
            except (ValueError, TypeError):
                observation = None
                result = dict(ok=False, observation=None, raw_response=raw, resumed_saved_reply=True)
        else:
            observation = recognizer.observe_scene(
                current_rgb=np.array(Image.open(request/'image_02.png').convert('RGB')),
                init_img_with_keypoints=np.array(Image.open(request/'image_01.png').convert('RGB')),
                instruction=instruction, stage_descriptions='', keypoint_id_to_object=mapping,
                trigger_reason='offline image check')
            result = recognizer.last_result
        # One observation per case: no duplicate frame used as temporal confirmation.
        state = {'current_stage': 1, 'use_guidance': True}
        decision = decide(state, observation, 0) if observation else 'invalid_observation'
        row = dict(input=str(request.relative_to(ROOT)), input_image_sha256=hashlib.sha256((request/'image_02.png').read_bytes()).hexdigest(),
                   context=metadata['context'], decision=decision,
                   resulting_state=state, **result)
        rows.append(row)
        (output/'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(dict(input=row['input'], observation=observation, decision=decision), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('reward', 'online'))
    parser.add_argument('--label', default='offline_model_tokens2048')
    args = parser.parse_args()
    action = args.action
    if action == 'reward':
        print(json.dumps(reward_audit(), indent=2))
    else:
        online(args.label)
