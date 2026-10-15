import pathlib,json,hashlib,datetime,sys,shutil,subprocess,yaml
r=pathlib.Path.cwd();o=(r.parent/'autonomy_20261004/turns/000860').resolve();p=o/'runtime-v1';sys.path.insert(0,str(r))
from scripts import qd_ed_final_runner as runner

def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
e=json.loads((o/'entry-reconciliation-v1.json').read_text());d=json.loads((p/'plan.DISABLED-v1.json').read_text());i=json.loads((p/'runtime-import-probe-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not i['errors'] and not i['uncovered_checkout_modules'] and not i['missing_files'] and not i['cuda_initialized']
assert len(d['expected_manifests'])==11 and d['release_enabled'] is False and d['source']['commit']==e['source']
assert (p/'runtime-post-prepare-receipt-v1.json').exists()
ledger=(r/'data/attempt-ledger.jsonl').read_text();assert all(k not in ledger for k in d['expected_manifests'])
for n,v in e['ledger_prefixes'].items():
 b=(r/'data'/n).read_bytes();assert {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==v
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==e['source']
next_step='Freeze separate continuation11 budget authority, protocol/root review and detached release from turn860 runtime-v1/plan.DISABLED-v1.json; pass public continuation validate_release on pinned interpreter before adopting authority and locked idle GPU7 admission. Retain original19/R11, all472 charges and unknown telemetry. Missing11 only; no replay, automatic promotion or protected evaluation.'
review=dict(schema='n34-continuation-runtime-preparation-review-v1',at=now,source=e['source'],scientific_source=d['scientific_source']['commit'],status='CPU_RUNTIME_AND_MISSING11_MANIFESTS_PASS_RELEASE_PENDING',probe=ref(p/'runtime-import-probe-v1.py'),inventory=ref(p/'runtime-import-probe-v1.json'),closure=ref(p/'runtime-closure.CANDIDATE-v1.json'),pre_prepare_receipt=ref(p/'runtime-probe-receipt-v1.json'),post_prepare_receipt=ref(p/'runtime-post-prepare-receipt-v1.json'),disabled_draft=ref(p/'plan.DISABLED-v1.json'),scientific_equality=d['scientific_equality'],composed_configurations=11,missing_identities_absent_from_ledger=True,retained_count=19,ledger_prefixes=e['ledger_prefixes'],cuda_initialized=False,gpu_dispatched=False,probe_exit_code=0,next_step=next_step,limitations=['CPU preparation is not an execution release or complete native runtime validity evidence.','Outcome-aware amended Dev screening is not independent replication or confirmatory evidence.','Scientific promotion, validation, formal and required ablations remain outstanding.'])
write(o/'runtime-preparation-review-v1.json',review)
sp=r/'research-state.yaml';cp=r/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
with runner.locked(r/'data/qd-ed-state.lock'):
 s=runner.read_state(sp);c=json.loads(cp.read_text());assert s['source_commit']==e['source'] and c['source_commit']==e['source']
 assert not s['current_owned_workers'] and s['active_controller']['live_handles']==[]
 for f in [sp,cp]:shutil.copyfile(f,o/(f.name+'.before'))
 for x in [s,c]:x.update(n34_continuation_runtime_preparation=ref(o/'runtime-preparation-review-v1.json'),next_action=next_step,updated_at=now,status='N34_CONTINUATION_RUNTIME_READY_RELEASE_PENDING')
 for f,x,y in [(sp,s,True),(cp,c,False)]:
  tmp=f.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(x,sort_keys=False,allow_unicode=True) if y else json.dumps(x,indent=2)+'\n');tmp.replace(f)
write(o/'end-reconciliation-v1.json',dict(at=now,source=e['source'],ledger_prefixes=e['ledger_prefixes'],ledger_prefixes_unchanged=True,gpu_dispatches=0,live_controller_handles=[],target_met=False,next_step=next_step))
(o/'operational-summary.md').write_text(f'''Turn860 — {now}

Current owning source {e['source']}; scientific source {d['scientific_source']['commit']} unchanged. Driver268073/start97715947 and coordinator2287748/start139917316 verified on boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Prior turn859 completed exit0; adopted source and private ledger effects reconciled. Historical controller1322966 and executor2244802/2244805 absent. No live GPU cohort. STOP absent; authorization deadline2026-10-11T11:13:13Z.

Completed: CPU continuation preparation on adopted source with existing pinned dependencies. Exactly11 missing manifests, exact scientific equality, strict pre/post runtime receipts and controller proof PASS. No missing/uncovered modules; CUDA uninitialized; probe exit0. Retained19 verified via reviewed public preparation without outcome replay. Three private ledgers unchanged;472 attempts/69.38354303190809 GPUh retained. Owning state/checkpoint updated under ordinary state lock; no source edits, GPU dispatch, protected evaluation or driver locks.

Next bounded step: {next_step}

Unresolved: separate production release/public validation, missing11 outcomes and full native validity, scientific promotion, validation20/formal10/required matched ablations and hash-bound completion record. Original R11 remains partial; amended screen is outcome-aware. Goal incomplete; local driver continues.
''')
print(json.dumps({'status':review['status'],'source':e['source'],'manifests':11,'ledger_unchanged':True}))
