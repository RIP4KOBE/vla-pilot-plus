import os,sys,json,hashlib,time,datetime as dt
from pathlib import Path
OUT=Path(__file__).parent;start=time.monotonic();A=json.loads((OUT/'authority-v1.json').read_text());sys.path.insert(0,A['worktree'])
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(r):
 actual=ref(r['path']);assert all(actual[k]==v for k,v in r.items());return json.loads(Path(r['path']).read_text())
def guard():
 assert not any(os.path.lexists(p) for p in A['STOP_paths'])
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['at'])+dt.timedelta(seconds=900)
def write(n,d):
 guard()
 with (OUT/n).open('x') as f:f.write(json.dumps(d,indent=2,allow_nan=False)+'\n')
 return ref(OUT/n)
guard();check=json.loads((OUT/'focused-check-results-v2.json').read_text());assert check['status']=='PASS' and check['blocker'] is None
pkg=read(A['inputs']['b5_input_package']);candidate=read(pkg['candidate_plan']);candidate_report=read(A['inputs']['candidate_report'])
# Check the immediate candidate reference graph only. Historical anchors remain leaves.
refs={str(Path(r['path'])):r for r in candidate_report['outputs'].values()};graph={p:set() for p in refs}
def edges(x,acc):
 if isinstance(x,dict):
  if 'path' in x and 'sha256' in x and x['path'] in refs:
   assert x['sha256']==refs[x['path']]['sha256'];acc.add(x['path'])
  for v in x.values():edges(v,acc)
 elif isinstance(x,list):
  for v in x:edges(v,acc)
for p,r in refs.items():
 data=read(r);edges(data,graph[p])
seen=set();active=set()
def visit(p):
 assert p not in active,'cyclic candidate graph'
 if p in seen:return
 active.add(p)
 for q in graph[p]:visit(q)
 active.remove(p);seen.add(p)
for p in graph:visit(p)
assert candidate['b5_review'] is None
expected_keys=('source','scientific_source','protocol','accounting','runtime','runtime_closure','native_build','controller_semantics','resource_routing')
assert pkg['review_inputs']=={k:candidate[k] for k in expected_keys}
assert pkg['required_external_record_schema']=='n36r2-independent-b5-review-v1'
assert pkg['required_external_decision']=='PASS_PREPARATION_REQUIRES_ROOT_RELEASE'
assert pkg['required_external_additional_fields']=={'worker_receipts_are_future':True,'release_enabled':False}
record={'schema':pkg['required_external_record_schema'],'decision':pkg['required_external_decision'],**pkg['review_inputs'],**pkg['required_external_additional_fields']}
b5ref=write('external-b5-review-v1.json',record)
from scripts import qd_ed_n36r2_admission as adm
# Only a local in-memory view is given a B5 ref; no final plan is created or frozen.
adm.independent_review({**candidate,'b5_review':{k:b5ref[k] for k in ('path','sha256')}})
guard()
prior=json.loads((OUT/'focused-check-results-v1.json').read_text())
checks=check['checks'];checks['candidate_reference_graph']={'status':'PASS','nodes':len(graph),'acyclic':True};checks['actual_independent_review_verifier']={'status':'PASS','function':'scripts.qd_ed_n36r2_admission.independent_review','external_record':b5ref,'candidate_mutated':False}
checks['future_receipt_and_release_semantics']={'status':'PASS_STATIC_SOURCE_REVIEW','full_native_runtime_model_byte_checks_required_at_production_release_and_admission':True,'worker_receipts_required_before_dispatch':False,'worker_receipts_required_before_attempt_acceptance':True,'process_binding':['pid','proc_start_ticks','boot_id','context','runtime_closure','phase'],'required_evidence':['source execution and loaded origins before/after','native build before/after','immutable hash-bound runtime observations before/after','controller instance','assigned actual CUDA UUID','generic and native arithmetic audits','parent terminal verification'],'readiness_is_release':False}
additional=[ref(OUT/'authority-v1.json'),ref(OUT/'focused-review-v1.py'),ref(OUT/'focused-review-v2.py'),ref(OUT/'finalize-review-v1.py'),ref(OUT/'focused-check-results-v1.json'),ref(OUT/'focused-check-results-v2.json')]
base=Path(A['inputs']['candidate_report']['path']).parent.parent
additional += [ref(base/'prepare-v1.py'),ref(base/'prepare-v2.py')]
for name in ['qd_ed_n36r2_admission.py','qd_ed_n36_release.py','qd_ed_n36_worker.py','qd_ed_n36_bridge.py','qd_ed_n34_controller.py','qd_ed_n34_source.py']:
 additional.append(ref(Path(A['worktree'])/'scripts'/name))
obligations=[
 'Coordinator must bind this external B5 record into the later final frozen plan. The final production plan must omit root_review and execution_release keys; this review does not create that plan.',
 'External root production review and caller-anchored detached execution release must follow; regenerate release-bearing worker contexts only afterward.',
 'Production release/admission must perform full native/runtime/model byte checks using the unmodified validators. Accepted unchanged evidence is reused in this bounded review; no large checkpoint rehash occurred.',
 'Under owner locks before each reservation/launch, recheck both STOP paths, deadline/window, private ACTIVE/PASS assignment, source/release bindings, GPU7 UUID/CUDA0/EGL4 exclusivity, provider readiness, fresh IDs/output paths, live ledgers and protected headroom. This review is point-in-time, outside those locks.',
 'Actual dispatched worker must create process-bound before/after source/runtime/native observations and controller/device/native arithmetic evidence. Parent must validate them before attempt acceptance/continuation. They cannot exist before dispatch; none was created or required here.',
 'Missing or invalid evidence retains charges and stops acceptance; unknown/live costs remain unsettled. Zero automatic recovery and unchanged scientific gates apply.'
]
result={'schema':'n36r2-independent-b5-report-v1','node_id':'15.6','at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'PASS','decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE','reviewer_role':'Independent B5 reviewer; did not implement candidate','authority':ref(OUT/'authority-v1.json'),'source_commit':A['base_source'],'candidate_plan':pkg['candidate_plan'],'b5_input_package':A['inputs']['b5_input_package'],'external_b5_record':b5ref,'score':None,'target_met':False,'release_enabled':False,'production_accepted':False,'root_production_review_created':False,'final_plan_frozen':False,'dispatch_performed':False,'worker_receipts_are_future':True,'future_worker_receipts_required_before_dispatch':False,'future_worker_receipts_required_before_attempt_acceptance':True,'future_worker_receipts_fabricated':False,'checks':checks,'blockers':[],'normalization_review':{'status':'PASS','initial_candidate_failure_preserved':read(A['inputs']['completion'])['preserved_initial_attempt'],'changes':['tuple to JSON list at resolved_config.qd_grid_shape','tuple to JSON list at resolved_config.qd_bounds_quantiles'],'all40_scalar_types_and_values_exact':True,'complete_config_hashes_equal_to_immediate_accepted_manifests':True,'note':'Candidate comparison artifact says normalization:null; the script/report disclose JSON normalization. Independent structural comparison confirms that only the two tuple/list representations changed and no scientific scalar changed.'},'review_harness_correction':{'preserved_attempt':ref(OUT/'focused-check-results-v1.json'),'reason':'Reviewer initially compared context.main_argv with complete manifest argv; actual worker verifier requires manifest argv[1:] because it excludes the Python executable. Corrected review harness only; source/candidate untouched. Full rerun passed all40.'},'evidence_hashes':check['evidence']+additional,'focused_cpu_checks':{'initial_attempt_wall_seconds':prior['wall_seconds'],'successful_attempt_wall_seconds':check['wall_seconds'],'initial_attempt_cpu_seconds':prior['cpu_seconds'],'successful_attempt_cpu_seconds':check['cpu_seconds'],'final_record_graph_verification_wall_seconds':time.monotonic()-start,'total_focused_wall_seconds':prior['wall_seconds']+check['wall_seconds']+time.monotonic()-start,'threads':2,'budget_seconds':120,'broad_tests':False},'retained_attempts':504,'retained_gpu_hours':75.49265038509455,'remaining_obligations':obligations,'verification_limits':['No new device, simulator, provider, network, credential or protected-result access.','No source/candidate edits, owner mutations, child agents, final plan, root production approval, detached release or dispatch.','Reused immediate accepted source/protocol/readiness/adoption evidence; did not recursively reconstruct historical provenance.','Runtime inventory, closure and native evidence inherited exactly except explicit reference/readiness metadata; full production byte verification not claimed here.'],'STOP_paths':A['STOP_paths'],'deadline':A['deadline']}
md='''Independent B5 review — continuing node15.6

**PASS_PREPARATION_REQUIRES_ROOT_RELEASE** for readiness-bound candidate-v2 on accepted source `30c6321715df86c5bab623db607bab2811aed56d`.

Score: null. target_met: false. release_enabled: false. No production acceptance or dispatch.

- Independently verified all 1088 frozen source files and all40 scientific configurations, fresh IDs, manifests and disabled contexts. Complete config hashes match immediate accepted inputs.
- The preserved initial candidate failure was tuple/list representation at `qd_grid_shape` and `qd_bounds_quantiles`. V2 changes only those representations; scalar types and values are exact in all40 cells. The comparison artifact's `normalization:null` is imprecise metadata, resolved by direct script and structural inspection.
- Runtime payload, closure inventory, native-build reference and controller semantics are inherited unchanged; readiness/adoption metadata and dependent hashes are correctly bound. External readiness is preparation evidence, not live admission or release.
- Protocol/accounting remain bound to accepted evidence. All three private journals retain exact hashes; fresh cohort IDs are absent. Retain504 attempts and75.49265038509455 GPUh, including both invalid charges. Full cohort reserves21 GPUh; remaining protected GPUh36.2408240024308155 and unprotected effective headroom88.1170008488933945. No automatic recovery.
- Candidate remains unfrozen and release-disabled, with release-null contexts; actual production validator rejects it. Immediate candidate graph is acyclic.
- The external B5 record uses the actual verifier's exact schema, nine review inputs, decision and additional fields. The unmodified `independent_review` accepted the written record via an in-memory candidate view. No candidate was edited.

Artifacts: [report JSON](report-v1.json), [external B5 record](external-b5-review-v1.json), [focused check results](focused-check-results-v2.json). Evidence hashes and all40 outcomes are in the JSON report.

The reviewer's first context check incorrectly included the Python executable. The actual worker requires `manifest.argv[1:]`; the corrected full check passed. Both attempts are retained. Focused checks used two CPU threads and stayed below120 seconds.

Coordinator duties remain: final frozen plan, separate root production review, detached release, regenerated contexts and locked admission. Full native/runtime/model byte checks remain mandatory at production release/admission. Actual process-bound before/after worker receipts and parent validation are mandatory before acceptance, never prerequisites before dispatch. No new device/provider access or large checkpoint rehash occurred.
'''
guard()
with (OUT/'report-v1.md').open('x') as f:f.write(md)
result['markdown']=ref(OUT/'report-v1.md');reportref=write('report-v1.json',result)
print(json.dumps({'status':'PASS','report':reportref,'markdown':result['markdown'],'external_b5_record':b5ref,'total_focused_wall_seconds':result['focused_cpu_checks']['total_focused_wall_seconds']}))
