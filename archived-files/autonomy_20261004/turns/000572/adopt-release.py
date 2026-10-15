import pathlib,json,hashlib,datetime,sys,subprocess,yaml,copy
root=pathlib.Path.cwd();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as r, qd_ed_n34_contract as c
out=root.parent/'autonomy_20261004/turns/000572'; base=out.parent.parent
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(v):
 p=pathlib.Path(v['path']);assert ref(p)['sha256']==v['sha256'];return json.loads(p.read_text())
def write(p,v):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def identity(pid):
 p=pathlib.Path('/proc')/str(pid)
 if not p.exists():return None
 a=(p/'stat').read_text().rsplit(')',1)[1].split();return {'pid':pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(a[19]),'state':a[0]}
prep=json.loads((out.parent/'000568/release-preparation-v2.json').read_text());plan=read(prep['plan']);release=read(prep['release']);authority=read(prep['authority']);read(authority['approval_basis'])
vpath=out.parent/'000569/full-public-release-validation-v2.json';v=json.loads(vpath.read_text());assert v['status']=='PASS' and v['manifest_count']==30 and v['plan']==prep['plan'] and v['release']==prep['release']
assert identity(2830025) is None
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'));assert not pathlib.Path(plan['stop_path']).exists()
driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==572
for key in ['driver','process']:
 actual=identity(driver[key]['pid']);assert all(actual[k]==driver[key][k] for k in ['pid','boot_id','start_ticks'])
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==plan['source']['commit']
with r.locked(root/'data/qd-ed-state.lock'):
 s=r.read_state(root/'research-state.yaml');checkpoint=json.loads(cp.read_text());assert s['active_controller'] is None and checkpoint['active_controller'] is None
 assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
 prefixes={}
 for name,expected in authority['ledger_prefixes'].items():
  b=(root/'data'/name).read_bytes();actual={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()};assert actual==expected;prefixes[name]=actual
 events=r.read_events(root/'data/attempt-ledger.jsonl');resources=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl');snap=r.budget_snapshot(events,resources);assert snap==authority['history_snapshot'] and snap['running']==0
 assert all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(events).values())
 caps=authority['caps'];assert s['budget']['max_episode_attempts']==caps['attempts'] and s['budget']['max_gpu_hours']==caps['gpu_hours'] and s['budget']['reserved']==caps['buckets'] and s['budget']['gpu_hour_reservations']==caps['protected_gpu_hours']
 for p in [root/'research-state.yaml',cp]: (out/(p.name+'.before')).write_bytes(p.read_bytes())
 entry={'at':now.isoformat(),'source':source,'driver':identity(driver['driver']['pid']),'coordinator':identity(driver['process']['pid']),'validator':None,'validation':ref(vpath),'ledger_prefixes':prefixes,'active_controller':None,'stop_exists':False,'deadline':c.DEADLINE,'prior_turn_exit':0,'target_met':False};write(out/'entry-reconciliation-v1.json',entry)
 record={'schema':'n34-root-authority-adoption-v1','at':now.isoformat(),'status':'ADOPTED_PENDING_PERSISTENT_CONTROLLER_ADMISSION','source':source,'plan':prep['plan'],'release':prep['release'],'authority':prep['authority'],'public_validation':ref(vpath),'accounting_snapshot':snap,'arithmetic':authority['arithmetic'],'window_amendment_scope':authority['window_amendment_scope'],'ledger_prefixes':prefixes,'gpu_dispatched':False,'target_met':False};write(out/'n34-authority-adoption-v1.json',record)
 update={'n34_budget_authority':prep['authority'],'n34_execution_release':prep['release'],'n34_frozen_plan':prep['plan'],'n34_public_release_validation':ref(vpath),'n34_authority_adoption':ref(out/'n34-authority-adoption-v1.json'),'n34_continuation_status':'RELEASE_ADOPTED_PENDING_CONTROLLER_ADMISSION','automatic_gpu_dispatch_scope':c.COHORT,'automatic_gpu_dispatch_authorized':True,'updated_at':now.isoformat()}
 for obj in [s,checkpoint]: obj.update(update)
 # Historical budget/window records and all prior scientific outcomes are retained.
 tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(root/'research-state.yaml');write(cp,checkpoint)
 assert r.read_state(root/'research-state.yaml')['budget']==s['budget']
 entry.update(authority_adopted=True,validation_status='PASS',gpu_dispatched=False);write(out/'end-reconciliation-v1.json',entry)
print(json.dumps(record,indent=2))
