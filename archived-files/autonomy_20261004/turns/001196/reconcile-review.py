import pathlib,json,hashlib,datetime,subprocess,fcntl,shutil,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001196').resolve();p=a/'turns/001193/runtime-review'
def read(p): return json.loads(p.read_text())
def ref(p): return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def check(r): assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
def write(p,x):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(x,indent=2)+'\n');q.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1196
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for h in [ds['driver'],ds['process']]:
 st=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(st[19])==h['start_ticks'] and st[0]!='Z'
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
prior=read(a/'turns/001195/operational-summary.json');assert read(a/'turns/001195/receipt.json')['exit']==0
ledgers={}
for name,r in prior['ledger_prefixes'].items():
 f=w/'data'/name;b=f.read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[name]={**ref(f),'bytes':len(b),'prior_prefix_matches':True}
for h in prior['executor']['handles'].values(): assert not pathlib.Path(f'/proc/{h["pid"]}').exists()
r=read(p/'report-v1.json');assert r['verdict']=='PASS' and not r['concrete_predispatch_defects'];ex=read(p/'executor-exit-v1.json');assert ex['exit']==0
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==r['source']==prior['source']
changed=subprocess.check_output(['git','diff','--name-only','HEAD'],text=True).splitlines()
assert all(x.startswith(('.arbor/','data/','docs/03_evidence/')) or x in ['research-state.yaml','research_config.yaml'] for x in changed),changed
for x in [r['authority'],r['reviewed_draft'],prior['executor']['process_record']]:check(x)
assert all(r[k] is False for k in ['promotion','target_met','release_enabled','runtime_ready','accounting_adopted','gpu_authorized'])
terminal={'schema':'n36-runtime-review-terminal-reconciliation-v1','at':now.isoformat(),'status':'PASS_CPU_RUNTIME_REVIEW_ROOT_RELEASE_REQUIRED','source':source,'report':ref(p/'report-v1.json'),'exit':ref(p/'executor-exit-v1.json'),'previous_handles':prior['executor']['handles'],'old_processes_absent':True,'authority_process_and_draft_hashes_verified':True,'accepted_scope':'Independent CPU runtime review completed and accepted within its stated scope. Runtime readiness, accounting adoption and detached release remain root obligations; no scientific success or GPU authorization.','producer_status':r['status'],'root_only_release_steps':r['root_only_release_steps'],'obligations':r['obligations'],'producer_resources':r['resources'],'ledger_prefixes':ledgers,'gpu_release':False,'promotion':False,'target_met':False}
write(o/'runtime-review-terminal-reconciliation-v1.json',terminal)
next_action='Reconcile and adopt finite N36 accounting, verify reusable accounted CUDA/EGL proof and current official provider readiness; freeze ready runtime with rebound closure/controller/all40 manifests and detached release only after complete validation. Follow turn1193 root_only_release_steps; preserve RT-03/04 live obligations and all history. No repeat CPU preparation absent a concrete defect.'
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 assert s['n36_runtime_review']==c['n36_runtime_review']==t['nodes']['15.6']['runtime_review']
 for f in [sp,cp,tp]:shutil.copyfile(f,o/(f.name+'.before'))
 for obj in [s,c]:
  rec={**obj['n36_runtime_review'],'status':terminal['status'],'executor_exited':True,'live_handles':[],'report':terminal['report'],'exit':terminal['exit'],'terminal_reconciliation':ref(o/'runtime-review-terminal-reconciliation-v1.json')}
  obj.update(n36_runtime_review=rec,in_flight_executor=None,phase='N36_CPU_RUNTIME_REVIEW_PASSED_ROOT_RELEASE_PENDING',next_action=next_action,updated_at=now.isoformat())
 c['inflight_executor']=None
 t['nodes']['15.6'].update(status='running',score=None,result='CPU_RUNTIME_REVIEW_PASS_NO_GPU_RELEASE',runtime_review=rec)
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'driver':ds['driver'],'coordinator':ds['process'],'live_handles':{},'active_controller':None,'current_owned_workers':[],'executor':rec,'ledger_prefixes':ledgers,'retained_attempts':502,'retained_gpu_hours':75.24379311215873,'new_gpu_dispatches':0,'completed':'Reconciled normal N36 independent CPU runtime review completion; verified absent executor identities, exact source, authority/process/draft hashes and unchanged private ledger prefixes. Updated owning state/checkpoint/tree under state lock. No release, source change or promotion.','terminal_reconciliation':ref(o/'runtime-review-terminal-reconciliation-v1.json'),'next_action':next_action,'unresolved':[v['remaining'] for v in r['obligations']]+['Original matched validation, formal and required QD/ED ablation goal remains unevidenced.'],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f"Source {source}. N36 CPU reviewer wrapper 116992 and executor 116994 exited normally and are absent; no active GPU controller. Driver {ds['driver']['pid']} and coordinator {ds['process']['pid']} boot/start identities verified.\n\nRecorded hash-bound terminal reconciliation and updated owning state/checkpoint/tree. Private ledgers unchanged: 502 attempts, 75.24379311215873 GPU hours retained. Independent review PASS; root readiness/accounting/release pending; no dispatch or release.\n\nNext: {next_action}\n\nLive native/device receipts, whole-episode audits, full execution costs and original validation/formal/ablation outcomes remain unresolved. Goal not complete.\n")
print(json.dumps({'terminal':ref(o/'runtime-review-terminal-reconciliation-v1.json'),'summary':ref(o/'operational-summary.json')},indent=2))
