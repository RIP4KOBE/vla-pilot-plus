"""Read-only bounded OpenGL input audit and prospective repair report."""
import ast
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = Path.cwd()
BASE = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns')
SITE = Path('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages')
A = json.loads((OUT/'authority-v1.json').read_text())
assert not any(os.path.lexists(p) for p in A['stop_authority']['paths'])
assert dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(A['stop_authority']['deadline'].replace('Z','+00:00'))
assert str(ROOT) == A['worktree']
def ref(p):
    p=Path(p); b=p.read_bytes()
    return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
def record(p):
    r=ref(p); return {k:r[k] for k in ('path','sha256')}
def save(name, data):
    p=OUT/name; p.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n');return ref(p)
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
terminal=Path(A['terminal_reconciliation']['path'])
assert ref(terminal)==A['terminal_reconciliation']
T=json.loads(terminal.read_text())
C_PATH=BASE/'001730/recovery-prefix-contract/downstream-v2/runtime-closure.json'
C=json.loads(C_PATH.read_text()); M=C['modules']
empty_sha=hashlib.sha256(b'').hexdigest()
assert 'OpenGL.GL.VERSION' not in M
assert not any(n=='OpenGL.GL' or n.startswith('OpenGL.GL.') for n in M)
assert M['OpenGL.raw.EGL']==record(SITE/'OpenGL/raw/EGL/__init__.py')
# Scope: syntactic unconditional imports reachable from the explicit preparation
# input OpenGL.GL, restricted to OpenGL. No import execution, AST function bodies,
# conditional imports, native libraries, or other package trees.
def module_path(name):
    if not (name=='OpenGL' or name.startswith('OpenGL.')): return None
    p=SITE.joinpath(*name.split('.'))
    for f in (p/'__init__.py',p.with_suffix('.py')):
        if f.is_file(): return f
    return None
queue=['OpenGL.GL']; reached={}; edges=[]
while queue:
    name=queue.pop()
    if name in reached: continue
    p=module_path(name)
    if p is None:continue
    assert len(reached)<250, 'bounded static audit exceeded'
    reached[name]=record(p)
    parts=name.split('.')
    queue.extend('.'.join(parts[:i]) for i in range(1,len(parts)))
    tree=ast.parse(p.read_bytes())
    for node in tree.body:
        candidates=[]
        if isinstance(node,ast.Import):candidates=[a.name for a in node.names]
        elif isinstance(node,ast.ImportFrom) and node.level==0 and node.module:
            candidates=[node.module]+[node.module+'.'+a.name for a in node.names if a.name!='*']
        for target in candidates:
            if module_path(target):
                edges.append({'importer':name,'line':node.lineno,'imported':target})
                queue.append(target)
conflicts={n:{'frozen':M[n],'installed':r} for n,r in reached.items() if n in M and M[n]!=r}
assert not conflicts
additions={n:r for n,r in sorted(reached.items()) if n not in M}
assert additions['OpenGL.GL.VERSION']['sha256']==empty_sha
adjacent=[]
for p in sorted((SITE/'OpenGL/GL').glob('*/__init__.py')):
    n='.'.join(p.parent.relative_to(SITE).parts)
    adjacent.append({'module':n,**ref(p),'frozen':n in M,'reachable_by_static_unconditional_imports':n in reached})
delta=save('prospective-input-delta-v1.json',{
    'schema':'n36-opengl-prospective-input-delta-v1','status':'PROPOSAL_ONLY_NOT_FROZEN_NOT_RELEASED',
    'base_closure':ref(C_PATH),'explicit_input':'OpenGL.GL',
    'origin':'scripts/qd_ed_gpu_probe.py:176 (read only; never executed)',
    'modules_to_add':additions,'existing_records_changed':{},'required_after_changed':False,
    'selection':'OpenGL-only, recursively resolved unconditional top-level absolute imports and their actual package parents; zero-byte files included',
    'static_edges':edges,'adjacent_GL_package_cases':adjacent,
    'empty_packages_already_frozen':sum(r['path'].endswith('/__init__.py') and r['sha256']==empty_sha for r in M.values()),
    'positive_counterexample':{'module':'OpenGL.raw.EGL',**M['OpenGL.raw.EGL']},
    'static_modules_examined':len(reached),'added_module_count':len(additions),
    'limitations':['Static input lower bound, not complete dynamic lifecycle coverage. Conditional/function-local/plugin imports are not expanded. Review exact proposed names/paths/hashes before prospective freezing.',
                   'Do not whitelist all installed OpenGL packages or permit unknown modules. GL sibling vendor packages absent from this dependency walk are not proposed additions.',
                   'Adding only OpenGL.GL.VERSION is insufficient: the nonempty OpenGL.GL package and its unconditional imports are also absent.']})
source_files=['scripts/qd_ed_n34_source.py','scripts/qd_ed_n23_worker.py','scripts/qd_ed_n34_controller.py','scripts/qd_ed_gpu_probe.py']
source_records=[]
for name in source_files:
    data=subprocess.check_output(['git','show',A['source']+':'+name],cwd=ROOT)
    r=ref(ROOT/name);assert r['sha256']==hashlib.sha256(data).hexdigest()
    source_records.append({'file':name,'before_sha256':r['sha256'],'after_sha256':r['sha256'],'bytes':r['bytes'],'diff':''})
assert git('rev-parse','HEAD')==A['source']
assert not git('status','--porcelain')
checks=json.loads((OUT/'focused-check-results-v1.json').read_text())
assert checks['status']=='PASS'
report={
 'schema':'n36-runtime-inventory-cpu-repair-report-v1','node_id':'15.6','at':dt.datetime.now(dt.timezone.utc).isoformat(),
 'status':'ARTIFACT_INPUT_OMISSION_DIAGNOSED_NO_SOURCE_EDIT_REQUIRED','authority':ref(OUT/'authority-v1.json'),
 'terminal_reconciliation':ref(terminal),'terminal_log':ref(T['child_log']['path']),
 'source_before':{'worktree':str(ROOT),'commit':A['source'],'tree':git('rev-parse','HEAD^{tree}'),'clean':True},
 'source_after':{'worktree':str(ROOT),'commit':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'clean':True},
 'source_changed':False,'source_files_changed':[],'source_diff':'','commit_created':False,'source_audit_files':source_records,
 'cause':{
   'classification':'Prospective import-input coverage omission, inherited by downstream closure copies; not zero-byte exclusion.',
   'failed_module':'OpenGL.GL.VERSION','expected':None,'installed':ref(SITE/'OpenGL/GL/VERSION/__init__.py'),
   'construction':'000914 snapshot builder lines 201-208 records every loaded file-backed module regardless of byte length. 001185 builder lines 28-45 merges sys.modules and recorded compiled-source inputs without a size filter. 001740 graph builder lines 102-103 copies old closure and changes runtime binding only.',
   'trigger':'Preparation source explicitly imports OpenGL.GL at scripts/qd_ed_gpu_probe.py:176. The current frozen closure has no OpenGL.GL or OpenGL.GL.* entries; GL/__init__.py unconditionally imports VERSION.GL_1_1, causing VERSION package loading. First rejected module does not enumerate all missing modules.',
   'evidence':{'frozen_module_count':len(M),'frozen_empty_package_count':115,'frozen_OpenGL_GL_module_count':0,'positive_empty_package':M['OpenGL.raw.EGL']},
   'historical_limit':'Read selected construction sources and current closure only; no recursive provenance rebuild or claim about every historical transformation.'},
 'builder_source_evidence':[ref(BASE/x) for x in ['000914/runtime-v1/runtime-import-probe-v1.py','001185/runtime-preparation/closure_probe_v2.py','001740/recovery-graph-refresh/prepare-graph-v1.py']],
 'tests':{'command':'python -B '+str(OUT/'focused-check-v1.py'),'exit_code':0,'result':'7 focused checks PASS','script':ref(OUT/'focused-check-v1.py'),'results':ref(OUT/'focused-check-results-v1.json'),'scope':checks['method'],'broad_tests_run':False},
 'prospective_input_repair':{'proposal':delta,'minimum_explicit_root':'OpenGL.GL','known_missing_static_dependency_entries':len(additions),
   'action':'For a fresh prospective closure, explicitly supply reviewed OpenGL.GL source dependencies including package __init__.py records regardless of byte length. Use the exact modules_to_add proposal as the known static input delta; preserve all existing rows and strict audit behavior. Do not rerun historical import probes or the measurement to discover authority.',
   'no_source_edit_reason':'Existing builder already includes empty packages when supplied/loaded. Existing audit correctly rejects missing names, changed bytes and changed paths. Changing audit or adding an empty-file exception would be wrong.',
   'historical_artifacts_modified':False,'prospective_closure_built':False,'dynamic_coverage_complete':False},
 'minimal_affected_prospective_artifact_set':[
   'New immutable runtime-source closure with reviewed input delta; runtime-input/model inventory data/runtime-inventory.json is a different artifact and is unaffected by this module omission.',
   'Fresh recovery identity, preparation policy/specification/path slots and recovery-prefix/accounting bindings retaining the failed predecessor.',
   'Only direct/transitive references to the changed runtime closure and fresh identity: prospective audit view, affected expected manifests, engineering manifest/plan, graph and reviewed preparation release. Do not rebuild unrelated provenance.',
   'Disabled runtime/baseline only if fresh identity policy requires a changed binding; then update its direct dependents. Preserve immutable historical baseline.',
   'Controller review content remains reusable if controller source/config/runtime binding is unchanged; no renewed semantic review merely for OpenGL additions. If runtime reference changes, rebind and review those references without repeating unchanged semantic findings.'
 ],
 'next_recovery_requirements':{
   'failed_resource_id':'n36_readiness_preparation_recovery_001723','replay_allowed':False,'next_resource_id':None,
   'requirements':['Owner must separately record a fresh unique recovery identity naming the aborted predecessor; this executor allocates no identity or lease.',
       'Retain exact predecessor accounting and incomplete telemetry; no refund or conversion to successful readiness.',
       'Review the prospective input delta and any remaining dynamic coverage before binding a fresh graph; never mutate frozen old closure/release/plan.',
       'Require separate reviewed release with current source/interpreter/closure/graph hashes, finite budget and STOP/deadline authority before any new measurement.',
       'Reuse accepted controller source/semantic reviews where their bound inputs remain unchanged; source commit remains unchanged here.',
       'No health/episode authorization follows from these CPU checks.']},
 'retained_failed_preparation_charge':{'resource_id':'n36_readiness_preparation_recovery_001723','gpu_process_wall_seconds':234.03980207443237,'provider_calls':1,'telemetry_complete':False,'additional_gpu_hours':T['additional_gpu_hours'],'ledger_mutation':False},
 'constraints':{'gpu_execution':False,'native_simulation':False,'provider_calls':0,'health_execution':False,'episode_execution':False,'cloud_execution':False,'agents_spawned':False,'owner_state_or_ledger_mutation':False,'leases_acquired':False,'historical_inventory_release_plan_modified':False,'protected_results_or_prohibited_design_opened':False,'credentials_opened':False,'graph_rebuilt':False,'scientific_source_or_thresholds_changed':False},
 'score':None,'promotion_claim':False,'readiness_accepted':False,
 'stop_authority':A['stop_authority'],'STOP_present_at_completion':False,
 'artifacts':[ref(OUT/'focused-check-v1.py'),ref(OUT/'focused-check-results-v1.json'),delta,ref(OUT/'write-report-v1.py')]
}
assert report['cause']['evidence']['frozen_empty_package_count']==sum(r['path'].endswith('/__init__.py') and r['sha256']==empty_sha for r in M.values())
report_ref=save('report-v1.json',report)
print(json.dumps({'report':report_ref,'source_changed':False,'static_modules_examined':len(reached),'proposed_added_modules':len(additions),'checks':7}))
