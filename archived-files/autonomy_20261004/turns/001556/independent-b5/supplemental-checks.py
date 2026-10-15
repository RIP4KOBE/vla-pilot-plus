"""Focused delta and schema checks; no recursive provenance reconstruction."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import datetime as dt

OUT = Path(__file__).parent
auth = json.loads((OUT / 'authority-v1.json').read_text())
root = Path(auth['worktree'])
checks, evidence = [], {}

def check(name, value, detail=None):
    checks.append({'check': name, 'pass': bool(value), 'detail': detail})
    assert value, name

def read(r, label):
    b = Path(r['path']).read_bytes()
    got = {'path': r['path'], 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
    check(label, got['sha256'] == r['sha256'] and ('bytes' not in r or len(b) == r['bytes']))
    evidence[label] = got
    return json.loads(b)

inputs = read(auth['inputs'], 'inputs')
accepted = read(inputs['accepted_records']['accepted_g5_review'], 'accepted_g5_root_review')
g5 = read(accepted['report'], 'accepted_g5_report')
rebinding = read(inputs['preparation_outputs']['rebindings-v1.json'], 'rebindings')
allowed = {'audit-view.disabled-v1.json': {'controller_semantics','expected_manifests'},
           'diagnostic-manifest.disabled-v1.json': {'controller_semantics','audit_manifest','audit_plan'},
           'engineering-plan.disabled-v1.json': {'controller_semantics','audit_plan','engineering_manifest','expected_manifests'}}
for record in rebinding['audit_manifests'] + rebinding['other_roots']:
    name = Path(record['old']['path']).name
    key = ('audit-manifests/' if 'audit-manifests' in Path(record['old']['path']).parts else '') + name
    oldref = g5['outputs'][key]
    check('accepted_G5_anchor:' + key, oldref['sha256'] == record['old']['sha256'] and Path(oldref['path']).resolve() == Path(record['old']['path']).resolve())
    old, new = read(record['old'], 'old:' + key), read(record['new'], 'new:' + key)
    changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    expected = {'controller_semantics'} if key.startswith('audit-manifests/') else allowed[name]
    check('independent_delta:' + key, changed == expected, {'changed_fields': sorted(changed), 'science_config_unchanged': old.get('resolved_config') == new.get('resolved_config'), 'argv_unchanged': old.get('argv') == new.get('argv')})
plan = read(auth['roots']['plan'], 'plan')
runtime = read(plan['runtime'], 'runtime')
for dep in runtime['dependencies']:
    target = Path(dep['target'])
    rel = str(target.relative_to(root))
    tree = subprocess.check_output(['git', 'ls-tree', auth['source'], '--', rel], cwd=root, text=True).split()
    check('dependency_gitlink:' + rel, tree[:3] == ['160000','commit',dep['commit']] and target.resolve() == target)
tree = subprocess.check_output(['git','ls-tree',auth['source'],'--','third_party/libero_pro'],cwd=root,text=True).split()
check('LIBERO_regular_superproject_tree', tree[:2] == ['040000','tree'])
check('isolated_dependency_search_path', runtime['environment']['PYTHONPATH'].split(':') == [str(root/'third_party/lerobot/src'), str(root/'third_party/rdt'), str(root/'third_party/libero_pro')])
source_record = read(runtime['preparation']['source_record'], 'accepted_complete_source_record')
check('source_record_exactly_reused', source_record == plan['source'])
text = (root/'scripts/qd_ed_n36_engineering.py').read_text()
tree = ast.parse(text)
bindings_node = next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BINDINGS' for t in n.targets))
binding_names = ast.literal_eval(bindings_node.value)
function = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_authority')
call = next(n.value for n in function.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='exact')
expected = eval(compile(ast.Expression(call.args[1]),'<candidate-B5-schema>','eval'),{'bindings': {k:plan[k] for k in binding_names}})
candidate = json.loads((OUT/'review-candidate-v1.json').read_text())
check('review_exact_source_schema', candidate == expected and set(candidate) == set(binding_names)|{'schema','decision','worker_receipts_are_future','release_enabled'})
altered = dict(candidate); altered['controller_semantics'] = dict(candidate['controller_semantics'], sha256='0'*64)
check('changed_controller_binding_invalidates_review', altered != expected)
altered = dict(candidate); altered['source'] = dict(candidate['source'], commit='0'*40)
check('changed_candidate_source_invalidates_review', altered != expected)
for function_name in ('launch_guard','execute_one'):
    fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==function_name)
    body = [n for n in fn.body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))]
    check('dispatch_veto_first:' + function_name, isinstance(body[0],ast.Expr) and isinstance(body[0].value,ast.Call) and isinstance(body[0].value.func,ast.Name) and body[0].value.func.id=='require_dispatch_implementation')
result = {'schema':'n36-independent-b5-supplemental-checks-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'PASS','checks':checks,'evidence':evidence,'scope':'Accepted G5 one-hop comparison, dependency gitlink/route metadata, and exact candidate review schema. No native execution or full release verification.'}
(OUT/'supplemental-checks-v1.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'status':'PASS','checks':len(checks),'independent_deltas':43,'review_binding_names':list(binding_names)}))
