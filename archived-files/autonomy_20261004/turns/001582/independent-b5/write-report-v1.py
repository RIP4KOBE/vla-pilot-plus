import json,hashlib,datetime as dt,os,subprocess
from pathlib import Path
out=Path(__file__).parent
root=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
def read(p):return json.loads(Path(p).read_text())
def ref(p):
 p=Path(p);return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
a=read(out/'authority-v1.json');prep=read(a['preparation_report']['path']);inputs=read(a['b5_inputs']['path']);plan=read(prep['roots']['plan']['path']);audit=read(prep['roots']['audit']['path']);passive=read(out/'passive-checks-v1.json');focused=read(out/'focused-runtime-incompatibility-v1.json')
now=dt.datetime.now(dt.timezone.utc);end=dt.datetime.fromisoformat(a['deadline'].replace('Z','+00:00'))
assert now<end and not any(os.path.lexists(p) for p in plan['stop_authority']['paths'])
assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==a['source']
assert not subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True).strip()
blockers=[]
for kind,identifier in [('runtime','B5-RUNTIME-STALE'),('runtime_closure','B5-CLOSURE-STALE')]:
 records=[x for x in focused['results'] if x['artifact']==plan[kind]]
 blockers.append({'id':identifier,'severity':'blocking_preparation','artifact':plan[kind],'finding':'Reused '+kind+' retains pre-G7 project-source fingerprints for three changed files; refreshed plan source binds different bytes.','evidence':records,'consumer':{'runtime':'scripts/qd_ed_n36_release.py:201 -> qd_ed_final_runner.verify_files','runtime_closure':'scripts/qd_ed_n36_release.py:180 -> qd_ed_n34_source.verify_runtime -> _runtime_file'}[kind],'compatibility_matrix_claim_rejected':kind+' cannot be reused byte-identically for this exact source.'})
report={
 'schema':'n36-independent-b5-report-v1','node_id':'15.6','at':now.isoformat(),'source':a['source'],'worktree':str(root),'decision':'FAIL','status':'INDEPENDENT_B5_FAIL_INCOMPLETE_AFFECTED_GRAPH','scope':'Exact-source independent semantic B5 of canonical refreshed disabled preparation; not a repeat source-lifecycle review.',
 'authority':ref(out/'authority-v1.json'),'preparation_report':a['preparation_report'],'b5_inputs':a['b5_inputs'],'accepted_source_review':inputs['accepted_source_review'],'independent_source_review':inputs['independent_source_review'],'roots':prep['roots'],
 'blockers':blockers,'graph_refresh_complete':False,
 'checks':{
  'passive_predicates':len(passive['checks']),'passed':sum(x['pass'] for x in passive['checks']),'failed':len(passive['failures']),'unique_direct_artifact_hashes_checked':len(passive['direct_hashes']),'focused_exact_predicate_rejections':6,
  'source':'HEAD exact and tracked clean; all 1110 inventoried file digests match; seven intervening paths are operational; changed files equal committed bytes; source/scientific_source identical throughout the 41 manifests and plan/audit roots.',
  'equivalence':'Unmodified AST scientific_equivalence validator passes against frozen scientific base; accepted turn001578 source review retained, not broadened.',
  'science':'Unmodified disabled audit validator passes; all40 task0..9 x C0/Q0/N34/N36 rows, original protocol/protocol-review/accounting refs, worker gates and limits retained. All41 old/new argv and resolved-config differences checked: only accepted source binding changes. Algorithm hashes retained. Complete10 each arm, N36>=max(5,C0,Q0,N34), final ablations and protected gates remain unproven.',
  'crossbindings':'Canonical final input/report roots agree; graph points to refreshed plan/audit/equivalence/inventory/engineering/all40 manifests. Declared document differences match actual differences; no obsolete affected document references in active roots. HOWEVER unchanged runtime leaves embed stale changed-source fingerprints, so the affected transitive graph is incomplete despite correct direct artifact hashes.',
  'protocol':'Frozen audit protocol and protocol review remain bound and unchanged. Engineering protocol acceptance is absent and was not fabricated.',
  'controller':'Current exact verify_semantics passes with the existing runtime/closure reference pair, controller source bytes match, and three deployed-source review refs are intact. This local schema pass cannot establish compatibility of stale runtime/closure leaves. Original source_commit is historical provenance only; no observed instance or physical gain certification.',
  'deployment':'Exact passive deployment/owner routing and both canonical STOP paths pass. Isolated engineering output root absent; no execution output or readiness was created.',
  'accounting':'Exact disabled accounting matches specification; all three retained ledger prefixes match bytes/digests. 506 attempts, failed/aborted charges, health costs, admission margin and protected reserves retained; no settlement/adoption.',
  'readiness':'Runtime explicitly has provider_ready=false, cuda_egl_verified=false, runtime_ready=false. No actual health/probe evidence exists in the prospective output root. These are expected future release gates, distinct from the stale-source preparation blockers.',
  'prior_failure':'Failed first refresh report, seal and difference diagnostic hashes verified and preserved; tuple/list normalization history retained.'},
 'evidence_refs':{'passive':ref(out/'passive-checks-v1.json'),'focused':ref(out/'focused-runtime-incompatibility-v1.json'),'passive_helper':ref(out/'passive-review-v2.py'),'focused_helper':ref(out/'focused-runtime-check-v1.py'),'helper_failure':ref(out/'helper-failure-v1.json'),'original_helper':ref(out/'passive-review-v1.py')},
 'review_schema':{'source_file':ref(root/'scripts/qd_ed_n36_engineering.py'),'consumer':'validate_authority lines 271-273','required_schema':'n36-engineering-independent-b5-review-v1','required_pass_decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE','binding_fields':['scope','accounting','audit_plan','engineering_manifest','source','scientific_source','scientific_equivalence','runtime','runtime_closure','native_build','controller_semantics','deployment'],'pass_artifact_written':False,'reason':'Current consumer only accepts an exact PASS object. No consumer-compatible PASS can truthfully be issued for this inconsistent graph; this report is the machine-readable FAIL.'},
 'reuse_assessment':{
  'runtime':'INCOMPATIBLE: /files/3294, /files/3296, /files/3298 bind old changed-source hashes and sizes.',
  'runtime_closure':'INCOMPATIBLE: modules scripts.qd_ed_n36_healthcheck, scripts.qd_ed_n36_runner, scripts.qd_ed_n36_worker bind old hashes. Contrary to matrix rationale this closure is not limited to external packages.',
  'native_build':'Unchanged expected build is reusable within passive scope; no native binary execution or hardware attestation performed.',
  'controller':'Underlying source-semantics findings unchanged; current runtime/closure refs and three review-evidence docs must be addressed transitively if their referenced hashes change, by the owning reviewer/root without inventing approval.',
  'scope_accounting_deployment':'Byte-identical and exact passive validators compatible with current source.',
  'prior_B5':'Read only for scope/schema context. Earlier source PASS does not transfer; no prior B5 adopted.'},
 'minimal_next_gate':{'action':'Owner arranges a bounded disabled artifact refresh for the stale runtime and runtime-closure entries, then a fresh exact-source B5 on new canonical roots. No source repair is indicated by these findings.','affected_references':['runtime files/3294,3296,3298 (hashes and sizes)','runtime_closure modules for the same three sources and runtime reference','controller_semantics runtime/runtime_closure bindings and scale_action/set_goal/wrapper_and_gripper review-evidence bindings, handled by their owner','all40 audit manifests, engineering manifest, audit view, disabled engineering plan, graph root','changed/reused matrix, graph edges, root index, final report/B5 input hashes and seals'],'preserve':['all original and failed records, including this FAIL','all40 scientific cells, thresholds, algorithms, configs and protocol','charges, unsettled costs, ledger prefixes, admission margin and protected reserves','disabled state; do not synthesize readiness, authority, adoption or root approval'],'subsequent_gate':'Only after a fresh B5 PASS may the coordinator consider separately authorized root protocol acceptance, source/accounting adoption and detached prospective health/episode releases, with fresh STOP/deadline/headroom and actual readiness checks.'},
 'retained_accounting':{'attempts':506,'gpu_hours':'75.60616276674473','margin_gpu_hours':'0.23357169027962','conservative_before_gpu_hours':'75.83973445702435','proposed_gpu_reservation_seconds':1900,'wall_seconds':2100,'protected_remaining_gpu_hours':{'validation':'24.2408240024308155','formal':'12.0'},'adopted':False},
 'retained_failed_preparation_attempt':prep['retained_failed_preparation_attempt'],
 'limitations':['No full release/runtime verifier execution, broad tests, Hydra recomposition, native library/model/provider execution or recursive historical provenance rebuild. Current preparation recomposition records inspected and independently compared statically.','Focused validation executed only the unmodified passive verify_files and _runtime_file predicates on the six conflicting entries.','Independent review establishes artifact failure, not scientific outcome. No protected validation/formal result or credential file read.'],
 'independence':{'implemented_candidate':False,'rebound_graph':False,'delegation':False,'semantic_B5_performed':True,'review_basis':'Independent exact-source passive predicates, content comparisons and focused runtime incompatibility checks; root direct-hash reconciliation was not treated as semantic B5.'},
 'stop_and_budget':{'STOP_absent':True,'deadline':a['deadline'],'deadline_remaining_seconds':(end-now).total_seconds(),'timeout_seconds':1200,'started_at':'2026-10-10T19:03:26Z','elapsed_seconds':(now-dt.datetime(2026,10,10,19,3,26,tzinfo=dt.timezone.utc)).total_seconds(),'CUDA_VISIBLE_DEVICES':''},
 'writes':{'directory':str(out),'new_artifacts_only':True,'source_edits':False,'commits':False,'owner_state_tree_ledger_writes':False,'source_or_accounting_adoption':False,'authority_grant':False},
 'release_enabled':False,'gpu_used':False,'model_provider_executed':False,'worker_receipts_are_future':True,'scientific_success':False,'target_met':False,'score':None,'original_goal_complete':False,
 'model_policy':{'required':'official current-login gpt-6-astra','execution':'Existing reviewer session only; no alternate account/API/Poe/model route used','credentials_opened':False,'authentication_revalidated':False}}
with (out/'report-v1.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
with (out/'report-v1.sha256').open('x') as f:f.write(ref(out/'report-v1.json')['sha256']+'  report-v1.json\n')
text='''# Independent B5: FAIL

Exact source: `b8d6b98164f24a599a9aa1fa6ce862b12cb2fcf6`.

The canonical refreshed preparation is internally inconsistent. Its source inventory correctly binds the new G7 code, but reused runtime and runtime-closure artifacts still bind the old hashes for:

- `scripts/qd_ed_n36_healthcheck.py`
- `scripts/qd_ed_n36_runner.py`
- `scripts/qd_ed_n36_worker.py`

Runtime fingerprints are at `/files/3294`, `/files/3296`, and `/files/3298`; closure fingerprints are under the corresponding `scripts.qd_ed_n36_*` module names. Exact recorded/actual hashes and sizes are in [focused-runtime-incompatibility-v1.json](focused-runtime-incompatibility-v1.json). Current unmodified passive consumer predicates reject all six entries. The matrix claims that these records can be reused byte-identically are therefore false. Direct root hashes being correct does not make the transitive source bindings complete.

Independent checks recorded 2,132 predicates: 2,130 passed and two compatibility checks failed, followed by six focused rejection confirmations. Exact disabled plan/audit/equivalence checks passed. The 1,110 inventoried source digests, all40 cells, 41 manifest deltas, frozen science, protocol, deployment, and retained ledger prefixes were checked. Controller semantics pass locally against the old reference pair, but their runtime/closure references and three root review-evidence bindings become affected when those records change.

The minimal next gate is a bounded owner-directed refresh of the stale runtime/closure leaves and their affected references, followed by fresh B5 on the new canonical roots. Preserve source, all40 cells, frozen thresholds, charges/reserves and every old record including the failed first refresh and this FAIL. Controller proof rebinding requires its owner; this review supplies no approval or adoption. No source edit is indicated by these artifact findings.

No PASS object was emitted: the current consumer accepts only an exact PASS schema. The machine-readable verdict is [report-v1.json](report-v1.json), sealed by [report-v1.sha256](report-v1.sha256). Existing disabled preparation, absent root approvals and unobserved readiness remain distinct from these preparation blockers. No GPU, native/model/provider execution, scientific result, source/accounting adoption, owner-state mutation, or authority grant occurred. Deadline and canonical STOP remain binding.
'''
with (out/'REPORT.md').open('x') as f:f.write(text)
print(json.dumps({'report':ref(out/'report-v1.json'),'human_report':ref(out/'REPORT.md'),'decision':'FAIL'},indent=2))
