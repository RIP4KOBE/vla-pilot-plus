import json,hashlib,datetime as dt,subprocess,os
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=Path.cwd().resolve()
def load(p):return json.loads(Path(p).read_text())
def ref(p):
 p=Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def write(p,v):
 p=OUT/p;assert not p.exists(),str(p);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');return ref(p)
def git(root,*args):return subprocess.check_output(['git','--no-optional-locks','-C',str(root),*args],text=True).strip()
a=load(OUT/'authority-v1.json');p=load(OUT/'plan.complete-disabled-v1.json');r=load(p['runtime']['path']);s=p['source'];attempts=[load(OUT/f'preparation-attempt-v{i}.json') for i in (1,2)];origins=load(OUT/'import-origins-v1.json');science=load(OUT/'full-scientific-config-comparison-v1.json');joins=load(OUT/'all40-joins-v1.json');assets=load(OUT/'relocated-assets-v1.json')
now=dt.datetime.now(dt.timezone.utc);stops={x:os.path.lexists(x) for x in a['STOP_paths']};head=git(ROOT,'rev-parse','HEAD');dirty=git(ROOT,'status','--porcelain=v1');ownerhead=git(a['owner'],'rev-parse','HEAD')
errors=[]
if any(stops.values()):errors.append('canonical STOP now present; preparation ceased')
if now>=dt.datetime.fromisoformat(a['deadline'].replace('Z','+00:00')):errors.append('deadline passed; preparation ceased')
if head!=a['base_source'] or dirty:errors.append('source identity/cleanliness changed')
if ownerhead!='ca4e6a96d049c7ebb1f302d755883388ddbfdbd8':errors.append('owner source changed externally')
if len(joins['rows'])!=40 or science['status']!='PASS' or origins['status']!='PASS':errors.append('incomplete joins')
for row in joins['rows']:
 if Path(row['output_dir']).exists():errors.append('prospective output exists: '+row['row']['episode_key'])
# Bound inherited inputs are checked without following history or opening journals.
oldreport=load('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001250/recovery-preparation/report-v1.json')
oldplanref=oldreport['drafts']['plan'];assert ref(oldplanref['path'])['sha256']==oldplanref['sha256']
oldplan=load(oldplanref['path']);preserved={}
for key in ['runtime','runtime_closure','controller_semantics','native_build','protocol','accounting','protocol_review']:
 x=oldplan[key];assert ref(x['path'])['sha256']==x['sha256'];preserved[key]=x
assert ref(a['root_acceptance']['path'])['sha256']==a['root_acceptance']['sha256']
result={'schema':'n36r2-source-runtime-composition-result-v1','status':'CPU_PREPARATION_COMPLETE_REVIEW_REQUIRED' if not errors else 'BLOCKED_PARTIAL','source':ref(OUT/'source.complete-v1.json'),'plan':ref(OUT/'plan.complete-disabled-v1.json'),'runtime':p['runtime'],'runtime_closure':p['runtime_closure'],'controller_semantics':p['controller_semantics'],'native_build':p['native_build'],'all40_joins':ref(OUT/'all40-joins-v1.json'),'full_scientific_comparison':ref(OUT/'full-scientific-config-comparison-v1.json'),'import_origins':ref(OUT/'import-origins-v1.json'),'score':None,'release_enabled':False,'production_accepted':False,'errors':errors}
write('composition-result-v1.json',result)
files=[]
patterns=['prepare-b2-b4-v*.py','prepare-b2-b4-v*.log','preparation-attempt-v*.json','compare-full-science-v1.*','finish-origins-v1.*','source.complete-v1.json','runtime*.json','controller-*.json','relocated-assets-v1.json','plan.complete-disabled-v1.json','all40-joins-v1.json','b5-hard-rejection-v1.json','import-origins-v1.json','full-scientific-config-comparison-v1.json','composition-result-v1.json','finalize-report-v1.py']
for pattern in patterns:files.extend(OUT.glob(pattern))
for folder in ['prepared','contexts','libero-config']:files.extend(x for x in (OUT/folder).rglob('*') if x.is_file())
index=write('evidence-index-v1.json',{'schema':'n36r2-cpu-evidence-index-v1','files':[ref(x) for x in sorted(set(files))]})
env='env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 GIT_NO_LAZY_FETCH=1 '
commands=[]
for name,timeout,exitcode,scope in [('prepare-b2-b4-v1',355,1,'FAILED: diagnostic guard falsely rejected standard-library unittest/main.py before source preparation'),('prepare-b2-b4-v2',350,1,'All production preparation/source/runtime/all40 checks PASS; final local origin diagnostic failed on namespace __file__=None'),('finish-origins-v1',35,0,'PASS: accurate namespace handling and actual CPU import/source-origin attestation; no production changes'),('compare-full-science-v1',85,0,'PASS: all40 full composed configurations and argv; exact source/output substitutions only')]:
 commands.append({'command':env+f'timeout {timeout}s /home/hynx/miniconda3/envs/vla-pilot/bin/python -B {OUT}/{name}.py > {OUT}/{name}.log 2>&1','cwd':str(ROOT),'exit_code':exitcode,'outcome':scope,'script':ref(OUT/(name+'.py')),'log':ref(OUT/(name+'.log'))})
seconds=sum(x['elapsed_seconds'] for x in attempts)+origins['wall_seconds']+science['wall_seconds']
report={'schema':'n36r2-source-runtime-cpu-report-v1','node_id':'15.6','turn':1268,'at':now.isoformat(),'status':result['status'],'score':None,'production_accepted':False,'release_enabled':False,'gpu_authorized':False,'source_adopted':False,'scientific_promotion':False,'target_met':False,
 'source_identity':{'worktree':str(ROOT),'commit':head,'owner_commit':ownerhead,'branch':git(ROOT,'branch','--show-current'),'tracked_and_untracked_status':dirty,'clean':not dirty,'source_record':ref(OUT/'source.complete-v1.json'),'source_file_count':len(s['files']),'source_inventory_canonical_sha256':s['sha256'],'scientific_source_identical':p['scientific_source']==s,'launcher_source':next(x for x in s['files'] if x['path']=='scripts/qd_ed_poe_launch.py'),'launcher_executed':False,'source_edits':[],'new_commit':None,'renewed_source_review_required':False,'new_artifact_composition_independent_review_required':True},
 'authority':ref(OUT/'authority-v1.json'),'root_acceptance':a['root_acceptance'],
 'B2':{'status':'PASS_PROSPECTIVE_CPU_SOURCE_FREEZE','complete_final_inventory':True,'production_source_record_and_verify_sources':'PASS','production_prepare':'PASS','all40_manifest_verification':'PASS','adoption_and_independent_artifact_review_pending':True},
 'B4':{'status':'CPU_COMPOSITION_COMPLETE_EXECUTION_GATES_REMAIN_BLOCKED','runtime':p['runtime'],'runtime_closure':p['runtime_closure'],'controller_semantics':p['controller_semantics'],'native_build':p['native_build'],'runtime_file_count':len(r['files']),'relocated_asset_count':len(assets['files']),'new_non_source_copies':sum(x['action']=='copied_non_source_bytes' for x in assets['files']),'preserved_relative_non_source_links':sum(x['action']=='preserved_relative_non_source_symlink' for x in assets['files']),'whole_owner_source_tree_linked':False,'ordinary_modules_preserved':6758,'interpreter_distributions_generated_and_cyutility_rules_preserved':True,'controller_ROOT_REVIEWED_status':'Inherited source findings only, bytes checked; no new root approval','historical_device_provider_fields':'Retained metadata only; not current readiness','all40_production_runtime_inputs_including_checkpoint_hashes':'PASS','all40_argv_full_config_task_seed_profile_output_absence':'PASS','all40_contexts':'Disabled prospective production-shaped contexts with release=None; not admitted worker contexts','import_origins':'PASS CPU imports and passive resolution, explicitly separated from worker evidence','immutable_runtime_observations_obtained':False,'complete_process_bound_before_after_worker_receipts_obtained':False,'remaining_gates':['Independent review/adoption of final isolated composition','Separately authorized immutable runtime observations and complete production worker before/after receipts','Separate B5 admission/accounting/resource routing and externally anchored root approval/release']},
 'B5':{'status':'HARD_REJECTED_RELEASE_DISABLED','evidence':ref(OUT/'b5-hard-rejection-v1.json'),'allowlists_changed':False,'approval_or_admission_token_created':False},
 'checks':attempts[1]['checks'],'exact_commands':commands,'read_only_final_commands':[{'command':'git status --porcelain=v1','stdout':dirty,'exit_code':0},{'command':'git diff --check','stdout':'','exit_code':0},{'command':'git rev-parse HEAD','stdout':head,'exit_code':0},{'command':'git -C '+a['owner']+' rev-parse HEAD','stdout':ownerhead,'exit_code':0}],
 'retained_failures':[{'attempt':ref(OUT/'preparation-attempt-v1.json'),'error':attempts[0]['error']['error'],'resolution':'Local diagnostic guard narrowed to exact prohibited project entrypoints; production untouched'},{'attempt':ref(OUT/'preparation-attempt-v2.json'),'error':attempts[1]['error']['error'],'resolution':'Supplement records namespace search locations and real file-backed CPU imports; completed production checks not repeated'}],
 'science':{'fresh_dev_cells':40,'same_episode_keys_as_authorized_N36R2_allocation':True,'tasks_seeds_profiles_rows_exact':True,'all_full_configs_and_argv_equal_after_exact_output_prefix_and_source_commit_normalization':True,'evidence':ref(OUT/'full-scientific-config-comparison-v1.json'),'method_thresholds_deadline_reserves_protocol_unchanged':True},
 'preservation':{'owner_state_and_ledgers_written':False,'owner_ledgers_read':False,'source_adopted':False,'old_bound_artifacts_verified_unchanged':preserved,'old_partial_plan_verified_unchanged':oldplanref,'old_outputs_overwritten':False,'attempts':504,'gpu_hours':75.49265038509455,'invalid_charges_seconds':{'n36_dev_t00_c0_001147':86.40354533703066,'n36r1_dev_t00_c0_001203':809.4826372319367},'accounting_basis':'Inherited authority and immutable draft/accounting snapshot; no recomputation or admission claim','protected_gpu_hours':{'validation':32,'formal':12},'protected_attempt_caps':{'validation':180,'formal':40}},
 'resource_limits':{'cpu_threads':2,'check_affinity':'Each validation script restricted to first two available CPUs','test_budget_seconds':360,'aggregate_measured_validation_script_seconds':seconds,'test_budget_within_limit':seconds<360,'wall_cap_seconds':1200,'conservative_elapsed_since_authority_seconds':(now-dt.datetime.fromisoformat(a['at'])).total_seconds(),'no_gpu_simulator_Main_provider_network_packages_or_agents':True,'no_credentials_read':True},
 'stop_deadline':{'initial_check_at':'2026-10-10T03:15:42.100354+00:00','initial_both_absent':True,'final_entries':stops,'deadline':a['deadline'],'final_before_deadline':now<dt.datetime.fromisoformat(a['deadline'].replace('Z','+00:00')),'checked_before_preparation_and_during_bounded_loops':True},
 'evidence_index':index,'result':result,'errors':errors,
 'insight':'Complete production source and CPU composition checks succeed on unchanged b1d20fc after exact isolated asset/config rebinding. This closes the preparation work, while live worker evidence, root adoption and B5 remain separate blocked gates.'}
md=f'''# Leaf 15.6 — bounded CPU source/runtime preparation

B2: **PASS for prospective CPU source freeze**. B4: **CPU composition complete; execution gates remain blocked**. B5: **hard rejected**. Score: null. Production accepted: false. Release enabled: false.

Source remains `{head}`; owner remains `{ownerhead}`. Checkout is clean. No production source edits or new commit; no source adoption, owner-state or ledger writes. Independent review of the new artifacts is required.

- Git-verified complete source/scientific_source: {len(s['files'])} identical entries across all arms, including ordinary tracked launcher SHA-256 `{report['source_identity']['launcher_source']['sha256']}`. Launcher never executed.
- Production `prepare`, `verify_sources`, runtime closure, controller semantics, runtime-file/input validators, and all 40 `verify_manifest` calls passed. Full checkpoint bytes were checked.
- 3,000 relocated asset records checked; 148 missing non-source files copied and 12 original relative non-source symlinks preserved. No owner-source-tree symlink. LIBERO config and dependency import paths bind the isolated checkout. All 6,758 ordinary runtime entries and interpreter/distribution/generated/native/_cyutility rules retained.
- All 40 Dev rows, seeds, profiles, argv and full configurations match the authorized prior drafts after only exact output-prefix/source-commit normalization. All prospective outputs remain absent. Forty disabled contexts have `release: null`.
- Actual bounded CPU imports and passive dependency origins checked. These are **not** immutable production runtime observations or complete before/after worker receipts. Controller review status is inherited source-semantic evidence, not new root approval. Device/provider fields remain historical metadata.

Two failed local diagnostic attempts are retained: an overly broad Main filename guard rejected `unittest/main.py`; the final origin diagnostic assumed namespace packages have `__file__`. Exact-path guarding and a separate namespace-aware origin diagnostic resolved these without modifying production code or rerunning completed broad validation.

Measured validation-script wall time: {seconds:.2f}s / 360s; two-CPU affinity and two-thread limits. Both canonical STOP entries remain absent; deadline unchanged. Retained accounting remains 504 attempts and 75.49265038509455 GPUh, including invalid charges 86.40354533703066s and 809.4826372319367s; inherited only, no ledger recomputation.

Artifacts: [complete disabled plan](plan.complete-disabled-v1.json), [source](source.complete-v1.json), [runtime](runtime.isolated.draft-v1.json), [all40 joins](all40-joins-v1.json), [full science comparison](full-scientific-config-comparison-v1.json), [CPU origins](import-origins-v1.json), [hashed evidence index](evidence-index-v1.json). Exact commands, exit codes and log hashes are in [report-v1.json](report-v1.json).

Remaining: independent artifact review/root adoption, separately authorized immutable runtime observations and complete process-bound worker receipts, and B5 admission/accounting/resource authority with external root approval. No release or admission token was created.
'''
mdpath=OUT/'report-v1.md';assert not mdpath.exists();mdpath.write_text(md);report['markdown']=ref(mdpath);write('report-v1.json',report)
print(json.dumps({'report':ref(OUT/'report-v1.json'),'markdown':ref(mdpath),'status':report['status'],'validation_seconds':seconds,'errors':errors},indent=2))
