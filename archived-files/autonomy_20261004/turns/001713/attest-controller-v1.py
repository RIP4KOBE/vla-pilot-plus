import pathlib,json,hashlib,datetime,subprocess,fcntl,os,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001713';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify(r):
 a=ref(pathlib.Path(r['path']));assert a['sha256']==r['sha256'];assert 'bytes' not in r or a['bytes']==r['bytes'];return a
def put(p,d):
 q=p.with_name(p.name+'.tmp-001713');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
now=datetime.datetime.now(datetime.timezone.utc);old=read(A/'turns/001712/operational-summary-v1.json');assert now < datetime.datetime.fromisoformat(old['deadline_utc'].replace('Z','+00:00'));assert not (A/'STOP').exists()
for r in old['ledger_prefixes'].values():verify(r)
R=A/'turns/001711/independent-graph-review/review-v1.json';review=read(R);assert review['decision']=='PASS_STATIC_GRAPH_REVIEW_ROOT_ATTESTATION_PENDING' and not review['defects'] and review['root_can_accept_static_semantics']
exitpath=R.parent/'exit-v1.json';ex=read(exitpath);assert ex['exit']==0 and not ex['timeout']
for pid in [3084027,3084028]:assert not pathlib.Path('/proc',str(pid)).exists()
for r in review['artifact_and_source_hashes']:verify(r)
verify(review['check_evidence']);verify(review['graph_report']);verify(review['outputs_manifest'])
source=review['source'];assert subprocess.check_output(['git','-C',source['worktree'],'rev-parse','HEAD'],text=True).strip()==source['commit'];assert not subprocess.check_output(['git','-C',source['worktree'],'status','--porcelain','--untracked-files=no'],text=True).strip()
p=pathlib.Path(review['graph']['controller_semantics']['path']);proposal=read(p);closure=read(pathlib.Path(proposal['runtime_closure']['path']));assert closure['modules'][proposal['module']]==proposal['source']
scope='Root acceptance of static controller source semantics and exact current source/runtime/closure bindings, supported by independent PASS_SCOPED review. No measured instance, physical gain, native readiness, complete graph acceptance, release or scientific promotion.'
evidence={};checks=[]
for kind,r in proposal['review_evidence'].items():
 verify(r);d=read(pathlib.Path(r['path']));checks.extend(verify(s) for s in d['sources']);assert d['runtime']==proposal['runtime'] and d['runtime_closure']==proposal['runtime_closure']
 d.update(native_execution_observed=False,physical_gain_certified=False,scientific_promotion=False,gpu_authorized=False,readiness_eligible=False,production_eligible=False,status='ROOT_REVIEWED',at=now.isoformat(),historical_source_commit=d['source_commit'],source_commit=source['commit'],review_scope=scope,root_binding_attestation=dict(reviewer='owning_root_coordinator_turn001713',proposal=r,independent_review=ref(R),current_source=source,scope=scope),release_enabled=False)
 out=T/(kind+'-root-reviewed-v1.json');put(out,d);evidence[kind]={k:v for k,v in ref(out).items() if k!='bytes'}
proposal.update(instance_scope='Expected configuration only; no live instance observed',native_execution_observed=False,readiness_eligible=False,production_eligible=False,status='ROOT_REVIEWED',at=now.isoformat(),historical_source_commit=proposal['source_commit'],source_commit=source['commit'],review_scope=scope,scope=scope,review_evidence=evidence,root_binding_attestation=dict(reviewer='owning_root_coordinator_turn001713',proposal=ref(p),independent_review=ref(R),current_source=source,scope=scope),release_enabled=False)
put(T/'controller-semantics.root-reviewed-v1.json',proposal)
att=dict(schema='n36-root-controller-binding-attestation-v1',at=now.isoformat(),status='PASS_SCOPED',authority=ref(A/'user-authorization-v1.json'),independent_review=ref(R),current_source=source,controller=ref(T/'controller-semantics.root-reviewed-v1.json'),runtime=proposal['runtime'],runtime_closure=proposal['runtime_closure'],source_checks=checks,scope=scope,retained_limitations=review['scope_limits'],gpu_authorized=False,release_enabled=False,target_met=False)
put(T/'root-controller-binding-attestation-v1.json',att)
terminal=dict(schema='independent-review-terminal-reconciliation-v1',at=now.isoformat(),review=ref(R),exit=ref(exitpath),process=ref(R.parent/'process-v1.json'),handles_absent=True,review_decision=review['decision'],effects=review['effects'],ledger_prefixes=old['ledger_prefixes'],gpu_authorized=False)
put(T/'terminal-reconciliation-v1.json',terminal)
nextstep='Refresh only affected disabled graph consumers/manifests to turn001713 root-reviewed controller and evidence; preserve old artifacts, scientific plan and validators. Run unchanged verify_graph on exact refreshed bindings. Then separately authorize finite source-bound readiness measurement; measured runtime/native acceptance, B5, source/accounting adoption and distinct fresh health/episode releases remain pending.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in old['ledger_prefixes'].values():verify(r)
 for f,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(f.read_text()) if isyaml else read(f);d['in_flight_executor']=None;d['n36_engineering_r1_preparation_accounting_independent_graph_review']={'status':'COMPLETED_STATIC_ACCEPTED','review':ref(R),'terminal_reconciliation':ref(T/'terminal-reconciliation-v1.json')};d['n36_engineering_r1_root_controller_acceptance']=ref(T/'root-controller-binding-attestation-v1.json');d['next_action']=nextstep;d['updated_at']=now.isoformat()
  if isyaml:
   q=f.with_name(f.name+'.tmp-001713');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,f)
  else:put(f,d)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='R1_CONTROLLER_ROOT_ACCEPTED_DISABLED_CONSUMER_REFRESH_PENDING',insight=scope+' '+nextstep);put(C/'idea_tree.json',tree)
driver=read(A/'driver-status.json');boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 d=driver[k];a=pathlib.Path('/proc',str(d['pid']),'stat').read_text().rsplit(')',1)[1].split();assert d['boot_id']==boot and int(a[19])==d['start_ticks'];d['observed_state']=a[0]
old.update(turn=1713,at=now.isoformat(),driver_status=driver,completed_work=['Verified handoff/authority, driver/coordinator boot/start identity and unchanged owning ledger prefixes; prior review processes and historical N31 handles absent.','Verified independent PASS_SCOPED review, exact graph and current graph and controller source hashes; inspected action scaling, goal update and gripper semantics.','Recorded narrow root controller/evidence acceptance bound to d322548 source and unchanged runtime/closure; updated owning state/checkpoint/tree.'],root_controller_acceptance=ref(T/'root-controller-binding-attestation-v1.json'),next_bounded_step=nextstep,unresolved_evidence=['Affected disabled graph must be refreshed and pass unchanged verify_graph.','Finite readiness measurement and independently accepted native evidence, B5 and separate production release gates remain pending.','Original validation/formal/required ablation goal remains unmet.'])
old.update(live_executor_handles={},executor=None,executor_exit_present=True,terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'));put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps({'status':'ROOT_CONTROLLER_ACCEPTED_SCOPED','source_checks':len(checks),'next_action':nextstep}))
