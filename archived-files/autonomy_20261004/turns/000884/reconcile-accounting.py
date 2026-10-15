import pathlib,json,hashlib,datetime,subprocess,sys,copy,yaml
w=pathlib.Path.cwd();o=(w.parent/'autonomy_20261004/turns/000884').resolve();prev=o.parent/'000882';rv=o.parent/'000883/n35-protocol-review'
sys.path.insert(0,str(w));from scripts import qd_ed_final_runner as runner
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,x):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(x,indent=2)+'\n');q.replace(p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat();d=read(w.parent/'autonomy_20261004/driver-status.json');assert d['turn']==884
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=d[k];s=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert boot==h['boot_id'] and int(s[19])==h['start_ticks']
assert not (w.parent/'autonomy_20261004/STOP').exists();assert now<'2026-10-11T11:13:13+00:00'
for pid in [2303352,2452985,2452986]:assert not pathlib.Path(f'/proc/{pid}').exists()
assert read(rv/'executor-exit-v1.json')['exit']==0
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='969d5fb57c90f61dfc93331346f0ea8158f4eaf1'
a=read(prev/'prospective-accounting-v1.json');a.update(schema='n35-prospective-accounting-v2',at=now,supersedes=ref(prev/'prospective-accounting-v1.json'),correction_review=ref(rv/'report-v1.json'))
for r in a['ledger_prefixes'].values():
 raw=pathlib.Path(r['path']).read_bytes();assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
a['effective_cumulative_caps']={'absolute_gpu_hours':224,'weekly_origin_gpu_hours':53.08404692669838,'weekly_increment_gpu_hours':168,'effective_gpu_hours':min(224,53.08404692669838+168),'authority':ref(w.parent/'week-autonomy-budget-proposal-20261004-v3.md'),'cap_increase':False}
r=a['retained_snapshot'];charged=r['gpu_hours_consumed']+r['gpu_healthcheck_hours'];a['cost_reconciliation']={'method':'Conservatively add separately retained healthcheck charge to retained attempt charge; do not assert inclusion or alter either historical snapshot.','attempt_charge_gpu_hours':r['gpu_hours_consumed'],'separate_healthcheck_gpu_hours':r['gpu_healthcheck_hours'],'total_retained_charge_gpu_hours':charged,'protected_outcomes_read':False}
ar=a['arithmetic'];ar['hours_after_max']=charged+a['cohort']['total_cap_hours'];ar['unprotected_hours_after_max']=a['effective_cumulative_caps']['effective_gpu_hours']-ar['hours_after_max']-ar['protected_validation_remaining']-ar['protected_formal_remaining'];assert ar['unprotected_hours_after_max']>0
requirement='At future admission enforce both absolute224 and original weekly-origin53.08404692669838+168 cumulative hour caps; charge attempt+separate healthcheck costs, existing reservations and full1840-second worker/cleanup reservation plus bounded healthchecks. Preserve protected remaining validation/formal reserves. Reconcile exact ledgers first; no reservation or dispatch now.'
a['adoption_requirement']=requirement;write(o/'prospective-accounting-v2.json',a)
p=read(prev/'n35-prospective-protocol-v1.json');old=copy.deepcopy(p);p.update(schema='n35-prospective-protocol-v2',at=now,supersedes=ref(prev/'n35-prospective-protocol-v1.json'),accounting=ref(o/'prospective-accounting-v2.json'),review_status='CORRECTED_ACCOUNTING_INDEPENDENT_REVIEW_PENDING');p['admission']=p['admission']+' '+requirement
for k in ['scientific_contract','decision','required_audits','episodes','limits','deadline','stop_path']:assert p[k]==old[k]
write(o/'n35-prospective-protocol-v2.json',p)
review={'schema':'n35-protocol-review-root-reconciliation-v1','at':now,'independent_review':ref(rv/'report-v1.json'),'exit':ref(rv/'executor-exit-v1.json'),'disposition':'ACCEPT_BLOCK_FINDINGS_ACCOUNTING_V2_PENDING_INDEPENDENT_REVIEW','fixed':['B1 effective dual-cap arithmetic','B2 separately retained healthcheck charge added conservatively'],'scientific_fields_unchanged':True,'source':'969d5fb57c90f61dfc93331346f0ea8158f4eaf1','live_executor_handles':[],'driver':d,'ledger_prefixes':a['ledger_prefixes'],'protocol_v2':ref(o/'n35-prospective-protocol-v2.json'),'accounting_v2':ref(o/'prospective-accounting-v2.json'),'implementation_authorized':False,'gpu_authorized':False,'target_met':False};write(o/'root-review-v1.json',review)
next_step='Obtain independent bounded review of N35 accounting/protocol v2 correcting B1/B2, preserving prior scientific PASS findings. Then separately authorize isolated CPU implementation only if review passes; no GPU/protected phase release.'
with runner.locked(w/'data/qd-ed-runner.lock',nonblocking=True):
 with runner.locked(w/'data/qd-ed-state.lock'):
  sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json';s=runner.read_state(sp);c=read(cp);t=read(tp)
  assert s['in_flight_executor']['process_record']==ref(rv/'executor-process-v1.json')
  rec=copy.deepcopy(s['n35_protocol_review']);rec.update(status='COMPLETED_BLOCK_ACCOUNTING_CORRECTED_REVIEW_PENDING',exit=ref(rv/'executor-exit-v1.json'),report=ref(rv/'report-v1.json'),root_review=ref(o/'root-review-v1.json'),live_handles=[])
  for obj in [s,c]:
   obj.update(n35_protocol_review=rec,n35_prospective_protocol=ref(o/'n35-prospective-protocol-v2.json'),n35_prospective_accounting=ref(o/'prospective-accounting-v2.json'),next_action=next_step,updated_at=now,in_flight_executor=None,in_flight_executors=[])
   for k in ['inflight_executor','inflight_executors']:
    if k in obj:obj[k]=[] if k.endswith('executors') else None
  t['nodes']['15.5'].update(status='pending',result='ACCOUNTING_V2_INDEPENDENT_REVIEW_PENDING_NO_GPU',protocol_review=rec,prospective_protocol=ref(o/'n35-prospective-protocol-v2.json'),prospective_accounting=ref(o/'prospective-accounting-v2.json'))
  for f in [sp,cp,tp]: (o/(f.name+'.before')).write_bytes(f.read_bytes())
  q=sp.with_suffix('.tmp');q.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));q.replace(sp);write(cp,c);write(tp,t)
  write(o/'adoption-v1.json',{'at':now,'root_review':ref(o/'root-review-v1.json'),'state':ref(sp),'checkpoint':ref(cp),'tree':ref(tp),'next_step':next_step})
(o/'operational-summary.md').write_text(f'''# Turn 884 operational summary\n\nSource remains `969d5fb57c90f61dfc93331346f0ea8158f4eaf1`. Driver PID268073/start97715947 and coordinator PID2456045/start140429345 verified on boot{boot}. STOP absent; deadline2026-10-11T11:13:13Z unchanged. No live GPU controller or reviewer; N34 continuation is terminal numeric futility. N35 reviewer wrapper2452985/executor2452986 exited0; no restart or replay.\n\nAccepted independent review BLOCK findings B1/B2 and wrote separately hash-bound protocol/accounting v2. Scientific contract, identities, thresholds and cohort rules unchanged. Effective cap {a['effective_cumulative_caps']['effective_gpu_hours']}h; retained attempt+healthcheck charge {charged}h; maximum post-cohort charge {ar['hours_after_max']}h; unprotected remainder {ar['unprotected_hours_after_max']}h after protected reserves. No cap increase, reservation, GPU dispatch, source edits or ledger mutation.\n\nNext: {next_step}\n\nOriginal validation/formal/required-ablation goal remains unproven. No completion record.\n''')
print(json.dumps({'arithmetic':ar,'next_step':next_step,'root_review':ref(o/'root-review-v1.json')},indent=2))
