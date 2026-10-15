import os,sys,json,hashlib,datetime as dt,subprocess,resource,signal
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2');sys.dont_write_bytecode=True;os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(60,60));signal.alarm(90)
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));OUT=Path(__file__).absolute().parent;BASE=OUT.parents[1]
from scripts import qd_ed_n36_stop as stop,qd_ed_n36r3_admission as a
stop.check(need=90)
inputs={}
def load(p):
 p=Path(p);raw=p.read_bytes();inputs[str(p)]={'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};return json.loads(raw)
def read(r):
 d=load(r['path']);assert inputs[r['path']]['sha256']==r['sha256'];return d
au=load(OUT/'authority-v1.json');p=read(au['plan']);oldreview=load(BASE/'001422/exact-b5-review/report-v1.json');old=read(oldreview['exact_plan']);runtime=read(p['runtime']);oldrt=read(old['runtime']);closure=read(p['runtime_closure']);oldcl=read(old['runtime_closure'])
names=subprocess.check_output(['git','diff','--name-only',old['source']['commit'],au['source']],text=True).splitlines();assert names==['scripts/qd_ed_n36_release.py','scripts/qd_ed_n36r3_admission.py','scripts/qd_ed_n36r3_preparation.py','tests/test_n36r3_accounting_health_repair.py']
for k in ('episodes','protocol','protocol_review','accounting','resource_routing','limits','worker_contract','deadline','stop_authority'):assert old[k]==p[k],k
x={r['path']:r for r in oldrt['files']};y={r['path']:r for r in runtime['files']};assert x.keys()==y.keys();changed=[k for k in x if x[k]!=y[k]];assert changed==[str(ROOT/'scripts/qd_ed_n36_release.py')]
assert {k:v for k,v in runtime.items() if k not in ('files','preparation')}=={k:v for k,v in oldrt.items() if k not in ('files','preparation')}
pre=runtime['preparation'];assert pre['source']==au['source'] and read(pre['source_record'])==p['source'] and pre['historical_runtime']==old['runtime']
assert {k:v for k,v in pre.items() if k not in ('source','source_record','historical_runtime')}=={k:v for k,v in oldrt['preparation'].items() if k not in ('source','source_record','historical_runtime')}
assert pre['runtime_ready'] is False and pre['historical_readiness_is_not_current'] is True
assert oldcl['modules'].keys()==closure['modules'].keys();mods=[k for k in closure['modules'] if closure['modules'][k]!=oldcl['modules'][k]];assert mods==['scripts.qd_ed_n36_release']
assert {k:v for k,v in closure.items() if k not in ('runtime','modules')}=={k:v for k,v in oldcl.items() if k not in ('runtime','modules')}
assert p['native_build']['sha256']==old['native_build']['sha256']
proof=read(p['controller_semantics']);oldproof=read(old['controller_semantics'])
for k in ('instance','semantics','source','module','class','physical_gain_certified'):assert proof[k]==oldproof[k]
inp=load(BASE/'001429/binding-refresh/runtime-input-bindings.disabled-v1.json');assert inp['runtime']==p['runtime'] and inp['runtime_closure']==p['runtime_closure'] and read(inp['source'])==p['source']
assert [r['relative_path'] for r in inp['changes']]==['scripts/qd_ed_n36_release.py']
repair=load(BASE/'001426/accounting-health-repair/report-v1.json')
for row in repair['changed_files']:
 raw=(ROOT/row['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==row['after_sha256'] and len(raw)==row['after_bytes']
# Exact B5 receipt only: no authority, adoption, runtime attestation or released plan.
receipt={'schema':'n36r3-independent-b5-review-v1','decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',**{k:p[k] for k in a.BINDINGS},'worker_receipts_are_future':True,'release_enabled':False}
assert not any(c['status']=='FAIL' and c['check']!='001422_to_current_exact_delta' for c in load(OUT/'checks-v1.json')['checks'])
path=OUT/'b5-review-v1.json'
with path.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
rr={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
a.independent_review({**p,'b5_review':rr})
stop.check()
result={'status':'PASS','at':dt.datetime.now(dt.timezone.utc).isoformat(),'source_delta':names,'runtime_file_delta':changed,'runtime_preparation_delta':['source','source_record','historical_runtime'],'runtime_closure_module_delta':mods,'unchanged_scientific_identities_gates_native_controller':True,'runtime_inventory_count':len(runtime['files']),'initial_failure':'Reviewer expected admission.py instead of release.py and omitted preparation metadata from allowed delta. Initial check retained unmodified; corrected exact comparison passed. No source or binding changed.','exact_b5_consumer':'qd_ed_n36r3_admission.independent_review passed against in-memory draft plus external receipt; no governance synthesized','b5_receipt':rr,'inputs':inputs}
with (OUT/'delta-followup-v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='inputs'}))
