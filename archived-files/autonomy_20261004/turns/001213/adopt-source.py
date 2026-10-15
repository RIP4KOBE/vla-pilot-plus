import pathlib,json,hashlib,datetime,subprocess,fcntl,shutil,os,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001213').resolve();cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';sp=w/'research-state.yaml';tp=cp.parent/'idea_tree.json'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def check(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256'],r['path']
def write(p,x):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(x,indent=2)+'\n');q.replace(p)
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1213
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for h in [ds['driver'],ds['process']]:
 st=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(st[19])==h['start_ticks'] and st[0]!='Z'
assert not os.path.lexists(a/'STOP') and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
prior=read(a/'turns/001212/operational-summary.json');assert read(a/'turns/001212/receipt.json')['exit']==0
ledgers={}
for key in ['ledger','health_ledger']:
 r=prior[key];b=pathlib.Path(r['path']).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];ledgers[key]=r
rpath=a/'turns/001210/identity-review/report-v1.json';r=read(rpath);assert r['status']=='PASS' and not r['blocking_findings']
base=r['source_before'];target=r['source_after'];assert git('rev-parse','HEAD')==base;assert git('rev-parse',target+'^')==base
assert git('branch','--show-current')=='exp/rdt-qd-ed-final-20260921T093925Z'
assert git('-C',r['worktree'],'rev-parse','HEAD')==target and not git('-C',r['worktree'],'status','--porcelain','--untracked-files=no')
for e in r['evidence']:check(e)
for e in r['source_evidence']:
 b=subprocess.check_output(['git','show',target+':'+e['path']]);assert hashlib.sha256(b).hexdigest()==e['sha256']
names=git('diff','--name-only',base,target).splitlines();assert len(names)==11 and all(n.startswith(('scripts/qd_ed_n36_','tests/test_n36_')) for n in names)
assert not git('diff','--name-only','HEAD','--',*names)
subprocess.run(['git','diff','--check',base,target],check=True)
diff=subprocess.check_output(['git','diff',base,target]);(o/'adopted-source.diff').write_bytes(diff)
assert hashlib.sha256(diff).hexdigest()==r['checks']['actual_diff_sha256']
next_action='Recompose N36R1 runtime/closure/controller/inventory/seed bindings and all40 actual manifests on adopted source 066f2bf57e05111fea329ff7c393ac3e002d7c0f using reviewed native metadata draft from turn1203 and exact operational protocol/accounting templates from turn1205. Freshly reconcile full private accounting and adopt finite authority; obtain detached root production review/release before metered GPU7 dispatch. Preserve original failed charge, scientific gates, reserves and October11 deadline.'
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert not s.get('active_controller') and not c.get('active_controller') and not s.get('current_owned_workers') and not s.get('in_flight_executor')
 assert s['source_commit']==base and s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 for h in s['closed_n36_controller']['handles'].values():
  p=pathlib.Path(f'/proc/{h["pid"]}/stat')
  if p.exists():assert int(p.read_text().rsplit(')',1)[1].split()[19])!=h['start_ticks']
 for f in [sp,cp,tp]:shutil.copyfile(f,o/(f.name+'.before'))
 rec={'schema':'n36r1-source-adoption-v1','at':now.isoformat(),'status':'APPROVED_OPERATIONAL_SOURCE_ONLY','source_before':base,'source_after':target,'review':ref(rpath),'diff':ref(o/'adopted-source.diff'),'changed_paths':names,'science_unchanged':True,'gpu_dispatch_authorized':False,'budget_adopted':False,'production_release':False,'ledger_prefixes':ledgers,'next_action':next_action}
 write(o/'source-adoption-intent-v1.json',rec)
 result=subprocess.run(['git','merge','--ff-only',target],text=True,capture_output=True);(o/'source-adoption-git.txt').write_text(result.stdout+result.stderr);assert result.returncode==0
 assert git('rev-parse','HEAD')==target and not git('diff','--name-only','HEAD','--',*names)
 write(o/'source-adoption-v1.json',{**rec,'status':'ADOPTED_OPERATIONAL_SOURCE_ONLY','git_result':ref(o/'source-adoption-git.txt')})
 for obj in [s,c]:
  obj.update(source_commit=target,n36r1_source_adoption=ref(o/'source-adoption-v1.json'),phase='N36R1_SOURCE_ADOPTED_RUNTIME_PREPARATION_PENDING',next_action=next_action,updated_at=now.isoformat(),automatic_gpu_dispatch_authorized=False)
 t['nodes']['15.6'].update(status='running',score=None,result='N36R1_OPERATIONAL_SOURCE_ADOPTED_RUNTIME_PENDING',operational_source_adoption=ref(o/'source-adoption-v1.json'))
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
for key,r0 in ledgers.items():assert ref(pathlib.Path(r0['path']))['sha256']==r0['sha256']
summary={'schema':'autonomy-operational-summary-v1','at':now.isoformat(),'turn':1213,'source_commit':target,'status':'N36R1_SOURCE_ADOPTED_RUNTIME_PREPARATION_PENDING','handles':{},'driver':ds['driver'],'coordinator':ds['process'],'gpu_cohort_running':False,**ledgers,'budget_snapshot':s['budget_snapshot'],'stop_present':False,'deadline':'2026-10-11T11:13:13Z','source_adoption':ref(o/'source-adoption-v1.json'),'completed_work':['Verified authority hashes, live driver/coordinator boot-start identities, terminal cohort records and unchanged private ledger prefixes. Prior coordinator exited normally.','Verified independent review evidence/source hashes and exact reviewed 11-file diff; fast-forward adopted operational source into owning branch without modifying scientific files or frozen artifacts.','Updated owning state/checkpoint/tree under state lock; preserved all charges and protected reserves. No GPU or provider dispatch.'],'next_action':next_action,'unresolved_evidence':r['remaining_runtime_scientific_gates'][1:],'target_met':False}
write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f"Current source {target}. Driver {ds['driver']['pid']}/{ds['driver']['start_ticks']}; coordinator {ds['process']['pid']}/{ds['process']['start_ticks']}; boot {boot}. No live experiment/executor handles. STOP absent; deadline 2026-10-11T11:13:13Z.\n\nAdopted independently reviewed operational N36R1 repair; source diff and evidence verified. Owning state/checkpoint/tree updated. Both private ledger prefixes unchanged, retaining 503 attempts and 75.26779409697457 GPUh. Existing 118 distinct CPU test passes reviewed; no broad tests repeated. No budget or GPU release granted.\n\nNext: {next_action}\n\nUnresolved: runtime readiness/native audits, actual Dev evidence, validation/formal and required ablations. Original goal not met.\n")
print(json.dumps({'source':target,'summary':ref(o/'operational-summary.json')},indent=2))
