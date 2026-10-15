import ast,copy,datetime,fcntl,hashlib,json,math,os,pathlib,subprocess,types,yaml
P=pathlib.Path; W=P.cwd(); O=W.parent/'autonomy_20261004/turns/001783'; B=O.parent/'001779/canonical-path-rebinding'
ROOT=P('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
def ref(p):
 p=P(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(r):
 if isinstance(r,dict):
  assert ref(r['path'])['sha256']==r['sha256'];r=r['path']
 return json.loads(P(r).read_text())
def save(n,x):
 p=O/n;assert not p.exists();p.write_text(json.dumps(x,indent=2)+'\n');return ref(p)
def ident(x):
 p=P('/proc')/str(x['pid'])/'stat'
 if not p.exists():return dict(pid=x['pid'],alive=False,identity_verified=False)
 a=p.read_text().rsplit(')',1)[1].split();boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
 return dict(pid=x['pid'],start_ticks=int(a[19]),boot_id=boot,state=a[0],alive=a[0]!='Z',identity_verified=a[0]!='Z' and int(a[19])==x['start_ticks'] and boot==x['boot_id'])
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); prior=read(O.parent/'001782/operational-summary-v1.json'); authority=read(B/'authority-v1.json')
assert now < authority['stop_authority']['deadline'];assert all(not os.path.lexists(p) for p in authority['stop_authority']['paths'])
d=read(O.parent.parent/'driver-status.json');handles={k:ident(d[k]) for k in ['driver','process']};assert all(x['identity_verified'] for x in handles.values())
terminal={k:ident(v) for k,v in read(B/'process-v1.json').items() if k in ['wrapper','executor']};assert all(not x['identity_verified'] for x in terminal.values());assert read(B/'exit-v1.json')['exit']==0
for v in prior['ledger_prefixes'].values():assert ref(v['path'])['sha256']==v['sha256']
commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip();assert commit==prior['current_source']['commit'];assert not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True).strip()
c=read(B/'controller-semantics.prospective-disabled-v1.json');old=read(c['historical_review']);r=read(c['runtime']);ro=read(old['runtime']);cl=read(c['runtime_closure']);clo=read(old['runtime_closure'])
def delta(a,b):return sorted(k for k in a.keys()|b.keys() if a.get(k)!=b.get(k))
assert delta(r,ro)==['preparation'];assert delta(cl,clo)==['runtime'];assert cl['runtime']==c['runtime'];assert r['preparation']['source']==commit
assert {k:v for k,v in r['preparation'].items() if k!='source_record'}=={k:v for k,v in ro['preparation'].items() if k!='source_record'}
assert read(r['preparation']['source_record'])==read(ro['preparation']['source_record'])
for k in ['source_commit','source','instance','semantics','review_evidence']:assert c[k]==old[k]
assert not r['provider_ready'] and not r['cuda_egl_verified'] and not r['preparation']['runtime_ready'] and not r['preparation']['release_enabled']
assert ref(c['source']['path'])==c['source']==cl['modules'][c['module']]
verified=[];ev={}
for k,v in c['review_evidence'].items():
 e=read(v);assert e['runtime']==old['runtime'] and not e['fixture_only'];assert e['source_commit']==commit
 for s in e['sources']:
  assert ref(s['path'])==s;verified.append(s)
 e.update(at=now,runtime=c['runtime'],runtime_closure=c['runtime_closure'],prior_review=v,reviewer='owning_root_coordinator_turn001783',review_scope='Exact source hashes and prior accepted findings unchanged; runtime differs only in source-record lexical path, whose contents are identical. Static current-binding acceptance only; no native, graph or release claim.')
 ev[k]=save(k+'-root-reviewed-v1.json',e)
c.update(status='ROOT_REVIEWED',at=now,review_evidence=ev,reviewer='owning_root_coordinator_turn001783',review_scope='Scoped static source/runtime/closure binding acceptance. Independent of artifact author; no independent whole-graph review, native readiness or release claimed.')
cr=save('controller-semantics.root-reviewed-disabled-v1.json',c)
# Run exact pure definitions from current production source without native imports.
def extract(file,names,ns):
 p=ROOT/file;nodes=[n for n in ast.parse(p.read_bytes()).body if (isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names) or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets))];exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns);return ns
base=dict(Path=P,json=json,hashlib=hashlib,math=math)
wn=extract('scripts/qd_ed_n23_worker.py',{'require','sha','canonical_sha','read_ref'},base.copy());w=types.SimpleNamespace(**wn)
ns=extract('scripts/qd_ed_n34_controller.py',{'FIELDS','verify_semantics'},dict(base,w=w));assert ns['verify_semantics'](cr,c['runtime'],cl)==c
failed=False
try:ns['verify_semantics'](c['historical_review'],c['runtime'],cl)
except Exception:failed=True
assert failed
result=save('root-controller-binding-attestation-v1.json',dict(schema='n36-root-controller-binding-attestation-v1',at=now,status='PASS_SCOPED_STATIC_BINDINGS',current_source=prior['current_source'],candidate=ref(B/'controller-semantics.prospective-disabled-v1.json'),controller=cr,runtime=c['runtime'],runtime_closure=c['runtime_closure'],prior_review=c['historical_review'],verified_source_references=verified,binding_delta={'runtime':['preparation.source_record.path'],'source_record_contents_identical':True,'closure':['runtime'],'source_instance_semantics_unchanged':True},checks=['Exact current production verify_semantics passes new reviewed binding','Prior binding rejected against current runtime','Exact current deployed source hashes match accepted source review','All private ledger prefixes unchanged'],scope='Static binding review only; no full source inventory or closure rescan; prior accepted unchanged source findings retained.',gpu_authorized=False,release_enabled=False,native_execution_observed=False,scientific_promotion=False,target_met=False))
next_step='Use turn001783 root-controller-binding-attestation-v1.json and controller-semantics.root-reviewed-disabled-v1.json to refresh affected turn001779 disabled graph references. Run focused production verify_graph admission, then independent B5 before readiness/accounting adoption or release. Preserve both consumed preparation identities and all charges; do not rebuild unaffected provenance or rerun all41 manifest checks unless affected.'
for v in prior['ledger_prefixes'].values():assert ref(v['path'])['sha256']==v['sha256']
with open(W/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,isyaml in [(W/'research-state.yaml',True),(W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  obj=yaml.safe_load(p.read_text()) if isyaml else read(p);obj['n36_canonical_controller_root_acceptance']=result;obj['next_action']=next_step
  tmp=p.with_name(p.name+'.turn001783.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False,allow_unicode=True) if isyaml else json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
summary=dict(prior,turn=1783,at=now,live_handles=handles,prior_executor_handles=terminal,controller_status='No active cohort; canonical controller static binding accepted; complete graph admission/B5 pending',completed_work=['Verified driver/coordinator boot/start identities, terminal prior executor, STOP/deadline and unchanged owning ledgers.','Independently checked exact current runtime delta: source-record lexical path only, identical content; closure changed runtime reference only.','Verified unchanged deployed controller evidence and produced scoped root binding attestation; exact production semantic consumer passes, stale binding is rejected.'],next_bounded_step=next_step,unresolved_evidence=['Affected graph references and focused admission need refresh; independent B5 pending.','Native readiness, scientific promotion, validation/formal and required ablations remain unproven.'],root_controller_acceptance=result)
summary.pop('terminal_reconciliation',None);sr=save('operational-summary-v1.json',summary);(O/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n');print(json.dumps({'review':result,'summary':sr,'next_step':next_step}))
