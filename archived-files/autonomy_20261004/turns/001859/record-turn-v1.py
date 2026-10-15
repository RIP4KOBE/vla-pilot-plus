import ast,json,pathlib,hashlib,math,datetime,fcntl,os,yaml
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001859';job=out/'successor-disabled-composition'
prev=json.loads((base/'turns/001858/operational-summary-v1.json').read_text())
def ref(p):
 p=P(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(n,v):
 p=out/n
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
 return ref(p)
for r in prev['ledger_prefixes'].values():assert ref(r['path'])==r
boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def live(h):
 p=P('/proc')/str(h['pid'])/'stat'
 if not p.exists():return dict(h,alive=False,identity_verified=False,state='absent')
 s=p.read_text().rsplit(')',1)[1].split();ok=boot==h['boot_id'] and int(s[19])==int(h['start_ticks']);return dict(h,state=s[0],alive=ok and s[0]!='Z',identity_verified=ok)
driver=json.loads((base/'driver-status.json').read_text());handles={k:live(driver[k]) for k in ['driver','process']};assert all(h['alive'] for h in handles.values())
process=json.loads((job/'process-v1.json').read_text());jobs={k:live(process[k]) for k in ['wrapper','executor']}
for pid in [203562,203563,3918335,3931995,3931997,3853486,3853487,3859839]:assert not P(f'/proc/{pid}').exists()
source=P(prev['current_source']['worktree'])/'scripts/qd_ed_final_runner.py';tree=ast.parse(source.read_bytes());names={'require','event_groups','budget_snapshot'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'BUCKETS','TERMINAL'} for t in n.targets)]
ns={'math':math};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
led=prev['ledger_prefixes'];rows=lambda name:[json.loads(l) for l in P(led[name]['path']).read_bytes().splitlines()]
snap=ns['budget_snapshot'](rows('attempt-ledger.jsonl'),rows('gpu-healthcheck-ledger.jsonl'));assert snap['running']==snap['gpu_healthcheck_inflight']==0
proposal=json.loads((base/'turns/001858/prospective-fresh-measurement-plan-v1.json').read_text());assert abs(snap['gpu_hours_consumed']-float(proposal['arithmetic']['reconstructed_current_gpu_hours']))<1e-10
accounting=put('production-accounting-check-v1.json',dict(status='PASS_CURRENT_FULL_LEDGER_SNAPSHOT',source=ref(source),method='Unmodified production AST require/event_groups/budget_snapshot, complete private attempt and global health ledgers; mirrored readiness not double counted.',snapshot=snap,ledger_prefixes=led,proposal=ref(base/'turns/001858/prospective-fresh-measurement-plan-v1.json'),dispatch_admission=False))
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00') and not (base/'STOP').exists()
record=dict(status='RUNNING_CPU_ONLY_SUCCESSOR_DISABLED_COMPOSITION',at=now.isoformat(),source=prev['current_source']['commit'],worktree=prev['current_source']['worktree'],authority=ref(job/'authority-v1.json'),output_directory=str(job),process_record_path=str(job/'process-v1.json'),exit_path=str(job/'exit-v1.json'),**jobs,gpu_authorized=False,measurement_authorized=False,source_edits_authorized=False,production_accounting_check=accounting)
next_action='Monitor existing CPU successor composition wrapper3974527/executor3974543 by recorded boot/start identity; do not duplicate. On terminal inspect successor-disabled-composition/report-v1.json and exact changed references. Reconcile four retained predecessor sequences and root review before disabled graph admission; production full-ledger snapshot verified in turn001859. No GPU/measurement authorized yet. Preserve source808e27f, current freshness semantics, independent B5 and all scientific gates. Fresh release may end only at 2026-10-11T11:13:13Z; STOP/deadline forbids new dispatch. Validation/formal/required ablation completion remains unresolved.'
summary=dict(schema='autonomy-operational-summary-v1',at=now.isoformat(),turn=1859,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,cpu_operation_handles=list(jobs.values()),controller_status='BLOCKED_PRODUCTION_AUDIT_CPU_SUCCESSOR_PREPARATION_RUNNING',ledger_prefixes=led,ledgers_unchanged=True,completed_work=['Verified bound handoff/authority/completion contract, driver live identities, prior terminal handles and unchanged four private ledgers.','Verified original production full-ledger snapshot: 507 dispatches, no inflight resource, retained charges including four readiness predecessors counted once.','Launched bounded official current-login gpt-6-astra CPU artifact executor for fresh successor disabled graph; no source edits, GPU or provider measurement authority.'],production_accounting_check=accounting,executor=record,next_bounded_step=next_action,unresolved_evidence=prev['unresolved_evidence'],target_met=False,stop_present=False,deadline='2026-10-11T11:13:13Z')
sr=put('operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text());d['n36_fresh_successor_disabled_composition']=record;d['active_executor']=record;d['next_action']=next_action;d['latest_operational_summary']=sr;d['updated_at']=now.isoformat();tmp=p.with_name(p.name+'.001859.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if is_yaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
for r in led.values():assert ref(r['path'])==r
print(json.dumps(dict(summary=sr,handles=jobs,snapshot=snap)))
