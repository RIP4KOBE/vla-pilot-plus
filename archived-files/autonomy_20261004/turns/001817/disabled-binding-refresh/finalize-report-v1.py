"""Finalize bounded executor packet. Does not create approvals or identities."""
import ast,datetime as dt,hashlib,json,os
from pathlib import Path
OUT=Path(__file__).resolve().parent
A=json.loads((OUT/'authority-v1.json').read_bytes())
def guard():
    assert not any(os.path.lexists(p) for p in A['stop_authority']['paths'])
    assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['stop_authority']['deadline'].replace('Z','+00:00'))
    assert (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat('2026-10-11T05:59:20+00:00')).total_seconds()<1200

def ref(path):
    path=Path(path);data=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
def short(r):return {k:r[k] for k in ('path','sha256')}
def load(r):
    actual=ref(r['path']);assert actual['sha256']==r['sha256']
    consumed[r['path']]=actual
    return json.loads(Path(r['path']).read_bytes())
def emit(name,value):
    guard()
    p=OUT/name
    with p.open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
    return ref(p)
guard()
R=json.loads((OUT/'refresh-result-v1.json').read_bytes())
consumed={r['path']:r for r in R['input_hashes']}
g=load(R['candidate_graph']);s=load(g['specification']);policy=load(g['policy']);closure=load(g['runtime_closure'])
identity=load(s['readiness_recovery']);contract=load(s['recovery_prefix_contract'])
# Bind just the direct authority leaves used by exact policy/recovery functions; no recursive traversal.
amendment=load(g['amendment']);scope=load(amendment['approved_prospective_scope'])
load(scope['authority']);load(s['runtime_binding']['repair_authority']);load(amendment['previous_runtime_amendment'])
load(contract['amendment']);load(contract['root_terminal_reconciliation']);load(contract['accepted_review'])
root=Path(A['worktree']);interpreter=closure['interpreter']
verify=['python','-B',str(OUT/'verify-artifacts-v1.py'),'--report',str(OUT/'report-v1.json')]
controller=load(g['controller_semantics'])
p3={
 'schema':'n36-disabled-controller-and-graph-review-prerequisites-v1','status':'PENDING_EXTERNAL_REVIEW','candidate_graph':R['candidate_graph'],
 'source_commit':R['source'],'source_record':g['source_record'],'runtime':g['runtime'],'runtime_closure':g['runtime_closure'],
 'final_source_review':short(A['root_review']),'source_placement':short(A['source_placement']),
 'controller_candidate':g['controller_semantics'],
 'required_controller_values':{**{k:controller[k] for k in ('schema','class','module','source','instance','semantics','source_commit','runtime','runtime_closure')},
     'status':'ROOT_REVIEWED','physical_gain_certified':False},
 'evidence_required':{key:{'kind':'deployed_source_review','runtime':g['runtime'],'fixture_only':False,
     'authorship':'Fresh independent/root source review; real hash-bound evidence reference required; executor supplies no attestation.'}
     for key in ('set_goal','scale_action','wrapper_and_gripper')},
 'exact_production_check':'scripts.qd_ed_n34_controller.verify_semantics(review_ref, candidate_runtime_ref, candidate_closure)',
 'bounded_review_command':verify+['--controller-proof','<ROOT_SUPPLIED_REVIEW_PATH>','--controller-sha256','<ROOT_SUPPLIED_REVIEW_SHA256>'],
 'command_values_unassigned':['ROOT_SUPPLIED_REVIEW_PATH','ROOT_SUPPLIED_REVIEW_SHA256'],
 'scope':'Review exact source/runtime/closure binding and deployed set_goal, scale_action, wrapper/gripper semantics. No measurement, controller instance or physical-gain assertion.',
 'remaining_graph_slots':[k for k,v in g.items() if v is None and k!='resource_id'],
 'final_graph_order':['Root settles P4 fresh disabled identity/recovery partition and final specification digest without release.',
     'Root supplies fresh exact controller evidence and acceptance for this runtime/closure; use bounded review command.',
     'Authorized builder binds affected plan/audit/full40 and separate engineering manifest, scientific equivalence and recovery references to final disabled specification/source/runtime; preserve immutable scientific inputs.',
     'Independent B5 and owning root review exact final graph hashes and full production verify_graph result. This candidate is neither an attestation nor accepted final graph.',
     'Only thereafter may root consider a separate finite preparation release and accounting adoption.'],
 'rebuild_warning':'If source/runtime/closure changes, controller evidence must be rebound/reviewed again. Do not reuse stale source-bound graph reviews.',
 'gpu_authorized':False,'release_enabled':False,'independent_review_claimed':False}
p3ref=emit('p3-review-prerequisites-v1.json',p3)
# Commands are explicit handoff templates. They are not run and supply no adopted values.
selection={'QD_ED_N36_R1_SPECIFICATION':'<JSON {path,sha256} OF ROOT_FINAL_DISABLED_SPECIFICATION>','PYTHONDONTWRITEBYTECODE':'1','GIT_OPTIONAL_LOCKS':'0','GIT_NO_LAZY_FETCH':'1'}
validate_code="import json,sys; from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_readiness_prepare as p; spec=e.specification(); p.policy(spec); release_ref={'path':sys.argv[1],'sha256':sys.argv[2]}; release=e.read(release_ref); source_ref=release['source_record']; source=e.read(source_ref); p.verify_graph(release,source,e.read(spec['canonical_runtime'])); p.validate_release(release_ref,spec,source,source_ref); print('PASS_GRAPH_AND_PREPARATION_RELEASE_VALIDATION_ONLY')"
p4={
 'schema':'n36-disabled-preparation-resource-release-prerequisites-v1','status':'UNASSIGNED_NOT_RELEASED','candidate_graph':R['candidate_graph'],
 'blocking_result':{'function':'scripts.qd_ed_n36_engineering_r1._recovery_specification','reason':'bound recovery policy successor',
     'actual_policy_resource_id':None,'historical_contract_successor':contract['successor']['resource_id'],'historical_reference_only':s['recovery_prefix_contract']},
 'root_owned_missing_values':['Fresh nonempty resource_id proven absent from complete attempt, health, reservation and preparation journals',
     'Fresh readiness_recovery identity reference and v2 recovery_prefix_contract with valid root reconciliation/review and exact accounting partition',
     'Final disabled specification, plan/audit/manifests and graph review hashes',
     'Finite issued_at, expires_at and gpu_seconds backed by current complete budget snapshot',
     'Detached accounting review, preparation accounting authority, owner adoption, detached measurement review and separate finite release'],
 'identity_rules':{'must_match':['policy.resource_id','readiness_recovery.resource_id','recovery_prefix_contract.successor.resource_id','accounting_authority.resource_id','release.resource_id'],
     'must_differ_from':['n36_healthcheck_engineering_r1_t00_c0_001616','n36_engineering_r1_t00_c0_001616',identity['resource_id'],*[p['resource_id'] for p in contract['predecessors']]],
     'kind':'readiness_preparation','automatic_retry':False,'unconsumed_at_draft':True,
     'occurrences_in_complete_ledgers':{name:0 for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl','readiness-preparation-ledger.jsonl')}},
 'lineage_value_already_repaired':policy['previous_specification'],
 'recovery_requirements':{'schema':'n36-failed-readiness-recovery-prefix-contract-v2','historical_predecessor_values_only':[
     {k:p[k] for k in ('resource_id','retained_charge_gpu_hours','retained_charge_gpu_seconds','provider_calls_retained','telemetry_complete')} for p in contract['predecessors']],
     'historical_subtotal_gpu_hours':identity['retained_charge_gpu_hours'],
     'current_complete_partition_not_verified':True,
     'requirement':'Root must account for every consumed/failed preparation including any later consumption of the old successor; retain raw byte segments and unknown telemetry charges. The two historical predecessor values are not asserted to be the complete current partition.',
     'preserve_original_offsets':s['retained_ledger_prefixes'],'root_observed_prefixes_at_authority':A['ledger_prefixes'],
     'original_snapshot_reference':s['retained_snapshot_reference'],'full_ledgers_required_for_budget_snapshots':True,
     'guard_functions':['_recovery_contract','_recovery_capture','_recovery_partition','preparation_budget'],
     'no_ledger_read_or_adoption_by_this_executor':True},
 'release_fixed_values':{'schema':'n36-preparation-measurement-release-v1','purpose':'readiness_preparation_only','source_record':g['source_record'],
     'baseline':s['canonical_runtime'],'source_cwd':str(root),'interpreter':interpreter,'provider_calls':1,'episode_authorized':False,'health_authorized':False,
     'runtime':g['runtime'],'cleanup_seconds':40,'policy_not_before':policy['not_before'],'measurement_not_before':s['runtime_binding']['measurement_contract']['not_before'],
     'deadline':policy['deadline'],'bounds':'max(policy.not_before, measurement.not_before) < issued_at <= now < expires_at <= deadline; 40 < gpu_seconds <= expires_at-issued_at; obey accounting/standing window and available headroom',
     'stop_authority_from':'scripts.qd_ed_n36_stop.binding() under owning authority; must still be clear',
     'root_review_schema':'n36-preparation-root-measurement-review-v1','accounting_authority_schema':'n36-preparation-accounting-authority-v1',
     'accounting_review_schema':'n36-preparation-accounting-root-review-v1','adoption_slot':'n36_preparation_accounting_adoption',
     'max_episode_attempts':0,'max_health_invocations':0,'automatic_recoveries':0,
     'retained_margin_gpu_hours':'0.23357169027962','absolute_gpu_hours':'224'},
 'current_candidate_paths':{k:v for k,v in policy.items() if k.endswith('_path')},
 'path_requirement':'Root must freeze distinct canonical absolute paths in final policy; pending paths are candidate values only. No release/proof/accounting/measurement files created here.',
 'commands_not_executed':[
     {'purpose':'After root supplies all prerequisite values: exact production recovery, graph and release validation; reads complete journals, no dispatch',
      'cwd':str(root),'environment':selection,'argv':[interpreter['path'],'-B','-c',validate_code,'<ROOT_REVIEWED_RELEASE_PATH>','<ROOT_REVIEWED_RELEASE_SHA256>']},
     {'purpose':'Only after separate root authorization, accounting adoption and successful review; this command performs measurement and is NOT authorized by this packet',
      'cwd':str(root),'environment':selection,'argv':[interpreter['path'],'-B','-m','scripts.qd_ed_n36_readiness_prepare','--release','<ROOT_REVIEWED_RELEASE_PATH>','--release-sha256','<ROOT_REVIEWED_RELEASE_SHA256>']}],
 'approved':False,'adopted':False,'resource_created':False,'release_enabled':False,'gpu_authorized':False,'provider_measurement_authorized':False}
p4ref=emit('p4-resource-release-prerequisites-v1.json',p4)
outputs={**R['outputs'],'refresh-result-v1.json':ref(OUT/'refresh-result-v1.json'),'p3-review-prerequisites-v1.json':p3ref,'p4-resource-release-prerequisites-v1.json':p4ref}
for name in ('refresh-artifacts-v1.py','verify-artifacts-v1.py','finalize-report-v1.py'):outputs[name]=ref(OUT/name)
report={
 'schema':'n36-disabled-binding-refresh-cpu-report-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'node_id':'15.6','role':'bounded CPU artifact executor; never coordinator',
 'status':'DISABLED_CANDIDATE_REFRESH_COMPLETE_PENDING_P3_P4','authority':ref(OUT/'authority-v1.json'),
 'source':R['source'],'scientific_source':R['scientific_source'],'worktree':str(root),'candidate_graph':R['candidate_graph'],
 'outputs':outputs,'input_hashes':list(consumed.values()),'boundary_manifest':R['boundary_manifest'],'validation':R['validation'],
 'changed_boundary_list':R['changed_boundary_list'],'unchanged_boundary_list':R['unchanged_boundary_list'],
 'result':'Affected disabled candidates refreshed at reviewed, placed f661a570. Exact prospective policy accepted; recovery and unreviewed controller fail closed at P4/P3. No source repair or placement remains in this executor scope.',
 'production_check_results':{'source_record':'PASS: 1117 committed source inventory files','policy':'PASS: exact production prospective composition',
     'specification':'EXPECTED_REJECTION: bound recovery policy successor','controller':'EXPECTED_REJECTION: reviewed controller semantics required',
     'closure':'PASS: exact production _runtime_file for canonical checkout modules and controller source; full external inventory scan deferred to final graph admission',
     'runtime':'PASS: exact canonical disabled projection','tracked_source':'PASS: clean final commit','full_graph':'NOT_RUN: missing reviewed controller, fresh recovery partition and dependent graph slots'},
 'commands_and_results':[{'argv':['python','-B',str(OUT/'refresh-artifacts-v1.py')],'returncode':0,'result':'DISABLED_CANDIDATE_REFRESHED','receipt':R['validation']},
     {'argv':['python','-B',str(OUT/'finalize-report-v1.py')],'result':'Creates this hash-bound prerequisite/report packet; no adoption'}],
 'remaining_gates':[{'id':'P1','status':'CLOSED_PREEXISTING','evidence':short(A['root_review'])},
     {'id':'P2','status':'CLOSED_PREEXISTING','evidence':short(A['source_placement'])},
     {'id':'P3','status':'CANDIDATE_READY_REVIEW_PENDING','prerequisites':short(p3ref)},
     {'id':'P4','status':'FRESH_IDENTITY_PARTITION_AND_SEPARATE_ROOT_RELEASE_REQUIRED','prerequisites':short(p4ref)},
     {'id':'scientific_promotion','status':'UNCHANGED_NOT_CLAIMED'}],
 'next_concrete_bounded_step':'Owning root reviews the hash-bound candidate and supplies fresh set_goal, scale_action and wrapper/gripper controller evidence for this runtime/closure. Complete root-owned fresh recovery/accounting partition before final dependent graph review. No source changes or placement.',
 'next_concrete_command':verify,'next_command_purpose':'Read-only packet hash and disabled-boundary verification; controller proof check command is in P3 prerequisites.',
 'graph_complete':False,'graph_verified':False,'source_adopted':False,'source_placement_performed':False,'source_edits':False,
 'gpu_authorized':False,'provider_measurement_authorized':False,'release_enabled':False,'owner_state_written':False,'checkpoint_writes':False,
 'ledger_reads':False,'ledger_writes':False,'driver_locks':False,'credentials_read':False,'protected_results_read':False,'prohibited_design_read':False,
 'subdelegation':False,'gpu_dispatches':0,'provider_calls':0,'fresh_preparation_resource_created':False,'independent_review_claimed':False,
 'historical_proof_eligible':False,'tests_rerun':False,'score':None,
 'route':'Existing current-login executor session only; no credentials/provider/client invocation or alternate account; no separate model/identity attestation fabricated.',
 'limits':'Unmodified production functions executed via AST with real dependencies. This is bounded CPU admission evidence, not imported full graph validation or root acceptance. Unchanged native/external inventories reused without a broad rescan.',
 'historical_preservation':'Prior partial graph, helpers, boundaries, failed checks and reviews remain untouched. Production-pinned old amendment review is historical scope provenance only; turn001816 is the final-source review.',
 'stop_check':{'stop_absent':True,'paths':A['stop_authority']['paths'],'deadline':A['stop_authority']['deadline'],'first_check_at':'2026-10-11T05:59:20Z',
     'elapsed_seconds':(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat('2026-10-11T05:59:20+00:00')).total_seconds(),'maximum_executor_seconds':1200}}
r=emit('report-v1.json',report)
print(json.dumps({'report':r,'status':report['status']}))
