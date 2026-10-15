"""At most six fixed CPU-only Stage calls for diagnostics, stopping at failure."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

W = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
A = Path(__file__).resolve().parents[1]
OUT = A / 'analysis/stage-transport-diagnostics-20260924'
sys.path.insert(0, str(W))
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as runner
from core.codex_stage import CodexStageRecognizer
import numpy as np
from PIL import Image


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def emit(event):
    with (OUT / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


assert os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'CPU-only diagnostic required'
OUT.mkdir(exist_ok=False)
old = runner.read_json(A / 'analysis/stage-json-live-check/manifest.json')
runtime = runner.read_json(A / 'runtime/n1u-deadline-stage/runtime-manifest.json')
runner.verify_provider(runtime, runner.child_environment(runtime), root=W)
config = dict(runtime['frozen_stage_provider'])
config['stage_template_path'] = str(W / 'vlm_query/stage_template.txt')
recognizer = CodexStageRecognizer(config)
assert recognizer.transport_metadata['public_config_sha256'] == config['public_config_sha256']
paths = [A / f'analysis/stage-json-live-check/input-{i}.png' for i in range(3)]
assert [runner.digest(path) for path in paths] == old['input_sha256']
images = [np.array(Image.open(path).convert('RGB')) for path in paths]
source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=W, text=True).strip()
manifest = {
    'schema': 'stage-transport-diagnostics-v1', 'created_at': now(),
    'source_commit': source,
    'source_sha256': {p: runner.digest(W / p) for p in [
        'core/codex_stage.py', 'core/codex_stage_policy.py', 'core/gemini_grounder.py',
        'vlm_query/stage_template.txt', 'tests/test_codex_stage.py']},
    'script_sha256': runner.digest(Path(__file__)),
    'runtime_manifest_sha256': runner.digest(A / 'runtime/n1u-deadline-stage/runtime-manifest.json'),
    'public_policy_sha256': config['public_config_sha256'],
    'input_png_sha256': old['input_sha256'],
    'maximum_calls': 6, 'input_order': [0, 1, 2, 0, 1, 2],
    'application_attempts_per_call': 1, 'timeout_seconds': 180,
    'stop_at_first_failed_or_incomplete_call': True,
    'gpu_used': False, 'episode_attempts': 0, 'gpu_hours': 0,
    'purpose': 'Observe current connectivity and redacted error categories; not a reliability certification or robot-policy evaluation.',
    'instruction': old['instruction'], 'stage_descriptions': old['stage_descriptions'],
    'triggers': old['triggers'], 'cpu_tests_passed': 153,
    'concurrent_shared_dispatched': [
        {k: g[-1].get(k) for k in ['attempt_id', 'physical_gpu', 'time_unix']}
        for g in runner.event_groups(runner.read_events(W / 'data/attempt-ledger.jsonl')).values()
        if g[-1]['event'] == 'dispatched'],
}
runner.durable_json(OUT / 'manifest.json', manifest)
for index, image_index in enumerate(manifest['input_order']):
    emit({'event': 'started', 'index': index, 'at': now()})
    returned = recognizer.identify_stage_and_guidance(
        current_rgb=images[image_index], init_img_with_keypoints=images[0],
        instruction=manifest['instruction'], stage_descriptions=manifest['stage_descriptions'],
        keypoint_id_to_object={0: 'red block', 1: 'green tray'}, num_stages=2,
        trigger_reason=manifest['triggers'][image_index])
    result = recognizer.last_result
    emit({'event': 'finished', 'index': index, 'at': now(), 'returned': returned, 'result': result})
    safe = {'index': index, 'ok': result['ok'], 'seconds': result['query_latency_s'],
            'logical_calls': result.get('codex_logical_call_attempts'),
            'usage_complete': result.get('codex_usage_complete_calls'),
            'input_tokens': result.get('codex_input_tokens'), 'output_tokens': result.get('codex_output_tokens'),
            'error': result.get('error'),
            'error_diagnostics': result.get('transport', {}).get('error_diagnostics'),
            'stderr_diagnostic': result.get('transport', {}).get('stderr_diagnostic')}
    print(json.dumps(safe), flush=True)
    if not result['ok'] or result.get('codex_usage_complete_calls') != 1:
        runner.durable_json(OUT / 'result.json', {'status': 'FAILED_STOPPED', 'finished': index + 1,
            'counter': recognizer.api_request_counter.snapshot(),
            'token_usage_complete': False, 'failed_call_tokens': None,
            'historical_failure_root_cause_proven': False})
        raise SystemExit(1)
runner.durable_json(OUT / 'result.json', {'status': 'SIX_CALLS_COMPLETED', 'finished': 6,
    'counter': recognizer.api_request_counter.snapshot(), 'token_usage_complete': True,
    'long_run_reliability_proven': False, 'historical_failure_root_cause_proven': False})
