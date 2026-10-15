import pathlib,json,hashlib,datetime,subprocess,sys
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/000861').resolve();sys.path.insert(0,str(root))
def ref(p):
 p=pathlib.Path(p).resolve();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(p):return json.loads(pathlib.Path(p).read_text())
def put(n,x):
 p=out/n;assert not p.exists();p.write_text(json.dumps(x,indent=2)+'\n');return ref(p)
p=read(out.parent/'000860/runtime-v1/plan.DISABLED-v1.json');original=read(p['predecessor_plan']['path']);old=read(original['authority']['path']);design=read(p['design']['path']);now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not pathlib.Path(p['stop_path']).exists();assert now < p['deadline']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==p['source']['commit']
for n,a in p['ledger_prefixes'].items():
 raw=(root/'data'/n).read_bytes();assert len(raw)==a['bytes'] and hashlib.sha256(raw).hexdigest()==a['sha256']
from scripts import qd_ed_final_runner as r
s=r.read_state(root/'research-state.yaml');snap=r.budget_snapshot(r.read_events(root/'data/attempt-ledger.jsonl'),r.read_events(root/'data/gpu-healthcheck-ledger.jsonl'))
assert snap['dispatched']==472 and snap['running']==0
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
handles={}
for pid,start in [(268073,97715947),(2296372,139942863)]:
 fields=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split();assert int(fields[19])==start;handles[str(pid)]={'start_ticks':start,'boot_id':boot,'state':fields[0]}
assert not pathlib.Path('/proc/1322966').exists()
put('entry-reconciliation-v1.json',dict(at=now,source=p['source']['commit'],handles=handles,prior_turn_exit=read(out.parent/'000860/receipt.json')['exit'],ledger_prefixes=p['ledger_prefixes'],snapshot=snap,live_gpu_controller_handles=[],stop=False))
protected={k:max(0,v-snap['gpu_hours_by_bucket'][k]) for k,v in old['caps']['protected_gpu_hours'].items()};cap=min(old['caps']['gpu_hours'],old['weekly_window']['origin_gpu_hours']+old['weekly_window']['increment_gpu_hours']);increment=20240/3600
account=put('prospective-accounting-v1.json',dict(schema='n34-continuation-accounting-v1',at=now,approval_basis=old['approval_basis'],previous_authority=original['authority'],ledger_prefixes=p['ledger_prefixes'],history_snapshot=snap,increment=p['limits'],arithmetic='11 * (1800 + 40) = 20240 seconds = 5.622222222222222 GPU hours; 472 + 11 = 483 attempts; baseline95+3=98; development290+8=298; recovery27 unchanged.',max_total_attempts=483,max_total_gpu_hours=snap['gpu_hours_consumed']+increment,effective_gpu_cap=cap,protected_remaining=protected,unprotected_after_increment=cap-snap['gpu_hours_consumed']-increment-sum(protected.values()),weekly_window_unchanged=old['weekly_window'],unknown_telemetry_preserved=True,old_plan_and_ceiling_unchanged=True))
a={'schema':'n34-continuation-budget-authority-v1','approved':True,'label':p['label'],'design':p['design'],'limits':p['limits'],'ledger_prefixes':p['ledger_prefixes'],'coordinator_ends_at':p['deadline'],'starts_at':now,'validation_authorized':False,'formal_authorized':False,'caps':old['caps'],'weekly_window':old['weekly_window'],'approval_basis':old['approval_basis'],'previous_authority':original['authority'],'history_snapshot':snap,'accounting_review':account,'amendment':{'approval':old['approval_basis'],'proposal':old['amendment']['proposal'],'previous_authority':original['authority'],'history_boundary':{'dispatched':472,'gpu_hours_consumed':snap['gpu_hours_consumed']},'prospective_accounting':account,'scope':'Only original missing11 identities, separate outcome-aware amended Dev screen; no retries, no protected-phase authorization.'}}
p['authority']=put('budget-authority-v1.json',a)
protocol=put('prospective-protocol-v1.json',dict(schema='n34-continuation-prospective-protocol-v1',at=now,design=p['design'],predecessor_plan=p['predecessor_plan'],terminal_reconciliation=p['terminal_reconciliation'],episodes=p['episodes'],retained_episode_keys=p['retained_episode_keys'],identity_mapping=p['identity_mapping'],ledger_prefixes=p['ledger_prefixes'],limits=p['limits'],gates=p['gates'],worker_contract=p['worker_contract'],scientific_interpretation=p['scientific_interpretation'],scientific_equality=p['scientific_equality'],source_commit=p['source']['commit'],deadline=p['deadline'],automatic_promotion=False,validation_requires_new_root_scientific_review=True))
p.update(schema='n34-continuation-plan-v1',frozen=True,release_enabled=True,phase_authorization={'dev':True,'validation':False,'formal':False},protocol=protocol)
pr=put('plan.frozen-v1.json',p)
expected={'schema':'n34-continuation-execution-release-v1','approved':True,'plan':pr,'design':p['design'],'label':p['label'],**{k:p[k] for k in ['source','scientific_source','scientific_equality','runtime','runtime_closure','controller_semantics','authority','limits','phase_authorization']},'automatic_promotion':False}
review=put('root-review-v1.json',{**expected,'schema':'n34-continuation-root-review-v1','decision':'APPROVED','scientific_interpretation':design['scientific_interpretation'],'retained_equivalence_reviewed':True,'validation_requires_new_root_scientific_review':True})
rr=put('execution-release-v1.json',{**expected,'root_review':review})
put('release-refs-v1.json',{'plan':pr,'release':rr})
print(json.dumps({'plan':pr,'release':rr,'adopted':False,'gpu_dispatched':False}))
