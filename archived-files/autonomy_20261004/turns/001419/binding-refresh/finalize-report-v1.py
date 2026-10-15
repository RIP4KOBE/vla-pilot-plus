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



import ast
from scripts import qd_ed_n36_release as release,qd_ed_n36_contract as c,qd_ed_n36r3_admission as admission
from scripts.qd_ed_n36_supervise import first_c0_boundary
plan=json.loads((OUT/'draft/plan.draft.json').read_text());prior=read(A['parent_plan'])
checks=json.loads((OUT/'checks-results-v1.json').read_text());supp=json.loads((OUT/'supplemental-checks-v1.json').read_text())
assert supp['status']=='PASS_DISABLED_BINDINGS'
assert not checks['errors']
assert supp['checks']['read_only_current_ledger_snapshot']['status']=='PASS'
for key in ('runtime','runtime_closure','native_build','controller_semantics'):
 read(plan[key])
for ref in plan['expected_manifests'].values():read(ref)
assert first_c0_boundary(plan['episodes'][0]) and not any(first_c0_boundary(r) for r in plan['episodes'][1:])
assert plan['episodes']==prior['episodes'] and len(plan['expected_manifests'])==40
# Static, exact call-site feasibility: no AST execution or production governance replacement.
callers=[]
for name,fn in [('scripts/qd_ed_n36_healthcheck.py','run_healthcheck'),('scripts/qd_ed_n36_runner.py','execute_one')]:
 path=ROOT/name;tree=ast.parse(path.read_text());function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==fn)
 calls=[n for n in ast.walk(function) if isinstance(n,ast.Call)]
 att=next(n for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='attest')
 kw=next(k.value for k in att.keywords if k.arg=='binding')
 assert isinstance(kw.func,ast.Attribute) and kw.func.attr=='runtime_receipt_binding'
 assert [ast.unparse(v) for v in kw.args]==['release_ref','plan','w.process_identity()',"'runtime_before'"]
 validators=[n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='validate' or isinstance(n.func,ast.Attribute) and n.func.attr=='validate_release']
 assert any(v.lineno<att.lineno for v in validators)
 callers.append({'source':bind(path),'function':fn,'attest_line':att.lineno,'call':ast.unparse(att),'validated_release_precedes_attestation':True})
feasibility={'schema':'n36r3-production-parent-cpu-attestation-feasibility-v1','status':'BLOCKED_BY_REQUIRED_PRODUCTION_GOVERNANCE','mode':'exact production release validators executed against refreshed disabled plan; exact caller paths inspected statically','production_parent_attestation_executed':False,'production_parent_imports_exercised':False,'source_only_bootstrap_exercised':False,'synthetic_governance_used':False,'validators':{k:v for k,v in supp['checks'].items() if 'production_governance' in k},'callers':callers,'precise_blockers':['Both production callers validate a detached release before runtime_before attestation. Refreshed draft has authority=None, b5_review=None, release_enabled=False and frozen=False. Both real production validators reject: N36R3 draft only; separate root bindings required.','Controller binding has DISABLED_PENDING_ROOT_REVIEW status and its exact production semantic verifier rejects: reviewed controller semantics required.','No independently reviewed B5, refreshed root adoption, owning accounting or detached health/episode release exists for this draft. A successful exact parent attestation cannot be claimed by passing an unvalidated preparation reference to the helper.'],'runtime_receipt':None,'gpu_reserved':False,'release_enabled':False,'next':'After root governance exists, use exact source-only production interpreter/bootstrap and real parent call path, retain same-process runtime_before evidence and any rejection before reservation; do not replay old health invocation.'}
write('production-parent-attestation-feasibility-v1.json',feasibility)
immutable=json.loads((OUT/'immutable-before-v1.json').read_text())
for group in immutable.values():
 for ref in group.values():assert bind(ref['path'])==ref
assert git(ROOT,'rev-parse','HEAD')==A['source'] and not git(ROOT,'status','--porcelain','--untracked-files=no')
assert git(OWNER,'rev-parse','HEAD')=='bee9f6a4703e9d5d802d6b8c7950b69beefac4c0'
stop.check()
for name in ('refresh-bindings-v1.py','complete-bindings-v1.py','finalize-report-v1.py'):
 INPUTS[str(BASE/'001408/binding-refresh'/name)]=bind(BASE/'001408/binding-refresh'/name)
runtime=read(plan['runtime']);closure=read(plan['runtime_closure']);delta=json.loads((OUT/'runtime-rebinding-provenance-v1.json').read_text())
summary={'candidate_source':A['source'],'owner_head':'bee9f6a4703e9d5d802d6b8c7950b69beefac4c0','prior_adopted_source':prior['source']['commit'],'source_files':len(plan['source']['files']),'runtime_files':len(runtime['files']),'runtime_modules':len(closure['modules']),'runtime_rebound_entries':len(delta['changes']),'closure_rebound_modules':len(delta['module_changes']),'manifest_count':40,'identities_unchanged':True,'deadline':c.DEADLINE,'first_C0':'PAUSED_FOR_ROOT_G3','canonical_owner_alias':release.N36R3_OWNER_ALIAS,'retained_attempts':505,'retained_gpu_hours':75.53031173955723,'accepted_repair_tests_rerun':False,'owner_state_ledgers_and_old_artifacts_unchanged':True,'fresh_health_preparation_identity_created':False,'old_health_relabel_or_replay':False}
remaining=[
'Root must review this exact refreshed controller runtime/closure/evidence binding against turn 001410. Instance/semantics and deployed source hashes are unchanged; draft approval is absent. Once ROOT_REVIEWED reference is issued, regenerate all affected manifests and plan/bindings; do not reuse the current controller reference as approved.',
'Independent B5 must produce schema n36r3-independent-b5-review-v1, decision PASS_PREPARATION_REQUIRES_ROOT_RELEASE, exact final admission.BINDINGS (source, scientific_source, protocol, protocol_review, accounting, runtime, runtime_closure, native_build, controller_semantics, resource_routing), worker_receipts_are_future=true, release_enabled=false. Review all 40 final manifests and CPU feasibility limitations; prior B5 is not current.',
'Root source/runtime adoption must bind exact final BINDINGS and new independent_review under schema n36r3-source-adoption-v1 with approved=true, lexical owner_root and source_cwd. No owner checkout edit/adoption was performed by this executor.',
'Root must separately record a NEW health preparation identity and finite accounting amendment before any fresh health; never relabel or replay any old health evidence. Root must reconcile/adopt finite owning accounting under its authorized transaction lock, retaining all three exact ledger prefixes, 505 attempts and 75.53031173955723 GPUh, protected reserves, finite caps and zero automatic recoveries. Snapshot is read-only and grants no spendable balance.',
'Exact production parent runtime_before attestation remains unexecuted: full real validators reject the disabled draft before the repaired callers. Following new B5/adoption/accounting and detached root health-only release, verify using the exact bound interpreter and source-only bootstrap, real verified release_ref, validated closure and current parent process identity. Do not substitute synthetic release governance or weaken origin/native/receipt audits.',
'Fresh bounded, separately charged health readiness requires authorized idle local GPU admission and current-login official Codex gpt-6-astra only; preserve source routing and canonical owner alias, STOP/deadline and journal reconciliation. No replay of old failed launch and no automatic retry. Readiness is absent here.',
'An independently detached episode release may then authorize first C0; terminal PAUSED_FOR_ROOT_G3 is mandatory. Root must review actual same-process Main/controller/native lifecycle receipts and science/audits at G3 before later-cell continuation. Validation/formal/protected outcomes remain unopened and scientific goal remains incomplete.'
]
commands=[{'argv':['python','-B',str(OUT/'refresh-bindings-v1.py')],'exit_code':0,'semantic_result':'PASS: exact source/runtime/controller/40-manifest refresh; no caught failures','log':bind(OUT/'refresh-v1.log')},{'argv':['python','-B',str(OUT/'complete-bindings-v1.py')],'exit_code':1,'semantic_result':'BLOCKED: historical production preparation helper pins 75.52725286641478 GPUh; rejection retained','log':bind(OUT/'complete-v1.log')},{'argv':['python','-B',str(OUT/'complete-bindings-v2.py')],'exit_code':0,'semantic_result':'PASS_DISABLED_BINDINGS; read-only budget_snapshot; no production accounting acceptance or arithmetic claimed','log':bind(OUT/'complete-v2.log')},{'argv':['python','-B',str(OUT/'finalize-report-v1.py')],'semantic_result':'all assertions before report write passed'}]+checks['commands']+supp['commands']+COMMANDS
write('commands-results-v1.json',{'commands':commands,'initial_checks':checks['checks'],'continuation_checks':supp['checks'],'initial_failure_retained':[{'command':'complete-bindings-v1.py','exit_code':1,'message':'current accounting differs; fresh root reconciliation required','log':bind(OUT/'complete-v1.log')}],'production_attestation_feasibility':bind(OUT/'production-parent-attestation-feasibility-v1.json'),'threads':2,'environment':{'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','MKL_NUM_THREADS':'2','NUMEXPR_NUM_THREADS':'2'},'network_and_outside_output_mutation_blocked_by_preparation_audit_hook':True})
md=f"""Leaf 15.6 CPU binding preparation completed; all outputs remain disabled.

Exact source: `{A['source']}`. Refreshed {len(plan['expected_manifests'])} manifests preserve all identities, source/owner routing, canonical owning alias, deadline `{c.DEADLINE}`, and the first-C0 mandatory `PAUSED_FOR_ROOT_G3` boundary. Production Main, native receipts, science and audits are unchanged.

Source/runtime/native inventory checks and inherited turn 001410 controller semantics passed. Controller evidence now agrees with the refreshed runtime and manifests, but requires new root approval. The inspected new script copies adapt the accepted repair schema and ledger field names to the unchanged production API; the source/runtime pass passed. Completion v1 was rejected by the historical accounting helper fixed at 75.52725286641478 GPUh; its failure is retained. Completion v2 records the unchanged budget_snapshot calculation at 75.53031173955723 GPUh without claiming production accounting acceptance or finite headroom. No accepted focused tests were rerun.

Production parent attestation feasibility is BLOCKED: both real release validators reject the disabled draft with `N36R3 draft only; separate root bindings required`. Exact caller inspection confirms validation precedes attestation. No production parent runtime attestation or source-only bootstrap was executed; no successful runtime receipt is claimed. Governance was not stubbed.

Owner/source/state and ledgers remain unchanged: 505 attempts, 75.53031173955723 GPUh; attempt ledger 7549047 bytes, SHA256 e670db934eb05565459f33e0d1e12d8753e87c351316b460177fe8863ad2c64d. No source adoption, coordinator locks, GPU/provider calls, enabled release, or child agents.

Remaining: root controller review and dependent manifest refresh; exact independent B5; root source/runtime adoption and locked finite accounting and new health preparation identity; exact production parent attestation and newly released health readiness; separately released first C0 and root G3 review. The JSON report gives exact requirements, hashes, commands and retained failures.

Goal incomplete. Score: null.
"""
with (OUT/'report-v1.md').open('x') as f:f.write(md)
artifacts={str(p.relative_to(OUT)):bind(p) for p in sorted(OUT.rglob('*')) if p.is_file() and (p.suffix in ('.json','.py') or p.name in ('refresh-v1.log','complete-v1.log','complete-v2.log','report-v1.md')) and not p.name.startswith(('executor-','wrapper-'))}
report={'schema':'n36r3-leaf-15.6-binding-preparation-report-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'PASS_DISABLED_BINDING_PREPARATION_PRODUCTION_ATTESTATION_BLOCKED','node_id':'15.6','role':'isolated CPU binding-preparation executor; not coordinator','authority':bind(OUT/'authority-v1.json'),'parent_plan':A['parent_plan'],'repair_acceptance':A['repair_acceptance'],'prior_adoption':A['prior_adoption'],'plan':bind(OUT/'draft/plan.draft.json'),'bindings':bind(OUT/'bindings.disabled-v1.json'),'summary':summary,'checks':checks['checks'],'supplemental_checks':supp,'retained_initial_failure':[{'command':'complete-bindings-v1.py','exit_code':1,'type':'ValueError','message':'current accounting differs; fresh root reconciliation required','log':bind(OUT/'complete-v1.log')}],'failure_resolution':'Completion v1 stale fixed retained-charge rejection preserved; completion v2 observes exact ledger bytes using unchanged budget_snapshot only. Production accounting reconciliation remains blocked.','production_parent_attestation_feasibility':feasibility,'accounting_preparation_blocker':{'status':'BLOCKED_STALE_FIXED_RETAINED_CHARGE','error':'current accounting differs; fresh root reconciliation required','failed_log':bind(OUT/'complete-v1.log'),'production_arithmetic':None},'remaining_requirements':remaining,'inputs':{**immutable['parent_artifacts'],**INPUTS},'owner_immutable_snapshot':immutable['owner_files'],'artifacts':artifacts,'commands_results':bind(OUT/'commands-results-v1.json'),'cpu_threads':2,'wall_cap_seconds':900,'stop_check_at_report':{'at':dt.datetime.now(dt.timezone.utc).isoformat(),'paths':list(stop.STOP_PATHS),'passed':True},'gpu_authorized':False,'source_edits':False,'source_adopted':False,'release_enabled':False,'runtime_ready':False,'owning_accounting_adopted':False,'goal_complete':False,'target_met':False,'score':None,'code_ref':A['source']}
write('report-v1.json',report)
with (OUT/'report-v1.sha256').open('x') as f:f.write(bind(OUT/'report-v1.json')['sha256']+'  report-v1.json\n')
print(json.dumps({'report':bind(OUT/'report-v1.json'),'summary':summary,'goal_complete':False,'score':None}))
