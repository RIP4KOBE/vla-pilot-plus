"""Materialize a self-contained real evidence prefix, never a completed trial claim."""
from pathlib import Path
import hashlib
import json

FIXTURE = Path(__file__).parent / 'fixtures' / 'steering_contract'
COUNTERS = ('logical_call_attempts','completed_turns','failed_calls','usage_complete_calls',
            'input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens','call_latency_s')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read_fixture_file(relative_path, fixture=FIXTURE):
    index = json.loads((fixture / 'files.json').read_bytes())
    entry = index['files'][relative_path]
    digest = entry['sha256']
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Invalid content digest')
    data = (fixture / 'blobs' / digest).read_bytes()
    if sha(data) != digest or len(data) != entry['bytes']:
        raise ValueError('Fixture integrity mismatch')
    return data

def json_write(path, value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def materialize(root, *, completed=False, fixture=FIXTURE):
    """Relocate recorded paths and optionally synthesize a cropped-prefix receipt.

    completed=True is test scaffolding: no real 40-step completed episode is claimed.
    Actual PNGs, model replies, prompts, saved reward code and proof source are unchanged.
    """
    root = Path(root).resolve()
    root.mkdir(parents=True,exist_ok=False)
    provenance=json.loads((fixture/'provenance.json').read_bytes())
    if sha((fixture/'files.json').read_bytes()) != provenance['files_manifest_sha256']:
        raise ValueError('Fixture index integrity mismatch')
    index = json.loads((fixture / 'files.json').read_bytes())
    for relative in index['files']:
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise ValueError('Fixture path escapes target')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(read_fixture_file(relative,fixture))
    environment = json.loads((root/'environment.json').read_bytes())
    environment['libero']['root'] = str(root/'assets/libero')
    json_write(root/'environment.json',environment)
    manifest = json.loads((root/'manifest.json').read_bytes())
    manifest['environment_sha256'] = sha((root/'environment.json').read_bytes())
    json_write(root/'manifest.json',manifest)
    events_file = root/'output/eds_eval/stage_events.jsonl'
    events = [json.loads(row) for row in events_file.read_text().splitlines()]
    for event in events:
        marker = event.get('current_target_marker')
        if isinstance(marker,dict):
            marker['raw_png_path'] = str(root/'output/eds_eval/stage_unmarked_frames'/
                 f"episode_{event['episode_id']:03d}"/f"step_{event['global_step']:06d}.png")
    events_file.write_text(''.join(json.dumps(row)+'\n' for row in events))
    if completed:
        json_write(root/'status.json',{'state':'exited','exit_code':0,'fixture_synthetic_status':True})
        def total(responses,field):
            values = [r['counters'][field] for r in responses]
            return None if any(v is None for v in values) else sum(values)
        stage=[json.loads(p.read_bytes()) for p in sorted((root/'output/captured_stage_inputs').glob('request_*/response.json'))]
        reward=[json.loads(p.read_bytes()) for p in sorted((root/'output/episode_1/vlm_agent/codex_requests').glob('request_*/response.json'))]
        receipt={'episode_id':0,'task_id':0,'episode_seed':44,'outcome':'completed',
          'fixture_synthetic_receipt':True,
          'fixture_scope':'Recomputed counters for retained requests only; not a real completed episode or scientific result.',
          'provider_request_attempts':None,'provider_sdk_retry_attempts':None,'provider_http_counters_available':False}
        for k in COUNTERS:
            receipt['stage_codex_'+k] = total(stage,k)
            receipt['guidance_codex_'+k] = total(reward,k)
            receipt['grounding_codex_'+k] = 0
            values=[receipt[p+'_codex_'+k] for p in ('stage','guidance','grounding')]
            receipt['provider_'+k] = None if any(v is None for v in values) else sum(values)
        (root/'output/eds_eval/episode_compute.jsonl').write_text(json.dumps(receipt)+'\n')
    return root
