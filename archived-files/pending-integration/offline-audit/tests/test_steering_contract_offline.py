"""CPU-only in-memory mutations of saved run evidence. Never changes run artifacts."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from test_steering_transport_audit import recovery

from steering_audit_fixture import materialize
from scripts.audit_steering_contract import main as audit_cli_main
DRAFT = Path(__file__).parents[1] / 'scripts' / 'audit_steering_contract.py'
READ, EXISTS = Path.read_bytes, Path.exists

def encoded(value):
    return json.dumps(value).encode()

def mutate(case, path, root):
    if case == 'missing_reward_metadata' and str(path) == str(root/'output/episode_1/vlm_agent/metadata.json'):
        raise FileNotFoundError('in-memory missing evidence fixture')
    data = READ(path)
    relative = str(path)
    if path.name == 'status.json' and case == 'missing_stage_bundle_ended':
        return encoded({'state':'failed', 'exit_code':1})
    if path.name == 'episode_compute.jsonl':
        rows = [json.loads(x) for x in data.splitlines() if x.strip()]
        if case == 'missing_compute': rows = [r for r in rows if r.get('task_id') != 0]
        if case == 'duplicate_compute': rows.append(copy.deepcopy(next(r for r in rows if r.get('task_id') == 0)))
        if case == 'wrong_compute_latency':
            for r in rows:
                if r.get('task_id') == 0: r['stage_codex_call_latency_s'] += 1
        return b''.join(encoded(r)+b'\n' for r in rows)
    if path.name == 'stage_events.jsonl':
        rows = [json.loads(x) for x in data.splitlines() if x.strip()]
        for r in rows:
            if r.get('task_id') != 0 or not r.get('validation_attempts'): continue
            if case == 'duplicate_capture_ref':
                r['validation_attempts'].append(copy.deepcopy(r['validation_attempts'][-1]))
            if case == 'one_pixel_coordinate': r['current_target_marker']['target_pixel'] = r['current_target_marker']['target_pixel'][:1]
            if case == 'wrong_observation': r['observation']['evidence'] = 'altered evidence'
            if case == 'wrong_attempt_reply': r['validation_attempts'][-1]['raw_response'] = '{}'
            if case == 'wrong_query_seed': r['episode_seed'] = 9876
            if case == 'bad_event_completion': r['completion_metadata']['response_model'] = 'wrong'
            if case == 'legal_recovery' and r.get('global_step') == 0:
                response = json.loads(READ(root/'output/captured_stage_inputs/request_0001/response.json'))
                policy = json.loads(READ(root/'output/captured_stage_inputs/request_0001/public-policy.json'))
                recovery((response,policy)); r['transport'] = response['transport']
        return b''.join(encoded(r)+b'\n' for r in rows)
    if path.name == 'safety_events.jsonl':
        rows = [json.loads(x) for x in data.splitlines() if x.strip()]
        for r in rows:
            if r.get('task_id') != 0: continue
            if case == 'action_override': r['override'] = True
            if case == 'action_changed': r['executed_action'][0] += .1
            if case == 'wrong_action_episode': r['episode'] = 13
        return b''.join(encoded(r)+b'\n' for r in rows)
    if case == 'wrong_identity_body' and str(path) == str(root/'output/captured_stage_inputs/request_0000/response.json'):
        value=json.loads(data);value['raw_response']='altered identity';return encoded(value)
    if '/episode_1/vlm_agent/' in relative:
        if case == 'wrong_saved_reward_code' and path.name == 'stage1_guidance.txt': return b'def stage1_guidance(keypoints):\n    return 100.0\n'
        if case == 'wrong_reward_prompt' and path.name == 'prompt.txt': return b'WRONG TASK PROMPT'
        if case == 'wrong_reward_output' and path.name == 'output_raw.txt': return b'WRONG OUTPUT'
        if case == 'wrong_reward_image' and path.name == 'query_img.png':
            from PIL import Image
            img = Image.open(io.BytesIO(data)).convert('RGB'); img.putpixel((0,0),(13,19,23)); output=io.BytesIO();img.save(output,format='PNG'); return output.getvalue()
        if case == 'wrong_reward_positions' and path.name == 'metadata.json' and '/codex_requests/' not in relative:
            value=json.loads(data);value['init_keypoint_positions'][0][0]+=1;return encoded(value)
        if case == 'wrong_contract_probes' and path.name == 'target_distance_reward.json':
            value=json.loads(data);value['checks'][0]['actual']+=1;return encoded(value)
    if case == 'legal_recovery' and str(path) == str(root/'output/captured_stage_inputs/request_0001/response.json'):
        response=json.loads(data);policy=json.loads(READ(path.with_name('public-policy.json')))
        recovery((response,policy));return encoded(response)
    return data

def exists(case,path,root):
    if case == 'missing_contract' and str(path) == str(root/'output/episode_1/vlm_agent/target_distance_reward.json'): return False
    if case in ('missing_stage_bundle','missing_stage_bundle_ended') and str(path) == str(root/'output/captured_stage_inputs/request_0001/public-policy.json'): return False
    return EXISTS(path)

CASES = ('real_prefix_synthetic_completion','legal_recovery','missing_compute','duplicate_compute','missing_contract',
         'missing_stage_bundle','missing_stage_bundle_ended','wrong_reward_prompt','wrong_reward_output',
         'wrong_reward_image','wrong_reward_positions','duplicate_capture_ref','wrong_compute_latency',
         'action_override','action_changed','wrong_action_episode','wrong_contract_probes','bad_event_completion','missing_reward_metadata',
         'one_pixel_coordinate','wrong_observation','wrong_attempt_reply','wrong_query_seed',
         'wrong_identity_body','wrong_saved_reward_code')

@pytest.mark.parametrize('case',CASES)
def test_completed_task_contract(case,tmp_path):
    root=materialize(tmp_path/'run',completed=True)
    report=tmp_path/('contract-'+case+'.json')
    argv=[str(DRAFT),str(root),'--task','0','--report',str(report)]
    with patch.object(Path,'read_bytes',lambda path:mutate(case,path,root)), patch.object(Path,'exists',lambda path:exists(case,path,root)), patch.object(sys,'argv',argv), contextlib.redirect_stdout(io.StringIO()):
        with pytest.raises(SystemExit) as exited:
            raise SystemExit(audit_cli_main())
        assert exited.value.code == (0 if case in ('real_prefix_synthetic_completion','legal_recovery') else 1)
    result=json.loads(READ(report))
    if case in ('real_prefix_synthetic_completion','legal_recovery'):
        assert result['task_contract_valid'] is True, result['summary']
        assert result['summary'].get('fail',0)==0
    else:
        assert result['task_contract_valid'] is False
        assert result['summary'].get('fail',0)>0, result['summary']
        assert result['summary'].get('pending',0)==0, result['summary']
    assert result['cohort_valid'] is None


def test_cropped_real_prefix_never_claims_completed_trial(tmp_path):
    from scripts.audit_steering_contract import audit_run
    root=materialize(tmp_path/'prefix')
    result=audit_run(root)
    assert result['summary'].get('fail',0)==0, result['checks']
    assert result['summary']['pending']==1
    assert result['task_evidence_complete'] is False
    assert result['task_contract_valid'] is False
    assert result['cohort_valid'] is None
    assert result['facts']['stage_events_checked']==2
    assert result['facts']['stage_response_captures_linked_to_prefix']==3
    assert result['facts']['action_rows_checked']==40


def test_missing_original_marker_path_uses_local_capture_fallback(tmp_path):
    from scripts.audit_steering_contract import audit_run
    root=materialize(tmp_path/'run',completed=True)
    events=root/'output/eds_eval/stage_events.jsonl'
    rows=[json.loads(line) for line in events.read_text().splitlines()]
    for row in rows:
        if isinstance(row.get('current_target_marker'),dict):
            row['current_target_marker']['raw_png_path']=str(tmp_path/'nonexistent-source-host'/'raw.png')
    events.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    result=audit_run(root)
    assert result['task_contract_valid'] is True, result['summary']
    assert result['cohort_valid'] is None
