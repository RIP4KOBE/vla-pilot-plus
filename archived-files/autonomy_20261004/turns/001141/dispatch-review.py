import pathlib,json,hashlib,datetime,subprocess,sys,time,shutil,os,yaml
w=pathlib.Path.cwd();a=w.parent/'autonomy_20261004';o=(a/'turns/001141').resolve();v=o/'selection-review'
def ref(p):
 p=pathlib.Path(p);return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(p):return json.loads(p.read_text())
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def verify(r):assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
now=datetime.datetime.now(datetime.timezone.utc);ds=read(a/'driver-status.json');assert ds['turn']==1141
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=ds[k];f=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(f[19])==h['start_ticks']
assert not (a/'STOP').exists() and now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert read(a/'turns/001140/receipt.json')['exit']==0
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source=='52a87af0bf11f95b21ce17aba456dc98944d9774'
ledger=w/'data/attempt-ledger.jsonl';assert ref(ledger)['sha256']=='aff9bf3e50b5d82b06cbb54f067746e3eeb6c27e499235519b903f42957ac368'
handoff=read(a/'handoff-v2.json')
for k in ['required_continuation_context','completion_contract','authorization']:verify(handoff[k])
review=read(a/'turns/001140/root-feasibility-review-v1.json')
for k in ['data','script']:verify(review[k])
for r in review['source_evidence']:verify(r)
v.mkdir(exist_ok=False)
auth={'schema':'n36-independent-selection-review-authority-v1','at':now.isoformat(),'source':source,'node_id':'15.6','user_authority':handoff['authorization'],'root_feasibility_review':ref(a/'turns/001140/root-feasibility-review-v1.json'),'ideation':ref(a/'turns/001139/n36-ideation-v1.json'),'ledger_prefix':dict(ref(ledger),bytes=ledger.stat().st_size),'scope':'CPU-only independent selection feasibility review; six bound eligible Dev next-decision packets; no source/state/ledger edits or GPU','gpu_authorized':False,'source_edits_authorized':False,'output_directory':str(v),'host_delegation_failure':'collaboration.spawn_agent failed: no thread with id 01a12295-04ec-7871-a1a1-84855d636b9d; no child started','wall_cap_seconds':1800}
write(v/'authority-v1.json',auth)
prompt=f'''You are an independent CPU scientific feasibility reviewer for continuing explicitly authorized Arbor node 15.6 (N36), not a coordinator. Read and hash-verify {v/'authority-v1.json'} and direct references. Review registered N36 detour ordinary-selection plausibility using ONLY the six already-bound eligible Dev next-decision packets from turn001140 feasibility-data-v1.json / feasibility.py and their turn001137 action-link-v1.json bindings. Frozen owning source {source}. Actual provider/projection semantics, native dtype and clipping matter. Compare the exact registered detour against matched direct-approach and template scores using the existing frozen reward provider/projection implementation where replay inputs permit. Inspect scoring and archive tie/selection semantics; distinguish scores from actual prospective archive survival. If exact scoring cannot be reconstructed from bounded packets, state missing evidence precisely rather than fabricate a score or change quality. Do not repeat trigger/encoding or broad N35 diagnosis. Assess whether this proposal has credible ordinary-selection feasibility; report PASS, BLOCKED, or REJECT with concrete evidence and limitations. CPU replay is not task success or scientific promotion.

Write report-v1.json and report-v1.md under {v}, plus any bounded CPU analysis scripts/results there only. Include source/inputs/script hashes, exact comparisons and audit limitations; preserve errors. Read actual source dependencies as needed, named paths only; do not recursively search historical artifacts/data/results. CPU tests only if they resolve a specific concern, CUDA_VISIBLE_DEVICES empty and bounded threads. No source edits, commits, worktree creation, adoption, state/ledger/tree mutation, resource reservations, GPU, simulator episodes, protected validation/formal access, external messages or further delegation. Never read 2026-08-10-eds-qd-stage-guidance-transition-design.md. No credentials/Poe, alternate providers/accounts/API keys; use only this official current-login gpt-6-astra session. Superpowers disabled. Prior root review is not independent; your review must independently inspect semantics. No forced selection, changed capture geometry, tuning thresholds or revised hypothesis. N35 is terminal; no active cohort. Finish bounded review within1800 seconds; useful partial report if evidence insufficient. PASS does not authorize GPU or implementation adoption.
'''
(v/'executor-prompt-v1.txt').write_text(prompt)
old=a/'turns/000910/n35-audit-repair-review/executor-launch-v1.py'
wrapper=old.read_text().replace(str(w.parent/'variants/n35_closure_intent/implementation_worktree'),str(w)).replace('n35-audit-repair-review-executor-process-v1','n36-selection-review-executor-process-v1')
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
 pr=read(v/'executor-process-v1.json');rec={'status':'CPU_SELECTION_REVIEW_RUNNING','node_id':'15.6','authority':ref(v/'authority-v1.json'),'process_record':ref(v/'executor-process-v1.json'),'handles':{k:pr[k] for k in ['wrapper','executor']},'worktree':str(w),'output_directory':str(v),'gpu_authorized':False,'source_edits_authorized':False}
 next_step='Monitor exact N36 independent CPU selection reviewer handles and exit/report; no duplicate review. Reconcile bounded provider/projection comparisons before protocol or implementation. No GPU release or protected access; retain frozen source/scientific gates.'
 for obj in [s,c]:obj.update(n36_selection_review=rec,in_flight_executor=rec,phase='N36_CPU_SELECTION_REVIEW_RUNNING',next_action=next_step,updated_at=now.isoformat())
 c['inflight_executor']=rec
 t['nodes']['15.6'].update(status='running',result='CPU_SELECTION_REVIEW_RUNNING_NO_GPU',selection_review=rec)
 tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c);write(tp,t)
 summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'driver':ds['driver'],'coordinator':ds['process'],'active_controller':None,'current_owned_workers':[],'prior_turn':'001140 completed exit0; six-window CPU feasibility records hash verified; no abnormal recovery required','stop_present':False,'deadline':'2026-10-11T11:13:13Z','ledger':dict(ref(ledger),bytes=ledger.stat().st_size),'completed':'Reconciled terminal controller, prior turn and owning ledger; launched independent official current-login gpt-6-astra CPU selection review after host subagent failure','executor':rec,'next_action':next_step,'unresolved':['Ordinary-selection plausibility','Prospective protocol, implementation and native audits','Original validation/formal/required ablation evidence'],'new_gpu_dispatches':0,'target_met':False,'scientific_source_changes':False}
 write(o/'operational-summary.json',summary)
 (o/'operational-summary.md').write_text(f'Turn001141: N36 independent CPU selection review launched.\n\nSource {source} unchanged. Driver {ds["driver"]}; coordinator {ds["process"]}. GPU controller2632351 absent and terminal status reconciled; no owned GPU worker. Prior turn001140 exit0. STOP absent; deadline2026-10-11T11:13:13Z. Ledger7513934 bytes / aff9bf3e50b5d82b06cbb54f067746e3eeb6c27e499235519b903f42957ac368 unchanged;502 dispatches and75.24379311215873 GPUh retained.\n\nReview handles: {rec["handles"]}. Official current-login gpt-6-astra CLI, CPU-only; output {v}. Built-in child launch failed without side effects, so established CLI wrapper used. No GPU/source changes or scientific promotion.\n\nNext: {next_step}\n\nUnresolved: selection plausibility, prospective protocol/implementation/native audits, original validation/formal/ablations. Goal not met.\n')
print(json.dumps(rec))
