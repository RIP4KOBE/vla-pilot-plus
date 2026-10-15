import ast, copy, datetime as dt, hashlib, json, math, os, resource, signal, subprocess, sys, time, types
from pathlib import Path
OUT=Path(__file__).absolute().parent
ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
SESSION=ROOT.parents[2]
OWNER=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree')
TURNS=OUT.parents[1]; HEAD='b8d6b98164f24a599a9aa1fa6ce862b12cb2fcf6'
START=time.monotonic(); CPU=time.process_time(); START_AT=dt.datetime.now(dt.timezone.utc)
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1')
sys.dont_write_bytecode=True
resource.setrlimit(resource.RLIMIT_CPU,(600,600));signal.alarm(600)
checks=[]; definitions=[]; inputs={}; outputs={}; mapping={}; matrix=[]; blockers=[]
def require(v,msg):
 if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p),bytes=Path(p).stat().st_size)
def pair(r):return {k:r[k] for k in ('path','sha256')}
def read(r):
 require(sha(r['path'])==r['sha256'],'hash mismatch '+r['path']);require('bytes' not in r or Path(r['path']).stat().st_size==r['bytes'],'size mismatch')
 inputs[r['path']]=ref(r['path']);return json.loads(Path(r['path']).read_text())
def ck(label,v,detail=None):
 checks.append(dict(check=label,pass_=bool(v),detail=detail));require(v,label+': '+str(detail))
def boundary():
 for p in [TURNS.parent/'STOP',SESSION/'autonomy_20261004/STOP']:
  try:p.lstat()
  except FileNotFoundError:pass
  else:raise ValueError('STOP present '+str(p))
 require(dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00'),'deadline');require(time.monotonic()-START<600,'CPU artifact executor time limit')
def fence(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('network prohibited')
 if event=='import' and args[0].split('.')[0] in {'torch','numpy','mujoco','robosuite','libero','transformers','diffusers','scipy','pandas'}:raise ImportError('native/model import prohibited')
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=Path(os.path.abspath(os.fsdecode(args[0])));s=str(p)
  require('2026-08-10-eds-qd-stage-guidance-transition-design.md' not in s and '/.codex/auth' not in s and 'credentials' not in s and '/formal/' not in s and '/validation/' not in s,'prohibited access')
  if args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):require(p.resolve().is_relative_to(OUT.resolve()),'outside output write')
 if event=='subprocess.Popen':require(Path(args[1][0]).name=='git','only passive git')
sys.addaudithook(fence)
def write(name,d):
 boundary();p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
 outputs[name]=ref(p);return pair(outputs[name])
def delta(a,b,p=''):
 if type(a)!=type(b):return [p]
 if isinstance(a,dict):return sum((delta(a[k],b[k],p+'/'+k) if k in a and k in b else [p+'/'+k] for k in sorted(set(a)|set(b))),[])
 if isinstance(a,list):return sum((delta(x,y,p+'/'+str(i)) for i,(x,y) in enumerate(zip(a,b))),[]) if len(a)==len(b) else [p]
 return [] if a==b else [p]
def rebind(d):
 if isinstance(d,dict):
  if d.get('path') in mapping and 'sha256' in d:
   r=mapping[d['path']];return {**d,'path':r['path'],'sha256':r['sha256'],**({'bytes':r['bytes']} if 'bytes' in d else {})}
  return {k:rebind(v) for k,v in d.items()}
 if isinstance(d,list):return [rebind(v) for v in d]
 return d
def changed(kind,oldref,name,new,allowed):
 old=read(oldref);diff=delta(old,new)
 ck('bounded delta '+kind,all(any(p==a or p.startswith(a+'/') for a in allowed) for p in diff),diff)
 nr=write(name,new);mapping[oldref['path']]=ref(nr['path']);matrix.append(dict(kind=kind,disposition='regenerated',old=ref(oldref['path']),new=ref(nr['path']),changed_fields=diff));return nr

def load_ast(file,names,env):
 tree=ast.parse((ROOT/file).read_text());selected=[]
 for n in tree.body:
  targets=[t.id for t in n.targets if isinstance(t,ast.Name)] if isinstance(n,ast.Assign) else []
  if (isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names) or set(targets)&set(names):selected.append(n)
 definitions.append(dict(file=file,sha256=sha(ROOT/file),names=names,rewritten=False))
 exec(compile(ast.Module(body=selected,type_ignores=[]),str(ROOT/file),'exec'),env);return env
boundary();ck('initial STOP/deadline',True,START_AT.isoformat())
a=read(ref(OUT/'authority-v1.json'));failure=read(a['failure_report']);prior=read(failure['preparation_report']);oldinputs=read(failure['b5_inputs'])
for k in ['standing_authority','root_reconciliation']:read(a[k])
ck('HEAD exact clean',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True))
oldplan=read(prior['roots']['plan']);oldaudit=read(prior['roots']['audit']);oldgraph=read(prior['roots']['graph'])
oldrt=read(oldplan['runtime']);oldcl=read(oldplan['runtime_closure']);oldctrl=read(oldplan['controller_semantics'])
runtime=copy.deepcopy(oldrt);closure=copy.deepcopy(oldcl);fixes=[]
for b in failure['blockers']:
 for e in b['evidence']:
  p=Path(e['path']);ck('committed bytes '+p.name,subprocess.check_output(['git','show',HEAD+':'+str(p.relative_to(ROOT))])==p.read_bytes())
  parts=e['json_pointer'].split('/')[1:];obj=runtime if parts[0]=='files' else closure
  record=obj[parts[0]][int(parts[1]) if parts[0]=='files' else parts[1]]
  ck('exact B5 stale target '+e['json_pointer'],record['sha256']==e['recorded_sha256'] and record['path']==e['path'])
  record['sha256']=sha(p)
  if parts[0]=='files':record['size_bytes']=p.stat().st_size
  fixes.append(dict(kind='runtime' if parts[0]=='files' else 'runtime_closure',json_pointer=e['json_pointer'],old_sha256=e['recorded_sha256'],actual=ref(p),closure_size_storage='Separate size-bound repair evidence; _runtime_file requires exactly path and sha256.'))
rtref=changed('runtime',oldplan['runtime'],'runtime.disabled-v1.json',runtime,['/files/3294/sha256','/files/3294/size_bytes','/files/3296/sha256','/files/3296/size_bytes','/files/3298/sha256','/files/3298/size_bytes'])
closure=rebind(closure)
clref=changed('runtime_closure',oldplan['runtime_closure'],'runtime-closure.disabled-v1.json',closure,['/runtime']+['/modules/scripts.qd_ed_n36_'+n+'/sha256' for n in ['healthcheck','runner','worker']])
write('six-fingerprint-repairs-v1.json',{'repairs':fixes,'external_dependency_evidence_preserved':True,'release_enabled':False,'b5_review':None})
# Prior root review is historical only; no replacement root attestation is fabricated.
def proposal(old,oldref):
 d=rebind(old);d['status']='PROPOSED_REFERENCE_REFRESH_REQUIRES_ROOT_ATTESTATION'
 d['reference_refresh_lineage']={'prior_evidence':ref(oldref['path']),'preparation_authority':ref(OUT/'authority-v1.json'),'prior_status':old.get('status'),'semantic_findings_unchanged':True,'new_root_approval':False,'independent_certification':False,'source_commit_is_historical':True}
 d['release_enabled']=False;d['b5_review']=None
 return d
for name,r in oldctrl['review_evidence'].items():
 old=read(r);new=proposal(old,r)
 for source in old['sources']:ck('reviewed source bytes '+source['path'],sha(source['path'])==source['sha256'])
 changed('controller_evidence:'+name,r,'controller-evidence/'+name+'.proposed-v1.json',new,['/runtime','/runtime_closure','/status','/reference_refresh_lineage','/b5_review'])
ctrl=proposal(oldctrl,oldplan['controller_semantics'])
ctrlref=changed('controller_semantics',oldplan['controller_semantics'],'controller-semantics.proposed-v1.json',ctrl,['/runtime','/runtime_closure','/review_evidence','/status','/reference_refresh_lineage','/b5_review'])
for row in oldaudit['episodes']:
 key=row['episode_key'];r=oldaudit['expected_manifests'][key];old=read(r);new=rebind(old)
 changed('audit_manifest:'+key,r,'audit-manifests/'+key+'.json',new,['/runtime','/runtime_closure','/controller_semantics'])
audit=rebind(oldaudit);auditref=changed('audit_view',prior['roots']['audit'],'audit-view.disabled-v1.json',audit,['/runtime','/runtime_closure','/controller_semantics','/expected_manifests'])
oldem=read(prior['roots']['engineering_manifest']);em=rebind(oldem)
emref=changed('engineering_manifest',prior['roots']['engineering_manifest'],'engineering-manifest.disabled-v1.json',em,['/runtime','/runtime_closure','/controller_semantics','/audit_plan','/audit_manifest'])
plan=rebind(oldplan);planref=changed('disabled_plan',prior['roots']['plan'],'engineering-plan.disabled-v1.json',plan,['/runtime','/runtime_closure','/controller_semantics','/audit_plan','/engineering_manifest','/expected_manifests'])
# Exact passive definitions reused from prior B5 helper setup, without executing its review workflow.
helper=TURNS/'001582/independent-b5/passive-review-v2.py';helpertext=helper.read_text();inputs[str(helper)]=ref(helper)
setup=helpertext[helpertext.index('stopns='):helpertext.index('for name,args in')]
exec(compile(setup,str(helper)+'::passive_setup','exec'),globals())
for name,args in [('validate_plan_shape',(plan,)),('validate_audit_view',(audit,)),('audit_mapping',(plan,audit,plan['episodes'][0])),('scientific_equivalence',(plan,))]:ens[name](*args);ck('unmodified passive '+name,True)
verify=load_ast('scripts/qd_ed_final_runner.py',['verify_files'],{'Path':Path,'os':os,'require':require,'digest':sha})['verify_files']
rfile=load_ast('scripts/qd_ed_n34_source.py',['_runtime_file'],{'Path':Path,'w':w})['_runtime_file']
focused=[]
for f in fixes:
 parts=f['json_pointer'].split('/')[1:];new=(runtime if f['kind']=='runtime' else closure)[parts[0]][int(parts[1]) if f['kind']=='runtime' else parts[1]]
 old=(oldrt if f['kind']=='runtime' else oldcl)[parts[0]][int(parts[1]) if f['kind']=='runtime' else parts[1]]
 def check_record(r):
  if f['kind']=='runtime':verify([r],allowed_roots=(str(ROOT),))
  else:rfile(r)
 try:check_record(old)
 except ValueError as ex:old_rejection=str(ex)
 else:raise ValueError('prior mismatch no longer reproduced')
 check_record(new);focused.append({**f,'old_rejection':old_rejection,'new_rejection':None,'resolved':True,'exact_unmodified_AST':True})
ck('six old rejects and six repaired passes',len(focused)==6)
write('focused-runtime-checks-v1.json',{'results':focused,'six_prior_mismatches_resolved':True,'native_model_provider_execution':False,'full_runtime_verifier_executed':False})
ctrlcheck=load_ast('scripts/qd_ed_n34_controller.py',['FIELDS','verify_semantics'],{'w':w,'math':math})['verify_semantics']
ctrlcheck(oldplan['controller_semantics'],oldplan['runtime'],oldcl)
try:ctrlcheck(ctrlref,rtref,closure)
except ValueError as ex:
 ck('expected controller root attestation gate',str(ex)=='reviewed controller semantics required')
 blockers.append({'id':'CONTROLLER_ROOT_ATTESTATION_REQUIRED','consumer':'scripts/qd_ed_n34_controller.py:verify_semantics, called by scripts/qd_ed_n36_release.py:183','predicate':"proof['status'] == 'ROOT_REVIEWED'",'rejection':str(ex),'proposed_artifact':ref(ctrlref['path']),'required_action':'Root must attest the changed runtime/closure bindings and issue controller semantics/review-evidence versions. Exact prior semantic findings are retained; this executor does not issue that approval.'})
else:raise ValueError('proposal unexpectedly accepted')
# Focused affected consumer data checks; command/config composition inputs are unchanged.
for r in audit['episodes']:
 m=read(audit['expected_manifests'][r['episode_key']]);old=read(oldaudit['expected_manifests'][r['episode_key']])
 ck('manifest row and frozen payload '+r['episode_key'],m['row']==r and all(m[k]==old[k] for k in ['argv','resolved_config','composed_config_sha256','expected_runtime','source','scientific_source']))
 for k in ['runtime','runtime_closure','controller_semantics','accounting','scope','deployment','protocol','protocol_review']:ck('manifest consumer binding '+r['episode_key']+' '+k,m[k]==audit[k])
ck('engineering frozen payload',all(em[k]==oldem[k] for k in ['argv','resolved_config','composed_config_sha256','expected_runtime','row','audit_row','source','scientific_source']))
ck('engineering audit binding',em['audit_plan']==plan['audit_plan'] and em['audit_manifest']==audit['expected_manifests'][audit['episodes'][0]['episode_key']])
ck('all40 scientific cells/gates/cost references unchanged',len(audit['episodes'])==40 and all(audit[k]==oldaudit[k] for k in ['episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting']))
for k in ['source_inventory','scientific_source_inventory','scientific_equivalence']:
 r=prior['roots'][k];read(r);matrix.append(dict(kind=k,disposition='reused_byte_identical',reference=r,rationale='Immutable source and science; this refresh changes only runtime source fingerprints and affected artifact references.'))
for k in ['native_build','scope','accounting','deployment']:
 r=plan[k];read(r);matrix.append(dict(kind=k,disposition='reused_byte_identical',reference=ref(r['path']),rationale='Unchanged direct evidence; no execution, adoption, ledger mutation or external dependency rebuild.'))
for k in ['protocol','protocol_review']:
 r=audit[k];read(r);matrix.append(dict(kind=k,disposition='reused_byte_identical',reference=ref(r['path']),rationale='Frozen scientific protocol retained.'))
account=read(plan['accounting'])
for name,r in account['retained_ledger_prefixes'].items():
 with open(r['path'],'rb') as f:data=f.read(r['bytes'])
 ck('retained ledger prefix '+name,len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256'])
ck('no output execution',not os.path.lexists(plan['artifact_root']))
ck('runtime unready',runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False and runtime['preparation']['runtime_ready'] is False)
for r in [failure['preparation_report'],failure['b5_inputs'],a['failure_report']]:ck('prior evidence preserved '+r['path'],ref(r['path'])==r)
# Active reference scan excludes explicit historical lineage; no historical provenance recursion.
edges=[]
def scan(d,p):
 if isinstance(d,dict):
  if isinstance(d.get('path'),str) and isinstance(d.get('sha256'),str):
   ck('active reference '+p,sha(d['path'])==d['sha256']);ck('no stale active ref '+p,d['path'] not in mapping);edges.append(dict(location=p,reference=ref(d['path'])));return
  for k,v in d.items():
   if k not in ['source','scientific_source','reference_refresh_lineage','inherited_review','root_review_evidence','prior_evidence','rebound_from']:scan(v,p+'/'+k)
 elif isinstance(d,list):
  for i,v in enumerate(d):scan(v,p+'/'+str(i))
for label,obj in [('plan',plan),('audit',audit),('engineering_manifest',em),('controller_semantics',ctrl)]+[(r['episode_key'],read(audit['expected_manifests'][r['episode_key']])) for r in audit['episodes']]:scan(obj,label)
edgeref=write('graph-edges-v1.json',{'edges':edges,'scope':'Active affected document references only; historical provenance remains immutable anchors.','release_enabled':False,'b5_review':None})
mref=write('changed-reused-evidence-matrix-v1.json',{'source':HEAD,'entries':matrix,'prior_B5_transfers':False,'all40_recomposed':False,'all40_config_argv_and_algorithm_bytes_preserved':True,'blockers':blockers,'release_enabled':False,'b5_review':None})
graph=rebind(oldgraph);graph['evidence_matrix']=mref;graph['prior_graph']=pair(prior['roots']['graph']);graph['graph_edges']=edgeref;graph['blockers']=blockers;graph['status']='DISABLED_PROPOSED_GRAPH_PENDING_ROOT_ATTESTATION_AND_B5'
graphref=changed('graph_root',prior['roots']['graph'],'graph-root.disabled-v1.json',graph,['/plan','/audit','/engineering_manifest','/audit_manifests','/retained_bindings','/evidence_matrix','/prior_graph','/graph_edges','/blockers','/status'])
roots={k:ref(rebind(v)['path']) for k,v in prior['roots'].items()};roots.update(runtime=ref(rtref['path']),runtime_closure=ref(clref['path']),controller_semantics=ref(ctrlref['path']),evidence_matrix=ref(mref['path']),graph=ref(graphref['path']))
rootref=write('refreshed-root-references-v1.json',dict(roots=roots,release_enabled=False,b5_review=None,authority=None,source_adopted=False,accounting_adopted=False))
# Graph-root delta is bound separately to avoid a matrix/graph hash cycle.
write('graph-root-delta-v1.json',matrix[-1])
stop.check(need=1);boundary();ck('final STOP/deadline',True,dt.datetime.now(dt.timezone.utc).isoformat())
ck('final HEAD exact clean',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True))
for r in list(inputs.values()):ck('input retained '+r['path'],ref(r['path'])==r)
checkref=write('passive-consumer-checks-v1.json',{'checks':checks,'definitions':definitions,'acceptance_predicates_modified':False,'expected_gate_rejections':blockers,'independent_B5_performed':False,'verification_scope':'Unmodified AST passive runtime predicates and plan/audit/mapping/scientific-equivalence/controller consumers; static crossbindings and exact payload preservation across all41 manifests. No Hydra recomposition, full runtime/release verification or native/model/provider work.','CUDA_VISIBLE_DEVICES':''})
status='GRAPH_REPAIRED_DISABLED_PROPOSALS_PENDING_ROOT_ATTESTATION_AND_INDEPENDENT_B5'
remaining=['Root attestation of proposed controller evidence for changed runtime/closure refs; exact consumer predicate recorded in blockers.','Subsequent independent B5 by coordinator; no prior PASS transfers.','Separate root protocol acceptance, source/accounting adoption, actual readiness and detached prospective releases remain absent.']
report={'schema':'n36-runtime-graph-refresh-report-v1','node_id':'15.6','source':HEAD,'status':status,'roots':roots,'canonical_root_references':ref(rootref['path']),'preparation_authority':ref(OUT/'authority-v1.json'),'prior_preparation_report':failure['preparation_report'],'prior_B5_FAIL':a['failure_report'],'retained_failed_preparation_attempt':prior['retained_failed_preparation_attempt'],'six_prior_mismatches_resolved':True,'graph_reference_refresh_complete':True,'graph_refresh_complete':False,'preparation_consumer_ready':False,'blockers':blockers,'remaining_obligations':remaining,'checks':ref(checkref['path']),'evidence_matrix':ref(mref['path']),'graph_root_delta':outputs['graph-root-delta-v1.json'],'inputs':list(inputs.values()),'outputs':dict(outputs),'retained_accounting':failure['retained_accounting'],'release_enabled':False,'b5_review':None,'authority':None,'authority_granted':False,'independent_B5_performed':False,'source_adopted':False,'accounting_adopted':False,'source_edited':False,'owner_state_tree_ledger_written':False,'native_model_provider_execution':False,'gpu_dispatch':False,'CUDA_VISIBLE_DEVICES':'','credentials_accessed':False,'protected_results_accessed':False,'delegation':False,'scientific_success':False,'target_met':False,'score':None,'tests_rerun':0,'model_policy':'Existing official current-login gpt-6-astra session only; no alternate provider, account or API invoked.','budget':{'started_at':START_AT.isoformat(),'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-START,'cpu_seconds':time.process_time()-CPU,'timeout_seconds':1200,'deadline':a['deadline']},'size_schema_note':'Runtime file sizes updated. Closure module records must remain exactly path/sha256 under unmodified _runtime_file; actual sizes are hash-bound in six-fingerprint-repairs-v1.json and focused-runtime-checks-v1.json.'}
rr=write('report-v1.json',report)
b5={**{k:oldinputs[k] for k in ['accepted_source_review','independent_source_review','prior_source','retained_failed_preparation_attempt']},'schema':'n36-runtime-refresh-independent-b5-inputs-v1','source':HEAD,'status':status,'roots':roots,'preparation_report':ref(rr['path']),'preparation_outputs':dict(outputs),'authority_record':ref(OUT/'authority-v1.json'),'prior_preparation_report':failure['preparation_report'],'prior_B5_FAIL':a['failure_report'],'blockers':blockers,'remaining_obligations':remaining,'release_enabled':False,'b5_review':None,'authority':None,'source_adopted':False,'accounting_adopted':False,'independent_B5_performed':False,'prior_B5_approves_current_source':False}
br=write('independent-b5-inputs-v1.json',b5)
with (OUT/'report-v1.sha256').open('x') as f:f.write(rr['sha256']+'  report-v1.json\n')
write('artifact-hash-seal-v1.json',{'report':ref(rr['path']),'independent_b5_inputs':ref(br['path']),'roots':roots,'release_enabled':False,'b5_review':None})
print(json.dumps({'status':status,'report':ref(rr['path']),'checks':len(checks),'resolved_mismatches':len(focused),'blockers':blockers},indent=2))
