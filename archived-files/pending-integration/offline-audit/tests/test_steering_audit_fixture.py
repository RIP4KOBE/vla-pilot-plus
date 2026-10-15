"""Ensure immutable evidence integrity and explain synthetic completion explicitly."""
import hashlib
import json
import shutil
from pathlib import Path
import pytest
from steering_audit_fixture import FIXTURE, materialize, read_fixture_file

def test_complete_fixture_index_hashes_and_synthetic_scope():
    provenance=json.loads((FIXTURE/'provenance.json').read_bytes())
    index_bytes=(FIXTURE/'files.json').read_bytes()
    assert hashlib.sha256(index_bytes).hexdigest()==provenance['files_manifest_sha256']
    entries=json.loads(index_bytes)['files']
    assert len(entries)==58
    for relative in entries:
        read_fixture_file(relative)
    assert provenance['facts']['is_completed_episode_evidence'] is False
    assert provenance['facts']['is_online_success_result'] is False
    assert provenance['crop']['action_steps_inclusive']==[0,39]
    assert provenance['crop']['stage_query_steps']==[0,32]

def test_corrupted_png_blob_is_rejected_before_audit(tmp_path):
    fixture=tmp_path/'fixture';shutil.copytree(FIXTURE,fixture)
    entries=json.loads((fixture/'files.json').read_bytes())['files']
    relative='output/captured_stage_inputs/request_0001/image_01.png'
    blob=fixture/'blobs'/entries[relative]['sha256'];blob.write_bytes(blob.read_bytes()+b'corrupt')
    with pytest.raises(ValueError,match='integrity mismatch'):
        materialize(tmp_path/'run',fixture=fixture)

def test_materialization_relocates_paths_but_preserves_scientific_payload(tmp_path):
    root=materialize(tmp_path/'relocated'/'run',completed=True)
    index=json.loads((FIXTURE/'files.json').read_bytes())['files']
    changed={'environment.json','manifest.json','status.json','output/eds_eval/stage_events.jsonl','output/eds_eval/episode_compute.jsonl'}
    for relative in set(index)-changed:
        assert (root/relative).read_bytes()==read_fixture_file(relative)
    environment=json.loads((root/'environment.json').read_bytes())
    assert Path(environment['libero']['root']).is_relative_to(root)
    compute=json.loads((root/'output/eds_eval/episode_compute.jsonl').read_text())
    assert compute['fixture_synthetic_receipt'] is True
    assert compute['stage_codex_completed_turns']==3
    assert compute['guidance_codex_completed_turns']==1
    assert compute['provider_completed_turns']==4
    assert 'model_forward_calls' not in compute
