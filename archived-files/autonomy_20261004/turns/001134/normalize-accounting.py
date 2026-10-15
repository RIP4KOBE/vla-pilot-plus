import datetime as dt, hashlib, json, os, pathlib, sys, yaml
sys.path.insert(0,str(pathlib.Path.cwd()))
from scripts import qd_ed_final_runner as r
root=pathlib.Path.cwd(); out=(root/'../autonomy_20261004/turns/001134').resolve(); cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):
 p=pathlib.Path(p);return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');os.replace(t,p)
def handle(pid):
 p=pathlib.Path(f'/proc/{pid}/stat')
 if not p.exists():return None
 v=p.read_text().rsplit(')',1)[1].split();return {'pid':pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(v[19]),'state':v[0]}
with r.locked(root/'data/qd-ed-state.lock'):
 state=yaml.safe_load((root/'research-state.yaml').read_text());checkpoint=json.loads(cp.read_text())
 assert state['active_controller'] is None and handle(2632351) is None
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 term=json.loads((out.parent/'001133/terminal-reconciliation-v1.json').read_text()); prefix=term['ledger']; raw=(root/'data/attempt-ledger.jsonl').read_bytes();assert len(raw)==prefix['bytes'] and hashlib.sha256(raw).hexdigest()==prefix['sha256']
 events=r.read_events(root/'data/attempt-ledger.jsonl');health=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl');snap=r.budget_snapshot(events,health)
 ids={x['attempt_id'] for x in term['receipts']};local=[e for e in events if e['attempt_id'] in ids];local_h=[h for h in health if h.get('kind')=='n35_resource_preparation_v1'];cohort=r.budget_snapshot(local,local_h)
 assert snap['running']==snap['gpu_healthcheck_inflight']==0 and cohort['valid']==28 and cohort['dispatched']==28
 for k in ('dispatched','valid','invalid','aborted','completed','running','gpu_hours_consumed'):assert state['budget'][k]==snap[k]
 for e in events:
  if e['attempt_id'] in ids:assert e.get('identity',{}).get('split')=='dev'
 margin=events[-1]['accounting_admission']['retained_margin_gpu_hours'];protected={k:max(0,h-snap['gpu_hours_by_bucket'][k]) for k,h in state['budget']['gpu_hour_reservations'].items()}
 cap=min(224.,53.08404692669838+168.)
 old=state['budget_snapshot'];delta={k:snap[k]-old[k] for k in ('dispatched','valid','invalid','aborted','completed','running','gpu_hours_consumed')}
 assert delta['dispatched']==28 and abs(delta['gpu_hours_consumed']-cohort['gpu_hours_consumed'])<1e-10
 records={}
 for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','gpu-hour-reservation-ledger.jsonl'):
  p=root/'data'/name;records[name]={**ref(p),'bytes':p.stat().st_size}
 now=dt.datetime.now(dt.timezone.utc).isoformat();driver=json.loads((root/'../autonomy_20261004/driver-status.json').read_text());live={k:handle(driver[k]['pid']) for k in ('driver','process')}
 for k,v in live.items():assert v and v['start_ticks']==driver[k]['start_ticks'] and v['boot_id']==driver[k]['boot_id']
 rec={'schema':'n35-terminal-accounting-normalization-v1','at':now,'source':state['source_commit'],'prior_terminal':ref(out.parent/'001133/terminal-reconciliation-v1.json'),'ledger_prefixes':records,'prior_snapshot':old,'normalized_snapshot':snap,'delta_from_prior_snapshot':delta,'cohort_including_preparation':cohort,'retained_admission_margin_gpu_hours':margin,'conservative_charge_gpu_hours':snap['gpu_hours_consumed']+margin,'protected_remaining_gpu_hours':protected,'effective_cap_gpu_hours':cap,'unprotected_headroom_gpu_hours':cap-snap['gpu_hours_consumed']-margin-sum(protected.values()),'live_handles':live,'live_controller':None,'stop_present':(root/'../autonomy_20261004/STOP').exists(),'deadline':'2026-10-11T11:13:13Z','ledger_unchanged':True,'caps_unchanged':True,'unknown_http_telemetry_preserved':True,'target_met':False,'mechanism_review_pending':True}
 rp=out/'accounting-normalization-v1.json';write(rp,rec)
 for path in (root/'research-state.yaml',cp):(out/(path.name+'.before-accounting')).write_bytes(path.read_bytes())
 next_action='Bounded N35 Dev-only mechanism review of the 28 terminal cells: eligibility, lifecycle, proposal deltas, archive survival, executed prefix and matched outcomes; update Idea Tree disposition and select a falsifiable next step. Accounting normalized in turn001134. No valid-cell replay or protected evaluation.'
 state['budget_snapshot']=snap;checkpoint['budget_snapshot']=snap
 for d in (state,checkpoint):d['n35_terminal_accounting']=ref(rp);d['next_action']=next_action;d['updated_at']=now
 temp=root/'research-state.yaml.accounting-tmp';temp.write_text(yaml.safe_dump(state,sort_keys=False));os.replace(temp,root/'research-state.yaml');write(cp,checkpoint)
 assert hashlib.sha256((root/'data/attempt-ledger.jsonl').read_bytes()).hexdigest()==prefix['sha256']
 summary=f'''Turn001134: N35 terminal accounting normalized at {now}.\n\nSource {state['source_commit']} unchanged. Driver PID268073/start97715947 and coordinator PID4000073/start144308784 match boot {live['driver']['boot_id']}; no active experiment controller or unsettled ledger worker. STOP absent at observation; authorization ends2026-10-11T11:13:13Z. Prior turn001133 completed normally; its terminal ledger prefix is intact.\n\n502 attempts;463 valid,18 invalid,21 aborted;75.243793112159 GPUh including healthchecks. N35 28 valid episodes plus preparation cost {cohort['gpu_hours_consumed']:.12f} GPUh. Retained admission margin {margin:.12f} GPUh; conservative total {rec['conservative_charge_gpu_hours']:.12f} GPUh. Protected reserves {sum(protected.values()):.12f} GPUh remain; all history and unknown HTTP telemetry retained. State and checkpoint snapshots refreshed without modifying caps or ledgers.\n\nN35 remains rejected: C0 1/7,Q0 0/7,N34 1/7,N35 1/7; frozen upper bound4<5. Tasks7–9 unknown. No new dispatch, source/plan edits, signals or protected reads.\n\nNext: {next_action}\n\nValidation/formal/required-ablation completion evidence remains unresolved. Accounting record SHA256 {ref(rp)['sha256']}.\n'''
 (out/'operational-summary.md').write_text(summary)
 print(json.dumps({k:rec[k] for k in ('normalized_snapshot','cohort_including_preparation','conservative_charge_gpu_hours','protected_remaining_gpu_hours','unprotected_headroom_gpu_hours')},indent=2));print(ref(rp))
