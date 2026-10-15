import pathlib,json,hashlib,datetime,subprocess,os,fcntl,time,yaml
owner=pathlib.Path.cwd(); turns=(owner/'../autonomy_20261004/turns').resolve(); out=turns/'001555/graph-rebinding';prior=turns/'001552/graph-rebinding'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert now<'2026-10-11T11:13:13' and not (turns.parent/'STOP').exists()
def ref(p):
 p=pathlib.Path(p).resolve();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return ref(p)
s=json.loads((turns/'001554/operational-summary-v1.json').read_text())
for r in s['ledgers'].values():assert ref(r['path'])['sha256']==r['sha256'] and pathlib.Path(r['path']).stat().st_size==r['bytes']
for pid in [2226929,2226930]:assert not pathlib.Path(f'/proc/{pid}').exists()
a=json.loads((prior/'authority-v1.json').read_text());W=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
assert subprocess.check_output(['git','-C',str(W),'rev-parse','HEAD'],text=True).strip()==a['source']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==s['owner_source']
out.mkdir(exist_ok=False)
a.update(at=now,corrected_controller_proof=ref(turns/'001554/controller-semantics.root-reviewed-v2.json'),schema_repair_review=ref(turns/'001554/terminal-and-proof-schema-review-v1.json'),prior_rebinding_report=ref(prior/'report-v1.json'),scope='CPU artifacts only: rebind existing disabled graph to canonical corrected proof, exact passive verification. No source/runtime/science/accounting changes; no GPU; no B5 claim.')
aref=write(out/'authority-v1.json',a)
prompt=(prior/'prompt.txt').read_text().replace(str(prior),str(out)).replace('/turns/001552/graph-rebinding', '/turns/001555/graph-rebinding').replace('turn001551 controller-semantics.root-reviewed-v1.json','turn001554 controller-semantics.root-reviewed-v2.json')
prompt+='\nContinuation: prior graph and reusable helper are at '+str(prior)+'. Prior executor exited 0 with sole controller reference-schema blocker, corrected in '+str(turns/'001554')+'. Consume corrected proof exactly (sha256 '+a['corrected_controller_proof']['sha256']+'). Reuse bounded helper, writing NEW output paths; do not rebuild accepted provenance or overwrite prior artifacts. Read report fields selectively. Check exact candidate passive controller/plan/audit and manifests. Produce final report and independent-b5-inputs, distinguishing actual PASS from disabled-release G7 veto. Do not recursively launch agents.\n'
(out/'prompt.txt').write_text(prompt);(out/'run-executor.py').write_text((prior/'run-executor.py').read_text())
with (out/'wrapper.log').open('xb') as log:
 p=subprocess.Popen(['/usr/bin/python3',str(out/'run-executor.py')],cwd=W,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
write(out/'wrapper-launch-v1.json',dict(pid=p.pid,at=now,authority=aref))
for _ in range(50):
 if (out/'process-v1.json').exists():break
 time.sleep(.1)
handles=json.loads((out/'process-v1.json').read_text())
record=dict(status='CPU_CORRECTED_PROOF_GRAPH_REBINDING_RUNNING',source=a['source'],worktree=str(W),authority=aref,output_directory=str(out),process_record_path=str(out/'process-v1.json'),exit_path=str(out/'exit-v1.json'),wrapper=handles['wrapper'],executor=handles['executor'],gpu_authorized=False,source_edits_authorized=False,release_enabled=False)
next_step='Monitor recorded turn001555 CPU executor by boot/start identity; reconcile report/exit and unchanged ledger prefixes. On exact graph PASS obtain independent B5. G7 dispatch veto/readiness unresolved; no GPU release.'
coord=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
with (coord/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,isyaml in [(owner/'research-state.yaml',True),(coord/'checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if isyaml else json.loads(path.read_text());d['n36_engineering_corrected_graph_rebinding']=record;d['active_executor']=record;d['next_action']=next_step
  tmp=path.with_suffix(path.suffix+'.tmp-001555');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');tmp.replace(path)
 path=coord/'idea_tree.json';d=json.loads(path.read_text());d['nodes']['15.6'].update(result='CPU_CORRECTED_PROOF_GRAPH_REBINDING_RUNNING_NO_GPU',insight='Canonical controller reference proof passed unchanged verifier; bounded graph refresh in progress. Independent B5, dispatch implementation and native readiness remain unresolved.');tmp=path.with_suffix('.tmp-001555');tmp.write_text(json.dumps(d,indent=2)+'\n');tmp.replace(path)
s.update(at=now,turn=1555,next_bounded_step=next_step,completed_work='Verified bound authority, live driver/coordinator and prior normal executor termination; all three ledger prefixes unchanged. Launched one official current-login gpt-6-astra CPU artifact executor to rebind canonical corrected proof.',STOP_present=False,target_met=False,active_executor=record)
s['live_handles']=[]
for role,pid in [('driver',268073),('coordinator',2238739),('wrapper',handles['wrapper']['pid']),('executor',handles['executor']['pid'])]:
 st=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();s['live_handles'].append(dict(role=role,pid=pid,start_ticks=int(st[19]),state=st[0],boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()))
s['executor_observation']={'status':'RUNNING','release_enabled':False}
r=write(turns/'001555/operational-summary-v1.json',s);(turns/'001555/operational-summary-v1.sha256').write_text(r['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(dict(summary=r,active_executor=record),indent=2))
