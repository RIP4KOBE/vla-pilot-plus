import pathlib,json,hashlib,datetime,fcntl,yaml,subprocess
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';out=(a/'turns/001203').resolve();v=out/'recovery-preparation';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def ident(pid):
 p=pathlib.Path('/proc',str(pid),'stat')
 if not p.exists():return None
 t=p.read_text().rsplit(')',1)[1].split();return {'pid':pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(t[19]),'state':t[0]}
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 ds=json.loads((a/'driver-status.json').read_text());assert ds['turn']==1203
 prior=json.loads((a/'turns/001202/operational-summary.json').read_text());ledger=(w/'data/attempt-ledger.jsonl').read_bytes();assert len(ledger)==prior['ledger']['bytes'] and hashlib.sha256(ledger).hexdigest()==prior['ledger']['sha256']
 proc=json.loads((v/'executor-process-v1.json').read_text());handles={}
 for key in ['wrapper','executor']:
  h=proc[key];live=ident(h['pid']);assert live and all(live[k]==h[k] for k in ['pid','boot_id','start_ticks']);handles[key]=live
 s=yaml.safe_load((w/'research-state.yaml').read_text());ck=json.loads(cp.read_text());tree=json.loads((cp.parent/'idea_tree.json').read_text());assert not s.get('active_controller') and not s.get('in_flight_executor')
 now=datetime.datetime.now(datetime.timezone.utc).isoformat();source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==s['source_commit']=='ab8e8c6f8fdfb66c3a82b0135c0441cf542a9557'
 task={'status':'CPU_RECOVERY_RUNTIME_PREPARATION_RUNNING','node_id':'15.6','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':handles,'worktree':str(w.parent/'variants/n36_nonprogress_tangent/implementation_worktree'),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False}
 nxt='Monitor existing official gpt-6-astra CPU recovery-preparation executor 208491/wrapper208489 using recorded boot/start identity; no duplicate. On exit reconcile artifacts and unchanged ledger/source, then independently review prospective N36R1 manifest/identity and draft plan before root release adoption. No GPU dispatch until separately reviewed release.'
 summary={'schema':'autonomy-bounded-operation-summary-v1','at':now,'source':source,'status':'N36_RECOVERY_RUNTIME_PREPARATION_RUNNING','driver':ident(ds['driver']['pid']),'coordinator':ident(ds['process']['pid']),'live_cohort_handles':[],'live_cpu_executor_handles':handles,'prior_turn_exit':json.loads((a/'turns/001202/receipt.json').read_text())['exit'],'ledger_prefix_verified':True,'ledger':{**ref(w/'data/attempt-ledger.jsonl'),'bytes':len(ledger)},'budget_snapshot':prior['budget_snapshot'],'completed':'Verified hash-bound authority, driver identities, STOP/deadline, closed N36 handles, unchanged ledger and successful prior turn; launched bounded official current-login gpt-6-astra executor for CPU-only recovery preparation with source/science/audits immutable.','preparation':task,'next_action':nxt,'unresolved':['Recovery manifest and fresh identity preparation plus independent review/release','RT-03/04 native/controller/whole-episode evidence','Original validation/formal/required ablations'],'target_met':False,'stop_present':(a/'STOP').exists(),'deadline':'2026-10-11T11:13:13Z'}
 write(out/'operational-summary.json',summary)
 for p in [w/'research-state.yaml',cp,cp.parent/'idea_tree.json']:(out/(p.name+'.before-update')).write_bytes(p.read_bytes())
 for d in [s,ck]:d.update(status=summary['status'],phase='N36_ENGINEERING_RECOVERY_PREPARATION',next_action=nxt,updated_at=now,automatic_gpu_dispatch_authorized=False,in_flight_executor=task,n36_recovery_runtime_preparation=task)
 tree['nodes']['15.6'].update(insight='CPU-only N36 recovery manifest/identity preparation in flight following reproduced visibility-dependent metadata mismatch. Frozen scientific source/protocol and strict audits preserved; original invalid charge retained. No new GPU dispatch or valid scientific outcome.',recovery_runtime_preparation=task)
 p=w/'research-state.yaml';tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(p);write(cp,ck);write(cp.parent/'idea_tree.json',tree)
 (out/'operational-summary.md').write_text(f'Source {source}. Driver {ds["driver"]["pid"]} and coordinator {ds["process"]["pid"]} verified. No live GPU cohort. CPU preparation wrapper208489/executor208491 live with bound boot/start identity.\n\nAuthority and ledger verified; 503 dispatches /75.26779409697457 GPUh retained. CPU-only recovery preparation delegated; no scientific source or audit edits authorized.\n\nNext: {nxt}\n\nUnresolved: recovery release/review, native execution evidence, original validation/formal/required ablations. Target not met.\n')
 print(json.dumps({'summary':ref(out/'operational-summary.json'),'live_handles':handles}))
