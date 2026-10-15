import json,pathlib,hashlib,copy
T=pathlib.Path(__file__).resolve().parent.parent; O=T/'001881'/'reviewed-graph'; O.mkdir(exist_ok=True)
H=lambda b:hashlib.sha256(b).hexdigest()
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':H(p.read_bytes())}
def read(r):
 p=pathlib.Path(r['path']);b=p.read_bytes();assert H(b)==r['sha256'];return json.loads(b)
def save(n,d):
 p=O/n;p.parent.mkdir(exist_ok=True,parents=True)
 with p.open('x') as f:json.dump(d,f,sort_keys=True,separators=(',',':'))
 return ref(p)
g=json.loads((T/'001876/canonical-successor/graph.complete-disabled-v1.json').read_text());n=copy.deepcopy(g);pairs=[]
def rep(v):
 for a,b in pairs:
  if v==a:return copy.deepcopy(b)
 if isinstance(v,dict):return {k:rep(x) for k,x in v.items()}
 if isinstance(v,list):return [rep(x) for x in v]
 return v
def bind(k,name,d=None):
 nr=save(name,rep(read(g[k])) if d is None else d);pairs.append((g[k],nr));n[k]=nr
r=ref(T/'001880/controller-semantics.root-reviewed-disabled-v1.json');pairs.append((g['controller_semantics'],r));n['controller_semantics']=r
c=read(g['recovery_prefix_contract']);c['accepted_review']=ref(T/'001879/predecessor-owner-review-v1.json');c['root_terminal_reconciliation']=ref(T/'001879/terminal-reconciliation-v1.json');c['status']='DISABLED_OWNER_RECONCILED_FIVE_PREDECESSORS'
bind('recovery_prefix_contract','recovery-prefix-contract.disabled-v1.json',c)
bind('specification','specification.disabled-v1.json')
plan=read(g['plan'])
for k in ['scope','accounting']:
 nr=save(k+'.disabled-v1.json',rep(read(plan[k])));pairs.append((plan[k],nr))
a=rep(read(g['audit']));checks=[]
for i,(key,r) in enumerate(a['expected_manifests'].items()):
 old=read(r);new=rep(old);nr=save('audit-manifests/%02d.json'%i,new);pairs.append((r,nr));a['expected_manifests'][key]=nr
 for k in ['argv','resolved_config','composed_config_sha256','row','audit_row','scientific_source','source','output_dir']:assert old.get(k)==new.get(k),k
 checks.append(key)
bind('audit','all40-audit.disabled-v1.json',a);bind('separate_engineering_manifest','engineering-manifest.disabled-v1.json');bind('plan','engineering-plan.disabled-v1.json')
n.update(status='DISABLED_OWNER_BINDINGS_COMPOSED_ADMISSION_PENDING',graph_verified=False,release_enabled=False)
save('graph.complete-disabled-v1.json',n)
save('composition-record-v1.json',dict(parent=ref(T/'001876/canonical-successor/graph.complete-disabled-v1.json'),review=n['controller_semantics'],manifest_count=len(checks)+1,source_unchanged=True,immutable_specification_references_preserved=True,release_enabled=False))
(O/'strict-production-admission-v1.py').write_bytes((T/'001876/canonical-successor/strict-production-admission-v1.py').read_bytes())
print(O)
