from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,time,yaml
owner=Path.cwd();A=(owner.parent/'autonomy_20261004').resolve();T=A/'turns/001560';W=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
 return ref(p)
def ident(pid):
 s=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
def verify(r):
 x=ref(r['path']);assert x['sha256']==r['sha256'],r['path']
 if 'bytes' in r:assert x['bytes']==r['bytes']
assert now<'2026-10-11T11:13:13' and not (A/'STOP').exists()
handoff=json.loads((A/'handoff-v2.json').read_text())
for key in ['authorization','required_continuation_context','completion_contract']:verify(handoff[key])
driver=json.loads((A/'driver-status.json').read_text());assert driver['turn']==1560
for k in ['driver','process']:
 live=ident(driver[k]['pid']);assert all(live[z]==driver[k][z] for z in ['pid','boot_id','start_ticks'])
s=json.loads((A/'turns/001559/operational-summary-v1.json').read_text());receipt=json.loads((A/'turns/001559/receipt.json').read_text());assert receipt['exit']==0 and receipt['status']=='completed_turn'
for h in ['wrapper','executor']:assert not Path('/proc/'+str(s['active_executor'][h]['pid'])).exists()
for r in s['ledgers'].values():verify(r)
state=yaml.safe_load((owner/'research-state.yaml').read_text());assert not state['current_owned_workers'];assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==s['owner_source']
assert subprocess.check_output(['git','-C',str(W),'rev-parse','HEAD'],text=True).strip()==s['candidate_source']
assert not subprocess.check_output(['git','-C',str(W),'status','--porcelain','-uno'],text=True).strip()
O=T/'g7-implementation';O.mkdir()
a=dict(schema='n36-g7-cpu-implementation-authority-v1',at=now,node_id='15.6',source=s['candidate_source'],worktree=str(W),standing_authority=ref(A/'user-authorization-v1.json'),root_review=ref(A/'turns/001559/terminal-review-v1.json'),prior_review=ref(A/'turns/001556/independent-b5/report-v1.json'),ledger_prefixes=s['ledgers'],timeout_seconds=1200,deadline='2026-10-11T11:13:13Z',gpu_authorized=False,source_edits_authorized=True,release_enabled=False,scope='Implement and CPU-test missing G7 released lifecycle/deep-closure dispatch path in existing isolated executor branch only. No scientific changes or owner adoption; prior graph review applies only to prior source.')
aref=put(O/'authority-v1.json',a)
prompt=f'''You are the single CPU implementation executor for G7, continuing explicitly authorized Arbor node 15.6. Read {O/'authority-v1.json'} and its hash-bound recent root/B5 review. Work only in isolated {W}; artifacts in {O}. Starting source {s['candidate_source']}. Complete missing released-lifecycle/deep-closure checks needed for a correct bounded engineering health+one-episode dispatch path, then replace the unconditional require_dispatch_implementation veto only if the actual implementation is complete and fail-closed. This instruction authorizes source edits and a scoped commit in this isolated branch; it authorizes no actual release, adoption, GPU/model/provider execution, dependency changes, owner state/checkpoint/tree/journal writes, or protected result access. Do not recursively delegate.
Inspect scripts/qd_ed_n36_engineering.py, associated runner/source-runtime verification and existing focused tests. The prior independent B5 report identifies remaining gaps. Preserve actual source/runtime/native attestation, detached exact authority and release bindings, state adoption, canonical STOP/deadline, private accounting/protected reserves, sole health/episode identities, same-process receipts, one GPU worker, invalidity stop and append-only accounting. Removing the veto or substituting a boolean/record is insufficient: trace executable call graph end-to-end and exercise released lifecycle, deep closure, and negative boundaries using CPU synthetic fixtures. No weakened hashes, audit predicates, budget or scientific thresholds. Engineering diagnostic is separate from science; preserve complete10 and N36>=5 and >=C0/Q0/N34, final required ablations, validation/formal promotion and unchanged original-goal contract. No source/plan scientific changes. No retrospective reclassification or replay.
Read only targeted existing accepted evidence; avoid rebuilding old provenance or broad test repeats. Preserve existing frozen/disabled graph and reviews as history. Do not refresh the entire artifact graph now; report exact affected bindings requiring follow-up refresh/review. Prior B5 is not valid approval of your new source. Use meaningful focused CPU tests, no native/model/GPU execution, no environment installation. Follow project instructions, Superpowers disabled, no credentials opened, no prohibited 2026-08-10-eds-qd-stage-guidance-transition-design.md or protected validation/formal results. Official current-login gpt-6-astra only. Observe STOP/deadline before work and finish within1200 seconds.
Commit only your intended source and test edits; preserve untracked/dependency artifacts. Write report-v1.json with starting/final commit, exact changed paths, test commands/results/evidence hashes, lifecycle coverage and negative checks, unresolved blockers, next minimal graph refresh/review obligations, score:null, scientific_success:false, target_met:false, release_enabled:false, unchanged ledger checks. If full safe implementation is not feasible, leave dispatch fail-closed and report concrete remaining gaps with useful partial code. Do not claim scientific completion from CPU checks. Coordinator owns all adoption/release decisions.
'''
(O/'prompt.txt').write_text(prompt);(O/'run-executor.py').write_text((A/'turns/001556/independent-b5/run-executor.py').read_text())
with (O/'wrapper.log').open('xb') as log:p=subprocess.Popen(['/usr/bin/python3',str(O/'run-executor.py')],cwd=W,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',dict(at=now,pid=p.pid,authority=aref))
for _ in range(50):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
h=json.loads((O/'process-v1.json').read_text());record=dict(status='CPU_G7_IMPLEMENTATION_RUNNING',source=s['candidate_source'],worktree=str(W),authority=aref,output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=h['wrapper'],executor=h['executor'],gpu_authorized=False,source_edits_authorized=True,release_enabled=False)
nextstep='Monitor turn001560 G7 executor by boot/start identity. Reconcile side effects and focused CPU tests after exit, then independent source review and only affected proof/graph/B5 refresh before any owner adoption or bounded diagnostic release. Actual readiness, scientific promotion and original-goal evidence remain unproven.'
C=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,isyaml in [(owner/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if isyaml else json.loads(path.read_text());d['n36_engineering_g7_implementation']=record;d['active_executor']=record;d['next_action']=nextstep;d['updated_at']=now
  tmp=path.with_suffix(path.suffix+'.tmp-001560');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');tmp.replace(path)
 path=C/'idea_tree.json';d=json.loads(path.read_text());d['nodes']['15.6'].update(result='CPU_G7_IMPLEMENTATION_RUNNING_NO_GPU',insight='Existing disabled graph B5 accepted only for previous source. One isolated executor implementing missing dispatch lifecycle; source review and affected binding refresh required before release.',g7_implementation=record);tmp=path.with_suffix('.tmp-001560');tmp.write_text(json.dumps(d,indent=2)+'\n');tmp.replace(path)
s.update(at=now,turn=1560,next_bounded_step=nextstep,completed_work='Verified bound handoff/authority/contract, normal prior turn exit, driver boot/start identity, no owned running attempts, and unchanged private ledgers. Launched one official gpt-6-astra CPU-only G7 implementation executor in existing isolated variant worktree; owner scientific source unchanged.',STOP_present=False,target_met=False,active_executor=record,executor_observation=dict(status='RUNNING',release_enabled=False))
s['live_handles']=[dict(role=role,**ident(pid)) for role,pid in [('driver',driver['driver']['pid']),('coordinator',driver['process']['pid']),('wrapper',h['wrapper']['pid']),('executor',h['executor']['pid'])]]
for r in s['ledgers'].values():verify(r)
sr=put(T/'operational-summary-v1.json',s);(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n');print(json.dumps(dict(summary=sr,handles=s['live_handles'],release_enabled=False)))
