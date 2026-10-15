"""Current checkout vs a recorded CPU golden; no reference-runtime checkout.

STEERING_GOLDEN_SOURCE_ROOT is only for staging this test before repository
integration. In a new clone the default is the root containing this tests folder.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

TESTS=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('STEERING_GOLDEN_SOURCE_ROOT',TESTS.parent)).resolve()
FIXTURE=TESTS/'fixtures/steering_eds_golden'
HARNESS=TESTS/'steering_eds_golden.py'


def invoke(tmp_path, reference):
    output=tmp_path/'candidate'
    env=dict(os.environ)
    env.pop('PYTHONPATH',None)
    env.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
    result=subprocess.run([sys.executable,str(HARNESS),'--source-root',str(ROOT),
        '--provenance',str(FIXTURE/'source-provenance.json'),
        '--output-dir',str(output),'--compare',str(reference)],
        cwd=tmp_path,env=env,text=True,capture_output=True,timeout=180)
    return result,output


def test_recorded_fixture_identity_and_portability():
    packed=(FIXTURE/'behavior.json.gz').read_bytes()
    report=json.loads((FIXTURE/'capture-report.json').read_text())
    raw=gzip.decompress(packed)
    assert hashlib.sha256(packed).hexdigest()==report['behavior_gzip_sha256']
    assert hashlib.sha256(raw).hexdigest()==report['behavior_sha256']
    assert b'/tmp/' not in raw and b'/home/' not in raw and b'$OUTPUT' not in raw
    assert b'raw_png_path' not in raw and b'latency_s' not in raw
    provenance=json.loads((FIXTURE/'source-provenance.json').read_text())
    assert provenance['commit']=='cfecb12db736f1a3408d9528d9336aadcb7e41b5'
    assert all(not Path(item['path']).is_absolute() and '..' not in Path(item['path']).parts
               for item in provenance['files'])
    assert report['scenario_cpu_rng_restored'] and not report['cuda_initialized']
    assert report['coverage']['float32']['guided_chunks']==10
    assert report['coverage']['bfloat16']['actual_reward_calls']==2560


def test_current_eds_closed_loop_matches_frozen_golden(tmp_path):
    result,output=invoke(tmp_path,FIXTURE/'behavior.json.gz')
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    report=json.loads((output/'report.json').read_text())
    assert report['comparison_requested'] and report['comparison_difference'] is None
    assert report['source_unchanged'] and report['scenario_cpu_rng_restored']
    assert not report['cuda_initialized']


def test_action_change_cannot_pass_as_matching_reference(tmp_path):
    # A test-only false action claim must be rejected after running the real
    # current engine. The recorded reference itself is never overwritten.
    changed=json.loads(gzip.decompress((FIXTURE/'behavior.json.gz').read_bytes()))
    changed['scenarios']['bfloat16']['actions'][0]['action']['values'][0] += .125
    bad=tmp_path/'changed-expected.json.gz'
    bad.write_bytes(gzip.compress(json.dumps(changed).encode(),mtime=0))
    result,output=invoke(tmp_path,bad)
    assert result.returncode==1,result.stdout+'\n'+result.stderr
    report=json.loads((output/'report.json').read_text())
    assert report['comparison_difference'].startswith('$.scenarios.bfloat16.actions[0].action.values[0]')
