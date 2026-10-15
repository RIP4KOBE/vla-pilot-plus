import pathlib,json,hashlib,datetime,decimal,fcntl,copy
P=pathlib.Path; root=P.cwd(); out=(root/'../autonomy_20261004/turns/001831').resolve(); base=(out.parent/'001827/disabled-v3-binding'); boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p.read_bytes())}
def write(n,o):
 p=out/n;assert not p.exists();p.write_text(json.dumps(o,indent=2)+'\n');return ref(p)
def handle(h):
 p=P('/proc')/str(h['pid'])/'stat';v={'recorded':h,'alive':False,'identity_matches':False}
 if p.exists():
  fields=p.read_text().rsplit(')',1)[1].split();v.update(current_boot_id=boot,current_start_ticks=int(fields[19]),state=fields[0]);v['identity_matches']=h['boot_id']==boot and int(h.get('start_ticks',h.get('proc_start_ticks')))==int(fields[19]);v['alive']=v['identity_matches'] and fields[0] not in ('Z','X')
 return v
c=json.loads((base/'recovery-prefix-contract.prospective-disabled-v3.json').read_text());prior=json.loads((out.parent/'001830/operational-summary-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (root/'data/qd-ed-runner.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 captures={n:P(a['path']).read_bytes() for n,a in c['root_observed_ledger_prefixes'].items()}
 for n,b in captures.items():
  for a in [c['root_observed_ledger_prefixes'][n],prior['ledger_prefixes'][n]]:assert len(b)==a['bytes'] and sha(b)==a['sha256']
 for n,a in c['original_ledger_prefixes'].items():assert sha(captures[n][:a['bytes']])==a['sha256']
 handles=[];findings=[];raws=[]
 for pred in c['predecessors']:
  raw=P(pred['raw_sequence']['path']).read_bytes();assert sha(raw)==pred['raw_sequence']['sha256'];assert raw.endswith(b'\n');raws.append(raw)
  rows=[json.loads(l) for l in raw.splitlines()];assert rows==pred['rows'];assert [r['event'] for r in rows]==pred['events']
  for key,n in [('global_health_segment','gpu-healthcheck-ledger.jsonl'),('own_journal','readiness-preparation-ledger.jsonl')]:
   a=pred[key];assert captures[n][a['start_inclusive']:a['end_exclusive']]==raw
  for r in rows:
   for k in ['parent','process']:
    if r.get(k):handles.append(handle(r[k]))
  r=rows[-1];assert r['telemetry_complete']==pred['telemetry_complete'];assert r['gpu_process_wall_seconds']==pred['retained_charge_gpu_seconds'];assert r['provider_calls']==pred['provider_calls_retained']==1
  findings.append({k:pred[k] for k in ['resource_id','terminal_status','telemetry_complete','retained_charge_gpu_seconds','retained_charge_gpu_hours','raw_sequence']})
 assert b''.join(raws)==captures['readiness-preparation-ledger.jsonl'];assert not any(h['alive'] for h in handles)
 successor=c['successor']['resource_id'];assert all(successor.encode() not in b for b in captures.values())
 total=sum(decimal.Decimal(str(p['retained_charge_gpu_seconds'])) for p in c['predecessors'])
 review=write('recovery-binding-review-v1.json',{'schema':'n36-root-recovery-binding-review-v1','at':now,'reviewer':'owning_root_coordinator_turn001831','status':'PASS_SCOPED_HISTORICAL_RECOVERY_ACCOUNTING','candidate':ref(base/'recovery-prefix-contract.prospective-disabled-v3.json'),'source':'cd6c969cbfdf006fd017553448bed2e61fc0380e','predecessors':findings,'predecessor_identity_checks':handles,'exact_decimal_gpu_seconds':str(total),'retained_charge_gpu_hours':sum(p['retained_charge_gpu_hours'] for p in c['predecessors']),'findings':['All nine raw rows equal private/global ledger segments at original offsets.','Two aborted predecessors retain incomplete telemetry; completed predecessor is retained history only.','All predecessor parent/child identities absent; successor absent in four full ledgers.','No ledger rewrite, replay, source adoption, readiness, release or scientific promotion.'],'remaining_gates':['controller_review','source_placement','complete_graph','finite_release','pre_existing_parity_failure'],'gpu_authorized':False,'scientific_success':False})
 recon=write('terminal-reconciliation-v1.json',{'schema':'n36-recovery-binding-review-terminal-reconciliation-v1','at':now,'review':review,'live_handles':[],'root_accepts_blocking_findings':True,'ledger_prefixes':c['root_observed_ledger_prefixes'],'predecessor_identity_checks':handles,'successor':successor,'gpu_authorized':False})
 c['accepted_review']=review;c['root_terminal_reconciliation']=recon;c['status']='ROOT_REVIEWED_HISTORICAL_ACCOUNTING_ONLY_DISABLED';c['read_semantics'][-1]='Exactly three consumed predecessor sequences retained. Owning root historical reconciliation supplied; successor readiness and dispatch remain unproven and disabled.'
 cr=write('recovery-prefix-contract.root-reviewed-disabled-v3.json',c)
 spec=json.loads((base/'specification.prospective-disabled-v3.json').read_text());spec['recovery_prefix_contract']=cr
 sr=write('specification.root-reconciled-disabled-v3.json',spec)
 for n,b in captures.items():assert P(c['root_observed_ledger_prefixes'][n]['path']).read_bytes()==b
 print(json.dumps({'review':review,'reconciliation':recon,'contract':cr,'specification':sr,'retained_seconds':str(total)}))
