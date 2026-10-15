import ast, copy, datetime, hashlib, json, math, os, pathlib, subprocess
from types import SimpleNamespace

OUT = pathlib.Path(__file__).parent
A = json.loads((OUT / 'authority-v1.json').read_text())
ROOT = pathlib.Path(A['worktree'])
B = pathlib.Path(A['inputs'][0]['path']).parent
OLD = B.parents[1] / '001632/runtime-binding-refresh'
evidence, checks = [], []
def read(p):
    return json.loads(pathlib.Path(p).read_text())
def ref(p):
    p = pathlib.Path(p); data = p.read_bytes()
    return {'path': str(p), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
def verify(r):
    v = ref(r['path']); v['matches'] = v['sha256'] == r['sha256'] and ('bytes' not in r or v['bytes'] == r['bytes'])
    evidence.append(v); assert v['matches'], v
def check(name, ok, **details):
    checks.append({'check': name, 'status': 'PASS' if ok else 'FAIL', **details})
def git(*args, cwd=ROOT):
    return subprocess.check_output(['git','--no-replace-objects','-C',str(cwd),*args],text=True).strip()
for p in [B.parents[2]/'STOP', pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP')]:
    assert not os.path.lexists(p), 'STOP'
assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
evidence.append(ref(OUT/'authority-v1.json'))
for r in A['inputs']+[A['standing_authority']]+list(A['ledger_prefixes'].values()): verify(r)
report=read(B/'report-v1.json')
# Hash immediate outputs and prepared anchors only; never follow their history.
for r in report['outputs']: verify(r)
for r in report['prepared'].values():
    if isinstance(r,dict) and 'path' in r and 'sha256' in r: verify(r)
plan=read(B/'engineering-plan.draft-disabled-v1.json'); audit=read(B/'audit-view.disabled-v1.json')
controller=read(B/'controller-semantics.proposed-disabled-v1.json')
for d in [plan,audit,controller]:
    for k in ['runtime','runtime_closure','scope','accounting','deployment','native_build','controller_semantics','scientific_equivalence','audit_plan','engineering_manifest','protocol','protocol_review']:
        if isinstance(d.get(k),dict) and 'path' in d[k]: verify(d[k])
for r in controller['review_evidence'].values():
    verify(r); d=read(r['path'])
    for x in d['sources']: verify(x)
    for x in d['sources']:
        if '/variants/n36_engineering_adapter_001482/implementation_worktree/' in x['path']:
            local=ROOT/x['path'].split('/implementation_worktree/',1)[1]
            verify({'path':str(local),'sha256':x['sha256']})
closure=read(plan['runtime_closure']['path'])
check('Controller immediate binding consistency',controller['source']==closure['modules'][controller['module']] and all(read(r['path'])['runtime']==plan['runtime'] and read(r['path'])['runtime_closure']==plan['runtime_closure'] and read(r['path'])['source_commit']==A['source'] for r in controller['review_evidence'].values()))
check('Exact isolated source and clean tracked files',git('rev-parse','HEAD')==A['source'] and not git('status','--porcelain','--untracked-files=no'))
dep=read(plan['deployment']['path'])
check('Deployment mismatch independently confirmed',git('rev-parse','HEAD',cwd=dep['source_cwd']) != A['source'],deployment_head=git('rev-parse','HEAD',cwd=dep['source_cwd']),reviewed_head=A['source'],source_cwd=dep['source_cwd'])
check('Deployment can advance along exact ancestry',subprocess.run(['git','--no-replace-objects','-C',dep['source_cwd'],'merge-base','--is-ancestor','HEAD',A['source']],capture_output=True).returncode==0)
delta=git('diff','--name-only',git('rev-parse','HEAD',cwd=dep['source_cwd']),A['source'],'--').splitlines()
check('Only three canonical runtime repair paths differ at deployment',set(delta)=={'configs/qd_ed_final/n36_engineering_r1_spec.disabled.json','scripts/qd_ed_n36_engineering_r1.py','tests/test_n36_engineering_r1.py'},changed_paths=delta)
for name,keys in [('engineering-plan.draft-disabled-v1.json',['episodes','limits','cohort','purpose','stop_path','stop_authority','artifact_root','worktree']),('audit-view.disabled-v1.json',['episodes','limits','cohort','protocol','protocol_review','accounting','artifact_root','worktree']),('accounting.disabled-v1.json',['accounting','retained_ledger_prefixes','retained_snapshot_reference']),('scope.disabled-v1.json',['scope'])]:
    old_path = pathlib.Path(read(OLD/'engineering-plan.draft-disabled-v1.json')[name.split('.')[0]]['path']) if name.startswith(('accounting.','scope.')) else OLD/name
    x,y=read(B/name),read(old_path); evidence.append(ref(old_path))
    check('Immediate predecessor preservation: '+name,all(x[k]==y[k] for k in keys),fields=keys)
old_audit=read(OLD/'audit-view.disabled-v1.json')
pairs=[(audit['expected_manifests'][k],old_audit['expected_manifests'][k]) for k in audit['expected_manifests']]
pairs.append((plan['engineering_manifest'],read(OLD/'engineering-plan.draft-disabled-v1.json')['engineering_manifest']))
for nr,orr in pairs:
    verify(nr);verify(orr);n,o=read(nr['path']),read(orr['path'])
    nc,oc=copy.deepcopy(n['resolved_config']),copy.deepcopy(o['resolved_config'])
    for k in ['n34_runtime_binding','n36_runtime_binding']:
        if isinstance(nc.get(k),dict):
            # Only source_commit is permitted to change in runtime config binding.
            nc[k]['source_commit']=oc[k]['source_commit']
    def normalize(argv):
        return [s.replace(A['source'],read(OLD/'engineering-plan.draft-disabled-v1.json')['source']['commit']) for s in argv]
    check('Manifest science/identity/argv preservation: '+n['row']['episode_key'],nc==oc and n['row']==o['row'] and n['output_dir']==o['output_dir'] and normalize(n['argv'])==o['argv'])
eq=read(plan['scientific_equivalence']['path']); changed=git('diff','--name-only',eq['base_commit'],A['source'],'--').splitlines()
check('Correct splitlines scientific equivalence comparison',sorted(changed)==eq['changed_paths'] and not eq['scientific_changes'],changed_paths=changed)
runtime=read(plan['runtime']['path']);spec=read(report['prepared']['specification_reused_exact']['path']);template=read(spec['canonical_runtime']['path']);verify(spec['canonical_runtime'])
template['preparation']['source']=runtime['preparation']['source'];template['preparation']['source_record']=runtime['preparation']['source_record']
check('Exact runtime derivation and false readiness',runtime==template and runtime['cuda_egl_verified'] is False and runtime['provider_ready'] is False and runtime['preparation']['runtime_ready'] is False)
mut=copy.deepcopy(runtime);mut['cuda_egl_verified']=mut['provider_ready']=True
check('Readiness mutation conflicts with exact template',mut!=template)
# Execute extracted pure source functions only; no package/controller/env imports.
import numpy as np
def extract(path,name):
    source=pathlib.Path(path).read_text();tree=ast.parse(source)
    node=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name][-1]
    node.decorator_list=[]
    return compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(path),'exec')
rs=pathlib.Path('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite')
ns={'np':np,'math':math};exec(extract(rs/'controllers/base_controller.py','scale_action'),ns)
s=SimpleNamespace(action_scale=None,input_min=np.full(6,-1.),input_max=np.ones(6),output_min=-np.array([.05]*3+[.5]*3),output_max=np.array([.05]*3+[.5]*3))
got=ns['scale_action'](s,np.array([2,-2,0,.5,-.5,0.]));check('Extracted scale_action clipping scaling zero',np.allclose(got,[.05,-.05,0,.25,-.25,0]),output=got.tolist())
exec(extract(rs/'utils/control_utils.py','set_goal_position'),ns)
exec(extract(rs/'controllers/osc.py','set_goal'),ns)
sentinel=np.eye(3)*2;s.goal_ori=sentinel;s.update=lambda:None;s.impedance_mode='fixed';s.use_delta=True;s.use_ori=True;s.ee_pos=np.array([1.,2.,3.]);s.ee_ori_mat=np.eye(3);s.orientation_limits=None;s.position_limits=None;s.interpolator_pos=None;s.interpolator_ori=None;s.scale_action=lambda a:ns['scale_action'](s,a)
ns['set_goal'](s,np.array([1,0,-1,0,0,0.]));check('Extracted set_goal zero orientation retains old goal and updates position',s.goal_ori is sentinel and np.allclose(s.goal_pos,[1.05,2,2.95]))
exec(extract(rs/'models/grippers/panda_gripper.py','format_action'),ns)
g=SimpleNamespace(dof=1,current_action=np.zeros(2),speed=.2)
closed=ns['format_action'](g,np.array([1.])).copy();opened=ns['format_action'](g,np.array([-1.])).copy();check('Extracted gripper signed incremental commands',np.allclose(closed,[-.2,.2]) and np.allclose(opened,[0,0]),close_increment=closed.tolist(),after_open=opened.tolist())
for p in ['scripts/qd_ed_n36_engineering_r1.py','scripts/qd_ed_n36_release.py','scripts/qd_ed_n34_controller.py','scripts/qd_ed_n34_source.py','core/env_adapters/libero_adapter.py','third_party/libero_pro/libero/libero/envs/env_wrapper.py','configs/qd_ed_final/n36_engineering_r1_spec.disabled.json']:
    evidence.append(ref(ROOT/p))
result={'schema':'n36-independent-bounded-checks-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Read-only immediate graph hashes, predecessor comparisons and extracted pure CPU functions; not native execution','checks':checks,'immediate_evidence':evidence,'historical_validator_totals_retained':report['validator_totals'],'historical_supplemental_failure_retained':report['supplemental_failure_retained'],'source_clean_end':not git('status','--porcelain','--untracked-files=no')}
(OUT/'bounded-checks-v1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'checks':len(checks),'failed':[x for x in checks if x['status']!='PASS'],'references':len(evidence),'result':str(OUT/'bounded-checks-v1.json')}))
