import pathlib,json,hashlib,datetime,subprocess,fcntl,shutil,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001184').resolve();cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';sp=w/'research-state.yaml';tp=cp.parent/'idea_tree.json'
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return {'path':str(p.resolve()),'sha256':digest(p)}
def check(r):assert digest(pathlib.Path(r['path']))==r['sha256'],r['path']
def write(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1184
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];st=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(st[19])==h['start_ticks'] and st[0]!='Z'
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001183/receipt.json')['exit']==0
prior=read(a/'turns/001183/operational-summary.json');ledgers=prior['ledger_prefixes']
for r in ledgers.values():check(r);assert pathlib.Path(r['path']).stat().st_size==r['bytes']
rp=a/'turns/001180/repair-review/report-v1.json';r=read(rp);candidate=r['candidate_source'];old=git('rev-parse','HEAD');assert old==prior['source'] and candidate==prior['candidate_source'];assert r['verdict']=='PASS'
for v in r['verified_direct_references'].values():check(v)
assert git('-C',r['worktree'],'rev-parse','HEAD')==candidate
assert not git('-C',r['worktree'],'status','--porcelain','--untracked-files=no')
subprocess.run(['git','merge-base','--is-ancestor',old,candidate],check=True)
changed=git('diff','--name-only',old,candidate).splitlines();dirty=git('diff','--name-only','HEAD').splitlines();assert not set(changed)&set(dirty)
assert not git('diff','--cached','--name-only')
assert git('branch','--show-current')=='exp/rdt-qd-ed-final-20260921T093925Z'
assert all(p.startswith(('configs/','core/','scripts/','tests/','docs/n36-')) or p=='main.py' for p in changed)
assert all(not (w/p).exists() for p in git('diff','--name-only','--diff-filter=A',old,candidate).splitlines())
for pid in [54422,54424]:assert not pathlib.Path(f'/proc/{pid}').exists()
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None and s['in_flight_executor'] is None
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 check(s['n36_audit_repair_review']['report']);check(s['n36_repair_review_terminal_reconciliation'])
 preserved={p:digest(w/p) for p in dirty}
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before'))
 intent={'schema':'n36-source-adoption-intent-v1','at':now.isoformat(),'old_source':old,'reviewed_source':candidate,'authority':ref(a/'user-authorization-v1.json'),'acceptance':s['n36_repair_review_terminal_reconciliation'],'review':ref(rp),'changed_files':changed,'preserved_dirty_hashes':preserved,'gpu_dispatch_authorized':False,'scientific_promotion':False,'scope':'Exact reviewed source integration for prospective Dev preparation only; no benchmark promotion or protected evaluation.'}
 write(o/'source-adoption-intent-v1.json',intent)
 result=subprocess.run(['git','-c','core.hooksPath=/dev/null','merge','--ff-only',candidate],text=True,capture_output=True)
 (o/'git-integration.log').write_text(result.stdout+result.stderr);assert result.returncode==0,result.stderr
 assert git('rev-parse','HEAD')==candidate
 assert all(digest(w/p)==v for p,v in preserved.items())
 for p in changed:
  assert (w/p).read_bytes()==subprocess.check_output(['git','show',candidate+':'+p]),p
 for v in ledgers.values():check(v)
 adoption={**intent,'schema':'n36-source-adoption-v1','adopted':True,'source_tree':git('rev-parse','HEAD^{tree}'),'dirty_files_preserved':True,'ledgers_unchanged':True,'exact_changed_blobs_verified':True,'intent':ref(o/'source-adoption-intent-v1.json')}
 write(o/'source-adoption-v1.json',adoption)
 next_step='Prepare actual pinned N36 runtime and source-only startup/native-build composition on adopted ab8e8c6 under RT-01/RT-02/RT-05; rebuild all40 prospective manifests. No GPU dispatch before independent accounting/runtime review and separately frozen release. RT-03/RT-04 require metered native whole-episode evidence; original scientific goals remain open.'
 for obj in [s,c]:obj.update(source_commit=candidate,n36_source_adoption=ref(o/'source-adoption-v1.json'),phase='N36_SOURCE_ADOPTED_PENDING_RUNTIME_PREPARATION',next_action=next_step,updated_at=now.isoformat())
 t['nodes']['15.6'].update(status='running',score=None,result='CPU_REVIEWED_SOURCE_ADOPTED_RUNTIME_PENDING',code_ref=candidate,source_adoption=ref(o/'source-adoption-v1.json'))
 q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
summary={**prior,'at':now.isoformat(),'source':candidate,'candidate_source':candidate,'driver':ds['driver'],'coordinator':ds['process'],'completed':'Integrated exact independently reviewed N36 source by fast-forward on owning study branch. Verified all 34 changed files against Git blobs and preserved all dirty records through integration; ledger prefixes unchanged. Updated owning state/checkpoint/tree under operation lock. No tests repeated and no GPU work launched.','source_adoption':ref(o/'source-adoption-v1.json'),'next_action':next_step,'live_handles':{},'active_controller':None,'new_gpu_dispatches':0,'target_met':False}
summary.pop('terminal_reconciliation',None);write(o/'operational-summary.json',summary)
(o/'operational-summary.md').write_text(f'Adopted exact reviewed N36 source {candidate}; 34 changed blobs verified, dirty study records preserved during integration. Driver {ds["driver"]["pid"]} and coordinator {ds["process"]["pid"]} boot/start identities verified; no active experiment/reviewer handles. Prior turn completed normally.\n\nRetained 502 attempts / 75.24379311215873 GPU hours and unchanged private ledger prefixes. No GPU dispatch, protected evaluation, scientific promotion, or completion claim.\n\nNext: {next_step}\n\nUnresolved: pinned runtime/source/native-build feasibility, before/after native receipts, whole-episode physical continuity, measured overhead, fresh matched Dev, validation/formal and required ablations.\n')
print(json.dumps({'adoption':ref(o/'source-adoption-v1.json'),'source':candidate,'next_action':next_step},indent=2))
