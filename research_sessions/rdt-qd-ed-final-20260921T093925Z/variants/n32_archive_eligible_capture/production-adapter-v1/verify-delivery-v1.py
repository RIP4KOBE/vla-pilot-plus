"""Read-only committed-source verification; writes only this delivery directory."""
import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path.cwd().resolve()
out = root.parent / 'production-adapter-v1'
sys.path.insert(0, str(root))
from scripts import qd_ed_n32_bridge as b, qd_ed_n23_worker as w


def git(*args):
    return subprocess.check_output(['git', *args], cwd=root)


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


commit = git('rev-parse', 'HEAD').decode().strip()
parent = git('rev-parse', 'HEAD^').decode().strip()
assert parent == '1e50517b32b63ef9c6ad58cf56e522a436be01b8'
assert git('status', '--porcelain') == b''
paths = b.source_paths(root)
source = w.source_record(root, paths)
changed_names = set(git('diff', '--name-only', parent, commit).decode().splitlines())
assert changed_names <= paths
changed, invariants = [], []
for entry in source['files']:
    name = entry['path']
    if name in changed_names:
        exists = subprocess.run(['git', 'cat-file', '-e', parent + ':' + name], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        changed.append({**entry, 'parent_sha256': hashlib.sha256(git('show', parent + ':' + name)).hexdigest() if exists else None,
                        'status': 'modified' if exists else 'added'})
    else:
        before = hashlib.sha256(git('show', parent + ':' + name)).hexdigest()
        assert before == entry['sha256'], name
        invariants.append({**entry, 'parent_sha256': before})
assert len(changed) == 7 and len(invariants) == 538 and len(source['files']) == 545
assert all(not x['path'].startswith(('core/', 'main.py', 'configs/', 'scripts/qd_ed_n31_')) for x in changed)
path = 'scripts/qd_ed_final_runner.py'
def definitions(data):
    return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(data).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
before, after = definitions(git('show', parent + ':' + path)), definitions((root / path).read_text())
modified = [name for name in before if before[name] != after.get(name)]
assert set(modified) == {'validate_plan', 'check_budget', 'wait_exclusively'}
unchanged = {name: hashlib.sha256(value.encode()).hexdigest() for name, value in before.items() if value == after.get(name)}
old = json.loads((root.parent / 'release-preparation-v1/result-v1.json').read_text())['draft_plan']
assert ref(old['path']) == old
original_draft = json.loads(Path(old['path']).read_text())
assert original_draft['frozen'] is False and original_draft['release_enabled'] is False
result = {'schema': 'n32-production-committed-source-verification-v1', 'at': dt.datetime.now(dt.timezone.utc).isoformat(),
          'commit': commit, 'parent': parent, 'worktree_clean': True,
          'source_inventory': source, 'changed_files': changed, 'invariant_files': invariants,
          'generic_modified_definitions': modified, 'generic_new_definitions': sorted(set(after) - set(before)),
          'generic_unchanged_definition_ast_sha256': unchanged, 'unchanged_disabled_draft': old,
          'verification_script': ref(__file__)}
(out / 'committed-verification-v1.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'commit': commit, 'parent': parent, 'changed_source_files': len(changed),
                  'invariant_source_files': len(invariants), 'source_files': len(source['files']),
                  'unchanged_generic_definitions': len(unchanged), 'worktree_clean': True,
                  'original_draft_unchanged_disabled': True}))
