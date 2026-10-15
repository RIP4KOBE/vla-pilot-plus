from pathlib import Path
import json,hashlib,subprocess,datetime,os,fcntl,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001755'; P=A/'turns/001753/independent-b5-review'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p): return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify(r):
 p=Path(r['path']);assert '2026-08-10-eds-qd-stage-guidance-transition-design.md' not in str(p); b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==r['sha256'],str(p)
 if 'bytes' in r:assert len(b)==r['bytes'],str(p)
def put(p,x):
 b=(json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode();assert not p.exists();p.write_bytes(b);return ref(p)
def atomic(p,x,isyaml=False):
 q=p.with_name(p.name+'.turn1755.tmp');q.write_text(yaml.safe_dump(x,sort_keys=False,allow_unicode=True) if isyaml else json.dumps(x,indent=2,ensure_ascii=False)+'\n');os.replace(q,p)
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def identity(r):
 f=Path('/proc')/str(r['pid'])/'stat';v=dict(r,alive=False,identity_verified=False)
 if f.exists():
  a=f.read_text().rsplit(') ',1)[1].split();v.update(state=a[0],alive=a[0]!='Z',identity_verified=(boot==r['boot_id'] and int(a[19])==r['start_ticks']))
 return v
prev=read(A/'turns/001754/operational-summary-v1.json');auth=read(P/'authority-v1.json');m=read(P/'file-manifest-v1.json');r=read(P/'review-v1.json');ex=read(P/'exit-v1.json');proc=read(P/'process-v1.json');driver=read(A/'driver-status.json')
assert ex['exit']==0 and not ex['timeout']; assert all(not identity(proc[k])['alive'] for k in ['wrapper','executor'])
assert m['status']=='PASS_SCOPED_B5';assert all(x['status']=='PASS' for x in m['checks']);assert r['decision']=='PASS_PREPARATION_REQUIRES_ROOT_RELEASE' and r['release_enabled'] is False
assert hashlib.sha256((P/'file-manifest-v1.json').read_bytes()).hexdigest()==(P/'file-manifest-v1.sha256').read_text().split()[0]
verified=[]
for v in m['files']+m['verified_input_files']:
 verify(v);verified.append(v)
for k in ['accounting','audit_plan','controller_semantics','deployment','engineering_manifest','native_build','runtime','runtime_closure','scientific_equivalence','scope']:verify(r[k])
assert r['source']['commit']==auth['source']['commit']
wt=auth['source']['worktree'];head=subprocess.check_output(['git','-C',wt,'rev-parse','HEAD'],text=True).strip();assert head==auth['source']['commit'];assert not subprocess.check_output(['git','-C',wt,'status','--porcelain','--untracked-files=no'],text=True).strip()
for v in prev['ledger_prefixes'].values():verify(v)
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); stops=[dict(path=p,present=os.path.lexists(p)) for p in auth['stop_authority']['paths']]
next_step='B5 exact disabled graph independently reviewed and scoped root acceptance recorded in turn001755. Next perform current full-ledger accounting and exact disabled graph adoption under standing authority; fund and record a finite preparation release preserving charges, unknown telemetry and reserves. Then obtain fresh measured readiness/external acceptance before separate health and episode releases. Do not rerun B5 or recursively rebuild provenance; no GPU dispatch currently released.'
terminal=put(T/'terminal-reconciliation-v1.json',dict(schema='n36-b5-terminal-reconciliation-v1',at=now,review=ref(P/'review-v1.json'),file_manifest=ref(P/'file-manifest-v1.json'),exit=ref(P/'exit-v1.json'),process=ref(P/'process-v1.json'),handles={k:identity(proc[k]) for k in ['wrapper','executor']},decision='TERMINAL_PASS_SCOPED_B5',verified_artifact_count=len(verified),ledger_prefixes=prev['ledger_prefixes'],source=head,source_tracked_clean=True,live_handles=[],gpu_dispatched=False,source_edited=False))
accept=put(T/'root-b5-scoped-acceptance-v1.json',dict(schema='n36-root-b5-scoped-acceptance-v1',at=now,decision='ACCEPT_STATIC_B5_ONLY',review=ref(P/'review-v1.json'),manifest=ref(P/'file-manifest-v1.json'),graph=auth['graph'],source=auth['source'],terminal_reconciliation=terminal,checks=m['checks'],limitations=m['limitations'],pending_gates=m['gates'],root_accounting_adoption=False,release_enabled=False,gpu_authorized=False,scientific_success=False,next_action=next_step))
record=dict(prev['review']);record.update(status='TERMINAL_PASS_SCOPED_B5_ROOT_ACCEPTED',review=ref(P/'review-v1.json'),file_manifest=ref(P/'file-manifest-v1.json'),terminal_reconciliation=terminal,root_scoped_acceptance=accept,live_handles=[],wrapper=identity(proc['wrapper']),executor=identity(proc['executor']))
summary=dict(prev);summary.update(turn=1755,at=now,live_handles=dict(driver=identity(driver['driver']),coordinator=identity(driver['process'])),controller_status='Independent B5 CPU reviewer exited 0; both process identities absent. Exact graph scoped static pass accepted. No GPU controller dispatched.',review=record,completed_work=['Verified handoff/authority hashes, driver identity, STOP/deadline and owning state/checkpoint.','Reconciled reviewer exit 0 and absent wrapper/executor; verified hash-bound B5 output/input artifacts and clean engineering source.','Accepted 15 scoped static checks; preserved all four private ledgers unchanged; recorded pending accounting/readiness/health/episode gates.'],next_bounded_step=next_step,unresolved_evidence=['Current full-ledger root accounting and exact disabled graph adoption pending.','Fresh finite preparation release, measured readiness and external acceptance pending; health and episode releases remain separate.','Original validation/formal/required ablation evidence remains incomplete.'],review_exit_present=True,stop_present=any(x['present'] for x in stops),deadline_passed=datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(prev['deadline_utc'].replace('Z','+00:00')))
sr=put(T/'operational-summary-v1.json',summary)
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=read(C/'checkpoint.json');tree=read(C/'idea_tree.json')
 for d in [s,c]:d.update(n36_final_graph_b5_review=record,n36_final_graph_b5_root_acceptance=accept,next_action=next_step,latest_operational_summary=sr,last_updated_utc=now)
 tree['nodes']['15.6'].update(result='FINAL_GRAPH_B5_SCOPED_ROOT_ACCEPTED_ACCOUNTING_PENDING',insight=next_step,final_graph_b5_review=record)
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(dict(summary=sr,acceptance=accept,verified_artifacts=len(verified),checks=len(m['checks']))))
