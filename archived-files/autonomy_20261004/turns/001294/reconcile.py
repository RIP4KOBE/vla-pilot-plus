import json,pathlib,hashlib,datetime,fcntl,yaml,subprocess
owner=pathlib.Path.cwd(); base=owner.parent/'autonomy_20261004'; turn=base/'turns/001294'; review=base/'turns/001292/independent-b5-review'; coord=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 p=pathlib.Path(p); b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 p=pathlib.Path(p); t=p.with_suffix(p.suffix+'.tmp'); t.write_text(json.dumps(d,indent=2)+'\n'); t.replace(p)
def handle(pid):
 p=pathlib.Path('/proc')/str(pid)/'stat'
 if not p.exists():return dict(pid=pid,absent=True)
 f=p.read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(f[19]),state=f[0])
now=datetime.datetime.now(datetime.timezone.utc); prior=json.loads((base/'turns/001293/entry-reconciliation-v1.json').read_text()); receipt=json.loads((base/'turns/001293/receipt.json').read_text()); report=json.loads((review/'report-v1.json').read_text())
assert report['status']=='PASS' and report['decision']=='PASS_PREPARATION_REQUIRES_ROOT_RELEASE'
assert json.loads((review/'executor-exit-v1.json').read_text())['exit']==0
for p in report['evidence_hashes']:
 assert ref(p['path'])['sha256']==p['sha256'],p['path']
for p in prior['owning_ledgers'].values():assert ref(p['path'])==p
for pid in [732790,732791]:assert handle(pid).get('absent') or handle(pid).get('state')=='Z'
stop=any(pathlib.Path(p).exists() for p in report['STOP_paths']); deadline=report['deadline']; assert not stop and now<datetime.datetime.fromisoformat(deadline.replace('Z','+00:00'))
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==report['source_commit']
driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1294
for k in ['driver','process']:
 live=handle(driver[k]['pid']);assert all(live[x]==driver[k][x] for x in ['pid','boot_id','start_ticks'])
entry=dict(schema='autonomy-entry-reconciliation-v1',turn=1294,at=now.isoformat(),source=source,driver=handle(driver['driver']['pid']),coordinator=handle(driver['process']['pid']),prior_turn_receipt=ref(base/'turns/001293/receipt.json'),owning_ledgers=prior['owning_ledgers'],STOP_exists=stop,deadline=deadline,owned_gpu_workers=[],reviewer={str(p):handle(p) for p in [732790,732791]})
put(turn/'entry-reconciliation-v1.json',entry)
record=dict(schema='n36r2-b5-terminal-reconciliation-v1',at=now.isoformat(),status='CPU_B5_ACCEPTED_FINAL_FREEZE_PENDING',source=source,report=ref(review/'report-v1.json'),external_b5_record=ref(review/'external-b5-review-v1.json'),exit=ref(review/'executor-exit-v1.json'),verified_evidence_count=len(report['evidence_hashes']),owning_ledgers=prior['owning_ledgers'],release_enabled=False,target_met=False,live_handles=[],remaining_obligations=report['remaining_obligations'])
put(turn/'terminal-reconciliation-v1.json',record)
next_action='Freeze N36R2 final plan binding turn001292 external-b5-review-v1.json with actual unmodified verifier; omit root_review/execution_release keys. Obtain separate external root production review and caller-anchored detached release, regenerate contexts, then locked admission with full runtime/native/model checks. No dispatch until gates pass.'
with open(owner/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p in [owner/'research-state.yaml',coord/'checkpoint.json']:
  (turn/(p.name+'.before')).write_bytes(p.read_bytes()); d=yaml.safe_load(p.read_text()) if p.suffix=='.yaml' else json.loads(p.read_text())
  assert d['source_commit']==source if 'source_commit' in d else True
  key='n36r2_readiness_b5_review'; d[key]['status']=record['status']; d[key]['historical_handles']=d[key].pop('handles',{});d[key]['live_handles']=[];d[key]['report']=record['report'];d[key]['external_b5_record']=record['external_b5_record'];d[key]['terminal_reconciliation']=ref(turn/'terminal-reconciliation-v1.json');d['next_action']=next_action
  if p.suffix=='.yaml':
   t=p.with_suffix('.yaml.tmp');t.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));t.replace(p)
  else:put(p,d)
summary=dict(schema='autonomy-operational-summary-v1',turn=1294,at=now.isoformat(),source=source,live_handles={},driver=entry['driver'],coordinator=entry['coordinator'],completed_work='Verified normal prior completion, current identities and unchanged private ledgers. Reconciled independent B5 PASS and all immediate evidence hashes; closed terminal CPU reviewer handles in owner state/checkpoint. No source, budget or GPU changes.',next_bounded_step=next_action,unresolved_evidence=report['remaining_obligations']+['Original validation/formal/required ablation success remains unevidenced.'],retained_attempts=504,retained_gpu_hours=75.49265038509455,release_enabled=False,target_met=False,STOP_exists=False,deadline=deadline)
put(turn/'operational-summary.json',summary)
(turn/'operational-summary.md').write_text(f"Source {source}. Driver {entry['driver']['pid']}; coordinator {entry['coordinator']['pid']}; no live reviewer or GPU cohort.\n\n{summary['completed_work']}\n\nRetained 504 attempts / 75.49265038509455 GPUh. STOP absent; deadline {deadline}.\n\nNext: {next_action}\n\nOriginal validation/formal/required ablation evidence remains pending; goal incomplete.\n")
(turn/'operational-summary.sha256').write_text(ref(turn/'operational-summary.json')['sha256']+'  operational-summary.json\n')
print(json.dumps(summary,indent=2))
