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
checks=read(bind(OUT/'checks-results-v1.json'));extra=read(bind(OUT/'supplemental-checks-v1.json'))
assert not checks['errors'] and extra['status']=='PASS_DISABLED_BINDINGS'
plan=read(bind(OUT/'draft/plan.draft.json'));parent=read(A['parent_plan']);accept=read(A['repair_acceptance'])
source_index={x['path']:x['sha256'] for x in plan['source']['files']}
runtime=read(plan['runtime']);closure=read(plan['runtime_closure']);oldclosure=read(parent['runtime_closure'])
changes=[]
for item in accept['changed_files']:
 name=item['path'];ref=bind(ROOT/name)
 assert ref['sha256']==item['after_sha256']==source_index[name]
 changes.append({'relative_path':name,'source':ref,'runtime_inventory_entries':[x for x in runtime['files'] if x['path']==str(ROOT/name)],'runtime_closure_modules':[k for k,v in closure['modules'].items() if v['path']==str(ROOT/name)]})
assert closure.get('module_aliases')==oldclosure.get('module_aliases')
assert closure.get('generated_modules')==oldclosure.get('generated_modules')
write('runtime-input-bindings.disabled-v1.json',{'status':'DISABLED_CPU_BINDING_REFRESH','source':bind(OUT/'source.complete-v1.json'),'runtime':plan['runtime'],'runtime_closure':plan['runtime_closure'],'changes':changes,'all_changed_paths_in_exact_source':True,'inventory_entries_removed':False,'module_aliases_preserved':True,'generated_modules_preserved':True,'release_enabled':False})
import ast
callers=[]
for file,fn in [('qd_ed_n36_healthcheck.py','run_healthcheck'),('qd_ed_n36_runner.py','execute_one')]:
 p=ROOT/'scripts'/file;tree=ast.parse(p.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==fn)
 calls=[{'line':n.lineno,'call':ast.unparse(n)} for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='attest']
 assert calls
 callers.append({'source':bind(p),'function':fn,'attestation_calls':calls,'validated_release_precedes_attestation':True})
write('production-parent-attestation-feasibility-v1.json',{'schema':'n36r3-production-parent-cpu-attestation-feasibility-v1','status':'BLOCKED_BY_REQUIRED_PRODUCTION_GOVERNANCE','mode':'Static exact caller inspection and actual production release validators on disabled bindings','validators':{k:v for k,v in extra['checks'].items() if 'governance_gate' in k},'callers':callers,'production_parent_attestation_executed':False,'production_parent_imports_exercised':False,'source_only_bootstrap_exercised':False,'synthetic_governance_used':False,'reservation_reached':False,'runtime_closure_passive_check_passed':True,'native_inventory_passive_check_passed':True,'controller_root_review_required':True,'manifest_refresh_after_root_controller_review_required':True,'conclusion':'Passive CPU consistency is feasible and passed. Actual production-parent attestation cannot be reached with disabled bindings; no readiness or B5 inferred.'})
immutable=read(bind(OUT/'immutable-before-v1.json'))
for group in immutable.values():
 for ref in group.values():assert bind(ref['path'])==ref
assert git(ROOT,'rev-parse','HEAD')==A['source'] and not git(ROOT,'status','--porcelain','--untracked-files=no')
assert git(OWNER,'rev-parse','HEAD')==checks['summary']['owner_head_observed']
assert plan['episodes']==parent['episodes'] and len(plan['episodes'])==40
assert plan['resource_routing']==parent['resource_routing']
accounting=read(bind(OUT/'accounting-snapshot.disabled-v1.json'))
assert accounting['arithmetic']['hours']['retained']=='75.53031173955723'
assert accounting['snapshot']['dispatched']==505 and not plan['release_enabled']
write('commands-results-v1.json',{'cwd':str(ROOT),'executed':[{'argv':[sys.executable,'-B',str(OUT/name)],'exit_code':0,'log':bind(OUT/log)} for name,log in [('refresh-bindings-v1.py','refresh-v1.log'),('complete-bindings-v1.py','complete-v1.log')]],'passive_git_commands':checks['commands']+extra['commands']+COMMANDS,'finalizer_argv':[sys.executable,'-B',str(OUT/'finalize-report-v1.py')],'finalizer_completion':'report and hash sidecar written only after assertions','inspection_commands':['Read authority-v1.json and referenced repair acceptance/report','Read turn001419 refresh-bindings-v1.py and complete-bindings-v1.py; turn001421 refresh-v1.py','Read canonical STOP module and driver-status; checked both STOP paths and 900-second deadline headroom','Read preparation arithmetic/admission/controller APIs and production attestation caller paths'],'preparation_errors':['Initial finalizer file-generation command had nested triple-quote SyntaxError; no file was written. The subsequent attempted execution returned file-not-found. Corrected before executing finalizer; no binding outputs affected.','Exploratory rg for scripts/qd_ed_source_execution.py returned missing path; actual caller sources were inspected directly.'],'no_broad_tests':True,'cpu_threads':2})
gates=[{'id':'ROOT_CONTROLLER_REVIEW_AND_MANIFEST_REFRESH','status':'REQUIRED','detail':'Root must review exact new controller/runtime/closure and evidence. Then refresh all 40 manifests and plan/bindings to that root-reviewed controller reference; these disabled drafts are not the final B5 target.'},{'id':'B5','status':'REQUIRED_INDEPENDENT','detail':'New independent exact B5 on repaired source and final root-reviewed bindings; none supplied or fabricated.'},{'id':'ROOT_ADOPTION','status':'REQUIRED','detail':'Root adoption of exact source/runtime and reconciliation of all three owner journals; no adoption here.'},{'id':'FINITE_ACCOUNTING','status':'REQUIRED','detail':'Root finite accounting and detached authority using retained 75.53031173955723 GPUh / 505 attempts. Arithmetic is prospective, current headroom remains null; no new spend authority.'},{'id':'FRESH_CHARGED_HEALTH','status':'REQUIRED_UNEXECUTED','detail':'Genuinely execute and durably charge n36_healthcheck_n36r3_preparation_001426 after root authority, with actual parent/import/controller/native/generated and GPU/provider evidence. Preserve prior charged health/failures; no replay.'},{'id':'FIRST_C0','status':'REQUIRED_UNRELEASED','detail':'Separate root episode authority after valid fresh health.'},{'id':'G3','status':'MANDATORY_FIRST_C0_TERMINAL_PAUSE','detail':'Root review of actual first-C0 production/audit evidence before any later cell; no retries or automatic recovery.'}]
md='''# Leaf 15.6 — disabled CPU binding refresh

Prepared source d01bc1e2e7acc876653a43ddf157d0b4a641f88a as new disabled artifacts only. Score: null. Goal incomplete. No source edits, adoption, owner/ledger writes, GPU/provider execution, reservation, release, child agents, or protected results access.

Exact source (1101 files), runtime inventory (3300 files), runtime closure (6767 modules), passive native inventory, inherited controller semantics, owner routing, and all 40 regenerated manifests passed. One existing inventory entry and one module changed; all four repaired source paths are in the exact source record. Scientific rules, production Main/native audit requirements, 40 identities, owner routing, and deadline 2026-10-11T11:13:13Z are preserved.

The repaired production accounting helper passed against unchanged owner journal bytes: 75.53031173955723 GPUh / 505 attempts. Finite arithmetic yields conservative-after 96.76388342983685 GPUh, with 21 cohort GPUh and 44 protected GPUh; this is not current spendable headroom. New health policy binds n36_healthcheck_n36r3_preparation_001426. Old charged health and failures remain retained; no replay.

Actual production release validators reject these disabled bindings before attestation/reservation. CPU inventory consistency passed; actual production parent/import/controller/native/generated attestation was not executed. No readiness or B5 is claimed.

Remaining gates: root controller review and consequent 40-manifest/plan refresh; independent exact B5; root source/runtime adoption and finite accounting/journal reconciliation; fresh charged production health; separate first-C0 release; mandatory G3 pause at first-C0 terminal. No later-cell continuation.

Commands: python -B refresh-bindings-v1.py; python -B complete-bindings-v1.py; python -B finalize-report-v1.py, using absolute paths in this output directory. Exact argv, logs, read-only Git commands, checks, and artifact SHA-256 bindings are in commands-results-v1.json and report-v1.json. Two CPU threads; 900-second task cap. STOP/deadline checked before work and at finalization. No locks/leases acquired. No broad historical tests or recursive provenance rebuild.

New copies derive from inspected turn001419 tools. The initial tooling-provenance-v1.json captures the copy before adding the health-policy artifact to complete-bindings-v1.py; the report binds the final executed script. Manifest generation uses the same production API inspected in turn001421. An initial finalizer-writing command failed to parse before creating any file; the corrected finalizer completed the artifact checks.
'''
with (OUT/'report-v1.md').open('x') as f:f.write(md)
names=['authority-v1.json','tooling-provenance-v1.json','refresh-bindings-v1.py','complete-bindings-v1.py','finalize-report-v1.py','source.complete-v1.json','scientific-source-provenance-v1.json','runtime.isolated.disabled-v1.json','runtime-closure.isolated.disabled-v1.json','runtime-rebinding-provenance-v1.json','runtime-input-bindings.disabled-v1.json','required-after.production-v1.json','native-build.disabled-v1.json','controller-semantics.disabled-v1.json','accounting-snapshot.disabled-v1.json','health-policy.disabled-v1.json','bindings.disabled-v1.json','draft/plan.draft.json','immutable-before-v1.json','checks-results-v1.json','supplemental-checks-v1.json','commands-results-v1.json','production-parent-attestation-feasibility-v1.json','refresh-v1.log','complete-v1.log','report-v1.md']
names += [str(p.relative_to(OUT)) for folder in ['controller-evidence','draft/expected'] for p in sorted((OUT/folder).glob('*.json'))]
guard()
report={'schema':'n36r3-binding-refresh-report-v1','node_id':'15.6','at':dt.datetime.now(dt.timezone.utc).isoformat(),'decision':'PASS_DISABLED_CPU_BINDINGS_ROOT_CONTROLLER_REVIEW_MANIFEST_REFRESH_AND_B5_REQUIRED','result':'Exact disabled binding refresh and repaired accounting snapshot passed; production attestation governance-blocked.','source':A['source'],'authority':bind(OUT/'authority-v1.json'),'repair_acceptance':A['repair_acceptance'],'repair_report':A['repair_report'],'parent_plan':A['parent_plan'],'summary':checks['summary'],'checks':checks['checks'],'supplemental_checks':extra['checks'],'remaining_gates':gates,'artifacts':{n:bind(OUT/n) for n in names},'stop_check':{'passed':True,**stop.binding()},'retained_gpu_hours':75.53031173955723,'retained_attempts':505,'health_identity':'n36_healthcheck_n36r3_preparation_001426','owner_journal_and_parent_artifact_hashes_unchanged':True,'source_edits':False,'source_adopted':False,'owning_accounting_adopted':False,'production_health_executed':False,'production_parent_attestation_executed':False,'runtime_ready':False,'release_enabled':False,'gpu_authorized':False,'score':None,'goal_complete':False,'target_met':False,'cpu_threads':2,'wall_cap_seconds':900,'code_ref':A['source'],'limitations':['No independent B5 or root-reviewed controller semantics fabricated','Historical runtime readiness fields retained as provenance only; preparation explicitly disables readiness','Finite arithmetic is not current headroom or authority','No broad test repeats; accepted repair tests not rerun','No source-only production bootstrap exercised; no production import attestation claim']}
write('report-v1.json',report)
with (OUT/'report-v1.sha256').open('x') as f:
 for n in ['report-v1.json','report-v1.md']:f.write(bind(OUT/n)['sha256']+'  '+n+'\n')
print(json.dumps({'status':report['decision'],'report':bind(OUT/'report-v1.json'),'score':None,'goal_complete':False}))
