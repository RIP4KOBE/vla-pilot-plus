import pathlib,json,hashlib,datetime,subprocess,os,sys,fcntl,yaml,copy
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001863';job=base/'turns/001859/successor-disabled-composition'
def ref(p):
 p=P(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(r):
 p=P(r['path']);assert ref(p)['sha256']==r['sha256'],str(p);return json.loads(p.read_text())
def write(n,d):
 p=out/n
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
 return ref(p)
boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def live(h):
 p=P('/proc')/str(h['pid'])/'stat'
 if not p.exists():return dict(h,alive=False,state='absent',identity_verified=False)
 s=p.read_text().rsplit(')',1)[1].split();ok=h.get('boot_id')==boot and int(h.get('start_ticks',h.get('proc_start_ticks',-1)))==int(s[19]);return dict(h,alive=ok and s[0]!='Z',identity_verified=ok,state=s[0])
prev=json.loads((base/'turns/001862/operational-summary-v1.json').read_text());driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1863
handles={k:live(driver[k]) for k in ('driver','process')};assert all(h['alive'] for h in handles.values());assert not (base/'STOP').exists()
now=datetime.datetime.now(datetime.timezone.utc).isoformat();assert now<'2026-10-11T11:13:13'
source=prev['current_source'];wt=P(source['worktree']);assert subprocess.check_output(['git','-C',str(wt),'rev-parse','HEAD'],text=True).strip()==source['commit']
for r in prev['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
pending_ref=ref(job/'controller-semantics.pending-disabled-v1.json');pending=read(pending_ref);old=read(pending['historical_review_only']);accept=read(old['root_acceptance']);assert accept['status']=='PASS_STATIC_DEPLOYED_SOURCE_SEMANTICS'
a=read(pending['runtime']);b=read(old['runtime']);assert {k:v for k,v in a.items() if k!='preparation'}=={k:v for k,v in b.items() if k!='preparation'}
ap=a['preparation'];bp=b['preparation'];assert {k:v for k,v in ap.items() if k!='source_record'}=={k:v for k,v in bp.items() if k!='source_record'};assert read(ap['source_record'])==read(bp['source_record']);assert ap['source_record']['sha256']==bp['source_record']['sha256']
c=read(pending['runtime_closure']);oc=read(old['runtime_closure']);assert c['runtime']==pending['runtime'];assert {k:v for k,v in c.items() if k!='runtime'}=={k:v for k,v in oc.items() if k!='runtime'}
for k in ['source','source_commit','instance','semantics','module','class']:assert pending[k]==old[k]
assert pending['source_commit']==source['commit'];verified=[];evidence={}
for k,r in old['review_evidence'].items():
 e=read(r);assert e['runtime']==old['runtime'] and e['runtime_closure']==old['runtime_closure'];assert e['status']=='ROOT_REVIEWED'
 for sr in e['sources']:
  assert ref(sr['path'])==sr;verified.append(sr)
 e.update(at=now,reviewer='owning_root_coordinator_turn001863',historical_review=r,runtime=pending['runtime'],runtime_closure=pending['runtime_closure'],review_scope='Scoped binding-equivalence review: historical reviewed source bytes and expected instance unchanged; only byte-identical source-record path and consequent runtime reference changed. No live instance, gain, full closure admission, readiness or execution claim.')
 evidence[k]=write(k+'-binding-reviewed-v1.json',e)
review=write('controller-binding-owner-review-v1.json',dict(schema='n36-controller-scoped-root-acceptance-v1',at=now,status='PASS_STATIC_CONTROLLER_BINDING_EQUIVALENCE',reviewer='owning_root_coordinator_turn001863',source=source['commit'],pending=pending_ref,prior=pending['historical_review_only'],runtime=pending['runtime'],runtime_closure=pending['runtime_closure'],evidence=evidence,verified_source_files=verified,changes=['runtime.preparation.source_record path changed; bytes and SHA256 identical','runtime closure runtime reference updated; every other closure field identical'],checks=['All non-preparation runtime fields identical','Only preparation source-record reference differs','Source record contents identical','All controller fields and seven source file hashes unchanged','Historical acceptance verified'],scope='Static source semantics binding only. Reuses reviewed unchanged source within its existing scope; no full graph/native/readiness acceptance.',gpu_authorized=False,release_enabled=False,readiness_eligible=False,native_execution_observed=False,physical_gain_certified=False,independent_review_claimed=False))
proof=copy.deepcopy(pending);proof.update(status='ROOT_REVIEWED',review_evidence=evidence,root_acceptance=review);proof_ref=write('controller-semantics.root-reviewed-disabled-v1.json',proof)
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True;sys.path.insert(0,str(wt))
from scripts.qd_ed_n34_controller import verify_semantics
assert verify_semantics(proof_ref,pending['runtime'],c)==proof
validation=write('controller-validator-result-v1.json',dict(at=now,status='PASS',validator='scripts.qd_ed_n34_controller.verify_semantics',source=source['commit'],proof=proof_ref,review=review,gpu_authorized=False,full_graph_verified=False))
# Recheck all recorded owning controller/worker identities without consuming any results.
s=yaml.safe_load((root/'research-state.yaml').read_text());cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';checkpoint=json.loads(cp.read_text());known={}
def walk(v):
 if isinstance(v,dict):
  if isinstance(v.get('pid'),int) and v.get('boot_id') and ('start_ticks' in v or 'proc_start_ticks' in v):
   h=live(v);known[(v['pid'],str(v.get('start_ticks',v.get('proc_start_ticks'))))]={k:h.get(k) for k in ['pid','boot_id','start_ticks','proc_start_ticks','state','alive','identity_verified']}
  for x in v.values():walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
walk(s);walk(checkpoint)
others=[h for h in known.values() if h['alive'] and h['pid'] not in [x['pid'] for x in handles.values()]];assert not others,others
reconciliation=write('live-reconciliation-v1.json',dict(at=now,driver_handles=handles,owning_recorded_handle_count=len(known),other_live_handles=others,terminal_handle_identities=list(known.values()),ledger_prefixes=prev['ledger_prefixes'],prior_summary=ref(base/'turns/001862/operational-summary-v1.json')))
next_step='Compose fresh disabled graph using turn001862 predecessor owner review/reconciliation and turn001863 ROOT_REVIEWED controller proof. Rebind dependent specification, plan and all41 manifests; run exact production graph admission. No renewed predecessor/source review needed unless bytes change. Fresh readiness/accounting/release and independent review remain gated; deadline 2026-10-11T11:13:13Z.'
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1863,current_source=source,owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,cpu_operation_handles=[],controller_status='NO_LIVE_EXPERIMENT_CONTROLLER_CONTROLLER_BINDING_REVIEW_PASS',ledger_prefixes=prev['ledger_prefixes'],ledgers_unchanged=True,completed_work=['Verified handoff and authorization hashes, driver identities, ACTIVE isolation and unchanged private ledger prefixes.','Verified successor runtime differs only by byte-identical source-record relocation; closure differs only by runtime reference.','Reverified seven reviewed source hashes and preserved expected-instance limits; wrote scoped owner review and new disabled controller proof.','Exact production verify_semantics passed; no benchmark source edits or GPU dispatch.'],review=review,controller_proof=proof_ref,validation=validation,terminal_reconciliation=reconciliation,next_bounded_step=next_step,unresolved_evidence=['Dependent graph/manifests admission','Fresh readiness/accounting/release and independent review','Valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=False,deadline='2026-10-11T11:13:13Z')
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in prev['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
 sr=write('operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
 record=dict(status='PASS_STATIC_BINDING_REVIEW_PRODUCTION_VALIDATOR_NOT_GRAPH_ADOPTED',at=now,review=review,controller_proof=proof_ref,validation=validation,gpu_authorized=False)
 for p,isyaml in [(root/'research-state.yaml',True),(cp,False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());d['n36_successor_controller_binding_owner_review']=record;d['latest_operational_summary']=sr;d['next_action']=next_step;d['updated_at']=now;t=p.with_name(p.name+'.001863.tmp');t.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(t,p)
print(json.dumps(dict(review=review,controller_proof=proof_ref,validation=validation,summary=sr)))
