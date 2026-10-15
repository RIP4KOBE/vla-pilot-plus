import pathlib,json,hashlib,datetime,subprocess,os
O=pathlib.Path(__file__).parent;T=O.parent.parent;A=O/'attempt-2'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text())
def rec(p):p=pathlib.Path(p);return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def ref(p):return {k:v for k,v in rec(p).items() if k!='bytes'}
def save(name,d):
 with (O/name).open('x') as f:json.dump(d,f,indent=2,allow_nan=False)
 return ref(O/name)
a=load(O/'authority-v1.json');r=load(a['source_review']['path']);i=load(T/'001617/recovery-implementation/binding-impact-v1.json');g1=load(O/'generation-results-v1.json');g2=load(A/'generation-results-v1.json');p=load(A/'engineering-plan.draft-disabled-v1.json');audit=load(A/'audit-view.disabled-v1.json');placement=load(O/'source-placement-v1.json');conflict=load(O/'immutable-runtime-conflict-v1.json');root=pathlib.Path(i['deployment_source_cwd'])
inputs={x['path']:x for g in (g1,g2) for x in g['inputs']};inputs[str(O/'authority-v1.json')]=rec(O/'authority-v1.json')
input_checks=[]
for name,expected in inputs.items():
 actual=rec(name);input_checks.append({'before':expected,'after':actual,'unchanged':actual==expected})
assert all(x['unchanged'] for x in input_checks)
ledger_checks={k:{'before':v,'after':rec(v['path']),'unchanged':rec(v['path'])==v} for k,v in a['ledger_prefixes'].items()};assert all(x['unchanged'] for x in ledger_checks.values())
stopchecks=[{'path':x['path'],'absent':not os.path.lexists(x['path'])} for x in r['stop_paths']];assert all(x['absent'] for x in stopchecks)
commands=[]
def cmd(args):
 rr=subprocess.run(args,capture_output=True,text=True);commands.append({'argv':args,'exit_code':rr.returncode,'stdout':rr.stdout,'stderr':rr.stderr});assert rr.returncode==0;return rr.stdout
head=cmd(['git','--no-optional-locks','-C',str(root),'rev-parse','HEAD']).strip();status=cmd(['git','--no-optional-locks','-C',str(root),'status','--porcelain=v1','--untracked-files=no']);assert head==r['source_commit'] and not status
assert sha(root/'scripts/qd_ed_n36_engineering.py')==r['parent_adapter_sha256']
assert sha(p['runtime']['path'])==i['preserve']['runtime_bytes']['sha256'];assert p['native_build']==i['preserve']['native_build'] and sha(p['native_build']['path'])==p['native_build']['sha256']
assert not pathlib.Path(p['artifact_root']).exists()
assert p['authority'] is None and p['b5_review'] is None and p['frozen'] is False and p['release_enabled'] is False
assert len(audit['expected_manifests'])==40
# New graph references only; do not recurse into provenance documents.
newdocs={str(x):load(x) for x in A.rglob('*.json') if x.name!='generation-results-v1.json'}
edges={k:set() for k in newdocs};missing=[];mismatched=[]
def visit(obj,current):
 if isinstance(obj,dict):
  if set(obj)=={'path','sha256'} and obj['path'] in newdocs:
   q=obj['path'];edges[current].add(q)
   if not pathlib.Path(q).exists():missing.append(obj)
   elif sha(q)!=obj['sha256']:mismatched.append(obj)
  for v in obj.values():visit(v,current)
 elif isinstance(obj,list):
  for v in obj:visit(v,current)
for k,v in newdocs.items():visit(v,k)
cycles=[];seen=set()
def walk(k,stack):
 if k in stack:cycles.append(stack+[k]);return
 if k in seen:return
 seen.add(k)
 for child in edges[k]:walk(child,stack+[k])
for k in edges:walk(k,[])
assert not cycles and not missing and not mismatched
binding_changes={k:{'prior':v['prior'],'refreshed':p[k]} for k,v in i['affected_bindings'].items()}
binddiff=save('binding-diff.disabled-v1.json',{'schema':'n36-engineering-r1-binding-diff-v1','release_enabled':False,'affected_count':len(binding_changes),'bindings':binding_changes,'native_build_unchanged':p['native_build'],'new_graph_cycles':cycles,'new_graph_missing_references':missing,'new_graph_hash_mismatches':mismatched,'pending_external_authority_fields':['authority','b5_review']})
verifyref=save('preservation-verification-v1.json',{'schema':'n36-engineering-r1-refresh-preservation-v1','inputs':input_checks,'ledgers':ledger_checks,'stop_paths':stopchecks,'runtime_bytes_unchanged':True,'native_build_reference_and_bytes_unchanged':True,'parent_adapter_bytes_unchanged':True,'original_scientific_rows_protocol_thresholds_unchanged':True,'canonical_source_head':head,'tracked_clean':True,'commands':commands,'release_enabled':False})
command_results=[{'argv':['python','-B',str(O/'place-source.disabled.py')],'exit_code':1,'result':'Stopped before mutation: initial process check incorrectly required cwd access for unrelated system processes. Preflight v1 preserved.'},{'argv':['python','-B',str(O/'place-source-v2.disabled.py')],'exit_code':0,'result':'Worker argv identified before cwd inspection; no matching live worker/inaccessible worker. Exact authorized fast-forward only.'},{'argv':['/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12','-B',str(O/'refresh-graph.disabled.py')],'environment_overrides':{'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'},'exit_code':0,'validator_result':'FAIL','log':ref(O/'refresh-graph.log'),'details':ref(O/'generation-results-v1.json')},{'argv':['/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12','-B',str(O/'refresh-graph-v2.disabled.py')],'environment_overrides':{'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'},'exit_code':0,'validator_result':'FAIL','log':ref(O/'refresh-graph-v2.log'),'details':ref(A/'generation-results-v1.json')}]
outputs=[]
# Exclude preexisting/live executor wrapper files. List only immutable artifacts we created.
for x in sorted(O.rglob('*')):
 if not x.is_file():continue
 if x.parent==O and x.name in {'events.jsonl','process-v1.json','wrapper-launch-v1.json','prompt.txt','stderr.log','wrapper.log','authority-v1.json','run-executor.py'}:continue
 outputs.append(rec(x))
started=datetime.datetime.fromisoformat(a['at']);now=datetime.datetime.now(datetime.timezone.utc)
report={'schema':'n36-engineering-r1-binding-refresh-report-v1','node_id':'15.6','status':'BLOCKED','verdict':'NOT_PASS','verdict_scope':'Disabled engineering artifact preparation only; actual CPU validators identify unresolved immutable runtime/source conflict and pending controller root review. No scientific outcome acceptance.','started_at':started.isoformat(),'completed_at':now.isoformat(),'elapsed_since_authority_seconds':(now-started).total_seconds(),'executor_timeout_seconds':1200,'deadline':a['deadline'],'authority':ref(O/'authority-v1.json'),'source_review':a['source_review'],'binding_impact':ref(T/'001617/recovery-implementation/binding-impact-v1.json'),'source_placement':{'evidence':ref(O/'source-placement-v1.json'),'before':placement['before'],'after':head,'diff':rec(O/'source-placement.diff'),'root_source_adoption':False,'preparatory_placement_only':True,'tracked_clean_before_and_after':True,'source_edits':False,'new_commits':False},'prepared':{'affected_bindings_count':11,'bindings':ref(A/'bindings.disabled-v1.json'),'binding_diff':binddiff,'audit_manifests_count':40,'audit_view':p['audit_plan'],'engineering_manifest':p['engineering_manifest'],'draft_plan':ref(A/'engineering-plan.draft-disabled-v1.json'),'scope':p['scope'],'accounting':p['accounting'],'deployment':p['deployment'],'runtime_closure_changes':ref(A/'runtime-closure-diff.disabled-v1.json'),'native_build':p['native_build'],'runtime':p['runtime'],'artifact_generation_complete':True,'affected_graph_validation_complete':False,'release_enabled':False},'blocking_findings':[{'id':'R1-RUNTIME-SOURCE-CONFLICT','validator':'scripts.qd_ed_final_runner.verify_files','message':conflict['blocker'],'evidence':ref(O/'immutable-runtime-conflict-v1.json'),'conflicting_records_count':len(conflict['conflicts']),'resolution_authorized_in_this_turn':False},{'id':'R1-CONTROLLER-ROOT-REVIEW-PENDING','validator':'scripts.qd_ed_n34_controller.verify_semantics (via full.verify_audit_closure)','message':'reviewed controller semantics required; refreshed proposal has PENDING_INDEPENDENT_AND_ROOT_REVIEW, not fabricated ROOT_REVIEWED.','reference':p['controller_semantics']}],'validator_results':g2['checks'],'retained_native_validation':[x for x in g1['checks'] if x['check']=='Preserved native build bytes'],'resolved_preparation_errors':[{'error':'First runtime closure retained four changed local source hashes','resolution':'Only the four exact reviewed source entries were refreshed in attempt-2; all other closure entries preserved.'},{'error':'Initial diagnostic invoked nonexistent DINO validate_runtime helper','resolution':'Attempt-2 invokes existing DinoSources constructor and check_file for all bound DINO source rows; PASS.'}],'command_results':command_results,'preservation':verifyref,'unchanged_ledgers':ledger_checks,'retained_accounting':load(i['operational_specification']['path'])['retained_snapshot'],'unknown_parent_telemetry_policy':'Preserved exact parent terminal and ledger bytes. No telemetry imputed, charges subtracted, historical outcome replayed or protected reserves borrowed.','input_hashes':list(inputs.values()),'output_hashes':outputs,'graph_reference_analysis':{'scope':'Only newly generated attempt-2 artifacts; historical provenance not recursively reconstructed','cycles':cycles,'missing_new_artifact_references':missing,'hash_mismatches':mismatched,'pending_authority':True,'pending_b5_review':True},'next_bounded_gates':['Owning coordinator must resolve unchanged runtime byte constraint versus four reviewed source file hash conflicts through a separately authorized prospective binding/amendment; no runtime mutation or validator bypass performed here.','Independent and root review of refreshed controller/source/runtime attestations; preserve semantic findings and prior provenance.','Regenerate only bindings/manifests affected by accepted resolution and run existing failed CPU gates.','New independent B5 bound to exact final 12 BINDINGS; prior B5 is not reusable.','Root protocol/source/accounting adoption and new frozen R1 plan; prior parent authority is not reused.','Create new empty isolated R1 output root only under subsequent authorization.','Distinct bounded health release and fresh settled readiness.','Distinct one-use episode release before any engineering diagnostic; zero automatic retries.'],'stop_paths':stopchecks,'restrictions_observed':{'gpu_dispatch':False,'api_provider_auth_fallback':False,'credential_reads':False,'protected_validation_formal_results_access':False,'prohibited_untracked_document_access':False,'owner_state_ledger_lock_driver_mutation':False,'foreign_study_work':False,'other_executors':False,'prior_artifacts_modified':False,'new_commits':False,'source_edits':False,'enabled_release':False,'independent_or_root_review_fabricated':False},'release_enabled':False,'gpu_authorized':False,'target_met':False,'scientific_success':False}
assert (now-started).total_seconds()<1200
save('report-v1.json',report)
save('report-v1.sha256.json',rec(O/'report-v1.json'))
print(json.dumps({'status':report['status'],'report':rec(O/'report-v1.json'),'outputs':len(outputs),'input_hashes':len(inputs),'elapsed':report['elapsed_since_authority_seconds']}))
