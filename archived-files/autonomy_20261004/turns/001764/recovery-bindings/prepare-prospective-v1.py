"""Bounded standard-library-only prospective evidence; no production adoption."""
import ast, datetime as dt, hashlib, json, os, subprocess, sys, time
from pathlib import Path
from decimal import Decimal
sys.dont_write_bytecode=True
START=time.monotonic()
O=Path(__file__).absolute().parent
T=O.parent.parent
INPUTS={}; OUTPUTS={}; CHECKS=[]
IDENTITY='n36_readiness_preparation_recovery_001764'
OLD='n36_readiness_preparation_recovery_001723'
def record(p):
 p=Path(p); data=p.read_bytes()
 return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def read(p):
 if isinstance(p,dict):
  r=p; p=Path(r['path']); actual=record(p)
  assert all(actual[k]==r[k] for k in ('sha256','bytes') if k in r),str(p)
 else:p=Path(p);actual=record(p)
 INPUTS[str(p)]=actual
 return json.loads(p.read_text())
def ref(r):return {k:r[k] for k in ('path','sha256')}
def save(name,d):
 guard(); p=O/name; assert p.parent==O and not p.exists()
 data=d if isinstance(d,bytes) else (json.dumps(d,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
 with p.open('xb') as f:f.write(data)
 OUTPUTS[str(p)]=record(p);return ref(OUTPUTS[str(p)])
A=read(O/'authority-v1.json')
def guard():
 assert time.monotonic()-START<1100
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['stop_authority']['deadline'].replace('Z','+00:00'))
 assert all(not os.path.lexists(p) for p in A['stop_authority']['paths'])
def check(label,value):
 assert value,label
 CHECKS.append(dict(check=label,status='PASS'))
ROOT=Path(A['worktree'])
os.environ.update(PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',CUDA_VISIBLE_DEVICES='')
def source():
 vals={}
 for key,args in [('commit',['rev-parse','HEAD']),('tree',['rev-parse','HEAD^{tree}']),('tracked_changes',['status','--porcelain','--untracked-files=no'])]:
  vals[key]=subprocess.check_output(['git','--no-optional-locks','-C',str(ROOT),*args],text=True).strip()
 assert vals['commit']==A['source'] and not vals['tracked_changes']
 return vals
before=source();guard()
summary=read(T/'001763/operational-summary-v1.json');review=read(summary['review'])
index=read(T/'001748/disabled-graph-composition/final-composition-index-v1.json')
graph=read(index['graph']);accept=read(T/'001755/root-b5-scoped-acceptance-v1.json')
terminal=read(A['terminal_reconciliation']);standing=read(A['standing_authority'])
measurement={}
for name in ['measurement-launch-intent-v1.json','measurement-exit-v1.json','release-preparation-result-v1.json','full-ledger-accounting-v1.json','reservation-arithmetic-v1.json']:
 measurement[name]=read(T/'001756'/name)
spec=read(graph['specification']);policy=read(graph['policy']);contract=read(graph['recovery_prefix_contract'])
runtime=read(graph['runtime']);base=read(review['base_closure']);candidate=read(summary['prospective_candidate_closure'])
check('candidate reference equals scoped review',summary['prospective_candidate_closure']==review['candidate_closure'])
check('all 6767 original module rows retained exactly',len(base['modules'])==6767 and all(candidate['modules'].get(k)==v for k,v in base['modules'].items()))
added={k:v for k,v in candidate['modules'].items() if k not in base['modules']}
check('exactly 145 OpenGL additions',len(added)==145 and all(k.startswith('OpenGL.') for k in added))
check('all non-module closure fields unchanged including strict runtime binding',set(base)==set(candidate) and all(base[k]==candidate[k] for k in base if k!='modules'))
check('closure bound to immediate prior exact disabled runtime',candidate['runtime']==graph['runtime'])
for k,r in added.items():
 actual=record(r['path']);assert actual['sha256']==r['sha256'],k;INPUTS[actual['path']]=actual
check('145 added installed source hashes verified without imports',True)
check('readiness and provider remain disabled',not runtime['preparation']['runtime_ready'] and not runtime['provider_ready'] and not runtime['cuda_egl_verified'])
raw={}
for name,r in A['ledger_prefixes'].items():
 actual=record(r['path']);check('complete current ledger matches authority: '+name,all(actual[k]==r[k] for k in ('path','bytes','sha256')))
 INPUTS[r['path']]=actual;raw[name]=Path(r['path']).read_bytes();assert raw[name].endswith(b'\n')
 rows=[json.loads(line) for line in raw[name].splitlines()]
 check('fresh identity absent: '+name,not any(IDENTITY in (x.get('resource_id'),x.get('attempt_id'),x.get('episode_key')) for x in rows))
for name,r in contract['original_ledger_prefixes'].items():
 check('original amendment prefix unchanged: '+name,hashlib.sha256(raw[name][:r['bytes']]).hexdigest()==r['sha256'])
own=raw['readiness-preparation-ledger.jsonl']; health=raw['gpu-healthcheck-ledger.jsonl']; offset=contract['original_ledger_prefixes']['gpu-healthcheck-ledger.jsonl']['bytes']
check('entire six-row readiness history mirrored byte-for-byte',health[offset:]==own and len(own.splitlines())==6)
rows=[json.loads(x) for x in own.splitlines()];groups=[rows[:3],rows[3:]]
check('two terminal lifecycles retained in original order',all([x['event'] for x in group]==['reserved','dispatched','aborted'] for group in groups))
check('latest terminal exact reconciliation match',rows[-1]==terminal['terminal'] and rows[-1]['resource_id']==OLD)
check('latest charge and unknown telemetry retained',rows[-1]['gpu_process_wall_seconds']/3600==0.06501105613178677 and rows[-1]['telemetry_complete'] is False)
rawref=save('retained-readiness-history.raw.jsonl',own)
charges=[dict(resource_id=g[-1]['resource_id'],gpu_process_wall_seconds=g[-1]['gpu_process_wall_seconds'],gpu_hours=g[-1]['gpu_process_wall_seconds']/3600,telemetry_complete=g[-1]['telemetry_complete'],provider_calls=g[-1]['provider_calls'],events=[x['event'] for x in g]) for g in groups]
accounting=save('accounting-prefix.prospective-v1.json',dict(schema='n36-prospective-accounting-prefix-evidence-v1',authority=ref(record(O/'authority-v1.json')),current_full_ledger_prefixes=A['ledger_prefixes'],original_ledger_prefixes=contract['original_ledger_prefixes'],original_retained_snapshot_reference=spec['retained_snapshot_reference'],retained_history=rawref,retained_lifecycles=charges,terminal_reconciliation=ref(record(T/'001759/terminal-reconciliation-v1.json')),all_charges_preserved=True,unknown_telemetry_preserved=True,charges_erased=False,accounting_baseline_rebased=False,full_budget_recomputed=False,reservation_created=False,caps_changed=False,synchronized_admission_claimed=False))
identity=save('recovery-identity.prospective-disabled-v1.json',dict(schema='n36-prospective-readiness-recovery-identity-v1',resource_id=IDENTITY,recovery_of=OLD,earlier_predecessor=charges[0]['resource_id'],unconsumed_at_draft=True,occurrences_in_complete_ledgers={k:0 for k in raw},retained_charge_gpu_hours=0.06501105613178677,retained_lifecycles=charges,accounting_prefix=accounting,automatic_retry=False,release_enabled=False,adopted=False))
closure=save('runtime-closure.candidate-v1.json',Path(summary['prospective_candidate_closure']['path']).read_bytes())
# Inspect committed production functions statically; do not monkeypatch/import validators.
codepath=ROOT/'scripts/qd_ed_n36_engineering_r1.py';prep=ROOT/'scripts/qd_ed_n36_readiness_prepare.py'
for p in (codepath,prep):INPUTS[str(p)]=record(p)
tree=ast.parse(codepath.read_text()); pin=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SPECIFICATION' for t in n.targets))
check('unchanged production pins exact old specification',pin==graph['specification'] and policy['resource_id']==OLD)
funcs={n.name:ast.get_source_segment(codepath.read_text(),n) for n in tree.body if isinstance(n,ast.FunctionDef)}
check('production restricts retained prefix to three rows at original zero offset',"== 3, 'three retained raw rows'" in funcs['_recovery_capture'] and "'readiness-preparation-ledger.jsonl', 0" in funcs['_recovery_capture'])
check('production original accounting offsets cannot be rebased',"amendment['ledger_prefixes']" in funcs['_recovery_contract'])
blockers=[dict(id='PINNED_CONSUMED_IDENTITY',source=record(codepath),lines=[37,86,100],detail='Committed source pins the exact turn001730 specification and policy resource_id n36_readiness_preparation_recovery_001723. Fresh specification/policy artifacts cannot be consumed by unchanged source; replacing old pinned bytes is forbidden and hash validation would reject.'),dict(id='SINGLE_PREDECESSOR_PARTITION',source=record(codepath),lines=[641,666,675,706],detail='Current own journal has 10278 bytes and six rows from two charged aborted lifecycles. Production requires exactly three retained predecessor rows starting at own offset 0 and original global offset 114767, then only its named current successor. Replacing successor with 001764 leaves consumed 001723 as a foreign identity; replacing predecessor with 001723 fails original offsets. Retaining six rows fails the three-row check. No permitted artifact-only rebinding satisfies these constraints.'),dict(id='NO_FRESH_ROOT_BINDING_ACCEPTANCE',detail='Prior B5/controller approvals cover their exact historical bindings. They remain retained evidence only and cannot be asserted as approval of this changed runtime closure or fresh identity.')]
retained=save('retained-evidence-v1.json',dict(schema='n36-scoped-retained-evidence-v1',prior_composition_index=ref(record(T/'001748/disabled-graph-composition/final-composition-index-v1.json')),prior_graph=index['graph'],scoped_b5_acceptance=ref(record(T/'001755/root-b5-scoped-acceptance-v1.json')),prior_controller=graph['controller_semantics'],prior_controller_acceptance=graph['root_controller_acceptance'],opengl_review=ref(summary['review']),measurement_records={k:ref(record(T/'001756'/k)) for k in measurement},terminal_reconciliation=ref(record(T/'001759/terminal-reconciliation-v1.json')),scope='Historical static semantic findings retained unchanged. No new independent review, root approval, native readiness or adoption claimed; changed binding consumers remain pending.'))
proposal=save('affected-bindings.prospective-disabled-v1.json',dict(schema='n36-blocked-prospective-recovery-bindings-v1',status='BLOCKED_UNCHANGED_SOURCE_CONTRACT',resource_id=IDENTITY,identity=identity,source_commit=A['source'],source_record=graph['source_record'],runtime=graph['runtime'],runtime_closure=closure,accounting_prefix=accounting,retained_evidence=retained,base_graph=index['graph'],affected_consumers_pending=['preparation policy and pinned specification','recovery history partition contract','controller runtime-closure reference with scoped review carry-forward','audit and engineering manifest closure bindings','audit and engineering plans and final graph','root preparation accounting and release'],release=None,root_review=None,release_enabled=False,provider_measurement_authorized=False,gpu_authorized=False,adopted=False,graph_complete=False,blockers=blockers))
check('source commit tree and tracked cleanliness unchanged',source()==before)
for p,r in INPUTS.items():check('input unchanged: '+p,record(p)==r)
manifest=save('artifact-manifest-v1.json',dict(schema='n36-prospective-artifact-manifest-v1',files=list(OUTPUTS.values())+[record(__file__)],excludes=['artifact-manifest-v1.json','report-v1.json','report-v1.sha256','existing executor transport logs']))
report=dict(schema='n36-prospective-recovery-bindings-report-v1',status='BLOCKED_SAFE_PREPARATION_INCOMPLETE',at=dt.datetime.now(dt.timezone.utc).isoformat(),authority=ref(record(O/'authority-v1.json')),resource_id=IDENTITY,recovery_of=OLD,source=dict(worktree=str(ROOT),**before),source_unchanged=True,identity=identity,runtime_closure=closure,accounting_prefix=accounting,prospective_bindings=proposal,retained_evidence=retained,artifact_manifest=manifest,artifacts=list(OUTPUTS.values())+[record(__file__)],direct_inputs=list(INPUTS.values()),focused_validation=CHECKS,blockers=blockers,retained_charge_gpu_hours=0.06501105613178677,retained_lifecycles=charges,unknown_telemetry_preserved=True,caps_changed=False,deadline=A['stop_authority']['deadline'],stop_authority=A['stop_authority'],elapsed_seconds=time.monotonic()-START,maximum_executor_seconds=1200,source_edits=False,owning_state_mutation=False,ledger_writes=False,old_artifact_writes=False,release_enabled=False,release_candidate=None,measurement_enabled=False,adopted=False,gpu_dispatches=0,provider_calls=0,native_imports=0,stage_access=False,protected_results_access=False,scientific_changes=False,independent_approval_claimed=False,full_graph_validated=False,recursive_provenance_rebuilt=False,gaps=['No complete graph or consumable release produced: unchanged source pins a consumed identity and supports only one retained predecessor.','Production graph/release validators were not bypassed or claimed to pass; no broad tests run.','Root must resolve the source/authority incompatibility before downstream composition or measurement; executor made no source change.','Prior controller/B5 static evidence is preserved, not transferred as approval of new bindings.','Runtime native coverage, measured readiness, external acceptance and scientific goal remain unproven.'],next_action='Root review of concrete unchanged-source blockers and prepared immutable evidence; do not dispatch or replay 001723.')
r=save('report-v1.json',report);save('report-v1.sha256',(r['sha256']+'  report-v1.json\n').encode());print(json.dumps(dict(status=report['status'],report=r,artifacts=len(OUTPUTS),checks=len(CHECKS))))
