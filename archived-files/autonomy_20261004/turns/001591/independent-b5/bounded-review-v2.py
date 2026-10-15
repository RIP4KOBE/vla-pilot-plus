import ast, json, hashlib, pathlib, types, math, os, subprocess, datetime as dt, copy
from decimal import Decimal
Path=pathlib.Path
OUT=Path(__file__).parent
BASE=OUT.parents[1]/'001588/attested-consumer-refresh'
IP=BASE/'independent-b5-inputs-v1.json'
I=json.loads(IP.read_text()); ROOT=Path.cwd(); results=[]; definitions=[]; verified={}
def ck(name,condition,detail=None):
 results.append({'check':name,'verdict':'PASS' if condition else 'FAIL','evidence':detail})
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(ref):
 p=Path(ref['path']);data=p.read_bytes();actual=hashlib.sha256(data).hexdigest()
 assert actual==ref['sha256'],str(p)+' hash mismatch'
 assert 'bytes' not in ref or ref['bytes']==len(data),str(p)+' size mismatch'
 verified[str(p)]={'path':str(p),'sha256':actual,'bytes':len(data)}
 return json.loads(data)
def refs(v):
 if isinstance(v,dict):
  if 'path'in v and 'sha256'in v:yield v
  for x in v.values():yield from refs(x)
 elif isinstance(v,list):
  for x in v:yield from refs(x)
def load(file,names,env):
 tree=ast.parse((ROOT/file).read_text());nodes=[]
 for n in tree.body:
  ids={n.name} if isinstance(n,(ast.FunctionDef,ast.ClassDef)) else {t.id for t in n.targets if isinstance(t,ast.Name)} if isinstance(n,ast.Assign) else set()
  if ids & set(names):nodes.append(n)
 assert len(nodes)==len(names),(file,names,len(nodes))
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/file),'exec'),env)
 definitions.append({'path':str(ROOT/file),'sha256':sha(ROOT/file),'names':names,'AST_unmodified':True})
 return types.SimpleNamespace(**{n:env[n] for n in names})
ck('exact input',sha(IP)=='1f6046e98d358a637877afd6bc9ccacd10e788cebd7a7df2d3888f54395bdfd0')
for r in refs(I):read(r)
ck('direct sealed input bindings',True,{'unique_artifacts':len(verified)})
ck('exact source HEAD',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==I['source'],I['source'])
status=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True)
ck('tracked source clean',not status,status)
p=read(I['roots']['plan']);a=read(I['roots']['audit']);g=read(I['roots']['graph']);rt=read(I['roots']['runtime']);cl=read(I['roots']['runtime_closure']);ctrl=read(I['roots']['controller_semantics']);em=read(I['roots']['engineering_manifest']);matrix=read(I['roots']['evidence_matrix']);att=read(I['root_attestation']);prior=read(I['prior_B5_FAIL'])
wenv={'Path':Path,'hashlib':hashlib,'json':json};w=load('scripts/qd_ed_n23_worker.py',['require','sha','canonical_sha','read_ref'],wenv)
# Only passive exact production definitions; no application module imports.
senv={'dt':dt,'os':os};stop=load('scripts/qd_ed_n36_stop.py',['OWNER_STOP','DATA_STOP','STOP_PATHS','DEADLINE','binding','check'],senv)
stop.check();ck('STOP and deadline passive check',True,{'paths':list(stop.STOP_PATHS),'deadline':stop.DEADLINE})
cenv={'Path':Path,'w':w,'stop':stop,'ROOT':ROOT};cnames=['COHORT','RECOVERY_COHORT','DRAFT_RECOVERY_COHORT','DRAFT_N36R3_COHORT','DRAFT_N36R4_COHORT','SEPARATE_HEALTH_COHORTS','IDENTITIES','ARMS','DEADLINE','GPU_UUID','PROTOCOL_REVIEW_SHA','LIMITS','WORKER_CONTRACT','expected_rows','stop_path','validate_stop_binding'];c=load('scripts/qd_ed_n36_contract.py',cnames,cenv)
SESSION=ROOT.parents[2];OWNER=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree')
eenv={'Path':Path,'w':w,'c':c,'stop':stop,'SESSION':SESSION,'OWNER':OWNER,'json':json,'subprocess':subprocess}
enames=['BASE','SOURCE','PREPARATION','SPECIFICATION','IDENTITY','EPISODE_KEY','HEALTH_ID','HEALTH_KIND','PURPOSE','PLAN_SCHEMA','AUDIT_SCHEMA','LIMITS','BINDINGS','RUNTIME_INPUTS','OPERATIONAL_FILES','exact','reference','read','specification','row','disabled_scope','disabled_accounting','validate_disabled_scope','validate_disabled_accounting','validate_scope_reference','validate_accounting_reference','require_row','deployment','owner_root','validate_audit_view','audit_mapping','validate_plan_shape','scientific_equivalence','review_bindings']
e=load('scripts/qd_ed_n36_engineering.py',enames,eenv)
for name,fn in [('disabled plan shape',lambda:e.validate_plan_shape(p)),('all40 audit shape',lambda:e.validate_audit_view(a)),('engineering audit mapping',lambda:e.audit_mapping(p,a,p['episodes'][0])),('scientific equivalence exact production predicate',lambda:e.scientific_equivalence(p))]:
 try:fn();ck(name,True)
 except Exception as ex:ck(name,False,str(ex))
ce={'w':w,'math':math};co=load('scripts/qd_ed_n34_controller.py',['FIELDS','verify_semantics'],ce)
try:co.verify_semantics(p['controller_semantics'],p['runtime'],cl);ck('controller semantics production consumer',True)
except Exception as ex:ck('controller semantics production consumer',False,str(ex))
ck('root attestation binds current controller/runtime/closure',all(att[k]['sha256']==I['roots'][k]['sha256'] for k in ['controller_semantics','runtime','runtime_closure']))
ck('controller closure reference coherent',ctrl['runtime_closure']==p['runtime_closure'] and cl['runtime']==p['runtime'])
for name,ref in {'controller_semantics':p['controller_semantics'],**ctrl['review_evidence']}.items():
 current=read(ref);line=current['root_binding_attestation'];old=read(line['prior_review']);proposal=read(line['proposal'])
 excluded={'runtime','runtime_closure','review_evidence','reference_refresh_lineage','status','root_binding_attestation','at'}
 ck('controller unchanged semantic payload '+name,{k:v for k,v in current.items() if k not in excluded}=={k:v for k,v in old.items() if k not in excluded})
 ck('controller current references '+name,current['runtime']==p['runtime'] and current['runtime_closure']==p['runtime_closure'] and current['status']=='ROOT_REVIEWED')
 for r in refs(current.get('source',{})):
  ck('controller implementation bytes '+name,sha(r['path'])==r['sha256'],r)
# Exact changed/reused matrix without traversing historical provenance.
def diff(x,y,pointer=''):
 if type(x)!=type(y):return [pointer]
 if isinstance(x,dict):return [pointer+'/'+k for k in sorted(x.keys()^y.keys())]+sum((diff(x[k],y[k],pointer+'/'+k) for k in sorted(x.keys()&y.keys())),[])
 if isinstance(x,list):
  if len(x)!=len(y):return [pointer]
  return sum((diff(v,y[j],pointer+'/'+str(j)) for j,v in enumerate(x)),[])
 return [] if x==y else [pointer]
for entry in matrix['entries']:
 if entry['disposition']=='regenerated':
  old=read(entry['old']);new=read(entry['new']);delta=diff(old,new)
  ck('matrix exact delta '+entry['kind'],sorted(delta)==sorted(entry['changed_fields']),delta)
 elif 'reference'in entry:read(entry['reference'])
# Every audit row stays bound to exact source and current consumers; scientific fields equal prior B5 roots.
old_a=read(prior['roots']['audit'])
science=['cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting']
ck('frozen all40 scientific plan content',all(a[k]==old_a[k] for k in science),science)
for row in a['episodes']:
 key=row['episode_key'];m=read(a['expected_manifests'][key]);old=read(old_a['expected_manifests'][key])
 fields=['argv','resolved_config','composed_config_sha256','expected_runtime','row']
 ck('all40 scientific manifest '+key,all(m[k]==old[k] for k in fields),fields)
 ck('all40 root binding '+key,all(m[k]==a[k] for k in ['source','scientific_source','runtime','runtime_closure','controller_semantics','native_build']) and m['row']==row and g['audit_manifests'][key]==a['expected_manifests'][key])
ck('graph current root references',all(g[k]['sha256']==I['roots'][v]['sha256'] for k,v in [('audit','audit'),('plan','plan'),('engineering_manifest','engineering_manifest'),('evidence_matrix','evidence_matrix')]))
ck('engineering manifest bindings',all(em[k]==p[k] for k in ['source','scientific_source','runtime','runtime_closure','controller_semantics','native_build','scope','accounting','deployment','audit_plan']) and em['audit_manifest']==a['expected_manifests'][em['audit_row']['episode_key']])
inv=read(I['roots']['source_inventory']);ck('inventory same exact source',p['source']==p['scientific_source']==inv and inv['commit']==I['source'])
renv={'Path':Path,'os':os,'require':w.require,'digest':sha};rf=load('scripts/qd_ed_final_runner.py',['verify_files'],renv)
rtproject=[r for r in rt['files'] if Path(r['path']).is_relative_to(ROOT)]
try:rf.verify_files(rtproject,allowed_roots=(ROOT,));ck('runtime project fingerprints production predicate',True,{'count':len(rtproject)})
except Exception as ex:ck('runtime project fingerprints production predicate',False,str(ex))
se={'Path':Path,'w':w};sf=load('scripts/qd_ed_n34_source.py',['_runtime_file'],se)
mods={k:r for k,r in cl['modules'].items() if Path(r['path']).is_relative_to(ROOT)}
for k,r in mods.items():
 try:sf._runtime_file(r)
 except Exception as ex:ck('closure file '+k,False,str(ex))
ck('closure project fingerprints checked',True,{'count':len(mods)})
source={r['path']:r['sha256'] for r in inv['files']}
ck('runtime source inventory coherence',all(source.get(str(Path(r['path']).relative_to(ROOT)))==r['sha256'] for r in rtproject))
ck('closure source inventory coherence',all(source.get(str(Path(r['path']).relative_to(ROOT)))==r['sha256'] for r in mods.values()))
acct=read(p['accounting']);spec=read(acct['specification'])
ck('accounting frozen to specification',acct['accounting']==spec['accounting_proposal'] and acct['retained_ledger_prefixes']==spec['retained_ledger_prefixes'])
for name,r in acct['retained_ledger_prefixes'].items():
 with open(r['path'],'rb') as stream:data=stream.read(r['bytes'])
 ck('unchanged opaque ledger prefix '+name,len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256'],r)
acc=acct['accounting'];ck('retained reserves and margin',acc['retained_attempts']==506 and acc['retained_gpu_hours']=='75.60616276674473' and acc['retained_admission_margin_gpu_hours']=='0.23357169027962' and acc['protected_remaining_gpu_hours']=={'formal':'12.0','validation':'24.2408240024308155'})
ck('finite prospective limits',p['limits']==e.LIMITS and acc['gpu_reservation_seconds']==1900 and acc['wall_seconds']==2100 and acc['new_attempts_max']==1 and acc['automatic_recoveries']==0,p['limits'])
ck('disabled readiness and authority',not rt['cuda_egl_verified'] and not rt['provider_ready'] and not p['release_enabled'] and p['authority'] is None and p['b5_review'] is None and not g['source_adopted'] and not g['accounting_adopted'])
# Mutation checks are in-memory only, exercising unchanged controller rejection gates.
original_read=w.read_ref
for label,mutate in [('status',lambda x:x.update(status='PROPOSED')),('runtime',lambda x:x['runtime'].update(sha256='0'*64)),('rotation',lambda x:x['semantics'].update(rotation='absolute_pose')),('coverage',lambda x:x['review_evidence'].pop('set_goal'))]:
 bad=copy.deepcopy(ctrl);mutate(bad);w.read_ref=lambda ref:bad if ref==p['controller_semantics'] else original_read(ref)
 rejected=False
 try:co.verify_semantics(p['controller_semantics'],p['runtime'],cl)
 except (ValueError,KeyError):rejected=True
 ck('controller negative rejection '+label,rejected)
w.read_ref=original_read
ck('prior FAIL retained',prior['decision']=='FAIL' and sha(I['prior_B5_FAIL']['path'])==I['prior_B5_FAIL']['sha256'])
record={'schema':'n36-independent-b5-bounded-checks-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'checks':results,'production_definitions':definitions,'verified_artifacts':list(verified.values()),'tracked_status':status,'imports':'stdlib only; exact selected AST definitions; no application/native/provider imports','ledger_access':'opaque bounded prefix bytes only; no result parsing','writes_only':str(OUT)}
(OUT/'bounded-checks-v1.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print(json.dumps({'checks':len(results),'failures':[x for x in results if x['verdict']=='FAIL'],'verified_artifacts':len(verified),'runtime_project_records':len(rtproject),'closure_project_records':len(mods)},indent=2))
