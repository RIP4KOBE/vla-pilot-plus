from pathlib import Path
import json,hashlib,datetime,os,fcntl,yaml
W=Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001756';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def atomic(p,d,y=False):
 q=p.with_name(p.name+'.turn1756.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(r):
 p=Path('/proc')/str(r['pid'])/'stat';v=dict(r,alive=False,identity_verified=False)
 if p.exists():
  s=p.read_text().rsplit(') ',1)[1].split();v.update(state=s[0],alive=s[0]!='Z',identity_verified=boot==r['boot_id'] and int(s[19])==r['start_ticks'])
 return v
prev=read(A/'turns/001755/operational-summary-v1.json');proc=read(T/'measurement-process-v1.json');driver=read(A/'driver-status.json');result=read(T/'release-preparation-result-v1.json');release=read(Path(result['release']['path']));now=datetime.datetime.now(datetime.timezone.utc).isoformat()
ledger={}
for name,prior in prev['ledger_prefixes'].items():
 p=Path(prior['path']);b=p.read_bytes();assert hashlib.sha256(b[:prior['bytes']]).hexdigest()==prior['sha256'];ledger[name]={**ref(p),'prior_prefix_preserved':True}
handles={k:ident(proc[k]) for k in ['wrapper','controller']};ex=T/'measurement-exit-v1.json'
nextstep='Monitor existing turn001756 readiness wrapper/controller by PID/boot/start identity; no duplicate launch or identity replay. On terminal exit reconcile preparation and mirrored resource ledgers and retained cost, then inspect only bounded readiness native/runtime/provider evidence for acceptance. Health/episode releases and scientific promotion remain separate; no scientific success established.'
record=dict(status='READINESS_MEASUREMENT_RUNNING' if not ex.exists() else 'READINESS_MEASUREMENT_EXIT_REQUIRES_RECONCILIATION',source=prev['current_source']['commit'],process_record=ref(T/'measurement-process-v1.json'),wrapper=handles['wrapper'],controller=handles['controller'],exit_path=str(ex),release=result['release'],episode_authorized=False,health_authorized=False,live_handles=[v for v in handles.values() if v['alive'] and v['identity_verified']])
summary=dict(schema='autonomy-operational-summary-v1',turn=1756,at=now,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles={**handles,'driver':ident(driver['driver']),'coordinator':ident(driver['process'])},controller_status=record['status'],ledger_prefixes=ledger,completed_work=['Verified hash-bound handoff/authority, owning state/checkpoint, terminal old handles and active driver identity.','Recomputed full private ledger accounting: 507 attempts and 75.68784192475492 GPU-hours; all old charges and unknown telemetry retained.','Adopted exact reviewed disabled preparation graph and separate 600-second, one-provider-call release; production accounting admission passed and protected reserves/margin preserved.','Verified assigned GPU7 idle and launched one source-bound readiness measurement through committed bootstrap; process identities durably recorded.'],next_bounded_step=nextstep,unresolved_evidence=['Readiness measurement outcome and native/runtime/provider evidence pending.','Fresh health/episode releases remain separate and unissued.','Original validation/formal/required ablation evidence remains incomplete.'],accounting=ref(T/'full-ledger-accounting-v1.json'),arithmetic=ref(T/'reservation-arithmetic-v1.json'),release_preparation=ref(T/'release-preparation-result-v1.json'),measurement=record,deadline_utc=prev['deadline_utc'],stop_present=any(os.path.lexists(p) for p in release['stop_authority']['paths']),deadline_passed=datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(prev['deadline_utc'].replace('Z','+00:00')),target_met=False)
assert not (T/'operational-summary-v1.json').exists();(T/'operational-summary-v1.json').write_text(json.dumps(summary,indent=2)+'\n');sr=ref(T/'operational-summary-v1.json')
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=read(C/'checkpoint.json');tree=read(C/'idea_tree.json')
 for d in [s,c]:
  d.update(n36_preparation_release_validation=ref(T/'release-preparation-result-v1.json'),n36_preparation_measurement_execution=record,n36_current_full_ledger_accounting=ref(T/'full-ledger-accounting-v1.json'),current_owned_workers=[record],latest_operational_summary=sr,next_action=nextstep,updated_at=now)
 tree['nodes']['15.6'].update(result=record['status'],insight=nextstep,readiness_measurement=record)
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(dict(summary=sr,measurement=record)))
