import pathlib,json,hashlib,datetime,fcntl,os,yaml
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001609';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p):return json.loads(p.read_text())
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001609');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';v=p.read_text().rsplit(')',1)[1].split() if p.exists() else [];m=bool(v and int(v[19])==h['start_ticks'] and h['boot_id']==boot);return {**h,'observed_start_ticks':int(v[19]) if v else None,'state':v[0] if v else None,'identity_matches':m,'live':bool(m and v[0]!='Z')}
s=read(T/'operational-summary-v1.json');d=read(A/'driver-status.json');now=datetime.datetime.now(datetime.timezone.utc).isoformat()
h={'wrapper':ident(read(T/'health-operation-launch-v1.json')['wrapper']),'health_operation':ident(read(T/'health-operation-process-v1.json'))}
nxt='Monitor turn001609 health wrapper/process boot/start identities and exit, health ledger and result. No duplicate healthcheck or replay: exact health identity is one-use. Settle actual health outcome and charges before preparing a separate engineering-only C0 episode release. No scientific promotion; validation/formal/required ablations remain unproven.'
s.update(at=now,turn=1609,driver=ident(d['driver']),coordinator=ident(d['process']),live_handles=h,next_bounded_step=nxt,completed_work=['Verified bound authority, normal prior completion, driver identity and private ledger prefixes.','Detached engineering health release passed unmodified production verification.','Initial launch rejected before dispatch because two historical YAML records referenced themselves; archived exact state and restored finite historical records from owning checkpoint, production state read/validation PASS.','Observed idle assigned GPU7 and launched one durable source-bootstrap health operation; wrapper and health process identities verified.'],unresolved_evidence=['Health operation is still in production pre-dispatch verification; no settled CUDA/EGL result yet.','Separate engineering-only episode release and diagnostic outcome pending.','Original matched validation/formal/required ablation evidence incomplete.'],state_cycle_repair=ref(T/'state-cycle-repair-v1.json'),health_release=ref(T/'health-release-v1.json'),health_release_consumer=ref(T/'health-release-consumer-v1.json'),target_met=False)
s['prior_ledger_prefixes']=s['ledger_prefixes'];s['ledger_prefixes']={name:{**ref(W/'data'/name),'bytes':(W/'data'/name).stat().st_size} for name in s['prior_ledger_prefixes']};s['ledgers_unchanged']=all(s['ledger_prefixes'][k]['sha256']==v['sha256'] for k,v in s['prior_ledger_prefixes'].items())
write(T/'operational-summary-v1.json',s);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n')
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 with (W/'data/qd-ed-state.lock').open('a') as lock2:
  fcntl.flock(lock2,fcntl.LOCK_EX)
  for p,y in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
   v=yaml.safe_load(p.read_text()) if y else read(p);v.update(latest_operational_summary=ref(T/'operational-summary-v1.json'),n36_engineering_state_cycle_repair=ref(T/'state-cycle-repair-v1.json'),next_action=nxt,updated_at=now);write(p,v,y)
  p=C/'idea_tree.json';v=read(p);v['nodes']['15.6'].update(result='ENGINEERING_HEALTH_OPERATION_RUNNING',insight='Detached health release verified; two self-recursive historical YAML records restored from exact checkpoint after archived pre-dispatch failure. One durable health operation running, no scientific outcome or promotion.',n36_engineering_operational_summary=ref(T/'operational-summary-v1.json'));write(p,v)
print(json.dumps({'summary':ref(T/'operational-summary-v1.json'),'live_handles':h,'ledgers_unchanged':s['ledgers_unchanged']}))
