import hashlib
import json
from pathlib import Path
import subprocess

root = Path.cwd()
tmp = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001793/preparation-binding-repair/tmp')
base = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001779/canonical-path-rebinding')
before = 'a5b32cdefc0879e98011f86b1559e4250926ba62'
after = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
def record(path):
    data = Path(path).read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
def read(ref):
    p = Path(ref['path']); assert record(p)['sha256'] == ref['sha256']
    return json.loads(p.read_text())
proof_ref = record(base/'proof.json')
proof = json.loads((base/'proof.json').read_text())
envelope = read(proof['measurement_envelope'])
source = read(proof['source_record'])
source_receipt = read(envelope['source_receipt'])
release = read(proof['release'])
plan = read(release['graph']['plan'])
# These are byte identities and receipt metadata only, not a readiness validation.
refs = {'proof': proof_ref, 'measurement_envelope': record(proof['measurement_envelope']['path']),
        'release': record(proof['release']['path']), 'source_record': record(proof['source_record']['path']),
        'plan': record(release['graph']['plan']['path'])}
for name in ('source_receipt', 'native_receipt', 'runtime_receipt'):
    refs[name] = record(envelope[name]['path'])
    assert refs[name]['sha256'] == envelope[name]['sha256']
refs['runtime_closure'] = record(plan['runtime_closure']['path'])
assert refs['runtime_closure']['sha256'] == plan['runtime_closure']['sha256']
changes = subprocess.check_output(['git', 'diff', '--name-only', before, after], text=True).splitlines()
source_versions = {}
for name in changes:
    current = record(root/name)
    result = subprocess.run(['git', 'show', before+':'+name], capture_output=True)
    original = {'sha256': hashlib.sha256(result.stdout).hexdigest(), 'bytes': len(result.stdout)} if result.returncode == 0 else None
    source_versions[name] = {'before': original, 'after': current}
producer_records = [r for r in source_receipt['compiled'] if r['module'] in {
    'scripts.qd_ed_n36_readiness_prepare', 'scripts.qd_ed_n36_source', 'scripts.qd_ed_n34_source',
    'scripts.qd_ed_n36_build', 'scripts.qd_ed_n36_engineering_r1', 'scripts.qd_ed_gpu_probe'}]
inspection = {'status': 'READ_ONLY_IDENTITY_INSPECTION_NOT_PROOF_ACCEPTANCE',
    'references': refs, 'historical_producer_commit': source['commit'],
    'historical_producer_root': envelope['source_cwd'], 'historical_binding': source_receipt['binding'],
    'historical_producer_records': producer_records,
    'historical_compiled_record_count': len(source_receipt['compiled']),
    'historical_importlib_claim_names': sorted(source_receipt['frozen_importlib_aliases']),
    'consumer_before': before, 'consumer_after': after,
    'consumer_location': str(root), 'source_versions': source_versions,
    'retained_receipts_edited': False, 'readiness_validator_invoked_on_retained_proof': False}
(tmp/'retained-identity-inspection.json').write_text(json.dumps(inspection, indent=2)+'\n')
# Capture exact intermediate code for the 230-case run. The only subsequent
# changes were typed receipt-process validation and six terminal-shape tests.
prior = tmp/'focused-run-source'; prior.mkdir(exist_ok=True)
for name in changes:
    data = (root/name).read_text()
    if name == 'scripts/qd_ed_n36_source.py':
        added = """    for evidence in (receipt, runtime_receipt):
        require(isinstance(evidence, dict) and isinstance(evidence.get('binding'), dict)
                and evidence['binding'] == binding, 'N36 preparation receipt binding differs')
        owned_identity(evidence['binding']['process'])
"""
        assert data.count(added) == 1
        data = data.replace(added, '')
    if name == 'tests/test_n36_preparation_binding.py':
        data = data.split("\n\n@pytest.mark.parametrize('fault', ['pid_bool'")[0]
    path = prior/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(data)
manifest = {'base': before, 'committed_after': after,
    'committed_files': [record(root/name) for name in changes],
    'focused_run_files': [record(prior/name) for name in changes],
    'unchanged_regression_tests': [record(root/'tests'/name) for name in
        ('test_n36_importlib_alias.py', 'test_n36_frozen_alias.py')],
    'interpreter': record(Path('/home/hynx/miniconda3/envs/vla-pilot/bin/python').resolve()),
    'working_tree_clean': not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()}
(tmp/'source-test-provenance.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps({'commit': after, 'inspection': record(tmp/'retained-identity-inspection.json'),
                  'provenance': record(tmp/'source-test-provenance.json')}))
