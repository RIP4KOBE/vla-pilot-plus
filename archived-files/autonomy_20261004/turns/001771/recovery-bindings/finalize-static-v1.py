"""Resolve source inventory/policy/deployment uncertainties; finalize own report only."""
import ast, hashlib, json, os, subprocess, sys, types
from pathlib import Path
sys.dont_write_bytecode=True
O=Path(__file__).absolute().parent
report=json.loads((O/'report-v1.json').read_text());ROOT=Path(report['source']['worktree'])
A=json.loads((O/'authority-v1.json').read_text())
assert not any(os.path.lexists(p) for p in A['stop_authority']['paths'])
def rec(p):
 p=Path(p);d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
def ref(p):return {k:v for k,v in rec(p).items() if k!='bytes'}
def save(n,d):
 p=O/n;assert not p.exists();p.write_text(json.dumps(d,sort_keys=True,separators=(',',':'))+'\n');return ref(p)
def extract(file,names,ns):
 p=ROOT/file;t=ast.parse(p.read_bytes());nodes=[]
 for n in t.body:
  if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names:nodes.append(n)
  elif isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id in names for x in n.targets):nodes.append(n)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns);return ns
base=dict(Path=Path,json=json,hashlib=hashlib,os=os,subprocess=subprocess)
w=types.SimpleNamespace(**extract('scripts/qd_ed_n23_worker.py',{'require','sha','canonical_sha','read_ref','_source_git','_source_entry'},base.copy()))
e=types.SimpleNamespace(**extract('scripts/qd_ed_n36_engineering_r1.py',{'exact','read','reference','HEALTH_ID'},dict(base,w=w)))
prep=extract('scripts/qd_ed_n36_readiness_prepare.py',{'SCHEMA','FIELDS','MEASUREMENT_CONTRACT','closed','policy'},dict(e=e,Path=Path))
spec=json.loads(Path(report['specification']['path']).read_text());policy=prep['policy'](spec)
assert policy['resource_id']==report['resource_id']
cl=extract('scripts/qd_ed_n34_source.py',{'PINNED_SUBMODULES','RDT','LEROBOT','LIBERO','SOURCE_SUFFIXES','submodule_pin','submodule_paths','dependency_paths'},dict(base,w=w))
rns=extract('scripts/qd_ed_final_runner.py',{'REQUIRED_CODE'},dict(ROOT=ROOT))
tree=ast.parse((ROOT/'scripts/qd_ed_final_runner.py').read_bytes())
updates=[n for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='REQUIRED_CODE']
exec(compile(ast.Module(body=updates,type_ignores=[]),'scripts/qd_ed_final_runner.py','exec'),rns)
bn=extract('scripts/qd_ed_n36_bridge.py',{'source_paths'},dict(Path=Path,ROOT=ROOT,runner=types.SimpleNamespace(**rns),closure=types.SimpleNamespace(**cl)))
actual=bn['source_paths'](ROOT);record=json.loads(Path(report['source_record']['path']).read_text())
assert actual=={x['path'] for x in record['files']}
adm=extract('scripts/qd_ed_n36r2_admission.py',{'SESSION'},dict(Path=Path))
deploy=extract('scripts/qd_ed_n36_engineering_r1.py',{'SOURCE'},adm)['SOURCE']
commit=subprocess.check_output(['git','--no-optional-locks','-C',str(deploy),'rev-parse','HEAD'],text=True).strip()
assert deploy.resolve()!=ROOT.resolve() and commit!=report['source']['commit']
checks=save('supplemental-static-validation-v1.json',dict(schema='n36-source-policy-route-static-validation-v1',method='Unchanged production AST definitions; no native imports or production module import.',checks=[dict(check='production preparation policy real authority/baseline/lineage/path checks',status='PASS'),dict(check='production source_paths exactly matches all 1116 source-record entries',status='PASS')],deployment=dict(required_path=str(deploy),resolved_path=str(deploy.resolve()),commit=commit,required_commit=report['source']['commit'],matches=False),production_files=[rec(ROOT/p) for p in ['scripts/qd_ed_final_runner.py','scripts/qd_ed_n36_bridge.py','scripts/qd_ed_n36_readiness_prepare.py','scripts/qd_ed_n36r2_admission.py']],release_enabled=False))
report['supplemental_validation']=checks
report['blockers'][-1].update(required_source_route=str(deploy),deployed_commit=commit,deployed_path_resolves_to=str(deploy.resolve()))
manifest=json.loads((O/'artifact-manifest-v1.json').read_text())
manifest['files'] += [rec(__file__),rec(O/'supplemental-static-validation-v1.json')]
(O/'artifact-manifest-v1.json').write_text(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
report['artifact_manifest']=ref(O/'artifact-manifest-v1.json')
report['finalized_at']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
(O/'report-v1.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
(O/'report-v1.sha256').write_text(rec(O/'report-v1.json')['sha256']+'  report-v1.json\n')
for f in manifest['files']:assert rec(f['path'])==f
for v in A['ledger_prefixes'].values():assert all(rec(v['path'])[k]==v[k] for k in ('bytes','sha256'))
assert subprocess.check_output(['git','--no-optional-locks','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==A['source']
assert not subprocess.check_output(['git','--no-optional-locks','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True).strip()
print(json.dumps(dict(report=ref(O/'report-v1.json'),status=report['status'],manifest_files=len(manifest['files']),deployed_commit=commit)))
