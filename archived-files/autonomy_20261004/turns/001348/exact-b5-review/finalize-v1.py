import os, sys, json, hashlib, datetime, copy, subprocess
from pathlib import Path
OUT=Path(__file__).absolute().parent
ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
from scripts import qd_ed_n36_stop as stop, qd_ed_n36r3_admission as a
stop.check(need=30)
def ref(p):
    p=Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n')
    return ref(OUT/name)
checks=json.loads((OUT/'checks-v1.json').read_text())
assert all(c['status']=='PASS' for c in checks['checks'])
for path,digest in checks['read_bindings'].items():assert ref(path)['sha256']==digest,path
authority=json.loads((OUT/'authority-v1.json').read_text())
assert ref(OUT/'authority-v1.json')==checks['authority']
plan=json.loads(Path(authority['plan']['path']).read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==authority['source']
attestation={'schema':'n36r3-independent-b5-review-v1','decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',**{k:plan[k] for k in a.BINDINGS},'worker_receipts_are_future':True,'release_enabled':False}
b5=write('b5-review-v1.json',attestation)
candidate=copy.deepcopy(plan);candidate['b5_review']=b5
a.independent_review(candidate)
negative=[]
for key in a.BINDINGS:
    changed=copy.deepcopy(candidate);changed[key]=None
    try:a.independent_review(changed)
    except (ValueError,KeyError,TypeError):negative.append(key)
    else:raise AssertionError('consumer did not reject changed '+key)
base=OUT.parents[2]
preserved={
 '001334_source_review':ref(base/'turns/001334/admission-independent-review/report-v1.json'),
 '001340_fixture_acceptance':ref(base/'turns/001340/terminal-reconciliation-v1.json'),
 '001346_controller_review':plan['controller_semantics']}
source_names=['qd_ed_n36_prepare.py','qd_ed_n36r3_preparation.py','qd_ed_n36r3_admission.py','qd_ed_n36r2_admission.py','qd_ed_n36_contract.py','qd_ed_n36_bridge.py','qd_ed_n36_release.py','qd_ed_n36_supervise.py','qd_ed_n36_runner.py','qd_ed_n36r3_health.py','qd_ed_n36_worker.py','qd_ed_n36_source.py','qd_ed_n36_generated.py','qd_ed_n36_build.py','qd_ed_n34_source.py','qd_ed_n34_controller.py','qd_ed_n36_stop.py']
findings=[
 {'id':'B5-1','classification':'verified_preparation','finding':'Exact authority hashes and current bee9f6a4 HEAD agree. Full disabled envelope equals plan for all ten production BINDINGS and all forty manifest references. Source and scientific_source are identical; 1,098 files match committed blobs including pinned dependencies.'},
 {'id':'B5-2','classification':'verified_preparation','finding':'Forty independently recomposed manifests match byte-hash-bound JSON semantically, including argv, output routing, composed/resolved config, source/runtime/native/controller and expected runtime bindings. Ten Dev task identities and matched seeds/init/BDDL hashes remain exact; C0/Q0/N34/N36 task-major order and 10 baseline/30 development buckets are unchanged.'},
 {'id':'B5-3','classification':'verified_preparation','finding':'Runtime verifier passed 6,767 module origins/hashes, pinned interpreter and installed distribution metadata. Generated remote module has the fixed generator/template and prospective content hash; _cyutility has only the three qualified native targets. required_after is exactly remote module, robosuite OSC, T5, SigLIP and _cyutility. Native pure validator passed all 75 library paths/hashes. This is prospective inventory evidence, not loaded worker evidence.'},
 {'id':'B5-4','classification':'verified_preparation','finding':'001346 ROOT_REVIEWED deployed controller proof and three evidence bindings pass the actual verify_semantics API for this runtime and required_after OSC source. No physical gain is certified. Actual controller instance observation remains mandatory in the worker.'},
 {'id':'B5-5','classification':'consumer_contract_note_not_blocker','finding':'qd_ed_n36_prepare.prepare is an initial disabled-draft constructor; its N36R3 branch expects historical DISABLED_PENDING_ROOT_REVIEW inheritance, not the newer ROOT_REVIEWED proof. The bounded 001347 refresh correctly replaces the proof and recomposes manifests through bridge APIs. Do not rerun the historical constructor against the reviewed proof. qd_ed_n36r3_preparation.prepare is an older authority-bound review-package builder with ledger snapshot requirements, not a B5/adoption/release consumer. Neither constructor was executed.'},
 {'id':'B5-6','classification':'consumer_contract_note_not_blocker','finding':'bindings.disabled-v1.json is a preparation envelope, not the exact independent-review object accepted by admission.independent_review. The separate b5-review-v1.json created here has exactly the production schema/decision/ten BINDINGS/future-receipts/disabled-release keys. Actual consumer accepts it on an in-memory copy of the exact plan and rejects mutations of every BINDINGS field. Original prepared files are unchanged.'},
 {'id':'B5-7','classification':'verified_routing_and_veto','finding':'Lexical owner stays the private study_worktree; isolated SOURCE is the bee9f6a4 implementation_worktree. N36R2 owner adapter delegates N36R3 to the exact lexical owner check. Runner and health paths reserve under owner runner/state locks, with no source-checkout accounting substitution. Both canonical STOP paths were checked; fixed deadline remains 2026-10-11T11:13:13Z. Actual release.validate_plan rejects this disabled draft.'},
 {'id':'B5-8','classification':'preserved_scientific_gates','finding':'Current refresh changes only controller_semantics, artifact_root and expected_manifests. Frozen protocol review retains complete10, N36>=5, N36>=C0/Q0/N34; complete-quadruple futility only, invalid/missing audit stop, unrun outcomes Unknown, all required final QD/ED ablations and protected validation/formal gates. No protected results inspected. No numeric outcome or scientific-success claim is made.'},
 {'id':'B5-9','classification':'mandatory_future_G3','finding':'Supervisor recognizes exact first row n36r3_dev_t00_c0_001314. A valid first-C0 terminal returns PAUSED_FOR_ROOT_G3 with no next row; invalid terminals stop. No plan-field override exists; additional groups fail. Health reserve also requires a next row, so health cannot bypass the pause. Production receipt consumer requires PID/boot/start/context, immutable before/after observations, compiled Main and monotonic execution, complete required_after, stable generated identity, native/generic/controller/CUDA audits and once-only charged terminal. No such evidence was fabricated or executed.'}
]
future=[
 {'id':'R1','stage':'before health release','requirement':'Root reviews and explicitly adopts exact source/runtime and this consumer-compatible B5 object. Construct separate new root artifacts; do not modify the reviewed 001347 draft/bindings/manifests. Match all ten BINDINGS in n36r3-source-adoption-v1 and bind independent_review. Any changed binding requires renewed review.'},
 {'id':'R2','stage':'before health reservation','requirement':'Root performs current owner state and three-journal reconciliation under normal locks, retaining accepted 505 attempts / 75.52725286641478 GPUh baseline and all legitimate later charges, unknown telemetry, retained margin, reservation reconciliation and protected reserves. Supply exact n36r3-owning-accounting-v1, finite authority and current prefix anchors. Historical draft current_headroom=null is intentional, not spendable authorization. This reviewer did not read or write owner journals.'},
 {'id':'R3','stage':'before first C0','requirement':'Separately hashed root health review/release and actual fresh assigned-idle GPU7/current official provider/CUDA/EGL evidence with durably charged successful health terminal; then distinct episode review/release binding that readiness. Existing provider_ready/cuda_egl_verified metadata is not fresh readiness. Both max 41 invocations and aggregate 1800 health seconds apply (60 seconds per full reservation); no retries. No health, provider or GPU query was made here.'},
 {'id':'R4','stage':'after first C0, before later cells','requirement':'Mandatory real G3 review at PAUSED_FOR_ROOT_G3. Root reconciles actual Main lifecycle/receipts and charge, and separately reviews continuation plumbing; no continuation override is implemented. CPU fixtures and this B5 review cannot close G3.'},
 {'id':'R5','stage':'scientific success','requirement':'Original complete scientific, validation/formal and required-ablation evidence remains necessary under its own gates. CPU evidence never proves scientific success.'}
]
next_action='Root must review/hash-bind report-v1.json and the exact consumer-compatible b5-review-v1.json, then perform explicit source/runtime adoption for bee9f6a4703e9d5d802d6b8c7950b69beefac4c0 with the unchanged ten BINDINGS. Preserve 001334/001340/001346 acceptance. Next reconcile current owning state and all three journals under locks and create separate finite accounting/authority and detached health-review/release artifacts; do not dispatch from this draft. Fresh charged health readiness must precede a distinct first-C0 episode release, which must preserve the mandatory G3 pause.'
report={
 'schema':'n36r3-independent-exact-b5-report-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'node_id':'15.6','role':'independent CPU reviewer; not coordinator',
 'decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE','independent_B5_disposition':'PASS_EXACT_001347_PREPARATION_ONLY','source':authority['source'],
 'authority':checks['authority'],'plan':authority['plan'],'bindings':authority['bindings'],'b5_review':b5,'checks_evidence':ref(OUT/'checks-v1.json'),
 'preserved_reviews':preserved,'preparation_context':{n:ref(Path(authority['plan']['path']).parent/n) for n in ['report-v1.json','refresh-v1.py']},
 'source_consumers':{n:ref(ROOT/'scripts'/n) for n in source_names},'findings':findings,'blocking_preparation_defects':[],
 'release_blockers_intentionally_future':future,'next_root_action':next_action,
 'checks':checks['checks'],'exact_consumer_check':{'API':'scripts.qd_ed_n36r3_admission.independent_review','positive':'PASS on in-memory plan copy with new review ref','negative':'PASS: rejected each changed BINDINGS field','fields':negative,'prepared_plan_written':False},
 'commands_and_results':[
 {'command':'git rev-parse HEAD; bounded rg/sed/cat and JSON key selection over named current artifacts and exact source consumers','result':'HEAD matches bee9f6a4; no historical recursive audit. Initial globs for nonexistent controller/closure/receipt filenames returned rg errors; corrected to qd_ed_n34_controller.py, qd_ed_n34_source.py and qd_ed_n36_worker.py; no verification failure.'},
 {'command':'OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 CUDA_VISIBLE_DEVICES=\'\' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B '+str(OUT/'check-v1.py'),'script':ref(OUT/'check-v1.py'),'result':'exit 0; all 12 bounded checks PASS; no tests rerun'},
 {'command':'OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 CUDA_VISIBLE_DEVICES=\'\' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B '+str(OUT/'finalize-v1.py'),'script':ref(OUT/'finalize-v1.py'),'result':'All input hashes rechecked, positive exact B5 consumer and ten negative field checks passed before report write'}],
 'limits':{'wall_cap_seconds':900,'started_at':'2026-10-10T07:41:11Z','cpu_threads':2,'verifier_affinity':checks['cpu_affinity'],'deadline':c_deadline if False else stop.DEADLINE,'STOP_paths':list(stop.STOP_PATHS),'STOP_result':'both absent via fail-closed lstat check at verification and finalization'},
 'scope_compliance':{'GPU':False,'provider_query':False,'runtime_health':False,'dispatch':False,'release':False,'source_adoption':False,'accounting_adoption':False,'source_edits':False,'owner_state_or_ledger_writes':False,'owner_journal_reads':False,'protected_validation_or_formal_results':False,'prohibited_untracked_design_read':False,'credentials_or_foreign_study':False,'child_agents':False,'broad_test_reruns':False,'output_only_under':str(OUT)},
 'limitations':['Runtime/source/native checks establish static prospective bindings, not actual production loading or success.','Accepted earlier reviews are preserved, not rerun or recursively re-audited.','No current accounting headroom, idle-device availability, provider health or production G3 assertion.'],
 'score':None,'target_met':False,'release_enabled':False,'scientific_success':False,'worker_receipts_are_future':True}
stop.check()
rr=write('report-v1.json',report)
lines=['# Independent exact B5 review — leaf 15.6','', '**PASS_PREPARATION_REQUIRES_ROOT_RELEASE** for exact turn 001347 at `'+authority['source']+'`. No blocking preparation defect found. This is independent CPU review, not source adoption, release or scientific success.','',
 'Plan SHA-256: `'+authority['plan']['sha256']+'`  ', 'Bindings SHA-256: `'+authority['bindings']['sha256']+'`  ', 'Consumer-compatible B5: [b5-review-v1.json](b5-review-v1.json), SHA-256 `'+b5['sha256']+'`.  ', 'Detailed report: [report-v1.json](report-v1.json), SHA-256 `'+rr['sha256']+'`.','',
 'All 12 bounded CPU checks passed: 40/40 exact manifest recompositions, 1,098 committed source files, 6,767 runtime module records, fixed generated-source/native-alias rules, 75 native libraries, exact controller proof, routing, draft rejection, unchanged refresh fields, first-C0 predicate and standing deadline. The actual B5 consumer accepted the separate exact-schema artifact and rejected each of ten changed binding fields. See [checks-v1.json](checks-v1.json) and the hash-bound commands in the JSON report. No test suite was rerun.','']
for f in findings:lines += ['- **'+f['id']+' — '+f['classification']+':** '+f['finding']]
lines += ['', 'Preparation blockers: **none found**. The following remain mandatory future release/scientific requirements:','']
for r in future:lines+=['- **'+r['id']+' ('+r['stage']+'):** '+r['requirement']]
lines+=['','**Exact next root action:** '+next_action,'','Accepted 001334 source review, 001340 scoped fixture repair and 001346 controller review are preserved by hashes in the report. No prepared binding or old artifact was altered. Both canonical STOP entries were absent; deadline is **2026-10-11T11:13:13Z**. Review execution stayed CPU-only with affinity limited to two CPUs and within the 900-second cap.','', '`score: null`; `target_met: false`; `release_enabled: false`. CPU evidence never proves scientific success.','']
with (OUT/'report-v1.md').open('x') as f:f.write('\n'.join(lines))
print(json.dumps({'report':rr,'markdown':ref(OUT/'report-v1.md'),'b5_review':b5,'decision':report['decision']}))
