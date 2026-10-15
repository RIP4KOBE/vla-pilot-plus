import datetime,hashlib,json,pathlib,subprocess
R=pathlib.Path.cwd();O=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001167/source-review')
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
a=json.loads((O/'authority-v1.json').read_text());refs={}
for k in ('implementation_report','root_review','protocol'):
 ref=a[k];actual=sha(ref['path']);assert actual==ref['sha256'];refs[k]={**ref,'hash_verified':True}
implementation=json.loads(pathlib.Path(a['implementation_report']['path']).read_text())
source=[]
for x in implementation['source_files']:
 p=R/x['path'];blob=subprocess.check_output(['git','show',a['candidate_source']+':'+x['path']]);actual=sha(p)
 assert actual==x['sha256'] and p.read_bytes()==blob
 source.append({'path':x['path'],'sha256':actual,'bytes':p.stat().st_size,'matches_candidate_git_blob':True,'matches_implementation_inventory':True})
assert git('rev-parse','HEAD')==a['candidate_source']
assert git('rev-parse','HEAD^')==a['source']
assert not git('status','--short','--untracked-files=no')
inspected={
 'core/qd_nonprogress_tangent.py':'Full file: independent memory, predicate, proposal, latch, origins, native writes.',
 'core/rdt_policy_steer.py':'Complete candidate diff; scoring/projection, config, lifecycle/descriptor hooks, prepare/apply/final-selection call sites and inherited source excerpts.',
 'main.py':'Complete candidate diff and execution-hook context.',
 'configs/config.yaml':'Candidate diff: mode off and null binding defaults.',
 'scripts/qd_ed_n36_native.py':'Full independent audit implementation.',
 'scripts/qd_ed_n36_arithmetic.py':'Full same-device score/descriptor/bounds/cell and sparse-parent reference.',
 'scripts/qd_ed_n36_lifecycle.py':'Full independent ordered lifecycle replay.',
 'scripts/qd_ed_n36_reference.py':'Full independent geometry/native encoding reference.',
 'scripts/qd_ed_n36_response.py':'Full physical-response join and Unknown denominators.',
 'scripts/qd_ed_n36_build.py':'Full external native manifest and mapped-library receipt implementation.',
 'scripts/qd_ed_n36_worker.py':'Full worker, auditor composition, CUDA identity and receipt binding; accounting/release not certified.',
 'scripts/qd_ed_n36_bridge.py':'Full arm/config/source/runtime composition.',
 'scripts/qd_ed_n36_runner.py':'Worker command/environment/receipt call path excerpts; no release/accounting verdict.',
 'core/qd_observed_jaw_approach.py':'Full inherited N34 fallback, packet and template association.',
 'core/qd_capture_dwell.py':'Inherited packet recognition, canonical cache, duplicate provenance, prepare/apply/close.',
 'core/rdt_libero_action_converter.py':'Decoder and native prefix encoder.',
 'core/qd_ed.py':'Descriptor/bounds/cells, archive ordering/occurrence snapshot, sparse parent allocation and seed.',
 'core/env_adapters/libero_adapter.py':'Native projection, executed action and pre-reset observation recording excerpts.',
 'core/qd_executed_quality.py':'Frozen provider expression template; recognizer references.',
 'scripts/qd_ed_n31_reference.py':'Full native-byte primitives and inherited reference context.',
 'scripts/qd_ed_n30_native.py':'provider_target source/AST/code-signature recognition.',
 'scripts/qd_ed_n34_source.py':'Source-record/loaded-module/runtime attestors and import/cache metadata checks.',
 'scripts/qd_ed_n34_native.py':'Inherited control audit entry, native assignment trust and observation joins.',
 'scripts/qd_ed_n34_worker.py':'Inherited worker/source attestation entry; N36 delegates control auditing.',
 'scripts/audit_decision_evidence.py':'Generic load/count, scoring/provider/candidate/parent/selection and execution coverage checks.',
 'scripts/qd_ed_final_runner.py':'child_environment implementation and bytecode environment references only.',
 'tests/test_n36_boundaries.py':'Identity/origin/full8/terminal/predicate/path/template/config fixtures; not rerun.',
 'tests/test_n36_integration.py':'Full synthetic policy/Main/auditor corruption fixtures; not rerun.',
 'tests/test_n36_compatibility.py':'Full six base-parity fixtures; not rerun.',
 'tests/test_n36_build.py':'Full synthetic library/maps negatives; not rerun.',
 'tests/test_n31_capture_dwell_integration.py':'Synthetic fixture construction/projection excerpts only; not invoked.',
 'docs/n36-cpu-implementation.md':'Full implementation scope/limitations documentation.',
 '.gitignore':'Ignored __pycache__ rule only.'}
inspected=[{'path':p,'sha256':sha(R/p),'scope':s} for p,s in inspected.items()]
findings=[
 {'id':'SR-01','severity':'HIGH / P1','status':'CONFIRMED_CPU_REPRODUCTION','title':'Loaded source hashes do not bind the executing Python code',
  'introduced_by':'Inherited attest_loaded limitation, used as N36 actual-code attestation.',
  'locations':[{'path':'scripts/qd_ed_n34_source.py','lines':'296-315'},{'path':'scripts/qd_ed_n36_bridge.py','lines':'105'},{'path':'scripts/qd_ed_n36_worker.py','lines':'37-68, 222-234, 249, 292-316'},{'path':'scripts/qd_ed_n36_runner.py','lines':'104, 130-132'}],
  'protocol_requirement':'Hash-bound actual loaded module/code/build identity; producer PASS flags cannot substitute for independently established execution provenance.',
  'evidence':'attest_loaded hashes module.__file__ on disk, not its live code or the bytecode used to import it. The worker spec/origin check also hashes only the .py. N36 source_paths excludes .pyc, and the launch does not enforce source-only imports. A synthetic standard SourceFileLoader imported a timestamp/size-valid stale .pyc while the .py retained its frozen SHA-256. The unchanged attest_loaded function, executed with an isolated one-module inventory, accepted that module although value() returned stale! rather than frozen. PYTHONDONTWRITEBYTECODE=1 was set during the reproduction; it does not prevent reading the cache.',
  'impact':'The reviewed source and actual policy/auditor/worker code need not coincide. Thus the current source/native receipts cannot discharge the explicit actual-code obligation even if every source hash and native library hash matches. No evidence that this happened in a real run is claimed.',
  'minimum_repair':'Make the released worker import path demonstrably independent of unverified bytecode from process startup, including auditor dependencies, or independently bind live executable code to compiled frozen source (with reviewed exceptions for wrappers/generated modules). Add a stale timestamp/size-cache negative demonstrating rejection or guaranteed execution of frozen source. Do not treat disabling bytecode writes alone as a repair.',
  'reproduction':'repro-v1.py loaded_code; original function body AST-extracted unchanged, inventory dependencies isolated. Not a full worker/release execution.'},
 {'id':'SR-02','severity':'MEDIUM / P2','status':'CONFIRMED_HELPER_REPRODUCTION_AND_CALLER_INSPECTION','title':'Archive geometry raw origins are never joined to their actual projection evidence',
  'introduced_by':'New N36 verify_assignment and archive geometry evidence path.',
  'locations':[{'path':'scripts/qd_ed_n36_arithmetic.py','lines':'66-77'},{'path':'scripts/qd_ed_n36_native.py','lines':'233-239'},{'path':'core/rdt_policy_steer.py','lines':'5088-5091, 5550-5593, 6704-6709'}],
  'protocol_requirement':'Exact actual projection/source-origin provenance, independent descriptor/archive replay, and rejection of corrupt required native telemetry.',
  'evidence':'verify_assignment accepts geometry.source_origins as reference inputs, casts them to candidate dtype, and checks only the resulting native trajectory. The caller supplies no projection_origin sequence/identity or raw-observation anchor and performs no separate raw-origin check. A synthetic bf16 batch passed, then still passed after just geometry.source_origins[0][0] changed from raw binary64 1.0 to 1.001 while projected_xyz, descriptors and cells stayed unchanged. Both raw values cast to bf16 1.0. The independent canonical scoring-origin checks do not reference this archive geometry field.',
  'impact':'Required raw provenance can be corrupted without invalidation. More generally, arithmetic consistency with an unbound descriptor origin does not prove that the descriptor came from the actual decision projection. The demonstrated perturbation does not change any native score, descriptor or action; no observed task error is claimed.',
  'minimum_repair':'Record and independently join each archive-descriptor projection to its ordered projection_origin events with decision/iteration/candidate identity, and require exact raw origin bytes as well as native casts/projection bytes. Bind those origins to the applicable cached physical observation where required by the observation contract. Add a cast-equivalent raw-origin corruption negative; retain exact comparisons and frozen arithmetic.',
  'reproduction':'repro-v1.py archive_origin; directly calls verify_assignment on a synthetic CPU tensor fixture. No full episode, provider, model or simulator invoked.'}
]
checks=[
 {'area':'Authority and source','result':'PASS','details':'All three supplied direct document digests match. Authority SHA is locally recorded only; no external digest supplied for authority itself. Candidate HEAD and first parent equal requested candidate/base; tracked worktree clean; all 29 reported changed-file hashes match actual bytes and candidate Git blobs.'},
 {'area':'Inactive controls','result':'PASS_BOUNDED_SOURCE_REVIEW','details':'Off/null defaults; N35 disabled by composition; no N36 object allocated unless enabled; C0/Q0/N34 candidate diff adds only inactive branches/metadata. Existing fp32/bf16 parity tests compare canonical/selected native bytes, RNG, compute and origin reads to base. This is synthetic parity evidence, not all-input or actual GPU parity.'},
 {'area':'Scientific lifecycle','result':'PASS_BOUNDED_SOURCE_REVIEW','details':'Independent N36 state; consume-and-clear at enter; all ten continuity fields plus adjacent step/distinct decision; exact transported direct-open origin; decoder/commit/full8 ordered action identity; terminal/truncation at any ack including 8 resets before completion; unguided/episode/stage/error reset paths; no N35 positive-close predicate or retained completed trajectory.'},
 {'area':'Predicate','result':'PASS_BOUNDED_SOURCE_REVIEW','details':'Committed fp32 promoted to binary64; explicit j-order sums followed by 0.01, xyz-order products/additions; finite nonzero p; exact dot<=0, no epsilon. Missing/nonfinite trigger data suppresses eligibility. No norm(d)>0 is required: d=0 intentionally qualifies.'},
 {'area':'Tangent and native bytes','result':'PASS_BOUNDED_SOURCE_REVIEW','details':'N34 normalized xyzw rotation/fsum and inclusive box; current jaw-centered error; min abs component xyz tie order; right-handed cross/hypot; a and b construction, four-plus/four-minus clipping; one command cast; exact native prefix writes preserving suffix/other channels and signed zeros; close branch wins; byte-identical proposal leaves ordinary slot15. Clipping/quantization do not license endpoint equality or collision claims.'},
 {'area':'Ten-update current-template schedule','result':'PASS_BOUNDED_SOURCE_REVIEW','details':'Frozen BoundaryLatch belongs to one decision. prepare is called before each ordinary update and selects that update actual archive best; source/alias provenance and best occurrence checked. apply replaces only slot15 after ordinary rollout, records ordinary other15/population and scores normally; ten opportunities then expiry. Initial16 plus ten16 remains176 canonical candidates/11 canonical score batches. Auxiliary trace scoring is separately retained (16 actual score batches/256 provider evaluations per recognized-provider guided decision).'},
 {'area':'Occurrence/archive/selection','result':'PASS_WITH_SR02_PROVENANCE_GAP','details':'Independent replay reconstructs origin by actual occurrence, preserves all identical-byte aliases, verifies selected occurrence against independently reconstructed archive snapshot, and prevents ordinary/detour aliases from rearming. Archive visits, stable reward/fingerprint ties, insertion sequence, source iteration, parent cell, seeded sparse allocations and final global-best bytes are checked through all rounds. Equal-content template matches require identical projection/reward/cost origins; ancestry is not used as origin. Descriptor raw-origin provenance remains SR-02.'},
 {'area':'Policy/Main integration','result':'PASS_BOUNDED_SOURCE_REVIEW','details':'Selection -> native-to-fp32 decode -> Main commit -> adapter executed_action/pre-reset outcome -> step_returned -> memory acknowledgement. Failures reset and rethrow. Existing Main fixtures cover hooks with observer on/off and step exception; no real Main/environment run in this review.'},
 {'area':'Whole-episode audit','result':'FAIL_PARTIAL','details':'Generic audit actually runs before dedicated N36 replay in the worker; it is not merely a supplied PASS flag. Dedicated audit requires all contexts/11 canonical batches/10 updates/10 allocations and decoder/commit/ack/reset events, independently recomputes path/lifecycle and rejects covered corruptions. 25 existing corruption fixtures retained. SR-02 is an uncovered corrupt-telemetry acceptance, and SR-01 limits trust in which audit code actually executed.'},
 {'area':'Physical response','result':'PASS_BOUNDED_SOURCE_REVIEW','details':'Selected exact detour occurrences are counted separately from full8 nonterminal completions. Response requires an adjacent same-identity boundary and available before/after geometry. Per-step raw EEF preserved; known and Unknown sum to selected-detour denominator. Terminal/no-next/identity-change remain Unknown; no interpolation/contact/task-success claim. Terminal identity-bound response is not synthesized; none executed here.'},
 {'area':'CUDA recomputation validity','result':'SOURCE_VALIDITY_ONLY_RUNTIME_UNVERIFIED','details':'verify_scores repeats deployed per-candidate 8x3 native multiply/cumsum/add, provider slice1:8 and frozen norm/weighted-square reduction on explicit device. verify_assignment repeats native projection, fp32 target-relative XY, quantile bounds and grid cells; parent allocation remains correctly CPU-seeded. Comparisons use dtype/shape/finite/native-byte equality, not tolerance or a CPU CUDA-scan model. Worker calls cuda:0 and checks actual UUID; N36 event device/dtype/version/build checked against recomputation, CPU receipt rejected. Source operation order matches inspected deployed code, but no actual CUDA result/kernel/path/performance attestation was performed.'},
 {'area':'External build and executable binding','result':'FAIL_ACTUAL_CODE_BINDING_SR01','details':'External hash-bound native_build inventory is required, metadata compared, loaded Torch/CUDA/driver paths checked against inventory before/after, unknown/deleted/missing required libraries reject; no observed inventory becomes its own anchor. No real inventory/loaded-binary attestation tested here. Mapped binary files plus module source hashes do not fix the live Python executable-code gap SR-01. CUDA build/runtime proof remains prospective.'},
 {'area':'Release/accounting','result':'OUT_OF_SCOPE','details':'Root separately reviews release/adoption/resource/accounting boundary; this report does not certify it or modify it.'}
]
tests=[]
for t in implementation['tests']:
 assert sha(t['log']['path'])==t['log']['sha256']
 tests.append({'iteration':t['iteration'],'summary':t['summary'],'exit_code':t['exit_code'],'log':t['log'],'log_hash_verified':True,'rerun_by_reviewer':False})
obligations=[
 'Repair and independently review SR-01 and SR-02 before treating the native/source audit as complete; add only targeted negatives, with no scientific retuning.',
 'Root release/accounting review, source adoption and externally frozen actual all40 manifests/runtime/checkpoint/cache/provider/controller/task/init/build closure remain separate gates; this report grants none.',
 'Materialize exact pinned dependencies in the adopted checkout and prove executing Python code as well as source paths and mapped native binaries match the reviewed release.',
 'On a separately authorized metered execution, demonstrate actual assigned-device CUDA projection/provider/descriptor/bounds/cells exact agreement. Any mismatch invalidates; no epsilon, CPU proxy or tolerance widening.',
 'Obtain whole-episode prospective actual offspring/parents/archive/final-occurrence/decode/commit/ack/physical-response evidence; no frozen later historical populations may substitute.',
 'Measure audit/source hashing/storage/runtime cost within frozen worker/cohort limits; CPU fixtures establish neither GPU feasibility nor throughput.',
 'Fresh matched C0/Q0/N34/N36 task outcomes and detour final survival/physical entry are Unknown. Required protected validation/formal and QD/ED ablations remain untouched and unreleased.'
]
command="CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -v -o "+str(O/'repro-v1.time')+' python '+str(O/'repro-v1.py')+' > '+str(O/'repro-v1.log')+' 2>&1'
artifacts=[{'path':str(O/f),'sha256':sha(O/f)} for f in ['repro-v1.py','repro-v1.log','repro-v1.time','repro-results-v1.json']]
report={'schema':'n36-independent-cpu-source-review-v1','node_id':'15.6','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'FAIL_SOURCE_AUDIT_GAPS_PARTIAL_SCOPE','verdict':'FAIL','score':None,'promotion':False,'target_met':False,
 'reviewer':'Independent bounded source reviewer; did not implement candidate; no further delegation or external model/provider call.',
 'candidate_source':a['candidate_source'],'base_source':a['source'],'worktree':str(R),
 'authority':{'path':str(O/'authority-v1.json'),'sha256':sha(O/'authority-v1.json'),'externally_supplied_self_digest':False},
 'verified_direct_references':refs,'source_verification':{'HEAD_matches':True,'first_parent_matches':True,'tracked_worktree_clean_before_and_after':True,'changed_files':source},
 'inspected_files':inspected,'findings':findings,'checks':checks,'existing_targeted_test_evidence':tests,
 'reviewer_reproduction':{'command':command,'exit_code':0,'cpu_user_seconds':1.14,'cpu_system_seconds':.24,'aggregate_cpu_seconds':1.38,'wall_seconds':1.45,'threads':2,'cuda_visible_devices':'','cuda_initialized':False,'artifacts':artifacts,'failures':[],'scope':'Two newly discovered concerns only; synthetic CPU tensors/files; no historical tensor replay, policy/provider/model/simulator execution or full worker launch.'},
 'unresolved_runtime_obligations':obligations,
 'scope_observance':{'source_writes':False,'commits':False,'adoption':False,'owning_state_checkpoint_tree_ledgers_modified':False,'other_studies_modified':False,'locks_acquired':False,'executors_dispatched':False,'gpu_calls':False,'simulator_calls':False,'provider_calls':False,'healthchecks':False,'protected_results_read':False,'historical_tensor_replay':False,'credential_files_read':False,'prohibited_design_read':False,'delegation':False,'superpowers_used':False,'artifacts_only_in_authorized_output':True},
 'conclusion':'The scientific lifecycle/proposal and inspected exact arithmetic structure are consistent with the reviewed protocol in this bounded source scope. Two confirmed audit/provenance gaps prevent an unqualified PASS. This is implementation/audit invalidity review, not scientific falsification, native execution attestation, efficacy or goal completion.'}
(O/'report-v1.json').write_text(json.dumps(report,indent=2)+'\n')
md=['# N36 independent CPU source review','', '**FAIL — two audit/provenance gaps; bounded source scope.** `score=null`, `promotion=false`, `target_met=false`.','',f"Candidate `{a['candidate_source']}`; base `{a['source']}`. I did not implement this candidate. No source changes, GPU/provider/simulator calls, historical tensor replay, delegation, adoption, locks or release actions occurred.",'','## Authority and source','',f"Authority SHA-256: `{sha(O/'authority-v1.json')}` (locally computed; no external self-digest supplied). All three direct document hashes match:",'']
for k,r in refs.items():md.append(f"- {k}: `{r['sha256']}` — [document]({r['path']}).")
md+=['','HEAD and parent match the requested commits. The tracked worktree was clean before and after. All 29 implementation-inventory source hashes equal actual candidate Git blobs. The JSON report records every hash and the precise inspected scope; unchanged large inherited files were inspected only where relevant.','', '## Findings','']
for f in findings:
 md += [f"### {f['id']} — {f['severity']}: {f['title']}",'',f['evidence'],'', '**Impact.** '+f['impact'],'','**Minimum repair.** '+f['minimum_repair'],'','**Source:** '+ '; '.join(f"[{x['path']}:{x['lines']}]({R/x['path']}:{x['lines'].split('-')[0].split(',')[0]})" for x in f['locations'])+'.','', '**Evidence scope.** '+f['reproduction'],'']
md+=['## Reviewed invariants','']
for x in checks:md += [f"- **{x['area']} — {x['result']}.** {x['details']}"]
md+=['','## Verification and limits','', 'Existing implementation test logs 01–10 were read and hash-verified, not rerun. Their intermediate failures remain preserved; later targeted results include 117 passed (05), 44 passed (07), 8 passed (09), and 29 passed (10). These runs overlap and are not summed into a unique-test claim. Source inspection, rather than producer PASS assertions, supports this review.','',f"The sole new reproduction used 1.38 aggregate CPU seconds, two threads, CUDA disabled; exit 0, CUDA uninitialized. [Script]({O/'repro-v1.py'}), [results]({O/'repro-results-v1.json'}), [log]({O/'repro-v1.log'}), [resource timing]({O/'repro-v1.time'}). No failed reproduction commands were discarded.",'','```sh',command,'```','', 'Actual CUDA recomputation is structurally appropriate: it repeats the deployed operation shapes/order on the designated device and uses exact native bytes. It has not been executed here. The external native-build inventory is a useful independent anchor, but neither CPU fixture success nor library filenames/hashes establishes the running Python code identity identified in SR-01. No arithmetic-tolerance weakening is proposed.','', '## Unresolved runtime obligations','']
md += ['- '+x for x in obligations]
md += ['','The two findings concern implementation/audit validity, not scientific falsification. No real detour survival, physical response, task outcome, performance, native execution, promotion or full-goal claim is made. Root release/accounting review remains separate.']
(O/'report-v1.md').write_text('\n'.join(md)+'\n')
print(json.dumps({'status':report['status'],'reports':[str(O/'report-v1.json'),str(O/'report-v1.md')],'findings':len(findings),'source_hashes_verified':len(source),'inspected_files':len(inspected),'tracked_worktree_clean':True}))
