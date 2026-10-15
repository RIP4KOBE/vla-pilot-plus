import pathlib,json,hashlib,datetime,subprocess,fcntl,shutil,yaml,os
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001212').resolve();p=a/'turns/001210/identity-review'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def check(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
def write(p,x):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(x,indent=2)+'\n');q.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1212
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for h in [ds['driver'],ds['process']]:
 st=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(st[19])==h['start_ticks'] and st[0]!='Z'
assert not os.path.lexists(a/'STOP') and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
prior=read(a/'turns/001211/operational-summary.json');assert read(a/'turns/001211/receipt.json')['exit']==0
ledgers={}
for key in ['ledger','health_ledger']:
 r=prior[key];f=pathlib.Path(r['path']);b=f.read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[key]={**ref(f),'bytes':len(b),'prior_prefix_matches':True}
for h in prior['handles'].values():assert not pathlib.Path(f'/proc/{h["pid"]}').exists()
r=read(p/'report-v1.json');assert r['status']=='PASS' and not r['blocking_findings'];ex=read(p/'executor-exit-v1.json');assert ex['exit']==0
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==r['source_before']==prior['source_commit']
assert subprocess.check_output(['git','-C',r['worktree'],'rev-parse','HEAD'],text=True).strip()==r['source_after']
for e in r['evidence']:check(e)
for e in r['source_evidence']:
 b=subprocess.check_output(['git','-C',r['worktree'],'show',r['source_after']+':'+e['path']]);assert hashlib.sha256(b).hexdigest()==e['sha256']
terminal={'schema':'n36r1-identity-review-terminal-reconciliation-v1','at':now.isoformat(),'status':'PASS_CPU_IDENTITY_REVIEW_ROOT_ADOPTION_PENDING','source':source,'isolated_commit':r['source_after'],'report':ref(p/'report-v1.json'),'exit':ref(p/'executor-exit-v1.json'),'previous_handles':prior['handles'],'old_processes_absent':True,'review_evidence_hashes_verified':True,'accepted_scope':r['decision_scope'],'remaining_runtime_scientific_gates':r['remaining_runtime_scientific_gates'],'ledger_prefixes':ledgers,'gpu_release':False,'promotion':False,'target_met':False}
write(o/'identity-review-terminal-reconciliation-v1.json',terminal)
next_action='Adopt independently reviewed isolated operational repair 066f2bf57e05111fea329ff7c393ac3e002d7c0f after bounded source/worktree checks; recompose N36R1 runtime, all40 manifests and fresh accounting/authority bindings. Follow turn1210 identity-review remaining_runtime_scientific_gates and preserve original charge, reserves, frozen science and deadline. No GPU dispatch before detached root release.'
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s.get('active_controller') is None and c.get('active_controller') is None
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 rec=s['n36r1_identity_repair_review'];assert rec==c['n36r1_identity_repair_review']==t['nodes']['15.6']['operational_identity_repair_review']
 check(rec['authority']);check(rec['process_record'])
 for f in [sp,cp,tp]:shutil.copyfile(f,o/(f.name+'.before'))
 rec={**rec,'status':terminal['status'],'executor_exited':True,'live_handles':[],'report':terminal['report'],'exit':terminal['exit'],'terminal_reconciliation':ref(o/'identity-review-terminal-reconciliation-v1.json')}
 for obj in [s,c]:obj.update(n36r1_identity_repair_review=rec,in_flight_executor=None,phase='N36R1_IDENTITY_REVIEW_PASSED_ROOT_ADOPTION_PENDING',next_action=next_action,updated_at=now.isoformat())
 c['inflight_executor']=None
 t['nodes']['15.6'].update(status='running',score=None,result='CPU_IDENTITY_REVIEW_PASS_SOURCE_ADOPTION_PENDING',operational_identity_repair_review=rec)
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={'schema':'autonomy-operational-summary-v1','at':now.isoformat(),'turn':1212,'source_commit':source,'isolated_repair_commit':r['source_after'],'status':terminal['status'],'handles':{},'driver':ds['driver'],'coordinator':ds['process'],'gpu_cohort_running':False,'ledger':ledgers['ledger'],'health_ledger':ledgers['health_ledger'],'budget_snapshot':s['budget_snapshot'],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','completed_work':['Verified bound handoff and authority; owning resource isolation ACTIVE/PASS.','Reconciled reviewer normal exit; verified report input and source hashes; CPU review PASS accepted within bounded operational scope.','Updated owning state/checkpoint/tree under state lock, clearing stale in-flight executor. No source adoption or new dispatch; both private ledgers unchanged.'],'terminal_reconciliation':ref(o/'identity-review-terminal-reconciliation-v1.json'),'next_action':next_action,'unresolved_evidence':r['remaining_runtime_scientific_gates'],'target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f"Source {source}; isolated repair {r['source_after']} remains unadopted. Review wrapper245231/executor245232 exited normally; no active GPU cohort. Driver268073/start97715947 and coordinator252758/start145459438 verified on boot {boot}.\n\nIndependent CPU identity review PASS reconciled; owning state/checkpoint/tree updated. Retained 503 attempts /75.26779409697457 GPUh and unchanged ledger prefixes.\n\nNext: {next_action}\n\nFresh runtime/release, live native/audit evidence and original validation/formal/required ablations remain unresolved. Target not met.\n")
print(json.dumps({'summary':ref(o/'operational-summary.json'),'terminal':ref(o/'identity-review-terminal-reconciliation-v1.json')},indent=2))
