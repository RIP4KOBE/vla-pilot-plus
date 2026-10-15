import json,hashlib,datetime as dt,os,sys
from pathlib import Path
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path.cwd()));os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
from scripts import qd_ed_n36_stop as stop,qd_ed_n36r3_admission as admission
O=Path(__file__).absolute().parent
load=lambda p:json.loads(Path(p).read_text())
def ref(p):
 p=Path(p);r=p.read_bytes();return {'path':str(p),'bytes':len(r),'sha256':hashlib.sha256(r).hexdigest()}
stop.check();checks=load(O/'checks-v1.json');follow=load(O/'delta-followup-v1.json');au=load(O/'authority-v1.json');plan=load(au['plan']['path'])
for r in [au['plan'],au['bindings'],au['controller_review'],au['terminal_reconciliation']]:assert ref(r['path'])==r
for r in checks['manifests']:assert all(ref(r['path'])[k]==r[k] for k in ('bytes','sha256'))
assert follow['status']=='PASS' and follow['consumer_result']=='PASS'
consumer=ref(O/'b5-review-v1.json');admission.independent_review({**plan,'b5_review':{k:consumer[k] for k in ('path','sha256')}})
findings=[
 {'id':'B5-1','classification':'PASS_PREPARATION','finding':'Authority byte counts and hashes match EXACT turn 001421 plan and bindings. All ten admission.BINDINGS values and 40 expected manifest references match. Source HEAD and all 1100 committed source file records verify at 4e632c3bf1afe682d9287a518e531e6f2a6eba42.'},
 {'id':'B5-2','classification':'PASS_PREPARATION','finding':'All 40 manifests independently recomposed through bridge._verify_manifest_bound: ten Dev tasks times C0/Q0/N34/N36, unchanged seeds/init/BDDL identities, 720 steps, 20 Hz, horizon 8, exclusive modes and control/candidate bindings. Source equals scientific_source. Protocol, protocol review, accounting and resource routing equal accepted 001413 bindings.'},
 {'id':'B5-3','classification':'PASS_PREPARATION','finding':'3300 runtime inventory file records, 6767 closure modules, generated Torch literal-content rule, qualified _cyutility alias rule, exact interpreter/distributions and 75 native libraries pass passive APIs. required_after exactly binds generated module, OSC, T5, SigLIP and _cyutility. No live loaded-module, mapped-native or worker receipt attestation is claimed.'},
 {'id':'B5-4','classification':'PASS_PREPARATION','finding':'001418 accepted repair changes only health caller comments, readiness admission ordering, and tests. Runtime inventory and closure each change only scripts.qd_ed_n36_healthcheck plus explicit runtime preparation metadata. Native build bytes and controller instance/semantics/source unchanged. 001421 ROOT_REVIEWED controller and all three deployed-source evidence references pass verify_semantics.'},
 {'id':'B5-5','classification':'PASS_PREPARATION','finding':'Readiness now requires finite ordered starts <= observed <= completed <= min(authority ends, now); preserves separate timestamps and all non-time evidence equality, exact source/runtime/terminal/probe/frame/provider and optional durable journal equality. Historical readiness remains explicitly non-current; no prior health replay.'},
 {'id':'B5-6','classification':'PASS_PREPARATION','finding':'owner_root verifies lexical owner study_worktree versus isolated SOURCE. Both STOP entries absent under lstat-based stop.check; deadline exactly 2026-10-11T11:13:13Z. Draft unfrozen, all phase flags false, no root authority or detached release. Production validate_plan rejects the unchanged draft as expected.'},
 {'id':'B5-7','classification':'PASS_PREPARATION','finding':'First task-0 C0 is the sole first_c0_boundary. Static supervisor and runner review confirms valid terminal is durably charged then PAUSED_FOR_ROOT_G3; restart reconciliation rejects later dispatch, health reserve cannot bypass pause, invalidity stops. No continuation override or G3 closure is issued.'},
 {'id':'B5-8','classification':'CONSUMER_FORMAT','finding':'admission.independent_review requires whole-object equality. b5-review-v1.json is the exact consumable record and passes that API using an in-memory view of the draft; report-v1.json is a detailed companion and MUST NOT be bound as plan.b5_review. No prepared plan or binding was altered.'}
]
future=[
 {'id':'ROOT-GOVERNANCE','classification':'FUTURE_RELEASE_BLOCKER_NOT_CPU_B5','detail':'New exact source/runtime adoption, current root accounting, finite budget authority and detached health/episode release are absent. 001413 adoption binds the prior source and cannot authorize this delta. Production parent attestation stays unexecuted until real governance; never synthesize governance to exercise it.'},
 {'id':'ACCOUNTING-DRIFT','classification':'FUTURE_ACCOUNTING_BLOCKER_NOT_CPU_B5','detail':'Bound 001419 snapshot reports 505 attempts and 75.53031173955723 GPU hours. preparation.ledger_snapshot/arithmetic and admission.validate_authority pin 75.52725286641478. Pure arithmetic(snapshot) independently rejects retained charge differs. Root must reconcile all charged health and three current owner journal prefixes and address fixed admission/preparation arithmetic before release. This review did not read live owner ledgers or establish current headroom.'},
 {'id':'FRESH-HEALTH-IDENTITY','classification':'FUTURE_HEALTH_REQUIREMENT_NOT_CPU_B5','detail':'Create an authorized fresh permitted health identity/accounting path and genuinely new charged health under current source/runtime after root governance. Current PREPARATION_ID is fixed; reserve rejects any reused resource_id across owner history. No arbitrary identity is accepted. Prior failed/charged health cannot be relabeled, replayed or treated as readiness. If resolving accounting/identity requires source changes, refresh every affected exact binding and obtain new B5.'},
 {'id':'PRODUCTION-ATTESTATION','classification':'FUTURE_UNKNOWN_NOT_CPU_B5','detail':'Actual governed production parent imports, full release/runtime-input validation, GPU/provider health, live generated/native/required_after/controller instance receipts remain unexecuted and unknown. Passive inventory success is not actual loaded-process or device evidence.'},
 {'id':'G3','classification':'MANDATORY_FUTURE_ROOT_PAUSE','detail':'After authorized fresh health and detached first-C0 release, pause at the first C0 terminal for root review of actual production source/runtime/controller/native/generated and audit evidence. No later cell or automatic recovery; continuation needs separately reviewed plumbing. CPU evidence never proves scientific success.'}
]
next_action='Root should reconcile and accept this exact preparation-only B5, binding b5-review-v1.json (sha256 '+consumer['sha256']+'), then address the retained-charge mismatch and fresh health identity under real root governance. Reconcile all three current owner journals and preserve all charges; issue exact source/runtime adoption and separate finite authorities only after those blockers are resolved. Any source/binding change requires refresh and a new exact B5. Only then execute governed production parent attestation and genuinely new charged health, followed by separately released first C0 and mandatory G3 pause. Do not dispatch from this draft.'
report={
 'schema':'n36r3-independent-b5-review-v1','decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE','independent_b5_disposition':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE','node_id':'15.6','role':'independent CPU reviewer, not coordinator','at':dt.datetime.now(dt.timezone.utc).isoformat(),
 **{k:plan[k] for k in admission.BINDINGS},'admission_BINDINGS':list(admission.BINDINGS),'worker_receipts_are_future':True,'release_enabled':False,'score':None,'target_met':False,'gpu_authorized':False,'source_adopted':False,'owning_accounting_adopted':False,'production_parent_attestation_executed':False,'deadline':plan['deadline'],
 'authority':ref(O/'authority-v1.json'),'exact_plan':au['plan'],'exact_bindings':au['bindings'],'consumer_review':consumer,'consumer_warning':'Use consumer_review as plan.b5_review; this detailed report has extra fields and does not satisfy whole-object admission equality.',
 'cpu_b5_blockers':[],'findings':findings,'future_requirements_and_execution_blockers':future,'next_root_action':next_action,
 'checks':checks['checks'],'delta_followup':ref(O/'delta-followup-v1.json'),'manifest_checks':checks['manifests'],'evidence_inputs':{**checks['inputs'],**follow['inputs']},
 'preserved_failures':[{'scope':'this review','detail':follow['initial_failure_preserved']},{'scope':'001419 accepted context','detail':'complete-bindings-v1 failed current accounting differs; fresh root reconciliation required; retained, not converted to current accounting PASS.'},{'scope':'001418 accepted context','detail':'57 passed with three nonfinite-probe exception expectation failures, followed by three corrected targeted passes. No final full green suite claimed or rerun.'},{'scope':'001334/001340 accepted context','detail':'Preserve F1-F4 fixture defects, historical containment incident, and accepted scoped test-only repair. No historical recursive audit or broad fixture rerun.'}],
 'commands_results':[
 {'command':'date -u; readlink -m; owner/data STOP existence; git rev-parse HEAD; then qd_ed_n36_stop.check()','result':'Both canonical STOP entries absent; exact source; deadline remains open. lstat API additionally rejects dangling symlinks.'},
 {'command':'rg/sed/cat bounded production consumer paths and selected review artifacts; git diff 4347951a..4e632c3 --stat / named production files','result':'Read-only static review. Initial exploratory references to absent qd_ed_stop.py, qd_ed_runtime_closure.py, qd_ed_n36_coordinator.py, qd_ed_n36_health.py and controller glob failed; resolved to actual n36_stop/n34_source/n36_supervise/n36r3_health consumers; no validation conclusion drawn from missing names.'},
 {'command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 CUDA_VISIBLE_DEVICES= /home/hynx/miniconda3/envs/vla-pilot/bin/python -B '+str(O/'review-cpu-v1.py'),'exit_code':0,'result':'All checks retained in checks-v1.json including one reviewer delta assertion failure and two expected release/accounting rejections.'},
 {'command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 CUDA_VISIBLE_DEVICES= /home/hynx/miniconda3/envs/vla-pilot/bin/python -B '+str(O/'delta-followup-v1.py'),'exit_code':0,'result':'Targeted metadata delta verification and real admission independent_review consumer PASS; original failed check preserved.'}],
 'review_tools':{n:ref(O/n) for n in ('review-cpu-v1.py','checks-v1.json','delta-followup-v1.py','finalize-report-v1.py')},
 'scope_limits':{'cpu_threads':2,'wall_cap_seconds':900,'start_at':'2026-10-10T11:27:39Z','no_gpu_provider_health_dispatch_release':True,'no_owner_state_or_ledger_writes':True,'no_prepared_binding_or_old_artifact_edits':True,'no_protected_results_credentials_foreign_study_or_prohibited_design_file_reads':True,'no_child_agents':True,'no_broad_test_reruns':True},
 'stop_final':{'paths':list(stop.STOP_PATHS),'lstat_absent':True,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat()},
 'scientific_conclusion':'Unknown. CPU preparation evidence never proves scientific success.'}
md='''# Independent B5 review — leaf 15.6

**PASS_PREPARATION_REQUIRES_ROOT_RELEASE** for exact source `4e632c3bf1afe682d9287a518e531e6f2a6eba42`.

`score: null`; `target_met: false`; `release_enabled: false`; `worker_receipts_are_future: true`.

Authority-bound inputs:

- Turn 001421 plan: `8ecb4baaf1f4bd9f7663ee39677c1388ab24106d08d90a5bcc7d176c22a2aad2` (419692 bytes).
- Turn 001421 bindings: `78747dc63384b884eded1ee5dc14451812999feb5a288479c1c4322ae31a0772` (391166 bytes).
- Controller review: `571f78eb9f64277b3b629369a8f033886705c23c5cdaaf8fe9388d3b34f049cb`.

All 40 expected manifests were independently recomposed and compared exactly. The 1100-file source closure, 3300-file runtime inventory, 6767-module closure, generated/alias rules, five required-after names, 75 native libraries and controller semantics passed passive production verifier APIs. Ten Dev tasks × four arms retain scientific identities, schedule, protocol and gates. Owner versus isolated SOURCE routing passes. Both canonical STOP entries are absent; the deadline remains **2026-10-11T11:13:13Z**.

The accepted readiness repair preserves finite ordered observation/completion times and non-time evidence equality. Relative to accepted 001413, only three committed files change; one runtime file/module changes plus explicit disabled preparation metadata. Turn 001421 changes only controller review, artifact destination and derived manifests relative to 001419. Native bytes and controller semantics are unchanged. Accepted 001334/001340 reviews are preserved without rerunning their suites.

## Exact consumer

Use [b5-review-v1.json](b5-review-v1.json), SHA-256 `'''+consumer['sha256']+'''`, as the future `plan.b5_review`. It contains exactly the schema, decision, all ten `admission.BINDINGS`, worker-future flag and disabled-release flag. The actual `admission.independent_review` API accepted it. [report-v1.json](report-v1.json) contains detailed findings and **must not** be supplied to that exact-equality consumer. No prepared plan was changed.

## Blockers and unknowns

There are **no unresolved CPU B5 preparation blockers**. Execution remains blocked:

- Root must provide new exact source/runtime adoption, current accounting and detached finite authority. Prior 001413 adoption is continuity only.
- The bounded 001419 snapshot reports **75.53031173955723 GPU hours**, while preparation arithmetic and admission pin **75.52725286641478**. The pure arithmetic API rejects it. Root must reconcile current journals and all charges, and resolve the fixed accounting contract. Current live ledgers/headroom were not inspected or certified.
- Fresh permitted health identity and charged health are still required. The fixed preparation identity cannot be replayed; arbitrary replacement identities are rejected. No old health was replayed or used as current readiness.
- Governed production parent attestation remains **unexecuted**, pending real governance. GPU/provider health and actual generated/native/required-after/controller worker receipts remain unknown.
- First task-0 C0 has a mandatory terminal **PAUSED_FOR_ROOT_G3** boundary; invalidity stops. Supervisor restart and health admission cannot bypass it. No continuation override is approved.

## Checks and preserved failures

[checks-v1.json](checks-v1.json) records individual API results and timings; [review-cpu-v1.py](review-cpu-v1.py) records exact calls. Disabled production admission and stale accounting rejection are expected future requirements, not preparation failures.

The first reviewer delta assertion incorrectly required preparation metadata equality. Its failure remains in the original checks. [delta-followup-v1.json](delta-followup-v1.json) verifies that metadata exactly against the new source record and historical runtime, with readiness/release disabled; all remaining delta checks pass. No binding was repaired or rewritten. Earlier 001419 accounting failure and 001418 partial test history remain explicitly retained; no broad reruns occurred. Native validation executed the exact passive manifest function via AST extraction to avoid importing Torch or loading native libraries.

Two-CPU affinity, hidden CUDA and bytecode-disabled Python were used for verification. Only this output directory was written. No GPU, provider query, runtime health, dispatch, release, source/accounting adoption, owner state/ledger write, child agent, protected result or credential access occurred. Initial missing navigation filenames were corrected to actual consumers and are recorded in the JSON report.

## Exact next root action

'''+next_action+'''

CPU evidence never proves scientific success.
'''
stop.check()
for name,data in [('report-v1.json',json.dumps(report,indent=2,allow_nan=False)+'\n'),('report-v1.md',md)]:
 with (O/name).open('x') as f:f.write(data)
assert load(O/'report-v1.json')['score'] is None
print(json.dumps({'report':ref(O/'report-v1.json'),'markdown':ref(O/'report-v1.md'),'consumer':consumer,'decision':report['decision'],'release_enabled':False},indent=2))
