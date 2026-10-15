"""Post-episode evidence extraction only; never edits science or labels a visual review done."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import cv2

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('task', type=int)
parser.add_argument('--frames', type=int, nargs='*', default=[])
args = parser.parse_args()
task = args.task
art = Path('artifacts/stage_closed_loop_20260929/runs')
folder = art/'codex_failed_contact_v17_historical_initialization_online_full10'
parent = art/'codex_fused_carry_v16_historical_initialization_online_full10'
out = folder/'output'


def rows(path):
    result = []
    lines = path.read_text().splitlines()
    for index,line in enumerate(lines):
        try: result.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines)-1: raise
    return result


events = [x for x in rows(out/'eds_eval/stage_events.jsonl') if x['task_id'] == task]
actions = [x for x in rows(out/'eds_eval/safety_events.jsonl') if x['task_id'] == task]
metrics = [x for x in rows(out/'eds_eval/eds_metrics.jsonl') if x['task_id'] == task]
computed = [x for x in rows(out/'eds_eval/episode_compute.jsonl') if x['task_id'] == task]
assert len(computed) == 1 and computed[0]['outcome'] == 'completed', 'Episode not complete'
reference = [x for x in rows(parent/'output/eds_eval/safety_events.jsonl') if x['task_id'] == task]
by_step = {x['global_step']:x for x in reference}
different = [x['global_step'] for x in actions if x['global_step'] in by_step
             and x['raw_action'] != by_step[x['global_step']]['raw_action']]
videos = list((out/f'episode_{task+1}').glob('*agentview.mp4'))
old_videos = list((parent/f'output/episode_{task+1}').glob('*agentview.mp4'))
assert len(videos) == len(old_videos) == 1
video,old_video = videos[0],old_videos[0]
review = folder/f'video-review/episode_{task:03d}'
review.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture(str(video))
count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
assert count == len(actions) and count > 0
extracted = []
for step in sorted(set([count-1, *args.frames])):
    assert 0 <= step < count
    cap.set(cv2.CAP_PROP_POS_FRAMES,step)
    ok,frame = cap.read()
    assert ok
    path = review/f'frame_{step:06d}.png'
    assert cv2.imwrite(str(path),frame)
    extracted.append(str(path))
cap.release()
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
centers = [[(e['robot_evidence']['geometry']['goal_xy_low'][i]+e['robot_evidence']['geometry']['goal_xy_high'][i])/2
            for i in range(2)] for e in events]
result = dict(utc=datetime.now(timezone.utc).isoformat(),task_id=task,episode_complete=True,
    environment_success='_success_' in video.name,actions=len(actions),parent_actions=len(reference),
    first_shared_action_difference_vs_v16=different[0] if different else None,
    stage_queries=sum(e['query_status']=='ok' for e in events),
    guided_chunks=sum(bool(e['guidance_after']) for e in events),
    stage2_chunks=sum(e['stage_after']==2 for e in events),
    fused_hold_steps=[e['global_step'] for e in events if e.get('fused_hold_established')],
    failed_contact_recoveries=[dict(step=e['global_step'],trace=e['failed_contact_recheck'])
        for e in events if (e.get('failed_contact_recheck') or {}).get('confirmed')],
    episode_checks=dict(native_actions_preserved=all(len(e['raw_action'])==7 and e['raw_action']==e['executed_action'] and not e['override'] for e in actions),
        all_native_actions_equal_v16=len(actions)==len(reference) and not different,
        full_encoded_video_equal_v16=digest(video)==digest(old_video),
        all_stage_queries_completed=all(e['error'] is None and (e['query_status']!='ok' or e['query_ok'] is True) for e in events),
        ED_steps_match_gate={e['global_step'] for e in events if e['guidance_after']}=={e['global_step'] for e in metrics},
        no_unavailable_reward_guided=all(e['reward_capability']['available'] for e in events if e['guidance_after'])),
    provider={k:computed[0][k] for k in ['provider_completed_turns','provider_failed_calls','provider_input_tokens','provider_output_tokens']},
    video_fingerprint=dict(frame_count=count,video_sha256=digest(video),v16_video_sha256=digest(old_video)),
    sampled_goal_xy_midpoint_max_displacement_m=max(math.dist(c,centers[0]) for c in centers),
    extracted_frames=extracted,visual_review_pending=True,full_cohort_audit_pending=True,
    final_fresh_observation=next(e['observation'] for e in events[::-1] if e['query_status']=='ok'),
    no_counterfactual_success_claim=True)
(review/'mechanical-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
