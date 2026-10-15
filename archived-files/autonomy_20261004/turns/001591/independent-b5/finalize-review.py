from pathlib import Path
import json,hashlib,datetime,subprocess
O=Path(__file__).parent;B=O.parents[1]/'001588/attested-consumer-refresh';IP=B/'independent-b5-inputs-v1.json'
def rd(p):return json.loads(Path(p).read_text())
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
I=rd(IP);C=rd(O/'bounded-checks-v1.json');P=rd(I['roots']['plan']['path']);A=rd(I['roots']['audit']['path']);prior=rd(I['prior_B5_FAIL']['path']);EM=rd(I['roots']['engineering_manifest']['path']);old=rd(prior['roots']['engineering_manifest']['path']);edges=rd(B/'graph-edges-v1.json');checks=[]
fields=['argv','resolved_config','composed_config_sha256','expected_runtime','row']
checks.append({'check':'engineering scientific payload retained from prior FAIL roots','verdict':'PASS' if all(EM[k]==old[k] for k in fields) else 'FAIL','fields':fields})
docs={'plan':P,'audit':A,'engineering_manifest':EM,'controller_semantics':rd(I['roots']['controller_semantics']['path'])}
docs.update({k:rd(v['path']) for k,v in A['expected_manifests'].items()});verified={x['path']:x for x in C['verified_artifacts']};bad=[]
for edge in edges['edges']:
 parts=edge['location'].split('/');v=docs[parts[0]]
 for key in parts[1:]:v=v[key]
 r=edge['reference'];actual=verified.get(r['path'])
 if actual is None:actual=ref(r['path']);verified[r['path']]=actual
 if any(v[k]!=r[k] for k in ['path','sha256']) or any(actual[k]!=r[k] for k in ['sha256','bytes']):bad.append(edge['location'])
checks.append({'check':'all direct graph edges match source locations and actual endpoints','verdict':'PASS' if not bad else 'FAIL','edge_count':len(edges['edges']),'failures':bad})
# Exact affected files close both earlier B5 blockers and remain at committed bytes.
rt=rd(I['roots']['runtime']['path']);cl=rd(I['roots']['runtime_closure']['path']);root=Path.cwd();affected=[]
for name in ['healthcheck','runner','worker']:
 relative='scripts/qd_ed_n36_'+name+'.py';path=root/relative;actual=ref(path);committed=subprocess.check_output(['git','show',I['source']+':'+relative]);rr=next(x for x in rt['files'] if x['path']==str(path));cr=cl['modules']['scripts.qd_ed_n36_'+name]
 ok=hashlib.sha256(committed).hexdigest()==actual['sha256']==rr['sha256']==cr['sha256'] and actual['bytes']==rr['size_bytes']
 affected.append({'source':actual,'runtime_json_pointer':'/files/'+str(rt['files'].index(rr)),'closure_json_pointer':'/modules/scripts.qd_ed_n36_'+name,'committed_bytes_match':ok})
checks.append({'check':'prior stale runtime and closure defects resolved for all three affected source files','verdict':'PASS' if all(x['committed_bytes_match'] for x in affected) else 'FAIL','evidence':affected})
checks.append({'check':'final exact HEAD and tracked source unchanged','verdict':'PASS' if subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==I['source'] and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True) else 'FAIL'})
(O/'supplementary-checks-v1.json').write_text(json.dumps({'checks':checks},indent=2)+'\n')
assert all(x['verdict']=='PASS' for x in C['checks']+checks)
report={
 'schema':'n36-independent-b5-report-v1','node_id':'15.6','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source':I['source'],'worktree':str(root),'decision':'PASS','preparation_verdict':'PASS','status':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',
 'scope':'Independent bounded read-only CPU semantic review of exact turn001588 disabled preparation roots. No prior B5 PASS transfer, no dispatch or adoption authorization.',
 'b5_inputs':ref(IP),'roots':I['roots'],'root_controller_binding_attestation':I['root_attestation'],'preparation_report':I['preparation_report'],
 'accepted_source_review':I['accepted_source_review'],'independent_source_review':I['independent_source_review'],
 'prior_B5_FAIL':I['prior_B5_FAIL'],'prior_B5_FAIL_retained':True,'prior_PASS_transferred':False,'blocking_defects':[],
 'checks':{'independent_check_count':len(C['checks'])+len(checks),'passed':len(C['checks'])+len(checks),'failed':0,
 'direct_input_artifacts':64,'verified_artifacts_in_bounded_checks':166,'graph_edges_verified':len(edges['edges']),
 'binding_completeness':'All 64 directly sealed input artifacts match hash/size. All direct graph edges match consumer JSON locations and endpoint hashes. Exact changed/reused deltas independently compared; plan/audit/all40/engineering/controller current references agree.',
 'frozen_scientific_equivalence':'Exact production scientific_equivalence, disabled audit shape and engineering mapping predicates pass. All40 episodes, protocol/review/accounting, limits and worker gates equal prior sealed audit. All40 plus engineering argv, composed config digests, resolved configs and expected runtime payloads remain equal to prior B5 roots. Source inventory and source/scientific_source agree at the exact commit.',
 'controller_semantics':'Exact production verify_semantics accepts current ROOT_REVIEWED proof and its three refreshed deployed-source reviews. Root attestation hashes bind current runtime/closure/controller. Semantic payloads equal immediate prior reviewed evidence; only reference/lineage/attestation/timestamp/status and added null B5 metadata differ. Controller implementation bytes checked. In-memory negative status/runtime/rotation/coverage mutations rejected.',
 'controller_consumption_limit':'verify_semantics consumes status, runtime, source-module and three review_evidence refs. It does not itself validate added root_binding_attestation metadata or the proof runtime_closure field. This review separately checked those bindings and immediate lineage; metadata alone was not treated as approval. No native instance or measured physical gain certified.',
 'runtime_inventory_source':'Prior six stale entries now match current working and committed healthcheck/runner/worker bytes. Exact passive verify_files checked 3009 runtime entries under current worktree once; exact _runtime_file checked nine local closure modules. All 610 overlapping runtime/scientific inventory entries and nine closure/source records agree. The other 2399 runtime entries are third_party files, intentionally outside the scientific source list; no overlapping mismatch.',
 'ledger_and_reserves':'All three retained ledger prefixes independently hashed as opaque bounded bytes, without parsing protected results. Accounting equals frozen specification: 506 attempts, 75.60616276674473 GPU hours, 0.23357169027962 margin; protected remaining validation 24.2408240024308155 and formal 12.0 GPU hours unchanged. No settlement or adoption.',
 'failure_audit_behavior':'Static production inspection confirms worker acceptance follows generic evidence-completeness audit, profile/native audit, immutable evidence check and post-run source/runtime/native attestation. Exceptions persist INVALID receipts; parent requires verified terminal before valid journal publication, retains full overrun charges, leaves unknown/live processes unsettled, and disables automatic retries. No runtime failure path was executed.',
 'finite_plan':'One dev task0 C0 diagnostic episode, one healthcheck, no recoveries; 1800+40 episode seconds, 20+40 health seconds, 1900 GPU reservation and 2100 wall seconds including 200 root overhead. No pooling/promotion/scientific eligibility. Disabled plan and audit phase gates preserved.',
 'readiness':'Runtime provider_ready and cuda_egl_verified are false. These are deferred release gates, not represented as preparation completion.'},
 'resolved_prior_blockers':[{'id':'B5-RUNTIME-STALE','status':'RESOLVED_IN_CURRENT_ROOTS','evidence':affected},{'id':'B5-CLOSURE-STALE','status':'RESOLVED_IN_CURRENT_ROOTS','evidence':affected}],
 'retained_accounting':rd(I['preparation_report']['path'])['retained_accounting'],
 'retained_failed_preparation_attempt':I['retained_failed_preparation_attempt'],
 'outstanding_gates':[
 {'gate':'ROOT_PROTOCOL_ACCEPTANCE','satisfied':False},
 {'gate':'SOURCE_AND_ACCOUNTING_ADOPTION','satisfied':False},
 {'gate':'ACTUAL_RUNTIME_PROVIDER_CUDA_EGL_AND_NATIVE_READINESS','satisfied':False},
 {'gate':'DETACHED_PROSPECTIVE_HEALTH_AND_EPISODE_RELEASES','satisfied':False},
 {'gate':'FRESH_STOP_DEADLINE_BUDGET_AND_HEADROOM_AT_ANY_FUTURE_DISPATCH','satisfied':False},
 {'gate':'FUTURE_WORKER_RECEIPTS_AND_SCIENTIFIC_SUCCESS','satisfied':False}],
 'consumer_integration':{'consumer':'scripts/qd_ed_n36_engineering.py:267 validate_authority','required_schema':'n36-engineering-independent-b5-review-v1','required_decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE','binding_fields':['scope','accounting','audit_plan','engineering_manifest','source','scientific_source','scientific_equivalence','runtime','runtime_closure','native_build','controller_semantics','deployment'],'binding_values_location':'Exact hash-bound plan root in this report; no roots modified.','note':'This detailed report records the independent verdict. It is not itself the closed-schema operational review token expected by validate_authority, nor a detached release. Owner must handle exact review-artifact integration before any separately authorized release; do not point an operational b5_review at this richer report and assume acceptance.'},
 'evidence_refs':{n:ref(O/n) for n in ['bounded-checks-v1.json','supplementary-checks-v1.json','bounded-checks-attempt2-v1.json','helper-failure-v1.json','helper-diagnostic-v2.json','bounded-review.py','bounded-review-v2.py','bounded-review-v3.py']},
 'production_code_inspected':[{**ref(root/f),'relevant_lines':lines} for f,lines in [('scripts/qd_ed_n34_controller.py','46-78'),('scripts/qd_ed_n36_engineering.py','163-273,482-518,561-606'),('scripts/qd_ed_n36_release.py','163-215'),('scripts/qd_ed_n36_bridge.py','120-200'),('scripts/qd_ed_n36_runner.py','150-207'),('scripts/qd_ed_n36_worker.py','285-330,425-467')]],
 'limitations':['No full release/readiness verifier, native execution, GPU/CUDA initialization, provider probe, credentials, foreign study or protected validation/formal result reads.','No recursive historical provenance rebuild or broad test rerun. Prior exact-source implementation review retained as scoped source evidence, never as a transferred B5 PASS.','Hydra recomposition was not rerun: independently compared frozen argv/config payloads and hash-bound prior recomposition evidence; exact affected passive consumers executed.','Unchanged external dependency/native inventory readiness was not re-probed. Preparation consistency does not establish deployment readiness.','Initial AST harness failures and overstrict comparison diagnostics retained; only reviewer-owned helper versions changed, never production predicates or input artifacts.','Existing untracked .cpu-test-artifacts/ reported by git status was not inspected or modified.'],
 'independence':{'implemented_candidate':False,'rebound_graph':False,'delegation':False,'semantic_B5_performed':True},
 'writes':{'directory':str(O),'source_changes':False,'state_checkpoint_tree_ledger_writes':False,'input_repairs':False,'release_or_adoption_writes':False},
 'skills':['/home/hynx/.codex/skills/arbor-research-agent/SKILL.md','/home/hynx/.codex/skills/arbor-agent-orchestrator/SKILL.md'],
 'dispatch_authorized':False,'release_enabled':False,'source_adopted':False,'accounting_adopted':False,'gpu_dispatch':False,'target_met':False,
 'worker_receipts_are_future':True,'scientific_success':False,'provider_executed':False,'credentials_accessed':False,'gpu_used':False
}
(O/'report-v1.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
R=ref(O/'report-v1.json');(O/'report-v1.sha256').write_text(R['sha256']+'  report-v1.json\n')
print(json.dumps({'decision':report['decision'],'checks':report['checks']['independent_check_count'],'report':R,'flags':{k:report[k] for k in ['release_enabled','source_adopted','accounting_adopted','gpu_dispatch','target_met']}},indent=2))
