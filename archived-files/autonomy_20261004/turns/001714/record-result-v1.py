import pathlib,json,hashlib,datetime,fcntl,os,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001714';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 q=p.with_name(p.name+'.tmp-001714');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
old=read(A/'turns/001713/operational-summary-v1.json');resultpath=T/'refreshed-disabled-graph/refresh-result-v1.json';result=read(resultpath);assert result['status']=='PASS'
for r in old['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))==r
now=datetime.datetime.now(datetime.timezone.utc)
nextstep='Disabled graph refresh passed unchanged complete verify_graph at turn001714, bound to root-reviewed controller and d322548 source. Next create the separately authorized finite source-bound readiness measurement review/release using existing policy and validated graph; document reservation arithmetic and preserve protected reserves/history, check STOP/deadline and exact live handles before dispatch. Actual native/runtime measured evidence and independent acceptance, B5/source/accounting adoption, and distinct fresh health/episode releases remain required.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in old['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))==r
 for f,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(f.read_text()) if isyaml else read(f);d['n36_engineering_r1_disabled_graph_root_refresh']=ref(resultpath);d['next_action']=nextstep;d['updated_at']=now.isoformat()
  if isyaml:
   q=f.with_name(f.name+'.tmp-001714');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,f)
  else:put(f,d)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='R1_DISABLED_GRAPH_PASS_FINITE_READINESS_RELEASE_PENDING',insight=nextstep);put(C/'idea_tree.json',tree)
driver=read(A/'driver-status.json');boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=driver[k];a=pathlib.Path('/proc',str(h['pid']),'stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(a[19])==h['start_ticks'];h['observed_state']=a[0]
old.update(turn=1714,at=now.isoformat(),driver_status=driver,live_executor_handles={},completed_work=['Verified bound authority, driver/coordinator PID boot/start identities, prior normal completion and unchanged owning ledger prefixes.','Refreshed only controller review bindings and dependent disabled graph manifests; preserved source, science, runtime and accounting.','Unchanged complete verify_graph passed on all refreshed bindings; no GPU or provider measurement dispatched.','Recorded graph result and next action in owning state/checkpoint/idea tree.'],disabled_graph_refresh=ref(resultpath),next_bounded_step=nextstep,unresolved_evidence=['Finite readiness measurement and independently accepted actual native/runtime evidence remain pending.','B5/source/accounting adoption and distinct fresh health/episode releases remain pending.','Original validation/formal/required ablation goal remains unmet.'])
put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n')
print(json.dumps(dict(status=result['status'],elapsed_seconds=result['elapsed_seconds'],summary=str(T/'operational-summary-v1.json'))))
