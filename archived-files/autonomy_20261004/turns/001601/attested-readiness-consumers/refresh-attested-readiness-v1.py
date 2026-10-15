from pathlib import Path
PREV=Path(__file__).absolute().parents[2]/'001598/readiness-binding-refresh'
HELPER=PREV.parents[1]/'001584/runtime-graph-refresh/refresh-runtime-v1.py'
exec(compile(HELPER.read_text().split("boundary();ck('initial STOP/deadline'")[0],str(HELPER)+'::utilities','exec'),globals())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
boundary();ck('initial STOP/deadline',True,START_AT.isoformat())
inputs[str(HELPER)]=ref(HELPER);inputs[__file__]=ref(__file__)
a=read(ref(OUT/'authority-v1.json'))
for v in a['inputs'].values():read(v)
ck('exact source and tracked clean',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True))
prior=read(a['inputs']['parent_report']);oldinputs=read(ref(PREV/'independent-b5-inputs-v1.json'))
oldplan=read(prior['roots']['plan']);oldaudit=read(prior['roots']['audit']);oldem=read(prior['roots']['engineering_manifest']);oldgraph=read(prior['roots']['graph'])
runtime=read(oldplan['runtime']);closure=read(oldplan['runtime_closure']);oldctrl=read(oldplan['controller_semantics'])
rtref=oldplan['runtime'];clref=oldplan['runtime_closure'];ctrlref=pair(a['inputs']['controller_semantics']);ctrl=read(ctrlref);att=read(a['inputs']['controller_attestation'])
ck('attestation scope',att['status']=='PASS_STATIC_BINDING_REFRESH_ONLY' and att['release_enabled'] is False and att['independent_B5_performed'] is False)
ck('exact attestation controller',att['controller_semantics']==a['inputs']['controller_semantics'])
ck('unchanged runtime and closure',ctrl['runtime']==rtref==att['runtime'] and ctrl['runtime_closure']==clref==att['runtime_closure'])
reviewed={**ctrl['review_evidence'],'controller_semantics':ctrlref}
for name,nr in reviewed.items():
 oldref=oldplan['controller_semantics'] if name=='controller_semantics' else oldctrl['review_evidence'][name]
 new=read(nr);old=read(oldref)
 entry=next(e for e in att['checks'] if e['proposal']['path']==oldref['path'])
 ck('root attestation covers '+name,entry['semantic_content_unchanged'] is True and entry['source_hashes_verified'] is True)
 ck('reviewed exact runtime '+name,new['runtime']==rtref and new['runtime_closure']==clref and new['release_enabled'] is False and new['b5_review'] is None)
 mapping[oldref['path']]=ref(nr['path'])
 matrix.append(dict(kind='controller:'+name,disposition='reused_supplied_root_reviewed',old=ref(oldref['path']),new=ref(nr['path']),attestation=a['inputs']['controller_attestation'],new_approval_issued=False))
for row in oldaudit['episodes']:
 key=row['episode_key'];r=oldaudit['expected_manifests'][key]
 changed('audit_manifest:'+key,r,'audit-manifests/'+key+'.json',rebind(read(r)),['/controller_semantics'])
audit=rebind(oldaudit);auditref=changed('audit_view',prior['roots']['audit'],'audit-view.disabled-v1.json',audit,['/controller_semantics','/expected_manifests'])
em=rebind(oldem);emref=changed('engineering_manifest',prior['roots']['engineering_manifest'],'engineering-manifest.disabled-v1.json',em,['/controller_semantics','/audit_plan','/audit_manifest'])
plan=rebind(oldplan);planref=changed('disabled_plan',prior['roots']['plan'],'engineering-plan.disabled-v1.json',plan,['/controller_semantics','/audit_plan','/engineering_manifest','/expected_manifests'])
helper=TURNS/'001582/independent-b5/passive-review-v2.py';s=helper.read_text();inputs[str(helper)]=ref(helper)
exec(compile(s[s.index('stopns='):s.index('for name,args in')],str(helper)+'::passive_setup','exec'),globals())
for name,args in [('validate_plan_shape',(plan,)),('validate_audit_view',(audit,)),('audit_mapping',(plan,audit,plan['episodes'][0])),('scientific_equivalence',(plan,))]:ens[name](*args);ck('unmodified passive '+name,True)
verify=load_ast('scripts/qd_ed_n34_controller.py',['FIELDS','verify_semantics'],{'w':w,'math':math})['verify_semantics']
def rejection(label,fn,expected=None):
 try:fn()
 except Exception as ex:
  result={'check':label,'status':'REJECTED','type':type(ex).__name__,'error':str(ex)}
  if expected:ck(label+' exact rejection',str(ex)==expected,str(ex))
  return result
 return {'check':label,'status':'PASS'}
controller_result=rejection('unmodified controller reviewed semantics',lambda:verify(ctrlref,rtref,closure))
ck('controller attestation blocker resolved',controller_result['status']=='PASS',controller_result)
for row in audit['episodes']:
 m=read(audit['expected_manifests'][row['episode_key']]);old=read(oldaudit['expected_manifests'][row['episode_key']])
 ck('frozen audit payload '+row['episode_key'],all(m[k]==old[k] for k in ['row','argv','resolved_config','composed_config_sha256','expected_runtime','source','scientific_source']))
 for k in ['runtime','runtime_closure','controller_semantics','accounting','scope','deployment','protocol','protocol_review']:ck('audit manifest crossbinding '+row['episode_key']+' '+k,m[k]==audit[k])
ck('engineering frozen payload',all(em[k]==oldem[k] for k in ['row','audit_row','argv','resolved_config','composed_config_sha256','expected_runtime','source','scientific_source']))
ck('engineering audit manifest binding',em['audit_plan']==plan['audit_plan'] and em['audit_manifest']==audit['expected_manifests'][audit['episodes'][0]['episode_key']])
ck('exact one C0 engineering and disabled audit',len(plan['episodes'])==1 and plan['episodes'][0]['profile']=='C0' and len(audit['episodes'])==40 and plan['release_enabled'] is False and audit['release_enabled'] is False and plan['authority'] is None and plan['b5_review'] is None)
for k in ['episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting']:ck('unchanged audit science '+k,audit[k]==oldaudit[k])
for k in ['runtime','runtime_closure','source_inventory','scientific_source_inventory','scientific_equivalence']:
 r=prior['roots'][k];read(r);matrix.append(dict(kind=k,disposition='reused_byte_identical',reference=ref(r['path'])))
for k in ['native_build','scope','accounting','deployment','protocol','protocol_review']:
 r=(plan if k in plan else audit)[k];read(r);matrix.append(dict(kind=k,disposition='reused_byte_identical',reference=ref(r['path'])))
# Expose each changed approval binding independently, without synthesizing B5 or enabling plan.
bindings=ens['review_bindings'](plan);root_inputs={};root_proposals={};binding_diagnostics=[]
parent_diag=read(prior['root_binding_diagnostics'])
for name,r in parent_diag['accepted_historical_inputs'].items():
 d=read(r);root_inputs[name]=r
 mismatch=[k for k,v in bindings.items() if d.get(k)!=v]
 result=rejection('inherited '+name+' exact bindings',lambda d=d:ens['exact']({k:d[k] for k in bindings},bindings,'changed readiness bindings require renewed '+name))
 binding_diagnostics.append(dict(kind=name,inherited=r,changed_binding_keys=mismatch,consumer_result=result))
 ck('inherited approval stale binding keys '+name,set(mismatch)=={'runtime','runtime_closure','controller_semantics','audit_plan','engineering_manifest'})
 matrix.append(dict(kind='inherited_approval:'+name,disposition='historical_review_retained_not_transferred',reference=r,changed_binding_keys=mismatch))
 if name!='independent_b5':
  # Wrappers contain reference proposals, never production approvals or a fake B5.
  root_proposals[name]=write('root-inputs/'+name+'.proposed-v1.json',{'schema':'n36-readiness-root-binding-proposal-v1','kind':name,'status':'PROPOSED_REQUIRES_COORDINATOR_ATTESTATION','prior_authority':r,'proposed_binding_replacements':{k:bindings[k] for k in mismatch},'proposed_predecessors':dict(root_proposals),'independent_b5':'PENDING_RENEWED_INDEPENDENT_REVIEW','unchanged_semantic_fields':[k for k in d if k not in mismatch],'release_enabled':False,'approved':False,'new_root_approval':False})
for key,action in [('INDEPENDENT_B5_RENEWAL_REQUIRED','Independent B5 must review changed runtime/closure/controller and affected manifests; inherited source/science findings remain provenance only.'),('ROOT_PROTOCOL_SOURCE_REATTESTATION_REQUIRED','Coordinator must reissue exact protocol acceptance and source adoption for final reviewed bindings and renewed B5.'),('ROOT_ACCOUNTING_BUDGET_REATTESTATION_REQUIRED','Coordinator must reissue accounting amendment and finite budget authority for final bindings; preserve all charges, caps, limits and ledger prefixes.'),('LATER_ROOT_RELEASE_OPERATIONS_REQUIRED','After complete passive closure and independent/root review, separate root operations must issue health release, run fresh metered native healthcheck, settle it, and issue episode release. No operation authorized here.')]:blockers.append(dict(id=key,required_action=action))
write('root-binding-diagnostics-v1.json',{'results':binding_diagnostics,'accepted_historical_inputs':root_inputs,'proposed_replacements':root_proposals,'release_enabled':False,'independent_B5_performed':False})
# Passive runtime closure verification: exact production function bodies, no native imports.
import importlib.machinery, importlib.metadata, importlib.util, tempfile
names=['GENERATED_NAME','GENERATOR_NAME','TEMPLATE_NAME','GENERATED_RULE','GENERATOR_SHA','TEMPLATE_SHA','CYUTILITY_TARGETS','CYUTILITY_RULE','RuntimeOriginError','_failure_origin','_runtime_file','_live_source','_generated_runtime','_alias_rules','verify_runtime']
rns=load_ast('scripts/qd_ed_n34_source.py',names,dict(w=w,Path=Path,sys=sys,json=json,ast=ast,hashlib=hashlib,importlib=importlib,tempfile=tempfile))
runtime_result=rejection('unmodified production runtime closure',lambda:rns['verify_runtime'](closure,rtref))
if runtime_result['status']!='PASS':blockers.append(dict(id='RUNTIME_CLOSURE_CHECK_FAILED',observation=runtime_result))
# Execute the exact readiness require statement separately from gated full closure.
fulltree=ast.parse((ROOT/'scripts/qd_ed_n36_release.py').read_text());fullfunc=next(n for n in fulltree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_audit_closure')
node=next(n for n in fullfunc.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and any(isinstance(a,ast.Constant) and a.value=='runtime checkout/device/provider' for a in n.value.args))
rrns=load_ast('scripts/qd_ed_final_runner.py',['E2_STAGE_CONDITION','runtime_gpu'],{'require':require});rr=types.SimpleNamespace(**rrns)
ready_result=rejection('exact production runtime checkout/device/provider predicate',lambda:exec(compile(ast.Module(body=[node],type_ignores=[]),str(ROOT/'scripts/qd_ed_n36_release.py'),'exec'),dict(w=w,Path=Path,runtime=runtime,plan=audit,c=c,r=rr)))
ck('prior readiness blocker resolved',ready_result['status']=='PASS',ready_result)
# Actual production import/call attempt under the no-native-import fence; no mocks or approval changes.
sys.path.insert(0,str(ROOT))
def actual_full():
 from scripts import qd_ed_n36_release as production
 return production.verify_audit_closure(audit)
full_result=rejection('actual production full audit closure',actual_full)
full_result['acceptance_predicates_modified']=False;full_result['authority_mutated']=False
full_result['full_closure_completed']=full_result['status']=='PASS'
if full_result['status']!='PASS':blockers.append(dict(id='FULL_PRODUCTION_CLOSURE_NOT_COMPLETED',observation=full_result,required_action='Root must run actual full audit closure after controller attestation in its authorized runtime. Executor fence prohibits native imports; no simulated full PASS.'))
write('production-closure-check-v1.json',dict(runtime_closure=runtime_result,readiness_predicate=ready_result,controller=controller_result,actual_full_closure=full_result,release_enabled=False,independent_B5_performed=False,scope='Component checks use unmodified AST bodies; actual full call uses real imports under no-native fence. No predicates bypassed.'))
# Only scan direct active references. No recursive historical provenance expansion.
edges=[]
def scan(d,p):
 if isinstance(d,dict):
  if isinstance(d.get('path'),str) and isinstance(d.get('sha256'),str):
   actual=ref(d['path']);ck('active hash and size '+p,actual['sha256']==d['sha256'] and all(d[k]==actual['bytes'] for k in ['bytes','size_bytes'] if k in d));ck('no stale active ref '+p,d['path'] not in mapping);edges.append(dict(location=p,reference=ref(d['path'])));return
  for k,v in d.items():
   if k not in ['source','scientific_source','reference_refresh_lineage','inherited_review','root_review_evidence','prior_evidence','rebound_from','root_binding_attestation','prior_graph']:scan(v,p+'/'+k)
 elif isinstance(d,list):
  for i,v in enumerate(d):scan(v,p+'/'+str(i))
for label,obj in [('plan',plan),('audit',audit),('engineering_manifest',em),('controller_semantics',ctrl)]+[(r['episode_key'],read(audit['expected_manifests'][r['episode_key']])) for r in audit['episodes']]:scan(obj,label)
edgeref=write('graph-edges-v1.json',dict(edges=edges,scope='Direct active affected refs; immutable historical anchors not recursively expanded.',release_enabled=False))

history={'parent_report':a['inputs']['parent_report'],'parent_b5_inputs':ref(PREV/'independent-b5-inputs-v1.json'),'parent_checks':prior['checks'],'parent_production_closure':prior['production_closure_check'],'parent_finalization':ref(PREV/'finalization-receipt-v1.json'),'parent_blockers':prior['blockers'],'policy':'All prior FAIL and failed-attempt history retained through immutable parent anchors. No historical checks rerun or recursive provenance reconstruction.'}
write('retained-history-v1.json',history)
mref=write('changed-reused-evidence-matrix-v1.json',dict(source=HEAD,entries=matrix,graph_delta_separate='graph-root-delta-v1.json',prior_B5_transfers=False,all41_payloads_preserved=True,release_enabled=False,b5_review=None))
graph=rebind(oldgraph);graph.update(evidence_matrix=mref,prior_graph=pair(prior['roots']['graph']),graph_edges=edgeref,blockers=blockers,status='DISABLED_ATTESTED_READINESS_CONSUMERS_PENDING_INDEPENDENT_B5')
scan(graph,'graph')
graphref=changed('graph_root',prior['roots']['graph'],'graph-root.disabled-v1.json',graph,['/plan','/audit','/engineering_manifest','/audit_manifests','/retained_bindings','/evidence_matrix','/prior_graph','/graph_edges','/blockers','/status'])
write('graph-root-delta-v1.json',matrix[-1])
roots={k:ref(rebind(v)['path']) for k,v in prior['roots'].items()};roots.update(controller_semantics=ref(ctrlref['path']),evidence_matrix=ref(mref['path']),graph=ref(graphref['path']))
for key in ['plan','audit','engineering_manifest','source_inventory','scientific_source_inventory','scientific_equivalence','evidence_matrix']:
 ck('graph root binding '+key,graph[key]==pair(roots[key]))
ck('graph all40 manifests',graph['audit_manifests']==audit['expected_manifests'])
for key,r in graph['retained_bindings'].items():ck('graph retained binding '+key,plan[key]==r)
for label,obj in [('plan',plan),('audit',audit),('graph',graph),('controller',ctrl)]:
 ck('disabled root '+label,obj['release_enabled'] is False and obj.get('b5_review') is None and obj.get('authority') is None)
ck('runtime preparation disabled',runtime['preparation']['release_enabled'] is False and runtime['preparation']['runtime_ready'] is False)
rootref=write('refreshed-root-references-v1.json',dict(roots=roots,root_controller_attestation=a['inputs']['controller_attestation'],proposed_authority_replacements=root_proposals,accepted_historical_inputs=root_inputs,release_enabled=False,b5_review=None,authority=None))
stop.check(need=1);boundary();ck('final STOP/deadline',True,dt.datetime.now(dt.timezone.utc).isoformat())
ck('final source preserved',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True))
ck('engineering output not created',not os.path.lexists(plan['artifact_root']))
for r in list(inputs.values()):ck('retained input '+r['path'],ref(r['path'])==r)
checkref=write('passive-consumer-checks-v1.json',dict(checks=checks,definitions=definitions,acceptance_predicates_modified=False,independent_B5_performed=False,release_enabled=False,scope='Unmodified passive consumer functions and exact bounded component predicates. Full production import attempted under no-native fence; no full PASS implied.'))
import shlex
code="from scripts import qd_ed_n23_worker as w; from scripts.qd_ed_n36_release import verify_audit_closure; verify_audit_closure(w.read_ref("+repr(pair(roots['audit']))+")); print('PASS_FULL_AUDIT_CLOSURE_ONLY_NO_DISPATCH')"
nextstep={'cwd':str(ROOT),'command':"env CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 /home/hynx/miniconda3/envs/vla-pilot/bin/python -c "+shlex.quote(code),'execute_now':False,'purpose':'Later root full production closure diagnostic with exact refreshed audit path/hash, only in separately authorized environment permitting necessary imports/reads. No authority or release mutation.','immediate_next_action':'Separate independent B5 reviewer reviews independent-b5-inputs-v1.json against these exact roots, preserving prior FAIL history; this executor does not perform B5.','independent_b5_inputs_path':str(OUT/'independent-b5-inputs-v1.json'),'sequence':['Independent B5 of final disabled graph.','Root reissues protocol/source/accounting/budget bindings for final graph and renewed B5.','Complete production full closure in authorized runtime.','Only separate later root operations may release, meter and settle fresh native healthcheck, then episode release.']}
write('proposed-next-command-v1.json',nextstep)
status='ATTESTED_READINESS_CONSUMERS_REFRESHED_RELEASE_DISABLED_REVIEW_REQUIRED'
report=dict(schema='n36-attested-readiness-consumer-refresh-report-v1',node_id='15.6',source=HEAD,status=status,roots=roots,canonical_root_references=ref(rootref['path']),preparation_authority=ref(OUT/'authority-v1.json'),root_controller_attestation=a['inputs']['controller_attestation'],parent_report=a['inputs']['parent_report'],retained_history=outputs['retained-history-v1.json'],checks=ref(checkref['path']),evidence_matrix=ref(mref['path']),graph_root_delta=outputs['graph-root-delta-v1.json'],blockers=blockers,root_binding_diagnostics=outputs['root-binding-diagnostics-v1.json'],production_closure_check=outputs['production-closure-check-v1.json'],proposed_next_command=nextstep,inputs=list(inputs.values()),outputs=dict(outputs),graph_reference_refresh_complete=True,affected_passive_consumers_pass=True,controller_attestation_blocker_resolved=True,full_production_closure_passed=full_result['full_closure_completed'],release_enabled=False,b5_review=None,authority=None,independent_B5_performed=False,inherited_review_transfers_to_changed_bindings=False,source_edited=False,owner_state_tree_ledger_written=False,native_model_provider_execution=False,gpu_dispatch=False,credentials_accessed=False,protected_results_accessed=False,delegation=False,scientific_success=False,target_met=False,score=None,model_policy='Existing official current-login gpt-6-astra session only; no provider/account/API invocation.',budget=dict(started_at=START_AT.isoformat(),finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-START,cpu_seconds=time.process_time()-CPU,timeout_seconds=1200,local_process_cap_seconds=600,deadline=a['deadline']),limits=['Runtime verification may stop at prohibited credential-library path; rejection is not a fingerprint mismatch.','Full production imports may stop at native/model fence; downstream unvisited gates remain unverified.','Prior FAIL history retained through parent references, not rerun.'])
reportref=write('report-v1.json',report)
b5={**{k:oldinputs[k] for k in ['accepted_source_review','independent_source_review','prior_source','retained_failed_preparation_attempt','historical_independent_b5'] if k in oldinputs},'schema':'n36-attested-readiness-independent-b5-inputs-v1','source':HEAD,'roots':roots,'preparation_report':ref(reportref['path']),'preparation_outputs':dict(outputs),'parent_inputs':ref(PREV/'independent-b5-inputs-v1.json'),'retained_history':outputs['retained-history-v1.json'],'root_controller_attestation':a['inputs']['controller_attestation'],'changed_bindings_require_renewed_review':True,'root_proposals':root_proposals,'blockers':blockers,'release_enabled':False,'authority':None,'b5_review':None,'independent_B5_performed':False,'prior_B5_approves_current_bindings':False}
b5ref=write('independent-b5-inputs-v1.json',b5)
with (OUT/'report-v1.sha256').open('x') as f:f.write(reportref['sha256']+'  report-v1.json\n')
outputs['report-v1.sha256']=ref(OUT/'report-v1.sha256')
seal=write('artifact-hash-seal-v1.json',dict(report=ref(reportref['path']),independent_b5_inputs=ref(b5ref['path']),outputs=dict(outputs),executor_helper=ref(__file__),release_enabled=False,b5_review=None))
boundary();stop.check(need=1)
for r in list(outputs.values())+list(inputs.values()):require(ref(r['path'])==r,'final hash/size drift '+r['path'])
receipt=write('finalization-receipt-v1.json',dict(schema='n36-attested-readiness-finalization-receipt-v1',at=dt.datetime.now(dt.timezone.utc).isoformat(),report=ref(reportref['path']),report_sha256=reportref['sha256'],independent_b5_inputs=ref(b5ref['path']),artifact_hash_seal=ref(seal['path']),verified_reference_count=len(outputs)+len(inputs),checks='PASS_FINAL_ARTIFACT_INTEGRITY_ONLY',stop_absent=True,deadline_open=True,source_head_exact_and_tracked_clean=True,release_enabled=False,authority_mutated=False,source_edited=False,gpu_dispatch=False,scientific_goal_complete=False,full_closure_passed=full_result['full_closure_completed'],blockers=blockers,proposed_next_command=nextstep,budget_elapsed_since_initial_check_seconds=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat('2026-10-10T19:55:01+00:00')).total_seconds()))
with (OUT/'finalization-receipt-v1.sha256').open('x') as f:f.write(receipt['sha256']+'  finalization-receipt-v1.json\n')
print(json.dumps(dict(status=status,report=ref(reportref['path']),checks=len(checks),blockers=blockers),indent=2))
