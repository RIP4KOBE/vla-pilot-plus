import pathlib,json,sys,hashlib,datetime,yaml,shutil
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as r
out=(root.parent/'autonomy_20261004/turns/000630').resolve();cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(x):assert ref(x['path'])==x;return json.loads(pathlib.Path(x['path']).read_text())
def write(p,x):t=p.with_suffix('.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
prep=json.loads((out/'release-preparation-v2.json').read_text());plan=read(prep['plan']);release=read(prep['release']);a=read(plan['authority']);v=json.loads((out/'full-public-release-validation-v2.json').read_text());assert v['status']=='PASS' and v['plan']==prep['plan'] and v['release']==prep['release']
assert not pathlib.Path(plan['stop_path']).exists()
with r.locked(root/'data/qd-ed-state.lock'):
 s=r.read_state(root/'research-state.yaml');c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None
 for n,p in a['ledger_prefixes'].items():
  b=(root/'data'/n).read_bytes();assert p=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 for p in [root/'research-state.yaml',cp]:shutil.copyfile(p,out/(p.name+'.before'))
 previous=s['n34_budget_authority'];assert previous==a['previous_authority'];s['budget']['amendment']=a['amendment']
 record={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_authority':previous,'authority':plan['authority'],'plan':prep['plan'],'release':prep['release'],'validation':ref(out/'full-public-release-validation-v2.json'),'accounting':a['accounting_review'],'ledger_prefixes':a['ledger_prefixes'],'source_commit':s['source_commit'],'gpu_dispatched':False,'historical_costs_preserved':True};write(out/'authority-adoption-v1.json',record)
 for obj in [s,c]:obj.update(n34_budget_authority=plan['authority'],n34_execution_release=prep['release'],n34_frozen_plan=prep['plan'],n34_public_release_validation=record['validation'],n34r2_authority_adoption=ref(out/'authority-adoption-v1.json'),n34_continuation_status='N34R2_RELEASE_ADOPTED_ADMISSION_PENDING',automatic_gpu_dispatch_scope='N34R2_OBSERVED_JAW_APPROACH_DEV_20261008',automatic_gpu_dispatch_authorized=True,next_action='Launch one N34R2 controller using turn630 validated release after locked idle GPU7 admission; no replay, no protected evaluation.')
 tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(root/'research-state.yaml');write(cp,c)
old=out.parent/'000623';(out/'controller.py').write_text((old/'controller.py').read_text().replace('000623','000630'))
launch=(old/'launch-controller.py').read_text().replace('000623','000630').replace("==623","==630").replace('turn623 N34R1','turn630 N34R2')
(out/'launch-controller.py').write_text(launch)
write(out/'launch-preparation-v1.json',{'plan':prep['plan'],'release':prep['release'],'budget_authority':plan['authority'],'wrapper':ref(out/'controller.py'),'validation':record['validation']})
print(json.dumps(record))
