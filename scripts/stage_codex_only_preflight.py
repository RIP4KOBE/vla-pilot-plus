"""Real managed-login Codex image/identity/reward diagnostic, no GPU rollout."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image
from core.c0_reward_contract import audit
from core.gemini_grounder import create_gemini_stage_recognizer
from utils.guidance_utils import load_functions_from_txt
from vlm_query.vlm_agent import VLMAgent


def main():
    destination=ROOT/'artifacts/stage_closed_loop_20260929/codex_only_preflight_v1'
    destination.mkdir(exist_ok=False)
    source=ROOT/'artifacts/stage_closed_loop_20260929/runs/stage_reference_v12_historical_initialization_online_full10/output/episode_1/vlm_agent'
    image=np.array(Image.open(source/'query_img.png').convert('RGB'))
    metadata=json.loads((source/'metadata.json').read_text())
    for key in ('num_stages','stage_names'):metadata.pop(key,None)
    instruction='pick up the alphabet soup and place it in the basket'
    config=dict(backend='codex_cli',model='gpt-6-astra',reasoning_effort='low',
        event_policy='completed_transport_cycles_v6',timeout_seconds=180,transport_retry_count=1,
        query_template_dir=str(ROOT/'vlm_query/c0_contract_v1'),api_key=None,base_url=None)
    report=dict(status='running',purpose='Transport/schema/C0 numeric-contract diagnostic; not a rollout or performance result',
        source_image=str(source/'query_img.png'),model=config['model'],reasoning_effort=config['reasoning_effort'])
    def save():
        (destination/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
    save()
    try:
        agent=VLMAgent(config,base_dir=str(destination),env_type='libero')
        agent.task_dir=str(destination/'reward')
        generated=Path(agent.generate_guidance(image,instruction,metadata))
        functions={s:load_functions_from_txt(generated/f'stage{s}_guidance.txt',validate=False) for s in (1,2)}
        contract=audit(functions,metadata['init_keypoint_positions'],target_index=0)
        (destination/'reward-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
        report.update(reward_contract_valid=contract['valid'],reward_probe_count=contract.get('probe_count'),
                      reward_counter=agent.api_request_counter.snapshot())
        save()
        if not contract['valid']:raise RuntimeError('Fresh Codex reward failed C0 numeric contract')
        observer=create_gemini_stage_recognizer(dict(config,output_format='stage_observation_v1',
            capture_dir=str(destination/'stage_requests'),identity_memory_enabled=True,observation_validation_max_attempts=2))
        observer.set_trace_context({'episode_id':'preflight','task_id':0},'preflight')
        observation=observer.observe_scene(current_rgb=image,instruction=instruction,stage_descriptions='',
            init_img_with_keypoints=image,keypoint_id_to_object=metadata.get('key_points_objects_map',{}))
        report.update(observation=observation,stage_result=observer.last_result,stage_counter=observer.api_request_counter.snapshot())
        if observation is None:raise RuntimeError('Codex visual observation preflight failed')
        report['status']='PASS'
    except Exception as exc:
        report.update(status='FAIL',error_type=type(exc).__name__)
        save()
        raise
    save()


if __name__=='__main__':main()
