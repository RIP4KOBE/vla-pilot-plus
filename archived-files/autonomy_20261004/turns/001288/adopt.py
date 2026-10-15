import pathlib,json,yaml,hashlib,datetime,subprocess,fcntl,os,copy
owner=pathlib.Path.cwd();base=owner.parent/'autonomy_20261004';turn=base/'turns/001288';coord=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def handle(pid):
 p=pathlib.Path(f'/proc/{pid}/stat')
 if not p.exists():return dict(pid=pid,absent=True)
 v=p.read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(v[19]),state=v[0])
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
previous=json.loads((base/'turns/001287/operational-summary.json').read_text());report=base/'turns/001284/independent-final-review/report-v1.json';review=json.loads(report.read_text());plan=json.loads((base/'turns/001282/final-source-refresh/plan.complete-disabled-v1.json').read_text());before=previous['source_commit'];after=review['source_commit']
assert review['status']=='FINAL_SOURCE_CPU_PACKAGE_ACCEPTED_EXECUTION_NOT_RELEASED' and not review['blockers']
assert json.loads((base/'turns/001287/receipt.json').read_text())['status']=='completed_turn'
for v in review['bindings'].values():
 if isinstance(v,dict) and 'path' in v and 'sha256' in v:assert ref(v['path'])['sha256']==v['sha256'],v['path']
assert handle(268073)['start_ticks']==97715947 and handle(707461)['start_ticks']==146884750
assert all(handle(p).get('absent') for p in [391755,678637,678638,691500,691501])
assert not any(os.path.lexists(p) for p in previous['STOP'])
now=datetime.datetime.now(datetime.timezone.utc);assert (datetime.datetime.fromisoformat(previous['deadline'].replace('Z','+00:00'))-now).total_seconds()>75600
assert git('rev-parse','HEAD')==before
subprocess.run(['git','merge-base','--is-ancestor',before,after],check=True)
changed=set(git('diff','--name-only',before,after).splitlines());dirty=set(git('diff','--name-only').splitlines())|set(git('diff','--cached','--name-only').splitlines());assert not changed&dirty
assert all(p.startswith(('scripts/','tests/','docs/n36-')) for p in changed)
old_auth=base/'turns/001222/budget-authority-v1.json';authority=json.loads(old_auth.read_text());accounting=json.loads(pathlib.Path(plan['accounting']['path']).read_text());calc=json.loads(pathlib.Path(accounting['calculation']['path']).read_text())
assert calc['attempts']['after']==544 and calc['arithmetic']['unprotected_effective_headroom_after_cohort_gpu_hours']=='88.1170008488933945'
for key in ['protocol','accounting']:
 v=plan[key];assert ref(v['path'])['sha256']==v['sha256']
authority.update(cohort=plan['cohort'],protocol=plan['protocol'],accounting=plan['accounting'],amendment=plan['accounting'],ledger_prefixes=accounting['ledger_prefixes'],starts_at=now.isoformat(),previous_authority=ref(old_auth),accounting_calculation=accounting['calculation'])
entry=dict(schema='n36r2-source-adoption-entry-v1',at=now.isoformat(),driver=handle(268073),coordinator=handle(707461),absent_handles=[391755,678637,678638,691500,691501],source_before=before,source_after=after,review=ref(report),ledger_prefixes=previous['ledger_prefixes'],STOP=previous['STOP'],deadline=previous['deadline'],changed_paths=sorted(changed),release_enabled=False)
next_action='Establish bounded current GPU7/CUDA logical0/EGL4 and official current-login Codex readiness for adopted N36R2 source30c6321715df86c5bab623db607bab2811aed56d. Reuse reviewed isolated source/runtime routing and unchanged provenance; update only readiness-dependent bindings. Obtain external input-bound B5 review, freeze final plan (omit root_review/execution_release keys), external root production review and detached release before any episode dispatch. Authority/accounting adopted in turn001288; no scientific promotion.'
with open(owner/'data/qd-ed-runner.lock','a') as runner:
 fcntl.flock(runner,fcntl.LOCK_EX|fcntl.LOCK_NB)
 with open(owner/'data/qd-ed-state.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  for v in previous['ledger_prefixes'].values():assert ref(v['path'])['sha256']==v['sha256']
  s=yaml.safe_load((owner/'research-state.yaml').read_text());c=json.loads((coord/'checkpoint.json').read_text());t=json.loads((coord/'idea_tree.json').read_text())
  assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
  assert s['budget']['running']==0 and not s['current_owned_workers']
  assert s['source_commit']==before
  for p in [owner/'research-state.yaml',coord/'checkpoint.json',coord/'idea_tree.json']:(turn/('before-'+p.name)).write_bytes(p.read_bytes())
  put(turn/'entry-reconciliation-v1.json',entry);put(turn/'previous-budget-envelope-v1.json',dict(budget=s['budget'],authority=s.get('authority'),previous_authority=ref(old_auth)))
  authority['previous_amendment']=copy.deepcopy(s['budget']['amendment'])
  put(turn/'budget-authority-v1.json',authority)
  proc=subprocess.run(['git','merge','--ff-only',after],text=True,capture_output=True);(turn/'source-adoption-git.txt').write_text(proc.stdout+proc.stderr);assert proc.returncode==0
  assert git('rev-parse','HEAD')==after
  record=dict(schema='n36r2-root-source-accounting-adoption-v1',at=now.isoformat(),status='SOURCE_ACCOUNTING_ADOPTED_READINESS_PENDING',source_before=before,source_after=after,independent_review=ref(report),authority=ref(turn/'budget-authority-v1.json'),amendment=plan['accounting'],calculation=accounting['calculation'],previous_budget=ref(turn/'previous-budget-envelope-v1.json'),ledger_prefixes=previous['ledger_prefixes'],retained_snapshot=previous['budget_snapshot'],arithmetic='504+40=544 attempts; 40*(1800+40)+1800+200=75600 seconds=21 GPUh; 75.49265038509455+0.23357169027962+21=96.72622207537417 conservative GPUh; effective cap221.08404692669838 minus protected36.2408240024308155 leaves88.1170008488933945 after full cohort.',caps_changed=False,scientific_gates_changed=False,release_enabled=False,gpu_dispatch=False,target_met=False,next_action=next_action)
  put(turn/'source-accounting-adoption-v1.json',record)
  for x in [s,c]:
   x['source_commit']=after;x['n36r2_source_accounting_adoption']=ref(turn/'source-accounting-adoption-v1.json');x['n36r2_budget_authority']=ref(turn/'budget-authority-v1.json');x['next_action']=next_action;x['updated_at']=now.isoformat();x['automatic_gpu_dispatch_authorized']=False
   if x.get('in_flight_executors'):
    x.setdefault('executor_handle_history',[]).extend(x['in_flight_executors']);x['in_flight_executors']=[]
  s['budget']['previous_amendment_envelope']=ref(turn/'previous-budget-envelope-v1.json');s['budget']['amendment']=plan['accounting']
  s['authority']=ref(turn/'budget-authority-v1.json');c['authority']=ref(turn/'budget-authority-v1.json')
  tmp=owner/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(owner/'research-state.yaml');put(coord/'checkpoint.json',c)
  node=t['nodes']['15.6'];node['n36r2_source_accounting_adoption']=ref(turn/'source-accounting-adoption-v1.json');node['result']='N36R2_SOURCE_ACCOUNTING_ADOPTED_READINESS_PENDING';node['insight']='Reviewed engineering source and finite accounting adopted; no GPU release or scientific promotion. Readiness and external B5/final plan/root review/release remain pending.';put(coord/'idea_tree.json',t)
  for v in previous['ledger_prefixes'].values():assert ref(v['path'])['sha256']==v['sha256']
summary=dict(previous);summary.update(turn=1288,at=now.isoformat(),status=record['status'],source_commit=after,source_adopted=True,driver=handle(268073),coordinator=handle(707461),handles={},prior_turn_receipt=ref(base/'turns/001287/receipt.json'),adoption=ref(turn/'source-accounting-adoption-v1.json'),next_action=next_action,completed_work='Verified live identities, normal prior exit, absent old workers, reviewed bindings and unchanged private ledger prefixes. Fast-forwarded reviewed engineering source and adopted finite N36R2 authority/accounting under owning runner/state locks. Archived old state and budget envelope. No GPU or provider operation; no source/protocol edits.',unresolved_evidence=['Current readiness, external B5, final plan, production review and detached release pending.','Actual worker audit validity and original validation/formal/required ablations remain unmet.'])
put(turn/'operational-summary.json',summary);(turn/'operational-summary.md').write_text('Turn001288: adopted source '+after+'. No live GPU/review workers; driver268073/start97715947 and coordinator707461/start146884750 verified. Retained504 attempts/75.49265038509455 GPUh and all private ledger bytes. N36R2 finite40-cell/21GPUh accounting adopted; no cap/reserve/science change. '+next_action+' Original goal unmet.\n');(turn/'operational-summary.sha256').write_text(ref(turn/'operational-summary.json')['sha256']+'  operational-summary.json\n');print(json.dumps(record,indent=2))
