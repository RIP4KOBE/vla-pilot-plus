"""Read-only verification of this executor packet, never production admission."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--report', required=True)
args = p.parse_args()
report_path = Path(args.report)
report = json.loads(report_path.read_bytes())
def check(ref):
    path = Path(ref['path'])
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == ref['sha256'], str(path)
    if 'bytes' in ref:
        assert len(data) == ref['bytes'], str(path)
for ref in report['outputs'].values():
    check(ref)
for ref in report['input_hashes']:
    check(ref)
assert report['status'] == 'PARTIAL_ARTIFACT_REFRESH_BLOCKED'
assert report['source'] == '0d618606a933473eb0e5a02fc3659a3a0ea0ee25'
assert report['scientific_source'] == '1065f38122379a515b60a9a424f574330405b66f'
for k in ('release_enabled', 'source_adopted', 'gpu_authorized', 'provider_measurement_authorized', 'graph_complete', 'graph_verified'):
    assert report[k] is False, k
base = report_path.parent
graph = json.loads((base / 'graph.partial-disabled-v1.json').read_bytes())
assert graph['resource_id'] is None
assert graph['authority'] is graph['b5_review'] is graph['root_acceptance'] is graph['root_controller_acceptance'] is None
assert graph['plan'] is graph['audit'] is graph['full40_manifests'] is None
runtime = json.loads((base / 'disabled-runtime.json').read_bytes())
assert runtime['preparation']['source'] == report['source']
assert runtime['preparation']['runtime_ready'] is runtime['provider_ready'] is runtime['cuda_egl_verified'] is False
controller = json.loads((base / 'controller-semantics.pending-disabled-v1.json').read_bytes())
assert controller['status'] == 'PENDING_ROOT_REVIEW_DISABLED' and controller['review_evidence'] == {}
print(json.dumps({'result': 'PASS_PACKET_HASHES_AND_DISABLED_BOUNDARIES', 'output_count': len(report['outputs']),
    'input_count': len(report['input_hashes']), 'production_admission': False,
    'report_sha256': hashlib.sha256(report_path.read_bytes()).hexdigest()}, sort_keys=True))
