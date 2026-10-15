from pathlib import Path
import json,hashlib,datetime,os,fcntl,subprocess,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001789'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p): return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def atomic(p,d,y=False):
 tmp=p.with_name(p.name+'.turn1789.tmp'); tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if y else json.dumps(d,indent=2)+'\n'); os.replace(tmp,p)
prev=read(A/'turns/001788/operational-summary-v1.json'); driver=read(A/'driver-status.json'); boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(r):
 v=dict(r,alive=False,identity_verified=False); p=Path('/proc')/str(r['pid'])/'stat'
 if p.exists():
  x=p.read_text().rsplit(') ',1)[1].split(); v.update(state=x[0],alive=x[0]!='Z',identity_verified=boot==r['boot_id'] and int(x[19])==r['start_ticks'])
 return v
proc=read(Path(prev['measurement']['process_record']['path'])); handles={k:ident(proc[k]) for k in ['wrapper','controller']}; handles.update(driver=ident(driver['driver']),coordinator=ident(driver['process']))
ledgers={}
for name,r in prev['ledger_prefixes'].items():
 b=Path(r['path']).read_bytes(); assert hashlib.sha256(b[:r['bytes']]).hexdigest()==r['sha256']; ledgers[name]={**ref(Path(r['path'])),'prior_prefix_preserved':True}
source=prev['current_source'].copy(); assert subprocess.check_output(['git','-C',source['worktree'],'rev-parse','HEAD'],text=True).strip()==source['commit']; source['tracked_clean']=subprocess.run(['git','-C',source['worktree'],'diff','--quiet','HEAD']).returncode==0
release=read(Path(prev['measurement']['release']['path'])); assert ref(Path(prev['measurement']['release']['path']))['sha256']==prev['measurement']['release']['sha256']
now=datetime.datetime.now(datetime.timezone.utc); ex=Path(prev['measurement']['exit_path']); measurement=prev['measurement'].copy(); measurement.update(wrapper=handles['wrapper'],controller=handles['controller'],live_handles=[handles[k] for k in ['wrapper','controller'] if handles[k]['alive'] and handles[k]['identity_verified']],status='READINESS_MEASUREMENT_EXIT_REQUIRES_RECONCILIATION' if ex.exists() else 'READINESS_MEASUREMENT_RUNNING')
if ex.exists(): measurement['exit']=read(ex)
summary=dict(schema='autonomy-operational-summary-v1',turn=1789,at=now.isoformat(),current_source=source,owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status=measurement['status'],ledger_prefixes=ledgers,completed_work=['Verified bound handoff and exact authorization hashes; read resource isolation, owning state/checkpoint and current measurement release.','Prior turn receipt confirms normal exit; verified existing wrapper/controller and current driver/coordinator PID, boot and start identities.','Verified all four private ledger prefixes preserved and current engineering source unchanged; monitored existing measurement without dispatch, replay or source mutation.'],next_bounded_step=prev['next_bounded_step'],unresolved_evidence=prev['unresolved_evidence'],measurement=measurement,deadline_utc=prev['deadline_utc'],stop_present=any(os.path.lexists(p) for p in release['stop_authority']['paths']),deadline_passed=now>=datetime.datetime.fromisoformat(prev['deadline_utc'].replace('Z','+00:00')),target_met=False)
p=T/'operational-summary-v1.json'; assert not p.exists(); atomic(p,summary); sr=ref(p); (T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX); fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text()); c=read(C/'checkpoint.json'); tree=read(C/'idea_tree.json')
 for d in [s,c]: d.update(n36_preparation_measurement_execution=measurement,current_owned_workers=[measurement],latest_operational_summary=sr,next_action=summary['next_bounded_step'],updated_at=summary['at'])
 tree['nodes']['15.6'].update(result=measurement['status'],insight=summary['next_bounded_step'],readiness_measurement=measurement)
 atomic(W/'research-state.yaml',s,True); atomic(C/'checkpoint.json',c); atomic(C/'idea_tree.json',tree)
print(json.dumps({'summary':sr,'status':measurement['status'],'handles':handles,'stop':summary['stop_present'],'deadline_passed':summary['deadline_passed']}))
