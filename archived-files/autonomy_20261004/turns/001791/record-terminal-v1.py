from pathlib import Path
import json,hashlib,datetime,os,fcntl,subprocess,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001791'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p): return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def atomic(p,d,y=False):
 tmp=p.with_name(p.name+'.turn1791.tmp'); tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if y else json.dumps(d,indent=2)+'\n'); os.replace(tmp,p)
prev=read(A/'turns/001790/operational-summary-v1.json'); driver=read(A/'driver-status.json'); boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
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
summary=dict(schema='autonomy-operational-summary-v1',turn=1791,at=now.isoformat(),current_source=source,owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status=measurement['status'],ledger_prefixes=ledgers,completed_work=['Verified bound handoff and exact authorization hashes; read resource isolation, owning state/checkpoint and current measurement release.','Prior turn receipt confirms normal exit; verified existing wrapper/controller and current driver/coordinator PID, boot and start identities.','Verified all four private ledger prefixes preserved and current engineering source unchanged; monitored existing measurement without dispatch, replay or source mutation.'],next_bounded_step=prev['next_bounded_step'],unresolved_evidence=prev['unresolved_evidence'],measurement=measurement,deadline_utc=prev['deadline_utc'],stop_present=any(os.path.lexists(p) for p in release['stop_authority']['paths']),deadline_passed=now>=datetime.datetime.fromisoformat(prev['deadline_utc'].replace('Z','+00:00')),target_met=False)

assert ex.exists() and read(ex)['returncode']==0
assert not measurement['live_handles']
rid=release['resource_id']
rows={n:[json.loads(x) for x in (W/'data'/n).read_text().splitlines() if rid in x] for n in ['readiness-preparation-ledger.jsonl','gpu-healthcheck-ledger.jsonl','attempt-ledger.jsonl']}
assert rows['readiness-preparation-ledger.jsonl']==rows['gpu-healthcheck-ledger.jsonl']
assert not rows['attempt-ledger.jsonl']
a=rows['readiness-preparation-ledger.jsonl']; assert [x['event'] for x in a]==['reserved','dispatched','completed']
terminal=a[-1]; assert terminal['telemetry_complete'] and terminal['error'] is None
assert not (Path('/proc')/str(terminal['process']['pid'])).exists()
proof_path=Path(release['source_record']['path']).parent/'proof.json'
proof=read(proof_path); verified={}
for k,v in proof.items():
 if isinstance(v,dict) and 'path' in v and 'sha256' in v:
  actual=ref(Path(v['path'])); assert actual['sha256']==v['sha256'],k; verified[k]=actual
assert read(Path(proof['accounting']['path']))==a
measurement.update(status='TERMINAL_MEASUREMENT_RECONCILED_READINESS_ACCEPTANCE_PENDING',proof=ref(proof_path),executor_exited=True)
reconciliation=dict(schema='n36-preparation-terminal-reconciliation-v1',at=now.isoformat(),source=source,exit=read(ex),measurement=measurement,verified_proof_references=verified,mirrored_ledger_rows_identical=True,events=[x['event'] for x in a],retained_gpu_process_wall_seconds=terminal['gpu_process_wall_seconds'],retained_gpu_hours=terminal['gpu_process_wall_seconds']/3600,provider_calls=terminal['provider_calls'],no_episode_attempt=True,scientific_success=False,readiness_acceptance_pending=True)
rp=T/'terminal-reconciliation-v1.json'; assert not rp.exists(); atomic(rp,reconciliation)
measurement['terminal_reconciliation']=ref(rp)
summary.update(controller_status=measurement['status'],measurement=measurement,terminal_reconciliation=ref(rp),next_bounded_step='Review measured preparation proof with existing readiness validator and scoped native/runtime/provider checks; refresh exact full-ledger accounting before any prospective health/episode release. Do not replay completed readiness measurement. Scientific promotion and original completion evidence remain pending.',unresolved_evidence=['Measured readiness proof requires scoped acceptance and production runtime binding.','Full-ledger budget subtotals need refresh before next release; terminal charge retained in both private ledgers.','Health/episode releases unissued; validation/formal/required ablation goal incomplete.'])
summary['completed_work'].append('Reconciled clean measurement exit, absent wrapper/controller/worker, identical three-event mirrored resource ledgers and proof reference hashes; retained 234.72371816635132 GPU seconds and one provider call.')

p=T/'operational-summary-v1.json'; assert not p.exists(); atomic(p,summary); sr=ref(p); (T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX); fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text()); c=read(C/'checkpoint.json'); tree=read(C/'idea_tree.json')
 for d in [s,c]: d.update(n36_preparation_measurement_execution=measurement,current_owned_workers=[],latest_operational_summary=sr,next_action=summary['next_bounded_step'],updated_at=summary['at'])
 tree['nodes']['15.6'].update(result=measurement['status'],insight=summary['next_bounded_step'],readiness_measurement=measurement)
 atomic(W/'research-state.yaml',s,True); atomic(C/'checkpoint.json',c); atomic(C/'idea_tree.json',tree)
print(json.dumps({'summary':sr,'status':measurement['status'],'handles':handles,'stop':summary['stop_present'],'deadline_passed':summary['deadline_passed']}))
