import os,sys,json,pathlib,hashlib,copy,datetime,time,traceback,subprocess,signal
sys.dont_write_bytecode=True
O=pathlib.Path(__file__).absolute().parent;T=O.parent.parent
ROOT=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree')
P=T/'001632/runtime-binding-refresh'
os.environ.update(PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1',CUDA_VISIBLE_DEVICES='')
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from scripts import qd_ed_n36_engineering_r1 as e,qd_ed_n36_bridge as b,qd_ed_n23_worker as w,qd_ed_n36_stop as stop
start=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat();inputs={};outputs={};checks=[];commands=[];manifest_checks=[]
def guard():
 stop.check(need=1)
 if time.monotonic()-start>1000:raise TimeoutError('bounded CPU preparation budget')
def rec(p):
 p=pathlib.Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def ref(p):return {k:v for k,v in rec(p).items() if k!='bytes'}
def verify(r):
 guard();actual=rec(r['path']);assert actual['sha256']==r['sha256'],str(r)
 if 'bytes' in r:assert actual['bytes']==r['bytes']
 inputs[r['path']]=actual;return actual

def load(p,expected=None):
 guard();r=rec(p)
 if expected:assert r['sha256']==expected,str(p)
 inputs[str(p)]=r;return json.loads(pathlib.Path(p).read_text())
def read(r):verify(r);return load(r['path'],r['sha256'])
def save(n,d):
 guard();p=O/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,sort_keys=True,separators=(',',':'),allow_nan=False)
 outputs[n]=rec(p);return ref(p)
def check(n,fn,blocked=False):
 guard();t=time.monotonic()
 try:fn();r={'check':n,'status':'PASS'}
 except Exception as ex:r={'check':n,'status':'BLOCKED' if blocked else 'FAIL','exception':type(ex).__name__,'message':str(ex),'traceback':traceback.format_exc()}
 r['elapsed_seconds']=time.monotonic()-t;checks.append(r);print(n,r['status'],r.get('message',''),flush=True);return r
def cmd(argv,cwd=ROOT):
 guard();r=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=60);commands.append({'argv':argv,'cwd':str(cwd),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});assert r.returncode==0,r.stderr;return r.stdout
try:
 a=load(O/'authority-v1.json');assert a['source_base']=='bd5dd4dabcb5a1f7823a9e2f51c849cd67767cb6'
 read(a['amendment']);read(a['standing_authority'])
 root=load(T/'001642/terminal-reconciliation-v1.json');review=read(root['review']);assert review['verdict']=='PASS' and root['source']==a['source_base']==review['source_commit']
 # Immediate anchors only: do not recurse into historical provenance.
 for r in root['checked_immediate_references']:verify(r)
 repair=load(T/'001635/canonical-runtime-repair/report-v1.json')
 binding=load(T/'001635/canonical-runtime-repair/binding-verification-v1.json')
 for r in binding['inputs_hash_verified']:verify(r)
 for r in review['changed_files']:
  assert w.sha(ROOT/r['path'])==r['source_sha256']
  inputs[str(ROOT/r['path'])]=rec(ROOT/r['path'])
 for r in a['ledger_prefixes'].values():verify(r)
 frozen=read(next(r for r in root['checked_immediate_references'] if r['path'].endswith('001608/engineering-plan.frozen-v2.json')))
 assert frozen['stop_authority']==stop.binding() and frozen['deadline']==stop.DEADLINE
 head=cmd(['git','rev-parse','HEAD']).strip();assert head==a['source_base']
 assert not cmd(['git','status','--porcelain=v1','--untracked-files=no'])
 prior_report=load(P/'report-v1.json');index={x['path']:x for x in prior_report['outputs']}
 verify(index[str(P/'refresh-disabled-v1.py')])
 def prior(n):return read(index[str(P/n)])
 oldplan=prior('engineering-plan.draft-disabled-v1.json');oldaudit=prior('audit-view.disabled-v1.json')
 source=read(review['binding_assessment']['source_inventory']);rtref=binding['runtime'];runtime=read(rtref);spec=read(e.SPECIFICATION)
 assert source==runtime['preparation']['source_record'] or runtime['preparation']['source']==head
 assert read(runtime['preparation']['source_record'])==source and source['commit']==head
 assert e.SPECIFICATION=={k:review['binding_assessment']['specification'][k] for k in ('path','sha256')}
 assert not runtime['cuda_egl_verified'] and not runtime['provider_ready'] and not runtime['preparation']['runtime_ready'] and not runtime['preparation']['release_enabled']
 scope=e.disabled_scope();accounting=e.disabled_accounting()
 oldscope=read(oldplan['scope']);oldaccounting=read(oldplan['accounting'])
 assert {k:v for k,v in oldscope.items() if k!='specification'}=={k:v for k,v in scope.items() if k!='specification'}
 assert {k:v for k,v in oldaccounting.items() if k!='specification'}=={k:v for k,v in accounting.items() if k!='specification'}
 sr=save('scope.disabled-v1.json',scope);ar=save('accounting.disabled-v1.json',accounting)
 changed=cmd(['git','diff','--name-only',e.BASE,head,'--']).splitlines();assert set(changed)<=e.OPERATIONAL_FILES
 eq={'schema':'n36-engineering-scientific-equivalence-v1','base_commit':e.BASE,'source':source,'changed_paths':sorted(changed),'scientific_changes':False}
 eqref=save('scientific-equivalence.disabled-v1.json',eq)
 deployment=read(oldplan['deployment'])
 closure=prior('runtime-closure.disabled-v1.json');oldclosure=copy.deepcopy(closure);closure['runtime']=rtref
 clref=save('runtime-closure.disabled-v1.json',closure)
 proof=prior('controller-semantics.proposed-disabled-v1.json')
 def proposal(d,prior_ref):
  d=copy.deepcopy(d);assert d['status']=='PENDING_INDEPENDENT_AND_ROOT_REVIEW'
  d.update(runtime=rtref,runtime_closure=clref,source_commit=head)
  d['reference_refresh_lineage']={'prior_evidence':prior_ref,'prior_status':'PENDING_INDEPENDENT_AND_ROOT_REVIEW','semantic_findings_unchanged':True,'new_root_approval':False,'independent_certification':False,'preparation_authority':ref(O/'authority-v1.json')}
  return d
 proof=proposal(proof,ref(P/'controller-semantics.proposed-disabled-v1.json'))
 for n,r in proof['review_evidence'].items():proof['review_evidence'][n]=save('controller-evidence/'+n+'.proposed-disabled-v1.json',proposal(read(r),r))
 proofref=save('controller-semantics.proposed-disabled-v1.json',proof)
 fields={'source':source,'scientific_source':source,'scope':sr,'runtime':rtref,'runtime_closure':clref,'controller_semantics':proofref}
 audit=copy.deepcopy(oldaudit);audit.update(fields,expected_manifests={})
 # Existing lexical deployment is retained pending separately authorized placement/adoption.
 # Helpers execute from the reviewed variant, with the complete exact reviewed source record.
 for row in audit['episodes']:
  guard();key=row['episode_key'];m=b.manifest(audit,runtime,row)
  audit['expected_manifests'][key]=save('audit-manifests/'+key+'.disabled.json',m)
  print('generated audit',key,flush=True)
 auditref=save('audit-view.disabled-v1.json',audit)
 plan=copy.deepcopy(oldplan);plan.update(fields,accounting=ar,scientific_equivalence=eqref,audit_plan=auditref,expected_manifests={})
 # Empty expected_manifests is the helper-supported disabled preparation shape.
 m=b.engineering_manifest(plan,runtime,e.row(),audit=audit)
 mr=save('engineering-manifest.disabled-v1.json',m);plan.update(engineering_manifest=mr,expected_manifests={e.EPISODE_KEY:mr})
 assert plan['authority'] is None and plan['b5_review'] is None and not plan['release_enabled'] and not plan['frozen']
 pr=save('engineering-plan.draft-disabled-v1.json',plan)
 for k in ('native_build',):read(plan[k])
 for k in ('protocol','protocol_review','accounting'):read(audit[k])
 save('bindings.disabled-v1.json',{'schema':'n36-engineering-r1-prepared-bindings-v1','bindings':e.review_bindings(plan),'plan':pr,'source_preparation_location':str(ROOT),'deployment_location':plan['worktree'],'helper_generated_manifests':41,'final_production_acceptance':False,'source_location_adopted':False,'independent_final_b5':False,'controller_review':'PENDING_INDEPENDENT_AND_ROOT_REVIEW','gpu_authorized':False,'release_enabled':False})
 check('Exact reviewed variant source closure',lambda:b.closure.verify_source(ROOT,source))
 check('Exact reviewed variant loaded source bytes',lambda:b.attest_loaded(ROOT,source))
 check('Exact disabled runtime binding',lambda:e.validate_runtime_binding(plan))
 check('R1 disabled scope',lambda:e.validate_scope_reference(sr))
 check('R1 disabled accounting',lambda:e.validate_accounting_reference(ar))
 check('Preserved lexical deployment route',lambda:e.deployment(plan))
 check('Eventual deployment source closure',lambda:b.verify_sources(plan),blocked=True)
 check('Eventual deployment loaded source location',lambda:b.attest_loaded(plan['worktree'],source),blocked=True)
 check('R1 draft plan shape',lambda:e.validate_plan_shape(plan))
 check('Full40 disabled audit shape',lambda:e.validate_audit_view(audit))
 check('Exact R1 task0 C0 mapping',lambda:e.audit_mapping(plan,audit,e.row()))
 check('Scientific equivalence at pinned deployment',lambda:e.scientific_equivalence(plan),blocked=True)
 def variant_equivalence():
  assert subprocess.run(['git','merge-base','--is-ancestor',e.BASE,head],cwd=ROOT).returncode==0
  e.exact(eq,{'schema':'n36-engineering-scientific-equivalence-v1','base_commit':e.BASE,'source':source,'changed_paths':sorted(cmd(['git','diff','--name-only',e.BASE,head,'--'])),'scientific_changes':False},'variant equivalence')
 check('Scientific equivalence at exact reviewed variant',variant_equivalence)
 check('Terminal parent prefixes and retained accounting',e.terminal_parent_prefix)
 check('Runtime closure exact bytes and versions',lambda:b.closure.verify_runtime(closure,rtref))
 from scripts.qd_ed_n34_controller import verify_semantics
 check('Controller independent/root attestation gate',lambda:verify_semantics(proofref,rtref,closure),blocked=True)
 check('Full production CPU audit closure',lambda:e.full.verify_audit_closure(audit),blocked=True)
 for row in audit['episodes']:
  manifest_checks.append(check('Audit helper certificate '+row['episode_key'],lambda row=row:b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']],audit,runtime,row)))
 engcheck=check('Distinct R1 engineering helper certificate',lambda:b.verify_engineering_manifest(mr,plan,runtime,e.row(),audit=audit))
 from scripts.qd_ed_n36_build import manifest as native_manifest
 check('Reused native build exact bytes',lambda:native_manifest(plan['native_build']))
 def dino():
  from scripts.qd_ed_n36_dino import DinoSources
  d=DinoSources(rtref)
  for n,p in d.names.items():d.check_file(n,p)
 check('Prospective DINO source consumer',dino)
 def cache_coverage():
  fingerprints={str(pathlib.Path(x['path']).resolve()) for x in runtime['files']}
  for task in runtime['tasks'].values():
   actual={str(p.resolve()) for p in pathlib.Path(task['cache_dir']).rglob('*') if p.is_file()};w.require(actual and actual<=fingerprints,'task cache inventory incomplete')
 check('Exact runtime task cache coverage',cache_coverage)
 check('Frozen runtime task seed inventory validators',lambda:e.r.validate_runtime_inputs(audit,runtime,b.profiles(plan['worktree']),pathlib.Path(plan['worktree']),{'artifacts':runtime['artifact_root']}))
 def preservation():
  expected=copy.deepcopy(oldclosure);expected['runtime']=rtref;assert expected==closure
  for k in oldaudit:
   if k not in (*fields,'expected_manifests'):assert oldaudit[k]==audit[k],k
  for k in oldplan:
   if k not in (*fields,'accounting','scientific_equivalence','audit_plan','engineering_manifest','expected_manifests'):assert oldplan[k]==plan[k],k
  for key,r in a['ledger_prefixes'].items():verify(r)
  for p,r in list(inputs.items()):assert rec(p)==r,p
 check('Science identity accounting and immediate-input preservation',preservation)
 save('helper-certification-v1.json',{'audit_manifests':manifest_checks,'engineering_manifest':engcheck,'count':41,'all_helper_checks_pass':all(x['status']=='PASS' for x in manifest_checks+[engcheck]),'production_acceptance':False,'release_enabled':False})
 save('deployment-validation-v1.json',{'deployment':plan['deployment'],'reviewed_source':head,'reviewed_source_location':str(ROOT),'pinned_deployment_location':plan['worktree'],'deployment_head':cmd(['git','rev-parse','HEAD'],cwd=pathlib.Path(plan['worktree'])).strip(),'source_placement_performed':False,'owner_location_adoption_pending':True,'outcomes':[x for x in checks if 'deployment' in x['check'].lower() or 'loaded source' in x['check'].lower()],'release_enabled':False})
 save('binding-diff-v1.json',{'reused_exact_specification':e.SPECIFICATION,'reused_exact_source_inventory':runtime['preparation']['source_record'],'reused_exact_runtime':rtref,'runtime_rewritten':False,'scope_accounting_changes':['specification reference only'],'closure_changes':['runtime reference only'],'controller_changes':['runtime','runtime_closure','source_commit','reference_refresh_lineage','review_evidence references'],'audit_changed_fields':[k for k in audit if audit[k]!=oldaudit[k]],'plan_changed_fields':[k for k in plan if plan[k]!=oldplan[k]],'all40_rows_preserved':audit['episodes']==oldaudit['episodes'],'engineering_row_preserved':plan['episodes']==oldplan['episodes'],'deployment_document_reused':plan['deployment']==oldplan['deployment'],'readiness_policy_changed':False})
except Exception as ex:
 checks.append({'check':'preparation','status':'FAIL','exception':type(ex).__name__,'message':str(ex),'traceback':traceback.format_exc()});print(traceback.format_exc(),flush=True)
finally:
 save('generation-results-v1.json',{'schema':'n36-affected-disabled-binding-results-v1','started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-start,'inputs':list(inputs.values()),'outputs':outputs.copy(),'checks':checks,'commands':commands,'gpu_authorized':False,'release_enabled':False})
