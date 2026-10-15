import sys,json,copy,time,datetime,subprocess
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root),str(root/'scripts')]
from scripts import qd_ed_n32_prepare as prep, qd_ed_n32_contract as c, qd_ed_n32_bridge as b, qd_ed_n32_release as rel, qd_ed_n23_worker as w, qd_ed_final_runner as r, qd_ed_n32_worker as worker
out=root.parent/'variants/n32_archive_eligible_capture/root-recovery-release-v2'
prior=out.parent/'prospective-recovery-release-v2'
def put(p,o):
 assert not p.exists(),str(p)
 w.atomic_json(p,o);return c.ref(p)
start=time.monotonic();original=w.read_ref(c.ref(prior/'plan.frozen.CANDIDATE-v1.json'))
oldruntime=w.read_ref(c.ref(prior/'payload/runtime.n32r2.candidate-v2.json'))
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==original['source']['commit']=='1065f38122379a515b60a9a424f574330405b66f'
assert not Path(c.stop_path(root)).exists() and not Path(c.stop_path(root)).is_symlink()
state=r.read_state(root/'research-state.yaml')
for k in ['n32_worker_entrypoint_adoption','n32r2_identity_adoption']:
 adoption=w.read_ref(state[k]);review=w.read_ref(adoption['review'])
 assert adoption['gpu_dispatched'] is False
# Rebind only lexical checkout locations; preserve all file hashes and task/provider contracts.
def rebase(x):
 if isinstance(x,str):return x.replace(oldruntime['worktree'],str(root))
 if isinstance(x,list):return [rebase(v) for v in x]
 if isinstance(x,dict):return {k:rebase(v) for k,v in x.items()}
 return x
runtime=rebase(copy.deepcopy(oldruntime))
for rec in runtime['files']:rec['resolved_path']=str(Path(rec['path']).resolve())
assert [v['sha256'] for v in runtime['files']]==[v['sha256'] for v in oldruntime['files']]
storage=Path(runtime['artifact_root'])/'variants/n32_archive_eligible_capture/root-recovery-release-v2'
assert not storage.exists();storage.mkdir(parents=True);(out/'payload').symlink_to(storage,target_is_directory=True)
runtime_ref=put(out/'payload/runtime.owning-v1.json',runtime)
prov=put(out/'owning-checkout-rebind-v1.json',{'schema':'n32r2-owning-checkout-rebind-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_runtime':c.ref(prior/'payload/runtime.n32r2.candidate-v2.json'),'runtime':runtime_ref,'reason':'Implementation checkout has stale separate state and journals; owning checkout has all 3291 exact dependency hashes. Execute only against authoritative owning state and locks.','source':original['source']['commit'],'scientific_change':False,'copied_or_linked_ledger':False,'gpu_dispatched':False})
draft=prep.prepare(out/'payload/draft-v1',runtime_ref,root=root)
assert draft['source']['files']==original['source']['files']
protocol=w.read_ref(original['protocol']);assert draft['episodes']==protocol['episodes']
protocol_ref=put(out/'protocol-v1.json',protocol)
auth=w.read_ref(original['authority']);authority_input=c.ref(prior/'budget-authority.candidate-v1.json')
for anchor in auth['ledger_prefixes'].values():rel.prefix(anchor['path'],anchor)
events=r.read_events(root/'data/attempt-ledger.jsonl');resources=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl')
snap=r.budget_snapshot(events,resources)
assert snap==auth['retained_history'];assert all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(events).values())
assert not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
# Full owning-checkout verification before granting detached scientific Dev release.
w.verify_source(root,draft['source']);b.attest_loaded(root,draft['source']);worker.attest_worker_loaded(root,draft['source'])
r.verify_files(runtime['files'],allowed_roots=(str(root),runtime['worktree'],runtime['artifact_root']))
plan=copy.deepcopy(draft)
for k in ['root_review','execution_release']:plan.pop(k)
for k in ['run_name','input_contract_label']:plan[k]=original[k]
for k in ['runtime_inventory','seed_plan']:
 path=root/'data'/Path(original[k+'_path']).name
 assert w.sha(path)==original[k+'_sha256'];plan[k+'_path']=str(path);plan[k+'_sha256']=original[k+'_sha256']
r.validate_runtime_inputs(plan,runtime,b.profiles(root),root,{'artifacts':runtime['artifact_root']})
assert auth['arithmetic']['attempts_after_max']==snap['dispatched']+30
assert auth['arithmetic']['gpu_hours_after_max']==snap['gpu_hours_consumed']+5
assert auth['arithmetic']['effective_ceiling']==min(auth['caps']['gpu_hours'],auth['weekly_window']['origin_gpu_hours']+auth['weekly_window']['increment_gpu_hours'])
for row in plan['episodes']:
 manifest=w.read_ref(plan['expected_manifests'][row['episode_key']]);assert not Path(manifest['output_dir']).exists()
 assert manifest==json.loads(json.dumps(b.manifest(plan,runtime,row)))
decision=put(out/'root-review-evidence-v1.json',{'schema':'n32r2-root-review-evidence-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'APPROVE_FINITE_DEV_RELEASE_SUBJECT_TO_OWNING_ADOPTION_AND_LIVE_ADMISSION','source':plan['source']['commit'],'source_files':len(plan['source']['files']),'runtime_inventory_count':len(runtime['files']),'full_frozen_model_task_seed_checks':'PASS','source_worker_entrypoint_attestation':'PASS','manifest_recomposition':'PASS_ALL_30','accounting':snap,'authority_input':authority_input,'rebind':prov,'scientific_protocol':protocol_ref,'existing_worker_review':state['n32_worker_entrypoint_adoption'],'existing_identity_review':state['n32r2_identity_adoption'],'protected_phases_authorized':False,'goal_complete':False,'gpu_dispatched':False})
auth['approved']=True;auth['authority_scope']='Approved finite N32R2 Dev cohort under standing user authorization; exact owning accounting and all prospective scientific gates retained; no protected-phase access or reserve borrowing.'
auth['root_review_evidence']=decision
auth_ref=put(out/'budget-authority-v1.json',auth)
plan.update(schema='n32-released-plan-v1',frozen=True,release_enabled=True,phase_authorization={'dev':True,'validation':False,'formal':False},authority=auth_ref,protocol=protocol_ref,attempt_identity='episode_key')
plan_ref=put(out/'plan.frozen.v1.json',plan)
common={'schema':'n32-execution-release-v1','approved':True,'plan':plan_ref,'authority':auth_ref,'protocol':protocol_ref,'source':plan['source'],'runtime':runtime_ref,'limits':c.LIMITS,'phase_authorization':plan['phase_authorization']}
review_ref=put(out/'root-production-review-v1.json',{**common,'schema':'n32-root-production-review-v1','decision':'APPROVED'})
release_ref=put(out/'execution-release-v1.json',{**common,'root_review':review_ref})
rel.validate_release(plan_ref,release_ref)
commands=[]
for row in plan['episodes']:
 ctx=worker.context_for(plan_ref,row,release_ref);ref=put(out/'payload/contexts'/f"{row['episode_key']}.json",ctx)
 manifest=w.read_ref(plan['expected_manifests'][row['episode_key']]);commands.append({'episode_key':row['episode_key'],'cwd':str(root),'context':ref,'argv':[manifest['argv'][0],'-m','scripts.qd_ed_n32_worker','--context',ref['path'],'--context-sha256',ref['sha256']]})
put(out/'worker-entrypoints-v1.json',{'commands':commands,'executed':False})
result={'schema':'n32r2-final-release-validation-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS','plan':plan_ref,'release':release_ref,'authority':auth_ref,'review_evidence':decision,'source':plan['source']['commit'],'runtime':runtime_ref,'accounting':snap,'elapsed_seconds':time.monotonic()-start,'owning_adoption_pending':True,'live_gpu_admission_pending':True,'gpu_dispatched':False}
put(out/'pre-adoption-validation-v1.json',result)
print(json.dumps(result,indent=2))
