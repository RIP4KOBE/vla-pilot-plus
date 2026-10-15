import pathlib,json,hashlib,sys,os,copy,time,traceback
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001714';O=T/'refreshed-disabled-graph';O.mkdir(exist_ok=True)
def ref(p):
 b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest())
def read(r):
 p=pathlib.Path(r['path']);assert ref(p)['sha256']==r['sha256'];return json.loads(p.read_text())
def save(n,d):
 p=O/n;p.parent.mkdir(exist_ok=True);b=json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 with p.open('xb') as f:f.write(b)
 return ref(p)
old=json.loads((A/'turns/001713/operational-summary-v1.json').read_text())
for r in old['ledger_prefixes'].values():readbytes=pathlib.Path(r['path']).read_bytes();assert len(readbytes)==r['bytes'] and hashlib.sha256(readbytes).hexdigest()==r['sha256']
att=read(old['root_controller_acceptance']);proof=read(att['controller']);assert proof['status']=='ROOT_REVIEWED'
report=json.loads((A/'turns/001707/disabled-graph-refresh/report-v1.json').read_text());plan=read(report['graph']['engineering_plan']);audit=read(plan['audit_plan']);runtime=read(plan['runtime']);source=plan['source']
sys.dont_write_bytecode=True;sys.path.insert(0,plan['worktree']);os.chdir(plan['worktree'])
from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_bridge as b, qd_ed_n36_readiness_prepare as prep
start=time.monotonic();e.stop.check();assert source['commit']==att['current_source']['commit'];assert proof['runtime']==plan['runtime'] and proof['runtime_closure']==plan['runtime_closure']
controller={k:v for k,v in att['controller'].items() if k!='bytes'}
oldplan=copy.deepcopy(plan);oldaudit=copy.deepcopy(audit)
audit.update(controller_semantics=controller,expected_manifests={})
for row in audit['episodes']:
 e.stop.check();audit['expected_manifests'][row['episode_key']]=save('audit-manifests/'+row['episode_key']+'.json',b.manifest(audit,runtime,row))
plan.update(controller_semantics=controller,audit_plan=save('audit-view.disabled-v1.json',audit),expected_manifests={})
m=save('engineering-manifest.disabled-v1.json',b.engineering_manifest(plan,runtime,e.row(),audit=audit));plan.update(engineering_manifest=m,expected_manifests={e.EPISODE_KEY:m})
p=save('engineering-plan.draft-disabled-v1.json',plan)
assert {k:v for k,v in oldplan.items() if k not in ['controller_semantics','audit_plan','engineering_manifest','expected_manifests']}=={k:v for k,v in plan.items() if k not in ['controller_semantics','audit_plan','engineering_manifest','expected_manifests']}
assert {k:v for k,v in oldaudit.items() if k not in ['controller_semantics','expected_manifests']}=={k:v for k,v in audit.items() if k not in ['controller_semantics','expected_manifests']}
result=dict(schema='n36-root-disabled-graph-refresh-v1',authority=ref(A/'user-authorization-v1.json'),root_controller_acceptance=old['root_controller_acceptance'],prior_plan=report['graph']['engineering_plan'],graph=dict(plan=p,runtime=plan['runtime']),source=source,changed_fields=['controller_semantics','audit_plan','engineering_manifest','expected_manifests'],gpu_authorized=False,release_enabled=False,target_met=False)
try:
 prep.verify_graph(result,source,read(e.specification()['canonical_runtime']));result['status']='PASS';print('verify_graph PASS',flush=True)
except Exception as ex:
 result.update(status='FAIL',error=str(ex),traceback=traceback.format_exc());print(result['traceback'],flush=True)
result['elapsed_seconds']=time.monotonic()-start
save('refresh-result-v1.json',result)
