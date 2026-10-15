"""Read-only verification of the committed CPU delivery and its external draft."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
root = Path.cwd().resolve()
sys.path.insert(0, str(root))
from scripts import qd_ed_n32_bridge as b, qd_ed_n32_contract as c, qd_ed_n23_worker as w
report_dir = root.parent / 'release-preparation-v1'
plan_path = report_dir / 'draft-v1/plan.draft.json'
plan = w.read_ref(c.ref(plan_path))
c.validate_draft(plan)
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
parent = subprocess.check_output(['git', 'rev-parse', 'HEAD^'], text=True).strip()
assert parent == '260f19ed29c38aa1c361fda50acb3abdf7fb0af0'
assert plan['source']['commit'] == commit
w.verify_source(root, plan['source'])
assert b.source_paths(root) == {v['path'] for v in plan['source']['files']}
runtime = w.read_ref(plan['runtime'])
manifest_refs = []
for row in plan['episodes']:
    reference = plan['expected_manifests'][row['episode_key']]
    actual = w.read_ref(reference)
    assert actual == json.loads(json.dumps(b.manifest(plan, runtime, row)))
    manifest_refs.append(reference)
# Exercise the production trust-chain verifier with actual committed files.
b.verify_manifest(plan['expected_manifests'][plan['episodes'][2]['episode_key']], plan, runtime, plan['episodes'][2])
changes = subprocess.check_output(['git', 'diff', '--name-status', parent, commit], text=True).splitlines()
assert len(changes) == 9 and all(line.startswith('A\t') for line in changes)
changed_names = {line.split('\t', 1)[1] for line in changes}
changed, invariant = [], []
for record in plan['source']['files']:
    (changed if record['path'] in changed_names else invariant).append(record)
    if record['path'] not in changed_names:
        prior = subprocess.check_output(['git', 'show', parent + ':' + record['path']])
        assert hashlib.sha256(prior).hexdigest() == record['sha256']
assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
assert not Path(plan['artifact_root']).exists()
assert (root / 'configs/qd_ed_final/n31_dev_task_identities.json').read_bytes() == (root.parent.parent / 'n31_capture_dwell_proposal/dev-task-identities-v1.json').read_bytes()
result = {'schema': 'n32-committed-draft-verification-v1', 'commit': commit, 'parent': parent,
          'source_inventory_count': len(plan['source']['files']), 'changed': changed, 'invariant': invariant,
          'changed_sha256': w.canonical_sha(changed), 'invariant_sha256': w.canonical_sha(invariant),
          'plan': c.ref(plan_path), 'expected_manifests': manifest_refs,
          'manifest_count': len(manifest_refs), 'worktree_clean': True, 'old_tracked_files_modified': 0,
          'runtime_worktree': runtime['worktree'], 'prospective_worktree': plan['worktree'],
          'actual_source_verification': True, 'all_manifests_recomposed': True,
          'artifacts_directory_absent': True, 'gpu_dispatched': False, 'release_enabled': False}
w.atomic_json(report_dir / 'committed-verification-v1.json', result)
w.atomic_json(report_dir / 'source-inventory-v1.json', plan['source'])
print(json.dumps({k: v for k, v in result.items() if k not in {'changed', 'invariant', 'expected_manifests'}}))
