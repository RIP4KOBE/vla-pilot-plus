"""Bounded CPU artifact preparation only; never grant release or modify source/state."""
import copy, datetime as dt, hashlib, json, os, subprocess, sys, time
from pathlib import Path
ROOT=Path.cwd().resolve(); OUT=ROOT.parent/'prospective-recovery-release-v2'
sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n32_prepare as prep, qd_ed_n32_contract as c, qd_ed_n32_bridge as b, qd_ed_n32_release as rel, qd_ed_n23_worker as w
from scripts import qd_ed_final_runner as r
START=time.monotonic(); SOURCE='1065f38122379a515b60a9a424f574330405b66f'
def put(name,obj):
 p=OUT/name; w.atomic_json(p,obj); return c.ref(p)
def read(p): return json.loads(Path(p).read_text())
def safe(p):
 s=str(p).lower()
 assert '2026-08-10-eds-qd-stage-guidance-transition-design.md' not in s
 assert not any(x in s for x in ('credentials','auth.json','api_key'))
def ref(p): safe(p); return c.ref(p)
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==SOURCE
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
auth=w.read_ref(ref(OUT/'authority-v1.json')); amendment=w.read_ref(auth['accounting_amendment'])
assert amendment['retained_history']['dispatched']==423 and amendment['retained_history']['gpu_hours_consumed']==56.92968407644514
assert amendment['finite_new_cohort']==c.LIMITS and amendment['new_cohort']==c.COHORT
oldpath=ROOT.parent/'root-recovery-release-v1/plan.frozen.v1.json'
old=w.read_ref(ref(oldpath)); previous_runtime=w.read_ref(old['runtime'])
storage=Path(previous_runtime['artifact_root'])/'variants/n32_archive_eligible_capture/prospective-recovery-release-v2'
assert not storage.exists(); storage.mkdir(parents=True)
(OUT/'payload').symlink_to(storage,target_is_directory=True)
# Preserve every inventory entry and fingerprint. Rebind lexical checkout only;
# missing dependencies are blockers, never silently omitted or imported elsewhere.
oldroot=previous_runtime['worktree']
def rebase(x):
 if isinstance(x,str): return x.replace(oldroot,str(ROOT))
 if isinstance(x,list): return [rebase(v) for v in x]
 if isinstance(x,dict): return {k:rebase(v) for k,v in x.items()}
 return x
runtime=rebase(copy.deepcopy(previous_runtime))
for record in runtime['files']:
 safe(record['path'])
 if record['path'].startswith(str(ROOT)+'/'):
  record['resolved_path']=str(Path(record['path']).resolve())
runtime_ref=put('payload/runtime.n32r2.candidate-v1.json',runtime)
provenance=put('runtime-provenance-v1.json',{
 'schema':'n32r2-runtime-provenance-v1','template':old['runtime'],'candidate':runtime_ref,
 'operation':'lexical checkout rebinding; preserve all 3291 file fingerprints and task/cache/provider contracts',
 'old_worktree':oldroot,'new_worktree':str(ROOT),'runtime_readiness':'Inherited historical assertions only; no fresh GPU or provider probe',
 'execution_authorized':False,'http_counters':'Unknown'})
draft=prep.prepare(OUT/'payload/draft-v1',runtime_ref,root=ROOT)
draft_ref=ref(OUT/'payload/draft-v1/plan.draft.json')
assert draft['source']['commit']==SOURCE
put('source-closure-v1.json',draft['source'])
protocol={'schema':'n32-production-protocol-v1','cohort':c.COHORT,'episodes':draft['episodes'],
 'limits':c.LIMITS,'worker_contract':c.WORKER_CONTRACT,'attempt_identity':'episode_key','deadline':c.DEADLINE,
 'promotion':{'all_valid_cells':30,'n32_min_successes':5,'matched_controls_required':True},
 'futility':'complete_valid_triples_only','validation_authorized':False,'formal_authorized':False}
protocol_ref=put('protocol.candidate-v1.json',protocol)
old_authority=w.read_ref(old['authority'])
authority=copy.deepcopy(old_authority)
authority.update(approved=False,cohort=c.COHORT,starts_at=amendment['at'],limits=c.LIMITS,
 retained_history=amendment['retained_history'],ledger_prefixes=amendment['ledger_prefixes'],arithmetic=amendment['arithmetic'],
 caps=amendment['unchanged_caps'],weekly_window=amendment['unchanged_weekly_window'],
 previous_cohort_authority=old['authority'],recovery_accounting_amendment=auth['accounting_amendment'])
authority['approval_basis']=amendment['authority']
authority['authority_scope']='UNAPPROVED CANDIDATE: finite N32R2 Dev cohort; root production review and owning adoption required. No protected phase or reserve borrowing.'
authority_ref=put('budget-authority.candidate-v1.json',authority)
plan=copy.deepcopy(draft)
for k in ('root_review','execution_release'):plan.pop(k)
plan.update(schema='n32-released-plan-v1',frozen=True,release_enabled=False,protocol=protocol_ref,
 authority=authority_ref,attempt_identity='episode_key')
for k in ('run_name','input_contract_label'):plan[k]=old[k]
for k in ('runtime_inventory','seed_plan'):
 p=ROOT/'data'/Path(old[k+'_path']).name
 assert w.sha(p)==old[k+'_sha256']
 plan[k+'_path']=str(p);plan[k+'_sha256']=old[k+'_sha256']
plan_ref=put('plan.frozen.CANDIDATE-v1.json',plan)
common={'schema':'n32-execution-release-v1','approved':False,'plan':plan_ref,'authority':authority_ref,
 'protocol':protocol_ref,'source':plan['source'],'runtime':runtime_ref,'limits':c.LIMITS,
 'phase_authorization':plan['phase_authorization']}
review_ref=put('root-production-review.CANDIDATE-v1.json',dict(common,schema='n32-root-production-review-v1',decision='PENDING_INDEPENDENT_ROOT_REVIEW'))
release_ref=put('execution-release.CANDIDATE-v1.json',dict(common,root_review=review_ref))
# Pure API and artifact checks: no launch, no monkeypatching of release trust.
c.validate_draft(draft)
shape=copy.deepcopy(plan);shape.update(release_enabled=True,phase_authorization={'dev':True,'validation':False,'formal':False})
rel.validate_plan(shape)  # In-memory shape only; no approval written or passed to execution.
w.verify_source(ROOT,plan['source'])
assert b.source_paths(ROOT)=={v['path'] for v in plan['source']['files']}
loaded=b.attest_loaded(ROOT,plan['source'])
from scripts import qd_ed_n32_worker as worker
worker_loaded=worker.attest_worker_loaded(ROOT,plan['source'])
manifest_refs=[]; commands=[]
for row in plan['episodes']:
 reference=plan['expected_manifests'][row['episode_key']]
 actual=w.read_ref(reference)
 assert actual==json.loads(json.dumps(b.manifest(plan,runtime,row)))
 assert actual['argv'][1]==str(ROOT/'main.py')
 assert not Path(actual['output_dir']).exists()
 context=worker.context_for(plan_ref,row,release_ref)
 context_ref=put('payload/contexts/'+row['episode_key']+'.CANDIDATE.json',context)
 commands.append({'episode_key':row['episode_key'],'cwd':str(ROOT),'context':context_ref,
  'argv':[actual['argv'][0],'-m','scripts.qd_ed_n32_worker','--context',context_ref['path'],'--context-sha256',context_ref['sha256']],
  'execution_authorized':False})
 manifest_refs.append(reference)
put('worker-entrypoints.CANDIDATE-v1.json',{'schema':'n32r2-worker-entrypoints-candidate-v1','worker_source':ref(ROOT/'scripts/qd_ed_n32_worker.py'),
 'attestation':worker_loaded['scripts.qd_ed_n32_worker'],'commands':commands,'executed':False})
errors=[];verified=[]
for record in runtime['files']:
 try:r.verify_files([record],allowed_roots=(str(ROOT),runtime['worktree'],runtime['artifact_root']))
 except Exception as e:errors.append({'path':record['path'],'expected_sha256':record['sha256'],'error':str(e)})
 else:verified.append(record['path'])
inventory_check=put('runtime-inventory-check-v1.json',{'total':len(runtime['files']),'verified':len(verified),'failures':errors})
# Frozen model weight hashes are an independent root gate; no model loading.
r.validate_runtime_inputs(plan,runtime,b.profiles(ROOT),ROOT,{'artifacts':runtime['artifact_root']},require_frozen=False)
fingerprints={str(Path(x['path']).resolve()) for x in runtime['files']}
for task in runtime['tasks'].values():
 actual={str(p.resolve()) for p in Path(task['cache_dir']).rglob('*') if p.is_file()}
 assert actual and actual<=fingerprints
try:rel.validate_release(plan_ref,release_ref)
except Exception as e:release_rejection={'exception':type(e).__name__,'message':str(e)}
else:raise AssertionError('unapproved candidate unexpectedly accepted')
# Hash-only history integrity; do not read result payloads or parse protected outcomes.
for name,anchor in amendment['ledger_prefixes'].items():rel.prefix(anchor['path'],anchor)
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
result={'schema':'n32r2-cpu-candidate-validation-v1','source_commit':SOURCE,'source_inventory_count':len(plan['source']['files']),
 'draft':draft_ref,'plan':plan_ref,'release':release_ref,'protocol':protocol_ref,'authority':authority_ref,
 'manifest_count':len(manifest_refs),'manifest_recomposition':'PASS_ALL_30','manifest_refs':manifest_refs,
 'source_verification':'PASS','worker_attestation':worker_loaded['scripts.qd_ed_n32_worker'],
 'released_plan_shape':'PASS_IN_MEMORY_ONLY','candidate_release_rejection':release_rejection,
 'task_seed_cache_checks':'PASS_REQUIRE_FROZEN_FALSE','checkpoint_encoder_weight_hashes':'NOT_RUN_ROOT_REQUIRED',
 'runtime_inventory_check':inventory_check,'runtime_inventory_failure_count':len(errors),
 'history_prefixes':'PASS_HASH_ONLY','history':amendment['retained_history'],'arithmetic':amendment['arithmetic'],
 'no_old_outcome_reuse':True,'runtime_provenance':provenance,'gpu_dispatched':False,'http_counters':'Unknown',
 'source_clean':True,'elapsed_seconds':time.monotonic()-START,
 'direct_templates':[ref(oldpath),old['authority'],old['protocol'],old['runtime'],ref(ROOT.parent/'release-preparation-v1/verify-draft-v1.py'),ref(ROOT/'scripts/qd_ed_n31_prepare.py')],
 'authority_inputs':[ref(OUT/'authority-v1.json'),auth['accounting_amendment']],
 'blockers':['Independent root production approval absent','Implementation checkout runtime inventory incomplete: '+str(len(errors))+' failed entries',
 'Root must settle execution checkout, owning state/ledger adoption, full frozen weight verification and live admission before dispatch']}
put('validation-v1.json',result)
print(json.dumps({k:result[k] for k in ('source_commit','source_inventory_count','manifest_count','runtime_inventory_failure_count','elapsed_seconds','blockers')},indent=2))
