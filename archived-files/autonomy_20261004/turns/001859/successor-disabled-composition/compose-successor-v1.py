"""Bounded disabled artifact composition; never an owner acceptance or executor."""
import os, sys, json, hashlib, copy, datetime as dt, time, subprocess, traceback
from pathlib import Path
from decimal import Decimal
O=Path(__file__).resolve().parent
AUTH=json.loads((O/'authority-v1.json').read_text()); ROOT=Path(AUTH['worktree'])
T=O.parent.parent; OLD=T/'001841/composition-v6'; START=time.monotonic()
os.environ.update(PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1',TMPDIR=str(O/'tmp'))
sys.dont_write_bytecode=True
(O/'tmp').mkdir(exist_ok=False)
checks=[];outputs={};inputs={}
def guard():
 assert time.monotonic()-START<750,'bounded executor deadline'
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(AUTH['stop_authority']['deadline'].replace('Z','+00:00')),'authority deadline'
 assert all(not os.path.lexists(p) for p in AUTH['stop_authority']['paths']),'STOP'
def sha(data):return hashlib.sha256(data).hexdigest()
def ref(path):
 p=Path(path);return {'path':str(p),'sha256':sha(p.read_bytes())}
def read(value):
 if isinstance(value,dict):
  p=Path(value['path']);data=p.read_bytes();assert sha(data)==value['sha256'];assert 'bytes' not in value or len(data)==value['bytes'];inputs[str(p)]=value
 else:p=Path(value);data=p.read_bytes()
 return json.loads(data)
def save(name,doc):
 guard();p=O/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(json.dumps(doc,sort_keys=True,separators=(',',':'),allow_nan=False))
 outputs[name]=ref(p);return outputs[name]
def check(name,fn,expected_block=False):
 guard();t=time.monotonic()
 try:
  result=fn();checks.append(dict(check=name,status='UNEXPECTED_PASS' if expected_block else 'PASS',elapsed_seconds=time.monotonic()-t));return result
 except Exception as ex:
  checks.append(dict(check=name,status='EXPECTED_BLOCK' if expected_block else 'BLOCKED',error_type=type(ex).__name__,error=str(ex),elapsed_seconds=time.monotonic()-t));return None
def git(*args):return subprocess.check_output(['git','--no-optional-locks','-C',str(ROOT),*args],text=True).strip()
guard();proposal=read(AUTH['proposal']);RID=proposal['resource_id'];assert RID=='n36_readiness_preparation_recovery_001858'
assert git('rev-parse','HEAD')==AUTH['source']; initial_status=git('status','--porcelain','--untracked-files=no');assert not initial_status
ledger={}
for name,r in AUTH['ledger_prefixes'].items():
 data=Path(r['path']).read_bytes();assert len(data)==r['bytes'] and sha(data)==r['sha256'];assert RID.encode() not in data;ledger[name]=data
checks.append(dict(check='authority proposal source STOP and four complete ledger hashes; successor globally absent',status='PASS'))
g=read(OLD/'graph.complete-disabled-v1.json');n=copy.deepcopy(g);oldspec=read(g['specification']);oldplan=read(g['plan']);oldcontract=read(g['recovery_prefix_contract']);oldpolicy=read(g['policy'])
source=read(g['source_record']);assert source['commit']==AUTH['source']
# Source inventory is already current; do not recursively regenerate historical provenance.
ns=save('source-record.json',source);n['source_record']=ns
amendment=read(g['amendment']);amendment['source']=ns;n['amendment']=save('source-scope-amendment.disabled-v1.json',amendment)
runtime=read(g['runtime']);runtime['preparation']['source_record']=ns
assert runtime['provider_ready'] is runtime['cuda_egl_verified'] is runtime['preparation']['runtime_ready'] is False
n['runtime']=save('runtime.disabled-v1.json',runtime)
closure=read(g['runtime_closure']);closure['runtime']=n['runtime'];n['runtime_closure']=save('runtime-closure.disabled-v1.json',closure)
# Changed runtime bindings require new review. Preserve old reviews only as historical evidence.
controller=read(g['controller_semantics']);historical_controller=copy.deepcopy(controller)
controller.update(runtime=n['runtime'],runtime_closure=n['runtime_closure'],status='PENDING_OWNER_REVIEW',root_acceptance=None,historical_review_only=g['controller_semantics'])
controller['historical_review_evidence']=controller['review_evidence'];controller['review_evidence']={k:None for k in controller['review_evidence']}
n['controller_semantics']=save('controller-semantics.pending-disabled-v1.json',controller)
predecessors=[]
for d in proposal['predecessors']:
 raw=Path(d['raw_sequence']['path']).read_bytes();assert sha(raw)==d['raw_sequence']['sha256'] and len(raw)==d['raw_sequence']['bytes']
 rows=[json.loads(line) for line in raw.splitlines()];last=rows[-1]
 assert [r['event'] for r in rows]==d['events'];assert all(r['resource_id']==d['resource_id'] for r in rows)
 assert str(last['gpu_process_wall_seconds'])==d['retained_charge_gpu_seconds']
 p=dict(consumed=True,events=[r['event'] for r in rows],kind=last['kind'],resource_id=last['resource_id'],terminal_status=last['event'],telemetry_complete=last['telemetry_complete'],provider_calls_retained=last['provider_calls'],retained_charge_gpu_seconds=last['gpu_process_wall_seconds'],retained_charge_gpu_hours=last['gpu_process_wall_seconds']/3600,raw_bytes=len(raw),raw_sequence={k:d['raw_sequence'][k] for k in ('path','sha256')},rows=rows,row_segments=[])
 for key,name,begin,end in [('own_journal','readiness-preparation-ledger.jsonl',d['own_start'],d['own_end']),('global_health_segment','gpu-healthcheck-ledger.jsonl',d['global_start'],d['global_end'])]:
  assert ledger[name][begin:end]==raw;p[key]=dict(path=AUTH['ledger_prefixes'][name]['path'],start_inclusive=begin,end_exclusive=end,sha256=sha(raw))
 cursor=0
 for line,row in zip(raw.splitlines(keepends=True),rows):
  p['row_segments'].append(dict(bytes=len(line),event=row['event'],global_start_inclusive=d['global_start']+cursor,global_end_exclusive=d['global_start']+cursor+len(line),own_start_inclusive=d['own_start']+cursor,own_end_exclusive=d['own_start']+cursor+len(line),sha256=sha(line)));cursor+=len(line)
 predecessors.append(p)
assert len(predecessors)==4
identity=dict(schema='n36-prospective-readiness-recovery-identity-v1',resource_id=RID,recovery_of=[p['resource_id'] for p in predecessors],retained_charge_gpu_hours=sum(p['retained_charge_gpu_hours'] for p in predecessors),source=AUTH['source'],unconsumed_at_draft=True,automatic_retry=False,adopted=False,release_enabled=False)
n['readiness_recovery']=save('recovery-identity.disabled-v1.json',identity)
contract=copy.deepcopy(oldcontract);contract.update(status='DISABLED_CANDIDATE_PENDING_ROOT_TERMINAL_RECONCILIATION',drafting_authority=ref(O/'authority-v1.json'),identity=n['readiness_recovery'],predecessors=predecessors,root_observed_ledger_prefixes=AUTH['ledger_prefixes'],own_journal_at_draft=AUTH['ledger_prefixes']['readiness-preparation-ledger.jsonl'],accepted_review=None,root_terminal_reconciliation=None)
contract['successor'].update(resource_id=RID,occurrences_in_complete_ledgers={k:0 for k in ledger})
contract['read_semantics'][-1]='Exactly four raw consumed predecessor sequences retained; no root reconciliation or acceptance claimed. Successor remains disabled; current production freshness and full global budget checks remain mandatory.'
n['recovery_prefix_contract']=save('recovery-prefix-contract.disabled-v1.json',contract)
policy=copy.deepcopy(oldpolicy)
for k in policy:
 if k.endswith('_path'):policy[k]=str(O/('pending-'+k.removesuffix('_path')+'.json'))
policy.update(resource_id=RID,disabled_runtime_path=n['runtime']['path'])
# Reuse exact unchanged inventory-derived previous specification, not a new approval.
n['policy']=save('preparation-policy.disabled-v1.json',policy)
spec=copy.deepcopy(oldspec);spec.update(readiness_recovery=n['readiness_recovery'],recovery_prefix_contract=n['recovery_prefix_contract'])
spec['runtime_binding'].update(preparation=n['policy'],amendment=n['amendment'],source_record_path=ns['path'],runtime_path=str(O/'pending-measured-runtime.json'))
n['specification']=save('specification.disabled-v1.json',spec)
pairs=[(g[k],n[k]) for k in ('source_record','runtime','runtime_closure','controller_semantics','amendment','readiness_recovery','recovery_prefix_contract','policy','specification')]
def replace(v):
 for a,b in pairs:
  if v==a:return copy.deepcopy(b)
 if isinstance(v,dict):return {k:replace(x) for k,x in v.items()}
 if isinstance(v,list):return [replace(x) for x in v]
 return v
# Retain unchanged scientific source/thresholds/config/commands and immutable accounting contract.
for key in ('scope','accounting'):
 nr=save(key+'.disabled-v1.json',replace(read(oldplan[key])));pairs.append((oldplan[key],nr))
# Fresh manifest documents, including all40, bind exact new operational references.
audit=replace(read(g['audit']));index=[]
for i,row in enumerate(audit['episodes']):
 oldref=audit['expected_manifests'][row['episode_key']]
 nr=save('audit-manifests/%02d.json'%i,replace(read(oldref)));pairs.append((oldref,nr));audit['expected_manifests'][row['episode_key']]=nr
 index.append(dict(row=row,original=oldref,new=nr,composition='exact_operational_reference_rebinding_unchanged_scientific_command'))
ar=save('all40-audit.disabled-v1.json',audit);pairs.append((g['audit'],ar));n['audit']=ar
engineering=replace(read(g['separate_engineering_manifest']));er=save('engineering-manifest.disabled-v1.json',engineering);pairs.append((g['separate_engineering_manifest'],er));n['separate_engineering_manifest']=er
plan=replace(oldplan);n['plan']=save('engineering-plan.disabled-v1.json',plan)
n.update(full40_manifests=save('full40-manifest-index-v1.json',dict(manifests=index)),resource_id=RID,actual_source_worktree=str(ROOT),source_placement_gate=None,root_controller_acceptance=None,root_acceptance=None,authority=None,b5_review=None,prior_partial_graph=None,historical_graph_only=ref(OLD/'graph.complete-disabled-v1.json'),status='DISABLED_COMPLETE_COMPOSITION_PENDING_OWNER_GATES',review_status='CHANGED_BINDINGS_REQUIRE_OWNER_REVIEW',graph_complete=True,graph_verified=False,release_enabled=False,gpu_authorized=False,provider_measurement_authorized=False,independent_review_claimed=False,historical_accounting_only=dict(recovery_of=identity['recovery_of'],retained_charge_gpu_hours=[p['retained_charge_gpu_hours'] for p in predecessors],retained_charge_gpu_seconds=sum(p['retained_charge_gpu_seconds'] for p in predecessors)))
gr=save('graph.complete-disabled-v1.json',n)
vi=save('disabled-graph-validator-input-v1.json',dict(graph=dict(plan=n['plan'],runtime=n['runtime']),approved=False,release_enabled=False))
# Bound exact production imports; no source, owner, network, GPU, or credential writes/reads.
os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(n['specification']);sys.path.insert(0,str(ROOT))
def hook(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.fsdecode(args[0]);p=Path(name);low=name.lower()
  if '2026-08-10-eds-qd-stage-guidance-transition-design.md' in low or p.name in ('auth.json','credentials.json','.env','state.json','checkpoint.json') or '/.ssh/' in low or '/dev/nvidia' in low:raise PermissionError('prohibited input')
  mode,flags=args[1:3];writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
  if writing and name!='/dev/null' and not p.resolve().is_relative_to(O):raise PermissionError('out of scope write')
 if event in ('socket.connect','socket.bind'):raise PermissionError('network prohibited')
 if event=='subprocess.Popen' and Path(str(args[0])).name not in ('git','uname','ldconfig'):raise PermissionError('non-CPU subprocess prohibited')
sys.addaudithook(hook)
from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_readiness_prepare as prep
check('exact production preparation policy',lambda:e.exact(prep.policy(spec),policy,'candidate policy'))
captured=check('exact production recovery capture four full raw predecessors; optimistic recheck without owner lock',lambda:e._recovery_capture(contract,Path(AUTH['ledger_prefixes']['attempt-ledger.jsonl']['path']).parent))
assert captured is not None
parsed,tail,current=captured;assert not tail and not current
snapshot=check('exact production budget_snapshot complete attempt and global resource ledgers',lambda:e.r.budget_snapshot(parsed[e.JOURNALS[0]],parsed[e.JOURNALS[1]]));assert snapshot is not None
check('exact production recovery contract rejects absent owner reconciliation',lambda:e._recovery_contract(spec),True)
check('exact production specification validates unchanged fields then rejects absent owner reconciliation',lambda:e._recovery_specification(spec),True)
check('exact production specification entrypoint remains disabled',e.specification,True)
check('exact production graph admission rejects pending owner gates',lambda:prep.verify_graph(read(vi),source,read(spec['canonical_runtime'])),True)
from scripts.qd_ed_n34_controller import verify_semantics
check('exact production controller validator rejects changed unreviewed binding',lambda:verify_semantics(n['controller_semantics'],n['runtime'],closure),True)
# Recomposition of one C0 and one N36 manifest checks both command branches; remaining rows only references changed.
for i in (0,3):
 row=audit['episodes'][i]
 check('production CPU manifest recomposition '+row['episode_key'],lambda row=row:e.exact(e.b.manifest(audit,runtime,row),read(audit['expected_manifests'][row['episode_key']]),'rebound manifest'))
D=lambda x:Decimal(str(x))
seconds=sum((D(p['retained_charge_gpu_seconds']) for p in predecessors),D(0))
protected=sum(max(0.,h-snapshot['gpu_hours_by_bucket'][k]) for k,h in e.c.CAPS['protected_gpu_hours'].items())
assert str(seconds)==proposal['arithmetic']['retained_preparation_gpu_seconds']
assert abs(D(snapshot['gpu_hours_consumed'])-D(proposal['arithmetic']['reconstructed_current_gpu_hours']))<D('1e-12')
assert snapshot['gpu_healthcheck_inflight']==snapshot['running']==0
arithmetic=dict(schema='n36-disabled-successor-full-ledger-arithmetic-v1',resource_id=RID,production_snapshot=snapshot,predecessor_seconds_decimal_terms=[str(D(p['retained_charge_gpu_seconds'])) for p in predecessors],predecessor_seconds_decimal_sum=str(seconds),predecessor_hours_production_sum=identity['retained_charge_gpu_hours'],provider_calls_retained=sum(p['provider_calls_retained'] for p in predecessors),proposal_arithmetic=proposal['arithmetic'],protected_hours_production=protected,finite_limits=proposal['finite_limits'],owner_state_read=False,preparation_budget_executed=False,reason='preparation_budget reads owner state and requires owner accounting authority/release; outside executor authority',release_enabled=False)
arithmetic_ref=save('release-arithmetic-v1.json',arithmetic)
for name,r in AUTH['ledger_prefixes'].items():assert Path(r['path']).read_bytes()==ledger[name]
assert git('rev-parse','HEAD')==AUTH['source'] and git('status','--porcelain','--untracked-files=no')==initial_status
checks.append(dict(check='final source and four complete private ledgers unchanged',status='PASS'))
validation=save('validation-results-v1.json',dict(checks=checks,production_predicates_unmodified=True,full_expensive_audit_run=False,measurement_run=False,owner_lock_acquired=False))
remaining=[dict(id='root_terminal_reconciliation',status='PENDING',slots=['recovery_prefix_contract.root_terminal_reconciliation','recovery_prefix_contract.accepted_review'],requirement='Owner independently reconciles all four exact raw sequences/current terminal handles; emits authentic review/reconciliation and fresh dependent contract/specification/manifest graph.'),dict(id='controller_binding_review',status='PENDING',slots=['controller_semantics.root_acceptance','controller_semantics.review_evidence'],requirement='Unchanged source semantics may be reused within original scope; owner must review new runtime/closure binding before assigning ROOT_REVIEWED.'),dict(id='disabled_graph_admission',status='PENDING',requirement='Exact production verify_graph after owner gates; no full expensive audit performed here.'),dict(id='accounting_adoption_and_finite_release',status='NOT_AUTHORIZED',requirement='Owner state/accounting snapshot, independent review, actual issuance time through original deadline, STOP and one-use preparation_budget admission. GPU/provider authorization remains false.'),dict(id='later_readiness_full_audit_B5_health_episode',status='NOT_AUTHORIZED',requirement='Fresh actual measurement, independent/root acceptance and full production audit; separately authorized fresh health and episode releases. Preserve freshness checks.' )]
# Commands are concrete for this disabled candidate. Gate-dependent future refs must be supplied by owner, never fabricated.
cmd_prefix=['env','PYTHONDONTWRITEBYTECODE=1','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','QD_ED_N36_R1_SPECIFICATION='+json.dumps(n['specification']),'/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B']
commands=[dict(purpose='Repeat bounded read-only exact candidate checks',argv=cmd_prefix+[str(O/'verify-candidate-v1.py')],cwd=str(ROOT),expected='Policy/capture/budget pass; null owner gates reject'),dict(purpose='Owner full disabled graph admission after authentic gate replacement',function='scripts.qd_ed_n36_readiness_prepare.verify_graph(release_graph, source, canonical_baseline)',required='New owner-final graph/specification refs, not the disabled candidate',authorized_here=False),dict(purpose='Owner budget admission before any separately authorized measurement',function='scripts.qd_ed_n36_readiness_prepare.preparation_budget(owner_root, plan, accounting_authority, release)',required='Authentic adopted owner state/accounting and fresh finite release; current STOP/deadline',authorized_here=False)]
command_ref=save('next-commands-v1.json',dict(commands=commands,release_enabled=False))
report=dict(schema='n36-successor-disabled-composition-report-v1',node_id='15.6',role='bounded CPU artifact executor, not coordinator',status='COMPLETE_DISABLED_COMPOSITION_WITH_PENDING_OWNER_GATES',source=AUTH['source'],resource_id=RID,authority=ref(O/'authority-v1.json'),proposal=AUTH['proposal'],candidate_graph=gr,validation=validation,checks=checks,arithmetic=arithmetic_ref,unresolved_owner_gates=remaining,next_commands=command_ref,predecessor_count=4,retained_preparation_gpu_seconds=str(seconds),reuse_scope=dict(source_inventory='Same current commit and inventory; no broad regeneration',runtime_inventory='Unchanged native/external file and module inventories; fresh references only',scientific_equivalence=g['scientific_equivalence'],source_review=g['final_source_review'],controller='Historical evidence only, changed binding approval null',accounting_contract='Immutable production-pinned accounting contract retained; fresh scope/accounting and release arithmetic bind successor specification',deployment='Unchanged engineering episode route retained; every preparation proof/release/output path is fresh'),fresh_pending_paths={k:v for k,v in policy.items() if k.endswith('_path')},outputs=outputs.copy(),gpu_authorized=False,provider_measurement_authorized=False,release_enabled=False,independent_review_claimed=False,root_acceptance_claimed=False,source_edits=False,owner_state_written=False,ledger_writes=False,measurement_run=False,delegation=False,elapsed_seconds=time.monotonic()-START,at=dt.datetime.now(dt.timezone.utc).isoformat())
save('report-v1.json',report)
print(json.dumps(dict(report=ref(O/'report-v1.json'),checks=checks,arithmetic=arithmetic_ref)))
