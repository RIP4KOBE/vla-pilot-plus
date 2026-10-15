"""Bounded CPU candidate composition. No imports of production entrypoints."""
import ast, copy, datetime as dt, hashlib, json, os, subprocess, sys, time, types, math
from pathlib import Path
from decimal import Decimal
OUT=Path(__file__).resolve().parent
AUTH=json.loads((OUT/'authority-v1.json').read_text())
ROOT=Path(AUTH['worktree']); FINAL=AUTH['source']; SCIENCE='1065f38122379a515b60a9a424f574330405b66f'
START=time.monotonic(); SESSION_START=dt.datetime.fromisoformat('2026-10-11T06:34:00+00:00')
checks=[];inputs={};outputs={};boundaries=[]
os.environ['GIT_OPTIONAL_LOCKS']='0';os.environ['GIT_NO_LAZY_FETCH']='1';sys.dont_write_bytecode=True
# Reuse only bounded helper definitions from the hash-bound 001817 builder.
prior_report=json.loads(Path(AUTH['prior_disabled_report']['path']).read_text())
helper_ref=prior_report['outputs']['refresh-artifacts-v1.py']
assert hashlib.sha256(Path(helper_ref['path']).read_bytes()).hexdigest()==helper_ref['sha256']
helper_tree=ast.parse(Path(helper_ref['path']).read_bytes())
names={'sha','ref','read','bound','git','ast_functions','literal','canon','changes','delta_record','expected_reject'}
exec(compile(ast.Module(body=[x for x in helper_tree.body if isinstance(x,ast.FunctionDef) and x.name in names],type_ignores=[]),helper_ref['path'],'exec'))
def guard():
 assert (dt.datetime.now(dt.timezone.utc)-SESSION_START).total_seconds()<1150,'executor deadline'
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(AUTH['stop_authority']['deadline'].replace('Z','+00:00')),'authority deadline'
 assert all(not os.path.lexists(p) for p in AUTH['stop_authority']['paths']),'STOP'
def emit(name,value):
 guard();p=OUT/name
 with p.open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
 outputs[name]={**ref(p),'bytes':p.stat().st_size};return ref(p)
def check(label,fn):
 guard()
 try:
  result=fn();checks.append({'check':label,'result':'PASS'});return result
 except Exception as ex:
  checks.append({'check':label,'result':'BLOCKED','error_type':type(ex).__name__,'reason':str(ex)});return None

guard()
inputs[helper_ref['path']]=helper_ref
for k in ('root_review','diagnosis','prior_disabled_report'):bound(AUTH[k])
review=bound(AUTH['root_review']);repair=bound(review['report']);diagnosis=bound(AUTH['diagnosis'])
assert review['decision']=='ACCEPT_SCOPED_CPU_REPAIR_FOR_DISABLED_BINDING_PREPARATION'
assert git('rev-parse','HEAD')==FINAL
assert git('status','--porcelain','--untracked-files=no')==''
initial_status=git('status','--porcelain')
DEPLOY=ROOT.parent.parent/'n36_engineering_adapter_001482/implementation_worktree'
deployed_head=git('rev-parse','HEAD',root=DEPLOY)
graph_ref=prior_report['outputs']['graph.candidate-disabled-v1.json'];graph=bound(graph_ref)
old={k:bound(graph[k]) for k in ('specification','policy','source_record','runtime','runtime_closure','controller_semantics','amendment')}
spec0=old['specification'];contract0=bound(spec0['recovery_prefix_contract'])
RID='n36_readiness_preparation_recovery_001827'
ledger_bytes={};occurrences={}
for name,r in AUTH['ledger_prefixes'].items():
 data=Path(r['path']).read_bytes();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256'];ledger_bytes[name]=data
 # Strong byte-wide identity absence, not just selected parsed fields.
 occurrences[name]=data.count(RID.encode());assert occurrences[name]==0
 inputs[r['path']]=dict(r)
checks.append({'check':'all four complete ledgers match authority and candidate identity absent','result':'PASS','occurrences':occurrences})
w_ns=dict(Path=Path,hashlib=hashlib,json=json,subprocess=subprocess,os=os)
ast_functions(ROOT/'scripts/qd_ed_n23_worker.py',['require','sha','canonical_sha','read_ref','_source_git','_source_entry'],w_ns)
w=types.SimpleNamespace(**{k:v for k,v in w_ns.items() if callable(v)})
ns=dict(Path=Path,hashlib=hashlib,json=json,subprocess=subprocess,os=os,w=w,RDT='third_party/rdt',LEROBOT='third_party/lerobot',LIBERO='third_party/libero_pro',PINNED_SUBMODULES={'third_party/rdt':'scripts/maniskill_model.py','third_party/lerobot':'src/lerobot/__init__.py'},SOURCE_SUFFIXES=('.py','.yaml','.yml','.json'))
ast_functions(ROOT/'scripts/qd_ed_n34_source.py',['submodule_pin','submodule_paths','dependency_paths','_source_tree','_source_blobs','source_record','_runtime_file'],ns)
paths=[r['path'] for r in old['source_record']['files']]
assert not any('2026-08-10-eds-qd-stage-guidance-transition-design.md' in p or p.startswith('data/') for p in paths)
source=check('production source_record on reused 1117-file inventory at actual recovery checkout',lambda:ns['source_record'](ROOT,paths,commit=FINAL))
assert source is not None
source_ref=emit('source-record.json',source)
idx={x['path']:x['sha256'] for x in source['files']};oldidx={x['path']:x['sha256'] for x in old['source_record']['files']}
delta=git('diff','--name-only',old['source_record']['commit'],FINAL,'--').splitlines()
assert set(delta)=={'scripts/qd_ed_n36_engineering_r1.py','tests/test_n36_engineering_r1.py'}
assert {p for p in idx if idx[p]!=oldidx[p]}==set(delta)
placement=emit('source-placement-gate-v1.json',dict(status='OWNER_PLACEMENT_REQUIRED',actual_source_worktree=str(ROOT),actual_source_commit=FINAL,production_required_worktree=str(DEPLOY),observed_deployed_commit=deployed_head,required_commit=FINAL,placement_performed=False,source_adopted=False,reason='Production SOURCE and verify_graph require the adapter checkout. Candidate source evidence is from recovery checkout. Owner must separately place accepted commit then refresh source/runtime closure routes and review before release.',changed_files=[{'path':p,'before_sha256':oldidx[p],'after_sha256':idx[p]} for p in delta]))
runtime=copy.deepcopy(old['runtime']);runtime['preparation'].update(source=FINAL,source_record=source_ref)
baseline=bound(spec0['canonical_runtime']);baseline['preparation'].update(source=FINAL,source_record=source_ref)
assert runtime==baseline
assert runtime['provider_ready'] is runtime['cuda_egl_verified'] is runtime['preparation']['runtime_ready'] is False
runtime_ref=emit('disabled-runtime.json',runtime);delta_record('runtime',old['runtime'],runtime,graph['runtime'],runtime_ref)
closure=copy.deepcopy(old['runtime_closure']);closure['runtime']=runtime_ref
module_changes=[]
for name,row in closure['modules'].items():
 p=Path(row['path'])
 if p.is_relative_to(DEPLOY):
  rel=str(p.relative_to(DEPLOY));before=dict(row);row.update(path=str(ROOT/rel),sha256=idx[rel]);ns['_runtime_file'](row);module_changes.append({'module':name,'before':before,'after':dict(row)})
ns['_runtime_file'](closure['modules'][old['controller_semantics']['module']])
closure_ref=emit('runtime-closure.prospective-disabled-v1.json',closure);delta_record('runtime_closure',old['runtime_closure'],closure,graph['runtime_closure'],closure_ref)
checks.append({'check':'exact production _runtime_file for rerouted local modules and unchanged controller source','result':'PASS','limitation':'Static path/hash projection only; no loaded runtime attestation; external inventory reused.'})
amendment=copy.deepcopy(old['amendment']);amendment['source']=source_ref
amendment_ref=emit('amendment.prospective-disabled-v1.json',amendment);delta_record('amendment',old['amendment'],amendment,graph['amendment'],amendment_ref)
# Exact raw predecessor sequences are reused by hash, never rewritten.
predecessors=[]
for d in diagnosis['predecessors']:
 r=d['raw_sequence'];raw=Path(r['path']).read_bytes();assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256'];inputs[r['path']]=r
 rows=[json.loads(x) for x in raw.splitlines()];assert [x['event'] for x in rows]==d['events']
 predecessor={k:d[k] for k in ('resource_id','events','terminal_status','telemetry_complete','retained_charge_gpu_seconds','retained_charge_gpu_hours','provider_calls_retained')}
 predecessor.update(consumed=True,kind='readiness_preparation',raw_bytes=len(raw),raw_sequence={k:r[k] for k in ('path','sha256')},rows=rows,row_segments=[])
 for key,name,begin,end in [('own_journal','readiness-preparation-ledger.jsonl',d['own_start'],d['own_end']),('global_health_segment','gpu-healthcheck-ledger.jsonl',d['health_start'],d['health_end'])]:
  assert ledger_bytes[name][begin:end]==raw
  predecessor[key]=dict(path=AUTH['ledger_prefixes'][name]['path'],start_inclusive=begin,end_exclusive=end,sha256=r['sha256'])
 cursor=0
 for line,event in zip(raw.splitlines(keepends=True),d['events']):
  predecessor['row_segments'].append(dict(bytes=len(line),event=event,global_start_inclusive=d['health_start']+cursor,global_end_exclusive=d['health_start']+cursor+len(line),own_start_inclusive=d['own_start']+cursor,own_end_exclusive=d['own_start']+cursor+len(line),sha256=hashlib.sha256(line).hexdigest()));cursor+=len(line)
 predecessors.append(predecessor)
assert len(predecessors)==3
identity=dict(schema='n36-prospective-readiness-recovery-identity-v1',resource_id=RID,recovery_of=[p['resource_id'] for p in predecessors],retained_charge_gpu_hours=sum(p['retained_charge_gpu_hours'] for p in predecessors),source=FINAL,unconsumed_at_draft=True,automatic_retry=False,adopted=False,release_enabled=False)
identity_ref=emit('recovery-identity.prospective-disabled-v1.json',identity)
contract=copy.deepcopy(contract0)
contract.update(schema='n36-readiness-recovery-prefix-contract-v3',status='DISABLED_CANDIDATE_PENDING_ROOT_TERMINAL_RECONCILIATION',drafting_authority=ref(OUT/'authority-v1.json'),identity=identity_ref,predecessors=predecessors,root_observed_ledger_prefixes=AUTH['ledger_prefixes'],own_journal_at_draft=AUTH['ledger_prefixes']['readiness-preparation-ledger.jsonl'],accepted_review=None,root_terminal_reconciliation=None)
contract['successor'].update(resource_id=RID,occurrences_in_complete_ledgers=occurrences)
contract['read_semantics'][-1]='Retain exactly three predecessor raw sequences including completed/true third predecessor. No root reconciliation or acceptance is claimed; null review slots must be filled by owning root in a fresh candidate, without changing historical rows.'
contract_ref=emit('recovery-prefix-contract.prospective-disabled-v3.json',contract);delta_record('recovery_contract',contract0,contract,spec0['recovery_prefix_contract'],contract_ref)
historical_spec=literal(ROOT/'scripts/qd_ed_n36_engineering_r1.py','HISTORICAL_SPECIFICATION')
policy=copy.deepcopy(old['policy'])
for key in policy:
 if key.endswith('_path'):policy[key]=str(OUT/Path(policy[key]).name)
policy.update(disabled_runtime_path=runtime_ref['path'],previous_specification=historical_spec,resource_id=RID)
policy_ref=emit('preparation-policy.prospective-disabled-v1.json',policy);delta_record('policy',old['policy'],policy,graph['policy'],policy_ref)
spec=copy.deepcopy(spec0);spec.update(readiness_recovery=identity_ref,recovery_prefix_contract=contract_ref)
spec['runtime_binding'].update(amendment=amendment_ref,preparation=policy_ref,source_record_path=source_ref['path'],runtime_path=str(OUT/'pending-measured-runtime.json'))
spec_ref=emit('specification.prospective-disabled-v3.json',spec);delta_record('specification',spec0,spec,graph['specification'],spec_ref)
assert all(spec[k]==spec0[k] for k in spec if k not in ('readiness_recovery','recovery_prefix_contract','runtime_binding'))
controller=copy.deepcopy(old['controller_semantics']);controller.update(runtime=runtime_ref,runtime_closure=closure_ref,source_commit=FINAL)
controller_ref=emit('controller-semantics.pending-disabled-v1.json',controller);delta_record('controller_semantics',old['controller_semantics'],controller,graph['controller_semantics'],controller_ref)
e=types.ModuleType('scripts.qd_ed_n36_engineering_r1');e.__dict__.update(Path=Path,hashlib=hashlib,json=json,w=w,SPECIFICATION=spec_ref,HISTORICAL_SPECIFICATION=historical_spec)
for key in ('HEALTH_ID','HEALTH_KIND','EPISODE_KEY','JOURNALS','AMENDMENT'):e.__dict__[key]=literal(ROOT/'scripts/qd_ed_n36_engineering_r1.py',key)
ast_functions(ROOT/'scripts/qd_ed_n36_engineering_r1.py',['reference','read','exact','_recovery_json','_recovery_rows','_recovery_read','_recovery_specification','_recovery_contract','_recovery_predecessors','_recovery_capture'],e.__dict__)
p=types.ModuleType('scripts.qd_ed_n36_readiness_prepare');p.__dict__.update(e=e,Path=Path)
for key in ('SCHEMA','FIELDS','MEASUREMENT_CONTRACT'):p.__dict__[key]=literal(ROOT/'scripts/qd_ed_n36_readiness_prepare.py',key)
ast_functions(ROOT/'scripts/qd_ed_n36_readiness_prepare.py',['policy','closed'],p.__dict__)
package=types.ModuleType('scripts');package.qd_ed_n36_readiness_prepare=p;sys.modules['scripts']=package;sys.modules[p.__name__]=p
check('production readiness_prepare.policy',lambda:e.exact(p.policy(spec),policy,'candidate policy'))
check('production _recovery_contract (root reconciliation deliberately absent)',lambda:e._recovery_contract(spec))
check('production _recovery_specification (root reconciliation deliberately absent)',lambda:e._recovery_specification(spec))
captured=check('production _recovery_capture actual complete ledgers, no owner lock; optimistic byte recheck only',lambda:e._recovery_capture(contract,Path(AUTH['ledger_prefixes']['attempt-ledger.jsonl']['path']).parent))
assert captured is not None
parsed,tail,current=captured;assert not tail and not current
ctrl_ns=dict(w=w,math=math,FIELDS=literal(ROOT/'scripts/qd_ed_n34_controller.py','FIELDS'))
ast_functions(ROOT/'scripts/qd_ed_n34_controller.py',['verify_semantics'],ctrl_ns)
check('production verify_semantics pending controller',lambda:ctrl_ns['verify_semantics'](controller_ref,runtime_ref,closure))
# Full-ledger budget calculation only: never emit scientific outcome rows.
budget_ns=dict(math=math,require=w.require,BUCKETS=literal(ROOT/'scripts/qd_ed_final_runner.py','BUCKETS'),TERMINAL=literal(ROOT/'scripts/qd_ed_final_runner.py','TERMINAL'))
ast_functions(ROOT/'scripts/qd_ed_final_runner.py',['event_groups','budget_snapshot'],budget_ns)
snapshot=check('production budget_snapshot complete original ledgers',lambda:budget_ns['budget_snapshot'](parsed[e.JOURNALS[0]],parsed[e.JOURNALS[1]]))
assert snapshot is not None
caps=literal(ROOT/'scripts/qd_ed_n36_contract.py','CAPS')
protected=sum(max(0.,hours-snapshot['gpu_hours_by_bucket'][k]) for k,hours in caps['protected_gpu_hours'].items())
D=lambda x:Decimal(str(x))
seconds=sum((D(x['retained_charge_gpu_seconds']) for x in predecessors),Decimal(0))
weekly=D('53.08404692669838')+D(168);margin=D('0.23357169027962')
charged=D(snapshot['gpu_hours_consumed']);prot=D(protected)
arithmetic=dict(schema='n36-disabled-release-arithmetic-v1',release_enabled=False,source=FINAL,resource_id=RID,predecessor_seconds_decimal_terms=[str(D(x['retained_charge_gpu_seconds'])) for x in predecessors],predecessor_seconds_decimal_sum=str(seconds),predecessor_seconds_production_float_sum=sum(x['retained_charge_gpu_seconds'] for x in predecessors),predecessor_hours_production_float_sum=identity['retained_charge_gpu_hours'],predecessor_provider_calls_retained=3,complete_ledger_gpu_hours_consumed=snapshot['gpu_hours_consumed'],complete_ledger_gpu_healthcheck_hours=snapshot['gpu_healthcheck_hours'],complete_ledger_gpu_hours_by_bucket=snapshot['gpu_hours_by_bucket'],inflight_resource_count=snapshot['gpu_healthcheck_inflight'],running_attempt_count=snapshot['running'],protected_hours=protected,retained_margin_hours=str(margin),absolute_hours='224',weekly_hours=str(weekly),absolute_headroom_seconds=str((D(224)-charged-prot-margin)*3600),weekly_headroom_seconds=str((weekly-charged-prot-margin)*3600),finite_example_seconds=600,finite_example_timeout_seconds=560,cleanup_seconds=40,provider_calls=1,formula='need <= min(state.max_gpu_hours,224,221.08404692669838)*3600 - (consumed+protected+margin)*3600; 40 < need <= expires-issued; check all bucket caps and reservations with production preparation_budget',owner_state_not_read=True,reservation_ledger_reference=AUTH['ledger_prefixes'][e.JOURNALS[2]],limitation='Arithmetic is not admission: owner state cap/adoption, current reservations, STOP/time window, graph/reviews and preparation_budget remain mandatory. Full ledgers retain every charge; no protected scientific results opened.')
arithmetic_ref=emit('release-arithmetic-v1.json',arithmetic)
newgraph=copy.deepcopy(graph)
newgraph.update(specification=spec_ref,policy=policy_ref,amendment=amendment_ref,source_record=source_ref,runtime=runtime_ref,runtime_closure=closure_ref,controller_semantics=controller_ref,recovery_prefix_contract=contract_ref,readiness_recovery=identity_ref,resource_id=RID,source_placement=None,source_placement_gate=placement,final_source_review={k:AUTH['root_review'][k] for k in ('path','sha256')},prior_partial_graph={k:graph_ref[k] for k in ('path','sha256')},status='DISABLED_V3_CANDIDATE_PENDING_OWNER_GATES',recovery_identity_status='FRESH_ABSENT_FROM_FOUR_COMPLETE_LEDGERS_NOT_RESERVED',historical_accounting_only={'recovery_of':identity['recovery_of'],'retained_charge_gpu_hours':[p['retained_charge_gpu_hours'] for p in predecessors],'retained_charge_gpu_seconds':arithmetic['predecessor_seconds_production_float_sum']},actual_source_worktree=str(ROOT),production_required_worktree=str(DEPLOY))
graph_new_ref=emit('graph.candidate-disabled-v3.json',newgraph);delta_record('graph',graph,newgraph,graph_ref,graph_new_ref)
remaining=[dict(id='root_recovery_reconciliation',status='BLOCKED',step='Owner independently reviews exact three raw sequences and current terminal handles/prefixes, creates authentic reconciliation and accepted review, then emits fresh contract/specification dependent hashes. Null slots intentionally reject.'),dict(id='source_placement',status='BLOCKED',evidence=placement),dict(id='controller_review',status='BLOCKED',step='Fresh source/runtime/closure-bound set_goal, scale_action and gripper evidence plus actual root review; pending projection cannot certify loaded semantics.'),dict(id='complete_graph',status='BLOCKED',step='Rebind plan/audit/all40 and separate engineering manifest plus native/source closure and root graph review; reuse unchanged evidence only within original scope.'),dict(id='finite_release',status='NOT_AUTHORIZED',step='Separate accounting authority and detached review, owner adoption, finite release and independent root measurement review; run exact production graph, release and preparation_budget checks before dispatch.'),dict(id='pre_existing_parity_failure',status='RETAINED',evidence=review['report'],reason=review['parity_failure_disposition'])]
prereq=bound(prior_report['outputs']['p4-resource-release-prerequisites-v1.json'])
commands=copy.deepcopy(prereq['commands_not_executed'])
for c in commands:
 c['environment']['QD_ED_N36_R1_SPECIFICATION']='<JSON {path,sha256} OF OWNER_FINAL_SPEC_AFTER_RECONCILIATION_AND_PLACEMENT>'
 c['required_placement']=placement;c['executed']=False
commands_ref=emit('later-finite-release-commands-v1.json',dict(schema='n36-disabled-later-release-commands-v1',commands_not_executed=commands,candidate_specification=spec_ref,arithmetic=arithmetic_ref,remaining_gates=remaining,release_enabled=False,adopted=False,source_placement_authorized=False))
# End checks: unchanged complete ledgers, source HEAD/status and all directly read inputs.
for name,r in AUTH['ledger_prefixes'].items():assert Path(r['path']).read_bytes()==ledger_bytes[name]
assert git('rev-parse','HEAD')==FINAL and git('status','--porcelain')==initial_status
assert git('rev-parse','HEAD',root=DEPLOY)==deployed_head
boundary_ref=emit('boundary-manifest-v1.json',dict(schema='n36-disabled-v3-boundaries-v1',artifact_field_boundaries=boundaries,module_path_changes=module_changes,changed_source_inventory_paths=delta,unchanged=['science anchor '+SCIENCE,'all scientific/specification fields outside three prospective operational binding fields','canonical disabled runtime except preparation.source/source_record','native/external inventories; no broad scan or execution','all predecessor raw bytes/row order/charges; original ledger offsets and full budget inputs','all source/owner state/checkpoints/ledgers/prior artifacts/driver locks'],limitations=['Runtime keeps canonical adapter worktree and file routes; current accepted source exists in recovery checkout. Owner placement gate is open.','Root review/reconciliation null; no substitute attestations.','AST selected functions are exact; partial CPU checks do not constitute full imported graph or release admission.']))
validation_ref=emit('validation-results-v1.json',dict(schema='n36-disabled-v3-production-checks-v1',checks=checks,production_function_bodies_unmodified=True,predicates_stubbed=False,full_graph_validation=False,broad_tests_rerun=False,owner_lock_acquired=False,method='Reused 001817 bounded helpers, selected original production AST functions/constants and real hash readers. Actual complete ledger capture rechecks bytes optimistically; no owner synchronization or dispatch admission claimed.'))
report=dict(schema='n36-disabled-v3-binding-cpu-report-v1',at=dt.datetime.now(dt.timezone.utc).isoformat(),node_id='15.6',role='bounded CPU artifact executor, not coordinator',status='DISABLED_V3_CANDIDATE_COMPOSED_WITH_PRESERVED_BLOCKERS',source=FINAL,scientific_source=SCIENCE,worktree=str(ROOT),authority=ref(OUT/'authority-v1.json'),root_scoped_review=AUTH['root_review'],repair_report=review['report'],prior_disabled_report=AUTH['prior_disabled_report'],candidate_graph=graph_new_ref,validation=validation_ref,boundary_manifest=boundary_ref,arithmetic=arithmetic_ref,later_commands=commands_ref,outputs=outputs.copy(),input_hashes=list(inputs.values()),remaining_gates=remaining,commands_and_results=[dict(argv=['python','-B',str(OUT/'compose-v1.py')],result='DISABLED_V3_CANDIDATE_COMPOSED_WITH_PRESERVED_BLOCKERS',returncode=0,receipt=validation_ref)],predecessor_count=3,retained_preparation_seconds=631.4651556015015,fresh_candidate_occurrences=occurrences,changed_boundaries=[b['boundary'] for b in boundaries]+['source_record','recovery_identity','release arithmetic and prerequisite commands'],unchanged_boundaries=['science','source bytes and commits','original costs and prefixes','owner state/checkpoints/ledgers','prior artifacts','native and external inventory'],source_placement_performed=False,source_adopted=False,release_enabled=False,adopted=False,gpu_dispatches=0,provider_calls=0,source_edits=False,owner_state_written=False,checkpoint_writes=False,ledger_writes=False,driver_locks=False,subdelegation=False,protected_results_read=False,prohibited_design_read=False,credentials_read=False,independent_review_claimed=False,scientific_success=False,score=None,route='Existing current-login Codex executor session only; no model/provider/alternate account invocation or separate identity attestation fabricated.',stop_check=dict(paths=AUTH['stop_authority']['paths'],deadline=AUTH['stop_authority']['deadline'],stop_absent=True,session_start=SESSION_START.isoformat(),elapsed_seconds=(dt.datetime.now(dt.timezone.utc)-SESSION_START).total_seconds(),maximum_executor_seconds=1200),result='Exact three-predecessor disabled v3 candidate composed. Policy/raw capture/source checks pass; root recovery reconciliation, controller review, adapter placement and complete graph/release remain blocked. Pre-existing parity failure retained without broad retest.')
report['candidate_path_correction']=ref(OUT/'initial-canonical-path-correction-v1.json')
report['outputs']['initial-canonical-path-correction-v1.json']={**ref(OUT/'initial-canonical-path-correction-v1.json'),'bytes':(OUT/'initial-canonical-path-correction-v1.json').stat().st_size}
report['outputs']['compose-v1.py']={**ref(OUT/'compose-v1.py'),'bytes':(OUT/'compose-v1.py').stat().st_size}
emit('report-v1.json',report)
print(json.dumps({'status':report['status'],'checks':checks[-8:],'arithmetic':arithmetic,'report':ref(OUT/'report-v1.json')},indent=2))
