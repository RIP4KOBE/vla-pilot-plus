import pathlib,json,hashlib,datetime,subprocess
O=pathlib.Path(__file__).resolve().parent
A=json.loads((O/'authority-v1.json').read_text());G=pathlib.Path(A['report']['path']).parent
load=lambda p:json.loads(pathlib.Path(p).read_text())
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
E=load(O/'direct-evidence-v1.json');R=load(A['report']['path']);S=load(R['prospective_specification']['path']);P=load(R['prospective_policy']['path']);graph=load(R['graph']['path'])
scope=load(G/'scope.canonical-prospective-disabled-v1.json');account=load(G/'accounting.canonical-prospective-disabled-v1.json')
assert scope=={'schema':'n36-engineering-scope-v1','specification':graph['specification'],'scope':S['scope'],'release_enabled':False}
assert account=={'schema':'n36-engineering-accounting-v1','specification':graph['specification'],'accounting':S['accounting_proposal'],'retained_ledger_prefixes':S['retained_ledger_prefixes'],'retained_snapshot_reference':S['retained_snapshot_reference'],'release_enabled':False,'root_adopted':False}
V={
 'schema':'n36-recovery-binding-independent-review-v1',
 'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'node_id':'15.6',
 'review_only':True,
 'reviewer':{'role':'independent bounded CPU reviewer','route':'Existing official Codex session; no alternate provider or agent invoked','requested_model':'gpt-6-astra','credential_or_login_probe_performed':False},
 'authority':ref(O/'authority-v1.json'),
 'terminal_reconciliation':A['terminal_reconciliation'],
 'terminal_report':A['report'],
 'reviewed_source':A['source'],
 'direct_evidence':ref(O/'direct-evidence-v1.json'),
 'evidence_collector':ref(O/'collect-direct-evidence-v1.py'),
 'disposition':'ACCEPT_RECOVERY_INTENT_BLOCK_EXACT_PIN_ONLY_REPAIR_AND_GRAPH_ADOPTION',
 'exact_dispositions':{
  'canonical_artifact_integrity':'ACCEPT_AS_IMMUTABLE_PROSPECTIVE_DRAFTS_ONLY',
  'new_identity_and_retained_charge':'ACCEPT_DIRECT_ACCOUNTING_AND_NO_REPLAY_FINDINGS',
  'minimal_binding_amendment_in_principle':'ACCEPT_JUSTIFIED',
  'exact_minimal_follow_on_canonical_source_pin_diff':'BLOCK_AS_SUFFICIENT_OR_FINAL_REPAIR',
  'current_canonical_specification_as_final_post_commit_binding':'BLOCK_OCCUPIED_FIXED_OUTPUT_SLOTS',
  'graph_completion_readiness_execution_or_adoption':'BLOCK',
  'root_prospective_audit_freeze_under_standing_authority':'PERMITTED_AFTER_EXACT_INPUT_REVIEW_WITHOUT_RENEWED_USER_APPROVAL'},
 'reviewed_artifacts':{k:ref(G/n) for k,n in {
   'specification':'engineering-r1-spec.canonical-prospective-disabled-v1.json',
   'policy':'preparation-policy.canonical-prospective-disabled-v1.json',
   'source_pin_diff':'minimal-follow-on-canonical-source-pin.diff',
   'specification_diff':'specification.canonical-final.diff',
   'identity':'recovery-identity.prospective-disabled-v1.json',
   'source_record':'source-record.prospective-disabled-v1.json',
   'graph':'graph.canonical-incomplete-prospective-disabled-v1.json'}.items()},
 'findings':[
  {'id':'F1','status':'PASS_BOUNDED','subject':'Fresh identity and retained accounting',
   'detail':'n36_readiness_preparation_recovery_001723 differs from consumed n36_readiness_preparation_001651 and has zero occurrences in the directly bound attempt, health, reservation and preparation journals. The old readiness journal exactly equals the three-row global health suffix: reserved, dispatched, aborted. Terminal seconds 162.70163536071777 / 3600 = 0.045194898711310494 GPUh. Original ledger prefixes match; no reset, subtraction or replay is justified.',
   'runtime_guards':'validate_release binds the exact policy identity/specification/source; preparation_budget scans all attempt/resource/own events for identity reuse and checks full global snapshots plus protected headroom. New pending evidence/release/acceptance/measured-runtime paths are absent. Old proof/release cannot satisfy fresh path/hash and source/identity bindings. This is a bounded current snapshot, not a future admission token.',
   'evidence':['direct-evidence-v1.json:checks.retained_preparation','direct-evidence-v1.json:checks.ledger_bindings','scripts/qd_ed_n36_readiness_prepare.py:130-166,479-527']},
  {'id':'F2','status':'PASS_BOUNDED','subject':'Scientific, audit, provider and resource invariants',
   'detail':'Canonical specification changes only readiness_recovery metadata, preparation path/hash, measured-runtime path and source-record path. Scope, accounting proposal, retained prefixes/snapshot, canonical runtime, full audit requirements and AMENDMENT are equal to the active specification. Canonical scope/accounting exactly match production disabled projections under the proposed pin. Runtime differs from the immutable baseline only in preparation.source and preparation.source_record. Audit retains all forty original episode rows, limits, worker contract, deadline, protocol/review/accounting references. Closure changes only its runtime reference; native/deployment reused bytes remain bound.',
   'protected_reserves':{'caps_gpu_hours':{'validation':32.0,'formal':12.0},'historical_remaining_gpu_hours':{'validation':'24.2408240024308155','formal':'12.0'},'admission_margin_gpu_hours':'0.23357169027962'},
   'provider':{'backend':'codex_cli','auth_mode':'chatgpt','model':'gpt-6-astra','login_policy':'current_official_chatgpt_login'},
   'stop_authority':A['stop_authority'],
   'qualification':'Historical disabled accounting amounts are not a fresh available-budget certificate. Full current suffix charges, including the retained failed preparation, must still be charged at admission. No thresholds, protected results or scientific payloads were retuned or reevaluated.'},
  {'id':'F3','status':'PASS_BOUNDED','subject':'Source inventory projection',
   'detail':E['checks']['source_projection'],
   'qualification':'1116 metadata entries have the same path inventory as the directly bound d3225489 source record. Only readiness_prepare.py and its focused test hash changed, matching exact Git diff and current committed/working bytes. Canonical inventory digest and current HEAD/tree match. Unchanged entries, including the Poe launcher, were inherited without opening their contents. This does not claim a fresh full inventory/native/model validation.'},
  {'id':'F4','status':'PASS_BINDING_MECHANISM_BLOCK_FINAL_TARGET','subject':'Exact canonical source-pin semantics',
   'current':E['checks']['current_spec_pin'],'proposed':E['checks']['proposed_spec_pin'],
   'detail':'The one-line canonical diff applies cleanly in read-only git apply --check and names the correct reviewed bytes. Preserve AMENDMENT at scripts/qd_ed_n36_engineering_r1.py:38. The audit router compares the scope specification reference exactly; its injected audit object cannot override the source-pinned specification. Physical paths are required only where readiness pinned/resolve checks demand them; lexical external specification references remain valid and must retain their exact strings. The superseded preparation-policy.diff describes lexical drafts, not the final canonical policy.',
   'qualification':'A pin replacement is necessary, but the exact proposed target cannot support immutable post-commit regeneration at already occupied slots and does not resolve the retained-prefix defect below.'}
 ],
 'blocking_defects':[
  {'id':'B1','severity':'BLOCKING_FINAL_REPAIR','title':'Fixed post-commit source and disabled-runtime slots are already occupied',
   'evidence':{'source_record_path':S['runtime_binding']['source_record_path'],'disabled_runtime_path':P['disabled_runtime_path'],'existing_source_commit':A['source']['commit'],'validator':'scripts/qd_ed_n34_source.py:374-377; scripts/qd_ed_n36_engineering_r1.py:109-127'},
   'detail':'Committing even the one-line pin changes HEAD and the engineering_r1.py source hash. The existing source-record.prospective-disabled-v1.json records pre-pin 1c10f9dd, and runtime.canonical-prospective-disabled-v1.json hashes that record. Keeping these bytes fails current-source validation; replacing them breaks preserved artifacts and their reviewed hashes. Moving new records elsewhere without revising the precommitted specification/policy fails exact-path checks.',
   'required_correction':'Before the final source pin commit, create new versioned prospective policy/specification with fresh, canonical, currently nonexistent source-record and disabled-runtime slots (prefer a separate follow-on directory for every downstream slot). Freeze those paths, not future record hashes, then review and pin that new specification. Preserve all existing 001723 artifacts.'},
  {'id':'B2','severity':'BLOCKING_RECOVERY_TO_PRODUCTION','title':'Retained failed preparation is rejected as a foreign suffix under the new identity',
   'evidence':{'source':'scripts/qd_ed_n36_engineering_r1.py:554-589','reproduction':E['checks']['isolated_suffix_reproduction'],'old_global_health_prefix_bytes':114767,'current_global_health_bytes':119910,'retained_readiness_journal_bytes':5143,'retained_readiness_journal_sha256':'e8c6de14d4f184dfe26fd877fbb0dfb93ab727ee498c483e8d314846fbe1160f'},
   'detail':'The immutable parent prefix precedes the failed n36_readiness_preparation_001651 lifecycle. preparation_health_suffix allows only the current policy identity or sole engineering health identity after that prefix; the first retained old event therefore raises foreign resource identity/kind in strict suffix. Furthermore, exact(own, prep) compares the whole readiness journal including the old failure against only the new lifecycle. Merely skipping foreign rows or changing the identity cannot fix this safely. readiness_recovery metadata is currently not consumed by this validator.',
   'impact':'This is a later engineering admission/terminal-readiness blocker; it need not block disabled graph composition or new preparation budgeting itself. Resolve it before spending on a new preparation that cannot reach production admission.',
   'required_correction':'Add a narrowly scoped, fail-closed recovery-prefix branch in preparation_health_suffix, backed by a new directly hash-bound root reconciliation contract: exact predecessor identity and full terminal aborted row sequence, unchanged charge, mirrored journal/global suffix prefix bytes, and explicit successor identity. Validate and partition that exact prefix before the existing strict current-preparation/sole-health suffix. Compare full own journal with retained prefix plus current preparation; compare the current own suffix with current prep. Keep complete ledgers in every global snapshot and veto unknown, changed, unfinished, torn, replayed or reordered records. Preserve AMENDMENT and its historical baseline; do not enlarge its prefixes or silently rebase snapshots. No broad foreign-identity allowlist or arbitrary identity filtering.'},
  {'id':'B3','severity':'BLOCKING_GRAPH_COMPLETION','title':'Audit freeze and downstream evidence are incomplete',
   'detail':E['checks']['prospective_flags'],
   'required_correction':'Under standing authority, root may approve the prospective audit-only freeze after reviewing its exact inputs: audit frozen=true, dispatch_authority=false, release_enabled=false, all scientific phase permissions false. Engineering preparation plan remains frozen=false/release_enabled=false with authority and B5 null; runtime/provider readiness remains false. Regenerate all forty audit manifests and the separate engineering manifest, exact final-source scientific equivalence, and accepted fresh controller binding evidence/closure references. Retain unmodified audit/readiness validators. No renewed user approval is required.'}
 ],
 'circular_binding_analysis':{
  'acyclic_design_accepted':True,
  'detail':'The existing design avoids pinning a final source/runtime hash in source: source pins an immutable external specification; the specification fixes source/runtime output paths and an immutable baseline. Only after the final source commit is known are current source record and downstream hashes produced. The exact proposed v1 filenames prevent immutable regeneration, but fresh slots solve this without a fixed-point hash search.',
  'required_order':['Write and review new recovery-prefix contract and revised external policy/specification with unused canonical paths; no final commit/source/runtime digest in those upstream documents.','Apply the final scoped code repair and exact new specification pin, preserving AMENDMENT; commit, review and place source.','Write the final source record at the reserved fresh slot; project the disabled baseline onto that source; bind a refreshed closure.','Obtain source/runtime/closure-bound controller evidence, derive science-equivalence and disabled scope/accounting, freeze only the reviewed audit view, build all40 manifests, then bind that audit into the separate engineering manifest/plan.','Verify the complete disabled preparation graph with the production validators under appropriately bounded later authority, then handle detached preparation accounting/review/adoption and release separately.'],
  'identity_metadata_rule':'The 001723 identity source commit is historical draft provenance. Do not rewrite that upstream identity metadata to the future pin commit while pinning its hash through the specification; that would create a commit -> spec -> identity -> commit cycle. Bind final source in downstream records and detached attestations instead.',
  'preserve_old_artifacts':True},
 'bounded_next_step':{
  'kind':'CPU_ENGINEERING_REPAIR_AND_IMMUTABLE_ARTIFACT_REGENERATION',
  'recommendation':'Prepare a new exact recovery-prefix contract and v2 policy/specification with unused canonical slots; amend only engineering_r1.py to pin that specification and validate the exact retained recovery prefix, plus focused regression coverage in the existing allowlist. Commit/place/review once the upstream bytes are final, then regenerate downstream artifacts from that final commit. Root may separately authorize the audit-only freeze under existing standing authority. This reviewer makes no edits or adoption.',
  'focused_validation_for_follow_on':['Old consumed identity and altered/missing/torn/reordered predecessor records must reject.','Exact retained failed prefix remains fully charged; only the explicit new identity can proceed to existing one-use lifecycle validation.','Unknown extra identity, replay, unfinished predecessor, duplicate current lifecycle, or health preceding current accepted preparation must reject.','Fresh source/runtime path equality and hashes, revised source allowlist, source projection/scientific-equivalence and acyclic downstream bindings must pass.','Audit-only frozen=true with false dispatch/release; engineering bootstrap remains unfrozen/disabled; required graph evidence complete.'],
  'no_broad_test_rerun':True,
  'no_gpu_or_provider_authorization':True,
  'no_user_reapproval_gate':True},
 'authority_interpretation':{
  'no_active_cohort':'Direct terminal reconciliation reports live_handles=[]; no new runtime liveness claim or active-state mutation made.',
  'prospective_freeze':'Legitimate immutable audit composition under root standing authority after exact-input review; not live/provider readiness, scientific cohort release, or permission to execute.',
  'execution':'Separate finite preparation accounting authority, root review, owner adoption, exact release and predispatch STOP/deadline/headroom checks remain necessary. Later readiness proof acceptance, production adoption, independent final B5 and distinct health/episode gates remain separate. These are root workflow gates, not renewed user permission requests.'},
 'validation_summary':{'direct_hash_checks':len(E['reference_checks']),'failed_direct_hash_checks':0,'isolated_defect_reproduction':'foreign resource identity/kind in strict suffix','full_production_graph_verification_run':False,'broad_tests_run':False,'full_source_record_or_verify_source_run':False,'source_scope_accounting_projection_checks':True},
 'limitations':E['limits'],
 'graph_complete':False,'graph_verified':False,'runtime_ready':False,'provider_ready':False,'production_ready':False,'final_b5':False,'scientific_success':False,'target_met':False,'source_adopted':False,'root_adopted':False,'release_enabled':False,'gpu_authorized':False,'provider_measurement_authorized':False,'episode_authorized':False,'health_authorized':False,'owning_state_mutation':False,'source_edits':False,'commits_created':False,
}
root=A['source']['worktree'];assert subprocess.check_output(['git','-C',root,'rev-parse','HEAD'],text=True).strip()==A['source']['commit'];assert subprocess.check_output(['git','-C',root,'diff','--name-only','HEAD','--'],text=True).strip()==''
for p,expected in [(A['report']['path'],A['report']['sha256']),(R['prospective_specification']['path'],R['prospective_specification']['sha256']),(R['prospective_policy']['path'],R['prospective_policy']['sha256'])]:assert ref(p)['sha256']==expected
with (O/'review-v1.json').open('x')as f:json.dump(V,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
for name in ['review-v1.json','direct-evidence-v1.json']:
 r=ref(O/name)
 with (O/(name.removesuffix('.json')+'.sha256')).open('x')as f:f.write(r['sha256']+'  '+name+'\n')
print(json.dumps({'disposition':V['disposition'],'review':ref(O/'review-v1.json'),'direct_evidence':ref(O/'direct-evidence-v1.json'),'source_unchanged':True},indent=2))
