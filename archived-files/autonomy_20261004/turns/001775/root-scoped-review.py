import ast,copy,datetime,hashlib,json,math,os,pathlib,subprocess,types,fcntl,sys
from pathlib import Path
sys.dont_write_bytecode=True
O=Path(__file__).absolute().parent; T=O.parent; B=T/'001771/recovery-bindings'; W=Path.cwd(); ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
def ref(p):
 p=Path(p);return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(x):
 if isinstance(x,dict):
  p=Path(x['path']);assert ref(p)['sha256']==x['sha256'];return json.loads(p.read_bytes())
 return json.loads(Path(x).read_bytes())
def save(n,x):
 p=O/n;assert not p.exists();p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');return ref(p)
def identity(pid):
 p=Path('/proc')/str(pid)
 if not p.exists():return dict(pid=pid,alive=False)
 f=(p/'stat').read_text().rsplit(')',1)[1].split();return dict(pid=pid,alive=f[0]!='Z',state=f[0],start_ticks=int(f[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); a=read(B/'authority-v1.json');assert all(not os.path.lexists(p) for p in a['stop_authority']['paths']);assert now<a['stop_authority']['deadline']
prior=read(T/'001774/operational-summary-v1.json'); driver=read(T.parent/'driver-status.json');handles={}
for k in ['driver','process']:
 x=driver[k]; y=identity(x['pid']);assert all(x[z]==y[z] for z in ['pid','boot_id','start_ticks']);handles[k]=y
assert read(T/'001774/receipt.json')['exit']==0
ledgers={}
for name,r in prior['ledger_prefixes'].items():
 raw=Path(r['path']).read_bytes();assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256'];ledgers[name]=r
commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip();assert commit=='a5b32cdefc0879e98011f86b1559e4250926ba62'
assert not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True).strip()
contract=read(B/'recovery-prefix-contract.prospective-disabled-v2.json');spec=read(B/'specification.prospective-disabled-v1.json');graph=read(B/'affected-graph.prospective-disabled-v1.json');closure=read(graph['runtime_closure']);runtime=read(graph['runtime'])
predecessor_handles=[]
for pred in contract['predecessors']:
 raw=Path(pred['raw_sequence']['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==pred['raw_sequence']['sha256'];assert [json.loads(x) for x in raw.splitlines()]==pred['rows']
 for segname in ['own_journal','global_health_segment']:
  seg=pred[segname];assert Path(seg['path']).read_bytes()[seg['start_inclusive']:seg['end_exclusive']]==raw
 assert pred['events']==['reserved','dispatched','aborted'] and pred['telemetry_complete'] is False
 assert pred['retained_charge_gpu_hours']==pred['retained_charge_gpu_seconds']/3600
 for row in pred['rows']:
  for key in ['process','parent']:
   old=row.get(key)
   if old:
    live=identity(old['pid']);matches=live['alive'] and live.get('boot_id')==old['boot_id'] and str(live.get('start_ticks'))==str(old.get('start_ticks',old.get('proc_start_ticks')))
    assert not matches;predecessor_handles.append(dict(recorded=old,current=live,identity_matches=False))
rid=contract['successor']['resource_id']
for r in ledgers.values():assert all(rid not in (v.get('resource_id'),v.get('attempt_id'),v.get('episode_key')) for v in map(json.loads,Path(r['path']).read_text().splitlines()))
# Exact read-only definitions from deployed production sources. No production module or native imports.
base=dict(Path=Path,json=json,hashlib=hashlib,os=os,subprocess=subprocess,math=math)
def extract(file,names,ns):
 p=ROOT/file;nodes=[]
 for n in ast.parse(p.read_bytes()).body:
  if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names:nodes.append(n)
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets):nodes.append(n)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns);return ns
wn=extract('scripts/qd_ed_n23_worker.py',{'require','sha','canonical_sha','read_ref'},base.copy());w=types.SimpleNamespace(**wn)
ns=extract('scripts/qd_ed_n36_engineering_r1.py',{'AMENDMENT','HEALTH_ID','EPISODE_KEY','JOURNALS','exact','reference','_recovery_json','_recovery_rows','_recovery_read','_recovery_predecessors','_recovery_contract','_recovery_capture'},dict(base,w=w))
with open(W/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 parsed,tail,current=ns['_recovery_capture'](contract,W/'data');assert len(parsed['readiness-preparation-ledger.jsonl'])==6 and not tail and not current
review=save('recovery-binding-review-v1.json',dict(schema='n36-root-recovery-binding-review-v1',at=now,reviewer='owning_root_coordinator_turn001775',status='PASS_SCOPED_STATIC_RECOVERY_ACCOUNTING',candidate=ref(B/'recovery-prefix-contract.prospective-disabled-v2.json'),source=commit,findings=['Both consumed predecessor raw sequences exactly match private/global ledger segments; six rows retained.','Charges retained: 162.70163536071777 + 234.03980207443237 = 396.74143743515015 seconds; 0.11020595484309727 GPU hours. Each provider call retained; telemetry remains incomplete.','Original global health offset 114767 unchanged. Fresh successor is absent in all four complete ledgers.','Prior executor completed; consumed preparation parent/child identities are no longer live.','Missing scoped root reconciliation was a real blocker; this actual review supplies it. Complete graph, native readiness and release remain unproven.'],retained_charge_gpu_hours=sum(p['retained_charge_gpu_hours'] for p in contract['predecessors']),predecessor_identity_checks=predecessor_handles,ledger_prefixes=ledgers,gpu_authorized=False,release_enabled=False,scientific_success=False,independent_review_claimed=False))
terminal=save('recovery-terminal-reconciliation-v1.json',dict(schema='n36-recovery-binding-review-terminal-reconciliation-v1',at=now,review=review,live_handles=[],root_accepts_blocking_findings=True,ledger_prefixes=contract['root_observed_ledger_prefixes'],scope='Root accepts static recovery findings, not readiness or release',release_enabled=False))
contract['accepted_review']=review;contract['root_terminal_reconciliation']=terminal;contract['status']='ROOT_REVIEWED_DISABLED_RECOVERY_ACCOUNTING'
contract['read_semantics']=[x for x in contract['read_semantics'] if 'accepted_review is deliberately null' not in x]+['Retain both exact predecessor segments and consumed identities. Turn001775 root review and reconciliation cover static accounting only; no release authority.']
cr=save('recovery-prefix-contract.root-reviewed-disabled-v2.json',contract);spec['recovery_prefix_contract']=cr
sr=save('specification.root-reviewed-disabled-v1.json',spec);assert ns['_recovery_contract'](spec)==contract
# Review exact unchanged deployed controller code and binding delta, retaining explicit static limits.
oldref=read(B/'controller-semantics.prospective-disabled-v1.json')['historical_review'];old=read(oldref);candidate=read(graph['controller_semantics']);ev={}
for k,r in old['review_evidence'].items():
 prior_ev=read(r)
 for source in prior_ev['sources']: assert ref(source['path'])==source
 ev[k]=save(k+'-root-reviewed-v1.json',dict(kind='deployed_source_review',at=now,status='ROOT_REVIEWED',runtime=graph['runtime'],runtime_closure=graph['runtime_closure'],source_commit=commit,sources=prior_ev['sources'],findings=prior_ev['findings'],prior_review=r,reviewer='owning_root_coordinator_turn001775',fixture_only=False,native_execution_observed=False,physical_gain_certified=False,release_enabled=False,review_scope='Source functions inspected this turn; exact source hashes unchanged. Accept current runtime binding for static semantics only. No independent review of new graph claimed.'))
assert candidate['instance']==old['instance'] and candidate['semantics']==old['semantics'];assert closure['modules'][candidate['module']]==candidate['source'];assert ref(candidate['source']['path'])==candidate['source']
assert runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False and runtime['preparation']['runtime_ready'] is False
candidate.update(status='ROOT_REVIEWED',at=now,review_evidence=ev,review_scope='Owning root static source semantics and current runtime binding review only; no live instance, physical gain, full graph or release certification.',reviewer='owning_root_coordinator_turn001775',independent_review_claimed=False)
cpr=save('controller-semantics.root-reviewed-disabled-v1.json',candidate)
cn=extract('scripts/qd_ed_n34_controller.py',{'FIELDS','verify_semantics'},dict(base,w=w));assert cn['verify_semantics'](cpr,graph['runtime'],closure)==candidate
result=save('scoped-review-result-v1.json',dict(schema='n36-root-scoped-recovery-controller-review-v1',at=now,status='PASS_SCOPED_STATIC_ONLY',recovery_review=review,recovery_reconciliation=terminal,recovery_prefix_contract=cr,specification=sr,controller_semantics=cpr,source=commit,checks=['production _recovery_capture retained both consumed predecessors and empty successor','production _recovery_contract accepts actual root reconciliation','production verify_semantics accepts current static source/runtime binding'],graph_complete=False,native_execution_observed=False,independent_review_claimed=False,release_enabled=False,scientific_promotion=False))
for name,r in ledgers.items():assert ref(r['path'])['sha256']==r['sha256']
next_step='Compose the affected disabled downstream graph using turn001775 scoped-review-result-v1.json (root-reviewed recovery contract/specification/controller) and turn001771 unchanged runtime/closure/source/policy. Run focused production graph consumers and required independent graph review before readiness/release. Do not replay either consumed preparation identity.'
with open(W/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 import yaml
 statepath=W/'research-state.yaml';cp=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
 for p,is_yaml in [(statepath,True),(cp,False)]:
  obj=yaml.safe_load(p.read_text()) if is_yaml else read(p)
  obj['n36_fresh_recovery_scoped_root_review']=result;obj['next_action']=next_step
  tmp=p.with_name(p.name+'.turn001775.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
summary=dict(schema='autonomy-operational-summary-v1',turn=1775,at=now,current_source=dict(worktree=str(ROOT),commit=commit,tracked_clean=True),owning_source=prior['owning_source'],scientific_source=prior['scientific_source'],live_handles=handles,controller_status='NO_LIVE_GPU_COHORT; historical preparations terminal, no dispatch',ledger_prefixes=ledgers,completed_work=['Reconciled successful previous source-placement turn and verified live driver/coordinator identity.','Reviewed retained raw predecessor accounting and exact controller source semantics.','Recorded genuine root static review/reconciliation and disabled bindings; exact production static consumers pass.'],scoped_review=result,next_bounded_step=next_step,unresolved_evidence=['Full disabled graph composition and independent graph review pending.','Native readiness, scientific promotion, original validation/formal/required ablations remain unproven.'],deadline_utc=a['stop_authority']['deadline'],stop_present=False,deadline_passed=False,gpu_dispatches=0,provider_calls=0,target_met=False)
p=save('operational-summary-v1.json',summary);(O/'operational-summary-v1.sha256').write_text(p['sha256']+'  operational-summary-v1.json\n');print(json.dumps(dict(result=result,summary=p,next_step=next_step)))
