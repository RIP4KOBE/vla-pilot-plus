import pathlib,json,hashlib,datetime,subprocess,fcntl,os,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001624';O=A/'turns/001617/recovery-implementation';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def put(p,v,y=False):
 q=p.with_name(p.name+'.tmp-001624');q.write_text(yaml.safe_dump(v,sort_keys=False,allow_unicode=True) if y else json.dumps(v,indent=2)+'\n');os.replace(q,p)
prior=read(A/'turns/001623/operational-summary-v1.json');report=read(O/'report-v1.json');exit=read(O/'exit-v1.json');assert exit['exit']==0 and not exit['timeout']
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';a=p.read_text().rsplit(')',1)[1].split() if p.exists() else [];m=bool(a and int(a[19])==h['start_ticks'] and h['boot_id']==boot);return {**h,'identity_matches':m,'live':bool(m and a[0]!='Z'),'observed_state':a[0] if a else None}
h={k:ident(v) for k,v in prior['live_handles'].items()};assert not any(v['live'] for v in h.values())
refs=[]
def verify(x):
 if isinstance(x,dict):
  if 'path' in x and 'sha256' in x:
   p=pathlib.Path(x['path']);p=p if p.is_absolute() else pathlib.Path(report['implementation_worktree'])/p;assert ref(p)['sha256']==x['sha256'],str(p);refs.append(ref(p))
  for v in x.values():verify(v)
 elif isinstance(x,list):
  for v in x:verify(v)
verify(report)
for r in prior['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
w=report['implementation_worktree'];assert subprocess.check_output(['git','-C',w,'rev-parse','HEAD'],text=True).strip()==report['final_commit'];assert not subprocess.check_output(['git','-C',w,'status','--porcelain','--untracked-files=no'],text=True).strip()
now=datetime.datetime.now(datetime.timezone.utc).isoformat();nxt='Perform independent scoped source review of R1 commit f256fecedbcf0d47b807aeaa196407cb24933a41 against turn001616 prospective amendment and turn001617 report/binding-impact. CPU implementation terminal reconciled in turn001624; do not repeat broad tests or launch GPU. After acceptance refresh only affected bindings, independent B5 and root adoption/release gates. Preserve invalid parent charges and all scientific gates.'
r=dict(schema='n36-engineering-r1-terminal-reconciliation-v1',at=now,status='TERMINAL_CPU_IMPLEMENTATION_HASH_VERIFIED_PENDING_INDEPENDENT_REVIEW',source_before=report['start_commit'],source_after=report['final_commit'],report=ref(O/'report-v1.json'),exit=ref(O/'exit-v1.json'),terminal_handles=h,verified_immediate_references=refs,tracked_worktree_clean=True,ledger_prefixes_preserved=True,tests=report['test_commands_and_results'],source_adopted=False,release_enabled=False,target_met=False,next_action=nxt);put(T/'terminal-reconciliation-v1.json',r)
d=read(A/'driver-status.json');s={**prior,'turn':1624,'at':now,'driver':ident(d['driver']),'coordinator':ident(d['process']),'live_handles':{},'terminal_handles':h,'executor_exit_exists':True,'active_executor':None,'completed_work':['Verified bound authority, ACTIVE/PASS resource isolation, owning state/checkpoint, prior normal turn and unchanged private ledger prefixes.','Reconciled normally exited CPU executor, clean f256fec commit and 32 immediate hash-bound references.','Verified logged CPU results: 46 final R1, 205 combined engineering, 97 shared and 40 STOP tests; no broad retest or GPU dispatch.'],'next_bounded_step':nxt,'terminal_reconciliation':ref(T/'terminal-reconciliation-v1.json')};put(T/'operational-summary-v1.json',s);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
with (C/'state.lock').open('a') as l:
 fcntl.flock(l,fcntl.LOCK_EX)
 with (W/'data/qd-ed-state.lock').open('a') as l2:
  fcntl.flock(l2,fcntl.LOCK_EX)
  for p,y in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
   v=yaml.safe_load(p.read_text()) if y else read(p);rec=dict(v['n36_engineering_r1_implementation']);rec.update(status=r['status'],source_after=report['final_commit'],report=ref(O/'report-v1.json'),terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'));v.update(n36_engineering_r1_implementation=rec,active_executor=None,next_action=nxt,updated_at=now,latest_operational_summary=ref(T/'operational-summary-v1.json'));put(p,v,y)
  p=C/'idea_tree.json';v=read(p);v['nodes']['15.6'].update(n36_engineering_r1_implementation=rec,result=r['status'],insight='R1 CPU repair completed and immediate evidence verified; independent source review, affected bindings and release gates pending. No scientific success or GPU dispatch.');put(p,v)
print(json.dumps({'summary':ref(T/'operational-summary-v1.json'),'status':r['status']}))
