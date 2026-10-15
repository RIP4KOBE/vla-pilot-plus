import pathlib,json,hashlib,datetime,os,sys,subprocess,time,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';turn=base/'turns/001443';out=turn/'binding-refresh';prior=json.loads((base/'turns/001442/operational-summary-v1.json').read_text());work=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(work));from scripts import qd_ed_final_runner as r
source='e36f8b945f6b2fde9e81010b3d16987b8c771dd0'
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');os.replace(t,p)
assert not (base/'STOP').exists();assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()==source
assert not subprocess.check_output(['git','-C',str(work),'status','--porcelain','--untracked-files=no'],text=True).strip()
for pid in [1553379,1553380,1547653]:assert not pathlib.Path(f'/proc/{pid}').exists()
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  for v in prior['ledger_prefixes'].values():assert ref(pathlib.Path(v['path']))['sha256']==v['sha256']
  out.mkdir(exist_ok=False)
  a={'schema':'n36r3-binding-refresh-authority-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'node_id':'15.6','source':source,'worktree':str(work),'output_directory':str(out),'authority':ref(base/'user-authorization-v1.json'),'repair_acceptance':ref(base/'turns/001442/terminal-reconciliation-v1.json'),'repair_report':ref(base/'turns/001440/lexical-reference-repair/report-v1.json'),'parent_plan':ref(base/'turns/001432/manifest-refresh/plan.draft.json'),'scope':'CPU-only prospective bindings after accepted lexical-reference repair; no source edits or owner adoption, release, GPU, provider or ledger writes.','gpu_authorized':False,'release_enabled':False,'source_edits_authorized':False,'cpu_threads':2,'wall_cap_seconds':900}
  write(out/'authority-v1.json',a)
  prompt=f'''Continue explicitly authorized Arbor leaf 15.6 as isolated CPU binding executor, not coordinator. Read {out}/authority-v1.json and bound accepted repair. Refresh bindings for exact committed source {source}, without source edits. Use inspected NEW copies of tooling in {base}/turns/001429/binding-refresh (refresh-bindings-v1.py, complete-bindings-v1.py, finalize-report-v1.py) and manifest tooling in turn001432 as needed. Adapt only new artifact tooling to current acceptance schema: changed_files are strings, acceptance status is N36R3_LEXICAL_REFERENCE_REPAIR_ACCEPTED_PENDING_BINDINGS; do not rewrite acceptance or invent a decision. Parent plan is turn001432/manifest-refresh/plan.draft.json. All new artifacts under {out}. Preserve original files, all 40 episode identities, frozen science, production Main/native audit, owner lexical routing, deadline 2026-10-11T11:13:13Z, first-C0 G3 pause. Retained actual accounting is 505 attempts / 75.53335346582918 GPUh; do not adopt stale 75.53031173955723 tooling constants. Preserve prior charged health; readiness of earlier source cannot transfer. Only prepare DISABLED source/runtime-input/closure/inventory/controller/native/manifests/plan/accounting/health bindings, identify any later fresh health identity requirement explicitly; no release or replay. Check binding consistency and passive runtime feasibility, no broad test repeats or recursive historical provenance rebuild. Root controller review, exact B5 and source adoption remain separate. Report hash-bound report-v1.json/report-v1.md, exact artifacts/checks/blockers, score null, goal incomplete. No owning state/ledger changes, GPU/provider calls, foreign-study operations, child agents, credentials or protected validation/formal results. Never open 2026-08-10-eds-qd-stage-guidance-transition-design.md. Official current-login gpt-6-astra only. STOP/deadline before work. No driver.lock/coordinator.lease. CPU two threads, 900 sec. If tooling exposes a mismatch, stop and report exact evidence rather than weaken audits.'''
  (out/'executor-prompt-v1.txt').write_text(prompt+'\n')
  (out/'executor-launch-v1.py').write_bytes((base/'turns/001429/binding-refresh/executor-launch-v1.py').read_bytes())
  with (out/'wrapper.log').open('wb') as log:p=subprocess.Popen([sys.executable,str(out/'executor-launch-v1.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  for _ in range(30):
   if (out/'executor-process-v1.json').exists():break
   time.sleep(.1)
  proc=json.loads((out/'executor-process-v1.json').read_text());write(out/'wrapper-launch-v1.json',{'authority':ref(out/'authority-v1.json'),'process':proc})
  now=datetime.datetime.now(datetime.timezone.utc).isoformat();status='N36R3_LEXICAL_BINDING_REFRESH_RUNNING';nextstep='Monitor existing turn001443 CPU binding executor by boot/start identity; reconcile exit/report before root controller review, exact manifest/B5 and adoption. No duplicate launch or GPU release.'
  handle={'status':status,'node_id':'15.6','authority':ref(out/'authority-v1.json'),'wrapper':proc['wrapper'],'executor':proc['executor'],'source':source,'worktree':str(work),'output_directory':str(out),'process_record_path':str(out/'executor-process-v1.json'),'gpu_authorized':False,'release_enabled':False,'source_edits_authorized':False}
  for path,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=yaml.safe_load(path.read_text()) if isyaml else json.loads(path.read_text());d.update(status=status,phase=status,next_action=nextstep,updated_at=now,n36r3_lexical_binding_refresh=handle,in_flight_executors=[handle]);d['active_executor']=handle
   if isyaml:
    t=path.with_suffix('.tmp');t.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(t,path)
   else:write(path,d)
  path=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(path.read_text());d['nodes']['15.6'].update(result=status,insight=nextstep,n36r3_lexical_binding_refresh=handle);write(path,d)
  summary={**prior,'at':now,'turn':1443,'live_handles':{'wrapper':proc['wrapper'],'executor':proc['executor']},'live_executor_handles':[handle],'driver':json.loads((base/'driver-status.json').read_text()),'current_controller_status':'NO_GPU_CONTROLLER_CPU_BINDING_EXECUTOR_RUNNING','completed_work':['Verified handoff and authorization hashes, driver identities, normal prior turn, absent prior handles and unchanged ledgers.','Launched one bounded official Codex CPU binding executor for accepted lexical-reference repair; owning source and all scientific gates unchanged.'],'next_bounded_step':nextstep}
  summary.pop('terminal_reconciliation',None);write(turn/'operational-summary-v1.json',summary);(turn/'operational-summary-v1.sha256').write_text(ref(turn/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'status':status,'handles':proc,'summary':ref(turn/'operational-summary-v1.json')}))
