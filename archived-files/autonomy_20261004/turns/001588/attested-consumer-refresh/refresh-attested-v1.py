from pathlib import Path
PREV=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001584/runtime-graph-refresh')
helper=PREV/'refresh-runtime-v1.py'
# Reuse only artifact utilities and unmodified AST loader, never prior execution.
exec(compile(helper.read_text().split("boundary();ck('initial STOP/deadline'")[0],str(helper)+'::utilities','exec'),globals())
boundary();ck('initial STOP/deadline',True,START_AT.isoformat())
a=read(ref(OUT/'authority-v1.json'));read(a['standing_authority']);att=read(a['root_attestation'])
prior=read(ref(PREV/'report-v1.json'));oldinputs=read(ref(PREV/'independent-b5-inputs-v1.json'))
inputs[str(helper)]=ref(helper)
ck('HEAD exact clean',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True))
oldplan=read(prior['roots']['plan']);oldaudit=read(prior['roots']['audit']);oldgraph=read(prior['roots']['graph']);oldem=read(prior['roots']['engineering_manifest'])
runtime=read(oldplan['runtime']);closure=read(oldplan['runtime_closure']);oldctrl=read(oldplan['controller_semantics']);ctrl=read(att['controller_semantics'])
ck('root attestation scope',att['status']=='PASS_STATIC_BINDING_REFRESH_ONLY' and att['release_enabled'] is False and att['independent_B5_performed'] is False)
ck('root runtime bindings',ctrl['runtime']==oldplan['runtime']==att['runtime'] and ctrl['runtime_closure']==oldplan['runtime_closure']==att['runtime_closure'])
reviewed={**ctrl['review_evidence'],'controller_semantics':att['controller_semantics']}
for entry in att['checks']:
 name='controller_semantics' if 'controller-semantics' in entry['proposal']['path'] else Path(entry['proposal']['path']).name.split('.')[0]
 newref=ref(reviewed[name]['path']);new=read(reviewed[name]);read(entry['proposal']);read(entry['prior'])
 ck('attested unchanged semantics '+name,entry['semantic_content_unchanged'] is True and entry['source_hashes_verified'] is True)
 for oldref in [entry['proposal'],entry['prior']]:mapping[oldref['path']]=newref
 matrix.append(dict(kind='controller:'+name,disposition='reused_existing_root_reviewed',old=entry['proposal'],prior=entry['prior'],new=newref,new_approval_issued=False))
for row in oldaudit['episodes']:
 key=row['episode_key'];r=oldaudit['expected_manifests'][key];old=read(r)
 changed('audit_manifest:'+key,r,'audit-manifests/'+key+'.json',rebind(old),['/controller_semantics'])
audit=rebind(oldaudit);changed('audit_view',prior['roots']['audit'],'audit-view.disabled-v1.json',audit,['/controller_semantics','/expected_manifests'])
em=rebind(oldem);changed('engineering_manifest',prior['roots']['engineering_manifest'],'engineering-manifest.disabled-v1.json',em,['/controller_semantics','/audit_plan','/audit_manifest'])
plan=rebind(oldplan);changed('disabled_plan',prior['roots']['plan'],'engineering-plan.disabled-v1.json',plan,['/controller_semantics','/audit_plan','/engineering_manifest','/expected_manifests'])
helper2=TURNS/'001582/independent-b5/passive-review-v2.py';s=helper2.read_text();inputs[str(helper2)]=ref(helper2)
exec(compile(s[s.index('stopns='):s.index('for name,args in')],str(helper2)+'::passive_setup','exec'),globals())
for name,args in [('validate_plan_shape',(plan,)),('validate_audit_view',(audit,)),('audit_mapping',(plan,audit,plan['episodes'][0])),('scientific_equivalence',(plan,))]:ens[name](*args);ck('unmodified passive '+name,True)
verify=load_ast('scripts/qd_ed_n34_controller.py',['FIELDS','verify_semantics'],{'w':w,'math':math})['verify_semantics']
try:verify(oldplan['controller_semantics'],oldplan['runtime'],closure)
except ValueError as ex:ck('prior controller gate reproduced',str(ex)=='reviewed controller semantics required',str(ex))
else:raise ValueError('prior proposal unexpectedly accepted')
verify(plan['controller_semantics'],plan['runtime'],closure);ck('unmodified controller reviewed semantics accepted',True)
for row in audit['episodes']:
 m=read(audit['expected_manifests'][row['episode_key']]);old=read(oldaudit['expected_manifests'][row['episode_key']])
 ck('manifest frozen payload '+row['episode_key'],m['row']==row and all(m[k]==old[k] for k in ['argv','resolved_config','composed_config_sha256','expected_runtime','source','scientific_source']))
 for k in ['runtime','runtime_closure','controller_semantics','accounting','scope','deployment','protocol','protocol_review']:ck('manifest consumer binding '+row['episode_key']+' '+k,m[k]==audit[k])
ck('engineering frozen payload',all(em[k]==oldem[k] for k in ['argv','resolved_config','composed_config_sha256','expected_runtime','row','audit_row','source','scientific_source']))
ck('engineering audit binding',em['audit_plan']==plan['audit_plan'] and em['audit_manifest']==audit['expected_manifests'][audit['episodes'][0]['episode_key']])
ck('forty cells protocols thresholds old charges unchanged',len(audit['episodes'])==40 and all(audit[k]==oldaudit[k] for k in ['episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting']))
for k in ['runtime','runtime_closure','source_inventory','scientific_source_inventory','scientific_equivalence']:
 r=prior['roots'][k];read(r);matrix.append(dict(kind=k,disposition='reused_byte_identical',reference=ref(r['path'])))
for k in ['native_build','scope','accounting','deployment','protocol','protocol_review']:
 r=(plan if k in plan else audit)[k];read(r);matrix.append(dict(kind=k,disposition='reused_byte_identical',reference=ref(r['path'])))
ck('runtime still unready',runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False and runtime['preparation']['runtime_ready'] is False)
ck('no execution output',not os.path.lexists(plan['artifact_root']))
remaining=['Independent B5 on these exact refreshed roots remains absent; coordinator followup, no prior PASS transfers.','Separate root protocol acceptance remains absent.','Source and accounting adoption remain absent.','Actual runtime/provider/CUDA-EGL readiness remains absent.','Detached prospective releases remain absent; all roots stay release_enabled=false and b5_review=null.']
blockers=[dict(id=i,required_action=t) for i,t in zip(['INDEPENDENT_B5_REQUIRED','ROOT_PROTOCOL_ACCEPTANCE_REQUIRED','SOURCE_ACCOUNTING_ADOPTION_REQUIRED','ACTUAL_READINESS_REQUIRED','DETACHED_PROSPECTIVE_RELEASES_REQUIRED'],remaining)]
# One-level reference verification only: do not reconstruct historical provenance.
edges=[]
def scan(d,p):
 if isinstance(d,dict):
  if isinstance(d.get('path'),str) and isinstance(d.get('sha256'),str):
   actual=ref(d['path']);ck('active hash '+p,actual['sha256']==d['sha256'] and ('bytes' not in d or d['bytes']==actual['bytes']) and ('size_bytes' not in d or d['size_bytes']==actual['bytes']))
   ck('no stale active controller/consumer ref '+p,d['path'] not in mapping);edges.append(dict(location=p,reference=actual));return
  for k,v in d.items():
   if k not in ['source','scientific_source','reference_refresh_lineage','inherited_review','root_review_evidence','prior_evidence','rebound_from','root_binding_attestation','prior_graph']:scan(v,p+'/'+k)
 elif isinstance(d,list):
  for i,v in enumerate(d):scan(v,p+'/'+str(i))
for label,obj in [('plan',plan),('audit',audit),('engineering_manifest',em),('controller_semantics',ctrl)]+[(r['episode_key'],read(audit['expected_manifests'][r['episode_key']])) for r in audit['episodes']]:scan(obj,label)
edgeref=write('graph-edges-v1.json',dict(edges=edges,scope='Direct affected consumer references only; no recursive provenance reconstruction.',release_enabled=False,b5_review=None))
mref=write('changed-reused-evidence-matrix-v1.json',dict(source=HEAD,entries=matrix,graph_delta_separate='graph-root-delta-v1.json',all40_config_argv_and_algorithm_bytes_preserved=True,all40_recomposed=False,prior_B5_transfers=False,release_enabled=False,b5_review=None))
graph=rebind(oldgraph);graph.update(evidence_matrix=mref,prior_graph=pair(prior['roots']['graph']),graph_edges=edgeref,blockers=blockers,status='DISABLED_ATTESTED_CONSUMERS_PENDING_INDEPENDENT_B5')
scan(graph,'graph')
graphref=changed('graph_root',prior['roots']['graph'],'graph-root.disabled-v1.json',graph,['/plan','/audit','/engineering_manifest','/audit_manifests','/retained_bindings','/evidence_matrix','/prior_graph','/graph_edges','/blockers','/status'])
write('graph-root-delta-v1.json',matrix[-1])
roots={k:ref(rebind(v)['path']) for k,v in prior['roots'].items()};roots.update(evidence_matrix=ref(mref['path']),graph=ref(graphref['path']))
for label,obj in [('plan',plan),('audit',audit),('graph',graph),('runtime',runtime),('runtime_closure',closure),('controller_semantics',ctrl)]:ck('disabled root '+label,obj['release_enabled'] is False and obj['b5_review'] is None)
rootref=write('refreshed-root-references-v1.json',dict(roots=roots,release_enabled=False,b5_review=None,authority=None,source_adopted=False,accounting_adopted=False))
stop.check(need=1);boundary();ck('final STOP/deadline',True,dt.datetime.now(dt.timezone.utc).isoformat())
ck('final HEAD exact clean',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True))
for r in list(inputs.values()):ck('input retained '+r['path'],ref(r['path'])==r)
checkref=write('passive-consumer-checks-v1.json',dict(checks=checks,definitions=definitions,acceptance_predicates_modified=False,independent_B5_performed=False,verification_scope='Unmodified AST plan/audit/mapping/scientific-equivalence/controller consumers; direct hash/size and crossbinding checks; frozen payload preservation. No full readiness/release verifier, tests, native/model/provider execution or external evidence reconstruction.',release_enabled=False,b5_review=None))
status='ATTESTED_CONSUMER_REFRESH_COMPLETE_DISABLED_PENDING_INDEPENDENT_B5'
report=dict(schema='n36-attested-consumer-refresh-report-v1',node_id='15.6',source=HEAD,status=status,roots=roots,canonical_root_references=ref(rootref['path']),preparation_authority=ref(OUT/'authority-v1.json'),root_attestation=a['root_attestation'],prior_preparation_report=ref(PREV/'report-v1.json'),prior_B5_FAIL=prior['prior_B5_FAIL'],retained_failed_preparation_attempt=prior['retained_failed_preparation_attempt'],graph_reference_refresh_complete=True,affected_passive_consumers_pass=True,controller_attestation_blocker_resolved=True,graph_refresh_complete=True,readiness_release_certified=False,blockers=blockers,remaining_obligations=remaining,checks=ref(checkref['path']),evidence_matrix=ref(mref['path']),graph_root_delta=outputs['graph-root-delta-v1.json'],inputs=list(inputs.values()),outputs=dict(outputs),retained_accounting=prior['retained_accounting'],release_enabled=False,b5_review=None,authority=None,authority_granted=False,new_approvals_issued=False,independent_B5_performed=False,source_adopted=False,accounting_adopted=False,source_edited=False,owner_state_tree_ledger_written=False,native_model_provider_execution=False,gpu_dispatch=False,CUDA_VISIBLE_DEVICES='',credentials_accessed=False,protected_results_accessed=False,delegation=False,scientific_success=False,target_met=False,score=None,tests_rerun=0,model_policy='Existing official current-login gpt-6-astra session only; no alternate provider, account or API invoked.',budget=dict(started_at=START_AT.isoformat(),finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-START,cpu_seconds=time.process_time()-CPU,timeout_seconds=1200,deadline=a['deadline']),size_schema_note='Existing pair-only reference schemas retained; real byte counts bound in matrix, direct edges, roots and B5 inputs.')
rr=write('report-v1.json',report)
b5={**{k:oldinputs[k] for k in ['accepted_source_review','independent_source_review','prior_source','retained_failed_preparation_attempt']},'schema':'n36-attested-consumer-refresh-independent-b5-inputs-v1','source':HEAD,'status':status,'roots':roots,'preparation_report':ref(rr['path']),'preparation_outputs':dict(outputs),'authority_record':ref(OUT/'authority-v1.json'),'root_attestation':a['root_attestation'],'prior_preparation_report':ref(PREV/'report-v1.json'),'prior_B5_FAIL':prior['prior_B5_FAIL'],'blockers':blockers,'remaining_obligations':remaining,'release_enabled':False,'b5_review':None,'authority':None,'source_adopted':False,'accounting_adopted':False,'independent_B5_performed':False,'prior_B5_approves_current_source':False}
br=write('independent-b5-inputs-v1.json',b5)
with (OUT/'report-v1.sha256').open('x') as f:f.write(rr['sha256']+'  report-v1.json\n')
write('artifact-hash-seal-v1.json',dict(report=ref(rr['path']),independent_b5_inputs=ref(br['path']),roots=roots,release_enabled=False,b5_review=None))
boundary();stop.check(need=1)
for r in list(outputs.values()):require(ref(r['path'])==r,'final output hash/size drift')
for r in list(inputs.values()):require(ref(r['path'])==r,'final input drift')
write('artifact-final-check-v1.json',dict(status='PASS',checked_outputs=len(outputs),checked_inputs=len(inputs),all_hashes_sizes_match=True,prior_input_bytes_preserved=True,STOP_absent=True,checked_at=dt.datetime.now(dt.timezone.utc).isoformat(),deadline=a['deadline'],release_enabled=False,b5_review=None))
print(json.dumps(dict(status=status,report=ref(rr['path']),checks=len(checks),changed_artifacts=len(mapping)-8,remaining_blockers=blockers),indent=2))
