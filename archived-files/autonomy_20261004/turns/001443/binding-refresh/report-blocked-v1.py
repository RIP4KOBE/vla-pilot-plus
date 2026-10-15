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
 stop.check();assert time.monotonic()-START<720

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



guard()
checks=read(bind(OUT/'checks-results-v1.json'))
accept=read(A['repair_acceptance'])
immutable=read(bind(OUT/'immutable-before-v1.json'))
for group in immutable.values():
 for ref in group.values(): assert bind(ref['path'])==ref
assert git(ROOT,'rev-parse','HEAD')==A['source']
assert not git(ROOT,'status','--porcelain','--untracked-files=no')
assert git(OWNER,'rev-parse','HEAD')==checks['summary']['owner_head_observed']
from scripts import qd_ed_final_runner as runner
rows={name:[json.loads(line) for line in Path(ref['path']).read_bytes().splitlines() if line.strip()] for name,ref in accept['ledger_prefixes'].items()}
# Diagnostic only: do not bypass the failed preparation API or produce an accounting binding.
snap=runner.budget_snapshot(rows['attempt-ledger.jsonl'],rows['gpu-healthcheck-ledger.jsonl'])
health=[{k:v for k,v in row.items() if k in ('event','resource_id','kind','source_commit','gpu_process_wall_seconds')} for row in rows['gpu-healthcheck-ledger.jsonl'] if row.get('resource_id')=='n36_healthcheck_n36r3_preparation_001426']
source_path=ROOT/'scripts/qd_ed_n36r3_preparation.py'
lines=source_path.read_text().splitlines()
evidence=write('blocking-evidence-v1.json',{'failed_command':{'argv':[sys.executable,'-B',str(OUT/'complete-bindings-v1.py')],'exit_code':1,'log':bind(OUT/'complete-v1.log')},'error':'ValueError: current accounting differs; fresh root reconciliation required','source':bind(source_path),'source_lines':{str(i):lines[i-1] for i in [48,49,50,63]},'diagnostic_budget_snapshot':snap,'diagnostic_only_not_accounting_binding':True,'retained_actual_attempts':505,'retained_actual_gpu_hours':75.53335346582918,'stale_source_gpu_hours_constant':75.53031173955723,'prior_health_events':health,'later_fresh_health_identity_required':True,'later_fresh_health_identity':None,'readiness_transfers':False,'ledger_bindings':accept['ledger_prefixes'],'immutable_inputs_rechecked':True,'source_and_owner_heads_unchanged':True})
missing=['runtime-input-bindings.disabled-v1.json','accounting-snapshot.disabled-v1.json','health-policy.disabled-v1.json','bindings.disabled-v1.json','supplemental-checks-v1.json','production-parent-attestation-feasibility-v1.json']
assert all(not (OUT/n).exists() for n in missing)
md="""# Leaf 15.6 — STOPPED on production accounting mismatch

Exact source: e36f8b945f6b2fde9e81010b3d16987b8c771dd0. Score: null. Goal incomplete. Release disabled.

Partial disabled bindings passed exact source (1102 files), runtime inventory (3300 files), runtime closure (6767 modules), passive native inventory, inherited controller semantics, owner lexical routing, draft contract and all 40 exact manifests. One inventory entry and one closure module were rebound. All episode identities, frozen science, production Main/native audit requirements, deadline 2026-10-11T11:13:13Z and first-C0 G3 pause remain preserved.

STOP: complete-bindings-v1.py exited 1 in the production ledger_snapshot API with `ValueError: current accounting differs; fresh root reconciliation required`. scripts/qd_ed_n36r3_preparation.py:48-50 still requires 75.53031173955723 GPUh; retained actual accounting is 505 attempts / 75.53335346582918 GPUh. Its arithmetic guard at line 63 also retains the stale constant. Exact source hash, log, ledger bindings and diagnostic snapshot are in blocking-evidence-v1.json. No assertion was weakened, no source was edited, and binding generation was not resumed.

The source-fixed health identity n36_healthcheck_n36r3_preparation_001426 is already completed and charged for earlier source d01bc1e2e7acc876653a43ddf157d0b4a641f88a. A later fresh identity requires separate authorized source/binding review; none is invented here. Prior charged health remains retained; readiness cannot transfer and replay is prohibited.

The full binding package is incomplete: runtime-input, accounting, health-policy, aggregate bindings and supplemental feasibility artifacts were not produced. Finalize-report-v1.py was inspected/copied but not executed because its prerequisites were not met; this blocked report was produced by report-blocked-v1.py. Passive inventory feasibility passed, but production release validators and parent attestation were not reached.

Next gates remain separate: root accounting reconciliation and authorized repair decision, root controller review/final manifest refresh, exact independent B5, source/runtime adoption, fresh health identity and charged health, first-C0 release, mandatory G3 terminal pause. No release authority is provided.

All prior bound inputs and three owner ledgers were hash-rechecked unchanged; source and owner heads were unchanged. No source edits, owner state/ledger writes, GPU/provider calls, child agents, locks/leases, protected results access, broad test repeats or historical provenance rebuild. Two CPU threads; 900-second cap. STOP/deadline checked before execution and reporting.
"""
with (OUT/'report-v1.md').open('x') as f:f.write(md)
names=['authority-v1.json','tooling-provenance-v1.json','refresh-bindings-v1.py','complete-bindings-v1.py','finalize-report-v1.py','report-blocked-v1.py','source.complete-v1.json','scientific-source-provenance-v1.json','runtime.isolated.disabled-v1.json','runtime-closure.isolated.disabled-v1.json','runtime-rebinding-provenance-v1.json','required-after.production-v1.json','native-build.disabled-v1.json','controller-semantics.disabled-v1.json','draft/plan.draft.json','immutable-before-v1.json','checks-results-v1.json','refresh-v1.log','complete-v1.log','blocking-evidence-v1.json','report-v1.md']
names += [str(p.relative_to(OUT)) for folder in ['controller-evidence','draft/expected'] for p in sorted((OUT/folder).glob('*.json'))]
report={'schema':'n36r3-binding-refresh-report-v1','node_id':'15.6','at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'STOPPED_PRODUCTION_ACCOUNTING_MISMATCH','result':'Partial disabled bindings passed; production accounting audit failed. No continuation or weakened audit.','source':A['source'],'code_ref':A['source'],'repair_acceptance':A['repair_acceptance'],'repair_report':A['repair_report'],'parent_plan':A['parent_plan'],'summary':checks['summary'],'checks':checks['checks'],'failure':evidence,'checks_not_reached':['production health/episode governance gates','production-parent attestation'],'artifacts':{n:bind(OUT/n) for n in names},'missing_artifacts':missing,'commands':[{'argv':[sys.executable,'-B',str(OUT/'refresh-bindings-v1.py')],'exit_code':0},{'argv':[sys.executable,'-B',str(OUT/'complete-bindings-v1.py')],'exit_code':1},{'argv':[sys.executable,'-B',str(OUT/'finalize-report-v1.py')],'executed':False,'reason':'prerequisites absent after audit mismatch'}],'reporting_git_checks':COMMANDS,'remaining_gates':['root accounting reconciliation and separately authorized repair decision','root controller review and exact manifest refresh','independent exact B5','source/runtime adoption','separately authorized later fresh health identity and charged health','first-C0 release','mandatory first-C0 G3 pause'],'retained_attempts':505,'retained_gpu_hours':75.53335346582918,'later_fresh_health_identity_required':True,'later_fresh_health_identity':None,'owner_journal_and_parent_artifact_hashes_unchanged':True,'source_edits':False,'source_adopted':False,'owning_accounting_adopted':False,'production_health_executed':False,'production_parent_attestation_executed':False,'runtime_ready':False,'release_enabled':False,'gpu_authorized':False,'replay_allowed':False,'score':None,'goal_complete':False,'target_met':False,'cpu_threads':2,'wall_cap_seconds':900,'stop_check':{'passed':True,**stop.binding()}}
guard()
write('report-v1.json',report)
with (OUT/'report-v1.sha256').open('x') as f:
 for n in ['report-v1.json','report-v1.md']:f.write(bind(OUT/n)['sha256']+'  '+n+'\n')
print(json.dumps({'status':report['status'],'report':bind(OUT/'report-v1.json'),'score':None,'goal_complete':False}))
