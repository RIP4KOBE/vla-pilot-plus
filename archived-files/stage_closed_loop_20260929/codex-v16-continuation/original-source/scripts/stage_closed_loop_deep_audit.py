#!/usr/bin/env python3
"""Post-run artifact audit and gallery; never changes a completed rollout."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/stage_closed_loop_20260929/runs'


def rows(p):
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def main(name):
    folder=ART/name
    audit=json.loads((folder/'audit.json').read_text())
    manifest=json.loads((folder/'manifest.json').read_text())
    events=rows(folder/'output/eds_eval/stage_events.jsonl')
    actions=rows(folder/'output/eds_eval/safety_events.jsonl')
    actions=[r for r in actions if r.get('event')=='stage_grasp_guard_action']
    config=yaml.safe_load((folder/'resolved-config.yaml').read_text())
    codex=manifest.get('provider')=='codex_cli'
    limit=config['perception']['gemini'].get('observation_validation_max_attempts',1)
    checks={'completion_audit_valid':audit['valid'],
            'archived_sources_match_manifest':all(hashlib.sha256((folder/'source'/p).read_bytes()).hexdigest()==h
                for p,h in manifest['source_sha256'].items())}
    per_task=[]
    for t in manifest['tasks']:
        ev=[x for x in events if x['task_id']==t]
        ac=[x for x in actions if x['task_id']==t]
        queries=[x for x in ev if x.get('query_status')=='ok']
        identities=[x for x in queries if x.get('identity_generated_this_query')]
        if manifest['controller']=='proprio_v4':
            checks[f'one_live_identity_task_{t}']=len(identities)==1
            checks[f'one_consistent_identity_task_{t}']=len({x.get('identity_memory') for x in queries})==1
        per_task.append(dict(task=t,online_queries=len(queries),live_identity_generations=len(identities),
            online_http_attempts=None if codex else sum(x.get('api_request_attempts',0) for x in queries),
            online_sdk_retries=None if codex else sum(x.get('api_sdk_retry_attempts',0) for x in queries),
            visual_held_with_empty_fingers=sum((x.get('observation') or {}).get('grasp')=='held'
                and (x.get('gripper_width_m') is not None and x['gripper_width_m']<.005) for x in queries),
            robot_negative_grasp_chunks=sum((x.get('robot_evidence') or {}).get('no_grasp',False) for x in ev),
            reacquisition_chunks=sum(x.get('sensor_consistency_reason')=='robot_observed_failed_grasp_reacquire' for x in ev),
            forced_open_actions=sum(x['override'] and x['reason']=='reopen_after_observed_empty_grasp' for x in ac),
            forced_hold_actions=sum(x['override'] and x['reason']=='hold_visible_target_outside_destination' for x in ac)))
        per_task[-1]['format_validation_retries']=sum(x.get('observation_validation_retries',0) for x in queries)
        per_task[-1]['guided_chunks_by_stage']={str(s):sum(x['stage_after']==s and x['guidance_after'] for x in ev) for s in [0,1,2]}
        if queries and all('validation_attempts' in x for x in queries):
            checks[f'first_valid_answer_task_{t}']=all(1<=len(x['validation_attempts'])<=limit and
                x['validation_attempts'][-1]['valid'] and not any(y['valid'] for y in x['validation_attempts'][:-1]) for x in queries)
            if codex:
                checks[f'codex_completion_accounting_task_{t}']=all(x.get('codex_completed_turns') ==
                    len(x['validation_attempts'])+int(x.get('identity_generated_this_query',False))
                    and x.get('api_request_attempts') is None for x in queries)
                per_task[-1]['online_cli_attempts']=sum(x.get('codex_logical_call_attempts',0) for x in queries)
            else:
                checks[f'http_accounting_task_{t}']=all(x.get('api_request_attempts') ==
                    len(x['validation_attempts'])+int(x.get('identity_generated_this_query',False))+
                    x.get('api_sdk_retry_attempts',0) for x in queries)
            same_payload=True
            for x in queries:
                fingerprints=[]
                for y in x['validation_attempts']:
                    path=folder/'output/captured_stage_inputs'/f'request_{y["capture_query_index"]:04d}'/'metadata.json'
                    metadata=json.loads(path.read_text())
                    fingerprints.append((metadata['prompt_sha256'],metadata['image_png_sha256']))
                same_payload &= all(v==fingerprints[0] for v in fingerprints)
            checks[f'format_retries_same_payload_task_{t}']=same_payload
    if manifest['controller']=='proprio_v4':
        capture=folder/'output/captured_stage_inputs'
        checks['current_observation_has_one_current_image']=True
        for p in capture.glob('request_*/parts.json'):
            parts=json.loads(p.read_text());text='\n'.join(x['text'] for x in parts if x['type']=='text')
            if 'Current observation; judge this image' in text:
                checks['current_observation_has_one_current_image'] &= sum(x['type']=='image_url' for x in parts)==1
    result=dict(valid=all(checks.values()),checks=checks,success=audit['success'],episodes=audit['episodes'],per_task=per_task)
    (folder/'deep-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    cards=[]
    for task in audit['per_task']:
        for video in task['videos']:
            relative=(ROOT/video).relative_to(folder)
            cards.append(f'<article><h2>Task {task["task"]}: {"success" if task["success"] else "failure"}</h2>'
                         f'<video controls preload="metadata" src="{html.escape(str(relative))}"></video></article>')
    page='<!doctype html><meta charset="utf-8"><title>'+html.escape(name)+'</title>'
    page+='<style>body{background:#15191f;color:#eceff4;font:17px sans-serif;margin:32px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:24px}video{width:100%}article{background:#242b36;padding:18px;border-radius:12px}</style>'
    page+=f'<h1>{html.escape(name)}: {audit["success"]}/{audit["episodes"]}</h1><p>Online Stage; fixed version and seeds. Environment success is the score. All failures retained.</p><main>'+''.join(cards)+'</main>'
    (folder/'videos.html').write_text(page)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');main(p.parse_args().name)
