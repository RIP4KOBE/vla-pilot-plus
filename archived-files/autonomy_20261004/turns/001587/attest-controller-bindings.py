import json,pathlib,hashlib,datetime,os,fcntl,yaml,subprocess
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001587'; P=A/'turns/001584/runtime-graph-refresh'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p): return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify(r):
 a=ref(pathlib.Path(r['path']));assert all(a[k]==v for k,v in r.items() if k in a);return a
def put(p,d):
 q=p.with_name(p.name+'.tmp-001587');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
now=datetime.datetime.now(datetime.timezone.utc); old=read(A/'turns/001586/operational-summary-v1.json')
assert now < datetime.datetime.fromisoformat(old['deadline'].replace('Z','+00:00')) and not (A/'STOP').exists()
for r in old['ledger_prefixes'].values():verify(r)
proposal=read(P/'controller-semantics.proposed-v1.json');verify(proposal['runtime']);verify(proposal['runtime_closure']); closure=read(pathlib.Path(proposal['runtime_closure']['path']))
assert closure['modules'][proposal['module']]==proposal['source'];assert proposal['module'] in closure['required_after']
checks=[]; evidence={}
for f in [*sorted((P/'controller-evidence').glob('*.json')),P/'controller-semantics.proposed-v1.json']:
 d=read(f); priorref=d['reference_refresh_lineage']['prior_evidence'];verify(priorref); prior=read(pathlib.Path(priorref['path']));assert prior['status']=='ROOT_REVIEWED'
 changed=sorted(k for k in set(d)|set(prior) if d.get(k)!=prior.get(k));assert set(changed)<= {'review_evidence','reference_refresh_lineage','runtime_closure','status','runtime'}
 for r in d.get('sources',[d['source']] if 'source' in d else []):verify(r)
 assert d['runtime']==proposal['runtime'] and d['runtime_closure']==proposal['runtime_closure']
 checks.append(dict(proposal=ref(f),prior=priorref,changed_keys=changed,semantic_content_unchanged=True,source_hashes_verified=True))
 d.update(status='ROOT_REVIEWED',at=now.isoformat(),root_binding_attestation=dict(reviewer='owning_root_coordinator_turn001587',scope='Static source semantics retained; repaired runtime/closure references verified. No native instance, physical gain, scientific promotion or release certification.',proposal=ref(f),prior_review=priorref),release_enabled=False)
 if 'review_evidence' in d:
  d['review_evidence']=evidence; name='controller-semantics.root-reviewed-v1.json'
 else: name=f.stem.replace('.proposed-v1','')+'-root-reviewed-v1.json'
 out=T/name;put(out,d)
 if 'review_evidence' not in d: evidence[f.stem.replace('.proposed-v1','')]={k:v for k,v in ref(out).items() if k!='bytes'}
review=dict(schema='n36-root-controller-binding-attestation-v1',at=now.isoformat(),status='PASS_STATIC_BINDING_REFRESH_ONLY',checks=checks,controller_semantics=ref(T/'controller-semantics.root-reviewed-v1.json'),runtime=proposal['runtime'],runtime_closure=proposal['runtime_closure'],gpu_dispatch=False,release_enabled=False,independent_B5_performed=False,target_met=False)
put(T/'root-controller-binding-attestation-v1.json',review)
nextstep='Refresh only affected disabled graph consumer references to turn001587/controller-semantics.root-reviewed-v1.json and its evidence; then obtain fresh independent B5. Preserve prior graph/FAIL history. Separate protocol/adoption/readiness/prospective release gates remain required before GPU dispatch.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for p,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else read(p);d['n36_engineering_controller_binding_attestation']=ref(T/'root-controller-binding-attestation-v1.json');d['next_action']=nextstep
  if isyaml:
   q=p.with_name(p.name+'.tmp-001587');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,p)
  else:put(p,d)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='CONTROLLER_BINDING_ATTESTED_CONSUMER_REFRESH_AND_B5_PENDING',insight='Root verified exact semantic equality with prior reviewed controller evidence and current cited source hashes; repaired runtime/closure bindings attested narrowly. Disabled consumers need new refs and fresh independent B5. No native readiness, release or scientific success established.');put(C/'idea_tree.json',tree)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(v):
 p=pathlib.Path('/proc')/str(v['pid'])/'stat'; a=p.read_text().rsplit(')',1)[1].split() if p.exists() else None; ticks=int(a[19]) if a else None; match=bool(a and ticks==v['start_ticks'] and boot==v['boot_id']);return {**v,'state':a[0] if a else None,'observed_start_ticks':ticks,'identity_matches':match,'live':bool(match and a[0]!='Z')}
old.update(at=now.isoformat(),turn=1587,driver=ident(old['driver']),live_handles={k:ident(v) for k,v in old['live_handles'].items()},prior_cohort_handles={k:ident(v) for k,v in old['prior_cohort_handles'].items()},next_bounded_step=nextstep,completed_work=['Verified handoff/authority hashes, driver identity, absent prior workers and unchanged owning ledger prefixes.','Reviewed exact proposal/prior semantic differences and verified cited deployed source hashes.','Issued narrow controller binding attestation and new reviewed evidence; persisted owning state/checkpoint/tree.'],unresolved_evidence=['Affected disabled consumers need refreshed references and fresh independent B5.','Separate protocol acceptance, source/accounting adoption, native readiness and prospective releases remain pending.','Original validation/formal/required ablation goal remains unestablished.'],controller_binding_attestation=ref(T/'root-controller-binding-attestation-v1.json'))
put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n');print(json.dumps(review,indent=2))
