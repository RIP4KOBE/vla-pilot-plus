import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,fcntl,yaml
w=pathlib.Path.cwd(); a=w.parent/'autonomy_20261004'; o=(a/'turns/001185').resolve(); v=o/'runtime-preparation'; wt=w.parent/'variants/n36_nonprogress_tangent/implementation_worktree'
def read(p): return json.loads(p.read_text())
def ref(p): return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp'); t.write_text(json.dumps(d,indent=2)+'\n'); t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc); ds=read(a/'driver-status.json'); assert ds['turn']==1185
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k]; z=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split(); assert h['boot_id']==boot and int(z[19])==h['start_ticks'] and z[0]!='Z'
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001184/receipt.json')['exit']==0
prior=read(a/'turns/001184/operational-summary.json')
for r in prior['ledger_prefixes'].values(): assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(); assert source=='ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557'
assert subprocess.check_output(['git','-C',str(wt),'rev-parse','HEAD'],text=True).strip()==source
review=read(a/'turns/001180/repair-review/report-v1.json')
v.mkdir()
auth={'schema':'n36-runtime-preparation-authority-v1','at':now.isoformat(),'node_id':'15.6','source':source,'source_adoption':ref(a/'turns/001184/source-adoption-v1.json'),'repair_review':ref(a/'turns/001180/repair-review/report-v1.json'),'protocol':review['verified_direct_references']['protocol'],'root_review':review['verified_direct_references']['root_review'],'user_authority':ref(a/'user-authorization-v1.json'),'ledger_prefixes':prior['ledger_prefixes'],'worktree':str(wt),'owning_worktree':str(w),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False,'wall_cap_seconds':3600,'test_cpu_seconds_limit':900,'threads':2,'scope':'Prepare pinned runtime and disabled 40-cell prospective manifests, source-only actual startup and native-build feasibility. No release, source edits, GPU, or scientific retuning.'}
for key in ['source_adoption','repair_review','protocol','root_review','user_authority']:
 r=auth[key]; assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
write(v/'authority-v1.json',auth)
prompt=f"""You are the isolated N36 runtime preparation executor for continuing explicitly invoked Arbor node 15.6. Read and verify {v/'authority-v1.json'} and its direct references. Reviewed source {source} was adopted into owning study {w}; your isolated worktree {wt} has the same commit. You are not a coordinator. Prepare artifacts under {v}, with any large runtime materialization on this same data-volume output path. No source edits/commits or owning state/checkpoint/tree/ledger writes. Do not dispatch GPU, healthcheck, simulator, model or provider calls. No source adoption, release, validation/formal access, historical tensor replay, credential reads, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md, Superpowers, alternate provider/account/API keys, or further delegation. Official current-login gpt-6-astra only.

Bounded task: discharge preparatory RT-01/RT-02/RT-05 as far as possible using actual pinned runtime, not copied synthetic fixtures. Read scripts/qd_ed_n36_prepare.py, bootstrap/source/build/contract/bridge and existing N35 runtime preparation artifacts to reuse known engineering context. Materialize pinned RDT/LeRobot and full dependencies using existing local pinned assets (no shared dependency mutations). Build hash-bound source/runtime/config/checkpoint/cache/provider/task/init/controller/native-build manifests and disabled draft for all40 prospective identities using adopted source, preserving frozen protocol/control branches, limits, thresholds, seeds and accounting. The owning study paths must remain correct in any prospective draft; do not silently bind dispatch to isolated executor state. Existing implementation receipts explain exact path requirements. Record precise path bindings.

Verify actual isolated/no-site/source-only startup through the unmodified full core initializer and real pinned imports. CUDA_VISIBLE_DEVICES empty, no device context or model/simulator/provider execution. Validate source closure, encoding/frozen/native/generated exceptions and runpy behavior with source-only execution, no restored uncontrolled loader, no suppressed initializer, no fabricated native mapping. Static native-build identification and CPU import are allowed, GPU work is not. If actual CUDA mapped-build attestation necessarily needs GPU, mark that portion unresolved and provide exact future metered command; never fake receipts. Record complete parent wall timing (including bootstrap/import/hash) and bounded resource/storage costs; worker_imports alone is not complete startup. RT-03/RT-04 whole-episode and GPU receipts remain unresolved and require separate prospective release. A failed audit is evidence, not permission to relax it.

Do not recursively rebuild provenance, repeat broad tests or inspect protected results. Reuse direct reviewed tests. <=3600 wall seconds and <=900 aggregate reproduction CPU seconds, two threads. If concrete source failure blocks preparation, stop and report minimal reproducible engineering repair; do not edit source. Do not claim readiness from --help-only tests or synthetic inventories. Write report-v1.json and report-v1.md with exact commands/timings/failures, hashes, artifacts/draft references, RT-01/02/05 disposition and remaining gaps, score=null,promotion=false,target_met=false,release_enabled=false. No accounting adoption; root must independently review runtime/accounting and freeze release before any dispatch. Stop after reports.
"""
(v/'executor-prompt-v1.txt').write_text(prompt)
wrapper=(a/'turns/001152/implementation/executor-launch-v1.py').read_text().replace('n36-implementation-executor-process-v1','n36-runtime-preparation-executor-process-v1')
(v/'executor-launch-v1.py').write_text(wrapper)
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml'; cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'; tp=cp.parent/'idea_tree.json'; s=yaml.safe_load(sp.read_text()); c=read(cp); t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None and not s.get('current_owned_workers') and not s.get('in_flight_executor')
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 for p in [sp,cp,tp]: shutil.copyfile(p,o/(p.name+'.before-runtime'))
 with open(v/'wrapper.log','ab') as log: proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=wt,stdout=log,stderr=log,start_new_session=True)
 write(v/'wrapper-launch-v1.json',{'pid':proc.pid,'at':now.isoformat(),'launcher':ref(v/'executor-launch-v1.py')})
 for _ in range(50):
  if (v/'executor-process-v1.json').exists(): break
  time.sleep(.1)
 assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid}; never retry blindly'
 pr=read(v/'executor-process-v1.json'); rec={'status':'CPU_RUNTIME_PREPARATION_RUNNING','node_id':'15.6','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:pr[k] for k in ['wrapper','executor']},'worktree':str(wt),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False}
 next_step='Monitor exact N36 pinned-runtime preparation executor; reconcile artifacts and RT-01/02/05 failures or evidence before independent runtime/accounting review. No GPU release; RT-03/04 and original scientific goal remain open.'
 for obj in [s,c]: obj.update(n36_runtime_preparation=rec,in_flight_executor=rec,phase='N36_CPU_RUNTIME_PREPARATION_RUNNING',next_action=next_step,updated_at=now.isoformat())
 c['inflight_executor']=rec; t['nodes']['15.6'].update(status='running',result='CPU_RUNTIME_PREPARATION_RUNNING_NO_GPU',runtime_preparation=rec)
 q=sp.with_suffix('.tmp'); q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True)); q.replace(sp); write(cp,c); write(tp,t)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'driver':ds['driver'],'coordinator':ds['process'],'executor':rec,'active_controller':None,'new_gpu_dispatches':0,'ledger_prefixes':prior['ledger_prefixes'],'retained_attempts':502,'retained_gpu_hours':75.24379311215873,'completed':'Verified handoff/authority, live driver/coordinator boot/start identities, prior normal source adoption and unchanged private ledgers. Started isolated bounded official-login CPU runtime preparation at adopted source; no GPU or source edits.','next_action':next_step,'unresolved':prior['unresolved'],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f"Current source {source}. Driver {ds['driver']['pid']}; coordinator {ds['process']['pid']}; runtime preparation handles {rec['handles']}. No live GPU controller.\n\n"+summary['completed']+'\n\nNext: '+next_step+'\n\nUnresolved: actual runtime/native-build feasibility and whole-episode audit, fresh matched Dev, validation/formal and required ablation evidence. Costs retained: 502 attempts / 75.24379311215873 GPUh.\n')
print(json.dumps(rec))
