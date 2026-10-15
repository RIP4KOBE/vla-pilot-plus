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
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
DEPLOY = ROOT.parent.parent / 'n36_engineering_adapter_001482/implementation_worktree'
FINAL = 'f661a570403e9ff7224d4c35230a0f2b9321a269'
BASE = '0d618606a933473eb0e5a02fc3659a3a0ea0ee25'
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

import sys
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
os.environ['GIT_NO_LAZY_FETCH'] = '1'
sys.dont_write_bytecode = True
guard()
assert git('rev-parse', 'HEAD') == FINAL
assert git('status', '--porcelain', '--untracked-files=no') == ''
review = bound(AUTH['root_review'])
placement_result = bound(AUTH['source_placement'])
prior_report = bound(AUTH['prior_partial_report'])
assert review['source_after'] == placement_result['after'] == FINAL
bound(AUTH['amendment'])
bound(review['report'])
prior = TURNS / '001808/disabled-binding-refresh'
for name in ('refresh-artifacts-v1.py', 'verify-artifacts-v1.py', 'boundary-manifest-v1.json', 'validation-results-v1.json'):
    r = prior_report['outputs'][name]
    assert sha(r['path']) == r['sha256']
    inputs[r['path']] = ref(r['path'])
graph_ref = prior_report['outputs']['graph.partial-disabled-v1.json']
graph = bound(graph_ref)
old = {k: bound(graph[k]) for k in ('specification','policy','source_record','runtime','runtime_closure','controller_semantics','amendment','native_build')}
spec0 = old['specification']
changed = git('diff', '--name-only', BASE, FINAL, '--').splitlines()
assert set(changed) == {'scripts/qd_ed_n36_engineering_r1.py','scripts/qd_ed_n36_readiness_prepare.py','tests/test_n36_engineering_r1.py','tests/test_n36_readiness_prepare.py'}
assert git('diff', '--name-only', BASE, FINAL, '--', 'core','configs','scripts/qd_ed_n36_contract.py') == ''
git('merge-base', '--is-ancestor', BASE, FINAL)
git('cat-file', '-t', SCIENCE)
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

idx = {v['path']:v['sha256'] for v in source['files']}
old_idx = {v['path']:v['sha256'] for v in old['source_record']['files']}
assert sorted(p for p in set(idx)|set(old_idx) if idx.get(p)!=old_idx.get(p)) == sorted(changed)
emit('source-delta-v1.json', {'source':source_ref,'previous_source':graph['source_record'], 'changed_paths':changed,
    'unchanged_inventory_paths':sorted(set(idx)-set(changed)), 'scientific_source':SCIENCE,
    'files':[{'path':p,'before_sha256':old_idx[p],'after_sha256':idx[p]} for p in changed],
    'source_edits':False,'placement_performed':False})
runtime = copy.deepcopy(old['runtime'])
runtime['preparation'].update(source=FINAL,source_record=source_ref)
assert runtime['preparation']['runtime_ready'] is runtime['provider_ready'] is runtime['cuda_egl_verified'] is False
runtime_ref = emit('disabled-runtime.json',runtime)
delta_record('runtime',old['runtime'],runtime,graph['runtime'],runtime_ref)
baseline = bound(spec0['canonical_runtime'])
baseline['preparation'].update(source=FINAL,source_record=source_ref)
assert runtime == baseline
checks.append({'check':'exact immutable canonical disabled runtime projection','result':'PASS','changed_fields':['preparation.source','preparation.source_record']})
closure = copy.deepcopy(old['runtime_closure'])
closure['runtime'] = runtime_ref
module_changes=[]
for name,row in closure['modules'].items():
    p=Path(row['path'])
    if p.is_relative_to(ROOT):
        rel=str(p.relative_to(ROOT))
        assert rel in idx
        if row['sha256'] != idx[rel]:
            module_changes.append({'module':name,'before':dict(row),'after':{'path':str(p),'sha256':idx[rel]}})
            row['sha256']=idx[rel]
closure_ref=emit('runtime-closure.prospective-disabled-v1.json',closure)
delta_record('runtime_closure',old['runtime_closure'],closure,graph['runtime_closure'],closure_ref)
file_ns=dict(Path=Path,w=w)
ast_functions(ROOT/'scripts/qd_ed_n34_source.py',['_runtime_file'],file_ns)
for row in closure['modules'].values():
    if Path(row['path']).is_relative_to(ROOT):
        file_ns['_runtime_file'](row)
file_ns['_runtime_file'](closure['modules'][old['controller_semantics']['module']])
assert closure['modules'][old['controller_semantics']['module']] == old['controller_semantics']['source']
checks.append({'check':'production _runtime_file on canonical checkout closure modules and controller source','result':'PASS','changed_modules':module_changes,'unchanged_external_inventory_not_rescanned':True})
native_ref=emit('native-binding.disabled-v1.json',{'schema':'n36-disabled-native-binding-refresh-v1','status':'DISABLED_STATIC_REFERENCE_ONLY',
    'source':source_ref,'runtime':runtime_ref,'runtime_closure':closure_ref,'native_build':graph['native_build'],
    'native_inventory_changed':False,'native_libraries_rehashed':False,'native_execution_observed':False,
    'prior_boundary':prior_report['boundary_manifest'],'basis_scope':'unchanged native inventory only; no historical review accepts new graph'})
amendment=copy.deepcopy(old['amendment'])
amendment['source']=source_ref
amendment_ref=emit('amendment.prospective-disabled-v1.json',amendment)
delta_record('amendment',old['amendment'],amendment,graph['amendment'],amendment_ref)
historical_spec=literal(ROOT/'scripts/qd_ed_n36_engineering_r1.py','HISTORICAL_SPECIFICATION')
bound(historical_spec)
policy=copy.deepcopy(old['policy'])
for key in policy:
    if key.endswith('_path'):
        policy[key]=str(OUT/Path(policy[key]).name)
policy['disabled_runtime_path']=runtime_ref['path']
policy['previous_specification']=historical_spec
assert policy['resource_id'] is None
policy_ref=emit('preparation-policy.unassigned-disabled-v1.json',policy)
delta_record('policy',old['policy'],policy,graph['policy'],policy_ref)
spec=copy.deepcopy(spec0)
spec['runtime_binding'].update(amendment=amendment_ref,preparation=policy_ref,source_record_path=source_ref['path'],runtime_path=str(OUT/'pending-measured-runtime.json'))
spec_ref=emit('specification.prospective-disabled-v1.json',spec)
delta_record('specification',spec0,spec,graph['specification'],spec_ref)
assert all(spec[k]==spec0[k] for k in spec0 if k!='runtime_binding')
controller=copy.deepcopy(old['controller_semantics'])
controller.update(runtime=runtime_ref,runtime_closure=closure_ref,source_commit=FINAL)
assert controller['review_evidence']=={} and controller['status']=='PENDING_ROOT_REVIEW_DISABLED'
controller_ref=emit('controller-semantics.pending-disabled-v1.json',controller)
delta_record('controller_semantics',old['controller_semantics'],controller,graph['controller_semantics'],controller_ref)
# Exact production function bodies, with real hash readers. No source/module import side effects.
e=types.ModuleType('scripts.qd_ed_n36_engineering_r1')
e.__dict__.update(Path=Path,hashlib=hashlib,json=json,w=w,SPECIFICATION=spec_ref,HISTORICAL_SPECIFICATION=historical_spec)
for key in ('HEALTH_ID','EPISODE_KEY','JOURNALS','AMENDMENT'):
    e.__dict__[key]=literal(ROOT/'scripts/qd_ed_n36_engineering_r1.py',key)
ast_functions(ROOT/'scripts/qd_ed_n36_engineering_r1.py',['reference','read','exact','_recovery_json','_recovery_read','_recovery_specification','_recovery_contract','_recovery_predecessors'],e.__dict__)
p=types.ModuleType('scripts.qd_ed_n36_readiness_prepare')
p.__dict__.update(e=e,Path=Path)
for key in ('SCHEMA','FIELDS','MEASUREMENT_CONTRACT'):
    p.__dict__[key]=literal(ROOT/'scripts/qd_ed_n36_readiness_prepare.py',key)
ast_functions(ROOT/'scripts/qd_ed_n36_readiness_prepare.py',['policy','closed'],p.__dict__)
package=types.ModuleType('scripts');package.qd_ed_n36_readiness_prepare=p
sys.modules['scripts']=package
sys.modules[p.__name__]=p
assert p.policy(spec)==policy
checks.append({'check':'production readiness_prepare.policy(new specification)','result':'PASS','resource_id':None,'limitation':'Policy composition acceptance is not fresh identity, recovery admission or release.'})
expected_reject('production _recovery_specification(new specification)',lambda:e._recovery_specification(spec),'bound recovery policy successor')
ctrl_ns=dict(w=w,math=__import__('math'),FIELDS=literal(ROOT/'scripts/qd_ed_n34_controller.py','FIELDS'))
ast_functions(ROOT/'scripts/qd_ed_n34_controller.py',['verify_semantics'],ctrl_ns)
expected_reject('production verify_semantics(new pending controller)',lambda:ctrl_ns['verify_semantics'](controller_ref,runtime_ref,closure),'reviewed controller semantics required')
# Exact operational source delta; no readiness, scientific or accounting projection changed.
actual_delta=git('diff','--name-only',spec['runtime_binding']['source_base'],FINAL,'--').splitlines()
assert set(actual_delta)<=set(spec['runtime_binding']['source_change_allowlist'])
checks.append({'check':'final source changes within exact policy allowlist','result':'PASS','paths':actual_delta})
new_graph=copy.deepcopy(graph)
new_graph.update(specification=spec_ref,policy=policy_ref,amendment=amendment_ref,source_record=source_ref,runtime=runtime_ref,
    runtime_closure=closure_ref,controller_semantics=controller_ref,status='DISABLED_CANDIDATE_PENDING_P3_REVIEW_AND_P4_RECOVERY',
    prior_partial_graph={k:graph_ref[k] for k in ('path','sha256')},final_source_review={k:AUTH['root_review'][k] for k in ('path','sha256')},
    source_placement={k:AUTH['source_placement'][k] for k in ('path','sha256')})
graph_new_ref=emit('graph.candidate-disabled-v1.json',new_graph)
delta_record('graph',graph,new_graph,{k:graph_ref[k] for k in ('path','sha256')},graph_new_ref)
unchanged=['scientific source anchor '+SCIENCE,'all specification fields outside runtime_binding; thresholds, seeds, accounting and scope',
    'runtime outside preparation.source and preparation.source_record','closure outside runtime reference and changed module hashes',
    'native inventory and all unrelated external modules','controller instance, semantics and source identity',
    'historical documents, failed checks, source checkout, state, checkpoints, ledgers and locks']
boundary_ref=emit('boundary-manifest-v1.json',{'schema':'n36-disabled-binding-boundaries-v1','prior_boundary':prior_report['boundary_manifest'],
    'artifact_field_boundaries':boundaries,'source_inventory_delta':changed,'module_changes':module_changes,'unchanged':unchanged,
    'historical_only':['amendment implementation_review is a production-pinned historical scope provenance field, never final-source acceptance',
        'specification readiness_recovery and recovery_prefix_contract remain historical placeholders; production rejects null policy successor',
        'prior controller review and B5 are not accepted for new graph'],
    'not_claimed':['full production graph validation','independent/root graph review','loaded controller behavior','fresh native execution','scientific result']})
checks.append({'check':'deployed preparation checkout','result':'PASS','worktree':str(ROOT),'commit':FINAL,'placement_performed':False})
assert git('rev-parse','HEAD')==FINAL
assert git('status','--porcelain','--untracked-files=no')==''
validation_ref=emit('validation-results-v1.json',{'schema':'n36-disabled-refresh-validation-v1','command':['python','-B',str(OUT/'refresh-artifacts-v1.py')],
    'checks':checks,'production_function_bodies_unmodified':True,'production_imports':False,'full_graph_validation':False,'tests_rerun':False,
    'dependency_method':'Selected unmodified AST function bodies and literal production constants; actual hash readers, source files and review references; no predicates stubbed.'})
# Report is finalized separately after bounded prerequisite packet construction.
emit('refresh-result-v1.json',{'schema':'n36-disabled-refresh-result-v1','source':FINAL,'scientific_source':SCIENCE,
    'authority':ref(OUT/'authority-v1.json'),'candidate_graph':graph_new_ref,'outputs':outputs.copy(),'input_hashes':list(inputs.values()),
    'validation':validation_ref,'boundary_manifest':boundary_ref,'changed_boundary_list':[b['boundary'] for b in boundaries]+['source_record','native wrapper'],
    'unchanged_boundary_list':unchanged,'elapsed_seconds':time.monotonic()-START})
print(json.dumps({'result':'DISABLED_CANDIDATE_REFRESHED','graph':graph_new_ref,'checks':checks[-5:]}))
