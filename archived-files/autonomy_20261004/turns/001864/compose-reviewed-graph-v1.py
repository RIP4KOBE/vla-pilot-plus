import pathlib,json,hashlib,copy,os,datetime,yaml,subprocess
P=pathlib.Path;root=P.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001864';old=base/'turns/001859/successor-disabled-composition'
def ref(p):
 p=P(p);return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(r):
 assert ref(r['path'])['sha256']==r['sha256'];return json.loads(P(r['path']).read_text())
def save(n,d):
 p=out/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,sort_keys=True,indent=2);f.write('\n')
 return ref(p)
prev=json.loads((base/'turns/001863/operational-summary-v1.json').read_text());driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1864
boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def live(h):
 p=P('/proc')/str(h['pid'])/'stat'
 if not p.exists():return dict(pid=h['pid'],alive=False,state='absent')
 t=p.read_text().rsplit(')',1)[1].split();ticks=h.get('start_ticks') or h.get('proc_start_ticks');ok=boot==h['boot_id'] and ticks is not None and int(ticks)==int(t[19]);return dict(pid=h['pid'],boot_id=boot,start_ticks=int(t[19]),identity_verified=ok,alive=ok and t[0]!='Z',state=t[0])
handles={k:live(driver[k]) for k in ['driver','process']};assert all(x['alive'] for x in handles.values());assert not (base/'STOP').exists();assert datetime.datetime.now(datetime.timezone.utc).isoformat()<'2026-10-11T11:13:13'
s=yaml.safe_load((root/'research-state.yaml').read_text());cp=json.loads((root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json').read_text());known=[]
def walk(x):
 if isinstance(x,dict):
  if isinstance(x.get('pid'),int) and x.get('boot_id') and ('start_ticks' in x or 'proc_start_ticks' in x):known.append(live(x))
  for v in x.values():walk(v)
 elif isinstance(x,list):
  for v in x:walk(v)
walk(s);walk(cp);others=[h for h in known if h['alive'] and h['pid'] not in [v['pid'] for v in handles.values()]];assert not others
assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
for r in prev['ledger_prefixes'].values():assert ref(r['path'])['sha256']==r['sha256'] and P(r['path']).stat().st_size==r['bytes']
assert subprocess.check_output(['git','-C',prev['current_source']['worktree'],'rev-parse','HEAD'],text=True).strip()==prev['current_source']['commit']
save('live-reconciliation-v1.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),driver_handles=handles,other_live_handles=others,recorded_handles_checked=len(known),ledger_prefixes=prev['ledger_prefixes'],stop_present=False,controller_status='NO_LIVE_EXPERIMENT_CONTROLLER',prior_summary=ref(base/'turns/001863/operational-summary-v1.json')))
g=read(ref(old/'graph.complete-disabled-v1.json'));n=copy.deepcopy(g);pairs=[]
def replace(v):
 for a,b in pairs:
  if v==a:return copy.deepcopy(b)
 if isinstance(v,dict):return {k:replace(x) for k,x in v.items()}
 if isinstance(v,list):return [replace(x) for x in v]
 return v
def bind(k,name,doc=None):
 nr=save(name,replace(read(g[k])) if doc is None else doc);pairs.append((g[k],nr));n[k]=nr
contract=read(g['recovery_prefix_contract']);contract.update(accepted_review=ref(base/'turns/001862/predecessor-owner-review-v1.json'),root_terminal_reconciliation=ref(base/'turns/001862/terminal-reconciliation-v1.json'),status='ROOT_RECONCILED_HISTORICAL_PREFIXES_DISABLED_SUCCESSOR')
bind('recovery_prefix_contract','recovery-prefix-contract.disabled-v1.json',contract)
controller=ref(base/'turns/001863/controller-semantics.root-reviewed-disabled-v1.json');read(controller);pairs.append((g['controller_semantics'],controller));n['controller_semantics']=controller
bind('specification','specification.disabled-v1.json')
plan=read(g['plan'])
for key in ['scope','accounting']:
 nr=save(key+'.disabled-v1.json',replace(read(plan[key])));pairs.append((plan[key],nr))
audit=replace(read(g['audit']));index=[]
for i,row in enumerate(audit['episodes']):
 r=audit['expected_manifests'][row['episode_key']];nr=save('audit-manifests/%02d.json'%i,replace(read(r)));pairs.append((r,nr));audit['expected_manifests'][row['episode_key']]=nr;index.append(dict(row=row,original=r,new=nr))
bind('audit','all40-audit.disabled-v1.json',audit);bind('separate_engineering_manifest','engineering-manifest.disabled-v1.json');bind('plan','engineering-plan.disabled-v1.json')
n['full40_manifests']=save('full40-manifest-index-v1.json',dict(manifests=index));n.update(status='OWNER_BINDINGS_COMPOSED_DISABLED_PENDING_PRODUCTION_ADMISSION',historical_graph_only=ref(old/'graph.complete-disabled-v1.json'),review_status='SCOPED_OWNER_BINDINGS_REVIEWED_FULL_GRAPH_NOT_YET_VERIFIED')
gr=save('graph.complete-disabled-v1.json',n)
print(json.dumps(dict(graph=gr,live_handles=handles,manifests=len(index)+1)))
