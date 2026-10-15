import ast,datetime,hashlib,json,subprocess
from pathlib import Path
root=Path.cwd();out=root.parent/'submodule-freeze-repair-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
def save(name,obj):(out/name).write_text(json.dumps(obj,indent=2)+'\n')
parent=git('rev-parse','HEAD^');commit=git('rev-parse','HEAD')
assert parent=='79f7cd2790cc667726a7cbe872a0a7f349a0e5b4'
changed=git('diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines()
assert changed==['scripts/qd_ed_n23_worker.py','tests/test_n32_submodule_freeze.py']
assert not git('status','--porcelain')
assert git('ls-tree',parent,'third_party/rdt')==git('ls-tree',commit,'third_party/rdt')
assert git('show',parent+':scripts/qd_ed_n32_bridge.py')==Path('scripts/qd_ed_n32_bridge.py').read_text().strip()
rows=[]
for folder in ('scripts','tests'):
 for path in sorted(Path(folder).glob('*.py')):
  text=path.read_text()
  if 'source_record(' not in text and 'verify_source(' not in text:continue
  tree=ast.parse(text)
  calls=[]
  for n in ast.walk(tree):
   if not isinstance(n,ast.Call):continue
   name=n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else None
   if name in ('source_record','verify_source'):calls.append({'line':n.lineno,'call':ast.get_source_segment(text,n)})
  if calls:rows.append({'path':str(path),'calls':sorted(calls,key=lambda x:x['line'])})
save('caller-inventory-v1.json',rows)
roundtrip=json.loads((out/'roundtrip-result-v1.json').read_text())
material=json.loads((out/'materialization-v1.json').read_text())
database=Path(material['object_database'])
for name,digest in material['shared_administration_hashes'].items():assert sha(database/name)==digest
save('final-checks-v1.json',{'parent':parent,'commit':commit,'git_status_porcelain':'','gitlink_unchanged':True,'attest_loaded_and_inventory_unchanged':True,'shared_submodule_administration_unchanged':True,'changed_paths':[{'path':p,'sha256':sha(root/p)} for p in changed],'caller_files':len(rows),'caller_calls':sum(len(x['calls']) for x in rows)})
# Preserve the initial diagnostic failure; the second run passed after authorized materialization.
save('tests-v1-command.json',{'argv':['python','-m','pytest','-q','-p','no:cacheprovider','--basetemp=../submodule-freeze-repair-v1/pytest-tmp','tests/test_n32_submodule_freeze.py','tests/test_n32_source_closure.py','tests/test_n32_release.py','-k','submodule_freeze or source_closure or source_requires_committed_bytes or loaded_checkout_rejection'],'exit':1,'passed':29,'errors':1,'reason':'real release fixture read required RDT file before materialization','log':'tests-v1.log','sha256':sha(out/'tests-v1.log')})
remaining=[
'Root review/adoption of commit '+commit+' and pinned materialization provenance is still required; no owning source has been adopted.',
'Future execution checkout must contain the pinned local RDT objects and regular source files. This repair materialized only scripts/maniskill_model.py; the remainder of RDT (models, configs, etc.) is absent here and full model/runtime readiness was not tested.',
'Create and validate a fresh prospective runtime/manifest binding in the intended execution checkout under separate authorization, with a distinct cohort/attempt identity. No release or prospective launch manifest was generated in this leaf.',
'Before any GPU cohort, obtain separate accounting amendment, root review and source/release freeze. Preserve terminal invalid n32_dev_t00_c0_20261004 and its 706.4010170580586 seconds / 0.19622250473834962 GPUh unchanged.'
]
report=f'''# Arbor engineering leaf 15.2: pinned submodule source freeze

Committed CPU integration repair: `{commit}`, parent `{parent}`, branch `{git('branch','--show-current')}`. Working tree is clean. No scientific score or success is claimed.

## Implementation and compatibility

Only `scripts/qd_ed_n23_worker.py` and `tests/test_n32_submodule_freeze.py` changed. The single explicit cross-gitlink allowlist entry is `third_party/rdt/scripts/maniskill_model.py`. The frozen superproject commit identifies its gitlink commit; that exact commit must exist as a commit object in the local common Git directory's `modules/third_party/rdt` database. The pinned tree must contain a regular blob, and the repository-local regular-file bytes must equal it. Submodule HEAD and adjacent worktree bytes are never source inputs. Object replacement is disabled and lazy fetching is disabled. Missing objects fail closed.

The existing record format remains `commit/files/sha256` with `path/sha256` rows. The superproject commit transitively binds the gitlink and blob; no mutable HEAD field or new optional provenance field weakens equality. `verify_source` still regenerates and compares the entire record. Root must be the Git top-level directory; canonical relative paths and every path component are checked against symlinks. As before, identical committed checkouts can share a content record: execution root binding remains enforced by the unchanged release/context checks and `attest_loaded`.

Reviewed all {len(rows)} caller files / {sum(len(x['calls']) for x in rows)} call sites captured in `caller-inventory-v1.json`, including internal worker calls and focused tests. Prepare/backend/contract paths supply explicit inventories, bridge/preflight/release paths verify complete records, and worker contexts reconstruct records. No signature or schema migration is needed. Historical reverse-source allowlists remain unchanged and are not silently reapproved by this repair. N32 inventory completeness and unknown/adjacent loaded-module rejection are unchanged. Science, thresholds, attestation scope, and accounting are untouched.

## Pinned materialization

Superproject parent pins RDT `{material['gitlink_commit']}`; blob `{material['blob']}`, SHA-256 `{material['sha256']}`, {material['bytes']} bytes. `materialize-v1.py` used read-only local Git object commands and an exclusive regular-file write inside this worktree. It created no `.git` pointer, ran no submodule checkout/init, and changed no gitlink or shared administrative files. Exact commands, paths, object IDs and before/after shared administration hashes are in `materialization-v1.json`. Only the required file was materialized.

## CPU validation

CUDA was hidden and numerical thread counts limited to two. No GPU, provider, model or simulator calls occurred. Test temporary repositories are contained in this report directory.

- Initial focused run: 29 passed, one fixture setup error because materialization had not yet occurred; retained in `tests-v1.log`.
- Final focused run: 33 passed, 55 deselected, exit 0 (`tests-v2.json` and `tests-v2.log`). Covers pinned bytes despite unrelated database HEAD, linked worktrees, missing/modified/wrong-pin files, missing database/objects, invalid pin object type, wrong root, file/parent/committed symlinks, unknown sources, record/hash/commit tampering, changed gitlink, and compatible regular files. Existing real closure and loaded-source rejection tests passed. One existing invalid-escape SyntaxWarning in `core/fkd_class.py` remains.
- Post-commit complete real inventory: {roundtrip['source_file_count']} files; `source_record` and strict `verify_source` passed. Digest `{roundtrip['source_sha256']}`. Six actually loaded repository modules also passed unchanged attestation. An import guard rejected model/simulator imports; none occurred. Exact record, command, environment and outputs are in `source-record-v1.json`, `roundtrip-v1.json`, and `roundtrip-result-v1.json`.
- `git diff --check` passed; only the two intended source/test paths were committed. Parent, clean status, unchanged gitlink and shared administration were checked after the roundtrip.

## Remaining prerequisites

'''+ '\n'.join('- '+x for x in remaining)+'''

No release generation, launch, owning tree/ledger mutation, source adoption, new agents, protected evaluation or scientific evaluation occurred. The old invalid attempt and its charge remain immutable.

Applied skills: [Arbor entrypoint](/home/hynx/.codex/skills/arbor-research-agent/SKILL.md), [orchestrator](/home/hynx/.codex/skills/arbor-agent-orchestrator/SKILL.md), [executor](/home/hynx/.codex/skills/arbor-agent-executor/SKILL.md). User restrictions govern this continuation; no coordinator/tree updates or new agents were used.
'''
(out/'report-v1.md').write_text(report)
artifacts=[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.is_file() and p.name!='result-v1.json' and not p.name.startswith('executor-')]
save('result-v1.json',{'schema':'n32-submodule-freeze-repair-result-v1','completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'CPU_PINNED_SOURCE_INTEGRATION_PASSED_COMMITTED_ROOT_REVIEW_REQUIRED','parent':parent,'commit':commit,'changed_paths':[{'path':p,'sha256':sha(root/p)} for p in changed],'materialized_source':{k:material[k] for k in ('materialized_path','gitlink_commit','blob','sha256','bytes')},'tests':{'passed':33,'exit':0,'log':'tests-v2.log'},'real_inventory_roundtrip':{'files':roundtrip['source_file_count'],'sha256':roundtrip['source_sha256'],'exit':0,'after_commit':True},'artifacts':artifacts,'inputs':[{'path':str(p),'sha256':sha(p)} for p in (Path('../root-source-closure-review-v1.json'),Path('../source-closure-repair-v1/result-v1.json'))],'remaining_prerequisites':remaining,'gitlink_changed':False,'attest_loaded_changed':False,'owning_records_modified':False,'root_adoption_required':True,'release_generated':False,'launched':False,'scientific_success':None,'old_attempt_id':'n32_dev_t00_c0_20261004','old_attempt_remains_terminal_and_charged':True,'immutable_old_seconds':706.4010170580586,'immutable_old_gpu_hours':0.19622250473834962})
print(json.dumps({'commit':commit,'report':str(out/'report-v1.md'),'result':str(out/'result-v1.json'),'artifact_count':len(artifacts)},indent=2))
