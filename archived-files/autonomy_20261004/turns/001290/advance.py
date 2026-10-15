import pathlib,json,hashlib,datetime,subprocess,fcntl,os,yaml,time
owner=pathlib.Path.cwd(); root=owner.parent/'autonomy_20261004';turn=root/'turns/001290';out=turn/'readiness-binding';out.mkdir(exist_ok=True)
coord=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator';cp=coord/'checkpoint.json'
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def write(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def handle(pid):
 p=pathlib.Path(f'/proc/{pid}/stat')
 if not p.exists():return {'pid':pid,'absent':True}
 s=p.read_text().split(') ',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
now=datetime.datetime.now(datetime.timezone.utc);status=json.loads((root/'driver-status.json').read_text());assert status['turn']==1290
for k in ['driver','process']:
 h=status[k];actual=handle(h['pid']);assert all(actual[x]==h[x] for x in ['boot_id','start_ticks'])
assert all(handle(p).get('absent') for p in [691500,691501,391755])
stop=[str(root/'STOP'),str(pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP'))];assert not any(os.path.lexists(p) for p in stop)
assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
ready=json.loads((root/'turns/001289/runtime-readiness-review-v1.json').read_text())
for r in ready['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
work=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree');source='30c6321715df86c5bab623db607bab2811aed56d'
for w in [owner,work]:assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()==source
rec=dict(schema='n36r2-readiness-binding-entry-v1',at=now.isoformat(),source=source,driver=handle(status['driver']['pid']),coordinator=handle(status['process']['pid']),old_executor_handles_absent=[691500,691501,391755],controller_status=ref(root/'turns/001235/controller-status-v1.json'),prior_turn=ref(root/'turns/001289/receipt.json'),ledger_prefixes=ready['ledger_prefixes'],retained_attempts=504,retained_gpu_hours=75.49265038509455,STOP=False,deadline='2026-10-11T11:13:13Z',gpu_dispatch=False,target_met=False)
write(turn/'entry-reconciliation-v1.json',rec)
inputs={k:ref(root/p) for k,p in {'accepted_package':'turns/001282/final-source-refresh/report-v1.json','independent_review':'turns/001284/independent-final-review/report-v1.json','root_acceptance':'turns/001287/terminal-reconciliation-v1.json','source_accounting_adoption':'turns/001288/source-accounting-adoption-v1.json','readiness_review':'turns/001289/runtime-readiness-review-v1.json','runtime_ready':'turns/001289/runtime.ready-v1.json','standing_authority':'user-authorization-v1.json'}.items()}
a=dict(schema='n36r2-readiness-binding-authority-v1',at=now.isoformat(),node_id='15.6',owner=str(owner),worktree=str(work),output_directory=str(out),base_source=source,inputs=inputs,scope='CPU-only readiness-dependent artifact binding preparation; source and science immutable; no execution release',allowed=['Read exact accepted package and immediate review/readiness/adoption references. Reuse unchanged accepted provenance.','Write new preparation script and resulting candidate artifacts only under output_directory. Complete runtime preparation only if verified readiness and all preparation obligations are satisfied; report remaining concrete blockers.','Run focused CPU-only structural checks of source/runtime/closure/controller/40 manifests/context joins, <=120 seconds with two threads.'],forbidden=['No source edits or old artifact overwrites; no owner state/ledger/tree writes.','No GPU, healthcheck, Main, simulator, provider/login probes, network, installs or credential reads.','No approval/review tokens minted by implementer, final frozen plan, production release or dispatch. No child agents.','No protected validation/formal results, prohibited untracked design or Superpowers. No scientific or threshold changes, replay, old provenance rebuilding or broad tests.'],wall_cap_seconds=900,test_budget_seconds=120,cpu_threads=2,gpu_authorized=False,source_edits_authorized=False,scientific_edits_authorized=False,release_enabled=False,STOP_paths=stop,deadline=rec['deadline'])
write(out/'authority-v1.json',a)
prompt=f'''You are the Arbor CPU artifact-preparation executor for existing node15.6, not coordinator or independent reviewer. Read {out/'authority-v1.json'} and its hash-bound immediate inputs. Source {source} has been adopted; turn001289 verified runtime readiness without changing runtime bytes. Complete the next bounded step: create a new readiness-bound candidate package from accepted turn001282 artifacts, changing only preparation/readiness-dependent bindings and propagating necessary hashes in acyclic dependency order. Preserve isolated source_cwd, owner_root, GPU7 UUID/routing, all40 fresh episode IDs, full scientific configs, protocol/accounting, budget/protected reserves and future native-worker obligations. Reuse unchanged evidence. Do not repeat source refresh, broad tests or rebuild historical provenance. Inspect actual verifier requirements before deciding which preparation fields are legitimately ready; do not simply rename false to true. Bind external readiness review as evidence; if preparation requirements cannot be met report precise blockers. Produce report-v1.json/md with hash-bound outputs, changes, focused check outcomes and exact next independent B5 review inputs. An implementer cannot mint B5 or root approval tokens or release. Candidate plan must remain nonreleased; final frozen plan is only after external input-bound B5 review and must omit root_review/execution_release keys. Do not fabricate future process-bound worker receipts or require them before dispatch; keep their acceptance obligations. No source edits, GPU/device/provider/network/protected data/credential access, owner state writes, child agents or old-artifact overwrites. Outputs only in {out}. CPU checks<=120s, two threads; whole task900s. Check STOP/deadline before work. Score null,target_met false,release_enabled false. Return concrete artifacts or blocker, no requests for routine permission.'''
(out/'executor-prompt-v1.txt').write_text(prompt+'\n')
launcher=(root/'turns/001284/independent-final-review/executor-launch-v1.py').read_text().replace('n36r2-independent-final-review-process-v1','n36r2-readiness-binding-process-v1');(out/'executor-launch-v1.py').write_text(launcher)
with open(owner/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in ready['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
 for p in [owner/'research-state.yaml',cp,coord/'idea_tree.json']:
  (turn/(p.name+'.before')).write_bytes(p.read_bytes())
 with open(out/'wrapper.log','ab') as log:p=subprocess.Popen(['python',str(out/'executor-launch-v1.py')],cwd=work,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 write(out/'wrapper-launch-v1.json',dict(wrapper=handle(p.pid),authority=ref(out/'authority-v1.json'),gpu_authorized=False))
 for _ in range(30):
  if (out/'executor-process-v1.json').exists():break
  time.sleep(.1)
 pr=json.loads((out/'executor-process-v1.json').read_text());item=dict(status='CPU_READINESS_BINDING_RUNNING_RELEASE_DISABLED',authority=ref(out/'authority-v1.json'),worktree=str(work),output_directory=str(out),gpu_authorized=False,source_edits_authorized=False,handles={k:pr[k] for k in ['wrapper','executor']},process_record=ref(out/'executor-process-v1.json'),wrapper_launch=ref(out/'wrapper-launch-v1.json'))
 nxt='Monitor turn001290 readiness-binding executor by boot/start identity. Reconcile terminal candidate report and focused checks; then obtain external input-bound B5 review, freeze final plan, external root production review and detached release. No duplicate or GPU dispatch while preparation/review gates remain pending.'
 d=json.loads(cp.read_text());s=yaml.safe_load((owner/'research-state.yaml').read_text());tree=json.loads((coord/'idea_tree.json').read_text())
 for x in [d,s]:
  x['in_flight_executor']=item;x['in_flight_executors']=[];x['n36r2_readiness_binding']=item;x['phase']='N36R2_READINESS_BINDING_PREPARATION_RUNNING';x['next_action']=nxt;x['updated_at']=now.isoformat()
 write(cp,d);t=owner/'research-state.yaml.tmp';t.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));t.replace(owner/'research-state.yaml')
 tree['nodes']['15.6']['n36r2_readiness_binding']=item;tree['nodes']['15.6']['status']='running';write(coord/'idea_tree.json',tree)
summary=dict(schema='autonomy-operational-summary-v1',turn=1290,source=source,live_handles=item['handles'],driver=rec['driver'],coordinator=rec['coordinator'],completed_work='Verified authority, live identities, terminal controller, unchanged private ledger prefixes and prior successful turn; launched bounded CPU readiness-binding preparation using accepted source/package and readiness evidence.',next_bounded_step=nxt,unresolved_evidence='External B5/final-plan/root-production/release and actual validation/formal/required ablation evidence remain pending. Goal not complete.',retained_attempts=504,retained_gpu_hours=75.49265038509455,release_enabled=False,target_met=False)
write(turn/'operational-summary.json',summary)
md=f"Source {source}. Driver {rec['driver']['pid']} and coordinator {rec['coordinator']['pid']} boot/start verified. CPU readiness-binding wrapper {pr['wrapper']['pid']} / executor {pr['executor']['pid']} launched; no GPU cohort.\n\n{summary['completed_work']} Retained 504 attempts / 75.49265038509455 GPUh; no new GPU charges.\n\nNext: {nxt}\n\n{summary['unresolved_evidence']}\n"
(turn/'operational-summary.md').write_text(md);(turn/'operational-summary.sha256').write_text(hashlib.sha256(md.encode()).hexdigest()+'  operational-summary.md\n')
print(json.dumps(summary,indent=2))
