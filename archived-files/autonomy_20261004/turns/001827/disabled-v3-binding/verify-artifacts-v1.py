"""Read-only verification of this executor packet, never production admission."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--report', required=True)
p.add_argument('--controller-proof')
p.add_argument('--controller-sha256')
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
assert report['status'] == 'DISABLED_V3_CANDIDATE_COMPOSED_WITH_PRESERVED_BLOCKERS'
assert report['source'] == 'cd6c969cbfdf006fd017553448bed2e61fc0380e'
assert report['scientific_source'] == '1065f38122379a515b60a9a424f574330405b66f'
for k in ('release_enabled', 'source_adopted', 'gpu_authorized', 'provider_measurement_authorized', 'graph_complete', 'graph_verified'):
    assert report[k] is False, k
base = report_path.parent
graph = json.loads((base / 'graph.candidate-disabled-v3.json').read_bytes())
assert graph['resource_id'] == 'n36_readiness_preparation_recovery_001827'
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

contract=json.loads(Path(graph['recovery_prefix_contract']['path']).read_bytes())
assert contract['schema']=='n36-readiness-recovery-prefix-contract-v3'
assert len(contract['predecessors'])==3
assert [(x['terminal_status'],x['telemetry_complete']) for x in contract['predecessors']]==[('aborted',False),('aborted',False),('completed',True)]
assert contract['accepted_review'] is contract['root_terminal_reconciliation'] is None
assert sum(x['retained_charge_gpu_seconds'] for x in contract['predecessors'])==631.4651556015015
for pred in contract['predecessors']:check(pred['raw_sequence'])
policy=json.loads(Path(graph['policy']['path']).read_bytes())
for key,value in policy.items():
    if key.endswith('_path'):assert str(Path(value).resolve())==value
assert graph['source_placement'] is None
assert all(x==0 for x in report['fresh_candidate_occurrences'].values())
print(json.dumps({'result':'PASS_THREE_PREDECESSORS_CANONICAL_PATHS_AND_OPEN_OWNER_GATES','production_admission':False}))
