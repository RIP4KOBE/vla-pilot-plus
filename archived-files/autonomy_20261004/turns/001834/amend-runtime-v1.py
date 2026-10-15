import pathlib,json,hashlib,copy,datetime,subprocess,fcntl,os,yaml
P=pathlib.Path; W=P.cwd(); B=(W/'../autonomy_20261004').resolve();T=B/'turns';O=T/'001834'
def read(p):return json.loads(P(p).read_text())
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(P(p).read_bytes()).hexdigest())
def save(n,d):
 p=O/n;assert not p.exists();p.write_text(json.dumps(d,sort_keys=True,separators=(',',':')));return ref(p)
prior=read(T/'001833/operational-summary-v1.json');driver=read(B/'driver-status.json');now=datetime.datetime.now(datetime.timezone.utc).isoformat();assert now<'2026-10-11T11:13:13+00:00';assert not (B/'STOP').exists() and not (B/'STOP.json').exists();assert read(T/'001833/receipt.json')['exit']==0
handles={};boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
for k,x in [('driver',driver['driver']),('coordinator',driver['process'])]:
 a=(P('/proc')/str(x['pid'])/'stat').read_text().rsplit(')',1)[1].split();assert boot==x['boot_id'] and int(a[19])==x['start_ticks'];handles[k]={**x,'state':a[0],'identity_verified':True}
for r in prior['ledger_prefixes'].values():assert P(r['path']).stat().st_size==r['bytes'] and ref(r['path'])['sha256']==r['sha256']
root=P(prior['current_source']['worktree']);assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==prior['current_source']['commit'];assert not subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True).strip()
spec=read(T/'001831/specification.root-reconciled-disabled-v3.json');oldref=spec['canonical_runtime'];assert ref(oldref['path'])['sha256']==oldref['sha256'];old=read(oldref['path']);new=copy.deepcopy(old)
g=read(T/'001827/disabled-v3-binding/graph.candidate-disabled-v3.json');source=read(g['source_record']['path']);sr=next(x for x in source['files'] if x['path']=='scripts/qd_ed_n36_source.py');row=next(x for x in new['files'] if x['path']==str(root/'scripts/qd_ed_n36_source.py'));before=copy.deepcopy(row);actual=root/'scripts/qd_ed_n36_source.py';assert ref(actual)['sha256']==sr['sha256'];row.update(sha256=sr['sha256'],size_bytes=actual.stat().st_size)
assert sum(a!=b for a,b in zip(old['files'],new['files']))==1
am=save('prospective-runtime-inventory-amendment-v1.json',dict(schema='n36-prospective-runtime-inventory-amendment-v1',at=now,authority=ref(B/'user-authorization-v1.json'),diagnosis=ref(T/'001833/runtime-binding-diagnosis-v1.json'),source=prior['current_source'],old_canonical_runtime=oldref,change={'before':before,'after':row},scope='Only canonical inventory hash and size for already reviewed source. Old canonical baseline remains intact. Derived graph still requires rebinding and production admission.',additional_attempts=0,additional_gpu_hours=0,budget_arithmetic='507 + 0 = 507 attempts; existing charged GPU hours + 0; protected reserves unchanged',ledger_prefixes=prior['ledger_prefixes'],scientific_changes=False,release_enabled=False,gpu_authorized=False))
nr=save('runtime.canonical.prospective-disabled-v2.json',new)
# Verify every inventory fingerprint without opening prohibited credential or protected content.
mismatches=[]
for r in new['files']:
 p=P(r['path']);assert '2026-08-10' not in str(p) and not ('poe' in p.name.lower() and p.name!='qd_ed_poe_launch.py')
 if ref(p)['sha256']!=r['sha256'] or ('size_bytes' in r and p.stat().st_size!=r['size_bytes']):mismatches.append(str(p))
assert not mismatches
vr=save('inventory-verification-v1.json',dict(schema='n36-runtime-inventory-verification-v1',status='PASS_EXACT_ONE_FILE_AMENDMENT',amendment=am,old_runtime=oldref,new_runtime=nr,inventory_entries=len(new['files']),mismatches=mismatches,source_unchanged=True,graph_verified=False,gpu_authorized=False))
next_step='Use turn001834 prospective-runtime-inventory-amendment-v1.json and verified runtime.canonical.prospective-disabled-v2.json to rebind specification/derived runtime/closure/controller references in new disabled artifacts only. Continue turn001833 compose-graph-v2.py with those bindings, production manifest constructors and verify_graph. Preserve prior reviews as historical evidence, obtain any required scoped acceptance for changed bindings; no broad test repeats or predecessor re-reconciliation. Finite release/native readiness and scientific promotion still pending.'
record=dict(status='CANONICAL_INVENTORY_AMENDED_VERIFIED_DERIVED_GRAPH_PENDING',source=prior['current_source']['commit'],amendment=am,canonical_runtime=nr,verification=vr,gpu_authorized=False,at=now)
with (W/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for p,isy in [(W/'research-state.yaml',True),(W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isy else read(p);d['n36_prospective_canonical_inventory_amendment']=record;d['next_action']=next_step;q=p.with_name(p.name+'.turn001834.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if isy else json.dumps(d,indent=2)+'\n');os.replace(q,p)
for r in prior['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256']
summary={**prior,'turn':1834,'at':now,'live_handles':handles,'controller_status':'NO_LIVE_OWNING_GPU_COHORT; CANONICAL_INVENTORY_VERIFIED_DERIVED_GRAPH_PENDING','completed_work':['Verified driver/coordinator identities, prior normal exit, owning state and unchanged four private ledger prefixes.','Recorded prospective zero-resource amendment for the exact stale source hash and size.','Verified all canonical runtime inventory fingerprints; source and original baseline unchanged.'],'next_bounded_step':next_step,'unresolved_evidence':['Derived disabled graph binding and production admission','Finite resource release and native readiness','Pre-existing parity failure retained','Original validation/formal/required ablation completion remains unevidenced'],'amendment':record};summary.pop('diagnosis',None)
r=save('operational-summary-v1.json',summary);(O/'operational-summary-v1.sha256').write_text(r['sha256']+'  operational-summary-v1.json\n');print(json.dumps({'summary':r,'verification':vr,'entries':len(new['files'])}))
