import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,fcntl,yaml
w=pathlib.Path.cwd(); a=w.parent/'autonomy_20261004';o=(a/'turns/001152').resolve();v=o/'implementation';wt=w.parent/'variants/n36_nonprogress_tangent/implementation_worktree'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1152
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];s=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(s[19])==h['start_ticks'] and s[0]!='Z'
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001151/receipt.json')['exit']==0
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source=='52a87af0bf11f95b21ce17aba456dc98944d9774'
reviewpath=a/'turns/001151/protocol-root-review-v1.json';review=read(reviewpath)
assert ref(reviewpath)['sha256']=='91391b76195b91bdb0318ae380820959a5bd4c3beaa6b35c6c7b16a65f121fa9'
for r in [review['protocol'],review['authority'],*review['ledger_prefixes'].values()]:assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
for pid in [4063036,4063037,2632351]:assert not pathlib.Path(f'/proc/{pid}').exists()
assert not wt.exists();v.mkdir();wt.parent.mkdir(exist_ok=True)
auth={'schema':'n36-cpu-implementation-authority-v1','at':now.isoformat(),'node_id':'15.6','source':source,'root_review':ref(reviewpath),'protocol':review['protocol'],'user_authority':review['authority'],'ledger_prefixes':review['ledger_prefixes'],'worktree':str(wt),'branch':'codex/n36-nonprogress-tangent','output_directory':str(v),'scope':'Implement reviewed N36 independent memory/path, production hooks, whole-episode native auditor and controller, meaningful CPU negative tests in isolated variant. Commit source only. No source adoption or GPU release.','gpu_authorized':False,'source_edits_authorized':True,'wall_cap_seconds':3600,'test_cpu_seconds_limit':1800,'threads':2}
write(v/'authority-v1.json',auth)
subprocess.run(['git','worktree','add','-b',auth['branch'],str(wt),source],check=True)
prompt=f'''You are the isolated CPU implementation executor for continuing explicitly authorized Arbor node 15.6 N36. Read and verify {v/'authority-v1.json'}, its root review and full protocol. Implement faithfully in {wt} from {source}; coordinator owns state and release. This is concrete implementation, not another design report. Source edits/commit permitted only in this isolated worktree, artifact outputs only in {v}. Read relevant AGENTS instructions. Do not modify owning research-state/checkpoint/tree/ledgers or other studies. No GPU, simulator episodes, provider probes, protected validation/formal reads, new historical tensor replay, or source adoption. Do not read prohibited untracked 2026-08-10-eds-qd-stage-guidance-transition-design.md. Superpowers disabled; do not open/use Poe credential files, alternate accounts/API keys. No further delegation.

Implement full reviewed protocol (root review resolves draft proposed flags). Independent N36 nonprogress memory, N35 disabled, exact occurrence transport/full8 acknowledgement, fixed ordered binary64 p/d dot<=0, full identity continuity, decision-adjacent consume/clear/expiry and ten-update immutable latch. Current observed geometry/tangent path, deterministic axes/ties, clipping/once-cast native encoding and unchanged inside-box close priority/fallback. Reuse validated transport carefully; do not conflate N35 closure memory with N36. Keep all other15 candidates/remainder/ordinary scoring/archive/ED/final selection and 176/11 budget unchanged. No forced selection or task-specific tuning. Respect all protocol reset cases and native bf16/fp32 signed-zero byte semantics.

Production implementation must include actual native all-round candidate/projection/provider/archive/occurrence/selected/decode/commit/ack/physical-response evidence and independently recomputing whole-episode auditor; never trust producer PASS flags. Extend/derive suitable controller/worker/manifest composition for N36 with fresh C0/Q0/N34/N36 task-major protocol, invalidity stop, zero auto retries, complete-quadruple futility and existing resource accounting/STOP behavior. CPU preparation only: no live config release, healthcheck, budget adoption or GPU execution. Bind source/config/runtime paths correctly; source/submodule dependencies must be explicit and do not mutate shared submodule checkouts. If separate submodule changes needed, preserve a versioned patch within worktree and document exact pinned base/application. Avoid importing unrelated environments; existing CPU testing patterns are available. Do not recreate old provenance, repeat broad suites or read protected artifacts.

Run meaningful targeted CPU tests proving boundaries and independent negatives: each identity change/missing, nonadjacency, origin ambiguity/alias ordinary vs direct/detour, full8 ordering/action/commit errors, terminal including eighth, p zero/nonfinite and dot signs/equality, invalid geometry, axes/ties/clipping/native remainder, ten-round current-template variation, latch expiry and controls unaffected. Auditor/controller corruption/missing telemetry tests must actually reject and prevent next admission. CPU fixtures are not native GPU attestation or performance evidence. Never weaken mandatory audits to get tests passing. Preserve failures and explain repairs.

Use up to 3600 seconds wall, 1800 seconds aggregate CPU test budget, two CPU threads, CUDA disabled. Implement coherent source and targeted tests, commit only intended code (no credentials/state/results), report source commit and per-file hashes, tests/commands/results/failures, protocol coverage and honest unresolved runtime obligations in {v/'report-v1.json'} and report-v1.md. Report score=null, no promotion, no task success claims. If complete implementation cannot fit, commit coherent partial work and specify blockers precisely; do not fabricate full PASS. Root independently reviews before adoption/runtime/release. Stop after reporting.'''
(v/'executor-prompt-v1.txt').write_text(prompt)
wrapper=(a/'turns/001147/protocol-preparation/executor-launch-v1.py').read_text().replace(str(w),str(wt)).replace('n36-protocol-preparation-executor-process-v1','n36-implementation-executor-process-v1').replace('1800','3600')
(v/'executor-launch-v1.py').write_text(wrapper)
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None and not s.get('current_owned_workers') and not s.get('in_flight_executor')
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before-dispatch'))
 with open(v/'wrapper.log','ab') as log:proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=wt,stdout=log,stderr=log,start_new_session=True)
 write(v/'wrapper-launch-v1.json',{'pid':proc.pid,'at':now.isoformat(),'launcher':ref(v/'executor-launch-v1.py')})
 for _ in range(50):
  if (v/'executor-process-v1.json').exists():break
  time.sleep(.1)
 assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid}; never retry blindly'
 pr=read(v/'executor-process-v1.json');rec={'status':'CPU_IMPLEMENTATION_RUNNING','node_id':'15.6','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:pr[k] for k in ['wrapper','executor']},'worktree':str(wt),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':True}
 next_step='Monitor exact N36 CPU implementation executor and bounded report. On exit reconcile commits/tests/side effects, independently review source/native auditor/controller and protocol conformance before source adoption and separately frozen runtime/accounting release. No GPU dispatch or protected access yet.'
 for obj in [s,c]:obj.update(n36_cpu_implementation=rec,in_flight_executor=rec,phase='N36_CPU_IMPLEMENTATION_RUNNING',next_action=next_step,updated_at=now.isoformat())
 c['inflight_executor']=rec;t['nodes']['15.6'].update(status='running',result='CPU_IMPLEMENTATION_RUNNING_NO_GPU',implementation=rec)
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'driver':ds['driver'],'coordinator':ds['process'],'executor':rec,'active_controller':None,'new_gpu_dispatches':0,'ledger_prefixes':review['ledger_prefixes'],'retained_attempts':502,'retained_gpu_hours':75.24379311215873,'completed':'Verified bound handoff/authorization, live identity, prior normal completion, terminal handles and unchanged ledger; created isolated N36 worktree and dispatched official current-login gpt-6-astra CPU implementation under reviewed protocol.','next_action':next_step,'unresolved':['Implementation and independent source/native-audit review','Runtime/accounting execution release','Fresh Dev then validation/formal/required ablation evidence'],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f"Turn 1152: source {source} unchanged in owning study. Driver/coordinator boot/start verified. Prior turn1151 exit0; no recovery required. N35 controller and drafting handles absent. STOP absent; deadline2026-10-11T11:13:13Z.\n\nCompleted: reviewed N36 CPU implementation dispatched in isolated worktree {wt}; source/protocol thresholds remain fixed. No GPU, budget or ledger change. Retained502 attempts/75.24379311215873 GPUh and bound ledger prefix.\n\nLive CPU handles: {rec['handles']}.\n\nNext: {next_step}\n\nUnresolved: implementation/source/runtime/native audit review and original-goal validation/formal/required ablation evidence. Goal not met.\n")
print(json.dumps(rec))
