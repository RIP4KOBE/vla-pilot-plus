import pathlib as pl,json,hashlib,datetime,subprocess,fcntl,os,yaml,time
P=pl.Path; owner=P.cwd(); turns=owner.parent/'autonomy_20261004/turns'; out=turns/'001552/graph-rebinding';out.mkdir(exist_ok=False)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):
 p=P(p); b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2);f.write('\n')
 return ref(p)
def ident(pid):
 a=P(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=P('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(a[19]),state=a[0])
assert not (turns.parent/'STOP').exists()
assert now<'2026-10-11T11:13:13+00:00'
prior=json.loads((turns/'001551/operational-summary-v1.json').read_text())
for r in prior['ledgers'].values(): assert ref(r['path'])==r
au=dict(schema='n36-disabled-graph-rebinding-authority-v1',at=now,node_id='15.6',source=prior['candidate_source'],standing_authority=ref(turns.parent/'user-authorization-v1.json'),controller_review=ref(turns/'001551/controller-root-review-v1.json'),accepted_g5_review=ref(turns/'001547/terminal-review-v1.json'),g6_reconciliation=ref(turns/'001550/terminal-review-v1.json'),ledger_prefixes=prior['ledgers'],gpu_authorized=False,source_edits_authorized=False,release_enabled=False,timeout_seconds=1200,scope='Write new disabled graph artifacts under this output directory only. Rebind controller proof transitively; preserve source/runtime/40 scientific rows/gates/accounting. No independent B5 claim or GPU dispatch.')
ar=put(out/'authority-v1.json',au)
prompt=f'''Continue explicit Arbor node 15.6 as bounded CPU artifact executor. Read {out}/authority-v1.json and its referenced accepted records. Candidate immutable worktree /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree at dcd890474b733743414d2a7711069bb0d2b0337e. Rebind disabled G5 plan/audit and ALL necessary transitive manifest references to turn001551 controller-semantics.root-reviewed-v1.json. Write new artifacts only under {out}; retain all old files. Use existing G5 preparation helper and G6 actual checks as guidance, bounded exact candidate passive verifier definitions; avoid rebuilding accepted G2/G3/G4/native provenance and broad tests. Produce report-v1.json with precise input/output hashes, checks, exact refreshed plan/graph roots and unresolved gates, plus independent-b5-inputs-v1.json. Keep b5_review null, release_enabled false, no authority grant/source adoption. Preserve science rows, thresholds, accounting, runtime bytes, unconditional source dispatch veto. No owner state/checkpoint/tree/ledger writes. No source edits, native/model/provider imports or execution, GPU dispatch, subprocess agents, credential reads, Superpowers, prohibited 2026-08-10-eds-qd-stage-guidance-transition-design.md, or protected validation/formal results. Only current-login official Codex gpt-6-astra. Check STOP/deadline before work; deadline 2026-10-11T11:13:13Z. 1200 seconds CPU preparation maximum. Claim only checks actually performed. If blocked write exact blocker with partial artifacts. This is preparation, not independent B5 or scientific success.'''
(out/'prompt.txt').write_text(prompt+'\n')
(out/'run-executor.py').write_text((turns/'001548/g6-verification/run-executor.py').read_text())
with (out/'wrapper.log').open('xb') as log:
 p=subprocess.Popen(['python',str(out/'run-executor.py')],cwd=owner,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
launch=put(out/'wrapper-launch-v1.json',dict(wrapper=ident(p.pid),authority=ar,at=now))
for _ in range(30):
 if (out/'process-v1.json').exists():break
 time.sleep(.1)
proc=json.loads((out/'process-v1.json').read_text())
record=dict(status='CPU_DISABLED_GRAPH_REBINDING_RUNNING',source=prior['candidate_source'],worktree='/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree',authority=ar,output_directory=str(out),process_record_path=str(out/'process-v1.json'),exit_path=str(out/'exit-v1.json'),wrapper=proc['wrapper'],executor=proc['executor'],gpu_authorized=False,source_edits_authorized=False,release_enabled=False)
next_action='Monitor turn001552 graph-rebinding executor by recorded PID/boot/start identity. Reconcile terminal artifacts then obtain independent B5 on exact disabled graph. No duplicate executor or GPU dispatch.'
lock=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/state.lock'
with lock.open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX)
 for path,isy in [(owner/'research-state.yaml',True),(lock.parent/'checkpoint.json',False)]:
  x=yaml.safe_load(path.read_text()) if isy else json.loads(path.read_text());x['n36_engineering_graph_rebinding']=record;x['active_executor']=record;x['next_action']=next_action;x['updated_at']=now
  tmp=path.with_name(path.name+'.turn1552.tmp');tmp.write_text(yaml.safe_dump(x,sort_keys=False,allow_unicode=True) if isy else json.dumps(x,indent=2)+'\n');tmp.replace(path)
summary=dict(prior);summary.update(at=now,turn=1552,completed_work='Verified bound authority, driver/coordinator identity, normal prior exit, terminal historical workers and unchanged ledger prefixes. Started one bounded official Codex CPU executor to refresh disabled graph against approved controller proof; recorded handles in owner state/checkpoint.',next_bounded_step=next_action,graph_rebinding=record)
d=json.loads((turns.parent/'driver-status.json').read_text());summary['live_handles']=[dict(role=k,**ident(d[k]['pid'])) for k in ['driver','process']]+[dict(role=k,**proc[k]) for k in ['wrapper','executor']]
for r in prior['ledgers'].values():assert ref(r['path'])==r
r=put(turns/'001552/operational-summary-v1.json',summary);(turns/'001552/operational-summary-v1.sha256').write_text(r['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(record))
