import ast,hashlib,json,os,types,datetime
from pathlib import Path
out=Path(__file__).parent
root=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
a=json.loads((out/'authority-v1.json').read_text());report=json.loads(Path(a['preparation_report']['path']).read_text());plan=json.loads(Path(report['roots']['plan']['path']).read_text())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(c,msg):
 if not c:raise ValueError(msg)
def extract(file,name,env):
 tree=ast.parse((root/file).read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(root/file),'exec'),env)
 return env[name]
verify=extract('scripts/qd_ed_final_runner.py','verify_files',{'Path':Path,'os':os,'require':require,'digest':digest})
runtime_file=extract('scripts/qd_ed_n34_source.py','_runtime_file',{'Path':Path,'w':types.SimpleNamespace(require=require,sha=digest)})
rows=[]
for kind in ['runtime','runtime_closure']:
 doc=json.loads(Path(plan[kind]['path']).read_text())
 entries=enumerate(doc['files']) if kind=='runtime' else doc['modules'].items()
 for key,r in entries:
  if Path(r['path']).name not in ['qd_ed_n36_healthcheck.py','qd_ed_n36_runner.py','qd_ed_n36_worker.py']:continue
  error=None
  try:
   if kind=='runtime':verify([r],allowed_roots=(str(root),))
   else:runtime_file(r)
  except ValueError as e:error=str(e)
  assert error
  rows.append({'artifact':plan[kind],'json_pointer':('/files/'+str(key)) if kind=='runtime' else '/modules/'+key,'path':r['path'],'recorded_sha256':r['sha256'],'actual_sha256':digest(r['path']),'recorded_size_bytes':r.get('size_bytes'),'actual_size_bytes':Path(r['path']).stat().st_size,'validator':'verify_files' if kind=='runtime' else '_runtime_file','rejection':error,'exact_unmodified_AST':True})
assert len(rows)==6
result={'schema':'n36-b5-focused-runtime-incompatibility-v1','source':a['source'],'six_rejections_confirmed':True,'results':rows,'full_runtime_or_release_verifier_executed':False,'native_or_model_imports':False,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
with (out/'focused-runtime-incompatibility-v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result,indent=2))
