"""Independent, stdlib-only B5 checks. No production module imports or releases."""
import ast
import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import types
from decimal import Decimal

OUT = Path(__file__).parent
AUTH = json.loads((OUT / 'authority-v1.json').read_text())
ROOT = Path(AUTH['worktree'])
checks, evidence, definitions = [], {}, []

def check(name, condition, detail=None):
    checks.append({'check': name, 'pass': bool(condition), 'detail': detail})
    if not condition:
        raise ValueError(name)

def ref(path):
    path = Path(path)
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def bound(value, label):
    got = ref(value['path'])
    check(label, got['sha256'] == value['sha256'] and ('bytes' not in value or got['bytes'] == value['bytes']))
    evidence[label] = got
    return json.loads(Path(value['path']).read_text())

def exact(a, b):
    return json.dumps(a, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(b, sort_keys=True, separators=(',', ':'), allow_nan=False)

def extract(relative, names, namespace):
    """Execute only selected unmodified top-level definitions, never imports."""
    path = ROOT / relative
    source = path.read_text()
    tree = ast.parse(source)
    selected = []
    for node in tree.body:
        node_names = ([node.name] if isinstance(node, ast.FunctionDef) else
                      [t.id for t in node.targets if isinstance(t, ast.Name)] if isinstance(node, ast.Assign) else [])
        if set(node_names) & set(names):
            selected.append(node)
            definitions.append({'source': ref(path), 'names': node_names, 'line': node.lineno,
                                'end_line': node.end_lineno,
                                'definition_sha256': hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()})
    found = {n.name if isinstance(n, ast.FunctionDef) else n.targets[0].id for n in selected}
    check('definitions:' + relative, set(names) <= found)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return types.SimpleNamespace(**namespace)

def ledger_snapshot():
    result = {}
    for name, anchor in AUTH['ledger_prefixes'].items():
        got = ref(anchor['path'])
        with Path(anchor['path']).open('rb') as stream:
            prefix = hashlib.sha256(stream.read(anchor['bytes'])).hexdigest()
        check('ledger:' + name, got == anchor and prefix == anchor['sha256'])
        result[name] = {**got, 'prefix_sha256': prefix, 'unchanged': True, 'suffix_bytes': got['bytes'] - anchor['bytes']}
    return result

def main():
    stop = extract('scripts/qd_ed_n36_stop.py', ['OWNER_STOP', 'DATA_STOP', 'STOP_PATHS', 'DEADLINE', 'binding', 'check'], {'dt': dt, 'os': os})
    stop.check(need=1200)
    check('STOP_and_deadline', True, {'paths': list(stop.STOP_PATHS), 'at': dt.datetime.now(dt.timezone.utc).isoformat()})
    initial = ledger_snapshot()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
    check('exact_candidate_HEAD', head == AUTH['source'])
    check('tracked_source_clean', subprocess.check_output(['git', 'diff', 'HEAD', '--name-only'], cwd=ROOT, text=True) == '', {'status': status, 'note': 'Pre-existing untracked .cpu-test-artifacts/ was not opened or modified.'})
    inputs = bound(AUTH['inputs'], 'inputs')
    terminal = bound(AUTH['root_terminal_review'], 'root_terminal_review')
    bound(AUTH['standing_authority'], 'standing_authority')
    check('identical_root_sets', exact(inputs['roots'], AUTH['roots']) and exact(terminal['roots'], AUTH['roots']))
    roots = {k: bound(v, 'root:' + k) for k, v in AUTH['roots'].items()}
    plan, audit, graph, diagnostic, proof = [roots[k] for k in ('plan', 'audit', 'graph', 'diagnostic_manifest', 'controller_semantics')]
    accepted = {k: bound(v, 'accepted:' + k) for k, v in inputs['accepted_records'].items() if k != 'prior_rebinding_report'}
    bound(terminal['report'], 'preparation_report')
    bound(inputs['preparation_report'], 'preparation_generation_report')
    bound(inputs['final_artifact_check'], 'preparation_final_check')
    for name, anchor in inputs['preparation_outputs'].items():
        got = ref(anchor['path'])
        check('prepared_hash:' + name, got == anchor)
        evidence['prepared:' + name] = got

    w = extract('scripts/qd_ed_n23_worker.py', ['require', 'sha', 'canonical_sha', 'read_ref'], {'hashlib': hashlib, 'json': json, 'Path': Path})
    routing = extract('scripts/qd_ed_n36r2_admission.py', ['SESSION', 'OWNER'], {'Path': Path})
    cnames = ['ROOT', 'COHORT', 'RECOVERY_COHORT', 'DRAFT_RECOVERY_COHORT', 'DRAFT_N36R3_COHORT', 'DRAFT_N36R4_COHORT', 'SEPARATE_HEALTH_COHORTS', 'IDENTITIES', 'ARMS', 'DEADLINE', 'GPU_UUID', 'PROTOCOL_REVIEW_SHA', 'PROTOCOL_SHA', 'ACCOUNTING_SHA', 'LIMITS', 'CAPS', 'WORKER_CONTRACT', 'stop_path', 'validate_stop_binding', 'expected_rows']
    c = extract('scripts/qd_ed_n36_contract.py', cnames, {'Path': Path, '__file__': str(ROOT / 'scripts/qd_ed_n36_contract.py'), 'json': json, 'w': w, 'stop': stop})
    enames = ['BASE', 'SOURCE', 'PREPARATION', 'OWNER_ROUTE_MAPPING', 'HISTORICAL_OWNER', 'SPECIFICATION', 'IDENTITY', 'EPISODE_KEY', 'HEALTH_ID', 'HEALTH_KIND', 'PURPOSE', 'PLAN_SCHEMA', 'AUDIT_SCHEMA', 'CONTEXT_SCHEMA', 'LIMITS', 'JOURNALS', 'BINDINGS', 'RUNTIME_INPUTS', 'OPERATIONAL_FILES', 'exact', 'reference', 'read', 'specification', 'row', 'disabled_scope', 'disabled_accounting', 'validate_disabled_scope', 'validate_disabled_accounting', 'validate_scope_reference', 'validate_accounting_reference', 'require_row', 'deployment', 'owner_root', 'operational_binding', 'validate_audit_view', 'audit_mapping', 'validate_plan_shape', 'validate_plan', 'scientific_equivalence', 'review_bindings', 'require_dispatch_implementation', 'launch_guard']
    e = extract('scripts/qd_ed_n36_engineering.py', enames, {'Path': Path, 'json': json, 'dt': dt, 'subprocess': subprocess, 'w': w, 'c': c, 'stop': stop, 'OWNER': routing.OWNER, 'SESSION': routing.SESSION})
    e.validate_plan_shape(plan)
    e.validate_audit_view(audit)
    e.audit_mapping(plan, audit, e.row())
    e.scientific_equivalence(plan)
    check('exact_passive_plan_audit_and_scientific_equivalence', True)
    check('disabled_authority', plan['authority'] is None and plan['b5_review'] is None and graph['authority'] is None and graph['b5_review'] is None and graph['release_enabled'] is False and graph['source_adopted'] is False)
    for name in ('plan', 'audit', 'diagnostic_manifest', 'controller_semantics'):
        check('graph_root:' + name, graph[name] == {k: AUTH['roots'][name][k] for k in ('path', 'sha256')})
    check('graph_audit_manifests', graph['audit_manifests'] == audit['expected_manifests'])
    check('graph_source', graph['source'] == head and plan['source'] == audit['source'] == plan['scientific_source'] and plan['source']['commit'] == head)
    for name, value in graph['retained_bindings'].items():
        check('retained_binding:' + name, exact(plan[name], value))
    for name in e.BINDINGS:
        if name not in ('source', 'scientific_source'):
            bound(plan[name], 'binding:' + name)
    original = bound(audit['original_plan'], 'original_scientific_plan')
    science_fields = ['cohort', 'episodes', 'limits', 'worker_contract', 'deadline', 'protocol', 'protocol_review', 'accounting']
    check('40_scientific_rows_and_gates_unchanged', len(audit['episodes']) == 40 and all(exact(audit[k], original[k]) for k in science_fields), {'fields': science_fields, 'row_sha256': w.canonical_sha(audit['episodes']), 'limits_sha256': w.canonical_sha(audit['limits']), 'worker_contract_sha256': w.canonical_sha(audit['worker_contract'])})
    for name in ('protocol', 'protocol_review', 'accounting'):
        bound(audit[name], 'science:' + name)
    for name in ('runtime_inventory', 'seed_plan'):
        got = ref(plan[name + '_path'])
        check('frozen_input:' + name, got['sha256'] == plan[name + '_sha256'])
        evidence['frozen_input:' + name] = got

    runtime = w.read_ref(plan['runtime'])
    closure = w.read_ref(plan['runtime_closure'])
    native = w.read_ref(plan['native_build'])
    controller = extract('scripts/qd_ed_n34_controller.py', ['FIELDS', 'INSTANCE_ATTRIBUTES', 'verify_semantics'], {'w': w, 'math': math})
    controller.verify_semantics(plan['controller_semantics'], plan['runtime'], closure)
    check('exact_controller_passive_verifier', True)
    check('controller_scope', proof['source_commit'] == head and proof['runtime_closure'] == plan['runtime_closure'] and proof['release_enabled'] is False and proof['scientific_promotion'] is False and proof['physical_gain_certified'] is False)
    for name, anchor in proof['review_evidence'].items():
        record = bound(anchor, 'controller_evidence:' + name)
        check('controller_evidence_scope:' + name, record['source_commit'] == head and record['runtime_closure'] == plan['runtime_closure'] and record['native_execution_observed'] is False and record['release_enabled'] is False)
        for source in record['sources']:
            got = ref(source['path'])
            check('controller_source:' + source['path'], got['sha256'] == source['sha256'])
            evidence['controller_source:' + source['path']] = got
    check('runtime_provenance_not_readiness', closure['runtime'] == plan['runtime'] and runtime['worktree'] == str(ROOT) and runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False and runtime['metadata_mapping_verified'] is False and runtime['cuda_egl_probe'] is None and runtime['provider_evidence'] is None)
    check('native_metadata_consistency', native['torch_version'] == closure['versions']['torch'], {'native_libraries': len(native['libraries']), 'torch_version': native['torch_version'], 'cuda_version': native['cuda_version'], 'scope': 'Accepted native binary verification reused; no binary rehash, import, ABI or loading check.'})

    # Independent static manifest consistency, reusing accepted Hydra recomposition.
    manifests = {}
    source_index = {x['path']: x['sha256'] for x in plan['source']['files']}
    for row in audit['episodes']:
        key = row['episode_key']
        m = w.read_ref(audit['expected_manifests'][key]); manifests[key] = m
        check('manifest_row:' + key, m['row'] == row and m['dispatch_authority'] is False)
        for field in ('source', 'scientific_source', 'native_build', 'runtime', 'runtime_closure', 'controller_semantics', 'scope', 'deployment', 'original_plan', 'cohort', 'protocol', 'protocol_review', 'accounting'):
            check('manifest_binding:' + key + ':' + field, exact(m[field], audit[field]))
        output = Path(audit['artifact_root']) / 'attempts' / key
        check('manifest_output:' + key, m['output_dir'] == str(output))
        overrides = {x.split('=', 1)[0]: x.split('=', 1)[1] for x in m['argv'] if '=' in x}
        routes = {'hydra.run.dir': str(output), 'main.eds_eval.output_dir': str(output / 'eds_eval'), 'main.eds_eval.report_dir': str(Path(audit['artifact_root']) / 'reports'), 'main.eds_mechanism_pretest.output_dir': str(output / 'mechanism')}
        check('manifest_routes:' + key, all(overrides.get(k) == v and sum(x.startswith(k + '=') for x in m['argv']) == 1 for k,v in routes.items()))
        resolved = m['resolved_config']; arm = row['profile']
        check('manifest_modes:' + key, resolved['closure_intent_mode'] == resolved['capture_dwell_proposal_mode'] == resolved['archive_eligible_capture_mode'] == 'off' and resolved['n32_runtime_binding'] is None and resolved['n35_runtime_binding'] is None and (resolved['nonprogress_tangent_mode'] != 'off') == (arm == 'N36') and (resolved['observed_jaw_approach_mode'] != 'off') == (arm in ('N34','N36')))
        if arm in ('C0','Q0'):
            check('control_runtime:' + key, m['expected_runtime'] is None and resolved['n34_runtime_binding'] is None and resolved['n36_runtime_binding'] is None)
        else:
            binding = {'task_id': row['task_id'], 'source_commit': head, 'run_id': key}
            expected = m['expected_runtime']
            check('active_runtime:' + key, resolved['n34_runtime_binding'] == binding and resolved['n36_runtime_binding'] == (binding if arm == 'N36' else None) and expected['binding'] == binding and expected['config_sha256'] == hashlib.sha256(json.dumps(resolved, sort_keys=True, allow_nan=False).encode()).hexdigest() and all(source_index[k] == v for k,v in expected['source_hashes'].items()))
        task = runtime['tasks'][str(row['task_id'])]; files = {x['path']:x['sha256'] for x in runtime['files']}
        check('task_inventory:' + key, task['init_index'] == row['init_index'] and files[task['init_path']] == row['init_file_sha256'] and files[task['bddl_path']] == row['bddl_sha256'])
    audited = manifests[audit['episodes'][0]['episode_key']]
    check('diagnostic_identity', diagnostic['audit_row'] == audit['episodes'][0] and diagnostic['row'] == e.row() and diagnostic['audit_manifest'] == audit['expected_manifests'][audit['episodes'][0]['episode_key']])
    for field in ('scope','accounting','deployment','audit_plan','source','scientific_source','native_build','runtime','runtime_closure','controller_semantics'):
        check('diagnostic_binding:' + field, diagnostic[field] == plan[field])
    check('diagnostic_no_scientific_eligibility', all(diagnostic[k] is False for k in ('scientific_eligible','matched_improvement_eligible','promotion_eligible')) and diagnostic['expected_runtime'] is None)
    normalize_keys = ('hydra.run.dir','main.eds_eval.output_dir','main.eds_eval.report_dir','main.eds_mechanism_pretest.output_dir','main.eds_eval.job_id','main.eds_mechanism_pretest.run_id')
    check('diagnostic_exact_six_argv_changes', len(diagnostic['argv']) == len(audited['argv']) and {a.split('=',1)[0] for a,b in zip(audited['argv'], diagnostic['argv']) if a != b} == set(normalize_keys) and all(a == b or a.split('=',1)[0] == b.split('=',1)[0] for a,b in zip(audited['argv'], diagnostic['argv'])))
    normalized = copy.deepcopy(diagnostic['resolved_config'])
    for k in ('output_dir', 'run_id'):
        normalized['mechanism_pretest'][k] = audited['resolved_config']['mechanism_pretest'][k]
    check('diagnostic_resolved_C0_science_unchanged', exact(normalized, audited['resolved_config']))
    output = Path(plan['artifact_root']) / 'attempts' / e.EPISODE_KEY
    expected_routes = dict(zip(normalize_keys, map(str, [output, output / 'eds_eval', Path(plan['artifact_root']) / 'reports', output / 'mechanism', e.EPISODE_KEY, e.EPISODE_KEY])))
    check('diagnostic_exact_output_and_identity', diagnostic['output_dir'] == str(output) and all(diagnostic['argv'].count(k + '=' + v) == 1 for k,v in expected_routes.items()))
    output_root = Path(plan['artifact_root'])
    check('isolated_output_empty_or_absent', not output_root.exists() or (output_root.is_dir() and not any(output_root.iterdir())))

    accounting = w.read_ref(plan['accounting']); proposal = accounting['accounting']
    check('finite_diagnostic_limits', e.LIMITS['attempts'] == e.LIMITS['healthchecks'] == 1 and e.LIMITS['automatic_recoveries'] == 0 and e.LIMITS['episode_seconds'] + e.LIMITS['cleanup_seconds'] + e.LIMITS['health_seconds'] + e.LIMITS['health_cleanup_seconds'] == e.LIMITS['gpu_seconds'] == 1900 and e.LIMITS['gpu_seconds'] + e.LIMITS['root_overhead_seconds'] == e.LIMITS['wall_seconds'] == 2100)
    check('costs_and_margin_preserved', proposal['retained_attempts'] == 506 and proposal['retained_gpu_hours'] == '75.60616276674473' and proposal['retained_admission_margin_gpu_hours'] == '0.23357169027962' and Decimal(proposal['conservative_before_gpu_hours']) == Decimal(proposal['retained_gpu_hours']) + Decimal(proposal['retained_admission_margin_gpu_hours']) and proposal['gpu_reservation_seconds'] == 1900 and proposal['new_attempts_max'] == 1 and proposal['prospective_attempts_max'] == 507 and proposal['baseline_before_after_cap'] == [106,107,400])
    check('accounting_not_adopted', accounting['root_adopted'] is False and accounting['release_enabled'] is False)
    for name, anchor in accounting['retained_ledger_prefixes'].items():
        check('accounting_retained_prefix:' + name, all(anchor[k] == AUTH['ledger_prefixes'][name][k] for k in ('path','bytes','sha256')))
    try:
        e.launch_guard(None, None)
    except RuntimeError as exc:
        check('unconditional_G7_veto_executes_first', str(exc) == 'engineering dispatch disabled: released lifecycle and deep-closure verification incomplete')
    else:
        check('unconditional_G7_veto_executes_first', False)
    # Focused negative controls mutate only in-memory copies.
    for name, mutate in [('extra_attempt', lambda p: p['limits'].update(attempts=2)), ('enable_science', lambda p: p['phase_authorization'].update(dev=True)), ('output_into_source', lambda p: p.update(artifact_root=str(ROOT)))]:
        bad = copy.deepcopy(plan); mutate(bad)
        try:
            e.audit_mapping(bad, audit, e.row())
        except ValueError as exc:
            check('reject:' + name, True, str(exc))
        else:
            check('reject:' + name, False)
    bad = copy.deepcopy(audit); bad['episodes'] = bad['episodes'][:-1]
    try:
        e.validate_audit_view(bad)
    except ValueError as exc:
        check('reject:truncated_science', True, str(exc))
    else:
        check('reject:truncated_science', False)
    # Verify reviewed source files against the exact plan inventory.
    for name in sorted({str(Path(d['source']['path']).relative_to(ROOT)) for d in definitions} | {'scripts/qd_ed_n36_bridge.py', 'scripts/qd_ed_n36_release.py', 'scripts/qd_ed_n36_worker.py', 'scripts/qd_ed_n34_source.py', 'core/env_adapters/libero_adapter.py'}):
        got = ref(ROOT / name)
        check('source_contract_hash:' + name, got['sha256'] == source_index[name])
        evidence['source_contract:' + name] = got
    final = ledger_snapshot()
    stop.check()
    check('final_HEAD_unchanged', subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip() == head)
    check('final_git_status_unchanged', subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True) == status)
    result = {'schema': 'n36-independent-b5-passive-checks-v1', 'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'checks': checks, 'evidence': evidence, 'definitions': definitions, 'ledger_checks': {'initial': initial, 'final': final}, 'source': head, 'roots': AUTH['roots'], 'production_modules_imported': False, 'native_libraries_loaded': False, 'full_release_verifier_run': False, 'manifest_composition': 'Accepted exact-candidate Hydra recomposition reused; independent static all-41 identity/binding/mode/route/config checks performed.', 'status': 'PASS'}
    (OUT / 'passive-checks-v1.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    # Candidate B5 schema comes directly from validate_authority's exact object.
    tree = ast.parse((ROOT / 'scripts/qd_ed_n36_engineering.py').read_text())
    authority_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_authority')
    exact_call = authority_fn.body[3].value
    check('B5_schema_AST', isinstance(exact_call, ast.Call) and isinstance(exact_call.func, ast.Name) and exact_call.func.id == 'exact')
    review = eval(compile(ast.Expression(exact_call.args[1]), '<exact-candidate-B5-schema>', 'eval'), {'bindings': e.review_bindings(plan)})
    (OUT / 'review-candidate-v1.json').write_text(json.dumps(review, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': 'PASS', 'checks': len(checks), 'ledger_unchanged': initial == final, 'candidate_review_schema': review['schema']}))

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        (OUT / 'passive-checks-failure-v1.json').write_text(json.dumps({'error': repr(exc), 'checks': checks, 'evidence': evidence, 'definitions': definitions}, indent=2) + '\n')
        raise
