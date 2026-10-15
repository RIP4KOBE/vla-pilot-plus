import pathlib,json,sys,hashlib,datetime,yaml,shutil
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as r
out=(root.parent/'autonomy_20261004/turns/000690').resolve();cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(x):assert ref(x['path'])==x;return json.loads(pathlib.Path(x['path']).read_text())
def write(p,x):t=p.with_suffix('.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
prep=json.loads((out/'release-preparation-v1.json').read_text());plan=read(prep['plan']);release=read(prep['release']);a=read(plan['authority']);v=json.loads((out/'full-public-release-validation-v1.json').read_text());assert v['status']=='PASS' and v['plan']==prep['plan'] and v['release']==prep['release']
assert not pathlib.Path(plan['stop_path']).exists()
with r.locked(root/'data/qd-ed-state.lock'):
 s=r.read_state(root/'research-state.yaml');c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None
 for n,p in a['ledger_prefixes'].items():
  b=(root/'data'/n).read_bytes();assert p=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 for p in [root/'research-state.yaml',cp]:shutil.copyfile(p,out/(p.name+'.before'))
 previous=s['n34_budget_authority'];assert previous==a['previous_authority'];s['budget']['amendment']=a['amendment']
 record={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_authority':previous,'authority':plan['authority'],'plan':prep['plan'],'release':prep['release'],'validation':ref(out/'full-public-release-validation-v1.json'),'accounting':a['accounting_review'],'ledger_prefixes':a['ledger_prefixes'],'source_commit':s['source_commit'],'gpu_dispatched':False,'historical_costs_preserved':True};write(out/'authority-adoption-v1.json',record)
 for obj in [s,c]:obj.update(active_node='15.4',status='N34R8_RELEASE_ADOPTED_ADMISSION_PENDING',phase='DEV_RELEASE_ADOPTED',n34_budget_authority=plan['authority'],n34_execution_release=prep['release'],n34_frozen_plan=prep['plan'],n34_public_release_validation=record['validation'],n34r8_authority_adoption=ref(out/'authority-adoption-v1.json'),n34_continuation_status='N34R8_RELEASE_ADOPTED_ADMISSION_PENDING',automatic_gpu_dispatch_scope='N34R8_OBSERVED_JAW_APPROACH_DEV_20261008',automatic_gpu_dispatch_authorized=True,next_action='Launch one N34R8 controller using turn690 validated release after locked idle GPU7 admission; no replay, no protected evaluation.')
 tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(root/'research-state.yaml');write(cp,c)
print(json.dumps(record))
