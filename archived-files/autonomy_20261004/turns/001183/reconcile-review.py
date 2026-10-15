import pathlib,json,hashlib,datetime,subprocess,fcntl,shutil,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001183').resolve();p=a/'turns/001180/repair-review'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def check(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
def write(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1183
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];st=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(st[19])==h['start_ticks'] and st[0]!='Z'
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001182/receipt.json')['exit']==0
prior=read(a/'turns/001182/operational-summary.json');ledgers={}
for name,r in prior['ledger_prefixes'].items():
 f=w/'data'/name;b=f.read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[name]={**ref(f),'bytes':len(b),'prior_prefix_matches':True}
r=read(p/'report-v1.json');assert r['verdict']=='PASS' and r['status']=='PASS_BOUNDED_SOURCE_REPAIR_REVIEW_ONLY';assert read(p/'executor-exit-v1.json')['exit']==0
for pid in [54422,54424]:assert not pathlib.Path(f'/proc/{pid}').exists()
wt=pathlib.Path(r['worktree']);source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();candidate=subprocess.check_output(['git','-C',str(wt),'rev-parse','HEAD'],text=True).strip()
assert source==prior['source'] and candidate==r['candidate_source']==prior['candidate_source']
assert not subprocess.check_output(['git','-C',str(wt),'status','--porcelain','--untracked-files=no'],text=True).strip()
check(r['authority'])
for v in r['verified_direct_references'].values():check(v)
for v in r['source_files']:
 assert ref(pathlib.Path(v['absolute_path']))['sha256']==v['sha256']
 assert hashlib.sha256(subprocess.check_output(['git','-C',str(wt),'show',candidate+':'+v['path']])).hexdigest()==v['sha256']
terminal={'schema':'n36-repair-review-terminal-reconciliation-v1','at':now.isoformat(),'status':r['status'],'source':source,'candidate_source':candidate,'report':ref(p/'report-v1.json'),'exit':ref(p/'executor-exit-v1.json'),'previous_handles':read(p/'executor-process-v1.json'),'old_processes_absent':True,'direct_references_and_reviewed_source_verified':True,'accepted_scope':r['scope'],'findings':[{'id':f['id'],'status':f['status'],'title':f['title'],'limits':f['limits']} for f in r['findings']],'unresolved_runtime_obligations':r['unresolved_runtime_obligations'],'ledger_prefixes':ledgers,'source_adopted':False,'gpu_release':False,'promotion':False,'target_met':False}
write(o/'repair-review-terminal-reconciliation-v1.json',terminal)
next_step='Adopt reviewed N36 source ab8e8c6 through the isolated source integration process, then prepare actual pinned runtime/source-only startup and native-build composition under RT-01 through RT-05. No GPU dispatch before a separately frozen prospective release; fresh Dev gates and original validation/formal/ablation goal remain open.'
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 for obj in [s,c]:check(obj['n36_audit_repair_review']['authority']);check(obj['n36_audit_repair_review']['process_record'])
 for f in [sp,cp,tp]:shutil.copyfile(f,o/(f.name+'.before'))
 for obj in [s,c]:
  rec={**obj['n36_audit_repair_review'],'status':r['status'],'executor_exited':True,'live_handles':[],'report':ref(p/'report-v1.json'),'exit':ref(p/'executor-exit-v1.json'),'terminal_reconciliation':ref(o/'repair-review-terminal-reconciliation-v1.json')}
  obj.update(n36_audit_repair_review=rec,n36_repair_review_terminal_reconciliation=ref(o/'repair-review-terminal-reconciliation-v1.json'),in_flight_executor=None,phase='N36_CPU_REPAIR_REVIEW_ACCEPTED_PENDING_SOURCE_RUNTIME',next_action=next_step,updated_at=now.isoformat())
 c['inflight_executor']=None
 t['nodes']['15.6'].update(status='running',score=None,result='CPU_REPAIR_REVIEW_ACCEPTED_NO_GPU',audit_repair_review=rec,audit_repair_review_terminal=ref(o/'repair-review-terminal-reconciliation-v1.json'))
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'candidate_source':candidate,'driver':ds['driver'],'coordinator':ds['process'],'live_handles':{},'active_controller':None,'ledger_prefixes':ledgers,'retained_attempts':502,'retained_gpu_hours':75.24379311215873,'new_gpu_dispatches':0,'completed':'Reconciled successful independent N36 repair review exit and absent exact reviewer handles. Verified direct authority/report bindings and reviewed source against candidate Git blobs. Accepted bounded SR-01/SR-02 source repair review with runtime limits retained; owning source unchanged. Updated owning state/checkpoint/tree under state lock.','terminal_reconciliation':ref(o/'repair-review-terminal-reconciliation-v1.json'),'next_action':next_step,'unresolved':[v['requirement'] for v in r['unresolved_runtime_obligations']],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f'''N36 independent CPU repair review accepted within its bounded scope. Owning source {source}; candidate {candidate}. Reviewer wrapper 54422 / executor 54424 exited normally and are absent; no live experiment controller or GPU worker. Driver {ds['driver']['pid']} and coordinator {ds['process']['pid']} identity verified.\n\nVerified authority/direct references, reviewed source bytes and unchanged private ledger prefixes. Retained 502 attempts and 75.24379311215873 GPU hours; zero new GPU dispatches. Both prior audit issues passed source review. Recorded hash-bound terminal reconciliation and updated owning state/checkpoint/tree; no source adoption or release.\n\nNext: {next_step}\n\nPinned runtime, native receipts, physical observation joins, overhead, fresh matched Dev outcomes, validation/formal and required ablations remain unresolved. Goal not complete.\n''')
print(json.dumps({'terminal':ref(o/'repair-review-terminal-reconciliation-v1.json'),'summary':ref(o/'operational-summary.json'),'next_action':next_step},indent=2))
