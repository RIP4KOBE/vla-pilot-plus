import os,sys,json,hashlib,ast,datetime,resource,signal
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(60,60));signal.alarm(90)
from scripts import qd_ed_n36_stop as stop,qd_ed_n36_release as release,qd_ed_n36_contract as c
stop.check(need=90)
def ref(p):
 p=Path(p);return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(name,d):
 with (OUT/name).open('x') as f:json.dump(d,f,indent=2);f.write('\n')
def read(p):return json.loads(Path(p).read_text())
a=read(OUT/'authority-v1.json');plan=read(OUT/'draft/plan.draft.json');checks=read(OUT/'checks-results-v1.json')
assert not checks['errors']
extra={}
try:release.validate_plan(plan)
except ValueError as e:
 assert str(e)=='N36R3 draft only; separate root bindings required'
 extra['released_plan_consumer']={'status':'PASS_EXPECTED_REJECTION','message':str(e)}
else:raise AssertionError('draft admitted')
# Execute only the exact owner-validation branch on read-only live state.
import yaml
owner=Path(plan['resource_routing']['owner_root']);statefile=owner/'research-state.yaml';before=ref(statefile);state=yaml.safe_load(statefile.read_text())
tree=ast.parse((ROOT/'scripts/qd_ed_n36_release.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_state');branch=next(n for n in fn.body if isinstance(n,ast.If));ns=dict(release.__dict__);ns.update(plan=plan,state=state)
exec(compile(ast.Module(body=[branch],type_ignores=[]),str(ROOT/'scripts/qd_ed_n36_release.py'),'exec'),ns)
assert ref(statefile)==before
extra['live_owner_branch']={'status':'PASS','scope':'Exact production validate_state owner branch only; full authority/accounting admission remains unapproved.','state_binding':before,'worktree':state['worktree'],'canonical_worktree':state['canonical_worktree'],'alias_samefile':Path(state['worktree']).samefile(owner)}
# Static inspection only; do not rerun or patch older fixtures.
fixture=ROOT/'tests/test_n36r3_admission.py';ft=ast.parse(fixture.read_text());setup=next(n for n in ft.body if isinstance(n,ast.FunctionDef) and n.name=='setup');st=next(n for n in ast.walk(setup) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='state' for t in n.targets));keys=[k.value for k in st.value.keys if isinstance(k,ast.Constant)]
assert 'canonical_worktree' not in keys
extra['older_synthetic_fixture']={'status':'STATIC_BLOCKER_IF_REUSED','source':ref(fixture),'line':st.lineno,'fixture':'tests/test_n36r3_admission.py::setup','missing_key':'canonical_worktree','production_rejection':'N36R3 owning state canonical worktree differs','tests_run':False,'source_changed':False,'checks_weakened':False}
from scripts.qd_ed_n36_supervise import first_c0_boundary
assert first_c0_boundary(plan['episodes'][0]) and not any(first_c0_boundary(r) for r in plan['episodes'][1:])
extra['first_C0_only_boundary']={'status':'PASS','episode_key':plan['episodes'][0]['episode_key'],'required_disposition':'PAUSED_FOR_ROOT_G3'}
write('supplemental-checks-v1.json',extra)
# Recheck all prepared references and immutable snapshots after supplemental checks.
for k in ('runtime','runtime_closure','native_build','controller_semantics'):
 assert ref(plan[k]['path'])['sha256']==plan[k]['sha256']
for v in plan['expected_manifests'].values():assert ref(v['path'])['sha256']==v['sha256']
imm=read(OUT/'immutable-before-v1.json')
for group in imm.values():
 for v in group.values():assert ref(v['path'])==v
stop.check()
artifacts={str(p.relative_to(OUT)):ref(p) for p in sorted(OUT.rglob('*')) if p.is_file() and (p.name.endswith('.json') or p.name.endswith('.py') or p.name=='refresh-v1.log') and not p.name.startswith(('executor-','wrapper-'))}
remaining=[
 'Root must review the exact refreshed controller runtime/closure/evidence bindings; inherited 001346 semantics and deployed source hashes are unchanged, but this executor draft deliberately is not ROOT_REVIEWED. Refresh affected manifests/bindings after root-approved controller reference exists.',
 'Independent exact B5 must bind all admission.BINDINGS fields on candidate 21fc93e5667a83520401282d4ba8e945f954f99b and final controller/runtime/manifests; prior 001348 B5 covers only the old source.',
 'Root source/runtime adoption must bind that independent review and exact new bindings. Owner remains bee9f6a4703e9d5d802d6b8c7950b69beefac4c0; prior 001350 adoption is provenance only.',
 'Owning root must reconcile and adopt finite accounting under its transaction lock, preserving all three journal prefixes, 505 attempts and 75.52725286641478 GPUh, exact caps/protected reserves and 40-cell finite arithmetic. This read-only snapshot is not spendable authority.',
 'Root detached health-only release and fresh separately charged readiness must precede any episode release; enforce source/owner routing, STOP/deadline, idle-device/private-resource checks, bounded health reservations, no retries, and observed runtime/native/controller lifecycle evidence.',
 'Root detached production release can authorize first C0 only; mandatory terminal PAUSED_FOR_ROOT_G3 and actual same-process Main/native/controller/receipt/audit review are required before any later-cell continuation. Scientific validation/formal/ablation gates remain unmet.',
 'If older synthetic admission fixture is reused, tests/test_n36r3_admission.py:134 lacks canonical_worktree and fails the exact owning-state canonical-worktree gate. Source-edit authorization is absent here; fixture unchanged and no historical suite rerun.'
]
md='''CPU binding refresh completed for leaf 15.6, with release disabled.\n\nCandidate/source/scientific-source: `21fc93e5667a83520401282d4ba8e945f954f99b`. Owner remains `bee9f6a4703e9d5d802d6b8c7950b69beefac4c0`.\n\nAll 40 identities/manifests, SOURCE routing, deadline `2026-10-11T11:13:13Z`, and first-C0 mandatory G3 pause are preserved. Exact source (1,099 files), runtime inventory (3,300 files), closure (6,767 modules), native inventory, inherited controller semantics, and live owner-alias branch passed. One runtime file and one closure module were rebound.\n\nThe refreshed controller is a disabled draft: its unchanged turn 001346 semantics do not grant root approval for the new runtime. The production verifier correctly rejects it pending root review. Older `tests/test_n36r3_admission.py:134` lacks `canonical_worktree`; static blocker recorded, no fixture/source changes or test reruns. The accepted 44 repair tests were retained as prior evidence.\n\nOwner state, all three ledgers, source and old inputs remained unchanged. Ledger retains 505 attempts / 75.52725286641478 GPUh. No GPU/provider calls, children/agents, locks, adoption or release.\n\nRemaining: root controller rebinding review and manifest refresh, independent exact B5, root source/runtime adoption, locked finite accounting, detached health release and fresh charged readiness, then separately released first C0 and G3 review.\n\n`target_met: false`; `score: null`. Hash-bound commands, results, inputs, artifacts and requirements are in `report-v1.json`.\n'''
with (OUT/'report-v1.md').open('x') as f:f.write(md)
artifacts['report-v1.md']=ref(OUT/'report-v1.md')
write('report-v1.json',{'schema':'n36r3-leaf-15.6-binding-preparation-report-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_DISABLED_BINDING_PREPARATION_PENDING_ROOT_CONTROLLER_REVIEW_AND_B5','node_id':'15.6','role':'isolated CPU binding-preparation executor','authority':ref(OUT/'authority-v1.json'),'parent_plan':a['parent_plan'],'prior_adoption':a['prior_adoption'],'repair_acceptance':a['repair_acceptance'],'summary':checks['summary'],'checks':checks['checks'],'supplemental_checks':extra,'commands':[{'argv':['python',str(OUT/'build-refresh-v1.py')],'exit_code':0},{'argv':['python',str(OUT/'refresh-bindings-v1.py')],'exit_code':0,'log':ref(OUT/'refresh-v1.log')},{'argv':['python',str(OUT/'finalize-report-v1.py')],'status':'all_assertions_passed_before_report_write'}]+checks['commands'],'inputs':imm['parent_artifacts'],'artifacts':artifacts,'remaining_requirements':remaining,'cpu_threads':2,'wall_cap_seconds':900,'refresh_seconds':checks['seconds'],'gpu_authorized':False,'release_enabled':False,'source_adopted':False,'runtime_ready':False,'owning_accounting_adopted':False,'target_met':False,'score':None})
with (OUT/'report-v1.sha256').open('x') as f:f.write(ref(OUT/'report-v1.json')['sha256']+'  report-v1.json\n')
print(json.dumps({'report':ref(OUT/'report-v1.json'),'manifest_count':40,'target_met':False,'score':None}))
