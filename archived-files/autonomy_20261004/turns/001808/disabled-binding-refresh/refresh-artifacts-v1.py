"""CPU-only, write-once disabled projections; no production imports or adoption."""
import ast
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import types

OUT = Path(__file__).resolve().parent
TURNS = OUT.parents[1]
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree')
DEPLOY = ROOT.parent.parent / 'n36_engineering_adapter_001482/implementation_worktree'
FINAL = '0d618606a933473eb0e5a02fc3659a3a0ea0ee25'
BASE = 'a5b32cdefc0879e98011f86b1559e4250926ba62'
SCIENCE = '1065f38122379a515b60a9a424f574330405b66f'
START = time.monotonic()
checks, inputs, outputs, boundaries = [], {}, {}, []

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': sha(path)}

def read(path):
    path = Path(path)
    result = json.loads(path.read_bytes())
    inputs[str(path)] = ref(path)
    return result

AUTH = read(OUT / 'authority-v1.json')

def guard():
    assert time.monotonic() - START < 1050, 'executor local work limit'
    assert dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(AUTH['stop_authority']['deadline'].replace('Z', '+00:00')), 'deadline'
    for p in AUTH['stop_authority']['paths'] + [str(TURNS.parent / 'STOP')]:
        assert not os.path.lexists(p), 'STOP: ' + p

def emit(name, value):
    guard()
    path = OUT / name
    with path.open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')
    result = ref(path)
    outputs[name] = {**result, 'bytes': path.stat().st_size}
    return result

def bound(r):
    assert sha(r['path']) == r['sha256'], 'reference mismatch: ' + r['path']
    return read(r['path'])

def git(*args, root=ROOT):
    guard()
    cmd = ['git', '--no-replace-objects', '-C', str(root), *args]
    p = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, 'GIT_NO_LAZY_FETCH': '1', 'GIT_OPTIONAL_LOCKS': '0'})
    checks.append({'command': cmd, 'returncode': p.returncode, 'stdout': p.stdout.strip(), 'stderr': p.stderr.strip()})
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()

def ast_functions(path, names, namespace):
    path = Path(path)
    inputs[str(path)] = ref(path)
    tree = ast.parse(path.read_bytes())
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in selected} == set(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace

def literal(path, name):
    tree = ast.parse(Path(path).read_bytes())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
            return ast.literal_eval(n.value)
    raise KeyError(name)

def canon(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def changes(a, b, prefix=''):
    if a == b:
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        result = []
        for k in sorted(set(a) | set(b)):
            key = prefix + '/' + k.replace('~', '~0').replace('/', '~1')
            if k not in a or k not in b:
                result.append(key)
            else:
                result += changes(a[k], b[k], key)
        return result
    return [prefix]

def delta_record(name, previous, candidate, old_ref, new_ref):
    boundaries.append({'boundary': name, 'before': old_ref, 'after': new_ref,
                       'changed_json_pointers': changes(previous, candidate),
                       'unchanged_top_level_fields': [k for k in previous if k in candidate and previous[k] == candidate[k]]})

def expected_reject(label, call, expected):
    try:
        call()
    except ValueError as e:
        assert str(e) == expected, (label, str(e))
        checks.append({'check': label, 'method': 'unaltered production function AST with real hash-reading dependencies; no production module import',
                       'result': 'EXPECTED_REJECTION', 'reason': str(e)})
    else:
        raise AssertionError('unexpected acceptance: ' + label)

guard()
assert git('rev-parse', 'HEAD') == FINAL
assert git('status', '--porcelain', '--untracked-files=no') == ''
assert git('rev-parse', 'HEAD', root=DEPLOY) == BASE
assert git('status', '--porcelain', '--untracked-files=no', root=DEPLOY) == ''
git('merge-base', '--is-ancestor', BASE, FINAL)
git('cat-file', '-t', SCIENCE)
changed = git('diff', '--name-only', BASE, FINAL, '--').splitlines()
assert set(changed) == {'scripts/qd_ed_n36_readiness_prepare.py', 'scripts/qd_ed_n36_source.py',
                        'tests/test_n36_preparation_binding.py', 'tests/test_n36_readiness_prepare.py'}
assert git('diff', '--name-only', BASE, FINAL, '--', 'core', 'configs', 'scripts/qd_ed_n36_contract.py') == ''
reviews = {t: read(TURNS / t / 'scoped-root-review-v1.json') for t in ('001799', '001803', '001807')}
approved_ref = ref(TURNS / '001804/source-scope-amendment-v1.json')
approved = bound(approved_ref)
assert approved_ref['sha256'] == AUTH['amendment']['sha256']
assert reviews['001807']['source'] == FINAL and reviews['001807']['source_adopted'] is False
graph_ref = ref(TURNS / '001784/graph.complete-disabled-v1.json')
graph = bound(graph_ref)
accept = read(TURNS / '001787/root-b5-acceptance-v1.json')
assert accept['graph']['sha256'] == graph_ref['sha256'] and accept['source']['commit'] == BASE
old = {k: bound(graph[k]) for k in ('specification', 'policy', 'source_record', 'runtime', 'runtime_closure', 'native_build', 'controller_semantics')}
spec0 = old['specification']
old_amendment = bound(spec0['runtime_binding']['amendment'])
old_authority = bound(spec0['runtime_binding']['repair_authority'])

# Load only pure source-inventory functions, with their actual standard-library dependencies.
w_ns = dict(Path=Path, hashlib=hashlib, json=json, subprocess=subprocess, os=os)
ast_functions(ROOT / 'scripts/qd_ed_n23_worker.py', ['require', 'sha', 'canonical_sha', 'read_ref', '_source_git', '_source_entry'], w_ns)
w = types.SimpleNamespace(**{k: v for k, v in w_ns.items() if callable(v)})
ns = dict(Path=Path, hashlib=hashlib, json=json, subprocess=subprocess, os=os, w=w,
          RDT='third_party/rdt', LEROBOT='third_party/lerobot', LIBERO='third_party/libero_pro',
          PINNED_SUBMODULES={'third_party/rdt': 'scripts/maniskill_model.py', 'third_party/lerobot': 'src/lerobot/__init__.py'},
          SOURCE_SUFFIXES=('.py', '.yaml', '.yml', '.json'))
ast_functions(ROOT / 'scripts/qd_ed_n34_source.py', ['submodule_pin', 'submodule_paths', 'dependency_paths', '_source_tree', '_source_blobs', 'source_record'], ns)
required = literal(ROOT / 'scripts/qd_ed_final_runner.py', 'REQUIRED_CODE')
required.update(str(p.relative_to(ROOT)) for folder in ('core', 'utils', 'vlm_query') for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in {'.py', '.txt'})
b_ns = dict(Path=Path, ROOT=ROOT, runner=types.SimpleNamespace(REQUIRED_CODE=required), closure=types.SimpleNamespace(dependency_paths=ns['dependency_paths']))
ast_functions(ROOT / 'scripts/qd_ed_n36_bridge.py', ['source_paths'], b_ns)
paths = b_ns['source_paths'](ROOT)
assert not any('2026-08-10-eds-qd-stage-guidance-transition-design.md' in p or p.startswith('data/') for p in paths)
source = ns['source_record'](ROOT, paths, commit=FINAL)
source_ref = emit('source-record.json', source)
checks.append({'check': 'production source_paths + source_record via unmodified AST', 'result': 'PASS', 'files': len(source['files']),
               'scope': 'local committed source bytes and pinned dependency Git objects; no runtime imports, provider calls, result files or credentials'})
idx = {v['path']: v['sha256'] for v in source['files']}
old_idx = {v['path']: v['sha256'] for v in old['source_record']['files']}
inventory_delta = sorted(p for p in set(idx) | set(old_idx) if idx.get(p) != old_idx.get(p))
assert inventory_delta == sorted(changed)
emit('source-delta-v1.json', {'schema': 'n36-disabled-source-delta-v1', 'source': source_ref, 'previous_source': graph['source_record'],
    'source_adopted': False, 'observed_checkout': str(ROOT), 'required_deployment_checkout': str(DEPLOY),
    'scientific_source_anchor': SCIENCE, 'scientific_changes_relative_to_accepted_source': False,
    'frozen_core_configs_contract_unchanged': True, 'changed_paths': changed,
    'files': [{'path': p, 'before_sha256': old_idx.get(p), 'after_sha256': idx[p], 'bytes': (ROOT / p).stat().st_size} for p in changed],
    'unchanged_inventory_paths': sorted(set(old_idx) - set(changed)),
    'limitation': 'Scientific anchor is retained, not an assertion that all operational files equal that older commit.'})

runtime = copy.deepcopy(old['runtime'])
runtime['preparation']['source'] = FINAL
runtime['preparation']['source_record'] = source_ref
assert runtime['preparation']['runtime_ready'] is False and runtime['cuda_egl_verified'] is False and runtime['provider_ready'] is False
runtime_ref = emit('disabled-runtime.json', runtime)
delta_record('runtime', old['runtime'], runtime, graph['runtime'], runtime_ref)
baseline = bound(spec0['canonical_runtime'])
baseline['preparation']['source'] = FINAL
baseline['preparation']['source_record'] = source_ref
assert baseline == runtime
checks.append({'check': 'exact immutable canonical runtime projection', 'result': 'PASS', 'only_changed_fields': ['preparation.source', 'preparation.source_record'],
               'readiness': False, 'file_inventory_rehashed': False})

closure = copy.deepcopy(old['runtime_closure'])
closure['runtime'] = runtime_ref
placement = []
for name, row in closure['modules'].items():
    p = Path(row['path'])
    if p.is_relative_to(DEPLOY):
        rel = str(p.relative_to(DEPLOY))
        assert rel in idx
        before = copy.deepcopy(row)
        row['sha256'] = idx[rel]
        if row != before:
            placement.append({'module': name, 'path': str(p), 'observed_sha256': sha(p), 'required_sha256': row['sha256'], 'source_path': str(ROOT / rel)})
assert [p['module'] for p in placement] == ['scripts.qd_ed_n36_source']
assert all(p['observed_sha256'] != p['required_sha256'] for p in placement)
closure_ref = emit('runtime-closure.prospective-disabled-v1.json', closure)
delta_record('runtime_closure', old['runtime_closure'], closure, graph['runtime_closure'], closure_ref)
emit('closure-placement-prerequisite-v1.json', {'schema': 'n36-disabled-closure-placement-prerequisite-v1',
    'runtime_closure': closure_ref, 'status': 'EXPECTED_FUTURE_INVENTORY_NOT_DEPLOYED', 'source': source_ref,
    'source_adopted': False, 'loaded_module_attestation': False, 'mismatches': placement,
    'unmodified_external_modules_reused': len(closure['modules']) - len(placement),
    'native_build_reused_exact': graph['native_build'], 'production_closure_validation': 'NOT_CLAIMED; known deployed source-module hash mismatch'})
emit('native-binding.disabled-v1.json', {'schema': 'n36-disabled-native-binding-refresh-v1', 'status': 'DISABLED_STATIC_REFERENCE_ONLY',
    'source': source_ref, 'runtime': runtime_ref, 'runtime_closure': closure_ref,
    'native_build': graph['native_build'], 'native_inventory_changed': False,
    'native_libraries_rehashed': False, 'native_execution_observed': False,
    'basis': ref(TURNS / '001787/root-b5-acceptance-v1.json'), 'basis_scope': 'unchanged native inventory only; historical B5 does not accept this graph'})

# Compose an amendment proposal without copying any historical approval into a new attestation.
allowlist = sorted(set(spec0['runtime_binding']['source_change_allowlist']) | set(approved['additional_allowed_source_paths']))
amendment = {'schema': 'n36-disabled-source-scope-composition-v1', 'status': 'DISABLED_PENDING_POLICY_ADMISSION',
    'node_id': '15.6', 'source': source_ref, 'source_base': spec0['runtime_binding']['source_base'],
    'approved_prospective_scope': approved_ref, 'implementation_review': ref(TURNS / '001807/scoped-root-review-v1.json'),
    'previous_runtime_amendment': spec0['runtime_binding']['amendment'],
    'code_change_scope': old_amendment['code_change_scope'][:3],
    'new_allowed_entrypoints': sorted(set(old_amendment['new_allowed_entrypoints']) | set(approved['additional_allowed_source_paths'])),
    'exact_source_change_allowlist': allowlist,
    'scientific_source_anchor': SCIENCE, 'scientific_changes_authorized': False, 'release_enabled': False,
    'deployment_authorized': False, 'source_adopted': False, 'provider_measurement_authorized': False,
    'gpu_authorized': False, 'new_repair_authority': None,
    'limitation': 'Prospective composition only. Existing repair authority pins the old amendment; this document is not a replacement approval.'}
amendment_ref = emit('amendment.prospective-disabled-v1.json', amendment)
policy = copy.deepcopy(old['policy'])
for key in policy:
    if key.endswith('_path'):
        policy[key] = str(OUT / ('pending-' + Path(policy[key]).name))
policy['disabled_runtime_path'] = runtime_ref['path']
policy['previous_specification'] = graph['specification']
policy['resource_id'] = None
policy_ref = emit('preparation-policy.unassigned-disabled-v1.json', policy)
delta_record('policy', old['policy'], policy, graph['policy'], policy_ref)
spec = copy.deepcopy(spec0)
spec['runtime_binding'].update(amendment=amendment_ref, source_change_allowlist=allowlist,
    preparation=policy_ref, runtime_path=str(OUT / 'pending-measured-runtime.json'), source_record_path=source_ref['path'])
spec_ref = emit('specification.prospective-disabled-v1.json', spec)
delta_record('specification', spec0, spec, graph['specification'], spec_ref)
assert all(spec[k] == spec0[k] for k in spec0 if k != 'runtime_binding')
assert not spec['release_enabled'] and not spec['root_adopted']

# Reproduce the two policy blockers without importing production, touching ledgers, or calling recovery admission.
e_ns = dict(Path=Path, hashlib=hashlib, json=json, w=w)
ast_functions(ROOT / 'scripts/qd_ed_n36_engineering_r1.py', ['reference', 'read', 'exact', '_recovery_json', '_recovery_read', '_recovery_specification'], e_ns)
e_ns['SPECIFICATION'] = spec_ref
e_ns['HISTORICAL_SPECIFICATION'] = literal(ROOT / 'scripts/qd_ed_n36_engineering_r1.py', 'HISTORICAL_SPECIFICATION')
bound(e_ns['HISTORICAL_SPECIFICATION'])
expected_reject('prospective specification admission', lambda: e_ns['_recovery_specification'](spec), 'immutable scientific and accounting specification')
e = types.SimpleNamespace(**{k: v for k, v in e_ns.items() if callable(v)})
e.w = w
p_ns = dict(e=e, Path=Path, SCHEMA=literal(ROOT / 'scripts/qd_ed_n36_readiness_prepare.py', 'SCHEMA'),
    FIELDS=literal(ROOT / 'scripts/qd_ed_n36_readiness_prepare.py', 'FIELDS'),
    MEASUREMENT_CONTRACT=literal(ROOT / 'scripts/qd_ed_n36_readiness_prepare.py', 'MEASUREMENT_CONTRACT'))
ast_functions(ROOT / 'scripts/qd_ed_n36_readiness_prepare.py', ['policy', 'closed'], p_ns)
expected_reject('refreshed amendment versus historical repair authority', lambda: p_ns['policy'](spec), 'readiness amendment authority')
minimal = copy.deepcopy(spec0)
minimal['runtime_binding']['source_change_allowlist'] = allowlist
expected_reject('allowlist-only prospective amendment cannot use old policy', lambda: p_ns['policy'](minimal), 'readiness scoped changes')

controller = {k: copy.deepcopy(old['controller_semantics'][k]) for k in ('schema', 'class', 'instance', 'instance_scope', 'module', 'source', 'semantics')}
controller.update(status='PENDING_ROOT_REVIEW_DISABLED', runtime=runtime_ref, runtime_closure=closure_ref,
    source_commit=FINAL, review_evidence={}, historical_review_only=graph['controller_semantics'],
    root_acceptance=None, b5_review=None, independent_review_claimed=False, native_execution_observed=False,
    physical_gain_certified=False, production_eligible=False, readiness_eligible=False, release_enabled=False,
    scientific_promotion=False, gpu_authorized=False)
controller_ref = emit('controller-semantics.pending-disabled-v1.json', controller)
delta_record('controller_semantics', old['controller_semantics'], controller, graph['controller_semantics'], controller_ref)
ctrl_ns = dict(w=w, math=__import__('math'), FIELDS=literal(ROOT / 'scripts/qd_ed_n34_controller.py', 'FIELDS'))
ast_functions(ROOT / 'scripts/qd_ed_n34_controller.py', ['verify_semantics'], ctrl_ns)
expected_reject('unreviewed controller cannot admit new runtime', lambda: ctrl_ns['verify_semantics'](controller_ref, runtime_ref, closure), 'reviewed controller semantics required')

pending = ['plan', 'audit', 'full40_manifests', 'separate_engineering_manifest', 'scientific_equivalence', 'relocation_map',
           'recovery_prefix_contract', 'root_controller_acceptance', 'root_acceptance', 'b5_review', 'authority']
new_graph = copy.deepcopy(graph)
new_graph.update(schema='n36-disabled-binding-refresh-partial-graph-v1', specification=spec_ref, policy=policy_ref,
    amendment=amendment_ref, source_record=source_ref, runtime=runtime_ref, runtime_closure=closure_ref,
    controller_semantics=controller_ref, native_build=graph['native_build'], resource_id=None,
    status='DISABLED_BLOCKED_POLICY_ADMISSION_AND_SOURCE_PLACEMENT', graph_complete=False, graph_verified=False,
    review_status='NEW_SOURCE_BOUND_REVIEW_REQUIRED', independent_review_claimed=False, source_adopted=False,
    scientific_source_anchor=SCIENCE, historical_graph_only=graph_ref,
    recovery_identity_status='UNASSIGNED; prior graph resource cannot authorize new measurement',
    historical_accounting_only={'recovery_of': graph['recovery_of'], 'retained_charge_gpu_hours': graph['retained_charge_gpu_hours']})
new_graph.pop('recovery_of')
new_graph.pop('retained_charge_gpu_hours')
for key in pending:
    new_graph[key] = None
new_graph_ref = emit('graph.partial-disabled-v1.json', new_graph)
delta_record('graph', graph, new_graph, graph_ref, new_graph_ref)

# Exact before/after boundary coverage; source-bound historical leaves are never accepted for this graph.
graph_boundaries = []
for key, value in graph.items():
    if isinstance(value, dict) and 'path' in value and 'sha256' in value:
        if key == 'native_build':
            state = 'REUSED_EXACT_UNCHANGED_NATIVE_INVENTORY_ONLY'
        elif key in pending:
            state = 'UNFILLED_AFFECTED_OR_REVIEW_SLOT; HISTORICAL_REFERENCE_NOT_CARRIED_FORWARD'
        else:
            state = 'REFRESHED_CANDIDATE_NOT_ADMITTED'
        graph_boundaries.append({'slot': key, 'before': value, 'after': new_graph.get(key), 'disposition': state})
boundary_ref = emit('boundary-manifest-v1.json', {'schema': 'n36-disabled-binding-boundaries-v1',
    'artifact_field_boundaries': boundaries, 'graph_reference_boundaries': graph_boundaries,
    'source_inventory_delta': inventory_delta,
    'unchanged': ['all source inventory paths listed in source-delta-v1.json except the exact four changes',
        'scientific source anchor 1065f38122379a515b60a9a424f574330405b66f',
        'all specification top-level fields outside runtime_binding (including scientific rules, scope, accounting and frozen thresholds)',
        'runtime outside preparation.source and preparation.source_record',
        'closure outside runtime and modules.scripts.qd_ed_n36_source.sha256',
        'native manifest bytes/reference; no native library rescan',
        'controller instance, semantics, source module identity and expected configuration',
        'every historical file; both worktree HEADs and tracked bytes; owner state, ledgers, checkpoints and locks'],
    'historical_only': ['001787 B5 acceptance', '001783 controller root review and its evidence leaves',
        'old source-bound full40, engineering manifest, audit, plan and scientific-equivalence evidence',
        'old recovery-prefix contract and consumed preparation resource identity'],
    'not_claimed': ['fresh native execution', 'loaded controller behavior', 'full production graph validation', 'independent review', 'scientific score']})
checks.append({'check': 'closure placement', 'result': 'BLOCKED', 'mismatches': placement})
checks.append({'check': 'deployed preparation checkout predicate at readiness_prepare.py:109-110', 'result': 'BLOCKED',
    'required_source_cwd': str(DEPLOY), 'observed_final_source_cwd': str(ROOT), 'deployed_head': BASE, 'required_head': FINAL})
checks.append({'check': 'controller review leaf runtime bindings', 'result': 'NOT_REUSED',
    'reason': 'Historical controller evidence pins the old runtime digest; root reviewer must supply fresh source/runtime-bound evidence.'})
validation_ref = emit('validation-results-v1.json', {'schema': 'n36-disabled-refresh-validation-v1',
    'command': ['python', '-B', str(OUT / 'refresh-artifacts-v1.py')], 'checks': checks,
    'production_imports': False, 'tests_rerun': False, 'full_graph_validation': False,
    'source_record_function_body_unchanged': True, 'guard_function_bodies_unchanged': True})
assert git('rev-parse', 'HEAD') == FINAL
assert git('status', '--porcelain', '--untracked-files=no') == ''
assert git('rev-parse', 'HEAD', root=DEPLOY) == BASE
assert git('status', '--porcelain', '--untracked-files=no', root=DEPLOY) == ''
guard()
prerequisites = [
    {'id': 'P1', 'status': 'BLOCKED', 'requirement': 'Separate scoped policy admission repair/review is required before this amendment can be selected. The current _recovery_specification freezes amendment and allowlist; readiness policy pins the old repair authority/amendment pair.',
     'symbols': ['scripts/qd_ed_n36_engineering_r1.py:_recovery_specification', 'scripts/qd_ed_n36_readiness_prepare.py:policy'],
     'scope': 'Coordinator must authorize exact prospective scope handling without changing scientific/accounting projection, generic episode acceptance or history. This executor is not authorized to edit source or issue replacement authority.',
     'evidence': validation_ref},
    {'id': 'P2', 'status': 'BLOCKED', 'requirement': 'Separate owning-root source placement authority must advance the fixed adapter checkout from a5b32cdefc0879e98011f86b1559e4250926ba62 to the final reviewed commit (currently 0d618606a933473eb0e5a02fc3659a3a0ea0ee25). A subsequent P1 repair would need its own final-commit review and regenerated bindings.',
     'source_cwd': str(DEPLOY), 'readiness_predicate': 'plan.worktree == resolved engineering_r1 module checkout == e.SOURCE',
     'preserve': 'tracked cleanliness, untracked and historical files, pinned dependency bytes; no checkout/reset/cherry-pick performed here'},
    {'id': 'P3', 'status': 'PENDING_ROOT_REVIEW', 'requirement': 'Supply fresh controller review evidence and source/runtime/closure-bound independent B5 plus root acceptance after valid placement/policy composition. Regenerate dependent audit/manifests/plan only then; prior scientific values remain frozen.'},
    {'id': 'P4', 'status': 'UNASSIGNED_NOT_RELEASED', 'requirement': 'Before any new measurement, assign a fresh preparation resource identity and reconcile its prospective recovery/accounting partition under owning authority; issue a separately reviewed finite release. No identity, accounting adoption, release or measurement is created here.'}]
for script_name in ('refresh-artifacts-v1.py', 'verify-artifacts-v1.py'):
    script_path = OUT / script_name
    outputs[script_name] = {**ref(script_path), 'bytes': script_path.stat().st_size}
report = {'schema': 'n36-disabled-binding-refresh-cpu-report-v1', 'at': dt.datetime.now(dt.timezone.utc).isoformat(),
    'node_id': '15.6', 'status': 'PARTIAL_ARTIFACT_REFRESH_BLOCKED', 'authority': ref(OUT / 'authority-v1.json'),
    'source': FINAL, 'scientific_source': SCIENCE, 'previous_accepted_source': BASE,
    'worktree': str(ROOT), 'deployment_worktree': str(DEPLOY), 'source_adopted': False,
    'outputs': outputs.copy(), 'input_hashes': list(inputs.values()), 'boundary_manifest': boundary_ref,
    'validation': validation_ref, 'unresolved_review_obligations_and_prerequisites': prerequisites,
    'changed_boundary_list': [b['boundary'] for b in boundaries] + ['source_record', 'amendment', 'native binding wrapper (native leaf unchanged)'],
    'unchanged_boundary_list': json.loads(Path(boundary_ref['path']).read_text())['unchanged'],
    'next_concrete_command': ['python', '-B', str(OUT / 'verify-artifacts-v1.py'), '--report', str(OUT / 'report-v1.json')],
    'next_command_purpose': 'Read-only handoff verification of the completed blocked packet. Coordinator then resolves P1/P2; no command here adopts source or enables release.',
    'gpu_authorized': False, 'provider_measurement_authorized': False, 'release_enabled': False,
    'graph_complete': False, 'graph_verified': False, 'historical_proof_eligible': False,
    'fresh_preparation_resource_created': False, 'owner_state_written': False, 'ledger_reads': False,
    'ledger_writes': False, 'driver_locks': False, 'protected_results_read': False, 'credentials_read': False,
    'score': None, 'code_ref': FINAL,
    'result': 'Fresh committed source inventory and disabled runtime/closure/specification/amendment/controller projections produced; native leaf reused exactly. Production admission intentionally blocked on policy and placement, with no stale review adoption.',
    'insight': 'Extending preparation NEW_FILES admits the source subset but does not extend the immutable prospective specification projection or the pinned amendment-authority pair. Deployment is a second independent prerequisite.',
    'elapsed_seconds': time.monotonic() - START,
    'route': 'Current executor session only; no provider/client invocation or credential access; no separate identity attestation fabricated.'}
emit('report-v1.json', report)
print(json.dumps({'report': outputs['report-v1.json'], 'status': report['status'], 'source_files': len(source['files']), 'outputs': len(outputs)}, indent=2))
