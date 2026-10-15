import json,hashlib,pathlib,datetime,fcntl,os,yaml
P=pathlib.Path; owner=P.cwd(); out=owner.parent/'autonomy_20261004/turns/001551'; g6=out.parent/'001548/g6-verification'; now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):
 p=P(p);b=p.read_bytes();return {'path':str(p.resolve()),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(r):
 a=ref(r['path']);assert a['sha256']==r['sha256'];return json.loads(P(r['path']).read_text())
def put(p,v):
 with P(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
 return ref(p)
prior=json.loads((out.parent/'001550/operational-summary-v1.json').read_text())
for r in prior['ledgers'].values():assert ref(r['path'])==r
assert not (owner.parent/'autonomy_20261004/STOP').exists()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
passive=json.loads((g6/'controller-passive-review-v1.json').read_text());proof=check(passive['proof']);closure=check(passive['runtime_closure']);check(passive['runtime'])
excerpts=check(passive['excerpts'])
for entry in excerpts:
 r=entry['source']; assert ref(r['path'])['sha256']==r['sha256']; lines=P(r['path']).read_text().splitlines()
 for sl in entry['slices']:assert '\n'.join(lines[sl['first_line']-1:sl['last_line']])==sl['text']
root=P('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
evidence={}
for key,r in proof['review_evidence'].items():
 e=check(r)
 for src in e['sources']:
  assert ref(src['path'])['sha256']==src['sha256']
  if '/implementation_worktree/' in src['path']:
   new=root/src['path'].split('/implementation_worktree/',1)[1];assert ref(new)['sha256']==src['sha256'];src['path']=str(new)
 e.update(at=now,status='ROOT_REVIEWED',binding_review='Root reviewed exact hash-verified source excerpts and candidate paths. Static command semantics only; loaded instance and postprocessor/decode path remain runtime obligations.',prior_evidence=r,release_enabled=False)
 evidence[key]=put(out/(key+'-root-reviewed-v1.json'),e)
proof.update(at=now,status='ROOT_REVIEWED',review_evidence=evidence,inherited_review=passive['proof'],scope='Root source-semantics approval only for bound runtime and candidate. No deployment, physical gain, release or scientific promotion certification.',root_review_evidence=ref(g6/'controller-passive-review-v1.json'))
proofref=put(out/'controller-semantics.root-reviewed-v1.json',proof)
review={'schema':'n36-controller-root-source-review-v1','at':now,'status':'PASS_SOURCE_SEMANTICS_ONLY','source':proof['source_commit'],'proof':proofref,'previous_proof':passive['proof'],'source_excerpts':passive['excerpts'],'source_excerpt_bytes_verified':True,'findings':passive['findings'],'candidate_paths_rebound':True,'physical_gain_certified':False,'actual_instance_observed':False,'release_enabled':False,'scientific_promotion':False,'next_step':'Rebind disabled G5 plan/audit and transitive manifest graph to this proof, then independent B5 on exact graph. Preserve runtime/source/science and dispatch veto.','unresolved':['G6 independent B5','G7 unconditional dispatch veto','owner adoption and detached releases','actual native/controller/postprocessor/device/provider readiness','validation/formal/required ablation completion']}
rr=put(out/'controller-root-review-v1.json',review)
next_action=review['next_step']
lock=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/state.lock'
with lock.open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX)
 for p,is_yaml in [(owner/'research-state.yaml',True),(lock.parent/'checkpoint.json',False)]:
  obj=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text())
  obj['n36_engineering_controller_root_review']=rr;obj['next_action']=next_action;obj['updated_at']=now
  tmp=p.with_name(p.name+'.turn1551.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
summary=dict(prior);summary.update(at=now,turn=1551,completed_work='Verified live driver/current coordinator identities and normal prior exit; owning ledger prefixes unchanged. Root-reviewed exact controller source excerpts; wrote separate source-only approval and candidate-path evidence. Updated state/checkpoint under owning state lock.',next_bounded_step=next_action,controller_root_review=rr)
boot=P('/proc/sys/kernel/random/boot_id').read_text().strip();summary['live_handles']=[]
for role,pid,ticks in [('driver',268073,97715947),('coordinator',2219805,151714382)]:
 parts=P(f'/proc/{pid}/stat').read_text().split(') ')[1].split();assert int(parts[19])==ticks;summary['live_handles'].append(dict(role=role,pid=pid,boot_id=boot,start_ticks=ticks,state=parts[0],identity_matches=True))
summary['unresolved_evidence']=[x for x in prior['unresolved_evidence'] if x['gate']!='G6_controller_root_approval'];summary['unresolved_evidence'].insert(0,{'gate':'G6_exact_graph_rebinding','status':'PENDING','reason':'New separate root-reviewed proof is not yet rebound into plan/audit/manifests; old artifacts retained.'})
for r in prior['ledgers'].values():assert ref(r['path'])==r
sr=put(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'review':rr,'summary':sr,'ledgers_unchanged':True,'gpu_dispatched':False}))
