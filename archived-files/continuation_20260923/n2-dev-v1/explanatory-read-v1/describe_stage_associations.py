"""Exact structured joins in saved output only, no new attempt reader or threshold."""
from pathlib import Path
import hashlib
import json

out=Path(__file__).parent/'output-v1'
source=out/'closed-loop-sequence.json'
data=source.read_bytes()
assert hashlib.sha256(data).hexdigest()=='b8a7c7bce23975ff1f421c7e7cd87eccc7d2517549301f4a81fb34189d1affa4'
arms=[]
for arm in json.loads(data)['arms']:
    by_step={s['global_step']:s for s in arm['actual_steps']}
    rows=[]
    for event in arm['stage_events']:
        previous=[d for d in arm['decisions'] if d['last_executed_step']==event['global_step']-1]
        current=[d for d in arm['decisions'] if d['global_step']==event['global_step']]
        assert len(previous)==len(current)==1
        decision=previous[0]
        first=by_step[decision['global_step']]['command']['value'][6]
        last=by_step[decision['last_executed_step']]['command']['value'][6]
        rows.append({'global_step':event['global_step'],'previous_decision_id':decision['decision_id'],
            'current_decision_id':current[0]['decision_id'],'trigger_reason':event['trigger_reason'],
            'query_status':event['query_status'],'gripper_value_used':event['gripper_value_used'],
            'previous_chunk_first_sent_command':first,'previous_chunk_last_sent_command':last,
            'logged_first_gripper_value':event['first_gripper_value'],
            'logged_last_gripper_value':event['last_gripper_value'],
            'used_matches_first_sent_command':event['gripper_value_used']==first,
            'used_matches_last_sent_command':event['gripper_value_used']==last,
            'same_step_context_agrees':(current[0]['stage'],current[0]['use_guidance'])==(event['stage_after'],event['guidance_after'])})
    arms.append({'arm':arm['arm'],'events':rows,'event_count':len(rows),
        'first_sent_command_mismatch_count':sum(not r['used_matches_first_sent_command'] for r in rows),
        'last_sent_command_mismatch_count':sum(not r['used_matches_last_sent_command'] for r in rows),
        'last_sent_command_mismatch_steps':[r['global_step'] for r in rows if not r['used_matches_last_sent_command']],
        'event_after_state_vs_actual_context_mismatch_count':sum(not r['same_step_context_agrees'] for r in rows)})
report={'input_sha256':hashlib.sha256(data).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope':'already saved structured output; exact numeric comparison, not a new trigger predicate or physical grasp classification',
    'arms':arms}
with (out/'stage-gripper-associations-v1.json').open('x') as f:
    json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
old=out/'findings-v1.md'
text=old.read_text()+'''\nAdditional existing-output join requested by root: all 50 Stage events agree with the same-step actual decision context's stage/guidance state. Logged `gripper_value_used` matches the previous chunk's first **sent** gripper command in C0 28/28, Q0 17/17 and N2 5/5 events. It differs from that previous chunk's last sent gripper command in C0 7/28, Q0 7/17 and N2 1/5 (N2 step 584). Full event joins and mismatch steps are in `stage-gripper-associations-v1.json`. These are exact recorded-value comparisons; they neither reconstruct an alternative trigger nor show that a Stage reply was wrong. Trigger priority can hide other simultaneous predicates, and normalized reward inputs remain unobserved.\n
The initial episode pre-action EEF observation is not in this actual-only motion summary; the first run therefore starts at the first post-action observation and omits that first action's displacement. The complete post-OFF summary has the observed step-23 origin and all 696 consecutive response edges. N2 Stage-0/OFF runs cover 440 actions at 144–583 and 128 actions at 592–719. Neither interval is labeled as a grasp state or a motion-failure category.\n'''
with (out/'findings-v2.md').open('x') as f:f.write(text)
print(json.dumps({'files':{name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['stage-gripper-associations-v1.json','findings-v2.md']},'new_attempt_reads':0}))
