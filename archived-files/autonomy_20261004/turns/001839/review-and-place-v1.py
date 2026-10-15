import pathlib,json,hashlib,datetime,subprocess,fcntl,os,yaml
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001839';now=datetime.datetime.now(datetime.timezone.utc).isoformat();source='808e27f702564fe51db45016e139b68ecb476f8c';before='cd6c969cbfdf006fd017553448bed2e61fc0380e';dest=P('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(n,v):
 p=out/n
 with p.open('x') as f:f.write(json.dumps(v,indent=2)+'\n')
 return ref(p)
def git(*a):return subprocess.check_output(['git','-C',str(dest),*a],text=True).strip()
def checked(r):
 p=P(r['path']);assert ref(p)['sha256']==r['sha256'];return json.loads(p.read_text())
assert not (base/'STOP').exists() and not (base/'STOP.json').exists()
auth=checked(dict(path=str(base/'user-authorization-v1.json'),sha256='a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c'));assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(auth['continuous_window']['end_utc'].replace('Z','+00:00'))
prev=json.loads((base/'turns/001838/terminal-reconciliation-v1.json').read_text());report=checked(prev['report']);assert report['source_commit']==source
with (root/'data/qd-ed-runner.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for r in prev['ledger_prefixes'].values(): assert ref(P(r['path']))['sha256']==r['sha256'] and P(r['path']).stat().st_size==r['bytes']
 assert git('rev-parse','HEAD')==before and not git('status','--short','--untracked-files=no')
 paths=git('diff','--name-only',before,source).splitlines();assert set(paths)=={'scripts/qd_ed_n36_engineering_r1.py','tests/test_n36_engineering_r1.py'}
 subprocess.run(['git','-C',str(dest),'diff','--check',before,source],check=True)
 review=write('root-scoped-review-v1.json',dict(schema='n36-inventory-admission-scoped-root-review-v1',at=now,status='PASS_SCOPED_EXACT_INVENTORY_ADMISSION_SOURCE_PLACEMENT_ONLY',source=source,parent=before,changed_paths=paths,report=prev['report'],terminal_reconciliation=ref(base/'turns/001838/terminal-reconciliation-v1.json'),findings=['Pinned immutable amendment and engineering authority; owning authority digest/length checked.','Whole canonical runtime compared after exactly one approved inventory row replacement; source bytes verified in both recorded deployment and validator checkout.','New previous-specification snapshot explicitly derives from unchanged historical original; scientific, accounting, deadline and release limits retain exact projections.','Negative cases exercise honest rehashed mutations; prior parity failure remains explicitly recorded, not waived.'],tests_reported=report['tests']['result'],tests_repeated=False,limitations=['Scoped source review only; existing validate_private_budget/validate_state parity failure unresolved.','Fresh full graph and controller bindings, release and native readiness still required.','No scientific promotion or completion evidence.'],gpu_authorized=False,measurement_authorized=False))
 authority=write('source-placement-authority-v1.json',dict(schema='n36-reviewed-source-placement-authority-v1',at=now,authority=ref(base/'user-authorization-v1.json'),review=review,destination=str(dest),before=before,after=source,operation='Fast-forward reviewed isolated engineering commit only; no source editing or scientific adoption',budget_delta_attempts=0,budget_delta_gpu_hours=0,ledger_prefixes=prev['ledger_prefixes'],gpu_authorized=False,measurement_authorized=False))
 merged=git('merge','--ff-only',source)
 assert git('rev-parse','HEAD')==source and not git('status','--short','--untracked-files=no')
 placement=write('source-placement-result-v1.json',dict(schema='n36-reviewed-source-placement-result-v1',at=now,authority=authority,before=before,after=source,destination=str(dest),tracked_clean=True,merge_output=merged,gpu_dispatches=0,measurement_authorized=False,remaining_gates=['complete_graph','controller_bindings','retained_parity_failure','finite_release','native_readiness','scientific_promotion']))
 for r in prev['ledger_prefixes'].values():assert ref(P(r['path']))['sha256']==r['sha256']
next_action='Compose a fresh disabled graph in a new directory for deployed 808e27f702564fe51db45016e139b68ecb476f8c using turn001835 report next_graph_composition_instructions; preserve composition-v3/v4. Rebind final source, exact turn001834 canonical inventory and derived previous snapshot, controller and dependent DAG documents; run production verify_graph and record next failing predicate. Retained validate_private_budget/validate_state parity failure remains unresolved. No GPU until all graph/release/native/scientific gates pass.'
record=dict(status='PASS_SCOPED_ENGINEERING_SOURCE_PLACED_FULL_GRAPH_PENDING',at=now,source=source,review=review,placement=placement,gpu_authorized=False)
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if is_yaml else json.loads(path.read_text());d['n36_canonical_inventory_scoped_source_placement']=record;d['next_action']=next_action;d['updated_at']=now
  tmp=path.with_name(path.name+'.turn001839.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,path)
status=json.loads((base/'driver-status.json').read_text());handles={}
for key in ['driver','process']:
 h=status[key];stat=P(f"/proc/{h['pid']}/stat").read_text().rsplit(')',1)[1].split();assert int(stat[19])==h['start_ticks'];handles[key]=dict(h,identity_verified=True)
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1839,current_source=dict(commit=source,worktree=str(dest)),owning_source=git('rev-parse', 'bee9f6a4703e9d5d802d6b8c7950b69beefac4c0'),scientific_source='1065f38122379a515b60a9a424f574330405b66f',live_handles=handles,controller_status='NO_OWNING_GPU_COHORT_OR_CPU_EXECUTOR',completed_work=['Verified bound handoff/authority, live driver identity, normal previous turn exit, terminal executor and unchanged private ledgers.','Reviewed exact inventory admission and negative-test diff; retained prior parity failure.','Fast-forwarded isolated adapter checkout to reviewed engineering commit; recorded authority and placement; updated owning state/checkpoint.'],source_placement=record,ledger_prefixes=prev['ledger_prefixes'],next_bounded_step=next_action,unresolved_evidence=['Full disabled graph and controller bindings','Retained parity test failure','Finite release and native readiness','Original validation/formal/required ablation evidence'],gpu_dispatches=0,target_met=False,stop_present=False,deadline=auth['continuous_window']['end_utc'])
r=write('operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(r['sha256']+'  operational-summary-v1.json\n');print(json.dumps(dict(review=review,placement=placement,summary=r)))
