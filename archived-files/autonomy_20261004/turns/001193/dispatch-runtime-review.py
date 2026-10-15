import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,fcntl,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001193').resolve();old=(a/'turns/001185/runtime-preparation').resolve();v=o/'runtime-review'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def check(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1193
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];t=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(t[19])==h['start_ticks'] and t[0]!='Z'
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001192/receipt.json')['exit']==0
prior=read(a/'turns/001192/operational-summary.json');ledgers={}
for name,r in prior['ledger_prefixes'].items():
 p=w/'data'/name;b=p.read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[name]={**ref(p),'bytes':len(b),'prior_prefix_matches':True}
for pid in [81030,81032,2632351]:assert not pathlib.Path(f'/proc/{pid}').exists()
r=read(old/'report-v1.json');pa=read(old/'authority-v1.json');source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==r['source']=='ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557'
assert read(old/'executor-exit-v1.json')['exit']==0
check(prior['executor']['report']);check(r['authority']);check(r['recommended_root_review_draft'])
for z in r['artifacts'].values():check(z)
for key in ['source_adoption','repair_review','protocol','root_review','user_authority']:check(pa[key])
v.mkdir()
auth={'schema':'n36-independent-runtime-review-authority-v1','at':now.isoformat(),'node_id':'15.6','source':source,'preparation_report':ref(old/'report-v1.json'),'draft':r['recommended_root_review_draft'],'preparation_authority':ref(old/'authority-v1.json'),**{k:pa[k] for k in ['source_adoption','repair_review','protocol','root_review','user_authority']},'worktree':pa['worktree'],'owning_worktree':str(w),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False,'wall_cap_seconds':1800,'test_cpu_seconds_limit':300,'threads':2}
write(v/'authority-v1.json',auth)
prompt=f'''You are the independent CPU runtime reviewer for ongoing explicitly authorized Arbor N36 node 15.6. This is not a coordinator. Read {v/'authority-v1.json'} SHA256 {ref(v/'authority-v1.json')['sha256']} and verify its direct references. Review actual source {source}, preparation report and enriched disabled draft from turn1185. Independently check the candidate runtime closure inventory changes (Cython origin and Triton transient sources), static native library inventory versus real CPU mapped receipt, controller semantic rebind, actual isolated no-site source-only startup/import/runpy provenance, and exact all40 identities/configs against frozen prospective protocol. Review runtime entrypoint and how a root release would enable the disabled draft without bypassing missing preparation requirements. Find concrete defects, not recursive old provenance. Reuse verified source/repair tests and focused preparation receipts; do not rerun preparation or broad tests absent concrete concerns. Distinguish what passes before dispatch from RT-03/04 live audit obligations and RT-05 metered cost feasibility. No need to demand live evidence before an otherwise valid prospective metered run, but fail closed on genuine predispatch defects. Check path bindings and changes in source/runtime/scientific parameters. Accounting adoption and release are root-only and remain disabled.

No source edits/commits, owning state/checkpoint/tree/ledger writes, GPU/model/provider/simulator/healthcheck calls, validation/formal result access, historical tensor replay, credential reads, prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md, Superpowers, API keys/alternate accounts or further delegation. Only official current-login Codex gpt-6-astra. All artifacts within {v}. Read source read-only from owning or isolated source; no shared dependency mutations. Up to 1800 seconds wall, 300 CPU seconds targeted checks with two threads/CUDA disabled. Do not inspect credential-bearing environment output. Write report-v1.json and report-v1.md with scoped PASS/FAIL, exact concrete findings and file/line references, hashes/checks, minimum remediation if any, and outstanding root release/live obligations. score=null, promotion=false, target_met=false, release_enabled=false. Stop after report.'''
(v/'executor-prompt-v1.txt').write_text(prompt)
wrapper=(a/'turns/001180/repair-review/executor-launch-v1.py').read_text().replace('n36-independent-repair-review-process-v1','n36-independent-runtime-review-process-v1');(v/'executor-launch-v1.py').write_text(wrapper)
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 assert s['n36_runtime_preparation']['executor_exited'] is True
 assert not s.get('current_owned_workers')
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before'))
 with open(v/'wrapper.log','ab') as log:proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=pa['worktree'],stdout=log,stderr=log,start_new_session=True)
 write(v/'wrapper-launch-v1.json',{'pid':proc.pid,'at':now.isoformat(),'launcher':ref(v/'executor-launch-v1.py')})
 for _ in range(50):
  if (v/'executor-process-v1.json').exists():break
  time.sleep(.1)
 assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid}; never retry blindly'
 pr=read(v/'executor-process-v1.json');rec={'status':'CPU_RUNTIME_REVIEW_RUNNING','node_id':'15.6','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:pr[k] for k in ['wrapper','executor']},'worktree':pa['worktree'],'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False}
 next_step='Monitor exact N36 independent runtime reviewer; reconcile report, then root accounting/runtime-readiness review and prospective metered release only if predispatch gates pass. Preserve RT-03/04 live obligations; no repeat preparation absent a concrete defect.'
 for obj in [s,c]:obj.update(n36_runtime_review=rec,in_flight_executor=rec,phase='N36_CPU_RUNTIME_REVIEW_RUNNING',next_action=next_step,updated_at=now.isoformat())
 c['inflight_executor']=rec;t['nodes']['15.6'].update(status='running',score=None,result='CPU_RUNTIME_REVIEW_RUNNING_NO_GPU',runtime_review=rec)
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'driver':ds['driver'],'coordinator':ds['process'],'executor':rec,'live_handles':rec['handles'],'active_controller':None,'new_gpu_dispatches':0,'ledger_prefixes':ledgers,'retained_attempts':502,'retained_gpu_hours':75.24379311215873,'completed':'Verified bound authority/handoff, normal prior completion, absent prior executor/controller identities, exact owning source, all direct preparation artifact hashes and unchanged private ledger prefixes. Launched independent bounded CPU runtime review using official current-login gpt-6-astra. No source, scientific rule, budget, or GPU release change.','next_action':next_step,'unresolved':['Independent runtime review','Prospective accounting and detached release','RT-03/04 live audit and RT-05 full episode feasibility','Fresh Dev promotion gates','Original validation/formal/required ablation evidence'],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f"Source {source}. Independent CPU runtime review running: {json.dumps(rec['handles'])}. No active GPU controller; no new GPU dispatch. All private ledger prefixes retained: 502 attempts / 75.24379311215873 GPUh. Prior turn normal completion and preparation hashes verified. STOP absent; deadline 2026-10-11T11:13:13Z. Next: {next_step} Original validation/formal/ablation evidence remains unmet.\n")
print(json.dumps({'handles':rec['handles'],'summary':str(o/'operational-summary.json'),'next':next_step},indent=2))
