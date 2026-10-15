import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,os,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001147').resolve();v=o/'protocol-preparation'
def ref(p):
 p=pathlib.Path(p);return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(p):return json.loads(p.read_text())
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def verify(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1147
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];f=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(f[19])==h['start_ticks']
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001146/receipt.json')['exit']==0
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source=='52a87af0bf11f95b21ce17aba456dc98944d9774'
ledger=w/'data/attempt-ledger.jsonl';assert ref(ledger)['sha256']=='aff9bf3e50b5d82b06cbb54f067746e3eeb6c27e499235519b903f42957ac368'
handoff=read(a/'handoff-v2.json')
for k in ['required_continuation_context','completion_contract','authorization']:verify(handoff[k])
review=read(a/'turns/001140/root-feasibility-review-v1.json')
for k in ['data','script']:verify(review[k])
for r in review['source_evidence']:verify(r)
v.mkdir(exist_ok=False)
auth={'schema':'n36-protocol-preparation-authority-v1','at':now.isoformat(),'source':source,'node_id':'15.6','user_authority':handoff['authorization'],'ideation':ref(a/'turns/001139/n36-ideation-v1.json'),'feasibility':ref(a/'turns/001140/root-feasibility-review-v1.json'),'selection_acceptance':ref(a/'turns/001146/selection-root-acceptance-v1.json'),'prior_protocol':ref(a/'turns/000884/n35-prospective-protocol-v2.json'),'prior_accounting':ref(a/'turns/000884/prospective-accounting-v2.json'),'current_accounting':ref(a/'turns/001134/accounting-normalization-v1.json'),'completion_contract':handoff['completion_contract'],'ledger_prefix':dict(ref(ledger),bytes=ledger.stat().st_size),'scope':'Draft prospective N36 Dev protocol and finite accounting only; independent review required before implementation and separate release required before GPU','gpu_authorized':False,'source_edits_authorized':False,'output_directory':str(v),'wall_cap_seconds':1800}
for key in ['ideation','feasibility','selection_acceptance','prior_protocol','prior_accounting','current_accounting','completion_contract']:verify(auth[key])
write(v/'authority-v1.json',auth)
prompt=f'''You are the CPU protocol-drafting executor for explicitly authorized continuing Arbor node15.6 N36. You are not a coordinator or implementation agent. Read/hash-verify {v/'authority-v1.json'} and its direct references. Draft a complete prospective N36 Dev science/lifecycle/native-audit protocol and finite accounting proposal, ready for independent review. Write protocol-v1.json, protocol-v1.md, prospective-accounting-v1.json and report-v1.json under {v} ONLY. Do not adopt anything or implement source. Use exact registered N36 ideation and accepted feasibility caveats; do not invent a replacement hypothesis or silently alter thresholds. Frozen base source {source}.

Read current state budget/snapshot read-only and prior N35 protocol for unchanged scientific gates, sample identities/splits, control semantics, halt rules and stage condition. Choose and justify fresh matched controls for isolating the N36 path change (N34 base with N35 closure memory disabled); specify whether C0/Q0/N34/N36 are required and exact primary order/denominators. No recycled historical controls or pooled mismatched rounds. Preserve original validation20 >=10 and >=C0/Q0, formal historical10 >=5 and >=C0/Q0, required ablations, and original Dev promotion thresholds. Do not read protected validation/formal outcomes. Explicitly distinguish gate inheritance from proposal choices needing independent review.

Specify independent nonprogress memory lifecycle from full CONTINUITY fields: preceding full8 acknowledged selected observed-open-approach, adjacent decision and same episode/Stage/target/tracker identity, finite nonzero p, observed d with dot(p,d)<=0, consume-once and invalid/unguided/terminal/reset cases. Define whether trigger eligibility persists across inner QD updates within the one adjacent decision, and justify against registered lifecycle; CPU evidence only tested first insertion. Specify deterministic tangent path, axis ties, native encode/decode arithmetic, clipping, unchanged close geometry and direct-close branch, remainder preservation, insertion slot and no forced selection. Treat approximate collision/endpoint claims as unproven. Require actual deployed native candidate/provider score/descriptor/archive/final selection/decode/commit/exact8 ack/physical-response linkage, negative-control coverage, native-byte audits, occurrence ambiguity handling and no weakened audits. Later archive competition cannot be replayed with fixed offspring; require prospective evidence. Propose useful mechanism falsification criteria without weakening unchanged scientific promotion gates or adding success claims.

Prepare exact prospective maximum attempts, bucket arithmetic and conservative GPU-hour cap (including preflight/healthcheck reservation), single idle locally assigned GPU7 only, zero automatic retries, reserved validation/formal hours preserved, retained502 attempts and75.24379311215873 GPUh (healthchecks retained as recorded), cumulative1800/224 bounds. Current authorization deadline2026-10-11T11:13:13Z; STOP/deadline no new dispatch and active cohort drains safely. Historical N31 October10 deadline unchanged; this new cohort needs explicit separately recorded prospective window adoption. No budget increase or reservation is actually adopted in this task. Distinguish wall-time feasibility from GPU accounting. Any open implementation/native-release obligations must be explicit blockers, not fabricated PASS flags.

Only named source paths/direct dependencies as needed, no broad historical reread or new tensor replay. No GPU, simulators, provider probes, source/state/tree/ledger edits, commits, worktrees, credentials/Poe/alternate accounts/API keys, external messages or further delegation. Never open prohibited2026-08-10-eds-qd-stage-guidance-transition-design.md or protected results. Superpowers disabled. Use only current official-login gpt-6-astra. Documentation task: no unnecessary tests. Preserve all costs/failures/unknowns. Finish within1800sec with concrete drafted artifacts, hashes, unresolved questions and independent-review requirements. CPU protocol work is not promotion or original-goal completion.'''
(v/'executor-prompt-v1.txt').write_text(prompt)
old=a/'turns/000910/n35-audit-repair-review/executor-launch-v1.py'
wrapper=old.read_text().replace(str(w.parent/'variants/n35_closure_intent/implementation_worktree'),str(w)).replace('n35-audit-repair-review-executor-process-v1','n36-protocol-preparation-executor-process-v1')
assert str(w) in wrapper
(v/'executor-launch-v1.py').write_text(wrapper)
sys.path.insert(0,str(w));from scripts import qd_ed_final_runner as runner
with runner.locked(w/'data/qd-ed-state.lock'):
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=yaml.safe_load(sp.read_text());c=read(cp);t=read(tp)
 assert s['active_controller'] is None and c['active_controller'] is None and not s.get('current_owned_workers') and not s.get('in_flight_executor')
 for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.before-review'))
 with open(v/'wrapper.log','ab') as log:proc=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=w,stdout=log,stderr=log,start_new_session=True)
 write(v/'wrapper-launch-v1.json',{'pid':proc.pid,'at':now.isoformat(),'launcher':ref(v/'executor-launch-v1.py')})
 for _ in range(50):
  if (v/'executor-process-v1.json').exists():break
  time.sleep(.1)
 assert (v/'executor-process-v1.json').exists(),f'Reconcile wrapper {proc.pid}; do not retry'
 pr=read(v/'executor-process-v1.json');rec={'status':'CPU_PROTOCOL_PREPARATION_RUNNING','node_id':'15.6','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:pr[k] for k in ['wrapper','executor']},'worktree':str(w),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False}
 next_step='Monitor exact N36 protocol-drafting executor handles and report. Independently review completed protocol/accounting before isolated implementation; no source adoption, GPU release or protected access from documentation. Preserve scientific gates and all costs.'
 for obj in [s,c]:obj.update(n36_protocol_preparation=rec,in_flight_executor=rec,phase='N36_CPU_PROTOCOL_PREPARATION_RUNNING',next_action=next_step,updated_at=now.isoformat())
 c['inflight_executor']=rec
 t['nodes']['15.6'].update(status='running',result='CPU_PROTOCOL_PREPARATION_RUNNING_NO_GPU',protocol_preparation=rec)
 tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c);write(tp,t)
 summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'driver':ds['driver'],'coordinator':ds['process'],'active_controller':None,'current_owned_workers':[],'prior_turn':'001146 completed exit0; accepted selection review and unchanged owning ledger reconciled; no recovery required','stop_present':False,'deadline':'2026-10-11T11:13:13Z','ledger':dict(ref(ledger),bytes=ledger.stat().st_size),'completed':'Verified live driver/coordinator identity, terminal N35/reviewer handles absent, unchanged ledger and prior exit0; launched official current-login gpt-6-astra CPU prospective protocol drafting executor','executor':rec,'next_action':next_step,'unresolved':['Independent prospective protocol/accounting review','Reviewed implementation and native audits','Fresh original-goal validation/formal/required ablation evidence'],'new_gpu_dispatches':0,'target_met':False,'scientific_source_changes':False}
 write(o/'operational-summary.json',summary)
 (o/'operational-summary.md').write_text(f"Turn001147: N36 prospective protocol drafting dispatched. Source {source} unchanged. Driver/coordinator identities verified; prior turn001146 exit0. N35 controller and selection-review handles absent; no GPU worker. Ledger prefix7513934 bytes aff9bf3e50b5d82b06cbb54f067746e3eeb6c27e499235519b903f42957ac368 unchanged;502 attempts and75.24379311215873 GPUh retained. STOP absent; deadline2026-10-11T11:13:13Z.\n\nLive CPU handles: {rec['handles']}.\n\nCompleted: bound handoff/authority and recent continuity reconciled; bounded protocol/accounting drafting authorized and dispatched through established official-login CLI wrapper. No source, budget, GPU or scientific-gate changes.\n\nNext: {next_step}\n\nUnresolved: prospective independent review, implementation/native audits, fresh matched outcomes and validation/formal/required ablation evidence. Goal not met.\n")

print(json.dumps(rec))
