import pathlib,json,hashlib,datetime,os,subprocess
O=pathlib.Path(__file__).absolute().parent;P=O.parent.parent/'001627/affected-binding-refresh/attempt-2'
def rec(p):
 p=pathlib.Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def read(p):return json.loads(pathlib.Path(p).read_text())
def save(n,d):
 with (O/n).open('x') as f:json.dump(d,f,indent=2,allow_nan=False)
 return rec(O/n)
a=read(O/'authority-v1.json');g=read(O/'generation-results-v1.json');plan=read(O/'engineering-plan.draft-disabled-v1.json');audit=read(plan['audit_plan']['path']);runtime=read(plan['runtime']['path']);now=datetime.datetime.now(datetime.timezone.utc)
assert now<datetime.datetime.fromisoformat(a['deadline'].replace('Z','+00:00'))
assert (now-datetime.datetime.fromisoformat(a['at'])).total_seconds()<1200
stops=[str(O.parent.parent.parent/'STOP'),'/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP']
assert all(not os.path.lexists(p) for p in stops)
assert len(audit['expected_manifests'])==40
assert not runtime['provider_ready'] and not runtime['cuda_egl_verified'] and not runtime['gpu_mapping']['cuda_egl_verified']
assert plan['authority'] is None and plan['b5_review'] is None and plan['release_enabled'] is False and plan['frozen'] is False
ledger={n:{'before':r,'after':rec(r['path']),'unchanged':rec(r['path'])==r} for n,r in a['ledger_prefixes'].items()};assert all(r['unchanged'] for r in ledger.values())
inputchecks=[{'before':r,'after':rec(r['path']),'unchanged':rec(r['path'])==r} for r in g['inputs']];assert all(r['unchanged'] for r in inputchecks)
# Compare only immediate predecessor manifests; do not traverse provenance.
oldplan=read(P/'engineering-plan.draft-disabled-v1.json');oldaudit=read(P/'audit-view.disabled-v1.json');changes=[]
for key,newref in audit['expected_manifests'].items():
 old=read(oldaudit['expected_manifests'][key]['path']);new=read(newref['path']);diff=[k for k in set(old)|set(new) if old.get(k)!=new.get(k)]
 assert set(diff)=={'runtime','runtime_closure','controller_semantics'}
 changes.append({'episode_key':key,'before':rec(oldaudit['expected_manifests'][key]['path']),'after':rec(newref['path']),'changed_fields':sorted(diff)})
old=read(oldplan['engineering_manifest']['path']);new=read(plan['engineering_manifest']['path']);diff=[k for k in set(old)|set(new) if old.get(k)!=new.get(k)]
assert set(diff)=={'runtime','runtime_closure','controller_semantics','audit_plan','audit_manifest'}
changes.append({'episode_key':new['row']['episode_key'],'before':rec(oldplan['engineering_manifest']['path']),'after':rec(plan['engineering_manifest']['path']),'changed_fields':sorted(diff)})
# Validate references within the newly generated graph; historical provenance remains opaque.
docs={str(pathlib.Path(r['path']).resolve()):read(r['path']) for r in g['outputs'].values() if r['path'].endswith('.json')};edges={p:set() for p in docs};count=0

def visit(x,current):
 global count
 if isinstance(x,dict):
  if isinstance(x.get('path'),str) and isinstance(x.get('sha256'),str):
   q=str(pathlib.Path(x['path']).resolve())
   if q in docs:
    assert rec(x['path'])['sha256']==x['sha256'];edges[current].add(q);count+=1
  for v in x.values():visit(v,current)
 elif isinstance(x,list):
  for v in x:visit(v,current)
for p,d in docs.items():visit(d,p)
seen=set()
def walk(p,stack):
 assert p not in stack,'new graph cycle'
 if p in seen:return
 for q in edges[p]:walk(q,stack|{p})
 seen.add(p)
for p in docs:walk(p,set())
commands=[]
for root in [plan['worktree'],a['worktree']]:
 for args in [['rev-parse','HEAD'],['status','--porcelain=v1','--untracked-files=no']]:
  argv=['git','--no-optional-locks','-C',root]+args;r=subprocess.run(argv,text=True,capture_output=True);commands.append({'argv':argv,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});assert r.returncode==0
  assert r.stdout.strip()==a['source_base'] if args[0]=='rev-parse' else not r.stdout
verification=save('final-verification-v1.json',{'immediate_inputs':inputchecks,'ledger_checks':ledger,'manifest_reference_only_diffs':changes,'new_graph_reference_occurrences_checked':count,'new_graph_acyclic':True,'source_commands':commands,'stop_paths':[{'path':p,'absent':True} for p in stops],'release_enabled':False})
failures=[r for r in g['checks'] if r['status']=='FAIL'];passed=[r['check'] for r in g['checks'] if r['status']=='PASS']
assert all(r.get('message') in ('R1 canonical runtime reference','reviewed controller semantics required') or r['check']=='41 preserved argv scientific configuration recompositions' for r in failures)
config_result=read(O/'config-recomposition-v1.json');assert config_result['status']=='PASS' and len(config_result['results'])==41
passed.append('All41 scientific configuration recompositions with production JSON normalization')
excluded={'events.jsonl','process-v1.json','wrapper-launch-v1.json','prompt.txt','stderr.log','wrapper.log','authority-v1.json','run-executor.py'}
outputs=[rec(p) for p in sorted(O.rglob('*')) if p.is_file() and not (p.parent==O and p.name in excluded)]
report={'schema':'n36-engineering-r1-runtime-binding-refresh-report-v1','node_id':'15.6','status':'PARTIAL_CLOSURE_BLOCKED','verdict':'NOT_PASS','verdict_scope':'CPU engineering preparation only; no source/release adoption and no scientific success. Reference-only drafts are not helper-certified manifests.','source_commit':a['source_base'],'authority':rec(O/'authority-v1.json'),'started_at':a['at'],'completed_at':now.isoformat(),'elapsed_since_authority_seconds':(now-datetime.datetime.fromisoformat(a['at'])).total_seconds(),'timeout_seconds':1200,'deadline':a['deadline'],'runtime_preparation':a['runtime_preparation'],'runtime_amendment':a['runtime_amendment'],'source_review':a['source_review'],'prepared':{'runtime':plan['runtime'],'runtime_source_record':runtime['preparation']['source_record'],'audit_view':plan['audit_plan'],'audit_manifests_count':40,'engineering_manifest':plan['engineering_manifest'],'engineering_draft_plan':rec(O/'engineering-plan.draft-disabled-v1.json'),'bindings':rec(O/'bindings.disabled-v1.json'),'binding_diff':rec(O/'binding-diff.disabled-v1.json'),'all_manifests_reference_refreshed':True,'all_manifests_helper_certified':False,'affected_graph_validation_complete':False,'generation_method':'Exact reference-only transformation of attempt-2 manifests; original helpers invoked unchanged and their canonical-runtime failures retained. Source, scope, accounting, deployment, native build and scientific equivalence bindings reused unchanged.'},'validated_partial_closure':passed,'validator_results':g['checks'],'validator_totals':{'pass':len(passed),'fail':len(failures)},'commands':[{'argv':['/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12','-B',str(O/'refresh-disabled-v1.py')],'environment_overrides':{'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TMPDIR':str(O/'cpu-tmp')},'cwd_at_validation':plan['worktree'],'exit_code':0,'note':'Script captures individual validator failures; process exit zero does not imply validation acceptance.','log':rec(O/'refresh-disabled-v1.log'),'results':rec(O/'generation-results-v1.json')},{'argv':['python','-B',str(O/'finalize-report-v1.py')],'exit_code':0,'validation':'All finalizer assertions passed before report creation.'}]+g['commands']+commands,'blocking_findings':[{'id':'R1-CANONICAL-RUNTIME-SPECIFICATION-PIN','message':'Reviewed source pins the old 001597 runtime in the hash-bound R1 specification. The prospective 001631-derived source-bound runtime is rejected by validate_plan_shape, validate_audit_view, audit_mapping, full audit closure, all40 audit helpers and the R1 manifest helper. No validator was changed or bypassed.','source_locations':['scripts/qd_ed_n36_engineering_r1.py:222','scripts/qd_ed_n36_engineering_r1.py:287'],'required_resolution':'Separately authorized and reviewed operational source/specification amendment accepting the exact prospective runtime binding, followed by affected graph/helper regeneration and CPU revalidation. Source edits forbidden in this executor scope.'},{'id':'CONTROLLER-INDEPENDENT-ROOT-REVIEW-PENDING','message':'Direct unmodified verify_semantics fails: reviewed controller semantics required. Proposal remains PENDING_INDEPENDENT_AND_ROOT_REVIEW.'},{'id':'RUNTIME-READINESS-FALSE','message':'Readiness deliberately false. Full audit closure also requires cuda_egl_verified and provider_ready true at qd_ed_n36_release.py runtime predicate; this downstream predicate was not reached due to the canonical runtime gate. No fresh probe exists or was fabricated.'}],'pending_gates':['Resolve reviewed source/specification canonical runtime pin through separately scoped reviewed changes; regenerate via helpers and rerun full CPU validators.','Independent and root controller/runtime semantics review on final exact bindings.','Independent B5 on exact final bindings.','Root adoption and prospective frozen plan.','Fresh separately authorized health/readiness procedure; inherited readiness remains false.','Distinct health and episode releases; no enabled release in this scope.'],'unchanged_ledgers':ledger,'preservation':{'immediate_input_hashes_unchanged':True,'source_commits_and_placement_unchanged':True,'native_build_dependency_model_and_scientific_bytes_preserved':True,'all41_manifest_scientific_fields_unchanged':True,'runtime_change_only':'preparation.source_record','closure_change_only':'runtime reference','historical_manifests_unchanged':True,'owner_state_driver_locks_ledger_mutations':False,'gpu_operations':0,'health_operations':0,'provider_calls':0,'nested_executors':0,'readiness_flags':{'cuda_egl_verified':False,'provider_ready':False,'gpu_mapping.cuda_egl_verified':False,'runtime_ready':False},'final_verification':verification},'inputs':g['inputs'],'outputs':outputs,'output_hash_scope':'All executor-created immutable artifacts before report; report self-hash in report-v1.sha256.json. Live wrapper files and preexisting authority excluded from output inventory.','release_enabled':False,'gpu_authorized':False,'scientific_success':False}
report['supplemental_config_validation']={'evidence':rec(O/'config-recomposition-v1.json'),'status':'PASS','count':41,'original_failure_retained':True,'diagnosis':'Initial supplemental comparison compared Python tuples to JSON lists for qd_grid_shape and qd_bounds_quantiles. Exact composed hashes passed; repeating the resolved comparison with production JSON normalization passes all41. No production validator changed.'}
report['validator_totals']['note']='Pass count includes one supplemental all41 recomposition check. Fail count retains original tuple/list diagnostic failure.'
report['commands'].append({'argv':['/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12','-B',str(O/'check-configs-v1.py')],'environment_overrides':report['commands'][0]['environment_overrides'],'exit_code':0,'log':rec(O/'check-configs-v1.log'),'results':rec(O/'config-recomposition-v1.json')})
save('report-v1.json',report);save('report-v1.sha256.json',rec(O/'report-v1.json'))
print(json.dumps({'status':report['status'],'validator_totals':report['validator_totals'],'report':rec(O/'report-v1.json')}))
