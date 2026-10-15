import pathlib,json,hashlib,datetime,subprocess,fcntl
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001832';packet=base/'turns/001827/disabled-v3-binding';old=base/'turns/001820';now=datetime.datetime.now(datetime.timezone.utc).isoformat();source='cd6c969cbfdf006fd017553448bed2e61fc0380e';before='f661a570403e9ff7224d4c35230a0f2b9321a269';dest=P('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(n,v):
 p=out/n;assert not p.exists();p.write_text(json.dumps(v,indent=2)+'\n');return ref(p)
def check(a):
 p=P(a['path']);assert ref(p)['sha256']==a['sha256'];return json.loads(p.read_text())
def git(*a):return subprocess.check_output(['git','-C',str(dest),*a],text=True).strip()
assert not (base/'STOP').exists() and not (base/'STOP.json').exists();auth=check({'path':str(base/'user-authorization-v1.json'),'sha256':'a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c'});assert now<auth['continuous_window']['end_utc']
prev=json.loads((base/'turns/001831/operational-summary-v1.json').read_text());receipt=json.loads((base/'turns/001831/receipt.json').read_text());assert receipt['exit']==0
candidate=json.loads((packet/'controller-semantics.pending-disabled-v1.json').read_text());assert candidate['source_commit']==source
for k in ['runtime','runtime_closure']:check(candidate[k])
with (root/'data/qd-ed-runner.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for a in prev['ledger_prefixes'].values():assert ref(P(a['path']))['sha256']==a['sha256'] and P(a['path']).stat().st_size==a['bytes']
 assert git('rev-parse','HEAD')==before and not git('status','--short','--untracked-files=no')
 changed=git('diff','--name-only',before,source).splitlines();assert set(changed)=={'scripts/qd_ed_n36_engineering_r1.py','tests/test_n36_engineering_r1.py'}
 subprocess.run(['git','-C',str(dest),'merge-base','--is-ancestor',before,source],check=True)
 reviews={}
 for key in ['set_goal','scale_action','wrapper_and_gripper']:
  prior=old/(key+'-root-reviewed-v1.json');r=json.loads(prior.read_text())
  for a in r['sources']:assert ref(P(a['path']))['sha256']==a['sha256']
  r.update(at=now,source_commit=source,runtime=candidate['runtime'],runtime_closure=candidate['runtime_closure'],prior_review=ref(prior),reviewer='owning_root_coordinator_turn001832',review_scope='Scoped carry-forward of prior static source review: exact hashes of all seven source files reverified; commit delta restricted to recovery accounting and tests. No native instance, physical gain, full graph or release acceptance claimed.')
  reviews[key]=write(key+'-root-reviewed-v1.json',r)
 candidate.update(status='ROOT_REVIEWED_STATIC_SEMANTICS_DISABLED',review_evidence=reviews,historical_review_only=ref(old/'controller-semantics.root-reviewed-disabled-v1.json'))
 proof=write('controller-semantics.root-reviewed-disabled-v1.json',candidate)
 review=write('controller-verification-v1.json',{'at':now,'status':'PASS_SCOPED_UNCHANGED_SOURCE_CONTROLLER_REVIEW','source':source,'changed_paths':changed,'proof':proof,'all_seven_source_hashes_verified':True,'native_execution_observed':False,'release_enabled':False,'independent_review_claimed':False})
 authority=write('source-placement-authority-v1.json',{'schema':'n36-reviewed-source-placement-authority-v1','at':now,'authority':ref(base/'user-authorization-v1.json'),'review':ref(base/'turns/001826/root-scoped-review-v1.json'),'recovery_review':ref(base/'turns/001831/recovery-binding-review-v1.json'),'destination':str(dest),'before':before,'after':source,'operation':'Fast-forward only in isolated adapter checkout; no new source edits','gpu_authorized':False,'measurement_authorized':False,'budget_delta_attempts':0,'budget_delta_gpu_hours':0,'ledger_prefixes':prev['ledger_prefixes']})
 merged=git('merge','--ff-only',source)
 assert git('rev-parse','HEAD')==source and not git('status','--short','--untracked-files=no')
 placement=write('source-placement-result-v1.json',{'schema':'n36-reviewed-source-placement-result-v1','at':now,'authority':authority,'before':before,'after':source,'destination':str(dest),'tracked_clean':True,'merge_output':merged,'gpu_dispatches':0,'measurement_authorized':False,'remaining_gates':['complete_graph','finite_release','native_readiness','scientific_promotion']})
 for a in prev['ledger_prefixes'].values():assert ref(P(a['path']))['sha256']==a['sha256']
 print(json.dumps({'review':review,'proof':proof,'placement':placement}))
