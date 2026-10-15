import os,sys,json,hashlib,subprocess,datetime as dt
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2');os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);sys.dont_write_bytecode=True;sys.path.insert(0,str(Path.cwd()))
from scripts import qd_ed_n36_stop as stop,qd_ed_n36r3_admission as a,qd_ed_n36_supervise as supervisor
OUT=Path(__file__).absolute().parent;BASE=OUT.parents[1];stop.check()
refs={}
def read(p):
 if isinstance(p,dict):
  r=p;p=Path(r['path']);raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==r['sha256']
 else:p=Path(p);raw=p.read_bytes()
 refs[str(p)]={'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};return json.loads(raw)
au=read(OUT/'authority-v1.json');plan=read(au['plan']);prior=read(BASE/'001413/source-adoption-v1.json');runtime=read(plan['runtime']);old=read(prior['runtime']);closure=read(plan['runtime_closure']);oldclosure=read(prior['runtime_closure'])
changed=subprocess.check_output(['git','diff','--name-only',prior['source']['commit'],au['source']],text=True).splitlines();assert changed==['scripts/qd_ed_n36_healthcheck.py','scripts/qd_ed_n36r3_admission.py','tests/test_n36r3_admission.py']
for k in ('protocol','protocol_review','accounting','resource_routing'):assert prior[k]==plan[k]
x={v['path']:v for v in old['files']};y={v['path']:v for v in runtime['files']};assert x.keys()==y.keys();rt=[k for k in x if x[k]!=y[k]];assert len(rt)==1 and rt[0].endswith('/scripts/qd_ed_n36_healthcheck.py')
assert {k:v for k,v in runtime.items() if k not in ('files','preparation')}=={k:v for k,v in old.items() if k not in ('files','preparation')}
assert runtime['preparation']=={'source':au['source'],'source_record':runtime['preparation']['source_record'],'status':'DISABLED_CPU_BINDING_REFRESH','runtime_ready':False,'release_enabled':False,'historical_runtime':prior['runtime'],'historical_readiness_is_not_current':True}
assert read(runtime['preparation']['source_record'])==plan['source']
assert oldclosure['modules'].keys()==closure['modules'].keys();mods=[k for k in closure['modules'] if closure['modules'][k]!=oldclosure['modules'][k]];assert mods==['scripts.qd_ed_n36_healthcheck']
assert {k:v for k,v in closure.items() if k not in ('runtime','modules')}=={k:v for k,v in oldclosure.items() if k not in ('runtime','modules')}
assert plan['native_build']['sha256']==prior['native_build']['sha256']
op=read(prior['controller_semantics']);cp=read(plan['controller_semantics'])
for k in ('instance','semantics','source','module','class','physical_gain_certified'):assert op[k]==cp[k]
for r in cp['review_evidence'].values():read(r)
assert supervisor.first_c0_boundary(plan['episodes'][0]);assert not any(supervisor.first_c0_boundary(r) for r in plan['episodes'][1:])
source=Path('scripts/qd_ed_n36r3_admission.py').read_text();assert "if k != 'time_unix'" in source and 'starts <= observed <= completed <= min(ends,' in source
accepted=read(BASE/'001334/admission-independent-review/report-v1.json')
checks=read(OUT/'checks-v1.json');assert [x['check'] for x in checks['checks'] if x['status']=='FAIL']==['accepted_001413_to_001418_001419_delta']
consumer={'schema':'n36r3-independent-b5-review-v1','decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',**{k:plan[k] for k in a.BINDINGS},'worker_receipts_are_future':True,'release_enabled':False}
p=OUT/'b5-review-v1.json'
with p.open('x') as f:json.dump(consumer,f,indent=2);f.write('\n')
read(p);cr={k:refs[str(p)][k] for k in ('path','sha256')}
a.independent_review({**plan,'b5_review':cr})
result={'status':'PASS','initial_failure_preserved':'checks-v1.json: accepted_001413_to_001418_001419_delta incorrectly required preparation metadata equality. Exact follow-up verifies source_record, new source, historical runtime and disabled/readiness flags; no production defect or binding mutation.','source_changes':changed,'runtime_file_changes':rt,'closure_module_changes':mods,'runtime_metadata_changes':['preparation'],'native_build_unchanged':True,'controller_semantics_unchanged':True,'protocol_accounting_routing_unchanged':True,'g3_first_row_only':True,'consumer_API':'qd_ed_n36r3_admission.independent_review','consumer_result':'PASS','consumer':refs[str(p)],'inputs':refs,'at':dt.datetime.now(dt.timezone.utc).isoformat()}
stop.check()
with (OUT/'delta-followup-v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='inputs'},indent=2))
