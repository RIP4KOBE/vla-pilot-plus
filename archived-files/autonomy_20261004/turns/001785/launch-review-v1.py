from pathlib import Path
import json,hashlib,datetime,subprocess,os,fcntl,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001785'; O=T/'independent-b5-review'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def read(p):return json.loads(p.read_text())
def put(p,v):
 assert not p.exists();p.write_text(json.dumps(v,indent=2)+'\n');return ref(p)
def ident(pid):
 s=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
a=read(O/'authority-v1.json');prev=read(A/'turns/001784/operational-summary-v1.json');d=read(A/'driver-status.json')
assert d['turn']==1785
now=datetime.datetime.now(datetime.timezone.utc)
assert now<datetime.datetime.fromisoformat(a['stop_authority']['deadline'].replace('Z','+00:00'))
assert not any(Path(p).exists() for p in a['stop_authority']['paths'])
for k in ['driver','process']:
 actual=ident(d[k]['pid']);assert all(actual[x]==d[k][x] for x in ['pid','boot_id','start_ticks']) and actual['state']!='Z'
for r in a['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256']
for k in ['graph','admission','composition','root_controller_acceptance','standing_authority']:
 r=a[k];assert ref(Path(r['path']))['sha256']==r['sha256']
assert subprocess.check_output(['git','-C',a['source']['worktree'],'rev-parse','HEAD'],text=True).strip()==a['source']['commit']
assert not subprocess.check_output(['git','-C',a['source']['worktree'],'status','--porcelain','--untracked-files=no'],text=True).strip()
s=yaml.safe_load((W/'research-state.yaml').read_text());assert not s.get('current_owned_workers') and not s.get('in_flight_executor') and not s.get('in_flight_executors')
assert not (O/'wrapper-launch-v1.json').exists() and not (O/'process-v1.json').exists()
with (O/'wrapper.log').open('wb') as log:
 p=subprocess.Popen(['python',str(O/'run-executor.py')],cwd=W,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
h=ident(p.pid);launch=put(O/'wrapper-launch-v1.json',dict(at=now.isoformat(),wrapper=h,authority=ref(O/'authority-v1.json'),gpu_authorized=False))
record=dict(status='RUNNING_CPU_ONLY_INDEPENDENT_B5_REVIEW',source=a['source']['commit'],worktree=a['source']['worktree'],authority=ref(O/'authority-v1.json'),output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=h,gpu_authorized=False,source_edits_authorized=False)
next_step='Monitor turn001785 independent-b5-review by exact PID/boot/start identity; do not duplicate. Reconcile terminal artifacts and review exact graph/source bindings. After independent B5 acceptance, root may adopt graph/accounting and issue a separate finite preparation-only release. Measured readiness and separate health/episode gates remain required.'
summary=dict(prev,turn=1785,at=now.isoformat(),live_handles=dict(driver=ident(d['driver']['pid']),coordinator=ident(d['process']['pid']),review_wrapper=h),controller_status='No active GPU cohort. Independent CPU-only B5 review of current disabled graph launched.',completed_work=['Verified bound handoff, exact authorization, continuation and completion-contract hashes.','Verified current driver/coordinator PID, boot and start ticks; STOP absent and deadline open; previous turn receipt successful and previous executor terminal.','Verified four unchanged owning ledger prefixes, clean exact engineering source and launched bounded independent B5 review using official current-login Codex gpt-6-astra.'],next_bounded_step=next_step,unresolved_evidence=['Independent B5 review pending; graph/accounting adoption and preparation-only release not yet granted.','Native readiness, scientific promotion, validation/formal and required ablations remain unproven.'],review=record,target_met=False)
sr=put(T/'operational-summary-v1.json',summary)
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 for path,isy in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  v=yaml.safe_load(path.read_text()) if isy else read(path)
  v.update(n36_current_graph_independent_b5_review=record,next_action=next_step,latest_operational_summary=sr,last_updated_utc=now.isoformat())
  tmp=path.with_name(path.name+'.turn001785.tmp');tmp.write_text(yaml.safe_dump(v,sort_keys=False,allow_unicode=True) if isy else json.dumps(v,indent=2)+'\n');os.replace(tmp,path)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='CURRENT_GRAPH_INDEPENDENT_B5_REVIEW_RUNNING',insight=next_step,current_graph_b5_review=record)
 path=C/'idea_tree.json';tmp=path.with_name(path.name+'.turn001785.tmp');tmp.write_text(json.dumps(tree,indent=2)+'\n');os.replace(tmp,path)
(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(dict(summary=sr,launch=launch,wrapper=h)))
