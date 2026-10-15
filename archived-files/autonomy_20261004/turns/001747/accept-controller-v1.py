import pathlib,json,hashlib,datetime,subprocess,fcntl,os,yaml,copy
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001747';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator';R=A/'turns/001744/independent-controller-review'
def read(p):return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify(r):
 a=ref(pathlib.Path(r['path']));assert a['sha256']==r['sha256'];assert 'bytes' not in r or r['bytes']==a['bytes'];return a
def put(p,d,atomic=False,y=False):
 b=yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if y else json.dumps(d,indent=2)+'\n'
 if atomic:
  q=p.with_name(p.name+'.tmp-001747');q.write_text(b);os.replace(q,p)
 else:
  with p.open('x') as f:f.write(b)
now=datetime.datetime.now(datetime.timezone.utc);prev=read(A/'turns/001746/operational-summary-v1.json');assert now<datetime.datetime.fromisoformat(prev['deadline_utc'].replace('Z','+00:00')) and not (A/'STOP').exists()
for r in prev['ledger_prefixes'].values():verify(r)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def observe(h):
 h=copy.deepcopy(h);p=pathlib.Path('/proc',str(h['pid']),'stat');a=p.read_text().rsplit(')',1)[1].split() if p.exists() else None
 h.update(alive=bool(a and int(a[19])==h['start_ticks'] and boot==h['boot_id'] and a[0]!='Z'),state=a[0] if a else None);return h
D=read(A/'driver-status.json');handles={k:observe(D[v]) for k,v in [('driver','driver'),('coordinator','process')]};assert all(h['alive'] for h in handles.values())
for k,h in read(R/'process-v1.json').items():
 if isinstance(h,dict) and 'pid' in h:handles['review_'+k]=observe(h);assert not handles['review_'+k]['alive']
ex=read(R/'exit-v1.json');assert ex['exit']==0 and not ex['timeout']
rv=read(R/'review-v1.json');assert rv['status']=='PASS_SCOPED_STATIC_BINDINGS' and not rv['decision']['blocking_findings_within_scope']
checks=[]
def walk(v):
 if isinstance(v,dict):
  if isinstance(v.get('path'),str) and 'sha256' in v:checks.append(verify(v));return
  for x in v.values():walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
walk(rv['references']);walk(read(R/'file-manifest-v1.json'))
src=rv['source'];assert subprocess.check_output(['git','-C',src['worktree'],'rev-parse','HEAD'],text=True).strip()==src['commit'];assert not subprocess.check_output(['git','-C',src['worktree'],'status','--porcelain','--untracked-files=no'],text=True).strip()
p=pathlib.Path(rv['references']['controller_proposal']['path']);proposal=read(p);closure=read(pathlib.Path(proposal['runtime_closure']['path']));assert closure['modules'][proposal['module']]==proposal['source'];assert closure['runtime']==proposal['runtime']
scope='Owning-root acceptance of independently reviewed static controller semantics and exact final source/runtime/closure bindings only. No live instance, physical gain, whole-graph attestation, measured readiness, B5, release or scientific promotion.'
binding=dict(reviewer='owning_root_coordinator_turn001747',independent_review=ref(R/'review-v1.json'),current_source=src,scope=scope)
evidence={}
for k,r in proposal['review_evidence'].items():
 verify(r);e=read(pathlib.Path(r['path']));assert e['runtime']==proposal['runtime'] and e['runtime_closure']==proposal['runtime_closure'] and e['source_commit']==src['commit']
 for z in e['sources']:checks.append(verify(z))
 e.update(status='ROOT_REVIEWED',at=now.isoformat(),review_scope=scope,root_binding_attestation=dict(binding,proposal=r),native_execution_observed=False,physical_gain_certified=False,gpu_authorized=False,release_enabled=False,scientific_promotion=False,readiness_eligible=False,production_eligible=False)
 f=T/(k+'-root-reviewed-v1.json');put(f,e);evidence[k]={a:b for a,b in ref(f).items() if a!='bytes'}
proposal.update(status='ROOT_REVIEWED',at=now.isoformat(),scope=scope,review_scope=scope,root_binding_attestation=dict(binding,proposal=ref(p)),review_evidence=evidence,instance_scope='Expected configuration only; no live instance observed',native_execution_observed=False,readiness_eligible=False,production_eligible=False,release_enabled=False)
put(T/'controller-semantics.root-reviewed-v1.json',proposal)
att=dict(schema='n36-root-controller-binding-attestation-v1',at=now.isoformat(),status='PASS_SCOPED',authority=ref(A/'user-authorization-v1.json'),independent_review=ref(R/'review-v1.json'),current_source=src,source_record=rv['references']['source_record'],controller=ref(T/'controller-semantics.root-reviewed-v1.json'),runtime=proposal['runtime'],runtime_closure=proposal['runtime_closure'],verified_references=checks,scope=scope,retained_limitations=rv['limitations'],gpu_authorized=False,release_enabled=False,target_met=False)
put(T/'root-controller-binding-attestation-v1.json',att)
terminal=dict(schema='independent-review-terminal-reconciliation-v1',at=now.isoformat(),review=ref(R/'review-v1.json'),exit=ref(R/'exit-v1.json'),process=ref(R/'process-v1.json'),live_handles=[],review_decision=rv['status'],ledger_prefixes=prev['ledger_prefixes'],gpu_authorized=False)
put(T/'terminal-reconciliation-v1.json',terminal)
nextstep='Compose fresh disabled all40 audit plus separate engineering manifest using turn001747 root-reviewed controller/evidence, source 89506fe and turn001730 recovery identity/prefix. Preserve existing artifacts. Frozen=True is allowed only for immutable audit-only snapshot with execution flags false (turn001743 diagnosis). Run unchanged graph validators; independent B5, root accounting/adoption, fresh measured readiness and distinct health/episode releases remain required.'
summary=dict(prev,turn=1747,at=now.isoformat(),live_handles=handles,controller_status='Independent CPU review terminal and scoped root acceptance recorded; no live GPU worker.',review=dict(status='TERMINAL_SCOPED_ROOT_ACCEPTED',review=ref(R/'review-v1.json')),root_controller_acceptance=ref(T/'root-controller-binding-attestation-v1.json'),terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),completed_work=['Verified bound authority, driver/coordinator identities, terminal reviewer and unchanged owning ledger prefixes.','Verified final source and direct review/manifest/controller/source hashes; accepted scoped static bindings with all limitations retained.','Created new controller/evidence acceptance artifacts; reconciled owning state/checkpoint/tree. No dispatch or source/science/budget/ledger changes.'],next_bounded_step=nextstep,unresolved_evidence=['Fresh complete graph and unchanged validators remain pending.','Independent B5, root accounting/adoption and fresh measured readiness remain pending.','Original validation/formal/required ablation evidence remains incomplete.'])
put(T/'operational-summary-v1.json',summary)
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 for r in prev['ledger_prefixes'].values():verify(r)
 for f,y in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(f.read_text()) if y else read(f);v=d['n36_final_controller_independent_review'];v.update(status='TERMINAL_SCOPED_ROOT_ACCEPTED',review=ref(R/'review-v1.json'),terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),live_handles=[])
  for k in ['wrapper','executor']:
   if k in v:v[k].update(alive=False,identity_verified=False)
  d['n36_final_root_controller_acceptance']=ref(T/'root-controller-binding-attestation-v1.json');d['next_action']=nextstep;d['latest_operational_summary']=ref(T/'operational-summary-v1.json');d['last_updated_utc']=now.isoformat();put(f,d,True,y)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='FINAL_CONTROLLER_SCOPED_ROOT_ACCEPTED_GRAPH_COMPOSITION_PENDING',insight=nextstep,final_controller_acceptance=ref(T/'root-controller-binding-attestation-v1.json'));put(C/'idea_tree.json',tree,True)
(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps(dict(status='SCOPED_ACCEPTANCE_RECORDED',verified_references=len(checks),summary=ref(T/'operational-summary-v1.json'))))
