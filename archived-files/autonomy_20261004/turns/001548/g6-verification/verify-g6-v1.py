"""Bounded passive G6: standard library only, no candidate import or execution."""
import ast, datetime, hashlib, json, os, resource, time
from pathlib import Path
OUT=Path(__file__).resolve().parent
START=time.monotonic(); CPU=time.process_time()
resource.setrlimit(resource.RLIMIT_CPU,(1100,1100))
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
inputs=[]; checks=[]; cache={}
def digest(p):
 p=Path(p); h=hashlib.sha256(); n=0
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024): h.update(b); n+=len(b)
 return {'path':str(p),'bytes':n,'sha256':h.hexdigest()}
def bind(ref):
 p=ref['path']
 if p not in cache: cache[p]=digest(p);inputs.append(cache[p])
 a=cache[p]; ok=a['sha256']==ref['sha256'] and ('bytes' not in ref or a['bytes']==ref['bytes'])
 checks.append({'check':'input_binding','expected':ref,'actual':a,'pass':ok})
 if not ok: raise ValueError('input binding mismatch: '+p)
 return a
def read(ref):
 bind(ref);return json.loads(Path(ref['path']).read_text())
def put(name,obj):
 p=OUT/name
 with p.open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
 return digest(p)
def check(name,ok,**details):checks.append({'check':name,'pass':bool(ok),**details})
a=json.loads((OUT/'authority-v1.json').read_text());inputs.append(digest(OUT/'authority-v1.json'))
g=read(a['accepted_g5_report']);review=read(a['accepted_g5_review']);bind(a['standing_authority'])
check('accepted_review_binds_g5',review['report']==a['accepted_g5_report'])
plan=read(g['outputs']['engineering-plan.disabled-v1.json']); audit=read(g['outputs']['audit-view.disabled-v1.json'])
rt=read(plan['runtime']);closure=read(plan['runtime_closure']);native=read(plan['native_build']);proof=read(plan['controller_semantics'])
source_ref=next(r for r in g['inputs'] if r['path'].endswith('/source.complete-v1.json'))
source=read(source_ref); equivalence=read(plan['scientific_equivalence'])
accepted_review=read(next(r for r in g['inputs'] if r['path'].endswith('001542/terminal-review-v1.json')))
check('accepted_G2_source_graph',source==plan['source'] and source['commit']==a['source'])
check('accepted_scientific_equivalence_binding',equivalence['source']==source and equivalence['scientific_changes'] is False)
root=Path(plan['worktree']); print('Source root',root,flush=True)
sourceidx={r['path']:r['sha256'] for r in source['files']}
verifier_files=['scripts/qd_ed_n36_build.py','scripts/qd_ed_n34_controller.py','scripts/qd_ed_n36_release.py','scripts/qd_ed_n36_engineering.py','scripts/qd_ed_n23_worker.py']
definitions=[]
selected={'manifest','verify_receipt','verify_semantics','attest_instance','verify_audit_closure','reference','read_ref','sha','canonical_sha','require_dispatch_implementation','launch_guard','review_bindings','validate_authority'}
for rel in verifier_files:
 path=root/rel;bind({'path':str(path),'sha256':sourceidx[rel]});text=path.read_text(); tree=ast.parse(text)
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in selected:
   definitions.append({'path':str(path),'function':node.name,'first_line':node.lineno,'last_line':node.end_lineno,'text':ast.get_source_segment(text,node)})
 if rel.endswith('qd_ed_n36_build.py'):
  required=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REQUIRED' for t in n.targets)))
 if rel.endswith('qd_ed_n36_engineering.py'):
  veto=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='require_dispatch_implementation')
  check('unconditional_dispatch_veto_AST',len(veto.body)==2 and isinstance(veto.body[1],ast.Raise),line=veto.lineno)
  guard=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='launch_guard')
  check('launch_guard_veto_first',ast.unparse(guard.body[0])=='require_dispatch_implementation()')
verifier_out=put('passive-verifier-definitions-v1.json',definitions)
check('native_schema',set(native)=={'schema','torch_version','cuda_version','torch_build','libraries'} and native['schema']=='n36-native-build-v1')
rows=native['libraries'];check('native_inventory_unique_nonempty',isinstance(rows,list) and bool(rows) and len({r['path'] for r in rows})==len(rows))
binary=[]
for i,r in enumerate(rows):
 p=Path(r['path']); item={'expected':r,'is_absolute':p.is_absolute(),'canonical_path':str(p.resolve())==str(p),'is_file':p.is_file(),'is_symlink':p.is_symlink()}
 try:
  actual=digest(p); item['actual']=actual;item['hash_matches']=actual['sha256']==r['sha256']
 except OSError as e:item['error']=str(e);item['hash_matches']=False
 item['pass']=set(r)=={'path','sha256'} and item['is_absolute'] and item['canonical_path'] and item['is_file'] and not item['is_symlink'] and item['hash_matches'];binary.append(item)
 if i%10==0:print('Hashed',i+1,'/',len(rows),flush=True)
names={Path(r['path']).name for r in rows};check('native_required_names',set(required)<=names and any(n.startswith('libcuda.so') for n in names));check('native_all_binary_predicates',all(r['pass'] for r in binary),count=len(binary))
check('native_runtime_metadata_consistency',native['torch_version']==closure['versions']['torch'] and native['cuda_version'] in native['torch_version'],limitation='Recorded metadata comparison, no loaded version or ABI verification.')
# Compare graph declarations without rewalking accepted dependency provenance.
index={r['path']:r['sha256'] for r in rows}; overlaps=[]
for module,ref in closure['modules'].items():
 if ref.get('path') in index:overlaps.append({'module':module,'path':ref['path'],'match':ref['sha256']==index[ref['path']]})
check('native_closure_overlapping_hashes',all(r['match'] for r in overlaps),overlaps=overlaps)
binary_out=put('native-binary-verification-v1.json',{'method':'streaming SHA256 and exact manifest predicates, no loading','manifest':plan['native_build'],'binaries':binary,'bytes_hashed':sum(x.get('actual',{}).get('bytes',0) for x in binary),'after_load_observed':False})
check('plan_audit_binding_equality',all(plan[k]==audit[k] for k in ['source','scientific_source','runtime','runtime_closure','native_build','controller_semantics']))
check('controller_runtime_graph',proof['runtime']==plan['runtime'] and proof['runtime_closure']==plan['runtime_closure'] and closure['runtime']==plan['runtime'])
check('controller_module_binding',proof['source']==closure['modules'][proof['module']] and proof['module'] in closure['required_after'])
check('disabled_authority_preserved',plan['release_enabled'] is False and plan['authority'] is None and plan['b5_review'] is None and not any(plan['phase_authorization'].values()))
controller=[]
for name,ref in proof['review_evidence'].items():
 evidence=read(ref);check('controller_evidence_'+name,evidence['runtime']==plan['runtime'] and evidence['runtime_closure']==plan['runtime_closure'] and evidence['fixture_only'] is False and evidence['kind']=='deployed_source_review')
 for src in evidence['sources']:
  bind(src);entry={'evidence':name,'record':src,'closure_modules':[k for k,v in closure['modules'].items() if v==src]}
  if '/implementation_worktree/' in src['path']:
   rel=src['path'].split('/implementation_worktree/',1)[1]; current={'path':str(root/rel),'sha256':sourceidx[rel]};bind(current)
   entry.update({'candidate_source':current,'candidate_hash_equal':current['sha256']==src['sha256'],'same_resolved_file':Path(src['path']).resolve()==Path(current['path']).resolve()})
  controller.append(entry)
controller_out=put('controller-source-bindings-v1.json',{'proof':plan['controller_semantics'],'sources':controller,'approval_status':proof['status'],'independent_b5':False})
# Ledger bytes only: no protected results parsing or cost recomputation.
ledgers=[]
for name,ref in a['ledger_prefixes'].items():
 p=Path(ref['path']);h=hashlib.sha256()
 with p.open('rb') as f:
  remaining=ref['bytes']
  while remaining:
   b=f.read(min(remaining,8*1024*1024))
   if not b:break
   h.update(b);remaining-=len(b)
 current=p.stat().st_size;ok=remaining==0 and h.hexdigest()==ref['sha256'];ledgers.append({'name':name,'prefix_sha256':h.hexdigest(),'prefix_agrees':ok,'current_bytes':current,'suffix_bytes':current-ref['bytes'],'reference':ref});check('retained_prefix_'+name,ok)
result={'inputs':inputs,'checks':checks,'outputs':[verifier_out,binary_out,controller_out], 'ledger_checks':ledgers,'retained_accounting':g['retained_accounting'],'retained_failed_attempts':g['retained_failed_attempts'],'accepted_review_summary':{'status':accepted_review.get('status'),'root_checks':accepted_review.get('root_checks')},'controller_approval_status':proof['status'],'controller_bindings':controller,'elapsed_seconds':time.monotonic()-START,'cpu_seconds':time.process_time()-CPU,'cpu_affinity':sorted(os.sched_getaffinity(0))}
put('actual-checks-v1.json',result)
print(json.dumps({'checks':len(checks),'failures':[x for x in checks if not x['pass']],'binary_count':len(binary),'elapsed':result['elapsed_seconds'],'cpu':result['cpu_seconds']}),flush=True)
