import pathlib,json,hashlib,datetime,sys,fcntl
from decimal import Decimal as D
import yaml
w=pathlib.Path.cwd();sys.path.insert(0,str(w))
from scripts import qd_ed_final_runner as r,qd_ed_n36_contract as c
base=w.parent/'autonomy_20261004';out=(base/'turns/001214').resolve()
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(p):return json.loads(p.read_text())
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 s=yaml.safe_load((w/'research-state.yaml').read_text());old=read(base/'turns/001197/accounting-reconciliation-v1.json');now=datetime.datetime.now(datetime.timezone.utc)
 assert not (base/'STOP').exists() and read(base/'driver-status.json')['turn']==1214
 ledger={}
 for name,anchor in old['ledger_prefixes'].items():
  p=w/'data'/name;b=p.read_bytes();assert hashlib.sha256(b[:anchor['bytes']]).hexdigest()==anchor['sha256'];ledger[name]={**ref(p),'bytes':len(b),'prior_prefix_matches':True}
 events=[json.loads(x) for x in (w/'data/attempt-ledger.jsonl').read_text().splitlines()];resources=[json.loads(x) for x in (w/'data/gpu-healthcheck-ledger.jsonl').read_text().splitlines()]
 snap=r.budget_snapshot(events,resources);assert snap==s['budget_snapshot'];assert snap['running']==snap['gpu_healthcheck_inflight']==0
 groups=r.event_groups(events);assert all(v[-1]['event'] in r.TERMINAL for v in groups.values())
 retained=groups['n36_dev_t00_c0_001147'][-1];assert retained['event']=='aborted' and retained['gpu_process_wall_seconds']==86.40354533703066
 margin=D('0.23357169027962');charge=D(str(snap['gpu_hours_consumed']))+margin;cap=D('53.08404692669838')+168;protected=sum(max(D(0),D(str(v))-D(str(snap['gpu_hours_by_bucket'][k]))) for k,v in c.CAPS['protected_gpu_hours'].items())
 after={k:snap['by_bucket'][k]+c.LIMITS.get(k,0) for k in c.CAPS['buckets']}
 assert all(after[k]<=c.CAPS['buckets'][k] for k in after) and snap['dispatched']+40<=c.CAPS['attempts'] and cap-charge-protected-21>0
 deadline=datetime.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))
 recon={'schema':'n36r1-root-accounting-reconciliation-v1','at':now.isoformat(),'source':s['source_commit'],'approval':ref(base/'user-authorization-v1.json'),'previous_reconciliation':ref(base/'turns/001197/accounting-reconciliation-v1.json'),'ledger_prefixes':ledger,'snapshot':snap,'retained_margin_gpu_hours':str(margin),'conservative_charge_gpu_hours':str(charge),'effective_cap_gpu_hours':str(cap),'absolute_cap_gpu_hours':'224','protected_remaining_gpu_hours':str(protected),'unprotected_after_full_21h':str(cap-charge-protected-21),'attempts_after_all40':snap['dispatched']+40,'bucket_after_max':after,'cohort_arithmetic':'40*(1800+40)+1800+200=75600 seconds=21 hours; baseline10 development30 zero recovery attempts','remaining_wall_hours':(deadline-now).total_seconds()/3600,'full_cohort_wall_cap_fits_now':(deadline-now).total_seconds()>=75600,'original_aborted_attempt':{'attempt_id':'n36_dev_t00_c0_001147','gpu_seconds':86.40354533703066,'unknown_telemetry_retained':True},'accounting_inheritance':ref(base/'turns/001205/identity-repair/accounting.n36r1.unsigned-v1.json'),'protocol':ref(base/'turns/001205/identity-repair/protocol.n36r1.unsigned-v1.json'),'budget_adopted':False,'reservation_created':False,'gpu_dispatch':False,'caps_increased':False,'historical_charges_unchanged':True,'n31_deadline_unchanged':'2026-10-10T17:42:00Z','note':'Fresh arithmetic only; adoption and detached runtime production release remain pending. Recheck prefixes before adoption. No protected scientific outcomes inspected.'}
 p=out/'accounting-reconciliation-v1.json';assert not p.exists();p.write_text(json.dumps(recon,indent=2)+'\n')
 summary=read(out/'operational-summary.json');summary.update(accounting_reconciliation=ref(p),budget_snapshot=snap)
 summary['completed']+=' Reconciled complete private attempt/healthcheck journals and reservation prefix; exact N36R1 40-cell/21-hour arithmetic fits unchanged caps and preserves failed charge and protected reserves. No budget adoption yet.'
 (out/'operational-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 with open(out/'operational-summary.md','a') as f:f.write('\nFresh accounting: 503 retained attempts; all40 would total543 (baseline113/development343/validation60/formal0/recovery27). Charged75.26779409697457 + margin0.23357169027962 = '+str(charge)+' GPUh. Effective cap221.08404692669838 - conservative charge - protected'+str(protected)+' - cohort21 = '+str(cap-charge-protected-21)+' GPUh remaining. No allocation/adoption or dispatch; recheck prefixes before adoption.\n')
 print(json.dumps({'reconciliation':ref(p),'conservative_charge':str(charge),'remaining_after_protected_and_cohort':str(cap-charge-protected-21),'all40_attempts':543}))
