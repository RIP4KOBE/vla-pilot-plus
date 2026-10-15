import os, sys, json, hashlib, datetime as dt, time, resource, subprocess, traceback, copy, signal
from pathlib import Path
OUT=Path(__file__).resolve().parent
A=json.loads((OUT/'authority-v1.json').read_text()); ROOT=Path(A['worktree']); OWNER=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree'); BASE=OUT.parents[1]
START=time.monotonic(); sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(600,600));signal.alarm(720)
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='2'
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['GIT_OPTIONAL_LOCKS']='0';os.environ['GIT_NO_LAZY_FETCH']='1'
os.environ['TMPDIR']=str(OUT/'tmp')
(OUT/'tmp').mkdir(exist_ok=True)
from scripts import qd_ed_n36_stop as stop
CHECKS={}; ART={}; INPUTS={}; COMMANDS=[]; ERRORS=[]
def guard():
 stop.check();assert time.monotonic()-START<720;assert time.time()-json.loads((OUT/'executor-process-v1.json').read_text())['started_unix']<900

def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('network forbidden')
 if event=='subprocess.Popen':
  argv=args[1];assert isinstance(argv,(list,tuple)) and Path(argv[0]).name=='git','only passive Git subprocesses permitted'
  assert any(x in argv for x in ('rev-parse','status','diff','ls-tree','cat-file','config')),'non-read-only Git forbidden'
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.path.abspath(os.fsdecode(args[0])); low=name.lower()
  assert not any(x in low for x in ('/.codex/auth.json','/.git-credentials','credentials.json','2026-08-10-eds-qd-stage-guidance-transition-design.md')),'prohibited read'
  assert not (('/validation/' in low or '/formal/' in low) and ('outcome' in low or '/artifacts/' in low)),'protected outcomes forbidden'
  flags=args[2]
  if isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
   assert name == '/dev/null' or Path(name).resolve().is_relative_to(OUT),'write outside output forbidden'
 if event in ('os.rename','os.remove','os.rmdir','os.mkdir'):
  for name in args[:2] if event=='os.rename' else args[:1]:
   if isinstance(name,(str,bytes)):assert Path(os.fsdecode(name)).resolve().is_relative_to(OUT),'mutation outside output forbidden'
 if event=='exec' and getattr(args[0],'co_filename','')==str(ROOT/'main.py'):raise PermissionError('Main forbidden')
sys.addaudithook(audit)
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb') as f:
  for raw in iter(lambda:f.read(8*1024*1024),b''):h.update(raw)
 return {'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest()}
def read(ref):
 b=bind(ref['path']);assert b['sha256']==ref['sha256'] and ('bytes' not in ref or b['bytes']==ref['bytes']);INPUTS[str(ref['path'])]=b
 return json.loads(Path(ref['path']).read_text())
def write(name,value):
 guard();p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
 ART[name]=bind(p);return {'path':str(p),'sha256':ART[name]['sha256']}
def git(root,*args):
 guard();argv=['git','-C',str(root),*args];p=subprocess.run(argv,text=True,capture_output=True);COMMANDS.append({'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});assert p.returncode==0,p.stderr;return p.stdout.strip()
def check(name,fn):
 guard();t=time.monotonic()
 try:v=fn();CHECKS[name]={'status':'PASS','seconds':time.monotonic()-t};print(name,'PASS',flush=True);return v
 except Exception as e:CHECKS[name]={'status':'FAIL','error':str(e),'traceback':traceback.format_exc()};raise



from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n36r3_admission as admission,qd_ed_n36r3_preparation as pack,qd_ed_n36_release as release
from scripts.qd_ed_n36_supervise import first_c0_boundary
accept=read(A['repair_acceptance']);plan=read(bind(OUT/'draft/plan.draft.json'));pr={'path':str(OUT/'draft/plan.draft.json'),'sha256':bind(OUT/'draft/plan.draft.json')['sha256']}
# Only adapt review field names to the unchanged production API; hashes stay exact.
anchors={name:{k:ref[k] for k in ('path','bytes','sha256')} for name,ref in accept['ledger_prefixes'].items()}
review={'ledger_prefix':anchors['attempt-ledger.jsonl'],'health_ledger_prefix':anchors['gpu-healthcheck-ledger.jsonl']}
snapshot=check('read_only_current_ledger_snapshot',lambda:pack.ledger_snapshot(OWNER,review))
assert snapshot['ledger_prefixes']==anchors
assert snapshot['snapshot']==accept['budget_snapshot']
health_rows=[json.loads(line) for line in Path(anchors['gpu-healthcheck-ledger.jsonl']['path']).read_text().splitlines() if line.strip()]
assert not any(row.get('resource_id')==admission.PREPARATION_ID for row in health_rows),'accepted prospective health identity already used'
assert any(row.get('resource_id')=='n36_healthcheck_n36r3_preparation_001426' for row in health_rows),'prior charged health absent'
write('accounting-snapshot.disabled-v1.json',{'release_enabled':False,'owning_accounting_adopted':False,'current_headroom':None,**snapshot,'arithmetic':pack.arithmetic(snapshot['snapshot'])})
assert first_c0_boundary(plan['episodes'][0]) and plan['episodes'][0]['profile']=='C0'
c.validate_draft(plan)
assert plan['controller_semantics']['path']==str(OUT/'controller-semantics.disabled-v1.json')
controller=read(plan['controller_semantics']);parent=read(A['parent_plan']);oldcontroller=read(parent['controller_semantics'])
for key in ('instance','semantics','source','physical_gain_certified','module','class'):assert controller[key]==oldcontroller[key]
assert controller['runtime']==plan['runtime'] and controller['runtime_closure']==plan['runtime_closure'] and controller['source_commit']==A['source']
for ref in controller['review_evidence'].values():
 ev=read(ref);assert ev['runtime']==plan['runtime'] and ev['runtime_closure']==plan['runtime_closure'] and ev['source_commit']==A['source']
assert plan['episodes']==parent['episodes'] and len(plan['episodes'])==40
assert plan['resource_routing']==parent['resource_routing']
assert release.N36R3_OWNER_ALIAS=='/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z'
assert Path(release.N36R3_OWNER_ALIAS).resolve()==OWNER
assert admission.PREPARATION_ID=='n36_healthcheck_n36r3_preparation_001445'
assert snapshot['snapshot']['gpu_hours_consumed']==75.53335346582918
assert snapshot['snapshot']['dispatched']==505
health_ref=write('health-policy.disabled-v1.json',{'schema':'n36r3-health-policy-draft-v1','status':'DISABLED_PENDING_ROOT_REVIEW','source':A['source'],'plan':pr,'runtime':plan['runtime'],'runtime_closure':plan['runtime_closure'],'healthchecks':admission.HEALTH,'preparation_id':admission.PREPARATION_ID,'prior_charged_identity':'n36_healthcheck_n36r3_preparation_001426','runtime_ready':False,'readiness_transferred':False,'later_fresh_identity_requirement':'001445 is prospective and must be uncharged before use. Once charged or attempted, a later fresh identity requires separately accepted source repair and new bindings; never reuse 001426 or 001445 for replay.','prior_health_and_failures_retained':True,'replay_allowed':False,'release_enabled':False,'fresh_charged_production_health_required':True,'arithmetic_health_bounds':pack.arithmetic(snapshot['snapshot'])['health'],'deadline':c.DEADLINE,'source_bindings':{name:bind(ROOT/'scripts'/name) for name in ('qd_ed_n36r3_admission.py','qd_ed_n36r3_preparation.py','qd_ed_n36r3_health.py','qd_ed_n36_release.py')}})
bindings=write('bindings.disabled-v1.json',{'schema':'n36r3-refresh-bindings-draft-v1','status':'DISABLED_PENDING_INDEPENDENT_B5_AND_ROOT_REVIEW','plan':pr,**{k:plan[k] for k in admission.BINDINGS},'expected_manifests':plan['expected_manifests'],'deadline':c.DEADLINE,'stop_authority':stop.binding(),'first_C0':'PAUSED_FOR_ROOT_G3; no later-cell continuation authority','accounting_snapshot':{'path':str(OUT/'accounting-snapshot.disabled-v1.json'),'sha256':bind(OUT/'accounting-snapshot.disabled-v1.json')['sha256']},'health_policy':health_ref,'b5_review':None,'source_adoption':None,'owning_accounting':None,'health_release':None,'episode_release':None,'release_enabled':False,'runtime_ready':False,'target_met':False,'score':None})
for label,fn in [('health',release.validate_health_release),('episode',release.validate_release)]:
 try:fn(pr,bindings)
 except ValueError as e:
  assert str(e)=='N36R3 draft only; separate root bindings required'
  CHECKS[label+'_production_governance_gate']={'status':'EXPECTED_BLOCK','error':str(e),'release_reference_is_disabled_binding_not_authority':True,'attestation_reached':False,'reservation_reached':False}
 else:raise AssertionError('draft unexpectedly accepted')
immutable=json.loads((OUT/'immutable-before-v1.json').read_text())
for group in immutable.values():
 for ref in group.values():assert bind(ref['path'])==ref
assert git(ROOT,'rev-parse','HEAD')==A['source'] and not git(ROOT,'status','--porcelain','--untracked-files=no')
assert git(OWNER,'rev-parse','HEAD')==json.loads((OUT/'checks-results-v1.json').read_text())['summary']['owner_head_observed']
write('supplemental-checks-v1.json',{'checks':CHECKS,'commands':COMMANDS,'status':'PASS_DISABLED_BINDINGS','ledger_adapter':'accepted ledger_prefixes keyed by filename mapped to existing ledger_snapshot review keys; acceptance annotation excluded from byte/hash binding','controller_provenance_consistent':True,'canonical_owner_alias_preserved':True,'owner_and_prior_artifacts_unchanged':True,'goal_complete':False,'score':None})
print('PASS_DISABLED_BINDINGS',flush=True)
