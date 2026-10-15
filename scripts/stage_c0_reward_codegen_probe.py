#!/usr/bin/env python3
"""CPU/API-only fresh code generation under a fixed C0 formula contract."""
import json
import os
from pathlib import Path
import sys
import numpy as np
from PIL import Image
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from c0_poe_fresh_retest import worker_env
from c0_poe_resilient_worker import install
from core.c0_reward_contract import audit
from utils.guidance_utils import load_functions_from_txt
from vlm_query.vlm_agent import VLMAgent


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='canonical_reward_codegen_probe');args=parser.parse_args()
    if not args.name.replace('_','').replace('-','').isalnum():raise ValueError('Invalid output name')
    output=ROOT/'artifacts/stage_closed_loop_20260929'/args.name
    output.mkdir(exist_ok=False)
    environment=worker_env()
    for k in ['OPENAI_API_KEY','GOOGLE_API_KEY','OPENAI_BASE_URL']:os.environ[k]=environment[k]
    install()
    frozen=ROOT/'artifacts/c0_poe_fresh_20260929/outputs/c0_poe_fresh_attempt2'
    config=yaml.safe_load((ROOT/'artifacts/stage_closed_loop_20260929/runs/proprio_v4_fresh_full10_r2/resolved-config.yaml').read_text())['perception']['vlm_agent']
    config.update(query_template_dir=str(ROOT/'vlm_query/c0_contract_v1'),temperature=0.,max_completion_tokens=8192)
    agent=VLMAgent(config,base_dir=str(output),env_type='libero')
    records=[]
    for t,instruction in [(3,'pick up the bbq sauce and place it in the basket'),
                          (8,'pick up the chocolate pudding and place it in the basket'),
                          (9,'pick up the orange juice and place it in the basket')]:
        source=frozen/f'episode_{t+1}/vlm_agent'
        metadata=json.loads((source/'metadata.json').read_text())
        for k in ['num_stages','stage_names']:metadata.pop(k,None)
        agent.task_dir=str(output/f'task_{t}')
        generated=Path(agent.generate_guidance(np.array(Image.open(source/'query_img.png').convert('RGB')),
                                              instruction,metadata))
        functions={s:load_functions_from_txt(generated/f'stage{s}_guidance.txt',validate=False) for s in [1,2]}
        result=audit(functions,metadata['init_keypoint_positions'])
        records.append(dict(task=t,source_image=str(source/'query_img.png'),**result))
        (output/'results.json').write_text(json.dumps(records,indent=2)+'\n')
        print(json.dumps(dict(task=t,valid=result['valid'],reason=result['reason'])),flush=True)


if __name__=='__main__':main()
