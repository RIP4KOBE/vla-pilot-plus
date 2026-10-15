import pathlib,json,hashlib,datetime,sys,shutil,subprocess,yaml
r=pathlib.Path.cwd();o=(r.parent/'autonomy_20261004/turns/000669').resolve();p=o/'runtime-v1';sys.path.insert(0,str(r))
from scripts import qd_ed_final_runner as runner
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
e=json.loads((o/'entry-reconciliation-v1.json').read_text());d=json.loads((p/'prospective-draft-v1/plan.draft.json').read_text());i=json.loads((p/'runtime-import-probe-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not i['errors'] and not i['uncovered_checkout_modules'] and not i['missing_files'] and not i['cuda_initialized']
assert len(d['expected_manifests'])==30 and d['release_enabled'] is False and d['source']['commit']==e['source']
assert (p/'runtime-post-prepare-receipt-v1.json').exists()
ledger=(r/'data/attempt-ledger.jsonl').read_text();assert all(k not in ledger for k in d['expected_manifests'])
for n,v in e['ledger_prefixes'].items():
 b=(r/'data'/n).read_bytes();assert {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==v
next_step='Freeze fresh detached N34R6 protocol/accounting/root review/release from turn669 disabled draft; retain all six invalid predecessor charges and unknown telemetry. Pass full public validate_release before state release adoption and locked idle GPU7 admission. No scientific promotion or protected evaluation.'
review=dict(schema='n34r6-runtime-regeneration-review-v1',at=now,source=e['source'],scientific_source=d['scientific_source']['commit'],status='CPU_RUNTIME_AND_30_FRESH_MANIFESTS_PASS_RELEASE_PENDING',probe=ref(p/'runtime-import-probe-v1.py'),inventory=ref(p/'runtime-import-probe-v1.json'),closure=ref(p/'runtime-closure.CANDIDATE-v1.json'),pre_prepare_receipt=ref(p/'runtime-probe-receipt-v1.json'),post_prepare_receipt=ref(p/'runtime-post-prepare-receipt-v1.json'),disabled_draft=ref(p/'prospective-draft-v1/plan.draft.json'),corrected_inventory_review=ref(o.parent/'000665/runtime-inventory-review-v1.json'),composed_configurations=30,fresh_identities_absent_from_ledger=True,ledger_prefixes=e['ledger_prefixes'],cuda_initialized=False,gpu_dispatched=False,probe_exit_code=0,next_step=next_step,limitations=['CPU import attestation does not prove complete native runtime coverage.','Dev efficacy, validation, formal and required ablations remain outstanding.'])
write(o/'runtime-regeneration-review-v1.json',review)
sp=r/'research-state.yaml';cp=r/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
with runner.locked(r/'data/qd-ed-state.lock'):
 s=runner.read_state(sp);c=json.loads(cp.read_text());assert s['source_commit']==e['source'] and s['active_controller'] is None and c['active_controller'] is None
 for f in [sp,cp]:shutil.copyfile(f,o/(f.name+'.before'))
 for x in [s,c]:x.update(n34r6_runtime_preparation=ref(o/'runtime-regeneration-review-v1.json'),next_action=next_step,updated_at=now)
 for f,x,y in [(sp,s,True),(cp,c,False)]:
  tmp=f.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(x,sort_keys=False,allow_unicode=True) if y else json.dumps(x,indent=2)+'\n');tmp.replace(f)
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==e['source']
write(o/'end-reconciliation-v1.json',dict(at=now,source=e['source'],ledger_prefixes=e['ledger_prefixes'],ledger_prefixes_unchanged=True,gpu_dispatches=0,active_controller=None,target_met=False,next_action=next_step))

(o/'operational-summary.md').write_text(f"""Turn669 — {now}

Current source {e['source']}; scientific source {d['scientific_source']['commit']} unchanged. Handoff, exact authorization, continuation and completion contract hashes verified. Driver268073/start97715947 and coordinator865070/start136320771 verified on boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Prior coordinator859062, CPU wrapper851893/executor851894, closed controller802963/worker805796 absent. Prior turn completed normally and its adoption/ledger effects reconciled. No active GPU cohort. STOP absent; authorization deadline2026-10-11T11:13:13Z.

Regenerated runtime closure with turn665 corrected CPU OpenGL conversions and serialization paths, and30 fresh N34R6 manifests on adopted source. Probe exited0; strict pre/post preparation runtime attestations and controller semantics PASS. No import errors, missing files or uncovered checkout modules; CUDA uninitialized. Fresh identities absent from ledger; draft release-disabled. Retained448 dispatches/63.87373613834589GPUh, six invalid N34 predecessor charges, unknown telemetry and all three private ledger byte/hash prefixes. State/checkpoint updated under ordinary state lock. No source change, GPU dispatch, driver/coordinator lock acquisition, foreign-state write, protected-result access or credential access.

Next bounded step: {next_step}

Unresolved: complete native runtime coverage, accepted fresh matched Dev efficacy, scientific promotion, validation20/formal10/required matched ablations and hash-bound completion record. Goal remains incomplete; local driver owns continuation.
""")
print(json.dumps({'status':review['status'],'source':e['source'],'manifests':30,'ledger_unchanged':True,'next_step':next_step}))
