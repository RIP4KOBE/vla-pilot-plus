#!/usr/bin/env python3
"""Offline steering evidence audit. Imports no policy or simulator modules; never executes saved code.
Only the explicit --report destination is written. Running cohorts remain pending.
PNG verification uses Pillow/OpenCV/NumPy on CPU, without CUDA/simulation/API.
"""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import io
from pathlib import Path
import re
from types import SimpleNamespace
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.steering_archive import support_asset, marker_frame

import yaml  # Safe parsing only; no runtime/repository import.

COUNTERS = ('logical_call_attempts', 'completed_turns', 'failed_calls', 'usage_complete_calls',
            'input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens', 'call_latency_s')
CONTEXT = ('episode_id', 'task_id', 'episode_seed', 'global_step', 'chunk_id')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def read_rows(path, partial):
    if not path.exists():
        return [], []
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    result, pending = [], []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError('JSONL row is not object')
            result.append(value)
        except (ValueError, UnicodeError):
            if partial and i == len(lines) and not line.endswith(b'\n'):
                pending.append(f'{path}:{i}: in-flight trailing line')
            else:
                raise
    return result, pending


def identity(row):
    return tuple(row.get(k) for k in CONTEXT)


def source_functions(text):
    fenced = re.search(r'```(?:python)?\s*\n(.*?)```', text, re.S)
    tree = ast.parse(fenced.group(1) if fenced else text)
    return {n.name: ast.dump(n, include_attributes=False)
            for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}



def counter_sum(records, field):
    values = [r.get(field) for r in records]
    if any(v is None for v in values):
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and math.isfinite(v) and v >= 0 for v in values):
        raise ValueError('Invalid counter value: ' + field)
    return sum(values)


def counter_equal(a, b, field):
    if a is None or b is None:
        return a is b
    if isinstance(a, bool) or isinstance(b, bool):
        return False
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return False
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6) if field == 'call_latency_s' else a == b


def parse_observation(raw):
    if not isinstance(raw, str):
        raise TypeError('Expected observation string')
    text = raw.strip()
    lines = text.splitlines()
    presentation = 'bare_json'
    if len(lines) >= 3 and lines[0].strip().lower() in ('```json', '```') and lines[-1].strip() == '```':
        text = '\n'.join(lines[1:-1]).strip()
        presentation = 'single_json_fence'
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate observation key')
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=pairs)
    enums = {'target_visibility': {'clear','occluded','unknown'},
             'target_location': {'outside_goal','inside_goal','above_goal','unknown'},
             'grasp': {'held','not_held','unknown'}, 'support': {'supported','unsupported','unknown'}}
    if not isinstance(value, dict) or set(value) != set(enums) | {'evidence'}:
        raise ValueError('Observation fields mismatch')
    if any(not isinstance(value[k],str) or value[k] not in allowed for k,allowed in enums.items()):
        raise ValueError('Invalid observation enum')
    if not isinstance(value['evidence'],str) or not value['evidence'].strip() or len(value['evidence']) > 2400:
        raise ValueError('Invalid observation evidence')
    return value, presentation


def rgb(path):
    from PIL import Image
    import numpy as np
    return np.asarray(Image.open(io.BytesIO(path.read_bytes())).convert('RGB'))


def literal_assignment(path, name):
    for node in ast.parse(path.read_bytes().decode()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('No literal assignment ' + name)


def instruction_for_task(root, task, manifest, *, archive_support=None):
    env_path = root / 'environment.json'
    if sha(env_path.read_bytes()) != manifest['environment_sha256']:
        raise ValueError('Environment manifest hash mismatch')
    env = read_json(env_path)
    assets_path = root / 'source/scripts/steering_assets_manifest.json'
    if sha(assets_path.read_bytes()) != manifest['source_sha256']['scripts/steering_assets_manifest.json']:
        raise ValueError('Asset manifest hash mismatch')
    assets = read_json(assets_path)
    rel = 'libero/libero/benchmark/libero_suite_task_map.py'
    task_map = support_asset(root, 'task_map', archive_support=archive_support, manifest=manifest)
    expected = assets['files'][rel]
    if isinstance(expected,dict):
        expected = expected['sha256']
    if sha(task_map.read_bytes()) != expected:
        raise ValueError('Task-map asset hash mismatch')
    mapping = literal_assignment(task_map, 'libero_task_map')
    return mapping['libero_object'][task].replace('_', ' ')

def evaluation_directory(root, manifest):
    """Resolve the manifest's run-relative evaluation directory, including old runs."""
    root = Path(root).resolve()
    relative = manifest.get('evaluation_directory', 'output/eds_eval')
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError('Invalid evaluation_directory')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('evaluation_directory must stay relative to the run')
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('evaluation_directory escapes the run')
    return resolved


def audit_run(run_dir, task=0, model="gpt-6-astra", effort="low", archive_support=None):
    """Read saved artifacts only; return task checks without writes or runtime imports."""
    args = SimpleNamespace(run_dir=Path(run_dir), task=task, model=model, effort=effort)
    root = args.run_dir.resolve()
    out = root / 'output'
    manifest = read_json(root / 'manifest.json')
    evaluation = evaluation_directory(root, manifest)
    status = read_json(root / 'status.json')
    worker_running = status.get('state') == 'running' and status.get('exit_code') is None
    partial = worker_running
    checks, pending, file_evidence, facts = {}, [], {}, {'evaluation_directory':str(evaluation.relative_to(root))}

    def check(name, condition, detail=None):
        checks[name] = {'status': 'pass' if condition else 'fail'}
        if detail is not None:
            checks[name]['detail'] = detail

    def wait(name, detail):
        checks[name] = {'status': 'pending' if partial else 'fail', 'detail': detail}

    def tracked(path):
        value = read_json(path)
        file_evidence[str(path.relative_to(root))] = sha(path.read_bytes())
        return value

    config_path = root / 'resolved-config.yaml'
    config = yaml.safe_load(config_path.read_text())
    check('resolved_config_hash', sha(config_path.read_bytes()) == manifest.get('config_sha256'))
    check('fixed_managed_provider_config', all(
        config['perception'][name].get('backend') == 'codex_cli'
        and config['perception'][name].get('model') == args.model
        and config['perception'][name].get('reasoning_effort') == args.effort
        and not config['perception'][name].get('api_key')
        and not config['perception'][name].get('base_url')
        for name in ('gemini','vlm_agent')))
    check('fresh_reward_configuration', not config['main'].get('cached_functions_dir')
          and not config['main'].get('cached_functions_root')
          and config['main'].get('reward_contract') == 'target_distance'
          and manifest.get('fresh_reward') is True)
    check('passthrough_and_marker_configuration', config['main'].get('grasp_action_guard_enabled') is False
          and config['main'].get('stage_target_marker_enabled') is True)
    check('no_other_remote_perception_config', all(
        config['perception'].get(name, {}).get('enabled') is False
        for name in ('sam3','gemini_grounding')))
    proof_files = ('main.py','core/codex_vision.py','core/codex_stage.py','core/codex_stage_policy.py',
                   'core/stage_grasp_guard.py','core/stage_target_marker.py','core/stage_observation.py',
                   'core/env_adapters/libero_adapter.py','vlm_query/vlm_agent.py',
                   'core/stage_identity_memory.py','core/stage_response_validation.py','core/stage_evidence.py',
                   'vlm_query/stage_observation_v1.txt','core/target_distance_reward.py')
    check('archived_evidence_implementations_match_manifest', all(
        sha((root / 'source' / path).read_bytes()) == manifest['source_sha256'].get(path)
        for path in proof_files))
    # Read once: this is a prefix snapshot, not an observer modifying the running job.
    rows = {}
    for name in ('stage_events', 'safety_events', 'episode_metadata', 'episode_compute', 'phase_timing'):
        rows[name], trailing = read_rows(evaluation / (name + '.jsonl'), partial)
        pending.extend(trailing)
    episode_index = manifest['tasks'].index(args.task)
    expected_seed = manifest['seeds'][episode_index]
    episode = out / f'episode_{episode_index + 1}'
    task_compute = [r for r in rows['episode_compute']
                    if r.get('task_id') == args.task or r.get('episode_id') == episode_index]
    final_video_exists = bool(list(episode.glob('*_agentview.mp4')))
    later_episode = any(r.get('episode_id', -1) > episode_index for r in rows['episode_metadata'])
    partial = worker_running and not (task_compute or final_video_exists or later_episode)
    if not partial and pending:
        facts['unattributed_inflight_tail_outside_completed_task'] = pending[:]
        pending.clear()
    expected_meta = (episode_index, args.task, expected_seed)
    task_metadata = [r for r in rows['episode_metadata']
                     if r.get('episode_id') == episode_index or r.get('task_id') == args.task]
    check('episode_metadata_anchored_to_manifest', len(task_metadata) == 1 and tuple(
        task_metadata[0].get(k) for k in ('episode_id','task_id','episode_seed')) == expected_meta)
    check('manifest_matches_resolved_task_seed_schedule', config['backend']['libero']['task_ids_filter'] == manifest['tasks']
          and config['main']['episode_seed_schedule'] == manifest['seeds'])
    events = [r for r in rows['stage_events'] if r.get('task_id') == args.task or r.get('episode_id') == episode_index]
    check('all_stage_events_anchored_to_manifest', bool(events) and all(
        tuple(r.get(k) for k in ('episode_id','task_id','episode_seed')) == expected_meta for r in events))
    queries = [r for r in events if r.get('query_status') in ('ok', 'error')]
    query_keys = {identity(r) for r in queries}
    check('unique_stage_query_identity', len(query_keys) == len(queries))
    check('queried_prefix_nonempty', bool(queries))
    stage_records, other_stage, reward_records = [], [], []
    instruction = instruction_for_task(root, args.task, manifest, archive_support=archive_support)
    reward_dir = episode / 'vlm_agent'
    reward_metadata = tracked(reward_dir / 'metadata.json')
    mapping = {int(k): v for k,v in reward_metadata['key_points_objects_map'].items()}
    mapping_labels = '\n'.join(f'{k}: {v}' for k,v in mapping.items())
    target_name = re.search(r'pick up (?:the )?(.+?) and place', instruction).group(1).replace(' ','_')
    target_indices = sorted(k for k,v in mapping.items() if v == target_name or v.startswith(target_name+'_'))
    check('reward_metadata_shape', reward_metadata.get('num_stages') == 2
          and reward_metadata.get('num_keypoints') == len(mapping) == len(reward_metadata['init_keypoint_positions'])
          and sorted(mapping) == list(range(len(mapping))) and bool(target_indices)
          and all(isinstance(v,str) for v in mapping.values())
          and all(len(p)==3 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in p)
                  for p in reward_metadata['init_keypoint_positions']))
    used_observation_captures = set()
    policy_template = None
    expected_disabled_features = set(literal_assignment(root/'source/core/codex_stage_policy.py','_DISABLED_FEATURES'))
    request_dirs = [(p, 'stage') for p in sorted((out / 'captured_stage_inputs').glob('request_*'))]
    request_dirs += [(p, 'reward') for p in sorted((episode / 'vlm_agent/codex_requests').glob('request_*'))]
    complete_request_names = []
    for directory, kind in request_dirs:
        response_path = directory / 'response.json'
        required = ('response.json','public-policy.json','metadata.json','parts.json','codex_prompt.txt')
        if not all((directory / name).exists() for name in required):
            if partial:
                pending.append(f'{directory.relative_to(root)}: incomplete capture bundle')
            elif kind == 'reward' or not worker_running:
                check(kind + '_capture_complete/' + directory.name, False)
            else:
                facts.setdefault('unattributed_inflight_captures', []).append(str(directory.relative_to(root)))
            continue
        try:
            response = tracked(response_path)
        except (ValueError, UnicodeError):
            if not partial:
                raise
            pending.append(f'{directory.relative_to(root)}: response write in progress')
            continue
        if kind == 'stage':
            context = response.get('context', {})
            if context.get('task_id') != args.task and context.get('episode_id') != episode_index:
                continue
            check(f'stage/{directory.name}/manifest_context', tuple(context.get(k) for k in
                  ('episode_id','task_id','episode_seed')) == expected_meta)

        policy = tracked(directory / 'public-policy.json')
        metadata = tracked(directory / 'metadata.json')
        parts = tracked(directory / 'parts.json')
        label = f'{kind}/{directory.name}'
        transport = response.get('transport', {})
        completion = response.get('completion_metadata') or {}
        overrides = policy.get('config_overrides', {})
        check(label + '/managed_fixed_request', response.get('backend') == 'codex_cli'
              and response.get('auth_mode') == 'chatgpt'
              and transport.get('backend') == 'codex_cli' and transport.get('auth_mode') == 'chatgpt'
              and transport.get('model') == args.model and transport.get('reasoning_effort') == args.effort
              and policy.get('model') == args.model and policy.get('reasoning_effort') == args.effort
              and overrides.get('model_provider') == 'openai'
              and overrides.get('forced_login_method') == 'chatgpt'
              and overrides.get('model_reasoning_effort') == args.effort)
        check(label + '/valid_completion', response.get('ok') is True
              and completion.get('response_model') == args.model
              and completion.get('reasoning_effort') == args.effort
              and transport.get('process_returncode') == 0
              and transport.get('process_timed_out') is False
              and transport.get('completed_turns') == 1)
        role_config = config['perception']['gemini' if kind == 'stage' else 'vlm_agent']
        check(label + '/fixed_transport_policy', transport.get('event_policy') == role_config.get('event_policy','strict_v1')
              and transport.get('transport_retry_count') == role_config.get('transport_retry_count',0)
              and transport.get('transport_retry_backoff_seconds') == role_config.get('transport_retry_backoff_seconds',2.0)
              and transport.get('timeout_seconds') == role_config.get('timeout_seconds',180)
              and transport.get('application_max_attempts') == 1)
        if __package__:
            from .steering_transport_audit import audit_transport
        else:
            from steering_transport_audit import audit_transport
        for name, passed in audit_transport(response, policy).items():
            if passed is None:
                wait(label + '/transport/' + name, 'Transport evidence not observable')
            else:
                check(label + '/transport/' + name, passed)
        canonical = json.dumps(policy, sort_keys=True, separators=(',', ':')).encode()
        check(label + '/policy_hash', sha(canonical) == transport.get('public_config_sha256'))
        fixed_arguments = policy.get('fixed_arguments', [])
        disabled_paths = policy.get('disabled_skill_paths', [])
        expected_skills = [{'path':str(Path(path)/'SKILL.md'),'enabled':False} for path in sorted(disabled_paths)]
        check(label + '/child_no_tools', set(policy.get('disabled_features', [])) == expected_disabled_features
              and not policy.get('enabled_features') and overrides.get('web_search') == 'disabled'
              and overrides.get('mcp_servers') == {} and overrides.get('project_doc_max_bytes') == 0
              and overrides.get('approval_policy') == 'never'
              and fixed_arguments == ['exec','--ignore-user-config','--ignore-rules','--ephemeral',
                   '--skip-git-repo-check','--sandbox','read-only','--json','--color','never']
              and bool(disabled_paths) and len(disabled_paths) == len(set(disabled_paths))
              and overrides.get('skills.config') == expected_skills
              and transport.get('disabled_skill_paths') == disabled_paths)
        if policy_template is None:
            policy_template = policy
        check(label + '/fixed_public_policy_across_requests', policy == policy_template)
        check(label + '/capture_index_matches_directory', metadata.get('query_index') == int(directory.name.split('_')[-1]))
        prompt = '\n\n'.join(p['text'] for p in parts if p['type'] == 'text')
        prompt_file = (directory / 'codex_prompt.txt').read_text()
        image_parts = [p for p in parts if p['type'] == 'image_url']
        image_hashes = []
        for item in image_parts:
            path = (directory / item['file']).resolve()
            if directory.resolve() not in path.parents:
                raise ValueError('Image path escapes request directory')
            digest = sha(path.read_bytes())
            image_hashes.append(digest)
            check(label + '/' + item['file'], digest == item['sha256'])
        expected = {'prompt_sha256': sha(prompt.encode()), 'image_png_sha256': image_hashes}
        check(label + '/payload_identity', prompt == prompt_file
              and all(metadata.get(k) == v for k,v in expected.items())
              and transport.get('request_fingerprint') == expected)
        record = {'response': response, 'metadata': metadata, 'directory': directory, 'parts': parts, 'prompt':prompt}
        if kind == 'stage':
            (stage_records if identity(response.get('context', {})) in query_keys else other_stage).append(record)
        else:
            reward_records.append(record)
        complete_request_names.append(label)
    facts['completed_request_captures_checked'] = complete_request_names
    facts['stage_events_checked'] = len(queries)
    facts['stage_response_captures_linked_to_prefix'] = len(stage_records)
    facts['unlinked_stage_responses'] = [str(r['directory'].relative_to(root)) for r in other_stage]
    if other_stage and partial:
        wait('no_orphan_stage_requests', 'Responses beyond this event snapshot may belong to an in-flight query')
    else:
        check('no_orphan_stage_requests', not other_stage)
    for query in queries:
        key = identity(query)
        group = [r for r in stage_records if identity(r['response']['context']) == key]
        label = f'query/task{args.task}/step{query["global_step"]}'
        check(label + '/capture_counter_match', bool(group) and all(
            counter_equal(counter_sum([r['response']['counters'] for r in group],k), query.get('codex_'+k), k)
            for k in COUNTERS))
        check(label + '/http_counts_unavailable', query.get('api_request_attempts') is None
              and query.get('api_sdk_retry_attempts') is None
              and query.get('api_request_counter_available') is False)
        attempts = query.get('validation_attempts', [])
        check(label + '/first_valid_answer', 1 <= len(attempts) <= config['perception']['gemini']['observation_validation_max_attempts']
              and attempts[-1].get('valid') is True
              and not any(a.get('valid') for a in attempts[:-1]))
        check(label + '/identity_completion_accounting', query.get('codex_completed_turns')
              == len(attempts) + int(query.get('identity_generated_this_query', False)))
        fingerprints, observation_images = [], []
        for attempt in attempts:
            index = attempt['capture_query_index']
            matches = [r for r in group if r['metadata'].get('query_index') == index]
            check(label + f'/capture_ref{index}', len(matches) == 1)
            if len(matches) != 1:
                continue
            record = matches[0]
            check(label + f'/capture_single_use{index}', index not in used_observation_captures)
            used_observation_captures.add(index)
            check(label + f'/reply_binding{index}', attempt.get('raw_response') == record['response'].get('raw_response')
                  and attempt.get('completion_metadata') == record['response'].get('completion_metadata'))
            try:
                parsed, presentation = parse_observation(record['response'].get('raw_response'))
                valid = (record['response'].get('completion_metadata') or {}).get('finish_reason') != 'length'
            except (ValueError, TypeError):
                parsed, presentation, valid = None, None, False
            check(label + f'/independent_schema{index}', attempt.get('valid') is valid
                  and (not valid or attempt.get('presentation') == presentation))
            if attempt is attempts[-1]:
                check(label + '/event_reply_and_observation_binding', query.get('raw_response') == record['response'].get('raw_response')
                      and query.get('observation') == parsed
                      and query.get('completion_metadata') == record['response'].get('completion_metadata')
                      and query.get('transport') == record['response'].get('transport'))
            expected_observation_prompt = (root/'source/vlm_query/stage_observation_v1.txt').read_bytes().decode().format(
                instruction=instruction+'\nTarget appearance from the initial reference (identity only): '+str(query.get('identity_memory')),
                keypoint_info=mapping_labels)
            marker_prompt = literal_assignment(root/'source/core/stage_target_marker.py','PROMPT')
            expected_observation_prompt += '\n' + marker_prompt
            check(label + f'/current_prompt_contract{index}', record['prompt'] == expected_observation_prompt
                  + '\n\nCurrent observation; judge this image')
            fingerprints.append((record['metadata']['prompt_sha256'], record['metadata']['image_png_sha256']))
            images = [p for p in record['parts'] if p['type'] == 'image_url']
            check(label + f'/one_current_image{index}', len(images) == 1)
            observation_images.extend(record['directory'] / p['file'] for p in images)
        check(label + '/attempt_order', [a.get('attempt') for a in attempts] == list(range(1,len(attempts)+1))
              and [a.get('capture_query_index') for a in attempts] == sorted(a.get('capture_query_index') for a in attempts))
        check(label + '/retry_payload_unchanged', bool(fingerprints)
              and all(f == fingerprints[0] for f in fingerprints))
        marker = query.get('current_target_marker')
        if not isinstance(marker, dict):
            check(label + '/marker_present', False)
            continue
        try:
            # Decode/hash and reconstruct annotation in memory only. No images written.
            from PIL import Image
            import cv2
            import numpy as np
            raw_path = marker_frame(evaluation, episode_index, query['global_step'], marker)
            raw = rgb(raw_path)
            check(label + '/raw_frame_hash', sha(raw_path.read_bytes()) == marker['raw_png_sha256']
                  and sha(raw.tobytes()) == marker['raw_rgb_sha256'])
            h, w = raw.shape[:2]
            shape_valid = (np.asarray(marker.get('target_world_position')).shape == (3,)
                           and np.asarray(marker.get('camera_extrinsic')).shape == (4,4)
                           and np.asarray(marker.get('camera_intrinsic')).shape == (3,3)
                           and (marker.get('target_pixel') is None or np.asarray(marker['target_pixel']).shape == (2,)))
            check(label + '/marker_shape_and_target', shape_valid and marker.get('target_keypoint_indices') == target_indices
                  and marker.get('schema') == 'stage_current_target_marker_v1'
                  and marker.get('camera') == config['backend']['libero']['vlm_camera'])
            geometry_finite = shape_valid and all(np.isfinite(np.asarray(marker[name],dtype=float)).all()
                for name in ('target_world_position','camera_extrinsic','camera_intrinsic'))
            check(label + '/marker_geometry_finite', geometry_finite)
            if not geometry_finite:
                continue
            point = np.array(marker['target_world_position'] + [1.])
            camera_point = (np.array(marker['camera_extrinsic']) @ point)[:3]
            depth = float(camera_point[2])
            expected_status, pixel = 'behind_camera', None
            marked = raw.copy()
            if depth > 1e-6:
                projected = np.array(marker['camera_intrinsic']) @ camera_point
                pixel = [float(projected[0]/projected[2]), float(h-1-projected[1]/projected[2])]
                expected_status = 'outside_image'
                if 0 <= pixel[0] < w and 0 <= pixel[1] < h:
                    expected_status = 'drawn'
                    center = tuple(int(round(v)) for v in pixel)
                    cv2.circle(marked, center, 24, (255,0,255), 2)
                    cv2.putText(marked, 'TARGET', (max(0,center[0]-29),max(15,center[1]-30)),
                                cv2.FONT_HERSHEY_SIMPLEX,.55,(255,0,255),2)
            check(label + '/marker_projection', marker['status'] == expected_status
                  and marker['image_width'] == w and marker['image_height'] == h
                  and math.isclose(marker['camera_depth'], depth, abs_tol=1e-9)
                  and (pixel == marker['target_pixel'] or (pixel is not None and marker['target_pixel'] is not None
                       and all(math.isclose(a,b,abs_tol=1e-9) for a,b in zip(pixel,marker['target_pixel'])))))
            check(label + '/marked_pixels_match', sha(marked.tobytes()) == marker['marked_rgb_sha256']
                  and bool(observation_images)
                  and all(sha(rgb(p).tobytes()) == marker['marked_rgb_sha256']
                          for p in observation_images))
        except (ImportError, OSError, ValueError, TypeError, KeyError) as exc:
            check(label + '/marker_pixel_verification', False, type(exc).__name__)
    identities = [r for r in queries if r.get('identity_generated_this_query')]
    check('one_identity_on_first_query', len(identities) == 1 and identities[0] is queries[0]
          and identities[0].get('global_step') == 0)
    identity_records = [r for r in stage_records if r['metadata']['query_index'] not in used_observation_captures]
    check('one_identity_capture_not_an_observation', len(identity_records) == 1)
    if len(identity_records) == 1 and queries:
        memory = identity_records[0]['response']['raw_response']
        expected_identity_prompt = ('Identify only the instructed target object. Task: '+instruction+'\n'
              'The initial image is annotated with these object keypoint labels:\n'+mapping_labels+'\n'
              'Describe the exact target by visible shape, colors, label and size so it can be '
              'recognized in another camera frame. Distinguish it from neighboring distractors. '
              'Do not describe robot actions or infer any current grasp or task success. '
              'Do not give commands or control decisions. Use under 100 words.')
        check('identity_request_bound_to_task_initial_query', identity_records[0]['prompt'] == expected_identity_prompt
              and identity(identity_records[0]['response']['context']) == identity(queries[0])
              and identity_records[0]['metadata']['query_index'] < min(used_observation_captures,default=-1))
        check('identity_memory_bound_to_capture', isinstance(memory,str) and bool(memory.strip()) and len(memory) <= 2400
              and all(q.get('identity_memory') == memory for q in queries))
        images = [x for x in identity_records[0]['parts'] if x['type'] == 'image_url']
        check('identity_initial_image_matches_prepare_image', len(images) == 1 and
              sha(rgb(identity_records[0]['directory']/images[0]['file']).tobytes()) == sha(rgb(reward_dir/'query_img.png').tobytes()))
    check('one_fresh_reward_capture_for_task', len(reward_records) == 1 and
          reward_records[0]['response'].get('counters', {}).get('completed_turns') == 1)
    if len(reward_records) == 1:
        record = reward_records[0]
        reward_raw = record['response']['raw_response']
        returned_functions = source_functions(reward_raw)
        stored = {}
        for path in sorted(reward_dir.glob('stage*_guidance.txt')):
            stored.update(source_functions(path.read_bytes().decode()))
            file_evidence[str(path.relative_to(root))] = sha(path.read_bytes())
        check('generated_reward_matches_saved_functions', bool(stored) and stored == returned_functions)
        check('reward_raw_output_bound_to_capture', (reward_dir/'output_raw.txt').read_bytes().decode() == reward_raw)
        prompt = (reward_dir/'prompt.txt').read_bytes().decode()
        check('reward_prompt_bound_to_capture', prompt == record['prompt'] and
              re.search(r'^Query Task: "(.*)"$', prompt, re.M).group(1) == instruction)
        map_match = re.search(r'^Keypoints to object name map: "(.*)"$',prompt,re.M)
        check('reward_prompt_mapping_bound_to_metadata', bool(map_match) and ast.literal_eval(map_match.group(1)) == mapping)
        positions = re.search(r'Keypoint 3D positions \[X, Y, Z\]: "(.*?)"',prompt,re.S)
        import numpy as np
        values = np.fromstring(positions.group(1).replace('[',' ').replace(']',' '),sep=' ') if positions else np.array([])
        expected_positions = np.asarray(reward_metadata['init_keypoint_positions'])
        check('reward_prompt_positions_bound_to_metadata', bool(positions) and values.size == expected_positions.size
              and positions.group(1) == np.array2string(np.asarray(expected_positions,dtype=np.float32)))
        images = [x for x in record['parts'] if x['type'] == 'image_url']
        check('reward_prepare_image_bound_to_capture', len(images) == 1 and
              sha((record['directory']/images[0]['file']).read_bytes()) == sha((reward_dir/'query_img.png').read_bytes()))
        check('reward_first_capture_for_episode', len(list((reward_dir/'codex_requests').glob('request_*'))) == 1
              and record['metadata']['query_index'] == episode_index)
    contract_path = episode / 'vlm_agent/target_distance_reward.json'
    if contract_path.exists():
        contract = tracked(contract_path)
        probes = contract.get('checks', [])
        check('saved_reward_contract_valid', contract.get('valid') is True
              and contract.get('reason') == 'consistent_on_probes'
              and contract.get('probe_count') == len(probes) == 64
              and all(p.get('consistent') is True and all(isinstance(p.get(k),(int,float))
                  and math.isfinite(p[k]) for k in ('actual','expected','absolute_difference'))
                  and math.isclose(abs(p['actual']-p['expected']),p['absolute_difference'],abs_tol=1e-12)
                  and p['absolute_difference'] <= 1e-6+1e-5*abs(p['expected']) for p in probes)
              and contract.get('max_absolute_difference') == max((p.get('absolute_difference',float('inf')) for p in probes),default=float('inf')))
    else:
        wait('saved_reward_contract_valid', 'Reward contract has not been completed')
    actions = [r for r in rows['safety_events'] if (r.get('task_id') == args.task
               or r.get('episode') == episode_index) and r.get('event') == 'stage_grasp_guard_action']
    check('actions_anchored_to_episode_task', bool(actions) and all(
          (r.get('episode'),r.get('task_id')) == (episode_index,args.task) for r in actions))
    check('actions_nonempty', bool(actions))
    check('no_arm_or_gripper_override', bool(actions) and all(r.get('override') is False
          and r.get('raw_action') == r.get('executed_action') and len(r.get('raw_action', [])) == 7
          and all(math.isfinite(v) for v in r['raw_action'])
          and r.get('reason') == 'policy_gripper_passthrough' for r in actions))
    steps = [r['global_step'] for r in actions]
    check('gripper_already_binary_before_adapter', bool(actions) and all(r['raw_action'][-1] in (-1,1) for r in actions))
    check('action_step_prefix_contiguous', steps == list(range(len(steps))))
    exited_steps = [r['global_step'] for r in rows['phase_timing']
                    if r.get('episode') == episode_index and r.get('name') == 'adapter_step'
                    and r.get('event') == 'exit']
    # The phase file is read after safety; newer phase entries are outside this prefix.
    if partial and steps:
        exited_steps = [step for step in exited_steps if step <= steps[-1]]
    # A safety record precedes adapter.step; one pending action is legal in a running snapshot.
    check('actions_cover_observed_adapter_steps', exited_steps == list(range(len(exited_steps)))
          and steps[:len(exited_steps)] == exited_steps
          and len(steps)-len(exited_steps) in ((0,1) if partial else (0,)))
    facts['action_rows_checked'] = len(actions)
    facts['adapter_step_exits_observed'] = len(exited_steps)
    if len(task_compute) == 1:
        c = task_compute[0]
        check('compute_identity_anchored_to_manifest', tuple(c.get(k) for k in ('episode_id','task_id','episode_seed')) == expected_meta
              and c.get('outcome') == 'completed')
        for prefix, records in [('stage',stage_records), ('guidance',reward_records)]:
            check(prefix + '_compute_matches_captures', all(counter_equal(c.get(prefix+'_codex_'+k),
                  counter_sum([r['response']['counters'] for r in records],k),k) for k in COUNTERS))
        check('provider_compute_sum_matches_components', all(counter_equal(c.get('provider_'+k),
              counter_sum([{'value':c.get(prefix+'_codex_'+k)} for prefix in ('stage','guidance','grounding')],'value'),k)
              for k in COUNTERS))
        check('inactive_grounding_has_zero_calls', all(c.get('grounding_codex_'+k) == 0 for k in COUNTERS))
        check('provider_http_counts_stay_unavailable', c.get('provider_request_attempts') is None
              and c.get('provider_sdk_retry_attempts') is None and c.get('provider_http_counters_available') is False)
    elif not task_compute:
        wait('episode_compute_capture_reconciliation', 'Missing episode_compute for this task')
    else:
        check('episode_compute_capture_reconciliation', False, 'Duplicate episode_compute rows')
    facts['worker_state_at_read'] = status.get('state')
    facts['task_episode_compute_rows'] = len(task_compute)
    result = {
        'schema':'steering-contract-audit-v1',
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'run_dir':str(root), 'task_id':args.task,
        'scope':'read-only completed request/action prefix; not cohort acceptance',
        'cohort_valid':None,
        'task_evidence_complete':not partial,
        'task_contract_valid': (not partial and not pending and all(c['status']=='pass' for c in checks.values())),
        'checks':checks,
        'summary':dict(Counter(c['status'] for c in checks.values())),
        'facts':facts, 'in_flight_or_pending':pending, 'artifact_sha256':file_evidence,
        'limits':[
            'No saved reply/function is executed. No GPU, simulator, API, policy/simulator imports or raw-run writes.',
            'response_model is transport-config metadata, not independently returned server model attestation.',
            'Raw transport event streams and notice text were not saved. Event-summary checks rely on hash-verified runtime validation and retained notice classifications, not independent parser replay.',
            'Action rows record task and episode, not seed. Seed is established by episode metadata and Stage/compute records.',
            'Reward formula probes are saved runtime attestations checked for internal consistency, not independently re-executed here.',
            'Action proof is postprocessor-to-adapter command passthrough; no independent simulator input telemetry is saved. Controller-native scaling/clipping remains normal.',
            'Recorded marker geometry/pixel linkage is verified; ground-truth semantic keypoint correctness is not inferred.',
            'A task audit alone does not establish complete cohort validity or a cohort success count.',
        ],
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('--archive-support', type=Path)
    parser.add_argument('--task', type=int, default=0)
    parser.add_argument('--model', default='gpt-6-astra')
    parser.add_argument('--effort', default='low')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report_path = args.report.resolve()
    try:
        result = audit_run(args.run_dir, args.task, args.model, args.effort, archive_support=args.archive_support)
    except Exception as exc:
        # Missing/malformed evidence is a failed audit, never an apparent pass.
        # Preserve a machine-readable result without exposing saved response text.
        result = {
            'schema':'steering-contract-audit-v1',
            'generated_at':datetime.now(timezone.utc).isoformat(),
            'run_dir':str(args.run_dir.resolve()), 'task_id':args.task,
            'scope':'offline task evidence audit; not cohort acceptance',
            'cohort_valid':None, 'task_evidence_complete':False,
            'task_contract_valid':False,
            'checks':{'evidence_read_and_structure':{'status':'fail','error_type':type(exc).__name__}},
            'summary':{'fail':1}, 'facts':{}, 'in_flight_or_pending':[],
        }
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'report':str(report_path),'summary':result['summary'],'facts':result['facts'],
                      'failed':[k for k,v in result['checks'].items() if v['status']=='fail']}, indent=2))
    return 1 if result['summary'].get('fail',0) else 0


if __name__ == '__main__':
    raise SystemExit(main())
