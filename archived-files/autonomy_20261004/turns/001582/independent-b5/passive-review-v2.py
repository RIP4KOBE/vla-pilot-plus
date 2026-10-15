import ast,datetime as dt,hashlib,json,math,os,subprocess,types
from pathlib import Path
OUT=Path(__file__).parent
ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
SESSION=ROOT.parents[2]
OWNER=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree')
P=OUT.parents[1]/'001579/g7-affected-graph-refresh'
checks=[]; hashes={}; definitions=[]
def ck(label,condition,detail=None):
 checks.append({'check':label,'pass':bool(condition),'detail':detail})
 if not condition: print('FAIL',label,detail)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def require(c,r):
 if not c:raise ValueError(r)
def ref(p):return {'path':str(p),'sha256':sha(p)}
def read(r):
 p=Path(r['path']);require('2026-08-10-eds-qd-stage-guidance-transition-design.md' not in str(p),'prohibited')
 actual=sha(p);ck('reference:'+str(p),actual==r['sha256'] and ('bytes' not in r or p.stat().st_size==r['bytes']))
 hashes[str(p)]=actual
 return json.loads(p.read_text())
def refs(d):
 if isinstance(d,dict):
  if isinstance(d.get('path'),str) and isinstance(d.get('sha256'),str):yield d
  else:
   for v in d.values():yield from refs(v)
 elif isinstance(d,list):
  for v in d:yield from refs(v)
def load_ast(file,names,env):
 tree=ast.parse((ROOT/file).read_text());selected=[]
 for n in tree.body:
  targets=[t.id for t in n.targets if isinstance(t,ast.Name)] if isinstance(n,ast.Assign) else []
  if (isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names) or set(targets)&set(names):selected.append(n)
 definitions.append({'file':file,'sha256':sha(ROOT/file),'names':names,'rewritten':False})
 exec(compile(ast.Module(body=selected,type_ignores=[]),str(ROOT/file),'exec'),env)
 return env
def git(*args):return subprocess.check_output(['git','--no-replace-objects','-C',str(ROOT),*args],env={**os.environ,'GIT_NO_LAZY_FETCH':'1'},text=True).strip()
authority=json.loads((OUT/'authority-v1.json').read_text());inputs=read(authority['b5_inputs']);report=read(authority['preparation_report'])
for k in ['standing_authority','terminal_reconciliation']:read(authority[k])
plan=read(report['roots']['plan']);audit=read(report['roots']['audit']);graph=read(report['roots']['graph']);manifest=read(report['roots']['engineering_manifest']);inventory=read(report['roots']['source_inventory']);matrix=read(report['roots']['evidence_matrix'])
for x in inputs['preparation_outputs'].values():read(x)
for x in report['retained_failed_preparation_attempt'].values():
 if isinstance(x,dict) and 'path' in x:read(x)
accepted=read(inputs['accepted_source_review']);ck('accepted source review',accepted['source']==authority['source'] and accepted['status']=='PASS_BOUNDED_SOURCE_REVIEW')
ck('HEAD exact',git('rev-parse','HEAD')==authority['source']);ck('tracked clean',not git('status','--porcelain','--untracked-files=no'))
stopns=load_ast('scripts/qd_ed_n36_stop.py',['OWNER_STOP','DATA_STOP','STOP_PATHS','DEADLINE','binding','check'],{'dt':dt,'os':os});stop=types.SimpleNamespace(**stopns);stop.check(need=1)
w=types.SimpleNamespace(require=require,sha=sha,canonical_sha=canonical,read_ref=read)
cnames=['COHORT','RECOVERY_COHORT','DRAFT_RECOVERY_COHORT','DRAFT_N36R3_COHORT','DRAFT_N36R4_COHORT','SEPARATE_HEALTH_COHORTS','IDENTITIES','ARMS','DEADLINE','GPU_UUID','PROTOCOL_REVIEW_SHA','LIMITS','WORKER_CONTRACT','expected_rows','stop_path','validate_stop_binding']
cns=load_ast('scripts/qd_ed_n36_contract.py',cnames,{'Path':Path,'ROOT':ROOT,'json':json,'w':w,'stop':stop});c=types.SimpleNamespace(**cns)
enames=['BASE','SOURCE','PREPARATION','SPECIFICATION','IDENTITY','EPISODE_KEY','HEALTH_ID','HEALTH_KIND','PURPOSE','PLAN_SCHEMA','AUDIT_SCHEMA','LIMITS','BINDINGS','RUNTIME_INPUTS','OPERATIONAL_FILES','exact','reference','read','specification','row','disabled_scope','disabled_accounting','validate_disabled_scope','validate_disabled_accounting','validate_scope_reference','validate_accounting_reference','require_row','deployment','owner_root','validate_audit_view','audit_mapping','validate_plan_shape','scientific_equivalence','review_bindings']
ens=load_ast('scripts/qd_ed_n36_engineering.py',enames,{'Path':Path,'SESSION':SESSION,'OWNER':OWNER,'w':w,'c':c,'stop':stop,'subprocess':subprocess})
for name,args in [('validate_plan_shape',(plan,)),('validate_audit_view',(audit,)),('audit_mapping',(plan,audit,plan['episodes'][0])),('scientific_equivalence',(plan,))]:
 try:ens[name](*args);ck('exact passive '+name,True)
 except Exception as ex:ck('exact passive '+name,False,str(ex))
ck('all root bindings agree',all(inputs['roots'][k]==v for k,v in report['roots'].items()))
for k in ['plan','audit','engineering_manifest','scientific_equivalence','source_inventory','scientific_source_inventory','evidence_matrix']:
 ck('graph root '+k,graph[k]=={x:report['roots'][k][x] for x in ('path','sha256')})
ck('graph all40 map',graph['audit_manifests']==audit['expected_manifests'] and len(graph['audit_manifests'])==40)
ck('disabled graph',graph['release_enabled'] is False and graph['authority'] is None and graph['b5_review'] is None and graph['source_adopted'] is False and graph['accounting_adopted'] is False)
ck('disabled plan',plan['authority'] is None and plan['b5_review'] is None and plan['release_enabled'] is False)
ck('source inventory digest',inventory['sha256']==canonical(inventory['files']))
for label,d in [('plan',plan),('audit',audit),('engineering_manifest',manifest)]:ck(label+' exact inventories',d['source']==d['scientific_source']==inventory)
for entry in inventory['files']:
 path=ROOT/entry['path'];require('2026-08-10-eds-qd-stage-guidance-transition-design.md' not in str(path),'prohibited');ck('source bytes '+entry['path'],sha(path)==entry['sha256'])
changed=git('diff','--name-only',inputs['prior_source'],authority['source'],'--').splitlines();ck('intervening operational paths',set(changed)<=ens['OPERATIONAL_FILES'],changed)
for f in changed:ck('changed committed bytes '+f,subprocess.check_output(['git','-C',str(ROOT),'show',authority['source']+':'+f])==(ROOT/f).read_bytes())
# No historical evidence recursion: compare direct affected objects and exact delta paths.
def differences(a,b,path=''):
 if type(a)!=type(b):return [path]
 if isinstance(a,dict):return sum((differences(a[k],b[k],path+'/'+k) if k in a and k in b else [path+'/'+k] for k in sorted(set(a)|set(b))),[])
 if isinstance(a,list):return sum((differences(x,y,path+'/'+str(i)) for i,(x,y) in enumerate(zip(a,b))),[]) if len(a)==len(b) else [path]
 return [] if a==b else [path]
old_new={};delta_details=[]
for entry in matrix['entries']:
 if entry['disposition']=='regenerated' and 'old' in entry:
  old=read(entry['old']);new=read(entry['new']);delta=differences(old,new);ck('declared delta '+entry['kind']+' '+Path(entry['new']['path']).name,delta==entry['changed_fields'],delta)
  old_new[entry['old']['path']]=entry['new'];delta_details.append({'kind':entry['kind'],'new':entry['new'],'differences':delta})
  # Any scientific resolved setting must remain the same except source commit runtime bindings.
  if 'resolved_config' in new:
   ck('science config delta '+Path(entry['new']['path']).name,all(x in ['/n34_runtime_binding/source_commit','/n36_runtime_binding/source_commit'] for x in differences(old['resolved_config'],new['resolved_config'])))
   oa=[x.replace(inputs['prior_source'],authority['source']) for x in old['argv']];ck('argv preserved '+Path(entry['new']['path']).name,oa==new['argv'])
  if 'expected_runtime' in new and new['expected_runtime'] is not None:ck('algorithm hashes preserved '+Path(entry['new']['path']).name,new['expected_runtime']['source_hashes']==old['expected_runtime']['source_hashes'])
 elif entry['disposition']=='reused_byte_identical':read(entry['reference'])
# Examine every active affected document for old graph refs; historical anchors intentionally excluded.
active=[graph,plan,audit,manifest]+[read(v) for v in audit['expected_manifests'].values()]
for i,d in enumerate(active):
 stale=[r for r in refs(d) if r['path'] in old_new];ck('no stale affected refs '+str(i),not stale,stale)
for row in audit['episodes']:
 m=read(audit['expected_manifests'][row['episode_key']]);ck('manifest row '+row['episode_key'],m['row']==row)
 for k in ['source','scientific_source','runtime','runtime_closure','native_build','controller_semantics','scope','deployment','protocol','protocol_review','accounting']:
  ck('manifest binding '+row['episode_key']+' '+k,m[k]==audit[k])
ck('engineering mapped audit',manifest['audit_plan']==plan['audit_plan'] and manifest['audit_manifest']==audit['expected_manifests'][audit['episodes'][0]['episode_key']] and manifest['audit_row']==audit['episodes'][0])
for k in ['source','scientific_source','runtime','runtime_closure','native_build','controller_semantics','scope','deployment','accounting']:ck('engineering binding '+k,manifest[k]==plan[k])
retained={k:read(v) for k,v in graph['retained_bindings'].items()}
for k,v in graph['retained_bindings'].items():ck('retained plan '+k,plan[k]==v)
rt=retained['runtime'];cl=retained['runtime_closure'];ctrl=retained['controller_semantics']
ck('runtime closure crossbinding',cl['runtime']==plan['runtime']);ck('controller closure crossbinding',ctrl['runtime_closure']==plan['runtime_closure'])
ck('runtime still unready',rt['provider_ready'] is False and rt['cuda_egl_verified'] is False and rt['preparation']['runtime_ready'] is False)
for kind,obj in [('runtime',rt),('runtime_closure',cl),('native_build',retained['native_build'])]:
 overlaps=[r for r in refs(obj) if r['path'] in {str(ROOT/f) for f in changed}];ck('no changed project files embedded in reused '+kind,not overlaps,overlaps)
controller_ns=load_ast('scripts/qd_ed_n34_controller.py',['FIELDS','verify_semantics'],{'w':w,'math':math})
try:controller_ns['verify_semantics'](plan['controller_semantics'],plan['runtime'],cl);ck('exact controller semantics verifier',True)
except Exception as ex:ck('exact controller semantics verifier',False,str(ex))
# Explicit direct reviewed source hashes only; do not recursively traverse historical reviews.
ck('controller installed source bytes',sha(ctrl['source']['path'])==ctrl['source']['sha256'])
for v in ctrl['review_evidence'].values():read(v)
account=retained['accounting'];spec=ens['specification']()
ck('accounting proposal exact',account['accounting']==spec['accounting_proposal'])
for name,r in account['retained_ledger_prefixes'].items():
 with open(r['path'],'rb') as stream:data=stream.read(r['bytes'])
 ck('retained ledger prefix '+name,len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256'])
ck('output absent',not os.path.lexists(plan['artifact_root']))
for key in ['protocol','protocol_review']:read(audit[key])
ck('review matrix no prior B5 transfer',matrix['prior_B5_transfers'] is False)
stop.check(need=1)
result={'schema':'n36-independent-b5-passive-checks-v1','source':authority['source'],'checks':checks,'failures':[x for x in checks if not x['pass']],'direct_hashes':hashes,'definitions':definitions,'affected_deltas':delta_details,'tests_run':0,'production_imports':False,'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'at':dt.datetime.now(dt.timezone.utc).isoformat()}
with (OUT/'passive-checks-v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'checks':len(checks),'failures':result['failures'],'hashes':len(hashes)},indent=2))
