import pathlib,json,yaml,hashlib,fcntl,os,sys,datetime
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001609';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
with (C/'state.lock').open('a') as l:
 fcntl.flock(l,fcntl.LOCK_EX)
 with (W/'data/qd-ed-state.lock').open('a') as l2:
  fcntl.flock(l2,fcntl.LOCK_EX)
  p=W/'research-state.yaml';raw=p.read_bytes();q=T/'research-state.before-cycle-repair.yaml';assert not q.exists();q.write_bytes(raw)
  cp=C/'checkpoint.json';(T/'checkpoint.before-cycle-repair.json').write_bytes(cp.read_bytes());c=json.loads(cp.read_text());s=yaml.safe_load(raw)
  keys=['n36_engineering_attested_independent_b5','n36_engineering_readiness_independent_b5']
  for k in keys:
   assert s[k]['historical_in_flight_record'] is s[k]
   h=c[k]['historical_in_flight_record'];assert h['wrapper']==s[k]['wrapper'] and h['executor']==s[k]['executor'] and h['authority']==s[k]['authority']
   s[k]['historical_in_flight_record']=h
  tmp=p.with_name(p.name+'.tmp-001609');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True))
  plan=json.loads((A/'turns/001608/engineering-plan.frozen-v2.json').read_text());sys.path.insert(0,plan['worktree'])
  from scripts import qd_ed_final_runner as r, qd_ed_n36_engineering as e
  checked=r.read_state(tmp);e.validate_state(plan,e.read(plan['authority']),checked)
  os.replace(tmp,p)
  record={'schema':'owning-state-cycle-repair-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':ref(q),'historical_record_source':ref(T/'checkpoint.before-cycle-repair.json'),'after':ref(p),'changed_paths':[k+'.historical_in_flight_record' for k in keys],'reason':'Production UniqueLoader rejects self-recursive YAML aliases; restored finite exact historical objects from owning checkpoint.','production_state_read':'PASS','production_state_validation':'PASS','gpu_dispatch':False,'scientific_changes':False}
  (T/'state-cycle-repair-v1.json').write_text(json.dumps(record,indent=2)+'\n')
print('Restored two historical records from owning checkpoint; production state reader and validator PASS')
