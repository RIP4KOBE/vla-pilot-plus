import os,sys,json,pathlib,hashlib,copy,datetime,time,traceback,subprocess,signal
O=pathlib.Path(__file__).absolute().parent; T=O.parent.parent
P=T/'001627/affected-binding-refresh/attempt-2'
ROOT=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from scripts import qd_ed_n36_engineering_r1 as e,qd_ed_n36_bridge as b,qd_ed_n23_worker as w,qd_ed_n36_stop as stop
start=time.monotonic(); inputs={};outputs={};checks=[];commands=[]
def guard():
 stop.check()
 if time.monotonic()-start>1000:raise TimeoutError('bounded CPU generation deadline')
def rec(p):
 p=pathlib.Path(p);return {'path':str(p),'sha256':w.sha(p),'bytes':p.stat().st_size}
def ref(p,canonical=False):
 p=pathlib.Path(p).resolve() if canonical else pathlib.Path(p)
 return {k:v for k,v in rec(p).items() if k!='bytes'}
def load(p,expected=None):
 guard();r=rec(p)
 if expected:assert r['sha256']==expected
 inputs[str(p)]=r
 return json.loads(pathlib.Path(p).read_text())
def read(r):return load(r['path'],r['sha256'])
def save(n,d,canonical=False):
 guard();p=O/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,sort_keys=True,separators=(',',':'),allow_nan=False)
 outputs[n]=rec(p);return ref(p,canonical)
def check(n,expr,fn):
 guard();t=time.monotonic()
 try:fn();r={'check':n,'expression':expr,'status':'PASS'}
 except Exception as ex:r={'check':n,'expression':expr,'status':'FAIL','exception':type(ex).__name__,'message':str(ex),'traceback':traceback.format_exc()}
 r['elapsed_seconds']=time.monotonic()-t;checks.append(r);print(n,r['status'],r.get('message',''),flush=True);return r
def cmd(argv):
 guard();r=subprocess.run(argv,capture_output=True,text=True,timeout=60);commands.append({'argv':argv,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});assert r.returncode==0;return r.stdout
try:
 a=load(O/'authority-v1.json');assert str(O)==a['output_directory']
 read(a['runtime_preparation']);read(a['runtime_amendment']);read(a['amendment']);read(a['standing_authority']);review=read(a['source_review'])
 inputs[str(T/'001627/affected-binding-refresh/refresh-graph-v2.disabled.py')]=rec(T/'001627/affected-binding-refresh/refresh-graph-v2.disabled.py')
 prior_results=load(P/'generation-results-v1.json')
 def prior(n):return load(P/n,prior_results['outputs'][n]['sha256'])
 oldplan=prior('engineering-plan.draft-disabled-v1.json');oldaudit=prior('audit-view.disabled-v1.json')
 source=prior('source-inventory.disabled-v1.json');assert source==oldplan['source']==oldplan['scientific_source'] and source['commit']==a['source_base']==review['source_commit']
 head=cmd(['git','--no-optional-locks','-C',str(ROOT),'rev-parse','HEAD']).strip();assert head==source['commit']
 status=cmd(['git','--no-optional-locks','-C',str(ROOT),'status','--porcelain=v1','--untracked-files=no']);assert not status
 for r in review['source_file_hashes']:assert w.sha(ROOT/r['path'])==r['sha256']
 for n,r in a['ledger_prefixes'].items():assert rec(r['path'])==r;inputs[r['path']]=r
 source_ref=save('source-inventory.disabled-v1.json',source)
 runtime=read(a['runtime']);runtime_before=copy.deepcopy(runtime)
 assert runtime['preparation']['source_record'] is None and runtime['preparation']['source']==source['commit']
 runtime['preparation']['source_record']=source_ref
 rtref=save('runtime.source-bound.disabled-v1.json',runtime,canonical=True)
 assert not runtime['cuda_egl_verified'] and not runtime['provider_ready'] and not runtime['gpu_mapping']['cuda_egl_verified'] and not runtime['preparation']['runtime_ready'] and not runtime['preparation']['release_enabled']
 closure=prior('runtime-closure.disabled-v1.json');closure_before=copy.deepcopy(closure);closure['runtime']=rtref
 clref=save('runtime-closure.disabled-v1.json',closure)
 proof=prior('controller-semantics.proposed-disabled-v1.json')
 def proposal(d,pr):
  d=copy.deepcopy(d);assert d['status']=='PENDING_INDEPENDENT_AND_ROOT_REVIEW'
  d.update(runtime=rtref,runtime_closure=clref)
  d['reference_refresh_lineage']={'prior_evidence':pr,'prior_status':'PENDING_INDEPENDENT_AND_ROOT_REVIEW','semantic_findings_unchanged':True,'new_root_approval':False,'independent_certification':False,'preparation_authority':ref(O/'authority-v1.json')}
  return d
 proof=proposal(proof,ref(P/'controller-semantics.proposed-disabled-v1.json'))
 for n,r in proof['review_evidence'].items():proof['review_evidence'][n]=save('controller-evidence/'+n+'.proposed-disabled-v1.json',proposal(read(r),r))
 proofref=save('controller-semantics.proposed-disabled-v1.json',proof)
 audit=copy.deepcopy(oldaudit);audit.update(runtime=rtref,runtime_closure=clref,controller_semantics=proofref,expected_manifests={})
 # Exact reference-only drafts. Existing helper rejection is retained below, never bypassed.
 fields={'runtime':rtref,'runtime_closure':clref,'controller_semantics':proofref}
 for row in audit['episodes']:
  key=row['episode_key'];m=read(oldaudit['expected_manifests'][key]);m.update(fields)
  audit['expected_manifests'][key]=save('audit-manifests/'+key+'.disabled.json',m)
 auditref=save('audit-view.disabled-v1.json',audit)
 plan=copy.deepcopy(oldplan);plan.update(fields,audit_plan=auditref)
 oldm=read(oldplan['engineering_manifest']);m=copy.deepcopy(oldm);m.update(fields,audit_plan=auditref,audit_manifest=audit['expected_manifests'][m['audit_row']['episode_key']])
 mr=save('engineering-manifest.disabled-v1.json',m);plan.update(engineering_manifest=mr,expected_manifests={e.EPISODE_KEY:mr})
 assert plan['authority'] is None and plan['b5_review'] is None and not plan['release_enabled'] and not plan['frozen']
 pr=save('engineering-plan.draft-disabled-v1.json',plan)
 save('bindings.disabled-v1.json',{'schema':'n36-engineering-r1-binding-refresh-draft-v1','bindings':e.review_bindings(plan),'plan':pr,'release_enabled':False,'gpu_authorized':False,'controller_review':'PENDING','root_review':'PENDING','independent_b5':'PENDING','helper_generation_accepted':False})
 for k in ('scope','accounting','deployment','scientific_equivalence','native_build'):read(plan[k])
 spec=read(e.SPECIFICATION)
 save('binding-diff.disabled-v1.json',{'runtime_preparation_change':{'field':'preparation.source_record','before':None,'after':source_ref,'justification':'Bind already accepted reviewed source record; all remaining runtime fields unchanged.'},'runtime_reference_before':oldplan['runtime'],'runtime_reference_after':rtref,'pinned_source_specification_runtime':spec['canonical_runtime'],'closure_only_change':'runtime','manifest_only_changes':['runtime','runtime_closure','controller_semantics','audit_plan (engineering only)','audit_manifest (engineering only)'],'unchanged_plan_bindings':[k for k in e.BINDINGS if oldplan[k]==plan[k]],'helper_generation_accepted':False,'release_enabled':False})
 check('Reviewed source closure','b.verify_sources(plan)',lambda:b.verify_sources(plan))
 check('Loaded source bytes','b.attest_loaded(plan["worktree"],plan["source"])',lambda:b.attest_loaded(plan['worktree'],source))
 check('Runtime closure','b.closure.verify_runtime(closure,rtref)',lambda:b.closure.verify_runtime(closure,rtref))
 check('R1 disabled scope','e.validate_scope_reference(plan["scope"])',lambda:e.validate_scope_reference(plan['scope']))
 check('R1 disabled accounting','e.validate_accounting_reference(plan["accounting"])',lambda:e.validate_accounting_reference(plan['accounting']))
 check('R1 lexical deployment','e.deployment(plan)',lambda:e.deployment(plan))
 check('R1 draft plan shape','e.validate_plan_shape(plan)',lambda:e.validate_plan_shape(plan))
 check('R1 all40 audit shape','e.validate_audit_view(audit)',lambda:e.validate_audit_view(audit))
 check('R1 exact audit mapping','e.audit_mapping(plan,audit,e.row())',lambda:e.audit_mapping(plan,audit,e.row()))
 check('R1 scientific equivalence','e.scientific_equivalence(plan)',lambda:e.scientific_equivalence(plan))
 check('Terminal parent prefixes and retained accounting','e.terminal_parent_prefix()',e.terminal_parent_prefix)
 check('Full actual CPU audit closure','e.full.verify_audit_closure(audit)',lambda:e.full.verify_audit_closure(audit))
 for row in audit['episodes']:
  check('Audit manifest helper '+row['episode_key'],'b._verify_manifest_bound(audit["expected_manifests"][row["episode_key"]],audit,runtime,row)',lambda row=row:b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']],audit,runtime,row))
 check('Engineering R1 manifest helper','b.verify_engineering_manifest(mr,plan,runtime,e.row(),audit=audit)',lambda:b.verify_engineering_manifest(mr,plan,runtime,e.row(),audit=audit))
 from scripts.qd_ed_n36_build import manifest as native_manifest
 check('Preserved native build bytes','native_manifest(plan["native_build"])',lambda:native_manifest(plan['native_build']))
 def dino():
  from scripts.qd_ed_n36_dino import DinoSources
  d=DinoSources(rtref)
  for n,p in d.names.items():d.check_file(n,p)
 check('Canonical DINO runtime reference and source bytes','DinoSources(rtref); check_file for every source',dino)
 def runtime_files():
  e.r.verify_files(runtime['files'],allowed_roots=(plan['worktree'],runtime['worktree'],runtime['artifact_root']))
  fingerprints={str(pathlib.Path(x['path']).resolve()) for x in runtime['files']}
  for task in runtime['tasks'].values():
   actual={str(p.resolve()) for p in pathlib.Path(task['cache_dir']).rglob('*') if p.is_file()};w.require(actual and actual<=fingerprints,'task cache inventory incomplete')
 check('Runtime file and task cache validators','e.r.verify_files(runtime["files"],allowed_roots=(plan["worktree"],runtime["worktree"],runtime["artifact_root"])); exact task cache coverage',runtime_files)
 check('Frozen runtime checkpoint task seed validators','e.r.validate_runtime_inputs(audit,runtime,b.profiles(plan["worktree"]),ROOT,{"artifacts":runtime["artifact_root"]})',lambda:e.r.validate_runtime_inputs(audit,runtime,b.profiles(plan['worktree']),ROOT,{'artifacts':runtime['artifact_root']}))
 from scripts.qd_ed_n34_controller import verify_semantics
 check('Pending controller attestation gate','verify_semantics(proofref,rtref,closure)',lambda:verify_semantics(proofref,rtref,closure))
 def configs():
  for r in list(audit['expected_manifests'].values())+[mr]:
   guard();v=json.loads(pathlib.Path(r['path']).read_text());config,resolved=b.compose_launch(v['argv'],plan['worktree']);assert w.canonical_sha(config)==v['composed_config_sha256'] and resolved==v['resolved_config']
 check('41 preserved argv scientific configuration recompositions','b.compose_launch for all40 audit and R1; compare composed hash and resolved config',configs)
 def preservation():
  before=copy.deepcopy(runtime_before);before['preparation']['source_record']=source_ref;assert runtime==before
  before=copy.deepcopy(closure_before);before['runtime']=rtref;assert closure==before
  for k in oldaudit:
   if k not in (*fields,'expected_manifests'):assert oldaudit[k]==audit[k]
  for k in oldplan:
   if k not in (*fields,'audit_plan','engineering_manifest','expected_manifests'):assert oldplan[k]==plan[k]
  assert all(rec(p)==r for p,r in inputs.items())
  for key,r in a['ledger_prefixes'].items():assert rec(r['path'])==r
 check('Exact preservation and unchanged input hashes','runtime/source binding only; closure runtime only; science and all immediate inputs unchanged; ledgers exact',preservation)
 save('preservation-verification-v1.json',{'inputs':[{'before':r,'after':rec(p),'unchanged':rec(p)==r} for p,r in inputs.items()],'ledgers':{n:{'before':r,'after':rec(r['path']),'unchanged':rec(r['path'])==r} for n,r in a['ledger_prefixes'].items()},'runtime_inventory_records_preserved':len(runtime['files']),'runtime_readiness':{k:runtime[k] for k in ('cuda_egl_verified','provider_ready')},'runtime_gpu_mapping_readiness':runtime['gpu_mapping']['cuda_egl_verified'],'source_head':head,'source_status_after':cmd(['git','--no-optional-locks','-C',str(ROOT),'status','--porcelain=v1','--untracked-files=no']),'stop_paths':[{'path':p,'absent':not os.path.lexists(p)} for p in stop.STOP_PATHS]})
except Exception as ex:
 checks.append({'check':'generation','status':'FAIL','message':str(ex),'traceback':traceback.format_exc()});print(traceback.format_exc(),flush=True)
finally:
 save('generation-results-v1.json',{'schema':'n36-runtime-binding-refresh-results-v1','inputs':list(inputs.values()),'outputs':outputs.copy(),'checks':checks,'commands':commands,'elapsed_seconds':time.monotonic()-start,'release_enabled':False,'gpu_authorized':False})
